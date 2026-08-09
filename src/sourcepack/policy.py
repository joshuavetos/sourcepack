from __future__ import annotations

import fnmatch
import json
import os
import stat
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from .git import run_git

POLICY_FILE_LIMIT_BYTES = 256 * 1024
POLICY_COLLECTION_LIMIT = 256
POLICY_STRING_LIMIT_CHARS = 1024
POLICY_NESTING_LIMIT = 12


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
    repository_rules: dict = field(default_factory=dict, repr=False)
    repository_policy_hash: str | None = field(default=None, repr=False)

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
    if text in {"local", "--local"}:
        return PolicyMode.LOCAL
    raise ValueError(f"unknown policy mode: {value}")


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
    if not isinstance(value, str):
        return None
    text = value.replace("\\", "/")
    if (
        not text
        or text != text.strip()
        or text.startswith("/")
        or "\x00" in text
        or "\r" in text
        or "\n" in text
        or (len(text) >= 2 and text[1] == ":" and text[0].isalpha())
        or value.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\"))
    ):
        return None
    if "//" in text or any(part in {"", ".", ".."} for part in text.split("/")):
        return None
    pure = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return pure.as_posix()


def policy_path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.rstrip("/") + "/**")


def validate_policy_config(repo: str | Path) -> PolicyValidationResult:
    repo_path = Path(repo).resolve()
    path = repo_path / ".sourcepack" / "policy.json"
    raw, byte_hash, read_error, policy_present = _read_repository_policy_file(repo_path, path)
    if not policy_present and read_error is None:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=False,
            valid=True,
        )
    warnings: list[str] = []
    invalid_entries: list[PolicyIgnoredEntryIssue] = []
    if read_error:
        validation_error = (
            "policy_config_invalid_json:" + read_error.removeprefix("malformed_json:")
            if read_error.startswith("malformed_json:")
            else f"policy_config_{read_error}"
        )
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(validation_error,),
            repository_policy_hash="sha256:" + byte_hash if byte_hash else None,
        )
    shape_error = _policy_shape_error(raw)
    if shape_error:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(f"policy_config_{shape_error}",),
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
    parsed_rules, rule_errors = _rules_from_policy(raw.get("rules"), "repository_policy", fail_unknown=True)
    if rule_errors:
        partial_config = PolicyConfig(
            ignored_paths=tuple(ignored), warnings=tuple(warnings), rules=_policy_rules_from_mapping(parsed_rules)
        )
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            effective_ignored_paths=tuple(ignored),
            ignored_invalid_entries=tuple(invalid_entries),
            warnings=tuple(warnings),
            errors=tuple(rule_errors),
            effective_config=partial_config,
            repository_rules=parsed_rules,
            repository_policy_hash=_content_identity(raw),
        )
    rules = _policy_rules_from_mapping(parsed_rules)
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
        repository_rules=parsed_rules,
        repository_policy_hash=_content_identity(raw),
    )


def load_policy_config(repo: str | Path) -> PolicyConfig:
    validation = validate_policy_config(repo)
    if not validation.policy_present:
        return PolicyConfig()
    if validation.valid:
        return validation.effective_config
    return PolicyConfig(warnings=tuple(validation.warnings) + tuple(validation.errors))


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
SUPPORTED_PACKAGE_MANAGERS = frozenset({"pnpm"})

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
        with path.open("rb") as handle:
            b = handle.read(POLICY_FILE_LIMIT_BYTES + 1)
    except OSError as exc:
        return None, None, f"unreadable:{exc}"
    if len(b) > POLICY_FILE_LIMIT_BYTES:
        return None, _sha256_bytes(b[:POLICY_FILE_LIMIT_BYTES]), f"limit_exceeded:file_bytes:{POLICY_FILE_LIMIT_BYTES}"
    try:
        return json.loads(b.decode("utf-8")), _sha256_bytes(b), None
    except UnicodeDecodeError as exc:
        return None, _sha256_bytes(b), f"malformed_json:utf8:{exc}"
    except json.JSONDecodeError as exc:
        return None, _sha256_bytes(b), f"malformed_json:{exc.msg}:line={exc.lineno}:column={exc.colno}"
    except (RecursionError, MemoryError) as exc:
        return None, _sha256_bytes(b), f"malformed_json:parser_limit:{type(exc).__name__}"


