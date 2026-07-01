import http.client
import json
import subprocess
import sys
import threading

import pytest

from sourcepack import workbench
from sourcepack.workbench import IPv6WorkbenchServer, WorkbenchHandler, WorkbenchServer, _is_relative_to


class FakeWorkbenchServer:
    server_address = ("127.0.0.1", 4321)
    closed = False

    def __init__(self, server_address, handler_class, repo_root, session_token):
        self.init_args = (server_address, handler_class, repo_root, session_token)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


def start_server(tmp_path):
    server = WorkbenchServer(("127.0.0.1", 0), WorkbenchHandler, tmp_path, "test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def request(server, method, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    conn.request(method, path, headers=headers or {})
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response.status, body, dict(response.getheaders())


def test_api_routes_require_valid_sourcepack_token(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        for headers in ({}, {"X-SourcePack-Token": "wrong"}, {"X-SourcePack-Token": "bad token"}):
            status, body, _ = request(server, "GET", "/api/status", headers)
            assert status == 403
            assert json.loads(body)["error"] == "forbidden"

        status, _, _ = request(server, "GET", "/api/latest", {"X-SourcePack-Token": "test-token"})
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_static_serving_strips_query_and_rejects_traversal(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, body, headers = request(server, "GET", "/?token=test-token")
        assert status == 200
        assert b"SourcePack Workbench" in body
        assert "Access-Control-Allow-Origin" not in headers

        status, _, _ = request(server, "GET", "/../../pyproject.toml")
        assert status in {403, 404}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_is_relative_to_compatibility_helper(tmp_path):
    root = tmp_path / "static"
    child = root / "app.js"
    other = tmp_path / "other.js"
    root.mkdir()
    child.write_text("", encoding="utf-8")
    other.write_text("", encoding="utf-8")
    assert _is_relative_to(child.resolve(), root.resolve())
    assert not _is_relative_to(other.resolve(), root.resolve())


def test_ui_and_workbench_help_are_registered():
    ui_help = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "ui", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert ui_help.returncode == 0
    assert "serve the local SourcePack Workbench" in ui_help.stdout

    workbench_help = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "workbench", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert workbench_help.returncode == 0
    assert "alias for sourcepack ui" in workbench_help.stdout


def test_no_open_prints_tokenized_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")

    assert workbench.serve_workbench(tmp_path, open_browser=False) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/?token=fixed-token"


def test_browser_open_false_prints_tokenized_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")
    monkeypatch.setattr(workbench.webbrowser, "open", lambda url: False)

    assert workbench.serve_workbench(tmp_path, open_browser=True) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/?token=fixed-token"


def test_browser_open_true_prints_base_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")
    monkeypatch.setattr(workbench.webbrowser, "open", lambda url: True)

    assert workbench.serve_workbench(tmp_path, open_browser=True) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/"


def test_requested_hosts_are_validated():
    for host in ("", "0", "0.0.0.0", "::", "192.168.1.10"):
        with pytest.raises(ValueError, match="only binds to explicit loopback hosts"):
            workbench._validate_requested_host(host)

    for host in ("127.0.0.1", "localhost", "::1"):
        workbench._validate_requested_host(host)


def test_actual_bound_host_is_validated_before_serving(monkeypatch, tmp_path):
    class NonLoopbackServer(FakeWorkbenchServer):
        server_address = ("192.168.1.10", 4321)

        def serve_forever(self):
            raise AssertionError("serve_forever must not run for non-loopback bound host")

    server_holder = {}

    class CapturingServer(NonLoopbackServer):
        def __init__(self, *args):
            super().__init__(*args)
            server_holder["server"] = self

    monkeypatch.setattr(workbench, "WorkbenchServer", CapturingServer)

    with pytest.raises(ValueError, match="refused non-loopback bound address"):
        workbench.serve_workbench(tmp_path, host="127.0.0.1", open_browser=False)
    assert server_holder["server"].closed


def test_ipv6_loopback_uses_ipv6_server_and_url_host():
    assert workbench._server_class_for_host("::1") is IPv6WorkbenchServer
    assert workbench._server_class_for_host("127.0.0.1") is WorkbenchServer
    assert workbench._url_host("::1") == "[::1]"
