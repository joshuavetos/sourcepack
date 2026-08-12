from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_sourcepack_home(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path_factory.mktemp("sourcepack-home")))


def symlink_or_skip(link: Path, target: str | Path, *, target_is_directory: bool = False) -> None:
    """Create a test symlink or capability-skip when Windows denies creation."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink creation capability is unavailable (WinError 1314)")
        raise
