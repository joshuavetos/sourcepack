# R10 — Native-Windows portability and recovery

Identify and repair the remaining SourcePack failures exposed by native Windows verification while preserving repository-evidence authority and cross-platform behavior.

Scope includes:
- Git/path decoding and non-UTF-8 path identity
- raw canonical report paths versus clipped display paths
- worktree/symlink collision inspection when descriptor-relative no-follow traversal is unavailable
- legacy packet newline/path compatibility
- Windows test portability without weakening behavior assertions

Requirements:
- do not claim POSIX-equivalent confinement where Windows only supports pathname/identity checks
- distinguish exact/exhausted authority from lower-bound or incomplete acquisition
- preserve raw identity separately from presentation clipping
- tests may skip only genuinely unavailable host capabilities, not failing behavior
- after repairs, run the affected Windows suites, full configured verification, self-dogfood, and inspect the next user-facing operation for false positives
- preserve existing verdict/reason/schema contracts unless a confirmed defect requires a narrow change