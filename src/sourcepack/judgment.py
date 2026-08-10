from __future__ import annotations

import fnmatch
import base64
import hashlib
import json
import os
import platform
import tomllib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Final, Iterable
from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_OUTPUT_LIMIT, GIT_RETURNCODE_TIMEOUT, run_git as canonical_run_git, run_git_bounded as canonical_run_git_bounded, run_git_bytes as canonical_run_git_bytes
from .diff_parser import PatchFileChange, normalize_diff_path as _normalize_diff_path, parse_unified_diff, quote_git_path
from .baseline import BaselineLockError, baseline_report_fields, build_current_baseline, generated_untracked_baseline_artifacts, validate_baseline
from .ecosystems.python import PY_IMPORT_ALIASES
from .packet import PacketWriter, SourceScanner, _read_stable_verification_file
from .paths import ensure_sourcepack_dirs, operational_sourcepack_artifact_path
from .reports.json import build_replay_bundle, normalized_finding, traffic_report, write_user_report
from .policy import PolicyMode, normalize_policy_mode, exit_code as policy_exit_code, load_policy_config, finding_ignored_by_policy, policy_path_matches, resolve_effective_policy
from .policy_authority import POLICY_AUTHORITY_ERROR, guard_effective_policy_result
from .execution_ledger import execution_findings
from .local_allow_trust import active_allow_records, readable_allow_file_matches_active
from .commands import resolve_command
from .dependencies import resolve_js_import, resolve_python_import
from .worktree_collision import inspect_symlink_transitions

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"

from .repository_evidence import (
    DEFAULT_IGNORED_DIRS,
    DEFAULT_IGNORED_PATTERNS,
    DEFAULT_TEXT_EXTENSIONS,
    SECRET_PATTERNS,
    COMMON_DEPENDENCIES,
    FEATURE_NAMES,
    GIT_TIMEOUT_SECONDS,
    NATURAL_LANGUAGE_COMMAND_TARGETS,
    PACKET_ARTIFACT_LIMIT_BYTES,
    POLICY_LEDGER_LIMIT_BYTES,
    POLICY_LEDGER_LINE_LIMIT_BYTES,
    POLICY_LEDGER_RECORD_LIMIT,
    INVENTORY_RECORD_LIMIT,
    _command_claims,
    utc_now,
    sha256_file,
    sha256_text,
    estimate_tokens,
    is_probably_binary,
    matches_any,
    redact_secrets,
    IncludedFile,
    IgnoredFile,
    _tracked_file_inventory,
    _included_paths,
    _package_json_scripts,
    _is_poetry_project,
    _uses_unittest,
    generate_reality_map,
    render_ai_instructions,
    _load_packet_bytes,
    _load_packet_json,
    load_manifest,
    PATHLIKE_EXTENSIONS,
    PROJECT_PATH_PREFIXES,
    _normalize_ai_ref,
    _looks_like_ai_file_ref,
    extract_refs,
    _packet_file_contents,
    _normalize_dependency_name,
    _dependency_name_for_import,
    _is_js_local_specifier,
    _js_package_root,
    _python_dependency_names_from_requirement_lines,
    _python_dependency_names_from_pyproject,
    _add_common_dependency,
    dependency_inventory,
    _has_import,
    PDF_DEPENDENCIES,
    _declares_pdf_dependency,
    feature_inventory,
    PROTECTED_PACKET_ARTIFACTS,
    _normalize_inventory_path,
    InventoryAuthority,
    _baseline_inventory_from_packet,
    known_files,
    supported_commands_inventory,
    docker_evidence,
    python_project_evidence,
    node_project_evidence,
    extract_js_import_specifiers_from_text,
    extract_imports_from_text
)

def _materialize_packet_worktree(packet: Path, overlay: dict[str, str] | None = None) -> tempfile.TemporaryDirectory[str]:
    tmp = tempfile.TemporaryDirectory(prefix="sourcepack-resolver-")
    root = Path(tmp.name)
    contents = _packet_file_contents(packet)
    if overlay:
        contents.update(overlay)
    for rel, content in contents.items():
        normalized, unsafe = _normalize_diff_path(rel)
        if unsafe or not normalized:
            continue
        target = root / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp


def _dependency_additions_from_patch(changes: list[PatchFileChange]) -> set[str]:
    return _declared_dependency_names_from_patch(changes)


def analyze_patch(packet_path: str | Path, patch_text: str, changes: list[PatchFileChange] | None = None, trusted_files: set[str] | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    reality_data = _load_packet_json(packet, "reality_map.json") if (packet / "reality_map.json").exists() else generate_reality_map(manifest, packet)
    reality = reality_data if isinstance(reality_data, dict) else {}
    inventory = _baseline_inventory_from_packet(packet, manifest)
    files, baseline_inventory_loaded = inventory
    if trusted_files is not None:
        files = set(trusted_files)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    if changes is None:
        changes = parse_unified_diff(patch_text)
    patch_deps = _dependency_additions_from_patch(changes)
    report = {
        "patch_judgment_schema_version": "1.0",
        "verdict": "PASS",
        "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [],
        "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "git_path_modifications": [], "warnings": [],
    }
    report["baseline_inventory_authority"] = {"status": inventory.status, "complete": inventory.complete, "reason": inventory.reason}
    if inventory.status == "failed":
        report["verdict"] = "FAIL"
        report["baseline_inventory_failed"] = True
        report["warnings"].append("Trusted baseline inventory could not be acquired safely.")
    if any(ch.unsafe_path for ch in changes):
        report["path_escape"] = True
    all_added = []
    for ch in changes:
        report["modified_files"].append(ch.path)
        if ch.new_file:
            report["new_files"].append(ch.path)
        elif ch.operation in {"rename", "copy"}:
            pass
        elif ch.path not in files:
            if baseline_inventory_loaded or ch.path in _included_paths(manifest):
                report["missing_modified_files"].append(ch.path)
            else:
                report.setdefault("uncertain_modified_files", []).append(ch.path)
        if ch.deleted_file:
            report["deleted_files"].append(ch.path)
        protected = ch.path.startswith(".sourcepack/")
        git_internal = ch.path == ".git" or ch.path.startswith(".git/")
        workflow = ch.path.startswith(".github/workflows/")
        if protected:
            report["protected_artifact_modifications"].append(ch.path)
        if git_internal:
            report.setdefault("git_path_modifications", []).append(ch.path)
        if workflow:
            report.setdefault("uncertainties", []).append({"id": "workflow_change", "message": f"{ch.path} changes repository automation and requires review", "path": ch.path, "evidence": ch.path})
        if ch.operation in {"rename", "copy"}:
            report.setdefault("uncertainties", []).append({"id": "unsupported_rename_copy", "message": f"{ch.operation} semantics for {ch.path} require review", "path": ch.path, "evidence": ch.old_path or ch.path})
        added = "\n".join(ch.added_lines or [])
        all_added.append(added)
        for imported in extract_imports_from_text(added, Path(ch.path).suffix.lower()):
            for dep in COMMON_DEPENDENCIES:
                if _normalize_dependency_name(imported) == _normalize_dependency_name(dep) and dep not in deps and dep not in patch_deps:
                    report["unsupported_dependencies"].append(dep)
    added_text = "\n".join(all_added)
    supported = supported_commands_inventory(reality)
    added_paths = {ch.path for ch in changes}
    compose_added = any(Path(path).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for path in added_paths)
    if re.search(r"docker\s+compose\s+up", added_text, re.I):
        evidence = docker_evidence(files)
        if compose_added:
            report["warnings"].append("Patch adds Docker Compose support used by commands; review the new support.")
            report.setdefault("declared_commands", []).append("docker compose up")
        elif not evidence["compose"]:
            report["unsupported_commands"].append("docker compose up")
    patch_scripts = set()
    command_uncertainties = []
    for ch in changes:
        if Path(ch.path).name.lower() != "package.json":
            continue
        base = _packet_file_contents(packet).get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        try:
            package = json.loads(post)
        except json.JSONDecodeError:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
            continue
        package_scripts = package.get("scripts")
        if isinstance(package_scripts, dict):
            patch_scripts.update(str(script) for script in package_scripts if isinstance(script, str) and script not in scripts)
    if command_uncertainties:
        report.setdefault("uncertainties", []).extend(command_uncertainties)
    for cmd in sorted(set(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))):
        normalized = cmd if cmd == "npm test" else cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script in patch_scripts:
                report["warnings"].append(f"Patch adds npm script {script} used by commands; review the new support.")
                report.setdefault("declared_commands", []).append(normalized)
            elif script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append(normalized)
    if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
        py = python_project_evidence(files, deps)
        if not (py["pytest"] or py["tests"] or "pytest" in supported):
            report["unsupported_commands"].append("pytest")
    packet_contents = _packet_file_contents(packet)
    make_text = packet_contents.get("Makefile") or packet_contents.get("makefile") or ""
    make_targets = {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.:-]+)\s*:", make_text, re.M)}
    for cmd in sorted(_command_claims(r"\bmake\s+[A-Za-z0-9_.:-]+", added_text)):
        target = cmd.split(None, 1)[1]
        if target not in make_targets:
            report["unsupported_commands"].append(cmd)
    if not baseline_inventory_loaded:
        outside_context = sorted({
            ch.path for ch in changes
            if not ch.new_file
            and not ch.deleted_file
            and ch.path not in _included_paths(manifest)
        })
        if outside_context:
            report.setdefault("uncertainties", []).append({"id": "baseline_inventory_missing", "message": "Baseline packet lacks full file inventory; modified files outside prompt context could not be checked against tracked repo inventory.", "evidence": ", ".join(outside_context)})
    if report["new_files"]:
        report["warnings"].append("Patch creates new files that were not part of the original packet reality.")
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "path_escape", "baseline_inventory_failed"]
    if any(report.get(k) for k in fail_keys):
        report["verdict"] = "FAIL"
    elif report["new_files"] or report["warnings"] or report.get("uncertainties"):
        report["verdict"] = "WARN"
    for key in ["modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "warnings"]:
        report[key] = sorted(set(report[key]))
    return report



from .ai_analysis import (
    _has_negation_before,
    _ai_dependency_actions,
    _ai_js_dependency_actions,
    _ai_command_instructions,
    analyze_ai_answer
)

# Compatibility wrapper preserves the facade's injectable Git adapter while
# repository_evidence owns inventory construction.
from . import repository_evidence as _repository_evidence


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    return _repository_evidence._tracked_file_inventory(
        root, included_records, run_git_bytes=run_git_bytes
    )


LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PY_STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"typing", "pathlib", "json", "os", "sys", "re", "subprocess", "datetime", "unittest"}
PY_DEP_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}



