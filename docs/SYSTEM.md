# The document system — how state survives a session

Not a standard. This is the working system I use to keep state across compactions and hand work to
whoever picks it up. **It is mine to change**, and it should change: if a shape here makes a task
harder, alter it and say what broke. Nothing below is settled enough to defend against a case.

## The distinction everything else follows from

**Durable state survives because it is true. Working state survives one task and is then invalid.**

The two failure modes are symmetric, and both happened here:

- **Working state written into a durable document.** `STEP-ZERO.md`'s handoff asserted a base term
  as a fact; it was wrong the day it was written and would have routed the next session into a
  dirty tree. `HANDOFF.md` still says "12/12 implemented, 13 of 13 real runs" — true on
  2026-08-10, misleading by 2026-08-16 after one baseline was rebuilt and three more were flagged.
  Neither *decayed*. Both were snapshots filed as if they were facts.
- **Durable state held only in context.** A CTRL finding about episode boundaries was carried in
  conversation, lost to a compaction, and came back **more confident and less correct** —
  summarisation strips hedges, because it optimises for assertion density.

So the rule is not "write more down." It is: **write the durable thing durably, and give the
working thing an expiry.**

## Layers

| Layer | Files | Shape | Changes by |
|---|---|---|---|
| **Standard** | [`porting-directive.md`](../../../docs/porting-directive.md), `STEP-ZERO.md`, `COMPARABILITY_CONTRACT.md`, `RIGOR.md` | context/definitions/stance → operative rules → the evidence that produced them | A contradicting case **amends the rule in place**, dated, carrying the case. Not appended to as a changelog. |
| **Log** | `REGISTER.md`, `INTEGRATION-DELTA.md`, `DECISION_LOG.md`, `VALIDATION.md` | append-only, one row per event | Never rewritten. A later repair does not discharge an earlier row. |
| **Reference** | `FAITHFULNESS.md`, `ORIGINAL_LOCATIONS.md`, `PREMISES.md`, `compute.md` | keyed tables | Corrected **at source**. A superseded claim does not stay standing beside its correction. |
| **Measurement** | `scripts/deviations.py` (what is ours), `scripts/requirements.py` (R1–R7 against the brief), `scripts/decisions.py` (what was decided and what would reopen it), `scripts/audit_eval_axis.py`, `scripts/audit_instruments.py`, `tools/gen_baselines.py --check`; `scripts/state.py` **for the superseded `rlgen/` port only, which it says in its own first line** | recomputed, never remembered | Re-run. Covers only what its author knew to check — a floor, never a status report. |
| **Assurance** | `ASSURANCE.md` | claims keyed by the MECHANISM that assures them | Recomputed against the register and the instruments. A row moves between mechanisms as evidence arrives — e.g. between-seed variance moved from "known gap" to "in progress" when a second seed was launched. |
| **Working** | `HANDOFF.md`, `STEP-ZERO.md`'s handoff block, plan files | scoped snapshot | **Carries its scope and expires with it.** See below. |

## Working state, specifically

The layer that keeps rotting, so it gets the most rules:

- **State its scope, not just its date.** "Valid for: the `ibac_sni` rebuild" lets a later reader
  *reject* it. A bare date invites them to trust it and discount slightly.
- **Prefer citing a measurement to restating one.** `scripts/state.py` recomputes base terms and
  descent; a handoff that says "run it" cannot be wrong about them, and one that copies its output
  can. Restate only what the script structurally cannot produce: what was decided, why, what to
  distrust first, what was tried and failed.
- **Dead ends belong here and nowhere else.** They are worth a lot for one task (they stop a
  re-run) and worth nothing after it.
- **Rewrite at the end of a task, not the start of the next.** The `ibac_sni` handoff still said
  "start here: rebuild `ibac_sni`" after it was done — a compaction would have sent the next
  session to redo finished work.

## What goes where, by trigger

The trigger matters more than the format:

- **A finding**, when noticed → `REGISTER.md`, dated and cited, **before** it is repaired or even
  understood. Repairing first and recording after loses why it was found.
