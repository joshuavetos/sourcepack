# SourcePack

SourcePack catches unsupported AI repository assumptions before commit by checking proposed changes against locally verifiable repo evidence. It is a local public-alpha guardrail for reviewing repo changes, not a proof system.

## Install

```bash
python -m pip install sourcepack
```

## Demo

```bash
sourcepack demo
```

Expected demo result:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.
```

## Use it in your repo

Create or refresh the trusted baseline only after reviewing that the current repo state should be trusted. SourcePack refuses to create a trusted baseline from a dirty Git working tree unless you pass `--force`.

```bash
sourcepack init . --auto
sourcepack diff .
sourcepack report open
```

## Limits

SourcePack does not prove code correctness, security, runtime success, semantic validity, external API truth, dependency safety, or user intent. It also does not replace tests, require cloud access, or upload repo contents.

## Public proof links

- [License](LICENSE)
- [Changelog](CHANGELOG.md)
- [Reason codes](docs/reason-codes.md)
- [CI usage](docs/ci.md)

## Local policy

- PASS exits `0`.
- WARN exits `0` locally.
- WARN exits nonzero with `--strict` or `--ci`.
- FAIL exits nonzero.
- `sourcepack policy validate [repo] [--json]` validates optional `.sourcepack/policy.json` without creating or updating baseline, prompt, report, evidence, hook, or working-tree files. Missing policy files exit `0`; invalid JSON or a non-object root exits nonzero. Reserved fields and dangerous trust overrides are warnings only and do not make prompt context authoritative or make CI baseline checks optional.

## Local development install

```bash
python -m pip install -e .
```

## Product screenshot section

Screenshot assets are generated from deterministic golden demo outputs and should be committed at these paths when refreshed:

- `docs/assets/sourcepack-terminal-red.png` — terminal output from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-red-report.png` — HTML report from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-warn-report.png` — HTML report from `warn-new-file`.
- `docs/assets/sourcepack-pass-report.png` — HTML report from `pass-clean`.

See [`docs/assets/README.md`](docs/assets/README.md) for exact capture instructions. If these image files are absent, the paths above are expected screenshot targets, not claimed live screenshots.

## How SourcePack works

SourcePack keeps trusted repo evidence separate from AI guidance:

- Baseline = the last trusted repo state.
- Prompt context = AI guidance only.
- Prompt context never becomes trust.
- `sourcepack diff` checks actual repo changes against the baseline.

Without baseline/prompt separation:

- AI prompt context says `deploy.sh` exists and uses port `8080`.
- That claim gets treated as trusted evidence.
- AI edits against a fake deploy script.
- The guardrail launders an AI claim into repo truth.

With SourcePack:

- Prompt context is only guidance.
- `.sourcepack/baseline/` is enforcement trust.
- If `deploy.sh` is not in the trusted baseline, the edit fails.
- AI-generated context cannot bless its own assumptions.


## Baseline lifecycle

SourcePack enforcement depends on a reviewed `.sourcepack/baseline/`, while `.sourcepack/prompt/` remains AI guidance only. CI should consume committed baseline state and must not create or update trusted baseline state automatically. See [`docs/baseline-lifecycle.md`](docs/baseline-lifecycle.md) for safe local and PR flows. SourcePack now dogfoods this model: its own CI runs `sourcepack diff . --ci --json` against committed `.sourcepack/baseline/` state, and AI-assisted PRs should report that gate verdict, reason codes, and report path.

## AI-agent workflow guidance

For AI-agent contribution guidance, use the concise post-change gate workflow in [`docs/ai-agent-workflow.md`](docs/ai-agent-workflow.md).

## Public-alpha readiness

Public-alpha readiness is tracked in [`docs/public-alpha-readiness.md`](docs/public-alpha-readiness.md). SourcePack is a local evidence guardrail; it does not prove code correctness, security, dependency safety, runtime success, semantic validity, external API truth, or user intent.

## What SourcePack catches

| Case | Local result | Reason code |
| --- | --- | --- |
| Missing/fake file edits | FAIL | `missing_file` |
| New file review | WARN | `new_file` |
| Deleted file review | WARN | `deleted_file` |
| Undeclared imports/dependencies | FAIL | `unsupported_dependency` |
| Same-patch dependency additions | WARN | `declared_dependency` |
| Unsupported commands | FAIL | `unsupported_command` |
| Unsupported ecosystems | WARN | `unsupported_ecosystem` |
| Protected `.sourcepack/` edits | FAIL | `protected_artifact` |
| `.git/` path edits | FAIL | `git_path_modification` |
| Unsafe paths | FAIL | `unsafe_path` |
| Binary diffs | WARN or FAIL for high-risk paths | `binary_diff` |
| Malformed diffs | FAIL | `malformed_diff` |
| Missing/stale/corrupt baseline | FAIL or WARN depending on state and mode | `baseline_missing`, `baseline_stale`, `baseline_corrupt` |

See [`docs/reason-codes.md`](docs/reason-codes.md) for reason-code behavior and fixes.

## What SourcePack does not claim

- Does not prove code correctness.
- Does not prove security.
- Does not replace tests.
- Does not understand full program semantics.
- Does not require cloud access.
- Does not upload repo contents.

## Commands

Documented user-facing commands that exist in the current CLI:

```bash
sourcepack init . --auto
sourcepack diff .
sourcepack diff . --json
sourcepack diff . --strict
sourcepack diff . --ci
sourcepack prompt . "task" --copy
sourcepack baseline .
sourcepack baseline . --refresh
sourcepack report path
sourcepack report open
sourcepack status .
sourcepack exec -- pytest
sourcepack evidence list
sourcepack evidence show <entry-id>
sourcepack evidence clear
sourcepack doctor
sourcepack doctor --strict
sourcepack demo
```

Hook management commands also exist for explicit maintenance:

```bash
sourcepack install-hook .
sourcepack uninstall-hook .
```

## Local execution evidence

`sourcepack exec -- <command...>` runs a local command and records bounded evidence under `.sourcepack/evidence/ledger.jsonl`. Ledger entries store command metadata, exit code, stdout/stderr SHA-256 hashes, short excerpts, git head, dirty-worktree state before and after execution, duration, and a small environment summary. They do not store full logs by default and are local-only. Command output can still contain sensitive information, so review `.sourcepack/evidence/` before sharing it.

Use:

```bash
sourcepack exec -- pytest
sourcepack evidence list
sourcepack evidence show <entry-id>
sourcepack evidence clear
sourcepack evidence export --json
```

Execution evidence only supports bounded claims that a command was run locally. It does not prove code correctness, security, or external API behavior. Prompt context in `.sourcepack/prompt/` remains advisory and cannot satisfy execution evidence.

## Local reports

`sourcepack diff .` writes local report artifacts under `.sourcepack/reports/`:

- `.sourcepack/reports/latest.html`
- `.sourcepack/reports/latest.json`
- `.sourcepack/reports/latest.md`

Use:

```bash
sourcepack report path
sourcepack report open
```

HTML is for humans. JSON is for automation and remains JSON-only on stdout when `sourcepack diff . --json` is used.

## Git hooks

`sourcepack init . --auto` installs hooks when possible in a Git repository.

- The pre-commit hook checks staged changes with `sourcepack diff . --staged`.
- The post-commit hook refreshes the baseline only after clean commits.
- If the working tree is dirty after a commit, SourcePack marks the baseline stale instead of silently trusting it.
- To uninstall hooks, run `sourcepack uninstall-hook .`.

## CI

The included GitHub Actions workflow installs SourcePack in editable mode, runs unit and pytest gates, runs the behavior matrix, and checks `sourcepack doctor` plus `sourcepack demo`.

Safe CI usage for projects that intentionally manage a trusted baseline:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install -e .
- run: sourcepack diff . --ci
```

