import json

import pytest

from sourcepack.reports import json as reports_json
from sourcepack.reports.json import build_replay_bundle, normalized_finding, traffic_report, write_user_report


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


def test_replay_bundle_is_an_independent_json_snapshot():
    report = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "review", "new", "a.py")])
    replay = build_replay_bundle(report)
    report["findings"][0]["path"] = "changed.py"
    report["authority"]["complete"] = False
    report_warning_path = report["warnings"][0]["path"]
    replay["warnings"][0]["path"] = "bundle-only.py"
    assert replay["findings"][0]["path"] == "a.py"
    assert replay["authority"]["complete"] is True
    assert report["warnings"][0]["path"] == report_warning_path


def test_evidence_id_collision_never_silently_overwrites(monkeypatch):
    monkeypatch.setattr(reports_json, "_finding_evidence_item", lambda finding: {"evidence_id": "same", "category": finding["id"]})
    report = {"findings": [{"id": "a"}, {"id": "b"}]}
    with pytest.raises(ValueError, match="contradictory evidence"):
        build_replay_bundle(report)


def test_write_latest_json_is_atomic_on_replace_failure(tmp_path, monkeypatch):
    report = traffic_report("PASS")
    write_user_report(tmp_path, report)
    latest = tmp_path / ".sourcepack" / "reports" / "latest.json"
    original = latest.read_bytes()
    monkeypatch.setattr(reports_json.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        write_user_report(tmp_path, report)
    assert latest.read_bytes() == original
    assert not list(latest.parent.glob(".*.tmp"))


def test_write_validates_post_construction_authority_mutation(tmp_path):
    report = traffic_report("PASS")
    report["authority"] = {"status": "incomplete", "complete": False, "reason": "invented"}
    with pytest.raises(ValueError, match="explicit producer-incomplete authority"):
        write_user_report(tmp_path, report)
    assert not (tmp_path / ".sourcepack" / "reports" / "latest.json").exists()


def test_validator_rejects_unknown_producer_with_complete_authority():
    report = traffic_report("PASS")
    report["construction_bounds"]["unknown_producer"] = {"source_exhausted": False}
    report["replay_bundle"] = build_replay_bundle(report)
    with pytest.raises(ValueError, match="complete authority"):
        reports_json.validate_report_construction_metadata(report)


def test_validator_rejects_multiple_incomplete_producer_envelopes():
    report = traffic_report("FAIL", findings=[normalized_finding("git_diff_failed", "error", "git", "failed")])
    report["authority"] = {"status": "incomplete", "complete": False, "reason": "git_diff_failed"}
    producer = {"count_state": "lower_bound", "source_exhausted": False, "limit_reached": False, "acquisition_state": "failed"}
    report["construction_bounds"]["git_diff"] = dict(producer)
    report["construction_bounds"]["git_untracked"] = dict(producer)
    report["replay_bundle"] = build_replay_bundle(report)
    with pytest.raises(ValueError, match="explicit producer-incomplete authority"):
        reports_json.validate_report_construction_metadata(report)


def test_validator_rejects_stale_replay_authority():
    report = traffic_report("PASS")
    report["replay_bundle"]["verdict"] = "FAIL"
    with pytest.raises(ValueError, match="replay bundle disagrees"):
        reports_json.validate_report_construction_metadata(report)


def test_accepted_report_serializes():
    report = traffic_report("PASS")
    json.dumps(report)


def test_replay_limit_is_aggregate_not_per_child(monkeypatch):
    report = traffic_report("PASS")
    report["baseline_metadata"] = {"value": "a" * 450}
    report["prompt_context_metadata"] = {"value": "b" * 450}
    monkeypatch.setattr(reports_json, "CANONICAL_REPORT_SNAPSHOT_LIMIT_BYTES", 1200)
    assert len(json.dumps(report["baseline_metadata"], separators=(",", ":")).encode()) < 1200
    assert len(json.dumps(report["prompt_context_metadata"], separators=(",", ":")).encode()) < 1200
    with pytest.raises(ValueError, match="canonical replay bundle exceeds the 1200 byte"):
        build_replay_bundle(report)


def test_bounded_json_snapshot_accepts_exact_boundary_and_rejects_one_over(monkeypatch):
    value = {"value": ""}
    overhead = len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    limit = 128
    monkeypatch.setattr(reports_json, "CANONICAL_REPORT_SNAPSHOT_LIMIT_BYTES", limit)
    value["value"] = "x" * (limit - overhead)
    assert reports_json._bounded_json_snapshot(value) == value
    value["value"] += "x"
    with pytest.raises(ValueError, match="canonical replay bundle exceeds the 128 byte"):
        reports_json._bounded_json_snapshot(value)


def test_oversized_canonical_report_preserves_existing_latest(tmp_path, monkeypatch):
    original = traffic_report("PASS")
    write_user_report(tmp_path, original)
    latest = tmp_path / ".sourcepack" / "reports" / "latest.json"
    previous = latest.read_bytes()

    oversized = traffic_report("PASS")
    oversized["baseline_metadata"] = {"value": "a" * 450}
    oversized["prompt_context_metadata"] = {"value": "b" * 450}
    monkeypatch.setattr(reports_json, "CANONICAL_REPORT_SNAPSHOT_LIMIT_BYTES", 1200)
    with pytest.raises(ValueError, match="canonical replay bundle exceeds the 1200 byte"):
        write_user_report(tmp_path, oversized)
    assert latest.read_bytes() == previous


def test_canonical_report_limit_applies_to_pre_replace_encoded_artifact(tmp_path, monkeypatch):
    report = traffic_report("PASS")
    generated_at = "2026-08-02T00:00:00+00:00"
    monkeypatch.setattr(reports_json, "utc_now", lambda: generated_at)
    replay = build_replay_bundle(report, generated_at=generated_at)
    compact_replay_size = len(json.dumps(replay, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    monkeypatch.setattr(reports_json, "CANONICAL_REPORT_SNAPSHOT_LIMIT_BYTES", compact_replay_size)
    with pytest.raises(ValueError, match="canonical latest.json report exceeds"):
        write_user_report(tmp_path, report)
    assert not (tmp_path / ".sourcepack" / "reports" / "latest.json").exists()
