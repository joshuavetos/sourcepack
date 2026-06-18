#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "sourcepack.real_corpus_validation.v2"
TOOL_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIRNAME = ".sourcepack_corpus_cache"
MUTATION_STATUSES = {"applied", "skipped_incompatible_repo", "mutation_failed", "repo_cleanup_failed", "baseline_failed"}
METRICS = ["false_red","missed_red","noisy_warn","crash","timeout","invalid_json","wrong_reason_code","mutation_failed","skipped_incompatible_repo","repo_cleanup_failed","baseline_failed","policy_over_suppression","trust_violation"]
FAILURE_METRICS = [m for m in METRICS if m != "skipped_incompatible_repo"]
ALTERNATE_SUPPRESSIBLE_METRICS = {"false_red", "missed_red", "noisy_warn", "wrong_reason_code"}

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    applies_to_tags: tuple[str, ...]
    required_files: tuple[str, ...]
    target_heuristic: str
    mutation: str
    expected_verdict: str
    expected_reason_codes_include: tuple[str, ...] = ()
    expected_reason_codes_exclude: tuple[str, ...] = ()
    allowed_alternate_outcomes: tuple[dict[str, Any], ...] = ()
    timeout_seconds: int = 20

@dataclass
class MutationResult:
    status: str
    applied: bool
    target_path: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

