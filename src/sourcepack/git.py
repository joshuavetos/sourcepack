from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final


GIT_TIMEOUT_SECONDS: Final[int] = 10

GIT_RETURNCODE_TIMEOUT: Final[int] = 124
GIT_RETURNCODE_NOT_FOUND: Final[int] = 127


def _completed_git_process(
    args: list[str],
    returncode: int,
    stderr: str,
    *,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["git", *args],
        returncode,
        stdout,
        stderr,
    )


def _git_failure_state(cp: subprocess.CompletedProcess[str]) -> str | None:
    if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
        return "git_unavailable"

    if cp.returncode == GIT_RETURNCODE_TIMEOUT:
        return "git_timeout"

    return None


def _timeout_output_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, str):
        return value
    return ""


def run_git(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a bounded git command in repo.

    This helper never invokes a shell. Callers must pass git arguments as a
    list, not as a shell string.

    Timeout and missing-executable failures are normalized into
    CompletedProcess objects so higher-level helpers can fail closed without
    hanging or raising.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=Path(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return _completed_git_process(
            args,
            GIT_RETURNCODE_NOT_FOUND,
            "git executable not found",
        )
    except OSError as exc:
        return _completed_git_process(
            args,
            GIT_RETURNCODE_NOT_FOUND,
            f"git executable not found: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_output_text(exc.stdout)
        stderr = _timeout_output_text(exc.stderr)

        timeout_message = f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
        if stderr:
            stderr = f"{stderr.rstrip()}\n{timeout_message}"
        else:
            stderr = timeout_message

        return _completed_git_process(
            args,
            GIT_RETURNCODE_TIMEOUT,
            stderr,
            stdout=stdout,
        )


def repo_root(path: str | Path) -> Path | None:
    cp = run_git(path, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return None

    root = cp.stdout.strip()
    if not root:
        return None

    return Path(root).resolve()


def diff(repo: str | Path, *, staged: bool = False, relative: bool = False) -> str:
    args = ["diff", "--staged"] if staged else ["diff"]

    if relative:
        args.append("--relative")

    cp = run_git(repo, args)
    return cp.stdout if cp.returncode == 0 else ""


def untracked_files(repo: str | Path) -> list[str]:
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    if cp.returncode != 0:
        return []

    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def dirty_worktree(repo: str | Path) -> tuple[bool, str | None]:
    root_cp = run_git(repo, ["rev-parse", "--show-toplevel"])

    failure_state = _git_failure_state(root_cp)
    if failure_state is not None:
        return False, failure_state

    if root_cp.returncode != 0:
        return False, "not_git"

    root_text = root_cp.stdout.strip()
    if not root_text:
        return False, "not_git"

    root = Path(root_text).resolve()

    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        cp = run_git(root, args)

        if cp.returncode == 0:
            continue

        if cp.returncode == 1:
            return True, None

        failure_state = _git_failure_state(cp)
        if failure_state is not None:
            return False, failure_state

        return False, "git_error"

    untracked_cp = run_git(root, ["ls-files", "--others", "--exclude-standard"])

    failure_state = _git_failure_state(untracked_cp)
    if failure_state is not None:
        return False, failure_state

    if untracked_cp.returncode != 0:
        return False, "git_error"

    has_untracked = any(line.strip() for line in untracked_cp.stdout.splitlines())
    return has_untracked, None


def metadata(repo: str | Path) -> dict:
    root = Path(repo)

    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, dirty_state = dirty_worktree(root)

    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": dirty if dirty_state is None else None,
        "dirty_state": dirty_state,
    }
