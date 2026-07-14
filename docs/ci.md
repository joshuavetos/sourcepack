# SourcePack CI usage

SourcePack can run in CI without a SourcePack service. It is local-first: CI runs the CLI against repository evidence already present in the checkout.

## Basic CI command

The public package install path is:

```bash
python -m pip install sourcepack
sourcepack diff . --ci
```

Editable install is for SourcePack development from a checked-out repository:

```bash
python -m pip install -e .
sourcepack diff . --ci
```

`--ci` keeps JSON output machine-readable and, by default, treats WARN as nonzero while FAIL remains nonzero and PASS exits `0`. Add `--exit-policy fail-only` when a CI boundary should preserve WARN verdicts and findings but exit `0` unless the verdict is FAIL. `--exit-policy warn-or-fail` is the explicit spelling of the default WARN-or-FAIL blocking behavior. Verdicts are report judgments; process exits are command-boundary policy decisions and do not rewrite JSON or human verdicts.

## Trust-state rule

CI must consume committed `.sourcepack/baseline/` state. It must not create, refresh, repair, or bless trusted baseline state for an untrusted pull request.

Do not add any of these commands to pull-request CI:

```bash
sourcepack init . --auto
sourcepack baseline .
sourcepack baseline . --refresh
```

Create or refresh trusted baseline state only after a maintainer reviews the repository state and decides it should become trusted. Commit the resulting `.sourcepack/baseline/` state before relying on CI enforcement.

## Pull-request delta visibility

`sourcepack diff . --ci` checks a visible repo-state transition.

In pull-request CI, a clean checkout of the PR head may already contain the proposed changes as committed files, leaving no local workspace delta for SourcePack to inspect.

For pull-request guardrails, materialize the PR delta before running SourcePack. The recommended GitHub Actions pattern is documented in [`docs/github-action-quickstart.md`](github-action-quickstart.md).

The important shape is:

```bash
git fetch --no-tags origin "$BASE_REF"
git reset --mixed "$BASE_SHA"
sourcepack diff . --ci
```

That keeps PR files in the working tree while resetting the index to the trusted base commit, making the proposed change visible to SourcePack's diff engine.

## Optional policy validation

CI may run `sourcepack policy validate . --json` before `sourcepack diff . --ci` to validate optional `.sourcepack/policy.json` without changing enforcement state.

A missing policy file exits `0`. Invalid JSON or a non-object root exits nonzero. Reserved fields, invalid report formats, unsafe ignored paths, and dangerous trust override attempts are reported in JSON output, but policy validation does not make those fields authoritative.

```bash
sourcepack policy validate . --json
sourcepack diff . --ci
```

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.

## Report sensitivity

If you upload a local report artifact, review the contents first. Report artifact files can include file paths, findings, command evidence hashes, excerpts, and other repository-sensitive context.

Do not upload sensitive reports by default without a project decision.

Hosted CI result: unavailable from this environment.

## GitHub Action reports

The composite action consumes an existing committed `.sourcepack/baseline/` and fails closed when it is missing. It does not run `sourcepack init` or `sourcepack baseline` in CI.

Reports are written to `sourcepack-report/` by default:

- `sourcepack.json` for the machine-readable SourcePack traffic report.
- `sourcepack.md` for the step-summary-friendly human report.
- `sourcepack.sarif.json` when the installed SourcePack writes SARIF.
- `sourcepack.stdout.txt` for captured SourcePack stdout.
- `sourcepack.stderr.txt` for captured SourcePack stderr.
- `sourcepack-command.txt` for a human-readable command record.
- `sourcepack-command.json` for structured command arguments usable by downstream tooling.
- `sourcepack-pr-comment.md` for the rendered PR comment body when `comment-pr` is enabled.
- `sourcepack-pr-comment.txt` for PR comment create/update/skip/failure status when `comment-pr` is enabled.

If trusted baseline state is missing, the action reports that SourcePack failed closed, writes the same command artifacts, and exits without creating or updating baseline state.

