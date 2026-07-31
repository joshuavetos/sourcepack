# AI Instructions for This SourcePack Packet

Use only the packet and `reality_map.json` as project evidence.
Do not invent files, commands, dependencies, frameworks, services, or capabilities.
If a required file is missing, say it is missing and ask for it rather than hallucinating it.
If a command is unsupported by detected evidence, say it is unsupported.
If a capability is not listed in `supported_capabilities`, treat it as unknown or unsupported.
If you introduce a new external dependency, modify the appropriate dependency manifest in the same patch and list it under Dependency Changes.
Only recommend commands listed under Supported Commands unless your patch also adds the project file that defines the new command.
Before referencing a file as existing, it must appear in Confirmed Files; label intentional creations as NEW FILE.
If required evidence is missing, say UNKNOWN and ask for the missing file/output instead of guessing.
Cite file paths when making project-specific claims.
Do not claim SourcePack proves semantic truth, security, production readiness, or external service behavior.

## Supported Commands

- `pytest`
- `python -m unittest`

## Supported Capabilities

- web server

## Confirmed Files

- `BUILD_WEEK.md`
- `CHANGELOG.md`
- `LICENSE`
- `PROJECT.md`
- `README.md`
- `SECURITY.md`
- `action.yml`
- `benchmarks/adversarial/README.md`
- `benchmarks/adversarial/contradictory-duplicate-manifests/case.md`
- `benchmarks/adversarial/contradictory-duplicate-manifests/expected.json`
- `benchmarks/adversarial/contradictory-duplicate-manifests/repo_before/app.py`
- `benchmarks/adversarial/contradictory-duplicate-manifests/repo_before/requirements-prod.txt`
- `benchmarks/adversarial/contradictory-duplicate-manifests/repo_before/requirements.txt`
- `benchmarks/adversarial/manifest-delete-recreate/case.md`
- `benchmarks/adversarial/manifest-delete-recreate/expected.json`
- `benchmarks/adversarial/manifest-delete-recreate/repo_before/app.py`
- `benchmarks/adversarial/manifest-delete-recreate/repo_before/requirements.txt`
- `benchmarks/adversarial/nested-manifest-scope-leakage/case.md`
- `benchmarks/adversarial/nested-manifest-scope-leakage/expected.json`
- `benchmarks/adversarial/nested-manifest-scope-leakage/repo_before/app.js`
- `benchmarks/adversarial/nested-manifest-scope-leakage/repo_before/package.json`
- `benchmarks/adversarial/nested-manifest-scope-leakage/repo_before/packages/worker/package.json`
- `benchmarks/adversarial/npm-same-patch-dependency/case.md`
- `benchmarks/adversarial/npm-same-patch-dependency/expected.json`
- `benchmarks/adversarial/npm-same-patch-dependency/repo_before/app.js`
- `benchmarks/adversarial/npm-same-patch-script/case.md`
- `benchmarks/adversarial/npm-same-patch-script/expected.json`
- `benchmarks/adversarial/npm-same-patch-script/repo_before/README.md`
- `benchmarks/adversarial/python-same-patch-dependency/case.md`
- `benchmarks/adversarial/python-same-patch-dependency/expected.json`
- `benchmarks/adversarial/python-same-patch-dependency/repo_before/app.py`
- `benchmarks/adversarial/repository-policy-weakened/case.md`
- `benchmarks/adversarial/repository-policy-weakened/expected.json`
- `benchmarks/adversarial/repository-policy-weakened/repo_before/app.py`
- `benchmarks/external_repositories/README.md`
- `benchmarks/external_repositories/multiple-dependency-manifests/expected.json`
- `benchmarks/external_repositories/multiple-dependency-manifests/repo_before/app.py`
- `benchmarks/external_repositories/multiple-dependency-manifests/repo_before/requirements-prod.txt`
- `benchmarks/external_repositories/multiple-dependency-manifests/repo_before/requirements.txt`
- `benchmarks/external_repositories/node-npm-project/expected.json`
- `benchmarks/external_repositories/node-npm-project/repo_before/index.js`
- `benchmarks/external_repositories/node-npm-project/repo_before/package.json`
- `benchmarks/external_repositories/pnpm-workspace/expected.json`
- `benchmarks/external_repositories/pnpm-workspace/repo_before/index.js`
- `benchmarks/external_repositories/pnpm-workspace/repo_before/package.json`
- `benchmarks/external_repositories/pnpm-workspace/repo_before/packages/web/index.js`
- `benchmarks/external_repositories/pnpm-workspace/repo_before/packages/web/package.json`
- `benchmarks/external_repositories/pnpm-workspace/repo_before/pnpm-workspace.yaml`
- `benchmarks/external_repositories/protected-policy-files/expected.json`
- `benchmarks/external_repositories/protected-policy-files/repo_before/app.py`
- `benchmarks/external_repositories/python-project/expected.json`
- `benchmarks/external_repositories/python-project/repo_before/app.py`
- `benchmarks/external_repositories/python-project/repo_before/requirements.txt`
- `benchmarks/external_repositories/unsupported-dependency-evidence/expected.json`
- `benchmarks/external_repositories/unsupported-dependency-evidence/repo_before/Cargo.toml`
- `benchmarks/external_repositories/unsupported-dependency-evidence/repo_before/src/main.rs`
- `corpus/repos.example.json`
- `docs/README.md`
- `docs/adversarial-hardening-plan.md`
- `docs/ai-agent-workflow.md`
- `docs/architecture.md`
- `docs/assets/README.md`
- `docs/baseline-lifecycle.md`
- `docs/ci.md`
- `docs/command-center-api.md`
- `docs/command-center-changelog.md`
- `docs/command-center-next.md`
- `docs/command-center-pr-scope.md`
- `docs/command-center-security.md`
- `docs/demo-evidence-checklist.md`
- `docs/examples/sourcepack-action.yml`
- `docs/github-action-quickstart.md`
- `docs/hosted-control-plane.md`
- `docs/limitations.md`
- `docs/problem-fit.md`
- `docs/public-alpha-readiness.md`
- `docs/real-corpus-validation.md`
- `docs/reason-codes.md`
- `docs/release-checklist.md`
- `docs/releases/v1.10.0a0-publish-checklist.md`
- `docs/releases/v1.10.0a0.md`
- `docs/schema-contracts.md`
- `docs/showcase/index.html`
- `docs/showcase/showcase-data.json`
- `docs/showcase/showcase.css`
- `docs/showcase/showcase.js`
- `docs/sourcepack-command-center.md`
- `docs/submission-assets.md`
- `docs/systemic-upgrade-status.md`
- `docs/threat-model.md`
- `docs/vscode-extension-plan.md`
- `docs/workbench-review-flow.md`
- `examples/demo_repo/README.md`
- `examples/demo_repo/pyproject.toml`
- `examples/demo_repo/sourcepack/cli.py`
- `examples/demo_repo/sourcepack/judge.py`
- `examples/demo_repo/sourcepack/verify.py`
- `examples/demo_repo/tests/test_verify.py`
- `examples/fake_ai_answer.md`
- `pyproject.toml`
- `pytest.ini`
- `schemas/command_center_snapshot.schema.json`
- `schemas/judgment_report.schema.json`
- `schemas/patch_judgment_report.schema.json`
- `schemas/reality_map.schema.json`
- `schemas/receipt.schema.json`
- `scripts/__init__.py`
- `scripts/release_smoke.py`
- `scripts/sourcepack_action.py`
- `src/sourcepack/__init__.py`
- `src/sourcepack/analysis.py`
- `src/sourcepack/assets/__init__.py`
- `src/sourcepack/assets/audit_template.md`
- `src/sourcepack/assets/packet_instructions.md`
- `src/sourcepack/baseline.py`
- `src/sourcepack/cli.py`
- `src/sourcepack/cloud.py`
- `src/sourcepack/command_center.py`
- `src/sourcepack/command_center_contract.py`
- `src/sourcepack/command_center_endpoint.py`
- `src/sourcepack/command_center_limits.py`
- `src/sourcepack/commands/__init__.py`
- `src/sourcepack/commands/bundle.py`
- `src/sourcepack/commands/fleet.py`
- `src/sourcepack/commands/report.py`
- `src/sourcepack/decision_ledger.py`
- `src/sourcepack/dependencies.py`
- `src/sourcepack/diff_parser.py`
- `src/sourcepack/ecosystems/__init__.py`
- `src/sourcepack/ecosystems/generic.py`
- `src/sourcepack/ecosystems/node.py`
- `src/sourcepack/ecosystems/python.py`
- `src/sourcepack/errors.py`
- `src/sourcepack/evidence.py`
- `src/sourcepack/evidence_bundle.py`
- `src/sourcepack/examples/demo_repo/README.md`
- `src/sourcepack/examples/demo_repo/pyproject.toml`
- `src/sourcepack/examples/demo_repo/sourcepack/cli.py`
- `src/sourcepack/examples/demo_repo/sourcepack/judge.py`
- `src/sourcepack/examples/demo_repo/sourcepack/verify.py`
- `src/sourcepack/examples/demo_repo/tests/test_verify.py`
- `src/sourcepack/examples/fake_ai_answer.md`
- `src/sourcepack/execution_ledger.py`
- `src/sourcepack/finding_identity.py`
- `src/sourcepack/fleet.py`
- `src/sourcepack/git.py`
- `src/sourcepack/hosted.py`
- `src/sourcepack/judgment.py`
- `src/sourcepack/overrides.py`
- `src/sourcepack/packet.py`
- `src/sourcepack/paths.py`
- `src/sourcepack/policy.py`
- `src/sourcepack/policy_authority.py`
- `src/sourcepack/reason_codes.py`
- `src/sourcepack/remediation.py`
- `src/sourcepack/replay.py`
- `src/sourcepack/reports/__init__.py`
- `src/sourcepack/reports/html.py`
- `src/sourcepack/reports/json.py`
- `src/sourcepack/reports/markdown.py`
- `src/sourcepack/reports/sarif.py`
- `src/sourcepack/repository_state.py`
- `src/sourcepack/schema_contracts.py`
- `src/sourcepack/schemas.py`
- `src/sourcepack/workbench.py`
- `src/sourcepack/workbench_static/command-center-aggregate.js`
- `src/sourcepack/workbench_static/index.html`
- `tests/__init__.py`
- `tests/simulation_helpers.py`
- `tests/test_adversarial_runner.py`
- `tests/test_baseline_integrity.py`
- `tests/test_baseline_lifecycle.py`
- `tests/test_baseline_lifecycle_cli.py`
- `tests/test_behavior_matrix.py`
- `tests/test_ci_docs_truth.py`
- `tests/test_cli_registry.py`
- `tests/test_clipboard.py`
- `tests/test_cloud_optional.py`
- `tests/test_command_center_activity_message_integrity.py`
- `tests/test_command_center_aggregate_client.py`
- `tests/test_command_center_api_contract.py`
- `tests/test_command_center_capability_integrity.py`
- `tests/test_command_center_changelog_contract.py`
- `tests/test_command_center_contract.py`
- `tests/test_command_center_endpoint.py`
- `tests/test_command_center_error_integrity.py`
- `tests/test_command_center_mission_control_contract.py`
- `tests/test_command_center_next_contract.py`
- `tests/test_command_center_payload_bounds.py`
- `tests/test_command_center_pr_scope.py`
- `tests/test_command_center_priority_actions.py`
- `tests/test_command_center_priority_integrity.py`
- `tests/test_command_center_score_integrity.py`
- `tests/test_command_center_security_contract.py`
- `tests/test_command_center_snapshot_v1.py`
- `tests/test_command_center_state.py`
- `tests/test_command_center_static.py`
- `tests/test_command_resolution_provenance.py`
- `tests/test_command_resolver.py`
- `tests/test_confidence_report.py`

## Required Answer Contract

- Files to modify
- New files
- Dependency changes
- Commands to run
- Assumptions/unknowns
- Patch or code

## Claim Boundaries

- SourcePack did not execute the application.
- SourcePack did not prove semantic correctness.
- SourcePack did not verify external services.
- SourcePack did not prove security.
- SourcePack did not prove production readiness.
- Absence of evidence means unknown, not impossible.
- Unsupported claims should be treated as ungrounded.
