# SourcePack

SourcePack is a **Project Reality Compiler**.

It scans a local repository and produces a verified reality map that tells an AI what actually exists before it builds. Its secondary mode judges whether an AI response stayed inside that reality map.

SourcePack is local-first: it compiles structural evidence from files, manifests, dependency declarations, included/ignored records, and deterministic capability detection. It does not host a service or execute your application by default.

## Install

```bash
python -m pip install -e .
```

## Build → reality map → AI instructions → judge

1. `sourcepack build` scans a local repo and writes a packet.
2. The packet includes the original context artifacts plus `reality_map.json`.
3. `ai_instructions.md` tells an AI how to stay grounded in that reality map.
4. `sourcepack verify` checks packet artifact hashes through `receipt.json`.
5. `sourcepack judge` checks an AI answer for unsupported file, dependency, command, and capability claims.

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
```

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

The demo builds `examples/demo_repo` into a temporary packet directory, verifies the packet, judges `examples/fake_ai_answer.md`, and prints the temporary output locations.

## What SourcePack does

- Compiles a local project into a verified reality map for AI tools.
- Records included files, ignored files, source hashes, packet hashes, token estimates, and redactions.
- Detects dependencies and capabilities from structural evidence rather than README claims alone.
- Reports supported commands only when deterministic evidence exists, such as package scripts, Dockerfiles, compose files, or test structure.
- Provides AI instructions that warn against inventing missing files, unsupported commands, dependencies, frameworks, services, or capabilities.
- Judges AI answers against packet evidence for grounding failures.

## What SourcePack does not prove

SourcePack does not prove objective truth, semantic correctness, production readiness, security, or external service behavior.

It also does not execute the application by default. Capability detection remains structural and heuristic, SourcePack can miss indirect unsupported claims, and absence of evidence means unknown, not impossible.
