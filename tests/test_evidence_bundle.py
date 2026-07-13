from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path


from sourcepack.cli import run_cli
from sourcepack.decision_ledger import append_event, append_report_events, filter_events, new_event, read_events
from sourcepack.evidence_bundle import BUNDLE_SCHEMA_VERSION, create_bundle, verify_bundle
from sourcepack.overrides import create_override
from sourcepack.reports.json import normalized_finding, traffic_report


def _report() -> dict:
    return traffic_report(
        "FAIL",
        findings=[
            normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"),
            normalized_finding("missing_file", "error", "file", "missing", path="src/missing.py"),
        ],
    )


def _write_report_and_ledger(tmp_path: Path):
    report = _report()
    tmp_path.mkdir(parents=True, exist_ok=True)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    events = append_report_events(ledger, report=report, report_path=report_path, command="test", repo=tmp_path)
    return report, report_path, ledger, events


def test_successful_bundle_creation_deterministic_id_and_chain(tmp_path: Path):
    report, report_path, ledger, events = _write_report_and_ledger(tmp_path)
    fail = filter_events(events, "fail_detected")[0]
    create_override(
        report=report,
        report_path=report_path,
        target_finding_id=fail["data"]["finding_id"],
        target_fail_event_id=fail["event_id"],
        actor="me",
        reason="reviewed",
        scope="local",
        ledger_path=ledger,
        repo=tmp_path,
    )

    first = create_bundle(report_path, ledger, created_at="2026-01-01T00:00:00+00:00")
    second = create_bundle(report_path, ledger, output_path=tmp_path / "other.json", created_at="2027-01-01T00:00:00+00:00")

    assert first["schema_version"] == BUNDLE_SCHEMA_VERSION
    assert first["bundle_id"] == second["bundle_id"]
    assert first["target_report"]["path"] == "report.json"
    assert first["decision_ledger"]["path"] == "ledger.jsonl"
    assert first["events"]["report_created"]["event_type"] == "report_created"
    assert len(first["events"]["fail_detected"]) == 2
    assert len(first["events"]["parent_chain"]) == 1
    assert len(first["events"]["overrides"]) == 1
    assert first["events"]["fail_detected"][0]["data"]["finding"]["severity"] == "error"
    assert first["creation_verification"]["status"] == "PASS"
    assert "verification" not in first
    assert verify_bundle(report_path.with_suffix(".bundle.json"))["status"] == "PASS"


