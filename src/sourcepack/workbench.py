from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import socket
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .baseline import validate_baseline
from .git import metadata as git_metadata
from .overrides import OVERRIDE_SCHEMA_VERSION, override_applies
from .paths import sourcepack_paths
from .policy import resolve_effective_policy

STATIC_ROOT = Path(__file__).with_name("workbench_static")
REQUEST_TIMEOUT_SECONDS = 120
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
DASHBOARD_PREFIX = "/api/dashboard/v1/"
TRAFFIC_REPORT_SCHEMA_VERSION = "traffic_report.v1"
WORKBENCH_EXCERPT_FILE_LIMIT_BYTES = 128 * 1024


def _dashboard_error(section: str, code: str, message: str, status: str = "error") -> dict[str, Any]:
    return {"schema_version": f"sourcepack.dashboard.{section}.v1", "ok": False, "status": status, "error": {"code": code, "message": message}}


def _read_canonical_report(repo: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read only the established latest.json location; never search archives."""
    path = sourcepack_paths(repo)["latest_json"]
    if not path.is_file():
        return None, None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, _dashboard_error("report", "artifact_malformed", "The canonical report is malformed.")
    if not isinstance(report, dict):
        return None, _dashboard_error("report", "artifact_malformed", "The canonical report is malformed.")
    if report.get("schema_version") != TRAFFIC_REPORT_SCHEMA_VERSION:
        return None, _dashboard_error("report", "artifact_version_unsupported", "The canonical report version is unsupported.", "unsupported")
    return report, None


def _safe_report_paths(report: dict[str, Any]) -> list[str]:
    raw = report.get("raw_patch_judgment") if isinstance(report.get("raw_patch_judgment"), dict) else {}
    paths: list[str] = []
    for key in ("modified_files", "new_files", "deleted_files", "missing_modified_files"):
        values = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value not in paths:
                    paths.append(value)
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and isinstance(finding.get("path"), str) and finding["path"] not in paths:
            paths.append(finding["path"])
    return paths[:8]


def _bounded_changed_file_excerpt(repo: Path, report: dict[str, Any]) -> dict[str, Any]:
    paths = _safe_report_paths(report)
    terms = sorted({str(finding.get("evidence") or "").lower() for finding in report.get("findings", []) if isinstance(finding, dict) and finding.get("evidence")})
    excerpts: list[dict[str, Any]] = []
    root = repo.resolve()
    for rel in paths:
        if not rel or Path(rel).is_absolute() or rel.startswith(("..", "/", "\\")):
            continue
        target = (root / rel).resolve()
        if not _is_relative_to(target, root) or not target.is_file():
            continue
        try:
            data = target.open("rb").read(WORKBENCH_EXCERPT_FILE_LIMIT_BYTES + 1)
        except OSError:
            excerpts.append({"path": rel, "source": "current_worktree_file_listed_by_canonical_report", "status": "omitted", "reason": "file_unreadable", "lines": []})
            continue
        status = "truncated" if len(data) > WORKBENCH_EXCERPT_FILE_LIMIT_BYTES else "available"
        if status == "truncated":
            data = data[:WORKBENCH_EXCERPT_FILE_LIMIT_BYTES]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            excerpts.append({"path": rel, "source": "current_worktree_file_listed_by_canonical_report", "status": "omitted", "reason": "file_not_utf8", "lines": []})
            continue
        lines = text.splitlines()
        selected: list[int] = []
        for index, line in enumerate(lines):
            low = line.lower()
            if any(term and term in low for term in terms):
                selected.extend(range(max(0, index - 1), min(len(lines), index + 2)))
        if not selected:
            selected = list(range(min(len(lines), 8)))
        selected = sorted(set(selected))[:12]
        excerpts.append({"path": rel, "source": "current_worktree_file_listed_by_canonical_report", "status": status, "byte_limit": WORKBENCH_EXCERPT_FILE_LIMIT_BYTES, "lines": [{"number": i + 1, "text": lines[i]} for i in selected]})
    return {"schema_version": "sourcepack.dashboard.proposed_change.v1", "source": "traffic_report.raw_patch_judgment plus bounded current worktree excerpt", "paths": paths, "excerpts": excerpts}

def _report_payload(repo: Path) -> dict[str, Any]:
    report, error = _read_canonical_report(repo)
    if error:
        return error
    if report is None:
        return {"schema_version": "sourcepack.dashboard.report.v1", "ok": True, "status": "empty", "error": {"code": "report_unavailable", "message": "No canonical report is available."}, "report": None}
    return {"schema_version": "sourcepack.dashboard.report.v1", "ok": True, "status": "success", "report_path": ".sourcepack/reports/latest.json", "report": report, "proposed_change": _bounded_changed_file_excerpt(repo, report)}


def _dashboard_payload(repo: Path, section: str) -> dict[str, Any]:
    try:
        if not repo.is_dir():
            return _dashboard_error(section, "repository_unavailable", "The Workbench repository is unavailable.")
        if section == "report":
            return _report_payload(repo)
        if section == "policy":
            policy = resolve_effective_policy(repo)
            status = "success" if policy.get("resolution_status") == "PASS" else "error"
            payload = {"schema_version": "sourcepack.dashboard.policy.v1", "ok": status == "success", "status": status, "policy": policy}
            if status != "success":
                payload["error"] = {"code": "policy_resolution_failed", "message": "Policy resolution failed."}
            return payload
        if section == "baseline":
            baseline = validate_baseline(repo)
            status = "success" if baseline.get("state") in {"present", "stale"} else "empty" if baseline.get("state") == "missing" else "error"
            payload = {"schema_version": "sourcepack.dashboard.baseline.v1", "ok": bool(baseline.get("ok")), "status": status, "baseline": baseline}
            if status == "empty": payload["error"] = {"code": "baseline_unavailable", "message": "No trusted baseline is available."}
            if status == "error": payload["error"] = {"code": "artifact_malformed", "message": "The baseline is unavailable or malformed."}
            return payload
        if section == "replay-evidence":
            report, error = _read_canonical_report(repo)
            if error:
                error["schema_version"] = "sourcepack.dashboard.replay_evidence.v1"
                return error
            if report is None:
                return {"schema_version": "sourcepack.dashboard.replay_evidence.v1", "ok": True, "status": "empty", "replay": None, "evidence": None}
            return {"schema_version": "sourcepack.dashboard.replay_evidence.v1", "ok": True, "status": "success", "report_path": ".sourcepack/reports/latest.json", "replay": report.get("replay_bundle"), "evidence": report.get("evidence_items", report.get("evidence")), "reason_code_evidence": report.get("reason_code_evidence")}
        if section == "overrides":
            # The decision ledger is the persisted SourcePack override record.
            ledger = sourcepack_paths(repo)["base"] / "decisions.jsonl"
            overrides: list[dict[str, Any]] = []
            if ledger.is_file():
                for line in ledger.read_text(encoding="utf-8").splitlines():
                    try: event = json.loads(line)
                    except json.JSONDecodeError:
                        return _dashboard_error("overrides", "artifact_malformed", "The persisted override record is malformed.")
                    data = event.get("data") if isinstance(event, dict) else None
                    override = data.get("override") if isinstance(data, dict) else None
                    if isinstance(override, dict) and override.get("schema_version") == OVERRIDE_SCHEMA_VERSION:
                        overrides.append({**override, "currently_applicable": override_applies(override), "related_finding": data.get("finding_id")})
            report, report_error = _read_canonical_report(repo)
            if report_error:
                report_error["schema_version"] = "sourcepack.dashboard.overrides.v1"
                return report_error
            findings = [item for item in (report or {}).get("findings", []) if isinstance(item, dict) and item.get("category") == "policy"]
            return {"schema_version": "sourcepack.dashboard.overrides.v1", "ok": True, "status": "success" if overrides or findings else "empty", "overrides": overrides, "policy_findings": findings}
        if section == "overview":
            git = git_metadata(repo)
            baseline = validate_baseline(repo)
            policy = resolve_effective_policy(repo)
            report, report_error = _read_canonical_report(repo)
            report_state = "error" if report_error else "empty" if report is None else "available"
            return {"schema_version": "sourcepack.dashboard.overview.v1", "ok": True, "status": "success", "repository": {"path": str(repo), "sourcepack_version": __version__}, "git": git, "baseline": baseline, "policy_resolution_status": policy.get("resolution_status"), "report_status": report_state, "report_verdict": report.get("verdict") if report else None, "blocker_count": len(report.get("blockers", [])) if report else 0, "warning_count": len(report.get("warnings", [])) if report else 0}
    except Exception:
        return _dashboard_error(section, "internal_error", "Dashboard data could not be read.")
    return _dashboard_error(section, "internal_error", "Dashboard section is unavailable.")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents


def _run_sourcepack(repo: Path, args: list[str], timeout: int = REQUEST_TIMEOUT_SECONDS, output_key: str | None = None) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "sourcepack.cli", *args]
    try:
        cp = subprocess.run(
            cmd,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "timeout": True,
            "error": "sourcepack_command_timeout",
            "message": f"SourcePack command timed out after {timeout} seconds.",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    result: dict[str, Any] = {"ok": cp.returncode == 0, "returncode": cp.returncode, "stderr": cp.stderr}
    if output_key is not None and cp.stdout.strip():
        try:
            result[output_key] = json.loads(cp.stdout)
        except json.JSONDecodeError:
            result["stdout"] = cp.stdout
            result["parse_error"] = "invalid_json_stdout"
    else:
        result["stdout"] = cp.stdout
    return result


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
        if requested.startswith("/api/"):
            if not self._require_api_token():
                return
            if requested == "/api/status":
                self._send_json(200, _run_sourcepack(self.repo_root, ["status", str(self.repo_root), "--json"], output_key="status"))
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
        if requested == "/api/review":
            self._send_json(200, _run_sourcepack(self.repo_root, ["diff", str(self.repo_root), "--json"], output_key="review"))
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

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
