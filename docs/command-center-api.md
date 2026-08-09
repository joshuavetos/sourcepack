# SourcePack Command Center API

The experimental Command Center exposes one authenticated aggregate endpoint:

```text
GET /api/command-center/v1/snapshot
X-SourcePack-Token: <workbench session token>
```

The canonical Workbench request handler registers and dispatches this route directly.
Importing the package does not install, wrap, or replace a Workbench handler. Snapshot
construction remains in the Command Center module and contract validation remains in
the contract layer; the router only authenticates, invokes the canonical payload
builder, and serializes its result.

The response contains the canonical Command Center snapshot built from the repository's existing Git, baseline, policy, status, and report readers.

## Verified growth paths

The pre-hardening composition review found six embedded producer objects: Git metadata,
baseline validation, effective policy, status, canonical report/report error, and the override
dashboard. The report could grow through findings, blockers, warnings, evidence variants,
reason-code maps, remediation, replay bundles, paths, raw patch/report fields, and arbitrary
nested metadata. Policy rules/material and override history were repository-sized; Git/status,
error messages, branch/path/time strings, evidence cards, correction rows, and activity text were
string-sized. Changed-file excerpts were already limited to eight paths, 128 KiB read per file,
and twelve selected lines, but individual line text was not clipped. Capabilities (nine), priority
actions (eight), activity (four plus one error), evidence cards (six), and correction rows (three)
were already count-bounded. The new projection bounds all indirect producer nesting as well as
these direct display paths; excerpt reads remain capped and excerpt line text is now clipped.

## Response shape

```json
{
  "ok": true,
  "status": "success",
  "snapshot": {
    "schema_version": "sourcepack.command_center.v1",
    "sourcepack_version": "...",
    "repository": {},
    "posture": {},
    "scores": {},
    "capabilities": [],
    "priority_actions": [],
    "activity": [],
    "artifacts": {},
    "bounds": {}
  }
}
```

## Contract guarantees

`sourcepack.command_center.v1` is a versioned local application contract. It is not yet a promise of long-term external API stability.

The backend validates every successful endpoint response against the canonical contract before sending it. The contract defines:

- required and nullable fields;
- closed top-level and modeled-section shapes;
- capability, action, priority, activity, and verdict vocabularies;
- canonical capability ordering;
- deterministic priority ordering and unique action IDs;
- bounded action payload rules;
- score ranges;
- additive compatibility inside bounded artifact diagnostics.

Producer diagnostics under `artifacts` are deterministic bounded projections, not complete raw
objects. Strings are limited to 2,048 code points (correction prompts to 8,192), lists and
mappings to 64 entries, and nesting to six levels. Mapping keys are sorted; lists retain producer
order; clipped text ends in `…[truncated]`. Findings, blockers, warnings, and evidence expose
`total_count`, `displayed_count`, `omitted_count`, and `truncated` under `bounds`, so canonical
totals are never confused with the displayed subset.

The compact UTF-8 serialization of a snapshot is limited to 262,144 bytes. After construction and
validation, the backend performs at most three deterministic reduction stages: decisions first,
then policy/baseline/status diagnostics, then nonessential report detail. It serializes after each
stage and stops immediately once the snapshot fits. Verdict, posture, totals,
scores, action selection, replay availability, and error integrity are retained and the result is
revalidated. If those essential fields cannot fit, the endpoint returns the established safe error
envelope and sends no partial snapshot. Bounding performs no review, repair, baseline mutation, or
trust-state mutation.

An invalid snapshot fails closed with the existing `command_center_snapshot_failed` response rather than sending a partially valid application state.

The endpoint preserves the Workbench session-token boundary, runs no arbitrary commands, and does not create or refresh trusted baseline state.

## Canonical snapshot field reference

This is an **internal versioned contract**, not a public compatibility contract. Consumers shipped in the same SourcePack release may depend on the complete `sourcepack.command_center.v1` shape. A breaking field, vocabulary, nullability, or semantic change requires a new schema identifier and endpoint version; raw diagnostic endpoint contracts are independent.

| Field | Meaning and provenance | Nullability / degradation |
|---|---|---|
| `schema_version` | Literal contract identifier owned by the snapshot builder. | Never null. |
| `sourcepack_version` | Installed SourcePack package version. | Never null. |
| `repository` | Resolved repository path and canonical Git metadata. | Never null; individual Git metadata remains producer-defined. |
| `display` | Backend-owned verdict labels/icons/classes and repository, finding, evidence, version, and report-time display values. | Branch and report time may be null; the browser renders values without interpreting verdicts or missing producer fields. |
| `state` | Explicit backend classification for the overall snapshot and report, baseline, policy, and replay inputs. | Never null. Report distinguishes `available`, `incomplete`, `unavailable`, `malformed`, and `unsupported`; policy and replay can be `degraded`. |
| `posture` | Verdict, finding/blocker/warning counts, baseline state, policy resolution, and automatic-mode posture derived from the canonical report and readers. | `verdict`, baseline state, and policy status may be null when their producers supply no value; counts remain zero without a valid report. |
| `scores` | Deterministic backend-owned operational indicators. | Never null; these are product indicators, not security guarantees. |
| `capabilities` | Fixed registry of explicitly supported, partial, planned, or setup-dependent capabilities. | Never null; capability status is never inferred by the browser. |
| `priority_actions` | Ordered backend queue with ID, priority, label, reason, action type, and bounded command or target metadata. | May be empty; command and target are explicitly null when inapplicable. |
| `activity` | Deterministic repository/baseline/policy/review lifecycle events and an optional terminal artifact error. | Never null; unsupported same-version verdicts use the canonical `Latest report state: unsupported` review message, while malformed or unsupported-version artifacts append an error event. |
| `available_artifacts` | Canonical usability flags for baseline, policy, supported complete canonical report, replay, and persisted decisions. | Never null; unsupported or incomplete raw reports remain inspectable under `artifacts.report` but their report availability flag is false. |
| `workbench` | Backend-owned bounded-review/correction action, bounded changed-file excerpt, evidence-card display model, and correction-summary rows. | `proposed_change` is null and presentation arrays are empty without a supported canonical report. |
| `artifacts` | Bundled canonical baseline, policy, status, report, report error, and persisted-decision payloads used to construct the snapshot. | Report and report error are mutually exclusive and nullable; producer-owned objects may contain additive fields. |
| `bounds` | Transport limit and honest per-collection/per-artifact truncation metadata. | Counts describe canonical totals and displayed subsets; omission reasons identify final byte-limit reduction. |

## Provenance and failure rules

The single builder reads only canonical Git metadata, baseline validation, effective policy resolution, SourcePack status, canonical report/replay evidence, persisted decisions, and the fixed capability/action registries. The authenticated endpoint validates both the JSON Schema and cross-field derivations. Invalid construction fails closed with `command_center_snapshot_failed`; it never emits a partial snapshot. The Workbench fetches this endpoint once and does not merge the raw diagnostic endpoints into application state. Raw endpoints remain available for diagnostics.

## Known limitations

The contract is local and release-coupled, activity is a current-state lifecycle summary rather than a durable audit log, capability scores are coarse product indicators, and replay is degraded when a canonical report has no replay bundle or explicitly incomplete construction authority. `state.report` is `incomplete` for the latter case even when retained evidence preserves a FAIL verdict. Bounding limits transport and rendering cost; it does **not** prove repository completeness, correctness, or security. Producer-specific read and construction limits remain separate from this projection. Persisted decisions currently expose the established override-ledger view rather than every possible future decision type.
