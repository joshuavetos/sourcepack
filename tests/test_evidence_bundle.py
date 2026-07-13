from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path


from sourcepack.cli import run_cli
from sourcepack.decision_ledger import append_event, append_report_events, filter_events, new_event, read_events, artifact_for
from sourcepack.evidence_bundle import BUNDLE_SCHEMA_VERSION, compute_bundle_id, create_bundle, verify_bundle
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
    assert len(first["events"]["parent_chain"]) == 0
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



def _rewrite_bundle(path: Path, data: dict) -> None:
    data["bundle_id"] = compute_bundle_id(data)
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def test_bundle_id_ignores_absolute_repository_root(tmp_path: Path):
    ids = []
    for repo in (tmp_path / "repo-a", tmp_path / "repo-b"):
        repo.mkdir()
        report = _report()
        report_path = repo / "report.json"
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        ledger = repo / "ledger.jsonl"
        report_event = new_event(
            "report_created",
            command="test",
            repo=repo,
            artifact={"path": str(report_path), "sha256": artifact_for(report_path)["sha256"], "schema_version": report["schema_version"]},
            created_at="2026-01-01T00:00:00+00:00",
            data={"verdict": "FAIL"},
        )
        report_event["event_id"] = "spke_report_same"
        append_event(ledger, report_event)
        for index, finding in enumerate(report["findings"], start=1):
            fail = new_event(
                "fail_detected",
                command="test",
                repo=repo,
                artifact={"path": str(report_path), "sha256": artifact_for(report_path)["sha256"], "schema_version": report["schema_version"]},
                parent_event_id=report_event["event_id"],
                created_at="2026-01-01T00:00:00+00:00",
                data={"finding_id": finding["finding_id"], "reason_code": finding["id"], "finding": finding},
            )
            fail["event_id"] = f"spke_fail_same_{index}"
            append_event(ledger, fail)
        ids.append(create_bundle(report_path, ledger)["bundle_id"])
    assert ids[0] == ids[1]


def test_unrelated_override_for_other_report_does_not_block_creation(tmp_path: Path):
    report_a, report_a_path, ledger, _ = _write_report_and_ledger(tmp_path)
    report_b = traffic_report(
        "FAIL",
        findings=[normalized_finding("unsupported_command", "error", "command", "missing", evidence="bundle-verify")],
    )
    report_b_path = tmp_path / "report-b.json"
    report_b_path.write_text(json.dumps(report_b, sort_keys=True), encoding="utf-8")
    events_b = append_report_events(ledger, report=report_b, report_path=report_b_path, command="test", repo=tmp_path)
    fail_b = filter_events(events_b, "fail_detected")[0]
    create_override(
        report=report_b,
        report_path=report_b_path,
        target_finding_id=fail_b["data"]["finding_id"],
        target_fail_event_id=fail_b["event_id"],
        actor="me",
        reason="reviewed other report",
        scope="local",
        ledger_path=ledger,
        repo=tmp_path,
    )
    bundle = create_bundle(report_a_path, ledger)
    assert bundle["events"]["overrides"] == []
    assert verify_bundle(report_a_path.with_suffix(".bundle.json"))["status"] == "PASS"


def test_verifier_requires_embedded_events_to_match_referenced_ledger(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    bundle_path = report_path.with_suffix(".bundle.json")
    create_bundle(report_path, ledger)
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    data["events"]["fail_detected"][0]["event_id"] = "spke_missing_from_ledger"
    _rewrite_bundle(bundle_path, data)
    assert "ledger_event_missing" in verify_bundle(bundle_path)["reasons"]

    create_bundle(report_path, ledger)
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    data["events"]["fail_detected"][0]["data"]["reason_code"] = "tampered"
    _rewrite_bundle(bundle_path, data)
    assert "ledger_event_mismatch" in verify_bundle(bundle_path)["reasons"]

    create_bundle(report_path, ledger)
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data["events"]["report_created"], sort_keys=True) + "\n")
    data["decision_ledger"]["sha256"] = artifact_for(ledger)["sha256"]
    _rewrite_bundle(bundle_path, data)
    assert "ledger_event_duplicate" in verify_bundle(bundle_path)["reasons"]


def test_verification_summaries_fail_for_missing_artifacts_and_invalid_chain(tmp_path: Path):
    _, report_path, ledger, _ = _write_report_and_ledger(tmp_path)
    bundle_path = report_path.with_suffix(".bundle.json")
    create_bundle(report_path, ledger)
    report_path.unlink()
    result = verify_bundle(bundle_path)
    assert "target_report_missing" in result["reasons"]
    assert result["artifact_verification"] == "FAIL"

    report, report_path, ledger, _ = _write_report_and_ledger(tmp_path / "chain")
    create_bundle(report_path, ledger)
    bundle_path = report_path.with_suffix(".bundle.json")
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    data["events"]["report_created"]["event_type"] = "fail_detected"
    _rewrite_bundle(bundle_path, data)
    result = verify_bundle(bundle_path)
    assert "report_created_invalid" in result["reasons"]
    assert result["chain_integrity"] == "FAIL"
