from __future__ import annotations

from copy import deepcopy

import pytest

from sourcepack.command_center_endpoint import _validate_report_error_derivations


def _snapshot() -> dict:
    return {
        "activity": [
            {"type": "repository", "message": "Repository loaded"},
            {"type": "baseline", "message": "Baseline state: present"},
            {"type": "policy", "message": "Policy resolution: PASS"},
            {"type": "review", "message": "Latest verdict: PASS"},
        ],
        "artifacts": {
            "report": {
                "verdict": "PASS",
                "findings": [],
                "blockers": [],
                "warnings": [],
            },
            "report_error": None,
        },
    }


def test_report_without_error_has_no_terminal_error_activity() -> None:
    _validate_report_error_derivations(_snapshot())


def test_report_error_requires_report_to_be_absent() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report_error"] = {"error": {"message": "Canonical report malformed"}}
    snapshot["activity"].append({"type": "error", "message": "Canonical report malformed"})

    with pytest.raises(ValueError, match="both a canonical report and report_error"):
        _validate_report_error_derivations(snapshot)


def test_report_error_requires_terminal_error_activity() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["artifacts"]["report_error"] = {"error": {"message": "Canonical report malformed"}}

    with pytest.raises(ValueError, match="requires terminal error activity"):
        _validate_report_error_derivations(snapshot)


def test_terminal_error_activity_requires_report_error() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["activity"].append({"type": "error", "message": "Canonical report malformed"})

    with pytest.raises(ValueError, match="requires report_error"):
        _validate_report_error_derivations(snapshot)


def test_terminal_error_message_must_match_report_error() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["artifacts"]["report_error"] = {"error": {"message": "Canonical report malformed"}}
    snapshot["activity"].append({"type": "error", "message": "Different error"})

    with pytest.raises(ValueError, match="does not match report_error"):
        _validate_report_error_derivations(snapshot)


def test_matching_report_error_and_terminal_activity_are_valid() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["artifacts"]["report_error"] = {"error": {"message": "Canonical report malformed"}}
    snapshot["activity"].append({"type": "error", "message": "Canonical report malformed"})

    _validate_report_error_derivations(snapshot)


def test_missing_error_message_uses_canonical_fallback() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["artifacts"]["report_error"] = {"error": {}}
    snapshot["activity"].append({"type": "error", "message": "Canonical report unavailable"})

    _validate_report_error_derivations(snapshot)


def test_validation_does_not_mutate_snapshot() -> None:
    snapshot = _snapshot()
    before = deepcopy(snapshot)

    _validate_report_error_derivations(snapshot)

    assert snapshot == before
