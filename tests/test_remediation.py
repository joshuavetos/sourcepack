from sourcepack.remediation import REMEDIATION_SCHEMA_VERSION, remediation_for_finding
from sourcepack.reports.json import normalized_finding, traffic_report


def test_remediation_is_derived_from_canonical_finding_fields():
    report = traffic_report(
        "FAIL",
        findings=[
            normalized_finding(
                "unsupported_dependency",
                "error",
                "dependency",
                "app.py imports fastapi, but fastapi is not declared.",
                "app.py",
                "pyproject.toml declares flask",
                "Use a repository-supported dependency.",
            )
        ],
    )

    finding = report["findings"][0]
    remediation = finding["remediation"]

    assert remediation["schema_version"] == REMEDIATION_SCHEMA_VERSION
    assert remediation["finding_id"] == finding["finding_id"]
    assert remediation["reason_code"] == "unsupported_dependency"
    assert remediation["path"] == "app.py"
    assert "fastapi is not declared" in remediation["agent_prompt"]
    assert "pyproject.toml declares flask" in remediation["agent_prompt"]
    assert "Do not modify manifests" in remediation["agent_prompt"]
    assert report["remediation"]["status"] == "available"
    assert report["remediation"]["items"] == [remediation]
    assert report["remediation"]["agent_prompt"] == remediation["agent_prompt"]


def test_remediation_does_not_invent_guidance_for_info_findings():
    finding = {
        "id": "informational",
        "severity": "info",
        "category": "review",
        "message": "note",
    }

    assert remediation_for_finding(finding) is None

    report = traffic_report("PASS", findings=[finding])
    assert "remediation" not in report["findings"][0]
    assert report["remediation"]["status"] == "unavailable"
    assert report["remediation"]["agent_prompt"] == ""


def test_remediation_is_added_after_stable_finding_identity():
    report_a = traffic_report(
        "FAIL",
        findings=[normalized_finding("missing_file", "error", "file", "missing", "ghost.py")],
    )
    report_b = traffic_report(
        "FAIL",
        findings=[normalized_finding("missing_file", "error", "file", "missing", "ghost.py")],
    )

    assert report_a["findings"][0]["finding_id"] == report_b["findings"][0]["finding_id"]
    assert report_a["findings"][0]["remediation"]["finding_id"] == report_a["findings"][0]["finding_id"]
