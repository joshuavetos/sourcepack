from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_endpoint import _validate_capability_derivations


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
                "pre_commit_hook_installed": True,
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


def test_generated_capabilities_match_canonical_model(tmp_path: Path) -> None:
    _validate_capability_derivations(_snapshot(tmp_path))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("name", "Invented capability"),
        ("surface", "Imaginary Surface"),
        ("status", "LIVE"),
        ("evidence", "Everything is complete"),
        ("action", None),
    ],
)
def test_capability_field_drift_is_rejected(
    tmp_path: Path,
    field: str,
    replacement: str | None,
) -> None:
    snapshot = _snapshot(tmp_path)
    capability = next(item for item in snapshot["capabilities"] if item["id"] == "policy")
    capability[field] = replacement

    with pytest.raises(ValueError, match="capabilities do not match the canonical capability model"):
        _validate_capability_derivations(snapshot)


def test_planned_capability_cannot_claim_live_status(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    capability = next(item for item in snapshot["capabilities"] if item["id"] == "autonomy")
    capability["status"] = "LIVE"
    capability["evidence"] = "Autonomous improvement is operational"
    capability["action"] = None

    with pytest.raises(ValueError, match="capabilities do not match the canonical capability model"):
        _validate_capability_derivations(snapshot)


def test_capability_validation_does_not_mutate_snapshot(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    before = deepcopy(snapshot)

    _validate_capability_derivations(snapshot)

    assert snapshot == before
