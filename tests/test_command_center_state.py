from pathlib import Path

from sourcepack.command_center import COMMAND_CENTER_SCHEMA_VERSION, build_command_center_snapshot


def _git(_repo: Path):
    return {"branch": "mega/sourcepack-command-center", "head": "abc123"}


def _status(*, automatic=False, pre=False, post=False):
    def reader(_repo: Path):
        return {
            "ok": True,
            "status": {
                "automatic_mode_enabled": automatic,
                "pre_commit_hook_installed": pre,
                "post_commit_hook_installed": post,
            },
        }

    return reader


def test_snapshot_exposes_live_capabilities_and_scores(tmp_path):
    report = {
        "verdict": "PASS",
        "findings": [],
        "blockers": [],
        "warnings": [],
        "evidence_items": [{"id": "e1"}],
        "replay_bundle": {"id": "r1"},
        "reason_code_evidence": {"ok": True},
    }
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "present", "ok": True},
        policy_reader=lambda _repo: {"resolution_status": "PASS"},
        git_reader=_git,
        status_reader=_status(automatic=True, pre=True, post=True),
        report_reader=lambda _repo: (report, None),
    )

    assert snapshot["schema_version"] == COMMAND_CENTER_SCHEMA_VERSION
    assert snapshot["posture"]["verdict"] == "PASS"
    assert snapshot["scores"] == {
        "trust": 100,
        "automation": 100,
        "product_breadth": 67,
        "report_depth": 100,
    }
    by_id = {item["id"]: item for item in snapshot["capabilities"]}
    assert by_id["review"]["status"] == "LIVE"
    assert by_id["baseline"]["status"] == "LIVE"
    assert by_id["policy"]["status"] == "LIVE"
    assert by_id["hook"]["status"] == "LIVE"
    assert by_id["replay"]["status"] == "LIVE"
    assert by_id["integrations"]["status"] == "PLANNED"
    assert snapshot["priority_actions"][0]["id"] == "build_adversarial_runner"


def test_missing_trust_artifacts_become_top_priority(tmp_path):
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "missing", "ok": False},
        policy_reader=lambda _repo: {"resolution_status": "FAIL"},
        git_reader=_git,
        status_reader=_status(),
        report_reader=lambda _repo: (None, None),
    )

    assert snapshot["scores"]["trust"] == 0
    assert snapshot["posture"]["verdict"] is None
    assert [item["id"] for item in snapshot["priority_actions"][:3]] == [
        "create_baseline",
        "repair_policy",
        "run_review",
    ]
    by_id = {item["id"]: item for item in snapshot["capabilities"]}
    assert by_id["baseline"]["status"] == "NEEDS_SETUP"
    assert by_id["policy"]["status"] == "DEGRADED"
    assert by_id["hook"]["status"] == "READY_TO_BUILD"


def test_warn_report_surfaces_resolution_action(tmp_path):
    report = {
        "verdict": "WARN",
        "findings": [{"id": "f1"}],
        "blockers": [],
        "warnings": [{"id": "w1"}],
    }
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "stale", "ok": True},
        policy_reader=lambda _repo: {"resolution_status": "PASS"},
        git_reader=_git,
        status_reader=_status(pre=True),
        report_reader=lambda _repo: (report, None),
    )

    actions = {item["id"]: item for item in snapshot["priority_actions"]}
    assert actions["refresh_baseline"]["priority"] == "P0"
    assert actions["resolve_findings"]["priority"] == "P1"
    assert snapshot["posture"]["finding_count"] == 1
    assert snapshot["posture"]["warning_count"] == 1


def test_report_error_is_recorded_without_fabricating_report(tmp_path):
    error = {"error": {"message": "report malformed"}}
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "present", "ok": True},
        policy_reader=lambda _repo: {"resolution_status": "PASS"},
        git_reader=_git,
        status_reader=_status(),
        report_reader=lambda _repo: (None, error),
    )

    assert snapshot["artifacts"]["report"] is None
    assert snapshot["artifacts"]["report_error"] == error
    assert snapshot["activity"][-1] == {"type": "error", "message": "report malformed"}
