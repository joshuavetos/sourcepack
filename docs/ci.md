# SourcePack CI usage

SourcePack can run in GitHub Actions without a SourcePack service. A minimal workflow installs the package and runs:

```bash
python -m pip install -e .
sourcepack diff . --ci
```

`--ci` keeps JSON output machine-readable and treats WARN as nonzero while FAIL remains nonzero and PASS exits 0.

If you upload a local report artifact, review the contents first: report artifact files can include file paths, findings, command evidence hashes, and other repository-sensitive context. Do not upload sensitive reports by default without a project decision.

Hosted CI result: unavailable from this environment.
