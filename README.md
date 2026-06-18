<img width="1800" height="620" alt="sourcepack-hero" src="https://github.com/user-attachments/assets/9b4af0df-1cfc-4aa8-8eb1-f673e6eb2e52" />

AI coding tools can edit files, add imports, invent commands, or assume project structure that is not actually present. SourcePack checks AI-generated repo changes against trusted local repo evidence before commit.

## Badges

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Package: local editable](https://img.shields.io/badge/package-local%20editable-blue)

## Quick demo

A small RED case: an AI change imports `fastapi`, but the repository does not declare `fastapi` in its dependency files.

```bash
$ sourcepack init . --auto
$ printf 'from fastapi import FastAPI\n' > app.py
$ git add app.py
$ git commit -m "add API"
RED LIGHT: commit blocked
unsupported_dependency: app.py imports fastapi, but fastapi is not declared.

Fix:
- add fastapi intentionally to pyproject.toml
- or remove the import
- run sourcepack report open for details
```

Then inspect the human report:

```bash
sourcepack report open
```

## Product screenshot section

Screenshot assets are generated from deterministic golden demo outputs and should be committed at these paths when refreshed:

- `docs/assets/sourcepack-terminal-red.png` — terminal output from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-red-report.png` — HTML report from `fail-unsupported-dependency`.
- `docs/assets/sourcepack-warn-report.png` — HTML report from `warn-new-file`.
- `docs/assets/sourcepack-pass-report.png` — HTML report from `pass-clean`.

See [`docs/assets/README.md`](docs/assets/README.md) for exact capture instructions. If these image files are absent, the paths above are expected screenshot targets, not claimed live screenshots.

## Install

Current local editable install:

```bash
python -m pip install -e .
```

SourcePack is not documented here as a published PyPI package. Planned package install commands such as `pipx install sourcepack`, `uv tool install sourcepack`, or `pip install sourcepack` should only be advertised after publication is true from release metadata.

## Quick start

```bash
sourcepack init . --auto
# make or receive AI changes
sourcepack diff .
sourcepack report open
# if accepted, continue with normal git commit
git commit -m "your change"
```

Local policy:

- PASS exits `0`.
- WARN exits `0` locally.
- WARN exits nonzero with `--strict` or `--ci`.
- FAIL exits nonzero.

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

Current validation is local and deterministic:

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
- Do not claim PyPI publication unless SourcePack is actually published there.


## CI and editor planning

See `docs/ci.md` for CI usage and `docs/vscode-extension-plan.md` for the VS Code extension plan.
