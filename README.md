# SourcePack

SourcePack catches unsupported AI repository assumptions before commit by checking proposed changes against locally verifiable project evidence.

**SourcePack blocks AI-generated code changes that rely on fake repo facts.**

Concrete first scenario: an AI assistant proposes adding FastAPI code to a repository that does not use FastAPI. SourcePack checks the proposed change against local repo evidence, sees that `fastapi` is not declared, and flags the change as an unsupported dependency before review.

SourcePack is a local public-alpha guardrail for reviewing repo changes. It does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

SourcePack still targets the same narrow problem:

- AI coding agents can edit files that do not exist.
- They can import undeclared dependencies.
- They can reference missing scripts or unsupported commands.
- They can reshape project structure based on prompt assumptions.
- SourcePack catches those locally verifiable failures before commit or in CI.

## Try the demo first

```bash
python -m pip install sourcepack
sourcepack demo
```

The demo creates a small local repo, applies the unsupported FastAPI scenario, and runs SourcePack against that change.

### What you should see

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

## First five minutes

1. Install SourcePack.

   ```bash
   python -m pip install sourcepack
   ```

2. Run the demo before configuring your own repo.

   ```bash
   sourcepack demo
   ```

3. Understand the failure: `RED LIGHT` is the human stop signal, `FAIL` is the formal result, and `unsupported_dependency` is the machine-readable reason code.

4. Then initialize SourcePack in a repo whose current state you have reviewed and want to trust.

   ```bash
   sourcepack init . --auto
   sourcepack diff .
   sourcepack report open
   ```

`sourcepack init . --auto` creates or refreshes local SourcePack state after you decide the current repo state should be trusted. Do not use initialization to bless an AI patch just because SourcePack reported a failure.

## What SourcePack catches

SourcePack focuses on locally verifiable AI repo-assumption failures:

| Case | Formal result | Reason code |
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

## Does SourcePack fit my problem?

Use SourcePack when the question can be checked against local project evidence: files, dependency manifests, commands, protected paths, diffs, and trusted SourcePack artifacts. It is only a partial fit for broad AI PR review burden, and it is not a fit for judging architecture, taste, runtime quality, or management decisions.

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

## How SourcePack works, briefly

SourcePack keeps trusted repo evidence separate from AI guidance:

- Baseline = reviewed local enforcement state.
- Prompt context = AI guidance only.
- Prompt context never becomes trust.
- `sourcepack diff` checks actual repo changes against the baseline.

Create or refresh the trusted baseline only after reviewing that the current repo state should be trusted. SourcePack refuses to create a trusted baseline from a dirty Git working tree unless you pass `--force`.

For baseline lifecycle details, see [`docs/baseline-lifecycle.md`](docs/baseline-lifecycle.md). CI should consume committed `.sourcepack/baseline/` state and must not create or refresh trusted baseline state automatically; SourcePack dogfoods this with `sourcepack diff . --ci --json` against committed `.sourcepack/baseline/` state.

## Local policy

- PASS exits `0`.
- WARN exits `0` locally.
- WARN exits nonzero with `--strict` or `--ci`.
- FAIL exits nonzero.

## Git hooks

`sourcepack init . --auto` installs hooks when possible in a Git repository.

- The pre-commit hook checks staged changes with `sourcepack diff . --staged`.
- The post-commit hook refreshes the baseline only after clean commits.
- If the working tree is dirty after a commit, SourcePack marks the baseline stale instead of silently trusting it.
- To uninstall hooks, run `sourcepack uninstall-hook .`.

## Replay saved reports

```bash
sourcepack replay <report-or-bundle-path>
sourcepack replay <report-or-bundle-path> --json
```

Replay reconstructs a saved SourcePack JSON report or replay bundle. Replay is read-only, does not rerun judgment against the current checkout, and does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

## Validation

Validation is local and deterministic. `sourcepack doctor --strict` checks production-readiness prerequisites and packaged assets; hosted GitHub Actions remains the source of truth for hosted checks. The primary proof unit is a repo-state transition, not a random repository.

## Common commands

```bash
sourcepack demo
sourcepack init . --auto
sourcepack diff .
sourcepack diff . --json
sourcepack diff . --strict
sourcepack diff . --ci
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

## CI quickstart

Safe CI usage for projects that intentionally manage a trusted baseline:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install sourcepack
- run: sourcepack diff . --ci
```

For a complete copy-paste workflow, see [`docs/github-action-quickstart.md`](docs/github-action-quickstart.md). CI must consume committed baseline state and must not create or refresh trusted baseline state.

## Local reports

`sourcepack diff .` writes local report artifacts under `.sourcepack/reports/`:

- `.sourcepack/reports/latest.html`
- `.sourcepack/reports/latest.json`
- `.sourcepack/reports/latest.md`

Use `sourcepack report path` to print the HTML report path and `sourcepack report open` to open it. HTML is for humans. JSON is for automation and remains JSON-only on stdout when `sourcepack diff . --json` is used.

## Local execution evidence

`sourcepack exec -- <command...>` runs a local command and records bounded evidence under `.sourcepack/evidence/ledger.jsonl`. Ledger entries store command metadata, exit code, stdout/stderr SHA-256 hashes, short excerpts, git head, dirty-worktree state before and after execution, duration, and a small environment summary. They do not store full logs by default and are local-only.

Execution evidence only supports bounded claims that a command was run locally. It does not prove code correctness, security, runtime success, semantic validity, external API truth, dependency safety, or user intent. Prompt context in `.sourcepack/prompt/` remains advisory and cannot satisfy execution evidence.

## Product screenshot section

Screenshot assets are generated from deterministic golden demo outputs and should be committed at these paths when refreshed:

- `docs/assets/sourcepack-terminal-red.png` — terminal output from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-red-report.png` — HTML report from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-warn-report.png` — HTML report from `warn-new-file`.
- `docs/assets/sourcepack-pass-report.png` — HTML report from `pass-clean`.

See [`docs/assets/README.md`](docs/assets/README.md) for exact capture instructions. If these image files are absent, the paths above are expected screenshot targets, not claimed live screenshots.

## Status

v1.10.0-alpha: local-first alpha. Core judgment behavior is validated. Packaging, reports, demos, and UX polish are active areas.
