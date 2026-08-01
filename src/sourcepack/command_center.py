from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .baseline import validate_baseline
from .command_center_limits import MAX_COLLECTION_ITEMS, MAX_PROMPT_CHARS, MAX_SNAPSHOT_BYTES, bounded_value, clip_text, collection_status
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
            "name": clip_text(self.name),
            "surface": clip_text(self.surface),
            "status": self.status,
            "evidence": clip_text(self.evidence),
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
    report_present = isinstance(report, dict)
    report_complete = report_present and report.get("authority", {}).get("complete", True) is True
    automatic = bool(_status_value(status, "automatic_mode_enabled", False))
    hook = bool(_status_value(status, "pre_commit_hook_installed", False))

    return [
        Capability(
            "review",
            "Canonical patch review",
            "Live Patch Review",
            "LIVE" if report_complete else "PARTIAL" if report_present else "READY",
            "latest canonical report available" if report_complete else "canonical report is incomplete" if report_present else "review engine available; no report recorded",
            "run_review" if not report_complete else None,
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
            "LIVE" if report_complete else "PARTIAL" if report_present else "READY",
            "canonical evidence available" if report_complete else "bounded evidence from an incomplete report" if report_present else "waiting for first canonical report",
        ),
        Capability(
            "replay",
            "Deterministic replay",
            "Replay Theater",
            "LIVE" if report_complete and report.get("replay_bundle") else "PARTIAL",
            "replay bundle recorded" if report_complete and report.get("replay_bundle") else "bounded replay from an incomplete report" if report_present and report.get("replay_bundle") else "no replay bundle available",
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
    report_complete = bool(report and report.get("authority", {}).get("complete", True) is True)
    trust = 0
    if baseline.get("state") == "present":
        trust += 45
    elif baseline.get("state") == "stale":
        trust += 25
    if policy.get("resolution_status") == "PASS":
        trust += 35
    if report_complete:
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
    action = spec.apply(action_id=action_id, priority=priority, reason=clip_text(reason))
    action["label"] = clip_text(action["label"])
    return action


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
    finding = next((item for rows in (blockers, warnings, findings) for item in rows[:MAX_COLLECTION_ITEMS] if isinstance(item, dict)), None)

    evidence_items = list(report.get("evidence_items")[:MAX_COLLECTION_ITEMS]) if isinstance(report.get("evidence_items"), list) else []
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    for key in ("checked_evidence", "missing_evidence", "unsupported_evidence", "not_checked"):
        values = evidence.get(key)
        if isinstance(values, list):
            evidence_items.extend(values[:MAX_COLLECTION_ITEMS])
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
    root_display = clip_text(root)
    baseline = baseline_reader(root)
    policy = policy_reader(root)
    git = git_reader(root)
    status = status_reader(root)
    report, report_error = report_reader(root)
    decisions = _dashboard_payload(root, "overrides")
    raw_verdict = report.get("verdict") if report else None
    supported_verdict = raw_verdict in {"PASS", "WARN", "FAIL"}
    canonical_report = report if supported_verdict else None
    report_complete = not canonical_report or canonical_report.get("authority", {}).get("complete", True) is True
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
        else "incomplete"
        if canonical_report is not None and not report_complete
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
    replay_available = bool(canonical_report and report_complete and canonical_report.get("replay_bundle"))
    verdict = raw_verdict if supported_verdict else None
    verdict_display = {
        "PASS": ("pass", "✓", "Change Passed"),
        "WARN": ("warn", "!", "Incomplete Review" if not report_complete else "Review Warning"),
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
    branch_value = git.get("branch") or git.get("current_branch")
    branch = clip_text(branch_value) if branch_value is not None else None
    report_time = clip_text(report_time) if report_time is not None else None
    overall_state = (
        report_state
        if report_state in {"malformed", "unsupported"}
        else "degraded"
        if baseline_state not in {"present", "stale"} or policy_state == "degraded" or not replay_available
        else "available"
    )
    review_message = (
        f"Latest verdict: {verdict} (incomplete)"
        if verdict is not None and not report_complete
        else f"Latest verdict: {verdict}"
        if verdict is not None
        else "Latest report state: unsupported"
        if report_state == "unsupported"
        else "Latest verdict: unavailable"
    )
    events = [
        {"type": "repository", "message": clip_text(f"Repository loaded at {root_display}")},
        {"type": "baseline", "message": clip_text(f"Baseline state: {baseline.get('state', 'unknown')}")},
        {"type": "policy", "message": clip_text(f"Policy resolution: {policy.get('resolution_status', 'unknown')}")},
        {"type": "review", "message": review_message},
    ]
    if report_error:
        events.append({"type": "error", "message": clip_text(report_error.get("error", {}).get("message") or "Canonical report unavailable")})

    result = {
        "schema_version": COMMAND_CENTER_SCHEMA_VERSION,
        "sourcepack_version": __version__,
        "repository": {"path": root_display, "git": bounded_value(git)},
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
            "baseline_state": clip_text(baseline.get("state")) if baseline.get("state") is not None else None,
            "policy_resolution_status": clip_text(policy.get("resolution_status")) if policy.get("resolution_status") is not None else None,
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
            {"id": "report", "available": canonical_report is not None and report_complete},
            {"id": "replay", "available": replay_available},
            {"id": "decisions", "available": decisions.get("ledger_available") is True and decisions.get("ledger_complete") is True},
        ],
        "workbench": {
            "review_action": review_action,
            "proposed_change": _bounded_changed_file_excerpt(root, canonical_report) if canonical_report is not None else None,
            **workbench_presentation,
        },
        "artifacts": {},
    }
    bounded_report = bounded_value(report) if report is not None else None
    result["artifacts"] = {
        "baseline": bounded_value(baseline), "policy": bounded_value(policy),
        "status": bounded_value(status), "report": bounded_report,
        "report_error": bounded_value(report_error) if report_error is not None else None,
        "decisions": bounded_value(decisions),
    }
    if "prompt" in result["workbench"]["review_action"]:
        result["workbench"]["review_action"]["prompt"] = clip_text(
            result["workbench"]["review_action"]["prompt"], MAX_PROMPT_CHARS
        )
    for key in ("label", "reason"):
        result["workbench"]["review_action"][key] = clip_text(result["workbench"]["review_action"][key])
    for card in result["workbench"]["evidence_cards"]:
        for key in ("name", "tag", "body"):
            card[key] = clip_text(card[key])
    for row in result["workbench"]["correction_rows"]:
        row["value"] = clip_text(row["value"])
    result["bounds"] = {
        "max_serialized_bytes": MAX_SNAPSHOT_BYTES,
        "bounded_content": True,
        "collections": {
            key: collection_status(report.get(key) if isinstance(report, dict) else None, bounded_report.get(key) if isinstance(bounded_report, dict) else None)
            for key in ("findings", "blockers", "warnings", "evidence_items")
        },
        "artifacts": {key: {"bounded": True, "omission_reason": None} for key in result["artifacts"]},
    }
    return result
