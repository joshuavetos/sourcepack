from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

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
COMMON_DEPENDENCIES = ["fastapi", "flask", "django", "react", "vue", "svelte", "pytest", "typer", "click", "sqlalchemy", "prisma", "pydantic"]
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


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md"]

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


def verify_packet(packet_path: str | Path, against: str | Path | None = None) -> bool:
    packet = Path(packet_path)
    ok = True
    receipt_path = packet / "receipt.json"
    if not receipt_path.exists():
        print("FAIL receipt.json missing")
        return False
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for name, expected in receipt.get("hashes", {}).items():
        path = packet / name
        if not path.exists():
            print(f"FAIL {name} missing")
            ok = False
            continue
        actual = sha256_file(path)
        if actual == expected:
            print(f"PASS {name}")
        else:
            print(f"FAIL {name} hash mismatch")
            ok = False
    if against:
        manifest = load_manifest(packet)
        source = Path(against).resolve()
        included = {rec["relative_path"]: rec for rec in manifest.get("included_files", [])}
        for rel, rec in included.items():
            source_file = source / rel
            if not source_file.exists():
                print(f"FAIL source missing {rel}")
                ok = False
            elif is_probably_binary(source_file):
                print(f"WARN source now binary {rel}")
            else:
                try:
                    content = source_file.read_text(encoding="utf-8")
                except Exception:
                    print(f"FAIL source unreadable {rel}")
                    ok = False
                    continue
                expected_source_hash = rec.get("source_sha256")
                if expected_source_hash is None:
                    expected_source_hash = rec.get("sha256")
                    redacted, _ = redact_secrets(content)
                    content_hash = sha256_text(redacted)
                else:
                    content_hash = sha256_text(content)
                if content_hash != expected_source_hash:
                    print(f"FAIL source changed {rel}")
                    ok = False
        current_files = []
        for root, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in sorted(dirs) if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
            for filename in sorted(files):
                fp = Path(root) / filename
                if filename.startswith(".") or fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    continue
                rel = str(fp.relative_to(source))
                if rel not in included:
                    current_files.append(rel)
        for rel in current_files:
            print(f"WARN new source file not in packet {rel}")
    print("OVERALL", "PASS" if ok else "FAIL")
    return ok


def extract_refs(text: str) -> set[str]:
    refs = set(re.findall(r"[`'\"]([A-Za-z0-9_./\\-]+\.[A-Za-z0-9_./\\-]+|Dockerfile|docker-compose\.yml|compose\.yaml|pyproject\.toml|package\.json)[`'\"]", text))
    refs |= set(re.findall(r"\b(?:src|sourcepack|tests|frontend|backend|docs)/[A-Za-z0-9_./-]+\b", text))
    return {r.replace("\\", "/") for r in refs}


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
            for quoted in re.findall(r"""["']([A-Za-z0-9_.-]+)(?:[<>=!~;\[].*)?["']""", content):
                _add_common_dependency(deps, quoted)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for line in content.splitlines():
                cleaned = line.split("#", 1)[0].strip()
                if cleaned and not cleaned.startswith(("-", "--")):
                    _add_common_dependency(deps, re.split(r"[<>=!~;\[]", cleaned, 1)[0])
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
                _add_common_dependency(deps, imported.split("/", 1)[0])
    return deps


def _has_import(content: str, *modules: str) -> bool:
    module_pattern = "|".join(re.escape(module) for module in modules)
    return bool(re.search(rf"(?m)^\s*(?:import|from)\s+({module_pattern})(?:\b|[._])", content))


PDF_DEPENDENCIES = {"pypdf", "pdfplumber", "fitz", "pymupdf"}


def _declares_pdf_dependency(rel: str, content: str) -> bool:
    name = Path(rel).name.lower()
    if name == "pyproject.toml":
        declared = re.findall(r"""["']([A-Za-z0-9_.-]+)(?:[<>=!~;\[].*)?["']""", content)
        return any(_normalize_dependency_name(dep) in PDF_DEPENDENCIES for dep in declared)
    if name.startswith("requirements") and name.endswith(".txt"):
        for line in content.splitlines():
            cleaned = line.split("#", 1)[0].strip()
            if cleaned and not cleaned.startswith(("-", "--")):
                dep = re.split(r"[<>=!~;\[]", cleaned, 1)[0]
                if _normalize_dependency_name(dep) in PDF_DEPENDENCIES:
                    return True
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


def known_files(manifest: dict) -> set[str]:
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


def extract_imports_from_text(text: str, suffix: str = ".py") -> set[str]:
    imports: set[str] = set()
    if suffix == ".py":
        imports |= set(re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text))
    elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
        
        for m in re.findall(r"""(?:from\s+["']|import\s*\(\s*["']|require\s*\(\s*["'])(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)""", text):
            if m.startswith("@") and "/" in m:
                imports.add(m.lower())
            else:
                imports.add(m.split("/", 1)[0].lower())
    return {i.lower() for i in imports}


