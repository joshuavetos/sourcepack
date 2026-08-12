from __future__ import annotations

import os
import errno
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from .diff_parser import PatchFileChange
from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_OUTPUT_LIMIT, GIT_RETURNCODE_TIMEOUT, decode_git_path, run_git_bounded_input

SYMLINK_MODE: Final[str] = "120000"
TRANSITION_LIMIT: Final[int] = 64
TOTAL_ENTRY_LIMIT: Final[int] = 2048
PER_TRANSITION_ENTRY_LIMIT: Final[int] = 512
DEPTH_LIMIT: Final[int] = 8
TOTAL_EVIDENCE_LIMIT: Final[int] = 128
PER_TRANSITION_EVIDENCE_LIMIT: Final[int] = 32
STRING_LIMIT: Final[int] = 4096
IGNORE_INPUT_LIMIT_BYTES: Final[int] = 256 * 1024
IGNORE_OUTPUT_LIMIT_BYTES: Final[int] = 256 * 1024
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_WINDOWS_PATH_FALLBACK = os.name == "nt"


@dataclass
class _Budget:
    entries_remaining: int
    evidence_remaining: int


def _display(value: str, limit: int) -> tuple[str, bool]:
    return value[:limit], len(value) > limit


def classify_symlink_target(repo: Path, proposed_path: str, target: str | None, *, string_limit: int = STRING_LIMIT) -> dict:
    del repo
    if target is None:
        return {"classification": "unavailable", "unsafe": True, "target": None, "target_truncated": False}
    if not isinstance(target, str):
        shown, truncated = _display(str(target), string_limit)
        return {"classification": "malformed", "unsafe": True, "target": shown, "target_truncated": truncated}
    shown, truncated = _display(target, string_limit)
    base = {"target": shown, "target_truncated": truncated}
    if not target or "\x00" in target or "\n" in target or "\r" in target:
        return {"classification": "malformed", "unsafe": True, **base}
    windows = PureWindowsPath(target)
    if target.startswith(("\\\\?\\", "\\\\.\\")):
        return {"classification": "windows_device_path", "unsafe": True, **base}
    if target.startswith("\\\\"):
        return {"classification": "windows_unc", "unsafe": True, **base}
    if _WINDOWS_DRIVE.match(target):
        return {"classification": "windows_drive_qualified", "unsafe": True, **base}
    if target.startswith("/"):
        return {"classification": "absolute", "unsafe": True, **base}
    if target.startswith("\\") or windows.is_absolute():
        return {"classification": "windows_rooted", "unsafe": True, **base}

    # Backslashes are separators for safety classification on every platform.
    normalized_target = target.replace("\\", "/")
    proposed = proposed_path.replace("\\", "/")
    parts: list[str] = []
    escaped = False
    for part in PurePosixPath(proposed).parent.joinpath(PurePosixPath(normalized_target)).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            else:
                escaped = True
        else:
            parts.append(part)
    resolved = "/".join(parts)
    if escaped:
        return {"classification": "escapes_repository", "unsafe": True, **base}
    if resolved == proposed:
        return {"classification": "self_reference", "unsafe": True, **base}
    return {"classification": "confined_relative", "unsafe": False, **base, "resolved_path": resolved}


def _base_result(change: PatchFileChange, target: dict, tracked_authority: dict, limits: dict) -> dict:
    shown, truncated = _display(change.path, limits["string_limit"])
    return {
        "proposed_path": shown, "path_truncated": truncated, "old_git_mode": change.old_mode, "new_git_mode": change.new_mode,
        "proposed_symlink_target": target.get("target"), "unsafe_target": target,
        "worktree_evidence_phase": "pre_transition_observation", "pre_transition_state": "observed",
        "worktree_object_type": "indeterminate", "directory_nonempty": None, "entries_inspected": 0,
        "entry_count_state": "exact", "untracked_observed": False, "ignored_observed": False,
        "ignore_classification_state": "not_required", "nested_entries_observed": False,
        "unrepresented_content_observed": False, "retained_entries": [], "_unrepresented_paths": [],
        "acquisition_status": "complete", "source_exhausted": True, "tracked_path_authority": tracked_authority,
        "evidence_retained": 0, "evidence_omitted_lower_bound": 0, "evidence_limit_reached": False,
        "limits": dict(limits),
    }


def _fail(result: dict, status: str, *, error: BaseException | None = None) -> dict:
    result.update(acquisition_status=status, source_exhausted=False, entry_count_state="lower_bound", pre_transition_state="unavailable")
    if error is not None:
        result["metadata_error"] = type(error).__name__
    return result


