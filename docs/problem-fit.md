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

- **Invented dependency:** a proposed change imports `fastapi` in Python code, but the scanned dependency files do not declare `fastapi`. SourcePack reports `unsupported_dependency`.
- **Invented import:** a proposed change adds an import for a package that is not already supported by dependency manifests. SourcePack reports `unsupported_dependency`.
- **Invented API or command:** a proposed change documents or wires `npm run dev` when project evidence does not support that command. SourcePack reports `unsupported_command`.
- **Invented file:** a proposed change edits `deploy.sh` when that path is not in the trusted baseline. SourcePack reports `missing_file`.
- **Invented config key:** a proposed change adds or changes a config or dependency manifest entry. SourcePack can surface that as review evidence, commonly through `declared_dependency` or `new_file`, depending on the file change.
- **Wrong repo structure:** a proposed change creates a module in a new path or deletes an existing path. SourcePack reports `new_file` or `deleted_file` so a human reviews the structure change before it becomes trusted.

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