SARIF is only a report format. It does not add a new judgment engine, does not change SourcePack's PASS/WARN/FAIL policy, and does not alter reason codes or verdicts.

If you choose to upload SARIF in GitHub code scanning, use the generated file only after deciding that report contents are acceptable for your repository:

```yaml
- name: Upload SourcePack SARIF
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sourcepack-report/sourcepack.sarif.json
```

## Pull request comments

The `comment-pr` input renders a compact SourcePack PR review comment when enabled.

The comment contains:

- the SourcePack traffic light and verdict
- the selected wrapper mode
- finding counts
- the exact SourcePack command
- top findings, capped for readability
- checked evidence categories when present in the JSON report
- not-checked categories when present in the JSON report
- the standard SourcePack limitation line

The full JSON, Markdown, stdout, stderr, command record, SARIF, and PR-comment body remain in the uploaded report artifact. The PR comment is intentionally smaller than the full report.

The comment uses a stable hidden marker:

```markdown
<!-- sourcepack-action-comment:v1 -->
```

The action uses that marker to update an existing SourcePack comment instead of posting duplicate comments on every PR synchronize event.

PR commenting requires a writable GitHub token. In a workflow that enables `comment-pr`, use permissions shaped like:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```

On pull requests from forks, GitHub may restrict write permissions. In that case, SourcePack should still write report artifacts and the GitHub step summary. PR comment status is recorded in `sourcepack-pr-comment.txt`.

PR commenting is presentation only. It does not change SourcePack's PASS/WARN/FAIL verdict, reason codes, SARIF output, artifacts, or exit code.

## Composite Action inputs

The repository action, whether used as `uses: ./` or as a tagged SourcePack action reference, exposes these inputs. They configure only wrapper behavior. Judgment remains delegated to `sourcepack diff`, and CI still consumes committed trusted baseline state only.

| Input | Default | Meaning |
| --- | --- | --- |
| `mode` | `ci` | SourcePack CLI mode: `ci`, `strict`, or `local`. |
| `sourcepack-version` | empty | Optional SourcePack package version to install from the configured Python package source; empty installs the current checkout. |
| `python-version` | `3.11` | Python version for the action runtime. |
| `baseline-path` | `.sourcepack/baseline` | Existing trusted baseline directory consumed by CI; the action fails closed if it is missing. |
| `report-dir` | `sourcepack-report` | Directory where action artifacts are written. |
| `json` | `true` | Preserve JSON report output as `sourcepack.json`. |
| `markdown` | `true` | Write `sourcepack.md` and append it to the GitHub step summary when available. |
| `sarif` | `true` | Copy `sourcepack.sarif.json` only when SourcePack produced SARIF; missing SARIF is non-fatal. |
| `fail-on-warn` | `false` | Add strict WARN handling outside modes that already fail on WARN. |
| `run-doctor` | `true` | Run `sourcepack doctor` before diff evaluation. |
| `upload-artifact` | `true` | Upload `report-dir` as a GitHub Actions artifact. |
| `comment-pr` | `false` | Post or update a compact SourcePack summary comment on pull requests. Requires PR write permissions and a writable token. Comment failures are recorded separately and do not replace SourcePack judgment. |

## Replaying saved reports

CI enforcement should continue to use `sourcepack diff . --ci --json` against committed trusted baseline state. SourcePack self-dogfood committed-range CI uses `sourcepack diff . --ci --json --exit-policy fail-only --base-ref "$BASE_SHA" --head-ref "$HEAD_SHA"` so legitimate new-file WARN findings remain visible without failing the gate; FAIL findings still exit nonzero.

For audit readback of an already-produced report, use:

```bash
sourcepack replay <report-or-bundle-path> --json
```

Replay JSON output uses `schema_version: "sourcepack.replay.v1"` and preserves the input report or bundle schema separately as `input_schema_version`.

Replay is read-only, does not require live baseline or prompt context, and does not rerun judgment over the current checkout. It does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.
