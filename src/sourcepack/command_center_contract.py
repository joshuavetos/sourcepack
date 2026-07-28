from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

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
ACTION_TYPES = ("run_review", "navigate", "copy_command")
ACTION_PRIORITIES = ("P0", "P1", "P2", "P3")
ACTIVITY_TYPES = ("repository", "baseline", "policy", "review", "error")
REQUIRED_ACTIVITY_SEQUENCE = ("repository", "baseline", "policy", "review")
VERDICTS = ("PASS", "WARN", "FAIL")


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def command_center_snapshot_schema() -> dict[str, Any]:
    nullable_string = _nullable({"type": "string"})
    nullable_object = _nullable({"type": "object"})
    capability = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "name", "surface", "status", "evidence", "action"],
        "properties": {
            "id": {"type": "string", "enum": list(CAPABILITY_IDS)},
            "name": {"type": "string", "minLength": 1},
            "surface": {"type": "string", "minLength": 1},
            "status": {"type": "string", "enum": list(CAPABILITY_STATUSES)},
            "evidence": {"type": "string", "minLength": 1},
            "action": nullable_string,
        },
    }
    priority_action = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "priority", "label", "action_type", "command", "target_surface", "reason"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "priority": {"type": "string", "enum": list(ACTION_PRIORITIES)},
            "label": {"type": "string", "minLength": 1},
            "action_type": {"type": "string", "enum": list(ACTION_TYPES)},
            "command": nullable_string,
            "target_surface": nullable_string,
            "reason": {"type": "string", "minLength": 1},
        },
    }
    activity = {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "message"],
        "properties": {
            "type": {"type": "string", "enum": list(ACTIVITY_TYPES)},
            "message": {"type": "string", "minLength": 1},
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
            "posture",
            "scores",
            "capabilities",
            "priority_actions",
            "activity",
            "artifacts",
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
            "artifacts": {
                "type": "object",
                "additionalProperties": False,
                "required": ["baseline", "policy", "status", "report", "report_error"],
                "properties": {
                    "baseline": {"type": "object"},
                    "policy": {"type": "object"},
                    "status": {"type": "object"},
                    "report": nullable_object,
                    "report_error": nullable_object,
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
