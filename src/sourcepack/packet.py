from __future__ import annotations

import fnmatch
import base64
import hashlib
import json
import os
import re
import stat
import tomllib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from .diff_parser import normalize_diff_path
from .git import GitProducerIncompleteError, tracked_paths as git_tracked_paths
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
REPOSITORY_ENTRY_LIMIT = 10_000
REPOSITORY_DEPTH_LIMIT = 64
REPOSITORY_READ_LIMIT_BYTES = 64 * 1024 * 1024
PACKET_CLEANUP_ENTRY_LIMIT = 10_000
PACKET_CLEANUP_DEPTH_LIMIT = 64
PACKET_VERIFY_METADATA_LIMIT_BYTES = 8 * 1024 * 1024
PACKET_VERIFY_RECORD_LIMIT = 10_000
PACKET_VERIFY_FILE_LIMIT_BYTES = 64 * 1024 * 1024
PACKET_VERIFY_AGGREGATE_LIMIT_BYTES = 128 * 1024 * 1024
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
        with path.open("rb") as stream:
            data = stream.read(sample_size)
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


def sourcepack_bootstrap_file(path: str) -> bool:
    return path.replace("\\", "/") in {".sourcepackignore", "sourcepack.config.json"}


def _git_tracked_paths(root: Path) -> set[str] | None:
    return git_tracked_paths(root)
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
        max_entries: int = REPOSITORY_ENTRY_LIMIT,
        max_depth: int = REPOSITORY_DEPTH_LIMIT,
        max_total_read_bytes: int = REPOSITORY_READ_LIMIT_BYTES,
    ):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.trust_git_tracked = trust_git_tracked
        self.max_entries = max_entries
        self.max_depth = max_depth
        self.max_total_read_bytes = max_total_read_bytes
        self.total_read_bytes = 0
        self.authority = {"status": "complete", "complete": True, "reason": None}
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0
        self.producer_entries_seen = 0

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
        if self.total_read_bytes + size > self.max_total_read_bytes:
            self.authority = {"status": "incomplete", "complete": False, "reason": "repository_read_limit"}
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
        self.total_read_bytes += size

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

        try:
            tracked_paths = _git_tracked_paths(self.input_path) if self.trust_git_tracked else None
        except GitProducerIncompleteError:
            self.authority = {"status": "incomplete", "complete": False, "reason": "git_output_limit"}
            return self

        pending = [(self.input_path, 0)]
        while pending and self.authority["complete"]:
            root_path, depth = pending.pop()
            try:
                entries = []
                with os.scandir(root_path) as iterator:
                    for entry in iterator:
                        self.producer_entries_seen += 1
                        if self.producer_entries_seen > self.max_entries:
                            self.authority = {"status": "incomplete", "complete": False, "reason": "repository_entry_limit"}
                            break
                        entries.append(entry)
            except OSError:
                self.ignore(root_path, "directory_read_error")
                continue
            if not self.authority["complete"]:
                break
            dirs = sorted((entry for entry in entries if entry.is_dir(follow_symlinks=False)), key=lambda item: item.name)
            files = sorted((entry for entry in entries if not entry.is_dir(follow_symlinks=False)), key=lambda item: item.name)
            kept_dirs: list[Path] = []

            for entry in dirs:
                d = entry.name
                dpath = Path(entry.path)
                rel = dpath.relative_to(self.input_path)
                rel_str = str(rel).replace("\\", "/")
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str + "/", "symlink_skipped"))
                else:
                    if depth >= self.max_depth:
                        self.authority = {"status": "incomplete", "complete": False, "reason": "repository_depth_limit"}
                        break
                    kept_dirs.append(dpath)
            if not self.authority["complete"]:
                break
            pending.extend((path, depth + 1) for path in reversed(kept_dirs))

            for entry in files:
                filename = entry.name
                fp = Path(entry.path)
                self.total_seen += 1
                rel = fp.relative_to(self.input_path)
                rel_str = str(rel).replace("\\", "/")
                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped"))
                    continue

                if not self.include_hidden and filename.startswith(".") and not sourcepack_bootstrap_file(rel_str):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file"))
                    continue

                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern"))
                    continue

                if tracked_paths is not None and rel_str not in tracked_paths and not sourcepack_bootstrap_file(rel_str):
                    self.ignored_files.append(IgnoredFile(rel_str, "untracked_file_skipped"))
                    continue

                self._include_file(fp, rel_str)
                if not self.authority["complete"]:
                    break

        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    raw_paths = _git_tracked_paths(root)
    source = "git_ls_files" if raw_paths is not None else "scanner_included_files"

    records: dict[str, str] = {}
    if raw_paths is None:
        records = {rel: "scanner_included_files" for rel in sorted(included)}
    else:
        records = {raw.replace("\\", "/"): "git_ls_files" for raw in sorted(raw_paths)}
        for rel in sorted(included):
            if sourcepack_bootstrap_file(rel) and rel not in records:
                records[rel] = "scanner_included_files"

    for rel, record_source in sorted(records.items()):
        path = root / rel
        rec = {"relative_path": rel, "included_in_prompt_context": rel in included, "source": record_source}
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


