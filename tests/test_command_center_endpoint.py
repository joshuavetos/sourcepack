from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sourcepack.command_center_endpoint import (
    COMMAND_CENTER_ROUTE,
    install_command_center_route,
)


class _FakeHandler:
    original_calls = 0

    def __init__(self, path: str, authorized: bool = True):
        self.path = path
        self.repo_root = Path(".")
        self.authorized = authorized
        self.sent = None

    def _require_api_token(self) -> bool:
        return self.authorized

    def _send_json(self, status: int, payload: dict) -> None:
        self.sent = (status, payload)

    def do_GET(self) -> None:
        type(self).original_calls += 1


def _module():
    class Handler(_FakeHandler):
        pass

    return SimpleNamespace(WorkbenchHandler=Handler)


def test_installed_route_returns_authenticated_snapshot() -> None:
    module = _module()
    install_command_center_route(module)
    handler = module.WorkbenchHandler(COMMAND_CENTER_ROUTE)

    with patch(
        "sourcepack.command_center_endpoint.command_center_payload",
        return_value={"ok": True, "status": "success", "snapshot": {"scores": {"trust": 100}}},
    ):
        handler.do_GET()

    assert handler.sent == (
        200,
        {"ok": True, "status": "success", "snapshot": {"scores": {"trust": 100}}},
    )


def test_route_rejects_missing_authentication() -> None:
    module = _module()
    install_command_center_route(module)
    handler = module.WorkbenchHandler(COMMAND_CENTER_ROUTE, authorized=False)

    handler.do_GET()

    assert handler.sent is None


def test_non_command_center_route_preserves_original_handler() -> None:
    module = _module()
    install_command_center_route(module)
    handler = module.WorkbenchHandler("/api/status")

    before = module.WorkbenchHandler.original_calls
    handler.do_GET()

    assert module.WorkbenchHandler.original_calls == before + 1


def test_installation_is_idempotent() -> None:
    module = _module()
    install_command_center_route(module)
    first = module.WorkbenchHandler.do_GET

    install_command_center_route(module)

    assert module.WorkbenchHandler.do_GET is first
