from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from sourcepack.command_center_endpoint import _validate_snapshot_derivations
from sourcepack.workbench import WorkbenchHandler


def _snapshot() -> dict:
    return {
        "posture": {
            "verdict": "WARN",
            "baseline_state": "present",
            "policy_resolution_status": "PASS",
            "automatic_mode_enabled": True,
            "finding_count": 2,
            "blocker_count": 1,
            "warning_count": 1,
        },
        "artifacts": {
            "baseline": {"state": "present"},
            "policy": {"resolution_status": "PASS"},
            "status": {"status": {"automatic_mode_enabled": True}},
            "report": {
                "verdict": "WARN",
                "findings": [{"id": "f1"}, {"id": "f2"}],
                "blockers": [{"id": "b1"}],
                "warnings": [{"id": "w1"}],
            },
            "report_error": None,
        },
    }


def test_package_import_does_not_replace_workbench_handler() -> None:
    import sourcepack
    from sourcepack import workbench

    original = workbench.WorkbenchHandler
    importlib.reload(sourcepack)

    assert workbench.WorkbenchHandler is original
    assert workbench.WorkbenchHandler is WorkbenchHandler


def test_repeated_workbench_imports_do_not_wrap_handler() -> None:
    from sourcepack import workbench

    original = workbench.WorkbenchHandler
    importlib.import_module("sourcepack.command_center_endpoint")
    importlib.import_module("sourcepack.command_center_endpoint")

    assert workbench.WorkbenchHandler is original
    assert not hasattr(workbench.WorkbenchHandler, "_sourcepack_command_center_handler_installed")


def test_no_patch_installation_api_remains() -> None:
    endpoint = importlib.import_module("sourcepack.command_center_endpoint")

    assert not hasattr(endpoint, "install_command_center_route")
    assert not hasattr(endpoint, "command_center_handler")
    assert "sourcepack.command_center_endpoint" in sys.modules

def test_posture_derivations_match_embedded_artifacts() -> None:
    _validate_snapshot_derivations(_snapshot())


def test_posture_rejects_report_verdict_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["verdict"] = "PASS"

    with pytest.raises(ValueError, match="verdict does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_posture_rejects_report_count_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["finding_count"] = 1

    with pytest.raises(ValueError, match="finding_count does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_posture_rejects_artifact_state_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["baseline_state"] = "stale"

    with pytest.raises(ValueError, match="baseline_state does not match embedded artifacts"):
        _validate_snapshot_derivations(snapshot)


def test_posture_without_report_requires_null_verdict_and_zero_counts() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["posture"].update(
        verdict=None,
        finding_count=0,
        blocker_count=0,
        warning_count=0,
    )

    _validate_snapshot_derivations(snapshot)

    snapshot["posture"]["warning_count"] = 1
    with pytest.raises(ValueError, match="warning_count does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_index_declares_aggregate_client_statically() -> None:
    body = Path("src/sourcepack/workbench_static/index.html").read_text(encoding="utf-8")

    assert body.count('<script src="/command-center-aggregate.js"></script>') == 1
    assert body.count("<!-- SourcePack Workbench -->") == 1
