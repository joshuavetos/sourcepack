from __future__ import annotations

import inspect
from pathlib import Path
from types import ModuleType

from .diff_parser import parse_unified_diff
from .git import decode_git_path, run_git_bounded

POLICY_AUTHORITY_ERROR = "repository_policy_modified_in_proposed_state"


def _normalize_path(value: object) -> str:
    path = str(value or "").replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def is_policy_authority_path(value: object) -> bool:
    path = _normalize_path(value)
    return path == ".sourcepack/policy.json" or path == ".sourcepack/policy" or path.startswith(".sourcepack/policy/")


def _git_paths(repo: Path, args: list[str]) -> set[str]:
    nul_args = list(args)
    separator = nul_args.index("--") if "--" in nul_args else len(nul_args)
    nul_args.insert(separator, "-z")
    cp = run_git_bounded(repo, nul_args, text=False)
    if cp.returncode != 0:
        return set()
    return {
        normalized
        for raw in cp.stdout.split(b"\0")
        if raw and (normalized := _normalize_path(decode_git_path(raw))) and is_policy_authority_path(normalized)
    }


def proposed_policy_paths(repo: str | Path, patch_text: str | None = None) -> tuple[str, ...]:
    root = Path(repo).resolve()
    paths: set[str] = set()

    if patch_text:
        for change in parse_unified_diff(patch_text):
            for candidate in (change.path, change.old_path):
                normalized = _normalize_path(candidate)
                if normalized and is_policy_authority_path(normalized):
                    paths.add(normalized)

    pathspec = ["--", ".sourcepack/policy.json", ".sourcepack/policy"]
    paths.update(_git_paths(root, ["diff", "--name-only", *pathspec]))
    paths.update(_git_paths(root, ["diff", "--cached", "--name-only", *pathspec]))
    paths.update(_git_paths(root, ["ls-files", "--others", "--exclude-standard", *pathspec]))
    return tuple(sorted(paths))


def _judgment_patch_text() -> str | None:
    frame = inspect.currentframe()
    try:
        current = frame.f_back if frame is not None else None
        for _ in range(20):
            if current is None:
                break
            if current.f_globals.get("__name__") == "sourcepack.judgment":
                value = current.f_locals.get("patch_text")
                if isinstance(value, str):
                    return value
            current = current.f_back
    finally:
        del frame
    return None


def guard_effective_policy_result(
    repo: str | Path,
    result: dict,
    *,
    patch_text: str | None = None,
) -> dict:
    changed_paths = proposed_policy_paths(repo, patch_text)
    if not changed_paths:
        return result

    guarded = dict(result)
    errors = list(guarded.get("errors") or [])
    if POLICY_AUTHORITY_ERROR not in errors:
        errors.append(POLICY_AUTHORITY_ERROR)

    rejected = list(guarded.get("rejected_weakening_attempts") or [])
    known = {
        (str(item.get("rule")), str(item.get("path")))
        for item in rejected
        if isinstance(item, dict)
    }
    for path in changed_paths:
        key = ("repository_policy_authority", path)
        if key not in known:
            rejected.append(
                {
                    "rule": "repository_policy_authority",
                    "path": path,
                    "comparison_method": "trusted_prechange_policy_only",
                    "reason": "a proposed policy change cannot govern the patch that introduces it",
                }
            )

    source = dict(guarded.get("repository_policy_source") or {})
    source.update(
        {
            "authority_basis": "trusted_prechange_state",
            "proposed_change_status": "rejected_for_current_judgment",
            "proposed_change_paths": list(changed_paths),
        }
    )

    guarded["resolution_status"] = "FAIL"
    guarded["errors"] = errors
    guarded["rejected_weakening_attempts"] = rejected
    guarded["repository_policy_source"] = source
    guarded["prechange_policy_authority"] = {
        "status": "FAIL",
        "reason": POLICY_AUTHORITY_ERROR,
        "changed_paths": list(changed_paths),
        "required_workflow": "accept policy changes separately before they govern later patches",
    }
    return guarded


def install_policy_authority_guard(policy_module: ModuleType) -> None:
    current = policy_module.resolve_effective_policy
    if getattr(current, "__sourcepack_prechange_policy_guard__", False):
        return

    def guarded_resolve_effective_policy(
        repo: str | Path,
        org_policy: str | Path | None = None,
        org_policy_mode: str = "optional",
    ) -> dict:
        result = current(repo, org_policy=org_policy, org_policy_mode=org_policy_mode)
        return guard_effective_policy_result(repo, result, patch_text=_judgment_patch_text())

    guarded_resolve_effective_policy.__name__ = current.__name__
    guarded_resolve_effective_policy.__doc__ = current.__doc__
    guarded_resolve_effective_policy.__sourcepack_prechange_policy_guard__ = True
    policy_module.resolve_effective_policy = guarded_resolve_effective_policy
