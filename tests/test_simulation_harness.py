from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sourcepack.cli import judge_patch_text, judge_patch, judge_ai_answer, run_cli, validate_baseline
from tests.simulation_helpers import *


def py_import_patch(path: str, line: str) -> str:
    old = "VALUE = 1\n"
    return unified_patch(path, old, f"{line}\n{old}")


def js_import_patch(path: str, line: str) -> str:
    old = "export const value = 1;\n"
    return unified_patch(path, old, f"{line}\n{old}")


def scenario_cases() -> list[Scenario]:
    cases: list[Scenario] = []
    py_base = {"app.py": "VALUE = 1\n", "requirements.txt": "requests\nPyYAML\nbeautifulsoup4\n"}
    for mod in ["os", "sys", "json", "pathlib", "datetime"]:
        cases.append(Scenario(f"py_stdlib_{mod}", {"app.py": "VALUE = 1\n"}, py_import_patch("app.py", f"import {mod}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python no deps", summary="stdlib import"))
    for local, files in [("localmod", {"app.py": "VALUE = 1\n", "localmod.py": "X=1\n"}), ("localpkg", {"app.py": "VALUE = 1\n", "src/localpkg/__init__.py": "X=1\n"})]:
        cases.append(Scenario(f"py_local_{local}", files, py_import_patch("app.py", f"import {local}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python local", summary="local import"))
    for dep, line in [("requests", "import requests"), ("yaml", "import yaml"), ("bs4", "from bs4 import BeautifulSoup")]:
        cases.append(Scenario(f"py_declared_{dep}", py_base, py_import_patch("app.py", line), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="requirements runtime", summary="declared import"))
    for dep in ["fastapi", "flask", "django", "sqlalchemy", "boto3", "pydantic", "typer", "click", "dotenv"]:
        cases.append(Scenario(f"py_undeclared_{dep}", {"app.py": "VALUE = 1\n", "requirements.txt": ""}, py_import_patch("app.py", f"import {dep}"), MUST_RED, "unsupported_dependency", repo_shape="empty requirements", summary="undeclared import"))
    dev_files = {"app.py": "VALUE = 1\n", "requirements-dev.txt": "pytest\nrequests\n"}
    cases.append(Scenario("py_dev_runtime_scope", dev_files, py_import_patch("app.py", "import requests"), MUST_YELLOW, "dependency_scope_review", repo_shape="requirements-dev", summary="runtime imports dev dep"))
    cases.append(Scenario("py_dev_test_scope", {**dev_files, "tests/test_app.py": "VALUE = 1\n"}, py_import_patch("tests/test_app.py", "import requests"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="requirements-dev", summary="test imports dev dep"))
    pyproject_shapes = {
        "project_runtime": '[project]\ndependencies=["fastapi"]\n',
        "project_optional": '[project]\n[project.optional-dependencies]\ndev=["requests"]\n',
        "poetry_runtime": '[tool.poetry.dependencies]\npython=">=3.11"\nfastapi="*"\n',
        "poetry_group": '[tool.poetry.group.dev.dependencies]\nrequests="*"\n',
        "uv_group": '[dependency-groups]\ndev=["requests"]\n',
    }
    for name, text in pyproject_shapes.items():
        dep = "fastapi" if "runtime" in name else "requests"
        expectation = MUST_NOT_RED if "runtime" in name else MUST_YELLOW
        expected = None if expectation == MUST_NOT_RED else "dependency_scope_review"
        cases.append(Scenario(f"py_shape_{name}", {"app.py": "VALUE = 1\n", "pyproject.toml": text}, py_import_patch("app.py", f"import {dep}"), expectation, expected, forbidden_ids={"unsupported_dependency"}, repo_shape=name, summary="pyproject scope"))
    same_patch_shapes = [
        ("req_exact", "requirements.txt", "", "requests>=2\n", "import requests", MUST_YELLOW, "declared_dependency"),
        ("req_alias", "requirements.txt", "", "beautifulsoup4\n", "import bs4", MUST_YELLOW, "declared_dependency"),
        ("req_wrong", "requirements.txt", "", "flask\n", "import requests", MUST_RED, "unsupported_dependency"),
        ("pyproject_exact", "pyproject.toml", '[project]\ndependencies=[]\n', '[project]\ndependencies=["requests"]\n', "import requests", MUST_YELLOW, "declared_dependency"),
        ("pyproject_unrelated", "pyproject.toml", '[tool.demo]\ndeps=[]\n', '[tool.demo]\ndeps=["requests"]\n', "import requests", MUST_RED, "unsupported_dependency"),
    ]
    for name, manifest, old_m, new_m, import_line, exp, fid in same_patch_shapes:
        files = {"app.py": "VALUE = 1\n", manifest: old_m}
        patch = multi_patch([("app.py", "VALUE = 1\n", f"{import_line}\nVALUE = 1\n"), (manifest, old_m, new_m)])
        cases.append(Scenario(f"py_same_patch_{name}", files, patch, exp, fid, repo_shape="same patch python", summary=name))
    cases.append(Scenario("py_wrong_ecosystem_js_dep", {"app.py": "VALUE = 1\n", "package.json": "{}\n"}, multi_patch([("app.py", "VALUE = 1\n", "import requests\nVALUE = 1\n"), ("package.json", "{}\n", '{"dependencies":{"requests":"1"}}\n')]), MUST_RED, "unsupported_dependency", repo_shape="wrong ecosystem", summary="js dep cannot support python"))

    js_runtime = {"index.js": "export const value = 1;\n", "package.json": '{"dependencies":{"react":"18","@scope/pkg":"1"},"devDependencies":{"vite":"1"}}\n'}
    for spec in ["react", "react/jsx-runtime", "@scope/pkg", "@scope/pkg/sub"]:
        cases.append(Scenario(f"js_declared_{spec.replace('/', '_')}", js_runtime, js_import_patch("index.js", f'import x from "{spec}";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="package runtime", summary="declared js import"))
    for spec in ["vue", "@missing/pkg", "@missing/pkg/sub"]:
        cases.append(Scenario(f"js_undeclared_{spec.replace('/', '_')}", {"index.js": "export const value = 1;\n", "package.json": "{}\n"}, js_import_patch("index.js", f'import x from "{spec}";'), MUST_RED, "unsupported_dependency", repo_shape="empty package", summary="undeclared js import"))
    cases.append(Scenario("js_dev_runtime_scope", js_runtime, js_import_patch("index.js", 'import vite from "vite";'), MUST_YELLOW, "dependency_scope_review", repo_shape="dev dependency", summary="runtime imports devDependency"))
    cases.append(Scenario("js_dev_test_scope", {**js_runtime, "app.test.js": "export const value = 1;\n"}, js_import_patch("app.test.js", 'import vite from "vite";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="dev dependency", summary="test imports devDependency"))
    alias_files = {"view.ts": "export const value = 1;\n", "src/components/Button.ts": "export const Button = 1\n", "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', "package.json": "{}\n"}
    cases.append(Scenario("js_alias_resolved", alias_files, js_import_patch("view.ts", 'import { Button } from "@/components/Button";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="ts paths", summary="resolved alias"))
    cases.append(Scenario("js_alias_unresolved", {"view.ts": "export const value = 1;\n", "package.json": "{}\n"}, js_import_patch("view.ts", 'import { Button } from "@/components/Button";'), MUST_YELLOW, "js_alias_uncertain", repo_shape="no aliases", summary="unresolved alias"))
    workspace_files = {"index.js": "export const value = 1;\n", "package.json": '{"workspaces":["packages/*"]}', "packages/core/package.json": '{"name":"@myorg/core"}\n'}
    for spec in ["@myorg/core", "@myorg/core/utils"]:
        cases.append(Scenario(f"js_workspace_{spec.replace('/', '_')}", workspace_files, js_import_patch("index.js", f'import x from "{spec}";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="workspace", summary="workspace import"))
    js_same = [
        ("exact", "{}\n", '{"dependencies":{"react":"18"}}\n', 'import React from "react";', MUST_YELLOW, "declared_dependency"),
        ("subpath", "{}\n", '{"dependencies":{"react":"18"}}\n', 'import runtime from "react/jsx-runtime";', MUST_YELLOW, "declared_dependency"),
        ("dev", "{}\n", '{"devDependencies":{"vite":"1"}}\n', 'import vite from "vite";', MUST_YELLOW, "declared_dependency"),
        ("wrong", "{}\n", '{"dependencies":{"vue":"3"}}\n', 'import React from "react";', MUST_RED, "unsupported_dependency"),
        ("script_not_dep", "{}\n", '{"scripts":{"react":"echo no"}}\n', 'import React from "react";', MUST_RED, "unsupported_dependency"),
    ]
    for name, old_pkg, new_pkg, import_line, exp, fid in js_same:
        cases.append(Scenario(f"js_same_patch_{name}", {"index.js": "export const value = 1;\n", "package.json": old_pkg}, multi_patch([("index.js", "export const value = 1;\n", f"{import_line}\nexport const value = 1;\n"), ("package.json", old_pkg, new_pkg)]), exp, fid, repo_shape="same patch js", summary=name))
    cases.append(Scenario("js_wrong_ecosystem_py_dep", {"index.js": "export const value = 1;\n", "requirements.txt": ""}, multi_patch([("index.js", "export const value = 1;\n", 'import React from "react";\nexport const value = 1;\n'), ("requirements.txt", "", "react\n")]), MUST_RED, "unsupported_dependency", repo_shape="wrong ecosystem", summary="python dep cannot support js"))

    command_files = {"README.md": "demo\n", "package.json": '{"scripts":{"dev":"vite","build":"vite build","test":"vitest"}}\n', "compose.yaml": "services: {}\n", "tests/test_app.py": "def test_x(): pass\n", "requirements.txt": "pytest\n"}
    for cmd in ["npm run dev", "npm run build", "npm test", "docker compose up", "pytest", "python -m pytest"]:
        cases.append(Scenario(f"cmd_supported_{cmd.replace(' ', '_')}", command_files, unified_patch("README.md", "demo\n", f"Run {cmd}\n"), MUST_NOT_RED, forbidden_ids={"unsupported_command"}, repo_shape="commands supported", summary=cmd))
    for cmd in ["npm run dev", "npm run build", "docker compose up", "pytest"]:
        cases.append(Scenario(f"cmd_unsupported_{cmd.replace(' ', '_')}", {"README.md": "demo\n", "package.json": "{}\n"}, unified_patch("README.md", "demo\n", f"Run {cmd}\n"), MUST_RED, "unsupported_command", repo_shape="commands unsupported", summary=cmd))
    cases.append(Scenario("cmd_same_patch_script_exact", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{"dev":"vite"}}\n')]), MUST_YELLOW, "declared_command", repo_shape="same patch script", summary="exact script"))
    cases.append(Scenario("cmd_same_patch_script_wrong", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run build\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{"dev":"vite"}}\n')]), MUST_RED, "unsupported_command", repo_shape="same patch script", summary="wrong script"))
    cases.append(Scenario("cmd_same_patch_script_under_wrong_object", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{},"metadata":{"dev":"vite"}}\n')]), MUST_RED, "unsupported_command", forbidden_ids={"declared_command"}, repo_shape="same patch script", summary="script-like key outside scripts"))
    cases.append(Scenario("cmd_same_patch_script_existing_object", {"README.md": "demo\n", "package.json": '{"scripts":{"test":"vitest"}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{"test":"vitest"}}\n', '{"scripts":{"test":"vitest","dev":"vite"}}\n')]), MUST_YELLOW, "declared_command", repo_shape="same patch script", summary="script added to existing scripts"))
    cases.append(Scenario("cmd_same_patch_compose", {"README.md": "demo\n"}, unified_patch("README.md", "demo\n", "Run docker compose up\n") + unified_patch("compose.yaml", "", "services: {}\n", new_file=True), MUST_YELLOW, "declared_command", repo_shape="same patch compose", summary="compose added"))

    protected = [".sourcepack/baseline/active.json", "src/../.sourcepack/baseline/active.json", "./.sourcepack/baseline/active.json", ".sourcepack\\baseline\\active.json", ".sourcepack/state/baseline.lock"]
    for path in protected:
        cases.append(Scenario(f"protected_{path}", {path.replace('\\', '/'): "{}\n"}, unified_patch(path, "{}\n", '{"x":true}\n'), MUST_RED, "protected_artifact", repo_shape="protected paths", summary=path))
    for path in ["manifest.json", "receipt.json", "docs/receipt.json", "public/manifest.json", "fixtures/manifest.json", "examples/.sourcepack/baseline/active.json"]:
        cases.append(Scenario(f"normal_{path}", {path: "{}\n"}, unified_patch(path, "{}\n", '{"x":true}\n'), MUST_NOT_RED, forbidden_ids={"protected_artifact"}, repo_shape="normal paths", summary=path))
    for path in ["../outside.txt", "docs/../../.sourcepack/state/baseline.lock", "/tmp/file.txt"]:
        cases.append(Scenario(f"escape_{path}", {"app.py": "VALUE = 1\n"}, unified_patch(path, "old\n", "new\n"), MUST_FAIL_CLOSED, "path_escape", repo_shape="path escape", summary=path))

    malformed = ["not a unified diff\n", "@@ -1 +1 @@\n+x\n", "diff --git a/a.py b/a.py\n", "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ nope\n+x\n"]
    for i, patch in enumerate(malformed):
        cases.append(Scenario(f"malformed_{i}", {"a.py": "x\n"}, patch, MUST_FAIL_CLOSED, "malformed_diff", repo_shape="malformed", summary=str(i)))
    cases.append(Scenario("binary_ordinary", {"a.py": "x\n"}, "diff --git a/img.png b/img.png\nBinary files a/img.png and b/img.png differ\n", MUST_YELLOW, "binary_diff", repo_shape="binary", summary="ordinary binary"))
    cases.append(Scenario("binary_high_risk", {"a.py": "x\n"}, "diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\nBinary files a/.sourcepack/baseline/active.json and b/.sourcepack/baseline/active.json differ\n", MUST_RED, "binary_diff", repo_shape="binary", summary="trust binary"))
    cases.append(Scenario("new_file", {"a.py": "x\n"}, unified_patch("new.py", "", "import os\n", new_file=True), MUST_YELLOW, "new_file", repo_shape="edge", summary="new file"))
    cases.append(Scenario("deleted_file", {"a.py": "x\n"}, unified_patch("a.py", "x\n", "", deleted=True), MUST_YELLOW, "deleted_file", repo_shape="edge", summary="deleted file"))
    for i, mod in enumerate(["csv", "hashlib", "collections", "itertools", "functools", "typing", "unittest", "subprocess", "re", "math", "decimal", "sqlite3", "http", "email"]):
        cases.append(Scenario(f"py_stdlib_extra_{i}_{mod}", {"app.py": "VALUE = 1\n"}, py_import_patch("app.py", f"import {mod}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python no deps", summary="extra stdlib coverage"))
    for script in ["lint", "typecheck", "format", "start"]:
        files = {"README.md": "demo\n", "package.json": f'{{"scripts":{{"{script}":"echo ok"}}}}\n'}
        cases.append(Scenario(f"cmd_supported_extra_{script}", files, unified_patch("README.md", "demo\n", f"Run npm run {script}\n"), MUST_NOT_RED, forbidden_ids={"unsupported_command"}, repo_shape="extra scripts", summary=script))
    return cases


SCENARIOS = scenario_cases()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_patch_simulation_scenarios(tmp_path: Path, scenario: Scenario) -> None:
    packet = write_packet(tmp_path, scenario.files)
    report = judge_patch_text(packet, scenario.patch)
    assert_expectation(scenario, report)


def test_simulation_count() -> None:
    assert len(SCENARIOS) >= 100



def test_ai_answer_simulation_catches_fake_claims(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "package.json": '{"scripts":{"dev":"vite"}}\n'})
    answer = tmp_path / "answer.md"
    answer.write_text(
        "Edit `src/auth.py`, import requests, run npm run build, use docker compose up, and add database support.\n",
        encoding="utf-8",
    )
    report = judge_ai_answer(packet, answer)
    assert report["verdict"] == "FAIL"
    assert "src/auth.py" in report["missing_files"]
    assert "requests" in {dep.lower() for dep in report["unsupported_dependencies"]}
    assert "npm run build" in report["unsupported_commands"]
    assert "docker compose up" in report["unsupported_commands"]
    assert "database" in report["unsupported_capabilities"]


def test_ai_answer_simulation_accepts_supported_claims(tmp_path: Path) -> None:
    packet = write_packet(
        tmp_path,
        {
            "app.py": "import requests\nVALUE = 1\n",
            "requirements.txt": "requests\npytest\n",
            "package.json": '{"scripts":{"dev":"vite","test":"vitest"}}\n',
            "compose.yaml": "services: {}\n",
            "tests/test_app.py": "def test_x(): pass\n",
        },
    )
    answer = tmp_path / "answer.md"
    answer.write_text("Edit `app.py`, then run npm run dev, npm test, pytest, and docker compose up.\n", encoding="utf-8")
    report = judge_ai_answer(packet, answer)
    assert report["verdict"] == "PASS"
    assert report["missing_files"] == []
    assert report["unsupported_commands"] == []


def test_non_utf8_patch_file_fails_closed(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"a.py": "x\n"})
    patch = tmp_path / "bad.diff"
    patch.write_bytes(b"\xff\xfe")
    out = tmp_path / "out"
    report = judge_patch(packet, patch, out)
    assert_expectation(Scenario("non_utf8", {"a.py": "x\n"}, "", MUST_FAIL_CLOSED, "malformed_diff"), report)


def test_baseline_state_cli_smoke() -> None:
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (repo / "app.py").write_text("import requests\nVALUE = 1\n", encoding="utf-8")
        code = run_cli(["diff", str(repo), "--json"])
        assert code == 1
        assert validate_baseline(repo)["state"] == "missing"
        code = run_cli(["baseline", str(repo), "--quiet"])
        assert code in {0, 1}
        (repo / ".sourcepack" / "baseline" / "active.json").write_text("not json", encoding="utf-8")
        status = validate_baseline(repo)
        assert status["state"] == "corrupt"
        assert status["finding_id"] == "baseline_corrupt"
