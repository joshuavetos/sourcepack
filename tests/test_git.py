from __future__ import annotations

import subprocess

from sourcepack import git as git_mod


def _cp(args: list[str], returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git", *args], returncode, stdout, stderr)


def test_run_git_missing_executable_returns_normalized_completed_process(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(git_mod.subprocess, "run", fake_run)

    cp = git_mod.run_git(tmp_path, ["status"])

    assert cp.args == ["git", "status"]
    assert cp.returncode == git_mod.GIT_RETURNCODE_NOT_FOUND
    assert cp.stdout == ""
    assert cp.stderr == "git executable not found"


def test_run_git_timeout_returns_normalized_completed_process_with_partial_output(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["git", "status"],
            timeout=git_mod.GIT_TIMEOUT_SECONDS,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )

    monkeypatch.setattr(git_mod.subprocess, "run", fake_run)

    cp = git_mod.run_git(tmp_path, ["status"])

    assert cp.args == ["git", "status"]
    assert cp.returncode == git_mod.GIT_RETURNCODE_TIMEOUT
    assert cp.stdout == "partial stdout"
    assert cp.stderr == "partial stderr\ngit command timed out after 10 seconds"


def test_dirty_worktree_maps_missing_git_executable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        git_mod,
        "run_git",
        lambda repo, args: _cp(args, git_mod.GIT_RETURNCODE_NOT_FOUND, stderr="git executable not found"),
    )

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is False
    assert state == "git_unavailable"


def test_dirty_worktree_maps_git_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(
        git_mod,
        "run_git",
        lambda repo, args: _cp(args, git_mod.GIT_RETURNCODE_TIMEOUT, stderr="timeout"),
    )

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is False
    assert state == "git_timeout"


def test_dirty_worktree_maps_non_git_repository(monkeypatch, tmp_path):
    monkeypatch.setattr(
        git_mod,
        "run_git",
        lambda repo, args: _cp(args, 128, stderr="fatal: not a git repository"),
    )

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is False
    assert state == "not_git"


def test_dirty_worktree_maps_generic_git_error_after_root_resolution(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return _cp(args, 0, stdout=str(tmp_path))
        if args == ["diff", "--quiet"]:
            return _cp(args, 2, stderr="unexpected git error")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(git_mod, "run_git", fake_run_git)

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is False
    assert state == "git_error"


def test_dirty_worktree_reports_clean_when_all_git_checks_succeed(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return _cp(args, 0, stdout=str(tmp_path))
        if args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
            return _cp(args, 0)
        if args == ["ls-files", "--others", "--exclude-standard"]:
            return _cp(args, 0, stdout="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(git_mod, "run_git", fake_run_git)

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is False
    assert state is None


def test_dirty_worktree_reports_dirty_for_tracked_changes(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return _cp(args, 0, stdout=str(tmp_path))
        if args == ["diff", "--quiet"]:
            return _cp(args, 1)
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(git_mod, "run_git", fake_run_git)

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is True
    assert state is None


def test_dirty_worktree_reports_dirty_for_untracked_files(monkeypatch, tmp_path):
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return _cp(args, 0, stdout=str(tmp_path))
        if args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
            return _cp(args, 0)
        if args == ["ls-files", "--others", "--exclude-standard"]:
            return _cp(args, 0, stdout="new-file.txt\n")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(git_mod, "run_git", fake_run_git)

    dirty, state = git_mod.dirty_worktree(tmp_path)

    assert dirty is True
    assert state is None
