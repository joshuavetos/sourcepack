# SourcePack architecture

## Problem

SourcePack is a local-first guardrail for AI-assisted repository edits. Its narrow promise is to catch unsupported AI repo assumptions before commit: invented files, undeclared dependencies, unsupported commands, protected trust-artifact edits, and similar evidence gaps.

## Trust model

SourcePack compares proposed or current changes against an integrity-checked accepted local baseline packet. Acceptance is the maintainer's trust decision; SHA-256 receipt verification checks the stored artifact bytes after acceptance. Hash agreement does not authenticate a creator, prove review, or independently establish trust. Prompt context is only guidance for an AI assistant and is never authoritative enforcement evidence.

## Baseline lifecycle

A trusted baseline is created intentionally with `sourcepack init . --auto` or `sourcepack baseline .` after the current repository state has been reviewed as trusted. Baseline state is stored under `.sourcepack/baseline/` with an active pointer and packet artifacts.

If a baseline is missing while changes exist, SourcePack fails closed with `baseline_missing`. If a baseline is stale, SourcePack warns with `baseline_stale`. If baseline artifacts are manually modified, missing, malformed, or hash-invalid, SourcePack fails with `baseline_corrupt`. Unknown baseline state is not silently trusted.

## Prompt context lifecycle

Prompt context packets help an AI answer with grounded local facts, but prompt context does not bless files, dependencies, commands, or capabilities. A prompt claim that a dependency or file exists is still checked against the trusted baseline and the changed diff.

## Diff judgment pipeline

The CLI obtains a Git diff or explicit patch text. Its parser recognizes and safety-checks the Git-style unified-diff subset SourcePack relies upon: file headers, new/delete and rename/copy metadata, hunk headers, and added/context/deleted lines. It is not a complete validator for every unified-diff grammar or semantic invariant. Unsupported or unsafe structure retains the existing fail-closed malformed-diff path where detected.

Diff paths normalize separators and `.` components. Internal parent segments are canonicalized (`directory/../file.py` becomes `file.py`), while a parent segment that would escape above the repository-relative root (`../file.py`) is marked unsafe and causes malformed handling. Thus the path check rejects escapes, not every literal `..` segment. The pipeline then evaluates file existence against the baseline inventory, detects dependency and command assumptions, applies PASS/WARN/FAIL policy, and writes local JSON, Markdown, and HTML reports.

## Reason-code lifecycle

Canonical reason codes live in `src/sourcepack/reason_codes.py`. Documentation should describe only codes that are emitted or intentionally reserved by the code vocabulary. JSON reports use lowercase snake_case reason-code strings.

## Policy modes

Local mode exits zero for PASS and WARN, and nonzero for FAIL. Strict mode and CI mode treat WARN as nonzero. CI mode also keeps machine-readable JSON output clean.

## Report generation

Report data is normalized before rendering. JSON is the machine contract, Markdown is terminal-friendly, and the local HTML report is the v1 human UI. Report-writing failures must not change the underlying judgment verdict.

## Known limitations

SourcePack does not prove semantic correctness, find vulnerabilities, scan secrets, or fully model every ecosystem. Unsupported or uncertain ecosystems should WARN rather than silently PASS as understood.

## Public-alpha engine boundary

The public-alpha core exposes `sourcepack.judgment.judge_repo_change(repo_path, *, staged=False, patch_text=None, policy_mode=PolicyMode.LOCAL) -> Judgment`. The CLI `sourcepack diff` now delegates repo judgment to that API, while keeping rendering, report persistence, and process exit behavior in the CLI layer.

The intended flow is:

1. CLI parses command-line arguments.
2. Git/diff acquisition resolves the repository root and obtains staged, unstaged, untracked, or supplied patch text.
3. Baseline loading validates `.sourcepack/baseline/` before trust is used.
4. Diff parsing extracts changed paths and added evidence.
5. The judgment engine creates report-ready findings from canonical reason codes.
6. Policy mode maps PASS/WARN/FAIL to local, strict, or CI exit behavior.
7. Report renderers write JSON, Markdown, and HTML without changing the verdict.

Prompt context is intentionally outside this enforcement evidence path.

## Operational producer bounds

