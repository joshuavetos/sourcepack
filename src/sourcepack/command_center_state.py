from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .baseline import baseline_report_fields, validate_baseline
from .command_center_limits import MAX_COLLECTION_ITEMS, MAX_EXCERPTS, MAX_LINE_CHARS, clip_text
from .git import metadata as git_metadata, run_git
from .overrides import OVERRIDE_SCHEMA_VERSION, override_applies
from .paths import sourcepack_paths
from .policy import resolve_effective_policy
from .judgment import git_worktree_dirty, utc_now
from .reports.json import validate_report_construction_metadata

TRAFFIC_REPORT_SCHEMA_VERSION = "traffic_report.v1"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents


WORKBENCH_EXCERPT_FILE_LIMIT_BYTES = 128 * 1024
CANONICAL_REPORT_FILE_LIMIT_BYTES = 2 * 1024 * 1024
DECISION_LEDGER_BYTE_LIMIT = 2 * 1024 * 1024
DECISION_LEDGER_RECORD_LIMIT = 512
DECISION_LEDGER_LINE_LIMIT_BYTES = 64 * 1024
CANONICAL_REPORT_COLLECTION_LIMIT = 2_000
CANONICAL_REPORT_MAPPING_LIMIT = 512
CANONICAL_REPORT_STRING_LIMIT_CHARS = 65_536
CANONICAL_REPORT_NESTING_LIMIT = 20

def _report_shape_limit(value: Any, depth: int = 0) -> str | None:
    if depth > CANONICAL_REPORT_NESTING_LIMIT:
        return "nesting_depth"
    if isinstance(value, str) and len(value) > CANONICAL_REPORT_STRING_LIMIT_CHARS:
        return "string_chars"
    if isinstance(value, list) and len(value) > CANONICAL_REPORT_COLLECTION_LIMIT:
        return "collection_items"
    if isinstance(value, dict) and len(value) > CANONICAL_REPORT_MAPPING_LIMIT:
        return "mapping_items"
    children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
    for child in children:
        failure = _report_shape_limit(child, depth + 1)
        if failure:
            return failure
    return None


def _workbench_action(report: dict[str, Any] | None) -> dict[str, Any]:
    """Build the Workbench CTA exclusively from canonical report fields."""
    if report is None:
        return {
            "action_type": "run_review",
            "label": "Run Review",
            "reason": "report_unavailable",
            "target_surface": "workbench_review",
            "available": True,
        }

    verdict = str(report.get("verdict") or "").upper()
    blockers_raw = report.get("blockers")
    warnings_raw = report.get("warnings")
    findings_raw = report.get("findings")
    blockers = [item for item in blockers_raw if isinstance(item, dict)] if isinstance(blockers_raw, list) else []
    warnings = [item for item in warnings_raw if isinstance(item, dict)] if isinstance(warnings_raw, list) else []
    findings = [item for item in findings_raw if isinstance(item, dict)] if isinstance(findings_raw, list) else []
    primary = (blockers or warnings or findings or [{}])[0]
    reason = primary.get("reason_code") or primary.get("id") or report.get("reason_code")
    if verdict == "PASS":
        raw = report.get("raw_patch_judgment") if isinstance(report.get("raw_patch_judgment"), dict) else {}
        has_change = any(raw.get(key) for key in ("modified_files", "new_files", "deleted_files", "missing_modified_files"))
        return {
            "action_type": "run_review",
            "label": "Run Review Again",
            "reason": "change_supported" if has_change else "no_diff",
            "target_surface": "workbench_review",
            "available": True,
        }
    if verdict in {"WARN", "FAIL"}:
        remediation = report.get("remediation") if isinstance(report.get("remediation"), dict) else {}
        prompt = remediation.get("agent_prompt")
        available = isinstance(prompt, str) and bool(prompt.strip())
        action = {
            "action_type": "copy_prompt",
            "label": "Copy Correction Prompt",
            "reason": str(reason or "remediation_unavailable"),
            "target_surface": "correction_prompt",
            "available": available,
        }
        if available:
            action["prompt"] = prompt
        return action
    return {
        "action_type": "none",
        "label": "Action Unavailable",
        "reason": str(reason or "unsupported_verdict"),
        "target_surface": "none",
        "available": False,
    }


def _dashboard_error(section: str, code: str, message: str, status: str = "error") -> dict[str, Any]:
    return {"schema_version": f"sourcepack.dashboard.{section}.v1", "ok": False, "status": status, "error": {"code": code, "message": message}}


