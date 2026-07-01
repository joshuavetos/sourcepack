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
