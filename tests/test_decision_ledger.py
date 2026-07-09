import json
from pathlib import Path

from sourcepack.decision_ledger import append_event, append_report_events, filter_events, follow_parent_chain, missing_parent_event_ids, new_event, read_events, verify_artifact_hash
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
