import contextlib
import io
import json
from pathlib import Path

from sourcepack.cli import run_cli
from sourcepack.decision_ledger import DECISION_LEDGER_EVENT_SCHEMA_VERSION, append_event, append_report_events, filter_events, follow_parent_chain, missing_parent_event_ids, new_event, read_events, verify_artifact_hash
from sourcepack.fleet import render_human_summary, summarize_ledgers, summarize_reports
from sourcepack.reports.json import normalized_finding, traffic_report


def test_append_read_and_filter_events(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    event = new_event("report_created", command="test", repo=tmp_path)
    append_event(ledger, event)
    result = read_events(ledger)
    assert result.events == [event]
    assert filter_events(result.events, "report_created") == [event]


def test_malformed_and_unsupported_lines_are_surfaced(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text('{bad}\n{"schema_version":"future","event_id":"x"}\n', encoding="utf-8")
    result = read_events(ledger)
    assert len(result.malformed_lines) == 1
    assert len(result.unsupported_schema_versions) == 1


def test_parent_chain_and_missing_parent_detection(tmp_path: Path):
    parent = new_event("report_created", command="test", repo=tmp_path)
    child = new_event("fail_detected", command="test", repo=tmp_path, parent_event_id=parent["event_id"])
    chain, missing = follow_parent_chain([parent, child], child["event_id"])
    assert [e["event_id"] for e in chain] == [child["event_id"], parent["event_id"]]
    assert missing == []
    orphan = new_event("fail_detected", command="test", repo=tmp_path, parent_event_id="missing")
    assert missing_parent_event_ids([orphan]) == ["missing"]


def test_artifact_hash_can_be_verified(tmp_path: Path):
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    event = new_event("report_created", command="test", repo=tmp_path, artifact={"path": str(artifact), "sha256": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a", "schema_version": "x"})
    assert verify_artifact_hash(event)["verified"] is True
    artifact.write_text("{ }", encoding="utf-8")
    assert verify_artifact_hash(event)["verified"] is False


def test_fail_detected_is_per_finding(tmp_path: Path):
    report = traffic_report("FAIL", findings=[
        normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"),
        normalized_finding("unsupported_command", "error", "command", "missing", evidence="npm run build"),
        normalized_finding("missing_file", "error", "file", "missing", path="src/missing.py"),
    ])
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    events = append_report_events(ledger, report=report, report_path=report_path, command="test", repo=tmp_path)
    assert [e["event_type"] for e in events].count("fail_detected") == 3
    result = read_events(ledger)
    assert len(filter_events(result.events, "fail_detected")) == 3


def test_read_events_surfaces_supported_schema_missing_required_fields_as_invalid(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text('{"schema_version":"sourcepack.decision_ledger.event.v1"}\n', encoding="utf-8")
    result = read_events(ledger)
    assert result.events == []
    assert len(result.invalid_events) == 1
    assert "missing required field: event_id" in result.invalid_events[0]["errors"]


def test_append_event_refuses_invalid_event_dict(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError, match="invalid decision ledger event"):
        append_event(tmp_path / "ledger.jsonl", {"schema_version": "sourcepack.decision_ledger.event.v1"})


def test_relative_report_artifact_hash_verifies_from_outside_repo(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    report_dir = repo / ".sourcepack" / "reports"
    report_dir.mkdir(parents=True)
    report = traffic_report("FAIL", findings=[normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests")])
    relative_report_path = Path(".sourcepack/reports/latest.json")
    (repo / relative_report_path).write_text(json.dumps(report), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    events = append_report_events(ledger, report=report, report_path=relative_report_path, command="test", repo=repo)
    monkeypatch.chdir(tmp_path)
    assert events[0]["artifact"]["path"] == relative_report_path.as_posix()
    assert events[0]["artifact"]["sha256"]
    assert verify_artifact_hash(events[0])["verified"] is True


def test_fleet_summarizes_decision_ledger_history(tmp_path: Path):
    report = traffic_report("FAIL", findings=[
        normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"),
        normalized_finding("missing_file", "error", "file", "missing", path="src/missing.py"),
    ])
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    ledger_a = tmp_path / "a.jsonl"
    ledger_b = tmp_path / "nested" / "b.jsonl"
    events = append_report_events(ledger_a, report=report, report_path=report_path, command="test", repo=tmp_path)
    append_event(ledger_b, new_event("override_recorded", command="test", repo=tmp_path, parent_event_id=events[0]["event_id"], data={"finding_id": "unsupported_dependency"}))
    append_event(ledger_b, new_event("override_recorded", command="test", repo=tmp_path, parent_event_id="missing-parent", data={"finding_id": "unsupported_dependency"}))
    append_event(ledger_b, new_event("bundle_verified", command="test", repo=tmp_path, parent_event_id="missing-parent"))
    missing_artifact = tmp_path / "missing-report.json"
    append_event(ledger_b, new_event("bundle_created", command="test", repo=tmp_path, artifact={"path": str(missing_artifact), "sha256": "0" * 64, "schema_version": "test"}))
    report_path.write_text("changed", encoding="utf-8")
    with ledger_b.open("a", encoding="utf-8") as fh:
        fh.write("{not json}\n")
        fh.write('{"schema_version":"future","event_id":"x"}\n')
        fh.write(json.dumps({"schema_version": DECISION_LEDGER_EVENT_SCHEMA_VERSION}) + "\n")

    summary = summarize_ledgers(tmp_path)

    assert summary["input_model"] == "decision_ledgers"
    assert summary["coverage"]["jsonl_files_seen"] == 2
    assert summary["coverage"]["accepted_events"] == 7
    assert summary["coverage"]["malformed_lines"] == 1
    assert summary["coverage"]["unsupported_schema_versions"] == 1
    assert summary["coverage"]["invalid_events"] == 1
    assert summary["coverage"]["broken_parent_references"] == 2
    assert summary["coverage"]["unique_missing_parent_ids"] == 1
    assert summary["event_type_counts"] == [
        {"event_type": "bundle_created", "count": 1},
        {"event_type": "bundle_verified", "count": 1},
        {"event_type": "fail_detected", "count": 2},
        {"event_type": "override_recorded", "count": 2},
        {"event_type": "report_created", "count": 1},
    ]
    assert summary["fail_finding_frequencies"] == [
        {"finding_id": report["findings"][0]["finding_id"], "count": 1},
        {"finding_id": report["findings"][1]["finding_id"], "count": 1},
    ]
    assert summary["missing_parent_event_ids"] == ["missing-parent"]
    assert summary["artifact_verification_counts"] == [
        {"status": "artifact missing", "count": 1},
        {"status": "mismatch", "count": 3},
        {"status": "not_provided", "count": 3},
    ]
    human = render_human_summary(summary)
    assert "Input model: decision ledgers" in human
    assert "FAIL finding frequencies:" in human
    assert "Artifact verification:" in human


def test_fleet_summary_schema_uses_symmetric_input_model_discriminator(tmp_path: Path):
    report = traffic_report("PASS")
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert summarize_reports(tmp_path)["input_model"] == "reports"
    assert summarize_ledgers(tmp_path)["input_model"] == "decision_ledgers"


def test_fleet_ledgers_cli_routes_to_ledger_mode(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_event(ledger, new_event("report_created", command="test", repo=tmp_path))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["fleet", "summarize", str(tmp_path), "--input-type", "ledgers", "--json"])

    assert code == 0
    data = json.loads(buf.getvalue())
    assert data["input_model"] == "decision_ledgers"
    assert data["coverage"]["jsonl_files_seen"] == 1
    assert data["event_type_counts"] == [{"event_type": "report_created", "count": 1}]


def test_fleet_directory_discovery_skips_execution_evidence_ledger(tmp_path: Path):
    decision_ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    append_event(decision_ledger, new_event("report_created", command="test", repo=tmp_path))
    evidence_ledger = tmp_path / ".sourcepack" / "evidence" / "ledger.jsonl"
    evidence_ledger.parent.mkdir(parents=True)
    evidence_ledger.write_text(
        json.dumps(
            {
                "schema_version": "sourcepack.exec.evidence.v1",
                "entry_id": "exec-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_ledgers(tmp_path)

    assert summary["coverage"]["jsonl_files_seen"] == 1
    assert summary["coverage"]["unsupported_schema_versions"] == 0
    assert summary["accepted_ledger_paths"] == [".sourcepack/decisions.jsonl"]


def test_fleet_explicit_jsonl_input_is_not_filtered_by_location(tmp_path: Path):
    evidence_ledger = tmp_path / ".sourcepack" / "evidence" / "ledger.jsonl"
    evidence_ledger.parent.mkdir(parents=True)
    evidence_ledger.write_text(
        '{"schema_version":"sourcepack.exec.evidence.v1"}\n',
        encoding="utf-8",
    )

    summary = summarize_ledgers(evidence_ledger)

    assert summary["coverage"]["jsonl_files_seen"] == 1
    assert summary["accepted_ledger_paths"] == ["ledger.jsonl"]
