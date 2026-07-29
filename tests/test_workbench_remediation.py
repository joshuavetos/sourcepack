import json
from pathlib import Path

from sourcepack import workbench
from sourcepack.reports.json import normalized_finding, traffic_report
from sourcepack.workbench import WORKBENCH_EXCERPT_FILE_LIMIT_BYTES, _dashboard_payload, _workbench_action


def test_workbench_surfaces_copyable_remediation_without_html_injection():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "Agent correction instruction" in ui
    assert "Copy correction prompt" in ui
    assert "action.action_type === 'copy_prompt'" in ui
    assert "typeof action.prompt === 'string'" in ui
    assert "navigator.clipboard.writeText" in ui
    assert "innerHTML" not in ui
    assert "textContent" in ui
    assert "Refresh Review" not in ui
    assert "Reload Latest Report" in ui
    assert "replayRes.status === 'success' ? 'verified'" not in ui
    assert "verdict-card neutral" in ui
    assert "Affected File Context" in ui
    assert "Current worktree context; may differ" in ui
    assert "renderAction(action)" in ui


def test_workbench_report_model_surfaces_real_unsupported_dependency_shape(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\nfrom fastapi import FastAPI\napp = Flask(__name__)\nfastapi_app = FastAPI()\n",
        encoding="utf-8",
    )
    report = traffic_report(
        "FAIL",
        findings=[
            normalized_finding(
                "unsupported_dependency",
                "error",
                "dependency",
                "app.py imports FastAPI, but FastAPI is not declared.",
                "app.py",
                "requirements.txt declares Flask; FastAPI declaration is absent",
                "Use Flask for the health endpoint instead of FastAPI.",
            )
        ],
    )
    report["findings"][0]["id"] = "spkf_stablefinding123"
    report["findings"][0]["reason_code"] = "unsupported_dependency"
    report["blockers"] = [report["findings"][0]]
    report["reason_code_evidence"] = {"unsupported_dependency": [report["evidence_items"][0]["evidence_id"]]}
    report["raw_patch_judgment"] = {"patch_judgment_schema_version": "1.0", "verdict": "FAIL", "modified_files": ["app.py"]}
    latest = tmp_path / ".sourcepack" / "reports" / "latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps(report), encoding="utf-8")

    payload = _dashboard_payload(tmp_path, "report")

    assert payload["report"]["verdict"] == "FAIL"
    assert payload["report"]["findings"][0]["id"] == "spkf_stablefinding123"
    assert payload["report"]["findings"][0]["reason_code"] == "unsupported_dependency"
    assert payload["report"]["findings"][0]["path"] == "app.py"
    assert "FastAPI" in payload["report"]["findings"][0]["message"]
    assert "Flask" in payload["report"]["findings"][0]["evidence"]
    assert "absent" in payload["report"]["findings"][0]["evidence"]
    assert "FastAPI" in payload["report"]["remediation"]["agent_prompt"]
    excerpt = payload["proposed_change"]["excerpts"][0]
    assert excerpt["path"] == "app.py"
    assert excerpt["status"] == "available"
    assert any("FastAPI" in line["text"] for line in excerpt["lines"])


def test_workbench_context_excerpt_bounds_oversized_files(tmp_path: Path):
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n" + ("x" * WORKBENCH_EXCERPT_FILE_LIMIT_BYTES), encoding="utf-8")
    report = traffic_report(
        "FAIL",
        findings=[normalized_finding("unsupported_dependency", "error", "dependency", "FastAPI is absent", "app.py", "fastapi")],
    )
    report["raw_patch_judgment"] = {"patch_judgment_schema_version": "1.0", "verdict": "FAIL", "modified_files": ["app.py"]}
    latest = tmp_path / ".sourcepack" / "reports" / "latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps(report), encoding="utf-8")

    excerpt = _dashboard_payload(tmp_path, "report")["proposed_change"]["excerpts"][0]

    assert excerpt["status"] == "truncated"
    assert excerpt["byte_limit"] == WORKBENCH_EXCERPT_FILE_LIMIT_BYTES
    assert any("FastAPI" in line["text"] for line in excerpt["lines"])


