# R02 — Evidence Bundles v1

Implement a compact deterministic local Evidence Bundle v1 for one saved SourcePack judgment report and its decision-ledger evidence chain.

Required behavior:
- create and verify bundles through `sourcepack bundle`
- match the target `report_created` event to the report
- reconstruct the parent chain
- include related `fail_detected` events and only verifiably related overrides
- include report, ledger, scanner-manifest, and referenced-artifact identities/hashes where available
- use a deterministic `spkb_...` bundle ID derived from canonical bundle material rather than creation time
- reject malformed, ambiguous, incomplete, or tampered evidence rather than reporting PASS
- keep the feature local/read-only with no signing, cloud, or network authority
- add focused tests, CLI coverage, docs, and run the repository's configured verification

Preserve existing SourcePack verdict/policy/baseline authority semantics. A legitimate SourcePack finding against the patch is evidence to understand; do not weaken unrelated enforcement merely to obtain PASS.