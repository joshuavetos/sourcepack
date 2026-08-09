from __future__ import annotations

from pathlib import Path


def test_command_center_security_boundary_is_explicit() -> None:
    text = Path("docs/command-center-security.md").read_text(encoding="utf-8")

    for phrase in (
        "loopback-only Workbench server",
        "session-token authentication",
        "no arbitrary command input",
        "no trusted baseline creation or refresh",
    ):
        assert phrase in text
