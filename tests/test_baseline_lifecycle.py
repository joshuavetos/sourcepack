from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def json_cli(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = run_cli(repo, *args)
    return cp, json.loads(cp.stdout)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)
    (repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return repo


def create_baseline(repo: Path) -> dict:
    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] in {"PASS", "WARN"}
    return data


def active_build(repo: Path) -> Path:
    active = json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text(encoding="utf-8"))
    return repo / ".sourcepack" / "baseline" / "builds" / active["active_build_id"]


def finding_ids(data: dict) -> set[str]:
    return {f.get("id") for f in data.get("findings", [])}


def assert_ci_diff_fails_closed(repo: Path, expected_id: str) -> dict:
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode != 0
    assert data["verdict"] == "FAIL"
    assert data.get("baseline_integrity_finding_id") == expected_id or expected_id in finding_ids(data)
    return data


def test_baseline_absent_fails_closed_and_prompt_does_not_satisfy_requirement(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".sourcepack" / "prompt" / "packet").mkdir(parents=True)
    (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").write_text("{}", encoding="utf-8")
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"
    assert not (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_active_json_missing_reports_missing_pointer_and_ci_fails_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".sourcepack" / "baseline").mkdir(parents=True)
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "missing"
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"


def test_active_json_points_to_missing_build_fails_verification_and_ci(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    baseline = repo / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    (baseline / "active.json").write_text(json.dumps({"active_build_id": "missing-build"}), encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_corrupt_active_json_fails_verification_ci_and_json_remains_parseable(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    baseline = repo / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    (baseline / "active.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_corrupt_build_metadata_fails_verification_and_ci(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (active_build(repo) / "metadata.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_missing_required_packet_file_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (active_build(repo) / "packet" / "manifest.json").unlink()
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_extra_inactive_build_does_not_affect_active_baseline_or_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    inactive = repo / ".sourcepack" / "baseline" / "builds" / "inactive-build" / "packet"
    inactive.mkdir(parents=True)
    (inactive / "manifest.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 0
    assert status["state"] == "present"
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["verdict"] == "PASS"
    assert data["baseline_state"] == "present"
    assert "no_diff" in finding_ids(data)


def test_prompt_only_state_with_no_baseline_fails_ci_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    cp = run_cli(repo, "prompt", ".", "test task", "--json")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists()
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"
    assert not (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_baseline_present_and_clean_verifies_and_diff_passes_no_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 0
    assert status["state"] == "present"
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["verdict"] == "PASS"
    assert data["baseline_state"] == "present"
    assert "no_diff" in finding_ids(data)


def test_baseline_present_with_tracked_file_changed_has_no_baseline_failure_or_prompt_involvement(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["baseline_state"] == "present"
    assert data.get("baseline_integrity_finding_id") is None
    ids = finding_ids(data)
    assert "baseline_missing" not in ids
    assert "baseline_corrupt" not in ids
    assert not (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists()


def test_baseline_refuses_dirty_git_worktree_without_force_before_sourcepack_mutation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")

    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet")

    assert cp.returncode == 1
    assert data["verdict"] == "FAIL"
    assert "dirty working tree" in data["findings"][0]["message"]
    assert not (repo / ".sourcepack").exists()


def test_baseline_force_permits_dirty_git_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "scratch.txt").write_text("trusted intentionally\n", encoding="utf-8")

    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet", "--force")

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] == "WARN"
    assert (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_init_auto_refuses_dirty_git_worktree_without_force_before_sourcepack_mutation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")

    cp = run_cli(repo, "init", ".", "--auto")

    assert cp.returncode == 1
    assert "dirty working tree" in cp.stdout
    assert not (repo / ".sourcepack").exists()
    assert not (repo / ".sourcepackignore").exists()
    assert not (repo / "sourcepack.config.json").exists()


def test_init_auto_force_permits_dirty_git_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")

    cp = run_cli(repo, "init", ".", "--auto", "--force", "--no-hook")

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert (repo / ".sourcepack" / "baseline" / "active.json").exists()


def _receipt_path(repo: Path) -> Path:
    return active_build(repo) / "packet" / "receipt.json"


def _read_receipt(repo: Path) -> dict:
    return json.loads(_receipt_path(repo).read_text(encoding="utf-8"))


def _write_receipt(repo: Path, receipt: dict) -> None:
    _receipt_path(repo).write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def _assert_verify_corrupt_reason(repo: Path, reason: str) -> dict:
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode != 0
    assert status["state"] == "corrupt"
    assert reason in status["details"]["reason"]
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"
    return status


def test_receipt_absolute_artifact_path_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    receipt = _read_receipt(repo)
    receipt["hashes"]["/tmp/outside.txt"] = "0" * 64
    _write_receipt(repo, receipt)

    _assert_verify_corrupt_reason(repo, "receipt.json tracks unsafe artifact path")


def test_receipt_traversal_artifact_path_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    receipt = _read_receipt(repo)
    receipt["hashes"]["../outside.txt"] = "0" * 64
    _write_receipt(repo, receipt)

    _assert_verify_corrupt_reason(repo, "receipt.json tracks unsafe artifact path")


def test_receipt_missing_tracked_artifact_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    receipt = _read_receipt(repo)
    receipt["hashes"]["missing-artifact.txt"] = "0" * 64
    _write_receipt(repo, receipt)

    _assert_verify_corrupt_reason(repo, "receipt-tracked artifact missing")


def test_receipt_hash_mismatch_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    packet = active_build(repo) / "packet"
    receipt = _read_receipt(repo)
    tracked_name = "context.md"
    assert tracked_name in receipt["hashes"]
    (packet / tracked_name).write_text("tampered\n", encoding="utf-8")

    _assert_verify_corrupt_reason(repo, "receipt hash mismatch")


def test_receipt_invalid_hash_entry_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    receipt = _read_receipt(repo)
    receipt["hashes"]["manifest.json"] = 123
    _write_receipt(repo, receipt)

    _assert_verify_corrupt_reason(repo, "receipt.json contains invalid hash entry")


def git_commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cp = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return cp.stdout.strip()


def test_committed_range_empty_returns_pass_no_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    head = git_commit(repo, "commit trusted baseline")

    cp, data = json_cli(repo, "diff", ".", "--ci", "--json", "--base-ref", head, "--head-ref", head)

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] == "PASS"
    assert "no_diff" in finding_ids(data)


def test_committed_range_mode_catches_committed_changes_in_clean_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    base = git_commit(repo, "commit trusted baseline")
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
    head = git_commit(repo, "change tracked file")

    clean_cp = subprocess.run(["git", "status", "--short"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert clean_cp.stdout == ""
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json", "--base-ref", base, "--head-ref", head)

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] == "PASS"
    ids = finding_ids(data)
    assert "no_diff" not in ids
    assert "app.py" in data.get("raw_patch_judgment", {}).get("modified_files", [])


def test_committed_range_mode_reports_binary_changes_with_text_changes(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    base = git_commit(repo, "commit trusted baseline")
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
    (repo / "image.bin").write_bytes(b"\x00\x01\x02\x03")
    head = git_commit(repo, "change text and add binary")

    clean_cp = subprocess.run(["git", "status", "--short"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert clean_cp.stdout == ""
    raw_diff = subprocess.run(["git", "diff", base + "..." + head], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    assert "Binary files" in raw_diff
    assert "GIT binary patch" not in raw_diff

    cp, data = json_cli(repo, "diff", ".", "--ci", "--json", "--base-ref", base, "--head-ref", head)

    assert cp.returncode != 0
    assert data["verdict"] == "WARN"
    assert "binary_diff" in finding_ids(data)
    assert data.get("raw_patch_judgment", {}).get("binary_diffs") == ["image.bin"]
    assert "app.py" in data.get("raw_patch_judgment", {}).get("modified_files", [])
    assert "no_diff" not in finding_ids(data)

def test_committed_range_preserves_missing_file_behavior_for_clean_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    base = git_commit(repo, "commit trusted baseline")
    (repo / "new_notes.md").write_text("notes\n", encoding="utf-8")
    head = git_commit(repo, "add untrusted file")

    clean_cp = subprocess.run(["git", "status", "--short"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert clean_cp.stdout == ""
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json", "--base-ref", base, "--head-ref", head)

    assert cp.returncode != 0
    assert data["verdict"] == "WARN"
    assert "new_file" in finding_ids(data)
    assert any(finding.get("path") == "new_notes.md" for finding in data.get("findings", []))
    assert "no_diff" not in finding_ids(data)
