import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import run_cli, validate_baseline, judge_patch_text, build_current_baseline


def capture_cli(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = run_cli(args)
    return code, out.getvalue()


class GauntletTest(unittest.TestCase):
    def make_repo(self, tmp: Path, files: dict[str, str | bytes]) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        for rel, content in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        code, _ = capture_cli(["baseline", str(repo), "--quiet"])
        self.assertEqual(code, 0)
        return repo

    def diff_json(self, repo: Path, staged: bool = False):
        args = ["diff", str(repo)] + (["--staged"] if staged else []) + ["--json"]
        code, text = capture_cli(args)
        return code, json.loads(text)

    def ids(self, report: dict) -> set[str]:
        return {f["id"] for f in report.get("findings", [])}

    def test_clean_supported_edit_is_scoped_green(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value():\n    return 1\n", "requirements.txt": ""})
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "PASS")
            self.assertEqual(data["light"], "GREEN LIGHT")
            self.assertIn("Python imports", data["checked_categories"])
            self.assertIn("semantic correctness", data["not_checked"])

    def test_new_helper_file_is_yellow_review_not_dependency_red(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
            (repo / "helper.py").write_text("import os\nfrom pathlib import Path\nVALUE = Path(os.getcwd()).name\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertEqual(data["reason_type"], "review")
            self.assertIn("new_file", self.ids(data))
            self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_python_dependencies_stdlib_aliases_and_local_imports(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "localmod.py": "X = 1\n", "src/localpkg/__init__.py": "Y = 1\n", "requirements.txt": "PyYAML\nPillow\n"})
            (repo / "app.py").write_text("import os\nimport sys\nimport json\nimport pathlib\nimport yaml\nfrom PIL import Image\nimport localmod\nimport localpkg\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertNotIn("unsupported_dependency", self.ids(data))
            self.assertNotEqual(data["verdict"], "FAIL")
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
            (repo / "app.py").write_text("import yaml\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertIn("unsupported_dependency", self.ids(data))
            self.assertTrue(any(f.get("evidence") == "yaml" for f in data["findings"]))
        if hasattr(sys, "stdlib_module_names") and "tomllib" in sys.stdlib_module_names:
            with TemporaryDirectory() as td:
                repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
                (repo / "app.py").write_text("import tomllib\n", encoding="utf-8")
                code, data = self.diff_json(repo)
                self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_python_fastapi_declared_and_undeclared(self):
        for declared, should_fail in [("", True), ("fastapi\n", False)]:
            with self.subTest(declared=bool(declared)):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": declared})
                    (repo / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
                    code, data = self.diff_json(repo)
                    self.assertEqual(code, 1 if should_fail else 0)
                    self.assertEqual("unsupported_dependency" in self.ids(data), should_fail)

    def test_js_declared_undeclared_scoped_alias_and_workspace(self):
        cases = [
            ({"package.json": '{"dependencies": {}}', "app.js": "console.log(1)\n"}, "view.js", 'import React from "react"\n', True),
            ({"package.json": '{"dependencies": {"react":"latest", "@scope/pkg":"1.0.0"}}', "app.js": "console.log(1)\n"}, "view.js", 'import React from "react"\nimport x from "@scope/pkg"\n', False),
            ({"package.json": '{"workspaces": ["packages/*"]}', "packages/core/package.json": '{"name":"@myorg/core"}', "app.js": "console.log(1)\n"}, "use.js", 'import { shared } from "@myorg/core"\n', False),
            ({"package.json": '{}', "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', "src/components/Button.ts": "export const Button = 1\n", "app.ts": "console.log(1)\n"}, "view.ts", 'import { Button } from "@/components/Button"\n', False),
        ]
        for files, changed, content, should_fail in cases:
            with self.subTest(content=content):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), files)
                    (repo / changed).write_text(content, encoding="utf-8")
                    code, data = self.diff_json(repo)
                    self.assertEqual("unsupported_dependency" in self.ids(data), should_fail)

    def test_npm_and_compose_same_patch_support_exactness(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{"scripts":{}}', "README.md": "demo\n"})
            (repo / "README.md").write_text("Run npm run dev\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertIn("unsupported_command", self.ids(data))
        patch = """diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1 @@
-{"scripts":{}}
+{"scripts":{"dev":"vite"}}
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-demo
+Run npm run dev and npm run build
"""
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{"scripts":{}}', "README.md": "demo\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, patch)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("npm run build", report["unsupported_commands"])
            self.assertNotIn("npm run dev", report["unsupported_commands"])
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"README.md": "demo\n"})
            (repo / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
            (repo / "README.md").write_text("Run docker compose up\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertNotIn("unsupported_command", self.ids(data))

    def test_protected_scope_root_manifest_and_sourcepack_trust(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"manifest.json": "{}\n", "docs/receipt.json": "{}\n"})
            (repo / "manifest.json").write_text('{"project":true}\n', encoding="utf-8")
            (repo / "docs" / "receipt.json").write_text('{"project":true}\n', encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertNotIn("protected_artifact", self.ids(data))
            packet = repo / validate_baseline(repo)["packet_path"]
            patch = """diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json
--- a/.sourcepack/baseline/active.json
+++ b/.sourcepack/baseline/active.json
@@ -1 +1 @@
-{}
+{"tamper": true}
"""
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(judge_patch_text(packet, patch))
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("protected_artifact", {f["id"] for f in traffic["findings"]})

    def test_unsupported_ecosystem_stale_binary_malformed_and_prompt(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"Cargo.toml": "[package]\nname='demo'\n", "src/lib.rs": "pub fn x(){}\n"})
            (repo / "src" / "lib.rs").write_text("pub fn x(){ }\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertIn("unsupported_ecosystem: Cargo.toml detected, but Rust dependency validation is not implemented", self.ids(data))
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            (repo / "asset.bin").write_bytes(b"\x00\x01\x02")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertIn("binary_diff", self.ids(data))
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, "not a unified diff\n")
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("malformed_diff", {f["id"] for f in traffic["findings"]})
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            (repo / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}')
            (repo / "app.py").write_text("def value(): return 2\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertIn("baseline_stale", self.ids(data))
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "app.py").write_text("def value(): return 1\n", encoding="utf-8")
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertTrue((repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_missing_baseline_untracked_binary_does_not_auto_create(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "asset.bin").write_bytes(b"\x00\x01")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_missing")
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_partial_legacy_and_receipt_traversal_are_corrupt(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            packet = repo / ".sourcepack" / "baseline" / "packet"
            packet.mkdir(parents=True)
            (packet / "receipt.json").write_text("{}")
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            receipt = json.loads((packet / "receipt.json").read_text())
            receipt["hashes"]["../outside"] = "abc"
            (packet / "receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")


if __name__ == "__main__":
    unittest.main()
