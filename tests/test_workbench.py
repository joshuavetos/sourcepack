import http.client
import json
import threading
from pathlib import Path

from sourcepack.workbench import WorkbenchHandler, WorkbenchServer, _is_relative_to


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
