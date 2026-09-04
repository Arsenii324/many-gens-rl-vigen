# 04 — What a stock `action_repeat=2` run would actually change, and what to do

**Written 2026-08-25. Dated snapshot, not a living document.** Derived from the code paths cited;
no run at `action_repeat=2` was performed, so everything here is structural inference, flagged as
such.

## Correcting a plausible-sounding but wrong reading

It is natural to say that `action_repeat=2` would mean "half the environment steps per frame, so
episodes end at a different point in the task." **That is wrong**, and the reason matters.

`train.py:134-135`:

```python
@property
def global_frame(self):
    return self.global_step * self.cfg.action_repeat
```

A *frame* is defined as an environment step. So a `num_train_frames` budget buys the **same number
of environment steps at any repeat value**. And `horizon: 500` (`envs/robosuiteVGB/cfg/robo_config.yaml:24`)
is enforced by a TimeLimit wrapper *inside* `_robo_make_env`, i.e. underneath
`ActionRepeatWrapper` — so an episode is 500 environment steps either way, and
`ActionRepeatWrapper.step()` breaks early on `time_step.last()` (`wrappers/dmc.py:51-52`).

## What actually changes, and what does not

For a fixed `num_train_frames` on Door:

| quantity | `action_repeat=1` (ours) | `action_repeat=2` (shipped) | changes? |
|---|---|---|---|
| environment steps per episode | 500 | 500 | **no** |
| environment steps per frame budget | N | N | **no** |
| episode return scale | sum over 500 env steps | sum over 500 env steps | **no** |
| shaping ceiling ([C62](../../CONSTRUCTION.md#c62)) | **250** | **250** | **no** |
| **agent decisions per episode** | **500** | **250** | **halved** |
| **gradient updates per frame budget** | N/2 | **N/4** | **halved** |
| control granularity | per env step | action held 2 steps | coarser |

The reward invariance holds because `ActionRepeatWrapper` **accumulates** (`reward += ...`,
`wrappers/dmc.py:49`) rather than sampling — the same 500 per-step rewards are summed, only
regrouped.

**So the 250 shaping ceiling and every return number's scale survive a repeat change.** What does
not survive is the learning budget: at repeat 2, the same frame count buys **half the gradient
updates** (compounded by `update_every_steps: 2`, `cfgs/config.yaml:46`) and half the decisions.
Given [C68](../../CONSTRUCTION.md#c68) (snapshots only at 50k multiples) and the finding that most
cells never solve Door at 50k, halving the updates at a fixed budget is the change most likely to
matter here.

## The detection gap this leaves

**`episode_length` in the logs cannot detect a repeat change.** `train.py:264` logs
`episode_length = step * action_repeat / episode`, which reads **500.0 at either value** — 500×1 or
250×2. So the one field a reader would instinctively check to confirm the x-axis is invariant to the
thing they are checking for.

Combined with the fact that `Protocol` declares `DEFAULT_ACTION_REPEAT = 1` but the runners never
consult it, a stock run's grids would look ordinary. The guard added on 2026-08-24 —
`tests/test_x_axis_invariant.py::test_every_archived_grid_was_measured_at_action_repeat_1` — closes
this at the point a wrong value would enter a reported number, and is currently the only thing that
would catch it.

## Recommendation for the main thread

1. **Keep `action_repeat=1`.** It is the value RL-ViGen's own paper specifies for Robosuite
   (Supplementary Table 2), it is the only value four of the twelve baselines can express, and the
   shipped `2` is a DMC-inherited "otherwise" the benchmark's authors already overrode for this
   domain. No change needed.

2. **Correct `INTEGRATION-DELTA.md`:489.** `rad`/`soda` do not get 1 "explicitly" — the flag is
   passed and never read. The count in that entry's conclusion should be **five of twelve by
   decision**, not seven. See [03](03-the-twelve-audit.md).

3. **Decide the paper-vs-shipped rule explicitly, and decide [C64](../../CONSTRUCTION.md#c64) under
   it rather than on its own.** The project currently resolves this class of conflict two different
   ways in the same launcher — paper for `action_repeat`, shipped for `feature_dim` and SGQN's
   `aux_lr`. Whichever rule is chosen, C64 is an instance of it, and the inconsistency is more
   reportable than either individual choice. See [02](02-paper-vs-shipped.md).

4. **Consider recording the three "inert knob" cases as one finding.** `rad`/`soda`
   (`wrappers.py:36`), `alda` (`alda_trainer.py:152`) and — from a different direction —
   `idaac`/`ctrl`/`ibac_sni`/`ppg` all present a configuration surface that does not reach the
   robosuite path. The `rad`/`soda` case is new as of this audit; the `alda` one is already in
   `INTEGRATION-DELTA.md`. A knob that reads as configured and is dead is worse than an absent one,
   because it invites tuning that silently does nothing.

## What was not done

No run at `action_repeat=2` was executed, so the "halved gradient updates" consequence is inferred
from the code, not measured. If it is ever worth measuring, the cheap version is a short paired run
at 1 and 2 on the same seed comparing `train/critic_loss` counts — not a full cell.
