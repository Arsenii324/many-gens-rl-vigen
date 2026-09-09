# Getting to a reportable battery in the fewest runs

**2026-09-09.** Every number here is measured on `card0-20260909-035152` or read from a vendored
source. The goal it serves: **spend as few runs as possible before every remaining run is production
grade.**

## The blocking constraint nobody had costed: seeds

RL-ViGen's own reporting standard, from the main paper (§ Provision of Raw Scores):

> To record the **stratified bootstrapped confidence interval** for each algorithm, it is vital to
> provide the **raw scores for each seed** instead of simply offering aggregated scores.

**We have one seed per baseline.** A single seed cannot produce a seed-level interval, so no amount
of additional evaluation on the runs we have makes them reportable to that standard. This is the one
gap that *requires* GPU time rather than analysis.

## What a seeded battery costs, from measured components

Components: **train 4.95 h**, **curve 4.60 h**, **endpoint 2.76 h per policy mode**. Three families
(`idaac`, `ppg`, `ibac_sni`) take a second endpoint pass; nine take one.

| plan | GPU-hours | days on one card | cells |
|---|---:|---:|---:|
| 1 seed, exactly as run today | 156 | 6.5 | 12 |
| 3 seeds, as run today | 468 | 19.5 | 36 |
| 3 seeds, lean curve | 402 | 16.7 | 36 |
| **3 seeds, lean curve, curve on seed 1 only** | **336** | **14.0** | **36** |
| 5 seeds, same shape | 537 | 22.4 | 60 |

Two savings, both already justified elsewhere:

- **Lean curve** (`production-host/28`): `train` + `eval-easy` at four scene sets, ten episodes,
  same eleven stamps — **cheaper AND more readable** than the current four regimes x ten scenes x
  three episodes, whose points are too thin to read individually.
- **Curve on seed 1 only.** The curve exists to show training dynamics; the confidence interval needs
  endpoints. Seeds 2 and 3 need train + endpoint, not a second and third trajectory.

**Recommendation: 3 seeds, lean curve on seed 1 only — 336 h.** Five seeds buys a tighter interval
for another 200 h, and 14 days of a shared booked card is already at the edge. The formal choice is
the owner's; this is the plan I would run.

## The ordering that makes it "fewest runs"

**Everything below must land before cell 1 of the battery**, or the battery inherits a defect and
some of its 36 cells have to be repeated. As of tonight a `ppg` re-run is already owed for exactly
this reason.

### Step 1 — collect `ppg` (in progress, ~01:20)
Nothing that moves an evaluator revision may be touched until its records are installed.

### Step 2 — one revision bump carrying three changes
Landing these separately costs three re-attestations of seven families; together, one.

| change | defect it closes | member |
|---|---|---|
| episode id gains `eval_scope` + `eval_policy_mode` | 760 of 2,120 ids collide, all reporting different returns | `scripts/eval_grid.py` (CODE) |
| `ppg` `nminibatch` — assert like `idaac` does | executed config was not the declared one, silently | `runnable/ppg/…` (FAMILY_RUNTIME) |
| write a frame-0 checkpoint | no family has a measured random floor, so "did it learn" is a judgement | family runtimes |

### Step 3 — re-attest, then verify on one short cell
`production_gates.py` back to 7/7, then a single short cell checked with
`scripts/audit_eval_validity.py --strict`: ids unique, summaries self-consistent, placement paired.
**One cheap cell, not a battery, is what proves the fixes.**

### Step 4 — the `drqv2` validity check, still first
Hard criterion, unchanged: Door's reward is 1.0 on success and at most 0.25+0.25 otherwise, so over
500 steps **a policy that never opens the door cannot exceed 250, and above 250 proves a success
step**. If `drqv2` lands near 34 with SR 0.000 beside `idaac`, the ceiling is the harness or the task
configuration, not either algorithm — and that changes what the whole battery is worth running for.

### Step 5 — the battery, 36 cells
With `record_host_run.py` at launch and `collect-host-run.sh` at the end, both now refusing to
overwrite.

## What is already fixed and needs no run to prove

`run_probe.sh` is in no evaluator member set, so the terminal-checkpoint stamp
(`snapshot_<frame>.pt`) is live now: endpoint frame provenance goes from **0 corroborated to all of
them**, verified on the real records by adding the alias and re-auditing.

## What no amount of running fixes, and must be reported as a limitation

`eval-medium` and `eval-hard` **resample their visual perturbation between passes** — 62 % and 10 %
of slots respectively, against 0 % for `train` and `eval-easy`. That is RL-ViGen's design, not a bug,
but it means **no paired claim is available for those regimes**, and their numbers carry perturbation
variance on top of episode variance. Seeds do not fix it; only more episodes narrow it.
