import json
import subprocess
import sys



def run(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout


def trust_current_repo(tmp_path, message="trusted state"):
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout


def report(repo):
    cp = run(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def report_ci(repo):
    cp = run(repo, "diff", ".", "--ci", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def test_dependency_allow_suppresses_only_matching_finding(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import fastapi\nimport flask\n", encoding="utf-8")
    assert run(tmp_path, "allow", "dependency", "fastapi", "--reason", "reviewed").returncode == 0
    code, data = report(tmp_path)
    deps = [f.get("evidence") for f in data["findings"] if f["id"] == "unsupported_dependency"]
    assert code == 1
    assert "fastapi" not in deps
    assert "flask" in deps
    assert data["policy_overrides"][0]["value"] == "fastapi"


def test_command_allow_suppresses_exact_matching_finding(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("npm run dev\nnpm run build\n", encoding="utf-8")
    assert run(tmp_path, "allow", "command", "npm run dev", "--reason", "local convention").returncode == 0
    _, data = report(tmp_path)
    commands = [f.get("evidence") for f in data["findings"] if f["id"] == "unsupported_command"]
    assert "npm run dev" not in commands
    assert "npm run build" in commands


def test_policy_cannot_suppress_git_path_finding(tmp_path):
    init_repo(tmp_path)
    assert run(tmp_path, "allow", "path", ".git/config", "--reason", "nope", "--high-risk").returncode != 0
    patch = "diff --git a/.git/config b/.git/config\n--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-a\n+b\n"
    from sourcepack.judgment import judge_repo_change
    judgment = judge_repo_change(tmp_path, patch_text=patch)
    assert "git_path_modification" in {f["id"] for f in judgment.report["findings"]}


def test_policy_config_ignored_paths_require_reason_and_do_not_suppress_protected(tmp_path):
    init_repo(tmp_path)
    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "ignored_paths": [
            {"pattern": "docs/**", "reason": "docs-only reviewed separately"},
            {"pattern": ".sourcepack/baseline/**", "reason": "dangerous"},
            {"pattern": "bad/**"}
        ],
        "prompt_context_authoritative": True,
        "baseline_required_in_ci": False,
    }), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("new docs\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 0
    assert "new_file" not in {f["id"] for f in data["findings"] if f.get("path") == "docs/note.md"}
    assert data["policy_config_ignores"][0]["reason"] == "docs-only reviewed separately"
    assert any("prompt_context_authoritative" in w for w in data["policy_config_warnings"])
    assert any("baseline_required_in_ci_false" in w for w in data["policy_config_warnings"])
    assert any("policy_ignore_unsafe" in w for w in data["policy_config_warnings"])


def test_policy_ignored_paths_allowlist_only_blocks_unsafe_reason_codes():
    from sourcepack.policy import PolicyConfig, finding_ignored_by_policy

    config = PolicyConfig(ignored_paths=({"pattern": "docs/**", "reason": "reviewed docs"},))
    assert finding_ignored_by_policy({"id": "new_file", "path": "docs/new.md"}, config) is not None
    blocked = {
        "unsupported_dependency",
        "declared_dependency",
        "unsupported_command",
        "missing_file",
        "baseline_missing",
        "baseline_stale",
        "baseline_corrupt",
        "baseline_failed",
        "protected_artifact",
        "git_path_modification",
        "unsafe_path",
        "path_escape",
        "malformed_diff",
        "binary_diff",
        "unsupported_ecosystem",
        "workflow_change",
        "policy_config_warning",
        "policy_override",
        "execution_evidence_missing",
        "execution_evidence_present",
        "execution_failed",
        "execution_inconclusive",
        "future_unknown_reason",
    }
    for fid in blocked:
        assert finding_ignored_by_policy({"id": fid, "path": "docs/new.md"}, config) is None, fid


def test_load_policy_config_rejects_exact_unsafe_ignored_paths(tmp_path):
    from sourcepack.policy import load_policy_config

    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "ignored_paths": [
            {"pattern": ".git", "reason": "unsafe"},
            {"pattern": ".sourcepack/baseline", "reason": "unsafe"},
            {"pattern": "docs/**", "reason": "ok"},
        ],
    }), encoding="utf-8")

    config = load_policy_config(tmp_path)

    assert {item["pattern"] for item in config.ignored_paths} == {"docs/**"}
    assert "policy_ignore_unsafe:.git" in config.warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline" in config.warnings


def test_policy_config_reserved_fields_emit_warnings_without_authority(tmp_path):
    from sourcepack.policy import load_policy_config

    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "strict_default": False,
        "fail_on_warn_in_ci": False,
        "protected_paths": ["docs/protected/**"],
        "report_formats": ["json"],
        "baseline_required_in_ci": False,
        "prompt_context_authoritative": True,
    }), encoding="utf-8")
    config = load_policy_config(tmp_path)
    warnings = set(config.warnings)
    assert "policy_config_ignored:prompt_context_authoritative" in warnings
    assert "policy_config_ignored:baseline_required_in_ci_false" in warnings
    assert "policy_config_reserved:strict_default" in warnings
    assert "policy_config_reserved:fail_on_warn_in_ci" in warnings
    assert "policy_config_reserved:protected_paths" in warnings
    assert "policy_config_reserved:report_formats" in warnings
    assert config.strict_default is True
    assert config.fail_on_warn_in_ci is True
    assert config.protected_paths == (".sourcepack/baseline/**", ".git/**")
    assert config.report_formats == ("json", "markdown", "html", "sarif")


