from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import run_cli
from sourcepack.execution_ledger import (
    SCHEMA_VERSION,
    detect_execution_claims,
    entry_to_json,
    execution_findings,
    iter_entries,
    ledger_path,
    run_and_record,
)


@contextlib.contextmanager
def cwd(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def init_repo(repo: Path) -> None:
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL)


def test_ledger_entry_creation_and_deterministic_shape():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "print('ok')"], cwd=repo)
        data = json.loads(entry_to_json(entry))
        assert data["schema_version"] == SCHEMA_VERSION
        assert list(data) == sorted(data)
        assert data["command"] == ["python", "-c", "print('ok')"]
        assert ledger_path(repo).exists()
        assert list(iter_entries(repo))[0]["entry_id"] == entry.entry_id


def test_stdout_stderr_hashing_and_excerpt_truncation():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "import sys; print('x'*3000); print('err', file=sys.stderr)"], cwd=repo)
        assert entry.stdout_sha256 == hashlib.sha256((("x" * 3000) + os.linesep).encode()).hexdigest()
        assert entry.stderr_sha256 == hashlib.sha256(("err" + os.linesep).encode()).hexdigest()
        assert entry.stdout_excerpt.endswith("…[truncated]")
        assert "err" in entry.stderr_excerpt


def test_failed_command_recording():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "import sys; sys.exit(7)"], cwd=repo)
        assert entry.exit_code == 7
        assert list(iter_entries(repo))[0]["exit_code"] == 7


def test_cli_json_only_output_where_applicable():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        with cwd(repo):
            assert run_cli(["exec", "--", "python", "-c", "print('json smoke')"]) == 0
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                assert run_cli(["evidence", "list", "--json"]) == 0
            parsed = json.loads(out.getvalue())
            assert parsed["schema_version"] == "sourcepack.execution_ledger.list.v1"


def test_explicit_execution_claim_detection():
    text = "Tests passed. pytest passed. npm run build works. I ran python -m pytest. I tested npm test."
    commands = [claim.command for claim in detect_execution_claims(text)]
    assert "tests" in commands
    assert "pytest" in commands
    assert "npm run build" in commands
    assert "python -m pytest" in commands
    assert "npm test" in commands


def test_near_miss_phrases_do_not_trigger_execution_claims():
    near_misses = [
        "run tests", "please test", "should pass", "probably passes", "expected to pass",
        "build support", "works toward", "the test file was added", "passing through",
        "unrelated prose containing the word passed",
    ]
    for phrase in near_misses:
        assert detect_execution_claims(phrase) == []


def test_report_includes_execution_evidence_when_available():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        run_and_record(["python", "-c", "print(1)"], cwd=repo)
        findings = execution_findings(repo, "I ran python -c print(1)")
        assert findings[0]["id"] == "execution_evidence_present"
        assert findings[0]["severity"] == "info"
        assert findings[0]["ledger_entry_id"]


def test_missing_execution_evidence_produces_warn_not_fake_pass():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        findings = execution_findings(repo, "pytest passed")
        assert findings[0]["id"] == "execution_evidence_missing"
        assert findings[0]["severity"] == "warn"


def test_ledger_does_not_update_trusted_baseline():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        baseline = repo / ".sourcepack" / "baseline"
        before_exists = baseline.exists()
        run_and_record(["python", "-c", "print('ok')"], cwd=repo)
        assert baseline.exists() is before_exists


def test_ledger_does_not_treat_prompt_claims_as_trusted_evidence():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        prompt = repo / ".sourcepack" / "prompt"
        prompt.mkdir(parents=True)
        (prompt / "context.md").write_text("pytest passed\n", encoding="utf-8")
        findings = execution_findings(repo, (prompt / "context.md").read_text(encoding="utf-8"))
        assert findings[0]["id"] == "execution_evidence_missing"
