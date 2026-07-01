from __future__ import annotations

import json
import mimetypes
import secrets
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

STATIC_ROOT = Path(__file__).with_name("workbench_static")
REQUEST_TIMEOUT_SECONDS = 120


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents


def _run_sourcepack(repo: Path, args: list[str], timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
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
    return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}


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

    def do_GET(self) -> None:
        requested = urllib.parse.urlparse(self.path).path
        if requested.startswith("/api/"):
            if not self._require_api_token():
                return
            if requested == "/api/status":
                self._send_json(200, _run_sourcepack(self.repo_root, ["status", str(self.repo_root), "--json"]))
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
        if not requested.startswith("/api/"):
            self.send_error(404)
            return
        if not self._require_api_token():
            return
        if requested == "/api/review":
            self._send_json(200, _run_sourcepack(self.repo_root, ["diff", str(self.repo_root), "--json"]))
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def _serve_static(self, requested: str) -> None:
        relative = requested.lstrip("/") or "index.html"
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


def serve_workbench(repo: str | Path = ".", host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> int:
    if host == "0.0.0.0":
        raise ValueError("Workbench refuses to bind to 0.0.0.0")
    token = secrets.token_urlsafe(32)
    repo_root = Path(repo).resolve()
    with WorkbenchServer((host, port), WorkbenchHandler, repo_root, token) as httpd:
        actual_host, actual_port = httpd.server_address
        url = f"http://{actual_host}:{actual_port}/?token={urllib.parse.quote(token)}"
        print(f"SourcePack Workbench: http://{actual_host}:{actual_port}/")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
