from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_endpoint import _validate_priority_action_derivations


def _snapshot(tmp_path: Path) -> dict:
    return build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "stale", "ok": True},
        policy_reader=lambda _repo: {"resolution_status": "WARN"},
        git_reader=lambda _repo: {"branch": "hardening-v1", "head": "abc123"},
        status_reader=lambda _repo: {
            "ok": True,
            "status": {
                "automatic_mode_enabled": False,
                "pre_commit_hook_installed": False,
                "post_commit_hook_installed": False,
            },
        },
        report_reader=lambda _repo: (
            {
                "verdict": "WARN",
                "findings": [{"id": "f1"}],
                "blockers": [],
                "warnings": [{"id": "w1"}],
                "replay_bundle": None,
            },
            None,
        ),
    )


def test_generated_priority_actions_match_canonical_model(tmp_path: Path) -> None:
    _validate_priority_action_derivations(_snapshot(tmp_path))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("priority", "P3"),
        ("label", "Do something else"),
        ("reason", "Invented reason"),
        ("command", "sourcepack baseline --force ."),
    ],
)
def test_priority_action_field_drift_is_rejected(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    snapshot = _snapshot(tmp_path)
    action = next(item for item in snapshot["priority_actions"] if item["id"] == "refresh_baseline")
    action[field] = replacement

    with pytest.raises(ValueError, match="priority actions do not match the canonical action model"):
        _validate_priority_action_derivations(snapshot)


def test_priority_action_order_drift_is_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["priority_actions"][0], snapshot["priority_actions"][1] = (
        snapshot["priority_actions"][1],
        snapshot["priority_actions"][0],
    )

    with pytest.raises(ValueError, match="priority actions do not match the canonical action model"):
        _validate_priority_action_derivations(snapshot)


def test_missing_required_priority_action_is_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["priority_actions"] = [
        item for item in snapshot["priority_actions"] if item["id"] != "repair_policy"
    ]

    with pytest.raises(ValueError, match="priority actions do not match the canonical action model"):
        _validate_priority_action_derivations(snapshot)


def test_extra_valid_but_unsupported_action_is_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["priority_actions"].append(
        {
            "id": "run_review",
            "priority": "P3",
            "label": "Run review",
            "action_type": "run_review",
            "command": None,
            "target_surface": None,
            "reason": "Review again even though a report exists.",
        }
    )

    with pytest.raises(ValueError, match="priority actions do not match the canonical action model"):
        _validate_priority_action_derivations(snapshot)


def test_priority_action_validation_does_not_mutate_snapshot(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    before = deepcopy(snapshot)

    _validate_priority_action_derivations(snapshot)

    assert snapshot == before
