# SourcePack

<p align="center">
  <img
    src="docs/assets/sourcepack-hero.png"
    alt="SourcePack checking an AI-generated code change against repository evidence"
    width="100%"
  >
</p>

![PyPI](https://img.shields.io/pypi/v/sourcepack)
![Python](https://img.shields.io/pypi/pyversions/sourcepack)
![License](https://img.shields.io/github/license/joshuavetos/sourcepack)
![Status](https://img.shields.io/badge/status-public%20alpha-orange)

**SourcePack blocks AI-generated code changes that rely on repository facts the local codebase does not support.**

It checks proposed diffs against locally verifiable evidence such as tracked files, dependency manifests, scripts, commands, protected paths, trusted baseline artifacts, and recorded execution evidence.

A simple example: an AI assistant adds FastAPI code to a repository that does not declare FastAPI. SourcePack detects the unsupported dependency and blocks the change before it becomes a review problem.

SourcePack is a local-first public-alpha guardrail. It does not prove code correctness, security, runtime success, semantic validity, dependency safety, external API truth, or user intent.

## Try the demo

```bash
python -m pip install sourcepack
sourcepack demo
```

The demo creates a small local repository, applies an unsupported FastAPI change, and runs SourcePack against it.

Expected output includes:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.

Verdict: FAIL
```

The output has three layers:

- `RED LIGHT` is the human stop signal.
- `Verdict: FAIL` is the formal judgment.
- `unsupported_dependency` is the machine-readable reason code.

## What SourcePack checks

SourcePack focuses on repository assumptions that can be tested locally:

- edits to files that do not exist
- undeclared imports or dependencies
- missing scripts and unsupported commands
- unsupported project ecosystems
- unsafe or protected paths
- malformed or binary diffs
- stale, missing, or corrupt trusted baselines
- policy violations in the proposed change
- bounded local execution evidence

Its judgment is deliberately narrow:

> This proposed change relies on a repository fact that the local evidence does not support.

SourcePack does not reject code merely because AI produced it.

## First five minutes

1. Install SourcePack.

   ```bash
   python -m pip install sourcepack
   ```

2. Run the demo.

   ```bash
   sourcepack demo
   ```

3. Initialize SourcePack in a repository whose current state you have reviewed and want to trust.

   ```bash
   sourcepack init . --auto
   ```

4. Check the current change and open the report.

   ```bash
   sourcepack diff .
   sourcepack report open
   ```

`sourcepack init . --auto` creates or refreshes local SourcePack state only after you decide the current repository state should be trusted. Do not use initialization to bless a failed AI patch.

## What SourcePack catches

| Case | Formal result | Reason code |
| --- | --- | --- |
| Missing or fake file edits | FAIL | `missing_file` |
| New file review | WARN | `new_file` |
| Deleted file review | WARN | `deleted_file` |
| Undeclared imports or dependencies | FAIL | `unsupported_dependency` |
| Same-patch dependency additions | WARN | `declared_dependency` |
| Unsupported commands | FAIL | `unsupported_command` |
| Unsupported ecosystems | WARN | `unsupported_ecosystem` |
| Protected `.sourcepack/` edits | FAIL | `protected_artifact` |
| `.git/` path edits | FAIL | `git_path_modification` |
| Unsafe paths | FAIL | `unsafe_path`, `path_escape` |
| Binary diffs | WARN or FAIL for high-risk paths | `binary_diff` |
| Malformed diffs | FAIL | `malformed_diff` |
| Missing, stale, or corrupt baseline | FAIL or WARN by state and mode | `baseline_missing`, `baseline_stale`, `baseline_corrupt` |
| Workflow automation changes | WARN or FAIL by mode and policy | `workflow_change` |

See [`docs/reason-codes.md`](docs/reason-codes.md) for exact behavior and remediation guidance.

## How the trust model works

SourcePack keeps reviewed repository evidence separate from AI guidance.

- **Baseline:** reviewed local enforcement state
- **Prompt context:** advisory material for an AI assistant
- **Diff:** the actual proposed repository change
- **Judgment:** the result of checking that change against trusted evidence and policy

Prompt context never becomes trust.

SourcePack refuses to create a trusted baseline from a dirty Git working tree unless `--force` is explicitly supplied. In CI, committed `.sourcepack/baseline/` state must be consumed as-is. CI must never create, refresh, repair, or silently bless trusted baseline state.

See [`docs/baseline-lifecycle.md`](docs/baseline-lifecycle.md).

## Verdicts and exit behavior

- PASS exits `0`.
- WARN exits `0` locally.
- WARN exits nonzero with `--strict` or `--ci` by default.
- `--exit-policy fail-only` keeps WARN visible but exits `0` for WARN.
- `--exit-policy warn-or-fail` exits nonzero for WARN and FAIL.
- FAIL exits nonzero under every diff exit policy.

Verdicts are report judgments. Process exit codes are command-boundary policy decisions and do not rewrite the saved JSON or human-readable verdict.

## Common commands

```bash
sourcepack demo
sourcepack init . --auto
sourcepack diff .
sourcepack diff . --json
sourcepack diff . --strict
sourcepack diff . --ci
sourcepack diff . --ci --json
sourcepack diff . --ci --json --exit-policy fail-only
sourcepack report path
sourcepack report open
sourcepack status .
sourcepack doctor
sourcepack doctor --strict
```

Additional workflows:

```bash
sourcepack prompt . "task" --copy
sourcepack baseline .
sourcepack baseline . --refresh
sourcepack replay <report-or-bundle-path>
sourcepack replay <report-or-bundle-path> --json
sourcepack install-hook .
sourcepack uninstall-hook .
sourcepack exec -- pytest
sourcepack evidence list
sourcepack evidence show <entry-id>
sourcepack evidence clear
sourcepack evidence export --json
sourcepack policy validate .
sourcepack policy validate . --json
sourcepack policy resolve .
sourcepack policy resolve . --org-policy ../org-policy.json --json
sourcepack fleet summarize .sourcepack/reports --json
sourcepack fleet summarize <decision-ledger.jsonl> --input-type ledgers --json
```

## Git hooks

`sourcepack init . --auto` installs hooks when possible in a Git repository.

- The pre-commit hook checks staged changes with `sourcepack diff . --staged`.
- The post-commit hook refreshes the baseline only after a clean commit.
- A dirty working tree after commit marks the baseline stale instead of silently trusting it.
- `sourcepack uninstall-hook .` removes the hooks.

## CI and GitHub Actions

Minimal CI usage:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install sourcepack
- run: sourcepack diff . --ci
```

For pull requests, make sure the PR delta is visible before running SourcePack. A clean checkout may already contain the proposed changes as committed files, leaving no workspace delta to inspect.

The bundled composite action consumes an existing committed `.sourcepack/baseline/` directory and fails closed when that baseline is missing.

By default it writes:

- `sourcepack.json`
- `sourcepack.md`
- `sourcepack.stdout.txt`
- `sourcepack.stderr.txt`
- `sourcepack-command.txt`
- `sourcepack-command.json`
- `sourcepack.sarif.json` when SARIF is produced

See [`docs/ci.md`](docs/ci.md) and [`docs/github-action-quickstart.md`](docs/github-action-quickstart.md).

## Local reports

`sourcepack diff .` writes:

- `.sourcepack/reports/latest.html`
- `.sourcepack/reports/latest.json`
- `.sourcepack/reports/latest.md`

Use `sourcepack report path` to print the HTML path and `sourcepack report open` to open it.

HTML is for humans. JSON is for automation. When `sourcepack diff . --json` is used, stdout remains JSON-only.

## Local Workbench

Start the read-only dashboard with:

```bash
sourcepack ui .
```

`sourcepack workbench .` is also supported.

The Workbench binds only to loopback, prints a session-token URL, and makes no external network requests. It has no telemetry, analytics, CDN dependency, cloud account requirement, or write controls.

The dashboard reads canonical SourcePack artifacts. It does not create or repair baselines, generate reports, execute replay, install hooks, edit policy, manage overrides, run commands, browse arbitrary files, or modify Git state.

Current report support is `traffic_report.v1`. Missing artifacts remain unavailable, malformed artifacts produce errors, and unsupported report versions do not silently fall back to older data.

## Evidence bundles

Create and verify a local Evidence Bundle v1:

```bash
sourcepack bundle create .sourcepack/reports/latest.json --ledger .sourcepack/decisions.jsonl
sourcepack bundle verify .sourcepack/reports/latest.bundle.json
sourcepack bundle verify .sourcepack/reports/latest.bundle.json --json
```

An evidence bundle is a JSON manifest that can bind a saved report to related decision-ledger events, linked overrides, scanner-manifest references, parent-chain information, and referenced artifact hashes.

Verification checks local bytes and relationships. It is not a cryptographic signature, tamper-proof archive, semantic proof, or guarantee that every historical event was recorded.

## Replay

```bash
sourcepack replay <report-or-bundle-path>
sourcepack replay <report-or-bundle-path> --json
```

Replay reconstructs a saved SourcePack JSON report or replay bundle. It is read-only and does not rerun judgment against the current checkout.

## Local execution evidence

```bash
sourcepack exec -- <command...>
```

SourcePack records bounded execution evidence under `.sourcepack/evidence/ledger.jsonl`, including command metadata, exit code, stdout and stderr hashes, short excerpts, Git head, dirty-worktree state before and after execution, duration, and a small environment summary.

Full logs are not stored by default. Execution evidence supports only the bounded claim that a command ran locally under the recorded conditions.

Prompt context in `.sourcepack/prompt/` is advisory and cannot satisfy execution evidence.

## Policy

Repository policy lives at `.sourcepack/policy.json` and is validated with:

```bash
sourcepack policy validate .
```

Supported rule areas include:

- dependency additions
- protected paths
- required tests for selected paths
- maximum changed lines
- secret-pattern blocking
- package-manager consistency, currently for `pnpm`

Organization policy can be supplied as explicit local input:

```bash
sourcepack policy resolve . --org-policy ../org-policy.json --json
sourcepack diff . --org-policy ../org-policy.json --org-policy-mode required
```

Policy findings are first-class SourcePack findings and participate in Markdown, HTML, JSON, SARIF, finding identity, override eligibility, and final PASS/WARN/FAIL composition.

The local policy layer is read-only during judgment. It does not mutate policy files, baseline state, overrides, decision ledgers, Git configuration, or the evaluated working tree.

See [`docs/problem-fit.md`](docs/problem-fit.md) and the policy documentation for supported scope and limits.

## Optional hosted control plane

The repository also contains an optional hosted service entry point, `sourcepack-hosted`, for team-oriented control-plane work such as organizations, memberships, repository registration, service identities, role-based authorization, idempotent mutations, and audit retrieval.

Local SourcePack commands do not start the hosted service. The local guardrail remains usable without accounts, telemetry, or a network service.

The hosted layer does not convert remote policy or organizational state into unquestioned local trust. Trust-state boundaries remain explicit.

## What SourcePack is not

SourcePack is not a general AI code reviewer. It does not decide whether code is elegant, scalable, secure, production-ready, architecturally sound, or aligned with business intent.

It does not replace:

- tests
- type checkers
- linters
- security scanners
- dependency review
- runtime validation
- human review

Use SourcePack when the disputed claim can be checked against local repository evidence. It is only a partial fit for broad PR-review burden and is not a fit for questions of taste, architecture, business logic, or management judgment.

## Explicit non-claims

SourcePack does not prove:

- code correctness
- security
- runtime success
- semantic validity
- external API truth
- dependency safety
- user intent
- authenticity of every historical artifact

## Validation and status

SourcePack is in the v1.10 public-alpha series.

Core judgment behavior, packaging, reports, demos, policy resolution, replay, local execution evidence, CI behavior, evidence bundles, and the local Workbench are implemented. Public-alpha work continues around compatibility, packaging, integration coverage, and UX polish.

`sourcepack doctor --strict` checks local production-readiness prerequisites and packaged assets. Hosted GitHub Actions remain the source of truth for hosted checks.

The primary proof unit is a repository-state transition: a known trusted state, a proposed change, the evidence evaluated, and the resulting judgment.

## Public proof links

- [License](LICENSE)
- [Changelog](CHANGELOG.md)
- [Reason codes](docs/reason-codes.md)
- [CI usage](docs/ci.md)
- [GitHub Actions quickstart](docs/github-action-quickstart.md)
- [Problem fit](docs/problem-fit.md)
- [AI-agent workflow](docs/ai-agent-workflow.md)
- [Public-alpha readiness](docs/public-alpha-readiness.md)
- [Baseline lifecycle](docs/baseline-lifecycle.md)
