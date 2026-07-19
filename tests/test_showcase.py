from __future__ import annotations

import json
import re
import subprocess
import tarfile
from pathlib import Path


from tools import generate_showcase_data

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "showcase" / "showcase-data.json"


def load_data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_generator_invokes_real_canonical_sourcepack_judgment(monkeypatch):
    calls = []
    real = generate_showcase_data.judge_repo_change

    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(generate_showcase_data, "judge_repo_change", wrapped)
    data = generate_showcase_data.build_showcase_data()

    assert len(calls) == 2
    assert calls[0][0][0] == calls[1][0][0]
    assert data["fail"]["verdict"] == "FAIL"
    assert data["pass"]["verdict"] == "PASS"


def test_generated_fail_fields_are_canonical_and_remediation_instruction_uses_supported_evidence():
    data = load_data()
    fresh = generate_showcase_data.build_showcase_data()

    assert data["fail"]["verdict"] == "FAIL"
    assert data["fail"]["reason_code"] == "unsupported_dependency"
    assert data["fail"]["missing_dependency"] == "fastapi"
    assert data["fail"]["repository_declared_dependency"] == "flask"
    assert data["fail"]["missing_evidence"] == "fastapi dependency declaration"
    assert data["fail"]["message"] == fresh["fail"]["message"]
    assert data["fail"]["remediation_summary"] == fresh["fail"]["remediation_summary"]
    instruction = data["fail"]["remediation_agent_instruction"]

    assert instruction == fresh["fail"]["remediation_agent_instruction"]
    assert "flask" in instruction.lower()
    assert "repository-supported flask dependency" in instruction.lower()
    assert "instead of fastapi" in instruction.lower()
    assert "repository evidence" not in instruction.lower()
    assert 'fastapi"' not in instruction.lower()


def test_request_uses_existing_framework_and_correction_preserves_health_endpoint():
    data = load_data()
    request = data["scenario"]["human_request"]
    corrected = data["scenario"]["corrected_flask_code"]

    assert request == "Add a health endpoint using the repository’s existing web framework."
    assert "FastAPI" not in request
    assert "existing web framework" in request
    assert "@app.get('/health')" in corrected
    assert "jsonify(status='ok')" in corrected
    assert "from flask import" in corrected
    assert "fastapi" not in corrected.lower()


def test_corrected_scenario_passes_and_change_supported_is_presentation_only():
    data = load_data()
    reason_codes = (ROOT / "src" / "sourcepack" / "reason_codes.py").read_text(encoding="utf-8")
    findings = json.dumps({"fail": data["fail"], "pass": data["pass"]})

    assert data["pass"]["verdict"] == "PASS"
    assert data["pass"]["blocking_finding_count"] == 0
    assert data["pass"]["supported_dependency"] == "flask"
    assert data["presentation"]["label"] == "change_supported"
    assert data["presentation"]["derived_from"] == "canonical PASS with zero blocking findings"
    assert "change_supported" not in reason_codes
    assert "change_supported" not in findings


def test_fixture_generation_leaves_checkout_unchanged_and_has_no_temp_paths():
    before = subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    data = generate_showcase_data.build_showcase_data()
    after = subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    rendered = json.dumps(data, sort_keys=True)

    assert after == before
    assert not re.search(r"/tmp/|/var/folders/|sourcepack-showcase-|[A-Z]:\\\\", rendered)


def test_supported_evidence_does_not_fall_back_to_hardcoded_success(tmp_path: Path):
    report = {"baseline_packet_path": ".sourcepack/baseline/builds/missing/packet"}

    try:
        generate_showcase_data._supported_evidence(tmp_path, report, "flask")
    except RuntimeError as exc:
        assert "canonical baseline reality_map.json is unavailable" in str(exc)
    else:
        raise AssertionError("supported evidence must fail when canonical evidence is unavailable")


def test_supported_evidence_requires_expected_dependency_and_manifest(tmp_path: Path):
    packet = tmp_path / ".sourcepack" / "baseline" / "builds" / "one" / "packet"
    packet.mkdir(parents=True)
    (packet / "reality_map.json").write_text(json.dumps({"detected_dependencies": [], "confirmed_files": ["requirements.txt"]}), encoding="utf-8")

    try:
        generate_showcase_data._supported_evidence(tmp_path, {"baseline_packet_path": ".sourcepack/baseline/builds/one/packet"}, "flask")
    except RuntimeError as exc:
        assert "does not verify supported dependency: flask" in str(exc)
    else:
        raise AssertionError("supported evidence must fail when Flask is absent from canonical evidence")


def test_committed_json_matches_freshly_regenerated_stable_fields():
    assert load_data() == generate_showcase_data.build_showcase_data()


def test_showcase_assets_readme_disclosure_and_workflow():
    html = (ROOT / "docs" / "showcase" / "index.html").read_text(encoding="utf-8")
    for asset in re.findall(r'(?:href|src)="([^"]+)"', html):
        if asset.startswith(("http://", "https://", "#")):
            continue
        assert (ROOT / "docs" / "showcase" / asset).exists(), asset

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://joshuavetos.github.io/sourcepack/" in readme
    assert "does not execute SourcePack in the browser" in readme
    assert "This browser walkthrough uses data generated by the real SourcePack judgment engine. SourcePack is not executing in your browser." in html
    assert 'data-field="fail.repository_declared_dependency"' in html
    assert 'data-field="fail.missing_dependency"' in html
    assert 'data-field="fail.missing_evidence"' in html
    assert 'data-field="pass.supported_dependency"' in html

    workflow = (ROOT / ".github" / "workflows" / "pages-showcase.yml").read_text(encoding="utf-8")
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "github-pages" in workflow
    assert re.search(r"path:\s*docs/showcase\b", workflow)
    assert "path: ." not in workflow


def test_pages_artifact_contains_only_showcase_files(tmp_path: Path):
    artifact = tmp_path / "artifact.tar"
    subprocess.run(["tar", "-cf", str(artifact), "-C", str(ROOT / "docs" / "showcase"), "."], check=True)
    with tarfile.open(artifact) as tar:
        names = {member.name for member in tar.getmembers() if member.isfile()}
    assert names == {"./index.html", "./showcase.css", "./showcase.js", "./showcase-data.json"}
