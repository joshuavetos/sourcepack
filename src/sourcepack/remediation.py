from __future__ import annotations

import json
from typing import Any


REMEDIATION_SCHEMA_VERSION = "sourcepack.remediation.v1"


def _prompt_field(value: Any) -> str:
    """Render repository-controlled finding fields as inert prompt data."""
    return json.dumps(str(value), ensure_ascii=False)


def remediation_for_finding(finding: dict[str, Any]) -> dict[str, Any] | None:
    """Render bounded agent guidance from an existing canonical finding.

    This function does not inspect the repository, infer missing facts, or call a
    model. It only restates evidence already present on the finding and asks the
    agent to revise within SourcePack's established claim boundary.
    """
    if finding.get("severity") not in {"error", "warn"}:
        return None

    reason_code = str(finding.get("id") or "unknown_finding")
    finding_id = finding.get("finding_id")
    path = finding.get("path")
    message = str(finding.get("message") or reason_code)
    evidence = finding.get("evidence")
    suggestion = finding.get("suggestion")

    lines = [
        "Revise the proposed change using only repository facts supported by SourcePack evidence.",
        "",
        f"Finding: {_prompt_field(reason_code)}",
    ]
    if path:
        lines.append(f"Path: {_prompt_field(path)}")
    lines.append(f"Problem: {_prompt_field(message)}")
    if evidence:
        lines.append(f"Repository evidence: {_prompt_field(evidence)}")
    if suggestion:
        lines.append(f"Suggested correction: {_prompt_field(suggestion)}")

    lines.extend(
        [
            "",
            "Requirements:",
            "- Preserve the user's requested behavior where the repository supports it.",
            "- Do not modify manifests, trusted baseline state, policy, or protected SourcePack artifacts merely to silence the finding.",
            "- Prefer files, dependencies, commands, and patterns already supported by the repository evidence.",
            "- Run the relevant tests or checks after revising the change.",
            "- Return the corrected patch and briefly state how it addresses this finding.",
        ]
    )

    return {
        "schema_version": REMEDIATION_SCHEMA_VERSION,
        "finding_id": finding_id,
        "reason_code": reason_code,
        "path": path,
        "summary": suggestion or message,
        "agent_prompt": "\n".join(lines),
        "source": "canonical_finding",
    }


def attach_remediation(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for finding in findings:
        remediation = remediation_for_finding(finding)
        if remediation is not None:
            finding["remediation"] = remediation
    return findings


def report_remediation(findings: list[dict[str, Any]]) -> dict[str, Any]:
    items = [finding["remediation"] for finding in findings if isinstance(finding.get("remediation"), dict)]
    prompts = [item["agent_prompt"] for item in items if item.get("agent_prompt")]
    return {
        "schema_version": REMEDIATION_SCHEMA_VERSION,
        "status": "available" if items else "unavailable",
        "items": items,
        "agent_prompt": "\n\n---\n\n".join(prompts),
        "limitations": [
            "Remediation restates canonical findings and does not prove the corrected patch is valid.",
            "No model call or autonomous code modification is performed.",
        ],
    }
