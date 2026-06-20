# SourcePack CI usage

SourcePack can run in GitHub Actions without a SourcePack service. A minimal workflow installs the package and runs:

```bash
python -m pip install -e .
sourcepack diff . --ci
```

`--ci` keeps JSON output machine-readable and treats WARN as nonzero while FAIL remains nonzero and PASS exits 0.

If you upload a local report artifact, review the contents first: report artifact files can include file paths, findings, command evidence hashes, and other repository-sensitive context. Do not upload sensitive reports by default without a project decision.

Hosted CI result: unavailable from this environment.

## GitHub Action reports

The composite action consumes an existing `.sourcepack/baseline/` and fails closed when it is missing. It does not run `sourcepack init` or `sourcepack baseline` in CI.

Reports are written to `sourcepack-report/` by default:

- `sourcepack.json` for the machine-readable SourcePack traffic report.
- `sourcepack.md` for the step-summary-friendly human report.
- `sourcepack.sarif.json` when the installed SourcePack writes SARIF.
- stdout, stderr, and command logs for CI troubleshooting.

SARIF is only a report format. It does not add a new judgment engine and does not change SourcePack's PASS/WARN/FAIL policy.

If you choose to upload SARIF in GitHub code scanning, use the generated file only after deciding that report contents are acceptable for your repository:

```yaml
- name: Upload SourcePack SARIF
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sourcepack-report/sourcepack.sarif.json
```
