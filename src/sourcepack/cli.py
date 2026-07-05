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
import webbrowser
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape
from .ecosystems.python import PY_IMPORT_ALIASES
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.html import render_report_html
from .reports.json import normalized_finding, traffic_report, write_user_report
from .reports.markdown import LIGHT_BY_VERDICT, SEVERITY_ORDER, render_traffic
from .execution_ledger import clear_ledger, entry_to_json, execution_findings, iter_entries, run_and_record, find_repo_root
from .policy import validate_policy_config
from .replay import reconstruct_replay, render_replay_human

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


@dataclass
class PatchFileChange:
    path: str
    old_path: str | None
    new_file: bool = False
    deleted_file: bool = False
    added_lines: list[str] | None = None
    diff_lines: list[str] | None = None
    unsafe_path: bool = False
    operation: str = "modify"


def _normalize_diff_path(path: str) -> tuple[str, bool]:
    raw = path.strip().replace("\\", "/")
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    if not raw or raw in {"a/", "b/"}:
        return raw, True
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        return raw, True
    parts: list[str] = []
    unsafe = False
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                unsafe = True
            else:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts), unsafe


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []
    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None
    new_file = False
    deleted_file = False
    operation = "modify"

    malformed = False

    def clean(path: str) -> tuple[str, bool]:
        path = path.strip().split("\t", 1)[0]
        return _normalize_diff_path(path)

    def flush():
        nonlocal current
        if current is not None:
            changes.append(current)
            current = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush(); old_path = new_path = None; new_file = deleted_file = False; operation = "modify"
            parts = line.split()
            if len(parts) >= 4:
                old_path, old_unsafe = clean(parts[2]); new_path, new_unsafe = clean(parts[3])
                if old_unsafe or new_unsafe:
                    malformed = True
            else:
                malformed = True
        elif line.startswith("new file mode"):
            new_file = True
        elif line.startswith("deleted file mode"):
            deleted_file = True
        elif line.startswith("rename from "):
            old_path, unsafe = clean(line.removeprefix("rename from "))
            operation = "rename"
            malformed = malformed or unsafe
        elif line.startswith("rename to "):
            new_path, unsafe = clean(line.removeprefix("rename to "))
            operation = "rename"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=False, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("copy from "):
            old_path, unsafe = clean(line.removeprefix("copy from "))
            operation = "copy"
            malformed = malformed or unsafe
        elif line.startswith("copy to "):
            new_path, unsafe = clean(line.removeprefix("copy to "))
            operation = "copy"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=True, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("--- "):
            val = line[4:].strip()
            if val == "/dev/null":
                old_path = None
            else:
                old_path, unsafe = clean(val)
                malformed = malformed or unsafe
        elif line.startswith("+++ "):
            val = line[4:].strip()
            if val == "/dev/null":
                new_path = None
                unsafe = False
            else:
                new_path, unsafe = clean(val)
            malformed = malformed or unsafe
            path = new_path or old_path or ""
            current = PatchFileChange(path=path, old_path=old_path, new_file=new_file or old_path is None, deleted_file=deleted_file or new_path is None, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("@@ ") and current is None:
            malformed = True
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.added_lines.append(line[1:])
            current.diff_lines.append(line)
        elif current is not None and (line.startswith("-") or line.startswith(" ") or line.startswith("@@")):
            current.diff_lines.append(line)
    flush()
    if malformed:
        changes.append(PatchFileChange(path="", old_path=None, added_lines=[], diff_lines=[], unsafe_path=True))
    return changes


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


def judge_ai_answer(packet_path: str | Path, ai_answer_path: str | Path, out_dir: str | Path | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    known_files = {rec["relative_path"] for rec in manifest.get("included_files", [])}
    ai_text = Path(ai_answer_path).read_text(encoding="utf-8")
    refs = extract_refs(ai_text)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    files_lower = {f.lower() for f in known_files}
    report = {"sourcepack_version": __version__, "supported_files": [], "missing_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "unsupported_capabilities": []}
    for ref in sorted(refs):
        if ref in known_files:
            report["supported_files"].append(ref)
        else:
            report["missing_files"].append(ref)
    for dep in COMMON_DEPENDENCIES:
        dep_norm = dep.lower()
        action = _ai_js_dependency_actions(ai_text, dep_norm) if dep_norm in {"react", "vue", "svelte", "prisma"} else _ai_dependency_actions(ai_text, dep_norm)
        if action and dep_norm not in deps:
            if dep_norm != "pytest" or not any(f.startswith("tests/") for f in known_files):
                report["unsupported_dependencies"].append(dep)
    if _ai_command_instructions(ai_text, r"docker\s+compose\s+up"):
        if not any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in known_files):
            report["unsupported_commands"].append("docker compose up")
    for cmd in sorted(set(_ai_command_instructions(ai_text, r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+"))):
        normalized = cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append("npm test")
    if _ai_command_instructions(ai_text, r"(?:python\s+-m\s+pytest|pytest)"):
        if not ({"pyproject.toml", "pytest.ini"} & files_lower or any(f.startswith("tests/") for f in known_files) or "pytest" in deps):
            report["unsupported_commands"].append("pytest")
    lower_text = ai_text.lower()
    supported_features = feature_inventory(manifest, packet, deps)
    for feature in FEATURE_NAMES:
        for m in re.finditer(rf"\b{re.escape(feature)}\b", lower_text):
            if feature not in supported_features and not _has_negation_before(lower_text, m.start()):
                report["unsupported_capabilities"].append(feature)
                break
    report["unsupported_dependencies"] = sorted(set(report["unsupported_dependencies"]))
    report["unsupported_commands"] = sorted(set(report["unsupported_commands"]))
    report["unsupported_capabilities"] = sorted(set(report["unsupported_capabilities"]))
    report["verdict"] = "FAIL" if any(report[k] for k in ["missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"]) else "PASS"
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


LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PY_STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"typing", "pathlib", "json", "os", "sys", "re", "subprocess", "datetime", "unittest"}
PY_DEP_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}



def _latest_report_html_path(repo: str | Path) -> Path:
    return ensure_sourcepack_dirs(repo)["latest_html"]


def cli_report_path(args) -> int:
    print(_latest_report_html_path(Path(args.repo).resolve()))
    return 0


def cli_report_open(args) -> int:
    repo = Path(args.repo).resolve()
    paths = ensure_sourcepack_dirs(repo)
    if not paths["latest_json"].exists():
        print(f"ERROR: no SourcePack report found at {paths['latest_json']}", file=sys.stderr)
        return 1
    try:
        report = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        paths["latest_html"].write_text(render_report_html(report), encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: could not prepare SourcePack HTML report at {paths['latest_html']}: {exc}", file=sys.stderr)
        return 1
    uri = paths["latest_html"].resolve().as_uri()
    opened = webbrowser.open(uri)
    print(f"Report HTML: {paths['latest_html']}")
    if not opened:
        print("Browser open was not confirmed; open the path above manually.")
    return 0


def finalize_diff_report(repo: str | Path | None, report: dict, args, stem: str = "diff") -> dict:
    full = dict(report)
    if getattr(args, "ci", False):
        full["ci"] = True
    if repo is not None:
        try:
            write_user_report(repo, full, stem)
        except Exception as exc:
            print(f"WARNING: could not write SourcePack report artifacts: {exc}", file=sys.stderr)
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
    return 0 if (verdict == "PASS" or (verdict == "WARN" and not (getattr(args, "strict", False) or getattr(args, "ci", False)))) else 1

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


DIRTY_BASELINE_REFUSAL = "SourcePack refused to create a trusted baseline from a dirty working tree. Review, commit, or stash current changes first, or rerun with --force only if this state should become trusted."


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None, force: bool = False) -> tuple[dict, bool]:
    repo = Path(repo).resolve()
    dirty, dirty_state = git_worktree_dirty(repo)
    if dirty and not force:
        raise RuntimeError(DIRTY_BASELINE_REFUSAL)
    paths = ensure_sourcepack_dirs(repo)
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
                if _is_js_local_specifier(imported):
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
    if dirty and not getattr(args, "force", False):
        rep = traffic_report("FAIL", "trusted baseline refused dirty working tree.", [normalized_finding("dirty_worktree", "error", "baseline", DIRTY_BASELINE_REFUSAL)], ["baseline", "git status"], "Review, commit, or stash current changes first; use --force only for an intentionally trusted state.")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end="")
        return 1
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("gitignore_unwritable","error","git",f"Cannot write .gitignore: {err}")]); print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    existed = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
    try:
        build_current_baseline(repo, quiet=getattr(args, "quiet", False), force=True); refreshed = existed or args.refresh
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


