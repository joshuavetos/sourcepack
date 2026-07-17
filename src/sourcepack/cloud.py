"""Explicit, opt-in client support for the SourcePack hosted control plane.

This module deliberately uses only the standard-library HTTP client.  Importing
it does not read configuration, contact a service, or alter repository state.
"""
from __future__ import annotations

import hashlib
import json
import os
import getpass
import stat
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import ORG_POLICY_SCHEMA_VERSION, _canonical_json
from .schema_contracts import DuplicateKeyError

CLOUD_CONFIG_SCHEMA = "sourcepack.cloud.config.v1"
POLICY_CACHE_SCHEMA = "sourcepack.cloud.policy_cache.v1"
API_ENVELOPE_SCHEMA = "sourcepack.cloud.api_response.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_no_duplicates(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise DuplicateKeyError(key)
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)


def canonical_json_bytes(value: Any) -> bytes:
    """The hosted canonical encoding: UTF-8, sorted keys, no whitespace."""
    return _canonical_json(value).encode("utf-8")


def default_config_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sourcepack" / "cloud.json"


@dataclass(frozen=True)
class CloudConfig:
    api_base_url: str
    organization_id: str | None = None
    repository_id: str | None = None
    credential_reference: str | None = None
    uploads_enabled: bool = False
    upload_categories: tuple[str, ...] = ()
    policy_sync_enabled: bool = False
    cached_policy_location: str | None = None
    request_timeout: float = 15.0

    @classmethod
    def load(cls, path: Path | None = None) -> "CloudConfig | None":
        path = path or default_config_path()
        if not path.is_file():
            return None
        raw = _json_no_duplicates(path.read_bytes())
        if not isinstance(raw, dict) or raw.get("schema_version") != CLOUD_CONFIG_SCHEMA:
            raise ValueError("cloud_configuration_invalid")
        allowed = {"schema_version", "api_base_url", "organization_id", "repository_id", "credential_reference", "uploads_enabled", "upload_categories", "policy_sync_enabled", "cached_policy_location", "request_timeout"}
        if set(raw) - allowed or not isinstance(raw.get("api_base_url"), str):
            raise ValueError("cloud_configuration_invalid")
        categories = raw.get("upload_categories", [])
        if not isinstance(categories, list) or not all(isinstance(v, str) for v in categories):
            raise ValueError("cloud_configuration_invalid")
        return cls(raw["api_base_url"].rstrip("/"), raw.get("organization_id"), raw.get("repository_id"), raw.get("credential_reference"), raw.get("uploads_enabled", False), tuple(categories), raw.get("policy_sync_enabled", False), raw.get("cached_policy_location"), float(raw.get("request_timeout", 15.0)))

    def save(self, path: Path | None = None) -> Path:
        path = path or default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("cloud_configuration_permissions_unsafe")
        data = {"schema_version": CLOUD_CONFIG_SCHEMA, **self.__dict__, "upload_categories": list(self.upload_categories)}
        path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        return path


class CloudError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code, self.status = code, status


