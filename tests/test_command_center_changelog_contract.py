from __future__ import annotations

from pathlib import Path


def test_command_center_changelog_mentions_aggregate_endpoint() -> None:
    text = Path("docs/command-center-changelog.md").read_text(encoding="utf-8")
    assert "authenticated aggregate snapshot endpoint" in text
    assert "Preserved existing Workbench routes" in text
