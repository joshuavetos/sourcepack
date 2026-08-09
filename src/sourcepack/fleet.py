from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sourcepack.decision_ledger import read_events, verify_artifact_hash


FLEET_SUMMARY_SCHEMA_VERSION = "sourcepack.fleet.summary.v1"
FLEET_DIRECTORY_ENTRY_LIMIT = 10_000
FLEET_DEPTH_LIMIT = 64
FLEET_RECORD_LIMIT = 5_000
FLEET_EVENT_RETENTION_LIMIT = 5_000
FLEET_FILE_SIZE_LIMIT_BYTES = 4 * 1024 * 1024
FLEET_AGGREGATE_READ_LIMIT_BYTES = 64 * 1024 * 1024

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


@dataclass
class DiscoveryResult:
    paths: list[Path]
    consumed: int
    source_exhausted: bool
    total: int
    total_is_lower_bound: bool
    limit_reached: str | None = None
    error: str | None = None


def _discover(path: Path, suffix: str, *, max_entries: int, max_depth: int, max_records: int) -> DiscoveryResult:
    if path.is_symlink():
        return DiscoveryResult([], 0, True, 0, False, error="input path is a symlink")
    if path.is_file():
        paths = [path] if path.suffix == suffix else []
        return DiscoveryResult(paths, 1, True, len(paths), False)
    if not path.exists():
        return DiscoveryResult([], 0, True, 0, False)
    pending = [(path, 0)]
    found: list[Path] = []
    consumed = 0
    while pending:
        directory, depth = pending.pop(0)
        try:
            entries = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    if consumed == max_entries:
                        return DiscoveryResult(found, consumed, False, len(found), True, "directory_entries")
                    consumed += 1
                    entries.append(entry)
        except OSError as exc:
            return DiscoveryResult(found, consumed, False, len(found), True, error=f"directory traversal failed: {exc}")
        for entry in sorted(entries, key=lambda item: item.name):
            candidate = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if depth >= max_depth:
                        return DiscoveryResult(found, consumed, False, len(found), True, "nesting_depth")
                    pending.append((candidate, depth + 1))
                elif entry.is_file(follow_symlinks=False) and candidate.suffix == suffix:
                    if len(found) == max_records:
                        return DiscoveryResult(found, consumed, False, len(found), True, "artifact_paths")
                    found.append(candidate)
            except OSError as exc:
                return DiscoveryResult(found, consumed, False, len(found), True, error=f"entry metadata failed: {exc}")
        pending.sort(key=lambda item: item[0].as_posix())
    found.sort(key=lambda candidate: candidate.as_posix())
    return DiscoveryResult(found, consumed, True, len(found), False)


def _bounds(result: DiscoveryResult, *, max_entries: int, max_depth: int, max_records: int, bytes_read: int, max_file_bytes: int, max_read_bytes: int, read_limit_reached: str | None = None, read_error: str | None = None) -> dict[str, Any]:
    failed = result.error is not None or read_error is not None
    limit = result.limit_reached or read_limit_reached
    return {
        "status": "failed" if failed else ("incomplete" if limit else "complete"),
        "complete": not failed and limit is None and result.source_exhausted,
        "consumed": result.consumed,
        "retained": len(result.paths),
        "source_exhausted": result.source_exhausted and not failed and limit is None,
        "total": result.total,
        "total_is_lower_bound": result.total_is_lower_bound or failed or limit is not None,
        "configured_limits": {"directory_entries": max_entries, "nesting_depth": max_depth, "retained_records": max_records, "individual_file_bytes": max_file_bytes, "aggregate_read_bytes": max_read_bytes},
        "limit_reached": limit,
        "error": result.error or read_error,
        "bytes_read": bytes_read,
    }


def _ledger_producer_bounds(
    discovery: DiscoveryResult,
    *,
    max_entries: int,
    max_depth: int,
    max_artifact_paths: int,
    bytes_read: int,
    max_file_bytes: int,
    max_read_bytes: int,
    read_limit_reached: str | None,
    read_error: str | None,
    events_consumed: int,
    events_retained: int,
    event_retention_limit: int,
    event_limit_reached: bool,
) -> dict[str, Any]:
    acquisition_failed = discovery.error is not None or read_error is not None
    acquisition_limit = discovery.limit_reached or read_limit_reached
    discovery_exhausted = discovery.source_exhausted and discovery.limit_reached is None and discovery.error is None
    events_exhausted = discovery_exhausted and read_limit_reached is None and read_error is None and not event_limit_reached
    complete = not acquisition_failed and acquisition_limit is None and events_exhausted
    return {
        "status": "failed" if acquisition_failed else ("complete" if complete else "incomplete"),
        "complete": complete,
        "discovery": {
            "entries_consumed": discovery.consumed,
            "artifact_paths_retained": len(discovery.paths),
            "source_exhausted": discovery_exhausted,
            "artifact_total": discovery.total if not discovery.total_is_lower_bound else None,
            "artifact_total_lower_bound": discovery.total if discovery.total_is_lower_bound else None,
            "artifact_path_limit": max_artifact_paths,
            "limit_reached": discovery.limit_reached,
            "error": discovery.error,
            "configured_limits": {"directory_entries": max_entries, "nesting_depth": max_depth},
        },
        "reading": {
            "bytes_read": bytes_read,
            "configured_limits": {"individual_file_bytes": max_file_bytes, "aggregate_read_bytes": max_read_bytes},
            "limit_reached": read_limit_reached,
            "error": read_error,
        },
        "events": {
            "events_consumed": events_consumed,
            "events_retained": events_retained,
            "events_source_exhausted": events_exhausted,
            "event_total": events_consumed if events_exhausted else None,
            "event_total_lower_bound": None if events_exhausted else events_consumed,
            "event_retention_limit": event_retention_limit,
            "event_limit_reached": event_limit_reached,
        },
    }