@dataclass
class PatchFileChange:
    path: str
    old_path: str | None
    new_file: bool = False
    deleted_file: bool = False
    added_lines: list[str] | None = None


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []
    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None
    new_file = False
    deleted_file = False

    def clean(path: str) -> str:
        path = path.strip().split("\t", 1)[0]
        if path.startswith("a/") or path.startswith("b/"):
            path = path[2:]
        return path

    def flush():
        nonlocal current
        if current is not None:
            changes.append(current)
            current = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush(); old_path = new_path = None; new_file = deleted_file = False
            parts = line.split()
            if len(parts) >= 4:
                old_path = clean(parts[2]); new_path = clean(parts[3])
        elif line.startswith("new file mode"):
            new_file = True
        elif line.startswith("deleted file mode"):
            deleted_file = True
        elif line.startswith("--- "):
            val = line[4:].strip()
            old_path = None if val == "/dev/null" else clean(val)
        elif line.startswith("+++ "):
            val = line[4:].strip()
            new_path = None if val == "/dev/null" else clean(val)
            path = new_path or old_path or ""
            current = PatchFileChange(path=path, old_path=old_path, new_file=new_file or old_path is None, deleted_file=deleted_file or new_path is None, added_lines=[])
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.added_lines.append(line[1:])
    flush()
    return changes


def _dependency_additions_from_patch(changes: list[PatchFileChange]) -> set[str]:
    deps: set[str] = set()
    for ch in changes:
        name = Path(ch.path).name.lower()
        added = "\n".join(ch.added_lines or [])
        if name == "pyproject.toml":
            for quoted in re.findall(r"""["']([A-Za-z0-9_.-]+)(?:[<>=!~;\[].*)?["']""", added):
                _add_common_dependency(deps, quoted)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for line in added.splitlines():
                cleaned = line.split("#", 1)[0].strip()
                if cleaned and not cleaned.startswith(("-", "--")):
                    _add_common_dependency(deps, re.split(r"[<>=!~;\[]", cleaned, 1)[0])
        elif name == "package.json":
            for dep in COMMON_DEPENDENCIES:
                if re.search(rf'"{re.escape(dep)}"\s*:', added, re.I):
                    deps.add(dep)
    return deps


