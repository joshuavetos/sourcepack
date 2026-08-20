# R08 hidden oracle — scorer only

Historical failure target:

The original hardened Git runner used `selectors.DefaultSelector` on anonymous subprocess stdout/stderr pipes. That works on POSIX but Windows `select()` cannot monitor those pipes, so the first Git invocation can raise `OSError`/WinError and SourcePack converts it to return code 126. Core commands then fail on Windows.

Pass requirements:
- do not use a selector mechanism that is unsupported for Windows anonymous subprocess pipes
- preserve timeout and combined-output bounds
- drain stdout/stderr concurrently without deadlock
- preserve bounded stdin behavior
- reap the child and close streams on failures
- include a regression that exercises the portable pipe-draining mechanism, not merely a mocked return value

Historical source: PR #237 introduced the selector-based hardening from pre-task commit `c8acf0b...`; PR #245 later replaced it with Windows-compatible threaded draining.