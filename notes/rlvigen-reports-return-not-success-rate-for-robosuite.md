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
and any direction helps; they prevent the refinement that comes after. Against Figure 22's 0-500
axis it is still under 10% of the plotted range, so the gap to RL-ViGen's own algorithms is real.

*(One caveat on the baseline: it is `ppg`'s initialisation, not `idaac`'s. A randomly initialised
policy's return on a dense-reward manipulation task is set by the environment far more than by the
network, so ~2 is a fair reference — but it is one architecture's random init measured once, and a
per-family frame-0 row would settle it properly. Every family's curve now evaluates its own frame-0
checkpoint, so this costs nothing to check as the battery runs.)*

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
- **Non-degenerate:** the train curve rises above its own first stamp by more than a few standard
  errors and *stays* there — the property `idaac` lacks, having returned to its starting value.
- **Harness validated:** train return at 6e5 reaches a substantial fraction of Figure 22's 0-500
  axis. A `drqv2` run that also ends where it started points at the harness or the scene set, not at
  the algorithm, and that is the finding worth having before eleven more baselines are run.
- **Comparability caveat:** RL-ViGen evaluates 10 episodes in each of its environments, 100 per
  level. Our grid is 20 episodes across 11 scene sets. Richer, but not the same denominator, so our
  numbers sit beside theirs rather than in their table.
