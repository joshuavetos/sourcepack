# GitHub Actions quickstart

This quickstart is for projects that already committed reviewed trusted baseline state under `.sourcepack/baseline/`.

CI must consume committed baseline state. It must not create, refresh, repair, or bless trusted baseline state for an untrusted pull request.

## Minimal pull-request workflow

Create `.github/workflows/sourcepack.yml` in the repository that uses SourcePack:

```yaml
name: SourcePack

on:
  pull_request:

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - name: Check out PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Materialize PR delta as workspace changes
        shell: bash
        run: |
          set -euo pipefail
          git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}
          git reset --mixed ${{ github.event.pull_request.base.sha }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: python -m pip install sourcepack

      - run: sourcepack diff . --ci
```

The `pull_request` trigger path is the actual PR guardrail path.

A clean PR checkout alone is structurally unsafe for local-diff validation because committed PR changes are already part of the checked-out tree, leaving no local workspace delta for `sourcepack diff . --ci` to inspect.

The explicit `git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}` and `git reset --mixed ${{ github.event.pull_request.base.sha }}` steps are intentional. They make the trusted base ref available, keep the PR files in the working tree, and reset the index to the trusted base commit. That makes the PR delta visible to SourcePack's diff engine as local workspace modifications.

Do not create, refresh, repair, or bless `.sourcepack/baseline/` inside pull-request CI. Pull-request CI must consume the committed, reviewed trusted baseline state.

## Using the bundled composite action

SourcePack also includes a composite GitHub Action.

Use it only after committed reviewed baseline state exists under `.sourcepack/baseline/`.

```yaml
name: SourcePack

on:
  pull_request:

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - name: Check out PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Materialize PR delta as workspace changes
        shell: bash
        run: |
          set -euo pipefail
          git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}
          git reset --mixed ${{ github.event.pull_request.base.sha }}

      - name: Run SourcePack
        uses: joshuavetos/sourcepack@main
        with:
          mode: ci
          upload-artifact: 'true'
          sarif: 'true'
```

The composite action preserves the same trust-state boundary:

- It consumes existing committed `.sourcepack/baseline/` state.
- It fails closed when that baseline is missing.
- It does not run `sourcepack init`.
- It does not run `sourcepack baseline`.
- It does not create or update trusted baseline state in CI.

By default, the action writes reports under `sourcepack-report/`, including:

- `sourcepack.json`
- `sourcepack.md`
- `sourcepack.stdout.txt`
- `sourcepack.stderr.txt`
- `sourcepack-command.txt`
- `sourcepack-command.json`
- `sourcepack.sarif.json` when SARIF is produced

`sourcepack-command.txt` is the human-readable command record. `sourcepack-command.json` records structured command arguments for downstream tooling.

If trusted baseline state is missing, the action still writes the fail-closed report artifacts and exits without creating or updating baseline state.

## Trust-state rule

Do not add any of these commands to pull-request CI:

```bash
sourcepack init . --auto
sourcepack baseline .
sourcepack baseline . --refresh
```

Create or refresh trusted baseline state only after a maintainer reviews the repository state and decides it should become trusted.

Commit the resulting `.sourcepack/baseline/` state before relying on CI enforcement.

## Optional policy validation

If the project has `.sourcepack/policy.json`, CI can validate it before running the gate:

```yaml
      - run: sourcepack policy validate . --json
      - run: sourcepack diff . --ci
```

Keep the PR delta materialization steps from the minimal workflow when adding policy validation.

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.

## SARIF upload

The composite action can preserve `sourcepack.sarif.json` when the installed SourcePack version produces SARIF.

SARIF is only a report format. It does not add a new judgment engine, does not change SourcePack's PASS/WARN/FAIL policy, and does not alter reason codes or verdicts.

If your repository has GitHub code scanning enabled and you accept uploading SourcePack report contents, you can add:

```yaml
      - name: Upload SourcePack SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: sourcepack-report/sourcepack.sarif.json
```

Review report contents before uploading artifacts. SourcePack reports can include file paths, findings, command records, hashes, excerpts, and other repository-sensitive context.

## Push workflows

The `pull_request` path is the guardrail path.

A clean push checkout may contain no uncommitted diff matrix for SourcePack to inspect, so do not present `push` as the main PR guardrail.

Push workflows can still run SourcePack for repository hygiene, but pull-request protection should use the PR delta materialization pattern above.
