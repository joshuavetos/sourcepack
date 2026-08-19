from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Final


_DRIVE_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:")


@dataclass
class PatchFileChange:
    path: str
    old_path: str | None
    new_file: bool = False
    deleted_file: bool = False
    added_lines: list[str] = field(default_factory=list)
    diff_lines: list[str] = field(default_factory=list)
    unsafe_path: bool = False
    operation: str = "modify"
    old_mode: str | None = None
    new_mode: str | None = None
    proposed_symlink_target: str | None = None


def normalize_diff_path(path: str) -> tuple[str, bool]:
    raw = path.strip().replace("\\", "/")

    if raw.startswith(("a/", "b/")):
        raw = raw[2:]

    if not raw:
        return raw, True

    if raw.startswith("/") or _DRIVE_PATH_RE.match(raw):
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

    normalized = "/".join(parts)
    return normalized, unsafe or not bool(normalized)


def _clean_diff_path(path: str) -> tuple[str, bool]:
    path = path.strip().split("\t", 1)[0]

    if len(path) >= 2 and path[0] == path[-1] == '"':
        try:
            decoded = json.loads(path)
        except json.JSONDecodeError:
            return path, True
        if not isinstance(decoded, str):
            return path, True
        path = decoded

    return normalize_diff_path(path)


def quote_git_path(path: str) -> str:
    """Return an unambiguous quoted path for a synthetic Git diff header."""
    if not any(character.isspace() or character in {'"', '\\'} or ord(character) < 32 or ord(character) > 126 for character in path):
        return path
    return json.dumps(path, ensure_ascii=True)


