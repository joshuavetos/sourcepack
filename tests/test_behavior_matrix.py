from __future__ import annotations

import json
import subprocess
import sys

from tools.behavior_matrix import (
    CANONICAL_REASON_CODES,
    build_scenarios,
    normalize_reason_code,
    normalize_reason_codes,
    run_matrix,
    validate_scenario_definitions,
)


def test_behavior_matrix_scenario_count_and_unique_ids():
    scenarios = build_scenarios()
    assert len(scenarios) >= 55
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids))


def test_all_scenario_expected_reason_codes_are_canonical():
    scenarios = build_scenarios()
    validate_scenario_definitions(scenarios)
    for scenario in scenarios:
        for code in scenario.expected_reason_codes_include + scenario.expected_reason_codes_exclude:
            assert code in CANONICAL_REASON_CODES
            assert normalize_reason_code(code) == code


def test_warn_and_fail_scenarios_have_expected_reason_codes():
    for scenario in build_scenarios():
        if scenario.expected_verdict in {"WARN", "FAIL"}:
            assert scenario.expected_reason_codes_include, scenario.scenario_id


def test_pass_scenarios_do_not_require_expected_reason_codes():
    pass_scenarios = [s for s in build_scenarios() if s.expected_verdict == "PASS"]
    assert pass_scenarios
    assert any(not s.expected_reason_codes_include for s in pass_scenarios)


def test_internal_judge_patch_scenarios_do_not_validate_exit_codes():
    judge_patch_scenarios = [s for s in build_scenarios() if s.command_mode == "judge_patch"]
    assert judge_patch_scenarios
    assert all(s.expected_exit_code is None for s in judge_patch_scenarios)


def test_scenario_schema_uses_expected_report_fields_name():
    scenario = build_scenarios()[0]
    assert hasattr(scenario, "expected_report_fields")
    assert not hasattr(scenario, "expected_checked_fields")


def test_reason_code_normalization_is_deterministic():
    assert normalize_reason_code("path_escape") == "unsafe_path"
    assert normalize_reason_code("missing_modified_files") == "missing_file"
    assert normalize_reason_codes(["new_file", "path_escape", "new_file"]) == ["new_file", "unsafe_path"]


def test_direct_matrix_run_passes():
    data = run_matrix()
    assert data["scenario_count"] >= 55
    assert data["metamorphic_invariant_count"] >= 8
    assert data["failed"] == 0
    assert data["passed"] == data["selected_count"]


def test_cli_json_output_is_valid_json_only():
    cp = subprocess.run([sys.executable, "tools/behavior_matrix.py", "--json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    data = json.loads(cp.stdout)
    assert data["failed"] == 0
    assert cp.stdout.lstrip().startswith("{")
    assert cp.stdout.rstrip().endswith("}")


def test_cli_human_run_passes():
    cp = subprocess.run([sys.executable, "tools/behavior_matrix.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert "Behavior matrix:" in cp.stdout


def test_core_invariant_tags_present():
    tags = {tag for scenario in build_scenarios() for tag in scenario.tags}
    assert {
        "invariant_reorder",
        "invariant_readme",
        "invariant_path",
        "invariant_whitespace",
        "invariant_manifest_order",
        "invariant_tempdir",
        "invariant_human_json",
    } <= tags


def test_behavior_matrix_reports_include_replay_evidence_for_representative_cases():
    data = run_matrix()
    covered = set()
    for result in data["results"]:
        report = result.get("report") or {}
        reason_map = report.get("reason_code_evidence") or report.get("traffic", {}).get("reason_code_evidence") or {}
        replay = report.get("replay_bundle") or report.get("traffic", {}).get("replay_bundle") or {}
        for code in {"missing_file", "unsupported_dependency", "unsupported_command", "protected_artifact", "unsupported_ecosystem", "binary_diff"}:
            if code in reason_map:
                assert reason_map[code]
                assert replay.get("schema_version") == "sourcepack.replay_bundle.v1"
                covered.add(code)
    assert {"missing_file", "unsupported_dependency", "unsupported_command", "protected_artifact"} <= covered
