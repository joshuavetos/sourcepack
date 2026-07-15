from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from .git import run_git


class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


class DiffExitPolicy(StrEnum):
    WARN_OR_FAIL = "warn-or-fail"
    FAIL_ONLY = "fail-only"


@dataclass(frozen=True)
class PolicyRules:
    block_dependency_additions: bool = False
    protected_paths: tuple[str, ...] = field(default_factory=tuple)
    package_manager: str | None = None
    require_tests_for: tuple[str, ...] = field(default_factory=tuple)
    max_changed_lines: int | None = None
    block_secret_patterns: bool = False

    def enabled(self) -> bool:
        return (
            self.block_dependency_additions
            or bool(self.protected_paths)
            or self.package_manager is not None
            or bool(self.require_tests_for)
            or self.max_changed_lines is not None
            or self.block_secret_patterns
        )


@dataclass(frozen=True)
class PolicyConfig:
    schema_version: str = "sourcepack.policy.v1"
    strict_default: bool = True
    fail_on_warn_in_ci: bool = True
    ignored_paths: tuple[dict, ...] = field(default_factory=tuple)
    protected_paths: tuple[str, ...] = (".sourcepack/baseline/**", ".git/**")
    report_formats: tuple[str, ...] = ("json", "markdown", "html", "sarif")
    baseline_required_in_ci: bool = True
    prompt_context_authoritative: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rules: PolicyRules = field(default_factory=PolicyRules)


@dataclass(frozen=True)
class PolicyIgnoredEntryIssue:
    index: int
    warning: str
    entry: object


