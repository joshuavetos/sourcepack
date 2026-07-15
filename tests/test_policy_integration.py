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


def resolution_failure_finding_id(repo, *args):
    cp = run(repo, "diff", ".", "--json", *args)
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_resolution_failed")
    return finding["finding_id"], finding, data


def test_resolution_failure_identity_repeats_for_identical_required_missing(tmp_path):
    init_repo(tmp_path)
    first, first_finding, _ = resolution_failure_finding_id(tmp_path, "--org-policy-mode", "required")
    second, second_finding, _ = resolution_failure_finding_id(tmp_path, "--org-policy-mode", "required")

    assert first == second
    assert first_finding["policy"]["resolution_fingerprint"] == second_finding["policy"]["resolution_fingerprint"]


def test_resolution_failure_identity_stable_across_checkout_roots(tmp_path):
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir()
    repo_b.mkdir()
    init_repo(repo_a)
    init_repo(repo_b)

    a_id, _, _ = resolution_failure_finding_id(repo_a, "--org-policy-mode", "required")
    b_id, _, _ = resolution_failure_finding_id(repo_b, "--org-policy-mode", "required")

    assert a_id == b_id


def test_resolution_failure_identity_distinguishes_missing_required_and_malformed(tmp_path):
    init_repo(tmp_path)
    missing_id, _, _ = resolution_failure_finding_id(tmp_path, "--org-policy-mode", "required")
    bad = tmp_path.parent / "bad-org-identity.json"
    bad.write_text("{", encoding="utf-8")
    malformed_id, _, _ = resolution_failure_finding_id(tmp_path, "--org-policy", str(bad))

    assert missing_id != malformed_id


def test_resolution_failure_identity_distinguishes_weakening_and_conflict_material():
    from sourcepack.judgment import _policy_resolution_failure_finding
    from sourcepack.reports.json import traffic_report

    weakening = {
        "schema_version": "sourcepack.effective_policy.v1",
        "effective_policy_id": "epol_same",
        "organization_policy_mode": "optional",
        "organization_policy_status": "loaded",
        "errors": ["repository_policy_weakening_attempt"],
        "conflicts": [],
        "rejected_weakening_attempts": [{"rule": "max_changed_lines", "organization_value": 200, "repository_value": 500}],
    }
    conflict = {
        "schema_version": "sourcepack.effective_policy.v1",
        "effective_policy_id": "epol_same",
        "organization_policy_mode": "optional",
        "organization_policy_status": "loaded",
        "errors": ["policy_conflict"],
        "conflicts": [{"rule": "package_manager", "organization_value": "pnpm", "repository_value": "npm"}],
        "rejected_weakening_attempts": [],
    }

    weak_finding = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(weakening)])["findings"][0]
    conflict_finding = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(conflict)])["findings"][0]

    assert weak_finding["finding_id"] != conflict_finding["finding_id"]


def test_resolution_failure_identity_sorts_error_ordering():
    from sourcepack.judgment import _policy_resolution_failure_finding
    from sourcepack.reports.json import traffic_report

    first = {
        "schema_version": "sourcepack.effective_policy.v1",
        "effective_policy_id": "epol_order",
        "organization_policy_mode": "optional",
        "organization_policy_status": "invalid",
        "errors": ["b_error", "a_error"],
        "conflicts": [],
        "rejected_weakening_attempts": [],
    }
    second = dict(first, errors=["a_error", "b_error"])

    first_id = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(first)])["findings"][0]["finding_id"]
    second_id = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(second)])["findings"][0]["finding_id"]

    assert first_id == second_id


def test_resolution_failure_identity_ignores_org_policy_path_spelling(tmp_path):
    init_repo(tmp_path)
    bad = tmp_path.parent / "bad-org-spelling.json"
    bad.write_text("{", encoding="utf-8")
    link = tmp_path.parent / "bad-org-link.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(bad)

    real_id, _, _ = resolution_failure_finding_id(tmp_path, "--org-policy", str(bad))
    link_id, _, _ = resolution_failure_finding_id(tmp_path, "--org-policy", str(link))

    assert real_id == link_id


