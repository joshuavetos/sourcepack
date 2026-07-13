from __future__ import annotations

import os
import subprocess
from pathlib import Path

from sourcepack import judgment
from tests.simulation_helpers import multi_patch, write_packet


def test_run_git_missing_executable_returns_127(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(judgment.subprocess, "run", fake_run)

    cp = judgment.run_git(tmp_path, ["status"])

    assert cp.returncode == judgment.GIT_RETURNCODE_NOT_FOUND
    assert cp.stdout == ""
    assert cp.stderr == "git executable not found"


def test_run_git_timeout_returns_124(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["git", "status"], timeout=10, output=b"partial out", stderr=b"partial err")

    monkeypatch.setattr(judgment.subprocess, "run", fake_run)

    cp = judgment.run_git(tmp_path, ["status"])

    assert cp.returncode == judgment.GIT_RETURNCODE_TIMEOUT
    assert cp.stdout == "partial out"
    assert "partial err" in cp.stderr
    assert "git command timed out after 10 seconds" in cp.stderr


def test_git_worktree_dirty_reports_git_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(
        judgment,
        "run_git",
        lambda repo, args: subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_TIMEOUT, "", "timeout"),
    )

    dirty, state = judgment.git_worktree_dirty(tmp_path)

    assert dirty is False
    assert state == "git_timeout"


def test_malformed_parser_sentinel_fails_closed(monkeypatch, tmp_path):
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n"})
    sentinel = judgment.PatchFileChange(path="", old_path=None, operation="malformed")
    monkeypatch.setattr(judgment, "parse_unified_diff", lambda patch_text: [sentinel])

    report = judgment.judge_patch_text(packet, "not a real diff\n")

    assert report["verdict"] == "FAIL"
    assert report["malformed_diff"] is True
    assert report["modified_files"] == []


def test_unsafe_untracked_file_paths_are_not_emitted(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "safe.txt").write_text("safe\n", encoding="utf-8")

    def fake_run_git(repo_arg: Path, args: list[str]):
        assert args == ["ls-files", "--others", "--exclude-standard"]
        return subprocess.CompletedProcess(["git", *args], 0, "../evil.txt\nsafe.txt\n", "")

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    diff = judgment.untracked_files_as_diff(repo)

    assert "evil.txt" not in diff
    assert "../" not in diff
    assert "diff --git a/safe.txt b/safe.txt" in diff


def test_same_patch_declared_dependency_is_review_not_unsupported(tmp_path):
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "requirements.txt": ""})
    patch = multi_patch(
        [
            ("app.py", "VALUE = 1\n", "import requests\nVALUE = 1\n"),
            ("requirements.txt", "", "requests>=2\n"),
        ]
    )

    report = judgment.judge_patch_text(packet, patch)

    assert "requests" not in report["unsupported_dependencies"]
    assert report["verdict"] == "WARN"
    assert "Patch declares new dependencies that require review." in report["warnings"]
    assert "requests" in report["declared_dependencies"]
    assert any(item.get("id") == "declared_dependency" for item in report.get("uncertainties", []))


