from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sourcepack import __version__
from sourcepack.paths import ensure_sourcepack_dirs
from sourcepack.reports.html import render_report_html
from sourcepack.reports.markdown import LIGHT_BY_VERDICT, render_traffic
from sourcepack.reason_codes import normalize_reason_code, is_canonical_reason_code
from sourcepack.evidence import evidence_summary, make_evidence

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalized_finding(fid: str, severity: str, category: str, message: str, path: str | None = None, evidence: str | None = None, suggestion: str | None = None) -> dict:
    code = normalize_reason_code(fid)
    if severity in {"error", "warn"} and not is_canonical_reason_code(code):
        raise ValueError(f"unknown SourcePack reason code: {fid}")
    return {"id": code, "severity": severity, "category": category, "path": path, "message": message, "evidence": evidence, "suggestion": suggestion}


def traffic_report(verdict: str, headline: str | None = None, findings: list[dict] | None = None, checked_categories: list[str] | None = None, next_action: str | None = None, report_path: str = ".sourcepack/reports/latest.json", reason_type: str | None = None, not_checked: list[str] | None = None) -> dict:
    findings = sorted(findings or [], key=lambda f: (SEVERITY_ORDER.get(f.get("severity", "info"), 9), f.get("id", ""), f.get("path") or ""))
    blockers = [f for f in findings if f.get("severity") == "error"]
    warnings = [f for f in findings if f.get("severity") == "warn"]
    light = LIGHT_BY_VERDICT.get(verdict, "YELLOW LIGHT")
    if reason_type is None:
        reason_type = "blocker" if verdict == "FAIL" else "review" if warnings else "none"
        if any(f.get("category") in {"uncertainty", "tooling"} for f in warnings):
            reason_type = "uncertainty" if any(f.get("category") == "uncertainty" for f in warnings) else "tooling"
    if headline is None:
        if verdict == "WARN" and reason_type == "uncertainty":
            headline = "SourcePack could not fully evaluate this change."
        elif verdict == "WARN" and reason_type == "tooling":
            headline = "SourcePack tooling degraded."
        else:
            headline = {"PASS": "good to continue.", "WARN": "review before continuing.", "FAIL": "stop before trusting this output."}.get(verdict, "review before continuing.")
    next_action = next_action or ("ask the AI to revise using only files, dependencies, and commands confirmed by SourcePack." if verdict == "FAIL" else "review the listed items before continuing." if verdict == "WARN" else "continue.")
    commit_policy = None
    if verdict == "WARN":
        commit_policy = "allowed locally, blocked in strict mode."
    elif verdict == "FAIL":
        commit_policy = "blocked unless explicitly bypassed."
    checked_categories = checked_categories or []
    not_checked = not_checked or ["runtime behavior", "semantic correctness", "security", "external services"]
    records = []
    for category in checked_categories:
        eclass = "trusted_baseline" if "baseline" in category else "dependency_manifest" if "import" in category.lower() else "command_manifest" if "command" in category.lower() else "current_worktree"
        records.append(make_evidence(eclass, category, "checked"))
    for category in not_checked:
        records.append(make_evidence("not_checked", category, "not_checked"))
    for f in findings:
        if f.get("evidence_class"):
            records.append(f)
    evidence = evidence_summary(records)
    confidence_summary = {"basis": "local evidence coverage, not AI confidence", "checked": checked_categories, "partially_checked": ["execution_claim_check"], "not_checked": not_checked, "limitations": ["SourcePack does not prove code correctness", "SourcePack does not prove security", "SourcePack does not verify external API behavior unless local evidence exists"]}
    return {"schema_version": "traffic_report.v1", "sourcepack_version": __version__, "verdict": verdict, "light": light, "headline": headline, "reason_type": reason_type, "commit_policy": commit_policy, "blockers": blockers, "warnings": warnings, "uncertainties": [f for f in warnings if f.get("category") == "uncertainty"], "checked_categories": checked_categories, "checked": checked_categories, "partially_checked": ["execution_claim_check"], "unavailable_evidence": evidence["missing_evidence"], "unsupported_evidence": [f for f in findings if f.get("id") == "unsupported_ecosystem"], "not_checked": not_checked, "confidence_summary": confidence_summary, "evidence": evidence, "next_action": next_action, "report_path": report_path, "findings": findings}


def _write_optional_report_file(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        print(f"WARNING: could not write SourcePack report artifact {path}: {exc}", file=sys.stderr)


def write_user_report(repo: str | Path, report: dict, stem: str = "report") -> None:
    paths = ensure_sourcepack_dirs(repo)
    full = dict(report)
    full.setdefault("sourcepack_version", __version__)
    full.setdefault("schema_version", "traffic_report.v1")
    full["generated_at"] = utc_now()
    json_text = json.dumps(full, indent=2)
    md_text = render_traffic(full, verbose=True)
    paths["latest_json"].write_text(json_text, encoding="utf-8")
    _write_optional_report_file(paths["latest_md"], md_text)
    try:
        html_text = render_report_html(full)
    except Exception as exc:
        print(f"WARNING: could not render SourcePack HTML report: {exc}", file=sys.stderr)
    else:
        _write_optional_report_file(paths["latest_html"], html_text)
    typed = paths.get(f"latest_{stem}_json")
    if typed is not None:
        _write_optional_report_file(typed, json_text)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _write_optional_report_file(paths["archive"] / f"{ts}_{stem}.json", json_text)
    _write_optional_report_file(paths["archive"] / f"{ts}_{stem}.md", md_text)

