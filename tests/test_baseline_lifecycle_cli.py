import json
import subprocess
import sys

from sourcepack.baseline import acquire_baseline_lock, release_baseline_lock


def run_cli(tmp_path,*args):
    return subprocess.run([sys.executable,"-m","sourcepack.cli",*args], cwd=tmp_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_missing_baseline_status_and_json(tmp_path):
    cp=run_cli(tmp_path,"baseline","status","--json")
    assert cp.returncode == 0
    assert json.loads(cp.stdout)["state"] == "missing"

def test_baseline_path_missing(tmp_path):
    assert run_cli(tmp_path,"baseline","path").returncode == 1

def test_reset_safety(tmp_path):
    (tmp_path/"code.py").write_text("x=1")
    assert run_cli(tmp_path,"reset").returncode == 0
    assert (tmp_path/"code.py").exists()


def test_canonical_baseline_lock_contention_reports_baseline_locked(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".sourcepack/\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    lock, fd = acquire_baseline_lock(tmp_path, "test")
    try:
        result = run_cli(tmp_path, "baseline", ".", "--json")
    finally:
        release_baseline_lock(lock, fd)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["verdict"] == "WARN"
    assert [finding["id"] for finding in report["findings"]] == ["baseline_locked"]
