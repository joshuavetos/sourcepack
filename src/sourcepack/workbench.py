from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import socket
import urllib.parse
import webbrowser
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .baseline import baseline_report_fields, validate_baseline
from .command_center_endpoint import COMMAND_CENTER_ROUTE, command_center_payload
from .command_center_limits import MAX_COLLECTION_ITEMS, MAX_EXCERPTS, MAX_LINE_CHARS, clip_text
from .git import metadata as git_metadata, run_git
from .overrides import OVERRIDE_SCHEMA_VERSION, override_applies
from .paths import sourcepack_paths
from .policy import PolicyMode, resolve_effective_policy
from .judgment import git_worktree_dirty, judge_repo_change, utc_now
from .reports.json import validate_report_construction_metadata, write_user_report

STATIC_ROOT = Path(__file__).with_name("workbench_static")
REQUEST_TIMEOUT_SECONDS = 120
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
DASHBOARD_PREFIX = "/api/dashboard/v1/"
WORKBENCH_REVIEW_ROUTE = "/api/workbench/v1/review"
TRAFFIC_REPORT_SCHEMA_VERSION = "traffic_report.v1"


# Compatibility exports for callers of the historical Workbench helpers.
from .command_center_state import (
    WORKBENCH_EXCERPT_FILE_LIMIT_BYTES,
    CANONICAL_REPORT_COLLECTION_LIMIT,
    CANONICAL_REPORT_FILE_LIMIT_BYTES,
    CANONICAL_REPORT_MAPPING_LIMIT,
    CANONICAL_REPORT_NESTING_LIMIT,
    CANONICAL_REPORT_STRING_LIMIT_CHARS,
    DECISION_LEDGER_BYTE_LIMIT,
    DECISION_LEDGER_LINE_LIMIT_BYTES,
    DECISION_LEDGER_RECORD_LIMIT,
    _bounded_changed_file_excerpt,
    _dashboard_error,
    _dashboard_payload,
    _decision_completeness,
    _decision_limit_error,
    _read_canonical_report,
    _read_decision_ledger,
    _report_payload,
    _report_shape_limit,
    _safe_report_paths,
    _sourcepack_status_payload,
    _workbench_action,
    validate_decision_completeness,
)


def _dashboard_payload(
    repo: Path,
    section: str,
    *,
    policy_reader=None,
    git_reader=None,
) -> dict[str, Any]:
    """Delegate with request-local dependencies while preserving monkeypatch seams."""
    from . import command_center_state as state

    return state.dashboard_payload(
        repo,
        section,
        policy_reader=policy_reader or resolve_effective_policy,
        git_reader=git_reader or git_metadata,
    )



def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents



