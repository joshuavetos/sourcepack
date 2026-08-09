from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def canonical_allow_record(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sourcepack_home() -> Path:
    configured = os.environ.get("SOURCEPACK_HOME")
    return (Path(configured).expanduser() if configured else Path.home() / ".sourcepack").resolve()


def active_allows_path(repo: str | Path | None = None) -> Path:
    home = sourcepack_home()
    if repo is not None:
        repository_path = Path(repo).resolve()
        if home == repository_path or home.is_relative_to(repository_path):
            raise ValueError("SOURCEPACK_HOME must be outside the repository")
    return home / "trust" / "active_allows.jsonl"


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


def _jsonl_bytes(records: list[dict]) -> bytes:
    return b"".join(canonical_allow_record(record).encode("utf-8") + b"\n" for record in records)


def active_allow_records(repo: str | Path) -> list[dict]:
    repository_path = str(Path(repo).resolve())
    records = _read_jsonl(active_allows_path(repo))
    required = {"repository_path", "id", "scope", "value", "reason", "created_at", "expires_at", "high_risk"}
    for record in records:
        if not required.issubset(record):
            raise ValueError("active allow record is missing required fields")
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
    repository_path = str(Path(repo).resolve())
    authority_path = active_allows_path(repo)
    authority_records = _read_jsonl(authority_path)
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
    repository_path = str(Path(repo).resolve())
    authority_path = active_allows_path(repo)
    authority_records = _read_jsonl(authority_path)
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
        _atomic_write(path, _jsonl_bytes([record for record in readable if record.get("id") not in removed_ids]))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        _atomic_write(authority_path, authority_original, private=True)
        raise
    return [{key: value for key, value in record.items() if key != "repository_path"} for record in removed]
