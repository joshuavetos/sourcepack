import json

import pytest

from sourcepack.cli import run_cli
from sourcepack.judgment import judge_patch_text
from sourcepack.repository_evidence import dependency_inventory, load_manifest
from tests.simulation_helpers import multi_patch, write_packet


NON_OBJECT_JSON = ["[]", "null", '"react"', "42", "true", "false"]


@pytest.mark.parametrize("content", NON_OBJECT_JSON)
def test_build_handles_non_object_package_json(tmp_path, content):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(content + "\n", encoding="utf-8")
    packet = tmp_path / "packet"

    assert run_cli(["build", str(repo), "--out", str(packet)]) == 0
    assert dependency_inventory(load_manifest(packet), packet) == set()
    assert run_cli(["verify", str(packet)]) == 0


@pytest.mark.parametrize("content", NON_OBJECT_JSON)
def test_non_object_baseline_does_not_support_imports(tmp_path, content):
    old = "console.log('baseline');\n"
    packet = write_packet(tmp_path, {"package.json": content + "\n", "app.js": old})
    patch = multi_patch([("app.js", old, "import React from 'react';\n" + old)])

    report = judge_patch_text(packet, patch)

    assert report["verdict"] == "FAIL"
    assert "react" in report["unsupported_dependencies"]


@pytest.mark.parametrize("content", NON_OBJECT_JSON)
def test_non_object_proposed_manifest_requires_review(tmp_path, content):
    packet = write_packet(tmp_path, {"package.json": "{}\n"})
    patch = multi_patch([("package.json", "{}\n", content + "\n")])

    report = judge_patch_text(packet, patch)

    assert report["verdict"] != "PASS"
    ids = {item["id"] for item in report.get("uncertainties", [])}
    assert {"dependency_manifest_uncertain", "command_manifest_uncertain"} <= ids


@pytest.mark.parametrize("content", NON_OBJECT_JSON)
def test_non_object_workspace_manifest_does_not_support_imports(tmp_path, content):
    old = "console.log('baseline');\n"
    packet = write_packet(tmp_path, {
        "package.json": json.dumps({"workspaces": ["packages/*"]}) + "\n",
        "packages/broken/package.json": content + "\n",
        "app.js": old,
    })
    patch = multi_patch([("app.js", old, "import React from 'react';\n" + old)])

    report = judge_patch_text(packet, patch)

    assert report["verdict"] == "FAIL"
    assert "react" in report["unsupported_dependencies"]