def _read_repository_policy_file(repo: Path, path: Path) -> tuple[object | None, str | None, str | None, bool]:
    """Acquire repository policy once without following repository-controlled symlinks.

    Descriptor-relative ``O_NOFOLLOW`` is used where available.  The before/after
    descriptor metadata check detects replacement or mutation during the bounded read.
    """
    policy_dir = repo / ".sourcepack"
    try:
        directory_stat = policy_dir.lstat()
    except FileNotFoundError:
        return None, None, None, False
    except OSError as exc:
        return None, None, f"unreadable:{exc}", True
    if stat.S_ISLNK(directory_stat.st_mode):
        return None, None, "unsafe:policy_directory_symlink", True
    if not stat.S_ISDIR(directory_stat.st_mode):
        return None, None, "unsafe:policy_directory_not_directory", True
    if (
        os.open not in getattr(os, "supports_dir_fd", ())
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
    ):
        # This fallback only classifies the pathname at one instant; it does not
        # provide descriptor-relative confinement or POSIX-equivalent race checks.
        try:
            unsupported_stat = path.lstat()
        except FileNotFoundError:
            return None, None, None, False
        except OSError as exc:
            return None, None, f"unsafe_or_unreadable:{exc}", True
        if stat.S_ISLNK(unsupported_stat.st_mode):
            return None, None, "unsafe:policy_symlink", True
        if not stat.S_ISREG(unsupported_stat.st_mode):
            return None, None, "unsafe:not_regular_file", True
        return None, None, "unsupported:descriptor_relative_no_follow", True
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory_fd = os.open(policy_dir, flags)
    except (OSError, NotImplementedError) as exc:
        return None, None, f"unsafe_or_unreadable:{exc}", True
    try:
        opened_directory_stat = os.fstat(directory_fd)
        if (directory_stat.st_dev, directory_stat.st_ino) != (opened_directory_stat.st_dev, opened_directory_stat.st_ino):
            return None, None, "unstable:policy_directory_replaced", True
        file_flags = os.O_RDONLY | os.O_NOFOLLOW
        try:
            file_fd = os.open(path.name, file_flags, dir_fd=directory_fd)
        except FileNotFoundError:
            try:
                current_directory_stat = policy_dir.lstat()
            except OSError as exc:
                return None, None, f"unstable:policy_directory_recheck:{exc}", True
            if (current_directory_stat.st_dev, current_directory_stat.st_ino) != (opened_directory_stat.st_dev, opened_directory_stat.st_ino):
                return None, None, "unstable:policy_directory_replaced", True
            return None, None, None, False
        except (OSError, NotImplementedError) as exc:
            return None, None, f"unsafe_or_unreadable:{exc}", True
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode):
                return None, None, "unsafe:not_regular_file", True
            chunks: list[bytes] = []
            remaining = POLICY_FILE_LIMIT_BYTES + 1
            while remaining:
                chunk = os.read(file_fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(file_fd)
            data = b"".join(chunks)
            identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            if identity_before != identity_after or len(data) != before.st_size:
                return None, _sha256_bytes(data[:POLICY_FILE_LIMIT_BYTES]), "unstable:mutation_detected", True
            try:
                current = path.lstat()
            except OSError as exc:
                return None, _sha256_bytes(data[:POLICY_FILE_LIMIT_BYTES]), f"unstable:path_recheck:{exc}", True
            if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
                return None, _sha256_bytes(data[:POLICY_FILE_LIMIT_BYTES]), "unstable:path_replaced", True
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)
    if len(data) > POLICY_FILE_LIMIT_BYTES:
        return None, _sha256_bytes(data[:POLICY_FILE_LIMIT_BYTES]), f"limit_exceeded:file_bytes:{POLICY_FILE_LIMIT_BYTES}", True
    try:
        return json.loads(data.decode("utf-8")), _sha256_bytes(data), None, True
    except UnicodeDecodeError as exc:
        return None, _sha256_bytes(data), f"malformed_json:utf8:{exc}", True
    except json.JSONDecodeError as exc:
        return None, _sha256_bytes(data), f"malformed_json:{exc.msg}:line={exc.lineno}:column={exc.colno}", True
    except (RecursionError, MemoryError) as exc:
        return None, _sha256_bytes(data), f"malformed_json:parser_limit:{type(exc).__name__}", True


