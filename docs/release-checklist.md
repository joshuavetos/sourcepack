# SourcePack release checklist

This checklist is for manual release preparation. It does not publish to PyPI, create GitHub releases, or replace maintainer approval.

## Preflight gates

- Confirm the release branch and commit SHA.
- Confirm `git status --short` is clean except intentional release-prep changes.
- Run the full pytest suite.
- Run SourcePack behavior-matrix and real-corpus checks.

## Build wheel/sdist

```bash
python -m pip install build
python -m build
```

Record the generated wheel and sdist filenames from `dist/`.

## Wheel install smoke

Create a clean virtual environment, install the built wheel, and run console/import checks outside editable mode.

## Sdist install smoke

Create a separate clean virtual environment, install the built sdist if feasible in the environment, and run the same console/import checks outside editable mode.

## SourcePack console smoke

Run:

```bash
sourcepack --version
sourcepack doctor
sourcepack demo
python -c "import sourcepack; print(sourcepack.__version__)"
```

## GitHub Action wrapper smoke

Verify `action.yml`, `scripts/sourcepack_action.py`, and `tests/test_github_action.py`. Confirm CI consumes committed trust state and does not create or update `.sourcepack/baseline/` automatically.

## Real-corpus local smoke

Run:

```bash
python tools/real_corpus_validation.py --repo /workspace/sourcepack --json
python tools/real_corpus_validation.py --repo /workspace/sourcepack --json --failures-only
```

The failures-only output should contain zero failure rows for release acceptance.

## Behavior matrix smoke

Run:

```bash
python tools/behavior_matrix.py
python tools/behavior_matrix.py --json
```

## README truth check

Run:

```bash
python -m pytest -q tests/test_readme_truth.py
```

Confirm README install claims match publication reality.

## Version/provenance capture

Record:

- branch
- commit SHA
- package version
- wheel filename and hash
- sdist filename and hash
- gate command results

## PyPI publish steps as manual checklist only

- Confirm maintainer approval.
- Confirm PyPI credentials and target repository.
- Upload only after wheel and sdist smoke pass.
- Verify the published project page and install command after publication.

## Rollback notes

- Do not delete local provenance records.
- If a published artifact is bad, stop promotion and publish a fixed version rather than mutating history.
- Document the failed artifact, reason, and replacement commit.
