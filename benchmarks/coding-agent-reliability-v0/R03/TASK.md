# R03 — Judgment evidence hardening

Harden packet/diff/judgment evidence handling against malformed, unsafe, unbounded, or ambiguous repository inputs while preserving current SourcePack authority semantics.

Scope includes packet artifact loading, packet context representation, inventory authority, quoted/unsafe Git diff paths, untracked-file diff production, symlink representation, and local policy-ledger acquisition.

Requirements:
- bound authoritative reads and producer output
- preserve exact path identity safely
- do not follow or expose unsafe symlinks/special files
- malformed/incomplete authoritative inputs must fail closed rather than degrade into a misleading success
- packet context must round-trip valid repository text/path data without creating malformed output
- inventory authority must distinguish complete from incomplete/malformed evidence
- add direct adversarial regressions and run the complete configured verification on the final code state
- preserve existing verdict/reason/policy/baseline contracts unless a confirmed defect requires a narrow change