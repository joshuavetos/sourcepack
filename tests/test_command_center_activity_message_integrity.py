from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_endpoint import _validate_activity_derivations


def _snapshot(tmp_path: Path, *, with_error: bool = False) -> dict:
    report = None if with_error else {
        "verdict": "WARN",
        "findings": [{"id": "f1"}],
        "blockers": [],
        "warnings": [{"id": "w1"}],
    }
    report_error = {"error": {}} if with_error else None
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
        report_reader=lambda _repo: (report, report_error),
    )


def test_generated_activity_matches_canonical_state(tmp_path: Path) -> None:
    _validate_activity_derivations(_snapshot(tmp_path))


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_normal_activity_message_drift_is_rejected(tmp_path: Path, index: int) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["activity"][index]["message"] = "Invented lifecycle message"

    with pytest.raises(ValueError, match="activity does not match canonical snapshot state"):
        _validate_activity_derivations(snapshot)


def test_repository_activity_must_match_snapshot_path(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["repository"]["path"] = str(tmp_path / "different-repository")

    with pytest.raises(ValueError, match="activity does not match canonical snapshot state"):
        _validate_activity_derivations(snapshot)


def test_error_activity_uses_canonical_fallback_message(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, with_error=True)

    assert snapshot["activity"][-1] == {
        "type": "error",
        "message": "Canonical report unavailable",
    }
    _validate_activity_derivations(snapshot)


def test_error_activity_message_drift_is_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, with_error=True)
    snapshot["activity"][-1]["message"] = "Different error"

    with pytest.raises(ValueError, match="activity does not match canonical snapshot state"):
        _validate_activity_derivations(snapshot)


def test_activity_validation_does_not_mutate_snapshot(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    before = deepcopy(snapshot)

    _validate_activity_derivations(snapshot)

    assert snapshot == before
