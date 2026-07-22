from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .analysis import AnalysisStatus
from .ecosystems.python import PY_IMPORT_ALIASES

DEPENDENCY_SCHEMA_VERSION = "sourcepack.dependency_resolver.v2"
UNSUPPORTED_ECOSYSTEM_MANIFESTS = {"Cargo.toml", "go.mod", "pom.xml", "build.gradle", "settings.gradle"}


@dataclass(frozen=True)
class DependencyResolution:
    verdict: str
    reason_code: str | None
    dependency: str
    evidence_source: str | None = None
    message: str = ""
    analysis_status: str | None = None
    evidence_class: str | None = None
    trust_status: str | None = None
    modified_by_patch: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_version": DEPENDENCY_SCHEMA_VERSION,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "dependency": self.dependency,
            "evidence_source": self.evidence_source,
            "message": self.message,
            "analysis_status": self.analysis_status,
            "evidence_class": self.evidence_class,
            "trust_status": self.trust_status,
            "modified_by_patch": self.modified_by_patch,
        }


def normalize_python_package(name: str) -> str:
    base = name.split(".")[0].replace("_", "-").lower()
    return PY_IMPORT_ALIASES.get(base, base)


def normalize_js_package(spec: str) -> str:
    if spec.startswith(".") or spec.startswith("/"):
        return spec
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]


def _python_dependency_inventory(root: str | Path) -> tuple[dict[str, str], list[str]]:
    root = Path(root)
    found: dict[str, str] = {}
    invalid: list[str] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            data = {}
            invalid.append("pyproject.toml")
        for dep in data.get("project", {}).get("dependencies", []) or []:
            found[_dep_name(dep)] = "pyproject.toml"
        for group, deps in (data.get("project", {}).get("optional-dependencies", {}) or {}).items():
            for dep in deps or []:
                found.setdefault(_dep_name(dep), f"pyproject.toml optional:{group}")
        for group, gdata in (data.get("dependency-groups", {}) or {}).items():
            for dep in (gdata if isinstance(gdata, list) else []):
                found.setdefault(_dep_name(str(dep)), f"pyproject.toml group:{group}")
        poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
        for dep in poetry:
            if dep.lower() != "python":
                found[_dep_name(dep)] = "pyproject.toml poetry"
    for req in sorted(root.glob("requirements*.txt")):
        try:
            lines = req.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            invalid.append(req.name)
            continue
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                found[_dep_name(line)] = req.name
    return found, invalid


def python_declared_dependencies(root: str | Path) -> dict[str, str]:
    found, _invalid = _python_dependency_inventory(root)
    return found


def _js_dependency_inventory(root: str | Path) -> tuple[dict[str, str], list[str]]:
    pj = Path(root) / "package.json"
    found: dict[str, str] = {}
    if not pj.exists():
        return found, []
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return found, ["package.json"]
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for dep in (data.get(section) or {}):
            found[dep] = f"package.json {section}"
    return found, []


def js_declared_dependencies(root: str | Path) -> dict[str, str]:
    found, _invalid = _js_dependency_inventory(root)
    return found