def cli_diff(args) -> int:
    from .judgment import judge_repo_change
    from .policy import PolicyMode
    if getattr(args, "ci", False):
        args.json = True
    if bool(getattr(args, "base_ref", None)) != bool(getattr(args, "head_ref", None)):
        raise SystemExit("--base-ref and --head-ref must be provided together")
    mode = PolicyMode.CI if getattr(args, "ci", False) else PolicyMode.STRICT if getattr(args, "strict", False) else PolicyMode.LOCAL
    judgment = judge_repo_change(args.repo, staged=args.staged, policy_mode=mode, base_ref=getattr(args, "base_ref", None), head_ref=getattr(args, "head_ref", None))
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
    baseline_exists_before_init = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
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
            _, created = build_current_baseline(repo, force=True)
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
    with _policy_file(repo).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True)+"\n")
    print(json.dumps(entry, indent=2))
    return 0

def cli_policy_validate(args) -> int:
    result = validate_policy_config(getattr(args, "repo", "."))
    if getattr(args, "json", False):
        print(json.dumps(result.to_json_dict(), indent=2))
        return 0 if result.valid else 1
    if not result.policy_present:
        print(f"No policy file found at {result.policy_path}; policy config is optional.")
        return 0
    print(f"Policy file: {result.policy_path}")
    if result.errors:
        for error in result.errors:
            if error.startswith("policy_config_invalid_json:"):
                print(f"ERROR: invalid JSON in {result.policy_path}: {error}")
            elif error == "policy_config_invalid:root_must_be_object":
                print(f"ERROR: policy root must be a JSON object in {result.policy_path}")
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
    if args.policy_command == "list":
        print(json.dumps({"schema_version":"sourcepack.policy.list.v1", "policies": _policy_entries(repo)}, indent=2)); return 0
    if args.policy_command == "remove":
        entries = [e for e in _policy_entries(repo) if e.get("id") != args.policy_id]
        _policy_file(repo).write_text("".join(json.dumps(e, sort_keys=True)+"\n" for e in entries), encoding="utf-8")
        print(f"Removed policy {args.policy_id}"); return 0
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

