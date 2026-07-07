# SourcePack reason codes

SourcePack reason codes explain why a repo-state transition is `PASS`, `WARN`, or `FAIL`.

Reason codes are machine-readable identifiers. Human-readable messages may change, but canonical reason-code IDs should remain stable.

The canonical vocabulary lives in:

```text
src/sourcepack/reason_codes.py
```

Current vocabulary version:

```text
reason_codes.v1
```

Local WARN exits `0` unless `--strict` is used. CI mode, `--ci`, treats WARN as nonzero and emits JSON.

## Result behavior

| Result | Local behavior | Strict behavior | CI behavior |
| --- | --- | --- | --- |
| `PASS` | exits `0` | exits `0` | exits `0` |
| `WARN` | exits `0` | exits nonzero | exits nonzero |
| `FAIL` | exits nonzero | exits nonzero | exits nonzero |

## Baseline and repo state

### `baseline_missing`

- **Meaning:** No trusted `.sourcepack/baseline/` exists for the repo state being checked.
- **Typical severity:** `FAIL` when changes exist.
- **Common cause:** Running `sourcepack diff .` before creating trusted baseline state.
- **Likely fix:** Review the repo state, then run `sourcepack baseline .` or `sourcepack init . --auto` only when that state should be trusted.
- **Example:** `No trusted SourcePack baseline exists while changes are present.`

### `baseline_stale`

- **Meaning:** Trusted baseline state exists, but SourcePack detected evidence that it may not match the current trusted repo state.
- **Typical severity:** `WARN`.
- **Common cause:** The working tree changed after the last trusted baseline refresh, or stale-state metadata is present.
- **Likely fix:** Review the current repo state, commit intended changes, then refresh baseline only after accepting that state as trusted.
- **Example:** `Trusted SourcePack baseline may not match current repo state.`

### `baseline_corrupt`

- **Meaning:** Trusted baseline packet, pointer, metadata, or receipt is corrupt or unverifiable.
- **Typical severity:** `FAIL`.
- **Common cause:** `.sourcepack/baseline/` artifacts were edited, deleted, moved, or their recorded hashes no longer match.
- **Likely fix:** Treat the baseline as untrusted. Recreate it only after verifying the current repo state should be trusted.
- **Example:** `Trusted SourcePack baseline is corrupt or unverifiable.`

### `baseline_locked`

- **Meaning:** SourcePack could not safely update or use baseline state because a baseline lock condition exists.
- **Typical severity:** `FAIL` or `WARN`, depending on command context.
- **Common cause:** Interrupted baseline operation, concurrent process, or stale lock artifact.
- **Likely fix:** Confirm no SourcePack process is running, then remove or repair stale lock state only after reviewing the repo state.

### `baseline_failed`

- **Meaning:** A baseline operation failed before SourcePack could establish or refresh trusted state.
- **Typical severity:** `FAIL`.
- **Common cause:** Git failure, filesystem failure, invalid repo state, or baseline write failure.
- **Likely fix:** Read the command output, fix the underlying repo or filesystem issue, then rerun baseline creation only after review.

### `baseline_inventory_missing`

- **Meaning:** SourcePack expected baseline inventory data but could not find it.
- **Typical severity:** `FAIL`.
- **Common cause:** Partial baseline artifact, old/incomplete baseline state, deleted inventory file, or corrupt baseline directory.
- **Likely fix:** Treat baseline state as incomplete and recreate it only after verifying the current repo state should be trusted.

### `dirty_worktree`

- **Meaning:** SourcePack detected uncommitted changes where a clean working tree was required for trust creation or refresh.
- **Typical severity:** `FAIL` or `WARN`, depending on command context.
- **Common cause:** Trying to create trusted state while local edits are present.
- **Likely fix:** Review, commit, stash, or discard changes before creating or refreshing trusted baseline state.

### `repo_not_directory`

- **Meaning:** The supplied repo path is not a directory.
- **Typical severity:** `FAIL`.
- **Common cause:** Typo, missing checkout, wrong working directory, or passing a file path instead of a repo path.
- **Likely fix:** Run SourcePack from a valid repository directory or pass the correct path.

### `no_git_repo`

- **Meaning:** SourcePack expected a Git repository but did not find one.
- **Typical severity:** `FAIL` or `WARN`, depending on command context.
- **Common cause:** Running SourcePack outside a Git checkout.
- **Likely fix:** Run SourcePack inside a Git repository or initialize/clone the intended repo.

### `no_diff`