Fleet report and decision-ledger discovery uses deterministic path ordering and producer-owned limits for directory entries, nesting depth, retained paths, individual artifact bytes, and aggregate bytes. Decision-ledger summaries report artifact-path discovery counts separately from consumed and retained event counts, with independent path and event limits and exhaustion metadata; bounded ledger reads stop after one valid-event probe beyond the retention limit rather than materializing the rest of the ledger. Its structured producer metadata distinguishes complete acquisition, boundary-limited incomplete acquisition, and acquisition failure; a retained prefix is never described as exhaustive. Symlinks are not followed. This bounds operational resource use, but does not prove repository correctness, security, runtime validity, or complete external fleet discovery, and fleet summaries cannot create or upgrade canonical PASS authority.

Forced packet-output cleanup is similarly bounded and reports complete, incomplete, or failed cleanup. It rejects a symlink output root and path escapes, never follows child symlinks, confines deletion to the canonical output root, and stops rather than broadening scope after traversal or metadata failure. An incomplete or failed cleanup prevents packet writing. Cleanup completeness is an operational property only and does not change trust state or review authority.

Packet verification reads receipt and manifest metadata under an 8 MiB per-file cap, accepts at
most 10,000 receipt hashes or manifest included-file records, hashes or compares no individual
artifact/source file larger than 64 MiB, and stops at 128 MiB of aggregate artifact and source
reads. Verification against a source tree additionally uses the bounded `SourceScanner` traversal.
Receipt and manifest paths must be safe relative paths resolving to non-symlink regular files under
non-symlink packet and source roots; absolute, drive-qualified, parent-traversing, escaping, or
symlinked paths return FAIL. Receipt and source digests must be lowercase SHA-256 values, the
receipt must cover `manifest.json` without recursively naming itself, and duplicate manifest paths
are rejected. Artifact and source bytes are read through one descriptor and verification rejects
identity, size, or modification-time changes across that bounded read. Baseline validation delegates
to this same canonical verifier. Malformed metadata, unavailable inputs, incomplete traversal, and any
verification boundary likewise return FAIL rather than an exhaustive or authoritative PASS. These
are packet-integrity and operational resource outcomes; they neither establish nor upgrade
canonical review authority.

The producer-hardening project is closed for the implemented canonical judgment and operational
surfaces described here. Closure means that incomplete producer evidence is kept non-authoritative,
trusted baseline creation rejects incomplete repository authority, emitted incomplete reports pass
their canonical contract path, and operational prefixes are not called exhaustive. It does not
claim that SourcePack is secure, correct, universally bounded, or complete for unsupported or
external evidence. Work outside those properties is maintenance or product/ecosystem work unless a
new regression demonstrates that one of these closure properties is false.

## Workbench and Command Center routing

The canonical `WorkbenchHandler` owns registration and dispatch for the authenticated
`GET /api/command-center/v1/snapshot` route alongside the established Workbench API
and static routes. Normal Workbench server construction therefore exposes the route
without package-initialization hooks or handler replacement. The Command Center
endpoint module owns snapshot construction and safe failure serialization, while the
Command Center contract module owns schema and cross-field validation.
The single snapshot is backend-bounded to 262,144 serialized UTF-8 bytes. Repository-controlled
producer objects are projected through deterministic list (64), mapping (64), depth (6), and
string (2,048; prompts 8,192) limits. Canonical totals and omitted counts accompany displayed
subsets. Three ordered reduction stages serialize after decisions, authority diagnostics, and
report diagnostics respectively, stopping at the first bounded result before revalidation; failure
to fit essential canonical state returns the safe error envelope. This boundary reduces transport
and browser cost but is not evidence of repository completeness, correctness, or security.
Package import does not mutate Workbench routing, and the browser consumes the single authenticated
snapshot without reconstructing it from diagnostic endpoints.

## Evidence graph and replay bundle

SourcePack reports include an additive evidence graph for explanation and reconstructability. Canonical evidence items are defined in `src/sourcepack/evidence.py` and carry stable IDs plus bounded local observations such as category, source type, path, optional line range, observed value, normalized value, reason-code support/contradiction links, uncertainty, and metadata.

The evidence graph is not a new authority. Local project evidence remains the only enforcement authority; prompt context and AI answers remain advisory. Evidence items make it easier to inspect why SourcePack emitted a verdict, but they do not prove code correctness, security, runtime success, external API truth, dependency safety, or user intent.

