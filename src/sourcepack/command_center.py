from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .baseline import validate_baseline
from .git import metadata as git_metadata
from .policy import resolve_effective_policy
from .workbench import (
    _bounded_changed_file_excerpt,
    _dashboard_payload,
    _read_canonical_report,
    _sourcepack_status_payload,
    _workbench_action,
)

COMMAND_CENTER_SCHEMA_VERSION = "sourcepack.command_center.v1"


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    surface: str
    status: str
    evidence: str
    action: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "surface": self.surface,
            "status": self.status,
            "evidence": self.evidence,
            "action": self.action,
        }


@dataclass(frozen=True)
class PriorityActionSpec:
    label: str
    action_type: str
    command: str | None = None
    target_surface: str | None = None

    def apply(self, *, action_id: str, priority: str, reason: str) -> dict[str, Any]:
        return {
            "id": action_id,
            "priority": priority,
            "label": self.label,
            "action_type": self.action_type,
            "command": self.command,
            "target_surface": self.target_surface,
            "reason": reason,
        }


_PRIORITY_ACTION_SPECS: dict[str, PriorityActionSpec] = {
    "run_review": PriorityActionSpec("Run review", "run_review"),
    "resolve_findings": PriorityActionSpec("Inspect findings", "navigate", target_surface="review"),
    "repair_policy": PriorityActionSpec("Open policy", "navigate", target_surface="policy"),
    "create_baseline": PriorityActionSpec("Copy baseline command", "copy_command", command="sourcepack baseline ."),
    "refresh_baseline": PriorityActionSpec("Copy baseline command", "copy_command", command="sourcepack baseline ."),
    "install_hooks": PriorityActionSpec("Copy hook command", "copy_command", command="sourcepack install-hook ."),
    "build_adversarial_runner": PriorityActionSpec("Open lab", "navigate", target_surface="lab"),
    "add_integration_adapter": PriorityActionSpec("Open integrations", "navigate", target_surface="integrations"),
    "build_improvement_loop": PriorityActionSpec("Open agents", "navigate", target_surface="agents"),
}


def _status_value(payload: dict[str, Any], key: str, default: Any = None) -> Any:
    status = payload.get("status")
    return status.get(key, default) if isinstance(status, dict) else default


def _capabilities(
    *,
    baseline: dict[str, Any],
    policy: dict[str, Any],
    report: dict[str, Any] | None,
    status: dict[str, Any],
) -> list[Capability]:
    baseline_state = str(baseline.get("state") or "missing")
    policy_state = str(policy.get("resolution_status") or "UNKNOWN")
    report_available = isinstance(report, dict)
    automatic = bool(_status_value(status, "automatic_mode_enabled", False))
    hook = bool(_status_value(status, "pre_commit_hook_installed", False))

    return [
        Capability(
            "review",
            "Canonical patch review",
            "Live Patch Review",
            "LIVE" if report_available else "READY",
            "latest canonical report available" if report_available else "review engine available; no report recorded",
            "run_review" if not report_available else None,
        ),
        Capability(
            "baseline",
            "Trusted repository baseline",
            "Repository Memory",
            "LIVE" if baseline_state in {"present", "stale"} else "NEEDS_SETUP",
            f"baseline state: {baseline_state}",
            "create_baseline" if baseline_state == "missing" else "refresh_baseline" if baseline_state == "stale" else None,
        ),
        Capability(
            "policy",
            "Policy authority",
            "Policy Studio",
            "LIVE" if policy_state == "PASS" else "DEGRADED",
            f"policy resolution: {policy_state}",
            "repair_policy" if policy_state != "PASS" else None,
        ),
        Capability(
            "hook",
            "Automatic Git enforcement",
            "Agent Gateway",
            "LIVE" if automatic else "PARTIAL" if hook else "READY_TO_BUILD",
            "automatic mode enabled" if automatic else "pre-commit hook installed" if hook else "manual review only",
            None if automatic else "install_hooks",
        ),
        Capability(
            "evidence",
            "Evidence and provenance explorer",
            "Evidence Graph",
            "LIVE" if report_available else "READY",
            "canonical evidence available" if report_available else "waiting for first canonical report",
        ),
        Capability(
            "replay",
            "Deterministic replay",
            "Replay Theater",
            "LIVE" if report_available and report.get("replay_bundle") else "PARTIAL",
            "replay bundle recorded" if report_available and report.get("replay_bundle") else "no replay bundle available",
        ),
        Capability(
            "adversarial",
            "Adversarial case laboratory",
            "Adversarial Lab",
            "READY_TO_BUILD",
            "hardening plan exists; executable corpus not yet connected",
            "build_adversarial_runner",
        ),
        Capability(
            "integrations",
            "External agent integrations",
            "Integration Hub",
            "PLANNED",
            "no remote integrations are configured or claimed",
            "add_integration_adapter",
        ),
        Capability(
            "autonomy",
            "Autonomous improvement loop",
            "Mission Control",
            "PLANNED",
            "objective, critic, and acceptance loop not implemented",
            "build_improvement_loop",
        ),
    ]


