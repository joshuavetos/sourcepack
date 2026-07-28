from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_endpoint import _validate_score_derivations


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
                "verdict": "WARN",
                "findings": [{"id": "f1"}],
                "blockers": [],
                "warnings": [{"id": "w1"}],
                "evidence_items": [{"id": "e1"}],
                "replay_bundle": {"id": "replay-1"},
                "reason_code_evidence": {"R1": ["e1"]},
            },
            None,
        ),
    )


def test_generated_scores_match_canonical_model(tmp_path: Path) -> None:
    _validate_score_derivations(_snapshot(tmp_path))


@pytest.mark.parametrize(
    "field",
    ["trust", "automation", "product_breadth", "report_depth"],
)
def test_score_drift_is_rejected(tmp_path: Path, field: str) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["scores"][field] = max(0, snapshot["scores"][field] - 1)

    with pytest.raises(ValueError, match="scores do not match the canonical scoring model"):
        _validate_score_derivations(snapshot)


def test_score_validation_recomputes_capability_model_from_artifacts(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["capabilities"][0]["status"] = "READY"

    _validate_score_derivations(snapshot)


def test_score_validation_does_not_mutate_snapshot(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    before = deepcopy(snapshot)

    _validate_score_derivations(snapshot)

    assert snapshot == before
