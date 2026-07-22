from __future__ import annotations

import json

from sourcepack.commands import resolve_command
from sourcepack.dependencies import resolve_python_import


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


def test_preexisting_python_dependency_can_be_trusted_pass(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests>=2\n", encoding="utf-8")

    result = resolve_python_import(tmp_path, "requests")

    assert result.verdict == "PASS"
    assert result.reason_code is None
    assert result.evidence_source == "requirements.txt"
    assert result.message == "declared"


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
