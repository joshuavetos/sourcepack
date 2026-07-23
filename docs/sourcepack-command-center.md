# SourcePack Command Center

SourcePack becomes a full AI software operations platform built around one rule: every agent action must remain inspectable, reproducible, policy-bound, and grounded in repository evidence.

## Product surfaces

1. **Mission Control**
   - live repository health
   - current branch and dirty-state visibility
   - active agent sessions
   - latest verdict, blockers, warnings, and unresolved uncertainty
   - recent reviews and replayable runs

2. **Live Patch Review**
   - paste, upload, or capture a proposed patch
   - side-by-side diff and repository evidence
   - dependency, command, policy, path, baseline, and manifest checks
   - typed provenance on every decisive finding
   - one-click correction prompt for coding agents

3. **Agent Gateway**
   - adapters for Codex, ChatGPT, Claude, Gemini, GitHub Copilot, Cursor, Windsurf, and generic MCP clients
   - a common preflight and postflight contract
   - tool-call receipts and agent-session identity
   - bounded approval gates before repository mutation

4. **Adversarial Lab**
   - built-in attack corpus
   - same-patch evidence attacks
   - policy self-weakening
   - malformed manifest attacks
   - baseline tampering
   - missing mandatory analysis
   - deterministic repeat and mutation testing

5. **Evidence Graph**
   - visualize claims, files, manifests, policies, commands, dependencies, checks, and verdicts
   - trace each finding to trusted, proposed, caller-designated, or analysis-state evidence
   - compare pre-change and proposed repository state
   - inspect content hashes and extraction methods

6. **Policy Studio**
   - visual policy editor
   - organization, caller, and repository authority layers
   - conflict and weakening detection
   - protected paths, dependency rules, required tests, package-manager rules, and secret-pattern controls
   - policy simulation against saved patches before acceptance

7. **Replay Theater**
   - deterministic reconstruction of prior judgments
   - timeline of checks, evidence, decisions, and overrides
   - compare two runs and identify why verdicts changed
   - export JSON, Markdown, HTML, SARIF, and signed receipt bundles

8. **Repository Memory**
   - trusted baseline history
   - accepted policy history
   - known commands and dependencies
   - recurring failure patterns
   - previous remediation prompts and outcomes
   - drift detection across branches and releases

9. **Team Review Room**
   - shareable review bundles
   - comments attached to findings and evidence
   - explicit approve, reject, waive, or request-fix decisions
   - durable decision ledger
   - reviewer identity and timestamped audit trail

10. **Integration Hub**
    - GitHub pull requests, checks, issues, and Actions
    - GitLab merge requests and pipelines
    - Bitbucket pull requests
    - Slack and Microsoft Teams notifications
    - Jira and Linear issue linking
    - VS Code and JetBrains launch points
    - MCP server and local HTTP API
    - webhooks and CI adapters

11. **Demo Arena**
    - guided attacks that visibly fail
    - clean patch that visibly passes
    - policy attack, fake dependency, invented command, malformed manifest, and baseline-tampering scenarios
    - narrated judge mode with a concise explanation of what SourcePack proved and what it did not prove

12. **Developer Platform**
    - Python API
    - CLI
    - local Workbench
    - MCP server
    - typed JSON schemas
    - plugin SDK for custom checks
    - custom evidence extractors
    - custom policy rules

## Command Center navigation

The Workbench becomes the Command Center with these primary sections:

- Overview
- Live Review
- Evidence Graph
- Agents
- Adversarial Lab
- Policy Studio
- Replay
- Memory
- Integrations
- Team Decisions
- Demo Arena
- Settings

## First executable vertical slice

The first slice must be real, not decorative:

1. Add a single Command Center overview endpoint that aggregates repository, baseline, policy, latest report, replay, and integration capability state.
2. Replace the narrow Workbench navigation with the full product shell while preserving existing review functionality.
3. Add capability cards whose state is derived from backend facts, never hard-coded claims.
4. Add a session activity timeline sourced from existing report and decision artifacts.
5. Add an integration registry with honest states: available, configured, disconnected, unsupported.
6. Add regression tests for authentication, deterministic payloads, missing artifacts, malformed artifacts, and no false connected-state claims.

## Non-negotiable trust rules

- Proposed evidence never becomes trusted because it appears in the same patch.
- Policy changes cannot govern the patch introducing them.
- Missing or incomplete mandatory analysis cannot produce PASS.
- Every decisive finding carries typed analysis status and provenance.
- Integrations are reported as connected only from verified configuration or a successful handshake.
- The Command Center cannot execute arbitrary shell commands.
- The platform does not claim semantic correctness, security proof, dependency safety, external API truth, or user-intent alignment.

## Delivery sequence

1. Command Center shell and aggregate API
2. Agent Gateway and integration registry
3. Adversarial Lab runner and corpus
4. Evidence Graph
5. Policy Studio
6. Replay Theater
7. Repository Memory
8. Team Review Room
9. MCP and editor integrations
10. Demo Arena and submission-grade guided experience
