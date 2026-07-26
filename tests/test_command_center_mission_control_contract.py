from pathlib import Path


CLIENT = Path("src/sourcepack/workbench_static/command-center-aggregate.js")


def test_mission_control_renders_canonical_scores_and_priorities() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    for token in (
        "command-center-intelligence",
        "command-center-scores",
        "command-center-priorities",
        "scores.trust",
        "scores.automation",
        "scores.product_breadth",
        "scores.report_depth",
        "snapshot.priority_actions",
    ):
        assert token in text


def test_mission_control_uses_live_capabilities_and_activity() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    assert "snapshot.capabilities" in text
    assert "snapshot.activity" in text
    assert 'document.getElementById("capability-mini")' in text
    assert 'document.getElementById("timeline")' in text
    assert "Adversarial Lab" in text
    assert "Integration Hub" in text
    assert "Agent Gateway" in text


def test_mission_control_preserves_single_snapshot_boundary() -> None:
    text = CLIENT.read_text(encoding="utf-8")

    assert text.count('/api/command-center/v1/snapshot') == 1
    for legacy in (
        "/api/dashboard/v1/overview",
        "/api/dashboard/v1/report",
        "/api/dashboard/v1/policy",
        "/api/status",
    ):
        assert legacy not in text