def _latest_report_html_path(repo: str | Path) -> Path:
    return ensure_sourcepack_dirs(repo)["latest_html"]




def finalize_diff_report(repo: str | Path | None, report: dict, args, stem: str = "diff") -> dict:
    full = dict(report)
    if getattr(args, "ci", False):
        full["ci"] = True
    if repo is not None:
        try:
            write_user_report(repo, full, stem)
            full["persistence"] = {"status": "written"}
        except Exception as exc:
            full["persistence"] = {"status": "failed", "reason": str(exc)}
    return full


def git_metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, dirty_state = git_worktree_dirty(root)
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": dirty if dirty_state is None else None,
        "dirty_state": dirty_state,
    }


def scanner_config_hash() -> str:
    payload = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "ignored_patterns": sorted(DEFAULT_IGNORED_PATTERNS),
        "text_extensions": sorted(DEFAULT_TEXT_EXTENSIONS),
        "max_file_size": 1_000_000,
        "include_hidden": False,
        "redact": True,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))



def build_prompt_context(repo: str | Path) -> dict:
    paths = ensure_sourcepack_dirs(repo)
    PacketWriter(paths["prompt_packet"], SourceScanner(repo).scan(), force=True).write_all()
    shutil.copy2(paths["prompt_packet"] / "reality_map.json", paths["prompt_reality"])
    shutil.copy2(paths["prompt_packet"] / "ai_instructions.md", paths["prompt_instructions"])
    return paths


def render_prompt(task: str, instructions: str, reality: dict) -> str:
    def bullets(items):
        return "\n".join(f"- {item}" for item in items) if items else "- None detected"
    return "\n".join(["# SourcePack Verified AI Prompt", "", "## User Task", "", task, "", "## AI Grounding Instructions", "", instructions.rstrip(), "", "## Compact Reality Map Summary", "", f"Project types: {', '.join(reality.get('project_types') or ['unknown'])}", f"Included files: {reality.get('included_file_count', 0)}", "", "## Supported Commands", "", bullets(reality.get('supported_commands', [])), "", "## Detected Dependencies", "", bullets(reality.get('detected_dependencies', [])), "", "## Supported Capabilities", "", bullets(reality.get('supported_capabilities', [])), "", "## Unknown and Unsupported Boundaries", "", bullets(reality.get('claim_boundaries', [])), "", "Cite exact file paths for project-specific claims.", "Do not invent files, dependencies, commands, services, or capabilities.", "Absence of evidence means unknown, not impossible.", ""])