SCENARIOS: list[Scenario] = [
    Scenario("benign_readme_edit","Edit README prose only.",(),(),"readme","append_readme","PASS",timeout_seconds=10),
    Scenario("new_file","Add a simple new source file.",(),(),"python","create_python_probe","WARN",("new_file",),timeout_seconds=10),
    Scenario("undeclared_python_dependency_import","Import an undeclared Python dependency.",("python",),("python_file",),"python","append_undeclared_python_import","FAIL",("unsupported_dependency",),timeout_seconds=10),
    Scenario("declared_python_dependency_import","Import a dependency declared in a Python manifest.",("python",),("python_file","python_manifest"),"python_manifest","append_declared_python_import","PASS",allowed_alternate_outcomes=({"verdict":"WARN","justification":"Some repos expose ambiguous dependency metadata despite a declaration."},),timeout_seconds=10),
    Scenario("same_patch_python_dependency_add_plus_import","Add Python dependency declaration and import in the same patch.",("python",),("python_file","python_manifest"),"python_manifest","add_python_dep_and_import","WARN",("declared_dependency",),timeout_seconds=10),
    Scenario("undeclared_js_dependency_import","Import an undeclared Node dependency.",("node","javascript","typescript"),("js_file","package_json"),"js_ts","append_undeclared_js_import","FAIL",("unsupported_dependency",),timeout_seconds=10),
    Scenario("declared_js_dependency_import","Import an existing package.json dependency.",("node","javascript","typescript"),("js_file","package_json"),"node_manifest","append_declared_js_import","PASS",allowed_alternate_outcomes=({"verdict":"WARN","justification":"Package metadata can be present but not mapped to the selected import form."},),timeout_seconds=10),
    Scenario("same_patch_js_dependency_add_plus_import","Add package.json dependency and import in one patch.",("node","javascript","typescript"),("js_file","package_json"),"node_manifest","add_js_dep_and_import","WARN",("declared_dependency",),timeout_seconds=10),
    Scenario("missing_npm_script_reference","Reference an npm script that is not declared.",("node",),("package_json",),"node_manifest","readme_missing_npm_script","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("existing_npm_script_reference","Reference an existing npm script.",("node",),("package_json",),"node_manifest","readme_existing_npm_script","PASS",timeout_seconds=10),
    Scenario("docker_compose_missing_file","Reference Docker Compose when no compose file exists.",(),(),"docker_compose_missing","readme_missing_compose","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("docker_compose_existing_file","Reference an existing Docker Compose command.",("docker_compose",),("docker_compose",),"docker_compose","readme_existing_compose","PASS",timeout_seconds=10),
    Scenario("make_target_missing","Reference missing Make target.",(),(),"makefile_missing","readme_missing_make_target","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("make_target_existing","Reference an existing Make target.",("makefile",),("makefile",),"makefile","readme_existing_make_target","PASS",timeout_seconds=10),
    Scenario("protected_sourcepack_baseline_edit","Patch attempts to edit protected SourcePack baseline.",(),(),"patch_text","protected_baseline_patch","FAIL",("protected_artifact",),timeout_seconds=10),
    Scenario("git_config_edit","Patch attempts to edit .git/config.",(),(),"patch_text","git_config_patch","FAIL",("git_path_modification",),timeout_seconds=10),
    Scenario("unsupported_ecosystem_touch","Touch unsupported ecosystem manifest.",("unsupported_ecosystem",),(),"unsupported","touch_cargo","WARN",("unsupported_ecosystem",),timeout_seconds=10),
    Scenario("binary_diff_low_risk","Add small binary artifact.",(),(),"binary","small_binary","WARN",("binary_diff",),timeout_seconds=10),
    Scenario("binary_diff_high_risk","Add larger binary artifact.",(),(),"binary","large_binary","WARN",("binary_diff",),timeout_seconds=10),
    Scenario("malformed_diff","Judge malformed patch text.",(),(),"patch_text","malformed_patch","FAIL",("malformed_diff",),timeout_seconds=10),
    Scenario("execution_claim_without_ledger","Claim command execution without ledger evidence.",(),(),"readme","execution_claim_no_ledger","WARN",("execution_evidence_missing",),timeout_seconds=10),
    Scenario("execution_claim_with_successful_ledger","Claim command execution with ledger evidence.",(),(),"readme","execution_claim_with_ledger","PASS",(),("execution_evidence_missing",),allowed_alternate_outcomes=({"verdict":"WARN","reason_codes_include":("execution_evidence_present",),"reason_codes_exclude":("execution_evidence_missing",),"justification":"Execution evidence may be reported as advisory while still proving ledger support."},),timeout_seconds=10),
    Scenario("policy_allow_matching_dependency","Policy allows one matching dependency finding.",("python",),("python_file",),"python","policy_allow_matching_dep","PASS",(),("unsupported_dependency",),allowed_alternate_outcomes=({"verdict":"WARN","reason_codes_exclude":("unsupported_dependency",),"justification":"Policy override evidence may keep an advisory report while suppressing the dependency failure."},),timeout_seconds=10),
    Scenario("policy_allow_nonmatching_dependency","Policy must not suppress unrelated dependency finding.",("python",),("python_file",),"python","policy_allow_nonmatching_dep","FAIL",("unsupported_dependency",),timeout_seconds=10),
]
SCENARIO_BY_ID = {s.scenario_id: s for s in SCENARIOS}

def sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file(): return None
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    env=os.environ.copy()
    src=str(TOOL_ROOT/"src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)

def git_files(repo: Path) -> list[str]:
    cp=run(["git","ls-files"], repo, 15)
    return sorted(cp.stdout.splitlines()) if cp.returncode == 0 else []

def excluded(p: str, tests: bool=False) -> bool:
    parts=set(Path(p).parts)
    bad={".venv","venv","node_modules","build","dist","__pycache__",".cache","generated",".sourcepack"}
    if parts & bad: return True
    if not tests and ("tests" in parts or "test" in parts): return True
    return False

def find_python(repo: Path, create: bool=False) -> Path | None:
    files=[f for f in git_files(repo) if f.endswith(".py") and not excluded(f) and Path(f).name not in {"setup.py","conftest.py"}]
    root=[f for f in files if len(Path(f).parts)==1]
    src=[f for f in files if Path(f).parts[:1]==("src",)]
    pkg=[f for f in files if (repo/Path(f).parent/"__init__.py").exists()]
    for group in (root,src,pkg,files):
        if group: return repo/group[0]
    if create: return repo/"sourcepack_corpus_probe.py"
    return None

def find_js(repo: Path, create: bool=False) -> Path | None:
    exts={".js",".ts",".tsx",".jsx"}
    files=[f for f in git_files(repo) if Path(f).suffix in exts and not excluded(f) and not f.endswith("lock")]
    root=[f for f in files if len(Path(f).parts)==1]
    src=[f for f in files if Path(f).parts[:1]==("src",)]
    for group in (root,src,files):
        if group: return repo/group[0]
    if create: return repo/"sourcepack_corpus_probe.js"
    return None

def find_readme(repo: Path, create: bool=True) -> Path | None:
    for n in ("README.md","readme.md"):
        if (repo/n).exists(): return repo/n
    return repo/"README.md" if create else None

def find_py_manifest(repo: Path) -> Path | None:
    for n in ("requirements.txt","pyproject.toml"):
        if (repo/n).exists(): return repo/n
    req=sorted(repo.glob("requirements*.txt"))
    return req[0] if req else None

def declared_python_dependency(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if path.name.startswith("requirements"):
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#") and not cleaned.startswith("-"):
                return cleaned.split("==")[0].split(">=")[0].split("[")[0].replace("-", "_")
        return None
    if path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception:
            return None
        deps = data.get("project", {}).get("dependencies")
        if not isinstance(deps, list) or not deps:
            return None
        return str(deps[0]).split("==")[0].split(">=")[0].split("[")[0].replace("-", "_")
    return None

def find_package(repo: Path) -> Path | None: return repo/"package.json" if (repo/"package.json").exists() else None
def find_makefile(repo: Path) -> Path | None:
    for n in ("Makefile","makefile"):
        if (repo/n).exists(): return repo/n
    return None
def find_compose(repo: Path) -> Path | None:
    for n in ("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml"):
        if (repo/n).exists(): return repo/n
    return None

def mutate_file(path: Path, text: str, append: bool=True) -> MutationResult:
    before=sha256_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.exists(): path.write_text(path.read_text(encoding="utf-8", errors="ignore") + text, encoding="utf-8")
    else: path.write_text(text, encoding="utf-8")
    after=sha256_path(path)
    status="applied" if before != after else "mutation_failed"
    return MutationResult(status, status=="applied", str(path), before, after, None if status=="applied" else "sha256_unchanged")

def write_policy_allow(repo: Path, scope: str, value: str, reason: str) -> tuple[bool, dict[str, Any]]:
    cp = run([sys.executable, "-m", "sourcepack.cli", "allow", scope, value, "--reason", reason], repo, 15)
    return cp.returncode == 0, {"policy_command": f"sourcepack allow {scope} {value}", "policy_stdout": cp.stdout.strip(), "policy_stderr": cp.stderr.strip(), "policy_exit_code": cp.returncode}

def makefile_targets(path: Path) -> list[str]:
    targets=[]
    phony=set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw=line.split("#",1)[0].rstrip()
        if not raw or raw.startswith(("\t", " ")) or ":" not in raw or "=" in raw.split(":",1)[0]:
            continue
        name, rest = raw.split(":",1)
        names=[n for n in name.split() if n]
        if ".PHONY" in names:
            phony.update(rest.split()); continue
        for n in names:
            if n.startswith(".") or "%" in n or "$" in n or "/" in n:
                continue
            if n not in phony and n not in targets:
                targets.append(n)
    return [t for t in targets if t not in phony]

def add_python_manifest_dependency(path: Path, dep: str) -> MutationResult:
    before = sha256_path(path)
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if path.name.startswith("requirements"):
        if dep not in {line.strip().split("==")[0].split(">=")[0] for line in text.splitlines()}:
            path.write_text(text.rstrip("\n") + f"\n{dep}\n", encoding="utf-8")
    elif path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception as exc:
            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, f"pyproject_parse_failed:{exc}")
        deps = data.get("project", {}).get("dependencies")
        if not isinstance(deps, list):
            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "project_dependencies_missing_or_unsupported")
        if dep not in {str(d).split("==")[0].split(">=")[0] for d in deps}:
            marker = "dependencies"
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith(marker) and "[" in line:
                    if "]" in line:
                        lines[i] = line.replace("]", f", \"{dep}\"]", 1)
                    else:
                        for j in range(i+1, len(lines)):
                            if "]" in lines[j]:
                                lines.insert(j, f'  "{dep}",')
                                break
                        else:
                            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "dependencies_array_not_closed")
                    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
                    break
            else:
                return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "dependencies_line_not_found")
    else:
        return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "unsupported_python_manifest")
    after = sha256_path(path)
    return MutationResult("applied" if before != after else "mutation_failed", before != after, str(path), before, after, None if before != after else "sha256_unchanged", {"dependency_added": dep})

