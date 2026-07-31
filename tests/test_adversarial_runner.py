import json
from pathlib import Path

import pytest

from tools import adversarial_runner


def test_run_corpus_rejects_fewer_than_two_runs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="runs must be at least 2 to prove determinism"):
        adversarial_runner.run_corpus(tmp_path, runs=1)


def test_malformed_patch_reaches_judgment_and_produces_expected_finding(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    case = corpus / "malformed-patch"
    repo_before = case / "repo_before"
    repo_before.mkdir(parents=True)
    (repo_before / "app.py").write_text("print('trusted')\n", encoding="utf-8")
    (case / "patch.diff").write_text("@@ nope @@\n+unsafe\n", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "schema_version": adversarial_runner.CASE_SCHEMA_VERSION,
                "case_id": case.name,
                "expected_verdict": "FAIL",
                "required_findings": [{"id": "malformed_diff"}],
                "forbidden_findings": [],
                "allowed_additional_findings": [],
                "deterministic": True,
            }
        ),
        encoding="utf-8",
    )

    report = adversarial_runner.run_corpus(corpus, runs=2)

    assert report["status"] == "PASS"
    assert report["cases"][0]["actual"]["findings"] == [{"id": "malformed_diff"}]