def _is_execution_evidence_ledger(path: Path) -> bool:
    return path.parts[-3:] == (".sourcepack", "evidence", "ledger.jsonl")


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


def _read_report(path: Path, root: Path, *, max_bytes: int) -> tuple[LoadedReport | None, dict[str, str] | None, int]:
    display_path = _display_path(path, root)
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None, {"path": display_path, "error": "individual file byte limit reached"}, 0
        raw_bytes = path.read_bytes()
        if len(raw_bytes) > max_bytes:
            return None, {"path": display_path, "error": "individual file byte limit reached"}, 0
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, {"path": display_path, "error": f"malformed UTF-8: {exc}"}, 0
    except OSError as exc:
        return None, {"path": display_path, "error": f"unreadable: {exc}"}, 0

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, {"path": display_path, "error": f"malformed JSON: {exc}"}, len(raw_bytes)

    if not isinstance(data, dict):
        return None, {"path": display_path, "error": "JSON root is not an object"}, len(raw_bytes)

    return LoadedReport(path=path, display_path=display_path, data=data), None, len(raw_bytes)


def summarize_reports(input_path: str | Path, *, max_entries: int = FLEET_DIRECTORY_ENTRY_LIMIT, max_depth: int = FLEET_DEPTH_LIMIT, max_records: int = FLEET_RECORD_LIMIT, max_file_bytes: int = FLEET_FILE_SIZE_LIMIT_BYTES, max_read_bytes: int = FLEET_AGGREGATE_READ_LIMIT_BYTES) -> dict[str, Any]:
    requested = Path(input_path)
    root = requested.resolve()
    display_root = root if root.is_dir() else root.parent
    discovery = _discover(requested, ".json", max_entries=max_entries, max_depth=max_depth, max_records=max_records)
    candidates = discovery.paths
    bytes_read = 0
    read_limit = None
    read_error = None

    unreadable_reports: list[dict[str, str]] = []
    unknown_schema_reports: list[dict[str, str]] = []
    accepted_reports: list[LoadedReport] = []

    schema_versions_seen: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter({"PASS": 0, "WARN": 0, "FAIL": 0, "UNKNOWN": 0})
    reason_code_counter: Counter[tuple[str, str]] = Counter()
    dependency_counter: Counter[tuple[str, str]] = Counter()
    path_counter: Counter[tuple[str, str]] = Counter()

    for candidate in candidates:
        try:
            size = candidate.stat().st_size
        except OSError as exc:
            read_error = f"file metadata failed: {exc}"
            break
        if size > max_file_bytes:
            read_limit = "individual_file_bytes"
            break
        if bytes_read + min(size, max_file_bytes + 1) > max_read_bytes:
            read_limit = "aggregate_read_bytes"
            break
        loaded, unreadable, consumed_bytes = _read_report(candidate, display_root, max_bytes=max_file_bytes)
        bytes_read += consumed_bytes
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
        "input_model": "reports",
        "producer": _bounds(discovery, max_entries=max_entries, max_depth=max_depth, max_records=max_records, bytes_read=bytes_read, max_file_bytes=max_file_bytes, max_read_bytes=max_read_bytes, read_limit_reached=read_limit, read_error=read_error),
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


