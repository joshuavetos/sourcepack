from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sourcepack.decision_ledger import read_events, verify_artifact_hash


FLEET_SUMMARY_SCHEMA_VERSION = "sourcepack.fleet.summary.v1"

SUPPORTED_REPORT_SCHEMAS = {
    "patch_judgment_report.v1",
    "traffic_report.v1",
}

DEPENDENCY_REASON_CODES = {
    "declared_dependency",
    "dependency_manifest_uncertain",
    "dependency_scope_review",
    "policy_dependency_addition",
    "unsupported_dependency",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _json_report_candidates(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted(
        (candidate for candidate in path.rglob("*.json") if candidate.is_file()),
        key=lambda candidate: candidate.as_posix(),
    )


def _jsonl_ledger_candidates(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix == ".jsonl" else []
    if not path.exists():
        return []
    return sorted(
        (candidate for candidate in path.rglob("*.jsonl") if candidate.is_file()),
        key=lambda candidate: candidate.as_posix(),
    )


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_verdict(value: Any) -> str:
    verdict = _string_value(value)
    if verdict in {"PASS", "WARN", "FAIL"}:
        return verdict
    return "UNKNOWN"


def _finding_id(finding: dict[str, Any]) -> str | None:
    return _string_value(finding.get("id"))


def _finding_schema_key(schema_version: str, finding_id: str) -> tuple[str, str]:
    return schema_version, finding_id


def _finding_dependency_key(finding: dict[str, Any]) -> str | None:
    finding_id = _finding_id(finding) or ""
    category = _string_value(finding.get("category")) or ""
    evidence_class = _string_value(finding.get("evidence_class")) or ""

    dependency_shaped = (
        finding_id in DEPENDENCY_REASON_CODES
        or category == "dependency"
        or evidence_class == "dependency_manifest"
    )
    if not dependency_shaped:
        return None

    return _string_value(finding.get("evidence"))


def _finding_path_key(finding: dict[str, Any]) -> str | None:
    return _string_value(finding.get("path"))


def _counter_entries(counter: Counter[tuple[str, str]], *, value_key: str) -> list[dict[str, Any]]:
    entries = []
    for (schema_version, value), count in sorted(counter.items(), key=lambda item: (item[0][0], item[0][1])):
        entries.append(
            {
                "schema_version": schema_version,
                value_key: value,
                "count": count,
            }
        )
    return entries


@dataclass(frozen=True)
class LoadedReport:
    path: Path
    display_path: str
    data: dict[str, Any]


def _read_report(path: Path, root: Path) -> tuple[LoadedReport | None, dict[str, str] | None]:
    display_path = _display_path(path, root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, {"path": display_path, "error": f"unreadable: {exc}"}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, {"path": display_path, "error": f"malformed JSON: {exc}"}

    if not isinstance(data, dict):
        return None, {"path": display_path, "error": "JSON root is not an object"}

    return LoadedReport(path=path, display_path=display_path, data=data), None


def summarize_reports(input_path: str | Path) -> dict[str, Any]:
    root = Path(input_path).resolve()
    display_root = root if root.is_dir() else root.parent
    candidates = _json_report_candidates(root)

    unreadable_reports: list[dict[str, str]] = []
    unknown_schema_reports: list[dict[str, str]] = []
    accepted_reports: list[LoadedReport] = []

    schema_versions_seen: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter({"PASS": 0, "WARN": 0, "FAIL": 0, "UNKNOWN": 0})
    reason_code_counter: Counter[tuple[str, str]] = Counter()
    dependency_counter: Counter[tuple[str, str]] = Counter()
    path_counter: Counter[tuple[str, str]] = Counter()

    for candidate in candidates:
        loaded, unreadable = _read_report(candidate, display_root)
        if unreadable is not None:
            unreadable_reports.append(unreadable)
            continue

        assert loaded is not None

        schema_version = _string_value(loaded.data.get("schema_version"))
        if schema_version is None:
            unknown_schema_reports.append(
                {
                    "path": loaded.display_path,
                    "error": "missing schema_version",
                }
            )
            continue

        schema_versions_seen[schema_version] += 1

        if schema_version not in SUPPORTED_REPORT_SCHEMAS:
            unknown_schema_reports.append(
                {
                    "path": loaded.display_path,
                    "schema_version": schema_version,
                    "error": "unsupported schema_version",
                }
            )
            continue

        accepted_reports.append(loaded)
        verdict_counts[_safe_verdict(loaded.data.get("verdict"))] += 1

        findings = _list_of_dicts(loaded.data.get("findings"))
        for finding in findings:
            finding_id = _finding_id(finding)
            if finding_id:
                reason_code_counter[_finding_schema_key(schema_version, finding_id)] += 1

            dependency_key = _finding_dependency_key(finding)
            if dependency_key:
                dependency_counter[(schema_version, dependency_key)] += 1

            path_key = _finding_path_key(finding)
            if path_key:
                path_counter[(schema_version, path_key)] += 1

    return {
        "schema_version": FLEET_SUMMARY_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "input_path": str(root),
        "supported_report_schemas": sorted(SUPPORTED_REPORT_SCHEMAS),
        "coverage": {
            "json_files_seen": len(candidates),
            "accepted_reports": len(accepted_reports),
            "unreadable_reports": len(unreadable_reports),
            "unknown_schema_reports": len(unknown_schema_reports),
        },
        "accepted_report_paths": [report.display_path for report in accepted_reports],
        "unreadable_reports": unreadable_reports,
        "unknown_schema_reports": unknown_schema_reports,
        "schema_versions_seen": [
            {"schema_version": schema_version, "count": count}
            for schema_version, count in sorted(schema_versions_seen.items())
        ],
        "verdict_counts": dict(verdict_counts),
        "reason_code_counts": _counter_entries(reason_code_counter, value_key="reason_code"),
        "dependency_counts": _counter_entries(dependency_counter, value_key="dependency"),
        "path_counts": _counter_entries(path_counter, value_key="path"),
    }


def summarize_ledgers(input_path: str | Path) -> dict[str, Any]:
    root = Path(input_path).resolve()
    display_root = root if root.is_dir() else root.parent
    candidates = _jsonl_ledger_candidates(root)

    event_type_counter: Counter[str] = Counter()
    finding_hotspots: Counter[str] = Counter()
    broken_parent_ids: set[str] = set()
    artifact_status_counter: Counter[str] = Counter()
    malformed_lines = 0
    unsupported_schema_versions = 0
    invalid_events = 0
    accepted_events = 0
    ledger_paths: list[str] = []

    for candidate in candidates:
        ledger_paths.append(_display_path(candidate, display_root))
        result = read_events(candidate)
        malformed_lines += len(result.malformed_lines)
        unsupported_schema_versions += len(result.unsupported_schema_versions)
        invalid_events += len(result.invalid_events)
        accepted_events += len(result.events)

        ids = {event.get("event_id") for event in result.events}
        for event in result.events:
            event_type = _string_value(event.get("event_type")) or "unknown"
            event_type_counter[event_type] += 1
            parent = event.get("parent_event_id")
            if isinstance(parent, str) and parent and parent not in ids:
                broken_parent_ids.add(parent)
            artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
            if artifact.get("path") and artifact.get("sha256"):
                verification = verify_artifact_hash(event)
                artifact_status_counter["verified" if verification.get("verified") else str(verification.get("reason") or "mismatch")] += 1
            else:
                artifact_status_counter["not_provided"] += 1
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            finding_id = _string_value(data.get("finding_id"))
            if finding_id and event_type == "fail_detected":
                finding_hotspots[finding_id] += 1

    return {
        "schema_version": FLEET_SUMMARY_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "input_path": str(root),
        "input_model": "decision_ledgers",
        "coverage": {
            "jsonl_files_seen": len(candidates),
            "accepted_events": accepted_events,
            "malformed_lines": malformed_lines,
            "unsupported_schema_versions": unsupported_schema_versions,
            "invalid_events": invalid_events,
            "broken_parent_events": len(broken_parent_ids),
        },
        "accepted_ledger_paths": ledger_paths,
        "event_type_counts": [
            {"event_type": event_type, "count": count}
            for event_type, count in sorted(event_type_counter.items())
        ],
        "finding_hotspots": [
            {"finding_id": finding_id, "count": count}
            for finding_id, count in sorted(finding_hotspots.items(), key=lambda item: (-item[1], item[0]))
        ],
        "broken_parent_event_ids": sorted(broken_parent_ids),
        "artifact_verification_counts": [
            {"status": status, "count": count}
            for status, count in sorted(artifact_status_counter.items())
        ],
    }


def render_human_summary(summary: dict[str, Any]) -> str:
    if summary.get("input_model") == "decision_ledgers":
        coverage = summary.get("coverage", {})
        lines = [
            "SourcePack fleet summary",
            "",
            f"Input: {summary.get('input_path')}",
            "Input model: decision ledgers",
            f"JSONL files seen: {coverage.get('jsonl_files_seen', 0)}",
            f"Accepted events: {coverage.get('accepted_events', 0)}",
            f"Malformed lines: {coverage.get('malformed_lines', 0)}",
            f"Unsupported-schema events: {coverage.get('unsupported_schema_versions', 0)}",
            f"Invalid events: {coverage.get('invalid_events', 0)}",
            f"Broken parent references: {coverage.get('broken_parent_events', 0)}",
            "",
            "Event types:",
        ]
        for item in summary.get("event_type_counts", []):
            lines.append(f"- {item['event_type']}: {item['count']}")
        if not summary.get("event_type_counts"):
            lines.append("- none")
        lines.append("")
        lines.append("Repeated finding hotspots:")
        for item in summary.get("finding_hotspots", []):
            lines.append(f"- {item['finding_id']}: {item['count']}")
        if not summary.get("finding_hotspots"):
            lines.append("- none")
        if summary.get("broken_parent_event_ids"):
            lines.extend(["", "Broken parent event IDs:"])
            lines.extend(f"- {event_id}" for event_id in summary["broken_parent_event_ids"])
        return "\n".join(lines) + "\n"

    coverage = summary.get("coverage", {})
    verdict_counts = summary.get("verdict_counts", {})

    lines = [
        "SourcePack fleet summary",
        "",
        f"Input: {summary.get('input_path')}",
        f"JSON files seen: {coverage.get('json_files_seen', 0)}",
        f"Accepted reports: {coverage.get('accepted_reports', 0)}",
        f"Unreadable reports: {coverage.get('unreadable_reports', 0)}",
        f"Unknown-schema reports: {coverage.get('unknown_schema_reports', 0)}",
        "",
        "Verdicts:",
        f"- PASS: {verdict_counts.get('PASS', 0)}",
        f"- WARN: {verdict_counts.get('WARN', 0)}",
        f"- FAIL: {verdict_counts.get('FAIL', 0)}",
        f"- UNKNOWN: {verdict_counts.get('UNKNOWN', 0)}",
        "",
        "Top reason codes:",
    ]

    reason_codes = sorted(
        summary.get("reason_code_counts", []),
        key=lambda item: (
            -int(item.get("count", 0)),
            str(item.get("schema_version", "")),
            str(item.get("reason_code", "")),
        ),
    )
    if reason_codes:
        for item in reason_codes[:10]:
            lines.append(f"- {item['schema_version']}::{item['reason_code']}: {item['count']}")
    else:
        lines.append("- none")

    dependencies = sorted(
        summary.get("dependency_counts", []),
        key=lambda item: (
            -int(item.get("count", 0)),
            str(item.get("schema_version", "")),
            str(item.get("dependency", "")),
        ),
    )
    if dependencies:
        lines.extend(["", "Top dependencies:"])
        for item in dependencies[:10]:
            lines.append(f"- {item['schema_version']}::{item['dependency']}: {item['count']}")

    paths = sorted(
        summary.get("path_counts", []),
        key=lambda item: (
            -int(item.get("count", 0)),
            str(item.get("schema_version", "")),
            str(item.get("path", "")),
        ),
    )
    if paths:
        lines.extend(["", "Top paths:"])
        for item in paths[:10]:
            lines.append(f"- {item['schema_version']}::{item['path']}: {item['count']}")

    if summary.get("unreadable_reports"):
        lines.extend(["", "Unreadable reports:"])
        for item in summary["unreadable_reports"]:
            lines.append(f"- {item.get('path')}: {item.get('error')}")

    if summary.get("unknown_schema_reports"):
        lines.extend(["", "Unknown-schema reports:"])
        for item in summary["unknown_schema_reports"]:
            schema = item.get("schema_version")
            suffix = f" ({schema})" if schema else ""
            lines.append(f"- {item.get('path')}{suffix}: {item.get('error')}")

    return "\n".join(lines) + "\n"
