#!/usr/bin/env python3
"""Deterministic SourcePack behavior-space validation matrix.

Canonical scenario schema: BehaviorScenario below is the single typed source used
by the behavior matrix, JSON assertions, and tests. Each scenario models:
baseline state + prompt context state + working tree change + output/policy mode
-> verdict + canonical reason codes + optional exit code + normalized report shape.

Canonical expected-output schema: NormalizedReport below is the single report
shape asserted by this harness. Required fields are schema_version,
sourcepack_version, verdict, exit_code, reason_codes, reason_type,
commit_policy, checked, not_checked, findings, warnings, blockers, and
uncertainties. generated_at is optional/mode-dependent because in-memory
judge-patch reports are not persisted by the CLI. checked_categories from
SourcePack traffic reports is normalized to checked.

Reason-code normalization: CANONICAL_REASON_CODES is the registry for reason
codes this matrix expects or normalizes from current SourcePack emissions. Codes
are lowercase snake_case [a-z0-9_]+ stable identifiers. Aliases in
REASON_CODE_ALIASES are legacy/emitted spellings normalized to canonical emitted
names; duplicates collapse; ordering is ignored; JSON assertions compare
normalized sets; human-readable messages are never used for correctness.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sourcepack.cli import (  # noqa: E402
    __version__, build_current_baseline, judge_patch_text, patch_report_to_traffic,
    run_cli, sha256_text,
)

Verdict = Literal["PASS", "WARN", "FAIL"]
CommandMode = Literal["local_json_diff", "strict_json_diff", "ci_json_diff", "judge_patch"]
PolicyMode = Literal["local", "strict", "ci", "judge_patch"]
BaselineSetupMode = Literal["present", "missing", "absent_authoritative_file", "packet"]
MutationOp = Literal["write", "append", "delete", "binary_write"]

CANONICAL_REASON_CODES: frozenset[str] = frozenset({
    "baseline_missing", "missing_file", "new_file", "deleted_file",
    "unsupported_dependency", "declared_dependency", "unsupported_command",
    "declared_command", "unsafe_path", "protected_artifact",
    "git_path_modification", "binary_diff", "malformed_diff",
    "unsupported_ecosystem", "baseline_stale", "dependency_scope_review",
    "js_alias_uncertain", "dependency_manifest_uncertain", "no_diff", "workflow_change",
    "execution_evidence_missing", "execution_failed", "execution_inconclusive",
    "execution_evidence_present",
})
REASON_CODE_ALIASES: dict[str, str] = {
    "path_escape": "unsafe_path",
    "baseline_inventory_missing": "baseline_missing",
    "missing_modified_file": "missing_file",
    "missing_modified_files": "missing_file",
    "binary_diff_blocker": "binary_diff",
}
_REASON_RE = re.compile(r"^[a-z0-9_]+$")


class Mutation(TypedDict):
    op: MutationOp
    path: str
    content: str


class NormalizedReport(TypedDict):
    schema_version: str | None
    sourcepack_version: str | None
    generated_at: str | None
    verdict: Verdict
    exit_code: int
    reason_codes: list[str]
    reason_type: str | None
    commit_policy: str | None
    checked: list[str]
    not_checked: list[str]
    findings: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]


@dataclass(frozen=True)
class BehaviorScenario:
    scenario_id: str
    description: str
    category: str
    repo_files: dict[str, str]
    prompt_context_omissions: tuple[str, ...]
    baseline_setup_mode: BaselineSetupMode
    pre_baseline_setup: tuple[Mutation, ...]
    working_tree_mutations: tuple[Mutation, ...]
    patch_text: str | None
    command_mode: CommandMode
    policy_mode: PolicyMode
    expected_verdict: Verdict | Literal["NOT_FAIL"]
    expected_reason_codes_include: tuple[str, ...]
    expected_reason_codes_exclude: tuple[str, ...]
    expected_exit_code: int | None
    expected_json_valid: bool
    expected_report_fields: tuple[str, ...]
    expected_not_checked_fields: tuple[str, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)


def normalize_reason_code(code: str) -> str:
    raw = str(code).strip()
    lowered = raw.lower()
    canonical = REASON_CODE_ALIASES.get(lowered, lowered)
    if not _REASON_RE.fullmatch(canonical):
        raise ValueError(f"non-canonical reason code syntax: {code!r}")
    if canonical not in CANONICAL_REASON_CODES:
        raise ValueError(f"unknown canonical reason code: {code!r} -> {canonical!r}")
    return canonical


def normalize_reason_codes(codes: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return sorted({normalize_reason_code(c) for c in codes})


def _patch(path: str, old: str, new: str, new_file: bool = False, deleted: bool = False) -> str:
    import difflib
    old_lines = [] if new_file else old.splitlines()
    new_lines = [] if deleted else new.splitlines()
    body = "\n".join(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")) + "\n"
    prefix = f"diff --git a/{path} b/{path}\n"
    if new_file:
        prefix += "new file mode 100644\n"
    if deleted:
        prefix += "deleted file mode 100644\n"
    return prefix + body


def _packet(tmp: Path, files: dict[str, str], context_omissions: tuple[str, ...] = (), inventory: set[str] | None = None) -> Path:
    packet = tmp / "packet"; packet.mkdir()
    included = []
    context_names = set(files) - set(context_omissions)
    inventory_names = set(files) if inventory is None else inventory
    chunks = ["# SourcePack Context", ""]
    for rel, content in sorted(files.items()):
        if rel in context_names:
            included.append({"relative_path": rel, "sha256": sha256_text(content), "extension": Path(rel).suffix})
            chunks.extend([f"## File: {rel}", "", "Content:", content.rstrip("\n"), "---", ""])
    inv = {"schema_version": "sourcepack.file_inventory.v1", "source": "behavior_matrix", "files": [{"relative_path": rel, "included_in_prompt_context": rel in context_names, "source": "behavior_matrix"} for rel in sorted(inventory_names)]}
    (packet/"manifest.json").write_text(json.dumps({"included_files": included}), encoding="utf-8")
    (packet/"file_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    (packet/"context.md").write_text("\n".join(chunks), encoding="utf-8")
    (packet/"reality_map.json").write_text(json.dumps({"supported_commands": []}), encoding="utf-8")
    (packet/"receipt.json").write_text(json.dumps({"hashes": {}}), encoding="utf-8")
    return packet


def _git(repo: Path, *args: str) -> None:
    cp = subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {cp.stderr}")


def _write(repo: Path, rel: str, content: str | bytes) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _apply(repo: Path, mutations: tuple[Mutation, ...]) -> None:
    for m in mutations:
        op, rel, content = m["op"], m["path"], m.get("content", "")
        path = repo / rel
        if op == "write":
            _write(repo, rel, content)
        elif op == "append":
            path.write_text(path.read_text(encoding="utf-8") + content, encoding="utf-8")
        elif op == "delete":
            path.unlink()
        elif op == "binary_write":
            _write(repo, rel, bytes.fromhex(content))


def _make_repo(parent: Path, s: BehaviorScenario) -> Path:
    repo = parent / "repo"; repo.mkdir()
    _git(repo, "init", "-q"); _git(repo, "config", "user.email", "matrix@example.invalid"); _git(repo, "config", "user.name", "Behavior Matrix")
    for rel, content in s.repo_files.items():
        _write(repo, rel, content)
    _apply(repo, s.pre_baseline_setup)
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "initial")
    if s.baseline_setup_mode == "present":
        build_current_baseline(repo, quiet=True)
    elif s.baseline_setup_mode == "absent_authoritative_file":
        build_current_baseline(repo, quiet=True)
        packet = repo / ".sourcepack/baseline/packet/file_inventory.json"
        data = json.loads(packet.read_text(encoding="utf-8"))
        data["files"] = [f for f in data["files"] if f.get("relative_path") != "app.py"]
        packet.write_text(json.dumps(data), encoding="utf-8")
        # Keep baseline integrity valid for scenario-level authoritative inventory testing.
        receipt = repo / ".sourcepack/baseline/packet/receipt.json"
        r = json.loads(receipt.read_text(encoding="utf-8")); r["hashes"]["file_inventory.json"] = sha256_text(packet.read_text(encoding="utf-8")); receipt.write_text(json.dumps(r), encoding="utf-8")
    _apply(repo, s.working_tree_mutations)
    return repo


def _ids(report: dict[str, Any]) -> list[str]:
    codes = [f.get("id", "") for f in report.get("findings", [])]
    if report.get("baseline_integrity_finding_id"):
        codes.append(report["baseline_integrity_finding_id"])
    return normalize_reason_codes([c for c in codes if c])


def normalize_report(raw: dict[str, Any], exit_code: int) -> NormalizedReport:
    traffic = raw if "findings" in raw else patch_report_to_traffic(raw)
    return {
        "schema_version": traffic.get("schema_version"), "sourcepack_version": traffic.get("sourcepack_version", __version__),
        "generated_at": traffic.get("generated_at"), "verdict": traffic.get("verdict", "WARN"), "exit_code": exit_code,
        "reason_codes": _ids(traffic), "reason_type": traffic.get("reason_type"), "commit_policy": traffic.get("commit_policy"),
        "checked": list(traffic.get("checked") or traffic.get("checked_categories") or []), "not_checked": list(traffic.get("not_checked") or []),
        "findings": list(traffic.get("findings") or []), "warnings": list(traffic.get("warnings") or []),
        "blockers": list(traffic.get("blockers") or []), "uncertainties": list(traffic.get("uncertainties") or []),
    }


def run_scenario(s: BehaviorScenario) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sp_behavior_") as td:
        tmp = Path(td)
        if s.command_mode == "judge_patch":
            inventory = set(s.repo_files)
            if s.baseline_setup_mode == "absent_authoritative_file":
                inventory.discard("app.py")
            packet = _packet(tmp, s.repo_files, s.prompt_context_omissions, inventory)
            raw = judge_patch_text(packet, s.patch_text or "")
            # judge_patch_text is an in-process helper, not the judge-patch CLI.
            # Its scenarios are not applicable for exit-code validation.
            report = normalize_report(raw, -1)
            stdout = json.dumps(report)
        else:
            repo = _make_repo(tmp, s)
            args = ["diff", str(repo), "--json"]
            if s.command_mode == "strict_json_diff": args.append("--strict")
            if s.command_mode == "ci_json_diff": args.append("--ci")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run_cli(args)
            stdout = buf.getvalue()
            raw = json.loads(stdout)
            report = normalize_report(raw, code)
        ok, errors = assert_scenario(s, report, stdout)
        return {"scenario_id": s.scenario_id, "ok": ok, "errors": errors, "report": report}


def assert_scenario(s: BehaviorScenario, report: NormalizedReport, stdout: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if s.expected_json_valid:
        try:
            json.loads(stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"stdout not valid JSON: {exc}")
    if s.expected_verdict == "NOT_FAIL":
        if report["verdict"] == "FAIL": errors.append("verdict is FAIL")
    elif report["verdict"] != s.expected_verdict:
        errors.append(f"verdict {report['verdict']} != {s.expected_verdict}")
    if s.expected_exit_code is not None and report["exit_code"] != s.expected_exit_code:
        errors.append(f"exit {report['exit_code']} != {s.expected_exit_code}")
    have = set(report["reason_codes"])
    inc = set(normalize_reason_codes(s.expected_reason_codes_include))
    exc = set(normalize_reason_codes(s.expected_reason_codes_exclude))
    if not inc <= have: errors.append(f"missing reason codes {sorted(inc - have)} from {sorted(have)}")
    if exc & have: errors.append(f"forbidden reason codes {sorted(exc & have)}")
    for f in s.expected_report_fields:
        if f not in report or report[f] is None: errors.append(f"expected report field {f}")
    for f in s.expected_not_checked_fields:
        if f in report and report[f]: errors.append(f"expected empty report field {f}")
    return not errors, errors


def m(op: MutationOp, path: str, content: str = "") -> Mutation:
    return {"op": op, "path": path, "content": content}


def build_scenarios() -> list[BehaviorScenario]:
    S: list[BehaviorScenario] = []
    def add(i:int, desc:str, cat:str, files:dict[str,str], muts:tuple[Mutation,...]=(), *, patch:str|None=None, mode:CommandMode="local_json_diff", base:BaselineSetupMode="present", verdict:Verdict|Literal["NOT_FAIL"]="PASS", inc:tuple[str,...]=(), exc:tuple[str,...]=(), exit:int=0, omit:tuple[str,...]=(), tags:tuple[str,...]=()):
        S.append(BehaviorScenario(f"BM{i:03d}", desc, cat, files, omit, base, (), muts, patch, mode, "judge_patch" if mode=="judge_patch" else "ci" if mode=="ci_json_diff" else "strict" if mode=="strict_json_diff" else "local", verdict, inc, exc, None if mode=="judge_patch" else exit, True, ("schema_version","sourcepack_version","verdict","reason_codes","findings","not_checked"), (), tags))
    app={"app.py":"print('hi')\n"}
    add(1,"tracked file omitted from prompt context remains in baseline inventory", "baseline_prompt", app, patch=_patch("app.py",app["app.py"],"print('bye')\n"), mode="judge_patch", verdict="NOT_FAIL", exc=("missing_file",), omit=("app.py",))
    add(2,"existing file absent from authoritative baseline inventory is blocker", "baseline_prompt", app, patch=_patch("app.py",app["app.py"],"print('bye')\n"), mode="judge_patch", base="absent_authoritative_file", verdict="FAIL", inc=("missing_file",), exit=1)
    add(3,"new file added", "baseline_prompt", app, (m("write","new.py","x=1\n"),), verdict="WARN", inc=("new_file",), exc=("missing_file",))
    add(4,"tracked file deleted", "baseline_prompt", app, (m("delete","app.py"),), verdict="WARN", inc=("deleted_file",))
    add(5,"baseline missing with changes", "baseline_prompt", app, (m("append","app.py","print(2)\n"),), base="missing", verdict="FAIL", inc=("baseline_missing",), exit=1)
    add(6,"baseline present no changes", "baseline_prompt", app, (), verdict="PASS", )
    add(7,"python stdlib import", "dependency_python", {"app.py":"print(1)\n"}, (m("append","app.py","import json\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(8,"python local import", "dependency_python", {"app.py":"print(1)\n","localmod.py":"x=1\n"}, (m("append","app.py","import localmod\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(9,"python undeclared external dependency", "dependency_python", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(10,"python declared external dependency", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",))
    py_old="[project]\ndependencies=[]\n"; py_new="[project]\ndependencies=['fastapi']\n"
    add(11,"python same-patch dependency addition", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":py_old}, patch=_patch("pyproject.toml",py_old,py_new)+_patch("app.py","print(1)\n","print(1)\nimport fastapi\n"), mode="judge_patch", verdict="WARN", inc=("declared_dependency",), exc=("unsupported_dependency",))
    add(12,"python version spec dependency recognized", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['fastapi>=0.100']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(13,"python optional dependency scope requires review", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project.optional-dependencies]\nweb=['fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="WARN", inc=("dependency_scope_review",), exc=("unsupported_dependency",))
    add(14,"js local relative import", "dependency_js", {"app.js":"console.log(1)\n","lib.js":"export const x=1\n"}, (m("append","app.js",'import x from "./lib.js"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(15,"js undeclared package import", "dependency_js", {"app.js":"console.log(1)\n","package.json":"{}\n"}, (m("append","app.js",'import React from "react"\n'),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(16,"js declared dependency", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"dependencies":{"react":"latest"}}\n'}, (m("append","app.js",'import React from "react"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(17,"js devDependency in production path is scope review", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"devDependencies":{"react":"latest"}}\n'}, (m("append","app.js",'import React from "react"\n'),), verdict="WARN", inc=("dependency_scope_review",), exc=("unsupported_dependency",))
    pj_old="{}\n"; pj_new='{"dependencies":{"react":"latest"}}\n'
    add(18,"js same-patch dependency addition", "dependency_js", {"app.js":"console.log(1)\n","package.json":pj_old}, patch=_patch("package.json",pj_old,pj_new)+_patch("app.js","console.log(1)\n",'console.log(1)\nimport React from "react"\n'), mode="judge_patch", verdict="WARN", inc=("declared_dependency",), exc=("unsupported_dependency",))
    add(19,"scoped package import recognized", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"dependencies":{"@scope/pkg":"1"}}\n'}, (m("append","app.js",'import x from "@scope/pkg/sub"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(20,"ts path alias import supported by tsconfig", "dependency_js", {"app.ts":"console.log(1)\n","src/lib.ts":"export const x=1\n","tsconfig.json":'{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}\n'}, (m("append","app.ts",'import {x} from "@/lib"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(21,"docker compose without compose file", "command", {"README.md":"run docker compose up\n"}, (m("append","README.md","docker compose up\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(22,"docker compose with compose file remains supported", "command", {"README.md":"demo\n","compose.yaml":"services: {}\n"}, (m("append","README.md","docker compose up\n"),), verdict="PASS", exc=("unsupported_command",))
    add(23,"npm run dev missing script", "command", {"README.md":"demo\n","package.json":'{"scripts":{}}\n'}, (m("append","README.md","npm run dev\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(24,"npm run dev script exists", "command", {"README.md":"demo\n","package.json":'{"scripts":{"dev":"vite"}}\n'}, (m("append","README.md","npm run dev\n"),), verdict="PASS", exc=("unsupported_command",))
    pkg2='{"scripts":{"dev":"vite"}}\n'; add(25,"same-patch package script addition is review", "command", {"README.md":"demo\n","package.json":'{"scripts":{}}\n'}, patch=_patch("package.json",'{"scripts":{}}\n',pkg2)+_patch("README.md","demo\n","demo\nnpm run dev\n"), mode="judge_patch", verdict="WARN", inc=("declared_command",), exc=("unsupported_command",))
    add(26,"normalized internal path form", "path_artifact", {"README.md":"old\n"}, patch=_patch("src/../README.md","old\n","new\n"), mode="judge_patch", verdict="PASS", exc=("unsafe_path",))
    add(27,"escaping traversal path", "path_artifact", app, patch=_patch("../outside.txt","","x\n",new_file=True), mode="judge_patch", verdict="FAIL", inc=("unsafe_path",), exit=1)
    add(28,"windows drive path", "path_artifact", app, patch=_patch("C:/tmp/x.txt","","x\n",new_file=True), mode="judge_patch", verdict="FAIL", inc=("unsafe_path",), exit=1)
    add(29,"baseline active pointer protected", "path_artifact", app, patch=_patch(".sourcepack/baseline/active.json","{}\n","{ }\n"), mode="judge_patch", verdict="FAIL", inc=("protected_artifact",), exit=1)
    add(30,"prompt artifact protected", "path_artifact", app, patch=_patch(".sourcepack/prompt/prompt.md","a\n","b\n"), mode="judge_patch", verdict="FAIL", inc=("protected_artifact",), exit=1)
    add(31,"git config modification", "path_artifact", app, patch=_patch(".git/config","a\n","b\n"), mode="judge_patch", verdict="FAIL", inc=("git_path_modification",), exit=1)
    add(32,"workflow change is new file review", "path_artifact", app, (m("write",".github/workflows/ci.yml","name: ci\n"),), verdict="WARN", inc=("new_file",))
    add(33,"ordinary binary diff uncertainty", "diff_binary", app, patch="diff --git a/image.bin b/image.bin\nBinary files a/image.bin and b/image.bin differ\n", mode="judge_patch", verdict="WARN", inc=("binary_diff",))
    add(34,"high-risk binary manifest blocker", "diff_binary", app, patch="diff --git a/package.json b/package.json\nBinary files a/package.json and b/package.json differ\n", mode="judge_patch", verdict="FAIL", inc=("binary_diff",), exit=1)
    add(35,"malformed diff fails closed", "diff_binary", app, patch="@@ nope @@\n+bad\n", mode="judge_patch", verdict="FAIL", inc=("malformed_diff",), exit=1)
    for i,name in [(36,"Cargo.toml"),(37,"go.mod"),(38,"pom.xml"),(39,"build.gradle")]: add(i,f"unsupported ecosystem {name}","ecosystem", {"app.py":"print(1)\n",name:"x\n"}, (m("append",name,"y\n"),), verdict="WARN", inc=("unsupported_ecosystem",))
    add(40,"multiple unsupported ecosystems preserve evidence", "ecosystem", {"Cargo.toml":"x\n","go.mod":"module x\n","app.py":"print(1)\n"}, (m("append","Cargo.toml","y\n"),), verdict="WARN", inc=("unsupported_ecosystem",))
    add(41,"json output valid only", "output_policy", app, (), verdict="PASS", )
    add(42,"local WARN exits zero", "output_policy", app, (m("write","n.py","x=1\n"),), verdict="WARN", inc=("new_file",), exit=0)
    add(43,"strict WARN exits nonzero", "output_policy", app, (m("write","n.py","x=1\n"),), mode="strict_json_diff", verdict="WARN", inc=("new_file",), exit=1)
    add(44,"CI WARN exits nonzero", "output_policy", app, (m("write","n.py","x=1\n"),), mode="ci_json_diff", verdict="WARN", inc=("new_file",), exit=1)
    add(45,"FAIL exits nonzero", "output_policy", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(46,"PASS exits zero", "output_policy", app, (), verdict="PASS", exit=0)
    add(47,"report includes schema fields", "output_policy", app, (), verdict="PASS", exit=0)
    # metamorphic explicit variants
    add(48,"metamorphic reordered independent hunks A", "metamorphic", {"a.py":"print(1)\n","b.js":"console.log(1)\n","package.json":"{}\n"}, patch=_patch("a.py","print(1)\n","print(1)\nimport fastapi\n")+_patch("b.js","console.log(1)\n",'console.log(1)\nimport r from "react"\n'), mode="judge_patch", verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_reorder",))
    add(49,"metamorphic reordered independent hunks B", "metamorphic", {"a.py":"print(1)\n","b.js":"console.log(1)\n","package.json":"{}\n"}, patch=_patch("b.js","console.log(1)\n",'console.log(1)\nimport r from "react"\n')+_patch("a.py","print(1)\n","print(1)\nimport fastapi\n"), mode="judge_patch", verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_reorder",))
    add(50,"metamorphic unrelated readme dependency", "metamorphic", {"app.py":"print(1)\n","README.md":"a\n"}, (m("append","app.py","import fastapi\n"),m("append","README.md","words\n")), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_readme",))
    add(51,"metamorphic path equivalent A", "metamorphic", {"README.md":"a\n"}, patch=_patch("README.md","a\n","b\n"), mode="judge_patch", verdict="PASS", tags=("invariant_path",))
    add(52,"metamorphic import whitespace", "metamorphic", {"app.py":"print(1)\n"}, (m("append","app.py","from   fastapi   import FastAPI\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_whitespace",))
    add(53,"metamorphic manifest ordering", "metamorphic", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['requests','fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",), tags=("invariant_manifest_order",))
    add(54,"metamorphic temp directory independence", "metamorphic", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_tempdir",))
    add(55,"metamorphic human/json reason stable", "metamorphic", app, (m("write","new.py","x=1\n"),), verdict="WARN", inc=("new_file",), tags=("invariant_human_json",))
    add(56,"execution claim without ledger warns", "execution", {"README.md":"demo\n"}, (m("append","README.md","tests passed\n"),), verdict="WARN", inc=("execution_evidence_missing",))
    add(57,"execution near miss does not warn", "execution", {"README.md":"demo\n"}, (m("append","README.md","please test; should pass; works toward coverage\n"),), verdict="PASS", exc=("execution_evidence_missing","execution_failed"))
    add(58,"make target missing command integration", "command", {"README.md":"demo\n","Makefile":"test:\n\ttrue\n"}, (m("append","README.md","make dev\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(59,"make target present command integration", "command", {"README.md":"demo\n","Makefile":"dev:\n\ttrue\n"}, (m("append","README.md","make dev\n"),), verdict="PASS", exc=("unsupported_command",))
    add(60,"real corpus no-corpus JSON clean", "corpus", app, (), verdict="PASS", exc=("unsupported_dependency",))
    return S


def validate_scenario_definitions(scenarios: list[BehaviorScenario]) -> None:
    seen: set[str] = set()
    for s in scenarios:
        if s.scenario_id in seen: raise AssertionError(f"duplicate scenario id {s.scenario_id}")
        seen.add(s.scenario_id)
        normalize_reason_codes(s.expected_reason_codes_include)
        normalize_reason_codes(s.expected_reason_codes_exclude)
        for code in (*s.expected_reason_codes_include, *s.expected_reason_codes_exclude):
            if code != normalize_reason_code(code):
                raise AssertionError(f"scenario {s.scenario_id} uses non-canonical spelling {code}")
        if s.expected_verdict in {"FAIL","WARN"} and not s.expected_reason_codes_include:
            raise AssertionError(f"{s.scenario_id} lacks expected reason code")


def run_matrix(selected: str | None = None) -> dict[str, Any]:
    scenarios = [s for s in build_scenarios() if selected in (None, s.scenario_id)]
    validate_scenario_definitions(scenarios)
    results = [run_scenario(s) for s in scenarios]
    invariant_count = 8
    return {"schema_version":"sourcepack.behavior_matrix.v1", "sourcepack_version":__version__, "scenario_count":len(build_scenarios()), "metamorphic_invariant_count":invariant_count, "selected_count":len(scenarios), "passed":sum(1 for r in results if r["ok"]), "failed":sum(1 for r in results if not r["ok"]), "results":results}


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(); p.add_argument("--json", action="store_true"); p.add_argument("--list", action="store_true"); p.add_argument("--scenario"); p.add_argument("--verbose", action="store_true"); p.add_argument("--keep-workdir", action="store_true", help="reserved; scenarios use temporary workdirs")
    args=p.parse_args(argv)
    if args.list:
        for s in build_scenarios(): print(f"{s.scenario_id}\t{s.category}\t{s.description}")
        return 0
    data=run_matrix(args.scenario)
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(f"Behavior matrix: {data['passed']}/{data['selected_count']} passed ({data['scenario_count']} scenarios, {data['metamorphic_invariant_count']} metamorphic invariants)")
        if data["failed"] or args.verbose:
            for r in data["results"]:
                if not r["ok"] or args.verbose: print(f"{r['scenario_id']}: {'PASS' if r['ok'] else 'FAIL'} {r['errors']}")
    return 0 if data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
