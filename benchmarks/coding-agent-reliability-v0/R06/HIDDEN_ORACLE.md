# R06 hidden oracle — scorer only

Historical failure targets:
1. `sourcepack.packet.is_probably_binary()` must not read the entire file and then slice. A bounded sample probe must request only the configured sample size from the file object.
2. Duplicate `BaselineLockError` ownership in CLI must not cause real baseline-lock contention to bypass canonical exception handling or be misclassified.
3. A fix that preserves returned values but keeps unbounded I/O fails this case.
4. A refactor that merely moves the duplicate implementation without establishing one canonical owner fails the ownership portion.

Direct regression expectations:
- instrument the file read and assert the requested read size is the configured sample size
- exercise real lock contention and assert canonical `baseline_locked` behavior

Historical source: PR #243 repaired both defects from pre-task commit `954e1ce...`.