from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sourcepack.command_center_endpoint import (
    COMMAND_CENTER_CLIENT,
    COMMAND_CENTER_ROUTE,
    WORKBENCH_RELEASE_MARKER,
    _validate_snapshot_derivations,
    command_center_handler,
    install_command_center_route,
)


class _FakeHandler:
    original_calls = 0
    original_static_calls = 0

    def __init__(self, path: str, authorized: bool = True):
        self.path = path
        self.repo_root = Path(".")
        self.authorized = authorized
        self.sent = None
        self.response_status = None
        self.response_headers: dict[str, str] = {}
        self.wfile = BytesIO()

    def _require_api_token(self) -> bool:
        return self.authorized

    def _send_json(self, status: int, payload: dict) -> None:
        self.sent = (status, payload)

    def send_response(self, status: int) -> None:
        self.response_status = status

    def send_header(self, name: str, value: str) -> None:
        self.response_headers[name] = value

    def end_headers(self) -> None:
        return None

    def do_GET(self) -> None:
        type(self).original_calls += 1

    def _serve_static(self, requested: str) -> None:
        type(self).original_static_calls += 1


def _module(static_root: Path | None = None):
    class Handler(_FakeHandler):
        pass

    return SimpleNamespace(WorkbenchHandler=Handler, STATIC_ROOT=static_root or Path("."))


def _snapshot() -> dict:
    return {
        "posture": {
            "verdict": "WARN",
            "baseline_state": "present",
            "policy_resolution_status": "PASS",
            "automatic_mode_enabled": True,
            "finding_count": 2,
            "blocker_count": 1,
            "warning_count": 1,
        },
        "artifacts": {
            "baseline": {"state": "present"},
            "policy": {"resolution_status": "PASS"},
            "status": {"status": {"automatic_mode_enabled": True}},
            "report": {
                "verdict": "WARN",
                "findings": [{"id": "f1"}, {"id": "f2"}],
                "blockers": [{"id": "b1"}],
                "warnings": [{"id": "w1"}],
            },
            "report_error": None,
        },
    }


def test_handler_factory_returns_explicit_subclass(tmp_path: Path) -> None:
    handler = command_center_handler(_FakeHandler, tmp_path)

    assert issubclass(handler, _FakeHandler)
    assert handler is not _FakeHandler
    assert handler.__name__ == "CommandCenterWorkbenchHandler"
    assert _FakeHandler.do_GET.__name__ == "do_GET"
    assert _FakeHandler._serve_static.__name__ == "_serve_static"


def test_installed_route_returns_authenticated_snapshot() -> None:
    module = _module()
    original = module.WorkbenchHandler
    install_command_center_route(module)
    handler = module.WorkbenchHandler(COMMAND_CENTER_ROUTE)

    assert issubclass(module.WorkbenchHandler, original)
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


def test_non_command_center_route_delegates_to_base_handler() -> None:
    module = _module()
    install_command_center_route(module)
    handler = module.WorkbenchHandler("/api/status")

    before = module.WorkbenchHandler.original_calls
    handler.do_GET()

    assert module.WorkbenchHandler.original_calls == before + 1


def test_posture_derivations_match_embedded_artifacts() -> None:
    _validate_snapshot_derivations(_snapshot())


def test_posture_rejects_report_verdict_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["verdict"] = "PASS"

    with pytest.raises(ValueError, match="verdict does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_posture_rejects_report_count_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["finding_count"] = 1

    with pytest.raises(ValueError, match="finding_count does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_posture_rejects_artifact_state_drift() -> None:
    snapshot = _snapshot()
    snapshot["posture"]["baseline_state"] = "stale"

    with pytest.raises(ValueError, match="baseline_state does not match embedded artifacts"):
        _validate_snapshot_derivations(snapshot)


def test_posture_without_report_requires_null_verdict_and_zero_counts() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"]["report"] = None
    snapshot["posture"].update(
        verdict=None,
        finding_count=0,
        blocker_count=0,
        warning_count=0,
    )

    _validate_snapshot_derivations(snapshot)

    snapshot["posture"]["warning_count"] = 1
    with pytest.raises(ValueError, match="warning_count does not match canonical report"):
        _validate_snapshot_derivations(snapshot)


def test_index_injects_aggregate_client_once(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<body>Command Center</body>", encoding="utf-8")
    module = _module(tmp_path)
    install_command_center_route(module)
    handler = module.WorkbenchHandler("/")

    handler._serve_static("/")

    body = handler.wfile.getvalue().decode("utf-8")
    assert handler.response_status == 200
    assert body.count(f'<script src="{COMMAND_CENTER_CLIENT}"></script>') == 1
    assert body.count(WORKBENCH_RELEASE_MARKER) == 1
    assert "SourcePack Workbench" in body
    assert body.endswith("</body>")


def test_non_index_asset_delegates_to_base_static_handler() -> None:
    module = _module()
    install_command_center_route(module)
    handler = module.WorkbenchHandler("/app.css")

    before = module.WorkbenchHandler.original_static_calls
    handler._serve_static("/app.css")

    assert module.WorkbenchHandler.original_static_calls == before + 1


def test_installation_is_idempotent() -> None:
    module = _module()
    install_command_center_route(module)
    first_handler = module.WorkbenchHandler

    install_command_center_route(module)

    assert module.WorkbenchHandler is first_handler
