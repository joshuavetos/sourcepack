import json, subprocess, sys


def run_cli(tmp_path, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=tmp_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_explain_policy_list_allow_remove(tmp_path):
    cp = run_cli(tmp_path, "explain", "unsupported_dependency")
    assert cp.returncode == 0 and "dependency" in cp.stdout
    cp = run_cli(tmp_path, "policy", "list")
    assert cp.returncode == 0 and json.loads(cp.stdout)["policies"] == []
    cp = run_cli(tmp_path, "allow", "dependency", "fastapi", "--reason", "reviewed")
    assert cp.returncode == 0
    pid = json.loads(cp.stdout)["id"]
    assert json.loads(run_cli(tmp_path, "policy", "list").stdout)["policies"][0]["scope"] == "dependency"
    assert run_cli(tmp_path, "policy", "remove", pid).returncode == 0


def test_allow_command_path_and_protected_rules(tmp_path):
    assert run_cli(tmp_path, "allow", "command", "npm run dev", "--reason", "reviewed").returncode == 0
    assert run_cli(tmp_path, "allow", "path", "src/app.py", "--reason", "reviewed").returncode == 0
    assert run_cli(tmp_path, "allow", "path", ".sourcepack/baseline/active.json", "--reason", "x").returncode == 1
    assert run_cli(tmp_path, "allow", "path", ".git/config", "--reason", "x", "--high-risk").returncode == 1
