import json
import subprocess
import sys


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
