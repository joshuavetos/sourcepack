# SourcePack

SourcePack blocks AI-generated code changes that rely on fake repo facts.

- AI coding agents can edit files that do not exist.
- They can import undeclared dependencies.
- They can reference missing scripts or unsupported commands.
- They can reshape project structure based on prompt assumptions.
- SourcePack catches those locally verifiable failures before commit or in CI.

SourcePack checks proposed changes against locally verifiable repo evidence. It is a local public-alpha guardrail for reviewing repo changes, not a proof system.

## The problem

AI coding agents can confidently edit files that are not in the repo, import dependencies that are not declared, reference commands that do not exist, or reshape project structure without local evidence. Those failures are review noise at best and dangerous trust-laundering at worst.

SourcePack keeps trusted repo evidence separate from AI guidance. The trusted baseline is local enforcement state; prompt context is advisory only.

## 30-second demo

```bash
python -m pip install sourcepack
sourcepack demo
```

Expected demo result:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.
```

## What RED LIGHT means

RED LIGHT means SourcePack found a local evidence problem that blocks the commit. In the demo, the patch imports `fastapi`, but the repo evidence does not declare `fastapi` as a dependency, so SourcePack reports `unsupported_dependency`.

Fix the unsupported assumption, add the missing repo evidence intentionally, or reject the patch. Do not refresh trusted baseline state merely to silence a warning or failure.

## Use it in your repo

Create or refresh the trusted baseline only after reviewing that the current repo state should be trusted. SourcePack refuses to create a trusted baseline from a dirty Git working tree unless you pass `--force`.

```bash
sourcepack init . --auto
sourcepack diff .
sourcepack report open
```

## Does SourcePack fit my problem?

Use SourcePack for locally verifiable AI repo-assumption failures: fake files, undeclared dependencies, unsupported commands, unsafe paths, malformed diffs, protected trust-artifact edits, and baseline problems. It is only a partial fit for broad AI PR review burden, and it is not a fit for judging architecture, taste, runtime quality, or management decisions.

See [`docs/problem-fit.md`](docs/problem-fit.md) for fit, partial-fit, and not-fit examples.

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

## Limits

SourcePack does not prove code correctness, security, runtime success, semantic validity, external API truth, dependency safety, or user intent. It also does not replace tests, require cloud access, or upload repo contents.

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

## CI quickstart

Safe CI usage for projects that intentionally manage a trusted baseline:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install sourcepack
- run: sourcepack diff . --ci
```

For a complete copy-paste workflow, see [`docs/github-action-quickstart.md`](docs/github-action-quickstart.md). CI must consume committed baseline state and must not create or refresh trusted baseline state.

## AI-agent workflow guidance

For AI-agent contribution guidance, use the concise post-change gate workflow in [`docs/ai-agent-workflow.md`](docs/ai-agent-workflow.md).

## Public-alpha readiness

Public-alpha readiness is tracked in [`docs/public-alpha-readiness.md`](docs/public-alpha-readiness.md). SourcePack is a local evidence guardrail; it does not prove code correctness, security, dependency safety, runtime success, semantic validity, external API truth, or user intent.

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
sourcepack replay <report-or-bundle-path>
sourcepack replay <report-or-bundle-path> --json
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

## Replay saved reports

Use `sourcepack replay <report-or-bundle-path>` to reconstruct a saved SourcePack JSON report or replay bundle. Use `sourcepack replay <report-or-bundle-path> --json` for parseable JSON output. Replay is read-only, does not rerun judgment over the current checkout, and does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

## Git hooks

`sourcepack init . --auto` installs hooks when possible in a Git repository.

- The pre-commit hook checks staged changes with `sourcepack diff . --staged`.
- The post-commit hook refreshes the baseline only after clean commits.
- If the working tree is dirty after a commit, SourcePack marks the baseline stale instead of silently trusting it.
- To uninstall hooks, run `sourcepack uninstall-hook .`.

## Product screenshot section

Screenshot assets are generated from deterministic golden demo outputs and should be committed at these paths when refreshed:

- `docs/assets/sourcepack-terminal-red.png` — terminal output from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-red-report.png` — HTML report from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-warn-report.png` — HTML report from `warn-new-file`.
- `docs/assets/sourcepack-pass-report.png` — HTML report from `pass-clean`.

See [`docs/assets/README.md`](docs/assets/README.md) for exact capture instructions. If these image files are absent, the paths above are expected screenshot targets, not claimed live screenshots.

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

## Composite GitHub Action

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
