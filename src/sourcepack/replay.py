from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reports.markdown import LIGHT_BY_VERDICT

REPLAY_BUNDLE_SCHEMA_PREFIX = "sourcepack.replay_bundle."
REPLAY_OUTPUT_SCHEMA_VERSION = "sourcepack.replay.v1"


def _empty(input_path: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": REPLAY_OUTPUT_SCHEMA_VERSION,
        "input_schema_version": None,
        "input_path": input_path,
        "input_type": None,
        "valid": False,
        "errors": [],
        "warnings": [],
        "reconstructed": False,
        "verdict": None,
        "exit_code": None,
        "light": None,
        "reason_codes": [],
        "findings": [],
        "blockers": [],
        "report_warnings": [],
        "checked_categories": [],
        "not_checked_categories": [],
        "evidence": {},
        "reason_code_evidence": {},
        "baseline_metadata": {},
        "prompt_context_metadata": {},
        "patch_metadata": {},
        "environment_metadata": {},
        "policy_metadata": {},
        "sourcepack_version": None,
        "replay_bundle": None,
        "reran_judgment": False,
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _reason_codes(source: dict[str, Any]) -> list[str]:
    explicit = source.get("reason_codes", source.get("normalized_reason_codes"))
    if isinstance(explicit, list):
        return sorted({str(code) for code in explicit if code is not None})
    codes = {str(f.get("id")) for f in _as_list(source.get("findings")) if isinstance(f, dict) and f.get("id")}
    return sorted(codes)


def _light(verdict: Any, source: dict[str, Any]) -> str | None:
    if isinstance(source.get("light"), str):
        return source["light"]
    if isinstance(verdict, str):
        return LIGHT_BY_VERDICT.get(verdict)
    return None


def _looks_like_replay_bundle(obj: dict[str, Any]) -> bool:
    schema = obj.get("schema_version")
    return isinstance(schema, str) and schema.startswith(REPLAY_BUNDLE_SCHEMA_PREFIX)


def _bundle_errors(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = bundle.get("schema_version")
    if not isinstance(schema, str) or not schema.startswith(REPLAY_BUNDLE_SCHEMA_PREFIX):
        errors.append("replay_bundle schema_version is missing or unsupported")
    if "verdict" not in bundle:
        errors.append("replay_bundle verdict is missing")
    if "findings" in bundle and not isinstance(bundle.get("findings"), list):
        errors.append("replay_bundle findings must be a list when present")
    if "reason_code_evidence" in bundle and not isinstance(bundle.get("reason_code_evidence"), dict):
        errors.append("replay_bundle reason_code_evidence must be an object when present")
    return errors


def _copy_from(source: dict[str, Any], out: dict[str, Any]) -> None:
    verdict = source.get("verdict")
    out["input_schema_version"] = source.get("schema_version") if isinstance(source.get("schema_version"), str) else None
    out["verdict"] = verdict if isinstance(verdict, str) else None
    out["exit_code"] = source.get("exit_code") if isinstance(source.get("exit_code"), int) else None
    out["light"] = _light(out["verdict"], source)
    out["reason_codes"] = _reason_codes(source)
    out["findings"] = _as_list(source.get("findings"))
    out["blockers"] = _as_list(source.get("blockers"))
    out["report_warnings"] = _as_list(source.get("warnings"))
    out["checked_categories"] = _as_list(source.get("checked_categories", source.get("checked")))
    out["not_checked_categories"] = _as_list(source.get("not_checked", source.get("not_checked_categories")))
    out["evidence"] = _as_dict(source.get("evidence"))
    if "unavailable_evidence" in source or "unsupported_evidence" in source:
        out["evidence"] = dict(out["evidence"])
        if "unavailable_evidence" in source:
            out["evidence"].setdefault("unavailable_evidence", _as_list(source.get("unavailable_evidence")))
        if "unsupported_evidence" in source:
            out["evidence"].setdefault("unsupported_evidence", _as_list(source.get("unsupported_evidence")))
    out["reason_code_evidence"] = _as_dict(source.get("reason_code_evidence"))
    out["baseline_metadata"] = _as_dict(source.get("baseline_metadata"))
    out["prompt_context_metadata"] = _as_dict(source.get("prompt_context_metadata"))
    out["patch_metadata"] = _as_dict(source.get("patch_metadata"))
    out["environment_metadata"] = _as_dict(source.get("environment_metadata"))
    out["policy_metadata"] = _as_dict(source.get("policy_metadata"))
    out["sourcepack_version"] = source.get("sourcepack_version") if isinstance(source.get("sourcepack_version"), str) else None


def reconstruct_replay(path: str | Path) -> tuple[dict[str, Any], int]:
    input_path = str(path)
    out = _empty(input_path)
    p = Path(path)
    if not p.exists():
        out["errors"].append(f"missing input path: {input_path}")
        return out, 1
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        out["errors"].append(f"invalid JSON in {input_path}: {exc.msg} at line {exc.lineno} column {exc.colno}")
        return out, 1
    except OSError as exc:
        out["errors"].append(f"could not read {input_path}: {exc}")
        return out, 1
    if not isinstance(data, dict):
        out["errors"].append("replay input root must be a JSON object")
        return out, 1

    out["input_schema_version"] = data.get("schema_version") if isinstance(data.get("schema_version"), str) else None

    bundle = data.get("replay_bundle") if isinstance(data.get("replay_bundle"), dict) else None
    if bundle is not None:
        out["input_type"] = "full_report_with_replay_bundle"
        _copy_from(data, out)
        out["replay_bundle"] = bundle
        errors = _bundle_errors(bundle)
        if errors:
            out["errors"].extend(errors)
            return out, 1
        out["valid"] = True
        out["reconstructed"] = True
        return out, 0

    if _looks_like_replay_bundle(data):
        out["input_type"] = "raw_replay_bundle"
        errors = _bundle_errors(data)
        _copy_from(data, out)
        out["replay_bundle"] = data
        if errors:
            out["errors"].extend(errors)
            return out, 1
        out["valid"] = True
        out["reconstructed"] = True
        return out, 0

    if "replay_bundle" in data and data.get("replay_bundle") is not None:
        out["input_type"] = "full_report_with_corrupt_replay_bundle"
        _copy_from(data, out)
        out["errors"].append("replay_bundle must be a JSON object when present")
        return out, 1

    if any(key in data for key in ("verdict", "findings", "blockers", "warnings", "checked_categories")):
        out["input_type"] = "full_report_without_replay_bundle"
        _copy_from(data, out)
        out["valid"] = True
        out["reconstructed"] = True
        out["warnings"].append("replay bundle is missing; reconstructed basic report summary only")
        return out, 0

    out["input_type"] = "unsupported_json_object"
    out["errors"].append("unsupported replay input schema: expected SourcePack report or replay bundle")
    return out, 1


def render_replay_human(result: dict[str, Any]) -> str:
    lines = [
        "SourcePack replay/audit reconstruction",
        f"Input path: {result.get('input_path')}",
        f"Input type: {result.get('input_type') or 'unknown'}",
        f"Valid: {result.get('valid')}",
        f"Schema version: {result.get('schema_version') or 'not present'}",
        f"Input schema version: {result.get('input_schema_version') or 'not present'}",
        f"SourcePack version: {result.get('sourcepack_version') or 'not present'}",
        f"Verdict: {result.get('verdict') or 'not present'}",
        f"Exit code: {result.get('exit_code') if result.get('exit_code') is not None else 'not present'}",
        f"Traffic light: {result.get('light') or 'not derivable'}",
        f"Finding count: {len(result.get('findings') or [])}",
        f"Blocker count: {len(result.get('blockers') or [])}",
        f"Warning count: {len(result.get('report_warnings') or [])}",
        f"Reason codes: {', '.join(result.get('reason_codes') or []) or 'none'}",
        f"Checked categories: {', '.join(result.get('checked_categories') or []) or 'none present'}",
        f"Not-checked categories: {', '.join(result.get('not_checked_categories') or []) or 'none present'}",
    ]
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    unavailable = evidence.get("unavailable_evidence", evidence.get("missing_evidence", [])) if evidence else []
    lines.append(f"Unavailable evidence: {len(unavailable or [])}")
    lines.append(f"Unsupported evidence: {len(evidence.get('unsupported_evidence') or []) if evidence else 0}")
    for label, key in (("Baseline metadata", "baseline_metadata"), ("Prompt-context metadata", "prompt_context_metadata"), ("Patch metadata", "patch_metadata"), ("Environment metadata", "environment_metadata"), ("Policy metadata", "policy_metadata")):
        lines.append(f"{label}: {'present' if result.get(key) else 'not present'}")
    lines.append(f"Replay bundle: {'present' if result.get('replay_bundle') is not None else 'missing'}")
    lines.append(f"Reconstructed without rerunning judgment: {result.get('reran_judgment') is False and result.get('reconstructed') is True}")
    for warning in result.get("warnings") or []:
        lines.append(f"WARNING: {warning}")
    for error in result.get("errors") or []:
        lines.append(f"ERROR: {error}")
    return "\n".join(lines) + "\n"
