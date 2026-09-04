# The methodology as an object of review

**Written 2026-08-24. Dated snapshot, not a living document.**

The process is as reviewable as the results, and in this project it is arguably the larger artifact:
roughly 29 lines are written about the work per line of the work itself. This file describes the
machinery and, where known, how it fails.

## The findings register

`../../CONSTRUCTION.md`, 65 entries as of this date (count it with `python scripts/register.py
--check`; a number in prose here would be stale within the week, which is itself one of the lessons
below).

Each entry carries a **class** (INHERITED / OURS / UNDECLARED / FALSE-CERTIFICATION / DESIGN-GAP), a
**status**, a blast radius, and — once acted on — the decision, the attempt, and the **effect**.
Structure is pinned by `tests/test_construction_register.py`, which enforces rules the register set
for itself:

- an `OPEN` entry **must** state its alternatives, or the test fails;
- a `RESOLVED` entry **must** name a commit;
- **an entry is not `RESOLVED` until the effect is recorded** — including "we did it and nothing
  changed", which is a result and is routinely lost.

**What is good about it.** Findings are recorded *when noticed*, before being repaired or even
understood, so the discovery order is preserved rather than laundered into a tidy story. A later
repair does not discharge an earlier row.

**What is weak.** The register is append-only and unbounded, and nothing distinguishes a live finding
from a closed one at a glance beyond the status field. More importantly, it is a list of things
*noticed*. It has no way to represent things not noticed, and [06](06-unknown-knowns.md) §1 argues
the project's entire defect population lives in a class its instruments cannot see.

## The four-field decision format

Every decision must record: the **structural property of the original** the mechanism depends on, the
**options considered**, the **choice**, and **the result that would show the choice was wrong**.

The fourth field is the load-bearing one — it is what stops a decision fossilising into an assumption.
`scripts/decisions.py` enumerates decisions across their homes and flags register entries that left
the judgement queue with no four-field block.

**Known weakness:** the format guarantees a falsifier is *stated*. It guarantees nothing about it
being *run*. See the selection effect below.

## Falsifier discipline, and the selection effect nobody accounts for

The practice is to state, in advance, what result would refute a claim. It works when honoured. On
2026-08-24, C63 stated a falsifier (*"if the 50k `eval-easy` half also reads −0.89, this entry is
blaming the wrong axis"*), it was run the same day, and it **confirmed** the entry rather than
refuting it — which is the practice working as intended, including the part where it could have gone
the other way.

**But there is a selection effect, and it is unmeasured.** Falsifiers that are cheap to run get run.
Falsifiers requiring a training run mostly do not. **Nobody has counted how many stated falsifiers
were never executed**, and the honest expectation is that most were not.

This is worse than it sounds, because it is systematically biased: expensive falsifiers are attached
to expensive claims, which are the load-bearing ones. **The claims most in need of refutation are the
ones whose refutation costs the most, so they are the least likely to have been attempted.** No
instrument tracks this and none is proposed here, because proposing one would repeat the mistake the
next section describes.

## Instrument vacuity, and why "it passed" means little here

The canonical case: the citation resolver reported **0 defects across 677 citations** while its
predicate — *"is the line number ≤ the file length"* — could not fail for any realistic input. It
reached 39% of the corpus. Content-anchoring, added later, immediately found **7 stale citations**.

The rule adopted from it: **every checker needs a test that deliberately breaks what it claims to
check. If you cannot construct an input that makes it red, it is decoration. A "nothing was checked"
result is a failure, not a pass.**

`scripts/audit_instruments.py` now reports the red–green share, deliberately as a **floor**: coverage
is detected by marker words in the covering test, so a test that checks a failure mode without saying
so reads as uncovered.

**The deeper problem is aim, not coverage.** Most instruments point at the **superseded `rlgen/`
port**, not at the twelve clones that produce reported numbers. An instrument aimed at the wrong
artifact is worse than a missing one, because it reports green — and C64 is precisely what that costs:
a "FIXED" certification for a config file no run reads.

## The build-before-reading failure, stated as a standing risk

`SYSTEM.md` records the conclusion that whether the join-blindness in [06](06-unknown-knowns.md) §1 is
fixable *"by a check or only by a habit is genuinely open, and proposing an instrument for it would
repeat the mistake of building before reading."*

That is the project's most self-aware sentence and also its least acted-upon. Four days after it was
written, C64 arrived — another join defect, found by hand, that no instrument could have caught.

## Working state versus durable state

The distinction everything else follows from: **durable state survives because it is true; working
state survives one task and is then invalid.** Both failure modes have occurred here — working state
filed as fact (`HANDOFF.md` asserting a 2026-08-10 state until marked EXPIRED), and durable state held
only in context and lost to a compaction, returning *"more confident and less correct"*, because
summarisation strips hedges.

**The mitigation that generalises:** prefer *citing a measurement* to *restating one*. A handoff that
says "run this command" cannot be wrong about the number; one that copies the output can.

## What a reviewer should be sceptical of in all this

1. **It is a lot of process for three measured cells.** A reasonable reading is that the methodology
   has outgrown the evidence it governs, and that effort spent on the register would have been better
   spent on seeds. We do not have a good answer to that.
2. **The self-criticism is produced by the thing being criticised.** Every weakness listed in this
   pack was found by the same process that produced the results. That is precisely why the
   distinctive failures are the ones still invisible.
3. **Documented ≠ mitigated.** Several items in [06](06-unknown-knowns.md) have been written down
   repeatedly and changed nothing. A register entry can function as a way of *discharging* a worry
   rather than acting on it, and from inside a session those look identical.
