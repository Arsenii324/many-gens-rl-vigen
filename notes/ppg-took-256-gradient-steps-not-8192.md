# `ppg`'s policy took 256 gradient steps, not 8,192 — and the trainer said so 291 times

**2026-09-09**, from the live `ppg` production cell `card0-20260909-115331`. This supersedes the
"either the policy is not moving or the diagnostics are vacuous" dilemma left open in
[`ppg-and-idaac-fail-in-opposite-directions.md`](ppg-and-idaac-fail-in-opposite-directions.md).
**Both halves were true, for one reason.**

## The line

```
Warning: nminibatch > ntrain!! (32 > 1)
```

**291 occurrences** in `cells/ppg-s1/training.log` — once per iteration, from the beginning.

## What it means

`minibatch_optimize` (`runnable/ppg/phasic_policy_gradient/minibatch_optimize.py:53`) starts with

```python
ntrain = tu.batch_len(tensordict)
if nminibatch > ntrain:
    logger.log(f"Warning: nminibatch > ntrain!! ({nminibatch} > {ntrain})")
    nminibatch = ntrain
```

and `batch_len` returns the **batch dimension**, which for PPG is the **environment** axis. A segment
from `nstep=2048` with **one** environment has shape `[1, 2048, ...]`, so `ntrain = 1`.

The cell's `effective_config.json` requests `--nminibatch 32`. It got **1**. With PPG's
`n_epoch_pi = 1`, that is:

> **one gradient step per iteration — 256 policy updates across the whole 524,288-frame run, where
> the configuration asked for 8,192.**

## It also explains why nothing detected it

`clipfrac` was **exactly 0.000** for all 256 iterations and `approxkl` sat at **1e-13**. That is not a
policy failing to move; it is **arithmetic**. `compute_losses` measures the ratio against the `logp`
stored at rollout time, and with a single minibatch the measurement always happens *before* the only
step — so `ratio ≡ 1`, `logratio ≡ 0`, and the residual 1e-13 is float32 recompute noise.

**The two columns a reader would check to find this problem are the two columns the problem forces to
look perfect.** A healthy PPO run and this run are indistinguishable on `clipfrac` and `approxkl`
alone. The only surviving signal in the metrics was σ moving 1.000 → 1.006 over half a million
frames, which is easy to read as "the scale head is just stable".

The one instrument that *did* report it printed a warning 291 times into a log nobody grepped.

## The auxiliary phase is NOT affected, and that completes the account

`minibatch_gen`'s other branch (`minibatch_optimize.py:88`) takes `batch_size` instead of
`nminibatch`: `nminibatch = max(ntrain // batch_size, 1)`. The auxiliary phase runs over
`seg_buf` — **`n_pi = 32` stored segments** — with `aux_mbsize = 4`, so `ntrain = 32` and it gets
**8 minibatches**. It optimises normally.

So the run trained its **value and auxiliary heads properly and barely trained its policy**:

| head | minibatches per pass | evidence |
|---|---|---|
| value / auxiliary | 8 | `VFStats/EV` 0.011 → **0.81** |
| policy | **1** | σ 1.000 → 1.006, `clipfrac` 0.000 |

That asymmetry is exactly what the metrics showed and what made the run confusing: a critic that
plainly learns beside a policy that plainly does not. It is one defect, not two, and the split falls
precisely on which `minibatch_gen` branch each phase takes.

**Checked, not assumed.** `grep -rn 'nminibatch|num_mini_batch|mini_batch' runnable/` finds this
clamp **only** in `runnable/ppg/`. The declared constants in `families.json` make the difference
concrete:

| family | parallelism | rollout | requested minibatches | samples available to split | effective |
|---|---|---|---|---|---|
| `idaac` | `num_processes=1` | `num_steps=2048` | `num_mini_batch=32` | **2048** (flattened) | **32** |
| `ppg` | `num_envs=1` | `nstep=2048` | `nminibatch=32` | **1** (batch axis only) | **1** |
| `ctrl` | `num_envs=64` (v100) | — | — | 64 | fine |

`idaac` and `ibac_sni` share the `pytorch-a2c-ppo-acktr` lineage, which flattens
`num_processes × num_steps` before splitting — which is why `idaac` reads `clip_fraction` 0.83 on the
*same* one-process configuration that reduces `ppg` to a single update. `ctrl` is a separate JAX
implementation at 64 environments, and the remaining families are off-policy and replay-based.
**`ppg` is the only baseline of the twelve with this exposure**, and the two on-policy families still
to run are not affected.

## Why the configuration is not obviously wrong

