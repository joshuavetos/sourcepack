import json
import shutil
from pathlib import Path

import pytest

from tools import adversarial_runner, external_repository_validation


def _write_case(corpus: Path, case_id: str = "case") -> Path:
    case = corpus / case_id
    (case / "repo_before").mkdir(parents=True)
    (case / "repo_before" / "app.py").write_text("print('ready')\n", encoding="utf-8")
    (case / "patch.diff").write_text("", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "schema_version": external_repository_validation.CASE_SCHEMA_VERSION,
                "case_id": case_id,
                "expected_verdict": "PASS",
                "required_findings": [],
                "forbidden_findings": ["malformed_diff"],
                "allowed_additional_findings": [],
                "deterministic": True,
            }
        ),
        encoding="utf-8",
    )
    return case


def test_all_vendored_fixtures_are_discovered() -> None:
    report = external_repository_validation.run_validation(runs=2)

    expected = sorted(
        path.name
        for path in external_repository_validation.DEFAULT_CORPUS.iterdir()
        if path.is_dir()
    )
    assert [case["case_id"] for case in report["cases"]] == expected
    assert report["case_count"] == 6
    assert report["status"] == "PASS"


def test_malformed_expectation_fails_clearly(tmp_path: Path) -> None:
    case = _write_case(tmp_path / "corpus")
    (case / "expected.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid expectation document.*missing="):
        external_repository_validation.run_validation(tmp_path / "corpus", runs=2)


def test_missing_fixture_file_fails_clearly(tmp_path: Path) -> None:
    case = _write_case(tmp_path / "corpus")
    (case / "patch.diff").unlink()

    with pytest.raises(ValueError, match="missing required paths:.*patch.diff"):
        external_repository_validation.run_validation(tmp_path / "corpus", runs=2)


def test_required_and_forbidden_findings_are_enforced(tmp_path: Path, monkeypatch) -> None:
    case = _write_case(tmp_path / "corpus")
    expected_path = case / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected["required_findings"] = [{"id": "new_file"}]
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(adversarial_runner, "_run_once", lambda _case: {"verdict": "PASS", "findings": [{"id": "malformed_diff"}]})

    result = external_repository_validation.run_validation(tmp_path / "corpus", runs=2)["cases"][0]

    assert result["status"] == "FAIL"
    assert "missing finding 'new_file'" in result["errors"]
    assert "forbidden findings present: ['malformed_diff']" in result["errors"]


def test_normalized_output_must_be_byte_identical(tmp_path: Path, monkeypatch) -> None:
    _write_case(tmp_path / "corpus")
    outputs = iter((
        {"verdict": "PASS", "findings": []},
        {"verdict": "PASS", "findings": [{"id": "new_file"}]},
    ))
    monkeypatch.setattr(adversarial_runner, "_run_once", lambda _case: next(outputs))

    result = external_repository_validation.run_validation(tmp_path / "corpus", runs=2)["cases"][0]

    assert result["deterministic"] is False
    assert "normalized output was not byte-identical across runs" in result["errors"]


def test_real_sourcepack_judgment_path_is_exercised(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    source_case = external_repository_validation.DEFAULT_CORPUS / "python-project"
    shutil.copytree(source_case, corpus / "python-project")
    real_judge = adversarial_runner.judge_repo_change
    calls = []

    def recording_judge(*args, **kwargs):
        calls.append((args, kwargs))
        return real_judge(*args, **kwargs)

    monkeypatch.setattr(adversarial_runner, "judge_repo_change", recording_judge)

    report = external_repository_validation.run_validation(corpus, runs=2)

    assert report["status"] == "PASS"
    assert len(calls) == 2
    assert all(call[1]["allow_missing_baseline_init"] is False for call in calls)
