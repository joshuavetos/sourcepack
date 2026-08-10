from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sourcepack.local_allow_trust import (
    ACTIVE_ALLOW_LIMIT_BYTES,
    ACTIVE_ALLOW_LINE_LIMIT_BYTES,
    ACTIVE_ALLOW_RECORD_LIMIT,
    active_allows_path,
    canonical_allow_record,
)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Tests"], cwd=path, check=True)
    (path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, stdout=subprocess.PIPE)
    baseline = _run(path, "baseline", "refresh", "--force")
    assert baseline.returncode == 0, baseline.stderr + baseline.stdout
    return path


def _allow_record(value: str) -> dict:
    return {
        "schema_version": "sourcepack.policy.allow.v1",
        "id": "forgedallow1",
        "scope": "dependency",
        "value": value,
        "reason": "forged",
        "created_at": "2026-08-09T00:00:00+00:00",
        "expires_at": None,
        "high_risk": False,
    }


def _write_allow(repo: Path, record: dict, *, append: bool = False) -> None:
    path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if append else "w", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _diff(repo: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = _run(repo, "diff", ".", "--json")
    return cp, json.loads(cp.stdout)


def _unsupported(report: dict) -> set[str]:
    return {
        str(finding.get("evidence"))
        for finding in report["findings"]
        if finding["id"] == "unsupported_dependency"
    }


def test_cli_allow_is_trusted_immediately_without_git_commit(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import immediate_dependency\n", encoding="utf-8")

    allowed = _run(repo, "allow", "dependency", "immediate_dependency", "--reason", "reviewed")
    cp, report = _diff(repo)

    assert allowed.returncode == 0
    assert cp.returncode == 0
    assert report["verdict"] == "PASS"
    assert _unsupported(report) == set()
    assert report["policy_overrides"][0]["value"] == "immediate_dependency"
    assert subprocess.run(["git", "ls-files", ".sourcepack/policy/allow.jsonl"], cwd=repo, text=True, stdout=subprocess.PIPE).stdout == ""


def test_cli_disallow_immediately_revokes_permission(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import revoked_dependency\n", encoding="utf-8")
    assert _run(repo, "allow", "dependency", "revoked_dependency", "--reason", "reviewed").returncode == 0
    assert _diff(repo)[1]["verdict"] == "PASS"

    removed = _run(repo, "disallow", "dependency", "revoked_dependency")
    cp, report = _diff(repo)

    assert removed.returncode == 0
    assert removed.stdout.strip() == "Removed active dependency permission for revoked_dependency"
    assert cp.returncode == 1
    assert _unsupported(report) == {"revoked_dependency"}
    assert not report.get("policy_overrides")


def test_restoring_repo_record_after_disallow_does_not_restore_permission(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import replayed_dependency\n", encoding="utf-8")
    assert _run(repo, "allow", "dependency", "replayed_dependency", "--reason", "reviewed").returncode == 0
    allow_path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    old_record = allow_path.read_text(encoding="utf-8")
    assert _run(repo, "disallow", "dependency", "replayed_dependency").returncode == 0
    allow_path.parent.mkdir(parents=True, exist_ok=True)
    allow_path.write_text(old_record, encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"replayed_dependency"}
    assert report["policy"]["resolution_status"] == "FAIL"
    assert "protected_artifact" in {finding["id"] for finding in report["findings"]}
    assert not report.get("policy_overrides")


def test_manual_valid_allow_is_untrusted(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import manual_dependency\n", encoding="utf-8")
    _write_allow(repo, _allow_record("manual_dependency"))

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["verdict"] == "FAIL"
    assert _unsupported(report) == {"manual_dependency"}
    assert "protected_artifact" in {finding["id"] for finding in report["findings"]}
    assert report["policy"]["resolution_status"] == "FAIL"
    assert not report.get("policy_overrides")


def test_altering_readable_allow_does_not_create_active_permission(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    assert _run(repo, "allow", "dependency", "original_dependency", "--reason", "reviewed").returncode == 0
    path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["value"] = "altered_dependency"
    _write_allow(repo, record)
    (repo / "app.py").write_text("import altered_dependency\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"altered_dependency"}
    assert not report.get("policy_overrides")


def test_appended_forged_allow_invalidates_current_policy_authority(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    assert _run(repo, "allow", "dependency", "real_dependency", "--reason", "reviewed").returncode == 0
    _write_allow(repo, _allow_record("forged_dependency"), append=True)
    (repo / "app.py").write_text("import real_dependency\nimport forged_dependency\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["verdict"] == "FAIL"
    assert _unsupported(report) == {"forged_dependency", "real_dependency"}
    assert not report.get("policy_overrides")
    assert "protected_artifact" in {finding["id"] for finding in report["findings"]}


def test_active_allow_is_bound_to_exact_repository(tmp_path: Path) -> None:
    repo_a = _repo(tmp_path / "repo-a")
    repo_b = _repo(tmp_path / "repo-b")
    assert _run(repo_a, "allow", "dependency", "copied_dependency", "--reason", "reviewed").returncode == 0
    destination = repo_b / ".sourcepack" / "policy" / "allow.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_a / ".sourcepack" / "policy" / "allow.jsonl", destination)
    (repo_b / "app.py").write_text("import copied_dependency\n", encoding="utf-8")

    cp, report = _diff(repo_b)

    assert cp.returncode == 1
    assert _unsupported(report) == {"copied_dependency"}
    assert not report.get("policy_overrides")


def test_same_patch_valid_allow_cannot_authorize_dependency(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import same_patch_dependency\n", encoding="utf-8")
    _write_allow(repo, _allow_record("same_patch_dependency"))

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"same_patch_dependency"}
    assert report["policy"]["resolution_status"] == "FAIL"
    assert "policy_resolution_failed" in {finding["id"] for finding in report["findings"]}
    assert not report.get("policy_overrides")


def test_expired_active_allow_does_not_suppress_finding(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "app.py").write_text("import expired_dependency\n", encoding="utf-8")
    expiry = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    allowed = _run(repo, "allow", "dependency", "expired_dependency", "--reason", "expired", "--expires", expiry)

    cp, report = _diff(repo)

    assert allowed.returncode == 0
    assert cp.returncode == 1
    assert _unsupported(report) == {"expired_dependency"}
    assert not report.get("policy_overrides")


def test_active_allow_file_contains_repository_bound_permission_fields(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    allowed = _run(repo, "allow", "dependency", "recorded_dependency", "--reason", "reviewed")
    record = json.loads(active_allows_path().read_text(encoding="utf-8"))

    assert allowed.returncode == 0
    assert record == {
        "repository_path": str(repo.resolve()),
        **json.loads((repo / ".sourcepack" / "policy" / "allow.jsonl").read_text(encoding="utf-8")),
    }
    assert active_allows_path().read_text(encoding="utf-8") == canonical_allow_record(record) + "\n"


def test_sourcepack_home_at_repository_root_is_rejected(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(repo))
    (repo / "app.py").write_text("import repository_home_dependency\n", encoding="utf-8")
    authority = repo / "trust" / "active_allows.jsonl"
    authority.parent.mkdir(parents=True)
    authority.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("repository_home_dependency")}) + "\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["verdict"] == "FAIL"
    assert _unsupported(report) == {"repository_home_dependency"}
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
    assert "policy_resolution_failed" in {finding["id"] for finding in report["findings"]}
    assert not report.get("policy_overrides")


def test_sourcepack_home_dot_directory_below_repository_is_rejected(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    inside_home = repo / ".sourcepack-home"
    monkeypatch.setenv("SOURCEPACK_HOME", str(inside_home))
    (repo / "app.py").write_text("import dot_home_dependency\n", encoding="utf-8")
    authority = inside_home / "trust" / "active_allows.jsonl"
    authority.parent.mkdir(parents=True)
    authority.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("dot_home_dependency")}) + "\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"dot_home_dependency"}
    assert report["authority"]["complete"] is False
    assert report["authority"]["reason"] == "local_policy_acquisition_failed"
    assert not report.get("policy_overrides")


def test_sourcepack_home_below_repository_is_rejected(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    inside_home = repo / "subfolder" / "trust"
    monkeypatch.setenv("SOURCEPACK_HOME", str(inside_home))
    (repo / "app.py").write_text("import nested_home_dependency\n", encoding="utf-8")
    authority = inside_home / "trust" / "active_allows.jsonl"
    authority.parent.mkdir(parents=True)
    authority.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("nested_home_dependency")}) + "\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"nested_home_dependency"}
    assert report["authority"]["complete"] is False
    assert report["authority"]["reason"] == "local_policy_acquisition_failed"
    assert not report.get("policy_overrides")


def test_sourcepack_home_symlink_resolving_into_repository_is_rejected(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    inside_home = repo / "internal-trust-home"
    inside_home.mkdir()
    linked_home = tmp_path / "linked-sourcepack-home"
    try:
        linked_home.symlink_to(inside_home, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest

        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setenv("SOURCEPACK_HOME", str(linked_home))
    (repo / "app.py").write_text("import symlink_home_dependency\n", encoding="utf-8")
    authority = inside_home / "trust" / "active_allows.jsonl"
    authority.parent.mkdir()
    authority.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("symlink_home_dependency")}) + "\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"symlink_home_dependency"}
    assert report["authority"]["complete"] is False
    assert report["authority"]["reason"] == "local_policy_acquisition_failed"
    assert not report.get("policy_overrides")


def test_default_sourcepack_home_symlink_resolving_into_repository_is_rejected(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    inside_home = repo / "default-trust-home"
    inside_home.mkdir()
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    try:
        (user_home / ".sourcepack").symlink_to(inside_home, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest

        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.delenv("SOURCEPACK_HOME")
    monkeypatch.setenv("HOME", str(user_home))
    (repo / "app.py").write_text("import default_symlink_dependency\n", encoding="utf-8")
    authority = inside_home / "trust" / "active_allows.jsonl"
    authority.parent.mkdir()
    authority.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("default_symlink_dependency")}) + "\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert _unsupported(report) == {"default_symlink_dependency"}
    assert report["authority"]["complete"] is False
    assert report["authority"]["reason"] == "local_policy_acquisition_failed"
    assert not report.get("policy_overrides")


def test_external_sourcepack_home_accepts_active_allow(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path / "external-home"))
    (repo / "app.py").write_text("import external_home_dependency\n", encoding="utf-8")

    assert _run(repo, "allow", "dependency", "external_home_dependency", "--reason", "reviewed").returncode == 0
    cp, report = _diff(repo)

    assert cp.returncode == 0
    assert report["authority"] == {"status": "complete", "complete": True, "reason": None}
    assert _unsupported(report) == set()


def test_sourcepack_home_trust_child_symlink_into_repository_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    home = tmp_path / "external-home"
    home.mkdir()
    inside = repo / "authority"
    inside.mkdir()
    try:
        (home / "trust").symlink_to(inside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setenv("SOURCEPACK_HOME", str(home))
    (repo / "app.py").write_text("import child_link_dependency\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
    assert _unsupported(report) == {"child_link_dependency"}
    assert not report.get("policy_overrides")


def test_sourcepack_home_final_authority_symlink_into_repository_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    home = tmp_path / "external-home"
    trust = home / "trust"
    trust.mkdir(parents=True)
    inside = repo / "active_allows.jsonl"
    inside.write_text(canonical_allow_record({"repository_path": str(repo.resolve()), **_allow_record("final_link_dependency")}) + "\n", encoding="utf-8")
    try:
        (trust / "active_allows.jsonl").symlink_to(inside)
    except (OSError, NotImplementedError) as exc:
        import pytest
        pytest.skip(f"file symlinks are unavailable: {exc}")
    monkeypatch.setenv("SOURCEPACK_HOME", str(home))
    (repo / "app.py").write_text("import final_link_dependency\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
    assert _unsupported(report) == {"final_link_dependency"}
    assert not report.get("policy_overrides")


def test_malformed_other_repository_record_does_not_poison_current_repository(monkeypatch, tmp_path: Path) -> None:
    repo_a = _repo(tmp_path / "repo-a")
    repo_b = _repo(tmp_path / "repo-b")
    home = tmp_path / "shared-home"
    monkeypatch.setenv("SOURCEPACK_HOME", str(home))
    authority = active_allows_path(repo_b)
    authority.parent.mkdir(parents=True)
    authority.write_text(json.dumps({"repository_path": str(repo_a.resolve()), "id": "malformed-a"}) + "\n", encoding="utf-8")
    (repo_b / "app.py").write_text("import isolated_dependency\n", encoding="utf-8")

    cp, report = _diff(repo_b)

    assert cp.returncode == 1
    assert report["authority"] == {"status": "complete", "complete": True, "reason": None}
    assert _unsupported(report) == {"isolated_dependency"}
    assert "local_policy_acquisition_failed" not in {finding.get("message", "") for finding in report["findings"]}


def test_malformed_current_repository_record_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path / "shared-home"))
    authority = active_allows_path(repo)
    authority.parent.mkdir(parents=True)
    authority.write_text(json.dumps({"repository_path": str(repo.resolve()), "id": "malformed-current"}) + "\n", encoding="utf-8")
    (repo / "app.py").write_text("import relevant_malformed_dependency\n", encoding="utf-8")

    cp, report = _diff(repo)

    assert cp.returncode == 1
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
    assert _unsupported(report) == {"relevant_malformed_dependency"}
    assert not report.get("policy_overrides")


def _assert_external_authority_limit_fails(repo: Path, authority: Path) -> None:
    (repo / "app.py").write_text("import bounded_dependency\n", encoding="utf-8")
    cp, report = _diff(repo)
    assert cp.returncode == 1
    assert report["authority"] == {"status": "incomplete", "complete": False, "reason": "local_policy_acquisition_failed"}
    assert _unsupported(report) == {"bounded_dependency"}
    assert not report.get("policy_overrides")


def test_active_allow_authority_total_byte_limit_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path / "home"))
    authority = active_allows_path(repo)
    authority.parent.mkdir(parents=True)
    authority.write_bytes(b" " * (ACTIVE_ALLOW_LIMIT_BYTES + 1))
    _assert_external_authority_limit_fails(repo, authority)


def test_active_allow_authority_line_limit_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path / "home"))
    authority = active_allows_path(repo)
    authority.parent.mkdir(parents=True)
    authority.write_bytes(b" " * (ACTIVE_ALLOW_LINE_LIMIT_BYTES + 1) + b"\n")
    _assert_external_authority_limit_fails(repo, authority)


def test_active_allow_authority_record_limit_fails_closed(monkeypatch, tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("SOURCEPACK_HOME", str(tmp_path / "home"))
    authority = active_allows_path(repo)
    authority.parent.mkdir(parents=True)
    authority.write_text("{}\n" * (ACTIVE_ALLOW_RECORD_LIMIT + 1), encoding="utf-8")
    _assert_external_authority_limit_fails(repo, authority)


def test_disallow_last_permission_restores_clean_next_review(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    original = (repo / "app.py").read_text(encoding="utf-8")
    (repo / "app.py").write_text("import lifecycle_dependency\n", encoding="utf-8")
    assert _run(repo, "allow", "dependency", "lifecycle_dependency", "--reason", "reviewed").returncode == 0
    assert _diff(repo)[1]["verdict"] == "PASS"

    assert _run(repo, "disallow", "dependency", "lifecycle_dependency").returncode == 0
    (repo / "app.py").write_text(original, encoding="utf-8")
    allow_path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    cp, report = _diff(repo)

    assert not allow_path.exists()
    assert cp.returncode == 0
    assert report["verdict"] == "PASS"
    assert [finding["id"] for finding in report["findings"]] == ["no_diff"]
    assert report["authority"] == {"status": "complete", "complete": True, "reason": None}


def test_disallow_removes_readable_file_only_after_last_permission(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    allow_path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    assert _run(repo, "allow", "dependency", "first_dependency", "--reason", "first").returncode == 0
    assert _run(repo, "allow", "dependency", "second_dependency", "--reason", "second").returncode == 0

    assert _run(repo, "disallow", "dependency", "first_dependency").returncode == 0
    assert allow_path.exists()
    assert [json.loads(line)["value"] for line in allow_path.read_text(encoding="utf-8").splitlines()] == ["second_dependency"]
    assert _run(repo, "disallow", "dependency", "second_dependency").returncode == 0
    assert not allow_path.exists()


def test_policy_authority_failure_preserves_independent_finding_then_allow_recovers(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    assert _run(repo, "allow", "dependency", "ordered_dependency", "--reason", "reviewed").returncode == 0
    (repo / "app.py").write_text("import ordered_dependency\n", encoding="utf-8")
    policy = repo / ".sourcepack" / "policy.json"
    policy.write_text(json.dumps({"schema_version": "sourcepack.policy.v1", "rules": {}}), encoding="utf-8")

    failed_cp, failed = _diff(repo)
    failed_ids = {finding["id"] for finding in failed["findings"]}
    assert failed_cp.returncode == 1
    assert "policy_resolution_failed" in failed_ids
    assert "unsupported_dependency" in failed_ids
    assert _unsupported(failed) == {"ordered_dependency"}
    assert not failed.get("policy_overrides")

    policy.unlink()
    allowed_cp, allowed = _diff(repo)
    assert allowed_cp.returncode == 0
    assert allowed["verdict"] == "PASS"
    assert _unsupported(allowed) == set()
    assert allowed["policy_overrides"][0]["value"] == "ordered_dependency"