def analyze_patch(packet_path: str | Path, patch_text: str) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    reality = json.loads((packet / "reality_map.json").read_text(encoding="utf-8")) if (packet / "reality_map.json").exists() else generate_reality_map(manifest, packet)
    files = known_files(manifest)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    changes = parse_unified_diff(patch_text)
    patch_deps = _dependency_additions_from_patch(changes)
    report = {
        "patch_judgment_schema_version": "1.0",
        "verdict": "PASS",
        "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [],
        "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [],
    }
    all_added = []
    for ch in changes:
        report["modified_files"].append(ch.path)
        if ch.new_file:
            report["new_files"].append(ch.path)
        elif ch.path not in files:
            report["missing_modified_files"].append(ch.path)
        if ch.deleted_file:
            report["deleted_files"].append(ch.path)
        if ch.path in PROTECTED_PACKET_ARTIFACTS:
            report["protected_artifact_modifications"].append(ch.path)
        added = "\n".join(ch.added_lines or [])
        all_added.append(added)
        for imported in extract_imports_from_text(added, Path(ch.path).suffix.lower()):
            for dep in COMMON_DEPENDENCIES:
                if _normalize_dependency_name(imported) == _normalize_dependency_name(dep) and dep not in deps and dep not in patch_deps:
                    report["unsupported_dependencies"].append(dep)
    added_text = "\n".join(all_added)
    supported = supported_commands_inventory(reality)
    if re.search(r"docker\s+compose\s+up", added_text, re.I):
        evidence = docker_evidence(files)
        if "docker compose up" not in supported or not evidence["compose"]:
            report["unsupported_commands"].append("docker compose up")
    for cmd in sorted(set(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))):
        normalized = cmd if cmd == "npm test" else cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append(normalized)
    if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
        py = python_project_evidence(files, deps)
        if not (py["pytest"] or py["tests"] or "pytest" in supported):
            report["unsupported_commands"].append("pytest")
    if report["new_files"]:
        report["warnings"].append("Patch creates new files that were not part of the original packet reality.")
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications"]
    if any(report[k] for k in fail_keys):
        report["verdict"] = "FAIL"
    elif report["new_files"] or report["warnings"]:
        report["verdict"] = "WARN"
    for key in ["modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "warnings"]:
        report[key] = sorted(set(report[key]))
    return report


def render_patch_judgment_report(report: dict) -> str:
    lines = ["# SourcePack Patch Judgment Report", "", f"Verdict: {report['verdict']}", ""]
    sections = [("modified_files", "Modified Files"), ("missing_modified_files", "Missing Modified Files"), ("new_files", "New Files"), ("deleted_files", "Deleted Files"), ("unsupported_dependencies", "Unsupported Dependencies"), ("unsupported_commands", "Unsupported Commands"), ("protected_artifact_modifications", "Protected Packet Artifact Modifications"), ("warnings", "Warnings")]
    for key, title in sections:
        lines.extend([f"## {title}"])
        lines.extend([f"- {item}" for item in report.get(key, [])] or ["None"])
        lines.append("")
    return "\n".join(lines)


def judge_patch(packet_path: str | Path, patch_path: str | Path, out_dir: str | Path) -> dict:
    patch_text = Path(patch_path).read_text(encoding="utf-8")
    report = analyze_patch(packet_path, patch_text)
    text = render_patch_judgment_report(report)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "patch_judgment_report.md").write_text(text, encoding="utf-8")
    (out / "patch_judgment_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(text)
    return report

def judge_ai_answer(packet_path: str | Path, ai_answer_path: str | Path, out_dir: str | Path | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    known_files = {rec["relative_path"] for rec in manifest.get("included_files", [])}
    ai_text = Path(ai_answer_path).read_text(encoding="utf-8")
    refs = extract_refs(ai_text)
    deps = dependency_inventory(manifest, packet)
    report = {"supported_files": [], "missing_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "unsupported_capabilities": []}
    for ref in sorted(refs):
        if ref in known_files:
            report["supported_files"].append(ref)
        else:
            report["missing_files"].append(ref)
    for dep in COMMON_DEPENDENCIES:
        if re.search(rf"(?i)\b{re.escape(dep)}\b", ai_text) and dep.lower() not in deps:
            if dep.lower() not in {"pytest"} or not any("tests/" in f for f in known_files):
                report["unsupported_dependencies"].append(dep)
    command_patterns = {
        "docker compose up": ["Dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"],
        "npm run dev": ["package.json"],
        "npm test": ["package.json"],
        "pytest": ["pyproject.toml", "pytest.ini"],
    }
    for cmd, evidence in command_patterns.items():
        if re.search(re.escape(cmd), ai_text, re.I):
            if not any(ev in known_files or any(k.endswith(ev) for k in known_files) for ev in evidence):
                report["unsupported_commands"].append(cmd)
    lower_text = ai_text.lower()
    supported_features = feature_inventory(manifest, packet, deps)
    for feature in FEATURE_NAMES:
        if feature in lower_text and feature not in supported_features:
            report["unsupported_capabilities"].append(feature)
    lines = ["# SourcePack Judgment Report", "", "Verdict: " + ("FAIL" if any(report[k] for k in ["missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"]) else "PASS"), ""]
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


LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PY_STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"typing", "pathlib", "json", "os", "sys", "re", "subprocess", "datetime", "unittest"}
PY_DEP_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}


def sourcepack_paths(repo: str | Path) -> dict[str, Path]:
    root = Path(repo).resolve()
    base = root / ".sourcepack"
    baseline = base / "baseline"
    prompt = base / "prompt"
    reports = base / "reports"
    return {
        "root": root,
        "base": base,
        "current": base / "current",  # legacy compatibility marker only
        "baseline": baseline,
        "packet": baseline / "packet",
        "baseline_meta": baseline / "metadata.json",
        "prompt_dir": prompt,
        "prompt_packet": prompt / "packet",
        "prompt_reality": prompt / "reality_map.json",
        "prompt_instructions": prompt / "ai_instructions.md",
        "reports": reports,
        "archive": reports / "archive",
        "reality": baseline / "reality_map.json",
        "instructions": baseline / "ai_instructions.md",
        "prompt": prompt / "prompt.md",
        "state": base / "state",
        "stale_marker": base / "state" / "baseline_stale.json",
        "latest_json": reports / "latest.json",
        "latest_md": reports / "latest.md",
        "latest_diff_json": reports / "latest_diff.json",
        "latest_prompt_json": reports / "latest_prompt.json",
        "latest_baseline_json": reports / "latest_baseline.json",
    }


def ensure_sourcepack_dirs(repo: str | Path) -> dict[str, Path]:
    paths = sourcepack_paths(repo)
    paths["baseline"].mkdir(parents=True, exist_ok=True)
    paths["prompt_dir"].mkdir(parents=True, exist_ok=True)
    paths["current"].mkdir(parents=True, exist_ok=True)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    paths["archive"].mkdir(parents=True, exist_ok=True)
    paths["state"].mkdir(parents=True, exist_ok=True)
    return paths


def ensure_gitignore_entry(repo: str | Path) -> tuple[bool, str | None]:
    path = Path(repo) / ".gitignore"
    try:
        if not path.exists():
            path.write_text(".sourcepack/\n", encoding="utf-8")
            return True, None
        data = path.read_bytes()
        text = data.decode("utf-8")
        if any(line.strip() in {".sourcepack", ".sourcepack/"} for line in text.splitlines()):
            return False, None
        newline = "\r\n" if b"\r\n" in data else "\n"
        addition = ("" if text.endswith(("\n", "\r\n")) or not text else newline) + ".sourcepack/" + newline
        path.write_text(text + addition, encoding="utf-8", newline="")
        return True, None
    except Exception as exc:
        return False, str(exc)


def normalized_finding(fid: str, severity: str, category: str, message: str, path: str | None = None, evidence: str | None = None, suggestion: str | None = None) -> dict:
    return {"id": fid, "severity": severity, "category": category, "path": path, "message": message, "evidence": evidence, "suggestion": suggestion}


def traffic_report(verdict: str, headline: str | None = None, findings: list[dict] | None = None, checked_categories: list[str] | None = None, next_action: str | None = None, report_path: str = ".sourcepack/reports/latest.json", reason_type: str | None = None, not_checked: list[str] | None = None) -> dict:
    findings = sorted(findings or [], key=lambda f: (SEVERITY_ORDER.get(f.get("severity", "info"), 9), f.get("id", ""), f.get("path") or ""))
    blockers = [f for f in findings if f.get("severity") == "error"]
    warnings = [f for f in findings if f.get("severity") == "warn"]
    light = LIGHT_BY_VERDICT.get(verdict, "YELLOW LIGHT")
    headline = headline or {"PASS": "good to continue.", "WARN": "review before continuing.", "FAIL": "stop before trusting this output."}.get(verdict, "review before continuing.")
    next_action = next_action or ("ask the AI to revise using only files, dependencies, and commands confirmed by SourcePack." if verdict == "FAIL" else "review the listed items before continuing." if verdict == "WARN" else "continue.")
    if reason_type is None:
        reason_type = "blocker" if verdict == "FAIL" else "review" if warnings else "none"
        if any(f.get("category") in {"uncertainty", "tooling"} for f in warnings):
            reason_type = "uncertainty" if any(f.get("category") == "uncertainty" for f in warnings) else "tooling"
    return {"verdict": verdict, "light": light, "headline": headline, "reason_type": reason_type, "blockers": blockers, "warnings": warnings, "checked_categories": checked_categories or [], "not_checked": not_checked or ["runtime behavior", "semantic correctness", "security", "external services"], "next_action": next_action, "report_path": report_path, "findings": findings}


def render_traffic(report: dict, verbose: bool = False) -> str:
    verdict = report.get("verdict", "WARN")
    lines = [f"{report.get('light', LIGHT_BY_VERDICT.get(verdict, 'YELLOW LIGHT'))}: {report.get('headline', '')}", ""]
    if report.get("reason_type") and verdict != "PASS":
        lines.append(f"Reason type: {report.get('reason_type')}")
        lines.append("")
    if verdict == "PASS":
        info = [f for f in report.get("findings", []) if f.get("severity") == "info"]
        lines.append(info[0]["message"] if info else "No unsupported project claims or patch assumptions detected.")
        if report.get("checked_categories"):
            lines.extend(["", "Checked:", ""])
            lines.extend(f"- {item}" for item in report.get("checked_categories", []))
        if report.get("not_checked"):
            lines.extend(["", "Not checked:", ""])
            lines.extend(f"- {item}" for item in report.get("not_checked", []))
    elif verdict == "WARN":
        lines.append("SourcePack found new or uncertain items, but no clear unsupported blocker.")
        lines.extend(["", "Warnings:", ""])
        shown = report.get("warnings", []) if verbose else report.get("warnings", [])[:3]
        lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    else:
        lines.append("SourcePack found missing files, unsupported dependencies, unsupported commands, or unsupported capabilities.")
        lines.extend(["", "Blockers:", ""])
        shown = report.get("blockers", []) if verbose else report.get("blockers", [])[:3]
        lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    lines.extend(["", f"Report: {report.get('report_path', '.sourcepack/reports/latest.json')}"])
    return "\n".join(lines) + "\n"


def write_user_report(repo: str | Path, report: dict, stem: str = "report") -> None:
    paths = ensure_sourcepack_dirs(repo)
    full = dict(report)
    full.setdefault("sourcepack_version", __version__)
    full.setdefault("schema_version", "traffic_report.v1")
    full["generated_at"] = utc_now()
    paths["latest_json"].write_text(json.dumps(full, indent=2), encoding="utf-8")
    paths["latest_md"].write_text(render_traffic(report, verbose=True), encoding="utf-8")
    typed = paths.get(f"latest_{stem}_json")
    if typed is not None:
        typed.write_text(json.dumps(full, indent=2), encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (paths["archive"] / f"{ts}_{stem}.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
    (paths["archive"] / f"{ts}_{stem}.md").write_text(render_traffic(report, verbose=True), encoding="utf-8")


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


def build_current_baseline(repo: str | Path, quiet: bool = False) -> tuple[dict, bool]:
    paths = ensure_sourcepack_dirs(repo)
    created = not (paths["packet"] / "manifest.json").exists()
    PacketWriter(paths["packet"], SourceScanner(repo).scan(), force=True).write_all()
    shutil.copy2(paths["packet"] / "reality_map.json", paths["reality"])
    shutil.copy2(paths["packet"] / "ai_instructions.md", paths["instructions"])
    if not quiet and not verify_packet(paths["packet"]):
        raise RuntimeError("packet verification returned FAIL")
    elif quiet:
        receipt = paths["packet"] / "receipt.json"
        if not receipt.exists():
            raise RuntimeError("packet verification returned FAIL")
    meta = {"created_at": utc_now(), "packet_path": str(paths["packet"]), "scanner_config_hash": scanner_config_hash(), **git_metadata(repo)}
    paths["baseline_meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if paths["stale_marker"].exists():
        paths["stale_marker"].unlink()
    return paths, created


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
    deps: set[str] = set()
    active_section: str | None = None
    section_depth: int | None = None
    depth = 0
    for line in lines:
        stripped = line.strip()
        section_match = re.match(r'"(dependencies|devDependencies|peerDependencies|optionalDependencies)"\s*:\s*\{', stripped)
        if section_match:
            active_section = section_match.group(1)
            section_depth = depth + stripped.count("{") - stripped.count("}")
            depth += stripped.count("{") - stripped.count("}")
            continue
        if active_section:
            dep_match = re.match(r'"(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)"\s*:', stripped)
            if dep_match and dep_match.group(1) not in JS_DEP_SECTIONS:
                deps.add(dep_match.group(1).lower())
        depth += stripped.count("{") - stripped.count("}")
        if active_section and section_depth is not None and depth < section_depth:
            active_section = None
            section_depth = None
    return deps


def _declared_dependency_names_from_patch(changes: list[PatchFileChange]) -> set[str]:
    deps = set(_dependency_additions_from_patch(changes))
    for ch in changes:
        added = "\n".join(ch.added_lines or [])
        name = Path(ch.path).name.lower()
        if name == "package.json":
            deps |= _package_json_declared_deps_from_added_lines(ch.added_lines or [])
        elif name in PY_DEP_FILES or (name.startswith("requirements") and name.endswith(".txt")):
            for line in added.splitlines():
                cleaned = line.split("#", 1)[0].strip().strip('"\' ,')
                if cleaned and not cleaned.startswith(("-", "[")):
                    deps.add(_normalize_dependency_name(re.split(r"[<>=!~;\[]", cleaned, 1)[0]))
    return deps


def judge_patch_text(packet_path: str | Path, patch_text: str) -> dict:
    report = analyze_patch(packet_path, patch_text)
    packet = Path(packet_path); manifest = load_manifest(packet); files = known_files(manifest); deps = dependency_inventory(manifest, packet)
    changes = parse_unified_diff(patch_text); declared = _declared_dependency_names_from_patch(changes)
    unsupported = set(report.get("unsupported_dependencies", []))
    for ch in changes:
        suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
        if suffix == ".py":
            for imported in extract_imports_from_text(added, suffix):
                if imported in PY_STDLIB or imported.startswith(".") or _is_local_python_import(imported, ch.path, files):
                    continue
                norm = _normalize_dependency_name(imported)
                if norm not in deps and norm not in declared:
                    unsupported.add(imported)
        elif suffix in JS_EXTS:
            for imported in extract_imports_from_text(added, suffix):
                if imported.startswith(".") or imported.startswith("/"):
                    continue
                if imported.lower() not in deps and imported.lower() not in declared:
                    unsupported.add(imported)
    declared_only = {d for d in declared if d not in deps}
    unsupported_ecosystems = []
    baseline_names = {Path(f).name.lower() for f in files}
    patch_names = {Path(ch.path).name.lower() for ch in changes}
    if "cargo.toml" in baseline_names or "cargo.toml" in patch_names:
        unsupported_ecosystems.append("unsupported_ecosystem: Cargo.toml detected, but Rust dependency validation is not implemented")
    if unsupported_ecosystems:
        report["uncertainties"] = sorted(set(report.get("uncertainties", []) + unsupported_ecosystems))
    report["unsupported_dependencies"] = sorted(unsupported)
    if declared_only:
        report.setdefault("warnings", []).append("Patch declares new dependencies that require review.")
        report["declared_dependencies"] = sorted(declared_only)
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications"]
    report["verdict"] = "FAIL" if any(report.get(k) for k in fail_keys) else "WARN" if (report.get("new_files") or report.get("deleted_files") or report.get("warnings") or declared_only or report.get("uncertainties")) else "PASS"
    return report


def patch_report_to_traffic(report: dict, report_path: str = ".sourcepack/reports/latest.json") -> dict:
    findings=[]
    for p in report.get("missing_modified_files", []): findings.append(normalized_finding("missing_file", "error", "file", f"{p} not found in the trusted baseline.", p, suggestion="Restore the file, create it as a new file, or refresh the baseline only after accepting the current repo state."))
    for d in report.get("unsupported_dependencies", []): findings.append(normalized_finding("unsupported_dependency", "error", "dependency", f"{d} is imported but not declared in scanned dependency files.", evidence=d, suggestion=f"Either remove {d} usage or add it intentionally to the appropriate dependency manifest."))
    for c in report.get("unsupported_commands", []): findings.append(normalized_finding("unsupported_command", "error", "command", f"{c} is not supported by project evidence.", evidence=c, suggestion="Use a detected supported command or add the project file that defines this command."))
    for p in report.get("protected_artifact_modifications", []): findings.append(normalized_finding("protected_artifact", "error", "artifact", f"{p} is a protected SourcePack packet artifact.", p))
    for p in report.get("new_files", []): findings.append(normalized_finding("new_file", "warn", "review", f"{p} was created by the patch.", p))
    for p in report.get("deleted_files", []): findings.append(normalized_finding("deleted_file", "warn", "review", f"{p} was deleted by the patch.", p))
    for d in report.get("declared_dependencies", []): findings.append(normalized_finding("declared_dependency", "warn", "review", f"{d} was added to dependency files.", evidence=d))
    for w in report.get("uncertainties", []): findings.append(normalized_finding(w, "warn", "uncertainty", f"{w}: SourcePack could not fully evaluate this change."))
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
    repo = Path(args.repo).resolve(); dirty, dirty_state = git_worktree_dirty(repo); paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("gitignore_unwritable","error","git",f"Cannot write .gitignore: {err}")]); print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    existed = (paths["packet"] / "manifest.json").exists()
    try:
        build_current_baseline(repo, quiet=getattr(args, "quiet", False)); refreshed = existed or args.refresh
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
    except Exception as exc:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("baseline_failed","error","baseline",f"Baseline verification failed: {exc}")]); write_user_report(repo, rep, "baseline")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1

