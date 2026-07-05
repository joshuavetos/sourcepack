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

- `CHANGELOG.md`
- `LICENSE`
- `README.md`
- `SECURITY.md`
- `action.yml`
- `corpus/repos.example.json`
- `docs/ai-agent-workflow.md`
- `docs/architecture.md`
- `docs/assets/README.md`
- `docs/baseline-lifecycle.md`
- `docs/ci.md`
- `docs/examples/sourcepack-action.yml`
- `docs/github-action-quickstart.md`
- `docs/limitations.md`
- `docs/problem-fit.md`
- `docs/public-alpha-readiness.md`
- `docs/real-corpus-validation.md`
- `docs/reason-codes.md`
- `docs/release-checklist.md`
- `docs/releases/v1.10.0a0-publish-checklist.md`
- `docs/releases/v1.10.0a0.md`
- `docs/systemic-upgrade-status.md`
- `docs/threat-model.md`
- `docs/vscode-extension-plan.md`
- `examples/demo_repo/README.md`
- `examples/demo_repo/pyproject.toml`
- `examples/demo_repo/sourcepack/cli.py`
- `examples/demo_repo/sourcepack/judge.py`
- `examples/demo_repo/sourcepack/verify.py`
- `examples/demo_repo/tests/test_verify.py`
- `examples/fake_ai_answer.md`
- `examples/golden/output/fail-protected-artifact/repo/README.md`
- `examples/golden/output/fail-protected-artifact/repo/pyproject.toml`
- `examples/golden/output/fail-protected-artifact/repo/sourcepack.config.json`
- `examples/golden/output/fail-protected-artifact/summary.json`
- `examples/golden/output/fail-protected-artifact/terminal.txt`
- `examples/golden/output/fail-unsupported-command/repo/README.md`
- `examples/golden/output/fail-unsupported-command/repo/package.json`
- `examples/golden/output/fail-unsupported-command/repo/pyproject.toml`
- `examples/golden/output/fail-unsupported-command/repo/sourcepack.config.json`
- `examples/golden/output/fail-unsupported-command/summary.json`
- `examples/golden/output/fail-unsupported-command/terminal.txt`
- `examples/golden/output/fail-unsupported-dependency/repo/README.md`
- `examples/golden/output/fail-unsupported-dependency/repo/app.py`
- `examples/golden/output/fail-unsupported-dependency/repo/pyproject.toml`
- `examples/golden/output/fail-unsupported-dependency/repo/sourcepack.config.json`
- `examples/golden/output/fail-unsupported-dependency/summary.json`
- `examples/golden/output/fail-unsupported-dependency/terminal.txt`
- `examples/golden/output/pass-clean/repo/README.md`
- `examples/golden/output/pass-clean/repo/pyproject.toml`
- `examples/golden/output/pass-clean/repo/sourcepack.config.json`
- `examples/golden/output/pass-clean/summary.json`
- `examples/golden/output/pass-clean/terminal.txt`
- `examples/golden/output/trust-boundary/repo/README.md`
- `examples/golden/output/trust-boundary/repo/deploy.sh`
- `examples/golden/output/trust-boundary/repo/pyproject.toml`
- `examples/golden/output/trust-boundary/repo/sourcepack.config.json`
- `examples/golden/output/trust-boundary/summary.json`
- `examples/golden/output/trust-boundary/terminal.txt`
- `examples/golden/output/warn-new-file/repo/README.md`
- `examples/golden/output/warn-new-file/repo/api.py`
- `examples/golden/output/warn-new-file/repo/pyproject.toml`
- `examples/golden/output/warn-new-file/repo/sourcepack.config.json`
- `examples/golden/output/warn-new-file/summary.json`
- `examples/golden/output/warn-new-file/terminal.txt`
- `pyproject.toml`
- `pytest.ini`
- `schemas/judgment_report.schema.json`
- `schemas/patch_judgment_report.schema.json`
- `schemas/reality_map.schema.json`
- `schemas/receipt.schema.json`
- `scripts/__init__.py`
- `scripts/release_smoke.py`
- `scripts/sourcepack_action.py`
- `src/sourcepack/__init__.py`
- `src/sourcepack/assets/__init__.py`
- `src/sourcepack/assets/audit_template.md`
- `src/sourcepack/assets/packet_instructions.md`
- `src/sourcepack/baseline.py`
- `src/sourcepack/cli.py`
- `src/sourcepack/commands.py`
- `src/sourcepack/dependencies.py`
- `src/sourcepack/diff_parser.py`
- `src/sourcepack/ecosystems/__init__.py`
- `src/sourcepack/ecosystems/generic.py`
- `src/sourcepack/ecosystems/node.py`
- `src/sourcepack/ecosystems/python.py`
- `src/sourcepack/errors.py`
- `src/sourcepack/evidence.py`
- `src/sourcepack/examples/demo_repo/README.md`
- `src/sourcepack/examples/demo_repo/pyproject.toml`
- `src/sourcepack/examples/demo_repo/sourcepack/cli.py`
- `src/sourcepack/examples/demo_repo/sourcepack/judge.py`
- `src/sourcepack/examples/demo_repo/sourcepack/verify.py`
- `src/sourcepack/examples/demo_repo/tests/test_verify.py`
- `src/sourcepack/examples/fake_ai_answer.md`
- `src/sourcepack/execution_ledger.py`
- `src/sourcepack/git.py`
- `src/sourcepack/judgment.py`
- `src/sourcepack/packet.py`
- `src/sourcepack/paths.py`
- `src/sourcepack/policy.py`
- `src/sourcepack/reason_codes.py`
- `src/sourcepack/replay.py`
- `src/sourcepack/reports/__init__.py`
- `src/sourcepack/reports/html.py`
- `src/sourcepack/reports/json.py`
- `src/sourcepack/reports/markdown.py`
- `src/sourcepack/reports/sarif.py`
- `src/sourcepack/schemas.py`
- `src/sourcepack/workbench.py`
- `src/sourcepack/workbench_static/index.html`
- `tests/__init__.py`
- `tests/simulation_helpers.py`
- `tests/test_baseline_integrity.py`
- `tests/test_baseline_lifecycle.py`
- `tests/test_baseline_lifecycle_cli.py`
- `tests/test_behavior_matrix.py`
- `tests/test_ci_docs_truth.py`
- `tests/test_clipboard.py`
- `tests/test_command_resolver.py`
- `tests/test_confidence_report.py`
- `tests/test_core_rendering.py`
- `tests/test_dependency_inventory_behavior.py`
- `tests/test_dependency_resolver.py`
- `tests/test_diff_parser.py`
- `tests/test_engine_inversion.py`
- `tests/test_evidence_model.py`
- `tests/test_execution_ledger.py`
- `tests/test_final_boss_integration.py`
- `tests/test_gauntlet.py`
- `tests/test_git.py`
- `tests/test_github_action.py`
- `tests/test_golden_demo.py`
- `tests/test_judgment.py`
- `tests/test_judgment_hardening.py`
- `tests/test_local_policy.py`
- `tests/test_policy_integration.py`
- `tests/test_policy_validation.py`
- `tests/test_readme_truth.py`
- `tests/test_real_corpus_validation.py`
- `tests/test_reason_code_docs.py`
- `tests/test_release_docs.py`
- `tests/test_release_smoke.py`
- `tests/test_replay_audit.py`
- `tests/test_report_ui.py`
- `tests/test_reports_json.py`
- `tests/test_scanner_behavior.py`
- `tests/test_secret_redaction.py`
- `tests/test_simulation_harness.py`
- `tests/test_smoke.py`
- `tests/test_ugly_repos.py`
- `tests/test_workbench.py`
- `tools/behavior_matrix.py`
- `tools/golden_demo.py`
- `tools/real_corpus_validation.py`
- `tools/release_smoke.py`

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