def _decision_completeness(consumed: int, retained: int, *, exhausted: bool) -> dict[str, Any]:
    return {
        "count_state": "exact" if exhausted else "lower_bound",
        "observed_count": consumed,
        "nonblank_records_consumed": consumed,
        "records_retained": retained,
        "source_exhausted": exhausted,
        "total_count": consumed if exhausted else None,
        "limit_reached": not exhausted,
        "retention_limit": DECISION_LEDGER_RECORD_LIMIT,
    }


def validate_decision_completeness(metadata: dict[str, Any]) -> None:
    required = {
        "count_state", "observed_count", "nonblank_records_consumed", "records_retained",
        "source_exhausted", "total_count", "limit_reached", "retention_limit",
    }
    if not isinstance(metadata, dict) or not required <= metadata.keys():
        raise ValueError("persisted decision completeness metadata is incomplete")
    consumed = metadata["nonblank_records_consumed"]
    retained = metadata["records_retained"]
    limit = metadata["retention_limit"]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (consumed, retained, limit)):
        raise ValueError("persisted decision counts must be non-negative integers")
    if limit != DECISION_LEDGER_RECORD_LIMIT:
        raise ValueError("persisted decision retention limit does not match the producer limit")
    if metadata["observed_count"] != consumed or retained != min(consumed, limit):
        raise ValueError("persisted decision consumed and retained counts are inconsistent")
    exhausted = metadata["source_exhausted"]
    reached = metadata["limit_reached"]
    if not isinstance(exhausted, bool) or not isinstance(reached, bool) or exhausted == reached:
        raise ValueError("persisted decision exhaustion and limit flags are inconsistent")
    if exhausted:
        if metadata["count_state"] != "exact" or metadata["total_count"] != consumed or consumed > limit:
            raise ValueError("complete persisted decision counts must be exact and within the retention limit")
    elif metadata["count_state"] != "lower_bound" or metadata["total_count"] is not None:
        raise ValueError("incomplete persisted decision counts require an unknown lower-bound total")


def _decision_limit_error(category: str, consumed: int) -> dict[str, Any]:
    completeness = _decision_completeness(consumed, min(consumed, DECISION_LEDGER_RECORD_LIMIT), exhausted=False)
    validate_decision_completeness(completeness)
    return _dashboard_error("overrides", "artifact_limit_exceeded", "The persisted override record exceeds the producer limit.", "incomplete") | {
        "limit_category": category,
        "ledger_available": True,
        "ledger_complete": False,
        "completeness": completeness,
    }


def _read_decision_ledger(handle: Any) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int, int]:
    """Stream bounded JSONL; reads at most the total budget plus one probe byte."""
    overrides: list[dict[str, Any]] = []
    observed_records = 0
    bytes_read = 0
    while True:
        remaining = DECISION_LEDGER_BYTE_LIMIT - bytes_read
        if remaining == 0:
            probe = handle.read(1)
            bytes_read += len(probe)
            if probe:
                return overrides, _decision_limit_error("ledger_total_byte_limit", observed_records), observed_records, bytes_read
            break
        request = min(DECISION_LEDGER_LINE_LIMIT_BYTES + 1, remaining)
        line = handle.readline(request)
        bytes_read += len(line)
        if not line:
            break
        if len(line) > DECISION_LEDGER_LINE_LIMIT_BYTES:
            return overrides, _decision_limit_error("ledger_line_byte_limit", observed_records), observed_records, bytes_read
        if not line.endswith(b"\n") and len(line) == request:
            probe = handle.read(1)
            bytes_read += len(probe)
            if probe:
                category = "ledger_line_byte_limit" if len(line) >= DECISION_LEDGER_LINE_LIMIT_BYTES else "ledger_total_byte_limit"
                return overrides, _decision_limit_error(category, observed_records), observed_records, bytes_read
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return overrides, _dashboard_error("overrides", "artifact_malformed", "The persisted override record is malformed."), observed_records, bytes_read
        if not isinstance(event, dict):
            return overrides, _dashboard_error("overrides", "artifact_malformed", "The persisted override record is malformed."), observed_records, bytes_read
        observed_records += 1
        if observed_records > DECISION_LEDGER_RECORD_LIMIT:
            return overrides, _decision_limit_error("ledger_record_limit", observed_records), observed_records, bytes_read
        data = event.get("data")
        override = data.get("override") if isinstance(data, dict) else None
        if isinstance(override, dict) and override.get("schema_version") == OVERRIDE_SCHEMA_VERSION:
            overrides.append({**override, "currently_applicable": override_applies(override), "related_finding": data.get("finding_id")})
    return overrides, None, observed_records, bytes_read


