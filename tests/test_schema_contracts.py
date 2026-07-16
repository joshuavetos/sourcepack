from __future__ import annotations

import json
from pathlib import Path

from sourcepack.cli import run_cli
from sourcepack.policy import resolve_effective_policy
from sourcepack.schema_contracts import CONTRACTS, schema_bytes, schema_for, validate_schema_registry


def _policy(tmp_path: Path) -> dict:
    (tmp_path / ".git").mkdir(exist_ok=True)
    return resolve_effective_policy(tmp_path)


def test_registry_schema_is_deterministic_and_metaschema_valid():
    validate_schema_registry()
    assert [c.name for c in CONTRACTS] == sorted(c.name for c in CONTRACTS)
    assert schema_bytes(CONTRACTS[0]) == schema_bytes(CONTRACTS[0])
    assert schema_for(CONTRACTS[0])["$id"].startswith("https://schemas.sourcepack.local/")


def test_schema_validate_effective_policy_and_alias(tmp_path: Path, capsys):
    artifact = tmp_path / "policy.json"
    artifact.write_text(json.dumps(_policy(tmp_path)), encoding="utf-8")
    assert run_cli(["schema", "validate", "effective-policy.v1", str(artifact)]) == 0
    capsys.readouterr()
    assert run_cli(["schema", "validate", "effective-policy", str(artifact), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"


def test_schema_validation_is_strict_and_secret_safe(tmp_path: Path, capsys):
    data = _policy(tmp_path)
    data["effective_policy_id"] = "epol_BAD"
    data["secret"] = "sk-proj-THISMUSTNOTAPPEARINOUTPUT123456"
    artifact = tmp_path / "invalid.json"
    artifact.write_text(json.dumps(data), encoding="utf-8")
    assert run_cli(["schema", "validate", "effective-policy.v1", str(artifact), "--json"]) == 5
    output = capsys.readouterr().out
    assert "THISMUSTNOTAPPEAR" not in output
    assert json.loads(output)["error_count"] >= 2


def test_schema_rejects_malformed_duplicate_and_unknown(tmp_path: Path, capsys):
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version":"x", "schema_version":"y"}', encoding="utf-8")
    assert run_cli(["schema", "validate", "effective-policy.v1", str(malformed)]) == 4
    assert run_cli(["schema", "show", "effective-policy.v2"]) == 2
    assert run_cli(["schema", "validate", "effective-policy.v1", str(tmp_path)]) == 3
    assert "Traceback" not in capsys.readouterr().err


def test_schema_rejects_wrong_value_type_for_every_rule(tmp_path: Path):
    cases = {
        "block_dependency_additions": 12,
        "block_secret_patterns": ["src/**"],
        "max_changed_lines": True,
        "package_manager": False,
        "protected_paths": "pnpm",
        "require_tests_for": 900,
    }
    for rule, invalid in cases.items():
        data = _policy(tmp_path)
        data["effective_policy"] = {rule: invalid}
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"{rule}.json", data)]) == 5


def _write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_schema_requires_complete_rule_results_and_accepts_sparse_effective_variants(tmp_path: Path):
    data = _policy(tmp_path)
    assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / "empty.json", data)]) == 0
    data["effective_policy"] = {"max_changed_lines": 1}
    assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / "populated.json", data)]) == 0
    del data["rules"]["max_changed_lines"]
    assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / "missing-rule.json", data)]) == 5


def test_unknown_schema_json_and_read_error_classification(tmp_path: Path, capsys, monkeypatch):
    artifact = _write(tmp_path / "policy.json", _policy(tmp_path))
    assert run_cli(["schema", "validate", "unknown.v1", artifact, "--json"]) == 2
    unknown = json.loads(capsys.readouterr().out)
    assert unknown["status"] == "unknown_schema"
    import sourcepack.schema_contracts as contracts
    monkeypatch.setattr(contracts.Path, "read_bytes", lambda _: (_ for _ in ()).throw(OSError("nope")))
    assert run_cli(["schema", "validate", "effective-policy.v1", artifact, "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["exit_classification"] == "unreadable_input"


def test_resolver_output_corpus_covers_policy_resolution_variants(tmp_path: Path):
    """Every resolver branch below must satisfy the public contract."""
    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    org = tmp_path / "org.json"
    org.write_text(json.dumps({"schema_version": "sourcepack.org_policy.v1", "policy_id": "engineering", "rules": {"block_dependency_additions": True, "block_secret_patterns": True, "protected_paths": ["src/**"], "require_tests_for": ["tests/**"], "max_changed_lines": 10, "package_manager": "pnpm"}}), encoding="utf-8")
    malformed = tmp_path / "bad-org.json"
    malformed.write_text("{", encoding="utf-8")
    inside = repo / "inside.json"
    inside.write_text(org.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / ".sourcepack").mkdir()
    (repo / ".sourcepack" / "policy.json").write_text(json.dumps({"rules": {"max_changed_lines": 5}}), encoding="utf-8")
    corpus = [
        resolve_effective_policy(repo),
        resolve_effective_policy(repo, org_policy_mode="required"),
        resolve_effective_policy(repo, org),
        resolve_effective_policy(repo, malformed),
        resolve_effective_policy(repo, inside),
    ]
    # A repository maximum above the organization maximum is an emitted
    # rejected-weakening variant, distinct from the strengthening case above.
    (repo / ".sourcepack" / "policy.json").write_text(json.dumps({"rules": {"max_changed_lines": 20}}), encoding="utf-8")
    corpus.append(resolve_effective_policy(repo, org))
    for index, artifact in enumerate(corpus):
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"variant-{index}.json", artifact)]) == 0


