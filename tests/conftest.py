from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_sourcepack_home(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path_factory.mktemp("sourcepack-home")))
