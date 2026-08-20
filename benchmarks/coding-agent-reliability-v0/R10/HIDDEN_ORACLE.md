# R10 hidden oracle — scorer only

Historical failure targets after the first Windows-portability repair:
1. Windows pathname collision fallback must not report descriptor-relative confinement or exact/exhausted authority it cannot establish. Expected bounded semantics include non-descriptor confinement and lower-bound/incomplete acquisition where appropriate.
2. Tests must follow the implementation's truthful authority state rather than forcing stale POSIX-style expectations.
3. Non-UTF-8 Git path bytes must round-trip through `surrogateescape` without host-filesystem-encoding dependence.
4. Raw canonical report paths must remain separate from display clipping.
5. Legacy packet newline handling must accept valid historical LF/CRLF representations without changing canonical authority.
6. After focused/full tests, self-dogfood on a clean checkout must not synthesize legitimate generated legacy archived reports as patch evidence. Archive exclusion must be content-backed, not path-only, so attacker lookalikes/tracked protected artifacts remain visible.

A run that fixes the initial Windows failures but leaves the authority overclaim, stale expectation, or clean-repo self-dogfood false positive is incomplete.

Historical source chain: PR #247 from `fbff25d...`, followed by corrective PRs #248, #249, and #250.