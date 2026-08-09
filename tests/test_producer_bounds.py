import json
from copy import deepcopy
from pathlib import Path

import pytest

from sourcepack.command_center import build_command_center_snapshot
from sourcepack.policy import POLICY_FILE_LIMIT_BYTES, resolve_effective_policy
from sourcepack.git import GIT_RETURNCODE_OUTPUT_LIMIT, run_git_bounded
from sourcepack import baseline, git as git_module, judgment, packet
from sourcepack.packet import SourceScanner
from sourcepack.reports.json import REPORT_FINDING_LIMIT, traffic_report, validate_report_construction_metadata
from sourcepack.workbench import (
    CANONICAL_REPORT_COLLECTION_LIMIT,
    CANONICAL_REPORT_FILE_LIMIT_BYTES,
    CANONICAL_REPORT_NESTING_LIMIT,
    DECISION_LEDGER_BYTE_LIMIT,
    DECISION_LEDGER_LINE_LIMIT_BYTES,
    DECISION_LEDGER_RECORD_LIMIT,
    _dashboard_payload,
    _read_canonical_report,
    _read_decision_ledger,
    validate_decision_completeness,
)


def _latest(tmp_path: Path) -> Path:
    path = tmp_path / ".sourcepack" / "reports" / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _record() -> bytes:
    return json.dumps({"data": {}}, separators=(",", ":")).encode() + b"\n"


def test_git_diff_producer_stops_at_byte_limit(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "bounds@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Bounds"], cwd=tmp_path, check=True)
    target = tmp_path / "large.txt"
    target.write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "large.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    target.write_text("b\n" * 4096, encoding="utf-8")

    cp = run_git_bounded(tmp_path, ["diff"], output_limit_bytes=1024)

    assert cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT
    assert cp.acquisition_state == "bounded"
    assert len(cp.stdout.encode()) <= 1024
    assert "producer limit" in cp.stderr
    assert run_git_bounded(tmp_path, ["status", "--porcelain"]).acquisition_state == "complete"
    assert run_git_bounded(tmp_path, ["not-a-command"]).acquisition_state == "failed"


def test_repository_entry_limit_is_deterministic_incomplete_authority(tmp_path: Path):
    for name in reversed(["a.py", "b.py", "c.py"]):
        (tmp_path / name).write_text(name, encoding="utf-8")
    scanner = SourceScanner(tmp_path, trust_git_tracked=False, max_entries=2).scan()
    assert scanner.authority == {"status": "incomplete", "complete": False, "reason": "repository_entry_limit"}
    assert scanner.included_files == []


def test_repository_depth_and_read_limits_are_explicit(tmp_path: Path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "deep.py").write_text("x", encoding="utf-8")
    depth = SourceScanner(tmp_path, trust_git_tracked=False, max_depth=1).scan()
    assert depth.authority["reason"] == "repository_depth_limit"

    (tmp_path / "large.py").write_text("x" * 20, encoding="utf-8")
    read = SourceScanner(tmp_path, trust_git_tracked=False, max_total_read_bytes=10).scan()
    assert read.authority == {"status": "incomplete", "complete": False, "reason": "repository_read_limit"}


def test_bounded_tracked_paths_cannot_fall_back_to_complete_scan_or_baseline(monkeypatch, tmp_path: Path):
    import subprocess

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    def bounded(_root, args):
        return subprocess.CompletedProcess(["git", *args], GIT_RETURNCODE_OUTPUT_LIMIT, b"app.py\0", b"bounded")

    monkeypatch.setattr(git_module, "run_git_bytes", bounded)
    scanner = SourceScanner(tmp_path).scan()
    assert scanner.authority == {"status": "incomplete", "complete": False, "reason": "git_output_limit"}
    assert scanner.included_files == []
    with pytest.raises(RuntimeError, match="git_output_limit"):
        baseline._write_baseline_packet(tmp_path, tmp_path / "packet")


