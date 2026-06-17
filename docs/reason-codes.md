# SourcePack reason codes

SourcePack reason codes explain why a repo-state transition is PASS, WARN, or FAIL. Local WARN exits `0` unless `--strict` is used. CI mode (`--ci`) treats WARN as nonzero and emits JSON.

## baseline_missing

- **Meaning:** No trusted `.sourcepack/baseline/` exists for the repo state being checked.
- **Local behavior:** FAIL when changes exist; SourcePack refuses to create trust while changes are present. With no changes, `sourcepack diff .` may create a baseline safely.
- **Strict/CI behavior:** FAIL; CI must not establish trust automatically.
- **Common cause:** Running `sourcepack diff .` before `sourcepack init . --auto` or `sourcepack baseline .`.
- **Likely fix:** Review the repo state, then run `sourcepack baseline .` or `sourcepack init . --auto` only when that state should be trusted.
- **Example message:** `No trusted SourcePack baseline exists while changes are present.`

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
