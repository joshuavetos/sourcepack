# SourcePack Build Week Evidence

This document records the concrete OpenAI Build Week development workflow behind SourcePack and gives judges a direct path to inspect and run the project.

## Product

SourcePack is a local-first repository evidence guardrail for AI-generated code changes. It checks a proposed diff against locally verifiable repository facts and reports unsupported assumptions such as undeclared dependencies, missing files, unsupported commands, unsafe paths, protected trust artifacts, malformed diffs, and selected policy violations.

Its claim is deliberately bounded. SourcePack does not prove semantic correctness, security, runtime success, external API behavior, dependency safety, or user intent.

## Build Week development workflow

SourcePack was developed through a repeated human-directed GPT-5.6 and Codex workflow:

1. Joshua Vetos selected the product goal, constraints, trust boundaries, and acceptable claim.
2. GPT-5.6 translated those decisions into bounded implementation specifications, reviewed results against the requested contract, identified gaps, and produced correction instructions.
3. Codex implemented repository changes, tests, documentation, and pull requests.
4. Joshua decided what to accept, reject, correct, and merge.

This was not a one-shot code-generation exercise. The repository history preserves the specification, implementation, correction, and merge loop.

## Concrete GPT-5.6 evidence

### PR #159: README rewrite

[PR #159, Rewrite README for clarity and focus](https://github.com/joshuavetos/sourcepack/pull/159), is a direct repository artifact from the GPT-5.6-directed workflow.

The work was directed through GPT-5.6, which shaped the repository change around one restrained product claim, a faster demo path, clearer trust boundaries, and removal of stale milestone-era framing. The resulting pull request was reviewed and merged, and the revised README is now the public front door of the repository.

The supporting conversation history can be shown in the submission video alongside the merged pull request and resulting README.

## Concrete Codex evidence

Codex task links are preserved in pull-request descriptions. Build Week implementation work includes:

- [PR #148](https://github.com/joshuavetos/sourcepack/pull/148): evidence bundle creation and verification
- [PR #149](https://github.com/joshuavetos/sourcepack/pull/149): explicit diff exit policies
- [PR #150](https://github.com/joshuavetos/sourcepack/pull/150): organization-policy resolution
- [PR #151](https://github.com/joshuavetos/sourcepack/pull/151): first-class policy findings integrated into canonical judgment
- [PR #152](https://github.com/joshuavetos/sourcepack/pull/152): policy suppression, stale-baseline composition, and idempotency fixes
- [PR #153](https://github.com/joshuavetos/sourcepack/pull/153): offline JSON Schema registry and schema CLI
- [PR #154](https://github.com/joshuavetos/sourcepack/pull/154): local read-only Workbench
- [PR #155](https://github.com/joshuavetos/sourcepack/pull/155): optional hosted control plane and cloud client
- [PR #156](https://github.com/joshuavetos/sourcepack/pull/156): transaction-safe membership lifecycle
- [PR #157](https://github.com/joshuavetos/sourcepack/pull/157): idempotent hosted mutations and one-time service-token disclosure
- [PR #158](https://github.com/joshuavetos/sourcepack/pull/158): audit-events API and transactional audit handling
- [PR #160](https://github.com/joshuavetos/sourcepack/pull/160): atomic hosted credential revocation and hardened logout behavior

These PRs provide dated, inspectable evidence of what changed during Build Week. Each PR states its motivation, scope, implementation, tests, and linked Codex task.

## Historical product evidence

SourcePack was shaped by failures encountered during AI-directed development.

[PR #129](https://github.com/joshuavetos/sourcepack/pull/129) refreshed trusted baseline artifacts from a dirty working tree and recorded `"dirty": true` in baseline metadata. No automated test suite was run for that patch. SourcePack was later hardened to refuse creation or refresh of trusted baseline state from a dirty Git worktree unless a human explicitly supplies `--force`.

This is a concrete example of the trust-boundary problem SourcePack addresses: generated work must not silently become the evidence used to judge itself.

## Fast judge path

Install and run the packaged demonstration:

```bash
python -m pip install sourcepack
sourcepack demo
```

The demonstration creates a small local repository, applies a patch that imports FastAPI without declaring it, and checks the patch against repository evidence.

The decisive output includes:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.

Verdict: FAIL
```

The human signal is `RED LIGHT`, the formal judgment is `FAIL`, and the machine-readable reason code is `unsupported_dependency`. In the packaged Workbench demonstration, correcting that change back to repository-supported Flask yields `PASS` with the judge-facing reason `change_supported`.

## Repository inspection path

For a real repository:

```bash
sourcepack init . --auto
sourcepack diff .
sourcepack report open
```

For a committed pull-request range:

```bash
sourcepack diff . --base-ref <base> --head-ref <head> --ci --json --exit-policy fail-only
```

The local Workbench is available with:

```bash
sourcepack ui .
```

It is loopback-only, read-only, token-protected, and does not make external network requests.

## What the submission can prove

The submission can directly prove:

- a public repository and installable package exist
- the one-command demo produces a bounded repository-evidence failure
- GPT-5.6 materially shaped specifications, review, corrections, and public repository changes
- Codex implemented substantial repository work through linked tasks and pull requests
- Build Week work is separated by dated PR history
- the project has tests, CI behavior, reports, replay, evidence bundles, policy enforcement, schema contracts, and a local Workbench

The submission should not claim that SourcePack proves code correctness, security, runtime success, semantic validity, production readiness, or every form of AI hallucination.
