from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .command_center_limits import MAX_SNAPSHOT_BYTES, clip_text

COMMAND_CENTER_ROUTE = "/api/command-center/v1/snapshot"


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _supported_report(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    report = snapshot["artifacts"]["report"]
    return report if isinstance(report, dict) and report.get("verdict") in {"PASS", "WARN", "FAIL"} else None


def _validate_snapshot_derivations(snapshot: dict[str, Any]) -> None:
    """Reject posture fields that disagree with their embedded artifacts."""
    posture = snapshot["posture"]
    artifacts = snapshot["artifacts"]
    baseline = artifacts["baseline"]
    policy = artifacts["policy"]
    status = artifacts["status"]
    report = artifacts["report"]

    status_data = status.get("status") if isinstance(status.get("status"), dict) else {}
    expected_artifact_fields = {
        "baseline_state": baseline.get("state"),
        "policy_resolution_status": policy.get("resolution_status"),
        "automatic_mode_enabled": bool(status_data.get("automatic_mode_enabled", False)),
    }
    for field, expected in expected_artifact_fields.items():
        if posture.get(field) != expected:
            raise ValueError(f"Command Center posture {field} does not match embedded artifacts")

    if report is None or (isinstance(report, dict) and report.get("verdict") not in {"PASS", "WARN", "FAIL"}):
        expected_report_fields = {
            "verdict": None,
            "finding_count": 0,
            "blocker_count": 0,
            "warning_count": 0,
        }
    else:
        totals = snapshot.get("bounds", {}).get("collections")
        if totals is not None:
            for key in ("findings", "blockers", "warnings", "evidence_items"):
                displayed = _list_count(report.get(key))
                metadata = totals[key]
                if displayed != metadata["displayed_count"] or metadata["omitted_count"] != metadata["total_count"] - displayed:
                    raise ValueError(f"Command Center bounded {key} metadata does not match canonical report")
        expected_report_fields = {
            "verdict": report.get("verdict"),
            "finding_count": totals["findings"]["total_count"] if totals else _list_count(report.get("findings")),
            "blocker_count": totals["blockers"]["total_count"] if totals else _list_count(report.get("blockers")),
            "warning_count": totals["warnings"]["total_count"] if totals else _list_count(report.get("warnings")),
        }
    for field, expected in expected_report_fields.items():
        if posture.get(field) != expected:
            raise ValueError(f"Command Center posture {field} does not match canonical report")


def _validate_report_error_derivations(snapshot: dict[str, Any]) -> None:
    """Reject report, report-error, and activity combinations that disagree."""
    artifacts = snapshot["artifacts"]
    report = artifacts["report"]
    report_error = artifacts["report_error"]
    activity = snapshot["activity"]
    terminal_error = activity[-1] if activity and activity[-1].get("type") == "error" else None

    if report is not None and report_error is not None:
        raise ValueError("Command Center cannot expose both a canonical report and report_error")

    if report_error is None:
        if terminal_error is not None:
            raise ValueError("Command Center terminal error activity requires report_error")
        return

    if report is not None:
        raise ValueError("Command Center report_error requires canonical report to be absent")
    if terminal_error is None:
        raise ValueError("Command Center report_error requires terminal error activity")

    error_data = report_error.get("error") if isinstance(report_error, dict) else None
    expected_message = error_data.get("message") if isinstance(error_data, dict) else None
    if not isinstance(expected_message, str) or not expected_message:
        expected_message = "Canonical report unavailable"
    expected_message = clip_text(expected_message)
    if terminal_error.get("message") != expected_message:
        raise ValueError("Command Center terminal error activity does not match report_error")


def _canonical_activity(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = snapshot["artifacts"]
    report = artifacts["report"]
    supported_report = _supported_report(snapshot)
    review_message = (
        f"Latest verdict: {supported_report['verdict']}"
        if supported_report is not None
        else "Latest report state: unsupported"
        if report is not None
        else "Latest verdict: unavailable"
    )
    activity = [
        {
            "type": "repository",
            "message": clip_text(f"Repository loaded at {snapshot['repository']['path']}"),
        },
        {
            "type": "baseline",
            "message": clip_text(f"Baseline state: {artifacts['baseline'].get('state', 'unknown')}"),
        },
        {
            "type": "policy",
            "message": clip_text(f"Policy resolution: {artifacts['policy'].get('resolution_status', 'unknown')}"),
        },
        {
            "type": "review",
            "message": review_message,
        },
    ]
    report_error = artifacts["report_error"]
    if report_error:
        error_data = report_error.get("error") if isinstance(report_error, dict) else None
        message = error_data.get("message") if isinstance(error_data, dict) else None
        activity.append(
            {
                "type": "error",
                "message": clip_text(message or "Canonical report unavailable"),
            }
        )
    return activity


def _validate_activity_derivations(snapshot: dict[str, Any]) -> None:
    """Reject activity messages that disagree with canonical snapshot state."""
    if snapshot["activity"] != _canonical_activity(snapshot):
        raise ValueError("Command Center activity does not match canonical snapshot state")


def _canonical_capabilities(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    from .command_center import _capabilities

    artifacts = snapshot["artifacts"]
    return [
        item.as_dict()
        for item in _capabilities(
            baseline=artifacts["baseline"],
            policy=artifacts["policy"],
            report=_supported_report(snapshot),
            status=artifacts["status"],
        )
    ]


def _validate_capability_derivations(snapshot: dict[str, Any]) -> None:
    """Reject capability claims that disagree with the canonical capability model."""
    if snapshot["capabilities"] != _canonical_capabilities(snapshot):
        raise ValueError("Command Center capabilities do not match the canonical capability model")


def _canonical_priority_actions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    from .command_center import Capability, _priority_actions

    artifacts = snapshot["artifacts"]
    capabilities = [Capability(**item) for item in _canonical_capabilities(snapshot)]
    return _priority_actions(
        capabilities,
        report=_supported_report(snapshot),
        baseline=artifacts["baseline"],
        policy=artifacts["policy"],
    )


def _validate_priority_action_derivations(snapshot: dict[str, Any]) -> None:
    """Reject priority queues that disagree with the canonical action model."""
    if snapshot["priority_actions"] != _canonical_priority_actions(snapshot):
        raise ValueError("Command Center priority actions do not match the canonical action model")


def _validate_score_derivations(snapshot: dict[str, Any]) -> None:
    """Reject displayed scores that disagree with the canonical scoring model."""
    from .command_center import Capability, _score

    artifacts = snapshot["artifacts"]
    expected_scores = _score(
        baseline=artifacts["baseline"],
        policy=artifacts["policy"],
        report=_supported_report(snapshot),
        status=artifacts["status"],
        capabilities=[Capability(**item) for item in _canonical_capabilities(snapshot)],
    )
    if snapshot["scores"] != expected_scores:
        raise ValueError("Command Center scores do not match the canonical scoring model")


def _serialized_snapshot(snapshot: dict[str, Any]) -> bytes:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _reduce_decision_diagnostics(snapshot: dict[str, Any]) -> None:
    snapshot["artifacts"]["decisions"] = {"bounded": True, "omission_reason": "snapshot_byte_limit"}
    snapshot["bounds"]["artifacts"]["decisions"] = {"bounded": True, "omission_reason": "snapshot_byte_limit"}


def _reduce_authority_diagnostics(snapshot: dict[str, Any]) -> None:
    artifacts = snapshot["artifacts"]
    artifacts["policy"] = {"resolution_status": artifacts["policy"].get("resolution_status")}
    artifacts["baseline"] = {"state": artifacts["baseline"].get("state")}
    artifacts["status"] = {"status": {
        "automatic_mode_enabled": bool((artifacts["status"].get("status") or {}).get("automatic_mode_enabled", False)),
        "pre_commit_hook_installed": bool((artifacts["status"].get("status") or {}).get("pre_commit_hook_installed", False)),
        "post_commit_hook_installed": bool((artifacts["status"].get("status") or {}).get("post_commit_hook_installed", False)),
    }}
    for key in ("policy", "baseline", "status"):
        snapshot["bounds"]["artifacts"][key] = {"bounded": True, "omission_reason": "snapshot_byte_limit"}


def _reduce_report_diagnostics(snapshot: dict[str, Any]) -> None:
    artifacts = snapshot["artifacts"]
    report = artifacts["report"]
    if isinstance(report, dict):
        artifacts["report"] = {key: report[key] for key in (
            "verdict", "findings", "blockers", "warnings", "evidence_items", "evidence",
            "replay_bundle", "reason_code_evidence",
        ) if key in report}
        for key in ("findings", "blockers", "warnings"):
            if key in artifacts["report"]:
                artifacts["report"][key] = []
        if "evidence_items" in artifacts["report"]:
            artifacts["report"]["evidence_items"] = [{}] if report.get("evidence_items") else []
        for key in ("evidence", "replay_bundle", "reason_code_evidence"):
            if key in artifacts["report"]:
                artifacts["report"][key] = {"bounded": True} if report.get(key) else {}
        for key in ("findings", "blockers", "warnings", "evidence_items"):
            metadata = snapshot["bounds"]["collections"][key]
            displayed = _list_count(artifacts["report"].get(key))
            metadata.update(displayed_count=displayed, omitted_count=metadata["total_count"] - displayed,
                            truncated=displayed < metadata["total_count"])
    snapshot["bounds"]["artifacts"]["report"] = {"bounded": True, "omission_reason": "snapshot_byte_limit"}


def _reduce_snapshot_to_size(snapshot: dict[str, Any], max_bytes: int) -> tuple[bytes, bool]:
    """Apply at most three ordered reductions, serializing and stopping after each."""
    encoded = _serialized_snapshot(snapshot)
    if len(encoded) <= max_bytes:
        return encoded, False
    for reducer in (_reduce_decision_diagnostics, _reduce_authority_diagnostics, _reduce_report_diagnostics):
        reducer(snapshot)
        encoded = _serialized_snapshot(snapshot)
        if len(encoded) <= max_bytes:
            return encoded, True
    return encoded, True


def command_center_payload(repo: str | Path) -> dict[str, Any]:
    """Build and validate the canonical Command Center snapshot."""
    from .command_center import build_command_center_snapshot
    from .command_center_contract import validate_command_center_snapshot

    try:
        snapshot = build_command_center_snapshot(repo)
        validate_command_center_snapshot(snapshot)
        _validate_snapshot_derivations(snapshot)
        _validate_report_error_derivations(snapshot)
        _validate_activity_derivations(snapshot)
        _validate_capability_derivations(snapshot)
        _validate_priority_action_derivations(snapshot)
        _validate_score_derivations(snapshot)
        encoded, reduced = _reduce_snapshot_to_size(snapshot, MAX_SNAPSHOT_BYTES)
        if reduced:
            validate_command_center_snapshot(snapshot)
            _validate_snapshot_derivations(snapshot)
            _validate_report_error_derivations(snapshot)
            _validate_activity_derivations(snapshot)
            _validate_capability_derivations(snapshot)
            _validate_priority_action_derivations(snapshot)
            _validate_score_derivations(snapshot)
        if len(encoded) > MAX_SNAPSHOT_BYTES:
            raise ValueError("essential Command Center snapshot exceeds byte limit")
        return {
            "ok": True,
            "status": "success",
            "snapshot": snapshot,
        }
    except Exception:
        return {
            "ok": False,
            "status": "error",
            "error": {
                "code": "command_center_snapshot_failed",
                "message": "The Command Center snapshot could not be built.",
            },
        }
