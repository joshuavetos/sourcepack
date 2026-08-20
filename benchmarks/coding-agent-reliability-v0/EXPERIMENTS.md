# Benchmark V0 experiment record

## Question

On historical SourcePack tasks with known latent defects, does the adversarial scaffold reduce unsupported completion claims and historical-defect recurrence relative to minimal and current-good scaffolds, at an acceptable cost?

## Initial design

Five cases × three scaffold conditions = 15 first-pass runs. Expand to all ten historical cases only after the first five produce a usable signal and the scoring procedure survives review.

## Primary outcomes

1. historical defect avoided
2. unsupported completion claim
3. unsupported authority/evidence claim
4. new material defect

## Secondary outcomes

- correction pass required
- legitimate failure suppressed
- unnecessary architecture change
- final full gate completed after final edit
- duration/tokens/diff size

## Promising-scaffold rule

A scaffold is promising if it avoids more historical defects than A, produces fewer unsupported completion claims than A, does not increase material new defects, does not require disproportionate correction passes, and has acceptable time/token cost.

## Interpretation boundary

V0 may support a claim about these historical failure-rich SourcePack tasks. It does not establish general coding-agent reliability or general software-engineering capability.

## Run discipline

- Materialize only the exact pre-task commit.
- Inject `TASK.md` and the selected scaffold externally.
- Keep `HIDDEN_ORACLE.md` outside the agent checkout.
- Record model/agent versions and prompt hash.
- Capture timestamps for the final edit and final verification start.
- Capture command output and exit code.
- Freeze the scorecard before viewing condition results.
- Where practical, score without revealing the condition to the reviewer.
- A historical defect avoided by replacing it with an equivalent/worse defect is scored as a new material defect, not success.