def write_rules(tmp_path, rules):
    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "rules": rules,
    }), encoding="utf-8")


def finding_ids(data):
    return {finding["id"] for finding in data["findings"]}


def test_policy_rules_missing_and_empty_do_not_emit_rule_findings(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "app.py").write_text("password = 'not-a-placeholder-secret'\n", encoding="utf-8")
    _, data = report(tmp_path)
    assert not any(finding["id"].startswith("policy_") for finding in data["findings"])

    write_rules(tmp_path, {})
    _, data = report(tmp_path)
    assert not any(finding["id"].startswith("policy_") for finding in data["findings"])


def test_policy_rule_protected_path_fails(tmp_path):
    init_repo(tmp_path)
    protected_dir = tmp_path / "src" / "auth"
    protected_dir.mkdir(parents=True)
    (protected_dir / "login.py").write_text("ALLOW = True\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["src/auth/**"]})

    (protected_dir / "login.py").write_text("ALLOW = False\n", encoding="utf-8")
    code, data = report(tmp_path)

    assert code == 1
    assert "policy_protected_path" in finding_ids(data)


def test_policy_rule_protected_path_fails_for_rename_source(tmp_path):
    init_repo(tmp_path)
    protected_dir = tmp_path / "src" / "auth"
    public_dir = tmp_path / "src" / "public"
    protected_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)
    (protected_dir / "login.py").write_text("ALLOW = True\n", encoding="utf-8")
    write_rules(tmp_path, {"protected_paths": ["src/auth/**"]})
    trust_current_repo(tmp_path)

    subprocess.run(["git", "mv", "src/auth/login.py", "src/public/login.py"], cwd=tmp_path, check=True)
    cp = run(tmp_path, "diff", ".", "--staged", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    data = json.loads(cp.stdout)

    assert cp.returncode == 1
    assert "policy_protected_path" in finding_ids(data)


def test_policy_rule_package_manager_drift_fails_for_pnpm(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"package_manager": "pnpm"})
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 1
    assert "policy_package_manager" in finding_ids(data)


def test_policy_rule_package_manager_drift_allows_lockfile_deletion_for_pnpm(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
    write_rules(tmp_path, {"package_manager": "pnpm"})
    trust_current_repo(tmp_path)

    (tmp_path / "package-lock.json").unlink()
    _, data = report(tmp_path)

    assert "policy_package_manager" not in finding_ids(data)


def test_policy_rule_missing_test_warns_and_test_change_satisfies(tmp_path):
    init_repo(tmp_path)
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_handler.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"require_tests_for": ["src/api/**"]})

    (api_dir / "handler.py").write_text("VALUE = 2\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_test_required" in finding_ids(data)

    (tests_dir / "test_handler.py").write_text("def test_value():\n    assert 2 == 2\n", encoding="utf-8")
    _, data = report(tmp_path)
    assert "policy_test_required" not in finding_ids(data)


def test_policy_rule_missing_test_blocks_in_ci(tmp_path):
    init_repo(tmp_path)
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"require_tests_for": ["src/api/**"]})
    (api_dir / "handler.py").write_text("VALUE = 2\n", encoding="utf-8")

    code, data = report_ci(tmp_path)

    assert code != 0
    assert "policy_test_required" in finding_ids(data)


def test_policy_rule_large_diff_warns(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 1
    assert "policy_change_limit" in finding_ids(data)


def test_policy_change_limit_line_count_excludes_diff_file_headers():
    from sourcepack.diff_parser import PatchFileChange
    from sourcepack.judgment import _policy_changed_line_count

    change = PatchFileChange(
        path="README.md",
        old_path="README.md",
        diff_lines=[
            "--- a/README.md",
            "+++ b/README.md",
            "@@ -1 +1 @@",
            " unchanged context",
            "-old content",
            "+new content",
        ],
    )

    assert _policy_changed_line_count([change]) == 2


def test_policy_rule_large_diff_blocks_in_ci(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    code, data = report_ci(tmp_path)

    assert code != 0
    assert "policy_change_limit" in finding_ids(data)


def test_policy_rule_secret_pattern_ignores_placeholders(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    (tmp_path / "app.py").write_text("token = 'REDACTED'\npassword = 'changeme'\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 0
    assert "policy_secret_pattern" not in finding_ids(data)


def test_policy_rule_secret_pattern_fails_for_common_assignment_shapes(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    (tmp_path / "app.py").write_text("api_key = 'live_secret_value_12345'\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)

    (tmp_path / "app.py").write_text('"api_key": "live_secret_value_12345"\n', encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)

    (tmp_path / "app.py").write_text("password: live_secret_value_12345\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)


def test_policy_rule_dependency_addition_fails(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 1
    assert "policy_dependency_addition" in finding_ids(data)


def test_policy_rule_dependency_addition_uncertain_manifest_emits_existing_uncertainty(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    patch = (
        "diff --git a/pyproject.toml b/pyproject.toml\n"
        "--- a/pyproject.toml\n"
        "+++ b/pyproject.toml\n"
        "@@ -1,3 +1,3 @@\n"
        " [project]\n"
        "-does-not-match-baseline\n"
        "+dependencies = ['requests']\n"
        " dependencies = []\n"
    )

    from sourcepack.judgment import judge_repo_change
    judgment = judge_repo_change(tmp_path, patch_text=patch)

    assert "dependency_manifest_uncertain" in finding_ids(judgment.report)
    assert "policy_dependency_addition" not in finding_ids(judgment.report)


def test_diff_required_org_policy_missing_is_structured_policy_fail(tmp_path):
    init_repo(tmp_path)
    cp = run(tmp_path, "diff", ".", "--json", "--exit-policy", "fail-only", "--org-policy-mode", "required")
    data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert data["verdict"] == "FAIL"
    findings = [f for f in data["findings"] if f["id"] == "policy_resolution_failed"]
    assert len(findings) == 1
    assert findings[0]["override_eligible"] is False
    assert findings[0]["policy"]["organization_policy_status"] == "required_but_missing"
    assert "org_policy_required_but_missing" in findings[0]["policy"]["errors"]
    assert data["policy"]["resolution_status"] == "FAIL"


def test_diff_external_org_policy_protected_path_authority(tmp_path):
    init_repo(tmp_path)
    org = tmp_path.parent / "org-diff-policy.json"
    org.write_text(json.dumps({"schema_version": "sourcepack.org_policy.v1", "policy_id": "eng", "rules": {"protected_paths": ["app.py"]}}), encoding="utf-8")
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = next(f for f in data["findings"] if f["id"] == "policy_protected_path")
    assert cp.returncode == 1
    assert finding["policy_authority"] == "organization"
    assert finding["override_eligible"] is False
    assert finding["policy"]["effective_policy_id"].startswith("epol_")
    assert data["policy"]["organization_policy_status"] == "loaded"
    assert data["policy"]["policy_finding_count"] == 1


def test_repository_policy_finding_is_override_eligible_and_identity_binds_rule(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["app.py"]})
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")
    _, data1 = report(tmp_path)
    finding1 = next(f for f in data1["findings"] if f["id"] == "policy_protected_path")
    assert finding1["policy_authority"] == "repository"
    assert finding1["override_eligible"] is True
    fid1 = finding1["finding_id"]
    write_rules(tmp_path, {"protected_paths": ["*.py"]})
    _, data2 = report(tmp_path)
    finding2 = next(f for f in data2["findings"] if f["id"] == "policy_protected_path")
    assert finding2["finding_id"] != fid1


def test_policy_resolution_failure_preserves_core_findings(tmp_path):
    init_repo(tmp_path)
    org = tmp_path.parent / "bad-org-policy.json"
    org.write_text("{", encoding="utf-8")
    (tmp_path / "app.py").write_text("import fastapi\n", encoding="utf-8")
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    ids = {f["id"] for f in data["findings"]}
    assert cp.returncode == 1
    assert "policy_resolution_failed" in ids
    assert "unsupported_dependency" in ids



def write_org_policy_file(path, rules):
    path.write_text(json.dumps({"schema_version": "sourcepack.org_policy.v1", "policy_id": "eng", "rules": rules}), encoding="utf-8")


def policy_finding(data, reason):
    return next(f for f in data["findings"] if f["id"] == reason)


def remove_active_baseline(repo):
    active = repo / ".sourcepack" / "baseline" / "active.json"
    if active.exists():
        active.unlink()


def corrupt_active_baseline(repo):
    active = repo / ".sourcepack" / "baseline" / "active.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text("{", encoding="utf-8")


def test_scalar_boolean_org_false_repo_true_dependency_is_repository_authority(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    org = tmp_path.parent / "org-false-deps.json"
    write_org_policy_file(org, {"block_dependency_additions": False})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_dependency_addition")

    assert cp.returncode == 1
    assert finding["policy_authority"] == "repository"
    assert finding["override_eligible"] is True


def test_scalar_boolean_org_false_repo_true_secret_is_repository_authority(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    org = tmp_path.parent / "org-false-secrets.json"
    write_org_policy_file(org, {"block_secret_patterns": False})
    (tmp_path / "app.py").write_text("token = 'abcdefghijklmnopqrstuvwxyz'\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_secret_pattern")

    assert finding["policy_authority"] == "repository"
    assert finding["override_eligible"] is True


def test_scalar_boolean_org_true_repo_true_dependency_is_mixed_authority(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    org = tmp_path.parent / "org-true-deps.json"
    write_org_policy_file(org, {"block_dependency_additions": True})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_dependency_addition")

    assert finding["policy_authority"] == "mixed"
    assert finding["override_eligible"] is False


def test_scalar_boolean_org_only_true_dependency_is_organization_authority(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    org = tmp_path.parent / "org-only-true-deps.json"
    write_org_policy_file(org, {"block_dependency_additions": True})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_dependency_addition")

    assert finding["policy_authority"] == "organization"
    assert finding["override_eligible"] is False


def test_max_changed_lines_repo_strengthening_is_repository_authority(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    org = tmp_path.parent / "org-max-500.json"
    write_org_policy_file(org, {"max_changed_lines": 500})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_change_limit")

    assert finding["policy_authority"] == "repository"
    assert finding["override_eligible"] is True


def test_max_changed_lines_equal_values_are_mixed_authority(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    org = tmp_path.parent / "org-max-1.json"
    write_org_policy_file(org, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_change_limit")

    assert finding["policy_authority"] == "mixed"
    assert finding["override_eligible"] is False


def test_max_changed_lines_repo_only_and_org_only_authority(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")
    _, repo_data = report(tmp_path)
    assert policy_finding(repo_data, "policy_change_limit")["policy_authority"] == "repository"

    repo = tmp_path / "orgonly"
    repo.mkdir()
    init_repo(repo)
    org = tmp_path / "org-only-max.json"
    write_org_policy_file(org, {"max_changed_lines": 1})
    (repo / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")
    cp = run(repo, "diff", ".", "--json", "--org-policy", str(org))
    org_data = json.loads(cp.stdout)
    assert policy_finding(org_data, "policy_change_limit")["policy_authority"] == "organization"


def test_actor_text_cannot_forge_organization_policy_override(tmp_path):
    from sourcepack.overrides import create_override

    init_repo(tmp_path)
    org = tmp_path.parent / "org-protected-app.json"
    write_org_policy_file(org, {"protected_paths": ["app.py"]})
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_protected_path")

    assert finding["policy_authority"] == "organization"
    try:
        create_override(report=data, report_path=tmp_path / ".sourcepack" / "reports" / "latest.json", target_finding_id=finding["finding_id"], actor="repository-admin", reason="actor text must not change policy authority", scope="path")
    except ValueError as exc:
        assert "override target" in str(exc)
    else:
        raise AssertionError("actor text must not make organization policy findings overrideable")


def test_baseline_missing_plus_protected_path_preserves_both_findings(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["app.py"]})
    remove_active_baseline(tmp_path)
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")

    code, data = report(tmp_path)
    ids = [f["id"] for f in data["findings"]]

    assert code == 1
    assert ids.count("policy_protected_path") == 1
    assert "baseline_missing" in ids


def test_baseline_corrupt_plus_secret_pattern_preserves_both_findings(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    corrupt_active_baseline(tmp_path)
    (tmp_path / "app.py").write_text("token = 'abcdefghijklmnopqrstuvwxyz'\n", encoding="utf-8")

    code, data = report(tmp_path)
    ids = [f["id"] for f in data["findings"]]

    assert code == 1
    assert ids.count("policy_secret_pattern") == 1
    assert "baseline_corrupt" in ids


def test_baseline_missing_plus_change_limit_preserves_both_findings(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    remove_active_baseline(tmp_path)
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    code, data = report(tmp_path)
    ids = [f["id"] for f in data["findings"]]

    assert code == 1
    assert ids.count("policy_change_limit") == 1
    assert "baseline_missing" in ids


def test_baseline_missing_does_not_guess_dependency_additions(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    remove_active_baseline(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    code, data = report(tmp_path)
    ids = [f["id"] for f in data["findings"]]

    assert code == 1
    assert "baseline_missing" in ids
    assert "policy_dependency_addition" not in ids
    assert data["verdict"] == "FAIL"
