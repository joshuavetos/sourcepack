# SourcePack CI usage

SourcePack can run in GitHub Actions without a SourcePack service. A minimal workflow installs the package and runs:

```bash
python -m pip install -e .
sourcepack diff . --ci
```

`--ci` keeps JSON output machine-readable and treats WARN as nonzero while FAIL remains nonzero and PASS exits 0.

CI may run `sourcepack policy validate . --json` before `sourcepack diff . --ci` to validate optional `.sourcepack/policy.json` without changing enforcement state. A missing policy file exits `0`; invalid JSON or a non-object root exits nonzero. Reserved fields, invalid report formats, unsafe ignored paths, and dangerous trust override attempts are reported in JSON output, but policy validation does not make those fields authoritative.

If you upload a local report artifact, review the contents first: report artifact files can include file paths, findings, command evidence hashes, and other repository-sensitive context. Do not upload sensitive reports by default without a project decision.

Hosted CI result: unavailable from this environment.

## GitHub Action reports

The composite action consumes an existing committed `.sourcepack/baseline/` and fails closed when it is missing. It does not run `sourcepack init` or `sourcepack baseline` in CI.

Reports are written to `sourcepack-report/` by default:

- `sourcepack.json` for the machine-readable SourcePack traffic report.
- `sourcepack.md` for the step-summary-friendly human report.
- `sourcepack.sarif.json` when the installed SourcePack writes SARIF.
- stdout, stderr, and command logs for CI troubleshooting.

SARIF is only a report format. It does not add a new judgment engine, does not change SourcePack's PASS/WARN/FAIL policy, and does not alter reason codes or verdicts.

If you choose to upload SARIF in GitHub code scanning, use the generated file only after deciding that report contents are acceptable for your repository:

```yaml
- name: Upload SourcePack SARIF
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sourcepack-report/sourcepack.sarif.json
```

## Replaying saved reports

CI enforcement should continue to use `sourcepack diff . --ci --json` against committed trusted baseline state. For audit readback of an already-produced report, use `sourcepack replay <report-or-bundle-path> --json`. Replay is read-only, does not require live baseline or prompt context, and does not rerun judgment over the current checkout.