- **A decision**, when reached → the document keyed by what it decides, in
  [`porting-directive.md`](../../../docs/porting-directive.md) §4's four fields, whose fourth
  field — the result that would show the choice wrong — is what stops a decision fossilising into
  an assumption. Not while still branching, not batched at the end: batching launders the
  discovery order into a tidy story.
  *Amended 2026-08-19, carrying its case.* This said `INTEGRATION-DELTA.md`, full stop. That file
  is keyed by **authored element** — "who wrote this, and how do we know it is right" — so a
  decision that changes code belongs there (P14 does), but one about what the **claim** may say is
  not an authored element and belongs with the claim, in `RESEARCH-FRAME.md`. Filing the second
  kind in the first would misfile it under a key that does not describe it.
  `python scripts/decisions.py` enumerates them across homes and flags register entries that left
  the judgement queue with no §4 block — the enforcement `REGISTER.md` category 42 records as
  missing. It found `C33` recorded only as prose on its first run.

  **Two shape rules the parser enforces and nothing told a writer, added 2026-08-25 after they
  cost two iterations each.** A §4 block is only enumerable if:

  1. it lives in one of the **two homes** — `INTEGRATION-DELTA.md` or `RESEARCH-FRAME.md`. A block
     written into `CONSTRUCTION.md` is invisible, by design rather than oversight: the register
     records *findings*, and a decision belongs with what it decides. Three of this session's
     decisions were written into the register and had to be moved.
  2. its bolded title line **names the register entry** (the title reads `**What was decided**` followed by a link to the entry) and
     sits **within three lines** of the `| §4 field | |` header. The citation is what links block
     to entry; the three-line limit is the parser's, and prose between title and table silently
     drops the block from the ledger.

  Both are cheap to satisfy and expensive to discover, which is the only reason they are written
  here rather than left in the regex that enforces them.
- **A mechanically-checkable claim about our own work** → make it *executable*, not written. This
  is the standing lesson: a documented classification of our own modules was wrong and one command
  exposed it.
- **A case that contradicts a rule** → amend that standard in place. Deviating where a document
  does not fit is correct behaviour; the deviation is what gets recorded.
- **Anything conversational** → chat. Docs are read by agents, not by the person who asked the
  question; "asked directly", "at your prompting", "within the hour" are register leaks. Record
  *that* a claim was surfaced by external challenge — that is real methodological evidence about
  which instruments work — without the dialogue around it.

## Section scope tags — a heading scan must not mislead

