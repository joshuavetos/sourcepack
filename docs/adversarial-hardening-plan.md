# SourcePack Adversarial Hardening Plan

Status: working plan for `hardening-v1`

This document defines the hardening work that should precede broader agent, MCP, or hosted integration. It is based on the current SourcePack judgment path and is intentionally limited to repository-evidence trust, adversarial resistance, deterministic verdicts, and regression proof.

## Objective

Strengthen SourcePack so a proposed change cannot obtain a misleading PASS by manufacturing, modifying, obscuring, or confusing the repository evidence used to judge that same change.

The hardening release should improve four properties:

1. proposed-state evidence is never confused with trusted baseline evidence
2. incomplete analysis cannot silently become PASS
3. every decisive finding identifies the evidence and trust source that produced it
4. adversarial cases are captured as reproducible fixtures and remain stable across releases

## Current trust path

The current review path is:

1. validate or locate the trusted baseline
2. obtain the proposed diff
3. parse the diff into canonical file-change records
4. compare changed claims against baseline packet evidence and repository policy
5. add execution and policy findings
6. rebuild the final verdict from finding severity
7. emit reports, remediation, identities, and evidence records

Important existing protections:

- corrupt baselines fail closed
- CI cannot initialize a missing baseline
- a missing baseline with present changes fails
- stale baselines downgrade otherwise successful judgments to WARN
- `.sourcepack/` and `.git/` changes are protected
- unsafe and escaping paths are blocking
- policy findings include authority and provenance metadata
- final verdicts are rebuilt from surviving findings
- remediation fields are quoted to prevent repository-controlled prompt structure

## Evidence classes

SourcePack should explicitly classify every decisive fact into one of these classes:

### Trusted baseline evidence

Evidence captured in the reviewed baseline and validated before patch judgment.

Examples:

- tracked file inventory
- dependency declarations
- repository scripts and command definitions
- baseline metadata and hashes
- repository-local policy captured or resolved under established authority rules

### Proposed-state evidence

Evidence introduced or changed by the patch currently under review.

Examples:

- a dependency added to `pyproject.toml` in the same patch that imports it
- an npm script added to `package.json` in the same patch that invokes it
- a new test file added to satisfy a require-tests rule
- a policy edit that weakens a rule affecting the same patch

Proposed-state evidence may justify a WARN or review-required result, but it must never be reported as pre-existing trusted repository support.

### External caller-designated evidence

Evidence supplied outside the repository under an explicit trust decision.

Examples:

- organization policy passed with `--org-policy`
- committed-range refs selected by the caller

### Tooling and analysis state

Facts about SourcePack's ability to complete the review.

Examples:

- malformed diff
- unsupported ecosystem
- parser uncertainty
- unreadable artifact
- Git timeout

Tooling and analysis uncertainty must not collapse into ordinary support.

## Primary hardening target: same-patch self-justification

The current dependency resolver can classify a dependency added in the same patch as `WARN / declared_dependency`. The command resolver similarly classifies an npm script added in the same patch as `WARN / declared_command`.

This is reasonable only when the report clearly states that the support comes from proposed-state evidence and has not been accepted into the trusted baseline. The hardening work must prove that this distinction survives every layer, including raw judgment, normalized findings, remediation, Workbench presentation, report rebuilding, finding identity, policy suppression, replay, and evidence bundles.

### Attack hypotheses

#### H1: dependency self-justification is presented as trusted support

A patch adds a dependency declaration and imports that dependency. The unsupported dependency is removed from the blocking set, leaving a warning.

Required behavior:

- verdict is never plain PASS
- finding identifies the dependency manifest changed by the patch
- evidence class is `proposed_state`
- trust status is `untrusted_until_accepted`
- remediation must not say the dependency already existed in repository evidence
- repeated report rebuilding preserves the provenance

#### H2: command self-justification is presented as trusted support

