from __future__ import annotations

from pathlib import Path


CLIENT = Path(__file__).parents[1] / "src" / "sourcepack" / "workbench_static" / "command-center-aggregate.js"


def test_client_uses_single_canonical_snapshot_route() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    assert 'const SNAPSHOT_ROUTE = "/api/command-center/v1/snapshot"' in text
    assert "Promise.allSettled" not in text
    assert "/api/dashboard/v1/" not in text
    assert "/api/status" not in text


def test_client_maps_snapshot_into_existing_surfaces() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    for assignment in (
        "state.commandCenter = snapshot",
        "state.overview =",
        "state.report =",
        "state.policy =",
        "state.baseline =",
        "state.status =",
        "state.replay =",
    ):
        assert assignment in text

    assert "render();" in text
    assert "loadAll = async function loadCommandCenterSnapshot()" in text


def test_client_preserves_error_visibility() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    assert "state.error = error.message" in text
    assert "Command Center snapshot failed:" in text
    assert "refresh.disabled = false" in text
