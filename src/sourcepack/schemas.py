from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .reason_codes import ReasonCode

BASELINE_SCHEMA_VERSION = "baseline_pointer.v1"
JUDGMENT_REPORT_SCHEMA_VERSION = "traffic_report.v1"
PROMPT_CONTEXT_SCHEMA_VERSION = "prompt_context.v1"


class Verdict(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


@dataclass(frozen=True)
class Finding:
    code: ReasonCode | str
    severity: Severity | str
    path: str | None
    message: str
    evidence: str | None = None
    suggested_fixes: list[str] = field(default_factory=list)
    category: str | None = None

    def to_report_dict(self) -> dict[str, Any]:
        suggestion = self.suggested_fixes[0] if self.suggested_fixes else None
        return {
            "id": str(self.code),
            "severity": str(self.severity),
            "category": self.category,
            "path": self.path,
            "message": self.message,
            "evidence": self.evidence,
            "suggestion": suggestion,
        }


@dataclass(frozen=True)
class Judgment:
    verdict: Verdict | str
    findings: list[Finding]
    checked_categories: list[str]
    not_checked: list[str]
    reason_type: str | None
    commit_policy: str | None
    next_action: str
