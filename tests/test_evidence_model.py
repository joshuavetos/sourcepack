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


def test_canonical_evidence_item_schema_and_stable_id():
    from sourcepack.evidence import make_evidence_item
    item1 = make_evidence_item("missing_file", "trusted_baseline", path="src/missing.py", observed_value="src/missing.py", supports=["missing_file"])
    item2 = make_evidence_item("missing_file", "trusted_baseline", path="src/missing.py", observed_value="src/missing.py", supports=["missing_file"])
    data = item1.to_dict()
    assert item1.evidence_id == item2.evidence_id
    assert set(data) == {"evidence_id", "category", "source_type", "path", "line_start", "line_end", "observed_value", "normalized_value", "supports", "contradicts", "uncertainty", "metadata"}
    assert data["evidence_id"].startswith("ev_")


def test_reason_code_to_evidence_mapping_uses_canonical_codes_and_json_valid():
    report = traffic_report("FAIL", findings=[{"id":"missing_file","severity":"error","category":"file","path":"src/nope.py","message":"missing"}])
    assert list(report["reason_code_evidence"]) == ["missing_file"]
    assert report["evidence_items"][0]["evidence_id"] in report["reason_code_evidence"]["missing_file"]
    assert report["replay_bundle"]["schema_version"] == "sourcepack.replay_bundle.v1"
    json.dumps(report)


def test_replay_bundle_is_deterministic_except_allowed_fields():
    finding = {"id":"unsupported_command","severity":"error","category":"command","message":"bad command","evidence":"npm run madeup"}
    one = traffic_report("FAIL", findings=[finding])["replay_bundle"]
    two = traffic_report("FAIL", findings=[finding])["replay_bundle"]
    one.pop("generated_at", None); two.pop("generated_at", None)
    assert one == two


def test_high_value_categories_link_to_evidence_items():
    findings = [
        {"id":"unsupported_dependency","severity":"error","category":"dependency","message":"dep","evidence":"fastapi"},
        {"id":"unsupported_command","severity":"error","category":"command","message":"cmd","evidence":"npm run x"},
        {"id":"missing_file","severity":"error","category":"file","message":"missing","path":"src/missing.py"},
        {"id":"protected_artifact","severity":"error","category":"artifact","message":"protected","path":".sourcepack/manifest.json","evidence":".sourcepack/manifest.json"},
        {"id":"unsafe_path","severity":"error","category":"diff","message":"unsafe","path":"../x","evidence":"x"},
        {"id":"unsupported_ecosystem","severity":"warn","category":"uncertainty","message":"Cargo.toml detected","evidence":"Cargo.toml"},
    ]
    report = traffic_report("FAIL", findings=findings)
    for code in {"unsupported_dependency", "unsupported_command", "missing_file", "protected_artifact", "unsafe_path", "unsupported_ecosystem"}:
        assert code in report["reason_code_evidence"]
        ev = [i for i in report["evidence_items"] if i["evidence_id"] in report["reason_code_evidence"][code]][0]
        assert ev["supports"] == [code]
    unsafe = [i for i in report["evidence_items"] if i["category"] == "unsafe_path"][0]
    assert unsafe["normalized_value"] == "../x"
