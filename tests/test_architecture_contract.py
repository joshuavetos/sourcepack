from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sourcepack.architecture_contract import (
    ArchitectureContractError,
    build_state,
    evaluate_change,
    load_contract,
    validate_contract,
)
from sourcepack.judgment import judge_repo_change
from sourcepack.reason_codes import is_canonical_reason_code


def contract(*, must_match: bool = True, exhaustive: bool = False, rules: list[dict] | None = None) -> dict:
    return {
        "schema_version": "architecture_contract.v1",
        "coverage": {"exhaustive": exhaustive, "paths": ["src/**/*.py"]},
        "layers": [
            {"id": "ui", "paths": ["src/ui/**/*.py"], "must_match": must_match},
            {"id": "data", "paths": ["src/data/**/*.py"], "must_match": must_match},
            {"id": "service", "paths": ["src/service/**/*.py"], "must_match": False},
        ],
        "rules": rules if rules is not None else [{"id": "arch.ui-no-data", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct"}],
    }


def contents(ui: str = "VALUE = 1\n", *, include_data: bool = True, contract_value: dict | None = None) -> dict[str, str]:
    result = {"sourcepack.architecture.json": json.dumps(contract_value or contract()), "src/ui/view.py": ui}
    if include_data:
        result["src/data/db.py"] = "def load(): return 1\n"
    return result


def ids(findings: list[dict]) -> list[str]:
    return [item["id"] for item in findings]


def test_new_direct_forbidden_import_is_instance_scoped_and_blocking() -> None:
    before = contents()
    baseline = build_state(before)
    after = contents("from src.data.db import load\n")
    findings, evidence = evaluate_change(before, after, baseline)
    assert ids(findings) == ["architecture_forbidden_import"]
    violation = evidence["rules"][0]["current_violation_instances"][0]
    assert violation["violation_id"].startswith("archv_")
    assert violation["rule_id"] == "arch.ui-no-data"
    assert violation["relationship_type"] == "direct_import"


def test_preexisting_violation_is_not_blame_and_new_instance_is() -> None:
    before = contents("import src.data.db\n")
    baseline = build_state(before)
    assert baseline["rules"][0]["current_status"] == "preexisting_violation"
    findings, _ = evaluate_change(before, before, baseline)
    assert "architecture_forbidden_import" not in ids(findings)
    after = dict(before, **{"src/ui/other.py": "import src.data.db\n"})
    findings, _ = evaluate_change(before, after, baseline)
    assert ids(findings).count("architecture_forbidden_import") == 1


def test_swapping_violation_still_finds_new_instance() -> None:
    before = contents("import src.data.db\n")
    baseline = build_state(before)
    after = contents("VALUE = 2\n")
    after["src/ui/other.py"] = "import src.data.db\n"
    findings, _ = evaluate_change(before, after, baseline)
    assert ids(findings).count("architecture_forbidden_import") == 1


def test_dynamic_resolution_distinguishes_literal_from_unresolved() -> None:
    literal = contents('import importlib\nmodule = importlib.import_module("src.data.db")\n')
    literal_state = build_state(literal)
    assert literal_state["rules"][0]["current_status"] == "preexisting_violation"
    assert literal_state["rules"][0]["current_violation_instances"][0]["resolution"] == "resolved_literal"
    before = contents("import src.data.db\n")
    baseline = build_state(before)
    dynamic = contents("import importlib\nmodule = importlib.import_module(name_from_config)\n")
    findings, _ = evaluate_change(before, dynamic, baseline)
    assert {"architecture_rule_unverifiable", "architecture_verifiability_reduced"} <= set(ids(findings))
    assert "architecture_forbidden_import" not in ids(findings)


def test_drift_is_rule_scoped_and_cannot_block_or_self_promote() -> None:
    two_rules = contract(rules=[
        {"id": "arch.ui-no-data", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct"},
        {"id": "arch.service-no-data", "type": "forbidden_import", "from": "service", "to": "data", "reachability": "direct"},
    ])
    before = contents(contract_value=two_rules)
    before["src/service/api.py"] = "VALUE = 1\n"
    baseline = build_state(before)
    drifted_contents = {key: value for key, value in before.items() if key != "src/ui/view.py"}
    drifted = build_state(drifted_contents, baseline)
    ui_rule = next(rule for rule in drifted["rules"] if rule["rule_id"] == "arch.ui-no-data")
    service_rule = next(rule for rule in drifted["rules"] if rule["rule_id"] == "arch.service-no-data")
    assert ui_rule["current_status"] == "drifted"
    assert service_rule["current_status"] == "valid"
    during = dict(drifted_contents, **{"src/ui/new.py": "import src.data.db\n", "src/service/api.py": "import src.data.db\n"})
    findings, _ = evaluate_change(drifted_contents, during, drifted)
    assert "architecture_contract_drift" in ids(findings)
    assert ids(findings).count("architecture_forbidden_import") == 1
    repaired_baseline = build_state(drifted_contents, baseline)
    repaired = dict(drifted_contents, **{"src/ui/view.py": "import src.data.db\n"})
    findings, _ = evaluate_change(drifted_contents, repaired, repaired_baseline)
    assert "architecture_violation_detected_after_drift" in ids(findings)
    assert "architecture_forbidden_import" not in ids(findings)


def test_contract_change_never_self_authorizes_and_scope_escape_is_visible() -> None:
    before = contents()
    baseline = build_state(before)
    weakened = contract(rules=[])
    after = contents("import src.data.db\n", contract_value=weakened)
    findings, _ = evaluate_change(before, after, baseline)
    assert {"architecture_contract_changed", "architecture_forbidden_import"} <= set(ids(findings))
    moved = dict(before)
    moved.pop("src/ui/view.py")
    moved["src/common/view.py"] = "VALUE = 1\n"
    findings, _ = evaluate_change(before, moved, baseline, path_transitions=[{"old_path": "src/ui/view.py", "new_path": "src/common/view.py", "deleted": False, "new_file": False}])
    assert "architecture_scope_changed" in ids(findings)
    # A same-path classification transition is separately detectable; a Git
    # rename is represented by contract transition evidence in integration.
    changed = dict(before)
    changed_contract = contract()
    changed_contract["layers"][0]["paths"] = ["src/elsewhere/**/*.py"]
    changed["sourcepack.architecture.json"] = json.dumps(changed_contract)
    findings, _ = evaluate_change(before, changed, baseline)
    assert "architecture_contract_changed" in ids(findings)


def test_retirement_deletion_and_replacement_preserve_history() -> None:
    violating = contents("import src.data.db\n")
    baseline = build_state(violating)
    deleted_contract = contract(rules=[])
    deleted = dict(violating, **{"sourcepack.architecture.json": json.dumps(deleted_contract)})
    findings, _ = evaluate_change(violating, deleted, baseline)
    assert "architecture_rule_retirement_unresolved" in ids(findings)
    clean = contents()
    clean_state = build_state(clean)
    findings, _ = evaluate_change(clean, dict(clean, **{"sourcepack.architecture.json": json.dumps(deleted_contract)}), clean_state)
    assert "architecture_rule_retired" in ids(findings)
    replacement = contract(rules=[
        {"id": "arch.ui-no-data", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct", "status": "retired", "replaced_by": "arch.ui-no-data.v2"},
        {"id": "arch.ui-no-data.v2", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct", "replaces": ["arch.ui-no-data"]},
    ])
    assert validate_contract(replacement)


def test_direct_reachability_is_explicit_and_transitive_is_rejected() -> None:
    invalid = contract()
    invalid["rules"][0]["reachability"] = "transitive"
    with pytest.raises(ArchitectureContractError, match="direct reachability"):
        validate_contract(invalid)
    direct = contents("import src.service.api\n")
    direct["src/service/api.py"] = "import src.data.db\n"
    assert build_state(direct)["rules"][0]["current_status"] == "valid"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_arch_repo(tmp_path: Path, *, ui: str = "VALUE = 1\n", contract_value: dict | None = None) -> Path:
    repo = tmp_path / "repo"; repo.mkdir()
    _git(repo, "init"); _git(repo, "config", "user.email", "test@example.com"); _git(repo, "config", "user.name", "Test")
    for path, text in contents(ui, contract_value=contract_value).items():
        target = repo / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text, encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-m", "initial")
    from sourcepack.baseline import build_current_baseline
    build_current_baseline(repo, quiet=True)
    return repo


def test_baseline_persists_authority_and_canonical_judgment_consumes_it(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _git(repo, "init"); _git(repo, "config", "user.email", "test@example.com"); _git(repo, "config", "user.name", "Test")
    for path, text in contents().items():
        target = repo / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text, encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-m", "initial")
    from sourcepack.baseline import build_current_baseline, validate_baseline
    build_current_baseline(repo, quiet=True)
    status = validate_baseline(repo)
    packet = repo / status["packet_path"]
    state = json.loads((packet / "architecture_state.json").read_text(encoding="utf-8"))
    assert state["rules"][0]["current_status"] == "valid"
    (repo / "src/ui/view.py").write_text("import src.data.db\n", encoding="utf-8")
    judgment = judge_repo_change(repo)
    assert judgment.verdict == "FAIL"
    assert "architecture_forbidden_import" in {item["id"] for item in judgment.report["findings"]}
    assert judgment.report["architecture"]["authority"] == "accepted_prechange_baseline"


def test_public_path_contract_weakening_and_rename_edit_remain_visible(tmp_path: Path) -> None:
    repo = init_arch_repo(tmp_path)
    weakened = json.dumps(contract(rules=[]), indent=2)
    patch = "\n".join([
        "diff --git a/sourcepack.architecture.json b/sourcepack.architecture.json", "--- a/sourcepack.architecture.json", "+++ b/sourcepack.architecture.json",
        "@@ -1 +1 @@", f"-{(repo / 'sourcepack.architecture.json').read_text(encoding='utf-8')}", f"+{weakened}",
        "diff --git a/src/ui/view.py b/src/common/view.py", "similarity index 50%", "rename from src/ui/view.py", "rename to src/common/view.py",
        "--- a/src/ui/view.py", "+++ b/src/common/view.py", "@@ -1 +1,2 @@", "-VALUE = 1", "+import src.data.db", "+VALUE = 2", "",
    ])
    report = judge_repo_change(repo, patch_text=patch).report
    report_ids = {item["id"] for item in report["findings"]}
    assert "architecture_contract_changed" in report_ids
    assert "architecture_scope_changed" in report_ids


def test_contract_deletion_baseline_carries_retired_history_and_stays_nonblocking(tmp_path: Path) -> None:
    repo = init_arch_repo(tmp_path, ui="import src.data.db\n")
    (repo / "sourcepack.architecture.json").unlink()
    _git(repo, "add", "-A"); _git(repo, "commit", "-m", "retire architecture contract")
    from sourcepack.baseline import build_current_baseline, validate_baseline
    build_current_baseline(repo, quiet=True)
    status = validate_baseline(repo)
    state = json.loads((repo / status["packet_path"] / "architecture_state.json").read_text(encoding="utf-8"))
    assert state["contract_present"] is False and state["contract_valid"] is True
    assert state["rules"][0]["current_status"] == "retired"
    assert state["rules"][0]["last_valid_violation_instances"]
    assert state["rules"][0]["unresolved_history"]
    (repo / "src/ui/view.py").write_text("import src.data.db\nVALUE = 2\n", encoding="utf-8")
    report = judge_repo_change(repo).report
    assert report["architecture"]["status"] == "retired"
    assert "architecture_forbidden_import" not in {item["id"] for item in report["findings"]}


def test_contract_removal_carries_clean_and_drifted_states() -> None:
    clean = contents()
    clean_retired = build_state({k: v for k, v in clean.items() if k != "sourcepack.architecture.json"}, build_state(clean))
    assert clean_retired["rules"][0]["current_status"] == "retired"
    assert clean_retired["rules"][0]["unresolved_history"] == []
    drift_source = contents(include_data=False)
    drift = build_state(drift_source)
    retired = build_state({k: v for k, v in drift_source.items() if k != "sourcepack.architecture.json"}, drift)
    assert retired["rules"][0]["unresolved_history"] == [{"event": "retired_with_unresolved_state", "prior_status": "drifted"}]


def test_duplicate_contract_rejected_by_baseline_and_schema_cli(tmp_path: Path, capsys) -> None:
    duplicate = '{"schema_version":"architecture_contract.v1","coverage":{"exhaustive":false,"paths":["src/**/*.py"]},"coverage":{"exhaustive":true,"paths":["src/**/*.py"]},"layers":[],"rules":[]}'
    repo = tmp_path / "repo"; repo.mkdir(); _git(repo, "init"); _git(repo, "config", "user.email", "test@example.com"); _git(repo, "config", "user.name", "Test")
    (repo / "sourcepack.architecture.json").write_text(duplicate, encoding="utf-8"); _git(repo, "add", "."); _git(repo, "commit", "-m", "duplicate")
    from sourcepack.baseline import build_current_baseline
    with pytest.raises(RuntimeError, match="duplicate JSON key"):
        build_current_baseline(repo, quiet=True)
    from sourcepack.cli import run_cli
    assert run_cli(["schema", "validate", "architecture-contract.v1", str(repo / "sourcepack.architecture.json")]) == 4
    capsys.readouterr()


def test_projection_failure_is_unverifiable_through_judgment(tmp_path: Path, monkeypatch) -> None:
    repo = init_arch_repo(tmp_path)
    import sourcepack.judgment as judgment_module
    monkeypatch.setattr(judgment_module, "_apply_patch_change_to_text", lambda _base, _change: None)
    patch = "diff --git a/src/ui/view.py b/src/ui/view.py\n--- a/src/ui/view.py\n+++ b/src/ui/view.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    report = judge_repo_change(repo, patch_text=patch).report
    report_ids = {item["id"] for item in report["findings"]}
    assert "architecture_rule_unverifiable" in report_ids
    assert "architecture_forbidden_import" not in report_ids


def test_clean_retirement_and_relative_uncertainty_use_canonical_judgment(tmp_path: Path) -> None:
    repo = init_arch_repo(tmp_path)
    (repo / "sourcepack.architecture.json").write_text(json.dumps(contract(rules=[])), encoding="utf-8")
    retirement = judge_repo_change(repo).report
    assert "architecture_rule_retired" in {item["id"] for item in retirement["findings"]}
    (repo / "sourcepack.architecture.json").write_text(json.dumps(contract()), encoding="utf-8")
    (repo / "src/ui/view.py").write_text("from ..missing import db\n", encoding="utf-8")
    uncertainty = judge_repo_change(repo).report
    uncertainty_ids = {item["id"] for item in uncertainty["findings"]}
    assert "architecture_rule_unverifiable" in uncertainty_ids
    assert "architecture_forbidden_import" not in uncertainty_ids


def test_missing_architecture_artifact_fails_closed_through_judgment(tmp_path: Path) -> None:
    repo = init_arch_repo(tmp_path)
    from sourcepack.baseline import validate_baseline
    packet = repo / validate_baseline(repo)["packet_path"]
    (packet / "architecture_state.json").unlink()
    (repo / "src/ui/view.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = judge_repo_change(repo).report
    assert report["verdict"] == "FAIL"
    assert "baseline_corrupt" in {item["id"] for item in report["findings"]}


def test_missing_or_corrupt_architecture_authority_fails_closed_in_evaluator() -> None:
    before = contents()
    finding, evidence = evaluate_change(before, before, {"contract_present": True, "contract_valid": False})
    assert ids(finding) == ["architecture_authority_corrupt"]
    assert evidence["status"] == "unavailable"


def test_violation_identity_ignores_resolution_but_includes_edge_paths() -> None:
    static = build_state(contents("import src.data.db\n"))["rules"][0]["current_violation_instances"][0]
    literal = build_state(contents('import importlib\ndb = importlib.import_module("src.data.db")\n'))["rules"][0]["current_violation_instances"][0]
    assert static["violation_id"] == literal["violation_id"]
    alternate_source = contents()
    alternate_source.pop("src/ui/view.py")
    alternate_source["src/ui/other.py"] = "import src.data.db\n"
    source_id = build_state(alternate_source)["rules"][0]["current_violation_instances"][0]["violation_id"]
    alternate_target = contents("import src.data.other\n")
    alternate_target["src/data/other.py"] = "VALUE = 1\n"
    target_id = build_state(alternate_target)["rules"][0]["current_violation_instances"][0]["violation_id"]
    assert len({static["violation_id"], source_id, target_id}) == 3


def test_relative_import_resolution_and_uncertainty() -> None:
    resolved = build_state(contents("from ..data import db\n"))["rules"][0]
    assert resolved["current_status"] == "preexisting_violation"
    assert resolved["current_violation_instances"][0]["target_path"] == "src/data/db.py"
    unresolved = build_state(contents("from ..missing import db\n"))["rules"][0]
    assert unresolved["current_status"] == "unverifiable"
    assert unresolved["current_verifiability"]["complete"] is False
    before = contents()
    findings, _ = evaluate_change(before, contents("from ..missing import db\n"), build_state(before))
    assert "architecture_rule_unverifiable" in ids(findings)
    assert "architecture_forbidden_import" not in ids(findings)


def test_retired_rule_never_regains_authority_and_active_rule_still_blocks() -> None:
    rules = [
        {"id": "arch.retired", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct", "status": "retired"},
        {"id": "arch.active", "type": "forbidden_import", "from": "service", "to": "data", "reachability": "direct"},
    ]
    before = contents(contract_value=contract(rules=rules))
    before["src/service/api.py"] = "VALUE = 1\n"
    baseline = build_state(before)
    after = dict(before, **{"src/ui/view.py": "import src.data.db\n", "src/service/api.py": "import src.data.db\n"})
    findings, _ = evaluate_change(before, after, baseline)
    forbidden = [item for item in findings if item["id"] == "architecture_forbidden_import"]
    assert len(forbidden) == 1 and "arch.active" in forbidden[0]["message"]
    proposed = contract(rules=[{**rules[1], "status": "retired"}, rules[0]])
    active_before = contents(contract_value=contract(rules=[rules[1]]))
    active_before["src/service/api.py"] = "VALUE = 1\n"
    active_after = dict(active_before, **{"src/service/api.py": "import src.data.db\n", "sourcepack.architecture.json": json.dumps(proposed)})
    findings, _ = evaluate_change(active_before, active_after, build_state(active_before))
    assert "architecture_forbidden_import" in ids(findings)


def test_duplicate_keys_rejected_by_authority_loader() -> None:
    duplicate = '{"schema_version":"architecture_contract.v1","coverage":{"exhaustive":false,"paths":["src/**/*.py"]},"coverage":{"exhaustive":true,"paths":["src/**/*.py"]},"layers":[],"rules":[]}'
    loaded, error = load_contract({"sourcepack.architecture.json": duplicate})
    assert loaded is None
    assert "duplicate JSON key: coverage" in str(error)


def test_rule_scoped_ambiguity_does_not_disable_unrelated_rule() -> None:
    value = contract(rules=[
        {"id": "arch.ui", "type": "forbidden_import", "from": "ui", "to": "data", "reachability": "direct"},
        {"id": "arch.service", "type": "forbidden_import", "from": "service", "to": "data", "reachability": "direct"},
    ])
    value["layers"].append({"id": "overlap", "paths": ["src/ui/ambiguous.py"], "must_match": False})
    state_contents = contents(contract_value=value)
    state_contents.update({"src/ui/ambiguous.py": "VALUE = 1\n", "src/service/api.py": "import src.data.db\n"})
    state = build_state(state_contents)
    assert next(r for r in state["rules"] if r["rule_id"] == "arch.ui")["current_status"] == "drifted"
    assert next(r for r in state["rules"] if r["rule_id"] == "arch.service")["current_status"] == "preexisting_violation"


def test_clean_retirement_is_canonical() -> None:
    before = contents()
    after = dict(before, **{"sourcepack.architecture.json": json.dumps(contract(rules=[]))})
    findings, _ = evaluate_change(before, after, build_state(before))
    assert "architecture_rule_retired" in ids(findings)
    assert is_canonical_reason_code("architecture_rule_retired")
