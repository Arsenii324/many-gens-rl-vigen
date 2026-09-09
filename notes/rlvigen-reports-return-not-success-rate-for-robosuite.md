# RL-ViGen's Robosuite outcome metric is aggregated RETURN. Success rate is a different benchmark's.

Read from the vendored supplement,
`ext/rl_vigen/NeurIPS-2023-...-Supplemental-Datasets_and_Benchmarks.pdf`, §B, 2026-09-09. Verbatim:

> **Dexterous manipulation:** … The aggregated **success rate** is calculated by averaging over all
> three tasks.
>
> **Table-top manipulation:** SECANT previously employed Robosuite for generalization testing …
> For each difficulty level, we deploy a variety of scenarios, and each trained agent is evaluated
> within each environment **10 times (in a total of 100 evaluations)**. The aggregated **return** is
> calculated by averaging over all three tasks.

Success rate is **Adroit's** metric and Habitat's (Figure 24). Robosuite's is return, and Figure 22
plots it — *"Sample efficiency of Robosuite. The episode return of each algorithm"* — on a y-axis
running 0 to **500**.

> **The 0-500 is the PLOT'S RANGE, not a reported achievement, and I used it as a target twice
> before checking.** Searching both vendored PDFs' extracted text for a numeric Door return finds
> **none**: every "Door" line is a hyperparameter (Table 6). RL-ViGen's Door results exist only in
> **Figures 22 and 19, which are images**, and Figure 22's caption additionally says the training
> steps are *"normalized into (0, 1)"*, so even the x-axis is not absolute. **We do not know what
> RL-ViGen's algorithms actually score on Door**, and no statement about "the gap to RL-ViGen's own
> results" is supported from these documents. `drqv2` at 6e5 under our evaluator is the only route
> to a comparable number we have.

## Why this matters right now

Our records carry a `success_rate` column for every row, and today's `idaac` endpoint grid reports
`success_rate: 0.0` almost everywhere. Read as the headline outcome, that says the run failed.

**It is not the axis RL-ViGen judges Robosuite on.** Reading it as the primary result would import a
metric the benchmark does not report for this environment, and would make every Door run look like a
null regardless of what it achieved on the axis the benchmark actually uses.

This does not make `success_rate` useless — a run that starts succeeding is worth knowing about, and
it costs nothing to record. It makes it **secondary**, and it means no comparison to RL-ViGen's
published Door numbers can be built on it.

## What the idaac curve says on the right axis

11 stamps, 60 episodes per stamp per regime, from
`card0-20260909-035152/native-out/cells/idaac-s101/offline_eval_curve.jsonl`:

| frame | train | eval-easy | eval-medium | eval-hard |
|---|---|---|---|---|
| 51200 | 24.66 | 22.07 | 5.11 | 10.45 |
| 200704 | 27.10 | 24.98 | 5.80 | 4.58 |
| 350208 | **50.32** | 41.39 | 11.49 | 5.53 |
| 501760 | 37.22 | 38.47 | 9.81 | 6.84 |
| 550912 | 24.74 | 21.12 | 7.16 | 11.65 |

Two things are true at once and both should be said.

**The harness works.** Returns are in the right units and on the right scale; the regimes separate in
the expected order (`train ≈ eval-easy` well above `eval-medium ≈ eval-hard`) at nearly every stamp;
60 episodes give a standard error around 2-3, so the train gap between 24.66 and 50.32 is many
standard errors wide. A pipeline that produced noise would not produce that ordering eleven times.

**The algorithm learned quickly, then stopped.** *(Corrected 2026-09-09, later the same day — the
first version of this line said "the algorithm did not learn Door", and that was wrong for want of a
baseline.)*

`ppg`'s curve evaluated its **frame-0 checkpoint** — a randomly initialised policy — under the same
evaluator, 60 episodes per regime:

| regime | random-policy return |
|---|---|
| train | **2.24** |
| eval-easy | **1.98** |
| eval-medium | **1.54** |
| eval-hard | **2.04** |

So **random is ≈ 2 on this axis**, and `idaac`'s 24.7-50.3 is **12-25x random**. It learned, and it
learned almost all of it *early*: 2 → 24.66 by frame 51,200, then 550,000 further frames of
oscillation between 12 and 50 with no monotone trend, ending at 24.74.

**The finding is the plateau, not a failure to learn** — and a plateau is what the trust-region
diagnostics predict. Large updates make rapid progress while the policy is far from anything good
and any direction helps; they prevent the refinement that comes after.

*(An earlier version of this paragraph added "so the gap to RL-ViGen's own algorithms is real",
reasoning from Figure 22's 0-500 axis. **Withdrawn**: that axis is the plot's range and the paper
reports no numeric Door return anywhere. There may be a gap; these documents cannot establish it.)*

