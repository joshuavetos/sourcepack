# SourcePack project state

## Completed

- Canonical report loading/construction, effective-policy inputs, and persisted-decision dashboard iteration now stop at producer-owned byte, record, collection, string, and nesting limits before Command Center projection. Finding truncation propagates incomplete authority through report, overview, replay-evidence, and Command Center states; ledger metadata distinguishes consumed from retained records while reads use a strict total-byte budget plus one probe and whitespace-aware bounded look-ahead.

- Backend-owned Workbench review actions include structured action type, label, reason, availability, prompt/target metadata, and remain bounded by the authenticated review endpoint.
- `sourcepack.command_center.v1` is the single canonical Command Center/Workbench snapshot and is explicitly an **internal versioned contract**, not a public compatibility promise.
- The Workbench now loads one authenticated snapshot instead of assembling dashboard state from overview, report, policy, baseline, replay, override, and status responses.
- Contract validation covers the closed modeled shape and backend cross-field derivations; raw diagnostic endpoints remain available.
- Workbench action, excerpt, excerpt-line, evidence-card, and correction-row models are closed and schema validated; unsupported raw reports cannot contribute canonical counts or display claims.
- Unsupported raw verdicts cannot contribute activity or replay claims, and review-action variants enforce consistent availability, targets, and prompt presence.
- Command Center producer diagnostics, collections, strings, nesting, excerpts, and final serialized output are backend-bounded with explicit canonical totals and omission metadata.

## Verification

- `PYTHONPATH=src python -m pytest -q` — 1112 passed, 18 skipped, 41 subtests passed.
- `PYTHONPATH=src python -m pytest -q tests/test_producer_bounds.py` — 28 passed.
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
- Producer bounds deliberately reject oversized canonical artifacts and policy inputs; callers needing complete oversized artifacts require a separate offline/indexed workflow.
- Git diff, tracked-path, base-tree, and untracked-file acquisition now drains producer output incrementally under byte and time limits. Limit hits fail closed and use canonical incomplete authority rather than treating retained prefixes as complete evidence.
- Analyzer repository discovery now routes recursive source and verification traversal through the deterministic `SourceScanner` producer, with entry, depth, per-file, and aggregate-read limits. Baseline construction rejects incomplete scans.
- Policy and canonical-report JSON structure checks occur after full `json.loads` construction; their strict byte caps provide finite input bounds, not streaming parser or per-object instantiation guarantees.

## Next recommended task

The remaining producer-hardening surface is non-analyzer operational tooling (fleet artifact discovery and packet output cleanup), which does not contribute repository evidence to a PASS judgment but should adopt the same bounded iterator pattern in a future maintenance pass.
