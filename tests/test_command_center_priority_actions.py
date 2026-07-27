from __future__ import annotations

import pytest

from sourcepack.command_center import Capability, _priority_action, _priority_actions


def test_priority_actions_include_complete_backend_owned_metadata() -> None:
    actions = _priority_actions(
        [
            Capability(
                "hook",
                "Automatic Git enforcement",
                "Agent Gateway",
                "READY_TO_BUILD",
                "manual review only",
                "install_hooks",
            )
        ],
        report=None,
        baseline={"state": "missing"},
        policy={"resolution_status": "FAIL"},
    )

    by_id = {item["id"]: item for item in actions}

    assert by_id["create_baseline"] == {
        "id": "create_baseline",
        "priority": "P0",
        "label": "Copy baseline command",
        "action_type": "copy_command",
        "command": "sourcepack baseline .",
        "target_surface": None,
        "reason": "No trusted repository baseline exists.",
    }
    assert by_id["repair_policy"]["action_type"] == "navigate"
    assert by_id["repair_policy"]["target_surface"] == "policy"
    assert by_id["run_review"]["action_type"] == "run_review"
    assert by_id["run_review"]["command"] is None
    assert by_id["install_hooks"]["command"] == "sourcepack install-hook ."


def test_priority_action_metadata_preserves_navigation_and_planned_claim_scope() -> None:
    actions = _priority_actions(
        [
            Capability(
                "adversarial",
                "Adversarial case laboratory",
                "Adversarial Lab",
                "READY_TO_BUILD",
                "hardening plan exists; executable corpus not yet connected",
                "build_adversarial_runner",
            ),
            Capability(
                "integrations",
                "External agent integrations",
                "Integration Hub",
                "PLANNED",
                "no remote integrations are configured or claimed",
                "add_integration_adapter",
            ),
        ],
        report={"verdict": "PASS"},
        baseline={"state": "present"},
        policy={"resolution_status": "PASS"},
    )

    by_id = {item["id"]: item for item in actions}
    assert by_id["build_adversarial_runner"]["target_surface"] == "lab"
    assert by_id["build_adversarial_runner"]["reason"] == "hardening plan exists; executable corpus not yet connected"
    assert by_id["add_integration_adapter"]["target_surface"] == "integrations"
    assert by_id["add_integration_adapter"]["reason"] == "no remote integrations are configured or claimed"


def test_unknown_priority_action_is_rejected_instead_of_rendered_as_a_fallback() -> None:
    with pytest.raises(ValueError, match="Unknown Command Center priority action"):
        _priority_action(action_id="arbitrary_shell", priority="P0", reason="unsupported")
