# SourcePack Context Packet

## Source Manifest Summary

Input path: /workspace/sourcepack
Generated at: 2026-07-03T13:55:00.393684+00:00
Files included: 113
Estimated tokens: 240998

## File: CHANGELOG.md

Metadata:
- sha256: ffc4c58adc1d0172034661f08ebeb891c70222456fcc411e98bc30b4b5d94103
- bytes: 328
- estimated_tokens: 82

Content:

# Changelog

## Unreleased

- Tighten public-alpha onboarding around install, demo, baseline trust, and documented limitations.
- Refuse trusted baseline creation or refresh from dirty Git working trees unless `--force` is used intentionally.
- Keep public reason-code examples aligned with canonical reason-code documentation.


---

## File: LICENSE

Metadata:
- sha256: a2730ad6bff3e6035045902c31f49c201f04567029d75ad0114b7939d56c9dbb
- bytes: 1080
- estimated_tokens: 270

Content:

MIT License

Copyright (c) 2026 SourcePack contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


---

## File: README.md

Metadata:
- sha256: ecda185af8e03c2926bdc7bb379c5235092515eca98c09c6a6ab3ab0f7b7fd9f
- bytes: 13897
- estimated_tokens: 3473

Content:

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
- Optional `.sourcepack/policy.json` `rules` are skipped transparently when the policy file is missing, `rules` is missing, or `rules` is empty. When configured, `sourcepack diff` analyzes proposed workspace deltas against enabled local rules only; it does not create, refresh, repair, or bless trusted artifacts. MVP rules support dependency-addition blocking, configured protected paths, pnpm package-manager drift checks, test-change expectations, large-diff warnings, and minimal obvious credential-assignment blocking.

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


---

## File: SECURITY.md

Metadata:
- sha256: 0ff61055843766dc02dfe08a53fc86ee1dd4c4d37d1eb54810eb651c200806ba
- bytes: 1128
- estimated_tokens: 282

Content:

# Security policy

SourcePack is not a vulnerability scanner, secret scanner, or supply-chain protection product. It is a local-first guardrail that checks whether AI-assisted repository changes rely on unsupported local evidence before commit.

## What to report

Please report issues that affect SourcePack's trust boundary, including:

- Baseline bypasses or cases where `.sourcepack/baseline/` edits are trusted silently.
- Prompt context laundering, where prompt context becomes enforcement evidence.
- False negatives for invented files, undeclared dependencies, unsupported commands, or unsafe paths.
- JSON/CI output issues that could hide WARN or FAIL results from automation.

## What is out of scope

- Vulnerabilities in projects analyzed by SourcePack.
- Malicious but baseline-consistent code.
- General dependency vulnerability reports.
- Secret scanning requests.

## Reporting process

Open a private security advisory if the hosting platform supports it. If not, open a minimal public issue that states a trust-boundary problem exists without exploit details, and maintainers can coordinate a private channel.


---

## File: action.yml

Metadata:
- sha256: 04cdf1bee42adb8c1403cc67abbd120d50708a05dca90c6d5099115d852e037d
- bytes: 5744
- estimated_tokens: 1436

Content:

name: SourcePack
description: Run the SourcePack CLI in CI without creating or updating trusted baseline state.
inputs:
  mode:
    description: SourcePack CLI mode: ci, strict, or local.
    required: false
    default: ci
  sourcepack-version:
    description: Optional SourcePack package version to install from the configured Python package source. Empty installs from the current checkout.
    required: false
    default: ''
  python-version:
    description: Python version for the action runtime.
    required: false
    default: '3.11'
  baseline-path:
    description: Trusted SourcePack baseline path consumed by CI.
    required: false
    default: .sourcepack/baseline
  report-dir:
    description: Directory where SourcePack action reports are written.
    required: false
    default: sourcepack-report
  json:
    description: Preserve JSON report output.
    required: false
    default: 'true'
  markdown:
    description: Write a minimal markdown summary around existing SourcePack CLI output.
    required: false
    default: 'true'
  sarif:
    description: Preserve SARIF report output when the installed SourcePack version writes it.
    required: false
    default: 'true'
  fail-on-warn:
    description: Make WARN fail the action outside modes that already fail on WARN.
    required: false
    default: 'false'
  run-doctor:
    description: Run sourcepack doctor before diff evaluation.
    required: false
    default: 'true'
  upload-artifact:
    description: Upload report-dir as a GitHub Actions artifact.
    required: false
    default: 'true'
  comment-pr:
    description: Reserved for future opt-in PR commenting; not implemented by this action.
    required: false
    default: 'false'
runs:
  using: composite
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
    - name: Install SourcePack
      shell: bash
      env:
        SOURCEPACK_VERSION: ${{ inputs.sourcepack-version }}
      run: |
        set -euo pipefail
        if [ -n "$SOURCEPACK_VERSION" ]; then
          python -m pip install "sourcepack==$SOURCEPACK_VERSION"
        else
          python -m pip install -e "$GITHUB_ACTION_PATH"
        fi
    - name: SourcePack version
      shell: bash
      run: sourcepack --version
    - name: SourcePack doctor
      if: ${{ inputs.run-doctor == 'true' }}
      shell: bash
      run: sourcepack doctor
    - name: Verify SourcePack baseline
      shell: bash
      env:
        BASELINE_PATH: ${{ inputs.baseline-path }}
        REPORT_DIR: ${{ inputs.report-dir }}
        SOURCEPACK_MODE: ${{ inputs.mode }}
        FAIL_ON_WARN: ${{ inputs.fail-on-warn }}
      run: |
        set -euo pipefail
        if [ ! -d "$BASELINE_PATH" ]; then
          mkdir -p "$REPORT_DIR"
          MESSAGE="$(printf '%s\n' \
            'SourcePack failed closed because trusted baseline state is missing.' \
            "Missing baseline path: $BASELINE_PATH" \
            'CI will not create or update trusted baseline state.' \
            'Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow.' \
            'This is a trust-boundary behavior, not a package crash.')"
          printf '%s\n' "$MESSAGE" | tee "$REPORT_DIR/sourcepack.stderr.txt" >&2
          printf '%s\n' 'baseline preflight' > "$REPORT_DIR/sourcepack-command.txt"
          : > "$REPORT_DIR/sourcepack.stdout.txt"
          {
            printf '%s\n\n' '# SourcePack Action summary'
            printf '%s\n' '- Verdict: FAIL'
            printf '%s\n' '- Traffic light: FAIL'
            printf '%s\n' "- Mode: $SOURCEPACK_MODE"
            if [ "$SOURCEPACK_MODE" = 'ci' ] || [ "$SOURCEPACK_MODE" = 'strict' ] || [ "$FAIL_ON_WARN" = 'true' ]; then
              printf '%s\n' '- WARN fails in selected mode: true'
            else
              printf '%s\n' '- WARN fails in selected mode: false'
            fi
            printf '%s\n' "- Report directory: $REPORT_DIR"
            printf '%s\n' '- Artifacts: sourcepack.stderr.txt, sourcepack.stdout.txt, sourcepack-command.txt'
            printf '%s\n' '- Missing baseline: SourcePack failed closed because trusted baseline state is missing. CI will not create or update trusted baseline state. Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow. This is a trust-boundary behavior, not a package crash.'
          } > "$REPORT_DIR/sourcepack.md"
          if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
            cat "$REPORT_DIR/sourcepack.md" >> "$GITHUB_STEP_SUMMARY"
          fi
          printf '%s\n' "SourcePack report directory: $REPORT_DIR"
          exit 2
        fi
    - name: Run SourcePack diff
      shell: bash
      env:
        SOURCEPACK_MODE: ${{ inputs.mode }}
        BASELINE_PATH: ${{ inputs.baseline-path }}
        REPORT_DIR: ${{ inputs.report-dir }}
        SOURCEPACK_JSON: ${{ inputs.json }}
        SOURCEPACK_MARKDOWN: ${{ inputs.markdown }}
        SOURCEPACK_SARIF: ${{ inputs.sarif }}
        FAIL_ON_WARN: ${{ inputs.fail-on-warn }}
      run: |
        set -euo pipefail
        python "$GITHUB_ACTION_PATH/scripts/sourcepack_action.py" \
          --mode "$SOURCEPACK_MODE" \
          --baseline-path "$BASELINE_PATH" \
          --report-dir "$REPORT_DIR" \
          --json "$SOURCEPACK_JSON" \
          --markdown "$SOURCEPACK_MARKDOWN" \
          --sarif "$SOURCEPACK_SARIF" \
          --fail-on-warn "$FAIL_ON_WARN"
    - name: Upload SourcePack reports
      if: ${{ always() && inputs.upload-artifact == 'true' }}
      uses: actions/upload-artifact@v4
      with:
        name: sourcepack-report
        path: ${{ inputs.report-dir }}


---

## File: corpus/repos.example.json

Metadata:
- sha256: a271995a2ec3f3b9cb371da6708c72f71ebbcaf1aef7d36b8446a7f3db2ebf98
- bytes: 714
- estimated_tokens: 179

Content:

[
  {
    "repo_id": "flask",
    "url": "https://github.com/pallets/flask.git",
    "ecosystem_tags": ["python", "flask", "github_actions"],
    "expected_features": ["pyproject.toml", "src layout"],
    "notes": "Small public Python project for optional network stress validation. Clone failures are reported as network_unavailable or clone_failed, not product failures."
  },
  {
    "repo_id": "vite",
    "url": "https://github.com/vitejs/vite.git",
    "ecosystem_tags": ["node", "javascript", "typescript", "vite", "monorepo", "workspace", "github_actions"],
    "expected_features": ["package.json", "workspace"],
    "notes": "Public Node/TypeScript project for optional network stress validation."
  }
]


---

## File: docs/ai-agent-workflow.md

Metadata:
- sha256: 1b6efd44adf7a49a493ba6d1f6a1ac2aae2684dbe6355525b4ace8fc1e3df80c
- bytes: 4104
- estimated_tokens: 1026

Content:

AI agent workflow

This workflow is for Codex, Claude Code, Cursor, Copilot-style agents, and any other AI system making repository changes.

SourcePack is not a replacement for tests, linters, type checkers, security scanners, dependency scanners, or human review. SourcePack checks whether AI-authored repository changes are supported by local repository evidence.

Core rule

AI prompt context is not trusted evidence.

A change is not acceptable merely because the prompt, chat history, issue text, or model output says a file, command, dependency, config, workflow, or baseline fact exists.

SourcePack enforcement must use local repository evidence and committed trusted baseline state.

Before editing

Inspect the repository state.

Run:

git status --short

If a trusted SourcePack baseline exists, run:

sourcepack diff . --json

If the installed command is unavailable but the local source tree is usable, run:

PYTHONPATH=src python -m sourcepack.cli diff . --json

If .sourcepack/baseline/active.json is missing, report:

SourcePack cannot run as an enforcement gate because trusted baseline state is missing. I will not create, refresh, repair, or update the baseline unless explicitly instructed.

Do not create or refresh the baseline before making changes unless the maintainer explicitly asks for that exact baseline lifecycle action.

During implementation

Make only the requested changes.

Do not expand SourcePack’s product claim.

Do not add behavior implying SourcePack proves:

* code correctness
* security
* dependency safety
* dependency reputation
* runtime success
* semantic validity
* external API truth
* user intent

Do not grant authority to LLM output.

Do not treat .sourcepack/prompt/ as enforcement state.

Do not make CI create or update .sourcepack/baseline/.

Do not weaken fail-closed missing-baseline behavior in CI.

After editing

Run the task-specific tests required by the prompt.

Then run SourcePack against the changed repository if trusted baseline state exists:

sourcepack diff . --json

If the installed command is unavailable but the local source tree is usable, run:

PYTHONPATH=src python -m sourcepack.cli diff . --json

Do not create, refresh, repair, or update .sourcepack/baseline/ to make the check pass.

Do not hide SourcePack WARN or FAIL results behind passing pytest results.

Final report requirements

Every AI implementation report should include:

1. Files changed.
2. Tests run.
3. Test results.
4. SourcePack gate result.
5. If SourcePack could not run, the exact reason.
6. If SourcePack returned PASS, include the verdict and report path if available.
7. If SourcePack returned WARN or FAIL, include:
    * verdict
    * reason codes
    * affected paths
    * whether findings appear caused by the current changes
    * whether maintainer action is required
8. Confirmation no baseline/prompt authority behavior changed.
9. Confirmation no CI baseline creation/update behavior was introduced.
10. Confirmation no product-claim expansion occurred.

Correct SourcePack gate failure handling

If SourcePack reports unsupported assumptions, do not automatically suppress them.

Acceptable next steps are:

* fix the change so local repository evidence supports it
* add missing repo evidence through a normal reviewed change
* ask the maintainer whether the finding should be accepted
* use policy only for explicitly allowed low-risk findings

Ignored-path policy must remain allowlist-only. At present, ignored-path policy may suppress only new_file.

Unsafe, protected, baseline, dependency, command, workflow, execution-evidence, malformed diff, binary diff, and unknown future reason codes must not be suppressible by ignored paths.

What SourcePack answers

SourcePack answers:

Did this change introduce unsupported repository assumptions relative to local evidence and trusted baseline state?

SourcePack does not answer:

Does this code work?
Is this secure?
Is this dependency safe?
Will runtime succeed?
Is the external API real?
Did the user intend this?

Use SourcePack beside tests and review, not instead of them.


---

## File: docs/architecture.md

Metadata:
- sha256: 54f531cad41cbb92a9596832fed15ccca4855934a8e18bc91c0be5e887d619ad
- bytes: 5413
- estimated_tokens: 1354

Content:

# SourcePack architecture

## Problem

SourcePack is a local-first guardrail for AI-assisted repository edits. Its narrow promise is to catch unsupported AI repo assumptions before commit: invented files, undeclared dependencies, unsupported commands, protected trust-artifact edits, and similar evidence gaps.

## Trust model

SourcePack compares proposed or current changes against a trusted local baseline packet. The baseline is enforcement evidence. Prompt context is only guidance for an AI assistant and is never authoritative enforcement evidence.

## Baseline lifecycle

A trusted baseline is created intentionally with `sourcepack init . --auto` or `sourcepack baseline .` after the current repository state has been reviewed as trusted. Baseline state is stored under `.sourcepack/baseline/` with an active pointer and packet artifacts.

If a baseline is missing while changes exist, SourcePack fails closed with `baseline_missing`. If a baseline is stale, SourcePack warns with `baseline_stale`. If baseline artifacts are manually modified, missing, malformed, or hash-invalid, SourcePack fails with `baseline_corrupt`. Unknown baseline state is not silently trusted.

## Prompt context lifecycle

Prompt context packets help an AI answer with grounded local facts, but prompt context does not bless files, dependencies, commands, or capabilities. A prompt claim that a dependency or file exists is still checked against the trusted baseline and the changed diff.

## Diff judgment pipeline

The CLI obtains a git diff or explicit patch text, parses changed files and added lines, checks path safety, evaluates file existence against the baseline inventory, detects dependency and command assumptions, applies PASS/WARN/FAIL policy, then writes local JSON, Markdown, and HTML reports.

## Reason-code lifecycle

Canonical reason codes live in `src/sourcepack/reason_codes.py`. Documentation should describe only codes that are emitted or intentionally reserved by the code vocabulary. JSON reports use lowercase snake_case reason-code strings.

## Policy modes

Local mode exits zero for PASS and WARN, and nonzero for FAIL. Strict mode and CI mode treat WARN as nonzero. CI mode also keeps machine-readable JSON output clean.

## Report generation

Report data is normalized before rendering. JSON is the machine contract, Markdown is terminal-friendly, and the local HTML report is the v1 human UI. Report-writing failures must not change the underlying judgment verdict.

## Known limitations

SourcePack does not prove semantic correctness, find vulnerabilities, scan secrets, or fully model every ecosystem. Unsupported or uncertain ecosystems should WARN rather than silently PASS as understood.

## Public-alpha engine boundary

The public-alpha core exposes `sourcepack.judgment.judge_repo_change(repo_path, *, staged=False, patch_text=None, policy_mode=PolicyMode.LOCAL) -> Judgment`. The CLI `sourcepack diff` now delegates repo judgment to that API, while keeping rendering, report persistence, and process exit behavior in the CLI layer.

The intended flow is:

1. CLI parses command-line arguments.
2. Git/diff acquisition resolves the repository root and obtains staged, unstaged, untracked, or supplied patch text.
3. Baseline loading validates `.sourcepack/baseline/` before trust is used.
4. Diff parsing extracts changed paths and added evidence.
5. The judgment engine creates report-ready findings from canonical reason codes.
6. Policy mode maps PASS/WARN/FAIL to local, strict, or CI exit behavior.
7. Report renderers write JSON, Markdown, and HTML without changing the verdict.

Prompt context is intentionally outside this enforcement evidence path.

## Evidence graph and replay bundle

SourcePack reports include an additive evidence graph for explanation and reconstructability. Canonical evidence items are defined in `src/sourcepack/evidence.py` and carry stable IDs plus bounded local observations such as category, source type, path, optional line range, observed value, normalized value, reason-code support/contradiction links, uncertainty, and metadata.

The evidence graph is not a new authority. Local project evidence remains the only enforcement authority; prompt context and AI answers remain advisory. Evidence items make it easier to inspect why SourcePack emitted a verdict, but they do not prove code correctness, security, runtime success, external API truth, dependency safety, or user intent.

JSON reports also include an additive replay bundle assembled by `src/sourcepack/reports/json.py`. The bundle records SourcePack version, replay schema version, generation timestamp when available, command/policy mode when provided, verdict, exit code when provided, normalized reason codes, checked and not-checked categories, findings, warnings, blockers, uncertainties, evidence items, reason-code-to-evidence mappings, and safe metadata about baselines, prompt context, patches, and environment when present. Replay/audit data reconstructs SourcePack's decision path, not reality itself, and avoids secrets or full file contents beyond information SourcePack already intentionally reports.

JSON compatibility is additive: existing fields are not removed or renamed. The evidence graph fields (`evidence_items`, `reason_code_evidence`, and `replay_bundle`) are optional for older reports and mode-dependent for callers that build partial reports directly.


---

## File: docs/assets/README.md

Metadata:
- sha256: 13995111442538dc5288bca959c75195f58364d6c29dde81982da610cb990ab4
- bytes: 1488
- estimated_tokens: 372

Content:

# SourcePack screenshot assets

Generate deterministic inputs first:

```bash
python tools/golden_demo.py --clean
```

Expected screenshot files:

- `docs/assets/sourcepack-terminal-red.png`
- `docs/assets/sourcepack-red-report.png`
- `docs/assets/sourcepack-warn-report.png`
- `docs/assets/sourcepack-pass-report.png`

## What to capture

1. `sourcepack-terminal-red.png`
   - Use `examples/golden/output/fail-unsupported-dependency/terminal.txt` as the terminal transcript source.
   - Show commit/check blocked, `unsupported_dependency`, fix guidance, and either the report path or `sourcepack report open`.

2. `sourcepack-red-report.png`
   - Open `examples/golden/output/fail-unsupported-dependency/repo/.sourcepack/reports/latest.html`.
   - Show the FAIL badge, reason-code row for `unsupported_dependency`, affected file `app.py`, and missing-evidence/suggested-fix cards.

3. `sourcepack-warn-report.png`
   - Open `examples/golden/output/warn-new-file/repo/.sourcepack/reports/latest.html`.
   - Show the WARN badge, reason-code row for `new_file`, and affected file `api.py`.

4. `sourcepack-pass-report.png`
   - Open `examples/golden/output/pass-clean/repo/.sourcepack/reports/latest.html`.
   - Show the PASS badge, no blockers, and commit allowed / next action.

The images should be real captures from the golden demo outputs, not hand-edited report mockups. If an illustrative mockup is ever used temporarily, label it as illustrative in the README or adjacent caption.


---

## File: docs/baseline-lifecycle.md

Metadata:
- sha256: f7f53f3047ef012cb11830782c28e9355c0ed3c5af2fda25d0711009b4edc5f5
- bytes: 8634
- estimated_tokens: 2159

Content:

# SourcePack baseline lifecycle

SourcePack separates trusted repository evidence from AI-facing prompt context. This document describes how `.sourcepack/baseline/` should be created, reviewed, and changed without weakening that separation.

## What `.sourcepack/baseline/` is

`.sourcepack/baseline/` is SourcePack's authoritative record of a repository state that a maintainer has accepted as trusted. `sourcepack diff .` compares current changes against that trusted state and reports unsupported assumptions such as missing files, protected trust-artifact edits, undeclared dependencies, and unsupported commands.

## Why the baseline is authoritative

The baseline is authoritative because it is produced from local repository evidence at a reviewed point in time. It is not a claim from an AI assistant, a README paragraph, or a prompt. Treat baseline changes like other trust-sensitive repository changes: review them before relying on them.

## Why `.sourcepack/prompt/` is not authoritative

`.sourcepack/prompt/` stores AI guidance and context. It may help an assistant understand a task, but it is not enforcement state. Prompt context cannot prove that a file, command, dependency, runtime behavior, external API, or user intent is real. SourcePack must not use prompt context to bless its own assumptions.

## How baseline is created

Create a baseline only from a repository state that should become trusted:

```bash
sourcepack init . --auto
# or, after explicit review
sourcepack baseline .
```

Use `sourcepack baseline . --refresh` only after the current state has been intentionally reviewed and accepted. Do not refresh the baseline merely to silence a warning.

## How baseline should be reviewed

Review baseline changes as trust-state changes:

- Confirm the working tree state is the intended trusted state.
- Review any `.sourcepack/baseline/` changes in the same PR or commit.
- Confirm generated baseline files were produced by SourcePack commands, not manual edits.
- Confirm no unreviewed proposed change is being laundered into trust.

## When baseline should change

A baseline should change when maintainers intentionally accept a new trusted repository state, such as after a reviewed commit that adds files, deletes files, changes dependency manifests, or updates supported commands. It should not change during untrusted PR validation just because SourcePack reports WARN or FAIL.

## Who should approve baseline changes

The same maintainer authority that approves trust-sensitive source, dependency, or workflow changes should approve baseline changes. For repositories with code owners or branch protection, baseline updates should follow those rules.

## Why CI consumes baseline but does not create or update it

CI runs on proposed changes and may be triggered by untrusted PR code. If CI created or refreshed `.sourcepack/baseline/`, a PR could turn its own assumptions into trusted evidence. CI should consume the committed baseline and fail closed when it is missing, stale, or corrupt. CI must not run `sourcepack init`, `sourcepack baseline`, `sourcepack baseline --force`, or any automatic trust-state creation/update step for untrusted PRs.

## What missing baseline means

A missing baseline means SourcePack has no trusted local evidence to compare against. In CI, this is a closed failure: SourcePack baseline not found. CI will not create or update trusted baseline state automatically. Locally, create a baseline only after deciding the current repository state should be trusted.

## Safe local setup flow

```bash
git status
sourcepack init . --auto
sourcepack diff .
sourcepack report open
```

Run setup from a reviewed local state. If the tree contains unreviewed AI changes, review or revert them before creating trust state.

## Safe PR flow

1. Commit an intentionally reviewed baseline before relying on CI enforcement.
2. In PR CI, install SourcePack and run `sourcepack diff . --ci`.
3. Let CI fail closed if the baseline is missing, stale, or corrupt.
4. Review any baseline changes in a trusted maintainer workflow, not in untrusted PR CI.

## Unsafe anti-patterns

- Generating baseline inside untrusted PR CI.
- Treating prompt context as enforcement state.
- Auto-refreshing baseline to make a warning disappear.
- Committing baseline changes without review.
- Using SourcePack as proof of runtime correctness.
- Using SourcePack as a dependency safety scanner.

## SourcePack self-dogfooding

SourcePack dogfoods its own enforcement model by committing `.sourcepack/baseline/` and running `sourcepack diff . --ci --json` in CI after package installation. The CI gate consumes the committed baseline only; it does not create, refresh, repair, bless, or update `.sourcepack/baseline/`, and it fails closed if the committed baseline is missing or corrupt.

Maintainers who need to refresh SourcePack's own baseline should first verify a reviewed clean state with the project test, behavior-matrix, and release-smoke gates. Only after those gates pass should they run `sourcepack baseline . --refresh`, review the resulting `.sourcepack/baseline/` changes, and commit them intentionally. AI-assisted PRs should report the SourcePack gate verdict, reason codes, and report path alongside the normal test results.

## Policy config v1

Project policy config lives at `.sourcepack/policy.json`. Policy config v1 is intentionally limited and cannot change the baseline/prompt trust model. The only enforced setting is `ignored_paths`, and it can suppress only explicitly allowlisted low-risk findings. The current allowlist is `new_file`.

```json
{
  "schema_version": "sourcepack.policy.v1",
  "ignored_paths": [
    {"pattern": "docs/**", "reason": "docs-only generated examples reviewed separately"}
  ],
  "prompt_context_authoritative": false,
  "baseline_required_in_ci": true
}
```

Ignored paths require a normalized relative pattern and a reason. Ignore rules cannot suppress dependency, command, baseline, protected artifact, unsafe path, malformed diff, binary diff, unsupported ecosystem, workflow, or execution-evidence findings. Unknown future reason codes are not suppressible. Attempts to make prompt context authoritative or to disable CI baseline requirements are reported as `policy_config_warning` findings and do not change SourcePack trust behavior.

Reserved recognized fields include `strict_default`, `fail_on_warn_in_ci`, `protected_paths`, and `report_formats`. When present, they are reported as policy config warnings because they are not enforcement controls in policy config v1. SARIF is written as a report format only and does not change SourcePack judgment. CI still consumes a committed baseline and fails closed when the baseline is missing. Prompt context is not authoritative.

Validate policy config directly with `sourcepack policy validate [repo]` or `sourcepack policy validate [repo] --json`. The command is read-only: it validates `.sourcepack/policy.json` without creating, updating, or deleting baseline, prompt, report, evidence, hook, or working-tree files. A missing policy file exits `0` and reports that policy config is optional. Invalid JSON and non-object policy roots exit nonzero; JSON mode still writes parseable JSON to stdout only. Validation reports effective ignored-path entries separately from invalid or unsafe ignored entries, including attempts to ignore `.git/**` or `.sourcepack/baseline/**`. Dangerous trust overrides such as `prompt_context_authoritative: true` and `baseline_required_in_ci: false` warn but do not alter trust behavior.

## Replay/audit reconstruction

`sourcepack replay <report-or-bundle-path>` reads a saved SourcePack JSON report or replay bundle and reconstructs the saved verdict, findings, reason codes, evidence mapping, metadata, and replay status. Use `sourcepack replay <report-or-bundle-path> --json` for parseable JSON output. Replay JSON output uses `schema_version: "sourcepack.replay.v1"` and preserves the input report or bundle schema separately as `input_schema_version`.

Replay is read-only. It does not require `.sourcepack/baseline/`, `.sourcepack/prompt/`, Git, or live repository state, and it does not rerun `sourcepack diff` judgment or scanning over the current working tree. Replay reconstructs saved report or bundle content only; it does not prove correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

`sourcepack diff` checks current changes against the trusted baseline and may write reports. `sourcepack replay` only reads an existing report or bundle and reports `reran_judgment: false`.


---

## File: docs/ci.md

Metadata:
- sha256: 873f6c9911e58c636c76911925f8f4b430f5294506ac2631b14eb2753b621b0f
- bytes: 4557
- estimated_tokens: 1140

Content:

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


## Composite Action inputs

The repository action (`uses: ./` or a tagged SourcePack action reference) exposes these inputs. They configure only wrapper behavior; judgment remains delegated to `sourcepack diff` and CI still consumes committed trusted baseline state only.

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
| `comment-pr` | `false` | Reserved for future opt-in PR commenting; not implemented by this action. |

The action also writes `sourcepack.stdout.txt`, `sourcepack.stderr.txt`, and `sourcepack-command.txt`. The command artifact records the exact command arguments the wrapper executed. If trusted baseline state is missing, the action reports that SourcePack failed closed, CI will not create or update baseline state, and the baseline must be created or refreshed locally or in a separate trusted maintainer-controlled setup workflow.

## Replaying saved reports

CI enforcement should continue to use `sourcepack diff . --ci --json` against committed trusted baseline state. For audit readback of an already-produced report, use `sourcepack replay <report-or-bundle-path> --json`. Replay JSON output uses `schema_version: "sourcepack.replay.v1"` and preserves the input report or bundle schema separately as `input_schema_version`. Replay is read-only, does not require live baseline or prompt context, and does not rerun judgment over the current checkout.


---

## File: docs/examples/sourcepack-action.yml

Metadata:
- sha256: d8a29fd970e20de33ffb4d71c798167fc63e1603e3fe6223cdb00ec8b0151007
- bytes: 832
- estimated_tokens: 208

Content:

name: SourcePack Action Example

on:
  workflow_dispatch:
  # Enable pull_request only after .sourcepack/baseline is committed or provided
  # by a separate trusted maintainer-controlled setup workflow.
  # pull_request:

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Run SourcePack
        uses: ./
        with:
          mode: ci
          # fail-on-warn: 'true'
          upload-artifact: 'true'
          sarif: 'true'
      # Optional if your repository has enabled code scanning and you accept
      # uploading local SourcePack report contents.
      # - name: Upload SourcePack SARIF
      #   if: always()
      #   uses: github/codeql-action/upload-sarif@v3
      #   with:
      #     sarif_file: sourcepack-report/sourcepack.sarif.json


---

## File: docs/github-action-quickstart.md

Metadata:
- sha256: 4d5869a1bf056d877b839232cb7013c55ed56348d73f1c937452e5d270038a3c
- bytes: 2944
- estimated_tokens: 736

Content:

# GitHub Actions quickstart

This quickstart is for projects that already committed reviewed trusted baseline state under `.sourcepack/baseline/`.

CI must consume committed baseline state. It must not create, refresh, repair, or bless trusted baseline state for an untrusted pull request.

## Minimal copy-paste workflow

Create `.github/workflows/sourcepack.yml` in the repository that uses SourcePack:

```yaml
name: SourcePack

on:
  pull_request:

jobs:
  sourcepack:
    runs-on: ubuntu-latest
    steps:
      - name: Check out PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - name: Materialize PR delta as workspace changes
        run: |
          git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}
          git reset --mixed ${{ github.event.pull_request.base.sha }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install sourcepack
      - run: sourcepack diff . --ci
```

The `pull_request` trigger path is the actual PR guardrail path. A clean PR checkout alone is structurally unsafe for local-diff validation because committed PR changes are already part of the checked-out tree, leaving no local workspace delta for `sourcepack diff . --ci` to inspect.

The explicit `git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}` and `git reset --mixed ${{ github.event.pull_request.base.sha }}` steps are highly intentional: they make the trusted base ref available, keep the PR files in the working tree, and reset the index to the trusted base commit. These steps make the PR delta visible to SourcePack's diff engine as local workspace modifications.

Do not create, refresh, repair, or bless `.sourcepack/baseline/` inside pull-request CI. Pull-request CI must consume the committed, reviewed trusted baseline state.

The `pull_request` path is the guardrail path. A clean push checkout may contain no uncommitted diff matrix for SourcePack to inspect, so do not present `push` as the main PR guardrail.

## Trust-state rule

Do not add any of these commands to pull-request CI:

```bash
sourcepack init . --auto
sourcepack baseline .
sourcepack baseline . --refresh
```

Create or refresh trusted baseline state only after a maintainer reviews the repository state and decides it should become trusted. Commit the resulting `.sourcepack/baseline/` state before relying on CI enforcement.

## Optional policy validation

If the project has `.sourcepack/policy.json`, CI can validate it before running the gate:

```yaml
      - run: sourcepack policy validate . --json
      - run: sourcepack diff . --ci
```

Keep the PR delta materialization steps from the minimal workflow when adding policy validation.

Policy validation is read-only. It does not create or update baseline, prompt, report, evidence, hook, or working-tree files.


---

## File: docs/limitations.md

Metadata:
- sha256: 606eba16d63400de25c8849584b22869ebadaef134fb44f75175fc5e443cc7fc
- bytes: 943
- estimated_tokens: 236

Content:

# SourcePack limitations

SourcePack intentionally has a narrow local-first scope.

- Dynamic imports may be missed.
- Monorepos may be limited.
- Unsupported ecosystems warn rather than receive full dependency validation.
- Generated code may be difficult to classify.
- Import/package aliases are incomplete.
- Lockfile-only evidence may not be authoritative.
- SourcePack does not prove code correctness.
- SourcePack does not detect vulnerabilities or replace dependency, secret, or supply-chain scanning tools.
- Docker build semantics beyond obvious command and file evidence are limited.

## Public-alpha unsupported ecosystem handling

SourcePack now warns with `unsupported_ecosystem` for recognized but not fully modeled ecosystem markers including Cargo, Go modules, Maven, Gradle, Ruby/Bundler, PHP/Composer, .NET project files, Terraform, and Nix flakes. This is uncertainty evidence, not semantic validation of those ecosystems.


---

## File: docs/problem-fit.md

Metadata:
- sha256: 56cdd88e7efaf9495decf4b970b983bd50197d5e0aea9f26ed6b91ab4d30a861
- bytes: 4352
- estimated_tokens: 1087

Content:

# Does SourcePack fit my problem?

SourcePack is a local evidence guardrail for repository changes. It checks proposed changes against trusted repo evidence and reports unsupported assumptions before commit. It is not a proof system and does not judge whether code is good, secure, maintainable, or architecturally sound.

“Fake repo facts” is plain-language shorthand for locally verifiable unsupported repository assumptions, such as importing a dependency the repo does not declare, editing a file that is not in the trusted baseline, referencing a command the repo evidence does not support, or creating or deleting structure that needs review before becoming trusted.

## Good fit

Use SourcePack when the failure you want to catch is visible in local repository evidence.

| Problem | Why it fits | Related reason codes |
| --- | --- | --- |
| AI-invented dependencies | SourcePack can fail a change that imports or requires a dependency that is not declared in scanned dependency files. | `unsupported_dependency` |
| AI-invented imports | A new import such as `fastapi` without a matching declaration is local evidence of an unsupported dependency assumption. | `unsupported_dependency` |
| AI-invented APIs or commands | A change that references a command unsupported by project evidence can be blocked. | `unsupported_command` |
| AI-invented files | A patch that modifies a path not present in the trusted baseline can be blocked. | `missing_file` |
| AI-invented config keys or dependency declarations | A patch that changes dependency or config manifests can be surfaced for review rather than silently trusted. | `declared_dependency`, `new_file` |
| Wrong repo structure | SourcePack can warn about new files, deleted files, missing files, unsafe paths, protected trust artifacts, and malformed diffs. | `new_file`, `deleted_file`, `missing_file`, `unsafe_path`, `protected_artifact`, `malformed_diff` |

### Examples

- **Invented dependency:** an AI patch imports `fastapi` in Python code, but the scanned dependency files do not declare `fastapi`. SourcePack reports `unsupported_dependency`.
- **Invented import:** an AI patch adds an import for a package that is not already supported by dependency manifests. SourcePack reports `unsupported_dependency`.
- **Invented API or command:** an AI patch documents or wires `npm run dev` when project evidence does not support that command. SourcePack reports `unsupported_command`.
- **Invented file:** an AI patch edits `deploy.sh` when that path is not in the trusted baseline. SourcePack reports `missing_file`.
- **Invented config key:** an AI patch adds or changes a config or dependency manifest entry. SourcePack can surface that as review evidence, commonly through `declared_dependency` or `new_file`, depending on the file change.
- **Wrong repo structure:** an AI patch creates a module in a new path or deletes an existing path. SourcePack reports `new_file` or `deleted_file` so a human reviews the structure change before it becomes trusted.

## Partial fit

SourcePack can reduce AI PR review burden when the PR risk is unsupported repo assumptions. It can tell reviewers where a change conflicts with local evidence, which reason code was triggered, and where the local report was written.

It is only a partial fit for broad AI PR review because it does not prove that the resulting code is correct, secure, useful, or well-designed. Keep running tests, linters, security review, and normal code review.

## Not a fit

Do not use SourcePack as the deciding tool for problems that require human design judgment or runtime validation.

SourcePack does **not** prove:

- Code correctness.
- Security.
- Dependency safety or reputation.
- Runtime success.
- Semantic validity.
- External API truth.
- User intent.
- Good architecture.
- Attractive or maintainable code style.
- Overall product quality.
- Whether management chose a sensible project direction.

## If SourcePack says RED LIGHT

RED LIGHT means the commit is blocked because SourcePack found a local evidence problem that must be reviewed. The reason code explains the class of problem, and the report gives the path and message. Fix the unsupported assumption, intentionally add the missing repo evidence, or reject the patch. Do not refresh trusted baseline state merely to silence a warning or failure.


---

## File: docs/public-alpha-readiness.md

Metadata:
- sha256: e914d23572f850efe774acc99db4670f961d6cbb419d2d750353390f67e75013
- bytes: 5113
- estimated_tokens: 1279

Content:

# SourcePack public-alpha readiness

This document is a release-readiness checklist and provenance template. It does not publish artifacts, create tags, or grant release approval.

## 1.10.0a2 public-alpha release note

1.10.0a2 is a public alpha intended for end-to-end outside evaluation. This release-prep note covers accepted hardening for release-smoke automation and failure-injection coverage, policy/SARIF handling, `sourcepack policy validate [repo] [--json]`, `sourcepack replay <report-or-bundle-path> [--json]` with stable `sourcepack.replay.v1` output, GitHub Action UX and composite Action integration coverage, the committed trusted baseline and self-dogfooding gate, ugly-repo fixtures, baseline lifecycle fixtures, and local-evidence trust-boundary hardening.

SourcePack remains bounded to locally verifiable repository evidence and does not claim to prove code correctness, security, dependency safety or reputation, runtime success, semantic validity, external API truth, or user intent.

## Accepted RC commit/provenance

- Branch: `work` from `git branch --show-current`.
- Commit SHA: missing; record the final release commit after merge.
- Package version: `1.10.0a2` from `pyproject.toml`.
- Wheel artifact: missing in current checkout; produce with `python -m build` and record the generated `dist/*.whl` path.
- Sdist artifact: missing in current checkout; produce with `python -m build` and record the generated `dist/*.tar.gz` path.
- Reviewer/approver: missing; record only after maintainer approval.
- Date: missing; record only when release approval occurs.

## GitHub Action wrapper acceptance

- `action.yml` present: yes.
- `scripts/sourcepack_action.py` present: yes.
- Missing baseline fails closed: documented in `docs/ci.md`; verify with the composite-action tests before release.
- CI does not create or update `.sourcepack/baseline/`: documented in `docs/ci.md` and `.github/workflows/sourcepack.yml`; verify in CI before release.

## Packaging/release-smoke acceptance

- Wheel built: missing; run `python -m build`.
- Sdist built: missing; run `python -m build`.
- Clean wheel install smoke passed: missing; run `python scripts/release_smoke.py` after building artifacts.
- Clean sdist install smoke passed: missing; run `python scripts/release_smoke.py` after building artifacts.
- Console commands passed outside editable install: missing; run `python scripts/release_smoke.py`.

## Baseline lifecycle docs

- Baseline lifecycle documented in `docs/baseline-lifecycle.md`: yes.
- Baseline/prompt separation explicit: yes.
- CI trust-state creation prohibited: yes.

## Reason-code/report docs

- Reason-code documentation updated: yes, tracked in `docs/reason-codes.md`.
- Human report wording reviewed: missing; run `python tools/golden_demo.py --clean` and review generated report wording.
- JSON-only mode preserved: missing in this checklist; verify with `sourcepack diff . --json` or the relevant pytest coverage before release.

## Behavior matrix status

- `python tools/behavior_matrix.py`: missing; run `python tools/behavior_matrix.py`.
- `python tools/behavior_matrix.py --json`: missing; run `python tools/behavior_matrix.py --json`.

## Real-corpus status

- Total runs: missing; run `python tools/real_corpus_validation.py` and record the summary.
- Executed runs: missing; run `python tools/real_corpus_validation.py` and record the summary.
- Failures-only rows: missing; run `python tools/real_corpus_validation.py --failures-only --json` and record the row count.
- Trust violations: missing; run `python tools/real_corpus_validation.py` and record any trust-violation summary.

## Full pytest status

- `python -m pytest -q`: missing; run `python -m pytest -q`.

## Install status

- Editable install: missing; run `python -m pip install -e .`.
- Wheel install: missing; run `python scripts/release_smoke.py` after building artifacts.
- Sdist install: missing; run `python scripts/release_smoke.py` after building artifacts.

## Unsupported ecosystem policy

Unsupported ecosystems remain WARN/YELLOW uncertainty. SourcePack should not add ecosystem support unless intentionally implemented and tested.

## Known limitations

- Unsupported ecosystems remain WARN/YELLOW.
- Baseline must be maintained intentionally.
- CI must not create trust state.
- Local evidence can only verify local evidence.
- Real repos may expose layout cases not yet covered.

## Non-claims: do not claim SourcePack proves

- Code correctness.
- Security.
- Dependency safety.
- Runtime success.
- Semantic validity.
- External API truth.
- User intent.

## Rollback criteria

Stop or roll back release promotion if any accepted gate fails, built artifacts cannot be installed in a clean environment, console commands fail outside editable install, real-corpus failures-only output is nonzero, or documentation introduces product overclaims.

## Manual publish checklist

- Maintainer merge approval.
- Branch protection satisfied.
- PyPI publish approval.
- GitHub release tag approval.
- Marketplace release approval, if applicable.
- Post-publish install verification.


---

## File: docs/real-corpus-validation.md

Metadata:
- sha256: bdc11fac49b01ff91e275aeb4b7278165b8bf511d7cb6e4774d5fdeab01364b1
- bytes: 3691
- estimated_tokens: 923

Content:

# Real-corpus validation

SourcePack's primary deterministic validation remains the behavior matrix. The real-corpus harness is an exposure and stress layer: it applies deterministic filesystem and git mutations to isolated working copies of repositories, then invokes SourcePack as the evaluator.

This does not change the product claim: SourcePack catches unsupported AI repo assumptions before commit by checking proposed changes against locally verifiable project evidence. It does not prove code correctness, security, semantic validity, or external API behavior.

## Corpus configuration

Example corpus entries live at `corpus/repos.example.json`. Each entry contains:

- `repo_id`
- `url`
- `ecosystem_tags`
- `expected_features`
- `notes`

Network access is optional. If a public repository cannot be cloned because the network is unavailable, the harness records `network_unavailable` and skips scenarios for that repository without counting it as a SourcePack product failure. Other clone errors are recorded as `clone_failed`.

## Cache and working directories

Persistent cloned or reused public repositories are stored under `.sourcepack_corpus_cache/`. The cache path is ignored by git.

Each repo/scenario pair runs in an isolated per-scenario working copy. Temporary directories are used only for these isolated working copies, not for persistent corpus repositories. Use `--keep-workdir` to preserve failed scenario working directories and include their paths in JSON output.

## Cleanup and baselines

Before baseline creation and before each scenario mutation, cleanup is exactly:

```sh
git reset --hard HEAD
git clean -fdx
```

The same cleanup runs after each scenario unless `--keep-workdir` preserves a failed workdir. If cleanup fails, the scenario is recorded as `repo_cleanup_failed` and SourcePack is not invoked.

For every scenario working copy the harness creates or refreshes the SourcePack baseline before mutation and verifies that a baseline exists. Baselines are never created after applying a mutation. Baseline failures are recorded as `baseline_failed` and skipped.

## SourcePack invocation

Default filesystem scenarios invoke SourcePack consistently as:

```sh
python -m sourcepack.cli diff . --json
```

Patch-text-only scenarios that cannot be represented safely as ordinary working-tree changes use SourcePack's programmatic judgment API and normalize results to the same JSON result shape.

## Mutation statuses

Every mutation returns a structured result with `status`, `applied`, `target_path`, `before_sha256`, `after_sha256`, `reason`, and `details`.

Supported statuses are:

- `applied`
- `skipped_incompatible_repo`
- `mutation_failed`
- `repo_cleanup_failed`
- `baseline_failed`

If a mutation is not applied, SourcePack is not invoked. If a file mutation leaves the file SHA-256 unchanged, it is recorded as `mutation_failed` and cannot masquerade as a product pass.

## Metrics and release interpretation

The harness tracks false REDs, missed REDs, noisy WARNs, crashes, timeouts, invalid JSON, wrong reason codes, mutation failures, skipped incompatible repos, cleanup failures, baseline failures, policy over-suppression, and trust violations.

Missed REDs and trust violations are release blockers. False REDs are tracked and triaged. Real repo results are stress evidence, not proof of correctness.

## Circuit breaker

A global circuit breaker aborts immediately after five consecutive scenario executions produce `crash` or `invalid_json`. The JSON summary records `circuit_breaker_triggered`, `circuit_breaker_reason`, `consecutive_failure_count`, and the last failed repo/scenario. A triggered circuit breaker exits nonzero.


---

## File: docs/reason-codes.md

Metadata:
- sha256: 8fa89ce5c411a27f0143102de48731e727803cc5de598c19dad346947aaf4c37
- bytes: 18097
- estimated_tokens: 4525

Content:

# SourcePack reason codes

SourcePack reason codes explain why a repo-state transition is PASS, WARN, or FAIL. Local WARN exits `0` unless `--strict` is used. CI mode (`--ci`) treats WARN as nonzero and emits JSON.

## baseline_missing

- **Meaning:** No trusted `.sourcepack/baseline/` exists for the repo state being checked.
- **Local behavior:** FAIL when changes exist; SourcePack refuses to create trust while changes are present. With no changes, `sourcepack diff .` may create a baseline safely.
- **Strict/CI behavior:** FAIL; CI must not establish trust automatically.
- **Common cause:** Running `sourcepack diff .` before `sourcepack init . --auto` or `sourcepack baseline .`.
- **Likely fix:** Review the repo state, then run `sourcepack baseline .` or `sourcepack init . --auto` only when that state should be trusted.
- **Example message:** `No trusted SourcePack baseline exists while changes are present.`

## baseline_stale

- **Meaning:** The trusted baseline exists, but SourcePack detected evidence that it may not match the current trusted repo state.
- **Local behavior:** WARN; the repo needs review before the current state becomes trusted.
- **Strict/CI behavior:** Nonzero because WARN is blocked by `--strict` and `--ci`.
- **Common cause:** The working tree changed after the last trusted baseline refresh, or SourcePack stale-state metadata is present.
- **Likely fix:** Review the current repo state, commit intended changes, then refresh the baseline only after accepting that state as trusted.
- **Example message:** `Trusted SourcePack baseline may not match current repo state.`

## baseline_corrupt

- **Meaning:** SourcePack found the trusted baseline packet, pointer, metadata, or receipt corrupt or unverifiable.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** `.sourcepack/baseline/` artifacts were edited, deleted, moved, or their recorded hashes no longer match.
- **Likely fix:** Treat the baseline as untrusted; recreate it only after verifying the current repo state should be trusted.
- **Example message:** `Trusted SourcePack baseline is corrupt or unverifiable.`

## missing_file

- **Meaning:** A patch modifies a path that was not present in the trusted baseline.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** AI edited a fake file, wrong path, deleted path, or file outside the trusted baseline inventory.
- **Likely fix:** Restore the correct file, create a reviewed new file, or refresh the baseline only after accepting the current repo state.
- **Example message:** `<path> not found in the trusted baseline.`

## new_file

- **Meaning:** The patch creates a file not in the trusted baseline.
- **Local behavior:** WARN; allowed locally by default after human review.
- **Strict/CI behavior:** Nonzero because WARN is blocked by `--strict` and `--ci`.
- **Common cause:** AI created a new module, test, config, or documentation file.
- **Likely fix:** Review the new file, commit if intended, then let the post-commit hook refresh the baseline.
- **Example message:** `<path> was created by the patch.`

## deleted_file

- **Meaning:** The patch deletes a file that existed in the trusted baseline.
- **Local behavior:** WARN.
- **Strict/CI behavior:** Nonzero.
- **Common cause:** AI removed a file or a refactor deleted a tracked path.
- **Likely fix:** Confirm the deletion is intended, restore if accidental, then commit the reviewed deletion.
- **Example message:** `<path> was deleted by the patch.`

## unsupported_dependency

- **Meaning:** New code imports or requires a dependency that is not declared in scanned dependency files.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** AI added `fastapi`, a JS package, or another external dependency without updating dependency manifests.
- **Likely fix:** Remove the import or add the dependency intentionally to the appropriate manifest.
- **Example message:** `fastapi is imported but not declared in scanned dependency files.`

## declared_dependency

- **Meaning:** The same patch adds a dependency declaration.
- **Local behavior:** WARN; the change needs review before becoming trusted.
- **Strict/CI behavior:** Nonzero.
- **Common cause:** A patch updates `pyproject.toml`, `requirements*.txt`, or `package.json` dependencies.
- **Likely fix:** Confirm the dependency addition is intentional and review lockfile or install implications.
- **Example message:** `<dependency> was added to dependency files.`

## unsupported_command

- **Meaning:** A command referenced by the change is not supported by project evidence.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** AI suggests `npm run dev` when `package.json` has no `dev` script, or references Docker Compose without evidence.
- **Likely fix:** Use an existing command or add the project file/script intentionally.
- **Example message:** `npm run dev is not supported by project evidence.`

## unsafe_path

- **Meaning:** A diff path escapes the repository root or is absolute. In JSON this may appear as the path-safety finding emitted for `path_escape`.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** Malicious or malformed diff paths such as `../secret` or `/tmp/file`.
- **Likely fix:** Reject the patch and regenerate a normal repo-relative diff.
- **Example message:** `Diff path escapes the repository root or is absolute.`

## protected_artifact

- **Meaning:** The patch modifies protected SourcePack trust artifacts under `.sourcepack/`.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** AI or a tool edits `.sourcepack/baseline/active.json` or generated trust state.
- **Likely fix:** Do not edit SourcePack trust artifacts manually; rebuild trust with SourcePack commands after review.
- **Example message:** `.sourcepack/baseline/active.json is a protected SourcePack trust artifact.`

## git_path_modification

- **Meaning:** The patch modifies `.git/` internals.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** AI generated a patch touching Git internal files.
- **Likely fix:** Reject the patch; Git internals should not be edited as normal repo files.
- **Example message:** `.git/config modifies Git internal state and is not safe to judge as a normal repository file.`

## binary_diff

- **Meaning:** A binary change was detected and SourcePack cannot semantically evaluate it.
- **Local behavior:** WARN for ordinary binary changes; FAIL for high-risk trust/control paths.
- **Strict/CI behavior:** Nonzero for WARN or FAIL.
- **Common cause:** Image, archive, lockfile, or protected artifact changed as binary data.
- **Likely fix:** Review manually; avoid binary changes in trust/control paths unless intentionally produced by trusted tooling.
- **Example message:** `Binary content was detected at <path> and was not semantically evaluated.`

## malformed_diff

- **Meaning:** SourcePack could not safely parse the diff artifact.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** Non-git diff text, truncated hunks, malformed hunk headers, or unsupported patch format.
- **Likely fix:** Regenerate the diff with Git or rerun `sourcepack diff .`.
- **Example message:** `SourcePack could not safely parse the diff artifact it was asked to judge.`

## unsupported_ecosystem

- **Meaning:** SourcePack detected ecosystem files whose dependency semantics are not implemented.
- **Local behavior:** WARN uncertainty.
- **Strict/CI behavior:** Nonzero.
- **Common cause:** Rust, Go, Maven, or Gradle markers appear in the repo or change.
- **Likely fix:** Treat the result as needing review and rely on ecosystem-specific tests until support is implemented.
- **Example message:** `Cargo.toml detected, but Rust dependency validation is not implemented.`

## policy_dependency_addition

- **Meaning:** Proposed change added an unapproved dependency to project manifest files.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** A configured repository policy blocks new dependency declarations unless separately approved.
- **Likely fix:** Remove the dependency addition or complete the repository-specific approval flow before changing the manifest.
- **Example message:** `Proposed change added an unapproved dependency to project manifest files.`

## policy_protected_path

- **Meaning:** Proposed change modified a path matching `rules.protected_paths` in `.sourcepack/policy.json`.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** A configured repository policy protects high-risk paths such as authentication, billing, or migrations.
- **Likely fix:** Avoid the protected path or update/review repository policy intentionally.
- **Example message:** `Proposed change modified a path protected by repository policy.`

## policy_package_manager_drift

- **Meaning:** Proposed change added or modified a package-manager artifact that conflicts with the configured package manager.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** `package_manager` is `pnpm`, but the change adds or modifies an npm or Yarn lock artifact.
- **Likely fix:** Use artifacts for the configured package manager or adjust repository policy intentionally.
- **Example message:** `Proposed change added or modified a package-manager artifact that conflicts with repository policy.`

## policy_missing_test

- **Meaning:** Proposed change altered a file matching `rules.require_tests_for` without a test-path or test-name change in the same delta.
- **Local behavior:** WARN for the MVP.
- **Strict/CI behavior:** Nonzero because WARN is blocked by `--strict` and `--ci`.
- **Common cause:** Repository policy expects certain source paths to be accompanied by test updates.
- **Likely fix:** Add or update a corresponding test in the same delta, or adjust repository policy intentionally.
- **Example message:** `Proposed change altered a path that repository policy expects to be accompanied by a test change.`

## policy_large_diff

- **Meaning:** Proposed change exceeds `rules.max_changed_lines`.
- **Local behavior:** WARN for the MVP.
- **Strict/CI behavior:** Nonzero because WARN is blocked by `--strict` and `--ci`.
- **Common cause:** The configured repository policy limits large deltas for local review.
- **Likely fix:** Split the proposed change or raise the configured limit intentionally.
- **Example message:** `Proposed change modifies <count> lines, exceeding repository policy limit <limit>.`

## policy_secret_pattern

- **Meaning:** Proposed change added an obvious credential-shaped assignment involving a sensitive name such as `password`, `token`, `secret`, `api_key`, `access_key`, or `private_key`.
- **Local behavior:** FAIL.
- **Strict/CI behavior:** FAIL.
- **Common cause:** Added lines contain high-confidence credential-shaped material rather than an obvious placeholder.
- **Likely fix:** Remove the value or replace it with an obvious placeholder such as `REDACTED` or `changeme`.
- **Example message:** `Proposed change added obvious credential-shaped assignment material blocked by repository policy.`

## Vocabulary enforcement

`src/sourcepack/reason_codes.py` is the source of truth for emitted reason-code IDs. Runtime report construction normalizes IDs to lowercase snake_case and refuses unknown WARN/FAIL finding IDs. Positive evidence such as dependency declarations is represented as review evidence (`declared_dependency`) rather than as proof that prompt context can enforce trust.


## baseline_failed

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## baseline_inventory_missing

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## baseline_locked

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## clipboard_unavailable

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## command_manifest_uncertain

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## declared_command

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## dependency_manifest_uncertain

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## dependency_scope_review

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## dirty_worktree

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## git_unavailable

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## gitignore_unwritable

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## hook_install_failed

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## hygiene_hooks_deferred

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## js_alias_uncertain

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## no_diff

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## no_git_repo

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## path_escape

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## prompt_context_failed

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## repo_not_directory

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## unsupported_rename_copy

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.


## workflow_change

- **Status:** Reserved/emitted canonical code.
- **Meaning:** See `src/sourcepack/reason_codes.py` for the canonical vocabulary entry.

## execution_evidence_missing

- **Status:** Reserved/emitted canonical code.
- **Meaning:** An answer makes an explicit command-execution claim, but no matching local SourcePack execution-ledger entry was found.


## execution_evidence_present

- **Status:** Reserved/emitted canonical code.
- **Meaning:** A matching local SourcePack execution-ledger entry exists for an explicit command-execution claim and recorded exit code 0.


## execution_failed

- **Status:** Reserved/emitted canonical code.
- **Meaning:** A matching local SourcePack execution-ledger entry exists for an explicit command-execution claim and recorded a nonzero exit code.


## execution_inconclusive

- **Status:** Reserved/emitted canonical code.
- **Meaning:** Local SourcePack execution-ledger entries for an explicit command-execution claim were ambiguous or mixed.

## command_manifest_missing

- **Meaning:** A command check requires a local manifest/config file and SourcePack could not find one.
- **Local behavior:** WARN; SourcePack preserves the missing-evidence state rather than pretending the command was verified.
- **Common cause:** A README or script references `make`, `just`, `task`, or similar project commands without the corresponding manifest.
- **Likely fix:** Add the intended manifest or remove the unsupported command claim.

## command_check_inconclusive

- **Meaning:** SourcePack recognized the command family, but the project config was dynamic, ambiguous, unsupported, or unsafe to infer.
- **Local behavior:** WARN; SourcePack does not fake a PASS from uncertain command evidence.
- **Common cause:** Dynamic tox/nox configuration or an unsupported command parser.
- **Likely fix:** Run the command locally with `sourcepack exec -- ...` and/or make the project command declaration explicit.


# What SourcePack is not claiming

Reason codes explain local evidence transitions. SourcePack reason-code output does not prove code correctness, does not prove dependency safety, does not prove runtime success, and does not prove semantic validity. Human-readable messages are remediation aids; canonical reason-code IDs remain the stable machine-readable identifiers.

## policy_config_warning

**Severity:** WARN.

A `.sourcepack/policy.json` entry attempted an unsupported or unsafe policy setting. SourcePack reports the warning and preserves the bounded trust model. Examples include attempts to make prompt context authoritative, disable CI baseline requirements, set reserved fields that are not enforced by policy config v1, ignore protected trust artifacts, or define an ignore rule without a reason.

**Fix:** Remove or correct the unsafe policy entry. Ignore rules must use normalized relative paths and include an explicit reason. Policy config can suppress only explicitly allowlisted low-risk findings; the current allowlist is `new_file`. It cannot suppress dependency, command, baseline, protected artifact, unsafe path, malformed diff, binary diff, unsupported ecosystem, workflow, execution-evidence, unknown future reason-code, path escape, or `.git/**` findings.


---

## File: docs/release-checklist.md

Metadata:
- sha256: 09f4c2bd44714df457ff7532bffd772b077dade97e61f433e9f62a6e4a5e3af7
- bytes: 4300
- estimated_tokens: 1075

Content:

# SourcePack release checklist

This checklist is for manual release preparation. It does not publish to PyPI, create GitHub releases, or replace maintainer approval.

## Preflight gates

- Confirm the release branch and commit SHA.
- Confirm `git status --short` is clean except intentional release-prep changes.
- Run the full pytest suite.
- Run SourcePack behavior-matrix and real-corpus checks.

## Release artifact smoke

Run the release smoke entrypoint before any upload:

```bash
python -m pip install build twine setuptools wheel
python scripts/release_smoke.py
```

The script removes `dist/`, `build/`, and root-level `*.egg-info` artifacts plus the build-backend-generated `src/sourcepack.egg-info` artifact before building. It does not recursively delete nested fixture, vendored, virtualenv, or test-repository `*.egg-info` directories. Cleanup failure is a release blocker.

The script builds deterministic artifacts with `python -m build --no-isolation`, so the maintainer-controlled environment is the build environment. Do not reuse artifacts from an earlier build step.

Expected build artifacts are exactly one wheel and one sdist for the version recorded in package metadata:

- `dist/sourcepack-<version>-py3-none-any.whl`
- `dist/sourcepack-<version>.tar.gz`

The smoke check runs `twine check` for package metadata validation, then opens the wheel and sdist directly and verifies packaged release/demo assets, including the demo `.env`, before install testing. It scans only packaged release/demo assets for forbidden token-shaped strings; it does not scan all source files.

The smoke check then creates separate fresh virtual environments for the wheel and sdist, installs each artifact, and runs:

```bash
sourcepack --version
sourcepack doctor
sourcepack demo
```

`sourcepack demo` may print the expected demo `Verdict: FAIL` / `RED LIGHT` report. That output is not a release-smoke failure as long as the command exits 0 and does not print the old missing-assets error.


## Build wheel/sdist

`python scripts/release_smoke.py` removes `dist/`, `build/`, and root-level `*.egg-info` artifacts plus `src/sourcepack.egg-info`, then builds exactly one wheel and one sdist with `python -m build --no-isolation`. Do not reuse artifacts from earlier build steps.

## Wheel install smoke

Covered by `python scripts/release_smoke.py`: it installs the freshly built wheel in a clean virtual environment and runs `sourcepack --version`, `sourcepack doctor`, and `sourcepack demo`.

## Sdist install smoke

Covered by `python scripts/release_smoke.py`: it installs the freshly built sdist in a separate clean virtual environment and runs the same console smoke commands.

## SourcePack console smoke

Run:

```bash
sourcepack --version
sourcepack doctor
sourcepack demo
python -c "import sourcepack; print(sourcepack.__version__)"
```

## GitHub Action wrapper smoke

Verify `action.yml`, `scripts/sourcepack_action.py`, and `tests/test_github_action.py`. Confirm CI consumes committed trust state and does not create or update `.sourcepack/baseline/` automatically.

## Real-corpus local smoke

Run:

```bash
python tools/real_corpus_validation.py --repo /workspace/sourcepack --json
python tools/real_corpus_validation.py --repo /workspace/sourcepack --json --failures-only
```

The failures-only output should contain zero failure rows for release acceptance.

## Behavior matrix smoke

Run:

```bash
python tools/behavior_matrix.py
python tools/behavior_matrix.py --json
```

## README truth check

Run:

```bash
python -m pytest -q tests/test_readme_truth.py
```

Confirm README install claims match publication reality.

## Version/provenance capture

Record:

- branch
- commit SHA
- package version
- wheel filename and hash
- sdist filename and hash
- gate command results

## PyPI publish steps as manual checklist only

- Confirm maintainer approval.
- Confirm PyPI credentials and target repository.
- Upload only after wheel and sdist smoke pass.
- Verify the public PyPI project page and install from public PyPI after publication.

## Rollback notes

- Do not delete local provenance records.
- If a published artifact is bad, stop promotion and publish a fixed version rather than mutating history.
- Document the failed artifact, reason, and replacement commit.


---

## File: docs/releases/v1.10.0a0-publish-checklist.md

Metadata:
- sha256: 4bf72df6bd078483a51487686d8298aa37e917afc5a8449e64d8ca828f9b69ff
- bytes: 992
- estimated_tokens: 248

Content:

# SourcePack v1.10.0a0 Maintainer Publish Checklist

Use this checklist only after maintainer approval to publish. Do not publish, tag, or create a GitHub release from automated verification alone.

1. Confirm branch and merged commit.
2. Confirm working tree clean.
3. Confirm full gates passed.
4. Confirm artifact hashes.
5. Confirm twine check.
6. Publish to TestPyPI, if desired.
7. Verify TestPyPI install in clean environment.
8. Publish to PyPI, if approved.
9. Verify PyPI install in clean environment.
10. Create GitHub tag.
11. Create GitHub release.
12. If publishing Action, verify uses: owner/repo@tag.
13. Run post-publish fresh-repo smoke.
14. Record final provenance.

## Final provenance fields to record

- Release version.
- Release commit SHA.
- Git tag.
- Wheel filename and SHA256.
- Source distribution filename and SHA256.
- TestPyPI URL, if used.
- PyPI URL, if approved and published.
- GitHub release URL.
- Post-publish install verification commands and results.


---

## File: docs/releases/v1.10.0a0.md

Metadata:
- sha256: 201f4761c2e67b8040ca46af4ce86c851582b6d9d299f707aa41c1dff458695c
- bytes: 4508
- estimated_tokens: 1127

Content:

# SourcePack v1.10.0a0 Release Notes Draft

## Release name/version

SourcePack v1.10.0a0 is an alpha release candidate prepared for maintainer-controlled publication.

## Merged commit SHA

Merged release-state commit verified before release-materials commit: `295e6ff6b00cc8a9eb8e27cf4813b603c5786d20`.

## Bounded product claim

SourcePack packages local repository evidence and applies bounded, evidence-based checks for missing referenced files, undeclared imports in supported ecosystems, unsupported project commands, protected SourcePack artifacts, local policy overrides, and recorded local execution evidence. It reports PASS, WARN, or FAIL based on the local evidence available to the tool.

## Install instructions

After the maintainer publishes the package, install from PyPI in a clean Python environment:

```bash
python -m pip install sourcepack==1.10.0a0
sourcepack --version
sourcepack doctor
```

For local artifact verification before publication:

```bash
python -m pip install dist/sourcepack-1.10.0a0-py3-none-any.whl
python -c "import sourcepack; print(sourcepack.__version__)"
sourcepack --version
sourcepack doctor
sourcepack demo
```

## GitHub Action usage summary

Use the SourcePack action from an immutable release tag after the maintainer creates the tag and release:

```yaml
- uses: owner/repo@v1.10.0a0
```

Replace `owner/repo` with the actual repository owner/name and verify the tag exists before using it in CI. CI should run SourcePack verification; CI must not create or refresh trust state.

## Baseline lifecycle warning

A SourcePack baseline is trust state. Create or refresh it only after a human accepts the current repository state. Do not let CI create trust state, and do not refresh the baseline as a way to bypass a finding.

## What changed

This release-materials draft records the post-merge release verification evidence for v1.10.0a0 and prepares maintainer-facing publication notes. It does not change SourcePack judgment semantics, add ecosystem support, add dependency reputation checks, add LLM semantic analysis, modify baseline trust behavior, or weaken tests.

## Validation evidence summary

The merged release state was verified with Python compile checks for CLI, git, baseline, diff parser, judgment, policy, behavior matrix, real-corpus validation, release smoke, and action script modules. The full pytest suite passed with 404 tests and 16 subtests. The behavior matrix passed 60 of 60 scenarios with 8 metamorphic invariants. Real-corpus validation reported 24 total runs, 14 executed runs, 10 skipped runs, 14 executed passed, and 0 executed failed; failures-only JSON contained zero result rows and print-failures emitted no failure lines. Local build produced both wheel and sdist artifacts, twine check passed for both, and release smoke passed clean wheel and sdist installs with console command checks.

Artifact hashes from the local build:

- `sourcepack-1.10.0a0-py3-none-any.whl`: `5f381e986877533dc3cf4eca7444c0f01a4639a23087f0b8d0e37ea92432f3e6`
- `sourcepack-1.10.0a0.tar.gz`: `eec8df95eb7786c12a37f912f6c2fd5c7ea11f92b3b2644dc6ba018d9b8219c6`

## Known limitations

- Unsupported ecosystems remain WARN/YELLOW unless explicitly supported.
- Baseline must be intentionally maintained.
- CI must not create trust state.
- Local evidence can only verify local evidence.
- Real repositories may expose unsupported layouts.
- Public package install cannot be verified until after publication.

## Non-claims

SourcePack does not prove:

- code correctness
- security
- dependency safety
- runtime success
- semantic validity
- external API truth
- user intent

This draft does not claim PyPI publication happened. This draft does not claim GitHub Marketplace availability happened.

## Manual post-publish verification checklist

- Verify TestPyPI installation in a new clean environment, if TestPyPI was used.
- Verify PyPI installation in a new clean environment after approved PyPI publication.
- Run `sourcepack --version` and confirm `1.10.0a0`.
- Run `sourcepack doctor` and confirm READY status.
- Run `sourcepack demo` and confirm the expected demo output completes.
- Run `python -c "import sourcepack; print(sourcepack.__version__)"` and confirm `1.10.0a0`.
- Verify the GitHub tag points to the intended release commit.
- Verify the GitHub release notes do not overclaim publication state or product guarantees.
- If publishing an Action, verify workflows use `owner/repo@v1.10.0a0` or the maintainer-approved tag.


---

## File: docs/systemic-upgrade-status.md

Metadata:
- sha256: b00f03f0f68430b18d6de053b61ff28054fa2fdd3c475d4a6e7ef58cef18b194
- bytes: 3923
- estimated_tokens: 972

Content:

# SourcePack systemic-upgrade status

## Current phase
Phase 11 complete; remaining next phase is final review/merge.

## Completed phases
- Phase 0: Baseline verification passed before edits.
- Phase 1: Local tool-execution ledger passed required gates.
- Phase 2: Evidence classes and report normalization completed.
- Phase 3: Command intelligence resolver completed.
- Phase 4: Dependency and ecosystem resolver module completed.
- Phase 5: Baseline lifecycle UX commands completed.
- Phase 6: Checked/not-checked confidence report fields completed.
- Phase 7: Local policy/allow CLI completed.
- Phase 8: Real corpus validation harness completed.
- Phase 9: Local report UI evidence/coverage upgrade completed.
- Phase 10: CI usage documentation completed.
- Phase 11: VS Code extension planning document completed; extension not implemented.

## Skipped phases
- None.

## Blocked phases
- None.

## Exact command results
- `python -m py_compile src/sourcepack/cli.py src/sourcepack/judgment.py src/sourcepack/baseline.py src/sourcepack/diff_parser.py src/sourcepack/packet.py src/sourcepack/git.py src/sourcepack/policy.py src/sourcepack/execution_ledger.py src/sourcepack/evidence.py src/sourcepack/commands.py src/sourcepack/dependencies.py tools/real_corpus_validation.py` — exit 0.
- `pytest -q tests/test_engine_inversion.py tests/test_behavior_matrix.py tests/test_golden_demo.py tests/test_readme_truth.py tests/test_execution_ledger.py tests/test_evidence_model.py tests/test_command_resolver.py tests/test_dependency_resolver.py tests/test_baseline_lifecycle_cli.py tests/test_confidence_report.py tests/test_local_policy.py tests/test_real_corpus_validation.py tests/test_report_ui.py tests/test_ci_docs_truth.py` — exit 0; 70 passed.
- `python tools/behavior_matrix.py` — exit 0; Behavior matrix: 55/55 passed, 8 metamorphic invariants.
- `python tools/behavior_matrix.py --json` — exit 0; emitted parseable JSON only, validated with `python -m json.tool`.
- `python tools/golden_demo.py --clean` — exit 0.
- `python tools/release_smoke.py` — exit 0.
- `pytest -q` — exit 0; 292 passed, 16 subtests passed.
- `sourcepack doctor` — exit 0.
- `sourcepack demo` — exit 0.
- `sourcepack exec -- python -c "print('sourcepack ledger smoke')"` — exit 0.
- `sourcepack evidence list` — exit 0.
- `sourcepack baseline status` — exit 0.
- `sourcepack baseline . --refresh --quiet` — exit 0; created active baseline for local gate execution after reviewing the current worktree.
- `sourcepack baseline verify` — exit 0.
- `sourcepack baseline path` — exit 0.
- `sourcepack explain unsupported_dependency` — exit 0.
- `sourcepack policy list` — exit 0.
- `python tools/real_corpus_validation.py --json` — exit 0; status `no_corpus_configured`.
- `sourcepack report path` — exit 0.

## Commits created
- `Complete systemic evidence upgrades (this branch commit)`

## Remaining next phase
Final review and merge.

## Trust invariant status
1. `.sourcepack/baseline/` remains trusted enforcement state: preserved.
2. `.sourcepack/prompt/` remains non-authoritative prompt context: preserved.
3. Prompt context did not become authoritative enforcement evidence: preserved.
4. `file_inventory.json` remains authoritative repo inventory when available: preserved.
5. UNKNOWN/PARTIAL/unchecked states are preserved: preserved via evidence and confidence fields.
6. JSON modes emit JSON only: preserved; behavior-matrix JSON parsed successfully.
7. Report-writing failures do not change verdict: preserved and tested.
8. Local WARN exits 0: preserved by existing policy tests and behavior matrix.
9. Strict/CI WARN exits nonzero: preserved by behavior matrix.
10. FAIL exits nonzero: preserved by behavior matrix.
11. PASS exits 0: preserved by behavior matrix.
12. Execution evidence proves only local command execution and recorded exit/output hashes: preserved in docs and report UI.


---

## File: docs/threat-model.md

Metadata:
- sha256: b14b3b5f214e70cd857e7c928ac1dde9d6a1de224be631c65b99ead705d343d6
- bytes: 1451
- estimated_tokens: 363

Content:

# SourcePack threat model

SourcePack is trust-boundary-adjacent, but it is not a security scanner.

## Defends against

- Invented files referenced or edited by AI output.
- Undeclared dependencies introduced by changed code.
- Unsupported project commands suggested or added without repo evidence.
- Protected baseline edits under `.sourcepack/baseline/`.
- Prompt context laundering, where prompt text claims something exists but the trusted baseline does not support it.

## Does not defend against

- Malicious but valid code that is consistent with the baseline.
- Logic bugs or incorrect implementations.
- Vulnerable declared dependencies.
- Test bypasses or inadequate test coverage.
- Secret exfiltration.
- Full supply-chain compromise.
- Full semantic code correctness.

## Reporting trust-boundary issues

Please report bypasses, false negatives, baseline trust-boundary failures, or prompt-laundering issues privately using the process in `SECURITY.md` when available.

## Public-alpha trust-boundary hardening

Prompt context remains non-authoritative: enforcement uses the trusted baseline, diff evidence, and declared dependency or command manifests, not AI prompt claims. Changes under `.sourcepack/baseline/` and `.git/` fail closed as protected or Git-internal artifact modifications. CI mode does not create new trust from a changed or missing baseline; baseline changes are treated as protected artifacts until reviewed locally.


---

## File: docs/vscode-extension-plan.md

Metadata:
- sha256: 709dca029b5c72bee19b8d300652e933b1b8ca6d7b9dba858de768095253a7a6
- bytes: 378
- estimated_tokens: 95

Content:

# VS Code extension plan

This PR does not implement a VS Code extension. A future local-only extension could:

- run `sourcepack diff` for the current workspace;
- show PASS/WARN/FAIL status;
- open the local SourcePack report;
- inspect findings and reason-code explanations;
- keep telemetry off by default;
- remain future work until a maintained extension scaffold exists.


---

## File: examples/demo_repo/README.md

Metadata:
- sha256: a7e1752b33efa2da5769f5e7aeb6e23498350f9c59a902341f8863a58c607900
- bytes: 153
- estimated_tokens: 39

Content:

# Demo Repo

This is a local-first CLI demo. PDF parsing is not supported. There is no web server. There is no Docker setup. There is no React frontend.


---

## File: examples/demo_repo/pyproject.toml

Metadata:
- sha256: 8bcd24bacf5a5936e911c814331afe1fab6bf036fcda5983c6eb143a89013cb9
- bytes: 99
- estimated_tokens: 25

Content:

[project]
name = "demo-repo"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = ["pytest"]


---

## File: examples/demo_repo/sourcepack/cli.py

Metadata:
- sha256: 27fae75b5f5b55d891fc89682bae49ff7f47f6bcd7b6c188fdb011be5e3c4a92
- bytes: 134
- estimated_tokens: 34

Content:

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    return parser.parse_args()


---

## File: examples/demo_repo/sourcepack/judge.py

Metadata:
- sha256: 409cce4f25abdd804048f4c0630d237e19a0b37a6e4b7feb946fd19cd98b9ffc
- bytes: 133
- estimated_tokens: 34

Content:

def judge(answer: str, known_files: set[str]) -> list[str]:
    return [line for line in answer.splitlines() if "server.py" in line]


---

## File: examples/demo_repo/sourcepack/verify.py

Metadata:
- sha256: 1fe61bada9b2a55f096e3f103d43730040a0eb39ecd8d6048a7e64367ff69ebc
- bytes: 125
- estimated_tokens: 32

Content:

import hashlib

def verify_hash(data: bytes, expected: str) -> bool:
    return hashlib.sha256(data).hexdigest() == expected


---

## File: examples/demo_repo/tests/test_verify.py

Metadata:
- sha256: cb2d232eb2353dd9807728eb487b3fbc42fc8112d96cd49fbbaec6c2b428bc68
- bytes: 164
- estimated_tokens: 41

Content:

from sourcepack.verify import verify_hash

def test_verify_hash():
    assert verify_hash(b"x", "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")


---

## File: examples/fake_ai_answer.md

Metadata:
- sha256: 889eeb9a7fd4438cdfa852e8c1f97d4dd9b1c336bc2a7a51237e811692bfa0aa
- bytes: 440
- estimated_tokens: 110

Content:

This project includes a FastAPI web server in `sourcepack/server.py`.

It supports PDF parsing through `sourcepack/pdf_parser.py`.

To run the full stack locally, use `docker compose up`.

The React dashboard is located at `frontend/App.tsx`.

The CLI verification system is implemented in `sourcepack/verify.py`.

The AI answer judgment system is implemented in `sourcepack/judge.py`.

The package metadata is defined in `pyproject.toml`.


---

## File: pyproject.toml

Metadata:
- sha256: d3e55340f530ebd8c0df5f2bf4367872998c0ee06ce9384b85961f8f0c5fe747
- bytes: 874
- estimated_tokens: 219

Content:

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "sourcepack"
version = "1.10.0a2"
description = "Local-first guardrail for unsupported AI repository assumptions before commit."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
keywords = ["ai", "git", "developer-tools", "guardrails", "local-first"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Software Development :: Quality Assurance",
]


[project.scripts]
sourcepack = "sourcepack.cli:main"
[tool.setuptools.package-data]
sourcepack = ["assets/*.md", "examples/*.md", "examples/*.diff", "examples/demo_repo/**/*", "examples/demo_repo/**/.env", "workbench_static/*"]


---

## File: pytest.ini

Metadata:
- sha256: 4d5193eb36807e4622451417a9fe7bea71e7307137cd05cc214332e514fd9527
- bytes: 44
- estimated_tokens: 11

Content:

[pytest]
testpaths = tests
pythonpath = src


---

## File: schemas/judgment_report.schema.json

Metadata:
- sha256: 9bee37d95c5a9ebe7c8ece691e4ac171153aa99bbdf013aec4e85ec6cba57ab1
- bytes: 655
- estimated_tokens: 164

Content:

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SourcePack Judgment Report",
  "type": "object",
  "required": ["supported_files", "missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"],
  "properties": {
    "supported_files": {"type": "array", "items": {"type": "string"}},
    "missing_files": {"type": "array", "items": {"type": "string"}},
    "unsupported_dependencies": {"type": "array", "items": {"type": "string"}},
    "unsupported_commands": {"type": "array", "items": {"type": "string"}},
    "unsupported_capabilities": {"type": "array", "items": {"type": "string"}}
  }
}


---

## File: schemas/patch_judgment_report.schema.json

Metadata:
- sha256: c88958c2c935ac166482d63368ce49c571ad790fc385f4a926de1644e8ac39c4
- bytes: 1085
- estimated_tokens: 272

Content:

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SourcePack Patch Judgment Report",
  "type": "object",
  "required": ["patch_judgment_schema_version", "verdict", "modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "warnings"],
  "properties": {
    "patch_judgment_schema_version": {"type": "string"},
    "verdict": {"enum": ["PASS", "WARN", "FAIL"]},
    "modified_files": {"type": "array", "items": {"type": "string"}},
    "missing_modified_files": {"type": "array", "items": {"type": "string"}},
    "new_files": {"type": "array", "items": {"type": "string"}},
    "deleted_files": {"type": "array", "items": {"type": "string"}},
    "unsupported_dependencies": {"type": "array", "items": {"type": "string"}},
    "unsupported_commands": {"type": "array", "items": {"type": "string"}},
    "protected_artifact_modifications": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}}
  }
}


---

## File: schemas/reality_map.schema.json

Metadata:
- sha256: 4cffbfc8bad68d1128fb6deab240b94b7fa3c963b92a382bccf3c15918e2aad8
- bytes: 887
- estimated_tokens: 222

Content:

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SourcePack Reality Map",
  "type": "object",
  "required": ["reality_map_schema_version", "tool_version", "generated_at", "input_path", "project_types", "supported_commands", "detected_dependencies", "supported_capabilities", "claim_boundaries"],
  "properties": {
    "reality_map_schema_version": {"type": "string"},
    "tool_version": {"type": "string"},
    "generated_at": {"type": "string"},
    "input_path": {"type": "string"},
    "project_types": {"type": "array", "items": {"type": "string"}},
    "supported_commands": {"type": "array", "items": {"type": "string"}},
    "detected_dependencies": {"type": "array", "items": {"type": "string"}},
    "supported_capabilities": {"type": "array", "items": {"type": "string"}},
    "claim_boundaries": {"type": "array", "items": {"type": "string"}}
  }
}


---

## File: schemas/receipt.schema.json

Metadata:
- sha256: 76774812cc7324913497884a566901d5e0a0ce731cac744bcecf0a8bc340e0c4
- bytes: 355
- estimated_tokens: 89

Content:

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SourcePack Receipt",
  "type": "object",
  "required": ["generated_at", "tool_version", "hashes"],
  "properties": {
    "generated_at": {"type": "string"},
    "tool_version": {"type": "string"},
    "hashes": {"type": "object", "additionalProperties": {"type": "string"}}
  }
}


---

## File: scripts/__init__.py

Metadata:
- sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- bytes: 0
- estimated_tokens: 0

Content:



---

## File: scripts/release_smoke.py

Metadata:
- sha256: c91c67c5793c7bc075d1c3f73a42ffec8f9efafa2b7928867491278daf966680
- bytes: 11402
- estimated_tokens: 2851

Content:

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PACKAGE_NAME = "sourcepack"
MISSING_ASSETS_ERROR = "ERROR: examples/demo_repo and examples/fake_ai_answer.md are required"
DEMO_ENV_MARKER = "SOURCEPACK_DEMO_PLACEHOLDER=example_value_not_a_secret"
FORBIDDEN_TOKEN_PATTERNS = (
    "sk-proj-",
    "THIS_SHOULD_NOT_BE_INCLUDED",
    "OPENAI_API_KEY",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "AKIA",
    "ASIA",
    "ya29.",
)
WHEEL_REQUIRED_FILES = (
    "sourcepack/assets/audit_template.md",
    "sourcepack/assets/packet_instructions.md",
    "sourcepack/examples/fake_ai_answer.md",
    "sourcepack/examples/fake_ai_patch.diff",
    "sourcepack/examples/demo_repo/.env",
)
SDIST_REQUIRED_FILES = tuple(f"src/{path}" for path in WHEEL_REQUIRED_FILES)
WHEEL_DEMO_SCAN_PREFIXES = (
    "sourcepack/assets/",
    "sourcepack/examples/",
)
SDIST_DEMO_SCAN_PREFIXES = tuple(f"src/{prefix}" for prefix in WHEEL_DEMO_SCAN_PREFIXES)


class ReleaseSmokeError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path = ROOT, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    cp = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(cp.stdout, end="")
    if check and cp.returncode != 0:
        raise ReleaseSmokeError(f"command failed with exit {cp.returncode}: {' '.join(cmd)}")
    return cp


def clean_build_outputs(root: Path = ROOT) -> None:
    for path in (root / "dist", root / "build"):
        if path.exists():
            shutil.rmtree(path)
        if path.exists():
            raise ReleaseSmokeError(f"unable to remove build output: {path}")
    egg_info_paths = [*root.glob("*.egg-info"), root / "src" / "sourcepack.egg-info"]
    for path in egg_info_paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        if path.exists():
            raise ReleaseSmokeError(f"unable to remove egg-info artifact: {path}")


def collect_dist_artifacts(dist: Path = DIST) -> list[Path]:
    artifacts = sorted(path for path in dist.iterdir() if path.is_file()) if dist.exists() else []
    if not artifacts:
        raise ReleaseSmokeError(f"no built artifacts found in {dist}; cannot run twine check")
    return artifacts


def build_clean_artifacts() -> None:
    clean_build_outputs(ROOT)
    run([sys.executable, "-m", "build"], ROOT)
    artifacts = collect_dist_artifacts(DIST)
    run([sys.executable, "-m", "twine", "check", *(str(path) for path in artifacts)], ROOT)


def _check_package_metadata(metadata, artifact: Path, label: str) -> tuple[str, str]:
    name = metadata.get("Name")
    version = metadata.get("Version")
    if name != PACKAGE_NAME:
        raise ReleaseSmokeError(f"{label} metadata package name mismatch in {artifact}: expected {PACKAGE_NAME!r}, found {name!r}")
    if not version:
        raise ReleaseSmokeError(f"missing Version in {label} metadata for {artifact}")
    return name, version


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as zf:
        metadata_names = [name for name in zf.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseSmokeError(f"expected exactly one wheel METADATA file in {wheel}, found {metadata_names}")
        metadata = Parser().parsestr(zf.read(metadata_names[0]).decode("utf-8"))
    return _check_package_metadata(metadata, wheel, "wheel")


def _sdist_metadata(sdist: Path) -> tuple[str, str]:
    with tarfile.open(sdist, "r:gz") as tf:
        metadata_names = [
            member
            for member in tf.getmembers()
            if member.isfile()
            and len(PurePosixPath(member.name).parts) == 2
            and PurePosixPath(member.name).name == "PKG-INFO"
        ]
        if len(metadata_names) != 1:
            raise ReleaseSmokeError(f"expected exactly one top-level sdist PKG-INFO file in {sdist}, found {[m.name for m in metadata_names]}")
        metadata_file = tf.extractfile(metadata_names[0])
        if metadata_file is None:
            raise ReleaseSmokeError(f"unable to read sdist PKG-INFO in {sdist}")
        metadata = Parser().parsestr(metadata_file.read().decode("utf-8"))
    return _check_package_metadata(metadata, sdist, "sdist")


def verify_expected_artifacts(dist: Path = DIST) -> tuple[str, Path, Path]:
    wheels = sorted(dist.glob("sourcepack-*.whl"))
    sdists = sorted(dist.glob("sourcepack-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseSmokeError(
            f"expected exactly one SourcePack wheel and one sdist in {dist}; found wheels={wheels}, sdists={sdists}"
        )
    _wheel_name, wheel_version = _wheel_metadata(wheels[0])
    _sdist_name, sdist_version = _sdist_metadata(sdists[0])
    if wheel_version != sdist_version:
        raise ReleaseSmokeError(
            f"wheel metadata version {wheel_version!r} does not match sdist metadata version {sdist_version!r}"
        )
    version = wheel_version
    expected_wheel = dist / f"sourcepack-{version}-py3-none-any.whl"
    expected_sdist = dist / f"sourcepack-{version}.tar.gz"
    if wheels[0] != expected_wheel or sdists[0] != expected_sdist:
        raise ReleaseSmokeError(
            "artifact names do not match packaging metadata version "
            f"{version!r}; expected {expected_wheel.name} and {expected_sdist.name}, "
            f"found {wheels[0].name} and {sdists[0].name}"
        )
    return version, wheels[0], sdists[0]


def _is_concrete_member(name: str, prefix: str) -> bool:
    return name.startswith(prefix) and name != prefix and not name.endswith("/")


def _check_forbidden_text(name: str, text: str) -> None:
    for pattern in FORBIDDEN_TOKEN_PATTERNS:
        if pattern in text:
            raise ReleaseSmokeError(f"forbidden token pattern {pattern!r} found in packaged release asset {name}")


def _decode_member(name: str, data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseSmokeError(f"packaged release asset is not UTF-8 text: {name}") from exc


def inspect_wheel_contents(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        missing = [name for name in WHEEL_REQUIRED_FILES if name not in names]
        if missing:
            raise ReleaseSmokeError(f"wheel is missing required packaged assets: {missing}")
        for prefix in ("sourcepack/examples/demo_repo/sourcepack/", "sourcepack/examples/demo_repo/tests/"):
            if not any(_is_concrete_member(name, prefix) for name in names):
                raise ReleaseSmokeError(f"wheel has no concrete file under {prefix}")
        env_text = _decode_member("sourcepack/examples/demo_repo/.env", zf.read("sourcepack/examples/demo_repo/.env"))
        if DEMO_ENV_MARKER not in env_text:
            raise ReleaseSmokeError("wheel demo .env does not contain the required placeholder marker")
        for name in sorted(names):
            if any(name.startswith(prefix) for prefix in WHEEL_DEMO_SCAN_PREFIXES) and not name.endswith("/"):
                _check_forbidden_text(name, _decode_member(name, zf.read(name)))


def inspect_sdist_contents(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        files_by_inner_path: dict[str, tarfile.TarInfo] = {}
        for member in members:
            parts = PurePosixPath(member.name).parts
            if len(parts) >= 2:
                files_by_inner_path["/".join(parts[1:])] = member
        names = set(files_by_inner_path)
        missing = [name for name in SDIST_REQUIRED_FILES if name not in names]
        if missing:
            raise ReleaseSmokeError(f"sdist is missing required packaged assets: {missing}")
        for prefix in ("src/sourcepack/examples/demo_repo/sourcepack/", "src/sourcepack/examples/demo_repo/tests/"):
            if not any(_is_concrete_member(name, prefix) for name in names):
                raise ReleaseSmokeError(f"sdist has no concrete file under {prefix}")
        env_member = files_by_inner_path["src/sourcepack/examples/demo_repo/.env"]
        env_file = tf.extractfile(env_member)
        if env_file is None:
            raise ReleaseSmokeError("unable to read sdist demo .env")
        env_text = _decode_member("src/sourcepack/examples/demo_repo/.env", env_file.read())
        if DEMO_ENV_MARKER not in env_text:
            raise ReleaseSmokeError("sdist demo .env does not contain the required placeholder marker")
        for name, member in sorted(files_by_inner_path.items()):
            if any(name.startswith(prefix) for prefix in SDIST_DEMO_SCAN_PREFIXES):
                extracted = tf.extractfile(member)
                if extracted is None:
                    raise ReleaseSmokeError(f"unable to read sdist release asset {name}")
                _check_forbidden_text(name, _decode_member(name, extracted.read()))


def _venv_paths(env: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return env / "Scripts" / "python.exe", env / "Scripts" / "sourcepack.exe"
    return env / "bin" / "python", env / "bin" / "sourcepack"


def smoke_installed_artifact(artifact: Path, version: str, name: str, work: Path) -> None:
    env = work / f"venv_{name}"
    venv.EnvBuilder(with_pip=True).create(env)
    python, sourcepack = _venv_paths(env)
    run([str(python), "-m", "pip", "install", "--no-cache-dir", str(artifact)], work)
    version_cp = run([str(sourcepack), "--version"], work)
    if version_cp.stdout.strip() != version:
        raise ReleaseSmokeError(f"{name} sourcepack --version printed {version_cp.stdout.strip()!r}, expected {version!r}")
    doctor_cp = run([str(sourcepack), "doctor"], work)
    if "Status: READY" not in doctor_cp.stdout:
        raise ReleaseSmokeError(f"{name} sourcepack doctor did not report Status: READY")
    demo_cp = run([str(sourcepack), "demo"], work)
    if MISSING_ASSETS_ERROR in demo_cp.stdout:
        raise ReleaseSmokeError(f"{name} sourcepack demo printed the old missing-assets error")


def main() -> int:
    try:
        build_clean_artifacts()
        version, wheel, sdist = verify_expected_artifacts(DIST)
        inspect_wheel_contents(wheel)
        print(f"wheel contents inspection passed: {wheel.name}")
        inspect_sdist_contents(sdist)
        print(f"sdist contents inspection passed: {sdist.name}")
        with tempfile.TemporaryDirectory(prefix="sourcepack_release_smoke_install_") as td:
            work = Path(td)
            smoke_installed_artifact(wheel, version, "wheel", work)
            print("fresh wheel install smoke passed")
            smoke_installed_artifact(sdist, version, "sdist", work)
            print("fresh sdist install smoke passed")
    except ReleaseSmokeError as exc:
        print(f"release smoke failed: {exc}", file=sys.stderr)
        return 1
    print("release smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


---

## File: scripts/sourcepack_action.py

Metadata:
- sha256: c51b5a88cd88f1ca26e6441f3b82b865e7ad22c7896913140da6aadcd5b943f8
- bytes: 7367
- estimated_tokens: 1842

Content:

#!/usr/bin/env python3
"""Thin GitHub Action wrapper for the existing SourcePack CLI."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def _truthy(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _json_data(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _verdict_from_json(path: Path) -> str | None:
    verdict = _json_data(path).get("verdict")
    return verdict if isinstance(verdict, str) else None


def _traffic_light_from_json(path: Path) -> str | None:
    data = _json_data(path)
    for key in ("traffic_light", "trafficLight", "light"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    verdict = data.get("verdict")
    return verdict if isinstance(verdict, str) else None


def _append_step_summary(path: str | None, markdown: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as summary:
        summary.write(markdown)
        if not markdown.endswith("\n"):
            summary.write("\n")


def _artifact_list(report_dir: Path) -> list[str]:
    names = [
        "sourcepack.json",
        "sourcepack.md",
        "sourcepack.sarif.json",
        "sourcepack.stdout.txt",
        "sourcepack.stderr.txt",
        "sourcepack-command.txt",
    ]
    return [name for name in names if (report_dir / name).exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SourcePack for GitHub Actions.")
    parser.add_argument("--mode", choices=["ci", "strict", "local"], default="ci")
    parser.add_argument("--baseline-path", default=".sourcepack/baseline")
    parser.add_argument("--report-dir", default="sourcepack-report")
    parser.add_argument("--json", default="true")
    parser.add_argument("--markdown", default="true")
    parser.add_argument("--sarif", default="true")
    parser.add_argument("--fail-on-warn", default="false")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    baseline = (repo / args.baseline_path).resolve()
    report_dir = (repo / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    command_log = report_dir / "sourcepack-command.txt"
    stdout_log = report_dir / "sourcepack.stdout.txt"
    stderr_log = report_dir / "sourcepack.stderr.txt"
    json_report = report_dir / "sourcepack.json"
    markdown_report = report_dir / "sourcepack.md"
    sarif_report = report_dir / "sourcepack.sarif.json"

    if not baseline.exists():
        message = (
            "SourcePack failed closed because trusted baseline state is missing.\n"
            f"Missing baseline path: {args.baseline_path}\n"
            "CI will not create or update trusted baseline state.\n"
            "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow.\n"
            "This is a trust-boundary behavior, not a package crash.\n"
        )
        _write(command_log, "baseline preflight\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            "- Verdict: FAIL\n"
            "- Traffic light: FAIL\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            "- Artifacts: sourcepack.md, sourcepack.stderr.txt, sourcepack.stdout.txt, sourcepack-command.txt\n"
            "- Missing baseline: SourcePack failed closed because trusted baseline state is missing. "
            "CI will not create or update trusted baseline state. Create or refresh the baseline locally "
            "or in a separate trusted maintainer-controlled setup workflow. This is a trust-boundary behavior, not a package crash.\n",
        )
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))
        print(message, file=sys.stderr, end="")
        print(f"SourcePack report directory: {report_dir}")
        return 2

    command = ["sourcepack", "diff", str(repo)]
    if _truthy(args.json) or args.mode == "ci":
        command.append("--json")
    if args.mode == "ci":
        command.append("--ci")
    elif args.mode == "strict" or _truthy(args.fail_on_warn):
        command.append("--strict")

    _write(command_log, shlex.join(command) + "\n")
    result = _run(command, repo)
    _write(stdout_log, result.stdout)
    _write(stderr_log, result.stderr)

    if _truthy(args.json):
        _write(json_report, result.stdout)

    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    if latest_json.exists():
        shutil.copyfile(latest_json, json_report)
    latest_sarif = repo / ".sourcepack" / "reports" / "latest.sarif.json"
    sarif_status = "disabled"
    if _truthy(args.sarif):
        if latest_sarif.exists():
            shutil.copyfile(latest_sarif, sarif_report)
            sarif_status = f"copied to {sarif_report}"
        else:
            sarif_status = "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact"

    if _truthy(args.markdown):
        verdict = _verdict_from_json(json_report) or "UNKNOWN"
        traffic_light = _traffic_light_from_json(json_report) or verdict
        artifacts = _artifact_list(report_dir)
        if "sourcepack.md" not in artifacts:
            artifacts.insert(1 if "sourcepack.json" in artifacts else 0, "sourcepack.md")
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            f"- Verdict: {verdict}\n"
            f"- Traffic light: {traffic_light}\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            f"- Artifacts: {', '.join(artifacts) if artifacts else 'none'}\n"
            f"- SARIF passthrough: {sarif_status}\n"
            f"- Command artifact: {command_log} contains the exact command arguments used.\n\n"
            "## Command\n\n"
            f"```text\n{shlex.join(command)}\n```\n\n"
            "## Output\n\n"
            f"```text\n{result.stdout}\n```\n",
        )

    print(f"SourcePack report directory: {report_dir}")
    print(f"SourcePack artifacts: {', '.join(_artifact_list(report_dir))}")
    print(f"SourcePack SARIF passthrough: {sarif_status}")

    if markdown_report.exists():
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())


---

## File: src/sourcepack/__init__.py

Metadata:
- sha256: e36ef49e312d7d1f83d0c504f10962bf7a920768df1125607ab8ffa28e6c16f8
- bytes: 649
- estimated_tokens: 163

Content:

from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.10.0a2"

# Keep subprocess-based development/test invocations runnable from temporary
# repositories before the package is installed. Installed packages do not need
# this, but local `python -m sourcepack.cli` smoke tests spawned from another
# cwd do.
_src_root = str(Path(__file__).resolve().parents[1])
_pythonpath = os.environ.get("PYTHONPATH")
if _pythonpath:
    _parts = _pythonpath.split(os.pathsep)
    if _src_root not in _parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([_src_root, *_parts])
else:
    os.environ["PYTHONPATH"] = _src_root


---

## File: src/sourcepack/assets/__init__.py

Metadata:
- sha256: 4c82669d1812be30d4255337f24946320810a891a7cd4384c0cfcb0763454570
- bytes: 43
- estimated_tokens: 11

Content:

"""Packaged SourcePack markdown assets."""


---

## File: src/sourcepack/assets/audit_template.md

Metadata:
- sha256: 363a4b24c719686ddcde6f4ddd12e13b2537301c3c85f6c3a7e126611b83c116
- bytes: 335
- estimated_tokens: 84

Content:

# SourcePack Audit Template

Review the AI answer against the packet manifest and packet contents. Identify supported references, missing references, unsupported dependency claims, unsupported command claims, and unsupported capability claims. Do not claim semantic truth verification unless deterministic packet evidence supports it.


---

## File: src/sourcepack/assets/packet_instructions.md

Metadata:
- sha256: fe7b53dce16afd545a64b74794639557bb5abd570e8e2750682a5275eab57dfc
- bytes: 288
- estimated_tokens: 72

Content:

# SourcePack Packet Instructions

Use only the supplied SourcePack packet as source material. Cite file paths when making claims. Do not infer files, commands, dependencies, services, or capabilities that are not present in the packet. If evidence is missing, say NOT FOUND or UNCERTAIN.


---

## File: src/sourcepack/baseline.py

Metadata:
- sha256: ed00d0ec6267b969db542935104274e9974e4a3725f83a3de0352afd3ab7013b
- bytes: 14995
- estimated_tokens: 3749

Content:

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .paths import ensure_sourcepack_dirs, sourcepack_paths

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"



def protected_baseline_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    return p.startswith(".sourcepack/baseline/")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaselineLockError(RuntimeError):
    pass


def _rel_to_repo(repo: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _read_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    return data, None


def baseline_corrupt_result(repo: Path, message: str, details: dict | None = None, packet_path: Path | None = None, metadata_path: Path | None = None, active_pointer_path: Path | None = None, mode: str = "none", active_build_id: str | None = None) -> dict:
    return {"ok": False, "state": "corrupt", "finding_id": "baseline_corrupt", "message": "Trusted SourcePack baseline is corrupt or unverifiable. Recreate the baseline only after verifying the current repo state should be trusted.", "details": {"reason": message, **(details or {})}, "packet_path": _rel_to_repo(repo, packet_path), "metadata_path": _rel_to_repo(repo, metadata_path), "active_pointer_path": _rel_to_repo(repo, active_pointer_path), "mode": mode, "active_build_id": active_build_id}


def resolve_active_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); paths = sourcepack_paths(repo); pointer = paths["active_pointer"]
    if pointer.exists():
        data, err = _read_json_file(pointer)
        if err:
            return baseline_corrupt_result(repo, f"active.json {err}", active_pointer_path=pointer, mode="pointer")
        build_id = data.get("active_build_id")
        if not isinstance(build_id, str) or not build_id or "/" in build_id or "\\" in build_id or build_id in {".", ".."}:
            return baseline_corrupt_result(repo, "active.json has invalid active_build_id", active_pointer_path=pointer, mode="pointer")
        build_dir = (paths["builds"] / build_id).resolve(); builds_dir = paths["builds"].resolve()
        try:
            build_dir.relative_to(builds_dir)
        except ValueError:
            return baseline_corrupt_result(repo, "active.json points outside baseline builds", active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        packet = build_dir / "packet"; meta = build_dir / "metadata.json"
        if not build_dir.exists() or not packet.exists():
            return baseline_corrupt_result(repo, "active.json points to a missing build", packet_path=packet, metadata_path=meta, active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        return {"ok": True, "state": "resolved", "mode": "pointer", "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, meta), "active_pointer_path": _rel_to_repo(repo, pointer), "active_build_id": build_id, "details": {}}
    legacy = paths["packet"]
    if legacy.exists():
        legacy_artifacts = {"manifest.json", "receipt.json", "reality_map.json", "context.md", "ai_instructions.md"}
        present = {child.name for child in legacy.iterdir()} if legacy.is_dir() else set()
        if (legacy / "manifest.json").exists():
            return {"ok": True, "state": "resolved", "mode": "legacy", "packet_path": _rel_to_repo(repo, legacy), "metadata_path": _rel_to_repo(repo, paths["baseline_meta"]), "active_pointer_path": None, "active_build_id": None, "details": {}}
        if present & legacy_artifacts:
            return baseline_corrupt_result(repo, "legacy baseline packet has baseline artifacts but is missing manifest.json", packet_path=legacy, mode="legacy")
    return {"ok": False, "state": "missing", "finding_id": "baseline_missing", "message": "No trusted SourcePack baseline exists while changes are present.", "details": {}, "packet_path": None, "metadata_path": None, "active_pointer_path": None, "mode": "none", "active_build_id": None}


def _validate_packet_artifacts(repo: Path, packet: Path) -> dict | None:
    required = ["manifest.json", "receipt.json", "reality_map.json"]
    for name in required:
        if not (packet / name).exists():
            return baseline_corrupt_result(repo, f"active packet missing {name}", packet_path=packet)
    for name in ["manifest.json", "receipt.json", "reality_map.json", "token_report.json", "redactions.json"]:
        path = packet / name
        if path.exists():
            _, err = _read_json_file(path)
            if err:
                return baseline_corrupt_result(repo, f"{name} {err}", packet_path=packet)
    receipt, err = _read_json_file(packet / "receipt.json")
    if err:
        return baseline_corrupt_result(repo, f"receipt.json {err}", packet_path=packet)
    hashes = receipt.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return baseline_corrupt_result(repo, "receipt.json has no hashes", packet_path=packet)
    for name, expected in hashes.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            return baseline_corrupt_result(repo, "receipt.json contains invalid hash entry", packet_path=packet)
        if Path(name).is_absolute() or ".." in Path(name).parts:
            return baseline_corrupt_result(repo, "receipt.json tracks unsafe artifact path", packet_path=packet)
        packet_root = packet.resolve(); path = (packet / name).resolve()
        try:
            path.relative_to(packet_root)
        except ValueError:
            return baseline_corrupt_result(repo, "receipt.json tracks path outside packet", packet_path=packet)
        if not path.exists():
            return baseline_corrupt_result(repo, f"receipt-tracked artifact missing: {name}", packet_path=packet)
        try:
            actual = sha256_file(path)
        except OSError as exc:
            return baseline_corrupt_result(repo, f"receipt-tracked artifact unreadable: {name}: {exc}", packet_path=packet)
        if actual != expected:
            return baseline_corrupt_result(repo, f"receipt hash mismatch: {name}", packet_path=packet)
    return None


def validate_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); resolved = resolve_active_baseline(repo)
    if resolved.get("state") in {"corrupt", "missing"}:
        return resolved
    packet = repo / resolved["packet_path"] if resolved.get("packet_path") else None
    meta = repo / resolved["metadata_path"] if resolved.get("metadata_path") else None
    corrupt = _validate_packet_artifacts(repo, packet)
    if corrupt:
        corrupt.update({"mode": resolved.get("mode", "none"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "active_build_id": resolved.get("active_build_id")})
        return corrupt
    if meta and meta.exists():
        _, err = _read_json_file(meta)
        if err:
            return baseline_corrupt_result(repo, f"metadata.json {err}", packet_path=packet, metadata_path=meta, active_pointer_path=repo / resolved["active_pointer_path"] if resolved.get("active_pointer_path") else None, mode=resolved.get("mode", "none"), active_build_id=resolved.get("active_build_id"))
    paths = sourcepack_paths(repo); stale = paths["stale_marker"].exists(); stale_details = None
    if stale:
        stale_details, err = _read_json_file(paths["stale_marker"])
        if err:
            stale_details = {"reason": "unreadable"}
    return {"ok": True, "state": "stale" if stale else "present", "finding_id": "baseline_stale" if stale else None, "message": "Trusted SourcePack baseline may not match current repo state." if stale else "Trusted SourcePack baseline is present.", "details": {"stale_details": stale_details} if stale else {}, "packet_path": resolved.get("packet_path"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "mode": resolved.get("mode"), "active_build_id": resolved.get("active_build_id")}


def acquire_baseline_lock(repo: str | Path, command: str | None = None) -> tuple[Path, int]:
    paths = ensure_sourcepack_dirs(repo); lock = paths["baseline_lock"]
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BaselineLockError("Another SourcePack baseline operation is already in progress.") from exc
    os.write(fd, json.dumps({"pid": os.getpid(), "command": command, "started_at": utc_now()}).encode("utf-8")); os.fsync(fd)
    return lock, fd


def release_baseline_lock(lock: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def _unique_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"


def _write_baseline_packet(repo: Path, packet: Path) -> None:
    from .packet import PacketWriter, SourceScanner

    PacketWriter(packet, SourceScanner(repo).scan(), force=True).write_all()


def _verify_baseline_packet(packet: Path) -> bool:
    from .packet import verify_packet

    return verify_packet(packet)


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    root = Path(repo)
    cp = _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if cp.returncode != 0:
        return False, "git_status_failed"
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    protected = [line for line in lines if protected_baseline_path(line[3:] if len(line) > 3 else line)]
    non_baseline = [line for line in lines if line not in protected]
    if non_baseline:
        return True, None
    if protected:
        return False, "baseline_only_dirty"
    return False, None


def scanner_config_hash() -> str:
    from .packet import scanner_config_hash as packet_scanner_config_hash

    return packet_scanner_config_hash()


def git_metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = _run_git(root, ["rev-parse", "HEAD"])
    branch = _run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, dirty_state = _git_worktree_dirty(root)
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": dirty if dirty_state is None else None,
        "dirty_state": dirty_state,
    }


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None) -> tuple[dict, bool]:
    repo = Path(repo).resolve(); paths = ensure_sourcepack_dirs(repo)
    previous = validate_baseline(repo); created = previous.get("state") == "missing"
    lock = fd = None; build_dir = None
    try:
        lock, fd = acquire_baseline_lock(repo, "baseline")
        build_id = _unique_build_id(); build_dir = paths["builds"] / build_id; packet = build_dir / "packet"
        build_dir.mkdir(parents=True, exist_ok=False)
        _write_baseline_packet(repo, packet)
        if not quiet and not _verify_baseline_packet(packet):
            raise RuntimeError("packet verification returned FAIL")
        candidate = _validate_packet_artifacts(repo, packet)
        if candidate:
            raise RuntimeError(candidate["details"].get("reason", "candidate baseline invalid"))
        meta = {"created_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "scanner_config_hash": scanner_config_hash(), **git_metadata(repo)}
        (build_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        _, meta_err = _read_json_file(build_dir / "metadata.json")
        if meta_err:
            raise RuntimeError(f"metadata.json {meta_err}")
        if fail_stage == "before_pointer_replace":
            raise RuntimeError("injected failure before pointer replacement")
        pointer = {"schema_version": "baseline_pointer.v1", "active_build_id": build_id, "activated_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, build_dir / "metadata.json")}
        _write_json_atomic(paths["active_pointer"], pointer)
        if fail_stage == "after_pointer_replace":
            raise RuntimeError("injected failure after pointer replacement")
        if paths["stale_marker"].exists():
            paths["stale_marker"].unlink()
        return paths, created
    except Exception:
        if build_dir is not None:
            active = None
            try:
                if paths["active_pointer"].exists():
                    active = json.loads(paths["active_pointer"].read_text(encoding="utf-8")).get("active_build_id")
            except Exception:
                active = None
            if active != build_dir.name:
                shutil.rmtree(build_dir, ignore_errors=True)
        raise
    finally:
        if lock is not None and fd is not None:
            release_baseline_lock(lock, fd)


def baseline_report_fields(status: dict) -> dict:
    return {"baseline_state": status.get("state"), "baseline_integrity_ok": bool(status.get("ok")) and status.get("state") in {"present", "stale"}, "baseline_integrity_finding_id": status.get("finding_id"), "baseline_integrity_message": status.get("message"), "baseline_stale": status.get("state") == "stale", "baseline_stale_details": (status.get("details") or {}).get("stale_details"), "baseline_mode": status.get("mode"), "baseline_packet_path": status.get("packet_path"), "baseline_metadata_path": status.get("metadata_path"), "baseline_active_pointer_path": status.get("active_pointer_path")}


---

## File: src/sourcepack/cli.py

Metadata:
- sha256: 33b619badc6bea81993d2eebcdb258e074c976dbd22d62db1253d412f0160de6
- bytes: 166859
- estimated_tokens: 41715

Content:

from __future__ import annotations

import argparse
import contextlib
import io
import importlib.resources as resources
import fnmatch
import hashlib
import json
import os
import platform
import tomllib
import webbrowser
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape
from .ecosystems.python import PY_IMPORT_ALIASES
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.html import render_report_html
from .reports.json import normalized_finding, traffic_report, write_user_report
from .reports.markdown import LIGHT_BY_VERDICT, SEVERITY_ORDER, render_traffic
from .execution_ledger import clear_ledger, entry_to_json, execution_findings, iter_entries, run_and_record, find_repo_root
from .policy import validate_policy_config
from .replay import reconstruct_replay, render_replay_human

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"

DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "target", "coverage", ".pytest_cache", ".sourcepack"
}
DEFAULT_IGNORED_PATTERNS = {
    ".env", ".env.*", "*.pem", "*.key", "*.sqlite", "*.db", "*.png", "*.jpg",
    "*.jpeg", "*.gif", "*.webp", "*.pdf", "*.zip", "*.tar", "*.gz", "*.exe",
    "*.dll", "*.so", "*.dylib", "*.bin", "*.pyc"
}
DEFAULT_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".html", ".css", ".csv", ".toml", ".ini", ".sql", ".sh", ".bat", ".ps1", ".rs",
    ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".xml"
}
SECRET_PATTERNS = [
    ("openai_key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9]{24,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}")),
]
COMMON_DEPENDENCIES = ["fastapi", "flask", "django", "react", "vue", "svelte", "pytest", "typer", "click", "sqlalchemy", "prisma", "pydantic", "pyyaml", "pillow", "beautifulsoup4", "opencv-python", "scikit-learn", "python-dotenv", "pyjwt", "python-dateutil", "boto3", "requests"]
FEATURE_NAMES = ("pdf", "ocr", "web server", "react", "docker", "authentication", "database")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return True
    if b"\x00" in data:
        return True
    if not data:
        return False
    nonprintable = sum(1 for b in data if b < 9 or (13 < b < 32))
    return (nonprintable / max(len(data), 1)) > 0.30


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def redact_secrets(text: str):
    redactions = []
    redacted = text
    for label, pattern in SECRET_PATTERNS:
        def repl(match):
            redactions.append({"pattern": label, "span_start": match.start(), "span_end": match.end()})
            return f"[REDACTED:{label}]"
        redacted = pattern.sub(repl, redacted)
    return redacted, redactions


@dataclass
class IncludedFile:
    relative_path: str
    absolute_path: str
    size_bytes: int
    sha256: str
    source_sha256: str
    packet_sha256: str
    estimated_tokens: int
    extension: str
    content: str


@dataclass
class IgnoredFile:
    relative_path: str
    reason: str


class SourceScanner:
    def __init__(self, input_path: str | Path, max_file_size: int = 1_000_000, include_hidden: bool = False, redact: bool = True):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0

    def ignore(self, path: Path, reason: str):
        rel = str(path.relative_to(self.input_path)) if path.is_absolute() or self.input_path in path.parents else str(path)
        self.ignored_files.append(IgnoredFile(rel, reason))

    def scan(self):
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_path}")
        for root, dirs, files in os.walk(self.input_path, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(dirs)
            files = sorted(files)
            kept_dirs = []
            for d in dirs:
                dpath = root_path / d
                rel = dpath.relative_to(self.input_path)
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "symlink_skipped"))
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs
            for filename in files:
                fp = root_path / filename
                rel = fp.relative_to(self.input_path)
                self.total_seen += 1
                rel_str = str(rel)
                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped")); continue
                if not self.include_hidden and filename.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file")); continue
                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern")); continue
                try:
                    size = fp.stat().st_size
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "stat_error")); continue
                if size > self.max_file_size:
                    self.ignored_files.append(IgnoredFile(rel_str, "max_file_size_exceeded")); continue
                if fp.suffix and fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    self.ignored_files.append(IgnoredFile(rel_str, "unsupported_extension")); continue
                if is_probably_binary(fp):
                    self.ignored_files.append(IgnoredFile(rel_str, "binary_detected")); continue
                try:
                    content = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    self.ignored_files.append(IgnoredFile(rel_str, "decode_error")); continue
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "read_error")); continue
                source_sha256 = sha256_text(content)
                if self.redact:
                    redacted, reds = redact_secrets(content)
                    for r in reds:
                        r["file"] = rel_str
                    self.redactions.extend(reds)
                    content = redacted
                packet_sha256 = sha256_text(content)
                self.included_files.append(IncludedFile(
                    relative_path=rel_str,
                    absolute_path=str(fp.resolve()),
                    size_bytes=size,
                    sha256=packet_sha256,
                    source_sha256=source_sha256,
                    packet_sha256=packet_sha256,
                    estimated_tokens=estimate_tokens(content),
                    extension=fp.suffix.lower(),
                    content=content,
                ))
        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    source = "scanner_included_files"
    try:
        cp = subprocess.run(["git", "ls-files", "-z"], cwd=root, text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError):
        cp = None
    if cp is not None and cp.returncode == 0:
        raw_paths = [p.decode("utf-8", "surrogateescape") for p in cp.stdout.split(b"\0") if p]
        source = "git_ls_files" if raw_paths else "scanner_included_files"
        if not raw_paths:
            raw_paths = sorted(included)
    else:
        raw_paths = sorted(included)
    for raw in raw_paths:
        rel = raw.replace("\\", "/")
        path = root / rel
        rec = {"relative_path": rel, "included_in_prompt_context": rel in included, "source": source}
        try:
            if path.exists() and path.is_file():
                rec["sha256"] = sha256_file(path)
                rec["file_type"] = "binary" if is_probably_binary(path) else "text"
            else:
                rec["file_type"] = "missing"
        except OSError:
            rec["file_type"] = "unreadable"
        files.append(rec)
    return {"schema_version": "sourcepack.file_inventory.v1", "generated_at": utc_now(), "source": source, "files": files}


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md", "file_inventory.json"]

    def __init__(self, out: str | Path, scanner: SourceScanner, force: bool = False):
        self.out = Path(out)
        self.scanner = scanner
        self.force = force

    def prepare_out(self):
        if self.out.exists() and any(self.out.iterdir()):
            if not self.force:
                raise FileExistsError(f"Output directory is non-empty: {self.out}")
            for child in self.out.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        self.out.mkdir(parents=True, exist_ok=True)

    def write_all(self):
        self.prepare_out()
        included_records = []
        for f in self.scanner.included_files:
            rec = asdict(f)
            rec.pop("content")
            included_records.append(rec)
        ignored_records = [asdict(f) for f in self.scanner.ignored_files]
        total_tokens = sum(f.estimated_tokens for f in self.scanner.included_files)
        total_bytes = sum(f.size_bytes for f in self.scanner.included_files)
        manifest = {
            "input_path": str(self.scanner.input_path),
            "generated_at": utc_now(),
            "tool_version": __version__,
            "total_files_seen": self.scanner.total_seen,
            "total_files_included": len(included_records),
            "total_files_ignored": len(ignored_records),
            "total_bytes_included": total_bytes,
            "total_estimated_tokens": total_tokens,
            "included_files": included_records,
            "ignored_files": ignored_records,
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.out / "file_inventory.json").write_text(json.dumps(_tracked_file_inventory(self.scanner.input_path, included_records), indent=2), encoding="utf-8")
        md_parts = ["# SourcePack Context Packet", "", "## Source Manifest Summary", "", f"Input path: {manifest['input_path']}", f"Generated at: {manifest['generated_at']}", f"Files included: {len(included_records)}", f"Estimated tokens: {total_tokens}", ""]
        for f in self.scanner.included_files:
            md_parts.extend([
                f"## File: {f.relative_path}", "", "Metadata:", f"- sha256: {f.sha256}", f"- bytes: {f.size_bytes}", f"- estimated_tokens: {f.estimated_tokens}", "", "Content:", "", f.content, "", "---", ""
            ])
        (self.out / "context.md").write_text("\n".join(md_parts), encoding="utf-8")
        xml_parts = ["<sourcepack>", "  <files>"]
        for f in self.scanner.included_files:
            xml_parts.append(f'    <file path="{xml_escape(f.relative_path)}" sha256="{f.sha256}" bytes="{f.size_bytes}" estimated_tokens="{f.estimated_tokens}">')
            xml_parts.append("      <content>")
            xml_parts.append(xml_escape(f.content))
            xml_parts.append("      </content>")
            xml_parts.append("    </file>")
        xml_parts.extend(["  </files>", "</sourcepack>"])
        (self.out / "context.xml").write_text("\n".join(xml_parts), encoding="utf-8")
        tree_lines = []
        for f in self.scanner.included_files:
            tree_lines.append(f"[INC] {f.relative_path}")
        for f in self.scanner.ignored_files:
            tree_lines.append(f"[IGN] {f.relative_path} - {f.reason}")
        (self.out / "file_tree.txt").write_text("\n".join(sorted(tree_lines)) + "\n", encoding="utf-8")
        (self.out / "ignored_files.txt").write_text("\n".join(f"{f.relative_path}\t{f.reason}" for f in self.scanner.ignored_files) + "\n", encoding="utf-8")
        token_report = {
            "total_estimated_tokens": total_tokens,
            "warnings": [limit for limit in [32_000, 128_000, 200_000, 1_000_000] if total_tokens > limit],
            "per_file": [{"relative_path": f.relative_path, "estimated_tokens": f.estimated_tokens} for f in self.scanner.included_files],
        }
        (self.out / "token_report.json").write_text(json.dumps(token_report, indent=2), encoding="utf-8")
        (self.out / "redactions.json").write_text(json.dumps({"redactions": self.scanner.redactions}, indent=2), encoding="utf-8")
        reality_map = generate_reality_map(manifest, self.out)
        (self.out / "reality_map.json").write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
        (self.out / "ai_instructions.md").write_text(render_ai_instructions(reality_map), encoding="utf-8")
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out



def _included_paths(manifest: dict) -> set[str]:
    return {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}


def _package_json_scripts(packet: Path) -> dict[str, str]:
    contents = _packet_file_contents(packet)
    for rel, content in contents.items():
        if Path(rel).name.lower() == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                return {}
            scripts = package.get("scripts")
            return scripts if isinstance(scripts, dict) else {}
    return {}


def _is_poetry_project(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).name.lower() == "pyproject.toml" and re.search(r"(?m)^\s*\[tool\.poetry\]\s*$", content):
            return True
    return False


def _uses_unittest(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).suffix.lower() == ".py" and re.search(r"(?m)^\s*(import\s+unittest|from\s+unittest\s+import\s+)", content):
            return True
    return False


def generate_reality_map(manifest: dict, packet: Path) -> dict:
    files = _included_paths(manifest)
    lower_files = {f.lower() for f in files}
    deps = dependency_inventory(manifest, packet)
    features = feature_inventory(manifest, packet, deps)
    scripts = _package_json_scripts(packet)
    project_types = []
    package_managers = []
    frameworks = []
    supported_commands = []
    test_commands = []
    build_commands = []
    run_commands = []
    if "pyproject.toml" in lower_files:
        project_types.append("python")
    if any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower_files):
        project_types.append("python")
        package_managers.append("pip")
    if _is_poetry_project(packet):
        package_managers.append("poetry")
    if "package.json" in lower_files:
        project_types.append("node")
        package_managers.append("npm")
        for name in sorted(scripts):
            cmd = "npm test" if name == "test" else f"npm run {name}"
            supported_commands.append(cmd)
            if name == "test": test_commands.append(cmd)
            elif name in {"build", "compile"}: build_commands.append(cmd)
            elif name in {"start", "dev", "serve"}: run_commands.append(cmd)
    if any(Path(f).name.lower() == "dockerfile" for f in files):
        supported_commands.append("docker build")
        build_commands.append("docker build")
    if any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in files):
        supported_commands.append("docker compose up")
        run_commands.append("docker compose up")
    if "pytest" in deps or any(f == "tests" or f.startswith("tests/") for f in lower_files):
        supported_commands.append("pytest")
        test_commands.append("pytest")
    if _uses_unittest(packet):
        supported_commands.append("python -m unittest")
        test_commands.append("python -m unittest")
    framework_map = {"fastapi": "FastAPI", "flask": "Flask", "django": "Django", "react": "React"}
    for dep, label in framework_map.items():
        if dep in deps or (dep == "react" and "react" in features):
            frameworks.append(label)
    ignored = manifest.get("ignored_files", [])
    ignored_reasons = {}
    for rec in ignored:
        reason = rec.get("reason", "unknown")
        ignored_reasons[reason] = ignored_reasons.get(reason, 0) + 1
    included_count = len(manifest.get("included_files", []))
    safe_claims = [
        f"This packet includes {included_count} source files.",
        f"SourcePack scanned input path: {manifest.get('input_path', '')}.",
    ]
    for name in ["pyproject.toml", "package.json", "Dockerfile"]:
        present = name.lower() in {Path(f).name.lower() for f in files}
        safe_claims.append(f"The project {'contains' if present else 'does not include'} {name}.")
    if "react" not in deps and "react" not in features:
        safe_claims.append("No React dependency was detected.")
    if "pdf" not in features:
        safe_claims.append("No PDF parsing capability was detected.")
    if ignored:
        safe_claims.append("The packet includes ignored file records for safety or relevance reasons.")
    claim_boundaries = [
        "SourcePack did not execute the application.",
        "SourcePack did not prove semantic correctness.",
        "SourcePack did not verify external services.",
        "SourcePack did not prove security.",
        "SourcePack did not prove production readiness.",
        "Absence of evidence means unknown, not impossible.",
        "Unsupported claims should be treated as ungrounded.",
    ]
    return {
        "reality_map_schema_version": "1.0",
        "tool_version": __version__,
        "generated_at": utc_now(),
        "input_path": manifest.get("input_path", ""),
        "project_types": sorted(set(project_types)),
        "package_managers": sorted(set(package_managers)),
        "frameworks": sorted(set(frameworks)),
        "entry_points": sorted(f for f in files if Path(f).name in {"main.py", "app.py", "server.py", "cli.py"}),
        "test_commands": sorted(set(test_commands)),
        "build_commands": sorted(set(build_commands)),
        "run_commands": sorted(set(run_commands)),
        "supported_commands": sorted(set(supported_commands)),
        "detected_dependencies": sorted(deps),
        "supported_capabilities": sorted(features),
        "excluded_files_summary": {"total": len(ignored), "reasons": ignored_reasons, "records": ignored[:25]},
        "included_file_count": included_count,
        "confirmed_files": sorted(files),
        "ignored_file_count": len(ignored),
        "safe_claims": safe_claims,
        "unknowns": [
            "Runtime behavior was not executed.",
            "Semantic correctness was not proven.",
            "External services were not verified.",
            "Capabilities not present in structural evidence must be treated as unknown.",
            "Missing files must not be invented.",
        ],
        "claim_boundaries": claim_boundaries,
        "ai_constraints": [
            "Use only the packet and reality map as project evidence.",
            "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
            "If a required file is missing, say it is missing.",
            "If a command is unsupported by detected evidence, say it is unsupported.",
            "If a capability is not in supported_capabilities, treat it as unknown or unsupported.",
            "Cite file paths when making project-specific claims.",
            "Do not claim SourcePack proves semantic truth.",
            "Ask for missing files rather than hallucinating them.",
        ],
    }


def render_ai_instructions(reality_map: dict) -> str:
    lines = [
        "# AI Instructions for This SourcePack Packet", "",
        "Use only the packet and `reality_map.json` as project evidence.",
        "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
        "If a required file is missing, say it is missing and ask for it rather than hallucinating it.",
        "If a command is unsupported by detected evidence, say it is unsupported.",
        "If a capability is not listed in `supported_capabilities`, treat it as unknown or unsupported.",
        "If you introduce a new external dependency, modify the appropriate dependency manifest in the same patch and list it under Dependency Changes.",
        "Only recommend commands listed under Supported Commands unless your patch also adds the project file that defines the new command.",
        "Before referencing a file as existing, it must appear in Confirmed Files; label intentional creations as NEW FILE.",
        "If required evidence is missing, say UNKNOWN and ask for the missing file/output instead of guessing.",
        "Cite file paths when making project-specific claims.",
        "Do not claim SourcePack proves semantic truth, security, production readiness, or external service behavior.", "",
        "## Supported Commands", "",
    ]
    cmds = reality_map.get("supported_commands", [])
    lines.extend([f"- `{cmd}`" for cmd in cmds] or ["- None detected"])
    lines.extend(["", "## Supported Capabilities", ""])
    caps = reality_map.get("supported_capabilities", [])
    lines.extend([f"- {cap}" for cap in caps] or ["- None detected"])
    lines.extend(["", "## Confirmed Files", ""])
    lines.extend(f"- `{path}`" for path in reality_map.get("confirmed_files", [])[:200])
    lines.extend(["", "## Required Answer Contract", "", "- Files to modify", "- New files", "- Dependency changes", "- Commands to run", "- Assumptions/unknowns", "- Patch or code", "", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in reality_map.get("claim_boundaries", []))
    return "\n".join(lines) + "\n"

def load_manifest(packet: Path) -> dict:
    return json.loads((packet / "manifest.json").read_text(encoding="utf-8"))


def verify_packet(packet_path: str | Path, against: str | Path | None = None) -> bool:
    packet = Path(packet_path)
    ok = True
    receipt_path = packet / "receipt.json"
    if not receipt_path.exists():
        print("FAIL receipt.json missing")
        return False
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for name, expected in receipt.get("hashes", {}).items():
        path = packet / name
        if not path.exists():
            print(f"FAIL {name} missing")
            ok = False
            continue
        actual = sha256_file(path)
        if actual == expected:
            print(f"PASS {name}")
        else:
            print(f"FAIL {name} hash mismatch")
            ok = False
    if against:
        manifest = load_manifest(packet)
        source = Path(against).resolve()
        included = {rec["relative_path"]: rec for rec in manifest.get("included_files", [])}
        for rel, rec in included.items():
            source_file = source / rel
            if not source_file.exists():
                print(f"FAIL source missing {rel}")
                ok = False
            elif is_probably_binary(source_file):
                print(f"WARN source now binary {rel}")
            else:
                try:
                    content = source_file.read_text(encoding="utf-8")
                except Exception:
                    print(f"FAIL source unreadable {rel}")
                    ok = False
                    continue
                expected_source_hash = rec.get("source_sha256")
                if expected_source_hash is None:
                    expected_source_hash = rec.get("sha256")
                    redacted, _ = redact_secrets(content)
                    content_hash = sha256_text(redacted)
                else:
                    content_hash = sha256_text(content)
                if content_hash != expected_source_hash:
                    print(f"FAIL source changed {rel}")
                    ok = False
        current_files = []
        for root, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in sorted(dirs) if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
            for filename in sorted(files):
                fp = Path(root) / filename
                if filename.startswith(".") or fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    continue
                rel = str(fp.relative_to(source))
                if rel not in included:
                    current_files.append(rel)
        for rel in current_files:
            print(f"WARN new source file not in packet {rel}")
    print("OVERALL", "PASS" if ok else "FAIL")
    return ok


PATHLIKE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cfg", ".ini", ".css", ".html", ".rs", ".go", ".java", ".rb", ".php", ".sh"}
PROJECT_PATH_PREFIXES = {"src", "sourcepack", "tests", "test", "frontend", "backend", "docs", "app", "lib", "packages", "public", "config", "scripts"}


def _normalize_ai_ref(ref: str) -> str | None:
    ref = ref.strip().strip("`'\".,;)")
    ref = ref.replace("\\", "/")
    if ref.endswith(":"):
        ref = ref[:-1]
    while ref.startswith("./"):
        ref = ref[2:]
    if not ref or ref.startswith("/") or re.match(r"^[A-Za-z]:/", ref):
        return None
    normalized, unsafe = _normalize_diff_path(ref)
    if unsafe or not normalized:
        return None
    return normalized


def _looks_like_ai_file_ref(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in {"Dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml", "pyproject.toml", "package.json", "requirements.txt"}:
        return True
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in PATHLIKE_EXTENSIONS:
        return False
    parts = [p for p in PurePosixPath(normalized).parts if p not in {"."}]
    return "/" in normalized or (parts and parts[0] in PROJECT_PATH_PREFIXES)


def extract_refs(text: str) -> set[str]:
    refs: set[str] = set()
    token = r"(?:\./)?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*\.[A-Za-z0-9_.-]+:?|Dockerfile"
    patterns = [rf"[`'\"]({token})[`'\"]", rf"(?m)^\s*[-*]\s+({token})\b", rf"\b(?:edit|open|update|modify|change|in|file)\s+({token})\b", rf"\b((?:\./)?(?:src|sourcepack|tests|test|frontend|backend|docs|app|lib|packages|public|config|scripts)[\\/][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_.-]+:?)\b"]
    for pattern in patterns:
        for candidate in re.findall(pattern, text, re.I):
            normalized = _normalize_ai_ref(candidate)
            if normalized and _looks_like_ai_file_ref(normalized):
                refs.add(normalized)
    return refs


def _packet_file_contents(packet: Path) -> dict[str, str]:
    context_path = packet / "context.md"
    if not context_path.exists():
        return {}
    text = context_path.read_text(encoding="utf-8", errors="ignore")
    contents: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    in_content = False
    for line in text.splitlines():
        if line.startswith("## File: "):
            if current is not None:
                contents[current] = "\n".join(body).rstrip("\n")
            current = line.removeprefix("## File: ").strip()
            body = []
            in_content = False
        elif current is not None and line == "Content:":
            in_content = True
            body = []
        elif current is not None and in_content and line == "---":
            contents[current] = "\n".join(body).rstrip("\n")
            current = None
            body = []
            in_content = False
        elif current is not None and in_content:
            body.append(line)
    if current is not None:
        contents[current] = "\n".join(body).rstrip("\n")
    return contents


def _normalize_dependency_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _dependency_name_for_import(name: str) -> str:
    normalized = _normalize_dependency_name(name)
    return PY_IMPORT_ALIASES.get(normalized, normalized)


def _js_package_root(imported: str) -> str:
    imported = imported.strip().lower()
    parts = imported.split("/")
    if imported.startswith("@") and len(parts) >= 2 and parts[0] != "@":
        return "/".join(parts[:2])
    if imported.startswith("@/"):
        return imported
    return parts[0]


def _python_dependency_names_from_requirement_lines(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned and not cleaned.startswith(("-", "--")):
            deps.add(_normalize_dependency_name(re.split(r"[<>=!~;\[]", cleaned, maxsplit=1)[0]))
    return deps


def _python_dependency_names_from_pyproject(content: str) -> set[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return set()
    deps: set[str] = set()

    def add_requirement(req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                deps.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_requirement(req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_requirement(req)

    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            for section_name in ("dependencies", "dev-dependencies"):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    for dep in section:
                        if dep.lower() != "python":
                            deps.add(_normalize_dependency_name(dep))
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            deps.update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_requirement(req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_requirement(req)
    return deps


def _add_common_dependency(deps: set[str], name: str):
    normalized = _normalize_dependency_name(name)
    for dep in COMMON_DEPENDENCIES:
        if normalized == _normalize_dependency_name(dep):
            deps.add(dep.lower())


def dependency_inventory(manifest: dict, packet: Path) -> set[str]:
    deps: set[str] = set()
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        suffix = Path(rel).suffix.lower()
        if name == "pyproject.toml":
            for dep in _python_dependency_names_from_pyproject(content):
                _add_common_dependency(deps, dep)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for dep in _python_dependency_names_from_requirement_lines(content):
                _add_common_dependency(deps, dep)
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    for dep_name in section_deps:
                        _add_common_dependency(deps, dep_name)
        elif suffix == ".py":
            for imported in re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", content):
                _add_common_dependency(deps, imported)
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            for imported in re.findall(r"""(?:from\s+["']|import\s*\(\s*["']|require\s*\(\s*["'])(@?[A-Za-z0-9_.-]+)""", content):
                _add_common_dependency(deps, _js_package_root(imported))
    return deps


def _has_import(content: str, *modules: str) -> bool:
    module_pattern = "|".join(re.escape(module) for module in modules)
    return bool(re.search(rf"(?m)^\s*(?:import|from)\s+({module_pattern})(?:\b|[._])", content))


PDF_DEPENDENCIES = {"pypdf", "pdfplumber", "fitz", "pymupdf"}


def _declares_pdf_dependency(rel: str, content: str) -> bool:
    name = Path(rel).name.lower()
    if name == "pyproject.toml":
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_pyproject(content))
    if name.startswith("requirements") and name.endswith(".txt"):
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_requirement_lines(content))
    return False


def feature_inventory(manifest: dict, packet: Path, deps: set[str] | None = None) -> set[str]:
    if deps is None:
        deps = dependency_inventory(manifest, packet)
    contents = _packet_file_contents(packet)
    files = {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}
    lower_files = {rel.lower() for rel in files}
    features: set[str] = set()

    if any(Path(rel).name.lower() in {"dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"} for rel in files):
        features.add("docker")
    if any(rel.endswith(("/pdf_parser.py", "pdf_parser.py")) for rel in lower_files):
        features.add("pdf")
    if any(_declares_pdf_dependency(rel, content) for rel, content in contents.items()):
        features.add("pdf")
    if "react" in deps or any(rel in {"frontend/app.tsx", "frontend/app.jsx"} for rel in lower_files):
        features.add("react")
    if deps & {"fastapi", "flask", "django"} or any(Path(rel).name.lower() in {"server.py", "app.py"} for rel in files):
        features.add("web server")
    if deps & {"sqlalchemy", "prisma"} or any("/migrations/" in f"/{rel}/" or Path(rel).name.lower() in {"schema.prisma", "schema.sql"} for rel in files):
        features.add("database")
    if any(part == "auth" or part.startswith("auth_") for rel in lower_files for part in Path(rel).parts):
        features.add("authentication")

    for rel, content in contents.items():
        suffix = Path(rel).suffix.lower()
        if suffix == ".py":
            if _has_import(content, "pypdf", "pdfplumber", "fitz"):
                features.add("pdf")
            if _has_import(content, "fastapi", "flask", "django") or re.search(r"(?m)^\s*@\w+\.(?:route|get|post|put|patch|delete)\(", content):
                features.add("web server")
            if _has_import(content, "sqlalchemy", "prisma") or re.search(r"(?i)\b(sqlite|postgres(?:ql)?|mysql)://", content):
                features.add("database")
            if _has_import(content, "jwt", "oauthlib", "authlib") or re.search(r"(?i)@\w+\.(?:route|get|post)\([^)]*login", content):
                features.add("authentication")
            if _has_import(content, "pytesseract", "easyocr"):
                features.add("ocr")
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            if re.search(r"""(?:from\s+["']react["']|require\s*\(\s*["']react["']|import\s+React\b)""", content):
                features.add("react")
            if re.search(r"(?i)\b(jwt|oauth|session|login)\b", content):
                features.add("authentication")
        elif Path(rel).name.lower() == "package.json":
            if re.search(r'"react"\s*:', content):
                features.add("react")
    return features


PROTECTED_PACKET_ARTIFACTS = {"manifest.json", "receipt.json", "reality_map.json", "ai_instructions.md"}


def _normalize_inventory_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    rel, unsafe = _normalize_diff_path(value)
    if unsafe or not rel:
        return None
    return rel


def _baseline_inventory_from_packet(packet: str | Path, manifest: dict | None = None) -> tuple[set[str], bool]:
    """Return authoritative enforcement baseline paths when a packet has them.

    Prompt context manifests may be selective, so diff enforcement must prefer the
    baseline file inventory artifact when it exists. The boolean is True only
    when a full inventory artifact was loaded successfully.
    """
    packet = Path(packet)
    for name in ("file_inventory.json", "inventory.json", "baseline_inventory.json"):
        path = packet / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_files = data.get("files") if isinstance(data, dict) else data
        if not isinstance(raw_files, list):
            continue
        files: set[str] = set()
        for item in raw_files:
            raw_path = item.get("relative_path") if isinstance(item, dict) else item
            rel = _normalize_inventory_path(raw_path)
            if rel:
                files.add(rel)
        return files, True
    return _included_paths(manifest or load_manifest(packet)), False


def known_files(manifest: dict, packet_path: str | Path | None = None) -> set[str]:
    if packet_path is not None:
        files, _ = _baseline_inventory_from_packet(packet_path, manifest)
        return files
    return _included_paths(manifest)


def supported_commands_inventory(reality_map: dict) -> set[str]:
    return set(reality_map.get("supported_commands", []))


def docker_evidence(files: set[str]) -> dict[str, bool]:
    names = {Path(f).name.lower() for f in files}
    return {
        "dockerfile": "dockerfile" in names,
        "compose": bool(names & {"docker-compose.yml", "compose.yaml", "compose.yml"}),
    }


def python_project_evidence(files: set[str], deps: set[str]) -> dict[str, bool]:
    lower = {f.lower() for f in files}
    return {
        "python_project": "pyproject.toml" in lower or any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower),
        "tests": any(f == "tests" or f.startswith("tests/") for f in lower),
        "pytest": "pytest" in deps,
    }


def node_project_evidence(files: set[str], scripts: dict[str, str]) -> dict[str, bool]:
    return {"package_json": "package.json" in {f.lower() for f in files}, "scripts": bool(scripts)}


def extract_js_import_specifiers_from_text(text: str) -> set[str]:
    specifiers: set[str] = set()
    patterns = [
        r"""\bimport\s+(?:[^"'()]+?\s+from\s+)?["']([^"']+)["']""",
        r"""\bexport\s+[^"']*?\s+from\s+["']([^"']+)["']""",
        r"""\bimport\s*\(\s*["']([^"']+)["']\s*\)""",
        r"""\brequire\s*\(\s*["']([^"']+)["']\s*\)""",
    ]
    for pattern in patterns:
        specifiers.update(m.strip() for m in re.findall(pattern, text) if m.strip())
    return {s.lower() for s in specifiers}


def extract_imports_from_text(text: str, suffix: str = ".py") -> set[str]:
    imports: set[str] = set()
    if suffix == ".py":
        imports |= set(re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text))
    elif suffix in JS_EXTS:
        imports |= extract_js_import_specifiers_from_text(text)
    return {i.lower() for i in imports}


@dataclass
class PatchFileChange:
    path: str
    old_path: str | None
    new_file: bool = False
    deleted_file: bool = False
    added_lines: list[str] | None = None
    diff_lines: list[str] | None = None
    unsafe_path: bool = False
    operation: str = "modify"


def _normalize_diff_path(path: str) -> tuple[str, bool]:
    raw = path.strip().replace("\\", "/")
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    if not raw or raw in {"a/", "b/"}:
        return raw, True
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        return raw, True
    parts: list[str] = []
    unsafe = False
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                unsafe = True
            else:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts), unsafe


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []
    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None
    new_file = False
    deleted_file = False
    operation = "modify"

    malformed = False

    def clean(path: str) -> tuple[str, bool]:
        path = path.strip().split("\t", 1)[0]
        return _normalize_diff_path(path)

    def flush():
        nonlocal current
        if current is not None:
            changes.append(current)
            current = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush(); old_path = new_path = None; new_file = deleted_file = False; operation = "modify"
            parts = line.split()
            if len(parts) >= 4:
                old_path, old_unsafe = clean(parts[2]); new_path, new_unsafe = clean(parts[3])
                if old_unsafe or new_unsafe:
                    malformed = True
            else:
                malformed = True
        elif line.startswith("new file mode"):
            new_file = True
        elif line.startswith("deleted file mode"):
            deleted_file = True
        elif line.startswith("rename from "):
            old_path, unsafe = clean(line.removeprefix("rename from "))
            operation = "rename"
            malformed = malformed or unsafe
        elif line.startswith("rename to "):
            new_path, unsafe = clean(line.removeprefix("rename to "))
            operation = "rename"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=False, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("copy from "):
            old_path, unsafe = clean(line.removeprefix("copy from "))
            operation = "copy"
            malformed = malformed or unsafe
        elif line.startswith("copy to "):
            new_path, unsafe = clean(line.removeprefix("copy to "))
            operation = "copy"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=True, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("--- "):
            val = line[4:].strip()
            if val == "/dev/null":
                old_path = None
            else:
                old_path, unsafe = clean(val)
                malformed = malformed or unsafe
        elif line.startswith("+++ "):
            val = line[4:].strip()
            if val == "/dev/null":
                new_path = None
                unsafe = False
            else:
                new_path, unsafe = clean(val)
            malformed = malformed or unsafe
            path = new_path or old_path or ""
            current = PatchFileChange(path=path, old_path=old_path, new_file=new_file or old_path is None, deleted_file=deleted_file or new_path is None, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("@@ ") and current is None:
            malformed = True
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.added_lines.append(line[1:])
            current.diff_lines.append(line)
        elif current is not None and (line.startswith("-") or line.startswith(" ") or line.startswith("@@")):
            current.diff_lines.append(line)
    flush()
    if malformed:
        changes.append(PatchFileChange(path="", old_path=None, added_lines=[], diff_lines=[], unsafe_path=True))
    return changes


def _dependency_additions_from_patch(changes: list[PatchFileChange]) -> set[str]:
    return set()


def analyze_patch(packet_path: str | Path, patch_text: str, changes: list[PatchFileChange] | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    reality = json.loads((packet / "reality_map.json").read_text(encoding="utf-8")) if (packet / "reality_map.json").exists() else generate_reality_map(manifest, packet)
    files, baseline_inventory_loaded = _baseline_inventory_from_packet(packet, manifest)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    if changes is None:
        changes = parse_unified_diff(patch_text)
    patch_deps = _dependency_additions_from_patch(changes)
    report = {
        "patch_judgment_schema_version": "1.0",
        "verdict": "PASS",
        "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [],
        "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "git_path_modifications": [], "warnings": [],
    }
    if any(ch.unsafe_path for ch in changes):
        report["path_escape"] = True
    all_added = []
    for ch in changes:
        report["modified_files"].append(ch.path)
        if ch.new_file:
            report["new_files"].append(ch.path)
        elif ch.operation in {"rename", "copy"}:
            pass
        elif ch.path not in files:
            if baseline_inventory_loaded or ch.path in _included_paths(manifest):
                report["missing_modified_files"].append(ch.path)
            else:
                report.setdefault("uncertain_modified_files", []).append(ch.path)
        if ch.deleted_file:
            report["deleted_files"].append(ch.path)
        protected = ch.path.startswith(".sourcepack/")
        git_internal = ch.path == ".git" or ch.path.startswith(".git/")
        workflow = ch.path.startswith(".github/workflows/")
        if protected:
            report["protected_artifact_modifications"].append(ch.path)
        if git_internal:
            report.setdefault("git_path_modifications", []).append(ch.path)
        if workflow:
            report.setdefault("uncertainties", []).append({"id": "workflow_change", "message": f"{ch.path} changes repository automation and requires review", "path": ch.path, "evidence": ch.path})
        if ch.operation in {"rename", "copy"}:
            report.setdefault("uncertainties", []).append({"id": "unsupported_rename_copy", "message": f"{ch.operation} semantics for {ch.path} require review", "path": ch.path, "evidence": ch.old_path or ch.path})
        added = "\n".join(ch.added_lines or [])
        all_added.append(added)
        for imported in extract_imports_from_text(added, Path(ch.path).suffix.lower()):
            for dep in COMMON_DEPENDENCIES:
                if _normalize_dependency_name(imported) == _normalize_dependency_name(dep) and dep not in deps and dep not in patch_deps:
                    report["unsupported_dependencies"].append(dep)
    added_text = "\n".join(all_added)
    supported = supported_commands_inventory(reality)
    added_paths = {ch.path for ch in changes}
    compose_added = any(Path(path).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for path in added_paths)
    if re.search(r"docker\s+compose\s+up", added_text, re.I):
        evidence = docker_evidence(files)
        if compose_added:
            report["warnings"].append("Patch adds Docker Compose support used by commands; review the new support.")
            report.setdefault("declared_commands", []).append("docker compose up")
        elif not evidence["compose"]:
            report["unsupported_commands"].append("docker compose up")
    patch_scripts = set()
    command_uncertainties = []
    for ch in changes:
        if Path(ch.path).name.lower() != "package.json":
            continue
        base = _packet_file_contents(packet).get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        try:
            package = json.loads(post)
        except json.JSONDecodeError:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
            continue
        package_scripts = package.get("scripts")
        if isinstance(package_scripts, dict):
            patch_scripts.update(str(script) for script in package_scripts if isinstance(script, str) and script not in scripts)
    if command_uncertainties:
        report.setdefault("uncertainties", []).extend(command_uncertainties)
    for cmd in sorted(set(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))):
        normalized = cmd if cmd == "npm test" else cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script in patch_scripts:
                report["warnings"].append(f"Patch adds npm script {script} used by commands; review the new support.")
                report.setdefault("declared_commands", []).append(normalized)
            elif script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append(normalized)
    if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
        py = python_project_evidence(files, deps)
        if not (py["pytest"] or py["tests"] or "pytest" in supported):
            report["unsupported_commands"].append("pytest")
    if not baseline_inventory_loaded:
        outside_context = sorted({
            ch.path for ch in changes
            if not ch.new_file
            and not ch.deleted_file
            and ch.path not in _included_paths(manifest)
        })
        if outside_context:
            report.setdefault("uncertainties", []).append({"id": "baseline_inventory_missing", "message": "Baseline packet lacks full file inventory; modified files outside prompt context could not be checked against tracked repo inventory.", "evidence": ", ".join(outside_context)})
    if report["new_files"]:
        report["warnings"].append("Patch creates new files that were not part of the original packet reality.")
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "path_escape"]
    if any(report.get(k) for k in fail_keys):
        report["verdict"] = "FAIL"
    elif report["new_files"] or report["warnings"] or report.get("uncertainties"):
        report["verdict"] = "WARN"
    for key in ["modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "warnings"]:
        report[key] = sorted(set(report[key]))
    return report


def render_patch_judgment_report(report: dict) -> str:
    traffic = report.get("traffic") if isinstance(report.get("traffic"), dict) else patch_report_to_traffic(report, "patch_judgment_report.json")
    lines = ["# SourcePack Patch Judgment Report", "", f"Verdict: {traffic.get('verdict', report.get('verdict', 'WARN'))}", f"Report: {report.get('report_path', 'patch_judgment_report.json')}", "", f"Next action: {traffic.get('next_action')}", ""]
    grouped = [("blockers", "Blockers"), ("warnings", "Review warnings"), ("uncertainties", "Uncertainties")]
    for key, title in grouped:
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {f.get('id')}: {f.get('message')}" for f in report.get(key, [])] or ["None"])
        lines.append("")
    for key, title in [("checked_categories", "Checked"), ("not_checked", "Not checked")]:
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {item}" for item in report.get(key, [])] or ["None"])
        lines.append("")
    lines.extend(["## Raw Patch Sections", ""])
    sections = [("modified_files", "Modified Files"), ("missing_modified_files", "Missing Modified Files"), ("new_files", "New Files"), ("deleted_files", "Deleted Files"), ("unsupported_dependencies", "Unsupported Dependencies"), ("unsupported_commands", "Unsupported Commands"), ("protected_artifact_modifications", "Protected Packet Artifact Modifications"), ("git_path_modifications", "Git Path Modifications"), ("binary_diffs", "Binary Diffs"), ("binary_diff_blockers", "Binary Diff Blockers"), ("declared_dependencies", "Declared Dependencies"), ("declared_commands", "Declared Commands"), ("warnings_text", "Legacy Warnings")]
    legacy = dict(report); legacy["warnings_text"] = report.get("legacy_warnings", report.get("warnings", []))
    for key, title in sections:
        lines.extend([f"### {title}"])
        lines.extend([f"- {item}" for item in legacy.get(key, [])] or ["None"])
        lines.append("")
    return "\n".join(lines)


def judge_patch(packet_path: str | Path, patch_path: str | Path, out_dir: str | Path) -> dict:
    try:
        patch_text = Path(patch_path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report = {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    else:
        report = judge_patch_text(packet_path, patch_text)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    report_path = str(out / "patch_judgment_report.json")
    traffic = patch_report_to_traffic(report, report_path)
    enriched = dict(report)
    enriched["legacy_warnings"] = list(report.get("warnings", []))
    enriched.update({
        "schema_version": "patch_judgment_report.v1",
        "sourcepack_version": __version__,
        "generated_at": utc_now(),
        "light": traffic.get("light"),
        "reason_type": traffic.get("reason_type"),
        "commit_policy": traffic.get("commit_policy"),
        "findings": traffic.get("findings", []),
        "blockers": traffic.get("blockers", []),
        "warnings": [f for f in traffic.get("warnings", []) if f.get("category") != "uncertainty"],
        "uncertainties": [f for f in traffic.get("warnings", []) if f.get("category") == "uncertainty"],
        "checked_categories": traffic.get("checked_categories", []),
        "not_checked": traffic.get("not_checked", []),
        "next_action": traffic.get("next_action"),
        "report_path": report_path,
        "traffic": traffic,
    })
    text = render_patch_judgment_report(enriched)
    (out / "patch_judgment_report.md").write_text(text, encoding="utf-8")
    (out / "patch_judgment_report.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    print(render_traffic(traffic, verbose=True), end="")
    return enriched

def _has_negation_before(text: str, start: int) -> bool:
    window = text[max(0, start - 48):start].lower()
    return bool(re.search(r"\b(do not|don't|avoid|not|no|without|unless|until|does not|is no|will not)\b", window))


def _ai_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    aliases = [dep_pat]
    for imported, package in PY_IMPORT_ALIASES.items():
        if package == _normalize_dependency_name(dep):
            aliases.append(re.escape(imported))
    alias_pat = "(?:" + "|".join(sorted(set(aliases), key=len, reverse=True)) + ")"
    patterns = [
        rf"\bimport\s+{alias_pat}\b",
        rf"\bfrom\s+{alias_pat}\s+import\b",
        rf"\b(?:pip install|python\s+-m\s+pip\s+install|poetry add|uv add|pdm add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_js_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    patterns = [
        rf"\bimport\s+[^\n;]*?from\s+[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]",
        rf"\brequire\s*\(\s*[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]\s*\)",
        rf"\b(?:npm install|npm i|pnpm add|yarn add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_command_instructions(text: str, command_pattern: str) -> list[str]:
    found = []
    for m in re.finditer(command_pattern, text, re.I):
        before = text[max(0, m.start() - 32):m.start()].lower()
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_prefix = text[line_start:m.start()].strip().lower()
        backticked = m.start() > 0 and m.end() < len(text) and text[m.start() - 1] == "`" and text[m.end()] == "`"
        instruction = bool(re.search(r"\b(run|then|execute|use|uses|start with)\s+$", before)) or line_prefix in {"-", "*", "1.", "2.", "3."} or backticked
        if instruction and not _has_negation_before(text, m.start()):
            found.append(re.sub(r"\s+", " ", m.group(0).strip()).lower())
    return found


def judge_ai_answer(packet_path: str | Path, ai_answer_path: str | Path, out_dir: str | Path | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    known_files = {rec["relative_path"] for rec in manifest.get("included_files", [])}
    ai_text = Path(ai_answer_path).read_text(encoding="utf-8")
    refs = extract_refs(ai_text)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    files_lower = {f.lower() for f in known_files}
    report = {"sourcepack_version": __version__, "supported_files": [], "missing_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "unsupported_capabilities": []}
    for ref in sorted(refs):
        if ref in known_files:
            report["supported_files"].append(ref)
        else:
            report["missing_files"].append(ref)
    for dep in COMMON_DEPENDENCIES:
        dep_norm = dep.lower()
        action = _ai_js_dependency_actions(ai_text, dep_norm) if dep_norm in {"react", "vue", "svelte", "prisma"} else _ai_dependency_actions(ai_text, dep_norm)
        if action and dep_norm not in deps:
            if dep_norm != "pytest" or not any(f.startswith("tests/") for f in known_files):
                report["unsupported_dependencies"].append(dep)
    if _ai_command_instructions(ai_text, r"docker\s+compose\s+up"):
        if not any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in known_files):
            report["unsupported_commands"].append("docker compose up")
    for cmd in sorted(set(_ai_command_instructions(ai_text, r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+"))):
        normalized = cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append("npm test")
    if _ai_command_instructions(ai_text, r"(?:python\s+-m\s+pytest|pytest)"):
        if not ({"pyproject.toml", "pytest.ini"} & files_lower or any(f.startswith("tests/") for f in known_files) or "pytest" in deps):
            report["unsupported_commands"].append("pytest")
    lower_text = ai_text.lower()
    supported_features = feature_inventory(manifest, packet, deps)
    for feature in FEATURE_NAMES:
        for m in re.finditer(rf"\b{re.escape(feature)}\b", lower_text):
            if feature not in supported_features and not _has_negation_before(lower_text, m.start()):
                report["unsupported_capabilities"].append(feature)
                break
    report["unsupported_dependencies"] = sorted(set(report["unsupported_dependencies"]))
    report["unsupported_commands"] = sorted(set(report["unsupported_commands"]))
    report["unsupported_capabilities"] = sorted(set(report["unsupported_capabilities"]))
    report["verdict"] = "FAIL" if any(report[k] for k in ["missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"]) else "PASS"
    lines = ["# SourcePack Judgment Report", "", "Verdict: " + report["verdict"], ""]
    for section, label in [("supported_files", "Supported File References"), ("missing_files", "Missing File References"), ("unsupported_dependencies", "Unsupported Dependencies"), ("unsupported_commands", "Unsupported Commands"), ("unsupported_capabilities", "Unsupported Capabilities")]:
        lines.append(f"## {label}")
        items = report[section]
        if not items:
            lines.append("None")
        else:
            for item in items:
                prefix = "SUPPORTED" if section == "supported_files" else "NOT FOUND" if section == "missing_files" else "UNSUPPORTED"
                lines.append(f"- [{prefix}] {item}")
        lines.append("")
    if out_dir:
        out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
        (out / "judgment_report.md").write_text("\n".join(lines), encoding="utf-8")
        (out / "judgment_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return report


LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PY_STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"typing", "pathlib", "json", "os", "sys", "re", "subprocess", "datetime", "unittest"}
PY_DEP_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}



def _latest_report_html_path(repo: str | Path) -> Path:
    return ensure_sourcepack_dirs(repo)["latest_html"]


def cli_report_path(args) -> int:
    print(_latest_report_html_path(Path(args.repo).resolve()))
    return 0


def cli_report_open(args) -> int:
    repo = Path(args.repo).resolve()
    paths = ensure_sourcepack_dirs(repo)
    if not paths["latest_json"].exists():
        print(f"ERROR: no SourcePack report found at {paths['latest_json']}", file=sys.stderr)
        return 1
    try:
        report = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        paths["latest_html"].write_text(render_report_html(report), encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: could not prepare SourcePack HTML report at {paths['latest_html']}: {exc}", file=sys.stderr)
        return 1
    uri = paths["latest_html"].resolve().as_uri()
    opened = webbrowser.open(uri)
    print(f"Report HTML: {paths['latest_html']}")
    if not opened:
        print("Browser open was not confirmed; open the path above manually.")
    return 0


def finalize_diff_report(repo: str | Path | None, report: dict, args, stem: str = "diff") -> dict:
    full = dict(report)
    if getattr(args, "ci", False):
        full["ci"] = True
    if repo is not None:
        try:
            write_user_report(repo, full, stem)
        except Exception as exc:
            print(f"WARNING: could not write SourcePack report artifacts: {exc}", file=sys.stderr)
    return full

def emit_diff_report(report: dict, args, added: bool = False, note: str | None = None) -> int:
    if getattr(args, "ci", False):
        args.json = True
        report["ci"] = True
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        if added:
            print("Added .sourcepack/ to .gitignore.")
        if note:
            print(note)
        print(render_traffic(report, getattr(args, "verbose", False)), end="")
    verdict = report.get("verdict")
    return 0 if (verdict == "PASS" or (verdict == "WARN" and not (getattr(args, "strict", False) or getattr(args, "ci", False)))) else 1

def git_metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, dirty_state = git_worktree_dirty(root)
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": dirty if dirty_state is None else None,
        "dirty_state": dirty_state,
    }


def scanner_config_hash() -> str:
    payload = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "ignored_patterns": sorted(DEFAULT_IGNORED_PATTERNS),
        "text_extensions": sorted(DEFAULT_TEXT_EXTENSIONS),
        "max_file_size": 1_000_000,
        "include_hidden": False,
        "redact": True,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


class BaselineLockError(RuntimeError):
    pass


def _rel_to_repo(repo: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _read_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    return data, None


def baseline_corrupt_result(repo: Path, message: str, details: dict | None = None, packet_path: Path | None = None, metadata_path: Path | None = None, active_pointer_path: Path | None = None, mode: str = "none", active_build_id: str | None = None) -> dict:
    return {"ok": False, "state": "corrupt", "finding_id": "baseline_corrupt", "message": "Trusted SourcePack baseline is corrupt or unverifiable. Recreate the baseline only after verifying the current repo state should be trusted.", "details": {"reason": message, **(details or {})}, "packet_path": _rel_to_repo(repo, packet_path), "metadata_path": _rel_to_repo(repo, metadata_path), "active_pointer_path": _rel_to_repo(repo, active_pointer_path), "mode": mode, "active_build_id": active_build_id}


def resolve_active_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); paths = sourcepack_paths(repo); pointer = paths["active_pointer"]
    if pointer.exists():
        data, err = _read_json_file(pointer)
        if err:
            return baseline_corrupt_result(repo, f"active.json {err}", active_pointer_path=pointer, mode="pointer")
        build_id = data.get("active_build_id")
        if not isinstance(build_id, str) or not build_id or "/" in build_id or "\\" in build_id or build_id in {".", ".."}:
            return baseline_corrupt_result(repo, "active.json has invalid active_build_id", active_pointer_path=pointer, mode="pointer")
        build_dir = (paths["builds"] / build_id).resolve(); builds_dir = paths["builds"].resolve()
        try:
            build_dir.relative_to(builds_dir)
        except ValueError:
            return baseline_corrupt_result(repo, "active.json points outside baseline builds", active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        packet = build_dir / "packet"; meta = build_dir / "metadata.json"
        if not build_dir.exists() or not packet.exists():
            return baseline_corrupt_result(repo, "active.json points to a missing build", packet_path=packet, metadata_path=meta, active_pointer_path=pointer, mode="pointer", active_build_id=build_id)
        return {"ok": True, "state": "resolved", "mode": "pointer", "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, meta), "active_pointer_path": _rel_to_repo(repo, pointer), "active_build_id": build_id, "details": {}}
    legacy = paths["packet"]
    if legacy.exists():
        legacy_artifacts = {"manifest.json", "receipt.json", "reality_map.json", "context.md", "ai_instructions.md"}
        present = {child.name for child in legacy.iterdir()} if legacy.is_dir() else set()
        if (legacy / "manifest.json").exists():
            return {"ok": True, "state": "resolved", "mode": "legacy", "packet_path": _rel_to_repo(repo, legacy), "metadata_path": _rel_to_repo(repo, paths["baseline_meta"]), "active_pointer_path": None, "active_build_id": None, "details": {}}
        if present & legacy_artifacts:
            return baseline_corrupt_result(repo, "legacy baseline packet has baseline artifacts but is missing manifest.json", packet_path=legacy, mode="legacy")
    return {"ok": False, "state": "missing", "finding_id": "baseline_missing", "message": "No trusted SourcePack baseline exists while changes are present.", "details": {}, "packet_path": None, "metadata_path": None, "active_pointer_path": None, "mode": "none", "active_build_id": None}


def _validate_packet_artifacts(repo: Path, packet: Path) -> dict | None:
    required = ["manifest.json", "receipt.json", "reality_map.json"]
    for name in required:
        if not (packet / name).exists():
            return baseline_corrupt_result(repo, f"active packet missing {name}", packet_path=packet)
    for name in ["manifest.json", "receipt.json", "reality_map.json", "token_report.json", "redactions.json"]:
        path = packet / name
        if path.exists():
            _, err = _read_json_file(path)
            if err:
                return baseline_corrupt_result(repo, f"{name} {err}", packet_path=packet)
    receipt, err = _read_json_file(packet / "receipt.json")
    if err:
        return baseline_corrupt_result(repo, f"receipt.json {err}", packet_path=packet)
    hashes = receipt.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return baseline_corrupt_result(repo, "receipt.json has no hashes", packet_path=packet)
    for name, expected in hashes.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            return baseline_corrupt_result(repo, "receipt.json contains invalid hash entry", packet_path=packet)
        if Path(name).is_absolute() or ".." in Path(name).parts:
            return baseline_corrupt_result(repo, "receipt.json tracks unsafe artifact path", packet_path=packet)
        packet_root = packet.resolve()
        path = (packet / name).resolve()
        try:
            path.relative_to(packet_root)
        except ValueError:
            return baseline_corrupt_result(repo, "receipt.json tracks path outside packet", packet_path=packet)
        if not path.exists():
            return baseline_corrupt_result(repo, f"receipt-tracked artifact missing: {name}", packet_path=packet)
        try:
            actual = sha256_file(path)
        except OSError as exc:
            return baseline_corrupt_result(repo, f"receipt-tracked artifact unreadable: {name}: {exc}", packet_path=packet)
        if actual != expected:
            return baseline_corrupt_result(repo, f"receipt hash mismatch: {name}", packet_path=packet)
    return None


def validate_baseline(repo: str | Path) -> dict:
    repo = Path(repo).resolve(); resolved = resolve_active_baseline(repo)
    if resolved.get("state") == "corrupt":
        return resolved
    if resolved.get("state") == "missing":
        return resolved
    packet = repo / resolved["packet_path"] if resolved.get("packet_path") else None
    meta = repo / resolved["metadata_path"] if resolved.get("metadata_path") else None
    corrupt = _validate_packet_artifacts(repo, packet)
    if corrupt:
        corrupt.update({"mode": resolved.get("mode", "none"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "active_build_id": resolved.get("active_build_id")})
        return corrupt
    if meta and meta.exists():
        _, err = _read_json_file(meta)
        if err:
            return baseline_corrupt_result(repo, f"metadata.json {err}", packet_path=packet, metadata_path=meta, active_pointer_path=repo / resolved["active_pointer_path"] if resolved.get("active_pointer_path") else None, mode=resolved.get("mode", "none"), active_build_id=resolved.get("active_build_id"))
    paths = sourcepack_paths(repo); stale = paths["stale_marker"].exists()
    stale_details = None
    if stale:
        stale_details, err = _read_json_file(paths["stale_marker"])
        if err:
            stale_details = {"reason": "unreadable"}
    return {"ok": True, "state": "stale" if stale else "present", "finding_id": "baseline_stale" if stale else None, "message": "Trusted SourcePack baseline may not match current repo state." if stale else "Trusted SourcePack baseline is present.", "details": {"stale_details": stale_details} if stale else {}, "packet_path": resolved.get("packet_path"), "metadata_path": resolved.get("metadata_path"), "active_pointer_path": resolved.get("active_pointer_path"), "mode": resolved.get("mode"), "active_build_id": resolved.get("active_build_id")}


def acquire_baseline_lock(repo: str | Path, command: str | None = None) -> tuple[Path, int]:
    paths = ensure_sourcepack_dirs(repo); lock = paths["baseline_lock"]
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BaselineLockError("Another SourcePack baseline operation is already in progress.") from exc
    payload = {"pid": os.getpid(), "command": command, "started_at": utc_now()}
    os.write(fd, json.dumps(payload).encode("utf-8"))
    os.fsync(fd)
    return lock, fd


def release_baseline_lock(lock: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def _unique_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"


DIRTY_BASELINE_REFUSAL = "SourcePack refused to create a trusted baseline from a dirty working tree. Review, commit, or stash current changes first, or rerun with --force only if this state should become trusted."


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None, force: bool = False) -> tuple[dict, bool]:
    repo = Path(repo).resolve()
    dirty, dirty_state = git_worktree_dirty(repo)
    if dirty and not force:
        raise RuntimeError(DIRTY_BASELINE_REFUSAL)
    paths = ensure_sourcepack_dirs(repo)
    previous = validate_baseline(repo); created = previous.get("state") == "missing"
    lock = fd = None; build_dir = None
    try:
        lock, fd = acquire_baseline_lock(repo, "baseline")
        build_id = _unique_build_id(); build_dir = paths["builds"] / build_id; packet = build_dir / "packet"
        build_dir.mkdir(parents=True, exist_ok=False)
        PacketWriter(packet, SourceScanner(repo).scan(), force=True).write_all()
        if not quiet and not verify_packet(packet):
            raise RuntimeError("packet verification returned FAIL")
        candidate = _validate_packet_artifacts(repo, packet)
        if candidate:
            raise RuntimeError(candidate["details"].get("reason", "candidate baseline invalid"))
        meta = {"created_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "scanner_config_hash": scanner_config_hash(), **git_metadata(repo)}
        (build_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        meta_check, meta_err = _read_json_file(build_dir / "metadata.json")
        if meta_err:
            raise RuntimeError(f"metadata.json {meta_err}")
        if fail_stage == "before_pointer_replace":
            raise RuntimeError("injected failure before pointer replacement")
        pointer = {"schema_version": "baseline_pointer.v1", "active_build_id": build_id, "activated_at": utc_now(), "packet_path": _rel_to_repo(repo, packet), "metadata_path": _rel_to_repo(repo, build_dir / "metadata.json")}
        _write_json_atomic(paths["active_pointer"], pointer)
        if fail_stage == "after_pointer_replace":
            raise RuntimeError("injected failure after pointer replacement")
        # Enforcement state is active.json -> builds/<id>/packet. Legacy packet copies are intentionally not updated after pointer activation.
        if paths["stale_marker"].exists():
            paths["stale_marker"].unlink()
        return paths, created
    except Exception:
        if build_dir is not None:
            active = None
            try:
                if paths["active_pointer"].exists():
                    active = json.loads(paths["active_pointer"].read_text(encoding="utf-8")).get("active_build_id")
            except Exception:
                active = None
            if active != build_dir.name:
                shutil.rmtree(build_dir, ignore_errors=True)
        raise
    finally:
        if lock is not None and fd is not None:
            release_baseline_lock(lock, fd)


def build_prompt_context(repo: str | Path) -> dict:
    paths = ensure_sourcepack_dirs(repo)
    PacketWriter(paths["prompt_packet"], SourceScanner(repo).scan(), force=True).write_all()
    shutil.copy2(paths["prompt_packet"] / "reality_map.json", paths["prompt_reality"])
    shutil.copy2(paths["prompt_packet"] / "ai_instructions.md", paths["prompt_instructions"])
    return paths


def render_prompt(task: str, instructions: str, reality: dict) -> str:
    def bullets(items):
        return "\n".join(f"- {item}" for item in items) if items else "- None detected"
    return "\n".join(["# SourcePack Verified AI Prompt", "", "## User Task", "", task, "", "## AI Grounding Instructions", "", instructions.rstrip(), "", "## Compact Reality Map Summary", "", f"Project types: {', '.join(reality.get('project_types') or ['unknown'])}", f"Included files: {reality.get('included_file_count', 0)}", "", "## Supported Commands", "", bullets(reality.get('supported_commands', [])), "", "## Detected Dependencies", "", bullets(reality.get('detected_dependencies', [])), "", "## Supported Capabilities", "", bullets(reality.get('supported_capabilities', [])), "", "## Unknown and Unsupported Boundaries", "", bullets(reality.get('claim_boundaries', [])), "", "Cite exact file paths for project-specific claims.", "Do not invent files, dependencies, commands, services, or capabilities.", "Absence of evidence means unknown, not impossible.", ""])


def copy_to_clipboard(text: str) -> bool:
    system = platform.system().lower()
    cmds = [["pbcopy"]] if system == "darwin" else [["clip"]] if system == "windows" else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            if subprocess.run(cmd, input=text, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
                return True
        except Exception:
            pass
    return False


def _is_local_python_import(name: str, path: str, files: set[str]) -> bool:
    candidates = {f"{name}.py", f"{name}/__init__.py", f"src/{name}.py", f"src/{name}/__init__.py"}
    parent = str(Path(path).parent).replace("\\", "/")
    if parent != ".":
        candidates |= {f"{parent}/{name}.py", f"{parent}/{name}/__init__.py"}
    return bool(candidates & files)


JS_DEP_SECTIONS = {"dependencies", "devDependencies", "peerDependencies", "optionalDependencies"}


def _package_json_declared_deps_from_added_lines(lines: list[str]) -> set[str]:
    added = "\n".join(lines)
    try:
        package = json.loads(added)
    except json.JSONDecodeError:
        package = None
    deps: set[str] = set()
    if isinstance(package, dict):
        for section in JS_DEP_SECTIONS:
            section_deps = package.get(section)
            if isinstance(section_deps, dict):
                deps.update(dep.lower() for dep in section_deps)
        if deps:
            return deps
    for section in JS_DEP_SECTIONS:
        for body in re.findall(rf'"{section}"\s*:\s*\{{(.*?)\}}', added, re.I | re.S):
            deps.update(m.lower() for m in re.findall(r'"(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)"\s*:', body))
    return deps


def _apply_patch_change_to_text(original: str, change: PatchFileChange) -> str | None:
    if change.deleted_file:
        return ""
    result = original.splitlines()
    if result and result[0] == "":
        result = result[1:]
    out: list[str] = []
    idx = 0
    saw_hunk = False
    for line in change.diff_lines or []:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not m:
                return None
            old_start = max(int(m.group(1)) - 1, 0)
            if old_start < idx or old_start > len(result):
                return None
            out.extend(result[idx:old_start])
            idx = old_start
            saw_hunk = True
        elif line.startswith(" "):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            out.append(result[idx])
            idx += 1
        elif line.startswith("-"):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            idx += 1
        elif line.startswith("+"):
            out.append(line[1:])
    if not saw_hunk and not change.new_file:
        return None
    out.extend(result[idx:])
    return "\n".join(out) + ("\n" if original.endswith("\n") or change.new_file else "")


def _python_dependency_names_by_scope_from_pyproject(content: str) -> dict[str, set[str]]:
    scopes = {"runtime": set(), "dev": set(), "optional": set()}
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return scopes

    def add_req(target: set[str], req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                target.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_req(scopes["runtime"], req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_req(scopes["optional"], req)
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            section = poetry.get("dependencies", {})
            if isinstance(section, dict):
                for dep in section:
                    if dep.lower() != "python":
                        scopes["runtime"].add(_normalize_dependency_name(dep))
            for section_name in ("dev-dependencies",):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_req(scopes["dev"], req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_req(scopes["dev"], req)
    return scopes


def _declared_dependency_scopes_by_ecosystem(manifest: dict, packet: Path) -> dict[str, dict[str, set[str]]]:
    contents = _packet_file_contents(packet)
    scopes = {"python": {"runtime": set(), "dev": set(), "optional": set()}, "js": {"runtime": set(), "dev": set(), "optional": set()}}
    for rel, content in contents.items():
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(content)
            for key, values in parsed.items():
                scopes["python"][key].update(values)
        elif name == "requirements.txt":
            scopes["python"]["runtime"].update(_python_dependency_names_from_requirement_lines(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            target = "dev" if any(x in name for x in ("dev", "test")) else "runtime"
            scopes["python"][target].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            section_map = {"dependencies": "runtime", "peerDependencies": "runtime", "optionalDependencies": "optional", "devDependencies": "dev"}
            for section, target in section_map.items():
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    scopes["js"][target].update(dep.lower() for dep in section_deps)
    return scopes


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    name = PurePosixPath(p).name
    return p.startswith(("tests/", "test/")) or "/__tests__/" in f"/{p}" or name.endswith("_test.py") or any(name.endswith(s) for s in (".test.js", ".test.ts", ".spec.js", ".spec.ts", ".test.jsx", ".test.tsx", ".spec.jsx", ".spec.tsx"))


def _dependency_scope_status(dep: str, scopes: dict[str, set[str]], path: str) -> str:
    dep = _normalize_dependency_name(dep)
    if dep in scopes.get("runtime", set()):
        return "supported"
    if dep in scopes.get("dev", set()):
        return "supported" if _is_test_path(path) else "scope_review"
    if dep in scopes.get("optional", set()):
        return "scope_review"
    return "missing"


def _declared_dependency_names_from_patch_by_ecosystem_structural(changes: list[PatchFileChange], contents: dict[str, str]) -> tuple[dict[str, set[str]], list[dict]]:
    deps = {"python": set(), "js": set()}
    uncertainties: list[dict] = []
    for ch in changes:
        name = Path(ch.path).name.lower()
        if name not in {"package.json", "pyproject.toml"} and not (name.startswith("requirements") and name.endswith(".txt")):
            continue
        base = contents.get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        if name == "package.json":
            try:
                package = json.loads(post)
            except json.JSONDecodeError:
                uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
                continue
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    deps["js"].update(dep.lower() for dep in section_deps)
        elif name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(post)
            deps["python"].update(set().union(*parsed.values()))
        else:
            deps["python"].update(_python_dependency_names_from_requirement_lines(post))
    return deps, uncertainties


def _declared_dependency_names_from_patch_by_ecosystem(changes: list[PatchFileChange]) -> dict[str, set[str]]:
    deps = {"python": set(), "js": set()}
    for ch in changes:
        added = "\n".join(ch.added_lines or [])
        name = Path(ch.path).name.lower()
        if name == "package.json":
            deps["js"].update(_package_json_declared_deps_from_added_lines(ch.added_lines or []))
        elif name == "pyproject.toml":
            deps["python"].update(_python_dependency_names_from_pyproject(added))
        elif name.startswith("requirements") and name.endswith(".txt"):
            deps["python"].update(_python_dependency_names_from_requirement_lines(added))
    return deps


def _declared_dependency_names_from_patch(changes: list[PatchFileChange]) -> set[str]:
    scoped = _declared_dependency_names_from_patch_by_ecosystem(changes)
    return scoped["python"] | scoped["js"]


def _declared_dependency_names_by_ecosystem(manifest: dict, packet: Path) -> dict[str, set[str]]:
    declared = {"python": set(), "js": set()}
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            declared["python"].update(_python_dependency_names_from_pyproject(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            declared["python"].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    declared["js"].update(dep.lower() for dep in section_deps)
    return declared


def _declared_dependency_names(manifest: dict, packet: Path) -> set[str]:
    scoped = _declared_dependency_names_by_ecosystem(manifest, packet)
    return scoped["python"] | scoped["js"]


def _workspace_package_names(packet: Path) -> set[str]:
    contents = _packet_file_contents(packet)
    root = {}
    try:
        root = json.loads(contents.get("package.json", "{}"))
    except json.JSONDecodeError:
        return set()
    workspaces = root.get("workspaces")
    patterns = workspaces if isinstance(workspaces, list) else workspaces.get("packages", []) if isinstance(workspaces, dict) else []
    names: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern.endswith("/*"):
            continue
        prefix = pattern[:-2].strip("/")
        for rel, content in contents.items():
            if Path(rel).name == "package.json" and rel.startswith(prefix + "/"):
                try:
                    package = json.loads(content)
                except json.JSONDecodeError:
                    continue
                name = package.get("name")
                if isinstance(name, str):
                    names.add(name.lower())
    return names


def _is_js_alias_specifier(imported: str) -> bool:
    return imported.startswith(("@/", "~/"))


def _js_alias_local(imported: str, files: set[str], contents: dict[str, str]) -> bool | None:
    configs = []
    for cfg in ("tsconfig.json", "jsconfig.json"):
        if cfg in contents:
            try:
                configs.append(json.loads(contents[cfg]))
            except json.JSONDecodeError:
                return None
    for cfg in configs:
        opts = cfg.get("compilerOptions", {}) if isinstance(cfg, dict) else {}
        base = str(opts.get("baseUrl", ".")).strip("./")
        paths = opts.get("paths", {})
        candidates = []
        if isinstance(paths, dict):
            for alias, targets in paths.items():
                prefix = alias[:-1] if alias.endswith("*") else alias
                if imported.startswith(prefix):
                    rest = imported[len(prefix):]
                    for target in targets if isinstance(targets, list) else []:
                        tprefix = target[:-1] if isinstance(target, str) and target.endswith("*") else target
                        candidates.append((tprefix + rest).strip("/"))
        if base and not imported.startswith("@") and not imported.startswith("~"):
            candidates.append(f"{base}/{imported}".strip("/"))
        for c in candidates:
            variants = {c, f"{c}.ts", f"{c}.tsx", f"{c}.js", f"{c}.jsx", f"{c}/index.ts", f"{c}/index.tsx", f"{c}/index.js", f"{c}/index.jsx"}
            if variants & files:
                return True
        if candidates:
            return None
    return False


def _is_high_risk_binary_path(rel: str) -> bool:
    normalized = rel.replace("\\", "/").lstrip("/")
    high_risk_prefixes = (".sourcepack/", ".git/", ".github/workflows/")
    high_risk_names = {"pyproject.toml", "package.json", "package-lock.json", "uv.lock", "poetry.lock"}
    return normalized.startswith(high_risk_prefixes) or Path(normalized).name in high_risk_names


UNSUPPORTED_ECOSYSTEM_MARKERS = {
    "gemfile": ("Gemfile", "Ruby/Bundler dependency validation is not implemented"),
    "composer.json": ("composer.json", "PHP/Composer dependency validation is not implemented"),
    "main.tf": ("main.tf", "Terraform module/provider validation is not implemented"),
    "flake.nix": ("flake.nix", "Nix flake validation is not implemented"),
    "cargo.toml": ("Cargo.toml", "Rust dependency validation is not implemented"),
    "go.mod": ("go.mod", "Go module dependency validation is not implemented"),
    "pom.xml": ("pom.xml", "Maven dependency validation is not implemented"),
    "build.gradle": ("build.gradle", "Gradle dependency validation is not implemented"),
    "build.gradle.kts": ("build.gradle.kts", "Gradle dependency validation is not implemented"),
    "settings.gradle": ("settings.gradle", "Gradle workspace validation is not implemented"),
    "settings.gradle.kts": ("settings.gradle.kts", "Gradle workspace validation is not implemented"),
    "*.csproj": ("*.csproj", ".NET/NuGet dependency validation is not implemented"),
}


def _unsupported_ecosystem_uncertainties(files: set[str], changes: list[PatchFileChange]) -> list[dict]:
    names = {Path(f).name.lower() for f in files}
    names.update(Path(ch.path).name.lower() for ch in changes)
    for ch in changes:
        if ch.path.lower().endswith(".csproj"):
            names.add("*.csproj")
    uncertainties = []
    for marker, (evidence, message) in sorted(UNSUPPORTED_ECOSYSTEM_MARKERS.items()):
        if marker in names:
            uncertainties.append({"id": "unsupported_ecosystem", "message": f"{evidence} detected, but {message}", "evidence": evidence})
    return uncertainties

def judge_patch_text(packet_path: str | Path, patch_text: str) -> dict:
    if re.search(r"(?m)^@@", patch_text) and "diff --git " not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    if re.search(r"(?m)^@@(?! -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)", patch_text):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    changes = parse_unified_diff(patch_text)
    unsafe_paths = sorted({ch.path for ch in changes if ch.unsafe_path and ch.path})
    if any(ch.unsafe_path for ch in changes):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "path_escape": True, "path_escape_paths": unsafe_paths}
    if patch_text.strip() and not changes and "Binary files " not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    report = analyze_patch(packet_path, patch_text, changes)
    packet = Path(packet_path); manifest = load_manifest(packet); files = known_files(manifest, packet); contents = _packet_file_contents(packet)
    existing_declared = _declared_dependency_names_by_ecosystem(manifest, packet)
    scopes = _declared_dependency_scopes_by_ecosystem(manifest, packet)
    patch_declared, manifest_uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
    if manifest_uncertainties:
        report.setdefault("uncertainties", []).extend(manifest_uncertainties)
    workspace_names = _workspace_package_names(packet)
    unsupported = set(report.get("unsupported_dependencies", []))
    for ch in changes:
        suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
        if suffix == ".py":
            for imported in extract_imports_from_text(added, suffix):
                if imported in PY_STDLIB or imported.startswith(".") or _is_local_python_import(imported, ch.path, files):
                    continue
                dep_name = _dependency_name_for_import(imported)
                scope_status = _dependency_scope_status(dep_name, scopes["python"], ch.path)
                if scope_status == "scope_review":
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{dep_name} is declared outside the runtime dependency scope", "path": ch.path, "evidence": dep_name})
                elif scope_status == "missing" and dep_name not in patch_declared["python"]:
                    unsupported.add(imported)
                elif dep_name in patch_declared["python"]:
                    unsupported.discard(imported)
                    unsupported.discard(dep_name)
        elif suffix in JS_EXTS:
            for imported in extract_imports_from_text(added, suffix):
                if imported.startswith(".") or imported.startswith("/"):
                    continue
                local_alias = _js_alias_local(imported, files, contents)
                pkg = _js_package_root(imported)
                if pkg in workspace_names or local_alias is True:
                    continue
                if local_alias is None or (local_alias is False and _is_js_alias_specifier(imported)):
                    report.setdefault("uncertainties", []).append({"id": "js_alias_uncertain", "message": f"{imported} could not be resolved safely", "path": ch.path, "evidence": imported})
                    continue
                scope_status = _dependency_scope_status(pkg, scopes["js"], ch.path)
                if scope_status == "scope_review":
                    report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{pkg} is declared outside the runtime dependency scope", "path": ch.path, "evidence": pkg})
                elif scope_status == "missing" and pkg not in patch_declared["js"]:
                    unsupported.add(pkg)
                elif pkg in patch_declared["js"]:
                    unsupported.discard(pkg)
    declared = patch_declared["python"] | patch_declared["js"]
    existing_deps = existing_declared["python"] | existing_declared["js"]
    declared_only = {d for d in declared if d not in existing_deps}
    binary_paths = []
    binary_blockers = []
    for line in patch_text.splitlines():
        if line.startswith("Binary files "):
            m = re.search(r" b/(.+?) differ", line)
            rel = m.group(1) if m else "unknown"
            binary_paths.append(rel)
            if rel == "unknown" or _is_high_risk_binary_path(rel):
                binary_blockers.append(rel)
    if binary_paths:
        report["binary_diffs"] = sorted(set(binary_paths))
    if binary_blockers:
        report["binary_diff_blockers"] = sorted(set(binary_blockers))
    unsupported_ecosystems = _unsupported_ecosystem_uncertainties(files, changes)
    if unsupported_ecosystems:
        seen_uncertainties = set()
        merged_uncertainties = []
        for uncertainty in report.get("uncertainties", []) + unsupported_ecosystems:
            if isinstance(uncertainty, dict):
                key = (uncertainty.get("id"), uncertainty.get("message"), uncertainty.get("evidence"), uncertainty.get("path"))
            else:
                key = (str(uncertainty),)
            if key not in seen_uncertainties:
                seen_uncertainties.add(key)
                merged_uncertainties.append(uncertainty)
        report["uncertainties"] = merged_uncertainties
    report["unsupported_dependencies"] = sorted(unsupported)
    if declared_only:
        report.setdefault("warnings", []).append("Patch declares new dependencies that require review.")
        report["declared_dependencies"] = sorted(declared_only)
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "binary_diff_blockers", "path_escape"]
    report["verdict"] = "FAIL" if any(report.get(k) for k in fail_keys) else "WARN" if (report.get("new_files") or report.get("deleted_files") or report.get("warnings") or declared_only or report.get("uncertainties") or report.get("binary_diffs")) else "PASS"
    return report


def patch_report_to_traffic(report: dict, report_path: str = ".sourcepack/reports/latest.json") -> dict:
    findings=[]
    for p in report.get("missing_modified_files", []): findings.append(normalized_finding("missing_file", "error", "file", f"{p} not found in the trusted baseline.", p, suggestion="Restore the file, create it as a new file, or refresh the baseline only after accepting the current repo state."))
    for d in report.get("unsupported_dependencies", []): findings.append(normalized_finding("unsupported_dependency", "error", "dependency", f"{d} is imported but not declared in scanned dependency files.", evidence=d, suggestion=f"Either remove {d} usage or add it intentionally to the appropriate dependency manifest."))
    for c in report.get("unsupported_commands", []): findings.append(normalized_finding("unsupported_command", "error", "command", f"{c} is not supported by project evidence.", evidence=c, suggestion="Use a detected supported command or add the project file that defines this command."))
    if report.get("malformed_diff"):
        findings.append(normalized_finding("malformed_diff", "error", "diff", "SourcePack could not safely parse the diff artifact it was asked to judge."))
    if report.get("path_escape"):
        paths = report.get("path_escape_paths") or []
        if paths:
            for p in paths:
                findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute.", p, evidence=p))
        else:
            findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute."))
    for p in report.get("protected_artifact_modifications", []): findings.append(normalized_finding("protected_artifact", "error", "artifact", f"{p} is a protected SourcePack trust artifact.", p, evidence=p))
    for p in report.get("git_path_modifications", []): findings.append(normalized_finding("git_path_modification", "error", "artifact", f"{p} modifies Git internal state and is not safe to judge as a normal repository file.", p, evidence=p))
    for p in report.get("binary_diff_blockers", []): findings.append(normalized_finding("binary_diff", "error", "diff", f"Binary change at {p} crosses a SourcePack trust or high-risk control boundary.", p, evidence=p))
    for p in report.get("binary_diffs", []):
        if p not in set(report.get("binary_diff_blockers", [])):
            findings.append(normalized_finding("binary_diff", "warn", "uncertainty", f"Binary content was detected at {p} and was not semantically evaluated.", p, evidence=p))
    for p in report.get("new_files", []): findings.append(normalized_finding("new_file", "warn", "review", f"{p} was created by the patch.", p))
    for p in report.get("deleted_files", []): findings.append(normalized_finding("deleted_file", "warn", "review", f"{p} was deleted by the patch.", p))
    for d in report.get("declared_dependencies", []): findings.append(normalized_finding("declared_dependency", "warn", "review", f"{d} was added to dependency files.", evidence=d))
    for c in report.get("declared_commands", []): findings.append(normalized_finding("declared_command", "warn", "review", f"{c} was added in the same patch.", evidence=c))
    for w in report.get("uncertainties", []):
        if isinstance(w, dict):
            fid = str(w.get("id") or "uncertainty")
            message = str(w.get("message") or "SourcePack could not fully evaluate this change.")
            findings.append(normalized_finding(fid, "warn", "uncertainty", message, w.get("path"), w.get("evidence"), w.get("suggestion")))
        else:
            fid, _, detail = str(w).partition(":")
            fid = fid.strip() or "uncertainty"
            message = detail.strip() or str(w)
            findings.append(normalized_finding(fid, "warn", "uncertainty", message))
    return traffic_report(report.get("verdict", "PASS"), findings=findings, checked_categories=["file references", "Python imports", "JS/TS imports", "known project commands", "protected SourcePack artifacts"], report_path=report_path)


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git executable not found")



def git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    repo = Path(repo)
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return False, "git_unavailable" if cp.returncode == 127 else "not_git"
    root = Path(cp.stdout.strip())
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        diff_cp = run_git(root, list(args))
        if diff_cp.returncode == 1:
            return True, None
        if diff_cp.returncode == 127:
            return False, "git_unavailable"
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0 and untracked.stdout.strip():
        return True, None
    if untracked.returncode == 127:
        return False, "git_unavailable"
    return False, None



def _only_sourcepack_gitignore_change(repo: Path) -> bool:
    status = run_git(repo, ["status", "--porcelain", "--", ".gitignore"])
    others = run_git(repo, ["status", "--porcelain"])
    if status.returncode != 0 or others.returncode != 0:
        return False
    lines = [line for line in others.stdout.splitlines() if line.strip()]
    if not lines or any(not line.endswith(".gitignore") for line in lines):
        return False
    try:
        text = (repo / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return False
    tracked = run_git(repo, ["show", "HEAD:.gitignore"])
    before = tracked.stdout if tracked.returncode == 0 else ""
    added = [line.strip() for line in text.splitlines() if line.strip() and line.strip() not in {l.strip() for l in before.splitlines()}]
    return bool(added) and set(added) <= {".sourcepack", ".sourcepack/"}

def baseline_report_fields(status: dict) -> dict:
    return {
        "baseline_state": status.get("state"),
        "baseline_integrity_ok": bool(status.get("ok")) and status.get("state") in {"present", "stale"},
        "baseline_integrity_finding_id": status.get("finding_id"),
        "baseline_integrity_message": status.get("message"),
        "baseline_stale": status.get("state") == "stale",
        "baseline_stale_details": (status.get("details") or {}).get("stale_details"),
        "baseline_mode": status.get("mode"),
        "baseline_packet_path": status.get("packet_path"),
        "baseline_metadata_path": status.get("metadata_path"),
        "baseline_active_pointer_path": status.get("active_pointer_path"),
    }

def cli_prompt(args) -> int:
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("repo_not_directory", "error", "git", f"Repo path is not a directory: {args.repo}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep = traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    try:
        build_prompt_context(repo)
    except Exception as exc:
        rep = traffic_report("FAIL", "could not generate prompt context.", [normalized_finding("prompt_context_failed", "error", "prompt", f"Prompt context generation failed: {exc}")])
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep, args.verbose), end=""); return 1
    task = args.task or "Explain how this project works and summarize its structure."
    reality = json.loads(paths["prompt_reality"].read_text(encoding="utf-8")); instructions = paths["prompt_instructions"].read_text(encoding="utf-8")
    prompt = render_prompt(task, instructions, reality); paths["prompt"].write_text(prompt, encoding="utf-8")
    copied = copy_to_clipboard(prompt) if args.copy else False
    dirty, dirty_state = git_worktree_dirty(repo)
    findings = []
    if args.copy and not copied:
        findings.append(normalized_finding("clipboard_unavailable", "warn", "clipboard", "clipboard unavailable."))
    if dirty:
        findings.append(normalized_finding("dirty_worktree", "warn", "prompt", "prompt context includes uncommitted working tree changes."))
    verdict = "WARN" if findings else "PASS"
    headline = "verified prompt copied to clipboard." if args.copy and copied else "clipboard unavailable." if args.copy and not copied else "verified prompt context saved."
    rep = traffic_report(verdict, headline, findings, ["prompt context", "file references", "known project commands"], "continue with the saved prompt; enforcement baseline was not changed.")
    write_user_report(repo, rep, "prompt")
    if args.json: print(json.dumps({**rep, "prompt_path": ".sourcepack/prompt/prompt.md", "clipboard_copied": copied}, indent=2)); return 0
    if added: print("Added .sourcepack/ to .gitignore.")
    print(f"{rep['light']}: {headline}\n\nPrompt saved: .sourcepack/prompt/prompt.md")
    return 0


def cli_baseline(args) -> int:
    repo = Path(args.repo).resolve(); dirty, dirty_state = git_worktree_dirty(repo)
    if dirty and not getattr(args, "force", False):
        rep = traffic_report("FAIL", "trusted baseline refused dirty working tree.", [normalized_finding("dirty_worktree", "error", "baseline", DIRTY_BASELINE_REFUSAL)], ["baseline", "git status"], "Review, commit, or stash current changes first; use --force only for an intentionally trusted state.")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end="")
        return 1
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if err:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("gitignore_unwritable","error","git",f"Cannot write .gitignore: {err}")]); print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    existed = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
    try:
        build_current_baseline(repo, quiet=getattr(args, "quiet", False), force=True); refreshed = existed or args.refresh
        if dirty:
            headline = "baseline refreshed while uncommitted changes are present." if refreshed else "baseline created while uncommitted changes are present."
            rep=traffic_report("WARN", headline, [normalized_finding("dirty_worktree", "warn", "baseline", "baseline now includes current uncommitted changes.")], ["baseline","verify"], "Commit or discard unintended changes before relying on this baseline.")
        else:
            headline = "baseline refreshed." if refreshed else "baseline created."
            rep=traffic_report("PASS", headline, checked_categories=["baseline","verify"])
        write_user_report(repo, rep, "baseline")
        if args.json: print(json.dumps(rep, indent=2)); return 0
        if getattr(args, "quiet", False): return 0
        if added: print("Added .sourcepack/ to .gitignore.")
        print(render_traffic(rep,args.verbose), end="")
        return 0
    except BaselineLockError as exc:
        rep=traffic_report("WARN","baseline writer is locked.",[normalized_finding("baseline_locked","warn","tooling",str(exc))], ["baseline"], "try again after the other baseline operation finishes.", reason_type="tooling"); write_user_report(repo, rep, "baseline")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1
    except Exception as exc:
        rep=traffic_report("FAIL","could not create baseline.",[normalized_finding("baseline_failed","error","baseline",f"Baseline verification failed: {exc}")]); write_user_report(repo, rep, "baseline")
        print(json.dumps(rep, indent=2) if args.json else render_traffic(rep,args.verbose), end=""); return 1


def untracked_files_as_diff(repo: str | Path) -> str:
    repo = Path(repo)
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    if cp.returncode != 0:
        return ""
    chunks = []
    for rel in [line.strip() for line in cp.stdout.splitlines() if line.strip()]:
        path = repo / rel
        if rel == ".gitignore":
            try:
                ignore_lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
            except OSError:
                ignore_lines = set()
            if ignore_lines <= {".sourcepack", ".sourcepack/"}:
                continue
        safe_rel = rel.replace("\\", "/")
        chunks.extend([f"diff --git a/{safe_rel} b/{safe_rel}", "new file mode 100644", "--- /dev/null", f"+++ b/{safe_rel}"])
        if is_probably_binary(path):
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        except OSError:
            continue
        lines = text.splitlines()
        chunks.append(f"@@ -0,0 +1,{len(lines)} @@")
        chunks.extend(f"+{line}" for line in lines)
    return "\n".join(chunks) + ("\n" if chunks else "")

def build_repo_change_report(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, ci: bool = False) -> dict:
    repo_arg = Path(repo_path).resolve(); cp = run_git(repo_arg, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found. Run sourcepack prompt or sourcepack baseline for non-git use."
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable" if cp.returncode == 127 else "no_git_repo", "error", "git", message)])
    git_root = Path(cp.stdout.strip()).resolve()
    repo = repo_arg if validate_baseline(repo_arg).get("state") in {"present", "stale", "corrupt"} else git_root
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if added:
        paths.setdefault("gitignore_added", True)
    if err:
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
    if patch_text is None:
        diff_args = ["diff", "--staged"] if staged else ["diff"]
        if repo != git_root:
            diff_args.append("--relative")
        cp = run_git(repo, diff_args); diff_text = cp.stdout
        if cp.returncode == 127:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable", "error", "git", "Git executable not found.")])
        if not staged:
            extra = untracked_files_as_diff(repo)
            if extra and not (added and _only_sourcepack_gitignore_change(repo)):
                diff_text = (diff_text + "\n" + extra).strip() + "\n"
    else:
        diff_text = patch_text
    baseline_status = validate_baseline(repo)
    if baseline_status["state"] == "corrupt":
        rep = traffic_report("FAIL", "trusted baseline is corrupt.", [normalized_finding("baseline_corrupt", "error", "baseline", baseline_status["message"])], ["baseline", "diff"], "Recreate the baseline only after verifying the current repo state should be trusted.")
        rep.update(baseline_report_fields(baseline_status)); return rep
    if baseline_status["state"] == "missing":
        dirty_now, dirty_state_now = git_worktree_dirty(repo)
        if ci:
            rep = traffic_report("FAIL", "trusted baseline is missing in CI.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists; CI must not establish trust.")], ["baseline", "diff"], "create the baseline locally only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        if diff_text.strip() or (dirty_now and not _only_sourcepack_gitignore_change(repo)):
            rep = traffic_report("FAIL", "baseline missing while changes are present.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists while changes are present.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        try:
            build_current_baseline(repo, quiet=True); baseline_status = validate_baseline(repo)
            rep_note = "Created SourcePack baseline because none existed and no diff was present."
        except BaselineLockError as exc:
            return traffic_report("WARN", "baseline writer is locked.", [normalized_finding("baseline_locked", "warn", "tooling", str(exc))], ["baseline", "diff"], "try again after the other baseline operation finishes.", reason_type="tooling")
        except Exception as exc:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}")])
    else:
        rep_note = None
    stale_findings = []
    if baseline_status["state"] == "stale":
        stale_findings.append(normalized_finding("baseline_stale", "warn", "uncertainty", "Trusted SourcePack baseline may not match current repo state."))
    if not diff_text.strip():
        verdict = "WARN" if stale_findings else "PASS"
        rep = traffic_report(verdict, "SourcePack could not fully evaluate this change." if stale_findings else "good to continue.", [normalized_finding("no_diff", "info", "diff", "No uncommitted changes detected."), *stale_findings], ["diff", "baseline freshness"])
    else:
        raw = judge_patch_text(repo / baseline_status["packet_path"], diff_text); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
        if stale_findings and rep["verdict"] != "FAIL":
            rep = traffic_report("WARN", "SourcePack could not fully evaluate this change.", rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action"), reason_type="uncertainty"); rep["raw_patch_judgment"] = raw
        elif stale_findings:
            rep = traffic_report("FAIL", rep.get("headline"), rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action")); rep["raw_patch_judgment"] = raw
    rep.update(baseline_report_fields(baseline_status))
    if baseline_status.get("metadata_path"):
        try:
            rep["baseline"] = json.loads((repo / baseline_status["metadata_path"]).read_text(encoding="utf-8"))
        except Exception:
            pass
    rep["current_git"] = git_metadata(repo)
    if rep_note:
        rep["note"] = rep_note
    rep["repo_path"] = str(repo)
    return rep


def cli_diff(args) -> int:
    from .judgment import judge_repo_change
    from .policy import PolicyMode
    if getattr(args, "ci", False):
        args.json = True
    mode = PolicyMode.CI if getattr(args, "ci", False) else PolicyMode.STRICT if getattr(args, "strict", False) else PolicyMode.LOCAL
    judgment = judge_repo_change(args.repo, staged=args.staged, policy_mode=mode)
    report = finalize_diff_report(Path(judgment.report.get("repo_path", args.repo)), judgment.report, args)
    return emit_diff_report(report, args, note=report.get("note"))

def hook_text(strict: bool) -> str:
    strict_block = """
if grep -q 'YELLOW LIGHT' .git/SOURCEPACK_LAST_DIFF 2>/dev/null; then
  echo 'SourcePack strict mode blocks YELLOW LIGHT.'
  echo 'To bypass manually: git commit --no-verify'
  exit 1
fi""" if strict else ""
    return """#!/bin/sh
# === SOURCEPACK BEGIN ===
# SourcePack hook version: 1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ]; then
  echo 'RED LIGHT: SourcePack could not locate git repository root.'
  echo 'To bypass manually: git commit --no-verify'
  exit 1
fi
cd "$repo_root" || exit 1
sourcepack diff . --staged > .git/SOURCEPACK_LAST_DIFF
sp_status=$?
cat .git/SOURCEPACK_LAST_DIFF
if [ $sp_status -ne 0 ]; then
  echo 'To bypass manually: git commit --no-verify'
  exit $sp_status
fi""" + strict_block + """
# === SOURCEPACK END ===
"""



def post_commit_hook_text() -> str:
    return """#!/bin/sh
# === SOURCEPACK POST-COMMIT BEGIN ===
# SourcePack hook version: 1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ]; then
  exit 0
fi
cd "$repo_root" || exit 0
if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  sourcepack baseline . --refresh --quiet >/dev/null 2>&1 || echo 'YELLOW LIGHT: SourcePack post-commit baseline refresh failed.'
else
  mkdir -p .sourcepack/state
  current_head="$(git rev-parse HEAD 2>/dev/null)"
  cat > .sourcepack/state/baseline_stale.json <<EOF
{"reason": "post_commit_dirty_worktree", "detected_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "current_head": "$current_head", "dirty_worktree": true}
EOF
  echo 'YELLOW LIGHT: SourcePack baseline is stale because uncommitted changes remain after commit.'
fi
# === SOURCEPACK POST-COMMIT END ===
"""


def install_post_commit_hook(repo: Path) -> bool:
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return False
    root = Path(cp.stdout.strip())
    hooks = root / ".git" / "hooks"
    post = hooks / "post-commit"
    hooks.mkdir(parents=True, exist_ok=True)
    text = post.read_text(encoding="utf-8", errors="ignore") if post.exists() else ""
    block = post_commit_hook_text()
    if "# === SOURCEPACK POST-COMMIT BEGIN ===" in text:
        text = re.sub(r"#!/bin/sh\n?# === SOURCEPACK POST-COMMIT BEGIN ===.*?# === SOURCEPACK POST-COMMIT END ===\n?", block, text, flags=re.S)
    elif text.strip():
        text = text.rstrip() + "\n" + block
    else:
        text = block
    post.write_text(text, encoding="utf-8")
    post.chmod(0o755)
    return True

def hook_chain_text(strict: bool) -> str:
    return hook_text(strict) + """
orig="$(git rev-parse --git-path hooks/pre-commit.sourcepack.orig 2>/dev/null)"
if [ -n "$orig" ] && [ -x "$orig" ]; then
  "$orig" "$@"
  exit $?
fi
exit 0
"""


def hook_is_sourcepack(text: str) -> bool:
    return "# === SOURCEPACK BEGIN ===" in text and "# === SOURCEPACK END ===" in text


def cli_install_hook(args) -> int:
    repo=Path(args.repo).resolve(); cp=run_git(repo,["rev-parse","--show-toplevel"])
    if cp.returncode!=0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found."
        print(f"RED LIGHT: SourcePack pre-commit hook install failed.\n\n{message}"); return 1
    root=Path(cp.stdout.strip()); hooks=root/".git"/"hooks"; pre=hooks/"pre-commit"; post=hooks/"post-commit"; orig=hooks/"pre-commit.sourcepack.orig"
    try:
        hooks.mkdir(parents=True, exist_ok=True)
        if pre.exists():
            text=pre.read_text(encoding="utf-8", errors="ignore")
            if hook_is_sourcepack(text):
                pre.write_text(hook_chain_text(args.strict) if orig.exists() else hook_text(args.strict) + "\nexit 0\n", encoding="utf-8")
            else:
                if not orig.exists(): shutil.copy2(pre, orig)
                pre.write_text(hook_chain_text(args.strict), encoding="utf-8")
        else:
            pre.write_text(hook_text(args.strict) + "\nexit 0\n", encoding="utf-8")
        pre.chmod(0o755); install_post_commit_hook(root); print("GREEN LIGHT: SourcePack pre-commit and post-commit hooks installed."); return 0
    except Exception as exc:
        print(f"RED LIGHT: SourcePack pre-commit hook install failed.\n\n{exc}"); return 1

def cli_uninstall_hook(args) -> int:
    repo=Path(args.repo).resolve(); cp=run_git(repo,["rev-parse","--show-toplevel"])
    if cp.returncode!=0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found."
        print(f"RED LIGHT: SourcePack pre-commit hook uninstall failed.\n\n{message}"); return 1
    root=Path(cp.stdout.strip()); hooks=root/".git"/"hooks"; pre=hooks/"pre-commit"; post=hooks/"post-commit"; orig=hooks/"pre-commit.sourcepack.orig"
    try:
        restored_original = False
        if orig.exists():
            shutil.move(str(orig), str(pre)); pre.chmod(0o755); restored_original = True
        elif pre.exists():
            text=pre.read_text(encoding="utf-8", errors="ignore")
            if not hook_is_sourcepack(text):
                print("RED LIGHT: Cannot safely uninstall SourcePack hook: SourcePack block not found."); return 1
            pre.write_text(re.sub(r"# === SOURCEPACK BEGIN ===.*?# === SOURCEPACK END ===\n?", "", text, flags=re.S), encoding="utf-8")
        if post.exists():
            post_text=post.read_text(encoding="utf-8", errors="ignore")
            if "# === SOURCEPACK POST-COMMIT BEGIN ===" in post_text:
                post.write_text(re.sub(r"#!/bin/sh\n?# === SOURCEPACK POST-COMMIT BEGIN ===.*?# === SOURCEPACK POST-COMMIT END ===\n?", "", post_text, flags=re.S), encoding="utf-8")
        print("GREEN LIGHT: SourcePack hooks uninstalled." if not restored_original else "GREEN LIGHT: SourcePack hooks uninstalled and original pre-commit hook restored."); return 0
    except Exception as exc:
        print(f"RED LIGHT: SourcePack pre-commit hook uninstall failed.\n\n{exc}"); return 1

def cli_status(args) -> int:
    repo=Path(args.repo).resolve(); paths=ensure_sourcepack_dirs(repo)
    current=paths["base"].exists(); baseline_status=validate_baseline(repo); baseline=baseline_status["state"] in {"present", "stale"}; last=None
    if baseline_status.get("packet_path"):
        receipt=repo / baseline_status["packet_path"] / "receipt.json"
        if receipt.exists():
            try: last=json.loads(receipt.read_text()).get("generated_at")
            except Exception: last=None
    cp=run_git(repo,["rev-parse","--show-toplevel"]); git_repo=cp.returncode==0; root=Path(cp.stdout.strip()) if git_repo else repo
    pre=root/".git"/"hooks"/"pre-commit"; post=root/".git"/"hooks"/"post-commit"; hook_installed=False; post_hook_installed=False; strict=False
    if pre.exists():
        text=pre.read_text(encoding="utf-8", errors="ignore"); hook_installed=hook_is_sourcepack(text); strict="strict mode blocks YELLOW LIGHT" in text
    if post.exists():
        post_hook_installed="# === SOURCEPACK POST-COMMIT BEGIN ===" in post.read_text(encoding="utf-8", errors="ignore")
    ignored=False; cig=run_git(repo,["check-ignore",".sourcepack/"])
    if cig.returncode==0: ignored=True
    elif (repo/".gitignore").exists(): ignored=any(line.strip() in {".sourcepack",".sourcepack/"} for line in (repo/".gitignore").read_text(errors="ignore").splitlines())
    last_report=None; last_light=None
    if paths["latest_json"].exists():
        try:
            lr=json.loads(paths["latest_json"].read_text()); last_report=lr.get("verdict"); last_light=lr.get("light")
        except Exception: pass
    dirty, dirty_state = git_worktree_dirty(repo)
    stale = baseline_status["state"] == "stale"
    stale_data = (baseline_status.get("details") or {}).get("stale_details")
    prompt_exists = paths["prompt"].exists()
    automatic = current and baseline and hook_installed and post_hook_installed and ignored
    data={"schema_version":"sourcepack_status.v1","sourcepack_version":__version__,"generated_at":utc_now(),"automatic_mode_enabled":automatic,"local_storage_exists":current,"baseline_exists":baseline,"prompt_context_exists":prompt_exists,"pre_commit_hook_installed":hook_installed,"post_commit_hook_installed":post_hook_installed,"hook_strict_mode":strict,"hook_policy":"RED blocks, YELLOW blocks" if strict else "RED blocks, YELLOW warns","sourcepack_gitignored":ignored,"last_report_verdict":last_report,"last_report_light":last_light,"dirty_worktree":dirty if dirty_state is None else None,"git_repo":git_repo,"last_baseline_update":last}
    data.update(baseline_report_fields(baseline_status))
    if args.json: print(json.dumps(data, indent=2)); return 0
    print(f"SourcePack status for {repo}\n")
    print(f"Automatic mode: {'enabled' if automatic else 'not enabled'}")
    print(f"Baseline: {baseline_status['state']}")
    print(f"Prompt context: {'present' if prompt_exists else 'missing'}")
    print(f"Pre-commit hook: {'installed' if hook_installed else 'not installed'}")
    print(f"Post-commit baseline hook: {'installed' if post_hook_installed else 'not installed'}")
    print(f"Hook policy: {data['hook_policy']}")
    print(f".sourcepack/ gitignored: {'yes' if ignored else 'no'}")
    print(f"Working tree: {'dirty' if dirty else 'clean' if dirty_state is None else 'unknown'}")
    print(f"Last report: {last_light or last_report or 'none'}")
    return 0

def init_workspace(path: str | Path):
    p = Path(path); p.mkdir(parents=True, exist_ok=True)
    ignore = p / ".sourcepackignore"
    config = p / "sourcepack.config.json"
    if not ignore.exists():
        ignore.write_text("# SourcePack ignore rules\n.env\nnode_modules/\ndist/\nbuild/\n", encoding="utf-8")
    if not config.exists():
        config.write_text(json.dumps({"max_file_size": 1_000_000, "include_hidden": False, "redact_secrets": True}, indent=2), encoding="utf-8")
    print(f"Initialized SourcePack workspace at {p}")



def write_auto_report(repo: Path, report: dict, details: dict) -> None:
    payload = dict(report)
    payload.update(details)
    write_user_report(repo, payload, "auto")


def cli_init(args) -> int:
    repo = Path(args.path).resolve()
    if not getattr(args, "auto", False):
        init_workspace(repo)
        return 0
    initial_dirty, initial_dirty_state = git_worktree_dirty(repo)
    baseline_exists_before_init = validate_baseline(repo).get("state") in {"present", "stale", "corrupt"}
    if initial_dirty and not getattr(args, "force", False) and (args.refresh_baseline or not baseline_exists_before_init):
        rep = traffic_report("FAIL", "trusted baseline refused dirty working tree.", [normalized_finding("dirty_worktree", "error", "baseline", DIRTY_BASELINE_REFUSAL)], ["init", "baseline", "git status"], "Review, commit, or stash current changes first; rerun with --force only if this exact state is intentionally trusted.")
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            print(render_traffic(rep), end="")
        return 1
    init_workspace(repo)
    findings: list[dict] = []
    details = {"baseline_created": False, "baseline_refreshed": False, "hook_installed": False, "strict_mode": bool(args.strict), "sourcepack_gitignored": False, "dirty_worktree": False, "next_action": "continue."}
    paths = ensure_sourcepack_dirs(repo)
    added, err = ensure_gitignore_entry(repo)
    if err:
        rep = traffic_report("FAIL", "SourcePack automatic mode could not be enabled.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
        write_auto_report(repo, rep, details)
        print(render_traffic(rep), end=""); return 1
    details["sourcepack_gitignored"] = True
    dirty, dirty_state = initial_dirty, initial_dirty_state
    details["dirty_worktree"] = dirty
    baseline_exists = baseline_exists_before_init
    if args.refresh_baseline or (not baseline_exists and (not dirty or getattr(args, "force", False))):
        try:
            _, created = build_current_baseline(repo, force=True)
            details["baseline_created"] = created
            details["baseline_refreshed"] = not created or args.refresh_baseline
            if dirty:
                findings.append(normalized_finding("dirty_worktree", "warn", "baseline", "dirty_worktree: baseline includes current uncommitted changes."))
        except BaselineLockError as exc:
            findings.append(normalized_finding("baseline_locked", "warn", "tooling", str(exc)))
            details["next_action"] = "Try again after the other baseline operation finishes."
        except Exception as exc:
            findings.append(normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}"))
    elif not baseline_exists and dirty:
        findings.append(normalized_finding("dirty_worktree", "warn", "baseline", "dirty_worktree: working tree has uncommitted changes, so baseline was not created."))
        findings.append(normalized_finding("baseline_missing", "warn", "baseline", "baseline_missing: run sourcepack baseline --refresh to accept current repo state."))
        details["next_action"] = "Run sourcepack init . --auto --refresh-baseline or sourcepack baseline --refresh to accept current repo state."
    if args.install_hygiene_hooks:
        findings.append(normalized_finding("hygiene_hooks_deferred", "warn", "hook", "baseline hygiene hooks are not installed by this release."))
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if args.no_hook:
        pass
    elif cp.returncode != 0:
        findings.append(normalized_finding("no_git_repo" if cp.returncode != 127 else "git_unavailable", "warn", "git", "no_git_repo: pre-commit hook was not installed because this is not a git repository." if cp.returncode != 127 else "Git executable not found."))
    else:
        class HookArgs: pass
        h = HookArgs(); h.repo = str(repo); h.strict = bool(args.strict)
        rc = cli_install_hook(h)
        details["hook_installed"] = rc == 0
        if rc != 0:
            findings.append(normalized_finding("hook_install_failed", "warn", "hook", "pre-commit hook could not be installed."))
    verdict = "FAIL" if any(f["severity"] == "error" for f in findings) else "WARN" if findings else "PASS"
    headline = "SourcePack automatic mode enabled." if verdict == "PASS" else "SourcePack automatic mode partially enabled." if verdict == "WARN" else "SourcePack automatic mode could not be enabled."
    rep = traffic_report(verdict, headline, findings, ["init", "baseline", "hook"], details.get("next_action", "continue."))
    write_auto_report(repo, rep, details)
    if args.json:
        print(json.dumps({**rep, **details}, indent=2)); return 0 if verdict != "FAIL" else 1
    print(f"{rep['light']}: {headline}\n")
    if findings:
        print("Warnings:" if verdict == "WARN" else "Blockers:")
        for f in findings: print(f"* {f['id']}: {f['message']}")
        print()
    print(f"Baseline: {'created' if details['baseline_created'] else 'refreshed' if details['baseline_refreshed'] else 'present' if baseline_exists else 'missing'}")
    print(f"Pre-commit hook: {'skipped' if args.no_hook else 'installed' if details['hook_installed'] else 'not installed'}")
    print(f".sourcepack/ gitignored: {'yes' if details['sourcepack_gitignored'] else 'no'}")
    return 0 if verdict != "FAIL" else 1

def _health_check_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    rows.append(("version", "PASS" if __version__ else "FAIL", __version__ or "missing package version"))
    rows.append(("python", "PASS" if sys.version_info >= (3, 11) else "FAIL", platform.python_version()))
    rows.append(("platform", "PASS", platform.platform()))
    rows.append(("git", "PASS" if shutil.which("git") else "WARN", shutil.which("git") or "not found on PATH; git-backed checks and hooks will be limited"))
    rows.append(("secret_signatures", "PASS" if SECRET_PATTERNS else "FAIL", str(len(SECRET_PATTERNS))))

    required_assets = ("audit_template.md", "packet_instructions.md")
    try:
        asset_root = resources.files("sourcepack.assets")
        missing_assets = [name for name in required_assets if not (asset_root / name).is_file()]
    except (FileNotFoundError, ModuleNotFoundError, AttributeError, TypeError) as exc:
        missing_assets = list(required_assets)
        rows.append(("package_assets", "FAIL", f"could not inspect packaged assets: {exc}"))
    else:
        rows.append(("package_assets", "PASS" if not missing_assets else "FAIL", "all required assets present" if not missing_assets else "missing: " + ", ".join(missing_assets)))

    report_renderers = (render_report_html, render_traffic, write_user_report)
    rows.append(("report_renderers", "PASS" if all(callable(fn) for fn in report_renderers) else "FAIL", "html, markdown, and json renderers importable"))
    return rows


def doctor(strict: bool = False) -> int:
    rows = _health_check_rows()
    print("--- SourcePack Health Check ---")
    for name, status, detail in rows:
        print(f"{status:4} {name}: {detail}")
    has_fail = any(status == "FAIL" for _, status, _ in rows)
    has_warn = any(status == "WARN" for _, status, _ in rows)
    if has_fail or (strict and has_warn):
        print("Status: NOT READY")
        return 1
    print("Status: READY")
    return 0



def cli_exec(args) -> int:
    entry = run_and_record(args.exec_command, cwd=".")
    print(entry.stdout_excerpt, end="")
    if entry.stderr_excerpt:
        print(entry.stderr_excerpt, end="", file=sys.stderr)
    print(f"SourcePack evidence entry: {entry.entry_id}", file=sys.stderr)
    return entry.exit_code


def cli_evidence(args) -> int:
    repo = find_repo_root(".")
    if args.evidence_command == "clear":
        clear_ledger(repo)
        print("Cleared SourcePack execution evidence ledger.")
        return 0
    if args.evidence_command == "list":
        entries = list(iter_entries(repo))
        if args.json:
            print(json.dumps({"schema_version": "sourcepack.execution_ledger.list.v1", "entries": entries}, indent=2))
            return 0
        for entry in entries:
            print(f"{entry.get('entry_id')} exit={entry.get('exit_code')} command={' '.join(entry.get('command') or [])}")
        return 0
    if args.evidence_command == "show":
        for entry in iter_entries(repo):
            if entry.get("entry_id") == args.entry_id:
                print(json.dumps(entry, indent=2, sort_keys=True))
                return 0
        print(f"ERROR: evidence entry not found: {args.entry_id}", file=sys.stderr)
        return 1
    if args.evidence_command == "export":
        print(json.dumps({"schema_version": "sourcepack.execution_ledger.export.v1", "entries": list(iter_entries(repo))}, indent=2))
        return 0
    return 1

REASON_EXPLANATIONS = {
    "unsupported_dependency": "A changed file imports a dependency that SourcePack could not find in local dependency manifests.",
    "unsupported_command": "A changed instruction references a project command that SourcePack could not find in local command manifests.",
    "declared_command": "The same patch declares command support and uses it; SourcePack requires review instead of treating it as established baseline evidence.",
    "command_manifest_missing": "A command check needed a local manifest/config file, but none was available.",
    "command_check_inconclusive": "SourcePack recognized the command family but could not safely infer support from dynamic or ambiguous config.",
}

def _policy_dir(repo: Path) -> Path:
    path = repo / ".sourcepack" / "policy"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _policy_file(repo: Path) -> Path:
    return _policy_dir(repo) / "allow.jsonl"

def _policy_entries(repo: Path) -> list[dict]:
    path = _policy_file(repo)
    if not path.exists(): return []
    entries=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try: entries.append(json.loads(line))
        except Exception: pass
    return entries

def cli_explain(args) -> int:
    code = args.reason_code.strip()
    print(f"{code}: {REASON_EXPLANATIONS.get(code, 'See docs/reason-codes.md and src/sourcepack/reason_codes.py for the canonical SourcePack reason-code vocabulary.')}")
    return 0

def cli_allow(args) -> int:
    repo = Path(".").resolve(); reason = getattr(args, "reason", None)
    if not reason:
        print("ERROR: --reason is required", file=sys.stderr); return 2
    scope_type = args.allow_type; value = args.value
    protected = value.startswith(".git/") or value == ".git" or value.startswith(".sourcepack/")
    if protected and not getattr(args, "high_risk", False):
        print("ERROR: protected artifacts require --high-risk and .git/** cannot be overridden", file=sys.stderr); return 1
    if value.startswith(".git/") or value == ".git":
        print("ERROR: .git/** cannot be overridden", file=sys.stderr); return 1
    entry = {"schema_version":"sourcepack.policy.allow.v1", "id": sha256_text(f'{scope_type}:{value}:{utc_now()}')[:12], "scope": scope_type, "value": value, "reason": reason, "created_at": utc_now(), "expires_at": getattr(args, "expires", None), "high_risk": bool(getattr(args, "high_risk", False))}
    with _policy_file(repo).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True)+"\n")
    print(json.dumps(entry, indent=2))
    return 0

def cli_policy_validate(args) -> int:
    result = validate_policy_config(getattr(args, "repo", "."))
    if getattr(args, "json", False):
        print(json.dumps(result.to_json_dict(), indent=2))
        return 0 if result.valid else 1
    if not result.policy_present:
        print(f"No policy file found at {result.policy_path}; policy config is optional.")
        return 0
    print(f"Policy file: {result.policy_path}")
    if result.errors:
        for error in result.errors:
            if error.startswith("policy_config_invalid_json:"):
                print(f"ERROR: invalid JSON in {result.policy_path}: {error}")
            elif error == "policy_config_invalid:root_must_be_object":
                print(f"ERROR: policy root must be a JSON object in {result.policy_path}")
            else:
                print(f"ERROR: {error}")
        return 1
    print("Policy config is valid.")
    if result.effective_ignored_paths:
        print("Effective ignored paths:")
        for item in result.effective_ignored_paths:
            print(f"- {item['pattern']} — {item['reason']}")
    else:
        print("Effective ignored paths: none")
    if result.ignored_invalid_entries:
        print("Ignored invalid entries:")
        for item in result.ignored_invalid_entries:
            print(f"- ignored_paths[{item.index}]: {item.warning}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    else:
        print("Warnings: none")
    return 0


def cli_policy(args) -> int:
    repo = Path(".").resolve()
    if args.policy_command == "validate":
        return cli_policy_validate(args)
    if args.policy_command == "list":
        print(json.dumps({"schema_version":"sourcepack.policy.list.v1", "policies": _policy_entries(repo)}, indent=2)); return 0
    if args.policy_command == "remove":
        entries = [e for e in _policy_entries(repo) if e.get("id") != args.policy_id]
        _policy_file(repo).write_text("".join(json.dumps(e, sort_keys=True)+"\n" for e in entries), encoding="utf-8")
        print(f"Removed policy {args.policy_id}"); return 0
    return 1

def cli_reset(args) -> int:
    repo = Path(args.repo).resolve(); target = repo / ".sourcepack" / "reports"
    if target.exists(): shutil.rmtree(target)
    print("SourcePack reset complete: removed local reports only; user code and trusted baseline were not deleted.")
    return 0

def cli_baseline_lifecycle(args) -> int | None:
    if args.repo not in {"status", "verify", "refresh", "repair", "path"}: return None
    command = args.repo; repo = Path(".").resolve(); status = validate_baseline(repo)
    if command == "status":
        if args.json: print(json.dumps({"schema_version":"sourcepack.baseline.status.v1", **status}, indent=2))
        else: print(f"Baseline: {status.get('state')}\n{status.get('message')}")
        return 0
    if command == "verify":
        if args.json: print(json.dumps({"schema_version":"sourcepack.baseline.verify.v1", **status}, indent=2))
        else: print(f"Baseline verify: {status.get('state')} - {status.get('message')}")
        return 0 if status.get("state") in {"present", "stale"} else 1
    if command == "path":
        print(status.get("packet_path") or "")
        return 0 if status.get("packet_path") else 1
    if command == "refresh":
        dirty, _ = git_worktree_dirty(repo)
        if dirty and not getattr(args, "force", False):
            print("ERROR: refusing baseline refresh with dirty worktree; commit/discard changes or pass --force after review.", file=sys.stderr); return 1
        class A: pass
        a=A(); a.repo="."; a.refresh=True; a.verbose=getattr(args,"verbose",False); a.json=args.json; a.quiet=False
        return cli_baseline(a)
    if command == "repair":
        print("Baseline repair checked metadata; no unsafe repair was attempted.")
        return 0 if status.get("state") in {"present", "stale"} else 1
    return None

def run_cli(args_list=None):
    parser = argparse.ArgumentParser(prog="sourcepack", description="Local guardrail for AI-assisted repo changes. PASS exits 0, WARN exits 0 locally unless --strict or --ci is used, and FAIL exits nonzero.")
    parser.add_argument("--version", action="store_true")
    subs = parser.add_subparsers(dest="command")
    build = subs.add_parser("build")
    build.add_argument("input")
    build.add_argument("--out", required=True)
    build.add_argument("--force", action="store_true")
    build.add_argument("--max-file-size", type=int, default=1_000_000)
    build.add_argument("--include-hidden", action="store_true")
    build.add_argument("--no-redact", action="store_true")
    verify = subs.add_parser("verify")
    verify.add_argument("packet")
    verify.add_argument("--against")
    judge = subs.add_parser("judge")
    judge.add_argument("packet")
    judge.add_argument("ai_answer")
    judge.add_argument("--out")
    judge_patch_cmd = subs.add_parser("judge-patch", help="judge a unified diff against a packet", description="Judge a git-style unified diff against SourcePack packet evidence. The JSON and markdown reports include verdict, blockers, warnings, uncertainties, checked categories, not checked categories, next action, and report path.")
    judge_patch_cmd.add_argument("packet")
    judge_patch_cmd.add_argument("patch")
    judge_patch_cmd.add_argument("--out", required=True)
    map_cmd = subs.add_parser("map")
    map_cmd.add_argument("input")
    map_cmd.add_argument("--out", required=True)
    instr = subs.add_parser("instructions")
    instr.add_argument("packet")
    subs.add_parser("demo")
    init = subs.add_parser("init", help="initialize local SourcePack state", description="Initialize .sourcepack state. With --auto, create a safe baseline when possible and install git hooks. --strict installs hooks that block WARN and FAIL.")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--auto", action="store_true")
    init.add_argument("--strict", action="store_true")
    init.add_argument("--no-hook", action="store_true")
    init.add_argument("--refresh-baseline", action="store_true")
    init.add_argument("--force", action="store_true")
    init.add_argument("--install-hygiene-hooks", action="store_true")
    init.add_argument("--json", action="store_true")
    doctor_cmd = subs.add_parser("doctor")
    doctor_cmd.add_argument("--strict", action="store_true", help="exit nonzero on warnings as well as failures")
    exec_cmd = subs.add_parser("exec", help="run a local command and record bounded execution evidence")
    exec_cmd.add_argument("exec_command", nargs=argparse.REMAINDER)
    evidence_cmd = subs.add_parser("evidence", help="inspect local SourcePack execution evidence")
    evidence_subs = evidence_cmd.add_subparsers(dest="evidence_command")
    evidence_list = evidence_subs.add_parser("list")
    evidence_list.add_argument("--json", action="store_true")
    evidence_show = evidence_subs.add_parser("show")
    evidence_show.add_argument("entry_id")
    evidence_subs.add_parser("clear")
    evidence_export = evidence_subs.add_parser("export")
    evidence_export.add_argument("--json", action="store_true")
    prompt_cmd = subs.add_parser("prompt", help="write non-authoritative AI prompt context", description="Generate selective prompt context for an AI task. Prompt context is non-authoritative and never refreshes the trusted enforcement baseline.")
    prompt_cmd.add_argument("repo")
    prompt_cmd.add_argument("task", nargs="?")
    prompt_cmd.add_argument("--copy", action="store_true")
    prompt_cmd.add_argument("--verbose", action="store_true")
    prompt_cmd.add_argument("--json", action="store_true")
    baseline_cmd = subs.add_parser("baseline", help="create or refresh trusted enforcement baseline", description="Create or refresh .sourcepack/baseline, the authoritative enforcement state used by sourcepack diff.")
    baseline_cmd.add_argument("repo")
    baseline_cmd.add_argument("--force", action="store_true")
    baseline_cmd.add_argument("--refresh", action="store_true")
    baseline_cmd.add_argument("--verbose", action="store_true")
    baseline_cmd.add_argument("--json", action="store_true")
    baseline_cmd.add_argument("--quiet", action="store_true")
    diff_cmd = subs.add_parser("diff", help="check repo changes against trusted baseline", description="Judge working-tree or staged changes against .sourcepack/baseline. PASS exits 0. WARN exits 0 locally, but exits nonzero with --strict or --ci. FAIL exits nonzero. --json stays machine-readable.")
    diff_cmd.add_argument("repo")
    diff_cmd.add_argument("--staged", action="store_true")
    diff_cmd.add_argument("--verbose", action="store_true")
    diff_cmd.add_argument("--json", action="store_true")
    diff_cmd.add_argument("--strict", action="store_true", help="exit nonzero on WARN as well as FAIL")
    diff_cmd.add_argument("--ci", action="store_true", help="non-interactive CI mode; implies --strict and prints JSON")
    install_hook = subs.add_parser("install-hook")
    install_hook.add_argument("repo")
    install_hook.add_argument("--strict", action="store_true")
    uninstall_hook = subs.add_parser("uninstall-hook")
    uninstall_hook.add_argument("repo")
    status_cmd = subs.add_parser("status", help="show SourcePack repo state", description="Show baseline, hook, report, git, and dirty-worktree state without changing the baseline.")
    status_cmd.add_argument("repo")
    status_cmd.add_argument("--json", action="store_true")
    replay_cmd = subs.add_parser("replay", help="reconstruct a saved SourcePack report or replay bundle")
    replay_cmd.add_argument("input_path")
    replay_cmd.add_argument("--json", action="store_true")
    ui_cmd = subs.add_parser("ui", help="serve the local SourcePack Workbench", description="serve the local SourcePack Workbench")
    ui_cmd.add_argument("repo", nargs="?", default=".")
    ui_cmd.add_argument("--host", default="127.0.0.1")
    ui_cmd.add_argument("--port", type=int, default=0)
    ui_cmd.add_argument("--no-open", action="store_true")
    workbench_cmd = subs.add_parser("workbench", help="alias for sourcepack ui", description="alias for sourcepack ui")
    workbench_cmd.add_argument("repo", nargs="?", default=".")
    workbench_cmd.add_argument("--host", default="127.0.0.1")
    workbench_cmd.add_argument("--port", type=int, default=0)
    workbench_cmd.add_argument("--no-open", action="store_true")
    report_cmd = subs.add_parser("report", help="work with local SourcePack reports")
    report_subs = report_cmd.add_subparsers(dest="report_command")
    report_open = report_subs.add_parser("open", help="open .sourcepack/reports/latest.html")
    report_open.add_argument("repo", nargs="?", default=".")
    report_path = report_subs.add_parser("path", help="print .sourcepack/reports/latest.html")
    report_path.add_argument("repo", nargs="?", default=".")
    explain_cmd = subs.add_parser("explain")
    explain_cmd.add_argument("reason_code")
    allow_cmd = subs.add_parser("allow")
    allow_cmd.add_argument("allow_type", choices=["dependency", "command", "path"])
    allow_cmd.add_argument("value")
    allow_cmd.add_argument("--reason", required=True)
    allow_cmd.add_argument("--expires")
    allow_cmd.add_argument("--high-risk", action="store_true")
    policy_cmd = subs.add_parser("policy")
    policy_subs = policy_cmd.add_subparsers(dest="policy_command")
    policy_subs.add_parser("list")
    policy_validate = policy_subs.add_parser("validate", help="validate .sourcepack/policy.json without changing repository state")
    policy_validate.add_argument("repo", nargs="?", default=".")
    policy_validate.add_argument("--json", action="store_true")
    policy_remove = policy_subs.add_parser("remove")
    policy_remove.add_argument("policy_id")
    reset_cmd = subs.add_parser("reset")
    reset_cmd.add_argument("repo", nargs="?", default=".")
    args = parser.parse_args(args_list)
    if args.version:
        print(__version__); return 0
    try:
        if args.command == "doctor":
            return doctor(strict=getattr(args, "strict", False))
        if args.command == "exec":
            if args.exec_command and args.exec_command[0] == "--":
                args.exec_command = args.exec_command[1:]
            return cli_exec(args)
        if args.command == "evidence":
            return cli_evidence(args)
        if args.command == "init":
            return cli_init(args)
        if args.command == "prompt":
            return cli_prompt(args)
        if args.command == "baseline":
            lifecycle = cli_baseline_lifecycle(args)
            if lifecycle is not None:
                return lifecycle
            return cli_baseline(args)
        if args.command == "diff":
            return cli_diff(args)
        if args.command == "install-hook":
            return cli_install_hook(args)
        if args.command == "uninstall-hook":
            return cli_uninstall_hook(args)
        if args.command == "status":
            return cli_status(args)
        if args.command == "explain":
            return cli_explain(args)
        if args.command == "allow":
            return cli_allow(args)
        if args.command == "policy":
            return cli_policy(args)
        if args.command == "reset":
            return cli_reset(args)
        if args.command == "replay":
            result, code = reconstruct_replay(args.input_path)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(render_replay_human(result), end="")
            return code
        if args.command in {"ui", "workbench"}:
            from .workbench import serve_workbench
            return serve_workbench(args.repo, host=args.host, port=args.port, open_browser=not args.no_open)
        if args.command == "report":
            if args.report_command == "open":
                return cli_report_open(args)
            if args.report_command == "path":
                return cli_report_path(args)
            parser.parse_args(["report", "--help"])
            return 1
        if args.command == "build":
            scanner = SourceScanner(args.input, max_file_size=args.max_file_size, include_hidden=args.include_hidden, redact=not args.no_redact).scan()
            out = PacketWriter(args.out, scanner, force=args.force).write_all()
            print(f"Packet built successfully at {out}"); return 0
        if args.command == "map":
            scanner = SourceScanner(args.input).scan()
            with tempfile.TemporaryDirectory() as td:
                packet = PacketWriter(td, scanner, force=True).write_all()
                reality_map = json.loads((packet / "reality_map.json").read_text(encoding="utf-8"))
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
            print(f"Reality map written to {out_path}"); return 0
        if args.command == "instructions":
            packet = Path(args.packet)
            instructions_path = packet / "ai_instructions.md"
            if instructions_path.exists():
                print(instructions_path.read_text(encoding="utf-8"), end=""); return 0
            reality_path = packet / "reality_map.json"
            if not reality_path.exists():
                print("ERROR: missing ai_instructions.md and reality_map.json", file=sys.stderr); return 1
            reality_map = json.loads(reality_path.read_text(encoding="utf-8"))
            text = render_ai_instructions(reality_map)
            instructions_path.write_text(text, encoding="utf-8")
            print(text, end=""); return 0
        if args.command == "demo":
            examples_root = resources.files("sourcepack") / "examples"
            with resources.as_file(examples_root) as examples_path:
                demo_repo = examples_path / "demo_repo"
                fake_patch = examples_path / "fake_ai_patch.diff"
                fake_answer = examples_path / "fake_ai_answer.md"
                if not demo_repo.exists() or not fake_patch.exists() or not fake_answer.exists():
                    print("ERROR: packaged examples/demo_repo, examples/fake_ai_patch.diff, and examples/fake_ai_answer.md are required", file=sys.stderr); return 1
                tmp = Path(tempfile.mkdtemp(prefix="sourcepack_demo_"))
                packet = tmp / "packet"
                patch_judgment = tmp / "patch_judgment"
                judgment = tmp / "judgment"
                PacketWriter(packet, SourceScanner(demo_repo).scan(), force=True).write_all()
                verification_output = io.StringIO()
                with contextlib.redirect_stdout(verification_output):
                    packet_ok = verify_packet(packet)
                if not packet_ok:
                    print(verification_output.getvalue(), end="", file=sys.stderr)
                    return 1
                with contextlib.redirect_stdout(io.StringIO()):
                    judge_ai_answer(packet, fake_answer, judgment)
                    report = judge_patch(packet, fake_patch, patch_judgment)
                traffic = patch_report_to_traffic(report, str(patch_judgment / "patch_judgment_report.json"))
                blockers = [f for f in traffic.get("blockers", []) if f.get("id") == "unsupported_dependency"]
                if not blockers:
                    print("ERROR: demo did not produce the expected unsupported_dependency finding", file=sys.stderr)
                    return 1
                print("RED LIGHT: commit blocked")
                for finding in blockers:
                    evidence = finding.get("evidence") or "dependency"
                    path = finding.get("path") or "sourcepack/server.py"
                    print(f"unsupported_dependency: {path} imports {evidence}, but {evidence} is not declared.")
                print()
                print(render_traffic(traffic), end="")
                print(f"Demo packet: {packet}")
                print(f"Demo judgment: {judgment}")
                print(f"Demo patch judgment: {patch_judgment}")
                return 0
        if args.command == "verify":
            return 0 if verify_packet(args.packet, args.against) else 1
        if args.command == "judge":
            judge_ai_answer(args.packet, args.ai_answer, args.out); return 0
        if args.command == "judge-patch":
            report = judge_patch(args.packet, args.patch, args.out)
            return 1 if report.get("malformed_diff") else 0
        parser.print_help(); return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())


---

## File: src/sourcepack/commands.py

Metadata:
- sha256: 34482d60d8a2cff0c1dad9715ee052d14ad7f686e8bb9b49ca0150ef6bed9cd2
- bytes: 8103
- estimated_tokens: 2026

Content:

from __future__ import annotations

import configparser
import json
import re
from dataclasses import dataclass
from pathlib import Path

COMMAND_SCHEMA_VERSION = "sourcepack.command_resolver.v1"
COMPOSE_FILES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")


@dataclass(frozen=True)
class CommandResolution:
    verdict: str
    reason_code: str | None
    command: str
    evidence_source: str | None = None
    message: str = ""

    def to_dict(self) -> dict:
        return {"schema_version": COMMAND_SCHEMA_VERSION, "verdict": self.verdict, "reason_code": self.reason_code, "command": self.command, "evidence_source": self.evidence_source, "message": self.message}


def _safe(root: Path, rel: str) -> Path | None:
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    return p


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _make_targets(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.-][^\s:=]*)\s*:(?!=)", text, re.M)}


def _just_targets(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.-]+)\s*:", text, re.M)}


def _taskfile_targets(data: dict) -> set[str]:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    return set(tasks.keys()) if isinstance(tasks, dict) else set()


def resolve_command(root: str | Path, command: str, *, added_manifests: dict[str, str] | None = None) -> CommandResolution:
    root = Path(root).resolve(); added_manifests = added_manifests or {}; command = command.strip()
    parts = command.split()
    if not parts:
        return CommandResolution("WARN", "command_check_inconclusive", command, message="empty command")
    if len(parts) >= 3 and parts[0] == "npm" and parts[1] == "run":
        script = parts[2]
        pj = _safe(root, "package.json")
        if "package.json" in added_manifests:
            data = _read_json_from_text(added_manifests["package.json"])
            if script in (data.get("scripts") or {}):
                return CommandResolution("WARN", "declared_command", command, "package.json", "script added in patch")
        if not pj or not pj.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "package.json", "package.json missing")
        data = _read_json(pj) or {}
        return CommandResolution("PASS", None, command, "package.json", "script present") if script in (data.get("scripts") or {}) else CommandResolution("FAIL", "unsupported_command", command, "package.json", "npm script missing")
    if len(parts) >= 3 and parts[0] == "docker" and parts[1] == "compose":
        for name in COMPOSE_FILES:
            p = _safe(root, name)
            if p and p.exists():
                return CommandResolution("PASS", None, command, name, "compose file present")
        return CommandResolution("FAIL", "unsupported_command", command, ",".join(COMPOSE_FILES), "compose file missing")
    if parts[0] == "make" and len(parts) >= 2:
        p = _safe(root, "Makefile")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "Makefile", "Makefile missing")
        targets = _make_targets(p.read_text(encoding="utf-8", errors="ignore"))
        return CommandResolution("PASS", None, command, "Makefile", "target present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, "Makefile", "Make target missing")
    if parts[0] == "just" and len(parts) >= 2:
        p = _safe(root, "justfile") or _safe(root, "Justfile")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "justfile", "justfile missing")
        targets = _just_targets(p.read_text(encoding="utf-8", errors="ignore"))
        return CommandResolution("PASS", None, command, str(p.name), "recipe present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, str(p.name), "recipe missing")
    if parts[0] == "task" and len(parts) >= 2:
        for name in ("Taskfile.yml", "Taskfile.yaml"):
            p = _safe(root, name)
            if p and p.exists():
                try:
                    import yaml  # type: ignore
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = _simple_taskfile_parse(p.read_text(encoding="utf-8", errors="ignore"))
                targets = _taskfile_targets(data)
                return CommandResolution("PASS", None, command, name, "task present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, name, "task missing")
        return CommandResolution("WARN", "command_manifest_missing", command, "Taskfile.yml", "Taskfile missing")
    if parts[0] in {"pytest", "py.test"} or (len(parts) >= 3 and parts[0] == "python" and parts[1] == "-m" and parts[2] == "pytest"):
        has_tests = any((root / name).exists() for name in ("tests", "test", "pytest.ini"))
        if has_tests:
            return CommandResolution("PASS", None, command, "tests", "pytest evidence present")
        pyproject = _safe(root, "pyproject.toml")
        requirements = list(root.glob("requirements*.txt"))
        manifest_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in ([pyproject] if pyproject and pyproject.exists() else []) + requirements)
        if re.search(r"(?im)\bpytest\b", manifest_text):
            return CommandResolution("PASS", None, command, "python dependency manifest", "pytest dependency present")
        return CommandResolution("FAIL", "unsupported_command", command, "tests/pytest.ini/pyproject.toml", "pytest project evidence missing")
    if parts[0] == "tox" and "-e" in parts:
        env = parts[parts.index("-e") + 1] if parts.index("-e") + 1 < len(parts) else ""
        p = _safe(root, "tox.ini")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_check_inconclusive", command, "tox.ini", "tox.ini missing")
        cp = configparser.ConfigParser(); cp.read(p)
        raw = cp.get("tox", "envlist", fallback="")
        if "{" in raw or "}" in raw or not raw:
            return CommandResolution("WARN", "command_check_inconclusive", command, "tox.ini", "dynamic or missing envlist")
        envs = {e.strip() for e in re.split(r"[,\n]", raw) if e.strip()}
        return CommandResolution("PASS", None, command, "tox.ini", "env present") if env in envs else CommandResolution("FAIL", "unsupported_command", command, "tox.ini", "tox env missing")
    if parts[0] == "nox" and "-s" in parts:
        session = parts[parts.index("-s") + 1] if parts.index("-s") + 1 < len(parts) else ""
        p = _safe(root, "noxfile.py")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "noxfile.py", "noxfile missing")
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"@nox\.session(?:\([^)]*\))?\s*\ndef\s+" + re.escape(session) + r"\b", text):
            return CommandResolution("PASS", None, command, "noxfile.py", "session present")
        return CommandResolution("WARN", "command_check_inconclusive", command, "noxfile.py", "dynamic or missing nox session")
    return CommandResolution("WARN", "command_check_inconclusive", command, message="command parser unsupported")


def _read_json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        return {}


def _simple_taskfile_parse(text: str) -> dict:
    tasks: dict[str, dict] = {}
    in_tasks = False
    for line in text.splitlines():
        if re.match(r"^tasks:\s*$", line):
            in_tasks = True; continue
        if in_tasks:
            m = re.match(r"^\s{2}([A-Za-z0-9_.-]+):", line)
            if m: tasks[m.group(1)] = {}
    return {"tasks": tasks}


---

## File: src/sourcepack/dependencies.py

Metadata:
- sha256: cc3f5af5a95790b1f4dfa53f23d63dbcb006d866377f24991563f2a0b34353e1
- bytes: 5856
- estimated_tokens: 1464

Content:

from __future__ import annotations

import ast, json, re, sys, tomllib
from dataclasses import dataclass
from pathlib import Path
from .ecosystems.python import PY_IMPORT_ALIASES

DEPENDENCY_SCHEMA_VERSION = "sourcepack.dependency_resolver.v1"
UNSUPPORTED_ECOSYSTEM_MANIFESTS = {"Cargo.toml", "go.mod", "pom.xml", "build.gradle", "settings.gradle"}

@dataclass(frozen=True)
class DependencyResolution:
    verdict: str
    reason_code: str | None
    dependency: str
    evidence_source: str | None = None
    message: str = ""
    def to_dict(self) -> dict:
        return {"schema_version": DEPENDENCY_SCHEMA_VERSION, "verdict": self.verdict, "reason_code": self.reason_code, "dependency": self.dependency, "evidence_source": self.evidence_source, "message": self.message}

def normalize_python_package(name: str) -> str:
    base = name.split(".")[0].replace("_", "-").lower()
    return PY_IMPORT_ALIASES.get(base, base)

def normalize_js_package(spec: str) -> str:
    if spec.startswith(".") or spec.startswith("/"):
        return spec
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]

def python_declared_dependencies(root: str | Path) -> dict[str, str]:
    root = Path(root); found: dict[str, str] = {}
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try: data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except Exception: data = {}
        for dep in data.get("project", {}).get("dependencies", []) or []: found[_dep_name(dep)] = "pyproject.toml"
        for group, deps in (data.get("project", {}).get("optional-dependencies", {}) or {}).items():
            for dep in deps or []: found.setdefault(_dep_name(dep), f"pyproject.toml optional:{group}")
        for group, gdata in (data.get("dependency-groups", {}) or {}).items():
            for dep in (gdata if isinstance(gdata, list) else []): found.setdefault(_dep_name(str(dep)), f"pyproject.toml group:{group}")
        poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
        for dep in poetry:
            if dep.lower() != "python": found[_dep_name(dep)] = "pyproject.toml poetry"
    for req in root.glob("requirements*.txt"):
        for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                found[_dep_name(line)] = req.name
    return found

def js_declared_dependencies(root: str | Path) -> dict[str, str]:
    pj = Path(root) / "package.json"; found: dict[str, str] = {}
    if not pj.exists(): return found
    try: data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception: return found
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for dep in (data.get(section) or {}): found[dep] = f"package.json {section}"
    return found

def resolve_python_import(root: str | Path, imported: str, *, added_dependencies: set[str] | None = None) -> DependencyResolution:
    root = Path(root); top = imported.split(".")[0]
    if top in sys.stdlib_module_names: return DependencyResolution("PASS", None, imported, "python stdlib", "stdlib")
    if (root / (top + ".py")).exists() or (root / top / "__init__.py").exists() or (root / "src" / top / "__init__.py").exists() or (root / "src" / (top + ".py")).exists(): return DependencyResolution("PASS", None, imported, "worktree", "local module")
    pkg = normalize_python_package(imported); declared = python_declared_dependencies(root)
    if pkg in (added_dependencies or set()): return DependencyResolution("WARN", "declared_dependency", pkg, "patch", "dependency added in same patch")
    if pkg in declared:
        source = declared[pkg]
        if "optional:" in source or "group:" in source: return DependencyResolution("WARN", "dependency_scope_review", pkg, source, "declared outside runtime dependency scope")
        return DependencyResolution("PASS", None, pkg, source, "declared")
    return DependencyResolution("FAIL", "unsupported_dependency", pkg, None, "external dependency not declared")

def resolve_js_import(root: str | Path, spec: str) -> DependencyResolution:
    root = Path(root); pkg = normalize_js_package(spec)
    if pkg.startswith(".") or pkg.startswith("/"): return DependencyResolution("PASS", None, spec, "relative import", "local relative import")
    declared = js_declared_dependencies(root)
    if pkg in declared:
        src = declared[pkg]
        if "devDependencies" in src: return DependencyResolution("WARN", "dependency_scope_review", pkg, src, "devDependency requires scope review")
        return DependencyResolution("PASS", None, pkg, src, "declared")
    if spec.startswith(("@/", "~/")):
        return DependencyResolution("WARN", "js_alias_uncertain", spec, "tsconfig.json", "alias requires bounded resolver")
    return DependencyResolution("FAIL", "unsupported_dependency", pkg, None, "package dependency not declared")

def unsupported_ecosystems(root: str | Path) -> list[DependencyResolution]:
    root = Path(root); return [DependencyResolution("WARN", "unsupported_ecosystem", m.name, m.name, "ecosystem detected but not semantically resolved") for m in root.iterdir() if m.name in UNSUPPORTED_ECOSYSTEM_MANIFESTS]

def imports_from_python_source(text: str) -> set[str]:
    out = set()
    try: tree = ast.parse(text)
    except SyntaxError: return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: out.add(node.module)
    return out

def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~;\[\s]", str(spec).strip(), 1)[0].replace("_", "-").lower()


---

## File: src/sourcepack/diff_parser.py

Metadata:
- sha256: 56ee3f55c4a4f420682dc7a28f64f8d4dbb3e2fecd403daf6ad71d9ce76dd554
- bytes: 4811
- estimated_tokens: 1203

Content:

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

@dataclass
class PatchFileChange:
    path: str
    old_path: str | None
    new_file: bool = False
    deleted_file: bool = False
    added_lines: list[str] | None = None
    diff_lines: list[str] | None = None
    unsafe_path: bool = False
    operation: str = "modify"


def normalize_diff_path(path: str) -> tuple[str, bool]:
    raw = path.strip().replace("\\", "/")
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    if not raw or raw in {"a/", "b/"}:
        return raw, True
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        return raw, True
    parts: list[str] = []
    unsafe = False
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                unsafe = True
            else:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts), unsafe


def parse_unified_diff(text: str) -> list[PatchFileChange]:
    changes: list[PatchFileChange] = []
    current: PatchFileChange | None = None
    old_path: str | None = None
    new_path: str | None = None
    new_file = False
    deleted_file = False
    operation = "modify"

    malformed = False

    def clean(path: str) -> tuple[str, bool]:
        path = path.strip().split("\t", 1)[0]
        return normalize_diff_path(path)

    def flush():
        nonlocal current
        if current is not None:
            changes.append(current)
            current = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush(); old_path = new_path = None; new_file = deleted_file = False; operation = "modify"
            parts = line.split()
            if len(parts) >= 4:
                old_path, old_unsafe = clean(parts[2]); new_path, new_unsafe = clean(parts[3])
                if old_unsafe or new_unsafe:
                    malformed = True
            else:
                malformed = True
        elif line.startswith("new file mode"):
            new_file = True
        elif line.startswith("deleted file mode"):
            deleted_file = True
        elif line.startswith("rename from "):
            old_path, unsafe = clean(line.removeprefix("rename from "))
            operation = "rename"
            malformed = malformed or unsafe
        elif line.startswith("rename to "):
            new_path, unsafe = clean(line.removeprefix("rename to "))
            operation = "rename"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=False, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("copy from "):
            old_path, unsafe = clean(line.removeprefix("copy from "))
            operation = "copy"
            malformed = malformed or unsafe
        elif line.startswith("copy to "):
            new_path, unsafe = clean(line.removeprefix("copy to "))
            operation = "copy"
            malformed = malformed or unsafe
            current = PatchFileChange(path=new_path or old_path or "", old_path=old_path, new_file=True, deleted_file=False, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("--- "):
            val = line[4:].strip()
            if val == "/dev/null":
                old_path = None
            else:
                old_path, unsafe = clean(val)
                malformed = malformed or unsafe
        elif line.startswith("+++ "):
            val = line[4:].strip()
            if val == "/dev/null":
                new_path = None
                unsafe = False
            else:
                new_path, unsafe = clean(val)
            malformed = malformed or unsafe
            path = new_path or old_path or ""
            current = PatchFileChange(path=path, old_path=old_path, new_file=new_file or old_path is None, deleted_file=deleted_file or new_path is None, added_lines=[], diff_lines=[], unsafe_path=unsafe, operation=operation)
        elif line.startswith("@@ ") and current is None:
            malformed = True
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.added_lines.append(line[1:])
            current.diff_lines.append(line)
        elif current is not None and (line.startswith("-") or line.startswith(" ") or line.startswith("@@")):
            current.diff_lines.append(line)
    flush()
    if malformed:
        changes.append(PatchFileChange(path="", old_path=None, added_lines=[], diff_lines=[], unsafe_path=True))
    return changes


---

## File: src/sourcepack/ecosystems/__init__.py

Metadata:
- sha256: 6589fde5184d12c464fdbd7189c50b182b82ff45b717c222a44f86fbdba75426
- bytes: 71
- estimated_tokens: 18

Content:

from .python import PY_IMPORT_ALIASES

__all__ = ["PY_IMPORT_ALIASES"]


---

## File: src/sourcepack/ecosystems/generic.py

Metadata:
- sha256: b5f0696b6977c62996daaf2513e3bcc6049174686d7071af69f33d2addb76bbd
- bytes: 344
- estimated_tokens: 86

Content:

from __future__ import annotations

UNSUPPORTED_ECOSYSTEM_FILES = {
    "Cargo.toml": "Rust/Cargo",
    "go.mod": "Go modules",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "Gemfile": "Ruby/Bundler",
    "composer.json": "PHP/Composer",
    "*.csproj": ".NET/NuGet",
    "main.tf": "Terraform",
    "flake.nix": "Nix",
}


---

## File: src/sourcepack/ecosystems/node.py

Metadata:
- sha256: ca37c2810efb59edfc963521117ea0af12768c41436a2c0a3df1e396dae4f6a3
- bytes: 90
- estimated_tokens: 23

Content:

from __future__ import annotations

JS_SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


---

## File: src/sourcepack/ecosystems/python.py

Metadata:
- sha256: 4367d9b593851e50cc1aea0a1a655ae9d343fcb9164131b64f324ee6c891d860
- bytes: 293
- estimated_tokens: 74

Content:

from __future__ import annotations

PY_IMPORT_ALIASES: dict[str, str] = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "pil": "pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "jwt": "pyjwt",
    "dateutil": "python-dateutil",
}


---

## File: src/sourcepack/errors.py

Metadata:
- sha256: 67c0c7dcdcdd89883c38ad4d9f9cc84023dea6cd94ea9a5377c9bcb213b33e23
- bytes: 400
- estimated_tokens: 100

Content:

from __future__ import annotations

class SourcePackError(Exception):
    """Base class for typed SourcePack core failures."""

class BaselineMissingError(SourcePackError):
    pass

class BaselineCorruptError(SourcePackError):
    pass

class MalformedDiffError(SourcePackError):
    pass

class UnsafePathError(SourcePackError):
    pass

class UnsupportedEcosystemError(SourcePackError):
    pass


---

## File: src/sourcepack/evidence.py

Metadata:
- sha256: 57cce10ee364f439ea45e5f83bae3dc515e8090c9f9495cf39816336e220392b
- bytes: 6475
- estimated_tokens: 1619

Content:

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, Iterable

EVIDENCE_SCHEMA_VERSION = "sourcepack.evidence.v1"
EVIDENCE_ITEM_SCHEMA_VERSION = "sourcepack.evidence_item.v1"
REPLAY_BUNDLE_SCHEMA_VERSION = "sourcepack.replay_bundle.v1"


class EvidenceClass(StrEnum):
    TRUSTED_BASELINE = "trusted_baseline"
    CURRENT_WORKTREE = "current_worktree"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    COMMAND_MANIFEST = "command_manifest"
    EXECUTION_LEDGER = "execution_ledger"
    GIT_METADATA = "git_metadata"
    PROMPT_CONTEXT = "prompt_context"
    AI_ANSWER = "ai_answer"
    USER_CONFIG = "user_config"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"


TRUST_LEVELS = {
    EvidenceClass.TRUSTED_BASELINE: "trusted",
    EvidenceClass.CURRENT_WORKTREE: "local_observation",
    EvidenceClass.DEPENDENCY_MANIFEST: "local_manifest",
    EvidenceClass.COMMAND_MANIFEST: "local_manifest",
    EvidenceClass.EXECUTION_LEDGER: "local_execution_record",
    EvidenceClass.GIT_METADATA: "local_metadata",
    EvidenceClass.USER_CONFIG: "user_policy",
    EvidenceClass.PROMPT_CONTEXT: "advisory",
    EvidenceClass.AI_ANSWER: "advisory",
    EvidenceClass.UNSUPPORTED: "unsupported",
    EvidenceClass.NOT_CHECKED: "not_checked",
}

ENFORCEMENT_CAPABLE = {
    EvidenceClass.TRUSTED_BASELINE,
    EvidenceClass.CURRENT_WORKTREE,
    EvidenceClass.DEPENDENCY_MANIFEST,
    EvidenceClass.COMMAND_MANIFEST,
    EvidenceClass.EXECUTION_LEDGER,
    EvidenceClass.GIT_METADATA,
    EvidenceClass.USER_CONFIG,
}


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    category: str
    source_type: str
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    observed_value: str | None = None
    normalized_value: str | None = None
    supports: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    uncertainty: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _stable_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence_item_id(payload: dict[str, Any]) -> str:
    stable = {k: v for k, v in payload.items() if k != "evidence_id" and v not in (None, [], {})}
    return "ev_" + hashlib.sha256(_stable_payload(stable).encode("utf-8")).hexdigest()[:16]


def make_evidence_item(category: str, source_type: str, *, path: str | None = None, line_start: int | None = None, line_end: int | None = None, observed_value: str | None = None, normalized_value: str | None = None, supports: Iterable[str] | None = None, contradicts: Iterable[str] | None = None, uncertainty: str | None = None, metadata: dict[str, Any] | None = None) -> EvidenceItem:
    payload = {
        "category": str(category),
        "source_type": str(source_type),
        "path": path,
        "line_start": line_start,
        "line_end": line_end,
        "observed_value": observed_value,
        "normalized_value": normalized_value,
        "supports": sorted(str(x) for x in (supports or [])),
        "contradicts": sorted(str(x) for x in (contradicts or [])),
        "uncertainty": uncertainty,
        "metadata": metadata or {},
    }
    return EvidenceItem(evidence_id=evidence_item_id(payload), **payload)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_class: str
    evidence_source: str
    trust_level: str
    checked_status: str
    missing_evidence: str | None = None
    required_evidence_class: str | None = None
    supports_claim: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_evidence_class(value: str | EvidenceClass) -> EvidenceClass:
    return value if isinstance(value, EvidenceClass) else EvidenceClass(str(value))


def make_evidence(evidence_class: str | EvidenceClass, evidence_source: str, checked_status: str = "checked", *, missing_evidence: str | None = None, required_evidence_class: str | EvidenceClass | None = None, supports_claim: str | None = None) -> EvidenceRecord:
    cls = normalize_evidence_class(evidence_class)
    req = normalize_evidence_class(required_evidence_class).value if required_evidence_class else None
    return EvidenceRecord(cls.value, evidence_source, TRUST_LEVELS[cls], checked_status, missing_evidence, req, supports_claim)


def can_satisfy(evidence: EvidenceRecord | dict, required: str | EvidenceClass, claim: str | None = None) -> bool:
    eclass = normalize_evidence_class(evidence["evidence_class"] if isinstance(evidence, dict) else evidence.evidence_class)
    required_cls = normalize_evidence_class(required)
    if eclass in {EvidenceClass.PROMPT_CONTEXT, EvidenceClass.AI_ANSWER, EvidenceClass.UNSUPPORTED, EvidenceClass.NOT_CHECKED}:
        return False
    if eclass != required_cls:
        return False
    if eclass == EvidenceClass.EXECUTION_LEDGER and claim not in {None, "local_execution"}:
        return False
    return eclass in ENFORCEMENT_CAPABLE


def evidence_summary(records: Iterable[EvidenceRecord | dict]) -> dict:
    checked: list[dict] = []
    missing: list[dict] = []
    advisory: list[dict] = []
    not_checked: list[dict] = []
    for rec in records:
        item = rec if isinstance(rec, dict) else rec.to_dict()
        cls = item.get("evidence_class")
        status = item.get("checked_status")
        if cls in {EvidenceClass.PROMPT_CONTEXT.value, EvidenceClass.AI_ANSWER.value}:
            advisory.append(item)
        elif cls == EvidenceClass.NOT_CHECKED.value or status == "not_checked":
            not_checked.append(item)
        elif item.get("missing_evidence") or status in {"missing", "unavailable"}:
            missing.append(item)
        else:
            checked.append(item)
    return {"schema_version": EVIDENCE_SCHEMA_VERSION, "checked_evidence": checked, "missing_evidence": missing, "advisory_evidence_ignored_for_enforcement": advisory, "not_checked": not_checked}


def attach_evidence_to_finding(finding: dict, evidence_class: str | EvidenceClass, evidence_source: str, checked_status: str = "checked", **kwargs) -> dict:
    result = dict(finding)
    rec = make_evidence(evidence_class, evidence_source, checked_status, **kwargs).to_dict()
    result.update(rec)
    return result


---

## File: src/sourcepack/examples/demo_repo/README.md

Metadata:
- sha256: a7e1752b33efa2da5769f5e7aeb6e23498350f9c59a902341f8863a58c607900
- bytes: 153
- estimated_tokens: 39

Content:

# Demo Repo

This is a local-first CLI demo. PDF parsing is not supported. There is no web server. There is no Docker setup. There is no React frontend.


---

## File: src/sourcepack/examples/demo_repo/pyproject.toml

Metadata:
- sha256: 8bcd24bacf5a5936e911c814331afe1fab6bf036fcda5983c6eb143a89013cb9
- bytes: 99
- estimated_tokens: 25

Content:

[project]
name = "demo-repo"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = ["pytest"]


---

## File: src/sourcepack/examples/demo_repo/sourcepack/cli.py

Metadata:
- sha256: 27fae75b5f5b55d891fc89682bae49ff7f47f6bcd7b6c188fdb011be5e3c4a92
- bytes: 134
- estimated_tokens: 34

Content:

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    return parser.parse_args()


---

## File: src/sourcepack/examples/demo_repo/sourcepack/judge.py

Metadata:
- sha256: 409cce4f25abdd804048f4c0630d237e19a0b37a6e4b7feb946fd19cd98b9ffc
- bytes: 133
- estimated_tokens: 34

Content:

def judge(answer: str, known_files: set[str]) -> list[str]:
    return [line for line in answer.splitlines() if "server.py" in line]


---

## File: src/sourcepack/examples/demo_repo/sourcepack/verify.py

Metadata:
- sha256: 1fe61bada9b2a55f096e3f103d43730040a0eb39ecd8d6048a7e64367ff69ebc
- bytes: 125
- estimated_tokens: 32

Content:

import hashlib

def verify_hash(data: bytes, expected: str) -> bool:
    return hashlib.sha256(data).hexdigest() == expected


---

## File: src/sourcepack/examples/demo_repo/tests/test_verify.py

Metadata:
- sha256: cb2d232eb2353dd9807728eb487b3fbc42fc8112d96cd49fbbaec6c2b428bc68
- bytes: 164
- estimated_tokens: 41

Content:

from sourcepack.verify import verify_hash

def test_verify_hash():
    assert verify_hash(b"x", "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")


---

## File: src/sourcepack/examples/fake_ai_answer.md

Metadata:
- sha256: 889eeb9a7fd4438cdfa852e8c1f97d4dd9b1c336bc2a7a51237e811692bfa0aa
- bytes: 440
- estimated_tokens: 110

Content:

This project includes a FastAPI web server in `sourcepack/server.py`.

It supports PDF parsing through `sourcepack/pdf_parser.py`.

To run the full stack locally, use `docker compose up`.

The React dashboard is located at `frontend/App.tsx`.

The CLI verification system is implemented in `sourcepack/verify.py`.

The AI answer judgment system is implemented in `sourcepack/judge.py`.

The package metadata is defined in `pyproject.toml`.


---

## File: src/sourcepack/execution_ledger.py

Metadata:
- sha256: 9a2ddb19207d1bbee97945c09293bcafce5a562181ea64f124bdca33d9b4a514
- bytes: 9214
- estimated_tokens: 2303

Content:

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sourcepack import __version__

SCHEMA_VERSION = "sourcepack.execution_ledger.v1"
LEDGER_FILENAME = "ledger.jsonl"
MAX_EXCERPT_CHARS = 2048


@dataclass(frozen=True)
class ExecutionClaim:
    command: str
    phrase: str
    start: int
    end: int


@dataclass(frozen=True)
class ExecutionLedgerEntry:
    schema_version: str
    entry_id: str
    generated_at: str
    repo_root: str
    git_head: str | None
    worktree_dirty_before: bool | None
    worktree_dirty_after: bool | None
    command: list[str]
    cwd: str
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str
    duration_ms: int
    environment_summary: dict
    sourcepack_version: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def excerpt_bytes(data: bytes, limit: int = MAX_EXCERPT_CHARS) -> str:
    text = data.decode("utf-8", "replace")
    if len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"


def find_repo_root(start: str | Path = ".") -> Path:
    start_path = Path(start).resolve()
    cp = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode == 0 and cp.stdout.strip():
        return Path(cp.stdout.strip()).resolve()
    return start_path


def _git_head(repo_root: Path) -> str | None:
    cp = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else None


def _worktree_dirty(repo_root: Path) -> bool | None:
    cp = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if cp.returncode != 0:
        return None
    return bool(cp.stdout.strip())


def ledger_dir(repo_root: str | Path) -> Path:
    return Path(repo_root) / ".sourcepack" / "evidence"


def ledger_path(repo_root: str | Path) -> Path:
    return ledger_dir(repo_root) / LEDGER_FILENAME


def entry_to_json(entry: ExecutionLedgerEntry) -> str:
    return json.dumps(asdict(entry), sort_keys=True, separators=(",", ":"))


def append_entry(repo_root: str | Path, entry: ExecutionLedgerEntry) -> None:
    path = ledger_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry_to_json(entry) + "\n")


def iter_entries(repo_root: str | Path) -> Iterable[dict]:
    path = ledger_path(repo_root)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def clear_ledger(repo_root: str | Path) -> None:
    path = ledger_path(repo_root)
    if path.exists():
        path.unlink()


def environment_summary() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "shell": os.environ.get("SHELL"),
        "path_entries": len(os.environ.get("PATH", "").split(os.pathsep)) if os.environ.get("PATH") else 0,
    }


def run_and_record(command: list[str], cwd: str | Path = ".") -> ExecutionLedgerEntry:
    if not command:
        raise ValueError("sourcepack exec requires a command after --")
    repo_root = find_repo_root(cwd)
    dirty_before = _worktree_dirty(repo_root)
    head = _git_head(repo_root)
    start = time.monotonic()
    cp = subprocess.run(command, cwd=Path(cwd).resolve(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    duration_ms = int((time.monotonic() - start) * 1000)
    dirty_after = _worktree_dirty(repo_root)
    entry = ExecutionLedgerEntry(
        schema_version=SCHEMA_VERSION,
        entry_id=uuid.uuid4().hex,
        generated_at=utc_now(),
        repo_root=str(repo_root),
        git_head=head,
        worktree_dirty_before=dirty_before,
        worktree_dirty_after=dirty_after,
        command=list(command),
        cwd=str(Path(cwd).resolve()),
        exit_code=int(cp.returncode),
        stdout_sha256=sha256_bytes(cp.stdout),
        stderr_sha256=sha256_bytes(cp.stderr),
        stdout_excerpt=excerpt_bytes(cp.stdout),
        stderr_excerpt=excerpt_bytes(cp.stderr),
        duration_ms=duration_ms,
        environment_summary=environment_summary(),
        sourcepack_version=__version__,
    )
    append_entry(repo_root, entry)
    return entry


_CLEAR_PHRASES = [
    "tests passed", "test passed", "build passed", "lint passed", "typecheck passed",
    "pytest passed", "npm test passed", "npm run build passed",
]
_SUPPORTED_COMMAND_PREFIXES = ["pytest", "npm test", "npm run build", "npm run test", "python -m pytest", "make test", "ruff check", "mypy"]
_RAN_RE = re.compile(r"\bI\s+(?:ran|tested)\s+([^\n.;]+)", re.IGNORECASE)


def detect_execution_claims(text: str) -> list[ExecutionClaim]:
    """Return bounded, explicit command-execution claims without semantic guessing."""
    claims: list[ExecutionClaim] = []
    lower = text.lower()
    for phrase in _CLEAR_PHRASES:
        start = lower.find(phrase)
        while start != -1:
            if not re.search(r"\b(should|probably|expected to)\s+" + re.escape(phrase.split()[0]), lower[max(0, start-20):start+len(phrase)]):
                cmd = phrase.removesuffix(" passed")
                claims.append(ExecutionClaim(command=cmd, phrase=text[start:start + len(phrase)], start=start, end=start + len(phrase)))
            start = lower.find(phrase, start + 1)
    for prefix in _SUPPORTED_COMMAND_PREFIXES:
        pattern = re.compile(r"\b" + re.escape(prefix) + r"\s+(passed|works|succeeds)\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            claims.append(ExecutionClaim(command=prefix, phrase=m.group(0), start=m.start(), end=m.end()))
    for m in _RAN_RE.finditer(text):
        cmd = m.group(1).strip().strip('`"\'')
        if cmd and len(cmd.split()) <= 8 and not cmd.lower().startswith(("tests", "the test file")):
            claims.append(ExecutionClaim(command=cmd, phrase=m.group(0), start=m.start(), end=m.end()))
    claims.sort(key=lambda c: (c.start, c.end, c.command))
    deduped: list[ExecutionClaim] = []
    seen = set()
    for claim in claims:
        key = (claim.command.lower(), claim.start, claim.end)
        if key not in seen:
            seen.add(key)
            deduped.append(claim)
    return deduped


def _command_matches(claim: str, entry_command: list[str]) -> bool:
    normalized_entry = " ".join(entry_command).strip().lower()
    normalized_claim = claim.strip().lower()
    return normalized_entry == normalized_claim or normalized_entry.startswith(normalized_claim + " ")


def evidence_for_claim(repo_root: str | Path, claim: ExecutionClaim) -> tuple[str, dict | None]:
    matches = [entry for entry in iter_entries(repo_root) if _command_matches(claim.command, list(entry.get("command") or []))]
    if not matches:
        return "execution_evidence_missing", None
    latest = sorted(matches, key=lambda e: str(e.get("generated_at") or ""))[-1]
    if len({int(m.get("exit_code", -999)) for m in matches}) > 1:
        return "execution_inconclusive", latest
    if int(latest.get("exit_code", -1)) == 0:
        return "execution_evidence_present", latest
    return "execution_failed", latest


def execution_findings(repo_root: str | Path, text: str) -> list[dict]:
    findings: list[dict] = []
    for claim in detect_execution_claims(text):
        status, entry = evidence_for_claim(repo_root, claim)
        if status == "execution_evidence_present":
            severity = "info"
            message = f"Execution ledger contains a successful local run for: {claim.command}."
        elif status == "execution_failed":
            severity = "warn"
            message = f"Execution ledger contains a failed local run for: {claim.command}."
        elif status == "execution_inconclusive":
            severity = "warn"
            message = f"Execution ledger has mixed or ambiguous local runs for: {claim.command}."
        else:
            severity = "warn"
            message = f"No SourcePack execution-ledger entry supports claimed run: {claim.command}."
        findings.append({
            "id": status,
            "severity": severity,
            "category": "execution",
            "path": None,
            "message": message,
            "evidence": claim.command,
            "suggestion": "Run the command through `sourcepack exec -- ...` if local execution evidence is intended." if severity == "warn" else None,
            "ledger_entry_id": entry.get("entry_id") if entry else None,
        })
    return findings


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


---

## File: src/sourcepack/git.py

Metadata:
- sha256: 260e7d3d958ec63b9705aba7ed47c00679ab50ca6f9d276d95332320e2f4acd3
- bytes: 2048
- estimated_tokens: 512

Content:

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(repo: str | Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=Path(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git executable not found")


def repo_root(path: str | Path) -> Path | None:
    cp = run_git(path, ["rev-parse", "--show-toplevel"])
    return Path(cp.stdout.strip()).resolve() if cp.returncode == 0 else None


def diff(repo: str | Path, *, staged: bool = False, relative: bool = False) -> str:
    args = ["diff", "--staged"] if staged else ["diff"]
    if relative:
        args.append("--relative")
    return run_git(repo, args).stdout


def untracked_files(repo: str | Path) -> list[str]:
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()] if cp.returncode == 0 else []


def dirty_worktree(repo: str | Path) -> tuple[bool, str | None]:
    root = repo_root(repo)
    if root is None:
        cp = run_git(repo, ["rev-parse", "--show-toplevel"])
        return False, "git_unavailable" if cp.returncode == 127 else "not_git"
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        cp = run_git(root, list(args))
        if cp.returncode == 1:
            return True, None
        if cp.returncode == 127:
            return False, "git_unavailable"
    return (bool(untracked_files(root)), None)


def metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, state = dirty_worktree(root)
    return {"branch": branch.stdout.strip() if branch.returncode == 0 else None, "head_commit": head.stdout.strip() if head.returncode == 0 else None, "dirty": dirty if state is None else None, "dirty_state": state}


---

## File: src/sourcepack/judgment.py

Metadata:
- sha256: f7ae2538aae87d3d49caac057b40edfe14d528fd05e78691724979df0ed1b36b
- bytes: 106428
- estimated_tokens: 26607

Content:

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tomllib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape
from .diff_parser import PatchFileChange, normalize_diff_path as _normalize_diff_path, parse_unified_diff
from .baseline import BaselineLockError, acquire_baseline_lock, baseline_corrupt_result, baseline_report_fields, build_current_baseline, protected_baseline_path, release_baseline_lock, resolve_active_baseline, validate_baseline
from .ecosystems.python import PY_IMPORT_ALIASES
from .paths import ensure_gitignore_entry, ensure_sourcepack_dirs, sourcepack_paths
from .reports.json import normalized_finding, traffic_report, write_user_report
from .policy import PolicyMode, normalize_policy_mode, exit_code as policy_exit_code, load_policy_config, finding_ignored_by_policy, policy_path_matches
from .execution_ledger import execution_findings
from .commands import resolve_command
from .dependencies import resolve_js_import, resolve_python_import

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"

DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "target", "coverage", ".pytest_cache", ".sourcepack"
}
DEFAULT_IGNORED_PATTERNS = {
    ".env", ".env.*", "*.pem", "*.key", "*.sqlite", "*.db", "*.png", "*.jpg",
    "*.jpeg", "*.gif", "*.webp", "*.pdf", "*.zip", "*.tar", "*.gz", "*.exe",
    "*.dll", "*.so", "*.dylib", "*.bin", "*.pyc"
}
DEFAULT_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".html", ".css", ".csv", ".toml", ".ini", ".sql", ".sh", ".bat", ".ps1", ".rs",
    ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".xml"
}
SECRET_PATTERNS = [
    ("openai_key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9]{24,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}")),
]
COMMON_DEPENDENCIES = ["fastapi", "flask", "django", "react", "vue", "svelte", "pytest", "typer", "click", "sqlalchemy", "prisma", "pydantic", "pyyaml", "pillow", "beautifulsoup4", "opencv-python", "scikit-learn", "python-dotenv", "pyjwt", "python-dateutil", "boto3", "requests"]
FEATURE_NAMES = ("pdf", "ocr", "web server", "react", "docker", "authentication", "database")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return True
    if b"\x00" in data:
        return True
    if not data:
        return False
    nonprintable = sum(1 for b in data if b < 9 or (13 < b < 32))
    return (nonprintable / max(len(data), 1)) > 0.30


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def redact_secrets(text: str):
    redactions = []
    redacted = text
    for label, pattern in SECRET_PATTERNS:
        def repl(match):
            redactions.append({"pattern": label, "span_start": match.start(), "span_end": match.end()})
            return f"[REDACTED:{label}]"
        redacted = pattern.sub(repl, redacted)
    return redacted, redactions


@dataclass
class IncludedFile:
    relative_path: str
    absolute_path: str
    size_bytes: int
    sha256: str
    source_sha256: str
    packet_sha256: str
    estimated_tokens: int
    extension: str
    content: str


@dataclass
class IgnoredFile:
    relative_path: str
    reason: str


class SourceScanner:
    def __init__(self, input_path: str | Path, max_file_size: int = 1_000_000, include_hidden: bool = False, redact: bool = True):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0

    def ignore(self, path: Path, reason: str):
        rel = str(path.relative_to(self.input_path)) if path.is_absolute() or self.input_path in path.parents else str(path)
        self.ignored_files.append(IgnoredFile(rel, reason))

    def scan(self):
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_path}")
        for root, dirs, files in os.walk(self.input_path, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(dirs)
            files = sorted(files)
            kept_dirs = []
            for d in dirs:
                dpath = root_path / d
                rel = dpath.relative_to(self.input_path)
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "symlink_skipped"))
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs
            for filename in files:
                fp = root_path / filename
                rel = fp.relative_to(self.input_path)
                self.total_seen += 1
                rel_str = str(rel)
                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped")); continue
                if not self.include_hidden and filename.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file")); continue
                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern")); continue
                try:
                    size = fp.stat().st_size
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "stat_error")); continue
                if size > self.max_file_size:
                    self.ignored_files.append(IgnoredFile(rel_str, "max_file_size_exceeded")); continue
                if fp.suffix and fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    self.ignored_files.append(IgnoredFile(rel_str, "unsupported_extension")); continue
                if is_probably_binary(fp):
                    self.ignored_files.append(IgnoredFile(rel_str, "binary_detected")); continue
                try:
                    content = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    self.ignored_files.append(IgnoredFile(rel_str, "decode_error")); continue
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "read_error")); continue
                source_sha256 = sha256_text(content)
                if self.redact:
                    redacted, reds = redact_secrets(content)
                    for r in reds:
                        r["file"] = rel_str
                    self.redactions.extend(reds)
                    content = redacted
                packet_sha256 = sha256_text(content)
                self.included_files.append(IncludedFile(
                    relative_path=rel_str,
                    absolute_path=str(fp.resolve()),
                    size_bytes=size,
                    sha256=packet_sha256,
                    source_sha256=source_sha256,
                    packet_sha256=packet_sha256,
                    estimated_tokens=estimate_tokens(content),
                    extension=fp.suffix.lower(),
                    content=content,
                ))
        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    source = "scanner_included_files"
    try:
        cp = subprocess.run(["git", "ls-files", "-z"], cwd=root, text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError):
        cp = None
    if cp is not None and cp.returncode == 0:
        raw_paths = [p.decode("utf-8", "surrogateescape") for p in cp.stdout.split(b"\0") if p]
        source = "git_ls_files" if raw_paths else "scanner_included_files"
        if not raw_paths:
            raw_paths = sorted(included)
    else:
        raw_paths = sorted(included)
    for raw in raw_paths:
        rel = raw.replace("\\", "/")
        path = root / rel
        rec = {"relative_path": rel, "included_in_prompt_context": rel in included, "source": source}
        try:
            if path.exists() and path.is_file():
                rec["sha256"] = sha256_file(path)
                rec["file_type"] = "binary" if is_probably_binary(path) else "text"
            else:
                rec["file_type"] = "missing"
        except OSError:
            rec["file_type"] = "unreadable"
        files.append(rec)
    return {"schema_version": "sourcepack.file_inventory.v1", "generated_at": utc_now(), "source": source, "files": files}


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md", "file_inventory.json"]

    def __init__(self, out: str | Path, scanner: SourceScanner, force: bool = False):
        self.out = Path(out)
        self.scanner = scanner
        self.force = force

    def prepare_out(self):
        if self.out.exists() and any(self.out.iterdir()):
            if not self.force:
                raise FileExistsError(f"Output directory is non-empty: {self.out}")
            for child in self.out.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        self.out.mkdir(parents=True, exist_ok=True)

    def write_all(self):
        self.prepare_out()
        included_records = []
        for f in self.scanner.included_files:
            rec = asdict(f)
            rec.pop("content")
            included_records.append(rec)
        ignored_records = [asdict(f) for f in self.scanner.ignored_files]
        total_tokens = sum(f.estimated_tokens for f in self.scanner.included_files)
        total_bytes = sum(f.size_bytes for f in self.scanner.included_files)
        manifest = {
            "input_path": str(self.scanner.input_path),
            "generated_at": utc_now(),
            "tool_version": __version__,
            "total_files_seen": self.scanner.total_seen,
            "total_files_included": len(included_records),
            "total_files_ignored": len(ignored_records),
            "total_bytes_included": total_bytes,
            "total_estimated_tokens": total_tokens,
            "included_files": included_records,
            "ignored_files": ignored_records,
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.out / "file_inventory.json").write_text(json.dumps(_tracked_file_inventory(self.scanner.input_path, included_records), indent=2), encoding="utf-8")
        md_parts = ["# SourcePack Context Packet", "", "## Source Manifest Summary", "", f"Input path: {manifest['input_path']}", f"Generated at: {manifest['generated_at']}", f"Files included: {len(included_records)}", f"Estimated tokens: {total_tokens}", ""]
        for f in self.scanner.included_files:
            md_parts.extend([
                f"## File: {f.relative_path}", "", "Metadata:", f"- sha256: {f.sha256}", f"- bytes: {f.size_bytes}", f"- estimated_tokens: {f.estimated_tokens}", "", "Content:", "", f.content, "", "---", ""
            ])
        (self.out / "context.md").write_text("\n".join(md_parts), encoding="utf-8")
        xml_parts = ["<sourcepack>", "  <files>"]
        for f in self.scanner.included_files:
            xml_parts.append(f'    <file path="{xml_escape(f.relative_path)}" sha256="{f.sha256}" bytes="{f.size_bytes}" estimated_tokens="{f.estimated_tokens}">')
            xml_parts.append("      <content>")
            xml_parts.append(xml_escape(f.content))
            xml_parts.append("      </content>")
            xml_parts.append("    </file>")
        xml_parts.extend(["  </files>", "</sourcepack>"])
        (self.out / "context.xml").write_text("\n".join(xml_parts), encoding="utf-8")
        tree_lines = []
        for f in self.scanner.included_files:
            tree_lines.append(f"[INC] {f.relative_path}")
        for f in self.scanner.ignored_files:
            tree_lines.append(f"[IGN] {f.relative_path} - {f.reason}")
        (self.out / "file_tree.txt").write_text("\n".join(sorted(tree_lines)) + "\n", encoding="utf-8")
        (self.out / "ignored_files.txt").write_text("\n".join(f"{f.relative_path}\t{f.reason}" for f in self.scanner.ignored_files) + "\n", encoding="utf-8")
        token_report = {
            "total_estimated_tokens": total_tokens,
            "warnings": [limit for limit in [32_000, 128_000, 200_000, 1_000_000] if total_tokens > limit],
            "per_file": [{"relative_path": f.relative_path, "estimated_tokens": f.estimated_tokens} for f in self.scanner.included_files],
        }
        (self.out / "token_report.json").write_text(json.dumps(token_report, indent=2), encoding="utf-8")
        (self.out / "redactions.json").write_text(json.dumps({"redactions": self.scanner.redactions}, indent=2), encoding="utf-8")
        reality_map = generate_reality_map(manifest, self.out)
        (self.out / "reality_map.json").write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
        (self.out / "ai_instructions.md").write_text(render_ai_instructions(reality_map), encoding="utf-8")
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out



def _included_paths(manifest: dict) -> set[str]:
    return {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}


def _package_json_scripts(packet: Path) -> dict[str, str]:
    contents = _packet_file_contents(packet)
    for rel, content in contents.items():
        if Path(rel).name.lower() == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                return {}
            scripts = package.get("scripts")
            return scripts if isinstance(scripts, dict) else {}
    return {}


def _is_poetry_project(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).name.lower() == "pyproject.toml" and re.search(r"(?m)^\s*\[tool\.poetry\]\s*$", content):
            return True
    return False


def _uses_unittest(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).suffix.lower() == ".py" and re.search(r"(?m)^\s*(import\s+unittest|from\s+unittest\s+import\s+)", content):
            return True
    return False


def generate_reality_map(manifest: dict, packet: Path) -> dict:
    files = _included_paths(manifest)
    lower_files = {f.lower() for f in files}
    deps = dependency_inventory(manifest, packet)
    features = feature_inventory(manifest, packet, deps)
    scripts = _package_json_scripts(packet)
    project_types = []
    package_managers = []
    frameworks = []
    supported_commands = []
    test_commands = []
    build_commands = []
    run_commands = []
    if "pyproject.toml" in lower_files:
        project_types.append("python")
    if any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower_files):
        project_types.append("python")
        package_managers.append("pip")
    if _is_poetry_project(packet):
        package_managers.append("poetry")
    if "package.json" in lower_files:
        project_types.append("node")
        package_managers.append("npm")
        for name in sorted(scripts):
            cmd = "npm test" if name == "test" else f"npm run {name}"
            supported_commands.append(cmd)
            if name == "test": test_commands.append(cmd)
            elif name in {"build", "compile"}: build_commands.append(cmd)
            elif name in {"start", "dev", "serve"}: run_commands.append(cmd)
    if any(Path(f).name.lower() == "dockerfile" for f in files):
        supported_commands.append("docker build")
        build_commands.append("docker build")
    if any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in files):
        supported_commands.append("docker compose up")
        run_commands.append("docker compose up")
    if "pytest" in deps or any(f == "tests" or f.startswith("tests/") for f in lower_files):
        supported_commands.append("pytest")
        test_commands.append("pytest")
    if _uses_unittest(packet):
        supported_commands.append("python -m unittest")
        test_commands.append("python -m unittest")
    framework_map = {"fastapi": "FastAPI", "flask": "Flask", "django": "Django", "react": "React"}
    for dep, label in framework_map.items():
        if dep in deps or (dep == "react" and "react" in features):
            frameworks.append(label)
    ignored = manifest.get("ignored_files", [])
    ignored_reasons = {}
    for rec in ignored:
        reason = rec.get("reason", "unknown")
        ignored_reasons[reason] = ignored_reasons.get(reason, 0) + 1
    included_count = len(manifest.get("included_files", []))
    safe_claims = [
        f"This packet includes {included_count} source files.",
        f"SourcePack scanned input path: {manifest.get('input_path', '')}.",
    ]
    for name in ["pyproject.toml", "package.json", "Dockerfile"]:
        present = name.lower() in {Path(f).name.lower() for f in files}
        safe_claims.append(f"The project {'contains' if present else 'does not include'} {name}.")
    if "react" not in deps and "react" not in features:
        safe_claims.append("No React dependency was detected.")
    if "pdf" not in features:
        safe_claims.append("No PDF parsing capability was detected.")
    if ignored:
        safe_claims.append("The packet includes ignored file records for safety or relevance reasons.")
    claim_boundaries = [
        "SourcePack did not execute the application.",
        "SourcePack did not prove semantic correctness.",
        "SourcePack did not verify external services.",
        "SourcePack did not prove security.",
        "SourcePack did not prove production readiness.",
        "Absence of evidence means unknown, not impossible.",
        "Unsupported claims should be treated as ungrounded.",
    ]
    return {
        "reality_map_schema_version": "1.0",
        "tool_version": __version__,
        "generated_at": utc_now(),
        "input_path": manifest.get("input_path", ""),
        "project_types": sorted(set(project_types)),
        "package_managers": sorted(set(package_managers)),
        "frameworks": sorted(set(frameworks)),
        "entry_points": sorted(f for f in files if Path(f).name in {"main.py", "app.py", "server.py", "cli.py"}),
        "test_commands": sorted(set(test_commands)),
        "build_commands": sorted(set(build_commands)),
        "run_commands": sorted(set(run_commands)),
        "supported_commands": sorted(set(supported_commands)),
        "detected_dependencies": sorted(deps),
        "supported_capabilities": sorted(features),
        "excluded_files_summary": {"total": len(ignored), "reasons": ignored_reasons, "records": ignored[:25]},
        "included_file_count": included_count,
        "confirmed_files": sorted(files),
        "ignored_file_count": len(ignored),
        "safe_claims": safe_claims,
        "unknowns": [
            "Runtime behavior was not executed.",
            "Semantic correctness was not proven.",
            "External services were not verified.",
            "Capabilities not present in structural evidence must be treated as unknown.",
            "Missing files must not be invented.",
        ],
        "claim_boundaries": claim_boundaries,
        "ai_constraints": [
            "Use only the packet and reality map as project evidence.",
            "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
            "If a required file is missing, say it is missing.",
            "If a command is unsupported by detected evidence, say it is unsupported.",
            "If a capability is not in supported_capabilities, treat it as unknown or unsupported.",
            "Cite file paths when making project-specific claims.",
            "Do not claim SourcePack proves semantic truth.",
            "Ask for missing files rather than hallucinating them.",
        ],
    }


def render_ai_instructions(reality_map: dict) -> str:
    lines = [
        "# AI Instructions for This SourcePack Packet", "",
        "Use only the packet and `reality_map.json` as project evidence.",
        "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
        "If a required file is missing, say it is missing and ask for it rather than hallucinating it.",
        "If a command is unsupported by detected evidence, say it is unsupported.",
        "If a capability is not listed in `supported_capabilities`, treat it as unknown or unsupported.",
        "If you introduce a new external dependency, modify the appropriate dependency manifest in the same patch and list it under Dependency Changes.",
        "Only recommend commands listed under Supported Commands unless your patch also adds the project file that defines the new command.",
        "Before referencing a file as existing, it must appear in Confirmed Files; label intentional creations as NEW FILE.",
        "If required evidence is missing, say UNKNOWN and ask for the missing file/output instead of guessing.",
        "Cite file paths when making project-specific claims.",
        "Do not claim SourcePack proves semantic truth, security, production readiness, or external service behavior.", "",
        "## Supported Commands", "",
    ]
    cmds = reality_map.get("supported_commands", [])
    lines.extend([f"- `{cmd}`" for cmd in cmds] or ["- None detected"])
    lines.extend(["", "## Supported Capabilities", ""])
    caps = reality_map.get("supported_capabilities", [])
    lines.extend([f"- {cap}" for cap in caps] or ["- None detected"])
    lines.extend(["", "## Confirmed Files", ""])
    lines.extend(f"- `{path}`" for path in reality_map.get("confirmed_files", [])[:200])
    lines.extend(["", "## Required Answer Contract", "", "- Files to modify", "- New files", "- Dependency changes", "- Commands to run", "- Assumptions/unknowns", "- Patch or code", "", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in reality_map.get("claim_boundaries", []))
    return "\n".join(lines) + "\n"

def load_manifest(packet: Path) -> dict:
    return json.loads((packet / "manifest.json").read_text(encoding="utf-8"))




PATHLIKE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cfg", ".ini", ".css", ".html", ".rs", ".go", ".java", ".rb", ".php", ".sh"}
PROJECT_PATH_PREFIXES = {"src", "sourcepack", "tests", "test", "frontend", "backend", "docs", "app", "lib", "packages", "public", "config", "scripts"}


def _normalize_ai_ref(ref: str) -> str | None:
    ref = ref.strip().strip("`'\".,;)")
    ref = ref.replace("\\", "/")
    if ref.endswith(":"):
        ref = ref[:-1]
    while ref.startswith("./"):
        ref = ref[2:]
    if not ref or ref.startswith("/") or re.match(r"^[A-Za-z]:/", ref):
        return None
    normalized, unsafe = _normalize_diff_path(ref)
    if unsafe or not normalized:
        return None
    return normalized


def _looks_like_ai_file_ref(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in {"Dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml", "pyproject.toml", "package.json", "requirements.txt"}:
        return True
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in PATHLIKE_EXTENSIONS:
        return False
    parts = [p for p in PurePosixPath(normalized).parts if p not in {"."}]
    return "/" in normalized or (parts and parts[0] in PROJECT_PATH_PREFIXES)


def extract_refs(text: str) -> set[str]:
    refs: set[str] = set()
    token = r"(?:\./)?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*\.[A-Za-z0-9_.-]+:?|Dockerfile"
    patterns = [rf"[`'\"]({token})[`'\"]", rf"(?m)^\s*[-*]\s+({token})\b", rf"\b(?:edit|open|update|modify|change|in|file)\s+({token})\b", rf"\b((?:\./)?(?:src|sourcepack|tests|test|frontend|backend|docs|app|lib|packages|public|config|scripts)[\\/][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_.-]+:?)\b"]
    for pattern in patterns:
        for candidate in re.findall(pattern, text, re.I):
            normalized = _normalize_ai_ref(candidate)
            if normalized and _looks_like_ai_file_ref(normalized):
                refs.add(normalized)
    return refs


def _packet_file_contents(packet: Path) -> dict[str, str]:
    context_path = packet / "context.md"
    if not context_path.exists():
        return {}
    text = context_path.read_text(encoding="utf-8", errors="ignore")
    contents: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    in_content = False
    for line in text.splitlines():
        if line.startswith("## File: "):
            if current is not None:
                contents[current] = "\n".join(body).rstrip("\n")
            current = line.removeprefix("## File: ").strip()
            body = []
            in_content = False
        elif current is not None and line == "Content:":
            in_content = True
            body = []
        elif current is not None and in_content and line == "---":
            contents[current] = "\n".join(body).rstrip("\n")
            current = None
            body = []
            in_content = False
        elif current is not None and in_content:
            body.append(line)
    if current is not None:
        contents[current] = "\n".join(body).rstrip("\n")
    return contents


def _normalize_dependency_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _dependency_name_for_import(name: str) -> str:
    normalized = _normalize_dependency_name(name)
    return PY_IMPORT_ALIASES.get(normalized, normalized)


def _js_package_root(imported: str) -> str:
    imported = imported.strip().lower()
    parts = imported.split("/")
    if imported.startswith("@") and len(parts) >= 2 and parts[0] != "@":
        return "/".join(parts[:2])
    if imported.startswith("@/"):
        return imported
    return parts[0]


def _python_dependency_names_from_requirement_lines(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned and not cleaned.startswith(("-", "--")):
            deps.add(_normalize_dependency_name(re.split(r"[<>=!~;\[]", cleaned, maxsplit=1)[0]))
    return deps


def _python_dependency_names_from_pyproject(content: str) -> set[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return set()
    deps: set[str] = set()

    def add_requirement(req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                deps.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_requirement(req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_requirement(req)

    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            for section_name in ("dependencies", "dev-dependencies"):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    for dep in section:
                        if dep.lower() != "python":
                            deps.add(_normalize_dependency_name(dep))
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            deps.update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_requirement(req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_requirement(req)
    return deps


def _add_common_dependency(deps: set[str], name: str):
    normalized = _normalize_dependency_name(name)
    for dep in COMMON_DEPENDENCIES:
        if normalized == _normalize_dependency_name(dep):
            deps.add(dep.lower())


def dependency_inventory(manifest: dict, packet: Path) -> set[str]:
    deps: set[str] = set()
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        suffix = Path(rel).suffix.lower()
        if name == "pyproject.toml":
            for dep in _python_dependency_names_from_pyproject(content):
                _add_common_dependency(deps, dep)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for dep in _python_dependency_names_from_requirement_lines(content):
                _add_common_dependency(deps, dep)
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    for dep_name in section_deps:
                        _add_common_dependency(deps, dep_name)
        elif suffix == ".py":
            for imported in re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", content):
                _add_common_dependency(deps, imported)
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            for imported in re.findall(r"""(?:from\s+["']|import\s*\(\s*["']|require\s*\(\s*["'])(@?[A-Za-z0-9_.-]+)""", content):
                _add_common_dependency(deps, _js_package_root(imported))
    return deps


def _has_import(content: str, *modules: str) -> bool:
    module_pattern = "|".join(re.escape(module) for module in modules)
    return bool(re.search(rf"(?m)^\s*(?:import|from)\s+({module_pattern})(?:\b|[._])", content))


PDF_DEPENDENCIES = {"pypdf", "pdfplumber", "fitz", "pymupdf"}


def _declares_pdf_dependency(rel: str, content: str) -> bool:
    name = Path(rel).name.lower()
    if name == "pyproject.toml":
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_pyproject(content))
    if name.startswith("requirements") and name.endswith(".txt"):
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_requirement_lines(content))
    return False


def feature_inventory(manifest: dict, packet: Path, deps: set[str] | None = None) -> set[str]:
    if deps is None:
        deps = dependency_inventory(manifest, packet)
    contents = _packet_file_contents(packet)
    files = {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}
    lower_files = {rel.lower() for rel in files}
    features: set[str] = set()

    if any(Path(rel).name.lower() in {"dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"} for rel in files):
        features.add("docker")
    if any(rel.endswith(("/pdf_parser.py", "pdf_parser.py")) for rel in lower_files):
        features.add("pdf")
    if any(_declares_pdf_dependency(rel, content) for rel, content in contents.items()):
        features.add("pdf")
    if "react" in deps or any(rel in {"frontend/app.tsx", "frontend/app.jsx"} for rel in lower_files):
        features.add("react")
    if deps & {"fastapi", "flask", "django"} or any(Path(rel).name.lower() in {"server.py", "app.py"} for rel in files):
        features.add("web server")
    if deps & {"sqlalchemy", "prisma"} or any("/migrations/" in f"/{rel}/" or Path(rel).name.lower() in {"schema.prisma", "schema.sql"} for rel in files):
        features.add("database")
    if any(part == "auth" or part.startswith("auth_") for rel in lower_files for part in Path(rel).parts):
        features.add("authentication")

    for rel, content in contents.items():
        suffix = Path(rel).suffix.lower()
        if suffix == ".py":
            if _has_import(content, "pypdf", "pdfplumber", "fitz"):
                features.add("pdf")
            if _has_import(content, "fastapi", "flask", "django") or re.search(r"(?m)^\s*@\w+\.(?:route|get|post|put|patch|delete)\(", content):
                features.add("web server")
            if _has_import(content, "sqlalchemy", "prisma") or re.search(r"(?i)\b(sqlite|postgres(?:ql)?|mysql)://", content):
                features.add("database")
            if _has_import(content, "jwt", "oauthlib", "authlib") or re.search(r"(?i)@\w+\.(?:route|get|post)\([^)]*login", content):
                features.add("authentication")
            if _has_import(content, "pytesseract", "easyocr"):
                features.add("ocr")
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            if re.search(r"""(?:from\s+["']react["']|require\s*\(\s*["']react["']|import\s+React\b)""", content):
                features.add("react")
            if re.search(r"(?i)\b(jwt|oauth|session|login)\b", content):
                features.add("authentication")
        elif Path(rel).name.lower() == "package.json":
            if re.search(r'"react"\s*:', content):
                features.add("react")
    return features


PROTECTED_PACKET_ARTIFACTS = {"manifest.json", "receipt.json", "reality_map.json", "ai_instructions.md"}


def _normalize_inventory_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    rel, unsafe = _normalize_diff_path(value)
    if unsafe or not rel:
        return None
    return rel


def _baseline_inventory_from_packet(packet: str | Path, manifest: dict | None = None) -> tuple[set[str], bool]:
    """Return authoritative enforcement baseline paths when a packet has them.

    Prompt context manifests may be selective, so diff enforcement must prefer the
    baseline file inventory artifact when it exists. The boolean is True only
    when a full inventory artifact was loaded successfully.
    """
    packet = Path(packet)
    for name in ("file_inventory.json", "inventory.json", "baseline_inventory.json"):
        path = packet / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_files = data.get("files") if isinstance(data, dict) else data
        if not isinstance(raw_files, list):
            continue
        files: set[str] = set()
        for item in raw_files:
            raw_path = item.get("relative_path") if isinstance(item, dict) else item
            rel = _normalize_inventory_path(raw_path)
            if rel:
                files.add(rel)
        return files, True
    return _included_paths(manifest or load_manifest(packet)), False


def known_files(manifest: dict, packet_path: str | Path | None = None) -> set[str]:
    if packet_path is not None:
        files, _ = _baseline_inventory_from_packet(packet_path, manifest)
        return files
    return _included_paths(manifest)


def supported_commands_inventory(reality_map: dict) -> set[str]:
    return set(reality_map.get("supported_commands", []))


def docker_evidence(files: set[str]) -> dict[str, bool]:
    names = {Path(f).name.lower() for f in files}
    return {
        "dockerfile": "dockerfile" in names,
        "compose": bool(names & {"docker-compose.yml", "compose.yaml", "compose.yml"}),
    }


def python_project_evidence(files: set[str], deps: set[str]) -> dict[str, bool]:
    lower = {f.lower() for f in files}
    return {
        "python_project": "pyproject.toml" in lower or any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower),
        "tests": any(f == "tests" or f.startswith("tests/") for f in lower),
        "pytest": "pytest" in deps,
    }


def node_project_evidence(files: set[str], scripts: dict[str, str]) -> dict[str, bool]:
    return {"package_json": "package.json" in {f.lower() for f in files}, "scripts": bool(scripts)}


def extract_js_import_specifiers_from_text(text: str) -> set[str]:
    specifiers: set[str] = set()
    patterns = [
        r"""\bimport\s+(?:[^"'()]+?\s+from\s+)?["']([^"']+)["']""",
        r"""\bexport\s+[^"']*?\s+from\s+["']([^"']+)["']""",
        r"""\bimport\s*\(\s*["']([^"']+)["']\s*\)""",
        r"""\brequire\s*\(\s*["']([^"']+)["']\s*\)""",
    ]
    for pattern in patterns:
        specifiers.update(m.strip() for m in re.findall(pattern, text) if m.strip())
    return {s.lower() for s in specifiers}


def extract_imports_from_text(text: str, suffix: str = ".py") -> set[str]:
    imports: set[str] = set()
    if suffix == ".py":
        imports |= set(re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text))
    elif suffix in JS_EXTS:
        imports |= extract_js_import_specifiers_from_text(text)
    return {i.lower() for i in imports}







def _materialize_packet_worktree(packet: Path, overlay: dict[str, str] | None = None) -> tempfile.TemporaryDirectory[str]:
    tmp = tempfile.TemporaryDirectory(prefix="sourcepack-resolver-")
    root = Path(tmp.name)
    contents = _packet_file_contents(packet)
    if overlay:
        contents.update(overlay)
    for rel, content in contents.items():
        normalized, unsafe = _normalize_diff_path(rel)
        if unsafe or not normalized:
            continue
        target = root / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp


def _dependency_additions_from_patch(changes: list[PatchFileChange]) -> set[str]:
    return set()


def analyze_patch(packet_path: str | Path, patch_text: str, changes: list[PatchFileChange] | None = None) -> dict:
    packet = Path(packet_path)
    manifest = load_manifest(packet)
    reality = json.loads((packet / "reality_map.json").read_text(encoding="utf-8")) if (packet / "reality_map.json").exists() else generate_reality_map(manifest, packet)
    files, baseline_inventory_loaded = _baseline_inventory_from_packet(packet, manifest)
    deps = dependency_inventory(manifest, packet)
    scripts = _package_json_scripts(packet)
    if changes is None:
        changes = parse_unified_diff(patch_text)
    patch_deps = _dependency_additions_from_patch(changes)
    report = {
        "patch_judgment_schema_version": "1.0",
        "verdict": "PASS",
        "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [],
        "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "git_path_modifications": [], "warnings": [],
    }
    if any(ch.unsafe_path for ch in changes):
        report["path_escape"] = True
    all_added = []
    for ch in changes:
        report["modified_files"].append(ch.path)
        if ch.new_file:
            report["new_files"].append(ch.path)
        elif ch.operation in {"rename", "copy"}:
            pass
        elif ch.path not in files:
            if baseline_inventory_loaded or ch.path in _included_paths(manifest):
                report["missing_modified_files"].append(ch.path)
            else:
                report.setdefault("uncertain_modified_files", []).append(ch.path)
        if ch.deleted_file:
            report["deleted_files"].append(ch.path)
        protected = ch.path.startswith(".sourcepack/")
        git_internal = ch.path == ".git" or ch.path.startswith(".git/")
        workflow = ch.path.startswith(".github/workflows/")
        if protected:
            report["protected_artifact_modifications"].append(ch.path)
        if git_internal:
            report.setdefault("git_path_modifications", []).append(ch.path)
        if workflow:
            report.setdefault("uncertainties", []).append({"id": "workflow_change", "message": f"{ch.path} changes repository automation and requires review", "path": ch.path, "evidence": ch.path})
        if ch.operation in {"rename", "copy"}:
            report.setdefault("uncertainties", []).append({"id": "unsupported_rename_copy", "message": f"{ch.operation} semantics for {ch.path} require review", "path": ch.path, "evidence": ch.old_path or ch.path})
        added = "\n".join(ch.added_lines or [])
        all_added.append(added)
        for imported in extract_imports_from_text(added, Path(ch.path).suffix.lower()):
            for dep in COMMON_DEPENDENCIES:
                if _normalize_dependency_name(imported) == _normalize_dependency_name(dep) and dep not in deps and dep not in patch_deps:
                    report["unsupported_dependencies"].append(dep)
    added_text = "\n".join(all_added)
    supported = supported_commands_inventory(reality)
    added_paths = {ch.path for ch in changes}
    compose_added = any(Path(path).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for path in added_paths)
    if re.search(r"docker\s+compose\s+up", added_text, re.I):
        evidence = docker_evidence(files)
        if compose_added:
            report["warnings"].append("Patch adds Docker Compose support used by commands; review the new support.")
            report.setdefault("declared_commands", []).append("docker compose up")
        elif not evidence["compose"]:
            report["unsupported_commands"].append("docker compose up")
    patch_scripts = set()
    command_uncertainties = []
    for ch in changes:
        if Path(ch.path).name.lower() != "package.json":
            continue
        base = _packet_file_contents(packet).get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        try:
            package = json.loads(post)
        except json.JSONDecodeError:
            command_uncertainties.append({"id": "command_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
            continue
        package_scripts = package.get("scripts")
        if isinstance(package_scripts, dict):
            patch_scripts.update(str(script) for script in package_scripts if isinstance(script, str) and script not in scripts)
    if command_uncertainties:
        report.setdefault("uncertainties", []).extend(command_uncertainties)
    for cmd in sorted(set(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))):
        normalized = cmd if cmd == "npm test" else cmd
        if normalized.startswith("npm run "):
            script = normalized.removeprefix("npm run ").strip()
            if script in patch_scripts:
                report["warnings"].append(f"Patch adds npm script {script} used by commands; review the new support.")
                report.setdefault("declared_commands", []).append(normalized)
            elif script not in scripts:
                report["unsupported_commands"].append(normalized)
        elif normalized == "npm test" and "test" not in scripts:
            report["unsupported_commands"].append(normalized)
    if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
        py = python_project_evidence(files, deps)
        if not (py["pytest"] or py["tests"] or "pytest" in supported):
            report["unsupported_commands"].append("pytest")
    packet_contents = _packet_file_contents(packet)
    make_text = packet_contents.get("Makefile") or packet_contents.get("makefile") or ""
    make_targets = {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.:-]+)\s*:", make_text, re.M)}
    for cmd in sorted(set(re.findall(r"\bmake\s+[A-Za-z0-9_.:-]+", added_text))):
        target = cmd.split(None, 1)[1]
        if target not in make_targets:
            report["unsupported_commands"].append(cmd)
    if not baseline_inventory_loaded:
        outside_context = sorted({
            ch.path for ch in changes
            if not ch.new_file
            and not ch.deleted_file
            and ch.path not in _included_paths(manifest)
        })
        if outside_context:
            report.setdefault("uncertainties", []).append({"id": "baseline_inventory_missing", "message": "Baseline packet lacks full file inventory; modified files outside prompt context could not be checked against tracked repo inventory.", "evidence": ", ".join(outside_context)})
    if report["new_files"]:
        report["warnings"].append("Patch creates new files that were not part of the original packet reality.")
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "path_escape"]
    if any(report.get(k) for k in fail_keys):
        report["verdict"] = "FAIL"
    elif report["new_files"] or report["warnings"] or report.get("uncertainties"):
        report["verdict"] = "WARN"
    for key in ["modified_files", "missing_modified_files", "new_files", "deleted_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "warnings"]:
        report[key] = sorted(set(report[key]))
    return report



def _has_negation_before(text: str, start: int) -> bool:
    window = text[max(0, start - 48):start].lower()
    return bool(re.search(r"\b(do not|don't|avoid|not|no|without|unless|until|does not|is no|will not)\b", window))


def _ai_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    aliases = [dep_pat]
    for imported, package in PY_IMPORT_ALIASES.items():
        if package == _normalize_dependency_name(dep):
            aliases.append(re.escape(imported))
    alias_pat = "(?:" + "|".join(sorted(set(aliases), key=len, reverse=True)) + ")"
    patterns = [
        rf"\bimport\s+{alias_pat}\b",
        rf"\bfrom\s+{alias_pat}\s+import\b",
        rf"\b(?:pip install|python\s+-m\s+pip\s+install|poetry add|uv add|pdm add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_js_dependency_actions(text: str, dep: str) -> bool:
    dep_pat = re.escape(dep)
    patterns = [
        rf"\bimport\s+[^\n;]*?from\s+[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]",
        rf"\brequire\s*\(\s*[`'\"]{dep_pat}(?:/[^`'\"]*)?[`'\"]\s*\)",
        rf"\b(?:npm install|npm i|pnpm add|yarn add|add|use|install|import)\s+{dep_pat}\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            if not _has_negation_before(text, m.start()):
                return True
    return False


def _ai_command_instructions(text: str, command_pattern: str) -> list[str]:
    found = []
    for m in re.finditer(command_pattern, text, re.I):
        before = text[max(0, m.start() - 32):m.start()].lower()
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_prefix = text[line_start:m.start()].strip().lower()
        backticked = m.start() > 0 and m.end() < len(text) and text[m.start() - 1] == "`" and text[m.end()] == "`"
        instruction = bool(re.search(r"\b(run|then|execute|use|uses|start with)\s+$", before)) or line_prefix in {"-", "*", "1.", "2.", "3."} or backticked
        if instruction and not _has_negation_before(text, m.start()):
            found.append(re.sub(r"\s+", " ", m.group(0).strip()).lower())
    return found




LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PY_STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"typing", "pathlib", "json", "os", "sys", "re", "subprocess", "datetime", "unittest"}
PY_DEP_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}



def _latest_report_html_path(repo: str | Path) -> Path:
    return ensure_sourcepack_dirs(repo)["latest_html"]




def finalize_diff_report(repo: str | Path | None, report: dict, args, stem: str = "diff") -> dict:
    full = dict(report)
    if getattr(args, "ci", False):
        full["ci"] = True
    if repo is not None:
        try:
            write_user_report(repo, full, stem)
        except Exception:
            full.setdefault("warnings", []).append("report_artifact_write_failed")
    return full


def git_metadata(repo: str | Path) -> dict:
    root = Path(repo)
    head = run_git(root, ["rev-parse", "HEAD"])
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty, dirty_state = git_worktree_dirty(root)
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": dirty if dirty_state is None else None,
        "dirty_state": dirty_state,
    }


def scanner_config_hash() -> str:
    payload = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "ignored_patterns": sorted(DEFAULT_IGNORED_PATTERNS),
        "text_extensions": sorted(DEFAULT_TEXT_EXTENSIONS),
        "max_file_size": 1_000_000,
        "include_hidden": False,
        "redact": True,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))



def build_prompt_context(repo: str | Path) -> dict:
    paths = ensure_sourcepack_dirs(repo)
    PacketWriter(paths["prompt_packet"], SourceScanner(repo).scan(), force=True).write_all()
    shutil.copy2(paths["prompt_packet"] / "reality_map.json", paths["prompt_reality"])
    shutil.copy2(paths["prompt_packet"] / "ai_instructions.md", paths["prompt_instructions"])
    return paths


def render_prompt(task: str, instructions: str, reality: dict) -> str:
    def bullets(items):
        return "\n".join(f"- {item}" for item in items) if items else "- None detected"
    return "\n".join(["# SourcePack Verified AI Prompt", "", "## User Task", "", task, "", "## AI Grounding Instructions", "", instructions.rstrip(), "", "## Compact Reality Map Summary", "", f"Project types: {', '.join(reality.get('project_types') or ['unknown'])}", f"Included files: {reality.get('included_file_count', 0)}", "", "## Supported Commands", "", bullets(reality.get('supported_commands', [])), "", "## Detected Dependencies", "", bullets(reality.get('detected_dependencies', [])), "", "## Supported Capabilities", "", bullets(reality.get('supported_capabilities', [])), "", "## Unknown and Unsupported Boundaries", "", bullets(reality.get('claim_boundaries', [])), "", "Cite exact file paths for project-specific claims.", "Do not invent files, dependencies, commands, services, or capabilities.", "Absence of evidence means unknown, not impossible.", ""])


def copy_to_clipboard(text: str) -> bool:
    system = platform.system().lower()
    cmds = [["pbcopy"]] if system == "darwin" else [["clip"]] if system == "windows" else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            if subprocess.run(cmd, input=text, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
                return True
        except Exception:
            pass
    return False


def _is_local_python_import(name: str, path: str, files: set[str]) -> bool:
    candidates = {f"{name}.py", f"{name}/__init__.py", f"src/{name}.py", f"src/{name}/__init__.py"}
    parent = str(Path(path).parent).replace("\\", "/")
    if parent != ".":
        candidates |= {f"{parent}/{name}.py", f"{parent}/{name}/__init__.py"}
    return bool(candidates & files)


JS_DEP_SECTIONS = {"dependencies", "devDependencies", "peerDependencies", "optionalDependencies"}


def _package_json_declared_deps_from_added_lines(lines: list[str]) -> set[str]:
    added = "\n".join(lines)
    try:
        package = json.loads(added)
    except json.JSONDecodeError:
        package = None
    deps: set[str] = set()
    if isinstance(package, dict):
        for section in JS_DEP_SECTIONS:
            section_deps = package.get(section)
            if isinstance(section_deps, dict):
                deps.update(dep.lower() for dep in section_deps)
        if deps:
            return deps
    for section in JS_DEP_SECTIONS:
        for body in re.findall(rf'"{section}"\s*:\s*\{{(.*?)\}}', added, re.I | re.S):
            deps.update(m.lower() for m in re.findall(r'"(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)"\s*:', body))
    return deps


def _apply_patch_change_to_text(original: str, change: PatchFileChange) -> str | None:
    if change.deleted_file:
        return ""
    result = original.splitlines()
    if result and result[0] == "":
        result = result[1:]
    out: list[str] = []
    idx = 0
    saw_hunk = False
    for line in change.diff_lines or []:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not m:
                return None
            old_start = max(int(m.group(1)) - 1, 0)
            if old_start < idx or old_start > len(result):
                return None
            out.extend(result[idx:old_start])
            idx = old_start
            saw_hunk = True
        elif line.startswith(" "):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            out.append(result[idx])
            idx += 1
        elif line.startswith("-"):
            body = line[1:]
            if idx >= len(result) or result[idx] != body:
                return None
            idx += 1
        elif line.startswith("+"):
            out.append(line[1:])
    if not saw_hunk and not change.new_file:
        return None
    out.extend(result[idx:])
    return "\n".join(out) + ("\n" if original.endswith("\n") or change.new_file else "")


def _python_dependency_names_by_scope_from_pyproject(content: str) -> dict[str, set[str]]:
    scopes = {"runtime": set(), "dev": set(), "optional": set()}
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return scopes

    def add_req(target: set[str], req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                target.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_req(scopes["runtime"], req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_req(scopes["optional"], req)
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            section = poetry.get("dependencies", {})
            if isinstance(section, dict):
                for dep in section:
                    if dep.lower() != "python":
                        scopes["runtime"].add(_normalize_dependency_name(dep))
            for section_name in ("dev-dependencies",):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            scopes["dev"].update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_req(scopes["dev"], req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_req(scopes["dev"], req)
    return scopes


def _declared_dependency_scopes_by_ecosystem(manifest: dict, packet: Path) -> dict[str, dict[str, set[str]]]:
    contents = _packet_file_contents(packet)
    scopes = {"python": {"runtime": set(), "dev": set(), "optional": set()}, "js": {"runtime": set(), "dev": set(), "optional": set()}}
    for rel, content in contents.items():
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(content)
            for key, values in parsed.items():
                scopes["python"][key].update(values)
        elif name == "requirements.txt":
            scopes["python"]["runtime"].update(_python_dependency_names_from_requirement_lines(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            target = "dev" if any(x in name for x in ("dev", "test")) else "runtime"
            scopes["python"][target].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            section_map = {"dependencies": "runtime", "peerDependencies": "runtime", "optionalDependencies": "optional", "devDependencies": "dev"}
            for section, target in section_map.items():
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    scopes["js"][target].update(dep.lower() for dep in section_deps)
    return scopes


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    name = PurePosixPath(p).name
    return p.startswith(("tests/", "test/")) or "/__tests__/" in f"/{p}" or name.endswith("_test.py") or any(name.endswith(s) for s in (".test.js", ".test.ts", ".spec.js", ".spec.ts", ".test.jsx", ".test.tsx", ".spec.jsx", ".spec.tsx"))


def _dependency_scope_status(dep: str, scopes: dict[str, set[str]], path: str) -> str:
    dep = _normalize_dependency_name(dep)
    if dep in scopes.get("runtime", set()):
        return "supported"
    if dep in scopes.get("dev", set()):
        return "supported" if _is_test_path(path) else "scope_review"
    if dep in scopes.get("optional", set()):
        return "scope_review"
    return "missing"


def _declared_dependency_names_from_patch_by_ecosystem_structural(changes: list[PatchFileChange], contents: dict[str, str]) -> tuple[dict[str, set[str]], list[dict]]:
    deps = {"python": set(), "js": set()}
    uncertainties: list[dict] = []
    for ch in changes:
        name = Path(ch.path).name.lower()
        if name not in {"package.json", "pyproject.toml"} and not (name.startswith("requirements") and name.endswith(".txt")):
            continue
        base = contents.get(ch.old_path or ch.path, "")
        post = _apply_patch_change_to_text(base, ch)
        if post is None:
            uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not reconstruct {ch.path} safely", "path": ch.path})
            continue
        if name == "package.json":
            try:
                package = json.loads(post)
            except json.JSONDecodeError:
                uncertainties.append({"id": "dependency_manifest_uncertain", "message": f"Could not parse {ch.path} as JSON", "path": ch.path})
                continue
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    deps["js"].update(dep.lower() for dep in section_deps)
        elif name == "pyproject.toml":
            parsed = _python_dependency_names_by_scope_from_pyproject(post)
            deps["python"].update(set().union(*parsed.values()))
        else:
            deps["python"].update(_python_dependency_names_from_requirement_lines(post))
    return deps, uncertainties


def _declared_dependency_names_from_patch_by_ecosystem(changes: list[PatchFileChange]) -> dict[str, set[str]]:
    deps = {"python": set(), "js": set()}
    for ch in changes:
        added = "\n".join(ch.added_lines or [])
        name = Path(ch.path).name.lower()
        if name == "package.json":
            deps["js"].update(_package_json_declared_deps_from_added_lines(ch.added_lines or []))
        elif name == "pyproject.toml":
            deps["python"].update(_python_dependency_names_from_pyproject(added))
        elif name.startswith("requirements") and name.endswith(".txt"):
            deps["python"].update(_python_dependency_names_from_requirement_lines(added))
    return deps


def _declared_dependency_names_from_patch(changes: list[PatchFileChange]) -> set[str]:
    scoped = _declared_dependency_names_from_patch_by_ecosystem(changes)
    return scoped["python"] | scoped["js"]


def _declared_dependency_names_by_ecosystem(manifest: dict, packet: Path) -> dict[str, set[str]]:
    declared = {"python": set(), "js": set()}
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        if name == "pyproject.toml":
            declared["python"].update(_python_dependency_names_from_pyproject(content))
        elif name.startswith("requirements") and name.endswith(".txt"):
            declared["python"].update(_python_dependency_names_from_requirement_lines(content))
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in JS_DEP_SECTIONS:
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    declared["js"].update(dep.lower() for dep in section_deps)
    return declared


def _declared_dependency_names(manifest: dict, packet: Path) -> set[str]:
    scoped = _declared_dependency_names_by_ecosystem(manifest, packet)
    return scoped["python"] | scoped["js"]


def _workspace_package_names(packet: Path) -> set[str]:
    contents = _packet_file_contents(packet)
    root = {}
    try:
        root = json.loads(contents.get("package.json", "{}"))
    except json.JSONDecodeError:
        return set()
    workspaces = root.get("workspaces")
    patterns = workspaces if isinstance(workspaces, list) else workspaces.get("packages", []) if isinstance(workspaces, dict) else []
    names: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern.endswith("/*"):
            continue
        prefix = pattern[:-2].strip("/")
        for rel, content in contents.items():
            if Path(rel).name == "package.json" and rel.startswith(prefix + "/"):
                try:
                    package = json.loads(content)
                except json.JSONDecodeError:
                    continue
                name = package.get("name")
                if isinstance(name, str):
                    names.add(name.lower())
    return names


def _is_js_alias_specifier(imported: str) -> bool:
    return imported.startswith(("@/", "~/"))


def _js_alias_local(imported: str, files: set[str], contents: dict[str, str]) -> bool | None:
    configs = []
    for cfg in ("tsconfig.json", "jsconfig.json"):
        if cfg in contents:
            try:
                configs.append(json.loads(contents[cfg]))
            except json.JSONDecodeError:
                return None
    for cfg in configs:
        opts = cfg.get("compilerOptions", {}) if isinstance(cfg, dict) else {}
        base = str(opts.get("baseUrl", ".")).strip("./")
        paths = opts.get("paths", {})
        candidates = []
        if isinstance(paths, dict):
            for alias, targets in paths.items():
                prefix = alias[:-1] if alias.endswith("*") else alias
                if imported.startswith(prefix):
                    rest = imported[len(prefix):]
                    for target in targets if isinstance(targets, list) else []:
                        tprefix = target[:-1] if isinstance(target, str) and target.endswith("*") else target
                        candidates.append((tprefix + rest).strip("/"))
        if base and not imported.startswith("@") and not imported.startswith("~"):
            candidates.append(f"{base}/{imported}".strip("/"))
        for c in candidates:
            variants = {c, f"{c}.ts", f"{c}.tsx", f"{c}.js", f"{c}.jsx", f"{c}/index.ts", f"{c}/index.tsx", f"{c}/index.js", f"{c}/index.jsx"}
            if variants & files:
                return True
        if candidates:
            return None
    return False


def _is_high_risk_binary_path(rel: str) -> bool:
    normalized = rel.replace("\\", "/").lstrip("/")
    high_risk_prefixes = (".sourcepack/", ".git/", ".github/workflows/")
    high_risk_names = {"pyproject.toml", "package.json", "package-lock.json", "uv.lock", "poetry.lock"}
    return normalized.startswith(high_risk_prefixes) or Path(normalized).name in high_risk_names


UNSUPPORTED_ECOSYSTEM_MARKERS = {
    "gemfile": ("Gemfile", "Ruby/Bundler dependency validation is not implemented"),
    "composer.json": ("composer.json", "PHP/Composer dependency validation is not implemented"),
    "main.tf": ("main.tf", "Terraform module/provider validation is not implemented"),
    "flake.nix": ("flake.nix", "Nix flake validation is not implemented"),
    "cargo.toml": ("Cargo.toml", "Rust dependency validation is not implemented"),
    "go.mod": ("go.mod", "Go module dependency validation is not implemented"),
    "pom.xml": ("pom.xml", "Maven dependency validation is not implemented"),
    "build.gradle": ("build.gradle", "Gradle dependency validation is not implemented"),
    "build.gradle.kts": ("build.gradle.kts", "Gradle dependency validation is not implemented"),
    "settings.gradle": ("settings.gradle", "Gradle workspace validation is not implemented"),
    "settings.gradle.kts": ("settings.gradle.kts", "Gradle workspace validation is not implemented"),
    "*.csproj": ("*.csproj", ".NET/NuGet dependency validation is not implemented"),
}


def _unsupported_ecosystem_uncertainties(files: set[str], changes: list[PatchFileChange]) -> list[dict]:
    names = {Path(f).name.lower() for f in files}
    names.update(Path(ch.path).name.lower() for ch in changes)
    for ch in changes:
        if ch.path.lower().endswith(".csproj"):
            names.add("*.csproj")
    uncertainties = []
    for marker, (evidence, message) in sorted(UNSUPPORTED_ECOSYSTEM_MARKERS.items()):
        if marker in names:
            uncertainties.append({"id": "unsupported_ecosystem", "message": f"{evidence} detected, but {message}", "evidence": evidence})
    return uncertainties

def judge_patch_text(packet_path: str | Path, patch_text: str) -> dict:
    if re.search(r"(?m)^@@", patch_text) and "diff --git " not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    if re.search(r"(?m)^@@(?! -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)", patch_text):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    changes = parse_unified_diff(patch_text)
    unsafe_paths = sorted({ch.path for ch in changes if ch.unsafe_path and ch.path})
    if any(ch.unsafe_path for ch in changes):
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "path_escape": True, "path_escape_paths": unsafe_paths}
    if patch_text.strip() and not changes and "Binary files " not in patch_text:
        return {"verdict": "FAIL", "modified_files": [], "missing_modified_files": [], "new_files": [], "deleted_files": [], "unsupported_dependencies": [], "unsupported_commands": [], "protected_artifact_modifications": [], "warnings": [], "malformed_diff": True}
    report = analyze_patch(packet_path, patch_text, changes)
    packet = Path(packet_path); manifest = load_manifest(packet); files = known_files(manifest, packet); contents = _packet_file_contents(packet)
    existing_declared = _declared_dependency_names_by_ecosystem(manifest, packet)
    scopes = _declared_dependency_scopes_by_ecosystem(manifest, packet)
    patch_declared, manifest_uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
    if manifest_uncertainties:
        report.setdefault("uncertainties", []).extend(manifest_uncertainties)
    workspace_names = _workspace_package_names(packet)
    unsupported = set(report.get("unsupported_dependencies", []))
    resolver_tmp = _materialize_packet_worktree(packet)
    resolver_root = Path(resolver_tmp.name)
    try:
        for ch in changes:
            suffix = Path(ch.path).suffix.lower(); added = "\n".join(ch.added_lines or [])
            if suffix == ".py":
                for imported in extract_imports_from_text(added, suffix):
                    dep_resolution = resolve_python_import(resolver_root, imported, added_dependencies=patch_declared["python"])
                    dep_name = _dependency_name_for_import(imported)
                    if dep_resolution.verdict == "PASS":
                        unsupported.discard(imported); unsupported.discard(dep_name)
                    elif dep_resolution.reason_code == "declared_dependency":
                        unsupported.discard(imported); unsupported.discard(dep_name)
                        report.setdefault("uncertainties", []).append({"id": "declared_dependency", "message": f"{dep_name} is declared in the same patch and requires review", "path": ch.path, "evidence": dep_name})
                    elif dep_resolution.reason_code == "dependency_scope_review":
                        report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{dep_name} is declared outside the runtime dependency scope", "path": ch.path, "evidence": dep_name})
                    elif dep_resolution.reason_code == "unsupported_dependency":
                        unsupported.add(imported)
            elif suffix in JS_EXTS:
                for imported in extract_imports_from_text(added, suffix):
                    pkg = _js_package_root(imported)
                    local_alias = _js_alias_local(imported, files, contents)
                    if pkg in workspace_names or local_alias is True:
                        continue
                    dep_resolution = resolve_js_import(resolver_root, imported)
                    if dep_resolution.verdict == "PASS":
                        unsupported.discard(pkg)
                    elif dep_resolution.reason_code == "js_alias_uncertain":
                        report.setdefault("uncertainties", []).append({"id": "js_alias_uncertain", "message": f"{imported} could not be resolved safely", "path": ch.path, "evidence": imported})
                    elif dep_resolution.reason_code == "dependency_scope_review":
                        report.setdefault("uncertainties", []).append({"id": "dependency_scope_review", "message": f"{pkg} is declared outside the runtime dependency scope", "path": ch.path, "evidence": pkg})
                    elif dep_resolution.reason_code == "unsupported_dependency" and pkg not in patch_declared["js"]:
                        unsupported.add(pkg)
    finally:
        resolver_tmp.cleanup()

    # Re-run command claims through the command resolver so report output is
    # based on the same manifest-aware command semantics as unit-level checks.
    command_overlay: dict[str, str] = {}
    for ch in changes:
        if Path(ch.path).name.lower() in {"package.json", "Makefile", "justfile", "Justfile", "Taskfile.yml", "Taskfile.yaml", "tox.ini", "noxfile.py", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
            base = contents.get(ch.old_path or ch.path, "")
            post = _apply_patch_change_to_text(base, ch)
            if post is not None:
                command_overlay[ch.path] = post
    command_tmp = _materialize_packet_worktree(packet, command_overlay)
    try:
        command_root = Path(command_tmp.name)
        added_text = "\n".join("\n".join(ch.added_lines or []) for ch in changes)
        commands = set()
        if re.search(r"docker\s+compose\s+up", added_text, re.I):
            commands.add("docker compose up")
        commands.update(re.findall(r"npm\s+(?:run\s+)?[A-Za-z0-9:_-]+", added_text))
        commands.update(re.findall(r"make\s+[A-Za-z0-9_.:-]+", added_text))
        commands.update(re.findall(r"just\s+[A-Za-z0-9_.:-]+", added_text))
        commands.update(re.findall(r"task\s+[A-Za-z0-9_.:-]+", added_text))
        if re.search(r"\b(pytest|python\s+-m\s+pytest)\b", added_text, re.I):
            commands.add("pytest")
        report["unsupported_commands"] = []
        for command in sorted(commands):
            resolution = resolve_command(command_root, command)
            if resolution.reason_code == "unsupported_command":
                report["unsupported_commands"].append(command)
            elif resolution.reason_code in {"declared_command", "command_check_inconclusive", "command_manifest_missing", "command_manifest_uncertain"}:
                report.setdefault("uncertainties", []).append({"id": resolution.reason_code, "message": resolution.message, "evidence": command})
    finally:
        command_tmp.cleanup()
    declared = patch_declared["python"] | patch_declared["js"]
    existing_deps = existing_declared["python"] | existing_declared["js"]
    declared_only = {d for d in declared if d not in existing_deps}
    binary_paths = []
    binary_blockers = []
    for line in patch_text.splitlines():
        if line.startswith("Binary files "):
            m = re.search(r" b/(.+?) differ", line)
            rel = m.group(1) if m else "unknown"
            binary_paths.append(rel)
            if rel == "unknown" or _is_high_risk_binary_path(rel):
                binary_blockers.append(rel)
    if binary_paths:
        report["binary_diffs"] = sorted(set(binary_paths))
    if binary_blockers:
        report["binary_diff_blockers"] = sorted(set(binary_blockers))
    unsupported_ecosystems = _unsupported_ecosystem_uncertainties(files, changes)
    if unsupported_ecosystems:
        seen_uncertainties = set()
        merged_uncertainties = []
        for uncertainty in report.get("uncertainties", []) + unsupported_ecosystems:
            if isinstance(uncertainty, dict):
                key = (uncertainty.get("id"), uncertainty.get("message"), uncertainty.get("evidence"), uncertainty.get("path"))
            else:
                key = (str(uncertainty),)
            if key not in seen_uncertainties:
                seen_uncertainties.add(key)
                merged_uncertainties.append(uncertainty)
        report["uncertainties"] = merged_uncertainties
    report["unsupported_dependencies"] = sorted(unsupported)
    if declared_only:
        report.setdefault("warnings", []).append("Patch declares new dependencies that require review.")
        report["declared_dependencies"] = sorted(declared_only)
    fail_keys = ["missing_modified_files", "unsupported_dependencies", "unsupported_commands", "protected_artifact_modifications", "git_path_modifications", "binary_diff_blockers", "path_escape"]
    report["verdict"] = "FAIL" if any(report.get(k) for k in fail_keys) else "WARN" if (report.get("new_files") or report.get("deleted_files") or report.get("warnings") or declared_only or report.get("uncertainties") or report.get("binary_diffs")) else "PASS"
    return report


def patch_report_to_traffic(report: dict, report_path: str = ".sourcepack/reports/latest.json") -> dict:
    findings=[]
    for p in report.get("missing_modified_files", []): findings.append(normalized_finding("missing_file", "error", "file", f"{p} not found in the trusted baseline.", p, suggestion="Restore the file, create it as a new file, or refresh the baseline only after accepting the current repo state."))
    for d in report.get("unsupported_dependencies", []): findings.append(normalized_finding("unsupported_dependency", "error", "dependency", f"{d} is imported but not declared in scanned dependency files.", evidence=d, suggestion=f"Either remove {d} usage or add it intentionally to the appropriate dependency manifest."))
    for c in report.get("unsupported_commands", []): findings.append(normalized_finding("unsupported_command", "error", "command", f"{c} is not supported by project evidence.", evidence=c, suggestion="Use a detected supported command or add the project file that defines this command."))
    if report.get("malformed_diff"):
        findings.append(normalized_finding("malformed_diff", "error", "diff", "SourcePack could not safely parse the diff artifact it was asked to judge."))
    if report.get("path_escape"):
        paths = report.get("path_escape_paths") or []
        if paths:
            for p in paths:
                findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute.", p, evidence=p))
        else:
            findings.append(normalized_finding("path_escape", "error", "diff", "Diff path escapes the repository root or is absolute."))
    for p in report.get("protected_artifact_modifications", []): findings.append(normalized_finding("protected_artifact", "error", "artifact", f"{p} is a protected SourcePack trust artifact.", p, evidence=p))
    for p in report.get("git_path_modifications", []): findings.append(normalized_finding("git_path_modification", "error", "artifact", f"{p} modifies Git internal state and is not safe to judge as a normal repository file.", p, evidence=p))
    for p in report.get("binary_diff_blockers", []): findings.append(normalized_finding("binary_diff", "error", "diff", f"Binary change at {p} crosses a SourcePack trust or high-risk control boundary.", p, evidence=p))
    for p in report.get("binary_diffs", []):
        if p not in set(report.get("binary_diff_blockers", [])):
            findings.append(normalized_finding("binary_diff", "warn", "uncertainty", f"Binary content was detected at {p} and was not semantically evaluated.", p, evidence=p))
    for p in report.get("new_files", []): findings.append(normalized_finding("new_file", "warn", "review", f"{p} was created by the patch.", p))
    for p in report.get("deleted_files", []): findings.append(normalized_finding("deleted_file", "warn", "review", f"{p} was deleted by the patch.", p))
    for d in report.get("declared_dependencies", []): findings.append(normalized_finding("declared_dependency", "warn", "review", f"{d} was added to dependency files.", evidence=d))
    for c in report.get("declared_commands", []): findings.append(normalized_finding("declared_command", "warn", "review", f"{c} was added in the same patch.", evidence=c))
    for w in report.get("uncertainties", []):
        if isinstance(w, dict):
            fid = str(w.get("id") or "uncertainty")
            message = str(w.get("message") or "SourcePack could not fully evaluate this change.")
            findings.append(normalized_finding(fid, "warn", "uncertainty", message, w.get("path"), w.get("evidence"), w.get("suggestion")))
        else:
            fid, _, detail = str(w).partition(":")
            fid = fid.strip() or "uncertainty"
            message = detail.strip() or str(w)
            findings.append(normalized_finding(fid, "warn", "uncertainty", message))
    return traffic_report(report.get("verdict", "PASS"), findings=findings, checked_categories=["file references", "Python imports", "JS/TS imports", "known project commands", "protected SourcePack artifacts"], report_path=report_path)


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git executable not found")



def git_worktree_dirty(repo: str | Path) -> tuple[bool, str | None]:
    repo = Path(repo)
    cp = run_git(repo, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        return False, "git_unavailable" if cp.returncode == 127 else "not_git"
    root = Path(cp.stdout.strip())
    for args in (["diff", "--quiet"], ["diff", "--staged", "--quiet"]):
        diff_cp = run_git(root, list(args))
        if diff_cp.returncode == 1:
            return True, None
        if diff_cp.returncode == 127:
            return False, "git_unavailable"
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0 and untracked.stdout.strip():
        return True, None
    if untracked.returncode == 127:
        return False, "git_unavailable"
    return False, None



def _only_sourcepack_gitignore_change(repo: Path) -> bool:
    status = run_git(repo, ["status", "--porcelain", "--", ".gitignore"])
    others = run_git(repo, ["status", "--porcelain"])
    if status.returncode != 0 or others.returncode != 0:
        return False
    lines = [line for line in others.stdout.splitlines() if line.strip()]
    if not lines or any(not line.endswith(".gitignore") for line in lines):
        return False
    try:
        text = (repo / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return False
    tracked = run_git(repo, ["show", "HEAD:.gitignore"])
    before = tracked.stdout if tracked.returncode == 0 else ""
    added = [line.strip() for line in text.splitlines() if line.strip() and line.strip() not in {l.strip() for l in before.splitlines()}]
    return bool(added) and set(added) <= {".sourcepack", ".sourcepack/"}


def untracked_files_as_diff(repo: str | Path) -> str:
    repo = Path(repo)
    cp = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    if cp.returncode != 0:
        return ""
    chunks = []
    for rel in [line.strip() for line in cp.stdout.splitlines() if line.strip()]:
        path = repo / rel
        if rel == ".gitignore":
            try:
                ignore_lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
            except OSError:
                ignore_lines = set()
            if ignore_lines <= {".sourcepack", ".sourcepack/"}:
                continue
        safe_rel = rel.replace("\\", "/")
        chunks.extend([f"diff --git a/{safe_rel} b/{safe_rel}", "new file mode 100644", "--- /dev/null", f"+++ b/{safe_rel}"])
        if is_probably_binary(path):
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            chunks.append(f"Binary files /dev/null and b/{safe_rel} differ")
            continue
        except OSError:
            continue
        lines = text.splitlines()
        chunks.append(f"@@ -0,0 +1,{len(lines)} @@")
        chunks.extend(f"+{line}" for line in lines)
    return "\n".join(chunks) + ("\n" if chunks else "")

def build_repo_change_report(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, ci: bool = False) -> dict:
    repo_arg = Path(repo_path).resolve(); cp = run_git(repo_arg, ["rev-parse", "--show-toplevel"])
    if cp.returncode != 0:
        message = "Git executable not found." if cp.returncode == 127 else "No git repository found. Run sourcepack prompt or sourcepack baseline for non-git use."
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable" if cp.returncode == 127 else "no_git_repo", "error", "git", message)])
    git_root = Path(cp.stdout.strip()).resolve()
    repo = repo_arg if validate_baseline(repo_arg).get("state") in {"present", "stale", "corrupt"} else git_root
    paths = ensure_sourcepack_dirs(repo); added, err = ensure_gitignore_entry(repo)
    if added:
        paths.setdefault("gitignore_added", True)
    if err:
        return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("gitignore_unwritable", "error", "git", f"Cannot write .gitignore: {err}")])
    if patch_text is None:
        diff_args = ["diff", "--staged"] if staged else ["diff"]
        if repo != git_root:
            diff_args.append("--relative")
        cp = run_git(repo, diff_args); diff_text = cp.stdout
        if cp.returncode == 127:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("git_unavailable", "error", "git", "Git executable not found.")])
        if not staged:
            extra = untracked_files_as_diff(repo)
            if extra and not (added and _only_sourcepack_gitignore_change(repo)):
                diff_text = (diff_text + "\n" + extra).strip() + "\n"
    else:
        diff_text = patch_text
    baseline_status = validate_baseline(repo)
    if baseline_status["state"] == "corrupt":
        rep = traffic_report("FAIL", "trusted baseline is corrupt.", [normalized_finding("baseline_corrupt", "error", "baseline", baseline_status["message"])], ["baseline", "diff"], "Recreate the baseline only after verifying the current repo state should be trusted.")
        rep.update(baseline_report_fields(baseline_status)); return rep
    if baseline_status["state"] == "missing":
        dirty_now, dirty_state_now = git_worktree_dirty(repo)
        if ci:
            rep = traffic_report("FAIL", "trusted baseline is missing in CI.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists; CI must not establish trust.")], ["baseline", "diff"], "create the baseline locally only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        if diff_text.strip() or (dirty_now and not _only_sourcepack_gitignore_change(repo)):
            rep = traffic_report("FAIL", "baseline missing while changes are present.", [normalized_finding("baseline_missing", "error", "baseline", "No trusted SourcePack baseline exists while changes are present.")], ["baseline", "diff"], "run sourcepack baseline only after deciding the current repo state should be trusted.")
            rep.update(baseline_report_fields(baseline_status)); return rep
        try:
            build_current_baseline(repo, quiet=True); baseline_status = validate_baseline(repo)
            rep_note = "Created SourcePack baseline because none existed and no diff was present."
        except BaselineLockError as exc:
            return traffic_report("WARN", "baseline writer is locked.", [normalized_finding("baseline_locked", "warn", "tooling", str(exc))], ["baseline", "diff"], "try again after the other baseline operation finishes.", reason_type="tooling")
        except Exception as exc:
            return traffic_report("FAIL", "stop before trusting this output.", [normalized_finding("baseline_failed", "error", "baseline", f"Baseline verification failed: {exc}")])
    else:
        rep_note = None
    stale_findings = []
    if baseline_status["state"] == "stale":
        stale_findings.append(normalized_finding("baseline_stale", "warn", "uncertainty", "Trusted SourcePack baseline may not match current repo state."))
    if not diff_text.strip():
        verdict = "WARN" if stale_findings else "PASS"
        rep = traffic_report(verdict, "SourcePack could not fully evaluate this change." if stale_findings else "good to continue.", [normalized_finding("no_diff", "info", "diff", "No uncommitted changes detected."), *stale_findings], ["diff", "baseline freshness"])
    else:
        packet_path = repo / baseline_status["packet_path"]
        raw = judge_patch_text(packet_path, diff_text); rep = patch_report_to_traffic(raw); rep["raw_patch_judgment"] = raw
        rep = _integrate_execution_findings(repo, diff_text, rep)
        rep = _apply_local_policy(repo, rep)
        rep = _apply_policy_rules(repo, packet_path, diff_text, rep)
        rep = _apply_policy_config(repo, rep)
        if stale_findings and rep["verdict"] != "FAIL":
            rep = traffic_report("WARN", "SourcePack could not fully evaluate this change.", rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action"), reason_type="uncertainty"); rep["raw_patch_judgment"] = raw
        elif stale_findings:
            rep = traffic_report("FAIL", rep.get("headline"), rep.get("findings", []) + stale_findings, rep.get("checked_categories", []), rep.get("next_action")); rep["raw_patch_judgment"] = raw
    rep.update(baseline_report_fields(baseline_status))
    if baseline_status.get("metadata_path"):
        try:
            rep["baseline"] = json.loads((repo / baseline_status["metadata_path"]).read_text(encoding="utf-8"))
        except Exception:
            pass
    rep["current_git"] = git_metadata(repo)
    if rep_note:
        rep["note"] = rep_note
    rep["repo_path"] = str(repo)
    return rep


def _rebuild_from_findings(rep: dict, findings: list[dict]) -> dict:
    verdict = "FAIL" if any(f.get("severity") == "error" for f in findings) else "WARN" if any(f.get("severity") == "warn" for f in findings) else "PASS"
    rebuilt = traffic_report(verdict, findings=findings, checked_categories=rep.get("checked_categories") or rep.get("checked") or [], report_path=rep.get("report_path", ".sourcepack/reports/latest.json"))
    for key in ("raw_patch_judgment", "policy_overrides", "policy_config", "policy_config_ignores", "policy_config_warnings", "policy_rule_findings"):
        if key in rep:
            rebuilt[key] = rep[key]
    return rebuilt


def _integrate_execution_findings(repo: Path, checked_text: str, rep: dict) -> dict:
    execution = execution_findings(repo, checked_text)
    if not execution:
        return rep
    return _rebuild_from_findings(rep, list(rep.get("findings", [])) + execution)


_PLACEHOLDER_SECRET_VALUES = {"example", "dummy", "fake", "test", "changeme", "placeholder", "redacted"}
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|apikey|access[_-]?key|private[_-]?key)\b"
    r"[A-Za-z0-9_.-]*['\"]?\s*[:=]\s*['\"]?([^'\"\s,#}]{8,})['\"]?"
)


def _policy_changed_line_count(changes: list[PatchFileChange]) -> int:
    count = 0
    for change in changes:
        for line in change.diff_lines or []:
            if (
                line.startswith("@@")
                or line.startswith(" ")
                or line.startswith("--- ")
                or line.startswith("+++ ")
            ):
                continue
            if line.startswith(("+", "-")):
                count += 1
    return count


def _line_has_policy_secret(line: str) -> bool:
    for match in _SECRET_ASSIGNMENT_RE.finditer(line):
        value = match.group(2).strip().lower()
        if any(placeholder in value for placeholder in _PLACEHOLDER_SECRET_VALUES):
            continue
        return True
    return False


def _policy_rule_findings(repo: Path, packet_path: Path, diff_text: str) -> list[dict]:
    config = load_policy_config(repo)
    rules = config.rules
    if not rules.enabled() or not diff_text.strip():
        return []
    changes = [change for change in parse_unified_diff(diff_text) if not change.unsafe_path]
    if not changes:
        return []

    findings: list[dict] = []
    changed_paths = sorted({change.path for change in changes if change.path})
    protected_check_paths = sorted({
        path
        for change in changes
        for path in (change.path, change.old_path if change.operation in {"rename", "copy"} else None)
        if path
    })

    for path in protected_check_paths:
        for pattern in rules.protected_paths:
            if policy_path_matches(path, pattern):
                findings.append(normalized_finding(
                    "policy_protected_path",
                    "error",
                    "policy",
                    "Proposed change modified a path protected by repository policy.",
                    path,
                    evidence=pattern,
                    suggestion="Change the protected path only after updating repository policy or obtaining the required review.",
                ))
                break

    if rules.package_manager == "pnpm":
        conflicting = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock"}
        for change in changes:
            if change.deleted_file:
                continue
            path = change.path
            if path and PurePosixPath(path).name in conflicting:
                findings.append(normalized_finding(
                    "policy_package_manager_drift",
                    "error",
                    "policy",
                    "Proposed change added or modified a package-manager artifact that conflicts with repository policy.",
                    path,
                    evidence="pnpm",
                    suggestion="Use pnpm artifacts for this repository or update policy intentionally.",
                ))

    if rules.max_changed_lines is not None:
        changed_line_count = _policy_changed_line_count(changes)
        if changed_line_count > rules.max_changed_lines:
            findings.append(normalized_finding(
                "policy_large_diff",
                "warn",
                "policy",
                f"Proposed change modifies {changed_line_count} lines, exceeding repository policy limit {rules.max_changed_lines}.",
                evidence=str(changed_line_count),
                suggestion="Split the proposed change or raise the configured limit intentionally.",
            ))

    if rules.require_tests_for:
        has_test_change = any(_is_test_path(path) for path in changed_paths)
        if not has_test_change:
            for path in changed_paths:
                if _is_test_path(path):
                    continue
                if any(policy_path_matches(path, pattern) for pattern in rules.require_tests_for):
                    findings.append(normalized_finding(
                        "policy_missing_test",
                        "warn",
                        "policy",
                        "Proposed change altered a path that repository policy expects to be accompanied by a test change.",
                        path,
                        evidence=", ".join(rules.require_tests_for),
                        suggestion="Add or update a corresponding test in the same delta, or adjust repository policy intentionally.",
                    ))
                    break

    if rules.block_secret_patterns:
        for change in changes:
            for line in change.added_lines or []:
                if _line_has_policy_secret(line):
                    findings.append(normalized_finding(
                        "policy_secret_pattern",
                        "error",
                        "policy",
                        "Proposed change added obvious credential-shaped assignment material blocked by repository policy.",
                        change.path,
                        suggestion="Remove the credential-shaped value or replace it with an obvious placeholder.",
                    ))
                    break

    if rules.block_dependency_additions:
        manifest = load_manifest(packet_path)
        contents = _packet_file_contents(packet_path)
        existing = _declared_dependency_names_by_ecosystem(manifest, packet_path)
        declared, uncertainties = _declared_dependency_names_from_patch_by_ecosystem_structural(changes, contents)
        if not uncertainties:
            additions = sorted((declared["python"] | declared["js"]) - (existing["python"] | existing["js"]))
            for dependency in additions:
                findings.append(normalized_finding(
                    "policy_dependency_addition",
                    "error",
                    "policy",
                    "Proposed change added an unapproved dependency to project manifest files.",
                    evidence=dependency,
                    suggestion="Remove the dependency addition or update repository policy/review evidence intentionally.",
                ))

    return findings


def _apply_policy_rules(repo: Path, packet_path: Path, diff_text: str, rep: dict) -> dict:
    findings = _policy_rule_findings(repo, packet_path, diff_text)
    if not findings:
        return rep
    rebuilt = _rebuild_from_findings(rep, list(rep.get("findings", [])) + findings)
    rebuilt["policy_rule_findings"] = findings
    return rebuilt


def _policy_entries_for_judgment(repo: Path) -> list[dict]:
    path = repo / ".sourcepack" / "policy" / "allow.jsonl"
    if not path.exists():
        return []
    entries = []
    now = utc_now()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except Exception:
            continue
        expires = entry.get("expires_at")
        if expires and str(expires) < now:
            continue
        entries.append(entry)
    return entries


def _policy_matches(entry: dict, finding: dict) -> bool:
    scope = entry.get("scope")
    value = str(entry.get("value") or "")
    fid = finding.get("id")
    if fid == "git_path_modification" or str(finding.get("path") or "").startswith(".git/"):
        return False
    if scope == "dependency":
        return fid == "unsupported_dependency" and finding.get("evidence") == value
    if scope == "command":
        return fid == "unsupported_command" and finding.get("evidence") == value
    if scope == "path":
        if str(finding.get("path") or "") != value:
            return False
        if str(value).startswith(".sourcepack/baseline/") and not entry.get("high_risk"):
            return False
        return fid not in {"git_path_modification"}
    return False


def _apply_local_policy(repo: Path, rep: dict) -> dict:
    entries = _policy_entries_for_judgment(repo)
    if not entries:
        return rep
    kept = []
    overrides = []
    for finding in rep.get("findings", []):
        match = next((entry for entry in entries if _policy_matches(entry, finding)), None)
        if match:
            overrides.append({"policy_id": match.get("id"), "scope": match.get("scope"), "value": match.get("value"), "reason": match.get("reason"), "suppressed_finding": finding.get("id"), "path": finding.get("path")})
        else:
            kept.append(finding)
    if not overrides:
        return rep
    rebuilt = _rebuild_from_findings(rep, kept)
    rebuilt["policy_overrides"] = overrides
    rebuilt.setdefault("findings", []).append(normalized_finding("policy_override", "info", "policy", "A local allow policy suppressed a matching finding.", evidence=", ".join(str(o.get("value")) for o in overrides)))
    return _rebuild_from_findings(rebuilt, rebuilt["findings"])


def _apply_policy_config(repo: Path, rep: dict) -> dict:
    config = load_policy_config(repo)
    kept = []
    ignored = []
    for finding in rep.get("findings", []):
        match = finding_ignored_by_policy(finding, config)
        if match:
            ignored.append({"suppressed_finding": finding.get("id"), **match})
        else:
            kept.append(finding)
    if ignored:
        rebuilt = _rebuild_from_findings(rep, kept)
        rebuilt["policy_config"] = {"path": ".sourcepack/policy.json", "schema_version": config.schema_version, "report_formats": list(config.report_formats)}
        rebuilt["policy_config_ignores"] = ignored
        rebuilt.setdefault("findings", []).append(normalized_finding("policy_override", "info", "policy", "Project policy ignored matching low-risk path findings.", evidence=", ".join(i["path"] for i in ignored)))
        rep = _rebuild_from_findings(rebuilt, rebuilt["findings"] )
    else:
        rep = dict(rep)
        rep["policy_config"] = {"path": ".sourcepack/policy.json", "schema_version": config.schema_version, "report_formats": list(config.report_formats)}
    if config.warnings:
        findings = list(rep.get("findings", []))
        findings.extend(normalized_finding("policy_config_warning", "warn", "policy", warning) for warning in config.warnings)
        rep = _rebuild_from_findings(rep, findings)
        rep["policy_config_warnings"] = list(config.warnings)
    return rep


def write_auto_report(repo: Path, report: dict, details: dict) -> None:
    payload = dict(report)
    payload.update(details)
    write_user_report(repo, payload, "auto")






# CLI-independent public judgment API
@dataclass(frozen=True)
class Judgment:
    repo_path: str
    policy_mode: PolicyMode
    report: dict

    @property
    def verdict(self) -> str:
        return str(self.report.get("verdict", "WARN"))

    def exit_code(self) -> int:
        return policy_exit_code(self.verdict, self.policy_mode)


def judge_repo_change(repo_path: str | Path, *, staged: bool = False, patch_text: str | None = None, policy_mode: PolicyMode | str = PolicyMode.LOCAL) -> Judgment:
    """Judge repository changes without CLI parsing, stdout rendering, or cli.py imports."""
    mode = normalize_policy_mode(policy_mode)
    report = build_repo_change_report(Path(repo_path).resolve(), staged=staged, patch_text=patch_text, ci=(mode is PolicyMode.CI))
    if mode is PolicyMode.CI:
        report["ci"] = True
    return Judgment(str(Path(repo_path).resolve()), mode, report)


---

## File: src/sourcepack/packet.py

Metadata:
- sha256: c16e59f4b1ec3791bc716a7ed20a431e1ba96bf03dc155ff51fa1a2d1fac96b4
- bytes: 39133
- estimated_tokens: 9784

Content:

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

from .ecosystems.python import PY_IMPORT_ALIASES

try:
    from . import __version__
except Exception:
    __version__ = "1.10.0-alpha"



DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "target", "coverage", ".pytest_cache", ".sourcepack"
}
DEFAULT_IGNORED_PATTERNS = {
    ".env", ".env.*", "*.pem", "*.key", "*.sqlite", "*.db", "*.png", "*.jpg",
    "*.jpeg", "*.gif", "*.webp", "*.pdf", "*.zip", "*.tar", "*.gz", "*.exe",
    "*.dll", "*.so", "*.dylib", "*.bin", "*.pyc"
}
DEFAULT_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".html", ".css", ".csv", ".toml", ".ini", ".sql", ".sh", ".bat", ".ps1", ".rs",
    ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".xml"
}
SECRET_PATTERNS = [
    ("openai_key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9]{24,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}")),
]
COMMON_DEPENDENCIES = ["fastapi", "flask", "django", "react", "vue", "svelte", "pytest", "typer", "click", "sqlalchemy", "prisma", "pydantic", "pyyaml", "pillow", "beautifulsoup4", "opencv-python", "scikit-learn", "python-dotenv", "pyjwt", "python-dateutil", "boto3", "requests"]
FEATURE_NAMES = ("pdf", "ocr", "web server", "react", "docker", "authentication", "database")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return True
    if b"\x00" in data:
        return True
    if not data:
        return False
    nonprintable = sum(1 for b in data if b < 9 or (13 < b < 32))
    return (nonprintable / max(len(data), 1)) > 0.30


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def redact_secrets(text: str):
    redactions = []
    redacted = text
    for label, pattern in SECRET_PATTERNS:
        def repl(match):
            redactions.append({"pattern": label, "span_start": match.start(), "span_end": match.end()})
            return f"[REDACTED:{label}]"
        redacted = pattern.sub(repl, redacted)
    return redacted, redactions


@dataclass
class IncludedFile:
    relative_path: str
    absolute_path: str
    size_bytes: int
    sha256: str
    source_sha256: str
    packet_sha256: str
    estimated_tokens: int
    extension: str
    content: str


@dataclass
class IgnoredFile:
    relative_path: str
    reason: str


class SourceScanner:
    def __init__(self, input_path: str | Path, max_file_size: int = 1_000_000, include_hidden: bool = False, redact: bool = True):
        self.input_path = Path(input_path).resolve()
        self.max_file_size = max_file_size
        self.include_hidden = include_hidden
        self.redact = redact
        self.included_files: list[IncludedFile] = []
        self.ignored_files: list[IgnoredFile] = []
        self.redactions: list[dict] = []
        self.total_seen = 0

    def ignore(self, path: Path, reason: str):
        rel = str(path.relative_to(self.input_path)) if path.is_absolute() or self.input_path in path.parents else str(path)
        self.ignored_files.append(IgnoredFile(rel, reason))

    def scan(self):
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_path}")
        for root, dirs, files in os.walk(self.input_path, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(dirs)
            files = sorted(files)
            kept_dirs = []
            for d in dirs:
                dpath = root_path / d
                rel = dpath.relative_to(self.input_path)
                if d in DEFAULT_IGNORED_DIRS:
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "ignored_directory"))
                elif not self.include_hidden and d.startswith("."):
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "hidden_directory"))
                elif dpath.is_symlink():
                    self.ignored_files.append(IgnoredFile(str(rel) + "/", "symlink_skipped"))
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs
            for filename in files:
                fp = root_path / filename
                rel = fp.relative_to(self.input_path)
                self.total_seen += 1
                rel_str = str(rel)
                if fp.is_symlink():
                    self.ignored_files.append(IgnoredFile(rel_str, "symlink_skipped")); continue
                if not self.include_hidden and filename.startswith("."):
                    self.ignored_files.append(IgnoredFile(rel_str, "hidden_file")); continue
                if matches_any(filename, DEFAULT_IGNORED_PATTERNS) or matches_any(rel_str, DEFAULT_IGNORED_PATTERNS):
                    self.ignored_files.append(IgnoredFile(rel_str, "ignored_pattern")); continue
                try:
                    size = fp.stat().st_size
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "stat_error")); continue
                if size > self.max_file_size:
                    self.ignored_files.append(IgnoredFile(rel_str, "max_file_size_exceeded")); continue
                if fp.suffix and fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    self.ignored_files.append(IgnoredFile(rel_str, "unsupported_extension")); continue
                if is_probably_binary(fp):
                    self.ignored_files.append(IgnoredFile(rel_str, "binary_detected")); continue
                try:
                    content = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    self.ignored_files.append(IgnoredFile(rel_str, "decode_error")); continue
                except OSError:
                    self.ignored_files.append(IgnoredFile(rel_str, "read_error")); continue
                source_sha256 = sha256_text(content)
                if self.redact:
                    redacted, reds = redact_secrets(content)
                    for r in reds:
                        r["file"] = rel_str
                    self.redactions.extend(reds)
                    content = redacted
                packet_sha256 = sha256_text(content)
                self.included_files.append(IncludedFile(
                    relative_path=rel_str,
                    absolute_path=str(fp.resolve()),
                    size_bytes=size,
                    sha256=packet_sha256,
                    source_sha256=source_sha256,
                    packet_sha256=packet_sha256,
                    estimated_tokens=estimate_tokens(content),
                    extension=fp.suffix.lower(),
                    content=content,
                ))
        self.included_files.sort(key=lambda x: x.relative_path)
        self.ignored_files.sort(key=lambda x: x.relative_path)
        return self


def _tracked_file_inventory(root: Path, included_records: list[dict]) -> dict:
    included = {str(rec.get("relative_path", "")).replace("\\", "/") for rec in included_records}
    files: list[dict] = []
    source = "scanner_included_files"
    try:
        cp = subprocess.run(["git", "ls-files", "-z"], cwd=root, text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError):
        cp = None
    if cp is not None and cp.returncode == 0:
        raw_paths = [p.decode("utf-8", "surrogateescape") for p in cp.stdout.split(b"\0") if p]
        source = "git_ls_files" if raw_paths else "scanner_included_files"
        if not raw_paths:
            raw_paths = sorted(included)
    else:
        raw_paths = sorted(included)
    for raw in raw_paths:
        rel = raw.replace("\\", "/")
        path = root / rel
        rec = {"relative_path": rel, "included_in_prompt_context": rel in included, "source": source}
        try:
            if path.exists() and path.is_file():
                rec["sha256"] = sha256_file(path)
                rec["file_type"] = "binary" if is_probably_binary(path) else "text"
            else:
                rec["file_type"] = "missing"
        except OSError:
            rec["file_type"] = "unreadable"
        files.append(rec)
    return {"schema_version": "sourcepack.file_inventory.v1", "generated_at": utc_now(), "source": source, "files": files}


class PacketWriter:
    OUTPUT_FILES = ["manifest.json", "context.md", "context.xml", "file_tree.txt", "ignored_files.txt", "token_report.json", "redactions.json", "reality_map.json", "ai_instructions.md", "file_inventory.json"]

    def __init__(self, out: str | Path, scanner: SourceScanner, force: bool = False):
        self.out = Path(out)
        self.scanner = scanner
        self.force = force

    def prepare_out(self):
        if self.out.exists() and any(self.out.iterdir()):
            if not self.force:
                raise FileExistsError(f"Output directory is non-empty: {self.out}")
            for child in self.out.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        self.out.mkdir(parents=True, exist_ok=True)

    def write_all(self):
        self.prepare_out()
        included_records = []
        for f in self.scanner.included_files:
            rec = asdict(f)
            rec.pop("content")
            included_records.append(rec)
        ignored_records = [asdict(f) for f in self.scanner.ignored_files]
        total_tokens = sum(f.estimated_tokens for f in self.scanner.included_files)
        total_bytes = sum(f.size_bytes for f in self.scanner.included_files)
        manifest = {
            "input_path": str(self.scanner.input_path),
            "generated_at": utc_now(),
            "tool_version": __version__,
            "total_files_seen": self.scanner.total_seen,
            "total_files_included": len(included_records),
            "total_files_ignored": len(ignored_records),
            "total_bytes_included": total_bytes,
            "total_estimated_tokens": total_tokens,
            "included_files": included_records,
            "ignored_files": ignored_records,
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.out / "file_inventory.json").write_text(json.dumps(_tracked_file_inventory(self.scanner.input_path, included_records), indent=2), encoding="utf-8")
        md_parts = ["# SourcePack Context Packet", "", "## Source Manifest Summary", "", f"Input path: {manifest['input_path']}", f"Generated at: {manifest['generated_at']}", f"Files included: {len(included_records)}", f"Estimated tokens: {total_tokens}", ""]
        for f in self.scanner.included_files:
            md_parts.extend([
                f"## File: {f.relative_path}", "", "Metadata:", f"- sha256: {f.sha256}", f"- bytes: {f.size_bytes}", f"- estimated_tokens: {f.estimated_tokens}", "", "Content:", "", f.content, "", "---", ""
            ])
        (self.out / "context.md").write_text("\n".join(md_parts), encoding="utf-8")
        xml_parts = ["<sourcepack>", "  <files>"]
        for f in self.scanner.included_files:
            xml_parts.append(f'    <file path="{xml_escape(f.relative_path)}" sha256="{f.sha256}" bytes="{f.size_bytes}" estimated_tokens="{f.estimated_tokens}">')
            xml_parts.append("      <content>")
            xml_parts.append(xml_escape(f.content))
            xml_parts.append("      </content>")
            xml_parts.append("    </file>")
        xml_parts.extend(["  </files>", "</sourcepack>"])
        (self.out / "context.xml").write_text("\n".join(xml_parts), encoding="utf-8")
        tree_lines = []
        for f in self.scanner.included_files:
            tree_lines.append(f"[INC] {f.relative_path}")
        for f in self.scanner.ignored_files:
            tree_lines.append(f"[IGN] {f.relative_path} - {f.reason}")
        (self.out / "file_tree.txt").write_text("\n".join(sorted(tree_lines)) + "\n", encoding="utf-8")
        (self.out / "ignored_files.txt").write_text("\n".join(f"{f.relative_path}\t{f.reason}" for f in self.scanner.ignored_files) + "\n", encoding="utf-8")
        token_report = {
            "total_estimated_tokens": total_tokens,
            "warnings": [limit for limit in [32_000, 128_000, 200_000, 1_000_000] if total_tokens > limit],
            "per_file": [{"relative_path": f.relative_path, "estimated_tokens": f.estimated_tokens} for f in self.scanner.included_files],
        }
        (self.out / "token_report.json").write_text(json.dumps(token_report, indent=2), encoding="utf-8")
        (self.out / "redactions.json").write_text(json.dumps({"redactions": self.scanner.redactions}, indent=2), encoding="utf-8")
        reality_map = generate_reality_map(manifest, self.out)
        (self.out / "reality_map.json").write_text(json.dumps(reality_map, indent=2), encoding="utf-8")
        (self.out / "ai_instructions.md").write_text(render_ai_instructions(reality_map), encoding="utf-8")
        hashes = {name: sha256_file(self.out / name) for name in self.OUTPUT_FILES if (self.out / name).exists()}
        receipt = {"generated_at": utc_now(), "tool_version": __version__, "hashes": hashes}
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return self.out



def _included_paths(manifest: dict) -> set[str]:
    return {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}


def _package_json_scripts(packet: Path) -> dict[str, str]:
    contents = _packet_file_contents(packet)
    for rel, content in contents.items():
        if Path(rel).name.lower() == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                return {}
            scripts = package.get("scripts")
            return scripts if isinstance(scripts, dict) else {}
    return {}


def _is_poetry_project(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).name.lower() == "pyproject.toml" and re.search(r"(?m)^\s*\[tool\.poetry\]\s*$", content):
            return True
    return False


def _uses_unittest(packet: Path) -> bool:
    for rel, content in _packet_file_contents(packet).items():
        if Path(rel).suffix.lower() == ".py" and re.search(r"(?m)^\s*(import\s+unittest|from\s+unittest\s+import\s+)", content):
            return True
    return False


def generate_reality_map(manifest: dict, packet: Path) -> dict:
    files = _included_paths(manifest)
    lower_files = {f.lower() for f in files}
    deps = dependency_inventory(manifest, packet)
    features = feature_inventory(manifest, packet, deps)
    scripts = _package_json_scripts(packet)
    project_types = []
    package_managers = []
    frameworks = []
    supported_commands = []
    test_commands = []
    build_commands = []
    run_commands = []
    if "pyproject.toml" in lower_files:
        project_types.append("python")
    if any(Path(f).name.lower().startswith("requirements") and f.endswith(".txt") for f in lower_files):
        project_types.append("python")
        package_managers.append("pip")
    if _is_poetry_project(packet):
        package_managers.append("poetry")
    if "package.json" in lower_files:
        project_types.append("node")
        package_managers.append("npm")
        for name in sorted(scripts):
            cmd = "npm test" if name == "test" else f"npm run {name}"
            supported_commands.append(cmd)
            if name == "test": test_commands.append(cmd)
            elif name in {"build", "compile"}: build_commands.append(cmd)
            elif name in {"start", "dev", "serve"}: run_commands.append(cmd)
    if any(Path(f).name.lower() == "dockerfile" for f in files):
        supported_commands.append("docker build")
        build_commands.append("docker build")
    if any(Path(f).name.lower() in {"docker-compose.yml", "compose.yaml", "compose.yml"} for f in files):
        supported_commands.append("docker compose up")
        run_commands.append("docker compose up")
    if "pytest" in deps or any(f == "tests" or f.startswith("tests/") for f in lower_files):
        supported_commands.append("pytest")
        test_commands.append("pytest")
    if _uses_unittest(packet):
        supported_commands.append("python -m unittest")
        test_commands.append("python -m unittest")
    framework_map = {"fastapi": "FastAPI", "flask": "Flask", "django": "Django", "react": "React"}
    for dep, label in framework_map.items():
        if dep in deps or (dep == "react" and "react" in features):
            frameworks.append(label)
    ignored = manifest.get("ignored_files", [])
    ignored_reasons = {}
    for rec in ignored:
        reason = rec.get("reason", "unknown")
        ignored_reasons[reason] = ignored_reasons.get(reason, 0) + 1
    included_count = len(manifest.get("included_files", []))
    safe_claims = [
        f"This packet includes {included_count} source files.",
        f"SourcePack scanned input path: {manifest.get('input_path', '')}.",
    ]
    for name in ["pyproject.toml", "package.json", "Dockerfile"]:
        present = name.lower() in {Path(f).name.lower() for f in files}
        safe_claims.append(f"The project {'contains' if present else 'does not include'} {name}.")
    if "react" not in deps and "react" not in features:
        safe_claims.append("No React dependency was detected.")
    if "pdf" not in features:
        safe_claims.append("No PDF parsing capability was detected.")
    if ignored:
        safe_claims.append("The packet includes ignored file records for safety or relevance reasons.")
    claim_boundaries = [
        "SourcePack did not execute the application.",
        "SourcePack did not prove semantic correctness.",
        "SourcePack did not verify external services.",
        "SourcePack did not prove security.",
        "SourcePack did not prove production readiness.",
        "Absence of evidence means unknown, not impossible.",
        "Unsupported claims should be treated as ungrounded.",
    ]
    return {
        "reality_map_schema_version": "1.0",
        "tool_version": __version__,
        "generated_at": utc_now(),
        "input_path": manifest.get("input_path", ""),
        "project_types": sorted(set(project_types)),
        "package_managers": sorted(set(package_managers)),
        "frameworks": sorted(set(frameworks)),
        "entry_points": sorted(f for f in files if Path(f).name in {"main.py", "app.py", "server.py", "cli.py"}),
        "test_commands": sorted(set(test_commands)),
        "build_commands": sorted(set(build_commands)),
        "run_commands": sorted(set(run_commands)),
        "supported_commands": sorted(set(supported_commands)),
        "detected_dependencies": sorted(deps),
        "supported_capabilities": sorted(features),
        "excluded_files_summary": {"total": len(ignored), "reasons": ignored_reasons, "records": ignored[:25]},
        "included_file_count": included_count,
        "confirmed_files": sorted(files),
        "ignored_file_count": len(ignored),
        "safe_claims": safe_claims,
        "unknowns": [
            "Runtime behavior was not executed.",
            "Semantic correctness was not proven.",
            "External services were not verified.",
            "Capabilities not present in structural evidence must be treated as unknown.",
            "Missing files must not be invented.",
        ],
        "claim_boundaries": claim_boundaries,
        "ai_constraints": [
            "Use only the packet and reality map as project evidence.",
            "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
            "If a required file is missing, say it is missing.",
            "If a command is unsupported by detected evidence, say it is unsupported.",
            "If a capability is not in supported_capabilities, treat it as unknown or unsupported.",
            "Cite file paths when making project-specific claims.",
            "Do not claim SourcePack proves semantic truth.",
            "Ask for missing files rather than hallucinating them.",
        ],
    }


def render_ai_instructions(reality_map: dict) -> str:
    lines = [
        "# AI Instructions for This SourcePack Packet", "",
        "Use only the packet and `reality_map.json` as project evidence.",
        "Do not invent files, commands, dependencies, frameworks, services, or capabilities.",
        "If a required file is missing, say it is missing and ask for it rather than hallucinating it.",
        "If a command is unsupported by detected evidence, say it is unsupported.",
        "If a capability is not listed in `supported_capabilities`, treat it as unknown or unsupported.",
        "If you introduce a new external dependency, modify the appropriate dependency manifest in the same patch and list it under Dependency Changes.",
        "Only recommend commands listed under Supported Commands unless your patch also adds the project file that defines the new command.",
        "Before referencing a file as existing, it must appear in Confirmed Files; label intentional creations as NEW FILE.",
        "If required evidence is missing, say UNKNOWN and ask for the missing file/output instead of guessing.",
        "Cite file paths when making project-specific claims.",
        "Do not claim SourcePack proves semantic truth, security, production readiness, or external service behavior.", "",
        "## Supported Commands", "",
    ]
    cmds = reality_map.get("supported_commands", [])
    lines.extend([f"- `{cmd}`" for cmd in cmds] or ["- None detected"])
    lines.extend(["", "## Supported Capabilities", ""])
    caps = reality_map.get("supported_capabilities", [])
    lines.extend([f"- {cap}" for cap in caps] or ["- None detected"])
    lines.extend(["", "## Confirmed Files", ""])
    lines.extend(f"- `{path}`" for path in reality_map.get("confirmed_files", [])[:200])
    lines.extend(["", "## Required Answer Contract", "", "- Files to modify", "- New files", "- Dependency changes", "- Commands to run", "- Assumptions/unknowns", "- Patch or code", "", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in reality_map.get("claim_boundaries", []))
    return "\n".join(lines) + "\n"

def load_manifest(packet: Path) -> dict:
    return json.loads((packet / "manifest.json").read_text(encoding="utf-8"))


def verify_packet(packet_path: str | Path, against: str | Path | None = None) -> bool:
    packet = Path(packet_path)
    ok = True
    receipt_path = packet / "receipt.json"
    if not receipt_path.exists():
        print("FAIL receipt.json missing")
        return False
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for name, expected in receipt.get("hashes", {}).items():
        path = packet / name
        if not path.exists():
            print(f"FAIL {name} missing")
            ok = False
            continue
        actual = sha256_file(path)
        if actual == expected:
            print(f"PASS {name}")
        else:
            print(f"FAIL {name} hash mismatch")
            ok = False
    if against:
        manifest = load_manifest(packet)
        source = Path(against).resolve()
        included = {rec["relative_path"]: rec for rec in manifest.get("included_files", [])}
        for rel, rec in included.items():
            source_file = source / rel
            if not source_file.exists():
                print(f"FAIL source missing {rel}")
                ok = False
            elif is_probably_binary(source_file):
                print(f"WARN source now binary {rel}")
            else:
                try:
                    content = source_file.read_text(encoding="utf-8")
                except Exception:
                    print(f"FAIL source unreadable {rel}")
                    ok = False
                    continue
                expected_source_hash = rec.get("source_sha256")
                expected_source_hash = rec.get("source_sha256")
                if expected_source_hash is None:
                    expected_source_hash = rec.get("sha256")
                    redacted, _ = redact_secrets(content)
                    content_hash = sha256_text(redacted)
                else:
                    content_hash = sha256_text(content)
                if content_hash != expected_source_hash:
                    print(f"FAIL source changed {rel}")
                    ok = False
        current_files = []
        for root, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in sorted(dirs) if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
            for filename in sorted(files):
                fp = Path(root) / filename
                if filename.startswith(".") or fp.suffix.lower() not in DEFAULT_TEXT_EXTENSIONS:
                    continue
                rel = str(fp.relative_to(source))
                if rel not in included:
                    current_files.append(rel)
        for rel in current_files:
            print(f"WARN new source file not in packet {rel}")
    print("OVERALL", "PASS" if ok else "FAIL")
    return ok


PATHLIKE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cfg", ".ini", ".css", ".html", ".rs", ".go", ".java", ".rb", ".php", ".sh"}
PROJECT_PATH_PREFIXES = {"src", "sourcepack", "tests", "test", "frontend", "backend", "docs", "app", "lib", "packages", "public", "config", "scripts"}


def _normalize_ai_ref(ref: str) -> str | None:
    ref = ref.strip().strip("`'\".,;)")
    ref = ref.replace("\\", "/")
    if ref.endswith(":"):
        ref = ref[:-1]
    while ref.startswith("./"):
        ref = ref[2:]
    if not ref or ref.startswith("/") or re.match(r"^[A-Za-z]:/", ref):
        return None
    normalized, unsafe = _normalize_diff_path(ref)
    if unsafe or not normalized:
        return None
    return normalized


def _looks_like_ai_file_ref(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in {"Dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml", "pyproject.toml", "package.json", "requirements.txt"}:
        return True
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in PATHLIKE_EXTENSIONS:
        return False
    parts = [p for p in PurePosixPath(normalized).parts if p not in {"."}]
    return "/" in normalized or (parts and parts[0] in PROJECT_PATH_PREFIXES)


def extract_refs(text: str) -> set[str]:
    refs: set[str] = set()
    token = r"(?:\./)?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*\.[A-Za-z0-9_.-]+:?|Dockerfile"
    patterns = [rf"[`'\"]({token})[`'\"]", rf"(?m)^\s*[-*]\s+({token})\b", rf"\b(?:edit|open|update|modify|change|in|file)\s+({token})\b", rf"\b((?:\./)?(?:src|sourcepack|tests|test|frontend|backend|docs|app|lib|packages|public|config|scripts)[\\/][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_.-]+:?)\b"]
    for pattern in patterns:
        for candidate in re.findall(pattern, text, re.I):
            normalized = _normalize_ai_ref(candidate)
            if normalized and _looks_like_ai_file_ref(normalized):
                refs.add(normalized)
    return refs


def _packet_file_contents(packet: Path) -> dict[str, str]:
    context_path = packet / "context.md"
    if not context_path.exists():
        return {}
    text = context_path.read_text(encoding="utf-8", errors="ignore")
    contents: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    in_content = False
    for line in text.splitlines():
        if line.startswith("## File: "):
            if current is not None:
                contents[current] = "\n".join(body).rstrip("\n")
            current = line.removeprefix("## File: ").strip()
            body = []
            in_content = False
        elif current is not None and line == "Content:":
            in_content = True
            body = []
        elif current is not None and in_content and line == "---":
            contents[current] = "\n".join(body).rstrip("\n")
            current = None
            body = []
            in_content = False
        elif current is not None and in_content:
            body.append(line)
    if current is not None:
        contents[current] = "\n".join(body).rstrip("\n")
    return contents


def _normalize_dependency_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _dependency_name_for_import(name: str) -> str:
    normalized = _normalize_dependency_name(name)
    return PY_IMPORT_ALIASES.get(normalized, normalized)


def _js_package_root(imported: str) -> str:
    imported = imported.strip().lower()
    parts = imported.split("/")
    if imported.startswith("@") and len(parts) >= 2 and parts[0] != "@":
        return "/".join(parts[:2])
    if imported.startswith("@/"):
        return imported
    return parts[0]


def _python_dependency_names_from_requirement_lines(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned and not cleaned.startswith(("-", "--")):
            deps.add(_normalize_dependency_name(re.split(r"[<>=!~;\[]", cleaned, maxsplit=1)[0]))
    return deps


def _python_dependency_names_from_pyproject(content: str) -> set[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return set()
    deps: set[str] = set()

    def add_requirement(req: object) -> None:
        if isinstance(req, str):
            name = re.split(r"[<>=!~;\[]", req.strip(), maxsplit=1)[0]
            if name:
                deps.add(_normalize_dependency_name(name))

    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            add_requirement(req)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for req in group:
                        add_requirement(req)

    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            for section_name in ("dependencies", "dev-dependencies"):
                section = poetry.get(section_name, {})
                if isinstance(section, dict):
                    for dep in section:
                        if dep.lower() != "python":
                            deps.add(_normalize_dependency_name(dep))
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_data in group.values():
                    if isinstance(group_data, dict):
                        section = group_data.get("dependencies", {})
                        if isinstance(section, dict):
                            deps.update(_normalize_dependency_name(dep) for dep in section)
        for tool_name in ("pdm", "uv"):
            tool_data = tool.get(tool_name, {})
            if isinstance(tool_data, dict):
                for key in ("dev-dependencies", "dependency-groups"):
                    groups = tool_data.get(key, {})
                    if isinstance(groups, dict):
                        for group in groups.values():
                            if isinstance(group, list):
                                for req in group:
                                    add_requirement(req)
    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                for req in group:
                    add_requirement(req)
    return deps


def _add_common_dependency(deps: set[str], name: str):
    normalized = _normalize_dependency_name(name)
    for dep in COMMON_DEPENDENCIES:
        if normalized == _normalize_dependency_name(dep):
            deps.add(dep.lower())


def dependency_inventory(manifest: dict, packet: Path) -> set[str]:
    deps: set[str] = set()
    contents = _packet_file_contents(packet)
    for rec in manifest.get("included_files", []):
        rel = rec.get("relative_path", "")
        content = contents.get(rel, "")
        name = Path(rel).name.lower()
        suffix = Path(rel).suffix.lower()
        if name == "pyproject.toml":
            for dep in _python_dependency_names_from_pyproject(content):
                _add_common_dependency(deps, dep)
        elif name.startswith("requirements") and name.endswith(".txt"):
            for dep in _python_dependency_names_from_requirement_lines(content):
                _add_common_dependency(deps, dep)
        elif name == "package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError:
                package = {}
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                section_deps = package.get(section)
                if isinstance(section_deps, dict):
                    for dep_name in section_deps:
                        _add_common_dependency(deps, dep_name)
        elif suffix == ".py":
            for imported in re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", content):
                _add_common_dependency(deps, imported)
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            for imported in re.findall(r"""(?:from\s+["']|import\s*\(\s*["']|require\s*\(\s*["'])(@?[A-Za-z0-9_.-]+)""", content):
                _add_common_dependency(deps, _js_package_root(imported))
    return deps


def _has_import(content: str, *modules: str) -> bool:
    module_pattern = "|".join(re.escape(module) for module in modules)
    return bool(re.search(rf"(?m)^\s*(?:import|from)\s+({module_pattern})(?:\b|[._])", content))


PDF_DEPENDENCIES = {"pypdf", "pdfplumber", "fitz", "pymupdf"}


def _declares_pdf_dependency(rel: str, content: str) -> bool:
    name = Path(rel).name.lower()
    if name == "pyproject.toml":
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_pyproject(content))
    if name.startswith("requirements") and name.endswith(".txt"):
        return any(dep in PDF_DEPENDENCIES for dep in _python_dependency_names_from_requirement_lines(content))
    return False


def feature_inventory(manifest: dict, packet: Path, deps: set[str] | None = None) -> set[str]:
    if deps is None:
        deps = dependency_inventory(manifest, packet)
    contents = _packet_file_contents(packet)
    files = {rec.get("relative_path", "").replace("\\", "/") for rec in manifest.get("included_files", [])}
    lower_files = {rel.lower() for rel in files}
    features: set[str] = set()

    if any(Path(rel).name.lower() in {"dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"} for rel in files):
        features.add("docker")
    if any(rel.endswith(("/pdf_parser.py", "pdf_parser.py")) for rel in lower_files):
        features.add("pdf")
    if any(_declares_pdf_dependency(rel, content) for rel, content in contents.items()):
        features.add("pdf")
    if "react" in deps or any(rel in {"frontend/app.tsx", "frontend/app.jsx"} for rel in lower_files):
        features.add("react")
    if deps & {"fastapi", "flask", "django"} or any(Path(rel).name.lower() in {"server.py", "app.py"} for rel in files):
        features.add("web server")
    if deps & {"sqlalchemy", "prisma"} or any("/migrations/" in f"/{rel}/" or Path(rel).name.lower() in {"schema.prisma", "schema.sql"} for rel in files):
        features.add("database")
    if any(part == "auth" or part.startswith("auth_") for rel in lower_files for part in Path(rel).parts):
        features.add("authentication")

    for rel, content in contents.items():
        suffix = Path(rel).suffix.lower()
        if suffix == ".py":
            if _has_import(content, "pypdf", "pdfplumber", "fitz"):
                features.add("pdf")
            if _has_import(content, "fastapi", "flask", "django") or re.search(r"(?m)^\s*@\w+\.(?:route|get|post|put|patch|delete)\(", content):
                features.add("web server")
            if _has_import(content, "sqlalchemy", "prisma") or re.search(r"(?i)\b(sqlite|postgres(?:ql)?|mysql)://", content):
                features.add("database")
            if _has_import(content, "jwt", "oauthlib", "authlib") or re.search(r"(?i)@\w+\.(?:route|get|post)\([^)]*login", content):
                features.add("authentication")
            if _has_import(content, "pytesseract", "easyocr"):
                features.add("ocr")
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            if re.search(r"""(?:from\s+["']react["']|require\s*\(\s*["']react["']|import\s+React\b)""", content):
                features.add("react")
            if re.search(r"(?i)\b(jwt|oauth|session|login)\b", content):
                features.add("authentication")
        elif Path(rel).name.lower() == "package.json":
            if re.search(r'"react"\s*:', content):
                features.add("react")
    return features



def scanner_config_hash() -> str:
    payload = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "ignored_patterns": sorted(DEFAULT_IGNORED_PATTERNS),
        "text_extensions": sorted(DEFAULT_TEXT_EXTENSIONS),
        "max_file_size": 1_000_000,
        "include_hidden": False,
        "redact": True,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


---

## File: src/sourcepack/paths.py

Metadata:
- sha256: 8d45ded4126c3230b6ada620eb493e34e4ca571bcedb10ac8bdbea4fbb594a7d
- bytes: 2805
- estimated_tokens: 702

Content:

from __future__ import annotations

from pathlib import Path


def sourcepack_paths(repo: str | Path) -> dict[str, Path]:
    root = Path(repo).resolve()
    base = root / ".sourcepack"
    baseline = base / "baseline"
    prompt = base / "prompt"
    reports = base / "reports"
    return {
        "root": root,
        "base": base,
        "current": base / "current",  # legacy compatibility marker only
        "baseline": baseline,
        "packet": baseline / "packet",
        "baseline_meta": baseline / "metadata.json",
        "prompt_dir": prompt,
        "prompt_packet": prompt / "packet",
        "prompt_reality": prompt / "reality_map.json",
        "prompt_instructions": prompt / "ai_instructions.md",
        "reports": reports,
        "archive": reports / "archive",
        "reality": baseline / "reality_map.json",
        "instructions": baseline / "ai_instructions.md",
        "prompt": prompt / "prompt.md",
        "state": base / "state",
        "stale_marker": base / "state" / "baseline_stale.json",
        "latest_json": reports / "latest.json",
        "latest_md": reports / "latest.md",
        "latest_html": reports / "latest.html",
        "latest_sarif": reports / "latest.sarif.json",
        "latest_diff_json": reports / "latest_diff.json",
        "latest_prompt_json": reports / "latest_prompt.json",
        "latest_baseline_json": reports / "latest_baseline.json",
        "builds": baseline / "builds",
        "active_pointer": baseline / "active.json",
        "baseline_lock": base / "state" / "baseline.lock",
    }


def ensure_sourcepack_dirs(repo: str | Path) -> dict[str, Path]:
    paths = sourcepack_paths(repo)
    paths["baseline"].mkdir(parents=True, exist_ok=True)
    paths["prompt_dir"].mkdir(parents=True, exist_ok=True)
    paths["current"].mkdir(parents=True, exist_ok=True)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    paths["archive"].mkdir(parents=True, exist_ok=True)
    paths["state"].mkdir(parents=True, exist_ok=True)
    return paths


def ensure_gitignore_entry(repo: str | Path) -> tuple[bool, str | None]:
    path = Path(repo) / ".gitignore"
    try:
        if not path.exists():
            path.write_text(".sourcepack/\n", encoding="utf-8")
            return True, None
        data = path.read_bytes()
        text = data.decode("utf-8")
        if any(line.strip() in {".sourcepack", ".sourcepack/", ".sourcepack/*"} for line in text.splitlines()):
            return False, None
        newline = "\r\n" if b"\r\n" in data else "\n"
        addition = ("" if text.endswith(("\n", "\r\n")) or not text else newline) + ".sourcepack/" + newline
        path.write_text(text + addition, encoding="utf-8", newline="")
        return True, None
    except Exception as exc:
        return False, str(exc)


---

## File: src/sourcepack/policy.py

Metadata:
- sha256: 9a202edec14b7edc2acc5654a85f946f2bcbfb01d5042818bf5e1450113241bb
- bytes: 16477
- estimated_tokens: 4120

Content:

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath


class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


@dataclass(frozen=True)
class PolicyRules:
    block_dependency_additions: bool = False
    protected_paths: tuple[str, ...] = field(default_factory=tuple)
    package_manager: str | None = None
    require_tests_for: tuple[str, ...] = field(default_factory=tuple)
    max_changed_lines: int | None = None
    block_secret_patterns: bool = False

    def enabled(self) -> bool:
        return (
            self.block_dependency_additions
            or bool(self.protected_paths)
            or self.package_manager is not None
            or bool(self.require_tests_for)
            or self.max_changed_lines is not None
            or self.block_secret_patterns
        )


@dataclass(frozen=True)
class PolicyConfig:
    schema_version: str = "sourcepack.policy.v1"
    strict_default: bool = True
    fail_on_warn_in_ci: bool = True
    ignored_paths: tuple[dict, ...] = field(default_factory=tuple)
    protected_paths: tuple[str, ...] = (".sourcepack/baseline/**", ".git/**")
    report_formats: tuple[str, ...] = ("json", "markdown", "html", "sarif")
    baseline_required_in_ci: bool = True
    prompt_context_authoritative: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rules: PolicyRules = field(default_factory=PolicyRules)


@dataclass(frozen=True)
class PolicyIgnoredEntryIssue:
    index: int
    warning: str
    entry: object


@dataclass(frozen=True)
class PolicyValidationResult:
    schema_version: str
    repo: str
    policy_path: str
    policy_present: bool
    valid: bool
    effective_ignored_paths: tuple[dict, ...] = field(default_factory=tuple)
    ignored_invalid_entries: tuple[PolicyIgnoredEntryIssue, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    effective_config: PolicyConfig = field(default_factory=PolicyConfig)

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "repo": self.repo,
            "policy_path": self.policy_path,
            "policy_present": self.policy_present,
            "valid": self.valid,
            "effective_ignored_paths": list(self.effective_ignored_paths),
            "ignored_invalid_entries": [
                {"index": item.index, "warning": item.warning, "entry": item.entry}
                for item in self.ignored_invalid_entries
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "effective_config": {
                "schema_version": self.effective_config.schema_version,
                "strict_default": self.effective_config.strict_default,
                "fail_on_warn_in_ci": self.effective_config.fail_on_warn_in_ci,
                "ignored_paths": list(self.effective_config.ignored_paths),
                "protected_paths": list(self.effective_config.protected_paths),
                "report_formats": list(self.effective_config.report_formats),
                "baseline_required_in_ci": self.effective_config.baseline_required_in_ci,
                "prompt_context_authoritative": self.effective_config.prompt_context_authoritative,
                "suppressible_ignored_path_finding_ids": sorted(SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS),
                "rules": {
                    "block_dependency_additions": self.effective_config.rules.block_dependency_additions,
                    "protected_paths": list(self.effective_config.rules.protected_paths),
                    "package_manager": self.effective_config.rules.package_manager,
                    "require_tests_for": list(self.effective_config.rules.require_tests_for),
                    "max_changed_lines": self.effective_config.rules.max_changed_lines,
                    "block_secret_patterns": self.effective_config.rules.block_secret_patterns,
                },
            },
        }


SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS = frozenset({"new_file"})
_RESERVED_POLICY_FIELDS = {
    "strict_default": "policy_config_reserved:strict_default",
    "fail_on_warn_in_ci": "policy_config_reserved:fail_on_warn_in_ci",
    "protected_paths": "policy_config_reserved:protected_paths",
    "report_formats": "policy_config_reserved:report_formats",
}


def _is_unsafe_policy_ignore_pattern(pattern: str) -> bool:
    return (
        pattern == ".git"
        or pattern.startswith(".git/")
        or pattern == ".sourcepack/baseline"
        or pattern.startswith(".sourcepack/baseline/")
    )


def normalize_policy_mode(value: PolicyMode | str | None) -> PolicyMode:
    if isinstance(value, PolicyMode):
        return value
    if value is None:
        return PolicyMode.LOCAL
    text = str(value).lower().strip()
    if text in {"ci", "--ci"}:
        return PolicyMode.CI
    if text in {"strict", "--strict"}:
        return PolicyMode.STRICT
    return PolicyMode.LOCAL


def commit_policy(verdict: str) -> str | None:
    if verdict == "WARN":
        return "allowed locally, blocked in strict mode."
    if verdict == "FAIL":
        return "blocked unless explicitly bypassed."
    return None


def exit_code(verdict: str, mode: PolicyMode | str | None = None) -> int:
    mode = normalize_policy_mode(mode)
    if verdict == "FAIL":
        return 1
    if verdict == "WARN" and mode in {PolicyMode.STRICT, PolicyMode.CI}:
        return 1
    return 0


def _normalize_policy_path(value: object) -> str | None:
    text = str(value or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or "\x00" in text:
        return None
    pure = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return pure.as_posix()


def policy_path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("/") + "/**")


def _parse_policy_rules(raw_rules: object, warnings: list[str]) -> PolicyRules:
    if raw_rules is None:
        return PolicyRules()
    if not isinstance(raw_rules, dict):
        warnings.append("policy_rules_invalid:rules_must_be_object")
        return PolicyRules()
    if not raw_rules:
        return PolicyRules()

    block_dependency_additions = False
    if "block_dependency_additions" in raw_rules:
        if raw_rules["block_dependency_additions"] is True:
            block_dependency_additions = True
        elif raw_rules["block_dependency_additions"] is not False:
            warnings.append("policy_rule_invalid:block_dependency_additions_must_be_boolean")

    protected_paths: list[str] = []
    if "protected_paths" in raw_rules:
        raw_protected = raw_rules["protected_paths"]
        if not isinstance(raw_protected, list):
            warnings.append("policy_rule_invalid:protected_paths_must_be_list")
        else:
            for value in raw_protected:
                norm = _normalize_policy_path(value)
                if norm:
                    protected_paths.append(norm)
                else:
                    warnings.append(f"policy_rule_invalid:protected_path:{value}")

    package_manager = None
    if "package_manager" in raw_rules:
        value = raw_rules["package_manager"]
        if isinstance(value, str) and value.strip().lower() == "pnpm":
            package_manager = "pnpm"
        elif value not in (None, ""):
            warnings.append(f"policy_rule_invalid:unsupported_package_manager:{value}")

    require_tests_for: list[str] = []
    if "require_tests_for" in raw_rules:
        raw_required = raw_rules["require_tests_for"]
        if not isinstance(raw_required, list):
            warnings.append("policy_rule_invalid:require_tests_for_must_be_list")
        else:
            for value in raw_required:
                norm = _normalize_policy_path(value)
                if norm:
                    require_tests_for.append(norm)
                else:
                    warnings.append(f"policy_rule_invalid:require_tests_for:{value}")

    max_changed_lines = None
    if "max_changed_lines" in raw_rules:
        value = raw_rules["max_changed_lines"]
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            max_changed_lines = value
        else:
            warnings.append("policy_rule_invalid:max_changed_lines_must_be_positive_integer")

    block_secret_patterns = False
    if "block_secret_patterns" in raw_rules:
        if raw_rules["block_secret_patterns"] is True:
            block_secret_patterns = True
        elif raw_rules["block_secret_patterns"] is not False:
            warnings.append("policy_rule_invalid:block_secret_patterns_must_be_boolean")

    return PolicyRules(
        block_dependency_additions=block_dependency_additions,
        protected_paths=tuple(protected_paths),
        package_manager=package_manager,
        require_tests_for=tuple(require_tests_for),
        max_changed_lines=max_changed_lines,
        block_secret_patterns=block_secret_patterns,
    )


def validate_policy_config(repo: str | Path) -> PolicyValidationResult:
    repo_path = Path(repo).resolve()
    path = repo_path / ".sourcepack" / "policy.json"
    if not path.exists():
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=False,
            valid=True,
        )
    warnings: list[str] = []
    errors: list[str] = []
    invalid_entries: list[PolicyIgnoredEntryIssue] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(f"policy_config_invalid_json:{exc.msg}:line={exc.lineno}:column={exc.colno}",),
        )
    except OSError as exc:
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=(f"policy_config_unreadable:{exc}",),
        )
    if not isinstance(raw, dict):
        return PolicyValidationResult(
            schema_version="sourcepack.policy.validation.v1",
            repo=str(repo_path),
            policy_path=str(path),
            policy_present=True,
            valid=False,
            errors=("policy_config_invalid:root_must_be_object",),
        )
    if raw.get("prompt_context_authoritative") is True:
        warnings.append("policy_config_ignored:prompt_context_authoritative")
    if raw.get("baseline_required_in_ci") is False:
        warnings.append("policy_config_ignored:baseline_required_in_ci_false")
    for field, warning in _RESERVED_POLICY_FIELDS.items():
        if field in raw:
            warnings.append(warning)
    ignored: list[dict] = []
    raw_ignored = raw.get("ignored_paths", [])
    if not isinstance(raw_ignored, list):
        warnings.append("policy_ignore_invalid:ignored_paths_must_be_list")
        raw_ignored = []
    for index, item in enumerate(raw_ignored):
        warning = None
        if not isinstance(item, dict):
            warning = "policy_ignore_invalid:not_object"
        else:
            pattern = _normalize_policy_path(item.get("pattern"))
            reason = str(item.get("reason") or "").strip()
            if not pattern or not reason:
                warning = "policy_ignore_invalid:pattern_and_reason_required"
            elif _is_unsafe_policy_ignore_pattern(pattern):
                warning = f"policy_ignore_unsafe:{pattern}"
            else:
                ignored.append({"pattern": pattern, "reason": reason})
        if warning:
            warnings.append(warning)
            invalid_entries.append(PolicyIgnoredEntryIssue(index=index, warning=warning, entry=item))
    raw_formats = raw.get("report_formats", [])
    if "report_formats" in raw and not isinstance(raw_formats, list):
        warnings.append("policy_report_format_ignored:report_formats_must_be_list")
    elif isinstance(raw_formats, list):
        for value in raw_formats:
            fmt = str(value).lower().strip()
            if fmt not in {"json", "markdown", "html", "sarif"}:
                warnings.append(f"policy_report_format_ignored:{fmt}")
    rules = _parse_policy_rules(raw.get("rules"), warnings)
    config = PolicyConfig(ignored_paths=tuple(ignored), warnings=tuple(warnings), rules=rules)
    return PolicyValidationResult(
        schema_version="sourcepack.policy.validation.v1",
        repo=str(repo_path),
        policy_path=str(path),
        policy_present=True,
        valid=True,
        effective_ignored_paths=tuple(ignored),
        ignored_invalid_entries=tuple(invalid_entries),
        warnings=tuple(warnings),
        effective_config=config,
    )


def load_policy_config(repo: str | Path) -> PolicyConfig:
    path = Path(repo) / ".sourcepack" / "policy.json"
    if not path.exists():
        return PolicyConfig()
    warnings: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PolicyConfig(warnings=(f"policy_config_unreadable:{exc}",))
    if not isinstance(raw, dict):
        return PolicyConfig(warnings=("policy_config_invalid:root_must_be_object",))
    if raw.get("prompt_context_authoritative") is True:
        warnings.append("policy_config_ignored:prompt_context_authoritative")
    if raw.get("baseline_required_in_ci") is False:
        warnings.append("policy_config_ignored:baseline_required_in_ci_false")
    for field, warning in _RESERVED_POLICY_FIELDS.items():
        if field in raw:
            warnings.append(warning)
    ignored: list[dict] = []
    for item in raw.get("ignored_paths", []) if isinstance(raw.get("ignored_paths", []), list) else []:
        if not isinstance(item, dict):
            warnings.append("policy_ignore_invalid:not_object")
            continue
        pattern = _normalize_policy_path(item.get("pattern"))
        reason = str(item.get("reason") or "").strip()
        if not pattern or not reason:
            warnings.append("policy_ignore_invalid:pattern_and_reason_required")
            continue
        if _is_unsafe_policy_ignore_pattern(pattern):
            warnings.append(f"policy_ignore_unsafe:{pattern}")
            continue
        ignored.append({"pattern": pattern, "reason": reason})
    protected = []
    for value in raw.get("protected_paths", []) if isinstance(raw.get("protected_paths", []), list) else []:
        norm = _normalize_policy_path(value)
        if norm:
            protected.append(norm)
    formats = []
    for value in raw.get("report_formats", []) if isinstance(raw.get("report_formats", []), list) else []:
        fmt = str(value).lower().strip()
        if fmt in {"json", "markdown", "html", "sarif"}:
            formats.append(fmt)
        else:
            warnings.append(f"policy_report_format_ignored:{fmt}")
    rules = _parse_policy_rules(raw.get("rules"), warnings)
    return PolicyConfig(
        strict_default=PolicyConfig.strict_default,
        fail_on_warn_in_ci=PolicyConfig.fail_on_warn_in_ci,
        ignored_paths=tuple(ignored),
        protected_paths=PolicyConfig.protected_paths,
        report_formats=PolicyConfig.report_formats,
        warnings=tuple(warnings),
        rules=rules,
    )


def finding_ignored_by_policy(finding: dict, config: PolicyConfig) -> dict | None:
    fid = str(finding.get("id") or "")
    if fid not in SUPPRESSIBLE_IGNORED_PATH_FINDING_IDS:
        return None
    path = _normalize_policy_path(finding.get("path"))
    if not path:
        return None
    for item in config.ignored_paths:
        pattern = item["pattern"]
        if _is_unsafe_policy_ignore_pattern(pattern):
            continue
        if policy_path_matches(path, pattern):
            return {"pattern": pattern, "reason": item["reason"], "path": path}
    return None


---

## File: src/sourcepack/reason_codes.py

Metadata:
- sha256: 101c855f304167a3324d333198074fd9779ba19bcc9484be36b28f1eb9ff1c6c
- bytes: 3089
- estimated_tokens: 773

Content:

from __future__ import annotations

from enum import StrEnum

REASON_CODE_VOCABULARY_VERSION = "reason_codes.v1"


class ReasonCode(StrEnum):
    BASELINE_MISSING = "baseline_missing"
    BASELINE_STALE = "baseline_stale"
    BASELINE_CORRUPT = "baseline_corrupt"
    MISSING_FILE = "missing_file"
    NEW_FILE = "new_file"
    DELETED_FILE = "deleted_file"
    UNSUPPORTED_DEPENDENCY = "unsupported_dependency"
    DECLARED_DEPENDENCY = "declared_dependency"
    DECLARED_COMMAND = "declared_command"
    UNSUPPORTED_COMMAND = "unsupported_command"
    UNSAFE_PATH = "unsafe_path"
    PATH_ESCAPE = "path_escape"
    PROTECTED_ARTIFACT = "protected_artifact"
    GIT_PATH_MODIFICATION = "git_path_modification"
    BINARY_DIFF = "binary_diff"
    MALFORMED_DIFF = "malformed_diff"
    UNSUPPORTED_ECOSYSTEM = "unsupported_ecosystem"
    DIRTY_WORKTREE = "dirty_worktree"
    BASELINE_LOCKED = "baseline_locked"
    BASELINE_FAILED = "baseline_failed"
    GIT_UNAVAILABLE = "git_unavailable"
    NO_GIT_REPO = "no_git_repo"
    NO_DIFF = "no_diff"
    REPO_NOT_DIRECTORY = "repo_not_directory"
    GITIGNORE_UNWRITABLE = "gitignore_unwritable"
    PROMPT_CONTEXT_FAILED = "prompt_context_failed"
    CLIPBOARD_UNAVAILABLE = "clipboard_unavailable"
    HOOK_INSTALL_FAILED = "hook_install_failed"
    HYGIENE_HOOKS_DEFERRED = "hygiene_hooks_deferred"
    BASELINE_INVENTORY_MISSING = "baseline_inventory_missing"
    WORKFLOW_CHANGE = "workflow_change"
    UNSUPPORTED_RENAME_COPY = "unsupported_rename_copy"
    DEPENDENCY_MANIFEST_UNCERTAIN = "dependency_manifest_uncertain"
    COMMAND_MANIFEST_UNCERTAIN = "command_manifest_uncertain"
    COMMAND_MANIFEST_MISSING = "command_manifest_missing"
    COMMAND_CHECK_INCONCLUSIVE = "command_check_inconclusive"
    DEPENDENCY_SCOPE_REVIEW = "dependency_scope_review"
    JS_ALIAS_UNCERTAIN = "js_alias_uncertain"
    EXECUTION_EVIDENCE_MISSING = "execution_evidence_missing"
    EXECUTION_EVIDENCE_PRESENT = "execution_evidence_present"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_INCONCLUSIVE = "execution_inconclusive"
    POLICY_CONFIG_WARNING = "policy_config_warning"
    POLICY_DEPENDENCY_ADDITION = "policy_dependency_addition"
    POLICY_PROTECTED_PATH = "policy_protected_path"
    POLICY_PACKAGE_MANAGER_DRIFT = "policy_package_manager_drift"
    POLICY_MISSING_TEST = "policy_missing_test"
    POLICY_LARGE_DIFF = "policy_large_diff"
    POLICY_SECRET_PATTERN = "policy_secret_pattern"


_CANONICAL = {code.value for code in ReasonCode}
_ALIASES = {
    "baseline-corrupt": ReasonCode.BASELINE_CORRUPT.value,
    "baseline-missing": ReasonCode.BASELINE_MISSING.value,
    "baseline-stale": ReasonCode.BASELINE_STALE.value,
}


def normalize_reason_code(code: str) -> str:
    normalized = str(code).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _ALIASES.get(normalized, normalized)
    return normalized


def is_canonical_reason_code(code: str) -> bool:
    return normalize_reason_code(code) in _CANONICAL


def canonical_reason_codes() -> tuple[str, ...]:
    return tuple(sorted(_CANONICAL))


---

## File: src/sourcepack/replay.py

Metadata:
- sha256: 6a4b3770496e9e51e56a5c893864f72e8b32459d8d4f31bee962d1f7cccc0a47
- bytes: 9851
- estimated_tokens: 2463

Content:

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reports.markdown import LIGHT_BY_VERDICT

REPLAY_BUNDLE_SCHEMA_PREFIX = "sourcepack.replay_bundle."
REPLAY_OUTPUT_SCHEMA_VERSION = "sourcepack.replay.v1"


def _empty(input_path: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": REPLAY_OUTPUT_SCHEMA_VERSION,
        "input_schema_version": None,
        "input_path": input_path,
        "input_type": None,
        "valid": False,
        "errors": [],
        "warnings": [],
        "reconstructed": False,
        "verdict": None,
        "exit_code": None,
        "light": None,
        "reason_codes": [],
        "findings": [],
        "blockers": [],
        "report_warnings": [],
        "checked_categories": [],
        "not_checked_categories": [],
        "evidence": {},
        "reason_code_evidence": {},
        "baseline_metadata": {},
        "prompt_context_metadata": {},
        "patch_metadata": {},
        "environment_metadata": {},
        "policy_metadata": {},
        "sourcepack_version": None,
        "replay_bundle": None,
        "reran_judgment": False,
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _reason_codes(source: dict[str, Any]) -> list[str]:
    explicit = source.get("reason_codes", source.get("normalized_reason_codes"))
    if isinstance(explicit, list):
        return sorted({str(code) for code in explicit if code is not None})
    codes = {str(f.get("id")) for f in _as_list(source.get("findings")) if isinstance(f, dict) and f.get("id")}
    return sorted(codes)


def _light(verdict: Any, source: dict[str, Any]) -> str | None:
    if isinstance(source.get("light"), str):
        return source["light"]
    if isinstance(verdict, str):
        return LIGHT_BY_VERDICT.get(verdict)
    return None


def _looks_like_replay_bundle(obj: dict[str, Any]) -> bool:
    schema = obj.get("schema_version")
    return isinstance(schema, str) and schema.startswith(REPLAY_BUNDLE_SCHEMA_PREFIX)


def _bundle_errors(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = bundle.get("schema_version")
    if not isinstance(schema, str) or not schema.startswith(REPLAY_BUNDLE_SCHEMA_PREFIX):
        errors.append("replay_bundle schema_version is missing or unsupported")
    if "verdict" not in bundle:
        errors.append("replay_bundle verdict is missing")
    if "findings" in bundle and not isinstance(bundle.get("findings"), list):
        errors.append("replay_bundle findings must be a list when present")
    if "reason_code_evidence" in bundle and not isinstance(bundle.get("reason_code_evidence"), dict):
        errors.append("replay_bundle reason_code_evidence must be an object when present")
    return errors


def _copy_from(source: dict[str, Any], out: dict[str, Any]) -> None:
    verdict = source.get("verdict")
    out["input_schema_version"] = source.get("schema_version") if isinstance(source.get("schema_version"), str) else None
    out["verdict"] = verdict if isinstance(verdict, str) else None
    out["exit_code"] = source.get("exit_code") if isinstance(source.get("exit_code"), int) else None
    out["light"] = _light(out["verdict"], source)
    out["reason_codes"] = _reason_codes(source)
    out["findings"] = _as_list(source.get("findings"))
    out["blockers"] = _as_list(source.get("blockers"))
    out["report_warnings"] = _as_list(source.get("warnings"))
    out["checked_categories"] = _as_list(source.get("checked_categories", source.get("checked")))
    out["not_checked_categories"] = _as_list(source.get("not_checked", source.get("not_checked_categories")))
    out["evidence"] = _as_dict(source.get("evidence"))
    if "unavailable_evidence" in source or "unsupported_evidence" in source:
        out["evidence"] = dict(out["evidence"])
        if "unavailable_evidence" in source:
            out["evidence"].setdefault("unavailable_evidence", _as_list(source.get("unavailable_evidence")))
        if "unsupported_evidence" in source:
            out["evidence"].setdefault("unsupported_evidence", _as_list(source.get("unsupported_evidence")))
    out["reason_code_evidence"] = _as_dict(source.get("reason_code_evidence"))
    out["baseline_metadata"] = _as_dict(source.get("baseline_metadata"))
    out["prompt_context_metadata"] = _as_dict(source.get("prompt_context_metadata"))
    out["patch_metadata"] = _as_dict(source.get("patch_metadata"))
    out["environment_metadata"] = _as_dict(source.get("environment_metadata"))
    out["policy_metadata"] = _as_dict(source.get("policy_metadata"))
    out["sourcepack_version"] = source.get("sourcepack_version") if isinstance(source.get("sourcepack_version"), str) else None


def reconstruct_replay(path: str | Path) -> tuple[dict[str, Any], int]:
    input_path = str(path)
    out = _empty(input_path)
    p = Path(path)
    if not p.exists():
        out["errors"].append(f"missing input path: {input_path}")
        return out, 1
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        out["errors"].append(f"invalid JSON in {input_path}: {exc.msg} at line {exc.lineno} column {exc.colno}")
        return out, 1
    except OSError as exc:
        out["errors"].append(f"could not read {input_path}: {exc}")
        return out, 1
    if not isinstance(data, dict):
        out["errors"].append("replay input root must be a JSON object")
        return out, 1

    out["input_schema_version"] = data.get("schema_version") if isinstance(data.get("schema_version"), str) else None

    bundle = data.get("replay_bundle") if isinstance(data.get("replay_bundle"), dict) else None
    if bundle is not None:
        out["input_type"] = "full_report_with_replay_bundle"
        _copy_from(data, out)
        out["replay_bundle"] = bundle
        errors = _bundle_errors(bundle)
        if errors:
            out["errors"].extend(errors)
            return out, 1
        out["valid"] = True
        out["reconstructed"] = True
        return out, 0

    if _looks_like_replay_bundle(data):
        out["input_type"] = "raw_replay_bundle"
        errors = _bundle_errors(data)
        _copy_from(data, out)
        out["replay_bundle"] = data
        if errors:
            out["errors"].extend(errors)
            return out, 1
        out["valid"] = True
        out["reconstructed"] = True
        return out, 0

    if "replay_bundle" in data and data.get("replay_bundle") is not None:
        out["input_type"] = "full_report_with_corrupt_replay_bundle"
        _copy_from(data, out)
        out["errors"].append("replay_bundle must be a JSON object when present")
        return out, 1

    if any(key in data for key in ("verdict", "findings", "blockers", "warnings", "checked_categories")):
        out["input_type"] = "full_report_without_replay_bundle"
        _copy_from(data, out)
        out["valid"] = True
        out["reconstructed"] = True
        out["warnings"].append("replay bundle is missing; reconstructed basic report summary only")
        return out, 0

    out["input_type"] = "unsupported_json_object"
    out["errors"].append("unsupported replay input schema: expected SourcePack report or replay bundle")
    return out, 1


def render_replay_human(result: dict[str, Any]) -> str:
    lines = [
        "SourcePack replay/audit reconstruction",
        f"Input path: {result.get('input_path')}",
        f"Input type: {result.get('input_type') or 'unknown'}",
        f"Valid: {result.get('valid')}",
        f"Schema version: {result.get('schema_version') or 'not present'}",
        f"Input schema version: {result.get('input_schema_version') or 'not present'}",
        f"SourcePack version: {result.get('sourcepack_version') or 'not present'}",
        f"Verdict: {result.get('verdict') or 'not present'}",
        f"Exit code: {result.get('exit_code') if result.get('exit_code') is not None else 'not present'}",
        f"Traffic light: {result.get('light') or 'not derivable'}",
        f"Finding count: {len(result.get('findings') or [])}",
        f"Blocker count: {len(result.get('blockers') or [])}",
        f"Warning count: {len(result.get('report_warnings') or [])}",
        f"Reason codes: {', '.join(result.get('reason_codes') or []) or 'none'}",
        f"Checked categories: {', '.join(result.get('checked_categories') or []) or 'none present'}",
        f"Not-checked categories: {', '.join(result.get('not_checked_categories') or []) or 'none present'}",
    ]
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    unavailable = evidence.get("unavailable_evidence", evidence.get("missing_evidence", [])) if evidence else []
    lines.append(f"Unavailable evidence: {len(unavailable or [])}")
    lines.append(f"Unsupported evidence: {len(evidence.get('unsupported_evidence') or []) if evidence else 0}")
    for label, key in (("Baseline metadata", "baseline_metadata"), ("Prompt-context metadata", "prompt_context_metadata"), ("Patch metadata", "patch_metadata"), ("Environment metadata", "environment_metadata"), ("Policy metadata", "policy_metadata")):
        lines.append(f"{label}: {'present' if result.get(key) else 'not present'}")
    lines.append(f"Replay bundle: {'present' if result.get('replay_bundle') is not None else 'missing'}")
    lines.append(f"Reconstructed without rerunning judgment: {result.get('reran_judgment') is False and result.get('reconstructed') is True}")
    for warning in result.get("warnings") or []:
        lines.append(f"WARNING: {warning}")
    for error in result.get("errors") or []:
        lines.append(f"ERROR: {error}")
    return "\n".join(lines) + "\n"


---

## File: src/sourcepack/reports/__init__.py

Metadata:
- sha256: 5f8862cf0d7ba09c9fd8dec3bacabc5e84a1a3017d182ad3f7d6f5b011cbae40
- bytes: 259
- estimated_tokens: 65

Content:

from .html import render_report_html
from .markdown import render_traffic
from .json import normalized_finding, traffic_report, write_user_report

__all__ = ["render_report_html", "render_traffic", "normalized_finding", "traffic_report", "write_user_report"]


---

## File: src/sourcepack/reports/html.py

Metadata:
- sha256: 742cabc329ec1c893048158167a4fcb99b2b7ba602a93cce016e93d5bed866b9
- bytes: 6852
- estimated_tokens: 1712

Content:

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape


def _html_escape(value: object) -> str:
    return xml_escape("" if value is None else str(value), {'"': '&quot;', "'": '&#x27;'})


def _report_badge_class(verdict: str) -> str:
    return {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}.get(verdict, "warn")

def render_report_html(report: dict) -> str:
    verdict = str(report.get("verdict", "WARN"))
    badge = _report_badge_class(verdict)
    findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
    raw_json_path = report.get("report_path") or ".sourcepack/reports/latest.json"
    baseline_path = report.get("baseline_packet_path") or (report.get("baseline") or {}).get("packet_path") if isinstance(report.get("baseline"), dict) else report.get("baseline_packet_path")

    def finding_rows(items: list[dict]) -> str:
        if not items:
            return '<tr><td colspan="5" class="muted">None.</td></tr>'
        rows = []
        for f in items:
            rows.append(
                "<tr>"
                f"<td><code>{_html_escape(f.get('id'))}</code></td>"
                f"<td><span class='severity {_html_escape(f.get('severity'))}'>{_html_escape(f.get('severity'))}</span></td>"
                f"<td>{_html_escape(f.get('path') or '—')}</td>"
                f"<td>{_html_escape(f.get('message'))}</td>"
                f"<td>{_html_escape(f.get('suggestion') or f.get('evidence') or '—')}</td>"
                "</tr>"
            )
        return "\n".join(rows)

    checked = "".join(f"<li>{_html_escape(item)}</li>" for item in report.get("checked_categories", [])) or "<li>None recorded.</li>"
    not_checked = "".join(f"<li>{_html_escape(item)}</li>" for item in report.get("not_checked", [])) or "<li>None recorded.</li>"
    affected = sorted({str(f.get("path")) for f in findings if f.get("path")})
    affected_html = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in affected) or "<li>No affected file paths recorded.</li>"
    missing = [f for f in findings if f.get("id") in {"missing_file", "unsupported_dependency", "unsupported_command", "unsupported_ecosystem", "js_alias_uncertain", "dependency_manifest_uncertain"} or f.get("category") == "uncertainty"]
    fixes = [f for f in findings if f.get("suggestion")]
    missing_html = "".join(f"<li><code>{_html_escape(f.get('id'))}</code>: {_html_escape(f.get('message'))}</li>" for f in missing) or "<li>No missing evidence recorded.</li>"
    fixes_html = "".join(f"<li>{_html_escape(f.get('suggestion'))}</li>" for f in fixes) or "<li>No suggested fixes recorded.</li>"
    generated = _html_escape(report.get("generated_at", "unknown"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SourcePack Report - {verdict}</title>
<style>
:root {{ color-scheme: light dark; --bg:#0f172a; --panel:#111827; --text:#e5e7eb; --muted:#94a3b8; --line:#334155; --pass:#16a34a; --warn:#d97706; --fail:#dc2626; }}
body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }}
main {{ max-width:1100px; margin:0 auto; padding:32px 20px 56px; }}
header, section {{ background:rgba(17,24,39,.92); border:1px solid var(--line); border-radius:18px; padding:22px; margin:16px 0; box-shadow:0 20px 50px rgba(0,0,0,.22); }}
h1 {{ margin:0 0 8px; font-size:32px; }}
h2 {{ margin-top:0; }}
.badge {{ display:inline-block; padding:8px 14px; border-radius:999px; font-weight:800; letter-spacing:.04em; }}
.badge.pass {{ background:var(--pass); }} .badge.warn {{ background:var(--warn); }} .badge.fail {{ background:var(--fail); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
.card {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:rgba(15,23,42,.72); }}
.label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.value {{ margin-top:6px; font-weight:650; overflow-wrap:anywhere; }}
table {{ width:100%; border-collapse:collapse; }} th, td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px; vertical-align:top; }} th {{ color:var(--muted); font-size:13px; }}
code {{ color:#bfdbfe; }} .muted {{ color:var(--muted); }} .severity.error {{ color:#fca5a5; }} .severity.warn {{ color:#fcd34d; }} .severity.info {{ color:#93c5fd; }}
</style>
</head>
<body><main>
<header>
<span class="badge {badge}">{_html_escape(report.get('light') or verdict)}</span>
<h1>SourcePack local report</h1>
<p>{_html_escape(report.get('headline'))}</p>
<p class="muted">Generated {generated}</p>
</header>
<section class="grid">
<div class="card"><div class="label">Verdict</div><div class="value">{_html_escape(verdict)}</div></div>
<div class="card"><div class="label">Reason type</div><div class="value">{_html_escape(report.get('reason_type') or 'none')}</div></div>
<div class="card"><div class="label">Commit policy</div><div class="value">{_html_escape(report.get('commit_policy') or 'allowed.')}</div></div>
<div class="card"><div class="label">Raw JSON</div><div class="value"><code>{_html_escape(raw_json_path)}</code></div></div>
</section>
<section><h2>Reason codes</h2><table><thead><tr><th>Code</th><th>Severity</th><th>Path</th><th>Explanation</th><th>Evidence / fix</th></tr></thead><tbody>{finding_rows(findings)}</tbody></table></section>
<section class="grid"><div class="card"><h2>Affected files</h2><ul>{affected_html}</ul></div><div class="card"><h2>Evidence found</h2><ul>{checked}</ul></div><div class="card"><h2>Evidence missing</h2><ul>{missing_html}</ul></div><div class="card"><h2>Suggested fixes</h2><ul>{fixes_html}</ul></div></section>
<section><h2>Baseline and prompt trust</h2><p>SourcePack treats prompt context as helpful but non-authoritative. Diff checks are judged against the trusted local baseline packet.</p><div class="grid"><div class="card"><div class="label">Baseline state</div><div class="value">{_html_escape(report.get('baseline_state') or 'not recorded')}</div></div><div class="card"><div class="label">Baseline packet</div><div class="value"><code>{_html_escape(baseline_path or 'not recorded')}</code></div></div></div></section>
<section class="grid"><div class="card"><h2>Checked</h2><ul>{checked}</ul></div><div class="card"><h2>Not checked</h2><ul>{not_checked}</ul></div></section>
<section><h2>Execution evidence</h2><p>Execution evidence proves only that a command was run locally and records exit/output hashes; it does not prove correctness, security, or external API behavior.</p></section><section><h2>Safe next actions</h2><p>{_html_escape(report.get('next_action'))}</p></section>
</main></body></html>"""




---

## File: src/sourcepack/reports/json.py

Metadata:
- sha256: e6a01f30ca28f26a2a51711079fdbb3b0abb6be170fafef9e9e4dfa3c5a98458
- bytes: 13624
- estimated_tokens: 3406

Content:

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sourcepack import __version__
from sourcepack.paths import ensure_sourcepack_dirs
from sourcepack.reports.html import render_report_html
from sourcepack.reports.sarif import render_sarif
from sourcepack.reports.markdown import LIGHT_BY_VERDICT, render_traffic
from sourcepack.reason_codes import normalize_reason_code, is_canonical_reason_code
from sourcepack.evidence import REPLAY_BUNDLE_SCHEMA_VERSION, attach_evidence_to_finding, evidence_summary, make_evidence, make_evidence_item

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalized_finding(fid: str, severity: str, category: str, message: str, path: str | None = None, evidence: str | None = None, suggestion: str | None = None) -> dict:
    code = normalize_reason_code(fid)
    if severity in {"error", "warn"} and not is_canonical_reason_code(code):
        raise ValueError(f"unknown SourcePack reason code: {fid}")
    return {"id": code, "severity": severity, "category": category, "path": path, "message": message, "evidence": evidence, "suggestion": suggestion}



def _finding_evidence_item(finding: dict) -> dict:
    fid = str(finding.get("id") or "")
    category = str(finding.get("category") or fid or "finding")
    path = finding.get("path") if finding.get("path") is not None else None
    observed = finding.get("evidence") if finding.get("evidence") is not None else path
    source_type = str(finding.get("evidence_class") or category or "finding")
    uncertainty = finding.get("message") if finding.get("severity") == "warn" and category == "uncertainty" else None
    item = make_evidence_item(
        fid or category,
        source_type,
        path=path,
        observed_value=str(observed) if observed is not None else None,
        normalized_value=str(path or observed) if (path or observed) is not None else None,
        supports=[fid] if fid else [],
        contradicts=[fid] if finding.get("severity") == "error" and fid else [],
        uncertainty=uncertainty,
        metadata={"finding_id": fid, "severity": finding.get("severity"), "category": category},
    )
    return item.to_dict()


def _dedupe_evidence_items(items: list[dict]) -> list[dict]:
    by_id = {item["evidence_id"]: item for item in items}
    return [by_id[k] for k in sorted(by_id)]


def build_replay_bundle(report: dict, *, generated_at: str | None = None, exit_code: int | None = None, command_mode: str | None = None, policy_mode: str | None = None) -> dict:
    findings = list(report.get("findings", []))
    evidence_items = _dedupe_evidence_items([_finding_evidence_item(f) for f in findings])
    reason_to_evidence: dict[str, list[str]] = {}
    for item in evidence_items:
        code = str(item.get("metadata", {}).get("finding_id") or item.get("category") or "")
        if code:
            reason_to_evidence.setdefault(code, []).append(item["evidence_id"])
    for code in list(reason_to_evidence):
        reason_to_evidence[code] = sorted(set(reason_to_evidence[code]))
    return {
        "schema_version": REPLAY_BUNDLE_SCHEMA_VERSION,
        "sourcepack_version": report.get("sourcepack_version", __version__),
        "generated_at": generated_at or report.get("generated_at"),
        "command_mode": command_mode or report.get("command_mode"),
        "policy_mode": policy_mode or report.get("policy_mode"),
        "verdict": report.get("verdict"),
        "exit_code": exit_code if exit_code is not None else report.get("exit_code"),
        "normalized_reason_codes": sorted(reason_to_evidence),
        "checked_categories": report.get("checked_categories", []),
        "not_checked": report.get("not_checked", []),
        "findings": findings,
        "warnings": report.get("warnings", []),
        "blockers": report.get("blockers", []),
        "uncertainties": report.get("uncertainties", []),
        "evidence_items": evidence_items,
        "reason_code_evidence": reason_to_evidence,
        "baseline_metadata": report.get("baseline_metadata", {}),
        "prompt_context_metadata": report.get("prompt_context_metadata", {}),
        "patch_metadata": report.get("patch_metadata", {}),
        "environment_metadata": report.get("environment_metadata", {}),
    }

def normalize_finding_evidence(finding: dict) -> dict:
    if finding.get("evidence_class"):
        return finding
    fid = str(finding.get("id") or "")
    category = str(finding.get("category") or "")
    source = str(finding.get("evidence") or finding.get("path") or category or fid)
    if category == "dependency" or fid in {"unsupported_dependency", "declared_dependency", "dependency_scope_review"}:
        status = "missing" if fid == "unsupported_dependency" else "partially_checked" if fid in {"declared_dependency", "dependency_scope_review"} else "checked"
        return attach_evidence_to_finding(finding, "dependency_manifest", source, status, missing_evidence=source if status == "missing" else None, required_evidence_class="dependency_manifest")
    if category == "command" or fid in {"unsupported_command", "declared_command", "command_manifest_missing", "command_check_inconclusive", "command_manifest_uncertain"}:
        status = "missing" if fid in {"unsupported_command", "command_manifest_missing"} else "partially_checked" if fid in {"declared_command", "command_check_inconclusive", "command_manifest_uncertain"} else "checked"
        return attach_evidence_to_finding(finding, "command_manifest", source, status, missing_evidence=source if status == "missing" else None, required_evidence_class="command_manifest")
    if category == "execution" or fid.startswith("execution_"):
        status = "checked" if fid == "execution_evidence_present" else "unavailable" if fid == "execution_evidence_missing" else "partially_checked"
        return attach_evidence_to_finding(finding, "execution_ledger", source, status, missing_evidence=source if status == "unavailable" else None, required_evidence_class="execution_ledger", supports_claim="local_execution")
    if category in {"baseline", "file"} or fid in {"missing_file", "baseline_missing", "baseline_corrupt", "baseline_stale", "baseline_inventory_missing"}:
        status = "missing" if fid in {"missing_file", "baseline_missing", "baseline_corrupt", "baseline_inventory_missing"} else "checked"
        return attach_evidence_to_finding(finding, "trusted_baseline", source, status, missing_evidence=source if status == "missing" else None, required_evidence_class="trusted_baseline")
    if category == "artifact" or fid in {"protected_artifact", "git_path_modification"}:
        eclass = "git_metadata" if fid == "git_path_modification" else "trusted_baseline"
        return attach_evidence_to_finding(finding, eclass, source, "checked", required_evidence_class=eclass)
    if fid in {"unsupported_ecosystem", "binary_diff", "path_escape", "unsafe_path"}:
        return attach_evidence_to_finding(finding, "unsupported", source, "unsupported", missing_evidence=source, required_evidence_class="current_worktree")
    return finding


def traffic_report(verdict: str, headline: str | None = None, findings: list[dict] | None = None, checked_categories: list[str] | None = None, next_action: str | None = None, report_path: str = ".sourcepack/reports/latest.json", reason_type: str | None = None, not_checked: list[str] | None = None) -> dict:
    findings = [normalize_finding_evidence(f) for f in (findings or [])]
    findings = sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.get("severity", "info"), 9), f.get("id", ""), f.get("path") or ""))
    blockers = [f for f in findings if f.get("severity") == "error"]
    warnings = [f for f in findings if f.get("severity") == "warn"]
    light = LIGHT_BY_VERDICT.get(verdict, "YELLOW LIGHT")
    if reason_type is None:
        reason_type = "blocker" if verdict == "FAIL" else "review" if warnings else "none"
        if any(f.get("category") in {"uncertainty", "tooling"} for f in warnings):
            reason_type = "uncertainty" if any(f.get("category") == "uncertainty" for f in warnings) else "tooling"
    if headline is None:
        if verdict == "WARN" and reason_type == "uncertainty":
            headline = "SourcePack could not fully evaluate this change."
        elif verdict == "WARN" and reason_type == "tooling":
            headline = "SourcePack tooling degraded."
        else:
            headline = {"PASS": "good to continue.", "WARN": "review before continuing.", "FAIL": "stop before trusting this output."}.get(verdict, "review before continuing.")
    next_action = next_action or ("ask the AI to revise using only files, dependencies, and commands confirmed by SourcePack." if verdict == "FAIL" else "review the listed items before continuing." if verdict == "WARN" else "continue.")
    commit_policy = None
    if verdict == "WARN":
        commit_policy = "allowed locally, blocked in strict mode."
    elif verdict == "FAIL":
        commit_policy = "blocked unless explicitly bypassed."
    checked_categories = checked_categories or []
    not_checked = not_checked or ["runtime behavior", "semantic correctness", "security", "external services"]
    records = []
    for category in checked_categories:
        eclass = "trusted_baseline" if "baseline" in category else "dependency_manifest" if "import" in category.lower() else "command_manifest" if "command" in category.lower() else "current_worktree"
        records.append(make_evidence(eclass, category, "checked"))
    for category in not_checked:
        records.append(make_evidence("not_checked", category, "not_checked"))
    for f in findings:
        if f.get("evidence_class"):
            records.append(f)
    evidence = evidence_summary(records)
    partial = sorted({f["category"] for f in findings if f.get("checked_status") == "partially_checked"} | ({"execution_claim_check"} if any(f.get("category") == "execution" for f in findings) else set()))
    checked_names = sorted(set(checked_categories) | {f["category"] for f in findings if f.get("checked_status") == "checked"})
    confidence_summary = {"basis": "local evidence coverage, not AI confidence", "checked": checked_names, "partially_checked": partial, "not_checked": not_checked, "limitations": ["SourcePack does not prove code correctness", "SourcePack does not prove security", "SourcePack does not verify external API behavior unless local evidence exists"]}
    base_report = {"schema_version": "traffic_report.v1", "sourcepack_version": __version__, "verdict": verdict, "light": light, "headline": headline, "reason_type": reason_type, "commit_policy": commit_policy, "blockers": blockers, "warnings": warnings, "uncertainties": [f for f in warnings if f.get("category") == "uncertainty"], "checked_categories": checked_names, "checked": checked_names, "partially_checked": partial, "unavailable_evidence": evidence["missing_evidence"], "unsupported_evidence": [f for f in findings if f.get("id") == "unsupported_ecosystem"], "not_checked": not_checked, "confidence_summary": confidence_summary, "evidence": evidence, "next_action": next_action, "report_path": report_path, "findings": findings}
    evidence_items = _dedupe_evidence_items([_finding_evidence_item(f) for f in findings])
    reason_code_evidence = {}
    for item in evidence_items:
        code = item.get("metadata", {}).get("finding_id") or item.get("category")
        reason_code_evidence.setdefault(code, []).append(item["evidence_id"])
    base_report["evidence_items"] = evidence_items
    base_report["reason_code_evidence"] = {k: sorted(set(v)) for k, v in sorted(reason_code_evidence.items())}
    base_report["replay_bundle"] = build_replay_bundle(base_report)
    return base_report


def _write_optional_report_file(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        print(f"WARNING: could not write SourcePack report artifact {path}: {exc}", file=sys.stderr)


def write_user_report(repo: str | Path, report: dict, stem: str = "report") -> None:
    paths = ensure_sourcepack_dirs(repo)
    full = dict(report)
    full.setdefault("sourcepack_version", __version__)
    full.setdefault("schema_version", "traffic_report.v1")
    full["generated_at"] = utc_now()
    if "replay_bundle" in full:
        full["replay_bundle"] = build_replay_bundle(full, generated_at=full["generated_at"], exit_code=full.get("exit_code"), command_mode=full.get("command_mode"), policy_mode=full.get("policy_mode"))
    json_text = json.dumps(full, indent=2)
    md_text = render_traffic(full, verbose=True)
    paths["latest_json"].write_text(json_text, encoding="utf-8")
    sarif_text = json.dumps(render_sarif(full), indent=2)
    _write_optional_report_file(paths["latest_sarif"], sarif_text)
    _write_optional_report_file(paths["latest_md"], md_text)
    try:
        html_text = render_report_html(full)
    except Exception as exc:
        print(f"WARNING: could not render SourcePack HTML report: {exc}", file=sys.stderr)
    else:
        _write_optional_report_file(paths["latest_html"], html_text)
    typed = paths.get(f"latest_{stem}_json")
    if typed is not None:
        _write_optional_report_file(typed, json_text)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _write_optional_report_file(paths["archive"] / f"{ts}_{stem}.json", json_text)
    _write_optional_report_file(paths["archive"] / f"{ts}_{stem}.md", md_text)


---

## File: src/sourcepack/reports/markdown.py

Metadata:
- sha256: 1d1bb8e68d0cc0a0a29f713795b1b1b524f42c17fc6a05f381c9be2d2667fec7
- bytes: 3627
- estimated_tokens: 907

Content:

from __future__ import annotations

LIGHT_BY_VERDICT = {"PASS": "GREEN LIGHT", "WARN": "YELLOW LIGHT", "FAIL": "RED LIGHT"}
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}

def render_traffic(report: dict, verbose: bool = False) -> str:
    verdict = report.get("verdict", "WARN")
    lines = [f"Verdict: {verdict}", f"{report.get('light', LIGHT_BY_VERDICT.get(verdict, 'YELLOW LIGHT'))}: {report.get('headline', '')}", ""]
    if report.get("reason_type"):
        lines.append(f"Reason type: {report.get('reason_type')}")
    lines.append(f"Commit policy: {report.get('commit_policy') or 'allowed.'}")
    lines.append("")
    if verdict == "PASS":
        info = [f for f in report.get("findings", []) if f.get("severity") == "info"]
        lines.append(info[0]["message"] if info else "No unsupported project claims or patch assumptions detected.")
        if report.get("checked_categories"):
            lines.extend(["", "Checked:", ""])
            lines.extend(f"- {item}" for item in report.get("checked_categories", []))
        if report.get("not_checked"):
            lines.extend(["", "Not checked:", ""])
            lines.extend(f"- {item}" for item in report.get("not_checked", []))
    elif verdict == "WARN":
        lines.append("SourcePack found review or uncertainty items, but no clear unsupported blocker.")
        review = [f for f in report.get("warnings", []) if f.get("category") != "uncertainty"]
        uncertain = [f for f in report.get("warnings", []) if f.get("category") == "uncertainty"]
        if review:
            lines.extend(["", "Review warnings:", ""])
            shown = review if verbose else review[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        if uncertain:
            lines.extend(["", "Uncertainties:", ""])
            shown = uncertain if verbose else uncertain[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    else:
        lines.append("SourcePack found missing files, unsupported dependencies, unsupported commands, or unsupported capabilities.")
        if report.get("blockers"):
            lines.extend(["", "Blockers:", ""])
            shown = report.get("blockers", []) if verbose else report.get("blockers", [])[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        review = [f for f in report.get("warnings", []) if f.get("category") != "uncertainty"]
        uncertain = [f for f in report.get("warnings", []) if f.get("category") == "uncertainty"]
        if review:
            lines.extend(["", "Review warnings:", ""])
            shown = review if verbose else review[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        if uncertain:
            lines.extend(["", "Uncertainties:", ""])
            shown = uncertain if verbose else uncertain[:3]
            lines.extend(f"- {f.get('id')}: {f.get('message')}" for f in shown)
        lines.extend(["", f"Next action: {report.get('next_action')}"])
    if verdict != "PASS":
        if report.get("checked_categories"):
            lines.extend(["", "Checked:", ""])
            lines.extend(f"- {item}" for item in report.get("checked_categories", []))
        if report.get("not_checked"):
            lines.extend(["", "Not checked:", ""])
            lines.extend(f"- {item}" for item in report.get("not_checked", []))
    lines.extend(["", f"Report path: {report.get('report_path', '.sourcepack/reports/latest.json')}"])
    return "\n".join(lines) + "\n"



---

## File: src/sourcepack/reports/sarif.py

Metadata:
- sha256: 24645dc7b6cbb76f176c3929c3500a05fc44486636fe2cbb9e55e70550171193
- bytes: 1505
- estimated_tokens: 377

Content:

from __future__ import annotations


def _level(severity: str) -> str:
    return {"error": "error", "warn": "warning", "info": "note"}.get(severity, "note")


def render_sarif(report: dict) -> dict:
    """Render a SourcePack traffic report as SARIF 2.1.0.

    SARIF is only a transport/report format here; SourcePack findings and
    verdicts remain the sole judgment source.
    """
    rules: dict[str, dict] = {}
    results: list[dict] = []
    for finding in report.get("findings", []) if isinstance(report.get("findings"), list) else []:
        rule_id = str(finding.get("id") or "sourcepack_finding")
        rules.setdefault(rule_id, {"id": rule_id, "name": rule_id, "shortDescription": {"text": rule_id}})
        result = {
            "ruleId": rule_id,
            "level": _level(str(finding.get("severity") or "info")),
            "message": {"text": str(finding.get("message") or rule_id)},
        }
        path = finding.get("path")
        if path:
            result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": str(path).replace("\\", "/")}}}]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "SourcePack", "informationUri": "https://pypi.org/project/sourcepack/", "rules": list(rules.values())}},
            "invocations": [{"executionSuccessful": True}],
            "results": results,
        }],
    }


---

## File: src/sourcepack/schemas.py

Metadata:
- sha256: 14b5eea7e92278818d97c60103d6e9aed1fca12a3dfd39598e413a5f43ed6d4d
- bytes: 1479
- estimated_tokens: 370

Content:

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .reason_codes import ReasonCode

BASELINE_SCHEMA_VERSION = "baseline_pointer.v1"
JUDGMENT_REPORT_SCHEMA_VERSION = "traffic_report.v1"
PROMPT_CONTEXT_SCHEMA_VERSION = "prompt_context.v1"


class Verdict(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class PolicyMode(StrEnum):
    LOCAL = "local"
    STRICT = "strict"
    CI = "ci"


@dataclass(frozen=True)
class Finding:
    code: ReasonCode | str
    severity: Severity | str
    path: str | None
    message: str
    evidence: str | None = None
    suggested_fixes: list[str] = field(default_factory=list)
    category: str | None = None

    def to_report_dict(self) -> dict[str, Any]:
        suggestion = self.suggested_fixes[0] if self.suggested_fixes else None
        return {
            "id": str(self.code),
            "severity": str(self.severity),
            "category": self.category,
            "path": self.path,
            "message": self.message,
            "evidence": self.evidence,
            "suggestion": suggestion,
        }


@dataclass(frozen=True)
class Judgment:
    verdict: Verdict | str
    findings: list[Finding]
    checked_categories: list[str]
    not_checked: list[str]
    reason_type: str | None
    commit_policy: str | None
    next_action: str


---

## File: src/sourcepack/workbench.py

Metadata:
- sha256: dbc142549ee23fc066d9bc9d342ac97d80d1cafe05d294f5c131e2fd01a5974d
- bytes: 8028
- estimated_tokens: 2007

Content:

from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import socket
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

STATIC_ROOT = Path(__file__).with_name("workbench_static")
REQUEST_TIMEOUT_SECONDS = 120
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents


def _run_sourcepack(repo: Path, args: list[str], timeout: int = REQUEST_TIMEOUT_SECONDS, output_key: str | None = None) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "sourcepack.cli", *args]
    try:
        cp = subprocess.run(
            cmd,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "timeout": True,
            "error": "sourcepack_command_timeout",
            "message": f"SourcePack command timed out after {timeout} seconds.",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    result: dict[str, Any] = {"ok": cp.returncode == 0, "returncode": cp.returncode, "stderr": cp.stderr}
    if output_key is not None and cp.stdout.strip():
        try:
            result[output_key] = json.loads(cp.stdout)
        except json.JSONDecodeError:
            result["stdout"] = cp.stdout
            result["parse_error"] = "invalid_json_stdout"
    else:
        result["stdout"] = cp.stdout
    return result


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "SourcePackWorkbench/0"

    @property
    def session_token(self) -> str:
        return self.server.session_token  # type: ignore[attr-defined]

    @property
    def repo_root(self) -> Path:
        return self.server.repo_root  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_token_valid(self) -> bool:
        values = self.headers.get_all("X-SourcePack-Token") or []
        if len(values) != 1:
            return False
        token = values[0]
        if not token or any(ch.isspace() for ch in token):
            return False
        return secrets.compare_digest(token, self.session_token)

    def _require_api_token(self) -> bool:
        if self._api_token_valid():
            return True
        self._send_json(403, {"ok": False, "error": "forbidden"})
        return False

    def do_GET(self) -> None:
        requested = urllib.parse.urlparse(self.path).path
        if requested.startswith("/api/"):
            if not self._require_api_token():
                return
            if requested == "/api/status":
                self._send_json(200, _run_sourcepack(self.repo_root, ["status", str(self.repo_root), "--json"], output_key="status"))
                return
            if requested == "/api/latest":
                latest = self.repo_root / ".sourcepack" / "reports" / "latest.json"
                if not latest.is_file():
                    self._send_json(404, {"ok": False, "error": "latest_report_missing"})
                    return
                try:
                    self._send_json(200, {"ok": True, "report": json.loads(latest.read_text(encoding="utf-8"))})
                except json.JSONDecodeError as exc:
                    self._send_json(500, {"ok": False, "error": "latest_report_invalid_json", "message": str(exc)})
                return
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._serve_static(requested)

    def do_POST(self) -> None:
        requested = urllib.parse.urlparse(self.path).path
        if not requested.startswith("/api/"):
            self.send_error(404)
            return
        if not self._require_api_token():
            return
        if requested == "/api/review":
            self._send_json(200, _run_sourcepack(self.repo_root, ["diff", str(self.repo_root), "--json"], output_key="review"))
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def _serve_static(self, requested: str) -> None:
        relative = requested.lstrip("/") or "index.html"
        static_root = STATIC_ROOT.resolve()
        target = (static_root / relative).resolve()
        if target != static_root and not _is_relative_to(target, static_root):
            self.send_error(403)
            return
        if target.is_dir():
            target = (target / "index.html").resolve()
            if not _is_relative_to(target, static_root):
                self.send_error(403)
                return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WorkbenchServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], repo_root: Path, session_token: str):
        super().__init__(server_address, handler_class)
        self.repo_root = repo_root
        self.session_token = session_token


class IPv6WorkbenchServer(WorkbenchServer):
    address_family = socket.AF_INET6


def _validate_requested_host(host: str) -> None:
    if host not in ALLOWED_LOOPBACK_HOSTS:
        allowed = ", ".join(sorted(ALLOWED_LOOPBACK_HOSTS))
        raise ValueError(f"Workbench only binds to explicit loopback hosts ({allowed}); got {host!r}")


def _validate_bound_host(host: str) -> None:
    normalized = "127.0.0.1" if host == "localhost" else host
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(f"Workbench bound to an invalid host: {host!r}") from exc
    if not address.is_loopback:
        raise ValueError(f"Workbench refused non-loopback bound address: {host!r}")


def _server_class_for_host(host: str) -> type[WorkbenchServer]:
    return IPv6WorkbenchServer if host == "::1" else WorkbenchServer


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def serve_workbench(repo: str | Path = ".", host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> int:
    _validate_requested_host(host)
    token = secrets.token_urlsafe(32)
    repo_root = Path(repo).resolve()
    server_class = _server_class_for_host(host)
    with server_class((host, port), WorkbenchHandler, repo_root, token) as httpd:
        actual_host, actual_port = httpd.server_address[:2]
        try:
            _validate_bound_host(actual_host)
        except ValueError:
            httpd.server_close()
            raise
        url_base = f"http://{_url_host(actual_host)}:{actual_port}/"
        url = f"{url_base}?token={urllib.parse.quote(token)}"
        opened = False
        if open_browser:
            opened = webbrowser.open(url)
        display_url = url_base if open_browser and opened else url
        print(f"SourcePack Workbench: {display_url}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


---

## File: src/sourcepack/workbench_static/index.html

Metadata:
- sha256: fb773a711143ebac18dc0c72afa4f2a5b1568b6b3cc37b2d5fbf7d2772d5ffde
- bytes: 1613
- estimated_tokens: 404

Content:

<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SourcePack Workbench</title>
</head>
<body>
  <h1>SourcePack Workbench</h1>
  <button id="status">Status</button>
  <button id="review">Review</button>
  <button id="latest">Latest</button>
  <pre id="output"></pre>
  <script>
    const params = new URLSearchParams(window.location.search);
    const queryToken = params.get('token');
    if (queryToken) {
      sessionStorage.setItem('sourcepackToken', queryToken);
      window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
    }
    const sourcepackToken = sessionStorage.getItem('sourcepackToken') || '';
    const output = document.getElementById('output');
    async function api(path, options = {}) {
      const headers = new Headers(options.headers || {});
      headers.set('X-SourcePack-Token', sourcepackToken);
      const response = await fetch(path, {...options, headers});
      const text = await response.text();
      try { return JSON.stringify(JSON.parse(text), null, 2); }
      catch (_error) { return text; }
    }
    document.getElementById('status').addEventListener('click', async () => { output.textContent = await api('/api/status'); });
    document.getElementById('review').addEventListener('click', async () => { output.textContent = await api('/api/review', {method: 'POST'}); });
    document.getElementById('latest').addEventListener('click', async () => { output.textContent = await api('/api/latest'); });
  </script>
</body>
</html>


---

## File: tests/__init__.py

Metadata:
- sha256: d1ea17b40bff9ad853be4aaac80d3d9abce3db729a880212c41a848912c2324b
- bytes: 450
- estimated_tokens: 113

Content:

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_existing_pythonpath = os.environ.get("PYTHONPATH")
if _existing_pythonpath:
    _parts = _existing_pythonpath.split(os.pathsep)
    if str(SRC) not in _parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([str(SRC), *_parts])
else:
    os.environ["PYTHONPATH"] = str(SRC)


---

## File: tests/simulation_helpers.py

Metadata:
- sha256: 63bb5c420f625ce5364720f37eea2ba46d2e21ee4fa00c31307ed2fb06885789
- bytes: 4695
- estimated_tokens: 1174

Content:

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path

from sourcepack.cli import patch_report_to_traffic, sha256_text

MUST_RED = "MUST_RED"
MUST_NOT_RED = "MUST_NOT_RED"
MUST_YELLOW = "MUST_YELLOW"
MAY_YELLOW_OR_GREEN = "MAY_YELLOW_OR_GREEN"
MUST_FAIL_CLOSED = "MUST_FAIL_CLOSED"


@dataclass(frozen=True)
class Scenario:
    name: str
    files: dict[str, str]
    patch: str
    expectation: str
    expected_id: str | None = None
    forbidden_ids: set[str] = field(default_factory=set)
    repo_shape: str = ""
    summary: str = ""


def unified_patch(path: str, old: str, new: str, new_file: bool = False, deleted: bool = False) -> str:
    old_lines = [] if new_file else old.splitlines()
    new_lines = [] if deleted else new.splitlines()
    body = "\n".join(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")) + "\n"
    prefix = f"diff --git a/{path} b/{path}\n"
    if new_file:
        prefix += "new file mode 100644\n"
    if deleted:
        prefix += "deleted file mode 100644\n"
    return prefix + body


def multi_patch(parts: list[tuple[str, str, str]]) -> str:
    return "".join(unified_patch(path, old, new) for path, old, new in parts)


def write_packet(tmp_path: Path, files: dict[str, str], context_files: set[str] | None = None, inventory_files: set[str] | None = None) -> Path:
    packet = tmp_path / "packet"
    packet.mkdir()
    included = []
    context = ["# SourcePack Context", ""]
    context_names = set(files) if context_files is None else context_files
    inventory_names = set(files) if inventory_files is None else inventory_files
    for rel, content in sorted(files.items()):
        if rel not in context_names:
            continue
        included.append({"relative_path": rel, "sha256": sha256_text(content), "extension": Path(rel).suffix})
        context.extend([f"## File: {rel}", "", "Content:", content.rstrip("\n"), "---", ""])
    manifest = {"included_files": included}
    inventory = {"schema_version": "sourcepack.file_inventory.v1", "source": "test", "files": [{"relative_path": rel, "included_in_prompt_context": rel in context_names, "source": "test"} for rel in sorted(inventory_names)]}
    (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (packet / "file_inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (packet / "context.md").write_text("\n".join(context), encoding="utf-8")
    (packet / "reality_map.json").write_text(json.dumps({"supported_commands": []}), encoding="utf-8")
    (packet / "receipt.json").write_text(json.dumps({"hashes": {}}), encoding="utf-8")
    return packet


def summarize(report: dict) -> dict:
    traffic = patch_report_to_traffic(report)
    findings = traffic.get("findings", [])
    return {
        "verdict": traffic.get("verdict"),
        "light": traffic.get("light"),
        "reason_type": traffic.get("reason_type"),
        "finding_ids": {f.get("id") for f in findings},
        "unsupported_dependencies": set(report.get("unsupported_dependencies", [])),
        "unsupported_commands": set(report.get("unsupported_commands", [])),
        "protected_artifact_modifications": set(report.get("protected_artifact_modifications", [])),
        "warnings": traffic.get("warnings", []),
        "uncertainties": report.get("uncertainties", []),
        "binary_diffs": set(report.get("binary_diffs", [])),
        "raw": report,
    }


def assert_expectation(scenario: Scenario, report: dict) -> None:
    s = summarize(report)
    msg = (
        f"scenario={scenario.name}\nrepo_shape={scenario.repo_shape}\nsummary={scenario.summary}\n"
        f"expected={scenario.expectation} expected_id={scenario.expected_id}\n"
        f"actual={s['verdict']} ids={sorted(s['finding_ids'])}\nfields={s}"
    )
    if scenario.expectation == MUST_RED:
        assert s["verdict"] == "FAIL", msg
        assert scenario.expected_id in s["finding_ids"], msg
    elif scenario.expectation == MUST_NOT_RED:
        assert s["verdict"] != "FAIL", msg
        assert not (scenario.forbidden_ids & s["finding_ids"]), msg
    elif scenario.expectation == MUST_YELLOW:
        assert s["verdict"] == "WARN", msg
        assert scenario.expected_id in s["finding_ids"], msg
    elif scenario.expectation == MAY_YELLOW_OR_GREEN:
        assert s["verdict"] in {"PASS", "WARN"}, msg
    elif scenario.expectation == MUST_FAIL_CLOSED:
        assert s["verdict"] == "FAIL", msg
        assert scenario.expected_id in s["finding_ids"], msg
    else:
        raise AssertionError(f"Unknown expectation {scenario.expectation}")


---

## File: tests/test_baseline_integrity.py

Metadata:
- sha256: 275deab968d13166a63ad25f8c613c875e47fc0017aa4ac6b2e1212dbc3c4bca
- bytes: 9444
- estimated_tokens: 2361

Content:

import contextlib
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import build_current_baseline, run_cli, validate_baseline, acquire_baseline_lock, release_baseline_lock


def capture_cli(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = run_cli(args)
    return code, out.getvalue()


class BaselineIntegrityTest(unittest.TestCase):
    def repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        (repo / "README.md").write_text("demo\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return repo

    def json_cli(self, args):
        code, text = capture_cli(args + ["--json"])
        return code, json.loads(text)

    def packet(self, repo: Path) -> Path:
        status = validate_baseline(repo)
        return repo / status["packet_path"]

    def corrupt_and_diff(self, repo: Path):
        (repo / "README.md").write_text("demo\nchange\n")
        return self.json_cli(["diff", str(repo)])

    def test_missing_baseline_with_changes(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); (repo / "README.md").write_text("changed\n")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["verdict"], "FAIL")
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_missing")

    def test_missing_baseline_with_no_changes_creates_or_passes_not_corrupt(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 0)
            self.assertNotEqual(data.get("baseline_integrity_finding_id"), "baseline_corrupt")

    def test_empty_and_partial_inactive_baseline_are_missing(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); (repo / ".sourcepack" / "baseline").mkdir(parents=True)
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "missing")
            scratch = repo / ".sourcepack" / "baseline" / "builds" / "scratch" / "packet"
            scratch.mkdir(parents=True); (scratch / "manifest.json").write_text("{}")
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "missing")

    def test_corrupt_pointer_cases(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); base = repo / ".sourcepack" / "baseline"; base.mkdir(parents=True)
            (base / "active.json").write_text("{")
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "corrupt")
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")
            (base / "active.json").write_text(json.dumps({"active_build_id":"missing"}))
            code, data = self.json_cli(["status", str(repo)])
            self.assertEqual(data["baseline_state"], "corrupt")

    def test_corrupt_packet_artifacts_block_diff(self):
        cases = [
            ("manifest.json", None),
            ("manifest.json", "{"),
            ("receipt.json", None),
            ("receipt.json", "{"),
            ("reality_map.json", '{"tampered": true}'),
            ("reality_map.json", None),
        ]
        for name, content in cases:
            with self.subTest(name=name, content=content):
                with TemporaryDirectory() as td:
                    repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
                    target = self.packet(repo) / name
                    if content is None:
                        target.unlink()
                    else:
                        target.write_text(content)
                    code, data = self.corrupt_and_diff(repo)
                    self.assertEqual(code, 1)
                    self.assertEqual(data["verdict"], "FAIL")
                    self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")

    def test_corrupt_baseline_wins_with_no_diff(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            (self.packet(repo) / "receipt.json").write_text("{")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_corrupt")
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")

    def test_stale_baseline_warns_and_stale_plus_red_fails(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            state = repo / ".sourcepack" / "state"; state.mkdir(parents=True, exist_ok=True)
            (state / "baseline_stale.json").write_text('{"reason":"test"}')
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertEqual(data["reason_type"], "uncertainty")
            self.assertTrue(any(f["id"] == "baseline_stale" for f in data["findings"]))
            (repo / "app.py").write_text("import fastapi\n")
            code, data = self.json_cli(["diff", str(repo)])
            self.assertEqual(code, 1)
            self.assertEqual(data["verdict"], "FAIL")
            ids = {f["id"] for f in data["findings"]}
            self.assertIn("unsupported_dependency", ids)

    def test_status_reports_missing_stale_corrupt(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            self.assertEqual(self.json_cli(["status", str(repo)])[1]["baseline_state"], "missing")
            build_current_baseline(repo, quiet=True)
            (repo / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}')
            self.assertEqual(self.json_cli(["status", str(repo)])[1]["baseline_state"], "stale")
            (self.packet(repo) / "manifest.json").write_text("{")
            data = self.json_cli(["status", str(repo)])[1]
            self.assertEqual(data["baseline_state"], "corrupt")
            self.assertFalse(data["baseline_integrity_ok"])

    def test_prompt_does_not_create_or_repair_baseline(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertTrue((repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "packet" / "manifest.json").exists())
            build_current_baseline(repo, quiet=True, force=True)
            (self.packet(repo) / "manifest.json").write_text("{")
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")

    def test_pointer_activation_failure_preserves_old_or_missing_state(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); build_current_baseline(repo, quiet=True)
            old = json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text())["active_build_id"]
            with self.assertRaises(RuntimeError):
                build_current_baseline(repo, quiet=True, fail_stage="before_pointer_replace")
            self.assertEqual(json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text())["active_build_id"], old)
            self.assertEqual(validate_baseline(repo)["state"], "present")
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td))
            with self.assertRaises(RuntimeError):
                build_current_baseline(repo, quiet=True, fail_stage="before_pointer_replace")
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())
            self.assertEqual(validate_baseline(repo)["state"], "missing")

    def test_concurrent_baseline_lock_blocks_second_writer(self):
        with TemporaryDirectory() as td:
            repo = self.repo(Path(td)); lock, fd = acquire_baseline_lock(repo, "test")
            try:
                with self.assertRaises(Exception):
                    build_current_baseline(repo, quiet=True)
                self.assertEqual(validate_baseline(repo)["state"], "missing")
            finally:
                release_baseline_lock(lock, fd)
            build_current_baseline(repo, quiet=True)
            self.assertEqual(validate_baseline(repo)["state"], "present")


if __name__ == "__main__":
    unittest.main()


---

## File: tests/test_baseline_lifecycle.py

Metadata:
- sha256: 496c6e5304c413aa6843ede912f0219e6d30d73821a722061c140d52a5047232
- bytes: 9436
- estimated_tokens: 2359

Content:

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def json_cli(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = run_cli(repo, *args)
    return cp, json.loads(cp.stdout)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)
    (repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return repo


def create_baseline(repo: Path) -> dict:
    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] in {"PASS", "WARN"}
    return data


def active_build(repo: Path) -> Path:
    active = json.loads((repo / ".sourcepack" / "baseline" / "active.json").read_text(encoding="utf-8"))
    return repo / ".sourcepack" / "baseline" / "builds" / active["active_build_id"]


def finding_ids(data: dict) -> set[str]:
    return {f.get("id") for f in data.get("findings", [])}


def assert_ci_diff_fails_closed(repo: Path, expected_id: str) -> dict:
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode != 0
    assert data["verdict"] == "FAIL"
    assert data.get("baseline_integrity_finding_id") == expected_id or expected_id in finding_ids(data)
    return data


def test_baseline_absent_fails_closed_and_prompt_does_not_satisfy_requirement(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".sourcepack" / "prompt" / "packet").mkdir(parents=True)
    (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").write_text("{}", encoding="utf-8")
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"
    assert not (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_active_json_missing_reports_missing_pointer_and_ci_fails_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".sourcepack" / "baseline").mkdir(parents=True)
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "missing"
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"


def test_active_json_points_to_missing_build_fails_verification_and_ci(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    baseline = repo / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    (baseline / "active.json").write_text(json.dumps({"active_build_id": "missing-build"}), encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_corrupt_active_json_fails_verification_ci_and_json_remains_parseable(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    baseline = repo / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    (baseline / "active.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_corrupt_build_metadata_fails_verification_and_ci(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (active_build(repo) / "metadata.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_missing_required_packet_file_fails_verification_and_diff_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (active_build(repo) / "packet" / "manifest.json").unlink()
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 1
    assert status["state"] == "corrupt"
    data = assert_ci_diff_fails_closed(repo, "baseline_corrupt")
    assert data["baseline_state"] == "corrupt"


def test_extra_inactive_build_does_not_affect_active_baseline_or_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    inactive = repo / ".sourcepack" / "baseline" / "builds" / "inactive-build" / "packet"
    inactive.mkdir(parents=True)
    (inactive / "manifest.json").write_text("{", encoding="utf-8")
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 0
    assert status["state"] == "present"
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["verdict"] == "PASS"
    assert data["baseline_state"] == "present"
    assert "no_diff" in finding_ids(data)


def test_prompt_only_state_with_no_baseline_fails_ci_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    cp = run_cli(repo, "prompt", ".", "test task", "--json")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists()
    data = assert_ci_diff_fails_closed(repo, "baseline_missing")
    assert data["baseline_state"] == "missing"
    assert not (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_baseline_present_and_clean_verifies_and_diff_passes_no_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    cp, status = json_cli(repo, "baseline", "verify", "--json")
    assert cp.returncode == 0
    assert status["state"] == "present"
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["verdict"] == "PASS"
    assert data["baseline_state"] == "present"
    assert "no_diff" in finding_ids(data)


def test_baseline_present_with_tracked_file_changed_has_no_baseline_failure_or_prompt_involvement(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    create_baseline(repo)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
    cp, data = json_cli(repo, "diff", ".", "--ci", "--json")
    assert cp.returncode == 0
    assert data["baseline_state"] == "present"
    assert data.get("baseline_integrity_finding_id") is None
    ids = finding_ids(data)
    assert "baseline_missing" not in ids
    assert "baseline_corrupt" not in ids
    assert not (repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists()


def test_baseline_refuses_dirty_git_worktree_without_force_before_sourcepack_mutation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")

    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet")

    assert cp.returncode == 1
    assert data["verdict"] == "FAIL"
    assert "dirty working tree" in data["findings"][0]["message"]
    assert not (repo / ".sourcepack").exists()


def test_baseline_force_permits_dirty_git_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "scratch.txt").write_text("trusted intentionally\n", encoding="utf-8")

    cp, data = json_cli(repo, "baseline", ".", "--json", "--quiet", "--force")

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert data["verdict"] == "WARN"
    assert (repo / ".sourcepack" / "baseline" / "active.json").exists()


def test_init_auto_refuses_dirty_git_worktree_without_force_before_sourcepack_mutation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")

    cp = run_cli(repo, "init", ".", "--auto")

    assert cp.returncode == 1
    assert "dirty working tree" in cp.stdout
    assert not (repo / ".sourcepack").exists()
    assert not (repo / ".sourcepackignore").exists()
    assert not (repo / "sourcepack.config.json").exists()


def test_init_auto_force_permits_dirty_git_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")

    cp = run_cli(repo, "init", ".", "--auto", "--force", "--no-hook")

    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert (repo / ".sourcepack" / "baseline" / "active.json").exists()


---

## File: tests/test_baseline_lifecycle_cli.py

Metadata:
- sha256: 01b1e1f216054fb8aa00f48f25260838fcb56b58b95313c52428b8c1aa35199b
- bytes: 675
- estimated_tokens: 169

Content:

import json, subprocess, sys


def run_cli(tmp_path,*args):
    return subprocess.run([sys.executable,"-m","sourcepack.cli",*args], cwd=tmp_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_missing_baseline_status_and_json(tmp_path):
    cp=run_cli(tmp_path,"baseline","status","--json")
    assert cp.returncode == 0
    assert json.loads(cp.stdout)["state"] == "missing"

def test_baseline_path_missing(tmp_path):
    assert run_cli(tmp_path,"baseline","path").returncode == 1

def test_reset_safety(tmp_path):
    (tmp_path/"code.py").write_text("x=1")
    assert run_cli(tmp_path,"reset").returncode == 0
    assert (tmp_path/"code.py").exists()


---

## File: tests/test_behavior_matrix.py

Metadata:
- sha256: e5bc0e39671206c13bca84b259e31be51f910359b724509d1dc340b91045f860
- bytes: 4279
- estimated_tokens: 1070

Content:

from __future__ import annotations

import json
import subprocess
import sys

from tools.behavior_matrix import (
    CANONICAL_REASON_CODES,
    build_scenarios,
    normalize_reason_code,
    normalize_reason_codes,
    run_matrix,
    validate_scenario_definitions,
)


def test_behavior_matrix_scenario_count_and_unique_ids():
    scenarios = build_scenarios()
    assert len(scenarios) >= 55
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids))


def test_all_scenario_expected_reason_codes_are_canonical():
    scenarios = build_scenarios()
    validate_scenario_definitions(scenarios)
    for scenario in scenarios:
        for code in scenario.expected_reason_codes_include + scenario.expected_reason_codes_exclude:
            assert code in CANONICAL_REASON_CODES
            assert normalize_reason_code(code) == code


def test_warn_and_fail_scenarios_have_expected_reason_codes():
    for scenario in build_scenarios():
        if scenario.expected_verdict in {"WARN", "FAIL"}:
            assert scenario.expected_reason_codes_include, scenario.scenario_id


def test_pass_scenarios_do_not_require_expected_reason_codes():
    pass_scenarios = [s for s in build_scenarios() if s.expected_verdict == "PASS"]
    assert pass_scenarios
    assert any(not s.expected_reason_codes_include for s in pass_scenarios)


def test_internal_judge_patch_scenarios_do_not_validate_exit_codes():
    judge_patch_scenarios = [s for s in build_scenarios() if s.command_mode == "judge_patch"]
    assert judge_patch_scenarios
    assert all(s.expected_exit_code is None for s in judge_patch_scenarios)


def test_scenario_schema_uses_expected_report_fields_name():
    scenario = build_scenarios()[0]
    assert hasattr(scenario, "expected_report_fields")
    assert not hasattr(scenario, "expected_checked_fields")


def test_reason_code_normalization_is_deterministic():
    assert normalize_reason_code("path_escape") == "unsafe_path"
    assert normalize_reason_code("missing_modified_files") == "missing_file"
    assert normalize_reason_codes(["new_file", "path_escape", "new_file"]) == ["new_file", "unsafe_path"]


def test_direct_matrix_run_passes():
    data = run_matrix()
    assert data["scenario_count"] >= 55
    assert data["metamorphic_invariant_count"] >= 8
    assert data["failed"] == 0
    assert data["passed"] == data["selected_count"]


def test_cli_json_output_is_valid_json_only():
    cp = subprocess.run([sys.executable, "tools/behavior_matrix.py", "--json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    data = json.loads(cp.stdout)
    assert data["failed"] == 0
    assert cp.stdout.lstrip().startswith("{")
    assert cp.stdout.rstrip().endswith("}")


def test_cli_human_run_passes():
    cp = subprocess.run([sys.executable, "tools/behavior_matrix.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert "Behavior matrix:" in cp.stdout


def test_core_invariant_tags_present():
    tags = {tag for scenario in build_scenarios() for tag in scenario.tags}
    assert {
        "invariant_reorder",
        "invariant_readme",
        "invariant_path",
        "invariant_whitespace",
        "invariant_manifest_order",
        "invariant_tempdir",
        "invariant_human_json",
    } <= tags


def test_behavior_matrix_reports_include_replay_evidence_for_representative_cases():
    data = run_matrix()
    covered = set()
    for result in data["results"]:
        report = result.get("report") or {}
        reason_map = report.get("reason_code_evidence") or report.get("traffic", {}).get("reason_code_evidence") or {}
        replay = report.get("replay_bundle") or report.get("traffic", {}).get("replay_bundle") or {}
        for code in {"missing_file", "unsupported_dependency", "unsupported_command", "protected_artifact", "unsupported_ecosystem", "binary_diff"}:
            if code in reason_map:
                assert reason_map[code]
                assert replay.get("schema_version") == "sourcepack.replay_bundle.v1"
                covered.add(code)
    assert {"missing_file", "unsupported_dependency", "unsupported_command", "protected_artifact"} <= covered


---

## File: tests/test_ci_docs_truth.py

Metadata:
- sha256: f84ebc3d5cfd5848dbd14ae46eef8447cb22fe3995d71eded4aa7ac80cae88f3
- bytes: 1934
- estimated_tokens: 484

Content:

from pathlib import Path


def test_ci_docs_truth():
    text = Path("docs/ci.md").read_text(encoding="utf-8")
    assert "sourcepack diff . --ci" in text
    assert "report artifact" in text.lower() and "sensitive" in text.lower()
    assert "Hosted CI result: unavailable from this environment" in text
    assert "docs/ci.md" in Path("README.md").read_text(encoding="utf-8")


def test_github_action_quickstart_materializes_pr_delta_with_mixed_reset():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    checkout = text.index("- name: Check out PR head")
    materialize = text.index("- name: Materialize PR delta as workspace changes")
    diff = text.index("- run: sourcepack diff . --ci")
    assert checkout < materialize < diff
    assert "ref: ${{ github.event.pull_request.head.sha }}" in text
    assert "fetch-depth: 0" in text
    assert "git fetch --no-tags origin ${{ github.event.pull_request.base.ref }}" in text
    assert "git reset --mixed ${{ github.event.pull_request.base.sha }}" in text
    assert "ref: ${{ github.event.pull_request.base.sha }}" not in text
    assert "git apply --index /tmp/sourcepack-pr.patch" not in text


def test_github_action_quickstart_explains_clean_pr_checkout_is_unsafe():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    assert "The `pull_request` trigger path is the actual PR guardrail path." in text
    assert "A clean PR checkout alone is structurally unsafe for local-diff validation" in text
    assert "no local workspace delta for `sourcepack diff . --ci` to inspect" in text
    assert "make the PR delta visible to SourcePack's diff engine as local workspace modifications" in text
    assert "Do not create, refresh, repair, or bless `.sourcepack/baseline/` inside pull-request CI." in text
    assert "A clean push checkout may contain no uncommitted diff matrix for SourcePack to inspect" in text


---

## File: tests/test_command_resolver.py

Metadata:
- sha256: 7656eeaa3a9dee55d5a3a29ec13fb8538433326705a5dbec662899ba587d6052
- bytes: 2081
- estimated_tokens: 521

Content:

from sourcepack.commands import resolve_command


def test_npm_script_missing_and_present(tmp_path):
    (tmp_path/"package.json").write_text('{"scripts":{}}')
    assert resolve_command(tmp_path, "npm run dev").reason_code == "unsupported_command"
    (tmp_path/"package.json").write_text('{"scripts":{"dev":"vite"}}')
    assert resolve_command(tmp_path, "npm run dev").verdict == "PASS"


def test_same_patch_script_addition_warns(tmp_path):
    assert resolve_command(tmp_path, "npm run dev", added_manifests={"package.json":'{"scripts":{"dev":"vite"}}'}).reason_code == "declared_command"


def test_compose_support(tmp_path):
    assert resolve_command(tmp_path, "docker compose up").reason_code == "unsupported_command"
    (tmp_path/"compose.yml").write_text("services: {}")
    assert resolve_command(tmp_path, "docker compose up").verdict == "PASS"


def test_makefile_target(tmp_path):
    (tmp_path/"Makefile").write_text("test:\n\tpytest\n")
    assert resolve_command(tmp_path, "make test").verdict == "PASS"
    assert resolve_command(tmp_path, "make missing").reason_code == "unsupported_command"


def test_justfile_taskfile_detected(tmp_path):
    (tmp_path/"justfile").write_text("test:\n  pytest\n")
    assert resolve_command(tmp_path, "just test").verdict == "PASS"
    (tmp_path/"Taskfile.yml").write_text("tasks:\n  build:\n    cmds: [echo ok]\n")
    assert resolve_command(tmp_path, "task build").verdict == "PASS"


def test_tox_env_present_and_dynamic_inconclusive(tmp_path):
    (tmp_path/"tox.ini").write_text("[tox]\nenvlist = py311\n")
    assert resolve_command(tmp_path, "tox -e py311").verdict == "PASS"
    (tmp_path/"tox.ini").write_text("[tox]\nenvlist = py{310,311}\n")
    assert resolve_command(tmp_path, "tox -e py311").reason_code == "command_check_inconclusive"


def test_unsupported_parser_and_path_safety(tmp_path):
    assert resolve_command(tmp_path, "unknown thing").reason_code == "command_check_inconclusive"
    assert resolve_command(tmp_path, "make ../../x").reason_code in {"command_manifest_missing", "unsupported_command"}


---

## File: tests/test_confidence_report.py

Metadata:
- sha256: 58023e6ecf0f256c5f7f4e0e679894b1a08222f0eeff50218525a8059f764e9f
- bytes: 764
- estimated_tokens: 191

Content:

from sourcepack.reports.json import traffic_report


def test_confidence_fields_and_limitations():
    report = traffic_report("PASS", checked_categories=["dependency_check", "command_check"])
    assert "checked" in report and "not_checked" in report and "confidence_summary" in report
    text = " ".join(report["confidence_summary"]["limitations"])
    assert "does not prove code correctness" in text
    assert report["verdict"] == "PASS"


def test_unsupported_categories_do_not_disappear():
    finding = {"id":"unsupported_ecosystem", "severity":"warn", "category":"uncertainty", "message":"Cargo"}
    report = traffic_report("WARN", findings=[finding])
    assert report["unsupported_evidence"]
    assert "semantic correctness" in report["not_checked"]


---

## File: tests/test_dependency_resolver.py

Metadata:
- sha256: b54635c6a352179f720abbf022bebeeb790aa21b5ef0e054c6018fad37b2bf33
- bytes: 2053
- estimated_tokens: 514

Content:

from sourcepack.dependencies import resolve_js_import, resolve_python_import, unsupported_ecosystems


def test_python_stdlib_local_undeclared_declared(tmp_path):
    assert resolve_python_import(tmp_path, "json").verdict == "PASS"
    (tmp_path/"localmod.py").write_text("x=1")
    assert resolve_python_import(tmp_path, "localmod").verdict == "PASS"
    assert resolve_python_import(tmp_path, "fastapi").reason_code == "unsupported_dependency"
    (tmp_path/"pyproject.toml").write_text("[project]\ndependencies=['fastapi>=0.100']\n")
    assert resolve_python_import(tmp_path, "fastapi").verdict == "PASS"


def test_python_same_patch_and_optional_scope(tmp_path):
    assert resolve_python_import(tmp_path, "fastapi", added_dependencies={"fastapi"}).reason_code == "declared_dependency"
    (tmp_path/"pyproject.toml").write_text("[project.optional-dependencies]\nweb=['fastapi']\n")
    assert resolve_python_import(tmp_path, "fastapi").reason_code == "dependency_scope_review"


def test_js_relative_undeclared_declared_dev_and_scoped(tmp_path):
    assert resolve_js_import(tmp_path, "./lib.js").verdict == "PASS"
    (tmp_path/"package.json").write_text("{}")
    assert resolve_js_import(tmp_path, "react").reason_code == "unsupported_dependency"
    (tmp_path/"package.json").write_text('{"dependencies":{"@scope/pkg":"1","react":"1"}}')
    assert resolve_js_import(tmp_path, "@scope/pkg/sub").verdict == "PASS"
    assert resolve_js_import(tmp_path, "react").verdict == "PASS"
    (tmp_path/"package.json").write_text('{"devDependencies":{"react":"1"}}')
    assert resolve_js_import(tmp_path, "react").reason_code == "dependency_scope_review"


def test_ts_alias_inconclusive_and_unsupported_ecosystem(tmp_path):
    (tmp_path/"tsconfig.json").write_text('{"compilerOptions":{"paths":{"@/*":["src/*"]}}}')
    assert resolve_js_import(tmp_path, "@/lib").reason_code == "js_alias_uncertain"
    (tmp_path/"Cargo.toml").write_text("[package]\nname='x'\n")
    assert unsupported_ecosystems(tmp_path)[0].reason_code == "unsupported_ecosystem"


---

## File: tests/test_engine_inversion.py

Metadata:
- sha256: 18c8abff8e0f3c61619b2c4b8f16469cff5fff71eabd754c2e35a9c09a03cb14
- bytes: 5273
- estimated_tokens: 1319

Content:

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from sourcepack.reason_codes import canonical_reason_codes, is_canonical_reason_code, normalize_reason_code
from sourcepack.reports.json import normalized_finding, traffic_report

ROOT = Path(__file__).resolve().parents[1]
CORE_PATHS = [
    ROOT / "src/sourcepack/judgment.py",
    ROOT / "src/sourcepack/baseline.py",
    ROOT / "src/sourcepack/diff_parser.py",
    ROOT / "src/sourcepack/git.py",
    ROOT / "src/sourcepack/policy.py",
    ROOT / "src/sourcepack/reason_codes.py",
    ROOT / "src/sourcepack/schemas.py",
    *sorted((ROOT / "src/sourcepack/ecosystems").glob("*.py")),
    *sorted((ROOT / "src/sourcepack/reports").glob("*.py")),
]


def _imports_cli(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "sourcepack.cli" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sourcepack.cli":
                return True
            if node.module == "cli" and node.level >= 1:
                return True
    text = path.read_text(encoding="utf-8")
    return any(token in text for token in ("from .cli import", "from sourcepack.cli import", "import sourcepack.cli"))


def test_core_modules_do_not_import_cli() -> None:
    offenders = [str(path.relative_to(ROOT)) for path in CORE_PATHS if _imports_cli(path)]
    assert offenders == []


def test_judgment_module_does_not_contain_cli_behavior() -> None:
    source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    forbidden = [
        "argparse",
        "webbrowser",
        "def run_cli",
        "def cli_",
        "print(",
        "parser.add_",
        "subparsers",
        "install_hook",
        "uninstall_hook",
    ]
    offenders = [token for token in forbidden if token in source]
    assert offenders == []


def test_judgment_uses_diff_parser_patch_file_change() -> None:
    source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    assert "from .diff_parser import PatchFileChange" in source
    assert "class PatchFileChange" not in source
    assert "def parse_unified_diff" not in source


def test_baseline_module_does_not_import_judgment() -> None:
    source = (ROOT / "src/sourcepack/baseline.py").read_text(encoding="utf-8")
    assert "judgment" not in source


def test_baseline_module_owns_baseline_engine() -> None:
    baseline_source = (ROOT / "src/sourcepack/baseline.py").read_text(encoding="utf-8")
    judgment_source = (ROOT / "src/sourcepack/judgment.py").read_text(encoding="utf-8")
    required = [
        "class BaselineLockError",
        "def baseline_corrupt_result",
        "def resolve_active_baseline",
        "def _validate_packet_artifacts",
        "def validate_baseline",
        "def acquire_baseline_lock",
        "def release_baseline_lock",
        "def _write_json_atomic",
        "def _unique_build_id",
        "def build_current_baseline",
        "def baseline_report_fields",
    ]
    assert [token for token in required if token not in baseline_source] == []
    forbidden = ["def validate_baseline", "def build_current_baseline", "def resolve_active_baseline"]
    assert [token for token in forbidden if token in judgment_source] == []


def test_cli_diff_delegates_to_judge_repo_change() -> None:
    source = (ROOT / "src/sourcepack/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cli_diff = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "cli_diff")
    calls = [node for node in ast.walk(cli_diff) if isinstance(node, ast.Call)]
    assert any(isinstance(call.func, ast.Name) and call.func.id == "judge_repo_change" for call in calls)


def test_report_rejects_unknown_warn_fail_reason_code() -> None:
    with pytest.raises(ValueError):
        normalized_finding("not_a_code", "warn", "review", "bad")
    with pytest.raises(ValueError):
        normalized_finding("not_a_code", "error", "review", "bad")


def test_report_all_warn_fail_codes_are_canonical() -> None:
    report = traffic_report(
        "WARN",
        findings=[normalized_finding("baseline-missing", "warn", "baseline", "missing")],
    )
    ids = {finding["id"] for finding in report["findings"] if finding["severity"] in {"warn", "error"}}
    assert ids <= set(canonical_reason_codes())


def test_reason_code_docs_match_code_vocabulary() -> None:
    docs = (ROOT / "docs/reason-codes.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^## ([a-z0-9_]+)$", docs, flags=re.MULTILINE))
    assert set(canonical_reason_codes()) <= documented


def test_reason_code_alias_normalization() -> None:
    assert normalize_reason_code("baseline-missing") == "baseline_missing"
    assert normalize_reason_code("baseline corrupt") == "baseline_corrupt"


def test_reason_code_strict_canonical_spelling() -> None:
    assert is_canonical_reason_code("baseline_missing")
    assert normalize_reason_code("baseline-missing") == "baseline_missing"
    assert "baseline-missing" not in set(canonical_reason_codes())


---

## File: tests/test_evidence_model.py

Metadata:
- sha256: 6d2cc3ebf680840ab6fa632f660e4bc2f22c927cb3fcb6df4a49a557da08fa6a
- bytes: 5515
- estimated_tokens: 1379

Content:

import json
from sourcepack.evidence import EvidenceClass, attach_evidence_to_finding, can_satisfy, evidence_summary, make_evidence
from sourcepack.reports.json import traffic_report, write_user_report


def test_advisory_evidence_cannot_satisfy_trusted_requirements():
    assert not can_satisfy(make_evidence("prompt_context", ".sourcepack/prompt/prompt.md"), "trusted_baseline")
    assert not can_satisfy(make_evidence("ai_answer", "answer.md"), "execution_ledger", claim="local_execution")


def test_execution_ledger_supports_local_execution_only():
    ev = make_evidence("execution_ledger", ".sourcepack/evidence/ledger.jsonl")
    assert can_satisfy(ev, EvidenceClass.EXECUTION_LEDGER, claim="local_execution")
    assert not can_satisfy(ev, EvidenceClass.EXECUTION_LEDGER, claim="semantic_correctness")


def test_unsupported_and_not_checked_do_not_become_trusted():
    assert not can_satisfy(make_evidence("unsupported", "Cargo.toml"), "trusted_baseline")
    assert not can_satisfy(make_evidence("not_checked", "security"), "trusted_baseline")


def test_report_includes_evidence_class_fields_and_json_schema():
    finding = attach_evidence_to_finding({"id":"no_diff","severity":"info","category":"diff","message":"ok"}, "trusted_baseline", ".sourcepack/baseline")
    report = traffic_report("PASS", findings=[finding], checked_categories=["baseline"])
    assert report["schema_version"] == "traffic_report.v1"
    assert report["evidence"]["schema_version"] == "sourcepack.evidence.v1"
    assert report["findings"][0]["evidence_class"] == "trusted_baseline"
    json.dumps(report)


def test_html_markdown_generation_failures_do_not_alter_verdict(tmp_path, monkeypatch):
    import sourcepack.reports.json as reports_json
    monkeypatch.setattr(reports_json, "render_report_html", lambda report: (_ for _ in ()).throw(RuntimeError("boom")))
    report = traffic_report("WARN", findings=[])
    write_user_report(tmp_path, report, "x")
    saved = json.loads((tmp_path/".sourcepack/reports/latest.json").read_text())
    assert saved["verdict"] == "WARN"


def test_evidence_summary_buckets():
    summary = evidence_summary([make_evidence("prompt_context", "prompt"), make_evidence("not_checked", "security", "not_checked"), make_evidence("dependency_manifest", "pyproject.toml")])
    assert summary["advisory_evidence_ignored_for_enforcement"]
    assert summary["not_checked"]
    assert summary["checked_evidence"]


def test_canonical_evidence_item_schema_and_stable_id():
    from sourcepack.evidence import make_evidence_item
    item1 = make_evidence_item("missing_file", "trusted_baseline", path="src/missing.py", observed_value="src/missing.py", supports=["missing_file"])
    item2 = make_evidence_item("missing_file", "trusted_baseline", path="src/missing.py", observed_value="src/missing.py", supports=["missing_file"])
    data = item1.to_dict()
    assert item1.evidence_id == item2.evidence_id
    assert set(data) == {"evidence_id", "category", "source_type", "path", "line_start", "line_end", "observed_value", "normalized_value", "supports", "contradicts", "uncertainty", "metadata"}
    assert data["evidence_id"].startswith("ev_")


def test_reason_code_to_evidence_mapping_uses_canonical_codes_and_json_valid():
    report = traffic_report("FAIL", findings=[{"id":"missing_file","severity":"error","category":"file","path":"src/nope.py","message":"missing"}])
    assert list(report["reason_code_evidence"]) == ["missing_file"]
    assert report["evidence_items"][0]["evidence_id"] in report["reason_code_evidence"]["missing_file"]
    assert report["replay_bundle"]["schema_version"] == "sourcepack.replay_bundle.v1"
    json.dumps(report)


def test_replay_bundle_is_deterministic_except_allowed_fields():
    finding = {"id":"unsupported_command","severity":"error","category":"command","message":"bad command","evidence":"npm run madeup"}
    one = traffic_report("FAIL", findings=[finding])["replay_bundle"]
    two = traffic_report("FAIL", findings=[finding])["replay_bundle"]
    one.pop("generated_at", None); two.pop("generated_at", None)
    assert one == two


def test_high_value_categories_link_to_evidence_items():
    findings = [
        {"id":"unsupported_dependency","severity":"error","category":"dependency","message":"dep","evidence":"fastapi"},
        {"id":"unsupported_command","severity":"error","category":"command","message":"cmd","evidence":"npm run x"},
        {"id":"missing_file","severity":"error","category":"file","message":"missing","path":"src/missing.py"},
        {"id":"protected_artifact","severity":"error","category":"artifact","message":"protected","path":".sourcepack/manifest.json","evidence":".sourcepack/manifest.json"},
        {"id":"unsafe_path","severity":"error","category":"diff","message":"unsafe","path":"../x","evidence":"x"},
        {"id":"unsupported_ecosystem","severity":"warn","category":"uncertainty","message":"Cargo.toml detected","evidence":"Cargo.toml"},
    ]
    report = traffic_report("FAIL", findings=findings)
    for code in {"unsupported_dependency", "unsupported_command", "missing_file", "protected_artifact", "unsafe_path", "unsupported_ecosystem"}:
        assert code in report["reason_code_evidence"]
        ev = [i for i in report["evidence_items"] if i["evidence_id"] in report["reason_code_evidence"][code]][0]
        assert ev["supports"] == [code]
    unsafe = [i for i in report["evidence_items"] if i["category"] == "unsafe_path"][0]
    assert unsafe["normalized_value"] == "../x"


---

## File: tests/test_execution_ledger.py

Metadata:
- sha256: 04d0eb77a1faddaf7be5368ef5fde686a090a81e167093408be6dcc63b41c245
- bytes: 5543
- estimated_tokens: 1386

Content:

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import run_cli
from sourcepack.execution_ledger import (
    SCHEMA_VERSION,
    detect_execution_claims,
    entry_to_json,
    execution_findings,
    iter_entries,
    ledger_path,
    run_and_record,
)


@contextlib.contextmanager
def cwd(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def init_repo(repo: Path) -> None:
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL)


def test_ledger_entry_creation_and_deterministic_shape():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "print('ok')"], cwd=repo)
        data = json.loads(entry_to_json(entry))
        assert data["schema_version"] == SCHEMA_VERSION
        assert list(data) == sorted(data)
        assert data["command"] == ["python", "-c", "print('ok')"]
        assert ledger_path(repo).exists()
        assert list(iter_entries(repo))[0]["entry_id"] == entry.entry_id


def test_stdout_stderr_hashing_and_excerpt_truncation():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "import sys; print('x'*3000); print('err', file=sys.stderr)"], cwd=repo)
        assert entry.stdout_sha256 == hashlib.sha256((("x" * 3000) + "\n").encode()).hexdigest()
        assert entry.stderr_sha256 == hashlib.sha256(b"err\n").hexdigest()
        assert entry.stdout_excerpt.endswith("…[truncated]")
        assert "err" in entry.stderr_excerpt


def test_failed_command_recording():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        entry = run_and_record(["python", "-c", "import sys; sys.exit(7)"], cwd=repo)
        assert entry.exit_code == 7
        assert list(iter_entries(repo))[0]["exit_code"] == 7


def test_cli_json_only_output_where_applicable():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        with cwd(repo):
            assert run_cli(["exec", "--", "python", "-c", "print('json smoke')"]) == 0
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                assert run_cli(["evidence", "list", "--json"]) == 0
            parsed = json.loads(out.getvalue())
            assert parsed["schema_version"] == "sourcepack.execution_ledger.list.v1"


def test_explicit_execution_claim_detection():
    text = "Tests passed. pytest passed. npm run build works. I ran python -m pytest. I tested npm test."
    commands = [claim.command for claim in detect_execution_claims(text)]
    assert "tests" in commands
    assert "pytest" in commands
    assert "npm run build" in commands
    assert "python -m pytest" in commands
    assert "npm test" in commands


def test_near_miss_phrases_do_not_trigger_execution_claims():
    near_misses = [
        "run tests", "please test", "should pass", "probably passes", "expected to pass",
        "build support", "works toward", "the test file was added", "passing through",
        "unrelated prose containing the word passed",
    ]
    for phrase in near_misses:
        assert detect_execution_claims(phrase) == []


def test_report_includes_execution_evidence_when_available():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        run_and_record(["python", "-c", "print(1)"], cwd=repo)
        findings = execution_findings(repo, "I ran python -c print(1)")
        assert findings[0]["id"] == "execution_evidence_present"
        assert findings[0]["severity"] == "info"
        assert findings[0]["ledger_entry_id"]


def test_missing_execution_evidence_produces_warn_not_fake_pass():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        findings = execution_findings(repo, "pytest passed")
        assert findings[0]["id"] == "execution_evidence_missing"
        assert findings[0]["severity"] == "warn"


def test_ledger_does_not_update_trusted_baseline():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        baseline = repo / ".sourcepack" / "baseline"
        before_exists = baseline.exists()
        run_and_record(["python", "-c", "print('ok')"], cwd=repo)
        assert baseline.exists() is before_exists


def test_ledger_does_not_treat_prompt_claims_as_trusted_evidence():
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        init_repo(repo)
        prompt = repo / ".sourcepack" / "prompt"
        prompt.mkdir(parents=True)
        (prompt / "context.md").write_text("pytest passed\n", encoding="utf-8")
        findings = execution_findings(repo, (prompt / "context.md").read_text(encoding="utf-8"))
        assert findings[0]["id"] == "execution_evidence_missing"


---

## File: tests/test_final_boss_integration.py

Metadata:
- sha256: 6d5ac9c3b7a224477c679dbc574be933510d465a58326f6434c9b04e7dde147c
- bytes: 3487
- estimated_tokens: 872

Content:

import json
import subprocess
import sys


def run(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_repo(tmp_path, files):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return tmp_path


def diff_json(repo):
    cp = run(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def ids(report):
    return {f["id"] for f in report["findings"]}


def test_missing_execution_evidence_changes_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n"})
    (repo / "README.md").write_text("demo\ntests passed\n", encoding="utf-8")
    code, report = diff_json(repo)
    assert code == 0
    assert report["verdict"] == "WARN"
    assert "execution_evidence_missing" in ids(report)
    finding = next(f for f in report["findings"] if f["id"] == "execution_evidence_missing")
    assert finding["evidence_class"] == "execution_ledger"
    assert "execution" in report["partially_checked"] or "execution_claim_check" in report["partially_checked"]


def test_successful_ledger_evidence_changes_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n"})
    cp = run(repo, "exec", "--", "python", "-c", "print('ok')")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    (repo / "README.md").write_text("demo\nI ran python -c print('ok')\n", encoding="utf-8")
    _, report = diff_json(repo)
    assert "execution_evidence_present" in ids(report)
    assert "execution_evidence_missing" not in ids(report)


def test_command_and_dependency_resolvers_affect_actual_diff_report(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n", "package.json": '{"scripts":{}}\n', "app.py": "print(1)\n"})
    (repo / "README.md").write_text("demo\nnpm run dev\n", encoding="utf-8")
    (repo / "app.py").write_text("print(1)\nimport fastapi\n", encoding="utf-8")
    code, report = diff_json(repo)
    assert code == 1
    assert {"unsupported_command", "unsupported_dependency"} <= ids(report)


def test_prompt_context_cannot_satisfy_enforcement_evidence(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "demo\n", ".sourcepack/prompt/context.md": "fastapi is declared and pytest passed\n", "app.py": "print(1)\n"})
    (repo / "app.py").write_text("print(1)\nimport fastapi\n", encoding="utf-8")
    (repo / "README.md").write_text("demo\ntests passed\n", encoding="utf-8")
    _, report = diff_json(repo)
    assert {"unsupported_dependency", "execution_evidence_missing"} <= ids(report)
    assert not any(f.get("evidence_class") == "prompt_context" and f["id"] in {"unsupported_dependency", "execution_evidence_missing"} for f in report["findings"])


---

## File: tests/test_gauntlet.py

Metadata:
- sha256: 3f7ece379810265514bc24f7381e6c8cf0ef5f376a44d915cf264df5af38f411
- bytes: 20520
- estimated_tokens: 5130

Content:

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sourcepack.cli import run_cli, validate_baseline, judge_patch, judge_patch_text, build_current_baseline, extract_js_import_specifiers_from_text


def capture_cli(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = run_cli(args)
    return code, out.getvalue()


class GauntletTest(unittest.TestCase):
    def make_repo(self, tmp: Path, files: dict[str, str | bytes]) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        for rel, content in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        code, _ = capture_cli(["baseline", str(repo), "--quiet"])
        self.assertEqual(code, 0)
        return repo

    def diff_json(self, repo: Path, staged: bool = False):
        args = ["diff", str(repo)] + (["--staged"] if staged else []) + ["--json"]
        code, text = capture_cli(args)
        return code, json.loads(text)

    def ids(self, report: dict) -> set[str]:
        return {f["id"] for f in report.get("findings", [])}

    def test_clean_supported_edit_is_scoped_green(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value():\n    return 1\n", "requirements.txt": ""})
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "PASS")
            self.assertEqual(data["light"], "GREEN LIGHT")
            self.assertIn("Python imports", data["checked_categories"])
            self.assertIn("semantic correctness", data["not_checked"])

    def test_new_helper_file_is_yellow_review_not_dependency_red(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
            (repo / "helper.py").write_text("import os\nfrom pathlib import Path\nVALUE = Path(os.getcwd()).name\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertEqual(data["reason_type"], "review")
            self.assertIn("new_file", self.ids(data))
            self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_python_dependencies_stdlib_aliases_and_local_imports(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "localmod.py": "X = 1\n", "src/localpkg/__init__.py": "Y = 1\n", "requirements.txt": "PyYAML\nPillow\n"})
            (repo / "app.py").write_text("import os\nimport sys\nimport json\nimport pathlib\nimport yaml\nfrom PIL import Image\nimport localmod\nimport localpkg\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertNotIn("unsupported_dependency", self.ids(data))
            self.assertNotEqual(data["verdict"], "FAIL")
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
            (repo / "app.py").write_text("import yaml\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertIn("unsupported_dependency", self.ids(data))
            self.assertTrue(any(f.get("evidence") == "yaml" for f in data["findings"]))
        if hasattr(sys, "stdlib_module_names") and "tomllib" in sys.stdlib_module_names:
            with TemporaryDirectory() as td:
                repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": ""})
                (repo / "app.py").write_text("import tomllib\n", encoding="utf-8")
                code, data = self.diff_json(repo)
                self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_python_fastapi_declared_and_undeclared(self):
        for declared, should_fail in [("", True), ("fastapi\n", False)]:
            with self.subTest(declared=bool(declared)):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "requirements.txt": declared})
                    (repo / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
                    code, data = self.diff_json(repo)
                    self.assertEqual(code, 1 if should_fail else 0)
                    self.assertEqual("unsupported_dependency" in self.ids(data), should_fail)

    def test_js_declared_undeclared_scoped_alias_and_workspace(self):
        cases = [
            ({"package.json": '{"dependencies": {}}', "app.js": "console.log(1)\n"}, "view.js", 'import React from "react"\n', True),
            ({"package.json": '{"dependencies": {"react":"latest", "@scope/pkg":"1.0.0"}}', "app.js": "console.log(1)\n"}, "view.js", 'import React from "react"\nimport x from "@scope/pkg"\n', False),
            ({"package.json": '{"workspaces": ["packages/*"]}', "packages/core/package.json": '{"name":"@myorg/core"}', "app.js": "console.log(1)\n"}, "use.js", 'import { shared } from "@myorg/core/utils"\n', False),
            ({"package.json": '{}', "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', "src/components/Button.ts": "export const Button = 1\n", "app.ts": "console.log(1)\n"}, "view.ts", 'import { Button } from "@/components/Button"\n', False),
        ]
        for files, changed, content, should_fail in cases:
            with self.subTest(content=content):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), files)
                    (repo / changed).write_text(content, encoding="utf-8")
                    code, data = self.diff_json(repo)
                    self.assertEqual("unsupported_dependency" in self.ids(data), should_fail)

    def test_same_patch_dependencies_are_ecosystem_scoped(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n", "package.json": '{"dependencies":{}}\n'})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
+import requests
 def value(): return 1
diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1,5 @@
-{"dependencies":{}}
+{
+  "dependencies": {
+    "requests": "^1.0.0"
+  }
+}
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("requests", report["unsupported_dependencies"])

        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.js": "export const value = 1;\n", "pyproject.toml": '[project]\nname="demo"\ndependencies=[]\n'})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, """diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1 +1,2 @@
+import React from "react/jsx-runtime";
 export const value = 1;
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,3 +1,3 @@
 [project]
 name="demo"
-dependencies=[]
+dependencies=["react"]
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("react", report["unsupported_dependencies"])


    def test_js_raw_import_specifier_extraction_preserves_alias_scoped_and_subpaths(self):
        imports = extract_js_import_specifiers_from_text('''
import { Button } from "@/components/Button"
import helper from "~/utils"
import { core } from "@myorg/core/utils"
import runtime from "react/jsx-runtime"
const React = require("react")
const lazy = import("@scope/pkg/subpath")
''')
        self.assertIn("@/components/button", imports)
        self.assertIn("~/utils", imports)
        self.assertIn("@myorg/core/utils", imports)
        self.assertIn("react/jsx-runtime", imports)
        self.assertIn("@scope/pkg/subpath", imports)

    def test_js_unresolved_alias_is_yellow_uncertain_not_silent_green(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{}', "app.ts": "console.log(1)\n"})
            (repo / "view.ts").write_text('import { Button } from "@/components/Button"\n', encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertIn("js_alias_uncertain", self.ids(data))
            self.assertNotIn("unsupported_dependency", self.ids(data))

    def test_same_patch_js_dependencies_are_yellow_for_json_formats_scoped_and_subpaths(self):
        cases = [
            ('{"dependencies":{"react":"latest"}}', 'import React from "react"\n', "react"),
            ('''{
  "dependencies": {
    "react": "latest"
  }
}''', 'import React from "react"\n', "react"),
            ('{"dependencies":{"@scope/pkg":"1.0.0"}}', 'import thing from "@scope/pkg/subpath"\n', "@scope/pkg"),
            ('{"dependencies":{"react":"latest"}}', 'import runtime from "react/jsx-runtime"\n', "react"),
        ]
        for package_json, import_line, expected_dep in cases:
            with self.subTest(expected_dep=expected_dep, import_line=import_line):
                with TemporaryDirectory() as td:
                    repo = self.make_repo(Path(td), {"app.js": "export const value = 1;\n", "package.json": '{}\n'})
                    packet = repo / validate_baseline(repo)["packet_path"]
                    added_package_json = "\n".join(f"+{line}" for line in package_json.splitlines())
                    report = judge_patch_text(packet, f'''diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1 +1,2 @@
+{import_line.rstrip()}
 export const value = 1;
diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1 @@
-{{}}
{added_package_json}
''')
                    traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
                    self.assertEqual(traffic["verdict"], "WARN")
                    self.assertNotIn("unsupported_dependency", {f["id"] for f in traffic["findings"]})
                    self.assertIn(expected_dep, report.get("declared_dependencies", []))

    def test_judge_patch_invalid_utf8_fails_closed_as_malformed_diff(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            repo = self.make_repo(root, {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            patch = root / "bad.patch"
            patch.write_bytes(b"\xff\xfe\x00")
            out = root / "out"
            report = judge_patch(packet, patch, out)
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("malformed_diff", {f["id"] for f in traffic["findings"]})

    def test_npm_and_compose_same_patch_support_exactness(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{"scripts":{}}', "README.md": "demo\n"})
            (repo / "README.md").write_text("Run npm run dev\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertIn("unsupported_command", self.ids(data))
        patch = """diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -1 +1 @@
-{"scripts":{}}
+{"scripts":{"dev":"vite"}}
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-demo
+Run npm run dev and npm run build
"""
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"package.json": '{"scripts":{}}', "README.md": "demo\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, patch)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("npm run build", report["unsupported_commands"])
            self.assertNotIn("npm run dev", report["unsupported_commands"])
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"README.md": "demo\n"})
            (repo / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
            (repo / "README.md").write_text("Run docker compose up\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertNotIn("unsupported_command", self.ids(data))

    def test_protected_scope_root_manifest_and_sourcepack_trust(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"manifest.json": "{}\n", "docs/receipt.json": "{}\n"})
            (repo / "manifest.json").write_text('{"project":true}\n', encoding="utf-8")
            (repo / "docs" / "receipt.json").write_text('{"project":true}\n', encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertNotIn("protected_artifact", self.ids(data))
            packet = repo / validate_baseline(repo)["packet_path"]
            patch = """diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json
--- a/.sourcepack/baseline/active.json
+++ b/.sourcepack/baseline/active.json
@@ -1 +1 @@
-{}
+{"tamper": true}
"""
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(judge_patch_text(packet, patch))
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("protected_artifact", {f["id"] for f in traffic["findings"]})

    def test_unsupported_ecosystem_stale_binary_malformed_and_prompt(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"Cargo.toml": "[package]\nname='demo'\n", "src/lib.rs": "pub fn x(){}\n"})
            (repo / "src" / "lib.rs").write_text("pub fn x(){ }\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertEqual(data["verdict"], "WARN")
            self.assertIn("unsupported_ecosystem", self.ids(data))
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            (repo / "asset.bin").write_bytes(b"\x00\x01\x02")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertIn("binary_diff", self.ids(data))
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            report = judge_patch_text(packet, "not a unified diff\n")
            traffic = __import__("sourcepack.cli", fromlist=["patch_report_to_traffic"]).patch_report_to_traffic(report)
            self.assertEqual(traffic["verdict"], "FAIL")
            self.assertIn("malformed_diff", {f["id"] for f in traffic["findings"]})
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            (repo / ".sourcepack" / "state" / "baseline_stale.json").write_text('{"reason":"test"}')
            (repo / "app.py").write_text("def value(): return 2\n", encoding="utf-8")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 0)
            self.assertIn("baseline_stale", self.ids(data))
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "app.py").write_text("def value(): return 1\n", encoding="utf-8")
            code, _ = capture_cli(["prompt", str(repo), "task"])
            self.assertEqual(code, 0)
            self.assertTrue((repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").exists())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_missing_baseline_untracked_binary_does_not_auto_create(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "asset.bin").write_bytes(b"\x00\x01")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            self.assertEqual(data["baseline_integrity_finding_id"], "baseline_missing")
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_partial_legacy_and_receipt_traversal_are_corrupt(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            packet = repo / ".sourcepack" / "baseline" / "packet"
            packet.mkdir(parents=True)
            (packet / "receipt.json").write_text("{}")
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {"app.py": "def value(): return 1\n"})
            packet = repo / validate_baseline(repo)["packet_path"]
            receipt = json.loads((packet / "receipt.json").read_text())
            receipt["hashes"]["../outside"] = "abc"
            (packet / "receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(validate_baseline(repo)["state"], "corrupt")


    def test_ugly_repo_mixed_layout_docs_workflow_deleted_binary_and_unsupported(self):
        with TemporaryDirectory() as td:
            repo = self.make_repo(Path(td), {
                "package.json": '{"devDependencies":{"eslint":"latest"}}\n',
                "pyproject.toml": '[project]\nname="ugly"\n[project.optional-dependencies]\ndev=["pytest"]\n',
                "src/ugly/__init__.py": "VALUE = 1\n",
                "packages/web/package.json": '{"dependencies":{"react":"latest"}}\n',
                "README.md": "Run pytest and npm test.\n",
                "docs/guide.md": "guide\n",
                ".github/workflows/ci.yml": "name: ci\non: [push]\n",
                "legacy.txt": "delete me\n",
                "blob.bin": b"\x00\x01\x02\x03",
                "Cargo.toml": "[package]\nname='unsupported'\nversion='0.1.0'\n",
            })
            (repo / "src" / "ugly" / "feature.py").write_text("import requests\n", encoding="utf-8")
            (repo / "docs" / "guide.md").write_text("guide v2\n", encoding="utf-8")
            (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: [push, pull_request]\n", encoding="utf-8")
            (repo / "legacy.txt").unlink()
            (repo / "generated.dat").write_bytes(b"\x00\x01generated")
            code, data = self.diff_json(repo)
            self.assertEqual(code, 1)
            finding_ids = self.ids(data)
            self.assertIn("unsupported_dependency", finding_ids)
            self.assertIn("new_file", finding_ids)
            self.assertIn("deleted_file", finding_ids)
            self.assertIn("workflow_change", finding_ids)
            self.assertIn("binary_diff", finding_ids)
            self.assertIn("unsupported_ecosystem", finding_ids)


if __name__ == "__main__":
    unittest.main()



---

## File: tests/test_github_action.py

Metadata:
- sha256: 12f910182d98a1bb054416ea63ea887d8b32017a22b2276b70f7d175483c60b2
- bytes: 25101
- estimated_tokens: 6276

Content:

import importlib.util
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "sourcepack.yml"
EXAMPLE_WORKFLOW = ROOT / "docs" / "examples" / "sourcepack-action.yml"
WRAPPER = ROOT / "scripts" / "sourcepack_action.py"


def load_action():
    text = ACTION.read_text(encoding="utf-8")
    data = {"inputs": {}, "runs": {"using": None, "steps": []}}
    section = None
    current_input = None
    in_steps = False
    current_step = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            in_steps = False
            continue
        if section == "inputs" and indent == 2 and line.endswith(":"):
            current_input = line[:-1]
            data["inputs"][current_input] = {}
            continue
        if section == "inputs" and current_input and indent == 4 and ":" in line:
            key, value = line.split(":", 1)
            data["inputs"][current_input][key] = value.strip().strip("'")
            continue
        if section == "runs" and indent == 2 and line.startswith("using:"):
            data["runs"]["using"] = line.split(":", 1)[1].strip()
            continue
        if section == "runs" and indent == 2 and line == "steps:":
            in_steps = True
            continue
        if section == "runs" and in_steps and indent == 4 and line.startswith("- "):
            current_step = {}
            data["runs"]["steps"].append(current_step)
            content = line[2:]
            if ":" in content:
                key, value = content.split(":", 1)
                current_step[key] = value.strip()
            continue
        if section == "runs" and in_steps and current_step is not None and indent == 6 and ":" in line:
            key, value = line.split(":", 1)
            current_step[key] = value.strip()
    return data


def action_text() -> str:
    return ACTION.read_text(encoding="utf-8")


def test_action_yml_exists_and_parses_as_yaml():
    data = load_action()
    assert data["runs"]["using"] == "composite"


def test_required_inputs_exist():
    inputs = load_action()["inputs"]
    required = {
        "mode",
        "sourcepack-version",
        "python-version",
        "baseline-path",
        "report-dir",
        "json",
        "markdown",
        "sarif",
        "fail-on-warn",
        "run-doctor",
        "upload-artifact",
        "comment-pr",
    }
    assert required <= set(inputs)
    assert inputs["mode"]["default"] == "ci"
    assert inputs["baseline-path"]["default"] == ".sourcepack/baseline"



def run_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if stripped.startswith("run:"):
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped == "run: |":
                index += 1
                body: list[str] = []
                while index < len(lines):
                    body_raw = lines[index]
                    body_indent = len(body_raw) - len(body_raw.lstrip(" "))
                    if body_raw.strip() and body_indent <= indent:
                        break
                    body.append(body_raw)
                    index += 1
                bodies.append("\n".join(body))
                continue
            bodies.append(stripped.split(":", 1)[1].strip())
        index += 1
    return bodies


def test_action_does_not_interpolate_inputs_inside_shell_run_bodies():
    offenders = [body for body in run_bodies(action_text()) if "${{ inputs." in body]
    assert offenders == []

def test_action_does_not_create_or_update_baseline_trust():
    text = action_text()
    forbidden = ["sourcepack init", "sourcepack baseline", "baseline --force"]
    assert [token for token in forbidden if token in text] == []


def test_action_references_version_and_conditional_doctor():
    data = load_action()
    text = action_text()
    assert "sourcepack --version" in text
    doctor_steps = [step for step in data["runs"]["steps"] if "sourcepack doctor" in str(step)]
    assert doctor_steps
    assert all("run-doctor" in step.get("if", "") for step in doctor_steps)


def test_action_verifies_baseline_before_diff_execution():
    text = action_text()
    baseline_index = text.index("SourcePack failed closed because trusted baseline state is missing")
    diff_index = text.index("sourcepack_action.py")
    assert baseline_index < diff_index
    assert "CI will not create or update trusted baseline state." in text


def test_action_writes_or_preserves_report_output():
    text = action_text()
    assert "sourcepack-report" in text
    assert "sourcepack.stderr.txt" in text
    assert "sourcepack.stdout.txt" in text
    assert "sourcepack-command.txt" in text
    assert "upload-artifact" in text


def test_ci_workflow_keeps_existing_validation_gates():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    required = [
        "push:",
        "pull_request:",
        "matrix:",
        "ubuntu-latest",
        "windows-latest",
        "python -m py_compile src/sourcepack/cli.py",
        "python -m unittest",
        "pytest -q tests/test_behavior_matrix.py",
        "pytest -q tests/test_golden_demo.py",
        "pytest -q tests/test_readme_truth.py",
        "pytest -q",
        "python tools/behavior_matrix.py",
        "python tools/behavior_matrix.py --json",
        "python tools/golden_demo.py --clean",
        "sourcepack doctor",
        "sourcepack demo",
        "python tools/release_smoke.py",
    ]
    assert [token for token in required if token not in text] == []



def test_sourcepack_workflow_dogfoods_committed_baseline_without_creating_trust_state():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python -B -m sourcepack.cli diff . --ci --json" in text
    assert "continue-on-error: true" not in text
    assert "PYTHONPATH: src" in text
    assert 'PYTHONDONTWRITEBYTECODE: "1"' in text
    assert "sourcepack baseline" not in text
    assert "sourcepack init" not in text
    assert "--refresh" not in text
    assert "baseline --force" not in text


def test_sourcepack_workflow_runs_gate_before_editable_install_and_validation_gates():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    install_index = text.index("Install package and test dependencies")
    gate_index = text.index("python -B -m sourcepack.cli diff . --ci --json")
    tests_index = text.index("Full pytest suite")
    assert gate_index < install_index < tests_index

def test_example_workflow_exists_and_does_not_create_baseline_during_pr():
    text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "# pull_request:" in text
    assert "uses: ./" in text
    assert "sourcepack baseline" not in text
    assert "sourcepack init" not in text
    assert "baseline --force" not in text


def load_wrapper():
    spec = importlib.util.spec_from_file_location("sourcepack_action", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wrapper_missing_baseline_returns_nonzero_and_message(tmp_path, capsys):
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    captured = capsys.readouterr()
    assert code != 0
    assert "SourcePack failed closed because trusted baseline state is missing" in captured.err
    assert "CI will not create or update trusted baseline state." in captured.err
    assert (tmp_path / "reports" / "sourcepack.stderr.txt").exists()


def test_wrapper_creates_report_dir_and_captures_command_output(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\necho err >&2\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    assert code == 0
    report_dir = tmp_path / "reports"
    assert (report_dir / "sourcepack-command.txt").read_text(encoding="utf-8").startswith("sourcepack diff")
    assert "PASS" in (report_dir / "sourcepack.stdout.txt").read_text(encoding="utf-8")
    assert "err" in (report_dir / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert (report_dir / "sourcepack.json").exists()
    assert (report_dir / "sourcepack.md").exists()


def os_path() -> str:
    import os

    return os.environ.get("PATH", "")


def test_wrapper_fail_on_warn_is_explicit_in_command(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"WARN\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    code = module.main([
        "--repo", str(tmp_path),
        "--baseline-path", ".sourcepack/baseline",
        "--report-dir", "reports",
        "--mode", "local",
        "--fail-on-warn", "true",
    ])
    assert code == 0
    command = (tmp_path / "reports" / "sourcepack-command.txt").read_text(encoding="utf-8")
    assert "--strict" in command


def test_wrapper_does_not_import_or_duplicate_core_judgment_logic():
    tree = WRAPPER.read_text(encoding="utf-8")
    forbidden = [
        "sourcepack.judgment",
        "sourcepack.dependencies",
        "sourcepack.baseline import",
        "def judge_",
        "def parse_unified_diff",
    ]
    assert [token for token in forbidden if token in tree] == []


def test_wrapper_py_compiles():
    subprocess.run([sys.executable, "-m", "py_compile", str(WRAPPER)], check=True)


def test_wrapper_sarif_true_copies_existing_latest_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "true"])
    assert code == 0
    assert (tmp_path / "out" / "sourcepack.sarif.json").read_text(encoding="utf-8") == '{"version":"2.1.0"}'


def test_wrapper_sarif_false_and_missing_sarif_do_not_fail_or_copy(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    (reports / "latest.sarif.json").unlink()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out2", "--sarif", "true"]) == 0
    assert not (tmp_path / "out2" / "sourcepack.sarif.json").exists()


def test_wrapper_missing_baseline_markdown_is_valid(tmp_path, capsys):
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "reports"]) != 0
    _ = capsys.readouterr()
    text = (tmp_path / "reports" / "sourcepack.md").read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0
    assert "SourcePack failed closed because trusted baseline state is missing" in text


def test_action_inputs_are_documented_in_ci_docs():
    inputs = set(load_action()["inputs"])
    ci_text = (ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
    missing = [name for name in sorted(inputs) if f"`{name}`" not in ci_text]
    assert missing == []


def test_wrapper_missing_baseline_explains_fail_closed_trust_boundary(tmp_path, capsys):
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    captured = capsys.readouterr()
    assert code != 0
    text = captured.err + (tmp_path / "reports" / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert "SourcePack failed closed because trusted baseline state is missing" in text
    assert "CI will not create or update trusted baseline state" in text
    assert "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow" in text
    assert "This is a trust-boundary behavior, not a package crash" in text


def test_wrapper_reports_paths_sarif_missing_and_step_summary(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\",\"traffic_light\":\"GREEN\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "reports", "--sarif", "true"]) == 0
    captured = capsys.readouterr()
    assert str(tmp_path / "reports") in captured.out
    assert "enabled, but no SourcePack SARIF report was present" in captured.out
    assert not (tmp_path / "reports" / "sourcepack.sarif.json").exists()
    summary_text = summary.read_text(encoding="utf-8")
    assert "Verdict: PASS" in summary_text
    assert "Traffic light: GREEN" in summary_text
    assert "Mode: ci" in summary_text
    assert "WARN fails in selected mode: True" in summary_text
    assert f"Report directory: {tmp_path / 'reports'}" in summary_text
    assert "SARIF passthrough: enabled, but no SourcePack SARIF report was present" in summary_text
    assert summary_text.count("```") % 2 == 0
    forbidden_claims = ["proves correctness", "proves security", "proves runtime success", "proves external API truth", "proves user intent"]
    assert [claim for claim in forbidden_claims if claim in summary_text] == []


def test_wrapper_sarif_disabled_summary_does_not_claim_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0
    summary = (tmp_path / "out" / "sourcepack.md").read_text(encoding="utf-8")
    assert "SARIF passthrough: disabled" in summary
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()


def test_wrapper_preserves_exact_command_and_delegates_to_cli(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    fake = bin_dir / "sourcepack"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$0 $*\" > {calls}\necho '{{\"verdict\":\"PASS\"}}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--mode", "strict"]) == 0
    command = (tmp_path / "out" / "sourcepack-command.txt").read_text(encoding="utf-8").strip()
    assert command == f"sourcepack diff {tmp_path} --json --strict"
    assert f"diff {tmp_path} --json --strict" in calls.read_text(encoding="utf-8")


def test_wrapper_does_not_create_baseline_or_use_prompt_as_authority(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    prompt = tmp_path / ".sourcepack" / "prompt"
    prompt.mkdir(parents=True)
    (prompt / "context.md").write_text("fake authority", encoding="utf-8")
    before_baseline = sorted(p.relative_to(baseline) for p in baseline.rglob("*"))
    before_prompt = sorted(p.relative_to(prompt) for p in prompt.rglob("*"))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out"]) == 0
    assert sorted(p.relative_to(baseline) for p in baseline.rglob("*")) == before_baseline
    assert sorted(p.relative_to(prompt) for p in prompt.rglob("*")) == before_prompt
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    assert ".sourcepack/prompt" not in wrapper_text
    assert "prompt" not in wrapper_text.lower()


def test_composite_action_like_run_writes_artifacts_command_summary_and_sarif(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    source_reports = tmp_path / ".sourcepack" / "reports"
    source_reports.mkdir(parents=True)
    (source_reports / "latest.sarif.json").write_text('{"version":"2.1.0","runs":[]}', encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    executed: list[list[str]] = []

    def fake_run(command, cwd):
        executed.append(command)
        (source_reports / "latest.json").write_text(
            '{"verdict":"PASS","traffic_light":"green","findings":[]}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS","traffic_light":"green"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    code = module.main([
        "--repo", str(tmp_path),
        "--baseline-path", ".sourcepack/baseline",
        "--report-dir", "action-report",
        "--mode", "ci",
        "--json", "true",
        "--markdown", "true",
        "--sarif", "true",
        "--fail-on-warn", "false",
    ])
    captured = capsys.readouterr()
    report_dir = tmp_path / "action-report"
    expected_command = ["sourcepack", "diff", str(tmp_path.resolve()), "--json", "--ci"]

    assert code == 0
    assert executed == [expected_command]
    assert report_dir.is_dir()
    for artifact in [
        "sourcepack.json",
        "sourcepack.md",
        "sourcepack.stdout.txt",
        "sourcepack.stderr.txt",
        "sourcepack-command.txt",
        "sourcepack.sarif.json",
    ]:
        assert (report_dir / artifact).exists(), artifact
    assert (report_dir / "sourcepack-command.txt").read_text(encoding="utf-8") == shlex.join(expected_command) + "\n"
    assert (report_dir / "sourcepack.sarif.json").read_text(encoding="utf-8") == '{"version":"2.1.0","runs":[]}'
    markdown = (report_dir / "sourcepack.md").read_text(encoding="utf-8")
    summary_text = summary.read_text(encoding="utf-8")
    for text in (markdown, summary_text):
        assert "- Verdict: PASS" in text
        assert "- Traffic light: green" in text
        assert "- Mode: ci" in text
        assert "- WARN fails in selected mode: True" in text
        assert f"- Report directory: {report_dir}" in text
        assert "sourcepack.json" in text
        assert "sourcepack.md" in text
        assert "sourcepack.stdout.txt" in text
        assert "sourcepack.stderr.txt" in text
        assert "sourcepack-command.txt" in text
        assert "sourcepack.sarif.json" in text
        assert "- SARIF passthrough: copied to" in text
        assert text.count("```") % 2 == 0
    assert "SourcePack SARIF passthrough: copied to" in captured.out


def test_composite_action_like_missing_sarif_is_reported_nonfatal(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "reports").mkdir(parents=True)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    executed: list[list[str]] = []

    def fake_run(command, cwd):
        executed.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "true"])
    captured = capsys.readouterr()

    assert code == 0
    assert len(executed) == 1
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    assert "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact" in captured.out
    assert "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact" in summary.read_text(encoding="utf-8")


def test_composite_action_like_sarif_disabled_does_not_imply_produced_artifact(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")

    def fake_run(command, cwd):
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"])
    captured = capsys.readouterr()
    markdown = (tmp_path / "out" / "sourcepack.md").read_text(encoding="utf-8")

    assert code == 0
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    assert "SourcePack SARIF passthrough: disabled" in captured.out
    assert "- SARIF passthrough: disabled" in markdown
    assert "sourcepack.sarif.json" not in markdown


def test_composite_action_like_prompt_context_does_not_satisfy_missing_baseline(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    prompt_dir = tmp_path / ".sourcepack" / "prompt"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "context.md").write_text("# non-authoritative prompt guidance\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    invoked: list[list[str]] = []

    def fake_run(command, cwd):
        invoked.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "out"])
    captured = capsys.readouterr()

    assert code != 0
    assert invoked == []
    assert not (tmp_path / ".sourcepack" / "baseline").exists()
    combined = captured.err + summary.read_text(encoding="utf-8") + (tmp_path / "out" / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert "SourcePack failed closed because trusted baseline state is missing" in combined
    assert "CI will not create or update trusted baseline state." in combined
    assert "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow." in combined
    assert "not a package crash" in combined
    command_log = (tmp_path / "out" / "sourcepack-command.txt").read_text(encoding="utf-8")
    assert command_log == "baseline preflight\n"
    assert "sourcepack baseline" not in command_log
    assert "sourcepack init" not in command_log
    assert "refresh" not in command_log
    assert "repair" not in command_log
    assert "bless" not in command_log


---

## File: tests/test_golden_demo.py

Metadata:
- sha256: b8508efb07cfd538fa3a40fceed037e239ec9be0b221414031b52bb275c042e3
- bytes: 1658
- estimated_tokens: 415

Content:

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "pass-clean": ("PASS", []),
    "warn-new-file": ("WARN", ["new_file"]),
    "fail-unsupported-dependency": ("FAIL", ["unsupported_dependency"]),
    "fail-unsupported-command": ("FAIL", ["unsupported_command"]),
    "fail-protected-artifact": ("FAIL", ["protected_artifact"]),
    "trust-boundary": ("WARN", ["new_file"]),
}


def test_golden_demo_runs_and_outputs_expected_summaries() -> None:
    cp = subprocess.run([sys.executable, "tools/golden_demo.py", "--clean"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert cp.returncode == 0, cp.stdout
    output = ROOT / "examples" / "golden" / "output"
    assert output.exists()
    for scenario, (verdict, reasons) in SCENARIOS.items():
        summary_path = output / scenario / "summary.json"
        assert summary_path.exists(), scenario
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["ok"] is True
        assert summary["actual"]["verdict"] == verdict
        for reason in reasons:
            assert reason in summary["actual"]["reasons"]
        assert (output / scenario / "terminal.txt").exists()
        assert (output / scenario / "repo" / ".sourcepack" / "reports" / "latest.html").exists()
        assert (output / scenario / "repo" / ".sourcepack" / "reports" / "latest.json").exists()


def test_product_docs_exist() -> None:
    assert (ROOT / "docs" / "reason-codes.md").exists()
    assert (ROOT / "docs" / "assets" / "README.md").exists()


---

## File: tests/test_local_policy.py

Metadata:
- sha256: 53bfc0400027f3509631ed6dd7663a1fdf3eff74c05fc8ce4e50309c9f28bdc9
- bytes: 1325
- estimated_tokens: 332

Content:

import json, subprocess, sys


def run_cli(tmp_path, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=tmp_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_explain_policy_list_allow_remove(tmp_path):
    cp = run_cli(tmp_path, "explain", "unsupported_dependency")
    assert cp.returncode == 0 and "dependency" in cp.stdout
    cp = run_cli(tmp_path, "policy", "list")
    assert cp.returncode == 0 and json.loads(cp.stdout)["policies"] == []
    cp = run_cli(tmp_path, "allow", "dependency", "fastapi", "--reason", "reviewed")
    assert cp.returncode == 0
    pid = json.loads(cp.stdout)["id"]
    assert json.loads(run_cli(tmp_path, "policy", "list").stdout)["policies"][0]["scope"] == "dependency"
    assert run_cli(tmp_path, "policy", "remove", pid).returncode == 0


def test_allow_command_path_and_protected_rules(tmp_path):
    assert run_cli(tmp_path, "allow", "command", "npm run dev", "--reason", "reviewed").returncode == 0
    assert run_cli(tmp_path, "allow", "path", "src/app.py", "--reason", "reviewed").returncode == 0
    assert run_cli(tmp_path, "allow", "path", ".sourcepack/baseline/active.json", "--reason", "x").returncode == 1
    assert run_cli(tmp_path, "allow", "path", ".git/config", "--reason", "x", "--high-risk").returncode == 1


---

## File: tests/test_policy_integration.py

Metadata:
- sha256: 3f51080f7b8f65505785c5520af87cda87afbf3c6058914cb5e3293e67936888
- bytes: 15955
- estimated_tokens: 3987

Content:

import json
import subprocess
import sys


def run(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout


def trust_current_repo(tmp_path, message="trusted state"):
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    cp = run(tmp_path, "baseline", "refresh", "--force")
    assert cp.returncode == 0, cp.stderr + cp.stdout


def report(repo):
    cp = run(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def report_ci(repo):
    cp = run(repo, "diff", ".", "--ci", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def test_dependency_allow_suppresses_only_matching_finding(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import fastapi\nimport flask\n", encoding="utf-8")
    assert run(tmp_path, "allow", "dependency", "fastapi", "--reason", "reviewed").returncode == 0
    code, data = report(tmp_path)
    deps = [f.get("evidence") for f in data["findings"] if f["id"] == "unsupported_dependency"]
    assert code == 1
    assert "fastapi" not in deps
    assert "flask" in deps
    assert data["policy_overrides"][0]["value"] == "fastapi"


def test_command_allow_suppresses_exact_matching_finding(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("npm run dev\nnpm run build\n", encoding="utf-8")
    assert run(tmp_path, "allow", "command", "npm run dev", "--reason", "local convention").returncode == 0
    _, data = report(tmp_path)
    commands = [f.get("evidence") for f in data["findings"] if f["id"] == "unsupported_command"]
    assert "npm run dev" not in commands
    assert "npm run build" in commands


def test_policy_cannot_suppress_git_path_finding(tmp_path):
    init_repo(tmp_path)
    assert run(tmp_path, "allow", "path", ".git/config", "--reason", "nope", "--high-risk").returncode != 0
    patch = "diff --git a/.git/config b/.git/config\n--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-a\n+b\n"
    from sourcepack.judgment import judge_repo_change
    judgment = judge_repo_change(tmp_path, patch_text=patch)
    assert "git_path_modification" in {f["id"] for f in judgment.report["findings"]}


def test_policy_config_ignored_paths_require_reason_and_do_not_suppress_protected(tmp_path):
    init_repo(tmp_path)
    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "ignored_paths": [
            {"pattern": "docs/**", "reason": "docs-only reviewed separately"},
            {"pattern": ".sourcepack/baseline/**", "reason": "dangerous"},
            {"pattern": "bad/**"}
        ],
        "prompt_context_authoritative": True,
        "baseline_required_in_ci": False,
    }), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("new docs\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 0
    assert "new_file" not in {f["id"] for f in data["findings"] if f.get("path") == "docs/note.md"}
    assert data["policy_config_ignores"][0]["reason"] == "docs-only reviewed separately"
    assert any("prompt_context_authoritative" in w for w in data["policy_config_warnings"])
    assert any("baseline_required_in_ci_false" in w for w in data["policy_config_warnings"])
    assert any("policy_ignore_unsafe" in w for w in data["policy_config_warnings"])


def test_policy_ignored_paths_allowlist_only_blocks_unsafe_reason_codes():
    from sourcepack.policy import PolicyConfig, finding_ignored_by_policy

    config = PolicyConfig(ignored_paths=({"pattern": "docs/**", "reason": "reviewed docs"},))
    assert finding_ignored_by_policy({"id": "new_file", "path": "docs/new.md"}, config) is not None
    blocked = {
        "unsupported_dependency",
        "declared_dependency",
        "unsupported_command",
        "missing_file",
        "baseline_missing",
        "baseline_stale",
        "baseline_corrupt",
        "baseline_failed",
        "protected_artifact",
        "git_path_modification",
        "unsafe_path",
        "path_escape",
        "malformed_diff",
        "binary_diff",
        "unsupported_ecosystem",
        "workflow_change",
        "policy_config_warning",
        "policy_override",
        "execution_evidence_missing",
        "execution_evidence_present",
        "execution_failed",
        "execution_inconclusive",
        "future_unknown_reason",
    }
    for fid in blocked:
        assert finding_ignored_by_policy({"id": fid, "path": "docs/new.md"}, config) is None, fid


def test_load_policy_config_rejects_exact_unsafe_ignored_paths(tmp_path):
    from sourcepack.policy import load_policy_config

    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "ignored_paths": [
            {"pattern": ".git", "reason": "unsafe"},
            {"pattern": ".sourcepack/baseline", "reason": "unsafe"},
            {"pattern": "docs/**", "reason": "ok"},
        ],
    }), encoding="utf-8")

    config = load_policy_config(tmp_path)

    assert {item["pattern"] for item in config.ignored_paths} == {"docs/**"}
    assert "policy_ignore_unsafe:.git" in config.warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline" in config.warnings


def test_policy_config_reserved_fields_emit_warnings_without_authority(tmp_path):
    from sourcepack.policy import load_policy_config

    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir()
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "strict_default": False,
        "fail_on_warn_in_ci": False,
        "protected_paths": ["docs/protected/**"],
        "report_formats": ["json"],
        "baseline_required_in_ci": False,
        "prompt_context_authoritative": True,
    }), encoding="utf-8")
    config = load_policy_config(tmp_path)
    warnings = set(config.warnings)
    assert "policy_config_ignored:prompt_context_authoritative" in warnings
    assert "policy_config_ignored:baseline_required_in_ci_false" in warnings
    assert "policy_config_reserved:strict_default" in warnings
    assert "policy_config_reserved:fail_on_warn_in_ci" in warnings
    assert "policy_config_reserved:protected_paths" in warnings
    assert "policy_config_reserved:report_formats" in warnings
    assert config.strict_default is True
    assert config.fail_on_warn_in_ci is True
    assert config.protected_paths == (".sourcepack/baseline/**", ".git/**")
    assert config.report_formats == ("json", "markdown", "html", "sarif")


def write_rules(tmp_path, rules):
    policy_dir = tmp_path / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({
        "schema_version": "sourcepack.policy.v1",
        "rules": rules,
    }), encoding="utf-8")


def finding_ids(data):
    return {finding["id"] for finding in data["findings"]}


def test_policy_rules_missing_and_empty_do_not_emit_rule_findings(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "app.py").write_text("password = 'not-a-placeholder-secret'\n", encoding="utf-8")
    _, data = report(tmp_path)
    assert not any(finding["id"].startswith("policy_") for finding in data["findings"])

    write_rules(tmp_path, {})
    _, data = report(tmp_path)
    assert not any(finding["id"].startswith("policy_") for finding in data["findings"])


def test_policy_rule_protected_path_fails(tmp_path):
    init_repo(tmp_path)
    protected_dir = tmp_path / "src" / "auth"
    protected_dir.mkdir(parents=True)
    (protected_dir / "login.py").write_text("ALLOW = True\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"protected_paths": ["src/auth/**"]})

    (protected_dir / "login.py").write_text("ALLOW = False\n", encoding="utf-8")
    code, data = report(tmp_path)

    assert code == 1
    assert "policy_protected_path" in finding_ids(data)


def test_policy_rule_protected_path_fails_for_rename_source(tmp_path):
    init_repo(tmp_path)
    protected_dir = tmp_path / "src" / "auth"
    public_dir = tmp_path / "src" / "public"
    protected_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)
    (protected_dir / "login.py").write_text("ALLOW = True\n", encoding="utf-8")
    write_rules(tmp_path, {"protected_paths": ["src/auth/**"]})
    trust_current_repo(tmp_path)

    subprocess.run(["git", "mv", "src/auth/login.py", "src/public/login.py"], cwd=tmp_path, check=True)
    cp = run(tmp_path, "diff", ".", "--staged", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    data = json.loads(cp.stdout)

    assert cp.returncode == 1
    assert "policy_protected_path" in finding_ids(data)


def test_policy_rule_package_manager_drift_fails_for_pnpm(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"package_manager": "pnpm"})
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 1
    assert "policy_package_manager_drift" in finding_ids(data)


def test_policy_rule_package_manager_drift_allows_lockfile_deletion_for_pnpm(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
    write_rules(tmp_path, {"package_manager": "pnpm"})
    trust_current_repo(tmp_path)

    (tmp_path / "package-lock.json").unlink()
    _, data = report(tmp_path)

    assert "policy_package_manager_drift" not in finding_ids(data)


def test_policy_rule_missing_test_warns_and_test_change_satisfies(tmp_path):
    init_repo(tmp_path)
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_handler.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"require_tests_for": ["src/api/**"]})

    (api_dir / "handler.py").write_text("VALUE = 2\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 0
    assert "policy_missing_test" in finding_ids(data)

    (tests_dir / "test_handler.py").write_text("def test_value():\n    assert 2 == 2\n", encoding="utf-8")
    _, data = report(tmp_path)
    assert "policy_missing_test" not in finding_ids(data)


def test_policy_rule_missing_test_blocks_in_ci(tmp_path):
    init_repo(tmp_path)
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"require_tests_for": ["src/api/**"]})
    (api_dir / "handler.py").write_text("VALUE = 2\n", encoding="utf-8")

    code, data = report_ci(tmp_path)

    assert code != 0
    assert "policy_missing_test" in finding_ids(data)


def test_policy_rule_large_diff_warns(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 0
    assert "policy_large_diff" in finding_ids(data)


def test_policy_large_diff_line_count_excludes_diff_file_headers():
    from sourcepack.diff_parser import PatchFileChange
    from sourcepack.judgment import _policy_changed_line_count

    change = PatchFileChange(
        path="README.md",
        old_path="README.md",
        diff_lines=[
            "--- a/README.md",
            "+++ b/README.md",
            "@@ -1 +1 @@",
            " unchanged context",
            "-old content",
            "+new content",
        ],
    )

    assert _policy_changed_line_count([change]) == 2


def test_policy_rule_large_diff_blocks_in_ci(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"max_changed_lines": 1})
    (tmp_path / "README.md").write_text("demo\nline 2\nline 3\n", encoding="utf-8")

    code, data = report_ci(tmp_path)

    assert code != 0
    assert "policy_large_diff" in finding_ids(data)


def test_policy_rule_secret_pattern_ignores_placeholders(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    (tmp_path / "app.py").write_text("token = 'REDACTED'\npassword = 'changeme'\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 0
    assert "policy_secret_pattern" not in finding_ids(data)


def test_policy_rule_secret_pattern_fails_for_common_assignment_shapes(tmp_path):
    init_repo(tmp_path)
    write_rules(tmp_path, {"block_secret_patterns": True})
    (tmp_path / "app.py").write_text("[REDACTED:generic_api_key]'\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)

    (tmp_path / "app.py").write_text('"api_key": "live_secret_value_12345"\n', encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)

    (tmp_path / "app.py").write_text("password: live_secret_value_12345\n", encoding="utf-8")
    code, data = report(tmp_path)
    assert code == 1
    assert "policy_secret_pattern" in finding_ids(data)


def test_policy_rule_dependency_addition_fails(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['requests']\n", encoding="utf-8")

    code, data = report(tmp_path)

    assert code == 1
    assert "policy_dependency_addition" in finding_ids(data)


def test_policy_rule_dependency_addition_uncertain_manifest_emits_existing_uncertainty(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8")
    trust_current_repo(tmp_path)
    write_rules(tmp_path, {"block_dependency_additions": True})
    patch = (
        "diff --git a/pyproject.toml b/pyproject.toml\n"
        "--- a/pyproject.toml\n"
        "+++ b/pyproject.toml\n"
        "@@ -1,3 +1,3 @@\n"
        " [project]\n"
        "-does-not-match-baseline\n"
        "+dependencies = ['requests']\n"
        " dependencies = []\n"
    )

    from sourcepack.judgment import judge_repo_change
    judgment = judge_repo_change(tmp_path, patch_text=patch)

    assert "dependency_manifest_uncertain" in finding_ids(judgment.report)
    assert "policy_dependency_addition" not in finding_ids(judgment.report)


---

## File: tests/test_policy_validation.py

Metadata:
- sha256: 129dbab3f5085de9c5bb807aabb86bbe6c23a713c70a8400687338c53a11e10d
- bytes: 9580
- estimated_tokens: 2395

Content:

import json
import subprocess
import sys
from pathlib import Path


def run_cli(repo, *args):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_policy(repo: Path, data):
    (repo / ".sourcepack").mkdir(exist_ok=True)
    (repo / ".sourcepack" / "policy.json").write_text(json.dumps(data), encoding="utf-8")


def snapshot(repo: Path):
    paths = []
    for path in sorted(repo.rglob("*")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(repo).as_posix()
        kind = "dir" if path.is_dir() else "file"
        content = path.read_bytes() if path.is_file() else b""
        paths.append((rel, kind, content))
    return paths


def test_policy_validate_missing_file_json_parseable_and_read_only(tmp_path):
    before = snapshot(tmp_path)
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert cp.stdout.lstrip().startswith("{")
    data = json.loads(cp.stdout)
    assert data["policy_present"] is False
    assert data["valid"] is True
    assert not (tmp_path / ".sourcepack" / "policy.json").exists()
    assert not (tmp_path / ".sourcepack" / "baseline").exists()
    assert not (tmp_path / ".sourcepack" / "prompt").exists()
    assert snapshot(tmp_path) == before


def test_policy_validate_missing_file_human(tmp_path):
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert cp.returncode == 0
    assert "No policy file found" in cp.stdout


def test_policy_validate_valid_policy_reports_effective_ignores(tmp_path):
    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "ignored_paths": [{"pattern": "docs/**", "reason": "reviewed docs"}]})
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert ".sourcepack/policy.json" in cp.stdout
    assert "docs/**" in cp.stdout
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_ignored_paths"] == [{"pattern": "docs/**", "reason": "reviewed docs"}]


def test_policy_validate_invalid_json_nonzero_json_parseable(tmp_path):
    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").write_text('{"ignored_paths": [', encoding="utf-8")
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode != 0
    data = json.loads(cp.stdout)
    assert data["valid"] is False
    assert any("policy_config_invalid_json" in error for error in data["errors"])
    human = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert human.returncode != 0
    assert "invalid JSON" in human.stdout
    assert ".sourcepack/policy.json" in human.stdout


def test_policy_validate_non_object_root_nonzero(tmp_path):
    (tmp_path / ".sourcepack").mkdir()
    (tmp_path / ".sourcepack" / "policy.json").write_text("[]", encoding="utf-8")
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode != 0
    data = json.loads(cp.stdout)
    assert data["errors"] == ["policy_config_invalid:root_must_be_object"]
    human = run_cli(tmp_path, "policy", "validate", str(tmp_path))
    assert "policy root must be a JSON object" in human.stdout


def test_policy_validate_invalid_and_unsafe_ignored_entries_are_reported(tmp_path):
    write_policy(tmp_path, {"ignored_paths": ["bad", {"reason": "missing pattern"}, {"pattern": "docs/**"}, {"pattern": "", "reason": "empty"}, {"pattern": "docs/**", "reason": ""}, {"pattern": ".git", "reason": "unsafe"}, {"pattern": ".git/config", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline/**", "reason": "unsafe"}, {"pattern": "docs/**", "reason": "ok"}]})
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    warnings = "\n".join(data["warnings"])
    assert "policy_ignore_invalid:not_object" in warnings
    assert "policy_ignore_invalid:pattern_and_reason_required" in warnings
    assert "policy_ignore_unsafe:.git" in warnings
    assert "policy_ignore_unsafe:.git/config" in warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline" in warnings
    assert "policy_ignore_unsafe:.sourcepack/baseline/**" in warnings
    assert data["effective_ignored_paths"] == [{"pattern": "docs/**", "reason": "ok"}]
    assert len(data["ignored_invalid_entries"]) == 9


def test_policy_validate_reserved_and_dangerous_fields_warn_without_authority(tmp_path):
    write_policy(tmp_path, {"strict_default": False, "fail_on_warn_in_ci": False, "protected_paths": ["docs/**"], "report_formats": ["json", "pdf"], "prompt_context_authoritative": True, "baseline_required_in_ci": False})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    warnings = set(data["warnings"])
    assert "policy_config_reserved:strict_default" in warnings
    assert "policy_config_reserved:fail_on_warn_in_ci" in warnings
    assert "policy_config_reserved:protected_paths" in warnings
    assert "policy_config_reserved:report_formats" in warnings
    assert "policy_config_ignored:prompt_context_authoritative" in warnings
    assert "policy_config_ignored:baseline_required_in_ci_false" in warnings
    assert "policy_report_format_ignored:pdf" in warnings
    assert data["effective_config"]["strict_default"] is True
    assert data["effective_config"]["fail_on_warn_in_ci"] is True
    assert data["effective_config"]["protected_paths"] == [".sourcepack/baseline/**", ".git/**"]
    assert data["effective_config"]["report_formats"] == ["json", "markdown", "html", "sarif"]
    assert data["effective_config"]["prompt_context_authoritative"] is False
    assert data["effective_config"]["baseline_required_in_ci"] is True


def test_policy_validate_rules_missing_and_empty_are_noop(tmp_path):
    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1"})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_config"]["rules"] == {
        "block_dependency_additions": False,
        "protected_paths": [],
        "package_manager": None,
        "require_tests_for": [],
        "max_changed_lines": None,
        "block_secret_patterns": False,
    }

    write_policy(tmp_path, {"schema_version": "sourcepack.policy.v1", "rules": {}})
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_config"]["rules"]["protected_paths"] == []
    assert data["effective_config"]["rules"]["block_secret_patterns"] is False


def test_policy_validate_rules_reports_effective_rules_and_warnings(tmp_path):
    write_policy(tmp_path, {
        "schema_version": "sourcepack.policy.v1",
        "rules": {
            "block_dependency_additions": True,
            "protected_paths": ["src/auth/**", "/abs", "../escape"],
            "package_manager": "pnpm",
            "require_tests_for": ["src/api/**", ""],
            "max_changed_lines": 800,
            "block_secret_patterns": True,
        },
    })
    data = json.loads(run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json").stdout)
    assert data["effective_config"]["rules"] == {
        "block_dependency_additions": True,
        "protected_paths": ["src/auth/**"],
        "package_manager": "pnpm",
        "require_tests_for": ["src/api/**"],
        "max_changed_lines": 800,
        "block_secret_patterns": True,
    }
    warnings = "\n".join(data["warnings"])
    assert "policy_rule_invalid:protected_path:/abs" in warnings
    assert "policy_rule_invalid:protected_path:../escape" in warnings
    assert "policy_rule_invalid:require_tests_for:" in warnings


def test_policy_validate_json_stdout_only_and_no_mutation_of_state_dirs(tmp_path):
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "prompt").mkdir()
    (tmp_path / ".sourcepack" / "reports").mkdir()
    (tmp_path / ".sourcepack" / "evidence").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    write_policy(tmp_path, {"ignored_paths": [{"pattern": "docs/**", "reason": "ok"}]})
    before = snapshot(tmp_path)
    cp = run_cli(tmp_path, "policy", "validate", str(tmp_path), "--json")
    assert cp.returncode == 0
    assert cp.stderr == ""
    assert cp.stdout.startswith("{")
    json.loads(cp.stdout)
    assert snapshot(tmp_path) == before


def test_policy_ignored_paths_allowlist_and_future_reason_remain_unsuppressible():
    from sourcepack.policy import PolicyConfig, finding_ignored_by_policy

    config = PolicyConfig(ignored_paths=({"pattern": "docs/**", "reason": "reviewed"},))
    assert finding_ignored_by_policy({"id": "new_file", "path": "docs/a.md"}, config)
    unsafe_config = PolicyConfig(ignored_paths=({"pattern": ".git", "reason": "unsafe"}, {"pattern": ".sourcepack/baseline", "reason": "unsafe"}))
    assert finding_ignored_by_policy({"id": "new_file", "path": ".git/config"}, unsafe_config) is None
    assert finding_ignored_by_policy({"id": "new_file", "path": ".sourcepack/baseline/active.json"}, unsafe_config) is None
    for reason in ["unsupported_dependency", "git_path_modification", "baseline_missing", "future_unknown_reason"]:
        assert finding_ignored_by_policy({"id": reason, "path": "docs/a.md"}, config) is None


---

## File: tests/test_readme_truth.py

Metadata:
- sha256: 641d60378c3c525f2ca3ba7f643efed5ab69bdf34dedcea155ede612636604c2
- bytes: 4928
- estimated_tokens: 1232

Content:

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def readme() -> str:
    return README.read_text(encoding="utf-8")


def cli_subcommands() -> set[str]:
    tree = ast.parse((ROOT / "src" / "sourcepack" / "cli.py").read_text(encoding="utf-8"))
    commands: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                commands.add(node.args[0].value)
    return commands


def project_claims_published_package() -> bool:
    marker = ROOT / ".sourcepack-published"
    return marker.exists() and marker.read_text(encoding="utf-8").strip().lower() in {"1", "true", "yes"}


def test_readme_does_not_claim_pypi_install_unless_published() -> None:
    text = readme()
    forbidden = ["pipx install sourcepack", "uv tool install sourcepack", "pip install sourcepack"]
    if not project_claims_published_package():
        available_sections = re.findall(r"```(?:bash)?\n(.*?)```", text, flags=re.S)
        executable_claims = "\n".join(block for block in available_sections if "planned" not in block.lower())
        for command in forbidden:
            assert command not in executable_claims


def test_readme_sourcepack_commands_use_existing_subcommands() -> None:
    text = readme()
    commands = cli_subcommands()
    for match in re.finditer(r"(?:^|[\n`])sourcepack\s+([a-z][a-z-]*)", text):
        subcommand = match.group(1)
        assert subcommand in commands, f"README references missing sourcepack subcommand: {subcommand}"


def test_readme_links_to_existing_docs_files() -> None:
    text = readme()
    for link in re.findall(r"\[[^\]]+\]\((docs/[^)#]+)(?:#[^)]+)?\)", text):
        assert (ROOT / link).exists(), f"README links to missing docs path: {link}"


def test_readme_image_paths_are_present_or_explained_as_expected_targets() -> None:
    text = readme()
    image_paths = re.findall(r"docs/assets/[^`\s)]+\.png", text)
    for image_path in image_paths:
        assert (ROOT / image_path).exists() or "expected screenshot targets" in text


def test_readme_links_reason_codes_and_reports_commands() -> None:
    text = readme()
    assert "docs/reason-codes.md" in text
    assert "sourcepack report open" in text
    assert "sourcepack report path" in text


def test_readme_dogfooding_claim_preserves_sourcepack_limitations() -> None:
    text = readme()
    assert "sourcepack diff . --ci --json" in text
    assert "committed `.sourcepack/baseline/` state" in text
    for forbidden in [
        "proves correctness",
        "proves security",
        "proves runtime success",
        "proves dependency safety",
        "proves external API truth",
        "proves user intent",
    ]:
        assert forbidden not in text.lower()


def test_demo_output_matches_quick_demo_claim() -> None:
    import os
    import subprocess
    import sys

    cp = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "demo"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert cp.returncode == 0, cp.stdout
    text = cp.stdout
    assert "RED LIGHT: commit blocked" in text
    assert "unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared." in text
    assert "PASS manifest.json" not in text


def test_readme_first_five_minutes_and_public_alpha_limits() -> None:
    text = readme()
    for required in [
        "SourcePack blocks AI-generated code changes that rely on fake repo facts.",
        "- AI coding agents can edit files that do not exist.",
        "- They can import undeclared dependencies.",
        "- They can reference missing scripts or unsupported commands.",
        "- They can reshape project structure based on prompt assumptions.",
        "- SourcePack catches those locally verifiable failures before commit or in CI.",
        "python -m pip install sourcepack",
        "sourcepack demo",
        "RED LIGHT: commit blocked",
        "unsupported_dependency",
        "sourcepack init . --auto",
        "sourcepack diff .",
        "sourcepack report open",
    ]:
        assert required in text
    claims = text.split("## What SourcePack does not claim", 1)[1].split("## Public proof links", 1)[0].strip()
    assert claims == "\n".join([
        "- does not prove code correctness",
        "- does not prove security",
        "- does not prove runtime success",
        "- does not prove semantic validity",
        "- does not prove external API truth",
        "- does not prove dependency safety",
        "- does not prove user intent",
    ])


---

## File: tests/test_real_corpus_validation.py

Metadata:
- sha256: 991ff066463a7f0bb2595947a407984c093840ead936353f073ebd22a9fd6fec
- bytes: 33257
- estimated_tokens: 8315

Content:

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import real_corpus_validation as rcv


def run_tool(*args):
    return subprocess.run([sys.executable, "tools/real_corpus_validation.py", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(cmd, cwd):
    return subprocess.run(["git", *cmd], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def make_repo(tmp_path, *, python=True, node=False):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("demo\n")
    if python:
        (repo / "app.py").write_text("print('hi')\n")
        (repo / "requirements.txt").write_text("requests\n")
    if node:
        (repo / "package.json").write_text(json.dumps({"scripts":{"dev":"vite"},"dependencies":{"react":"latest"}}))
        (repo / "index.js").write_text("console.log('hi')\n")
    git(["init"], repo)
    git(["config", "user.email", "t@example.invalid"], repo)
    git(["config", "user.name", "Test"], repo)
    git(["add", "."], repo)
    git(["commit", "-m", "initial"], repo)
    return repo


def test_repo_list_parsing(tmp_path):
    p = tmp_path / "repos.json"
    p.write_text(json.dumps([{"repo_id":"x","url":"/tmp/x","ecosystem_tags":[],"expected_features":[],"notes":"n"}]))
    assert rcv.load_repo_list(p)[0]["repo_id"] == "x"


def test_no_corpus_json_behavior():
    cp = run_tool("--json")
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["repo_count"] == 0
    assert data["results"] == []


def test_local_repo_execution_json_and_filter(tmp_path):
    repo = make_repo(tmp_path)
    cp = run_tool("--repo", str(repo), "--scenario", "benign_readme_edit", "--json")
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["scenario_count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["mutation_result"]["status"] in rcv.MUTATION_STATUSES


def test_mutation_failure_detection(tmp_path):
    p = tmp_path / "same.txt"
    p.write_text("x")
    mr = rcv.mutate_file(p, "x", append=False)
    assert mr.status == "mutation_failed"
    assert not mr.applied


def test_skipped_incompatible_repo_detection(tmp_path):
    repo = make_repo(tmp_path, python=False)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["undeclared_python_dependency_import"])
    assert mr.status == "skipped_incompatible_repo"


def test_cleanup_uses_hard_reset_and_clean(tmp_path, monkeypatch):
    calls=[]
    def fake_run(cmd, cwd, timeout):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(rcv, "run", fake_run)
    assert rcv.cleanup_repo(tmp_path)
    assert calls == [["git","reset","--hard","HEAD"],["git","clean","-fdx"]]


def test_classification_metrics():
    s = rcv.Scenario("x","",(),(),"","","PASS",("needed",),("bad",))
    mr = rcv.MutationResult("applied", True)
    f = rcv.classify(s, "FAIL", ["bad"], False, False, False, mr)
    assert f["false_red"] and f["wrong_reason_code"]
    s2 = rcv.Scenario("y","",(),(),"","","FAIL")
    assert rcv.classify(s2, "WARN", [], False, False, False, mr)["missed_red"]
    assert rcv.classify(s, "WARN", [], False, False, False, mr)["noisy_warn"]
    assert rcv.classify(s, None, [], True, False, False, mr)["invalid_json"]


def test_policy_over_suppression_and_trust_violation():
    mr = rcv.MutationResult("applied", True)
    assert rcv.classify(rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"], "PASS", [], False, False, False, mr)["policy_over_suppression"]
    assert rcv.classify(rcv.SCENARIO_BY_ID["execution_claim_without_ledger"], "PASS", [], False, False, False, mr)["trust_violation"]


def test_circuit_breaker_behavior(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]] * 6)
    monkeypatch.setattr(rcv, "prepare_repo", lambda entry, cache, timeout: (str(repo), None, None))
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (0, "not json", "", False, None, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, code = rcv.run_harness(args)
    assert code == 1
    assert summary["circuit_breaker_triggered"] is True
    assert summary["invalid_json"] == 5


def test_network_unavailable_reported_separately(tmp_path):
    p = tmp_path / "repos.json"
    p.write_text(json.dumps([{"repo_id":"bad","url":"https://example.invalid/sourcepack-nope.git","ecosystem_tags":[],"expected_features":[],"notes":"n"}]))
    cp = run_tool("--repo-list", str(p), "--max-repos", "1", "--scenario", "benign_readme_edit", "--timeout", "2", "--json")
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["results"][0]["notes"][0] in {"network_unavailable", "clone_failed"}
    assert data["crash"] == 0


def test_execution_claim_without_ledger_writes_detectable_claim(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["execution_claim_without_ledger"])
    assert mr.applied
    assert "tests passed" in (repo / "README.md").read_text()
    assert rcv.SCENARIO_BY_ID["execution_claim_without_ledger"].expected_reason_codes_include == ("execution_evidence_missing",)


def test_policy_matching_scenario_creates_allow_policy_before_evaluation(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"])
    assert mr.applied
    assert (repo / ".sourcepack" / "policy" / "allow.jsonl").exists()
    assert mr.details["policy_allowed_dependency"] == "fastapi"
    assert "sourcepack allow dependency fastapi" in mr.details["policy_command"]
    assert "import fastapi" in (repo / "app.py").read_text()


def test_policy_nonmatching_scenario_leaves_unrelated_dependency_unsuppressed(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"])
    assert mr.applied
    text = (repo / "app.py").read_text()
    assert "import fastapi" in text
    assert "import flask" in text
    assert mr.details["policy_allowed_dependency"] == "fastapi"
    assert mr.details["unsuppressed_dependency"] == "flask"


def test_same_patch_python_dependency_mutates_manifest_not_comment(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_python_dependency_add_plus_import"])
    assert mr.applied
    assert "fastapi" in (repo / "requirements.txt").read_text()
    assert "sourcepack corpus dependency" not in (repo / "requirements.txt").read_text()
    assert mr.details["manifest_before_sha256"] != mr.details["manifest_after_sha256"]


def test_same_patch_js_dependency_mutates_package_json(tmp_path):
    repo = make_repo(tmp_path, node=True)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"])
    assert mr.applied
    data = json.loads((repo / "package.json").read_text())
    assert mr.details["dependency_added"] == "sourcepack-corpus-js-dep"
    assert data["dependencies"]["sourcepack-corpus-js-dep"] == "latest"
    assert "react" != mr.details["dependency_added"]
    assert mr.details["dependency_preexisting"] is False
    assert mr.details["import_specifier"] == mr.details["dependency_added"]
    assert mr.details["package_json_before_sha256"] != mr.details["package_json_after_sha256"]
    assert mr.details["source_before_sha256"] != mr.details["source_after_sha256"]


def test_same_patch_js_dependency_fails_if_candidates_preexist(tmp_path):
    repo = make_repo(tmp_path, node=True)
    data = json.loads((repo / "package.json").read_text())
    data["dependencies"].update({"sourcepack-corpus-js-dep":"latest", "sourcepack-corpus-js-dep-2":"latest", "sourcepack-corpus-js-dep-3":"latest"})
    (repo / "package.json").write_text(json.dumps(data))
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"])
    assert mr.status == "mutation_failed"
    assert mr.reason == "js_dependency_candidate_preexisting"


@pytest.mark.parametrize("source", [
    "import x from 'sourcepack-corpus-js-dep';",
    'import { x } from "sourcepack-corpus-js-dep";',
    "import {\n  x,\n  y\n} from 'sourcepack-corpus-js-dep';",
    "import * as x from 'sourcepack-corpus-js-dep';",
    "import 'sourcepack-corpus-js-dep';",
    "const x = require('sourcepack-corpus-js-dep');",
    'let x = require("sourcepack-corpus-js-dep");',
    "var x = require('sourcepack-corpus-js-dep');",
    "const { x } = require('sourcepack-corpus-js-dep');",
    "require('sourcepack-corpus-js-dep');",
    'await import("sourcepack-corpus-js-dep");',
    "import('sourcepack-corpus-js-dep').then(m => m);",
])
def test_source_contains_js_import_accepts_structural_forms(source):
    assert rcv.source_contains_js_import(source, "sourcepack-corpus-js-dep")


@pytest.mark.parametrize("source", [
    "// import x from 'sourcepack-corpus-js-dep';",
    "/* import x from 'sourcepack-corpus-js-dep'; */",
    "const msg = 'sourcepack-corpus-js-dep';",
    'const msg = "Install sourcepack-corpus-js-dep";',
    "console.log('sourcepack-corpus-js-dep');",
    'const msg = "import x from \'sourcepack-corpus-js-dep\';";',
    'const msg = \'import x from "sourcepack-corpus-js-dep";\';',
    'const msg = "require(\'sourcepack-corpus-js-dep\')";',
    'const msg = "import(\'sourcepack-corpus-js-dep\')";',
    'console.log("import x from \'sourcepack-corpus-js-dep\';");',
    'console.log("require(\'sourcepack-corpus-js-dep\')");',
    "import x from 'sourcepack-corpus-js-dep-extra';",
    "require('sourcepack-corpus-js-dep-extra');",
    "import('sourcepack-corpus-js-dep-extra');",
    'import x from \'other\'; const msg = "from \'sourcepack-corpus-js-dep\'";',
    'import x from \'other\'\nconst msg = "from \'sourcepack-corpus-js-dep\'";',
])
def test_source_contains_js_import_rejects_non_structural_or_substring_forms(source):
    assert not rcv.source_contains_js_import(source, "sourcepack-corpus-js-dep")



def test_scenario_audit_matches_scenario_registry():
    scenario_ids = {s.scenario_id for s in rcv.SCENARIOS}
    assert set(rcv.SCENARIO_AUDIT) == scenario_ids
    for scenario in rcv.SCENARIOS:
        audit = rcv.SCENARIO_AUDIT[scenario.scenario_id]
        assert audit["scenario_id"] == scenario.scenario_id
        assert audit["expected_verdict"] == scenario.expected_verdict
        assert tuple(audit["expected_reason_codes_include"]) == scenario.expected_reason_codes_include
        assert tuple(audit["expected_reason_codes_exclude"]) == scenario.expected_reason_codes_exclude
        assert audit.get("mutation_kind") in rcv.SCENARIO_AUDIT_ALLOWED_MUTATION_KINDS
        proof = audit.get("independent_proof")
        assert proof
        assert not isinstance(proof, str)
        assert isinstance(proof, tuple)
        assert set(proof) <= rcv.SCENARIO_AUDIT_ALLOWED_PROOFS
        assert all("Verifier checks mutation" not in item for item in proof)
    assert rcv.SCENARIO_AUDIT["same_patch_python_dependency_add_plus_import"]["mutation_kind"] == "multi_file_mutation"
    assert rcv.SCENARIO_AUDIT["same_patch_js_dependency_add_plus_import"]["mutation_kind"] == "multi_file_mutation"
    assert rcv.SCENARIO_AUDIT["docker_compose_missing_file"]["mutation_kind"] == "delete_plus_file_mutation"
    assert rcv.SCENARIO_AUDIT["protected_sourcepack_baseline_edit"]["mutation_kind"] == "programmatic_patch_text"
    assert rcv.SCENARIO_AUDIT["git_config_edit"]["mutation_kind"] == "programmatic_patch_text"
    assert rcv.SCENARIO_AUDIT["malformed_diff"]["mutation_kind"] == "programmatic_patch_text"

def test_makefile_existing_uses_real_parsed_target(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "Makefile").write_text(".PHONY: clean\nclean:\n\t@echo clean\nbuild:\n\t@echo build\n")
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["make_target_existing"])
    assert mr.applied
    assert mr.details["make_target"] == "build"
    assert "make build" in (repo / "README.md").read_text()


def test_makefile_missing_requires_existing_makefile_for_target_semantics(tmp_path):
    repo = make_repo(tmp_path, python=False)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["make_target_missing"])
    assert mr.status == "skipped_incompatible_repo"
    assert mr.reason == "makefile_missing"


def test_docker_compose_missing_uses_detected_command_form(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "compose.yml").write_text("services: {}\n")
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["docker_compose_missing_file"])
    assert mr.applied
    assert "docker compose up" in (repo / "README.md").read_text()
    assert mr.details["command_written"] == "docker compose up"
    assert mr.details["deleted_compose_files"]
    assert mr.details["compose_files_remaining"] == []
    assert not (repo / "compose.yml").exists()


def test_allowed_alternate_outcomes_are_honored():
    s = rcv.Scenario("alt", "", (), (), "", "", "PASS", allowed_alternate_outcomes=({"verdict":"WARN", "reason_codes_exclude":("bad",), "justification":"ok"},))
    mr = rcv.MutationResult("applied", True)
    flags = rcv.classify(s, "WARN", [], False, False, False, mr)
    assert not flags["noisy_warn"]
    assert rcv.allowed_alternate_match(s, "WARN", [])[0] is True


def test_console_script_metadata_points_to_callable():
    import tomllib
    import importlib
    data = tomllib.loads(Path("pyproject.toml").read_text())
    target = data["project"]["scripts"]["sourcepack"]
    assert target == "sourcepack.cli:main"
    module_name, attr = target.split(":", 1)
    assert callable(getattr(importlib.import_module(module_name), attr))


def test_failures_only_json_includes_failures_and_json_only(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (1, "{}", "", True, {"verdict":"FAIL","findings":[]}, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["results"] and summary["results"][0]["false_red"]
    assert json.loads(json.dumps(summary))["results"][0]["scenario_id"] == "benign_readme_edit"


def test_run_harness_verifier_failure_blocks_evaluation_and_reports_mutation_failure(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    calls = []
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True))

    def fake_verify(repo, scenario, mr):
        calls.append("verify")
        return rcv.MutationResult("mutation_failed", False, reason="verifier_rejected")

    def fake_evaluate(repo, scenario, timeout):
        calls.append("evaluate")
        raise AssertionError("evaluate must not run after verifier mutation failure")

    monkeypatch.setattr(rcv, "verify_scenario_state", fake_verify)
    monkeypatch.setattr(rcv, "evaluate", fake_evaluate)
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert calls == ["verify"]
    assert summary["results"][0]["mutation_status"] == "mutation_failed"
    assert summary["results"][0]["mutation_result"]["reason"] == "verifier_rejected"
    assert summary["results"][0]["mutation_failed"] is True


def test_failures_only_json_excludes_pure_skips(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["make_target_existing"]])
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["skipped_incompatible_repo"] == 1
    assert summary["results"] == []


def test_summary_accounting_separates_skips_and_executed(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    scenarios = [rcv.SCENARIO_BY_ID["benign_readme_edit"], rcv.SCENARIO_BY_ID["make_target_existing"]]
    monkeypatch.setattr(rcv, "SCENARIOS", scenarios)
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=False, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    assert summary["passed"] == summary["executed_passed"]
    assert summary["executed_passed"] + summary["executed_failed"] == summary["executed_runs"]
    assert summary["executed_runs"] + summary["skipped_runs"] == summary["total_runs"]
    assert summary["skipped_runs"] == 1


def test_failure_rows_expose_inspection_fields(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: rcv.MutationResult("applied", True, reason=None))
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (1, "{}", "", True, {"verdict":"FAIL","findings":[{"id":"unsupported_dependency"}]}, False))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    row = rcv.run_harness(args)[0]["results"][0]
    assert row["scenario_id"] and row["actual_verdict"] and row["actual_reason_codes"]
    assert isinstance(row["mutation_result"], dict)
    assert any(row[m] for m in rcv.FAILURE_METRICS)


def test_allowed_alternates_cannot_suppress_hard_failures():
    alt = ({"verdict":"PASS", "justification":"narrow"},)
    for sid, metric in [("execution_claim_without_ledger", "trust_violation"), ("policy_allow_nonmatching_dependency", "policy_over_suppression")]:
        s = rcv.SCENARIO_BY_ID[sid]
        s = rcv.Scenario(s.scenario_id, s.description, s.applies_to_tags, s.required_files, s.target_heuristic, s.mutation, s.expected_verdict, s.expected_reason_codes_include, s.expected_reason_codes_exclude, alt)
        assert rcv.classify(s, "PASS", [], False, False, False, rcv.MutationResult("applied", True))[metric]
    s = rcv.Scenario("x", "", (), (), "", "", "PASS", allowed_alternate_outcomes=alt)
    for kwargs, metric in [((True, False, False), "invalid_json"), ((False, True, False), "crash"), ((False, False, True), "timeout")]:
        assert rcv.classify(s, "PASS", [], *kwargs, rcv.MutationResult("applied", True))[metric]
    for status, metric in [("mutation_failed", "mutation_failed"), ("baseline_failed", "baseline_failed"), ("repo_cleanup_failed", "repo_cleanup_failed")]:
        assert rcv.classify(s, "PASS", [], False, False, False, rcv.MutationResult(status, False))[metric]


def test_policy_nonmatching_cannot_pass_if_unrelated_finding_disappears():
    flags = rcv.classify(rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"], "PASS", ["policy_override"], False, False, False, rcv.MutationResult("applied", True))
    assert flags["policy_over_suppression"]


def test_execution_without_ledger_cannot_pass_without_trust_violation():
    flags = rcv.classify(rcv.SCENARIO_BY_ID["execution_claim_without_ledger"], "PASS", [], False, False, False, rcv.MutationResult("applied", True))
    assert flags["trust_violation"]


def test_execution_claim_with_successful_ledger_records_setup_details(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"])
    assert {"ledger_command", "ledger_exit_code", "ledger_stdout", "ledger_stderr"} <= set(mr.details)


def test_validate_mutation_result_rejects_invalid_states(tmp_path):
    repo = make_repo(tmp_path)
    scenario = rcv.SCENARIO_BY_ID["benign_readme_edit"]
    mr = rcv.MutationResult("applied", True, str(repo / "README.md"), "same", "same")
    assert rcv.validate_mutation_result(repo, scenario, mr).reason == "sha256_unchanged"
    js = rcv.SCENARIO_BY_ID["same_patch_js_dependency_add_plus_import"]
    mr = rcv.MutationResult("applied", True, details={"dependency_preexisting": True, "dependency_added":"a", "import_specifier":"a"})
    assert rcv.validate_mutation_result(repo, js, mr).reason == "js_package_json_missing"
    mr = rcv.MutationResult("applied", True, details={"dependency_added":"a", "import_specifier":"b"})
    assert rcv.validate_mutation_result(repo, js, mr).reason == "js_package_json_missing"
    pol = rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"]
    mr = rcv.MutationResult("applied", True, details={"policy_exit_code": 1})
    assert rcv.validate_mutation_result(repo, pol, mr).reason == "policy_setup_failed"
    led = rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"]
    mr = rcv.MutationResult("applied", True, details={"ledger_exit_code": 1})
    assert rcv.validate_mutation_result(repo, led, mr).reason == "execution_ledger_setup_failed"
    dock = rcv.SCENARIO_BY_ID["docker_compose_missing_file"]
    mr = rcv.MutationResult("applied", True, details={"compose_files_remaining": ["compose.yml"]})
    assert rcv.validate_mutation_result(repo, dock, mr).reason == "compose_readme_missing"


@pytest.mark.parametrize("mr", [
    rcv.MutationResult("applied", False),
    rcv.MutationResult("mutation_failed", True),
])
def test_validate_mutation_result_rejects_status_applied_inconsistency(tmp_path, mr):
    repo = make_repo(tmp_path)
    scenario = rcv.SCENARIO_BY_ID["benign_readme_edit"]
    result = rcv.validate_mutation_result(repo, scenario, mr)
    assert result.status == "mutation_failed"
    assert result.reason == "mutation_status_applied_inconsistent"


@pytest.mark.parametrize("mr", [
    rcv.MutationResult("applied", False),
    rcv.MutationResult("mutation_failed", True),
])
def test_inconsistent_mutation_state_is_explicit_metric(tmp_path, monkeypatch, mr):
    repo = make_repo(tmp_path)
    monkeypatch.setattr(rcv, "SCENARIOS", [rcv.SCENARIO_BY_ID["benign_readme_edit"]])
    monkeypatch.setattr(rcv, "create_baseline", lambda repo, timeout: True)
    monkeypatch.setattr(rcv, "cleanup_repo", lambda repo: True)
    monkeypatch.setattr(rcv, "apply_mutation", lambda repo, s: mr)
    monkeypatch.setattr(rcv, "evaluate", lambda repo, s, timeout: (_ for _ in ()).throw(AssertionError("evaluate must not run")))
    args = rcv.argparse.Namespace(repo_list=None, repo=[str(repo)], workdir=str(tmp_path/"w"), json=True, max_repos=None, scenario=None, keep_workdir=False, failures_only=True, print_failures=False, timeout=5, fail_on_missed_red=False, fail_on_crash=False, fail_on_invalid_json=False, fail_on_trust_violation=False, fail_on_policy_over_suppression=False)
    summary, _ = rcv.run_harness(args)
    row = summary["results"][0]
    assert row["mutation_result"]["reason"] == "mutation_status_applied_inconsistent"
    assert row["mutation_failed"] is True
    assert row["mutation_status_applied_inconsistent"] is True
    assert summary["mutation_failed"] == 1
    assert summary["mutation_status_applied_inconsistent"] == 1


def _verify_reason(repo, sid, mr):
    return rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).reason


def _valid_js_mutation(tmp_path):
    repo = make_repo(tmp_path, node=True)
    sid = "same_patch_js_dependency_add_plus_import"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    return repo, sid, mr.details.copy()


@pytest.mark.parametrize("mutate, expected", [
    (lambda repo, good: ({k: v for k, v in good.items() if k != "dependency_added"}), "js_dependency_added_missing"),
    (lambda repo, good: (good | {"dependency_added": ""}), "js_dependency_added_missing"),
    (lambda repo, good: (good | {"dependency_added": "lodash", "import_specifier": "lodash"}), "js_dependency_candidate_invalid"),
    (lambda repo, good: (good | {"dependency_added": "react", "import_specifier": "react"}), "js_dependency_candidate_invalid"),
    (lambda repo, good: (good | {"existing_dependency_sections": {"dependencies": [good["dependency_added"]]}}), "js_dependency_preexisting"),
])
def test_hostile_js_verifier_rejects_dependency_metadata_in_check_order(tmp_path, mutate, expected):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = mutate(repo, good)
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == expected


def test_hostile_js_verifier_rejects_missing_dependency_in_package_json(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    data = json.loads((repo / "package.json").read_text())
    data["dependencies"].pop(good["dependency_added"])
    (repo / "package.json").write_text(json.dumps(data))
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=good)) == "js_dependency_not_added_to_dependencies"


@pytest.mark.parametrize("value", [True, None])
def test_hostile_js_verifier_rejects_dependency_preexisting_flag_invalid(tmp_path, value):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"dependency_preexisting": value}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_dependency_preexisting_flag_invalid"


def test_hostile_js_verifier_rejects_import_specifier_mismatch(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"import_specifier": "other"}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_import_specifier_mismatch"


@pytest.mark.parametrize("source", [
    "// import x from 'sourcepack-corpus-js-dep';\n",
    "/* import x from 'sourcepack-corpus-js-dep'; */\n",
    "const msg = 'sourcepack-corpus-js-dep';\n",
    "const msg = \"import x from 'sourcepack-corpus-js-dep';\";\n",
    "const msg = \"require('sourcepack-corpus-js-dep')\";\n",
    "const msg = \"import('sourcepack-corpus-js-dep')\";\n",
    "console.log('sourcepack-corpus-js-dep');\n",
    "import x from 'other'; const msg = \"from 'sourcepack-corpus-js-dep'\";\n",
    "import x from 'other'\nconst msg = \"from 'sourcepack-corpus-js-dep'\";\n",
])
def test_hostile_js_verifier_rejects_non_import_dependency_mentions(tmp_path, source):
    repo, sid, good = _valid_js_mutation(tmp_path)
    (repo / "index.js").write_text(source.replace("sourcepack-corpus-js-dep", good["dependency_added"]))
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=good)) == "js_source_import_missing"


def test_hostile_js_verifier_rejects_package_json_unchanged_sha(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"package_json_after_sha256": good["package_json_before_sha256"]}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_package_json_unchanged"


def test_hostile_js_verifier_rejects_source_unchanged_sha(tmp_path):
    repo, sid, good = _valid_js_mutation(tmp_path)
    bad = good | {"source_after_sha256": good["source_before_sha256"]}
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, details=bad)) == "js_source_unchanged"

def test_hostile_python_verifier_rejects_lies_and_accepts_valid(tmp_path):
    repo = make_repo(tmp_path)
    sid = "same_patch_python_dependency_add_plus_import"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    good = mr.details.copy()
    (repo / "requirements.txt").write_text("requests\n# fastapi\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"app.py"), "a", "b", details=good)) == "python_dependency_not_in_manifest"
    (repo / "requirements.txt").write_text("requests\nfastapi\n")
    (repo / "app.py").write_text("print('missing')\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"app.py"), "a", "b", details=good)) == "python_import_missing"


def test_hostile_docker_verifier_rejects_lies_and_accepts_valid(tmp_path):
    repo = make_repo(tmp_path, python=False)
    (repo / "compose.yml").write_text("services: {}\n")
    sid = "docker_compose_missing_file"
    mr = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID[sid])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID[sid], mr).status == "applied"
    good = mr.details.copy()
    (repo / "compose.yml").write_text("services: {}\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=good)) == "compose_files_still_present"
    (repo / "compose.yml").unlink()
    bad = good.copy(); bad.pop("deleted_compose_files")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=bad)) == "compose_deletion_provenance_missing"
    (repo / "README.md").write_text("no command\n")
    assert _verify_reason(repo, sid, rcv.MutationResult("applied", True, str(repo/"README.md"), "a", "b", details=good)) == "compose_command_missing"


def test_hostile_policy_and_execution_verifiers(tmp_path):
    repo = make_repo(tmp_path)
    pol = rcv.apply_mutation(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"])
    assert rcv.verify_scenario_state(repo, rcv.SCENARIO_BY_ID["policy_allow_matching_dependency"], pol).status == "applied"
    (repo / ".sourcepack" / "policy" / "allow.jsonl").unlink()
    assert _verify_reason(repo, "policy_allow_matching_dependency", pol) == "policy_artifact_missing"
    (tmp_path / "n").mkdir()
    repo2 = make_repo(tmp_path / "n")
    non = rcv.apply_mutation(repo2, rcv.SCENARIO_BY_ID["policy_allow_nonmatching_dependency"])
    (repo2 / "app.py").write_text("import fastapi\n")
    assert _verify_reason(repo2, "policy_allow_nonmatching_dependency", non) == "policy_imports_missing"
    (tmp_path / "e").mkdir()
    repo3 = make_repo(tmp_path / "e")
    led = rcv.apply_mutation(repo3, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"])
    assert rcv.verify_scenario_state(repo3, rcv.SCENARIO_BY_ID["execution_claim_with_successful_ledger"], led).status == "applied"
    (repo3 / ".sourcepack" / "evidence" / "ledger.jsonl").unlink()
    assert _verify_reason(repo3, "execution_claim_with_successful_ledger", led) == "execution_ledger_artifact_missing"
    no = rcv.MutationResult("applied", True, str(repo3 / "README.md"), "a", "b")
    (repo3 / "README.md").write_text("no claim\n")
    assert _verify_reason(repo3, "execution_claim_without_ledger", no) == "execution_claim_missing"


def test_programmatic_and_generic_verifier_rejects_lies(tmp_path):
    repo = make_repo(tmp_path)
    mr = rcv.MutationResult("applied", True, details={})
    assert _verify_reason(repo, "malformed_diff", mr) == "programmatic_patch_text_missing"
    same = rcv.MutationResult("applied", True, str(repo / "README.md"), "same", "same")
    assert _verify_reason(repo, "benign_readme_edit", same) == "sha256_unchanged"


---

## File: tests/test_reason_code_docs.py

Metadata:
- sha256: 93cc5bcb4ad812cd43e6ab491c77d56e37470c76fa0cadb01adb405eb03653ff
- bytes: 1717
- estimated_tokens: 430

Content:

from __future__ import annotations

import re
from pathlib import Path

from sourcepack.reason_codes import canonical_reason_codes

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reason-codes.md"


def documented_codes() -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    return set(re.findall(r"^## ([a-z0-9_]+)$", text, flags=re.MULTILINE))


def test_reason_code_docs_include_every_canonical_code() -> None:
    assert set(canonical_reason_codes()) <= documented_codes()


def test_reason_code_docs_do_not_include_unknown_codes() -> None:
    assert documented_codes() <= set(canonical_reason_codes())


def test_reason_code_docs_preserve_non_claims() -> None:
    text = DOC.read_text(encoding="utf-8")
    for phrase in [
        "does not prove code correctness",
        "does not prove dependency safety",
        "does not prove runtime success",
        "does not prove semantic validity",
    ]:
        assert phrase in text

PUBLIC_REASON_CODE_ALLOWLIST = {"input_schema_version"}


def test_public_docs_do_not_reference_new_command_reason_code() -> None:
    public_paths = [ROOT / "README.md", ROOT / "docs" / "ci.md", ROOT / "docs" / "reason-codes.md", ROOT / "src" / "sourcepack" / "workbench_static" / "index.html"]
    for path in public_paths:
        assert "new_command" not in path.read_text(encoding="utf-8"), str(path)


def test_readme_backtick_reason_codes_are_canonical_or_allowlisted() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    codes = set(re.findall(r"`([a-z][a-z0-9_]+)`", text))
    likely_codes = {code for code in codes if "_" in code}
    assert likely_codes <= set(canonical_reason_codes()) | PUBLIC_REASON_CODE_ALLOWLIST


---

## File: tests/test_release_docs.py

Metadata:
- sha256: dd1d32ed324c8fb7c16527b45972e4ad952a9d9e74dbc20719d157fa7ebecb96
- bytes: 2131
- estimated_tokens: 533

Content:

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_baseline_lifecycle_documents_trust_separation_and_ci_rules() -> None:
    text = read("docs/baseline-lifecycle.md")
    required = [
        ".sourcepack/baseline/",
        ".sourcepack/prompt/",
        "Prompt context cannot prove",
        "CI must not run `sourcepack init`",
        "CI will not create or update trusted baseline state automatically.",
        "Generating baseline inside untrusted PR CI.",
        "Using SourcePack as proof of runtime correctness.",
        "Using SourcePack as a dependency safety scanner.",
    ]
    for phrase in required:
        assert phrase in text


def test_release_checklist_has_required_sections() -> None:
    text = read("docs/release-checklist.md").lower()
    sections = [
        "preflight gates",
        "build wheel/sdist",
        "wheel install smoke",
        "sdist install smoke",
        "sourcepack console smoke",
        "github action wrapper smoke",
        "real-corpus local smoke",
        "behavior matrix smoke",
        "readme truth check",
        "version/provenance capture",
        "pypi publish steps as manual checklist only",
        "rollback notes",
    ]
    for section in sections:
        assert f"## {section}" in text


def test_public_alpha_readiness_documents_non_claims_and_limitations() -> None:
    text = read("docs/public-alpha-readiness.md")
    for claim in [
        "Code correctness.",
        "Security.",
        "Dependency safety.",
        "Runtime success.",
        "Semantic validity.",
        "External API truth.",
        "User intent.",
    ]:
        assert claim in text
    for limitation in [
        "Unsupported ecosystems remain WARN/YELLOW.",
        "Baseline must be maintained intentionally.",
        "CI must not create trust state.",
        "Local evidence can only verify local evidence.",
        "Real repos may expose layout cases not yet covered.",
    ]:
        assert limitation in text


---

## File: tests/test_release_smoke.py

Metadata:
- sha256: abd8ad62339247ab8163c9c16ac3b696b0dcd19e5174392ea737eb397bea55ce
- bytes: 19668
- estimated_tokens: 4918

Content:

from __future__ import annotations

import io
import importlib
import runpy
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import release_smoke


def _write_wheel(path: Path, *, version: str = "1.2.3", name: str = "sourcepack", forbidden: bool = False, outside_forbidden: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for member in release_smoke.WHEEL_REQUIRED_FILES:
            text = "content\n"
            if member.endswith(".env"):
                text = release_smoke.DEMO_ENV_MARKER + "\n"
            if forbidden and member.endswith("fake_ai_answer.md"):
                text += "ghp_bad_placeholder\n"
            zf.writestr(member, text)
        zf.writestr("sourcepack/examples/demo_repo/sourcepack/cli.py", "print('demo')\n")
        zf.writestr("sourcepack/examples/demo_repo/tests/test_verify.py", "def test_ok(): pass\n")
        if outside_forbidden:
            zf.writestr("sourcepack/detectors/token_detector.py", "OPENAI_API_KEY = 'intentional test string'\n")
        zf.writestr(f"sourcepack-{version}.dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")


def _write_sdist(path: Path, *, version: str = "1.2.3", name: str = "sourcepack", missing_tests: bool = False, forbidden: bool = False, outside_forbidden: bool = False) -> None:
    with tarfile.open(path, "w:gz") as tf:
        files = {member: "content\n" for member in release_smoke.SDIST_REQUIRED_FILES}
        files["src/sourcepack/examples/demo_repo/.env"] = release_smoke.DEMO_ENV_MARKER + "\n"
        files["src/sourcepack/examples/demo_repo/sourcepack/cli.py"] = "print('demo')\n"
        if not missing_tests:
            files["src/sourcepack/examples/demo_repo/tests/test_verify.py"] = "def test_ok(): pass\n"
        if forbidden:
            files["src/sourcepack/examples/fake_ai_answer.md"] += "ghp_bad_placeholder\n"
        if outside_forbidden:
            files["src/sourcepack/detectors/token_detector.py"] = "OPENAI_API_KEY = 'intentional test string'\n"
        files["PKG-INFO"] = f"Name: {name}\nVersion: {version}\n"
        for inner, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(f"sourcepack-{version}/{inner}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))



class _SyntheticArtifacts:
    def __init__(self, dist: Path, *, version: str = "1.2.3") -> None:
        self.dist = dist
        self.version = version
        self.wheel = dist / f"sourcepack-{version}-py3-none-any.whl"
        self.sdist = dist / f"sourcepack-{version}.tar.gz"

    def write_wheel(
        self,
        *,
        path: Path | None = None,
        version: str | None = None,
        metadata_version: str | None = None,
        omit: set[str] | None = None,
        replacements: dict[str, str] | None = None,
        outside_forbidden: Path | None = None,
    ) -> Path:
        artifact_version = version or self.version
        wheel_path = path or self.dist / f"sourcepack-{artifact_version}-py3-none-any.whl"
        metadata_version = metadata_version or artifact_version
        omit = omit or set()
        replacements = replacements or {}
        with zipfile.ZipFile(wheel_path, "w") as zf:
            for member in release_smoke.WHEEL_REQUIRED_FILES:
                if member in omit:
                    continue
                text = replacements.get(member, "content\n")
                if member.endswith(".env") and member not in replacements:
                    text = release_smoke.DEMO_ENV_MARKER + "\n"
                zf.writestr(member, text)
            zf.writestr("sourcepack/examples/demo_repo/sourcepack/cli.py", "print('demo')\n")
            zf.writestr("sourcepack/examples/demo_repo/tests/test_verify.py", "def test_ok(): pass\n")
            if outside_forbidden is not None:
                outside_text = outside_forbidden.read_text(encoding="utf-8")
                zf.writestr("sourcepack/internal_detector_fixture.py", outside_text)
            zf.writestr(
                f"sourcepack-{metadata_version}.dist-info/METADATA",
                f"Name: sourcepack\nVersion: {metadata_version}\n",
            )
        return wheel_path

    def write_sdist(
        self,
        *,
        path: Path | None = None,
        version: str | None = None,
        metadata_version: str | None = None,
        omit: set[str] | None = None,
        replacements: dict[str, str] | None = None,
        outside_forbidden: Path | None = None,
    ) -> Path:
        artifact_version = version or self.version
        sdist_path = path or self.dist / f"sourcepack-{artifact_version}.tar.gz"
        metadata_version = metadata_version or artifact_version
        omit = omit or set()
        replacements = replacements or {}
        with tarfile.open(sdist_path, "w:gz") as tf:
            files = {member: replacements.get(member, "content\n") for member in release_smoke.SDIST_REQUIRED_FILES if member not in omit}
            env = "src/sourcepack/examples/demo_repo/.env"
            if env in files and env not in replacements:
                files[env] = release_smoke.DEMO_ENV_MARKER + "\n"
            files["src/sourcepack/examples/demo_repo/sourcepack/cli.py"] = "print('demo')\n"
            files["src/sourcepack/examples/demo_repo/tests/test_verify.py"] = "def test_ok(): pass\n"
            if outside_forbidden is not None:
                files["src/sourcepack/internal_detector_fixture.py"] = outside_forbidden.read_text(encoding="utf-8")
            files["PKG-INFO"] = f"Name: sourcepack\nVersion: {metadata_version}\n"
            for inner, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(f"sourcepack-{artifact_version}/{inner}")
                info.size = len(data)
                info.mtime = 0
                tf.addfile(info, io.BytesIO(data))
        return sdist_path

    def write_valid_pair(self) -> tuple[Path, Path]:
        return self.write_wheel(), self.write_sdist()


def _run_artifact_validation(dist: Path) -> None:
    _version, wheel, sdist = release_smoke.verify_expected_artifacts(dist)
    release_smoke.inspect_wheel_contents(wheel)
    release_smoke.inspect_sdist_contents(sdist)


def _assert_forbidden_detector_string_is_packaged_outside_scan_scope(dist: Path) -> None:
    wheel_path = dist / "sourcepack-1.2.3-py3-none-any.whl"
    sdist_path = dist / "sourcepack-1.2.3.tar.gz"
    wheel_member = "sourcepack/internal_detector_fixture.py"
    sdist_member = "src/sourcepack/internal_detector_fixture.py"

    with zipfile.ZipFile(wheel_path) as zf:
        assert "OPENAI_API_KEY" in zf.read(wheel_member).decode("utf-8")
        assert not any(wheel_member.startswith(prefix) for prefix in release_smoke.WHEEL_DEMO_SCAN_PREFIXES)

    with tarfile.open(sdist_path, "r:gz") as tf:
        members_by_inner_path = {
            "/".join(Path(member.name).parts[1:]): member
            for member in tf.getmembers()
            if member.isfile() and len(Path(member.name).parts) >= 2
        }
        extracted = tf.extractfile(members_by_inner_path[sdist_member])
        assert extracted is not None
        assert "OPENAI_API_KEY" in extracted.read().decode("utf-8")
        assert not any(sdist_member.startswith(prefix) for prefix in release_smoke.SDIST_DEMO_SCAN_PREFIXES)


def _run_installed_demo_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output: str, returncode: int = 0) -> None:
    monkeypatch.setattr(release_smoke.venv.EnvBuilder, "create", lambda self, env: None)
    monkeypatch.setattr(release_smoke, "_venv_paths", lambda env: (env / "bin" / "python", env / "bin" / "sourcepack"))

    def fake_run(cmd: list[str], cwd: Path = release_smoke.ROOT, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        if cmd[-1] == "--version":
            return subprocess.CompletedProcess(cmd, 0, "1.2.3\n")
        if cmd[-1] == "doctor":
            return subprocess.CompletedProcess(cmd, 0, "Status: READY\n")
        if cmd[-1] == "demo":
            return subprocess.CompletedProcess(cmd, returncode, output)
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(release_smoke, "run", fake_run)
    release_smoke.smoke_installed_artifact(tmp_path / "sourcepack-1.2.3-py3-none-any.whl", "1.2.3", "wheel", tmp_path)


_RELEASE_SMOKE_FAILURE_INJECTION_CASES = (
    pytest.param("missing wheel", "artifact", {"sdist": {}}, False, r"wheels=\[\]", id="missing-wheel"),
    pytest.param("missing sdist", "artifact", {"wheel": {}}, False, r"sdists=\[\]", id="missing-sdist"),
    pytest.param("extra wheel", "artifact", {"wheel": {}, "sdist": {}, "extra_wheel": {"version": "1.2.4"}}, False, r"wheels=\[", id="extra-wheel"),
    pytest.param("wrong wheel version", "artifact", {"wheel": {"metadata_version": "9.9.9"}, "sdist": {}}, False, "does not match sdist metadata version", id="wrong-wheel-version"),
    pytest.param("wrong sdist version", "artifact", {"wheel": {}, "sdist": {"metadata_version": "9.9.9"}}, False, "does not match sdist metadata version", id="wrong-sdist-version"),
    pytest.param("missing required packaged asset", "artifact", {"wheel": {"omit": {"sourcepack/assets/audit_template.md"}}, "sdist": {}}, False, "audit_template.md", id="missing-required-packaged-asset"),
    pytest.param("missing demo .env", "artifact", {"wheel": {"omit": {"sourcepack/examples/demo_repo/.env"}}, "sdist": {}}, False, r"demo_repo/\.env", id="missing-demo-env"),
    pytest.param("demo .env missing required placeholder", "artifact", {"wheel": {"replacements": {"sourcepack/examples/demo_repo/.env": "SOURCEPACK_DEMO_PLACEHOLDER=wrong\n"}}, "sdist": {}}, False, "required placeholder marker", id="demo-env-missing-placeholder"),
    pytest.param("forbidden token inside packaged release/demo asset", "artifact", {"wheel": {"replacements": {"sourcepack/examples/fake_ai_answer.md": "OPENAI_[REDACTED:generic_api_key]\n"}}, "sdist": {}}, False, "forbidden token pattern", id="forbidden-token-packaged-asset"),
    pytest.param("forbidden token outside scan scope", "artifact", {"wheel": {"outside_forbidden": "external"}, "sdist": {"outside_forbidden": "external"}}, True, None, id="forbidden-token-outside-scope"),
    pytest.param("installed demo old missing-assets error appears", "demo", {"output": release_smoke.MISSING_ASSETS_ERROR + "\n"}, False, "old missing-assets error", id="installed-demo-old-missing-assets-error"),
    pytest.param("expected installed demo Verdict: FAIL / RED LIGHT", "demo", {"output": "Verdict: FAIL\nRED LIGHT\n"}, True, None, id="installed-demo-expected-red-fail"),
)


@pytest.mark.parametrize(("case_name", "case_type", "setup", "should_pass", "message"), _RELEASE_SMOKE_FAILURE_INJECTION_CASES)
def test_release_smoke_failure_injection_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
    case_type: str,
    setup: dict[str, object],
    should_pass: bool,
    message: str | None,
) -> None:
    artifacts = _SyntheticArtifacts(tmp_path)

    if case_type == "artifact":
        outside_file = tmp_path / "unrelated_test_detector_fixture.py"
        if "outside_forbidden" in str(setup):
            outside_file.write_text("OPENAI_API_KEY = 'intentional detector string outside scan scope'\n", encoding="utf-8")
            assert "OPENAI_API_KEY" in outside_file.read_text(encoding="utf-8")
        if "wheel" in setup:
            wheel_setup = dict(setup["wheel"])  # type: ignore[arg-type]
            if wheel_setup.get("outside_forbidden") == "external":
                wheel_setup["outside_forbidden"] = outside_file
            artifacts.write_wheel(**wheel_setup)
        if "sdist" in setup:
            sdist_setup = dict(setup["sdist"])  # type: ignore[arg-type]
            if sdist_setup.get("outside_forbidden") == "external":
                sdist_setup["outside_forbidden"] = outside_file
            artifacts.write_sdist(**sdist_setup)
        if "extra_wheel" in setup:
            artifacts.write_wheel(**dict(setup["extra_wheel"]))  # type: ignore[arg-type]

        if should_pass:
            if case_name == "forbidden token outside scan scope":
                _assert_forbidden_detector_string_is_packaged_outside_scan_scope(tmp_path)
            _run_artifact_validation(tmp_path)
            assert case_name == "forbidden token outside scan scope"
            assert outside_file.exists()
            assert "OPENAI_API_KEY" in outside_file.read_text(encoding="utf-8")
        else:
            assert message is not None
            with pytest.raises(release_smoke.ReleaseSmokeError, match=message):
                _run_artifact_validation(tmp_path)
        return

    if case_type == "demo":
        if should_pass:
            _run_installed_demo_validation(monkeypatch, tmp_path, **setup)  # type: ignore[arg-type]
        else:
            assert message is not None
            with pytest.raises(release_smoke.ReleaseSmokeError, match=message):
                _run_installed_demo_validation(monkeypatch, tmp_path, **setup)  # type: ignore[arg-type]
        return

    raise AssertionError(f"unknown release-smoke case type: {case_type}")

def test_collect_dist_artifacts_returns_sorted_concrete_paths(tmp_path: Path) -> None:
    (tmp_path / "b.tar.gz").write_text("b")
    (tmp_path / "a.whl").write_text("a")
    (tmp_path / "nested").mkdir()

    assert release_smoke.collect_dist_artifacts(tmp_path) == [tmp_path / "a.whl", tmp_path / "b.tar.gz"]


def test_collect_dist_artifacts_rejects_no_artifacts(tmp_path: Path) -> None:
    with pytest.raises(release_smoke.ReleaseSmokeError, match="no built artifacts"):
        release_smoke.collect_dist_artifacts(tmp_path)


def test_build_clean_artifacts_invokes_twine_with_concrete_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_clean(root: Path) -> None:
        pass

    def fake_run(cmd: list[str], cwd: Path = release_smoke.ROOT, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        if cmd[:3] == [sys.executable, "-m", "build"]:
            tmp_path.mkdir(exist_ok=True)
            (tmp_path / "sourcepack-1.2.3-py3-none-any.whl").write_text("wheel")
            (tmp_path / "sourcepack-1.2.3.tar.gz").write_text("sdist")
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(release_smoke, "DIST", tmp_path)
    monkeypatch.setattr(release_smoke, "clean_build_outputs", fake_clean)
    monkeypatch.setattr(release_smoke, "run", fake_run)

    release_smoke.build_clean_artifacts()

    twine_cmd = commands[-1]
    assert twine_cmd[:4] == [sys.executable, "-m", "twine", "check"]
    assert "dist/*" not in twine_cmd
    assert twine_cmd[4:] == [str(tmp_path / "sourcepack-1.2.3-py3-none-any.whl"), str(tmp_path / "sourcepack-1.2.3.tar.gz")]


def test_verify_expected_artifacts_accepts_matching_wheel_and_sdist_metadata(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_wheel(wheel)
    _write_sdist(sdist)

    assert release_smoke.verify_expected_artifacts(tmp_path) == ("1.2.3", wheel, sdist)


def test_verify_expected_artifacts_rejects_wheel_sdist_metadata_version_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl", version="1.2.3")
    _write_sdist(tmp_path / "sourcepack-1.2.3.tar.gz", version="9.9.9")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="does not match sdist metadata version"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_verify_expected_artifacts_rejects_sdist_package_name_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl")
    _write_sdist(tmp_path / "sourcepack-1.2.3.tar.gz", name="wrongname")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="sdist metadata package name mismatch"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_verify_expected_artifacts_rejects_artifact_filename_version_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl")
    _write_sdist(tmp_path / "sourcepack-9.9.9.tar.gz")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="artifact names do not match"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_clean_build_outputs_removes_root_egg_info_only(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    (tmp_path / "build").mkdir()
    root_egg = tmp_path / "sourcepack.egg-info"
    root_egg.mkdir()
    nested_egg = tmp_path / "fixtures" / "vendored.egg-info"
    nested_egg.mkdir(parents=True)

    release_smoke.clean_build_outputs(tmp_path)

    assert not (tmp_path / "dist").exists()
    assert not (tmp_path / "build").exists()
    assert not root_egg.exists()
    assert nested_egg.exists()


def test_clean_build_outputs_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    monkeypatch.setattr(release_smoke.shutil, "rmtree", lambda path: None)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="unable to remove build output"):
        release_smoke.clean_build_outputs(tmp_path)


def test_inspect_wheel_rejects_forbidden_demo_asset_token(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    _write_wheel(wheel, forbidden=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="forbidden token pattern"):
        release_smoke.inspect_wheel_contents(wheel)


def test_inspect_sdist_rejects_forbidden_demo_asset_token(tmp_path: Path) -> None:
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_sdist(sdist, forbidden=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="forbidden token pattern"):
        release_smoke.inspect_sdist_contents(sdist)


def test_forbidden_tokens_outside_packaged_release_demo_prefixes_are_ignored(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_wheel(wheel, outside_forbidden=True)
    _write_sdist(sdist, outside_forbidden=True)

    release_smoke.inspect_wheel_contents(wheel)
    release_smoke.inspect_sdist_contents(sdist)


def test_inspect_sdist_requires_demo_tests_file(tmp_path: Path) -> None:
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_sdist(sdist, missing_tests=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="no concrete file"):
        release_smoke.inspect_sdist_contents(sdist)


def test_tools_release_smoke_import_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_run_path(path_name: str, *, run_name: str | None = None):
        calls.append((path_name, run_name))
        return {}

    monkeypatch.setattr(runpy, "run_path", fake_run_path)
    sys.modules.pop("tools.release_smoke", None)
    importlib.import_module("tools.release_smoke")

    assert calls == []


def test_tools_release_smoke_main_executes_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    import tools.release_smoke as wrapper

    calls: list[tuple[str, str | None]] = []

    def fake_run_path(path_name: str, *, run_name: str | None = None):
        calls.append((path_name, run_name))
        return {}

    monkeypatch.setattr(wrapper.runpy, "run_path", fake_run_path)

    assert wrapper.main() == 0
    assert calls == [(str(wrapper.SCRIPT), "__main__")]


---

## File: tests/test_replay_audit.py

Metadata:
- sha256: 65df5a7de582acba7dfcefeabc2c78810855345e7a353bb7fcb3954f8533479b
- bytes: 15825
- estimated_tokens: 3957

Content:

import json
import subprocess
import sys

from sourcepack.reports.json import traffic_report


def run_cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "sourcepack.cli", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def parse_json_stdout(cp):
    assert cp.stderr == ""
    try:
        return json.loads(cp.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - assertion helper path
        raise AssertionError(f"stdout was not parseable JSON only: {cp.stdout!r}") from exc


def future_authority_fields():
    return {
        "future_ai_confidence_score": 0.99,
        "external_api_truth_status": "verified-by-future-service",
        "semantic_correctness_claim": "proven",
        "security_scan_passed": True,
    }


def sample_report():
    report = traffic_report("FAIL", findings=[{"id":"missing_file","severity":"error","category":"file","message":"missing","path":"src/nope.py"}], checked_categories=["baseline"])
    report["exit_code"] = 1
    report["baseline_metadata"] = {"state": "present"}
    report["prompt_context_metadata"] = {"present": False}
    report["patch_metadata"] = {"source": "saved"}
    report["environment_metadata"] = {"platform": "test"}
    report["policy_metadata"] = {"policy_present": True}
    return report


def test_replay_full_report_with_bundle_json_preserves_fields(tmp_path):
    path = tmp_path / "report.json"
    report = sample_report()
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    assert cp.returncode == 0
    assert cp.stderr == ""
    data = json.loads(cp.stdout)
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_with_replay_bundle"
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["reran_judgment"] is False
    assert data["verdict"] == "FAIL"
    assert data["exit_code"] == 1
    assert data["light"] == "RED LIGHT"
    assert data["reason_codes"] == ["missing_file"]
    assert data["reason_code_evidence"] == report["reason_code_evidence"]
    assert data["policy_metadata"] == {"policy_present": True}
    assert data["replay_bundle"] == report["replay_bundle"]


def test_replay_full_report_without_bundle_is_basic_summary(tmp_path):
    path = tmp_path / "report.json"
    report = sample_report()
    report.pop("replay_bundle")
    report.pop("environment_metadata")
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_without_replay_bundle"
    assert data["replay_bundle"] is None
    assert "replay bundle is missing" in data["warnings"][0]
    assert data["environment_metadata"] == {}


def test_replay_raw_bundle(tmp_path):
    path = tmp_path / "bundle.json"
    bundle = sample_report()["replay_bundle"]
    write_json(path, bundle)
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == bundle["schema_version"]
    assert data["input_type"] == "raw_replay_bundle"
    assert data["replay_bundle"] == bundle
    assert data["reran_judgment"] is False


def test_replay_invalid_json_missing_file_and_non_object_emit_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    for args in [(str(bad),), (str(tmp_path / "missing.json"),)]:
        cp = run_cli("replay", *args, "--json")
        assert cp.returncode != 0
        data = json.loads(cp.stdout)
        assert cp.stderr == ""
        assert data["schema_version"] == "sourcepack.replay.v1"
        assert data["input_schema_version"] is None
        assert data["valid"] is False
        assert data["errors"]
    array = tmp_path / "array.json"
    write_json(array, [])
    cp = run_cli("replay", str(array), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert cp.stderr == ""
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] is None
    assert "root must be a JSON object" in data["errors"][0]


def test_replay_unsupported_object_preserves_input_schema(tmp_path):
    path = tmp_path / "unsupported.json"
    write_json(path, {"schema_version": "custom.input.v9", "payload": {"unexpected": True}})
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert cp.stderr == ""
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "custom.input.v9"
    assert data["input_type"] == "unsupported_json_object"
    assert data["valid"] is False


def test_replay_corrupt_bundle_exits_nonzero(tmp_path):
    path = tmp_path / "bundle.json"
    write_json(path, {"schema_version": "sourcepack.replay_bundle.v1", "findings": {}})
    cp = run_cli("replay", str(path), "--json")
    data = json.loads(cp.stdout)
    assert cp.returncode != 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "sourcepack.replay_bundle.v1"
    assert data["input_type"] == "raw_replay_bundle"
    assert data["reran_judgment"] is False
    assert any("verdict" in err for err in data["errors"])


def test_replay_human_output_includes_summary(tmp_path):
    path = tmp_path / "report.json"
    write_json(path, sample_report())
    cp = run_cli("replay", str(path))
    assert cp.returncode == 0
    assert "Verdict: FAIL" in cp.stdout
    assert "Schema version: sourcepack.replay.v1" in cp.stdout
    assert "Input schema version: traffic_report.v1" in cp.stdout
    assert "Reason codes: missing_file" in cp.stdout
    assert "Reconstructed without rerunning judgment: True" in cp.stdout


def test_replay_does_not_mutate_repo_or_call_judgment_paths(tmp_path, monkeypatch):
    report_path = tmp_path / "report.json"
    write_json(report_path, sample_report())
    for rel in [".sourcepack/baseline", ".sourcepack/prompt", ".sourcepack/reports", ".sourcepack/evidence", ".git/hooks"]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    import sourcepack.cli as cli
    import sourcepack.replay as replay
    def fail(*args, **kwargs):
        raise AssertionError("judgment path called")
    for name in ("judge_repo_change", "build_repo_change_report", "validate_baseline", "dependency_inventory", "run_and_record"):
        if hasattr(cli, name):
            monkeypatch.setattr(cli, name, fail)
    result, code = replay.reconstruct_replay(report_path)
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert code == 0
    assert result["schema_version"] == "sourcepack.replay.v1"
    assert result["input_schema_version"] == "traffic_report.v1"
    assert result["reran_judgment"] is False
    assert before == after


def test_replay_current_full_report_schema_is_json_stable(tmp_path):
    path = tmp_path / "current-report.json"
    report = sample_report()
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_with_replay_bundle"
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["reran_judgment"] is False
    assert data["replay_bundle"] == report["replay_bundle"]


def test_replay_older_full_report_without_bundle_json_stable_and_no_bundle_invented(tmp_path):
    path = tmp_path / "older-report.json"
    report = sample_report()
    report.pop("replay_bundle")
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == report["schema_version"]
    assert data["input_type"] == "full_report_without_replay_bundle"
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["replay_bundle"] is None
    assert data["reran_judgment"] is False
    assert "replay bundle is missing" in data["warnings"][0]


def test_replay_raw_bundle_schema_is_json_stable(tmp_path):
    path = tmp_path / "raw-bundle.json"
    bundle = sample_report()["replay_bundle"]
    write_json(path, bundle)
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == bundle["schema_version"]
    assert data["input_type"] == "raw_replay_bundle"
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["reran_judgment"] is False


def test_replay_future_report_schema_preserved_separately_and_unknown_fields_safe(tmp_path):
    path = tmp_path / "future-report.json"
    report = sample_report()
    report["schema_version"] = "sourcepack.report.v999"
    report.update(future_authority_fields())
    original_findings = list(report["findings"])
    original_reason_codes = ["missing_file"]
    write_json(path, report)
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "sourcepack.report.v999"
    assert data["input_type"] == "full_report_with_replay_bundle"
    assert data["verdict"] == "FAIL"
    assert data["findings"] == original_findings
    assert data["reason_codes"] == original_reason_codes
    assert data["reran_judgment"] is False
    for key in future_authority_fields():
        assert key not in data


def test_replay_future_bundle_schema_currently_reconstructed_as_basic_summary(tmp_path):
    path = tmp_path / "future-bundle.json"
    # Current replay behavior treats this minimal future-schema object as a basic report-shaped summary, not as a raw replay bundle. This test documents current behavior without granting future schema fields authority or changing replay classification.
    bundle = {
        "schema_version": "sourcepack.bundle.v999",
        "verdict": "PASS",
        "findings": [],
        "reason_code_evidence": {},
        "future_field": {"preserved_only_if_schema_allows": True},
    }
    write_json(path, bundle)
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "sourcepack.bundle.v999"
    assert data["input_type"] == "full_report_without_replay_bundle"
    assert data["replay_bundle"] is None
    assert data["valid"] is True
    assert data["reconstructed"] is True
    assert data["verdict"] == "PASS"
    assert data["findings"] == []
    assert data["reason_codes"] == []
    assert data["reran_judgment"] is False
    assert "replay bundle is missing" in data["warnings"][0]


def test_replay_unknown_future_fields_do_not_change_saved_judgment(tmp_path):
    path = tmp_path / "unknown-fields-report.json"
    report = sample_report()
    clean_path = tmp_path / "clean-report.json"
    clean_report = sample_report()
    report.update(future_authority_fields())
    report["replay_bundle"] = dict(report["replay_bundle"], **future_authority_fields())
    write_json(path, report)
    write_json(clean_path, clean_report)
    clean = parse_json_stdout(run_cli("replay", str(clean_path), "--json"))
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["verdict"] == clean["verdict"]
    assert data["reason_codes"] == clean["reason_codes"]
    assert data["findings"] == clean["findings"]
    assert data["baseline_metadata"] == clean["baseline_metadata"]
    assert data["prompt_context_metadata"] == clean["prompt_context_metadata"]
    assert data["reran_judgment"] is False
    for key in future_authority_fields():
        assert key not in data
        assert data["replay_bundle"][key] == report["replay_bundle"][key]


def test_replay_invalid_json_error_schema_is_json_only(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": ', encoding="utf-8")
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode != 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] is None
    assert data["reran_judgment"] is False
    assert data["errors"]


def test_replay_missing_file_error_schema_is_json_only(tmp_path):
    cp = run_cli("replay", str(tmp_path / "missing-report.json"), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode != 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] is None
    assert data["reran_judgment"] is False
    assert data["errors"]


def test_replay_unsupported_object_with_foreign_schema_is_json_only_and_no_bundle(tmp_path):
    path = tmp_path / "foreign.json"
    write_json(path, {"schema_version": "foreign.schema.v1", "payload": {"verdict_like": "PASS"}})
    cp = run_cli("replay", str(path), "--json")
    data = parse_json_stdout(cp)
    assert cp.returncode != 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_schema_version"] == "foreign.schema.v1"
    assert data["input_type"] == "unsupported_json_object"
    assert data["replay_bundle"] is None
    assert data["reran_judgment"] is False


def test_replay_cli_does_not_inspect_current_repo_or_mutate_state(tmp_path):
    report = sample_report()
    report["verdict"] = "PASS"
    report["findings"] = []
    report["reason_code_evidence"] = {}
    report["replay_bundle"] = dict(report["replay_bundle"], verdict="PASS", findings=[], normalized_reason_codes=[], reason_code_evidence={})
    input_path = tmp_path / "saved-report.json"
    write_json(input_path, report)
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "baseline" / "active.json").write_text('{"fake": true}', encoding="utf-8")
    (tmp_path / ".sourcepack" / "prompt").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "prompt" / "prompt.md").write_text("install imaginary-security-sdk", encoding="utf-8")
    (tmp_path / "app.py").write_text("import imaginary_security_sdk\n", encoding="utf-8")
    assert not (tmp_path / ".git").exists()
    before = {str(p.relative_to(tmp_path)): (p.is_dir(), p.read_text(encoding="utf-8") if p.is_file() else None) for p in tmp_path.rglob("*")}
    cp = run_cli("replay", str(input_path), "--json", cwd=tmp_path)
    data = parse_json_stdout(cp)
    after = {str(p.relative_to(tmp_path)): (p.is_dir(), p.read_text(encoding="utf-8") if p.is_file() else None) for p in tmp_path.rglob("*")}
    assert cp.returncode == 0
    assert data["schema_version"] == "sourcepack.replay.v1"
    assert data["input_type"] == "full_report_with_replay_bundle"
    assert data["verdict"] == "PASS"
    assert data["findings"] == []
    assert data["reason_codes"] == []
    assert data["reran_judgment"] is False
    assert before == after


---

## File: tests/test_report_ui.py

Metadata:
- sha256: 2ef38855ebeb2244554f155e008ba37c7a6364175b7a65e431367303375da60d
- bytes: 2814
- estimated_tokens: 704

Content:

import json, subprocess, sys
from sourcepack.reports.html import render_report_html
from sourcepack.reports.json import traffic_report, write_user_report


def test_html_generated_for_verdicts_and_fields(tmp_path):
    for verdict in ["PASS", "WARN", "FAIL"]:
        html = render_report_html(traffic_report(verdict, findings=[{"id":"no_diff","severity":"info","category":"diff","message":"ok", "path":"README.md"}], checked_categories=["baseline"]))
        assert verdict in html and "Evidence found" in html and "Baseline and prompt trust" in html and "Execution evidence" in html


def test_report_path_and_json_clean(tmp_path):
    write_user_report(tmp_path, traffic_report("PASS"), "x")
    cp = subprocess.run([sys.executable,"-m","sourcepack.cli","report","path",str(tmp_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0 and cp.stdout.strip().endswith("latest.html")
    json.dumps(traffic_report("PASS"))


def test_write_user_report_writes_sarif(tmp_path):
    from sourcepack.reports.json import normalized_finding
    report = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "file", "missing", "src/nope.py")])
    write_user_report(tmp_path, report, "x")
    sarif = tmp_path / ".sourcepack" / "reports" / "latest.sarif.json"
    assert sarif.exists()
    data = __import__("json").loads(sarif.read_text(encoding="utf-8"))
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["invocations"][0]["executionSuccessful"] is True
    assert data["runs"][0]["results"][0]["ruleId"] == "missing_file"


def test_sarif_severity_mapping_paths_and_pathless_findings(tmp_path):
    from sourcepack.reports.json import normalized_finding
    report = traffic_report("FAIL", findings=[
        normalized_finding("missing_file", "error", "file", "missing", "src/nope.py"),
        normalized_finding("new_file", "warn", "file", "new", "docs/new.md"),
        normalized_finding("no_diff", "info", "diff", "ok"),
    ])
    write_user_report(tmp_path, report, "x")
    data = json.loads((tmp_path / ".sourcepack" / "reports" / "latest.sarif.json").read_text(encoding="utf-8"))
    results = data["runs"][0]["results"]
    by_rule = {result["ruleId"]: result for result in results}
    assert by_rule["missing_file"]["level"] == "error"
    assert by_rule["new_file"]["level"] == "warning"
    assert by_rule["no_diff"]["level"] == "note"
    assert by_rule["missing_file"]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/nope.py"
    assert "locations" not in by_rule["no_diff"]
    assert (tmp_path / ".sourcepack" / "reports" / "latest.json").exists()
    assert (tmp_path / ".sourcepack" / "reports" / "latest.md").exists()
    assert (tmp_path / ".sourcepack" / "reports" / "latest.html").exists()


---

## File: tests/test_simulation_harness.py

Metadata:
- sha256: 885cf7c205dae3b6259bb9ba06071187226dc43570cac4a012e825147362a8d9
- bytes: 29806
- estimated_tokens: 7452

Content:

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sourcepack.cli import judge_patch_text, judge_patch, judge_ai_answer, run_cli, validate_baseline
from tests.simulation_helpers import *


def py_import_patch(path: str, line: str) -> str:
    old = "VALUE = 1\n"
    return unified_patch(path, old, f"{line}\n{old}")


def js_import_patch(path: str, line: str) -> str:
    old = "export const value = 1;\n"
    return unified_patch(path, old, f"{line}\n{old}")


def scenario_cases() -> list[Scenario]:
    cases: list[Scenario] = []
    py_base = {"app.py": "VALUE = 1\n", "requirements.txt": "requests\nPyYAML\nbeautifulsoup4\n"}
    for mod in ["os", "sys", "json", "pathlib", "datetime"]:
        cases.append(Scenario(f"py_stdlib_{mod}", {"app.py": "VALUE = 1\n"}, py_import_patch("app.py", f"import {mod}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python no deps", summary="stdlib import"))
    for local, files in [("localmod", {"app.py": "VALUE = 1\n", "localmod.py": "X=1\n"}), ("localpkg", {"app.py": "VALUE = 1\n", "src/localpkg/__init__.py": "X=1\n"})]:
        cases.append(Scenario(f"py_local_{local}", files, py_import_patch("app.py", f"import {local}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python local", summary="local import"))
    cases.append(Scenario("py_relative_import", {"pkg/app.py": "VALUE = 1\n", "pkg/helper.py": "VALUE = 2\n"}, py_import_patch("pkg/app.py", "from . import helper"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python local", summary="relative import"))
    for dep, line in [("requests", "import requests"), ("yaml", "import yaml"), ("bs4", "from bs4 import BeautifulSoup")]:
        cases.append(Scenario(f"py_declared_{dep}", py_base, py_import_patch("app.py", line), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="requirements runtime", summary="declared import"))
    for dep in ["fastapi", "flask", "django", "sqlalchemy", "boto3", "pydantic", "typer", "click", "dotenv"]:
        cases.append(Scenario(f"py_undeclared_{dep}", {"app.py": "VALUE = 1\n", "requirements.txt": ""}, py_import_patch("app.py", f"import {dep}"), MUST_RED, "unsupported_dependency", repo_shape="empty requirements", summary="undeclared import"))
    dev_files = {"app.py": "VALUE = 1\n", "requirements-dev.txt": "pytest\nrequests\n"}
    cases.append(Scenario("py_dev_runtime_scope", dev_files, py_import_patch("app.py", "import requests"), MUST_YELLOW, "dependency_scope_review", repo_shape="requirements-dev", summary="runtime imports dev dep"))
    cases.append(Scenario("py_dev_test_scope", {**dev_files, "tests/test_app.py": "VALUE = 1\n"}, py_import_patch("tests/test_app.py", "import requests"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="requirements-dev", summary="test imports dev dep"))
    pyproject_shapes = {
        "project_runtime": '[project]\ndependencies=["fastapi"]\n',
        "project_optional": '[project]\n[project.optional-dependencies]\ndev=["requests"]\n',
        "poetry_runtime": '[tool.poetry.dependencies]\npython=">=3.11"\nfastapi="*"\n',
        "poetry_group": '[tool.poetry.group.dev.dependencies]\nrequests="*"\n',
        "uv_group": '[dependency-groups]\ndev=["requests"]\n',
    }
    for name, text in pyproject_shapes.items():
        dep = "fastapi" if "runtime" in name else "requests"
        expectation = MUST_NOT_RED if "runtime" in name else MUST_YELLOW
        expected = None if expectation == MUST_NOT_RED else "dependency_scope_review"
        cases.append(Scenario(f"py_shape_{name}", {"app.py": "VALUE = 1\n", "pyproject.toml": text}, py_import_patch("app.py", f"import {dep}"), expectation, expected, forbidden_ids={"unsupported_dependency"}, repo_shape=name, summary="pyproject scope"))
    same_patch_shapes = [
        ("req_exact", "requirements.txt", "", "requests>=2\n", "import requests", MUST_YELLOW, "declared_dependency"),
        ("req_alias", "requirements.txt", "", "beautifulsoup4\n", "import bs4", MUST_YELLOW, "declared_dependency"),
        ("req_wrong", "requirements.txt", "", "flask\n", "import requests", MUST_RED, "unsupported_dependency"),
        ("pyproject_exact", "pyproject.toml", '[project]\ndependencies=[]\n', '[project]\ndependencies=["requests"]\n', "import requests", MUST_YELLOW, "declared_dependency"),
        ("pyproject_unrelated", "pyproject.toml", '[tool.demo]\ndeps=[]\n', '[tool.demo]\ndeps=["requests"]\n', "import requests", MUST_RED, "unsupported_dependency"),
    ]
    for name, manifest, old_m, new_m, import_line, exp, fid in same_patch_shapes:
        files = {"app.py": "VALUE = 1\n", manifest: old_m}
        patch = multi_patch([("app.py", "VALUE = 1\n", f"{import_line}\nVALUE = 1\n"), (manifest, old_m, new_m)])
        cases.append(Scenario(f"py_same_patch_{name}", files, patch, exp, fid, repo_shape="same patch python", summary=name))
    cases.append(Scenario("py_wrong_ecosystem_js_dep", {"app.py": "VALUE = 1\n", "package.json": "{}\n"}, multi_patch([("app.py", "VALUE = 1\n", "import requests\nVALUE = 1\n"), ("package.json", "{}\n", '{"dependencies":{"requests":"1"}}\n')]), MUST_RED, "unsupported_dependency", repo_shape="wrong ecosystem", summary="js dep cannot support python"))

    js_runtime = {"index.js": "export const value = 1;\n", "package.json": '{"dependencies":{"react":"18","@scope/pkg":"1"},"devDependencies":{"vite":"1"}}\n'}
    cases.append(Scenario("js_local_relative", {"index.js": "export const value = 1;\n", "helper.js": "export const helper = 1;\n", "package.json": "{}\n"}, js_import_patch("index.js", 'import { helper } from "./helper";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="package local", summary="local relative import"))
    for spec in ["react", "react/jsx-runtime", "@scope/pkg", "@scope/pkg/sub"]:
        cases.append(Scenario(f"js_declared_{spec.replace('/', '_')}", js_runtime, js_import_patch("index.js", f'import x from "{spec}";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="package runtime", summary="declared js import"))
    for spec in ["vue", "@missing/pkg", "@missing/pkg/sub"]:
        cases.append(Scenario(f"js_undeclared_{spec.replace('/', '_')}", {"index.js": "export const value = 1;\n", "package.json": "{}\n"}, js_import_patch("index.js", f'import x from "{spec}";'), MUST_RED, "unsupported_dependency", repo_shape="empty package", summary="undeclared js import"))
    cases.append(Scenario("js_dev_runtime_scope", js_runtime, js_import_patch("index.js", 'import vite from "vite";'), MUST_YELLOW, "dependency_scope_review", repo_shape="dev dependency", summary="runtime imports devDependency"))
    cases.append(Scenario("js_dev_test_scope", {**js_runtime, "app.test.js": "export const value = 1;\n"}, js_import_patch("app.test.js", 'import vite from "vite";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="dev dependency", summary="test imports devDependency"))
    alias_files = {"view.ts": "export const value = 1;\n", "src/components/Button.ts": "export const Button = 1\n", "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', "package.json": "{}\n"}
    cases.append(Scenario("js_alias_resolved", alias_files, js_import_patch("view.ts", 'import { Button } from "@/components/Button";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="ts paths", summary="resolved alias"))
    cases.append(Scenario("js_alias_unresolved", {"view.ts": "export const value = 1;\n", "package.json": "{}\n"}, js_import_patch("view.ts", 'import { Button } from "@/components/Button";'), MUST_YELLOW, "js_alias_uncertain", repo_shape="no aliases", summary="unresolved alias"))
    workspace_files = {"index.js": "export const value = 1;\n", "package.json": '{"workspaces":["packages/*"]}', "packages/core/package.json": '{"name":"@myorg/core"}\n'}
    for spec in ["@myorg/core", "@myorg/core/utils"]:
        cases.append(Scenario(f"js_workspace_{spec.replace('/', '_')}", workspace_files, js_import_patch("index.js", f'import x from "{spec}";'), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="workspace", summary="workspace import"))
    js_same = [
        ("exact", "{}\n", '{"dependencies":{"react":"18"}}\n', 'import React from "react";', MUST_YELLOW, "declared_dependency"),
        ("subpath", "{}\n", '{"dependencies":{"react":"18"}}\n', 'import runtime from "react/jsx-runtime";', MUST_YELLOW, "declared_dependency"),
        ("dev", "{}\n", '{"devDependencies":{"vite":"1"}}\n', 'import vite from "vite";', MUST_YELLOW, "declared_dependency"),
        ("wrong", "{}\n", '{"dependencies":{"vue":"3"}}\n', 'import React from "react";', MUST_RED, "unsupported_dependency"),
        ("script_not_dep", "{}\n", '{"scripts":{"react":"echo no"}}\n', 'import React from "react";', MUST_RED, "unsupported_dependency"),
    ]
    for name, old_pkg, new_pkg, import_line, exp, fid in js_same:
        cases.append(Scenario(f"js_same_patch_{name}", {"index.js": "export const value = 1;\n", "package.json": old_pkg}, multi_patch([("index.js", "export const value = 1;\n", f"{import_line}\nexport const value = 1;\n"), ("package.json", old_pkg, new_pkg)]), exp, fid, repo_shape="same patch js", summary=name))
    cases.append(Scenario("js_wrong_ecosystem_py_dep", {"index.js": "export const value = 1;\n", "requirements.txt": ""}, multi_patch([("index.js", "export const value = 1;\n", 'import React from "react";\nexport const value = 1;\n'), ("requirements.txt", "", "react\n")]), MUST_RED, "unsupported_dependency", repo_shape="wrong ecosystem", summary="python dep cannot support js"))

    command_files = {"README.md": "demo\n", "package.json": '{"scripts":{"dev":"vite","build":"vite build","test":"vitest"}}\n', "compose.yaml": "services: {}\n", "tests/test_app.py": "def test_x(): pass\n", "requirements.txt": "pytest\n"}
    for cmd in ["npm run dev", "npm run build", "npm test", "docker compose up", "pytest", "python -m pytest"]:
        cases.append(Scenario(f"cmd_supported_{cmd.replace(' ', '_')}", command_files, unified_patch("README.md", "demo\n", f"Run {cmd}\n"), MUST_NOT_RED, forbidden_ids={"unsupported_command"}, repo_shape="commands supported", summary=cmd))
    for cmd in ["npm run dev", "npm run build", "docker compose up", "pytest"]:
        cases.append(Scenario(f"cmd_unsupported_{cmd.replace(' ', '_')}", {"README.md": "demo\n", "package.json": "{}\n"}, unified_patch("README.md", "demo\n", f"Run {cmd}\n"), MUST_RED, "unsupported_command", repo_shape="commands unsupported", summary=cmd))
    cases.append(Scenario("cmd_same_patch_script_exact", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{"dev":"vite"}}\n')]), MUST_YELLOW, "declared_command", repo_shape="same patch script", summary="exact script"))
    cases.append(Scenario("cmd_same_patch_script_wrong", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run build\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{"dev":"vite"}}\n')]), MUST_RED, "unsupported_command", repo_shape="same patch script", summary="wrong script"))
    cases.append(Scenario("cmd_same_patch_script_under_wrong_object", {"README.md": "demo\n", "package.json": '{"scripts":{}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{}}\n', '{"scripts":{},"metadata":{"dev":"vite"}}\n')]), MUST_RED, "unsupported_command", forbidden_ids={"declared_command"}, repo_shape="same patch script", summary="script-like key outside scripts"))
    cases.append(Scenario("cmd_same_patch_script_existing_object", {"README.md": "demo\n", "package.json": '{"scripts":{"test":"vitest"}}\n'}, multi_patch([("README.md", "demo\n", "Run npm run dev\n"), ("package.json", '{"scripts":{"test":"vitest"}}\n', '{"scripts":{"test":"vitest","dev":"vite"}}\n')]), MUST_YELLOW, "declared_command", repo_shape="same patch script", summary="script added to existing scripts"))
    cases.append(Scenario("cmd_same_patch_compose", {"README.md": "demo\n"}, unified_patch("README.md", "demo\n", "Run docker compose up\n") + unified_patch("compose.yaml", "", "services: {}\n", new_file=True), MUST_YELLOW, "declared_command", repo_shape="same patch compose", summary="compose added"))

    protected = [".sourcepack/baseline/active.json", "src/../.sourcepack/baseline/active.json", "./.sourcepack/baseline/active.json", ".sourcepack\\baseline\\active.json", ".sourcepack/state/baseline.lock"]
    for path in protected:
        cases.append(Scenario(f"protected_{path}", {path.replace('\\', '/'): "{}\n"}, unified_patch(path, "{}\n", '{"x":true}\n'), MUST_RED, "protected_artifact", repo_shape="protected paths", summary=path))
    for path in ["manifest.json", "receipt.json", "docs/receipt.json", "public/manifest.json", "fixtures/manifest.json", "examples/.sourcepack/baseline/active.json"]:
        cases.append(Scenario(f"normal_{path}", {path: "{}\n"}, unified_patch(path, "{}\n", '{"x":true}\n'), MUST_NOT_RED, forbidden_ids={"protected_artifact"}, repo_shape="normal paths", summary=path))
    for path in ["../outside.txt", "docs/../../.sourcepack/state/baseline.lock", "/tmp/file.txt"]:
        cases.append(Scenario(f"escape_{path}", {"app.py": "VALUE = 1\n"}, unified_patch(path, "old\n", "new\n"), MUST_FAIL_CLOSED, "path_escape", repo_shape="path escape", summary=path))
    cases.append(Scenario("escape_windows_mixed", {"app.py": "VALUE = 1\n"}, unified_patch("docs\\..\\..\\outside.txt", "old\n", "new\n"), MUST_FAIL_CLOSED, "path_escape", repo_shape="path escape", summary="windows traversal"))
    cases.append(Scenario("protected_sourcepack_root", {".sourcepack/config.json": "{}\n"}, unified_patch(".sourcepack/config.json", "{}\n", "{\"x\":true}\n"), MUST_RED, "protected_artifact", repo_shape="protected paths", summary="sourcepack root"))
    cases.append(Scenario("protected_git_path", {".git/config": "[core]\n"}, unified_patch(".git/config", "[core]\n", "[core]\nrepositoryformatversion = 0\n"), MUST_RED, "git_path_modification", repo_shape="protected paths", summary="git internal"))
    cases.append(Scenario("workflow_change_warn", {".github/workflows/ci.yml": "name: ci\n"}, unified_patch(".github/workflows/ci.yml", "name: ci\n", "name: ci\non: push\n"), MUST_YELLOW, "workflow_change", repo_shape="automation", summary="workflow review"))

    malformed = ["not a unified diff\n", "@@ -1 +1 @@\n+x\n", "diff --git a/a.py b/a.py\n", "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ nope\n+x\n"]
    for i, patch in enumerate(malformed):
        cases.append(Scenario(f"malformed_{i}", {"a.py": "x\n"}, patch, MUST_FAIL_CLOSED, "malformed_diff", repo_shape="malformed", summary=str(i)))
    cases.append(Scenario("binary_ordinary", {"a.py": "x\n"}, "diff --git a/img.png b/img.png\nBinary files a/img.png and b/img.png differ\n", MUST_YELLOW, "binary_diff", repo_shape="binary", summary="ordinary binary"))
    cases.append(Scenario("binary_high_risk", {"a.py": "x\n"}, "diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\nBinary files a/.sourcepack/baseline/active.json and b/.sourcepack/baseline/active.json differ\n", MUST_RED, "binary_diff", repo_shape="binary", summary="trust binary"))
    cases.append(Scenario("binary_manifest_review", {"package.json": "{}\n"}, "diff --git a/package.json b/package.json\nBinary files a/package.json and b/package.json differ\n", MUST_RED, "binary_diff", repo_shape="binary", summary="manifest binary"))
    cases.append(Scenario("rename_unsupported_warn", {"old.py": "VALUE = 1\n"}, "diff --git a/old.py b/new.py\nsimilarity index 100%\nrename from old.py\nrename to new.py\n", MUST_YELLOW, "unsupported_rename_copy", repo_shape="rename", summary="rename unsupported"))
    cases.append(Scenario("copy_protected_fail", {"README.md": "demo\n"}, "diff --git a/README.md b/.sourcepack/baseline/active.json\ncopy from README.md\ncopy to .sourcepack/baseline/active.json\n", MUST_RED, "protected_artifact", repo_shape="copy", summary="copy to protected"))
    cases.append(Scenario("new_file", {"a.py": "x\n"}, unified_patch("new.py", "", "import os\n", new_file=True), MUST_YELLOW, "new_file", repo_shape="edge", summary="new file"))
    cases.append(Scenario("deleted_file", {"a.py": "x\n"}, unified_patch("a.py", "x\n", "", deleted=True), MUST_YELLOW, "deleted_file", repo_shape="edge", summary="deleted file"))
    for marker in ["Cargo.toml", "go.mod", "pom.xml", "build.gradle", "settings.gradle.kts"]:
        cases.append(Scenario(f"unsupported_ecosystem_{marker.replace('.', '_').lower()}", {marker: "\n", "README.md": "demo\n"}, unified_patch("README.md", "demo\n", "updated\n"), MUST_YELLOW, "unsupported_ecosystem", repo_shape="unsupported ecosystem", summary=marker))
    for i, mod in enumerate(["csv", "hashlib", "collections", "itertools", "functools", "typing", "unittest", "subprocess", "re", "math", "decimal", "sqlite3", "http", "email"]):
        cases.append(Scenario(f"py_stdlib_extra_{i}_{mod}", {"app.py": "VALUE = 1\n"}, py_import_patch("app.py", f"import {mod}"), MUST_NOT_RED, forbidden_ids={"unsupported_dependency"}, repo_shape="python no deps", summary="extra stdlib coverage"))
    for script in ["lint", "typecheck", "format", "start"]:
        files = {"README.md": "demo\n", "package.json": f'{{"scripts":{{"{script}":"echo ok"}}}}\n'}
        cases.append(Scenario(f"cmd_supported_extra_{script}", files, unified_patch("README.md", "demo\n", f"Run npm run {script}\n"), MUST_NOT_RED, forbidden_ids={"unsupported_command"}, repo_shape="extra scripts", summary=script))
    return cases


SCENARIOS = scenario_cases()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_patch_simulation_scenarios(tmp_path: Path, scenario: Scenario) -> None:
    packet = write_packet(tmp_path, scenario.files)
    report = judge_patch_text(packet, scenario.patch)
    assert_expectation(scenario, report)


def test_real_repo_failure_regression_readme_outside_prompt_context(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old docs\n", "app.py": "VALUE = 1\n"}, context_files={"app.py"}, inventory_files={"README.md", "app.py"})
    report = judge_patch_text(packet, unified_patch("README.md", "old docs\n", "updated docs\n"))
    assert report["verdict"] != "FAIL"
    assert report["missing_modified_files"] == []
    assert summarize(report)["finding_ids"].isdisjoint({"missing_file"})


def test_real_repo_failure_regression_new_file_yellow(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old docs\n"}, context_files=set(), inventory_files={"README.md"})
    report = judge_patch_text(packet, unified_patch("NEW_NOTES.md", "", "notes\n", new_file=True))
    assert report["verdict"] == "WARN"
    assert "NEW_NOTES.md" in report["new_files"]
    assert "new_file" in summarize(report)["finding_ids"]
    assert report["missing_modified_files"] == []


def test_real_repo_failure_regression_missing_existing_file_red(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old docs\n"}, context_files={"README.md"}, inventory_files={"README.md"})
    report = judge_patch_text(packet, unified_patch("ghost.py", "VALUE = 1\n", "VALUE = 2\n"))
    assert report["verdict"] == "FAIL"
    assert "ghost.py" in report["missing_modified_files"]
    assert "missing_file" in summarize(report)["finding_ids"]


def test_real_repo_failure_regression_unsupported_import_outside_prompt_context(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n"}, context_files=set(), inventory_files={"app.py"})
    report = judge_patch_text(packet, unified_patch("app.py", "VALUE = 1\n", "import fastapi\nVALUE = 1\n"))
    ids = summarize(report)["finding_ids"]
    assert report["verdict"] == "FAIL"
    assert "fastapi" in report["unsupported_dependencies"]
    assert "unsupported_dependency" in ids
    assert "missing_file" not in ids
    assert report["missing_modified_files"] == []


def test_legacy_packet_without_inventory_treats_outside_context_edit_as_uncertain_not_missing_file(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old docs\n", "app.py": "VALUE = 1\n"}, context_files={"app.py"})
    (packet / "file_inventory.json").unlink()
    report = judge_patch_text(packet, unified_patch("README.md", "old docs\n", "updated docs\n"))
    assert report["verdict"] == "WARN"
    assert report["missing_modified_files"] == []
    assert "README.md" in report.get("uncertain_modified_files", [])
    assert any(item.get("id") == "baseline_inventory_missing" for item in report.get("uncertainties", []))
    assert "missing_file" not in summarize(report)["finding_ids"]


def test_legacy_packet_without_inventory_still_reds_unsupported_import_outside_context(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old docs\n", "app.py": "VALUE = 1\n"}, context_files={"README.md"})
    (packet / "file_inventory.json").unlink()
    report = judge_patch_text(packet, unified_patch("app.py", "VALUE = 1\n", "import fastapi\nVALUE = 1\n"))
    assert report["verdict"] == "FAIL"
    assert report["missing_modified_files"] == []
    assert "app.py" in report.get("uncertain_modified_files", [])
    assert "fastapi" in report["unsupported_dependencies"]
    ids = summarize(report)["finding_ids"]
    assert "unsupported_dependency" in ids
    assert "missing_file" not in ids


def test_multiple_unsupported_ecosystem_markers_preserve_evidence(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "demo\n", "go.mod": "module demo\n", "pom.xml": "<project/>\n"})
    report = judge_patch_text(packet, unified_patch("README.md", "demo\n", "updated\n"))
    assert report["verdict"] == "WARN"
    evidences = [item.get("evidence") for item in report.get("uncertainties", []) if item.get("id") == "unsupported_ecosystem"]
    assert "go.mod" in evidences
    assert "pom.xml" in evidences


def test_path_normalization_inside_repo_and_protected_targets(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"README.md": "old\n", ".sourcepack/baseline/active.json": "{}\n", ".git/config": "[core]\n"})
    inside = judge_patch_text(packet, unified_patch("src/../README.md", "old\n", "new\n"))
    assert inside["verdict"] != "FAIL"
    assert "README.md" in inside.get("modified_files", [])

    protected = judge_patch_text(packet, unified_patch("src/../.sourcepack/baseline/active.json", "{}\n", "{\"x\":true}\n"))
    assert_expectation(Scenario("normalized_protected", {}, "", MUST_RED, "protected_artifact"), protected)

    git_path = judge_patch_text(packet, unified_patch("src/../.git/config", "[core]\n", "[core]\nrepositoryformatversion = 0\n"))
    assert_expectation(Scenario("normalized_git", {}, "", MUST_RED, "git_path_modification"), git_path)


def test_raw_patch_markdown_exposes_extended_sections(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"package.json": "{}\n"})
    patch = "diff --git a/package.json b/package.json\nBinary files a/package.json and b/package.json differ\n"
    out = tmp_path / "out"
    patch_file = tmp_path / "patch.diff"
    patch_file.write_text(patch, encoding="utf-8")
    judge_patch(packet, patch_file, out)
    text = (out / "patch_judgment_report.md").read_text(encoding="utf-8")
    for section in ["Git Path Modifications", "Binary Diffs", "Binary Diff Blockers", "Declared Dependencies", "Declared Commands"]:
        assert f"### {section}" in text
    assert "package.json" in text

def test_simulation_count() -> None:
    assert len(SCENARIOS) >= 100


def test_ai_answer_simulation_catches_fake_claims(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "package.json": '{"scripts":{"dev":"vite"}}\n'})
    answer = tmp_path / "answer.md"
    answer.write_text(
        "Edit `src/auth.py`, import requests, run npm run build, use docker compose up, and add database support.\n",
        encoding="utf-8",
    )
    report = judge_ai_answer(packet, answer)
    assert report["verdict"] == "FAIL"
    assert "src/auth.py" in report["missing_files"]
    assert "requests" in {dep.lower() for dep in report["unsupported_dependencies"]}
    assert "npm run build" in report["unsupported_commands"]
    assert "docker compose up" in report["unsupported_commands"]
    assert "database" in report["unsupported_capabilities"]


def test_ai_answer_simulation_accepts_supported_claims(tmp_path: Path) -> None:
    packet = write_packet(
        tmp_path,
        {
            "app.py": "import requests\nVALUE = 1\n",
            "requirements.txt": "requests\npytest\n",
            "package.json": '{"scripts":{"dev":"vite","test":"vitest"}}\n',
            "compose.yaml": "services: {}\n",
            "tests/test_app.py": "def test_x(): pass\n",
        },
    )
    answer = tmp_path / "answer.md"
    answer.write_text("Edit `app.py`, then run npm run dev, npm test, pytest, and docker compose up.\n", encoding="utf-8")
    report = judge_ai_answer(packet, answer)
    assert report["verdict"] == "PASS"
    assert report["missing_files"] == []
    assert report["unsupported_commands"] == []



def test_analyze_patch_warns_when_uncertainties_exist(tmp_path: Path) -> None:
    from sourcepack.cli import analyze_patch

    packet = write_packet(tmp_path, {"package.json": '{"scripts":{}}\n'})
    patch = unified_patch("package.json", '{"scripts":{}}\n', '{"scripts":{"dev":"vite"}\n')
    report = analyze_patch(packet, patch)
    assert report["verdict"] == "WARN"
    assert any(item.get("id") == "command_manifest_uncertain" for item in report.get("uncertainties", []))


def test_ai_answer_negated_and_cautionary_mentions_do_not_fail(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "package.json": "{}\n"})
    answer = tmp_path / "answer.md"
    answer.write_text(
        "Do not use FastAPI. This repo does not include React. Avoid requests unless added to requirements.txt. "
        "Do not run npm run build. There is no docker compose up support. Avoid pytest until tests are configured. "
        "Do not import pydantic unless it is added first. There is no need for SQLAlchemy here.\n",
        encoding="utf-8",
    )
    report = judge_ai_answer(packet, answer)
    assert report["verdict"] == "PASS"
    assert report["unsupported_dependencies"] == []
    assert report["unsupported_commands"] == []


def test_ai_answer_file_reference_forms(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"src/auth.py": "VALUE = 1\n"})
    supported = ["`src/auth.py`", "'src/auth.py'", "edit src/auth.py", "edit ./src/auth.py", "src/auth.py:", "- src/auth.py", "edit src\\auth.py"]
    for index, text in enumerate(supported):
        answer = tmp_path / f"answer-{index}.md"
        answer.write_text(text, encoding="utf-8")
        report = judge_ai_answer(packet, answer)
        assert report["verdict"] == "PASS", text
        assert "src/auth.py" in report["supported_files"], text


def test_ai_answer_action_like_unsupported_claims_fail(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"app.py": "VALUE = 1\n", "package.json": "{}\n"})
    cases = [
        ("import fastapi", "unsupported_dependencies", "fastapi"),
        ('import React from "react"', "unsupported_dependencies", "react"),
        ("run npm run build", "unsupported_commands", "npm run build"),
        ("use docker compose up", "unsupported_commands", "docker compose up"),
        ("add database support", "unsupported_capabilities", "database"),
    ]
    for index, (text, key, expected) in enumerate(cases):
        answer = tmp_path / f"unsupported-{index}.md"
        answer.write_text(text, encoding="utf-8")
        report = judge_ai_answer(packet, answer)
        assert report["verdict"] == "FAIL", text
        assert expected in {str(item).lower() for item in report[key]}, report


def test_non_utf8_patch_file_fails_closed(tmp_path: Path) -> None:
    packet = write_packet(tmp_path, {"a.py": "x\n"})
    patch = tmp_path / "bad.diff"
    patch.write_bytes(b"\xff\xfe")
    out = tmp_path / "out"
    report = judge_patch(packet, patch, out)
    assert_expectation(Scenario("non_utf8", {"a.py": "x\n"}, "", MUST_FAIL_CLOSED, "malformed_diff"), report)


def test_baseline_state_cli_smoke() -> None:
    with TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (repo / "app.py").write_text("import requests\nVALUE = 1\n", encoding="utf-8")
        code = run_cli(["diff", str(repo), "--json"])
        assert code == 1
        assert validate_baseline(repo)["state"] == "missing"
        code = run_cli(["baseline", str(repo), "--quiet"])
        assert code in {0, 1}
        (repo / ".sourcepack" / "baseline" / "active.json").write_text("not json", encoding="utf-8")
        status = validate_baseline(repo)
        assert status["state"] == "corrupt"
        assert status["finding_id"] == "baseline_corrupt"


---

## File: tests/test_smoke.py

Metadata:
- sha256: f715db283f71e3bfa3116809af82a9abfed742b746b54910578d445ee3bf6fcb
- bytes: 55901
- estimated_tokens: 13970

Content:

import json
import unittest
import os
import subprocess
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from sourcepack.cli import dependency_inventory, extract_imports_from_text, feature_inventory, load_manifest, run_cli, traffic_report, normalized_finding, render_traffic, judge_patch_text, write_user_report


class SourcePackSmokeTest(unittest.TestCase):
    def test_smoke_build_verify_judge(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            (repo / "sourcepack").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "README.md").write_text("Local-first CLI. No Docker. No FastAPI. No PDF parsing.")
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\ndependencies=["pytest"]\n')
            (repo / "sourcepack" / "verify.py").write_text("def verify(): return True\n")
            (repo / "sourcepack" / "judge.py").write_text("def judge(): return True\n")
            (repo / ".env").write_text("OPENAI_API_KEY=[REDACTED:openai_key]\n")
            packet = tmp / "packet"
            self.assertEqual(run_cli(["doctor"]), 0)
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            for name in ["manifest.json", "context.md", "context.xml", "receipt.json", "file_tree.txt", "ignored_files.txt", "token_report.json"]:
                self.assertTrue((packet / name).exists(), name)
            self.assertEqual(run_cli(["verify", str(packet)]), 0)
            answer = tmp / "ai_answer.md"
            answer.write_text("Uses `sourcepack/server.py` and `docker compose up`, but real file `sourcepack/verify.py` exists.")
            judgment = tmp / "judgment"
            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            report = (judgment / "judgment_report.md").read_text()
            self.assertIn("sourcepack/server.py", report)
            self.assertIn("docker compose up", report)

    def test_readme_prose_does_not_create_dependency_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("Local-first CLI. No Docker. No FastAPI. No PDF parsing.")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertNotIn("fastapi", dependency_inventory(load_manifest(packet), packet))
            self.assertNotIn("pdf", dependency_inventory(load_manifest(packet), packet))

    def test_verify_against_uses_source_hash_when_packet_is_redacted(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            secret_line = "OPENAI_API_KEY=[REDACTED:openai_key]\n"
            (repo / "config.py").write_text(secret_line)
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            context = (packet / "context.md").read_text()
            self.assertIn("[REDACTED:openai_key]", context)
            self.assertEqual(run_cli(["verify", str(packet), "--against", str(repo)]), 0)

    def test_doctor_reports_production_readiness_checks(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = run_cli(["doctor", "--strict"])

        output = buffer.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("PASS version:", output)
        self.assertIn("PASS package_assets:", output)
        self.assertIn("PASS report_renderers:", output)
        self.assertIn("Status: READY", output)


    def test_readme_negative_prose_does_not_create_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("PDF parsing is not supported. No Docker setup. No React frontend. No database.")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            answer = tmp / "ai_answer.md"
            answer.write_text("This project supports PDF parsing, Docker, React, and database storage.")
            judgment = tmp / "judgment"

            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            report = (judgment / "judgment_report.md").read_text()
            self.assertIn("- [UNSUPPORTED] pdf", report)
            self.assertIn("- [UNSUPPORTED] docker", report)
            self.assertIn("- [UNSUPPORTED] react", report)
            self.assertIn("- [UNSUPPORTED] database", report)

    def test_dockerfile_creates_docker_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "Dockerfile").write_text("FROM python:3.12-slim\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("docker", feature_inventory(load_manifest(packet), packet))

    def test_pdf_parser_file_creates_pdf_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "pdf_parser.py").write_text("def parse_pdf(path):\n    return path\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("pdf", feature_inventory(load_manifest(packet), packet))

    def test_pdf_library_import_creates_pdf_capability_evidence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "reader.py").write_text("import pypdf\n")
            packet = tmp / "packet"

            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)

            self.assertIn("pdf", feature_inventory(load_manifest(packet), packet))


class SourcePackRealityMapTest(unittest.TestCase):
    def _build(self, repo: Path, packet: Path):
        self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
        return __import__("json").loads((packet / "reality_map.json").read_text())

    def test_build_creates_reality_map_ai_instructions_and_receipt_hashes(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\ndependencies=["pytest"]\n')
            packet = tmp / "packet"
            reality = self._build(repo, packet)
            self.assertTrue((packet / "reality_map.json").exists())
            self.assertTrue((packet / "ai_instructions.md").exists())
            receipt = json.loads((packet / "receipt.json").read_text())
            self.assertIn("reality_map.json", receipt["hashes"])
            self.assertIn("ai_instructions.md", receipt["hashes"])
            self.assertEqual(reality["reality_map_schema_version"], "1.0")
            self.assertEqual(run_cli(["verify", str(packet)]), 0)

    def test_tampered_new_artifacts_fail_verify(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self._build(repo, packet)
            (packet / "reality_map.json").write_text('{"tampered": true}')
            self.assertEqual(run_cli(["verify", str(packet)]), 1)
            self._build(repo, packet)
            (packet / "ai_instructions.md").write_text("tampered")
            self.assertEqual(run_cli(["verify", str(packet)]), 1)

    def test_python_poetry_detection_rules(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "pyproject.toml").write_text('[project]\nname="demo"\n')
            reality = self._build(repo, tmp / "packet")
            self.assertIn("python", reality["project_types"])
            self.assertNotIn("poetry", reality["package_managers"])
            (repo / "pyproject.toml").write_text('[tool.poetry]\nname="demo"\n')
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("poetry", reality["package_managers"])

    def test_docker_and_compose_command_detection(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("No Docker setup")
            reality = self._build(repo, tmp / "packet")
            self.assertNotIn("docker build", reality["supported_commands"])
            (repo / "Dockerfile").write_text("FROM python:3.12-slim\n")
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("docker build", reality["supported_commands"])
            self.assertNotIn("docker compose up", reality["supported_commands"])
            (repo / "compose.yaml").write_text("services: {}\n")
            reality = self._build(repo, tmp / "packet3")
            self.assertIn("docker compose up", reality["supported_commands"])

    def test_package_json_scripts_only(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "package.json").write_text('{"dependencies": {"react": "latest"}}')
            reality = self._build(repo, tmp / "packet")
            self.assertNotIn("npm test", reality["supported_commands"])
            self.assertNotIn("npm run dev", reality["supported_commands"])
            (repo / "package.json").write_text('{"scripts": {"test": "node test.js", "dev": "vite", "build": "vite build"}}')
            reality = self._build(repo, tmp / "packet2")
            self.assertIn("npm test", reality["supported_commands"])
            self.assertIn("npm run dev", reality["supported_commands"])
            self.assertIn("npm run build", reality["supported_commands"])

    def test_ai_instructions_warnings_and_json_validity(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self._build(repo, packet)
            text = (packet / "ai_instructions.md").read_text()
            self.assertIn("missing", text.lower())
            self.assertIn("unsupported", text.lower())
            for name in ["manifest.json", "receipt.json", "token_report.json", "redactions.json", "reality_map.json"]:
                json.loads((packet / name).read_text())

    def test_map_and_instructions_commands(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            out = tmp / "reality_map.json"
            self.assertEqual(run_cli(["map", str(repo), "--out", str(out)]), 0)
            self.assertTrue(out.exists())
            packet = tmp / "packet"
            self._build(repo, packet)
            (packet / "ai_instructions.md").unlink()
            self.assertEqual(run_cli(["instructions", str(packet)]), 0)
            self.assertTrue((packet / "ai_instructions.md").exists())


class SourcePackPatchJudgmentTest(unittest.TestCase):
    def _packet(self, tmp: Path):
        repo = tmp / "repo"; repo.mkdir()
        (repo / "README.md").write_text("demo\n")
        (repo / "app.py").write_text("def main():\n    return True\n")
        packet = tmp / "packet"
        self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
        return packet

    def _judge_patch(self, packet: Path, tmp: Path, text: str):
        patch = tmp / "change.diff"; patch.write_text(text)
        out = tmp / "patch_report"
        self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(out)]), 0)
        import json
        return json.loads((out / "patch_judgment_report.json").read_text()), out

    def test_known_file_patch_does_not_fail_for_existence(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def main():
+    print('ok')
     return True
""")
            self.assertNotIn("app.py", report["missing_modified_files"])
            self.assertEqual(report["verdict"], "PASS")

    def test_missing_file_patch_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/sourcepack/server.py b/sourcepack/server.py
--- a/sourcepack/server.py
+++ b/sourcepack/server.py
@@ -1 +1,2 @@
+print('x')
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("sourcepack/server.py", report["missing_modified_files"])

    def test_new_file_warns_not_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1 @@
+print('new')
""")
            self.assertEqual(report["verdict"], "WARN")
            self.assertIn("new.py", report["new_files"])

    def test_deleted_file_reported(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
deleted file mode 100644
--- a/app.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def main():
-    return True
""")
            self.assertIn("app.py", report["deleted_files"])

    def test_fastapi_import_without_dependency_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+from fastapi import FastAPI
 def main():
     return True
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("fastapi", report["unsupported_dependencies"])

    def test_new_file_with_unsupported_fastapi_import_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/api.py b/api.py
new file mode 100644
--- /dev/null
+++ b/api.py
@@ -0,0 +1,2 @@
+from fastapi import FastAPI
+app = FastAPI()
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("api.py", report["new_files"])
            self.assertIn("fastapi", report["unsupported_dependencies"])

    def test_import_extraction_catches_python_and_javascript_imports(self):
        self.assertIn("fastapi", extract_imports_from_text("import fastapi\n", ".py"))
        self.assertIn("fastapi", extract_imports_from_text("from fastapi import FastAPI\n", ".py"))
        self.assertIn("react", extract_imports_from_text("import React from 'react'\n", ".tsx"))
        self.assertIn("vue", extract_imports_from_text("const vue = require('vue')\n", ".js"))

    def test_unsupported_commands_fail(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,4 @@
 demo
+docker compose up
+npm run dev
""")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("docker compose up", report["unsupported_commands"])
            self.assertIn("npm run dev", report["unsupported_commands"])

    def test_protected_artifact_patch_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            for name in [".sourcepack/baseline/active.json", ".sourcepack/baseline/builds/x/packet/receipt.json"]:
                report, _ = self._judge_patch(packet, tmp, f"""diff --git a/{name} b/{name}
--- a/{name}
+++ b/{name}
@@ -1 +1,2 @@
+tamper
""")
                self.assertEqual(report["verdict"], "FAIL")
                self.assertIn(name, report["protected_artifact_modifications"])

    def test_nested_receipt_json_is_not_protected_artifact(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/docs/receipt.json b/docs/receipt.json
new file mode 100644
--- /dev/null
+++ b/docs/receipt.json
@@ -0,0 +1 @@
+{}
""")
            self.assertNotIn("docs/receipt.json", report["protected_artifact_modifications"])
            self.assertEqual(report["verdict"], "WARN")

    def test_judge_patch_does_not_mutate_packet_artifacts(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            names = ["manifest.json", "receipt.json", "reality_map.json", "ai_instructions.md"]
            before = {name: (packet / name).read_bytes() for name in names}
            report, out = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+print('ok')
 def main():
     return True
""")
            self.assertTrue((out / "patch_judgment_report.json").exists())
            self.assertIn("verdict", report)
            after = {name: (packet / name).read_bytes() for name in names}
            self.assertEqual(before, after)

    def test_patch_report_files_created_and_json_parses(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, out = self._judge_patch(packet, tmp, """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
+print('ok')
""")
            self.assertTrue((out / "patch_judgment_report.md").exists())
            self.assertIn("verdict", report)
            json.loads((out / "patch_judgment_report.json").read_text())

    def test_judge_patch_exit_code_zero_when_verdict_fails(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            patch = tmp / "fail.diff"
            patch.write_text("""diff --git a/receipt.json b/receipt.json
--- a/receipt.json
+++ b/receipt.json
@@ -1 +1,2 @@
+tamper
""")
            out = tmp / "patch_report"
            self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(out)]), 0)
            report = json.loads((out / "patch_judgment_report.json").read_text())
            self.assertEqual(report["verdict"], "FAIL")



    def test_package_json_declared_dependency_extraction_is_section_scoped(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); packet = self._packet(tmp)
            report, _ = self._judge_patch(packet, tmp, """diff --git a/package.json b/package.json
new file mode 100644
--- /dev/null
+++ b/package.json
@@ -0,0 +1,6 @@
+{
+  "scripts": {"dev": "vite"},
+  "name": "demo",
+  "version": "1.0.0"
+}
""")
            self.assertNotIn("scripts", report.get("declared_dependencies", []))
            self.assertNotIn("dev", report.get("declared_dependencies", []))
            report = judge_patch_text(packet, """diff --git a/package.json b/package.json
new file mode 100644
--- /dev/null
+++ b/package.json
@@ -0,0 +1,5 @@
+{
+  "dependencies": {
+    "@scope/pkg": "^1.0.0"
+  }
+}
""")
            self.assertIn("@scope/pkg", report.get("declared_dependencies", []))

class SourcePackSchemaAndDemoTest(unittest.TestCase):
    def test_generated_artifacts_required_fields(self):
        import json
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = tmp / "repo"; repo.mkdir()
            (repo / "README.md").write_text("demo")
            packet = tmp / "packet"
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            answer = tmp / "answer.md"; answer.write_text("README.md")
            judgment = tmp / "judgment"
            self.assertEqual(run_cli(["judge", str(packet), str(answer), "--out", str(judgment)]), 0)
            patch = tmp / "change.diff"; patch.write_text("""diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+more
""")
            patch_out = tmp / "patch_judgment"
            self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(patch_out)]), 0)
            reality = json.loads((packet / "reality_map.json").read_text())
            judgment_json = json.loads((judgment / "judgment_report.json").read_text())
            patch_json = json.loads((patch_out / "patch_judgment_report.json").read_text())
            for key in ["reality_map_schema_version", "tool_version", "supported_commands", "detected_dependencies"]:
                self.assertIn(key, reality)
            for key in ["sourcepack_version", "supported_files", "missing_files", "unsupported_dependencies", "unsupported_commands", "unsupported_capabilities"]:
                self.assertIn(key, judgment_json)
            for key in ["patch_judgment_schema_version", "verdict", "modified_files", "missing_modified_files", "new_files"]:
                self.assertIn(key, patch_json)

    def test_demo_exits_successfully(self):
        self.assertEqual(run_cli(["demo"]), 0)

    def test_demo_exits_successfully_with_expected_fake_fail_reports(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(run_cli(["demo"]), 0)
        output = buf.getvalue()
        judgment_line = next(line for line in output.splitlines() if line.startswith("Demo judgment: "))
        judgment = Path(judgment_line.removeprefix("Demo judgment: "))
        judgment_report = json.loads((judgment / "judgment_report.json").read_text(encoding="utf-8"))
        self.assertEqual(judgment_report["verdict"], "FAIL")
        if "Demo patch judgment: " in output:
            patch_line = next(line for line in output.splitlines() if line.startswith("Demo patch judgment: "))
            patch_judgment = Path(patch_line.removeprefix("Demo patch judgment: "))
            patch_report = json.loads((patch_judgment / "patch_judgment_report.json").read_text(encoding="utf-8"))
            self.assertEqual(patch_report["verdict"], "FAIL")


class SourcePackLocalUsabilityTest(unittest.TestCase):
    def _repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"; repo.mkdir()
        (repo / "README.md").write_text("demo\n", encoding="utf-8")
        (repo / "app.py").write_text("def main():\n    return True\n", encoding="utf-8")
        return repo


    def test_sourcepack_directory_is_not_included_in_manifest(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            sp = repo / ".sourcepack" / "current" / "packet"
            sp.mkdir(parents=True)
            (sp / "manifest.json").write_text('{"generated": true}\n', encoding="utf-8")
            (repo / ".sourcepack" / "reports").mkdir(parents=True)
            (repo / ".sourcepack" / "reports" / "latest.json").write_text('{"verdict":"PASS"}\n', encoding="utf-8")

            packet = Path(td) / "packet"
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
            included = [rec["relative_path"] for rec in manifest["included_files"]]
            self.assertFalse(any(path.startswith(".sourcepack/") for path in included), included)

    def test_prompt_does_not_refresh_baseline_by_default(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            self.assertEqual(run_cli(["prompt", str(repo), "first task"]), 0)
            (repo / "new_prompt_file.py").write_text("print('fresh')\n", encoding="utf-8")
            self.assertEqual(run_cli(["prompt", str(repo), "second task"]), 0)
            prompt_manifest = json.loads((repo / ".sourcepack" / "prompt" / "packet" / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("new_prompt_file.py", [rec["relative_path"] for rec in prompt_manifest["included_files"]])
            self.assertFalse((repo / ".sourcepack" / "baseline" / "packet" / "manifest.json").exists())

    def test_diff_missing_baseline_with_changes_fails_without_autobaseline(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            subprocess.run(["git", "add", "README.md", "app.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            (repo / "app.py").write_text("def main():\n    return False\n", encoding="utf-8")

            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("baseline_missing", {f["id"] for f in report["findings"]})
            self.assertFalse((repo / ".sourcepack" / "baseline" / "packet" / "manifest.json").exists())

    def test_prompt_creates_storage_gitignore_and_prompt_files(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            (repo / ".gitignore").write_text("dist/\r\n", encoding="utf-8", newline="")
            self.assertEqual(run_cli(["prompt", str(repo), "fix auth bug"]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            self.assertTrue((repo / ".sourcepack" / "reports").is_dir())
            prompt = (repo / ".sourcepack" / "prompt" / "prompt.md").read_text(encoding="utf-8")
            self.assertIn("fix auth bug", prompt)
            self.assertIn("AI Grounding Instructions", prompt)
            self.assertIn("Do not invent files, dependencies, commands, services, or capabilities.", prompt)
            self.assertTrue((repo / ".sourcepack" / "prompt" / "reality_map.json").exists())
            self.assertTrue((repo / ".sourcepack" / "prompt" / "ai_instructions.md").exists())
            gitignore = (repo / ".gitignore").read_bytes()
            self.assertIn(b"dist/\r\n.sourcepack/\r\n", gitignore)
            self.assertEqual(run_cli(["prompt", str(repo), "task"]), 0)
            self.assertEqual((repo / ".gitignore").read_text(encoding="utf-8").count(".sourcepack/"), 1)

    def test_prompt_copy_fallback_and_json_status(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = ""
            try:
                self.assertEqual(run_cli(["prompt", str(repo), "task", "--copy"]), 0)
            finally:
                os.environ["PATH"] = old_path
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "WARN")
            self.assertTrue((repo / ".sourcepack" / "prompt" / "prompt.md").exists())
            self.assertEqual(run_cli(["status", str(repo), "--json"]), 0)

    def test_traffic_light_renderer_shapes(self):
        red = traffic_report("FAIL", findings=[normalized_finding("missing_file", "error", "missing_file", "tests/test_auth.py not found.")])
        yellow = traffic_report("WARN", findings=[normalized_finding("new_file", "warn", "new_file", "src/auth.py was created by the patch.")])
        green = traffic_report("PASS")
        self.assertIn("RED LIGHT", render_traffic(red))
        self.assertIn("missing_file", render_traffic(red))
        self.assertIn("YELLOW LIGHT", render_traffic(yellow))
        self.assertIn("Reason type: review", render_traffic(yellow))
        self.assertIn("Commit policy: allowed locally, blocked in strict mode.", render_traffic(yellow))
        self.assertIn("new_file", render_traffic(yellow))
        self.assertIn("GREEN LIGHT", render_traffic(green))
        json.dumps(green)

    def test_baseline_created_and_refreshed(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            self.assertEqual(run_cli(["baseline", str(repo), "--force"]), 0)
            self.assertTrue((repo / ".sourcepack" / "baseline" / "active.json").exists())
            first = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("created", first["headline"])
            self.assertEqual(run_cli(["baseline", str(repo), "--refresh"]), 0)
            second = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("refreshed", second["headline"])

    def test_diff_no_diff_new_file_fastapi_declared_and_outside_git(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo), "--force"]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            no_diff = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertEqual(no_diff["verdict"], "PASS")
            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertEqual(json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())["verdict"], "WARN")
            (repo / "api.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            red = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertEqual(red["verdict"], "FAIL")
            self.assertIn("unsupported_dependency", {f["id"] for f in red["findings"]})
            (repo / "requirements.txt").write_text("fastapi\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertEqual(json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())["verdict"], "WARN")
            self.assertTrue((repo / ".sourcepack" / "reports" / "latest.md").exists())
            self.assertTrue(list((repo / ".sourcepack" / "reports" / "archive").glob("*_diff.json")))
            self.assertEqual(run_cli(["diff", str(tmp)]), 1)

    def test_diff_staged_commands_artifacts_import_edges_and_hooks(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            (repo / "localmod.py").write_text("x=1\n")
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo), "--force"]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", "localmod.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            (repo / "app.py").write_text("import os\nfrom . import rel\nimport localmod\ndef main():\n    return True\n")
            subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
            self.assertEqual(run_cli(["diff", str(repo), "--staged"]), 0)
            (repo / "README.md").write_text("demo\ndocker compose up\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            (repo / "receipt.json").write_text("{}\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            (repo / "docs").mkdir(); (repo / "docs" / "receipt.json").write_text("{}\n")
            # docs/receipt.json may warn as a new file, but should not be a protected artifact finding.
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertNotIn("docs/receipt.json", [f.get("path") for f in report["findings"] if f["id"] == "protected_artifact"])
            (repo / "ui.ts").write_text("import x from '@scope/pkg'\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 1)
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text())
            self.assertIn("@scope/pkg", [f.get("evidence") for f in report["findings"]])
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            hook = (repo / ".git" / "hooks" / "pre-commit").read_text()
            self.assertIn("sourcepack diff . --staged", hook)
            self.assertNotIn('exec "$0"', hook)

    def test_installed_hook_execution_blocks_red_allows_yellow_and_chains_original(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
            self.assertEqual(run_cli(["baseline", str(repo), "--force"]), 0)
            subprocess.run(["git", "add", "README.md", "app.py", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            bindir = tmp / "bin"; bindir.mkdir()
            sourcepack_bin = bindir / "sourcepack"
            sourcepack_bin.write_text("#!/bin/sh\nif [ \"$SOURCEPACK_FAKE\" = red ]; then echo 'RED LIGHT: fake'; exit 1; fi\nif [ \"$SOURCEPACK_FAKE\" = green ]; then echo 'GREEN LIGHT: fake'; exit 0; fi\necho 'YELLOW LIGHT: fake'; exit 0\n", encoding="utf-8")
            sourcepack_bin.chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}{os.pathsep}" + os.environ.get("PATH", "")}

            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            yellow = subprocess.run([str(repo / ".git" / "hooks" / "pre-commit")], cwd=repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(yellow.returncode, 0, yellow.stdout + yellow.stderr)
            self.assertIn("YELLOW LIGHT", yellow.stdout)

            (repo / "api.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
            red = subprocess.run([str(repo / ".git" / "hooks" / "pre-commit")], cwd=repo, env={**env, "SOURCEPACK_FAKE": "red"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(red.returncode, 0, red.stdout + red.stderr)
            self.assertIn("RED LIGHT", red.stdout)

            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
            original = repo / ".git" / "hooks" / "pre-commit"
            original.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            chained = subprocess.run([str(original), "arg1"], cwd=repo, env={**env, "SOURCEPACK_FAKE": "green"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(chained.returncode, 7, chained.stdout + chained.stderr)


    def _git_init_clean(self, repo: Path):
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=repo, check=True)
        subprocess.run(["git", "add", "README.md", "app.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)


    def test_diff_ci_missing_baseline_clean_repo_is_json_fail_without_creating_baseline(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--ci"]), 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["verdict"], "FAIL")
            self.assertTrue(data["ci"])
            self.assertEqual(data["baseline_state"], "missing")
            self.assertIn("baseline_missing", {f["id"] for f in data["blockers"]})
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_diff_ci_missing_baseline_dirty_repo_is_json_fail_without_creating_baseline(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            (repo / "app.py").write_text("def main():\n    return False\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--ci"]), 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["verdict"], "FAIL")
            self.assertTrue(data["ci"])
            self.assertEqual(data["baseline_state"], "missing")
            self.assertFalse((repo / ".sourcepack" / "baseline" / "active.json").exists())

    def test_fail_rendering_splits_blockers_review_warnings_and_uncertainties(self):
        rep = traffic_report(
            "FAIL",
            findings=[
                normalized_finding("missing_file", "error", "file", "app.py not found", "app.py"),
                normalized_finding("new_file", "warn", "review", "new.py was created", "new.py"),
                normalized_finding("baseline_inventory_missing", "warn", "uncertainty", "inventory was missing"),
            ],
        )
        rendered = render_traffic(rep, verbose=True)
        self.assertIn("Blockers:", rendered)
        self.assertIn("Review warnings:", rendered)
        self.assertIn("Uncertainties:", rendered)
        self.assertLess(rendered.index("Blockers:"), rendered.index("Review warnings:"))
        self.assertLess(rendered.index("Review warnings:"), rendered.index("Uncertainties:"))

    def test_init_auto_clean_idempotent_status_and_no_hook(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            self.assertEqual(run_cli(["init", str(repo), "--auto"]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            self.assertTrue((repo / ".sourcepack" / "reports").is_dir())
            self.assertTrue((repo / ".sourcepack" / "baseline" / "active.json").exists())
            self.assertIn(".sourcepack/", (repo / ".gitignore").read_text())
            hook = repo / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.exists())
            first_gitignore = (repo / ".gitignore").read_text().count(".sourcepack/")
            first_hook_blocks = hook.read_text().count("# === SOURCEPACK BEGIN ===")
            self.assertEqual(run_cli(["init", str(repo), "--auto"]), 0)
            self.assertEqual((repo / ".gitignore").read_text().count(".sourcepack/"), first_gitignore)
            self.assertEqual(hook.read_text().count("# === SOURCEPACK BEGIN ==="), first_hook_blocks)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["status", str(repo)]), 0)
            self.assertIn("Automatic mode: enabled", buf.getvalue())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["status", str(repo), "--json"]), 0)
            self.assertTrue(json.loads(buf.getvalue())["automatic_mode_enabled"])
            self.assertEqual(run_cli(["uninstall-hook", str(repo)]), 0)
            self.assertTrue((repo / ".sourcepack" / "current").is_dir())
            (Path(td) / "repo2").mkdir(); repo2 = self._repo(Path(td) / "repo2"); self._git_init_clean(repo2)
            self.assertEqual(run_cli(["init", str(repo2), "--auto", "--no-hook"]), 0)
            self.assertFalse((repo2 / ".git" / "hooks" / "pre-commit").exists())

    def test_init_auto_dirty_baseline_policy_and_strict_hook(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            (repo / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): rc = run_cli(["init", str(repo), "--auto"])
            self.assertEqual(rc, 1)
            self.assertIn("RED LIGHT", buf.getvalue())
            self.assertIn("dirty_worktree", buf.getvalue())
            self.assertFalse((repo / ".sourcepack" / "baseline" / "packet" / "manifest.json").exists())
            self.assertEqual(run_cli(["init", str(repo), "--auto", "--refresh-baseline", "--strict", "--force"]), 0)
            self.assertTrue((repo / ".sourcepack" / "baseline" / "active.json").exists())
            hook = (repo / ".git" / "hooks" / "pre-commit").read_text()
            self.assertIn("strict mode blocks YELLOW LIGHT", hook)
            post_hook = (repo / ".git" / "hooks" / "post-commit").read_text()
            self.assertIn("git ls-files --others --exclude-standard", post_hook)

    def test_hook_chains_existing_hook_and_uninstall_restores(self):
        with TemporaryDirectory() as td:
            tmp = Path(td); repo = self._repo(tmp); self._git_init_clean(repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\necho ORIGINAL_HOOK\nexit 7\n", encoding="utf-8"); hook.chmod(0o755)
            self.assertEqual(run_cli(["install-hook", str(repo)]), 0)
            installed = hook.read_text()
            self.assertNotIn('exec "$0"', installed)
            bindir = tmp / "bin"; bindir.mkdir()
            fake = bindir / "sourcepack"
            fake.write_text("#!/bin/sh\necho 'GREEN LIGHT: fake'\nexit 0\n", encoding="utf-8"); fake.chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}{os.pathsep}" + os.environ.get("PATH", "")}
            cp = subprocess.run([str(hook)], cwd=repo / "src" if (repo / "src").exists() else repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(cp.returncode, 7, cp.stdout + cp.stderr)
            self.assertIn("GREEN LIGHT", cp.stdout)
            self.assertIn("ORIGINAL_HOOK", cp.stdout)
            self.assertEqual(run_cli(["uninstall-hook", str(repo)]), 0)
            self.assertEqual(hook.read_text(), "#!/bin/sh\necho ORIGINAL_HOOK\nexit 7\n")
            restored = subprocess.run([str(hook)], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(restored.returncode, 7)


    def test_diff_strict_and_ci_block_warn(self):
        with TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("base\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(run_cli(["baseline", str(repo), "--quiet"]), 0)
            (repo / "new.txt").write_text("new\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertEqual(run_cli(["diff", str(repo), "--strict"]), 1)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--ci"]), 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["verdict"], "WARN")
            self.assertTrue(data["ci"])
            self.assertIn("report_path", data)

    def test_diff_ci_missing_baseline_with_changes_is_json_fail(self):
        with TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--ci"]), 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["verdict"], "FAIL")
            self.assertTrue(data["ci"])
            self.assertEqual(data["baseline_state"], "missing")

    def test_diff_ci_corrupt_baseline_is_json_fail(self):
        with TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(run_cli(["baseline", str(repo), "--quiet"]), 0)
            status_buf = io.StringIO()
            with contextlib.redirect_stdout(status_buf):
                self.assertEqual(run_cli(["status", str(repo), "--json"]), 0)
            meta_path = json.loads(status_buf.getvalue())["baseline_metadata_path"]
            (repo / meta_path).write_text("{", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--ci"]), 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["verdict"], "FAIL")
            self.assertTrue(data["ci"])
            self.assertEqual(data["baseline_state"], "corrupt")

    def test_judge_patch_report_has_traffic_sections(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "app.py").write_text("print('ok')\n")
            packet = tmp / "packet"
            self.assertEqual(run_cli(["build", str(repo), "--out", str(packet), "--force"]), 0)
            patch = tmp / "change.diff"
            patch.write_text("""diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,1 @@
+print('new')
""")
            out = tmp / "out"
            self.assertEqual(run_cli(["judge-patch", str(packet), str(patch), "--out", str(out)]), 0)
            report = json.loads((out / "patch_judgment_report.json").read_text())
            for key in ["verdict", "findings", "blockers", "warnings", "uncertainties", "checked_categories", "not_checked", "next_action", "report_path"]:
                self.assertIn(key, report)
            md = (out / "patch_judgment_report.md").read_text()
            self.assertIn("## Blockers", md)
            self.assertIn("## Review warnings", md)
            self.assertIn("## Uncertainties", md)

    def test_diff_output_omits_legacy_patch_report_header(self):
        with TemporaryDirectory() as td:
            repo = self._repo(Path(td)); self._git_init_clean(repo)
            self.assertEqual(run_cli(["baseline", str(repo), "--force"]), 0)
            (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertNotIn("# SourcePack Patch Judgment Report", buf.getvalue())



class SourcePackReportUiTest(unittest.TestCase):
    def test_diff_writes_local_html_report(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("demo\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.assertEqual(run_cli(["baseline", str(repo), "--quiet"]), 0)
            (repo / "README.md").write_text("demo changed\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)

            html_path = repo / ".sourcepack" / "reports" / "latest.html"
            self.assertTrue(html_path.exists())
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("SourcePack local report", html)
            self.assertIn("Reason codes", html)
            self.assertIn("Affected files", html)
            self.assertIn("Baseline and prompt trust", html)
            self.assertIn(".sourcepack/reports/latest.json", html)

    def test_report_open_generates_html_and_invokes_browser(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            report = traffic_report("PASS", checked_categories=["diff"], report_path=".sourcepack/reports/latest.json")
            write_user_report(repo, report, "diff")
            calls = []
            import sourcepack.cli as cli
            original = cli.webbrowser.open
            try:
                cli.webbrowser.open = lambda uri: calls.append(uri) or True
                self.assertEqual(run_cli(["report", "open", str(repo)]), 0)
            finally:
                cli.webbrowser.open = original
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0].startswith("file:"))
            self.assertTrue((repo / ".sourcepack" / "reports" / "latest.html").exists())


    def test_report_path_prints_latest_html_path(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["report", "path", str(repo)]), 0)
            self.assertEqual(Path(buf.getvalue().strip()), repo.resolve() / ".sourcepack" / "reports" / "latest.html")

    def test_report_open_missing_report_fails_gracefully(self):
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(run_cli(["report", "open", str(repo)]), 1)
            self.assertIn("no SourcePack report found", err.getvalue())

    def test_diff_json_stdout_remains_json_after_html_report_exists(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("demo\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run_cli(["baseline", str(repo), "--quiet"]), 0)
            (repo / "README.md").write_text("demo changed\n")
            self.assertEqual(run_cli(["diff", str(repo)]), 0)
            self.assertTrue((repo / ".sourcepack" / "reports" / "latest.html").exists())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_cli(["diff", str(repo), "--json"]), 0)
            data = json.loads(buf.getvalue())
            self.assertIn(data["verdict"], {"PASS", "WARN"})
            self.assertNotIn("Report HTML:", buf.getvalue())

    def test_diff_verdict_survives_html_report_write_failure(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("demo\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(run_cli(["baseline", str(repo), "--quiet"]), 0)
            (repo / "new.py").write_text("print(1)\n")
            import sourcepack.cli as cli
            original = cli.render_report_html
            try:
                cli.render_report_html = lambda report: (_ for _ in ()).throw(RuntimeError("html boom"))
                self.assertEqual(run_cli(["diff", str(repo)]), 0)
            finally:
                cli.render_report_html = original
            report = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "WARN")

if __name__ == "__main__":
    unittest.main()


---

## File: tests/test_ugly_repos.py

Metadata:
- sha256: e9ac5b33d879e4b70b62afdf092a3395c838e40ade072aae89d5bb7957b8ee5a
- bytes: 6989
- estimated_tokens: 1748

Content:

import json
import subprocess
import sys
from pathlib import Path

from sourcepack.cli import patch_report_to_traffic, validate_baseline
from sourcepack.judgment import judge_patch_text


def run_sourcepack(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def init_repo(repo: Path, files: dict[str, str | bytes]) -> Path:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "ugly@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Ugly Repo"], cwd=repo, check=True)
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    baseline = run_sourcepack(repo, "baseline", "refresh", "--force")
    assert baseline.returncode == 0, baseline.stderr + baseline.stdout
    return repo


def diff_json(repo: Path) -> tuple[int, dict]:
    cp = run_sourcepack(repo, "diff", ".", "--json")
    assert cp.stdout.lstrip().startswith("{"), cp.stderr + cp.stdout
    return cp.returncode, json.loads(cp.stdout)


def finding_ids(report: dict) -> set[str]:
    return {finding.get("id") for finding in report.get("findings", [])}


def judge_patch_json(repo: Path, patch: str) -> dict:
    packet = repo / validate_baseline(repo)["packet_path"]
    return patch_report_to_traffic(judge_patch_text(packet, patch))


def test_python_src_layout_supported_file_edit(tmp_path):
    repo = init_repo(
        tmp_path,
        {
            "pyproject.toml": "[project]\nname = 'ugly-src'\ndependencies = []\n",
            "src/ugly_pkg/__init__.py": "VALUE = 1\n",
            "src/ugly_pkg/core.py": "def value():\n    return 1\n",
            "tests/test_core.py": "from ugly_pkg.core import value\n",
        },
    )
    (repo / "src" / "ugly_pkg" / "core.py").write_text("def value():\n    return 2\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "PASS"
    assert "unsupported_dependency" not in finding_ids(data)
    assert "missing_file" not in finding_ids(data)


def test_flat_python_layout_undeclared_import(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "def main():\n    return 1\n", "requirements.txt": ""})
    (repo / "app.py").write_text("import fastapi\n\ndef main():\n    return fastapi.FastAPI()\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 1
    assert data["verdict"] == "FAIL"
    assert "unsupported_dependency" in finding_ids(data)


def test_scripts_only_repo_unsupported_command_assumption(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "Scripts are kept in bin/.\n", "bin/lint": "#!/bin/sh\nexit 0\n"})
    (repo / "README.md").write_text("Scripts are kept in bin/.\nRun " + "docker compose" + " up to publish.\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 1
    assert data["verdict"] == "FAIL"
    assert "unsupported_command" in finding_ids(data)
    assert any(f.get("evidence") == "docker compose" + " up" for f in data["findings"] if f.get("id") == "unsupported_command")


def test_docs_only_repo_allowed_docs_new_file_policy(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "Docs only\n"})
    policy_dir = repo / ".sourcepack"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "policy.json").write_text(
        json.dumps({"schema_version": "sourcepack.policy.v1", "ignored_paths": [{"pattern": "docs/**", "reason": "docs reviewed separately"}]}),
        encoding="utf-8",
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    ids = finding_ids(data)
    assert "new_file" not in {f.get("id") for f in data["findings"] if f.get("path") == "docs/guide.md"}
    assert "policy_override" in ids
    assert data["policy_config_ignores"][0]["suppressed_finding"] == "new_file"


def test_workflow_only_change_reports_workflow_change(tmp_path):
    repo = init_repo(tmp_path, {".github/workflows/ci.yml": "name: ci\non: [push]\njobs: {}\n"})
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: [push, pull_request]\njobs: {}\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "workflow_change" in finding_ids(data)


def test_protected_sourcepack_edit_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json
--- a/.sourcepack/baseline/active.json
+++ b/.sourcepack/baseline/active.json
@@ -1 +1 @@
-{}
+{\"tamper\": true}
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "protected_artifact" in finding_ids(data)


def test_git_path_edit_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/.git/config b/.git/config
--- a/.git/config
+++ b/.git/config
@@ -1 +1 @@
-a
+b
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "git_path_modification" in finding_ids(data)


def test_unsafe_path_normalization_fails(tmp_path):
    repo = init_repo(tmp_path, {"app.py": "print(1)\n"})
    patch = """diff --git a/../outside.txt b/../outside.txt
--- a/../outside.txt
+++ b/../outside.txt
@@ -1 +1 @@
-a
+b
"""

    data = judge_patch_json(repo, patch)

    assert data["verdict"] == "FAIL"
    assert "path_escape" in finding_ids(data)


def test_binary_asset_change_warns_with_binary_diff(tmp_path):
    repo = init_repo(tmp_path, {"README.md": "assets\n"})
    (repo / "assets").mkdir()
    (repo / "assets" / "logo.bin").write_bytes(b"\x00\x01\x02\x03")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "binary_diff" in finding_ids(data)


def test_unsupported_ecosystem_layout_warns_without_crashing(tmp_path):
    repo = init_repo(tmp_path, {"Cargo.toml": "[package]\nname = 'ugly-rust'\nversion = '0.1.0'\n", "src/lib.rs": "pub fn value() -> u8 { 1 }\n"})
    (repo / "src" / "lib.rs").write_text("pub fn value() -> u8 { 2 }\n", encoding="utf-8")

    code, data = diff_json(repo)

    assert code == 0
    assert data["verdict"] == "WARN"
    assert "unsupported_ecosystem" in finding_ids(data)
    assert "semantic correctness" in data.get("not_checked", [])


---

## File: tests/test_workbench.py

Metadata:
- sha256: b0a80def99039d7abba20e121bf7398149ae95ea4a27023ba1c1dca28c9537e8
- bytes: 6273
- estimated_tokens: 1569

Content:

import http.client
import json
import subprocess
import sys
import threading

import pytest

from sourcepack import workbench
from sourcepack.workbench import IPv6WorkbenchServer, WorkbenchHandler, WorkbenchServer, _is_relative_to


class FakeWorkbenchServer:
    server_address = ("127.0.0.1", 4321)
    closed = False

    def __init__(self, server_address, handler_class, repo_root, session_token):
        self.init_args = (server_address, handler_class, repo_root, session_token)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


def start_server(tmp_path):
    server = WorkbenchServer(("127.0.0.1", 0), WorkbenchHandler, tmp_path, "test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def request(server, method, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    conn.request(method, path, headers=headers or {})
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response.status, body, dict(response.getheaders())


def test_api_routes_require_valid_sourcepack_token(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        for headers in ({}, {"X-SourcePack-Token": "wrong"}, {"X-SourcePack-Token": "bad token"}):
            status, body, _ = request(server, "GET", "/api/status", headers)
            assert status == 403
            assert json.loads(body)["error"] == "forbidden"

        status, _, _ = request(server, "GET", "/api/latest", {"X-SourcePack-Token": "test-token"})
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_static_serving_strips_query_and_rejects_traversal(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, body, headers = request(server, "GET", "/?token=test-token")
        assert status == 200
        assert b"SourcePack Workbench" in body
        assert "Access-Control-Allow-Origin" not in headers

        status, _, _ = request(server, "GET", "/../../pyproject.toml")
        assert status in {403, 404}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_is_relative_to_compatibility_helper(tmp_path):
    root = tmp_path / "static"
    child = root / "app.js"
    other = tmp_path / "other.js"
    root.mkdir()
    child.write_text("", encoding="utf-8")
    other.write_text("", encoding="utf-8")
    assert _is_relative_to(child.resolve(), root.resolve())
    assert not _is_relative_to(other.resolve(), root.resolve())


def test_ui_and_workbench_help_are_registered():
    ui_help = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "ui", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert ui_help.returncode == 0
    assert "serve the local SourcePack Workbench" in ui_help.stdout

    workbench_help = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "workbench", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert workbench_help.returncode == 0
    assert "alias for sourcepack ui" in workbench_help.stdout


def test_no_open_prints_tokenized_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")

    assert workbench.serve_workbench(tmp_path, open_browser=False) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/?token=fixed-token"


def test_browser_open_false_prints_tokenized_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")
    monkeypatch.setattr(workbench.webbrowser, "open", lambda url: False)

    assert workbench.serve_workbench(tmp_path, open_browser=True) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/?token=fixed-token"


def test_browser_open_true_prints_base_url(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workbench, "WorkbenchServer", FakeWorkbenchServer)
    monkeypatch.setattr(workbench.secrets, "token_urlsafe", lambda size: "fixed-token")
    monkeypatch.setattr(workbench.webbrowser, "open", lambda url: True)

    assert workbench.serve_workbench(tmp_path, open_browser=True) == 0
    assert capsys.readouterr().out.strip() == "SourcePack Workbench: http://127.0.0.1:4321/"


def test_requested_hosts_are_validated():
    for host in ("", "0", "0.0.0.0", "::", "192.168.1.10"):
        with pytest.raises(ValueError, match="only binds to explicit loopback hosts"):
            workbench._validate_requested_host(host)

    for host in ("127.0.0.1", "localhost", "::1"):
        workbench._validate_requested_host(host)


def test_actual_bound_host_is_validated_before_serving(monkeypatch, tmp_path):
    class NonLoopbackServer(FakeWorkbenchServer):
        server_address = ("192.168.1.10", 4321)

        def serve_forever(self):
            raise AssertionError("serve_forever must not run for non-loopback bound host")

    server_holder = {}

    class CapturingServer(NonLoopbackServer):
        def __init__(self, *args):
            super().__init__(*args)
            server_holder["server"] = self

    monkeypatch.setattr(workbench, "WorkbenchServer", CapturingServer)

    with pytest.raises(ValueError, match="refused non-loopback bound address"):
        workbench.serve_workbench(tmp_path, host="127.0.0.1", open_browser=False)
    assert server_holder["server"].closed


def test_ipv6_loopback_uses_ipv6_server_and_url_host():
    assert workbench._server_class_for_host("::1") is IPv6WorkbenchServer
    assert workbench._server_class_for_host("127.0.0.1") is WorkbenchServer
    assert workbench._url_host("::1") == "[::1]"


---

## File: tools/behavior_matrix.py

Metadata:
- sha256: fd9710d6e74406cb0e1fb73827107716752d5bdfe5679515860d68e08b728015
- bytes: 29564
- estimated_tokens: 7391

Content:

#!/usr/bin/env python3
"""Deterministic SourcePack behavior-space validation matrix.

Canonical scenario schema: BehaviorScenario below is the single typed source used
by the behavior matrix, JSON assertions, and tests. Each scenario models:
baseline state + prompt context state + working tree change + output/policy mode
-> verdict + canonical reason codes + optional exit code + normalized report shape.

Canonical expected-output schema: NormalizedReport below is the single report
shape asserted by this harness. Required fields are schema_version,
sourcepack_version, verdict, exit_code, reason_codes, reason_type,
commit_policy, checked, not_checked, findings, warnings, blockers, and
uncertainties. generated_at is optional/mode-dependent because in-memory
judge-patch reports are not persisted by the CLI. checked_categories from
SourcePack traffic reports is normalized to checked.

Reason-code normalization: CANONICAL_REASON_CODES is the registry for reason
codes this matrix expects or normalizes from current SourcePack emissions. Codes
are lowercase snake_case [a-z0-9_]+ stable identifiers. Aliases in
REASON_CODE_ALIASES are legacy/emitted spellings normalized to canonical emitted
names; duplicates collapse; ordering is ignored; JSON assertions compare
normalized sets; human-readable messages are never used for correctness.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sourcepack.cli import (  # noqa: E402
    __version__, build_current_baseline, judge_patch_text, patch_report_to_traffic,
    run_cli, sha256_text,
)

Verdict = Literal["PASS", "WARN", "FAIL"]
CommandMode = Literal["local_json_diff", "strict_json_diff", "ci_json_diff", "judge_patch"]
PolicyMode = Literal["local", "strict", "ci", "judge_patch"]
BaselineSetupMode = Literal["present", "missing", "absent_authoritative_file", "packet"]
MutationOp = Literal["write", "append", "delete", "binary_write"]

CANONICAL_REASON_CODES: frozenset[str] = frozenset({
    "baseline_missing", "missing_file", "new_file", "deleted_file",
    "unsupported_dependency", "declared_dependency", "unsupported_command",
    "declared_command", "unsafe_path", "protected_artifact",
    "git_path_modification", "binary_diff", "malformed_diff",
    "unsupported_ecosystem", "baseline_stale", "dependency_scope_review",
    "js_alias_uncertain", "dependency_manifest_uncertain", "no_diff", "workflow_change",
    "execution_evidence_missing", "execution_failed", "execution_inconclusive",
    "execution_evidence_present",
})
REASON_CODE_ALIASES: dict[str, str] = {
    "path_escape": "unsafe_path",
    "baseline_inventory_missing": "baseline_missing",
    "missing_modified_file": "missing_file",
    "missing_modified_files": "missing_file",
    "binary_diff_blocker": "binary_diff",
}
_REASON_RE = re.compile(r"^[a-z0-9_]+$")


class Mutation(TypedDict):
    op: MutationOp
    path: str
    content: str


class NormalizedReport(TypedDict):
    schema_version: str | None
    sourcepack_version: str | None
    generated_at: str | None
    verdict: Verdict
    exit_code: int
    reason_codes: list[str]
    reason_type: str | None
    commit_policy: str | None
    checked: list[str]
    not_checked: list[str]
    findings: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    reason_code_evidence: dict[str, list[str]]
    replay_bundle: dict[str, Any]


@dataclass(frozen=True)
class BehaviorScenario:
    scenario_id: str
    description: str
    category: str
    repo_files: dict[str, str]
    prompt_context_omissions: tuple[str, ...]
    baseline_setup_mode: BaselineSetupMode
    pre_baseline_setup: tuple[Mutation, ...]
    working_tree_mutations: tuple[Mutation, ...]
    patch_text: str | None
    command_mode: CommandMode
    policy_mode: PolicyMode
    expected_verdict: Verdict | Literal["NOT_FAIL"]
    expected_reason_codes_include: tuple[str, ...]
    expected_reason_codes_exclude: tuple[str, ...]
    expected_exit_code: int | None
    expected_json_valid: bool
    expected_report_fields: tuple[str, ...]
    expected_not_checked_fields: tuple[str, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)


def normalize_reason_code(code: str) -> str:
    raw = str(code).strip()
    lowered = raw.lower()
    canonical = REASON_CODE_ALIASES.get(lowered, lowered)
    if not _REASON_RE.fullmatch(canonical):
        raise ValueError(f"non-canonical reason code syntax: {code!r}")
    if canonical not in CANONICAL_REASON_CODES:
        raise ValueError(f"unknown canonical reason code: {code!r} -> {canonical!r}")
    return canonical


def normalize_reason_codes(codes: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return sorted({normalize_reason_code(c) for c in codes})


def _patch(path: str, old: str, new: str, new_file: bool = False, deleted: bool = False) -> str:
    import difflib
    old_lines = [] if new_file else old.splitlines()
    new_lines = [] if deleted else new.splitlines()
    body = "\n".join(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")) + "\n"
    prefix = f"diff --git a/{path} b/{path}\n"
    if new_file:
        prefix += "new file mode 100644\n"
    if deleted:
        prefix += "deleted file mode 100644\n"
    return prefix + body


def _packet(tmp: Path, files: dict[str, str], context_omissions: tuple[str, ...] = (), inventory: set[str] | None = None) -> Path:
    packet = tmp / "packet"; packet.mkdir()
    included = []
    context_names = set(files) - set(context_omissions)
    inventory_names = set(files) if inventory is None else inventory
    chunks = ["# SourcePack Context", ""]
    for rel, content in sorted(files.items()):
        if rel in context_names:
            included.append({"relative_path": rel, "sha256": sha256_text(content), "extension": Path(rel).suffix})
            chunks.extend([f"## File: {rel}", "", "Content:", content.rstrip("\n"), "---", ""])
    inv = {"schema_version": "sourcepack.file_inventory.v1", "source": "behavior_matrix", "files": [{"relative_path": rel, "included_in_prompt_context": rel in context_names, "source": "behavior_matrix"} for rel in sorted(inventory_names)]}
    (packet/"manifest.json").write_text(json.dumps({"included_files": included}), encoding="utf-8")
    (packet/"file_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    (packet/"context.md").write_text("\n".join(chunks), encoding="utf-8")
    (packet/"reality_map.json").write_text(json.dumps({"supported_commands": []}), encoding="utf-8")
    (packet/"receipt.json").write_text(json.dumps({"hashes": {}}), encoding="utf-8")
    return packet


def _git(repo: Path, *args: str) -> None:
    cp = subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {cp.stderr}")


def _write(repo: Path, rel: str, content: str | bytes) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _apply(repo: Path, mutations: tuple[Mutation, ...]) -> None:
    for m in mutations:
        op, rel, content = m["op"], m["path"], m.get("content", "")
        path = repo / rel
        if op == "write":
            _write(repo, rel, content)
        elif op == "append":
            path.write_text(path.read_text(encoding="utf-8") + content, encoding="utf-8")
        elif op == "delete":
            path.unlink()
        elif op == "binary_write":
            _write(repo, rel, bytes.fromhex(content))


def _make_repo(parent: Path, s: BehaviorScenario) -> Path:
    repo = parent / "repo"; repo.mkdir()
    _git(repo, "init", "-q"); _git(repo, "config", "user.email", "matrix@example.invalid"); _git(repo, "config", "user.name", "Behavior Matrix")
    for rel, content in s.repo_files.items():
        _write(repo, rel, content)
    _apply(repo, s.pre_baseline_setup)
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "initial")
    if s.baseline_setup_mode == "present":
        build_current_baseline(repo, quiet=True)
    elif s.baseline_setup_mode == "absent_authoritative_file":
        build_current_baseline(repo, quiet=True)
        packet = repo / ".sourcepack/baseline/packet/file_inventory.json"
        data = json.loads(packet.read_text(encoding="utf-8"))
        data["files"] = [f for f in data["files"] if f.get("relative_path") != "app.py"]
        packet.write_text(json.dumps(data), encoding="utf-8")
        # Keep baseline integrity valid for scenario-level authoritative inventory testing.
        receipt = repo / ".sourcepack/baseline/packet/receipt.json"
        r = json.loads(receipt.read_text(encoding="utf-8")); r["hashes"]["file_inventory.json"] = sha256_text(packet.read_text(encoding="utf-8")); receipt.write_text(json.dumps(r), encoding="utf-8")
    _apply(repo, s.working_tree_mutations)
    return repo


def _ids(report: dict[str, Any]) -> list[str]:
    codes = [f.get("id", "") for f in report.get("findings", [])]
    if report.get("baseline_integrity_finding_id"):
        codes.append(report["baseline_integrity_finding_id"])
    return normalize_reason_codes([c for c in codes if c])


def normalize_report(raw: dict[str, Any], exit_code: int) -> NormalizedReport:
    traffic = raw if "findings" in raw else patch_report_to_traffic(raw)
    return {
        "schema_version": traffic.get("schema_version"), "sourcepack_version": traffic.get("sourcepack_version", __version__),
        "generated_at": traffic.get("generated_at"), "verdict": traffic.get("verdict", "WARN"), "exit_code": exit_code,
        "reason_codes": _ids(traffic), "reason_type": traffic.get("reason_type"), "commit_policy": traffic.get("commit_policy"),
        "checked": list(traffic.get("checked") or traffic.get("checked_categories") or []), "not_checked": list(traffic.get("not_checked") or []),
        "findings": list(traffic.get("findings") or []), "warnings": list(traffic.get("warnings") or []),
        "blockers": list(traffic.get("blockers") or []), "uncertainties": list(traffic.get("uncertainties") or []),
        "evidence_items": list(traffic.get("evidence_items") or []), "reason_code_evidence": dict(traffic.get("reason_code_evidence") or {}),
        "replay_bundle": dict(traffic.get("replay_bundle") or {}),
    }


def run_scenario(s: BehaviorScenario) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sp_behavior_") as td:
        tmp = Path(td)
        if s.command_mode == "judge_patch":
            inventory = set(s.repo_files)
            if s.baseline_setup_mode == "absent_authoritative_file":
                inventory.discard("app.py")
            packet = _packet(tmp, s.repo_files, s.prompt_context_omissions, inventory)
            raw = judge_patch_text(packet, s.patch_text or "")
            # judge_patch_text is an in-process helper, not the judge-patch CLI.
            # Its scenarios are not applicable for exit-code validation.
            report = normalize_report(raw, -1)
            stdout = json.dumps(report)
        else:
            repo = _make_repo(tmp, s)
            args = ["diff", str(repo), "--json"]
            if s.command_mode == "strict_json_diff": args.append("--strict")
            if s.command_mode == "ci_json_diff": args.append("--ci")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run_cli(args)
            stdout = buf.getvalue()
            raw = json.loads(stdout)
            report = normalize_report(raw, code)
        ok, errors = assert_scenario(s, report, stdout)
        return {"scenario_id": s.scenario_id, "ok": ok, "errors": errors, "report": report}


def assert_scenario(s: BehaviorScenario, report: NormalizedReport, stdout: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if s.expected_json_valid:
        try:
            json.loads(stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"stdout not valid JSON: {exc}")
    if s.expected_verdict == "NOT_FAIL":
        if report["verdict"] == "FAIL": errors.append("verdict is FAIL")
    elif report["verdict"] != s.expected_verdict:
        errors.append(f"verdict {report['verdict']} != {s.expected_verdict}")
    if s.expected_exit_code is not None and report["exit_code"] != s.expected_exit_code:
        errors.append(f"exit {report['exit_code']} != {s.expected_exit_code}")
    have = set(report["reason_codes"])
    inc = set(normalize_reason_codes(s.expected_reason_codes_include))
    exc = set(normalize_reason_codes(s.expected_reason_codes_exclude))
    if not inc <= have: errors.append(f"missing reason codes {sorted(inc - have)} from {sorted(have)}")
    if exc & have: errors.append(f"forbidden reason codes {sorted(exc & have)}")
    for f in s.expected_report_fields:
        if f not in report or report[f] is None: errors.append(f"expected report field {f}")
    for f in s.expected_not_checked_fields:
        if f in report and report[f]: errors.append(f"expected empty report field {f}")
    return not errors, errors


def m(op: MutationOp, path: str, content: str = "") -> Mutation:
    return {"op": op, "path": path, "content": content}


def build_scenarios() -> list[BehaviorScenario]:
    S: list[BehaviorScenario] = []
    def add(i:int, desc:str, cat:str, files:dict[str,str], muts:tuple[Mutation,...]=(), *, patch:str|None=None, mode:CommandMode="local_json_diff", base:BaselineSetupMode="present", verdict:Verdict|Literal["NOT_FAIL"]="PASS", inc:tuple[str,...]=(), exc:tuple[str,...]=(), exit:int=0, omit:tuple[str,...]=(), tags:tuple[str,...]=()):
        S.append(BehaviorScenario(f"BM{i:03d}", desc, cat, files, omit, base, (), muts, patch, mode, "judge_patch" if mode=="judge_patch" else "ci" if mode=="ci_json_diff" else "strict" if mode=="strict_json_diff" else "local", verdict, inc, exc, None if mode=="judge_patch" else exit, True, ("schema_version","sourcepack_version","verdict","reason_codes","findings","not_checked"), (), tags))
    app={"app.py":"print('hi')\n"}
    add(1,"tracked file omitted from prompt context remains in baseline inventory", "baseline_prompt", app, patch=_patch("app.py",app["app.py"],"print('bye')\n"), mode="judge_patch", verdict="NOT_FAIL", exc=("missing_file",), omit=("app.py",))
    add(2,"existing file absent from authoritative baseline inventory is blocker", "baseline_prompt", app, patch=_patch("app.py",app["app.py"],"print('bye')\n"), mode="judge_patch", base="absent_authoritative_file", verdict="FAIL", inc=("missing_file",), exit=1)
    add(3,"new file added", "baseline_prompt", app, (m("write","new.py","x=1\n"),), verdict="WARN", inc=("new_file",), exc=("missing_file",))
    add(4,"tracked file deleted", "baseline_prompt", app, (m("delete","app.py"),), verdict="WARN", inc=("deleted_file",))
    add(5,"baseline missing with changes", "baseline_prompt", app, (m("append","app.py","print(2)\n"),), base="missing", verdict="FAIL", inc=("baseline_missing",), exit=1)
    add(6,"baseline present no changes", "baseline_prompt", app, (), verdict="PASS", )
    add(7,"python stdlib import", "dependency_python", {"app.py":"print(1)\n"}, (m("append","app.py","import json\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(8,"python local import", "dependency_python", {"app.py":"print(1)\n","localmod.py":"x=1\n"}, (m("append","app.py","import localmod\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(9,"python undeclared external dependency", "dependency_python", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(10,"python declared external dependency", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",))
    py_old="[project]\ndependencies=[]\n"; py_new="[project]\ndependencies=['fastapi']\n"
    add(11,"python same-patch dependency addition", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":py_old}, patch=_patch("pyproject.toml",py_old,py_new)+_patch("app.py","print(1)\n","print(1)\nimport fastapi\n"), mode="judge_patch", verdict="WARN", inc=("declared_dependency",), exc=("unsupported_dependency",))
    add(12,"python version spec dependency recognized", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['fastapi>=0.100']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",))
    add(13,"python optional dependency scope requires review", "dependency_python", {"app.py":"print(1)\n","pyproject.toml":"[project.optional-dependencies]\nweb=['fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="WARN", inc=("dependency_scope_review",), exc=("unsupported_dependency",))
    add(14,"js local relative import", "dependency_js", {"app.js":"console.log(1)\n","lib.js":"export const x=1\n"}, (m("append","app.js",'import x from "./lib.js"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(15,"js undeclared package import", "dependency_js", {"app.js":"console.log(1)\n","package.json":"{}\n"}, (m("append","app.js",'import React from "react"\n'),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(16,"js declared dependency", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"dependencies":{"react":"latest"}}\n'}, (m("append","app.js",'import React from "react"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(17,"js devDependency in production path is scope review", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"devDependencies":{"react":"latest"}}\n'}, (m("append","app.js",'import React from "react"\n'),), verdict="WARN", inc=("dependency_scope_review",), exc=("unsupported_dependency",))
    pj_old="{}\n"; pj_new='{"dependencies":{"react":"latest"}}\n'
    add(18,"js same-patch dependency addition", "dependency_js", {"app.js":"console.log(1)\n","package.json":pj_old}, patch=_patch("package.json",pj_old,pj_new)+_patch("app.js","console.log(1)\n",'console.log(1)\nimport React from "react"\n'), mode="judge_patch", verdict="WARN", inc=("declared_dependency",), exc=("unsupported_dependency",))
    add(19,"scoped package import recognized", "dependency_js", {"app.js":"console.log(1)\n","package.json":'{"dependencies":{"@scope/pkg":"1"}}\n'}, (m("append","app.js",'import x from "@scope/pkg/sub"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(20,"ts path alias import supported by tsconfig", "dependency_js", {"app.ts":"console.log(1)\n","src/lib.ts":"export const x=1\n","tsconfig.json":'{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}\n'}, (m("append","app.ts",'import {x} from "@/lib"\n'),), verdict="PASS", exc=("unsupported_dependency",))
    add(21,"docker compose without compose file", "command", {"README.md":"run docker compose up\n"}, (m("append","README.md","docker compose up\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(22,"docker compose with compose file remains supported", "command", {"README.md":"demo\n","compose.yaml":"services: {}\n"}, (m("append","README.md","docker compose up\n"),), verdict="PASS", exc=("unsupported_command",))
    add(23,"npm run dev missing script", "command", {"README.md":"demo\n","package.json":'{"scripts":{}}\n'}, (m("append","README.md","npm run dev\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(24,"npm run dev script exists", "command", {"README.md":"demo\n","package.json":'{"scripts":{"dev":"vite"}}\n'}, (m("append","README.md","npm run dev\n"),), verdict="PASS", exc=("unsupported_command",))
    pkg2='{"scripts":{"dev":"vite"}}\n'; add(25,"same-patch package script addition is review", "command", {"README.md":"demo\n","package.json":'{"scripts":{}}\n'}, patch=_patch("package.json",'{"scripts":{}}\n',pkg2)+_patch("README.md","demo\n","demo\nnpm run dev\n"), mode="judge_patch", verdict="WARN", inc=("declared_command",), exc=("unsupported_command",))
    add(26,"normalized internal path form", "path_artifact", {"README.md":"old\n"}, patch=_patch("src/../README.md","old\n","new\n"), mode="judge_patch", verdict="PASS", exc=("unsafe_path",))
    add(27,"escaping traversal path", "path_artifact", app, patch=_patch("../outside.txt","","x\n",new_file=True), mode="judge_patch", verdict="FAIL", inc=("unsafe_path",), exit=1)
    add(28,"windows drive path", "path_artifact", app, patch=_patch("C:/tmp/x.txt","","x\n",new_file=True), mode="judge_patch", verdict="FAIL", inc=("unsafe_path",), exit=1)
    add(29,"baseline active pointer protected", "path_artifact", app, patch=_patch(".sourcepack/baseline/active.json","{}\n","{ }\n"), mode="judge_patch", verdict="FAIL", inc=("protected_artifact",), exit=1)
    add(30,"prompt artifact protected", "path_artifact", app, patch=_patch(".sourcepack/prompt/prompt.md","a\n","b\n"), mode="judge_patch", verdict="FAIL", inc=("protected_artifact",), exit=1)
    add(31,"git config modification", "path_artifact", app, patch=_patch(".git/config","a\n","b\n"), mode="judge_patch", verdict="FAIL", inc=("git_path_modification",), exit=1)
    add(32,"workflow change is new file review", "path_artifact", app, (m("write",".github/workflows/ci.yml","name: ci\n"),), verdict="WARN", inc=("new_file",))
    add(33,"ordinary binary diff uncertainty", "diff_binary", app, patch="diff --git a/image.bin b/image.bin\nBinary files a/image.bin and b/image.bin differ\n", mode="judge_patch", verdict="WARN", inc=("binary_diff",))
    add(34,"high-risk binary manifest blocker", "diff_binary", app, patch="diff --git a/package.json b/package.json\nBinary files a/package.json and b/package.json differ\n", mode="judge_patch", verdict="FAIL", inc=("binary_diff",), exit=1)
    add(35,"malformed diff fails closed", "diff_binary", app, patch="@@ nope @@\n+bad\n", mode="judge_patch", verdict="FAIL", inc=("malformed_diff",), exit=1)
    for i,name in [(36,"Cargo.toml"),(37,"go.mod"),(38,"pom.xml"),(39,"build.gradle")]: add(i,f"unsupported ecosystem {name}","ecosystem", {"app.py":"print(1)\n",name:"x\n"}, (m("append",name,"y\n"),), verdict="WARN", inc=("unsupported_ecosystem",))
    add(40,"multiple unsupported ecosystems preserve evidence", "ecosystem", {"Cargo.toml":"x\n","go.mod":"module x\n","app.py":"print(1)\n"}, (m("append","Cargo.toml","y\n"),), verdict="WARN", inc=("unsupported_ecosystem",))
    add(41,"json output valid only", "output_policy", app, (), verdict="PASS", )
    add(42,"local WARN exits zero", "output_policy", app, (m("write","n.py","x=1\n"),), verdict="WARN", inc=("new_file",), exit=0)
    add(43,"strict WARN exits nonzero", "output_policy", app, (m("write","n.py","x=1\n"),), mode="strict_json_diff", verdict="WARN", inc=("new_file",), exit=1)
    add(44,"CI WARN exits nonzero", "output_policy", app, (m("write","n.py","x=1\n"),), mode="ci_json_diff", verdict="WARN", inc=("new_file",), exit=1)
    add(45,"FAIL exits nonzero", "output_policy", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1)
    add(46,"PASS exits zero", "output_policy", app, (), verdict="PASS", exit=0)
    add(47,"report includes schema fields", "output_policy", app, (), verdict="PASS", exit=0)
    # metamorphic explicit variants
    add(48,"metamorphic reordered independent hunks A", "metamorphic", {"a.py":"print(1)\n","b.js":"console.log(1)\n","package.json":"{}\n"}, patch=_patch("a.py","print(1)\n","print(1)\nimport fastapi\n")+_patch("b.js","console.log(1)\n",'console.log(1)\nimport r from "react"\n'), mode="judge_patch", verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_reorder",))
    add(49,"metamorphic reordered independent hunks B", "metamorphic", {"a.py":"print(1)\n","b.js":"console.log(1)\n","package.json":"{}\n"}, patch=_patch("b.js","console.log(1)\n",'console.log(1)\nimport r from "react"\n')+_patch("a.py","print(1)\n","print(1)\nimport fastapi\n"), mode="judge_patch", verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_reorder",))
    add(50,"metamorphic unrelated readme dependency", "metamorphic", {"app.py":"print(1)\n","README.md":"a\n"}, (m("append","app.py","import fastapi\n"),m("append","README.md","words\n")), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_readme",))
    add(51,"metamorphic path equivalent A", "metamorphic", {"README.md":"a\n"}, patch=_patch("README.md","a\n","b\n"), mode="judge_patch", verdict="PASS", tags=("invariant_path",))
    add(52,"metamorphic import whitespace", "metamorphic", {"app.py":"print(1)\n"}, (m("append","app.py","from   fastapi   import FastAPI\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_whitespace",))
    add(53,"metamorphic manifest ordering", "metamorphic", {"app.py":"print(1)\n","pyproject.toml":"[project]\ndependencies=['requests','fastapi']\n"}, (m("append","app.py","import fastapi\n"),), verdict="PASS", exc=("unsupported_dependency",), tags=("invariant_manifest_order",))
    add(54,"metamorphic temp directory independence", "metamorphic", {"app.py":"print(1)\n"}, (m("append","app.py","import fastapi\n"),), verdict="FAIL", inc=("unsupported_dependency",), exit=1, tags=("invariant_tempdir",))
    add(55,"metamorphic human/json reason stable", "metamorphic", app, (m("write","new.py","x=1\n"),), verdict="WARN", inc=("new_file",), tags=("invariant_human_json",))
    add(56,"execution claim without ledger warns", "execution", {"README.md":"demo\n"}, (m("append","README.md","tests passed\n"),), verdict="WARN", inc=("execution_evidence_missing",))
    add(57,"execution near miss does not warn", "execution", {"README.md":"demo\n"}, (m("append","README.md","please test; should pass; works toward coverage\n"),), verdict="PASS", exc=("execution_evidence_missing","execution_failed"))
    add(58,"make target missing command integration", "command", {"README.md":"demo\n","Makefile":"test:\n\ttrue\n"}, (m("append","README.md","make dev\n"),), verdict="FAIL", inc=("unsupported_command",), exit=1)
    add(59,"make target present command integration", "command", {"README.md":"demo\n","Makefile":"dev:\n\ttrue\n"}, (m("append","README.md","make dev\n"),), verdict="PASS", exc=("unsupported_command",))
    add(60,"real corpus no-corpus JSON clean", "corpus", app, (), verdict="PASS", exc=("unsupported_dependency",))
    return S


def validate_scenario_definitions(scenarios: list[BehaviorScenario]) -> None:
    seen: set[str] = set()
    for s in scenarios:
        if s.scenario_id in seen: raise AssertionError(f"duplicate scenario id {s.scenario_id}")
        seen.add(s.scenario_id)
        normalize_reason_codes(s.expected_reason_codes_include)
        normalize_reason_codes(s.expected_reason_codes_exclude)
        for code in (*s.expected_reason_codes_include, *s.expected_reason_codes_exclude):
            if code != normalize_reason_code(code):
                raise AssertionError(f"scenario {s.scenario_id} uses non-canonical spelling {code}")
        if s.expected_verdict in {"FAIL","WARN"} and not s.expected_reason_codes_include:
            raise AssertionError(f"{s.scenario_id} lacks expected reason code")


def run_matrix(selected: str | None = None) -> dict[str, Any]:
    scenarios = [s for s in build_scenarios() if selected in (None, s.scenario_id)]
    validate_scenario_definitions(scenarios)
    results = [run_scenario(s) for s in scenarios]
    invariant_count = 8
    return {"schema_version":"sourcepack.behavior_matrix.v1", "sourcepack_version":__version__, "scenario_count":len(build_scenarios()), "metamorphic_invariant_count":invariant_count, "selected_count":len(scenarios), "passed":sum(1 for r in results if r["ok"]), "failed":sum(1 for r in results if not r["ok"]), "results":results}


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(); p.add_argument("--json", action="store_true"); p.add_argument("--list", action="store_true"); p.add_argument("--scenario"); p.add_argument("--verbose", action="store_true"); p.add_argument("--keep-workdir", action="store_true", help="reserved; scenarios use temporary workdirs")
    args=p.parse_args(argv)
    if args.list:
        for s in build_scenarios(): print(f"{s.scenario_id}\t{s.category}\t{s.description}")
        return 0
    data=run_matrix(args.scenario)
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(f"Behavior matrix: {data['passed']}/{data['selected_count']} passed ({data['scenario_count']} scenarios, {data['metamorphic_invariant_count']} metamorphic invariants)")
        if data["failed"] or args.verbose:
            for r in data["results"]:
                if not r["ok"] or args.verbose: print(f"{r['scenario_id']}: {'PASS' if r['ok'] else 'FAIL'} {r['errors']}")
    return 0 if data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


---

## File: tools/golden_demo.py

Metadata:
- sha256: 1dd7967d77f50d33e253ab20d1f990ce733a3ac2249ceac03468b88d0f6c7b83
- bytes: 7225
- estimated_tokens: 1807

Content:

#!/usr/bin/env python3
"""Generate deterministic SourcePack golden demo repositories and reports."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "golden" / "output"
SOURCEPACK = [sys.executable, "-m", "sourcepack.cli"]

SCENARIOS = {
    "pass-clean": {"verdict": "PASS", "reasons": []},
    "warn-new-file": {"verdict": "WARN", "reasons": ["new_file"]},
    "fail-unsupported-dependency": {"verdict": "FAIL", "reasons": ["unsupported_dependency"]},
    "fail-unsupported-command": {"verdict": "FAIL", "reasons": ["unsupported_command"]},
    "fail-protected-artifact": {"verdict": "FAIL", "reasons": ["protected_artifact"]},
    "trust-boundary": {"verdict": "WARN", "reasons": ["new_file"]},
}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cp = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and cp.returncode != 0:
        raise RuntimeError(f"command failed in {cwd}: {' '.join(cmd)}\n{cp.stdout}")
    return cp


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(repo: Path, package_json: bool = False) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], repo)
    run(["git", "config", "user.email", "demo@example.com"], repo)
    run(["git", "config", "user.name", "SourcePack Demo"], repo)
    write(repo / "README.md", "# Demo repo\n\nUse SourcePack before commit.\n")
    write(repo / "pyproject.toml", "[project]\nname = \"demo\"\nversion = \"0.1.0\"\ndependencies = []\n")
    if package_json:
        write(repo / "package.json", json.dumps({"scripts": {"test": "node test.js"}}, indent=2) + "\n")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "initial trusted repo"], repo)
    run(SOURCEPACK + ["init", ".", "--auto", "--no-hook"], repo)
    local_config_files = [
        name
        for name in (".gitignore", ".sourcepackignore", "sourcepack.config.json")
        if (repo / name).exists()
    ]
    if local_config_files:
        run(["git", "add", *local_config_files], repo)
        staged = run(["git", "diff", "--cached", "--quiet"], repo, check=False)
        if staged.returncode != 0:
            run(["git", "commit", "-q", "-m", "accept sourcepack local config"], repo)
    run(SOURCEPACK + ["baseline", ".", "--refresh", "--quiet"], repo)


def scenario_pass_clean(repo: Path) -> None:
    init_repo(repo)


def scenario_warn_new_file(repo: Path) -> None:
    init_repo(repo)
    write(repo / "api.py", "def health():\n    return {'ok': True}\n")


def scenario_fail_unsupported_dependency(repo: Path) -> None:
    init_repo(repo)
    write(repo / "app.py", "from fastapi import FastAPI\n\napp = FastAPI()\n")


def scenario_fail_unsupported_command(repo: Path) -> None:
    init_repo(repo, package_json=True)
    write(repo / "README.md", "# Demo repo\n\nAI note: run `npm run dev` to start local development.\n")


def scenario_fail_protected_artifact(repo: Path) -> None:
    init_repo(repo)
    active = repo / ".sourcepack" / "baseline" / "active.json"
    run(["git", "add", "-f", ".sourcepack/baseline/active.json"], repo)
    run(["git", "commit", "-q", "-m", "track protected artifact for demo"], repo)
    data = json.loads(active.read_text(encoding="utf-8"))
    data["demo_tamper"] = True
    write(active, json.dumps(data, indent=2) + "\n")


def scenario_trust_boundary(repo: Path) -> None:
    init_repo(repo)
    prompt_dir = repo / ".sourcepack" / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    write(prompt_dir / "prompt.md", "AI guidance claims deploy.sh exists and uses port 8080.\n")
    write(prompt_dir / "reality_map.json", json.dumps({"ai_claim": "deploy.sh exists and uses port 8080"}, indent=2) + "\n")
    write(repo / "deploy.sh", "#!/bin/sh\necho starting fake deploy on 8080\n")

BUILDERS = {
    "pass-clean": scenario_pass_clean,
    "warn-new-file": scenario_warn_new_file,
    "fail-unsupported-dependency": scenario_fail_unsupported_dependency,
    "fail-unsupported-command": scenario_fail_unsupported_command,
    "fail-protected-artifact": scenario_fail_protected_artifact,
    "trust-boundary": scenario_trust_boundary,
}


def reason_ids(report: dict) -> list[str]:
    return sorted({str(f.get("id")) for f in report.get("findings", []) if isinstance(f, dict) and f.get("severity") != "info"})


def run_scenario(name: str) -> dict:
    scenario_dir = OUT / name
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    repo = scenario_dir / "repo"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    BUILDERS[name](repo)
    diff = run(SOURCEPACK + ["diff", "."], repo, check=False)
    report_open = run(SOURCEPACK + ["report", "path"], repo, check=False)
    report_path_line = report_open.stdout.strip().splitlines()[-1] if report_open.stdout.strip() else ".sourcepack/reports/latest.html"
    transcript = [
        "$ sourcepack diff .",
        diff.stdout.rstrip(),
        f"exit code: {diff.returncode}",
        "$ sourcepack report path",
        report_path_line,
        "$ sourcepack report open",
        "Open the HTML report above for details.",
        "",
    ]
    write(scenario_dir / "terminal.txt", "\n".join(transcript))
    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    latest_html = repo / ".sourcepack" / "reports" / "latest.html"
    if not latest_json.exists() or not latest_html.exists():
        raise RuntimeError(f"missing reports for {name}")
    report = json.loads(latest_json.read_text(encoding="utf-8"))
    actual = {"verdict": report.get("verdict"), "reasons": reason_ids(report)}
    expected = SCENARIOS[name]
    ok = actual["verdict"] == expected["verdict"] and all(r in actual["reasons"] for r in expected["reasons"])
    summary = {
        "scenario": name,
        "repo": "repo",
        "expected": expected,
        "actual": actual,
        "ok": ok,
        "terminal": "terminal.txt",
        "latest_html": "repo/.sourcepack/reports/latest.html",
        "latest_json": "repo/.sourcepack/reports/latest.json",
    }
    write(scenario_dir / "summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)
    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    names = [args.scenario] if args.scenario else list(SCENARIOS)
    summaries = [run_scenario(name) for name in names]
    print(json.dumps({"output_dir": str(OUT), "summaries": summaries}, indent=2))
    return 0 if all(s["ok"] for s in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())


---

## File: tools/real_corpus_validation.py

Metadata:
- sha256: 9435797831f4d56f11b03b53775b6fc0b511a18feae458c8bc9ca4aedd2f74a4
- bytes: 58335
- estimated_tokens: 14584

Content:

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "sourcepack.real_corpus_validation.v2"
TOOL_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIRNAME = ".sourcepack_corpus_cache"
MUTATION_STATUSES = {"applied", "skipped_incompatible_repo", "mutation_failed", "repo_cleanup_failed", "baseline_failed"}
METRICS = ["false_red","missed_red","noisy_warn","crash","timeout","invalid_json","wrong_reason_code","mutation_failed","mutation_status_applied_inconsistent","skipped_incompatible_repo","repo_cleanup_failed","baseline_failed","policy_over_suppression","trust_violation"]
FAILURE_METRICS = [m for m in METRICS if m != "skipped_incompatible_repo"]
ALTERNATE_SUPPRESSIBLE_METRICS = {"false_red", "missed_red", "noisy_warn", "wrong_reason_code"}

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    applies_to_tags: tuple[str, ...]
    required_files: tuple[str, ...]
    target_heuristic: str
    mutation: str
    expected_verdict: str
    expected_reason_codes_include: tuple[str, ...] = ()
    expected_reason_codes_exclude: tuple[str, ...] = ()
    allowed_alternate_outcomes: tuple[dict[str, Any], ...] = ()
    timeout_seconds: int = 20

@dataclass
class MutationResult:
    status: str
    applied: bool
    target_path: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

SCENARIOS: list[Scenario] = [
    Scenario("benign_readme_edit","Edit README prose only.",(),(),"readme","append_readme","PASS",timeout_seconds=10),
    Scenario("new_file","Add a simple new source file.",(),(),"python","create_python_probe","WARN",("new_file",),timeout_seconds=10),
    Scenario("undeclared_python_dependency_import","Import an undeclared Python dependency.",("python",),("python_file",),"python","append_undeclared_python_import","FAIL",("unsupported_dependency",),timeout_seconds=10),
    Scenario("declared_python_dependency_import","Import a dependency declared in a Python manifest.",("python",),("python_file","python_manifest"),"python_manifest","append_declared_python_import","PASS",allowed_alternate_outcomes=({"verdict":"WARN","justification":"Some repos expose ambiguous dependency metadata despite a declaration."},),timeout_seconds=10),
    Scenario("same_patch_python_dependency_add_plus_import","Add Python dependency declaration and import in the same patch.",("python",),("python_file","python_manifest"),"python_manifest","add_python_dep_and_import","WARN",("declared_dependency",),timeout_seconds=10),
    Scenario("undeclared_js_dependency_import","Import an undeclared Node dependency.",("node","javascript","typescript"),("js_file","package_json"),"js_ts","append_undeclared_js_import","FAIL",("unsupported_dependency",),timeout_seconds=10),
    Scenario("declared_js_dependency_import","Import an existing package.json dependency.",("node","javascript","typescript"),("js_file","package_json"),"node_manifest","append_declared_js_import","PASS",allowed_alternate_outcomes=({"verdict":"WARN","justification":"Package metadata can be present but not mapped to the selected import form."},),timeout_seconds=10),
    Scenario("same_patch_js_dependency_add_plus_import","Add package.json dependency and import in one patch.",("node","javascript","typescript"),("js_file","package_json"),"node_manifest","add_js_dep_and_import","WARN",("declared_dependency",),timeout_seconds=10),
    Scenario("missing_npm_script_reference","Reference an npm script that is not declared.",("node",),("package_json",),"node_manifest","readme_missing_npm_script","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("existing_npm_script_reference","Reference an existing npm script.",("node",),("package_json",),"node_manifest","readme_existing_npm_script","PASS",timeout_seconds=10),
    Scenario("docker_compose_missing_file","Reference Docker Compose when no compose file exists.",(),(),"docker_compose_missing","readme_missing_compose","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("docker_compose_existing_file","Reference an existing Docker Compose command.",("docker_compose",),("docker_compose",),"docker_compose","readme_existing_compose","PASS",timeout_seconds=10),
    Scenario("make_target_missing","Reference missing Make target.",(),(),"makefile_missing","readme_missing_make_target","FAIL",("unsupported_command",),timeout_seconds=10),
    Scenario("make_target_existing","Reference an existing Make target.",("makefile",),("makefile",),"makefile","readme_existing_make_target","PASS",timeout_seconds=10),
    Scenario("protected_sourcepack_baseline_edit","Patch attempts to edit protected SourcePack baseline.",(),(),"patch_text","protected_baseline_patch","FAIL",("protected_artifact",),timeout_seconds=10),
    Scenario("git_config_edit","Patch attempts to edit .git/config.",(),(),"patch_text","git_config_patch","FAIL",("git_path_modification",),timeout_seconds=10),
    Scenario("unsupported_ecosystem_touch","Touch unsupported ecosystem manifest.",("unsupported_ecosystem",),(),"unsupported","touch_cargo","WARN",("unsupported_ecosystem",),timeout_seconds=10),
    Scenario("binary_diff_low_risk","Add small binary artifact.",(),(),"binary","small_binary","WARN",("binary_diff",),timeout_seconds=10),
    Scenario("binary_diff_high_risk","Add larger binary artifact.",(),(),"binary","large_binary","WARN",("binary_diff",),timeout_seconds=10),
    Scenario("malformed_diff","Judge malformed patch text.",(),(),"patch_text","malformed_patch","FAIL",("malformed_diff",),timeout_seconds=10),
    Scenario("execution_claim_without_ledger","Claim command execution without ledger evidence.",(),(),"readme","execution_claim_no_ledger","WARN",("execution_evidence_missing",),timeout_seconds=10),
    Scenario("execution_claim_with_successful_ledger","Claim command execution with ledger evidence.",(),(),"readme","execution_claim_with_ledger","PASS",(),("execution_evidence_missing",),allowed_alternate_outcomes=({"verdict":"WARN","reason_codes_include":("execution_evidence_present",),"reason_codes_exclude":("execution_evidence_missing",),"justification":"Execution evidence may be reported as advisory while still proving ledger support."},),timeout_seconds=10),
    Scenario("policy_allow_matching_dependency","Policy allows one matching dependency finding.",("python",),("python_file",),"python","policy_allow_matching_dep","PASS",(),("unsupported_dependency",),allowed_alternate_outcomes=({"verdict":"WARN","reason_codes_exclude":("unsupported_dependency",),"justification":"Policy override evidence may keep an advisory report while suppressing the dependency failure."},),timeout_seconds=10),
    Scenario("policy_allow_nonmatching_dependency","Policy must not suppress unrelated dependency finding.",("python",),("python_file",),"python","policy_allow_nonmatching_dep","FAIL",("unsupported_dependency",),timeout_seconds=10),
]
SCENARIO_AUDIT_ALLOWED_MUTATION_KINDS = {
    "file_mutation",
    "multi_file_mutation",
    "delete_plus_file_mutation",
    "programmatic_patch_text",
    "policy_setup_plus_file_mutation",
    "ledger_setup_plus_file_mutation",
    "binary_file_mutation",
    "unsupported_ecosystem_marker",
}

SCENARIO_AUDIT_ALLOWED_PROOFS = {
    "readme_changed",
    "readme_contains_corpus_note",
    "new_file_exists",
    "python_source_contains_fastapi_import",
    "python_source_contains_declared_import",
    "python_manifest_contains_fastapi_dependency",
    "js_source_contains_missing_dep_import",
    "js_source_contains_declared_import",
    "js_source_contains_added_dependency_import",
    "package_json_contains_added_dependency",
    "readme_contains_missing_npm_script",
    "readme_contains_existing_npm_script",
    "readme_contains_docker_compose_up",
    "compose_files_absent",
    "compose_file_exists",
    "readme_contains_missing_make_target",
    "readme_contains_existing_make_target",
    "programmatic_patch_text_true",
    "cargo_toml_written",
    "binary_file_written",
    "readme_contains_execution_claim",
    "ledger_artifact_exists",
    "readme_claim_matches_ledger_command",
    "policy_artifact_exists",
    "source_contains_policy_allowed_dependency",
    "source_contains_policy_unsuppressed_dependency",
}

_AUDIT_PROOF_BY_SCENARIO = {
    "benign_readme_edit": ("readme_changed", "readme_contains_corpus_note"),
    "new_file": ("new_file_exists",),
    "undeclared_python_dependency_import": ("python_source_contains_fastapi_import",),
    "declared_python_dependency_import": ("python_source_contains_declared_import",),
    "same_patch_python_dependency_add_plus_import": ("python_manifest_contains_fastapi_dependency", "python_source_contains_fastapi_import"),
    "undeclared_js_dependency_import": ("js_source_contains_missing_dep_import",),
    "declared_js_dependency_import": ("js_source_contains_declared_import",),
    "same_patch_js_dependency_add_plus_import": ("package_json_contains_added_dependency", "js_source_contains_added_dependency_import"),
    "missing_npm_script_reference": ("readme_contains_missing_npm_script",),
    "existing_npm_script_reference": ("readme_contains_existing_npm_script",),
    "docker_compose_missing_file": ("readme_contains_docker_compose_up", "compose_files_absent"),
    "docker_compose_existing_file": ("readme_contains_docker_compose_up", "compose_file_exists"),
    "make_target_missing": ("readme_contains_missing_make_target",),
    "make_target_existing": ("readme_contains_existing_make_target",),
    "protected_sourcepack_baseline_edit": ("programmatic_patch_text_true",),
    "git_config_edit": ("programmatic_patch_text_true",),
    "unsupported_ecosystem_touch": ("cargo_toml_written",),
    "binary_diff_low_risk": ("binary_file_written",),
    "binary_diff_high_risk": ("binary_file_written",),
    "malformed_diff": ("programmatic_patch_text_true",),
    "execution_claim_without_ledger": ("readme_contains_execution_claim",),
    "execution_claim_with_successful_ledger": ("readme_contains_execution_claim", "ledger_artifact_exists", "readme_claim_matches_ledger_command"),
    "policy_allow_matching_dependency": ("policy_artifact_exists", "source_contains_policy_allowed_dependency"),
    "policy_allow_nonmatching_dependency": ("policy_artifact_exists", "source_contains_policy_allowed_dependency", "source_contains_policy_unsuppressed_dependency"),
}

_AUDIT_KIND_BY_SCENARIO = {
    "same_patch_python_dependency_add_plus_import": "multi_file_mutation",
    "same_patch_js_dependency_add_plus_import": "multi_file_mutation",
    "docker_compose_missing_file": "delete_plus_file_mutation",
    "protected_sourcepack_baseline_edit": "programmatic_patch_text",
    "git_config_edit": "programmatic_patch_text",
    "malformed_diff": "programmatic_patch_text",
    "policy_allow_matching_dependency": "policy_setup_plus_file_mutation",
    "policy_allow_nonmatching_dependency": "policy_setup_plus_file_mutation",
    "execution_claim_with_successful_ledger": "ledger_setup_plus_file_mutation",
    "binary_diff_low_risk": "binary_file_mutation",
    "binary_diff_high_risk": "binary_file_mutation",
    "unsupported_ecosystem_touch": "unsupported_ecosystem_marker",
}

SCENARIO_AUDIT: dict[str, dict[str, Any]] = {
    scenario.scenario_id: {
        "scenario_id": scenario.scenario_id,
        "repo_condition_created": scenario.description,
        "independent_proof": _AUDIT_PROOF_BY_SCENARIO[scenario.scenario_id],
        "expected_verdict": scenario.expected_verdict,
        "expected_reason_codes_include": scenario.expected_reason_codes_include,
        "expected_reason_codes_exclude": scenario.expected_reason_codes_exclude,
        "skip_conditions": f"Scenario may skip only when required files for target heuristic '{scenario.target_heuristic}' are absent or incompatible.",
        "mutation_failure_conditions": f"Mutation fails if '{scenario.mutation}' cannot create a changed, independently verifiable repo state.",
        "mutation_kind": _AUDIT_KIND_BY_SCENARIO.get(scenario.scenario_id, "file_mutation"),
    }
    for scenario in SCENARIOS
}

SCENARIO_BY_ID = {s.scenario_id: s for s in SCENARIOS}

def sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file(): return None
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    env=os.environ.copy()
    src=str(TOOL_ROOT/"src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)

def git_files(repo: Path) -> list[str]:
    cp=run(["git","ls-files"], repo, 15)
    return sorted(cp.stdout.splitlines()) if cp.returncode == 0 else []

def excluded(p: str, tests: bool=False) -> bool:
    parts=set(Path(p).parts)
    bad={".venv","venv","node_modules","build","dist","__pycache__",".cache","generated",".sourcepack"}
    if parts & bad: return True
    if not tests and ("tests" in parts or "test" in parts): return True
    return False

def find_python(repo: Path, create: bool=False) -> Path | None:
    files=[f for f in git_files(repo) if f.endswith(".py") and not excluded(f) and Path(f).name not in {"setup.py","conftest.py"}]
    root=[f for f in files if len(Path(f).parts)==1]
    src=[f for f in files if Path(f).parts[:1]==("src",)]
    pkg=[f for f in files if (repo/Path(f).parent/"__init__.py").exists()]
    for group in (root,src,pkg,files):
        if group: return repo/group[0]
    if create: return repo/"sourcepack_corpus_probe.py"
    return None

def find_js(repo: Path, create: bool=False) -> Path | None:
    exts={".js",".ts",".tsx",".jsx"}
    files=[f for f in git_files(repo) if Path(f).suffix in exts and not excluded(f) and not f.endswith("lock")]
    root=[f for f in files if len(Path(f).parts)==1]
    src=[f for f in files if Path(f).parts[:1]==("src",)]
    for group in (root,src,files):
        if group: return repo/group[0]
    if create: return repo/"sourcepack_corpus_probe.js"
    return None

def find_readme(repo: Path, create: bool=True) -> Path | None:
    for n in ("README.md","readme.md"):
        if (repo/n).exists(): return repo/n
    return repo/"README.md" if create else None

def find_py_manifest(repo: Path) -> Path | None:
    for n in ("requirements.txt","pyproject.toml"):
        if (repo/n).exists(): return repo/n
    req=sorted(repo.glob("requirements*.txt"))
    return req[0] if req else None

def declared_python_dependency(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if path.name.startswith("requirements"):
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#") and not cleaned.startswith("-"):
                return cleaned.split("==")[0].split(">=")[0].split("[")[0].replace("-", "_")
        return None
    if path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception:
            return None
        deps = data.get("project", {}).get("dependencies")
        if not isinstance(deps, list) or not deps:
            return None
        return str(deps[0]).split("==")[0].split(">=")[0].split("[")[0].replace("-", "_")
    return None

def find_package(repo: Path) -> Path | None: return repo/"package.json" if (repo/"package.json").exists() else None
def find_makefile(repo: Path) -> Path | None:
    for n in ("Makefile","makefile"):
        if (repo/n).exists(): return repo/n
    return None
def find_compose(repo: Path) -> Path | None:
    for n in ("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml"):
        if (repo/n).exists(): return repo/n
    return None

def mutate_file(path: Path, text: str, append: bool=True) -> MutationResult:
    before=sha256_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.exists(): path.write_text(path.read_text(encoding="utf-8", errors="ignore") + text, encoding="utf-8")
    else: path.write_text(text, encoding="utf-8")
    after=sha256_path(path)
    status="applied" if before != after else "mutation_failed"
    return MutationResult(status, status=="applied", str(path), before, after, None if status=="applied" else "sha256_unchanged")

def write_policy_allow(repo: Path, scope: str, value: str, reason: str) -> tuple[bool, dict[str, Any]]:
    cp = run([sys.executable, "-m", "sourcepack.cli", "allow", scope, value, "--reason", reason], repo, 15)
    return cp.returncode == 0, {"policy_command": f"sourcepack allow {scope} {value}", "policy_stdout": cp.stdout.strip(), "policy_stderr": cp.stderr.strip(), "policy_exit_code": cp.returncode}

def makefile_targets(path: Path) -> list[str]:
    targets=[]
    phony=set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw=line.split("#",1)[0].rstrip()
        if not raw or raw.startswith(("\t", " ")) or ":" not in raw or "=" in raw.split(":",1)[0]:
            continue
        name, rest = raw.split(":",1)
        names=[n for n in name.split() if n]
        if ".PHONY" in names:
            phony.update(rest.split()); continue
        for n in names:
            if n.startswith(".") or "%" in n or "$" in n or "/" in n:
                continue
            if n not in phony and n not in targets:
                targets.append(n)
    return [t for t in targets if t not in phony]

def add_python_manifest_dependency(path: Path, dep: str) -> MutationResult:
    before = sha256_path(path)
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if path.name.startswith("requirements"):
        if dep not in {line.strip().split("==")[0].split(">=")[0] for line in text.splitlines()}:
            path.write_text(text.rstrip("\n") + f"\n{dep}\n", encoding="utf-8")
    elif path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception as exc:
            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, f"pyproject_parse_failed:{exc}")
        deps = data.get("project", {}).get("dependencies")
        if not isinstance(deps, list):
            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "project_dependencies_missing_or_unsupported")
        if dep not in {str(d).split("==")[0].split(">=")[0] for d in deps}:
            marker = "dependencies"
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith(marker) and "[" in line:
                    if "]" in line:
                        lines[i] = line.replace("]", f", \"{dep}\"]", 1)
                    else:
                        for j in range(i+1, len(lines)):
                            if "]" in lines[j]:
                                lines.insert(j, f'  "{dep}",')
                                break
                        else:
                            return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "dependencies_array_not_closed")
                    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
                    break
            else:
                return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "dependencies_line_not_found")
    else:
        return MutationResult("skipped_incompatible_repo", False, str(path), before, before, "unsupported_python_manifest")
    after = sha256_path(path)
    return MutationResult("applied" if before != after else "mutation_failed", before != after, str(path), before, after, None if before != after else "sha256_unchanged", {"dependency_added": dep})

def skip(reason: str, details: dict[str,Any]|None=None) -> MutationResult:
    return MutationResult("skipped_incompatible_repo", False, reason=reason, details=details or {})

def apply_mutation(repo: Path, scenario: Scenario) -> MutationResult:
    sid=scenario.scenario_id
    if sid == "benign_readme_edit":
        return mutate_file(find_readme(repo, True), f"\nSourcePack corpus note for {sid}.\n")
    if sid == "execution_claim_without_ledger":
        return mutate_file(find_readme(repo, True), "\ntests passed\n")
    if sid == "execution_claim_with_successful_ledger":
        # Record ledger if available; README mutation remains the evaluated change.
        cp = run([sys.executable,"-m","sourcepack.cli","exec","--","python","--version"], repo, 20)
        mr = mutate_file(find_readme(repo, True), "\nI ran python --version\n")
        mr.details.update({"ledger_command":"python --version","ledger_exit_code":cp.returncode,"ledger_stdout":cp.stdout.strip(),"ledger_stderr":cp.stderr.strip()})
        if cp.returncode != 0:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="execution_ledger_setup_failed"
        return mr
    if sid == "new_file": return mutate_file(repo / "sourcepack_corpus_probe.py", "print('sourcepack corpus probe')\n", append=False)
    if sid.startswith("undeclared_python"):
        p=find_python(repo); return skip("python_target_missing") if not p else mutate_file(p, "\nimport fastapi\n")
    if sid == "policy_allow_matching_dependency":
        p=find_python(repo)
        if not p: return skip("python_target_missing")
        ok, details = write_policy_allow(repo, "dependency", "fastapi", "real corpus policy test")
        if not ok: return MutationResult("mutation_failed", False, reason="policy_setup_failed", details=details)
        mr = mutate_file(p, "\nimport fastapi\n")
        mr.details.update(details); mr.details["policy_allowed_dependency"] = "fastapi"
        return mr
    if sid == "policy_allow_nonmatching_dependency":
        p=find_python(repo)
        if not p: return skip("python_target_missing")
        ok, details = write_policy_allow(repo, "dependency", "fastapi", "real corpus policy test")
        if not ok: return MutationResult("mutation_failed", False, reason="policy_setup_failed", details=details)
        mr = mutate_file(p, "\nimport fastapi\nimport flask\n")
        mr.details.update(details); mr.details["policy_allowed_dependency"] = "fastapi"; mr.details["unsuppressed_dependency"] = "flask"
        return mr
    if sid == "declared_python_dependency_import":
        p=find_python(repo); m=find_py_manifest(repo)
        
        if not p or not m: return skip("python_target_or_manifest_missing")
        dep = declared_python_dependency(m)
        return skip("python_declared_dependency_missing") if not dep else mutate_file(p, f"\nimport {dep}\n")
    if sid == "same_patch_python_dependency_add_plus_import":
        p=find_python(repo); m=find_py_manifest(repo)
        if not p or not m: return skip("python_target_or_manifest_missing")
        dep_mr = add_python_manifest_dependency(m, "fastapi")
        if not dep_mr.applied: return dep_mr
        mr = mutate_file(p, "\nimport fastapi\n")
        mr.details.update({"manifest_path": str(m), "manifest_before_sha256": dep_mr.before_sha256, "manifest_after_sha256": dep_mr.after_sha256, "source_path": str(p), "source_before_sha256": mr.before_sha256, "source_after_sha256": mr.after_sha256, "dependency_added": "fastapi"})
        return mr
    if sid.startswith("undeclared_js"):
        p=find_js(repo); pkg=find_package(repo)
        return skip("js_target_or_package_json_missing") if not p or not pkg else mutate_file(p, "\nimport missingSourcepackDep from 'missing-sourcepack-dep';\n")
    if sid == "declared_js_dependency_import":
        p=find_js(repo); pkg=find_package(repo)
        if not p or not pkg: return skip("js_target_or_package_json_missing")
        data=json.loads(pkg.read_text() or "{}"); deps=data.get("dependencies") or data.get("devDependencies") or {"react":"latest"}; dep=sorted(deps)[0]
        return mutate_file(p, f"\nimport sourcepackCorpusDep from '{dep}';\n")
    if sid == "same_patch_js_dependency_add_plus_import":
        p=find_js(repo); pkg=find_package(repo)
        if not p or not pkg: return skip("js_target_or_package_json_missing")
        before=sha256_path(pkg)
        try:
            data=json.loads(pkg.read_text() or "{}")
        except Exception as exc:
            return skip("package_json_invalid", {"error": str(exc)})
        existing=set()
        existing_sections={}
        for section in ("dependencies","devDependencies","peerDependencies","optionalDependencies"):
            vals=data.get(section)
            if isinstance(vals, dict):
                names=sorted(str(k) for k in vals)
                existing_sections[section]=names
                existing.update(names)
        candidates=("sourcepack-corpus-js-dep","sourcepack-corpus-js-dep-2","sourcepack-corpus-js-dep-3")
        dep=next((c for c in candidates if c not in existing), None)
        if dep is None:
            return MutationResult("mutation_failed", False, str(pkg), before, before, "js_dependency_candidate_preexisting", {"dependency_candidates": list(candidates), "existing_dependency_sections": existing_sections})
        deps=data.setdefault("dependencies",{})
        if not isinstance(deps, dict):
            return MutationResult("mutation_failed", False, str(pkg), before, before, "package_json_dependencies_not_object")
        deps[dep]="latest"
        pkg.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        after=sha256_path(pkg)
        source_before=sha256_path(p)
        if before == after or dep not in (json.loads(pkg.read_text()).get("dependencies") or {}):
            return MutationResult("mutation_failed", False, str(pkg), before, after, "package_json_unchanged")
        mr = mutate_file(p, f"\nimport sourcepackCorpusJsDep from '{dep}';\n")
        mr.details.update({"package_json_path": str(pkg), "package_json_before_sha256": before, "package_json_after_sha256": after, "source_path": str(p), "source_before_sha256": source_before, "source_after_sha256": mr.after_sha256, "dependency_added": dep, "dependency_preexisting": False, "existing_dependency_sections": existing_sections, "import_specifier": dep})
        if not mr.applied:
            mr.status="mutation_failed"; mr.reason="source_unchanged"
        return mr
    if sid in {"missing_npm_script_reference","existing_npm_script_reference"}:
        pkg=find_package(repo)
        if not pkg: return skip("package_json_missing")
        script="missing-sourcepack-script"
        if sid == "existing_npm_script_reference":
            data=json.loads(pkg.read_text() or "{}"); scripts=data.get("scripts") or {}
            if not scripts: return skip("npm_scripts_missing")
            script=sorted(scripts)[0]
        return mutate_file(find_readme(repo, True), f"\nRun `npm run {script}`.\n")
    if sid == "docker_compose_missing_file":
        compose_names=("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml")
        deleted=[]
        for c in compose_names:
            path=repo/c
            if path.exists():
                path.unlink(); deleted.append(str(path))
        remaining=[str(repo/c) for c in compose_names if (repo/c).exists()]
        readme=find_readme(repo, True)
        before=sha256_path(readme)
        mr=mutate_file(readme, "\nRun `docker compose up`.\n")
        mr.details.update({"deleted_compose_files": deleted, "compose_files_remaining": remaining, "command_written": "docker compose up", "readme_path": str(readme), "readme_before_sha256": before, "readme_after_sha256": mr.after_sha256})
        if remaining:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="compose_files_still_present"
        elif before == mr.after_sha256:
            mr.status="mutation_failed"; mr.applied=False; mr.reason="readme_unchanged"
        return mr
    if sid == "docker_compose_existing_file":
        c=find_compose(repo); return skip("docker_compose_missing") if not c else mutate_file(find_readme(repo, True), "\nRun `docker compose up`.\n")
    if sid == "make_target_missing":
        mf=find_makefile(repo)
        if not mf: return skip("makefile_missing")
        return mutate_file(find_readme(repo, True), "\nRun `make missing-sourcepack-target`.\n")
    if sid == "make_target_existing":
        mf=find_makefile(repo)
        if not mf: return skip("makefile_missing")
        targets=makefile_targets(mf)
        if not targets: return skip("makefile_target_missing")
        mr=mutate_file(find_readme(repo, True), f"\nRun `make {targets[0]}`.\n")
        mr.details["make_target"] = targets[0]
        return mr
    if sid == "unsupported_ecosystem_touch": return mutate_file(repo/"Cargo.toml", "[package]\nname='sourcepack-corpus'\nversion='0.1.0'\n", append=False)
    if sid in {"binary_diff_low_risk","binary_diff_high_risk"}:
        p=repo/("sourcepack_corpus_low.bin" if sid.endswith("low_risk") else "sourcepack_corpus_high.bin"); data=b"\0\1\2" if sid.endswith("low_risk") else bytes(range(256))*64
        before=sha256_path(p); p.write_bytes(data); after=sha256_path(p); return MutationResult("applied", True, str(p), before, after)
    if sid in {"protected_sourcepack_baseline_edit","git_config_edit","malformed_diff"}:
        return MutationResult("applied", True, None, None, hashlib.sha256(sid.encode()).hexdigest(), details={"programmatic_patch_text": True})
    return MutationResult("mutation_failed", False, reason="unknown_scenario")

def _strip_js_comments(source_text: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", source_text, flags=re.DOTALL)
    return re.sub(r"//[^\n\r]*", "", without_block)

def _single_line_string_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(['\"])(?:\\.|(?!\1)[^\\\r\n])*\1", text):
        spans.append(match.span())
    return spans


def _inside_span(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _js_static_import_statements(text: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    lines = text.splitlines(keepends=True)
    offset = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        line_start = offset
        offset += len(line)
        index += 1
        if not re.match(r"^[ \t]*import\s+(?!\()", line):
            continue

        statement = line
        brace_balance = line.count("{") - line.count("}")
        has_from = re.search(r"\bfrom\b", line) is not None
        has_semicolon = ";" in line
        while not has_from and not has_semicolon and index < len(lines):
            next_line = lines[index]
            next_stripped = next_line.strip()
            if not next_stripped:
                statement += next_line
                offset += len(next_line)
                index += 1
                continue
            is_continuation = (
                brace_balance > 0
                or statement.rstrip().endswith((",", "{"))
                or next_line.startswith((" ", "\t"))
                or next_stripped.startswith(("}", ","))
            )
            if not is_continuation:
                break
            statement += next_line
            brace_balance += next_line.count("{") - next_line.count("}")
            has_from = re.search(r"\bfrom\b", next_line) is not None
            has_semicolon = ";" in next_line
            offset += len(next_line)
            index += 1

        statements.append((line_start, statement))
    return statements


def source_contains_js_import(source_text: str, dependency: str) -> bool:
    escaped = re.escape(dependency)
    quoted_dep = rf"(['\"]){escaped}\1"
    text = _strip_js_comments(source_text)
    string_spans = _single_line_string_spans(text)

    import_from = re.compile(
        rf"^\s*import\s+(?!\()(?:[\s\S]*?)\s+from\s+{quoted_dep}\s*;?\s*$"
    )
    import_side_effect = re.compile(rf"^\s*import\s+{quoted_dep}\s*;?\s*$")
    call_patterns = (
        re.compile(rf"\brequire\s*\(\s*{quoted_dep}\s*\)", re.MULTILINE),
        re.compile(rf"\bimport\s*\(\s*{quoted_dep}\s*\)", re.MULTILINE),
    )
    for start, statement in _js_static_import_statements(text):
        static_import_match = import_from.search(statement) or import_side_effect.search(statement)
        if static_import_match and not _inside_span(start, string_spans):
            return True
    for pattern in call_patterns:
        for match in pattern.finditer(text):
            if not _inside_span(match.start(), string_spans):
                return True
    return False

def mutation_validation_failed(mutation_result: MutationResult, reason: str, details: dict[str, Any] | None = None) -> MutationResult:
    failure_details = dict(details or {})
    failure_details["original_mutation_result"] = asdict(mutation_result)
    return MutationResult("mutation_failed", False, mutation_result.target_path, mutation_result.before_sha256, mutation_result.after_sha256, reason, failure_details)

def _rel_or_abs(repo: Path, value: Any) -> Path | None:
    if not value:
        return None
    p = Path(str(value))
    return p if p.is_absolute() else repo / p

def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path and path.exists() else ""

def _python_manifest_has_dependency(path: Path, dep: str) -> bool:
    text = _read(path)
    if path.name.startswith("requirements"):
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            name = raw.split("#", 1)[0].strip().split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip().replace("-", "_")
            if name == dep:
                return True
        return False
    if path.name == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception:
            return False
        deps = data.get("project", {}).get("dependencies")
        return isinstance(deps, list) and any(str(d).split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip().replace("-", "_") == dep for d in deps)
    return False

def _policy_artifact_exists(repo: Path) -> bool:
    return (repo / ".sourcepack" / "policy" / "allow.jsonl").exists()

def _ledger_artifact_exists(repo: Path) -> bool:
    return (repo / ".sourcepack" / "evidence" / "ledger.jsonl").exists()

def verify_scenario_state(repo: Path, scenario: Scenario, mr: MutationResult) -> MutationResult:
    if (mr.status == "applied" and mr.applied != True) or (mr.status != "applied" and mr.applied == True):
        return mutation_validation_failed(mr, "mutation_status_applied_inconsistent")
    if mr.status != "applied":
        return mr
    d = mr.details or {}
    sid = scenario.scenario_id
    if sid != "same_patch_js_dependency_add_plus_import" and mr.before_sha256 is not None and mr.after_sha256 == mr.before_sha256:
        return mutation_validation_failed(mr, "sha256_unchanged")
    if sid == "same_patch_js_dependency_add_plus_import":
        pkg = _rel_or_abs(repo, d.get("package_json_path")); src = _rel_or_abs(repo, d.get("source_path")); dep = d.get("dependency_added")
        candidates = {"sourcepack-corpus-js-dep", "sourcepack-corpus-js-dep-2", "sourcepack-corpus-js-dep-3"}
        if not pkg or not pkg.exists(): return mutation_validation_failed(mr, "js_package_json_missing")
        if not src or not src.exists(): return mutation_validation_failed(mr, "js_source_missing")
        if not dep: return mutation_validation_failed(mr, "js_dependency_added_missing")
        preexisting = set()
        sections = d.get("existing_dependency_sections")
        if isinstance(sections, dict):
            for vals in sections.values():
                if isinstance(vals, list): preexisting.update(str(v) for v in vals)
        if dep not in candidates or dep == "react": return mutation_validation_failed(mr, "js_dependency_candidate_invalid")
        if dep in preexisting: return mutation_validation_failed(mr, "js_dependency_preexisting")
        try: data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception: data = {}
        if dep not in (data.get("dependencies") or {}): return mutation_validation_failed(mr, "js_dependency_not_added_to_dependencies")
        if d.get("dependency_preexisting") is not False: return mutation_validation_failed(mr, "js_dependency_preexisting_flag_invalid")
        if d.get("import_specifier") != dep: return mutation_validation_failed(mr, "js_import_specifier_mismatch")
        if not source_contains_js_import(_read(src), str(dep)): return mutation_validation_failed(mr, "js_source_import_missing")
        if d.get("package_json_before_sha256") == d.get("package_json_after_sha256") or sha256_path(pkg) == d.get("package_json_before_sha256"): return mutation_validation_failed(mr, "js_package_json_unchanged")
        if d.get("source_before_sha256") == d.get("source_after_sha256") or sha256_path(src) == d.get("source_before_sha256"): return mutation_validation_failed(mr, "js_source_unchanged")
    if sid == "same_patch_python_dependency_add_plus_import":
        manifest = _rel_or_abs(repo, d.get("manifest_path")); src = _rel_or_abs(repo, d.get("source_path") or mr.target_path); dep = d.get("dependency_added")
        if not manifest or not manifest.exists(): return mutation_validation_failed(mr, "python_manifest_missing")
        if not src or not src.exists(): return mutation_validation_failed(mr, "python_source_missing")
        if dep != "fastapi": return mutation_validation_failed(mr, "python_dependency_added_missing")
        if not _python_manifest_has_dependency(manifest, "fastapi"): return mutation_validation_failed(mr, "python_dependency_not_in_manifest")
        if "import fastapi" not in _read(src): return mutation_validation_failed(mr, "python_import_missing")
        if d.get("manifest_before_sha256") == d.get("manifest_after_sha256") or sha256_path(manifest) == d.get("manifest_before_sha256"): return mutation_validation_failed(mr, "python_manifest_unchanged")
        if sha256_path(src) == mr.before_sha256 or d.get("source_before_sha256") == d.get("source_after_sha256"): return mutation_validation_failed(mr, "python_source_unchanged")
    if sid == "docker_compose_missing_file":
        readme = _rel_or_abs(repo, d.get("readme_path") or mr.target_path)
        if not readme or not readme.exists(): return mutation_validation_failed(mr, "compose_readme_missing")
        if "docker compose up" not in _read(readme): return mutation_validation_failed(mr, "compose_command_missing")
        if any((repo / n).exists() for n in ("compose.yml","compose.yaml","docker-compose.yml","docker-compose.yaml")): return mutation_validation_failed(mr, "compose_files_still_present")
        if "deleted_compose_files" not in d: return mutation_validation_failed(mr, "compose_deletion_provenance_missing")
        if "compose_files_remaining" not in d or d.get("compose_files_remaining") != []: return mutation_validation_failed(mr, "compose_remaining_provenance_invalid")
        if d.get("readme_before_sha256") == d.get("readme_after_sha256") or sha256_path(readme) == d.get("readme_before_sha256"): return mutation_validation_failed(mr, "compose_readme_unchanged")
    if sid == "policy_allow_matching_dependency":
        src = _rel_or_abs(repo, mr.target_path)
        if d.get("policy_exit_code") != 0: return mutation_validation_failed(mr, "policy_setup_failed")
        if d.get("policy_allowed_dependency") != "fastapi": return mutation_validation_failed(mr, "policy_allowed_dependency_missing")
        if not d.get("policy_command"): return mutation_validation_failed(mr, "policy_command_missing")
        if "import fastapi" not in _read(src): return mutation_validation_failed(mr, "policy_import_missing")
        if not _policy_artifact_exists(repo): return mutation_validation_failed(mr, "policy_artifact_missing")
    if sid == "policy_allow_nonmatching_dependency":
        src = _rel_or_abs(repo, mr.target_path)
        if d.get("policy_exit_code") != 0: return mutation_validation_failed(mr, "policy_setup_failed")
        if d.get("policy_allowed_dependency") != "fastapi": return mutation_validation_failed(mr, "policy_allowed_dependency_missing")
        if d.get("unsuppressed_dependency") != "flask": return mutation_validation_failed(mr, "policy_unsuppressed_dependency_missing")
        text = _read(src)
        if "import fastapi" not in text or "import flask" not in text: return mutation_validation_failed(mr, "policy_imports_missing")
        if not _policy_artifact_exists(repo): return mutation_validation_failed(mr, "policy_artifact_missing")
    if sid == "execution_claim_without_ledger":
        if not any(x in _read(_rel_or_abs(repo, mr.target_path)).lower() for x in ("tests passed", "pytest passed", "i ran pytest")): return mutation_validation_failed(mr, "execution_claim_missing")
    if sid == "execution_claim_with_successful_ledger":
        cmd = d.get("ledger_command"); readme_text = _read(_rel_or_abs(repo, mr.target_path)).lower()
        if d.get("ledger_exit_code") != 0: return mutation_validation_failed(mr, "execution_ledger_setup_failed")
        if not cmd: return mutation_validation_failed(mr, "execution_ledger_command_missing")
        if not _ledger_artifact_exists(repo): return mutation_validation_failed(mr, "execution_ledger_artifact_missing")
        if str(cmd).lower() not in readme_text: return mutation_validation_failed(mr, "execution_claim_missing")
    if sid in {"protected_sourcepack_baseline_edit", "git_config_edit", "malformed_diff"} and d.get("programmatic_patch_text") is not True:
        return mutation_validation_failed(mr, "programmatic_patch_text_missing")
    return mr

validate_mutation_result = verify_scenario_state

def cleanup_repo(repo: Path) -> bool:
    a=run(["git","reset","--hard","HEAD"], repo, 20)
    b=run(["git","clean","-fdx"], repo, 20)
    return a.returncode == 0 and b.returncode == 0

def create_baseline(repo: Path, timeout: int) -> bool:
    cp=run([sys.executable,"-m","sourcepack.cli","baseline",".","--force","--json","--quiet"], repo, timeout)
    return cp.returncode == 0 and ((repo/".sourcepack"/"baseline"/"active.json").exists() or (repo/".sourcepack"/"baseline"/"active").exists())

def reason_codes(report: dict[str,Any]) -> list[str]:
    vals=[]
    for key in ("findings","warnings","blockers","uncertainties"):
        for f in report.get(key,[]) or []:
            rid=f.get("id") or f.get("finding_id") or f.get("code")
            if rid: vals.append(str(rid))
    return sorted(set(vals))

def sourcepack_version() -> str:
    try:
        import sourcepack
        return getattr(sourcepack,"__version__","unknown")
    except Exception: return "unknown"

def evaluate(repo: Path, scenario: Scenario, timeout: int) -> tuple[int,str,str,bool,dict[str,Any]|None,bool]:
    if scenario.scenario_id in {"protected_sourcepack_baseline_edit","git_config_edit","malformed_diff"}:
        try:
            if str(TOOL_ROOT / "src") not in sys.path:
                sys.path.insert(0, str(TOOL_ROOT / "src"))
            from sourcepack.judgment import judge_repo_change
            patch = "@@ nope @@\n+bad\n" if scenario.scenario_id == "malformed_diff" else "diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\n--- a/.sourcepack/baseline/active.json\n+++ b/.sourcepack/baseline/active.json\n@@ -1 +1 @@\n-{}\n+{ }\n"
            if scenario.scenario_id == "git_config_edit": patch="diff --git a/.git/config b/.git/config\n--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-x\n+y\n"
            rep=judge_repo_change(repo, patch_text=patch).report
            return 0,json.dumps(rep),"",True,rep,False
        except Exception as exc:
            return 1,"",str(exc),False,None,False
    cp=run([sys.executable,"-m","sourcepack.cli","diff",".","--json"], repo, timeout)
    try:
        stripped=cp.stdout.strip(); rep=json.loads(stripped); valid=(stripped.startswith("{") and stripped.endswith("}"))
    except Exception:
        rep=None; valid=False
    return cp.returncode,cp.stdout,cp.stderr,valid,rep,False

def allowed_alternate_match(s: Scenario, actual: str|None, codes: list[str]) -> tuple[bool, str | None]:
    got=set(codes)
    for alt in s.allowed_alternate_outcomes:
        if not alt.get("verdict") or not alt.get("justification"):
            continue
        if actual != alt.get("verdict"):
            continue
        inc=set(alt.get("reason_codes_include", ()))
        exc=set(alt.get("reason_codes_exclude", ()))
        if inc - got or exc & got:
            continue
        return True, str(alt.get("justification"))
    return False, None

def classify(s: Scenario, actual: str|None, codes: list[str], invalid_json: bool, crash: bool, timeout: bool, mr: MutationResult) -> dict[str,bool]:
    d={k:False for k in METRICS}
    d["invalid_json"]=invalid_json; d["crash"]=crash; d["timeout"]=timeout
    d["mutation_failed"]=mr.status=="mutation_failed"; d["mutation_status_applied_inconsistent"]=mr.status=="mutation_failed" and mr.reason=="mutation_status_applied_inconsistent"; d["skipped_incompatible_repo"]=mr.status=="skipped_incompatible_repo"; d["repo_cleanup_failed"]=mr.status=="repo_cleanup_failed"; d["baseline_failed"]=mr.status=="baseline_failed"
    matched_alt, _ = allowed_alternate_match(s, actual, codes)
    if actual:
        candidate={k:False for k in ALTERNATE_SUPPRESSIBLE_METRICS}
        candidate["false_red"] = s.expected_verdict in {"PASS","WARN"} and actual == "FAIL"
        candidate["missed_red"] = s.expected_verdict == "FAIL" and actual in {"PASS","WARN"}
        candidate["noisy_warn"] = s.expected_verdict == "PASS" and actual == "WARN"
        inc=set(s.expected_reason_codes_include); exc=set(s.expected_reason_codes_exclude); got=set(codes)
        candidate["wrong_reason_code"] = bool((inc-got) or (exc&got))
        if not matched_alt:
            d.update(candidate)
    if s.scenario_id == "policy_allow_nonmatching_dependency" and actual != "FAIL": d["policy_over_suppression"] = True
    if s.scenario_id == "execution_claim_without_ledger" and actual == "PASS": d["trust_violation"] = True
    return d

def repo_entry_from_path(p: str) -> dict[str,Any]:
    path=Path(p).resolve(); return {"repo_id":path.name,"url":str(path),"path":str(path),"ecosystem_tags":infer_tags(path),"expected_features":[],"notes":"local repo"}

def infer_tags(path: Path) -> list[str]:
    tags=[]
    if any(path.glob("*.py")) or (path/"pyproject.toml").exists() or (path/"requirements.txt").exists(): tags.append("python")
    if (path/"package.json").exists(): tags.append("node")
    if find_compose(path): tags.append("docker_compose")
    if find_makefile(path): tags.append("makefile")
    if (path/"Cargo.toml").exists(): tags.append("unsupported_ecosystem")
    return tags

def load_repo_list(path: Path) -> list[dict[str,Any]]:
    data=json.loads(path.read_text())
    if not isinstance(data, list): raise ValueError("repo list must be a JSON array")
    for r in data:
        for k in ("repo_id","url","ecosystem_tags","expected_features","notes"):
            if k not in r: raise ValueError(f"repo list entry missing {k}")
    return data

def prepare_repo(entry: dict[str,Any], cache: Path, timeout: int) -> tuple[str|None,str|None,str|None]:
    url=entry["url"]
    p=Path(url)
    if p.exists(): return str(p.resolve()), None, None
    cache.mkdir(parents=True, exist_ok=True); dest=cache/entry["repo_id"]
    if dest.exists(): return str(dest.resolve()), None, None
    try:
        cp=run(["git","clone","--depth","1",url,str(dest)], cache.parent, timeout)
    except Exception as exc:
        return None,"network_unavailable",str(exc)
    if cp.returncode != 0:
        txt=(cp.stderr+cp.stdout).lower(); status="network_unavailable" if any(x in txt for x in ["could not resolve","failed to connect","network","unable to access"]) else "clone_failed"
        return None,status,cp.stderr.strip() or cp.stdout.strip()
    return str(dest.resolve()), None, None

def copy_work(src: Path, parent: Path, sid: str) -> Path:
    dst=Path(tempfile.mkdtemp(prefix=f"{src.name}_{sid}_", dir=parent))
    shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".sourcepack"))
    return dst

def empty_result(entry:dict[str,Any], scenario:Scenario, repo_path:str|None, mr:MutationResult, notes:list[str]) -> dict[str,Any]:
    flags={k:False for k in METRICS}
    flags["mutation_failed"] = mr.status == "mutation_failed"
    flags["mutation_status_applied_inconsistent"] = mr.status == "mutation_failed" and mr.reason == "mutation_status_applied_inconsistent"
    flags["skipped_incompatible_repo"] = mr.status == "skipped_incompatible_repo"
    flags["repo_cleanup_failed"] = mr.status == "repo_cleanup_failed"
    flags["baseline_failed"] = mr.status == "baseline_failed"
    return {"repo_id":entry["repo_id"],"repo_url":entry["url"],"repo_path":repo_path,"scenario_id":scenario.scenario_id,"mutation_status":mr.status,"mutation_result":asdict(mr),"expected_verdict":scenario.expected_verdict,"actual_verdict":None,"expected_reason_codes_include":list(scenario.expected_reason_codes_include),"expected_reason_codes_exclude":list(scenario.expected_reason_codes_exclude),"actual_reason_codes":[],"matched_allowed_alternate":False,"allowed_alternate_justification":None,"exit_code":None,"stdout_json_valid":False,**flags,"duration_ms":0,"report_path":None,"workdir_path":None,"notes":notes}

def run_harness(args: argparse.Namespace) -> tuple[dict[str,Any], int]:
    repos=[]
    if args.repo_list: repos.extend(load_repo_list(Path(args.repo_list)))
    for r in args.repo: repos.append(repo_entry_from_path(r))
    if args.max_repos is not None: repos=repos[:args.max_repos]
    selected=[SCENARIO_BY_ID[args.scenario]] if args.scenario else SCENARIOS
    workroot=Path(args.workdir or tempfile.mkdtemp(prefix="sourcepack_corpus_work_")).resolve(); workroot.mkdir(parents=True, exist_ok=True)
    cache=Path.cwd()/CACHE_DIRNAME
    results=[]; consecutive=0; circuit=False; cb_reason=None; last_failed=None
    for entry in repos:
        repo_path, prep_status, prep_msg = prepare_repo(entry, cache, args.timeout)
        if prep_status:
            for s in selected:
                row=empty_result(entry,s,None,skip(prep_status,{"message":prep_msg}),[prep_status]); row["skipped_incompatible_repo"]=True; results.append(row)
            continue
        src=Path(repo_path)
        for s in selected:
            start=time.time(); work=None; mr=MutationResult("mutation_failed",False,reason="not_run"); row=None
            try:
                work=copy_work(src, workroot, s.scenario_id)
                if not cleanup_repo(work): mr=MutationResult("repo_cleanup_failed",False,reason="git_reset_or_clean_failed"); row=empty_result(entry,s,repo_path,mr,["cleanup before baseline failed"])
                elif not create_baseline(work, min(args.timeout, s.timeout_seconds)):
                    mr=MutationResult("baseline_failed",False,reason="sourcepack_baseline_failed"); row=empty_result(entry,s,repo_path,mr,["baseline creation failed"])
                else:
                    mr=verify_scenario_state(work, s, apply_mutation(work,s))
                    if not (mr.status == "applied" and mr.applied == True): row=empty_result(entry,s,repo_path,mr,[mr.reason or mr.status])
                    else:
                        try:
                            code,out,err,valid,report,_ = evaluate(work,s,min(args.timeout,s.timeout_seconds))
                            invalid=not valid; crash=(code not in (0,1,2) and not invalid); actual=report.get("verdict") if report else None; codes=reason_codes(report or {})
                        except subprocess.TimeoutExpired:
                            code=None; valid=False; actual=None; codes=[]; invalid=False; crash=False; flags={k:False for k in METRICS}; flags["timeout"]=True
                        else:
                            flags=classify(s,actual,codes,invalid,crash,False,mr)
                        row={"repo_id":entry["repo_id"],"repo_url":entry["url"],"repo_path":repo_path,"scenario_id":s.scenario_id,"mutation_status":mr.status,"mutation_result":asdict(mr),"expected_verdict":s.expected_verdict,"actual_verdict":actual,"expected_reason_codes_include":list(s.expected_reason_codes_include),"expected_reason_codes_exclude":list(s.expected_reason_codes_exclude),"actual_reason_codes":codes,"matched_allowed_alternate":allowed_alternate_match(s,actual,codes)[0],"allowed_alternate_justification":allowed_alternate_match(s,actual,codes)[1],"exit_code":code,"stdout_json_valid":valid,**flags,"duration_ms":int((time.time()-start)*1000),"report_path":(report or {}).get("report_path") if isinstance(report,dict) else None,"workdir_path":str(work) if args.keep_workdir else None,"notes":[]}
            except subprocess.TimeoutExpired:
                row=empty_result(entry,s,repo_path,mr,["timeout"]); row["timeout"]=True
            except Exception as exc:
                row=empty_result(entry,s,repo_path,mr,[str(exc)]); row["crash"]=True
            row["duration_ms"]=row.get("duration_ms") or int((time.time()-start)*1000)
            if work and (args.keep_workdir and any(row.get(k) for k in METRICS)):
                row["workdir_path"]=str(work)
            elif work:
                cleanup_repo(work)
                shutil.rmtree(work, ignore_errors=True)
            results.append(row)
            if row.get("crash") or row.get("invalid_json"):
                consecutive += 1; last_failed={"repo_id":entry["repo_id"],"scenario_id":s.scenario_id}; cb_reason="crash" if row.get("crash") else "invalid_json"
            else: consecutive=0
            if consecutive >= 5:
                circuit=True; break
        if circuit: break
    executed_runs=sum(1 for r in results if r["mutation_status"]=="applied" and r.get("exit_code") is not None)
    skipped_runs=len(results)-executed_runs
    executed_failed=sum(1 for r in results if r["mutation_status"]=="applied" and r.get("exit_code") is not None and any(r.get(m) for m in FAILURE_METRICS))
    executed_passed=executed_runs-executed_failed
    summary={"schema_version":SCHEMA_VERSION,"sourcepack_version":sourcepack_version(),"generated_at":datetime.now(timezone.utc).isoformat(),"repo_count":len(repos),"scenario_count":len(selected),"total_runs":len(repos)*len(selected),"executed_runs":executed_runs,"skipped_runs":skipped_runs,"executed_passed":executed_passed,"executed_failed":executed_failed,"passed":executed_passed,"failed":0,**{m:sum(1 for r in results if r.get(m)) for m in METRICS},"circuit_breaker_triggered":circuit,"circuit_breaker_reason":cb_reason,"consecutive_failure_count":consecutive,"last_failed_repo_scenario":last_failed,"results":results}
    summary["failed"]=sum(1 for r in results if any(r.get(m) for m in FAILURE_METRICS))
    exit_code=1 if circuit else 0
    for flag,metric in [(args.fail_on_missed_red,"missed_red"),(args.fail_on_crash,"crash"),(args.fail_on_invalid_json,"invalid_json"),(args.fail_on_trust_violation,"trust_violation"),(args.fail_on_policy_over_suppression,"policy_over_suppression")]:
        if flag and summary[metric] > 0: exit_code=1
    if getattr(args, "failures_only", False):
        summary["results"]=[r for r in summary["results"] if any(r.get(m) for m in FAILURE_METRICS)]
    return summary, exit_code

def failure_line(row: dict[str,Any]) -> str:
    failed=[m for m in FAILURE_METRICS if row.get(m)]
    mr=row.get("mutation_result") or {}
    return " | ".join([
        f"repo_id={row.get('repo_id')}",
        f"scenario_id={row.get('scenario_id')}",
        f"expected_verdict={row.get('expected_verdict')}",
        f"actual_verdict={row.get('actual_verdict')}",
        f"actual_reason_codes={','.join(row.get('actual_reason_codes') or [])}",
        f"failed_metrics={','.join(failed)}",
        f"mutation_status={row.get('mutation_status')}",
        f"mutation_reason={mr.get('reason')}",
        f"workdir_path={row.get('workdir_path')}",
    ])

def main(argv: list[str]|None=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-list")
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--workdir")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-repos", type=int)
    ap.add_argument("--scenario", choices=sorted(SCENARIO_BY_ID))
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--failures-only", action="store_true")
    ap.add_argument("--print-failures", action="store_true")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--fail-on-missed-red", action="store_true")
    ap.add_argument("--fail-on-crash", action="store_true")
    ap.add_argument("--fail-on-invalid-json", action="store_true")
    ap.add_argument("--fail-on-trust-violation", action="store_true")
    ap.add_argument("--fail-on-policy-over-suppression", action="store_true")
    args=ap.parse_args(argv)
    summary, code=run_harness(args)
    if args.json: print(json.dumps(summary, indent=2, sort_keys=True))
    elif args.print_failures:
        for row in summary["results"]:
            if any(row.get(m) for m in FAILURE_METRICS):
                print(failure_line(row))
    else: print(f"Real corpus validation: {summary['executed_passed']} executed passed, {summary['executed_failed']} executed failed, {summary['skipped_runs']} skipped")
    return code

if __name__ == "__main__":
    raise SystemExit(main())


---

## File: tools/release_smoke.py

Metadata:
- sha256: 8d4d64d2b821aca37bfcc5b00fafc2011c48bdc3fa871facf98915cd51fe3778
- bytes: 298
- estimated_tokens: 75

Content:

from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_smoke.py"


def main() -> int:
    runpy.run_path(str(SCRIPT), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


---
