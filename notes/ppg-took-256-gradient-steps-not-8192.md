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