def _score(
    *,
    baseline: dict[str, Any],
    policy: dict[str, Any],
    report: dict[str, Any] | None,
    status: dict[str, Any],
    capabilities: list[Capability],
) -> dict[str, int]:
    trust = 0
    if baseline.get("state") == "present":
        trust += 45
    elif baseline.get("state") == "stale":
        trust += 25
    if policy.get("resolution_status") == "PASS":
        trust += 35
    if report:
        trust += 20

    automation = 10
    if _status_value(status, "pre_commit_hook_installed", False):
        automation += 25
    if _status_value(status, "post_commit_hook_installed", False):
        automation += 20
    if _status_value(status, "automatic_mode_enabled", False):
        automation += 35
    if report:
        automation += 10

    live = sum(1 for item in capabilities if item.status == "LIVE")
    partial = sum(1 for item in capabilities if item.status in {"PARTIAL", "READY"})
    breadth = round(100 * (live + partial * 0.5) / max(len(capabilities), 1))

    report_quality = 0
    if report:
        report_quality += 30
        if report.get("findings") is not None:
            report_quality += 20
        if report.get("evidence_items") or report.get("evidence"):
            report_quality += 20
        if report.get("replay_bundle"):
            report_quality += 20
        if report.get("reason_code_evidence"):
            report_quality += 10

    return {
        "trust": min(trust, 100),
        "automation": min(automation, 100),
        "product_breadth": min(breadth, 100),
        "report_depth": min(report_quality, 100),
    }


def _priority_action(*, action_id: str, priority: str, reason: str) -> dict[str, Any]:
    try:
        spec = _PRIORITY_ACTION_SPECS[action_id]
    except KeyError as exc:
        raise ValueError(f"Unknown Command Center priority action: {action_id}") from exc
    return spec.apply(action_id=action_id, priority=priority, reason=reason)