def skip(reason: str, details: dict[str,Any]|None=None) -> MutationResult:
    return MutationResult("skipped_incompatible_repo", False, reason=reason, details=details or {})

def apply_mutation(repo: Path, scenario: Scenario) -> MutationResult:
    sid=scenario.scenario_id
    if sid == "benign_readme_edit":
        return mutate_file(find_readme(repo, True), f"\nSourcePack corpus note for {sid}.\n")
    if sid == "execution_claim_without_ledger":
        return mutate_file(find_readme(repo, True), "\ntests passed\n")
    if sid == "execution_claim_with_successful_ledger":
        # Record ledger if available; README mutation remains the evaluated change.
        cp = run([sys.executable,"-m","sourcepack.cli","exec","--","python","--version"], repo, 20)
        mr = mutate_file(find_readme(repo, True), "\nI ran python --version\n")
        mr.details.update({"ledger_command":"python --version","ledger_exit_code":cp.returncode,"ledger_stdout":cp.stdout.strip(),"ledger_stderr":cp.stderr.strip()})
        if cp.returncode != 0:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="execution_ledger_setup_failed"
        return mr
    if sid == "new_file": return mutate_file(repo / "sourcepack_corpus_probe.py", "print('sourcepack corpus probe')\n", append=False)
    if sid.startswith("undeclared_python"):
        p=find_python(repo); return skip("python_target_missing") if not p else mutate_file(p, "\nimport fastapi\n")
    if sid == "policy_allow_matching_dependency":
        p=find_python(repo)
        if not p: return skip("python_target_missing")
        ok, details = write_policy_allow(repo, "dependency", "fastapi", "real corpus policy test")
        if not ok: return MutationResult("mutation_failed", False, reason="policy_setup_failed", details=details)
        mr = mutate_file(p, "\nimport fastapi\n")
        mr.details.update(details); mr.details["policy_allowed_dependency"] = "fastapi"
        return mr
    if sid == "policy_allow_nonmatching_dependency":
        p=find_python(repo)
        if not p: return skip("python_target_missing")
        ok, details = write_policy_allow(repo, "dependency", "fastapi", "real corpus policy test")
        if not ok: return MutationResult("mutation_failed", False, reason="policy_setup_failed", details=details)
        mr = mutate_file(p, "\nimport fastapi\nimport flask\n")
        mr.details.update(details); mr.details["policy_allowed_dependency"] = "fastapi"; mr.details["unsuppressed_dependency"] = "flask"
        return mr
    if sid == "declared_python_dependency_import":
        p=find_python(repo); m=find_py_manifest(repo)
        
        if not p or not m: return skip("python_target_or_manifest_missing")
        dep = declared_python_dependency(m)
        return skip("python_declared_dependency_missing") if not dep else mutate_file(p, f"\nimport {dep}\n")
    if sid == "same_patch_python_dependency_add_plus_import":
        p=find_python(repo); m=find_py_manifest(repo)
        if not p or not m: return skip("python_target_or_manifest_missing")
        dep_mr = add_python_manifest_dependency(m, "fastapi")
        if not dep_mr.applied: return dep_mr
        mr = mutate_file(p, "\nimport fastapi\n")
        mr.details.update({"manifest_path": str(m), "manifest_before_sha256": dep_mr.before_sha256, "manifest_after_sha256": dep_mr.after_sha256, "source_path": str(p), "source_before_sha256": mr.before_sha256, "source_after_sha256": mr.after_sha256, "dependency_added": "fastapi"})
        return mr
    if sid.startswith("undeclared_js"):
        p=find_js(repo); pkg=find_package(repo)
        return skip("js_target_or_package_json_missing") if not p or not pkg else mutate_file(p, "\nimport missingSourcepackDep from 'missing-sourcepack-dep';\n")
    if sid == "declared_js_dependency_import":
        p=find_js(repo); pkg=find_package(repo)
        if not p or not pkg: return skip("js_target_or_package_json_missing")
        data=json.loads(pkg.read_text() or "{}"); deps=data.get("dependencies") or data.get("devDependencies") or {"react":"latest"}; dep=sorted(deps)[0]
        return mutate_file(p, f"\nimport sourcepackCorpusDep from '{dep}';\n")
    if sid == "same_patch_js_dependency_add_plus_import":
        p=find_js(repo); pkg=find_package(repo)
        if not p or not pkg: return skip("js_target_or_package_json_missing")
        before=sha256_path(pkg)
        try:
            data=json.loads(pkg.read_text() or "{}")
        except Exception as exc:
            return skip("package_json_invalid", {"error": str(exc)})
        existing=set()
        existing_sections={}
        for section in ("dependencies","devDependencies","peerDependencies","optionalDependencies"):
            vals=data.get(section)
            if isinstance(vals, dict):
                names=sorted(str(k) for k in vals)
                existing_sections[section]=names
                existing.update(names)
        candidates=("sourcepack-corpus-js-dep","sourcepack-corpus-js-dep-2","sourcepack-corpus-js-dep-3")
        dep=next((c for c in candidates if c not in existing), None)
        if dep is None:
            return MutationResult("mutation_failed", False, str(pkg), before, before, "js_dependency_candidate_preexisting", {"dependency_candidates": list(candidates), "existing_dependency_sections": existing_sections})
        deps=data.setdefault("dependencies",{})
        if not isinstance(deps, dict):
            return MutationResult("mutation_failed", False, str(pkg), before, before, "package_json_dependencies_not_object")
        deps[dep]="latest"
        pkg.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        after=sha256_path(pkg)
        source_before=sha256_path(p)
        if before == after or dep not in (json.loads(pkg.read_text()).get("dependencies") or {}):
            return MutationResult("mutation_failed", False, str(pkg), before, after, "package_json_unchanged")
        mr = mutate_file(p, f"\nimport sourcepackCorpusJsDep from '{dep}';\n")
        mr.details.update({"package_json_path": str(pkg), "package_json_before_sha256": before, "package_json_after_sha256": after, "source_path": str(p), "source_before_sha256": source_before, "source_after_sha256": mr.after_sha256, "dependency_added": dep, "dependency_preexisting": False, "existing_dependency_sections": existing_sections, "import_specifier": dep})
        if not mr.applied:
            mr.status="mutation_failed"; mr.reason="source_unchanged"
        return mr
    if sid in {"missing_npm_script_reference","existing_npm_script_reference"}:
        pkg=find_package(repo)
        if not pkg: return skip("package_json_missing")
        script="missing-sourcepack-script"
        if sid == "existing_npm_script_reference":
            data=json.loads(pkg.read_text() or "{}"); scripts=data.get("scripts") or {}
            if not scripts: return skip("npm_scripts_missing")
            script=sorted(scripts)[0]
        return mutate_file(find_readme(repo, True), f"\nRun `npm run {script}`.\n")
    if sid == "docker_compose_missing_file":
        compose_names=("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml")
        deleted=[]
        for c in compose_names:
            path=repo/c
            if path.exists():
                path.unlink(); deleted.append(str(path))
        remaining=[str(repo/c) for c in compose_names if (repo/c).exists()]
        readme=find_readme(repo, True)
        before=sha256_path(readme)
        mr=mutate_file(readme, "\nRun `docker compose up`.\n")
        mr.details.update({"deleted_compose_files": deleted, "compose_files_remaining": remaining, "command_written": "docker compose up", "readme_path": str(readme), "readme_before_sha256": before, "readme_after_sha256": mr.after_sha256})
        if remaining:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="compose_files_still_present"
        elif before == mr.after_sha256:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="readme_unchanged"
        return mr
    if sid == "docker_compose_existing_file":
        c=find_compose(repo); return skip("docker_compose_missing") if not c else mutate_file(find_readme(repo, True), "\nRun `docker compose up`.\n")
    if sid == "make_target_missing":
        mf=find_makefile(repo)
        if not mf: return skip("makefile_missing")
        return mutate_file(find_readme(repo, True), "\nRun `make missing-sourcepack-target`.\n")
    if sid == "make_target_existing":
        mf=find_makefile(repo)
        if not mf: return skip("makefile_missing")
        targets=makefile_targets(mf)
        if not targets: return skip("makefile_target_missing")
        mr=mutate_file(find_readme(repo, True), f"\nRun `make {targets[0]}`.\n")
        mr.details["make_target"] = targets[0]
        return mr
    if sid == "unsupported_ecosystem_touch": return mutate_file(repo/"Cargo.toml", "[package]\nname='sourcepack-corpus'\nversion='0.1.0'\n", append=False)
    if sid in {"binary_diff_low_risk","binary_diff_high_risk"}:
        p=repo/("sourcepack_corpus_low.bin" if sid.endswith("low_risk") else "sourcepack_corpus_high.bin"); data=b"\0\1\2" if sid.endswith("low_risk") else bytes(range(256))*64
        before=sha256_path(p); p.write_bytes(data); after=sha256_path(p); return MutationResult("applied", True, str(p), before, after)
    if sid in {"protected_sourcepack_baseline_edit","git_config_edit","malformed_diff"}:
        return MutationResult("applied", True, None, None, hashlib.sha256(sid.encode()).hexdigest(), details={"programmatic_patch_text": True})
    return MutationResult("mutation_failed", False, reason="unknown_scenario")