def test_required_org_missing_plus_git_diff_failure_preserves_both_findings(tmp_path, monkeypatch):
    import sourcepack.judgment as judgment

    init_repo(tmp_path)
    real_run_git = judgment.run_git

    def fake_run_git(cwd, args, *extra, **kwargs):
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(args, 2, stdout="", stderr="synthetic diff failure")
        return real_run_git(cwd, args, *extra, **kwargs)

    monkeypatch.setattr(judgment, "run_git", fake_run_git)
    report_data = judgment.build_repo_change_report(tmp_path, org_policy_mode="required")
    ids = [f["id"] for f in report_data["findings"]]

    assert "git_diff_failed" in ids
    assert ids.count("policy_resolution_failed") == 1
    assert report_data["policy"]["resolution_status"] == "FAIL"
    assert report_data["policy_rule_findings"][0]["id"] == "policy_resolution_failed"


def test_malformed_org_policy_plus_git_timeout_preserves_both_findings(tmp_path, monkeypatch):
    import sourcepack.judgment as judgment

    init_repo(tmp_path)
    bad = tmp_path.parent / "bad-timeout-org.json"
    bad.write_text("{", encoding="utf-8")
    real_run_git = judgment.run_git

    def fake_run_git(cwd, args, *extra, **kwargs):
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(args, judgment.GIT_RETURNCODE_TIMEOUT, stdout="", stderr="timeout")
        return real_run_git(cwd, args, *extra, **kwargs)

    monkeypatch.setattr(judgment, "run_git", fake_run_git)
    report_data = judgment.build_repo_change_report(tmp_path, org_policy=bad)
    ids = [f["id"] for f in report_data["findings"]]

    assert "git_timeout" in ids
    assert ids.count("policy_resolution_failed") == 1
    assert report_data["policy"]["organization_policy_status"] == "invalid"


def test_policy_pass_plus_git_diff_failure_emits_only_git_failure(tmp_path, monkeypatch):
    import sourcepack.judgment as judgment

    init_repo(tmp_path)
    real_run_git = judgment.run_git

    def fake_run_git(cwd, args, *extra, **kwargs):
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(args, 2, stdout="", stderr="synthetic diff failure")
        return real_run_git(cwd, args, *extra, **kwargs)

    monkeypatch.setattr(judgment, "run_git", fake_run_git)
    report_data = judgment.build_repo_change_report(tmp_path)
    ids = [f["id"] for f in report_data["findings"]]

    assert ids == ["git_diff_failed"]
    assert report_data["policy"]["resolution_status"] == "PASS"
    assert report_data["policy_rule_findings"] == []


def test_early_failure_does_not_guess_policy_rules_without_diff(tmp_path, monkeypatch):
    import sourcepack.judgment as judgment

    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["app.py"], "block_dependency_additions": True, "max_changed_lines": 1})
    bad = tmp_path.parent / "bad-early-org.json"
    bad.write_text("{", encoding="utf-8")
    real_run_git = judgment.run_git

    def fake_run_git(cwd, args, *extra, **kwargs):
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(args, 2, stdout="", stderr="synthetic diff failure")
        return real_run_git(cwd, args, *extra, **kwargs)

    monkeypatch.setattr(judgment, "run_git", fake_run_git)
    report_data = judgment.build_repo_change_report(tmp_path, org_policy=bad)
    ids = [f["id"] for f in report_data["findings"]]

    assert "git_diff_failed" in ids
    assert ids.count("policy_resolution_failed") == 1
    assert "policy_protected_path" not in ids
    assert "policy_dependency_addition" not in ids
    assert "policy_change_limit" not in ids


def test_resolution_failure_identity_ignores_effective_policy_id_and_array_ordering():
    from sourcepack.judgment import _policy_resolution_failure_finding
    from sourcepack.reports.json import traffic_report

    first = {
        "schema_version": "sourcepack.effective_policy.v1",
        "effective_policy_id": "epol_order_a",
        "organization_policy_mode": "optional",
        "organization_policy_status": "loaded",
        "organization_policy_id": "eng",
        "organization_policy_hash": "sha256:org",
        "repository_policy_hash": "sha256:repo",
        "errors": ["z_error", "a_error", "a_error"],
        "conflicts": [
            {"rule": "package_manager", "organization_value": "pnpm", "repository_value": "npm"},
            {"rule": "future", "organization_value": 1, "repository_value": 2},
        ],
        "rejected_weakening_attempts": [
            {"rule": "max_changed_lines", "organization_value": 200, "repository_value": 500},
            {"rule": "block_secret_patterns", "organization_value": True, "repository_value": False},
        ],
    }
    second = dict(
        first,
        effective_policy_id="epol_order_b",
        errors=["a_error", "z_error"],
        conflicts=list(reversed(first["conflicts"])),
        rejected_weakening_attempts=list(reversed(first["rejected_weakening_attempts"])),
    )

    first_finding = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(first)])["findings"][0]
    second_finding = traffic_report("FAIL", findings=[_policy_resolution_failure_finding(second)])["findings"][0]

    assert first_finding["policy"]["effective_policy_id"] != second_finding["policy"]["effective_policy_id"]
    assert first_finding["policy"]["resolution_fingerprint"] == second_finding["policy"]["resolution_fingerprint"]
    assert first_finding["finding_id"] == second_finding["finding_id"]


