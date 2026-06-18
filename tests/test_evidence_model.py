import json
from sourcepack.evidence import EvidenceClass, attach_evidence_to_finding, can_satisfy, evidence_summary, make_evidence
from sourcepack.reports.json import traffic_report, write_user_report


def test_advisory_evidence_cannot_satisfy_trusted_requirements():
    assert not can_satisfy(make_evidence("prompt_context", ".sourcepack/prompt/prompt.md"), "trusted_baseline")
    assert not can_satisfy(make_evidence("ai_answer", "answer.md"), "execution_ledger", claim="local_execution")


def test_execution_ledger_supports_local_execution_only():
    ev = make_evidence("execution_ledger", ".sourcepack/evidence/ledger.jsonl")
    assert can_satisfy(ev, EvidenceClass.EXECUTION_LEDGER, claim="local_execution")
    assert not can_satisfy(ev, EvidenceClass.EXECUTION_LEDGER, claim="semantic_correctness")


def test_unsupported_and_not_checked_do_not_become_trusted():
    assert not can_satisfy(make_evidence("unsupported", "Cargo.toml"), "trusted_baseline")
    assert not can_satisfy(make_evidence("not_checked", "security"), "trusted_baseline")


def test_report_includes_evidence_class_fields_and_json_schema():
    finding = attach_evidence_to_finding({"id":"no_diff","severity":"info","category":"diff","message":"ok"}, "trusted_baseline", ".sourcepack/baseline")
    report = traffic_report("PASS", findings=[finding], checked_categories=["baseline"])
    assert report["schema_version"] == "traffic_report.v1"
    assert report["evidence"]["schema_version"] == "sourcepack.evidence.v1"
    assert report["findings"][0]["evidence_class"] == "trusted_baseline"
    json.dumps(report)


def test_html_markdown_generation_failures_do_not_alter_verdict(tmp_path, monkeypatch):
    import sourcepack.reports.json as reports_json
    monkeypatch.setattr(reports_json, "render_report_html", lambda report: (_ for _ in ()).throw(RuntimeError("boom")))
    report = traffic_report("WARN", findings=[])
    write_user_report(tmp_path, report, "x")
    saved = json.loads((tmp_path/".sourcepack/reports/latest.json").read_text())
    assert saved["verdict"] == "WARN"


def test_evidence_summary_buckets():
    summary = evidence_summary([make_evidence("prompt_context", "prompt"), make_evidence("not_checked", "security", "not_checked"), make_evidence("dependency_manifest", "pyproject.toml")])
    assert summary["advisory_evidence_ignored_for_enforcement"]
    assert summary["not_checked"]
    assert summary["checked_evidence"]
