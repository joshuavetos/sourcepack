# SourcePack Command Center API

The experimental Command Center exposes one authenticated aggregate endpoint:

```text
GET /api/command-center/v1/snapshot
X-SourcePack-Token: <workbench session token>
```

The response contains the canonical Command Center snapshot built from the repository's existing Git, baseline, policy, status, and report readers.

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
    "artifacts": {}
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
- additive compatibility inside raw artifact payloads.

Raw baseline, policy, status, report, and report-error objects remain preserved under `artifacts`. Their internal schemas are owned by their respective producers and are intentionally not redefined by the Command Center contract.

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
| `state` | Explicit backend classification for the overall snapshot and report, baseline, policy, and replay inputs. | Never null. Report distinguishes `unavailable`, `malformed`, and `unsupported`; policy and replay can be `degraded`. |
| `posture` | Verdict, finding/blocker/warning counts, baseline state, policy resolution, and automatic-mode posture derived from the canonical report and readers. | `verdict`, baseline state, and policy status may be null when their producers supply no value; counts remain zero without a valid report. |
| `scores` | Deterministic backend-owned operational indicators. | Never null; these are product indicators, not security guarantees. |
| `capabilities` | Fixed registry of explicitly supported, partial, planned, or setup-dependent capabilities. | Never null; capability status is never inferred by the browser. |
| `priority_actions` | Ordered backend queue with ID, priority, label, reason, action type, and bounded command or target metadata. | May be empty; command and target are explicitly null when inapplicable. |
| `activity` | Deterministic repository/baseline/policy/review lifecycle events and an optional terminal artifact error. | Never null; unsupported same-version verdicts use the canonical `Latest report state: unsupported` review message, while malformed or unsupported-version artifacts append an error event. |
| `available_artifacts` | Canonical usability flags for baseline, policy, supported canonical report, replay, and persisted decisions. | Never null; an unsupported raw report remains inspectable under `artifacts.report` but its report availability flag is false. |
| `workbench` | Backend-owned bounded-review/correction action, bounded changed-file excerpt, evidence-card display model, and correction-summary rows. | `proposed_change` is null and presentation arrays are empty without a supported canonical report. |
| `artifacts` | Bundled canonical baseline, policy, status, report, report error, and persisted-decision payloads used to construct the snapshot. | Report and report error are mutually exclusive and nullable; producer-owned objects may contain additive fields. |

## Provenance and failure rules

The single builder reads only canonical Git metadata, baseline validation, effective policy resolution, SourcePack status, canonical report/replay evidence, persisted decisions, and the fixed capability/action registries. The authenticated endpoint validates both the JSON Schema and cross-field derivations. Invalid construction fails closed with `command_center_snapshot_failed`; it never emits a partial snapshot. The Workbench fetches this endpoint once and does not merge the raw diagnostic endpoints into application state. Raw endpoints remain available for diagnostics.

## Known limitations

The contract is local and release-coupled, activity is a current-state lifecycle summary rather than a durable audit log, capability scores are coarse product indicators, and replay is degraded when a canonical report has no replay bundle. The snapshot embeds raw producer payloads, so it can be larger than the previous overview response. Persisted decisions currently expose the established override-ledger view rather than every possible future decision type.
