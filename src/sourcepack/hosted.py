"""Optional SourcePack hosted control plane; never started by local commands."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

API_SCHEMA = "sourcepack.cloud.api_response.v1"
MIGRATION_VERSION = 4
ROLE_PERMISSIONS = {
    "owner": {"members:write", "repositories:read", "repositories:write", "services:write", "artifacts:write", "audit:read"},
    "maintainer": {"repositories:read", "repositories:write", "artifacts:write", "audit:read"},
    "reviewer": {"repositories:read", "audit:read"},
    "member": {"repositories:read"},
}
_PASSWORD_HASHER = PasswordHasher()


def now() -> str: return datetime.now(timezone.utc).isoformat()
def canonical_audit_timestamp(value: str, error: str) -> str:
    """Normalize a timezone-aware ISO-8601 instant to audit storage format."""
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        raise ValueError(error) from None
def hash_value(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()
def hash_password(password: str) -> str:
    if not password: raise ValueError("password_required")
    return _PASSWORD_HASHER.hash(password)
def verify_password(password_hash: str, password: str) -> bool:
    try: return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError): return False


def initialize_database(path: str | Path) -> None:
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("CREATE TABLE IF NOT EXISTS cloud_migrations (version INTEGER PRIMARY KEY)")
        applied = {r[0] for r in db.execute("SELECT version FROM cloud_migrations")}
        if 1 not in applied:
            db.executescript("""
