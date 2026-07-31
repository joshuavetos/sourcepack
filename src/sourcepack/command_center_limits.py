"""Centrally owned transport limits for the Command Center v1 snapshot."""

from __future__ import annotations

from typing import Any

MAX_SNAPSHOT_BYTES = 262_144
MAX_COLLECTION_ITEMS = 64
MAX_MAPPING_ITEMS = 64
MAX_NESTING_DEPTH = 6
MAX_STRING_CHARS = 2_048
MAX_PROMPT_CHARS = 8_192
MAX_PATHS = 64
MAX_EXCERPTS = 8
MAX_EXCERPT_LINES = 80
MAX_LINE_CHARS = 512
TRUNCATION_MARKER = "…[truncated]"


def clip_text(value: Any, limit: int = MAX_STRING_CHARS) -> str:
    """Return a deterministic Unicode-code-point clip with an explicit marker."""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(TRUNCATION_MARKER))] + TRUNCATION_MARKER


def bounded_value(value: Any, *, depth: int = 0, string_limit: int = MAX_STRING_CHARS) -> Any:
    """Bound repository-controlled diagnostics; mapping keys are sorted for stability."""
    if isinstance(value, str):
        return clip_text(value, string_limit)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= MAX_NESTING_DEPTH:
        return {"bounded": True, "omission_reason": "maximum_nesting_depth"}
    if isinstance(value, dict):
        keys = sorted(value, key=lambda item: str(item))
        shown = keys[:MAX_MAPPING_ITEMS]
        result = {str(key): bounded_value(value[key], depth=depth + 1, string_limit=string_limit) for key in shown}
        if len(keys) > len(shown):
            result["_sourcepack_bounds"] = {
                "truncated": True, "total_count": len(keys), "displayed_count": len(shown),
                "omitted_count": len(keys) - len(shown),
            }
        return result
    if isinstance(value, (list, tuple)):
        shown = value[:MAX_COLLECTION_ITEMS]
        return [bounded_value(item, depth=depth + 1, string_limit=string_limit) for item in shown]
    return clip_text(value, string_limit)


def collection_status(value: Any, displayed: Any) -> dict[str, Any]:
    total = len(value) if isinstance(value, list) else 0
    count = len(displayed) if isinstance(displayed, list) else 0
    return {"truncated": count < total, "total_count": total, "displayed_count": count, "omitted_count": total - count}
