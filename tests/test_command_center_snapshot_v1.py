from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_contract import command_center_snapshot_schema, validate_command_center_snapshot
from sourcepack.command_center_endpoint import _validate_snapshot_derivations


def _build(tmp_path: Path, *, verdict: str | None = "PASS", report_error=None, report_override=None):
    report = report_override if report_override is not None else None if verdict is None else {"verdict": verdict, "findings": [], "blockers": [], "warnings": []}
    return build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _: {"state": "missing", "ok": True},
        policy_reader=lambda _: {"resolution_status": "PASS"},
        git_reader=lambda _: {"branch": "main", "head": "abc"},
        status_reader=lambda _: {"status": {"automatic_mode_enabled": False}},
        report_reader=lambda _: (report, report_error),
    )


def test_checked_in_schema_prevents_contract_drift() -> None:
    checked_in = json.loads(Path("schemas/command_center_snapshot.schema.json").read_text())
    assert checked_in == command_center_snapshot_schema()


def test_pass_warn_fail_and_no_report_snapshots(tmp_path: Path) -> None:
    for verdict in ("PASS", "WARN", "FAIL", None):
        snapshot = _build(tmp_path, verdict=verdict)
        validate_command_center_snapshot(snapshot)
        assert snapshot["schema_version"] == "sourcepack.command_center.v1"
        assert snapshot["posture"]["verdict"] == verdict
        assert set(snapshot) == set(command_center_snapshot_schema()["required"])


def test_malformed_and_unsupported_reports_are_explicit(tmp_path: Path) -> None:
    for code, expected in (("artifact_malformed", "malformed"), ("artifact_version_unsupported", "unsupported")):
        error = {"error": {"code": code, "message": code}}
        snapshot = _build(tmp_path, verdict=None, report_error=error)
        assert snapshot["state"]["report"] == expected
        assert snapshot["state"]["overall"] == expected


def test_same_version_unsupported_verdict_is_a_valid_unsupported_snapshot(tmp_path: Path) -> None:
    unsupported = {
        "verdict": "UNKNOWN",
        "findings": [{"message": "unexpected", "evidence": "must not become canonical evidence"}],
        "blockers": [{"message": "unexpected"}],
        "warnings": [{"message": "unexpected"}],
        "evidence_items": [{"summary": "unsupported evidence"}],
        "generated_at": "2099-01-01T00:00:00Z",
    }
    snapshot = _build(tmp_path, verdict="UNKNOWN", report_override=unsupported)
    validate_command_center_snapshot(snapshot)
    _validate_snapshot_derivations(snapshot)
    assert snapshot["state"]["report"] == "unsupported"
    assert snapshot["state"]["overall"] == "unsupported"
    assert snapshot["posture"]["verdict"] is None
    assert snapshot["display"]["verdict_title"] == "Unsupported Report"
    assert snapshot["workbench"]["review_action"]["available"] is False
    assert snapshot["posture"]["finding_count"] == 0
    assert snapshot["posture"]["blocker_count"] == 0
    assert snapshot["posture"]["warning_count"] == 0
    assert snapshot["display"]["findings_summary"] == "0 blocking, 0 warnings"
    assert snapshot["display"]["evidence_summary"] == "unavailable"
    assert snapshot["display"]["report_time"] is None
    assert snapshot["workbench"]["evidence_cards"] == []
    assert snapshot["state"]["replay"] == "unavailable"
    assert next(item for item in snapshot["available_artifacts"] if item["id"] == "report")["available"] is False
    assert "UNKNOWN" not in json.dumps(snapshot["display"])
    assert "UNKNOWN" not in json.dumps(snapshot["posture"])
    assert "UNKNOWN" not in json.dumps(snapshot["activity"])
    assert "UNKNOWN" not in json.dumps(snapshot["workbench"])
    assert snapshot["activity"][-1]["message"] == "Latest report state: unsupported"
    assert snapshot["artifacts"]["report"]["verdict"] == "UNKNOWN"


def test_workbench_modeled_sections_are_closed(tmp_path: Path) -> None:
    snapshot = _build(tmp_path)
    for section, invalid in (
        ("review_action", {"banana": 9000}),
        ("evidence_cards", [{"banana": 9000}]),
        ("correction_rows", [{"html": "<script>bad()</script>"}]),
        ("proposed_change", {"anything": "goes"}),
    ):
        candidate = deepcopy(snapshot)
        candidate["workbench"][section] = invalid
        try:
            validate_command_center_snapshot(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid open Workbench model accepted: {section}")


def test_review_action_semantics_are_closed(tmp_path: Path) -> None:
    snapshot = _build(tmp_path)
    contradictory_actions = (
        {
            "action_type": "copy_prompt", "available": True, "label": "Copy Correction Prompt",
            "reason": "unsupported_dependency", "target_surface": "correction_prompt",
        },
        {
            "action_type": "none", "available": True, "label": "Do Something", "reason": "unknown",
            "target_surface": "workbench_review", "prompt": "unexpected",
        },
        {
            "action_type": "run_review", "available": False, "label": "Run Review", "reason": "no_diff",
            "target_surface": "correction_prompt",
        },
    )
    for action in contradictory_actions:
        candidate = deepcopy(snapshot)
        candidate["workbench"]["review_action"] = action
        try:
            validate_command_center_snapshot(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError(f"contradictory review action accepted: {action}")


def test_identical_inputs_produce_identical_output(tmp_path: Path) -> None:
    assert _build(tmp_path) == _build(tmp_path)


def test_workbench_has_one_snapshot_source_and_no_client_assembly() -> None:
    html = Path("src/sourcepack/workbench_static/index.html").read_text()
    client = Path("src/sourcepack/workbench_static/command-center-aggregate.js").read_text()
    assert client.count("/api/command-center/v1/snapshot") == 1
    assert "Promise.all" not in html + client
    assert "/api/dashboard/v1/" not in html + client
    assert "state.overview" not in html + client
    assert ".innerHTML" not in client
    assert "posture.verdict ===" not in client
    assert ".toLowerCase()" not in client
    assert "snapshot.display" in client
