# R03 runbook

1. Fresh-clone SourcePack and checkout the SHA in `PRE_TASK_COMMIT.txt`.
2. Confirm clean status; record environment/model/agent versions.
3. Do not copy benchmark metadata into the task checkout.
4. Supply only `TASK.md` plus scaffold A, B, or C.
5. Deny access to later commits/PRs and `HIDDEN_ORACLE.md`.
6. Record final code-change time; run/capture the configured full verification after that time.
7. Capture final diff/stat and completion report.
8. Score only after the run ends.