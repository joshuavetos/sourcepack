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
