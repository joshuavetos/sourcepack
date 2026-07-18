# Submission Proof Map

## Product proof

Run the released package:

```bash
python -m pip install sourcepack
sourcepack demo
```

## GPT-5.6 proof

Show the conversation that produced the repository change merged in PR #159, then show the merged PR and live README.

## Codex proof

Show a linked Codex task in a merged Build Week PR, the implemented change, tests, and any correction cycle.

## Historical trust-boundary proof

Show PR #129 recording a trusted baseline generated from a dirty worktree, then show the current documented refusal to create trusted baseline state from a dirty worktree without `--force`.

## Boundaries

Do not present semantic bugs, security defects, or runtime failures as findings SourcePack necessarily detects unless the finding is grounded in one of SourcePack's documented repository-evidence checks.
