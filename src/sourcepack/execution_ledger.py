from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Iterable


SCHEMA_VERSION: Final[str] = "sourcepack.execution_ledger.v1"
LEDGER_FILENAME: Final[str] = "ledger.jsonl"

MAX_EXCERPT_CHARS: Final[int] = 2048

GIT_TIMEOUT_SECONDS: Final[int] = 10
EXEC_TIMEOUT_SECONDS: Final[int] = 120

RETURNCODE_TIMEOUT: Final[int] = 124
RETURNCODE_NOT_FOUND: Final[int] = 127


@dataclass(frozen=True)
class ExecutionClaim:
    command: str
    phrase: str
    start: int
    end: int


@dataclass(frozen=True)
class ExecutionLedgerEntry:
    schema_version: str
    entry_id: str
    generated_at: str
    repo_root: str
    git_head: str | None
    worktree_dirty_before: bool | None
    worktree_dirty_after: bool | None
    command: list[str]
    cwd: str
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str
    duration_ms: int
    environment_summary: dict
    sourcepack_version: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def excerpt_bytes(data: bytes, limit: int = MAX_EXCERPT_CHARS) -> str:
    text = data.decode("utf-8", "replace")
    if len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"


def _completed_process(
    command: list[str],
    returncode: int,
    stderr: bytes,
    *,
    stdout: bytes = b"",
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout,
        stderr,
    )


def _timeout_stderr(existing: bytes, message: str) -> bytes:
    timeout_message = message.encode("utf-8", "replace")
    if existing:
        return existing.rstrip() + b"\n" + timeout_message
    return timeout_message


def _run_git(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]

    try:
        return subprocess.run(
            command,
            cwd=Path(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            command,
            RETURNCODE_NOT_FOUND,
            "",
            "git executable not found",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""

        message = f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
        stderr = f"{stderr.rstrip()}\n{message}" if stderr else message

        return subprocess.CompletedProcess(
            command,
            RETURNCODE_TIMEOUT,
            stdout,
            stderr,
        )


def find_repo_root(start: str | Path = ".") -> Path:
    start_path = Path(start).resolve()
    cp = _run_git(start_path, ["rev-parse", "--show-toplevel"])

    if cp.returncode == 0 and cp.stdout.strip():
        return Path(cp.stdout.strip()).resolve()

    return start_path


def _git_head(repo_root: Path) -> str | None:
    cp = _run_git(repo_root, ["rev-parse", "HEAD"])
    if cp.returncode == 0 and cp.stdout.strip():
        return cp.stdout.strip()
    return None


def _worktree_dirty(repo_root: Path) -> bool | None:
    cp = _run_git(repo_root, ["status", "--porcelain"])
    if cp.returncode != 0:
        return None
    return bool(cp.stdout.strip())


def ledger_dir(repo_root: str | Path) -> Path:
    return Path(repo_root) / ".sourcepack" / "evidence"


def ledger_path(repo_root: str | Path) -> Path:
    return ledger_dir(repo_root) / LEDGER_FILENAME


def entry_to_json(entry: ExecutionLedgerEntry) -> str:
    return json.dumps(asdict(entry), sort_keys=True, separators=(",", ":"))


def append_entry(repo_root: str | Path, entry: ExecutionLedgerEntry) -> None:
    path = ledger_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry_to_json(entry) + "\n")


def iter_entries(repo_root: str | Path) -> Iterable[dict]:
    path = ledger_path(repo_root)
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(entry, dict):
                yield entry


def clear_ledger(repo_root: str | Path) -> None:
    path = ledger_path(repo_root)
    if path.exists():
        path.unlink()


def environment_summary() -> dict:
    path_value = os.environ.get("PATH", "")

    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "shell": os.environ.get("SHELL"),
        "path_entries": len(path_value.split(os.pathsep)) if path_value else 0,
    }


def _sourcepack_version() -> str:
    from sourcepack import __version__

    return __version__


