# Versioned schema contracts (Milestone K)

`sourcepack schema` is an offline, read-only contract interface.  It neither
opens Git nor creates `.sourcepack` state.

## Public registry

| Canonical name | Artifact version | Alias | Owner | Structural/semantic scope |
| --- | --- | --- | --- | --- |
| `effective-policy.v1` | `sourcepack.effective_policy.v1` | `effective-policy` | `sourcepack.policy.resolve_effective_policy` | Closed resolved-policy envelope, policy rule values, IDs, package-manager and policy-rule vocabularies. |

The registry is deliberately small.  `traffic_report.v1`, findings, repository
policy, organization policy, override, decision-ledger events, execution-ledger
entries, evidence bundles, and replay bundles are **deferred**: inspection found
open or insufficiently versioned value domains, or one version with output
variants not yet proven as a strict standalone public contract.  In particular,
decision event types and override scopes are currently accepted as open runtime
strings.  They are not advertised as schemas.

## Commands

```console
sourcepack schema list [--json]
sourcepack schema show effective-policy.v1
sourcepack schema validate effective-policy.v1 policy.json [--json]
```

Names resolve only to their exact canonical name or the aliases displayed by
`list`; aliases never float to a future version. `show` emits sorted, two-space
indented JSON with exactly one trailing newline. The generated schema object is
the single source used by `show`, `validate`, and tests.

Validation uses `jsonschema` Draft 2020-12 and validates each generated schema
against that validator's metaschema. It performs no network access and has no
external `$ref` values. Input duplicate JSON keys are rejected. Diagnostics are
sorted, omit invalid values, and therefore do not echo secrets.

Exit classes are: `0` valid, `2` unknown schema, `3` unreadable/non-regular
input, `4` malformed JSON or UTF-8, `5` contract violation, and `6` validator
failure. `--json` writes only a deterministic JSON result to stdout.

## Inventory and non-claims

The effective-policy schema has universally required top-level fields emitted by
`resolve_effective_policy`; rule values are variant values (`boolean`, positive
integer, `pnpm`, nonempty path arrays, or null). It cannot establish policy-file
provenance, authorization, repository history, external references, execution
truth, correctness, security, dependency safety, or human intent.

## Compatibility

A published versioned schema is immutable. Required-field additions/removals,
renames, type or numeric-bound changes, enum removals/narrowing, closed-object
changes, conditional requirements, regex/ID changes, semantic-invariant changes,
`$id` changes, schema-name changes, or schema-version changes require a new
version. Optional-property and enum additions also require compatibility review:
they can break closed or exhaustive consumers. Aliases must remain one-to-one;
they may be added only as explicit immutable mappings. Defaults are not used.
Future versions must add a new generator branch, registry entry, independent
fixtures, runtime-vocabulary equality tests, and package smoke coverage without
altering existing bytes.

### Effective-policy rule contract

`rules` is the complete six-rule resolver record. Each rule's organization,
repository, and effective values use its own type: booleans for the two block
rules; positive integers for `max_changed_lines`; the runtime package-manager
enum for `package_manager`; and unique structurally constrained relative policy-pattern arrays for
`protected_paths` and `require_tests_for`. `effective_policy` is intentionally
a sparse map in current resolver output and may be empty or a non-empty subset
of those typed rules; absence means that no effective constraint was emitted. The
schema does not prove full runtime path normalization. Malformed organization-policy parse failures
may retain a bare SHA-256 byte digest, while successfully parsed policy content
uses the `sha256:` identity prefix; both are current emitted forms.

### Supported semantic validation

After structural validation, `effective-policy.v1` validates resolver-state
relationships owned by `resolve_effective_policy`: PASS has no errors,
conflicts, or rejected weakening attempts; FAIL has an error; conflicts and
rejected weakening attempts require their canonical error entries. It also
checks the emitted organization-source states (`not_supplied`,
`required_but_missing`, `loaded`, `invalid`, and trust-boundary violation) and
repository hash presence for absent and loaded repository policies. These
checks validate a standalone resolver result only; they do not prove that a
referenced policy file, source path, or hash is authentic or currently exists.

Semantic diagnostics use stable keywords including `resolution_state_mismatch`,
`organization_status_resolution_mismatch`, `organization_status_error_mismatch`,
`organization_mode_status_mismatch`, `conflict_error_mismatch`, and
`weakening_error_mismatch`; diagnostics retain generic messages and do not echo
artifact values.

Repository-policy semantic validation also distinguishes `absent`, `loaded`, and
`invalid`: absent has neither a hash nor a repository-policy configuration
error; loaded has a hash and no repository-policy configuration error; invalid
has FAIL, an emitted repository-policy configuration error, and the emitted
content or byte hash.
