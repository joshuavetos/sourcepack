from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sourcepack import baseline, cli, git as git_mod, judgment, packet
from sourcepack.packet import SourceScanner


def _cp(args: list[str], returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git", *args], returncode, stdout, stderr)


def _cp_bytes(args: list[str], returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(["git", *args], returncode, stdout, stderr)


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)


def test_cli_diff_parser_symbols_are_canonical() -> None:
    from sourcepack import diff_parser

    assert cli.PatchFileChange is diff_parser.PatchFileChange
    assert cli.parse_unified_diff is diff_parser.parse_unified_diff
    assert cli._normalize_diff_path is diff_parser.normalize_diff_path


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
    assert denied_cp.returncode not in {git_mod.GIT_RETURNCODE_NOT_FOUND, git_mod.GIT_RETURNCODE_TIMEOUT}
    assert "denied" in denied_cp.stderr

    missing_cwd_cp = git_mod.run_git(tmp_path / "missing", ["status"])
    assert missing_cwd_cp.returncode not in {git_mod.GIT_RETURNCODE_NOT_FOUND, git_mod.GIT_RETURNCODE_TIMEOUT}
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


@pytest.mark.skipif(os.name != "posix", reason="surrogateescape path behavior is POSIX-specific")
def test_tracked_paths_preserves_non_utf8_git_filename_with_surrogateescape(tmp_path: Path) -> None:
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

        with pytest.raises(RuntimeError, match=state):
            baseline.build_current_baseline(repo, quiet=True, force=True)

        assert not (repo / ".sourcepack").exists()


def test_baseline_dirty_refusal_and_force_are_canonical(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(baseline, "_git_worktree_dirty", lambda root: (True, None))

    with pytest.raises(RuntimeError, match="dirty working tree"):
        baseline.build_current_baseline(repo, quiet=True, force=False)
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
