from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sourcepack.baseline import build_current_baseline
from sourcepack.judgment import judge_repo_change

HUMAN_REQUEST = "Add a health endpoint using the repository’s existing web framework."
ORIGINAL_FLASK_CODE = "from flask import Flask\n\napp = Flask(__name__)\n"
AI_FASTAPI_CODE = "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n"
CORRECTED_FLASK_CODE = "from flask import Flask, jsonify\n\napp = Flask(__name__)\n\n\n@app.get('/health')\ndef health():\n    return jsonify(status='ok')\n"

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "showcase" / "showcase-data.json"


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _write_project(repo: Path, app_code: str) -> None:
    (repo / "app.py").write_text(app_code, encoding="utf-8")
    (repo / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")


def _first_blocker(report: dict[str, Any], reason_code: str) -> dict[str, Any]:
    for finding in report.get("blockers", []) + report.get("findings", []):
        if finding.get("reason_code") == reason_code or finding.get("id") == reason_code:
            return finding
    raise RuntimeError(f"canonical finding not found: {reason_code}")


def _supported_evidence(repo: Path, report: dict[str, Any], dependency: str) -> dict[str, str]:
    packet_path = report.get("baseline_packet_path")
    if not isinstance(packet_path, str) or not packet_path:
        raise RuntimeError("canonical report does not identify a baseline packet path")
    packet = repo / packet_path
    reality_map_path = packet / "reality_map.json"
    try:
        reality_map = json.loads(reality_map_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError("canonical baseline reality_map.json is unavailable") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("canonical baseline reality_map.json is malformed") from exc

    detected = reality_map.get("detected_dependencies")
    confirmed_files = reality_map.get("confirmed_files")
    normalized_deps = {str(dep).lower() for dep in detected} if isinstance(detected, list) else set()
    normalized_files = {str(path).replace("\\", "/") for path in confirmed_files} if isinstance(confirmed_files, list) else set()
    if dependency.lower() not in normalized_deps or "requirements.txt" not in normalized_files:
        raise RuntimeError(f"canonical baseline evidence does not verify supported dependency: {dependency}")
    return {"dependency": dependency.lower(), "evidence": "requirements.txt declares flask"}


def _showcase_remediation_instruction(supported_dependency: str, unsupported_dependency: str) -> str:
    return (
        "Revise the change to use the repository-supported "
        f"{supported_dependency} dependency instead of {unsupported_dependency}."
    )


def build_showcase_data() -> dict[str, Any]:
    checkout = Path.cwd().resolve()
    with tempfile.TemporaryDirectory(prefix="sourcepack-showcase-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        _run_git(repo, "init", "-q")
        _run_git(repo, "config", "user.email", "showcase@example.invalid")
        _run_git(repo, "config", "user.name", "SourcePack Showcase")
        _write_project(repo, ORIGINAL_FLASK_CODE)
        _run_git(repo, "add", "app.py", "requirements.txt")
        _run_git(repo, "commit", "-qm", "trusted flask baseline")
        build_current_baseline(repo, quiet=True)
        _run_git(repo, "add", ".sourcepack")
        _run_git(repo, "commit", "-qm", "trust sourcepack baseline")

        (repo / "app.py").write_text(AI_FASTAPI_CODE, encoding="utf-8")
        fail = judge_repo_change(repo, allow_missing_baseline_init=False)
        fail_report = fail.report
        fail_finding = _first_blocker(fail_report, "unsupported_dependency")
        remediation = fail_finding.get("remediation") or {}
        if not remediation:
            raise RuntimeError("canonical unsupported_dependency finding lacks remediation")

        (repo / "app.py").write_text(CORRECTED_FLASK_CODE, encoding="utf-8")
        passed = judge_repo_change(repo, allow_missing_baseline_init=False)
        pass_report = passed.report
        supported_flask = _supported_evidence(repo, pass_report, "flask")

        data = {
            "schema_version": "sourcepack.showcase.v1",
            "scenario": {
                "human_request": HUMAN_REQUEST,
                "original_flask_code": ORIGINAL_FLASK_CODE,
                "ai_fastapi_code": AI_FASTAPI_CODE,
                "corrected_flask_code": CORRECTED_FLASK_CODE,
            },
            "fail": {
                "verdict": fail.verdict,
                "reason_code": fail_finding.get("reason_code") or fail_finding.get("id"),
                "message": fail_finding.get("message"),
                "missing_dependency": "fastapi",
                "repository_evidence": fail_finding.get("evidence"),
                "repository_declared_dependency": supported_flask["dependency"],
                "missing_evidence": "fastapi dependency declaration",
                "remediation_summary": remediation.get("summary"),
                "remediation_agent_instruction": _showcase_remediation_instruction(
                    supported_flask["dependency"], "fastapi"
                ),
            },
            "pass": {
                "verdict": passed.verdict,
                "blocking_finding_count": len(pass_report.get("blockers", [])),
                "supported_dependency": supported_flask["dependency"],
                "supported_dependency_evidence": supported_flask["evidence"],
            },
            "presentation": {
                "label": "change_supported" if passed.verdict == "PASS" and len(pass_report.get("blockers", [])) == 0 else None,
                "derived_from": "canonical PASS with zero blocking findings",
            },
        }
        if Path.cwd().resolve() != checkout:
            raise RuntimeError("showcase generator changed the invoking checkout working directory")

    if Path.cwd().resolve() != checkout:
        raise RuntimeError("showcase generator changed the invoking checkout working directory")
    return data


def write_showcase_data(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    data = build_showcase_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    write_showcase_data()
