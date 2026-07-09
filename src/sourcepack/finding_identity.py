from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any

FINDING_IDENTITY_SCHEMA_VERSION = "sourcepack.finding_identity.v1"


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    text = value.replace("\\", "/")
    parts = []
    for part in PurePosixPath(text).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) or None


def _scope(finding: dict[str, Any]) -> str | None:
    for key in ("scope", "checked_status", "required_evidence_class"):
        value = _text(finding.get(key))
        if value:
            return value.lower()
    return None


def finding_identity_payload(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> dict[str, Any]:
    category = (_text(finding.get("category")) or "finding").lower()
    reason_code = (_text(finding.get("id")) or "unknown").lower()
    path = _normalize_path(_text(finding.get("path")))
    evidence = _text(finding.get("evidence")) or _text(finding.get("missing_evidence"))
    evidence_class = _text(finding.get("evidence_class"))
    command = None
    dependency = None
    if category == "command" or reason_code.endswith("command") or evidence_class == "command_manifest":
        command = evidence.lower() if evidence else None
    if category == "dependency" or "dependency" in reason_code or evidence_class == "dependency_manifest":
        dependency = evidence.lower() if evidence else None
    return {
        "schema_version": FINDING_IDENTITY_SCHEMA_VERSION,
        "report_schema_version": report_schema_version,
        "category": category,
        "reason_code": reason_code,
        "path": path,
        "dependency": dependency,
        "command": command,
        "evidence_source": evidence_class,
        "scope": _scope(finding),
    }


def finding_id_for(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> str:
    payload = finding_identity_payload(finding, report_schema_version=report_schema_version)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "spkf_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def attach_finding_id(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> dict[str, Any]:
    enriched = dict(finding)
    enriched.setdefault("finding_id", finding_id_for(enriched, report_schema_version=report_schema_version))
    return enriched