@dataclass(frozen=True)
class PolicyValidationResult:
    schema_version: str
    repo: str
    policy_path: str
    policy_present: bool
    valid: bool
    effective_ignored_paths: tuple[dict, ...] = field(default_factory=tuple)
    ignored_invalid_entries: tuple[PolicyIgnoredEntryIssue, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    effective_config: PolicyConfig = field(default_factory=PolicyConfig)

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "repo": self.repo,
            "policy_path": self.policy_path,
            "policy_present": self.policy_present,
            "valid": self.valid,
            "effective_ignored_paths": list(self.effective_ignored_paths),
            "ignored_invalid_entries": [
                {"index": item.index, "warning": item.warning, "entry": item.entry}
                for item in self.ignored_invalid_entries
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "effective_config": {
                "schema_version": self.effective_config.schema_version,
                "strict_default": self.effective_config.strict_default,
                "fail_on_warn_in_ci": self.effective_config.fail_on_warn_in_ci,
                "ignored_paths": list(self.effective_config.ignored_paths),
                "protected_paths": list(self.effective_config.protected_paths),
                "report_formats": list(self.effective_config.report_formats),
                "baseline_required_in_ci": self.effective_config.baseline_required_in_ci,
                "prompt_context_authoritative": self.effective_config.prompt_context_authoritative,
                "suppressible_ignored_path_finding_ids": sorted(SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS),
                "rules": {
                    "block_dependency_additions": self.effective_config.rules.block_dependency_additions,
                    "protected_paths": list(self.effective_config.rules.protected_paths),
                    "package_manager": self.effective_config.rules.package_manager,
                    "require_tests_for": list(self.effective_config.rules.require_tests_for),
                    "max_changed_lines": self.effective_config.rules.max_changed_lines,
                    "block_secret_patterns": self.effective_config.rules.block_secret_patterns,
                },
            },
        }


SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS = frozenset({"new_file"})
_RESERVED_POLICY_FIELDS = {
    "strict_default": "policy_config_reserved:strict_default",
    "fail_on_warn_in_ci": "policy_config_reserved:fail_on_warn_in_ci",
    "protected_paths": "policy_config_reserved:protected_paths",
    "report_formats": "policy_config_reserved:report_formats",
}


def _is_unsafe_policy_ignore_pattern(pattern: str) -> bool:
    return (
        pattern == ".git"
        or pattern.startswith(".git/")
        or pattern == ".sourcepack/baseline"
        or pattern.startswith(".sourcepack/baseline/")
    )


def normalize_policy_mode(value: PolicyMode | str | None) -> PolicyMode:
    if isinstance(value, PolicyMode):
        return value
    if value is None:
        return PolicyMode.LOCAL
    text = str(value).lower().strip()
    if text in {"ci", "--ci"}:
        return PolicyMode.CI
    if text in {"strict", "--strict"}:
        return PolicyMode.STRICT
    return PolicyMode.LOCAL


def commit_policy(verdict: str) -> str | None:
    if verdict == "WARN":
        return "allowed locally, blocked in strict mode."
    if verdict == "FAIL":
        return "blocked unless explicitly bypassed."
    return None


def normalize_diff_exit_policy(value: DiffExitPolicy | str | None) -> DiffExitPolicy | None:
    if isinstance(value, DiffExitPolicy):
        return value
    if value is None:
        return None
    text = str(value).lower().strip()
    if text == DiffExitPolicy.WARN_OR_FAIL.value:
        return DiffExitPolicy.WARN_OR_FAIL
    if text == DiffExitPolicy.FAIL_ONLY.value:
        return DiffExitPolicy.FAIL_ONLY
    raise ValueError(f"unknown diff exit policy: {value}")


def exit_code(verdict: str, mode: PolicyMode | str | None = None, exit_policy: DiffExitPolicy | str | None = None) -> int:
    policy = normalize_diff_exit_policy(exit_policy)
    if policy is DiffExitPolicy.FAIL_ONLY:
        return 1 if verdict == "FAIL" else 0
    if policy is DiffExitPolicy.WARN_OR_FAIL:
        return 0 if verdict == "PASS" else 1
    mode = normalize_policy_mode(mode)
    if verdict == "FAIL":
        return 1
    if verdict == "WARN" and mode in {PolicyMode.STRICT, PolicyMode.CI}:
        return 1
    return 0


def _normalize_policy_path(value: object) -> str | None:
    text = str(value or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or "\x00" in text:
        return None
    pure = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return pure.as_posix()


def policy_path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("/") + "/**")


def _parse_policy_rules(raw_rules: object, warnings: list[str]) -> PolicyRules:
    if raw_rules is None:
        return PolicyRules()
    if not isinstance(raw_rules, dict):
        warnings.append("policy_rules_invalid:rules_must_be_object")
        return PolicyRules()
    if not raw_rules:
        return PolicyRules()

    block_dependency_additions = False
    if "block_dependency_additions" in raw_rules:
        if raw_rules["block_dependency_additions"] is True:
            block_dependency_additions = True
        elif raw_rules["block_dependency_additions"] is not False:
            warnings.append("policy_rule_invalid:block_dependency_additions_must_be_boolean")

    protected_paths: list[str] = []
    if "protected_paths" in raw_rules:
        raw_protected = raw_rules["protected_paths"]
        if not isinstance(raw_protected, list):
            warnings.append("policy_rule_invalid:protected_paths_must_be_list")
        else:
            for value in raw_protected:
                norm = _normalize_policy_path(value)
                if norm:
                    protected_paths.append(norm)
                else:
                    warnings.append(f"policy_rule_invalid:protected_path:{value}")

    package_manager = None
    if "package_manager" in raw_rules:
        value = raw_rules["package_manager"]
        if isinstance(value, str) and value.strip().lower() == "pnpm":
            package_manager = "pnpm"
        elif value not in (None, ""):
            warnings.append(f"policy_rule_invalid:unsupported_package_manager:{value}")

    require_tests_for: list[str] = []
    if "require_tests_for" in raw_rules:
        raw_required = raw_rules["require_tests_for"]
        if not isinstance(raw_required, list):
            warnings.append("policy_rule_invalid:require_tests_for_must_be_list")
        else:
            for value in raw_required:
                norm = _normalize_policy_path(value)
                if norm:
                    require_tests_for.append(norm)
                else:
                    warnings.append(f"policy_rule_invalid:require_tests_for:{value}")

    max_changed_lines = None
    if "max_changed_lines" in raw_rules:
        value = raw_rules["max_changed_lines"]
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            max_changed_lines = value
        else:
            warnings.append("policy_rule_invalid:max_changed_lines_must_be_positive_integer")

    block_secret_patterns = False
    if "block_secret_patterns" in raw_rules:
        if raw_rules["block_secret_patterns"] is True:
            block_secret_patterns = True
        elif raw_rules["block_secret_patterns"] is not False:
            warnings.append("policy_rule_invalid:block_secret_patterns_must_be_boolean")

    return PolicyRules(
        block_dependency_additions=block_dependency_additions,
        protected_paths=tuple(protected_paths),
        package_manager=package_manager,
        require_tests_for=tuple(require_tests_for),
        max_changed_lines=max_changed_lines,
        block_secret_patterns=block_secret_patterns,
    )


def validate_policy_config(repo: str | Path) -> PolicyValidationResult:
    repo_path = Path(repo).resolve()
    path = repo_path / ".sourcepack" / "policy.json"
    if not path.exists():
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=False,
            valid=True,
        )
    warnings: list[str] = []
    errors: list[str] = []
    invalid_entries: list[PolicyIgnoredEntryIssue] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(f"policy_config_invalid_json:{exc.msg}:line={exc.lineno}:column={exc.colno}",),
        )
    except OSError as exc:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(f"policy_config_unreadable:{exc}",),
        )
    if not isinstance(raw, dict):
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=("policy_config_invalid:root_must_be_object",),
        )
    if raw.get("prompt_context_authoritative") is True:
        warnings.append("policy_config_ignored:prompt_context_authoritative")
    if raw.get("baseline_required_in_ci") is False:
        warnings.append("policy_config_ignored:baseline_required_in_ci_false")
    for field, warning in _RESERVED_POLICY_FIELDS.items():
        if field in raw:
            warnings.append(warning)
    ignored: list[dict] = []
    raw_ignored = raw.get("ignored_paths", [])
    if not isinstance(raw_ignored, list):
        warnings.append("policy_ignore_invalid:ignored_paths_must_be_list")
        raw_ignored = []
    for index, item in enumerate(raw_ignored):
        warning = None
        if not isinstance(item, dict):
            warning = "policy_ignore_invalid:not_object"
        else:
            pattern = _normalize_policy_path(item.get("pattern"))
            reason = str(item.get("reason") or "").strip()
            if not pattern or not reason:
                warning = "policy_ignore_invalid:pattern_and_reason_required"
            elif _is_unsafe_policy_ignore_pattern(pattern):
                warning = f"policy_ignore_unsafe:{pattern}"
            else:
                ignored.append({"pattern": pattern, "reason": reason})
        if warning:
            warnings.append(warning)
            invalid_entries.append(PolicyIgnoredEntryIssue(index=index, warning=warning, entry=item))
    raw_formats = raw.get("report_formats", [])
    if "report_formats" in raw and not isinstance(raw_formats, list):
        warnings.append("policy_report_format_ignored:report_formats_must_be_list")
    elif isinstance(raw_formats, list):
        for value in raw_formats:
            fmt = str(value).lower().strip()
            if fmt not in {"json", "markdown", "html", "sarif"}:
                warnings.append(f"policy_report_format_ignored:{fmt}")
    rules = _parse_policy_rules(raw.get("rules"), warnings)
    config = PolicyConfig(ignored_paths=tuple(ignored), warnings=tuple(warnings), rules=rules)
    return PolicyValidationResult(
        schema_version="sourcepack.policy.validation.v1",
        repo=str(repo_path),
        policy_path=str(path),
        policy_present=True,
        valid=True,
        effective_ignored_paths=tuple(ignored),
        ignored_invalid_entries=tuple(invalid_entries),
        warnings=tuple(warnings),
        effective_config=config,
    )


