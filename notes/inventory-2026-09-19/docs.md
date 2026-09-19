> **Executor output, not a finding of record.** Produced 2026-09-19 by a read-only Sonnet executor. Re-checked by the lead: `START-HERE.md` and `CURRENT-STATE-AND-RESPONSIBILITY.md` flagged ENTRY as expected; the overlapping owner-decision lists were found independently. **Corrected by the lead:** the "26 of 39 orphans in `notes/production-host/`" is an artifact of the brief, which did not name that folder's own `README.md` as a hub — all 38 numbered notes are linked from it. Real orphans are the ~34 one-off notes directly under `notes/`. First-commit dates reflect the 2026-09-04 recovery snapshot, not authorship.

# Documentation inventory — many-gens-rl-vigen

Factual inventory only. No recommendations, no restructuring plan. Produced by reading each
in-scope file's first ~20 lines (`head -20`), `git log` on each path, `grep` for
supersede/archive/frozen language and for dated headings, and `grep` of the 8 hub files for each
filename. Bodies of `notes/ai-review-*` and `notes/*-external*.md` were **not read** per
instructions; they are reported as a group only.

## Coverage

- **Repository total: 508 `*.md` files** (tracked + untracked, excluding `.git`).
- **In scope and covered by this report: 241 files.**
  - 180 given full individual treatment (table below).
  - 27 external-review files grouped only (`notes/ai-review-*-external*.md` plus
    `notes/ai-answer-egl-28-external.md`, `notes/ai-help-26-external.md`,
    `notes/ai-recommendation-22-external.md`) — bodies not read.
  - 34 files covered only as per-folder counts: `docs/dated/` (20), `docs/refs/` (0 `.md`, 1 `.txt`
    out of scope by extension), `docs/library-survey/` (10), `docs/metrics-survey/` (4).
- **Skipped by the task's explicit exclusion rule** (`ext/`, `third_party/`, `RL-ViGen-upstream/`,
  `mutants/`, `runs/`, `results/`): **173 files** (`ext/` 124, `third_party/` 2,
  `RL-ViGen-upstream/` 30, `mutants/` 0, `runs/` 0, `results/` 17).
- **Outside the task's stated scope entirely** (never asked for, not skipped "by rule" so much as
  never in bounds): **94 files** — five `notes/` subdirectories other than `production-host/`
  (`notes/one-offs` 5, `notes/endgame` 6, `notes/model` 2, `notes/review-17-18-response` 5,
  `notes/review-19-response` 2 = 20), plus ten other top-level directories with their own `.md`
  files (`baselines` 14, `compute` 1, `datasphere` 2, `datasphere_gemini` 6, `research` 11,
  `rlgen` 3, `runnable` 33, `setup` 2, `.claude` 1, `.pytest_cache` 1 = 74).
- 241 + 173 + 94 = 508. (verified: `find . -name "*.md" | wc -l` = 508)

**Methodological caveat (unverified beyond direct observation, stated so it is not mistaken for a
finding about staleness):** this tree is `ccm-intro-native-recovery-workspace-2026-08-31`, a
reconstructed/recovered copy. A large fraction of files — nearly everything touched only once —
show **first commit = 2026-09-04** in this repository's `git log`, regardless of the date the
prose itself claims authorship (e.g. `instruction.md` says "Written 2026-08-10" but its own first
commit here is 2026-09-04). Read "date of first commit" in the table as *when this recovery tree
first carried the file*, not necessarily original authorship date. "Date of last commit" is a
direct, reliable measure of edit recency regardless of this.

All 8 named hub files exist (`CLAUDE.md`, `README.md`, `notes/START-HERE.md`,
`docs/PROJECT-INDEX.md`, `docs/SYSTEM.md`, `docs/STEP-ZERO.md`,
`notes/CURRENT-STATE-AND-RESPONSIBILITY.md`, `notes/OPERATOR-GUIDE.md`) — verified directly
(`ls -la`).

Style codes: **APPEND-LOG** (3+ dated headings/entries that accumulate), **STATE** (rewritten in
place, current-state framing), **REFERENCE** (stable spec/procedure/index/generated table),
**ONE-OFF** (single dated report/finding, not accreting).

## Table — repo root (6 files)

| Path | Lines | Last / First commit | Role (self-claim, ≤25w) | Style (evidence) | Entry | Superseded/archived/frozen self-declaration | Inbound (n; hubs) |
|---|---:|---|---|---|:-:|---|---|
| `CLAUDE.md` | 169 | 2026-09-17 / 2026-09-04 | Project-specific operating rules supplementing the workspace `CLAUDE.md`; production-host safety pointer | REFERENCE — fixed rules, no dated accretion | | No | 2; `docs/STEP-ZERO.md`, `notes/OPERATOR-GUIDE.md` |
| `HANDOFF.md` | 92 | 2026-09-04 / 2026-09-04 | "Handoff — EXPIRED, kept as evidence"; 2026-08-10 snapshot | ONE-OFF — single dated snapshot marked EXPIRED | | **Yes** — L3 "Superseded 2026-08-16." | 5; START-HERE, PROJECT-INDEX, SYSTEM, CURRENT-STATE, OPERATOR-GUIDE |
| `HANDOVER-FROM-CLAUDE-2026-09-04.md` | 180 | 2026-09-06 / 2026-09-06 | Standing context for the Codex session after the 2026-09-04 pre-production pass | ONE-OFF — single dated handover | | No | **0 → ORPHAN** |
| `instruction.md` | 430 | 2026-09-04 / 2026-09-04 | Map from prior artifacts to what's in the tree now, and why; "read this before changing anything" | REFERENCE — static historical map, 1 commit | **ENTRY** | No (mentions superseded *code*, not itself) | 2; README, PROJECT-INDEX |
| `README.md` | 169 | 2026-09-17 / 2026-09-04 | Code entry point; banner: approach changed 2026-08-17, "read this before the rest of the file" | STATE — banner rewritten in place | **ENTRY** | Partial — pre-08-17 body below the banner is called "superseded" (not the whole file) | 5; START-HERE, PROJECT-INDEX, STEP-ZERO, CURRENT-STATE, OPERATOR-GUIDE |
| `RECOVERY-HANDOFF.md` | 148 | 2026-09-06 / 2026-09-04 | Handoff for the isolated recovery *candidate* only, distinct from the project tree | STATE — "State, updated 2026-09-04 — previous version was false" | scoped | No | 1; START-HERE |

## Table — `docs/` root level (41 files; `dated/`, `refs/`, `library-survey/`, `metrics-survey/` summarized separately below)

