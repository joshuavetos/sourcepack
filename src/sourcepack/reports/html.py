from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape


def _html_escape(value: object) -> str:
    return xml_escape("" if value is None else str(value), {'"': '&quot;', "'": '&#x27;'})


def _report_badge_class(verdict: str) -> str:
    return {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}.get(verdict, "warn")

def render_report_html(report: dict) -> str:
    verdict = str(report.get("verdict", "WARN"))
    badge = _report_badge_class(verdict)
    findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
    raw_json_path = report.get("report_path") or ".sourcepack/reports/latest.json"
    baseline_path = report.get("baseline_packet_path") or (report.get("baseline") or {}).get("packet_path") if isinstance(report.get("baseline"), dict) else report.get("baseline_packet_path")

    def finding_rows(items: list[dict]) -> str:
        if not items:
            return '<tr><td colspan="5" class="muted">None.</td></tr>'
        rows = []
        for f in items:
            rows.append(
                "<tr>"
                f"<td><code>{_html_escape(f.get('id'))}</code></td>"
                f"<td><span class='severity {_html_escape(f.get('severity'))}'>{_html_escape(f.get('severity'))}</span></td>"
                f"<td>{_html_escape(f.get('path') or '—')}</td>"
                f"<td>{_html_escape(f.get('message'))}</td>"
                f"<td>{_html_escape(f.get('suggestion') or f.get('evidence') or '—')}</td>"
                "</tr>"
            )
        return "\n".join(rows)

    checked = "".join(f"<li>{_html_escape(item)}</li>" for item in report.get("checked_categories", [])) or "<li>None recorded.</li>"
    not_checked = "".join(f"<li>{_html_escape(item)}</li>" for item in report.get("not_checked", [])) or "<li>None recorded.</li>"
    affected = sorted({str(f.get("path")) for f in findings if f.get("path")})
    affected_html = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in affected) or "<li>No affected file paths recorded.</li>"
    missing = [f for f in findings if f.get("id") in {"missing_file", "unsupported_dependency", "unsupported_command", "unsupported_ecosystem", "js_alias_uncertain", "dependency_manifest_uncertain"} or f.get("category") == "uncertainty"]
    fixes = [f for f in findings if f.get("suggestion")]
    missing_html = "".join(f"<li><code>{_html_escape(f.get('id'))}</code>: {_html_escape(f.get('message'))}</li>" for f in missing) or "<li>No missing evidence recorded.</li>"
    fixes_html = "".join(f"<li>{_html_escape(f.get('suggestion'))}</li>" for f in fixes) or "<li>No suggested fixes recorded.</li>"
    generated = _html_escape(report.get("generated_at", "unknown"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SourcePack Report - {verdict}</title>
<style>
:root {{ color-scheme: light dark; --bg:#0f172a; --panel:#111827; --text:#e5e7eb; --muted:#94a3b8; --line:#334155; --pass:#16a34a; --warn:#d97706; --fail:#dc2626; }}
body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }}
main {{ max-width:1100px; margin:0 auto; padding:32px 20px 56px; }}
header, section {{ background:rgba(17,24,39,.92); border:1px solid var(--line); border-radius:18px; padding:22px; margin:16px 0; box-shadow:0 20px 50px rgba(0,0,0,.22); }}
h1 {{ margin:0 0 8px; font-size:32px; }}
h2 {{ margin-top:0; }}
.badge {{ display:inline-block; padding:8px 14px; border-radius:999px; font-weight:800; letter-spacing:.04em; }}
.badge.pass {{ background:var(--pass); }} .badge.warn {{ background:var(--warn); }} .badge.fail {{ background:var(--fail); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
.card {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:rgba(15,23,42,.72); }}
.label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.value {{ margin-top:6px; font-weight:650; overflow-wrap:anywhere; }}
table {{ width:100%; border-collapse:collapse; }} th, td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px; vertical-align:top; }} th {{ color:var(--muted); font-size:13px; }}
code {{ color:#bfdbfe; }} .muted {{ color:var(--muted); }} .severity.error {{ color:#fca5a5; }} .severity.warn {{ color:#fcd34d; }} .severity.info {{ color:#93c5fd; }}
</style>
</head>
<body><main>
<header>
<span class="badge {badge}">{_html_escape(report.get('light') or verdict)}</span>
<h1>SourcePack local report</h1>
<p>{_html_escape(report.get('headline'))}</p>
<p class="muted">Generated {generated}</p>
</header>
<section class="grid">
<div class="card"><div class="label">Verdict</div><div class="value">{_html_escape(verdict)}</div></div>
<div class="card"><div class="label">Reason type</div><div class="value">{_html_escape(report.get('reason_type') or 'none')}</div></div>
<div class="card"><div class="label">Commit policy</div><div class="value">{_html_escape(report.get('commit_policy') or 'allowed.')}</div></div>
<div class="card"><div class="label">Raw JSON</div><div class="value"><code>{_html_escape(raw_json_path)}</code></div></div>
</section>
<section><h2>Reason codes</h2><table><thead><tr><th>Code</th><th>Severity</th><th>Path</th><th>Explanation</th><th>Evidence / fix</th></tr></thead><tbody>{finding_rows(findings)}</tbody></table></section>
<section class="grid"><div class="card"><h2>Affected files</h2><ul>{affected_html}</ul></div><div class="card"><h2>Missing evidence</h2><ul>{missing_html}</ul></div><div class="card"><h2>Suggested fixes</h2><ul>{fixes_html}</ul></div></section>
<section><h2>Baseline and prompt trust</h2><p>SourcePack treats prompt context as helpful but non-authoritative. Diff checks are judged against the trusted local baseline packet.</p><div class="grid"><div class="card"><div class="label">Baseline state</div><div class="value">{_html_escape(report.get('baseline_state') or 'not recorded')}</div></div><div class="card"><div class="label">Baseline packet</div><div class="value"><code>{_html_escape(baseline_path or 'not recorded')}</code></div></div></div></section>
<section class="grid"><div class="card"><h2>Checked</h2><ul>{checked}</ul></div><div class="card"><h2>Not checked</h2><ul>{not_checked}</ul></div></section>
<section><h2>Next action</h2><p>{_html_escape(report.get('next_action'))}</p></section>
</main></body></html>"""


