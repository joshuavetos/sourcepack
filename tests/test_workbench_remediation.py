import json
from pathlib import Path

from sourcepack import workbench
from sourcepack.reports.json import normalized_finding, traffic_report
from sourcepack.workbench import WORKBENCH_EXCERPT_FILE_LIMIT_BYTES, _dashboard_payload


def test_workbench_surfaces_copyable_remediation_without_html_injection():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "Agent correction instruction" in ui
    assert "Copy correction prompt" in ui
    assert "data.report?.remediation?.agent_prompt" in ui
    assert "navigator.clipboard.writeText" in ui
    assert "innerHTML" not in ui
    assert "textContent" in ui
    assert "Refresh Review" not in ui
    assert "Reload Latest Report" in ui
    assert "replayRes.status === 'success' ? 'verified'" not in ui
    assert "verdict-card neutral" in ui
    assert "Affected File Context" in ui
    assert "Current worktree context; may differ" in ui
    assert "finding?.reason_code ||" in ui
    assert "report?.reason_code ||" in ui


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
