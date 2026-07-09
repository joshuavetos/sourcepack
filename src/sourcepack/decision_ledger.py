from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sourcepack import __version__

DECISION_LEDGER_EVENT_SCHEMA_VERSION = "sourcepack.decision_ledger.event.v1"
SUPPORTED_SCHEMA_VERSIONS = {DECISION_LEDGER_EVENT_SCHEMA_VERSION}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def artifact_for(path: str | Path, *, schema_version: str | None = None) -> dict[str, Any]:
    artifact_path = Path(path)
    item: dict[str, Any] = {"path": str(artifact_path), "sha256": None, "schema_version": schema_version}
    if artifact_path.is_file():
        item["sha256"] = sha256_file(artifact_path)
    return item


def new_event(
    event_type: str,
    *,
    command: str,
    repo: str | Path,
    artifact: dict[str, Any] | None = None,
    parent_event_id: str | None = None,
    related_event_ids: Iterable[str] | None = None,
    data: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": DECISION_LEDGER_EVENT_SCHEMA_VERSION,
        "event_id": "spke_" + uuid.uuid4().hex,
        "event_type": event_type,
        "created_at": created_at or utc_now(),
        "sourcepack_version": __version__,
        "command": command,
        "repo": str(repo),
        "artifact": artifact or {"path": None, "sha256": None, "schema_version": None},
        "parent_event_id": parent_event_id,
        "related_event_ids": list(related_event_ids or []),
        "data": data or {},
    }


def append_event(path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


@dataclass(frozen=True)
class LedgerReadResult:
    events: list[dict[str, Any]]
    malformed_lines: list[dict[str, Any]]
    unsupported_schema_versions: list[dict[str, Any]]


def read_events(path: str | Path) -> LedgerReadResult:
    events: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    ledger_path = Path(path)
    if not ledger_path.exists():
        return LedgerReadResult(events, malformed, unsupported)
    for line_no, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed.append({"line": line_no, "error": str(exc), "raw": line})
            continue
        if not isinstance(data, dict):
            malformed.append({"line": line_no, "error": "JSONL event is not an object", "raw": line})
            continue
        schema = data.get("schema_version")
        if schema not in SUPPORTED_SCHEMA_VERSIONS:
            unsupported.append({"line": line_no, "schema_version": schema, "event": data})
            continue
        events.append(data)
    return LedgerReadResult(events, malformed, unsupported)


def filter_events(events: Iterable[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event_type") == event_type]


def follow_parent_chain(events: Iterable[dict[str, Any]], event_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {event.get("event_id"): event for event in events if isinstance(event.get("event_id"), str)}
    chain: list[dict[str, Any]] = []
    missing: list[str] = []
    current = by_id.get(event_id)
    seen: set[str] = set()
    while current is not None:
        chain.append(current)
        parent = current.get("parent_event_id")
        if not parent:
            break
        if parent in seen:
            missing.append(parent)
            break
        seen.add(parent)
        current = by_id.get(parent)
        if current is None:
            missing.append(parent)
    if not chain and event_id:
        missing.append(event_id)
    return chain, missing


def missing_parent_event_ids(events: Iterable[dict[str, Any]]) -> list[str]:
    event_list = list(events)
    ids = {event.get("event_id") for event in event_list}
    return sorted({event.get("parent_event_id") for event in event_list if event.get("parent_event_id") and event.get("parent_event_id") not in ids})


def verify_artifact_hash(event: dict[str, Any]) -> dict[str, Any]:
    artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
    path = artifact.get("path")
    expected = artifact.get("sha256")
    if not path or not expected:
        return {"verified": False, "reason": "artifact path or sha256 missing"}
    file_path = Path(path)
    if not file_path.is_file():
        return {"verified": False, "reason": "artifact missing"}
    actual = sha256_file(file_path)
    return {"verified": actual == expected, "expected_sha256": expected, "actual_sha256": actual}


def append_report_events(path: str | Path, *, report: dict[str, Any], report_path: str | Path, command: str, repo: str | Path) -> list[dict[str, Any]]:
    report_event = append_event(path, new_event("report_created", command=command, repo=repo, artifact=artifact_for(report_path, schema_version=report.get("schema_version")), data={"verdict": report.get("verdict")}))
    events = [report_event]
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and finding.get("severity") == "error":
            events.append(append_event(path, new_event("fail_detected", command=command, repo=repo, artifact=artifact_for(report_path, schema_version=report.get("schema_version")), parent_event_id=report_event["event_id"], data={"finding_id": finding.get("finding_id"), "reason_code": finding.get("id"), "finding": finding})))
    return events
