# Optional hosted control plane (Milestone M)

SourcePack is local-only by default. The normal CLI, hooks, policy resolver,
baseline lifecycle, and Workbench neither load cloud configuration nor make
network requests. `sourcepack cloud` is the only command family that can use
the hosted HTTP client.

## Architecture evidence and dependencies

Repository inspection found a standard-library `http.server` Workbench and no
existing web framework, HTTP client, ORM, migration tool, or database
abstraction. The hosted entry point therefore uses a small standard-library
modular monolith: `sqlite3` with foreign keys and explicit schema migration,
and `http.server` transport. `argon2-cffi` is declared for the hosted
authentication implementation because the repository had no maintained
password-hashing dependency. Python's standard-library `urllib` is sufficient
for explicit CLI HTTP requests, so no HTTP-client dependency was added.

Run the server only with an explicit persistent database path:

```console
sourcepack-hosted --database /var/lib/sourcepack/cloud.sqlite
```

It binds to loopback by default. The entry point is intentionally separate from
Workbench, which remains a local loopback dashboard.

## Cloud CLI and credential handling

`sourcepack cloud status` reports `unconfigured` when no opt-in configuration
exists. `sourcepack cloud login` prompts for an API URL, identity, and hidden
password; credentials are sent in a JSON body, never query parameters. The
fallback credential file is outside the repository at
`$XDG_CONFIG_HOME/sourcepack/credentials.json` (or `~/.config/sourcepack`) and
is written mode `0600`. `sourcepack cloud logout` removes it. Commands never
print access or refresh tokens.

Explicit commands are `repo-register`, `repo-list`, `policy-pull`,
`policy-show`, and `upload-report`, `upload-evidence`, `upload-replay`, and
`upload-overrides`. Uploads require both upload enablement and an enabled
category; they display type, source path, byte size, and destination before
transmission. Retryable creates use a UUID `Idempotency-Key`.

## Policy cache boundary and hashes

`policy-pull` fetches an artifact-only policy response and writes its exact
accepted response bytes to an **unverified** location. It records the SHA-256
of those bytes as `source_sha256` and deterministic parsed JSON as
`canonical_sha256` in
`sourcepack.cloud.policy_cache.v1` metadata. It does **not** create or update a
verified policy cache: server-declared-hash, organization/repository binding,
revision consistency, and the existing resolver trust chain must all be
implemented before a downloaded policy can be trusted. Downloaded bytes are not
passed to the resolver, so they cannot influence effective policy.

## Non-claims and retention

Hosted transport and storage do not prove repository correctness, current
repository state, artifact authenticity or completeness, report correctness,
complete event history, absence of secrets, runtime safety, or user intent.
The service does not scan source code, clone repositories, execute commands,
or provide arbitrary file storage. Operators must back up their SQLite database;
this milestone has no retention administration and repository deactivation is
designed to preserve historical records rather than hard-delete them.
