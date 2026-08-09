from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_TIMEOUT


_PORCELAIN_V1_STATUSES = frozenset({
    " M", " D", " T", "M ", "T ", "A ", "D ", "R ", "C ",
    "MM", "MT", "MD", "TM", "TT", "TD", "AM", "AT", "AD",
    "RM", "RT", "RD", "CM", "CT", "CD", "DD", "AU", "UD",
    "UA", "DU", "AA", "UU", "??", "!!",
})


@dataclass(frozen=True)
class StatusRecord:
    status: str
    path: str | None
    old_path: str | None = None


def _failure_state(returncode: int) -> str:
    if returncode == GIT_RETURNCODE_NOT_FOUND:
        return "git_unavailable"
    if returncode == GIT_RETURNCODE_TIMEOUT:
        return "git_timeout"
    return "git_error"


def parse_porcelain_v1_z(data: bytes, prefix: bytes) -> tuple[list[StatusRecord], str | None]:
    """Parse ``status --porcelain=v1 -z`` and confine paths to ``prefix``."""
    if data and not data.endswith(b"\0"):
        return [], "git_error"
    fields = data.split(b"\0")[:-1]
    records: list[StatusRecord] = []
    index = 0

    def selected_path(raw: bytes) -> str | None:
        if not raw or raw.startswith(b"/") or b"\0" in raw:
            raise ValueError("invalid Git status path")
        if prefix:
            if not raw.startswith(prefix):
                return None
            raw = raw[len(prefix):]
            if not raw:
                raise ValueError("status path is the selected directory")
        return os.fsdecode(raw)

    try:
        while index < len(fields):
            field = fields[index]
            index += 1
            if len(field) < 4 or field[2:3] != b" ":
                raise ValueError("malformed porcelain record")
            status_bytes = field[:2]
            if any(byte < 0x20 or byte > 0x7e for byte in status_bytes):
                raise ValueError("invalid porcelain status")
            status = status_bytes.decode("ascii")
            if status not in _PORCELAIN_V1_STATUSES:
                raise ValueError("impossible porcelain status")
            path = selected_path(field[3:])
            old_path = None
            if b"R" in status_bytes or b"C" in status_bytes:
                if index >= len(fields):
                    raise ValueError("rename/copy record missing source path")
                old_path = selected_path(fields[index])
                index += 1
            if path is not None or old_path is not None:
                records.append(StatusRecord(status=status, path=path, old_path=old_path))
    except (UnicodeError, ValueError):
        return [], "git_error"
    return records, None


def acquire_status(repo: str | Path, run_git_bytes: Callable, paths: list[str] | None = None) -> tuple[list[StatusRecord], str | None]:
    """Acquire selected-root status using bounded, NUL-delimited byte output."""
    repo = Path(repo)
    top = run_git_bytes(repo, ["rev-parse", "--show-toplevel"])
    if top.returncode != 0:
        if b"not a git repository" in bytes(top.stderr or b"").lower():
            return [], "not_git"
        return [], _failure_state(top.returncode)
    prefix_cp = run_git_bytes(repo, ["rev-parse", "--show-prefix"])
    if prefix_cp.returncode != 0:
        return [], _failure_state(prefix_cp.returncode)
    prefix = prefix_cp.stdout.rstrip(b"\n")
    if prefix and not prefix.endswith(b"/"):
        return [], "git_error"
    git_root = Path(os.fsdecode(top.stdout.rstrip(b"\n")))
    pathspecs = [prefix + os.fsencode(path) for path in (paths or ["."])]
    cp = run_git_bytes(
        git_root,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *[os.fsdecode(path) for path in pathspecs]],
    )
    if cp.returncode != 0:
        return [], _failure_state(cp.returncode)
    return parse_porcelain_v1_z(cp.stdout, prefix)


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
    # Keep acquisition bounded to the caller-selected root.  Git top-level
    # discovery validates that the path is in a repository, but widening to the
    # enclosing top level would treat parent/sibling changes as authoritative
    # evidence for a selected subdirectory review.
    root = repo
    for args in (["diff", "--quiet", "--", "."], ["diff", "--staged", "--quiet", "--", "."]):
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
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard", "--", "."])
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
