# R06 — Architecture duplication and bounded resource behavior

Audit the current SourcePack architecture for duplicated ownership or behavior that can diverge across CLI, baseline, packet/evidence, judgment/reporting, and Workbench/Command Center boundaries.

Trace definitions, imports, callers, tests, compatibility exports, and resource behavior before editing. Fix only confirmed defects or duplications where one existing owner should be canonical. Preserve public behavior and compatibility unless the existing behavior is itself the confirmed defect.

Pay attention to helpers that appear bounded: verify the implementation actually performs bounded I/O rather than reading an entire producer and slicing afterward.

Add direct regressions for every confirmed defect. Run relevant focused tests and the complete configured verification after the final edit. Inspect the final diff and report unresolved risks.