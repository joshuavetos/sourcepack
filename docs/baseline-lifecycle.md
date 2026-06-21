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
- Confirm no unreviewed AI patch is being laundered into trust.

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