def run_cli(args_list=None):
    parser = argparse.ArgumentParser(prog="sourcepack", description="Local guardrail for AI-assisted repo changes. PASS exits 0, WARN exits 0 locally unless --strict or --ci is used, and FAIL exits nonzero.")
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
    baseline_cmd = subs.add_parser("baseline", help="create or refresh trusted enforcement baseline", description="Create or refresh .sourcepack/baseline, the authoritative enforcement state used by sourcepack diff.")
    baseline_cmd.add_argument("repo")
    baseline_cmd.add_argument("--force", action="store_true")
    baseline_cmd.add_argument("--refresh", action="store_true")
    baseline_cmd.add_argument("--verbose", action="store_true")
    baseline_cmd.add_argument("--json", action="store_true")
    baseline_cmd.add_argument("--quiet", action="store_true")
    diff_cmd = subs.add_parser("diff", help="check repo changes against trusted baseline", description="Judge working-tree or staged changes against .sourcepack/baseline. PASS exits 0. WARN exits 0 locally, but exits nonzero with --strict or --ci. FAIL exits nonzero. --json stays machine-readable.")
    diff_cmd.add_argument("repo")
    diff_cmd.add_argument("--staged", action="store_true")
    diff_cmd.add_argument("--verbose", action="store_true")
    diff_cmd.add_argument("--json", action="store_true")
    diff_cmd.add_argument("--strict", action="store_true", help="exit nonzero on WARN as well as FAIL")
    diff_cmd.add_argument("--ci", action="store_true", help="non-interactive CI mode; implies --strict and prints JSON")
    diff_cmd.add_argument("--base-ref", help="base git ref for committed-range diff mode; requires --head-ref")
    diff_cmd.add_argument("--head-ref", help="head git ref for committed-range diff mode; requires --base-ref")
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
    report_cmd = subs.add_parser("report", help="work with local SourcePack reports")
    report_subs = report_cmd.add_subparsers(dest="report_command")
    report_open = report_subs.add_parser("open", help="open .sourcepack/reports/latest.html")
    report_open.add_argument("repo", nargs="?", default=".")
    report_path = report_subs.add_parser("path", help="print .sourcepack/reports/latest.html")
    report_path.add_argument("repo", nargs="?", default=".")
    explain_cmd = subs.add_parser("explain")
    explain_cmd.add_argument("reason_code")
    allow_cmd = subs.add_parser("allow")
    allow_cmd.add_argument("allow_type", choices=["dependency", "command", "path"])
    allow_cmd.add_argument("value")
    allow_cmd.add_argument("--reason", required=True)
    allow_cmd.add_argument("--expires")
    allow_cmd.add_argument("--high-risk", action="store_true")
    policy_cmd = subs.add_parser("policy")
    policy_subs = policy_cmd.add_subparsers(dest="policy_command")
    policy_subs.add_parser("list")
    policy_validate = policy_subs.add_parser("validate", help="validate .sourcepack/policy.json without changing repository state")
    policy_validate.add_argument("repo", nargs="?", default=".")
    policy_validate.add_argument("--json", action="store_true")
    policy_remove = policy_subs.add_parser("remove")
    policy_remove.add_argument("policy_id")
    reset_cmd = subs.add_parser("reset")
    reset_cmd.add_argument("repo", nargs="?", default=".")
    args = parser.parse_args(args_list)
    if args.version:
        print(__version__); return 0
    try:
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
        if args.command == "policy":
            return cli_policy(args)
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
            if args.report_command == "open":
                return cli_report_open(args)
            if args.report_command == "path":
                return cli_report_path(args)
            parser.parse_args(["report", "--help"])
            return 1
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
