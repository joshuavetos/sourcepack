from __future__ import annotations

import json
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sourcepack.cli import run_cli
from sourcepack.cloud import CloudClient, CloudConfig, CloudError, canonical_json_bytes, pull_policy
from sourcepack.hosted import Store, hash_password, initialize_database, make_handler, verify_password


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_cloud_status_is_unconfigured_without_touching_repository(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert run_cli(["cloud", "status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unconfigured"
    assert not (tmp_path / ".sourcepack").exists()


def test_cloud_config_and_canonical_json_are_deterministic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    config = CloudConfig("https://cloud.example", uploads_enabled=True, upload_categories=("report",))
    path = config.save()
    assert path.stat().st_mode & 0o077 == 0
    assert CloudConfig.load() == config
    assert canonical_json_bytes({"z": 1, "a": [True]}) == b'{"a":[true],"z":1}'


def test_hosted_database_initialization_is_persistent(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"
    initialize_database(database)
    initialize_database(database)
    assert database.is_file()


def test_hosted_password_hashing_uses_one_way_verification() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "wrong")


def test_hosted_authentication_roles_and_tenant_scoped_repositories(tmp_path: Path) -> None:
    store = Store(tmp_path / "cloud.sqlite")
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    outsider, other_organization = store.bootstrap("other@example.test", "password", "Two")
    assert store.login("owner@example.test", "wrong") is None
    tokens = store.login("owner@example.test", "password")
    assert tokens and store.actor("Bearer " + tokens["access_token"])["id"] == owner
    repository = store.create_repository(owner, organization, "Repository")
    assert store.repositories(owner, organization) == [repository]
    try:
        store.repositories(outsider, organization)
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-organization access must be denied")
    assert store.repositories(outsider, other_organization) == []


def test_refresh_rotates_credentials_and_revocation_stops_access(tmp_path: Path) -> None:
    store = Store(tmp_path / "cloud.sqlite")
    _, _ = store.bootstrap("owner@example.test", "password", "One")
    first = store.login("owner@example.test", "password")
    second = store.refresh(first["refresh_token"])
    assert second and store.actor("Bearer " + first["access_token"]) is None
    assert store.actor("Bearer " + second["access_token"]) is not None
    assert store.revoke("Bearer " + second["access_token"])
    assert store.actor("Bearer " + second["access_token"]) is None


def test_members_final_owner_and_service_assignment_lifecycle(tmp_path: Path) -> None:
    store = Store(tmp_path / "cloud.sqlite")
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    member, _ = store.bootstrap("member@example.test", "password", "Two")
    membership = store.add_membership(owner, organization, member, "maintainer")
    store.change_role(owner, organization, membership["id"], "owner")
    store.remove_member(owner, organization, membership["id"])
    owner_membership = next(item["id"] for item in store.members(owner, organization) if item["user_id"] == owner)
    try: store.remove_member(owner, organization, owner_membership)
    except ValueError as exc: assert str(exc) == "final_owner"
    else: raise AssertionError("final owner removal must be rejected")
    repository = store.create_repository(owner, organization, "repo")
    service, raw_token = store.create_service(owner, organization, "ci")
    assert raw_token and raw_token not in str(store.services(owner, organization))
    assignment = store.assign_service(owner, organization, service["id"], repository["id"])
    assert store.assignments(owner, organization, service["id"])[0]["id"] == assignment["id"]
    store.remove_assignment(owner, organization, assignment["id"])
    assert store.assignments(owner, organization, service["id"]) == []
    store.revoke_service(owner, organization, service["id"])


def test_inactive_repository_rejects_new_service_assignments(tmp_path: Path) -> None:
    store = Store(tmp_path / "cloud.sqlite")
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    repository = store.create_repository(owner, organization, "repo")
    service, _ = store.create_service(owner, organization, "ci")
    store.set_repository_status(owner, organization, repository["id"], "inactive")
    try: store.assign_service(owner, organization, service["id"], repository["id"])
    except LookupError: pass
    else: raise AssertionError("inactive repositories cannot receive assignments")


def test_service_token_authentication_is_assignment_and_status_scoped(tmp_path: Path) -> None:
    store = Store(tmp_path / "cloud.sqlite")
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    repository = store.create_repository(owner, organization, "repo")
    other = store.create_repository(owner, organization, "other")
    service, token = store.create_service(owner, organization, "ci")
    actor = store.actor("Bearer " + token)
    assert actor and actor["actor_kind"] == "service"
    assert not store.service_repository_access(actor, organization, repository["id"])
    assignment = store.assign_service(owner, organization, service["id"], repository["id"])
    assert store.service_repository_access(actor, organization, repository["id"])
    assert not store.service_repository_access(actor, organization, other["id"])
    store.remove_assignment(owner, organization, assignment["id"])
    assert not store.service_repository_access(actor, organization, repository["id"])
    replacement = store.assign_service(owner, organization, service["id"], repository["id"])
    assert replacement and store.service_repository_access(actor, organization, repository["id"])
    store.revoke_service(owner, organization, service["id"])
    assert store.actor("Bearer " + token) is None


def test_cloud_client_repository_routes_match_hosted_api(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"
    store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    tokens = store.login("owner@example.test", "password")
    server, url = _serve(make_handler(database))
    try:
        client = CloudClient(CloudConfig(url, organization_id=organization), tokens["access_token"])
        created = client.request("POST", f"organizations/{organization}/repositories", b'{"display_name":"Repository"}')
        assert created["data"]["organization_id"] == organization
        listed = client.request("GET", f"organizations/{organization}/repositories")
        assert [item["id"] for item in listed["data"]["items"]] == [created["data"]["id"]]
    finally:
        server.shutdown(); server.server_close()


def test_hosted_governance_routes_expose_members_repositories_and_services(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    member, _ = store.bootstrap("member@example.test", "password", "Two")
    token = store.login("owner@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database)); client = CloudClient(CloudConfig(url, organization_id=organization), token)
    try:
        membership = client.request("POST", f"organizations/{organization}/members", json.dumps({"user_id":member,"role":"reviewer"}).encode())["data"]
        assert client.request("PATCH", f"organizations/{organization}/members/{membership['id']}", b'{"role":"maintainer"}')["data"]["changed"]
        repository = client.request("POST", f"organizations/{organization}/repositories", b'{"display_name":"repo"}')["data"]
        assert client.request("GET", f"organizations/{organization}/repositories/{repository['id']}")["data"]["id"] == repository["id"]
        assert client.request("POST", f"organizations/{organization}/repositories/{repository['id']}/deactivate", b'{}')["data"]["status"] == "inactive"
        service = client.request("POST", f"organizations/{organization}/services", b'{"display_name":"ci"}')["data"]
        assert service["schema_version"] == "sourcepack.cloud.service_identity.v1"
        assert client.request("POST", f"organizations/{organization}/repositories/{repository['id']}/reactivate", b'{}')["data"]["status"] == "active"
        assignment = client.request("POST", f"organizations/{organization}/services/{service['id']}/assignments", json.dumps({"repository_id":repository["id"]}).encode())["data"]
        assert client.request("DELETE", f"organizations/{organization}/assignments/{assignment['id']}")["data"]["removed"]
    finally: server.shutdown(); server.server_close()


def test_repo_commands_require_organization_configuration(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    CloudConfig("https://cloud.example").save()
    from sourcepack.cloud import save_credentials
    save_credentials("token", None)
    assert run_cli(["cloud", "repo-list"]) == 2
    assert "cloud_configuration_missing" in capsys.readouterr().err


def test_policy_pull_hashes_exact_artifact_bytes_and_keeps_unverified(tmp_path: Path) -> None:
    policy_bytes = b'{\n "rules" : { "max_changed_lines" : 2 }, "policy_id" : "engineering", "schema_version" : "sourcepack.org_policy.v1"\n}'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None: pass
        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(policy_bytes))); self.send_header("X-SourcePack-Policy-Revision-Id", "rev_1")
            self.end_headers(); self.wfile.write(policy_bytes)
    server, url = _serve(Handler)
    try:
        cache = tmp_path / "cache"
        metadata = pull_policy(CloudConfig(url, organization_id="org_1"), "token", cache)
        assert (cache / "downloaded-unverified-policy.json").read_bytes() == policy_bytes
        assert metadata["source_sha256"] == hashlib.sha256(policy_bytes).hexdigest()
        assert metadata["verification_status"] == "unverified"
        assert metadata["verified_policy_location"] is None
        assert not (cache / "verified-org-policy.json").exists()
        compact = b'{"schema_version":"sourcepack.org_policy.v1","policy_id":"engineering","rules":{"max_changed_lines":2}}'
        assert hashlib.sha256(compact).hexdigest() != metadata["source_sha256"]
        assert canonical_json_bytes(json.loads(compact)) == canonical_json_bytes(json.loads(policy_bytes))
    finally:
        server.shutdown(); server.server_close()
