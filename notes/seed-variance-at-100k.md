# Between-seed variance, measured — and what it says about a 3-seed campaign

Job `bt1ik7krfpjeftl65s3b` (DataSphere, `vigen-drqv2-seedvar-v202`), drqv2 at 100k frames,
production seeds 101/102/103, `NATIVE_HOST_PROFILE=datasphere` explicit. Settled SUCCESS
2026-09-08 ~15:22 MSK. This is the measurement OWNER gate 4 was waiting on.

## The numbers, from the endpoint grid that `results/records/` actually reports

| regime | s101 | s102 | s103 | mean | sd | cv | 95% CI (t₂) |
|---|---:|---:|---:|---:|---:|---:|---|
| train | 44.25 | 85.29 | 73.61 | 67.72 | 21.15 | 0.31 | [15.18, 120.25] |
| eval-easy | 8.01 | 12.68 | 3.73 | 8.14 | 4.48 | 0.55 | **[−2.98, 19.26]** |

**The eval-easy interval includes zero.** With n=3 and t₂ = 4.303, a coefficient of variation of
0.55 puts the 95% half-width at 11.1 on a mean of 8.14. At this budget, three seeds cannot
distinguish drqv2's eval-easy performance from nothing at all — never mind distinguishing it from
another baseline.

## The caveat, stated before anyone acts on the number

**This is 100k, and production is 600k.** drqv2 at 100k is nowhere near converged — its own
training curve is still climbing steeply and its seeds are at 196.63 / 484.52 / 471.07, a 2.5×
spread. Between-seed variance in RL usually shrinks as runs converge, so this is best read as an
**upper bound on the noise**, not as the production figure.

It is also the *only* measurement of between-seed variance this project has. Treating an
unmeasured hope that "600k will be tighter" as though it were evidence is the failure mode this
whole workspace is organised against. So: the honest position is that 3 seeds is **unproven, not
refuted**, and the cheapest thing that would settle it is one more seed-variance cell at the
production budget on the family that is cheapest to run — not on drqv2.

**This is an owner decision.** More seeds multiply the campaign's cost linearly (36 cells → 48 at
4 seeds, 60 at 5), and the disk model is per-cell. It is not mine to widen.

## Second finding: the checkpoint-reproduction defect reproduces across every seed

The same checkpoints, scored two ways at the same frame:

| seed | training curve | endpoint grid | ratio |
|---|---:|---:|---:|
| 101 | 196.63 | 44.25 | 4.44× |
| 102 | 484.52 | 85.29 | 5.68× |
| 103 | 471.07 | 73.61 | 6.40× |

A stamped checkpoint evaluates **4.4×–6.4× below what its own run logged**, in the same direction,
in the same magnitude band, across three independent seeds. This project had recorded the defect
from single observations and had excluded every offline explanation; what was missing was whether
it was systematic. It is.

Three seeds agreeing this closely rules out a per-run accident. It does not identify the cause —
the two live candidates remain the exploration-noise difference between a logged training episode
and a mode-policy evaluation, and an actual reload discrepancy. The first would be *expected* and
benign; the second would invalidate every reported endpoint. **Nothing here separates them**, and
the separation is cheap: score one checkpoint with the sampling policy instead of the mode, and
see whether the ratio collapses. That is worth doing before the fleet runs, not after.
