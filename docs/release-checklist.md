# SourcePack release checklist

This checklist is for manual release preparation. It does not publish to PyPI, create GitHub releases, or replace maintainer approval.

## Preflight gates

- Confirm the release branch and commit SHA.
- Confirm `git status --short` is clean except intentional release-prep changes.
- Run the full pytest suite.
- Run SourcePack behavior-matrix and real-corpus checks.

## Release artifact smoke

Run the release smoke entrypoint before any upload:

```bash
python -m pip install build twine setuptools wheel
python scripts/release_smoke.py
```

The script removes `dist/`, `build/`, and root-level `*.egg-info` artifacts plus the build-backend-generated `src/sourcepack.egg-info` artifact before building. It does not recursively delete nested fixture, vendored, virtualenv, or test-repository `*.egg-info` directories. Cleanup failure is a release blocker.

The script builds deterministic artifacts with `python -m build --no-isolation`, so the maintainer-controlled environment is the build environment. Do not reuse artifacts from an earlier build step.

Expected build artifacts are exactly one wheel and one sdist for the version recorded in package metadata:

- `dist/sourcepack-<version>-py3-none-any.whl`
- `dist/sourcepack-<version>.tar.gz`

The smoke check runs `twine check` for package metadata validation, then opens the wheel and sdist directly and verifies packaged release/demo assets, including the demo `.env`, before install testing. It scans only packaged release/demo assets for forbidden token-shaped strings; it does not scan all source files.

The smoke check then creates separate fresh virtual environments for the wheel and sdist, installs each artifact, and runs:

```bash
sourcepack --version
sourcepack doctor
sourcepack demo
```

`sourcepack demo` may print the expected demo `Verdict: FAIL` / `RED LIGHT` report. That output is not a release-smoke failure as long as the command exits 0 and does not print the old missing-assets error.


## Build wheel/sdist

`python scripts/release_smoke.py` removes `dist/`, `build/`, and root-level `*.egg-info` artifacts plus `src/sourcepack.egg-info`, then builds exactly one wheel and one sdist with `python -m build --no-isolation`. Do not reuse artifacts from earlier build steps.

## Wheel install smoke

Covered by `python scripts/release_smoke.py`: it installs the freshly built wheel in a clean virtual environment and runs `sourcepack --version`, `sourcepack doctor`, and `sourcepack demo`.

## Sdist install smoke

Covered by `python scripts/release_smoke.py`: it installs the freshly built sdist in a separate clean virtual environment and runs the same console smoke commands.

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
- Verify the public PyPI project page and install from public PyPI after publication.

## Rollback notes

- Do not delete local provenance records.
- If a published artifact is bad, stop promotion and publish a fixed version rather than mutating history.
- Document the failed artifact, reason, and replacement commit.