class PacketCleanupError(RuntimeError):
    def __init__(self, result: dict[str, object]):
        self.result = result
        super().__init__(f"packet output cleanup {result['status']}: {result.get('error') or result.get('limit_reached')}")


def _cleanup_result(status: str, consumed: int, source_exhausted: bool, limit: int, limit_reached: str | None, error: str | None) -> dict[str, object]:
    return {"status": status, "complete": status == "complete", "consumed": consumed, "retained": 0, "source_exhausted": source_exhausted, "total": consumed, "total_is_lower_bound": not source_exhausted, "configured_limit": limit, "limit_reached": limit_reached, "error": error}


def _cleanup_packet_output(root: Path, *, max_entries: int, max_depth: int) -> dict[str, object]:
    canonical_root = root.resolve(strict=True)
    pending: list[tuple[Path, int, bool]] = [(root, 0, False)]
    consumed = 0
    while pending:
        path, depth, visited = pending.pop()
        if path != root and not visited:
            if consumed == max_entries:
                return _cleanup_result("incomplete", consumed, False, max_entries, "cleanup_entries", None)
            consumed += 1
        if path != root:
            try:
                path.parent.resolve(strict=True).relative_to(canonical_root)
            except (OSError, ValueError) as exc:
                return _cleanup_result("failed", consumed, False, max_entries, None, f"path escape or metadata failure: {exc}")
        try:
            if path.is_symlink():
                path.unlink()
                continue
            if not path.is_dir():
                path.unlink()
                continue
            try:
                path.resolve(strict=True).relative_to(canonical_root)
            except (OSError, ValueError) as exc:
                return _cleanup_result("failed", consumed, False, max_entries, None, f"path escape or metadata failure: {exc}")
            if visited:
                if path != root:
                    path.rmdir()
                continue
            if depth > max_depth:
                return _cleanup_result("incomplete", consumed, False, max_entries, "cleanup_depth", None)
            entries = []
            with os.scandir(path) as iterator:
                for entry in iterator:
                    if len(entries) >= max_entries - consumed:
                        return _cleanup_result("incomplete", consumed, False, max_entries, "cleanup_entries", None)
                    entries.append(Path(entry.path))
            pending.append((path, depth, True))
            for child in reversed(sorted(entries, key=lambda item: item.name)):
                pending.append((child, depth + 1, False))
            # Entries are counted only after successful deletion, so failures never
            # imply that an observed prefix was cleaned.
            if not entries and path != root:
                pending.pop()
                path.rmdir()
        except OSError as exc:
            return _cleanup_result("failed", consumed, False, max_entries, None, f"cleanup failed: {exc}")
    return _cleanup_result("complete", consumed, True, max_entries, None, None)


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md", "file_inventory.json"]

    def __init__(self, out: str | Path, scanner: SourceScanner, force: bool = False, *, cleanup_entry_limit: int = PACKET_CLEANUP_ENTRY_LIMIT, cleanup_depth_limit: int = PACKET_CLEANUP_DEPTH_LIMIT):
        self.out = Path(out)
        self.scanner = scanner
        self.force = force
        self.cleanup_entry_limit = cleanup_entry_limit
        self.cleanup_depth_limit = cleanup_depth_limit
        self.cleanup_result: dict[str, object] | None = None

    def prepare_out(self):
        if self.out.is_symlink():
            self.cleanup_result = _cleanup_result("failed", 0, False, self.cleanup_entry_limit, "output_root_symlink", "output root must not be a symlink")
            raise PacketCleanupError(self.cleanup_result)
        if self.out.exists():
            if not self.out.is_dir():
                self.cleanup_result = _cleanup_result("failed", 0, False, self.cleanup_entry_limit, None, "output root is not a directory")
                raise PacketCleanupError(self.cleanup_result)
            if not self.force:
                try:
                    nonempty = next(os.scandir(self.out), None) is not None
                except OSError as exc:
                    raise FileExistsError(f"Cannot inspect output directory: {self.out}: {exc}") from exc
                if nonempty:
                    raise FileExistsError(f"Output directory is non-empty: {self.out}")
            else:
                self.cleanup_result = _cleanup_packet_output(self.out, max_entries=self.cleanup_entry_limit, max_depth=self.cleanup_depth_limit)
                if self.cleanup_result["status"] != "complete":
                    raise PacketCleanupError(self.cleanup_result)
        self.out.mkdir(parents=True, exist_ok=True)
        if self.cleanup_result is None:
            self.cleanup_result = _cleanup_result("complete", 0, True, self.cleanup_entry_limit, None, None)
        return self.cleanup_result

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
            "authority": dict(self.scanner.authority),
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
            encoded_path = base64.b64encode(f.relative_path.encode("utf-8", "surrogateescape")).decode("ascii")
            encoded_content = base64.b64encode(f.content.encode("utf-8")).decode("ascii")
            xml_parts.append(f'    <file path_b64="{encoded_path}" sha256="{f.sha256}" bytes="{f.size_bytes}" estimated_tokens="{f.estimated_tokens}">')
            xml_parts.append(f'      <content encoding="base64">{encoded_content}</content>')
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
        reality_map = generate_reality_map(manifest, self.out, packet_construction=True)
        (self.out / "reality_map.json").write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
        (self.out / "ai_instructions.md").write_text(render_ai_instructions(reality_map), encoding="utf-8")
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out


