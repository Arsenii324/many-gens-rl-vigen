# IDAAC did not fail to learn Door mysteriously. It shows a textbook PPO trust-region blowout.

**2026-09-09**, from the first complete production cell: `card0-20260909-035152`, `idaac-s101`,
598,016 frames, `progress-robosuite:Door-idaac-s101.csv` (26 rows).

## The measurement

| steps | approx_kl_k3 | clip_fraction | dist_entropy | sigma_mean | train reward (normalised) | order_acc |
|---|---|---|---|---|---|---|
| 2,048 | 0.027 | 0.316 | 9.92 | 0.996 | 1.51 | 0.410 |
| 100,352 | 0.506 | 0.800 | 8.10 | 0.769 | 40.7 | 0.358 |
| 296,960 | 1.095 | 0.831 | 3.98 | 0.424 | 64.4 | 0.377 |
| 444,416 | 1.455 | 0.828 | 0.405 | 0.255 | 70.0 | 0.383 |
| 542,720 | 0.725 | 0.822 | −1.75 | 0.188 | 50.1 | 0.438 |

**Every one of these is outside the range a healthy PPO run occupies.**

- **`approx_kl_k3` reaches 1.0-1.5 nats.** PPO targets roughly 0.01-0.05; implementations that early-stop
  on KL use 0.015 as the trigger. This is **20-100x** the intended step size, sustained from 100k on.
- **`clip_fraction` saturates at 0.80-0.84** by 100k, from 0.32 at the first update. Four of five
  samples sit on the clipping boundary, so most of the batch contributes a flat objective and the
  gradient is dominated by the clip edge rather than by the advantage.
- **`dist_entropy` falls 9.92 → −1.75**, monotonically. This is entirely the policy standard
  deviation collapsing: for a 7-DoF diagonal Gaussian, entropy is `7 × (½ln(2πe) + ln σ)`, which at
  σ=0.996 gives **9.93** and at σ=0.188 gives **−1.77**. Measured 9.92 and −1.75. The two columns are
  the same fact, and nothing resists the collapse — IDAAC's tuned entropy coefficient is **0.0**.

The value function is fine (`value_loss` 0.45 → 0.01-0.03), so this is not a critic failure.
**`order_acc` sits at 0.34-0.44 for the whole run**, never departing from chance, so IDAAC's order
classifier — the auxiliary task the method is named for — is not learning either.

## What the returns do

Training reward rises **1.5 → 70** and then falls back to **50**. That is real progress inside the
training loop, and it is on the **normalised** scale (`REWARD_NORMALIZATION` marks `idaac` as
normalising training reward), so it is not comparable to the records, which report raw return
regardless. On the raw evaluation axis the curve wanders 12-50 across eleven stamps and ends where it
began — see
[`rlvigen-reports-return-not-success-rate-for-robosuite.md`](rlvigen-reports-return-not-success-rate-for-robosuite.md).

So the run is not inert. It improves, then degrades, with a policy collapsing toward determinism
while its updates are far outside the trust region — the shape of a run that is over-updating.

**Measured against random, later the same day:** `ppg`'s frame-0 checkpoint — a randomly initialised
policy under the same evaluator — returns **2.24 train / 1.98 eval-easy** over 60 episodes per
regime. `idaac`'s 24.7-50.3 is therefore **12-25x random**, and essentially all of that gain arrives
by frame 51,200. **This is a plateau after fast early learning, not an inert run**, which is exactly
what an over-large update step produces: rapid progress while any direction helps, then no
refinement.

## The mechanism this is consistent with, stated as inference and not as a finding

[`idaac-2048-steps-was-chosen-under-action-repeat-8.md`](idaac-2048-steps-was-chosen-under-action-repeat-8.md)
recorded that IDAAC's `2048 steps, 1 process` and its **10 PPO epochs per update** were selected on
Cartpole Swingup, Cartpole Balance and Ball In Cup at **action repeat 4-8**, and that Door runs at
**action repeat 1**, so one rollout covers 4-8x less simulated time than the authors' did. That note
was careful to claim nothing was wrong, only that the condition was unwritten.

**These diagnostics are what that condition mismatch would predict.** Ten epochs of reuse over 2048
samples, with entropy coefficient 0.0, on a 7-DoF manipulator with a 500-step horizon, is a far more
aggressive update per unit of simulated experience than the same numbers were on a 5-dimensional
cartpole at repeat 8. A KL of 1.0+ and a clip fraction of 0.83 are the signature.

**This is not proof of cause.** The measurement is that the run is over-updating; the attribution to
action repeat is an inference from one run with no arm holding it fixed. Two other explanations are
live and are not excluded here: continuous-control PPO on manipulation may simply need a smaller step
than IDAAC's Procgen/DMC-tuned settings whatever the repeat, and the σ collapse could be
self-reinforcing once entropy has gone (a narrow policy makes larger ratio excursions for the same
parameter change).