CREATE TABLE organizations (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, display_name TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE audit_events (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, organization_id TEXT NOT NULL REFERENCES organizations(id), actor_id TEXT, action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT, timestamp TEXT NOT NULL, result TEXT NOT NULL, detail_json TEXT NOT NULL);
CREATE TABLE idempotency (organization_id TEXT NOT NULL, actor_id TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL, key TEXT NOT NULL, body_sha256 TEXT NOT NULL, response_json TEXT NOT NULL, PRIMARY KEY (organization_id, actor_id, method, route, key));
"""); db.execute("INSERT INTO cloud_migrations VALUES (1)")
        if 2 not in applied:
            db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, login_identity TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
            db.execute("INSERT INTO cloud_migrations VALUES (2)")
        if 3 not in applied:
            db.executescript("""
CREATE TABLE memberships (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, organization_id TEXT NOT NULL REFERENCES organizations(id), user_id TEXT NOT NULL REFERENCES users(id), role TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, role_changed_at TEXT NOT NULL, UNIQUE(organization_id,user_id));
CREATE TABLE repositories (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, organization_id TEXT NOT NULL REFERENCES organizations(id), display_name TEXT NOT NULL, local_identity_json TEXT, created_at TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(organization_id,id));
CREATE TABLE service_identities (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, organization_id TEXT NOT NULL REFERENCES organizations(id), display_name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE service_tokens (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, service_id TEXT NOT NULL REFERENCES service_identities(id), token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, revoked_at TEXT);
CREATE TABLE repository_assignments (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, organization_id TEXT NOT NULL REFERENCES organizations(id), repository_id TEXT NOT NULL REFERENCES repositories(id), service_id TEXT NOT NULL REFERENCES service_identities(id), creator_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(repository_id,service_id));
CREATE TABLE credentials (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id), token_hash TEXT NOT NULL UNIQUE, refresh_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, refresh_expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL);
"""); db.execute("INSERT INTO cloud_migrations VALUES (3)")
        if 4 not in applied:
            # Rebuild the original table so actor kind and the committed status are
            # part of the durable replay contract.
            db.executescript("""
ALTER TABLE idempotency RENAME TO idempotency_v1;
CREATE TABLE idempotency (organization_id TEXT NOT NULL, actor_kind TEXT NOT NULL, actor_id TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL, key TEXT NOT NULL, body_sha256 TEXT NOT NULL, response_status INTEGER NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (organization_id, actor_kind, actor_id, method, route, key));
INSERT INTO idempotency (organization_id,actor_kind,actor_id,method,route,key,body_sha256,response_status,response_json,created_at)
SELECT organization_id,'user',actor_id,method,route,key,body_sha256,201,response_json,datetime('now') FROM idempotency_v1;
DROP TABLE idempotency_v1;
""")
            db.execute("INSERT INTO cloud_migrations VALUES (4)")
        db.commit()
    finally: db.close()


class Store:
    def __init__(self, path: str | Path): self.path = str(path); initialize_database(path)
    def db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys = ON"); return conn
    def bootstrap(self, login: str, password: str, organization_name: str) -> tuple[str, str]:
        user_id, org_id, stamp = "usr_"+uuid.uuid4().hex, "org_"+uuid.uuid4().hex, now()
        with self.db() as db:
            db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (user_id,"sourcepack.cloud.user.v1",login,hash_password(password),"active",stamp))
            db.execute("INSERT INTO organizations VALUES (?,?,?,?,?)", (org_id,"sourcepack.cloud.organization.v1",organization_name,stamp,"active"))
            db.execute("INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?)", ("mem_"+uuid.uuid4().hex,"sourcepack.cloud.membership.v1",org_id,user_id,"owner","active",stamp,stamp))
        return user_id, org_id
    def audit(self, db: sqlite3.Connection, org: str, actor: str, action: str, resource: str, resource_id: str, result: str="success") -> None:
        db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", ("aud_"+uuid.uuid4().hex,"sourcepack.cloud.audit_event.v1",org,actor,action,resource,resource_id,now(),result,"{}"))
    def login(self, identity: str, password: str) -> dict | None:
        with self.db() as db:
            row=db.execute("SELECT * FROM users WHERE login_identity=?",(identity,)).fetchone()
            if not row or row["status"]!="active" or not verify_password(row["password_hash"],password): return None
            return self.issue_tokens(db,row["id"])
    def issue_tokens(self, db: sqlite3.Connection, user_id: str) -> dict:
        access, refresh=secrets.token_urlsafe(32),secrets.token_urlsafe(48); stamp=now()
        db.execute("INSERT INTO credentials VALUES (?,?,?,?,?,?,?,?,?)", ("cred_"+uuid.uuid4().hex,"sourcepack.cloud.credential.v1",user_id,hash_value(access),hash_value(refresh),(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),None,stamp))
        return {"access_token":access,"refresh_token":refresh,"token_type":"bearer","expires_in":900}
    def refresh(self, refresh: str) -> dict | None:
        with self.db() as db:
            row=db.execute("SELECT * FROM credentials WHERE refresh_hash=? AND revoked_at IS NULL AND refresh_expires_at>?",(hash_value(refresh),now())).fetchone()
            if not row: return None
            db.execute("UPDATE credentials SET revoked_at=? WHERE id=?",(now(),row["id"]))
            return self.issue_tokens(db,row["user_id"])
    def revoke(self, authorization: str) -> bool:
        """Revoke one access/refresh credential row and audit active memberships atomically."""
        if not authorization.startswith("Bearer "):
            return False
        token_hash = hash_value(authorization[7:])
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            credential = db.execute("SELECT id,user_id,refresh_hash FROM credentials WHERE token_hash=? AND revoked_at IS NULL", (token_hash,)).fetchone()
            if not credential:
                return False
            stamp = now()
            updated = db.execute("UPDATE credentials SET revoked_at=? WHERE id=? AND token_hash=? AND refresh_hash=? AND revoked_at IS NULL", (stamp, credential["id"], token_hash, credential["refresh_hash"]))
            if updated.rowcount != 1:
                return False
            organizations = db.execute("SELECT organization_id FROM memberships WHERE user_id=? AND status='active'", (credential["user_id"],)).fetchall()
            for organization in organizations:
                self.audit(db, organization["organization_id"], credential["user_id"], "credential_revoked", "credential", credential["id"])
            return True
    def actor(self, authorization: str | None) -> sqlite3.Row | None:
        if not authorization or not authorization.startswith("Bearer "): return None
        token=hash_value(authorization[7:])
        with self.db() as db:
            user=db.execute("SELECT u.*, 'user' AS actor_kind FROM credentials c JOIN users u ON u.id=c.user_id WHERE c.token_hash=? AND c.revoked_at IS NULL AND c.expires_at>? AND u.status='active'",(token,now())).fetchone()
            if user: return user
            return db.execute("SELECT s.id,s.organization_id,s.status,'service' AS actor_kind FROM service_tokens t JOIN service_identities s ON s.id=t.service_id WHERE t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>? AND s.status='active'",(token,now())).fetchone()
    def service_repository_access(self, actor: sqlite3.Row, org: str, repo: str) -> bool:
        if actor["actor_kind"] != "service" or actor["organization_id"] != org: return False
        with self.db() as db:
            return bool(db.execute("SELECT 1 FROM repository_assignments a JOIN repositories r ON r.id=a.repository_id WHERE a.service_id=? AND a.organization_id=? AND a.repository_id=? AND a.status='active' AND r.organization_id=? AND r.status='active'",(actor["id"],org,repo,org)).fetchone())
    def membership(self, actor: str, org: str) -> sqlite3.Row | None:
        with self.db() as db: return db.execute("SELECT * FROM memberships WHERE user_id=? AND organization_id=? AND status='active'",(actor,org)).fetchone()
    def permit(self, actor: str, org: str, permission: str) -> bool:
        membership=self.membership(actor,org); return bool(membership and permission in ROLE_PERMISSIONS.get(membership["role"],set()))
    def create_repository(self, actor: str, org: str, name: str) -> dict:
        if not self.permit(actor,org,"repositories:write"): raise PermissionError
        record={"schema_version":"sourcepack.cloud.repository.v1","id":"repo_"+uuid.uuid4().hex,"organization_id":org,"display_name":name,"registered_at":now(),"status":"active"}
        with self.db() as db:
            db.execute("INSERT INTO repositories VALUES (?,?,?,?,?,?,?)",(record["id"],record["schema_version"],org,name,None,record["registered_at"],"active")); self.audit(db,org,actor,"repository_registered","repository",record["id"])
        return record
    def repositories(self, actor: str, org: str) -> list[dict]:
        if not self.permit(actor,org,"repositories:read"): raise PermissionError
        with self.db() as db: return [{"schema_version":"sourcepack.cloud.repository.v1","id":r["id"],"organization_id":org,"display_name":r["display_name"],"registered_at":r["created_at"],"status":r["status"]} for r in db.execute("SELECT * FROM repositories WHERE organization_id=? ORDER BY created_at,id",(org,))]
    def _membership_record(self, row: sqlite3.Row) -> dict:
        return {"schema_version":"sourcepack.cloud.membership.v1","id":row["id"],"organization_id":row["organization_id"],"user_id":row["user_id"],"role":row["role"],"status":row["status"],"created_at":row["created_at"],"role_changed_at":row["role_changed_at"]}
    def _membership_authorized(self, db: sqlite3.Connection, actor: str, org: str) -> sqlite3.Row:
        """Authorize membership mutations inside the locked transaction."""
        row=db.execute("SELECT * FROM memberships WHERE user_id=? AND organization_id=? AND status='active'",(actor,org)).fetchone()
        if not row or "members:write" not in ROLE_PERMISSIONS.get(row["role"],set()): raise PermissionError
        return row
    def _begin_membership_write(self, db: sqlite3.Connection) -> None:
        # SQLite must acquire the write lock before any membership state is read.
        db.execute("BEGIN IMMEDIATE")
    def _authorized(self, db: sqlite3.Connection, actor: sqlite3.Row, org: str, permission: str) -> None:
        if actor["actor_kind"] != "user": raise PermissionError
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=? AND status='active'", (actor["id"], org)).fetchone()
        if not row or permission not in ROLE_PERMISSIONS.get(row["role"], set()): raise PermissionError
    def idempotent_create(self, actor: sqlite3.Row, org: str, route: str, key: str, body: bytes, mutation) -> tuple[int, dict]:
        """Atomically replay or commit a create response while holding SQLite's write lock."""
        digest=hashlib.sha256(body).hexdigest(); db=self.db()
        try:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT body_sha256,response_status,response_json FROM idempotency WHERE organization_id=? AND actor_kind=? AND actor_id=? AND method='POST' AND route=? AND key=?", (org,actor["actor_kind"],actor["id"],route,key)).fetchone()
            if row:
                if row["body_sha256"] != digest: db.rollback(); return 409,envelope(error="idempotency_conflict")
                payload=json.loads(row["response_json"]); db.rollback(); return row["response_status"],payload
            record=mutation(db)
            payload=envelope(data=record)
            db.execute("INSERT INTO idempotency VALUES (?,?,?,?,?,?,?,?,?,?)", (org,actor["actor_kind"],actor["id"],"POST",route,key,digest,201,json.dumps(payload,separators=(",",":"),sort_keys=True),now()))
            db.commit(); return 201,payload
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def create_repository_in(self, db: sqlite3.Connection, actor: sqlite3.Row, org: str, name: str) -> dict:
        self._authorized(db,actor,org,"repositories:write")
        record={"schema_version":"sourcepack.cloud.repository.v1","id":"repo_"+uuid.uuid4().hex,"organization_id":org,"display_name":name,"registered_at":now(),"status":"active"}
        db.execute("INSERT INTO repositories VALUES (?,?,?,?,?,?,?)",(record["id"],record["schema_version"],org,name,None,record["registered_at"],"active")); self.audit(db,org,actor["id"],"repository_registered","repository",record["id"])
        return record
    def add_membership_in(self, db: sqlite3.Connection, actor: sqlite3.Row, org: str, user_id: str, role: str) -> dict:
        if role not in ROLE_PERMISSIONS: raise ValueError("invalid_role")
        self._authorized(db,actor,org,"members:write")
        if not db.execute("SELECT 1 FROM users WHERE id=? AND status='active'",(user_id,)).fetchone(): raise LookupError
        existing=db.execute("SELECT * FROM memberships WHERE organization_id=? AND user_id=?",(org,user_id)).fetchone(); stamp=now()
        if existing and existing["status"] == "active": raise ValueError("duplicate_membership")
        if existing:
            db.execute("UPDATE memberships SET role=?,status='active',role_changed_at=? WHERE id=?",(role,stamp,existing["id"])); row=db.execute("SELECT * FROM memberships WHERE id=?",(existing["id"],)).fetchone(); self.audit(db,org,actor["id"],"membership_reactivated","membership",existing["id"])
        else:
            record_id="mem_"+uuid.uuid4().hex; db.execute("INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?)",(record_id,"sourcepack.cloud.membership.v1",org,user_id,role,"active",stamp,stamp)); row=db.execute("SELECT * FROM memberships WHERE id=?",(record_id,)).fetchone(); self.audit(db,org,actor["id"],"membership_added","membership",record_id)
        return self._membership_record(row)
    def create_service_in(self, db: sqlite3.Connection, actor: sqlite3.Row, org: str, name: str) -> dict:
        self._authorized(db,actor,org,"services:write"); sid="svc_"+uuid.uuid4().hex; stamp=now()
        record={"schema_version":"sourcepack.cloud.service_identity.v1","id":sid,"organization_id":org,"display_name":name,"status":"active","created_at":stamp}
        db.execute("INSERT INTO service_identities VALUES (?,?,?,?,?,?)",(sid,"sourcepack.cloud.service_identity.v1",org,name,"active",stamp)); self.audit(db,org,actor["id"],"service_created","service",sid)
        return record
    def create_service_token(self, actor: sqlite3.Row, org: str, service_id: str, route: str, key: str, body: bytes, expires_hours: int) -> tuple[int, dict]:
        """Issue a service token once; replays disclose only its non-secret metadata."""
        digest=hashlib.sha256(body).hexdigest(); db=self.db()
        try:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT body_sha256,response_status,response_json FROM idempotency WHERE organization_id=? AND actor_kind=? AND actor_id=? AND method='POST' AND route=? AND key=?", (org,actor["actor_kind"],actor["id"],route,key)).fetchone()
            if row:
                if row["body_sha256"] != digest: db.rollback(); return 409,envelope(error="idempotency_conflict")
                metadata=json.loads(row["response_json"]); db.rollback()
                return row["response_status"],envelope(data={**metadata["data"],"raw_token_disclosed":False,"raw_token_unavailable":True})
            self._authorized(db,actor,org,"services:write")
            if not db.execute("SELECT 1 FROM service_identities WHERE id=? AND organization_id=? AND status='active'",(service_id,org)).fetchone(): raise LookupError
            raw=secrets.token_urlsafe(32); expires=(datetime.now(timezone.utc)+timedelta(hours=expires_hours)).isoformat(); token_id="stok_"+uuid.uuid4().hex
            metadata={"schema_version":"sourcepack.cloud.service_token.v1","id":token_id,"service_id":service_id,"expires_at":expires}
            db.execute("INSERT INTO service_tokens VALUES (?,?,?,?,?,?)",(token_id,"sourcepack.cloud.credential.v1",service_id,hash_value(raw),expires,None)); self.audit(db,org,actor["id"],"service_token_created","service_token",token_id)
            stored=envelope(data=metadata)
            db.execute("INSERT INTO idempotency VALUES (?,?,?,?,?,?,?,?,?,?)",(org,actor["actor_kind"],actor["id"],"POST",route,key,digest,201,json.dumps(stored,separators=(",",":"),sort_keys=True),now()))
            db.commit(); return 201,envelope(data={**metadata,"token":raw,"raw_token_disclosed":True})
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def assign_service_in(self, db: sqlite3.Connection, actor: sqlite3.Row, org: str, sid: str, repo: str) -> dict:
        self._authorized(db,actor,org,"services:write"); stamp=now(); aid="asn_"+uuid.uuid4().hex
        if not db.execute("SELECT 1 FROM repositories WHERE id=? AND organization_id=? AND status='active'",(repo,org)).fetchone() or not db.execute("SELECT 1 FROM service_identities WHERE id=? AND organization_id=? AND status='active'",(sid,org)).fetchone(): raise LookupError
        previous=db.execute("SELECT id FROM repository_assignments WHERE repository_id=? AND service_id=?",(repo,sid)).fetchone()
        if previous: aid=previous["id"]; db.execute("UPDATE repository_assignments SET status='active',creator_id=?,created_at=? WHERE id=?",(actor["id"],stamp,aid))
        else: db.execute("INSERT INTO repository_assignments VALUES (?,?,?,?,?,?,?,?)",(aid,"sourcepack.cloud.repository_assignment.v1",org,repo,sid,actor["id"],"active",stamp))
        self.audit(db,org,actor["id"],"service_assigned","repository_assignment",aid)
        return {"schema_version":"sourcepack.cloud.repository_assignment.v1","id":aid,"organization_id":org,"repository_id":repo,"service_id":sid,"status":"active","created_at":stamp}
    def add_membership(self, actor: str, org: str, user_id: str, role: str) -> dict:
        if role not in ROLE_PERMISSIONS: raise ValueError("invalid_role")
        db=self.db()
        try:
            self._begin_membership_write(db); self._membership_authorized(db,actor,org)
            if not db.execute("SELECT 1 FROM users WHERE id=? AND status='active'",(user_id,)).fetchone(): raise LookupError
            existing=db.execute("SELECT * FROM memberships WHERE organization_id=? AND user_id=?",(org,user_id)).fetchone()
            if existing and existing["status"] == "active": raise ValueError("duplicate_membership")
            stamp=now()
            if existing:
                db.execute("UPDATE memberships SET role=?,status='active',role_changed_at=? WHERE id=?",(role,stamp,existing["id"]))
                row=db.execute("SELECT * FROM memberships WHERE id=?",(existing["id"],)).fetchone()
                self.audit(db,org,actor,"membership_reactivated","membership",existing["id"])
            else:
                record_id="mem_"+uuid.uuid4().hex
                db.execute("INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?)",(record_id,"sourcepack.cloud.membership.v1",org,user_id,role,"active",stamp,stamp))
                row=db.execute("SELECT * FROM memberships WHERE id=?",(record_id,)).fetchone()
                self.audit(db,org,actor,"membership_added","membership",record_id)
            db.commit(); return self._membership_record(row)
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def _owner_count(self, db: sqlite3.Connection, org: str) -> int:
        return int(db.execute("SELECT COUNT(*) FROM memberships WHERE organization_id=? AND role='owner' AND status='active'", (org,)).fetchone()[0])
    def change_role(self, actor: str, org: str, membership_id: str, role: str) -> None:
        if role not in ROLE_PERMISSIONS: raise ValueError("invalid_role")
        db=self.db()
        try:
            self._begin_membership_write(db); self._membership_authorized(db,actor,org)
            row=db.execute("SELECT * FROM memberships WHERE id=? AND organization_id=? AND status='active'",(membership_id,org)).fetchone()
            if not row: raise LookupError
            if row["role"]=="owner" and role!="owner" and self._owner_count(db,org)<=1: raise ValueError("final_owner")
            db.execute("UPDATE memberships SET role=?,role_changed_at=? WHERE id=?",(role,now(),membership_id)); self.audit(db,org,actor,"membership_role_changed","membership",membership_id)
            db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def remove_member(self, actor: str, org: str, membership_id: str) -> None:
        db=self.db()
        try:
            self._begin_membership_write(db); self._membership_authorized(db,actor,org)
            row=db.execute("SELECT * FROM memberships WHERE id=? AND organization_id=? AND status='active'",(membership_id,org)).fetchone()
            if not row: raise LookupError
            if row["role"]=="owner" and self._owner_count(db,org)<=1: raise ValueError("final_owner")
            db.execute("UPDATE memberships SET status='removed' WHERE id=?",(membership_id,)); self.audit(db,org,actor,"membership_removed","membership",membership_id)
            db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def repository(self, actor:str, org:str, repo:str)->dict:
        if not self.permit(actor,org,"repositories:read"): raise PermissionError
        with self.db() as db:
            row=db.execute("SELECT * FROM repositories WHERE id=? AND organization_id=?",(repo,org)).fetchone()
            if not row: raise LookupError
            return {"schema_version":"sourcepack.cloud.repository.v1","id":row["id"],"organization_id":org,"display_name":row["display_name"],"registered_at":row["created_at"],"status":row["status"]}
    def set_repository_status(self,actor:str,org:str,repo:str,status:str)->None:
        if status not in {"active","inactive"} or not self.permit(actor,org,"repositories:write"): raise PermissionError
        with self.db() as db:
            if db.execute("UPDATE repositories SET status=? WHERE id=? AND organization_id=?",(status,repo,org)).rowcount!=1: raise LookupError
            self.audit(db,org,actor,"repository_"+status,"repository",repo)
    def create_service(self,actor:str,org:str,name:str,expires_hours:int=720)->tuple[dict,str]:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        sid="svc_"+uuid.uuid4().hex; token=secrets.token_urlsafe(32); stamp=now()
        record={"schema_version":"sourcepack.cloud.service_identity.v1","id":sid,"organization_id":org,"display_name":name,"status":"active","created_at":stamp}
        with self.db() as db:
            db.execute("INSERT INTO service_identities VALUES (?,?,?,?,?,?)",(sid,"sourcepack.cloud.service_identity.v1",org,name,"active",stamp)); db.execute("INSERT INTO service_tokens VALUES (?,?,?,?,?,?)",("stok_"+uuid.uuid4().hex,"sourcepack.cloud.credential.v1",sid,hash_value(token),(datetime.now(timezone.utc)+timedelta(hours=expires_hours)).isoformat(),None)); self.audit(db,org,actor,"service_created","service",sid)
        return record,token
    def services(self,actor:str,org:str)->list[dict]:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        with self.db() as db:return [{"schema_version":"sourcepack.cloud.service_identity.v1","id":r["id"],"organization_id":org,"display_name":r["display_name"],"status":r["status"],"created_at":r["created_at"]} for r in db.execute("SELECT * FROM service_identities WHERE organization_id=? ORDER BY created_at,id",(org,))]
    def revoke_service(self,actor:str,org:str,sid:str)->None:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        with self.db() as db:
            if db.execute("UPDATE service_identities SET status='revoked' WHERE id=? AND organization_id=?",(sid,org)).rowcount!=1: raise LookupError
            db.execute("UPDATE service_tokens SET revoked_at=? WHERE service_id=?",(now(),sid)); self.audit(db,org,actor,"service_revoked","service",sid)
    def assign_service(self,actor:str,org:str,sid:str,repo:str)->dict:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        stamp=now(); aid="asn_"+uuid.uuid4().hex
        with self.db() as db:
            if not db.execute("SELECT 1 FROM repositories WHERE id=? AND organization_id=? AND status='active'",(repo,org)).fetchone(): raise LookupError
            if not db.execute("SELECT 1 FROM service_identities WHERE id=? AND organization_id=? AND status='active'",(sid,org)).fetchone(): raise LookupError
            previous=db.execute("SELECT id FROM repository_assignments WHERE repository_id=? AND service_id=?",(repo,sid)).fetchone()
            if previous:
                aid=previous["id"]; db.execute("UPDATE repository_assignments SET status='active',creator_id=?,created_at=? WHERE id=?",(actor,stamp,aid))
            else: db.execute("INSERT INTO repository_assignments VALUES (?,?,?,?,?,?,?,?)",(aid,"sourcepack.cloud.repository_assignment.v1",org,repo,sid,actor,"active",stamp))
            self.audit(db,org,actor,"service_assigned","repository_assignment",aid)
        return {"schema_version":"sourcepack.cloud.repository_assignment.v1","id":aid,"organization_id":org,"repository_id":repo,"service_id":sid,"status":"active","created_at":stamp}
    def assignments(self,actor:str,org:str,sid:str)->list[dict]:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        with self.db() as db:return [{"schema_version":"sourcepack.cloud.repository_assignment.v1","id":r["id"],"organization_id":org,"repository_id":r["repository_id"],"service_id":sid,"status":r["status"],"created_at":r["created_at"]} for r in db.execute("SELECT * FROM repository_assignments WHERE organization_id=? AND service_id=? AND status='active' ORDER BY created_at,id",(org,sid))]
    def remove_assignment(self,actor:str,org:str,aid:str)->None:
        if not self.permit(actor,org,"services:write"): raise PermissionError
        with self.db() as db:
            if db.execute("UPDATE repository_assignments SET status='removed' WHERE id=? AND organization_id=? AND status='active'",(aid,org)).rowcount!=1: raise LookupError
            self.audit(db,org,actor,"service_assignment_removed","repository_assignment",aid)
    def members(self, actor: str, org: str) -> list[dict]:
        if not self.permit(actor,org,"repositories:read"): raise PermissionError
        with self.db() as db:
            return [self._membership_record(r) for r in db.execute("SELECT * FROM memberships WHERE organization_id=? ORDER BY created_at,id",(org,))]
    def audit_events(self, actor: sqlite3.Row, org: str, filters: dict[str, object]) -> dict:
        """Return the append-only organization audit history in cursor order."""
        if actor["actor_kind"] != "user" or not self.permit(actor["id"], org, "audit:read"):
            raise PermissionError
        clauses = ["organization_id=?"]
        parameters: list[object] = [org]
        for field in ("actor_id", "action", "resource_type", "resource_id", "result"):
            value = filters.get(field)
            if value is not None:
                clauses.append(f"{field}=?")
                parameters.append(value)
        if filters.get("timestamp_from") is not None:
            clauses.append("timestamp>=?")
            parameters.append(filters["timestamp_from"])
        if filters.get("timestamp_to") is not None:
            clauses.append("timestamp<=?")
            parameters.append(filters["timestamp_to"])
        cursor = filters.get("cursor")
        if cursor is not None:
            cursor_org, cursor_timestamp, cursor_id, cursor_filter_digest = decode_audit_cursor(str(cursor))
            if cursor_org != org or cursor_filter_digest != audit_filter_digest(filters):
                raise ValueError("invalid_cursor")
            clauses.append("(timestamp < ? OR (timestamp = ? AND id < ?))")
            parameters.extend((cursor_timestamp, cursor_timestamp, cursor_id))
        parameters.append(int(filters["limit"]) + 1)
        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM audit_events WHERE " + " AND ".join(clauses) +
                " ORDER BY timestamp DESC, id DESC LIMIT ?", parameters,
            ).fetchall()
        more = len(rows) > int(filters["limit"])
        rows = rows[:int(filters["limit"])]
        items = []
        for row in rows:
            try:
                detail = json.loads(row["detail_json"])
            except (TypeError, json.JSONDecodeError):
                # Existing audit rows are durable evidence; do not rewrite them.
                detail = {}
            if not isinstance(detail, dict):
                detail = {}
            items.append({
                "id": row["id"], "schema_version": row["schema_version"],
                "organization_id": row["organization_id"], "actor_id": row["actor_id"],
                "action": row["action"], "resource_type": row["resource_type"],
                "resource_id": row["resource_id"], "timestamp": row["timestamp"],
                "result": row["result"], "detail": detail,
            })
        next_cursor = encode_audit_cursor(org, rows[-1]["timestamp"], rows[-1]["id"], audit_filter_digest(filters)) if more else None
        return {"schema_version": "sourcepack.cloud.audit_event_collection.v1", "items": items, "next_cursor": next_cursor}


