from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .command_center_limits import MAX_LINE_CHARS, MAX_PROMPT_CHARS, MAX_STRING_CHARS

COMMAND_CENTER_SCHEMA_VERSION = "sourcepack.command_center.v1"
CAPABILITY_IDS = (
    "review",
    "baseline",
    "policy",
    "hook",
    "evidence",
    "replay",
    "adversarial",
    "integrations",
    "autonomy",
)
CAPABILITY_STATUSES = (
    "LIVE",
    "READY",
    "NEEDS_SETUP",
    "DEGRADED",
    "PARTIAL",
    "READY_TO_BUILD",
    "PLANNED",
)
ACTION_IDS = (
    "run_review",
    "resolve_findings",
    "repair_policy",
    "create_baseline",
    "refresh_baseline",
    "install_hooks",
    "build_adversarial_runner",
    "add_integration_adapter",
    "build_improvement_loop",
)
ACTION_TYPES = ("run_review", "navigate", "copy_command")
ACTION_PRIORITIES = ("P0", "P1", "P2", "P3")
TARGET_SURFACES = ("review", "policy", "lab", "integrations", "agents")
ACTION_TYPE_BY_ID = {
    "run_review": "run_review",
    "resolve_findings": "navigate",
    "repair_policy": "navigate",
    "create_baseline": "copy_command",
    "refresh_baseline": "copy_command",
    "install_hooks": "copy_command",
    "build_adversarial_runner": "navigate",
    "add_integration_adapter": "navigate",
    "build_improvement_loop": "navigate",
}
ACTION_PAYLOAD_BY_ID = {
    "run_review": (None, None),
    "resolve_findings": (None, "review"),
    "repair_policy": (None, "policy"),
    "create_baseline": ("sourcepack baseline .", None),
    "refresh_baseline": ("sourcepack baseline .", None),
    "install_hooks": ("sourcepack install-hook .", None),
    "build_adversarial_runner": (None, "lab"),
    "add_integration_adapter": (None, "integrations"),
    "build_improvement_loop": (None, "agents"),
}
CAPABILITY_ACTIONS_BY_ID = {
    "review": ("run_review",),
    "baseline": ("create_baseline", "refresh_baseline"),
    "policy": ("repair_policy",),
    "hook": ("install_hooks",),
    "evidence": (),
    "replay": (),
    "adversarial": ("build_adversarial_runner",),
    "integrations": ("add_integration_adapter",),
    "autonomy": ("build_improvement_loop",),
}
ACTIVITY_TYPES = ("repository", "baseline", "policy", "review", "error")
REQUIRED_ACTIVITY_SEQUENCE = ("repository", "baseline", "policy", "review")
VERDICTS = ("PASS", "WARN", "FAIL")


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def command_center_snapshot_schema() -> dict[str, Any]:
    nullable_string = _nullable({"type": "string", "maxLength": MAX_STRING_CHARS})
    nullable_action_id = _nullable({"type": "string", "enum": list(ACTION_IDS)})
    nullable_target_surface = _nullable({"type": "string", "enum": list(TARGET_SURFACES)})
    nullable_object = _nullable({"type": "object"})
    capability = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "name", "surface", "status", "evidence", "action"],
        "properties": {
            "id": {"type": "string", "enum": list(CAPABILITY_IDS)},
            "name": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "surface": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "status": {"type": "string", "enum": list(CAPABILITY_STATUSES)},
            "evidence": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "action": nullable_action_id,
        },
    }
    priority_action = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "priority", "label", "action_type", "command", "target_surface", "reason"],
        "properties": {
            "id": {"type": "string", "enum": list(ACTION_IDS)},
            "priority": {"type": "string", "enum": list(ACTION_PRIORITIES)},
            "label": {"type": "string", "minLength": 1},
            "action_type": {"type": "string", "enum": list(ACTION_TYPES)},
            "command": nullable_string,
            "target_surface": nullable_target_surface,
            "reason": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
        },
    }
    activity = {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "message"],
        "properties": {
            "type": {"type": "string", "enum": list(ACTIVITY_TYPES)},
            "message": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
        },
    }
    review_action = {
        "type": "object",
        "additionalProperties": False,
        "required": ["action_type", "label", "reason", "target_surface", "available"],
        "properties": {
            "action_type": {"type": "string", "enum": ["run_review", "copy_prompt", "none"]},
            "label": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "reason": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "target_surface": {"type": "string", "enum": ["workbench_review", "correction_prompt", "none"]},
            "available": {"type": "boolean"},
            "prompt": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
        },
        "oneOf": [
            {
                "properties": {
                    "action_type": {"const": "run_review"},
                    "target_surface": {"const": "workbench_review"},
                    "available": {"const": True},
                },
                "not": {"required": ["prompt"]},
            },
            {
                "properties": {
                    "action_type": {"const": "copy_prompt"},
                    "target_surface": {"const": "correction_prompt"},
                    "available": {"const": True},
                },
                "required": ["prompt"],
            },
            {
                "properties": {
                    "action_type": {"const": "copy_prompt"},
                    "target_surface": {"const": "correction_prompt"},
                    "available": {"const": False},
                },
                "not": {"required": ["prompt"]},
            },
            {
                "properties": {
                    "action_type": {"const": "none"},
                    "target_surface": {"const": "none"},
                    "available": {"const": False},
                },
                "not": {"required": ["prompt"]},
            },
        ],
    }
    excerpt_line = {
        "type": "object",
        "additionalProperties": False,
        "required": ["number", "text"],
        "properties": {
            "number": {"type": "integer", "minimum": 1},
            "text": {"type": "string", "maxLength": MAX_LINE_CHARS},
        },
    }
    excerpt = {
        "type": "object",
        "additionalProperties": False,
        "required": ["path", "source", "status", "lines"],
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "source": {"const": "current_worktree_file_listed_by_canonical_report"},
            "status": {"type": "string", "enum": ["available", "truncated", "omitted"]},
            "reason": {"type": "string", "minLength": 1},
            "byte_limit": {"type": "integer", "minimum": 1},
            "lines": {"type": "array", "items": excerpt_line},
        },
        "allOf": [
            {
                "if": {"properties": {"status": {"const": "omitted"}}},
                "then": {"required": ["reason"]},
            },
            {
                "if": {"properties": {"status": {"enum": ["available", "truncated"]}}},
                "then": {"required": ["byte_limit"]},
            },
        ],
    }
    proposed_change = {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "source", "paths", "excerpts"],
        "properties": {
            "schema_version": {"const": "sourcepack.dashboard.proposed_change.v1"},
            "source": {"const": "traffic_report.raw_patch_judgment plus bounded current worktree excerpt"},
            "paths": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS}},
            "excerpts": {"type": "array", "items": excerpt},
        },
    }
    evidence_card = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "tag", "body", "problem"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "tag": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "body": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "problem": {"type": "boolean"},
        },
    }
    correction_row = {
        "type": "object",
        "additionalProperties": False,
        "required": ["label", "value"],
        "properties": {
            "label": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
            "value": {"type": "string", "minLength": 1, "maxLength": MAX_STRING_CHARS},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.sourcepack.local/command-center.v1.snapshot.schema.json",
        "title": "SourcePack Command Center v1 Snapshot",
        "description": "Versioned application contract for the authenticated local Command Center snapshot.",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "sourcepack_version",
            "repository",
            "display",
            "state",
            "posture",
            "scores",
            "capabilities",
            "priority_actions",
            "activity",
            "available_artifacts",
            "workbench",
            "artifacts",
            "bounds",
        ],
        "properties": {
            "schema_version": {"const": COMMAND_CENTER_SCHEMA_VERSION},
            "sourcepack_version": {"type": "string", "minLength": 1},
            "repository": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "git"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "git": {"type": "object"},
                },
            },
            "display": {
                "type": "object", "additionalProperties": False,
                "required": ["verdict_class", "verdict_icon", "verdict_title", "verdict_label", "findings_summary", "navigation_findings_summary", "evidence_summary", "branch", "version_label", "report_time"],
                "properties": {
                    "verdict_class": {"enum": ["pass", "warn", "fail", "neutral"]},
                    "verdict_icon": {"type": "string"}, "verdict_title": {"type": "string"},
                    "verdict_label": {"type": "string"}, "findings_summary": {"type": "string"},
                    "navigation_findings_summary": {"type": "string"}, "evidence_summary": {"type": "string"},
                    "branch": nullable_string, "version_label": {"type": "string"}, "report_time": nullable_string,
                },
            },
            "state": {
                "type": "object",
                "additionalProperties": False,
                "required": ["overall", "report", "baseline", "policy", "replay"],
                "properties": {
                    "overall": {"enum": ["available", "degraded", "unavailable", "malformed", "unsupported"]},
                    "report": {"enum": ["available", "unavailable", "malformed", "unsupported", "incomplete"]},
                    "baseline": {"enum": ["available", "unavailable"]},
                    "policy": {"enum": ["available", "degraded"]},
                    "replay": {"enum": ["available", "degraded", "unavailable"]},
                },
            },
            "posture": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "verdict",
                    "baseline_state",
                    "policy_resolution_status",
                    "automatic_mode_enabled",
                    "finding_count",
                    "blocker_count",
                    "warning_count",
                ],
                "properties": {
                    "verdict": _nullable({"type": "string", "enum": list(VERDICTS)}),
                    "baseline_state": nullable_string,
                    "policy_resolution_status": nullable_string,
                    "automatic_mode_enabled": {"type": "boolean"},
                    "finding_count": {"type": "integer", "minimum": 0},
                    "blocker_count": {"type": "integer", "minimum": 0},
                    "warning_count": {"type": "integer", "minimum": 0},
                },
            },
            "scores": {
                "type": "object",
                "additionalProperties": False,
                "required": ["trust", "automation", "product_breadth", "report_depth"],
                "properties": {
                    key: {"type": "integer", "minimum": 0, "maximum": 100}
                    for key in ("trust", "automation", "product_breadth", "report_depth")
                },
            },
            "capabilities": {
                "type": "array",
                "minItems": len(CAPABILITY_IDS),
                "maxItems": len(CAPABILITY_IDS),
                "items": capability,
            },
            "priority_actions": {
                "type": "array",
                "maxItems": 8,
                "items": priority_action,
            },
            "activity": {
                "type": "array",
                "minItems": len(REQUIRED_ACTIVITY_SEQUENCE),
                "maxItems": len(REQUIRED_ACTIVITY_SEQUENCE) + 1,
                "items": activity,
            },
            "available_artifacts": {
                "type": "array", "minItems": 5, "maxItems": 5,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["id", "available"],
                    "properties": {"id": {"enum": ["baseline", "policy", "report", "replay", "decisions"]}, "available": {"type": "boolean"}},
                },
            },
            "workbench": {
                "type": "object", "additionalProperties": False,
                "required": ["review_action", "proposed_change", "evidence_cards", "correction_rows"],
                "properties": {
                    "review_action": review_action,
                    "proposed_change": _nullable(proposed_change),
                    "evidence_cards": {"type": "array", "maxItems": 6, "items": evidence_card},
                    "correction_rows": {"type": "array", "maxItems": 3, "items": correction_row},
                },
            },
            "artifacts": {
                "type": "object",
                "additionalProperties": False,
                "required": ["baseline", "policy", "status", "report", "report_error", "decisions"],
                "properties": {
                    "baseline": {"type": "object"},
                    "policy": {"type": "object"},
                    "status": {"type": "object"},
                    "report": nullable_object,
                    "report_error": nullable_object,
                    "decisions": {"type": "object"},
                },
            },
            "bounds": {
                "type": "object", "additionalProperties": False,
                "required": ["max_serialized_bytes", "bounded_content", "collections", "artifacts"],
                "properties": {
                    "max_serialized_bytes": {"type": "integer", "minimum": 1},
                    "bounded_content": {"const": True},
                    "collections": {
                        "type": "object", "additionalProperties": False,
                        "required": ["findings", "blockers", "warnings", "evidence_items"],
                        "properties": {key: {
                            "type": "object", "additionalProperties": False,
                            "required": ["truncated", "total_count", "displayed_count", "omitted_count"],
                            "properties": {
                                "truncated": {"type": "boolean"},
                                "total_count": {"type": "integer", "minimum": 0},
                                "displayed_count": {"type": "integer", "minimum": 0},
                                "omitted_count": {"type": "integer", "minimum": 0},
                            },
                        } for key in ("findings", "blockers", "warnings", "evidence_items")},
                    },
                    "artifacts": {"type": "object"},
                },
            },
        },
    }