`sourcepack diff . --ci` implies strict JSON output and exits nonzero for WARN or FAIL. CI must not establish trust automatically: if no trusted baseline exists, CI fails until a baseline strategy is intentionally created outside CI.

## Validation

Current validation is local and deterministic. `sourcepack doctor --strict` performs a production-readiness health check and fails on missing runtime prerequisites or packaged assets:

- Hosted GitHub Actions workflow is the source of truth for hosted checks.
- The behavior matrix covers canonical repo-state transitions.
- The simulation harness validates local workflow transitions.
- Gauntlet and smoke tests cover CLI and report behavior.
- The optional real-corpus harness is available in `tools/real_corpus_validation.py` for caller-provided repositories.

The primary proof unit is a repo-state transition, not a random repository.

## Status

v1.10.0-alpha: local-first alpha. Core judgment behavior is validated. Packaging, reports, demos, and UX polish are active areas.

## Public-alpha checklist

Before public alpha, verify:

- Install works from a clean environment.
- `sourcepack --version` works.
- `sourcepack doctor` works.
- `sourcepack demo` works.
- `sourcepack init . --auto` works.
- `sourcepack diff .` works.
- `sourcepack report open` or `sourcepack report path` works.
- Behavior matrix passes.
- Golden demos pass.
- Known limitations are documented.
- PyPI publication metadata should match public install documentation.


## CI and editor planning

See `docs/ci.md` for CI usage and `docs/vscode-extension-plan.md` for the VS Code extension plan.

## GitHub Action

SourcePack includes a composite GitHub Action that runs the existing `sourcepack` CLI in CI. It packages the CLI behavior; it does not create a second implementation of SourcePack judgment logic.

Minimal workflow:

```yaml
name: SourcePack

on:
  pull_request:

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./
        with:
          mode: ci
          # fail-on-warn: 'true'
```

Baseline trust rule: CI consumes `.sourcepack/baseline/`. CI does not create, refresh, bless, or update trusted baseline state automatically. If the baseline is missing, the Action fails closed with `SourcePack baseline not found` and explains that CI will not create or update trusted baseline state automatically. Maintainers should create or refresh baselines locally or in a separate trusted maintainer-controlled setup workflow before relying on PR checks.

The Action writes report artifacts to `sourcepack-report` by default, including `sourcepack.json`, `sourcepack.md`, `sourcepack.stderr.txt`, `sourcepack.stdout.txt`, and `sourcepack-command.txt` when available. `RED`/`FAIL` exits nonzero. `WARN` follows the selected CLI mode: `ci` and `strict` fail on WARN, while `local` does not unless `fail-on-warn: 'true'` is set.

Before pushing, run SourcePack locally with:

```bash
sourcepack --version
sourcepack doctor
sourcepack diff . --json
```

Current limitations: PR commenting is future work and is not implemented by this Action. Unsupported ecosystems remain YELLOW/WARN unless SourcePack core supports them.

### Replay saved reports

Use `sourcepack replay <report-or-bundle-path>` to reconstruct a saved SourcePack JSON report or replay bundle. Add `--json` for a single parseable JSON object on stdout. Replay JSON output uses `schema_version: "sourcepack.replay.v1"` and preserves the input report or bundle schema separately as `input_schema_version`. Replay is read-only: it does not rerun `sourcepack diff`, does not inspect the current working tree for new findings, and does not require `.sourcepack/baseline/`, `.sourcepack/prompt/`, or Git. It reconstructs saved local-evidence report content and does not prove correctness, security, runtime success, external API truth, or user intent.
