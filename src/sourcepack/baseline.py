from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_TIMEOUT, metadata as canonical_git_metadata, run_git
from .paths import ensure_sourcepack_dirs, sourcepack_paths

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"



def protected_baseline_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    return p.startswith(".sourcepack/baseline/")


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


def baseline_corrupt_result(repo: Path, message: str, details: dict | None = None, packet_path: Path | None = None, metadata_path: Path | None = None, active_pointer_path: Path | None = None, mode: str = "none", active_build_id: str | None = None) -> dict:
    return {"ok": False, "state": "corrupt", "finding_id": "baseline_corrupt", "message": "Trusted SourcePack baseline is corrupt or unverifiable. Recreate the baseline only after verifying the current repo state should be trusted.", "details": {"reason": message, **(details or {})}, "packet_path": _rel_to_repo(repo, packet_path), "metadata_path": _rel_to_repo(repo, metadata_path), "active_pointer_path": _rel_to_repo(repo, active_pointer_path), "mode": mode, "active_build_id": active_build_id}


def resolve_active_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); paths = sourcepack_paths(repo); pointer = paths["active_pointer"]
    if pointer.exists():
        data, err = _read_json_file(pointer)
        if err:
            return baseline_corrupt_result(repo, f"active.json {err}", active_pointer_path=pointer, mode="pointer")
        build_id = data.get("active_build_id")
        if not isinstance(build_id, str) or not build_id or "/" in build_id or "\\" in build_id or build_id in {".", ".."}:
            return baseline_corrupt_result(repo, "active.json has invalid active_build_id", active_pointer_path=pointer, mode="pointer")
        build_dir = (paths["builds"] / build_id).resolve(); builds_dir = paths["builds"].resolve()
        try:
            build_dir.relative_to(builds_dir)
        except ValueError:
            return baseline_corrupt_result(repo, "active.json points outside baseline builds", active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        packet = build_dir / "packet"; meta = build_dir / "metadata.json"
        if not build_dir.exists() or not packet.exists():
            return baseline_corrupt_result(repo, "active.json points to a missing build", packet_path=packet, metadata_path=meta, active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        return {"ok": True, "state": "resolved", "mode": "pointer", "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, meta), "active_pointer_path": _rel_to_repo(repo, pointer), "active_build_id": build_id, "details": {}}
    legacy = paths["packet"]
    if legacy.exists():
        legacy_artifacts = {"manifest.json", "receipt.json", "reality_map.json", "context.md", "ai_instructions.md"}
        present = {child.name for child in legacy.iterdir()} if legacy.is_dir() else set()
        if (legacy / "manifest.json").exists():
            return {"ok": True, "state": "resolved", "mode": "legacy", "packet_path": _rel_to_repo(repo, legacy), "metadata_path": _rel_to_repo(repo, paths["baseline_meta"]), "active_pointer_path": None, "active_build_id": None, "details": {}}
        if present & legacy_artifacts:
            return baseline_corrupt_result(repo, "legacy baseline packet has baseline artifacts but is missing manifest.json", packet_path=legacy, mode="legacy")
    return {"ok": False, "state": "missing", "finding_id": "baseline_missing", "message": "No trusted SourcePack baseline exists while changes are present.", "details": {}, "packet_path": None, "metadata_path": None, "active_pointer_path": None, "mode": "none", "active_build_id": None}


def _validate_packet_artifacts(repo: Path, packet: Path) -> dict | None:
    required = ["manifest.json", "receipt.json", "reality_map.json"]
    for name in required:
        if not (packet / name).exists():
            return baseline_corrupt_result(repo, f"active packet missing {name}", packet_path=packet)
    for name in ["manifest.json", "receipt.json", "reality_map.json", "token_report.json", "redactions.json"]:
        path = packet / name
        if path.exists():
            _, err = _read_json_file(path)
            if err:
                return baseline_corrupt_result(repo, f"{name} {err}", packet_path=packet)
    receipt, err = _read_json_file(packet / "receipt.json")
    if err:
        return baseline_corrupt_result(repo, f"receipt.json {err}", packet_path=packet)
    hashes = receipt.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return baseline_corrupt_result(repo, "receipt.json has no hashes", packet_path=packet)
    for name, expected in hashes.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            return baseline_corrupt_result(repo, "receipt.json contains invalid hash entry", packet_path=packet)
        if Path(name).is_absolute() or ".." in Path(name).parts:
            return baseline_corrupt_result(repo, "receipt.json tracks unsafe artifact path", packet_path=packet)
        packet_root = packet.resolve(); path = (packet / name).resolve()
        try:
            path.relative_to(packet_root)
        except ValueError:
            return baseline_corrupt_result(repo, "receipt.json tracks path outside packet", packet_path=packet)
        if not path.exists():
            return baseline_corrupt_result(repo, f"receipt-tracked artifact missing: {name}", packet_path=packet)
        try:
            actual = sha256_file(path)
        except OSError as exc:
            return baseline_corrupt_result(repo, f"receipt-tracked artifact unreadable: {name}: {exc}", packet_path=packet)
        if actual != expected:
            return baseline_corrupt_result(repo, f"receipt hash mismatch: {name}", packet_path=packet)
    return None


def validate_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); resolved = resolve_active_baseline(repo)
    if resolved.get("state") in {"corrupt", "missing"}:
        return resolved
    packet = repo / resolved["packet_path"] if resolved.get("packet_path") else None
    meta = repo / resolved["metadata_path"] if resolved.get("metadata_path") else None
    corrupt = _validate_packet_artifacts(repo, packet)
    if corrupt:
        corrupt.update({"mode": resolved.get("mode", "none"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "active_build_id": resolved.get("active_build_id")})
        return corrupt
    if meta and meta.exists():
        _, err = _read_json_file(meta)
        if err:
            return baseline_corrupt_result(repo, f"metadata.json {err}", packet_path=packet, metadata_path=meta, active_pointer_path=repo / resolved["active_pointer_path"] if resolved.get("active_pointer_path") else None, mode=resolved.get("mode", "none"), active_build_id=resolved.get("active_build_id"))
    paths = sourcepack_paths(repo); stale = paths["stale_marker"].exists(); stale_details = None
    if stale:
        stale_details, err = _read_json_file(paths["stale_marker"])
        if err:
            stale_details = {"reason": "unreadable"}
    return {"ok": True, "state": "stale" if stale else "present", "finding_id": "baseline_stale" if stale else None, "message": "Trusted SourcePack baseline may not match current repo state." if stale else "Trusted SourcePack baseline is present.", "details": {"stale_details": stale_details} if stale else {}, "packet_path": resolved.get("packet_path"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "mode": resolved.get("mode"), "active_build_id": resolved.get("active_build_id")}


def acquire_baseline_lock(repo: str | Path, command: str | None = None) -> tuple[Path, int]:
    paths = ensure_sourcepack_dirs(repo); lock = paths["baseline_lock"]
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BaselineLockError("Another SourcePack baseline operation is already in progress.") from exc
    os.write(fd, json.dumps({"pid": os.getpid(), "command": command, "started_at": utc_now()}).encode("utf-8")); os.fsync(fd)
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
        json.dump(payload, f, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def _unique_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"


def _write_baseline_packet(repo: Path, packet: Path) -> None:
    from .packet import PacketWriter, SourceScanner

    PacketWriter(packet, SourceScanner(repo).scan(), force=True).write_all()


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
    protected = [line for line in lines if protected_baseline_path(line[3:] if len(line) > 3 else line)]
    non_baseline = [line for line in lines if line not in protected]
    if non_baseline:
        return True, None
    if protected:
        return False, "baseline_only_dirty"
    return False, None


def _only_sourcepack_gitignore_change(repo: str | Path) -> bool:
    repo = Path(repo)
    status = _run_git(repo, ["status", "--porcelain", "--", ".gitignore"])
    others = _run_git(repo, ["status", "--porcelain"])
    if status.returncode != 0 or others.returncode != 0:
        return False
    lines = [line for line in others.stdout.splitlines() if line.strip()]
    if not lines or any(not line.endswith(".gitignore") for line in lines):
        return False
    try:
        text = (repo / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return False
    tracked = _run_git(repo, ["show", "HEAD:.gitignore"])
    before = tracked.stdout if tracked.returncode == 0 else ""
    added = [line.strip() for line in text.splitlines() if line.strip() and line.strip() not in {line.strip() for line in before.splitlines()}]
    return bool(added) and set(added) <= {".sourcepack", ".sourcepack/"}


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


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None, force: bool = False) -> tuple[dict, bool]:
    repo = Path(repo).resolve()
    dirty, dirty_state = _git_worktree_dirty(repo)
    if dirty_state in {"git_unavailable", "git_timeout", "git_error"}:
        raise RuntimeError(f"SourcePack refused to create a trusted baseline because git status could not be verified: {dirty_state}")
    if dirty and not force and not _only_sourcepack_gitignore_change(repo):
        raise RuntimeError(DIRTY_BASELINE_REFUSAL)
    paths = ensure_sourcepack_dirs(repo)
    previous = validate_baseline(repo); created = previous.get("state") == "missing"
    lock = fd = None; build_dir = None
    try:
        lock, fd = acquire_baseline_lock(repo, "baseline")
        build_id = _unique_build_id(); build_dir = paths["builds"] / build_id; packet = build_dir / "packet"
        build_dir.mkdir(parents=True, exist_ok=False)
        _write_baseline_packet(repo, packet)
        if not quiet and not _verify_baseline_packet(packet):
            raise RuntimeError("packet verification returned FAIL")
        candidate = _validate_packet_artifacts(repo, packet)
        if candidate:
            raise RuntimeError(candidate["details"].get("reason", "candidate baseline invalid"))
        meta = {"created_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "scanner_config_hash": scanner_config_hash(), **git_metadata(repo)}
        (build_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        _, meta_err = _read_json_file(build_dir / "metadata.json")
        if meta_err:
            raise RuntimeError(f"metadata.json {meta_err}")
        if fail_stage == "before_pointer_replace":
            raise RuntimeError("injected failure before pointer replacement")
        pointer = {"schema_version": "baseline_pointer.v1", "active_build_id": build_id, "activated_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, build_dir / "metadata.json")}
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
                    active = json.loads(paths["active_pointer"].read_text(encoding="utf-8")).get("active_build_id")
            except Exception:
                active = None
            if active != build_dir.name:
                shutil.rmtree(build_dir, ignore_errors=True)
        raise
    finally:
        if lock is not None and fd is not None:
            release_baseline_lock(lock, fd)


def baseline_report_fields(status: dict) -> dict:
    return {"baseline_state": status.get("state"), "baseline_integrity_ok": bool(status.get("ok")) and status.get("state") in {"present", "stale"}, "baseline_integrity_finding_id": status.get("finding_id"), "baseline_integrity_message": status.get("message"), "baseline_stale": status.get("state") == "stale", "baseline_stale_details": (status.get("details") or {}).get("stale_details"), "baseline_mode": status.get("mode"), "baseline_packet_path": status.get("packet_path"), "baseline_metadata_path": status.get("metadata_path"), "baseline_active_pointer_path": status.get("active_pointer_path")}