def summarize_ledgers(input_path: str | Path, *, max_entries: int = FLEET_DIRECTORY_ENTRY_LIMIT, max_depth: int = FLEET_DEPTH_LIMIT, max_records: int = FLEET_RECORD_LIMIT, max_events: int = FLEET_EVENT_RETENTION_LIMIT, max_file_bytes: int = FLEET_FILE_SIZE_LIMIT_BYTES, max_read_bytes: int = FLEET_AGGREGATE_READ_LIMIT_BYTES) -> dict[str, Any]:
    requested = Path(input_path)
    root = requested.resolve()
    display_root = root if root.is_dir() else root.parent
    discovery = _discover(requested, ".jsonl", max_entries=max_entries, max_depth=max_depth, max_records=max_records)
    if root.is_dir():
        discovery.paths = [candidate for candidate in discovery.paths if not _is_execution_evidence_ledger(candidate)]
        discovery.total = len(discovery.paths)
    candidates = discovery.paths
    bytes_read = 0
    read_limit = None
    read_error = None

    event_type_counter: Counter[str] = Counter()
    fail_finding_frequency: Counter[str] = Counter()
    artifact_status_counter: Counter[str] = Counter()
    malformed_lines = 0
    unsupported_schema_versions = 0
    invalid_events = 0
    accepted_events = 0
    ledger_paths: list[str] = []
    events: list[dict[str, Any]] = []
    events_consumed = 0
    event_limit_reached = False

    for candidate in candidates:
        try:
            size = candidate.stat().st_size
        except OSError as exc:
            read_error = f"file metadata failed: {exc}"
            break
        if size > max_file_bytes:
            read_limit = "individual_file_bytes"
            break
        if bytes_read + size > max_read_bytes:
            read_limit = "aggregate_read_bytes"
            break
        bytes_read += size
        ledger_paths.append(_display_path(candidate, display_root))
        try:
            result = read_events(candidate, max_events=max_events - len(events))
        except (OSError, UnicodeDecodeError) as exc:
            read_error = f"ledger read failed: {exc}"
            break
        malformed_lines += len(result.malformed_lines)
        unsupported_schema_versions += len(result.unsupported_schema_versions)
        invalid_events += len(result.invalid_events)
        events.extend(result.events)
        accepted_events += len(result.events)
        events_consumed += result.events_consumed
        if not result.events_source_exhausted:
            event_limit_reached = True
            break

    event_ids = {event.get("event_id") for event in events}
    missing_parent_ids: set[str] = set()
    broken_parent_references = 0
    for event in events:
        event_type = _string_value(event.get("event_type")) or "unknown"
        event_type_counter[event_type] += 1
        parent = event.get("parent_event_id")
        if isinstance(parent, str) and parent and parent not in event_ids:
            missing_parent_ids.add(parent)
            broken_parent_references += 1
        artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
        if artifact.get("path") and artifact.get("sha256"):
            verification = verify_artifact_hash(event)
            artifact_status_counter["verified" if verification.get("verified") else str(verification.get("reason") or "mismatch")] += 1
        else:
            artifact_status_counter["not_provided"] += 1
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        finding_id = _string_value(data.get("finding_id"))
        if finding_id and event_type == "fail_detected":
            fail_finding_frequency[finding_id] += 1

    return {
        "schema_version": FLEET_SUMMARY_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "input_path": str(root),
        "input_model": "decision_ledgers",
        "producer": _ledger_producer_bounds(discovery, max_entries=max_entries, max_depth=max_depth, max_artifact_paths=max_records, bytes_read=bytes_read, max_file_bytes=max_file_bytes, max_read_bytes=max_read_bytes, read_limit_reached=read_limit, read_error=read_error, events_consumed=events_consumed, events_retained=len(events), event_retention_limit=max_events, event_limit_reached=event_limit_reached),
        "coverage": {
            "jsonl_files_seen": len(candidates),
            "accepted_events": accepted_events,
            "malformed_lines": malformed_lines,
            "unsupported_schema_versions": unsupported_schema_versions,
            "invalid_events": invalid_events,
            "broken_parent_references": broken_parent_references,
            "unique_missing_parent_ids": len(missing_parent_ids),
        },
        "accepted_ledger_paths": ledger_paths,
        "event_type_counts": [
            {"event_type": event_type, "count": count}
            for event_type, count in sorted(event_type_counter.items())
        ],
        "fail_finding_frequencies": [
            {"finding_id": finding_id, "count": count}
            for finding_id, count in sorted(fail_finding_frequency.items(), key=lambda item: (-item[1], item[0]))
        ],
        "missing_parent_event_ids": sorted(missing_parent_ids),
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
            f"Broken parent references: {coverage.get('broken_parent_references', 0)}",
            f"Unique missing parent IDs: {coverage.get('unique_missing_parent_ids', 0)}",
            "",
            "Event types:",
        ]
        for item in summary.get("event_type_counts", []):
            lines.append(f"- {item['event_type']}: {item['count']}")
        if not summary.get("event_type_counts"):
            lines.append("- none")
        lines.append("")
        lines.append("FAIL finding frequencies:")
        for item in summary.get("fail_finding_frequencies", []):
            lines.append(f"- {item['finding_id']}: {item['count']}")
        if not summary.get("fail_finding_frequencies"):
            lines.append("- none")
        if summary.get("artifact_verification_counts"):
            lines.extend(["", "Artifact verification:"])
            for item in summary["artifact_verification_counts"]:
                lines.append(f"- {item['status']}: {item['count']}")
        if summary.get("missing_parent_event_ids"):
            lines.extend(["", "Missing parent event IDs:"])
            lines.extend(f"- {event_id}" for event_id in summary["missing_parent_event_ids"])
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
