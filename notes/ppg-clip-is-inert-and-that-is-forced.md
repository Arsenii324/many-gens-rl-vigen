# PPG's clip term is inert in our configuration, and a 32 GB card makes that unavoidable

**2026-09-10.** Answering "why do we not take multiple gradient steps per rollout?" — a fair
question, because the answer is not a preference and the honest version is a limitation.

## Gradient steps per rollout are pinned by both sources, not chosen

Steps per rollout = `n_epoch_pi × nminibatch`.

- **`n_epoch_pi = 1`** — PPG's released default (`train.py:33,170`), and §E's *PPG-specific* search
  independently reports **E_π = 1**. We pass no epoch flag, so we take the default. §E's shared grid
  says "10 ppo epochs", but the very next sentences carve PPG out: *"For PPG, we ran the same
  hyperparameter search as the one performed in the original paper for Procgen and found Nπ = 32,
  **Eπ = 1**, EV = 1, Eaux = 6, and βclone = 1 to be the best."*
- **`nminibatch ≤ num_envs = 1`** — `minibatch_optimize` splits the leading axis and
  `Roller.singles_to_multi` documents that axis as `(batch, time)`.

So **1 × 1 = one gradient step per 2048-frame rollout.** There is no room for more without
contradicting a cited value.

## That matches upstream on two axes and fails on a third

| | rollout | steps | samples/step | steps per env frame | clip active |
|---|---:|---:|---:|---:|:--:|
| PPG released, 1 rank | 16384 | 8 | 2048 | 0.00048828 | **yes** |
| ours | 2048 | 1 | **2048** | **0.00048828** | **no** |

**Density and per-step batch size are exact matches. The clip term is not.**

`runnable/ppg/phasic_policy_gradient/ppo.py:130-134` computes `ratio = exp(newlogp - logp)` where `newlogp` is recomputed from the
*current* model. With one epoch and one minibatch the model has not moved since collection, so
`ratio ≡ 1` exactly, `max(-adv·1, -adv·clamp(1, 1−ε, 1+ε))` is `-adv`, and the objective reduces to
the vanilla advantage-weighted policy gradient. Upstream's eight sequential minibatch steps drift
off-policy *within* a rollout, which is what makes its clip bind at all.

**This also explains `clipfrac = 0.000` and `approxkl = 1e-13` in our logs.** They are arithmetic,
not measurements — and, importantly, not evidence of a broken run. Reading them as symptoms is what
made this run look pathological for a day.

## Why we cannot have all three

Restoring an active clip needs `nminibatch ≥ 2`, hence `num_envs ≥ 2`. Holding upstream density
`nminibatch / segment = 8/16384` then forces the segment up. The auxiliary buffer is
`n_pi × segment` with **n_pi = 32** (PPG's own, §E-confirmed), and it is what sets VRAM:

| segment (`num_envs × nstep`) | nminibatch for 1× density | clip active | aux transitions |
|---:|---:|:--:|---:|
| 2048 (ours) | 1 | no | 65,536 |
| **16384 (upstream's own)** | **8** | **yes** | **524,288** |

Our 65,536-transition buffer peaks at **26,653 MiB of a 32,768 MiB V100 — 81 % of the card**,
measured on `card0-20260909-115331`. Upstream's segment is **8×** that. **PPG's own rollout geometry
does not fit on this hardware at n_pi = 32.**

So the three properties — upstream update density, upstream per-step batch size, active clipping —
are jointly unreachable here. We hold the first two and lose the third, and say so.

## What was rejected, and why

- **`num_envs=8, nstep=256, nminibatch=8`** (the pre-A36 configuration): clip active, but
  **8× upstream density** at 256 samples per step. Two deviations to remove one.
- **`num_envs=32, nstep=64, nminibatch=32`**: makes §E's literal "32 minibatches" run, but that
  rollout shape appears in **neither** PPG's released code nor §E. It would trade a false
  declaration for an unsourced geometry, and at 32× upstream density.
- **Reducing `n_pi` below 32** to fit a larger segment: `n_pi = 32` is a cited value from PPG's own
  search, reported in §E. Trading a cited constant for an uncited geometry is the wrong direction.

## What this costs the claim

`ppg`'s numbers are **PPG's optimisation budget, without PPO's trust region active**. Any statement
comparing `ppg` to `idaac` on this axis must carry that: `idaac` reads `clip_fraction` 0.83 on the
same one-process setting, because its lineage flattens `num_processes × num_steps` before splitting
and therefore gets 32 real minibatches from 2048 samples.

That asymmetry is a property of the two codebases' minibatching, not of the two algorithms, and it
is not removable at this scale. It belongs in the comparability discussion beside the policy-mode
split, not in a footnote.