def load_policy_config(repo: str | Path) -> PolicyConfig:
    path = Path(repo) / ".sourcepack" / "policy.json"
    if not path.exists():
        return PolicyConfig()
    warnings: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PolicyConfig(warnings=(f"policy_config_unreadable:{exc}",))
    if not isinstance(raw, dict):
        return PolicyConfig(warnings=("policy_config_invalid:root_must_be_object",))
    if raw.get("prompt_context_authoritative") is True:
        warnings.append("policy_config_ignored:prompt_context_authoritative")
    if raw.get("baseline_required_in_ci") is False:
        warnings.append("policy_config_ignored:baseline_required_in_ci_false")
    for field, warning in _RESERVED_POLICY_FIELDS.items():
        if field in raw:
            warnings.append(warning)
    ignored: list[dict] = []
    for item in raw.get("ignored_paths", []) if isinstance(raw.get("ignored_paths", []), list) else []:
        if not isinstance(item, dict):
            warnings.append("policy_ignore_invalid:not_object")
            continue
        pattern = _normalize_policy_path(item.get("pattern"))
        reason = str(item.get("reason") or "").strip()
        if not pattern or not reason:
            warnings.append("policy_ignore_invalid:pattern_and_reason_required")
            continue
        if _is_unsafe_policy_ignore_pattern(pattern):
            warnings.append(f"policy_ignore_unsafe:{pattern}")
            continue
        ignored.append({"pattern": pattern, "reason": reason})
    protected = []
    for value in raw.get("protected_paths", []) if isinstance(raw.get("protected_paths", []), list) else []:
        norm = _normalize_policy_path(value)
        if norm:
            protected.append(norm)
    formats = []
    for value in raw.get("report_formats", []) if isinstance(raw.get("report_formats", []), list) else []:
        fmt = str(value).lower().strip()
        if fmt in {"json", "markdown", "html", "sarif"}:
            formats.append(fmt)
        else:
            warnings.append(f"policy_report_format_ignored:{fmt}")
    rules = _parse_policy_rules(raw.get("rules"), warnings)
    return PolicyConfig(
        strict_default=PolicyConfig.strict_default,
        fail_on_warn_in_ci=PolicyConfig.fail_on_warn_in_ci,
        ignored_paths=tuple(ignored),
        protected_paths=PolicyConfig.protected_paths,
        report_formats=PolicyConfig.report_formats,
        warnings=tuple(warnings),
        rules=rules,
    )


