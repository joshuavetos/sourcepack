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
    stderr: str | bytes,
    *,
    stdout: str | bytes = "",
) -> subprocess.CompletedProcess:
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


def _cwd_error(repo: str | Path) -> subprocess.CompletedProcess[str] | None:
    cwd = Path(repo)
    if not cwd.exists():
        return subprocess.CompletedProcess(["git"], 1, "", f"git working directory does not exist: {cwd}")
    if not cwd.is_dir():
        return subprocess.CompletedProcess(["git"], 1, "", f"git working directory is not a directory: {cwd}")
    return None


def _os_error_text(exc: OSError) -> str:
    return f"git execution failed: {exc}"


def run_git(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a bounded text-mode git command in repo without invoking a shell."""
    cwd_failure = _cwd_error(repo)
    if cwd_failure is not None:
        cwd_failure.args = ["git", *args]
        return cwd_failure
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
    except OSError as exc:
        return _completed_git_process(args, 1, _os_error_text(exc))


def _timeout_output_bytes(value: str | bytes | None) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", "surrogateescape")
    return b""


def run_git_bytes(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a bounded bytes-mode git command in repo without decoding stdout/stderr."""
    cwd_failure = _cwd_error(repo)
    if cwd_failure is not None:
        return subprocess.CompletedProcess(["git", *args], cwd_failure.returncode, b"", str(cwd_failure.stderr).encode("utf-8", "replace"))
    try:
        return subprocess.run(
            ["git", *args],
            cwd=Path(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return _completed_git_process(args, GIT_RETURNCODE_NOT_FOUND, b"git executable not found", stdout=b"")
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_output_bytes(exc.stdout)
        stderr = _timeout_output_bytes(exc.stderr)
        timeout_message = f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds".encode("utf-8")
        stderr = stderr.rstrip() + b"\n" + timeout_message if stderr else timeout_message
        return _completed_git_process(args, GIT_RETURNCODE_TIMEOUT, stderr, stdout=stdout)
    except OSError as exc:
        return _completed_git_process(args, 1, _os_error_text(exc).encode("utf-8", "replace"), stdout=b"")


def decode_git_path(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape").replace("\\", "/")


def split_nul_paths(raw: bytes) -> list[str]:
    return [decode_git_path(part) for part in raw.split(b"\0") if part]


def tracked_paths(repo: str | Path) -> set[str] | None:
    cp = run_git_bytes(repo, ["ls-files", "-z"])
    if cp.returncode != 0:
        return None
    paths = set(split_nul_paths(cp.stdout))
    if paths:
        return paths

    top_level = repo_root(repo)
    if top_level is None:
        return None

    all_cp = run_git_bytes(top_level, ["ls-files", "-z"])
    if all_cp.returncode != 0:
        return None
    if not split_nul_paths(all_cp.stdout):
        return None
    return set()


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
