#!/usr/bin/env python3
"""Run the versioned SourcePack adversarial fixture corpus."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sourcepack.baseline import build_current_baseline
from sourcepack.judgment import judge_repo_change
from sourcepack.reason_codes import canonical_reason_codes


CORPUS_VERSION = "sourcepack.adversarial-corpus.v1"
CASE_SCHEMA_VERSION = "sourcepack.adversarial-case.v1"
DEFAULT_RUNS = 3
UNSTABLE_KEYS = {
    "active_build_id",
    "created_at",
    "generated_at",
    "head_commit",
    "repository_root",
    "timestamp",
}
EXPECTATION_KEYS = {
    "schema_version",
    "case_id",
    "expected_verdict",
    "required_findings",
    "forbidden_findings",
    "allowed_additional_findings",
    "deterministic",
}
FINDING_FIELDS = {
    "id",
    "analysis_status",
    "evidence_class",
    "trust_status",
    "source_path",
    "source_kind",
    "modified_by_patch",
}


def _git(repo: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def _normalize(value: Any, temp_root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize(item, temp_root)
            for key, item in sorted(value.items())
            if key not in UNSTABLE_KEYS
        }
    if isinstance(value, list):
        return [_normalize(item, temp_root) for item in value]
    if isinstance(value, str):
        return value.replace(str(temp_root), "<fixture-repo>")
    return value


def _finding_projection(report: dict[str, Any]) -> list[dict[str, Any]]:
    fields = (
        "id",
        "analysis_status",
        "evidence_class",
        "trust_status",
        "source_path",
        "source_kind",
        "modified_by_patch",
    )
    return [
        {field: finding.get(field) for field in fields if field in finding}
        for finding in report.get("findings", [])
    ]


def _validate_expected(expected: Any, case_id: str) -> dict[str, Any]:
    if not isinstance(expected, dict):
        raise ValueError("expectation root must be an object")
    unknown = sorted(set(expected) - EXPECTATION_KEYS)
    missing = sorted(EXPECTATION_KEYS - set(expected))
    if unknown or missing:
        raise ValueError(f"expectation fields invalid; missing={missing}, unknown={unknown}")
    if expected["schema_version"] != CASE_SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {expected['schema_version']!r}")
    if expected["case_id"] != case_id:
        raise ValueError(f"case_id must be {case_id!r}")
    if expected["expected_verdict"] not in {"PASS", "WARN", "FAIL"}:
        raise ValueError("expected_verdict must be PASS, WARN, or FAIL")
    if expected["deterministic"] is not True:
        raise ValueError("deterministic must be true")
    canonical = set(canonical_reason_codes())
    for key in ("forbidden_findings", "allowed_additional_findings"):
        values = expected[key]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"{key} must be an array of reason-code strings")
        invalid = sorted(set(values) - canonical)
        if invalid:
            raise ValueError(f"{key} contains unknown reason codes: {invalid}")
        if len(values) != len(set(values)):
            raise ValueError(f"{key} contains duplicate reason codes")
    required = expected["required_findings"]
    if not isinstance(required, list) or not required:
        raise ValueError("required_findings must be a non-empty array")
    for index, finding in enumerate(required):
        if not isinstance(finding, dict):
            raise ValueError(f"required_findings[{index}] must be an object")
        unknown_fields = sorted(set(finding) - FINDING_FIELDS)
        if unknown_fields:
            raise ValueError(f"required_findings[{index}] has unknown fields: {unknown_fields}")
        if not isinstance(finding.get("id"), str) or finding["id"] not in canonical:
            raise ValueError(f"required_findings[{index}].id is not a canonical reason code")
    required_ids = {finding["id"] for finding in required}
    forbidden = set(expected["forbidden_findings"])
    allowed = set(expected["allowed_additional_findings"])
    if required_ids & forbidden or forbidden & allowed:
        raise ValueError("required, forbidden, and allowed finding sets must not overlap")
    return expected


def _run_once(case_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"sourcepack-{case_dir.name}-") as raw:
        repo = Path(raw) / "repo"
        shutil.copytree(case_dir / "repo_before", repo)
        _git(repo, "init", "--quiet")
        _git(repo, "config", "user.email", "adversarial@sourcepack.invalid")
        _git(repo, "config", "user.name", "SourcePack Adversarial Runner")
        _git(repo, "add", ".")
        _git(repo, "commit", "--quiet", "-m", "trusted fixture baseline")
        baseline, created = build_current_baseline(repo, quiet=True)
        if not created:
            raise RuntimeError(f"could not initialize trusted baseline: {baseline}")
        patch_text = (case_dir / "patch.diff").read_text(encoding="utf-8")
        judgment = judge_repo_change(
            repo, patch_text=patch_text, allow_missing_baseline_init=False
        )
        report = judgment.report
        projected = {
            "verdict": report.get("verdict"),
            "findings": _finding_projection(report),
        }
        return _normalize(projected, repo)


def _matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if actual.get("verdict") != expected["expected_verdict"]:
        errors.append(
            f"verdict: expected {expected['expected_verdict']!r}, got {actual.get('verdict')!r}"
        )
    findings = actual.get("findings", [])
    canonical = set(canonical_reason_codes())
    invalid_ids = [
        item.get("id")
        for item in findings
        if not isinstance(item.get("id"), str) or item["id"] not in canonical
    ]
    if invalid_ids:
        errors.append(f"findings contain invalid reason codes: {invalid_ids!r}")
    for wanted in expected["required_findings"]:
        candidates = [item for item in findings if item.get("id") == wanted.get("id")]
        if not candidates:
            errors.append(f"missing finding {wanted.get('id')!r}")
            continue
        if not any(all(item.get(key) == value for key, value in wanted.items()) for item in candidates):
            errors.append(f"finding {wanted.get('id')!r} did not match {wanted!r}")
    required_by_id: dict[str, list[dict[str, Any]]] = {}
    for wanted in expected["required_findings"]:
        required_by_id.setdefault(wanted["id"], []).append(wanted)
    for item in findings:
        requirements = required_by_id.get(item.get("id"), [])
        if requirements and not any(
            all(item.get(key) == value for key, value in wanted.items())
            for wanted in requirements
        ):
            errors.append(f"unexpected projection for required finding {item.get('id')!r}: {item!r}")
    actual_ids = {item["id"] for item in findings if isinstance(item.get("id"), str)}
    forbidden = sorted(actual_ids & set(expected["forbidden_findings"]))
    if forbidden:
        errors.append(f"forbidden findings present: {forbidden}")
    permitted = (
        {item["id"] for item in expected["required_findings"]}
        | set(expected["allowed_additional_findings"])
    )
    unexpected = sorted(actual_ids - permitted)
    if unexpected:
        errors.append(f"unexpected findings present: {unexpected}")
    return errors


def run_corpus(corpus: Path, runs: int) -> dict[str, Any]:
    case_dirs = sorted(path for path in corpus.iterdir() if (path / "expected.json").is_file())
    results: list[dict[str, Any]] = []
    for case_dir in case_dirs:
        loaded = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
        expected = _validate_expected(loaded, case_dir.name)
        outputs = [_run_once(case_dir) for _ in range(runs)]
        encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in outputs]
        errors = _matches_expected(outputs[0], expected)
        if len(set(encoded)) != 1:
            errors.append("normalized output was not byte-identical across runs")
        results.append(
            {
                "case_id": case_dir.name,
                "runs": runs,
                "deterministic": len(set(encoded)) == 1,
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
                "actual": outputs[0],
            }
        )
    return {
        "schema_version": CORPUS_VERSION,
        "runs_per_case": runs,
        "case_count": len(results),
        "status": "PASS" if results and all(r["status"] == "PASS" for r in results) else "FAIL",
        "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT / "benchmarks" / "adversarial")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    args = parser.parse_args(argv)
    if args.runs < 2:
        parser.error("--runs must be at least 2 to prove determinism")
    report = run_corpus(args.corpus.resolve(), args.runs)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
