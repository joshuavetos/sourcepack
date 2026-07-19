# SourcePack public-alpha readiness

This document is a release-readiness checklist and provenance template. It does not publish artifacts, create tags, or grant release approval.

## 1.10.0a3 public-alpha release note

1.10.0a3 is a public alpha intended for end-to-end outside evaluation. This release-prep note covers accepted hardening for release-smoke automation and failure-injection coverage, policy/SARIF handling, `sourcepack policy validate [repo] [--json]`, `sourcepack replay <report-or-bundle-path> [--json]` with stable `sourcepack.replay.v1` output, GitHub Action UX and composite Action integration coverage, the committed trusted baseline and self-dogfooding gate, ugly-repo fixtures, baseline lifecycle fixtures, and local-evidence trust-boundary hardening.

SourcePack remains bounded to locally verifiable repository evidence and does not claim to prove code correctness, security, dependency safety or reputation, runtime success, semantic validity, external API truth, or user intent.

## Accepted RC commit/provenance

- Branch: `work` from `git branch --show-current`.
- Commit SHA: missing; record the final release commit after merge.
- Package version: `1.10.0a3` from `pyproject.toml`.
- Wheel artifact: produced during release validation with `python -m build`; record the final uploaded `dist/*.whl` path at publish time.
- Sdist artifact: produced during release validation with `python -m build`; record the final uploaded `dist/*.tar.gz` path at publish time.
- Reviewer/approver: missing; record only after maintainer approval.
- Date: missing; record only when release approval occurs.

## GitHub Action wrapper acceptance

- `action.yml` present: yes.
- `scripts/sourcepack_action.py` present: yes.
- Missing baseline fails closed: documented in `docs/ci.md`; verify with the composite-action tests before release.
- CI does not create or update `.sourcepack/baseline/`: documented in `docs/ci.md` and `.github/workflows/sourcepack.yml`; verify in CI before release.

## Packaging/release-smoke acceptance

- Wheel built: verify with `python -m build` before publishing.
- Sdist built: verify with `python -m build` before publishing.
- Clean wheel install smoke passed: verify with `python scripts/release_smoke.py`.
- Clean sdist install smoke passed: verify with `python scripts/release_smoke.py`.
- Console commands passed outside editable install: verify with `python scripts/release_smoke.py`.

## Baseline lifecycle docs

- Baseline lifecycle documented in `docs/baseline-lifecycle.md`: yes.
- Baseline/prompt separation explicit: yes.
- CI trust-state creation prohibited: yes.

## Reason-code/report docs

- Reason-code documentation updated: yes, tracked in `docs/reason-codes.md`.
- Human report wording reviewed: missing; run `python tools/golden_demo.py --clean` and review generated report wording.
- JSON-only mode preserved: verify with `sourcepack diff . --json` or the relevant pytest coverage before release.

## Behavior matrix status

- `python tools/behavior_matrix.py`: verify before publishing.
- `python tools/behavior_matrix.py --json`: verify before publishing.

## Real-corpus status

- Total runs: missing; run `python tools/real_corpus_validation.py` and record the summary.
- Executed runs: missing; run `python tools/real_corpus_validation.py` and record the summary.
- Failures-only rows: missing; run `python tools/real_corpus_validation.py --failures-only --json` and record the row count.
- Trust violations: missing; run `python tools/real_corpus_validation.py` and record any trust-violation summary.

## Full pytest status

- `python -m pytest -q`: verify before publishing.

## Install status

- Editable install: verify with `python -m pip install -e .` when preparing a development checkout.
- Wheel install: verify with `python scripts/release_smoke.py`.
- Sdist install: verify with `python scripts/release_smoke.py`.

## Unsupported ecosystem policy

Unsupported ecosystems remain WARN/YELLOW uncertainty. SourcePack should not add ecosystem support unless intentionally implemented and tested.

## Known limitations

- Unsupported ecosystems remain WARN/YELLOW.
- Baseline must be maintained intentionally.
- CI must not create trust state.
- Local evidence can only verify local evidence.
- Real repos may expose layout cases not yet covered.

## Non-claims: do not claim SourcePack proves

- Code correctness.
- Security.
- Dependency safety.
- Runtime success.
- Semantic validity.
- External API truth.
- User intent.

## Rollback criteria

Stop or roll back release promotion if any accepted gate fails, built artifacts cannot be installed in a clean environment, console commands fail outside editable install, real-corpus failures-only output is nonzero, or documentation introduces product overclaims.

## Manual publish checklist

- Maintainer merge approval.
- Branch protection satisfied.
- PyPI publish approval.
- GitHub release tag approval.
- Marketplace release approval, if applicable.
- Post-publish install verification.
