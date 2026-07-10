from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tomllib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Final, Iterable
from xml.sax.saxutils import escape as xml_escape
from .git import GIT_RETURNCODE_NOT_FOUND, GIT_RETURNCODE_OS_ERROR, GIT_RETURNCODE_TIMEOUT, run_git as canonical_run_git
from .diff_parser import PatchFileChange, normalize_diff_path as _normalize_diff_path, parse_unified_diff
from .baseline import BaselineLockError, acquire_baseline_lock, baseline_corrupt_result, baseline_report_fields, build_current_baseline, protected_baseline_path, release_baseline_lock, resolve_active_baseline, validate_baseline
from .ecosystems.python import PY_IMPORT_ALIASES
from .packet import PacketWriter, SourceScanner
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.json import normalized_finding, traffic_report, write_user_report
from .policy import PolicyMode, normalize_policy_mode, exit_code as policy_exit_code, load_policy_config, finding_ignored_by_policy, policy_path_matches
from .execution_ledger import execution_findings
from .commands import resolve_command
from .dependencies import resolve_js_import, resolve_python_import

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"

DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "target", "coverage", ".pytest_cache", ".sourcepack"
}
DEFAULT_IGNORED_PATTERNS = {
    ".env", ".env.*", "*.pem", "*.key", "*.sqlite", "*.db", "*.png", "*.jpg",
    "*.jpeg", "*.gif", "*.webp", "*.pdf", "*.zip", "*.tar", "*.gz", "*.exe",
    "*.dll", "*.so", "*.dylib", "*.bin", "*.pyc"
}
DEFAULT_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".html", ".css", ".csv", ".toml", ".ini", ".sql", ".sh", ".bat", ".ps1", ".rs",
    ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".xml"
}
SECRET_PATTERNS = [
    ("openai_key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9]{24,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}")),
]
COMMON_DEPENDENCIES = ["fastapi", "flask", "django", "react", "vue", "svelte", "pytest", "typer", "click", "sqlalchemy", "prisma", "pydantic", "pyyaml", "pillow", "beautifulsoup4", "opencv-python", "scikit-learn", "python-dotenv", "pyjwt", "python-dateutil", "boto3", "requests"]
FEATURE_NAMES = ("pdf", "ocr", "web server", "react", "docker", "authentication", "database")
GIT_TIMEOUT_SECONDS: Final[int] = 10
NATURAL_LANGUAGE_COMMAND_TARGETS: Final[frozenset[str]] = frozenset({"a", "an", "the", "this", "that", "these", "those"})


def _command_claims(pattern: str, text: str) -> set[str]:
    commands = set()
    for command in re.findall(pattern, text):
        parts = command.split()
        if len(parts) >= 2 and parts[1].lower() in NATURAL_LANGUAGE_COMMAND_TARGETS:
            continue
        commands.add(command)
    return commands


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return True
    if b"\x00" in data:
        return True
    if not data:
        return False
    nonprintable = sum(1 for b in data if b < 9 or (13 < b < 32))
    return (nonprintable / max(len(data), 1)) > 0.30


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def redact_secrets(text: str):
    redactions = []
    redacted = text
    for label, pattern in SECRET_PATTERNS:
        def repl(match):
            redactions.append({"pattern": label, "span_start": match.start(), "span_end": match.end()})
            return f"[REDACTED:{label}]"
        redacted = pattern.sub(repl, redacted)
    return redacted, redactions


@dataclass
class IncludedFile:
    relative_path: str
    absolute_path: str
    size_bytes: int
    sha256: str
    source_sha256: str
    packet_sha256: str
    estimated_tokens: int
    extension: str
    content: str


@dataclass
class IgnoredFile:
    relative_path: str
    reason: str



def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    source = "scanner_included_files"
    cp = run_git(root, ["ls-files", "-z"])
    if cp.returncode == 0:
        raw_paths = [p for p in cp.stdout.split("\0") if p]
        source = "git_ls_files" if raw_paths else "scanner_included_files"
        if not raw_paths:
            raw_paths = sorted(included)
    else:
        raw_paths = sorted(included)
    for raw in raw_paths:
        safe_rel, unsafe = _normalize_diff_path(raw)
        if unsafe or not safe_rel:
            files.append({
                "relative_path": raw.replace("\\", "/"),
                "included_in_prompt_context": False,
                "source": source,
                "file_type": "unsafe_path",
            })
            continue
        rel = safe_rel
        path = root / rel
        rec = {"relative_path": rel, "included_in_prompt_context": rel in included, "source": source}
        try:
            if path.exists() and path.is_file():
                rec["sha256"] = sha256_file(path)
                rec["file_type"] = "binary" if is_probably_binary(path) else "text"
            else:
                rec["file_type"] = "missing"
        except OSError:
            rec["file_type"] = "unreadable"
        files.append(rec)
    return {"schema_version": "sourcepack.file_inventory.v1", "generated_at": utc_now(), "source": source, "files": files}


def _included_paths(manifest: dict) -> set[str]:
    return {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}


def _package_json_scripts(packet: Path) -> dict[str, str]:
    contents = _packet_file_contents(packet)
    for rel, content in contents.items():
        if Path(rel).name.lower() == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                return {}
            scripts = package.get("scripts")
            return scripts if isinstance(scripts, dict) else {}
    return {}


