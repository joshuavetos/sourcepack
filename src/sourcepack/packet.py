from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

from .diff_parser import normalize_diff_path
from .ecosystems.python import PY_IMPORT_ALIASES

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


def _decode_git_path(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape").replace("\\", "/")


def _git_tracked_paths(root: Path) -> set[str] | None:
    try:
        cp = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, ValueError):
        return None

    if cp.returncode != 0:
        return None

    tracked_paths = {_decode_git_path(path) for path in cp.stdout.split(b"\0") if path}
    if tracked_paths:
        return tracked_paths

    try:
        top_level_cp = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, ValueError):
        return None

    if top_level_cp.returncode != 0:
        return None

    top_level = top_level_cp.stdout.strip()
    if not top_level:
        return None

    try:
        all_tracked_cp = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=top_level,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, ValueError):
        return None

    if all_tracked_cp.returncode != 0:
        return None

    all_tracked_paths = {
        _decode_git_path(path) for path in all_tracked_cp.stdout.split(b"\0") if path
    }
    if not all_tracked_paths:
        return None

    return set()


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
    def __init__(
        self,
        input_path: str | Path,
        max_file_size: int = 1_000_000,
        include_hidden: bool = False,
        redact: bool = True,
        trust_git_tracked: bool = True,
    ):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.trust_git_tracked = trust_git_tracked
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0

    def ignore(self, path: Path, reason: str):
        rel = str(path.relative_to(self.input_path)) if path.is_absolute() or self.input_path in path.parents else str(path)
        self.ignored_files.append(IgnoredFile(rel.replace("\\", "/"), reason))

    def _include_file(self, fp: Path, rel_str: str) -> None:
        try:
            size = fp.stat().st_size
        except OSError:
            self.ignored_files.append(IgnoredFile(rel_str, "stat_error"))
            return

        if size > self.max_file_size:
            self.ignored_files.append(IgnoredFile(rel_str, "max_file_size_exceeded"))
            return

        if fp.suffix and fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
            self.ignored_files.append(IgnoredFile(rel_str, "unsupported_extension"))
            return

        if is_probably_binary(fp):
            self.ignored_files.append(IgnoredFile(rel_str, "binary_detected"))
            return

        try:
            content = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.ignored_files.append(IgnoredFile(rel_str, "decode_error"))
            return
        except OSError:
            self.ignored_files.append(IgnoredFile(rel_str, "read_error"))
            return

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

    def scan(self):
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_path}")

        tracked_paths = _git_tracked_paths(self.input_path) if self.trust_git_tracked else None

        for root, dirs, files in os.walk(self.input_path, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(dirs)
            files = sorted(files)
            kept_dirs = []

            for d in dirs:
                dpath = root_path / d
                rel = dpath.relative_to(self.input_path)
                rel_str = str(rel).replace("\\", "/")
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "symlink_skipped"))
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs

            for filename in files:
                fp = root_path / filename
                rel = fp.relative_to(self.input_path)
                rel_str = str(rel).replace("\\", "/")
                self.total_seen += 1

                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped"))
                    continue

                if not self.include_hidden and filename.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file"))
                    continue

                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern"))
                    continue

                if tracked_paths is not None and rel_str not in tracked_paths:
                    self.ignored_files.append(IgnoredFile(rel_str, "untracked_file_skipped"))
                    continue

                self._include_file(fp, rel_str)

        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    raw_paths = _git_tracked_paths(root)
    source = "git_ls_files" if raw_paths is not None else "scanner_included_files"

    if raw_paths is None:
        raw_paths = sorted(included)

    for raw in sorted(raw_paths):
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

        tracked_paths = _git_tracked_paths(source)
        current_files = []
        for root, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in sorted(dirs) if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
            for filename in sorted(files):
                fp = Path(root) / filename
                if filename.startswith(".") or fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    continue
                rel = str(fp.relative_to(source)).replace("\\", "/")
                if tracked_paths is not None and rel not in tracked_paths:
                    continue
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
    normalized, unsafe = normalize_diff_path(ref)
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


def scanner_config_hash() -> str:
    payload = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "ignored_patterns": sorted(DEFAULT_IGNORED_PATTERNS),
        "text_extensions": sorted(DEFAULT_TEXT_EXTENSIONS),
        "max_file_size": 1_000_000,
        "include_hidden": False,
        "redact": True,
        "trust_git_tracked": True,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))
