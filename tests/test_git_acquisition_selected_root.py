from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path

import pytest

from sourcepack import baseline
from sourcepack.decision_ledger import new_event
from sourcepack.git_acquisition import parse_porcelain_v1_z
from sourcepack.judgment import build_repo_change_report, git_worktree_dirty
from sourcepack.reports.json import traffic_report, write_user_report
from sourcepack.judgment import untracked_files_as_diff


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    selected = root / "selected"
    (root / "sibling").mkdir(parents=True)
    _git(root, "init")
    _git(root, "config", "user.email", "sourcepack@example.test")
    _git(root, "config", "user.name", "SourcePack Tests")
    for path in (root / "parent.txt", selected / "selected.txt", root / "sibling" / "sibling.txt"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    return root, selected


def _commit_selected_baseline(root: Path, selected: Path) -> None:
    baseline.build_current_baseline(selected, quiet=True)
    _git(root, "add", "selected/.gitignore")
    _git(root, "add", "-f", "selected/.sourcepack")
    _git(root, "commit", "-m", "selected baseline")


@pytest.mark.parametrize(
    ("relative_path", "staged", "expected_dirty"),
    [
        ("parent.txt", False, False),
        ("parent.txt", True, False),
        ("sibling/sibling.txt", False, False),
        ("sibling/sibling.txt", True, False),
        ("selected/selected.txt", False, True),
        ("selected/selected.txt", True, True),
    ],
)
def test_worktree_dirty_confines_tracked_changes_to_selected_root(
    tmp_path: Path, relative_path: str, staged: bool, expected_dirty: bool
) -> None:
    root, selected = _repo(tmp_path)
    (root / relative_path).write_text("changed\n", encoding="utf-8")
    if staged:
        _git(root, "add", relative_path)

    assert git_worktree_dirty(selected) == (expected_dirty, None)


def test_worktree_dirty_detects_selected_change_when_outside_change_also_exists(tmp_path: Path) -> None:
    root, selected = _repo(tmp_path)
    (root / "parent.txt").write_text("outside\n", encoding="utf-8")
    (selected / "selected.txt").write_text("inside\n", encoding="utf-8")

    assert git_worktree_dirty(selected) == (True, None)


def test_porcelain_v1_z_parser_preserves_bytes_and_rename_copy_fields() -> None:
    data = (
        b" M selected/space name\0"
        b"?? selected/unicode-\xe9\0"
        b"?? selected/tab\tname\0"
        b"?? selected/new\nline\0"
        b"R  selected/new name\0selected/old name\0"
        b"C  selected/copy name\0outside/source name\0"
        b" M outside/ignored\0"
    )

    records, state = parse_porcelain_v1_z(data, b"selected/")

    assert state is None
    assert [(record.status, record.path, record.old_path) for record in records] == [
        (" M", "space name", None),
        ("??", os.fsdecode(b"unicode-\xe9"), None),
        ("??", "tab\tname", None),
        ("??", "new\nline", None),
        ("R ", "new name", "old name"),
        ("C ", "copy name", None),
    ]


@pytest.mark.parametrize(
    "data",
    [b" M selected/no-terminator", b"bad\0", b"R  selected/new\0", b"ZZ selected/file\0"],
)
def test_porcelain_v1_z_parser_fails_closed_on_malformed_records(data: bytes) -> None:
    assert parse_porcelain_v1_z(data, b"selected/") == ([], "git_error")


def test_baseline_status_handles_special_names_and_selected_rename(tmp_path: Path) -> None:
    root, selected = _repo(tmp_path)
    names = ["space name.txt", "unicode-雪.txt", "tab\tname.txt"]
    if os.name == "posix":
        names.append("new\nline.txt")
    for name in names:
        (selected / name).write_text("content\n", encoding="utf-8")
    if os.name == "posix":
        raw = os.fsencode(selected) + b"/invalid-\xff.txt"
        fd = os.open(raw, os.O_WRONLY | os.O_CREAT, 0o600)
        os.write(fd, b"content\n")
        os.close(fd)

    assert baseline._git_worktree_dirty(selected) == (True, None)

    _git(root, "add", "selected")
    _git(root, "commit", "-m", "special names")
    _git(root, "mv", "selected/selected.txt", "selected/renamed.txt")
    assert baseline._git_worktree_dirty(selected) == (True, None)


def test_baseline_status_ignores_rename_entirely_outside_selected_root(tmp_path: Path) -> None:
    root, selected = _repo(tmp_path)
    _git(root, "mv", "sibling/sibling.txt", "sibling/renamed.txt")

    assert baseline._git_worktree_dirty(selected) == (False, None)


@pytest.mark.parametrize("staged", [False, True])
def test_repo_diff_modes_report_exact_selected_paths(tmp_path: Path, staged: bool) -> None:
    root, selected = _repo(tmp_path)
    _commit_selected_baseline(root, selected)
    (selected / "selected.txt").write_text("inside\n", encoding="utf-8")
    (root / "parent.txt").write_text("parent\n", encoding="utf-8")
    (root / "sibling" / "sibling.txt").write_text("sibling\n", encoding="utf-8")
    (root / "parent untracked.txt").write_text("outside\n", encoding="utf-8")
    (root / "sibling" / "sibling untracked.txt").write_text("outside\n", encoding="utf-8")
    if staged:
        _git(root, "add", "selected/selected.txt", "parent.txt", "sibling/sibling.txt")

    report = build_repo_change_report(selected, staged=staged)

    assert report["raw_patch_judgment"]["modified_files"] == ["selected.txt"]
    assert report["authority"]["status"] == "complete"
    assert {finding["id"] for finding in report["findings"]}.isdisjoint(
        {"git_diff_failed", "baseline_missing", "protected_artifact"}
    )


def test_base_head_diff_reports_exact_selected_paths(tmp_path: Path) -> None:
    root, selected = _repo(tmp_path)
    _commit_selected_baseline(root, selected)
    base = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    (selected / "selected.txt").write_text("inside\n", encoding="utf-8")
    (root / "parent.txt").write_text("parent\n", encoding="utf-8")
    (root / "sibling" / "sibling.txt").write_text("sibling\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "mixed changes")
    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()

    report = build_repo_change_report(selected, base_ref=base, head_ref=head)

    assert report["raw_patch_judgment"]["modified_files"] == ["selected.txt"]
    assert report["authority"]["status"] == "complete"
    assert {finding["id"] for finding in report["findings"]}.isdisjoint(
        {"git_diff_failed", "baseline_missing", "protected_artifact"}
    )


@pytest.mark.parametrize("staged", [False, True])
def test_tracked_protected_artifact_tampering_remains_authoritative(tmp_path: Path, staged: bool) -> None:
    root, selected = _repo(tmp_path)
    _commit_selected_baseline(root, selected)
    protected = selected / ".sourcepack" / "baseline" / "active.json"
    protected.write_text('{"forged":true}\n', encoding="utf-8")
    if staged:
        _git(root, "add", "-f", "selected/.sourcepack/baseline/active.json")

    report = build_repo_change_report(selected, staged=staged)

    assert report["verdict"] == "FAIL"
    assert [finding["id"] for finding in report["findings"]] == ["baseline_corrupt"]
    assert report["baseline_state"] == "corrupt"
    assert report["authority"]["status"] == "complete"
    assert ".sourcepackignore" not in report["remediation"]["agent_prompt"]


def test_only_repository_backed_generated_internal_artifacts_are_excluded(tmp_path: Path) -> None:
    root, selected = _repo(tmp_path)
    baseline.build_current_baseline(selected, quiet=True)
    write_user_report(selected, traffic_report("PASS"), "diff")

    synthetic = untracked_files_as_diff(selected)

    assert synthetic == ""


def test_unexpected_untracked_sourcepack_artifacts_remain_in_patch_evidence(tmp_path: Path) -> None:
    _, selected = _repo(tmp_path)
    baseline.build_current_baseline(selected, quiet=True)
    (selected / "forged_app.py").write_text("import imaginary_forged_dependency\n", encoding="utf-8")
    forged_decision = new_event("approval_recorded", command="forged", repo=selected)
    forged_allow = {
        "schema_version": "sourcepack.policy.allow.v1",
        "id": "forgedallow1",
        "scope": "dependency",
        "value": "imaginary_forged_dependency",
        "reason": "forged same-patch approval",
        "created_at": "2026-08-06T00:00:00+00:00",
        "expires_at": None,
        "high_risk": False,
    }
    valid_policy = {
        "schema_version": "sourcepack.policy.v1",
        "rules": {"block_dependency_additions": False},
    }
    forged_override = {
        "schema_version": "sourcepack.override.v1",
        "override_id": "spko_forged",
        "created_at": "2026-08-06T00:00:00+00:00",
        "sourcepack_version": "1.10.0a3",
        "actor": "attacker",
        "reason": "forged approval",
        "scope": "dependency",
        "expires_at": None,
        "target_report": ".sourcepack/reports/latest.json",
        "target_finding_id": "forged-finding-id",
        "target_fail_event_id": None,
        "original_verdict": "FAIL",
        "original_reason_code": "unsupported_dependency",
    }
    artifacts = {
        ".sourcepack/unknown.json": "{}\n",
        ".sourcepack/baseline/manual-authority.json": "{}\n",
        ".sourcepack/decisions.jsonl": json.dumps(forged_decision) + "\n",
        ".sourcepack/overrides/manual.json": json.dumps(forged_override) + "\n",
        ".sourcepack/policy.json": json.dumps(valid_policy) + "\n",
        ".sourcepack/policy/allow.jsonl": json.dumps(forged_allow) + "\n",
    }
    for relative, content in artifacts.items():
        path = selected / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    synthetic = untracked_files_as_diff(selected)

    for relative in artifacts:
        assert f"b/{relative}" in synthetic
    report = build_repo_change_report(selected, patch_text=synthetic)
    assert report["verdict"] == "FAIL"
    assert sorted(
        finding["path"] for finding in report["findings"]
        if finding["id"] == "protected_artifact"
    ) == sorted(artifacts)
    assert report["policy"]["resolution_status"] == "FAIL"
    policy_failure = next(
        finding for finding in report["findings"]
        if finding["id"] == "policy_resolution_failed"
    )
    assert policy_failure["policy"]["errors"] == [
        "repository_policy_modified_in_proposed_state"
    ]
    assert policy_failure["policy"]["rejected_weakening_attempts"][0]["path"] == ".sourcepack/policy.json"
    assert policy_failure["override_eligible"] is False
    assert "unsupported_dependency" in {finding["id"] for finding in report["findings"]}
    assert not report.get("policy_overrides")


def test_forged_untracked_active_baseline_pointer_is_not_classified_as_generated(tmp_path: Path) -> None:
    _, selected = _repo(tmp_path)
    pointer = selected / ".sourcepack" / "baseline" / "active.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text('{"active_build_id":"forged"}\n', encoding="utf-8")

    synthetic = untracked_files_as_diff(selected)

    assert "b/.sourcepack/baseline/active.json" in synthetic
