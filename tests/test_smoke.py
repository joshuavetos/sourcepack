import json
import unittest
import os
import subprocess
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from sourcepack.cli import dependency_inventory, extract_imports_from_text, feature_inventory, load_manifest, run_cli, traffic_report, normalized_finding, render_traffic, judge_patch_text


class SourcePackSmokeTest(unittest.TestCase):
    def test_smoke_build_verify_judge(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            (repo / "sourcepack").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "README.md").write_text("Local-first CLI. No Docker. No FastAPI. No PDF parsing.")
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\ndependencies=["pytest"]\n')
            (repo / "sourcepack" / "verify.py").write_text("def verify(): return True\n")
            (repo / "sourcepack" / "judge.py").write_text("def judge(): return True\n")
            (repo / ".env").write_text("OPENAI_API_KEY=sk-proj-SECRETSECRETSECRETSECRET\n")
            packet = tmp / "packet"
            self.assertEqual(run_cli(["doctor"]), 0)
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            for name in ["manifest.json", "context.md", "context.xml", "receipt.json", "file_tree.txt", "ignored_files.txt", "token_report.json"]:
                self.assertTrue((packet / name).exists(), name)
            self.assertEqual(run_cli(["verify", str(packet)]), 0)
            answer = tmp / "ai_answer.md"
            answer.write_text("Uses `sourcepack/server.py` and `docker compose up`, but real file `sourcepack/verify.py` exists.")
            judgment = tmp / "judgment"
            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            report = (judgment / "judgment_report.md").read_text()
            self.assertIn("sourcepack/server.py", report)
            self.assertIn("docker compose up", report)

    def test_readme_prose_does_not_create_dependency_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("Local-first CLI. No Docker. No FastAPI. No PDF parsing.")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertNotIn("fastapi", dependency_inventory(load_manifest(packet), packet))
            self.assertNotIn("pdf", dependency_inventory(load_manifest(packet), packet))

    def test_verify_against_uses_source_hash_when_packet_is_redacted(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            secret_line = "OPENAI_API_KEY=sk-proj-SECRETSECRETSECRETSECRET\n"
            (repo / "config.py").write_text(secret_line)
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            context = (packet / "context.md").read_text()
            self.assertIn("[REDACTED:openai_key]", context)
            self.assertEqual(run_cli(["verify", str(packet), "--against", str(repo)]), 0)


    def test_readme_negative_prose_does_not_create_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("PDF parsing is not supported. No Docker setup. No React frontend. No database.")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            answer = tmp / "ai_answer.md"
            answer.write_text("This project supports PDF parsing, Docker, React, and database storage.")
            judgment = tmp / "judgment"

            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            report = (judgment / "judgment_report.md").read_text()
            self.assertIn("- [UNSUPPORTED] pdf", report)
            self.assertIn("- [UNSUPPORTED] docker", report)
            self.assertIn("- [UNSUPPORTED] react", report)
            self.assertIn("- [UNSUPPORTED] database", report)

    def test_dockerfile_creates_docker_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "Dockerfile").write_text("FROM python:3.12-slim\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("docker", feature_inventory(load_manifest(packet), packet))

    def test_pdf_parser_file_creates_pdf_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "pdf_parser.py").write_text("def parse_pdf(path):\n    return path\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("pdf", feature_inventory(load_manifest(packet), packet))

    def test_pdf_library_import_creates_pdf_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "reader.py").write_text("import pypdf\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("pdf", feature_inventory(load_manifest(packet), packet))


class SourcePackRealityMapTest(unittest.TestCase):
    def _build(self, repo: Path, packet: Path):
        self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
        return __import__("json").loads((packet / "reality_map.json").read_text())

    def test_build_creates_reality_map_ai_instructions_and_receipt_hashes(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\ndependencies=["pytest"]\n')
            packet = tmp / "packet"
            reality = self._build(repo, packet)
            self.assertTrue((packet / "reality_map.json").exists())
            self.assertTrue((packet / "ai_instructions.md").exists())
            receipt = json.loads((packet / "receipt.json").read_text())
            self.assertIn("reality_map.json", receipt["hashes"])
            self.assertIn("ai_instructions.md", receipt["hashes"])
            self.assertEqual(reality["reality_map_schema_version"], "1.0")
            self.assertEqual(run_cli(["verify", str(packet)]), 0)

    def test_tampered_new_artifacts_fail_verify(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self._build(repo, packet)
            (packet / "reality_map.json").write_text('{"tampered": true}')
            self.assertEqual(run_cli(["verify", str(packet)]), 1)
            self._build(repo, packet)
            (packet / "ai_instructions.md").write_text("tampered")
            self.assertEqual(run_cli(["verify", str(packet)]), 1)

    def test_python_poetry_detection_rules(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\n')
            reality = self._build(repo, tmp / "packet")
            self.assertIn("python", reality["project_types"])
            self.assertNotIn("poetry", reality["package_managers"])
            (repo / "pyproject.toml").write_text('[tool.poetry]\nname="demo"\n')
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("poetry", reality["package_managers"])

    def test_docker_and_compose_command_detection(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("No Docker setup")
            reality = self._build(repo, tmp / "packet")
            self.assertNotIn("docker build", reality["supported_commands"])
            (repo / "Dockerfile").write_text("FROM python:3.12-slim\n")
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("docker build", reality["supported_commands"])
            self.assertNotIn("docker compose up", reality["supported_commands"])
            (repo / "compose.yaml").write_text("services: {}\n")
            reality = self._build(repo, tmp / "packet3")
            self.assertIn("docker compose up", reality["supported_commands"])

    def test_package_json_scripts_only(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "package.json").write_text('{"dependencies": {"react": "latest"}}')
            reality = self._build(repo, tmp / "packet")
            self.assertNotIn("npm test", reality["supported_commands"])
            self.assertNotIn("npm run dev", reality["supported_commands"])
            (repo / "package.json").write_text('{"scripts": {"test": "node test.js", "dev": "vite", "build": "vite build"}}')
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("npm test", reality["supported_commands"])
            self.assertIn("npm run dev", reality["supported_commands"])
            self.assertIn("npm run build", reality["supported_commands"])

    def test_ai_instructions_warnings_and_json_validity(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self._build(repo, packet)
            text = (packet / "ai_instructions.md").read_text()
            self.assertIn("missing", text.lower())
            self.assertIn("unsupported", text.lower())
            for name in ["manifest.json", "receipt.json", "token_report.json", "redactions.json", "reality_map.json"]:
                json.loads((packet / name).read_text())

    def test_map_and_instructions_commands(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            out = tmp / "reality_map.json"
            self.assertEqual(run_cli(["map", str(repo), "--out", str(out)]), 0)
            self.assertTrue(out.exists())
            packet = tmp / "packet"
            self._build(repo, packet)
            (packet / "ai_instructions.md").unlink()
            self.assertEqual(run_cli(["instructions", str(packet)]), 0)
            self.assertTrue((packet / "ai_instructions.md").exists())


class SourcePackPatchJudgmentTest(unittest.TestCase):
    def _packet(self, tmp: Path):
        repo = tmp / "repo"; repo.mkdir()
        (repo / "README.md").write_text("demo\n")
        (repo / "app.py").write_text("def main():\n    return True\n")
        packet = tmp / "packet"
        self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
        return packet

    def _judge_patch(self, packet: Path, tmp: Path, text: str):
        patch = tmp / "change.diff"; patch.write_text(text)
        out = tmp / "patch_report"
        self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(out)]), 0)
        import json
        return json.loads((out / "patch_judgment_report.json").read_text()), out

    def test_known_file_patch_does_not_fail_for_existence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def main():
+    print('ok')
     return True
""")
            self.assertNotIn("app.py", report["missing_modified_files"])
            self.assertEqual(report["verdict"], "PASS")

    def test_missing_file_patch_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/sourcepack/server.py b/sourcepack/server.py
--- a/sourcepack/server.py
+++ b/sourcepack/server.py
@@ -1 +1,2 @@
+print('x')
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("sourcepack/server.py", report["missing_modified_files"])

    def test_new_file_warns_not_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1 @@
+print('new')
""")
            self.assertEqual(report["verdict"], "WARN")
            self.assertIn("new.py", report["new_files"])

    def test_deleted_file_reported(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
deleted file mode 100644
--- a/app.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def main():
-    return True
""")
            self.assertIn("app.py", report["deleted_files"])

    def test_fastapi_import_without_dependency_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+from fastapi import FastAPI
 def main():
     return True
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("fastapi", report["unsupported_dependencies"])

    def test_new_file_with_unsupported_fastapi_import_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/api.py b/api.py
new file mode 100644
--- /dev/null
+++ b/api.py
@@ -0,0 +1,2 @@
+from fastapi import FastAPI
+app = FastAPI()
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("api.py", report["new_files"])
            self.assertIn("fastapi", report["unsupported_dependencies"])

    def test_import_extraction_catches_python_and_javascript_imports(self):
        self.assertIn("fastapi", extract_imports_from_text("import fastapi\n", ".py"))
        self.assertIn("fastapi", extract_imports_from_text("from fastapi import FastAPI\n", ".py"))
        self.assertIn("react", extract_imports_from_text("import React from 'react'\n", ".tsx"))
        self.assertIn("vue", extract_imports_from_text("const vue = require('vue')\n", ".js"))

    def test_unsupported_commands_fail(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,4 @@
 demo
+docker compose up
+npm run dev
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("docker compose up", report["unsupported_commands"])
            self.assertIn("npm run dev", report["unsupported_commands"])

    def test_protected_artifact_patch_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            for name in ["receipt.json", "manifest.json", "reality_map.json", "ai_instructions.md"]:
                report, _ = self._judge_patch(packet, tmp, f"""diff --git a/{name} b/{name}
--- a/{name}
+++ b/{name}
@@ -1 +1,2 @@
+tamper
""")
                self.assertEqual(report["verdict"], "FAIL")
                self.assertIn(name, report["protected_artifact_modifications"])

    def test_nested_receipt_json_is_not_protected_artifact(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/docs/receipt.json b/docs/receipt.json
new file mode 100644
--- /dev/null
+++ b/docs/receipt.json
@@ -0,0 +1 @@
+{}
""")
            self.assertNotIn("docs/receipt.json", report["protected_artifact_modifications"])
            self.assertEqual(report["verdict"], "WARN")

    def test_judge_patch_does_not_mutate_packet_artifacts(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            names = ["manifest.json", "receipt.json", "reality_map.json", "ai_instructions.md"]
            before = {name: (packet / name).read_bytes() for name in names}
            report, out = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+print('ok')
 def main():
     return True
""")
            self.assertTrue((out / "patch_judgment_report.json").exists())
            self.assertIn("verdict", report)
            after = {name: (packet / name).read_bytes() for name in names}
            self.assertEqual(before, after)

    def test_patch_report_files_created_and_json_parses(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, out = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+print('ok')
""")
            self.assertTrue((out / "patch_judgment_report.md").exists())
            self.assertIn("verdict", report)
            json.loads((out / "patch_judgment_report.json").read_text())

    def test_judge_patch_exit_code_zero_when_verdict_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            patch = tmp / "fail.diff"
            patch.write_text("""diff --git a/receipt.json b/receipt.json
--- a/receipt.json
+++ b/receipt.json
@@ -1 +1,2 @@
+tamper
""")
            out = tmp / "patch_report"
            self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(out)]), 0)
            report = json.loads((out / "patch_judgment_report.json").read_text())
            self.assertEqual(report["verdict"], "FAIL")



    def test_package_json_declared_dependency_extraction_is_section_scoped(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/package.json b/package.json
new file mode 100644
--- /dev/null
+++ b/package.json
@@ -0,0 +1,6 @@
+{
+  "scripts": {"dev": "vite"},
+  "name": "demo",
+  "version": "1.0.0"
+}
""")
            self.assertNotIn("scripts", report.get("declared_dependencies", []))
            self.assertNotIn("dev", report.get("declared_dependencies", []))
            report = judge_patch_text(packet, """diff --git a/package.json b/package.json
new file mode 100644
--- /dev/null
+++ b/package.json
@@ -0,0 +1,5 @@
+{
+  "dependencies": {
+    "@scope/pkg": "^1.0.0"
+  }
+}
""")
            self.assertIn("@scope/pkg", report.get("declared_dependencies", []))

class SourcePackSchemaAndDemoTest(unittest.TestCase):
    def test_generated_artifacts_required_fields(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            answer = tmp / "answer.md"; answer.write_text("README.md")
            judgment = tmp / "judgment"
            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            patch = tmp / "change.diff"; patch.write_text("""diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+more
""")
            patch_out = tmp / "patch_judgment"
            self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(patch_out)]), 0)
            reality = json.loads((packet / "reality_map.json").read_text())
            judgment_json = json.loads((judgment / "judgment_report.json").read_text())
            patch_json = json.loads((patch_out / "patch_judgment_report.json").read_text())
            for key in ["reality_map_schema_version", "tool_version", "supported_commands", "detected_dependencies"]:
                self.assertIn(key, reality)
            for key in ["supported_files", "missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"]:
                self.assertIn(key, judgment_json)
            for key in ["patch_judgment_schema_version", "verdict", "modified_files", "missing_modified_files", "new_files"]:
                self.assertIn(key, patch_json)

    def test_demo_exits_successfully(self):
        self.assertEqual(run_cli(["demo"]), 0)


class SourcePackLocalUsabilityTest(unittest.TestCase):
    def _repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"; repo.mkdir()
        (repo / "README.md").write_text("demo\n", encoding="utf-8")
        (repo / "app.py").write_text("def main():\n    return True\n", encoding="utf-8")
        return repo


    def test_sourcepack_directory_is_not_included_in_manifest(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            sp = repo / ".sourcepack" / "current" / "packet"
            sp.mkdir(parents=True)
            (sp / "manifest.json").write_text('{"generated": true}\n', encoding="utf-8")
            (repo / ".sourcepack" / "reports").mkdir(parents=True)
            (repo / ".sourcepack" / "reports" / "latest.json").write_text('{"verdict":"PASS"}\n', encoding="utf-8")

            packet = Path(td) / "packet"
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
            included = [rec["relative_path"] for rec in manifest["included_files"]]
            self.assertFalse(any(path.startswith(".sourcepack/") for path in included), included)

    def test_prompt_refreshes_baseline_by_default(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            self.assertEqual(run_cli(["prompt", str(repo), "first task"]), 0)
            (repo / "new_prompt_file.py").write_text("print('fresh')\n", encoding="utf-8")
            self.assertEqual(run_cli(["prompt", str(repo), "second task"]), 0)
            manifest = json.loads((repo / ".sourcepack" / "current" / "packet" / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("new_prompt_file.py", [rec["relative_path"] for rec in manifest["included_files"]])

    def test_diff_missing_baseline_with_changes_fails_without_autobaseline(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            subprocess.run(["git", "add", "README.md", "app.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            (repo / "app.py").write_text("def main():\n    return False\n", encoding="utf-8")

            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("baseline_missing", {f["id"] for f in report["findings"]})
            self.assertFalse((repo / ".sourcepack" / "current" / "packet" / "manifest.json").exists())

    def test_prompt_creates_storage_gitignore_and_prompt_files(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            (repo / ".gitignore").write_text("dist/\r\n", encoding="utf-8", newline="")
            self.assertEqual(run_cli(["prompt", str(repo), "fix auth bug"]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            self.assertTrue((repo / ".sourcepack" / "reports").is_dir())
            prompt = (repo / ".sourcepack" / "current" / "prompt.md").read_text(encoding="utf-8")
            self.assertIn("fix auth bug", prompt)
            self.assertIn("AI Grounding Instructions", prompt)
            self.assertIn("Do not invent files, dependencies, commands, services, or capabilities.", prompt)
            self.assertTrue((repo / ".sourcepack" / "current" / "reality_map.json").exists())
            self.assertTrue((repo / ".sourcepack" / "current" / "ai_instructions.md").exists())
            gitignore = (repo / ".gitignore").read_bytes()
            self.assertIn(b"dist/\r\n.sourcepack/\r\n", gitignore)
            self.assertEqual(run_cli(["prompt", str(repo), "task"]), 0)
            self.assertEqual((repo / ".gitignore").read_text(encoding="utf-8").count(".sourcepack/"), 1)

    def test_prompt_copy_fallback_and_json_status(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = ""
            try:
                self.assertEqual(run_cli(["prompt", str(repo), "task", "--copy"]), 0)
            finally:
                os.environ["PATH"] = old_path
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "WARN")
            self.assertTrue((repo / ".sourcepack" / "current" / "prompt.md").exists())
            self.assertEqual(run_cli(["status", str(repo), "--json"]), 0)

    def test_traffic_light_renderer_shapes(self):
        red = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "missing_file", "tests/test_auth.py not found.")])
        yellow = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "new_file", "src/auth.py was created by the patch.")])
        green = traffic_report("PASS")
        self.assertIn("RED LIGHT", render_traffic(red))
        self.assertIn("missing_file", render_traffic(red))
        self.assertIn("YELLOW LIGHT", render_traffic(yellow))
        self.assertIn("new_file", render_traffic(yellow))
        self.assertIn("GREEN LIGHT", render_traffic(green))
        json.dumps(green)

    def test_baseline_created_and_refreshed(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            self.assertEqual(run_cli(["baseline", str(repo)]), 0)
            self.assertTrue((repo / ".sourcepack" / "current" / "packet" / "manifest.json").exists())
            first = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("created", first["headline"])
            self.assertEqual(run_cli(["baseline", str(repo), "--refresh"]), 0)
            second = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("refreshed", second["headline"])

    def test_diff_no_diff_new_file_fastapi_declared_and_outside_git(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo)]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            no_diff = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertEqual(no_diff["verdict"], "PASS")
            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertEqual(json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())["verdict"], "WARN")
            (repo / "api.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            red = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertEqual(red["verdict"], "FAIL")
            self.assertIn("unsupported_dependency", {f["id"] for f in red["findings"]})
            (repo / "requirements.txt").write_text("fastapi\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertEqual(json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())["verdict"], "WARN")
            self.assertTrue((repo / ".sourcepack" / "reports" / "latest.md").exists())
            self.assertTrue(list((repo / ".sourcepack" / "reports" / "archive").glob("*_patch_judgment.json")))
            self.assertEqual(run_cli(["diff", str(tmp)]), 1)

    def test_diff_staged_commands_artifacts_import_edges_and_hooks(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            (repo / "localmod.py").write_text("x=1\n")
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo)]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", "localmod.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            (repo / "app.py").write_text("import os\nfrom . import rel\nimport localmod\ndef main():\n    return True\n")
            subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
            self.assertEqual(run_cli(["diff", str(repo), "--staged"]), 0)
            (repo / "README.md").write_text("demo\ndocker compose up\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            (repo / "receipt.json").write_text("{}\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            (repo / "docs").mkdir(); (repo / "docs" / "receipt.json").write_text("{}\n")
            # docs/receipt.json may warn as a new file, but should not be a protected artifact finding.
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertNotIn("docs/receipt.json", [f.get("path") for f in report["findings"] if f["id"] == "protected_artifact"])
            (repo / "ui.ts").write_text("import x from '@scope/pkg'\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertIn("@scope/pkg", [f.get("evidence") for f in report["findings"]])
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            hook = (repo / ".git" / "hooks" / "pre-commit").read_text()
            self.assertIn("sourcepack diff . --staged", hook)
            self.assertNotIn('exec "$0"', hook)

    def test_installed_hook_execution_blocks_red_allows_yellow_and_chains_original(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo)]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            bindir = tmp / "bin"; bindir.mkdir()
            sourcepack_bin = bindir / "sourcepack"
            sourcepack_bin.write_text("#!/bin/sh\nif [ \"$SOURCEPACK_FAKE\" = red ]; then echo 'RED LIGHT: fake'; exit 1; fi\nif [ \"$SOURCEPACK_FAKE\" = green ]; then echo 'GREEN LIGHT: fake'; exit 0; fi\necho 'YELLOW LIGHT: fake'; exit 0\n", encoding="utf-8")
            sourcepack_bin.chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}{os.pathsep}" + os.environ.get("PATH", "")}

            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            yellow = subprocess.run([str(repo / ".git" / "hooks" / "pre-commit")], cwd=repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(yellow.returncode, 0, yellow.stdout + yellow.stderr)
            self.assertIn("YELLOW LIGHT", yellow.stdout)

            (repo / "api.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
            red = subprocess.run([str(repo / ".git" / "hooks" / "pre-commit")], cwd=repo, env={**env, "SOURCEPACK_FAKE": "red"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(red.returncode, 0, red.stdout + red.stderr)
            self.assertIn("RED LIGHT", red.stdout)

            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            original = repo / ".git" / "hooks" / "pre-commit"
            original.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            chained = subprocess.run([str(original), "arg1"], cwd=repo, env={**env, "SOURCEPACK_FAKE": "green"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(chained.returncode, 7, chained.stdout + chained.stderr)


    def _git_init_clean(self, repo: Path):
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        subprocess.run(["git", "add", "README.md", "app.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

    def test_init_auto_clean_idempotent_status_and_no_hook(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            self.assertEqual(run_cli(["init", str(repo), "--auto"]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            self.assertTrue((repo / ".sourcepack" / "reports").is_dir())
            self.assertTrue((repo / ".sourcepack" / "current" / "packet" / "manifest.json").exists())
            self.assertIn(".sourcepack/", (repo / ".gitignore").read_text())
            hook = repo / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.exists())
            first_gitignore = (repo / ".gitignore").read_text().count(".sourcepack/")
            first_hook_blocks = hook.read_text().count("# === SOURCEPACK BEGIN ===")
            self.assertEqual(run_cli(["init", str(repo), "--auto"]), 0)
            self.assertEqual((repo / ".gitignore").read_text().count(".sourcepack/"), first_gitignore)
            self.assertEqual(hook.read_text().count("# === SOURCEPACK BEGIN ==="), first_hook_blocks)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["status", str(repo)]), 0)
            self.assertIn("Automatic mode: enabled", buf.getvalue())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["status", str(repo), "--json"]), 0)
            self.assertTrue(json.loads(buf.getvalue())["automatic_mode_enabled"])
            self.assertEqual(run_cli(["uninstall-hook", str(repo)]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            (Path(td) / "repo2").mkdir(); repo2 = self._repo(Path(td) / "repo2"); self._git_init_clean(repo2)
            self.assertEqual(run_cli(["init", str(repo2), "--auto", "--no-hook"]), 0)
            self.assertFalse((repo2 / ".git" / "hooks" / "pre-commit").exists())

    def test_init_auto_dirty_baseline_policy_and_strict_hook(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            (repo / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): rc = run_cli(["init", str(repo), "--auto"])
            self.assertEqual(rc, 0)
            self.assertIn("YELLOW LIGHT", buf.getvalue())
            self.assertFalse((repo / ".sourcepack" / "current" / "packet" / "manifest.json").exists())
            self.assertEqual(run_cli(["init", str(repo), "--auto", "--refresh-baseline", "--strict"]), 0)
            self.assertTrue((repo / ".sourcepack" / "current" / "packet" / "manifest.json").exists())
            hook = (repo / ".git" / "hooks" / "pre-commit").read_text()
            self.assertIn("strict mode blocks YELLOW LIGHT", hook)

    def test_hook_chains_existing_hook_and_uninstall_restores(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp); self._git_init_clean(repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\necho ORIGINAL_HOOK\nexit 7\n", encoding="utf-8"); hook.chmod(0o755)
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            installed = hook.read_text()
            self.assertNotIn('exec "$0"', installed)
            bindir = tmp / "bin"; bindir.mkdir()
            fake = bindir / "sourcepack"
            fake.write_text("#!/bin/sh\necho 'GREEN LIGHT: fake'\nexit 0\n", encoding="utf-8"); fake.chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}{os.pathsep}" + os.environ.get("PATH", "")}
            cp = subprocess.run([str(hook)], cwd=repo / "src" if (repo / "src").exists() else repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(cp.returncode, 7, cp.stdout + cp.stderr)
            self.assertIn("GREEN LIGHT", cp.stdout)
            self.assertIn("ORIGINAL_HOOK", cp.stdout)
            self.assertEqual(run_cli(["uninstall-hook", str(repo)]), 0)
            self.assertEqual(hook.read_text(), "#!/bin/sh\necho ORIGINAL_HOOK\nexit 7\n")
            restored = subprocess.run([str(hook)], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(restored.returncode, 7)

    def test_diff_output_omits_legacy_patch_report_header(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            self.assertEqual(run_cli(["baseline", str(repo)]), 0)
            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertNotIn("# SourcePack Patch Judgment Report", buf.getvalue())



if __name__ == "__main__":
    unittest.main()
