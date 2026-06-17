from __future__ import annotations

LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}

def render_traffic(report: dict, verbose: bool = False) -> str:
    verdict = report.get("verdict", "WARN")
    lines = [f"Verdict: {verdict}", f"{report.get('light', LIGHT_BY_VERDICT.get(verdict, 'YELLOW LIGHT'))}: {report.get('headline', '')}", ""]
    if report.get("reason_type"):
        lines.append(f"Reason type: {report.get('reason_type')}")
    lines.append(f"Commit policy: {report.get('commit_policy') or 'allowed.'}")
    lines.append("")
    if verdict == "PASS":
        info = [f for f in report.get("findings", []) if f.get("severity") == "info"]
        lines.append(info[0]["message"] if info else "No unsupported project claims or patch assumptions detected.")
        if report.get("checked_categories"):
            lines.extend(["", "Checked:", ""])
            lines.extend(f"- {item}" for item in report.get("checked_categories", []))
        if report.get("not_checked"):
            lines.extend(["", "Not checked:", ""])
            lines.extend(f"- {item}" for item in report.get("not_checked", []))
    elif verdict == "WARN":
        lines.append("SourcePack found review or uncertainty items, but no clear unsupported blocker.")
        review = [f for f in report.get("warnings", []) if f.get("category") != "uncertainty"]
        uncertain = [f for f in report.get("warnings", []) if f.get("category") == "uncertainty"]
        if review:
            lines.extend(["", "Review warnings:", ""])
            shown = review if verbose else review[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        if uncertain:
            lines.extend(["", "Uncertainties:", ""])
            shown = uncertain if verbose else uncertain[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    else:
        lines.append("SourcePack found missing files, unsupported dependencies, unsupported commands, or unsupported capabilities.")
        if report.get("blockers"):
            lines.extend(["", "Blockers:", ""])
            shown = report.get("blockers", []) if verbose else report.get("blockers", [])[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        review = [f for f in report.get("warnings", []) if f.get("category") != "uncertainty"]
        uncertain = [f for f in report.get("warnings", []) if f.get("category") == "uncertainty"]
        if review:
            lines.extend(["", "Review warnings:", ""])
            shown = review if verbose else review[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        if uncertain:
            lines.extend(["", "Uncertainties:", ""])
            shown = uncertain if verbose else uncertain[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    if verdict != "PASS":
        if report.get("checked_categories"):
            lines.extend(["", "Checked:", ""])
            lines.extend(f"- {item}" for item in report.get("checked_categories", []))
        if report.get("not_checked"):
            lines.extend(["", "Not checked:", ""])
            lines.extend(f"- {item}" for item in report.get("not_checked", []))
    lines.extend(["", f"Report path: {report.get('report_path', '.sourcepack/reports/latest.json')}"])
    return "\n".join(lines) + "\n"

