from __future__ import annotations

from enum import StrEnum

class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


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