def test_bundle_id_and_report_and_ledger_hash_verification(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    bundle_path = report_path.with_suffix(".bundle.json")
    bundle = create_bundle(report_path, ledger)
    assert verify_bundle(bundle_path)["status"] == "PASS"

    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    data["events"]["fail_detected"] = []
    bundle_path.write_text(json.dumps(data), encoding="utf-8")
    result = verify_bundle(bundle_path)
    assert result["status"] == "FAIL"
    assert "bundle_id_mismatch" in result["reasons"]

    create_bundle(report_path, ledger)
    report_path.write_text("{}", encoding="utf-8")
    result = verify_bundle(bundle_path)
    assert "target_report_hash_mismatch" in result["reasons"]

    report_path.write_text(json.dumps(_report(), sort_keys=True), encoding="utf-8")
    create_bundle(report_path, ledger)
    ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = verify_bundle(bundle_path)
    assert "decision_ledger_hash_mismatch" in result["reasons"]
    assert bundle["decision_ledger"]["sha256"]


def test_report_created_validation_and_missing_report_event(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    bundle_path = report_path.with_suffix(".bundle.json")
    create_bundle(report_path, ledger)
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    data["events"]["report_created"]["event_type"] = "fail_detected"
    data["bundle_id"] = "spkb_invalid"
    bundle_path.write_text(json.dumps(data), encoding="utf-8")
    result = verify_bundle(bundle_path)
    assert "report_created_invalid" in result["reasons"]
    assert "report_created_chain_mismatch" not in result["reasons"]

    ledger.write_text("", encoding="utf-8")
    try:
        create_bundle(report_path, ledger)
        raise AssertionError("expected missing report_created failure")
    except ValueError as exc:
        assert "report_created event is missing" in str(exc)


def test_missing_parent_duplicate_malformed_and_unsupported_bundle(tmp_path: Path):
    _, report_path, ledger, events = _write_report_and_ledger(tmp_path)
    report_event = filter_events(events, "report_created")[0]
    report_event["parent_event_id"] = "missing"
    ledger.write_text(json.dumps(report_event, sort_keys=True) + "\n", encoding="utf-8")
    try:
        create_bundle(report_path, ledger)
        raise AssertionError("expected parent failure")
    except ValueError as exc:
        assert "parent" in str(exc)

    _, report_path, ledger, events = _write_report_and_ledger(tmp_path / "dup")
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(events[0], sort_keys=True) + "\n")
    try:
        create_bundle(report_path, ledger)
        raise AssertionError("expected duplicate failure")
    except ValueError as exc:
        assert "duplicate" in str(exc)

    ledger.write_text("{bad}\n", encoding="utf-8")
    try:
        create_bundle(report_path, ledger)
        raise AssertionError("expected malformed failure")
    except ValueError as exc:
        assert "malformed" in str(exc)

    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert "malformed_bundle" in verify_bundle(bad)["reasons"]
    bad.write_text(json.dumps({"schema_version": "future"}), encoding="utf-8")
    result = verify_bundle(bad)
    assert "unsupported_bundle_schema" in result["reasons"]
    assert "missing_required_field" in result["reasons"]


def test_scanner_manifest_verification_when_available(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    packet = tmp_path / ".sourcepack" / "baseline" / "builds" / "b1" / "packet"
    packet.mkdir(parents=True)
    (packet / "manifest.json").write_text('{"ok": true}\n', encoding="utf-8")
    (tmp_path / ".sourcepack" / "baseline" / "active.json").write_text(
        json.dumps({"active_build_id": "b1", "packet_path": ".sourcepack/baseline/builds/b1/packet"}),
        encoding="utf-8",
    )
    create_bundle(report_path, ledger)
    bundle_path = report_path.with_suffix(".bundle.json")
    assert verify_bundle(bundle_path)["status"] == "PASS"
    (packet / "manifest.json").write_text("changed", encoding="utf-8")
    assert "scanner_manifest_hash_mismatch" in verify_bundle(bundle_path)["reasons"]
    (packet / "manifest.json").unlink()
    assert "scanner_manifest_missing" in verify_bundle(bundle_path)["reasons"]


def test_unresolved_override_relationship_fails_closed(tmp_path: Path):
    report, report_path, ledger, events = _write_report_and_ledger(tmp_path)
    report_event = filter_events(events, "report_created")[0]
    finding_id = report["findings"][0]["finding_id"]
    append_event(
        ledger,
        new_event("override_recorded", command="test", repo=tmp_path, parent_event_id=report_event["event_id"], data={"finding_id": finding_id}),
    )
    try:
        create_bundle(report_path, ledger)
        raise AssertionError("expected unresolved override failure")
    except ValueError as exc:
        assert "override relationship is unresolved" in str(exc)


def test_cli_create_and_verify_json_and_human(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    out = tmp_path / "bundle.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["bundle", "create", str(report_path), "--ledger", str(ledger), "--out", str(out), "--json"])
    assert code == 0
    assert json.loads(buf.getvalue())["creation_verification"]["status"] == "PASS"

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["bundle", "verify", str(out)])
    assert code == 0
    assert "Chain integrity: PASS" in buf.getvalue()
    assert "Artifact verification: PASS" in buf.getvalue()

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["bundle", "verify", str(out), "--json"])
    assert code == 0
    assert json.loads(buf.getvalue())["status"] == "PASS"