- **Meaning:** SourcePack found no visible repo-state transition to judge.
- **Typical severity:** `PASS` or `WARN`, depending on mode and command context.
- **Common cause:** Clean working tree, clean PR checkout, or no staged changes when using staged mode.
- **Likely fix:** For pull-request CI, materialize the PR delta before running `sourcepack diff . --ci`.

## Diff and path safety

### `missing_file`

- **Meaning:** A patch modifies a path that was not present in the trusted baseline.
- **Typical severity:** `FAIL`.
- **Common cause:** AI edited a fake file, wrong path, deleted path, or file outside the trusted baseline inventory.
- **Likely fix:** Restore the correct file, create a reviewed new file, or refresh baseline only after accepting the current repo state.
- **Example:** `<path> not found in the trusted baseline.`

### `new_file`

- **Meaning:** The patch creates a file not in the trusted baseline.
- **Typical severity:** `WARN`.
- **Common cause:** AI created a new module, test, config, or documentation file.
- **Likely fix:** Review the new file. Commit it if intended, then refresh trusted baseline state after review.
- **Example:** `<path> was created by the patch.`

### `deleted_file`

- **Meaning:** The patch deletes a file that existed in the trusted baseline.
- **Typical severity:** `WARN`.
- **Common cause:** AI removed a file or a refactor deleted a tracked path.
- **Likely fix:** Confirm the deletion is intended, restore if accidental, then commit the reviewed deletion.
- **Example:** `<path> was deleted by the patch.`

### `unsafe_path`

- **Meaning:** A diff path is unsafe, absolute, malformed, or not safely repo-relative.
- **Typical severity:** `FAIL`.
- **Common cause:** Malicious or malformed diff path such as `/tmp/file` or an unsafe platform path.
- **Likely fix:** Reject the patch and regenerate a normal repo-relative diff.
- **Example:** `Diff path is unsafe or not repo-relative.`

### `path_escape`

- **Meaning:** A diff path escapes the repository root.
- **Typical severity:** `FAIL`.
- **Common cause:** Malicious or malformed diff path such as `../secret`.
- **Likely fix:** Reject the patch and regenerate a normal repo-relative diff.
- **Example:** `Diff path escapes the repository root.`

### `protected_artifact`

- **Meaning:** The patch modifies protected SourcePack trust artifacts under `.sourcepack/`.
- **Typical severity:** `FAIL`.
- **Common cause:** AI or a tool edits `.sourcepack/baseline/`, generated trust state, reports, receipts, or internal SourcePack artifacts.
- **Likely fix:** Do not edit SourcePack trust artifacts manually. Rebuild trust with SourcePack commands after review.
- **Example:** `.sourcepack/baseline/active.json is a protected SourcePack trust artifact.`

### `git_path_modification`

- **Meaning:** The patch modifies `.git/` internals.
- **Typical severity:** `FAIL`.
- **Common cause:** AI generated a patch touching Git internal files.
- **Likely fix:** Reject the patch. Git internals should not be edited as normal repo files.
- **Example:** `.git/config modifies Git internal state and is not safe to judge as a normal repository file.`

### `binary_diff`

- **Meaning:** A binary change was detected and SourcePack cannot semantically evaluate it.
- **Typical severity:** `WARN` for ordinary binary changes; `FAIL` for high-risk trust/control paths.
- **Common cause:** Image, archive, lockfile, or protected artifact changed as binary data.
- **Likely fix:** Review manually. Avoid binary changes in trust/control paths unless intentionally produced by trusted tooling.
- **Example:** `Binary content was detected at <path> and was not semantically evaluated.`

### `malformed_diff`

- **Meaning:** SourcePack could not safely parse the diff artifact.
- **Typical severity:** `FAIL`.
- **Common cause:** Non-Git diff text, truncated hunks, malformed hunk headers, or unsupported patch format.
- **Likely fix:** Regenerate the diff with Git or rerun `sourcepack diff .`.
- **Example:** `SourcePack could not safely parse the diff artifact it was asked to judge.`

### `unsupported_rename_copy`

- **Meaning:** SourcePack detected a rename or copy diff pattern it cannot safely judge in the current path.
- **Typical severity:** `WARN` or `FAIL`, depending on path and mode.
- **Common cause:** Git rename/copy metadata without enough safe local evidence for the intended check.
- **Likely fix:** Review manually, or express the change as ordinary delete/create modifications when appropriate.

## Dependency and command evidence

### `unsupported_dependency`