def _run_recorded_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=EXEC_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        executable = command[0] if command else "<empty>"
        return _completed_process(
            command,
            RETURNCODE_NOT_FOUND,
            f"command executable not found: {executable}".encode("utf-8", "replace"),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""

        return _completed_process(
            command,
            RETURNCODE_TIMEOUT,
            _timeout_stderr(
                stderr,
                f"command timed out after {EXEC_TIMEOUT_SECONDS} seconds",
            ),
            stdout=stdout,
        )


def run_and_record(command: list[str], cwd: str | Path = ".") -> ExecutionLedgerEntry:
    if not command:
        raise ValueError("sourcepack exec requires a command after --")

    resolved_cwd = Path(cwd).resolve()
    repo_root = find_repo_root(resolved_cwd)

    dirty_before = _worktree_dirty(repo_root)
    head = _git_head(repo_root)

    start = time.monotonic()
    cp = _run_recorded_command(command, resolved_cwd)
    duration_ms = int((time.monotonic() - start) * 1000)

    dirty_after = _worktree_dirty(repo_root)

    stdout = cp.stdout or b""
    stderr = cp.stderr or b""

    entry = ExecutionLedgerEntry(
        schema_version=SCHEMA_VERSION,
        entry_id=uuid.uuid4().hex,
        generated_at=utc_now(),
        repo_root=str(repo_root),
        git_head=head,
        worktree_dirty_before=dirty_before,
        worktree_dirty_after=dirty_after,
        command=list(command),
        cwd=str(resolved_cwd),
        exit_code=int(cp.returncode),
        stdout_sha256=sha256_bytes(stdout),
        stderr_sha256=sha256_bytes(stderr),
        stdout_excerpt=excerpt_bytes(stdout),
        stderr_excerpt=excerpt_bytes(stderr),
        duration_ms=duration_ms,
        environment_summary=environment_summary(),
        sourcepack_version=_sourcepack_version(),
    )

    append_entry(repo_root, entry)
    return entry


_CLEAR_PHRASES: Final[tuple[str, ...]] = (
    "tests passed",
    "test passed",
    "build passed",
    "lint passed",
    "typecheck passed",
    "pytest passed",
    "npm test passed",
    "npm run build passed",
)

_SUPPORTED_COMMAND_PREFIXES: Final[tuple[str, ...]] = (
    "pytest",
    "npm test",
    "npm run build",
    "npm run test",
    "python -m pytest",
    "make test",
    "ruff check",
    "mypy",
)

_RAN_RE: Final[re.Pattern[str]] = re.compile(
    r"\bI\s+(?:ran|tested)\s+([^\n.;]+)",
    re.IGNORECASE,
)


def detect_execution_claims(text: str) -> list[ExecutionClaim]:
    """Return bounded, explicit command-execution claims without semantic guessing."""
    claims: list[ExecutionClaim] = []
    lower = text.lower()

    for phrase in _CLEAR_PHRASES:
        start = lower.find(phrase)

        while start != -1:
            context = lower[max(0, start - 20) : start + len(phrase)]
            uncertain = re.search(
                r"\b(should|probably|expected to)\s+" + re.escape(phrase.split()[0]),
                context,
            )

            if not uncertain:
                command = phrase.removesuffix(" passed")
                claims.append(
                    ExecutionClaim(
                        command=command,
                        phrase=text[start : start + len(phrase)],
                        start=start,
                        end=start + len(phrase),
                    )
                )

            start = lower.find(phrase, start + 1)

    for prefix in _SUPPORTED_COMMAND_PREFIXES:
        pattern = re.compile(
            r"\b" + re.escape(prefix) + r"\s+(passed|works|succeeds)\b",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            claims.append(
                ExecutionClaim(
                    command=prefix,
                    phrase=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

    for match in _RAN_RE.finditer(text):
        command = match.group(1).strip().strip('`"\'')

        if not command:
            continue

        command_lower = command.lower()
        if len(command.split()) > 8:
            continue

        if command_lower.startswith(("tests", "the test file")):
            continue

        claims.append(
            ExecutionClaim(
                command=command,
                phrase=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    claims.sort(key=lambda claim: (claim.start, claim.end, claim.command.lower()))

    deduped: list[ExecutionClaim] = []
    seen: set[tuple[str, int, int]] = set()

    for claim in claims:
        key = (claim.command.lower(), claim.start, claim.end)
        if key in seen:
            continue

        seen.add(key)
        deduped.append(claim)

    return deduped


def _command_matches(claim: str, entry_command: list[str]) -> bool:
    normalized_entry = " ".join(entry_command).strip().lower()
    normalized_claim = claim.strip().lower()

    return normalized_entry == normalized_claim or normalized_entry.startswith(
        normalized_claim + " "
    )


def evidence_for_claim(repo_root: str | Path, claim: ExecutionClaim) -> tuple[str, dict | None]:
    matches = [
        entry
        for entry in iter_entries(repo_root)
        if _command_matches(claim.command, list(entry.get("command") or []))
    ]

    if not matches:
        return "execution_evidence_missing", None

    latest = sorted(matches, key=lambda entry: str(entry.get("generated_at") or ""))[-1]

    exit_codes: set[int] = set()
    for match in matches:
        try:
            exit_codes.add(int(match.get("exit_code", -999)))
        except (TypeError, ValueError):
            exit_codes.add(-999)

    if len(exit_codes) > 1:
        return "execution_inconclusive", latest

    try:
        latest_exit_code = int(latest.get("exit_code", -1))
    except (TypeError, ValueError):
        latest_exit_code = -1

    if latest_exit_code == 0:
        return "execution_evidence_present", latest

    return "execution_failed", latest


def execution_findings(repo_root: str | Path, text: str) -> list[dict]:
    findings: list[dict] = []

    for claim in detect_execution_claims(text):
        status, entry = evidence_for_claim(repo_root, claim)

        if status == "execution_evidence_present":
            severity = "info"
            message = f"Execution ledger contains a successful local run for: {claim.command}."
        elif status == "execution_failed":
            severity = "warn"
            message = f"Execution ledger contains a failed local run for: {claim.command}."
        elif status == "execution_inconclusive":
            severity = "warn"
            message = f"Execution ledger has mixed or ambiguous local runs for: {claim.command}."
        else:
            severity = "warn"
            message = f"No SourcePack execution-ledger entry supports claimed run: {claim.command}."

        findings.append(
            {
                "id": status,
                "severity": severity,
                "category": "execution",
                "path": None,
                "message": message,
                "evidence": claim.command,
                "suggestion": (
                    "Run the command through `sourcepack exec -- ...` if local execution evidence is intended."
                    if severity == "warn"
                    else None
                ),
                "ledger_entry_id": entry.get("entry_id") if entry else None,
            }
        )

    return findings


def command_available(command: str) -> bool:
    return shutil.which(command) is not None