def run_bounded_workbench_review(repo: Path) -> dict[str, Any]:
    """Run the same CLI-independent judgment path used by `sourcepack diff .`.

    The CLI calls sourcepack.judgment.judge_repo_change() and then writes the
    canonical user report. Workbench reuses that same function directly, with
    no shell, no client-supplied repo path, and no command input.
    """
    started_at = __import__("time").time()
    stages = [
        "Reading repository state",
        "Acquiring proposed diff",
        "Checking repository evidence",
        "Writing canonical report",
        "Loading result",
    ]
    root = repo.resolve()
    judgment = judge_repo_change(root, policy_mode=PolicyMode.LOCAL, allow_missing_baseline_init=False)
    write_user_report(root, judgment.report, "diff")
    payload = _report_payload(root)
    return {
        "schema_version": "sourcepack.workbench.review_operation.v1",
        "ok": True,
        "status": "completed",
        "operation": "bounded_canonical_review",
        "verdict": judgment.verdict,
        "exit_code": judgment.exit_code(),
        "canonical_report_path": ".sourcepack/reports/latest.json",
        "stages": stages,
        "elapsed_seconds": round(__import__("time").time() - started_at, 3),
        "report": payload.get("report"),
        "report_payload": payload,
        "report_status": payload.get("status"),
        "action": payload.get("action"),
    }


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "SourcePackWorkbench/0"

    @property
    def session_token(self) -> str:
        return self.server.session_token  # type: ignore[attr-defined]

    @property
    def repo_root(self) -> Path:
        return self.server.repo_root  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_review_method_not_allowed(self) -> None:
        body = json.dumps({"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "method_not_allowed", "message": "Use POST to run a bounded Workbench review."}}, indent=2).encode("utf-8")
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_token_valid(self) -> bool:
        values = self.headers.get_all("X-SourcePack-Token") or []
        if len(values) != 1:
            return False
        token = values[0]
        if not token or any(ch.isspace() for ch in token):
            return False
        return secrets.compare_digest(token, self.session_token)

    def _require_api_token(self) -> bool:
        if self._api_token_valid():
            return True
        self._send_json(403, {"ok": False, "error": "forbidden"})
        return False

    def _require_dashboard_token(self) -> bool:
        if self._api_token_valid():
            return True
        self._send_json(403, _dashboard_error("authorization", "unauthorized", "A valid session token is required."))
        return False

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        requested = parsed.path
        if requested.startswith(DASHBOARD_PREFIX):
            if not self._require_dashboard_token():
                return
            section = requested.removeprefix(DASHBOARD_PREFIX)
            sections = {"overview", "policy", "report", "baseline", "replay-evidence", "overrides"}
            if section not in sections or "/" in section or "%" in requested:
                self._send_json(404, _dashboard_error("routing", "internal_error", "Dashboard route was not found."))
                return
            self._send_json(200, _dashboard_payload(self.repo_root, section))
            return
        if requested == WORKBENCH_REVIEW_ROUTE:
            if not self._require_api_token():
                return
            self._send_review_method_not_allowed()
            return
        if requested == COMMAND_CENTER_ROUTE:
            if not self._require_api_token():
                return
            payload = command_center_payload(self.repo_root)
            self._send_json(200 if payload.get("ok") else 500, payload)
            return
        if requested.startswith("/api/"):
            if not self._require_api_token():
                return
            if requested == "/api/status":
                self._send_json(200, _sourcepack_status_payload(self.repo_root))
                return
            if requested == "/api/latest":
                latest = self.repo_root / ".sourcepack" / "reports" / "latest.json"
                if not latest.is_file():
                    self._send_json(404, {"ok": False, "error": "latest_report_missing"})
                    return
                try:
                    self._send_json(200, {"ok": True, "report": json.loads(latest.read_text(encoding="utf-8"))})
                except json.JSONDecodeError as exc:
                    self._send_json(500, {"ok": False, "error": "latest_report_invalid_json", "message": str(exc)})
                return
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._serve_static(requested)

    def do_POST(self) -> None:
        requested = urllib.parse.urlparse(self.path).path
        if requested.startswith(DASHBOARD_PREFIX):
            if not self._require_dashboard_token():
                return
            self._send_json(405, _dashboard_error("routing", "internal_error", "Dashboard endpoints are read-only."))
            return
        if not requested.startswith("/api/"):
            self.send_error(404)
            return
        if not self._require_api_token():
            return
        if requested in {WORKBENCH_REVIEW_ROUTE, "/api/review"}:
            self._handle_review_post()
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def _handle_review_unsupported_method(self) -> None:
        requested = urllib.parse.urlparse(self.path).path
        if requested != WORKBENCH_REVIEW_ROUTE:
            self.send_error(501)
            return
        if not self._require_api_token():
            return
        self._send_review_method_not_allowed()

    def do_PUT(self) -> None:
        self._handle_review_unsupported_method()

    def do_PATCH(self) -> None:
        self._handle_review_unsupported_method()

    def do_DELETE(self) -> None:
        self._handle_review_unsupported_method()

    def do_OPTIONS(self) -> None:
        self._handle_review_unsupported_method()

    def _handle_review_post(self) -> None:
        if self.headers.get("Origin") not in {None, f"http://{self.headers.get('Host')}", "null"}:
            self._send_json(403, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "csrf_rejected", "message": "Review requests must come from the Workbench same-origin session."}})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._send_json(400, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "bounded_request_only", "message": "Review requests must be empty or the empty JSON object."}})
            return
        if length < 0 or length > 2048:
            self._send_json(400, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "bounded_request_only", "message": "Review requests must be empty or the empty JSON object."}})
            return
        body = self.rfile.read(length) if length else b""
        if body.strip():
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "bounded_request_only", "message": "Review requests must be empty or the empty JSON object."}})
                return
            if payload != {}:
                self._send_json(400, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "bounded_request_only", "message": "Review requests must be empty or the empty JSON object."}})
                return
        if not self.server.review_lock.acquire(blocking=False):  # type: ignore[attr-defined]
            self._send_json(409, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "busy", "error": {"code": "review_already_running", "message": "A SourcePack review is already running for this Workbench."}})
            return
        lock_released_by_future = False
        def release_review_lock(_future: Any) -> None:
            nonlocal lock_released_by_future
            if lock_released_by_future:
                return
            lock_released_by_future = True
            try:
                self.server.review_lock.release()  # type: ignore[attr-defined]
            except RuntimeError:
                pass
        try:
            future = self.server.review_executor.submit(run_bounded_workbench_review, self.repo_root)  # type: ignore[attr-defined]
        except Exception:
            release_review_lock(None)
            self._send_json(500, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "review_execution_failed", "message": "SourcePack could not start the bounded review."}})
            return
        future.add_done_callback(release_review_lock)
        try:
            self._send_json(200, future.result(timeout=self.server.review_timeout_seconds))  # type: ignore[attr-defined]
        except TimeoutError:
            self._send_json(504, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "timed_out", "timeout_seconds": self.server.review_timeout_seconds, "error": {"code": "review_timeout", "message": f"SourcePack review timed out after {self.server.review_timeout_seconds} seconds and is still finishing in the background."}})  # type: ignore[attr-defined]
        except Exception:
            self._send_json(500, {"schema_version": "sourcepack.workbench.review_operation.v1", "ok": False, "status": "failed", "error": {"code": "review_execution_failed", "message": "SourcePack could not complete the bounded review."}})

    def _serve_static(self, requested: str) -> None:
        relative = urllib.parse.unquote(requested).lstrip("/\\") or "index.html"
        if Path(relative).is_absolute() or relative.startswith(".."):
            self.send_error(403)
            return
        static_root = STATIC_ROOT.resolve()
        target = (static_root / relative).resolve()
        if target != static_root and not _is_relative_to(target, static_root):
            self.send_error(403)
            return
        if target.is_dir():
            target = (target / "index.html").resolve()
            if not _is_relative_to(target, static_root):
                self.send_error(403)
                return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WorkbenchServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], repo_root: Path, session_token: str):
        super().__init__(server_address, handler_class)
        self.repo_root = repo_root
        self.session_token = session_token
        self.review_lock = threading.Lock()
        self.review_executor = ThreadPoolExecutor(max_workers=1)
        self.review_timeout_seconds = REQUEST_TIMEOUT_SECONDS

    def server_close(self) -> None:
        # Nonblocking shutdown: queued reviews are cancelled where possible, but
        # Python cannot forcibly terminate an already running in-process review.
        self.review_executor.shutdown(wait=False, cancel_futures=True)
        super().server_close()


