# GitHub Actions quickstart

This quickstart is for projects that already committed reviewed trusted baseline state under `.sourcepack/baseline/`.

CI must consume committed baseline state. It must not create, refresh, repair, or bless trusted baseline state for an untrusted pull request.

## Minimal copy-paste workflow

Create `.github/workflows/sourcepack.yml` in the repository that uses SourcePack:

```yaml
name: SourcePack

on:
  pull_request:
  push:
    branches: [main]

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - name: Check out trusted baseline for PRs
        if: github.event_name == 'pull_request'
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          fetch-depth: 0
      - name: Check out pushed commit
        if: github.event_name != 'pull_request'
        uses: actions/checkout@v4
      - name: Materialize the PR patch as working-tree changes
        if: github.event_name == 'pull_request'
        run: |
          git fetch --no-tags origin pull/${{ github.event.pull_request.number }}/head:sourcepack-pr-head
          MERGE_BASE="$(git merge-base HEAD sourcepack-pr-head)"
          git diff --binary "$MERGE_BASE" sourcepack-pr-head > /tmp/sourcepack-pr.patch
          git apply --index /tmp/sourcepack-pr.patch
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install sourcepack
      - run: sourcepack diff . --ci
```


For `pull_request` events, the workflow intentionally checks out the trusted base commit first, fetches the pull-request head through GitHub's `pull/<number>/head` ref, computes the merge base, and applies the PR patch without committing it. That leaves the proposed PR changes staged in the working tree, which is the input `sourcepack diff . --ci` evaluates. Do not replace this with a plain PR-head checkout; a clean checkout of the already-committed PR ref has no uncommitted diff for SourcePack to inspect and can report `no_diff`.

The `pull_request` path is the guardrail path. The `push` path is included only for projects that intentionally arrange a diff before running SourcePack or use it for additional status checks; a clean push checkout may have no diff for SourcePack to inspect.

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

Keep the PR patch-materialization steps from the minimal workflow when adding policy validation.

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.
