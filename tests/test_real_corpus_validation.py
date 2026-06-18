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
