from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from sourcepack.policy import resolve_effective_policy
from sourcepack.policy_authority import (
    POLICY_AUTHORITY_ERROR,
    guard_effective_policy_result,
    proposed_policy_paths,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


class PrechangePolicyAuthorityTests(unittest.TestCase):
    def _repo(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        _git(repo, "init")
        _git(repo, "config", "user.email", "sourcepack@example.invalid")
        _git(repo, "config", "user.name", "SourcePack Tests")
        policy = repo / ".sourcepack" / "policy.json"
        policy.parent.mkdir(parents=True)
        policy.write_text(
            json.dumps(
                {
                    "schema_version": "sourcepack.policy.v1",
                    "rules": {"block_dependency_additions": True},
                }
            ),
            encoding="utf-8",
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "trusted policy")
        return td, repo

    def test_clean_committed_policy_remains_authoritative(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)

        result = resolve_effective_policy(repo)

        self.assertEqual(result["resolution_status"], "PASS")
        self.assertNotIn(POLICY_AUTHORITY_ERROR, result.get("errors", []))

    def test_modified_policy_fails_closed(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)
        policy = repo / ".sourcepack" / "policy.json"
        policy.write_text(
            json.dumps(
                {
                    "schema_version": "sourcepack.policy.v1",
                    "rules": {"block_dependency_additions": False},
                }
            ),
            encoding="utf-8",
        )

        result = resolve_effective_policy(repo)

        self.assertEqual(result["resolution_status"], "FAIL")
        self.assertIn(POLICY_AUTHORITY_ERROR, result["errors"])
        self.assertEqual(
            result["prechange_policy_authority"]["changed_paths"],
            [".sourcepack/policy.json"],
        )

    def test_deleted_policy_fails_closed(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)
        (repo / ".sourcepack" / "policy.json").unlink()

        result = resolve_effective_policy(repo)

        self.assertEqual(result["resolution_status"], "FAIL")
        self.assertIn(POLICY_AUTHORITY_ERROR, result["errors"])

    def test_untracked_allowlist_fails_closed(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)
        allow = repo / ".sourcepack" / "policy" / "allow.jsonl"
        allow.parent.mkdir(parents=True)
        allow.write_text('{"scope":"dependency","value":"demo"}\n', encoding="utf-8")

        result = resolve_effective_policy(repo)

        self.assertEqual(result["resolution_status"], "FAIL")
        self.assertEqual(
            result["prechange_policy_authority"]["changed_paths"],
            [".sourcepack/policy/allow.jsonl"],
        )

    def test_explicit_patch_detects_policy_delete_recreate(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)
        patch = """diff --git a/.sourcepack/policy.json b/.sourcepack/policy.json
index 1111111..2222222 100644
--- a/.sourcepack/policy.json
+++ b/.sourcepack/policy.json
@@ -1 +1 @@
-{"rules":{"block_dependency_additions":true}}
+{"rules":{"block_dependency_additions":false}}
"""

        paths = proposed_policy_paths(repo, patch)
        guarded = guard_effective_policy_result(
            repo,
            {"resolution_status": "PASS", "errors": []},
            patch_text=patch,
        )

        self.assertEqual(paths, (".sourcepack/policy.json",))
        self.assertEqual(guarded["resolution_status"], "FAIL")
        self.assertEqual(
            guarded["rejected_weakening_attempts"][0]["comparison_method"],
            "trusted_prechange_policy_only",
        )

    def test_non_policy_patch_does_not_change_resolution(self) -> None:
        td, repo = self._repo()
        self.addCleanup(td.cleanup)
        patch = """diff --git a/src/app.py b/src/app.py
new file mode 100644
--- /dev/null
+++ b/src/app.py
@@ -0,0 +1 @@
+print('ok')
"""
        original = {"resolution_status": "PASS", "errors": []}

        guarded = guard_effective_policy_result(repo, original, patch_text=patch)

        self.assertIs(guarded, original)


if __name__ == "__main__":
    unittest.main()