JSON reports also include an additive replay bundle assembled by `src/sourcepack/reports/json.py`. The bundle records SourcePack version, replay schema version, generation timestamp when available, command/policy mode when provided, verdict, exit code when provided, normalized reason codes, checked and not-checked categories, findings, warnings, blockers, uncertainties, evidence items, reason-code-to-evidence mappings, and safe metadata about baselines, prompt context, patches, and environment when present. Replay/audit data reconstructs SourcePack's decision path, not reality itself, and avoids secrets or full file contents beyond information SourcePack already intentionally reports.

JSON compatibility is additive: existing fields are not removed or renamed. The evidence graph fields (`evidence_items`, `reason_code_evidence`, and `replay_bundle`) are optional for older reports and mode-dependent for callers that build partial reports directly.

### Producer-side construction bounds

Command Center transport projection is not a producer limit. Before projection, its three
repository-controlled producer paths enforce independent limits:

* Canonical `latest.json` loading reads at most 2,097,153 bytes (the 2 MiB budget plus one
  deliberate overflow probe) and rejects the artifact as
  `incomplete`/`artifact_limit_exceeded` when the 2 MiB limit is exceeded. It does not parse or
  expose a prefix, so an omitted finding can never create PASS authority. Canonical report
  construction consumes at most 1,001 source findings, retains the first 1,000 in producer order,
  and adds a deterministic `report_construction_limit` warning. `authority.complete` is false and
  `authority.status` is `incomplete` even when a retained blocker preserves a `FAIL`; without a
  retained blocker the `WARN` verdict is explicitly non-final because unseen blockers may exist.
  The finding bounds separately record source consumed (including look-ahead), source retained
  (excluding the synthetic warning), canonical emitted (including it), source exhaustion, the
  retention limit, and an exact or lower-bound source total. Replay copies both authority and
  construction metadata; Command Center reports `state.report=incomplete` and degrades replay.
  The raw dashboard overview uses `report_status=incomplete`, while replay-evidence and report
  diagnostics use `status=incomplete` but keep bounded replay/evidence inspectable with the report's
  authority and construction metadata. The override dashboard likewise marks its policy-finding
  projection incomplete while keeping independently complete ledger counts inspectable.
  Remediation, blocker, warning, and evidence construction operate only on the bounded canonical set.
  Loading also rejects, before authority use, parsed reports exceeding 2,000 list items, 512 mapping
  entries, 65,536 Unicode code points per string, or 20 nested levels. Like policy shape checks,
  this structural rejection follows full `json.loads` materialization within the strict byte cap.
* Effective policy reads each of the only two resolution inputs—the repository
  `.sourcepack/policy.json` and optional caller-designated organization policy—through a 256 KiB
  plus-one-byte reader. Parsed inputs additionally allow at most 256 entries per collection,
  1,024 Unicode code points per string, and 12 nested levels. There is no include or inheritance
  traversal. Any boundary failure makes resolution `FAIL`; no prefix is merged and no successful
  policy authority is claimed. Source and limit category remain in the bounded error list.
* The persisted-decision dashboard streams `.sourcepack/decisions.jsonl` in ledger order. Ordinary
  reads are capped by the remaining 2 MiB budget; only a one-byte overflow probe is permitted. It
  accepts at most 512 nonblank records and 64 KiB per physical line. After record 512 it continues
  bounded line-by-line look-ahead: blank/whitespace lines do not count, a malformed nonblank line is
  malformed, record 513 establishes a lower bound, and exhaustion within the byte budget establishes
  an exact total. It never scans beyond the byte budget merely to prove trailing whitespace. It neither
  loads nor sorts the complete ledger. A complete scan reports an `exact` record count. A limit returns an
  `incomplete` error with a `lower_bound`, null total, and `limit_reached`. Decision completeness
  separately records nonblank records consumed, records retained/evaluated, source exhaustion, and
  the 512-record retention limit; the legacy additive `observed_count` equals consumed records. Thus
  later overrides and malformed trailing content are explicitly unknown and current applicability
  is not claimed. Malformed content reached within the boundary retains the established malformed
  envelope.

Exact boundaries are accepted; a deliberate single byte or source/ledger record look-ahead is used only to prove overflow.
Selection is producer/ledger order, duplicate handling is unchanged, JSON output remains
repeatable for unchanged inputs, and repository-controlled strings remain JSON/text data. These
read-only bounds do not create baselines, approve overrides, rewrite policy or reports, or otherwise
mutate trust state. They also do not establish repository completeness, correctness, security,
dependency safety, runtime validity, or user intent beyond the inspected evidence.