def test_protected_path_matching_org_and_repo_patterns_is_mixed_authority(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["*.py"]})
    org = tmp_path.parent / "org-protected-mixed-patterns.json"
    write_org_policy_file(org, {"protected_paths": ["app.*"]})
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_protected_path")

    assert finding["policy_authority"] == "mixed"
    assert finding["override_eligible"] is False
    assert sorted(finding["policy"]["matching_patterns"]) == ["*.py", "app.*"]


def test_require_tests_matching_org_and_repo_patterns_is_mixed_authority(tmp_path):
    init_repo(tmp_path)
    src = tmp_path / "src" / "api"
    src.mkdir(parents=True)
    (src / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"require_tests_for": ["src/api/**"]})
    org = tmp_path.parent / "org-tests-mixed-patterns.json"
    write_org_policy_file(org, {"require_tests_for": ["src/**"]})
    (src / "handler.py").write_text("VALUE = 2\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    data = json.loads(cp.stdout)
    finding = policy_finding(data, "policy_test_required")

    assert finding["policy_authority"] == "mixed"
    assert finding["override_eligible"] is False
    assert finding["policy"]["triggering_path"] == "src/api/handler.py"


def test_repository_policy_protected_path_exact_allow_suppresses_and_recomputes_verdict(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["app.py"]})
    assert run(tmp_path, "allow", "path", "app.py", "--reason", "repository policy reviewed").returncode == 0
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 0
    assert data["verdict"] == "PASS"
    assert "policy_protected_path" not in finding_ids(data)
    assert data["policy"]["policy_finding_count"] == 0
    assert data["policy_rule_findings"] == []
    assert data["policy_overrides"][0]["suppressed_finding"] == "policy_protected_path"
    assert data["policy_overrides"][0]["value"] == "app.py"


def test_local_allow_does_not_suppress_org_mixed_or_resolution_policy_findings(tmp_path):
    init_repo(tmp_path)
    assert run(tmp_path, "allow", "path", "app.py", "--reason", "local review").returncode == 0
    org = tmp_path.parent / "org-allow-unsuppressible.json"
    write_org_policy_file(org, {"protected_paths": ["app.py"]})
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    org_data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert policy_finding(org_data, "policy_protected_path")["policy_authority"] == "organization"
    assert not org_data.get("policy_overrides")

    write_rules(tmp_path, {"protected_paths": ["*.py"]})
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    mixed_data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert policy_finding(mixed_data, "policy_protected_path")["policy_authority"] == "mixed"
    assert not mixed_data.get("policy_overrides")

    bad = tmp_path.parent / "bad-allow-unsuppressible.json"
    bad.write_text("{", encoding="utf-8")
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(bad))
    failed_data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert [f["id"] for f in failed_data["findings"]].count("policy_resolution_failed") == 1
    assert not failed_data.get("policy_overrides")


def test_local_allow_non_policy_behavior_still_suppresses_dependency(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import fastapi\n", encoding="utf-8")
    assert run(tmp_path, "allow", "dependency", "fastapi", "--reason", "reviewed").returncode == 0

    code, data = report(tmp_path)

    assert code == 0
    assert data["verdict"] == "PASS"
    assert "unsupported_dependency" not in finding_ids(data)
    assert data["policy_overrides"][0]["suppressed_finding"] == "unsupported_dependency"


def test_stale_baseline_preserves_single_policy_finding_and_metadata(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["app.py"]})
    (tmp_path / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}', encoding="utf-8")
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")

    code, data = report(tmp_path)

    policy_findings = [f for f in data["findings"] if f["id"] == "policy_protected_path"]
    assert code == 1
    assert data["verdict"] == "FAIL"
    assert len(policy_findings) == 1
    assert data["policy"]["policy_finding_count"] == 1
    assert [f["id"] for f in data["policy_rule_findings"]] == ["policy_protected_path"]
    assert "baseline_stale" in finding_ids(data)