def test_bounded_base_tree_is_fail_with_incomplete_authority(monkeypatch, tmp_path: Path):
    def fake_git(_repo, args):
        import subprocess
        if args == ["rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(["git", *args], 0, str(tmp_path), "")
        if args == ["diff", "--binary", "base...head", "--", "."]:
            return subprocess.CompletedProcess(["git", *args], 0, "", "")
        if args == ["ls-tree", "-r", "--name-only", "base", "--", "."]:
            return subprocess.CompletedProcess(["git", *args], GIT_RETURNCODE_OUTPUT_LIMIT, "partial", "bounded")
        raise AssertionError(args)

    monkeypatch.setattr(judgment, "run_git", fake_git)
    monkeypatch.setattr(judgment, "validate_baseline", lambda _repo: {"state": "present", "packet_path": ".sourcepack/baseline/packet"})
    report = judgment.build_repo_change_report(tmp_path, base_ref="base", head_ref="head")
    assert report["verdict"] == "FAIL"
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "git_output_limit"}
    assert report["construction_bounds"]["git_base_tree"]["acquisition_state"] == "bounded"
    validate_report_construction_metadata(report)


@pytest.mark.parametrize(("reason", "state", "limited"), [("git_output_limit", "bounded", True), ("git_diff_failed", "failed", False)])
def test_git_producer_incomplete_reports_round_trip_canonical_loader(tmp_path: Path, reason: str, state: str, limited: bool):
    report = traffic_report("FAIL", findings=[{"id": "git_diff_failed", "severity": "error", "category": "git", "message": "incomplete"}])
    report["authority"] = {"status": "incomplete", "complete": False, "reason": reason}
    report["construction_bounds"]["git_untracked"] = {
        "count_state": "lower_bound", "source_exhausted": False,
        "limit_reached": limited, "acquisition_state": state,
    }
    report["replay_bundle"]["authority"] = report["authority"]
    report["replay_bundle"]["construction_bounds"] = report["construction_bounds"]
    validate_report_construction_metadata(report)
    _latest(tmp_path).write_text(json.dumps(report), encoding="utf-8")
    loaded, error = _read_canonical_report(tmp_path)
    assert error is None
    assert loaded == report


def _findings(count: int, *, blocker_at: int | None = None):
    for index in range(count):
        blocker = index == blocker_at
        yield {
            "id": "missing_file" if blocker else "no_diff",
            "severity": "error" if blocker else "info",
            "category": "file" if blocker else "diff",
            "message": str(index),
        }


def test_report_limit_is_explicit_incomplete_authority_and_counts_are_distinct():
    report = traffic_report("PASS", findings=_findings(REPORT_FINDING_LIMIT + 100))
    assert report["verdict"] == "WARN"
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "finding_construction_limit"}
    assert report["construction_bounds"]["findings"] == {
        "count_state": "lower_bound",
        "source_consumed_count": REPORT_FINDING_LIMIT + 1,
        "source_retained_count": REPORT_FINDING_LIMIT,
        "canonical_emitted_count": REPORT_FINDING_LIMIT + 1,
        "source_exhausted": False,
        "total_count": None,
        "limit_reached": True,
        "source_retention_limit": REPORT_FINDING_LIMIT,
    }
    assert report["replay_bundle"]["authority"] == report["authority"]
    assert report["replay_bundle"]["construction_bounds"] == report["construction_bounds"]


def test_report_limit_retains_fail_but_never_claims_complete():
    report = traffic_report("FAIL", findings=_findings(REPORT_FINDING_LIMIT + 1, blocker_at=0))
    assert report["verdict"] == "FAIL"
    assert report["blockers"]
    assert report["authority"]["complete"] is False


def test_exact_report_counts_and_deterministic_serialization():
    first = traffic_report("PASS", findings=list(_findings(3)))
    second = traffic_report("PASS", findings=list(_findings(3)))
    bounds = first["construction_bounds"]["findings"]
    assert bounds["count_state"] == "exact"
    assert bounds["source_consumed_count"] == bounds["source_retained_count"] == bounds["canonical_emitted_count"] == bounds["total_count"] == 3
    assert bounds["source_exhausted"] is True
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_report_count_validator_rejects_inconsistent_metadata():
    report = traffic_report("PASS", findings=list(_findings(3)))
    for field, bad in (("source_consumed_count", 4), ("source_retained_count", 2), ("canonical_emitted_count", 2), ("total_count", None)):
        candidate = deepcopy(report)
        candidate["construction_bounds"]["findings"][field] = bad
        with pytest.raises(ValueError):
            validate_report_construction_metadata(candidate)
    limited = traffic_report("PASS", findings=_findings(REPORT_FINDING_LIMIT + 1))
    limited["verdict"] = "PASS"
    with pytest.raises(ValueError):
        validate_report_construction_metadata(limited)


