from __future__ import annotations

import argparse
import contextlib
import io
import importlib.resources as resources
import fnmatch
import hashlib
import json
import os
import platform
import tomllib
import webbrowser  # noqa: F401 - exposed for tests that monkeypatch report browser opening
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from .diff_parser import PatchFileChange, normalize_diff_path as _normalize_diff_path, parse_unified_diff
from .baseline import (
    BaselineLockError,
    DIRTY_BASELINE_REFUSAL,
    acquire_baseline_lock,
    baseline_corrupt_result,
    baseline_report_fields,
    build_current_baseline,
    release_baseline_lock,
    resolve_active_baseline,
    validate_baseline,
)
from .ecosystems.python import PY_IMPORT_ALIASES
from .packet import PacketWriter, SourceScanner, sourcepack_bootstrap_file, verify_packet as canonical_verify_packet
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.html import render_report_html
from .reports.json import finalize_user_report, normalized_finding, traffic_report, write_auto_report, write_user_report
from .reports.markdown import render_traffic
from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_TIMEOUT, run_git as canonical_run_git, tracked_paths as canonical_tracked_paths
from .execution_ledger import clear_ledger, iter_entries, run_and_record, find_repo_root
from .commands import bundle as bundle_command
from .commands import fleet as fleet_command
from .commands import report as report_command
from .policy import PolicyMode, exit_code as policy_exit_code, validate_policy_config, resolve_effective_policy
from .replay import reconstruct_replay, render_replay_human

from . import __version__

# Compatibility exports and internal adapters. Authority-bearing analysis lives in
# sourcepack.judgment; CLI code must not implement a second judgment pipeline.
from . import judgment as _judgment

analyze_patch = _judgment.analyze_patch
build_prompt_context = _judgment.build_prompt_context
build_repo_change_report = _judgment.build_repo_change_report
copy_to_clipboard = _judgment.copy_to_clipboard
dependency_inventory = _judgment.dependency_inventory
docker_evidence = _judgment.docker_evidence
estimate_tokens = _judgment.estimate_tokens
extract_imports_from_text = _judgment.extract_imports_from_text
extract_js_import_specifiers_from_text = _judgment.extract_js_import_specifiers_from_text
extract_refs = _judgment.extract_refs
feature_inventory = _judgment.feature_inventory
generate_reality_map = _judgment.generate_reality_map
git_metadata = _judgment.git_metadata
git_worktree_dirty = _judgment.git_worktree_dirty
is_probably_binary = _judgment.is_probably_binary
judge_patch_text = _judgment.judge_patch_text
known_files = _judgment.known_files
load_manifest = _judgment.load_manifest
matches_any = _judgment.matches_any
node_project_evidence = _judgment.node_project_evidence
patch_report_to_traffic = _judgment.patch_report_to_traffic
python_project_evidence = _judgment.python_project_evidence
redact_secrets = _judgment.redact_secrets
render_ai_instructions = _judgment.render_ai_instructions
render_prompt = _judgment.render_prompt
run_git = _judgment.run_git
scanner_config_hash = _judgment.scanner_config_hash
sha256_file = _judgment.sha256_file
sha256_text = _judgment.sha256_text
supported_commands_inventory = _judgment.supported_commands_inventory
untracked_files_as_diff = _judgment.untracked_files_as_diff
utc_now = _judgment.utc_now

# Legacy import compatibility: canonical models and classifications are owned by
# the judgment facade and its internal evidence modules.
DEFAULT_IGNORED_DIRS = _judgment.DEFAULT_IGNORED_DIRS
DEFAULT_IGNORED_PATTERNS = _judgment.DEFAULT_IGNORED_PATTERNS
DEFAULT_TEXT_EXTENSIONS = _judgment.DEFAULT_TEXT_EXTENSIONS
SECRET_PATTERNS = _judgment.SECRET_PATTERNS
COMMON_DEPENDENCIES = _judgment.COMMON_DEPENDENCIES
FEATURE_NAMES = _judgment.FEATURE_NAMES
IncludedFile = _judgment.IncludedFile
IgnoredFile = _judgment.IgnoredFile
PATHLIKE_EXTENSIONS = _judgment.PATHLIKE_EXTENSIONS
PROJECT_PATH_PREFIXES = _judgment.PROJECT_PATH_PREFIXES
PDF_DEPENDENCIES = _judgment.PDF_DEPENDENCIES
PROTECTED_PACKET_ARTIFACTS = _judgment.PROTECTED_PACKET_ARTIFACTS

def verify_packet(packet_path: str | Path, against: str | Path | None = None) -> bool:
    return canonical_verify_packet(packet_path, against)


def render_patch_judgment_report(report: dict) -> str:
    traffic = report.get("traffic") if isinstance(report.get("traffic"), dict) else patch_report_to_traffic(report, "patch_judgment_report.json")
    lines = ["# SourcePack Patch Judgment Report", "", f"Verdict: {traffic.get('verdict', report.get('verdict', 'WARN'))}", f"Report: {report.get('report_path', 'patch_judgment_report.json')}", "", f"Next action: {traffic.get('next_action')}", ""]
    grouped = [("blockers", "Blockers"), ("warnings", "Review warnings"), ("uncertainties", "Uncertainties")]
    for key, title in grouped:
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {f.get('id')}: {f.get('message')}" for f in report.get(key, [])] or ["None"])
        lines.append("")
    for key, title in [("checked_categories", "Checked"), ("not_checked", "Not checked")]:
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {item}" for item in report.get(key, [])] or ["None"])
        lines.append("")
    lines.extend(["## Raw Patch Sections", ""])
    sections = [("modified_files", "Modified Files"), ("missing_modified_files", "Missing Modified Files"), ("new_files", "New Files"), ("deleted_files", "Deleted Files"), ("unsupported_dependencies", "Unsupported Dependencies"), ("unsupported_commands", "Unsupported Commands"), ("protected_artifact_modifications", "Protected Packet Artifact Modifications"), ("git_path_modifications", "Git Path Modifications"), ("binary_diffs", "Binary Diffs"), ("binary_diff_blockers", "Binary Diff Blockers"), ("declared_dependencies", "Declared Dependencies"), ("declared_commands", "Declared Commands"), ("warnings_text", "Legacy Warnings")]
    legacy = dict(report); legacy["warnings_text"] = report.get("legacy_warnings", report.get("warnings", []))
    for key, title in sections:
        lines.extend([f"### {title}"])
        lines.extend([f"- {item}" for item in legacy.get(key, [])] or ["None"])
        lines.append("")
    return "\n".join(lines)


