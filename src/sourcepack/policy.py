from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath


class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


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



SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS = frozenset({"new_file"})
_RESERVED_POLICY_FIELDS = {
    "strict_default": "policy_config_reserved:strict_default",
    "fail_on_warn_in_ci": "policy_config_reserved:fail_on_warn_in_ci",
    "protected_paths": "policy_config_reserved:protected_paths",
    "report_formats": "policy_config_reserved:report_formats",
}

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


def exit_code(verdict: str, mode: PolicyMode | str | None = None) -> int:
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
        if pattern.startswith(".git/") or pattern.startswith(".sourcepack/baseline/"):
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
    return PolicyConfig(
        strict_default=bool(raw.get("strict_default", True)),
        fail_on_warn_in_ci=bool(raw.get("fail_on_warn_in_ci", True)),
        ignored_paths=tuple(ignored),
        protected_paths=tuple(protected) or PolicyConfig.protected_paths,
        report_formats=tuple(formats) or PolicyConfig.report_formats,
        warnings=tuple(warnings),
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
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("/") + "/**"):
            return {"pattern": pattern, "reason": item["reason"], "path": path}
    return None
