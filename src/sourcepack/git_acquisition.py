from __future__ import annotations

from pathlib import Path
from typing import Callable

from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_TIMEOUT


def worktree_dirty(repo: str | Path, run_git: Callable) -> tuple[bool, str | None]:
    """Acquire worktree dirtiness while leaving facade-owned Git adapters injectable."""
    repo = Path(repo)
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            return False, "git_unavailable"
        if cp.returncode == GIT_RETURNCODE_TIMEOUT:
            return False, "git_timeout"
        if cp.returncode == GIT_RETURNCODE_OS_ERROR:
            return False, "git_error"
        return False, "not_git"
    root = Path(cp.stdout.strip())
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        diff_cp = run_git(root, list(args))
        if diff_cp.returncode == 1:
            return True, None
        if diff_cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            return False, "git_unavailable"
        if diff_cp.returncode == GIT_RETURNCODE_TIMEOUT:
            return False, "git_timeout"
        if diff_cp.returncode == GIT_RETURNCODE_OS_ERROR:
            return False, "git_error"
        if diff_cp.returncode != 0:
            return False, "git_error"
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0 and untracked.stdout.strip():
        return True, None
    if untracked.returncode == GIT_RETURNCODE_NOT_FOUND:
        return False, "git_unavailable"
    if untracked.returncode == GIT_RETURNCODE_TIMEOUT:
        return False, "git_timeout"
    if untracked.returncode == GIT_RETURNCODE_OS_ERROR:
        return False, "git_error"
    if untracked.returncode != 0:
        return False, "git_error"
    return False, None
