from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "pass-clean": ("PASS", []),
    "warn-new-file": ("WARN", ["new_file"]),
    "fail-unsupported-dependency": ("FAIL", ["unsupported_dependency"]),
    "fail-unsupported-command": ("FAIL", ["unsupported_command"]),
    "fail-protected-artifact": ("FAIL", ["protected_artifact"]),
    "trust-boundary": ("WARN", ["new_file"]),
}


def test_golden_demo_runs_and_outputs_expected_summaries() -> None:
    cp = subprocess.run([sys.executable, "tools/golden_demo.py", "--clean"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert cp.returncode == 0, cp.stdout
    output = ROOT / "examples" / "golden" / "output"
    assert output.exists()
    for scenario, (verdict, reasons) in SCENARIOS.items():
        summary_path = output / scenario / "summary.json"
        assert summary_path.exists(), scenario
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["ok"] is True
        assert summary["actual"]["verdict"] == verdict
        for reason in reasons:
            assert reason in summary["actual"]["reasons"]
        assert (output / scenario / "terminal.txt").exists()
        assert (output / scenario / "repo" / ".sourcepack" / "reports" / "latest.html").exists()
        assert (output / scenario / "repo" / ".sourcepack" / "reports" / "latest.json").exists()


def test_product_docs_exist() -> None:
    assert (ROOT / "docs" / "reason-codes.md").exists()
    assert (ROOT / "docs" / "assets" / "README.md").exists()
