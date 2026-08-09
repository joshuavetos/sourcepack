import json
import re
from pathlib import Path

from sourcepack import workbench
from sourcepack.command_center import build_command_center_snapshot
from sourcepack.reports.json import normalized_finding, traffic_report
from sourcepack.workbench import WORKBENCH_EXCERPT_FILE_LIMIT_BYTES, _dashboard_payload, _workbench_action


def test_workbench_surfaces_copyable_remediation_without_html_injection():
    ui = (workbench.STATIC_ROOT / "index.html").read_text() + (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    assert "Agent correction instruction" in ui
    assert "Copy correction prompt" in ui
    assert "action.action_type === 'copy_prompt'" in ui
    assert "navigator.clipboard.writeText" in ui
    assert "innerHTML" not in ui
    assert "textContent" in ui
    assert "Reload Latest Report" in ui
    assert "renderChange(snapshot)" in ui
    assert "renderEvidence(snapshot)" in ui
    assert "renderCorrectionSummary(snapshot)" in ui


def test_workbench_removes_supplied_token_from_browser_url():
    ui = (workbench.STATIC_ROOT / "index.html").read_text()
    assert "if (suppliedToken)" in ui
    assert "history.replaceState({}, document.title, location.pathname + location.hash)" in ui


def test_priority_navigation_mapping_points_only_to_existing_elements():
    html = (workbench.STATIC_ROOT / "index.html").read_text()
    client = (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    mapping = re.search(r"const SURFACE_TARGETS = \{([^}]+)\}", client)
    assert mapping is not None
    targets = re.findall(r': "([^"]+)"', mapping.group(1))
    assert targets
    for target in targets:
        assert f'id="{target}"' in html


def test_priority_actions_fail_closed_and_copy_failure_is_visible():
    ui = (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    assert "PRIORITY_ACTION_IDS.has(item.id)" in ui
    assert "button.disabled = !PRIORITY_ACTION_IDS.has(item.id)" in ui
    assert 'showActionError("Action unavailable: unsupported snapshot metadata")' in ui
    assert "Clipboard unavailable. Command:" in ui

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

    snapshot = build_command_center_snapshot(tmp_path)
    assert snapshot["workbench"]["evidence_cards"][0]["body"] == "requirements.txt declares Flask; FastAPI declaration is absent"


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
    ui = (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    assert "snapshot.workbench.review_action" in ui
    assert "reportRes.action" not in ui
    assert "function reasonOf(" not in ui


def test_workbench_empty_agent_prompt_hides_copy_controls_and_prevents_empty_copy():
    ui = (workbench.STATIC_ROOT / "index.html").read_text() + (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    assert "if (!currentPrompt) return" in ui
    assert "await navigator.clipboard.writeText(currentPrompt)" in ui
    assert "action.available" in ui
    assert "typeof action.prompt === 'string'" in ui
    assert "action.prompt.trim() !== ''" in ui
    assert "$(id).hidden = !copyAvailable" in ui
    assert "$('correction-prompt').closest('details').hidden = !copyAvailable" in ui
    assert "finally { $('run-review').disabled=false; }" not in ui


def test_workbench_uses_safe_text_rendering_without_json_html_injection():
    ui = (workbench.STATIC_ROOT / "index.html").read_text() + (workbench.STATIC_ROOT / "command-center-aggregate.js").read_text()
    assert ".innerHTML" not in ui
    assert ".textContent" in ui


def test_workbench_technical_report_toggle_has_no_stray_empty_object_text():
    ui = (workbench.STATIC_ROOT / "index.html").read_text()
    assert "{} Show Technical Report" not in ui
    assert 'id="toggle-report" type="button">Show Technical Report</button>' in ui
    assert "'Hide Technical Report':'Show Technical Report'" in ui