def test_canonical_report_loader_byte_and_structure_boundaries(tmp_path: Path):
    path = _latest(tmp_path)
    prefix = b'{"schema_version":"traffic_report.v1","verdict":"PASS"}'
    path.write_bytes(prefix + b" " * (CANONICAL_REPORT_FILE_LIMIT_BYTES - len(prefix)))
    assert _read_canonical_report(tmp_path)[1] is None
    path.write_bytes(b" " * (CANONICAL_REPORT_FILE_LIMIT_BYTES + 1))
    assert _read_canonical_report(tmp_path)[1]["error"]["code"] == "artifact_limit_exceeded"

    hostile = {"schema_version": "traffic_report.v1", "verdict": "PASS", "items": [0] * (CANONICAL_REPORT_COLLECTION_LIMIT + 1)}
    path.write_text(json.dumps(hostile), encoding="utf-8")
    report, error = _read_canonical_report(tmp_path)
    assert report is None and error["status"] == "incomplete"
    nested = "x"
    for _ in range(CANONICAL_REPORT_NESTING_LIMIT + 2):
        nested = [nested]
    path.write_text(json.dumps({"schema_version": "traffic_report.v1", "verdict": "PASS", "nested": nested}), encoding="utf-8")
    assert _read_canonical_report(tmp_path)[0] is None


def test_command_center_preserves_incomplete_report_state(tmp_path: Path):
    report = traffic_report("PASS", findings=_findings(REPORT_FINDING_LIMIT + 1))
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _: {"state": "present"},
        policy_reader=lambda _: {"resolution_status": "PASS"},
        git_reader=lambda _: {},
        status_reader=lambda _: {"status": {}},
        report_reader=lambda _: (report, None),
    )
    assert snapshot["state"]["report"] == "incomplete"
    assert snapshot["state"]["overall"] == "degraded"
    assert snapshot["state"]["replay"] == "degraded"
    assert "incomplete" in snapshot["activity"][3]["message"]
    assert next(item for item in snapshot["available_artifacts"] if item["id"] == "report")["available"] is False
    review = next(item for item in snapshot["capabilities"] if item["id"] == "review")
    assert review["status"] == "PARTIAL"


@pytest.mark.parametrize(
    ("report", "expected_state", "expected_verdict"),
    [
        (traffic_report("PASS", findings=[]), "available", "PASS"),
        (traffic_report("PASS", findings=_findings(REPORT_FINDING_LIMIT + 1)), "incomplete", "WARN"),
        (traffic_report("FAIL", findings=_findings(REPORT_FINDING_LIMIT + 1, blocker_at=0)), "incomplete", "FAIL"),
    ],
)
def test_dashboard_overview_preserves_report_authority(tmp_path: Path, report: dict, expected_state: str, expected_verdict: str):
    _latest(tmp_path).write_text(json.dumps(report), encoding="utf-8")
    overview = _dashboard_payload(tmp_path, "overview")
    assert overview["report_status"] == expected_state
    assert overview["report_verdict"] == expected_verdict


def test_dashboard_overview_missing_malformed_and_oversized_states(tmp_path: Path):
    assert _dashboard_payload(tmp_path, "overview")["report_status"] == "empty"
    path = _latest(tmp_path)
    path.write_text("{", encoding="utf-8")
    assert _dashboard_payload(tmp_path, "overview")["report_status"] == "error"
    path.write_bytes(b" " * (CANONICAL_REPORT_FILE_LIMIT_BYTES + 1))
    assert _dashboard_payload(tmp_path, "overview")["report_status"] == "incomplete"


