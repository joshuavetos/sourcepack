from __future__ import annotations

import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

COMMAND_CENTER_ROUTE = "/api/command-center/v1/snapshot"
COMMAND_CENTER_CLIENT = "/command-center-aggregate.js"
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
    """Add the authenticated aggregate route and client without replacing Workbench."""
    if workbench_module is None:
        from . import workbench as workbench_module

    handler = workbench_module.WorkbenchHandler
    if getattr(handler, _INSTALL_MARKER, False):
        return

    original_do_get: Callable[..., Any] = handler.do_GET
    original_serve_static: Callable[..., Any] = handler._serve_static

    def command_center_do_get(self: Any) -> Any:
        requested = urllib.parse.urlparse(self.path).path
        if requested != COMMAND_CENTER_ROUTE:
            return original_do_get(self)
        if not self._require_api_token():
            return None
        payload = command_center_payload(self.repo_root)
        self._send_json(200 if payload.get("ok") else 500, payload)
        return None

    def command_center_serve_static(self: Any, requested: str) -> Any:
        if requested not in {"", "/", "/index.html"}:
            return original_serve_static(self, requested)
        index_path = workbench_module.STATIC_ROOT / "index.html"
        body = index_path.read_text(encoding="utf-8")
        marker = f'<script src="{COMMAND_CENTER_CLIENT}"></script>'
        if marker not in body:
            body = body.replace("</body>", f"{marker}\n</body>")
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return None

    command_center_do_get.__name__ = original_do_get.__name__
    command_center_do_get.__doc__ = original_do_get.__doc__
    command_center_serve_static.__name__ = original_serve_static.__name__
    command_center_serve_static.__doc__ = original_serve_static.__doc__
    handler.do_GET = command_center_do_get
    handler._serve_static = command_center_serve_static
    setattr(handler, _INSTALL_MARKER, True)
