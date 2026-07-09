from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from sourcepack.decision_ledger import append_report_events, filter_events, read_events
from sourcepack.overrides import classify_fail_overrides, create_override, override_applies
from sourcepack.reports.json import normalized_finding, traffic_report


def _report():
    return traffic_report("FAIL", findings=[
        normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"),
        normalized_finding("unsupported_command", "error", "command", "missing", evidence="npm run build"),
    ])


def test_cannot_create_override_without_reason(tmp_path: Path):
    report = _report()
    with pytest.raises(ValueError, match="reason"):
        create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=report["findings"][0]["finding_id"], actor="me", reason="", scope="local")


def test_cannot_create_override_without_target(tmp_path: Path):
    with pytest.raises(ValueError, match="target"):
        create_override(report=_report(), report_path=tmp_path / "r.json", target_finding_id="missing", actor="me", reason="reviewed", scope="local")


def test_override_preserves_original_fail_metadata(tmp_path: Path):
    report = _report()
    finding = report["findings"][0]
    override = create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=finding["finding_id"], actor="me", reason="accepted local risk", scope="local")
    assert override["original_verdict"] == "FAIL"
    assert override["original_reason_code"] == finding["id"]
    assert override["actor"] == "me"


def test_expired_override_does_not_apply(tmp_path: Path):
    report = _report()
    override = create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=report["findings"][0]["finding_id"], actor="me", reason="reviewed", scope="local", expires_at="2000-01-01T00:00:00+00:00")
    assert override_applies(override, now=datetime(2026, 1, 1, tzinfo=timezone.utc)) is False


def test_override_recorded_links_to_fail_detected_when_ledger_used(tmp_path: Path):
    report = _report()
    report_path = tmp_path / "r.json"
    report_path.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    fail_event = filter_events(append_report_events(ledger, report=report, report_path=report_path, command="report", repo=tmp_path), "fail_detected")[0]
    create_override(report=report, report_path=report_path, target_finding_id=fail_event["data"]["finding_id"], target_fail_event_id=fail_event["event_id"], actor="me", reason="reviewed", scope="local", ledger_path=ledger, repo=tmp_path)
    events = read_events(ledger).events
    override_event = filter_events(events, "override_recorded")[0]
    assert override_event["parent_event_id"] == fail_event["event_id"]


def test_overridden_and_unoverridden_fails_are_distinguished_without_erasing(tmp_path: Path):
    report = _report()
    override = create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=report["findings"][0]["finding_id"], actor="me", reason="reviewed", scope="local", expires_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    classified = classify_fail_overrides(report, [override])
    assert classified["overridden"] == [report["findings"][0]["finding_id"]]
    assert classified["unoverridden"] == [report["findings"][1]["finding_id"]]
    assert len(report["findings"]) == 2


def test_override_ledger_recording_fails_without_fail_event_id(tmp_path: Path):
    report = _report()
    with pytest.raises(ValueError, match="target_fail_event_id is required"):
        create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=report["findings"][0]["finding_id"], actor="me", reason="reviewed", scope="local", ledger_path=tmp_path / "ledger.jsonl")


def test_override_ledger_recording_fails_when_fail_event_missing_from_ledger(tmp_path: Path):
    report = _report()
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="not found"):
        create_override(report=report, report_path=tmp_path / "r.json", target_finding_id=report["findings"][0]["finding_id"], target_fail_event_id="spke_missing", actor="me", reason="reviewed", scope="local", ledger_path=ledger)


def test_override_ledger_recording_fails_when_fail_event_finding_id_mismatches(tmp_path: Path):
    report = _report()
    report_path = tmp_path / "r.json"
    report_path.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    fail_event = filter_events(append_report_events(ledger, report=report, report_path=report_path, command="report", repo=tmp_path), "fail_detected")[0]
    other_finding_id = report["findings"][1]["finding_id"]
    with pytest.raises(ValueError, match="does not match"):
        create_override(report=report, report_path=report_path, target_finding_id=other_finding_id, target_fail_event_id=fail_event["event_id"], actor="me", reason="reviewed", scope="local", ledger_path=ledger, repo=tmp_path)