def mutation_validation_failed(mutation_result: MutationResult, reason: str, details: dict[str, Any] | None = None) -> MutationResult:
    failure_details = dict(details or {})
    failure_details["original_mutation_result"] = asdict(mutation_result)
    return MutationResult("mutation_failed", False, mutation_result.target_path, mutation_result.before_sha256, mutation_result.after_sha256, reason, failure_details)

def _rel_or_abs(repo: Path, value: Any) -> Path | None:
    if not value:
        return None
    p = Path(str(value))
    return p if p.is_absolute() else repo / p

def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path and path.exists() else ""

def _python_manifest_has_dependency(path: Path, dep: str) -> bool:
    text = _read(path)
    if path.name.startswith("requirements"):
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            name = raw.split("#", 1)[0].strip().split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip().replace("-", "_")
            if name == dep:
                return True
        return False
    if path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception:
            return False
        deps = data.get("project", {}).get("dependencies")
        return isinstance(deps, list) and any(str(d).split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip().replace("-", "_") == dep for d in deps)
    return False

def _policy_artifact_exists(repo: Path) -> bool:
    return (repo / ".sourcepack" / "policy" / "allow.jsonl").exists()

def _ledger_artifact_exists(repo: Path) -> bool:
    return (repo / ".sourcepack" / "evidence" / "ledger.jsonl").exists()

