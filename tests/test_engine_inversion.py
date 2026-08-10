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


def test_judgment_module_does_not_contain_cli_behavior() -> None:
    source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    forbidden = [
        "argparse",
        "webbrowser",
        "def run_cli",
        "def cli_",
        "print(",
        "parser.add_",
        "subparsers",
        "install_hook",
        "uninstall_hook",
    ]
    offenders = [token for token in forbidden if token in source]
    assert offenders == []


def test_judgment_uses_diff_parser_patch_file_change() -> None:
    source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    assert "from .diff_parser import PatchFileChange" in source
    assert "class PatchFileChange" not in source
    assert "def parse_unified_diff" not in source


def test_baseline_module_does_not_import_judgment() -> None:
    source = (ROOT / "src/sourcepack/baseline.py").read_text(encoding="utf-8")
    assert "judgment" not in source


def test_baseline_module_owns_baseline_engine() -> None:
    baseline_source = (ROOT / "src/sourcepack/baseline.py").read_text(encoding="utf-8")
    judgment_source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    required = [
        "class BaselineLockError",
        "def baseline_corrupt_result",
        "def resolve_active_baseline",
        "def _validate_packet_artifacts",
        "def validate_baseline",
        "def acquire_baseline_lock",
        "def release_baseline_lock",
        "def _write_json_atomic",
        "def _unique_build_id",
        "def build_current_baseline",
        "def baseline_report_fields",
    ]
    assert [token for token in required if token not in baseline_source] == []
    forbidden = ["def validate_baseline", "def build_current_baseline", "def resolve_active_baseline"]
    assert [token for token in forbidden if token in judgment_source] == []


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


def test_judgment_facade_reexports_internal_engines() -> None:
    import sourcepack.ai_analysis as ai_analysis
    import sourcepack.judgment as judgment
    import sourcepack.repository_evidence as repository_evidence

    assert judgment.analyze_ai_answer is ai_analysis.analyze_ai_answer
    assert judgment.generate_reality_map is repository_evidence.generate_reality_map
    assert judgment.dependency_inventory is repository_evidence.dependency_inventory
    assert judgment.IncludedFile is repository_evidence.IncludedFile


def test_cli_has_no_copied_canonical_models_or_classifications() -> None:
    source = (ROOT / "src/sourcepack/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    copied = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in {"IncludedFile", "IgnoredFile"}
    }
    assigned_literals = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"COMMON_DEPENDENCIES", "FEATURE_NAMES", "SECRET_PATTERNS", "PROTECTED_PACKET_ARTIFACTS"}
        and isinstance(node.value, (ast.List, ast.Tuple, ast.Set, ast.Dict))
    }
    assert copied == set()
    assert assigned_literals == set()


def test_git_acquisition_is_owned_outside_facade() -> None:
    facade = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    acquisition = (ROOT / "src/sourcepack/git_acquisition.py").read_text(encoding="utf-8")
    assert "def worktree_dirty" in acquisition
    assert "return worktree_dirty(repo, run_git)" in facade


def test_cli_baseline_exports_are_compatibility_delegates() -> None:
    import sourcepack.baseline as baseline
    import sourcepack.cli as cli

    for name in (
        "acquire_baseline_lock",
        "baseline_corrupt_result",
        "baseline_report_fields",
        "build_current_baseline",
        "release_baseline_lock",
        "resolve_active_baseline",
        "validate_baseline",
    ):
        assert getattr(cli, name) is getattr(baseline, name)

    source = (ROOT / "src/sourcepack/cli.py").read_text(encoding="utf-8")
    assert "def _validate_packet_artifacts" not in source
    assert "def baseline_corrupt_result" not in source


def test_packet_interpretation_exports_delegate_to_repository_evidence() -> None:
    import sourcepack.packet as packet
    import sourcepack.repository_evidence as repository_evidence

    for name in (
        "dependency_inventory",
        "extract_refs",
        "feature_inventory",
        "generate_reality_map",
        "render_ai_instructions",
    ):
        assert getattr(packet, name) is getattr(repository_evidence, name)


def test_report_persistence_is_owned_by_reports_module() -> None:
    judgment_source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    reports_source = (ROOT / "src/sourcepack/reports/json.py").read_text(encoding="utf-8")
    assert "def write_auto_report" not in judgment_source
    assert "def finalize_user_report" in reports_source
    assert "return finalize_user_report(" in judgment_source


def test_command_center_does_not_import_workbench_implementation() -> None:
    source = (ROOT / "src/sourcepack/command_center.py").read_text(encoding="utf-8")
    assert "from .workbench import" not in source
    assert "from .command_center_state import" in source


def test_packet_load_manifest_preserves_non_object_json_compatibility(tmp_path) -> None:
    import sourcepack.packet as packet
    import sourcepack.repository_evidence as repository_evidence

    (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")
    assert packet.load_manifest(tmp_path) == []
    with pytest.raises(ValueError, match="packet manifest must be an object"):
        repository_evidence.load_manifest(tmp_path)
