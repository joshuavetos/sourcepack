# Real-corpus validation

SourcePack's primary deterministic validation remains the behavior matrix. The real-corpus harness is an exposure and stress layer: it applies deterministic filesystem and git mutations to isolated working copies of repositories, then invokes SourcePack as the evaluator.

This does not change the product claim: SourcePack catches unsupported AI repo assumptions before commit by checking proposed changes against locally verifiable project evidence. It does not prove code correctness, security, semantic validity, or external API behavior.

## Corpus configuration

Example corpus entries live at `corpus/repos.example.json`. Each entry contains:

- `repo_id`
- `url`
- `ecosystem_tags`
- `expected_features`
- `notes`

Network access is optional. If a public repository cannot be cloned because the network is unavailable, the harness records `network_unavailable` and skips scenarios for that repository without counting it as a SourcePack product failure. Other clone errors are recorded as `clone_failed`.

## Cache and working directories

Persistent cloned or reused public repositories are stored under `.sourcepack_corpus_cache/`. The cache path is ignored by git.

Each repo/scenario pair runs in an isolated per-scenario working copy. Temporary directories are used only for these isolated working copies, not for persistent corpus repositories. Use `--keep-workdir` to preserve failed scenario working directories and include their paths in JSON output.

## Cleanup and baselines

Before baseline creation and before each scenario mutation, cleanup is exactly:

```sh
git reset --hard HEAD
git clean -fdx
```

The same cleanup runs after each scenario unless `--keep-workdir` preserves a failed workdir. If cleanup fails, the scenario is recorded as `repo_cleanup_failed` and SourcePack is not invoked.

For every scenario working copy the harness creates or refreshes the SourcePack baseline before mutation and verifies that a baseline exists. Baselines are never created after applying a mutation. Baseline failures are recorded as `baseline_failed` and skipped.

## SourcePack invocation

Default filesystem scenarios invoke SourcePack consistently as:

```sh
python -m sourcepack.cli diff . --json
```

Patch-text-only scenarios that cannot be represented safely as ordinary working-tree changes use SourcePack's programmatic judgment API and normalize results to the same JSON result shape.

## Mutation statuses

Every mutation returns a structured result with `status`, `applied`, `target_path`, `before_sha256`, `after_sha256`, `reason`, and `details`.

Supported statuses are:

- `applied`
- `skipped_incompatible_repo`
- `mutation_failed`
- `repo_cleanup_failed`
- `baseline_failed`

If a mutation is not applied, SourcePack is not invoked. If a file mutation leaves the file SHA-256 unchanged, it is recorded as `mutation_failed` and cannot masquerade as a product pass.

## Metrics and release interpretation

The harness tracks false REDs, missed REDs, noisy WARNs, crashes, timeouts, invalid JSON, wrong reason codes, mutation failures, skipped incompatible repos, cleanup failures, baseline failures, policy over-suppression, and trust violations.

Missed REDs and trust violations are release blockers. False REDs are tracked and triaged. Real repo results are stress evidence, not proof of correctness.

## Circuit breaker

A global circuit breaker aborts immediately after five consecutive scenario executions produce `crash` or `invalid_json`. The JSON summary records `circuit_breaker_triggered`, `circuit_breaker_reason`, `consecutive_failure_count`, and the last failed repo/scenario. A triggered circuit breaker exits nonzero.
