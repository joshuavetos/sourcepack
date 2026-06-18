from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable

EVIDENCE_SCHEMA_VERSION = "sourcepack.evidence.v1"


class EvidenceClass(StrEnum):
    TRUSTED_BASELINE = "trusted_baseline"
    CURRENT_WORKTREE = "current_worktree"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    COMMAND_MANIFEST = "command_manifest"
    EXECUTION_LEDGER = "execution_ledger"
    GIT_METADATA = "git_metadata"
    PROMPT_CONTEXT = "prompt_context"
    AI_ANSWER = "ai_answer"
    USER_CONFIG = "user_config"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"


TRUST_LEVELS = {
    EvidenceClass.TRUSTED_BASELINE: "trusted",
    EvidenceClass.CURRENT_WORKTREE: "local_observation",
    EvidenceClass.DEPENDENCY_MANIFEST: "local_manifest",
    EvidenceClass.COMMAND_MANIFEST: "local_manifest",
    EvidenceClass.EXECUTION_LEDGER: "local_execution_record",
    EvidenceClass.GIT_METADATA: "local_metadata",
    EvidenceClass.USER_CONFIG: "user_policy",
    EvidenceClass.PROMPT_CONTEXT: "advisory",
    EvidenceClass.AI_ANSWER: "advisory",
    EvidenceClass.UNSUPPORTED: "unsupported",
    EvidenceClass.NOT_CHECKED: "not_checked",
}

ENFORCEMENT_CAPABLE = {
    EvidenceClass.TRUSTED_BASELINE,
    EvidenceClass.CURRENT_WORKTREE,
    EvidenceClass.DEPENDENCY_MANIFEST,
    EvidenceClass.COMMAND_MANIFEST,
    EvidenceClass.EXECUTION_LEDGER,
    EvidenceClass.GIT_METADATA,
    EvidenceClass.USER_CONFIG,
}


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_class: str
    evidence_source: str
    trust_level: str
    checked_status: str
    missing_evidence: str | None = None
    required_evidence_class: str | None = None
    supports_claim: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_evidence_class(value: str | EvidenceClass) -> EvidenceClass:
    return value if isinstance(value, EvidenceClass) else EvidenceClass(str(value))


def make_evidence(evidence_class: str | EvidenceClass, evidence_source: str, checked_status: str = "checked", *, missing_evidence: str | None = None, required_evidence_class: str | EvidenceClass | None = None, supports_claim: str | None = None) -> EvidenceRecord:
    cls = normalize_evidence_class(evidence_class)
    req = normalize_evidence_class(required_evidence_class).value if required_evidence_class else None
    return EvidenceRecord(cls.value, evidence_source, TRUST_LEVELS[cls], checked_status, missing_evidence, req, supports_claim)


def can_satisfy(evidence: EvidenceRecord | dict, required: str | EvidenceClass, claim: str | None = None) -> bool:
    eclass = normalize_evidence_class(evidence["evidence_class"] if isinstance(evidence, dict) else evidence.evidence_class)
    required_cls = normalize_evidence_class(required)
    if eclass in {EvidenceClass.PROMPT_CONTEXT, EvidenceClass.AI_ANSWER, EvidenceClass.UNSUPPORTED, EvidenceClass.NOT_CHECKED}:
        return False
    if eclass != required_cls:
        return False
    if eclass == EvidenceClass.EXECUTION_LEDGER and claim not in {None, "local_execution"}:
        return False
    return eclass in ENFORCEMENT_CAPABLE


def evidence_summary(records: Iterable[EvidenceRecord | dict]) -> dict:
    checked: list[dict] = []
    missing: list[dict] = []
    advisory: list[dict] = []
    not_checked: list[dict] = []
    for rec in records:
        item = rec if isinstance(rec, dict) else rec.to_dict()
        cls = item.get("evidence_class")
        status = item.get("checked_status")
        if cls in {EvidenceClass.PROMPT_CONTEXT.value, EvidenceClass.AI_ANSWER.value}:
            advisory.append(item)
        elif cls == EvidenceClass.NOT_CHECKED.value or status == "not_checked":
            not_checked.append(item)
        elif item.get("missing_evidence") or status in {"missing", "unavailable"}:
            missing.append(item)
        else:
            checked.append(item)
    return {"schema_version": EVIDENCE_SCHEMA_VERSION, "checked_evidence": checked, "missing_evidence": missing, "advisory_evidence_ignored_for_enforcement": advisory, "not_checked": not_checked}


def attach_evidence_to_finding(finding: dict, evidence_class: str | EvidenceClass, evidence_source: str, checked_status: str = "checked", **kwargs) -> dict:
    result = dict(finding)
    rec = make_evidence(evidence_class, evidence_source, checked_status, **kwargs).to_dict()
    result.update(rec)
    return result
