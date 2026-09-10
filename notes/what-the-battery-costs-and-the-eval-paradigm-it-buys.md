# What the battery costs, and the eval paradigm that buys it

**2026-09-10.** Written because the question *"did you select the proper eval compute and paradigm
with respect to the whole plan, end to end?"* had no answer in this repo. The depth and cadence were
chosen in [`retention-and-eval-depth.md`](retention-and-eval-depth.md) against a **DataSphere**
job-hour budget. Nobody re-derived them against the **V100 host**, where the constraint is card-days
on a shared machine rather than billed hours.

## The measurement that changes the shape

Measured to completion on the `idaac` 600k cell (`launch-card-cell.sh`'s own arithmetic):

| phase | hours | what it is |
|---|---:|---|
| training | 4.95 | 600,000 frames |
| curve evaluation | 4.60 | 11 stamps × 44 rows × 3 episodes = 1,452 episodes |
| endpoint grid | 5.52 | 44 rows × 20 episodes × **two policy-mode passes** |
| **evaluation total** | **10.12** | **2.04× the training it follows** |

**Evaluation is the majority of the campaign, not its tail.** At 11.3 s/episode — the same constant
covers both phases (11.4 curve, 11.2 endpoint) — the per-cell arithmetic is:

    endpoint, one pass : 44 rows × 20 ep = 880 ep = 2.76 h
    curve, 3 episodes  : 11 × 44 × 3     = 1452 ep = 4.56 h

## The decision — REVERSED the same day, before it was implemented

**Keep the supplementary `mode` endpoint pass. Keep curve at 3 episodes and endpoint at 20.
Change nothing.**

> **The first version of this note said to drop the `mode` pass, and it was wrong.** I costed it
> from `idaac`'s training time and concluded 2.76 h per affected cell was worth removing.
> `family.py:702` had already costed it, more accurately, and accepted it:
>
> > *"Cost as actually scoped: THREE baselines x three seeds x ~2.4 h = **~21.6 GPU-h against a
> > campaign near 893, about 2.4%** -- not the ~3.2% the four-family figure implies."*
>
> **2.4 % of the campaign**, decided deliberately, against a scientific need I was discounting: two
> of A25's three fixed cross-group pairs **straddle the policy-mode split** (`SAME-AXES-VERDICT.md`),
> so a cross-group number built from native passes alone confounds the mechanism with the action
> rule. Dropping the pass does not save a meaningful fraction of the campaign and does damage the
> comparison the campaign exists to make.
>
> And all three of my fragility arguments were fixed **today**, hours before I made them: the
> `no_grad` defect that killed the pass, the supplementary-failure path that let it destroy a
> complete native grid, and the early mode-path probe that surfaces such a defect at the first curve
> stamp. Arguing to remove a pass because it is fragile, on the day its fragility was repaired, is
> reasoning from a stale premise.
>
> Left visible rather than deleted, because the arithmetic below is still the thing this note exists
> to record, and because "existing code was right and I nearly overrode it" is the finding.

`ENDPOINT_EVAL_POLICY_MODES` defaults to `native,mode`, which runs the **whole 44-row grid twice**
for the three sampling families (`idaac`, `ppg`, `ibac_sni`). The four reasons I gave for dropping
it, and why each fails:

1. **It is not the reported estimand.** `family_eval_policy_mode` makes *sampled* native for those
   three; `mode` exists for A25's cross-group pairs. Every headline number comes from the native
   pass.
2. **It is recoverable at zero training cost.** Checkpoints are retained, and
   `sha256(snapshot.pt)` provably matches the `checkpoint_sha256` on the rows — so a later
   `mode` pass is commensurable with the native one by construction. This is precisely what
   `retention-and-eval-depth.md` argues retention is *for*.
3. **It is the fragile path.** It is what died on `card0-20260909-115331`, taking a complete 44-row
   native grid with it until the supplementary-failure fix landed.
4. **It costs 2.76 h per affected cell**, and the affected cells are three baselines × three seeds.

Curve depth is **not** where to economise, despite being the larger line. `retention-and-eval-depth.md`
§1 argues the opposite and is right: *"intermediate points carry shape; the endpoint carries the
number"*, and shape at 1 episode on a task whose per-episode SD is comparable to its mean is noise,
not a cheaper curve. Endpoint depth is what every reported interval rests on.

## The campaign total, so the number exists somewhere

At `idaac`'s training time for every family — a **floor**, since a 6e5 `soda` cell is projected at
45 h — twelve baselines × three seeds:

| paradigm | GPU-h | card-days |
|---|---:|---:|
| **as currently configured (`native,mode`) — kept** | **467** | **19.4** |
| native only (rejected: 2.4 % saved, A25 pairs confounded) | 442 | 18.4 |
| native only, curve at 1 episode (rejected: shape becomes noise) | 332 | 13.8 |

The project's own campaign figure, using per-family training times, is **~893 GPU-h ≈ 37 card-days
on one card.** That is the number that matters for scheduling, and it is why the supplementary pass
is not free.

## What is deliberately NOT changed

- **Not** the 50k stamp grid, the four regimes, the ten scenes, or the 20 endpoint episodes.
- **Not** parallel evaluation. It would improve utilisation but not GPU-hours, and it needs a
  process-count signal the yield watch deliberately does not use — see below.
- **Not** card 1. It is not ours to take.

## Why parallel evaluation does not need a yield signal, and where one would be needed

`yield_gpu_to_neighbour.py` has two triggers. The **armed** one is memory (`--floor-mib`, 4000 via
the launcher): it measures the harm — free VRAM below a floor — and is therefore indifferent to how
many processes are ours. The **process-count** trigger (`--yield-on-processes`) is **off by
default**, and its own help says why: *"our own cells start many interpreters (24 in one packed 600k
run), so the count of 'our' processes is not knowable from the cell list and a count-based trigger
yields to itself."*

So a dynamic own-count breaks the count trigger and cannot break the memory trigger. Parallel
evaluation would add processes of ours; that only matters if it actually starves the card, and then
yielding is correct. A cell-written count file would be required **only** if process-yield were
enabled alongside parallel evaluation — which is not the configuration this fleet runs.
