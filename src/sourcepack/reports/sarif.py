from __future__ import annotations


def _level(severity: str) -> str:
    return {"error": "error", "warn": "warning", "info": "note"}.get(severity, "note")


def render_sarif(report: dict) -> dict:
    """Render a SourcePack traffic report as SARIF 2.1.0.

    SARIF is only a transport/report format here; SourcePack findings and
    verdicts remain the sole judgment source.
    """
    rules: dict[str, dict] = {}
    results: list[dict] = []
    for finding in report.get("findings", []) if isinstance(report.get("findings"), list) else []:
        rule_id = str(finding.get("id") or "sourcepack_finding")
        rules.setdefault(rule_id, {"id": rule_id, "name": rule_id, "shortDescription": {"text": rule_id}})
        result = {
            "ruleId": rule_id,
            "level": _level(str(finding.get("severity") or "info")),
            "message": {"text": str(finding.get("message") or rule_id)},
        }
        path = finding.get("path")
        if path:
            result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": str(path).replace("\\", "/")}}}]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "SourcePack", "informationUri": "https://pypi.org/project/sourcepack/", "rules": list(rules.values())}},
            "invocations": [{"executionSuccessful": report.get("verdict") != "FAIL"}],
            "results": results,
        }],
    }