def verify_scenario_state(repo: Path, scenario: Scenario, mr: MutationResult) -> MutationResult:
    if mr.status != "applied":
        return mr
    d = mr.details or {}
    sid = scenario.scenario_id
    if mr.before_sha256 is not None and mr.after_sha256 == mr.before_sha256:
        return mutation_validation_failed(mr, "sha256_unchanged")
    if sid == "same_patch_js_dependency_add_plus_import":
        pkg = _rel_or_abs(repo, d.get("package_json_path")); src = _rel_or_abs(repo, d.get("source_path")); dep = d.get("dependency_added")
        candidates = {"sourcepack-corpus-js-dep", "sourcepack-corpus-js-dep-2", "sourcepack-corpus-js-dep-3"}
        if not pkg or not pkg.exists(): return mutation_validation_failed(mr, "js_package_json_missing")
        if not src or not src.exists(): return mutation_validation_failed(mr, "js_source_missing")
        if not dep: return mutation_validation_failed(mr, "js_dependency_added_missing")
        preexisting = set()
        sections = d.get("existing_dependency_sections")
        if isinstance(sections, dict):
            for vals in sections.values():
                if isinstance(vals, list): preexisting.update(str(v) for v in vals)
        if dep not in candidates or dep == "react": return mutation_validation_failed(mr, "js_dependency_candidate_invalid")
        if dep in preexisting: return mutation_validation_failed(mr, "js_dependency_preexisting")
        try: data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception: data = {}
        if dep not in (data.get("dependencies") or {}): return mutation_validation_failed(mr, "js_dependency_not_added_to_dependencies")
        if d.get("dependency_preexisting") is not False: return mutation_validation_failed(mr, "js_dependency_preexisting_flag_invalid")
        if d.get("import_specifier") != dep: return mutation_validation_failed(mr, "js_import_specifier_mismatch")
        if f"'{dep}'" not in _read(src) and f'"{dep}"' not in _read(src): return mutation_validation_failed(mr, "js_source_import_missing")
        if d.get("package_json_before_sha256") == d.get("package_json_after_sha256") or sha256_path(pkg) == d.get("package_json_before_sha256"): return mutation_validation_failed(mr, "js_package_json_unchanged")
        if d.get("source_before_sha256") == d.get("source_after_sha256") or sha256_path(src) == d.get("source_before_sha256"): return mutation_validation_failed(mr, "js_source_unchanged")
    if sid == "same_patch_python_dependency_add_plus_import":
        manifest = _rel_or_abs(repo, d.get("manifest_path")); src = _rel_or_abs(repo, d.get("source_path") or mr.target_path); dep = d.get("dependency_added")
        if not manifest or not manifest.exists(): return mutation_validation_failed(mr, "python_manifest_missing")
        if not src or not src.exists(): return mutation_validation_failed(mr, "python_source_missing")
        if dep != "fastapi": return mutation_validation_failed(mr, "python_dependency_added_missing")
        if not _python_manifest_has_dependency(manifest, "fastapi"): return mutation_validation_failed(mr, "python_dependency_not_in_manifest")
        if "import fastapi" not in _read(src): return mutation_validation_failed(mr, "python_import_missing")
        if d.get("manifest_before_sha256") == d.get("manifest_after_sha256") or sha256_path(manifest) == d.get("manifest_before_sha256"): return mutation_validation_failed(mr, "python_manifest_unchanged")
        if sha256_path(src) == mr.before_sha256 or d.get("source_before_sha256") == d.get("source_after_sha256"): return mutation_validation_failed(mr, "python_source_unchanged")
    if sid == "docker_compose_missing_file":
        readme = _rel_or_abs(repo, d.get("readme_path") or mr.target_path)
        if not readme or not readme.exists(): return mutation_validation_failed(mr, "compose_readme_missing")
        if "docker compose up" not in _read(readme): return mutation_validation_failed(mr, "compose_command_missing")
        if any((repo / n).exists() for n in ("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml")): return mutation_validation_failed(mr, "compose_files_still_present")
        if "deleted_compose_files" not in d: return mutation_validation_failed(mr, "compose_deletion_provenance_missing")
        if "compose_files_remaining" not in d or d.get("compose_files_remaining") != []: return mutation_validation_failed(mr, "compose_remaining_provenance_invalid")
        if d.get("readme_before_sha256") == d.get("readme_after_sha256") or sha256_path(readme) == d.get("readme_before_sha256"): return mutation_validation_failed(mr, "compose_readme_unchanged")
    if sid == "policy_allow_matching_dependency":
        src = _rel_or_abs(repo, mr.target_path)
        if d.get("policy_exit_code") != 0: return mutation_validation_failed(mr, "policy_setup_failed")
        if d.get("policy_allowed_dependency") != "fastapi": return mutation_validation_failed(mr, "policy_allowed_dependency_missing")
        if not d.get("policy_command"): return mutation_validation_failed(mr, "policy_command_missing")
        if "import fastapi" not in _read(src): return mutation_validation_failed(mr, "policy_import_missing")
        if not _policy_artifact_exists(repo): return mutation_validation_failed(mr, "policy_artifact_missing")
    if sid == "policy_allow_nonmatching_dependency":
        src = _rel_or_abs(repo, mr.target_path)
        if d.get("policy_exit_code") != 0: return mutation_validation_failed(mr, "policy_setup_failed")
        if d.get("policy_allowed_dependency") != "fastapi": return mutation_validation_failed(mr, "policy_allowed_dependency_missing")
        if d.get("unsuppressed_dependency") != "flask": return mutation_validation_failed(mr, "policy_unsuppressed_dependency_missing")
        text = _read(src)
        if "import fastapi" not in text or "import flask" not in text: return mutation_validation_failed(mr, "policy_imports_missing")
        if not _policy_artifact_exists(repo): return mutation_validation_failed(mr, "policy_artifact_missing")
    if sid == "execution_claim_without_ledger":
        if not any(x in _read(_rel_or_abs(repo, mr.target_path)).lower() for x in ("tests passed", "pytest passed", "i ran pytest")): return mutation_validation_failed(mr, "execution_claim_missing")
    if sid == "execution_claim_with_successful_ledger":
        cmd = d.get("ledger_command"); readme_text = _read(_rel_or_abs(repo, mr.target_path)).lower()
        if d.get("ledger_exit_code") != 0: return mutation_validation_failed(mr, "execution_ledger_setup_failed")
        if not cmd: return mutation_validation_failed(mr, "execution_ledger_command_missing")
        if not _ledger_artifact_exists(repo): return mutation_validation_failed(mr, "execution_ledger_artifact_missing")
        if str(cmd).lower() not in readme_text: return mutation_validation_failed(mr, "execution_claim_missing")
    if sid in {"protected_sourcepack_baseline_edit", "git_config_edit", "malformed_diff"} and d.get("programmatic_patch_text") is not True:
        return mutation_validation_failed(mr, "programmatic_patch_text_missing")
    return mr

