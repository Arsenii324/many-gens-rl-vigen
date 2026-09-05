# What the campaign actually costs, recomputed from measurements

Written 2026-09-05, replacing the envelope in [`CORRECTIONS.md`](CORRECTIONS.md) #12. That entry was
already corrected twice; **one of its terms is now measured and was wrong by 8x to 50x**, and the
evaluation half has changed shape since it was written (A20's trajectory grid did not exist).

## The four terms

| term | GPU-hours | basis |
|---|---|---|
| **training** | **601** | the schedule's per-baseline `solo_hours_per_seed_gt4_1`, x3 seeds. **Measured** for ten of twelve; alda and ctrl converted from gt4i.1 at x1.14 |
| **endpoint evaluation** | **96** | 36 cells x 800 episodes at 12 s/episode (measured, `bt1e81rq286p23d3l4l9`) |
| **trajectory evaluation** | **176** | **A20 DECIDED at 3 episodes/stamp, 2026-09-05.** Was 291 at 5, which is 48% of the training budget for a figure that carries no inferential claim. 579 at 10. |
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

## The trajectory grid costs 29% of all training — and it lands very unevenly

Evaluation is **sequential with training**, not parallel: `run_one_cell` runs training, then
`retain`, then the curve, then the endpoint grid. So the hours add.

| baseline | train h/seed | trajectory h/cell | trajectory as % of training |
|---|---|---|---|
| idaac | 4.8 | 8.08 | **169%** |
| ppg | 5.9 | 8.08 | **136%** |
| ibac_sni | 6.3 | 8.08 | **129%** |
| drqv2 | 6.4 | 8.08 | **126%** |
| ctrl | 11.2 | 8.08 | 72% |
| curl / drq / svea | 12.7-16.7 | 8.08 | 48-64% |
| alda / sgqn / rad | 19.1-27.1 | 8.08 | 30-42% |
| soda | 51.3 | 8.08 | **16%** |

**Fleet: 601 GPU-h training against 176 GPU-h trajectory evaluation — trajectory evaluation is 29%
of training.** Endpoint evaluation and environment construction add another ~99 GPU-h to the
campaign total; they are not part of the trajectory-depth comparison.

The unevenness is the point. The curve is a **fixed** cost per cell (12 stamps x 240 episodes), while
training cost varies elevenfold across baselines. So **the four cheapest baselines pay more for
their curve than for their training**, and soda pays 16%.

The 240-episode figure above is the current 3-episode setting (12 stamps x 4 regimes x 10 scenes x
3). The earlier 400-episode arithmetic belonged to the former five-episode setting and remains
only in the superseded table above. The uniform-grid choice is operationally set, while the
owner-facing A20 record remains ratifiable.

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
