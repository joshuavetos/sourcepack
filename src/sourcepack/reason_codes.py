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
    DECLARED_COMMAND = "declared_command"
    UNSUPPORTED_COMMAND = "unsupported_command"
    UNSAFE_PATH = "unsafe_path"
    PATH_ESCAPE = "path_escape"
    PROTECTED_ARTIFACT = "protected_artifact"
    GIT_PATH_MODIFICATION = "git_path_modification"
    BINARY_DIFF = "binary_diff"
    MALFORMED_DIFF = "malformed_diff"
    UNSUPPORTED_ECOSYSTEM = "unsupported_ecosystem"
    DIRTY_WORKTREE = "dirty_worktree"
    BASELINE_LOCKED = "baseline_locked"
    BASELINE_FAILED = "baseline_failed"
    GIT_UNAVAILABLE = "git_unavailable"
    GIT_TIMEOUT = "git_timeout"
    GIT_DIFF_FAILED = "git_diff_failed"
    NO_GIT_REPO = "no_git_repo"
    NO_DIFF = "no_diff"
    REPO_NOT_DIRECTORY = "repo_not_directory"
    GITIGNORE_UNWRITABLE = "gitignore_unwritable"
    PROMPT_CONTEXT_FAILED = "prompt_context_failed"
    CLIPBOARD_UNAVAILABLE = "clipboard_unavailable"
    HOOK_INSTALL_FAILED = "hook_install_failed"
    HYGIENE_HOOKS_DEFERRED = "hygiene_hooks_deferred"
    BASELINE_INVENTORY_MISSING = "baseline_inventory_missing"
    WORKFLOW_CHANGE = "workflow_change"
    UNSUPPORTED_RENAME_COPY = "unsupported_rename_copy"
    DEPENDENCY_MANIFEST_UNCERTAIN = "dependency_manifest_uncertain"
    COMMAND_MANIFEST_UNCERTAIN = "command_manifest_uncertain"
    COMMAND_MANIFEST_MISSING = "command_manifest_missing"
    COMMAND_CHECK_INCONCLUSIVE = "command_check_inconclusive"
    DEPENDENCY_SCOPE_REVIEW = "dependency_scope_review"
    JS_ALIAS_UNCERTAIN = "js_alias_uncertain"
    EXECUTION_EVIDENCE_MISSING = "execution_evidence_missing"
    EXECUTION_EVIDENCE_PRESENT = "execution_evidence_present"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_INCONCLUSIVE = "execution_inconclusive"
    POLICY_CONFIG_WARNING = "policy_config_warning"
    POLICY_DEPENDENCY_ADDITION = "policy_dependency_addition"
    POLICY_PROTECTED_PATH = "policy_protected_path"
    POLICY_RESOLUTION_FAILED = "policy_resolution_failed"
    POLICY_PACKAGE_MANAGER = "policy_package_manager"
    POLICY_TEST_REQUIRED = "policy_test_required"
    POLICY_CHANGE_LIMIT = "policy_change_limit"
    POLICY_SECRET_PATTERN = "policy_secret_pattern"


_CANONICAL = {code.value for code in ReasonCode}
_ALIASES = {
    "baseline-corrupt": ReasonCode.BASELINE_CORRUPT.value,
    "baseline-missing": ReasonCode.BASELINE_MISSING.value,
    "baseline-stale": ReasonCode.BASELINE_STALE.value,
    "policy_package_manager_drift": ReasonCode.POLICY_PACKAGE_MANAGER.value,
    "policy_missing_test": ReasonCode.POLICY_TEST_REQUIRED.value,
    "policy_large_diff": ReasonCode.POLICY_CHANGE_LIMIT.value,
}


def normalize_reason_code(code: str) -> str:
    normalized = str(code).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _ALIASES.get(normalized, normalized)
    return normalized


def is_canonical_reason_code(code: str) -> bool:
    return normalize_reason_code(code) in _CANONICAL


def canonical_reason_codes() -> tuple[str, ...]:
    return tuple(sorted(_CANONICAL))