def _read_canonical_report(repo: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read only the established latest.json location; never search archives."""
    path = sourcepack_paths(repo)["latest_json"]
    if not path.is_file():
        return None, None
    try:
        with path.open("rb") as handle:
            raw = handle.read(CANONICAL_REPORT_FILE_LIMIT_BYTES + 1)
        if len(raw) > CANONICAL_REPORT_FILE_LIMIT_BYTES:
            return None, _dashboard_error("report", "artifact_limit_exceeded", "The canonical report exceeds the producer read limit.", "incomplete")
        report = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, _dashboard_error("report", "artifact_malformed", "The canonical report is malformed.")
    if not isinstance(report, dict):
        return None, _dashboard_error("report", "artifact_malformed", "The canonical report is malformed.")
    if report.get("schema_version") != TRAFFIC_REPORT_SCHEMA_VERSION:
        return None, _dashboard_error("report", "artifact_version_unsupported", "The canonical report version is unsupported.", "unsupported")
    shape_failure = _report_shape_limit(report)
    if shape_failure:
        return None, _dashboard_error("report", "artifact_limit_exceeded", f"The canonical report exceeds the producer {shape_failure} limit.", "incomplete")
    try:
        validate_report_construction_metadata(report)
    except ValueError:
        return None, _dashboard_error("report", "artifact_malformed", "The canonical report construction metadata is malformed.")
    return report, None


def _safe_report_paths(report: dict[str, Any]) -> list[str]:
    raw = report.get("raw_patch_judgment") if isinstance(report.get("raw_patch_judgment"), dict) else {}
    paths: list[str] = []
    for key in ("modified_files", "new_files", "deleted_files", "missing_modified_files"):
        values = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str):
                    path = clip_text(value)
                    if path not in paths:
                        paths.append(path)
    for finding in report.get("findings", [])[:MAX_COLLECTION_ITEMS]:
        if isinstance(finding, dict) and isinstance(finding.get("path"), str):
            path = clip_text(finding["path"])
            if path not in paths:
                paths.append(path)
    return paths[:MAX_EXCERPTS]


def _bounded_changed_file_excerpt(repo: Path, report: dict[str, Any]) -> dict[str, Any]:
    paths = _safe_report_paths(report)
    terms = sorted({str(finding.get("evidence") or "")[:MAX_LINE_CHARS].lower() for finding in report.get("findings", [])[:MAX_COLLECTION_ITEMS] if isinstance(finding, dict) and finding.get("evidence")})
    excerpts: list[dict[str, Any]] = []
    root = repo.resolve()
    for rel in paths:
        if not rel or Path(rel).is_absolute() or rel.startswith(("..", "/", "\\")):
            continue
        target = (root / rel).resolve()
        if not _is_relative_to(target, root):
            continue
        try:
            is_file = target.is_file()
        except OSError:
            excerpts.append({"path": clip_text(rel), "source": "current_worktree_file_listed_by_canonical_report", "status": "omitted", "reason": "file_unreadable", "lines": []})
            continue
        if not is_file:
            continue
        try:
            data = target.open("rb").read(WORKBENCH_EXCERPT_FILE_LIMIT_BYTES + 1)
        except OSError:
            excerpts.append({"path": clip_text(rel), "source": "current_worktree_file_listed_by_canonical_report", "status": "omitted", "reason": "file_unreadable", "lines": []})
            continue
        status = "truncated" if len(data) > WORKBENCH_EXCERPT_FILE_LIMIT_BYTES else "available"
        if status == "truncated":
            data = data[:WORKBENCH_EXCERPT_FILE_LIMIT_BYTES]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            excerpts.append({"path": clip_text(rel), "source": "current_worktree_file_listed_by_canonical_report", "status": "omitted", "reason": "file_not_utf8", "lines": []})
            continue
        lines = text.splitlines()
        selected: list[int] = []
        for index, line in enumerate(lines):
            low = line.lower()
            if any(term and term in low for term in terms):
                selected.extend(range(max(0, index - 1), min(len(lines), index + 2)))
        if not selected:
            selected = list(range(min(len(lines), 8)))
        selected = sorted(set(selected))[:12]
        excerpts.append({"path": clip_text(rel), "source": "current_worktree_file_listed_by_canonical_report", "status": status, "byte_limit": WORKBENCH_EXCERPT_FILE_LIMIT_BYTES, "lines": [{"number": i + 1, "text": clip_text(lines[i], MAX_LINE_CHARS)} for i in selected]})
    return {"schema_version": "sourcepack.dashboard.proposed_change.v1", "source": "traffic_report.raw_patch_judgment plus bounded current worktree excerpt", "paths": paths, "excerpts": excerpts}

def _report_payload(repo: Path) -> dict[str, Any]:
    report, error = _read_canonical_report(repo)
    if error:
        error["action"] = {
            "action_type": "none",
            "label": "Action Unavailable",
            "reason": str(error.get("error", {}).get("code") or "report_unavailable"),
            "target_surface": "none",
            "available": False,
        }
        return error
    if report is None:
        return {"schema_version": "sourcepack.dashboard.report.v1", "ok": True, "status": "empty", "error": {"code": "report_unavailable", "message": "No canonical report is available."}, "report": None, "action": _workbench_action(None)}
    status = "incomplete" if report.get("authority", {}).get("complete") is False else "success"
    return {"schema_version": "sourcepack.dashboard.report.v1", "ok": True, "status": status, "report_path": ".sourcepack/reports/latest.json", "report": report, "proposed_change": _bounded_changed_file_excerpt(repo, report), "action": _workbench_action(report)}


def _hook_is_sourcepack(text: str) -> bool:
    return "# === SOURCEPACK BEGIN ===" in text and "# === SOURCEPACK END ===" in text


def _sourcepack_status_payload(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    paths = sourcepack_paths(repo)
    current = paths["base"].exists()
    baseline_status = validate_baseline(repo)
    baseline = baseline_status["state"] in {"present", "stale"}
    last = None
    if baseline_status.get("packet_path"):
        receipt = repo / baseline_status["packet_path"] / "receipt.json"
        if receipt.exists():
            try:
                last = json.loads(receipt.read_text(encoding="utf-8")).get("generated_at")
            except Exception:
                last = None
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    git_repo = cp.returncode == 0
    root = Path(cp.stdout.strip()) if git_repo else repo
    pre = root / ".git" / "hooks" / "pre-commit"
    post = root / ".git" / "hooks" / "post-commit"
    hook_installed = False
    post_hook_installed = False
    strict = False
    if pre.exists():
        text = pre.read_text(encoding="utf-8", errors="ignore")
        hook_installed = _hook_is_sourcepack(text)
        strict = "strict mode blocks YELLOW LIGHT" in text
    if post.exists():
        post_hook_installed = "# === SOURCEPACK POST-COMMIT BEGIN" in post.read_text(encoding="utf-8", errors="ignore")
    ignored = False
    cig = run_git(repo, ["check-ignore", ".sourcepack/"])
    if cig.returncode == 0:
        ignored = True
    elif (repo / ".gitignore").exists():
        ignored = any(line.strip() in {".sourcepack", ".sourcepack/"} for line in (repo / ".gitignore").read_text(errors="ignore").splitlines())
    last_report = None
    last_light = None
    if paths["latest_json"].exists():
        try:
            lr = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
            last_report = lr.get("verdict")
            last_light = lr.get("light")
        except Exception:
            pass
    dirty, dirty_state = git_worktree_dirty(repo)
    prompt_exists = paths["prompt"].exists()
    automatic = current and baseline and hook_installed and post_hook_installed and ignored
    data = {
        "schema_version": "sourcepack_status.v1",
        "sourcepack_version": __version__,
        "generated_at": utc_now(),
        "automatic_mode_enabled": automatic,
        "local_storage_exists": current,
        "baseline_exists": baseline,
        "prompt_context_exists": prompt_exists,
        "pre_commit_hook_installed": hook_installed,
        "post_commit_hook_installed": post_hook_installed,
        "hook_strict_mode": strict,
        "hook_policy": "RED blocks, YELLOW blocks" if strict else "RED blocks, YELLOW warns",
        "sourcepack_gitignored": ignored,
        "last_report_verdict": last_report,
        "last_report_light": last_light,
        "dirty_worktree": dirty if dirty_state is None else None,
        "git_repo": git_repo,
        "last_baseline_update": last,
    }
    data.update(baseline_report_fields(baseline_status))
    return {"ok": True, "returncode": 0, "stderr": "", "status": data}


def _dashboard_payload(
    repo: Path,
    section: str,
    *,
    policy_reader=resolve_effective_policy,
    git_reader=git_metadata,
) -> dict[str, Any]:
    try:
        if not repo.is_dir():
            return _dashboard_error(section, "repository_unavailable", "The Workbench repository is unavailable.")
        if section == "report":
            return _report_payload(repo)
        if section == "policy":
            policy = policy_reader(repo)
            status = "success" if policy.get("resolution_status") == "PASS" else "error"
            payload = {"schema_version": "sourcepack.dashboard.policy.v1", "ok": status == "success", "status": status, "policy": policy}
            if status != "success":
                payload["error"] = {"code": "policy_resolution_failed", "message": "Policy resolution failed."}
            return payload
        if section == "baseline":
            baseline = validate_baseline(repo)
            status = "success" if baseline.get("state") in {"present", "stale"} else "empty" if baseline.get("state") == "missing" else "error"
            payload = {"schema_version": "sourcepack.dashboard.baseline.v1", "ok": bool(baseline.get("ok")), "status": status, "baseline": baseline}
            if status == "empty": payload["error"] = {"code": "baseline_unavailable", "message": "No trusted baseline is available."}
            if status == "error": payload["error"] = {"code": "artifact_malformed", "message": "The baseline is unavailable or malformed."}
            return payload
        if section == "replay-evidence":
            report, error = _read_canonical_report(repo)
            if error:
                error["schema_version"] = "sourcepack.dashboard.replay_evidence.v1"
                return error
            if report is None:
                return {"schema_version": "sourcepack.dashboard.replay_evidence.v1", "ok": True, "status": "empty", "replay": None, "evidence": None}
            status = "incomplete" if report.get("authority", {}).get("complete") is False else "success"
            return {"schema_version": "sourcepack.dashboard.replay_evidence.v1", "ok": True, "status": status, "report_path": ".sourcepack/reports/latest.json", "authority": report.get("authority"), "construction_bounds": report.get("construction_bounds"), "replay": report.get("replay_bundle"), "evidence": report.get("evidence_items", report.get("evidence")), "reason_code_evidence": report.get("reason_code_evidence")}
        if section == "overrides":
            # The decision ledger is the persisted SourcePack override record.
            ledger = sourcepack_paths(repo)["base"] / "decisions.jsonl"
            overrides: list[dict[str, Any]] = []
            observed_records = 0
            if ledger.is_file():
                with ledger.open("rb") as handle:
                    overrides, ledger_error, observed_records, _bytes_read = _read_decision_ledger(handle)
                if ledger_error:
                    return ledger_error
            report, report_error = _read_canonical_report(repo)
            if report_error:
                report_error["schema_version"] = "sourcepack.dashboard.overrides.v1"
                return report_error
            findings = [item for item in (report or {}).get("findings", []) if isinstance(item, dict) and item.get("category") == "policy"]
            completeness = _decision_completeness(observed_records, observed_records, exhausted=True)
            validate_decision_completeness(completeness)
            report_incomplete = bool(report and report.get("authority", {}).get("complete") is False)
            return {"schema_version": "sourcepack.dashboard.overrides.v1", "ok": True, "status": "incomplete" if report_incomplete else "success" if overrides or findings else "empty", "ledger_available": ledger.is_file(), "ledger_complete": True, "overrides": overrides, "policy_findings": findings, "report_authority": report.get("authority") if report else None, "report_construction_bounds": report.get("construction_bounds") if report else None, "completeness": completeness}
        if section == "overview":
            git = git_reader(repo)
            baseline = validate_baseline(repo)
            policy = policy_reader(repo)
            report, report_error = _read_canonical_report(repo)
            report_state = report_error.get("status", "error") if report_error else "empty" if report is None else "incomplete" if report.get("authority", {}).get("complete") is False else "available"
            return {"schema_version": "sourcepack.dashboard.overview.v1", "ok": True, "status": "success", "repository": {"path": str(repo), "sourcepack_version": __version__}, "git": git, "baseline": baseline, "policy_resolution_status": policy.get("resolution_status"), "report_status": report_state, "report_verdict": report.get("verdict") if report else None, "blocker_count": len(report.get("blockers", [])) if report else 0, "warning_count": len(report.get("warnings", [])) if report else 0}
    except Exception:
        return _dashboard_error(section, "internal_error", "Dashboard data could not be read.")
    return _dashboard_error(section, "internal_error", "Dashboard section is unavailable.")



# Public shared backend-state API. Underscored aliases remain in workbench for compatibility.
workbench_action = _workbench_action
dashboard_error = _dashboard_error
read_canonical_report = _read_canonical_report
bounded_changed_file_excerpt = _bounded_changed_file_excerpt
sourcepack_status_payload = _sourcepack_status_payload
dashboard_payload = _dashboard_payload
