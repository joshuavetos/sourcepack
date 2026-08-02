from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from .diff_parser import PatchFileChange
from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_OUTPUT_LIMIT, GIT_RETURNCODE_TIMEOUT, run_git_bounded_input

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
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass
class _Budget:
    entries_remaining: int
    evidence_remaining: int


def classify_symlink_target(repo: Path, proposed_path: str, target: str | None) -> dict:
    del repo
    if target is None:
        return {"classification": "unavailable", "unsafe": True, "target": None}
    if not isinstance(target, str) or "\x00" in target or "\n" in target:
        return {"classification": "malformed", "unsafe": True, "target": str(target)[:STRING_LIMIT]}
    retained = target[:STRING_LIMIT]
    if len(target) > STRING_LIMIT:
        return {"classification": "malformed", "unsafe": True, "target": retained, "truncated": True}
    if _WINDOWS_DRIVE.match(target):
        return {"classification": "windows_drive_qualified", "unsafe": True, "target": retained}
    if target.startswith("/"):
        return {"classification": "absolute", "unsafe": True, "target": retained}
    parts: list[str] = []
    escaped = False
    for part in PurePosixPath(proposed_path).parent.joinpath(PurePosixPath(target)).parts:
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
        return {"classification": "escapes_repository", "unsafe": True, "target": retained}
    if resolved == proposed_path:
        return {"classification": "self_reference", "unsafe": True, "target": retained}
    return {"classification": "confined_relative", "unsafe": False, "target": retained, "resolved_path": resolved}


def _base_result(change: PatchFileChange, target: dict, tracked_authority: dict) -> dict:
    return {
        "proposed_path": change.path[:STRING_LIMIT], "old_git_mode": change.old_mode, "new_git_mode": change.new_mode,
        "proposed_symlink_target": target.get("target"), "unsafe_target": target,
        "worktree_evidence_phase": "pre_transition_observation", "pre_transition_state": "observed",
        "worktree_object_type": "indeterminate", "directory_nonempty": None, "entries_inspected": 0,
        "entry_count_state": "exact", "untracked_observed": False, "ignored_observed": False,
        "ignore_classification_state": "not_required", "nested_entries_observed": False,
        "unrepresented_content_observed": False, "retained_entries": [], "_unrepresented_paths": [],
        "acquisition_status": "complete", "source_exhausted": True, "tracked_path_authority": tracked_authority,
        "limits": {
            "transition_limit": TRANSITION_LIMIT, "total_entry_limit": TOTAL_ENTRY_LIMIT,
            "per_transition_entry_limit": PER_TRANSITION_ENTRY_LIMIT, "depth_limit": DEPTH_LIMIT,
            "total_evidence_limit": TOTAL_EVIDENCE_LIMIT, "per_transition_evidence_limit": PER_TRANSITION_EVIDENCE_LIMIT,
            "string_limit": STRING_LIMIT, "ignore_input_limit_bytes": IGNORE_INPUT_LIMIT_BYTES,
            "ignore_output_limit_bytes": IGNORE_OUTPUT_LIMIT_BYTES,
        },
    }