- **Meaning:** New code imports or requires a dependency that is not declared in scanned dependency files.
- **Typical severity:** `FAIL`.
- **Common cause:** AI added `fastapi`, a JavaScript package, or another external dependency without updating dependency manifests.
- **Likely fix:** Remove the import or intentionally add the dependency to the appropriate manifest.
- **Example:** `fastapi is imported but not declared in scanned dependency files.`

### `declared_dependency`

- **Meaning:** The same patch adds a dependency declaration.
- **Typical severity:** `WARN`.
- **Common cause:** A patch updates `pyproject.toml`, `requirements*.txt`, `package.json`, or another dependency manifest.
- **Likely fix:** Confirm the dependency addition is intentional and review lockfile, install, and supply-chain implications.
- **Example:** `<dependency> was added to dependency files.`

### `dependency_manifest_uncertain`

- **Meaning:** SourcePack found dependency evidence, but the manifest or parser result is uncertain.
- **Typical severity:** `WARN`.
- **Common cause:** Dynamic dependency configuration, unsupported manifest shape, partial parse, or dependency metadata SourcePack cannot safely interpret.
- **Likely fix:** Review dependency changes manually and make dependency declarations explicit where possible.

### `dependency_scope_review`

- **Meaning:** SourcePack found dependency evidence that requires human scope review.
- **Typical severity:** `WARN`.
- **Common cause:** Dependency appears in an optional/dev/test group, dynamic dependency table, or scope that may not satisfy runtime import usage.
- **Likely fix:** Confirm the dependency is declared in the correct scope for the changed code path.

### `unsupported_ecosystem`

- **Meaning:** SourcePack detected ecosystem files whose dependency semantics are not implemented or not fully supported.
- **Typical severity:** `WARN`.
- **Common cause:** Rust, Go, Maven, Gradle, or other ecosystem markers appear in the repo or change before full support exists.
- **Likely fix:** Treat the result as needing review and rely on ecosystem-specific tests until SourcePack support is implemented.
- **Example:** `Cargo.toml detected, but Rust dependency validation is not implemented.`

### `js_alias_uncertain`

- **Meaning:** SourcePack detected JavaScript or TypeScript import aliasing it cannot safely resolve.
- **Typical severity:** `WARN`.
- **Common cause:** Path aliases, bundler aliases, TypeScript config paths, or framework-specific resolution rules.
- **Likely fix:** Review manually and make alias configuration explicit.

### `unsupported_command`

- **Meaning:** A command referenced by the change is not supported by project evidence.
- **Typical severity:** `FAIL`.
- **Common cause:** AI suggests `npm run dev` when `package.json` has no `dev` script, or references Docker Compose without evidence.
- **Likely fix:** Use an existing command or add the project file/script intentionally.
- **Example:** `npm run dev is not supported by project evidence.`

### `declared_command`

- **Meaning:** The repo contains evidence that a referenced command is declared.
- **Typical severity:** Usually informational or review evidence rather than a blocking failure.
- **Common cause:** A script or manifest declares a command that appears in the proposed change or prompt.
- **Likely fix:** No fix required unless the command declaration itself was changed and needs review.

### `command_manifest_missing`

- **Meaning:** A command check requires a local manifest/config file and SourcePack could not find one.
- **Typical severity:** `WARN`.
- **Common cause:** A README or script references `make`, `just`, `task`, or similar project commands without the corresponding manifest.
- **Likely fix:** Add the intended manifest or remove the unsupported command claim.

### `command_manifest_uncertain`

- **Meaning:** SourcePack found command-manifest evidence but could not safely interpret it.
- **Typical severity:** `WARN`.
- **Common cause:** Dynamic command config, unsupported task runner shape, generated scripts, or parser uncertainty.
- **Likely fix:** Make the project command declaration explicit or verify command behavior with `sourcepack exec -- ...`.

### `command_check_inconclusive`

- **Meaning:** SourcePack recognized the command family, but the project config was dynamic, ambiguous, unsupported, or unsafe to infer.
- **Typical severity:** `WARN`.
- **Common cause:** Dynamic tox/nox configuration or an unsupported command parser.
- **Likely fix:** Run the command locally with `sourcepack exec -- ...` and/or make the project command declaration explicit.

## Policy layer

Policy reason codes come from optional `.sourcepack/policy.json` rules.

Policy configuration can add local repository rules, but it must not make prompt context authoritative or weaken core trust boundaries.

### `policy_config_warning`

