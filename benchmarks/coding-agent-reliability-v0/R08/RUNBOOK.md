# R08 runbook

1. Fresh-clone SourcePack and checkout `PRE_TASK_COMMIT.txt`.
2. Confirm clean status; record host platform, Python, Git, model, and agent versions.
3. Supply only `TASK.md` and assigned scaffold. Do not expose later PRs/commits or hidden oracle.
4. Native Windows execution is preferred when available; otherwise record that the platform oracle was simulated rather than natively exercised.
5. Capture final code-change timestamp and run the complete final verification afterward.
6. Capture Git-focused tests, full gate output/exit code, final diff/stat, and completion report.
7. Score after the run.