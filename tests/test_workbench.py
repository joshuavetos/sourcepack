import http.client
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from sourcepack import workbench
from sourcepack.policy import resolve_effective_policy
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


def _write_report(repo: Path, verdict: str, blockers=None, warnings=None):
    report_path = repo / ".sourcepack" / "reports" / "latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"schema_version": "traffic_report.v1", "verdict": verdict, "blockers": blockers or [], "warnings": warnings or []}), encoding="utf-8")


def _repo_snapshot(repo: Path) -> tuple[list[str], str | None, dict[str, str], bool]:
    tree = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False).stdout if (repo / ".git").exists() else None
    tracked: dict[str, str] = {}
    if status is not None:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=repo, stdout=subprocess.PIPE, check=True).stdout
        for raw in listed.split(b"\0"):
            if raw:
                path = repo / os.fsdecode(raw)
                tracked[os.fsdecode(raw)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return tree, status, tracked, (repo / ".sourcepack").exists()


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


def test_dashboard_routes_are_token_protected_and_versioned(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        paths = ("overview", "policy", "report", "baseline", "replay-evidence", "overrides")
        for name in paths:
            status, body, _ = request(server, "GET", f"/api/dashboard/v1/{name}")
            assert status == 403
            assert json.loads(body)["error"]["code"] == "unauthorized"
            status, body, _ = request(server, "GET", f"/api/dashboard/v1/{name}", {"X-SourcePack-Token": "test-token"})
            assert status == 200
            assert json.loads(body)["schema_version"] == f"sourcepack.dashboard.{name.replace('-', '_')}.v1"
        status, body, _ = request(server, "POST", "/api/dashboard/v1/overview", {"X-SourcePack-Token": "test-token"})
        assert status == 405
        assert json.loads(body)["error"]["message"] == "Dashboard endpoints are read-only."
        assert request(server, "GET", "/api/dashboard/v1/%2e%2e/overview", {"X-SourcePack-Token": "test-token"})[0] == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_report_surfaces_canonical_artifact_states(tmp_path):
    server, thread = start_server(tmp_path)
    headers = {"X-SourcePack-Token": "test-token"}
    latest = tmp_path / ".sourcepack" / "reports" / "latest.json"
    latest.parent.mkdir(parents=True)
    try:
        latest.write_text("{", encoding="utf-8")
        status, body, _ = request(server, "GET", "/api/dashboard/v1/report", headers)
        assert status == 200 and json.loads(body)["error"]["code"] == "artifact_malformed"
        status, body, _ = request(server, "GET", "/api/dashboard/v1/overrides", headers)
        data = json.loads(body)
        assert status == 200 and data["schema_version"] == "sourcepack.dashboard.overrides.v1" and data["error"]["code"] == "artifact_malformed"
        latest.write_text(json.dumps({"schema_version": "future.v9"}), encoding="utf-8")
        status, body, _ = request(server, "GET", "/api/dashboard/v1/report", headers)
        assert json.loads(body)["error"]["code"] == "artifact_version_unsupported"
        status, body, _ = request(server, "GET", "/api/dashboard/v1/overrides", headers)
        data = json.loads(body)
        assert status == 200 and data["schema_version"] == "sourcepack.dashboard.overrides.v1" and data["status"] == "unsupported" and data["error"]["code"] == "artifact_version_unsupported"
        report = {"schema_version": "traffic_report.v1", "verdict": "FAIL", "blockers": [{"message": "<b>stored</b>"}], "warnings": [{"message": "warning"}]}
        latest.write_text(json.dumps(report), encoding="utf-8")
        status, body, _ = request(server, "GET", "/api/dashboard/v1/overview", headers)
        data = json.loads(body)
        assert status == 200 and data["report_verdict"] == "FAIL" and data["blocker_count"] == 1 and data["warning_count"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("git_repository", [False, True])
def test_dashboard_reads_are_read_only_inside_and_outside_git(tmp_path, git_repository):
    repo = tmp_path / ("git" if git_repository else "plain")
    repo.mkdir(); (repo / "tracked.txt").write_text("unchanged\n", encoding="utf-8")
    if git_repository:
        for command in (("git", "init"), ("git", "config", "user.email", "test@example.com"), ("git", "config", "user.name", "Test User"), ("git", "add", "tracked.txt"), ("git", "commit", "-m", "initial")):
            subprocess.run(command, cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    before = _repo_snapshot(repo)
    server, thread = start_server(repo)
    try:
        for section in ("overview", "policy", "report", "baseline", "replay-evidence", "overrides"):
            assert request(server, "GET", f"/api/dashboard/v1/{section}", {"X-SourcePack-Token": "test-token"})[0] == 200
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    assert _repo_snapshot(repo) == before


def test_dashboard_policy_preserves_actual_resolver_corpus(tmp_path, monkeypatch):
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    policy_dir = repo / ".sourcepack"; policy_dir.mkdir(); repo_policy = policy_dir / "policy.json"; org = tmp_path / "org.json"
    def set_org(rules, text=None):
        org.write_text(text if text is not None else json.dumps({"schema_version": "sourcepack.org_policy.v1", "policy_id": "engineering", "rules": rules}), encoding="utf-8")
    def set_repo(rules, text=None):
        repo_policy.write_text(text if text is not None else json.dumps({"schema_version": "sourcepack.policy.v1", "rules": rules}), encoding="utf-8")
    corpus = [resolve_effective_policy(repo, org_policy_mode="required")]
    set_org({"block_dependency_additions": True}); corpus.append(resolve_effective_policy(repo, org))
    set_org({}, "{"); corpus.append(resolve_effective_policy(repo, org))
    inside = policy_dir / "inside.json"; inside.write_text(json.dumps({"schema_version": "sourcepack.org_policy.v1", "policy_id": "inside", "rules": {}}), encoding="utf-8"); corpus.append(resolve_effective_policy(repo, inside))
    set_org({"block_dependency_additions": False}); set_repo({"block_dependency_additions": True}); corpus.append(resolve_effective_policy(repo, org))
    set_org({"block_dependency_additions": True}); set_repo({"block_dependency_additions": False}); corpus.append(resolve_effective_policy(repo, org))
    set_org({"package_manager": "pnpm"}); set_repo({"package_manager": "pnpm"}); corpus.append(resolve_effective_policy(repo, org))
    set_repo({}, "{"); corpus.append(resolve_effective_policy(repo, org))
    server, thread = start_server(repo)
    try:
        for expected in corpus:
            monkeypatch.setattr(workbench, "resolve_effective_policy", lambda _repo, result=expected: result)
            status, body, _ = request(server, "GET", "/api/dashboard/v1/policy", {"X-SourcePack-Token": "test-token"})
            assert status == 200 and json.loads(body)["policy"] == expected
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_dashboard_report_matrix_and_security_cases(tmp_path):
    server, thread = start_server(tmp_path); headers = {"X-SourcePack-Token": "test-token"}
    try:
        assert json.loads(request(server, "GET", "/api/dashboard/v1/report", headers)[1])["status"] == "empty"
        for verdict in ("PASS", "WARN", "FAIL"):
            report = {"schema_version": "traffic_report.v1", "verdict": verdict, "blockers": [{"severity": "error", "message": "<img src=x>"}], "warnings": [{"severity": "warn", "message": "<script>unsafe</script>"}]}
            _write_report(tmp_path, verdict, report["blockers"], report["warnings"])
            data = json.loads(request(server, "GET", "/api/dashboard/v1/report", headers)[1])
            assert data["report"] == report
        archive = tmp_path / ".sourcepack" / "reports" / "archive"; archive.mkdir()
        (archive / "older.json").write_text(json.dumps({"schema_version": "traffic_report.v1", "verdict": "PASS"}), encoding="utf-8")
        latest = tmp_path / ".sourcepack" / "reports" / "latest.json"; latest.write_text('{"token":"sk-proj-secret-value"', encoding="utf-8")
        body = request(server, "GET", "/api/dashboard/v1/report", headers)[1]
        assert json.loads(body)["error"]["code"] == "artifact_malformed" and b"sk-proj-secret-value" not in body
        ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        assert "innerHTML" not in ui and "textContent" in ui
        assert request(server, "PATCH", "/api/dashboard/v1/report", headers)[0] == 501
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_dashboard_normal_use_has_no_external_connections(tmp_path, monkeypatch):
    connections = []
    original = workbench.socket.create_connection
    def record_connection(address, *args, **kwargs):
        connections.append(address)
        assert address[0] in {"127.0.0.1", "::1", "localhost"}
        return original(address, *args, **kwargs)
    monkeypatch.setattr(workbench.socket, "create_connection", record_connection)
    server, thread = start_server(tmp_path)
    try:
        for section in ("overview", "policy", "report", "baseline", "replay-evidence", "overrides"):
            assert request(server, "GET", f"/api/dashboard/v1/{section}", {"X-SourcePack-Token": "test-token"})[0] == 200
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    assert connections


def test_static_serving_strips_query_and_rejects_traversal(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, body, headers = request(server, "GET", "/?token=test-token")
        assert status == 200
        assert b"SourcePack Workbench" in body
        assert "Access-Control-Allow-Origin" not in headers

        status, _, _ = request(server, "GET", "/../../pyproject.toml")
        assert status in {403, 404}

        status, _, _ = request(server, "GET", "/%2e%2e/pyproject.toml")
        assert status in {403, 404}

        status, _, _ = request(server, "GET", "/C:/windows/system32/cmd.exe")
        assert status in {403, 404}

        status, _, _ = request(server, "GET", "/\\windows\\system32\\cmd.exe")
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
