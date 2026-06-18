from sourcepack.reports.json import traffic_report


def test_confidence_fields_and_limitations():
    report = traffic_report("PASS", checked_categories=["dependency_check", "command_check"])
    assert "checked" in report and "not_checked" in report and "confidence_summary" in report
    text = " ".join(report["confidence_summary"]["limitations"])
    assert "does not prove code correctness" in text
    assert report["verdict"] == "PASS"


def test_unsupported_categories_do_not_disappear():
    finding = {"id":"unsupported_ecosystem", "severity":"warn", "category":"uncertainty", "message":"Cargo"}
    report = traffic_report("WARN", findings=[finding])
    assert report["unsupported_evidence"]
    assert "semantic correctness" in report["not_checked"]