def _safe_change_parts(path: object) -> tuple[list[str] | None, str | None]:
    if not isinstance(path, str) or not path or "\x00" in path or "\n" in path or "\r" in path:
        return None, "unsafe_proposed_path"
    if path.startswith(("/", "\\", "//")) or _WINDOWS_DRIVE.match(path):
        return None, "unsafe_proposed_path"
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None, "unsafe_proposed_path"
    return parts, None


def _open_root_strict(repo: Path) -> tuple[Path | None, int | None, BaseException | None]:
    try:
        absolute = repo.absolute()
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current /= part
            if stat.S_ISLNK(current.lstat().st_mode):
                raise OSError("symlinked repository component")
        canonical = repo.resolve(strict=True)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
            raise NotImplementedError("descriptor-backed no-follow traversal unavailable")
        fd = os.open(canonical, flags)
        return canonical, fd, None
    except (OSError, ValueError, RuntimeError, NotImplementedError) as exc:
        return None, None, exc


def _scan_transition_windows_path(
    repo: Path, result: dict, parts: list[str], tracked_paths: set[str] | None,
    tracked_authority: dict, budget: _Budget, *, entry_limit: int,
    depth_limit: int, evidence_limit: int, limits: dict,
) -> dict:
    """Bounded Windows traversal with explicit, non-descriptor authority."""
    # Path identity checks can detect many changes, but they cannot bind the
    # pathname enumerated by listdir to the objects checked immediately before
    # and after it.  Retain observations from this fallback without claiming
    # that its traversal exhausted the authoritative source.
    result.update(
        confinement_method="windows_path_identity_checks",
        descriptor_relative_confinement=False,
        acquisition_status="pathname_confinement_incomplete",
        source_exhausted=False,
        entry_count_state="lower_bound",
    )
    try:
        root = repo.resolve(strict=True)
        current = root
        for component in parts[:-1]:
            current /= component
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode):
                return _fail(result, "failed_symlink_component")
            if not stat.S_ISDIR(info.st_mode):
                return _fail(result, "failed_symlink_component")
        target_path = current / parts[-1]
        try:
            info = target_path.lstat()
        except FileNotFoundError:
            result.update(worktree_object_type="absent", directory_nonempty=False)
            return result
        if stat.S_ISLNK(info.st_mode):
            result.update(worktree_object_type="symlink", worktree_evidence_phase="current_post_transition_observation", pre_transition_state="unavailable", acquisition_status="historical_state_unavailable", source_exhausted=False, entry_count_state="lower_bound")
            return result
        if not stat.S_ISDIR(info.st_mode):
            result["worktree_object_type"] = "regular_file" if stat.S_ISREG(info.st_mode) else "other"
            return result
        result["worktree_object_type"] = "real_directory"
        if tracked_paths is None or not tracked_authority.get("complete"):
            return _fail(result, "tracked_authority_incomplete")
        stack = [(target_path, "/".join(parts), 0, (info.st_dev, info.st_ino))]
        while stack:
            directory, directory_rel, depth, identity = stack.pop()
            before = directory.lstat()
            if stat.S_ISLNK(before.st_mode) or not directory.resolve(strict=True).is_relative_to(root):
                return _fail(result, "failed_symlink_component")
            if (before.st_dev, before.st_ino) != identity:
                return _fail(result, "directory_identity_changed")
            names = sorted(os.listdir(directory), key=os.fsencode)
            after = directory.lstat()
            if stat.S_ISLNK(after.st_mode) or (after.st_dev, after.st_ino) != identity:
                return _fail(result, "directory_identity_changed")
            for name in names:
                if result["entries_inspected"] >= entry_limit:
                    result.update(acquisition_status="per_transition_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                if budget.entries_remaining <= 0:
                    result.update(acquisition_status="global_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                child_path = directory / name
                child = child_path.lstat()
                budget.entries_remaining -= 1
                result["entries_inspected"] += 1
                rel = f"{directory_rel}/{name}"
                nested = depth > 0
                result["nested_entries_observed"] |= nested
                represented = rel in tracked_paths
                if not represented:
                    result["unrepresented_content_observed"] = True
                    result["_unrepresented_paths"].append(rel)
                    result["ignore_classification_state"] = "pending"
                if len(result["retained_entries"]) < evidence_limit and budget.evidence_remaining > 0:
                    budget.evidence_remaining -= 1
                    shown, truncated = _display(rel, limits["string_limit"])
                    result["retained_entries"].append({"path": shown, "path_truncated": truncated, "_full_path": rel, "tracked": represented, "ignored": None if not represented else False, "nested": nested})
                    result["evidence_retained"] += 1
                else:
                    result["evidence_limit_reached"] = True
                    result["evidence_omitted_lower_bound"] += 1
                if stat.S_ISDIR(child.st_mode):
                    if depth >= depth_limit:
                        result.update(acquisition_status="depth_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                        return result
                    opened = child_path.lstat()
                    if stat.S_ISLNK(opened.st_mode) or not child_path.resolve(strict=True).is_relative_to(root):
                        return _fail(result, "failed_symlink_component")
                    if (opened.st_dev, opened.st_ino) != (child.st_dev, child.st_ino):
                        return _fail(result, "child_identity_changed")
                    stack.append((child_path, rel, depth + 1, (child.st_dev, child.st_ino)))
        result["directory_nonempty"] = result["entries_inspected"] > 0
        result["retained_entries"].sort(key=lambda item: item["_full_path"])
        return result
    except (OSError, ValueError, RuntimeError) as exc:
        result["directory_nonempty"] = result["entries_inspected"] > 0 or None
        return _fail(result, "read_failed", error=exc)


def _scan_transition(repo: Path, change: PatchFileChange, tracked_paths: set[str] | None, tracked_authority: dict, budget: _Budget, *, entry_limit: int, depth_limit: int, evidence_limit: int, limits: dict) -> dict:
    result = _base_result(change, classify_symlink_target(repo, change.path, change.proposed_symlink_target, string_limit=limits["string_limit"]), tracked_authority, limits)
    parts, unsafe = _safe_change_parts(change.path)
    if unsafe:
        return _fail(result, unsafe)
    canonical, root_fd, root_error = _open_root_strict(repo)
    if root_fd is None or canonical is None:
        if _WINDOWS_PATH_FALLBACK and parts is not None:
            return _scan_transition_windows_path(repo, result, parts, tracked_paths, tracked_authority, budget, entry_limit=entry_limit, depth_limit=depth_limit, evidence_limit=evidence_limit, limits=limits)
        return _fail(result, "repository_confinement_unavailable", error=root_error)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = root_fd
    opened: list[int] = [root_fd]
    try:
        assert parts is not None
        for component in parts[:-1]:
            parent_fd = os.open(component, flags, dir_fd=parent_fd)
            opened.append(parent_fd)
        try:
            info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            result.update(worktree_object_type="absent", directory_nonempty=False)
            return result
        mode = info.st_mode
        if stat.S_ISLNK(mode):
            result.update(worktree_object_type="symlink", worktree_evidence_phase="current_post_transition_observation", pre_transition_state="unavailable", acquisition_status="historical_state_unavailable", source_exhausted=False, entry_count_state="lower_bound")
            return result
        if not stat.S_ISDIR(mode):
            result["worktree_object_type"] = "regular_file" if stat.S_ISREG(mode) else "other"
            return result
        result["worktree_object_type"] = "real_directory"
        if tracked_paths is None or not tracked_authority.get("complete"):
            return _fail(result, "tracked_authority_incomplete")
        top_fd = os.open(parts[-1], flags, dir_fd=parent_fd)
        opened.append(top_fd)
        if (os.fstat(top_fd).st_dev, os.fstat(top_fd).st_ino) != (info.st_dev, info.st_ino):
            return _fail(result, "directory_identity_changed")
        stack: list[tuple[int, str, int, tuple[int, int]]] = [(top_fd, "/".join(parts), 0, (info.st_dev, info.st_ino))]
        while stack:
            directory_fd, directory_rel, depth, identity = stack.pop()
            before = os.fstat(directory_fd)
            if (before.st_dev, before.st_ino) != identity:
                return _fail(result, "directory_identity_changed")
            names = sorted(os.listdir(directory_fd), key=os.fsencode)
            after = os.fstat(directory_fd)
            if (after.st_dev, after.st_ino) != identity:
                return _fail(result, "directory_identity_changed")
            for name in names:
                if result["entries_inspected"] >= entry_limit:
                    result.update(acquisition_status="per_transition_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                if budget.entries_remaining <= 0:
                    result.update(acquisition_status="global_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                child = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                budget.entries_remaining -= 1
                result["entries_inspected"] += 1
                rel = f"{directory_rel}/{name}"
                nested = depth > 0
                result["nested_entries_observed"] |= nested
                represented = rel in tracked_paths
                if not represented:
                    result["unrepresented_content_observed"] = True
                    result["_unrepresented_paths"].append(rel)
                    result["ignore_classification_state"] = "pending"
                if len(result["retained_entries"]) < evidence_limit and budget.evidence_remaining > 0:
                    budget.evidence_remaining -= 1
                    shown, truncated = _display(rel, limits["string_limit"])
                    result["retained_entries"].append({"path": shown, "path_truncated": truncated, "_full_path": rel, "tracked": represented, "ignored": None if not represented else False, "nested": nested})
                    result["evidence_retained"] += 1
                else:
                    result["evidence_limit_reached"] = True
                    result["evidence_omitted_lower_bound"] += 1
                if stat.S_ISDIR(child.st_mode):
                    if depth >= depth_limit:
                        result.update(acquisition_status="depth_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                        return result
                    child_fd = os.open(name, flags, dir_fd=directory_fd)
                    opened.append(child_fd)
                    opened_info = os.fstat(child_fd)
                    if (opened_info.st_dev, opened_info.st_ino) != (child.st_dev, child.st_ino):
                        return _fail(result, "child_identity_changed")
                    stack.append((child_fd, rel, depth + 1, (child.st_dev, child.st_ino)))
        result["directory_nonempty"] = result["entries_inspected"] > 0
        result["retained_entries"].sort(key=lambda item: item["_full_path"])
        return result
    except (OSError, ValueError, NotImplementedError) as exc:
        status = "failed_symlink_component" if isinstance(exc, OSError) and getattr(exc, "errno", None) in {errno.ELOOP, errno.ENOTDIR} else "read_failed"
        result["directory_nonempty"] = result["entries_inspected"] > 0 or None
        return _fail(result, status, error=exc)
    finally:
        for fd in reversed(opened):
            try:
                os.close(fd)
            except OSError:
                pass


def _classify_ignored(repo: Path, inspections: list[dict], limits: dict) -> dict:
    paths_by_item = [(item, set(item.pop("_unrepresented_paths"))) for item in inspections]
    paths = sorted({path for _, item_paths in paths_by_item for path in item_paths})
    if not paths:
        for item in inspections:
            for entry in item["retained_entries"]:
                entry.pop("_full_path", None)
        return {"status": "complete", "complete": True, "reason": None, "path_count": 0, "git_invocations": 0}
    encoded = b"".join(os.fsencode(path) + b"\0" for path in paths)
    cp = run_git_bounded_input(repo, ["check-ignore", "--stdin", "-z"], encoded, input_limit_bytes=limits["ignore_input_limit_bytes"], output_limit_bytes=limits["ignore_output_limit_bytes"], accepted_returncodes=frozenset({0, 1}))
    if cp.returncode not in {0, 1}:
        status = "bounded" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "failed"
        reason = {GIT_RETURNCODE_OUTPUT_LIMIT: "git_output_limit", GIT_RETURNCODE_TIMEOUT: "git_timeout", GIT_RETURNCODE_NOT_FOUND: "git_unavailable", GIT_RETURNCODE_OS_ERROR: "git_os_error"}.get(cp.returncode, "git_check_ignore_failed")
        for item in inspections:
            if item["ignore_classification_state"] == "pending":
                item.update(ignore_classification_state=status, source_exhausted=False, entry_count_state="lower_bound", acquisition_status="ignore_classification_" + status)
            for entry in item["retained_entries"]:
                entry.pop("_full_path", None)
        return {"status": status, "complete": False, "reason": reason, "path_count": len(paths), "git_invocations": 1, "returncode": cp.returncode}
    ignored = {decode_git_path(raw) for raw in cp.stdout.split(b"\0") if raw}
    for item, item_paths in paths_by_item:
        if item["ignore_classification_state"] == "pending":
            item["ignored_observed"] = any(path in ignored for path in item_paths)
            item["untracked_observed"] = any(path not in ignored for path in item_paths)
            item["ignore_classification_state"] = "complete"
        for entry in item["retained_entries"]:
            full_path = entry.pop("_full_path", entry["path"])
            if entry["tracked"] is False:
                entry["ignored"] = full_path in ignored
    return {"status": "complete", "complete": True, "reason": None, "path_count": len(paths), "git_invocations": 1, "input_bytes": len(encoded), "output_bytes": len(cp.stdout)}


def inspect_symlink_transitions(repo: Path, changes: list[PatchFileChange], *, tracked_paths: set[str] | None, tracked_authority: dict, transition_limit: int = TRANSITION_LIMIT, total_entry_limit: int = TOTAL_ENTRY_LIMIT, per_transition_entry_limit: int = PER_TRANSITION_ENTRY_LIMIT, depth_limit: int = DEPTH_LIMIT, total_evidence_limit: int = TOTAL_EVIDENCE_LIMIT, per_transition_evidence_limit: int = PER_TRANSITION_EVIDENCE_LIMIT, string_limit: int = STRING_LIMIT, ignore_input_limit_bytes: int = IGNORE_INPUT_LIMIT_BYTES, ignore_output_limit_bytes: int = IGNORE_OUTPUT_LIMIT_BYTES) -> dict:
    limits = {"transition_limit": transition_limit, "total_entry_limit": total_entry_limit, "per_transition_entry_limit": per_transition_entry_limit, "depth_limit": depth_limit, "total_evidence_limit": total_evidence_limit, "per_transition_evidence_limit": per_transition_evidence_limit, "string_limit": string_limit, "ignore_input_limit_bytes": ignore_input_limit_bytes, "ignore_output_limit_bytes": ignore_output_limit_bytes}
    proposed = [change for change in changes if change.new_mode == SYMLINK_MODE]
    retained = proposed[:transition_limit]
    transition_limit_reached = len(proposed) > transition_limit
    budget = _Budget(total_entry_limit, total_evidence_limit)
    represented_paths = None if tracked_paths is None else set(tracked_paths)
    if represented_paths is not None:
        represented_paths.update(parent.as_posix() for path in tracked_paths for parent in PurePosixPath(path).parents if parent.as_posix() != ".")
    inspections = [_scan_transition(repo, change, represented_paths, tracked_authority, budget, entry_limit=per_transition_entry_limit, depth_limit=depth_limit, evidence_limit=per_transition_evidence_limit, limits=limits) for change in retained]
    ignore_authority = _classify_ignored(repo, inspections, limits)
    by_path = {change.path.replace("\\", "/"): item for change, item in zip(retained, inspections)}
    for change, item in zip(retained, inspections):
        peer = by_path.get(item["unsafe_target"].get("resolved_path"))
        if peer and peer["unsafe_target"].get("resolved_path") == change.path.replace("\\", "/"):
            item["unsafe_target"].update(classification="direct_cycle", unsafe=True)
    evidence_retained = total_evidence_limit - budget.evidence_remaining
    omitted = sum(item["evidence_omitted_lower_bound"] for item in inspections)
    return {"inspections": inspections, "transition_count_state": "lower_bound" if transition_limit_reached else "exact", "transitions_consumed": len(retained) + (1 if transition_limit_reached else 0), "transitions_retained": len(retained), "total_transitions": None if transition_limit_reached else len(proposed), "transition_limit_reached": transition_limit_reached, "source_exhausted": not transition_limit_reached and all(item["source_exhausted"] for item in inspections) and ignore_authority["complete"], "entries_inspected": total_entry_limit - budget.entries_remaining, "evidence_retained": evidence_retained, "evidence_omitted_lower_bound": omitted, "evidence_limit_reached": omitted > 0, "evidence_is_bounded_subset": omitted > 0, "ignore_authority": ignore_authority, "tracked_path_authority": tracked_authority, "limits": dict(limits)}


def inspect_symlink_transition(repo: Path, change: PatchFileChange, *, tracked_paths: set[str] | None = None, tracked_authority: dict | None = None, entry_limit: int = PER_TRANSITION_ENTRY_LIMIT, depth_limit: int = DEPTH_LIMIT, evidence_limit: int = PER_TRANSITION_EVIDENCE_LIMIT, string_limit: int = STRING_LIMIT, ignore_input_limit_bytes: int = IGNORE_INPUT_LIMIT_BYTES, ignore_output_limit_bytes: int = IGNORE_OUTPUT_LIMIT_BYTES) -> dict:
    authority = tracked_authority or {"source": "unavailable", "status": "unavailable", "complete": False, "reason": "trusted_tracked_paths_unavailable"}
    result = inspect_symlink_transitions(repo, [change], tracked_paths=tracked_paths, tracked_authority=authority, total_entry_limit=entry_limit, per_transition_entry_limit=entry_limit, depth_limit=depth_limit, total_evidence_limit=evidence_limit, per_transition_evidence_limit=evidence_limit, string_limit=string_limit, ignore_input_limit_bytes=ignore_input_limit_bytes, ignore_output_limit_bytes=ignore_output_limit_bytes)
    return result["inspections"][0]
