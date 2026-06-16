from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

try:
    from . import __version__
except Exception:
    __version__ = "1.9.8"

DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "target", "coverage", ".pytest_cache"
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
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json"]

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
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out


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


def init_workspace(path: str | Path):
    p = Path(path); p.mkdir(parents=True, exist_ok=True)
    ignore = p / ".sourcepackignore"
    config = p / "sourcepack.config.json"
    if not ignore.exists():
        ignore.write_text("# SourcePack ignore rules\n.env\nnode_modules/\ndist/\nbuild/\n", encoding="utf-8")
    if not config.exists():
        config.write_text(json.dumps({"max_file_size": 1_000_000, "include_hidden": False, "redact_secrets": True}, indent=2), encoding="utf-8")
    print(f"Initialized SourcePack workspace at {p}")


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
    init = subs.add_parser("init")
    init.add_argument("path", nargs="?", default=".")
    subs.add_parser("doctor")
    args = parser.parse_args(args_list)
    if args.version:
        print(__version__); return 0
    try:
        if args.command == "doctor":
            doctor(); return 0
        if args.command == "init":
            init_workspace(args.path); return 0
        if args.command == "build":
            scanner = SourceScanner(args.input, max_file_size=args.max_file_size, include_hidden=args.include_hidden, redact=not args.no_redact).scan()
            out = PacketWriter(args.out, scanner, force=args.force).write_all()
            print(f"Packet built successfully at {out}"); return 0
        if args.command == "verify":
            return 0 if verify_packet(args.packet, args.against) else 1
        if args.command == "judge":
            judge_ai_answer(args.packet, args.ai_answer, args.out); return 0
        parser.print_help(); return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