def resolve_python_import(root: str | Path, imported: str, *, added_dependencies: set[str] | None = None) -> DependencyResolution:
    root = Path(root)
    top = imported.split(".")[0]
    if top in sys.stdlib_module_names:
        return DependencyResolution(
            "PASS", None, imported, "python stdlib", "stdlib",
            AnalysisStatus.SUPPORTED.value, "analysis_state", "trusted", False,
        )
    if (
        (root / (top + ".py")).exists()
        or (root / top / "__init__.py").exists()
        or (root / "src" / top / "__init__.py").exists()
        or (root / "src" / (top + ".py")).exists()
    ):
        return DependencyResolution(
            "PASS", None, imported, "worktree", "local module",
            AnalysisStatus.SUPPORTED.value, "current_worktree", "local_observation", False,
        )
    pkg = normalize_python_package(imported)
    declared, invalid = _python_dependency_inventory(root)
    if pkg in (added_dependencies or set()):
        return DependencyResolution(
            "WARN", "declared_dependency", pkg, "patch", "dependency added in same patch",
            AnalysisStatus.UNKNOWN.value, "proposed_state", "untrusted_until_accepted", True,
        )
    if invalid:
        source = ", ".join(sorted(set(invalid)))
        return DependencyResolution(
            "FAIL", "manifest_parse_failure", pkg, source,
            "dependency evidence could not be parsed",
            AnalysisStatus.UNREVIEWABLE.value, "analysis_state", "invalid", False,
        )
    if pkg in declared:
        source = declared[pkg]
        if "optional:" in source or "group:" in source:
            return DependencyResolution(
                "WARN", "dependency_scope_review", pkg, source,
                "declared outside runtime dependency scope",
                AnalysisStatus.UNKNOWN.value, "dependency_manifest", "trusted_preexisting", False,
            )
        return DependencyResolution(
            "PASS", None, pkg, source, "declared",
            AnalysisStatus.SUPPORTED.value, "dependency_manifest", "trusted_preexisting", False,
        )
    return DependencyResolution(
        "FAIL", "unsupported_dependency", pkg, None,
        "external dependency not declared",
        AnalysisStatus.UNSUPPORTED.value, None, "missing", False,
    )


def resolve_js_import(
    root: str | Path,
    spec: str,
    *,
    added_dependencies: set[str] | None = None,
) -> DependencyResolution:
    root = Path(root)
    pkg = normalize_js_package(spec)
    if pkg.startswith(".") or pkg.startswith("/"):
        return DependencyResolution(
            "PASS", None, spec, "relative import", "local relative import",
            AnalysisStatus.SUPPORTED.value, "current_worktree", "local_observation", False,
        )
    normalized_added = {normalize_js_package(dep) for dep in (added_dependencies or set())}
    if pkg in normalized_added:
        return DependencyResolution(
            "WARN", "declared_dependency", pkg, "patch", "dependency added in same patch",
            AnalysisStatus.UNKNOWN.value, "proposed_state", "untrusted_until_accepted", True,
        )
    declared, invalid = _js_dependency_inventory(root)
    if invalid:
        return DependencyResolution(
            "FAIL", "manifest_parse_failure", pkg, "package.json",
            "dependency evidence could not be parsed",
            AnalysisStatus.UNREVIEWABLE.value, "analysis_state", "invalid", False,
        )
    if pkg in declared:
        src = declared[pkg]
        if "devDependencies" in src:
            return DependencyResolution(
                "WARN", "dependency_scope_review", pkg, src,
                "devDependency requires scope review",
                AnalysisStatus.UNKNOWN.value, "dependency_manifest", "trusted_preexisting", False,
            )
        return DependencyResolution(
            "PASS", None, pkg, src, "declared",
            AnalysisStatus.SUPPORTED.value, "dependency_manifest", "trusted_preexisting", False,
        )
    if spec.startswith(("@/", "~/")):
        return DependencyResolution(
            "WARN", "js_alias_uncertain", spec, "tsconfig.json",
            "alias requires bounded resolver",
            AnalysisStatus.UNKNOWN.value, "analysis_state", "unknown", False,
        )
    return DependencyResolution(
        "FAIL", "unsupported_dependency", pkg, None,
        "package dependency not declared",
        AnalysisStatus.UNSUPPORTED.value, None, "missing", False,
    )


def unsupported_ecosystems(root: str | Path) -> list[DependencyResolution]:
    root = Path(root)
    return [
        DependencyResolution(
            "WARN", "unsupported_ecosystem", manifest.name, manifest.name,
            "ecosystem detected but not semantically resolved",
            AnalysisStatus.UNKNOWN.value, "analysis_state", "unknown", False,
        )
        for manifest in root.iterdir()
        if manifest.name in UNSUPPORTED_ECOSYSTEM_MANIFESTS
    ]


def imports_from_python_source(text: str) -> set[str]:
    out = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
    return out


def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~;\[\s]", str(spec).strip(), 1)[0].replace("_", "-").lower()
