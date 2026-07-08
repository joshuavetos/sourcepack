# SourcePack

![PyPI](https://img.shields.io/pypi/v/sourcepack)
![Python](https://img.shields.io/pypi/pyversions/sourcepack)
![License](https://img.shields.io/github/license/joshuavetos/sourcepack)
![Status](https://img.shields.io/badge/status-public%20alpha-orange)

SourcePack blocks AI-generated code changes that rely on fake repo facts.

SourcePack catches fake repo facts in AI-generated code changes before they become review facts.

**SourcePack checks proposed diffs against locally verifiable evidence from the actual codebase.**

Concrete first scenario: an AI assistant proposes adding FastAPI code to a repository that does not use FastAPI. SourcePack checks the proposed change against local repo evidence, sees that `fastapi` is not declared, and flags the change as an unsupported dependency before review.

SourcePack is a local public-alpha guardrail for reviewing repo changes. It does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

## Try the demo first

```bash
python -m pip install sourcepack
sourcepack demo
```

The demo creates a small local repo, applies the unsupported FastAPI scenario, and runs SourcePack against that change.

You should see a concrete failure like this:

```text
RED LIGHT: commit blocked
FAIL
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.
```

Read that output as three separate layers:

- Human-facing verdict: `RED LIGHT`
- Formal result: `FAIL`
- Machine reason code: `unsupported_dependency`

In this demo, the proposed code imports `fastapi`, but the repository evidence does not declare FastAPI as a dependency. SourcePack blocks the commit because the AI change relies on an unsupported repo assumption.

## What SourcePack does

AI-generated code can look plausible while relying on facts that are not true in your repository.

SourcePack focuses on locally verifiable repo-assumption failures:

- AI coding agents can edit files that do not exist.
- They can import undeclared dependencies.
- They can reference missing scripts or unsupported commands.
- They can reshape project structure based on prompt assumptions.
- They can touch protected trust or workflow files without making that risk obvious.

- SourcePack catches those locally verifiable failures before commit or in CI.

SourcePack checks those claims against repo evidence before commit or in CI.

It does not say “this code is bad because AI wrote it.”

It says a narrower, testable thing:

> This proposed change relies on a repo fact that the local evidence does not support.

## First five minutes

1. Install SourcePack.

   ```bash
   python -m pip install sourcepack
   ```

2. Run the demo before configuring your own repo.

   ```bash
   sourcepack demo
   ```

3. Understand the failure.

   `RED LIGHT` is the human stop signal.

   `FAIL` is the formal result.

   `unsupported_dependency` is the machine-readable reason code.

4. Initialize SourcePack in a repo whose current state you have reviewed and want to trust.

   ```bash
   sourcepack init . --auto
   sourcepack diff .
   sourcepack report open
   ```

`sourcepack init . --auto` creates or refreshes local SourcePack state after you decide the current repo state should be trusted. Do not use initialization to bless an AI patch just because SourcePack reported a failure.

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
| Missing, stale, or corrupt baseline | FAIL or WARN depending on state and mode | `baseline_missing`, `baseline_stale`, `baseline_corrupt` |
| Workflow automation changes | WARN or FAIL depending on mode and policy | `workflow_change` |

See [`docs/reason-codes.md`](docs/reason-codes.md) for reason-code behavior and fixes.

## What SourcePack is not

SourcePack is not a general AI code reviewer.

It does not judge whether code is elegant, well-designed, scalable, secure, or production-ready. It does not replace tests, type checkers, security scanners, linters, or human review.

SourcePack answers a narrower question:

> Did this proposed change rely on repo facts that are locally verifiable?

## Does SourcePack fit my problem?

Use SourcePack when the question can be checked against local project evidence:

- files
- dependency manifests
- scripts and commands
- protected paths
- diffs
- trusted SourcePack baseline artifacts
- local execution evidence

SourcePack is only a partial fit for broad AI PR review burden, and it is not a fit for judging architecture, taste, runtime quality, business logic, or management decisions.

See [`docs/problem-fit.md`](docs/problem-fit.md) for fit, partial-fit, and not-fit examples.

## What SourcePack does not claim

- does not prove code correctness
- does not prove security
- does not prove runtime success
- does not prove semantic validity
- does not prove external API truth
- does not prove dependency safety
- does not prove user intent

## Public proof links

- [License](LICENSE)
- [Changelog](CHANGELOG.md)
- [Reason codes](docs/reason-codes.md)
- [CI usage](docs/ci.md)
- [GitHub Actions quickstart](docs/github-action-quickstart.md)
- [Problem fit](docs/problem-fit.md)
- [AI-agent workflow](docs/ai-agent-workflow.md)
- [Public-alpha readiness](docs/public-alpha-readiness.md)

## How SourcePack works

SourcePack keeps trusted repo evidence separate from AI guidance.

- Baseline = reviewed local enforcement state.
- Prompt context = AI guidance only.
- Prompt context never becomes trust.
- `sourcepack diff` checks actual repo changes against the baseline.

Create or refresh the trusted baseline only after reviewing that the current repo state should be trusted.

SourcePack refuses to create a trusted baseline from a dirty Git working tree unless you pass `--force`.

For baseline lifecycle details, see [`docs/baseline-lifecycle.md`](docs/baseline-lifecycle.md).

CI should consume committed `.sourcepack/baseline/` state and must not create, refresh, repair, or bless trusted baseline state automatically.

## Local policy

- PASS exits `0`.
- WARN exits `0` locally.
- WARN exits nonzero with `--strict` or `--ci`.
- FAIL exits nonzero.

## Common commands

```bash
sourcepack demo
sourcepack init . --auto
sourcepack diff .
sourcepack diff . --json
sourcepack diff . --strict
sourcepack diff . --ci
sourcepack diff . --ci --json
sourcepack report path
sourcepack report open
sourcepack status .
sourcepack doctor
sourcepack doctor --strict
```

More commands exist for prompt generation, baseline maintenance, report replay, hooks, local execution evidence, and policy validation:

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
```

## Git hooks

`sourcepack init . --auto` installs hooks when possible in a Git repository.

- The pre-commit hook checks staged changes with `sourcepack diff . --staged`.
- The post-commit hook refreshes the baseline only after clean commits.
- If the working tree is dirty after a commit, SourcePack marks the baseline stale instead of silently trusting it.
- To uninstall hooks, run `sourcepack uninstall-hook .`.

## CI quickstart

Safe CI usage for projects that intentionally manage a trusted baseline:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install sourcepack
- run: sourcepack diff . --ci
```

For pull-request CI, make sure the PR delta is visible before running `sourcepack diff . --ci`.

A clean PR checkout may already contain the proposed changes as committed files, leaving no local workspace delta for SourcePack to inspect.

For a complete copy-paste workflow, see [`docs/github-action-quickstart.md`](docs/github-action-quickstart.md).

CI must consume committed baseline state and must not create, refresh, repair, or bless trusted baseline state.

## GitHub Action

The bundled composite action can run SourcePack in CI while preserving the trust-state boundary.

It consumes an existing committed `.sourcepack/baseline/` directory and fails closed when that baseline is missing.

The action writes report artifacts under `sourcepack-report/` by default:

- `sourcepack.json`
- `sourcepack.md`
- `sourcepack.stdout.txt`
- `sourcepack.stderr.txt`
- `sourcepack-command.txt`
- `sourcepack-command.json`
- `sourcepack.sarif.json` when SARIF is produced

`sourcepack-command.txt` is human-readable. `sourcepack-command.json` records structured command arguments for downstream tooling.

See [`docs/ci.md`](docs/ci.md) and [`docs/github-action-quickstart.md`](docs/github-action-quickstart.md) before enabling the action on pull requests.

## Local reports

`sourcepack diff .` writes local report artifacts under `.sourcepack/reports/`:

- `.sourcepack/reports/latest.html`
- `.sourcepack/reports/latest.json`
- `.sourcepack/reports/latest.md`

Use `sourcepack report path` to print the HTML report path and `sourcepack report open` to open it.

HTML is for humans. JSON is for automation and remains JSON-only on stdout when `sourcepack diff . --json` is used.

## Replay saved reports

```bash
sourcepack replay <report-or-bundle-path>
sourcepack replay <report-or-bundle-path> --json
```

Replay reconstructs a saved SourcePack JSON report or replay bundle.

Replay is read-only, does not rerun judgment against the current checkout, and does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

## Local execution evidence

`sourcepack exec -- <command...>` runs a local command and records bounded evidence under `.sourcepack/evidence/ledger.jsonl`.

Ledger entries store command metadata, exit code, stdout/stderr SHA-256 hashes, short excerpts, git head, dirty-worktree state before and after execution, duration, and a small environment summary.

They do not store full logs by default and are local-only.

Execution evidence only supports bounded claims that a command was run locally. It does not prove code correctness, security, runtime success, semantic validity, external API truth, dependency safety, or user intent.

Prompt context in `.sourcepack/prompt/` remains advisory and cannot satisfy execution evidence.

## Validation

Validation is local and deterministic.

`sourcepack doctor --strict` checks production-readiness prerequisites and packaged assets. Hosted GitHub Actions remains the source of truth for hosted checks.

The primary proof unit is a repo-state transition, not a random repository.

## Screenshot assets

Screenshot assets are optional and should only be shown inline after the image files actually exist in the repository.

Expected future asset targets are expected screenshot targets:

- `docs/assets/sourcepack-terminal-red.png` — terminal output from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-red-report.png` — HTML report from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-warn-report.png` — HTML report from `warn-new-file`.
- `docs/assets/sourcepack-pass-report.png` — HTML report from `pass-clean`.

See [`docs/assets/README.md`](docs/assets/README.md) for exact capture instructions.

## Status

v1.10 alpha series: local-first public alpha.

Core judgment behavior is validated. Packaging, reports, demos, CI behavior, and UX polish are active areas.