def _priority_actions(
    capabilities: list[Capability],
    *,
    report: dict[str, Any] | None,
    baseline: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    queued: list[tuple[str, str, str]] = []
    if baseline.get("state") == "missing":
        queued.append(("P0", "create_baseline", "No trusted repository baseline exists."))
    elif baseline.get("state") == "stale":
        queued.append(("P0", "refresh_baseline", "The trusted baseline is stale."))
    if policy.get("resolution_status") != "PASS":
        queued.append(("P0", "repair_policy", "Policy authority did not resolve successfully."))
    if report is None:
        queued.append(("P1", "run_review", "No canonical patch review is available."))
    elif report.get("verdict") in {"FAIL", "WARN"}:
        queued.append(("P1", "resolve_findings", f"Latest canonical verdict is {report.get('verdict')}."))

    queued_ids = {action_id for _, action_id, _ in queued}
    for capability in capabilities:
        if capability.action and capability.action not in queued_ids:
            priority = "P2" if capability.status in {"PARTIAL", "READY_TO_BUILD"} else "P3"
            queued.append((priority, capability.action, capability.evidence))
            queued_ids.add(capability.action)

    return [
        _priority_action(action_id=action_id, priority=priority, reason=reason)
        for priority, action_id, reason in queued[:8]
    ]


def _workbench_presentation(report: dict[str, Any] | None, action: dict[str, Any]) -> dict[str, Any]:
    """Build safe, display-ready Workbench rows from the canonical report."""
    if report is None:
        return {"evidence_cards": [], "correction_rows": []}

    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    finding = next((item for item in blockers + warnings + findings if isinstance(item, dict)), None)

    evidence_items = list(report.get("evidence_items")) if isinstance(report.get("evidence_items"), list) else []
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    for key in ("checked_evidence", "missing_evidence", "unsupported_evidence", "not_checked"):
        values = evidence.get(key)
        if isinstance(values, list):
            evidence_items.extend(values)
    reason_map = report.get("reason_code_evidence") if isinstance(report.get("reason_code_evidence"), dict) else {}
    evidence_ids = reason_map.get(action.get("reason"))
    if isinstance(evidence_ids, list) and evidence_ids:
        evidence_items = [
            item for item in evidence_items
            if isinstance(item, dict) and (item.get("evidence_id") in evidence_ids or item.get("id") in evidence_ids)
        ]
    if finding and finding.get("evidence"):
        evidence_items.insert(0, {"summary": finding["evidence"], "kind": "finding evidence", "checked_status": finding.get("checked_status")})

    cards = []
    for item in evidence_items[:6]:
        if isinstance(item, str):
            cards.append({"name": "Repository fact", "tag": "Evidence", "body": item, "problem": False})
            continue
        if not isinstance(item, dict):
            continue
        body = str(
            item.get("summary")
            or item.get("message")
            or item.get("fact")
            or item.get("path")
            or item.get("evidence_id")
            or "Evidence item recorded."
        )
        lowered = body.lower()
        cards.append({
            "name": str(item.get("title") or item.get("kind") or item.get("evidence_id") or "Repository fact"),
            "tag": str(item.get("checked_status") or item.get("status") or item.get("source_type") or "Evidence"),
            "body": body,
            "problem": "not found" in lowered or "missing" in lowered,
        })

    remediation = report.get("remediation") if isinstance(report.get("remediation"), dict) else {}
    remediation_items = remediation.get("items") if isinstance(remediation.get("items"), list) else []
    item = remediation_items[0] if remediation_items and isinstance(remediation_items[0], dict) else {}
    finding_remediation = finding.get("remediation") if finding and isinstance(finding.get("remediation"), dict) else {}
    correction_values = (
        ("Correction summary", item.get("summary") or finding_remediation.get("summary")),
        ("Affected path", item.get("path") or (finding or {}).get("path")),
        ("Repository-supported replacement", (finding or {}).get("suggestion") or item.get("summary") or finding_remediation.get("summary")),
    )
    return {
        "evidence_cards": cards,
        "correction_rows": [{"label": label, "value": str(value)} for label, value in correction_values if value],
    }


def build_command_center_snapshot(
    repo: str | Path,
    *,
    baseline_reader: Callable[[Path], dict[str, Any]] = validate_baseline,
    policy_reader: Callable[[Path], dict[str, Any]] = resolve_effective_policy,
    git_reader: Callable[[Path], dict[str, Any]] = git_metadata,
    status_reader: Callable[[Path], dict[str, Any]] = _sourcepack_status_payload,
    report_reader: Callable[[Path], tuple[dict[str, Any] | None, dict[str, Any] | None]] = _read_canonical_report,
) -> dict[str, Any]:
    root = Path(repo).resolve()
    baseline = baseline_reader(root)
    policy = policy_reader(root)
    git = git_reader(root)
    status = status_reader(root)
    report, report_error = report_reader(root)
    decisions = _dashboard_payload(root, "overrides")
    raw_verdict = report.get("verdict") if report else None
    supported_verdict = raw_verdict in {"PASS", "WARN", "FAIL"}
    canonical_report = report if supported_verdict else None
    capabilities = _capabilities(baseline=baseline, policy=policy, report=canonical_report, status=status)
    scores = _score(baseline=baseline, policy=policy, report=canonical_report, status=status, capabilities=capabilities)

    findings = canonical_report.get("findings", []) if isinstance(canonical_report, dict) else []
    blockers = canonical_report.get("blockers", []) if isinstance(canonical_report, dict) else []
    warnings = canonical_report.get("warnings", []) if isinstance(canonical_report, dict) else []
    report_error_code = (
        report_error.get("error", {}).get("code")
        if isinstance(report_error, dict) and isinstance(report_error.get("error"), dict)
        else None
    )
    report_state = (
        "unsupported"
        if report is not None and not supported_verdict
        else "available"
        if canonical_report is not None
        else "unsupported"
        if report_error_code == "artifact_version_unsupported"
        else "malformed"
        if report_error_code == "artifact_malformed"
        else "unavailable"
    )
    baseline_state = str(baseline.get("state") or "unavailable")
    policy_state = "available" if policy.get("resolution_status") == "PASS" else "degraded"
    replay_available = bool(canonical_report and canonical_report.get("replay_bundle"))
    verdict = raw_verdict if supported_verdict else None
    verdict_display = {
        "PASS": ("pass", "✓", "Change Passed"),
        "WARN": ("warn", "!", "Review Warning"),
        "FAIL": ("fail", "×", "Change Blocked"),
        None: ("neutral", "·", "No Report Available"),
    }[verdict] if report is None or supported_verdict else ("neutral", "·", "Unsupported Report")
    review_action = _workbench_action(report) if report_error is None else {
        "action_type": "none", "label": "Action Unavailable", "reason": str(report_error_code or "report_unavailable"),
        "target_surface": "none", "available": False,
    }
    workbench_presentation = _workbench_presentation(canonical_report, review_action)
    evidence_items = canonical_report.get("evidence_items", []) if canonical_report else []
    evidence_count = len(evidence_items) if isinstance(evidence_items, list) else 0
    report_time = next(
        (canonical_report.get(key) for key in ("generated_at", "created_at", "timestamp") if canonical_report and canonical_report.get(key)),
        None,
    )
    branch = git.get("branch") or git.get("current_branch")
    overall_state = (
        report_state
        if report_state in {"malformed", "unsupported"}
        else "degraded"
        if baseline_state not in {"present", "stale"} or policy_state == "degraded" or not replay_available
        else "available"
    )
    review_message = (
        f"Latest verdict: {verdict}"
        if verdict is not None
        else "Latest report state: unsupported"
        if report_state == "unsupported"
        else "Latest verdict: unavailable"
    )
    events = [
        {"type": "repository", "message": f"Repository loaded at {root}"},
        {"type": "baseline", "message": f"Baseline state: {baseline.get('state', 'unknown')}"},
        {"type": "policy", "message": f"Policy resolution: {policy.get('resolution_status', 'unknown')}"},
        {"type": "review", "message": review_message},
    ]
    if report_error:
        events.append({"type": "error", "message": str(report_error.get("error", {}).get("message") or "Canonical report unavailable")})

    return {
        "schema_version": COMMAND_CENTER_SCHEMA_VERSION,
        "sourcepack_version": __version__,
        "repository": {"path": str(root), "git": git},
        "display": {
            "verdict_class": verdict_display[0],
            "verdict_icon": verdict_display[1],
            "verdict_title": verdict_display[2],
            "verdict_label": verdict or ("UNSUPPORTED" if report is not None else "UNAVAILABLE"),
            "findings_summary": f"{len(blockers) if isinstance(blockers, list) else 0} blocking, {len(warnings) if isinstance(warnings, list) else 0} warnings",
            "navigation_findings_summary": f"{len(blockers) if isinstance(blockers, list) else 0} blocking · {len(warnings) if isinstance(warnings, list) else 0} warnings",
            "evidence_summary": f"{evidence_count} evidence items" if canonical_report else "unavailable",
            "branch": branch,
            "version_label": f"SourcePack v{__version__}",
            "report_time": report_time,
        },
        "state": {
            "overall": overall_state,
            "report": report_state,
            "baseline": "available" if baseline_state in {"present", "stale"} else "unavailable",
            "policy": policy_state,
            "replay": "available" if replay_available else "degraded" if canonical_report is not None else "unavailable",
        },
        "posture": {
            "verdict": verdict,
            "baseline_state": baseline.get("state"),
            "policy_resolution_status": policy.get("resolution_status"),
            "automatic_mode_enabled": bool(_status_value(status, "automatic_mode_enabled", False)),
            "finding_count": len(findings) if isinstance(findings, list) else 0,
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
            "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        },
        "scores": scores,
        "capabilities": [item.as_dict() for item in capabilities],
        "priority_actions": _priority_actions(capabilities, report=canonical_report, baseline=baseline, policy=policy),
        "activity": events,
        "available_artifacts": [
            {"id": "baseline", "available": baseline_state in {"present", "stale"}},
            {"id": "policy", "available": policy_state == "available"},
            {"id": "report", "available": canonical_report is not None},
            {"id": "replay", "available": replay_available},
            {"id": "decisions", "available": decisions.get("status") != "error"},
        ],
        "workbench": {
            "review_action": review_action,
            "proposed_change": _bounded_changed_file_excerpt(root, canonical_report) if canonical_report is not None else None,
            **workbench_presentation,
        },
        "artifacts": {
            "baseline": baseline,
            "policy": policy,
            "status": status,
            "report": report,
            "report_error": report_error,
            "decisions": decisions,
        },
    }
