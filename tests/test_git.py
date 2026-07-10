from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path

from sourcepack import baseline, cli, git as git_mod, judgment, packet
from sourcepack.packet import SourceScanner


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


# Phase 1 consolidation regression tests moved from the temporary catch-all file.
def _cp_bytes(args: list[str], returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(["git", *args], returncode, stdout, stderr)


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)


def test_cli_and_judgment_git_wrappers_delegate_to_canonical(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, list[str]]] = []

    def fake_run(repo, args):
        calls.append((Path(repo), list(args)))
        return _cp(args, 0, stdout="ok")

    monkeypatch.setattr(cli, "canonical_run_git", fake_run)
    monkeypatch.setattr(judgment, "canonical_run_git", fake_run)

    assert cli.run_git(tmp_path, ["status"]).stdout == "ok"
    assert judgment.run_git(tmp_path, ["status"]).stdout == "ok"
    assert calls == [(tmp_path, ["status"]), (tmp_path, ["status"])]


def test_packet_tracked_file_discovery_uses_canonical_helper(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("print('untracked')\n", encoding="utf-8")

    monkeypatch.setattr(packet, "git_tracked_paths", lambda root: {"tracked.py"})

    scanner = SourceScanner(tmp_path).scan()

    assert [item.relative_path for item in scanner.included_files] == ["tracked.py"]
    assert {item.relative_path: item.reason for item in scanner.ignored_files}["untracked.py"] == "untracked_file_skipped"


def test_cli_tracked_inventory_uses_canonical_byte_preserving_helper(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "spaced name.py").write_text("print('space')\n", encoding="utf-8")
    (tmp_path / "unicodé.py").write_text("print('unicode')\n", encoding="utf-8")

    monkeypatch.setattr(cli, "canonical_tracked_paths", lambda root: {"spaced name.py", "unicodé.py"})

    inventory = cli._tracked_file_inventory(tmp_path, [])

    assert [item["relative_path"] for item in inventory["files"]] == ["spaced name.py", "unicodé.py"]
    assert {item["source"] for item in inventory["files"]} == {"git_ls_files"}


def test_git_run_differentiates_missing_executable_permission_and_missing_cwd(monkeypatch, tmp_path: Path) -> None:
    def missing(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(git_mod.subprocess, "run", missing)
    missing_cp = git_mod.run_git(tmp_path, ["status"])
    assert missing_cp.returncode == git_mod.GIT_RETURNCODE_NOT_FOUND

    def denied(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(git_mod.subprocess, "run", denied)
    denied_cp = git_mod.run_git(tmp_path, ["status"])
    assert denied_cp.returncode == git_mod.GIT_RETURNCODE_OS_ERROR
    assert "denied" in denied_cp.stderr

    missing_cwd_cp = git_mod.run_git(tmp_path / "missing", ["status"])
    assert missing_cwd_cp.returncode == git_mod.GIT_RETURNCODE_OS_ERROR
    assert "working directory does not exist" in missing_cwd_cp.stderr


def test_git_timeout_preserves_string_and_byte_partial_output(monkeypatch, tmp_path: Path) -> None:
    def timeout_text(*args, **kwargs):
        raise subprocess.TimeoutExpired(["git", "status"], git_mod.GIT_TIMEOUT_SECONDS, output="partial out", stderr="partial err")

    monkeypatch.setattr(git_mod.subprocess, "run", timeout_text)
    text_cp = git_mod.run_git(tmp_path, ["status"])
    assert text_cp.returncode == git_mod.GIT_RETURNCODE_TIMEOUT
    assert text_cp.stdout == "partial out"
    assert text_cp.stderr == "partial err\ngit command timed out after 10 seconds"

    def timeout_bytes(*args, **kwargs):
        raise subprocess.TimeoutExpired(["git", "ls-files"], git_mod.GIT_TIMEOUT_SECONDS, output=b"raw out", stderr=b"raw err")

    monkeypatch.setattr(git_mod.subprocess, "run", timeout_bytes)
    bytes_cp = git_mod.run_git_bytes(tmp_path, ["ls-files", "-z"])
    assert bytes_cp.returncode == git_mod.GIT_RETURNCODE_TIMEOUT
    assert bytes_cp.stdout == b"raw out"
    assert bytes_cp.stderr == b"raw err\ngit command timed out after 10 seconds"


def test_tracked_paths_split_nul_preserves_spaces_and_unicode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        git_mod,
        "run_git_bytes",
        lambda repo, args: _cp_bytes(args, 0, b"space name.py\0unicod\xc3\xa9.py\0"),
    )

    assert git_mod.tracked_paths(tmp_path) == {"space name.py", "unicodé.py"}


def test_tracked_paths_preserves_non_utf8_git_filename_with_surrogateescape(tmp_path: Path) -> None:
    if os.name != "posix":
        return
    _init_repo(tmp_path)
    raw_name = b"bad_\xff.py"
    path = tmp_path / os.fsdecode(raw_name)
    path.write_text("print('bad bytes')\n", encoding="utf-8")
    subprocess.run(["git", "add", os.fsdecode(raw_name)], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    tracked = git_mod.tracked_paths(tmp_path)

    assert tracked == {os.fsdecode(raw_name)}


def test_run_git_bytes_missing_git_and_timeout(monkeypatch, tmp_path: Path) -> None:
    def missing(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(git_mod.subprocess, "run", missing)
    missing_cp = git_mod.run_git_bytes(tmp_path, ["ls-files", "-z"])
    assert missing_cp.returncode == git_mod.GIT_RETURNCODE_NOT_FOUND
    assert missing_cp.stderr == b"git executable not found"

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(["git", "ls-files"], git_mod.GIT_TIMEOUT_SECONDS, output=b"a.py\0", stderr=b"slow")

    monkeypatch.setattr(git_mod.subprocess, "run", timeout)
    timeout_cp = git_mod.run_git_bytes(tmp_path, ["ls-files", "-z"])
    assert timeout_cp.returncode == git_mod.GIT_RETURNCODE_TIMEOUT
    assert timeout_cp.stdout == b"a.py\0"
    assert timeout_cp.stderr == b"slow\ngit command timed out after 10 seconds"


def test_baseline_creation_fails_closed_for_canonical_git_failure_states(monkeypatch, tmp_path: Path) -> None:
    for state in ("git_unavailable", "git_timeout", "git_error"):
        repo = tmp_path / state
        repo.mkdir()
        monkeypatch.setattr(baseline, "_git_worktree_dirty", lambda root, state=state: (False, state))

        try:
            baseline.build_current_baseline(repo, quiet=True, force=True)
        except RuntimeError as exc:
            assert state in str(exc)
        else:
            raise AssertionError("baseline creation should fail")

        assert not (repo / ".sourcepack").exists()


def test_baseline_dirty_refusal_and_force_are_canonical(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(baseline, "_git_worktree_dirty", lambda root: (True, None))

    try:
        baseline.build_current_baseline(repo, quiet=True, force=False)
    except RuntimeError as exc:
        assert "dirty working tree" in str(exc)
    else:
        raise AssertionError("baseline creation should fail")
    assert not (repo / ".sourcepack").exists()

    paths, created = baseline.build_current_baseline(repo, quiet=True, force=True)
    assert created is True
    assert paths["active_pointer"].exists()


def test_baseline_protected_only_dirty_state_remains_allowed(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(baseline, "_git_worktree_dirty", lambda root: (False, "baseline_only_dirty"))

    paths, created = baseline.build_current_baseline(repo, quiet=True)

    assert created is True
    assert paths["active_pointer"].exists()


def test_no_direct_production_git_subprocess_invocation_remains_outside_git_module() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "sourcepack"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "git.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "run" and isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
                continue
            first = node.args[0] if node.args else None
            if isinstance(first, ast.List) and first.elts and isinstance(first.elts[0], ast.Constant) and first.elts[0].value == "git":
                offenders.append(f"{path.relative_to(root)}:{node.lineno}")
    assert offenders == []

def test_dirty_worktree_maps_permission_error_to_git_error(monkeypatch, tmp_path: Path) -> None:
    def denied(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(git_mod.subprocess, "run", denied)

    assert git_mod.dirty_worktree(tmp_path) == (False, "git_error")


def test_dirty_worktree_missing_working_directory_is_git_error_not_dirty(tmp_path: Path) -> None:
    assert git_mod.dirty_worktree(tmp_path / "missing") == (False, "git_error")


def test_dirty_worktree_os_error_during_root_check_is_not_not_git(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(git_mod, "run_git", lambda repo, args: _cp(args, git_mod.GIT_RETURNCODE_OS_ERROR, stderr="permission denied"))

    assert git_mod.dirty_worktree(tmp_path) == (False, "git_error")


def test_dirty_worktree_preserves_real_diff_quiet_one_as_dirty(monkeypatch, tmp_path: Path) -> None:
    def fake_run_git(repo, args):
        if args == ["rev-parse", "--show-toplevel"]:
            return _cp(args, 0, stdout=str(tmp_path))
        if args == ["diff", "--quiet"]:
            return _cp(args, 1)
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(git_mod, "run_git", fake_run_git)

    assert git_mod.dirty_worktree(tmp_path) == (True, None)


def test_baseline_refuses_normalized_os_error_126(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(baseline, "_run_git", lambda repo, args: _cp(args, git_mod.GIT_RETURNCODE_OS_ERROR, stderr="permission denied"))

    try:
        baseline.build_current_baseline(repo, quiet=True, force=True)
    except RuntimeError as exc:
        assert "git_error" in str(exc)
    else:
        raise AssertionError("baseline creation should fail")

    assert not (repo / ".sourcepack").exists()


def test_canonical_baseline_allows_only_exact_sourcepack_gitignore_addition_without_force(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "app"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (tmp_path / ".gitignore").write_text(".sourcepack/\n", encoding="utf-8")

    paths, created = baseline.build_current_baseline(tmp_path, quiet=True, force=False)

    assert created is True
    assert paths["active_pointer"].exists()


def test_canonical_baseline_blocks_unrelated_dirty_state_even_after_gitignore_addition(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "app"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (tmp_path / ".gitignore").write_text(".sourcepack/\n", encoding="utf-8")
    (tmp_path / "scratch.txt").write_text("unrelated\n", encoding="utf-8")

    try:
        baseline.build_current_baseline(tmp_path, quiet=True, force=False)
    except RuntimeError as exc:
        assert "dirty working tree" in str(exc)
    else:
        raise AssertionError("baseline creation should fail")

    assert not (tmp_path / ".sourcepack").exists()


def test_cli_baseline_blocks_file_added_after_precheck(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "app"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    original_ensure = cli.ensure_gitignore_entry

    def dirty_after_precheck(repo):
        result = original_ensure(repo)
        (Path(repo) / "late.txt").write_text("late dirty\n", encoding="utf-8")
        return result

    monkeypatch.setattr(cli, "ensure_gitignore_entry", dirty_after_precheck)

    class Args:
        repo = str(tmp_path)
        json = True
        verbose = False
        force = False
        quiet = True
        refresh = False

    assert cli.cli_baseline(Args()) == 1
    assert not (tmp_path / ".sourcepack" / "baseline" / "active.json").exists()


def test_cli_baseline_passes_user_force_value(monkeypatch, tmp_path: Path) -> None:
    seen: list[bool] = []
    monkeypatch.setattr(cli, "git_worktree_dirty", lambda repo: (False, None))
    monkeypatch.setattr(cli, "ensure_sourcepack_dirs", lambda repo: {"active_pointer": tmp_path / "active.json"})
    monkeypatch.setattr(cli, "ensure_gitignore_entry", lambda repo: (False, None))
    monkeypatch.setattr(cli, "validate_baseline", lambda repo: {"state": "missing"})
    monkeypatch.setattr(cli, "write_user_report", lambda repo, rep, stem: None)

    def fake_build(repo, quiet=False, fail_stage=None, force=False):
        seen.append(force)
        return {"active_pointer": tmp_path / "active.json"}, True

    monkeypatch.setattr(cli, "build_current_baseline", fake_build)

    class Args:
        repo = str(tmp_path)
        json = True
        verbose = False
        force = False
        quiet = True
        refresh = False

    assert cli.cli_baseline(Args()) == 0
    Args.force = True
    assert cli.cli_baseline(Args()) == 0
    assert seen == [False, True]

def test_auto_no_diff_baseline_creation_passes_false_force(monkeypatch, tmp_path: Path) -> None:
    seen: list[bool] = []
    monkeypatch.setattr(cli, "run_git", lambda repo, args: _cp(args, 0, stdout=str(tmp_path) if args == ["rev-parse", "--show-toplevel"] else ""))
    monkeypatch.setattr(cli, "validate_baseline", lambda repo: {"state": "missing"})
    monkeypatch.setattr(cli, "git_worktree_dirty", lambda repo: (False, None))
    monkeypatch.setattr(cli, "ensure_sourcepack_dirs", lambda repo: {})
    monkeypatch.setattr(cli, "ensure_gitignore_entry", lambda repo: (False, None))
    monkeypatch.setattr(cli, "untracked_files_as_diff", lambda repo: "")
    monkeypatch.setattr(cli, "baseline_report_fields", lambda status: {})

    def fake_build(repo, quiet=False, fail_stage=None, force=False):
        seen.append(force)
        return {}, True

    monkeypatch.setattr(cli, "build_current_baseline", fake_build)

    report = cli.build_repo_change_report(tmp_path)

    assert report["verdict"] == "PASS"
    assert seen == [False]


def test_init_auto_passes_user_force_value_to_baseline(monkeypatch, tmp_path: Path) -> None:
    seen: list[bool] = []
    monkeypatch.setattr(cli, "init_workspace", lambda repo: None)
    monkeypatch.setattr(cli, "git_worktree_dirty", lambda repo: (False, None))
    monkeypatch.setattr(cli, "validate_baseline", lambda repo: {"state": "missing"})
    monkeypatch.setattr(cli, "ensure_sourcepack_dirs", lambda repo: {})
    monkeypatch.setattr(cli, "ensure_gitignore_entry", lambda repo: (False, None))
    monkeypatch.setattr(cli, "install_post_commit_hook", lambda repo, strict=False: None)
    monkeypatch.setattr(cli, "write_auto_report", lambda repo, report, details=None: None)

    def fake_build(repo, quiet=False, fail_stage=None, force=False):
        seen.append(force)
        return {}, True

    monkeypatch.setattr(cli, "build_current_baseline", fake_build)

    class Args:
        path = str(tmp_path)
        auto = True
        force = False
        refresh_baseline = False
        no_hook = True
        install_hygiene_hooks = False
        strict = False
        json = True

    assert cli.cli_init(Args()) == 0
    Args.force = True
    assert cli.cli_init(Args()) == 0
    assert seen == [False, True]


def test_sourcepack_gitignore_exact_newline_variants_are_accepted(tmp_path: Path) -> None:
    for name, content in {
        "new-lf": b".sourcepack\n",
        "new-crlf": b".sourcepack\r\n",
        "new-slash-lf": b".sourcepack/\n",
        "new-slash-crlf": b".sourcepack/\r\n",
    }.items():
        repo = tmp_path / name
        repo.mkdir()
        _init_repo(repo)
        (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "app"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (repo / ".gitignore").write_bytes(content)

        assert baseline._gitignore_change_is_exact_sourcepack_addition(repo), name


def test_sourcepack_gitignore_exact_tracked_append_newline_variants_are_accepted(tmp_path: Path) -> None:
    for name, before, after in [
        ("tracked-lf", b"dist\n", b"dist\n.sourcepack/\n"),
        ("tracked-crlf", b"dist\r\n", b"dist\r\n.sourcepack/\r\n"),
    ]:
        repo = tmp_path / name
        repo.mkdir()
        _init_repo(repo)
        (repo / ".gitignore").write_bytes(before)
        subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "ignore"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (repo / ".gitignore").write_bytes(after)

        assert baseline._gitignore_change_is_exact_sourcepack_addition(repo), name


def test_sourcepack_gitignore_rejects_removed_or_modified_preexisting_rules(tmp_path: Path) -> None:
    cases = {
        "deleted-rule": (b"dist\nnode_modules\n", b"dist\n.sourcepack/\n"),
        "modified-rule": (b"dist\n", b"build\n.sourcepack/\n"),
    }
    for name, (before, after) in cases.items():
        repo = tmp_path / name
        repo.mkdir()
        _init_repo(repo)
        (repo / ".gitignore").write_bytes(before)
        subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "ignore"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (repo / ".gitignore").write_bytes(after)

        assert not baseline._gitignore_change_is_exact_sourcepack_addition(repo), name


def test_baseline_pre_activation_recheck_blocks_late_dirty_file_and_cleans_candidate(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "app"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    paths, _ = baseline.build_current_baseline(tmp_path, quiet=True, force=False)
    active_before = paths["active_pointer"].read_text(encoding="utf-8")
    builds_before = {path.name for path in (tmp_path / ".sourcepack" / "baseline" / "builds").iterdir()}

    original_write = baseline._write_baseline_packet

    def write_then_dirty(repo, packet_path):
        original_write(repo, packet_path)
        (Path(repo) / "late.txt").write_text("late dirty\n", encoding="utf-8")

    monkeypatch.setattr(baseline, "_write_baseline_packet", write_then_dirty)

    try:
        baseline.build_current_baseline(tmp_path, quiet=True, force=False)
    except RuntimeError as exc:
        assert "dirty working tree" in str(exc)
    else:
        raise AssertionError("baseline creation should fail")

    assert paths["active_pointer"].read_text(encoding="utf-8") == active_before
    builds_after = {path.name for path in (tmp_path / ".sourcepack" / "baseline" / "builds").iterdir()}
    assert builds_after == builds_before
