# Demo Evidence Checklist

This checklist is intentionally separate from the final video script. It defines what must be real, complete, and verified before recording begins.

## Product state

- [ ] Intended PyPI version is published.
- [ ] `python -m pip install sourcepack` succeeds in a clean virtual environment.
- [ ] `sourcepack demo` completes from the installed package.
- [ ] Demo output matches the README claim.
- [ ] `sourcepack doctor --strict` reports no release-blocking package or asset problem.
- [ ] Repository default branch is green.
- [ ] Public links work while logged out.

## Demonstration repository

- [ ] Repository begins from a clean, reviewed state.
- [ ] Proposed patch imports FastAPI without declaring it.
- [ ] The exact diff is visible before SourcePack runs.
- [ ] SourcePack reports `unsupported_dependency`.
- [ ] The report identifies the affected file and unsupported package.
- [ ] The generated HTML report opens.
- [ ] The Workbench opens against the same repository and report.
- [ ] No empty, broken, or irrelevant panels appear in the capture path.

## AI-development evidence

- [ ] GPT-5.6 conversation evidence for PR #159 is isolated from unrelated conversation.
- [ ] PR #159 is shown merged.
- [ ] At least one linked Codex task is shown with its resulting merged PR.
- [ ] At least one correction cycle is shown: requested behavior, implementation gap, correction instruction, corrected repository result.
- [ ] Build Week additions are distinguishable from work completed before the event.
- [ ] The `/feedback` Codex session identifier for the primary build thread is saved.

## Claim discipline

- [ ] The submission says SourcePack checks repository-supported facts.
- [ ] It does not claim semantic correctness.
- [ ] It does not claim security proof.
- [ ] It does not claim runtime proof unless bounded execution evidence is shown.
- [ ] It does not describe every AI defect as a SourcePack-detectable defect.
- [ ] PR #129 is described specifically as a trust-state contamination example.

## Capture truth

- [ ] Terminal evidence is recorded from a real command run.
- [ ] GitHub evidence is recorded from real PR pages.
- [ ] Designed workflow diagrams are clearly presented as diagrams.
- [ ] No recreated terminal image is presented as execution evidence.
- [ ] Text remains readable on a phone-sized playback window.