| Path | Lines | Last / First commit | Role (self-claim, ≤25w) | Style (evidence) | Entry | Superseded/archived/frozen self-declaration | Inbound (n; hubs) |
|---|---:|---|---|---|:-:|---|---|
| `docs/ASSURANCE.md` | 116 | 2026-09-04 / 2026-09-04 | Classifies what's believed and by what mechanism, tagged `[CURRENT-STATE]` | STATE — tagged `[CURRENT-STATE]` in its own title | | No | 3; PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/AUDIT-2026-08-17.md` | 369 | 2026-09-04 / 2026-09-04 | Canonical provenance audit, 17 Aug 2026, twelve baselines six clones; wins over its own HTML | ONE-OFF — dated audit | | No | 1; PROJECT-INDEX |
| `docs/COMPARABILITY_CONTRACT.md` | 792 | 2026-09-08 / 2026-09-04 | The comparability contract; §1–§10 flagged obsolete by its own banner | APPEND-LOG — 3 dated addenda (08-16, 09-03, 09-08) | | Partial — L13 "⚠ §1–§10 DESCRIBE THE RETIRED `rlgen/` PORT — read this before relying on them" | 5; CLAUDE, PROJECT-INDEX, SYSTEM, STEP-ZERO, OPERATOR-GUIDE |
| `docs/compute.md` | 236 | 2026-09-04 / 2026-09-04 | What runs locally on the M2 Pro vs needs CUDA/remote, measured throughput | REFERENCE — measured facts, edited in place | | Partial — L92 "Superseded — the V100's own Python no longer matters" (one paragraph) | 4; README, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/CONSTRUCTION.md` | 7884 | 2026-09-08 / 2026-09-04 | Construction register: every difference needing a decision, C-numbered entries | **APPEND-LOG — 98 numbered `C##` entries accumulate** | | No | 5; CLAUDE, START-HERE, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/DECISION_LOG.md` | 111 | 2026-09-04 / 2026-09-04 | Decision log for the superseded `rlgen`-port era, marked HISTORICAL | APPEND-LOG — 3 dated headings (08-13, 08-13, 08-14), now closed | | **Yes** — L3 "HISTORICAL. These entries are from the superseded `rlgen` port era" | 3; PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/DISCIPLINE_IMPOSED.md` | 362 | 2026-09-04 / 2026-09-04 | Dense recap of discipline rules imposed 2026-08-14, for reapplication not readability | ONE-OFF — session recap | | **Yes** — L3 "Superseded as the authoritative document, 2026-08-14, by .../porting-directive.md" | 2; PROJECT-INDEX, STEP-ZERO |
| `docs/dz-report-2026-08-24.md` | 498 | 2026-09-04 / 2026-09-04 | RU status report to supervisor DZ, snapshot dated 25.08.2026, "not a living document" | ONE-OFF | | Self-describes as a point-in-time snapshot, not the keyword | 1; PROJECT-INDEX |
| `docs/dz-report-criteria.md` | 64 | 2026-09-04 / 2026-09-04 | Checklist for grading the DZ report, written before the report | REFERENCE — checklist | | No | 1; PROJECT-INDEX |
| `docs/dz-report-ru-spoken.md` | 182 | 2026-09-04 / 2026-09-04 | Spoken-word version of the DZ report, meant to be read aloud | ONE-OFF | | No | 1; PROJECT-INDEX |
| `docs/dz-report-ru.md` | 213 | 2026-09-04 / 2026-09-04 | RU written report to supervisor DZ dated 2026-08-11 | ONE-OFF | | No | 1; PROJECT-INDEX |
| `docs/EVAL-DECOMPOSITION.md` | 118 | 2026-09-07 / 2026-09-04 | Derives every term the reported number depends on, from its definition | REFERENCE | | No | 1; PROJECT-INDEX |
| `docs/EVAL-PROTOCOL.md` | 560 | 2026-09-07 / 2026-09-04 | Proposed eval protocol for P-C76/R3; "Status: PROPOSED, nothing here is settled" | STATE — bold items owner-decided, updated in place | | No | 4; START-HERE, PROJECT-INDEX, CURRENT-STATE, OPERATOR-GUIDE |
| `docs/EVALUATOR-DELTA.md` | 120 | 2026-09-06 / 2026-09-04 | Delta ledger, shared evaluator vs each baseline's own; "incomplete and honest about it" | REFERENCE — ledger, explicit incomplete | | No | 1; PROJECT-INDEX |
| `docs/FAITHFULNESS.md` | 1498 | 2026-09-16 / 2026-09-04 | Per-algorithm fidelity table vs canonical sources; generated block, "do not hand-edit" | REFERENCE — generated by script, `--check` enforced | | Partial (self-admitted stale) — L81 "[SUPERSEDED 2026-09-08 ...] This banner is itself two revisions stale" | 5; START-HERE, PROJECT-INDEX, SYSTEM, STEP-ZERO, CURRENT-STATE |
| `docs/FINAL-VERIFICATION-CHECKLIST.md` | 293 | 2026-09-04 / 2026-09-04 | Living checklist for the 2026-08-14 push to a finished, parity-verified state | STATE — rows move to DONE with evidence | | No | 1; PROJECT-INDEX |
| `docs/independent-audit-2026-08-17.md` | 240 | 2026-09-04 / 2026-09-04 | Blind subagent audit re-checking finding categories against the current tree | ONE-OFF | | No | 1; PROJECT-INDEX |
| `docs/INTEGRATION-DELTA.md` | 1023 | 2026-09-07 / 2026-09-04 | Everything in the code that is ours, not the authors'; self-describes "a log, appended to, never rewritten" | **APPEND-LOG — 21 dated headings, 08-16→09-05** | | No | 3; PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/INTERIM-REPORT-2026-08-16.md` | 278 | 2026-09-04 / 2026-09-04 | First-person interim report 2026-08-16 on reward-normalizer, CTRL, Stage 3, infra | ONE-OFF | | No | 1; PROJECT-INDEX |
| `docs/MILESTONES.md` | 61 | 2026-09-04 / 2026-09-04 | Which commits mattered; narrow inclusion rule so navigation stays findable | REFERENCE — curated dated table | | No | 1; PROJECT-INDEX |
| `docs/ORIGINAL_LOCATIONS.md` | 348 | 2026-09-07 / 2026-09-04 | Lookup table of where each baseline's original-author code sits, fidelity yes/no | REFERENCE | | No | 4; START-HERE, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/PART2-METRIC-INVENTORY.md` | 630 | 2026-09-08 / 2026-09-04 | What each baseline actually emits and against what; "an inventory, not a plan" | APPEND-LOG — 3 dated status headings (08-17/08-19/09-04) | | No | 6; CLAUDE, README, PROJECT-INDEX, SYSTEM, STEP-ZERO, OPERATOR-GUIDE |
| `docs/POINTS-LIST.md` | 51 | 2026-09-06 / 2026-09-04 | Recovered points list (I/J/K) that only existed in conversation, reconstructed from transcript | ONE-OFF | | No | 1; PROJECT-INDEX |
| `docs/PREMISES.md` | 375 | 2026-09-07 / 2026-09-04 | Minimal premises before a number means anything; companion to FAITHFULNESS.md | STATE — rungs corrected in place | | No | 4; CLAUDE, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/PROJECT-INDEX.md` | 127 | 2026-09-16 / 2026-09-04 | Index of documents that outlive a session; "code's own entry point is `../README.md`" | REFERENCE — index | **ENTRY** (hub) | No | 4; CLAUDE, SYSTEM, STEP-ZERO, OPERATOR-GUIDE |
| `docs/RECORDING-A-RESOLVED-FINDING.md` | 75 | 2026-09-10 / 2026-09-10 | How to record a finding so it stays true, from a day three findings were wrong | REFERENCE — procedure | | No | 1; PROJECT-INDEX |
| `docs/REGISTER.md` | 318 | 2026-09-09 / 2026-09-04 | Findings register: found→recorded→decided, dated rows, per `porting-directive.md` §5 | **APPEND-LOG — 190 dated rows accumulate** | | No | 4; START-HERE, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/RESEARCH-FRAME.md` | 328 | 2026-09-08 / 2026-09-04 | What the design can support given what's manipulated; "a reading", not authoritative | APPEND-LOG — 3 dated findings headings (08-18/08-19/08-26) | | No | 5; CLAUDE, PROJECT-INDEX, SYSTEM, STEP-ZERO, OPERATOR-GUIDE |
| `docs/RESOLVED-REGISTER.md` | 544 | 2026-09-16 / 2026-09-10 | One row per settled question; generated from `docs/resolved-register.json` | REFERENCE — generated, "do not edit by hand" | | No | 2; START-HERE, PROJECT-INDEX |
| `docs/REVIEW.md` | 430 | 2026-09-04 / 2026-09-04 | Code review vs `TASK.md` §3 under `RIGOR.md`, dated 2026-08-09 snapshot at a specific git HEAD | ONE-OFF | | No (TASK.md calls it a dated snapshot; it doesn't say so itself) | 2; README, PROJECT-INDEX |
| `docs/RIGOR.md` | 536 | 2026-09-04 / 2026-09-04 | Working standard for rigor/observability/verification this project holds itself to | REFERENCE — standard | | No | 4; README, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/RUN-THIS-PROJECT.md` | 246 | 2026-09-18 / 2026-09-07 | Clone-to-submitted-run in six steps; "replaces knowing which of ~30 documents in `notes/` to read" | REFERENCE — procedure | **ENTRY** | No | 3; README, PROJECT-INDEX, OPERATOR-GUIDE |
| `docs/RUNNABLE-ORIGINALS.md` | 521 | 2026-09-16 / 2026-09-04 | Part 1: the originals running, change-count as deliverable; "supersedes the port-and-harness approach" | STATE — ledger via `scripts/deviations.py` | | No (supersedes *another* doc, not itself) | 4; README, PROJECT-INDEX, SYSTEM, STEP-ZERO |
| `docs/STAGES.md` | 301 | 2026-09-04 / 2026-09-04 | Virtual view projecting the project onto stages; explicitly not an instruction or error containment | REFERENCE | | Partial — L87 "Superseded 2026-08-25 — read the paragraph below as history" (one section) | 2; CLAUDE, PROJECT-INDEX |
| `docs/STATE-2026-08-16.md` | 136 | 2026-09-04 / 2026-09-04 | What is original vs written, the whole scene measured 2026-08-16 | ONE-OFF — kept as history | | **Yes** — L3 "SCOPE, added 2026-08-17: this measures `rlgen/`, which is the SUPERSEDED port... It is not the state of the project." | 1; PROJECT-INDEX |
| `docs/STATUS-AGAINST-THE-GOAL.md` | 224 | 2026-09-04 / 2026-09-04 | Top-down check of how much of the actual task is done, written 2026-08-10 | ONE-OFF | | No | 2; PROJECT-INDEX, OPERATOR-GUIDE |
| `docs/STEP-ZERO.md` | 1632 | 2026-09-09 / 2026-09-04 | Practice before any code and how claims must survive; carries a live "Handoff" block at the top | STATE (hub) — handoff block rewritten per session | **ENTRY** (hub) | No | 3; CLAUDE, PROJECT-INDEX, SYSTEM |
| `docs/SUPERVISOR-BRIEFING.md` | 357 | 2026-09-04 / 2026-09-04 | Status briefing for the supervisor dated 2026-08-10, decisions-first framing | ONE-OFF | | Partial — L127 "(Partly superseded — see Appendix A1/A3...)" (one claim) | 1; PROJECT-INDEX |
| `docs/SYSTEM.md` | 393 | 2026-09-06 / 2026-09-04 | The document system itself: durable/working-state split, four doc shapes, own weaknesses | REFERENCE (hub) | | No | 3; CLAUDE, PROJECT-INDEX, STEP-ZERO |
| `docs/TASK.md` | 517 | 2026-09-04 / 2026-09-04 | Task of record: the contract, not a plan; criteria checked mechanically | STATE — amended in place ("Amended 2026-08-19") | | No | 6; CLAUDE, README, PROJECT-INDEX, SYSTEM, STEP-ZERO, OPERATOR-GUIDE |
| `docs/VALIDATION.md` | 495 | 2026-09-04 / 2026-09-04 | Validation record: what was run 2026-08-10, what it returned, what it does not establish | APPEND-LOG — 5 dated headings | | Partial — L12 "Superseding every number further down, which is kept because the progression is the argument" | 3; README, PROJECT-INDEX, SYSTEM |

## Table — `notes/` top level, part 1 of 2 (A–H, 47 files; external-review group excluded, see below)

| Path | Lines | Last / First commit | Role (self-claim, ≤25w) | Style (evidence) | Entry | Superseded/archived/frozen self-declaration | Inbound (n; hubs) |
|---|---:|---|---|---|:-:|---|---|
| `notes/ACCEPTANCE-R7.md` | 53 | 2026-09-06 / 2026-09-06 | R7 acceptance test for a clean-machine newcomer; "a skeleton, not a finished script" | ONE-OFF | | No | 1; START-HERE |
| `notes/ACCOUNTABILITY.md` | 412 | 2026-09-19 / 2026-09-17 | Open taskset and how each item was actually closed, asked for 2026-09-17 | STATE — rewritten per item, 1 dated self-audit heading | | No | 2; CLAUDE, CURRENT-STATE |
| `notes/ai-help-16.md` | 52 | 2026-09-07 / 2026-09-07 | External AI answer recommending `frame_stack=3` for IDAAC/PPG on Door | ONE-OFF — external answer | | No | **0 → ORPHAN** |
| `notes/ask-claude.md` | 1033 | 2026-09-07 / 2026-09-06 | Single-writer mailbox: only Codex appends questions here | **APPEND-LOG — 39 dated `Q##` headings, append-only** | | No | 1; START-HERE |
| `notes/BATTERY-LAUNCH-CONDITIONS.md` | 144 | 2026-09-10 / 2026-09-10 | What the production battery is/costs, four shaping constraints, pre-flight 2026-09-10 | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/both-endpoint-grids-against-the-random-floor.md` | 97 | 2026-09-10 / 2026-09-10 | Corrects an earlier "unanswerable" claim using a random-action floor | ONE-OFF — correction | | No | 1; START-HERE |
| `notes/CAMPAIGN-REPORT-2026-09-18.md` | 127 | 2026-09-18 / 2026-09-18 | Campaign report: what ran/failed, 07:40 MSK 2026-09-18 | ONE-OFF | | No | 3; START-HERE, CURRENT-STATE, OPERATOR-GUIDE |
| `notes/CHANGE-PLAN-2026-09-08.md` | 678 | 2026-09-08 / 2026-09-08 | Change plan; "Status: OPEN and INCOMPLETE", three agents sweeping axes | STATE — open/incomplete tracker | | No | **0 → ORPHAN** |
| `notes/CLAIMS-LEDGER.md` | 234 | 2026-09-08 / 2026-09-06 | What each result row is entitled to claim; Tier 1/2 distinction | APPEND-LOG — 4 dated Added/Correction/Upgraded headings | | No | 1; START-HERE |
| `notes/claude-answers.md` | 3907 | 2026-09-10 / 2026-09-06 | Single-writer answers to `ask-claude.md`, keyed by question id | **APPEND-LOG — 36 dated `A##` headings, append-only** | | No | 1; START-HERE |
| `notes/CODEX-WHOLE-PROJECT-AUDIT-2026-09-05.md` | 279 | 2026-09-06 / 2026-09-06 | Live pre-production audit record by Codex, 2026-09-05; "not a launch approval" | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/COLLABORATION.md` | 41 | 2026-09-06 / 2026-09-06 | Rules for working alongside another agent: mailbox, default-and-announce | REFERENCE — procedure | | No | 1; START-HERE |
| `notes/CONSOLIDATION-DESIGN-2026-09-09.md` | 370 | 2026-09-09 / 2026-09-09 | A design (not execution) for consolidating repo understanding, written at ~99% context | ONE-OFF — "nothing here executed" | | No | 1; START-HERE |
| `notes/CORRECTIONS.md` | 2322 | 2026-09-08 / 2026-09-06 | Claims made in these notes that were wrong, corrected inline at source | **APPEND-LOG — 43-row numbered retraction ledger** | | No | 1; START-HERE |
| `notes/ctrl-has-never-run-on-this-host-and-why.md` | 233 | 2026-09-11 / 2026-09-10 | `ctrl` fails on the host twice, for two reasons; found while attesting evaluator families | ONE-OFF — same-day self-correction (all headings dated 09-10) | | Partial — L138 "SUPERSEDED — this section's conclusion is WRONG" (one section) | **0 → ORPHAN** |
| `notes/ctrl-v170-operational-triage.md` | 172 | 2026-09-07 / 2026-09-07 | Read-only investigation of the v170 evaluator-validator wave; "no job was launched" | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/CURRENT-STATE-AND-RESPONSIBILITY.md` | 297 | 2026-09-19 / 2026-09-06 | "What is true right now"; kept current not appended to | STATE — explicit rewrite-in-place | **ENTRY** (hub) | No (describes replacing its *own* prior version, but the live file isn't marked superseded) | 2; START-HERE, OPERATOR-GUIDE |
| `notes/DECISION-SHEET.md` | 3330 | 2026-09-09 / 2026-09-06 | Everything awaiting the owner in one pass, answer-by-exception with researched defaults | **APPEND-LOG — 60 dated Revision/`A##` headings** | | No | 1; START-HERE |
| `notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` | 262 | 2026-09-09 / 2026-09-07 | Nine OWNER gates as decisions, each with symptom/test/cost, written pre-results | REFERENCE — diagnostic playbook | | No | 1; OPERATOR-GUIDE |
| `notes/draft-codex-parallel-preproduction-plan-under-review.md` | 426 | 2026-09-06 / 2026-09-06 | DRAFT Codex parallel-work plan; status note says events diverged, now historical intent only | ONE-OFF — marked stale by its own added note | | Partial-self (not the literal keyword) | **0 → ORPHAN** |
| `notes/draft-git-publication-rehearsal-and-freeze-plan-under-review.md` | 342 | 2026-09-07 / 2026-09-06 | "DRAFT, UNDER REVIEW" git publication/freeze plan; not authorization to push | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/eval-validity-and-what-is-reportable.md` | 112 | 2026-09-09 / 2026-09-09 | What 518 recorded episode rows support, two defects found by reading records | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/EVALUATOR-THROUGHPUT.md` | 400 | 2026-09-06 / 2026-09-06 | Evaluator throughput under current evaluator is UNMEASURED; earlier "~4x slower" withdrawn | APPEND-LOG — 4 dated correction headings | | No (a claim within it is withdrawn, not the doc) | 1; START-HERE |
| `notes/EVALUATOR-VALIDATION-STATUS.md` | 235 | 2026-09-07 / 2026-09-06 | Which evaluator families are validated on the CURRENT revision, and how | APPEND-LOG — 5 dated superseding-update headings stacked at top | | Partial — L18 "historical evidence, not a live validation ledger" | 1; START-HERE |
| `notes/EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md` | 421 | 2026-09-07 / 2026-09-07 | Defines the review contract for the artifact builder; not itself an artifact | REFERENCE — spec | | No | 1; START-HERE |
| `notes/external-review-triage.md` | 260 | 2026-09-07 / 2026-09-06 | Triage of an external review against the real tree; "I agree with the reviewer's no-go" | APPEND-LOG — 4 dated triage-update headings | | No | 1; START-HERE |
| `notes/faithfulness-reconciliation.md` | 271 | 2026-09-07 / 2026-09-06 | Reconciles FAITHFULNESS.md's divergence table against clones and executed args | ONE-OFF — checked once 2026-09-05 | | No | 1; START-HERE |
| `notes/FINDING-c1-does-the-asymmetry-cancel.md` | 102 | 2026-09-06 / 2026-09-06 | Whether C1's 9-vs-3 truncation asymmetry cancels in reported metrics | ONE-OFF | | No | 1; START-HERE |
| `notes/FINDING-on-policy-update-density.md` | 137 | 2026-09-10 / 2026-09-06 | Four on-policy families' update density vs Procgen source | ONE-OFF, self-voided for one baseline | | Partial — L3 "SUPERSEDED FOR `idaac`, 2026-09-06 — and the finding is VOID" | 1; START-HERE |
| `notes/FINDING-online-eval-per-family.md` | 81 | 2026-09-06 / 2026-09-06 | During-training eval per family: what runs, what's suppressed, why it's safe | ONE-OFF | | No | 1; START-HERE |
| `notes/FINDING-resolving-power-at-n3.md` | 92 | 2026-09-06 / 2026-09-06 | What the production design can resolve at n=3, correcting a stale five-seed figure | ONE-OFF | | No | 1; START-HERE |
| `notes/FINDING-update-to-data-ratio.md` | 105 | 2026-09-06 / 2026-09-06 | Update/data accounting is an undeclared axis | ONE-OFF | | No | 1; START-HERE |
| `notes/first-complete-endpoint-grid-idaac.md` | 215 | 2026-09-10 / 2026-09-09 | First complete endpoint grid, `idaac` at 598,016 frames | ONE-OFF, corrected in place | | No | 1; START-HERE |
| `notes/gemini-ai-review-2-take-critically.md` | 522 | 2026-09-06 / 2026-09-06 | External Gemini review; own header: "weak AI model... take critically" | ONE-OFF — external review | | No | **0 → ORPHAN** |
| `notes/HANDOFF-CODEX-2026-09-05-0858.md` | 59 | 2026-09-06 / 2026-09-06 | Codex handoff 08:58 MSK 2026-09-05: live T4 jobs, monitor PIDs | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/HANDOFF-CODEX-2026-09-07.md` | 129 | 2026-09-07 / 2026-09-07 | Claude→Codex handoff 2026-09-07: intent/priorities, Q56 file reservation respected | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/HANDOFF-JUDGEMENT-2026-09-09.md` | 217 | 2026-09-09 / 2026-09-09 | What the files don't say: systematic vs luck findings, written at end of context | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/HANDOFF.md` | 511 | 2026-09-19 / 2026-09-07 | "The part that does NOT survive compaction"; priorities, suspicions, open branches | **APPEND-LOG — 8 dated Morning/Evening/Afternoon/Night-state headings** | | No | 5; START-HERE, PROJECT-INDEX, SYSTEM, CURRENT-STATE, OPERATOR-GUIDE |
| `notes/idaac-2048-steps-was-chosen-under-action-repeat-8.md` | 64 | 2026-09-09 / 2026-09-09 | IDAAC's step count came from action-repeat 4–8 conditions; Door runs action-repeat 1 | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/idaac-on-door-is-a-trust-region-blowout.md` | 148 | 2026-09-09 / 2026-09-09 | idaac's Door failure is a textbook PPO trust-region blowout | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/is-the-system-ready-for-the-next-run.md` | 55 | 2026-09-09 / 2026-09-09 | Audit after the first two production cells: fixed-with-a-test vs still not | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/local-disk-candidates.md` | 120 | 2026-09-10 / 2026-09-09 | What laptop disk is safe to reclaim; nothing deleted yet | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/METRIC-INVENTORY-VERDICT-2026-09-05.md` | 494 | 2026-09-06 / 2026-09-06 | What's logged per baseline, cadence/formula/collisions; extends PART2-METRIC-INVENTORY | ONE-OFF — dated verdict | | No | 1; START-HERE |
| `notes/MIGRATION-T4-TO-V100.md` | 168 | 2026-09-06 / 2026-09-06 | Host-delta category: values correct on DataSphere, wrong on V100, or vice versa | REFERENCE — delta table | | No | 1; START-HERE |
| `notes/NEXT-ACTIONS.md` | 269 | 2026-09-09 / 2026-09-06 | Where pre-production stands, ordered by review 7's priority list | APPEND-LOG — 4 dated superseding-update headings | | No | 1; START-HERE |
| `notes/OPEN-QUESTIONS-LEDGER.md` | 444 | 2026-09-09 / 2026-09-08 | Open questions from the owner, and what each turned up (several REVERSED) | REFERENCE — ledger, rows updated in place | scoped **ENTRY** | No | 1; START-HERE |
| `notes/OPEN-QUESTIONS.md` | 19 | 2026-09-07 / 2026-09-06 | Research questions anyone can answer, distinct from DECISION-SHEET's owner items | REFERENCE — small table, rows struck through in place | | No | 1; START-HERE |
| `notes/OPERATOR-GUIDE.md` | 1190 | 2026-09-19 / 2026-09-17 | The whole operator path end to end; "read this once, top to bottom, before running anything" | STATE/REFERENCE hybrid | **ENTRY** (hub) | No | 3; README, START-HERE, CURRENT-STATE |
| `notes/OPERATOR-READINESS-ADVERSARIAL-2026-09-18.md` | 62 | 2026-09-18 / 2026-09-18 | Adversarial review of the operator package: "is this well prepared for an operator to run?" | ONE-OFF | | No | 2; START-HERE, OPERATOR-GUIDE |

Row for `notes/OPEN-QUESTIONS-LEDGER.md`'s scoped ENTRY quote: L14 "[Claude 2026-09-09] This file
is the entry point, not the answer" — scoped to researching one axis, not the whole project.

## Table — `notes/` top level, part 2 of 2 (O–W, 47 files)

| Path | Lines | Last / First commit | Role (self-claim, ≤25w) | Style (evidence) | Entry | Superseded/archived/frozen self-declaration | Inbound (n; hubs) |
|---|---:|---|---|---|:-:|---|---|
| `notes/OWNER-DECISIONS-2026-09-08.md` | 95 | 2026-09-09 / 2026-09-08 | Ten OWNER gates made decision-ready, sorted by signature/cost/measurement needed | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/owner-decisions-recommended.md` | 330 | 2026-09-06 / 2026-09-06 | Current ratification batch (2026-09-06) prepended to the unedited 2026-09-05 document | APPEND-LOG — newer batch prepended, older kept verbatim below | | Partial — L6 "§1 (IBAC-SNI) and §2 (shared evaluator validation) **are** stale ... re-read those two sections as history, not as the current ask" | 1; START-HERE |
| `notes/PARAMETER-REVIEW-CONSENSUS-MATRIX.md` | 706 | 2026-09-10 / 2026-09-08 | Reconciles every significant parameter against all 27 external reviews; "DISPOSITIONS not values" | REFERENCE — produced once by a subagent | | No | 1; START-HERE |
| `notes/ppg-and-idaac-fail-in-opposite-directions.md` | 92 | 2026-09-09 / 2026-09-09 | `ppg`/`idaac` fail as mirror images; `ppg`'s two reward series disagree in sign | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/ppg-clip-is-inert-and-that-is-forced.md` | 77 | 2026-09-10 / 2026-09-10 | `ppg`'s clip term is inert; a 32 GB card makes it unavoidable | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/ppg-took-256-gradient-steps-not-8192.md` | 450 | 2026-09-10 / 2026-09-09 | `ppg` took 256 gradient steps not 8192; conclusion later inverted | ONE-OFF, self-inverting banner | | Partial — L3 "RESOLVED 2026-09-10 — and the conclusion below is inverted, not merely completed" | **0 → ORPHAN** |
| `notes/PRE-PRODUCTION-STATUS-2026-09-07-EVENING.md` | 215 | 2026-09-08 / 2026-09-07 | Freeze-candidate status, 2026-09-07 evening; "Supersedes the in-flight-wave section" of the `-07.md` page | APPEND-LOG — 2 dated headings | | No (supersedes *another* doc's section) | 1; START-HERE |
| `notes/PRE-PRODUCTION-STATUS-2026-09-07.md` | 189 | 2026-09-07 / 2026-09-07 | What's finished/not, 2026-09-07; carries two later self-correction banners | APPEND-LOG — 2 dated banners | | Partial — L11 "That is not true of this tree" (self-corrects a "7/7" claim made earlier in the same file) | 1; START-HERE |
| `notes/PRE-PRODUCTION-STATUS-2026-09-08.md` | 282 | 2026-09-08 / 2026-09-08 | Successor status doc to the `-07-EVENING` one; the day's shape, v196 canary failure | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` | 372 | 2026-09-07 / 2026-09-07 | Phase 2 source-and-implementation audit of all 12 baselines, 2026-09-06 | ONE-OFF | | No | 1; START-HERE |
| `notes/PRODUCTION-CALENDAR.md` | 153 | 2026-09-07 / 2026-09-06 | What the campaign costs, recomputed; replaces an 8–50x-wrong prior estimate | ONE-OFF, same-day correction | | Partial — L20 "Superseded later the same day" (one number) | 1; START-HERE |
| `notes/PRODUCTION-GRADE-PLAN.md` | 148 | 2026-09-10 / 2026-09-09 | Getting to a reportable battery in fewest runs; "the blocking constraint nobody had costed: seeds" | ONE-OFF — 2 dated step headings | | No | **0 → ORPHAN** |
| `notes/PRODUCTION-HOST-RATIFICATION.md` | 166 | 2026-09-09 / 2026-09-07 | Companion to RUNNING-ON-PRODUCTION-HOST.md: reasoning, defect history, owner decisions | STATE — defect history corrected in place | | No (an internal claim is marked superseded, not the doc) | 2; README, START-HERE |
| `notes/production-readiness-by-class.md` | 293 | 2026-09-08 / 2026-09-06 | "Are all things of this class ready?" item by item, 2026-09-05 | APPEND-LOG — 2 dated update/correction headings | | No | 1; START-HERE |
| `notes/production-run-register-adversarial-review.md` | 105 | 2026-09-09 / 2026-09-09 | Adversarial review of the run-register system: what would report reassuring falsely | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/PRODUCTION-RUNBOOK.md` | 188 | 2026-09-08 / 2026-09-06 | What to watch/aborts/must-not-do during the 9–28 day campaign, grounded in real failures | REFERENCE — failure-signature table | | No | 1; START-HERE |
| `notes/proposal-inference-and-checkpoint-selection.md` | 157 | 2026-09-06 / 2026-09-06 | Proposal for inference/checkpoint-selection decisions, revised after external review | ONE-OFF, revised once | | No | 1; START-HERE |
| `notes/push-plan-review.md` | 67 | 2026-09-06 / 2026-09-06 | Review of a hypothetical push plan v3; "Verdict: redo, not patch" | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/README.md` | 8 | 2026-09-06 / 2026-09-06 | Pointer only: "see START-HERE.md"; avoids a second index going stale | REFERENCE — pointer stub | | No | 5; START-HERE, PROJECT-INDEX, STEP-ZERO, CURRENT-STATE, OPERATOR-GUIDE |
| `notes/recommendation-22-accounting.md` | 54 | 2026-09-07 / 2026-09-07 | External recommendation 22's sixteen requirements audited met/partial/not | ONE-OFF | | No | 1; START-HERE |
| `notes/record-completeness-spec.md` | 210 | 2026-09-06 / 2026-09-06 | What every production episode row must carry; record broadly, rerun is not cheap | APPEND-LOG — 2 dated addenda | | No | 1; START-HERE |
| `notes/RESULTS-VALIDITY.md` | 111 | 2026-09-06 / 2026-09-06 | Which existing measurements still stand given four evaluator changes since | APPEND-LOG — 2 dated update headings | | No | 2; START-HERE, SYSTEM |
| `notes/retention-and-eval-depth.md` | 197 | 2026-09-14 / 2026-09-06 | What production must emit: retention, eval depth, cross-scale problem | APPEND-LOG — 2 dated headings | | Partial — L3 "SUPERSEDED IN PART — read this first (stamped 2026-09-14)" | 1; START-HERE |
| `notes/review-11-12-gemini-triage.md` | 185 | 2026-09-06 / 2026-09-06 | Triage of reviews 11, 12, Gemini-2 against the executable tree, snapshot 2026-09-05 | ONE-OFF | | No | 1; START-HERE |
| `notes/review-15-triage.md` | 68 | 2026-09-06 / 2026-09-06 | External review 15 triage, snapshot 2026-09-06 | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/review-17-triage.md` | 220 | 2026-09-07 / 2026-09-07 | Review 17 triage, 2026-09-06; carries a later superseding-update banner on its PPG rows | ONE-OFF, 1 superseding banner | | No (banner marks one section historical) | 1; START-HERE |
| `notes/review-18-triage.md` | 159 | 2026-09-07 / 2026-09-07 | Independent triage of review 18, treated as strong evidence despite lacking the live tree | ONE-OFF | | No | 1; START-HERE |
| `notes/review-20-21-accounting.md` | 59 | 2026-09-07 / 2026-09-07 | External reviews 20/21, item-by-item accounting against the live tree | ONE-OFF | | No | 1; START-HERE |
| `notes/review-4-5-triage.md` | 89 | 2026-09-06 / 2026-09-06 | Reviews 4/5 triage; both caught defects in the author's own instruments | ONE-OFF — 1 dated update heading | | No | 1; START-HERE |
| `notes/review-6-7-8-triage.md` | 390 | 2026-09-06 / 2026-09-06 | Reviews 6/7/8 triage, 2026-09-05; review 7 "the most complete audit" received | ONE-OFF | | No | 1; START-HERE |
| `notes/review-9-10-triage.md` | 133 | 2026-09-06 / 2026-09-06 | Reviews 9/10 triage; two things missed, one wrongly refuted earlier | ONE-OFF — 1 dated re-audit heading | | No | 1; START-HERE |
| `notes/review-artifact-spec.md` | 87 | 2026-09-06 / 2026-09-06 | Spec correcting the review-artifact builder after real omissions produced false findings | REFERENCE — spec | | No | 1; START-HERE |
| `notes/rlvigen-published-door-anchor.md` | 165 | 2026-09-06 / 2026-09-06 | RL-ViGen's own published Door numbers, from the vendored spreadsheet | ONE-OFF — 2 dated correction/refinement headings | | No | 1; START-HERE |
| `notes/rlvigen-reports-return-not-success-rate-for-robosuite.md` | 165 | 2026-09-09 / 2026-09-09 | RL-ViGen's Robosuite metric is return not success rate, read verbatim from the supplement | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/run-level-constants-stamped-per-row.md` | 68 | 2026-09-10 / 2026-09-10 | A run-level constant stamped onto every delivered row; 98% of two bundles | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/RUNNING-ON-PRODUCTION-HOST.md` | 1711 | 2026-09-18 / 2026-09-07 | The operator's procedure for running a cell on the host; "§0 is the arrival sequence" | REFERENCE — procedure, 3 dated correction/addendum headings | **ENTRY** | No | 3; README, START-HERE, OPERATOR-GUIDE |
| `notes/SAME-AXES-VERDICT.md` | 251 | 2026-09-08 / 2026-09-07 | Is the same-axes goal reached? "No — R3 NOT MET"; states exactly how | ONE-OFF — 1 dated revision heading | | No | 1; START-HERE |
| `notes/seed-variance-at-100k.md` | 79 | 2026-09-08 / 2026-09-08 | Between-seed variance measured at 100k frames; eval-easy 95% CI includes zero at n=3 | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/START-HERE.md` | 609 | 2026-09-18 / 2026-09-06 | "The index to the surfaces"; content stays in surfaces so this file "cannot drift" | REFERENCE (self-claim) **but** 12 dated "Added 2026-09-05..." accretive headings (APPEND-LOG signal) | **ENTRY** (hub) | No | 3; README, CURRENT-STATE, OPERATOR-GUIDE |
| `notes/SYNTHESIS.md` | 134 | 2026-09-06 / 2026-09-06 | What ~60 findings across five reviews and 19 corrections add up to | ONE-OFF, 1 dated update heading | | Partial — L111 "Update 2026-09-05 — the closing section above is now STALE, and deliberately left in place" | 1; START-HERE |
| `notes/two-endpoint-grids-and-the-unit-of-variation.md` | 181 | 2026-09-10 / 2026-09-10 | Two complete endpoint grids, two defects, the wrong standard error | ONE-OFF | | No | 1; START-HERE |
| `notes/what-a-door-return-number-means.md` | 81 | 2026-09-09 / 2026-09-09 | A Door return number is a hard ceiling; why SR=0 caps it at 250 | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/what-the-battery-costs-and-the-eval-paradigm-it-buys.md` | 107 | 2026-09-10 / 2026-09-10 | Battery cost re-derived against the V100 host rather than DataSphere hours | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/what-the-regimes-actually-cost.md` | 84 | 2026-09-09 / 2026-09-09 | What each eval regime costs, measured with its noise floor | ONE-OFF | | No | **0 → ORPHAN** |
| `notes/what-the-train-regime-actually-measures.md` | 59 | 2026-09-08 / 2026-09-08 | The "train regime" aggregate is already a generalization number | ONE-OFF | | No | **0 → ORPHAN** |

Note on `notes/START-HERE.md`: its own text claims to be a stable, non-drifting index ("content
stays in the surfaces so this file cannot drift out of date with them"), yet it carries 12 dated,
accreting "Added 2026-09-05 (later)"-style headings inside itself — a direct tension between its
self-description and its structure. Flagged, not resolved, here.

## Table — `notes/production-host/` (39 files)

| Path | Lines | Last / First commit | Role (self-claim, ≤25w) | Style (evidence) | Entry | Superseded/archived/frozen self-declaration | Inbound (n; hubs) |
|---|---:|---|---|---|:-:|---|---|
| `00-authority-and-scope.md` | 38 | 2026-09-08 / 2026-09-08 | Which machine (`cds2`), whose authority, what being listed does NOT mean | REFERENCE | | No | **0 → ORPHAN** |
| `01-connection.md` | 82 | 2026-09-08 / 2026-09-08 | Netbird connection commands; "installation is not our step" | REFERENCE | | No | **0 → ORPHAN** |
| `02-absolute-prohibitions.md` | 40 | 2026-09-08 / 2026-09-08 | Absolute host prohibitions, no exception path | REFERENCE | | No | **0 → ORPHAN** |
| `03-docker-discipline.md` | 94 | 2026-09-09 / 2026-09-08 | All work inside a container; the shape of a correct run | REFERENCE | | No | **0 → ORPHAN** |
| `04-resource-safety.md` | 58 | 2026-09-08 / 2026-09-08 | Assume nothing is free: GPU/VRAM/RAM/disk shared-resource rules | REFERENCE | | No (note 10 says it "subsumes most of" this file, from the other side) | **0 → ORPHAN** |
| `05-privacy-and-non-alarm.md` | 31 | 2026-09-08 / 2026-09-08 | What not to look at on a shared machine, and why looking is itself a hazard | REFERENCE | | No | **0 → ORPHAN** |
| `06-before-any-action.md` | 52 | 2026-09-08 / 2026-09-08 | Every host action stated and reasoned about before being taken | REFERENCE | | No | **0 → ORPHAN** |
| `07-this-repo-s-own-hazards.md` | 109 | 2026-09-08 / 2026-09-08 | This repo's own dangerous defaults on a shared host, found by reading code | REFERENCE — 1 dated fixed-item heading | | No | **0 → ORPHAN** |
| `08-gpu-assignment-and-time.md` | 78 | 2026-09-08 / 2026-09-08 | The GPU assignment schedule; only the assigned GPU, machine, window | REFERENCE | | No | 1; CLAUDE |
| `09-standing-cautions.md` | 81 | 2026-09-08 / 2026-09-08 | Standing cautions, not exhaustive; "must grow" with every new hazard | REFERENCE — living list | | No | 1; CLAUDE |
| `10-resource-upper-bound-rule.md` | 151 | 2026-09-16 / 2026-09-08 | "If you do not know an upper bound... do not run it" — the owner's rule, subsumes `04` | REFERENCE — 1 dated addendum heading | | No | 1; CLAUDE |
| `11-host-state-2026-09-08.md` | 551 | 2026-09-09 / 2026-09-08 | Host state snapshot, "read fresh every session; this is a snapshot, not a fact" | **APPEND-LOG — 5 dated same-day update headings** | | No | **0 → ORPHAN** |
| `12-incremental-bringup-plan.md` | 205 | 2026-09-08 / 2026-09-08 | Incremental bring-up plan for `cds2`; "Status: PLAN ONLY, nothing executed" | ONE-OFF — 1 dated status heading | | No | **0 → ORPHAN** |
| `13-how-the-operator-path-works.md` | 102 | 2026-09-08 / 2026-09-08 | What the operator path does and what's wasteful, "read from the scripts, not inferred" | REFERENCE | | No | **0 → ORPHAN** |
| `14-assets-and-environment-on-a-persistent-host.md` | 186 | 2026-09-09 / 2026-09-08 | What's transient vs accumulates on a persistent host; corrects an overstated danger | ONE-OFF — 1 dated fixed-item heading | | No | **0 → ORPHAN** |
| `15-what-fails-when.md` | 169 | 2026-09-09 / 2026-09-08 | The abort ladder from invocation to first gradient step | APPEND-LOG — 3 dated closed-item headings | | No | 1; OPERATOR-GUIDE |
| `16-host-work-log.md` | 385 | 2026-09-09 / 2026-09-08 | "Work log: what was actually run on `cds2`, and what it cost" | **APPEND-LOG — self-described work log, 3 dated day headings** | | No | **0 → ORPHAN** |
| `17-first-real-cell-plan.md` | 449 | 2026-09-09 / 2026-09-08 | The first real cell (`idaac`) and how it cannot disturb the neighbour | APPEND-LOG — 3 dated headings incl. one SUPERSEDED-IN-PART | | Partial — L363 "[Claude 2026-09-08] SUPERSEDED IN PART by `datasphere/native/launch-card-cell.sh`" | **0 → ORPHAN** |
| `18-the-watch-that-would-have-expired-first.md` | 135 | 2026-09-09 / 2026-09-09 | Near-miss: a watch timeout sized for a 10-min bootstrap during a 2h+ real one | ONE-OFF — 1 dated heading | | No | 2; README, START-HERE |
| `19-environment-lifecycle-vs-run-lifecycle.md` | 193 | 2026-09-09 / 2026-09-09 | Every cell rebuilds an identical environment from scratch; names the mistake | APPEND-LOG — 2 dated implemented/validated headings | | No | 3; README, START-HERE, STEP-ZERO |
| `20-egl-renderer-problem-STATEMENT.md` | 213 | 2026-09-09 / 2026-09-09 | Full EGL/NVIDIA renderer problem statement for outside help; "Status: RESOLVED 2026-09-09" | ONE-OFF — self-declared resolved | | No (RESOLVED is a status word, not supersede/archive/frozen) | **0 → ORPHAN** |
| `21-which-baselines-to-run-on-a-shared-card.md` | 193 | 2026-09-09 / 2026-09-09 | Which three baselines to run first on a shared card, and on what evidence | APPEND-LOG — 3 dated revision headings | | No | **0 → ORPHAN** |
| `22-what-a-cell-actually-uses.md` | 304 | 2026-09-09 / 2026-09-09 | What a cell actually uses, measured on the card during the first `idaac` cell | APPEND-LOG — 4 dated measurement/correction headings | | No | **0 → ORPHAN** |
| `23-the-first-complete-cell.md` | 123 | 2026-09-09 / 2026-09-09 | The first complete cell on `cds2`: what it proves, what it cost | ONE-OFF — 1 dated heading | | No | **0 → ORPHAN** |
| `24-what-a-yield-actually-costs.md` | 52 | 2026-09-09 / 2026-09-09 | A yield is not cheap: no resume path exists for `idaac`/`ppg` | ONE-OFF | | No | **0 → ORPHAN** |
| `25-a-production-cell-is-half-training.md` | 49 | 2026-09-09 / 2026-09-09 | A production cell is about half training, half evaluation | ONE-OFF | | No | **0 → ORPHAN** |
| `26-the-vram-cap-never-reached-a-trainer.md` | 135 | 2026-09-09 / 2026-09-09 | The VRAM cap module was never on the trainer's path | ONE-OFF — 1 dated confirmed heading | | No | 1; OPERATOR-GUIDE |
| `27-disk-not-vram-is-what-caps-parallelism.md` | 259 | 2026-09-18 / 2026-09-09 | Disk headroom, not VRAM, caps parallelism; one shared filesystem for everything | APPEND-LOG — 3 dated addendum/executed headings (09-18) | | No | 1; OPERATOR-GUIDE |
| `28-eval-is-sixty-percent-of-a-cell.md` | 85 | 2026-09-09 / 2026-09-09 | Evaluation is 60% of cell wall-clock, the hardest half to read | ONE-OFF | | No | **0 → ORPHAN** |
| `29-two-drifts-a-self-yield-and-a-wrong-cost.md` | 87 | 2026-09-10 / 2026-09-10 | Two drifts, one mechanism: taking a shared resource with no bound | ONE-OFF | | No | **0 → ORPHAN** |
| `30-did-we-crowd-anyone-out.md` | 56 | 2026-09-10 / 2026-09-10 | Measured, per cell, what eight cells took from the shared card | ONE-OFF | | No | **0 → ORPHAN** |
| `31-state-at-the-pause-2026-09-10.md` | 45 | 2026-09-10 / 2026-09-10 | State at a ~24h owner-directed pause | ONE-OFF — 1 dated heading | | No | **0 → ORPHAN** |
| `32-what-we-actually-have-2026-09-14.md` | 190 | 2026-09-14 / 2026-09-14 | Full artifact audit 2026-09-14; corrects an earlier "checkpoints dropped" claim | ONE-OFF — 1 dated heading | | No | **0 → ORPHAN** |
| `33-what-we-actually-have-2026-09-16.md` | 276 | 2026-09-16 / 2026-09-16 | "Successor to" note 32; re-evaluation landed, three numbers were wrong | ONE-OFF — 1 dated heading | | No | 1; CURRENT-STATE |
| `34-first-three-baseline-reading-2026-09-17.md` | 94 | 2026-09-17 / 2026-09-17 | First three-baseline same-axes reading; "a reading, not a result" | ONE-OFF | | No | 1; CURRENT-STATE |
| `35-what-the-campaign-costs-at-measured-rates.md` | 155 | 2026-09-18 / 2026-09-17 | What the remaining campaign costs at measured, not extrapolated, rates | APPEND-LOG — 2 dated addendum/decision headings | | No | 1; CURRENT-STATE |
| `36-no-completed-cell-passes-the-competence-gate.md` | 144 | 2026-09-18 / 2026-09-18 | Every completed cell fails the competence gate | ONE-OFF | | No | 1; CURRENT-STATE |
| `37-what-a-cell-actually-costs-in-wall-clock.md` | 92 | 2026-09-18 / 2026-09-18 | Retracts a wrong "96s endpoint grid" figure quoted out of context | ONE-OFF — self-retraction | | No | **0 → ORPHAN** |
| `production-host/README.md` | 97 | 2026-09-18 / 2026-09-08 | "Read this entire directory before touching anything"; index of what each note governs | REFERENCE — index | **ENTRY** | No | 5; START-HERE, PROJECT-INDEX, STEP-ZERO, CURRENT-STATE, OPERATOR-GUIDE |

**Observation on this directory as a whole:** 26 of these 39 files (67%) have zero inbound links
from the 8 named hubs. The hubs mostly link the directory as a unit (e.g. `CLAUDE.md`:
"read `notes/production-host/` in full") rather than each numbered note individually. Verified
directly: `production-host/README.md` itself links notes `00` through `33` by name (34 links) but
**not `34`, `35`, `36`, or `37`** — the four newest notes (2026-09-16 through 2026-09-18) are
absent from the directory's own index, even though `notes/CURRENT-STATE-AND-RESPONSIBILITY.md`
links to all four of those directly. This is a structural fact about how the hub-link check is
scoped, not proof the older numbered notes are unread.

## Folders reported as counts only (per task instructions)

| Folder | `.md` file count | Total lines | Note |
|---|---:|---:|---|
| `docs/dated/` | 20 | 2,601 | Includes two subfolders: `2026-08-24-reviewer-pack/` (11 files) and `2026-08-25-action-repeat-audit/` (4 files), plus 5 files directly in `docs/dated/` (`2026-08-24-faithfulness-delta-review.md`, `2026-08-24-outside-reviewer-brief.md`, `hundred-k-results-2026-09-04.md`, `preprod-table-2026-09-03.md`, `README.md`) |
| `docs/refs/` | 0 | 0 | Contains one file, `rlvigen-supplemental-extract.txt` — not `.md`, out of scope by extension |
| `docs/library-survey/` | 10 | 2,311 | `CONTEXT.md`, `synthesis-cleanrl.md`, plus 8 files under `raw/` |
| `docs/metrics-survey/` | 4 | 1,800 | `CONTEXT.md`, `flow.md`, `gen-rebuttal.md`, `unified-bench.md` |

## External-review group (not read; `notes/ai-review-*` and `notes/*-external*.md`)

**27 files, 17,444 total lines.** Per instructions, bodies were not opened — only counted
(`wc -l`) and checked for inbound hub links (by exact filename match). All 27 show **0/8** hub
matches by exact filename. `notes/START-HERE.md:298` does reference this group **categorically**
("`ai-review-2..5-external.md` — the reviews as received") rather than by exact filename per file,
so the 0-count should not be read as "START-HERE never mentions these" — only as "no hub spells out
any one of these 27 filenames individually." (unverified beyond this one categorical-reference
check; the other 22 files in the group were not individually searched for elsewhere in START-HERE.)

The 27 files: `ai-answer-egl-28-external.md`, `ai-help-26-external.md`,
`ai-recommendation-22-external.md`, and
`ai-review-{2,3,4,5,6,7,8,9,10,11,12,13,14,15,17,18,19,20,21,23,24,25,27}-external.md` (23 files,
non-contiguous — no `ai-review-16-external.md`; `22` and `26` in that numeric run appear instead as
`ai-recommendation-22-external.md` and `ai-help-26-external.md`, suggesting one shared numbering
sequence across review/help/recommendation/answer types, though that is inferred from filenames,
not verified against content), plus `ai-review-15-external-processed.md` (a second, processed copy
of review 15). Note separately: **`notes/ai-help-16.md` exists without an `-external` suffix** and
so falls *outside* this grouping rule and was given full individual treatment above (row in
part 1 of the `notes/` table) — its number (16) is exactly the one missing from the
`ai-review-N-external` run, consistent with it being the same underlying external input named
differently.

## Files flagged ENTRY, with the exact claiming sentence

All line numbers below verified directly with `grep -n` against the live file (not the reading
dump this report was drafted from).

| File | Exact sentence (file:line) |
|---|---|
| `instruction.md` | "Read this before changing anything." (`instruction.md:3`) |
| `README.md` | "## The approach changed on 2026-08-17. Read this before the rest of the file." (`README.md:5`) |
| `docs/PROJECT-INDEX.md` | "## Start here from a fresh clone" (`docs/PROJECT-INDEX.md:6`) |
| `docs/RUN-THIS-PROJECT.md` | "This replaces knowing which of ~30 documents in `notes/` to read." (`docs/RUN-THIS-PROJECT.md:7`) |
| `docs/STEP-ZERO.md` | "# Step zero — the practice before any code, and how claims must be shaped to survive" (`docs/STEP-ZERO.md:1`), plus its live "## Handoff, 2026-09-08 —..." block (`docs/STEP-ZERO.md:3`) |
| `notes/CURRENT-STATE-AND-RESPONSIBILITY.md` | "# Current state and responsibility — read this first, especially after context loss" (`notes/CURRENT-STATE-AND-RESPONSIBILITY.md:1`) |
| `notes/OPERATOR-GUIDE.md` | "Read this once, top to bottom, before running anything." (`notes/OPERATOR-GUIDE.md:11`) |
| `notes/START-HERE.md` | "# START HERE — the index to the surfaces" (`notes/START-HERE.md:1`) |
| `notes/RUNNING-ON-PRODUCTION-HOST.md` | "This is the operator's guide. Read §0 first; it is the arrival sequence." (`notes/RUNNING-ON-PRODUCTION-HOST.md:3`) |
| `notes/production-host/README.md` | "# The production host: read this entire directory before touching anything" (`notes/production-host/README.md:1`) |
| `notes/OPEN-QUESTIONS-LEDGER.md` (scoped) | "[Claude 2026-09-09] This file is the entry point, not the answer." (`notes/OPEN-QUESTIONS-LEDGER.md:14`) — scoped to researching one axis, not a whole-project claim |

**10 files (11 counting the scoped `OPEN-QUESTIONS-LEDGER.md` claim) self-describe as an entry
point, "read first", "start here", or index** — for at least four distinct audiences (a fresh
clone / code, a new session after context loss, an operator running the production host, a
research question).

## Pairs/groups of files whose self-declared roles overlap (factual only, no ranking)

1. **`notes/START-HERE.md` and `docs/PROJECT-INDEX.md`** both self-describe as *the* index: `START-HERE.md` is "the index to the surfaces" for `notes/`; `PROJECT-INDEX.md` is the index of documents "that outlive any one session" for `docs/`. Each links to the other, but neither states which is the index-of-indexes.
2. **Four "current state / handoff" surfaces overlap in claimed freshness**: root `HANDOFF.md` (explicitly EXPIRED, kept as evidence), `notes/HANDOFF.md` ("the part that does NOT survive compaction" — a diary), `docs/STEP-ZERO.md`'s embedded "Handoff, 2026-09-08" block, and `notes/CURRENT-STATE-AND-RESPONSIBILITY.md` ("what is true right now"). `docs/SYSTEM.md`'s own text names part of this overlap directly: root `HANDOFF.md` L13 states "two working-state slots exist (this file and STEP-ZERO's block) with no rule for which is authoritative."
3. **Three files claim the operator/production-host procedure role**: `notes/OPERATOR-GUIDE.md` calls itself "the map"; `notes/RUNNING-ON-PRODUCTION-HOST.md`'s own banner literally says "This is the operator's guide"; `notes/production-host/README.md` says "Read this entire directory before touching anything." `OPERATOR-GUIDE.md` itself tries to resolve part of this by naming `RUNNING-ON-PRODUCTION-HOST.md` "the procedure" and pointing to `production-host/README.md` for the "why" — but the naming collision (a file titled "operator's guide" inside a document that is not `OPERATOR-GUIDE.md`) stands as written.
4. **Four files claim the "what the owner still needs to decide" role, at different dates**: `notes/DECISION-SHEET.md` (2026-09-05, "everything waiting on you, in one pass"), `notes/OWNER-DECISIONS-2026-09-08.md` ("the ten OWNER gates, made decision-ready"), `notes/owner-decisions-recommended.md` (2026-09-06 batch prepended to a 2026-09-05 one), and `notes/OPEN-QUESTIONS-LEDGER.md` ("open questions from the owner"). None of the four states it supersedes the others; `owner-decisions-recommended.md` explicitly treats parts of its own earlier content as stale rather than pointing readers to a single successor.
5. **A three-document "pre-production status" chain**: `notes/PRE-PRODUCTION-STATUS-2026-09-07.md`, `notes/PRE-PRODUCTION-STATUS-2026-09-07-EVENING.md` (explicitly "Supersedes the in-flight-wave section of" the `-07.md` page), and `notes/PRE-PRODUCTION-STATUS-2026-09-08.md` ("Successor to `PRE-PRODUCTION-STATUS-2026-09-07-EVENING.md`"). Each names its immediate predecessor, so the chain is self-documenting, but all three remain in the tree with overlapping "what is finished / not" claims and none is marked archived.
6. **Seven files self-describe as a "handoff" for the next session/agent**, at different dates/scopes: root `HANDOFF.md`, root `HANDOVER-FROM-CLAUDE-2026-09-04.md`, `notes/HANDOFF.md`, `notes/HANDOFF-CODEX-2026-09-05-0858.md`, `notes/HANDOFF-CODEX-2026-09-07.md`, `notes/HANDOFF-JUDGEMENT-2026-09-09.md`, and root `RECOVERY-HANDOFF.md` (scoped to the recovery candidate only). Six of the seven have zero inbound links from the 8 hubs (only `notes/HANDOFF.md` is hub-linked).
7. **The external-review triage family overlaps with its own consensus summary**: eleven separate `notes/review-*-triage.md` / `notes/external-review-triage.md` files each independently reconcile one or two external reviews against the live tree, while `notes/PARAMETER-REVIEW-CONSENSUS-MATRIX.md` explicitly self-describes as "one reconciliation of every significant parameter... against every external review the project has received — 27 files," produced later (2026-09-08) by a subagent instructed to read all of them. The matrix does not state it replaces the individual triage files, and all still carry hub links from `START-HERE.md`.
8. **The "DZ report" family has two report dates plus a delivery-format variant**: `docs/dz-report-ru.md` (2026-08-11) and `docs/dz-report-2026-08-24.md` (2026-08-24, a later revision after "внешнего рецензирования") both self-describe as the status report to supervisor DZ, and `docs/dz-report-ru-spoken.md` is a spoken-delivery variant (unclear from its own text which written report it accompanies).

## Broken hub links (in the 8 hub files only)

**None found.** Extracted every inline Markdown link (`[text](target.md...)`) from all 8 hub files
with `grep -noE`: **344 links total**. For each, resolved the target relative to the hub file's own
directory and checked existence with a filesystem check. **All 344 resolve to an existing file.**
No reference-style link definitions (`[text]: target`) exist in any of the 8 hubs (checked
separately, zero matches). This check covers Markdown link syntax only; a bare filename mentioned
in prose or inside a code span without link syntax (e.g. `` `some-file.md` ``) was not evaluated as
a "link" for this check, per the task's literal wording ("hub link").

## Summary counts (over the 180 individually-treated files; 27 external-review + 34 folder-summary files excluded from these counts)

| Style | Count | Note |
|---|---:|---|
| ONE-OFF | 91 | Majority style: a single dated finding/report/triage, not rewritten or accreted |
| REFERENCE | 42 | Includes 2 counted twice below (hybrids) |
| APPEND-LOG | 35 | Includes 2 counted twice below (hybrids) |
| STATE | 14 | Includes 1 counted twice below (hybrid) |
| **Distinct files** | **180** | Two files carry a contested/hybrid classification: `notes/OPERATOR-GUIDE.md` (STATE/REFERENCE) and `notes/START-HERE.md` (self-claims REFERENCE/index but structurally shows APPEND-LOG signals) |

- **ENTRY-flagged: 11** (10 unscoped + 1 scoped to a single research question) — see list above.
- **ORPHAN (zero inbound links from the 8 hubs): 60 of 180 (33%)**. Concentrated in two places:
  `notes/production-host/` (26 of 39 files, 67%) and one-off dated findings/handoffs directly under
  `notes/` (33 files) that are reachable only by browsing the directory, not by a hub link — plus
  root `HANDOVER-FROM-CLAUDE-2026-09-04.md`.
- **Declares itself superseded/archived/frozen (in whole or in a marked part): 22 of 180** files
  (12%) carry at least one such self-declaration — 4 whole-document (root `HANDOFF.md`,
  `docs/DECISION_LOG.md`, `docs/DISCIPLINE_IMPOSED.md`, `docs/STATE-2026-08-16.md`) and 18
  partial/section-scoped (a banner, a paragraph, or one finding within an otherwise-live document,
  e.g. `docs/COMPARABILITY_CONTRACT.md`'s §1–§10 banner or `notes/FINDING-on-policy-update-density.md`'s
  idaac-only void). No file in the corpus uses the literal word "archived" of itself; the
  vocabulary actually used is "Superseded", "SUPERSEDED IN PART", "HISTORICAL", "STALE", "RESOLVED
  (with an inverted conclusion)", and "SCOPE, ... this measures the SUPERSEDED port." This count
  is exact over the 180-row table (machine-counted from the Superseded column), not an estimate.

## Assumptions and scope decisions made while producing this report

1. "Date of first commit" was taken as the earliest date `git log --format=%cs -- <path>` reports
   for that exact path in this workspace's history, which is frequently the 2026-09-04 recovery
   snapshot rather than true original authorship (see the methodological caveat at the top).
   (verified directly: `git log`)
2. "3+ dated headings" for APPEND-LOG was interpreted to include table rows and numbered `C##`
   entries that function the same way (`docs/CONSTRUCTION.md`'s 98 `C##` entries,
   `docs/REGISTER.md`'s 190 dated rows, `notes/CORRECTIONS.md`'s 43-row ledger), per the task's own
   example wording "or dated C-/entry blocks that accumulate." (unverified — this is an
   interpretation of ambiguous instructions, not a measurement)
3. A file was flagged ENTRY only where it makes a first-person claim about **itself** ("read this
   first", "start here", "the index", "the entry point") — not where another file merely
   *describes* it as an entry point (e.g. `docs/PROJECT-INDEX.md` calling `README.md` "the code's
   own entry point" was corroborating evidence, not the reason `README.md` was flagged; `README.md`
   was flagged for its own "read this before the rest of the file" banner).
4. A superseded/archived/frozen self-declaration was counted only when the sentence refers to the
   file (or a clearly bounded section of it) itself as superseded/stale/historical — not every
   occurrence of those words in prose about some other artifact (e.g. "the frozen tree",
   "a frozen evaluator", "PPG's σ frozen at 1.0" were read and excluded as topical, not
   self-referential). This required reading the actual sentence around each `grep` hit rather than
   trusting the keyword match alone; ~40 additional keyword hits across the corpus were reviewed
   and excluded on this basis (not separately tabulated).
5. Inbound-link counting used exact-filename substring matching (`grep -qF <basename> <hub>`)
   against the 8 named hub files only, per the task. A hub referencing a file by directory-glob
   shorthand (as `notes/START-HERE.md:298` does for `ai-review-2..5-external.md`) does not count as
   linking that file by name; this is noted where it materially affects the ORPHAN reading
   (production-host directory, external-review group) but was not separately re-checked for every
   other zero-inbound file in case a similar shorthand exists elsewhere. (unverified for files
   outside those two call-outs)
6. Broken-link checking covered inline Markdown link syntax `[text](target)` only, resolved
   relative to each hub file's own directory; anchors (`#section`) were stripped before checking
   file existence, not validated as real headings.









