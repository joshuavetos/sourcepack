import json
import subprocess
import sys


def run(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_repo(tmp_path, files):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return tmp_path


def diff_json(repo):
    cp = run(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def ids(report):
    return {f["id"] for f in report["findings"]}


def test_missing_execution_evidence_changes_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n"})
    (repo / "README.md").write_text("demo\ntests passed\n", encoding="utf-8")
    code, report = diff_json(repo)
    assert code == 0
    assert report["verdict"] == "WARN"
    assert "execution_evidence_missing" in ids(report)
    finding = next(f for f in report["findings"] if f["id"] == "execution_evidence_missing")
    assert finding["evidence_class"] == "execution_ledger"
    assert "execution" in report["partially_checked"] or "execution_claim_check" in report["partially_checked"]


def test_successful_ledger_evidence_changes_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n"})
    cp = run(repo, "exec", "--", "python", "-c", "print('ok')")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    (repo / "README.md").write_text("demo\nI ran python -c print('ok')\n", encoding="utf-8")
    _, report = diff_json(repo)
    assert "execution_evidence_present" in ids(report)
    assert "execution_evidence_missing" not in ids(report)


def test_command_and_dependency_resolvers_affect_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n", "package.json": '{"scripts":{}}\n', "app.py": "print(1)\n"})
    (repo / "README.md").write_text("demo\nnpm run dev\n", encoding="utf-8")
    (repo / "app.py").write_text("print(1)\nimport fastapi\n", encoding="utf-8")
    code, report = diff_json(repo)
    assert code == 1
    assert {"unsupported_command", "unsupported_dependency"} <= ids(report)


def test_prompt_context_cannot_satisfy_enforcement_evidence(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n", ".sourcepack/prompt/context.md": "fastapi is declared and pytest passed\n", "app.py": "print(1)\n"})
    (repo / "app.py").write_text("print(1)\nimport fastapi\n", encoding="utf-8")
    (repo / "README.md").write_text("demo\ntests passed\n", encoding="utf-8")
    _, report = diff_json(repo)
    assert {"unsupported_dependency", "execution_evidence_missing"} <= ids(report)
    assert not any(f.get("evidence_class") == "prompt_context" and f["id"] in {"unsupported_dependency", "execution_evidence_missing"} for f in report["findings"])
