from __future__ import annotations

import subprocess
from pathlib import Path

from sourcepack.baseline import build_current_baseline
from sourcepack.judgment import build_repo_change_report, untracked_files_as_diff


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "selected").mkdir(parents=True)
    (root / "sibling").mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "sourcepack@example.test")
    _git(root, "config", "user.name", "SourcePack Tests")
    (root / "Cargo.toml").write_text('[package]\nname = "parent"\n', encoding="utf-8")
    (root / "sibling" / "Cargo.toml").write_text('[package]\nname = "sibling"\n', encoding="utf-8")
    (root / "selected" / "app.py").write_text('print("selected")\n', encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    return root


def test_clean_selected_root_first_run_does_not_self_report_protected_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    selected = root / "selected"

    build_current_baseline(selected, quiet=True)
    report = build_repo_change_report(selected)

    assert report["verdict"] == "PASS"
    assert report["repo_path"] == str(selected.resolve())
    assert {finding["id"] for finding in report["findings"]} == {"no_diff"}


def test_selected_root_ignores_parent_and_sibling_git_state_and_ecosystems(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    selected = root / "selected"
    build_current_baseline(selected, quiet=True)

    (root / "parent_untracked.py").write_text("print('parent')\n", encoding="utf-8")
    (root / "sibling" / "sibling_untracked.py").write_text("print('sibling')\n", encoding="utf-8")
    (selected / "kept.py").write_text("print('kept')\n", encoding="utf-8")
    report = build_repo_change_report(selected)
    text = str(report)

    assert "kept.py" in text
    assert "parent_untracked.py" not in text
    assert "sibling_untracked.py" not in text
    assert "Cargo.toml" not in text


def test_selected_root_git_modes_are_root_relative_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    selected = root / "selected"
    build_current_baseline(selected, quiet=True)
    _git(root, "add", "selected/.gitignore")
    _git(root, "add", "-f", "selected/.sourcepack")
    _git(root, "commit", "-m", "trust selected baseline")

    (root / "sibling" / "ignored.py").write_text("ignored\n", encoding="utf-8")
    (selected / "delete_me.py").write_text("delete\n", encoding="utf-8")
    _git(root, "add", "selected/delete_me.py")
    _git(root, "commit", "-m", "add delete target")

    (selected / "app.py").write_text('print("unstaged")\n', encoding="utf-8")
    (selected / "staged.py").write_text("staged\n", encoding="utf-8")
    _git(root, "add", "selected/staged.py")
    (selected / "untracked space.py").write_text("space\n", encoding="utf-8")
    (selected / "unicode_雪.py").write_text("snow\n", encoding="utf-8")
    _git(root, "mv", "selected/app.py", "selected/renamed app.py")
    (selected / "delete_me.py").unlink()

    report = build_repo_change_report(selected)
    text = str(report)

    assert "renamed app.py" in text
    assert "untracked space.py" in text
    assert "unicode_雪.py" in text
    assert "delete_me.py" in text
    staged_report = build_repo_change_report(selected, staged=True)
    assert "staged.py" in str(staged_report)
    assert "ignored.py" not in text
    assert "sibling/" not in text


def test_generated_untracked_sourcepack_state_is_not_synthetic_patch_but_tampering_still_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    selected = root / "selected"
    build_current_baseline(selected, quiet=True)

    synthetic = untracked_files_as_diff(selected)
    assert ".sourcepack/baseline/active.json" not in synthetic
    assert ".sourcepack/reports" not in synthetic

    (selected / ".sourcepack" / "baseline" / "active.json").write_text('{"forged": true}\n', encoding="utf-8")
    report = build_repo_change_report(selected, patch_text="diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\n--- a/.sourcepack/baseline/active.json\n+++ b/.sourcepack/baseline/active.json\n@@ -1 +1 @@\n-{}\n+{}\n")
    assert report["verdict"] == "FAIL"
    assert "sourcepackignore" not in str(report).lower()
