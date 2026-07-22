from __future__ import annotations

import json

from sourcepack.analysis import AnalysisStatus
from sourcepack.commands import resolve_command
from sourcepack.dependencies import resolve_js_import, resolve_python_import


def test_same_patch_python_dependency_is_patch_evidence_not_trusted_pass(tmp_path):
    result = resolve_python_import(
        tmp_path,
        "requests",
        added_dependencies={"requests"},
    )

    assert result.verdict == "WARN"
    assert result.reason_code == "declared_dependency"
    assert result.evidence_source == "patch"
    assert result.message == "dependency added in same patch"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "proposed_state"
    assert result.trust_status == "untrusted_until_accepted"
    assert result.modified_by_patch is True


def test_preexisting_python_dependency_can_be_trusted_pass(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests>=2\n", encoding="utf-8")

    result = resolve_python_import(tmp_path, "requests")

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.evidence_source == "requirements.txt"
    assert result.message == "declared"
    assert result.analysis_status == AnalysisStatus.SUPPORTED.value
    assert result.evidence_class == "dependency_manifest"
    assert result.trust_status == "trusted_preexisting"
    assert result.modified_by_patch is False


def test_malformed_pyproject_fails_closed_instead_of_looking_undeclared(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project\ndependencies = ["requests"]\n',
        encoding="utf-8",
    )

    result = resolve_python_import(tmp_path, "requests")

    assert result.verdict == "FAIL"
    assert result.reason_code == "manifest_parse_failure"
    assert result.analysis_status == AnalysisStatus.UNREVIEWABLE.value
    assert result.evidence_source == "pyproject.toml"
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "invalid"


def test_same_patch_js_dependency_is_proposed_evidence_not_trusted_pass(tmp_path):
    result = resolve_js_import(
        tmp_path,
        "axios",
        added_dependencies={"axios"},
    )

    assert result.verdict == "WARN"
    assert result.reason_code == "declared_dependency"
    assert result.dependency == "axios"
    assert result.evidence_source == "patch"
    assert result.message == "dependency added in same patch"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "proposed_state"
    assert result.trust_status == "untrusted_until_accepted"
    assert result.modified_by_patch is True


def test_same_patch_scoped_js_dependency_normalizes_subpath(tmp_path):
    result = resolve_js_import(
        tmp_path,
        "@scope/pkg/subpath",
        added_dependencies={"@scope/pkg"},
    )

    assert result.verdict == "WARN"
    assert result.reason_code == "declared_dependency"
    assert result.dependency == "@scope/pkg"
    assert result.evidence_class == "proposed_state"
    assert result.modified_by_patch is True


def test_preexisting_js_dependency_can_be_trusted_pass(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"axios": "^1.0.0"}}),
        encoding="utf-8",
    )

    result = resolve_js_import(tmp_path, "axios")

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.evidence_source == "package.json dependencies"
    assert result.analysis_status == AnalysisStatus.SUPPORTED.value
    assert result.evidence_class == "dependency_manifest"
    assert result.trust_status == "trusted_preexisting"
    assert result.modified_by_patch is False


def test_preexisting_js_dev_dependency_requires_scope_review(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"vitest": "^2.0.0"}}),
        encoding="utf-8",
    )

    result = resolve_js_import(tmp_path, "vitest")

    assert result.verdict == "WARN"
    assert result.reason_code == "dependency_scope_review"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "dependency_manifest"
    assert result.trust_status == "trusted_preexisting"
    assert result.modified_by_patch is False


def test_relative_js_import_does_not_consult_added_dependency_evidence(tmp_path):
    result = resolve_js_import(
        tmp_path,
        "./local.js",
        added_dependencies={"./local.js"},
    )

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.evidence_class == "current_worktree"
    assert result.modified_by_patch is False


def test_malformed_package_json_fails_closed_instead_of_looking_undeclared(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^18"}',
        encoding="utf-8",
    )

    result = resolve_js_import(tmp_path, "react")

    assert result.verdict == "FAIL"
    assert result.reason_code == "manifest_parse_failure"
    assert result.analysis_status == AnalysisStatus.UNREVIEWABLE.value
    assert result.evidence_source == "package.json"
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "invalid"


def test_same_patch_npm_script_is_patch_evidence_not_trusted_pass(tmp_path):
    added_package_json = json.dumps(
        {
            "scripts": {
                "build": "node build.js",
            }
        }
    )

    result = resolve_command(
        tmp_path,
        "npm run build",
        added_manifests={"package.json": added_package_json},
    )

    assert result.verdict == "WARN"
    assert result.reason_code == "declared_command"
    assert result.evidence_source == "package.json"
    assert result.message == "script added in patch"


def test_preexisting_npm_script_can_be_trusted_pass(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "build": "node build.js",
                }
            }
        ),
        encoding="utf-8",
    )

    result = resolve_command(tmp_path, "npm run build")

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.evidence_source == "package.json"
    assert result.message == "script present"
