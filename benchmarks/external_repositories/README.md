# External-repository validation corpus

This versioned, repository-local corpus models six external-style repository layouts: a Python project, an npm project, a pnpm workspace, conflicting dependency manifests, protected SourcePack policy, and an unsupported ecosystem manifest. The files are intentionally minimal original fixtures created for SourcePack and distributed under the repository's MIT license. They are not copies or snapshots of third-party repositories.

Run the canonical offline validation command from the repository root:

```console
python tools/external_repository_validation.py
```

Each case contains a complete trusted `repo_before/`, an untrusted `patch.diff`, and an explicit expectation document. The shared adversarial runner validates the expectation schema, creates a fresh Git repository and trusted baseline, calls the canonical `sourcepack.judgment.judge_repo_change` path, projects canonical finding identities, and compares normalized JSON bytes across three independent runs. No test or CI job clones, installs, resolves, or contacts these fixtures' named dependencies.

## What this proves

The suite proves that the current SourcePack judgment path can ingest these six representative, vendored repository structures and produce the declared verdict and finding projections deterministically in the tested environment. It also proves discovery and strict enforcement of required, forbidden, and explicitly allowed additional findings for every fixture.

## What this does not prove

These fixtures do not prove SourcePack is correct or secure. They do not execute application code, validate runtime behavior, establish that dependencies are safe or installable, or test network package resolution. They do not represent complete upstream projects and do not establish universal repository or ecosystem support. A passing suite only establishes the narrow structural and deterministic judgment behavior described above.
