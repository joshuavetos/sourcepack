# GitHub Actions quickstart

This quickstart is for projects that already committed reviewed trusted baseline state under `.sourcepack/baseline/`.

CI must consume committed baseline state. It must not create, refresh, repair, or bless trusted baseline state for an untrusted pull request.

## Minimal copy-paste workflow

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
        run: |
          git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}
          git reset --mixed ${{ github.event.pull_request.base.sha }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install sourcepack
      - run: sourcepack diff . --ci
```

The `pull_request` trigger path is the actual PR guardrail path. A clean PR checkout alone is structurally unsafe for local-diff validation because committed PR changes are already part of the checked-out tree, leaving no local workspace delta for `sourcepack diff . --ci` to inspect.

The explicit `git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}` and `git reset --mixed ${{ github.event.pull_request.base.sha }}` steps are highly intentional: they make the trusted base ref available, keep the PR files in the working tree, and reset the index to the trusted base commit. These steps make the PR delta visible to SourcePack's diff engine as local workspace modifications.

Do not create, refresh, repair, or bless `.sourcepack/baseline/` inside pull-request CI. Pull-request CI must consume the committed, reviewed trusted baseline state.

The `pull_request` path is the guardrail path. A clean push checkout may contain no uncommitted diff matrix for SourcePack to inspect, so do not present `push` as the main PR guardrail.

## Trust-state rule

Do not add any of these commands to pull-request CI:

```bash
sourcepack init . --auto
sourcepack baseline .
sourcepack baseline . --refresh
```

Create or refresh trusted baseline state only after a maintainer reviews the repository state and decides it should become trusted. Commit the resulting `.sourcepack/baseline/` state before relying on CI enforcement.

## Optional policy validation

If the project has `.sourcepack/policy.json`, CI can validate it before running the gate:

```yaml
      - run: sourcepack policy validate . --json
      - run: sourcepack diff . --ci
```

Keep the PR delta materialization steps from the minimal workflow when adding policy validation.

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.