def test_workbench_action_metadata_is_deterministic_for_canonical_states():
    prompt = "Replace the unsupported dependency with the repository-supported dependency."
    cases = [
        ({"verdict": "PASS", "raw_patch_judgment": {"modified_files": ["app.py"]}}, {"action_type": "run_review", "label": "Run Review Again", "reason": "change_supported", "target_surface": "workbench_review", "available": True}),
        ({"verdict": "PASS", "raw_patch_judgment": {"modified_files": []}}, {"action_type": "run_review", "label": "Run Review Again", "reason": "no_diff", "target_surface": "workbench_review", "available": True}),
        ({"verdict": "WARN", "warnings": [{"reason_code": "uncertain_support"}], "remediation": {"agent_prompt": prompt}}, {"action_type": "copy_prompt", "label": "Copy Correction Prompt", "reason": "uncertain_support", "target_surface": "correction_prompt", "available": True, "prompt": prompt}),
        ({"verdict": "FAIL", "blockers": [{"reason_code": "unsupported_dependency"}], "remediation": {"agent_prompt": prompt}}, {"action_type": "copy_prompt", "label": "Copy Correction Prompt", "reason": "unsupported_dependency", "target_surface": "correction_prompt", "available": True, "prompt": prompt}),
        ({"verdict": "FAIL", "blockers": [{"reason_code": "unsupported_dependency"}]}, {"action_type": "copy_prompt", "label": "Copy Correction Prompt", "reason": "unsupported_dependency", "target_surface": "correction_prompt", "available": False}),
        ({"verdict": "FAIL", "blockers": None, "warnings": None, "findings": None, "remediation": None}, {"action_type": "copy_prompt", "label": "Copy Correction Prompt", "reason": "remediation_unavailable", "target_surface": "correction_prompt", "available": False}),
        ({"verdict": "UNKNOWN"}, {"action_type": "none", "label": "Action Unavailable", "reason": "unsupported_verdict", "target_surface": "none", "available": False}),
    ]
    for report, expected in cases:
        assert _workbench_action(report) == expected
        assert _workbench_action(report) == expected


def test_workbench_client_consumes_backend_action_without_selection_logic():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    render_action = ui.split("function renderAction(action)", 1)[1].split("async function copyPrompt()", 1)[0]
    set_operation = ui.split("function setOperation(state, message)", 1)[1].split("function transitionMessage", 1)[0]
    run_review = ui.split("async function runReview()", 1)[1].split("async function load()", 1)[0]

    assert "const action = reportRes.action" in ui
    assert "renderAction(action)" in ui
    assert "runButton.hidden = true; runButton.disabled = true" in render_action
    assert "$(id).hidden = true; $(id).disabled = true" in render_action
    assert "if (copyAvailable) { $(id).hidden = false; $(id).disabled = false" in render_action
    assert "if (available && action?.action_type === 'run_review')" in render_action
    assert "renderAction(currentAction)" in set_operation
    assert "renderAction(data.action); await load()" in run_review
    assert "completedOnce" not in ui
    assert "'Run Review Again'" not in ui
    assert "function reasonOf(" not in ui
    assert "function explain(" not in ui
    assert "reviewedPaths(report)" not in ui
    assert "data.report?.remediation?.agent_prompt" not in ui


def test_workbench_empty_agent_prompt_hides_copy_controls_and_prevents_empty_copy():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "if (!currentPrompt)" in ui
    assert "No correction prompt is required for this PASS report." in ui
    assert "$(id).hidden = true; $(id).disabled = true" in ui
    assert "$(id).hidden = false; $(id).disabled = false" in ui
    assert "promptDetails.hidden = !copyAvailable" in ui
    assert "await navigator.clipboard.writeText(currentPrompt)" in ui


def test_workbench_evidence_cards_render_readable_fields_without_json_fallback():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "function evidenceFields(ev)" in ui
    assert "ev.fact || ev.title || ev.kind || 'Repository fact'" in ui
    assert "ev.checked_status || ev.status" in ui
    assert "ev.evidence_source || ev.source || ev.source_type" in ui
    assert "ev.evidence_class" in ui
    assert "JSON.stringify(ev)" not in ui.split("function evidenceText(ev)", 1)[1].split("function evidenceItems(report)", 1)[0]


def test_workbench_technical_report_toggle_has_no_stray_empty_object_text():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "{} Show Technical Report" not in ui
    assert "{} Hide Technical Report" not in ui
    assert "id=\"toggle-report\" type=\"button\">Show Technical Report</button>" in ui
    assert "? 'Hide Technical Report' : 'Show Technical Report'" in ui