validate_mutation_result = verify_scenario_state

def cleanup_repo(repo: Path) -> bool:
    a=run(["git","reset","--hard","HEAD"], repo, 20)
    b=run(["git","clean","-fdx"], repo, 20)
    return a.returncode == 0 and b.returncode == 0

def create_baseline(repo: Path, timeout: int) -> bool:
    cp=run([sys.executable,"-m","sourcepack.cli","baseline",".","--force","--json","--quiet"], repo, timeout)
    return cp.returncode == 0 and ((repo/".sourcepack"/"baseline"/"active.json").exists() or (repo/".sourcepack"/"baseline"/"active").exists())

def reason_codes(report: dict[str,Any]) -> list[str]:
    vals=[]
    for key in ("findings","warnings","blockers","uncertainties"):
        for f in report.get(key,[]) or []:
            rid=f.get("id") or f.get("finding_id") or f.get("code")
            if rid: vals.append(str(rid))
    return sorted(set(vals))

def sourcepack_version() -> str:
    try:
        import sourcepack
        return getattr(sourcepack,"__version__","unknown")
    except Exception: return "unknown"

def evaluate(repo: Path, scenario: Scenario, timeout: int) -> tuple[int,str,str,bool,dict[str,Any]|None,bool]:
    if scenario.scenario_id in {"protected_sourcepack_baseline_edit","git_config_edit","malformed_diff"}:
        try:
            if str(TOOL_ROOT / "src") not in sys.path:
                sys.path.insert(0, str(TOOL_ROOT / "src"))
            from sourcepack.judgment import judge_repo_change
            patch = "@@ nope @@\n+bad\n" if scenario.scenario_id == "malformed_diff" else "diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\n--- a/.sourcepack/baseline/active.json\n+++ b/.sourcepack/baseline/active.json\n@@ -1 +1 @@\n-{}\n+{ }\n"
            if scenario.scenario_id == "git_config_edit": patch="diff --git a/.git/config b/.git/config\n--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-x\n+y\n"
            rep=judge_repo_change(repo, patch_text=patch).report
            return 0,json.dumps(rep),"",True,rep,False
        except Exception as exc:
            return 1,"",str(exc),False,None,False
    cp=run([sys.executable,"-m","sourcepack.cli","diff",".","--json"], repo, timeout)
    try:
        stripped=cp.stdout.strip(); rep=json.loads(stripped); valid=(stripped.startswith("{") and stripped.endswith("}"))
    except Exception:
        rep=None; valid=False
    return cp.returncode,cp.stdout,cp.stderr,valid,rep,False

def allowed_alternate_match(s: Scenario, actual: str|None, codes: list[str]) -> tuple[bool, str | None]:
    got=set(codes)
    for alt in s.allowed_alternate_outcomes:
        if not alt.get("verdict") or not alt.get("justification"):
            continue
        if actual != alt.get("verdict"):
            continue
        inc=set(alt.get("reason_codes_include", ()))
        exc=set(alt.get("reason_codes_exclude", ()))
        if inc - got or exc & got:
            continue
        return True, str(alt.get("justification"))
    return False, None

def classify(s: Scenario, actual: str|None, codes: list[str], invalid_json: bool, crash: bool, timeout: bool, mr: MutationResult) -> dict[str,bool]:
    d={k:False for k in METRICS}
    d["invalid_json"]=invalid_json; d["crash"]=crash; d["timeout"]=timeout
    d["mutation_failed"]=mr.status=="mutation_failed"; d["skipped_incompatible_repo"]=mr.status=="skipped_incompatible_repo"; d["repo_cleanup_failed"]=mr.status=="repo_cleanup_failed"; d["baseline_failed"]=mr.status=="baseline_failed"
    matched_alt, _ = allowed_alternate_match(s, actual, codes)
    if actual:
        candidate={k:False for k in ALTERNATE_SUPPRESSIBLE_METRICS}
        candidate["false_red"] = s.expected_verdict in {"PASS","WARN"} and actual == "FAIL"
        candidate["missed_red"] = s.expected_verdict == "FAIL" and actual in {"PASS","WARN"}
        candidate["noisy_warn"] = s.expected_verdict == "PASS" and actual == "WARN"
        inc=set(s.expected_reason_codes_include); exc=set(s.expected_reason_codes_exclude); got=set(codes)
        candidate["wrong_reason_code"] = bool((inc-got) or (exc&got))
        if not matched_alt:
            d.update(candidate)
    if s.scenario_id == "policy_allow_nonmatching_dependency" and actual != "FAIL": d["policy_over_suppression"] = True
    if s.scenario_id == "execution_claim_without_ledger" and actual == "PASS": d["trust_violation"] = True
    return d

