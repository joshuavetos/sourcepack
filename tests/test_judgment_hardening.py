from __future__ import annotations

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
        raise subprocess.TimeoutExpired(cmd=["git", "status"], timeout=10, output="partial out", stderr="partial err")

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