def _scan_transition(repo: Path, change: PatchFileChange, tracked_paths: set[str] | None, tracked_authority: dict, budget: _Budget, *, entry_limit: int, depth_limit: int, evidence_limit: int) -> dict:
    result = _base_result(change, classify_symlink_target(repo, change.path, change.proposed_symlink_target), tracked_authority)
    path = repo / change.path
    try:
        current = repo
        for component in PurePosixPath(change.path).parts[:-1]:
            current /= component
            if stat.S_ISLNK(current.lstat().st_mode):
                result.update(acquisition_status="failed_symlink_component", source_exhausted=False, entry_count_state="lower_bound", pre_transition_state="unavailable")
                return result
        mode = path.lstat().st_mode
    except FileNotFoundError:
        result.update(worktree_object_type="absent", directory_nonempty=False)
        return result
    except OSError as exc:
        result.update(acquisition_status="metadata_failed", source_exhausted=False, entry_count_state="lower_bound", pre_transition_state="unavailable", metadata_error=type(exc).__name__)
        return result
    if stat.S_ISLNK(mode):
        result.update(worktree_object_type="symlink", worktree_evidence_phase="current_post_transition_observation", pre_transition_state="unavailable", acquisition_status="historical_state_unavailable", source_exhausted=False, entry_count_state="lower_bound")
        return result
    if not stat.S_ISDIR(mode):
        result["worktree_object_type"] = "regular_file" if stat.S_ISREG(mode) else "other"
        return result
    result["worktree_object_type"] = "real_directory"
    if tracked_paths is None or not tracked_authority.get("complete"):
        result.update(acquisition_status="tracked_authority_incomplete", source_exhausted=False, entry_count_state="lower_bound")
        return result
    stack = [(path, 0)]
    try:
        while stack:
            directory, depth = stack.pop()
            entries = sorted(os.scandir(directory), key=lambda item: os.fsencode(item.name))
            for entry in entries:
                if result["entries_inspected"] >= entry_limit:
                    result.update(acquisition_status="per_transition_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                if budget.entries_remaining <= 0:
                    result.update(acquisition_status="global_entry_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                    return result
                budget.entries_remaining -= 1
                result["entries_inspected"] += 1
                rel = Path(entry.path).relative_to(repo).as_posix()
                nested = depth > 0
                result["nested_entries_observed"] |= nested
                represented = rel in tracked_paths
                if not represented:
                    result["unrepresented_content_observed"] = True
                    result["_unrepresented_paths"].append(rel)
                    result["ignore_classification_state"] = "pending"
                if len(result["retained_entries"]) < evidence_limit and budget.evidence_remaining > 0:
                    budget.evidence_remaining -= 1
                    result["retained_entries"].append({"path": rel[:STRING_LIMIT], "tracked": represented, "ignored": None if not represented else False, "nested": nested})
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    if depth >= depth_limit:
                        result.update(acquisition_status="depth_limit_reached", source_exhausted=False, entry_count_state="lower_bound", directory_nonempty=True)
                        return result
                    stack.append((Path(entry.path), depth + 1))
        result["directory_nonempty"] = result["entries_inspected"] > 0
        result["retained_entries"] = sorted(result["retained_entries"], key=lambda item: item["path"])
        return result
    except OSError as exc:
        result.update(acquisition_status="read_failed", source_exhausted=False, entry_count_state="lower_bound", metadata_error=type(exc).__name__, directory_nonempty=result["entries_inspected"] > 0 or None)
        return result


def _classify_ignored(repo: Path, inspections: list[dict]) -> dict:
    paths_by_item = [(item, set(item.pop("_unrepresented_paths"))) for item in inspections]
    paths = sorted({path for _, item_paths in paths_by_item for path in item_paths})
    if not paths:
        return {"status": "complete", "complete": True, "reason": None, "path_count": 0, "git_invocations": 0}
    encoded = b"".join(os.fsencode(path) + b"\0" for path in paths)
    cp = run_git_bounded_input(repo, ["check-ignore", "--stdin", "-z"], encoded, input_limit_bytes=IGNORE_INPUT_LIMIT_BYTES, output_limit_bytes=IGNORE_OUTPUT_LIMIT_BYTES)
    if cp.returncode not in {0, 1}:
        status = "bounded" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "failed"
        reason = {
            GIT_RETURNCODE_OUTPUT_LIMIT: "git_output_limit",
            GIT_RETURNCODE_TIMEOUT: "git_timeout",
            GIT_RETURNCODE_NOT_FOUND: "git_unavailable",
            GIT_RETURNCODE_OS_ERROR: "git_os_error",
        }.get(cp.returncode, "git_check_ignore_failed")
        for item in inspections:
            if item["ignore_classification_state"] == "pending":
                item["ignore_classification_state"] = status
                item["source_exhausted"] = False
                item["entry_count_state"] = "lower_bound"
                item["acquisition_status"] = "ignore_classification_" + status
        return {"status": status, "complete": False, "reason": reason, "path_count": len(paths), "git_invocations": 1, "returncode": cp.returncode}
    ignored = {os.fsdecode(raw).replace("\\", "/") for raw in cp.stdout.split(b"\0") if raw}
    for item, item_paths in paths_by_item:
        if item["ignore_classification_state"] != "pending":
            continue
        item["ignored_observed"] = any(path in ignored for path in item_paths)
        item["untracked_observed"] = any(path not in ignored for path in item_paths)
        item["ignore_classification_state"] = "complete"
        for entry in item["retained_entries"]:
            if entry["tracked"] is False:
                entry["ignored"] = entry["path"] in ignored
    return {"status": "complete", "complete": True, "reason": None, "path_count": len(paths), "git_invocations": 1, "input_bytes": len(encoded), "output_bytes": len(cp.stdout)}


def inspect_symlink_transitions(repo: Path, changes: list[PatchFileChange], *, tracked_paths: set[str] | None, tracked_authority: dict, transition_limit: int = TRANSITION_LIMIT, total_entry_limit: int = TOTAL_ENTRY_LIMIT, per_transition_entry_limit: int = PER_TRANSITION_ENTRY_LIMIT, depth_limit: int = DEPTH_LIMIT, total_evidence_limit: int = TOTAL_EVIDENCE_LIMIT, per_transition_evidence_limit: int = PER_TRANSITION_EVIDENCE_LIMIT) -> dict:
    proposed = [change for change in changes if change.new_mode == SYMLINK_MODE and not change.unsafe_path]
    retained = proposed[:transition_limit]
    transition_limit_reached = len(proposed) > transition_limit
    budget = _Budget(total_entry_limit, total_evidence_limit)
    represented_paths = None if tracked_paths is None else set(tracked_paths)
    if represented_paths is not None:
        represented_paths.update(parent.as_posix() for path in tracked_paths for parent in PurePosixPath(path).parents if parent.as_posix() != ".")
    inspections = [_scan_transition(repo, change, represented_paths, tracked_authority, budget, entry_limit=per_transition_entry_limit, depth_limit=depth_limit, evidence_limit=per_transition_evidence_limit) for change in retained]
    ignore_authority = _classify_ignored(repo, inspections)
    by_path = {item["proposed_path"]: item for item in inspections}
    for item in inspections:
        peer = by_path.get(item["unsafe_target"].get("resolved_path"))
        if peer and peer["unsafe_target"].get("resolved_path") == item["proposed_path"]:
            item["unsafe_target"].update(classification="direct_cycle", unsafe=True)
    return {
        "inspections": inspections, "transition_count_state": "lower_bound" if transition_limit_reached else "exact",
        "transitions_consumed": len(retained) + (1 if transition_limit_reached else 0), "transitions_retained": len(retained),
        "total_transitions": None if transition_limit_reached else len(proposed), "transition_limit_reached": transition_limit_reached,
        "source_exhausted": not transition_limit_reached and all(item["source_exhausted"] for item in inspections) and ignore_authority["complete"],
        "entries_inspected": total_entry_limit - budget.entries_remaining, "evidence_retained": total_evidence_limit - budget.evidence_remaining,
        "ignore_authority": ignore_authority, "tracked_path_authority": tracked_authority,
        "limits": {"transition_limit": transition_limit, "total_entry_limit": total_entry_limit, "total_evidence_limit": total_evidence_limit},
    }


def inspect_symlink_transition(repo: Path, change: PatchFileChange, *, tracked_paths: set[str] | None = None, tracked_authority: dict | None = None, entry_limit: int = PER_TRANSITION_ENTRY_LIMIT, depth_limit: int = DEPTH_LIMIT, evidence_limit: int = PER_TRANSITION_EVIDENCE_LIMIT) -> dict:
    authority = tracked_authority or {"source": "unavailable", "status": "unavailable", "complete": False, "reason": "trusted_tracked_paths_unavailable"}
    result = inspect_symlink_transitions(repo, [change], tracked_paths=tracked_paths, tracked_authority=authority, total_entry_limit=entry_limit, per_transition_entry_limit=entry_limit, depth_limit=depth_limit, total_evidence_limit=evidence_limit, per_transition_evidence_limit=evidence_limit)
    return result["inspections"][0]
