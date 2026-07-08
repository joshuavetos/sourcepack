from __future__ import annotations

import json
from pathlib import Path

from sourcepack.fleet import render_human_summary, summarize_reports


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_fleet_summarizes_supported_traffic_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports"

    write_json(
        reports / "repo-a" / "sourcepack.json",
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
        reports / "repo-b" / "sourcepack.json",
        {
            "schema_version": "traffic_report.v1",
            "verdict": "WARN",
            "findings": [
                {
                    "id": "new_file",
                    "severity": "warn",
                    "category": "file",
                    "path": "src/new_feature.py",
                    "message": "src/new_feature.py was created by the patch.",
                    "evidence": "src/new_feature.py",
                    "suggestion": None,
                }
            ],
        },
    )

    summary = summarize_reports(reports)

    assert summary["schema_version"] == "sourcepack.fleet.summary.v1"
    assert summary["coverage"] == {
        "json_files_seen": 2,
        "accepted_reports": 2,
        "unreadable_reports": 0,
        "unknown_schema_reports": 0,
    }
    assert summary["verdict_counts"] == {
        "PASS": 0,
        "WARN": 1,
        "FAIL": 1,
        "UNKNOWN": 0,
    }
    assert summary["schema_versions_seen"] == [
        {"schema_version": "traffic_report.v1", "count": 2}
    ]
    assert summary["reason_code_counts"] == [
        {"schema_version": "traffic_report.v1", "reason_code": "missing_file", "count": 1},
        {"schema_version": "traffic_report.v1", "reason_code": "new_file", "count": 1},
        {"schema_version": "traffic_report.v1", "reason_code": "unsupported_dependency", "count": 1},
    ]
    assert summary["dependency_counts"] == [
        {"schema_version": "traffic_report.v1", "dependency": "fastapi", "count": 1}
    ]
    assert summary["path_counts"] == [
        {"schema_version": "traffic_report.v1", "path": "src/new_feature.py", "count": 1},
        {"schema_version": "traffic_report.v1", "path": "src/server.py", "count": 1},
    ]


def test_fleet_keeps_reason_codes_separate_by_schema_version(tmp_path: Path) -> None:
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
                }
            ],
        },
    )
    write_json(
        reports / "patch.json",
        {
            "schema_version": "patch_judgment_report.v1",
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
                }
            ],
        },
    )

    summary = summarize_reports(reports)

    assert summary["coverage"]["accepted_reports"] == 2
    assert summary["schema_versions_seen"] == [
        {"schema_version": "patch_judgment_report.v1", "count": 1},
        {"schema_version": "traffic_report.v1", "count": 1},
    ]
    assert summary["reason_code_counts"] == [
        {
            "schema_version": "patch_judgment_report.v1",
            "reason_code": "unsupported_dependency",
            "count": 1,
        },
        {
            "schema_version": "traffic_report.v1",
            "reason_code": "unsupported_dependency",
            "count": 1,
        },
    ]
    assert summary["dependency_counts"] == [
        {
            "schema_version": "patch_judgment_report.v1",
            "dependency": "fastapi",
            "count": 1,
        },
        {
            "schema_version": "traffic_report.v1",
            "dependency": "fastapi",
            "count": 1,
        },
    ]


def test_fleet_reports_missing_and_unknown_schema_without_accepting(tmp_path: Path) -> None:
    reports = tmp_path / "reports"

    write_json(
        reports / "accepted.json",
        {
            "schema_version": "traffic_report.v1",
            "verdict": "PASS",
            "findings": [],
        },
    )
    write_json(
        reports / "missing-schema.json",
        {
            "verdict": "FAIL",
            "findings": [],
        },
    )
    write_json(
        reports / "unknown-schema.json",
        {
            "schema_version": "sourcepack.future.report.v99",
            "verdict": "FAIL",
            "findings": [
                {
                    "id": "unsupported_dependency",
                    "severity": "error",
                    "category": "dependency",
                    "path": None,
                    "message": "future schema should not be counted.",
                    "evidence": "futuredep",
                    "suggestion": None,
                }
            ],
        },
    )

    summary = summarize_reports(reports)

    assert summary["coverage"] == {
        "json_files_seen": 3,
        "accepted_reports": 1,
        "unreadable_reports": 0,
        "unknown_schema_reports": 2,
    }
    assert summary["verdict_counts"] == {
        "PASS": 1,
        "WARN": 0,
        "FAIL": 0,
        "UNKNOWN": 0,
    }
    assert summary["reason_code_counts"] == []
    assert summary["dependency_counts"] == []
    assert summary["unknown_schema_reports"] == [
        {
            "path": "missing-schema.json",
            "error": "missing schema_version",
        },
        {
            "path": "unknown-schema.json",
            "schema_version": "sourcepack.future.report.v99",
            "error": "unsupported schema_version",
        },
    ]
    assert summary["schema_versions_seen"] == [
        {"schema_version": "sourcepack.future.report.v99", "count": 1},
        {"schema_version": "traffic_report.v1", "count": 1},
    ]


