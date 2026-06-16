import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from sourcepack.cli import dependency_inventory, feature_inventory, load_manifest, run_cli


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


if __name__ == "__main__":
    unittest.main()
