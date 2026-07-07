# Changelog

## Unreleased

- Tighten public-alpha onboarding around install, demo, baseline trust, and documented limitations.
- Refuse trusted baseline creation or refresh from dirty Git working trees unless `--force` is used intentionally.
- Keep public reason-code examples aligned with canonical reason-code documentation.

## 1.10.0a3

- Implement `comment-pr` as a real GitHub Action input instead of a reserved placeholder.
- Add PR comment rendering with a stable `sourcepack-action-comment:v1` marker so repeated pull-request runs update the SourcePack comment instead of posting duplicates.
- Add `sourcepack-pr-comment.md` and `sourcepack-pr-comment.txt` action artifacts for rendered comment body and comment create/update/skip/failure status.
- Keep PR commenting as presentation-only behavior: comment failures are recorded separately and do not replace SourcePack's PASS/WARN/FAIL judgment, reason codes, artifacts, SARIF behavior, or exit code.
- Document the permissions needed for PR commenting: `contents: read`, `pull-requests: write`, and `issues: write`.
- Update the action example to show `comment-pr: 'true'` with explicit token-permission notes and fork-permission caveats.
- Add tests for `comment-pr` wiring, comment body rendering, marker-based update behavior, missing-token/event skips, non-spamming behavior, and comment failure isolation.
