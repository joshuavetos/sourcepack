# Submission Asset Specification

This file defines the exact public-facing assets needed before recording the final SourcePack submission video.

## Required repository assets

### 1. Product front door

- `README.md` states the bounded product claim.
- `BUILD_WEEK.md` documents GPT-5.6 and Codex development evidence.
- `docs/assets/sourcepack-hero.png` provides the repository hero image.

### 2. Demo evidence

The canonical public demonstration is:

```bash
python -m pip install sourcepack
sourcepack demo
```

The decisive terminal excerpt is:

```text
RED LIGHT: commit blocked
unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared.

Verdict: FAIL
```

A final terminal capture must be made from the released package in a clean environment. The capture must not be fabricated from styled text. It must show the real command and real installed-package output at a readable font size.

### 3. GPT-5.6 workflow evidence

Capture the conversation sequence that led to [PR #159](https://github.com/joshuavetos/sourcepack/pull/159):

1. Joshua directs the README/product-framing change.
2. GPT-5.6 shapes the concrete repository change.
3. The resulting PR is created.
4. Joshua reviews and merges it.
5. The updated README is visible on `main`.

The capture should show enough conversation context to establish the contribution without exposing unrelated personal conversation.

### 4. Codex implementation evidence

Use one or two PRs with linked Codex tasks. Strong candidates:

- [PR #151](https://github.com/joshuavetos/sourcepack/pull/151), canonical policy findings and correction cycle
- [PR #154](https://github.com/joshuavetos/sourcepack/pull/154), local read-only Workbench
- [PR #160](https://github.com/joshuavetos/sourcepack/pull/160), atomic credential revocation and logout hardening

Each capture should visibly include the PR title, merged state, summary, tests, and Codex task link.

### 5. Historical product-origin evidence

Use [PR #129](https://github.com/joshuavetos/sourcepack/pull/129) only for the specific bounded point that a trusted baseline was refreshed from a dirty worktree and recorded `"dirty": true`.

Do not claim SourcePack would have proven the patch semantically incorrect. The relevant failure is trust-state contamination.

### 6. Workbench evidence

Capture the local Workbench only after running the released package against a prepared demonstration repository. Show:

- repository overview
- current verdict
- the `unsupported_dependency` finding
- repository evidence supporting the finding

Do not show empty panels or placeholder states in the final submission.

## Required final verification

Before recording:

1. Install the intended public package in a clean virtual environment.
2. Run `sourcepack demo` and save the complete output.
3. Confirm the README excerpt matches the actual release output.
4. Run the prepared repository demonstration.
5. Open the generated HTML report and Workbench.
6. Confirm every public link works while logged out.
7. Confirm Build Week PR links and Codex task links remain accessible.

## Asset truth rule

Repository screenshots and terminal captures must come from real repository pages and real command output. Designed diagrams may explain the workflow, but they must be labeled as diagrams rather than execution evidence.