## What would discriminate it, predefined

Each is one cell at the same 600k budget, judged on the diagnostics rather than on return, so a null
on reward does not make them uninformative:

1. **PPO epochs 10 → 3.** The single cheapest intervention and the one that directly reduces reuse
   per batch. **Predicts:** `clip_fraction` below 0.5 and `approx_kl_k3` below 0.2. If the KL stays
   above 1.0 with 3 epochs, the step size is not coming from epoch count and the action-repeat story
   weakens sharply.
2. **A KL early-stop at 0.05**, breaking the epoch loop when exceeded. Diagnostic rather than
   faithful — it tells us how many epochs the data actually supports before the trust region is
   left, which is the number the authors' setting was implicitly buying.
3. **Entropy coefficient 0.0 → 0.001**, from IDAAC's own grid (the paper searched
   `[0.0, 0.01, 0.001, 0.0001]` and chose 0.0 *for those tasks*). **Predicts:** σ stays above ~0.4.
   This one is inside the authors' searched space, so it is the least invasive as fidelity.

**None of these should become the default on the strength of this note.** They are arms. The
faithful configuration is the one that ran, and it stays the reference — what changes is that we now
know *how* it fails, which is the thing a second run needs in order to be worth its GPU time.

## Why this matters beyond IDAAC

`ppg` and `ctrl` are also on-policy, also carry Procgen-tuned constants, and `ppg` is running now.
**Its log should be read for the same three columns before its curve is interpreted.** If `ppg`
shows the same signature, the finding is about transferring Procgen/DMC PPO settings to a physical
manipulator, not about IDAAC — and that is a materially more useful thing to know before the
remaining ten baselines run.

---

# This run IS the validation `families.json` was waiting on

`datasphere/native/families.json`, `idaac.constants_note`, declares the IDAAC-C2 recipe — including
**`ppo_epoch: 10`** — and says of it, verbatim:

> **NOT YET VALIDATED by a full-length training run**: the partial C1 pilot (`frame_stack=1`,
> `ppo_epoch=3`, `bt1djeamji7gilgnndft`) tested part of this recipe and showed **substantially higher
> raw returns than the old defaults** without yet reaching competence at a short budget … consistent
> with this direction, not proof of it. This is this project's best technical default (Q55) …
> **a full-length competence run is the separate, not-yet-spent validation this default is waiting on**.

**`card0-20260909-035152` is that run.** 600,064 frames, full C2 recipe, and it is now spent. What it
returns:

- **The recipe learns.** Train return reaches **33.69** at the endpoint over 400 episodes, roughly
  **17x** a random policy. That is not a failed default.
- **It does not reach competence.** Success rate is **0.000** across all 880 endpoint episodes, and
  the curve plateaus after frame 51,200 — almost all the learning happens in the first 8% of the
  budget.
- **The optimiser is far outside its trust region for the whole run**: `approx_kl_k3` 1.0-1.5 nats
  against PPO's 0.01-0.05, `clip_fraction` saturated at 0.82, σ collapsing 0.996 → 0.188 with
  `entropy_coef` 0.0.

So the declared default is **validated as learning and not validated as competent**, and the
diagnostics say *why* rather than leaving it a mystery. That is a materially better outcome than
either "it worked" or "it failed".

## What this does to the proposed 3-epoch arm

The arm I proposed — `ppo_epoch` 10 → 3, everything else held — is **not** a repeat of
`bt1djeamji7gilgnndft`. That pilot ran `frame_stack=1` on a short budget under the **C1** recipe and
was judged on returns. Mine holds the full **C2** recipe at `frame_stack=3` and 600k, and is judged
on **diagnostics**: does `clip_fraction` fall below 0.5 and `approx_kl_k3` below 0.2.

But the pilot is real evidence in the same direction and should be cited rather than rediscovered: it
already showed `ppo_epoch=3` giving **substantially higher raw returns** than the then-defaults.
Two independent hints now point at epoch count.

**It needs no hashed-tree change.** `NATIVE_EXTRA_OVERRIDES` is a declared escape hatch
(`run_probe.sh:398`) that appends to argv and is recorded in `effective_config.json`, so the arm runs
as a separate cell without moving `families.json` or any evaluator revision:

```bash
NATIVE_EXTRA_OVERRIDES="--ppo_epoch 3"   # everything else the faithful C2 recipe
```

**The faithful default stays `ppo_epoch: 10`.** The arm is a diagnostic, not a proposal to retune, and
whether 10 should change is an owner decision that a single arm does not settle.
