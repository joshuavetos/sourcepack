# SourcePack Workbench review flow

SourcePack Workbench is the primary local application for the ordinary SourcePack review loop.

1. Install SourcePack.
2. Initialize trusted state only when the current repository state should be trusted.
3. Launch `sourcepack ui .` from the repository.
4. Click **Run Review** in the browser.
5. Inspect PASS, WARN, or FAIL findings, canonical reason codes, stable finding IDs, affected-file context, repository evidence, and remediation.
6. Copy the deterministic correction prompt.
7. Let Codex or another external coding agent edit the repository outside Workbench.
8. Click **Run Review Again** to analyze the updated change.

Workbench review execution is local and bounded. The browser sends only a token-authenticated POST to `/api/workbench/v1/review`; it does not supply a repository path, shell command, or arbitrary arguments. The Python Workbench process uses the repository fixed when the server started, reuses `sourcepack.judgment.judge_repo_change()` (the same canonical internal judgment API used by `sourcepack diff .`), writes the normal `.sourcepack/reports/latest.json` report through canonical report writing, and returns structured operation JSON.

Workbench can create or update SourcePack analysis artifacts required by a review, including canonical reports. It cannot run arbitrary commands, edit code, invoke Codex, stage files, commit changes, install hooks, or silently initialize, refresh, repair, or trust a baseline.

Executor shutdown is nonblocking. Closing Workbench cancels queued reviews where possible and prevents new review submissions after server close, but Python cannot forcibly terminate an already running in-process canonical review; that active review may continue until it completes.

`POST /api/review` remains a compatibility alias for the bounded review operation. New browser code should use `POST /api/workbench/v1/review`.

## Manual browser verification: unsupported FastAPI in Flask repo

1. Prepare a Git repository with Flask declared in `requirements.txt`, a committed trusted SourcePack baseline, and no FastAPI dependency.
2. Modify the working tree to add or import FastAPI in an application file.
3. Launch `sourcepack ui .` from that repository.
4. In the browser, click **Run Review**.
5. Confirm the verdict is **FAIL** with reason code `unsupported_dependency`.
6. Inspect the affected-file context showing the FastAPI change.
7. Inspect repository evidence showing Flask support and missing FastAPI evidence.
8. Expand the correction panel and copy the deterministic correction prompt.
9. Let Codex or another external coding agent repair the repository outside Workbench.
10. Return to the same browser session and click **Run Review Again**.
11. Confirm the current verdict becomes **PASS** and the current-session transition message reports the previous FAIL and current PASS without claiming code correctness.
