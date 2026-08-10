from __future__ import annotations

import os
import queue
import subprocess
import threading
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


def _bounded_process(repo: Path, args: list[str], limit: int, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Drain git incrementally without relying on selectable subprocess pipes."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError("output limit must be a non-negative integer")
    command = ["git", *args]
    process = subprocess.Popen(command, cwd=repo, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    retained = 0
    state = "complete"
    events: queue.Queue[tuple[str, bytes | BaseException | None]] = queue.Queue(maxsize=8)

    def read_pipe(name: str, stream) -> None:
        try:
            while data := stream.read(65536):
                events.put((name, data))
        except BaseException as exc:
            events.put(("error", exc))
        finally:
            events.put((name, None))

    def write_input(stream) -> None:
        try:
            assert input_bytes is not None
            view = memoryview(input_bytes)
            while view:
                written = stream.write(view[:65536])
                if not written:
                    break
                view = view[written:]
            stream.close()
        except BrokenPipeError:
            if not stream.closed:
                stream.close()
        except BaseException as exc:
            events.put(("error", exc))

    workers: list[threading.Thread] = []
    pending_error: BaseException | None = None
    try:
        assert process.stdout is not None and process.stderr is not None
        workers = [
            threading.Thread(target=read_pipe, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=read_pipe, args=("stderr", process.stderr), daemon=True),
        ]
        if input_bytes is not None:
            assert process.stdin is not None
            workers.append(threading.Thread(target=write_input, args=(process.stdin,), daemon=True))
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
        open_readers = 2
        while open_readers:
            remaining = deadline - time.monotonic()
            if remaining <= 0 and state == "complete":
                state = "timeout"
                process.kill()
            try:
                name, value = events.get(timeout=max(0.01, remaining) if state == "complete" else 0.1)
            except queue.Empty:
                if state == "complete":
                    state = "timeout"
                    process.kill()
                continue
            if name == "error":
                assert isinstance(value, BaseException)
                pending_error = value
                if process.poll() is None:
                    process.kill()
                continue
            if value is None:
                open_readers -= 1
                continue
            assert isinstance(value, bytes)
            if state != "complete":
                continue
            if retained + len(value) > limit:
                allowed = max(0, limit - retained)
                if allowed:
                    chunks[name].append(value[:allowed])
                retained = limit
                state = "bounded"
                process.kill()
                continue
            chunks[name].append(value)
            retained += len(value)
        if pending_error is not None:
            raise pending_error
    finally:
        try:
            if process.poll() is None:
                try:
                    process.kill()
                finally:
                    process.wait()
            else:
                process.wait()
        finally:
            for worker in workers:
                worker.join(timeout=1)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
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
    if not isinstance(output_limit_bytes, int) or isinstance(output_limit_bytes, bool) or output_limit_bytes < 0:
        raise ValueError("output limit must be a non-negative integer")
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


def run_git_bounded_input(repo: str | Path, args: list[str], input_bytes: bytes, *, input_limit_bytes: int, output_limit_bytes: int, text: bool = False, accepted_returncodes: frozenset[int] = frozenset({0})) -> subprocess.CompletedProcess:
    """Run Git with bounded stdin and incrementally bounded combined output."""
    if not isinstance(input_limit_bytes, int) or isinstance(input_limit_bytes, bool) or input_limit_bytes < 0:
        raise ValueError("input limit must be a non-negative integer")
    if not isinstance(output_limit_bytes, int) or isinstance(output_limit_bytes, bool) or output_limit_bytes < 0:
        raise ValueError("output limit must be a non-negative integer")
    if len(input_bytes) > input_limit_bytes:
        cp = subprocess.CompletedProcess(["git", *args], GIT_RETURNCODE_OUTPUT_LIMIT, b"", b"git input exceeded producer limit")
        cp.acquisition_state = "bounded"
        return cp
    cwd_failure = _cwd_error(repo)
    if cwd_failure is not None:
        cp = _completed_git_process(args, cwd_failure.returncode, str(cwd_failure.stderr).encode(), stdout=b"")
    else:
        try:
            cp = _bounded_process(Path(repo), args, output_limit_bytes, input_bytes=input_bytes)
        except FileNotFoundError:
            cp = _completed_git_process(args, GIT_RETURNCODE_NOT_FOUND, b"git executable not found", stdout=b"")
        except OSError as exc:
            cp = _completed_git_process(args, GIT_RETURNCODE_OS_ERROR, _os_error_text(exc).encode("utf-8", "replace"), stdout=b"")
    if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT:
        cp.acquisition_state = "bounded"
    elif cp.returncode in {GIT_RETURNCODE_TIMEOUT, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_NOT_FOUND}:
        cp.acquisition_state = "failed"
    else:
        cp.acquisition_state = "complete" if cp.returncode in accepted_returncodes else "failed"
    if not text:
        return cp
    result = subprocess.CompletedProcess(cp.args, cp.returncode, cp.stdout.decode("utf-8", "replace"), cp.stderr.decode("utf-8", "replace"))
    result.acquisition_state = cp.acquisition_state
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
    return run_git_bounded(repo, args, text=True)


def run_git_bytes(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a bounded bytes-mode git command in repo without decoding stdout/stderr."""
    return run_git_bounded(repo, args, text=False)


_DEFAULT_RUN_GIT_BYTES = run_git_bytes


def decode_git_path(raw: bytes) -> str:
    path = os.fsdecode(raw)
    return path.replace("\\", "/") if os.name == "nt" else path


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