def _diff_git_paths(header: str) -> tuple[str, str] | None:
    decoder = json.JSONDecoder()
    rest = header.removeprefix("diff --git ").lstrip()
    values: list[str] = []
    for _ in range(2):
        if not rest:
            return None
        if rest.startswith('"'):
            try:
                value, end = decoder.raw_decode(rest)
            except json.JSONDecodeError:
                return None
            if not isinstance(value, str):
                return None
            rest = rest[end:].lstrip()
        else:
            value, separator, rest = rest.partition(" ")
            if not separator and len(values) == 0:
                return None
            rest = rest.lstrip()
        values.append(value)
    return values[0], values[1]


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []

    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None

    new_file = False
    deleted_file = False
    operation = "modify"
    old_mode: str | None = None
    new_mode: str | None = None

    current_unsafe = False
    malformed = False
    hunk_old_remaining = 0
    hunk_new_remaining = 0
    in_hunk = False

    def finish_hunk() -> None:
        nonlocal in_hunk
        in_hunk = False

    def reset_file_state() -> None:
        nonlocal current, old_path, new_path, new_file, deleted_file, operation, current_unsafe, old_mode, new_mode

        finish_hunk()
        if current is not None:
            changes.append(current)

        current = None
        old_path = None
        new_path = None
        new_file = False
        deleted_file = False
        operation = "modify"
        old_mode = None
        new_mode = None
        current_unsafe = False

    def mark_unsafe(unsafe: bool) -> None:
        nonlocal current_unsafe, malformed
        if unsafe:
            current_unsafe = True
            malformed = True

    def ensure_current() -> None:
        nonlocal current

        if current is not None:
            return

        path = new_path or old_path or ""
        current = PatchFileChange(
            path=path,
            old_path=old_path,
            new_file=new_file or old_path is None,
            deleted_file=deleted_file or new_path is None,
            unsafe_path=current_unsafe,
            operation=operation,
            old_mode=old_mode,
            new_mode=new_mode,
        )

    for line in text.splitlines():
        # Hunk payload prefixes take precedence over header-like text.  A real
        # added line may itself begin with ``+++``, ``---``, or ``diff --git``.
        if in_hunk and (
            line.startswith(("diff --git ", "@@ "))
            or (
                hunk_old_remaining <= 0
                and hunk_new_remaining <= 0
                and not line.startswith(("+", "-", " ", r"\ No newline at end of file"))
            )
        ):
            finish_hunk()
        if in_hunk:
            if line == r"\ No newline at end of file":
                continue
            if line.startswith("+"):
                current.added_lines.append(line[1:])
                current.diff_lines.append(line)
                hunk_new_remaining -= 1
            elif line.startswith("-"):
                current.diff_lines.append(line)
                hunk_old_remaining -= 1
            elif line.startswith(" "):
                current.diff_lines.append(line)
                hunk_old_remaining -= 1
                hunk_new_remaining -= 1
            else:
                malformed = True
            continue

        if line.startswith("diff --git "):
            reset_file_state()
            header_paths = _diff_git_paths(line)

            if header_paths is not None:
                parsed_old, old_unsafe = _clean_diff_path(header_paths[0])
                parsed_new, new_unsafe = _clean_diff_path(header_paths[1])
                old_path = parsed_old or old_path
                new_path = parsed_new or new_path
                mark_unsafe(old_unsafe or new_unsafe)
            else:
                malformed = True

            continue

        if line.startswith("old mode "):
            old_mode = line.removeprefix("old mode ").strip() or None
            continue

        if line.startswith("new mode "):
            new_mode = line.removeprefix("new mode ").strip() or None
            continue

        if line.startswith("index "):
            index_parts = line.split()
            if len(index_parts) >= 3 and re.fullmatch(r"[0-7]{6}", index_parts[-1]):
                old_mode = old_mode or index_parts[-1]
                new_mode = new_mode or index_parts[-1]
            continue

        if line.startswith("new file mode"):
            new_file = True
            new_mode = line.removeprefix("new file mode").strip() or None
            continue

        if line.startswith("deleted file mode"):
            deleted_file = True
            old_mode = line.removeprefix("deleted file mode").strip() or None
            continue

        if line.startswith("rename from "):
            old_path, unsafe = _clean_diff_path(line.removeprefix("rename from "))
            operation = "rename"
            mark_unsafe(unsafe)
            continue

        if line.startswith("rename to "):
            new_path, unsafe = _clean_diff_path(line.removeprefix("rename to "))
            operation = "rename"
            mark_unsafe(unsafe)
            ensure_current()
            continue

        if line.startswith("copy from "):
            old_path, unsafe = _clean_diff_path(line.removeprefix("copy from "))
            operation = "copy"
            mark_unsafe(unsafe)
            continue

        if line.startswith("copy to "):
            new_path, unsafe = _clean_diff_path(line.removeprefix("copy to "))
            operation = "copy"
            new_file = True
            mark_unsafe(unsafe)
            ensure_current()
            continue

        if line.startswith("--- "):
            value = line[4:].strip()

            if value == "/dev/null":
                old_path = None
            else:
                old_path, unsafe = _clean_diff_path(value)
                mark_unsafe(unsafe)

            continue

        if line.startswith("+++ "):
            value = line[4:].strip()

            if value == "/dev/null":
                new_path = None
            else:
                new_path, unsafe = _clean_diff_path(value)
                mark_unsafe(unsafe)

            ensure_current()

            if current is not None:
                current.path = new_path or old_path or ""
                current.old_path = old_path
                current.new_file = new_file or old_path is None
                current.deleted_file = deleted_file or new_path is None
                current.unsafe_path = current.unsafe_path or current_unsafe
                current.operation = operation
                current.old_mode = old_mode
                current.new_mode = new_mode

            continue

        if line.startswith("@@ "):
            finish_hunk()
            if current is None:
                malformed = True
            else:
                current.diff_lines.append(line)
                match = re.match(r"^@@ -(?:\d+)(?:,(\d+))? \+(?:\d+)(?:,(\d+))? @@(?: |$)", line)
                if match is None:
                    malformed = True
                else:
                    hunk_old_remaining = int(match.group(1) or "1")
                    hunk_new_remaining = int(match.group(2) or "1")
                    in_hunk = True
            continue

        if current is None:
            continue

        if line == r"\ No newline at end of file":
            if current is None:
                malformed = True
            continue

        if line.startswith("+") and not line.startswith("+++"):
            if not in_hunk or hunk_new_remaining <= 0:
                malformed = True
                continue
            current.added_lines.append(line[1:])
            current.diff_lines.append(line)
            hunk_new_remaining -= 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            if not in_hunk or hunk_old_remaining <= 0:
                malformed = True
                continue
            current.diff_lines.append(line)
            hunk_old_remaining -= 1
            continue

        if line.startswith(" "):
            if not in_hunk or hunk_old_remaining <= 0 or hunk_new_remaining <= 0:
                malformed = True
                continue
            current.diff_lines.append(line)
            hunk_old_remaining -= 1
            hunk_new_remaining -= 1
            continue

        if in_hunk:
            malformed = True

    finish_hunk()
    if current is not None:
        changes.append(current)

    for change in changes:
        if change.new_mode == "120000":
            target = "\n".join(change.added_lines)
            change.proposed_symlink_target = target if target else None

    if malformed:
        changes.append(
            PatchFileChange(
                path="",
                old_path=None,
                unsafe_path=True,
                operation="malformed",
            )
        )

    return changes