def _pointer(parts: list[Any]) -> str:
    if not parts:
        return "/"
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def validate_command_center_snapshot(snapshot: dict[str, Any]) -> None:
    validator = Draft202012Validator(command_center_snapshot_schema())
    errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        raise ValueError(f"Invalid Command Center snapshot at {_pointer(list(first.absolute_path))}: {first.message}")

    capability_ids = tuple(item["id"] for item in snapshot["capabilities"])
    if capability_ids != CAPABILITY_IDS:
        raise ValueError(
            "Invalid Command Center snapshot at /capabilities: capability order must match the canonical registry"
        )
    for index, capability in enumerate(snapshot["capabilities"]):
        action_id = capability["action"]
        if action_id is not None and action_id not in CAPABILITY_ACTIONS_BY_ID[capability["id"]]:
            raise ValueError(
                f"Invalid Command Center snapshot at /capabilities/{index}/action: action does not belong to capability"
            )

    activity_types = tuple(item["type"] for item in snapshot["activity"])
    if activity_types[: len(REQUIRED_ACTIVITY_SEQUENCE)] != REQUIRED_ACTIVITY_SEQUENCE:
        raise ValueError(
            "Invalid Command Center snapshot at /activity: lifecycle order must be repository, baseline, policy, review"
        )
    if len(activity_types) == len(REQUIRED_ACTIVITY_SEQUENCE) + 1 and activity_types[-1] != "error":
        raise ValueError(
            "Invalid Command Center snapshot at /activity: only one terminal error event may follow review"
        )
    if len(set(activity_types)) != len(activity_types):
        raise ValueError("Invalid Command Center snapshot at /activity: lifecycle event types must be unique")

    actions = snapshot["priority_actions"]
    action_ids = [item["id"] for item in actions]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("Invalid Command Center snapshot at /priority_actions: action IDs must be unique")

    ranks = {priority: index for index, priority in enumerate(ACTION_PRIORITIES)}
    action_ranks = [ranks[item["priority"]] for item in actions]
    if action_ranks != sorted(action_ranks):
        raise ValueError("Invalid Command Center snapshot at /priority_actions: priorities must be deterministic")

    for index, action in enumerate(actions):
        action_type = action["action_type"]
        command = action["command"]
        target_surface = action["target_surface"]
        expected_action_type = ACTION_TYPE_BY_ID[action["id"]]
        expected_command, expected_target_surface = ACTION_PAYLOAD_BY_ID[action["id"]]
        if action_type != expected_action_type:
            raise ValueError(
                f"Invalid Command Center snapshot at /priority_actions/{index}: action type does not match action ID"
            )
        if command != expected_command or target_surface != expected_target_surface:
            raise ValueError(
                f"Invalid Command Center snapshot at /priority_actions/{index}: command and target do not match action ID"
            )
        if action_type == "copy_command" and (not command or target_surface is not None):
            raise ValueError(
                f"Invalid Command Center snapshot at /priority_actions/{index}: copy_command requires only command"
            )
        if action_type == "navigate" and (not target_surface or command is not None):
            raise ValueError(
                f"Invalid Command Center snapshot at /priority_actions/{index}: navigate requires only target_surface"
            )
        if action_type == "run_review" and (command is not None or target_surface is not None):
            raise ValueError(
                f"Invalid Command Center snapshot at /priority_actions/{index}: run_review has no command or target"
            )
