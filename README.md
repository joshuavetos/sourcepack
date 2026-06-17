# SourcePack

SourcePack is a **local reality check for AI code changes**.

It catches fake files, fake commands, undeclared imports, and protected SourcePack artifact edits before you commit AI-assisted work. SourcePack compiles local repo evidence into a verified reality map, then judges whether AI answers and proposed patches stay inside that evidence.

SourcePack is local-first. It does not host a service, use a database, call external APIs, or execute your application by default.

## Install

```bash
python -m pip install -e .
```

Target packaged install after release:

```bash
pipx install sourcepack
# or
uv tool install sourcepack
```

## Quick start

```bash
sourcepack init . --auto
```

Optional prompt grounding before the AI edits files:

```bash
sourcepack prompt . "your task" --copy
```

Then apply the AI change and inspect it locally:

```bash
sourcepack diff .
```

The automatic git workflow is:

1. `sourcepack init . --auto` creates local `.sourcepack/` state, ignores it in git, creates a trusted baseline when safe, and installs hooks when this is a git repo.
2. Optional: `sourcepack prompt . "task" --copy` writes non-authoritative prompt context for the AI.
3. The AI applies changes.
4. `sourcepack diff .` checks actual repo changes against the trusted baseline.
5. The pre-commit hook runs `sourcepack diff . --staged`.
6. The post-commit hook refreshes the trusted baseline only when the working tree is clean.

## Trust model

- `.sourcepack/baseline/` is the authoritative enforcement state.
- `.sourcepack/prompt/` is non-authoritative prompt context.
- Prompt context may be selective and must not define repo truth.
- Diff gating enforces against actual repo changes.
- Prompt grounding is probabilistic; diff judgment is the guardrail.

## Prevention vs enforcement

SourcePack separates prompt prevention from diff enforcement:

- **Prompt prevention**: `sourcepack prompt` gives the AI grounded instructions and an answer contract. This reduces hallucinated output, but it cannot force model compliance.
- **Diff enforcement**: `sourcepack diff` and the hooks inspect actual file changes. This is the enforceable layer.

Prompt grounding is preventive and model-dependent. Diff gating is the enforceable check. A well-grounded prompt can still produce unsupported changes, and SourcePack is expected to catch those later.

## Build, verify, judge

1. `sourcepack build` scans a local repo and writes a packet.
2. The packet includes `manifest.json`, source context artifacts, `receipt.json`, and `reality_map.json`.
3. `ai_instructions.md` tells an AI how to stay grounded in that reality map.
4. `sourcepack verify` checks packet artifact hashes through `receipt.json` and can compare source drift with `--against`.
5. `sourcepack judge` checks an AI answer for unsupported file, dependency, command, and capability claims.
6. `sourcepack judge-patch` checks a unified diff for unsupported patch assumptions.

## Packet outputs

`sourcepack build <repo> --out <packet> --force` writes:

- `manifest.json`
- `context.md`
- `context.xml`
- `receipt.json`
- `file_tree.txt`
- `ignored_files.txt`
- `token_report.json`
- `redactions.json`
- `reality_map.json`
- `ai_instructions.md`

`receipt.json` includes hashes for packet artifacts so tampering can be detected by `sourcepack verify`.

## Commands

```bash
sourcepack doctor
sourcepack init .
sourcepack build examples/demo_repo --out /tmp/sourcepack_demo_packet --force
sourcepack verify /tmp/sourcepack_demo_packet
sourcepack verify /tmp/sourcepack_demo_packet --against examples/demo_repo
sourcepack judge /tmp/sourcepack_demo_packet examples/fake_ai_answer.md --out /tmp/sourcepack_judgment
sourcepack judge-patch /tmp/sourcepack_demo_packet examples/fake_ai_patch.diff --out /tmp/sourcepack_patch_judgment
```

### Answer judgment versus patch judgment

`sourcepack judge <packet> <answer.md> --out <report_folder>` evaluates prose answers. It reports unsupported file references, dependency claims, commands, and capabilities in `judgment_report.md` and `judgment_report.json`.

`sourcepack judge-patch <packet> <patch.diff> --out <report_folder>` evaluates standard git-style unified diffs, such as output from `git diff`. It reports modified missing files, new files, deleted files, unsupported imports, unsupported commands, and root-level protected packet artifact edits in `patch_judgment_report.md` and `patch_judgment_report.json`. JSON reports include stable automation fields such as schema version, SourcePack version, verdict, findings, blockers, review warnings, uncertainties, checked categories, not checked categories, next action, and report path. It does not claim support for arbitrary patch formats, binary diffs, rename/copy semantics, full semantic patch analysis, or runtime validation.

`sourcepack judge` and `sourcepack judge-patch` return success when report generation succeeds. Read the report verdict to determine whether the answer or patch passed grounding checks.

Patch judgment does not mutate packet artifacts. New files in a patch may be reported as new evidence, but they are not treated as part of the original packet reality. Patch dependency detection is structural and heuristic. Unknown dependencies may require future expansion of the dependency inventory.

### Reality map only

```bash
sourcepack map examples/demo_repo --out /tmp/reality_map.json
```

This scans the repo with SourcePack's existing scanning and detection logic and writes only a `reality_map.json` output path.

### AI instructions from a packet

```bash
sourcepack instructions /tmp/sourcepack_demo_packet
```

If `ai_instructions.md` exists, SourcePack prints it. If it is missing but `reality_map.json` exists, SourcePack regenerates and prints it. If both are missing, the command fails clearly.

### Local demo

```bash
sourcepack demo
```

The demo builds `examples/demo_repo` into a temporary packet directory, verifies the packet, judges `examples/fake_ai_answer.md`, and prints the temporary output locations. If `examples/fake_ai_patch.diff` exists, the demo also runs patch judgment.

