import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import real_corpus_validation as rcv


def run_tool(*args):
    return subprocess.run([sys.executable, "tools/real_corpus_validation.py", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(cmd, cwd):
    return subprocess.run(["git", *cmd], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def make_repo(tmp_path, *, python=True, node=False):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("demo\n")
    if python:
        (repo / "app.py").write_text("print('hi')\n")
        (repo / "requirements.txt").write_text("requests\n")
    if node:
        (repo / "package.json").write_text(json.dumps({"scripts":{"dev":"vite"},"dependencies":{"react":"latest"}}))
        (repo / "index.js").write_text("console.log('hi')\n")
    git(["init"], repo)
    git(["config", "user.email", "t@example.invalid"], repo)
    git(["config", "user.name", "Test"], repo)
    git(["add", "."], repo)
    git(["commit", "-m", "initial"], repo)
    return repo


def test_repo_list_parsing(tmp_path):
    p = tmp_path / "repos.json"
    p.write_text(json.dumps([{"repo_id":"x","url":"/tmp/x","ecosystem_tags":[],"expected_features":[],"notes":"n"}]))
    assert rcv.load_repo_list(p)[0]["repo_id"] == "x"


def test_no_corpus_json_behavior():
    cp = run_tool("--json")
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["repo_count"] == 0
    assert data["results"] == []


def test_local_repo_execution_json_and_filter(tmp_path):
    repo = make_repo(tmp_path)
    cp = run_tool("--repo", str(repo), "--scenario", "benign_readme_edit", "--json")
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["scenario_count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["mutation_result"]["status"] in rcv.MUTATION_STATUSES


def test_mutation_failure_detection(tmp_path):
    p = tmp_path / "same.txt"
    p.write_text("x")
    mr = rcv.mutate_file(p, "x", append=False)
    assert mr.status == "mutation_failed"
    assert not mr.applied


def test_skipped_incompatible_repo_detection(tmp_path):
    repo = make_repo(tmp_path, python=False)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["undeclared_python_dependency_import"])
    assert mr.status == "skipped_incompatible_repo"


def test_cleanup_uses_hard_reset_and_clean(tmp_path, monkeypatch):
    calls=[]
    def fake_run(cmd, cwd, timeout):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(rcv, "run", fake_run)
    assert rcv.cleanup_repo(tmp_path)
    assert calls == [["git","reset","--hard","HEAD"],["git","clean","-fdx"]]


def test_classification_metrics():
    s = rcv.Scenario("x","",(),(),"","","PASS",("needed",),("bad",))
    mr = rcv.MutationResult("applied", True)
    f = rcv.classify(s, "FAIL", ["bad"], False, False, False, mr)
    assert f["false_red"] and f["wrong_reason_code"]
    s2 = rcv.Scenario("y","",(),(),"","","FAIL")
    assert rcv.classify(s2, "WARN", [], False, False, False, mr)["missed_red"]
    assert rcv.classify(s, "WARN", [], False, False, False, mr)["noisy_warn"]
    assert rcv.classify(s, None, [], True, False, False, mr)["invalid_json"]


def test_policy_over_suppression_and_trust_violation():
    mr = rcv.MutationResult("applied", True)
    assert rcv.classify(rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"], "PASS", [], False, False, False, mr)["policy_over_suppression"]
    assert rcv.classify(rcv.SCENARIO_BY_ID["execution_claim_without_ledger"], "PASS", [], False, False, False, mr)["trust_violation"]


def test_circuit_breaker_behavior(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]] * 6)
    monkeypatch.setattr(rcv, "prepare_repo", lambda entry, cache, timeout: (str(repo), None, None))
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (0, "not json", "", False, None, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, code = rcv.run_harness(args)
    assert code == 1
    assert summary["circuit_breaker_triggered"] is True
    assert summary["invalid_json"] == 5


def test_network_unavailable_reported_separately(tmp_path):
    p = tmp_path / "repos.json"
    p.write_text(json.dumps([{"repo_id":"bad","url":"https://example.invalid/sourcepack-nope.git","ecosystem_tags":[],"expected_features":[],"notes":"n"}]))
    cp = run_tool("--repo-list", str(p), "--max-repos", "1", "--scenario", "benign_readme_edit", "--timeout", "2", "--json")
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["results"][0]["notes"][0] in {"network_unavailable", "clone_failed"}
    assert data["crash"] == 0


def test_execution_claim_without_ledger_writes_detectable_claim(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["execution_claim_without_ledger"])
    assert mr.applied
    assert "tests passed" in (repo / "README.md").read_text()
    assert rcv.SCENARIO_BY_ID["execution_claim_without_ledger"].expected_reason_codes_include == ("execution_evidence_missing",)


def test_policy_matching_scenario_creates_allow_policy_before_evaluation(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"])
    assert mr.applied
    assert (repo / ".sourcepack" / "policy" / "allow.jsonl").exists()
    assert mr.details["policy_allowed_dependency"] == "fastapi"
    assert "sourcepack allow dependency fastapi" in mr.details["policy_command"]
    assert "import fastapi" in (repo / "app.py").read_text()


def test_policy_nonmatching_scenario_leaves_unrelated_dependency_unsuppressed(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"])
    assert mr.applied
    text = (repo / "app.py").read_text()
    assert "import fastapi" in text
    assert "import flask" in text
    assert mr.details["policy_allowed_dependency"] == "fastapi"
    assert mr.details["unsuppressed_dependency"] == "flask"


def test_same_patch_python_dependency_mutates_manifest_not_comment(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_python_dependency_add_plus_import"])
    assert mr.applied
    assert "fastapi" in (repo / "requirements.txt").read_text()
    assert "sourcepack corpus dependency" not in (repo / "requirements.txt").read_text()
    assert mr.details["manifest_before_sha256"] != mr.details["manifest_after_sha256"]


def test_same_patch_js_dependency_mutates_package_json(tmp_path):
    repo = make_repo(tmp_path, node=True)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"])
    assert mr.applied
    data = json.loads((repo / "package.json").read_text())
    assert mr.details["dependency_added"] == "sourcepack-corpus-js-dep"
    assert data["dependencies"]["sourcepack-corpus-js-dep"] == "latest"
    assert "react" != mr.details["dependency_added"]
    assert mr.details["dependency_preexisting"] is False
    assert mr.details["import_specifier"] == mr.details["dependency_added"]
    assert mr.details["package_json_before_sha256"] != mr.details["package_json_after_sha256"]
    assert mr.details["source_before_sha256"] != mr.details["source_after_sha256"]


def test_same_patch_js_dependency_fails_if_candidates_preexist(tmp_path):
    repo = make_repo(tmp_path, node=True)
    data = json.loads((repo / "package.json").read_text())
    data["dependencies"].update({"sourcepack-corpus-js-dep":"latest", "sourcepack-corpus-js-dep-2":"latest", "sourcepack-corpus-js-dep-3":"latest"})
    (repo / "package.json").write_text(json.dumps(data))
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"])
    assert mr.status == "mutation_failed"
    assert mr.reason == "js_dependency_candidate_preexisting"


@pytest.mark.parametrize("source", [
    "import x from 'sourcepack-corpus-js-dep';",
    'import { x } from "sourcepack-corpus-js-dep";',
    "import {\n  x,\n  y\n} from 'sourcepack-corpus-js-dep';",
    "import * as x from 'sourcepack-corpus-js-dep';",
    "import 'sourcepack-corpus-js-dep';",
    "const x = require('sourcepack-corpus-js-dep');",
    'let x = require("sourcepack-corpus-js-dep");',
    "var x = require('sourcepack-corpus-js-dep');",
    "const { x } = require('sourcepack-corpus-js-dep');",
    "require('sourcepack-corpus-js-dep');",
    'await import("sourcepack-corpus-js-dep");',
    "import('sourcepack-corpus-js-dep').then(m => m);",
])
def test_source_contains_js_import_accepts_structural_forms(source):
    assert rcv.source_contains_js_import(source, "sourcepack-corpus-js-dep")


@pytest.mark.parametrize("source", [
    "// import x from 'sourcepack-corpus-js-dep';",
    "/* import x from 'sourcepack-corpus-js-dep'; */",
    "const msg = 'sourcepack-corpus-js-dep';",
    'const msg = "Install sourcepack-corpus-js-dep";',
    "console.log('sourcepack-corpus-js-dep');",
    'const msg = "import x from \'sourcepack-corpus-js-dep\';";',
    'const msg = \'import x from "sourcepack-corpus-js-dep";\';',
    'const msg = "require(\'sourcepack-corpus-js-dep\')";',
    'const msg = "import(\'sourcepack-corpus-js-dep\')";',
    'console.log("import x from \'sourcepack-corpus-js-dep\';");',
    'console.log("require(\'sourcepack-corpus-js-dep\')");',
    "import x from 'sourcepack-corpus-js-dep-extra';",
    "require('sourcepack-corpus-js-dep-extra');",
    "import('sourcepack-corpus-js-dep-extra');",
    'import x from \'other\'; const msg = "from \'sourcepack-corpus-js-dep\'";',
])
def test_source_contains_js_import_rejects_non_structural_or_substring_forms(source):
    assert not rcv.source_contains_js_import(source, "sourcepack-corpus-js-dep")



def test_scenario_audit_matches_scenario_registry():
    scenario_ids = {s.scenario_id for s in rcv.SCENARIOS}
    assert set(rcv.SCENARIO_AUDIT) == scenario_ids
    for scenario in rcv.SCENARIOS:
        audit = rcv.SCENARIO_AUDIT[scenario.scenario_id]
        assert audit["scenario_id"] == scenario.scenario_id
        assert audit["expected_verdict"] == scenario.expected_verdict
        assert tuple(audit["expected_reason_codes_include"]) == scenario.expected_reason_codes_include
        assert tuple(audit["expected_reason_codes_exclude"]) == scenario.expected_reason_codes_exclude
        assert audit.get("mutation_kind") in rcv.SCENARIO_AUDIT_ALLOWED_MUTATION_KINDS
        proof = audit.get("independent_proof")
        assert proof
        assert not isinstance(proof, str)
        assert isinstance(proof, tuple)
        assert set(proof) <= rcv.SCENARIO_AUDIT_ALLOWED_PROOFS
        assert all("Verifier checks mutation" not in item for item in proof)
    assert rcv.SCENARIO_AUDIT["same_patch_python_dependency_add_plus_import"]["mutation_kind"] == "multi_file_mutation"
    assert rcv.SCENARIO_AUDIT["same_patch_js_dependency_add_plus_import"]["mutation_kind"] == "multi_file_mutation"
    assert rcv.SCENARIO_AUDIT["docker_compose_missing_file"]["mutation_kind"] == "delete_plus_file_mutation"
    assert rcv.SCENARIO_AUDIT["protected_sourcepack_baseline_edit"]["mutation_kind"] == "programmatic_patch_text"
    assert rcv.SCENARIO_AUDIT["git_config_edit"]["mutation_kind"] == "programmatic_patch_text"
    assert rcv.SCENARIO_AUDIT["malformed_diff"]["mutation_kind"] == "programmatic_patch_text"

def test_makefile_existing_uses_real_parsed_target(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "Makefile").write_text(".PHONY: clean\nclean:\n\t@echo clean\nbuild:\n\t@echo build\n")
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["make_target_existing"])
    assert mr.applied
    assert mr.details["make_target"] == "build"
    assert "make build" in (repo / "README.md").read_text()


def test_makefile_missing_requires_existing_makefile_for_target_semantics(tmp_path):
    repo = make_repo(tmp_path, python=False)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["make_target_missing"])
    assert mr.status == "skipped_incompatible_repo"
    assert mr.reason == "makefile_missing"


def test_docker_compose_missing_uses_detected_command_form(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "compose.yml").write_text("services: {}\n")
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["docker_compose_missing_file"])
    assert mr.applied
    assert "docker compose up" in (repo / "README.md").read_text()
    assert mr.details["command_written"] == "docker compose up"
    assert mr.details["deleted_compose_files"]
    assert mr.details["compose_files_remaining"] == []
    assert not (repo / "compose.yml").exists()


def test_allowed_alternate_outcomes_are_honored():
    s = rcv.Scenario("alt", "", (), (), "", "", "PASS", allowed_alternate_outcomes=({"verdict":"WARN", "reason_codes_exclude":("bad",), "justification":"ok"},))
    mr = rcv.MutationResult("applied", True)
    flags = rcv.classify(s, "WARN", [], False, False, False, mr)
    assert not flags["noisy_warn"]
    assert rcv.allowed_alternate_match(s, "WARN", [])[0] is True


def test_console_script_metadata_points_to_callable():
    import tomllib
    import importlib
    data = tomllib.loads(Path("pyproject.toml").read_text())
    target = data["project"]["scripts"]["sourcepack"]
    assert target == "sourcepack.cli:main"
    module_name, attr = target.split(":", 1)
    assert callable(getattr(importlib.import_module(module_name), attr))


def test_failures_only_json_includes_failures_and_json_only(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (1, "{}", "", True, {"verdict":"FAIL","findings":[]}, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["results"] and summary["results"][0]["false_red"]
    assert json.loads(json.dumps(summary))["results"][0]["scenario_id"] == "benign_readme_edit"


def test_run_harness_verifier_failure_blocks_evaluation_and_reports_mutation_failure(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    calls = []
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))

    def fake_verify(repo, scenario, mr):
        calls.append("verify")
        return rcv.MutationResult("mutation_failed", False, reason="verifier_rejected")

    def fake_evaluate(repo, scenario, timeout):
        calls.append("evaluate")
        raise AssertionError("evaluate must not run after verifier mutation failure")

    monkeypatch.setattr(rcv, "verify_scenario_state", fake_verify)
    monkeypatch.setattr(rcv, "evaluate", fake_evaluate)
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert calls == ["verify"]
    assert summary["results"][0]["mutation_status"] == "mutation_failed"
    assert summary["results"][0]["mutation_result"]["reason"] == "verifier_rejected"
    assert summary["results"][0]["mutation_failed"] is True


def test_failures_only_json_excludes_pure_skips(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["make_target_existing"]])
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["skipped_incompatible_repo"] == 1
    assert summary["results"] == []


def test_summary_accounting_separates_skips_and_executed(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    scenarios = [rcv.SCENARIO_BY_ID["benign_readme_edit"], rcv.SCENARIO_BY_ID["make_target_existing"]]
    monkeypatch.setattr(rcv, "SCENARIOS", scenarios)
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=False, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["passed"] == summary["executed_passed"]
    assert summary["executed_passed"] + summary["executed_failed"] == summary["executed_runs"]
    assert summary["executed_runs"] + summary["skipped_runs"] == summary["total_runs"]
    assert summary["skipped_runs"] == 1


def test_failure_rows_expose_inspection_fields(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True, reason=None))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (1, "{}", "", True, {"verdict":"FAIL","findings":[{"id":"unsupported_dependency"}]}, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    row = rcv.run_harness(args)[0]["results"][0]
    assert row["scenario_id"] and row["actual_verdict"] and row["actual_reason_codes"]
    assert isinstance(row["mutation_result"], dict)
    assert any(row[m] for m in rcv.FAILURE_METRICS)


def test_allowed_alternates_cannot_suppress_hard_failures():
    alt = ({"verdict":"PASS", "justification":"narrow"},)
    for sid, metric in [("execution_claim_without_ledger", "trust_violation"), ("policy_allow_nonmatching_dependency", "policy_over_suppression")]:
        s = rcv.SCENARIO_BY_ID[sid]
        s = rcv.Scenario(s.scenario_id, s.description, s.applies_to_tags, s.required_files, s.target_heuristic, s.mutation, s.expected_verdict, s.expected_reason_codes_include, s.expected_reason_codes_exclude, alt)
        assert rcv.classify(s, "PASS", [], False, False, False, rcv.MutationResult("applied", True))[metric]
    s = rcv.Scenario("x", "", (), (), "", "", "PASS", allowed_alternate_outcomes=alt)
    for kwargs, metric in [((True, False, False), "invalid_json"), ((False, True, False), "crash"), ((False, False, True), "timeout")]:
        assert rcv.classify(s, "PASS", [], *kwargs, rcv.MutationResult("applied", True))[metric]
    for status, metric in [("mutation_failed", "mutation_failed"), ("baseline_failed", "baseline_failed"), ("repo_cleanup_failed", "repo_cleanup_failed")]:
        assert rcv.classify(s, "PASS", [], False, False, False, rcv.MutationResult(status, False))[metric]


def test_policy_nonmatching_cannot_pass_if_unrelated_finding_disappears():
    flags = rcv.classify(rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"], "PASS", ["policy_override"], False, False, False, rcv.MutationResult("applied", True))
    assert flags["policy_over_suppression"]


def test_execution_without_ledger_cannot_pass_without_trust_violation():
    flags = rcv.classify(rcv.SCENARIO_BY_ID["execution_claim_without_ledger"], "PASS", [], False, False, False, rcv.MutationResult("applied", True))
    assert flags["trust_violation"]


def test_execution_claim_with_successful_ledger_records_setup_details(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"])
    assert {"ledger_command", "ledger_exit_code", "ledger_stdout", "ledger_stderr"} <= set(mr.details)


def test_validate_mutation_result_rejects_invalid_states(tmp_path):
    repo = make_repo(tmp_path)
    scenario = rcv.SCENARIO_BY_ID["benign_readme_edit"]
    mr = rcv.MutationResult("applied", True, str(repo / "README.md"), "same", "same")
    assert rcv.validate_mutation_result(repo, scenario, mr).reason == "sha256_unchanged"
    js = rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"]
    mr = rcv.MutationResult("applied", True, details={"dependency_preexisting": True, "dependency_added":"a", "import_specifier":"a"})
    assert rcv.validate_mutation_result(repo, js, mr).reason == "js_package_json_missing"
    mr = rcv.MutationResult("applied", True, details={"dependency_added":"a", "import_specifier":"b"})
    assert rcv.validate_mutation_result(repo, js, mr).reason == "js_package_json_missing"
    pol = rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"]
    mr = rcv.MutationResult("applied", True, details={"policy_exit_code": 1})
    assert rcv.validate_mutation_result(repo, pol, mr).reason == "policy_setup_failed"
    led = rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"]
    mr = rcv.MutationResult("applied", True, details={"ledger_exit_code": 1})
    assert rcv.validate_mutation_result(repo, led, mr).reason == "execution_ledger_setup_failed"
    dock = rcv.SCENARIO_BY_ID["docker_compose_missing_file"]
    mr = rcv.MutationResult("applied", True, details={"compose_files_remaining": ["compose.yml"]})
    assert rcv.validate_mutation_result(repo, dock, mr).reason == "compose_readme_missing"


@pytest.mark.parametrize("mr", [
    rcv.MutationResult("applied", False),
    rcv.MutationResult("mutation_failed", True),
])
def test_validate_mutation_result_rejects_status_applied_inconsistency(tmp_path, mr):
    repo = make_repo(tmp_path)
    scenario = rcv.SCENARIO_BY_ID["benign_readme_edit"]
    result = rcv.validate_mutation_result(repo, scenario, mr)
    assert result.status == "mutation_failed"
    assert result.reason == "mutation_status_applied_inconsistent"


@pytest.mark.parametrize("mr", [
    rcv.MutationResult("applied", False),
    rcv.MutationResult("mutation_failed", True),
])
def test_inconsistent_mutation_state_is_explicit_metric(tmp_path, monkeypatch, mr):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: mr)
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (_ for _ in ()).throw(AssertionError("evaluate must not run")))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    row = summary["results"][0]
    assert row["mutation_result"]["reason"] == "mutation_status_applied_inconsistent"
    assert row["mutation_failed"] is True
    assert row["mutation_status_applied_inconsistent"] is True
    assert summary["mutation_failed"] == 1
    assert summary["mutation_status_applied_inconsistent"] == 1


def _verify_reason(repo, sid, mr):
    return rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).reason


def _valid_js_mutation(tmp_path):
    repo = make_repo(tmp_path, node=True)
    sid = "same_patch_js_dependency_add_plus_import"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    return repo, sid, mr.details.copy()


@pytest.mark.parametrize("mutate, expected", [
    (lambda repo, good: ({k: v for k, v in good.items() if k != "dependency_added"}), "js_dependency_added_missing"),
    (lambda repo, good: (good | {"dependency_added": ""}), "js_dependency_added_missing"),
    (lambda repo, good: (good | {"dependency_added": "lodash", "import_specifier": "lodash"}), "js_dependency_candidate_invalid"),
    (lambda repo, good: (good | {"dependency_added": "react", "import_specifier": "react"}), "js_dependency_candidate_invalid"),
    (lambda repo, good: (good | {"existing_dependency_sections": {"dependencies": [good["dependency_added"]]}}), "js_dependency_preexisting"),
])
def test_hostile_js_verifier_rejects_dependency_metadata_in_check_order(tmp_path, mutate, expected):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = mutate(repo, good)
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == expected


def test_hostile_js_verifier_rejects_missing_dependency_in_package_json(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    data = json.loads((repo / "package.json").read_text())
    data["dependencies"].pop(good["dependency_added"])
    (repo / "package.json").write_text(json.dumps(data))
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=good)) == "js_dependency_not_added_to_dependencies"


@pytest.mark.parametrize("value", [True, None])
def test_hostile_js_verifier_rejects_dependency_preexisting_flag_invalid(tmp_path, value):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"dependency_preexisting": value}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_dependency_preexisting_flag_invalid"


def test_hostile_js_verifier_rejects_import_specifier_mismatch(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"import_specifier": "other"}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_import_specifier_mismatch"


@pytest.mark.parametrize("source", [
    "// import x from 'sourcepack-corpus-js-dep';\n",
    "/* import x from 'sourcepack-corpus-js-dep'; */\n",
    "const msg = 'sourcepack-corpus-js-dep';\n",
    "const msg = \"import x from 'sourcepack-corpus-js-dep';\";\n",
    "const msg = \"require('sourcepack-corpus-js-dep')\";\n",
    "const msg = \"import('sourcepack-corpus-js-dep')\";\n",
    "console.log('sourcepack-corpus-js-dep');\n",
    "import x from 'other'; const msg = \"from 'sourcepack-corpus-js-dep'\";\n",
])
def test_hostile_js_verifier_rejects_non_import_dependency_mentions(tmp_path, source):
    repo, sid, good = _valid_js_mutation(tmp_path)
    (repo / "index.js").write_text(source.replace("sourcepack-corpus-js-dep", good["dependency_added"]))
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=good)) == "js_source_import_missing"