*(Caveat, and the second half of it corrects something I wrote an hour earlier. The baseline is
`ppg`'s initialisation, not `idaac`'s; a random policy's return on a dense-reward manipulation task
is set by the environment far more than by the network, so ~2 is a fair reference, but it is one
architecture measured once.*

***The floor is NOT free, and I said it was.*** *I wrote that "every family's curve now evaluates its
own frame-0 checkpoint". It does not. `ppg` has a frame-0 row only because its save-index scheme
writes `model000.jd` at `IC=0`. **`idaac`'s earliest retained checkpoint is 51,200** — its trainer
saves on a cadence that starts at the first interval, so no untrained checkpoint exists for it at
all. `scripts/eval_grid.py` refuses without a snapshot rather than constructing a fresh policy
(`"no snapshot found; nothing was measured"`), which is right, and means the floor cannot be
recovered from the evaluator alone.*

*Getting a per-family floor needs the trainer to write a checkpoint before the first update. That is
a `runnable/` change — the same hashed-tree constraint that defers the `ppg` minibatch fix — so it
should be scheduled with it, not before. `scripts/learning_over_random.py` reports* `NO frame-0 row
-- floor unknown, ratio NOT computed` *for every family that lacks one, and refuses to borrow
another family's.)*

## The budget is not the excuse

RL-ViGen's own **Table 6** gives Robosuite Door `Training Frames int(6e5)`, and **Table 2** gives
`Action repeat — Robosuite: 1`. Our 600k-frame, `action_repeat=1` budget **is the paper's budget**,
not a reduced one. So "it needed longer" is not available as an explanation without contradicting the
benchmark this project is reproducing.

## A trap: there are two Doors

**Table 5 is Adroit and it also has a task called Door**, at `int(1e6)` frames and scored by success
rate. **Table 6 is Robosuite**, Door at `int(6e5)` and scored by return. A search for "Door" in the
supplement returns both, newest-looking first is meaningless, and taking the Adroit row yields a
frame budget 67% too high and the wrong metric. Anyone re-deriving these numbers should check which
table they are standing in.

## What this does NOT close

**The `idaac`-side `action_repeat` question stays OPEN.** Table 2 settles the *environment*
convention — `action_repeat=1` is RL-ViGen's Robosuite setting and every baseline on Door inherits
it, which `notes/DECISION-SHEET.md` already recorded and this reading confirms from the primary
source. It says nothing about whether IDAAC's own hyperparameters, tuned by its authors at action
repeat 4-8, transfer to repeat 1. That is a different question with the same words in it, and today's
null is exactly the kind of evidence that would tempt someone to answer it in one direction without
having tested it. See
[`idaac-2048-steps-was-chosen-under-action-repeat-8.md`](idaac-2048-steps-was-chosen-under-action-repeat-8.md).

## The acceptance criterion this gives the drqv2 validity check

`drqv2` is RL-ViGen-native and Figure 22 marks it as one of the two strongest on Robosuite. It is the
run that tells us whether a null on Door is the harness or the algorithm. Predefined, so it cannot be
adjusted after seeing the number:

- **Judge it on episode return, not success rate.**
- **The scale is now anchored at both ends**, which it was not when this criterion was first
  written:

  | reference | train-regime return | what it is |
  |---|---|---|
  | random policy | **≈ 2** | measured, `ppg` frame-0, 60 episodes |
  | `idaac` at 6e5 | **25-50** | an added baseline at faithful config, plateaued |
  | Figure 22 axis top | **500** | RL-ViGen's own plot for Door |

- **Non-degenerate (weakest bar):** clears random by a wide margin. `idaac` already does this at
  12-25x, so this alone proves nothing about `drqv2`.
- **Beats the plateau:** exceeds `idaac`'s 25-50 band and keeps rising past frame 51,200 — the point
  where `idaac` stopped improving. This is the informative comparison, because `drqv2` is
  RL-ViGen-native and Figure 22 marks it as one of the two strongest on Robosuite.
- **Harness validated:** reaches a substantial fraction of the 0-500 axis. *(Held loosely — that
  axis is the plot's range, not a published score. It bounds what Door returns can be, not what
  RL-ViGen achieved.)* **If `drqv2` also plateaus in the 25-50 band, the ceiling is the harness or
  the scene set, not the algorithm** —
  and that is the finding worth having before ten more baselines run. Two baselines from different
  families stopping at the same number is a much stronger signal than either alone.
- **A HARD threshold, added after this criterion was first written:** Door's reward is `1.0` on
  success and **otherwise** at most `0.25 + 0.25` per step, so over 500 steps **a policy that never
  opens the door cannot exceed return 250**, and **return > 250 proves at least one success step**.
  That converts "a substantial fraction of the axis" from a judgement into a test. See
  [`what-a-door-return-number-means.md`](what-a-door-return-number-means.md).
- **Comparability caveat:** RL-ViGen evaluates 10 episodes in each of its environments, 100 per
  level. Our grid is 20 episodes across 11 scene sets. Richer, but not the same denominator, so our
  numbers sit beside theirs rather than in their table.
