# SourcePack Submission Summary

SourcePack blocks AI-generated code changes that rely on repository facts the local codebase does not support.

The submission should demonstrate three things:

1. A public, installable developer tool exists.
2. The tool catches a concrete unsupported repository assumption.
3. GPT-5.6 and Codex materially shaped the repository through an inspectable specification, implementation, correction, and merge workflow.

## One-command proof

```bash
python -m pip install sourcepack
sourcepack demo
```

Expected decisive result:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.

Verdict: FAIL
```

## Development proof

- GPT-5.6-directed repository change: [PR #159](https://github.com/joshuavetos/sourcepack/pull/159)
- Codex implementation history: [PRs #148 through #160](https://github.com/joshuavetos/sourcepack/pulls?q=is%3Apr+is%3Amerged+148..160)
- Historical trust-boundary example: [PR #129](https://github.com/joshuavetos/sourcepack/pull/129)

## Claim boundary

SourcePack checks locally verifiable repository assumptions. It does not prove semantic correctness, security, runtime success, external API truth, dependency safety, or user intent.
