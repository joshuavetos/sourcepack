# Current behavior claim audit

This is the repository-grounded claim inventory for SourcePack 1.10.0a3. It
maps the product claims in `README.md`, the canonical reason-code vocabulary,
and the supported product surfaces to their implementation and executable
evidence. A mapping means that a test exercises the behavior; it does not turn
SourcePack's explicit non-claims into guarantees.

## Product-level claims and surfaces

| Claimed behavior | Implementation | Existing executable evidence |
| --- | --- | --- |
| Build an integrity-checked accepted baseline; reject dirty creation unless explicitly forced; never create trust in CI | `baseline.py`, `packet.py`, and the baseline/init paths in `cli.py` | `test_baseline_integrity.py`, `test_baseline_lifecycle.py`, `test_baseline_lifecycle_cli.py`, `test_prechange_policy_authority.py` |
| Acquire working-tree, staged, and committed-range changes without changing the selected repository root | `git.py`, `git_acquisition.py`, `repository_state.py` | `test_git.py`, `test_git_acquisition_selected_root.py`, `test_repository_state_separation.py`, `test_selected_root_boundary.py` |
| Parse Git-style text and binary changes, normalize POSIX/Windows separators and parent components, and fail closed on unsafe or malformed paths | `diff_parser.py`, `paths.py`, and `judgment.py` | `test_diff_parser.py`, `test_judgment_hardening.py`, `test_diff_exit_policy.py`, `test_ugly_repos.py` |
| Compare file, dependency, command, ecosystem, workflow, and protected-path assumptions with accepted repository evidence | `judgment.py`, `dependencies.py`, `commands/`, `ecosystems/`, and `repository_evidence.py` | `test_judgment.py`, `test_dependency_resolver.py`, `test_command_resolver.py`, `test_dependency_inventory_behavior.py`, `test_engine_inversion.py` |
| Treat dependency/command declarations introduced by the reviewed patch as proposed evidence, not prior authority | `dependencies.py`, `commands/`, `judgment.py`, and `repository_evidence.py` | `test_same_patch_evidence_provenance.py`, `test_command_resolution_provenance.py`, `test_judgment_provenance_handoff.py`, `test_prechange_policy_authority.py` |
| Resolve local and organization policy without allowing same-patch policy to authorize itself | `policy.py`, `policy_authority.py`, and `local_allow_trust.py` | `test_policy_integration.py`, `test_org_policy_resolution.py`, `test_local_policy.py`, `test_local_allow_trust.py`, `test_prechange_policy_authority.py` |
| Consume bounded execution evidence without claiming that it proves runtime success | `execution_ledger.py`, `evidence.py`, and `judgment.py` | `test_execution_ledger.py`, `test_evidence_model.py`, `test_judgment.py` |
| Render canonical JSON, Markdown, HTML, and SARIF reports with finding identity, provenance, replay, remediation, decisions, and evidence bundles | `reports/`, `finding_identity.py`, `replay.py`, `remediation.py`, `decision_ledger.py`, and `evidence_bundle.py` | `test_reports_json.py`, `test_report_provenance.py`, `test_replay_audit.py`, `test_remediation.py`, `test_decision_ledger.py`, `test_evidence_bundle.py` |
| Expose the same judgment engine through CLI and authenticated local Workbench review | `cli.py`, `workbench.py`, `command_center.py`, and `command_center_endpoint.py` | `test_engine_parity.py`, `test_workbench.py`, `test_workbench_remediation.py`, `test_command_center_endpoint.py`, `test_command_center_snapshot_v1.py` |
| Provide CI/GitHub Action behavior, report artifacts, summaries, and optional PR comments without changing the verdict when commenting is unavailable | `cli.py`, `action.yml`, and `scripts/sourcepack_action.py` | `test_github_action.py`, `test_ci_docs_truth.py`, `test_diff_exit_policy.py` |
| Provide schema validation, fleet summaries, replay/bundle commands, an optional hosted control plane, and the packaged demonstration | `schema_contracts.py`, `fleet.py`, `commands/`, `cloud.py`, `hosted.py`, and `cli.py` | `test_schema_contracts.py`, `test_fleet.py`, `test_cloud_optional.py`, `test_demo_smoke.py`, `test_release_smoke.py` |
| Bound repository, Git, report, ledger, packet, fleet, Workbench, and Command Center producers; incomplete evidence cannot become authoritative PASS | `repository_evidence.py`, `git_acquisition.py`, `reports/json.py`, `decision_ledger.py`, `evidence_bundle.py`, `fleet.py`, and `command_center_limits.py` | `test_producer_bounds.py`, `test_operational_producer_bounds.py`, `test_command_center_payload_bounds.py`, `test_final_boss_integration.py` |
| Detect a proposed symlink replacing a nonempty directory, while failing separately when the necessary current/prior evidence is incomplete | `worktree_collision.py` and `judgment.py` | `test_symlink_directory_collision.py`, `test_operational_producer_bounds.py` |

CLI registration and help text are additionally checked by
`test_cli_registry.py`; the README's executable commands, links, demo output,
and non-claims are checked by `test_readme_truth.py`. The cross-surface scenario
set is exercised by `test_behavior_matrix.py`, `test_simulation_harness.py`,
`test_gauntlet.py`, `test_adversarial_runner.py`, and
`test_real_corpus_validation.py`.

