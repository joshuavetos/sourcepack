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