def _independent_policy(*, status: str = "PASS", effective: dict | None = None) -> dict:
    """Literal contract fixture; it deliberately does not call the resolver."""
    values = {
        "block_dependency_additions": None, "block_secret_patterns": None,
        "protected_paths": None, "require_tests_for": None,
        "max_changed_lines": None, "package_manager": None,
    }
    methods = {
        "block_dependency_additions": "boolean_false_less_than_true_or",
        "block_secret_patterns": "boolean_false_less_than_true_or",
        "protected_paths": "normalized_set_union",
        "require_tests_for": "normalized_set_union",
        "max_changed_lines": "lower_positive_integer_is_stricter_absent_is_no_limit",
        "package_manager": "string_equality_no_ordering",
    }
    rules = {name: {"organization_constraint": value, "repository_contribution": value,
                    "effective_value": value, "provenance": {"sources": []} if name not in {"protected_paths", "require_tests_for"} else {},
                    "comparison_method": methods[name], "compatibility_status": "absent"}
             for name, value in values.items()}
    required_missing = status == "FAIL"
    return {"schema_version": "sourcepack.effective_policy.v1", "resolution_status": status,
            "organization_policy_mode": "required" if required_missing else "optional", "organization_policy_status": "required_but_missing" if required_missing else "not_supplied",
            "organization_policy_source": {"supplied": False, "path": None},
            "organization_policy_id": None, "organization_policy_hash": None,
            "repository_policy_source": {"path": ".sourcepack/policy.json", "status": "absent"},
            "repository_policy_hash": None, "effective_policy": effective or {}, "rules": rules,
            "strengthening_contributions": [], "rejected_weakening_attempts": [], "conflicts": [],
            "errors": [] if status == "PASS" else ["org_policy_required_but_missing"],
            "effective_policy_id": "epol_0123456789abcdef0123456789abcdef"}


def test_independent_contract_fixtures_cover_pass_and_fail_variants(tmp_path: Path):
    fixtures = [
        _independent_policy(),
        _independent_policy(effective={"max_changed_lines": 7}),
        _independent_policy(status="FAIL"),
        {**_independent_policy(status="FAIL"), "organization_policy_mode": "optional", "organization_policy_status": "invalid", "organization_policy_source": {"supplied": True, "path": "org.json", "resolved_path": "org.json"}, "organization_policy_hash": "a" * 64, "errors": ["org_policy_malformed_json"]},
    ]
    for index, artifact in enumerate(fixtures):
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"independent-{index}.json", artifact)]) == 0


def test_nested_rule_positions_and_change_records_reject_wrong_types(tmp_path: Path):
    cases = [
        ("rules.block_dependency_additions.effective_value", lambda d: d["rules"]["block_dependency_additions"].__setitem__("effective_value", 5)),
        ("rules.max_changed_lines.repository_contribution", lambda d: d["rules"]["max_changed_lines"].__setitem__("repository_contribution", True)),
        ("rules.package_manager.organization_constraint", lambda d: d["rules"]["package_manager"].__setitem__("organization_constraint", False)),
        ("rules.protected_paths.effective_value", lambda d: d["rules"]["protected_paths"].__setitem__("effective_value", "src/**")),
        ("rejected", lambda d: d.__setitem__("rejected_weakening_attempts", [{"rule": "max_changed_lines", "organization_value": 2, "repository_value": True, "comparison_method": "m", "reason": "r"}])),
        ("conflict", lambda d: d.__setitem__("conflicts", [{"rule": "package_manager", "organization_value": False, "repository_value": "pnpm", "comparison_method": "m", "reason": "r"}])),
    ]
    for index, (_name, mutate) in enumerate(cases):
        artifact = _independent_policy()
        mutate(artifact)
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"nested-{index}.json", artifact)]) == 5


def _tree_snapshot(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def test_schema_commands_are_read_only_inside_and_outside_git(tmp_path: Path, monkeypatch):
    import subprocess
    for name, git in (("git", True), ("plain", False)):
        root = tmp_path / name
        root.mkdir()
        if git:
            subprocess.run(["git", "init", "-q", str(root)], check=True)
        artifact = root / "policy.json"
        artifact.write_text(json.dumps(_independent_policy()), encoding="utf-8")
        before = _tree_snapshot(root)
        before_status = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=True).stdout if git else None
        monkeypatch.chdir(root)
        assert run_cli(["schema", "list", "--json"]) == 0
        assert run_cli(["schema", "show", "effective-policy.v1"]) == 0
        assert run_cli(["schema", "validate", "effective-policy.v1", str(artifact)]) == 0
        assert _tree_snapshot(root) == before
        assert not (root / ".sourcepack").exists()
        if git:
            assert subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=True).stdout == before_status