def test_replay_evidence_preserves_incomplete_authority_and_bounds(tmp_path: Path):
    report = traffic_report("PASS", findings=_findings(REPORT_FINDING_LIMIT + 1))
    _latest(tmp_path).write_text(json.dumps(report), encoding="utf-8")
    payload = _dashboard_payload(tmp_path, "replay-evidence")
    assert payload["status"] == "incomplete"
    assert payload["authority"] == report["authority"]
    assert payload["construction_bounds"] == report["construction_bounds"]
    assert payload["replay"]["authority"]["complete"] is False
    overrides = _dashboard_payload(tmp_path, "overrides")
    assert overrides["status"] == "incomplete"
    assert overrides["report_authority"] == report["authority"]
    assert overrides["report_construction_bounds"] == report["construction_bounds"]


@pytest.mark.parametrize("suffix", [b"", b"\n\n", b" \t\n\r\n"])
def test_ledger_exact_record_limit_with_only_whitespace_is_exact(tmp_path: Path, suffix: bytes):
    ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(_record() * DECISION_LEDGER_RECORD_LIMIT + suffix)
    first = _dashboard_payload(tmp_path, "overrides")
    second = _dashboard_payload(tmp_path, "overrides")
    assert first == second
    assert first["completeness"] == {
        "count_state": "exact", "observed_count": 512, "nonblank_records_consumed": 512,
        "records_retained": 512, "source_exhausted": True, "total_count": 512,
        "limit_reached": False, "retention_limit": 512,
    }


def test_ledger_513th_record_is_lower_bound_and_malformed_lookahead_is_malformed(tmp_path: Path):
    ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(_record() * (DECISION_LEDGER_RECORD_LIMIT + 1))
    limited = _dashboard_payload(tmp_path, "overrides")
    assert limited["status"] == "incomplete"
    assert limited["limit_category"] == "ledger_record_limit"
    assert limited["completeness"]["observed_count"] == 513
    assert limited["completeness"]["nonblank_records_consumed"] == 513
    assert limited["completeness"]["records_retained"] == 512
    assert limited["completeness"]["source_exhausted"] is False
    ledger.write_bytes(_record() * DECISION_LEDGER_RECORD_LIMIT + b"not-json\n")
    malformed = _dashboard_payload(tmp_path, "overrides")
    assert malformed["error"]["code"] == "artifact_malformed"
    assert "completeness" not in malformed


def test_decision_count_validator_rejects_inconsistent_metadata(tmp_path: Path):
    ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(_record() * DECISION_LEDGER_RECORD_LIMIT)
    exact = _dashboard_payload(tmp_path, "overrides")["completeness"]
    for field, value in (("nonblank_records_consumed", 511), ("records_retained", 511), ("source_exhausted", False), ("total_count", None), ("retention_limit", 511)):
        candidate = {**exact, field: value}
        with pytest.raises(ValueError):
            validate_decision_completeness(candidate)


def _command_center_decisions_available(tmp_path: Path) -> bool:
    snapshot = build_command_center_snapshot(
        tmp_path,
        baseline_reader=lambda _: {"state": "present"},
        policy_reader=lambda _: {"resolution_status": "PASS"},
        git_reader=lambda _: {},
        status_reader=lambda _: {"status": {}},
        report_reader=lambda _: (None, None),
    )
    return next(item["available"] for item in snapshot["available_artifacts"] if item["id"] == "decisions")


def test_command_center_decision_availability_requires_existing_complete_ledger(tmp_path: Path):
    ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    absent = _dashboard_payload(tmp_path, "overrides")
    assert absent["ledger_available"] is False
    assert absent["ledger_complete"] is True
    assert absent["completeness"]["total_count"] == 0
    assert _command_center_decisions_available(tmp_path) is False

    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b"")
    empty = _dashboard_payload(tmp_path, "overrides")
    assert empty["ledger_available"] is True
    assert empty["ledger_complete"] is True
    assert _command_center_decisions_available(tmp_path) is True

    ledger.write_bytes(_record())
    assert _command_center_decisions_available(tmp_path) is True

    ledger.write_bytes(_record() * (DECISION_LEDGER_RECORD_LIMIT + 1))
    bounded = _dashboard_payload(tmp_path, "overrides")
    assert bounded["ledger_available"] is True
    assert bounded["ledger_complete"] is False
    assert _command_center_decisions_available(tmp_path) is False

    ledger.write_bytes(b"not-json\n")
    assert _command_center_decisions_available(tmp_path) is False