`num_processes = 1` is a **fidelity** decision, sourced and deliberate: IDAAC's supplement specifies
"2048 steps, 1 process" and this project follows it
([`idaac-2048-steps-was-chosen-under-action-repeat-8.md`](idaac-2048-steps-was-chosen-under-action-repeat-8.md)).
`nminibatch = 32` is equally sourced, from the same paragraph.

**Each is right and together they cancel.** PPG was written for Procgen, where 64 parallel
environments make the batch axis the natural thing to split. Ported to a single physical
environment, its minibatching has nothing to divide, and the code degrades **silently and by
design** — with a warning rather than an error. Neither constant is wrong; the *interaction* is,
and no fidelity table has a row for interactions.

**`idaac` is not affected.** Its lineage (`pytorch-a2c-ppo-acktr-gail`) minibatches over
`num_processes × num_steps` flattened, so one process still yields 2048 samples to split — which is
why its `clip_fraction` reads 0.83 rather than 0.

## What this does and does not settle about the run

**Settles:** why the policy barely moved, why σ is frozen, and why the diagnostics looked clean. The
run is a faithful execution of its configuration and a **severe under-optimisation** of PPG.

**Does not settle:** what `ppg` would do with the intended 32 minibatches, or the reward-scale
question — `EpRewMean` 28.3 against `EpLenMean × FrameRewMean` = 8.3 is still unresolved and the
offline curve is still its arbiter.

## The decision on the running cell: let it finish

It is 92% through training; the expensive half is already paid. Its evaluation is the arbiter for the
reward-scale question and produces the first `ppg` rows on the raw axis. Killing a production cell to
save evaluation time is the impatience this project's runbook exists to prevent, and the result is
now **explained rather than mysterious**, which is what makes it worth keeping.

**It must be labelled.** Any `ppg` number from this cell describes a policy that received 1/32 of its
configured updates.

## Fixed forward

`scripts/audit_training_diagnostics.py` now scans for trainer warnings about the trainer's own
optimisation and reports them **above** the range checks, with the reasoning that a warning outranks
a range: the ranges describe how an optimiser behaved, this says it did not run the optimisation
configured. It fires on the live log at `x291`.

**Open for the owner, with my recommendation.** The next `ppg` cell should either raise
`num_processes` so the batch axis can be split, or use a PPG build that minibatches over the
flattened `batch × time` axis as `idaac`'s lineage does. **I recommend the second**: it preserves the
sourced `1 process` and the sourced `32 minibatches` simultaneously, changes no hyperparameter, and
makes the executed optimisation match the one the authors described. Raising `num_processes` would
silently change the on-policy update density, which
[`FINDING-on-policy-update-density.md`](FINDING-on-policy-update-density.md) already flags as its own
comparability axis.

---

# The fix is specified here and deliberately NOT applied yet

I would normally implement this rather than describe it. **A hard constraint says otherwise, and it
is the project's own:**

```
FAMILY_RUNTIME_MEMBERS['ppg'] = ('runnable/ppg/phasic_policy_gradient',
                                 'runnable/ppg/phasic_policy_gradient/train.py', ...)
ppg evaluator revision = 184329928b51da31de8e314b87db805154f823dbd0edfec1c533ed9d7ea49a2c
```

`minibatch_optimize.py` lives inside a **family runtime member**, so editing it **moves ppg's
evaluator revision**. The ppg cell is 92% through training with ten hours of evaluation ahead of it,
and `populate_evaluator_ledger.py` refuses a record whose revision is not the live one — by
assertion, deliberately. **Editing this file now would make a twelve-hour cell uncollectable.** The
standing rule is explicit: while a wave runs, nothing under `runnable/` is touched, comment bytes
included.

So: **apply it after the ppg cell is collected and its revision retired**, not before.

## The change

`minibatch_gen` splits `th.randperm(ntrain)` where `ntrain` is the batch axis. For a non-recurrent
model the batch and time axes are interchangeable for optimisation purposes, and `idaac`'s lineage
already flattens them. The fix is to make the policy phase split over `batch × time` rather than
`batch` alone.

**It is not a one-line clamp removal.** Removing the clamp without flattening gives
`th.chunk(th.randperm(1), 32)`, which yields one chunk — the same behaviour with the warning gone,
which is strictly worse because the only instrument that reported the problem would fall silent.

The safe form flattens the leading two axes before splitting, and must keep `state_in` and `first`
consistent. PPG as configured here is non-recurrent (`state_in` is empty), so the flatten is sound —
**and that condition must be asserted in the code rather than assumed**, because a future recurrent
configuration would be silently corrupted by it.

## Acceptance, predefined

A short cell after the change must show **all three**, and any one of them alone is insufficient:

1. **`Warning: nminibatch > ntrain!!` no longer appears.** Necessary, not sufficient — removing the
   clamp alone achieves this while changing nothing.
2. **`Opt/clipfrac` is non-zero and in 0.1-0.3**, and **`Opt/approxkl` is around 0.01-0.05.** This is
   the real test: it means the ratio is being measured against a policy that has actually moved.
3. **`nminibatch` reported as 32**, matching `effective_config.json`.

Then re-run `ppg` at 600k. **The current cell is a diagnostic, not a data point for PPG** — it
measures a policy that received 1/32 of its configured updates, and no comparison against the other
eleven baselines may include it. The battery is twelve baselines **plus one re-run**.

---

# Independent confirmation on the return axis, 2026-09-09 16:12

The evidence above is all from the optimiser's own diagnostics. The curve evaluation now supplies a
second, unrelated line of evidence, and it agrees.

`scripts/learning_over_random.py` on the live `ppg` curve, first two stamps:

| regime | floor (frame 0) | frame 51,200 | ratio |
|---|---|---|---|
| train | 2.24 | **4.68** | **2.1x** |
| eval-easy | 1.98 | **4.47** | **2.3x** |

**`ppg` is learning — it moved off its floor.** But `idaac` at the *same* frame count reached
**24.66** on the train regime, roughly 11x its floor.

The update counts at frame 51,200 explain the difference directly:

| | iterations | updates per iteration | **policy updates at 51,200** |
|---|---|---|---|
| `idaac` | 25 | 10 epochs x 32 minibatches | **8,000** |
| `ppg` | 25 | 1 epoch x **1** minibatch (clamped from 32) | **25** |

**320x fewer updates, and about 5x less return.** The two lines of evidence are independent — one is
`clipfrac`/`approxkl`/σ from inside the optimiser, the other is offline evaluation of checkpoints on
the benchmark's own axis — and they point the same way.

**The caveat, and it is not small.** `idaac` and `ppg` are different algorithms with different
networks; their returns at a shared frame count are **not** an algorithm comparison, and
`scripts/comparison_blocks.py` would refuse to rank them. What the number supports is narrower and
sufficient: **`ppg`'s optimisation is throttled**, which the log said, the diagnostics said, and the
return now says too.

**What to watch as the curve completes.** `ppg` will have had **293 policy updates** by 600k. If its
return keeps climbing to the end rather than flattening, the run is update-limited rather than
converged — which would mean the re-run after the minibatch fix should be expected to go
substantially higher, not merely to look tidier.

## Refinement: the clamp changes the KIND of update, not only the count

The curve at three stamps, train regime, against `idaac` at the same frames:

| frame | `ppg` | `idaac` | `ppg` policy updates so far |
|---|---|---|---|
| 0 | 2.24 | — | 0 |
| 51,200 | 4.68 | 24.66 | 25 |
| 100,352 | **10.05** | 12.21 | **49** |

**`ppg` is still climbing and accelerating** — roughly doubling per stamp — which answers the
question this note left open: the run is **update-limited, not converged**, so the re-run after the
fix should be expected to go materially higher rather than merely look tidier.

**But it reaches 10.05 on 49 updates where `idaac` reaches 12.21 on roughly 15,700**, and that
forces a correction to how I framed the defect above. "320x fewer updates" is arithmetically true
and misleading as an account of the damage:

> `nminibatch` clamped to 1 does not delete 31 of 32 updates. It replaces **32 minibatch steps of
> 64 samples each** with **one full-batch step over all 2,048** — far fewer steps, but each one a
> much lower-variance gradient estimate.

So the clamp trades step count for gradient quality, and PPG's auxiliary phase — which is
**unaffected**, getting its 8 minibatches over 32 stored segments — keeps fitting the value function
throughout. That combination is why the run learns respectably instead of collapsing, and it is the
honest reason the diagnostics looked calm rather than broken.

**What this does not change:** the executed optimisation is still not the configured one, `clipfrac`
and `approxkl` are still structurally uninformative at one minibatch, and the run still cannot be
compared with the other eleven as a representative of PPG.

**What it does change:** I should not predict the size of the improvement from the fix. Thirty-two
noisy steps are not simply thirty-two times one clean step, and claiming they are would be the same
error as reading an axis as a result. The prediction that stands is directional — more steps per
batch, `clipfrac` in 0.1-0.3, `approxkl` near 0.01-0.05 — and the magnitude is what the re-run is
for.

*(These are different algorithms with different networks; the `idaac` column is context for update
counts, not an algorithm comparison. `scripts/comparison_blocks.py` would refuse to rank them.)*
