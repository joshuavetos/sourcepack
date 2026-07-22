from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping


REPOSITORY_STATE_SCHEMA_VERSION = "sourcepack.repository_state.v1"


def _normalize_path(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or "\x00" in text:
        raise ValueError(f"unsafe repository path: {value!r}")
    pure = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"unsafe repository path: {value!r}")
    return pure.as_posix()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RepositoryFileState:
    path: str
    trusted_content: str | None
    proposed_content: str | None
    modified_by_patch: bool

    @property
    def trusted_sha256(self) -> str | None:
        return _sha256_text(self.trusted_content) if self.trusted_content is not None else None

    @property
    def proposed_sha256(self) -> str | None:
        return _sha256_text(self.proposed_content) if self.proposed_content is not None else None

    @property
    def exists_in_trusted_state(self) -> bool:
        return self.trusted_content is not None

    @property
    def exists_in_proposed_state(self) -> bool:
        return self.proposed_content is not None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "exists_in_trusted_state": self.exists_in_trusted_state,
            "exists_in_proposed_state": self.exists_in_proposed_state,
            "modified_by_patch": self.modified_by_patch,
            "trusted_sha256": self.trusted_sha256,
            "proposed_sha256": self.proposed_sha256,
        }


@dataclass(frozen=True)
class RepositoryState:
    trusted_files: Mapping[str, str]
    proposed_files: Mapping[str, str | None]

    @classmethod
    def build(
        cls,
        trusted_files: Mapping[str, str],
        proposed_overlay: Mapping[str, str | None] | None = None,
    ) -> "RepositoryState":
        trusted = {_normalize_path(path): str(content) for path, content in trusted_files.items()}
        proposed = {
            _normalize_path(path): (None if content is None else str(content))
            for path, content in (proposed_overlay or {}).items()
        }
        return cls(trusted_files=trusted, proposed_files=proposed)

    def file(self, path: str) -> RepositoryFileState:
        normalized = _normalize_path(path)
        trusted = self.trusted_files.get(normalized)
        if normalized in self.proposed_files:
            proposed = self.proposed_files[normalized]
            modified = proposed != trusted
        else:
            proposed = trusted
            modified = False
        return RepositoryFileState(normalized, trusted, proposed, modified)

    def trusted_content(self, path: str) -> str | None:
        return self.file(path).trusted_content

    def proposed_content(self, path: str) -> str | None:
        return self.file(path).proposed_content

    def modified_paths(self) -> tuple[str, ...]:
        return tuple(sorted(path for path in self.proposed_files if self.file(path).modified_by_patch))

    def trusted_inventory(self) -> tuple[str, ...]:
        return tuple(sorted(self.trusted_files))

    def proposed_inventory(self) -> tuple[str, ...]:
        paths = set(self.trusted_files)
        for path, content in self.proposed_files.items():
            if content is None:
                paths.discard(path)
            else:
                paths.add(path)
        return tuple(sorted(paths))

    def materialize(self) -> "MaterializedRepositoryState":
        return MaterializedRepositoryState(self)

    def to_dict(self) -> dict:
        return {
            "schema_version": REPOSITORY_STATE_SCHEMA_VERSION,
            "trusted_inventory": list(self.trusted_inventory()),
            "proposed_inventory": list(self.proposed_inventory()),
            "modified_paths": list(self.modified_paths()),
            "files": [self.file(path).to_dict() for path in sorted(set(self.trusted_files) | set(self.proposed_files))],
        }


class MaterializedRepositoryState:
    def __init__(self, state: RepositoryState) -> None:
        self.state = state
        self._tmp = tempfile.TemporaryDirectory(prefix="sourcepack-repository-state-")
        self.root = Path(self._tmp.name)
        self.trusted_root = self.root / "trusted"
        self.proposed_root = self.root / "proposed"
        self._write_tree(self.trusted_root, state.trusted_files)
        proposed_tree: dict[str, str] = dict(state.trusted_files)
        for path, content in state.proposed_files.items():
            if content is None:
                proposed_tree.pop(path, None)
            else:
                proposed_tree[path] = content
        self._write_tree(self.proposed_root, proposed_tree)

    @staticmethod
    def _write_tree(root: Path, files: Mapping[str, str]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            target = root / _normalize_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def cleanup(self) -> None:
        self._tmp.cleanup()

    def __enter__(self) -> "MaterializedRepositoryState":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()
