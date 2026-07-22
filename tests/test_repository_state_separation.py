from __future__ import annotations

import unittest
from pathlib import Path

from sourcepack.repository_state import REPOSITORY_STATE_SCHEMA_VERSION, RepositoryState


class RepositoryStateSeparationTests(unittest.TestCase):
    def test_modified_manifest_preserves_trusted_content(self):
        state = RepositoryState.build(
            {"package.json": '{"dependencies":{"react":"1"}}'},
            {"package.json": '{"dependencies":{"react":"1","lodash":"1"}}'},
        )

        file_state = state.file("package.json")
        self.assertTrue(file_state.modified_by_patch)
        self.assertIn("react", file_state.trusted_content or "")
        self.assertNotIn("lodash", file_state.trusted_content or "")
        self.assertIn("lodash", file_state.proposed_content or "")
        self.assertNotEqual(file_state.trusted_sha256, file_state.proposed_sha256)

    def test_new_file_exists_only_in_proposed_state(self):
        state = RepositoryState.build({}, {"package.json": "{}"})
        file_state = state.file("package.json")
        self.assertFalse(file_state.exists_in_trusted_state)
        self.assertTrue(file_state.exists_in_proposed_state)
        self.assertTrue(file_state.modified_by_patch)

    def test_deleted_file_remains_addressable_as_trusted_evidence(self):
        state = RepositoryState.build({"pyproject.toml": "[project]\n"}, {"pyproject.toml": None})
        file_state = state.file("pyproject.toml")
        self.assertTrue(file_state.exists_in_trusted_state)
        self.assertFalse(file_state.exists_in_proposed_state)
        self.assertEqual("[project]\n", state.trusted_content("pyproject.toml"))
        self.assertIsNone(state.proposed_content("pyproject.toml"))

    def test_materialized_roots_are_physically_separate(self):
        state = RepositoryState.build(
            {"package.json": '{"scripts":{"test":"old"}}'},
            {"package.json": '{"scripts":{"test":"new"}}'},
        )
        with state.materialize() as materialized:
            trusted = (materialized.trusted_root / "package.json").read_text(encoding="utf-8")
            proposed = (materialized.proposed_root / "package.json").read_text(encoding="utf-8")
            self.assertNotEqual(materialized.trusted_root, materialized.proposed_root)
            self.assertIn("old", trusted)
            self.assertNotIn("new", trusted)
            self.assertIn("new", proposed)

    def test_proposed_inventory_applies_additions_and_deletions(self):
        state = RepositoryState.build(
            {"a.txt": "a", "delete.txt": "x"},
            {"b.txt": "b", "delete.txt": None},
        )
        self.assertEqual(("a.txt", "delete.txt"), state.trusted_inventory())
        self.assertEqual(("a.txt", "b.txt"), state.proposed_inventory())
        self.assertEqual(("b.txt", "delete.txt"), state.modified_paths())

    def test_serialized_state_contains_no_file_contents(self):
        secret = "do-not-serialize-this-content"
        state = RepositoryState.build({"config.txt": secret}, {"config.txt": secret + "-changed"})
        payload = state.to_dict()
        self.assertEqual(REPOSITORY_STATE_SCHEMA_VERSION, payload["schema_version"])
        self.assertNotIn(secret, repr(payload))
        self.assertEqual(["config.txt"], payload["modified_paths"])

    def test_unsafe_paths_are_rejected(self):
        for path in ("../outside", "/absolute", "a/../b", ""):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    RepositoryState.build({path: "x"})


if __name__ == "__main__":
    unittest.main()