A patch adds an npm script and references that script in the same patch.

Required behavior:

- verdict is WARN or FAIL according to policy
- finding identifies `package.json` as patch-modified evidence
- no presentation layer describes the script as pre-existing support

#### H3: manifest replacement hides undeclared use

A patch deletes or replaces the original manifest and supplies a new manifest containing the desired dependency or command.

Required behavior:

- replacement is recognized as proposed-state evidence
- deletion and recreation cannot erase the distinction between baseline and proposed state
- conflicting or duplicate manifests produce explicit uncertainty or failure

#### H4: policy self-modification weakens enforcement

A patch modifies repository policy while making a change that would be blocked by the original policy.

Required behavior:

- the patch is judged against the pre-change effective policy
- policy changes are separately surfaced for review
- organization and mixed authority cannot be weakened by repository changes
- repository policy changes never retroactively authorize the same patch

#### H5: tests self-justify a require-tests rule without adequate scope

A patch modifies a protected implementation path and adds an irrelevant or empty test file.

Required behavior:

- the rule must distinguish test-file presence from meaningful path relationship where supported
- unsupported relationship analysis must be marked uncertain, not supported

## Secondary hardening targets

### Diff integrity

The canonical parser normalizes separators, rejects absolute and drive paths, collapses in-repository `..` segments, and emits a synthetic malformed change when unsafe parsing occurs.

Adversarial fixtures must cover:

- quoted paths containing spaces
- tabs and timestamps in file markers
- rename and copy pairs with mismatched headers
- duplicate file sections
- missing hunk headers
- binary markers on protected paths
- path aliases that normalize to the same target
- Unicode normalization collisions
- case-only path collisions on case-insensitive filesystems
- symlink targets that resolve outside the repository

Required invariant:

Any path ambiguity that could change the trust target must produce FAIL or explicit UNREVIEWABLE state.

### Manifest ambiguity

Current dependency discovery supports root-level Python and Node manifests and warns on unsupported ecosystems.

Adversarial fixtures must cover:

- multiple `requirements*.txt` files with contradictory declarations
- root and nested `pyproject.toml` files
- root and nested `package.json` files
- monorepo imports crossing package boundaries
- optional and development dependency scopes used at runtime
- malformed manifests currently treated as empty
- duplicate JSON keys
- dependency aliases and import-name/package-name mismatches
- dynamic Python imports and JavaScript requires

Required invariant:

SourcePack must not claim repository-wide support when evidence is package-local, malformed, contradictory, or outside the analyzed scope.

### Command ambiguity

Current command resolution handles selected npm, Docker Compose, Make, Just, Task, pytest, tox, and nox patterns. Unsupported command shapes become `command_check_inconclusive` warnings.

Adversarial fixtures must cover:

- shell wrappers that invoke missing commands
- chained scripts
- npm lifecycle aliases
- workspace-qualified scripts
- Make includes and dynamic targets
- Taskfile includes
- tox factor expressions
- nox sessions with aliases or parameterization
- commands introduced through same-patch manifests

Required invariant:

An unparsed command must remain explicitly inconclusive and cannot become PASS through a broad project-level signal.

### Baseline and artifact integrity

Adversarial fixtures must cover:

- baseline metadata and packet disagreement
- manifest hash mismatch
- partial baseline deletion
- symlinked baseline artifacts
- stale baseline combined with policy suppression
- copied baseline from another repository
- baseline created at one repository root and consumed from a nested root
- report or ledger paths resolving outside the repository

Required invariant:

The baseline identity must bind repository root, captured evidence, and metadata. Any decisive mismatch fails closed.

### Verdict composition

Current verdict composition uses error findings for FAIL, warning findings for WARN, and otherwise PASS.

Hardening should introduce an internal analysis status independent of display verdict:

- `SUPPORTED`
- `CONTRADICTED`
- `UNSUPPORTED`
- `UNKNOWN`
- `UNREVIEWABLE`