def test_stale_baseline_preserves_single_policy_resolution_failure(tmp_path):
    init_repo(tmp_path)
    (tmp_path / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}', encoding="utf-8")
    (tmp_path / "app.py").write_text("print(2)\n", encoding="utf-8")
    bad = tmp_path.parent / "bad-stale-org.json"
    bad.write_text("{", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(bad))
    data = json.loads(cp.stdout)

    resolution_findings = [f for f in data["findings"] if f["id"] == "policy_resolution_failed"]
    assert cp.returncode == 1
    assert data["verdict"] == "FAIL"
    assert len(resolution_findings) == 1
    assert data["policy"]["policy_finding_count"] == 1
    assert [f["id"] for f in data["policy_rule_findings"]] == ["policy_resolution_failed"]
    assert "baseline_stale" in finding_ids(data)


def test_repository_policy_dependency_addition_exact_allow_suppresses_and_recomputes_verdict(tmp_path):
    from sourcepack.judgment import _apply_local_policy
    from sourcepack.reports.json import normalized_finding, traffic_report

    init_repo(tmp_path)
    assert run(tmp_path, "allow", "dependency", "requests", "--reason", "reviewed dependency").returncode == 0
    finding = normalized_finding(
        "policy_dependency_addition",
        "error",
        "policy",
        "Proposed change added an unapproved dependency to project manifest files.",
        evidence="requests",
    )
    finding["policy_authority"] = "repository"
    finding["override_eligible"] = True
    finding["policy"] = {"rule_name": "block_dependency_additions", "rule_fingerprint": "sha256:test", "scope": "requests"}
    report_data = traffic_report("FAIL", findings=[finding])
    report_data["policy"] = {"evaluated": True, "resolution_status": "PASS", "policy_finding_count": 1}
    report_data["policy_rule_findings"] = [report_data["findings"][0]]

    data = _apply_local_policy(tmp_path, report_data)

    assert data["verdict"] == "PASS"
    assert "policy_dependency_addition" not in finding_ids(data)
    assert data["policy"]["policy_finding_count"] == 0
    assert data["policy_rule_findings"] == []
    assert data["policy_overrides"][0]["suppressed_finding"] == "policy_dependency_addition"
    assert data["policy_overrides"][0]["value"] == "requests"


def test_repository_policy_dependency_addition_exact_allow_suppresses_integration(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    assert run(tmp_path, "allow", "dependency", "requests", "--reason", "reviewed dependency").returncode == 0
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 0
    assert "policy_dependency_addition" not in finding_ids(data)
    assert data["policy"]["policy_finding_count"] == 0
    assert data["policy_rule_findings"] == []
    assert data["policy_overrides"][0]["suppressed_finding"] == "policy_dependency_addition"
    assert data["policy_overrides"][0]["value"] == "requests"


def test_policy_dependency_addition_allow_does_not_suppress_org_mixed_or_wrong_name(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    assert run(tmp_path, "allow", "dependency", "requests", "--reason", "reviewed dependency").returncode == 0
    org = tmp_path.parent / "org-dependency-unsuppressible.json"
    write_org_policy_file(org, {"block_dependency_additions": True})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    org_data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert policy_finding(org_data, "policy_dependency_addition")["policy_authority"] == "organization"
    assert not org_data.get("policy_overrides")

    write_rules(tmp_path, {"block_dependency_additions": True})
    cp = run(tmp_path, "diff", ".", "--json", "--org-policy", str(org))
    mixed_data = json.loads(cp.stdout)
    assert cp.returncode == 1
    assert policy_finding(mixed_data, "policy_dependency_addition")["policy_authority"] == "mixed"
    assert not mixed_data.get("policy_overrides")

    wrong_name_repo = tmp_path / "wrong-name"
    wrong_name_repo.mkdir()
    init_repo(wrong_name_repo)
    (wrong_name_repo / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(wrong_name_repo)
    write_rules(wrong_name_repo, {"block_dependency_additions": True})
    assert run(wrong_name_repo, "allow", "dependency", "flask", "--reason", "different dependency").returncode == 0
    (wrong_name_repo / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    wrong_code, wrong_data = report(wrong_name_repo)
    assert wrong_code == 1
    assert policy_finding(wrong_data, "policy_dependency_addition")["evidence"] == "requests"
    assert not wrong_data.get("policy_overrides")