def copy_to_clipboard(text: str) -> bool:
    system = platform.system().lower()
    cmds = [["pbcopy"]] if system == "darwin" else [["clip"]] if system == "windows" else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            if subprocess.run(cmd, input=text, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
                return True
        except Exception:
            pass
    return False


def _is_local_python_import(name: str, path: str, files: set[str]) -> bool:
    candidates = {f"{name}.py", f"{name}/__init__.py", f"src/{name}.py", f"src/{name}/__init__.py"}
    parent = str(Path(path).parent).replace("\\", "/")
    if parent != ".":
        candidates |= {f"{parent}/{name}.py", f"{parent}/{name}/__init__.py"}
    return bool(candidates & files)


JS_DEP_SECTIONS = {"dependencies", "devDependencies", "peerDependencies", "optionalDependencies"}


def _package_json_declared_deps_from_added_lines(lines: list[str]) -> set[str]:
    added = "\n".join(lines)
    try:
        package = json.loads(added)
    except json.JSONDecodeError:
        package = None
    deps: set[str] = set()
    if isinstance(package, dict):
        for section in JS_DEP_SECTIONS:
            section_deps = package.get(section)
            if isinstance(section_deps, dict):
                deps.update(dep.lower() for dep in section_deps)
        if deps:
            return deps
    for section in JS_DEP_SECTIONS:
        for body in re.findall(rf'"{section}"\s*:\s*\{{(.*?)\}}', added, re.I | re.S):
            deps.update(m.lower() for m in re.findall(r'"(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)"\s*:', body))
    return deps


def _apply_patch_change_to_text(original: str, change: PatchFileChange) -> str | None:
    if change.deleted_file:
        return ""
    result = original.splitlines()
    out: list[str] = []
    idx = 0
    saw_hunk = False
    for line in change.diff_lines or []:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not m:
                return None
            old_start = max(int(m.group(1)) - 1, 0)
            if old_start < idx or old_start > len(result):
                return None
            out.extend(result[idx:old_start])
            idx = old_start
            saw_hunk = True
        elif line.startswith(" "):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            out.append(result[idx])
            idx += 1
        elif line.startswith("-"):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            idx += 1
        elif line.startswith("+"):
            out.append(line[1:])
    if not saw_hunk and not change.new_file:
        return None
    out.extend(result[idx:])
    return "\n".join(out) + ("\n" if original.endswith("\n") or change.new_file else "")


def _python_dependency_names_by_scope_from_pyproject(content: str) -> dict[str, set[str]]:
    scopes = {"runtime": set(), "dev": set(), "optional": set()}
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return scopes

    def add_req(target: set[str], req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                target.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_req(scopes["runtime"], req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_req(scopes["optional"], req)
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            section = poetry.get("dependencies", {})
            if isinstance(section, dict):
                for dep in section:
                    if dep.lower() != "python":
                        scopes["runtime"].add(_normalize_dependency_name(dep))
            for section_name in ("dev-dependencies",):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_req(scopes["dev"], req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_req(scopes["dev"], req)
    return scopes


def _declared_dependency_scopes_by_ecosystem(manifest: dict, packet: Path, source_path: str | None = None) -> dict[str, dict[str, set[str]]]:
    contents = _packet_file_contents(packet)
    scopes = {"python": {"runtime": set(), "dev": set(), "optional": set()}, "js": {"runtime": set(), "dev": set(), "optional": set()}}
    for rel, content in contents.items():
        manifest_parent = PurePosixPath(rel).parent
        source_parent = PurePosixPath(source_path).parent if source_path else None
        if source_parent is not None and manifest_parent != PurePosixPath(".") and manifest_parent not in (source_parent, *source_parent.parents):
            continue
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(content)
            for key, values in parsed.items():
                scopes["python"][key].update(values)
        elif name == "requirements.txt":
            scopes["python"]["runtime"].update(_python_dependency_names_from_requirement_lines(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            target = "dev" if any(x in name for x in ("dev", "test")) else "runtime"
            scopes["python"][target].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            section_map = {"dependencies": "runtime", "peerDependencies": "runtime", "optionalDependencies": "optional", "devDependencies": "dev"}
            for section, target in section_map.items():
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    scopes["js"][target].update(dep.lower() for dep in section_deps)
    return scopes


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    name = PurePosixPath(p).name
    return p.startswith(("tests/", "test/")) or "/__tests__/" in f"/{p}" or name.endswith("_test.py") or any(name.endswith(s) for s in (".test.js", ".test.ts", ".spec.js", ".spec.ts", ".test.jsx", ".test.tsx", ".spec.jsx", ".spec.tsx"))


def _dependency_scope_status(dep: str, scopes: dict[str, set[str]], path: str) -> str:
    dep = _normalize_dependency_name(dep)
    if dep in scopes.get("runtime", set()):
        return "supported"
    if dep in scopes.get("dev", set()):
        return "supported" if _is_test_path(path) else "scope_review"
    if dep in scopes.get("optional", set()):
        return "scope_review"
    return "missing"


def _declared_dependency_names_from_patch_by_ecosystem_structural(changes: list[PatchFileChange], contents: dict[str, str]) -> tuple[dict[str, set[str]], list[dict]]:
    deps = {"python": set(), "js": set()}
    uncertainties: list[dict] = []
    for ch in changes:
        name = Path(ch.path).name.lower()
        if name not in {"package.json", "pyproject.toml"} and not (name.startswith("requirements") and name.endswith(".txt")):
            continue
        base = contents.get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        if name == "package.json":
            try:
                package = json.loads(post)
            except json.JSONDecodeError:
                uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
                continue
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    deps["js"].update(dep.lower() for dep in section_deps)
        elif name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(post)
            deps["python"].update(set().union(*parsed.values()))
        else:
            deps["python"].update(_python_dependency_names_from_requirement_lines(post))
    return deps, uncertainties


def _declared_dependency_names_from_patch_by_ecosystem(changes: list[PatchFileChange]) -> dict[str, set[str]]:
    deps = {"python": set(), "js": set()}
    for ch in changes:
        added = "\n".join(ch.added_lines or [])
        name = Path(ch.path).name.lower()
        if name == "package.json":
            deps["js"].update(_package_json_declared_deps_from_added_lines(ch.added_lines or []))
        elif name == "pyproject.toml":
            deps["python"].update(_python_dependency_names_from_pyproject(added))
        elif name.startswith("requirements") and name.endswith(".txt"):
            deps["python"].update(_python_dependency_names_from_requirement_lines(added))
    return deps


def _declared_dependency_names_from_patch(changes: list[PatchFileChange]) -> set[str]:
    scoped = _declared_dependency_names_from_patch_by_ecosystem(changes)
    return scoped["python"] | scoped["js"]


def _declared_dependency_names_by_ecosystem(manifest: dict, packet: Path) -> dict[str, set[str]]:
    declared = {"python": set(), "js": set()}
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            declared["python"].update(_python_dependency_names_from_pyproject(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            declared["python"].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    declared["js"].update(dep.lower() for dep in section_deps)
    return declared


def _declared_dependency_names(manifest: dict, packet: Path) -> set[str]:
    scoped = _declared_dependency_names_by_ecosystem(manifest, packet)
    return scoped["python"] | scoped["js"]


def _ambiguous_root_requirement_dependencies(packet: Path) -> set[str]:
    """Return dependencies with conflicting exact pins in peer runtime manifests."""
    pins_by_dependency: dict[str, set[str]] = {}
    specialized = re.compile(r"^requirements[-_.](?:dev|development|test|testing|docs?|documentation)(?:[-_.]|\.txt$)")
    for rel, content in _packet_file_contents(packet).items():
        name = Path(rel).name.lower()
        if "/" in rel or not name.startswith("requirements") or not name.endswith(".txt"):
            continue
        if specialized.match(name):
            continue
        for line in content.splitlines():
            match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([^\s;#]+)", line)
            if not match:
                continue
            dependency = _normalize_dependency_name(match.group(1))
            pins_by_dependency.setdefault(dependency, set()).add(match.group(2))
    return {
        dependency
        for dependency, pins in pins_by_dependency.items()
        if len(pins) > 1
    }


def _workspace_package_names(packet: Path) -> set[str]:
    contents = _packet_file_contents(packet)
    root = {}
    try:
        root = json.loads(contents.get("package.json", "{}"))
    except json.JSONDecodeError:
        return set()
    workspaces = root.get("workspaces")
    patterns = workspaces if isinstance(workspaces, list) else workspaces.get("packages", []) if isinstance(workspaces, dict) else []
    names: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern.endswith("/*"):
            continue
        prefix = pattern[:-2].replace("\\", "/").strip("/")
        for rel, content in contents.items():
            rel_posix = rel.replace("\\", "/")
            if PurePosixPath(rel_posix).name == "package.json" and rel_posix.startswith(prefix + "/"):
                try:
                    package = json.loads(content)
                except json.JSONDecodeError:
                    continue
                name = package.get("name")
                if isinstance(name, str):
                    names.add(name.lower())
    return names


def _is_js_alias_specifier(imported: str) -> bool:
    return imported.startswith(("@/", "~/"))


def _js_alias_local(imported: str, files: set[str], contents: dict[str, str]) -> bool | None:
    configs = []
    for cfg in ("tsconfig.json", "jsconfig.json"):
        if cfg in contents:
            try:
                configs.append(json.loads(contents[cfg]))
            except json.JSONDecodeError:
                return None
    for cfg in configs:
        opts = cfg.get("compilerOptions", {}) if isinstance(cfg, dict) else {}
        base = str(opts.get("baseUrl", ".")).strip("./")
        paths = opts.get("paths", {})
        candidates = []
        if isinstance(paths, dict):
            for alias, targets in paths.items():
                prefix = alias[:-1] if alias.endswith("*") else alias
                if imported.startswith(prefix):
                    rest = imported[len(prefix):]
                    for target in targets if isinstance(targets, list) else []:
                        tprefix = target[:-1] if isinstance(target, str) and target.endswith("*") else target
                        candidates.append((tprefix + rest).strip("/"))
        if base and not imported.startswith("@") and not imported.startswith("~"):
            candidates.append(f"{base}/{imported}".strip("/"))
        for c in candidates:
            variants = {c, f"{c}.ts", f"{c}.tsx", f"{c}.js", f"{c}.jsx", f"{c}/index.ts", f"{c}/index.tsx", f"{c}/index.js", f"{c}/index.jsx"}
            if variants & files:
                return True
        if candidates:
            return None
    return False


def _is_high_risk_binary_path(rel: str) -> bool:
    normalized = rel.replace("\\", "/").lstrip("/")
    high_risk_prefixes = (".sourcepack/", ".git/", ".github/workflows/")
    high_risk_names = {"pyproject.toml", "package.json", "package-lock.json", "uv.lock", "poetry.lock"}
    return normalized.startswith(high_risk_prefixes) or Path(normalized).name in high_risk_names


UNSUPPORTED_ECOSYSTEM_MARKERS = {
    "gemfile": ("Gemfile", "Ruby/Bundler dependency validation is not implemented"),
    "composer.json": ("composer.json", "PHP/Composer dependency validation is not implemented"),
    "main.tf": ("main.tf", "Terraform module/provider validation is not implemented"),
    "flake.nix": ("flake.nix", "Nix flake validation is not implemented"),
    "cargo.toml": ("Cargo.toml", "Rust dependency validation is not implemented"),
    "go.mod": ("go.mod", "Go module dependency validation is not implemented"),
    "pom.xml": ("pom.xml", "Maven dependency validation is not implemented"),
    "build.gradle": ("build.gradle", "Gradle dependency validation is not implemented"),
    "build.gradle.kts": ("build.gradle.kts", "Gradle dependency validation is not implemented"),
    "settings.gradle": ("settings.gradle", "Gradle workspace validation is not implemented"),
    "settings.gradle.kts": ("settings.gradle.kts", "Gradle workspace validation is not implemented"),
    "*.csproj": ("*.csproj", ".NET/NuGet dependency validation is not implemented"),
}


def _diff_header_paths(line: str) -> tuple[str | None, str | None, bool]:
    prefix = "diff --git a/"
    if not line.startswith(prefix):
        return None, None, True
    remainder = line[len(prefix):]
    sep = " b/"
    split_at = remainder.rfind(sep)
    if split_at < 0:
        return None, None, True
    old_raw = "a/" + remainder[:split_at]
    new_raw = "b/" + remainder[split_at + len(sep):]
    old_path, old_unsafe = _normalize_diff_path(old_raw)
    new_path, new_unsafe = _normalize_diff_path(new_raw)
    return old_path, new_path, bool(old_unsafe or new_unsafe)


def _binary_diff_paths_from_patch(patch_text: str) -> list[str]:
    paths: list[str] = []
    current_new_path: str | None = None
    current_unsafe = False
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            _old_path, new_path, unsafe = _diff_header_paths(line)
            current_new_path = new_path
            current_unsafe = unsafe
        elif line.startswith("Binary files "):
            m = re.search(r" b/(.+) differ$", line)
            raw = m.group(1) if m else None
            if raw is None:
                paths.append("unknown")
                continue
            rel, unsafe = _normalize_diff_path(raw)
            paths.append("unknown" if unsafe else rel)
        elif line == "GIT binary patch":
            if current_unsafe or not current_new_path:
                paths.append("unknown")
            else:
                paths.append(current_new_path)
    return paths


def _unsupported_ecosystem_uncertainties(files: set[str], changes: list[PatchFileChange]) -> list[dict]:
    names = {Path(f).name.lower() for f in files}
    names.update(Path(ch.path).name.lower() for ch in changes)
    for ch in changes:
        if ch.path.lower().endswith(".csproj"):
            names.add("*.csproj")
    uncertainties = []
    for marker, (evidence, message) in sorted(UNSUPPORTED_ECOSYSTEM_MARKERS.items()):
        if marker in names:
            uncertainties.append({"id": "unsupported_ecosystem", "message": f"{evidence} detected, but {message}", "evidence": evidence})
    return uncertainties

def judge_patch_text(packet_path: str | Path, patch_text: str, *, trusted_files: set[str] | None = None, worktree_root: str | Path | None = None) -> dict:
    if re.search(r"(?m)^@@", patch_text) and "diff --git " not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    if re.search(r"(?m)^@@(?! -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)", patch_text):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    changes = parse_unified_diff(patch_text)
    unsafe_paths = sorted({ch.path for ch in changes if ch.unsafe_path and ch.path})
    if any(ch.operation == "malformed" for ch in changes) and not any(ch.unsafe_path for ch in changes):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    if any(ch.unsafe_path for ch in changes):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "path_escape": True, "path_escape_paths": unsafe_paths}
    if patch_text.strip() and not changes and "Binary files " not in patch_text and "GIT binary patch" not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    report = analyze_patch(packet_path, patch_text, changes, trusted_files)
    packet = Path(packet_path); manifest = load_manifest(packet); files = known_files(manifest, packet); contents = _packet_file_contents(packet)
    if worktree_root is not None:
        baseline_files, baseline_inventory_loaded = _baseline_inventory_from_packet(packet, manifest)
        if trusted_files is not None:
            tracked_paths = set(trusted_files)
            tracked_authority = {"source": "base_tree", "status": "complete", "complete": True, "reason": None}
        elif baseline_inventory_loaded:
            tracked_paths = set(baseline_files)
            tracked_authority = {"source": "trusted_baseline_inventory", "status": "complete", "complete": True, "reason": None}
        else:
            tracked_paths = None
            tracked_authority = {"source": "trusted_baseline_inventory", "status": "unavailable", "complete": False, "reason": "baseline_inventory_missing"}
        report["symlink_worktree_inspection"] = inspect_symlink_transitions(Path(worktree_root), changes, tracked_paths=tracked_paths, tracked_authority=tracked_authority)
    existing_declared = _declared_dependency_names_by_ecosystem(manifest, packet)
    ambiguous_requirements = _ambiguous_root_requirement_dependencies(packet)
    patch_declared, manifest_uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
    if manifest_uncertainties:
        report.setdefault("uncertainties", []).extend(manifest_uncertainties)
    workspace_names = _workspace_package_names(packet)
    unsupported = set(report.get("unsupported_dependencies", []))
    for ch in changes:
        suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
        scopes = _declared_dependency_scopes_by_ecosystem(manifest, packet, ch.path)
        if suffix == ".py":
            for imported in extract_imports_from_text(added, suffix):
                if imported in PY_STDLIB or imported.startswith(".") or _is_local_python_import(imported, ch.path, files):
                    continue
                dep_name = _dependency_name_for_import(imported)
                if dep_name in ambiguous_requirements:
                    unsupported.discard(imported); unsupported.discard(dep_name)
                    report.setdefault("uncertainties", []).append({"id": "dependency_manifest_uncertain", "message": f"{dep_name} has contradictory root requirements evidence", "path": ch.path, "evidence": dep_name})
                    continue
                scope_status = _dependency_scope_status(dep_name, scopes["python"], ch.path)
                if scope_status == "scope_review":
                    unsupported.discard(imported); unsupported.discard(dep_name)
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{dep_name} is declared outside the runtime dependency scope", "path": ch.path, "evidence": dep_name})
                elif scope_status == "missing" and dep_name not in patch_declared["python"]:
                    unsupported.add(imported)
                elif dep_name in patch_declared["python"]:
                    unsupported.discard(imported); unsupported.discard(dep_name)
                    report.setdefault("uncertainties", []).append({"id": "declared_dependency", "message": f"{dep_name} is declared in the same patch and requires review", "path": ch.path, "evidence": dep_name})
        elif suffix in JS_EXTS:
            for imported in extract_imports_from_text(added, suffix):
                if _is_js_local_specifier(imported):
                    continue
                pkg = _js_package_root(imported)
                local_alias = _js_alias_local(imported, files, contents)
                if pkg in workspace_names or local_alias is True:
                    continue
                if local_alias is None or (local_alias is False and _is_js_alias_specifier(imported)):
                    report.setdefault("uncertainties", []).append({"id": "js_alias_uncertain", "message": f"{imported} could not be resolved safely", "path": ch.path, "evidence": imported})
                    continue
                scope_status = _dependency_scope_status(pkg, scopes["js"], ch.path)
                if scope_status == "scope_review":
                    unsupported.discard(pkg)
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{pkg} is declared outside the runtime dependency scope", "path": ch.path, "evidence": pkg})
                elif scope_status == "missing" and pkg not in patch_declared["js"]:
                    unsupported.add(pkg)
                elif pkg in patch_declared["js"]:
                    unsupported.discard(pkg)
                    report.setdefault("uncertainties", []).append({"id": "declared_dependency", "message": f"{pkg} is declared in the same patch and requires review", "path": ch.path, "evidence": pkg})

    # Re-run command claims through the command resolver so report output is
    # based on the same manifest-aware command semantics as unit-level checks.
    command_overlay: dict[str, str] = {}
    for ch in changes:
        if Path(ch.path).name.lower() in {"package.json", "Makefile", "justfile", "Justfile", "Taskfile.yml", "Taskfile.yaml", "tox.ini", "noxfile.py", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
            base = contents.get(ch.old_path or ch.path, "")
            post = _apply_patch_change_to_text(base, ch)
            if post is not None:
                command_overlay[ch.path] = post
    command_tmp = _materialize_packet_worktree(packet, command_overlay)
    try:
        command_root = Path(command_tmp.name)
        added_text = "\n".join("\n".join(ch.added_lines or []) for ch in changes)
        commands = set()
        if re.search(r"docker\s+compose\s+up", added_text, re.I):
            commands.add("docker compose up")
        commands.update(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))
        commands.update(_command_claims(r"make\s+[A-Za-z0-9_.:-]+", added_text))
        commands.update(_command_claims(r"just\s+[A-Za-z0-9_.:-]+", added_text))
        commands.update(_command_claims(r"task\s+[A-Za-z0-9_.:-]+", added_text))
        if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
            commands.add("pytest")
        report["unsupported_commands"] = []
        for command in sorted(commands):
            resolution = resolve_command(command_root, command)
            if resolution.reason_code == "unsupported_command":
                report["unsupported_commands"].append(command)
            elif resolution.reason_code in {"declared_command", "command_check_inconclusive", "command_manifest_missing", "command_manifest_uncertain"}:
                report.setdefault("uncertainties", []).append({"id": resolution.reason_code, "message": resolution.message, "evidence": command})
    finally:
        command_tmp.cleanup()
    declared = patch_declared["python"] | patch_declared["js"]
    existing_deps = existing_declared["python"] | existing_declared["js"]
    declared_only = {d for d in declared if d not in existing_deps}
    binary_paths = _binary_diff_paths_from_patch(patch_text)
    binary_blockers = []
    for rel in binary_paths:
        if rel == "unknown" or _is_high_risk_binary_path(rel):
            binary_blockers.append(rel)
    if binary_paths:
        report["binary_diffs"] = sorted(set(binary_paths))
    if binary_blockers:
        report["binary_diff_blockers"] = sorted(set(binary_blockers))
    unsupported_ecosystems = _unsupported_ecosystem_uncertainties(files, changes)
    if unsupported_ecosystems:
        seen_uncertainties = set()
        merged_uncertainties = []
        for uncertainty in report.get("uncertainties", []) + unsupported_ecosystems:
            if isinstance(uncertainty, dict):
                key = (uncertainty.get("id"), uncertainty.get("message"), uncertainty.get("evidence"), uncertainty.get("path"))
            else:
                key = (str(uncertainty),)
            if key not in seen_uncertainties:
                seen_uncertainties.add(key)
                merged_uncertainties.append(uncertainty)
        report["uncertainties"] = merged_uncertainties
    report["unsupported_dependencies"] = sorted(unsupported)
    if declared_only:
        report.setdefault("warnings", []).append("Patch declares new dependencies that require review.")
        report["declared_dependencies"] = sorted(declared_only)
    inspection_envelope = report.get("symlink_worktree_inspection", {})
    inspections = inspection_envelope.get("inspections", [])
    report["symlink_directory_collisions"] = [item for item in inspections if item.get("worktree_object_type") == "real_directory" and item.get("directory_nonempty") is True and item.get("unrepresented_content_observed")]
    report["symlink_worktree_inspection_incomplete"] = [item for item in inspections if not item.get("source_exhausted")]
    if inspection_envelope and not inspection_envelope.get("source_exhausted") and not report["symlink_worktree_inspection_incomplete"]:
        report["symlink_worktree_inspection_incomplete"].append({"proposed_path": None, "acquisition_status": "transition_limit_reached", "source_exhausted": False, "inspection_envelope": inspection_envelope})
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "binary_diff_blockers", "path_escape", "symlink_directory_collisions", "symlink_worktree_inspection_incomplete"]
    report["verdict"] = "FAIL" if any(report.get(k) for k in fail_keys) else "WARN" if (report.get("new_files") or report.get("deleted_files") or report.get("warnings") or declared_only or report.get("uncertainties") or report.get("binary_diffs")) else "PASS"
    return report


def patch_report_to_traffic(report: dict, report_path: str = ".sourcepack/reports/latest.json") -> dict:
    findings=[]
    for p in report.get("missing_modified_files", []): findings.append(normalized_finding("missing_file", "error", "file", f"{p} not found in the trusted baseline.", p, suggestion="Restore the file, create it as a new file, or refresh the baseline only after accepting the current repo state."))
    for d in report.get("unsupported_dependencies", []): findings.append(normalized_finding("unsupported_dependency", "error", "dependency", f"{d} is imported but not declared in scanned dependency files.", evidence=d, suggestion=f"Either remove {d} usage or add it intentionally to the appropriate dependency manifest."))
    for c in report.get("unsupported_commands", []): findings.append(normalized_finding("unsupported_command", "error", "command", f"{c} is not supported by project evidence.", evidence=c, suggestion="Use a detected supported command or add the project file that defines this command."))
    if report.get("malformed_diff"):
        findings.append(normalized_finding("malformed_diff", "error", "diff", "SourcePack could not safely parse the diff artifact it was asked to judge."))
    if report.get("path_escape"):
        paths = report.get("path_escape_paths") or []
        if paths:
            for p in paths:
                findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute.", p, evidence=p))
        else:
            findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute."))
    for p in report.get("protected_artifact_modifications", []): findings.append(normalized_finding("protected_artifact", "error", "artifact", f"{p} is a protected SourcePack trust artifact.", p, evidence=p))
    for p in report.get("git_path_modifications", []): findings.append(normalized_finding("git_path_modification", "error", "artifact", f"{p} modifies Git internal state and is not safe to judge as a normal repository file.", p, evidence=p))
    for p in report.get("binary_diff_blockers", []): findings.append(normalized_finding("binary_diff", "error", "diff", f"Binary change at {p} crosses a SourcePack trust or high-risk control boundary.", p, evidence=p))
    for p in report.get("binary_diffs", []):
        if p not in set(report.get("binary_diff_blockers", [])):
            findings.append(normalized_finding("binary_diff", "warn", "uncertainty", f"Binary content was detected at {p} and was not semantically evaluated.", p, evidence=p))
    for collision in report.get("symlink_directory_collisions", []):
        path = collision.get("proposed_path")
        complete = collision.get("source_exhausted") and collision.get("acquisition_status") == "complete"
        message = f"{path} currently exists as a nonempty real directory, but the proposed Git state replaces that path with a symlink. The directory contains entries absent from the selected trusted tracked-path evidence and from this proposed transition; applying it may overwrite, displace, hide, or delete data outside Git's recovery boundary."
        if not complete:
            message = f"Inspection of the real directory at {path} was incomplete or failed; SourcePack cannot establish that the proposed symlink transition is safe."
        finding = normalized_finding("symlink_replaces_nonempty_directory", "error", "filesystem", message, path, evidence=path, suggestion="Inspect and preserve the directory contents, back up untracked or ignored data, remove the collision explicitly only after review, correct unsafe or cyclic targets, and rerun SourcePack.", evidence_class="current_worktree", checked_status="checked" if complete else "unavailable", required_evidence_class="current_worktree")
        finding["symlink_transition"] = collision
        findings.append(finding)
    for incomplete in report.get("symlink_worktree_inspection_incomplete", []):
        path = incomplete.get("proposed_path")
        finding = normalized_finding("symlink_worktree_inspection_incomplete", "error", "filesystem", f"SourcePack could not completely acquire the worktree or prior-state evidence required to judge the proposed symlink transition{f' at {path}' if path else ''}; safety was not established.", path, evidence=path or "symlink transition inspection", suggestion="Restore or provide trustworthy pre-transition evidence, reduce the change to producer limits, resolve filesystem or Git acquisition failures, and rerun SourcePack.", evidence_class="current_worktree", checked_status="unavailable", required_evidence_class="current_worktree")
        finding["symlink_transition"] = incomplete
        findings.append(finding)
    for p in report.get("new_files", []): findings.append(normalized_finding("new_file", "warn", "review", f"{p} was created by the patch.", p))
    for p in report.get("deleted_files", []): findings.append(normalized_finding("deleted_file", "warn", "review", f"{p} was deleted by the patch.", p))
    for d in report.get("declared_dependencies", []): findings.append(normalized_finding("declared_dependency", "warn", "uncertainty", f"{d} was added to dependency files.", evidence=d))
    for c in report.get("declared_commands", []): findings.append(normalized_finding("declared_command", "warn", "uncertainty", f"{c} was added in the same patch.", evidence=c))
    for w in report.get("uncertainties", []):
        if isinstance(w, dict):
            fid = str(w.get("id") or "uncertainty")
            message = str(w.get("message") or "SourcePack could not fully evaluate this change.")
            findings.append(normalized_finding(fid, "warn", "uncertainty", message, w.get("path"), w.get("evidence"), w.get("suggestion")))
        else:
            fid, _, detail = str(w).partition(":")
            fid = fid.strip() or "uncertainty"
            message = detail.strip() or str(w)
            findings.append(normalized_finding(fid, "warn", "uncertainty", message))
    traffic = traffic_report(report.get("verdict", "PASS"), findings=findings, checked_categories=["file references", "Python imports", "JS/TS imports", "known project commands", "protected SourcePack artifacts", "bounded worktree symlink collisions"], report_path=report_path)
    incomplete = report.get("symlink_worktree_inspection_incomplete", [])
    if incomplete:
        traffic["authority"] = {"status": "incomplete", "complete": False, "reason": "symlink_worktree_inspection_incomplete"}
        traffic["construction_bounds"]["symlink_worktree_inspection"] = {
            "acquisition_state": "incomplete", "count_state": "lower_bound", "source_exhausted": False,
            "limit_reached": any(str(item.get("acquisition_status", "")).endswith("limit_reached") for item in incomplete),
            "paths": [item.get("proposed_path") for item in incomplete],
            "producer": report.get("symlink_worktree_inspection", {}),
        }
        traffic["replay_bundle"] = build_replay_bundle(traffic)
    return traffic


def run_git(repo: Path, args: list[str]):
    return canonical_run_git(repo, args)


def run_git_bytes(repo: Path, args: list[str]):
    return canonical_run_git_bytes(repo, args)


def run_git_bounded(repo: Path, args: list[str]):
    if getattr(run_git, "__module__", __name__) != __name__:
        return run_git(repo, args)
    return canonical_run_git_bounded(repo, args)


def git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    # Keep this facade wrapper so compatibility monkeypatches continue to
    # control acquisition while the focused module owns the implementation.
    from .git_acquisition import worktree_dirty

    return worktree_dirty(repo, run_git)



def _only_sourcepack_gitignore_change(repo: Path) -> bool:
    status = run_git(repo, ["status", "--porcelain", "--", ".gitignore"])
    others = run_git(repo, ["status", "--porcelain"])
    if status.returncode != 0 or others.returncode != 0:
        return False
    lines = [line for line in others.stdout.splitlines() if line.strip()]
    if not lines or any(not line.endswith(".gitignore") for line in lines):
        return False
    try:
        text = (repo / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return False
    tracked = run_git(repo, ["show", "HEAD:.gitignore"])
    before = tracked.stdout if tracked.returncode == 0 else ""
    added = [line.strip() for line in text.splitlines() if line.strip() and line.strip() not in {l.strip() for l in before.splitlines()}]
    return bool(added) and set(added) <= {".sourcepack", ".sourcepack/"}


def untracked_files_as_diff(repo: str | Path, *, with_authority: bool = False):
    repo = Path(repo)
    cp = canonical_run_git_bounded(repo, ["ls-files", "--others", "--exclude-standard", "-z", "--", "."], text=False)
    if cp.returncode != 0:
        reason = "git_output_limit" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "git_diff_failed"
        state = "bounded" if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "failed"
        result = ("", {"status": "incomplete", "complete": False, "reason": reason, "acquisition_state": state})
        return result if with_authority else ""
    internal_cp = canonical_run_git_bounded(
        repo,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", ".sourcepack"],
        text=False,
    )
    if internal_cp.returncode != 0:
        reason = "git_output_limit" if internal_cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "git_diff_failed"
        state = "bounded" if internal_cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT else "failed"
        result = ("", {"status": "incomplete", "complete": False, "reason": reason, "acquisition_state": state})
        return result if with_authority else ""
    raw_paths = list(dict.fromkeys(
        item for output in (cp.stdout, internal_cp.stdout)
        for item in output.split(b"\0") if item
    ))
    decoded_paths = [item.decode("utf-8", "surrogateescape") for item in raw_paths]
    generated_paths = {
        path for path in decoded_paths if operational_sourcepack_artifact_path(path)
    } | generated_untracked_baseline_artifacts(repo, decoded_paths)
    allow_path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    if ".sourcepack/policy/allow.jsonl" in decoded_paths and readable_allow_file_matches_active(repo, allow_path):
        generated_paths.add(".sourcepack/policy/allow.jsonl")
    chunks = []
    retained_bytes = 0
    for raw_rel in raw_paths:
        rel = raw_rel.decode("utf-8", "surrogateescape")
        safe_rel, unsafe = _normalize_diff_path(rel)
        if unsafe or not safe_rel:
            result = ("\n".join(chunks) + ("\n" if chunks else ""), {"status": "incomplete", "complete": False, "reason": "unsafe_git_path", "acquisition_state": "failed"})
            return result if with_authority else result[0]
        if safe_rel in generated_paths:
            continue
        path = repo / safe_rel
        try:
            stat_result = path.lstat()
        except OSError:
            continue
        is_symlink = stat.S_ISLNK(stat_result.st_mode)
        if is_symlink:
            try:
                link_target = os.readlink(path)
            except OSError:
                continue
            target_bytes = os.fsencode(link_target)
            if len(target_bytes) > 64 * 1024:
                result = ("\n".join(chunks) + ("\n" if chunks else ""), {"status": "incomplete", "complete": False, "reason": "git_output_limit", "acquisition_state": "bounded"})
                return result if with_authority else result[0]
            size = len(target_bytes)
        elif not stat.S_ISREG(stat_result.st_mode):
            continue
        else:
            size = stat_result.st_size
        if retained_bytes + size > 8 * 1024 * 1024:
            result = ("\n".join(chunks) + ("\n" if chunks else ""), {"status": "incomplete", "complete": False, "reason": "git_output_limit", "acquisition_state": "bounded"})
            return result if with_authority else result[0]
        retained_bytes += size
        if safe_rel == ".gitignore":
            try:
                ignore_lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
            except OSError:
                ignore_lines = set()
            if ignore_lines <= {".sourcepack", ".sourcepack/"}:
                continue
        old_header = quote_git_path(f"a/{safe_rel}")
        new_header = quote_git_path(f"b/{safe_rel}")
        chunks.extend([f"diff --git {old_header} {new_header}", f"new file mode {'120000' if is_symlink else '100644'}", "--- /dev/null", f"+++ {new_header}"])
        if is_symlink:
            target_lines = link_target.split("\n")
            chunks.append(f"@@ -0,0 +1,{len(target_lines)} @@")
            chunks.extend(f"+{line}" for line in target_lines)
            continue
        if is_probably_binary(path):
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        except OSError:
            continue
        lines = text.splitlines()
        chunks.append(f"@@ -0,0 +1,{len(lines)} @@")
        chunks.extend(f"+{line}" for line in lines)
    result = ("\n".join(chunks) + ("\n" if chunks else ""), {"status": "complete", "complete": True, "reason": None, "acquisition_state": "complete"})
    return result if with_authority else result[0]

def build_repo_change_report(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, ci: bool = False, base_ref: str | None = None, head_ref: str | None = None, org_policy: str | Path | None = None, org_policy_mode: str = "optional", allow_missing_baseline_init: bool = True) -> dict:
    if (base_ref is None) != (head_ref is None):
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", "--base-ref and --head-ref must be provided together.")])
    repo_arg = Path(repo_path).resolve(); cp = run_git(repo_arg, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            finding_id = "git_unavailable"
            message = "Git executable not found."
        elif cp.returncode == GIT_RETURNCODE_TIMEOUT:
            finding_id = "git_timeout"
            message = f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds."
        elif cp.returncode == GIT_RETURNCODE_OS_ERROR:
            finding_id = "git_diff_failed"
            message = cp.stderr.strip() or "Git execution failed."
        else:
            finding_id = "no_git_repo"
            message = "No git repository found. Run sourcepack prompt or sourcepack baseline for non-git use."
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding(finding_id, "error", "git", message)])
    git_root = Path(cp.stdout.strip()).resolve()
    try:
        repo_arg.relative_to(git_root)
    except ValueError:
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", "Selected repository path is outside the discovered Git top-level.")])
    # The Git top-level is validation evidence only.  The user-selected path is
    # the SourcePack analysis root even when it has no existing baseline yet.
    repo = repo_arg
    policy_result = resolve_effective_policy(repo, org_policy=org_policy, org_policy_mode=org_policy_mode)
    # Explicit patch evidence may not exist in the checked-out worktree.  The
    # judgment pipeline therefore supplies it directly to the authority owner.
    if patch_text is not None:
        policy_result = guard_effective_policy_result(repo, policy_result, patch_text=patch_text)
    added = False
    if patch_text is None:
        if base_ref is not None and head_ref is not None:
            diff_args = ["diff", "--binary", f"{base_ref}...{head_ref}"]
        else:
            diff_args = ["diff", "--staged"] if staged else ["diff"]
        if repo != git_root:
            diff_args.append("--relative")
        diff_args.extend(["--", "."])
        cp = run_git_bounded(repo, diff_args); diff_text = cp.stdout
        if cp.returncode == GIT_RETURNCODE_OUTPUT_LIMIT:
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", cp.stderr.strip() or "Git diff acquisition was incomplete.")])
            return _finalize_git_incomplete(repo, rep, policy_result, producer="git_diff", reason="git_output_limit", acquisition_state="bounded")
        if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable", "error", "git", "Git executable not found.")])
            return _finalize_early_core_failure(repo, rep, policy_result)
        if cp.returncode == GIT_RETURNCODE_TIMEOUT:
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_timeout", "error", "git", f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds.")])
            return _finalize_early_core_failure(repo, rep, policy_result)
        if cp.returncode != 0:
            message = cp.stderr.strip() or "Git diff failed."
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", message)])
            return _finalize_early_core_failure(repo, rep, policy_result)
        if base_ref is None and head_ref is None and not staged:
            extra, extra_authority = untracked_files_as_diff(repo, with_authority=True)
            if not extra_authority["complete"]:
                rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", "Untracked-file diff acquisition exceeded its producer limit.")])
                return _finalize_git_incomplete(repo, rep, policy_result, producer="git_untracked", reason=extra_authority["reason"], acquisition_state=extra_authority["acquisition_state"])
            if extra and not (added and _only_sourcepack_gitignore_change(repo)):
                diff_text = (diff_text + "\n" + extra).strip() + "\n"
    else:
        diff_text = patch_text
    policy_result = guard_effective_policy_result(repo, policy_result, patch_text=diff_text)
    baseline_status = validate_baseline(repo)
    if baseline_status["state"] == "corrupt":
        rep = traffic_report("FAIL", "trusted baseline is corrupt.", [normalized_finding("baseline_corrupt", "error", "baseline", baseline_status["message"])], ["baseline", "diff"], "Recreate the baseline only after verifying the current repo state should be trusted.")
        rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
        rep.update(baseline_report_fields(baseline_status)); return rep
    if baseline_status["state"] == "missing":
        dirty_now, dirty_state_now = git_worktree_dirty(repo)
        if ci:
            rep = traffic_report("FAIL", "trusted baseline is missing in CI.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists; CI must not establish trust.")], ["baseline", "diff"], "create the baseline locally only after deciding the current repo state should be trusted.")
            rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
            rep.update(baseline_report_fields(baseline_status)); return rep
        if diff_text.strip() or (dirty_now and not _only_sourcepack_gitignore_change(repo)):
            rep = traffic_report("FAIL", "baseline missing while changes are present.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists while changes are present.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
            rep.update(baseline_report_fields(baseline_status)); return rep
        if not allow_missing_baseline_init:
            rep = traffic_report("FAIL", "trusted baseline is missing.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists; this review path will not initialize or trust one automatically.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
            rep.update(baseline_report_fields(baseline_status)); return rep
        try:
            build_current_baseline(repo, quiet=True, force=False); baseline_status = validate_baseline(repo)
            rep_note = "Created SourcePack baseline because none existed and no diff was present."
        except BaselineLockError as exc:
            rep = traffic_report("WARN", "baseline writer is locked.", [normalized_finding("baseline_locked", "warn", "tooling", str(exc))], ["baseline", "diff"], "try again after the other baseline operation finishes.", reason_type="tooling")
            rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
            rep["repo_path"] = str(repo)
            return rep
        except Exception as exc:
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}")])
            rep = _apply_policy_finishers(repo, None, diff_text, rep, policy_result)
            rep["repo_path"] = str(repo)
            return rep
    else:
        rep_note = None
    trusted_base_files: set[str] | None = None
    if base_ref is not None:
        selected_prefix = repo.relative_to(git_root).as_posix()
        tree_pathspec = selected_prefix if selected_prefix != "." else "."
        base_tree = run_git_bounded(git_root, ["ls-tree", "-r", "--name-only", base_ref, "--", tree_pathspec])
        if base_tree.returncode == GIT_RETURNCODE_OUTPUT_LIMIT:
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", base_tree.stderr.strip() or "Git base-tree acquisition was incomplete.")])
            return _finalize_git_incomplete(repo, rep, policy_result, producer="git_base_tree", reason="git_output_limit", acquisition_state="bounded")
        if base_tree.returncode != 0:
            message = base_tree.stderr.strip() or "Git could not inspect the base revision."
            rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", message)])
            return _finalize_early_core_failure(repo, rep, policy_result)
        trusted_base_files = {
            normalized.removeprefix(selected_prefix.rstrip("/") + "/") if selected_prefix != "." else normalized
            for path in base_tree.stdout.splitlines()
            for normalized, unsafe in [_normalize_diff_path(path)]
            if normalized and not unsafe
        }
    stale_findings = []
    if baseline_status["state"] == "stale":
        stale_findings.append(normalized_finding("baseline_stale", "warn", "uncertainty", "Trusted SourcePack baseline may not match current repo state."))
    if not diff_text.strip():
        verdict = "WARN" if stale_findings else "PASS"
        rep = traffic_report(verdict, "SourcePack could not fully evaluate this change." if stale_findings else "good to continue.", [normalized_finding("no_diff", "info", "diff", "No uncommitted changes detected."), *stale_findings], ["diff", "baseline freshness"])
    else:
        packet_path = repo / baseline_status["packet_path"]
        raw = judge_patch_text(packet_path, diff_text, trusted_files=trusted_base_files, worktree_root=repo); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
        rep = _integrate_execution_findings(repo, diff_text, rep)
        rep = _apply_policy_finishers(repo, packet_path, diff_text, rep, policy_result)
        if stale_findings:
            rep = _rebuild_from_findings(rep, rep.get("findings", []) + stale_findings)
            if rep["verdict"] != "FAIL":
                rep["verdict"] = "WARN"
                rep["light"] = "YELLOW"
                rep["headline"] = "SourcePack could not fully evaluate this change."
                rep["reason_type"] = "uncertainty"
            rep["raw_patch_judgment"] = raw
    if "policy" not in rep:
        rep = _apply_policy_rules(repo, None, diff_text, rep, policy_result)
    rep.update(baseline_report_fields(baseline_status))
    if baseline_status.get("metadata_path"):
        try:
            rep["baseline"] = json.loads((repo / baseline_status["metadata_path"]).read_text(encoding="utf-8"))
        except Exception:
            pass
    rep["current_git"] = git_metadata(repo)
    if rep_note:
        rep["note"] = rep_note
    rep["repo_path"] = str(repo)
    return rep


def _rebuild_from_findings(rep: dict, findings: list[dict]) -> dict:
    verdict = "FAIL" if any(f.get("severity") == "error" for f in findings) else "WARN" if any(f.get("severity") == "warn" for f in findings) else "PASS"
    rebuilt = traffic_report(verdict, findings=findings, checked_categories=rep.get("checked_categories") or rep.get("checked") or [], report_path=rep.get("report_path", ".sourcepack/reports/latest.json"))
    for key in ("raw_patch_judgment", "policy", "policy_overrides", "policy_config", "policy_config_ignores", "policy_config_warnings", "policy_rule_findings"):
        if key in rep:
            rebuilt[key] = rep[key]
    if isinstance(rep.get("authority"), dict) and rep["authority"].get("complete") is False:
        rebuilt["authority"] = rep["authority"]
        for producer, bounds in (rep.get("construction_bounds") or {}).items():
            if producer != "findings":
                rebuilt["construction_bounds"][producer] = bounds
        rebuilt["replay_bundle"] = build_replay_bundle(rebuilt)
    return rebuilt


def _integrate_execution_findings(repo: Path, checked_text: str, rep: dict) -> dict:
    execution = execution_findings(repo, checked_text)
    if not execution:
        return rep
    return _rebuild_from_findings(rep, list(rep.get("findings", [])) + execution)


_PLACEHOLDER_SECRET_VALUES = {"example", "dummy", "fake", "test", "changeme", "placeholder", "redacted"}
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|apikey|access[_-]?key|private[_-]?key)\b"
    r"[A-Za-z0-9_.-]*['\"]?\s*[:=]\s*['\"]?([^'\"\s,#}]{8,})['\"]?"
)


def _policy_changed_line_count(changes: list[PatchFileChange]) -> int:
    count = 0
    for change in changes:
        for line in change.diff_lines or []:
            if (
                line.startswith("@@")
                or line.startswith(" ")
                or line.startswith("--- ")
                or line.startswith("+++ ")
            ):
                continue
            if line.startswith(("+", "-")):
                count += 1
    return count


def _line_has_policy_secret(line: str) -> bool:
    for match in _SECRET_ASSIGNMENT_RE.finditer(line):
        value = match.group(2).strip().lower()
        if any(placeholder in value for placeholder in _PLACEHOLDER_SECRET_VALUES):
            continue
        return True
    return False


def _rule_semantic_hash(rule_name: str, value: object) -> str:
    return "sha256:" + sha256_text(json.dumps({"rule": rule_name, "value": value}, sort_keys=True, separators=(",", ":")))


def _authority_from_sources(sources: list[str]) -> str:
    source_set = set(sources)
    if {"organization", "repository"}.issubset(source_set):
        return "mixed"
    if "organization" in source_set:
        return "organization"
    return "repository"


def _policy_authority_for_rule(result: dict, rule_name: str, *, value: object | None = None) -> str:
    rule = result.get("rules", {}).get(rule_name, {}) if isinstance(result.get("rules"), dict) else {}
    provenance = rule.get("provenance") if isinstance(rule.get("provenance"), dict) else {}
    org_value = rule.get("organization_constraint")
    repo_value = rule.get("repository_contribution")
    effective_value = rule.get("effective_value")

    if rule_name in {"protected_paths", "require_tests_for"}:
        sources: list[str] = []
        if value is not None and isinstance(provenance.get(str(value)), list):
            sources = [str(x) for x in provenance.get(str(value), [])]
        elif isinstance(provenance.get("sources"), list):
            sources = [str(x) for x in provenance.get("sources", [])]
        return _authority_from_sources(sources)

    if rule_name in {"block_dependency_additions", "block_secret_patterns"}:
        sources = []
        if org_value is True:
            sources.append("organization")
        if repo_value is True:
            sources.append("repository")
        return _authority_from_sources(sources)

    if rule_name == "max_changed_lines":
        sources = []
        if org_value == effective_value:
            sources.append("organization")
        if repo_value == effective_value:
            sources.append("repository")
        return _authority_from_sources(sources)

    if rule_name == "package_manager":
        sources = []
        if org_value == effective_value:
            sources.append("organization")
        if repo_value == effective_value:
            sources.append("repository")
        return _authority_from_sources(sources)

    sources = [str(x) for x in provenance.get("sources", [])] if isinstance(provenance.get("sources"), list) else []
    return _authority_from_sources(sources)


def _policy_authority_for_matching_values(result: dict, rule_name: str, values: list[str]) -> str:
    sources: list[str] = []
    for value in values:
        authority = _policy_authority_for_rule(result, rule_name, value=value)
        if authority == "mixed":
            sources.extend(["organization", "repository"])
        else:
            sources.append(authority)
    return _authority_from_sources(sources)


def _policy_metadata_for_finding(result: dict, rule_name: str, effective_value: object, authority: str, *, scope: str, provenance: object | None = None) -> dict:
    return {
        "effective_policy_id": result.get("effective_policy_id"),
        "rule_name": rule_name,
        "effective_rule_value": effective_value,
        "rule_fingerprint": _rule_semantic_hash(rule_name, effective_value),
        "provenance": provenance if provenance is not None else result.get("rules", {}).get(rule_name, {}).get("provenance"),
        "authority": authority,
        "scope": scope,
    }


def _annotate_policy_finding(finding: dict, result: dict, rule_name: str, effective_value: object, authority: str, *, scope: str, provenance: object | None = None, extra: dict | None = None) -> dict:
    out = dict(finding)
    out["policy"] = _policy_metadata_for_finding(result, rule_name, effective_value, authority, scope=scope, provenance=provenance)
    if extra:
        out["policy"].update(extra)
    out["policy_authority"] = authority
    out["override_eligible"] = authority == "repository"
    return out


def _policy_rules_enabled(effective: dict) -> bool:
    return any(effective.get(k) for k in ("block_dependency_additions", "protected_paths", "package_manager", "require_tests_for", "max_changed_lines", "block_secret_patterns"))


def _policy_rule_findings(repo: Path, packet_path: Path | None, diff_text: str, policy_result: dict) -> list[dict]:
    effective = policy_result.get("effective_policy", {}) if isinstance(policy_result.get("effective_policy"), dict) else {}
    if not _policy_rules_enabled(effective) or not diff_text.strip():
        return []
    changes = [change for change in parse_unified_diff(diff_text) if not change.unsafe_path]
    if not changes:
        return []

    findings: list[dict] = []
    changed_paths = sorted({change.path for change in changes if change.path})
    protected_check_paths = sorted({
        path
        for change in changes
        for path in (change.path, change.old_path if change.operation in {"rename", "copy"} else None)
        if path
    })

    for path in protected_check_paths:
        matches = [pattern for pattern in effective.get("protected_paths", []) if policy_path_matches(path, pattern)]
        if matches:
            authority = _policy_authority_for_matching_values(policy_result, "protected_paths", matches)
            findings.append(_annotate_policy_finding(normalized_finding(
                    "policy_protected_path",
                    "error",
                    "policy",
                    "Proposed change modified a path protected by repository policy.",
                    path,
                    evidence=", ".join(matches),
                    suggestion="Change the protected path only after updating policy or obtaining the required review.",
                ), policy_result, "protected_paths", matches, authority, scope=path, provenance={m: policy_result.get("rules", {}).get("protected_paths", {}).get("provenance", {}).get(m, []) for m in matches}, extra={"matching_patterns": matches}))

    if effective.get("package_manager") == "pnpm":
        conflicting = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock"}
        for change in changes:
            if change.deleted_file:
                continue
            path = change.path
            if path and PurePosixPath(path).name in conflicting:
                findings.append(_annotate_policy_finding(normalized_finding(
                    "policy_package_manager",
                    "error",
                    "policy",
                    "Proposed change added or modified a package-manager artifact that conflicts with repository policy.",
                    path,
                    evidence="pnpm",
                    suggestion="Use pnpm artifacts for this repository or update policy intentionally.",
                ), policy_result, "package_manager", "pnpm", _policy_authority_for_rule(policy_result, "package_manager"), scope=path, extra={"conflicting_lockfile": path}))

    if effective.get("max_changed_lines") is not None:
        changed_line_count = _policy_changed_line_count(changes)
        max_lines = int(effective.get("max_changed_lines"))
        added_count = sum(1 for change in changes for line in (change.diff_lines or []) if line.startswith("+") and not line.startswith("+++ "))
        deleted_count = sum(1 for change in changes for line in (change.diff_lines or []) if line.startswith("-") and not line.startswith("--- "))
        if changed_line_count > max_lines:
            findings.append(_annotate_policy_finding(normalized_finding(
                "policy_change_limit",
                "error",
                "policy",
                f"Proposed change modifies {changed_line_count} lines, exceeding policy limit {max_lines}.",
                evidence=str(changed_line_count),
                suggestion="Split the proposed change or raise the configured limit intentionally.",
            ), policy_result, "max_changed_lines", max_lines, _policy_authority_for_rule(policy_result, "max_changed_lines"), scope="repository", extra={"added_lines": added_count, "deleted_lines": deleted_count, "total_changed_lines": changed_line_count, "maximum": max_lines}))

    if effective.get("require_tests_for"):
        non_deleted_changed_paths = sorted({change.path for change in changes if change.path and not change.deleted_file})
        test_change_paths = [path for path in non_deleted_changed_paths if _is_test_path(path)]
        has_test_change = bool(test_change_paths)
        if not has_test_change:
            for path in changed_paths:
                if _is_test_path(path):
                    continue
                matches = [pattern for pattern in effective.get("require_tests_for", []) if policy_path_matches(path, pattern)]
                if matches:
                    authority = _policy_authority_for_matching_values(policy_result, "require_tests_for", matches)
                    findings.append(_annotate_policy_finding(normalized_finding(
                        "policy_test_required",
                        "error",
                        "policy",
                        "Proposed change altered a path that repository policy expects to be accompanied by a test change.",
                        path,
                        evidence=", ".join(matches),
                        suggestion="Add or update a corresponding test in the same delta, or adjust policy intentionally.",
                    ), policy_result, "require_tests_for", matches, authority, scope=path, provenance={m: policy_result.get("rules", {}).get("require_tests_for", {}).get("provenance", {}).get(m, []) for m in matches}, extra={"triggering_path": path, "observed_test_change_paths": test_change_paths, "test_detection_method": "sourcepack._is_test_path"}))

    if effective.get("block_secret_patterns") is True:
        for change in changes:
            for line in change.added_lines or []:
                if _line_has_policy_secret(line):
                    findings.append(_annotate_policy_finding(normalized_finding(
                        "policy_secret_pattern",
                        "error",
                        "policy",
                        "Proposed change added obvious credential-shaped assignment material blocked by repository policy.",
                        change.path,
                        suggestion="Remove the credential-shaped value or replace it with an obvious placeholder.",
                    ), policy_result, "block_secret_patterns", True, _policy_authority_for_rule(policy_result, "block_secret_patterns"), scope=change.path or "repository", extra={"secret_pattern_class": "credential_assignment", "match_count": 1}))
                    break

    if effective.get("block_dependency_additions") is True and packet_path is not None:
        manifest = load_manifest(packet_path)
        contents = _packet_file_contents(packet_path)
        existing = _declared_dependency_names_by_ecosystem(manifest, packet_path)
        declared, uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
        if not uncertainties:
            additions = sorted((declared["python"] | declared["js"]) - (existing["python"] | existing["js"]))
            for dependency in additions:
                findings.append(_annotate_policy_finding(normalized_finding(
                    "policy_dependency_addition",
                    "error",
                    "policy",
                    "Proposed change added an unapproved dependency to project manifest files.",
                    evidence=dependency,
                    suggestion="Remove the dependency addition or update policy/review evidence intentionally.",
                ), policy_result, "block_dependency_additions", True, _policy_authority_for_rule(policy_result, "block_dependency_additions"), scope=dependency, extra={"dependency": dependency}))

    return findings



def _canonical_policy_resolution_sequence(items: object) -> list[object]:
    if not isinstance(items, list):
        return []
    unique = {json.dumps(item, sort_keys=True, separators=(",", ":")): item for item in items}
    return [unique[key] for key in sorted(unique)]


def _canonical_policy_resolution_material(policy_result: dict) -> dict:
    return {
        "schema_version": policy_result.get("schema_version"),
        "organization_policy_mode": policy_result.get("organization_policy_mode"),
        "organization_policy_status": policy_result.get("organization_policy_status"),
        "organization_policy_id": policy_result.get("organization_policy_id"),
        "organization_policy_hash": policy_result.get("organization_policy_hash"),
        "repository_policy_hash": policy_result.get("repository_policy_hash"),
        "errors": sorted(set(str(e) for e in policy_result.get("errors", []))),
        "conflicts": _canonical_policy_resolution_sequence(policy_result.get("conflicts", [])),
        "rejected_weakening_attempts": _canonical_policy_resolution_sequence(policy_result.get("rejected_weakening_attempts", [])),
    }


def _policy_resolution_hash(policy_result: dict) -> str:
    return "sha256:" + sha256_text(json.dumps(_canonical_policy_resolution_material(policy_result), sort_keys=True, separators=(",", ":")))

def _policy_resolution_failure_finding(policy_result: dict) -> dict:
    finding = normalized_finding("policy_resolution_failed", "error", "policy", "Effective policy resolution failed; diff fails closed.", evidence=", ".join(policy_result.get("errors", [])), suggestion="Fix policy resolution errors before trusting this diff.")
    finding["policy"] = {k: policy_result.get(k) for k in ("schema_version", "effective_policy_id", "organization_policy_mode", "organization_policy_status", "organization_policy_id", "organization_policy_hash", "repository_policy_hash", "errors", "conflicts", "rejected_weakening_attempts")}
    resolution_fingerprint = _policy_resolution_hash(policy_result)
    finding["policy"]["resolution_fingerprint"] = resolution_fingerprint
    finding["policy"]["rule_name"] = "policy_resolution_failed"
    finding["policy"]["rule_fingerprint"] = resolution_fingerprint
    finding["policy"]["scope"] = "policy_resolution"
    finding["policy_authority"] = "mixed"
    finding["override_eligible"] = False
    return finding


def _policy_report_metadata(policy_result: dict, policy_finding_count: int) -> dict:
    return {
        "evaluated": True,
        "resolution_status": policy_result.get("resolution_status"),
        "effective_policy_id": policy_result.get("effective_policy_id"),
        "organization_policy_mode": policy_result.get("organization_policy_mode"),
        "organization_policy_status": policy_result.get("organization_policy_status"),
        "organization_policy_id": policy_result.get("organization_policy_id"),
        "organization_policy_hash": policy_result.get("organization_policy_hash"),
        "repository_policy_hash": policy_result.get("repository_policy_hash"),
        "effective_rules": policy_result.get("effective_policy", {}),
        "policy_finding_count": policy_finding_count,
    }


def _is_policy_rule_finding(finding: dict) -> bool:
    return finding.get("category") == "policy" and finding.get("id") in {
        "policy_resolution_failed",
        "policy_dependency_addition",
        "policy_protected_path",
        "policy_test_required",
        "policy_change_limit",
        "policy_secret_pattern",
        "policy_package_manager",
    }


def _policy_finding_key(finding: dict) -> str:
    policy = finding.get("policy") if isinstance(finding.get("policy"), dict) else {}
    payload = {
        "id": finding.get("id"),
        "path": finding.get("path"),
        "evidence": finding.get("evidence"),
        "rule_fingerprint": policy.get("rule_fingerprint"),
        "scope": policy.get("scope"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sync_policy_rule_metadata(rep: dict, policy_result: dict) -> dict:
    synced = dict(rep)
    policy_rule_findings = [finding for finding in synced.get("findings", []) if _is_policy_rule_finding(finding)]
    synced["policy"] = _policy_report_metadata(policy_result, len(policy_rule_findings))
    synced["policy_rule_findings"] = policy_rule_findings
    return synced


def _apply_policy_rules(repo: Path, packet_path: Path | None, diff_text: str, rep: dict, policy_result: dict) -> dict:
    findings = []
    if policy_result.get("resolution_status") != "PASS":
        findings.append(_policy_resolution_failure_finding(policy_result))
    elif not rep.get("policy"):
        findings = _policy_rule_findings(repo, packet_path, diff_text, policy_result)

    existing_findings = list(rep.get("findings", []))
    existing_policy_keys = {_policy_finding_key(finding) for finding in existing_findings if _is_policy_rule_finding(finding)}
    new_findings = [finding for finding in findings if _policy_finding_key(finding) not in existing_policy_keys]
    rebuilt = _rebuild_from_findings(rep, existing_findings + new_findings) if new_findings else dict(rep)
    return _sync_policy_rule_metadata(rebuilt, policy_result)





def _apply_policy_finishers(repo: Path, packet_path: Path | None, diff_text: str, rep: dict, policy_result: dict) -> dict:
    rep = _apply_policy_rules(repo, packet_path, diff_text, rep, policy_result)
    if POLICY_AUTHORITY_ERROR in policy_result.get("errors", []):
        return rep
    rep = _apply_local_policy(repo, rep)
    return _apply_policy_config(repo, rep)

def _finalize_early_core_failure(repo: Path, rep: dict, policy_result: dict) -> dict:
    finalized = _apply_policy_finishers(repo, None, "", rep, policy_result)
    finalized["repo_path"] = str(repo)
    return finalized


def _finalize_git_incomplete(repo: Path, rep: dict, policy_result: dict, *, producer: str, reason: str, acquisition_state: str) -> dict:
    finalized = _finalize_early_core_failure(repo, rep, policy_result)
    finalized["authority"] = {"status": "incomplete", "complete": False, "reason": reason}
    finalized["construction_bounds"][producer] = {
        "count_state": "lower_bound",
        "source_exhausted": False,
        "limit_reached": acquisition_state == "bounded",
        "acquisition_state": acquisition_state,
    }
    finalized["replay_bundle"] = build_replay_bundle(finalized)
    return finalized

@dataclass(frozen=True)
class PolicyLedgerResult:
    entries: tuple[dict, ...]
    status: str
    reason: str | None = None


def _parse_policy_expiry(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expires_at must be a timestamp string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("expires_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _parse_policy_ledger_data(data: bytes) -> PolicyLedgerResult:
    lines = data.splitlines()
    if len(lines) > POLICY_LEDGER_RECORD_LIMIT:
        return PolicyLedgerResult((), "incomplete", "policy ledger record limit exceeded")
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()
    now = datetime.now(timezone.utc)
    for raw_line in lines:
        if len(raw_line) > POLICY_LEDGER_LINE_LIMIT_BYTES:
            return PolicyLedgerResult((), "malformed", "policy ledger line limit exceeded")
        try:
            entry = json.loads(raw_line.decode("utf-8"))
            if not isinstance(entry, dict):
                raise ValueError("record must be an object")
            if not isinstance(entry.get("id"), str) or entry.get("scope") not in {"path", "dependency", "command"} or not isinstance(entry.get("value"), str) or not isinstance(entry.get("reason"), str):
                raise ValueError("record does not match the allow policy schema")
            expiry = _parse_policy_expiry(entry.get("expires_at"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return PolicyLedgerResult((), "malformed", str(exc))
        key = (entry["scope"], entry["value"])
        if key in seen:
            return PolicyLedgerResult((), "malformed", "duplicate or contradictory policy entry")
        seen.add(key)
        if expiry is not None and expiry < now:
            continue
        entries.append(entry)
    return PolicyLedgerResult(tuple(entries), "complete")


def _policy_entries_for_judgment(repo: Path) -> PolicyLedgerResult:
    readable_path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    if readable_path.exists():
        try:
            readable_data = _read_stable_verification_file(readable_path, POLICY_LEDGER_LIMIT_BYTES)
        except (OSError, ValueError) as exc:
            return PolicyLedgerResult((), "incomplete", str(exc))
        readable_result = _parse_policy_ledger_data(readable_data)
        if readable_result.status != "complete":
            return readable_result
    try:
        authority_entries = active_allow_records(repo)
        authority_data = b"".join(json.dumps(entry, sort_keys=True).encode("utf-8") + b"\n" for entry in authority_entries)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return PolicyLedgerResult((), "incomplete", str(exc))
    return _parse_policy_ledger_data(authority_data)


def _policy_matches(entry: dict, finding: dict) -> bool:
    scope = entry.get("scope")
    value = str(entry.get("value") or "")
    fid = finding.get("id")
    override_eligible = {
        "unsupported_dependency", "policy_dependency_addition", "unsupported_command",
        "missing_file", "new_file", "deleted_file", "binary_diff",
        "policy_protected_path", "policy_test_required", "policy_change_limit",
        "policy_secret_pattern", "policy_package_manager",
    }
    if fid not in override_eligible or str(finding.get("path") or "").startswith(".git/"):
        return False
    if fid == "policy_resolution_failed":
        return False
    if finding.get("category") == "policy" and not (finding.get("policy_authority") == "repository" and finding.get("override_eligible") is True):
        return False
    if scope == "dependency":
        return fid in {"unsupported_dependency", "policy_dependency_addition"} and finding.get("evidence") == value
    if scope == "command":
        return fid == "unsupported_command" and finding.get("evidence") == value
    if scope == "path":
        if str(finding.get("path") or "") != value:
            return False
        if str(value).startswith(".sourcepack/baseline/") and not entry.get("high_risk"):
            return False
        return fid in {
            "missing_file", "new_file", "deleted_file", "binary_diff",
            "policy_protected_path", "policy_test_required", "policy_change_limit",
            "policy_secret_pattern", "policy_package_manager",
        }
    return False




def _sync_existing_policy_rule_metadata(rep: dict) -> dict:
    synced = dict(rep)
    if "policy" not in synced:
        return synced
    policy_rule_findings = [finding for finding in synced.get("findings", []) if _is_policy_rule_finding(finding)]
    synced["policy_rule_findings"] = policy_rule_findings
    policy = dict(synced.get("policy") or {})
    policy["policy_finding_count"] = len(policy_rule_findings)
    synced["policy"] = policy
    return synced

def _apply_local_policy(repo: Path, rep: dict) -> dict:
    ledger = _policy_entries_for_judgment(repo)
    if ledger.status != "complete":
        finding = normalized_finding("policy_resolution_failed", "error", "policy", f"Local allow policy could not be acquired safely: {ledger.reason or ledger.status}.")
        failed = dict(rep)
        failed["authority"] = {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
        return _rebuild_from_findings(failed, list(rep.get("findings", [])) + [finding])
    entries = ledger.entries
    if not entries:
        return rep
    kept = []
    overrides = []
    for finding in rep.get("findings", []):
        match = next((entry for entry in entries if _policy_matches(entry, finding)), None)
        if match:
            overrides.append({"policy_id": match.get("id"), "scope": match.get("scope"), "value": match.get("value"), "reason": match.get("reason"), "suppressed_finding": finding.get("id"), "path": finding.get("path")})
        else:
            kept.append(finding)
    if not overrides:
        return rep
    rebuilt = _sync_existing_policy_rule_metadata(_rebuild_from_findings(rep, kept))
    rebuilt["policy_overrides"] = overrides
    rebuilt.setdefault("findings", []).append(normalized_finding("policy_override", "info", "policy", "A local allow policy suppressed a matching finding.", evidence=", ".join(str(o.get("value")) for o in overrides)))
    return _sync_existing_policy_rule_metadata(_rebuild_from_findings(rebuilt, rebuilt["findings"]))


def _apply_policy_config(repo: Path, rep: dict) -> dict:
    config = load_policy_config(repo)
    kept = []
    ignored = []
    for finding in rep.get("findings", []):
        match = finding_ignored_by_policy(finding, config)
        if match:
            ignored.append({"suppressed_finding": finding.get("id"), **match})
        else:
            kept.append(finding)
    if ignored:
        rebuilt = _rebuild_from_findings(rep, kept)
        rebuilt["policy_config"] = {"path": ".sourcepack/policy.json", "schema_version": config.schema_version, "report_formats": list(config.report_formats)}
        rebuilt["policy_config_ignores"] = ignored
        rebuilt.setdefault("findings", []).append(normalized_finding("policy_override", "info", "policy", "Project policy ignored matching low-risk path findings.", evidence=", ".join(i["path"] for i in ignored)))
        rep = _rebuild_from_findings(rebuilt, rebuilt["findings"] )
    else:
        rep = dict(rep)
        rep["policy_config"] = {"path": ".sourcepack/policy.json", "schema_version": config.schema_version, "report_formats": list(config.report_formats)}
    if config.warnings:
        findings = list(rep.get("findings", []))
        findings.extend(normalized_finding("policy_config_warning", "warn", "policy", warning) for warning in config.warnings)
        rep = _rebuild_from_findings(rep, findings)
        rep["policy_config_warnings"] = list(config.warnings)
    return rep


def write_auto_report(repo: Path, report: dict, details: dict) -> None:
    payload = dict(report)
    payload.update(details)
    write_user_report(repo, payload, "auto")






# CLI-independent public judgment API
@dataclass(frozen=True)
class Judgment:
    repo_path: str
    policy_mode: PolicyMode
    report: dict

    @property
    def verdict(self) -> str:
        return str(self.report.get("verdict", "WARN"))

    def exit_code(self) -> int:
        return policy_exit_code(self.verdict, self.policy_mode)


def judge_repo_change(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, policy_mode: PolicyMode | str = PolicyMode.LOCAL, base_ref: str | None = None, head_ref: str | None = None, org_policy: str | Path | None = None, org_policy_mode: str = "optional", allow_missing_baseline_init: bool = True) -> Judgment:
    """Judge repository changes without CLI parsing, stdout rendering, or cli.py imports."""
    mode = normalize_policy_mode(policy_mode)
    report = build_repo_change_report(Path(repo_path).resolve(), staged=staged, patch_text=patch_text, ci=(mode is PolicyMode.CI), base_ref=base_ref, head_ref=head_ref, org_policy=org_policy, org_policy_mode=org_policy_mode, allow_missing_baseline_init=allow_missing_baseline_init)
    if mode is PolicyMode.CI:
        report["ci"] = True
    return Judgment(str(Path(repo_path).resolve()), mode, report)
