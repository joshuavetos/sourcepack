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
## Workbench browser validation

The canonical rendered-page gate is:

```bash
python -m pip install -e '.[browser-test]'
python -m playwright install --with-deps chromium
python -m pytest -q tests/test_workbench_browser.py
```

Playwright is an optional, development-only dependency because the repository had no
browser-capable test dependency or harness. It does not change SourcePack's runtime
dependencies and never downloads a browser during ordinary installation or Workbench
use. Browser installation is an explicit setup step. CI runs this suite as the distinct
**Workbench browser gate**, rather than making browser availability part of the offline
release-smoke command.

The suite starts the actual `WorkbenchServer` with `WorkbenchHandler`, a session token,
checked-in HTML and JavaScript, an ephemeral loopback port, and an isolated temporary
repository. It observes the authenticated
`GET /api/command-center/v1/snapshot` request and exercises the bounded review endpoint.
Narrow producer-boundary injection supplies deterministic, canonical Command Center
snapshots for states that cannot safely be manufactured as trusted repository state.
It does not replace the application with a fixture or reconstruct snapshot state in the
browser.

Covered states include PASS, WARN, FAIL, no report, missing baseline, stale baseline,
corrupt/unverifiable baseline, malformed report, unsupported report, snapshot-builder
failure, unavailable remediation, and an available correction prompt. Interaction
coverage includes token cleanup and session reload, bounded review, prompt copy,
technical-report expansion, explicit-surface navigation, structured-action handling,
and HTML-like untrusted report text.

The automated accessibility checks cover a single page-level heading, heading order,
document title and language, viewport metadata, unique IDs, accessible names for
actions, native disabled controls, keyboard reachability, visible focus, live status and
alert semantics, and keyboard operation of the technical report. These focused checks
help prevent obvious regressions; **they do not establish complete WCAG compliance or
replace assistive-technology and manual accessibility testing**.

Responsive DOM measurements run at 1440×1000 (desktop), 900×900 (tablet/narrow
laptop), 620×900 (the existing mobile breakpoint), and 360×800 (extra-small mobile).
They assert no page-level horizontal overflow or clipped panels, reachable navigation
and primary actions, wrapping prompt text, bounded technical-report overflow, and visible
degraded-state messaging. Screenshots are not used as the correctness oracle.

If Playwright reports that Chromium is missing, rerun
`python -m playwright install --with-deps chromium`. In a locked-down environment the
browser CDN and operating-system package repositories must be allow-listed; do not add
a runtime download fallback. Use `PLAYWRIGHT_BROWSERS_PATH` consistently during both
installation and test execution when CI stores browser binaries in a custom cache.
