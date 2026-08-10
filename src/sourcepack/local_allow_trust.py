from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


ACTIVE_ALLOW_LIMIT_BYTES = 1024 * 1024
ACTIVE_ALLOW_LINE_LIMIT_BYTES = 16 * 1024
ACTIVE_ALLOW_RECORD_LIMIT = 1000
_REQUIRED_ALLOW_FIELDS = {
    "repository_path", "id", "scope", "value", "reason", "created_at", "expires_at", "high_risk",
}

def canonical_allow_record(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sourcepack_home() -> Path:
    configured = os.environ.get("SOURCEPACK_HOME")
    return (Path(configured).expanduser() if configured else Path.home() / ".sourcepack").resolve()


def active_allows_path(repo: str | Path | None = None) -> Path:
    home = sourcepack_home()
    authority_path = (home / "trust" / "active_allows.jsonl").resolve()
    if repo is not None:
        repository_path = Path(repo).resolve()
        if authority_path == repository_path or authority_path.is_relative_to(repository_path):
            raise ValueError("active allow authority path must be outside the repository")
    return authority_path


def _atomic_write(path: Path, data: bytes, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        if private:
            os.chmod(temporary, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    records: list[dict] = []
    for line in lines:
        if not line:
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"record in {path} must be an object")
        records.append(record)
    return records


def _read_bounded_authority(path: Path) -> list[dict]:
    """Read the complete external authority ledger without following its final symlink."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return []
    try:
        before = os.fstat(fd)
        if before.st_size > ACTIVE_ALLOW_LIMIT_BYTES:
            raise ValueError("active allow ledger byte limit exceeded")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(ACTIVE_ALLOW_LIMIT_BYTES + 1)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if len(data) > ACTIVE_ALLOW_LIMIT_BYTES:
        raise ValueError("active allow ledger byte limit exceeded")
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
    ):
        raise ValueError("active allow ledger changed during acquisition")
    lines = data.splitlines()
    if len(lines) > ACTIVE_ALLOW_RECORD_LIMIT:
        raise ValueError("active allow ledger record limit exceeded")
    records: list[dict] = []
    for line in lines:
        if len(line) > ACTIVE_ALLOW_LINE_LIMIT_BYTES:
            raise ValueError("active allow ledger line limit exceeded")
        if not line:
            continue
        record = json.loads(line.decode("utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"record in {path} must be an object")
        records.append(record)
    return records


def _authority_records(repo: str | Path) -> tuple[str, Path, list[dict]]:
    repository_path = str(Path(repo).resolve())
    authority_path = active_allows_path(repo)
    records = _read_bounded_authority(authority_path)
    for record in records:
        # Repository isolation precedes repository-specific schema validation.
        if record.get("repository_path") != repository_path:
            continue
        if not _REQUIRED_ALLOW_FIELDS.issubset(record):
            raise ValueError("active allow record is missing required fields")
    return repository_path, authority_path, records


def _jsonl_bytes(records: list[dict]) -> bytes:
    return b"".join(canonical_allow_record(record).encode("utf-8") + b"\n" for record in records)


def active_allow_records(repo: str | Path) -> list[dict]:
    repository_path, _, records = _authority_records(repo)
    return [
        {key: value for key, value in record.items() if key != "repository_path"}
        for record in records
        if record["repository_path"] == repository_path
    ]


def readable_allow_file_matches_active(repo: str | Path, path: str | Path) -> bool:
    try:
        readable = _read_jsonl(Path(path))
        active = active_allow_records(repo)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return False
    return bool(readable) and readable == active


def add_active_allow(repo: str | Path, allow_path: str | Path, record: dict) -> None:
    repository_path, authority_path, authority_records = _authority_records(repo)
    authority_original = _jsonl_bytes(authority_records)
    authority_record = {"repository_path": repository_path, **record}
    if any(item.get("repository_path") == repository_path and item.get("id") == record.get("id") for item in authority_records):
        raise ValueError("active allow ID already exists for this repository")
    authority_records.append(authority_record)
    _atomic_write(authority_path, _jsonl_bytes(authority_records), private=True)

    path = Path(allow_path)
    try:
        readable_records = _read_jsonl(path)
        _atomic_write(path, _jsonl_bytes(readable_records + [record]))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        _atomic_write(authority_path, authority_original, private=True)
        raise


def remove_active_allows(
    repo: str | Path,
    allow_path: str | Path,
    *,
    scope: str | None = None,
    value: str | None = None,
    allow_id: str | None = None,
) -> list[dict]:
    repository_path, authority_path, authority_records = _authority_records(repo)
    authority_original = _jsonl_bytes(authority_records)

    def matches(record: dict) -> bool:
        if record.get("repository_path") != repository_path:
            return False
        if allow_id is not None:
            return record.get("id") == allow_id
        return record.get("scope") == scope and record.get("value") == value

    removed = [record for record in authority_records if matches(record)]
    if not removed:
        return []
    remaining = [record for record in authority_records if not matches(record)]
    _atomic_write(authority_path, _jsonl_bytes(remaining), private=True)

    path = Path(allow_path)
    try:
        readable = _read_jsonl(path)
        removed_ids = {record.get("id") for record in removed}
        readable_remaining = [record for record in readable if record.get("id") not in removed_ids]
        if readable_remaining:
            _atomic_write(path, _jsonl_bytes(readable_remaining))
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            try:
                path.parent.rmdir()
            except OSError:
                pass
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        _atomic_write(authority_path, authority_original, private=True)
        raise
    return [{key: value for key, value in record.items() if key != "repository_path"} for record in removed]
