from __future__ import annotations

import re
import unittest
from pathlib import Path


INDEX = Path(__file__).resolve().parents[1] / "src" / "sourcepack" / "workbench_static" / "index.html"


class CommandCenterStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_command_center_exposes_all_major_surfaces(self) -> None:
        expected = {
            "Mission Control",
            "Live Review",
            "Evidence Graph",
            "Policy Studio",
            "Replay Theater",
            "Agent Gateway",
            "Adversarial Lab",
            "Integration Hub",
            "Raw Systems",
        }
        for label in expected:
            with self.subTest(label=label):
                self.assertIn(label, self.html)

    def test_live_surfaces_use_existing_authenticated_endpoints(self) -> None:
        expected_routes = {
            "/api/dashboard/v1/overview",
            "/api/dashboard/v1/report",
            "/api/dashboard/v1/policy",
            "/api/dashboard/v1/baseline",
            "/api/dashboard/v1/replay-evidence",
            "/api/dashboard/v1/overrides",
            "/api/status",
            "/api/workbench/v1/review",
        }
        for route in expected_routes:
            with self.subTest(route=route):
                self.assertIn(route, self.html)
        self.assertIn("X-SourcePack-Token", self.html)

    def test_planned_integrations_are_not_presented_as_live(self) -> None:
        self.assertIn("READY TO BUILD", self.html)
        self.assertIn("PLANNED", self.html)
        self.assertIn("PARTIAL", self.html)
        self.assertNotIn("All integrations connected", self.html)

    def test_page_remains_mobile_responsive(self) -> None:
        self.assertRegex(self.html, re.compile(r"@media\(max-width:1000px\)"))
        self.assertRegex(self.html, re.compile(r"@media\(max-width:620px\)"))
        self.assertIn('name="viewport"', self.html)

    def test_command_center_has_no_remote_runtime_dependencies(self) -> None:
        self.assertNotIn("<script src=", self.html)
        self.assertNotIn("<link rel=\"stylesheet\" href=\"http", self.html)
        self.assertNotIn("https://cdn.", self.html)


if __name__ == "__main__":
    unittest.main()
