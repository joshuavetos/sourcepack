from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Final


_DRIVE_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:/")


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
            unsafe = True
            continue

        parts.append(part)

    normalized = "/".join(parts)
    return normalized, unsafe or not bool(normalized)


def _clean_diff_path(path: str) -> tuple[str, bool]:
    path = path.strip().split("\t", 1)[0]

    if len(path) >= 2 and path[0] == path[-1] == '"':
        path = path[1:-1]

    return normalize_diff_path(path)


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []

    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None

    new_file = False
    deleted_file = False
    operation = "modify"

    current_unsafe = False
    malformed = False

    def reset_file_state() -> None:
        nonlocal current, old_path, new_path, new_file, deleted_file, operation, current_unsafe

        if current is not None:
            changes.append(current)

        current = None
        old_path = None
        new_path = None
        new_file = False
        deleted_file = False
        operation = "modify"
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
        )

    for line in text.splitlines():
        if line.startswith("diff --git "):
            reset_file_state()
            parts = line.split()

            if len(parts) >= 4:
                parsed_old, old_unsafe = _clean_diff_path(parts[2])
                parsed_new, new_unsafe = _clean_diff_path(parts[3])
                old_path = parsed_old or old_path
                new_path = parsed_new or new_path
                mark_unsafe(old_unsafe or new_unsafe)
            else:
                malformed = True

            continue

        if line.startswith("new file mode"):
            new_file = True
            continue

        if line.startswith("deleted file mode"):
            deleted_file = True
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

            continue

        if line.startswith("@@ "):
            if current is None:
                malformed = True
            else:
                current.diff_lines.append(line)
            continue

        if current is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current.added_lines.append(line[1:])
            current.diff_lines.append(line)
            continue

        if line.startswith("-") and not line.startswith("---"):
            current.diff_lines.append(line)
            continue

        if line.startswith(" "):
            current.diff_lines.append(line)
            continue

    if current is not None:
        changes.append(current)

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
