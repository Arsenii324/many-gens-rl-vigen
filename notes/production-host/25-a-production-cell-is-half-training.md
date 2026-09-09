# 25 — A production cell is about half training and half evaluation

**2026-09-09, measured on the `idaac:101` 600k cell.** Every cost estimate this project carries is a
*training* estimate. The production settings add an evaluation phase of comparable size, and nothing
said so before this run.

## The measurement

| phase | cost |
|---|---|
| training to the endpoint (598016 frames) | **~5 h** (03:52 → ~08:50, ~2000-2500 frames/min) |
| offline curve eval | **~4.5 h** — 11 retained checkpoints x **1478 s each** (1480, 1483, 1472 observed) |
| endpoint grid | additional; 4 regimes x 10 scenes x 20 episodes x 2 policy modes |

So a "600k cell" is roughly a **10-hour** job, not a 5-hour one. `notes/DECISION-SHEET.md` quotes
7.5 h for `idaac` at production length; that figure is the training half.

## Where the eval cost comes from

`run_curve_eval` (run_probe.sh ~1067) loops over **every retained checkpoint** and runs the full
grid on each:

```
--regimes ${CURVE_EVAL_REGIMES}   --scenes ${CURVE_EVAL_SCENES:-0}   --episodes ${CURVE_EVAL_EPISODES:-3}
```

and the production freeze sets `CURVE_EVAL_SCENES=0,1,2,3,4,5,6,7,8,9` — all ten certified scenes,
where a non-production cell would use one. With `SAVE_EVERY_FRAMES=50000` over 598016 frames that is
11 checkpoints, and 11 x 10 scenes is where the 4.5 hours goes. Each pass writes 44 records.

**This is a deliberate design, not an accident.** `preserve_snapshots` and the ten-scene grid exist
so a retention curve can be computed from real evaluations rather than interpolated. The cost is
the price of that, and it is fine — but it has to be *in the plan*, and it was not.

## What follows

- **Budget ~10 h per production cell, not ~5.** Four cells is roughly two days of card time, not
  one. The queue in note 21 should be read with that arithmetic.
- **`CELL_TIMEOUT_SECONDS` must cover both halves.** 43200 s (12 h) covers this cell with about two
  hours to spare. A timeout sized from a training estimate alone would have killed it during
  evaluation, after all the training was done — the worst possible place.
- **The eval phase is the cheapest thing to shorten if throughput matters.** `CURVE_EVAL_EPISODES`,
  the scene count, and `SAVE_EVERY_FRAMES` (which sets how many checkpoints exist to evaluate) each
  scale it linearly. All three are production-frozen, so changing any is an owner decision, not an
  operator one.
- **It also changes the yield calculus** (note 24). A cell yielded during evaluation loses the
  evaluation but keeps its checkpoints — those are durable and can be evaluated later offline. A
  cell yielded during *training* loses the training outright, because `idaac` and `ppg` cannot
  resume. So the second half of a cell is far less exposed than the first.