def repo_entry_from_path(p: str) -> dict[str,Any]:
    path=Path(p).resolve(); return {"repo_id":path.name,"url":str(path),"path":str(path),"ecosystem_tags":infer_tags(path),"expected_features":[],"notes":"local repo"}

def infer_tags(path: Path) -> list[str]:
    tags=[]
    if any(path.glob("*.py")) or (path/"pyproject.toml").exists() or (path/"requirements.txt").exists(): tags.append("python")
    if (path/"package.json").exists(): tags.append("node")
    if find_compose(path): tags.append("docker_compose")
    if find_makefile(path): tags.append("makefile")
    if (path/"Cargo.toml").exists(): tags.append("unsupported_ecosystem")
    return tags

def load_repo_list(path: Path) -> list[dict[str,Any]]:
    data=json.loads(path.read_text())
    if not isinstance(data, list): raise ValueError("repo list must be a JSON array")
    for r in data:
        for k in ("repo_id","url","ecosystem_tags","expected_features","notes"):
            if k not in r: raise ValueError(f"repo list entry missing {k}")
    return data

def prepare_repo(entry: dict[str,Any], cache: Path, timeout: int) -> tuple[str|None,str|None,str|None]:
    url=entry["url"]
    p=Path(url)
    if p.exists(): return str(p.resolve()), None, None
    cache.mkdir(parents=True, exist_ok=True); dest=cache/entry["repo_id"]
    if dest.exists(): return str(dest.resolve()), None, None
    try:
        cp=run(["git","clone","--depth","1",url,str(dest)], cache.parent, timeout)
    except Exception as exc:
        return None,"network_unavailable",str(exc)
    if cp.returncode != 0:
        txt=(cp.stderr+cp.stdout).lower(); status="network_unavailable" if any(x in txt for x in ["could not resolve","failed to connect","network","unable to access"]) else "clone_failed"
        return None,status,cp.stderr.strip() or cp.stdout.strip()
    return str(dest.resolve()), None, None

def copy_work(src: Path, parent: Path, sid: str) -> Path:
    dst=Path(tempfile.mkdtemp(prefix=f"{src.name}_{sid}_", dir=parent))
    shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".sourcepack"))
    return dst

def empty_result(entry:dict[str,Any], scenario:Scenario, repo_path:str|None, mr:MutationResult, notes:list[str]) -> dict[str,Any]:
    flags={k:False for k in METRICS}
    flags["mutation_failed"] = mr.status == "mutation_failed"
    flags["skipped_incompatible_repo"] = mr.status == "skipped_incompatible_repo"
    flags["repo_cleanup_failed"] = mr.status == "repo_cleanup_failed"
    flags["baseline_failed"] = mr.status == "baseline_failed"
    return {"repo_id":entry["repo_id"],"repo_url":entry["url"],"repo_path":repo_path,"scenario_id":scenario.scenario_id,"mutation_status":mr.status,"mutation_result":asdict(mr),"expected_verdict":scenario.expected_verdict,"actual_verdict":None,"expected_reason_codes_include":list(scenario.expected_reason_codes_include),"expected_reason_codes_exclude":list(scenario.expected_reason_codes_exclude),"actual_reason_codes":[],"matched_allowed_alternate":False,"allowed_alternate_justification":None,"exit_code":None,"stdout_json_valid":False,**flags,"duration_ms":0,"report_path":None,"workdir_path":None,"notes":notes}

