# SourcePack project state

## Completed

- Backend-owned Workbench review actions include structured action type, label, reason, availability, prompt/target metadata, and remain bounded by the authenticated review endpoint.
- `sourcepack.command_center.v1` is the single canonical Command Center/Workbench snapshot and is explicitly an **internal versioned contract**, not a public compatibility promise.
- The Workbench now loads one authenticated snapshot instead of assembling dashboard state from overview, report, policy, baseline, replay, override, and status responses.
- Contract validation covers the closed modeled shape and backend cross-field derivations; raw diagnostic endpoints remain available.
- Workbench action, excerpt, excerpt-line, evidence-card, and correction-row models are closed and schema validated; unsupported raw reports cannot contribute canonical counts or display claims.
- Unsupported raw verdicts cannot contribute activity or replay claims, and review-action variants enforce consistent availability, targets, and prompt presence.
- Command Center producer diagnostics, collections, strings, nesting, excerpts, and final serialized output are backend-bounded with explicit canonical totals and omission metadata.

## Verification

- `pytest -q` — 1051 passed, 41 subtests passed.
- `pytest -q tests/test_command_center_snapshot_v1.py tests/test_command_center_contract.py tests/test_command_center_endpoint.py tests/test_command_center_error_integrity.py tests/test_command_center_activity_message_integrity.py tests/test_command_center_priority_integrity.py tests/test_workbench_remediation.py tests/test_command_center_aggregate_client.py tests/test_command_center_mission_control_contract.py tests/test_command_center_static.py tests/test_workbench.py` — 118 passed, 17 subtests passed.
- `python scripts/release_smoke.py` — passed distribution build, metadata validation, fresh wheel/sdist installation, and authenticated Workbench smoke checks.
- `node --check src/sourcepack/workbench_static/command-center-aggregate.js` — passed.
- `python -m compileall -q src` — passed.
- `ruff check src/sourcepack/command_center.py src/sourcepack/command_center_contract.py src/sourcepack/command_center_endpoint.py tests/test_command_center_snapshot_v1.py` — passed.
- `git diff --check` — passed.

## Current risks

- Activity is a deterministic current-state summary, not a durable event history.
- Persisted decision coverage is currently limited to the established override ledger view.
- Operational scores remain coarse product indicators rather than security guarantees.
- Producer objects are built before the snapshot projection, so their producer-specific construction costs remain outside this transport boundary.

## Next recommended task

Bound producer-side construction of canonical report, policy, and decision objects before they reach the Command Center projection.
