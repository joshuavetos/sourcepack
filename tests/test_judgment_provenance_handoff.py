from sourcepack.finding_identity import attach_finding_id
from sourcepack.judgment import patch_report_to_traffic
from sourcepack.reports.json import normalized_finding, traffic_report


def _finding(report, reason_code):
    return next(f for f in report["findings"] if f["id"] == reason_code)


def test_same_patch_dependency_warning_restores_proposed_state_provenance():
    report = patch_report_to_traffic(
        {
            "verdict": "WARN",
            "uncertainties": [
                {
                    "id": "declared_dependency",
                    "message": "requests is declared in the same patch and requires review",
                    "path": "src/app.py",
                    "evidence": "requests",
                }
            ],
        }
    )

    finding = _finding(report, "declared_dependency")
    assert finding["analysis_status"] == "UNKNOWN"
    assert finding["evidence_class"] == "proposed_state"
    assert finding["trust_status"] == "untrusted_until_accepted"
    assert finding["modified_by_patch"] is True
    assert finding["source_kind"] == "dependency_manifest"
    assert finding["source_path"] == "src/app.py"

    replay = _finding(report["replay_bundle"], "declared_dependency")
    assert replay["evidence_class"] == "proposed_state"
    assert replay["trust_status"] == "untrusted_until_accepted"


def test_same_patch_command_warning_restores_proposed_state_provenance():
    report = patch_report_to_traffic(
        {
            "verdict": "WARN",
            "uncertainties": [
                {
                    "id": "declared_command",
                    "message": "script added in patch",
                    "evidence": "npm run build",
                }
            ],
        }
    )

    finding = _finding(report, "declared_command")
    assert finding["analysis_status"] == "UNKNOWN"
    assert finding["evidence_class"] == "proposed_state"
    assert finding["trust_status"] == "untrusted_until_accepted"
    assert finding["modified_by_patch"] is True
    assert finding["source_kind"] == "command_manifest"
    assert finding["source_path"] == "package.json"


def test_unsupported_dependency_cannot_look_like_manifest_support():
    report = patch_report_to_traffic(
        {
            "verdict": "FAIL",
            "unsupported_dependencies": ["ghostlib"],
        }
    )

    finding = _finding(report, "unsupported_dependency")
    assert finding["analysis_status"] == "UNSUPPORTED"
    assert finding["evidence_class"] == "analysis_state"
    assert finding["trust_status"] == "no_supporting_evidence"
    assert finding["modified_by_patch"] is False


def test_explicit_resolver_provenance_is_never_overwritten():
    finding = normalized_finding(
        "declared_dependency",
        "warn",
        "uncertainty",
        "explicit resolver record",
        evidence="requests",
        analysis_status="CONTRADICTED",
        evidence_class="caller_designated",
        trust_status="explicit_override",
        source_path="caller.json",
        source_kind="caller_designated",
        modified_by_patch=False,
    )

    report = traffic_report("WARN", findings=[finding])
    final = _finding(report, "declared_dependency")
    assert final["analysis_status"] == "CONTRADICTED"
    assert final["evidence_class"] == "caller_designated"
    assert final["trust_status"] == "explicit_override"
    assert final["source_path"] == "caller.json"
    assert final["source_kind"] == "caller_designated"
    assert final["modified_by_patch"] is False


def test_finding_identity_remains_stable_when_provenance_is_restored():
    plain = attach_finding_id(
        {
            "id": "declared_command",
            "severity": "warn",
            "category": "uncertainty",
            "message": "script added in patch",
            "evidence": "npm run build",
        }
    )
    explicit = attach_finding_id(
        {
            "id": "declared_command",
            "severity": "warn",
            "category": "uncertainty",
            "message": "script added in patch",
            "evidence": "npm run build",
            "analysis_status": "UNKNOWN",
            "evidence_class": "proposed_state",
            "trust_status": "untrusted_until_accepted",
            "modified_by_patch": True,
            "source_kind": "command_manifest",
            "source_path": "package.json",
        }
    )

    assert plain["finding_id"] == explicit["finding_id"]
