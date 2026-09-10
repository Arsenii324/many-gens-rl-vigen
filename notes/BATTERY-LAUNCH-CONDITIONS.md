# What the battery is, what it costs, and the four constraints that shape it

**2026-09-10.** The pre-flight for the production battery, written from measurement rather than
intent. Everything here is checkable and most of it corrects a number this repo already published.

## The shape

36 cells: **12 baselines × 3 seeds (101, 102, 103) × 600,000 frames**, from
`production-schedule-v100.json`.

## The cost, corrected

`production-schedule.json` published `job_hours: 530.5` and
`wall_clock_days_at_two_parallel_jobs: 11.1`. **Both were training only** — `row["job_hours"]` is
`frames / fps` and nothing else. `curve_eval_hours` existed, was correct, and had no callers; the
endpoint grid was not modelled at all.

| | hours | note |
|---|---:|---|
| training | 530.5 | what was published as the whole campaign |
| curve evaluation | 165.1 | 12 stamps × 4 regimes × 10 scenes × 3 episodes |
| endpoint evaluation | 105.3 | 4 × 10 × 20 episodes, **×2 passes** for the three sampling families |
| **campaign** | **800.9** | **33.4 card-days on one card, 16.7 at two parallel jobs** |

Evaluation is **34 %** of the fleet campaign — and on a fast-training family far more: the one
`idaac` 600k cell measured to completion was 4.95 h training against **10.12 h evaluation**.

## Constraint 1 — the VRAM cap is not a safety property, and never was

`notes/production-host/26` established it and it is **still true**: all **nine** family launchers
overwrite `PYTHONPATH` without preserving it, so the cap module never reaches the trainer.
`NATIVE_VRAM_CAP_APPLIED` is printed by our *monitors*. ppg reached **26,653 MiB under a 10,240
cap**.

I set `NATIVE_VRAM_CAP_MIB` on today's attestation cells and should not have described it as
protection. What actually protected them is `yield_gpu_to_neighbour.py`'s **free-memory floor**
(`--floor-mib 4000`, armed by `launch-card-cell.sh`), which is external, cooperative, sees render
buffers and other tenants, and cannot fail late from fragmentation.

**Fixing the nine launchers is a hashed-tree edit — `runnable/_launch/*` are payload members — and
note 26 rules it an owner decision.** It buys predictability, not safety. Not done here.

## Constraint 2 — `ppg` is a whole-card job

**26,653 MiB of 32,494** at its auxiliary phase. It cannot be packed with anything. Schedule it
alone, and do not co-schedule any cell against the remaining ~5.8 GiB.

## Constraint 3 — card 1 is not ours

Card 0 only, one cell at a time, every cell through `launch-card-cell.sh` so the exclusivity, yield
and disk watches are armed and sized. `--yield-on-processes` stays **off**: our own cells start many
interpreters (24 in one packed 600k run), so a count trigger yields to itself. The memory floor is
the armed one and is indifferent to how many processes are ours.

At one cell at a time on one card, **33.4 days**. That is the honest wall-clock, and it is the
scheduling fact the campaign turns on.

## Constraint 4 — evaluation is now watched, and the reaper no longer kills blind

Both fixed today, and both mattered for a 45-hour cell:

- the yield poller and `cell-active` marker were released when **training** ended, leaving the
  evaluation phase — 2.04× longer — unwatched and unable to yield. They now span the whole cell.
- the container reaper was `sleep $WATCH_SECONDS; docker stop`. A cell one minute from writing its
  delivery died like a hung one. It now grants bounded grace while the container is still emitting
  and stops a silent one immediately.

## Preconditions, in order

1. **7/7 evaluator families attested on the current closure.** In progress: idaac and ppg done,
   alda running, ibac_sni/ctrl/svea/soda chained. Nothing launched before this is reportable,
   because records on a superseded revision are what `populate_evaluator_ledger.py` refuses.
2. **Places365 train corpus on the host** — 26 GB. Only the 1000-image attestation fixture is
   there. Blocks `svea`, `sgqn`, `soda` production cells, not attestation.
3. **A frame-0 row per family** would give each result its own initialised-network floor. Not
   blocking: C55's random-**action** floor (1.842) already applies and survives the closure change,
   because `probe_floor.py` never reads the observation.
