from __future__ import annotations

import json

from sourcepack.analysis import AnalysisStatus
from sourcepack.commands import resolve_command


def test_same_patch_npm_script_is_proposed_evidence(tmp_path):
    result = resolve_command(
        tmp_path,
        "npm run build",
        added_manifests={
            "package.json": json.dumps({"scripts": {"build": "node build.js"}}),
        },
    )

    assert result.verdict == "WARN"
    assert result.reason_code == "declared_command"
    assert result.evidence_source == "package.json"
    assert result.message == "script added in patch"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "proposed_state"
    assert result.trust_status == "untrusted_until_accepted"
    assert result.modified_by_patch is True


def test_preexisting_npm_script_is_trusted_support(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"build": "node build.js"}}),
        encoding="utf-8",
    )

    result = resolve_command(tmp_path, "npm run build")

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.analysis_status == AnalysisStatus.SUPPORTED.value
    assert result.evidence_class == "command_manifest"
    assert result.trust_status == "trusted_preexisting"
    assert result.modified_by_patch is False


def test_malformed_preexisting_package_json_fails_closed(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"build": "node build.js"}',
        encoding="utf-8",
    )

    result = resolve_command(tmp_path, "npm run build")

    assert result.verdict == "FAIL"
    assert result.reason_code == "manifest_parse_failure"
    assert result.analysis_status == AnalysisStatus.UNREVIEWABLE.value
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "invalid"
    assert result.modified_by_patch is False


def test_malformed_proposed_package_json_fails_closed(tmp_path):
    result = resolve_command(
        tmp_path,
        "npm run build",
        added_manifests={
            "package.json": '{"scripts": {"build": "node build.js"}',
        },
    )

    assert result.verdict == "FAIL"
    assert result.reason_code == "manifest_parse_failure"
    assert result.analysis_status == AnalysisStatus.UNREVIEWABLE.value
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "invalid"
    assert result.modified_by_patch is True


def test_missing_npm_manifest_is_explicitly_unknown(tmp_path):
    result = resolve_command(tmp_path, "npm run build")

    assert result.verdict == "WARN"
    assert result.reason_code == "command_manifest_missing"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "missing"


def test_missing_preexisting_npm_script_is_unsupported(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "pytest"}}),
        encoding="utf-8",
    )

    result = resolve_command(tmp_path, "npm run build")

    assert result.verdict == "FAIL"
    assert result.reason_code == "unsupported_command"
    assert result.analysis_status == AnalysisStatus.UNSUPPORTED.value
    assert result.evidence_class == "command_manifest"
    assert result.trust_status == "trusted_preexisting"


def test_unsupported_parser_is_explicitly_unknown(tmp_path):
    result = resolve_command(tmp_path, "custom-tool deploy")

    assert result.verdict == "WARN"
    assert result.reason_code == "command_check_inconclusive"
    assert result.analysis_status == AnalysisStatus.UNKNOWN.value
    assert result.evidence_class == "analysis_state"
    assert result.trust_status == "unknown"
