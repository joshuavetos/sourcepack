from __future__ import annotations

import os
import selectors
import subprocess
import time
from pathlib import Path
from typing import Final


GIT_TIMEOUT_SECONDS: Final[int] = 10
GIT_OUTPUT_LIMIT_BYTES: Final[int] = 8 * 1024 * 1024

GIT_RETURNCODE_TIMEOUT: Final[int] = 124
GIT_RETURNCODE_OS_ERROR: Final[int] = 126
GIT_RETURNCODE_NOT_FOUND: Final[int] = 127
GIT_RETURNCODE_OUTPUT_LIMIT: Final[int] = 125


class GitProducerIncompleteError(RuntimeError):
    """A Git evidence producer stopped before exhausting its output."""


def _bounded_process(repo: Path, args: list[str], limit: int) -> subprocess.CompletedProcess[bytes]:
    """Drain git incrementally, killing it before retained output exceeds limit."""
    command = ["git", *args]
    process = subprocess.Popen(command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    retained = 0
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    state = "complete"
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                state = "timeout"
                process.kill()
                break
            events = selector.select(remaining)
            if not events:
                state = "timeout"
                process.kill()
                break
            for key, _ in events:
                data = os.read(key.fileobj.fileno(), min(65536, limit + 1 - retained))
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if retained + len(data) > limit:
                    allowed = max(0, limit - retained)
                    if allowed:
                        chunks[key.data].append(data[:allowed])
                    retained = limit
                    state = "bounded"
                    process.kill()
                    break
                chunks[key.data].append(data)
                retained += len(data)
            if state != "complete":
                break
        process.wait()
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    stdout = b"".join(chunks["stdout"])
    stderr = b"".join(chunks["stderr"])
    if state == "bounded":
        message = f"git output exceeded {limit} byte producer limit".encode()
        return subprocess.CompletedProcess(command, GIT_RETURNCODE_OUTPUT_LIMIT, stdout, stderr.rstrip() + (b"\n" if stderr else b"") + message)
    if state == "timeout":
        message = f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds".encode()
        return subprocess.CompletedProcess(command, GIT_RETURNCODE_TIMEOUT, stdout, stderr.rstrip() + (b"\n" if stderr else b"") + message)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def run_git_bounded(repo: str | Path, args: list[str], *, output_limit_bytes: int = GIT_OUTPUT_LIMIT_BYTES, text: bool = True) -> subprocess.CompletedProcess:
    """Acquire Git evidence with complete/bounded/failed states encoded by return code."""
    cwd_failure = _cwd_error(repo)
    if cwd_failure is not None:
        result = _completed_git_process(args, cwd_failure.returncode, str(cwd_failure.stderr), stdout=b"" if not text else "")
        result.acquisition_state = "failed"
        return result
    try:
        cp = _bounded_process(Path(repo), args, output_limit_bytes)
    except FileNotFoundError:
        cp = subprocess.CompletedProcess(["git", *args], GIT_RETURNCODE_NOT_FOUND, b"", b"git executable not found")
    except OSError as exc:
        cp = subprocess.CompletedProcess(["git", *args], GIT_RETURNCODE_OS_ERROR, b"", _os_error_text(exc).encode("utf-8", "replace"))
    if not text:
        cp.acquisition_state = "bounded" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "complete" if cp.returncode == 0 else "failed"
        return cp
    result = subprocess.CompletedProcess(cp.args, cp.returncode, cp.stdout.decode("utf-8", "replace"), cp.stderr.decode("utf-8", "replace"))
    result.acquisition_state = "bounded" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "complete" if cp.returncode == 0 else "failed"
    return result


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

    if cp.returncode == GIT_RETURNCODE_OS_ERROR:
        return "git_error"

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
        return subprocess.CompletedProcess(["git"], GIT_RETURNCODE_OS_ERROR, "", f"git working directory does not exist: {cwd}")
    if not cwd.is_dir():
        return subprocess.CompletedProcess(["git"], GIT_RETURNCODE_OS_ERROR, "", f"git working directory is not a directory: {cwd}")
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
        return _completed_git_process(args, GIT_RETURNCODE_OS_ERROR, _os_error_text(exc))


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
        return _completed_git_process(args, GIT_RETURNCODE_OS_ERROR, _os_error_text(exc).encode("utf-8", "replace"), stdout=b"")


_DEFAULT_RUN_GIT_BYTES = run_git_bytes


def decode_git_path(raw: bytes) -> str:
    return os.fsdecode(raw).replace("\\", "/")


def split_nul_paths(raw: bytes) -> list[str]:
    return [decode_git_path(part) for part in raw.split(b"\0") if part]


def tracked_paths(repo: str | Path) -> set[str] | None:
    runner = run_git_bounded if run_git_bytes is _DEFAULT_RUN_GIT_BYTES else run_git_bytes
    cp = runner(repo, ["ls-files", "-z"], text=False) if runner is run_git_bounded else runner(repo, ["ls-files", "-z"])
    if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT:
        raise GitProducerIncompleteError("git tracked-path acquisition exceeded its producer limit")
    if cp.returncode != 0:
        return None
    paths = set(split_nul_paths(cp.stdout))
    if paths:
        return paths

    top_level = repo_root(repo)
    if top_level is None:
        return None

    all_cp = runner(top_level, ["ls-files", "-z"], text=False) if runner is run_git_bounded else runner(top_level, ["ls-files", "-z"])
    if all_cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT:
        raise GitProducerIncompleteError("git tracked-path acquisition exceeded its producer limit")
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
    """Return diff text, or an empty string when this convenience query fails.

    Callers making security or policy decisions must use :func:`run_git` and
    inspect its return code instead of treating this lossy result as evidence
    that a repository has no changes.
    """
    args = ["diff", "--staged"] if staged else ["diff"]

    if relative:
        args.append("--relative")

    cp = run_git(repo, args)
    return cp.stdout if cp.returncode == 0 else ""


def untracked_files(repo: str | Path) -> list[str]:
    """Return untracked paths, or an empty list when this convenience query fails.

    This wrapper intentionally favors a simple display-oriented API over
    diagnostic fidelity. Security-sensitive callers must use :func:`run_git`
    so failure remains distinguishable from a successful empty result.
    """
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
