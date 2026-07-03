import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import run_cli, validate_baseline, judge_patch, judge_patch_text, build_current_baseline, extract_js_import_specifiers_from_text


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
            ({"package.json": '{"dependencies": {"@myorg/core":"1.0.0"}}', "app.js": "console.log(1)\n"}, "use.js", 'import { shared } from "@myorg/core/utils"\n', False),
            ({"package.json": '{"dependencies": {}}', "app.js": "console.log(1)\n"}, "use.js", 'import { shared } from "@myorg/missing/utils"\n', True),
            ({"package.json": '{"dependencies": {"react":"latest"}}', "app.js": "console.log(1)\n"}, "jsx.js", 'import runtime from "react/jsx-runtime"\n', False),
            ({"package.json": '{"dependencies": {}}', "local.js": "export const value = 1\n"}, "relative.js", 'import { value } from "./local"\n', False),
            ({"package.json": '{"workspaces": ["packages/*"]}', "packages/core/package.json": '{"name":"@myorg/core"}', "app.js": "console.log(1)\n"}, "use.js", 'import { shared } from "@myorg/core/utils"\n', False),
            ({"package.json": '{}', "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', "src/components/Button.ts": "export const Button = 1\n", "app.ts": "console.log(1)\n"}, "view.ts", 'import { Button } from "@/components/Button"\n', False),
        ]
        for files, changed, content, should_fail in cases:
            with self.subTest(content=content):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), files)
                    (repo / changed).write_text(content, encoding="utf-8")
                    code, data = self.diff_json(repo)
                    self.assertEqual("unsupported_dependency" in self.ids(data), should_fail)

    def test_same_patch_dependencies_are_ecosystem_scoped(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "package.json": '{"dependencies":{}}\n'})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
+import requests
 def value(): return 1
diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1,5 @@
-{"dependencies":{}}
+{
+  "dependencies": {
+    "requests": "^1.0.0"
+  }
+}
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("requests", report["unsupported_dependencies"])

        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.js": "export const value = 1;\n", "pyproject.toml": '[project]\nname="demo"\ndependencies=[]\n'})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, """diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1 +1,2 @@
+import React from "react/jsx-runtime";
 export const value = 1;
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,3 +1,3 @@
 [project]
 name="demo"
-dependencies=[]
+dependencies=["react"]
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("react", report["unsupported_dependencies"])


    def test_js_raw_import_specifier_extraction_preserves_alias_scoped_and_subpaths(self):
        imports = extract_js_import_specifiers_from_text('''
import { Button } from "@/components/Button"
import helper from "~/utils"
import { core } from "@myorg/core/utils"
import runtime from "react/jsx-runtime"
const React = require("react")
const lazy = import("@scope/pkg/subpath")
''')
        self.assertIn("@/components/button", imports)
        self.assertIn("~/utils", imports)
        self.assertIn("@myorg/core/utils", imports)
        self.assertIn("react/jsx-runtime", imports)
        self.assertIn("@scope/pkg/subpath", imports)

    def test_js_unresolved_alias_is_yellow_uncertain_not_silent_green(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{}', "app.ts": "console.log(1)\n"})
            (repo / "view.ts").write_text('import { Button } from "@/components/Button"\n', encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertIn("js_alias_uncertain", self.ids(data))
            self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_same_patch_js_dependencies_are_yellow_for_json_formats_scoped_and_subpaths(self):
        cases = [
            ('{"dependencies":{"react":"latest"}}', 'import React from "react"\n', "react"),
            ('''{
  "dependencies": {
    "react": "latest"
  }
}''', 'import React from "react"\n', "react"),
            ('{"dependencies":{"@scope/pkg":"1.0.0"}}', 'import thing from "@scope/pkg/subpath"\n', "@scope/pkg"),
            ('{"dependencies":{"react":"latest"}}', 'import runtime from "react/jsx-runtime"\n', "react"),
        ]
        for package_json, import_line, expected_dep in cases:
            with self.subTest(expected_dep=expected_dep, import_line=import_line):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), {"app.js": "export const value = 1;\n", "package.json": '{}\n'})
                    packet = repo / validate_baseline(repo)["packet_path"]
                    added_package_json = "\n".join(f"+{line}" for line in package_json.splitlines())
                    report = judge_patch_text(packet, f'''diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1 +1,2 @@
+{import_line.rstrip()}
 export const value = 1;
diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1 @@
-{{}}
{added_package_json}
''')
                    traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
                    self.assertEqual(traffic["verdict"], "WARN")
                    self.assertNotIn("unsupported_dependency", {f["id"] for f in traffic["findings"]})
                    self.assertIn(expected_dep, report.get("declared_dependencies", []))

    def test_judge_patch_invalid_utf8_fails_closed_as_malformed_diff(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            repo = self.make_repo(root, {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            patch = root / "bad.patch"
            patch.write_bytes(b"\xff\xfe\x00")
            out = root / "out"
            report = judge_patch(packet, patch, out)
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("malformed_diff", {f["id"] for f in traffic["findings"]})

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
            self.assertIn("unsupported_ecosystem", self.ids(data))
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


    def test_ugly_repo_mixed_layout_docs_workflow_deleted_binary_and_unsupported(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {
                "package.json": '{"devDependencies":{"eslint":"latest"}}\n',
                "pyproject.toml": '[project]\nname="ugly"\n[project.optional-dependencies]\ndev=["pytest"]\n',
                "src/ugly/__init__.py": "VALUE = 1\n",
                "packages/web/package.json": '{"dependencies":{"react":"latest"}}\n',
                "README.md": "Run pytest and npm test.\n",
                "docs/guide.md": "guide\n",
                ".github/workflows/ci.yml": "name: ci\non: [push]\n",
                "legacy.txt": "delete me\n",
                "blob.bin": b"\x00\x01\x02\x03",
                "Cargo.toml": "[package]\nname='unsupported'\nversion='0.1.0'\n",
            })
            (repo / "src" / "ugly" / "feature.py").write_text("import requests\n", encoding="utf-8")
            (repo / "docs" / "guide.md").write_text("guide v2\n", encoding="utf-8")
            (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: [push, pull_request]\n", encoding="utf-8")
            (repo / "legacy.txt").unlink()
            (repo / "generated.dat").write_bytes(b"\x00\x01generated")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            finding_ids = self.ids(data)
            self.assertIn("unsupported_dependency", finding_ids)
            self.assertIn("new_file", finding_ids)
            self.assertIn("deleted_file", finding_ids)
            self.assertIn("workflow_change", finding_ids)
            self.assertIn("binary_diff", finding_ids)
            self.assertIn("unsupported_ecosystem", finding_ids)


if __name__ == "__main__":
    unittest.main()

