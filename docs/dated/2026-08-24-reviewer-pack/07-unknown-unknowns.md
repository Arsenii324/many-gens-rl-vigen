# Unknown unknowns — where we would look if we were you

**Written 2026-08-24. Dated snapshot, not a living document.**

**This whole file is speculation and is labelled as such.** It is our honest guess at where a hostile
expert would find something we have not thought about. It is included because omitting it would be
the more dishonest choice, not because we think it is reliable. Items are ordered by our estimate of
expected damage.

A note on how to read it: item 1 was speculation in the seed version of this brief written earlier
the same day. It stopped being speculation four hours later, when re-deriving numbers for
[03](03-what-was-measured.md) turned up the replicate pair. **Treat the rest of this list as having
the same status that item 1 had that morning.**

## 1. ~~Evaluation may not be deterministic in the way everything assumes~~ — CONFIRMED, same day

Promoted from speculation to measurement on 2026-08-24. The same checkpoint at the same seed gives
19/200 vs 28/200 successes. See [03](03-what-was-measured.md) §2 and
[05](05-what-would-embarrass-us.md) §1.

**What remains unknown, and is the live question:** the *cause*. Unseeded env stochasticity, unseeded
action sampling, MuJoCo/Metal nondeterminism, and an unrecorded code change between the two runs are
all consistent with the recorded metadata. **The metadata cannot distinguish them**, which suggests
the protocol record itself is under-specified — and if it is under-specified for a replicate, it is
under-specified for every comparison.

## 2. The evaluation protocol may not match RL-ViGen's, and nothing would catch it

**Nothing has ever reproduced a published RL-ViGen number (C48).** So the external comparison rests
entirely on protocol equivalence being assumed. We know episode count, horizon, robot, controller,
resolution, and level match. We do **not** know that scene sampling, episode seeding, the definition
of the reported statistic, or the checkpoint-selection rule match.

The one quantitative handle we have is discouraging: the estimand moves **10×** (0.003 vs 0.030)
depending only on which scenes enter the pool. A protocol difference far subtler than that would be
invisible and decisive.

**Sharpest form:** their `DrQ-v2` sits at 3.6 — 1.4% of the shaping ceiling — with 12× our budget,
while ours passes through 3.49 at 50k and reaches 131.05 by 100k. One of two things is true, and we
do not know which: their runs genuinely failed, or the two numbers are not the same quantity. **The
project has been implicitly assuming the first.**

## 3. Success may be defined differently in three places

Speculative but cheap to check and not checked. "Success" appears in robosuite's `_check_success`, in
the evaluator's per-episode counting, and in the reward function's `if/elif` branch. Whether all
three agree on *when* an episode counts as solved — at any step, at the final step, latched once
achieved — has not been verified end to end.

The replicate in §1 is weak evidence something here is loose: pooled *means* agreed to 0.4% on train
while *success counts* disagreed by 47%. That asymmetry is odd. If success were simply a threshold on
the same underlying trajectory statistic, both should move together.

## 4. The shaping ceiling of 250 may be wrong

C62's ceiling is derived from reading the reward function: ≤0.25/step reaching plus ≤0.25/step latch
over 500 steps. It has **not been verified empirically** by, say, running a policy that maximises
shaping and confirming it saturates near 250 without successes.

It matters more than a normal derived constant, because it is now load-bearing for a *published-number
reinterpretation* — the claim that RL-ViGen's 3.6 means "never approached the handle" is entirely
downstream of it. If the true ceiling were, say, 40, that reading collapses.

Our own data is mildly uncomfortable here: at 100k, 43 of 200 `eval-easy` episodes exceed 250, which
is expected for episodes containing successes but has not been reconciled episode-by-episode against
the ceiling argument.

## 5. Single-seed variance may exceed every effect being measured

Not speculation about whether variance is large — that is measured (59/200 vs 0/200 across two seeds;
C41 puts run-to-run variation near 49%). The unknown is whether **any** difference this project has
reported survives it.

**The uncomfortable version:** with the §1 replicate noise added on top of seed noise, it is possible
that *none* of the four fresh cells are distinguishable from each other. Nobody has run that test.
The four ratios are 0.030, 0.176, 0.280, 0.877 — the extremes probably separate; the middle two
probably do not; and "probably" is doing unearned work in that sentence.

## 6. Numbers in prose may have drifted from artifacts far more widely than the cases found

Three drifts were found on 2026-08-24 alone: the register count in the index (26 vs 63), the
baselines-without-cells figure (8 vs 9), and SGQN's live hyperparameters (C64). All three were found
incidentally, while looking for something else.

**None was found by an instrument.** `check_citations --content` exists and has ~57% precision on its
flagged set, but it checks that a cited *line* contains what the citation claims — not that a *number
in prose* still matches the artifact that produced it. There is no instrument for the latter, and the
three found today all belong to that class.

**Base-rate argument, which is the worrying part:** if three drifts surface incidentally in one day of
work not aimed at finding them, the density in a 17,700-line corpus is likely much higher than three.

## 7. The hermetic-clone stance may be hiding a common-mode failure

Twelve independent clones cannot share a bug — that is the design's whole promise. But they *do* share
the environment wrapper, the evaluator, the protocol declaration, the device shim, and the metric
plumbing.

An independent blind audit already concluded that the clone approach makes most port-era defect
classes structurally impossible **but eliminates none of the harness half** — and that every live
finding at the time sat in the harness. C54 sits there. C43/C45 sit there. The replicate in §1, if it
is an evaluator problem, sits there too.

**So the strongest form of this worry:** the design successfully eliminated the class of error the
project was watching for, and every error it has actually suffered came from the class it did not
partition.

## 8. The 100k-vs-50k window may be an artifact of checkpoint selection

The project's binding constraint is that the window yielding a *measurable* cell is narrower than the
one yielding a *finite* checkpoint — below ~50k most baselines have no skill to retain, and both 120k
runs diverged to NaN.

**But checkpoints are chosen by when they happened to be saved, not by a stated rule.** C63 already
shows that a conclusion (the −0.887 distance↔return correlation) reversed between 50k and 100k of the
*same run*. If one conclusion is that checkpoint-sensitive, others may be, and "which checkpoint" is
currently an unstated researcher degree of freedom.

## What we would most want you to add here

Anything at all. This list is written by the process whose blind spots it is trying to enumerate,
which is a known-impossible task. The three items above that we would bet are *incomplete* rather than
wrong are §3, §6, and §7.
