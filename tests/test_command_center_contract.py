from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_contract import (
    CAPABILITY_IDS,
    COMMAND_CENTER_SCHEMA_VERSION,
    command_center_snapshot_schema,
    validate_command_center_snapshot,
)


def _snapshot(tmp_path: Path) -> dict:
    return build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _repo: {"state": "present", "ok": True},
        policy_reader=lambda _repo: {"resolution_status": "PASS"},
        git_reader=lambda _repo: {"branch": "hardening-v1", "head": "abc123"},
        status_reader=lambda _repo: {
            "ok": True,
            "status": {
                "automatic_mode_enabled": True,
                "pre_commit_hook_installed": True,
                "post_commit_hook_installed": True,
            },
        },
        report_reader=lambda _repo: (
            {
                "verdict": "PASS",
                "findings": [],
                "blockers": [],
                "warnings": [],
                "replay_bundle": {"id": "replay-1"},
            },
            None,
        ),
    )


def test_generated_snapshot_satisfies_v1_contract(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    validate_command_center_snapshot(snapshot)

    assert snapshot["schema_version"] == COMMAND_CENTER_SCHEMA_VERSION
    assert tuple(item["id"] for item in snapshot["capabilities"]) == CAPABILITY_IDS
    assert command_center_snapshot_schema()["properties"]["schema_version"] == {
        "const": COMMAND_CENTER_SCHEMA_VERSION
    }


def test_contract_rejects_unknown_capability_status(tmp_path: Path) -> None:
    snapshot = deepcopy(_snapshot(tmp_path))
    snapshot["capabilities"][0]["status"] = "MAGIC"

    with pytest.raises(ValueError, match="/capabilities/0/status"):
        validate_command_center_snapshot(snapshot)


def test_contract_rejects_noncanonical_capability_order(tmp_path: Path) -> None:
    snapshot = deepcopy(_snapshot(tmp_path))
    snapshot["capabilities"][0], snapshot["capabilities"][1] = (
        snapshot["capabilities"][1],
        snapshot["capabilities"][0],
    )

    with pytest.raises(ValueError, match="capability order"):
        validate_command_center_snapshot(snapshot)


def test_contract_rejects_invalid_action_payload(tmp_path: Path) -> None:
    snapshot = deepcopy(_snapshot(tmp_path))
    action = snapshot["priority_actions"][0]
    action["action_type"] = "navigate"
    action["target_surface"] = None

    with pytest.raises(ValueError, match="navigate requires only target_surface"):
        validate_command_center_snapshot(snapshot)


def test_contract_allows_additive_fields_inside_raw_artifacts(tmp_path: Path) -> None:
    snapshot = deepcopy(_snapshot(tmp_path))
    snapshot["artifacts"]["report"]["future_report_field"] = {"preserved": True}

    validate_command_center_snapshot(snapshot)


def test_contract_rejects_additive_top_level_fields(tmp_path: Path) -> None:
    snapshot = deepcopy(_snapshot(tmp_path))
    snapshot["future_top_level_field"] = True

    with pytest.raises(ValueError, match="Additional properties"):
        validate_command_center_snapshot(snapshot)