def judge_patch(packet_path: str | Path, patch_path: str | Path, out_dir: str | Path) -> dict:
    try:
        patch_text = Path(patch_path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report = {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    else:
        report = judge_patch_text(packet_path, patch_text)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    report_path = str(out / "patch_judgment_report.json")
    traffic = patch_report_to_traffic(report, report_path)
    enriched = dict(report)
    enriched["legacy_warnings"] = list(report.get("warnings", []))
    enriched.update({
        "schema_version": "patch_judgment_report.v1",
        "sourcepack_version": __version__,
        "generated_at": utc_now(),
        "light": traffic.get("light"),
        "reason_type": traffic.get("reason_type"),
        "commit_policy": traffic.get("commit_policy"),
        "findings": traffic.get("findings", []),
        "blockers": traffic.get("blockers", []),
        "warnings": [f for f in traffic.get("warnings", []) if f.get("category") != "uncertainty"],
        "uncertainties": [f for f in traffic.get("warnings", []) if f.get("category") == "uncertainty"],
        "checked_categories": traffic.get("checked_categories", []),
        "not_checked": traffic.get("not_checked", []),
        "next_action": traffic.get("next_action"),
        "report_path": report_path,
        "traffic": traffic,
    })
    text = render_patch_judgment_report(enriched)
    (out / "patch_judgment_report.md").write_text(text, encoding="utf-8")
    (out / "patch_judgment_report.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    print(render_traffic(traffic, verbose=True), end="")
    return enriched


def judge_ai_answer(packet_path: str | Path, ai_answer_path: str | Path, out_dir: str | Path | None = None) -> dict:
    ai_text = Path(ai_answer_path).read_text(encoding="utf-8")
    report = _judgment.analyze_ai_answer(packet_path, ai_text)
    lines = ["# SourcePack Judgment Report", "", "Verdict: " + report["verdict"], ""]
    for section, label in [("supported_files", "Supported File References"), ("missing_files", "Missing File References"), ("unsupported_dependencies", "Unsupported Dependencies"), ("unsupported_commands", "Unsupported Commands"), ("unsupported_capabilities", "Unsupported Capabilities")]:
        lines.append(f"## {label}")
        items = report[section]
        if not items:
            lines.append("None")
        else:
            for item in items:
                prefix = "SUPPORTED" if section == "supported_files" else "NOT FOUND" if section == "missing_files" else "UNSUPPORTED"
                lines.append(f"- [{prefix}] {item}")
        lines.append("")
    if out_dir:
        out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
        (out / "judgment_report.md").write_text("\n".join(lines), encoding="utf-8")
        (out / "judgment_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return report


def finalize_diff_report(repo: str | Path | None, report: dict, args, stem: str = "diff") -> dict:
    try:
        return finalize_user_report(repo, report, stem=stem, ci=getattr(args, "ci", False))
    except Exception as exc:
        print(f"WARNING: could not write SourcePack report artifacts: {exc}", file=sys.stderr)
        full = dict(report)
        if getattr(args, "ci", False):
            full["ci"] = True
        return full

def emit_diff_report(report: dict, args, added: bool = False, note: str | None = None) -> int:
    if getattr(args, "ci", False):
        args.json = True
        report["ci"] = True
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        if added:
            print("Added .sourcepack/ to .gitignore.")
        if note:
            print(note)
        print(render_traffic(report, getattr(args, "verbose", False)), end="")
    verdict = report.get("verdict")
    mode = PolicyMode.CI if getattr(args, "ci", False) else PolicyMode.STRICT if getattr(args, "strict", False) else PolicyMode.LOCAL
    return policy_exit_code(verdict, mode=mode, exit_policy=getattr(args, "exit_policy", None))


def cli_prompt(args) -> int:
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("repo_not_directory", "error", "git", f"Repo path is not a directory: {args.repo}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    try:
        build_prompt_context(repo)
    except Exception as exc:
        rep = traffic_report("FAIL", "could not generate prompt context.", [normalized_finding("prompt_context_failed", "error", "prompt", f"Prompt context generation failed: {exc}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    task = args.task or "Explain how this project works and summarize its structure."
    reality = json.loads(paths["prompt_reality"].read_text(encoding="utf-8")); instructions = paths["prompt_instructions"].read_text(encoding="utf-8")
    prompt = render_prompt(task, instructions, reality); paths["prompt"].write_text(prompt, encoding="utf-8")
    copied = copy_to_clipboard(prompt) if args.copy else False
    dirty, dirty_state = git_worktree_dirty(repo)
    findings = []
    if args.copy and not copied:
        findings.append(normalized_finding("clipboard_unavailable", "warn", "clipboard", "clipboard unavailable."))
    if dirty:
        findings.append(normalized_finding("dirty_worktree", "warn", "prompt", "prompt context includes uncommitted working tree changes."))
    verdict = "WARN" if findings else "PASS"
    headline = "verified prompt copied to clipboard." if args.copy and copied else "clipboard unavailable." if args.copy and not copied else "verified prompt context saved."
    rep = traffic_report(verdict, headline, findings, ["prompt context", "file references", "known project commands"], "continue with the saved prompt; enforcement baseline was not changed.")
    write_user_report(repo, rep, "prompt")
    if args.json: print(json.dumps({**rep, "prompt_path": ".sourcepack/prompt/prompt.md", "clipboard_copied": copied}, indent=2)); return 0
    if added: print("Added .sourcepack/ to .gitignore.")
    print(f"{rep['light']}: {headline}\n\nPrompt saved: .sourcepack/prompt/prompt.md")
    return 0


def cli_baseline(args) -> int:
    repo = Path(args.repo).resolve(); dirty, dirty_state = git_worktree_dirty(repo)
    if dirty_state in {"git_unavailable", "git_timeout", "git_error"}:
        rep = traffic_report("FAIL", "trusted baseline refused unverifiable git state.", [normalized_finding("git_unavailable" if dirty_state == "git_unavailable" else "git_timeout" if dirty_state == "git_timeout" else "baseline_failed", "error", "git", f"Cannot verify git status before creating trusted baseline: {dirty_state}")], ["baseline", "git status"], "Fix Git execution before creating trusted baseline state.")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end="")
        return 1
    if dirty and not getattr(args, "force", False):
        rep = traffic_report("FAIL", "trusted baseline refused dirty working tree.", [normalized_finding("dirty_worktree", "error", "baseline", DIRTY_BASELINE_REFUSAL)], ["baseline", "git status"], "Review, commit, or stash current changes first; use --force only for an intentionally trusted state.")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end="")
        return 1
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("gitignore_unwritable","error","git",f"Cannot write .gitignore: {err}")]); print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    existed = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
    try:
        build_current_baseline(repo, quiet=getattr(args, "quiet", False), force=getattr(args, "force", False)); refreshed = existed or args.refresh
        if dirty:
            headline = "baseline refreshed while uncommitted changes are present." if refreshed else "baseline created while uncommitted changes are present."
            rep=traffic_report("WARN", headline, [normalized_finding("dirty_worktree", "warn", "baseline", "baseline now includes current uncommitted changes.")], ["baseline","verify"], "Commit or discard unintended changes before relying on this baseline.")
        else:
            headline = "baseline refreshed." if refreshed else "baseline created."
            rep=traffic_report("PASS", headline, checked_categories=["baseline","verify"])
        write_user_report(repo, rep, "baseline")
        if args.json: print(json.dumps(rep, indent=2)); return 0
        if getattr(args, "quiet", False): return 0
        if added: print("Added .sourcepack/ to .gitignore.")
        print(render_traffic(rep,args.verbose), end="")
        return 0
    except BaselineLockError as exc:
        rep=traffic_report("WARN","baseline writer is locked.",[normalized_finding("baseline_locked","warn","tooling",str(exc))], ["baseline"], "try again after the other baseline operation finishes.", reason_type="tooling"); write_user_report(repo, rep, "baseline")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    except Exception as exc:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("baseline_failed","error","baseline",f"Baseline verification failed: {exc}")]); write_user_report(repo, rep, "baseline")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1


def cli_diff(args) -> int:
    from .judgment import judge_repo_change
    if getattr(args, "ci", False):
        args.json = True
    if bool(getattr(args, "base_ref", None)) != bool(getattr(args, "head_ref", None)):
        raise SystemExit("--base-ref and --head-ref must be provided together")
    mode = PolicyMode.CI if getattr(args, "ci", False) else PolicyMode.STRICT if getattr(args, "strict", False) else PolicyMode.LOCAL
    judgment = judge_repo_change(args.repo, staged=args.staged, policy_mode=mode, base_ref=getattr(args, "base_ref", None), head_ref=getattr(args, "head_ref", None), org_policy=getattr(args, "org_policy", None), org_policy_mode=getattr(args, "org_policy_mode", "optional"))
    report = finalize_diff_report(Path(judgment.report.get("repo_path", args.repo)), judgment.report, args)
    return emit_diff_report(report, args, note=report.get("note"))

def hook_text(strict: bool) -> str:
    strict_block = """
if grep -q 'YELLOW LIGHT' .git/SOURCEPACK_LAST_DIFF 2>/dev/null; then
  echo 'SourcePack strict mode blocks YELLOW LIGHT.'
  echo 'To bypass manually: git commit --no-verify'
  exit 1
fi""" if strict else ""
    return """#!/bin/sh
# === SOURCEPACK BEGIN ===
# SourcePack hook version: 1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ]; then
  echo 'RED LIGHT: SourcePack could not locate git repository root.'
  echo 'To bypass manually: git commit --no-verify'
  exit 1
fi
cd "$repo_root" || exit 1
sourcepack diff . --staged > .git/SOURCEPACK_LAST_DIFF
sp_status=$?
cat .git/SOURCEPACK_LAST_DIFF
if [ $sp_status -ne 0 ]; then
  echo 'To bypass manually: git commit --no-verify'
  exit $sp_status
fi""" + strict_block + """
# === SOURCEPACK END ===
"""


def post_commit_hook_text() -> str:
    return """#!/bin/sh
# === SOURCEPACK POST-COMMIT BEGIN ===
# SourcePack hook version: 1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ]; then
  exit 0
fi
cd "$repo_root" || exit 0
if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  sourcepack baseline . --refresh --quiet >/dev/null 2>&1 || echo 'YELLOW LIGHT: SourcePack post-commit baseline refresh failed.'
else
  mkdir -p .sourcepack/state
  current_head="$(git rev-parse HEAD 2>/dev/null)"
  cat > .sourcepack/state/baseline_stale.json <<EOF
{"reason": "post_commit_dirty_worktree", "detected_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "current_head": "$current_head", "dirty_worktree": true}
EOF
  echo 'YELLOW LIGHT: SourcePack baseline is stale because uncommitted changes remain after commit.'
fi
# === SOURCEPACK POST-COMMIT END ===
"""


def install_post_commit_hook(repo: Path) -> bool:
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return False
    root = Path(cp.stdout.strip())
    hooks = root / ".git" / "hooks"
    post = hooks / "post-commit"
    hooks.mkdir(parents=True, exist_ok=True)
    text = post.read_text(encoding="utf-8", errors="ignore") if post.exists() else ""
    block = post_commit_hook_text()
    if "# === SOURCEPACK POST-COMMIT BEGIN ===" in text:
        text = re.sub(r"#!/bin/sh\n?# === SOURCEPACK POST-COMMIT BEGIN ===.*?# === SOURCEPACK POST-COMMIT END ===\n?", block, text, flags=re.S)
    elif text.strip():
        text = text.rstrip() + "\n" + block
    else:
        text = block
    post.write_text(text, encoding="utf-8")
    post.chmod(0o755)
    return True

def hook_chain_text(strict: bool) -> str:
    return hook_text(strict) + """
orig="$(git rev-parse --git-dir 2>/dev/null)/hooks/pre-commit.sourcepack.orig"
if [ -n "$orig" ] && [ -x "$orig" ]; then
  "$orig" "$@"
  exit $?
fi
exit 0
"""


def hook_is_sourcepack(text: str) -> bool:
    return "# === SOURCEPACK BEGIN ===" in text and "# === SOURCEPACK END ===" in text


def cli_install_hook(args) -> int:
    repo=Path(args.repo).resolve(); cp=run_git(repo,["rev-parse","--show-toplevel"])
    if cp.returncode!=0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found."
        print(f"RED LIGHT: SourcePack pre-commit hook install failed.\n\n{message}"); return 1
    root=Path(cp.stdout.strip()); hooks=root/".git"/"hooks"; pre=hooks/"pre-commit"; post=hooks/"post-commit"; orig=hooks/"pre-commit.sourcepack.orig"
    try:
        hooks.mkdir(parents=True, exist_ok=True)
        if pre.exists():
            text=pre.read_text(encoding="utf-8", errors="ignore")
            if hook_is_sourcepack(text):
                pre.write_text(hook_chain_text(args.strict) if orig.exists() else hook_text(args.strict) + "\nexit 0\n", encoding="utf-8")
            else:
                if not orig.exists(): shutil.copy2(pre, orig)
                pre.write_text(hook_chain_text(args.strict), encoding="utf-8")
        else:
            pre.write_text(hook_text(args.strict) + "\nexit 0\n", encoding="utf-8")
        pre.chmod(0o755); install_post_commit_hook(root); print("GREEN LIGHT: SourcePack pre-commit and post-commit hooks installed."); return 0
    except Exception as exc:
        print(f"RED LIGHT: SourcePack pre-commit hook install failed.\n\n{exc}"); return 1

def cli_uninstall_hook(args) -> int:
    repo=Path(args.repo).resolve(); cp=run_git(repo,["rev-parse","--show-toplevel"])
    if cp.returncode!=0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found."
        print(f"RED LIGHT: SourcePack pre-commit hook uninstall failed.\n\n{message}"); return 1
    root=Path(cp.stdout.strip()); hooks=root/".git"/"hooks"; pre=hooks/"pre-commit"; post=hooks/"post-commit"; orig=hooks/"pre-commit.sourcepack.orig"
    try:
        restored_original = False
        if orig.exists():
            shutil.move(str(orig), str(pre)); pre.chmod(0o755); restored_original = True
        elif pre.exists():
            text=pre.read_text(encoding="utf-8", errors="ignore")
            if not hook_is_sourcepack(text):
                print("RED LIGHT: Cannot safely uninstall SourcePack hook: SourcePack block not found."); return 1
            pre.write_text(re.sub(r"# === SOURCEPACK BEGIN ===.*?# === SOURCEPACK END ===\n?", "", text, flags=re.S), encoding="utf-8")
        if post.exists():
            post_text=post.read_text(encoding="utf-8", errors="ignore")
            if "# === SOURCEPACK POST-COMMIT BEGIN ===" in post_text:
                post.write_text(re.sub(r"#!/bin/sh\n?# === SOURCEPACK POST-COMMIT BEGIN ===.*?# === SOURCEPACK POST-COMMIT END ===\n?", "", post_text, flags=re.S), encoding="utf-8")
        print("GREEN LIGHT: SourcePack hooks uninstalled." if not restored_original else "GREEN LIGHT: SourcePack hooks uninstalled and original pre-commit hook restored."); return 0
    except Exception as exc:
        print(f"RED LIGHT: SourcePack pre-commit hook uninstall failed.\n\n{exc}"); return 1

def cli_status(args) -> int:
    repo=Path(args.repo).resolve(); paths=ensure_sourcepack_dirs(repo)
    current=paths["base"].exists(); baseline_status=validate_baseline(repo); baseline=baseline_status["state"] in {"present", "stale"}; last=None
    if baseline_status.get("packet_path"):
        receipt=repo / baseline_status["packet_path"] / "receipt.json"
        if receipt.exists():
            try: last=json.loads(receipt.read_text()).get("generated_at")
            except Exception: last=None
    cp=run_git(repo,["rev-parse","--show-toplevel"]); git_repo=cp.returncode==0; root=Path(cp.stdout.strip()) if git_repo else repo
    pre=root/".git"/"hooks"/"pre-commit"; post=root/".git"/"hooks"/"post-commit"; hook_installed=False; post_hook_installed=False; strict=False
    if pre.exists():
        text=pre.read_text(encoding="utf-8", errors="ignore"); hook_installed=hook_is_sourcepack(text); strict="strict mode blocks YELLOW LIGHT" in text
    if post.exists():
        post_hook_installed="# === SOURCEPACK POST-COMMIT BEGIN ===" in post.read_text(encoding="utf-8", errors="ignore")
    ignored=False; cig=run_git(repo,["check-ignore",".sourcepack/"])
    if cig.returncode==0: ignored=True
    elif (repo/".gitignore").exists(): ignored=any(line.strip() in {".sourcepack",".sourcepack/"} for line in (repo/".gitignore").read_text(errors="ignore").splitlines())
    last_report=None; last_light=None
    if paths["latest_json"].exists():
        try:
            lr=json.loads(paths["latest_json"].read_text()); last_report=lr.get("verdict"); last_light=lr.get("light")
        except Exception: pass
    dirty, dirty_state = git_worktree_dirty(repo)
    stale = baseline_status["state"] == "stale"
    stale_data = (baseline_status.get("details") or {}).get("stale_details")
    prompt_exists = paths["prompt"].exists()
    automatic = current and baseline and hook_installed and post_hook_installed and ignored
    data={"schema_version":"sourcepack_status.v1","sourcepack_version":__version__,"generated_at":utc_now(),"automatic_mode_enabled":automatic,"local_storage_exists":current,"baseline_exists":baseline,"prompt_context_exists":prompt_exists,"pre_commit_hook_installed":hook_installed,"post_commit_hook_installed":post_hook_installed,"hook_strict_mode":strict,"hook_policy":"RED blocks, YELLOW blocks" if strict else "RED blocks, YELLOW warns","sourcepack_gitignored":ignored,"last_report_verdict":last_report,"last_report_light":last_light,"dirty_worktree":dirty if dirty_state is None else None,"git_repo":git_repo,"last_baseline_update":last}
    data.update(baseline_report_fields(baseline_status))
    if args.json: print(json.dumps(data, indent=2)); return 0
    print(f"SourcePack status for {repo}\n")
    print(f"Automatic mode: {'enabled' if automatic else 'not enabled'}")
    print(f"Baseline: {baseline_status['state']}")
    print(f"Prompt context: {'present' if prompt_exists else 'missing'}")
    print(f"Pre-commit hook: {'installed' if hook_installed else 'not installed'}")
    print(f"Post-commit baseline hook: {'installed' if post_hook_installed else 'not installed'}")
    print(f"Hook policy: {data['hook_policy']}")
    print(f".sourcepack/ gitignored: {'yes' if ignored else 'no'}")
    print(f"Working tree: {'dirty' if dirty else 'clean' if dirty_state is None else 'unknown'}")
    print(f"Last report: {last_light or last_report or 'none'}")
    return 0

def init_workspace(path: str | Path):
    p = Path(path); p.mkdir(parents=True, exist_ok=True)
    ignore = p / ".sourcepackignore"
    config = p / "sourcepack.config.json"
    if not ignore.exists():
        ignore.write_text("# SourcePack ignore rules\n.env\nnode_modules/\ndist/\nbuild/\n", encoding="utf-8")
    if not config.exists():
        config.write_text(json.dumps({"max_file_size": 1_000_000, "include_hidden": False, "redact_secrets": True}, indent=2), encoding="utf-8")
    print(f"Initialized SourcePack workspace at {p}")


def cli_init(args) -> int:
    repo = Path(args.path).resolve()
    if not getattr(args, "auto", False):
        init_workspace(repo)
        return 0
    initial_dirty, initial_dirty_state = git_worktree_dirty(repo)
    baseline_exists_before_init = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
    if initial_dirty_state in {"git_unavailable", "git_timeout", "git_error"} and (args.refresh_baseline or not baseline_exists_before_init):
        rep = traffic_report("FAIL", "trusted baseline refused unverifiable git state.", [normalized_finding("git_unavailable" if initial_dirty_state == "git_unavailable" else "git_timeout" if initial_dirty_state == "git_timeout" else "baseline_failed", "error", "git", f"Cannot verify git status before creating trusted baseline: {initial_dirty_state}")], ["init", "baseline", "git status"], "Fix Git execution before creating trusted baseline state.")
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            print(render_traffic(rep), end="")
        return 1
    if initial_dirty and not getattr(args, "force", False) and (args.refresh_baseline or not baseline_exists_before_init):
        rep = traffic_report("FAIL", "trusted baseline refused dirty working tree.", [normalized_finding("dirty_worktree", "error", "baseline", DIRTY_BASELINE_REFUSAL)], ["init", "baseline", "git status"], "Review, commit, or stash current changes first; rerun with --force only if this exact state is intentionally trusted.")
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            print(render_traffic(rep), end="")
        return 1
    init_workspace(repo)
    findings: list[dict] = []
    details = {"baseline_created": False, "baseline_refreshed": False, "hook_installed": False, "strict_mode": bool(args.strict), "sourcepack_gitignored": False, "dirty_worktree": False, "next_action": "continue."}
    paths = ensure_sourcepack_dirs(repo)
    added, err = ensure_gitignore_entry(repo)
    if err:
        rep = traffic_report("FAIL", "SourcePack automatic mode could not be enabled.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
        write_auto_report(repo, rep, details)
        print(render_traffic(rep), end=""); return 1
    details["sourcepack_gitignored"] = True
    dirty, dirty_state = initial_dirty, initial_dirty_state
    details["dirty_worktree"] = dirty
    baseline_exists = baseline_exists_before_init
    if args.refresh_baseline or (not baseline_exists and (not dirty or getattr(args, "force", False))):
        try:
            _, created = build_current_baseline(repo, force=getattr(args, "force", False))
            details["baseline_created"] = created
            details["baseline_refreshed"] = not created or args.refresh_baseline
            if dirty:
                findings.append(normalized_finding("dirty_worktree", "warn", "baseline", "dirty_worktree: baseline includes current uncommitted changes."))
        except BaselineLockError as exc:
            findings.append(normalized_finding("baseline_locked", "warn", "tooling", str(exc)))
            details["next_action"] = "Try again after the other baseline operation finishes."
        except Exception as exc:
            findings.append(normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}"))
    elif not baseline_exists and dirty:
        findings.append(normalized_finding("dirty_worktree", "warn", "baseline", "dirty_worktree: working tree has uncommitted changes, so baseline was not created."))
        findings.append(normalized_finding("baseline_missing", "warn", "baseline", "baseline_missing: run sourcepack baseline --refresh to accept current repo state."))
        details["next_action"] = "Run sourcepack init . --auto --refresh-baseline or sourcepack baseline --refresh to accept current repo state."
    if args.install_hygiene_hooks:
        findings.append(normalized_finding("hygiene_hooks_deferred", "warn", "hook", "baseline hygiene hooks are not installed by this release."))
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if args.no_hook:
        pass
    elif cp.returncode != 0:
        findings.append(normalized_finding("no_git_repo" if cp.returncode != 127 else "git_unavailable", "warn", "git", "no_git_repo: pre-commit hook was not installed because this is not a git repository." if cp.returncode != 127 else "Git executable not found."))
    else:
        class HookArgs: pass
        h = HookArgs(); h.repo = str(repo); h.strict = bool(args.strict)
        rc = cli_install_hook(h)
        details["hook_installed"] = rc == 0
        if rc != 0:
            findings.append(normalized_finding("hook_install_failed", "warn", "hook", "pre-commit hook could not be installed."))
    verdict = "FAIL" if any(f["severity"] == "error" for f in findings) else "WARN" if findings else "PASS"
    headline = "SourcePack automatic mode enabled." if verdict == "PASS" else "SourcePack automatic mode partially enabled." if verdict == "WARN" else "SourcePack automatic mode could not be enabled."
    rep = traffic_report(verdict, headline, findings, ["init", "baseline", "hook"], details.get("next_action", "continue."))
    write_auto_report(repo, rep, details)
    if args.json:
        print(json.dumps({**rep, **details}, indent=2)); return 0 if verdict != "FAIL" else 1
    print(f"{rep['light']}: {headline}\n")
    if findings:
        print("Warnings:" if verdict == "WARN" else "Blockers:")
        for f in findings: print(f"* {f['id']}: {f['message']}")
        print()
    print(f"Baseline: {'created' if details['baseline_created'] else 'refreshed' if details['baseline_refreshed'] else 'present' if baseline_exists else 'missing'}")
    print(f"Pre-commit hook: {'skipped' if args.no_hook else 'installed' if details['hook_installed'] else 'not installed'}")
    print(f".sourcepack/ gitignored: {'yes' if details['sourcepack_gitignored'] else 'no'}")
    return 0 if verdict != "FAIL" else 1

def _health_check_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    rows.append(("version", "PASS" if __version__ else "FAIL", __version__ or "missing package version"))
    rows.append(("python", "PASS" if sys.version_info >= (3, 11) else "FAIL", platform.python_version()))
    rows.append(("platform", "PASS", platform.platform()))
    rows.append(("git", "PASS" if shutil.which("git") else "WARN", shutil.which("git") or "not found on PATH; git-backed checks and hooks will be limited"))
    rows.append(("secret_signatures", "PASS" if SECRET_PATTERNS else "FAIL", str(len(SECRET_PATTERNS))))

    required_assets = ("audit_template.md", "packet_instructions.md")
    try:
        asset_root = resources.files("sourcepack.assets")
        missing_assets = [name for name in required_assets if not (asset_root / name).is_file()]
    except (FileNotFoundError, ModuleNotFoundError, AttributeError, TypeError) as exc:
        missing_assets = list(required_assets)
        rows.append(("package_assets", "FAIL", f"could not inspect packaged assets: {exc}"))
    else:
        rows.append(("package_assets", "PASS" if not missing_assets else "FAIL", "all required assets present" if not missing_assets else "missing: " + ", ".join(missing_assets)))

    report_renderers = (render_report_html, render_traffic, write_user_report)
    rows.append(("report_renderers", "PASS" if all(callable(fn) for fn in report_renderers) else "FAIL", "html, markdown, and json renderers importable"))
    return rows


def doctor(strict: bool = False) -> int:
    rows = _health_check_rows()
    print("--- SourcePack Health Check ---")
    for name, status, detail in rows:
        print(f"{status:4} {name}: {detail}")
    has_fail = any(status == "FAIL" for _, status, _ in rows)
    has_warn = any(status == "WARN" for _, status, _ in rows)
    if has_fail or (strict and has_warn):
        print("Status: NOT READY")
        return 1
    print("Status: READY")
    return 0


def cli_exec(args) -> int:
    entry = run_and_record(args.exec_command, cwd=".")
    print(entry.stdout_excerpt, end="")
    if entry.stderr_excerpt:
        print(entry.stderr_excerpt, end="", file=sys.stderr)
    print(f"SourcePack evidence entry: {entry.entry_id}", file=sys.stderr)
    return entry.exit_code


def cli_evidence(args) -> int:
    repo = find_repo_root(".")
    if args.evidence_command == "clear":
        clear_ledger(repo)
        print("Cleared SourcePack execution evidence ledger.")
        return 0
    if args.evidence_command == "list":
        entries = list(iter_entries(repo))
        if args.json:
            print(json.dumps({"schema_version": "sourcepack.execution_ledger.list.v1", "entries": entries}, indent=2))
            return 0
        for entry in entries:
            print(f"{entry.get('entry_id')} exit={entry.get('exit_code')} command={' '.join(entry.get('command') or [])}")
        return 0
    if args.evidence_command == "show":
        for entry in iter_entries(repo):
            if entry.get("entry_id") == args.entry_id:
                print(json.dumps(entry, indent=2, sort_keys=True))
                return 0
        print(f"ERROR: evidence entry not found: {args.entry_id}", file=sys.stderr)
        return 1
    if args.evidence_command == "export":
        print(json.dumps({"schema_version": "sourcepack.execution_ledger.export.v1", "entries": list(iter_entries(repo))}, indent=2))
        return 0
    return 1

REASON_EXPLANATIONS = {
    "unsupported_dependency": "A changed file imports a dependency that SourcePack could not find in local dependency manifests.",
    "unsupported_command": "A changed instruction references a project command that SourcePack could not find in local command manifests.",
    "declared_command": "The same patch declares command support and uses it; SourcePack requires review instead of treating it as established baseline evidence.",
    "command_manifest_missing": "A command check needed a local manifest/config file, but none was available.",
    "command_check_inconclusive": "SourcePack recognized the command family but could not safely infer support from dynamic or ambiguous config.",
    "symlink_replaces_nonempty_directory": "A proposed symlink collides with a live nonempty real directory whose ignored or untracked contents are absent from the Git transition.",
    "symlink_worktree_inspection_incomplete": "SourcePack could not completely acquire the current or prior worktree evidence required to judge a proposed symlink transition.",
}

def _policy_dir(repo: Path) -> Path:
    path = repo / ".sourcepack" / "policy"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _policy_file(repo: Path) -> Path:
    return _policy_dir(repo) / "allow.jsonl"

def _policy_entries(repo: Path) -> list[dict]:
    path = _policy_file(repo)
    if not path.exists(): return []
    entries=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try: entries.append(json.loads(line))
        except Exception: pass
    return entries

def cli_explain(args) -> int:
    code = args.reason_code.strip()
    print(f"{code}: {REASON_EXPLANATIONS.get(code, 'See docs/reason-codes.md and src/sourcepack/reason_codes.py for the canonical SourcePack reason-code vocabulary.')}")
    return 0

def cli_allow(args) -> int:
    from .local_allow_trust import add_active_allow

    repo = Path(".").resolve(); reason = getattr(args, "reason", None)
    if not reason:
        print("ERROR: --reason is required", file=sys.stderr); return 2
    scope_type = args.allow_type; value = args.value
    protected = value.startswith(".git/") or value == ".git" or value.startswith(".sourcepack/")
    if protected and not getattr(args, "high_risk", False):
        print("ERROR: protected artifacts require --high-risk and .git/** cannot be overridden", file=sys.stderr); return 1
    if value.startswith(".git/") or value == ".git":
        print("ERROR: .git/** cannot be overridden", file=sys.stderr); return 1
    entry = {"schema_version":"sourcepack.policy.allow.v1", "id": sha256_text(f'{scope_type}:{value}:{utc_now()}')[:12], "scope": scope_type, "value": value, "reason": reason, "created_at": utc_now(), "expires_at": getattr(args, "expires", None), "high_risk": bool(getattr(args, "high_risk", False))}
    try:
        add_active_allow(repo, _policy_file(repo), entry)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not persist active local allow: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(entry, indent=2))
    return 0

def cli_disallow(args) -> int:
    from .local_allow_trust import remove_active_allows

    repo = Path(".").resolve()
    try:
        removed = remove_active_allows(repo, _policy_file(repo), scope=args.allow_type, value=args.value)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not remove active local allow: {exc}", file=sys.stderr)
        return 1
    if not removed:
        print(f"No active {args.allow_type} permission matched {args.value}")
        return 0
    print(f"Removed active {args.allow_type} permission for {args.value}")
    return 0

def _display_repo_relative_path(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def cli_policy_resolve(args) -> int:
    repo = Path(getattr(args, "repo", "."))
    try:
        result = resolve_effective_policy(repo, org_policy=getattr(args, "org_policy", None), org_policy_mode=getattr(args, "org_policy_mode", "optional"))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("resolution_status") == "PASS" else 1
    print(f"Resolution verdict: {result['resolution_status']}")
    print(f"Organization-policy mode: {result['organization_policy_mode']}")
    print(f"Organization-policy status: {result['organization_policy_status']}")
    if result.get("organization_policy_id"):
        print(f"Organization policy ID: {result['organization_policy_id']}")
    if result.get("organization_policy_hash"):
        print(f"Organization policy hash: {result['organization_policy_hash']}")
    print(f"Repository policy: {result['repository_policy_source']['status']}")
    print(f"Effective rule count: {len(result['effective_policy'])}")
    print(f"Strengthening contributions: {len(result['strengthening_contributions'])}")
    print(f"Weakening attempts: {len(result['rejected_weakening_attempts'])}")
    print(f"Conflicts: {len(result['conflicts'])}")
    print(f"Effective-policy ID: {result['effective_policy_id']}")
    if result.get("errors"):
        print("Errors:")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result.get("resolution_status") == "PASS" else 1

def cli_policy_validate(args) -> int:
    repo = Path(getattr(args, "repo", "."))
    result = validate_policy_config(repo)
    policy_display_path = _display_repo_relative_path(Path(result.policy_path), repo)
    if getattr(args, "json", False):
        print(json.dumps(result.to_json_dict(), indent=2))
        return 0 if result.valid else 1
    if not result.policy_present:
        print(f"No policy file found at {policy_display_path}; policy config is optional.")
        return 0
    print(f"Policy file: {policy_display_path}")
    if result.errors:
        for error in result.errors:
            if error.startswith("policy_config_invalid_json:"):
                print(f"ERROR: invalid JSON in {policy_display_path}: {error}")
            elif error == "policy_config_invalid:root_must_be_object":
                print(f"ERROR: policy root must be a JSON object in {policy_display_path}")
            else:
                print(f"ERROR: {error}")
        return 1
    print("Policy config is valid.")
    if result.effective_ignored_paths:
        print("Effective ignored paths:")
        for item in result.effective_ignored_paths:
            print(f"- {item['pattern']} — {item['reason']}")
    else:
        print("Effective ignored paths: none")
    if result.ignored_invalid_entries:
        print("Ignored invalid entries:")
        for item in result.ignored_invalid_entries:
            print(f"- ignored_paths[{item.index}]: {item.warning}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    else:
        print("Warnings: none")
    return 0


def cli_policy(args) -> int:
    repo = Path(".").resolve()
    if args.policy_command == "validate":
        return cli_policy_validate(args)
    if args.policy_command == "resolve":
        return cli_policy_resolve(args)
    if args.policy_command == "list":
        print(json.dumps({"schema_version":"sourcepack.policy.list.v1", "policies": _policy_entries(repo)}, indent=2)); return 0
    if args.policy_command == "remove":
        from .local_allow_trust import remove_active_allows
        try:
            removed = remove_active_allows(repo, _policy_file(repo), allow_id=args.policy_id)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: could not remove active local allow: {exc}", file=sys.stderr); return 1
        print(f"Removed policy {args.policy_id}" if removed else f"No active policy matched {args.policy_id}"); return 0
    return 1


def cli_reset(args) -> int:
    repo = Path(args.repo).resolve(); target = repo / ".sourcepack" / "reports"
    if target.exists(): shutil.rmtree(target)
    print("SourcePack reset complete: removed local reports only; user code and trusted baseline were not deleted.")
    return 0

def cli_baseline_lifecycle(args) -> int | None:
    if args.repo not in {"status", "verify", "refresh", "repair", "path"}: return None
    command = args.repo; repo = Path(".").resolve(); status = validate_baseline(repo)
    if command == "status":
        if args.json: print(json.dumps({"schema_version":"sourcepack.baseline.status.v1", **status}, indent=2))
        else: print(f"Baseline: {status.get('state')}\n{status.get('message')}")
        return 0
    if command == "verify":
        if args.json: print(json.dumps({"schema_version":"sourcepack.baseline.verify.v1", **status}, indent=2))
        else: print(f"Baseline verify: {status.get('state')} - {status.get('message')}")
        return 0 if status.get("state") in {"present", "stale"} else 1
    if command == "path":
        print(status.get("packet_path") or "")
        return 0 if status.get("packet_path") else 1
    if command == "refresh":
        dirty, _ = git_worktree_dirty(repo)
        if dirty and not getattr(args, "force", False):
            print("ERROR: refusing baseline refresh with dirty worktree; commit/discard changes or pass --force after review.", file=sys.stderr); return 1
        class A: pass
        a=A(); a.repo="."; a.refresh=True; a.verbose=getattr(args,"verbose",False); a.json=args.json; a.quiet=False
        return cli_baseline(a)
    if command == "repair":
        print("Baseline repair checked metadata; no unsafe repair was attempted.")
        return 0 if status.get("state") in {"present", "stale"} else 1
    return None

def cli_schema(args) -> int:
    """Read-only offline schema commands; diagnostics intentionally never echo values."""
    from . import schema_contracts
    command = getattr(args, "schema_command", None)
    if command == "list":
        rows = [{"name": c.name, "artifact_schema_version": c.artifact_version, "json_schema_draft": schema_contracts.DRAFT_2020_12, "description": c.description, "aliases": list(c.aliases)} for c in schema_contracts.CONTRACTS]
        if args.json:
            print(json.dumps({"schemas": rows}, sort_keys=True, indent=2))
        else:
            for row in rows:
                aliases = f" aliases={','.join(row['aliases'])}" if row["aliases"] else ""
                print(f"{row['name']}  {row['artifact_schema_version']}  {row['json_schema_draft']}{aliases}\n  {row['description']}")
        return 0
    contract = schema_contracts.resolve(getattr(args, "schema_name", ""))
    if contract is None:
        if getattr(args, "json", False):
            print(json.dumps({"status": "unknown_schema", "schema": getattr(args, "schema_name", ""), "path": str(getattr(args, "file", "")), "exit_classification": "unknown_schema", "error_count": 1, "errors": [{"document_path": "/", "schema_path": "/", "keyword": "schema", "message": "unknown schema"}]}, sort_keys=True, indent=2))
        else:
            print("ERROR: unknown schema", file=sys.stderr)
        return schema_contracts.EXIT_UNKNOWN_SCHEMA
    if command == "show":
        sys.stdout.buffer.write(schema_contracts.schema_bytes(contract)); return 0
    path = Path(args.file)
    if not path.is_file():
        payload = {"status": "error", "schema": contract.name, "path": str(path), "exit_classification": "unreadable_input", "error_count": 1, "errors": [{"document_path": "/", "schema_path": "/", "keyword": "input", "message": "input is not a readable regular file"}]}
        if args.json: print(json.dumps(payload, sort_keys=True, indent=2))
        else: print("ERROR: input is not a readable regular file", file=sys.stderr)
        return schema_contracts.EXIT_UNREADABLE
    try:
        instance = schema_contracts.load_json(path)
    except schema_contracts.DuplicateKeyError:
        errors = [{"document_path": "/", "schema_path": "/", "keyword": "duplicate_key", "message": "JSON object contains a duplicate key"}]; code = schema_contracts.EXIT_MALFORMED_JSON; kind = "malformed_json"
    except UnicodeDecodeError:
        errors = [{"document_path": "/", "schema_path": "/", "keyword": "utf8", "message": "input is not valid UTF-8"}]; code = schema_contracts.EXIT_MALFORMED_JSON; kind = "malformed_json"
    except OSError:
        errors = [{"document_path": "/", "schema_path": "/", "keyword": "input", "message": "input is not readable"}]; code = schema_contracts.EXIT_UNREADABLE; kind = "unreadable_input"
    except json.JSONDecodeError:
        errors = [{"document_path": "/", "schema_path": "/", "keyword": "json", "message": "input is not valid JSON"}]; code = schema_contracts.EXIT_MALFORMED_JSON; kind = "malformed_json"
    else:
        try:
            errors = schema_contracts.validation_errors(contract, instance)
        except Exception:
            errors = [{"document_path": "/", "schema_path": "/", "keyword": "validator", "message": "validator failed"}]; code = schema_contracts.EXIT_INTERNAL; kind = "validator_failure"
        else:
            code = 0 if not errors else schema_contracts.EXIT_INVALID; kind = "valid" if not errors else "invalid"
    payload = {"status": kind, "schema": contract.name, "path": str(path), "exit_classification": kind, "error_count": len(errors), "errors": errors}
    if args.json: print(json.dumps(payload, sort_keys=True, indent=2))
    elif errors:
        for error in errors: print(f"ERROR [{error['keyword']}] {error['document_path']} {error['schema_path']}: {error['message']}", file=sys.stderr)
    else: print(f"VALID: {contract.name}")
    return code

def run_cli(args_list=None):
    parser = argparse.ArgumentParser(prog="sourcepack", description="Local guardrail for AI-assisted repo changes. PASS exits 0, WARN exits 0 locally unless --strict or --ci is used, and FAIL exits nonzero.")
    parser.add_argument("--version", action="store_true")
    subs = parser.add_subparsers(dest="command")
    schema_cmd = subs.add_parser("schema", help="list, export, and validate public JSON Schema contracts")
    schema_subs = schema_cmd.add_subparsers(dest="schema_command")
    schema_list = schema_subs.add_parser("list")
    schema_list.add_argument("--json", action="store_true")
    schema_show = schema_subs.add_parser("show")
    schema_show.add_argument("schema_name")
    schema_validate = schema_subs.add_parser("validate")
    schema_validate.add_argument("schema_name")
    schema_validate.add_argument("file")
    schema_validate.add_argument("--json", action="store_true")
    build = subs.add_parser("build")
    build.add_argument("input")
    build.add_argument("--out", required=True)
    build.add_argument("--force", action="store_true")
    build.add_argument("--max-file-size", type=int, default=1_000_000)
    build.add_argument("--include-hidden", action="store_true")
    build.add_argument("--no-redact", action="store_true")
    verify = subs.add_parser("verify")
    verify.add_argument("packet")
    verify.add_argument("--against")
    judge = subs.add_parser("judge")
    judge.add_argument("packet")
    judge.add_argument("ai_answer")
    judge.add_argument("--out")
    judge_patch_cmd = subs.add_parser("judge-patch", help="judge a unified diff against a packet", description="Judge a git-style unified diff against SourcePack packet evidence. The JSON and markdown reports include verdict, blockers, warnings, uncertainties, checked categories, not checked categories, next action, and report path.")
    judge_patch_cmd.add_argument("packet")
    judge_patch_cmd.add_argument("patch")
    judge_patch_cmd.add_argument("--out", required=True)
    map_cmd = subs.add_parser("map")
    map_cmd.add_argument("input")
    map_cmd.add_argument("--out", required=True)
    instr = subs.add_parser("instructions")
    instr.add_argument("packet")
    subs.add_parser("demo")
    init = subs.add_parser("init", help="initialize local SourcePack state", description="Initialize .sourcepack state. With --auto, create a safe baseline when possible and install git hooks. --strict installs hooks that block WARN and FAIL.")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--auto", action="store_true")
    init.add_argument("--strict", action="store_true")
    init.add_argument("--no-hook", action="store_true")
    init.add_argument("--refresh-baseline", action="store_true")
    init.add_argument("--force", action="store_true")
    init.add_argument("--install-hygiene-hooks", action="store_true")
    init.add_argument("--json", action="store_true")
    doctor_cmd = subs.add_parser("doctor")
    doctor_cmd.add_argument("--strict", action="store_true", help="exit nonzero on warnings as well as failures")
    exec_cmd = subs.add_parser("exec", help="run a local command and record bounded execution evidence")
    exec_cmd.add_argument("exec_command", nargs=argparse.REMAINDER)
    evidence_cmd = subs.add_parser("evidence", help="inspect local SourcePack execution evidence")
    evidence_subs = evidence_cmd.add_subparsers(dest="evidence_command")
    evidence_list = evidence_subs.add_parser("list")
    evidence_list.add_argument("--json", action="store_true")
    evidence_show = evidence_subs.add_parser("show")
    evidence_show.add_argument("entry_id")
    evidence_subs.add_parser("clear")
    evidence_export = evidence_subs.add_parser("export")
    evidence_export.add_argument("--json", action="store_true")
    prompt_cmd = subs.add_parser("prompt", help="write non-authoritative AI prompt context", description="Generate selective prompt context for an AI task. Prompt context is non-authoritative and never refreshes the trusted enforcement baseline.")
    prompt_cmd.add_argument("repo")
    prompt_cmd.add_argument("task", nargs="?")
    prompt_cmd.add_argument("--copy", action="store_true")
    prompt_cmd.add_argument("--verbose", action="store_true")
    prompt_cmd.add_argument("--json", action="store_true")
    baseline_cmd = subs.add_parser(
        "baseline",
        help="create or refresh an accepted enforcement baseline",
        description=(
            "Create or refresh .sourcepack/baseline after accepting the repository "
            "state. Later hash checks verify stored-artifact integrity; they do not "
            "authenticate its creator or establish trust."
        ),
    )
    baseline_cmd.add_argument("repo")
    baseline_cmd.add_argument("--force", action="store_true")
    baseline_cmd.add_argument("--refresh", action="store_true")
    baseline_cmd.add_argument("--verbose", action="store_true")
    baseline_cmd.add_argument("--json", action="store_true")
    baseline_cmd.add_argument("--quiet", action="store_true")
    diff_cmd = subs.add_parser(
        "diff",
        help="check repo changes against the accepted baseline",
        description=(
            "Judge working-tree or staged changes against the integrity-checked "
            "accepted .sourcepack/baseline. Hash checks verify stored-artifact "
            "integrity, not creator identity or trust. PASS exits 0. WARN exits 0 "
            "locally, but exits nonzero with --strict or --ci. FAIL exits nonzero. "
            "--json stays machine-readable."
        ),
    )
    diff_cmd.add_argument("repo")
    diff_cmd.add_argument("--staged", action="store_true")
    diff_cmd.add_argument("--verbose", action="store_true")
    diff_cmd.add_argument("--json", action="store_true")
    diff_cmd.add_argument("--strict", action="store_true", help="exit nonzero on WARN as well as FAIL")
    diff_cmd.add_argument("--ci", action="store_true", help="non-interactive CI mode; implies --strict and prints JSON")
    diff_cmd.add_argument("--exit-policy", choices=("warn-or-fail", "fail-only"), help="override diff verdict-to-process-exit behavior: warn-or-fail blocks WARN and FAIL; fail-only blocks only FAIL")
    diff_cmd.add_argument("--base-ref", help="base git ref for committed-range diff mode; requires --head-ref")
    diff_cmd.add_argument("--head-ref", help="head git ref for committed-range diff mode; requires --base-ref")
    diff_cmd.add_argument("--org-policy", help="external caller-designated organization policy file for diff policy evaluation")
    diff_cmd.add_argument("--org-policy-mode", choices=("optional", "required"), default="optional", help="organization-policy requirement mode for diff policy evaluation")
    install_hook = subs.add_parser("install-hook")
    install_hook.add_argument("repo")
    install_hook.add_argument("--strict", action="store_true")
    uninstall_hook = subs.add_parser("uninstall-hook")
    uninstall_hook.add_argument("repo")
    status_cmd = subs.add_parser("status", help="show SourcePack repo state", description="Show baseline, hook, report, git, and dirty-worktree state without changing the baseline.")
    status_cmd.add_argument("repo")
    status_cmd.add_argument("--json", action="store_true")
    replay_cmd = subs.add_parser("replay", help="reconstruct a saved SourcePack report or replay bundle")
    replay_cmd.add_argument("input_path")
    replay_cmd.add_argument("--json", action="store_true")
    ui_cmd = subs.add_parser("ui", help="serve the local SourcePack Workbench", description="serve the local SourcePack Workbench")
    ui_cmd.add_argument("repo", nargs="?", default=".")
    ui_cmd.add_argument("--host", default="127.0.0.1")
    ui_cmd.add_argument("--port", type=int, default=0)
    ui_cmd.add_argument("--no-open", action="store_true")
    workbench_cmd = subs.add_parser("workbench", help="alias for sourcepack ui", description="alias for sourcepack ui")
    workbench_cmd.add_argument("repo", nargs="?", default=".")
    workbench_cmd.add_argument("--host", default="127.0.0.1")
    workbench_cmd.add_argument("--port", type=int, default=0)
    workbench_cmd.add_argument("--no-open", action="store_true")
    report_command.register(subs)
    bundle_command.register(subs)
    explain_cmd = subs.add_parser("explain")
    explain_cmd.add_argument("reason_code")
    allow_cmd = subs.add_parser("allow")
    allow_cmd.add_argument("allow_type", choices=["dependency", "command", "path"])
    allow_cmd.add_argument("value")
    allow_cmd.add_argument("--reason", required=True)
    allow_cmd.add_argument("--expires")
    allow_cmd.add_argument("--high-risk", action="store_true")
    disallow_cmd = subs.add_parser("disallow")
    disallow_cmd.add_argument("allow_type", choices=["dependency", "command", "path"])
    disallow_cmd.add_argument("value")
    policy_cmd = subs.add_parser("policy")
    policy_subs = policy_cmd.add_subparsers(dest="policy_command")
    policy_subs.add_parser("list")
    policy_validate = policy_subs.add_parser("validate", help="validate .sourcepack/policy.json without changing repository state")
    policy_validate.add_argument("repo", nargs="?", default=".")
    policy_validate.add_argument("--json", action="store_true")
    policy_resolve = policy_subs.add_parser("resolve", help="resolve repository policy with an optional caller-designated local organization policy")
    policy_resolve.add_argument("repo", nargs="?", default=".")
    policy_resolve.add_argument("--json", action="store_true")
    policy_resolve.add_argument("--org-policy")
    policy_resolve.add_argument("--org-policy-mode", choices=("optional", "required"), default="optional")
    policy_remove = policy_subs.add_parser("remove")
    policy_remove.add_argument("policy_id")
    cloud_cmd = subs.add_parser("cloud", help="explicit optional hosted-control-plane commands")
    cloud_subs = cloud_cmd.add_subparsers(dest="cloud_command")
    for name in ("status", "login", "logout", "repo-list", "policy-pull", "policy-show"):
        item = cloud_subs.add_parser(name); item.add_argument("--json", action="store_true")
    register = cloud_subs.add_parser("repo-register"); register.add_argument("display_name"); register.add_argument("--json", action="store_true")
    for name in ("report", "evidence", "replay", "overrides"):
        item = cloud_subs.add_parser("upload-" + name); item.add_argument("path"); item.add_argument("--json", action="store_true")
    fleet_command.register(subs)
    reset_cmd = subs.add_parser("reset")
    reset_cmd.add_argument("repo", nargs="?", default=".")
    args = parser.parse_args(args_list)
    if args.version:
        print(__version__); return 0
    try:
        if args.command == "schema":
            return cli_schema(args)
        if args.command == "cloud":
            from .cloud import cli_cloud
            return cli_cloud(args)
        if args.command == "doctor":
            return doctor(strict=getattr(args, "strict", False))
        if args.command == "exec":
            if args.exec_command and args.exec_command[0] == "--":
                args.exec_command = args.exec_command[1:]
            return cli_exec(args)
        if args.command == "evidence":
            return cli_evidence(args)
        if args.command == "init":
            return cli_init(args)
        if args.command == "prompt":
            return cli_prompt(args)
        if args.command == "baseline":
            lifecycle = cli_baseline_lifecycle(args)
            if lifecycle is not None:
                return lifecycle
            return cli_baseline(args)
        if args.command == "diff":
            return cli_diff(args)
        if args.command == "install-hook":
            return cli_install_hook(args)
        if args.command == "uninstall-hook":
            return cli_uninstall_hook(args)
        if args.command == "status":
            return cli_status(args)
        if args.command == "explain":
            return cli_explain(args)
        if args.command == "allow":
            return cli_allow(args)
        if args.command == "disallow":
            return cli_disallow(args)
        if args.command == "policy":
            return cli_policy(args)
        if args.command == "fleet":
            return fleet_command.cli_fleet(args)
        if args.command == "bundle":
            return bundle_command.cli_bundle(args)
        if args.command == "reset":
            return cli_reset(args)
        if args.command == "replay":
            result, code = reconstruct_replay(args.input_path)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(render_replay_human(result), end="")
            return code
        if args.command in {"ui", "workbench"}:
            from .workbench import serve_workbench
            return serve_workbench(args.repo, host=args.host, port=args.port, open_browser=not args.no_open)
        if args.command == "report":
            result = report_command.cli_report(args)
            if result == 1 and getattr(args, "report_command", None) is None:
                parser.parse_args(["report", "--help"])
            return result
        if args.command == "build":
            scanner = SourceScanner(args.input, max_file_size=args.max_file_size, include_hidden=args.include_hidden, redact=not args.no_redact).scan()
            out = PacketWriter(args.out, scanner, force=args.force).write_all()
            print(f"Packet built successfully at {out}"); return 0
        if args.command == "map":
            scanner = SourceScanner(args.input).scan()
            with tempfile.TemporaryDirectory() as td:
                packet = PacketWriter(td, scanner, force=True).write_all()
                reality_map = json.loads((packet / "reality_map.json").read_text(encoding="utf-8"))
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
            print(f"Reality map written to {out_path}"); return 0
        if args.command == "instructions":
            packet = Path(args.packet)
            instructions_path = packet / "ai_instructions.md"
            if instructions_path.exists():
                print(instructions_path.read_text(encoding="utf-8"), end=""); return 0
            reality_path = packet / "reality_map.json"
            if not reality_path.exists():
                print("ERROR: missing ai_instructions.md and reality_map.json", file=sys.stderr); return 1
            reality_map = json.loads(reality_path.read_text(encoding="utf-8"))
            text = render_ai_instructions(reality_map)
            instructions_path.write_text(text, encoding="utf-8")
            print(text, end=""); return 0
        if args.command == "demo":
            examples_root = resources.files("sourcepack") / "examples"
            with resources.as_file(examples_root) as examples_path:
                demo_repo = examples_path / "demo_repo"
                fake_patch = examples_path / "fake_ai_patch.diff"
                fake_answer = examples_path / "fake_ai_answer.md"
                if not demo_repo.exists() or not fake_patch.exists() or not fake_answer.exists():
                    print("ERROR: packaged examples/demo_repo, examples/fake_ai_patch.diff, and examples/fake_ai_answer.md are required", file=sys.stderr); return 1
                tmp = Path(tempfile.mkdtemp(prefix="sourcepack_demo_"))
                packet = tmp / "packet"
                patch_judgment = tmp / "patch_judgment"
                judgment = tmp / "judgment"
                PacketWriter(packet, SourceScanner(demo_repo).scan(), force=True).write_all()
                verification_output = io.StringIO()
                with contextlib.redirect_stdout(verification_output):
                    packet_ok = verify_packet(packet)
                if not packet_ok:
                    print(verification_output.getvalue(), end="", file=sys.stderr)
                    return 1
                with contextlib.redirect_stdout(io.StringIO()):
                    judge_ai_answer(packet, fake_answer, judgment)
                    report = judge_patch(packet, fake_patch, patch_judgment)
                traffic = patch_report_to_traffic(report, str(patch_judgment / "patch_judgment_report.json"))
                blockers = [f for f in traffic.get("blockers", []) if f.get("id") == "unsupported_dependency"]
                if not blockers:
                    print("ERROR: demo did not produce the expected unsupported_dependency finding", file=sys.stderr)
                    return 1
                print("RED LIGHT: commit blocked")
                for finding in blockers:
                    evidence = finding.get("evidence") or "dependency"
                    path = finding.get("path") or "sourcepack/server.py"
                    print(f"unsupported_dependency: {path} imports {evidence}, but {evidence} is not declared.")
                print()
                print(render_traffic(traffic), end="")
                print(f"Demo packet: {packet}")
                print(f"Demo judgment: {judgment}")
                print(f"Demo patch judgment: {patch_judgment}")
                return 0
        if args.command == "verify":
            return 0 if verify_packet(args.packet, args.against) else 1
        if args.command == "judge":
            judge_ai_answer(args.packet, args.ai_answer, args.out); return 0
        if args.command == "judge-patch":
            report = judge_patch(args.packet, args.patch, args.out)
            return 1 if report.get("malformed_diff") else 0
        parser.print_help(); return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
