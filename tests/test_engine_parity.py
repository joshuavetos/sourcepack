from __future__ import annotations

import ast
import json
from pathlib import Path

from sourcepack import cli, judgment
from tests.simulation_helpers import unified_patch, write_packet


STABLE_PATCH_FIELDS = (
    "verdict",
    "modified_files",
    "missing_modified_files",
    "new_files",
    "deleted_files",
    "unsupported_dependencies",
    "unsupported_commands",
    "protected_artifact_modifications",
    "git_path_modifications",
    "warnings",
    "uncertainties",
)


def _stable_patch(report: dict) -> dict:
    return {field: report.get(field, []) for field in STABLE_PATCH_FIELDS}


def test_cli_patch_exports_are_canonical_compatibility_aliases() -> None:
    assert cli.analyze_patch is judgment.analyze_patch
    assert cli.judge_patch_text is judgment.judge_patch_text
    assert cli.patch_report_to_traffic is judgment.patch_report_to_traffic
    assert cli.build_repo_change_report is judgment.build_repo_change_report


def test_packet_command_and_programmatic_engine_have_stable_parity(tmp_path: Path, capsys) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "requirements.txt": "\n"})
    patch_text = unified_patch("app.py", "VALUE = 1\n", "import requests\nVALUE = 1\n")
    patch_path = tmp_path / "change.diff"
    patch_path.write_text(patch_text, encoding="utf-8")

    canonical = judgment.judge_patch_text(packet, patch_text)
    command = cli.judge_patch(packet, patch_path, tmp_path / "report")

    assert _stable_patch(command) == _stable_patch(canonical)
    assert command["traffic"]["verdict"] == canonical["verdict"]
    assert {item["id"] for item in command["findings"]} == {
        item["id"] for item in judgment.patch_report_to_traffic(canonical)["findings"]
    }
    capsys.readouterr()


def test_ai_answer_command_adapter_uses_canonical_analysis(tmp_path: Path, capsys) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n"})
    answer = tmp_path / "answer.md"
    text = "Update `missing.py` and run npm run invented."
    answer.write_text(text, encoding="utf-8")

    assert cli.judge_ai_answer(packet, answer) == judgment.analyze_ai_answer(packet, text)
    capsys.readouterr()


def test_cli_has_no_independent_canonical_analysis_definitions() -> None:
    root = Path(__file__).resolve().parents[1]
    cli_tree = ast.parse((root / "src/sourcepack/cli.py").read_text(encoding="utf-8"))
    judgment_tree = ast.parse((root / "src/sourcepack/judgment.py").read_text(encoding="utf-8"))
    cli_functions = {node.name for node in cli_tree.body if isinstance(node, ast.FunctionDef)}
    judgment_functions = {node.name for node in judgment_tree.body if isinstance(node, ast.FunctionDef)}

    # These are presentation/persistence adapters, not judgment computation.
    allowed_adapters = {"finalize_diff_report", "write_auto_report"}
    assert cli_functions & judgment_functions == allowed_adapters
    assert "def analyze_patch" not in (root / "src/sourcepack/cli.py").read_text(encoding="utf-8")
    assert "def judge_patch_text" not in (root / "src/sourcepack/cli.py").read_text(encoding="utf-8")


def test_parity_projection_is_json_stable(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n"})
    report = judgment.judge_patch_text(packet, unified_patch("new.py", "", "VALUE = 1\n", new_file=True))
    assert json.loads(json.dumps(_stable_patch(report), sort_keys=True)) == _stable_patch(report)
