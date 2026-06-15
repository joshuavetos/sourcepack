# SourcePack

Know what your AI actually saw.

SourcePack is a local-first CLI for creating verifiable AI context packets from local source folders. It builds context artifacts, records included and ignored files, generates receipt hashes, verifies packet integrity, checks source drift with `--against`, and judges AI-generated answers for unsupported file, dependency, command, and capability references.

## Install

```bash
python -m pip install -e .
```

## Commands

```bash
sourcepack doctor
sourcepack init .
sourcepack build examples/demo_repo --out examples/demo_packet --force
sourcepack verify examples/demo_packet
sourcepack verify examples/demo_packet --against examples/demo_repo
sourcepack judge examples/demo_packet examples/fake_ai_answer.md --out examples/judgment
```

## What SourcePack does

- Builds AI-ready `context.md` and `context.xml` packets.
- Generates `manifest.json`, `receipt.json`, `file_tree.txt`, `ignored_files.txt`, and `token_report.json`.
- Verifies packet files against receipt hashes.
- Checks whether source files drifted after packet creation.
- Judges an AI answer against the packet manifest and deterministic project evidence.

## What SourcePack does not do

- It does not prove objective truth.
- It does not replace code review.
- It does not guarantee all hallucinations are detected.
- It checks explicit grounding signals: files, dependencies, commands, and capability evidence.