def envelope(*, data: object | None=None, error: str | None=None, request_id: str | None=None) -> dict:
    result={"schema_version":API_SCHEMA,"ok":error is None,"request_id":request_id or str(uuid.uuid4())}; result["data" if error is None else "error"] = data if error is None else {"code":error,"message":"The request could not be completed."}; return result


def valid_idempotency_key(key: str | None) -> bool:
    return bool(key and 16 <= len(key) <= 128 and all(33 <= ord(char) <= 126 for char in key))


AUDIT_QUERY_FIELDS = {"actor_id", "action", "resource_type", "resource_id", "result", "timestamp_from", "timestamp_to", "limit", "cursor"}
AUDIT_DEFAULT_LIMIT = 50
AUDIT_MAX_LIMIT = 100


def audit_filter_digest(filters: dict[str, object]) -> str:
    """Bind cursors to the filters that define their ordered result set."""
    values = {key: filters[key] for key in sorted(filters) if key not in {"cursor", "limit"}}
    return hashlib.sha256(json.dumps(values, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def encode_audit_cursor(org: str, timestamp: str, event_id: str, filter_digest: str) -> str:
    payload = json.dumps([org, canonical_audit_timestamp(timestamp, "invalid_cursor"), event_id, filter_digest], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_audit_cursor(cursor: str) -> tuple[str, str, str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        org, timestamp, event_id, filter_digest = json.loads(decoded.decode())
        if not all(isinstance(value, str) and value for value in (org, timestamp, event_id, filter_digest)):
            raise ValueError
        canonical_timestamp = canonical_audit_timestamp(timestamp, "invalid_cursor")
        if timestamp != canonical_timestamp or not event_id.startswith("aud_") or len(filter_digest) != 64:
            raise ValueError
        int(filter_digest, 16)
        return org, canonical_timestamp, event_id, filter_digest
    except (binascii.Error, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid_cursor") from None


def audit_query(query: str) -> dict[str, object]:
    pairs = parse_qsl(query, keep_blank_values=True)
    if len({key for key, _ in pairs}) != len(pairs) or any(key not in AUDIT_QUERY_FIELDS for key, _ in pairs):
        raise ValueError("invalid_request")
    result: dict[str, object] = {key: value for key, value in pairs}
    raw_limit = result.get("limit", str(AUDIT_DEFAULT_LIMIT))
    try:
        limit = int(str(raw_limit))
    except ValueError:
        raise ValueError("invalid_request") from None
    if str(limit) != raw_limit or not 1 <= limit <= AUDIT_MAX_LIMIT:
        raise ValueError("invalid_request")
    result["limit"] = limit
    for field in ("timestamp_from", "timestamp_to"):
        if field in result:
            result[field] = canonical_audit_timestamp(str(result[field]), "invalid_request")
    if result.get("timestamp_from", "") > result.get("timestamp_to", "~"):
        raise ValueError("invalid_request")
    if "cursor" in result:
        decode_audit_cursor(str(result["cursor"]))
    return result


def make_handler(database: str | Path) -> type[BaseHTTPRequestHandler]:
    store=Store(database)
    class Handler(BaseHTTPRequestHandler):
        server_version="SourcePackHosted/1"; max_body=1_000_000
        def log_message(self, format: str, *args: object) -> None: return
        def send(self,status:int,payload:dict)->None:
            body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
        def bounded_body(self, absent_length: int) -> bytes | None:
            """Read only a declared body whose length is valid for this handler."""
            raw_length=self.headers.get("Content-Length")
            try: size=absent_length if raw_length is None else int(raw_length)
            except ValueError: self.send(400,envelope(error="malformed_json")); return None
            if size < 0: self.send(400,envelope(error="malformed_json")); return None
            if size > self.max_body: self.send(413,envelope(error="payload_too_large")); return None
            body=self.rfile.read(size)
            if len(body) != size: self.send(400,envelope(error="malformed_json")); return None
            return body
        def body(self)->dict|None:
            if self.headers.get("Content-Type","").split(";",1)[0]!="application/json": self.send(415,envelope(error="unsupported_content_type")); return None
            try:
                self.request_body=self.bounded_body(-1)
                if self.request_body is None: return None
                def pairs(items):
                    d={}
                    for k,v in items:
                        if k in d: raise ValueError
                        d[k]=v
                    return d
                value=json.loads(self.request_body.decode(),object_pairs_hook=pairs); assert isinstance(value,dict); return value
            except Exception: self.send(400,envelope(error="malformed_json")); return None
        def auth(self):
            actor=store.actor(self.headers.get("Authorization"))
            if not actor: self.send(401,envelope(error="authentication_required")); return None
            return actor
        def membership_actor(self, actor):
            if actor["actor_kind"] != "user": self.send(404,envelope(error="not_found")); return None
            return actor
        def create(self, actor, org: str, path: str, mutation) -> None:
            key=self.headers.get("Idempotency-Key")
            if not valid_idempotency_key(key): self.send(400,envelope(error="invalid_idempotency_key")); return
            try:
                status,payload=store.idempotent_create(actor,org,path,key,self.request_body,mutation); self.send(status,payload)
            except ValueError as exc:self.send(409 if str(exc)=="duplicate_membership" else 400,envelope(error=str(exc) if str(exc)=="duplicate_membership" else "invalid_request"))
            except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
        def do_GET(self)->None:
            path=urlparse(self.path).path
            if path=="/api/v1/health": self.send(200,envelope(data={"status":"ok"})); return
            actor=self.auth()
            if not actor:return
            if path=="/api/v1/auth/me":
                if actor["actor_kind"] != "user": self.send(404,envelope(error="not_found")); return
                self.send(200,envelope(data={"schema_version":"sourcepack.cloud.user.v1","id":actor["id"],"login_identity":actor["login_identity"],"status":actor["status"],"created_at":actor["created_at"]})); return
            parts=path.split("/")
            if len(parts)==5 and parts[3]=="organizations" and parts[4]:
                if not store.permit(actor["id"],parts[4],"repositories:read"): self.send(404,envelope(error="not_found")); return
                with store.db() as db: row=db.execute("SELECT * FROM organizations WHERE id=? AND status='active'",(parts[4],)).fetchone()
                if not row:self.send(404,envelope(error="not_found")); return
                self.send(200,envelope(data={"schema_version":"sourcepack.cloud.organization.v1","id":row["id"],"display_name":row["display_name"],"created_at":row["created_at"],"status":row["status"]})); return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="repositories":
                try:self.send(200,envelope(data={"items":store.repositories(actor["id"],parts[4])}))
                except PermissionError:self.send(404,envelope(error="not_found"))
                return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="audit-events":
                try:
                    self.send(200,envelope(data=store.audit_events(actor, parts[4], audit_query(urlparse(self.path).query))))
                except PermissionError:
                    self.send(404,envelope(error="not_found"))
                except ValueError as exc:
                    self.send(400,envelope(error=str(exc)))
                return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="members":
                if not self.membership_actor(actor): return
                try:self.send(200,envelope(data={"items":store.members(actor["id"],parts[4])}))
                except PermissionError:self.send(404,envelope(error="not_found"))
                return
            if len(parts)==7 and parts[3]=="organizations" and parts[5]=="repositories":
                try:self.send(200,envelope(data=store.repository(actor["id"],parts[4],parts[6])))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="services":
                try:self.send(200,envelope(data={"items":store.services(actor["id"],parts[4])}))
                except PermissionError:self.send(404,envelope(error="not_found"))
                return
            if len(parts)==8 and parts[3]=="organizations" and parts[5]=="services" and parts[7]=="assignments":
                try:self.send(200,envelope(data={"items":store.assignments(actor["id"],parts[4],parts[6])}))
                except PermissionError:self.send(404,envelope(error="not_found"))
                return
            self.send(404,envelope(error="not_found"))
        def do_POST(self)->None:
            path=urlparse(self.path).path; data=self.body()
            if data is None:return
            if path=="/api/v1/auth/login":
                tokens=store.login(str(data.get("identity","")),str(data.get("password",""))); self.send(200 if tokens else 401,envelope(data=tokens) if tokens else envelope(error="authentication_rejected")); return
            if path=="/api/v1/auth/refresh":
                tokens=store.refresh(str(data.get("refresh_token",""))); self.send(200 if tokens else 401,envelope(data=tokens) if tokens else envelope(error="authentication_rejected")); return
            actor=self.auth()
            if not actor:return
            parts=path.split("/")
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="repositories":
                name=data.get("display_name")
                if not isinstance(name,str) or not name.strip(): self.send(400,envelope(error="invalid_request")); return
                self.create(actor,parts[4],path,lambda db: store.create_repository_in(db,actor,parts[4],name))
                return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="members":
                if not self.membership_actor(actor): return
                if set(data)!={"user_id","role"} or not isinstance(data.get("user_id"),str) or not isinstance(data.get("role"),str): self.send(400,envelope(error="invalid_request")); return
                self.create(actor,parts[4],path,lambda db: store.add_membership_in(db,actor,parts[4],data["user_id"],data["role"]))
                return
            if len(parts)==6 and parts[3]=="organizations" and parts[5]=="services":
                if set(data)!={"display_name"} or not isinstance(data.get("display_name"),str):self.send(400,envelope(error="invalid_request"));return
                self.create(actor,parts[4],path,lambda db: store.create_service_in(db,actor,parts[4],data["display_name"]))
                return
            if len(parts)==8 and parts[3]=="organizations" and parts[5]=="services" and parts[7]=="tokens":
                if set(data) != {"expires_hours"} or not isinstance(data.get("expires_hours"),int) or not 1 <= data["expires_hours"] <= 8760: self.send(400,envelope(error="invalid_request")); return
                key=self.headers.get("Idempotency-Key")
                if not valid_idempotency_key(key): self.send(400,envelope(error="invalid_idempotency_key")); return
                try:
                    status,payload=store.create_service_token(actor,parts[4],parts[6],path,key,self.request_body,data["expires_hours"]); self.send(status,payload)
                except (PermissionError,LookupError): self.send(404,envelope(error="not_found"))
                return
            if len(parts)==9 and parts[3]=="organizations" and parts[5]=="repositories" and parts[7] in {"deactivate","reactivate"}:
                self.send(404,envelope(error="not_found")); return
            if len(parts)==8 and parts[3]=="organizations" and parts[5]=="repositories" and parts[7] in {"deactivate","reactivate"}:
                try:store.set_repository_status(actor["id"],parts[4],parts[6],"inactive" if parts[7]=="deactivate" else "active");self.send(200,envelope(data={"status":"inactive" if parts[7]=="deactivate" else "active"}))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            if len(parts)==8 and parts[3]=="organizations" and parts[5]=="services" and parts[7]=="revoke":
                try:store.revoke_service(actor["id"],parts[4],parts[6]);self.send(200,envelope(data={"revoked":True}))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            if len(parts)==8 and parts[3]=="organizations" and parts[5]=="services" and parts[7]=="assignments":
                if set(data)!={"repository_id"} or not isinstance(data.get("repository_id"),str):self.send(400,envelope(error="invalid_request"));return
                self.create(actor,parts[4],path,lambda db: store.assign_service_in(db,actor,parts[4],parts[6],data["repository_id"]))
                return
            self.send(404,envelope(error="not_found"))
        def do_DELETE(self)->None:
            if urlparse(self.path).path=="/api/v1/auth/current":
                if store.revoke(self.headers.get("Authorization", "")): self.send(200,envelope(data={"revoked":True}))
                else:self.send(401,envelope(error="authentication_required"))
                return
            actor=self.auth()
            if not actor:return
            parts=urlparse(self.path).path.split("/")
            if len(parts)==7 and parts[3]=="organizations" and parts[5]=="members":
                if not self.membership_actor(actor): return
                content_type=self.headers.get("Content-Type")
                if content_type and content_type.split(";",1)[0] != "application/json": self.send(415,envelope(error="unsupported_content_type")); return
                try:
                    delete_body=self.bounded_body(0)
                    if delete_body is None: return
                    if delete_body:
                        def pairs(items):
                            result={}
                            for key,value in items:
                                if key in result: raise ValueError
                                result[key]=value
                            return result
                        if _json:=json.loads(delete_body.decode(),object_pairs_hook=pairs): raise ValueError
                except Exception: self.send(400,envelope(error="malformed_json")); return
                try:store.remove_member(actor["id"],parts[4],parts[6]);self.send(200,envelope(data={"removed":True}))
                except ValueError:self.send(409,envelope(error="final_owner"))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            if len(parts)==7 and parts[3]=="organizations" and parts[5]=="assignments":
                try:store.remove_assignment(actor["id"],parts[4],parts[6]);self.send(200,envelope(data={"removed":True}))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            self.send(404,envelope(error="not_found"))
        def do_PATCH(self)->None:
            data=self.body()
            if data is None:return
            actor=self.auth()
            if not actor:return
            parts=urlparse(self.path).path.split("/")
            if len(parts)==7 and parts[3]=="organizations" and parts[5]=="members":
                if not self.membership_actor(actor): return
                if set(data)!={"role"} or not isinstance(data.get("role"),str): self.send(400,envelope(error="invalid_request")); return
                try:store.change_role(actor["id"],parts[4],parts[6],data["role"]);self.send(200,envelope(data={"changed":True}))
                except ValueError as exc:self.send(409 if str(exc)=="final_owner" else 400,envelope(error=str(exc) if str(exc)=="final_owner" else "invalid_request"))
                except (PermissionError,LookupError):self.send(404,envelope(error="not_found"))
                return
            self.send(400,envelope(error="invalid_request"))
    return Handler


def main(argv: list[str] | None=None)->int:
    parser=argparse.ArgumentParser(description="Run the optional SourcePack hosted API."); parser.add_argument("--database",required=True); parser.add_argument("--host",default="127.0.0.1"); parser.add_argument("--port",type=int,default=8080); args=parser.parse_args(argv)
    ThreadingHTTPServer((args.host,args.port),make_handler(args.database)).serve_forever(); return 0