## Canonical finding behavior inventory

`reason_codes.py` is the vocabulary authority and `docs/reason-codes.md` is the
severity, meaning, and remediation contract. Every current code is covered by
the following implementation/test ownership map.

| Behavior codes | Primary implementation | Direct test families |
| --- | --- | --- |
| `baseline_missing`, `baseline_stale`, `baseline_corrupt`, `baseline_locked`, `baseline_failed`, `baseline_inventory_missing`, `dirty_worktree` | `baseline.py`, `packet.py`, `cli.py`, `judgment.py` | baseline integrity/lifecycle tests, `test_judgment.py`, `test_smoke.py` |
| `repo_not_directory`, `no_git_repo`, `no_diff`, `git_unavailable`, `git_timeout`, `git_diff_failed` | `git.py`, `git_acquisition.py`, `repository_state.py`, `cli.py` | Git, selected-root, diff-exit, producer-bound, and smoke tests |
| `missing_file`, `new_file`, `deleted_file`, `unsafe_path`, `path_escape`, `protected_artifact`, `git_path_modification`, `binary_diff`, `malformed_diff`, `unsupported_rename_copy` | `diff_parser.py`, `judgment.py`, `paths.py` | diff-parser, judgment-hardening, behavior-matrix, simulation, ugly-repository, and gauntlet tests |
| `unsupported_dependency`, `declared_dependency`, `dependency_manifest_uncertain`, `dependency_scope_review`, `unsupported_ecosystem`, `js_alias_uncertain` | `dependencies.py`, `ecosystems/`, `repository_evidence.py`, `judgment.py` | dependency resolver/inventory, scanner, same-patch provenance, simulation, and real-corpus tests |
| `unsupported_command`, `declared_command`, `command_manifest_missing`, `command_manifest_uncertain`, `command_check_inconclusive` | `commands/`, `repository_evidence.py`, `judgment.py` | command resolver/provenance, simulation, behavior-matrix, and judgment tests |
| `policy_config_warning`, `policy_dependency_addition`, `policy_protected_path`, `policy_secret_pattern`, `policy_resolution_failed`, `policy_package_manager`, `policy_test_required`, `policy_change_limit` | `policy.py`, `policy_authority.py`, `judgment.py` | policy validation/integration, organization-policy, pre-change-authority, and local-policy tests |
| `execution_evidence_missing`, `execution_evidence_present`, `execution_failed`, `execution_inconclusive` | `execution_ledger.py`, `evidence.py`, `judgment.py` | execution-ledger, evidence-model, report-provenance, and judgment tests |
| `workflow_change`, `gitignore_unwritable`, `prompt_context_failed`, `clipboard_unavailable`, `hook_install_failed`, `hygiene_hooks_deferred` | `judgment.py`, `paths.py`, `packet.py`, `cli.py` | judgment, clipboard, lifecycle CLI, GitHub Action, and smoke tests |
| `report_construction_limit` | `reports/json.py` and Command Center projection | producer-bound and Command Center integrity tests |
| `symlink_replaces_nonempty_directory`, `symlink_worktree_inspection_incomplete` | `worktree_collision.py`, `judgment.py`, `reports/json.py` | symlink-collision and operational-producer-bound tests |

The registry/document parity itself is enforced by `test_reason_code_docs.py`.
Schema/report contracts and presentation layers test the codes they accept, but
they are not independent evidence that each detector can emit every code.

## Adversarial audit result

The existing suite already exercises malformed and duplicate JSON, malformed
diffs and hunks, binary changes, path traversal and aliases, Unicode and unusual
repository names, same-patch manifests/policy/local allow records, missing and
corrupt evidence, bounded partial producers, concurrency in baseline/hosted/
Workbench paths, and POSIX/Windows-specific fallbacks.

One additional boundary probe found a confirmed discrepancy: the diff path
normalizer rejected `C:/absolute` and `C:\\absolute`, but accepted the
drive-relative Windows spelling `C:relative`. Python's canonical packet path
validator and the symlink target validator already classify any nonempty
Windows drive as unsafe. The diff parser now applies the same rule, with a
direct regression test.

## Remaining weak or intentionally bounded evidence

- Browser behavior is covered by static/endpoint tests and optional Playwright
  tests; environments without Playwright skip the real-browser layer.
- POSIX newline-containing paths and Windows symlink creation require host
  filesystem capabilities and are conditionally skipped when unavailable.
- External-repository validation uses the checked-in offline corpus; it is not
  evidence about every ecosystem or repository shape.
- Command/dependency parsing is deliberately bounded. Dynamic imports, dynamic
  build targets, aliases, nested package scope, and unsupported ecosystems can
  produce uncertainty rather than proof of support.
- Workbench and CLI share the judgment entry point and test parity of canonical
  outputs, but presentation-specific labels are not public judgment verdicts.
- Hosted checks and native-Windows CI remain external environment evidence;
  a local POSIX run cannot independently reproduce those platform claims.

These are limitations or evidence gaps, not confirmed implementation defects.
SourcePack continues not to claim code correctness, security, runtime success,
semantic validity, external API truth, dependency safety, or user intent.