def test_semantic_resolver_relationships_reject_impossible_combinations(tmp_path: Path):
    cases = [
        lambda d: d.__setitem__("errors", ["unexpected"]),
        lambda d: d.__setitem__("resolution_status", "FAIL"),
        lambda d: d.update({"organization_policy_status": "required_but_missing", "organization_policy_mode": "optional"}),
        lambda d: d.update({"organization_policy_status": "loaded", "organization_policy_source": {"supplied": False, "path": None}}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "absent"}, "repository_policy_hash": "sha256:" + "a" * 64}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "loaded"}, "repository_policy_hash": None}),
        lambda d: d.__setitem__("conflicts", [{"rule": "package_manager", "organization_value": "pnpm", "repository_value": "pnpm", "comparison_method": "m", "reason": "r"}]),
        lambda d: d.__setitem__("rejected_weakening_attempts", [{"rule": "max_changed_lines", "organization_value": 2, "repository_value": 3, "comparison_method": "m", "reason": "r"}]),
    ]
    for index, mutate in enumerate(cases):
        artifact = _independent_policy()
        mutate(artifact)
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"semantic-{index}.json", artifact)]) == 5


def test_semantic_organization_status_error_relationships_are_bidirectional(tmp_path: Path, capsys):
    invalid_source = {"supplied": True, "path": "bad.json", "resolved_path": "bad.json"}
    cases = [
        lambda d: d.update({"organization_policy_status": "invalid", "organization_policy_source": invalid_source}),
        lambda d: d.update({"organization_policy_status": "trust_boundary_violation", "organization_policy_source": invalid_source}),
        lambda d: d.update({"organization_policy_mode": "required"}),
        lambda d: d.update({"resolution_status": "FAIL", "errors": ["policy_conflict"]}),
        lambda d: d.update({"resolution_status": "FAIL", "errors": ["repository_policy_weakening_attempt"]}),
        lambda d: d.update({"resolution_status": "FAIL", "organization_policy_mode": "required", "organization_policy_status": "loaded", "organization_policy_source": {"supplied": True, "path": "org.json", "resolved_path": "org.json"}, "organization_policy_id": "engineering", "organization_policy_hash": "sha256:" + "a" * 64, "errors": ["org_policy_required_but_missing"]}),
        lambda d: d.update({"resolution_status": "FAIL", "organization_policy_status": "invalid", "organization_policy_source": invalid_source, "errors": ["repository_root_unresolved"]}),
        lambda d: d.update({"resolution_status": "FAIL", "organization_policy_status": "trust_boundary_violation", "organization_policy_source": invalid_source, "errors": ["repository_root_unresolved"]}),
    ]
    for index, mutate in enumerate(cases):
        artifact = _independent_policy()
        mutate(artifact)
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"organization-{index}.json", artifact), "--json"]) == 5
        payload = json.loads(capsys.readouterr().out)
        assert any(error["keyword"].endswith("mismatch") for error in payload["errors"])


def test_repository_invalid_state_semantics_and_required_missing_source(tmp_path: Path):
    import subprocess
    repo = tmp_path / "invalid-repository"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".sourcepack").mkdir()
    (repo / ".sourcepack" / "policy.json").write_text("{", encoding="utf-8")
    emitted = resolve_effective_policy(repo)
    assert emitted["repository_policy_source"]["status"] == "invalid"
    assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / "repository-invalid-valid.json", emitted)]) == 0
    invalid_source = {"supplied": False, "path": "org.json", "resolved_path": "/tmp/org.json"}
    cases = [
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "invalid"}, "resolution_status": "PASS", "errors": [], "repository_policy_hash": "sha256:" + "a" * 64}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "invalid"}, "resolution_status": "FAIL", "errors": ["repository_root_unresolved"], "repository_policy_hash": "sha256:" + "a" * 64}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "invalid"}, "resolution_status": "FAIL", "errors": ["repository_policy_config_invalid_json:x"], "repository_policy_hash": None}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "loaded"}, "repository_policy_hash": "sha256:" + "a" * 64, "errors": ["repository_policy_config_invalid_json:x"], "resolution_status": "FAIL"}),
        lambda d: d.update({"repository_policy_source": {"path": ".sourcepack/policy.json", "status": "absent"}, "errors": ["repository_policy_config_invalid_json:x"], "resolution_status": "FAIL"}),
        lambda d: d.update({"resolution_status": "FAIL", "organization_policy_mode": "required", "organization_policy_status": "required_but_missing", "organization_policy_source": invalid_source, "errors": ["org_policy_required_but_missing"]}),
    ]
    for index, mutate in enumerate(cases):
        artifact = _independent_policy()
        mutate(artifact)
        assert run_cli(["schema", "validate", "effective-policy.v1", _write(tmp_path / f"repository-invalid-{index}.json", artifact)]) == 5