- **Meaning:** `.sourcepack/policy.json` contains an unsupported, unsafe, or ignored policy setting.
- **Typical severity:** `WARN`.
- **Common cause:** Attempting to make prompt context authoritative, disable CI baseline requirements, set reserved fields, ignore protected trust artifacts, or define ignore rules without reasons.
- **Likely fix:** Remove or correct the unsafe policy entry.
- **Notes:** Policy config can suppress only explicitly allowlisted low-risk findings. It cannot suppress dependency, command, baseline, protected artifact, unsafe path, malformed diff, binary diff, unsupported ecosystem, workflow, execution-evidence, unknown future reason-code, path escape, or `.git/**` findings.

### `policy_dependency_addition`

- **Meaning:** Proposed change added an unapproved dependency to project manifest files.
- **Typical severity:** `FAIL`.
- **Common cause:** A configured repository policy blocks new dependency declarations unless separately approved.
- **Likely fix:** Remove the dependency addition or complete the repository-specific approval flow before changing the manifest.
- **Example:** `Proposed change added an unapproved dependency to project manifest files.`

### `policy_protected_path`

- **Meaning:** Proposed change modified a path matching `rules.protected_paths` in `.sourcepack/policy.json`.
- **Typical severity:** `FAIL`.
- **Common cause:** A configured repository policy protects high-risk paths such as authentication, billing, migrations, release automation, or trust artifacts.
- **Likely fix:** Avoid the protected path or update/review repository policy intentionally.
- **Example:** `Proposed change modified a path protected by repository policy.`

### `policy_package_manager_drift`

- **Meaning:** Proposed change added or modified a package-manager artifact that conflicts with the configured package manager.
- **Typical severity:** `FAIL`.
- **Common cause:** `package_manager` is `pnpm`, but the change adds or modifies an npm or Yarn lock artifact.
- **Likely fix:** Use artifacts for the configured package manager or adjust repository policy intentionally.
- **Example:** `Proposed change added or modified a package-manager artifact that conflicts with repository policy.`

### `policy_missing_test`

- **Meaning:** Proposed change altered a file matching `rules.require_tests_for` without a test-path or test-name change in the same delta.
- **Typical severity:** `WARN` for the MVP.
- **Common cause:** Repository policy expects certain source paths to be accompanied by test updates.
- **Likely fix:** Add or update a corresponding test in the same delta, or adjust repository policy intentionally.
- **Example:** `Proposed change altered a path that repository policy expects to be accompanied by a test change.`

### `policy_large_diff`

- **Meaning:** Proposed change exceeds `rules.max_changed_lines`.
- **Typical severity:** `WARN` for the MVP.
- **Common cause:** The configured repository policy limits large deltas for local review.
- **Likely fix:** Split the proposed change or raise the configured limit intentionally.
- **Example:** `Proposed change modifies <count> lines, exceeding repository policy limit <limit>.`

### `policy_secret_pattern`

- **Meaning:** Proposed change added an obvious credential-shaped assignment involving a sensitive name such as `password`, `token`, `secret`, `api_key`, `access_key`, or `private_key`.
- **Typical severity:** `FAIL`.
- **Common cause:** Added lines contain high-confidence credential-shaped material rather than an obvious placeholder.
- **Likely fix:** Remove the value or replace it with an obvious placeholder such as `REDACTED` or `changeme`.
- **Example:** `Proposed change added obvious credential-shaped assignment material blocked by repository policy.`

## Execution evidence

Execution evidence reason codes relate to explicit command-execution claims and local SourcePack execution-ledger entries.

Execution evidence does not prove code correctness, security, runtime success in general, dependency safety, semantic validity, external API truth, or user intent. It only records bounded local command evidence.

### `execution_evidence_missing`

- **Meaning:** An answer or report makes an explicit command-execution claim, but no matching local SourcePack execution-ledger entry was found.
- **Typical severity:** `WARN` or `FAIL`, depending on mode and policy.
- **Common cause:** A tool or assistant claims tests were run without a matching `sourcepack exec -- ...` ledger entry.
- **Likely fix:** Run the claimed command locally with `sourcepack exec -- ...`, or remove the unsupported execution claim.

### `execution_evidence_present`

- **Meaning:** A matching local SourcePack execution-ledger entry exists for an explicit command-execution claim and recorded exit code `0`.
- **Typical severity:** Informational or positive evidence.
- **Common cause:** A command was run through `sourcepack exec -- ...` and completed successfully.
- **Likely fix:** No fix required. Review the command, exit code, and captured evidence as bounded local proof of execution.

