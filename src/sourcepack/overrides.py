from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sourcepack import __version__
from sourcepack.decision_ledger import append_event, artifact_for, filter_events, new_event, read_events

OVERRIDE_SCHEMA_VERSION = "sourcepack.override.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_target_finding(report: dict[str, Any], finding_id: str) -> dict[str, Any] | None:
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and finding.get("finding_id") == finding_id and finding.get("severity") == "error":
            return finding
    return None


def _verify_fail_event_link(ledger_path: str | Path, target_fail_event_id: str, target_finding_id: str) -> None:
    result = read_events(ledger_path)
    for event in filter_events(result.events, "fail_detected"):
        if event.get("event_id") != target_fail_event_id:
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if data.get("finding_id") != target_finding_id:
            raise ValueError("target_fail_event_id does not match target_finding_id")
        return
    raise ValueError("target_fail_event_id was not found in the decision ledger")


def create_override(
    *,
    report: dict[str, Any],
    report_path: str | Path,
    target_finding_id: str,
    actor: str,
    reason: str,
    scope: str,
    target_fail_event_id: str | None = None,
    expires_at: str | None = None,
    ledger_path: str | Path | None = None,
    repo: str | Path = ".",
    command: str = "override",
) -> dict[str, Any]:
    if not reason or not reason.strip():
        raise ValueError("override reason is required")
    if not actor or not actor.strip():
        raise ValueError("override actor is required")
    target = find_target_finding(report, target_finding_id)
    if target is None:
        raise ValueError("override target finding_id must reference a real FAIL finding")
    if ledger_path is not None:
        if not target_fail_event_id:
            raise ValueError("target_fail_event_id is required when recording override to decision ledger")
        _verify_fail_event_link(ledger_path, target_fail_event_id, target_finding_id)
    override = {
        "schema_version": OVERRIDE_SCHEMA_VERSION,
        "override_id": "spko_" + uuid.uuid4().hex,
        "created_at": utc_now(),
        "sourcepack_version": __version__,
        "actor": actor,
        "reason": reason.strip(),
        "scope": scope,
        "expires_at": expires_at,
        "target_report": str(report_path),
        "target_finding_id": target_finding_id,
        "target_fail_event_id": target_fail_event_id,
        "original_verdict": report.get("verdict"),
        "original_reason_code": target.get("id"),
    }
    if ledger_path is not None:
        append_event(ledger_path, new_event("override_recorded", command=command, repo=repo, artifact=artifact_for(report_path, schema_version=report.get("schema_version")), parent_event_id=target_fail_event_id, data={"override": override, "finding_id": target_finding_id}))
    return override


def write_override(path: str | Path, override: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(override, indent=2, sort_keys=True), encoding="utf-8")


def override_applies(override: dict[str, Any], *, now: datetime | None = None) -> bool:
    if override.get("schema_version") != OVERRIDE_SCHEMA_VERSION:
        return False
    expires = _parse_time(override.get("expires_at"))
    if expires is None:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > current


def classify_fail_overrides(report: dict[str, Any], overrides: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, list[str]]:
    active = {ov.get("target_finding_id") for ov in overrides if override_applies(ov, now=now)}
    overridden: list[str] = []
    unoverridden: list[str] = []
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and finding.get("severity") == "error":
            fid = finding.get("finding_id")
            if fid in active:
                overridden.append(fid)
            else:
                unoverridden.append(fid)
    return {"overridden": overridden, "unoverridden": unoverridden}
