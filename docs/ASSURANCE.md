# Assurance — what is believed, and by what mechanism  ·  [CURRENT-STATE]

> **Written 2026-08-29, at the owner's prompting**: *"where it's surely present; where it's
> reasonably present 'by construction' and 'by burden of proof'; where it's verified post-hoc;
> where you're not sure."* The classification below is not theirs verbatim and not a taxonomy worth
> defending — it is the set of mechanisms this project actually uses, named so that a reader can
> ask *"how do you know?"* of any row and get a different answer per row.
>
> **The point is that these are not interchangeable.** A claim assured by construction survives
> carelessness; one assured by a passing test survives only until the test stops being sensitive;
> one assured by a burden of proof is not assured at all — it is *withheld*, which is a different
> and often better thing. Presenting all of them as "verified" is the failure this file exists to
> prevent.

## The mechanisms, strongest first

| # | mechanism | what it buys | how it fails |
|---|---|---|---|
| 1 | **By construction** | the failure is impossible, not absent | the construction is misunderstood |
| 2 | **By falsifiable test that could have failed** | evidence against a specific alternative | the test was insensitive and nobody checked |
| 3 | **By measured instrument sensitivity** (mutation) | the checker would notice a real regression | the mutant catalogue is too easy |
| 4 | **By independent re-derivation** | two paths agree | both inherit the same wrong assumption |
| 5 | **By burden of proof** (refusal) | nothing false is asserted | a reader reads the blank as zero |
| 6 | **Verified post-hoc** | an existing artifact is checked | the check was written after seeing the data |
| 7 | **Asserted, unverified** | nothing | — |
| 8 | **Known gap** | honesty about what is missing | the list of gaps is itself incomplete |

## The headline results, by mechanism