def _load_verification_json(path: Path, byte_limit: int) -> dict:
    raw = _read_stable_verification_file(path, byte_limit)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _confined_verification_file(root: Path, raw_path: object) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path:
        return None, "path must be a nonempty string"
    portable = raw_path.replace("\\", "/")
    windows_path = PureWindowsPath(raw_path)
    if PurePosixPath(portable).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        return None, "absolute or drive-qualified path"
    if ".." in PurePosixPath(portable).parts:
        return None, "parent traversal"
    normalized, unsafe = normalize_diff_path(portable)
    if unsafe or not normalized:
        return None, "unsafe path"

    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    current = root
    try:
        for component in PurePosixPath(normalized).parts:
            current = current / component
            if current.is_symlink():
                return None, "symlink traversal"
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file():
            return None, "not a regular file"
    except (OSError, ValueError):
        return None, "missing, unreadable, or outside declared root"
    return resolved, None


def verify_packet(
    packet_path: str | Path,
    against: str | Path | None = None,
    *,
    metadata_byte_limit: int = PACKET_VERIFY_METADATA_LIMIT_BYTES,
    record_limit: int = PACKET_VERIFY_RECORD_LIMIT,
    file_byte_limit: int = PACKET_VERIFY_FILE_LIMIT_BYTES,
    aggregate_byte_limit: int = PACKET_VERIFY_AGGREGATE_LIMIT_BYTES,
) -> bool:
    packet = Path(packet_path)
    if packet.is_symlink():
        print("FAIL packet root must not be a symlink")
        return False
    try:
        packet = packet.resolve(strict=True)
    except OSError:
        print("FAIL packet root missing or unreadable")
        return False
    if not packet.is_dir():
        print("FAIL packet root is not a directory")
        return False
    ok = True
    receipt_path, receipt_path_error = _confined_verification_file(packet, "receipt.json")
    if receipt_path_error or receipt_path is None:
        print(f"FAIL unsafe receipt.json: {receipt_path_error}")
        return False
    try:
        receipt = _load_verification_json(receipt_path, metadata_byte_limit)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL receipt.json unavailable or malformed: {exc}")
        return False
    hashes = receipt.get("hashes", {})
    if not isinstance(hashes, dict):
        print("FAIL receipt.json hashes must be an object")
        return False
    if len(hashes) > record_limit:
        print(f"FAIL packet verification record limit exceeded: {record_limit}")
        return False
    if "receipt.json" in hashes or "manifest.json" not in hashes:
        print("FAIL receipt.json has incoherent artifact coverage")
        return False
    digest_pattern = re.compile(r"^[0-9a-f]{64}$")
    bytes_read = 0
    for name, expected in hashes.items():
        if not isinstance(expected, str) or digest_pattern.fullmatch(expected) is None:
            print(f"FAIL invalid receipt hash for {name!r}")
            return False
        path, path_error = _confined_verification_file(packet, name)
        if path_error or path is None:
            print(f"FAIL unsafe packet artifact {name!r}: {path_error}")
            return False
        remaining = min(file_byte_limit, aggregate_byte_limit - bytes_read)
        if remaining < 0:
            print(f"FAIL packet verification byte limit exceeded at {name}")
            return False
        try:
            raw = _read_stable_verification_file(path, remaining)
        except (OSError, ValueError):
            print(f"FAIL packet verification byte limit or stable-read check failed at {name}")
            return False
        bytes_read += len(raw)
        actual = hashlib.sha256(raw).hexdigest()
        if actual == expected:
            print(f"PASS {name}")
        else:
            print(f"FAIL {name} hash mismatch")
            ok = False
    if against:
        manifest_path, manifest_path_error = _confined_verification_file(packet, "manifest.json")
        if manifest_path_error or manifest_path is None:
            print(f"FAIL unsafe manifest.json: {manifest_path_error}")
            return False
        try:
            manifest = _load_verification_json(manifest_path, metadata_byte_limit)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"FAIL manifest.json unavailable or malformed: {exc}")
            return False
        source = Path(against)
        if source.is_symlink():
            print("FAIL against-source root must not be a symlink")
            return False
        try:
            source = source.resolve(strict=True)
        except OSError:
            print("FAIL against-source root missing or unreadable")
            return False
        if not source.is_dir():
            print("FAIL against-source root is not a directory")
            return False
        included_records = manifest.get("included_files", [])
        if not isinstance(included_records, list) or len(included_records) > record_limit:
            print(f"FAIL manifest included-file verification record limit exceeded: {record_limit}")
            return False
        if any(not isinstance(rec, dict) or not isinstance(rec.get("relative_path"), str) for rec in included_records):
            print("FAIL manifest included-file records are malformed")
            return False
        relative_paths = [rec["relative_path"] for rec in included_records]
        if len(set(relative_paths)) != len(relative_paths):
            print("FAIL manifest contains duplicate relative_path values")
            return False
        included = dict(zip(relative_paths, included_records))
        for rel, rec in included.items():
            source_file, path_error = _confined_verification_file(source, rel)
            if path_error or source_file is None:
                print(f"FAIL unsafe source file {rel!r}: {path_error}")
                return False
            has_source_hash = rec.get("source_sha256") is not None
            expected_source_hash = rec.get("source_sha256") if has_source_hash else rec.get("sha256")
            if not isinstance(expected_source_hash, str) or digest_pattern.fullmatch(expected_source_hash) is None:
                print(f"FAIL invalid source hash for {rel!r}")
                return False
            remaining = min(file_byte_limit, aggregate_byte_limit - bytes_read)
            try:
                raw = _read_stable_verification_file(source_file, remaining)
            except (OSError, ValueError):
                print(f"FAIL source verification byte limit or stable-read check failed at {rel}")
                return False
            bytes_read += len(raw)
            if b"\x00" in raw[:1024]:
                print(f"WARN source now binary {rel}")
                content_hash = hashlib.sha256(raw).hexdigest()
            else:
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    print(f"FAIL source unreadable {rel}")
                    ok = False
                    continue
                if not has_source_hash:
                    redacted, _ = redact_secrets(content)
                    content_hash = sha256_text(redacted)
                else:
                    content_hash = sha256_text(content)
            if content_hash != expected_source_hash:
                print(f"FAIL source changed {rel}")
                ok = False

        scanner = SourceScanner(source).scan()
        if not scanner.authority["complete"]:
            print(f"FAIL repository traversal incomplete: {scanner.authority['reason']}")
            ok = False
        current_files = [item.relative_path for item in scanner.included_files if item.relative_path not in included]
        for rel in current_files:
            print(f"WARN new source file not in packet {rel}")
    print("OVERALL", "PASS" if ok else "FAIL")
    return ok


