from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .policy import PolicyMode, normalize_policy_mode, exit_code

@dataclass(frozen=True)
class Judgment:
    repo_path: str
    policy_mode: PolicyMode
    report: dict

    @property
    def verdict(self) -> str:
        return str(self.report.get("verdict", "WARN"))

    def exit_code(self) -> int:
        return exit_code(self.verdict, self.policy_mode)


def judge_repo_change(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, policy_mode: PolicyMode | str = PolicyMode.LOCAL) -> Judgment:
    """Judge repository changes without requiring CLI parsing or stdout rendering."""
    from .cli import build_repo_change_report
    mode = normalize_policy_mode(policy_mode)
    report = build_repo_change_report(Path(repo_path).resolve(), staged=staged, patch_text=patch_text, ci=(mode is PolicyMode.CI))
    if mode is PolicyMode.CI:
        report["ci"] = True
    return Judgment(str(Path(repo_path).resolve()), mode, report)
