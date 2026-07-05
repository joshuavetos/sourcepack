from sourcepack.reports.json import normalized_finding, traffic_report


def test_normalized_finding_preserves_fields_and_canonicalizes_id():
    finding = normalized_finding("baseline-missing", "warn", "baseline", "missing", "p", "e", "s")

    assert finding == {
        "id": "baseline_missing",
        "severity": "warn",
        "category": "baseline",
        "path": "p",
        "message": "missing",
        "evidence": "e",
        "suggestion": "s",
    }


def test_normalized_finding_rejects_unknown_error_and_warn_but_allows_info():
    for severity in ("error", "warn"):
        try:
            normalized_finding("not_a_code", severity, "review", "bad")
        except ValueError:
            pass
        else:
            raise AssertionError(f"{severity} severity accepted an unknown reason code")

    finding = normalized_finding("not_a_code", "info", "review", "note")
    assert finding["id"] == "not_a_code"


def test_traffic_report_shape_sorting_and_evidence_fields():
    report = traffic_report(
        "FAIL",
        findings=[
            normalized_finding("new_file", "warn", "review", "new", "b.py"),
            normalized_finding("missing_file", "error", "file", "missing", "a.py"),
            normalized_finding("baseline_inventory_missing", "warn", "uncertainty", "uncertain"),
        ],
        checked_categories=["diff"],
    )

    assert report["schema_version"] == "traffic_report.v1"
    assert report["verdict"] == "FAIL"
    assert report["light"] == "RED LIGHT"
    assert [finding["severity"] for finding in report["findings"]] == ["error", "warn", "warn"]
    assert [finding["id"] for finding in report["blockers"]] == ["missing_file"]
    assert {finding["id"] for finding in report["warnings"]} == {"new_file", "baseline_inventory_missing"}
    assert [finding["id"] for finding in report["uncertainties"]] == ["baseline_inventory_missing"]
    assert "runtime behavior" in report["not_checked"]
    assert "semantic correctness" in report["not_checked"]
    assert "evidence_items" in report
    assert "reason_code_evidence" in report
    assert report["replay_bundle"]["schema_version"] == "sourcepack.replay_bundle.v1"
