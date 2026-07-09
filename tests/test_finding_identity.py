from sourcepack.finding_identity import attach_finding_id, finding_id_for
from sourcepack.reports.json import normalized_finding, traffic_report


def test_same_dependency_finding_has_stable_id_across_runs():
    f = normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests")
    assert traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"] == traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"]


def test_same_command_finding_has_stable_id_across_runs():
    f = normalized_finding("unsupported_command", "error", "command", "missing", evidence="npm run build")
    assert traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"] == traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"]


def test_same_path_finding_has_stable_id_across_runs():
    f = normalized_finding("missing_file", "error", "file", "missing", path="src/app.py")
    assert traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"] == traffic_report("FAIL", findings=[f])["findings"][0]["finding_id"]


def test_reordered_findings_do_not_change_ids():
    a = normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests")
    b = normalized_finding("unsupported_command", "error", "command", "missing", evidence="npm run build")
    ids1 = {f["id"]: f["finding_id"] for f in traffic_report("FAIL", findings=[a, b])["findings"]}
    ids2 = {f["id"]: f["finding_id"] for f in traffic_report("FAIL", findings=[b, a])["findings"]}
    assert ids1 == ids2


def test_materially_different_facts_get_different_ids():
    a = attach_finding_id(normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"))
    b = attach_finding_id(normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="flask"))
    assert a["finding_id"] != b["finding_id"]


def test_normalized_finding_remains_backward_compatible_until_report_enrichment():
    assert "finding_id" not in normalized_finding("missing_file", "error", "file", "missing", path="a.py")


def test_same_unsupported_dependency_fact_shares_id_even_when_message_changes():
    a = traffic_report("FAIL", findings=[normalized_finding("unsupported_dependency", "error", "dependency", "first wording", evidence="requests")])["findings"][0]
    b = traffic_report("FAIL", findings=[normalized_finding("unsupported_dependency", "error", "dependency", "second wording", evidence="requests")])["findings"][0]
    assert a["finding_id"] == b["finding_id"]


def test_path_identity_preserves_traversal_tokens_without_laundering():
    a = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "file", "missing", path="src/../secrets.env")])["findings"][0]
    b = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "file", "missing", path="secrets.env")])["findings"][0]
    assert a["finding_id"] != b["finding_id"]


def test_raw_finding_id_matches_report_enriched_finding_id_for_dependency_and_command():
    dep = normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests")
    cmd = normalized_finding("unsupported_command", "error", "command", "missing", evidence="npm run build")
    report = traffic_report("FAIL", findings=[dep, cmd])
    by_reason = {finding["id"]: finding["finding_id"] for finding in report["findings"]}
    assert finding_id_for(dep) == by_reason["unsupported_dependency"]
    assert finding_id_for(cmd) == by_reason["unsupported_command"]
