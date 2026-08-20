# Scaffold conditions

Use the same task, pre-task commit, model family, tool access, environment, and stopping rule across conditions.

## A — Minimal

Fix or implement the requested task. Test your work. Report what changed and whether it is done.

## B — Current-good

Before editing, inspect the repository, relevant implementation, nearby tests, and current constraints. Trace affected callers and compatibility surfaces. Implement the smallest coherent solution. Run direct regressions, relevant focused tests, the repository's configured full verification, and inspect the final diff. Verification must run after the final edit. Do not suppress legitimate product findings to make the gate green. Report changes, exact checks and exit statuses, unresolved risks, and whether the completion claim is supported.

## C — Adversarial

Do everything in condition B. Before claiming completion, actively try to falsify the implementation. Probe authority/evidence boundaries, fail-open behavior, resource bounds, platform-specific behavior, concurrency/state sharing, compatibility, malformed/partial inputs, and the next operation a user would perform. Distinguish a product finding from a test failure; do not redesign around a legitimate finding merely to obtain PASS. Add focused regressions for any material failure discovered. Re-run affected checks and the complete final verification after the final edit. Claim completion only to the exact scope established by final evidence.

## Experimental note

B and C are intentionally bundled interventions in V0. A later ablation may split reconnaissance, diff review, adversarial categories, independent review, and verification depth.