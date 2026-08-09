# SourcePack project state

## Completed

- **Producer hardening is closed.** The final closure audit covered bounded Git diff, tracked-path,
  base-tree, and untracked-content acquisition; repository scanning and baseline packet inputs;
  canonical report construction/loading; effective-policy and persisted-decision loading; fleet
  discovery and artifact/event reads; packet-output cleanup; and packet verification. Incomplete
  prefixes remain non-authoritative, cannot activate a trusted baseline, and are not reported with
  exact totals unless their source was exhausted. This closure is limited to the implemented
  producer and operational boundaries: it is not a claim that SourcePack is secure, correct,
  universally bounded, or complete for external repositories and ecosystems. Maintenance outside
  those authority/completeness contracts does not reopen this project without a demonstrated
  regression against them.

- Directory-to-symlink collision judgment uses the trusted baseline inventory (or the explicitly
  acquired base tree for range review) once per report, never a per-link current-index substitute.
  It bounds proposed transitions, aggregate and per-transition entries, traversal depth, retained
  evidence, strings, and batched `git check-ignore --stdin -z` input/output. Proven nonempty real
  directories with content outside trusted tracked evidence fail as
  `symlink_replaces_nonempty_directory`; producer limits, acquisition failures, symlinked parent
  components, and unavailable historical state fail separately as
  `symlink_worktree_inspection_incomplete`. A current resulting symlink is post-transition evidence,
  not proof of what occupied the path earlier.

- Fleet artifact discovery and packet-output cleanup now have deterministic producer-owned entry, depth, record, file-byte, aggregate-byte, and cleanup limits. Decision-ledger metadata keeps artifact-path discovery counts and event consumption/retention counts in separate envelopes with independent limits, and ledger reads stop after one valid-event overflow probe. Structured outcomes distinguish complete, boundary-incomplete, and failed work without treating retained prefixes as exhaustive; cleanup remains symlink-safe and path-confined. This bounds operational resource use and cleanup completeness, not repository correctness, security, runtime validity, complete external fleet discovery, or PASS authority.

- Canonical report loading/construction, effective-policy inputs, and persisted-decision dashboard iteration now stop at producer-owned byte, record, collection, string, and nesting limits before Command Center projection. Finding truncation propagates incomplete authority through report, overview, replay-evidence, and Command Center states; ledger metadata distinguishes consumed from retained records while reads use a strict total-byte budget plus one probe and whitespace-aware bounded look-ahead.

- Backend-owned Workbench review actions include structured action type, label, reason, availability, prompt/target metadata, and remain bounded by the authenticated review endpoint.
- `sourcepack.command_center.v1` is the single canonical Command Center/Workbench snapshot and is explicitly an **internal versioned contract**, not a public compatibility promise.
- The Workbench now loads one authenticated snapshot instead of assembling dashboard state from overview, report, policy, baseline, replay, override, and status responses.
- Contract validation covers the closed modeled shape and backend cross-field derivations; raw diagnostic endpoints remain available.
- Workbench action, excerpt, excerpt-line, evidence-card, and correction-row models are closed and schema validated; unsupported raw reports cannot contribute canonical counts or display claims.
- Unsupported raw verdicts cannot contribute activity or replay claims, and review-action variants enforce consistent availability, targets, and prompt presence.
- Command Center producer diagnostics, collections, strings, nesting, excerpts, and final serialized output are backend-bounded with explicit canonical totals and omission metadata.

## Verification

- `PYTHONPATH=src python -m pytest -q` — 1132 passed, 18 skipped, 41 subtests passed.
- `PYTHONPATH=src python -m pytest -q tests/test_operational_producer_bounds.py tests/test_producer_bounds.py` — 40 passed.
- `pytest -q tests/test_command_center_snapshot_v1.py tests/test_command_center_contract.py tests/test_command_center_endpoint.py tests/test_command_center_error_integrity.py tests/test_command_center_activity_message_integrity.py tests/test_command_center_priority_integrity.py tests/test_workbench_remediation.py tests/test_command_center_aggregate_client.py tests/test_command_center_mission_control_contract.py tests/test_command_center_static.py tests/test_workbench.py` — 118 passed, 17 subtests passed.
- `PYTHONPATH=src python scripts/release_smoke.py` — passed distribution build, metadata validation, fresh wheel/sdist installation, and authenticated Workbench smoke checks.
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
- Packet verification bounds receipt and manifest bytes, receipt and manifest records, individual
  artifact/source reads, aggregate reads, and any optional against-source traversal. Verification is
  confined to non-symlink regular files beneath non-symlink packet and source roots, validates
  SHA-256 shapes and coherent manifest coverage, rejects duplicate manifest paths, and rejects files
  that change across their descriptor-backed bounded read. Baseline validation uses the same
  canonical verifier. A boundary,
  unsafe path, or symlink returns verification failure rather than PASS; these operational limits
  do not create or upgrade canonical judgment authority.
- Policy and canonical-report JSON structure checks occur after full `json.loads` construction; their strict byte caps provide finite input bounds, not streaming parser or per-object instantiation guarantees.
