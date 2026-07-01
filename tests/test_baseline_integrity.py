import contextlib
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import build_current_baseline, run_cli, validate_baseline, acquire_baseline_lock, release_baseline_lock


def capture_cli(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = run_cli(args)
    return code, out.getvalue()


class BaselineIntegrityTest(unittest.TestCase):
    def repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        (repo / "README.md").write_text("demo\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return repo

    def json_cli(self, args):
        code, text = capture_cli(args + ["--json"])
        return code, json.loads(text)

    def packet(self, repo: Path) -> Path:
        status = validate_baseline(repo)
        return repo / status["packet_path"]

    def corrupt_and_diff(self, repo: Path):
        (repo / "README.md").write_text("demo\nchange\n")
        return self.json_cli(["diff", str(repo)])

    def test_missing_baseline_with_changes(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); (repo / "README.md").write_text("changed\n")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["verdict"], "FAIL")
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_missing")

    def test_missing_baseline_with_no_changes_creates_or_passes_not_corrupt(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 0)
            self.assertNotEqual(data.get("baseline_integrity_finding_id"), "baseline_corrupt")

    def test_empty_and_partial_inactive_baseline_are_missing(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); (repo / ".sourcepack" / "baseline").mkdir(parents=True)
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "missing")
            scratch = repo / ".sourcepack" / "baseline" / "builds" / "scratch" / "packet"
            scratch.mkdir(parents=True); (scratch / "manifest.json").write_text("{}")
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "missing")

    def test_corrupt_pointer_cases(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); base = repo / ".sourcepack" / "baseline"; base.mkdir(parents=True)
            (base / "active.json").write_text("{")
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "corrupt")
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")
            (base / "active.json").write_text(json.dumps({"active_build_id":"missing"}))
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "corrupt")

    def test_corrupt_packet_artifacts_block_diff(self):
        cases = [
            ("manifest.json", None),
            ("manifest.json", "{"),
            ("receipt.json", None),
            ("receipt.json", "{"),
            ("reality_map.json", '{"tampered": true}'),
            ("reality_map.json", None),
        ]
        for name, content in cases:
            with self.subTest(name=name, content=content):
                with TemporaryDirectory() as td:
                    repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
                    target = self.packet(repo) / name
                    if content is None:
                        target.unlink()
                    else:
                        target.write_text(content)
                    code, data = self.corrupt_and_diff(repo)
                    self.assertEqual(code, 1)
                    self.assertEqual(data["verdict"], "FAIL")
                    self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")

    def test_corrupt_baseline_wins_with_no_diff(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            (self.packet(repo) / "receipt.json").write_text("{")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")

    def test_stale_baseline_warns_and_stale_plus_red_fails(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            state = repo / ".sourcepack" / "state"; state.mkdir(parents=True, exist_ok=True)
            (state / "baseline_stale.json").write_text('{"reason":"test"}')
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertEqual(data["reason_type"], "uncertainty")
            self.assertTrue(any(f["id"] == "baseline_stale" for f in data["findings"]))
            (repo / "app.py").write_text("import fastapi\n")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["verdict"], "FAIL")
            ids = {f["id"] for f in data["findings"]}
            self.assertIn("unsupported_dependency", ids)

    def test_status_reports_missing_stale_corrupt(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            self.assertEqual(self.json_cli(["status", str(repo)])[1]["baseline_state"], "missing")
            build_current_baseline(repo, quiet=True)
            (repo / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}')
            self.assertEqual(self.json_cli(["status", str(repo)])[1]["baseline_state"], "stale")
            (self.packet(repo) / "manifest.json").write_text("{")
            data = self.json_cli(["status", str(repo)])[1]
            self.assertEqual(data["baseline_state"], "corrupt")
            self.assertFalse(data["baseline_integrity_ok"])

    def test_prompt_does_not_create_or_repair_baseline(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertTrue((repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "packet" / "manifest.json").exists())
            build_current_baseline(repo, quiet=True, force=True)
            (self.packet(repo) / "manifest.json").write_text("{")
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")

    def test_pointer_activation_failure_preserves_old_or_missing_state(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            old = json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text())["active_build_id"]
            with self.assertRaises(RuntimeError):
                build_current_baseline(repo, quiet=True, fail_stage="before_pointer_replace")
            self.assertEqual(json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text())["active_build_id"], old)
            self.assertEqual(validate_baseline(repo)["state"], "present")
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            with self.assertRaises(RuntimeError):
                build_current_baseline(repo, quiet=True, fail_stage="before_pointer_replace")
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())
            self.assertEqual(validate_baseline(repo)["state"], "missing")

    def test_concurrent_baseline_lock_blocks_second_writer(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); lock, fd = acquire_baseline_lock(repo, "test")
            try:
                with self.assertRaises(Exception):
                    build_current_baseline(repo, quiet=True)
                self.assertEqual(validate_baseline(repo)["state"], "missing")
            finally:
                release_baseline_lock(lock, fd)
            build_current_baseline(repo, quiet=True)
            self.assertEqual(validate_baseline(repo)["state"], "present")


if __name__ == "__main__":
    unittest.main()
