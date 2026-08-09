from __future__ import annotations

from pathlib import Path


def test_command_center_api_documentation_matches_route() -> None:
    text = Path("docs/command-center-api.md").read_text(encoding="utf-8")

    assert "GET /api/command-center/v1/snapshot" in text
    assert "X-SourcePack-Token" in text
    assert "sourcepack.command_center.v1" in text
    assert "does not create or refresh trusted baseline state" in text
