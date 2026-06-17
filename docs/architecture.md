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
