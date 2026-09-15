# The first admissible full-length result — ppg, 600,064 frames, 2026-09-16

`results/records/reeval-v214-ppg-endpoint__records.jsonl`

```
88 rows          44 sample + 44 mode
frame            600064
regimes          train / eval-easy / eval-medium / eval-hard  (22 rows each)
scene sets       11  (scenes 0-9 plus the pooled set)
episodes         20 (80 rows) and 200 (8 rows)
checkpoint       a328e63e6ffa...   sha-verified against the banked run
revision         248751f7caca      = the LIVE ppg closure
ledger           paired=True, diagnostics_complete=True, populate exit=0
```

Plus `reeval-v214-ppg-curve__records.jsonl`: **264 rows across 6 stamps** (51,200 → 301,056), same
closure, `eval_scope=curve` at 3 episodes, one distinct checkpoint per stamp. The remaining stamps
are still sweeping.

## Why this is the first

Before today every row in `results/records/` was either superseded or attestation-scale. The fleet
export read **2,969 rows, 28 on the current closure**, and those 28 were 4 offline-eval rows per
family from a 10k-frame attestation with the curve deliberately disabled. Nothing measured an
algorithm; they measured that the instrument runs.

This row set measures ppg at production length on the closure that is live now, at the depth the
protocol specifies, across every regime and scene set. It cost **no training**: the weights came
from `card0-20260909-115331`, trained 2026-09-09, whose 14 checkpoints were sha-verified against
their own rows earlier in this session.

## The mistake that nearly cost it

The cell's log ends in `d-cell.sh: command not found`. I `scp`'d a new version of `reeval-ppg.sh`
over the file **while bash was executing it**. Bash reads a script incrementally by byte offset, so
replacing the file shifted the offsets and execution resumed mid-token, in the middle of
`launch-card-cell.sh`.

It cost nothing here only by luck of timing: the corruption hit the wrapper's epilogue after the
cell had finished and the archive had been written, which is why 88 complete rows exist. Had it
landed thirty minutes earlier it would have destroyed a seven-hour run.

**Rule: never write to a script that is running.** Deploy to a new name, or stop the process first.
The same applies to `rsync` over a live tree, which is how the file came to be replaced at all.


---

## The numbers, and the anomaly that is not one

Mean over the ten individual scenes, 20 episodes each, endpoint checkpoint:

| policy mode | train | eval-easy | eval-medium | eval-hard |
|---|---:|---:|---:|---:|
| `sample` (ppg's own rule) | 22.69 | 17.96 | **11.67** | 16.70 |
| `mode` (supplementary pass) | 42.86 | 38.89 | **33.94** | 40.58 |

Two things stand out and both are explained rather than assumed.

**eval-medium scores BELOW eval-hard, in both passes.** That is not a defect and not noise: the
regimes are not one ordered difficulty axis. `audit_eval_validity.py` records that `eval-medium`
alone sets **`except_robot=False`**, so it randomises the ROBOT'S OWN APPEARANCE, while eval-easy
and eval-hard perturb background, colour and lighting with the robot held fixed. A policy trained
on one robot appearance can reasonably find robot randomisation harder than a moving light. The
ordering in the names is not an ordering in the distributions.

**`mode` returns are roughly double `sample` returns.** This is the policy-mode split the project
already blocks comparisons on: ppg, idaac and ibac_sni report a SAMPLED return, the other nine a
mode return, and `comparison_blocks.py` refuses to rank across that boundary. This measurement is a
direct quantification of why -- for ppg on Door the same weights score 22.69 or 42.86 depending on
the action rule alone.

## Validity, checked with the project's own instrument on the new rows

`audit_eval_validity.py` on this file:

```
1. row summaries match their own raw episodes: PASS
2. episode ids unique and agreeing with their row: PASS  [1600 ids, 0 duplicated, 0 mismatched]
3. placement seed identical across regimes and frames: PASS
4. eval-easy 0% vary | eval-hard 6% | eval-medium 60% | train 1 of 200
```

The eval-medium rate of 60% reproduces the 62% measured on `card0-20260909-035152` in September --
an independent run, a different closure, the same property. That is the benchmark behaving as
documented.

**One new detail worth keeping:** `train` shows **1 of 200** slots varying, where the earlier
reference measured 0 of 200. Small, but train is supposed to be fully reproducible, so it is either
the evaluator nondeterminism measured earlier this session (~0.095 SE) surfacing in a reset
observation, or a single perturbed slot. Not chased further tonight; recorded so it is not
rediscovered as new.