class CloudClient:
    def __init__(self, config: CloudConfig, token: str | None = None):
        self.config, self.token = config, token

    def request(self, method: str, route: str, body: bytes | None = None, *, idempotency_key: str | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if body is not None: headers["Content-Type"] = "application/json"
        if self.token: headers["Authorization"] = "Bearer " + self.token
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(self.config.api_base_url + "/api/v1/" + route.lstrip("/"), data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.request_timeout) as response:
                payload = _json_no_duplicates(response.read())
        except urllib.error.HTTPError as exc:
            try: payload = _json_no_duplicates(exc.read())
            except Exception: payload = None
            code = payload.get("error", {}).get("code") if isinstance(payload, dict) else "cloud_server_error"
            raise CloudError(code or "cloud_server_error", exc.code) from None
        except TimeoutError as exc: raise CloudError("cloud_request_timeout") from exc
        except urllib.error.URLError as exc: raise CloudError("cloud_network_unavailable") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != API_ENVELOPE_SCHEMA:
            raise CloudError("cloud_invalid_response")
        if not payload.get("ok"):
            raise CloudError(str(payload.get("error", {}).get("code", "cloud_server_error")))
        return payload

    def request_bytes(self, route: str) -> tuple[bytes, dict[str, str]]:
        """Return policy artifact bytes before parsing them or interpreting metadata."""
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(self.config.api_base_url + "/api/v1/" + route.lstrip("/"), headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.config.request_timeout) as response:
                if response.headers.get_content_type() != "application/json":
                    raise CloudError("unsupported_content_type")
                return response.read(), {key.lower(): value for key, value in response.headers.items()}
        except CloudError:
            raise
        except urllib.error.HTTPError as exc:
            raise CloudError("cloud_server_error", exc.code) from None
        except TimeoutError as exc:
            raise CloudError("cloud_request_timeout") from exc
        except urllib.error.URLError as exc:
            raise CloudError("cloud_network_unavailable") from exc


def pull_policy(config: CloudConfig, token: str, cache_root: Path) -> dict[str, Any]:
    """Download policy bytes into the untrusted cache only.

    Full binding, declared-hash, and existing resolver trust validation is not
    performed here.  Therefore this function deliberately never creates or
    updates a verified cache file and cannot influence effective policy.
    """
    if not config.organization_id:
        raise CloudError("cloud_configuration_missing")
    client = CloudClient(config, token)
    source, headers = client.request_bytes("organizations/" + config.organization_id + "/policy/active/artifact")
    source_hash = hashlib.sha256(source).hexdigest()
    cache_root.mkdir(parents=True, exist_ok=True)
    unverified = cache_root / "downloaded-unverified-policy.json"
    unverified.write_bytes(source)
    try:
        policy = _json_no_duplicates(source)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError):
        raise CloudError("policy_artifact_malformed") from None
    if not isinstance(policy, dict) or policy.get("schema_version") != ORG_POLICY_SCHEMA_VERSION or not isinstance(policy.get("policy_id"), str):
        raise CloudError("policy_trust_failure")
    canonical = canonical_json_bytes(policy)
    metadata = {"schema_version": POLICY_CACHE_SCHEMA, "organization_id": config.organization_id, "hosted_repository_id": config.repository_id, "policy_revision_id": headers.get("x-sourcepack-policy-revision-id"), "revision_number": headers.get("x-sourcepack-policy-revision-number"), "download_timestamp": _now(), "verification_timestamp": None, "source_sha256": source_hash, "canonical_sha256": hashlib.sha256(canonical).hexdigest(), "remote_declared_hash": headers.get("x-sourcepack-policy-canonical-sha256"), "verification_status": "unverified", "stale": False, "verified_policy_location": None, "unverified_download_location": str(unverified), "last_retrieval_error_code": "policy_trust_verification_not_implemented"}
    (cache_root / "policy-cache.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return metadata


def new_idempotency_key() -> str:
    return str(uuid.uuid4())


def credential_path() -> Path:
    return default_config_path().with_name("credentials.json")


def load_access_token() -> str | None:
    path = credential_path()
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        return None
    try:
        data = _json_no_duplicates(path.read_bytes())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    token = data.get("access_token") if isinstance(data, dict) else None
    return token if isinstance(token, str) else None


def save_credentials(access_token: str, refresh_token: str | None) -> None:
    path = credential_path(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "sourcepack.cloud.credential.v1", "access_token": access_token, "refresh_token": refresh_token}, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def clear_credentials() -> None:
    credential_path().unlink(missing_ok=True)


def cli_cloud(args: Any) -> int:
    """Cloud command dispatcher; this is the only local CLI path that uses HTTP."""
    command = getattr(args, "cloud_command", None)
    if command == "status":
        config = CloudConfig.load()
        payload = {"schema_version": CLOUD_CONFIG_SCHEMA, "status": "configured" if config else "unconfigured", "authenticated": bool(load_access_token())}
        print(json.dumps(payload, sort_keys=True) if args.json else payload["status"])
        return 0
    if command == "logout":
        clear_credentials(); print(json.dumps({"status": "logged_out"}) if args.json else "Logged out."); return 0
    config = CloudConfig.load()
    if command == "login":
        api_url = config.api_base_url if config else input("API base URL: ").strip().rstrip("/")
        identity = input("Email or username: ").strip()
        password = getpass.getpass("Password: ")
        if not api_url or not identity or not password:
            print("ERROR: cloud authentication rejected", file=os.sys.stderr); return 2
        try:
            response = CloudClient(CloudConfig(api_url)).request("POST", "auth/login", json.dumps({"identity": identity, "password": password}).encode("utf-8"))
            data = response.get("data", {}); access, refresh = data.get("access_token"), data.get("refresh_token")
            if not isinstance(access, str): raise CloudError("cloud_authentication_rejected")
            CloudConfig(api_url, credential_reference=str(credential_path())).save(); save_credentials(access, refresh if isinstance(refresh, str) else None)
        except CloudError as exc:
            print(f"ERROR: {exc.code}", file=os.sys.stderr); return 2
        print(json.dumps({"status": "logged_in"}) if args.json else "Logged in."); return 0
    if config is None:
        print("ERROR: cloud_configuration_missing", file=os.sys.stderr); return 2
    token = load_access_token()
    if not token:
        print("ERROR: cloud_authentication_required", file=os.sys.stderr); return 2
    try:
        client = CloudClient(config, token)
        if command == "repo-list":
            if not config.organization_id: raise CloudError("cloud_configuration_missing")
            result = client.request("GET", f"organizations/{config.organization_id}/repositories")
        elif command == "repo-register":
            if not config.organization_id: raise CloudError("cloud_configuration_missing")
            result = client.request("POST", f"organizations/{config.organization_id}/repositories", json.dumps({"display_name": args.display_name}).encode(), idempotency_key=new_idempotency_key())
        elif command == "policy-show": result = client.request("GET", "policy/active")
        elif command == "policy-pull":
            result = pull_policy(config, token, Path(config.cached_policy_location or (Path.cwd() / ".sourcepack" / "cloud-policy-cache")))
        elif command.startswith("upload-"):
            path = Path(args.path)
            if not path.is_file(): raise CloudError("artifact_malformed")
            data = path.read_bytes(); artifact_type = command.removeprefix("upload-")
            if not config.uploads_enabled or artifact_type not in config.upload_categories: raise CloudError("cloud_upload_not_enabled")
            if not config.repository_id: raise CloudError("cloud_configuration_missing")
            print(f"Uploading {artifact_type}: {path} ({len(data)} bytes) to {config.repository_id}")
            result = client.request("POST", f"repositories/{config.repository_id}/artifacts", data, idempotency_key=new_idempotency_key())
        else: raise CloudError("cloud_command_invalid")
    except CloudError as exc:
        print(f"ERROR: {exc.code}", file=os.sys.stderr); return 2
    print(json.dumps(result, sort_keys=True, indent=2) if args.json else "Cloud request completed.")
    return 0
