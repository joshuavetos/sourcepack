"""Offline, deterministic public schema registry for stable SourcePack artifacts.

Only ``effective-policy.v1`` is public currently.  Other version-tagged JSON
artifacts are deliberately deferred: their emitters either accept open event
or scope vocabularies, or emit incompatible report variants under one version.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .policy import EFFECTIVE_POLICY_SCHEMA_VERSION, SUPPORTED_PACKAGE_MANAGERS, _POLICY_RULE_NAMES

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
EXIT_UNKNOWN_SCHEMA = 2
EXIT_UNREADABLE = 3
EXIT_MALFORMED_JSON = 4
EXIT_INVALID = 5
EXIT_INTERNAL = 6

@dataclass(frozen=True)
class Contract:
    name: str
    artifact_version: str
    description: str
    aliases: tuple[str, ...]
    owner: str


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _safe_policy_path_schema() -> dict[str, Any]:
    # Runtime owns full normalization; this structural portion rejects empty,
    # backslash, absolute, and parent-traversal forms.
    return {"type": "string", "minLength": 1, "pattern": r"^(?!/)(?![A-Za-z]:)(?!.*\\)(?!.*(?:^|/)\.\.(?:/|$))(?!.*//).+$"}


def _rule_schemas() -> dict[str, dict[str, Any]]:
    """Rule-specific schemas, keyed from the canonical policy registry."""
    array = {"type": "array", "items": _safe_policy_path_schema(), "uniqueItems": True}
    values = {
        "block_dependency_additions": {"type": "boolean"},
        "block_secret_patterns": {"type": "boolean"},
        "protected_paths": array,
        "require_tests_for": array,
        "max_changed_lines": {"type": "integer", "minimum": 1},
        "package_manager": {"type": "string", "enum": sorted(SUPPORTED_PACKAGE_MANAGERS)},
    }
    if set(values) != set(_POLICY_RULE_NAMES):
        raise RuntimeError("policy rule schema mapping is not synchronized with runtime rules")
    return {name: _nullable(values[name]) for name in _POLICY_RULE_NAMES}


def _rule_result_schema(value_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["organization_constraint", "repository_contribution", "effective_value", "provenance", "comparison_method", "compatibility_status"],
        "properties": {
            "organization_constraint": value_schema,
            "repository_contribution": value_schema,
            "effective_value": value_schema,
            "provenance": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string", "enum": ["organization", "repository"]}, "uniqueItems": True}},
            "comparison_method": {"type": "string", "minLength": 1},
            "compatibility_status": {"type": "string", "enum": ["absent", "compatible", "conflict", "rejected_weakening", "strengthening"]},
        },
    }


def _rule_change_schema(rule: str, value_schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "required": ["rule", "organization_value", "repository_value", "comparison_method", "reason"],
            "properties": {"rule": {"const": rule}, "organization_value": value_schema,
                           "repository_value": value_schema,
                           "comparison_method": {"type": "string", "minLength": 1},
                           "reason": {"type": "string", "minLength": 1}}}


def effective_policy_schema() -> dict[str, Any]:
    """Generate the sole source of truth from policy-owned vocabularies."""
    rule_values = _rule_schemas()
    rule_names = list(_POLICY_RULE_NAMES)
    sparse_effective = {"type": "object", "additionalProperties": False,
                        "properties": rule_values}
    nullable_sha = {"type": ["string", "null"], "pattern": "^(?:sha256:)?[0-9a-f]{64}$"}
    return {
        "$schema": DRAFT_2020_12,
        "$id": "https://schemas.sourcepack.local/effective-policy.v1.schema.json",
        "title": "SourcePack Effective Policy v1",
        "description": "Resolved local repository and caller-designated organization policy.",
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "resolution_status", "organization_policy_mode", "organization_policy_status", "organization_policy_source", "organization_policy_id", "organization_policy_hash", "repository_policy_source", "repository_policy_hash", "effective_policy", "rules", "strengthening_contributions", "rejected_weakening_attempts", "conflicts", "errors", "effective_policy_id"],
        "properties": {
            "schema_version": {"const": EFFECTIVE_POLICY_SCHEMA_VERSION},
            "resolution_status": {"type": "string", "enum": ["PASS", "FAIL"]},
            "organization_policy_mode": {"type": "string", "enum": ["optional", "required"]},
            "organization_policy_status": {"type": "string", "enum": ["not_supplied", "required_but_missing", "loaded", "trust_boundary_violation", "invalid"]},
            "organization_policy_source": {"type": "object", "additionalProperties": False, "required": ["supplied", "path"], "properties": {"supplied": {"type": "boolean"}, "path": {"type": ["string", "null"]}, "resolved_path": {"type": "string", "minLength": 1}}},
            "organization_policy_id": {"type": ["string", "null"], "minLength": 1}, "organization_policy_hash": nullable_sha,
            "repository_policy_source": {"type": "object", "additionalProperties": False, "required": ["path", "status"], "properties": {"path": {"const": ".sourcepack/policy.json"}, "status": {"type": "string", "enum": ["loaded", "absent", "invalid"]}}},
            "repository_policy_hash": nullable_sha,
            # The runtime intentionally emits a sparse effective map: absent
            # means no effective constraint, while rules is always complete.
            "effective_policy": sparse_effective,
            "rules": {"type": "object", "additionalProperties": False, "required": rule_names,
                      "properties": {name: _rule_result_schema(rule_values[name]) for name in rule_names}},
            "strengthening_contributions": {"type": "array", "items": {"type": "string", "enum": rule_names}, "uniqueItems": True},
            "rejected_weakening_attempts": {"type": "array", "items": {"oneOf": [_rule_change_schema(name, rule_values[name]) for name in rule_names]}},
            "conflicts": {"type": "array", "items": _rule_change_schema("package_manager", rule_values["package_manager"])},
            "errors": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
            "effective_policy_id": {"type": "string", "pattern": "^epol_[0-9a-f]{32}$"},
        },
    }

CONTRACTS = (Contract("effective-policy.v1", EFFECTIVE_POLICY_SCHEMA_VERSION, "Resolved organization and repository policy.", ("effective-policy",), "sourcepack.policy.resolve_effective_policy"),)

def resolve(name: str) -> Contract | None:
    return next((c for c in CONTRACTS if name == c.name or name in c.aliases), None)

def schema_for(contract: Contract) -> dict[str, Any]:
    if contract.name == "effective-policy.v1": return effective_policy_schema()
    raise KeyError(contract.name)

def schema_bytes(contract: Contract) -> bytes:
    return (json.dumps(schema_for(contract), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")

class DuplicateKeyError(ValueError): pass

def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out: raise DuplicateKeyError(key)
        out[key] = value
    return out

def load_json(path: str | Path) -> Any:
    raw = Path(path).read_bytes()
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)

def _semantic_errors(instance: Any) -> list[dict[str, str]]:
    """Validate stable bidirectional relationships emitted by the resolver."""
    if not isinstance(instance, dict):
        return []
    errors = instance.get("errors") if isinstance(instance.get("errors"), list) else []
    status = instance.get("resolution_status")
    conflicts = instance.get("conflicts") if isinstance(instance.get("conflicts"), list) else []
    weakening = instance.get("rejected_weakening_attempts") if isinstance(instance.get("rejected_weakening_attempts"), list) else []
    problems: list[tuple[str, str, str]] = []
    def add(code: str, path: str, message: str) -> None:
        problems.append((code, path, message))
    if status == "PASS" and (errors or conflicts or weakening):
        add("resolution_state_mismatch", "/resolution_status", "PASS resolver output has no errors, conflicts, or rejected weakening attempts")
    if status == "FAIL" and not errors:
        add("resolution_state_mismatch", "/errors", "FAIL resolver output has at least one error")
    conflict_error = "policy_conflict" in errors
    weakening_error = "repository_policy_weakening_attempt" in errors
    if bool(conflicts) != conflict_error:
        add("conflict_error_mismatch", "/conflicts", "policy_conflict and conflicts are emitted together")
    if bool(weakening) != weakening_error:
        add("weakening_error_mismatch", "/rejected_weakening_attempts", "repository_policy_weakening_attempt and rejected weakening attempts are emitted together")
    org_status = instance.get("organization_policy_status")
    org_mode = instance.get("organization_policy_mode")
    org_source = instance.get("organization_policy_source") if isinstance(instance.get("organization_policy_source"), dict) else {}
    org_id, org_hash = instance.get("organization_policy_id"), instance.get("organization_policy_hash")
    required_error = "org_policy_required_but_missing" in errors
    trust_error = any(isinstance(item, str) and item.startswith("org_policy_trust_boundary_violation") for item in errors)
    invalid_error = any(isinstance(item, str) and item.startswith("org_policy_") and not item.startswith("org_policy_trust_boundary_violation") and item != "org_policy_required_but_missing" for item in errors)
    if org_status == "not_supplied":
        if org_mode != "optional":
            add("organization_mode_status_mismatch", "/organization_policy_mode", "not_supplied organization policy uses optional mode")
        if org_source.get("supplied") is not False or org_source.get("path") is not None or "resolved_path" in org_source or org_id is not None or org_hash is not None:
            add("organization_source_mismatch", "/organization_policy_source", "not_supplied organization policy has no supplied source, identity, or hash")
        if required_error or trust_error or invalid_error:
            add("organization_status_error_mismatch", "/errors", "not_supplied organization policy has no organization-policy failure error")
    elif org_status == "required_but_missing":
        if org_mode != "required" or org_source.get("supplied") is not False or org_source.get("path") is not None or "resolved_path" in org_source or org_id is not None or org_hash is not None:
            add("organization_mode_status_mismatch", "/organization_policy_status", "required_but_missing has no supplied organization source, identity, or hash")
        if status != "FAIL" or not required_error or trust_error or invalid_error:
            add("organization_status_error_mismatch", "/organization_policy_status", "required_but_missing emits only its canonical organization failure error")
    elif org_status == "loaded":
        if org_source.get("supplied") is not True or not isinstance(org_source.get("path"), str) or not org_source.get("path") or not isinstance(org_source.get("resolved_path"), str) or not org_source.get("resolved_path") or not isinstance(org_id, str) or not org_id or not isinstance(org_hash, str) or not org_hash:
            add("organization_source_mismatch", "/organization_policy_status", "loaded organization policy has supplied path, resolved path, ID, and hash")
        if required_error or trust_error or invalid_error:
            add("organization_status_error_mismatch", "/errors", "loaded organization policy has no organization-policy load failure error")
    elif org_status in {"invalid", "trust_boundary_violation"}:
        if org_source.get("supplied") is not True or not isinstance(org_source.get("path"), str) or not org_source.get("path"):
            add("organization_source_mismatch", "/organization_policy_status", "supplied invalid organization policy retains its source path")
        expected = trust_error if org_status == "trust_boundary_violation" else invalid_error
        exclusive = (trust_error and not required_error and not invalid_error) if org_status == "trust_boundary_violation" else (invalid_error and not required_error and not trust_error)
        if status != "FAIL":
            add("organization_status_resolution_mismatch", "/resolution_status", "invalid organization policy status emits FAIL")
        if not expected or not exclusive:
            add("organization_status_error_mismatch", "/errors", "organization failure status has only its matching canonical error family")
    repo = instance.get("repository_policy_source") if isinstance(instance.get("repository_policy_source"), dict) else {}
    repo_status, repo_hash = repo.get("status"), instance.get("repository_policy_hash")
    repository_error = any(isinstance(item, str) and item.startswith("repository_policy_config_") for item in errors)
    if repo_status == "absent":
        if repo_hash is not None:
            add("repository_status_hash_mismatch", "/repository_policy_hash", "absent repository policy has no hash")
        if repository_error:
            add("repository_status_error_mismatch", "/errors", "absent repository policy has no repository validation error")
    elif repo_status == "loaded":
        if not isinstance(repo_hash, str) or not repo_hash:
            add("repository_status_hash_mismatch", "/repository_policy_hash", "loaded repository policy has a hash")
        if repository_error:
            add("repository_status_error_mismatch", "/errors", "loaded repository policy has no repository validation error")
    elif repo_status == "invalid":
        if status != "FAIL":
            add("repository_status_resolution_mismatch", "/resolution_status", "invalid repository policy emits FAIL")
        if not repository_error:
            add("repository_status_error_mismatch", "/errors", "invalid repository policy has a repository validation error")
        if not isinstance(repo_hash, str) or not repo_hash:
            add("repository_status_hash_mismatch", "/repository_policy_hash", "invalid repository policy has its emitted content or byte hash")
    return [{"document_path": path, "schema_path": "/semantic", "keyword": code, "message": message} for code, path, message in problems]


def validation_errors(contract: Contract, instance: Any) -> list[dict[str, str]]:
    schema = schema_for(contract)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = []
    for error in validator.iter_errors(instance):
        doc_path = "/" + "/".join(str(v) for v in error.absolute_path)
        schema_path = "/" + "/".join(str(v) for v in error.absolute_schema_path)
        errors.append({"document_path": doc_path or "/", "schema_path": schema_path or "/", "keyword": error.validator or "validation", "message": "artifact does not satisfy the selected contract"})
    errors.extend(_semantic_errors(instance))
    return sorted(errors, key=lambda e: (e["document_path"], e["schema_path"], e["keyword"], e["message"]))

def validate_schema_registry() -> None:
    ids = set()
    for contract in CONTRACTS:
        schema = schema_for(contract)
        Draft202012Validator.check_schema(schema)
        if schema["$id"] in ids: raise SchemaError("duplicate schema id")
        ids.add(schema["$id"])
