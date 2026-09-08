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

## RETRACTED: the "checkpoint-reproduction defect reproduces across every seed"

**An earlier version of this file claimed the defect reproduced on all three seeds at 4.44× /
5.68× / 6.40×. That claim was wrong and is withdrawn.** It compared the training curve on
**scene 0** against the endpoint grid **aggregated over scenes 0–9**. Those are different
populations, so the ratio measured a scene difference and attributed it to a reload.

Like for like — scene 0 against scene 0, at the same frame:

| | s101 | s102 | s103 | mean |
|---|---:|---:|---:|---:|
| training curve, scene 0, noisy policy, 1 episode | 196.63 | 484.52 | 471.07 | 384.07 |
| endpoint grid, scene 0, mode policy, 20 episodes | 180.23 | 426.44 | 455.88 | 354.18 |

**1.08×**, with the mode policy slightly *lower* — a small gap in the direction one would expect
from a single noisy episode versus a 20-episode mode average. **This run gives no evidence of a
reload discrepancy at all.** The project's original observation (131.5 vs 13.85) is untouched by
this: it is neither reproduced nor refuted here, because this job did not test it.

Two things made the error easy to make and are worth naming, since the next reader will meet both.
The curve row and the grid rows share a `frame` and a `regime` and differ only in `scene_set`,
`episodes` and `phase` — and the frame arrives as `100000.0` from the curve and `100000` from the
grid, so a naive grouping key silently merges them. My aggregation kept whichever row it saw last.
An analysis script that groups records **must** key on `scene_set` and `phase`, not on frame and
regime alone.

## What the scene-0-versus-the-rest gap actually shows, which is a result

Within the **train regime**, mode policy, 20 episodes per scene:

| scene | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean return | **354.18** | 9.73 | 112.61 | 6.86 | 37.06 | 69.14 | 17.20 | 3.42 | 13.52 | 53.45 |

Scene 0 is the scene the agent trained on. It scores **354.18** there and **35.89** averaged over
scenes 1–9 — a **9.9× gap inside the nominally in-distribution regime**. The reported train figure
of 67.72 is the 200-episode aggregate over all ten, so it is dominated by the nine the agent never
saw.

This is not a defect; it is the benchmark measuring what it exists to measure. But it does mean
**"train regime" is not "training performance"**, and a report that presents the aggregate as the
in-distribution number while the agent trained on one tenth of it would be misleading. Whether the
production grid should separate the training scene from the other nine — or whether training
should sample the whole train scene set — is a design question this measurement raises and does
not answer.
