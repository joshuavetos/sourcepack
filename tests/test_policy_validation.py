import json
import subprocess
import sys
from pathlib import Path


def run_cli(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_policy(repo: Path, data):
    (repo / ".sourcepack").mkdir(exist_ok=True)
    (repo / ".sourcepack" / "policy.json").write_text(json.dumps(data), encoding="utf-8")


def snapshot(repo: Path):
    paths = []
    for path in sorted(repo.rglob("*")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(repo).as_posix()
        kind = "dir" if path.is_dir() else "file"
        content = path.read_bytes() if path.is_file() else b""
        paths.append((rel, kind, content))
    return paths


def test_policy_validate_missing_file_json_parseable_and_read_only(tmp_path):
    before = snapshot(tmp_path)
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert cp.stdout.lstrip().startswith("{")
    data = json.loads(cp.stdout)
    assert data["policy_present"] is False
    assert data["valid"] is True
    assert not (tmp_path / ".sourcepack" / "policy.json").exists()
    assert not (tmp_path / ".sourcepack" / "baseline").exists()
    assert not (tmp_path / ".sourcepack" / "prompt").exists()
    assert snapshot(tmp_path) == before


def test_policy_validate_missing_file_human(tmp_path):
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert cp.returncode == 0
    assert "No policy file found" in cp.stdout


def test_policy_validate_valid_policy_reports_effective_ignores(tmp_path):
    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "ignored_paths": [{"pattern": "docs/**", "reason": "reviewed docs"}]})
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert ".sourcepack/policy.json" in cp.stdout
    assert "docs/**" in cp.stdout
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_ignored_paths"] == [{"pattern": "docs/**", "reason": "reviewed docs"}]


def test_policy_validate_invalid_json_nonzero_json_parseable(tmp_path):
    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").write_text('{"ignored_paths": [', encoding="utf-8")
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode != 0
    data = json.loads(cp.stdout)
    assert data["valid"] is False
    assert any("policy_config_invalid_json" in error for error in data["errors"])
    human = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert human.returncode != 0
    assert "invalid JSON" in human.stdout
    assert ".sourcepack/policy.json" in human.stdout


def test_policy_validate_non_object_root_nonzero(tmp_path):
    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").write_text("[]", encoding="utf-8")
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode != 0
    data = json.loads(cp.stdout)
    assert data["errors"] == ["policy_config_invalid:root_must_be_object"]
    human = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert "policy root must be a JSON object" in human.stdout


def test_policy_validate_invalid_and_unsafe_ignored_entries_are_reported(tmp_path):
    write_policy(tmp_path, {"ignored_paths": ["bad", {"reason": "missing pattern"}, {"pattern": "docs/**"}, {"pattern": "", "reason": "empty"}, {"pattern": "docs/**", "reason": ""}, {"pattern": ".git", "reason": "unsafe"}, {"pattern": ".git/config", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline/**", "reason": "unsafe"}, {"pattern": "docs/**", "reason": "ok"}]})
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    warnings = "\n".join(data["warnings"])
    assert "policy_ignore_invalid:not_object" in warnings
    assert "policy_ignore_invalid:pattern_and_reason_required" in warnings
    assert "policy_ignore_unsafe:.git" in warnings
    assert "policy_ignore_unsafe:.git/config" in warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline" in warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline/**" in warnings
    assert data["effective_ignored_paths"] == [{"pattern": "docs/**", "reason": "ok"}]
    assert len(data["ignored_invalid_entries"]) == 9


def test_policy_validate_reserved_and_dangerous_fields_warn_without_authority(tmp_path):
    write_policy(tmp_path, {"strict_default": False, "fail_on_warn_in_ci": False, "protected_paths": ["docs/**"], "report_formats": ["json", "pdf"], "prompt_context_authoritative": True, "baseline_required_in_ci": False})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    warnings = set(data["warnings"])
    assert "policy_config_reserved:strict_default" in warnings
    assert "policy_config_reserved:fail_on_warn_in_ci" in warnings
    assert "policy_config_reserved:protected_paths" in warnings
    assert "policy_config_reserved:report_formats" in warnings
    assert "policy_config_ignored:prompt_context_authoritative" in warnings
    assert "policy_config_ignored:baseline_required_in_ci_false" in warnings
    assert "policy_report_format_ignored:pdf" in warnings
    assert data["effective_config"]["strict_default"] is True
    assert data["effective_config"]["fail_on_warn_in_ci"] is True
    assert data["effective_config"]["protected_paths"] == [".sourcepack/baseline/**", ".git/**"]
    assert data["effective_config"]["report_formats"] == ["json", "markdown", "html", "sarif"]
    assert data["effective_config"]["prompt_context_authoritative"] is False
    assert data["effective_config"]["baseline_required_in_ci"] is True


def test_policy_validate_json_stdout_only_and_no_mutation_of_state_dirs(tmp_path):
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "prompt").mkdir()
    (tmp_path / ".sourcepack" / "reports").mkdir()
    (tmp_path / ".sourcepack" / "evidence").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    write_policy(tmp_path, {"ignored_paths": [{"pattern": "docs/**", "reason": "ok"}]})
    before = snapshot(tmp_path)
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode == 0
    assert cp.stderr == ""
    assert cp.stdout.startswith("{")
    json.loads(cp.stdout)
    assert snapshot(tmp_path) == before


def test_policy_ignored_paths_allowlist_and_future_reason_remain_unsuppressible():
    from sourcepack.policy import PolicyConfig, finding_ignored_by_policy

    config = PolicyConfig(ignored_paths=({"pattern": "docs/**", "reason": "reviewed"},))
    assert finding_ignored_by_policy({"id": "new_file", "path": "docs/a.md"}, config)
    unsafe_config = PolicyConfig(ignored_paths=({"pattern": ".git", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline", "reason": "unsafe"}))
    assert finding_ignored_by_policy({"id": "new_file", "path": ".git/config"}, unsafe_config) is None
    assert finding_ignored_by_policy({"id": "new_file", "path": ".sourcepack/baseline/active.json"}, unsafe_config) is None
    for reason in ["unsupported_dependency", "git_path_modification", "baseline_missing", "future_unknown_reason"]:
        assert finding_ignored_by_policy({"id": reason, "path": "docs/a.md"}, config) is None
