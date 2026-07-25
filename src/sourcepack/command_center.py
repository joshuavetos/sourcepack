from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .baseline import validate_baseline
from .git import metadata as git_metadata
from .policy import resolve_effective_policy
from .workbench import _read_canonical_report, _sourcepack_status_payload

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


def _priority_actions(
    capabilities: list[Capability],
    *,
    report: dict[str, Any] | None,
    baseline: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if baseline.get("state") == "missing":
        actions.append({"priority": "P0", "id": "create_baseline", "reason": "No trusted repository baseline exists."})
    elif baseline.get("state") == "stale":
        actions.append({"priority": "P0", "id": "refresh_baseline", "reason": "The trusted baseline is stale."})
    if policy.get("resolution_status") != "PASS":
        actions.append({"priority": "P0", "id": "repair_policy", "reason": "Policy authority did not resolve successfully."})
    if report is None:
        actions.append({"priority": "P1", "id": "run_review", "reason": "No canonical patch review is available."})
    elif report.get("verdict") in {"FAIL", "WARN"}:
        actions.append({"priority": "P1", "id": "resolve_findings", "reason": f"Latest canonical verdict is {report.get('verdict')}."})

    for capability in capabilities:
        if capability.action and capability.action not in {item["id"] for item in actions}:
            priority = "P2" if capability.status in {"PARTIAL", "READY_TO_BUILD"} else "P3"
            actions.append({"priority": priority, "id": capability.action, "reason": capability.evidence})
    return actions[:8]


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
    capabilities = _capabilities(baseline=baseline, policy=policy, report=report, status=status)
    scores = _score(baseline=baseline, policy=policy, report=report, status=status, capabilities=capabilities)

    findings = report.get("findings", []) if isinstance(report, dict) else []
    blockers = report.get("blockers", []) if isinstance(report, dict) else []
    warnings = report.get("warnings", []) if isinstance(report, dict) else []
    events = [
        {"type": "repository", "message": f"Repository loaded at {root}"},
        {"type": "baseline", "message": f"Baseline state: {baseline.get('state', 'unknown')}"},
        {"type": "policy", "message": f"Policy resolution: {policy.get('resolution_status', 'unknown')}"},
        {"type": "review", "message": f"Latest verdict: {report.get('verdict', 'unavailable') if report else 'unavailable'}"},
    ]
    if report_error:
        events.append({"type": "error", "message": str(report_error.get("error", {}).get("message") or "Canonical report unavailable")})

    return {
        "schema_version": COMMAND_CENTER_SCHEMA_VERSION,
        "sourcepack_version": __version__,
        "repository": {"path": str(root), "git": git},
        "posture": {
            "verdict": report.get("verdict") if report else None,
            "baseline_state": baseline.get("state"),
            "policy_resolution_status": policy.get("resolution_status"),
            "automatic_mode_enabled": bool(_status_value(status, "automatic_mode_enabled", False)),
            "finding_count": len(findings) if isinstance(findings, list) else 0,
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
            "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        },
        "scores": scores,
        "capabilities": [item.as_dict() for item in capabilities],
        "priority_actions": _priority_actions(capabilities, report=report, baseline=baseline, policy=policy),
        "activity": events,
        "artifacts": {
            "baseline": baseline,
            "policy": policy,
            "status": status,
            "report": report,
            "report_error": report_error,
        },
    }
