# R02 runbook

1. Fresh-clone SourcePack and checkout the SHA in `PRE_TASK_COMMIT.txt`.
2. Confirm `git status --short` is empty and record environment/model/agent versions.
3. Do not copy this benchmark directory into the task checkout.
4. Supply only `TASK.md` plus scaffold A, B, or C.
5. Allow normal repository tools/tests; deny access to later SourcePack commits/PRs and `HIDDEN_ORACLE.md`.
6. Record every code-changing timestamp. After the final code change, capture the configured full verification output and exit status.
7. Capture final diff/stat and the agent's completion report.
8. Score against `HIDDEN_ORACLE.md` only after the run ends.