class CountingReader:
    def __init__(self, raw):
        self.raw = raw
        self.bytes_read = 0
        self.requests = []

    def read(self, size=-1):
        self.requests.append(("read", size))
        value = self.raw.read(size)
        self.bytes_read += len(value)
        return value

    def readline(self, size=-1):
        self.requests.append(("readline", size))
        value = self.raw.readline(size)
        self.bytes_read += len(value)
        return value


def test_ledger_actual_reads_stop_at_total_budget_plus_probe(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    path.write_bytes((b" \n" * (DECISION_LEDGER_BYTE_LIMIT // 2)) + b"x")
    with path.open("rb") as raw:
        reader = CountingReader(raw)
        _, error, observed, measured = _read_decision_ledger(reader)
    assert error["limit_category"] == "ledger_total_byte_limit"
    assert error["completeness"]["nonblank_records_consumed"] == 0
    assert error["completeness"]["records_retained"] == 0
    assert error["completeness"]["source_exhausted"] is False
    assert observed == 0
    assert reader.bytes_read == measured == DECISION_LEDGER_BYTE_LIMIT + 1
    assert max(size for _, size in reader.requests) <= DECISION_LEDGER_LINE_LIMIT_BYTES + 1


def test_ledger_line_and_total_limits_are_distinct_and_exact_total_succeeds(tmp_path: Path):
    with (tmp_path / "line").open("wb") as out:
        out.write(b"x" * (DECISION_LEDGER_LINE_LIMIT_BYTES + 1))
    with (tmp_path / "line").open("rb") as raw:
        _, line_error, observed, read_count = _read_decision_ledger(CountingReader(raw))
    assert line_error["limit_category"] == "ledger_line_byte_limit"
    assert observed == 0
    assert read_count == DECISION_LEDGER_LINE_LIMIT_BYTES + 1

    exact = tmp_path / "exact"
    exact.write_bytes(b" \n" * (DECISION_LEDGER_BYTE_LIMIT // 2))
    with exact.open("rb") as raw:
        _, error, observed, read_count = _read_decision_ledger(CountingReader(raw))
    assert error is None and observed == 0 and read_count == DECISION_LEDGER_BYTE_LIMIT


def test_policy_is_strictly_byte_bounded_but_shape_rejection_is_post_parse(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("sourcepack.policy._canonical_repository_root", lambda path: (Path(path), None))
    path = tmp_path / ".sourcepack" / "policy.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b" " * (POLICY_FILE_LIMIT_BYTES + 1))
    policy = resolve_effective_policy(tmp_path)
    assert policy["resolution_status"] == "FAIL"
    assert any("limit_exceeded:file_bytes" in error for error in policy["errors"])


def test_limit_paths_do_not_mutate_repository_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("sourcepack.policy._canonical_repository_root", lambda path: (Path(path), None))
    report_path = _latest(tmp_path)
    report_path.write_bytes(b" " * (CANONICAL_REPORT_FILE_LIMIT_BYTES + 1))
    policy_path = tmp_path / ".sourcepack" / "policy.json"
    policy_path.write_bytes(b" " * (POLICY_FILE_LIMIT_BYTES + 1))
    ledger = tmp_path / ".sourcepack" / "decisions.jsonl"
    ledger.write_bytes(_record() * (DECISION_LEDGER_RECORD_LIMIT + 1))
    before = {path: path.read_bytes() for path in (report_path, policy_path, ledger)}
    _read_canonical_report(tmp_path)
    resolve_effective_policy(tmp_path)
    _dashboard_payload(tmp_path, "overrides")
    assert {path: path.read_bytes() for path in before} == before
    assert not (tmp_path / ".sourcepack" / "baseline").exists()