def _policy_shape_error(value: object, depth: int = 0) -> str | None:
    if depth > POLICY_NESTING_LIMIT:
        return f"limit_exceeded:nesting_depth:{POLICY_NESTING_LIMIT}"
    if isinstance(value, str) and len(value) > POLICY_STRING_LIMIT_CHARS:
        return f"limit_exceeded:string_chars:{POLICY_STRING_LIMIT_CHARS}"
    if isinstance(value, (list, dict)) and len(value) > POLICY_COLLECTION_LIMIT:
        return f"limit_exceeded:collection_items:{POLICY_COLLECTION_LIMIT}"
    children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
    for child in children:
        error = _policy_shape_error(child, depth + 1)
        if error:
            return error
    return None


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
        if not isinstance(value, str) or not value.strip():
            return None, f"{source}_rule_invalid:package_manager_must_be_string"
        normalized = value.strip().lower()
        if normalized in SUPPORTED_PACKAGE_MANAGERS:
            return normalized, None
        return None, f"{source}_rule_invalid:unsupported_package_manager:{normalized}"
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


def _policy_rules_from_mapping(rules: dict) -> PolicyRules:
    """Create the public value object without discarding explicit presence in ``rules``."""
    return PolicyRules(
        block_dependency_additions=rules.get("block_dependency_additions", False),
        protected_paths=tuple(rules.get("protected_paths", ())),
        package_manager=rules.get("package_manager"),
        require_tests_for=tuple(rules.get("require_tests_for", ())),
        max_changed_lines=rules.get("max_changed_lines"),
        block_secret_patterns=rules.get("block_secret_patterns", False),
    )


def _repo_rules_from_validation(validation: PolicyValidationResult) -> dict:
    return dict(validation.repository_rules)


def _resolve_effective_policy(repo: str | Path, org_policy: str | Path | None = None, org_policy_mode: str = "optional") -> dict:
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
                    shape_error = _policy_shape_error(raw_org)
                    if shape_error:
                        org_status = "invalid"
                        errors.append(f"org_policy_{shape_error}")
                        org_id = None
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
    repo_hash = repo_validation.repository_policy_hash
    if not repo_validation.valid:
        for e in repo_validation.errors:
            prefixed = e if e.startswith("repository_") else f"repository_{e}"
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


def resolve_effective_policy(repo: str | Path, org_policy: str | Path | None = None, org_policy_mode: str = "optional") -> dict:
    """Resolve trusted policy and explicitly enforce proposed-state authority."""
    from .policy_authority import guard_effective_policy_result

    result = _resolve_effective_policy(repo, org_policy=org_policy, org_policy_mode=org_policy_mode)
    return guard_effective_policy_result(repo, result)


def _rule_provenance(rule: str, o_present: bool, r_present: bool, o: object, r: object, eff: object) -> dict:
    if rule in {"protected_paths", "require_tests_for"}:
        vals = sorted(set(o or ()) | set(r or ()))
        return {v: [s for s, present in (("organization", o_present and v in set(o or ())), ("repository", r_present and v in set(r or ()))) if present] for v in vals}
    return {"sources": [s for s, present in (("organization", o_present), ("repository", r_present)) if present]}