**Added 2026-08-27 after it cost three wrong claims in one day** ([C82](CONSTRUCTION.md#c82)).
Every one came from concluding out of `grep '^## '` rather than out of reading, and the headings
gave nothing to conclude from: "Summary", "The PPO family", "What would raise fidelity most" say
nothing about *which system* they describe. The worst of the three wrote a banner over
`FAITHFULNESS.md` saying it did not know the clone tree existed — when its §5 is a clone-era
re-triage that resolves and re-opens everything above it.

**The rule is not "read more carefully".** That failed three times the same day. It is: make the
cheap operation return something true.

A `##` heading in a **scoped** document — one spanning more than one era — ends with a tag:

    ## 4. The PPO family — `idaac`, `ppg`, `ibac_sni`, `ctrl`  ·  [PORT-ERA]
    ## 5. What would raise fidelity most, per unit of work  ·  [CURRENT-STATE]

| tag | meaning |
|---|---|
| `LIVE` | describes what runs today; verifiable against the current tree |
| `PORT-ERA` | describes the retired `rlgen/` port, superseded 2026-08-17 |
| `HISTORY` | was true when written, deliberately kept; **not a backlog** |
| `DURABLE` | papers, released code, other people's results; era-independent |
| `MIXED` | both eras; individual items carry their own marks inside |
| `CURRENT-STATE` | **the document's own latest triage — read this first.** At most one per document |

A tag may carry a **`-U` suffix** — *unverified*: the tag is a belief about the section, not the
result of reading it. `COMPARABILITY_CONTRACT.md`'s carry it, because they were inferred from
[C30](CONSTRUCTION.md#c30) rather than checked section by section. A guess that looks like a
finding is the failure this convention exists to stop, so it is marked rather than hidden.

> **A TAG NEVER LICENSES DISCARDING A CLAIM.** It scopes a section's *own* claims — what our
> implementation did — and says nothing about whether the section is right. `PORT-ERA` sections
> routinely carry durable research about papers and released code that no change of our tree can
> affect. `FAITHFULNESS.md` §4 is the case in point: tagged `PORT-ERA` for an hour, which would
> have invited a reader to throw away IDAAC's Appendix E column, PPG's 65 536-sample update and the
> first author's own caution about DAAC on DMC. It is `MIXED`, and the safe default for an
> uncertain section is `MIXED` or a `-U` suffix, never the tidier-looking single era.

`CURRENT-STATE` is the one that matters, because **scoped appending edits put the newest answer at
the END of a file**, and a reader arriving at the top has no way to know. Which documents are
scoped is *listed*, not detected: whether a file has two eras is a judgement about its history, and
a heuristic would nag everything or miss the ones that count.

`python scripts/check_section_scope.py --strict` enforces presence and vocabulary;
`tests/test_section_scope.py` pins that `FAITHFULNESS.md` still marks its triage as the entry
point, and goes red if that mark moves. **Neither checks a tag is *correct*** — nothing can. A
wrong tag is visible to the next reader; a missing one is what let three wrong claims through.

## Across a compaction

1. Before: finish the current unit, rewrite the working state with its scope, commit.
2. After: `STEP-ZERO.md` gates → `python scripts/state.py` → the one document that answers the
   question at hand. **Not** the whole set; it is ~7500 lines and is not meant to be read.

   **But distinguish routing from relying, added 2026-08-26 after three failures in one session.**
   *Routing* — finding which document owns a question — is what grep is for. **Relying on a
   document's conclusion is not**: read that document whole. All three failures were the same
   shape, all against `RUNNABLE-ORIGINALS.md`: a sentence matched, and the paragraph that
   superseded it sat further down. It produced a contradiction between two lines that did not
   contradict, a "still not confirmed" that had been confirmed nine runs later, and a compute plan
   built on a question the file had already answered. **A conclusion is often three paragraphs
   below the sentence that matches**, and this project amends in place, which guarantees it.
3. Treat every inherited claim, including this project's own earlier output, as argument-shaped
   until re-derived. Where a record and the artifact disagree, the artifact wins.

## Auditing the system

These documents assert things about the repo. The mechanical assertions should be runnable, and
coverage is currently thin:

| Instrument | Checks | Status |
|---|---|---|
| `scripts/state.py` | base terms with the working tree opened; descent per reference, naming which reference matched | **built**, smoke-tested |
| `tools/gen_baselines.py --check` | generated `baselines/*` match the registry | **built**, in the suite |
| citation resolver | every `file:line` in docs and docstrings resolves | **built** (`scripts/check_citations.py`), 688 citations, 0 unresolvable |
| citation *content* | the cited line contains what the citing text claims | **built 2026-08-18** (`--content`, `tests/test_citation_content.py`). This row previously read "not built — the largest gap", which was already false: the resolver existed. The real gap was subtler and is the case this table now carries — **the resolver reported 0 defects because its predicate was vacuous.** It asked only whether the line number was ≤ the file's length, which a stale citation passes as easily as a correct one, and it reached 39% of the corpus. Content anchoring found 7 genuinely stale citations, all drifting *later*, exactly as the old wording predicted and the old instrument could not see. Precision on its flagged set is ≈57% (7 sampled), so it is a lead generator |
| emission inventory | what each baseline actually logs, classified by coverage class | **built 2026-08-17** — [`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md), **432 lines** (was 289 when this row was written), seven findings. **This is the reasoning of record for what any metric IS**: raw-vs-normalised reward with the wrapper-order argument, the frame-stack split (9/3 as of 2026-09-06, `idaac` moved; 8/4 when this row was written), the three-way resolution split, three distinct action distributions, per-baseline x-axis units. `scripts/audit_comparability_seam.py` is its re-derivable regression check, **not** a second opinion — anything the two disagree about is a defect in one of them. *This row said "not built" until 2026-08-18, a day after it was done, and then carried a stale line count for a week. A status column is the part of a document most worth distrusting.* |
| decision ledger | every decision reached is enumerable, with its alternatives and its falsifier | **built 2026-08-19** (`scripts/decisions.py`, `tests/test_decisions_ledger.py`). Adds no document: the home and the §4 format both already existed and only the enforcement was missing |
| requirement status | R1-R7 from the brief, against the repo now | **built 2026-08-19** (`scripts/requirements.py`). Grades only what is decidable; R4/R6/R7 print NEEDS JUDGEMENT rather than a verdict. Its first run reported R5 MET on the evidence "plotter (requirements.py)" — it had regex-matched its own source |
| chance floor | no ratio is reported over a denominator that has not cleared a random policy | **built 2026-08-20** (`scripts/eval_across_scenes.py --random-policy`, `scripts/regime_retention_report.py`, `tests/test_regime_retention_report.py`). Door reads 1.82 with 0 successes in 400 episodes. Its first two guards both passed a chance-level denominator — one keyed to the returns' own spread, one to significance — which is why the tests are written against the measured values rather than a fixture ([C55](CONSTRUCTION.md#c55)) |
| training-distribution witness | what the agent actually saw, not what the config asked for | **built 2026-08-20** (`scripts/watch_training_frames.py`, `scripts/classify_drift_frames.py`, tests for both). Needed because `replay_buffer.py:94` hardcodes `_save_snapshot = False`, so a run's buffer holds only its ending and cannot testify about its middle ([C54](CONSTRUCTION.md#c54)) |
| eval-path determinism | two processes evaluating the same checkpoint at the same seed return identical episodes | **built 2026-08-25** (`tests/test_eval_path_determinism.py`), mutation-verified against the real defect. Exists because [C69](CONSTRUCTION.md#c69) happened in the gap between two instruments that each disclaimed it: `audit_seed_control.py` is a *static* screen and its docstring says outright that it "CANNOT establish determinism… an unseeded third RNG… needs runs, not reading"; `probe_determinism.py` is the run-based screen and fingerprints **training** runs only. Nobody ever pointed a determinism check at `scripts/eval_across_scenes.py` — our own code, and the source of every retention number reported. **The failure mode was written down, in advance, by the instrument that could not check it** |
| clone-era comparability seam | do the twelve's reported numbers land on one axis, on the architecture that actually runs | **built 2026-08-26** (`scripts/audit_comparability_seam.py`, `tests/test_comparability_seam_audit.py`), mutation-verified. Exists because [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) §1–§10 audit the **retired `rlgen/` port** — its argument rests on one shared construction path and four adapters, neither of which survives the clone approach — while [`TASK.md`](TASK.md) R3, relaxed 2026-08-26 to *metrics on the same axes*, names that document as carrying the burden. Ten axes, each classed **UNITS** (what the number means) or **CONDITIONS** (what was measured) because the two fail differently. Reports **UNITS 4/5, CONDITIONS 1/7, zero underived**. The single UNITS split is the **evaluation scene set** ([C72](CONSTRUCTION.md#c72)): our evaluator sweeps ten scenes, all seven non-native evaluators pin `scene_id=0`, so *mean over ten scenes* is being compared with *mean at scene 0*. CONDITIONS splits the claim declares and quantifies; a UNITS split it cannot. Prints the null on every run, counts the axes still underived, and is prevented by a test from emitting anything that reads as a verdict of comparability. **Subordinate to [`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md)**, which derived several of these by hand first |
| live divergence watch | is a training run still a network, or already 7.4M NaNs | **built 2026-08-26** (`scripts/watch_divergence.py`, `tests/test_divergence_watch.py`), attached by `run_cell.sh` automatically. [C57](CONSTRUCTION.md#c57) called divergence invisible in every kept artifact — true of the eight logs it had, which carry no loss column. `use_tb=True` (08-20) added `actor_loss`/`critic_loss`, and they go literally `nan` on the first bad update; for six days nothing read them. Measured cost: a run NaN at frame 7 000 (5.9 min) that ran 64 more. **Reports, never kills**, and returns a distinct BLIND code when the log has no loss columns — `drq` always — rather than calling an unwatchable run healthy. [C79](CONSTRUCTION.md#c79) |
| intermediate snapshot | keep the 50k point a 100k run is about to overwrite | **built 2026-08-26** (`scripts/preserve_intermediate_snapshot.py`, tested). [C68](CONSTRUCTION.md#c68) makes the save cadence unsettable and there is no end-of-run save, so a 100k run overwrites its own 50k weights. Preserving them turns [C73](CONSTRUCTION.md#c73)'s `n = 1` (and contaminated) budget pairing into a within-run comparison per cell. **Refuses a snapshot from a diverged run**, delegating that judgement to the watch above rather than reimplementing it |
| static defect classes | three shapes that were findable by reading and were not found | **built 2026-08-28** (`scripts/audit_static_classes.py`, `tests/test_static_classes_audit.py`). Loop boundary ([C77](CONSTRUCTION.md#c77)), written-never-read ([C79](CONSTRUCTION.md#c79)), never-executed ([C80](CONSTRUCTION.md#c80)) — the three classes that cost compute this session and had no checker, alongside `audit_dead_knobs`'s fourth. **Positive control is C77 itself**: `train.py:309` must keep being flagged. Deliberately noisy in the safe direction — a hit is a question, and a minute of reading is cheaper than a 3.5-hour run. See [C85](CONSTRUCTION.md#c85) for the sort of which findings needed a run and which did not |
| cell provenance | do the tabulated numbers come from the runs they claim | **built 2026-08-29** (`scripts/verify_cells.py`, `tests/test_verify_cells.py`, 9 tests). Per cell, the `train` and `eval-easy` grids must agree on **everything but the regime**: same `snapshot_md5` on both sides of the ratio (else it compares two policies), the file still hashing to it, the regime genuinely different, same protocol, same scene set, post-[C69](CONSTRUCTION.md#c69) seeding, the budget label matching `trained_step`, and a control seed that differs. The layer beneath the retention report and the table, and the one that was missing. **Found on its first run**: the random floor recorded no `placement_seeded` — an unwritten field, not a seeding failure (the two floor grids are byte-identical across 200 episodes), now written |
| legacy results table | an archived, within-run diagnostic — **not** a production headline | **built 2026-08-28; demoted 2026-09-05** (`scripts/results_table.py`, `tests/test_results_table.py`). It now requires explicit `--legacy-exploratory`, because its bootstrap resamples episodes from one trained policy while the production outer unit is the training seed. The usable-scene and floor refusals remain useful diagnostics, but its historic rows predate the current evaluator revision; see [`notes/RESULTS-VALIDITY.md`](../notes/RESULTS-VALIDITY.md). Production inference belongs to the frozen multi-seed reporting path, not this renderer. |
| dead knobs | a configuration value accepted by a signature and never read on the path that runs | **built 2026-08-25** (`scripts/audit_dead_knobs.py`, `tests/test_dead_knob_audit.py`), two mutants killed. Finds 4 of the 6 cases [C71](CONSTRUCTION.md#c71) records, and **the docstring states which two it cannot see** — instances 3 and 4 are an orphaned file and an unconsulted constant, a different shape. Its first version handled named parameters only and reported `alda` clean, because `alda`'s config arrives as dict keys; the test that fails on that regression is the reason the extension exists rather than a note saying it should |
| tier ledger | every declared parity tier maps to a test node producing it | **not built** |

## Four kinds of divergence, and the one with no home

Surfaced 2026-08-24 while writing a supervisor report, which had to invent a taxonomy because the
document set does not state one. Divergences are more useful split by **what licenses the change**
— the question a reviewer asks — than by importance:

| kind | licensed by | home |
|---|---|---|
| **Adaptation made, as an act of construction** | the target forces it; correctness is `INTRINSIC`, by delegation, or by corroboration | [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md), "Adaptations forced by the target" |
| **Divergence from the original, left deliberately** | a choice, with the original's value known | [`FAITHFULNESS.md`](FAITHFULNESS.md), per algorithm |
| **Handicap: recorded, not removed** | nothing — it is a *non*-change with a consequence | the register, **indexed by baseline** via `python scripts/handicaps.py` (2026-08-25) |
| **Measurement defect in our own instruments** | ours entirely | [`CONSTRUCTION.md`](CONSTRUCTION.md), by finding |

> **Closed 2026-08-25, and the fix was not a document.** Everything below diagnoses the problem
> correctly and then reaches for the wrong remedy — it looks for a *place to put* handicaps, when
> the facts were already recorded and what was missing was an **axis to reach them by**. Each
> handicap entry now carries one `**Handicap — affects:**` line naming its baselines, and
> `scripts/handicaps.py` inverts the register into the per-baseline view. No second document, so
> nothing to drift; `tests/test_handicaps_index.py` fails if the markers are lost, which is the
> one silent failure the design has.
>
> **It answered its own question immediately.** Handicaps are not evenly distributed:
> `idaac` and `ibac_sni` carry **four** each, `ppg` and `ctrl` three, and `rad`/`soda`/`alda`
> **one**. A reader comparing `idaac` against `rad` is comparing across that gap, and until now
> there was no way to see it without reading the register by date. That asymmetry is exactly what
> the paragraph below predicted would stay invisible.

**The third row was the gap, and it was structural rather than an oversight.** A handicap leaves no
trace in code, so it cannot be found by the two mechanisms this project relies on: it produces no
`git diff` hunk for `deviations.py` to count, and no authored line for `INTEGRATION-DELTA`'s own
rule ("if a reader would be wrong to attribute it to the paper's authors") to admit — a
non-change *is* correctly attributed to the authors. `FAITHFULNESS.md` is the natural home, since
a handicap bears directly on "would this number be fair to call that method's result?", but it is
keyed by algorithm and these are cross-cutting, so each one fragments across four sections or
lands in none.

Current members, all recorded somewhere and collected nowhere: the entropy coefficient
([C61](CONSTRUCTION.md#c61)), `ibac_sni`'s 227× model ([C3](CONSTRUCTION.md#c3)), render
resolution 100→84/84/64 ([C5](CONSTRUCTION.md#c5)), IDAAC's referent-less instance labels
([C50](CONSTRUCTION.md#c50)), the 3/9 truncation split ([C1](CONSTRUCTION.md#c1)), and same-named
metrics meaning different things ([`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md)).

They are findable by **date** through the register and invisible by **algorithm**, which is the
axis a reader of `idaac`'s FAITHFULNESS section is on — so that reader currently learns nothing
about its instance-invariance loss being inert here.

## Known weaknesses of this system, as of 2026-08-20

- **Every defect this project has found sits at a *join*, and the system checks artifacts.**
  Not one was a wrong measurement. [C54](CONSTRUCTION.md#c54) is config ↔ what the env rendered;
  [C55](CONSTRUCTION.md#c55) is a measured floor ↔ the instrument that needed it;
  [C56](CONSTRUCTION.md#c56) is env A ↔ env B; [C43](CONSTRUCTION.md#c43)/[C45](CONSTRUCTION.md#c45)
  is `Protocol`'s certification ↔ `train.py`'s eval loop; [C23](CONSTRUCTION.md#c23) is "RESOLVED"
  ↔ "defect removed"; [C53](CONSTRUCTION.md#c53) is TASK.md R3 ↔ porting-directive §1;
  [C57](CONSTRUCTION.md#c57) is "training ran" ↔ "a policy exists";
  [C58](CONSTRUCTION.md#c58) is "verify the training distribution" ↔ "baselines keep buffers".
  In each case both sides were individually correct.

  The project's founding rule is *"duplication is free; any join carries burden of proof"*, and it
  was applied with real discipline to **code** joins — hermetic baselines, no shared adapters,
  C53 raised rather than silently resolved. It was never applied to **epistemic** joins. The same
  rule, unapplied where it mattered more, which is why these were unknown *knowns* rather than
  discoveries: nobody would write down "and then use the number you measured".

  Consequence for this system: 622 tests and 58 register entries all point at artifacts —
  a file, a field, a number. **Nothing points at a seam.** Whether that is fixable by a check or
  only by a habit is genuinely open, and proposing an instrument for it would repeat the mistake
  of building before reading.

Stated so they can be attacked rather than discovered. Re-measured 2026-08-18; the numbers moved
enough in two days that the previous wording had become wrong in both directions.

- **It is large, and growing faster than it is being read.** *(2026-08-19: the session that added
  the instrument bullet below also added several hundred more lines to this set in one night,
  while this bullet sat here saying not to. Recorded rather than excused — the growth was mostly
  register entries carrying measurements that did not exist before, which is the defensible kind,
  but "defensible" is what every session's growth looks like from inside it.)* Count it with
  `cat docs/*.md | wc -l`; on 2026-08-16 it was ~7,500 lines across 23 documents and by
  2026-08-18 it had passed 11,400 across 31 — **more than +50% in two days**, nearly all written
  by this project's own sessions rather than demanded by a reader. *(2026-08-20: **17,700 across
  32** — another +55% in two more days, and this time from one overnight session plus one review.
  The bullet has now been updated three times by sessions it was written to restrain, which is
  either evidence it does not work or evidence that the growth is genuinely load-bearing each
  time; from inside a session those are indistinguishable, which is the bullet's point. For
  scale: the project's entire porting deviation is **602 code lines**, so there are roughly 29
  lines written about the work per line of it.)* *(The exact figure is not
  transcribed here, and the reason is this bullet's own history: it was written on 2026-08-18
  reading "11,069", and the same session added ~400 more lines before the night was out — while
  arguing that the growth was the problem.)* Progressive disclosure is the intent
  (`PROJECT-INDEX.md` routes; nothing is meant to be read whole) and it is still unmeasured
  whether the routing works. Growth of this shape is the system's most likely failure: not a
  wrong document, a set too large for the next session to reach the right one. **A session that
  adds a document should be able to name which one it expects the next reader to open instead.**
- ~~**Standards outnumber instruments.**~~ **Reversed, and the replacement worry is sharper.**
  Instruments now outnumber standards several times over — count them with
  `ls scripts/*.py tools/*.py | wc -l` and `grep -rh 'def test_' tests/*.py | wc -l`, against
  4 standards. But run
  `python scripts/test_inventory.py`: most of that coverage points at the **superseded `rlgen/`
  port**, not at the twelve clones that produce reported numbers. The count stopped being the
  problem; *what it points at* is. An instrument aimed at the wrong artifact is worse than a
  missing one, because it reports green.

  **The share is deliberately not transcribed here.** It was, for about four hours on
  2026-08-18 — "6% (20 of 334) clone-facing, 71% port" — and the same session's own work moved
  it to 8% (30 of 398) clone-facing, 59% port, by adding tests. A number that a session can
  invalidate by working is working state, and this file's own rule is to cite the measurement
  rather than restate it. The rule was written here and broken here in the same edit.
- **Workspace-level documents are outside every check this project owns.** Found 2026-08-18: this
  table said `porting-directive.md` was at the workspace root; it is at `docs/porting-directive.md`,
  and the Standard holding *"duplication is cheaper than a wrong abstraction"* and *"step N dictates
  step N+1"* was therefore being routed to a path that does not exist. Two structural reasons it
  survived, neither of them carelessness: **`ccm-intro/` is not a git repository** (only
  `projects/many-gens-rl-vigen/` is), so a moved file leaves no diff; and `scripts/check_citations.py`
  matches `path.ext:line` forms inside this project, so a bare filename in a table cell is not a
  citation it can see and the target is outside its scan root anyway. Fixed by converting the prose
  path into a **markdown link**, which brings it under `test_docs_integrity.py::test_internal_links_resolve`
  — red-green verified. **The general form: a claim about a location is only checkable if it is
  written in the form the checker reads.**

- **A new instrument is usually wrong on its first run, and only its *use* reveals how.**
  Added 2026-08-19, after a single session found six defects in checkers — three of them in
  instruments written that same session:

  | instrument | defect | how it surfaced |
  |---|---|---|
  | `audit_seed_control` | three blind spots (constructor kwargs, `absl.flags`, dynamic import) | hand-checking its verdicts against the source |
  | `probe_determinism` | timing filter dropped whole LINES, discarding 21 updates of signal | a baseline returned a one-value fingerprint |
  | `probe_determinism` | called a third identical run a "cross-seed control" | reading the code while it ran |
  | `probe_determinism` | compared trials that had hit a wall-clock cap | noticing `ppg` has no step budget |
  | `check_citations` | anchored across markdown table cells | it flagged two correct citations |
  | `highest_patch_id` | read a P-number out of a *comment* as a declaration | four documents failed for saying something true |

  Not one was found by writing the instrument more carefully. Every one was found by running it
  and disbelieving a result — the one-value fingerprint, the verdict that named a control that did
  not exist, the flag on a citation known to be right. **The practical rule: the first output of a
  new checker is data about the checker.** Budget a hand-check of its first verdicts against the
  thing it measures, and treat "it agrees with what I expected" as the least informative outcome.

  Note the direction, because it is not symmetric: five of the six *understated* the subject —
  inventing a defect, refusing a valid citation, discarding real signal. An instrument that
  invents defects wastes a session; one that hides them corrupts a result. Both are bugs, but only
  the second is dangerous, and this session produced mostly the first.

- **A session that measures this system invalidates its own measurement by continuing to work.**
  Added 2026-08-18, after three figures written that night were stale by morning — the document
  set's line count, the register's entry total, and the instrument/test counts in the bullet
  above — **each one invalidated by later work in the same session that wrote it**. None decayed
  over weeks; they were overtaken within hours. This is the `HANDOFF.md` failure at a smaller
  scale, and it has the same fix: **a count about this repository belongs in a command, not in
  prose.** Where prose needs a number, give it a date and treat it as a log entry rather than a
  description of the present.

- **Instruments are not audited for vacuity.** Added 2026-08-18, and it is the lesson of the
  citation resolver: it ran, passed, and reported **0 defects across 677 citations** while its
  predicate — "is the line number ≤ the file length" — could not fail for any realistic input.
  A green instrument is evidence only if something is known to make it red. Every checker here
  should have a test that deliberately breaks what it claims to check. **This is now a command,
  not a figure in prose** — `python scripts/audit_instruments.py`, promoted into the repo
  2026-08-19 for exactly the reason the bullet below gives. It reports the red-green share as a
  *floor*: coverage is detected by marker words in the covering test, so a test that checks a
  failure mode without saying so is missed. Read a `NO` as "look at this one".

  **Log entry, 2026-08-18: 13 of 21 instruments (61%) had a test asserting a failure mode; 7 had
  none at all** —
  `authorship`, `greenmark`, `probe_heads`, `probe_regimes`, `probe_shim_divergence`,
  `rlvigen_reference`, `test_inventory`. Two were load-bearing for claims already published in
  this register, and **both were closed on 2026-08-18**, each verified by mutation (every mutant
  killed, unmutated copy green):
  `rlvigen_reference` reads the ceiling C31/C32/C37 rest on — `tests/test_rlvigen_reference.py`
  now pins the parser against synthetic sheets *and* checks that the 3.6 quoted in prose is still
  what the workbook says, which is the anti-drift check that module's own docstring promised and
  never enforced; `probe_shim_divergence` produced C41's bound — `tests/test_shim_divergence_probe.py`
  pins that a flat divergence and a compounding one cannot report the same growth ratio, without
  which C41 is a design that could not have seen the failure it rules out.
  A third followed: `greenmark` decides whether the suite needs re-running at all, so a wrong
  answer there is a *skipped suite* rather than a wrong number — invisible by construction.
  `tests/test_greenmark.py` pins both defects its own docstrings record (a sentinel that compared
  equal to itself and reported STABLE while measuring nothing; `RL-ViGen-upstream/` and `setup/`
  classified as not-code, so a patch to the environment every baseline runs through read as
  "docs-only, no run needed").
  Two more followed the same day: `probe_regimes` now has a contract test asserting its
  hardcoded regime tuple matches what `make_env` implements (writing it found the environment has
  **six** regimes, not four — `cam-easy`/`cam-hard` are a camera axis nothing here has ever
  measured), and `probe_heads` was found returning **0 with an all-clear when every head failed
  to import**, printing that verdict directly above its own warning that a skip is not a pass.
  `test_inventory` followed, which closes the circular position: the instrument producing the
  figure this bullet quotes now has a test, and the mutation that reintroduces its known
  ~80-test misclassification is caught. **All seven are now covered**, each mutation-verified; the one surviving mutant was shown
  equivalent (`count=1` is redundant because the pattern's `^` has no `re.MULTILINE`, so it can
  only match at offset 0) rather than left as an unexplained survivor: `test_inventory` produced the 6% figure cited in
  the bullet above, so the number this document uses to criticise its own test coverage came
  from an instrument with no test — closed 2026-08-18 by `tests/test_test_inventory.py`. (Coverage was measured by name reference, which
  over-counts; treat 61% as an upper bound.)
- **The Log layer is unbounded.** `REGISTER.md` is append-only by design, which is right, but
  nothing yet distinguishes a live finding from a closed one at a glance.
- **The working-state slot is now singular, but by convention only.** `HANDOFF.md` is marked
  EXPIRED and kept as evidence; the live slot is `STEP-ZERO.md`'s handoff block plus the
  measurement layer above. No test enforces that there is exactly one.

  *Amended 2026-08-19.* This said the measurement half "describes the wrong artifact" because it
  named only `state.py`, which reports on the superseded port. `state.py` was already declaring
  that scope in its own docstring and first output line; what was wrong was this table, which
  listed it as the measurement rather than as one report about a retired thing. The clone-facing
  set is now named above. **The general shape, since it has now happened three times in this
  file: a routing row goes stale faster than the thing it routes to**, because the target knows
  what it is and the index only knows what it was told.