def test_fleet_reports_malformed_json_as_unreadable_coverage(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "broken.json").write_text("{not json", encoding="utf-8")

    summary = summarize_reports(reports)

    assert summary["coverage"] == {
        "json_files_seen": 1,
        "accepted_reports": 0,
        "unreadable_reports": 1,
        "unknown_schema_reports": 0,
    }
    assert summary["unreadable_reports"][0]["path"] == "broken.json"
    assert "malformed JSON" in summary["unreadable_reports"][0]["error"]


def test_fleet_accepts_single_report_file(tmp_path: Path) -> None:
    report = write_json(
        tmp_path / "sourcepack.json",
        {
            "schema_version": "traffic_report.v1",
            "verdict": "PASS",
            "findings": [],
        },
    )

    summary = summarize_reports(report)

    assert summary["coverage"] == {
        "json_files_seen": 1,
        "accepted_reports": 1,
        "unreadable_reports": 0,
        "unknown_schema_reports": 0,
    }
    assert summary["accepted_report_paths"] == ["sourcepack.json"]
    assert summary["verdict_counts"]["PASS"] == 1


def test_fleet_does_not_infer_dependency_or_path_from_message_or_evidence(tmp_path: Path) -> None:
    reports = tmp_path / "reports"

    write_json(
        reports / "sourcepack.json",
        {
            "schema_version": "traffic_report.v1",
            "verdict": "FAIL",
            "findings": [
                {
                    "id": "unsupported_dependency",
                    "severity": "error",
                    "category": "dependency",
                    "path": None,
                    "message": "fastapi appears in this message and docs/path.py appears too.",
                    "evidence": None,
                    "suggestion": None,
                },
                {
                    "id": "malformed_diff",
                    "severity": "error",
                    "category": "diff",
                    "path": None,
                    "message": "Diff references src/fake.py in prose.",
                    "evidence": "src/fake.py",
                    "suggestion": None,
                },
            ],
        },
    )

    summary = summarize_reports(reports)

    assert summary["reason_code_counts"] == [
        {"schema_version": "traffic_report.v1", "reason_code": "malformed_diff", "count": 1},
        {"schema_version": "traffic_report.v1", "reason_code": "unsupported_dependency", "count": 1},
    ]
    assert summary["dependency_counts"] == []
    assert summary["path_counts"] == []


def test_render_human_summary_surfaces_coverage_and_unknowns(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()

    write_json(
        reports / "accepted.json",
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
                }
            ],
        },
    )
    write_json(
        reports / "unknown.json",
        {
            "schema_version": "future.v1",
            "verdict": "FAIL",
            "findings": [],
        },
    )
    (reports / "broken.json").write_text("{nope", encoding="utf-8")

    summary = summarize_reports(reports)
    rendered = render_human_summary(summary)

    assert "SourcePack fleet summary" in rendered
    assert "JSON files seen: 3" in rendered
    assert "Accepted reports: 1" in rendered
    assert "Unreadable reports: 1" in rendered
    assert "Unknown-schema reports: 1" in rendered
    assert "- FAIL: 1" in rendered
    assert "traffic_report.v1::unsupported_dependency: 1" in rendered
    assert "traffic_report.v1::fastapi: 1" in rendered
    assert "broken.json" in rendered
    assert "unknown.json (future.v1)" in rendered