def test_build_repo_change_report_initial_git_timeout(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        assert args == ["rev-parse", "--show-toplevel"]
        return subprocess.CompletedProcess(
            ["git", "rev-parse", "--show-toplevel"],
            judgment.GIT_RETURNCODE_TIMEOUT,
            "",
            "timeout",
        )

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    report = judgment.build_repo_change_report(tmp_path)
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_timeout" in finding_ids
    assert "no_git_repo" not in finding_ids


def test_build_repo_change_report_later_git_diff_timeout_fails(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(["git", *args], 0, str(tmp_path), "")
        if args == ["diff"]:
            return subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_TIMEOUT, "", "timeout")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    report = judgment.build_repo_change_report(tmp_path)
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_timeout" in finding_ids
    assert "no_diff" not in finding_ids


def test_tracked_file_inventory_marks_unsafe_git_paths(monkeypatch, tmp_path):
    def fake_run_git_bytes(repo, args):
        assert args == ["ls-files", "-z"]
        return subprocess.CompletedProcess(["git", "ls-files", "-z"], 0, b"../evil.py\0safe.py\0", b"")

    monkeypatch.setattr(judgment, "run_git_bytes", fake_run_git_bytes)
    (tmp_path / "safe.py").write_text("print('safe')\n", encoding="utf-8")

    inventory = judgment._tracked_file_inventory(tmp_path, [{"relative_path": "safe.py"}])
    by_path = {item["relative_path"]: item for item in inventory["files"]}

    assert by_path["../evil.py"]["file_type"] == "unsafe_path"
    assert by_path["../evil.py"]["included_in_prompt_context"] is False
    assert by_path["safe.py"]["included_in_prompt_context"] is True
    assert by_path["safe.py"]["file_type"] == "text"


def test_tracked_file_inventory_preserves_non_utf8_git_paths(monkeypatch, tmp_path):
    if os.name != "posix":
        return

    raw_name = b"bad_\xff.py"
    rel_name = os.fsdecode(raw_name)

    def fake_run_git_bytes(repo, args):
        assert args == ["ls-files", "-z"]
        return subprocess.CompletedProcess(["git", "ls-files", "-z"], 0, raw_name + b"\0", b"")

    monkeypatch.setattr(judgment, "run_git_bytes", fake_run_git_bytes)
    (tmp_path / rel_name).write_text("print('bad bytes')\n", encoding="utf-8")

    inventory = judgment._tracked_file_inventory(tmp_path, [{"relative_path": rel_name}])

    assert inventory["source"] == "git_ls_files"
    assert inventory["files"][0]["relative_path"] == rel_name
    assert inventory["files"][0]["included_in_prompt_context"] is True


def test_git_binary_patch_high_risk_path_with_spaces_blocks(tmp_path):
    packet = write_packet(tmp_path, {"README.md": "demo\n"})
    patch = """diff --git a/.github/workflows/foo bar.bin b/.github/workflows/foo bar.bin
new file mode 100644
index 0000000..1234567
GIT binary patch
literal 4
"""

    report = judgment.judge_patch_text(packet, patch)
    traffic = judgment.patch_report_to_traffic(report)
    finding_ids = {finding.get("id") for finding in traffic.get("findings", [])}

    assert ".github/workflows/foo bar.bin" in report["binary_diffs"]
    assert ".github/workflows/foo bar.bin" in report["binary_diff_blockers"]
    assert report["verdict"] == "FAIL"
    assert "binary_diff" in finding_ids


def test_git_binary_patch_ordinary_path_without_spaces_warns(tmp_path):
    packet = write_packet(tmp_path, {"README.md": "demo\n"})
    patch = """diff --git a/assets/logo.bin b/assets/logo.bin
new file mode 100644
index 0000000..1234567
GIT binary patch
literal 4
"""

    report = judgment.judge_patch_text(packet, patch)

    assert report["binary_diffs"] == ["assets/logo.bin"]
    assert "binary_diff_blockers" not in report
    assert report["verdict"] == "WARN"


def test_binary_files_path_with_spaces_is_preserved(tmp_path):
    packet = write_packet(tmp_path, {"README.md": "demo\n"})
    patch = """diff --git a/assets/foo bar.bin b/assets/foo bar.bin
Binary files a/assets/foo bar.bin and b/assets/foo bar.bin differ
"""

    report = judgment.judge_patch_text(packet, patch)

    assert report["binary_diffs"] == ["assets/foo bar.bin"]
    assert "binary_diff_blockers" not in report


def test_cli_binary_diff_path_helper_matches_judgment_for_spaces():
    from sourcepack import cli

    patch = """diff --git a/.github/workflows/foo bar.bin b/.github/workflows/foo bar.bin
new file mode 100644
index 0000000..1234567
GIT binary patch
literal 4
"""

    assert cli._binary_diff_paths_from_patch(patch) == judgment._binary_diff_paths_from_patch(patch)
    assert cli._binary_diff_paths_from_patch(patch) == [".github/workflows/foo bar.bin"]


def test_build_repo_change_report_initial_git_os_error_is_not_no_git_repo(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        assert args == ["rev-parse", "--show-toplevel"]
        return subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_OS_ERROR, "", "permission denied")

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    report = judgment.build_repo_change_report(tmp_path)
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_diff_failed" in finding_ids
    assert "no_git_repo" not in finding_ids


def test_build_repo_change_report_later_git_diff_os_error_is_not_baseline_failed(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(["git", *args], 0, str(tmp_path), "")
        if args == ["diff"]:
            return subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_OS_ERROR, "", "permission denied")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    report = judgment.build_repo_change_report(tmp_path)
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_diff_failed" in finding_ids
    assert "baseline_failed" not in finding_ids


def test_build_repo_change_report_invalid_ref_pair_stays_git_diff_failed(tmp_path):
    report = judgment.build_repo_change_report(tmp_path, base_ref="HEAD")
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_diff_failed" in finding_ids
    assert "baseline_failed" not in finding_ids


def test_build_repo_change_report_initial_missing_git_remains_git_unavailable(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        assert args == ["rev-parse", "--show-toplevel"]
        return subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_NOT_FOUND, "", "missing")

    monkeypatch.setattr(judgment, "run_git", fake_run_git)

    report = judgment.build_repo_change_report(tmp_path)
    finding_ids = {finding.get("id") for finding in report.get("findings", [])}

    assert report["verdict"] == "FAIL"
    assert "git_unavailable" in finding_ids
    assert "no_git_repo" not in finding_ids

# Evidence bundle tests
import contextlib as _sp_contextlib
import io as _sp_io
import json as _sp_json
from pathlib import Path as _SpPath

from sourcepack.decision_ledger import append_report_events as _sp_append_report_events, filter_events as _sp_filter_events
from sourcepack.overrides import create_override as _sp_create_override
from sourcepack.reports.json import normalized_finding as _sp_normalized_finding, traffic_report as _sp_traffic_report
from sourcepack.cli import BUNDLE_SCHEMA_VERSION as _SP_BUNDLE_SCHEMA_VERSION, create_bundle as _sp_create_bundle, verify_bundle as _sp_verify_bundle, run_cli as _sp_run_cli


def _sp_bundle_report_and_ledger(tmp_path: _SpPath):
    report = _sp_traffic_report("FAIL", findings=[
        _sp_normalized_finding("unsupported_dependency", "error", "dependency", "missing", evidence="requests"),
        _sp_normalized_finding("missing_file", "error", "file", "missing", path="src/missing.py"),
    ])
    tmp_path.mkdir(parents=True, exist_ok=True)
    report_path = tmp_path / "report.json"
    report_path.write_text(_sp_json.dumps(report, sort_keys=True), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    events = _sp_append_report_events(ledger, report=report, report_path=report_path, command="test", repo=tmp_path)
    return report, report_path, ledger, events


def test_evidence_bundle_creation_deterministic_id_events_and_override(tmp_path: _SpPath):
    report, report_path, ledger, events = _sp_bundle_report_and_ledger(tmp_path)
    fail = _sp_filter_events(events, "fail_detected")[0]
    _sp_create_override(report=report, report_path=report_path, target_finding_id=fail["data"]["finding_id"], target_fail_event_id=fail["event_id"], actor="me", reason="reviewed", scope="local", ledger_path=ledger, repo=tmp_path)
    a = _sp_create_bundle(report_path, ledger, created_at="2026-01-01T00:00:00+00:00")
    b = _sp_create_bundle(report_path, ledger, output_path=tmp_path / "other.json", created_at="2027-01-01T00:00:00+00:00")
    assert a["schema_version"] == _SP_BUNDLE_SCHEMA_VERSION
    assert a["bundle_id"] == b["bundle_id"]
    assert a["events"]["report_created"]["event_type"] == "report_created"
    assert len(a["events"]["fail_detected"]) == 2
    assert len(a["events"]["parent_chain"]) == 1
    assert len(a["events"]["overrides"]) == 1
    assert a["events"]["fail_detected"][0]["data"]["finding"]["severity"] == "error"
    assert a["verification"]["status"] == "PASS"


def test_evidence_bundle_verifies_hash_malformed_unsupported_and_duplicate(tmp_path: _SpPath):
    _, report_path, ledger, events = _sp_bundle_report_and_ledger(tmp_path)
    _sp_create_bundle(report_path, ledger)
    path = report_path.with_suffix(".bundle.json")
    assert _sp_verify_bundle(path)["status"] == "PASS"
    report_path.write_text("{}", encoding="utf-8")
    assert "target_report_hash_mismatch" in _sp_verify_bundle(path)["reasons"]
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert "malformed_bundle" in _sp_verify_bundle(bad)["reasons"]
    bad.write_text(_sp_json.dumps({"schema_version": "future"}), encoding="utf-8")
    assert "unsupported_bundle_schema" in _sp_verify_bundle(bad)["reasons"]
    report, report_path, ledger, events = _sp_bundle_report_and_ledger(tmp_path / "dup")
    report_path.parent.mkdir(exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(_sp_json.dumps(events[0], sort_keys=True) + "\n")
    try:
        _sp_create_bundle(report_path, ledger)
        raise AssertionError("expected failure")
    except ValueError as exc:
        assert "duplicate" in str(exc)


def test_evidence_bundle_scanner_manifest_and_cli_routing(tmp_path: _SpPath):
    _, report_path, ledger, _ = _sp_bundle_report_and_ledger(tmp_path)
    packet = tmp_path / ".sourcepack" / "baseline" / "builds" / "b1" / "packet"
    packet.mkdir(parents=True)
    (packet / "manifest.json").write_text('{"ok": true}\n', encoding="utf-8")
    (tmp_path / ".sourcepack" / "baseline" / "active.json").write_text(_sp_json.dumps({"active_build_id": "b1", "packet_path": ".sourcepack/baseline/builds/b1/packet"}), encoding="utf-8")
    out = tmp_path / "bundle.json"
    buf = _sp_io.StringIO()
    with _sp_contextlib.redirect_stdout(buf):
        code = _sp_run_cli(["bundle", "create", str(report_path), "--ledger", str(ledger), "--out", str(out), "--json"])
    assert code == 0
    assert _sp_json.loads(buf.getvalue())["scanner_manifest"]["sha256"]
    assert _sp_verify_bundle(out)["status"] == "PASS"
    (packet / "manifest.json").write_text("changed", encoding="utf-8")
    assert "scanner_manifest_hash_mismatch" in _sp_verify_bundle(out)["reasons"]
    buf = _sp_io.StringIO()
    with _sp_contextlib.redirect_stdout(buf):
        code = _sp_run_cli(["bundle", "verify", str(out)])
    assert code == 1
    assert "Artifact verification: FAIL" in buf.getvalue()
    buf = _sp_io.StringIO()
    with _sp_contextlib.redirect_stdout(buf):
        code = _sp_run_cli(["bundle", "verify", str(out), "--json"])
    assert code == 1
    assert "scanner_manifest_hash_mismatch" in _sp_json.loads(buf.getvalue())["reasons"]
