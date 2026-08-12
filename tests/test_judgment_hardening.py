from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import symlink_or_skip

from sourcepack import judgment
from tests.simulation_helpers import multi_patch, write_packet


def test_run_git_missing_executable_returns_127(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("sourcepack.git._bounded_process", fake_run)

    cp = judgment.run_git(tmp_path, ["status"])

    assert cp.returncode == judgment.GIT_RETURNCODE_NOT_FOUND
    assert cp.stdout == ""
    assert cp.stderr == "git executable not found"


def test_run_git_timeout_returns_124(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(["git", "status"], judgment.GIT_RETURNCODE_TIMEOUT, b"partial out", b"partial err\ngit command timed out after 10 seconds")

    monkeypatch.setattr("sourcepack.git._bounded_process", fake_run)

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

    def fake_run_git(repo_arg: Path, args: list[str], *, text: bool):
        assert text is False
        if args == ["ls-files", "--others", "--exclude-standard", "-z", "--", "."]:
            return subprocess.CompletedProcess(["git", *args], 0, b"../evil.txt\0safe.txt\0", b"")
        assert args == ["ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", ".sourcepack"]
        return subprocess.CompletedProcess(["git", *args], 0, b"", b"")

    monkeypatch.setattr(judgment, "canonical_run_git_bounded", fake_run_git)

    diff, authority = judgment.untracked_files_as_diff(repo, with_authority=True)

    assert "evil.txt" not in diff
    assert "../" not in diff
    assert authority["complete"] is False
    assert authority["reason"] == "unsafe_git_path"


def test_untracked_filename_inventory_obeys_git_producer_limit(monkeypatch, tmp_path):
    def bounded(repo_arg: Path, args: list[str], *, text: bool):
        return subprocess.CompletedProcess(["git", *args], judgment.GIT_RETURNCODE_OUTPUT_LIMIT, b"partial", b"limit")

    monkeypatch.setattr(judgment, "canonical_run_git_bounded", bounded)

    diff, authority = judgment.untracked_files_as_diff(tmp_path, with_authority=True)

    assert diff == ""
    assert authority == {"status": "incomplete", "complete": False, "reason": "git_output_limit", "acquisition_state": "bounded"}


def test_untracked_symlink_is_not_followed_and_uses_symlink_mode(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("must not be read\n", encoding="utf-8")
    symlink_or_skip(repo / "linked path", outside)

    diff = judgment.untracked_files_as_diff(repo)
    changes = judgment.parse_unified_diff(diff)

    assert "new file mode 120000" in diff
    assert "must not be read" not in diff
    assert str(outside) in diff
    assert changes[0].path == "linked path"
    assert changes[0].new_mode == "120000"


@pytest.mark.skipif(os.name != "posix", reason="host filesystem cannot represent newline path components")
def test_untracked_filename_with_newline_round_trips(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    name = "line one\nline two.txt"
    (repo / name).write_text("safe\n", encoding="utf-8")

    changes = judgment.parse_unified_diff(judgment.untracked_files_as_diff(repo))

    assert [change.path for change in changes] == [name]


def test_untracked_symlink_target_with_newline_round_trips(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    target = "first\nsecond"
    symlink_or_skip(repo / "link", target)

    changes = judgment.parse_unified_diff(judgment.untracked_files_as_diff(repo))

    assert changes[0].new_mode == "120000"
    assert changes[0].proposed_symlink_target == target


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


def test_path_allow_cannot_suppress_symlink_collision(tmp_path):
    policy_dir = tmp_path / ".sourcepack" / "policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "allow.jsonl").write_text(
        '{"id":"allow-books","scope":"path","value":"books_out","reason":"reviewed"}\n',
        encoding="utf-8",
    )
    finding = judgment.normalized_finding(
        "symlink_replaces_nonempty_directory", "error", "diff", "collision", path="books_out"
    )
    report = judgment.traffic_report("FAIL", findings=[finding])

    result = judgment._apply_local_policy(tmp_path, report)

    assert result["verdict"] == "FAIL"
    assert any(item["id"] == "symlink_replaces_nonempty_directory" for item in result["findings"])


def test_malformed_allow_ledger_fails_closed(tmp_path):
    policy_dir = tmp_path / ".sourcepack" / "policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "allow.jsonl").write_text("not-json\n", encoding="utf-8")
    finding = judgment.normalized_finding("missing_file", "error", "diff", "missing", path="app.py")
    report = judgment.traffic_report("FAIL", findings=[finding])

    result = judgment._apply_local_policy(tmp_path, report)

    assert result["verdict"] == "FAIL"
    assert result["authority"]["complete"] is False
    assert {item["id"] for item in result["findings"]} >= {"missing_file", "policy_resolution_failed"}


def test_malformed_allow_ledger_blocks_clean_report(tmp_path):
    policy_dir = tmp_path / ".sourcepack" / "policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "allow.jsonl").write_text("not-json\n", encoding="utf-8")

    result = judgment._apply_local_policy(tmp_path, judgment.traffic_report("PASS", findings=[]))

    assert result["verdict"] == "FAIL"
    assert result["authority"]["complete"] is False
    assert [item["id"] for item in result["findings"]] == ["policy_resolution_failed"]


def test_current_packet_xml_round_trips_xml_invalid_control_character(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "control.txt").write_text("before\x01after\n", encoding="utf-8")
    packet = tmp_path / "packet"
    judgment.PacketWriter(packet, judgment.SourceScanner(repo).scan()).write_all()

    contents = judgment._packet_file_contents(packet)

    assert contents["control.txt"] == "before\x01after\n"


def test_packet_loader_rejects_top_level_artifact_symlink(tmp_path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "real.json").write_text("{}", encoding="utf-8")
    symlink_or_skip(packet / "manifest.json", "real.json")

    try:
        judgment.load_manifest(packet)
    except ValueError as exc:
        assert "regular file" in str(exc)
    else:
        raise AssertionError("packet artifact symlink was accepted")


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_legacy_packet_context_accepts_lf_and_crlf_records(tmp_path, newline):
    packet = tmp_path / "packet"
    packet.mkdir()
    context = newline.join(["# SourcePack Context", "", "## File: app.py", "", "Content:", "VALUE = 1", "---", ""])
    (packet / "context.md").write_bytes(context.encode("utf-8"))

    assert judgment._packet_file_contents(packet) == {"app.py": "VALUE = 1"}


@pytest.mark.parametrize(
    ("context", "message"),
    [
        ("# SourcePack Context\n\n## File: app.py\n\nVALUE = 1\n---\n", "malformed legacy packet context record"),
        ("# SourcePack Context\n\n## File: app.py\n\nContent:\nVALUE = 1\n", "malformed legacy packet context terminator"),
    ],
)
def test_legacy_packet_context_rejects_malformed_records(tmp_path, context, message):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "context.md").write_text(context, encoding="utf-8", newline="")

    with pytest.raises(ValueError, match=message):
        judgment._packet_file_contents(packet)


def test_duplicate_inventory_paths_fail_authority(tmp_path):
    packet = write_packet(tmp_path, {"app.py": "print(1)\n"})
    (packet / "file_inventory.json").write_text(
        '{"files":[{"relative_path":"app.py"},{"relative_path":"app.py"}]}', encoding="utf-8"
    )

    authority = judgment._baseline_inventory_from_packet(packet)

    assert authority.status == "failed"
    assert authority.reason and "duplicate inventory path" in authority.reason


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
        if args == ["diff", "--", "."]:
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


def test_canonical_binary_diff_path_helper_handles_spaces():
    patch = """diff --git a/.github/workflows/foo bar.bin b/.github/workflows/foo bar.bin
new file mode 100644
index 0000000..1234567
GIT binary patch
literal 4
"""

    assert judgment._binary_diff_paths_from_patch(patch) == [".github/workflows/foo bar.bin"]


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
        if args == ["diff", "--", "."]:
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


def test_contradictory_root_requirements_do_not_become_repository_support(tmp_path):
    packet = write_packet(
        tmp_path,
        {
            "app.py": "print('baseline')\n",
            "requirements.txt": "requests==2.31.0\n",
            "requirements-prod.txt": "requests==2.32.4\n",
        },
    )
    patch = multi_patch([("app.py", "print('baseline')\n", "import requests\nprint('baseline')\n")])

    report = judgment.judge_patch_text(packet, patch)

    assert report["verdict"] == "WARN"
    assert report["unsupported_dependencies"] == []
    assert any(
        finding.get("id") == "dependency_manifest_uncertain"
        for finding in report.get("uncertainties", [])
    )


def test_specialized_requirement_files_are_additive_not_contradictory(tmp_path):
    for specialized_name in (
        "requirements-dev.txt",
        "requirements-test.txt",
        "requirements-docs.txt",
    ):
        case_root = tmp_path / specialized_name
        case_root.mkdir()
        packet = write_packet(
            case_root,
            {
                "app.py": "print('baseline')\n",
                "requirements.txt": "requests==2.32.4\n",
                specialized_name: "pytest==8.3.5\n",
            },
        )
        patch = multi_patch([("app.py", "print('baseline')\n", "import requests\nprint('baseline')\n")])

        report = judgment.judge_patch_text(packet, patch)

        assert report["verdict"] == "PASS", specialized_name
        assert not any(
            finding.get("id") == "dependency_manifest_uncertain"
            for finding in report.get("uncertainties", [])
        ), specialized_name
