from __future__ import annotations

from pathlib import Path


def test_next_slice_keeps_aggregate_endpoint_as_ui_source() -> None:
    text = Path("docs/command-center-next.md").read_text(encoding="utf-8")

    assert "aggregate snapshot endpoint" in text
    assert "capability matrix and priority queue" in text
    assert "authenticated local-only operation" in text