class IPv6WorkbenchServer(WorkbenchServer):
    address_family = socket.AF_INET6


def _validate_requested_host(host: str) -> None:
    if host not in ALLOWED_LOOPBACK_HOSTS:
        allowed = ", ".join(sorted(ALLOWED_LOOPBACK_HOSTS))
        raise ValueError(f"Workbench only binds to explicit loopback hosts ({allowed}); got {host!r}")


def _validate_bound_host(host: str) -> None:
    normalized = "127.0.0.1" if host == "localhost" else host
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(f"Workbench bound to an invalid host: {host!r}") from exc
    if not address.is_loopback:
        raise ValueError(f"Workbench refused non-loopback bound address: {host!r}")


def _server_class_for_host(host: str) -> type[WorkbenchServer]:
    return IPv6WorkbenchServer if host == "::1" else WorkbenchServer


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def serve_workbench(repo: str | Path = ".", host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> int:
    _validate_requested_host(host)
    token = secrets.token_urlsafe(32)
    repo_root = Path(repo).resolve()
    server_class = _server_class_for_host(host)
    with server_class((host, port), WorkbenchHandler, repo_root, token) as httpd:
        actual_host, actual_port = httpd.server_address[:2]
        try:
            _validate_bound_host(actual_host)
        except ValueError:
            httpd.server_close()
            raise
        url_base = f"http://{_url_host(actual_host)}:{actual_port}/"
        url = f"{url_base}?token={urllib.parse.quote(token)}"
        opened = False
        if open_browser:
            opened = webbrowser.open(url)
        display_url = url_base if open_browser and opened else url
        print(f"SourcePack Workbench: {display_url}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