def cli_diff(args) -> int:
    repo_arg = Path(args.repo).resolve(); cp = run_git(repo_arg, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found. Run sourcepack prompt or sourcepack baseline for non-git use."
        rep=traffic_report("FAIL","stop before trusting this output.",[normalized_finding("git_unavailable" if cp.returncode == 127 else "no_git_repo","error","git",message)])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    git_root = Path(cp.stdout.strip()).resolve()
    candidate_paths = sourcepack_paths(repo_arg)
    repo = repo_arg if (candidate_paths["packet"] / "manifest.json").exists() else git_root
    paths = ensure_sourcepack_dirs(repo); note = None; added, err = ensure_gitignore_entry(repo)
    if err:
        rep=traffic_report("FAIL","stop before trusting this output.",[normalized_finding("gitignore_unwritable","error","git",f"Cannot write .gitignore: {err}")]); print(render_traffic(rep,args.verbose), end=""); return 1
    diff_args = ["diff", "--staged"] if args.staged else ["diff"]
    if 'git_root' in locals() and repo != git_root:
        diff_args.append("--relative")
    cp = run_git(repo, diff_args); diff_text = cp.stdout
    if cp.returncode == 127:
        rep=traffic_report("FAIL","stop before trusting this output.",[normalized_finding("git_unavailable","error","git","Git executable not found.")]); print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    if not args.staged:
        extra = untracked_files_as_diff(repo)
        if extra:
            diff_text = (diff_text + "\n" + extra).strip() + "\n"
    if not (paths["packet"] / "manifest.json").exists():
        if diff_text.strip():
            rep=traffic_report("FAIL","baseline missing while changes are present.",[normalized_finding("baseline_missing","error","baseline","No baseline exists. Run sourcepack baseline before AI edits, or run sourcepack baseline --refresh to accept current repo state.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            write_user_report(repo, rep, "diff")
            print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
        try: build_current_baseline(repo); note = "Created SourcePack baseline because none existed and no diff was present."
        except Exception as exc:
            rep=traffic_report("FAIL","stop before trusting this output.",[normalized_finding("baseline_failed","error","baseline",f"Baseline verification failed: {exc}")]); print(render_traffic(rep,args.verbose), end=""); return 1
    stale_findings = []
    if paths["stale_marker"].exists():
        stale_findings.append(normalized_finding("baseline_stale", "warn", "uncertainty", "baseline_stale: trusted baseline may not match current HEAD."))
    if not diff_text.strip():
        verdict = "WARN" if stale_findings else "PASS"
        rep=traffic_report(verdict,"SourcePack could not fully evaluate this change." if stale_findings else "good to continue.",[normalized_finding("no_diff","info","diff","No uncommitted changes detected."), *stale_findings], ["diff", "baseline freshness"])
    else:
        raw = judge_patch_text(paths["packet"], diff_text); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
        if stale_findings and rep["verdict"] != "FAIL":
            rep = traffic_report("WARN", "SourcePack could not fully evaluate this change.", rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action"), reason_type="uncertainty")
            rep["raw_patch_judgment"] = raw
    if paths["baseline_meta"].exists():
        try:
            rep["baseline"] = json.loads(paths["baseline_meta"].read_text(encoding="utf-8"))
        except Exception:
            pass
    rep["current_git"] = git_metadata(repo)
    write_user_report(repo, rep, "diff")
    if args.json: print(json.dumps(rep, indent=2)); return 0 if rep["verdict"] != "FAIL" else 1
    if added: print("Added .sourcepack/ to .gitignore.")
    if note: print(note)
    print(render_traffic(rep, args.verbose), end="")
    return 0 if rep["verdict"] != "FAIL" else 1



def untracked_files_as_diff(repo: Path) -> str:
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"]); parts=[]
    if cp.returncode != 0: return ""
    for rel in cp.stdout.splitlines():
        path = repo / rel
        if not path.is_file() or is_probably_binary(path):
            continue
        try: content = path.read_text(encoding="utf-8")
        except Exception: continue
        lines = [f"diff --git a/{rel} b/{rel}", "new file mode 100644", "--- /dev/null", f"+++ b/{rel}", f"@@ -0,0 +1,{len(content.splitlines())} @@"]
        lines.extend("+" + line for line in content.splitlines())
        parts.append("\n".join(lines))
    return "\n".join(parts)

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
if git diff --quiet && git diff --staged --quiet; then
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
orig="$(git rev-parse --git-path hooks/pre-commit.sourcepack.orig 2>/dev/null)"
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
    current=paths["base"].exists(); baseline=(paths["packet"] / "manifest.json").exists(); receipt=paths["packet"] / "receipt.json"; last=None
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
    stale = paths["stale_marker"].exists()
    stale_data = None
    if stale:
        try: stale_data=json.loads(paths["stale_marker"].read_text(encoding="utf-8"))
        except Exception: stale_data={"reason":"unreadable"}
    prompt_exists = paths["prompt"].exists()
    automatic = current and baseline and hook_installed and post_hook_installed and ignored
    data={"automatic_mode_enabled":automatic,"local_storage_exists":current,"baseline_exists":baseline,"baseline_stale":stale,"baseline_stale_details":stale_data,"prompt_context_exists":prompt_exists,"pre_commit_hook_installed":hook_installed,"post_commit_hook_installed":post_hook_installed,"hook_strict_mode":strict,"hook_policy":"RED blocks, YELLOW blocks" if strict else "RED blocks, YELLOW warns","sourcepack_gitignored":ignored,"last_report_verdict":last_report,"last_report_light":last_light,"dirty_worktree":dirty if dirty_state is None else None,"git_repo":git_repo,"last_baseline_update":last}
    if args.json: print(json.dumps(data, indent=2)); return 0
    print(f"SourcePack status for {repo}\n")
    print(f"Automatic mode: {'enabled' if automatic else 'not enabled'}")
    print(f"Baseline: {'present' if baseline else 'missing'}" + (" (stale)" if stale else ""))
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



def write_auto_report(repo: Path, report: dict, details: dict) -> None:
    payload = dict(report)
    payload.update(details)
    write_user_report(repo, payload, "auto")


def cli_init(args) -> int:
    repo = Path(args.path).resolve()
    if not getattr(args, "auto", False):
        init_workspace(repo)
        return 0
    initial_dirty, initial_dirty_state = git_worktree_dirty(repo)
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
    baseline_exists = (paths["packet"] / "manifest.json").exists()
    if args.refresh_baseline or (not baseline_exists and not dirty):
        try:
            _, created = build_current_baseline(repo)
            details["baseline_created"] = created
            details["baseline_refreshed"] = not created or args.refresh_baseline
            if dirty:
                findings.append(normalized_finding("dirty_worktree", "warn", "baseline", "dirty_worktree: baseline includes current uncommitted changes."))
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

def doctor() -> bool:
    print("--- SourcePack Health Check ---")
    print(f"Version: {__version__}")
    print(f"Python: {platform.python_version()}")
    print(f"Platform: {platform.platform()}")
    print(f"Secret signatures: {len(SECRET_PATTERNS)}")
    print("Status: READY")
    return True


def run_cli(args_list=None):
    parser = argparse.ArgumentParser(prog="sourcepack")
    parser.add_argument("--version", action="store_true")
    subs = parser.add_subparsers(dest="command")
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
    judge_patch_cmd = subs.add_parser("judge-patch")
    judge_patch_cmd.add_argument("packet")
    judge_patch_cmd.add_argument("patch")
    judge_patch_cmd.add_argument("--out", required=True)
    map_cmd = subs.add_parser("map")
    map_cmd.add_argument("input")
    map_cmd.add_argument("--out", required=True)
    instr = subs.add_parser("instructions")
    instr.add_argument("packet")
    subs.add_parser("demo")
    init = subs.add_parser("init")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--auto", action="store_true")
    init.add_argument("--strict", action="store_true")
    init.add_argument("--no-hook", action="store_true")
    init.add_argument("--refresh-baseline", action="store_true")
    init.add_argument("--install-hygiene-hooks", action="store_true")
    init.add_argument("--json", action="store_true")
    subs.add_parser("doctor")
    prompt_cmd = subs.add_parser("prompt")
    prompt_cmd.add_argument("repo")
    prompt_cmd.add_argument("task", nargs="?")
    prompt_cmd.add_argument("--copy", action="store_true")
    prompt_cmd.add_argument("--verbose", action="store_true")
    prompt_cmd.add_argument("--json", action="store_true")
    baseline_cmd = subs.add_parser("baseline")
    baseline_cmd.add_argument("repo")
    baseline_cmd.add_argument("--refresh", action="store_true")
    baseline_cmd.add_argument("--verbose", action="store_true")
    baseline_cmd.add_argument("--json", action="store_true")
    baseline_cmd.add_argument("--quiet", action="store_true")
    diff_cmd = subs.add_parser("diff")
    diff_cmd.add_argument("repo")
    diff_cmd.add_argument("--staged", action="store_true")
    diff_cmd.add_argument("--verbose", action="store_true")
    diff_cmd.add_argument("--json", action="store_true")
    install_hook = subs.add_parser("install-hook")
    install_hook.add_argument("repo")
    install_hook.add_argument("--strict", action="store_true")
    uninstall_hook = subs.add_parser("uninstall-hook")
    uninstall_hook.add_argument("repo")
    status_cmd = subs.add_parser("status")
    status_cmd.add_argument("repo")
    status_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(args_list)
    if args.version:
        print(__version__); return 0
    try:
        if args.command == "doctor":
            doctor(); return 0
        if args.command == "init":
            return cli_init(args)
        if args.command == "prompt":
            return cli_prompt(args)
        if args.command == "baseline":
            return cli_baseline(args)
        if args.command == "diff":
            return cli_diff(args)
        if args.command == "install-hook":
            return cli_install_hook(args)
        if args.command == "uninstall-hook":
            return cli_uninstall_hook(args)
        if args.command == "status":
            return cli_status(args)
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
            demo_repo = Path("examples/demo_repo")
            fake_answer = Path("examples/fake_ai_answer.md")
            if not demo_repo.exists() or not fake_answer.exists():
                print("ERROR: examples/demo_repo and examples/fake_ai_answer.md are required", file=sys.stderr); return 1
            tmp = Path(tempfile.mkdtemp(prefix="sourcepack_demo_"))
            packet = tmp / "packet"
            judgment = tmp / "judgment"
            PacketWriter(packet, SourceScanner(demo_repo).scan(), force=True).write_all()
            if not verify_packet(packet): return 1
            judge_ai_answer(packet, fake_answer, judgment)
            fake_patch = Path("examples/fake_ai_patch.diff")
            if fake_patch.exists():
                patch_judgment = tmp / "patch_judgment"
                judge_patch(packet, fake_patch, patch_judgment)
                print(f"Demo patch judgment: {patch_judgment}")
            print(f"Demo packet: {packet}")
            print(f"Demo judgment: {judgment}")
            return 0
        if args.command == "verify":
            return 0 if verify_packet(args.packet, args.against) else 1
        if args.command == "judge":
            judge_ai_answer(args.packet, args.ai_answer, args.out); return 0
        if args.command == "judge-patch":
            judge_patch(args.packet, args.patch, args.out); return 0
        parser.print_help(); return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