The fake AI answer and fake AI patch are expected to produce FAIL verdicts because they intentionally contain unsupported claims and assumptions. The demo command itself exits successfully when the SourcePack workflow runs correctly.

## What SourcePack catches

- Missing modified files relative to the trusted baseline.
- Undeclared Python and JS/TS imports detected in patches.
- Unsupported project commands such as missing `npm` scripts or missing Docker Compose evidence.
- Protected SourcePack artifact edits.
- New files, deleted files, and declared dependency changes that need review.
- Unsupported ecosystems, such as Rust dependency validation, as YELLOW uncertainty rather than false GREEN.

## What SourcePack does not catch

- Bad logic.
- Failing runtime behavior.
- Security flaws.
- External API behavior.
- Unsupported ecosystems beyond explicit uncertainty warnings.

SourcePack does not execute the target application by default. Capability, dependency, and patch detection are structural and heuristic. Absence of evidence means unknown, not impossible. GREEN means SourcePack found no blockers only inside the checked scope printed in the report.

## Traffic lights and exit codes

- GREEN/PASS exits `0`: no checked category triggered. It does not prove correctness.
- YELLOW/WARN exits `0` by default: review, uncertainty, or tooling degradation exists. It is allowed locally unless strict mode is enabled.
- YELLOW/WARN exits nonzero with `--strict` or `--ci`.
- RED/FAIL exits `1`: action is blocked unless the user explicitly bypasses the gate.
- Hook strict mode blocks YELLOW/WARN as well as RED/FAIL.
- `sourcepack diff --ci` is non-interactive, disables clipboard use, prints JSON on every return path, and stamps CI reports with `ci: true`.

### CI usage

Run SourcePack CI after checkout and installation:

```yaml
- uses: actions/checkout@v4
- run: python -m pip install -e .
- run: sourcepack diff . --ci
```

`sourcepack diff . --ci` prints JSON, returns `0` for PASS, and exits nonzero for WARN or FAIL. CI mode must not establish trust automatically: if the trusted baseline is missing, the CI check fails until a baseline is created intentionally outside CI.

YELLOW findings are surfaced by reason type so different risks do not collapse into one generic warning:

- **YELLOW REVIEW**: allowed locally by default. This covers normal changes that need human review, such as new files, declared dependencies, and deleted files.
- **YELLOW UNCERTAIN**: allowed locally by default, but louder. This means SourcePack could not fully evaluate the change, such as unsupported ecosystems, stale baselines, binary diffs, or parser limitations.
- **YELLOW TOOLING**: visually separate from repo judgment. This covers degraded SourcePack tooling, such as unavailable clipboard integration, report archive failures, or incomplete metadata.

Rendered output includes the reason type and commit policy, for example:

```text
YELLOW LIGHT: SourcePack could not fully evaluate this change.
Reason type: uncertainty
Commit policy: allowed locally, blocked in strict mode.
```

Local default policy allows GREEN and YELLOW findings, with stronger review language for YELLOW UNCERTAIN. RED blocks. Strict mode and CI mode block every YELLOW and RED.

## Development

Run the local checks with:

```bash
python -m pip install -e .
sourcepack doctor
python -m unittest
sourcepack demo
```

## Local trust semantics

SourcePack keeps two local realities separate:

- `.sourcepack/baseline/` is the trusted enforcement baseline used by `sourcepack diff` and hooks.
- `.sourcepack/prompt/` is current working-tree prompt context generated by `sourcepack prompt`.

`sourcepack prompt` never refreshes the enforcement baseline. This prevents a dirty prompt run from silently accepting bad AI edits as trusted reality. `sourcepack baseline` accepts the current working tree as trusted reality, and `sourcepack baseline --refresh` intentionally replaces trusted project reality with the current working tree. `sourcepack diff` refuses to silently create a baseline when changes already exist; if no baseline exists and changes exist, explicitly decide whether to run `sourcepack baseline --refresh` before trusting that state.

`sourcepack init . --auto` enables the first automatic local workflow by creating local `.sourcepack/` state, ensuring `.sourcepack/` is ignored, creating a safe baseline when possible, and installing pre-commit and post-commit hooks when a git repository is available. The pre-commit hook gates the staged diff. The post-commit hook refreshes the baseline only after clean commits; if uncommitted changes remain, it marks the baseline stale instead of accepting the dirty working tree.

### Clean baseline refresh definition

For automatic post-commit baseline refresh, clean means all three checks are empty:

- `git diff`
- `git diff --staged`
- `git ls-files --others --exclude-standard`

SourcePack treats untracked non-ignored files as dirty for baseline refresh purposes because baseline refresh scans the working tree. If tracked unstaged diff exists, staged diff exists, or untracked non-ignored files exist, the post-commit hook marks the baseline stale instead of refreshing it. Only when all three checks are empty does SourcePack refresh the trusted baseline automatically.

## Optional real-corpus validation

The external Colab 10-repo corpus validation is not part of default pytest and is not reproduced by this checkout. The repository does not currently include enough executable inputs to recreate it safely: the 10 target repo URLs or revisions, scenario definitions per repo, generated packet locations, and Colab output artifacts are not present.

`tools/real_corpus_validation.py` exists as an optional harness and is not run by default pytest. It accepts caller-provided repositories with `--repo` or `--repo-list`, deep-cleans repositories between scenarios with `git reset --hard` and `git clean -ffdx`, rebuilds a current SourcePack baseline, and runs `README_EDIT`, `NEW_FILE`, and `IMPORT_FAIL`. It preserves verdicts, reason codes, report paths, and ok/fail status, and exits nonzero when calibrated expectations fail. It does not embed or reproduce the prior external Colab corpus unless the exact corpus inputs are supplied and run.
