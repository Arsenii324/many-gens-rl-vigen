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
