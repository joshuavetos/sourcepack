from __future__ import annotations

from enum import StrEnum

REASON_CODE_VOCABULARY_VERSION = "reason_codes.v1"


class ReasonCode(StrEnum):
    BASELINE_MISSING = "baseline_missing"
    BASELINE_STALE = "baseline_stale"
    BASELINE_CORRUPT = "baseline_corrupt"
    MISSING_FILE = "missing_file"
    NEW_FILE = "new_file"
    DELETED_FILE = "deleted_file"
    UNSUPPORTED_DEPENDENCY = "unsupported_dependency"
    DECLARED_DEPENDENCY = "declared_dependency"
    UNSUPPORTED_COMMAND = "unsupported_command"
    UNSAFE_PATH = "unsafe_path"
    PROTECTED_ARTIFACT = "protected_artifact"
    GIT_PATH_MODIFICATION = "git_path_modification"
    BINARY_DIFF = "binary_diff"
    MALFORMED_DIFF = "malformed_diff"
    UNSUPPORTED_ECOSYSTEM = "unsupported_ecosystem"


_CANONICAL = {code.value for code in ReasonCode}
_ALIASES = {
    "baseline-corrupt": ReasonCode.BASELINE_CORRUPT.value,
    "baseline-missing": ReasonCode.BASELINE_MISSING.value,
    "baseline-stale": ReasonCode.BASELINE_STALE.value,
}


def normalize_reason_code(code: str) -> str:
    normalized = str(code).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _ALIASES.get(normalized, normalized)
    return normalized


def is_canonical_reason_code(code: str) -> bool:
    return normalize_reason_code(code) in _CANONICAL


def canonical_reason_codes() -> tuple[str, ...]:
    return tuple(sorted(_CANONICAL))
