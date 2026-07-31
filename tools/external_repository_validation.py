#!/usr/bin/env python3
"""Run the deterministic, vendored external-repository validation corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import adversarial_runner


CORPUS_VERSION = "sourcepack.external-repository-corpus.v1"
CASE_SCHEMA_VERSION = "sourcepack.external-repository-case.v1"
DEFAULT_CORPUS = REPO_ROOT / "benchmarks" / "external_repositories"


def run_validation(corpus: Path = DEFAULT_CORPUS, runs: int = 3) -> dict:
    """Validate every external-style fixture through the canonical judgment path."""
    return adversarial_runner.run_corpus(
        corpus,
        runs,
        corpus_version=CORPUS_VERSION,
        case_schema_version=CASE_SCHEMA_VERSION,
        corpus_label="external-repository corpus",
        allow_empty_required=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--runs", type=int, default=adversarial_runner.DEFAULT_RUNS)
    args = parser.parse_args(argv)
    if args.runs < 2:
        parser.error("--runs must be at least 2 to prove determinism")
    try:
        report = run_validation(args.corpus.resolve(), args.runs)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"external-repository validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
