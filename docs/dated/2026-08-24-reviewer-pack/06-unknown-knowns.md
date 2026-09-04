# Unknown knowns — what the project knows and has not acted on

**Written 2026-08-24. Dated snapshot, not a living document.**

Things that are written down somewhere, or are plainly implied by things written down, but have not
changed how the work is done. These are more interesting than the open items in the register,
because the register is a list of things we are *watching*. This is a list of things we have already
concluded and then walked past.

## 1. Every defect found sits at a *join*, and every instrument checks an *artifact*

The project's founding rule is **"duplication is free; any join carries burden of proof."** It was
applied with real discipline to **code** joins — hermetic baselines, no shared adapters, a register
entry (C53) raised rather than silently resolved when two standards conflicted.

**It was never applied to epistemic joins.** And every defect the project has found is one:

| entry | the join |
|---|---|
| C54 | config ↔ what the environment actually rendered |
| C55 | a measured floor ↔ the instrument that needed it |
| C56 | env A ↔ env B |
| C43 / C45 | `Protocol`'s certification ↔ `train.py`'s eval loop |
| C23 | "RESOLVED" ↔ "defect removed" |
| C53 | `TASK.md` R3 ↔ porting-directive §1 |
| C57 | "training ran" ↔ "a policy exists" |
| C58 | "verify the training distribution" ↔ "baselines keep buffers" |
| **C64** | "the fix was applied" ↔ "the fix reaches a run" |

**In every case both sides were individually correct.** That is what makes them invisible: no
artifact is wrong, so no artifact-checking instrument fires.

The project has **65 register entries and several hundred tests, and not one of them points at a
seam.** They all point at a file, a field, or a number. This was written down in `SYSTEM.md` on
2026-08-20 with the conclusion that whether it is fixable by a check or only by a habit is *"genuinely
open"* — and nothing has been done since. **C64, found four days later, is another instance of
exactly the class that bullet describes.**

If you review one thing about the process, review this.

## 2. A whole class of divergence has no home

Divergences split by **what licenses the change**. Three kinds have a document. The fourth does not:

> **Handicap: recorded, not removed.** Licensed by *nothing* — it is a *non*-change with a
> consequence.

It has no home **structurally**, not by oversight: a handicap produces no `git diff` hunk for
`deviations.py` to count, and no authored line for `INTEGRATION-DELTA.md`'s own admission rule to
catch — a non-change *is* correctly attributed to the original authors. `FAITHFULNESS.md` is the
natural home, since a handicap bears directly on "would this number be fair to call that method's
result?", but it is keyed by algorithm and these are cross-cutting.

**Current members, all recorded somewhere and collected nowhere:** the entropy coefficient (C61),
`ibac_sni`'s 227× model (C3), render resolution 100→84/84/64 (C5), IDAAC's referent-less instance
labels (C50), the 3/9 truncation split (C1), and same-named metrics meaning different things.

They are findable by **date**, through the register. They are invisible by **algorithm**, which is
the axis a reader of `idaac`'s fidelity section is actually on — so that reader currently learns
nothing about its instance-invariance loss being inert here.

## 3. A new instrument is usually wrong on its first run, and only *use* reveals how

Documented with six worked examples, three of them in instruments written the same day:

| instrument | defect | how it surfaced |
|---|---|---|
| `audit_seed_control` | three blind spots (constructor kwargs, `absl.flags`, dynamic import) | hand-checking its verdicts |
| `probe_determinism` | timing filter dropped whole LINES, discarding 21 updates of signal | a one-value fingerprint looked wrong |
| `probe_determinism` | called a third identical run a "cross-seed control" | reading the code while it ran |
| `check_citations` | anchored across markdown table cells | it flagged two *correct* citations |
| `highest_patch_id` | read a P-number out of a *comment* as a declaration | four documents failed for saying something true |

**Not one was found by writing the instrument more carefully.** Every one was found by running it and
disbelieving a result. The stated rule — *"the first output of a new checker is data about the
checker"* — is real and is followed inconsistently.

Note the asymmetry, which is recorded and worth your attention: five of six **understated** the
subject. An instrument that invents defects wastes a session; one that hides them corrupts a result.

## 4. Instruments are not audited for vacuity — and the canonical case is ugly

The citation resolver ran, passed, and reported **0 defects across 677 citations** while its
predicate — *"is the line number ≤ the file length"* — could not fail for any realistic input. It
reached 39% of the corpus. When content-anchoring was added, it immediately found **7 genuinely stale
citations**, all drifting later, exactly as predicted.

The lesson is now a command (`scripts/audit_instruments.py`) rather than a figure in prose, which is
the right shape. But it reports coverage as a **floor**, detected by marker words in the covering
test — so a test that checks a failure mode without saying so reads as uncovered.

## 5. The measurement layer mostly points at retired code

Instruments outnumber standards several times over. But most of that coverage points at the
**superseded `rlgen/` port**, not at the twelve clones that produce reported numbers. The share was
measured once at ~6–8% clone-facing and deliberately not transcribed, because the same session's own
work moved it.

**An instrument aimed at the wrong artifact is worse than a missing one, because it reports green.**
C64 is what that costs in practice.

## 6. A session that measures this system invalidates its own measurement by continuing to work

Three figures written one night were stale by morning — the document set's line count, the register's
entry total, the instrument counts — **each invalidated by later work in the same session that wrote
it.** The fix is stated (*"a count about this repository belongs in a command, not in prose"*) and is
followed unevenly; `PROJECT-INDEX.md` was still describing the register as "26 items" on 2026-08-24,
when it held 63.

## 7. The document set grows faster than it is read

`SYSTEM.md` carries a bullet saying so. **That bullet has now been updated three times by sessions it
was written to restrain** — ~7,500 lines across 23 documents on 2026-08-16, 11,400 across 31 by
08-18, 17,700 across 32 by 08-20. For scale: the project's entire porting deviation is **602 code
lines**, so roughly **29 lines are written about the work per line of it.**

The bullet's own observation is the sharp part: from inside a session, "this growth is load-bearing"
and "this growth is the failure mode" are indistinguishable. **This pack is more lines. We are aware
of the irony and cannot resolve it from inside.**
