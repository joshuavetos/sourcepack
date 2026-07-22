from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any

FINDING_IDENTITY_SCHEMA_VERSION = "sourcepack.finding_identity.v1"


_CANONICAL_PROVENANCE_BY_REASON = {
    "declared_dependency": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "proposed_state",
        "trust_status": "untrusted_until_accepted",
        "modified_by_patch": True,
        "source_kind": "dependency_manifest",
    },
    "declared_command": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "proposed_state",
        "trust_status": "untrusted_until_accepted",
        "modified_by_patch": True,
        "source_kind": "command_manifest",
    },
    "dependency_scope_review": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "dependency_manifest",
        "trust_status": "trusted_preexisting",
        "modified_by_patch": False,
        "source_kind": "dependency_manifest",
    },
    "unsupported_dependency": {
        "analysis_status": "UNSUPPORTED",
        "evidence_class": "analysis_state",
        "trust_status": "no_supporting_evidence",
        "modified_by_patch": False,
        "source_kind": "dependency_resolution",
    },
    "unsupported_command": {
        "analysis_status": "UNSUPPORTED",
        "evidence_class": "analysis_state",
        "trust_status": "no_supporting_evidence",
        "modified_by_patch": False,
        "source_kind": "command_resolution",
    },
    "command_manifest_missing": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "analysis_state",
        "trust_status": "missing",
        "modified_by_patch": False,
        "source_kind": "command_manifest",
    },
    "command_check_inconclusive": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "analysis_state",
        "trust_status": "inconclusive",
        "modified_by_patch": False,
        "source_kind": "command_resolution",
    },
    "command_manifest_uncertain": {
        "analysis_status": "UNKNOWN",
        "evidence_class": "analysis_state",
        "trust_status": "inconclusive",
        "modified_by_patch": False,
        "source_kind": "command_manifest",
    },
    "manifest_parse_failure": {
        "analysis_status": "UNREVIEWABLE",
        "evidence_class": "analysis_state",
        "trust_status": "invalid",
        "modified_by_patch": False,
        "source_kind": "manifest_parse",
    },
}


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
        parts.append(part)
    return "/".join(parts) or None


def _restore_canonical_provenance(finding: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(finding)
    reason_code = (_text(enriched.get("id")) or "").lower()
    defaults = _CANONICAL_PROVENANCE_BY_REASON.get(reason_code)
    if defaults:
        for field, value in defaults.items():
            enriched.setdefault(field, value)
        if enriched.get("source_path") is None:
            if reason_code in {"declared_command", "command_manifest_missing", "command_manifest_uncertain", "manifest_parse_failure"}:
                enriched["source_path"] = "package.json"
            elif reason_code in {"declared_dependency", "dependency_scope_review"}:
                enriched["source_path"] = enriched.get("path") or "dependency manifest"
    return enriched


def finding_identity_payload(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> dict[str, Any]:
    category = (_text(finding.get("category")) or "finding").lower()
    reason_code = (_text(finding.get("id")) or "unknown").lower()
    path = _normalize_path(_text(finding.get("path")))
    evidence = _text(finding.get("evidence")) or _text(finding.get("missing_evidence"))
    command = None
    dependency = None
    policy = finding.get("policy") if isinstance(finding.get("policy"), dict) else {}
    if category == "command" or reason_code.endswith("command"):
        command = evidence.lower() if evidence else None
    if category == "dependency" or "dependency" in reason_code:
        dependency = evidence.lower() if evidence else None
    payload = {
        "schema_version": FINDING_IDENTITY_SCHEMA_VERSION,
        "report_schema_version": report_schema_version,
        "category": category,
        "reason_code": reason_code,
        "path": path,
        "dependency": dependency,
        "command": command,
    }
    if policy:
        payload.update({
            "policy_rule": policy.get("rule_name"),
            "policy_rule_fingerprint": policy.get("rule_fingerprint"),
            "policy_scope": policy.get("scope"),
        })
    return payload


def finding_id_for(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> str:
    payload = finding_identity_payload(finding, report_schema_version=report_schema_version)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "spkf_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def attach_finding_id(finding: dict[str, Any], *, report_schema_version: str = "traffic_report.v1") -> dict[str, Any]:
    enriched = _restore_canonical_provenance(finding)
    enriched.setdefault("finding_id", finding_id_for(enriched, report_schema_version=report_schema_version))
    return enriched
