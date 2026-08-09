import json
import stat
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


def test_policy_validate_rules_missing_and_empty_are_noop(tmp_path):
    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1"})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_config"]["rules"] == {
        "block_dependency_additions": False,
        "protected_paths": [],
        "package_manager": None,
        "require_tests_for": [],
        "max_changed_lines": None,
        "block_secret_patterns": False,
    }

    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "rules": {}})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_config"]["rules"]["protected_paths"] == []
    assert data["effective_config"]["rules"]["block_secret_patterns"] is False


def test_policy_validate_rules_reports_effective_rules_and_warnings(tmp_path):
    write_policy(tmp_path, {
        "schema_version": "sourcepack.policy.v1",
        "rules": {
            "block_dependency_additions": True,
            "protected_paths": ["src/auth/**", "/abs", "../escape"],
            "package_manager": "pnpm",
            "require_tests_for": ["src/api/**", ""],
            "max_changed_lines": 800,
            "block_secret_patterns": True,
        },
    })
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["valid"] is False
    assert data["effective_config"]["rules"] == {
        "block_dependency_additions": True,
        "protected_paths": [],
        "package_manager": "pnpm",
        "require_tests_for": [],
        "max_changed_lines": 800,
        "block_secret_patterns": True,
    }
    errors = "\n".join(data["errors"])
    assert "repository_policy_rule_invalid:protected_paths:/abs" in errors
    assert "repository_policy_rule_invalid:require_tests_for:" in errors


def test_policy_rule_types_unknown_names_and_non_string_paths_fail_closed(tmp_path):
    cases = [
        {"block_dependency_additions": "false"},
        {"protected_paths": [7]},
        {"future_rul": True},
    ]
    for rules in cases:
        write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "rules": rules})
        cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
        assert cp.returncode != 0
        assert json.loads(cp.stdout)["valid"] is False


def test_policy_paths_reject_cross_platform_unsafe_spellings_and_match_case_sensitively():
    from sourcepack.policy import _normalize_policy_path, policy_path_matches

    for value in [7, "C:\\escape", "\\\\server\\share", "\\\\?\\C:\\escape", "a\r/b", "a\n/b", "a//b", "a/./b", "a/../b"]:
        assert _normalize_policy_path(value) is None
    assert _normalize_policy_path("src/**") == "src/**"
    assert policy_path_matches("src/App.py", "src/*.py") is True
    assert policy_path_matches("src/App.py", "src/app.py") is False


def test_unknown_policy_mode_fails_closed():
    import pytest
    from sourcepack.policy import exit_code, normalize_policy_mode

    with pytest.raises(ValueError, match="unknown policy mode"):
        normalize_policy_mode("strcit")
    with pytest.raises(ValueError, match="unknown policy mode"):
        exit_code("WARN", "strcit")


def test_dangling_repository_policy_symlink_is_invalid(tmp_path):
    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    (policy_dir / "policy.json").symlink_to(policy_dir / "missing.json")
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["policy_present"] is True
    assert data["valid"] is False


def test_repository_policy_acquisition_owns_missing_and_presence_observation(tmp_path, monkeypatch):
    from sourcepack import policy

    assert policy.validate_policy_config(tmp_path).policy_present is False
    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "rules": {}})
    monkeypatch.setattr(policy.os.path, "lexists", lambda _path: False)
    result = policy.validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is True


def test_repository_policy_rejects_symlinked_ancestry_and_non_regular_file(tmp_path):
    from sourcepack.policy import validate_policy_config

    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".sourcepack").symlink_to(outside, target_is_directory=True)
    result = validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert "policy_config_unsafe:policy_directory_symlink" in result.errors

    (tmp_path / ".sourcepack").unlink()
    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").mkdir()
    result = validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert "policy_config_unsafe:not_regular_file" in result.errors


def test_repository_policy_unsupported_dir_fd_is_structured_failure(tmp_path, monkeypatch):
    from sourcepack import policy

    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1"})
    monkeypatch.setattr(policy.os, "supports_dir_fd", frozenset())
    result = policy.validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert result.errors == ("policy_config_unsupported:descriptor_relative_no_follow",)


def test_repository_policy_unsupported_platform_preserves_absence_and_rejects_unsafe_objects(tmp_path, monkeypatch):
    from sourcepack import policy

    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    monkeypatch.setattr(policy.os, "supports_dir_fd", frozenset())

    absent = policy.validate_policy_config(tmp_path)
    assert absent.policy_present is False
    assert absent.valid is True

    policy_path = policy_dir / "policy.json"
    policy_path.symlink_to(policy_dir / "missing.json")
    dangling = policy.validate_policy_config(tmp_path)
    assert dangling.policy_present is True
    assert dangling.valid is False
    assert dangling.errors == ("policy_config_unsafe:policy_symlink",)

    policy_path.unlink()
    policy_path.mkdir()
    directory = policy.validate_policy_config(tmp_path)
    assert directory.policy_present is True
    assert directory.valid is False
    assert directory.errors == ("policy_config_unsafe:not_regular_file",)


def test_repository_policy_mutation_during_descriptor_read_is_invalid(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sourcepack import policy

    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1"})
    real_fstat = policy.os.fstat
    regular_calls = 0

    def changing_fstat(fd):
        nonlocal regular_calls
        observed = real_fstat(fd)
        if stat.S_ISREG(observed.st_mode):
            regular_calls += 1
            if regular_calls == 2:
                return SimpleNamespace(
                    st_mode=observed.st_mode, st_dev=observed.st_dev, st_ino=observed.st_ino,
                    st_size=observed.st_size, st_mtime_ns=observed.st_mtime_ns + 1,
                )
        return observed

    monkeypatch.setattr(policy.os, "fstat", changing_fstat)
    result = policy.validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert result.errors == ("policy_config_unstable:mutation_detected",)


def test_repository_policy_replacement_during_descriptor_read_is_invalid(tmp_path, monkeypatch):
    from sourcepack import policy

    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1"})
    policy_path = tmp_path / ".sourcepack" / "policy.json"
    replacement = tmp_path / ".sourcepack" / "replacement.json"
    replacement.write_text('{"schema_version":"sourcepack.policy.v1","rules":{}}', encoding="utf-8")
    real_read = policy.os.read
    replaced = False

    def replacing_read(fd, size):
        nonlocal replaced
        data = real_read(fd, size)
        if data and not replaced:
            replaced = True
            replacement.replace(policy_path)
        return data

    monkeypatch.setattr(policy.os, "read", replacing_read)
    result = policy.validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert result.errors == ("policy_config_unstable:path_replaced",)


def test_pathological_nested_policy_json_is_structured_invalid_result(tmp_path):
    from sourcepack.policy import validate_policy_config

    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").write_text("[" * 1500 + "]" * 1500, encoding="utf-8")
    result = validate_policy_config(tmp_path)
    assert result.policy_present is True
    assert result.valid is False
    assert any("parser_limit:RecursionError" in error or "limit_exceeded:nesting_depth" in error for error in result.errors)


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