def test_hostile_js_verifier_rejects_package_json_unchanged_sha(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"package_json_after_sha256": good["package_json_before_sha256"]}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_package_json_unchanged"


def test_hostile_js_verifier_rejects_source_unchanged_sha(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"source_after_sha256": good["source_before_sha256"]}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_source_unchanged"

def test_hostile_python_verifier_rejects_lies_and_accepts_valid(tmp_path):
    repo = make_repo(tmp_path)
    sid = "same_patch_python_dependency_add_plus_import"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    good = mr.details.copy()
    (repo / "requirements.txt").write_text("requests\n# fastapi\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"app.py"), "a", "b", details=good)) == "python_dependency_not_in_manifest"
    (repo / "requirements.txt").write_text("requests\nfastapi\n")
    (repo / "app.py").write_text("print('missing')\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"app.py"), "a", "b", details=good)) == "python_import_missing"


def test_hostile_docker_verifier_rejects_lies_and_accepts_valid(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "compose.yml").write_text("services: {}\n")
    sid = "docker_compose_missing_file"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    good = mr.details.copy()
    (repo / "compose.yml").write_text("services: {}\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=good)) == "compose_files_still_present"
    (repo / "compose.yml").unlink()
    bad = good.copy(); bad.pop("deleted_compose_files")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=bad)) == "compose_deletion_provenance_missing"
    (repo / "README.md").write_text("no command\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=good)) == "compose_command_missing"


def test_hostile_policy_and_execution_verifiers(tmp_path):
    repo = make_repo(tmp_path)
    pol = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"], pol).status == "applied"
    (repo / ".sourcepack" / "policy" / "allow.jsonl").unlink()
    assert _verify_reason(repo, "policy_allow_matching_dependency", pol) == "policy_artifact_missing"
    (tmp_path / "n").mkdir()
    repo2 = make_repo(tmp_path / "n")
    non = rcv.apply_mutation(repo2, rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"])
    (repo2 / "app.py").write_text("import fastapi\n")
    assert _verify_reason(repo2, "policy_allow_nonmatching_dependency", non) == "policy_imports_missing"
    (tmp_path / "e").mkdir()
    repo3 = make_repo(tmp_path / "e")
    led = rcv.apply_mutation(repo3, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"])
    assert rcv.verify_scenario_state(repo3, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"], led).status == "applied"
    (repo3 / ".sourcepack" / "evidence" / "ledger.jsonl").unlink()
    assert _verify_reason(repo3, "execution_claim_with_successful_ledger", led) == "execution_ledger_artifact_missing"
    no = rcv.MutationResult("applied", True, str(repo3 / "README.md"), "a", "b")
    (repo3 / "README.md").write_text("no claim\n")
    assert _verify_reason(repo3, "execution_claim_without_ledger", no) == "execution_claim_missing"


def test_programmatic_and_generic_verifier_rejects_lies(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.MutationResult("applied", True, details={})
    assert _verify_reason(repo, "malformed_diff", mr) == "programmatic_patch_text_missing"
    same = rcv.MutationResult("applied", True, str(repo / "README.md"), "same", "same")
    assert _verify_reason(repo, "benign_readme_edit", same) == "sha256_unchanged"
