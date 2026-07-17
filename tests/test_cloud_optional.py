from __future__ import annotations

import json
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sourcepack.cli import run_cli
from sourcepack.cloud import CloudClient, CloudConfig, CloudError, canonical_json_bytes, pull_policy
from sourcepack.hosted import Store, hash_password, initialize_database, make_handler, verify_password


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _membership_request(url: str, token: str, method: str, route: str, body: bytes | None = None, content_type: str | None = "application/json") -> tuple[int, dict]:
    headers = {"Authorization": "Bearer " + token}
    if content_type is not None:
        headers["Content-Type"] = content_type
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
