from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

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


def normalize_diff_path(path: str) -> tuple[str, bool]:
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
        return normalize_diff_path(path)

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
