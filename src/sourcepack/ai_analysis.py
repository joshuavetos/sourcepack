from __future__ import annotations

import re
from pathlib import Path

from . import __version__
from .ecosystems.python import PY_IMPORT_ALIASES
from .repository_evidence import (
    COMMON_DEPENDENCIES,
    FEATURE_NAMES,
    _package_json_scripts,
    _normalize_dependency_name,
    dependency_inventory,
    extract_refs,
    feature_inventory,
    load_manifest,
)

def _has_negation_before(text: str, start: int) -> bool:
    window = text[max(0, start - 48):start].lower()
    return bool(re.search(r"\b(do not|don't|avoid|not|no|without|unless|until|does not|is no|will not)\b", window))


def _ai_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    aliases = [dep_pat]
    for imported, package in PY_IMPORT_ALIASES.items():
        if package == _normalize_dependency_name(dep):
            aliases.append(re.escape(imported))
    alias_pat = "(?:" + "|".join(sorted(set(aliases), key=len, reverse=True)) + ")"
    patterns = [
        rf"\bimport\s+{alias_pat}\b",
        rf"\bfrom\s+{alias_pat}\s+import\b",
        rf"\b(?:pip install|python\s+-m\s+pip\s+install|poetry add|uv add|pdm add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_js_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    patterns = [
        rf"\bimport\s+[^\n;]*?from\s+[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]",
        rf"\brequire\s*\(\s*[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]\s*\)",
        rf"\b(?:npm install|npm i|pnpm add|yarn add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_command_instructions(text: str, command_pattern: str) -> list[str]:
    found = []
    for m in re.finditer(command_pattern, text, re.I):
        before = text[max(0, m.start() - 32):m.start()].lower()
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_prefix = text[line_start:m.start()].strip().lower()
        backticked = m.start() > 0 and m.end() < len(text) and text[m.start() - 1] == "`" and text[m.end()] == "`"
        instruction = bool(re.search(r"\b(run|then|execute|use|uses|start with)\s+$", before)) or line_prefix in {"-", "*", "1.", "2.", "3."} or backticked
        if instruction and not _has_negation_before(text, m.start()):
            found.append(re.sub(r"\s+", " ", m.group(0).strip()).lower())
    return found


def analyze_ai_answer(packet_path: str | Path, ai_text: str) -> dict:
    """Compute AI-answer judgment without rendering, persistence, or CLI state."""
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    packet_files = {rec["relative_path"] for rec in manifest.get("included_files", [])}
    refs = extract_refs(ai_text)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    files_lower = {path.lower() for path in packet_files}
    report = {"sourcepack_version": __version__, "supported_files": [], "missing_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "unsupported_capabilities": []}
    for ref in sorted(refs):
        report["supported_files" if ref in packet_files else "missing_files"].append(ref)
    for dep in COMMON_DEPENDENCIES:
        dep_norm = dep.lower()
        action = _ai_js_dependency_actions(ai_text, dep_norm) if dep_norm in {"react", "vue", "svelte", "prisma"} else _ai_dependency_actions(ai_text, dep_norm)
        if action and dep_norm not in deps and (dep_norm != "pytest" or not any(path.startswith("tests/") for path in packet_files)):
            report["unsupported_dependencies"].append(dep)
    if _ai_command_instructions(ai_text, r"docker\s+compose\s+up") and not any(Path(path).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for path in packet_files):
        report["unsupported_commands"].append("docker compose up")
    for command in sorted(set(_ai_command_instructions(ai_text, r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+"))):
        if command.startswith("npm run ") and command.removeprefix("npm run ").strip() not in scripts:
            report["unsupported_commands"].append(command)
        elif command == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append(command)
    if _ai_command_instructions(ai_text, r"(?:python\s+-m\s+pytest|pytest)") and not ({"pyproject.toml", "pytest.ini"} & files_lower or any(path.startswith("tests/") for path in packet_files) or "pytest" in deps):
        report["unsupported_commands"].append("pytest")
    lower_text = ai_text.lower()
    supported_features = feature_inventory(manifest, packet, deps)
    for feature in FEATURE_NAMES:
        if any(not _has_negation_before(lower_text, match.start()) for match in re.finditer(rf"\b{re.escape(feature)}\b", lower_text)) and feature not in supported_features:
            report["unsupported_capabilities"].append(feature)
    for key in ("unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"):
        report[key] = sorted(set(report[key]))
    report["verdict"] = "FAIL" if any(report[key] for key in ("missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities")) else "PASS"
    return report
