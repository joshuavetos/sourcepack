# SourcePack

SourcePack is a **Project Reality Compiler** for AI-assisted software work.

It compiles a local project into a verified reality map so AI tools know what files, commands, dependencies, and capabilities actually exist before they generate code. It also judges whether AI answers and proposed patches stay inside that compiled project reality.

SourcePack is local-first. It does not host a service, use a database, call external APIs, or execute your application by default.

## Install

```bash
python -m pip install -e .
```

## Build → verify → judge

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

`sourcepack judge-patch <packet> <patch.diff> --out <report_folder>` evaluates standard git-style unified diffs, such as output from `git diff`. It reports modified missing files, new files, deleted files, unsupported imports, unsupported commands, and root-level protected packet artifact edits in `patch_judgment_report.md` and `patch_judgment_report.json`. It does not claim support for arbitrary patch formats, binary diffs, rename/copy semantics, full semantic patch analysis, or runtime validation.

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

## What SourcePack checks

- Files included in the packet and file references made by an AI answer or patch.
- Dependencies detected from structural evidence such as imports and dependency manifests.
- Commands supported by structural evidence, including package scripts, Docker/compose files, and Python test evidence.
- Capabilities detected from structural project evidence.
- Packet tampering through `receipt.json` artifact hashes.
- Source drift with `sourcepack verify --against`.
- Patch assumptions, including missing modified files, new files, deleted files, unsupported imports, unsupported commands, and protected packet artifact edits.

## What SourcePack does not prove

- Semantic correctness.
- Runtime behavior.
- Security.
- Production readiness.
- External service behavior.
- All possible hallucinations.

SourcePack does not execute the target application by default. Capability, dependency, and patch detection are structural and heuristic. Dependency detection is bounded by current inventory logic. Absence of evidence means unknown, not impossible.

## Development

Run the local checks with:

```bash
python -m pip install -e .
sourcepack doctor
python -m unittest
sourcepack demo
```
