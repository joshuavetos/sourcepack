# SourcePack

SourcePack catches fake repo facts in AI-generated code changes before they become review facts.

**SourcePack checks proposed diffs against locally verifiable evidence from the actual codebase.**

Concrete first scenario: an AI assistant proposes adding FastAPI code to a repository that does not use FastAPI. SourcePack checks the proposed change against local repo evidence, sees that `fastapi` is not declared, and flags the change as an unsupported dependency before review.

SourcePack is a local public-alpha guardrail for reviewing repo changes. It does not prove code correctness, security, runtime success, dependency safety, semantic validity, external API truth, or user intent.

SourcePack targets a narrow problem:

- AI coding agents can edit files that do not exist.
- They can import undeclared dependencies.
- They can reference missing scripts or unsupported commands.
- They can reshape project structure based on prompt assumptions.
- SourcePack catches those locally verifiable failures before commit or in CI.

## Try the demo first

```bash
python -m pip install sourcepack
sourcepack demo
