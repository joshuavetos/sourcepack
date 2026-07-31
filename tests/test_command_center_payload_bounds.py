from __future__ import annotations

import json
from copy import deepcopy

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.command_center_contract import validate_command_center_snapshot
from sourcepack.command_center_limits import MAX_SNAPSHOT_BYTES, MAX_STRING_CHARS, TRUNCATION_MARKER
from sourcepack.command_center_endpoint import (
    _reduce_authority_diagnostics,
    _reduce_decision_diagnostics,
    _reduce_report_diagnostics,
    _reduce_snapshot_to_size,
    _serialized_snapshot,
)
from sourcepack.workbench import _bounded_changed_file_excerpt, _safe_report_paths


def _snapshot(tmp_path, report):
    return build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _: {"state": "present", "metadata": {str(i): "x" * 5000 for i in range(1000)}},
        policy_reader=lambda _: {"resolution_status": "PASS", "policy": [["<script>" * 1000] * 100] * 100},
        git_reader=lambda _: {"branch": "main"},
        status_reader=lambda _: {"status": {"automatic_mode_enabled": True}},
        report_reader=lambda _: (report, None),
    )


def test_adversarial_snapshot_is_deterministic_and_honest(tmp_path, monkeypatch):
    hostile = "🙂<script>alert(1)</script>" * 1000
    report = {
        "verdict": "FAIL", "findings": [{"message": hostile, "path": "a.py"} for _ in range(3000)],
        "blockers": [{"message": hostile} for _ in range(2000)], "warnings": [{"message": hostile} for _ in range(1000)],
        "evidence_items": [{"summary": hostile, "metadata": {str(i): hostile for i in range(100)}} for _ in range(4000)],
        "replay_bundle": {"records": [hostile] * 1000}, "remediation": {"prompt": hostile},
    }
    built = _snapshot(tmp_path, report)
    built_bytes = json.dumps(built, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert len(built_bytes) > MAX_SNAPSHOT_BYTES
    original_posture = built["posture"].copy()
    original_actions = built["priority_actions"]
    import sourcepack.command_center as builder_module
    from sourcepack.command_center_endpoint import command_center_payload
    monkeypatch.setattr(builder_module, "build_command_center_snapshot", lambda _: json.loads(json.dumps(built)))
    first = command_center_payload(tmp_path)["snapshot"]
    second = command_center_payload(tmp_path)["snapshot"]
    validate_command_center_snapshot(first)
    encoded = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert encoded == json.dumps(second, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert first["posture"]["verdict"] == "FAIL"
    assert first["posture"] == original_posture
    assert first["priority_actions"] == original_actions
    assert first["bounds"]["artifacts"]["report"]["omission_reason"] == "snapshot_byte_limit"
    assert first["bounds"]["artifacts"]["decisions"]["omission_reason"] == "snapshot_byte_limit"
    bounds = first["bounds"]["collections"]["findings"]
    assert bounds["total_count"] == 3000
    assert bounds["omitted_count"] == 3000 - bounds["displayed_count"]
    assert bounds["truncated"] is True
    assert len(encoded) <= MAX_SNAPSHOT_BYTES


def test_exact_string_boundary_and_one_over(tmp_path):
    report = {"verdict": "WARN", "findings": [{"message": "x" * MAX_STRING_CHARS}, {"message": "x" * (MAX_STRING_CHARS + 1)}]}
    snapshot = _snapshot(tmp_path, report)
    messages = [item["message"] for item in snapshot["artifacts"]["report"]["findings"]]
    assert messages[0] == "x" * MAX_STRING_CHARS
    assert messages[1].endswith(TRUNCATION_MARKER)


def test_repository_controlled_essential_strings_are_clipped(tmp_path):
    long = "界" * (MAX_STRING_CHARS + 1)
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _: {"state": long},
        policy_reader=lambda _: {"resolution_status": long},
        git_reader=lambda _: {"branch": long},
        status_reader=lambda _: {"status": {}},
        report_reader=lambda _: ({"verdict": "WARN", "generated_at": long}, None),
    )
    values = (snapshot["display"]["branch"], snapshot["display"]["report_time"],
              snapshot["posture"]["baseline_state"], snapshot["posture"]["policy_resolution_status"])
    assert all(value.endswith(TRUNCATION_MARKER) for value in values)
    assert all(len(value) == MAX_STRING_CHARS for value in values)


def test_oversized_changed_file_paths_are_clipped(tmp_path):
    oversized = "nested/" + "界" * MAX_STRING_CHARS
    report = {
        "verdict": "WARN",
        "raw_patch_judgment": {"modified_files": [oversized]},
        "findings": [{"path": oversized + "duplicate-source"}],
    }

    paths = _safe_report_paths(report)
    proposed_change = _bounded_changed_file_excerpt(tmp_path, report)

    assert paths == proposed_change["paths"]
    assert len(paths) == 1  # Identical clipped prefixes are deterministically deduplicated.
    assert all(len(path) == MAX_STRING_CHARS for path in paths)
    assert all(path.endswith(TRUNCATION_MARKER) for path in paths)
    assert proposed_change["excerpts"][0]["status"] == "omitted"
    assert proposed_change["excerpts"][0]["path"] == paths[0]
    snapshot = _snapshot(tmp_path, report)
    validate_command_center_snapshot(snapshot)


def test_essential_snapshot_that_cannot_fit_fails_safely(tmp_path, monkeypatch):
    built = _snapshot(tmp_path, {"verdict": "PASS", "findings": []})
    import sourcepack.command_center as builder_module
    import sourcepack.command_center_endpoint as endpoint_module
    monkeypatch.setattr(builder_module, "build_command_center_snapshot", lambda _: built)
    monkeypatch.setattr(endpoint_module, "MAX_SNAPSHOT_BYTES", 1)
    assert endpoint_module.command_center_payload(tmp_path) == {
        "ok": False, "status": "error",
        "error": {"code": "command_center_snapshot_failed", "message": "The Command Center snapshot could not be built."},
    }


def _staged_snapshot(tmp_path):
    snapshot = _snapshot(tmp_path, {
        "verdict": "WARN", "findings": [{"message": "finding"}], "blockers": [], "warnings": [],
        "evidence_items": [{"summary": "evidence"}], "diagnostic": ["r" * MAX_STRING_CHARS] * 64,
    })
    snapshot["artifacts"]["decisions"] = {"records": ["d" * MAX_STRING_CHARS] * 64}
    snapshot["artifacts"]["policy"]["diagnostic"] = ["p" * MAX_STRING_CHARS] * 64
    snapshot["artifacts"]["baseline"]["diagnostic"] = ["b" * MAX_STRING_CHARS] * 64
    snapshot["artifacts"]["status"]["diagnostic"] = ["s" * MAX_STRING_CHARS] * 64
    return snapshot


def test_decisions_only_reduction_preserves_authority_and_report(tmp_path):
    snapshot = _staged_snapshot(tmp_path)
    expected = deepcopy(snapshot)
    _reduce_decision_diagnostics(expected)
    limit = len(_serialized_snapshot(expected))
    original_policy = deepcopy(snapshot["artifacts"]["policy"])
    original_report = deepcopy(snapshot["artifacts"]["report"])

    encoded, reduced = _reduce_snapshot_to_size(snapshot, limit)

    assert reduced and len(encoded) <= limit
    assert snapshot["artifacts"]["policy"] == original_policy
    assert snapshot["artifacts"]["report"] == original_report
    assert snapshot["bounds"]["artifacts"]["policy"]["omission_reason"] is None
    assert snapshot["bounds"]["artifacts"]["report"]["omission_reason"] is None


def test_authority_reduction_runs_only_after_decisions_are_insufficient(tmp_path):
    snapshot = _staged_snapshot(tmp_path)
    after_decisions = deepcopy(snapshot)
    _reduce_decision_diagnostics(after_decisions)
    expected = deepcopy(after_decisions)
    _reduce_authority_diagnostics(expected)
    limit = len(_serialized_snapshot(expected))
    original_report = deepcopy(snapshot["artifacts"]["report"])
    assert len(_serialized_snapshot(after_decisions)) > limit

    encoded, _ = _reduce_snapshot_to_size(snapshot, limit)

    assert len(encoded) <= limit
    assert snapshot["artifacts"]["report"] == original_report
    assert snapshot["bounds"]["artifacts"]["policy"]["omission_reason"] == "snapshot_byte_limit"
    assert snapshot["bounds"]["artifacts"]["report"]["omission_reason"] is None


def test_report_reduction_is_last(tmp_path):
    snapshot = _staged_snapshot(tmp_path)
    after_authority = deepcopy(snapshot)
    _reduce_decision_diagnostics(after_authority)
    _reduce_authority_diagnostics(after_authority)
    expected = deepcopy(after_authority)
    _reduce_report_diagnostics(expected)
    limit = len(_serialized_snapshot(expected))
    assert len(_serialized_snapshot(after_authority)) > limit

    encoded, _ = _reduce_snapshot_to_size(snapshot, limit)

    assert len(encoded) <= limit
    assert snapshot["bounds"]["artifacts"]["decisions"]["omission_reason"] == "snapshot_byte_limit"
    assert snapshot["bounds"]["artifacts"]["policy"]["omission_reason"] == "snapshot_byte_limit"
    assert snapshot["bounds"]["artifacts"]["report"]["omission_reason"] == "snapshot_byte_limit"
    assert snapshot["artifacts"]["report"]["findings"] == []
