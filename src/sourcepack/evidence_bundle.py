from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sourcepack import __version__
from sourcepack.decision_ledger import read_events, sha256_file, validate_event
from sourcepack.overrides import OVERRIDE_SCHEMA_VERSION

BUNDLE_SCHEMA_VERSION = "sourcepack.evidence_bundle.v1"
VERIFY_SCHEMA_VERSION = "sourcepack.evidence_bundle.verify.v1"
SUPPORTED_REPORT_SCHEMAS = {"patch_judgment_report.v1", "traffic_report.v1"}
BUNDLE_ID_MATERIAL_FIELDS = (
    "schema_version",
    "sourcepack_version",
    "target_report",
    "events",
    "scanner_manifest",
    "artifacts",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object")
    return data


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _repo_relative_or_absolute(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except Exception:
        return str(path.resolve()).replace("\\", "/")


def _resolve_path(path: str, base: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _event_artifact_path(event: dict[str, Any]) -> str | None:
    artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
    path = artifact.get("path")
    return path if isinstance(path, str) and path else None


def _same_artifact(event: dict[str, Any], report_path: Path, report_sha: str) -> bool:
    artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
    if artifact.get("sha256") != report_sha:
        return False
    path = _event_artifact_path(event)
    if not path:
        return False
    repo = Path(str(event.get("repo") or "."))
    disk = Path(path) if Path(path).is_absolute() else repo / path
    try:
        return disk.resolve() == report_path.resolve()
    except Exception:
        return str(disk) == str(report_path)


def _artifact_matches_target(event: dict[str, Any], target: dict[str, Any], repo: Path) -> bool:
    artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
    if artifact.get("sha256") != target.get("sha256"):
        return False
    if artifact.get("schema_version") != target.get("schema_version"):
        return False
    path = artifact.get("path")
    target_path = target.get("path")
    if not isinstance(path, str) or not isinstance(target_path, str):
        return False
    event_disk = _resolve_path(path, repo)
    target_disk = _resolve_path(target_path, repo)
    try:
        return event_disk.resolve() == target_disk.resolve()
    except Exception:
        return str(event_disk) == str(target_disk)


def _finding_ids(report: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str):
            ids.add(finding["finding_id"])
    return ids


def _parent_chain(all_events: dict[str, dict[str, Any]], start: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    chain: list[dict[str, Any]] = []
    missing: list[str] = []
    seen: set[str] = set()
    current: dict[str, Any] | None = start
    while current is not None:
        event_id = current.get("event_id")
        if isinstance(event_id, str):
            if event_id in seen:
                missing.append(event_id)
                break
            seen.add(event_id)
        chain.append(current)
        parent = current.get("parent_event_id")
        if not parent:
            break
        if not isinstance(parent, str):
            missing.append(str(parent))
            break
        current = all_events.get(parent)
        if current is None:
            missing.append(parent)
            break
    return chain, missing


def _find_scanner_manifest(repo: Path) -> dict[str, Any] | None:
    active = repo / ".sourcepack" / "baseline" / "active.json"
    if active.is_file():
        try:
            active_data = _load_json(active)
        except Exception:
            return None
        packet = active_data.get("packet_path")
        if isinstance(packet, str) and packet:
            manifest = repo / packet / "manifest.json"
            if manifest.is_file():
                return {
                    "path": _repo_relative_or_absolute(manifest, repo),
                    "path_base": "repository",
                    "schema_version": "sourcepack.scanner_manifest.v1",
                    "sha256": sha256_file(manifest),
                }
    return None


def _artifact_refs(events: Iterable[dict[str, Any]], repo: Path) -> list[dict[str, Any]]:
    refs: dict[tuple[str, str | None], dict[str, Any]] = {}
    for event in events:
        artifact = event.get("artifact") if isinstance(event.get("artifact"), dict) else {}
        path = artifact.get("path")
        if not isinstance(path, str) or not path:
            continue
        normalized_path = _repo_relative_or_absolute(Path(path), repo) if Path(path).is_absolute() else path.replace("\\", "/")
        refs[(normalized_path, artifact.get("sha256"))] = {
            "path": normalized_path,
            "path_base": "repository",
            "schema_version": artifact.get("schema_version"),
            "sha256": artifact.get("sha256"),
        }
    return [refs[key] for key in sorted(refs)]



def _duplicate_event_ids(events: Iterable[dict[str, Any]]) -> list[str]:
    ids = [event.get("event_id") for event in events]
    return sorted(event_id for event_id, count in Counter(ids).items() if isinstance(event_id, str) and count > 1)


def _identity_path(value: str, repo: Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        return value.replace("\\", "/")
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except Exception:
        return "<absolute-path>"


def _identity_normalized(value: Any, repo: Path) -> Any:
    if isinstance(value, list):
        return [_identity_normalized(item, repo) for item in value]
    if not isinstance(value, dict):
        return value
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "repo" and isinstance(item, str):
            normalized[key] = "<repository>"
        elif key == "path" and isinstance(item, str):
            normalized[key] = _identity_path(item, repo)
        else:
            normalized[key] = _identity_normalized(item, repo)
    return normalized


def _bundle_id_material(bundle: dict[str, Any]) -> dict[str, Any]:
    repo_obj = bundle.get("repository") if isinstance(bundle.get("repository"), dict) else {}
    repo = Path(str(repo_obj.get("path") or "."))
    material = {field: bundle.get(field) for field in BUNDLE_ID_MATERIAL_FIELDS}
    ledger = bundle.get("decision_ledger") if isinstance(bundle.get("decision_ledger"), dict) else {}
    material["decision_ledger"] = {"sha256": ledger.get("sha256")}
    return _identity_normalized(material, repo)


def compute_bundle_id(bundle: dict[str, Any]) -> str:
    return "spkb_" + sha256_text(canonical_json(_bundle_id_material(bundle)))[:32]


def _creation_verification(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sourcepack.evidence_bundle.creation_verification.v1",
        "created_at": utc_now(),
        "status": result.get("status"),
        "reasons": result.get("reasons", []),
        "note": "Creation-time verification snapshot; run sourcepack bundle verify for current local artifact verification.",
    }


def create_bundle(
    report_path: str | Path,
    ledger_path: str | Path,
    *,
    output_path: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    report_file = Path(report_path)
    if not report_file.is_file():
        raise ValueError("target report is missing or unreadable")
    report = _load_json(report_file)
    schema = report.get("schema_version") or report.get("patch_judgment_schema_version")
    if schema not in SUPPORTED_REPORT_SCHEMAS:
        raise ValueError("unsupported report schema")
    report_sha = sha256_file(report_file)
    ledger_file = Path(ledger_path)
    result = read_events(ledger_file)
    if result.malformed_lines or result.unsupported_schema_versions or result.invalid_events:
        raise ValueError("decision ledger is malformed or unsupported")
    events = result.events
    ids = [event.get("event_id") for event in events]
    duplicates = sorted(event_id for event_id, count in Counter(ids).items() if isinstance(event_id, str) and count > 1)
    if duplicates:
        raise ValueError("duplicate event IDs create ambiguity")
    report_events = [event for event in events if event.get("event_type") == "report_created" and _same_artifact(event, report_file, report_sha)]
    if not report_events:
        raise ValueError("corresponding report_created event is missing")
    if len(report_events) > 1:
        raise ValueError("corresponding report_created event is ambiguous")
    report_event = report_events[0]
    by_id = {event["event_id"]: event for event in events if isinstance(event.get("event_id"), str)}
    chain, missing = _parent_chain(by_id, report_event)
    if missing:
        raise ValueError("required parent events are missing")
    fail_events = [event for event in events if event.get("event_type") == "fail_detected" and _same_artifact(event, report_file, report_sha)]
    included_finding_ids = {event.get("data", {}).get("finding_id") for event in fail_events if isinstance(event.get("data"), dict)}
    fail_event_ids = {event.get("event_id") for event in fail_events}
    report_finding_ids = _finding_ids(report)
    override_events = []
    unresolved_overrides: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "override_recorded":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        override = data.get("override") if isinstance(data.get("override"), dict) else None
        finding_id = data.get("finding_id") or (override or {}).get("target_finding_id")
        target = (override or {}).get("target_fail_event_id") or event.get("parent_event_id")
        claims_target_report = _same_artifact(event, report_file, report_sha) or finding_id in report_finding_ids or target in fail_event_ids
        if finding_id in included_finding_ids and target in fail_event_ids:
            override_events.append(event)
        elif claims_target_report:
            unresolved_overrides.append({"event_id": event.get("event_id"), "finding_id": finding_id, "target_fail_event_id": target})
    if unresolved_overrides:
        raise ValueError("override relationship is unresolved for the target report")
    repo = Path(str(report_event.get("repo") or report_file.parent)).resolve()
    report_ref = _repo_relative_or_absolute(report_file, repo)
    ledger_ref = _repo_relative_or_absolute(ledger_file, repo)
    scanner_manifest = _find_scanner_manifest(repo)
    included_events = sorted(
        {event["event_id"]: event for event in (chain + fail_events + override_events) if isinstance(event.get("event_id"), str)}.values(),
        key=lambda event: event["event_id"],
    )
    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "sourcepack_version": __version__,
        "repository": {"path": str(repo), "path_base": "absolute_local_path"},
        "target_report": {"path": report_ref, "path_base": "repository", "schema_version": schema, "sha256": report_sha},
        "decision_ledger": {"path": ledger_ref, "path_base": "repository", "sha256": sha256_file(ledger_file)},
        "events": {
            "report_created": report_event,
            "parent_chain": chain[1:],
            "fail_detected": sorted(fail_events, key=lambda event: event["event_id"]),
            "overrides": sorted(override_events, key=lambda event: event["event_id"]),
            "missing_parent_event_ids": missing,
            "unresolved_override_events": unresolved_overrides,
        },
        "scanner_manifest": scanner_manifest,
        "artifacts": _artifact_refs(included_events, repo),
        "created_at": created_at or utc_now(),
    }
    manifest["bundle_id"] = compute_bundle_id(manifest)
    creation_result = verify_bundle_dict(manifest)
    manifest["creation_verification"] = _creation_verification(creation_result)
    out = Path(output_path) if output_path else report_file.with_suffix(".bundle.json")
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _verify_result(status: str, reasons: list[str], failures: list[str], **extra: Any) -> dict[str, Any]:
    return {"schema_version": VERIFY_SCHEMA_VERSION, "status": status, "reasons": sorted(set(reasons)), "failures": failures, **extra}


def verify_bundle(path: str | Path) -> dict[str, Any]:
    try:
        bundle = _load_json(Path(path))
    except Exception as exc:
        return _verify_result("FAIL", ["malformed_bundle"], [str(exc)])
    return verify_bundle_dict(bundle)



def _event_ids(events: Iterable[dict[str, Any]]) -> list[str]:
    return [event["event_id"] for event in events if isinstance(event.get("event_id"), str)]


def _relevant_overrides(
    events: Iterable[dict[str, Any]],
    *,
    target: dict[str, Any],
    repo: Path,
    fail_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fail_ids = {event.get("event_id") for event in fail_events}
    finding_ids = {event.get("data", {}).get("finding_id") for event in fail_events if isinstance(event.get("data"), dict)}
    relevant: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "override_recorded":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        override = data.get("override") if isinstance(data.get("override"), dict) else None
        finding_id = data.get("finding_id") or (override or {}).get("target_finding_id")
        target_fail_event_id = (override or {}).get("target_fail_event_id") or event.get("parent_event_id")
        claims_target = _artifact_matches_target(event, target, repo) or finding_id in finding_ids or target_fail_event_id in fail_ids
        if finding_id in finding_ids and target_fail_event_id in fail_ids:
            relevant.append(event)
        elif claims_target:
            unresolved.append(event)
    return relevant, unresolved


def _compare_expected_ids(
    *,
    reasons: list[str],
    expected_ids: list[str],
    embedded_ids: list[str],
    missing_reason: str,
    unexpected_reason: str,
) -> None:
    expected = set(expected_ids)
    embedded = set(embedded_ids)
    if expected - embedded:
        reasons.append(missing_reason)
    if embedded - expected:
        reasons.append(unexpected_reason)

def verify_bundle_dict(bundle: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    failures: list[str] = []
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        reasons.append("unsupported_bundle_schema")
    required = ("schema_version", "bundle_id", "created_at", "repository", "target_report", "decision_ledger", "events", "artifacts")
    for field in required:
        if field not in bundle:
            reasons.append("missing_required_field")
            failures.append(field)
    if bundle.get("bundle_id") != compute_bundle_id(bundle):
        reasons.append("bundle_id_mismatch")
    repo_obj = bundle.get("repository") if isinstance(bundle.get("repository"), dict) else {}
    repo = Path(str(repo_obj.get("path") or "."))
    target = bundle.get("target_report") if isinstance(bundle.get("target_report"), dict) else {}
    report_path = target.get("path")
    report_disk: Path | None = None
    if not report_path:
        reasons.append("target_report_missing")
    else:
        report_disk = _resolve_path(str(report_path), repo)
        if not report_disk.is_file():
            reasons.append("target_report_missing")
        elif target.get("sha256") != sha256_file(report_disk):
            reasons.append("target_report_hash_mismatch")
    if target.get("schema_version") not in SUPPORTED_REPORT_SCHEMAS:
        reasons.append("unsupported_report_schema")
    ledger = bundle.get("decision_ledger") if isinstance(bundle.get("decision_ledger"), dict) else {}
    ledger_path = ledger.get("path")
    ledger_events_by_id: dict[str, dict[str, Any]] = {}
    if not ledger_path or not ledger.get("sha256"):
        reasons.append("decision_ledger_reference_invalid")
    else:
        ledger_disk = _resolve_path(str(ledger_path), repo)
        if not ledger_disk.is_file():
            reasons.append("decision_ledger_missing")
        elif ledger.get("sha256") != sha256_file(ledger_disk):
            reasons.append("decision_ledger_hash_mismatch")
        else:
            ledger_result = read_events(ledger_disk)
            if ledger_result.malformed_lines or ledger_result.unsupported_schema_versions or ledger_result.invalid_events:
                reasons.append("ledger_invalid")
            ledger_ids = [event.get("event_id") for event in ledger_result.events]
            if any(count > 1 for event_id, count in Counter(ledger_ids).items() if isinstance(event_id, str)):
                reasons.append("ledger_event_duplicate")
            else:
                ledger_events_by_id = {event["event_id"]: event for event in ledger_result.events if isinstance(event.get("event_id"), str)}
    events_obj = bundle.get("events") if isinstance(bundle.get("events"), dict) else {}
    report_event = events_obj.get("report_created")
    event_lists: list[dict[str, Any]] = []
    if report_event is None:
        reasons.append("report_created_missing")
    elif not isinstance(report_event, dict):
        reasons.append("invalid_event")
    else:
        event_lists.append(report_event)
        if report_event.get("event_type") != "report_created":
            reasons.append("report_created_invalid")
        if not _artifact_matches_target(report_event, target, repo):
            reasons.append("report_created_artifact_mismatch")
    for key in ("parent_chain", "fail_detected", "overrides"):
        value = events_obj.get(key)
        if not isinstance(value, list):
            reasons.append("missing_required_field")
            failures.append(f"events.{key}")
            value = []
        event_lists.extend([event for event in value if isinstance(event, dict)])
    chain = events_obj.get("parent_chain") if isinstance(events_obj.get("parent_chain"), list) else []
    if isinstance(report_event, dict):
        parent = report_event.get("parent_event_id")
        chain_ids = [event.get("event_id") for event in chain if isinstance(event, dict)]
        if parent and (not chain_ids or chain_ids[0] != parent):
            reasons.append("report_created_chain_mismatch")
        if not parent and chain_ids:
            reasons.append("report_created_chain_mismatch")
    duplicate_ids = _duplicate_event_ids(event_lists)
    if duplicate_ids:
        reasons.append("duplicate_event_id")
    by_id = {event.get("event_id"): event for event in event_lists if isinstance(event.get("event_id"), str)}
    compared_ids: set[str] = set()
    for event in event_lists:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id in compared_ids:
            continue
        compared_ids.add(event_id)
        ledger_event = ledger_events_by_id.get(event_id)
        if ledger_event is None:
            reasons.append("ledger_event_missing")
            continue
        if canonical_json(ledger_event) != canonical_json(event):
            reasons.append("ledger_event_mismatch")
    for event in event_lists:
        if validate_event(event):
            reasons.append("invalid_event")
            break
        parent = event.get("parent_event_id")
        if parent and parent not in by_id:
            reasons.append("missing_parent_event")
            break
    for event in [event for event in event_lists if event.get("event_type") == "fail_detected"]:
        if not _artifact_matches_target(event, target, repo):
            reasons.append("fail_event_artifact_mismatch")
            break
    fail_ids = {event.get("event_id") for event in event_lists if event.get("event_type") == "fail_detected"}
    finding_ids = {event.get("data", {}).get("finding_id") for event in event_lists if event.get("event_type") == "fail_detected" and isinstance(event.get("data"), dict)}
    for event in [event for event in event_lists if event.get("event_type") == "override_recorded"]:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        override = data.get("override") if isinstance(data.get("override"), dict) else {}
        if override and override.get("schema_version") != OVERRIDE_SCHEMA_VERSION:
            reasons.append("invalid_override")
        if (data.get("finding_id") or override.get("target_finding_id")) not in finding_ids:
            reasons.append("override_target_missing")
        if (override.get("target_fail_event_id") or event.get("parent_event_id")) not in fail_ids:
            reasons.append("override_fail_event_missing")
    if events_obj.get("unresolved_override_events"):
        reasons.append("unresolved_override_event")
    scanner = bundle.get("scanner_manifest")
    if isinstance(scanner, dict):
        scanner_path = scanner.get("path")
        scanner_disk = _resolve_path(str(scanner_path), repo) if scanner_path else None
        if not scanner_path or scanner_disk is None or not scanner_disk.is_file():
            reasons.append("scanner_manifest_missing")
        elif scanner.get("sha256") != sha256_file(scanner_disk):
            reasons.append("scanner_manifest_hash_mismatch")
    artifacts = bundle.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                reasons.append("invalid_artifact")
                continue
            artifact_path = artifact.get("path")
            expected = artifact.get("sha256")
            path_base = artifact.get("path_base")
            if path_base not in {"repository", "absolute_local_path"}:
                reasons.append("artifact_path_base_unsupported")
                continue
            if expected and artifact_path:
                disk = _resolve_path(str(artifact_path), repo)
                if not disk.is_file() or sha256_file(disk) != expected:
                    reasons.append("artifact_hash_mismatch")
                    break
    else:
        reasons.append("missing_required_field")
        failures.append("artifacts")
    if ledger_events_by_id:
        ledger_events = list(ledger_events_by_id.values())
        matching_reports = [event for event in ledger_events if event.get("event_type") == "report_created" and _artifact_matches_target(event, target, repo)]
        if len(matching_reports) > 1:
            reasons.append("report_created_ambiguous")
        elif len(matching_reports) == 1:
            expected_report = matching_reports[0]
            if isinstance(report_event, dict) and report_event.get("event_id") != expected_report.get("event_id"):
                reasons.append("report_created_artifact_mismatch")
            expected_chain, expected_missing = _parent_chain(ledger_events_by_id, expected_report)
            expected_parent_chain = expected_chain[1:]
            embedded_chain = [event for event in chain if isinstance(event, dict)]
            expected_chain_ids = _event_ids(expected_parent_chain)
            embedded_chain_ids = _event_ids(embedded_chain)
            if expected_missing or any(event_id not in embedded_chain_ids for event_id in expected_chain_ids):
                reasons.append("parent_chain_incomplete")
            if embedded_chain_ids != expected_chain_ids:
                reasons.append("parent_chain_unexpected_event")
            expected_fail_events = sorted(
                [event for event in ledger_events if event.get("event_type") == "fail_detected" and _artifact_matches_target(event, target, repo)],
                key=lambda event: event.get("event_id") or "",
            )
            embedded_fail_events = [event for event in events_obj.get("fail_detected", []) if isinstance(event, dict)]
            _compare_expected_ids(
                reasons=reasons,
                expected_ids=_event_ids(expected_fail_events),
                embedded_ids=_event_ids(embedded_fail_events),
                missing_reason="fail_event_missing_from_bundle",
                unexpected_reason="unexpected_fail_event",
            )
            expected_override_events, unresolved_ledger_overrides = _relevant_overrides(
                ledger_events,
                target=target,
                repo=repo,
                fail_events=expected_fail_events,
            )
            embedded_override_events = [event for event in events_obj.get("overrides", []) if isinstance(event, dict)]
            _compare_expected_ids(
                reasons=reasons,
                expected_ids=_event_ids(expected_override_events),
                embedded_ids=_event_ids(embedded_override_events),
                missing_reason="override_event_missing_from_bundle",
                unexpected_reason="unexpected_override_event",
            )
            if unresolved_ledger_overrides:
                reasons.append("unresolved_override_event")
    status = "PASS" if not reasons else "FAIL"
    artifact_failure_reasons = {
        "target_report_missing",
        "target_report_hash_mismatch",
        "decision_ledger_reference_invalid",
        "decision_ledger_missing",
        "decision_ledger_hash_mismatch",
        "scanner_manifest_missing",
        "scanner_manifest_hash_mismatch",
        "invalid_artifact",
        "artifact_hash_mismatch",
        "artifact_path_base_unsupported",
    }
    chain_failure_reasons = {
        "invalid_event",
        "missing_parent_event",
        "duplicate_event_id",
        "report_created_missing",
        "report_created_invalid",
        "report_created_artifact_mismatch",
        "report_created_chain_mismatch",
        "fail_event_artifact_mismatch",
        "override_target_missing",
        "override_fail_event_missing",
        "unresolved_override_event",
        "ledger_invalid",
        "ledger_event_missing",
        "ledger_event_mismatch",
        "ledger_event_duplicate",
        "report_created_ambiguous",
        "parent_chain_incomplete",
        "parent_chain_unexpected_event",
        "fail_event_missing_from_bundle",
        "unexpected_fail_event",
        "override_event_missing_from_bundle",
        "unexpected_override_event",
    }
    return _verify_result(
        status,
        reasons,
        failures,
        event_counts={
            "report_created": 1 if isinstance(report_event, dict) else 0,
            "parent_chain": len(chain),
            "fail_detected": len(events_obj.get("fail_detected", []) or []),
            "overrides": len(events_obj.get("overrides", []) or []),
        },
        artifact_count=len(artifacts) if isinstance(artifacts, list) else 0,
        chain_integrity="PASS" if not any(reason in reasons for reason in chain_failure_reasons) else "FAIL",
        artifact_verification="PASS" if not any(reason in reasons for reason in artifact_failure_reasons) else "FAIL",
    )


def render_bundle_verify_human(bundle_or_result: dict[str, Any]) -> str:
    result = bundle_or_result.get("verification", bundle_or_result)
    lines = [
        "SourcePack evidence bundle verification",
        f"Status: {result.get('status')}",
        f"Bundle: {bundle_or_result.get('bundle_id', 'unknown')}",
        f"Chain integrity: {result.get('chain_integrity')}",
        f"Artifact verification: {result.get('artifact_verification')}",
        f"Artifacts: {result.get('artifact_count', 0)}",
    ]
    counts = result.get("event_counts", {}) if isinstance(result.get("event_counts"), dict) else {}
    lines.append(
        "Events: "
        f"report_created={counts.get('report_created', 0)} "
        f"parent_chain={counts.get('parent_chain', 0)} "
        f"fail_detected={counts.get('fail_detected', 0)} "
        f"overrides={counts.get('overrides', 0)}"
    )
    if result.get("reasons"):
        lines.append("Failures:")
        lines.extend(f"- {reason}" for reason in result.get("reasons", []))
    return "\n".join(lines) + "\n"
