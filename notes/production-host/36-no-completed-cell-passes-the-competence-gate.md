# 36 — Every completed cell fails the competence gate, and that decides what this campaign can report

**2026-09-18, 06:30 MSK.** Found while building `scripts/production_reading.py` — the headline
reading path that `results_table.py` had been pointing at for weeks without it existing.

## The measurement

Train-regime endpoint results for every production cell this project holds, aggregated as
`docs/EVAL-PROTOCOL.md` §4c requires (episodes → ten scenes → one number per trained policy):

| baseline | seed | estimand | train Ȳ | train success |
|---|---|---|---|---|
| `ibac_sni` | 101 | mode | 75.81 | **0.000** |
| `ibac_sni` | 101 | sample | 82.18 | **0.005** |
| `idaac` | 101 | mode | 32.91 | **0.000** |
| `idaac` | 101 | sample | 39.24 | **0.000** |
| `idaac` | 102 | mode | 29.58 | **0.000** |
| `idaac` | 102 | sample | 20.51 | **0.005** |
| `ppg` | 1 | sample | 22.69 | **0.000** |
| `drqv2` | 2 | mode | 96.21 | 0.270 |

The random-policy floor is **1.842** (C55), so every return is far above chance. The success
column is the problem: at 600,000 frames on Door, **these policies essentially never open the
door.** They have learned the shaped reward — approach, reach, grasp — and stop there. The
`drqv2` row is not a counterexample: it is an older, shorter, exploratory cell at a different
budget and protocol, kept in the table only because it is the one row with real successes.

## What follows, under this project's own rules

`docs/EVAL-PROTOCOL.md` §3 — the competence gate — says a baseline receives a retention *ratio*
only if its train-regime denominator clears the floor **and** its train-regime success is
non-zero; `regime_retention_report.py` sharpened "non-zero" to `MIN_DENOM_SUCCESS = 0.25` after an
adversarial re-check found a policy scoring 1/20 per scene producing a retention of 0.947 that was
a shaped-reward plateau. **All six production cells fail that gate**, so
`production_reading.py --retention` prints `DID NOT REACH COMPETENCE` for each and no ratio at all.

That is the intended behaviour, not a gap. A method that never solves the task has a gap of
approximately zero between regimes *because there is nothing to lose*, and a ratio computed there
reads as robustness. The returns remain published; only the ratio is withheld.

## Why this matters more than any single number

**The campaign's headline question is retention.** As of today, no completed cell can answer it,
and adding more seeds of the same three baselines at the same budget will not change that — it
will produce three more shaped-reward plateaus with tighter error bars. Note 35's plan (finish the
sampled-estimand block) still gives the first honest *seed-spread* result, and it is still the
cheapest thing to run, but it should be understood as answering **"how variable is this measure"**
rather than **"which method generalises better"**.

## What I would check before drawing any conclusion from this

Three explanations, none excluded, in the order I would test them:

1. **The budget is too small for Door — CHECKED, and the curve does not support it.** The
   retained stamps answer this without spending anything, so I read them (train regime, per-stamp
   mean over scenes):

   | stamps | return at first → last stamp | success across the whole curve |
   |---|---|---|
   | `ibac_sni` s101, 12 | 15.15 → 79.36 | 0.000, except 0.033 at two stamps |
   | `ibac_sni` s102, 7 | 20.74 → 92.25 | 0.000 throughout |
   | `idaac` s101, 11 | 24.96 → 24.54, noisy | 0.000, except 0.033 at one stamp |
   | `idaac` s102, 11 | 1.20 → 10.99 | 0.000 throughout |
   | `ppg` s1, 12 | 4.68 → 20.53 | 0.000, except 0.067 and 0.033 at two stamps |

   **Shaped return climbs; success does not move.** `ibac_sni` more than quintuples its return
   across training and still opens the door in 0 of 30 episodes at almost every stamp. That is the
   signature of a policy optimising the shaping term, not of one approaching a solution it would
   reach with more frames.

   Resolution caveat, stated because it bounds the claim: curve stamps use 3 episodes per scene
   (30 per stamp), so the smallest visible non-zero rate is 0.033; the endpoint uses 20 per scene
   (200), where `ibac_sni` s101 shows 0.005 — one success in two hundred. So "essentially never"
   means **at most about half a percent**, measured, not zero proven.
2. **The estimand.** Every one of these is an on-policy method reported at `sample`, and sampled
   actions on a precision task lose more than they do on Procgen. The `mode` columns are also near
   zero, so this cannot be the whole story, but it is measurable per cell.
3. **The reward and horizon convention.** Our returns (20–96) sit an order of magnitude above
   RL-ViGen's own published `drqv2` Door numbers (≈3.6, range 1–7, in the anchor note), and our
   protocol runs `action_repeat=1` where their config ships 2. A shaped per-step reward over a
   500-step horizon scales with the number of steps taken, so the two are probably not the same
   axis at all. **This needs resolving before any of our numbers is compared with a published
   one** — it is exactly the "a scale is not a result" trap, and the anchor gate assumes the two
   are comparable.

## One measurement defect found while doing this, and fixed

`idaac` s101 carries **two** sets of endpoint rows for the same checkpoint — the in-cell grid and a
later offline re-evaluation sweep. Averaging a flat list of rows would have weighted those scenes
twice in Ȳ. `production_reading.py` now averages *within a scene* first, so a repeated measurement
is a better estimate of that scene rather than an extra scene. The numbers did not move (the two
measurements agree closely), which is itself worth knowing: the offline re-evaluation reproduces
the in-cell grid.

## Status

This note records a measurement and a consequence, not a decision. The owner decides whether the
campaign continues at 600k, extends the budget for a subset, or reports the shaped-reward plateau
as the result — which would be a legitimate finding about the benchmark at this budget, provided
it is stated as that and not as a generalisation ranking.

Reproduce with:

    python scripts/production_reading.py --retention
