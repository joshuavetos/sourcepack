from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from sourcepack.reason_codes import canonical_reason_codes, is_canonical_reason_code, normalize_reason_code
from sourcepack.reports.json import normalized_finding, traffic_report

ROOT = Path(__file__).resolve().parents[1]
CORE_PATHS = [
    ROOT / "src/sourcepack/judgment.py",
    ROOT / "src/sourcepack/baseline.py",
    ROOT / "src/sourcepack/diff_parser.py",
    ROOT / "src/sourcepack/git.py",
    ROOT / "src/sourcepack/policy.py",
    ROOT / "src/sourcepack/reason_codes.py",
    ROOT / "src/sourcepack/schemas.py",
    *sorted((ROOT / "src/sourcepack/ecosystems").glob("*.py")),
    *sorted((ROOT / "src/sourcepack/reports").glob("*.py")),
]


def _imports_cli(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "sourcepack.cli" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sourcepack.cli":
                return True
            if node.module == "cli" and node.level >= 1:
                return True
    text = path.read_text(encoding="utf-8")
    return any(token in text for token in ("from .cli import", "from sourcepack.cli import", "import sourcepack.cli"))


def test_core_modules_do_not_import_cli() -> None:
    offenders = [str(path.relative_to(ROOT)) for path in CORE_PATHS if _imports_cli(path)]
    assert offenders == []


def test_cli_diff_delegates_to_judge_repo_change() -> None:
    source = (ROOT / "src/sourcepack/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cli_diff = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "cli_diff")
    calls = [node for node in ast.walk(cli_diff) if isinstance(node, ast.Call)]
    assert any(isinstance(call.func, ast.Name) and call.func.id == "judge_repo_change" for call in calls)


def test_report_rejects_unknown_warn_fail_reason_code() -> None:
    with pytest.raises(ValueError):
        normalized_finding("not_a_code", "warn", "review", "bad")
    with pytest.raises(ValueError):
        normalized_finding("not_a_code", "error", "review", "bad")


def test_report_all_warn_fail_codes_are_canonical() -> None:
    report = traffic_report(
        "WARN",
        findings=[normalized_finding("baseline-missing", "warn", "baseline", "missing")],
    )
    ids = {finding["id"] for finding in report["findings"] if finding["severity"] in {"warn", "error"}}
    assert ids <= set(canonical_reason_codes())


def test_reason_code_docs_match_code_vocabulary() -> None:
    docs = (ROOT / "docs/reason-codes.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^## ([a-z0-9_]+)$", docs, flags=re.MULTILINE))
    assert set(canonical_reason_codes()) <= documented


def test_reason_code_alias_normalization() -> None:
    assert normalize_reason_code("baseline-missing") == "baseline_missing"
    assert normalize_reason_code("baseline corrupt") == "baseline_corrupt"


def test_reason_code_strict_canonical_spelling() -> None:
    assert is_canonical_reason_code("baseline_missing")
    assert normalize_reason_code("baseline-missing") == "baseline_missing"
    assert "baseline-missing" not in set(canonical_reason_codes())
