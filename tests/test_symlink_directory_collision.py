from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sourcepack.diff_parser import PatchFileChange, parse_unified_diff
from sourcepack.judgment import _rebuild_from_findings, patch_report_to_traffic
from sourcepack.replay import reconstruct_replay
from sourcepack.reports.json import validate_report_construction_metadata
from sourcepack.worktree_collision import classify_symlink_target, inspect_symlink_transition, inspect_symlink_transitions


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "sourcepack@example.invalid")
    git(tmp_path, "config", "user.name", "SourcePack Test")
    (tmp_path / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
    git(tmp_path, "add", ".gitignore")
    git(tmp_path, "commit", "-qm", "initial")
    return tmp_path


def change(path: str = "books_out", target: str = "books") -> PatchFileChange:
    return PatchFileChange(path, path, old_mode="040000", new_mode="120000", added_lines=[target], proposed_symlink_target=target)


def inspect(repo: Path, proposed: PatchFileChange, **kwargs) -> dict:
    output = subprocess.run(["git", "ls-files", "-z"], cwd=repo, check=True, capture_output=True).stdout
    tracked = {item.decode().replace("\\", "/") for item in output.split(b"\0") if item}
    return inspect_symlink_transition(repo, proposed, tracked_paths=tracked, tracked_authority={"source": "test_trusted_inventory", "status": "complete", "complete": True, "reason": None}, **kwargs)


def incomplete_envelope(inspection: dict) -> dict:
    return {
        "inspections": [inspection], "transition_count_state": "exact", "transitions_consumed": 1,
        "transitions_retained": 1, "total_transitions": 1, "transition_limit_reached": False,
        "source_exhausted": False, "entries_inspected": inspection["entries_inspected"],
        "evidence_retained": len(inspection["retained_entries"]),
        "ignore_authority": {"status": "complete", "complete": True},
        "tracked_path_authority": inspection["tracked_path_authority"], "limits": {"transition_limit": 1},
    }


def test_parser_preserves_modes_and_symlink_blob_target() -> None:
    parsed = parse_unified_diff("""diff --git a/books_out b/books_out
old mode 100644
new mode 120000
--- a/books_out
+++ b/books_out
@@ -1 +1 @@
-old
+../books
""")[0]
    assert (parsed.old_mode, parsed.new_mode, parsed.proposed_symlink_target) == ("100644", "120000", "../books")

    unchanged_mode = parse_unified_diff("""diff --git a/link b/link
index 1111111..2222222 120000
--- a/link
+++ b/link
@@ -1 +1 @@
-old
+new
""")[0]
    assert (unchanged_mode.old_mode, unchanged_mode.new_mode, unchanged_mode.proposed_symlink_target) == ("120000", "120000", "new")


def test_absent_and_empty_paths_are_distinct_and_not_collisions(repo: Path) -> None:
    absent = inspect(repo, change())
    assert (absent["worktree_object_type"], absent["directory_nonempty"]) == ("absent", False)
    (repo / "books_out").mkdir()
    empty = inspect(repo, change())
    assert (empty["worktree_object_type"], empty["directory_nonempty"], empty["unrepresented_content_observed"]) == ("real_directory", False, False)


@pytest.mark.parametrize(("name", "ignored"), [("draft.txt", False), ("draft.ignored", True)])
def test_untracked_and_ignored_content_fail(repo: Path, name: str, ignored: bool) -> None:
    directory = repo / "books_out"
    directory.mkdir()
    (directory / name).write_text("sentinel", encoding="utf-8")
    inspection = inspect(repo, change())
    report = patch_report_to_traffic({"verdict": "FAIL", "symlink_directory_collisions": [inspection]})
    finding = next(item for item in report["findings"] if item["id"] == "symlink_replaces_nonempty_directory")
    assert report["verdict"] == "FAIL"
    assert finding["symlink_transition"]["ignored_observed"] is ignored
    assert finding["symlink_transition"]["untracked_observed"] is not ignored
    assert (directory / name).read_text(encoding="utf-8") == "sentinel"


def test_nested_content_is_deterministic_and_external_sentinel_unchanged(repo: Path, tmp_path: Path) -> None:
    directory = repo / "books_out" / "nested"
    directory.mkdir(parents=True)
    for name in ("z.txt", "a.txt"):
        (directory / name).write_text(name, encoding="utf-8")
    sentinel = tmp_path.parent / "external-sentinel"
    sentinel.write_text("outside", encoding="utf-8")
    first = inspect(repo, change())
    second = inspect(repo, change())
    assert first == second
    assert first["nested_entries_observed"] is True
    assert [item["path"] for item in first["retained_entries"]] == sorted(item["path"] for item in first["retained_entries"])
    assert sentinel.read_text(encoding="utf-8") == "outside"


def test_fully_tracked_nested_content_does_not_claim_hidden_data(repo: Path) -> None:
    path = repo / "books_out" / "tracked.txt"
    path.parent.mkdir()
    path.write_text("tracked", encoding="utf-8")
    git(repo, "add", "books_out/tracked.txt")
    inspection = inspect(repo, change())
    assert inspection["directory_nonempty"] is True
    assert inspection["unrepresented_content_observed"] is False
    assert inspection["untracked_observed"] is False
    assert inspection["ignored_observed"] is False


@pytest.mark.parametrize(("target", "classification"), [("books_out", "self_reference"), ("../../../outside", "escapes_repository"), ("/tmp/out", "absolute"), (r"C:\\out", "windows_drive_qualified"), ("books", "confined_relative")])
def test_target_classifications(repo: Path, target: str, classification: str) -> None:
    assert classify_symlink_target(repo, "books_out", target)["classification"] == classification


def test_direct_proposed_cycle_is_classified(repo: Path) -> None:
    transitions = inspect_symlink_transitions(repo, [change("a", "b"), change("b", "a")], tracked_paths=set(), tracked_authority={"source": "test", "status": "complete", "complete": True, "reason": None})["inspections"]
    assert [item["unsafe_target"]["classification"] for item in transitions] == ["direct_cycle", "direct_cycle"]


def test_symlinked_parent_is_not_followed(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-dir"
    outside.mkdir()
    (outside / "sentinel").write_text("safe", encoding="utf-8")
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    result = inspect(repo, change("linked/books_out"))
    assert result["acquisition_status"] == "failed_symlink_component"
    assert result["source_exhausted"] is False
    assert (outside / "sentinel").read_text(encoding="utf-8") == "safe"


def test_entry_and_depth_limits_are_lower_bounds_and_fail(repo: Path) -> None:
    directory = repo / "books_out" / "one" / "two"
    directory.mkdir(parents=True)
    (directory / "data").write_text("x", encoding="utf-8")
    entry_limited = inspect(repo, change(), entry_limit=1)
    depth_limited = inspect(repo, change(), depth_limit=0)
    for inspection in (entry_limited, depth_limited):
        assert inspection["source_exhausted"] is False
        assert inspection["entry_count_state"] == "lower_bound"
        report = patch_report_to_traffic({"verdict": "FAIL", "symlink_directory_collisions": [inspection] if inspection["unrepresented_content_observed"] else [], "symlink_worktree_inspection_incomplete": [inspection], "symlink_worktree_inspection": incomplete_envelope(inspection)})
        assert report["verdict"] == "FAIL"
        assert report["authority"]["complete"] is False


def test_read_failure_is_not_safe(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "books_out").mkdir()
    import sourcepack.worktree_collision as collision
    monkeypatch.setattr(collision.os, "listdir", lambda path: (_ for _ in ()).throw(PermissionError()))
    inspection = inspect(repo, change())
    assert inspection["acquisition_status"] == "read_failed"
    assert inspection["source_exhausted"] is False


@pytest.mark.parametrize("unsafe", ["", "/outside", "../outside", r"..\outside", r"C:\outside", "C:relative", r"\\server\share", r"\\?\C:\path"])
def test_direct_inspection_rejects_unsafe_change_paths(repo: Path, unsafe: str) -> None:
    proposed = change(unsafe)
    proposed.unsafe_path = False
    result = inspect(repo, proposed)
    assert result["acquisition_status"] == "unsafe_proposed_path"
    assert result["source_exhausted"] is False


@pytest.mark.parametrize(("target", "classification"), [
    (r"..\outside", "escapes_repository"),
    (r"\rooted", "windows_rooted"),
    (r"\\server\share", "windows_unc"),
    (r"\\?\C:\path", "windows_device_path"),
    (r"C:\path", "windows_drive_qualified"),
    ("C:relative", "windows_drive_qualified"),
    ("", "malformed"),
    ("safe/target", "confined_relative"),
])
def test_platform_neutral_target_classification(repo: Path, target: str, classification: str) -> None:
    result = classify_symlink_target(repo, "link", target)
    assert result["classification"] == classification
    assert result["unsafe"] is (classification != "confined_relative")


def test_custom_limits_are_enforced_and_reported_identically(repo: Path) -> None:
    directory = repo / "books_out"
    directory.mkdir()
    for name in ("a", "b"):
        (directory / name).write_text(name, encoding="utf-8")
    envelope = inspect_symlink_transitions(
        repo, [change()], tracked_paths=set(), tracked_authority={"source": "test", "status": "complete", "complete": True, "reason": None},
        transition_limit=3, total_entry_limit=4, per_transition_entry_limit=2, depth_limit=1,
        total_evidence_limit=1, per_transition_evidence_limit=1, string_limit=5,
        ignore_input_limit_bytes=1234, ignore_output_limit_bytes=2345,
    )
    inspection = envelope["inspections"][0]
    assert inspection["limits"] == envelope["limits"] == {
        "transition_limit": 3, "total_entry_limit": 4, "per_transition_entry_limit": 2,
        "depth_limit": 1, "total_evidence_limit": 1, "per_transition_evidence_limit": 1,
        "string_limit": 5, "ignore_input_limit_bytes": 1234, "ignore_output_limit_bytes": 2345,
    }
    assert inspection["evidence_retained"] == envelope["evidence_retained"] == 1
    assert inspection["evidence_limit_reached"] is envelope["evidence_limit_reached"] is True
    assert inspection["evidence_omitted_lower_bound"] == envelope["evidence_omitted_lower_bound"] == 1
    assert inspection["source_exhausted"] is True


def test_long_evidence_uses_full_path_for_identity_and_ignore(repo: Path) -> None:
    prefix = "x" * 40
    directory = repo / "books_out"
    directory.mkdir()
    (directory / f"{prefix}a.ignored").write_text("a", encoding="utf-8")
    (directory / f"{prefix}b").write_text("b", encoding="utf-8")
    result = inspect_symlink_transition(
        repo, change(), tracked_paths=set(),
        tracked_authority={"source": "test", "status": "complete", "complete": True, "reason": None},
        string_limit=12,
    )
    assert result["ignored_observed"] is True
    assert result["untracked_observed"] is True
    assert len(result["retained_entries"]) == 2
    assert all(item["path_truncated"] for item in result["retained_entries"])


def test_evidence_exact_boundary_is_not_exhausted(repo: Path) -> None:
    directory = repo / "books_out"
    directory.mkdir()
    (directory / "only").write_text("x", encoding="utf-8")
    result = inspect(repo, change(), evidence_limit=1)
    assert result["evidence_retained"] == 1
    assert result["evidence_limit_reached"] is False
    assert result["evidence_omitted_lower_bound"] == 0


def test_report_json_and_replay_preserve_finding_and_incomplete_authority(repo: Path, tmp_path: Path) -> None:
    (repo / "books_out").mkdir()
    (repo / "books_out" / "hidden").write_text("x", encoding="utf-8")
    inspection = inspect(repo, change(), entry_limit=0)
    report = patch_report_to_traffic({"verdict": "FAIL", "symlink_directory_collisions": [], "symlink_worktree_inspection_incomplete": [inspection], "symlink_worktree_inspection": incomplete_envelope(inspection)})
    loaded = json.loads(json.dumps(report))
    validate_report_construction_metadata(loaded)
    saved = tmp_path / "report.json"
    saved.write_text(json.dumps(loaded), encoding="utf-8")
    replayed, exit_code = reconstruct_replay(saved)
    assert loaded["findings"][0]["symlink_transition"]["entry_count_state"] == "lower_bound"
    assert loaded["reason_code_evidence"]["symlink_worktree_inspection_incomplete"]
    assert loaded["replay_bundle"]["authority"]["complete"] is False
    rebuilt = _rebuild_from_findings(loaded, loaded["findings"])
    assert rebuilt["authority"]["complete"] is False
    assert rebuilt["replay_bundle"]["authority"]["complete"] is False
    assert exit_code == 0
    assert replayed["verdict"] == "FAIL"


def test_current_resulting_symlink_records_unavailable_historical_state(repo: Path) -> None:
    (repo / "books_out").symlink_to("books")
    inspection = inspect(repo, change())
    assert inspection["worktree_object_type"] == "symlink"
    assert inspection["worktree_evidence_phase"] == "current_post_transition_observation"
    assert inspection["pre_transition_state"] == "unavailable"
    assert inspection["source_exhausted"] is False


def test_many_transitions_use_one_batched_ignore_call_and_global_limits(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sourcepack.worktree_collision as collision
    for index in range(4):
        directory = repo / f"link-{index}"
        directory.mkdir()
        (directory / "hidden").write_text("x", encoding="utf-8")
    calls = []
    real = collision.run_git_bounded_input

    def counted(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(collision, "run_git_bounded_input", counted)
    changes = [change(f"link-{index}") for index in range(4)]
    envelope = inspect_symlink_transitions(repo, changes, tracked_paths=set(), tracked_authority={"source": "test", "status": "complete", "complete": True, "reason": None}, transition_limit=2, total_entry_limit=2)
    assert len(calls) == 1
    assert envelope["transition_count_state"] == "lower_bound"
    assert envelope["transition_limit_reached"] is True
    assert envelope["entries_inspected"] <= 2
    assert envelope["source_exhausted"] is False


def test_validator_rejects_contradictory_incomplete_producers(repo: Path) -> None:
    (repo / "books_out").mkdir()
    (repo / "books_out" / "hidden").write_text("x", encoding="utf-8")
    inspection = inspect(repo, change(), entry_limit=0)
    report = patch_report_to_traffic({"verdict": "FAIL", "symlink_directory_collisions": [], "symlink_worktree_inspection_incomplete": [inspection], "symlink_worktree_inspection": incomplete_envelope(inspection)})
    report["construction_bounds"]["git_diff"] = {"acquisition_state": "failed", "count_state": "lower_bound", "source_exhausted": False, "limit_reached": False}
    with pytest.raises(ValueError, match="explicit producer-incomplete authority"):
        validate_report_construction_metadata(report)


def test_failed_ignore_batch_does_not_claim_untracked(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sourcepack.worktree_collision as collision
    directory = repo / "books_out"
    directory.mkdir()
    (directory / "hidden").write_text("x", encoding="utf-8")
    failed = subprocess.CompletedProcess(["git", "check-ignore"], 124, b"", b"timeout")
    failed.acquisition_state = "failed"
    monkeypatch.setattr(collision, "run_git_bounded_input", lambda *args, **kwargs: failed)
    envelope = inspect_symlink_transitions(repo, [change()], tracked_paths=set(), tracked_authority={"source": "test", "status": "complete", "complete": True, "reason": None})
    inspection = envelope["inspections"][0]
    assert envelope["ignore_authority"]["reason"] == "git_timeout"
    assert inspection["ignore_classification_state"] == "failed"
    assert inspection["ignored_observed"] is False
    assert inspection["untracked_observed"] is False
    assert inspection["source_exhausted"] is False
