from __future__ import annotations

import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any

COMMAND_CENTER_ROUTE = "/api/command-center/v1/snapshot"
COMMAND_CENTER_CLIENT = "/command-center-aggregate.js"
WORKBENCH_RELEASE_MARKER = "<!-- SourcePack Workbench -->"
_INSTALL_MARKER = "_sourcepack_command_center_handler_installed"


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _validate_snapshot_derivations(snapshot: dict[str, Any]) -> None:
    """Reject posture fields that disagree with their embedded artifacts."""
    posture = snapshot["posture"]
    artifacts = snapshot["artifacts"]
    baseline = artifacts["baseline"]
    policy = artifacts["policy"]
    status = artifacts["status"]
    report = artifacts["report"]

    status_data = status.get("status") if isinstance(status.get("status"), dict) else {}
    expected_artifact_fields = {
        "baseline_state": baseline.get("state"),
        "policy_resolution_status": policy.get("resolution_status"),
        "automatic_mode_enabled": bool(status_data.get("automatic_mode_enabled", False)),
    }
    for field, expected in expected_artifact_fields.items():
        if posture.get(field) != expected:
            raise ValueError(f"Command Center posture {field} does not match embedded artifacts")

    if report is None:
        expected_report_fields = {
            "verdict": None,
            "finding_count": 0,
            "blocker_count": 0,
            "warning_count": 0,
        }
    else:
        expected_report_fields = {
            "verdict": report.get("verdict"),
            "finding_count": _list_count(report.get("findings")),
            "blocker_count": _list_count(report.get("blockers")),
            "warning_count": _list_count(report.get("warnings")),
        }
    for field, expected in expected_report_fields.items():
        if posture.get(field) != expected:
            raise ValueError(f"Command Center posture {field} does not match canonical report")


def _validate_report_error_derivations(snapshot: dict[str, Any]) -> None:
    """Reject report, report-error, and activity combinations that disagree."""
    artifacts = snapshot["artifacts"]
    report = artifacts["report"]
    report_error = artifacts["report_error"]
    activity = snapshot["activity"]
    terminal_error = activity[-1] if activity and activity[-1].get("type") == "error" else None

    if report is not None and report_error is not None:
        raise ValueError("Command Center cannot expose both a canonical report and report_error")

    if report_error is None:
        if terminal_error is not None:
            raise ValueError("Command Center terminal error activity requires report_error")
        return

    if report is not None:
        raise ValueError("Command Center report_error requires canonical report to be absent")
    if terminal_error is None:
        raise ValueError("Command Center report_error requires terminal error activity")

    error_data = report_error.get("error") if isinstance(report_error, dict) else None
    expected_message = error_data.get("message") if isinstance(error_data, dict) else None
    if not isinstance(expected_message, str) or not expected_message:
        expected_message = "Canonical report unavailable"
    if terminal_error.get("message") != expected_message:
        raise ValueError("Command Center terminal error activity does not match report_error")


def _validate_score_derivations(snapshot: dict[str, Any]) -> None:
    """Reject displayed scores that disagree with the canonical scoring model."""
    from .command_center import _capabilities, _score

    artifacts = snapshot["artifacts"]
    baseline = artifacts["baseline"]
    policy = artifacts["policy"]
    status = artifacts["status"]
    report = artifacts["report"]
    capabilities = _capabilities(
        baseline=baseline,
        policy=policy,
        report=report,
        status=status,
    )
    expected_scores = _score(
        baseline=baseline,
        policy=policy,
        report=report,
        status=status,
        capabilities=capabilities,
    )
    if snapshot["scores"] != expected_scores:
        raise ValueError("Command Center scores do not match the canonical scoring model")


def command_center_payload(repo: str | Path) -> dict[str, Any]:
    """Build and validate the canonical Command Center snapshot."""
    from .command_center import build_command_center_snapshot
    from .command_center_contract import validate_command_center_snapshot

    try:
        snapshot = build_command_center_snapshot(repo)
        validate_command_center_snapshot(snapshot)
        _validate_snapshot_derivations(snapshot)
        _validate_report_error_derivations(snapshot)
        _validate_score_derivations(snapshot)
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
