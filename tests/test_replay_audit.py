import json
import subprocess
import sys

from sourcepack.reports.json import traffic_report


def run_cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def sample_report():
    report = traffic_report("FAIL", findings=[{"id":"missing_file","severity":"error","category":"file","message":"missing","path":"src/nope.py"}], checked_categories=["baseline"])
    report["exit_code"] = 1
    report["baseline_metadata"] = {"state": "present"}
    report["prompt_context_metadata"] = {"present": False}
    report["patch_metadata"] = {"source": "saved"}
    report["environment_metadata"] = {"platform": "test"}
    report["policy_metadata"] = {"policy_present": True}
    return report


def test_replay_full_report_with_bundle_json_preserves_fields(tmp_path):
    path = tmp_path / "report.json"
    report = sample_report()
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    assert cp.returncode == 0
    assert cp.stderr == ""
    data = json.loads(cp.stdout)
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_with_replay_bundle"
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["reran_judgment"] is False
    assert data["verdict"] == "FAIL"
    assert data["exit_code"] == 1
    assert data["light"] == "RED LIGHT"
    assert data["reason_codes"] == ["missing_file"]
    assert data["reason_code_evidence"] == report["reason_code_evidence"]
    assert data["policy_metadata"] == {"policy_present": True}
    assert data["replay_bundle"] == report["replay_bundle"]


def test_replay_full_report_without_bundle_is_basic_summary(tmp_path):
    path = tmp_path / "report.json"
    report = sample_report()
    report.pop("replay_bundle")
    report.pop("environment_metadata")
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_without_replay_bundle"
    assert data["replay_bundle"] is None
    assert "replay bundle is missing" in data["warnings"][0]
    assert data["environment_metadata"] == {}


def test_replay_raw_bundle(tmp_path):
    path = tmp_path / "bundle.json"
    bundle = sample_report()["replay_bundle"]
    write_json(path, bundle)
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == bundle["schema_version"]
    assert data["input_type"] == "raw_replay_bundle"
    assert data["replay_bundle"] == bundle
    assert data["reran_judgment"] is False


def test_replay_invalid_json_missing_file_and_non_object_emit_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    for args in [(str(bad),), (str(tmp_path / "missing.json"),)]:
        cp = run_cli("replay", *args, "--json")
        assert cp.returncode != 0
        data = json.loads(cp.stdout)
        assert cp.stderr == ""
        assert data["schema_version"] == "sourcepack.replay.v1"
        assert data["input_schema_version"] is None
        assert data["valid"] is False
        assert data["errors"]
    array = tmp_path / "array.json"
    write_json(array, [])
    cp = run_cli("replay", str(array), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert cp.stderr == ""
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] is None
    assert "root must be a JSON object" in data["errors"][0]


def test_replay_unsupported_object_preserves_input_schema(tmp_path):
    path = tmp_path / "unsupported.json"
    write_json(path, {"schema_version": "custom.input.v9", "payload": {"unexpected": True}})
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert cp.stderr == ""
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "custom.input.v9"
    assert data["input_type"] == "unsupported_json_object"
    assert data["valid"] is False


def test_replay_corrupt_bundle_exits_nonzero(tmp_path):
    path = tmp_path / "bundle.json"
    write_json(path, {"schema_version": "sourcepack.replay_bundle.v1", "findings": {}})
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "sourcepack.replay_bundle.v1"
    assert data["input_type"] == "raw_replay_bundle"
    assert data["reran_judgment"] is False
    assert any("verdict" in err for err in data["errors"])


def test_replay_human_output_includes_summary(tmp_path):
    path = tmp_path / "report.json"
    write_json(path, sample_report())
    cp = run_cli("replay", str(path))
    assert cp.returncode == 0
    assert "Verdict: FAIL" in cp.stdout
    assert "Schema version: sourcepack.replay.v1" in cp.stdout
    assert "Input schema version: traffic_report.v1" in cp.stdout
    assert "Reason codes: missing_file" in cp.stdout
    assert "Reconstructed without rerunning judgment: True" in cp.stdout


def test_replay_does_not_mutate_repo_or_call_judgment_paths(tmp_path, monkeypatch):
    report_path = tmp_path / "report.json"
    write_json(report_path, sample_report())
    for rel in [".sourcepack/baseline", ".sourcepack/prompt", ".sourcepack/reports", ".sourcepack/evidence", ".git/hooks"]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    import sourcepack.cli as cli
    import sourcepack.replay as replay
    def fail(*args, **kwargs):
        raise AssertionError("judgment path called")
    for name in ("judge_repo_change", "build_repo_change_report", "validate_baseline", "dependency_inventory", "run_and_record"):
        if hasattr(cli, name):
            monkeypatch.setattr(cli, name, fail)
    result, code = replay.reconstruct_replay(report_path)
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert code == 0
    assert result["schema_version"] == "sourcepack.replay.v1"
    assert result["input_schema_version"] == "traffic_report.v1"
    assert result["reran_judgment"] is False
    assert before == after