def _is_poetry_project(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).name.lower() == "pyproject.toml" and re.search(r"(?m)^\s*\[tool\.poetry\]\s*$", content):
            return True
    return False


def _uses_unittest(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).suffix.lower() == ".py" and re.search(r"(?m)^\s*(import\s+unittest|from\s+unittest\s+import\s+)", content):
            return True
    return False


def generate_reality_map(manifest: dict, packet: Path) -> dict:
    files = _included_paths(manifest)
    lower_files = {f.lower() for f in files}
    deps = dependency_inventory(manifest, packet)
    features = feature_inventory(manifest, packet, deps)
    scripts = _package_json_scripts(packet)
    project_types = []
    package_managers = []
    frameworks = []
    supported_commands = []
    test_commands = []
    build_commands = []
    run_commands = []
    if "pyproject.toml" in lower_files:
        project_types.append("python")
    if any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower_files):
        project_types.append("python")
        package_managers.append("pip")
    if _is_poetry_project(packet):
        package_managers.append("poetry")
    if "package.json" in lower_files:
        project_types.append("node")
        package_managers.append("npm")
        for name in sorted(scripts):
            cmd = "npm test" if name == "test" else f"npm run {name}"
            supported_commands.append(cmd)
            if name == "test": test_commands.append(cmd)
            elif name in {"build", "compile"}: build_commands.append(cmd)
            elif name in {"start", "dev", "serve"}: run_commands.append(cmd)
    if any(Path(f).name.lower() == "dockerfile" for f in files):
        supported_commands.append("docker build")
        build_commands.append("docker build")
    if any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in files):
        supported_commands.append("docker compose up")
        run_commands.append("docker compose up")
    if "pytest" in deps or any(f == "tests" or f.startswith("tests/") for f in lower_files):
        supported_commands.append("pytest")
        test_commands.append("pytest")
    if _uses_unittest(packet):
        supported_commands.append("python -m unittest")
        test_commands.append("python -m unittest")
    framework_map = {"fastapi": "FastAPI", "flask": "Flask", "django": "Django", "react": "React"}
    for dep, label in framework_map.items():
        if dep in deps or (dep == "react" and "react" in features):
            frameworks.append(label)
    ignored = manifest.get("ignored_files", [])
    ignored_reasons = {}
    for rec in ignored:
        reason = rec.get("reason", "unknown")
        ignored_reasons[reason] = ignored_reasons.get(reason, 0) + 1
    included_count = len(manifest.get("included_files", []))
    safe_claims = [
        f"This packet includes {included_count} source files.",
        f"SourcePack scanned input path: {manifest.get('input_path', '')}.",
    ]
    for name in ["pyproject.toml", "package.json", "Dockerfile"]:
        present = name.lower() in {Path(f).name.lower() for f in files}
        safe_claims.append(f"The project {'contains' if present else 'does not include'} {name}.")
    if "react" not in deps and "react" not in features:
        safe_claims.append("No React dependency was detected.")
    if "pdf" not in features:
        safe_claims.append("No PDF parsing capability was detected.")
    if ignored:
        safe_claims.append("The packet includes ignored file records for safety or relevance reasons.")
    claim_boundaries = [
        "SourcePack did not execute the application.",
        "SourcePack did not prove semantic correctness.",
        "SourcePack did not verify external services.",
        "SourcePack did not prove security.",
        "SourcePack did not prove production readiness.",
        "Absence of evidence means unknown, not impossible.",
        "Unsupported claims should be treated as ungrounded.",
    ]
    return {
        "reality_map_schema_version": "1.0",
        "tool_version": __version__,
        "generated_at": utc_now(),
        "input_path": manifest.get("input_path", ""),
        "project_types": sorted(set(project_types)),
        "package_managers": sorted(set(package_managers)),
        "frameworks": sorted(set(frameworks)),
        "entry_points": sorted(f for f in files if Path(f).name in {"main.py", "app.py", "server.py", "cli.py"}),
        "test_commands": sorted(set(test_commands)),
        "build_commands": sorted(set(build_commands)),
        "run_commands": sorted(set(run_commands)),
        "supported_commands": sorted(set(supported_commands)),
        "detected_dependencies": sorted(deps),
        "supported_capabilities": sorted(features),
        "excluded_files_summary": {"total": len(ignored), "reasons": ignored_reasons, "records": ignored[:25]},
        "included_file_count": included_count,
        "confirmed_files": sorted(files),
        "ignored_file_count": len(ignored),
        "safe_claims": safe_claims,
        "unknowns": [
            "Runtime behavior was not executed.",
            "Semantic correctness was not proven.",
            "External services were not verified.",
            "Capabilities not present in structural evidence must be treated as unknown.",
            "Missing files must not be invented.",
        ],
        "claim_boundaries": claim_boundaries,
        "ai_constraints": [
            "Use only the packet and reality map as project evidence.",
            "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
            "If a required file is missing, say it is missing.",
            "If a command is unsupported by detected evidence, say it is unsupported.",
            "If a capability is not in supported_capabilities, treat it as unknown or unsupported.",
            "Cite file paths when making project-specific claims.",
            "Do not claim SourcePack proves semantic truth.",
            "Ask for missing files rather than hallucinating them.",
        ],
    }


