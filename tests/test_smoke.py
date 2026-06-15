import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from sourcepack.cli import dependency_inventory, load_manifest, run_cli


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

if __name__ == "__main__":
    unittest.main()
