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
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install sourcepack
      - run: sourcepack diff . --ci
```

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

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.