def render_ai_instructions(reality_map: dict) -> str:
    lines = [
        "# AI Instructions for This SourcePack Packet", "",
        "Use only the packet and `reality_map.json` as project evidence.",
        "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
        "If a required file is missing, say it is missing and ask for it rather than hallucinating it.",
        "If a command is unsupported by detected evidence, say it is unsupported.",
        "If a capability is not listed in `supported_capabilities`, treat it as unknown or unsupported.",
        "If you introduce a new external dependency, modify the appropriate dependency manifest in the same patch and list it under Dependency Changes.",
        "Only recommend commands listed under Supported Commands unless your patch also adds the project file that defines the new command.",
        "Before referencing a file as existing, it must appear in Confirmed Files; label intentional creations as NEW FILE.",
        "If required evidence is missing, say UNKNOWN and ask for the missing file/output instead of guessing.",
        "Cite file paths when making project-specific claims.",
        "Do not claim SourcePack proves semantic truth, security, production readiness, or external service behavior.", "",
        "## Supported Commands", "",
    ]
    cmds = reality_map.get("supported_commands", [])
    lines.extend([f"- `{cmd}`" for cmd in cmds] or ["- None detected"])
    lines.extend(["", "## Supported Capabilities", ""])
    caps = reality_map.get("supported_capabilities", [])
    lines.extend([f"- {cap}" for cap in caps] or ["- None detected"])
    lines.extend(["", "## Confirmed Files", ""])
    lines.extend(f"- `{path}`" for path in reality_map.get("confirmed_files", [])[:200])
    lines.extend(["", "## Required Answer Contract", "", "- Files to modify", "- New files", "- Dependency changes", "- Commands to run", "- Assumptions/unknowns", "- Patch or code", "", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in reality_map.get("claim_boundaries", []))
    return "\n".join(lines) + "\n"

def load_manifest(packet: Path) -> dict:
    return json.loads((packet / "manifest.json").read_text(encoding="utf-8"))




PATHLIKE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cfg", ".ini", ".css", ".html", ".rs", ".go", ".java", ".rb", ".php", ".sh"}
PROJECT_PATH_PREFIXES = {"src", "sourcepack", "tests", "test", "frontend", "backend", "docs", "app", "lib", "packages", "public", "config", "scripts"}


def _normalize_ai_ref(ref: str) -> str | None:
    ref = ref.strip().strip("`'\".,;)")
    ref = ref.replace("\\", "/")
    if ref.endswith(":"):
        ref = ref[:-1]
    while ref.startswith("./"):
        ref = ref[2:]
    if not ref or ref.startswith("/") or re.match(r"^[A-Za-z]:/", ref):
        return None
    normalized, unsafe = _normalize_diff_path(ref)
    if unsafe or not normalized:
        return None
    return normalized


def _looks_like_ai_file_ref(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in {"Dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml", "pyproject.toml", "package.json", "requirements.txt"}:
        return True
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in PATHLIKE_EXTENSIONS:
        return False
    parts = [p for p in PurePosixPath(normalized).parts if p not in {"."}]
    return "/" in normalized or (parts and parts[0] in PROJECT_PATH_PREFIXES)


def extract_refs(text: str) -> set[str]:
    refs: set[str] = set()
    token = r"(?:\./)?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*\.[A-Za-z0-9_.-]+:?|Dockerfile"
    patterns = [rf"[`'\"]({token})[`'\"]", rf"(?m)^\s*[-*]\s+({token})\b", rf"\b(?:edit|open|update|modify|change|in|file)\s+({token})\b", rf"\b((?:\./)?(?:src|sourcepack|tests|test|frontend|backend|docs|app|lib|packages|public|config|scripts)[\\/][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_.-]+:?)\b"]
    for pattern in patterns:
        for candidate in re.findall(pattern, text, re.I):
            normalized = _normalize_ai_ref(candidate)
            if normalized and _looks_like_ai_file_ref(normalized):
                refs.add(normalized)
    return refs


def _packet_file_contents(packet: Path) -> dict[str, str]:
    context_path = packet / "context.md"
    if not context_path.exists():
        return {}
    text = context_path.read_text(encoding="utf-8", errors="ignore")
    contents: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    in_content = False
    for line in text.splitlines():
        if line.startswith("## File: "):
            if current is not None:
                contents[current] = "\n".join(body).rstrip("\n")
            current = line.removeprefix("## File: ").strip()
            body = []
            in_content = False
        elif current is not None and line == "Content:":
            in_content = True
            body = []
        elif current is not None and in_content and line == "---":
            contents[current] = "\n".join(body).rstrip("\n")
            current = None
            body = []
            in_content = False
        elif current is not None and in_content:
            body.append(line)
    if current is not None:
        contents[current] = "\n".join(body).rstrip("\n")
    return contents


def _normalize_dependency_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _dependency_name_for_import(name: str) -> str:
    normalized = _normalize_dependency_name(name)
    return PY_IMPORT_ALIASES.get(normalized, normalized)


def _is_js_local_specifier(imported: str) -> bool:
    return imported.startswith((".", "/"))


def _js_package_root(imported: str) -> str:
    imported = imported.strip().lower()
    if _is_js_local_specifier(imported):
        return imported
    parts = imported.split("/")
    if imported.startswith("@") and len(parts) >= 2 and parts[0] != "@":
        return "/".join(parts[:2])
    if imported.startswith("@/"):
        return imported
    return parts[0]


def _python_dependency_names_from_requirement_lines(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned and not cleaned.startswith(("-", "--")):
            deps.add(_normalize_dependency_name(re.split(r"[<>=!~;\[]", cleaned, maxsplit=1)[0]))
    return deps


def _python_dependency_names_from_pyproject(content: str) -> set[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return set()
    deps: set[str] = set()

    def add_requirement(req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                deps.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_requirement(req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_requirement(req)

    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            for section_name in ("dependencies", "dev-dependencies"):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    for dep in section:
                        if dep.lower() != "python":
                            deps.add(_normalize_dependency_name(dep))
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            deps.update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_requirement(req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_requirement(req)
    return deps


def _add_common_dependency(deps: set[str], name: str):
    normalized = _normalize_dependency_name(name)
    for dep in COMMON_DEPENDENCIES:
        if normalized == _normalize_dependency_name(dep):
            deps.add(dep.lower())


def dependency_inventory(manifest: dict, packet: Path) -> set[str]:
    deps: set[str] = set()
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        suffix = Path(rel).suffix.lower()
        if name == "pyproject.toml":
            for dep in _python_dependency_names_from_pyproject(content):
                _add_common_dependency(deps, dep)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for dep in _python_dependency_names_from_requirement_lines(content):
                _add_common_dependency(deps, dep)
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    for dep_name in section_deps:
                        _add_common_dependency(deps, dep_name)
        elif suffix == ".py":
            for imported in re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", content):
                _add_common_dependency(deps, imported)
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            for imported in re.findall(r"""(?:from\s+["']|import\s*\(\s*["']|require\s*\(\s*["'])(@?[A-Za-z0-9_.-]+)""", content):
                _add_common_dependency(deps, _js_package_root(imported))
    return deps


def _has_import(content: str, *modules: str) -> bool:
    module_pattern = "|".join(re.escape(module) for module in modules)
    return bool(re.search(rf"(?m)^\s*(?:import|from)\s+({module_pattern})(?:\b|[._])", content))


PDF_DEPENDENCIES = {"pypdf", "pdfplumber", "fitz", "pymupdf"}


def _declares_pdf_dependency(rel: str, content: str) -> bool:
    name = Path(rel).name.lower()
    if name == "pyproject.toml":
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_pyproject(content))
    if name.startswith("requirements") and name.endswith(".txt"):
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_requirement_lines(content))
    return False


def feature_inventory(manifest: dict, packet: Path, deps: set[str] | None = None) -> set[str]:
    if deps is None:
        deps = dependency_inventory(manifest, packet)
    contents = _packet_file_contents(packet)
    files = {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}
    lower_files = {rel.lower() for rel in files}
    features: set[str] = set()

    if any(Path(rel).name.lower() in {"dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"} for rel in files):
        features.add("docker")
    if any(rel.endswith(("/pdf_parser.py", "pdf_parser.py")) for rel in lower_files):
        features.add("pdf")
    if any(_declares_pdf_dependency(rel, content) for rel, content in contents.items()):
        features.add("pdf")
    if "react" in deps or any(rel in {"frontend/app.tsx", "frontend/app.jsx"} for rel in lower_files):
        features.add("react")
    if deps & {"fastapi", "flask", "django"} or any(Path(rel).name.lower() in {"server.py", "app.py"} for rel in files):
        features.add("web server")
    if deps & {"sqlalchemy", "prisma"} or any("/migrations/" in f"/{rel}/" or Path(rel).name.lower() in {"schema.prisma", "schema.sql"} for rel in files):
        features.add("database")
    if any(part == "auth" or part.startswith("auth_") for rel in lower_files for part in Path(rel).parts):
        features.add("authentication")

    for rel, content in contents.items():
        suffix = Path(rel).suffix.lower()
        if suffix == ".py":
            if _has_import(content, "pypdf", "pdfplumber", "fitz"):
                features.add("pdf")
            if _has_import(content, "fastapi", "flask", "django") or re.search(r"(?m)^\s*@\w+\.(?:route|get|post|put|patch|delete)\(", content):
                features.add("web server")
            if _has_import(content, "sqlalchemy", "prisma") or re.search(r"(?i)\b(sqlite|postgres(?:ql)?|mysql)://", content):
                features.add("database")
            if _has_import(content, "jwt", "oauthlib", "authlib") or re.search(r"(?i)@\w+\.(?:route|get|post)\([^)]*login", content):
                features.add("authentication")
            if _has_import(content, "pytesseract", "easyocr"):
                features.add("ocr")
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            if re.search(r"""(?:from\s+["']react["']|require\s*\(\s*["']react["']|import\s+React\b)""", content):
                features.add("react")
            if re.search(r"(?i)\b(jwt|oauth|session|login)\b", content):
                features.add("authentication")
        elif Path(rel).name.lower() == "package.json":
            if re.search(r'"react"\s*:', content):
                features.add("react")
    return features


PROTECTED_PACKET_ARTIFACTS = {"manifest.json", "receipt.json", "reality_map.json", "ai_instructions.md"}


def _normalize_inventory_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    rel, unsafe = _normalize_diff_path(value)
    if unsafe or not rel:
        return None
    return rel


def _baseline_inventory_from_packet(packet: str | Path, manifest: dict | None = None) -> tuple[set[str], bool]:
    """Return authoritative enforcement baseline paths when a packet has them.

    Prompt context manifests may be selective, so diff enforcement must prefer the
    baseline file inventory artifact when it exists. The boolean is True only
    when a full inventory artifact was loaded successfully.
    """
    packet = Path(packet)
    for name in ("file_inventory.json", "inventory.json", "baseline_inventory.json"):
        path = packet / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_files = data.get("files") if isinstance(data, dict) else data
        if not isinstance(raw_files, list):
            continue
        files: set[str] = set()
        for item in raw_files:
            raw_path = item.get("relative_path") if isinstance(item, dict) else item
            rel = _normalize_inventory_path(raw_path)
            if rel:
                files.add(rel)
        return files, True
    return _included_paths(manifest or load_manifest(packet)), False


def known_files(manifest: dict, packet_path: str | Path | None = None) -> set[str]:
    if packet_path is not None:
        files, _ = _baseline_inventory_from_packet(packet_path, manifest)
        return files
    return _included_paths(manifest)


def supported_commands_inventory(reality_map: dict) -> set[str]:
    return set(reality_map.get("supported_commands", []))


def docker_evidence(files: set[str]) -> dict[str, bool]:
    names = {Path(f).name.lower() for f in files}
    return {
        "dockerfile": "dockerfile" in names,
        "compose": bool(names & {"docker-compose.yml", "compose.yaml", "compose.yml"}),
    }


def python_project_evidence(files: set[str], deps: set[str]) -> dict[str, bool]:
    lower = {f.lower() for f in files}
    return {
        "python_project": "pyproject.toml" in lower or any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower),
        "tests": any(f == "tests" or f.startswith("tests/") for f in lower),
        "pytest": "pytest" in deps,
    }


def node_project_evidence(files: set[str], scripts: dict[str, str]) -> dict[str, bool]:
    return {"package_json": "package.json" in {f.lower() for f in files}, "scripts": bool(scripts)}


def extract_js_import_specifiers_from_text(text: str) -> set[str]:
    specifiers: set[str] = set()
    patterns = [
        r"""\bimport\s+(?:[^"'()]+?\s+from\s+)?["']([^"']+)["']""",
        r"""\bexport\s+[^"']*?\s+from\s+["']([^"']+)["']""",
        r"""\bimport\s*\(\s*["']([^"']+)["']\s*\)""",
        r"""\brequire\s*\(\s*["']([^"']+)["']\s*\)""",
    ]
    for pattern in patterns:
        specifiers.update(m.strip() for m in re.findall(pattern, text) if m.strip())
    return {s.lower() for s in specifiers}


def extract_imports_from_text(text: str, suffix: str = ".py") -> set[str]:
    imports: set[str] = set()
    if suffix == ".py":
        imports |= set(re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text))
    elif suffix in JS_EXTS:
        imports |= extract_js_import_specifiers_from_text(text)
    return {i.lower() for i in imports}







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
    return set()


def analyze_patch(packet_path: str | Path, patch_text: str, changes: list[PatchFileChange] | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    reality = json.loads((packet / "reality_map.json").read_text(encoding="utf-8")) if (packet / "reality_map.json").exists() else generate_reality_map(manifest, packet)
    files, baseline_inventory_loaded = _baseline_inventory_from_packet(packet, manifest)
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
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "path_escape"]
    if any(report.get(k) for k in fail_keys):
        report["verdict"] = "FAIL"
    elif report["new_files"] or report["warnings"] or report.get("uncertainties"):
        report["verdict"] = "WARN"
    for key in ["modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "warnings"]:
        report[key] = sorted(set(report[key]))
    return report



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
        except Exception:
            full.setdefault("warnings", []).append("report_artifact_write_failed")
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
    if result and result[0] == "":
        result = result[1:]
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


def _declared_dependency_scopes_by_ecosystem(manifest: dict, packet: Path) -> dict[str, dict[str, set[str]]]:
    contents = _packet_file_contents(packet)
    scopes = {"python": {"runtime": set(), "dev": set(), "optional": set()}, "js": {"runtime": set(), "dev": set(), "optional": set()}}
    for rel, content in contents.items():
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

def judge_patch_text(packet_path: str | Path, patch_text: str) -> dict:
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
    report = analyze_patch(packet_path, patch_text, changes)
    packet = Path(packet_path); manifest = load_manifest(packet); files = known_files(manifest, packet); contents = _packet_file_contents(packet)
    existing_declared = _declared_dependency_names_by_ecosystem(manifest, packet)
    scopes = _declared_dependency_scopes_by_ecosystem(manifest, packet)
    patch_declared, manifest_uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
    if manifest_uncertainties:
        report.setdefault("uncertainties", []).extend(manifest_uncertainties)
    workspace_names = _workspace_package_names(packet)
    unsupported = set(report.get("unsupported_dependencies", []))
    resolver_tmp = _materialize_packet_worktree(packet)
    resolver_root = Path(resolver_tmp.name)
    try:
        for ch in changes:
            suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
            if suffix == ".py":
                for imported in extract_imports_from_text(added, suffix):
                    dep_resolution = resolve_python_import(resolver_root, imported, added_dependencies=patch_declared["python"])
                    dep_name = _dependency_name_for_import(imported)
                    if dep_resolution.verdict == "PASS":
                        unsupported.discard(imported); unsupported.discard(dep_name)
                    elif dep_resolution.reason_code == "declared_dependency":
                        unsupported.discard(imported); unsupported.discard(dep_name)
                        report.setdefault("uncertainties", []).append({"id": "declared_dependency", "message": f"{dep_name} is declared in the same patch and requires review", "path": ch.path, "evidence": dep_name})
                    elif dep_resolution.reason_code == "dependency_scope_review":
                        report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{dep_name} is declared outside the runtime dependency scope", "path": ch.path, "evidence": dep_name})
                    elif dep_resolution.reason_code == "unsupported_dependency":
                        unsupported.add(imported)
            elif suffix in JS_EXTS:
                for imported in extract_imports_from_text(added, suffix):
                    if _is_js_local_specifier(imported):
                        continue
                    pkg = _js_package_root(imported)
                    local_alias = _js_alias_local(imported, files, contents)
                    if pkg in workspace_names or local_alias is True:
                        continue
                    dep_resolution = resolve_js_import(resolver_root, imported)
                    if dep_resolution.verdict == "PASS":
                        unsupported.discard(pkg)
                    elif dep_resolution.reason_code == "js_alias_uncertain":
                        report.setdefault("uncertainties", []).append({"id": "js_alias_uncertain", "message": f"{imported} could not be resolved safely", "path": ch.path, "evidence": imported})
                    elif dep_resolution.reason_code == "dependency_scope_review":
                        report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{pkg} is declared outside the runtime dependency scope", "path": ch.path, "evidence": pkg})
                    elif dep_resolution.reason_code == "unsupported_dependency" and pkg not in patch_declared["js"]:
                        unsupported.add(pkg)
    finally:
        resolver_tmp.cleanup()

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
    unsupported -= patch_declared["python"]
    unsupported -= patch_declared["js"]
    report["unsupported_dependencies"] = sorted(unsupported)
    if declared_only:
        report.setdefault("warnings", []).append("Patch declares new dependencies that require review.")
        report["declared_dependencies"] = sorted(declared_only)
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "binary_diff_blockers", "path_escape"]
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
    for p in report.get("new_files", []): findings.append(normalized_finding("new_file", "warn", "review", f"{p} was created by the patch.", p))
    for p in report.get("deleted_files", []): findings.append(normalized_finding("deleted_file", "warn", "review", f"{p} was deleted by the patch.", p))
    for d in report.get("declared_dependencies", []): findings.append(normalized_finding("declared_dependency", "warn", "review", f"{d} was added to dependency files.", evidence=d))
    for c in report.get("declared_commands", []): findings.append(normalized_finding("declared_command", "warn", "review", f"{c} was added in the same patch.", evidence=c))
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
    return traffic_report(report.get("verdict", "PASS"), findings=findings, checked_categories=["file references", "Python imports", "JS/TS imports", "known project commands", "protected SourcePack artifacts"], report_path=report_path)


def run_git(repo: Path, args: list[str]):
    return canonical_run_git(repo, args)


def git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    repo = Path(repo)
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            return False, "git_unavailable"
        if cp.returncode == GIT_RETURNCODE_TIMEOUT:
            return False, "git_timeout"
        if cp.returncode == GIT_RETURNCODE_OS_ERROR:
            return False, "git_error"
        return False, "not_git"
    root = Path(cp.stdout.strip())
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        diff_cp = run_git(root, list(args))
        if diff_cp.returncode == 1:
            return True, None
        if diff_cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            return False, "git_unavailable"
        if diff_cp.returncode == GIT_RETURNCODE_TIMEOUT:
            return False, "git_timeout"
        if diff_cp.returncode == GIT_RETURNCODE_OS_ERROR:
            return False, "git_error"
        if diff_cp.returncode != 0:
            return False, "git_error"
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0 and untracked.stdout.strip():
        return True, None
    if untracked.returncode == GIT_RETURNCODE_NOT_FOUND:
        return False, "git_unavailable"
    if untracked.returncode == GIT_RETURNCODE_TIMEOUT:
        return False, "git_timeout"
    if untracked.returncode == GIT_RETURNCODE_OS_ERROR:
        return False, "git_error"
    if untracked.returncode != 0:
        return False, "git_error"
    return False, None



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


def untracked_files_as_diff(repo: str | Path) -> str:
    repo = Path(repo)
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    if cp.returncode != 0:
        return ""
    chunks = []
    for rel in [line.strip() for line in cp.stdout.splitlines() if line.strip()]:
        safe_rel, unsafe = _normalize_diff_path(rel)
        if unsafe or not safe_rel:
            continue
        path = repo / safe_rel
        if safe_rel == ".gitignore":
            try:
                ignore_lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
            except OSError:
                ignore_lines = set()
            if ignore_lines <= {".sourcepack", ".sourcepack/"}:
                continue
        chunks.extend([f"diff --git a/{safe_rel} b/{safe_rel}", "new file mode 100644", "--- /dev/null", f"+++ b/{safe_rel}"])
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
    return "\n".join(chunks) + ("\n" if chunks else "")

def build_repo_change_report(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, ci: bool = False, base_ref: str | None = None, head_ref: str | None = None) -> dict:
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
    repo = repo_arg if validate_baseline(repo_arg).get("state") in {"present", "stale", "corrupt"} else git_root
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if added:
        paths.setdefault("gitignore_added", True)
    if err:
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
    if patch_text is None:
        if base_ref is not None and head_ref is not None:
            diff_args = ["diff", "--binary", f"{base_ref}...{head_ref}"]
        else:
            diff_args = ["diff", "--staged"] if staged else ["diff"]
        if repo != git_root:
            diff_args.append("--relative")
        cp = run_git(repo, diff_args); diff_text = cp.stdout
        if cp.returncode == GIT_RETURNCODE_NOT_FOUND:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable", "error", "git", "Git executable not found.")])
        if cp.returncode == GIT_RETURNCODE_TIMEOUT:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_timeout", "error", "git", f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds.")])
        if cp.returncode != 0:
            message = cp.stderr.strip() or "Git diff failed."
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_diff_failed", "error", "git", message)])
        if base_ref is None and head_ref is None and not staged:
            extra = untracked_files_as_diff(repo)
            if extra and not (added and _only_sourcepack_gitignore_change(repo)):
                diff_text = (diff_text + "\n" + extra).strip() + "\n"
    else:
        diff_text = patch_text
    baseline_status = validate_baseline(repo)
    if baseline_status["state"] == "corrupt":
        rep = traffic_report("FAIL", "trusted baseline is corrupt.", [normalized_finding("baseline_corrupt", "error", "baseline", baseline_status["message"])], ["baseline", "diff"], "Recreate the baseline only after verifying the current repo state should be trusted.")
        rep.update(baseline_report_fields(baseline_status)); return rep
    if baseline_status["state"] == "missing":
        dirty_now, dirty_state_now = git_worktree_dirty(repo)
        if ci:
            rep = traffic_report("FAIL", "trusted baseline is missing in CI.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists; CI must not establish trust.")], ["baseline", "diff"], "create the baseline locally only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        if diff_text.strip() or (dirty_now and not _only_sourcepack_gitignore_change(repo)):
            rep = traffic_report("FAIL", "baseline missing while changes are present.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists while changes are present.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        try:
            build_current_baseline(repo, quiet=True, force=False); baseline_status = validate_baseline(repo)
            rep_note = "Created SourcePack baseline because none existed and no diff was present."
        except BaselineLockError as exc:
            return traffic_report("WARN", "baseline writer is locked.", [normalized_finding("baseline_locked", "warn", "tooling", str(exc))], ["baseline", "diff"], "try again after the other baseline operation finishes.", reason_type="tooling")
        except Exception as exc:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}")])
    else:
        rep_note = None
    stale_findings = []
    if baseline_status["state"] == "stale":
        stale_findings.append(normalized_finding("baseline_stale", "warn", "uncertainty", "Trusted SourcePack baseline may not match current repo state."))
    if not diff_text.strip():
        verdict = "WARN" if stale_findings else "PASS"
        rep = traffic_report(verdict, "SourcePack could not fully evaluate this change." if stale_findings else "good to continue.", [normalized_finding("no_diff", "info", "diff", "No uncommitted changes detected."), *stale_findings], ["diff", "baseline freshness"])
    else:
        packet_path = repo / baseline_status["packet_path"]
        raw = judge_patch_text(packet_path, diff_text); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
        rep = _integrate_execution_findings(repo, diff_text, rep)
        rep = _apply_local_policy(repo, rep)
        rep = _apply_policy_rules(repo, packet_path, diff_text, rep)
        rep = _apply_policy_config(repo, rep)
        if stale_findings and rep["verdict"] != "FAIL":
            rep = traffic_report("WARN", "SourcePack could not fully evaluate this change.", rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action"), reason_type="uncertainty"); rep["raw_patch_judgment"] = raw
        elif stale_findings:
            rep = traffic_report("FAIL", rep.get("headline"), rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action")); rep["raw_patch_judgment"] = raw
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
    for key in ("raw_patch_judgment", "policy_overrides", "policy_config", "policy_config_ignores", "policy_config_warnings", "policy_rule_findings"):
        if key in rep:
            rebuilt[key] = rep[key]
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


def _policy_rule_findings(repo: Path, packet_path: Path, diff_text: str) -> list[dict]:
    config = load_policy_config(repo)
    rules = config.rules
    if not rules.enabled() or not diff_text.strip():
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
        for pattern in rules.protected_paths:
            if policy_path_matches(path, pattern):
                findings.append(normalized_finding(
                    "policy_protected_path",
                    "error",
                    "policy",
                    "Proposed change modified a path protected by repository policy.",
                    path,
                    evidence=pattern,
                    suggestion="Change the protected path only after updating repository policy or obtaining the required review.",
                ))
                break

    if rules.package_manager == "pnpm":
        conflicting = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock"}
        for change in changes:
            if change.deleted_file:
                continue
            path = change.path
            if path and PurePosixPath(path).name in conflicting:
                findings.append(normalized_finding(
                    "policy_package_manager_drift",
                    "error",
                    "policy",
                    "Proposed change added or modified a package-manager artifact that conflicts with repository policy.",
                    path,
                    evidence="pnpm",
                    suggestion="Use pnpm artifacts for this repository or update policy intentionally.",
                ))

    if rules.max_changed_lines is not None:
        changed_line_count = _policy_changed_line_count(changes)
        if changed_line_count > rules.max_changed_lines:
            findings.append(normalized_finding(
                "policy_large_diff",
                "warn",
                "policy",
                f"Proposed change modifies {changed_line_count} lines, exceeding repository policy limit {rules.max_changed_lines}.",
                evidence=str(changed_line_count),
                suggestion="Split the proposed change or raise the configured limit intentionally.",
            ))

    if rules.require_tests_for:
        has_test_change = any(_is_test_path(path) for path in changed_paths)
        if not has_test_change:
            for path in changed_paths:
                if _is_test_path(path):
                    continue
                if any(policy_path_matches(path, pattern) for pattern in rules.require_tests_for):
                    findings.append(normalized_finding(
                        "policy_missing_test",
                        "warn",
                        "policy",
                        "Proposed change altered a path that repository policy expects to be accompanied by a test change.",
                        path,
                        evidence=", ".join(rules.require_tests_for),
                        suggestion="Add or update a corresponding test in the same delta, or adjust repository policy intentionally.",
                    ))
                    break

    if rules.block_secret_patterns:
        for change in changes:
            for line in change.added_lines or []:
                if _line_has_policy_secret(line):
                    findings.append(normalized_finding(
                        "policy_secret_pattern",
                        "error",
                        "policy",
                        "Proposed change added obvious credential-shaped assignment material blocked by repository policy.",
                        change.path,
                        suggestion="Remove the credential-shaped value or replace it with an obvious placeholder.",
                    ))
                    break

    if rules.block_dependency_additions:
        manifest = load_manifest(packet_path)
        contents = _packet_file_contents(packet_path)
        existing = _declared_dependency_names_by_ecosystem(manifest, packet_path)
        declared, uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
        if not uncertainties:
            additions = sorted((declared["python"] | declared["js"]) - (existing["python"] | existing["js"]))
            for dependency in additions:
                findings.append(normalized_finding(
                    "policy_dependency_addition",
                    "error",
                    "policy",
                    "Proposed change added an unapproved dependency to project manifest files.",
                    evidence=dependency,
                    suggestion="Remove the dependency addition or update repository policy/review evidence intentionally.",
                ))

    return findings


def _apply_policy_rules(repo: Path, packet_path: Path, diff_text: str, rep: dict) -> dict:
    findings = _policy_rule_findings(repo, packet_path, diff_text)
    if not findings:
        return rep
    rebuilt = _rebuild_from_findings(rep, list(rep.get("findings", [])) + findings)
    rebuilt["policy_rule_findings"] = findings
    return rebuilt


def _policy_entries_for_judgment(repo: Path) -> list[dict]:
    path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    if not path.exists():
        return []
    entries = []
    now = utc_now()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except Exception:
            continue
        expires = entry.get("expires_at")
        if expires and str(expires) < now:
            continue
        entries.append(entry)
    return entries


def _policy_matches(entry: dict, finding: dict) -> bool:
    scope = entry.get("scope")
    value = str(entry.get("value") or "")
    fid = finding.get("id")
    if fid == "git_path_modification" or str(finding.get("path") or "").startswith(".git/"):
        return False
    if scope == "dependency":
        return fid == "unsupported_dependency" and finding.get("evidence") == value
    if scope == "command":
        return fid == "unsupported_command" and finding.get("evidence") == value
    if scope == "path":
        if str(finding.get("path") or "") != value:
            return False
        if str(value).startswith(".sourcepack/baseline/") and not entry.get("high_risk"):
            return False
        return fid not in {"git_path_modification"}
    return False


def _apply_local_policy(repo: Path, rep: dict) -> dict:
    entries = _policy_entries_for_judgment(repo)
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
    rebuilt = _rebuild_from_findings(rep, kept)
    rebuilt["policy_overrides"] = overrides
    rebuilt.setdefault("findings", []).append(normalized_finding("policy_override", "info", "policy", "A local allow policy suppressed a matching finding.", evidence=", ".join(str(o.get("value")) for o in overrides)))
    return _rebuild_from_findings(rebuilt, rebuilt["findings"])


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


def judge_repo_change(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, policy_mode: PolicyMode | str = PolicyMode.LOCAL, base_ref: str | None = None, head_ref: str | None = None) -> Judgment:
    """Judge repository changes without CLI parsing, stdout rendering, or cli.py imports."""
    mode = normalize_policy_mode(policy_mode)
    report = build_repo_change_report(Path(repo_path).resolve(), staged=staged, patch_text=patch_text, ci=(mode is PolicyMode.CI), base_ref=base_ref, head_ref=head_ref)
    if mode is PolicyMode.CI:
        report["ci"] = True
    return Judgment(str(Path(repo_path).resolve()), mode, report)
