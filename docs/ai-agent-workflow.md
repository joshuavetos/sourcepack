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