### `execution_failed`

- **Meaning:** A matching local SourcePack execution-ledger entry exists for an explicit command-execution claim and recorded a nonzero exit code.
- **Typical severity:** `FAIL` or `WARN`, depending on the claim and mode.
- **Common cause:** A claimed verification command actually failed.
- **Likely fix:** Fix the failing command or remove the claim that it passed.

### `execution_inconclusive`

- **Meaning:** Local SourcePack execution-ledger entries for an explicit command-execution claim were ambiguous or mixed.
- **Typical severity:** `WARN`.
- **Common cause:** Multiple matching ledger entries disagree, command matching is ambiguous, or evidence does not cleanly support the claim.
- **Likely fix:** Rerun the intended command with `sourcepack exec -- ...` and make the verification claim specific.

## Workflow and hygiene

### `workflow_change`

- **Meaning:** Proposed change modifies workflow or automation files that can affect CI, release, trust, or repository control flow.
- **Typical severity:** `WARN` or `FAIL`, depending on mode and policy.
- **Common cause:** Editing `.github/workflows/**`, CI config, release automation, or other workflow control files.
- **Likely fix:** Review workflow changes carefully and confirm they do not weaken trust boundaries.
- **Example:** `Proposed change modified workflow automation.`

### `git_unavailable`

- **Meaning:** SourcePack could not run Git.
- **Typical severity:** `FAIL`.
- **Common cause:** Git is not installed, unavailable on PATH, blocked by environment, or failed to launch.
- **Likely fix:** Install Git, fix PATH, or run SourcePack in an environment with Git available.

### `git_timeout`

- **Meaning:** A Git operation exceeded SourcePack's bounded execution time.
- **Typical severity:** `FAIL`.
- **Common cause:** Hung Git process, extremely large repository operation, slow filesystem, or Git prompt waiting for input.
- **Likely fix:** Check Git health, remove interactive prompts, and rerun in a clean environment.

### `gitignore_unwritable`

- **Meaning:** SourcePack could not update `.gitignore` when it needed to add local SourcePack ignores.
- **Typical severity:** `WARN`.
- **Common cause:** Read-only `.gitignore`, filesystem permission issue, or locked file.
- **Likely fix:** Update `.gitignore` manually or fix file permissions.

### `prompt_context_failed`

- **Meaning:** SourcePack failed to generate or update prompt-context artifacts.
- **Typical severity:** `WARN` or `FAIL`, depending on command context.
- **Common cause:** Filesystem failure, invalid repo state, unavailable clipboard, or prompt artifact write failure.
- **Likely fix:** Fix the reported filesystem or environment issue and rerun the prompt command.
- **Trust note:** Prompt context is advisory. It never becomes trusted baseline state.

### `clipboard_unavailable`

- **Meaning:** SourcePack could not copy generated prompt context to the system clipboard.
- **Typical severity:** `WARN`.
- **Common cause:** Headless environment, missing clipboard utility, remote shell, or unsupported platform clipboard access.
- **Likely fix:** Use the printed output or generated file path instead of clipboard copy.

### `hook_install_failed`

- **Meaning:** SourcePack could not install Git hooks.
- **Typical severity:** `WARN` or `FAIL`, depending on command context.
- **Common cause:** Missing `.git/hooks`, permissions issue, nonstandard Git setup, or read-only filesystem.
- **Likely fix:** Install hooks manually or fix hook-directory permissions.

### `hygiene_hooks_deferred`

- **Meaning:** SourcePack deferred hook installation or hygiene setup because current conditions were not safe.
- **Typical severity:** `WARN`.
- **Common cause:** Dirty working tree, missing Git repository, permissions issue, or intentionally deferred setup.
- **Likely fix:** Finish repo cleanup, then rerun setup if hooks are desired.

## Vocabulary enforcement

`src/sourcepack/reason_codes.py` is the source of truth for emitted reason-code IDs.

Runtime report construction normalizes IDs to lowercase snake_case and refuses unknown WARN/FAIL finding IDs.

Positive evidence such as `declared_dependency`, `declared_command`, and `execution_evidence_present` is review evidence. It is not proof that prompt context can enforce trust.

## What SourcePack is not claiming

Reason codes explain local evidence transitions.

SourcePack reason-code output does not prove:

- code correctness
- security
- runtime success
- dependency safety
- semantic validity
- external API truth
- user intent

Human-readable messages are remediation aids. Canonical reason-code IDs remain the stable machine-readable identifiers.
