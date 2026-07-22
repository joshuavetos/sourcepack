from __future__ import annotations

import json

from sourcepack.analysis import AnalysisStatus
from sourcepack.reports.json import normalized_finding, traffic_report, write_user_report


def _proposed_dependency_finding() -> dict:
    return normalized_finding(
        "declared_dependency",
        "warn",
        "uncertainty",
        "axios is declared in the same patch and requires review",
        path="src/app.ts",
        evidence="axios",
        analysis_status=AnalysisStatus.UNKNOWN.value,
        evidence_class="proposed_state",
        trust_status="untrusted_until_accepted",
        source_path="package.json",
        baseline_or_proposed="proposed",
        modified_by_patch=True,
        extraction_method="dependency_resolver",
    )


def test_provenance_survives_normalized_finding_and_traffic_report():
    report = traffic_report("WARN", findings=[_proposed_dependency_finding()])

    finding = report["findings"][0]
    assert finding["analysis_status"] == AnalysisStatus.UNKNOWN.value
    assert finding["evidence_class"] == "proposed_state"
    assert finding["trust_status"] == "untrusted_until_accepted"
    assert finding["source_path"] == "package.json"
    assert finding["baseline_or_proposed"] == "proposed"
    assert finding["modified_by_patch"] is True
    assert finding["extraction_method"] == "dependency_resolver"


def test_provenance_survives_warning_projection_and_replay_bundle():
    report = traffic_report("WARN", findings=[_proposed_dependency_finding()])

    warning = report["warnings"][0]
    replay_finding = report["replay_bundle"]["findings"][0]
    for finding in (warning, replay_finding):
        assert finding["analysis_status"] == AnalysisStatus.UNKNOWN.value
        assert finding["evidence_class"] == "proposed_state"
        assert finding["trust_status"] == "untrusted_until_accepted"
        assert finding["modified_by_patch"] is True

    evidence_metadata = report["evidence_items"][0]["metadata"]
    assert evidence_metadata["analysis_status"] == AnalysisStatus.UNKNOWN.value
    assert evidence_metadata["evidence_class"] == "proposed_state"
    assert evidence_metadata["trust_status"] == "untrusted_until_accepted"
    assert evidence_metadata["modified_by_patch"] is True


def test_provenance_survives_json_artifact_write(tmp_path):
    report = traffic_report("WARN", findings=[_proposed_dependency_finding()])

    write_user_report(tmp_path, report, "diff")

    written = json.loads((tmp_path / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
    finding = written["findings"][0]
    assert finding["analysis_status"] == AnalysisStatus.UNKNOWN.value
    assert finding["evidence_class"] == "proposed_state"
    assert finding["trust_status"] == "untrusted_until_accepted"
    assert finding["source_path"] == "package.json"
    assert finding["modified_by_patch"] is True


def test_legacy_findings_still_receive_default_evidence_normalization():
    finding = normalized_finding(
        "declared_dependency",
        "warn",
        "review",
        "axios was added to dependency files.",
        evidence="axios",
    )

    report = traffic_report("WARN", findings=[finding])
    normalized = report["findings"][0]

    assert normalized["evidence_class"] == "dependency_manifest"
    assert normalized["checked_status"] == "partially_checked"
