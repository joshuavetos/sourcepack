# R10 runbook

1. Fresh-clone SourcePack and checkout `PRE_TASK_COMMIT.txt` on native Windows when possible.
2. Record Windows version, Python, Git, model, and agent versions; confirm clean status.
3. Supply only `TASK.md` and assigned scaffold; deny later history and hidden oracle.
4. Let the agent inspect the pre-task repository and run its normal tools.
5. Record final code-change timestamp. Run affected Windows tests and the full configured gate afterward.
6. On the final clean committed state, run SourcePack self-dogfood and capture output/exit status.
7. Capture final diff/stat and completion report.
8. Score only after the run ends, including later-operation/self-dogfood behavior.