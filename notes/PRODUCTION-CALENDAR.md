# What the campaign actually costs, recomputed from measurements

Written 2026-09-05, replacing the envelope in [`CORRECTIONS.md`](CORRECTIONS.md) #12. That entry was
already corrected twice; **one of its terms is now measured and was wrong by 8x to 50x**, and the
evaluation half has changed shape since it was written (A20's trajectory grid did not exist).

## The four terms

| term | GPU-hours | basis |
|---|---|---|
| **training** | **601** | the schedule's per-baseline `solo_hours_per_seed_gt4_1`, x3 seeds. **Measured** for ten of twelve; alda and ctrl converted from gt4i.1 at x1.14 |
| **endpoint evaluation** | **96** | 36 cells x 800 episodes at 12 s/episode (measured, `bt1e81rq286p23d3l4l9`) |
| **trajectory evaluation** | **165** | **A20 DECIDED at 3 episodes/stamp, 2026-09-05.** [Recomputed 2026-09-07 by `plan_production.curve_eval_hours`, which now reads the resolved v100 descriptor and MEASURED per-episode wall-clock instead of a flat 12 s.] 325 is the upper bound: six of twelve baselines have no measured evaluation rate and carry `audit_job_budgets.UNMEASURED_DEFAULT = 30 s/episode`. Measured rates are 9 (`rlvigen`) and 25 (`idaac`). If the six unmeasured evaluate like `rlvigen`, the term is ~160. |
| **env construction** | **3.4** | 20,160 constructions at **0.6 s measured**, not the 28–168 h previously budgeted |
| **total** | **~876 GPU-h** | **37 days sequential on one GPU** |

With two-way packing where RAM allows: **~21 days**.

## Three caveats, none of which I will paper over

1. **These are T4-class (gt4.1) throughputs.** The production host is a V100, which is faster for
   this workload by a factor nobody has measured. The calendar above is therefore an **upper
   bound**, and a real V100 number would likely cut training substantially. **I am not going to
   guess the ratio** — twice this session I inferred a timing from wall-clock and was wrong twice.
   One 100k cell on the production host measures it.
2. **One GPU, not two.** `notes/remote-infra.txt` shows GPU 0 occupied by another user (15.1 GB,
   67%). If it frees, both halves roughly halve.
3. **Packing is RAM-bound, not GPU-bound.** drqv2 uses ~1.65 GiB of a 32 GiB V100, so the binding
   constraint is 113 GiB of host RAM against 40 GiB per RL-ViGen cell at the A14 default of 620k
   replay — two cells. At the rejected 1M it would be one, which is where that decision shows up in
   the calendar.

## What the trajectory decision costs, in days

| A20 depth | eval GPU-h | total GPU-h | sequential days | packed ~2x |
|---|---|---|---|---|
| none (endpoint only) | 96 | 700 | 29 | 15 |
| 3 episodes/stamp | 272 | 876 | 37 | 19 |
| **5 (superseded)** | 387 | 991 | 41 | 21 |
| 10 episodes/stamp | 675 | 1,279 | 53 | 27 |

So the curve costs about **six sequential days** over endpoint-only at the current default. That is
the number to weigh against "the first look at a learning curve happens after the campaign".

## The trajectory grid costs 27% of all training — and it lands very unevenly

Evaluation is **sequential with training**, not parallel: `run_one_cell` runs training, then
`retain`, then the curve, then the endpoint grid. So the hours add.

| baseline | train h/seed | trajectory h/cell | as % of training | s/episode (gt4.1 basis) | tier measured on |
|---|---|---|---|---|---|
| ctrl | 11.2 | 5.20 | 46% | 12 | gt4i.1 -> gt4.1 |
| svea | 16.7 | 4.77 | 29% | 11 | gt4i.1 -> gt4.1 |
| drq | 13.4 | 4.77 | 36% | 11 | gt4i.1 -> gt4.1 |
| sgqn | 25.6 | 4.77 | 19% | 11 | gt4i.1 -> gt4.1 |
| curl | 12.7 | 4.77 | 38% | 11 | gt4i.1 -> gt4.1 |
| alda | 19.1 | 4.77 | 25% | 11 | gt4i.1 -> gt4.1 |
| idaac | 4.8 | 4.77 | 99% | 11 | gt4.1 native |
| ppg | 5.9 | 4.77 | 81% | 11 | gt4.1 native |
| rad | 27.1 | 4.33 | 16% | 10 | gt4i.1 -> gt4.1 |
| soda | 51.3 | 4.33 | 8% | 10 | gt4i.1 -> gt4.1 |
| drqv2 | 6.4 | 3.90 | 61% | 9 | gt4i.1 -> gt4.1 |
| ibac_sni | 6.3 | 3.90 | 62% | 9 | gt4.1 native |

**Fleet: 601 GPU-h training against 165 GPU-h trajectory evaluation — 27% of training, on the
gt4.1 basis this whole document uses.** Endpoint evaluation and environment construction add
another ~99 GPU-h; they are not part of the trajectory-depth comparison.

**No family carries a placeholder any more.** An earlier pass reported 160-325 GPU-h because six of
twelve baselines had never had an evaluation episode timed and carried
`audit_job_budgets.UNMEASURED_DEFAULT = 30 s/episode`. They have now, at zero compute cost: the
v176 evaluator-validation wave already ran an endpoint grid per family at an identical scope
(2 regimes x 1 scene x 5 episodes = 10 episodes), and every job log carries its own
`NATIVE_ENDPOINT_EVAL_SECONDS`.

**Two corrections applied to that extraction before it was used**, both of which changed the number:

1. **The wave ran on two tiers**, not one — rlvigen, dmc_gb, alda and ctrl on `gt4i.1`, ppg,
   ibac_sni and idaac on `gt4.1`. Pooling the raw durations would have compared a faster second with
   a slower one. Every gt4i.1 duration is multiplied by the 1.14 factor this project measured on
   drqv2 (20.05 vs 17.53 fps) to reach the gt4.1 basis; the tier column above says which is which.
2. **These are T4-class, not V100.** The production host's evaluation factor is as unmeasured as its
   training factor. That is consistent with this document's own first caveat — everything here is
   T4-class and therefore an upper bound — and it is the step-2 measurement that will replace it.

On one basis every family lands between **8.9 and 11.3 s/episode**, against a placeholder of 30. The
placeholder was roughly 3x too high for all seven, which is the finding that survives the tier
correction. Regenerate with `plan_production.curve_eval_hours(600_000, 3)`.

**One caveat that no correction removes**: these are 10-episode grids over a single scene, while
production runs 800 episodes over ten. Per-episode cost should be equal or slightly lower there,
since environment construction amortises over more episodes — reasoning, not measurement, and the
canary checks it.

The unevenness is the point. The curve is a **fixed** grid per cell — 13 retained stamps x 120
episodes (4 regimes x 10 scenes x 3 episodes) = 1,560 evaluation episodes — while training cost
varies elevenfold across baselines. So **`idaac`'s curve costs more than twice its own training**,
and `soda`'s costs a quarter of its. The per-cell hours differ only through the per-episode rate,
which is why measuring the six unmeasured rates is worth more than any further modelling.

Corrected 2026-09-07: this section previously said "12 stamps x 240 episodes". The production grid
is 120 episodes per stamp, not 240, and the per-baseline table carried the superseded five-episode
hours. The uniform-grid choice is operationally set, while the owner-facing A20 record remains
ratifiable.

Three ways to respond, and this is really part of A20's historical reasoning:

1. **Accept it.** The curve is uniform across baselines, which keeps it comparable, and 64% of
   training for a full learning curve is not obviously bad.
2. **Scale depth by training cost** — fewer episodes per stamp for cheap families, so the curve is a
   bounded fraction (say <=50%) of each cell's training. Curves stay internally valid; cross-baseline
   curve noise becomes uneven, which is acceptable for a descriptive product.
3. **Fewer stamps for cheap families** — e.g. every 100k instead of 50k. Cheaper, but the stamp grid
   stops being shared, and comparing curves at common frames gets harder.

**It is trivially switchable either way**: `apply_production_settings` only sets a variable when it
is empty, so an explicit `CURVE_EVAL=0` in a job config wins over the production default. Turning
the curve off is one environment variable, per job, with no code change.


---

## Update 2026-09-05 — A20 is decided, and the headline totals change

The trajectory term was the campaign's one genuinely open number. It is now **3 episodes per stamp**
(DECISION-SHEET A20), taken once env construction was measured at **0.6 s** and the two-term
uncertainty collapsed into a single linear one.

| term | was (A20 undecided, costed at 5) | now (A20 = 3) |
|---|---|---|
| trajectory evaluation | 291 GPU-h | **176 GPU-h** |
| trajectory as a share of the 601 h training budget | **48%** | **29%** |
| campaign total | ~991 GPU-h | **~876 GPU-h** |
| packed wall-clock | ~21 days | **~18 days** |

**The "64% of all training" figure in the section above is superseded** — it was computed when the
curve was costed at 5 episodes per stamp. The *unevenness* it describes is unchanged and still the
point: the curve is a fixed cost per cell while training cost varies ~10x across baselines, so idaac
still pays proportionally far more for its curve than soda does. Only the magnitude moves.

Two numbers for one quantity is how this file could have drifted from the decision sheet, so: A20's
table gives **173 h** for episodes alone; this file gives **176 h** including the 3.4 h of env
construction. Same quantity, and the 3.4 h is the difference.
