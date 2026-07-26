from pathlib import Path


def test_command_center_pr_scope_excludes_main_and_trusted_state_writes() -> None:
    text = Path("docs/command-center-pr-scope.md").read_text(encoding="utf-8")
    assert "modify `main`" in text
    assert "create trusted repository state" in text