# Compatibility exports: packet construction calls the canonical evidence
# interpreter, while this module retains scanning, writing, and verification.
from . import repository_evidence as _repository_evidence

_read_stable_verification_file = _repository_evidence._read_stable_verification_file

_included_paths = _repository_evidence._included_paths
_package_json_scripts = _repository_evidence._package_json_scripts
_is_poetry_project = _repository_evidence._is_poetry_project
_uses_unittest = _repository_evidence._uses_unittest
generate_reality_map = _repository_evidence.generate_reality_map
render_ai_instructions = _repository_evidence.render_ai_instructions
def load_manifest(packet: Path):
    """Load legacy packet manifests without imposing canonical object validation."""
    return json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
PATHLIKE_EXTENSIONS = _repository_evidence.PATHLIKE_EXTENSIONS
PROJECT_PATH_PREFIXES = _repository_evidence.PROJECT_PATH_PREFIXES
_normalize_ai_ref = _repository_evidence._normalize_ai_ref
_looks_like_ai_file_ref = _repository_evidence._looks_like_ai_file_ref
extract_refs = _repository_evidence.extract_refs
_packet_file_contents = _repository_evidence._packet_file_contents
_normalize_dependency_name = _repository_evidence._normalize_dependency_name
_dependency_name_for_import = _repository_evidence._dependency_name_for_import
_js_package_root = _repository_evidence._js_package_root
_python_dependency_names_from_requirement_lines = _repository_evidence._python_dependency_names_from_requirement_lines
_python_dependency_names_from_pyproject = _repository_evidence._python_dependency_names_from_pyproject
_add_common_dependency = _repository_evidence._add_common_dependency
dependency_inventory = _repository_evidence.dependency_inventory
_has_import = _repository_evidence._has_import
PDF_DEPENDENCIES = _repository_evidence.PDF_DEPENDENCIES
_declares_pdf_dependency = _repository_evidence._declares_pdf_dependency
feature_inventory = _repository_evidence.feature_inventory


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