| claim | mechanism | evidence |
|---|---|---|
| the twelve are hermetic: no shared-base defect can span baselines | **1 construction** | each baseline is its own clone; there is no shared trainer to share a bug ([`porting-directive.md`](../../../docs/porting-directive.md) §1) |
| `scripts/requirements.py` R3 can never grade itself MET | **1 construction** | driven to every-axis-uniform with nothing underived it stops at NEEDS JUDGEMENT; a test breaks it ([C76](CONSTRUCTION.md#c76)) |
| the seam audit can never print "comparable" | **1 construction** | every mention of comparability is negated or conditional, enforced by test |
| **the regime shift is purely visual** | **2 falsifiable** | the random-policy floor is **400/400 episodes byte-identical** across `train` and `eval-easy`, two processes 19 h apart, max diff exactly 0. A single differing episode would have refuted it ([C81](CONSTRUCTION.md#c81)) |
| **C62's shaping ceiling**: return > 250 proves the door opened | **2 falsifiable** | 240 scene-grids, 311 high-return episodes, **0** with more >250 episodes than successes. One violation would withdraw every "proves the door opened" reading in the project |
| every tabulated cell measured the same weights in both regimes | **2 + 6** | `scripts/verify_cells.py`, 8 invariants, **0 failures**; 9 tests including 7 that break one invariant each |
| **the evaluator's measurement loop is correct** | **2 + 3** | return == sum of emitted rewards, success is any-step, agent asked in eval mode — stub-env tests, three mutants killed ([added 2026-08-29](#the-gap-this-file-found)) |
| the instruments would notice a regression | **3 mutation** | 31 catalogue mutants, all killed; every checker built this week carries its own mutation check |
| the retention numbers | **4 independent** | `results_table.py` and `regime_retention_report.py` compute them by separate paths and agree |
| the reward/frame-stack/resolution facts | **4 independent** | `PART2-METRIC-INVENTORY.md` derived them by hand in August; `audit_comparability_seam.py` re-derives them from code and agrees ([C82](CONSTRUCTION.md#c82)) |
| `svea`@50k has **no** retention | **5 burden of proof** | 0/10 scenes clear the denominator rule; printed REFUSED, never a blank or a zero ([C55](CONSTRUCTION.md#c55)) |
| nine of twelve baselines have no row | **5 burden of proof** | listed as **absent with a reason** — absent and poor are different claims |
| two baselines' numbers are the same quantity | **5 burden of proof** | *not* asserted. The null is non-comparability and one UNITS axis still splits ([P-C76](RESEARCH-FRAME.md)) |

## Where I am **not** sure, stated plainly

| claim | status | why it is not more |
|---|---|---|
| **`drq`'s policy scale of exactly 0** ([C84](CONSTRUCTION.md#c84)) | **7 unexplained** | `log_std_bounds [-10, 2]` and a `tanh` squash make `exp(log_std) == 0` unreachable through that path. I cannot account for the observed value from the code. The lottery reading is *consistent with* the retry succeeding, not evidence for it |
| **why the trained scene collapses under the shift** ([C89](CONSTRUCTION.md#c89)) | **7 hypothesis** | the pattern is 3/3 arms and large; the *mechanism* — confidently-wrong features — is untested and needs a policy-behaviour probe this project does not have |
| **`svea` not correlating with the DrQ arms on scene difficulty** ([C88](CONSTRUCTION.md#c88)) | **7 absence of evidence** | ρ = +0.15/+0.21 is *not distinguishable from zero*, which is not the same as independence. Three arms, two families, one seed each |
| **the published ordering reproducing** ([C87](CONSTRUCTION.md#c87)) | **7 weak** | with three methods a random ordering matches 1 in 6 times. It leans on `drq` landing within 16%, which is one number |
| **the test suite's own green** | **8 known gap** | Three separate things were wrong with it, and only one is closed. **(a)** `2fdc161f` was committed on a red suite; cause established as my own test polluting `sys.modules` ([C90](CONSTRUCTION.md#c90)) — fixed. **(b)** The command I used to *report* suite status, `grep -c "^FAILED"`, can never match, because ANSI colour precedes the word ([C91](CONSTRUCTION.md#c91)); every "0 failures" read from it was uninformative, and only the exit code printed beside it kept the reports true. **(c)** With the grep fixed the suite is **not** green: two `test_greenmark.py` failures remain, and they are **true positives** — the tree id is unstable while a run writes into `results/` ([C93](CONSTRUCTION.md#c93)) |
| **that the suite is a valid gate at all while a run is live** | **8 known gap** | Never once run on a quiet machine this week. [C92](CONSTRUCTION.md#c92) (an MPS kernel failure that did not reproduce) and [C93](CONSTRUCTION.md#c93) both surfaced only under load. Until the suite is run with nothing else active, every green reported this week is evidence of unknown strength |
| **that greenmark can tell you when to run the suite** | **8 known gap** | It cannot see the vendored environment at all — gitignored, so an upstream-only edit reports "no pending changes" and skips the suite holding the only instrument that would catch it ([C94](CONSTRUCTION.md#c94)). The test pinning that defect asserts on a string, not the pipeline |
| **between-seed variance** | **8 known gap → in progress** | every interval in this project bounds *within-run* noise. `drqv2` seed 8 launched 2026-08-29 12:41 — the first measurement of it |
| **RL-ViGen's own evaluator on our policy** | **8 known gap** | [C48](CONSTRUCTION.md#c48), open since it was written. [C87](CONSTRUCTION.md#c87) compares the same *quantity*, which is not the same as running their *path* |
| **nine of twelve baselines** | **8 known gap** | `curl` cannot run here; `ctrl`/`ppg` cannot checkpoint as published; the rest have no cell at the 105k protocol |
| **the write-up's fidelity claims** | **8 known gap** | rest on `RUNNABLE-ORIGINALS.md`'s diff counts, not on hyperparameter-level comparison against each paper — `FAITHFULNESS.md` §4's comparisons are port-era ([C82](CONSTRUCTION.md#c82)) |

## The gap this file found

**Writing this surfaced a real one, which is the argument for writing it.** Asking "by what mechanism
is the evaluator assured?" produced an uncomfortable answer: `tests/test_eval_across_scenes.py` has
eight tests and **every one checks aggregation** — how retention is computed once rows exist.
**Nothing checked that a recorded episode return equals the sum of the rewards the environment
emitted**, and that loop is the single point every number in this project flows through.

Closed the same day (`tests/test_eval_loop_measurement.py`, stub environment, three properties).
And the closing found a second defect **in the test itself**: the first reward sequence ended in
`0.0`, so a mutant that dropped the reward on the terminal transition **survived**. Distinct
non-zero rewards now; all three mutants killed.

That is the pattern this project keeps producing — *the layer everything rests on is the layer
nobody tested* — and it is the reason this file is organised by mechanism rather than by
conclusion. Sorting claims by "how do I know?" makes an untested foundation visible in a way that
sorting them by subject does not.

## How this work was done, and what went wrong in doing it

The mechanisms above assure *the project's claims*. This section is about **my own practice**,
because the owner asked for it and because the failure modes below produced most of the wasted
compute and every withdrawn claim. Each row says whether the failure is now **prevented** by
something mechanical, or merely **known** — and that distinction is the whole point, because
"remember to be careful" has failed here often enough to be evidence against itself.

| what I did wrong | cost | now |
|---|---|---|
| **Concluded from a proxy for reading** — a `grep '^## '` map, then a reference count — three times about the same file | three withdrawn claims about `FAITHFULNESS.md`, one of which would have handed the owner a fabricated twelve-baseline task | **prevented**: `##` headings in two-era docs carry era tags, `scripts/check_section_scope.py --strict`, and a `CURRENT-STATE` mark naming the file's own latest section. Plus the rule: check the **value** a claim asserts, not the path it cites |
| **Inferred one requirement from another's summary verdict** — graded R7's plotter link as `r5() == MET` and reported "there is no shared plotting routine" | false; `scripts/plot_curves.py` exists. R5 is PARTLY for unrelated reasons | **prevented**: R7 now checks the link directly; the general shape is what `scripts/audit_static_classes.py` exists for |
| **Read a stale artifact and reported it as live** — a killed run's log, a run directory matched by mtime | two false alarms, one of which I nearly reported as a new failure | **known, partly prevented**: monitors now gate on the current run's own banner, and `run_cell.sh` scopes watchers per run. A time-relative `find` inside a long loop still goes blind — recorded in `STEP-ZERO.md` |
| **Wrote a test whose data could not fail** — the reward sequence ended in `0.0`, so a mutant dropping the terminal reward survived | the evaluator's measurement loop looked tested and was not | **prevented**: mutation is run on every new checker, and it is what caught this. The test now uses distinct non-zero rewards |
| **Ran mutations by editing the working tree** — `cp`/patch/`pytest`/restore, during a session interrupted twice | nothing lost (checked), but a race away from leaving a mutated file committed | **prevented**: the seven are catalogue entries (`mutants/catalogue.py` M25–M31) that run against a copy |
| **Started a third rendering job twice** | swap to 14.6 GB, then 0.1 GB free; the swap file grew 2 → 24 GB | **known**: `docs/local-envs.md` amended — two runs is an upper bound, not a safe number; count the memory **tree**, and `drq` runs alone. Not mechanically enforced |
| **Let a watcher's timeout expire between batches** | `drq`'s 3.1-hour cell has **no paired 50k snapshot**, unrecoverable without re-running | **prevented**: `run_cell.sh` attaches the preserver per run, scoped to the run's own budget |
| **Reported status with a check that cannot fail** — `grep -c "^FAILED"` over colourised pytest output, perhaps twenty times | none, by luck: the exit code was printed beside it every time and is authoritative. Had I printed the grep alone I would have reported green on a red suite — the `2fdc161f` failure exactly | **prevented**: `--color=no`, and the exit code is the verdict. [C91](CONSTRUCTION.md#c91) |
| **Aimed a test at the layer that was never broken** — `TestWhatCountsAsCode` asserts a *string* starts with a code prefix; nothing checked the string ever reaches the classifier | the vendored-environment blindness the test was written to pin has been live the whole time ([C94](CONSTRUCTION.md#c94)) | **known, made visible**: an `xfail(strict=True)` now exercises the real pipeline, so closing the hole produces a loud XPASS. The hole itself is an owner decision |
| **Recorded a commit hash before committing** | caught before it landed; it would have been a fabricated citation | **prevented**: the register test refuses a RESOLVED entry with no commit, which forces the two-step |

**The pattern across them.** Eight of the ten are the same shape: *a cheap operation stood in for
an expensive one, and nothing said so.* A heading scan for a read; a summary verdict for a check; a
file's presence for its freshness; a passing test for a sensitive one. That is why the remedies are
almost all instruments rather than resolutions — an instrument is what makes the cheap operation
either correct or loudly incomplete.

**What is still only remembered, not enforced:** the concurrency rule, and the discipline of
re-reading a load-bearing document rather than grepping it. Both are candidates for the next
instrument, and neither has one today.

## What this file is not

It is **not** a confidence score, and the mechanisms do not compose into one. A result assured by
construction *and* sitting on one seed is still a one-seed result: mechanism 1 does not upgrade
mechanism 8. Nor is the list of gaps complete — that is mechanism 8's own failure mode, and the
honest position is that the unknown unknowns are, by definition, absent from this table.
