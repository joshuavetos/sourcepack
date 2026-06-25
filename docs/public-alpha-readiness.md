# SourcePack public-alpha readiness

This document is a release-readiness checklist and provenance template. It does not publish artifacts, create tags, or grant release approval.


## 1.10.0a2 public-alpha release note

1.10.0a2 is a public alpha intended for end-to-end outside evaluation. This release-prep note covers accepted hardening for release-smoke automation and failure-injection coverage, policy/SARIF handling, `sourcepack policy validate [repo] [--json]`, `sourcepack replay <report-or-bundle-path> [--json]` with stable `sourcepack.replay.v1` output, GitHub Action UX and composite Action integration coverage, the committed trusted baseline and self-dogfooding gate, ugly-repo fixtures, baseline lifecycle fixtures, and local-evidence trust-boundary hardening.

SourcePack remains bounded to locally verifiable repository evidence and does not claim to prove code correctness, security, dependency safety or reputation, runtime success, semantic validity, external API truth, or user intent.

## Accepted RC commit/provenance

- Branch:
- Commit SHA:
- Package version:
- Wheel artifact:
- Sdist artifact:
- Reviewer/approver:
- Date:

## GitHub Action wrapper acceptance

- `action.yml` present:
- `scripts/sourcepack_action.py` present:
- Missing baseline fails closed:
- CI does not create or update `.sourcepack/baseline/`:

## Packaging/release-smoke acceptance

- Wheel built:
- Sdist built:
- Clean wheel install smoke passed:
- Clean sdist install smoke passed:
- Console commands passed outside editable install:

## Baseline lifecycle docs

- Baseline lifecycle documented in `docs/baseline-lifecycle.md`:
- Baseline/prompt separation explicit:
- CI trust-state creation prohibited:

## Reason-code/report docs

- Reason-code documentation updated:
- Human report wording reviewed:
- JSON-only mode preserved:

## Behavior matrix status

- `python tools/behavior_matrix.py`:
- `python tools/behavior_matrix.py --json`:

## Real-corpus status

- Total runs:
- Executed runs:
- Failures-only rows:
- Trust violations:

## Full pytest status

- `python -m pytest -q`:

## Install status

- Editable install:
- Wheel install:
- Sdist install:

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
