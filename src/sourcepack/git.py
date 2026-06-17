from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=Path(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git executable not found")


def repo_root(path: str | Path) -> Path | None:
    cp = run_git(path, ["rev-parse", "--show-toplevel"])
    return Path(cp.stdout.strip()).resolve() if cp.returncode == 0 else None


def diff(repo: str | Path, *, staged: bool = False, relative: bool = False) -> str:
    args = ["diff", "--staged"] if staged else ["diff"]
    if relative:
        args.append("--relative")
    return run_git(repo, args).stdout


def untracked_files(repo: str | Path) -> list[str]:
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()] if cp.returncode == 0 else []


def dirty_worktree(repo: str | Path) -> tuple[bool, str | None]:
    root = repo_root(repo)
    if root is None:
        cp = run_git(repo, ["rev-parse", "--show-toplevel"])
        return False, "git_unavailable" if cp.returncode == 127 else "not_git"
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        cp = run_git(root, list(args))
        if cp.returncode == 1:
            return True, None
        if cp.returncode == 127:
            return False, "git_unavailable"
    return (bool(untracked_files(root)), None)


def metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, state = dirty_worktree(root)
    return {"branch": branch.stdout.strip() if branch.returncode == 0 else None, "head_commit": head.stdout.strip() if head.returncode == 0 else None, "dirty": dirty if state is None else None, "dirty_state": state}
