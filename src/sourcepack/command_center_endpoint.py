from __future__ import annotations

import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

COMMAND_CENTER_ROUTE = "/api/command-center/v1/snapshot"
_INSTALL_MARKER = "_sourcepack_command_center_route_installed"


def command_center_payload(repo: str | Path) -> dict[str, Any]:
    """Build the canonical Command Center snapshot without duplicating state logic."""
    from .command_center import build_command_center_snapshot

    try:
        return {
            "ok": True,
            "status": "success",
            "snapshot": build_command_center_snapshot(repo),
        }
    except Exception:
        return {
            "ok": False,
            "status": "error",
            "error": {
                "code": "command_center_snapshot_failed",
                "message": "The Command Center snapshot could not be built.",
            },
        }


def install_command_center_route(workbench_module: ModuleType | None = None) -> None:
    """Add one authenticated aggregate route while preserving Workbench behavior."""
    if workbench_module is None:
        from . import workbench as workbench_module

    handler = workbench_module.WorkbenchHandler
    if getattr(handler, _INSTALL_MARKER, False):
        return

    original_do_get: Callable[..., Any] = handler.do_GET

    def command_center_do_get(self: Any) -> Any:
        requested = urllib.parse.urlparse(self.path).path
        if requested != COMMAND_CENTER_ROUTE:
            return original_do_get(self)
        if not self._require_api_token():
            return None
        payload = command_center_payload(self.repo_root)
        self._send_json(200 if payload.get("ok") else 500, payload)
        return None

    command_center_do_get.__name__ = original_do_get.__name__
    command_center_do_get.__doc__ = original_do_get.__doc__
    handler.do_GET = command_center_do_get
    setattr(handler, _INSTALL_MARKER, True)
