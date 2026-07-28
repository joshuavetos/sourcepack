from __future__ import annotations

import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any

COMMAND_CENTER_ROUTE = "/api/command-center/v1/snapshot"
COMMAND_CENTER_CLIENT = "/command-center-aggregate.js"
WORKBENCH_RELEASE_MARKER = "<!-- SourcePack Workbench -->"
_INSTALL_MARKER = "_sourcepack_command_center_handler_installed"


def command_center_payload(repo: str | Path) -> dict[str, Any]:
    """Build and validate the canonical Command Center snapshot."""
    from .command_center import build_command_center_snapshot
    from .command_center_contract import validate_command_center_snapshot

    try:
        snapshot = build_command_center_snapshot(repo)
        validate_command_center_snapshot(snapshot)
        return {
            "ok": True,
            "status": "success",
            "snapshot": snapshot,
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


def command_center_handler(base_handler: type[Any], static_root: Path) -> type[Any]:
    """Return an explicit Workbench handler that owns Command Center behavior."""

    class CommandCenterWorkbenchHandler(base_handler):
        def do_GET(self) -> None:
            requested = urllib.parse.urlparse(self.path).path
            if requested != COMMAND_CENTER_ROUTE:
                super().do_GET()
                return
            if not self._require_api_token():
                return
            payload = command_center_payload(self.repo_root)
            self._send_json(200 if payload.get("ok") else 500, payload)

        def _serve_static(self, requested: str) -> None:
            if requested not in {"", "/", "/index.html"}:
                super()._serve_static(requested)
                return
            index_path = static_root / "index.html"
            body = index_path.read_text(encoding="utf-8")
            client_marker = f'<script src="{COMMAND_CENTER_CLIENT}"></script>'
            injected = f"{WORKBENCH_RELEASE_MARKER}\n{client_marker}"
            if client_marker not in body:
                body = body.replace("</body>", f"{injected}\n</body>")
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    CommandCenterWorkbenchHandler.__name__ = "CommandCenterWorkbenchHandler"
    CommandCenterWorkbenchHandler.__qualname__ = "CommandCenterWorkbenchHandler"
    setattr(CommandCenterWorkbenchHandler, _INSTALL_MARKER, True)
    return CommandCenterWorkbenchHandler


def install_command_center_route(workbench_module: ModuleType | None = None) -> None:
    """Install one explicit Command Center handler subclass for Workbench."""
    if workbench_module is None:
        from . import workbench as workbench_module

    current = workbench_module.WorkbenchHandler
    if getattr(current, _INSTALL_MARKER, False):
        return
    workbench_module.WorkbenchHandler = command_center_handler(
        current,
        workbench_module.STATIC_ROOT,
    )
