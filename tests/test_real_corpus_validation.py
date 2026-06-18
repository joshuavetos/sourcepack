import json, subprocess, sys


def run_tool(*args):
    return subprocess.run([sys.executable, "tools/real_corpus_validation.py", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_no_corpus_json_behavior():
    cp = run_tool("--json")
    assert cp.returncode == 0
    data=json.loads(cp.stdout)
    assert data["status"] == "no_corpus_configured"


def test_local_temp_repo_and_seed_count(tmp_path):
    (tmp_path/"README.md").write_text("x")
    cp = run_tool(str(tmp_path), "--json")
    data=json.loads(cp.stdout)
    assert data["scenario_count"] == 10
    assert len(data["results"]) == 10


def test_threshold_behavior():
    assert run_tool("--json", "--max-false-red", "-1").returncode == 1


def test_unavailable_network_not_product_failure():
    cp = run_tool("--clone-url", "https://example.invalid/repo.git", "--json")
    data=json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["network_status"] == "network_unavailable"
