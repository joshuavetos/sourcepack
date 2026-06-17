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
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape
from .diff_parser import PatchFileChange, normalize_diff_path as _normalize_diff_path, parse_unified_diff
from .ecosystems.python import PY_IMPORT_ALIASES
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.json import normalized_finding, traffic_report, write_user_report
from .policy import PolicyMode, normalize_policy_mode, exit_code as policy_exit_code

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


class SourceScanner:
    def __init__(self, input_path: str | Path, max_file_size: int = 1_000_000, include_hidden: bool = False, redact: bool = True):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0

    def ignore(self, path: Path, reason: str):
        rel = str(path.relative_to(self.input_path)) if path.is_absolute() or self.input_path in path.parents else str(path)
        self.ignored_files.append(IgnoredFile(rel, reason))

    def scan(self):
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_path}")
        for root, dirs, files in os.walk(self.input_path, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(dirs)
            files = sorted(files)
            kept_dirs = []
            for d in dirs:
                dpath = root_path / d
                rel = dpath.relative_to(self.input_path)
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "symlink_skipped"))
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs
            for filename in files:
                fp = root_path / filename
                rel = fp.relative_to(self.input_path)
                self.total_seen += 1
                rel_str = str(rel)
                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped")); continue
                if not self.include_hidden and filename.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file")); continue
                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern")); continue
                try:
                    size = fp.stat().st_size
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "stat_error")); continue
                if size > self.max_file_size:
                    self.ignored_files.append(IgnoredFile(rel_str, "max_file_size_exceeded")); continue
                if fp.suffix and fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    self.ignored_files.append(IgnoredFile(rel_str, "unsupported_extension")); continue
                if is_probably_binary(fp):
                    self.ignored_files.append(IgnoredFile(rel_str, "binary_detected")); continue
                try:
                    content = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    self.ignored_files.append(IgnoredFile(rel_str, "decode_error")); continue
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "read_error")); continue
                source_sha256 = sha256_text(content)
                if self.redact:
                    redacted, reds = redact_secrets(content)
                    for r in reds:
                        r["file"] = rel_str
                    self.redactions.extend(reds)
                    content = redacted
                packet_sha256 = sha256_text(content)
                self.included_files.append(IncludedFile(
                    relative_path=rel_str,
                    absolute_path=str(fp.resolve()),
                    size_bytes=size,
                    sha256=packet_sha256,
                    source_sha256=source_sha256,
                    packet_sha256=packet_sha256,
                    estimated_tokens=estimate_tokens(content),
                    extension=fp.suffix.lower(),
                    content=content,
                ))
        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    source = "scanner_included_files"
    try:
        cp = subprocess.run(["git", "ls-files", "-z"], cwd=root, text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError):
        cp = None
    if cp is not None and cp.returncode == 0:
        raw_paths = [p.decode("utf-8", "surrogateescape") for p in cp.stdout.split(b"\0") if p]
        source = "git_ls_files" if raw_paths else "scanner_included_files"
        if not raw_paths:
            raw_paths = sorted(included)
    else:
        raw_paths = sorted(included)
    for raw in raw_paths:
        rel = raw.replace("\\", "/")
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


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md", "file_inventory.json"]

    def __init__(self, out: str | Path, scanner: SourceScanner, force: bool = False):
        self.out = Path(out)
        self.scanner = scanner
        self.force = force

    def prepare_out(self):
        if self.out.exists() and any(self.out.iterdir()):
            if not self.force:
                raise FileExistsError(f"Output directory is non-empty: {self.out}")
            for child in self.out.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        self.out.mkdir(parents=True, exist_ok=True)

    def write_all(self):
        self.prepare_out()
        included_records = []
        for f in self.scanner.included_files:
            rec = asdict(f)
            rec.pop("content")
            included_records.append(rec)
        ignored_records = [asdict(f) for f in self.scanner.ignored_files]
        total_tokens = sum(f.estimated_tokens for f in self.scanner.included_files)
        total_bytes = sum(f.size_bytes for f in self.scanner.included_files)
        manifest = {
            "input_path": str(self.scanner.input_path),
            "generated_at": utc_now(),
            "tool_version": __version__,
            "total_files_seen": self.scanner.total_seen,
            "total_files_included": len(included_records),
            "total_files_ignored": len(ignored_records),
            "total_bytes_included": total_bytes,
            "total_estimated_tokens": total_tokens,
            "included_files": included_records,
            "ignored_files": ignored_records,
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.out / "file_inventory.json").write_text(json.dumps(_tracked_file_inventory(self.scanner.input_path, included_records), indent=2), encoding="utf-8")
        md_parts = ["# SourcePack Context Packet", "", "## Source Manifest Summary", "", f"Input path: {manifest['input_path']}", f"Generated at: {manifest['generated_at']}", f"Files included: {len(included_records)}", f"Estimated tokens: {total_tokens}", ""]
        for f in self.scanner.included_files:
            md_parts.extend([
                f"## File: {f.relative_path}", "", "Metadata:", f"- sha256: {f.sha256}", f"- bytes: {f.size_bytes}", f"- estimated_tokens: {f.estimated_tokens}", "", "Content:", "", f.content, "", "---", ""
            ])
        (self.out / "context.md").write_text("\n".join(md_parts), encoding="utf-8")
        xml_parts = ["<sourcepack>", "  <files>"]
        for f in self.scanner.included_files:
            xml_parts.append(f'    <file path="{xml_escape(f.relative_path)}" sha256="{f.sha256}" bytes="{f.size_bytes}" estimated_tokens="{f.estimated_tokens}">')
            xml_parts.append("      <content>")
            xml_parts.append(xml_escape(f.content))
            xml_parts.append("      </content>")
            xml_parts.append("    </file>")
        xml_parts.extend(["  </files>", "</sourcepack>"])
        (self.out / "context.xml").write_text("\n".join(xml_parts), encoding="utf-8")
        tree_lines = []
        for f in self.scanner.included_files:
            tree_lines.append(f"[INC] {f.relative_path}")
        for f in self.scanner.ignored_files:
            tree_lines.append(f"[IGN] {f.relative_path} - {f.reason}")
        (self.out / "file_tree.txt").write_text("\n".join(sorted(tree_lines)) + "\n", encoding="utf-8")
        (self.out / "ignored_files.txt").write_text("\n".join(f"{f.relative_path}\t{f.reason}" for f in self.scanner.ignored_files) + "\n", encoding="utf-8")
        token_report = {
            "total_estimated_tokens": total_tokens,
            "warnings": [limit for limit in [32_000, 128_000, 200_000, 1_000_000] if total_tokens > limit],
            "per_file": [{"relative_path": f.relative_path, "estimated_tokens": f.estimated_tokens} for f in self.scanner.included_files],
        }
        (self.out / "token_report.json").write_text(json.dumps(token_report, indent=2), encoding="utf-8")
        (self.out / "redactions.json").write_text(json.dumps({"redactions": self.scanner.redactions}, indent=2), encoding="utf-8")
        reality_map = generate_reality_map(manifest, self.out)
        (self.out / "reality_map.json").write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
        (self.out / "ai_instructions.md").write_text(render_ai_instructions(reality_map), encoding="utf-8")
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out



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


