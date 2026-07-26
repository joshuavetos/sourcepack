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

The endpoint preserves the Workbench session-token boundary, runs no arbitrary commands, and does not create or refresh trusted baseline state.
