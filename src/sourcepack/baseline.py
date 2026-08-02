from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from .git import (
    GIT_RETURNCODE_NOT_FOUND,
    GIT_RETURNCODE_OS_ERROR,
    GIT_RETURNCODE_TIMEOUT,
    metadata as canonical_git_metadata,
    run_git,
    run_git_bytes,
)
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths

DEFAULT_SOURCEPACKIGNORE = (
    "# SourcePack ignore rules\n.env\nnode_modules/\ndist/\nbuild/\n"
)
DEFAULT_SOURCEPACK_CONFIG = json.dumps(
    {"max_file_size": 1_000_000, "include_hidden": False, "redact_secrets": True},
    indent=2,
)
_DIR_FD_NOFOLLOW_SUPPORTED = (
    hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
    and os.open in os.supports_dir_fd
)


def protected_baseline_path(path: str) -> bool:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return (
        p.startswith(".sourcepack/baseline/") or p == ".sourcepack/state/baseline.lock"
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaselineLockError(RuntimeError):
    pass


def _rel_to_repo(repo: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _read_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    return data, None


def _read_repo_json_nofollow(repo: Path, relative: tuple[str, ...], *, byte_limit: int = 1024 * 1024) -> tuple[dict | None, str | None]:
    """Read repository metadata without following any path component on POSIX."""
    if not relative or any(part in {"", ".", ".."} or "/" in part or "\\" in part for part in relative):
        return None, "unsafe repository-relative path"
    if not _DIR_FD_NOFOLLOW_SUPPORTED:
        # Windows lacks the dir-fd/no-follow primitives used for this trust
        # boundary.  Reject symlinked components, then retain the existing
        # stable final-path behavior rather than claiming descriptor authority.
        current = repo
        try:
            for part in relative:
                current = current / part
                if current.is_symlink():
                    return None, "symlinked repository component"
            if not current.exists():
                return None, "missing"
        except OSError as exc:
            return None, f"unreadable: {exc}"
        return _read_json_file(current)

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_BINARY", 0)
    descriptors: list[int] = []
    try:
        parent_fd = os.open(repo, directory_flags)
        descriptors.append(parent_fd)
        for component in relative[:-1]:
            parent_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            descriptors.append(parent_fd)
        fd = os.open(relative[-1], file_flags, dir_fd=parent_fd)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > byte_limit:
            return None, "not a regular file or byte limit exceeded"
        raw = bytearray()
        while len(raw) <= byte_limit:
            block = os.read(fd, min(65536, byte_limit + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(fd)
        if len(raw) > byte_limit:
            return None, "byte limit exceeded"
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ) or len(raw) != before.st_size:
            return None, "file changed during read"
        data = json.loads(bytes(raw).decode("utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable or symlinked repository component: {exc}"
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    return data, None


def _baseline_ancestor_error(repo: Path) -> str | None:
    """Reject baseline storage reached through a symlinked repository component."""
    current = repo
    for component in (".sourcepack", "baseline"):
        current = current / component
        try:
            info = current.stat(follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as exc:
            return f"baseline ancestor unreadable: {exc}"
        if stat.S_ISLNK(info.st_mode):
            return f"baseline ancestor {component} must not be a symlink"
        if not stat.S_ISDIR(info.st_mode):
            return f"baseline ancestor {component} must be a directory"
    return None


def baseline_corrupt_result(
    repo: Path,
    message: str,
    details: dict | None = None,
    packet_path: Path | None = None,
    metadata_path: Path | None = None,
    active_pointer_path: Path | None = None,
    mode: str = "none",
    active_build_id: str | None = None,
) -> dict:
    return {
        "ok": False,
        "state": "corrupt",
        "finding_id": "baseline_corrupt",
        "message": "Trusted SourcePack baseline is corrupt or unverifiable. Recreate the baseline only after verifying the current repo state should be trusted.",
        "details": {"reason": message, **(details or {})},
        "packet_path": _rel_to_repo(repo, packet_path),
        "metadata_path": _rel_to_repo(repo, metadata_path),
        "active_pointer_path": _rel_to_repo(repo, active_pointer_path),
        "mode": mode,
        "active_build_id": active_build_id,
    }


def resolve_active_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve()
    paths = sourcepack_paths(repo)
    ancestor_error = _baseline_ancestor_error(repo)
    if ancestor_error:
        return baseline_corrupt_result(repo, ancestor_error, mode="none")
    pointer = paths["active_pointer"]
    if pointer.is_symlink():
        return baseline_corrupt_result(
            repo, "active.json must not be a symlink", active_pointer_path=pointer, mode="pointer"
        )
    if pointer.exists():
        data, err = _read_repo_json_nofollow(repo, (".sourcepack", "baseline", "active.json"))
        if err:
            return baseline_corrupt_result(
                repo, f"active.json {err}", active_pointer_path=pointer, mode="pointer"
            )
        build_id = data.get("active_build_id")
        if (
            not isinstance(build_id, str)
            or not build_id
            or "/" in build_id
            or "\\" in build_id
            or build_id in {".", ".."}
        ):
            return baseline_corrupt_result(
                repo,
                "active.json has invalid active_build_id",
                active_pointer_path=pointer,
                mode="pointer",
            )
        if paths["builds"].is_symlink():
            return baseline_corrupt_result(
                repo, "baseline builds directory must not be a symlink", active_pointer_path=pointer, mode="pointer", active_build_id=build_id
            )
        unresolved_build_dir = paths["builds"] / build_id
        if unresolved_build_dir.is_symlink():
            return baseline_corrupt_result(
                repo, "active baseline build must not be a symlink", active_pointer_path=pointer, mode="pointer", active_build_id=build_id
            )
        build_dir = unresolved_build_dir.resolve()
        builds_dir = paths["builds"].resolve()
        try:
            build_dir.relative_to(builds_dir)
        except ValueError:
            return baseline_corrupt_result(
                repo,
                "active.json points outside baseline builds",
                active_pointer_path=pointer,
                mode="pointer",
                active_build_id=build_id,
            )
        packet = build_dir / "packet"
        meta = build_dir / "metadata.json"
        if packet.is_symlink() or meta.is_symlink():
            return baseline_corrupt_result(
                repo, "active baseline artifacts must not be symlinks", packet_path=packet, metadata_path=meta, active_pointer_path=pointer, mode="pointer", active_build_id=build_id
            )
        if not build_dir.exists() or not packet.exists():
            return baseline_corrupt_result(
                repo,
                "active.json points to a missing build",
                packet_path=packet,
                metadata_path=meta,
                active_pointer_path=pointer,
                mode="pointer",
                active_build_id=build_id,
            )
        return {
            "ok": True,
            "state": "resolved",
            "mode": "pointer",
            "packet_path": _rel_to_repo(repo, packet),
            "metadata_path": _rel_to_repo(repo, meta),
            "active_pointer_path": _rel_to_repo(repo, pointer),
            "active_build_id": build_id,
            "details": {},
        }
    legacy = paths["packet"]
    if legacy.is_symlink() or paths["baseline_meta"].is_symlink():
        return baseline_corrupt_result(
            repo, "legacy baseline artifacts must not be symlinks", packet_path=legacy, metadata_path=paths["baseline_meta"], mode="legacy"
        )
    if legacy.exists():
        legacy_artifacts = {
            "manifest.json",
            "receipt.json",
            "reality_map.json",
            "context.md",
            "ai_instructions.md",
        }
        present = (
            {child.name for child in legacy.iterdir()} if legacy.is_dir() else set()
        )
        if (legacy / "manifest.json").exists():
            return {
                "ok": True,
                "state": "resolved",
                "mode": "legacy",
                "packet_path": _rel_to_repo(repo, legacy),
                "metadata_path": _rel_to_repo(repo, paths["baseline_meta"]),
                "active_pointer_path": None,
                "active_build_id": None,
                "details": {},
            }
        if present & legacy_artifacts:
            return baseline_corrupt_result(
                repo,
                "legacy baseline packet has baseline artifacts but is missing manifest.json",
                packet_path=legacy,
                mode="legacy",
            )
    return {
        "ok": False,
        "state": "missing",
        "finding_id": "baseline_missing",
        "message": "No trusted SourcePack baseline exists while changes are present.",
        "details": {},
        "packet_path": None,
        "metadata_path": None,
        "active_pointer_path": None,
        "mode": "none",
        "active_build_id": None,
    }


def _validate_packet_artifacts(repo: Path, packet: Path) -> dict | None:
    from .packet import verify_packet

    with redirect_stdout(io.StringIO()):
        verified = verify_packet(packet)
    if not verified:
        return baseline_corrupt_result(
            repo, "canonical packet verification failed", packet_path=packet
        )
    return None


def validate_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve()
    resolved = resolve_active_baseline(repo)
    if resolved.get("state") in {"corrupt", "missing"}:
        return resolved
    packet = repo / resolved["packet_path"] if resolved.get("packet_path") else None
    meta = repo / resolved["metadata_path"] if resolved.get("metadata_path") else None
    ancestor_error = _baseline_ancestor_error(repo)
    if ancestor_error:
        return baseline_corrupt_result(repo, ancestor_error, packet_path=packet, metadata_path=meta, mode=resolved.get("mode", "none"))
    corrupt = _validate_packet_artifacts(repo, packet)
    if corrupt:
        corrupt.update(
            {
                "mode": resolved.get("mode", "none"),
                "metadata_path": resolved.get("metadata_path"),
                "active_pointer_path": resolved.get("active_pointer_path"),
                "active_build_id": resolved.get("active_build_id"),
            }
        )
        return corrupt
    ancestor_error = _baseline_ancestor_error(repo)
    if ancestor_error:
        return baseline_corrupt_result(repo, ancestor_error, packet_path=packet, metadata_path=meta, mode=resolved.get("mode", "none"))
    if resolved.get("mode") == "pointer" and resolved.get("active_build_id"):
        _, err = _read_repo_json_nofollow(
            repo,
            (".sourcepack", "baseline", "builds", str(resolved["active_build_id"]), "metadata.json"),
        )
    else:
        _, err = _read_repo_json_nofollow(repo, (".sourcepack", "baseline", "metadata.json"))
        if err == "missing":
            err = None
    if err:
        return baseline_corrupt_result(
            repo,
            f"metadata.json {err}",
            packet_path=packet,
            metadata_path=meta,
            active_pointer_path=(
                repo / resolved["active_pointer_path"]
                if resolved.get("active_pointer_path")
                else None
            ),
            mode=resolved.get("mode", "none"),
            active_build_id=resolved.get("active_build_id"),
        )
    paths = sourcepack_paths(repo)
    stale_details, stale_error = _read_repo_json_nofollow(
        repo, (".sourcepack", "state", "baseline_stale.json")
    )
    stale = stale_error != "missing"
    if stale_error:
        stale_details = {"reason": "unreadable", "acquisition_error": stale_error}
    return {
        "ok": True,
        "state": "stale" if stale else "present",
        "finding_id": "baseline_stale" if stale else None,
        "message": (
            "Trusted SourcePack baseline may not match current repo state."
            if stale
            else "Trusted SourcePack baseline is present."
        ),
        "details": {"stale_details": stale_details} if stale else {},
        "packet_path": resolved.get("packet_path"),
        "metadata_path": resolved.get("metadata_path"),
        "active_pointer_path": resolved.get("active_pointer_path"),
        "mode": resolved.get("mode"),
        "active_build_id": resolved.get("active_build_id"),
    }


def acquire_baseline_lock(
    repo: str | Path, command: str | None = None
) -> tuple[Path, int]:
    paths = ensure_sourcepack_dirs(repo)
    lock = paths["baseline_lock"]
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BaselineLockError(
            "Another SourcePack baseline operation is already in progress."
        ) from exc
    os.write(
        fd,
        json.dumps(
            {"pid": os.getpid(), "command": command, "started_at": utc_now()}
        ).encode("utf-8"),
    )
    os.fsync(fd)
    return lock, fd


def release_baseline_lock(lock: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _unique_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"


def _write_baseline_packet(repo: Path, packet: Path) -> None:
    from .packet import PacketWriter, SourceScanner

    scanner = SourceScanner(repo).scan()
    if not scanner.authority["complete"]:
        raise RuntimeError(f"repository traversal incomplete: {scanner.authority['reason']}")
    PacketWriter(packet, scanner, force=True).write_all()


def _verify_baseline_packet(packet: Path) -> bool:
    from .packet import verify_packet

    return verify_packet(packet)


def _run_git(repo: Path, args: list[str]):
    return run_git(repo, args)


def _git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    root = Path(repo)
    cp = _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
        return False, "git_unavailable"
    if cp.returncode == GIT_RETURNCODE_TIMEOUT:
        return False, "git_timeout"
    if cp.returncode == GIT_RETURNCODE_OS_ERROR:
        return False, "git_error"
    if cp.returncode != 0:
        stderr = str(cp.stderr or "").lower()
        if "not a git repository" in stderr:
            return False, "not_git"
        return False, "git_error"
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    protected = [
        line
        for line in lines
        if protected_baseline_path(line[3:] if len(line) > 3 else line)
    ]
    non_baseline = [line for line in lines if line not in protected]
    if non_baseline:
        return True, None
    if protected:
        return False, "baseline_only_dirty"
    return False, None


def _status_path(line: str) -> str:
    return line[3:] if len(line) > 3 else line


def _gitignore_change_is_exact_sourcepack_addition(repo: str | Path) -> bool:
    repo = Path(repo)
    cp = _run_git(repo, ["status", "--porcelain", "--", ".gitignore"])
    if cp.returncode != 0:
        return False
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    if len(lines) != 1 or _status_path(lines[0]) != ".gitignore":
        return False
    status = lines[0][:2]
    if status not in {"??", " M", "M "}:
        return False
    try:
        current = (repo / ".gitignore").read_bytes()
    except OSError:
        return False
    if status == "??":
        return current in {
            b".sourcepack\n",
            b".sourcepack/\n",
            b".sourcepack\r\n",
            b".sourcepack/\r\n",
        }
    before_cp = run_git_bytes(repo, ["show", "HEAD:.gitignore"])
    if before_cp.returncode != 0:
        return False
    before = before_cp.stdout
    if any(
        line.strip() in {b".sourcepack", b".sourcepack/", b".sourcepack/*"}
        for line in before.splitlines()
    ):
        return False
    before_lines = before.splitlines()
    current_lines = current.splitlines()
    if not current.endswith((b"\n", b"\r\n")):
        return False
    return current_lines in (
        before_lines + [b".sourcepack"],
        before_lines + [b".sourcepack/"],
    )


def _bootstrap_file_change_is_exact(repo: Path, rel: str, expected: str) -> bool:
    cp = _run_git(repo, ["status", "--porcelain", "--", rel])
    if cp.returncode != 0:
        return False
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    if not lines:
        return True
    if len(lines) != 1 or lines[0][:2] != "??" or _status_path(lines[0]) != rel:
        return False
    try:
        return (repo / rel).read_text(encoding="utf-8") == expected
    except OSError:
        return False


def _only_sourcepack_bootstrap_changes(repo: str | Path) -> bool:
    repo = Path(repo)
    cp = _run_git(repo, ["status", "--porcelain", "-uall"])
    if cp.returncode != 0:
        return False
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    if not lines:
        return False
    allowed = {".gitignore", ".sourcepackignore", "sourcepack.config.json"}
    for line in lines:
        rel = _status_path(line)
        if protected_baseline_path(rel):
            continue
        if rel not in allowed:
            return False
    if any(
        _status_path(line) == ".gitignore" for line in lines
    ) and not _gitignore_change_is_exact_sourcepack_addition(repo):
        return False
    if not _bootstrap_file_change_is_exact(
        repo, ".sourcepackignore", DEFAULT_SOURCEPACKIGNORE
    ):
        return False
    if not _bootstrap_file_change_is_exact(
        repo, "sourcepack.config.json", DEFAULT_SOURCEPACK_CONFIG
    ):
        return False
    return True


def _only_sourcepack_gitignore_change(repo: str | Path) -> bool:
    return _only_sourcepack_bootstrap_changes(
        repo
    ) and _gitignore_change_is_exact_sourcepack_addition(repo)


def scanner_config_hash() -> str:
    from .packet import scanner_config_hash as packet_scanner_config_hash

    return packet_scanner_config_hash()


def git_metadata(repo: str | Path) -> dict:
    metadata = canonical_git_metadata(repo)
    dirty, dirty_state = _git_worktree_dirty(repo)
    metadata["dirty"] = dirty if dirty_state is None else None
    metadata["dirty_state"] = dirty_state
    return metadata


DIRTY_BASELINE_REFUSAL = "SourcePack refused to create a trusted baseline from a dirty working tree. Review, commit, or stash current changes first, or rerun with --force only if this state should become trusted."


def build_current_baseline(
    repo: str | Path,
    quiet: bool = False,
    fail_stage: str | None = None,
    force: bool = False,
) -> tuple[dict, bool]:
    repo = Path(repo).resolve()
    _, gitignore_error = ensure_gitignore_entry(repo)
    if gitignore_error:
        raise RuntimeError(f"Cannot configure SourcePack ignore entry: {gitignore_error}")
    dirty, dirty_state = _git_worktree_dirty(repo)
    if dirty_state in {"git_unavailable", "git_timeout", "git_error"}:
        raise RuntimeError(
            f"SourcePack refused to create a trusted baseline because git status could not be verified: {dirty_state}"
        )
    if dirty and not force and not _only_sourcepack_bootstrap_changes(repo):
        raise RuntimeError(DIRTY_BASELINE_REFUSAL)
    paths = ensure_sourcepack_dirs(repo)
    previous = validate_baseline(repo)
    created = previous.get("state") == "missing"
    lock = fd = None
    build_dir = None
    try:
        lock, fd = acquire_baseline_lock(repo, "baseline")
        build_id = _unique_build_id()
        build_dir = paths["builds"] / build_id
        packet = build_dir / "packet"
        build_dir.mkdir(parents=True, exist_ok=False)
        _write_baseline_packet(repo, packet)
        if not quiet and not _verify_baseline_packet(packet):
            raise RuntimeError("packet verification returned FAIL")
        candidate = _validate_packet_artifacts(repo, packet)
        if candidate:
            raise RuntimeError(
                candidate["details"].get("reason", "candidate baseline invalid")
            )
        meta = {
            "created_at": utc_now(),
            "packet_path": _rel_to_repo(repo, packet),
            "scanner_config_hash": scanner_config_hash(),
            **git_metadata(repo),
        }
        (build_dir / "metadata.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        _, meta_err = _read_json_file(build_dir / "metadata.json")
        if meta_err:
            raise RuntimeError(f"metadata.json {meta_err}")
        if fail_stage == "before_pointer_replace":
            raise RuntimeError("injected failure before pointer replacement")
        dirty_before_activate, dirty_state_before_activate = _git_worktree_dirty(repo)
        if dirty_state_before_activate in {
            "git_unavailable",
            "git_timeout",
            "git_error",
        }:
            raise RuntimeError(
                f"SourcePack refused to activate trusted baseline because git status could not be verified: {dirty_state_before_activate}"
            )
        if (
            dirty_before_activate
            and not force
            and not _only_sourcepack_bootstrap_changes(repo)
        ):
            raise RuntimeError(DIRTY_BASELINE_REFUSAL)
        pointer = {
            "schema_version": "baseline_pointer.v1",
            "active_build_id": build_id,
            "activated_at": utc_now(),
            "packet_path": _rel_to_repo(repo, packet),
            "metadata_path": _rel_to_repo(repo, build_dir / "metadata.json"),
        }
        _write_json_atomic(paths["active_pointer"], pointer)
        if fail_stage == "after_pointer_replace":
            raise RuntimeError("injected failure after pointer replacement")
        if paths["stale_marker"].exists():
            paths["stale_marker"].unlink()
        return paths, created
    except Exception:
        if build_dir is not None:
            active = None
            try:
                if paths["active_pointer"].exists():
                    active = json.loads(
                        paths["active_pointer"].read_text(encoding="utf-8")
                    ).get("active_build_id")
            except Exception:
                active = None
            if active != build_dir.name:
                shutil.rmtree(build_dir, ignore_errors=True)
        raise
    finally:
        if lock is not None and fd is not None:
            release_baseline_lock(lock, fd)


def baseline_report_fields(status: dict) -> dict:
    return {
        "baseline_state": status.get("state"),
        "baseline_integrity_ok": bool(status.get("ok"))
        and status.get("state") in {"present", "stale"},
        "baseline_integrity_finding_id": status.get("finding_id"),
        "baseline_integrity_message": status.get("message"),
        "baseline_stale": status.get("state") == "stale",
        "baseline_stale_details": (status.get("details") or {}).get("stale_details"),
        "baseline_mode": status.get("mode"),
        "baseline_packet_path": status.get("packet_path"),
        "baseline_metadata_path": status.get("metadata_path"),
        "baseline_active_pointer_path": status.get("active_pointer_path"),
    }
