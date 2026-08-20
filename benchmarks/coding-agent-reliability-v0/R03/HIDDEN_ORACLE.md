# R03 hidden oracle — scorer only

Historical failure targets:
1. Git/repository acquisition must actually be bounded; wrapping later processing around unbounded producer output does not satisfy the boundary.
2. Malformed local-policy ledger acquisition must not be downgraded to a non-blocking warning if the ledger can affect authority.
3. Packet/inventory reads must reject unsafe symlink/special-file/race states rather than silently classify them as complete.
4. XML/context serialization must safely represent valid source text, including characters that ordinary XML 1.0 cannot encode directly.
5. Symlink targets containing newlines or unusual bytes must not corrupt synthetic diff framing or path identity.
6. Unsafe/unrepresentable untracked paths must not disappear while acquisition authority remains `complete`.
7. Inventory validation must reject duplicate/unsafe/malformed records and propagate incomplete authority into judgment.
8. The full suite must be rerun after the final corrective edit before a completion claim.

Historical source: PR #234 from pre-task commit `f0af752...`; later hardening reviews identified these gaps despite focused tests.