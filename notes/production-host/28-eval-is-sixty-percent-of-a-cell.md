# Evaluation is 60% of a cell, and the expensive half is the part that is hardest to read

Measured on the first complete production cell, `card0-20260909-035152` (`idaac-s101`, 600k frames),
2026-09-09. Every number below is from the job log, not a projection.

## The breakdown

| phase | wall time | what it produced |
|---|---|---|
| training | **4.95 h** | 600,064 frames, 12 checkpoints |
| curve evaluation | **4.60 h** | 11 stamps x 44 rows x **3 episodes** = 1,452 episodes |
| endpoint evaluation | **2.76 h** | 44 rows x **20 episodes** = 880 episodes |
| **cell total** | **12.3 h** | |

The eleven curve stamps took 1480, 1483, 1472, 1472, 1484, 1505, 1473, 1520, 1567, 1533, 1567
seconds — remarkably flat, including the stamps that ran while `ppg` shared the card. **Evaluation
is 7.36 h against training's 4.95 h: 60% of the cell.**

Both evaluation phases cost the same per episode — **11.4 s/episode** for the curve, 11.2 s/episode
for the endpoint. Episode count is the only lever; the split between curve and endpoint is not.

Training ran at **33.7 frames/s**, matching the 33.2 env steps/s measured earlier by a different
route.

## The curve costs more than the endpoint and says less

The curve spends **4.60 h** to produce points of **3 episodes** each. With a per-row standard
deviation of 15-20, a 3-episode point has a standard error near 10 — larger than most of the
differences the curve is drawn to show. Only the regime aggregate (44 rows, 132 episodes per stamp)
and the trend across stamps carry weight; **an individual curve point is not a level and must not be
read as one.**

The endpoint spends **2.76 h**, 40% less, and produces the 20-episode rows that are actually
readable. RL-ViGen's own Robosuite protocol is 10 evaluations per environment (supplement §B).

**A better split exists, and it is cheaper.** Curve stamps do not need all four regimes at all eleven
scene sets: `train` and `eval-easy` at four scene sets, 10 episodes each, over the same eleven
stamps is **880 episodes = 2.76 h** — it saves **1.84 h per cell** *and* raises each point from 3
episodes to 10. Across twelve baselines that is **22 GPU-hours**, for a curve that can be read.

## The decision, and it is to change nothing now

**Do not touch `CURVE_EVAL_*` for this battery.** `idaac` and `ppg` have run under the current
protocol. Changing it mid-campaign means the remaining ten are measured differently from the first
two, and restoring comparability means re-evaluating those two — 2 x 7.36 h — against a saving of
22 h. The net is positive on paper and negative in practice: this project's core claim is that its
numbers sit on one axis, and a protocol that changed halfway through is exactly the defect
`scripts/comparison_blocks.py` exists to refuse. **22 GPU-hours is not worth a seam in the axis.**

Recorded here for the *next* campaign, where it costs nothing to adopt.

## Deferring evaluation is feasible, and it is the real throughput lever

The plan asks whether evaluation can run in parallel with training given that training is VRAM-bound
and evaluation compute-bound. The measurements say yes, and better than that:

- **Evaluation is already independent.** It runs *outside* `CELL_TIMEOUT_SECONDS`, from checkpoints
  on disk, in a fresh process. Nothing about it requires the trainer to be alive.
- **VRAM is not the obstacle.** Evaluation runs under a 4096 MiB cap and `idaac` training held
  2,644 MiB; a 32 GiB card fits both several times over.
- **Disk is not the obstacle either, for evaluation specifically.** Records are small and the
  checkpoints already exist. Evaluation adds essentially nothing to the footprint that
  [`27-disk-not-vram-is-what-caps-parallelism.md`](27-disk-not-vram-is-what-caps-parallelism.md)
  shows to be the binding constraint.

So the shape that raises throughput most is **train-only cells, then a separate evaluation wave over
the retained checkpoints**. Twelve trainings cost 59 h instead of 148 h, the card is never idle
waiting on a single-threaded evaluator, and the evaluation wave can be packed against a *training*
cell of the next baseline rather than against nothing.

**What this requires that is not yet proven:** an evaluation wave reads checkpoints that a previous
cell wrote, and this project has never run one that way on this host. The in-cell path has now run
end to end; the standalone path has not. That is one cheap experiment — evaluate `idaac-s101`'s
retained checkpoints from a fresh cell and check the rows match the ones it already produced — and
it should happen before the shape is adopted, not after.