def finding_ignored_by_policy(finding: dict, config: PolicyConfig) -> dict | None:
    fid = str(finding.get("id") or "")
    if fid not in SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS:
        return None
    path = _normalize_policy_path(finding.get("path"))
    if not path:
        return None
    for item in config.ignored_paths:
        pattern = item["pattern"]
        if _is_unsafe_policy_ignore_pattern(pattern):
            continue
        if policy_path_matches(path, pattern):
            return {"pattern": pattern, "reason": item["reason"], "path": path}
    return None

ORG_POLICY_SCHEMA_VERSION = "sourcepack.org_policy.v1"
EFFECTIVE_POLICY_SCHEMA_VERSION = "sourcepack.effective_policy.v1"
_POLICY_RULE_NAMES = (
    "block_dependency_additions",
    "block_secret_patterns",
    "protected_paths",
    "require_tests_for",
    "max_changed_lines",
    "package_manager",
)


def _sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _content_identity(data: object | None) -> str | None:
    if data is None:
        return None
    return "sha256:" + _sha256_bytes(_canonical_json(data).encode("utf-8"))



def _canonical_repository_root(start: str | Path) -> tuple[Path | None, str | None]:
    requested = Path(start).resolve()
    cp = run_git(requested, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0 or not cp.stdout.strip():
        return None, "repository_root_unresolved"
    return Path(cp.stdout.strip()).resolve(), None

def _is_relative_to_path(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_json_file(path: Path) -> tuple[object | None, str | None, str | None]:
    try:
        b = path.read_bytes()
    except OSError as exc:
        return None, None, f"unreadable:{exc}"
    try:
        return json.loads(b.decode("utf-8")), _sha256_bytes(b), None
    except UnicodeDecodeError as exc:
        return None, _sha256_bytes(b), f"malformed_json:utf8:{exc}"
    except json.JSONDecodeError as exc:
        return None, _sha256_bytes(b), f"malformed_json:{exc.msg}:line={exc.lineno}:column={exc.colno}"


def _validate_rule_value(rule: str, value: object, source: str) -> tuple[object | None, str | None]:
    if rule in {"block_dependency_additions", "block_secret_patterns"}:
        if isinstance(value, bool):
            return value, None
        return None, f"{source}_rule_invalid:{rule}_must_be_boolean"
    if rule in {"protected_paths", "require_tests_for"}:
        if not isinstance(value, list):
            return None, f"{source}_rule_invalid:{rule}_must_be_list"
        normalized = []
        for item in value:
            norm = _normalize_policy_path(item)
            if not norm:
                return None, f"{source}_rule_invalid:{rule}:{item}"
            normalized.append(norm)
        return tuple(sorted(set(normalized))), None
    if rule == "max_changed_lines":
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value, None
        return None, f"{source}_rule_invalid:max_changed_lines_must_be_positive_integer"
    if rule == "package_manager":
        if isinstance(value, str) and value.strip():
            return value.strip().lower(), None
        return None, f"{source}_rule_invalid:package_manager_must_be_string"
    return None, f"{source}_rule_unknown:{rule}"


def _rules_from_policy(raw_rules: object, source: str, *, fail_unknown: bool) -> tuple[dict, list[str]]:
    errors: list[str] = []
    if raw_rules is None:
        return {}, errors
    if not isinstance(raw_rules, dict):
        return {}, [f"{source}_rules_invalid:rules_must_be_object"]
    out = {}
    for rule, value in raw_rules.items():
        if rule not in _POLICY_RULE_NAMES:
            if fail_unknown:
                errors.append(f"{source}_rule_unknown:{rule}")
            continue
        parsed, err = _validate_rule_value(rule, value, source)
        if err:
            errors.append(err)
        else:
            out[rule] = parsed
    return out, errors


def _repo_rules_from_validation(validation: PolicyValidationResult) -> dict:
    rules = validation.effective_config.rules
    out = {}
    if rules.block_dependency_additions:
        out["block_dependency_additions"] = True
    if rules.protected_paths:
        out["protected_paths"] = tuple(sorted(set(rules.protected_paths)))
    if rules.package_manager is not None:
        out["package_manager"] = rules.package_manager
    if rules.require_tests_for:
        out["require_tests_for"] = tuple(sorted(set(rules.require_tests_for)))
    if rules.max_changed_lines is not None:
        out["max_changed_lines"] = rules.max_changed_lines
    if rules.block_secret_patterns:
        out["block_secret_patterns"] = True
    return out


def _repo_rules_from_file(path: Path) -> tuple[dict, list[str], object | None, str | None]:
    raw, byte_hash, err = _read_json_file(path)
    if err or not isinstance(raw, dict):
        return {}, [], raw, byte_hash
    rules, errors = _rules_from_policy(raw.get("rules", {}), "repository_policy", fail_unknown=False)
    # Repository-local policy validation historically warns about unsupported package
    # managers instead of failing. Policy resolution must still see the raw non-empty
    # string so organization equality/conflict authority cannot be bypassed.
    raw_rules = raw.get("rules", {})
    if isinstance(raw_rules, dict) and "package_manager" in raw_rules and isinstance(raw_rules["package_manager"], str) and raw_rules["package_manager"].strip():
        rules["package_manager"] = raw_rules["package_manager"].strip().lower()
    return rules, errors, raw, byte_hash


def resolve_effective_policy(repo: str | Path, org_policy: str | Path | None = None, org_policy_mode: str = "optional") -> dict:
    requested_path = Path(repo).resolve()
    repo_root, repo_root_error = _canonical_repository_root(requested_path)
    errors: list[str] = []
    conflicts: list[dict] = []
    rejected: list[dict] = []
    if repo_root_error is not None or repo_root is None:
        repo_root = requested_path
        errors.append(repo_root_error or "repository_root_unresolved")
    org_status = "not_supplied"
    org_id = None
    org_hash = None
    org_rules: dict = {}
    org_source = {"supplied": org_policy is not None, "path": str(org_policy) if org_policy is not None else None}
    if org_policy_mode not in {"optional", "required"}:
        raise ValueError("org_policy_mode must be optional or required")
    if org_policy is None:
        if org_policy_mode == "required":
            org_status = "required_but_missing"
            errors.append("org_policy_required_but_missing")
    else:
        supplied = Path(org_policy)
        try:
            org_resolved = supplied.resolve(strict=True)
        except FileNotFoundError:
            org_status = "invalid"
            errors.append("org_policy_missing")
            org_resolved = None
        except OSError as exc:
            org_status = "invalid"
            errors.append(f"org_policy_unreadable:{exc}")
            org_resolved = None
        if org_resolved is not None:
            org_source["resolved_path"] = str(org_resolved)
            if _is_relative_to_path(org_resolved, repo_root):
                org_status = "trust_boundary_violation"
                errors.append("org_policy_trust_boundary_violation:inside_repository")
            elif org_resolved.is_dir():
                org_status = "invalid"
                errors.append("org_policy_is_directory")
            elif not org_resolved.is_file():
                org_status = "invalid"
                errors.append("org_policy_not_file")
            else:
                raw_org, org_hash, err = _read_json_file(org_resolved)
                if err:
                    org_status = "invalid"
                    errors.append(f"org_policy_{err}")
                elif not isinstance(raw_org, dict):
                    org_status = "invalid"
                    errors.append("org_policy_invalid:root_must_be_object")
                elif raw_org.get("schema_version") != ORG_POLICY_SCHEMA_VERSION:
                    org_status = "invalid"
                    errors.append("org_policy_unsupported_schema")
                else:
                    org_id = raw_org.get("policy_id")
                    if not isinstance(org_id, str) or not org_id.strip():
                        org_status = "invalid"; errors.append("org_policy_invalid:policy_id_required")
                    else:
                        org_hash = _content_identity(raw_org)
                        org_rules, rule_errors = _rules_from_policy(raw_org.get("rules", {}), "org_policy", fail_unknown=True)
                        if rule_errors:
                            org_status = "invalid"; errors.extend(rule_errors)
                        else:
                            org_status = "loaded"
    repo_validation = validate_policy_config(repo_root) if repo_root_error is None else PolicyValidationResult(
        schema_version="sourcepack.policy.validation.v1",
        repo=str(requested_path),
        policy_path=str(requested_path / ".sourcepack" / "policy.json"),
        policy_present=False,
        valid=False,
        errors=(repo_root_error or "repository_root_unresolved",),
    )
    repo_rules = _repo_rules_from_validation(repo_validation) if repo_validation.valid else {}
    repo_hash = None
    repo_path = Path(repo_validation.policy_path)
    if repo_validation.policy_present and repo_path.exists() and repo_path.is_file():
        parsed_repo_rules, repo_rule_errors, raw_repo_policy, repo_byte_hash = _repo_rules_from_file(repo_path)
        repo_hash = _content_identity(raw_repo_policy) if raw_repo_policy is not None else ("sha256:" + repo_byte_hash if repo_byte_hash else None)
        if repo_validation.valid:
            repo_rules = parsed_repo_rules
        errors.extend(repo_rule_errors)
    if not repo_validation.valid:
        for e in repo_validation.errors:
            prefixed = f"repository_{e}"
            if prefixed not in errors:
                errors.append(prefixed)
    effective = {}
    rule_results = {}
    strengthen = []
    for rule in _POLICY_RULE_NAMES:
        o_present = rule in org_rules; r_present = rule in repo_rules
        o = org_rules.get(rule); r = repo_rules.get(rule)
        status = "absent"; method = "none"; eff = None
        if rule in {"block_dependency_additions", "block_secret_patterns"}:
            method = "boolean_false_less_than_true_or"
            eff = bool(o) or bool(r)
            if o_present or r_present: effective[rule] = eff
            if o_present and r_present and o is True and r is False:
                status = "rejected_weakening"; rejected.append({"rule": rule, "organization_value": o, "repository_value": r, "comparison_method": method, "reason": "repository false weakens organization true"})
            elif r_present and (not o_present or (o is False and r is True)):
                status = "strengthening"; strengthen.append(rule)
            elif o_present or r_present: status = "compatible"
        elif rule in {"protected_paths", "require_tests_for"}:
            method = "normalized_set_union"
            union = tuple(sorted(set(o or ()) | set(r or ())))
            if union: effective[rule] = list(union)
            status = "compatible" if (o_present or r_present) else "absent"
            if r_present and set(r or ()) - set(o or ()): status = "strengthening"; strengthen.append(rule)
        elif rule == "max_changed_lines":
            method = "lower_positive_integer_is_stricter_absent_is_no_limit"
            if o_present and r_present:
                eff = min(o, r); effective[rule] = eff
                if r > o:
                    status = "rejected_weakening"; rejected.append({"rule": rule, "organization_value": o, "repository_value": r, "comparison_method": method, "reason": "repository maximum is higher than organization maximum"})
                elif r < o: status = "strengthening"; strengthen.append(rule)
                else: status = "compatible"
            elif o_present: effective[rule] = o; status = "compatible"
            elif r_present: effective[rule] = r; status = "strengthening"; strengthen.append(rule)
        elif rule == "package_manager":
            method = "string_equality_no_ordering"
            if o_present and r_present and o != r:
                status = "conflict"; conflicts.append({"rule": rule, "organization_value": o, "repository_value": r, "comparison_method": method, "reason": "differing non-null package managers"})
            elif o_present or r_present:
                effective[rule] = o if o_present else r; status = "compatible" if o_present else "strengthening"
                if r_present and not o_present: strengthen.append(rule)
        rule_results[rule] = {"organization_constraint": o if not isinstance(o, tuple) else list(o), "repository_contribution": r if not isinstance(r, tuple) else list(r), "effective_value": effective.get(rule), "provenance": _rule_provenance(rule, o_present, r_present, o, r, effective.get(rule)), "comparison_method": method, "compatibility_status": status}
    if rejected: errors.append("repository_policy_weakening_attempt")
    if conflicts: errors.append("policy_conflict")
    verdict = "FAIL" if errors else "PASS"
    identity_material = {"schema_version": EFFECTIVE_POLICY_SCHEMA_VERSION, "org_policy_mode": org_policy_mode, "org_policy_status": org_status, "org_policy_hash": org_hash, "repository_policy_hash": repo_hash, "organization_policy_id": org_id, "effective_policy": effective, "rules": rule_results, "rejected_weakening_attempts": rejected, "conflicts": conflicts, "errors": errors}
    eid = "epol_" + _sha256_bytes(_canonical_json(identity_material).encode("utf-8"))[:32]
    return {"schema_version": EFFECTIVE_POLICY_SCHEMA_VERSION, "resolution_status": verdict, "organization_policy_mode": org_policy_mode, "organization_policy_status": org_status, "organization_policy_source": org_source, "organization_policy_id": org_id, "organization_policy_hash": org_hash, "repository_policy_source": {"path": ".sourcepack/policy.json", "status": "loaded" if repo_validation.policy_present and repo_validation.valid else "absent" if not repo_validation.policy_present else "invalid"}, "repository_policy_hash": repo_hash, "effective_policy": effective, "rules": rule_results, "strengthening_contributions": sorted(set(strengthen)), "rejected_weakening_attempts": rejected, "conflicts": conflicts, "errors": errors, "effective_policy_id": eid}


def _rule_provenance(rule: str, o_present: bool, r_present: bool, o: object, r: object, eff: object) -> dict:
    if rule in {"protected_paths", "require_tests_for"}:
        vals = sorted(set(o or ()) | set(r or ()))
        return {v: [s for s, present in (("organization", o_present and v in set(o or ())), ("repository", r_present and v in set(r or ()))) if present] for v in vals}
    return {"sources": [s for s, present in (("organization", o_present), ("repository", r_present)) if present]}