def _js_package_root(imported: str) -> str:
    imported = imported.strip().lower()
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


class BaselineLockError(RuntimeError):
    pass


def _rel_to_repo(repo: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _read_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    return data, None


def baseline_corrupt_result(repo: Path, message: str, details: dict | None = None, packet_path: Path | None = None, metadata_path: Path | None = None, active_pointer_path: Path | None = None, mode: str = "none", active_build_id: str | None = None) -> dict:
    return {"ok": False, "state": "corrupt", "finding_id": "baseline_corrupt", "message": "Trusted SourcePack baseline is corrupt or unverifiable. Recreate the baseline only after verifying the current repo state should be trusted.", "details": {"reason": message, **(details or {})}, "packet_path": _rel_to_repo(repo, packet_path), "metadata_path": _rel_to_repo(repo, metadata_path), "active_pointer_path": _rel_to_repo(repo, active_pointer_path), "mode": mode, "active_build_id": active_build_id}


def resolve_active_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); paths = sourcepack_paths(repo); pointer = paths["active_pointer"]
    if pointer.exists():
        data, err = _read_json_file(pointer)
        if err:
            return baseline_corrupt_result(repo, f"active.json {err}", active_pointer_path=pointer, mode="pointer")
        build_id = data.get("active_build_id")
        if not isinstance(build_id, str) or not build_id or "/" in build_id or "\\" in build_id or build_id in {".", ".."}:
            return baseline_corrupt_result(repo, "active.json has invalid active_build_id", active_pointer_path=pointer, mode="pointer")
        build_dir = (paths["builds"] / build_id).resolve(); builds_dir = paths["builds"].resolve()
        try:
            build_dir.relative_to(builds_dir)
        except ValueError:
            return baseline_corrupt_result(repo, "active.json points outside baseline builds", active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        packet = build_dir / "packet"; meta = build_dir / "metadata.json"
        if not build_dir.exists() or not packet.exists():
            return baseline_corrupt_result(repo, "active.json points to a missing build", packet_path=packet, metadata_path=meta, active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        return {"ok": True, "state": "resolved", "mode": "pointer", "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, meta), "active_pointer_path": _rel_to_repo(repo, pointer), "active_build_id": build_id, "details": {}}
    legacy = paths["packet"]
    if legacy.exists():
        legacy_artifacts = {"manifest.json", "receipt.json", "reality_map.json", "context.md", "ai_instructions.md"}
        present = {child.name for child in legacy.iterdir()} if legacy.is_dir() else set()
        if (legacy / "manifest.json").exists():
            return {"ok": True, "state": "resolved", "mode": "legacy", "packet_path": _rel_to_repo(repo, legacy), "metadata_path": _rel_to_repo(repo, paths["baseline_meta"]), "active_pointer_path": None, "active_build_id": None, "details": {}}
        if present & legacy_artifacts:
            return baseline_corrupt_result(repo, "legacy baseline packet has baseline artifacts but is missing manifest.json", packet_path=legacy, mode="legacy")
    return {"ok": False, "state": "missing", "finding_id": "baseline_missing", "message": "No trusted SourcePack baseline exists while changes are present.", "details": {}, "packet_path": None, "metadata_path": None, "active_pointer_path": None, "mode": "none", "active_build_id": None}


def _validate_packet_artifacts(repo: Path, packet: Path) -> dict | None:
    required = ["manifest.json", "receipt.json", "reality_map.json"]
    for name in required:
        if not (packet / name).exists():
            return baseline_corrupt_result(repo, f"active packet missing {name}", packet_path=packet)
    for name in ["manifest.json", "receipt.json", "reality_map.json", "token_report.json", "redactions.json"]:
        path = packet / name
        if path.exists():
            _, err = _read_json_file(path)
            if err:
                return baseline_corrupt_result(repo, f"{name} {err}", packet_path=packet)
    receipt, err = _read_json_file(packet / "receipt.json")
    if err:
        return baseline_corrupt_result(repo, f"receipt.json {err}", packet_path=packet)
    hashes = receipt.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return baseline_corrupt_result(repo, "receipt.json has no hashes", packet_path=packet)
    for name, expected in hashes.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            return baseline_corrupt_result(repo, "receipt.json contains invalid hash entry", packet_path=packet)
        if Path(name).is_absolute() or ".." in Path(name).parts:
            return baseline_corrupt_result(repo, "receipt.json tracks unsafe artifact path", packet_path=packet)
        packet_root = packet.resolve()
        path = (packet / name).resolve()
        try:
            path.relative_to(packet_root)
        except ValueError:
            return baseline_corrupt_result(repo, "receipt.json tracks path outside packet", packet_path=packet)
        if not path.exists():
            return baseline_corrupt_result(repo, f"receipt-tracked artifact missing: {name}", packet_path=packet)
        try:
            actual = sha256_file(path)
        except OSError as exc:
            return baseline_corrupt_result(repo, f"receipt-tracked artifact unreadable: {name}: {exc}", packet_path=packet)
        if actual != expected:
            return baseline_corrupt_result(repo, f"receipt hash mismatch: {name}", packet_path=packet)
    return None


def validate_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); resolved = resolve_active_baseline(repo)
    if resolved.get("state") == "corrupt":
        return resolved
    if resolved.get("state") == "missing":
        return resolved
    packet = repo / resolved["packet_path"] if resolved.get("packet_path") else None
    meta = repo / resolved["metadata_path"] if resolved.get("metadata_path") else None
    corrupt = _validate_packet_artifacts(repo, packet)
    if corrupt:
        corrupt.update({"mode": resolved.get("mode", "none"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "active_build_id": resolved.get("active_build_id")})
        return corrupt
    if meta and meta.exists():
        _, err = _read_json_file(meta)
        if err:
            return baseline_corrupt_result(repo, f"metadata.json {err}", packet_path=packet, metadata_path=meta, active_pointer_path=repo / resolved["active_pointer_path"] if resolved.get("active_pointer_path") else None, mode=resolved.get("mode", "none"), active_build_id=resolved.get("active_build_id"))
    paths = sourcepack_paths(repo); stale = paths["stale_marker"].exists()
    stale_details = None
    if stale:
        stale_details, err = _read_json_file(paths["stale_marker"])
        if err:
            stale_details = {"reason": "unreadable"}
    return {"ok": True, "state": "stale" if stale else "present", "finding_id": "baseline_stale" if stale else None, "message": "Trusted SourcePack baseline may not match current repo state." if stale else "Trusted SourcePack baseline is present.", "details": {"stale_details": stale_details} if stale else {}, "packet_path": resolved.get("packet_path"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "mode": resolved.get("mode"), "active_build_id": resolved.get("active_build_id")}


def acquire_baseline_lock(repo: str | Path, command: str | None = None) -> tuple[Path, int]:
    paths = ensure_sourcepack_dirs(repo); lock = paths["baseline_lock"]
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BaselineLockError("Another SourcePack baseline operation is already in progress.") from exc
    payload = {"pid": os.getpid(), "command": command, "started_at": utc_now()}
    os.write(fd, json.dumps(payload).encode("utf-8"))
    os.fsync(fd)
    return lock, fd


def release_baseline_lock(lock: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def _unique_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None) -> tuple[dict, bool]:
    repo = Path(repo).resolve(); paths = ensure_sourcepack_dirs(repo)
    previous = validate_baseline(repo); created = previous.get("state") == "missing"
    lock = fd = None; build_dir = None
    try:
        lock, fd = acquire_baseline_lock(repo, "baseline")
        build_id = _unique_build_id(); build_dir = paths["builds"] / build_id; packet = build_dir / "packet"
        build_dir.mkdir(parents=True, exist_ok=False)
        PacketWriter(packet, SourceScanner(repo).scan(), force=True).write_all()
        if not quiet and not verify_packet(packet):
            raise RuntimeError("packet verification returned FAIL")
        candidate = _validate_packet_artifacts(repo, packet)
        if candidate:
            raise RuntimeError(candidate["details"].get("reason", "candidate baseline invalid"))
        meta = {"created_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "scanner_config_hash": scanner_config_hash(), **git_metadata(repo)}
        (build_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        meta_check, meta_err = _read_json_file(build_dir / "metadata.json")
        if meta_err:
            raise RuntimeError(f"metadata.json {meta_err}")
        if fail_stage == "before_pointer_replace":
            raise RuntimeError("injected failure before pointer replacement")
        pointer = {"schema_version": "baseline_pointer.v1", "active_build_id": build_id, "activated_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, build_dir / "metadata.json")}
        _write_json_atomic(paths["active_pointer"], pointer)
        if fail_stage == "after_pointer_replace":
            raise RuntimeError("injected failure after pointer replacement")
        # Enforcement state is active.json -> builds/<id>/packet. Legacy packet copies are intentionally not updated after pointer activation.
        if paths["stale_marker"].exists():
            paths["stale_marker"].unlink()
        return paths, created
    except Exception:
        if build_dir is not None:
            active = None
            try:
                if paths["active_pointer"].exists():
                    active = json.loads(paths["active_pointer"].read_text(encoding="utf-8")).get("active_build_id")
            except Exception:
                active = None
            if active != build_dir.name:
                shutil.rmtree(build_dir, ignore_errors=True)
        raise
    finally:
        if lock is not None and fd is not None:
            release_baseline_lock(lock, fd)


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
        prefix = pattern[:-2].strip("/")
        for rel, content in contents.items():
            if Path(rel).name == "package.json" and rel.startswith(prefix + "/"):
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
    if any(ch.unsafe_path for ch in changes):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "path_escape": True, "path_escape_paths": unsafe_paths}
    if patch_text.strip() and not changes and "Binary files " not in patch_text:
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
    for ch in changes:
        suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
        if suffix == ".py":
            for imported in extract_imports_from_text(added, suffix):
                if imported in PY_STDLIB or imported.startswith(".") or _is_local_python_import(imported, ch.path, files):
                    continue
                dep_name = _dependency_name_for_import(imported)
                scope_status = _dependency_scope_status(dep_name, scopes["python"], ch.path)
                if scope_status == "scope_review":
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{dep_name} is declared outside the runtime dependency scope", "path": ch.path, "evidence": dep_name})
                elif scope_status == "missing" and dep_name not in patch_declared["python"]:
                    unsupported.add(imported)
                elif dep_name in patch_declared["python"]:
                    unsupported.discard(imported)
                    unsupported.discard(dep_name)
        elif suffix in JS_EXTS:
            for imported in extract_imports_from_text(added, suffix):
                if imported.startswith(".") or imported.startswith("/"):
                    continue
                local_alias = _js_alias_local(imported, files, contents)
                pkg = _js_package_root(imported)
                if pkg in workspace_names or local_alias is True:
                    continue
                if local_alias is None or (local_alias is False and _is_js_alias_specifier(imported)):
                    report.setdefault("uncertainties", []).append({"id": "js_alias_uncertain", "message": f"{imported} could not be resolved safely", "path": ch.path, "evidence": imported})
                    continue
                scope_status = _dependency_scope_status(pkg, scopes["js"], ch.path)
                if scope_status == "scope_review":
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{pkg} is declared outside the runtime dependency scope", "path": ch.path, "evidence": pkg})
                elif scope_status == "missing" and pkg not in patch_declared["js"]:
                    unsupported.add(pkg)
                elif pkg in patch_declared["js"]:
                    unsupported.discard(pkg)
    declared = patch_declared["python"] | patch_declared["js"]
    existing_deps = existing_declared["python"] | existing_declared["js"]
    declared_only = {d for d in declared if d not in existing_deps}
    binary_paths = []
    binary_blockers = []
    for line in patch_text.splitlines():
        if line.startswith("Binary files "):
            m = re.search(r" b/(.+?) differ", line)
            rel = m.group(1) if m else "unknown"
            binary_paths.append(rel)
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


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git executable not found")



def git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    repo = Path(repo)
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return False, "git_unavailable" if cp.returncode == 127 else "not_git"
    root = Path(cp.stdout.strip())
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        diff_cp = run_git(root, list(args))
        if diff_cp.returncode == 1:
            return True, None
        if diff_cp.returncode == 127:
            return False, "git_unavailable"
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0 and untracked.stdout.strip():
        return True, None
    if untracked.returncode == 127:
        return False, "git_unavailable"
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

def baseline_report_fields(status: dict) -> dict:
    return {
        "baseline_state": status.get("state"),
        "baseline_integrity_ok": bool(status.get("ok")) and status.get("state") in {"present", "stale"},
        "baseline_integrity_finding_id": status.get("finding_id"),
        "baseline_integrity_message": status.get("message"),
        "baseline_stale": status.get("state") == "stale",
        "baseline_stale_details": (status.get("details") or {}).get("stale_details"),
        "baseline_mode": status.get("mode"),
        "baseline_packet_path": status.get("packet_path"),
        "baseline_metadata_path": status.get("metadata_path"),
        "baseline_active_pointer_path": status.get("active_pointer_path"),
    }



def untracked_files_as_diff(repo: str | Path) -> str:
    repo = Path(repo)
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    if cp.returncode != 0:
        return ""
    chunks = []
    for rel in [line.strip() for line in cp.stdout.splitlines() if line.strip()]:
        path = repo / rel
        if rel == ".gitignore":
            try:
                ignore_lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
            except OSError:
                ignore_lines = set()
            if ignore_lines <= {".sourcepack", ".sourcepack/"}:
                continue
        safe_rel = rel.replace("\\", "/")
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

def build_repo_change_report(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, ci: bool = False) -> dict:
    repo_arg = Path(repo_path).resolve(); cp = run_git(repo_arg, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found. Run sourcepack prompt or sourcepack baseline for non-git use."
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable" if cp.returncode == 127 else "no_git_repo", "error", "git", message)])
    git_root = Path(cp.stdout.strip()).resolve()
    repo = repo_arg if validate_baseline(repo_arg).get("state") in {"present", "stale", "corrupt"} else git_root
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if added:
        paths.setdefault("gitignore_added", True)
    if err:
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
    if patch_text is None:
        diff_args = ["diff", "--staged"] if staged else ["diff"]
        if repo != git_root:
            diff_args.append("--relative")
        cp = run_git(repo, diff_args); diff_text = cp.stdout
        if cp.returncode == 127:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable", "error", "git", "Git executable not found.")])
        if not staged:
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
            build_current_baseline(repo, quiet=True); baseline_status = validate_baseline(repo)
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
        raw = judge_patch_text(repo / baseline_status["packet_path"], diff_text); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
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


def judge_repo_change(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, policy_mode: PolicyMode | str = PolicyMode.LOCAL) -> Judgment:
    """Judge repository changes without CLI parsing, stdout rendering, or cli.py imports."""
    mode = normalize_policy_mode(policy_mode)
    report = build_repo_change_report(Path(repo_path).resolve(), staged=staged, patch_text=patch_text, ci=(mode is PolicyMode.CI))
    if mode is PolicyMode.CI:
        report["ci"] = True
    return Judgment(str(Path(repo_path).resolve()), mode, report)
