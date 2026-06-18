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
    assert data["dependencies"]["react"] == "latest"
    assert mr.details["package_json_before_sha256"] != mr.details["package_json_after_sha256"]


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
