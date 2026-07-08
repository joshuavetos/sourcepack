from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_fleet_cli_fixture(tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    write_json(
        reports / "traffic.json",
        {
            "schema_version": "traffic_report.v1",
            "verdict": "FAIL",
            "findings": [
                {
                    "id": "unsupported_dependency",
                    "severity": "error",
                    "category": "dependency",
                    "path": None,
                    "message": "fastapi is imported but not declared.",
                    "evidence": "fastapi",
                    "suggestion": None,
                },
                {
                    "id": "missing_file",
                    "severity": "error",
                    "category": "file",
                    "path": "src/server.py",
                    "message": "src/server.py not found in the trusted baseline.",
                    "evidence": "src/server.py",
                    "suggestion": None,
                },
            ],
        },
    )
    write_json(
        reports / "unsupported.json",
        {
            "schema_version": "sourcepack.future.report.v1",
            "verdict": "FAIL",
            "findings": [
                {
                    "id": "unsupported_dependency",
                    "category": "dependency",
                    "path": "future.py",
                    "evidence": "futuredep",
                }
            ],
        },
    )
    (reports / "malformed.json").write_text("{not json", encoding="utf-8")
    return reports


def test_fleet_summarize_json_cli_reports_coverage_and_counts(tmp_path: Path) -> None:
    reports = write_fleet_cli_fixture(tmp_path)

    cp = run_cli(tmp_path, "fleet", "summarize", str(reports), "--json")

    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["schema_version"] == "sourcepack.fleet.summary.v1"
    assert data["coverage"] == {
        "json_files_seen": 3,
        "accepted_reports": 1,
        "unreadable_reports": 1,
        "unknown_schema_reports": 1,
    }
    assert data["verdict_counts"] == {
        "PASS": 0,
        "WARN": 0,
        "FAIL": 1,
        "UNKNOWN": 0,
    }
    assert data["reason_code_counts"] == [
        {"schema_version": "traffic_report.v1", "reason_code": "missing_file", "count": 1},
        {"schema_version": "traffic_report.v1", "reason_code": "unsupported_dependency", "count": 1},
    ]
    assert data["dependency_counts"] == [
        {"schema_version": "traffic_report.v1", "dependency": "fastapi", "count": 1}
    ]
    assert data["path_counts"] == [
        {"schema_version": "traffic_report.v1", "path": "src/server.py", "count": 1}
    ]
    assert data["unreadable_reports"][0]["path"] == "malformed.json"
    assert data["unknown_schema_reports"] == [
        {
            "path": "unsupported.json",
            "schema_version": "sourcepack.future.report.v1",
            "error": "unsupported schema_version",
        }
    ]


def test_fleet_summarize_human_cli_surfaces_coverage_and_top_reason_codes(tmp_path: Path) -> None:
    reports = write_fleet_cli_fixture(tmp_path)

    cp = run_cli(tmp_path, "fleet", "summarize", str(reports))

    assert cp.returncode == 0, cp.stderr
    assert "SourcePack fleet summary" in cp.stdout
    assert "Accepted reports: 1" in cp.stdout
    assert "Unreadable reports: 1" in cp.stdout
    assert "Unknown-schema reports: 1" in cp.stdout
    assert "Top reason codes:" in cp.stdout
    assert "traffic_report.v1::unsupported_dependency: 1" in cp.stdout
    assert "traffic_report.v1::missing_file: 1" in cp.stdout
    assert "malformed.json" in cp.stdout
    assert "unsupported.json (sourcepack.future.report.v1)" in cp.stdout
