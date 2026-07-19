from __future__ import annotations

import base64
import json
import os
import sqlite3
import hashlib
import http.client
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sourcepack.cli import run_cli
from sourcepack.cloud import CloudClient, CloudConfig, canonical_json_bytes, pull_policy
from sourcepack.hosted import Store, hash_password, hash_value, initialize_database, make_handler, verify_password


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _membership_request(url: str, token: str, method: str, route: str, body: bytes | None = None, content_type: str | None = "application/json") -> tuple[int, dict]:
    headers = {"Authorization": "Bearer " + token}
    if content_type is not None:
        headers["Content-Type"] = content_type
    if method == "POST" and route.endswith(("/members", "/repositories", "/services", "/assignments")):
        headers["Idempotency-Key"] = "test-idempotency-" + uuid.uuid4().hex
    request = Request(url + "/api/v1/" + route, data=body, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _audit_count(store: Store, organization: str) -> int:
    with store.db() as db:
        return int(db.execute("SELECT COUNT(*) FROM audit_events WHERE organization_id=? AND resource_type='membership'", (organization,)).fetchone()[0])


def test_cloud_status_is_unconfigured_without_touching_repository(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert run_cli(["cloud", "status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unconfigured"
    assert not (tmp_path / ".sourcepack").exists()


def test_cloud_config_and_canonical_json_are_deterministic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    config = CloudConfig("https://cloud.example", uploads_enabled=True, upload_categories=("report",))
    path = config.save()
    if os.name == "nt":
        assert path.is_file()
    else:
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
        created = client.request("POST", f"organizations/{organization}/repositories", b'{"display_name":"Repository"}', idempotency_key="client-idempotency-key-0001")
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
        membership = client.request("POST", f"organizations/{organization}/members", json.dumps({"user_id":member,"role":"reviewer"}).encode(), idempotency_key="governance-members-key-0001")["data"]
        assert client.request("PATCH", f"organizations/{organization}/members/{membership['id']}", b'{"role":"maintainer"}')["data"]["changed"]
        repository = client.request("POST", f"organizations/{organization}/repositories", b'{"display_name":"repo"}', idempotency_key="governance-repository-key-1")["data"]
        assert client.request("GET", f"organizations/{organization}/repositories/{repository['id']}")["data"]["id"] == repository["id"]
        assert client.request("POST", f"organizations/{organization}/repositories/{repository['id']}/deactivate", b'{}')["data"]["status"] == "inactive"
        service = client.request("POST", f"organizations/{organization}/services", b'{"display_name":"ci"}', idempotency_key="governance-service-key-0001")["data"]
        assert service["schema_version"] == "sourcepack.cloud.service_identity.v1"
        assert client.request("POST", f"organizations/{organization}/repositories/{repository['id']}/reactivate", b'{}')["data"]["status"] == "active"
        assignment = client.request("POST", f"organizations/{organization}/services/{service['id']}/assignments", json.dumps({"repository_id":repository["id"]}).encode(), idempotency_key="governance-assignment-key-1")["data"]
        assert client.request("DELETE", f"organizations/{organization}/assignments/{assignment['id']}")["data"]["removed"]
    finally: server.shutdown(); server.server_close()


def test_membership_http_lifecycle_authority_validation_and_auditing(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    member, _ = store.bootstrap("member@example.test", "password", "Two")
    reviewer, _ = store.bootstrap("reviewer@example.test", "password", "Three")
    maintainer, _ = store.bootstrap("maintainer@example.test", "password", "Four")
    promoted_user, _ = store.bootstrap("promoted@example.test", "password", "Five")
    outsider, other_org = store.bootstrap("outsider@example.test", "password", "Other")
    owner_token = store.login("owner@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database))
    route = f"organizations/{organization}/members"
    try:
        # Owners can add every supported role, promote, change roles, and remove.
        status, added_member = _membership_request(url, owner_token, "POST", route, b'{"user_id":"' + member.encode() + b'","role":"member"}')
        assert status == 201 and added_member["data"]["role"] == "member"
        status, added_reviewer = _membership_request(url, owner_token, "POST", route, json.dumps({"user_id": reviewer, "role": "reviewer"}).encode())
        assert status == 201 and added_reviewer["data"]["role"] == "reviewer"
        status, added_maintainer = _membership_request(url, owner_token, "POST", route, json.dumps({"user_id": maintainer, "role": "maintainer"}).encode())
        assert status == 201 and added_maintainer["data"]["role"] == "maintainer"
        status, promoted_membership = _membership_request(url, owner_token, "POST", route, json.dumps({"user_id": promoted_user, "role": "member"}).encode())
        assert status == 201
        status, promoted = _membership_request(url, owner_token, "PATCH", route + "/" + promoted_membership["data"]["id"], b'{"role":"owner"}')
        assert status == 200 and promoted["data"]["changed"]
        status, changed = _membership_request(url, owner_token, "PATCH", route + "/" + added_reviewer["data"]["id"], b'{"role":"maintainer"}')
        assert status == 200 and changed["data"]["changed"]
        status, removed = _membership_request(url, owner_token, "DELETE", route + "/" + added_member["data"]["id"])
        assert status == 200 and removed["data"]["removed"]
        # Rejoining reactivates the historical record rather than inserting another one.
        status, reactivated = _membership_request(url, owner_token, "POST", route, json.dumps({"user_id": member, "role": "reviewer"}).encode())
        assert status == 201 and reactivated["data"]["id"] == added_member["data"]["id"] and reactivated["data"]["status"] == "active"
        status, demoted = _membership_request(url, owner_token, "PATCH", route + "/" + promoted_membership["data"]["id"], b'{"role":"member"}')
        assert status == 200 and demoted["data"]["changed"]
        status, duplicate = _membership_request(url, owner_token, "POST", route, json.dumps({"user_id": member, "role": "member"}).encode())
        assert status == 409 and duplicate["error"]["code"] == "duplicate_membership"
        # Cross-organization IDs and all non-owner mutation attempts are generic not_found.
        maintainer_token = store.login("maintainer@example.test", "password")["access_token"]
        reviewer_token = store.login("reviewer@example.test", "password")["access_token"]
        member_token = store.login("member@example.test", "password")["access_token"]
        owner_membership = next(item["id"] for item in store.members(owner, organization) if item["user_id"] == owner)
        for token, method, target, body in (
            (maintainer_token, "POST", route, json.dumps({"user_id": outsider, "role": "owner"}).encode()),
            (maintainer_token, "PATCH", route + "/" + added_maintainer["data"]["id"], b'{"role":"owner"}'),
            (maintainer_token, "PATCH", route + "/" + owner_membership, b'{"role":"member"}'),
            (maintainer_token, "DELETE", route + "/" + owner_membership, None),
            (reviewer_token, "PATCH", route + "/" + added_maintainer["data"]["id"], b'{"role":"member"}'),
            (member_token, "DELETE", route + "/" + added_maintainer["data"]["id"], None),
        ):
            status, response = _membership_request(url, token, method, target, body)
            assert status == 404 and response["error"]["code"] == "not_found"
        status, response = _membership_request(url, owner_token, "PATCH", f"organizations/{other_org}/members/{added_maintainer['data']['id']}", b'{"role":"member"}')
        assert status == 404 and response["error"]["code"] == "not_found"
        # Membership payload validation is stable and all responses have the versioned envelope/request id.
        for method, body, content_type, expected in (
            ("POST", b'{"user_id":"' + outsider.encode() + b'","role":"member","extra":true}', "application/json", "invalid_request"),
            ("POST", b'{"user_id":"' + outsider.encode() + b'","user_id":"' + outsider.encode() + b'","role":"member"}', "application/json", "malformed_json"),
            ("POST", b"{", "application/json", "malformed_json"),
            ("POST", b'{}', "text/plain", "unsupported_content_type"),
        ):
            status, response = _membership_request(url, owner_token, method, route, body, content_type)
            assert status in {400, 415} and response["error"]["code"] == expected and response["schema_version"] == "sourcepack.cloud.api_response.v1" and response["request_id"]
        listing_status, listing = _membership_request(url, owner_token, "GET", route, None, None)
        assert listing_status == 200
        items = listing["data"]["items"]
        assert [item["id"] for item in items] == sorted([item["id"] for item in items], key=lambda item_id: next(item["created_at"] for item in items if item["id"] == item_id))
        assert all(item["organization_id"] == organization and item["schema_version"] == "sourcepack.cloud.membership.v1" and item["role_changed_at"] for item in items)
        service, service_token = store.create_service(owner, organization, "ci")
        for method, target, body in (("GET", route, None), ("POST", route, json.dumps({"user_id": outsider, "role": "member"}).encode())):
            status, response = _membership_request(url, service_token, method, target, body)
            assert status == 404 and response["error"]["code"] == "not_found"
        assert service["id"]
        assert _audit_count(store, organization) == 9
    finally: server.shutdown(); server.server_close()


def test_membership_http_final_owner_transactions_are_atomic_and_serialized(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    second, _ = store.bootstrap("second@example.test", "password", "Two")
    token = store.login("owner@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database)); route = f"organizations/{organization}/members"
    try:
        status, second_membership = _membership_request(url, token, "POST", route, json.dumps({"user_id": second, "role": "owner"}).encode())
        assert status == 201
        owner_membership = next(item["id"] for item in store.members(owner, organization) if item["user_id"] == owner)
        # Either request may win, but BEGIN IMMEDIATE means the loser observes the committed final-owner state.
        barrier = threading.Barrier(2); results: list[tuple[int, dict]] = []
        def remove(membership_id: str) -> None:
            barrier.wait(); results.append(_membership_request(url, token, "DELETE", route + "/" + membership_id))
        first = threading.Thread(target=remove, args=(owner_membership,)); second_thread = threading.Thread(target=remove, args=(second_membership["data"]["id"],))
        first.start(); second_thread.start(); first.join(); second_thread.join()
        assert 200 in [status for status, _ in results] and any(status in {404, 409} for status, _ in results)
        assert _audit_count(store, organization) == 2
        with store.db() as db:
            remaining = db.execute("SELECT id,user_id FROM memberships WHERE organization_id=? AND status='active' AND role='owner'", (organization,)).fetchall()
        assert len(remaining) == 1
        remaining_token = token if remaining[0]["user_id"] == owner else store.login("second@example.test", "password")["access_token"]
        status, response = _membership_request(url, remaining_token, "DELETE", route + "/" + remaining[0]["id"])
        assert status == 409 and response["error"]["code"] == "final_owner" and _audit_count(store, organization) == 2
        status, response = _membership_request(url, remaining_token, "PATCH", route + "/" + remaining[0]["id"], b'{"role":"member"}')
        assert status == 409 and response["error"]["code"] == "final_owner" and _audit_count(store, organization) == 2
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


def _create_request(url: str, token: str, route: str, body: bytes, key: str | None) -> tuple[int, dict]:
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    request = Request(url + "/api/v1/" + route, data=body, headers=headers, method="POST")
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_hosted_create_idempotency_http_contract(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    other_owner, other_organization = store.bootstrap("other@example.test", "password", "Two")
    member, _ = store.bootstrap("member@example.test", "password", "Three")
    token = store.login("owner@example.test", "password")["access_token"]
    other_token = store.login("other@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database)); route = f"organizations/{organization}/repositories"; body = b'{"display_name":"once"}'; key = "valid-idempotency-key-0001"
    try:
        for invalid in (None, "short", "x" * 129, "valid idempotency key", "valid-idempotency-key-\u00e9", "valid-idempotency-key-\x01"):
            status, response = _create_request(url, token, route, body, invalid)
            assert status == 400 and response["error"]["code"] == "invalid_idempotency_key"
        status, first = _create_request(url, token, route, body, key)
        status2, replay = _create_request(url, token, route, body, key)
        assert status == status2 == 201 and first == replay
        with store.db() as db:
            assert db.execute("SELECT COUNT(*) FROM repositories WHERE organization_id=?", (organization,)).fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM idempotency WHERE organization_id=?", (organization,)).fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM audit_events WHERE organization_id=? AND action='repository_registered'", (organization,)).fetchone()[0] == 1
        status, conflict = _create_request(url, token, route, b'{"display_name":"other"}', key)
        assert status == 409 and conflict["error"]["code"] == "idempotency_conflict"
        status, independent = _create_request(url, other_token, f"organizations/{other_organization}/repositories", body, key)
        assert status == 201 and independent["data"]["organization_id"] == other_organization
        # Invalid payload and unauthorized attempts do not consume a valid key.
        bad_key = "valid-idempotency-key-0002"
        assert _create_request(url, token, route, b'{"unexpected":true}', bad_key)[0] == 400
        assert _create_request(url, token, route, b'{"display_name":"corrected"}', bad_key)[0] == 201
        assert _create_request(url, other_token, route, b'{"display_name":"denied"}', "valid-idempotency-key-0003")[0] == 404
        with store.db() as db:
            assert db.execute("SELECT COUNT(*) FROM idempotency WHERE organization_id=? AND key=?", (organization, "valid-idempotency-key-0003")).fetchone()[0] == 0
        # Each other covered route uses the same atomic path.
        membership = _create_request(url, token, f"organizations/{organization}/members", json.dumps({"user_id": member, "role": "reviewer"}).encode(), "valid-idempotency-key-0004")
        service = _create_request(url, token, f"organizations/{organization}/services", b'{"display_name":"ci"}', "valid-idempotency-key-0005")
        assignment = _create_request(url, token, f"organizations/{organization}/services/{service[1]['data']['id']}/assignments", json.dumps({"repository_id": first["data"]["id"]}).encode(), "valid-idempotency-key-0006")
        assert membership[0] == service[0] == assignment[0] == 201
    finally:
        server.shutdown(); server.server_close()


def test_hosted_idempotency_concurrent_requests_are_serialized(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    token = store.login("owner@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database)); route = f"organizations/{organization}/repositories"; key = "valid-idempotency-key-serial"
    try:
        barrier = threading.Barrier(2); results: list[tuple[int, dict]] = []
        def create(body: bytes) -> None:
            barrier.wait(); results.append(_create_request(url, token, route, body, key))
        threads = [threading.Thread(target=create, args=(b'{"display_name":"once"}',)) for _ in range(2)]
        [thread.start() for thread in threads]; [thread.join() for thread in threads]
        assert [result[0] for result in results] == [201, 201]
        assert results[0][1]["data"]["id"] == results[1][1]["data"]["id"]
        with store.db() as db:
            assert db.execute("SELECT COUNT(*) FROM repositories WHERE organization_id=?", (organization,)).fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM audit_events WHERE organization_id=? AND action='repository_registered'", (organization,)).fetchone()[0] == 1
        results.clear(); barrier = threading.Barrier(2); key = "valid-idempotency-key-differ"
        threads = [threading.Thread(target=create, args=(body,)) for body in (b'{"display_name":"one"}', b'{"display_name":"two"}')]
        [thread.start() for thread in threads]; [thread.join() for thread in threads]
        assert sorted(result[0] for result in results) == [201, 409]
    finally:
        server.shutdown(); server.server_close()


def test_hosted_idempotency_migration_preserves_v3_records(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; initialize_database(database)
    with sqlite3.connect(database) as db:
        db.executescript("""
ALTER TABLE idempotency RENAME TO idempotency_v4_test;
CREATE TABLE idempotency (organization_id TEXT NOT NULL, actor_id TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL, key TEXT NOT NULL, body_sha256 TEXT NOT NULL, response_json TEXT NOT NULL, PRIMARY KEY (organization_id, actor_id, method, route, key));
INSERT INTO idempotency VALUES ('org','usr','POST','/api/v1/organizations/org/repositories','legacy-idempotency-key-0001','hash','{\"ok\":true}');
DROP TABLE idempotency_v4_test;
DELETE FROM cloud_migrations WHERE version=4;
""")
    initialize_database(database)
    with sqlite3.connect(database) as db:
        record = db.execute("SELECT actor_kind,response_status,response_json FROM idempotency").fetchone()
        assert record == ("user", 201, '{"ok":true}')
        assert db.execute("SELECT version FROM cloud_migrations WHERE version=4").fetchone() == (4,)


def test_service_token_creation_discloses_secret_once_without_persistence(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    token = store.login("owner@example.test", "password")["access_token"]
    server, url = _serve(make_handler(database)); key = "service-token-idempotency-0001"
    try:
        status, service = _create_request(url, token, f"organizations/{organization}/services", b'{"display_name":"ci"}', "service-identity-idempotency-1")
        assert status == 201 and "token" not in service["data"]
        route = f"organizations/{organization}/services/{service['data']['id']}/tokens"; body = b'{"expires_hours":24}'
        status, first = _create_request(url, token, route, body, key)
        status2, replay = _create_request(url, token, route, body, key)
        assert status == status2 == 201 and first["data"]["token"] and first["data"]["raw_token_disclosed"]
        assert replay["data"]["id"] == first["data"]["id"] and replay["data"]["raw_token_unavailable"] and "token" not in replay["data"]
        with store.db() as db:
            serialized = " ".join(str(value) for row in db.execute("SELECT token_hash FROM service_tokens") for value in row) + " ".join(str(value) for row in db.execute("SELECT response_json FROM idempotency") for value in row) + " ".join(str(value) for row in db.execute("SELECT detail_json FROM audit_events") for value in row)
            assert first["data"]["token"] not in serialized
            assert db.execute("SELECT COUNT(*) FROM service_tokens").fetchone()[0] == 1
    finally:
        server.shutdown(); server.server_close()


def _delete_with_headers(url: str, token: str, route: str, headers: dict[str, str], body: bytes | None = None) -> tuple[int, dict]:
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port)
    connection.putrequest("DELETE", "/api/v1/" + route)
    connection.putheader("Authorization", "Bearer " + token)
    for name, value in headers.items():
        connection.putheader(name, value)
    connection.endheaders(body)
    response = connection.getresponse(); payload = json.loads(response.read()); connection.close()
    return response.status, payload


def test_membership_delete_body_length_validation(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    member, _ = store.bootstrap("member@example.test", "password", "Two")
    token = store.login("owner@example.test", "password")["access_token"]
    membership = store.add_membership(owner, organization, member, "member")
    server, url = _serve(make_handler(database)); route = f"organizations/{organization}/members/{membership['id']}"
    try:
        for headers, body, expected in (
            ({}, None, 200),
        ):
            status, response = _delete_with_headers(url, token, route, headers, body)
            assert status == expected and response["data"]["removed"]
        # Re-add a target for each parser case so parse rejection cannot mutate it.
        for headers, body, expected in (
            ({"Content-Length": "0"}, None, "ok"),
            ({"Content-Type": "application/json", "Content-Length": "2"}, b"{}", "ok"),
            ({"Content-Length": "-1"}, None, "malformed_json"),
            ({"Content-Length": "nope"}, None, "malformed_json"),
            ({"Content-Length": "1000001"}, None, "payload_too_large"),
            ({"Content-Type": "application/json", "Content-Length": "1"}, b"{", "malformed_json"),
            ({"Content-Type": "application/json", "Content-Length": "13"}, b'{"a":1,"a":2}', "malformed_json"),
            ({"Content-Type": "text/plain", "Content-Length": "0"}, None, "unsupported_content_type"),
        ):
            current = store.add_membership(owner, organization, member, "member")
            status, response = _delete_with_headers(url, token, f"organizations/{organization}/members/{current['id']}", headers, body)
            if expected == "ok":
                assert status == 200 and response["data"]["removed"]
            else:
                assert response["error"]["code"] == expected
                assert store.members(owner, organization)[-1]["id"] == current["id"]
                store.remove_member(owner, organization, current["id"])
        owner_membership = next(item["id"] for item in store.members(owner, organization) if item["user_id"] == owner)
        status, response = _delete_with_headers(url, token, f"organizations/{organization}/members/{owner_membership}", {"Content-Length": "0"})
        assert status == 409 and response["error"]["code"] == "final_owner"
    finally:
        server.shutdown(); server.server_close()


def test_audit_events_http_contract_authorization_filters_and_pagination(tmp_path: Path) -> None:
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("audit-owner@example.test", "audit-password", "One")
    maintainer, _ = store.bootstrap("audit-maintainer@example.test", "password", "Two")
    reviewer, _ = store.bootstrap("audit-reviewer@example.test", "password", "Three")
    member, _ = store.bootstrap("audit-member@example.test", "password", "Four")
    removed, _ = store.bootstrap("audit-removed@example.test", "password", "Five")
    outsider, other_organization = store.bootstrap("audit-outsider@example.test", "password", "Six")
    for user, role in ((maintainer, "maintainer"), (reviewer, "reviewer"), (member, "member"), (removed, "reviewer")):
        store.add_membership(owner, organization, user, role)
    removed_membership = next(record["id"] for record in store.members(owner, organization) if record["user_id"] == removed)
    store.remove_member(owner, organization, removed_membership)
    repository = store.create_repository(owner, organization, "history")
    store.set_repository_status(owner, organization, repository["id"], "inactive")
    store.set_repository_status(owner, organization, repository["id"], "active")
    service, service_token = store.create_service(owner, organization, "audit-service")
    with store.db() as db:
        db.executemany("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", (
            ("aud_a", "sourcepack.cloud.audit_event.v1", organization, owner, "manual", "test", "resource-a", "2099-01-01T00:00:00+00:00", "success", "{\"safe\":true}"),
            ("aud_z", "sourcepack.cloud.audit_event.v1", organization, maintainer, "manual", "test", "resource-z", "2099-01-01T00:00:00+00:00", "failure", "{}"),
        ))
    issued = {identity: store.login(identity, "audit-password" if identity == "audit-owner@example.test" else "password") for identity in (
        "audit-owner@example.test", "audit-maintainer@example.test", "audit-reviewer@example.test",
        "audit-member@example.test", "audit-removed@example.test", "audit-outsider@example.test",
    )}
    tokens = {identity: value["access_token"] for identity, value in issued.items()}
    server, url = _serve(make_handler(database)); route = f"organizations/{organization}/audit-events"
    try:
        status, owner_page = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?limit=2", None, None)
        assert status == 200
        assert owner_page["schema_version"] == "sourcepack.cloud.api_response.v1" and owner_page["request_id"]
        assert len(owner_page["data"]["items"]) == 2
        first_items = owner_page["data"]["items"]
        assert all("detail_json" not in item and isinstance(item["detail"], dict) for item in first_items)
        assert [(item["timestamp"], item["id"]) for item in first_items] == sorted(
            [(item["timestamp"], item["id"]) for item in first_items], reverse=True)
        assert [item["id"] for item in first_items] == ["aud_z", "aud_a"]
        status, second_page = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?limit=2&cursor=" + owner_page["data"]["next_cursor"], None, None)
        assert status == 200 and not {item["id"] for item in first_items} & {item["id"] for item in second_page["data"]["items"]}
        all_ids = [item["id"] for item in first_items]; cursor = owner_page["data"]["next_cursor"]
        while cursor:
            status, page = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?limit=2&cursor=" + cursor, None, None)
            assert status == 200
            all_ids.extend(item["id"] for item in page["data"]["items"]); cursor = page["data"]["next_cursor"]
        with store.db() as db:
            expected_count = db.execute("SELECT COUNT(*) FROM audit_events WHERE organization_id=?", (organization,)).fetchone()[0]
        assert len(all_ids) == expected_count == len(set(all_ids))
        for identity in ("audit-maintainer@example.test", "audit-reviewer@example.test"):
            assert _membership_request(url, tokens[identity], "GET", route, None, None)[0] == 200
        for identity in ("audit-member@example.test", "audit-removed@example.test"):
            status, response = _membership_request(url, tokens[identity], "GET", route, None, None)
            assert status == 404 and response["error"]["code"] == "not_found"
        status, response = _membership_request(url, service_token, "GET", route, None, None)
        assert status == 404 and response["error"]["code"] == "not_found"
        status, response = _membership_request(url, tokens["audit-outsider@example.test"], "GET", route, None, None)
        assert status == 404 and response["error"]["code"] == "not_found"
        for query, expected in (("?limit=0", "invalid_request"), ("?limit=101", "invalid_request"), ("?limit=x", "invalid_request"), ("?cursor=broken", "invalid_cursor"), ("?unknown=value", "invalid_request"), ("?timestamp_from=nope", "invalid_request"), ("?timestamp_to=nope", "invalid_request"), ("?timestamp_from=2099-01-02T00%3A00%3A00%2B00%3A00&timestamp_to=2099-01-01T00%3A00%3A00%2B00%3A00", "invalid_request"), ("?timestamp_from=2099-01-01T00%3A00%3A00", "invalid_request"), ("?action=manual&action=repository_active", "invalid_request")):
            status, response = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + query, None, None)
            assert status == 400 and response["error"]["code"] == expected
        assert _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?limit=100", None, None)[0] == 200
        forged = base64.urlsafe_b64encode(json.dumps([organization, "2099-01-01T01:00:00+01:00", "aud_z", "0" * 64]).encode()).decode().rstrip("=")
        status, response = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?cursor=" + forged, None, None)
        assert status == 400 and response["error"]["code"] == "invalid_cursor"
        status, filtered = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?resource_id=" + repository["id"] + "&action=repository_inactive", None, None)
        assert status == 200 and [item["action"] for item in filtered["data"]["items"]] == ["repository_inactive"]
        status, literal = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?action=%27%20OR%201%3D1--", None, None)
        assert status == 200 and literal["data"] == {"schema_version": "sourcepack.cloud.audit_event_collection.v1", "items": [], "next_cursor": None}
        for query, expected_id in (("?actor_id=" + maintainer, "aud_z"), ("?action=manual", "aud_z"), ("?resource_type=test", "aud_z"), ("?resource_id=resource-a", "aud_a"), ("?result=failure", "aud_z"), ("?timestamp_from=2099-01-01T00%3A00%3A00%2B00%3A00", "aud_z"), ("?timestamp_to=2099-01-01T00%3A00%3A00%2B00%3A00", "aud_z"), ("?action=manual&resource_id=resource-a&result=success", "aud_a")):
            status, filtered = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + query, None, None)
            assert status == 200 and filtered["data"]["items"][0]["id"] == expected_id
        status, normalized = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?timestamp_from=2099-01-01T01%3A00%3A00%2B01%3A00&timestamp_to=2099-01-01T01%3A00%3A00%2B01%3A00", None, None)
        assert status == 200 and [item["id"] for item in normalized["data"]["items"]] == ["aud_z", "aud_a"]
        status, filtered_page = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?action=manual&limit=1", None, None)
        assert status == 200 and filtered_page["data"]["next_cursor"]
        status, filtered_next = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?action=manual&limit=1&cursor=" + filtered_page["data"]["next_cursor"], None, None)
        assert status == 200 and filtered_next["data"]["items"][0]["id"] == "aud_a"
        status, response = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?action=repository_active&cursor=" + filtered_page["data"]["next_cursor"], None, None)
        assert status == 400 and response["error"]["code"] == "invalid_cursor"
        status, cross_cursor = _membership_request(url, tokens["audit-owner@example.test"], "GET", f"organizations/{other_organization}/audit-events?cursor=" + owner_page["data"]["next_cursor"], None, None)
        assert status == 404 and cross_cursor["error"]["code"] == "not_found"
        status, history = _membership_request(url, tokens["audit-owner@example.test"], "GET", route + "?resource_id=" + repository["id"], None, None)
        assert status == 200 and {item["action"] for item in history["data"]["items"]} >= {"repository_registered", "repository_inactive", "repository_active"}
        status, response = _membership_request(url, tokens["audit-owner@example.test"], "PATCH", route + "/aud_a", b'{"detail":{}}')
        assert status == 400 and response["error"]["code"] == "invalid_request"
        status, response = _membership_request(url, tokens["audit-owner@example.test"], "DELETE", route + "/aud_a", None, None)
        assert status == 404 and response["error"]["code"] == "not_found"
        status, error = _membership_request(url, tokens["audit-member@example.test"], "GET", route, None, None)
        assert status == 404
        owner_issued = issued["audit-owner@example.test"]
        secrets_to_exclude = [
            "audit-password", owner_issued["access_token"], owner_issued["refresh_token"], service_token,
            hash_value(owner_issued["access_token"]), hash_value(owner_issued["refresh_token"]), hash_value(service_token),
            "Bearer " + owner_issued["access_token"],
            *(value["access_token"] for value in issued.values()), *(value["refresh_token"] for value in issued.values()),
            *(hash_value(value["access_token"]) for value in issued.values()), *(hash_value(value["refresh_token"]) for value in issued.values()),
        ]
        with store.db() as db:
            audit_storage = " ".join(str(value) for row in db.execute("SELECT actor_id,action,resource_type,resource_id,detail_json FROM audit_events") for value in row)
        assert all(value not in audit_storage for value in secrets_to_exclude)
        assert all(value not in json.dumps(error) for value in secrets_to_exclude)
        assert service["id"]
    finally:
        server.shutdown(); server.server_close()


def test_hosted_audit_mutations_share_transaction_boundaries(tmp_path: Path) -> None:
    """An audit insertion failure rolls back each covered state mutation."""
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("transaction-owner@example.test", "password", "One")
    repository = store.create_repository(owner, organization, "repo")
    service, _ = store.create_service(owner, organization, "ci")
    assignment = store.assign_service(owner, organization, service["id"], repository["id"])
    credential = store.login("transaction-owner@example.test", "password")

    def reject(action: str) -> None:
        with store.db() as db:
            db.execute("CREATE TRIGGER reject_audit BEFORE INSERT ON audit_events WHEN NEW.action=" + repr(action) + " BEGIN SELECT RAISE(ABORT, 'audit rejected'); END")

    reject("repository_inactive")
    try:
        store.set_repository_status(owner, organization, repository["id"], "inactive")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("audit failure must reject repository deactivation")
    with store.db() as db:
        assert db.execute("SELECT status FROM repositories WHERE id=?", (repository["id"],)).fetchone()[0] == "active"
        db.execute("DROP TRIGGER reject_audit")

    reject("service_revoked")
    try:
        store.revoke_service(owner, organization, service["id"])
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("audit failure must reject service revocation")
    with store.db() as db:
        assert db.execute("SELECT status FROM service_identities WHERE id=?", (service["id"],)).fetchone()[0] == "active"
        db.execute("DROP TRIGGER reject_audit")

    reject("service_assignment_removed")
    try:
        store.remove_assignment(owner, organization, assignment["id"])
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("audit failure must reject assignment removal")
    with store.db() as db:
        assert db.execute("SELECT status FROM repository_assignments WHERE id=?", (assignment["id"],)).fetchone()[0] == "active"
        db.execute("DROP TRIGGER reject_audit")

    reject("credential_revoked")
    try:
        store.revoke("Bearer " + credential["access_token"])
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("audit failure must reject credential revocation")
    assert store.actor("Bearer " + credential["access_token"])
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE action='credential_revoked'").fetchone()[0] == 0
        db.execute("DROP TRIGGER reject_audit")
    assert store.revoke("Bearer " + credential["access_token"])
    with store.db() as db:
        event = db.execute("SELECT organization_id,actor_id,resource_type,resource_id FROM audit_events WHERE action='credential_revoked'").fetchone()
    assert tuple(event) == (organization, owner, "credential", event[3])


def _auth_current_request(url: str, token: str) -> tuple[int, dict]:
    request = Request(url + "/api/v1/auth/current", headers={"Authorization": "Bearer " + token}, method="DELETE")
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _refresh_request(url: str, refresh_token: str) -> tuple[int, dict]:
    request = Request(url + "/api/v1/auth/refresh", data=json.dumps({"refresh_token": refresh_token}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _credential_revoke_audits(store: Store) -> list[sqlite3.Row]:
    with store.db() as db:
        return db.execute("SELECT action,resource_type,resource_id,detail_json FROM audit_events WHERE action='credential_revoked' ORDER BY organization_id").fetchall()


def test_cli_logout_revokes_hosted_credential_and_deletes_local_credentials(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    owner, organization = store.bootstrap("owner@example.test", "password", "One")
    other = "org_" + uuid.uuid4().hex
    with store.db() as db:
        stamp = "2026-01-01T00:00:00+00:00"
        db.execute("INSERT INTO organizations VALUES (?,?,?,?,?)", (other, "sourcepack.cloud.organization.v1", "Two", stamp, "active"))
        db.execute("INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?)", ("mem_" + uuid.uuid4().hex, "sourcepack.cloud.membership.v1", other, owner, "owner", "active", stamp, stamp))
    tokens = store.login("owner@example.test", "password")
    server, url = _serve(make_handler(database))
    try:
        from sourcepack.cloud import credential_path, save_credentials
        CloudConfig(url, organization_id=organization).save(); save_credentials(tokens["access_token"], tokens["refresh_token"])
        assert run_cli(["cloud", "logout", "--json"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"status": "server_revocation_success"}
        assert captured.err == ""
        assert not credential_path().exists()
        assert store.actor("Bearer " + tokens["access_token"]) is None
        status, response = _refresh_request(url, tokens["refresh_token"])
        assert status == 401 and response["error"]["code"] == "authentication_rejected"
        audits = _credential_revoke_audits(store)
        assert len(audits) == 2
        assert {audit["resource_type"] for audit in audits} == {"credential"}
        forbidden = [tokens["access_token"], tokens["refresh_token"], hash_value(tokens["access_token"]), hash_value(tokens["refresh_token"]), "Authorization", "Bearer"]
        output = captured.out + captured.err + json.dumps(response) + "\n".join(audit["detail_json"] for audit in audits)
        assert not any(secret in output for secret in forbidden)
        assert run_cli(["cloud", "logout", "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == {"status": "local_logout_success"}
        assert len(_credential_revoke_audits(store)) == 2
    finally:
        server.shutdown(); server.server_close()


def test_cli_logout_with_credentials_and_missing_config_is_unconfirmed(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from sourcepack.cloud import credential_path, save_credentials
    access = "missing-config-access-token"; refresh = "missing-config-refresh-token"
    save_credentials(access, refresh)
    assert run_cli(["cloud", "logout", "--json"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "local_logout_remote_revocation_unconfirmed"}
    assert captured.err == ""
    assert not credential_path().exists()
    combined = captured.out + captured.err
    forbidden = [access, refresh, hash_value(access), hash_value(refresh), "Authorization", "Bearer"]
    assert not any(secret in combined for secret in forbidden)
    assert run_cli(["cloud", "logout", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "local_logout_success"}
    assert captured.err == ""


def test_cli_logout_already_revoked_or_invalid_credentials_cleanup_exit_zero(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    database = tmp_path / "cloud.sqlite"; store = Store(database)
    _, organization = store.bootstrap("owner@example.test", "password", "One")
    tokens = store.login("owner@example.test", "password")
    server, url = _serve(make_handler(database))
    try:
        from sourcepack.cloud import credential_path, save_credentials
        CloudConfig(url, organization_id=organization).save()
        assert store.revoke("Bearer " + tokens["access_token"])
        save_credentials(tokens["access_token"], tokens["refresh_token"])
        assert run_cli(["cloud", "logout", "--json"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"status": "local_logout_success"}
        assert captured.err == "" and not credential_path().exists()
        save_credentials("invalid-access-token", "invalid-refresh-token")
        assert run_cli(["cloud", "logout", "--json"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"status": "local_logout_success"}
        assert captured.err == "" and not credential_path().exists()
        combined = captured.out + captured.err
        assert "invalid-access-token" not in combined and "invalid-refresh-token" not in combined and "Authorization" not in combined
        assert len(_credential_revoke_audits(store)) == 1
    finally:
        server.shutdown(); server.server_close()


def test_cli_logout_unavailable_server_deletes_local_credentials_and_warns(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from sourcepack.cloud import credential_path, save_credentials
    access = "offline-access-token"; refresh = "offline-refresh-token"
    CloudConfig("http://127.0.0.1:9", request_timeout=0.1).save(); save_credentials(access, refresh)
    assert run_cli(["cloud", "logout"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "remote revocation unconfirmed" in captured.err
    assert not credential_path().exists()
    assert access not in captured.err and refresh not in captured.err and "Authorization" not in captured.err and "Bearer" not in captured.err
