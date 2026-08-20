# R08 — Cross-platform bounded Git subprocess handling

Harden SourcePack's Git subprocess execution so stdout/stderr/stdin handling is bounded, deterministic, leak-free, and portable across the repository's supported platforms.

Requirements:
- preserve the existing timeout/output-limit/return-code contracts
- drain stdout and stderr without deadlock while optionally supplying bounded stdin
- reap/close child resources on success, timeout, output-limit, missing Git, and unexpected I/O failures
- do not assume an OS primitive works for subprocess pipes on every supported platform
- keep acquisition-state semantics explicit and fail closed on producer incompleteness
- add tests that exercise the mechanism rather than only returned happy-path values
- run focused Git tests plus the complete configured verification after the final edit

Do not redesign unrelated policy/judgment behavior.