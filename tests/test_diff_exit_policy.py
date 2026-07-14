from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from sourcepack.cli import emit_diff_report
from sourcepack.reports.json import normalized_finding, traffic_report


def _args(**kwargs):
    defaults = {"ci": False, "json": True, "strict": False, "verbose": False, "exit_policy": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_pass_with_fail_only_exits_zero(capsys):
    assert emit_diff_report(traffic_report("PASS"), _args(exit_policy="fail-only")) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"


def test_warn_with_fail_only_exits_zero_and_preserves_warn_findings(capsys):
    report = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "file", "new", "src/new.py")])
    assert emit_diff_report(report, _args(exit_policy="fail-only")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "WARN"
    assert [f["id"] for f in data["findings"]] == ["new_file"]
    assert data["findings"][0]["path"] == "src/new.py"


def test_fail_with_fail_only_exits_nonzero(capsys):
    report = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "file", "missing", "src/missing.py")])
    assert emit_diff_report(report, _args(exit_policy="fail-only")) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_pass_with_warn_or_fail_exits_zero(capsys):
    assert emit_diff_report(traffic_report("PASS"), _args(exit_policy="warn-or-fail")) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"


def test_warn_with_warn_or_fail_exits_nonzero(capsys):
    report = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "file", "new", "src/new.py")])
    assert emit_diff_report(report, _args(exit_policy="warn-or-fail")) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "WARN"


def test_fail_with_warn_or_fail_exits_nonzero(capsys):
    report = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "file", "missing", "src/missing.py")])
    assert emit_diff_report(report, _args(exit_policy="warn-or-fail")) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_without_exit_policy_preserves_current_ci_warn_behavior(capsys):
    report = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "file", "new", "src/new.py")])
    assert emit_diff_report(report, _args(ci=True)) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "WARN"
    assert data["ci"] is True


def test_ci_fail_only_emits_valid_uncontaminated_json(capsys):
    report = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "file", "new", "src/new.py")])
    assert emit_diff_report(report, _args(ci=True, exit_policy="fail-only")) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert out.lstrip().startswith("{")
    assert data["verdict"] == "WARN"
    assert data["ci"] is True


def _run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_unknown_exit_policy_is_rejected_by_argument_parsing(tmp_path: Path):
    cp = _run_cli(tmp_path, "diff", ".", "--exit-policy", "nope")
    assert cp.returncode == 2
    assert "invalid choice" in cp.stderr