def run_harness(args: argparse.Namespace) -> tuple[dict[str,Any], int]:
    repos=[]
    if args.repo_list: repos.extend(load_repo_list(Path(args.repo_list)))
    for r in args.repo: repos.append(repo_entry_from_path(r))
    if args.max_repos is not None: repos=repos[:args.max_repos]
    selected=[SCENARIO_BY_ID[args.scenario]] if args.scenario else SCENARIOS
    workroot=Path(args.workdir or tempfile.mkdtemp(prefix="sourcepack_corpus_work_")).resolve(); workroot.mkdir(parents=True, exist_ok=True)
    cache=Path.cwd()/CACHE_DIRNAME
    results=[]; consecutive=0; circuit=False; cb_reason=None; last_failed=None
    for entry in repos:
        repo_path, prep_status, prep_msg = prepare_repo(entry, cache, args.timeout)
        if prep_status:
            for s in selected:
                row=empty_result(entry,s,None,skip(prep_status,{"message":prep_msg}),[prep_status]); row["skipped_incompatible_repo"]=True; results.append(row)
            continue
        src=Path(repo_path)
        for s in selected:
            start=time.time(); work=None; mr=MutationResult("mutation_failed",False,reason="not_run"); row=None
            try:
                work=copy_work(src, workroot, s.scenario_id)
                if not cleanup_repo(work): mr=MutationResult("repo_cleanup_failed",False,reason="git_reset_or_clean_failed"); row=empty_result(entry,s,repo_path,mr,["cleanup before baseline failed"])
                elif not create_baseline(work, min(args.timeout, s.timeout_seconds)):
                    mr=MutationResult("baseline_failed",False,reason="sourcepack_baseline_failed"); row=empty_result(entry,s,repo_path,mr,["baseline creation failed"])
                else:
                    mr=verify_scenario_state(work, s, apply_mutation(work,s))
                    if not mr.applied: row=empty_result(entry,s,repo_path,mr,[mr.reason or mr.status])
                    else:
                        try:
                            code,out,err,valid,report,_ = evaluate(work,s,min(args.timeout,s.timeout_seconds))
                            invalid=not valid; crash=(code not in (0,1,2) and not invalid); actual=report.get("verdict") if report else None; codes=reason_codes(report or {})
                        except subprocess.TimeoutExpired:
                            code=None; valid=False; actual=None; codes=[]; invalid=False; crash=False; flags={k:False for k in METRICS}; flags["timeout"]=True
                        else:
                            flags=classify(s,actual,codes,invalid,crash,False,mr)
                        row={"repo_id":entry["repo_id"],"repo_url":entry["url"],"repo_path":repo_path,"scenario_id":s.scenario_id,"mutation_status":mr.status,"mutation_result":asdict(mr),"expected_verdict":s.expected_verdict,"actual_verdict":actual,"expected_reason_codes_include":list(s.expected_reason_codes_include),"expected_reason_codes_exclude":list(s.expected_reason_codes_exclude),"actual_reason_codes":codes,"matched_allowed_alternate":allowed_alternate_match(s,actual,codes)[0],"allowed_alternate_justification":allowed_alternate_match(s,actual,codes)[1],"exit_code":code,"stdout_json_valid":valid,**flags,"duration_ms":int((time.time()-start)*1000),"report_path":(report or {}).get("report_path") if isinstance(report,dict) else None,"workdir_path":str(work) if args.keep_workdir else None,"notes":[]}
            except subprocess.TimeoutExpired:
                row=empty_result(entry,s,repo_path,mr,["timeout"]); row["timeout"]=True
            except Exception as exc:
                row=empty_result(entry,s,repo_path,mr,[str(exc)]); row["crash"]=True
            row["duration_ms"]=row.get("duration_ms") or int((time.time()-start)*1000)
            if work and (args.keep_workdir and any(row.get(k) for k in METRICS)):
                row["workdir_path"]=str(work)
            elif work:
                cleanup_repo(work)
                shutil.rmtree(work, ignore_errors=True)
            results.append(row)
            if row.get("crash") or row.get("invalid_json"):
                consecutive += 1; last_failed={"repo_id":entry["repo_id"],"scenario_id":s.scenario_id}; cb_reason="crash" if row.get("crash") else "invalid_json"
            else: consecutive=0
            if consecutive >= 5:
                circuit=True; break
        if circuit: break
    executed_runs=sum(1 for r in results if r["mutation_status"]=="applied" and r.get("exit_code") is not None)
    skipped_runs=len(results)-executed_runs
    executed_failed=sum(1 for r in results if r["mutation_status"]=="applied" and r.get("exit_code") is not None and any(r.get(m) for m in FAILURE_METRICS))
    executed_passed=executed_runs-executed_failed
    summary={"schema_version":SCHEMA_VERSION,"sourcepack_version":sourcepack_version(),"generated_at":datetime.now(timezone.utc).isoformat(),"repo_count":len(repos),"scenario_count":len(selected),"total_runs":len(repos)*len(selected),"executed_runs":executed_runs,"skipped_runs":skipped_runs,"executed_passed":executed_passed,"executed_failed":executed_failed,"passed":executed_passed,"failed":0,**{m:sum(1 for r in results if r.get(m)) for m in METRICS},"circuit_breaker_triggered":circuit,"circuit_breaker_reason":cb_reason,"consecutive_failure_count":consecutive,"last_failed_repo_scenario":last_failed,"results":results}
    summary["failed"]=sum(1 for r in results if any(r.get(m) for m in FAILURE_METRICS))
    exit_code=1 if circuit else 0
    for flag,metric in [(args.fail_on_missed_red,"missed_red"),(args.fail_on_crash,"crash"),(args.fail_on_invalid_json,"invalid_json"),(args.fail_on_trust_violation,"trust_violation"),(args.fail_on_policy_over_suppression,"policy_over_suppression")]:
        if flag and summary[metric] > 0: exit_code=1
    if getattr(args, "failures_only", False):
        summary["results"]=[r for r in summary["results"] if any(r.get(m) for m in FAILURE_METRICS)]
    return summary, exit_code

def failure_line(row: dict[str,Any]) -> str:
    failed=[m for m in FAILURE_METRICS if row.get(m)]
    mr=row.get("mutation_result") or {}
    return " | ".join([
        f"repo_id={row.get('repo_id')}",
        f"scenario_id={row.get('scenario_id')}",
        f"expected_verdict={row.get('expected_verdict')}",
        f"actual_verdict={row.get('actual_verdict')}",
        f"actual_reason_codes={','.join(row.get('actual_reason_codes') or [])}",
        f"failed_metrics={','.join(failed)}",
        f"mutation_status={row.get('mutation_status')}",
        f"mutation_reason={mr.get('reason')}",
        f"workdir_path={row.get('workdir_path')}",
    ])

def main(argv: list[str]|None=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-list")
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--workdir")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-repos", type=int)
    ap.add_argument("--scenario", choices=sorted(SCENARIO_BY_ID))
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--failures-only", action="store_true")
    ap.add_argument("--print-failures", action="store_true")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--fail-on-missed-red", action="store_true")
    ap.add_argument("--fail-on-crash", action="store_true")
    ap.add_argument("--fail-on-invalid-json", action="store_true")
    ap.add_argument("--fail-on-trust-violation", action="store_true")
    ap.add_argument("--fail-on-policy-over-suppression", action="store_true")
    args=ap.parse_args(argv)
    summary, code=run_harness(args)
    if args.json: print(json.dumps(summary, indent=2, sort_keys=True))
    elif args.print_failures:
        for row in summary["results"]:
            if any(row.get(m) for m in FAILURE_METRICS):
                print(failure_line(row))
    else: print(f"Real corpus validation: {summary['executed_passed']} executed passed, {summary['executed_failed']} executed failed, {summary['skipped_runs']} skipped")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
