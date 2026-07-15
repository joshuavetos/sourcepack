import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_cli(cwd, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_git_repo(repo: Path):
    if not (repo / ".git").exists():
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def write_repo_policy(repo: Path, rules: dict):
    (repo / ".sourcepack").mkdir(exist_ok=True)
    (repo / ".sourcepack" / "policy.json").write_text(json.dumps({"schema_version": "sourcepack.policy.v1", "rules": rules}), encoding="utf-8")


def write_org(path: Path, rules: dict, *, policy_id="engineering-default", schema="sourcepack.org_policy.v1"):
    path.write_text(json.dumps({"schema_version": schema, "policy_id": policy_id, "rules": rules}), encoding="utf-8")


def resolve_json(repo: Path, *extra):
    ensure_git_repo(repo)
    cp = run_cli(repo, "policy", "resolve", str(repo), "--json", *extra)
    return cp, json.loads(cp.stdout)


def test_optional_and_required_modes_without_org_policy(tmp_path):
    cp, data = resolve_json(tmp_path)
    assert cp.returncode == 0
    assert data["resolution_status"] == "PASS"
    assert data["organization_policy_status"] == "not_supplied"
    cp, data = resolve_json(tmp_path, "--org-policy-mode", "required")
    assert cp.returncode != 0
    assert data["organization_policy_status"] == "required_but_missing"
    assert "org_policy_required_but_missing" in data["errors"]


def test_valid_external_org_policy_loaded_and_human_summary(tmp_path):
    org = tmp_path.parent / "org-policy.json"
    write_org(org, {"block_dependency_additions": True})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode == 0
    assert data["organization_policy_status"] == "loaded"
    assert data["organization_policy_id"] == "engineering-default"
    assert data["organization_policy_hash"]
    assert data["effective_policy"]["block_dependency_additions"] is True
    human = run_cli(tmp_path, "policy", "resolve", str(tmp_path), "--org-policy", str(org))
    assert "Resolution verdict: PASS" in human.stdout
    assert "Organization-policy mode: optional" in human.stdout
    assert "Effective-policy ID:" in human.stdout


def test_boundary_rejects_inside_relative_symlink_missing_directory_malformed_and_schema(tmp_path):
    inside = tmp_path / ".sourcepack" / "org.json"
    inside.parent.mkdir()
    write_org(inside, {})
    cp, data = resolve_json(tmp_path, "--org-policy", str(inside))
    assert cp.returncode != 0 and data["organization_policy_status"] == "trust_boundary_violation"
    cp, data = resolve_json(tmp_path, "--org-policy", ".sourcepack/org.json")
    assert cp.returncode != 0 and data["organization_policy_status"] == "trust_boundary_violation"
    link = tmp_path.parent / "link-org.json"
    if link.exists() or link.is_symlink(): link.unlink()
    link.symlink_to(inside)
    cp, data = resolve_json(tmp_path, "--org-policy", str(link))
    assert cp.returncode != 0 and data["organization_policy_status"] == "trust_boundary_violation"
    missing = tmp_path.parent / "missing-org.json"
    cp, data = resolve_json(tmp_path, "--org-policy", str(missing))
    assert cp.returncode != 0 and data["organization_policy_status"] == "invalid"
    cp, data = resolve_json(tmp_path, "--org-policy", str(tmp_path.parent))
    assert cp.returncode != 0 and data["organization_policy_status"] == "invalid"
    bad = tmp_path.parent / "bad-org.json"; bad.write_text("{", encoding="utf-8")
    cp, data = resolve_json(tmp_path, "--org-policy", str(bad))
    assert cp.returncode != 0 and data["organization_policy_status"] == "invalid"
    future = tmp_path.parent / "future-org.json"; write_org(future, {}, schema="future")
    cp, data = resolve_json(tmp_path, "--org-policy", str(future))
    assert cp.returncode != 0 and "org_policy_unsupported_schema" in data["errors"]


def test_external_symlink_to_valid_policy_and_spelling_do_not_change_identity(tmp_path):
    real = tmp_path.parent / "real-org.json"; write_org(real, {"protected_paths": ["src/**"]})
    link = tmp_path.parent / "valid-org-link.json"
    if link.exists() or link.is_symlink(): link.unlink()
    link.symlink_to(real)
    cp1, data1 = resolve_json(tmp_path, "--org-policy", str(real))
    cp2, data2 = resolve_json(tmp_path, "--org-policy", str(link))
    assert cp1.returncode == cp2.returncode == 0
    assert data1["effective_policy_id"] == data2["effective_policy_id"]


def test_unknown_org_rule_and_invalid_rule_values_fail_closed(tmp_path):
    org = tmp_path.parent / "org-unknown.json"; write_org(org, {"future_rule": True})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode != 0 and "org_policy_rule_unknown:future_rule" in data["errors"]
    for rule, value in [("max_changed_lines", 0), ("max_changed_lines", -1), ("max_changed_lines", True), ("max_changed_lines", "10"), ("protected_paths", ["../x"]), ("block_secret_patterns", "yes")]:
        org = tmp_path.parent / f"org-{rule}-{str(value).replace('/', '_')}.json"; write_org(org, {rule: value})
        cp, data = resolve_json(tmp_path, "--org-policy", str(org))
        assert cp.returncode != 0, (rule, value, data)
        assert data["resolution_status"] == "FAIL"


def test_boolean_semantics_for_both_boolean_fields(tmp_path):
    for rule in ["block_dependency_additions", "block_secret_patterns"]:
        org = tmp_path.parent / f"org-{rule}.json"
        write_org(org, {rule: False}); write_repo_policy(tmp_path, {rule: True})
        cp, data = resolve_json(tmp_path, "--org-policy", str(org))
        assert cp.returncode == 0 and data["effective_policy"][rule] is True
        assert data["rules"][rule]["compatibility_status"] == "strengthening"
        write_org(org, {rule: True}); write_repo_policy(tmp_path, {rule: False})
        cp, data = resolve_json(tmp_path, "--org-policy", str(org))
        assert cp.returncode != 0 and data["rejected_weakening_attempts"][0]["rule"] == rule
        write_repo_policy(tmp_path, {})
        cp, data = resolve_json(tmp_path, "--org-policy", str(org))
        assert cp.returncode == 0 and data["effective_policy"][rule] is True


def test_path_sets_union_dedupe_separator_normalization_and_provenance(tmp_path):
    org = tmp_path.parent / "org-paths.json"
    write_org(org, {"protected_paths": ["src/**", "src\\**"], "require_tests_for": ["lib/**"]})
    write_repo_policy(tmp_path, {"protected_paths": ["tests/**"], "require_tests_for": ["lib/**", "src/**"]})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode == 0
    assert data["effective_policy"]["protected_paths"] == ["src/**", "tests/**"]
    assert data["effective_policy"]["require_tests_for"] == ["lib/**", "src/**"]
    assert data["rules"]["require_tests_for"]["provenance"]["lib/**"] == ["organization", "repository"]
    assert data["rules"]["protected_paths"]["provenance"]["src/**"] == ["organization"]


def test_numeric_and_package_manager_semantics(tmp_path):
    org = tmp_path.parent / "org-num.json"
    write_org(org, {"max_changed_lines": 500}); write_repo_policy(tmp_path, {"max_changed_lines": 200})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode == 0 and data["effective_policy"]["max_changed_lines"] == 200
    write_repo_policy(tmp_path, {"max_changed_lines": 800})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode != 0 and data["rejected_weakening_attempts"][0]["rule"] == "max_changed_lines"
    write_org(org, {"package_manager": "pnpm"}); write_repo_policy(tmp_path, {"package_manager": "pnpm"})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode == 0
    write_org(org, {"package_manager": "npm"})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode != 0
    assert "org_policy_rule_invalid:unsupported_package_manager:npm" in data["errors"]


def test_deterministic_json_identity_and_no_paths_in_identity_material(tmp_path):
    org = tmp_path.parent / "org-det.json"
    org.write_text('{"rules":{"protected_paths":["src/**"]},"policy_id":"engineering-default","schema_version":"sourcepack.org_policy.v1"}', encoding="utf-8")
    cp1, data1 = resolve_json(tmp_path, "--org-policy", str(org))
    cp2, data2 = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp1.stdout == cp2.stdout
    org.write_text(json.dumps({"schema_version":"sourcepack.org_policy.v1","policy_id":"engineering-default","rules":{"protected_paths":["src/**"]}}, indent=4), encoding="utf-8")
    cp3, data3 = resolve_json(tmp_path, "--org-policy", str(org))
    assert data1["effective_policy_id"] == data3["effective_policy_id"]
    write_repo_policy(tmp_path, {"protected_paths": ["src/**"]})
    cp4, data4 = resolve_json(tmp_path, "--org-policy", str(org))
    assert data4["effective_policy_id"] != data3["effective_policy_id"]
    assert str(tmp_path) not in data4["effective_policy_id"]


def test_invalid_mode_argparse_json_uncontaminated_and_read_only(tmp_path):
    ensure_git_repo(tmp_path)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    cp = run_cli(tmp_path, "policy", "resolve", str(tmp_path), "--org-policy-mode", "bogus")
    assert cp.returncode != 0
    cp, data = resolve_json(tmp_path)
    assert cp.stdout.lstrip().startswith("{") and cp.stderr == ""
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert before == after



def test_subdirectory_invocation_rejects_policy_elsewhere_inside_actual_repo(tmp_path):
    ensure_git_repo(tmp_path)
    nested = tmp_path / "packages" / "app"
    nested.mkdir(parents=True)
    internal = tmp_path / "org-policy.json"
    write_org(internal, {"block_dependency_additions": True})
    cp = run_cli(tmp_path, "policy", "resolve", str(nested), "--json", "--org-policy", str(internal))
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["organization_policy_status"] == "trust_boundary_violation"
    assert "org_policy_trust_boundary_violation:inside_repository" in data["errors"]


def test_nested_invocation_loads_root_policy_and_keeps_same_effective_id(tmp_path):
    ensure_git_repo(tmp_path)
    write_repo_policy(tmp_path, {"protected_paths": ["src/**"]})
    nested = tmp_path / "packages" / "app"
    nested.mkdir(parents=True)
    external = tmp_path.parent / "nested-valid-org.json"
    write_org(external, {"require_tests_for": ["src/**"]})
    root_cp = run_cli(tmp_path, "policy", "resolve", str(tmp_path), "--json", "--org-policy", str(external))
    nested_cp = run_cli(tmp_path, "policy", "resolve", str(nested), "--json", "--org-policy", str(external))
    root = json.loads(root_cp.stdout)
    nested_data = json.loads(nested_cp.stdout)
    assert root_cp.returncode == nested_cp.returncode == 0
    assert nested_data["repository_policy_source"]["status"] == "loaded"
    assert nested_data["effective_policy"]["protected_paths"] == ["src/**"]
    assert root["effective_policy_id"] == nested_data["effective_policy_id"]


def test_external_policy_valid_from_subdirectory_and_symlink_back_inside_rejected(tmp_path):
    ensure_git_repo(tmp_path)
    nested = tmp_path / "packages" / "app"
    nested.mkdir(parents=True)
    external = tmp_path.parent / "outside-org.json"
    write_org(external, {"block_secret_patterns": True})
    cp = run_cli(tmp_path, "policy", "resolve", str(nested), "--json", "--org-policy", str(external))
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["organization_policy_status"] == "loaded"
    internal = tmp_path / "internal-org.json"
    write_org(internal, {"block_secret_patterns": True})
    link = tmp_path.parent / "outside-link-to-internal-org.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(internal)
    cp = run_cli(tmp_path, "policy", "resolve", str(nested), "--json", "--org-policy", str(link))
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["organization_policy_status"] == "trust_boundary_violation"


def test_cannot_determine_canonical_repository_root_fails_closed(tmp_path):
    external = tmp_path.parent / "nogit-org.json"
    write_org(external, {"block_dependency_additions": True})
    cp = run_cli(tmp_path, "policy", "resolve", str(tmp_path), "--json", "--org-policy", str(external))
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["resolution_status"] == "FAIL"
    assert any("repository_root_unresolved" in error for error in data["errors"])



def test_package_manager_supported_domain_and_invalid_outputs(tmp_path):
    org = tmp_path.parent / "org-pm-supported.json"
    write_org(org, {"package_manager": "pnpm"})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode == 0
    assert data["effective_policy"]["package_manager"] == "pnpm"
    for value in ["npm", "banana"]:
        org = tmp_path.parent / f"org-pm-{value}.json"
        write_org(org, {"package_manager": value})
        cp, data = resolve_json(tmp_path, "--org-policy", str(org))
        assert cp.returncode != 0
        assert data["resolution_status"] == "FAIL"
        assert f"org_policy_rule_invalid:unsupported_package_manager:{value}" in data["errors"]
        assert "package_manager" not in data["effective_policy"]
        human = run_cli(tmp_path, "policy", "resolve", str(tmp_path), "--org-policy", str(org))
        assert human.returncode != 0
        assert f"org_policy_rule_invalid:unsupported_package_manager:{value}" in human.stdout


def test_unsupported_repository_package_manager_fails_without_effective_value(tmp_path):
    write_repo_policy(tmp_path, {"package_manager": "npm"})
    cp, data = resolve_json(tmp_path)
    assert cp.returncode != 0
    assert data["resolution_status"] == "FAIL"
    assert "repository_policy_rule_invalid:unsupported_package_manager:npm" in data["errors"]
    assert "package_manager" not in data["effective_policy"]


def test_unsupported_repository_package_manager_does_not_mask_invalid_value_as_conflict(tmp_path):
    org = tmp_path.parent / "org-pnpm-repo-banana.json"
    write_org(org, {"package_manager": "pnpm"})
    write_repo_policy(tmp_path, {"package_manager": "banana"})
    cp, data = resolve_json(tmp_path, "--org-policy", str(org))
    assert cp.returncode != 0
    assert "repository_policy_rule_invalid:unsupported_package_manager:banana" in data["errors"]
    assert data["conflicts"] == []
    assert data["effective_policy"]["package_manager"] == "pnpm"