The public PASS/WARN/FAIL result may remain, but mappings must be explicit and tested.

Required invariant:

PASS is possible only when all mandatory checks completed and no mandatory check returned UNKNOWN or UNREVIEWABLE.

## Provenance contract

Every blocking or review-required finding should be able to carry:

- `evidence_class`
- `trust_status`
- `source_path`
- `source_kind`
- `source_sha256`
- `baseline_or_proposed`
- `modified_by_patch`
- `extraction_method`
- `evidence_span` when available
- `analysis_status`

This should be additive first. Existing schemas and presentation layers should remain compatible until a deliberate versioned contract change is approved.

## Fixture format

Add a versioned adversarial corpus under:

```text
benchmarks/adversarial/
```

Each case should contain:

```text
case-id/
  repo_before/
  patch.diff
  expected.json
  case.md
```

`expected.json` should minimally contain:

```json
{
  "schema_version": "sourcepack.adversarial_case.v1",
  "expected_verdict": "FAIL",
  "required_reason_codes": ["unsupported_dependency"],
  "forbidden_reason_codes": [],
  "required_analysis_status": "UNSUPPORTED",
  "deterministic": true
}
```

The benchmark runner should execute each case repeatedly and compare normalized outputs.

## Implementation sequence

### PR 1: adversarial fixtures for same-patch evidence

Add tests only. Do not change production behavior.

Cases:

1. Python dependency added and imported in same patch
2. npm dependency added and imported in same patch
3. npm script added and referenced in same patch
4. manifest deleted and recreated with self-justifying declaration
5. duplicate manifests with contradictory evidence
6. repository policy weakened in the same patch

Expected result:

The tests document current behavior and intentionally fail where provenance or verdict semantics are insufficient.

### PR 2: evidence-class and trust-status metadata

Add provenance metadata to dependency and command resolutions, then preserve it through normalized findings and report rebuilding.

No broad resolver expansion in this PR.

### PR 3: pre-change policy enforcement

Prove that repository policy edits cannot authorize the same patch. Add explicit policy-change findings and tests for organization, mixed, and repository authority.

### PR 4: manifest scope and ambiguity

Introduce package-scope ownership for nested manifests and explicit ambiguity findings for conflicting or malformed evidence.

### PR 5: diff and path adversarial suite

Expand parser fixtures, symlink checks, normalized-path collision detection, and fail-closed behavior.

### PR 6: analysis-state model

Add internal `SUPPORTED / CONTRADICTED / UNSUPPORTED / UNKNOWN / UNREVIEWABLE` status and map it deterministically to public verdicts.

### PR 7: benchmark runner and release report

Create the versioned adversarial runner, repeated-run determinism checks, and machine-readable summary.

## Release gates before broader integration

API, MCP, autonomous retry loops, and broader hosted integration remain blocked until all gates pass:

1. every critical trust boundary has at least one adversarial fixture
2. no critical same-patch evidence case produces plain PASS
3. proposed-state evidence is explicitly labeled through canonical reports and remediation
4. incomplete mandatory analysis cannot produce PASS
5. repeated benchmark runs produce byte-stable normalized judgments
6. malformed, contradictory, or unreadable decisive evidence fails closed
7. policy changes cannot authorize the same patch
8. critical path and baseline tampering fixtures all fail
9. every blocking finding identifies its decisive evidence source
10. the complete hosted CI suite passes on the hardening branch

## Non-goals for this hardening release

- proving semantic correctness
- proving security
- general code review
- vulnerability scanning
- arbitrary command execution
- autonomous repair
- model invocation
- broad ecosystem support without bounded resolvers
- replacing tests, linters, type checking, or human review

## First action

The next change should add adversarial tests for dependency and command same-patch self-justification without modifying production code. The tests should lock down the distinction between trusted baseline evidence and proposed-state evidence before any resolver behavior is changed.
