import json
import subprocess
import sys
from pathlib import Path

from sourcepack.cli import patch_report_to_traffic, validate_baseline
from sourcepack.judgment import judge_patch_text


def run_sourcepack(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def init_repo(repo: Path, files: dict[str, str | bytes]) -> Path:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "ugly@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Ugly Repo"], cwd=repo, check=True)
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    baseline = run_sourcepack(repo, "baseline", "refresh", "--force")
    assert baseline.returncode == 0, baseline.stderr + baseline.stdout
    return repo


def diff_json(repo: Path) -> tuple[int, dict]:
    cp = run_sourcepack(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def finding_ids(report: dict) -> set[str]:
    return {finding.get("id") for finding in report.get("findings", [])}


def judge_patch_json(repo: Path, patch: str) -> dict:
    packet = repo / validate_baseline(repo)["packet_path"]
    return patch_report_to_traffic(judge_patch_text(packet, patch))


def test_python_src_layout_supported_file_edit(tmp_path):
    repo = init_repo(
        tmp_path,
        {
            "pyproject.toml": "[project]\nname = 'ugly-src'\ndependencies = []\n",
            "src/ugly_pkg/__init__.py": "VALUE = 1\n",
            "src/ugly_pkg/core.py": "def value():\n    return 1\n",
            "tests/test_core.py": "from ugly_pkg.core import value\n",
        },
    )
    (repo / "src" / "ugly_pkg" / "core.py").write_text("def value():\n    return 2\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "PASS"
    assert "unsupported_dependency" not in finding_ids(data)
    assert "missing_file" not in finding_ids(data)


def test_flat_python_layout_undeclared_import(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "def main():\n    return 1\n", "requirements.txt": ""})
    (repo / "app.py").write_text("import fastapi\n\ndef main():\n    return fastapi.FastAPI()\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 1
    assert data["verdict"] == "FAIL"
    assert "unsupported_dependency" in finding_ids(data)


def test_scripts_only_repo_unsupported_command_assumption(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "Scripts are kept in bin/.\n", "bin/lint": "#!/bin/sh\nexit 0\n"})
    (repo / "README.md").write_text("Scripts are kept in bin/.\nRun " + "docker compose" + " up to publish.\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 1
    assert data["verdict"] == "FAIL"
    assert "unsupported_command" in finding_ids(data)
    assert any(f.get("evidence") == "docker compose" + " up" for f in data["findings"] if f.get("id") == "unsupported_command")


def test_docs_only_repo_allowed_docs_new_file_policy(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "Docs only\n"})
    policy_dir = repo / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(
        json.dumps({"schema_version": "sourcepack.policy.v1", "ignored_paths": [{"pattern": "docs/**", "reason": "docs reviewed separately"}]}),
        encoding="utf-8",
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    ids = finding_ids(data)
    assert "new_file" not in {f.get("id") for f in data["findings"] if f.get("path") == "docs/guide.md"}
    assert "policy_override" in ids
    assert data["policy_config_ignores"][0]["suppressed_finding"] == "new_file"


def test_workflow_only_change_reports_workflow_change(tmp_path):
    repo = init_repo(tmp_path, {".github/workflows/ci.yml": "name: ci\non: [push]\njobs: {}\n"})
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: [push, pull_request]\njobs: {}\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "workflow_change" in finding_ids(data)


def test_protected_sourcepack_edit_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json
--- a/.sourcepack/baseline/active.json
+++ b/.sourcepack/baseline/active.json
@@ -1 +1 @@
-{}
+{\"tamper\": true}
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "protected_artifact" in finding_ids(data)


def test_git_path_edit_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/.git/config b/.git/config
--- a/.git/config
+++ b/.git/config
@@ -1 +1 @@
-a
+b
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "git_path_modification" in finding_ids(data)


def test_unsafe_path_normalization_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/../outside.txt b/../outside.txt
--- a/../outside.txt
+++ b/../outside.txt
@@ -1 +1 @@
-a
+b
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "malformed_diff" in finding_ids(data)


def test_binary_asset_change_warns_with_binary_diff(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "assets\n"})
    (repo / "assets").mkdir()
    (repo / "assets" / "logo.bin").write_bytes(b"\x00\x01\x02\x03")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "binary_diff" in finding_ids(data)


def test_unsupported_ecosystem_layout_warns_without_crashing(tmp_path):
    repo = init_repo(tmp_path, {"Cargo.toml": "[package]\nname = 'ugly-rust'\nversion = '0.1.0'\n", "src/lib.rs": "pub fn value() -> u8 { 1 }\n"})
    (repo / "src" / "lib.rs").write_text("pub fn value() -> u8 { 2 }\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "unsupported_ecosystem" in finding_ids(data)
    assert "semantic correctness" in data.get("not_checked", [])
