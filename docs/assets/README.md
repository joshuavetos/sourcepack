# SourcePack screenshot assets

Generate deterministic inputs first:

```bash
python tools/golden_demo.py --clean
```

Expected screenshot files:

- `docs/assets/sourcepack-terminal-red.png`
- `docs/assets/sourcepack-red-report.png`
- `docs/assets/sourcepack-warn-report.png`
- `docs/assets/sourcepack-pass-report.png`

## What to capture

1. `sourcepack-terminal-red.png`
   - Use `examples/golden/output/fail-unsupported-dependency/terminal.txt` as the terminal transcript source.
   - Show commit/check blocked, `unsupported_dependency`, fix guidance, and either the report path or `sourcepack report open`.

2. `sourcepack-red-report.png`
   - Open `examples/golden/output/fail-unsupported-dependency/repo/.sourcepack/reports/latest.html`.
   - Show the FAIL badge, reason-code row for `unsupported_dependency`, affected file `app.py`, and missing-evidence/suggested-fix cards.

3. `sourcepack-warn-report.png`
   - Open `examples/golden/output/warn-new-file/repo/.sourcepack/reports/latest.html`.
   - Show the WARN badge, reason-code row for `new_file`, and affected file `api.py`.

4. `sourcepack-pass-report.png`
   - Open `examples/golden/output/pass-clean/repo/.sourcepack/reports/latest.html`.
   - Show the PASS badge, no blockers, and commit allowed / next action.

The images should be real captures from the golden demo outputs, not hand-edited report mockups. If an illustrative mockup is ever used temporarily, label it as illustrative in the README or adjacent caption.
