"""Deterministic, baseline-owned architecture contract evaluation.

The v1 substrate intentionally supports only Python forbidden direct imports.
It consumes packet contents rather than independently discovering repository
state, and proposed contract bytes never become authority for the current
review.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any

CONTRACT_PATH = "sourcepack.architecture.json"
STATE_ARTIFACT = "architecture_state.json"
CONTRACT_VERSION = "architecture_contract.v1"
STATE_VERSION = "architecture_state.v1"
RULE_STATES = {"valid", "preexisting_violation", "drifted", "unverifiable", "retired"}


class ArchitectureContractError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArchitectureContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(value: object, name: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - keys:
        raise ArchitectureContractError(f"{name} must be an object with only {sorted(keys)}")
    return value


def validate_contract(value: object) -> dict[str, Any]:
    root = _object(value, "contract", {"schema_version", "coverage", "layers", "rules"})
    if root.get("schema_version") != CONTRACT_VERSION:
        raise ArchitectureContractError(f"schema_version must be {CONTRACT_VERSION}")
    coverage = _object(root.get("coverage"), "coverage", {"exhaustive", "paths"})
    if not isinstance(coverage.get("exhaustive"), bool):
        raise ArchitectureContractError("coverage.exhaustive must be boolean")
    paths = coverage.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p and "\\" not in p and not p.startswith("/") and ".." not in PurePosixPath(p).parts for p in paths):
        raise ArchitectureContractError("coverage.paths must contain safe repository-relative globs")
    layers = root.get("layers")
    if not isinstance(layers, list):
        raise ArchitectureContractError("layers must be an array")
    layer_ids: set[str] = set()
    for index, raw in enumerate(layers):
        layer = _object(raw, f"layers[{index}]", {"id", "paths", "must_match"})
        lid = layer.get("id")
        if not isinstance(lid, str) or not lid or lid in layer_ids:
            raise ArchitectureContractError("layer IDs must be unique nonempty strings")
        layer_ids.add(lid)
        lpaths = layer.get("paths")
        if not isinstance(lpaths, list) or not lpaths or not all(isinstance(p, str) and p and "\\" not in p and not p.startswith("/") and ".." not in PurePosixPath(p).parts for p in lpaths):
            raise ArchitectureContractError(f"layer {lid} paths must contain safe globs")
        if not isinstance(layer.get("must_match"), bool):
            raise ArchitectureContractError(f"layer {lid} must_match must be boolean")
    rules = root.get("rules")
    if not isinstance(rules, list):
        raise ArchitectureContractError("rules must be an array")
    rule_ids: set[str] = set()
    replacements: set[str] = set()
    for index, raw in enumerate(rules):
        rule = _object(raw, f"rules[{index}]", {"id", "type", "from", "to", "reachability", "status", "replaced_by", "replaces"})
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid or rid in rule_ids:
            raise ArchitectureContractError("rule IDs must be unique nonempty strings")
        rule_ids.add(rid)
        if rule.get("type") != "forbidden_import" or rule.get("reachability") != "direct":
            raise ArchitectureContractError(f"rule {rid} must declare forbidden_import with direct reachability")
        if rule.get("from") not in layer_ids or rule.get("to") not in layer_ids:
            raise ArchitectureContractError(f"rule {rid} references an unknown layer")
        status = rule.get("status", "active")
        if status not in {"active", "retired"}:
            raise ArchitectureContractError(f"rule {rid} status must be active or retired")
        replaced_by = rule.get("replaced_by")
        replaces = rule.get("replaces", [])
        if replaced_by is not None and (status != "retired" or not isinstance(replaced_by, str) or not replaced_by):
            raise ArchitectureContractError(f"rule {rid} replaced_by requires an explicit retired rule")
        if not isinstance(replaces, list) or not all(isinstance(item, str) and item for item in replaces):
            raise ArchitectureContractError(f"rule {rid} replaces must be an array of rule IDs")
        replacements.update(replaces)
    for rule in rules:
        if rule.get("replaced_by") is not None:
            successor = next((r for r in rules if r.get("id") == rule["replaced_by"]), None)
            if successor is None or rule["id"] not in successor.get("replaces", []):
                raise ArchitectureContractError(f"rule {rule['id']} replacement must be bidirectional")
    return root


def load_contract(contents: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    raw = contents.get(CONTRACT_PATH)
    if raw is None:
        return None, None
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        return validate_contract(value), None
    except (json.JSONDecodeError, ArchitectureContractError) as exc:
        return None, str(exc)


def _matches(path: str, patterns: list[str]) -> bool:
    # Pure fnmatch does not make ** match a zero-directory prefix. Supporting
    # both spellings keeps repository globs deterministic and unsurprising.
    return any(fnmatch.fnmatchcase(path, pattern) or ("/**/" in pattern and fnmatch.fnmatchcase(path, pattern.replace("/**/", "/"))) for pattern in patterns)


def classify(contract: dict[str, Any], paths: set[str]) -> tuple[dict[str, str], list[str], list[str]]:
    layers: dict[str, str] = {}
    ambiguous: list[str] = []
    uncovered: list[str] = []
    coverage = contract["coverage"]
    for path in sorted(paths):
        if not _matches(path, coverage["paths"]):
            continue
        matched = [layer["id"] for layer in contract["layers"] if _matches(path, layer["paths"])]
        if len(matched) == 1:
            layers[path] = matched[0]
        elif len(matched) > 1:
            ambiguous.append(path)
        elif coverage["exhaustive"]:
            uncovered.append(path)
    return layers, ambiguous, uncovered


def _module_candidates(module: str) -> tuple[str, ...]:
    rel = module.replace(".", "/")
    return (f"{rel}.py", f"{rel}/__init__.py", f"src/{rel}.py", f"src/{rel}/__init__.py")


def _resolved_repository_target(modules: list[str], known: set[str]) -> str | None:
    matches = {candidate for module in modules for candidate in _module_candidates(module) if candidate in known}
    return next(iter(matches)) if len(matches) == 1 else None


def _relative_modules(path: str, node: ast.ImportFrom) -> list[str] | None:
    module_parts = list(PurePosixPath(path).with_suffix("").parts)
    package = module_parts if module_parts[-1] == "__init__" else module_parts[:-1]
    if package and package[-1] == "__init__":
        package = package[:-1]
    ascend = node.level - 1
    if ascend > len(package):
        return None
    base = package[: len(package) - ascend] if ascend else package
    if node.module:
        base.extend(node.module.split("."))
    modules: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            modules.append(".".join(base))
        else:
            modules.extend((".".join([*base, alias.name]), ".".join(base)))
    return [module for module in modules if module]


def _imports(path: str, text: str, known: set[str]) -> tuple[list[tuple[str, str]], int, bool]:
    try:
        tree = ast.parse(text, filename=path)
    except (SyntaxError, ValueError):
        return [], 0, False
    edges: list[tuple[str, str]] = []
    unresolved = 0
    for node in ast.walk(tree):
        modules: list[tuple[list[str], str]] = []
        if isinstance(node, ast.Import):
            modules.extend(([alias.name], "resolved_static") for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(([node.module, *[f"{node.module}.{alias.name}" for alias in node.names]], "resolved_static"))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            relative = _relative_modules(path, node)
            if relative is None:
                unresolved += 1
            else:
                modules.append((relative, "resolved_static"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib" and node.func.attr == "import_module":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                modules.append(([node.args[0].value], "resolved_literal"))
            else:
                unresolved += 1
        for module_options, resolution in modules:
            target = _resolved_repository_target(module_options, known)
            if target is not None:
                edges.append((target, resolution))
            elif isinstance(node, ast.ImportFrom) and node.level > 0:
                unresolved += 1
    return sorted(set(edges)), unresolved, True


def _instance(rule_id: str, source: str, target: str, resolution: str) -> dict[str, str]:
    basis = {"rule_id": rule_id, "source_path": source, "target_path": target, "relationship_type": "direct_import"}
    identity = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:32]
    return {"violation_id": f"archv_{identity}", **basis, "resolution": resolution}


def build_state(contents: dict[str, str], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    contract, error = load_contract(contents)
    prior_by_id = {rule.get("rule_id"): rule for rule in (previous or {}).get("rules", []) if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str)}
    contract_present = CONTRACT_PATH in contents
    state: dict[str, Any] = {"schema_version": STATE_VERSION, "contract_present": contract_present, "contract_valid": contract is not None or not contract_present, "contract_error": error, "rules": []}
    if contract is None:
        if not contract_present and prior_by_id:
            for rid, prior in sorted(prior_by_id.items()):
                unresolved = list(prior.get("unresolved_history", []))
                if prior.get("current_status") in {"drifted", "unverifiable", "preexisting_violation"}:
                    marker = {"event": "retired_with_unresolved_state", "prior_status": prior.get("current_status")}
                    if marker not in unresolved:
                        unresolved.append(marker)
                state["rules"].append({
                    "rule_id": rid, "current_status": "retired",
                    "current_violation_instances": list(prior.get("current_violation_instances", [])),
                    "current_verifiability": dict(prior.get("current_verifiability", {"complete": False})),
                    "last_valid_violation_instances": list(prior.get("last_valid_violation_instances", [])),
                    "last_valid_verifiability": dict(prior.get("last_valid_verifiability", {"complete": False})),
                    "unresolved_history": unresolved,
                })
        return state
    py_paths = {path for path in contents if path.endswith(".py")}
    classes, ambiguous, uncovered = classify(contract, py_paths)
    layer_matches = {layer["id"]: sorted(path for path, lid in classes.items() if lid == layer["id"]) for layer in contract["layers"]}
    parsed: dict[str, tuple[list[tuple[str, str]], int, bool]] = {path: _imports(path, contents[path], py_paths) for path in sorted(classes)}
    for rule in sorted(contract["rules"], key=lambda item: item["id"]):
        rid = rule["id"]
        violations: list[dict[str, str]] = []
        relevant_unresolved: list[str] = []
        drift_reasons = [f"layer:{lid}:must_match" for lid in (rule["from"], rule["to"]) if next(layer for layer in contract["layers"] if layer["id"] == lid)["must_match"] and not layer_matches[lid]]
        for source in layer_matches[rule["from"]]:
            edges, unresolved_count, parsed_ok = parsed[source]
            if not parsed_ok or unresolved_count:
                relevant_unresolved.append(source)
            for target, resolution in edges:
                if classes.get(target) == rule["to"]:
                    violations.append(_instance(rid, source, target, resolution))
        relevant_ambiguous = [path for path in ambiguous if any(_matches(path, layer["paths"]) for layer in contract["layers"] if layer["id"] in {rule["from"], rule["to"]})]
        # Uncovered exhaustive paths have no declared layer and therefore do
        # not, by themselves, make every unrelated relationship rule drift.
        if rule.get("status", "active") == "retired":
            current_status = "retired"
        elif drift_reasons or relevant_ambiguous:
            current_status = "drifted"
        elif relevant_unresolved:
            current_status = "unverifiable"
        elif violations:
            current_status = "preexisting_violation"
        else:
            current_status = "valid"
        prior = prior_by_id.get(rid, {})
        if current_status in {"valid", "preexisting_violation"}:
            last_valid = violations
        else:
            last_valid = prior.get("last_valid_violation_instances", [])
        state["rules"].append({
            "rule_id": rid, "current_status": current_status,
            "current_violation_instances": sorted(violations, key=lambda item: item["violation_id"]),
            "current_verifiability": {"complete": current_status not in {"drifted", "unverifiable"}, "unresolved_paths": sorted(set(relevant_unresolved)), "drift_reasons": sorted(set(drift_reasons + (["ambiguous_classification"] if relevant_ambiguous else [])))},
            "last_valid_violation_instances": last_valid,
            "last_valid_verifiability": prior.get("last_valid_verifiability", {"complete": True}) if current_status in {"drifted", "unverifiable"} else {"complete": True},
            "unresolved_history": prior.get("unresolved_history", []),
        })
    current_ids = {rule["rule_id"] for rule in state["rules"]}
    for rid, prior in sorted(prior_by_id.items()):
        if rid in current_ids:
            continue
        unresolved = list(prior.get("unresolved_history", []))
        if prior.get("current_status") in {"drifted", "unverifiable", "preexisting_violation"}:
            marker = {"event": "retired_with_unresolved_state", "prior_status": prior.get("current_status")}
            if marker not in unresolved:
                unresolved.append(marker)
        state["rules"].append({
            "rule_id": rid,
            "current_status": "retired",
            "current_violation_instances": list(prior.get("current_violation_instances", [])),
            "current_verifiability": dict(prior.get("current_verifiability", {"complete": False})),
            "last_valid_violation_instances": list(prior.get("last_valid_violation_instances", [])),
            "last_valid_verifiability": dict(prior.get("last_valid_verifiability", {"complete": False})),
            "unresolved_history": unresolved,
        })
    state["rules"].sort(key=lambda item: item["rule_id"])
    state["classification"] = classes
    state["ambiguous_paths"] = ambiguous
    state["uncovered_paths"] = uncovered
    state["contract"] = contract
    state["contract_sha256"] = hashlib.sha256(contents[CONTRACT_PATH].encode()).hexdigest()
    return state


def evaluate_change(
    before_contents: dict[str, str],
    after_contents: dict[str, str],
    baseline_state: dict[str, Any],
    *,
    path_transitions: list[dict[str, Any]] | None = None,
    projection_failures: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return normalized-finding inputs and backend-owned architecture evidence."""
    findings: list[dict[str, Any]] = []
    if not baseline_state.get("contract_present"):
        carried = baseline_state.get("rules", [])
        return findings, {"status": "retired" if carried else "not_declared", "rules": carried}
    if not baseline_state.get("contract_valid") or not isinstance(baseline_state.get("contract"), dict):
        return [{"id": "architecture_authority_corrupt", "severity": "error", "category": "architecture", "message": "Accepted baseline architecture authority is corrupt or unavailable."}], {"status": "unavailable", "rules": []}
    # Always use the accepted contract, including when proposed bytes edit it.
    authority_contents = dict(after_contents)
    authority_contents[CONTRACT_PATH] = before_contents[CONTRACT_PATH]
    after_state = build_state(authority_contents, baseline_state)
    before_rules = {r["rule_id"]: r for r in baseline_state["rules"]}
    after_rules = {r["rule_id"]: r for r in after_state["rules"]}
    for rid in sorted(before_rules):
        before = before_rules[rid]; after = after_rules[rid]
        pre_status = before["current_status"]; post_status = after["current_status"]
        if pre_status == "retired":
            continue
        failed_sources = [path for path in projection_failures or [] if baseline_state.get("classification", {}).get(path) == next((rule["from"] for rule in baseline_state["contract"]["rules"] if rule["id"] == rid), None)]
        if failed_sources or CONTRACT_PATH in (projection_failures or []):
            findings.append({"id": "architecture_rule_unverifiable", "severity": "warn", "category": "architecture", "message": f"The proposed state for architecture rule {rid} could not be projected completely.", "evidence": ", ".join(sorted(failed_sources or [CONTRACT_PATH]))})
            continue
        if pre_status in {"drifted", "unverifiable"}:
            findings.append({"id": "architecture_contract_drift" if pre_status == "drifted" else "architecture_rule_unverifiable", "severity": "warn", "category": "architecture", "message": f"Architecture rule {rid} entered review as {pre_status} and has no blocking authority for this review.", "evidence": rid})
            if post_status in {"valid", "preexisting_violation"}:
                known = {v["violation_id"] for v in before.get("last_valid_violation_instances", [])}
                for violation in after["current_violation_instances"]:
                    if violation["violation_id"] not in known:
                        findings.append({"id": "architecture_violation_detected_after_drift", "severity": "warn", "category": "architecture", "message": f"Rule {rid} can again be evaluated and a violation appeared after its last valid state; the introducing patch is unknown.", "path": violation["source_path"], "evidence": violation["violation_id"]})
            continue
        if post_status == "drifted":
            findings.append({"id": "architecture_contract_drift", "severity": "warn", "category": "architecture", "message": f"The proposed change makes architecture rule {rid} drifted.", "evidence": rid})
            continue
        if post_status == "unverifiable":
            findings.append({"id": "architecture_rule_unverifiable", "severity": "warn", "category": "architecture", "message": f"The proposed change makes architecture rule {rid} unverifiable.", "evidence": rid})
            if before["current_verifiability"].get("complete"):
                findings.append({"id": "architecture_verifiability_reduced", "severity": "warn", "category": "architecture", "message": f"The proposed change reduced verifiability for architecture rule {rid}.", "evidence": rid})
            continue
        old = {v["violation_id"] for v in before["current_violation_instances"]}
        for violation in after["current_violation_instances"]:
            if violation["violation_id"] not in old:
                findings.append({"id": "architecture_forbidden_import", "severity": "error", "category": "architecture", "message": f"Rule {rid} forbids this direct import from {violation['source_path']} to {violation['target_path']}.", "path": violation["source_path"], "evidence": violation["violation_id"]})
    before_classes = baseline_state.get("classification", {})
    after_classes = after_state.get("classification", {})
    for path, old_layer in sorted(before_classes.items()):
        if path in after_contents and after_classes.get(path) != old_layer:
            findings.append({"id": "architecture_scope_changed", "severity": "warn", "category": "architecture", "message": f"{path} changed architecture classification from {old_layer} to {after_classes.get(path, 'undeclared')}.", "path": path, "evidence": old_layer})
    for transition in path_transitions or []:
        old_path, new_path = transition.get("old_path"), transition.get("new_path")
        if transition.get("deleted") or transition.get("new_file") or not old_path or not new_path or old_path == new_path:
            continue
        old_layer = before_classes.get(old_path)
        if old_layer is not None and after_classes.get(new_path) != old_layer:
            findings.append({"id": "architecture_scope_changed", "severity": "warn", "category": "architecture", "message": f"{old_path} moved to {new_path} and changed architecture classification from {old_layer} to {after_classes.get(new_path, 'undeclared')}.", "path": new_path, "evidence": old_path})
    proposed, proposed_error = load_contract(after_contents)
    if after_contents.get(CONTRACT_PATH) != before_contents.get(CONTRACT_PATH):
        findings.append({"id": "architecture_contract_changed", "severity": "warn", "category": "architecture", "message": "The proposed architecture contract did not authorize this review; accepted pre-change authority was used.", "path": CONTRACT_PATH, "evidence": proposed_error or "proposed contract differs"})
        proposed_rules = {r["id"]: r for r in proposed.get("rules", [])} if proposed else {}
        for rid, old in before_rules.items():
            if rid not in proposed_rules:
                unresolved = old["current_status"] in {"drifted", "unverifiable", "preexisting_violation"} or bool(old.get("unresolved_history"))
                findings.append({"id": "architecture_rule_retirement_unresolved" if unresolved else "architecture_rule_retired", "severity": "warn" if unresolved else "info", "category": "architecture", "message": f"Architecture rule {rid} was removed from proposed authority{' with unresolved history' if unresolved else ''}.", "evidence": rid})
            elif proposed_rules[rid].get("status") == "retired":
                unresolved = old["current_status"] != "valid" or bool(old.get("unresolved_history"))
                findings.append({"id": "architecture_rule_retirement_unresolved" if unresolved else "architecture_rule_retired", "severity": "warn" if unresolved else "info", "category": "architecture", "message": f"Architecture rule {rid} is proposed for retirement{' with unresolved history' if unresolved else ''}.", "evidence": rid})
    return findings, {"status": "evaluated", "authority": "accepted_prechange_baseline", "rules": after_state["rules"], "contract_change_valid": proposed_error is None, "contract_change_error": proposed_error}
