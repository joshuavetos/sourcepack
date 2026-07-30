# SourcePack adversarial corpus

This directory is the versioned `sourcepack.adversarial-corpus.v1` attack corpus. Each case contains the complete trusted `repo_before/`, an untrusted `patch.diff`, a `sourcepack.adversarial-case.v1` expectation document, and a human-readable `case.md`.

Run all cases from the repository root:

```console
python tools/adversarial_runner.py
```

The runner validates every expectation document before executing its case. Expectations declare required findings, forbidden findings, and the only reason codes permitted as additional findings; unknown fields and noncanonical reason codes are rejected. The runner then creates a fresh Git repository and SourcePack trusted baseline for every attempt, submits the patch through `sourcepack.judgment.judge_repo_change`, removes unstable report fields, validates the exact permitted finding set and provenance, and compares canonical JSON bytes across three runs. It writes one JSON report to standard output and exits nonzero if any expectation or determinism check fails.
