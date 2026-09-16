# RESOLVED — the evaluator is slightly nondeterministic; the estimand did not change

**Status: RESOLVED 2026-09-15.** It blocked for about an hour and the block was correct to apply.
The conclusion reverses: the difference is evaluator noise, not a changed measurement, and my own
STOP condition was mis-specified -- it said "differs", where it should have said "differs beyond
evaluator noise". Comparing two numbers without first measuring the instrument's own spread is
exactly the error [[a-scale-is-not-a-result]] names.

## The measurement

Same weights, same episode seed, same everything the row records except the sweep breadth:

| | value | evaluator_revision |
|---|---|---|
| recorded 2026-09-09 | **26.099544954299926** | `184329928b51` |
| re-measured 2026-09-15 | **25.794515705108644** | `248751f7caca` |

Difference **-0.305, 1.17% relative**. `episode_return_sd` also moved, 14.257017218363774 ->
14.245690545714764, so the EPISODES differ, not just their mean. `checkpoint_sha256` is
`a328e63e6ffa96f8...` in both, so the weights are byte-identical.

Every `evaluator_scope` field matches -- `episode_seed=20260903`, `eval_policy_mode=sample`,
`eval_scope=endpoint`, `frame_stack=3`, `image_size=64`, `action_repeat=1`, `episode_length=500`,
`deterministic_setting={'backend':'torch','enabled':True,'mode':'torch.use_deterministic_algorithms'}`
-- **except two**, which record the INVOCATION rather than the row:

```
new: regimes=['train']                                      scenes=[0]
old: regimes=['train','eval-easy','eval-medium','eval-hard'] scenes=[0,...,9]
```

## What this refutes

It refutes my own claim, made earlier this session, that the ppg and idaac runs are "superseded by
re-hashing, not by a change of estimand". I reached that by reading three diffs and checking that
`eval_policy_mode` was `sample` then and now. The empirical test disagrees, which is exactly why it
was worth running instead of reasoning.

It also weakens the claim that a partial re-run is exactly valid. That claim rested on
`placement_condition_seed(eval_seed, scene_id, episode_index)` being content-addressed, which it
is -- but see below.

> **Correction, 2026-09-16, from a full-grid replicate:**
> [`results/evidence/evaluator-noise-full-grid-replicate-ppg`](../../results/evidence/evaluator-noise-full-grid-replicate-ppg/CLAIM.md).
>
> - **The comparison.** Two complete endpoint grids of this checkpoint came from one identical
>   invocation.
> - **`mode` rows diverge as often as `sample` rows**: 282/800 against 264/800 episodes identical,
>   with every placement seed identical. A `mode` row takes the Normal's mean and draws no sample.
> - **So the unseeded torch stream below is not what makes identical invocations differ.** It
>   still describes the code, and it can still make a narrow sweep differ from a full one.
> - **"The nine mode baselines ... are unaffected" does not follow.** ppg's own mode rows are
>   affected.
> - **eval-medium and eval-hard episodes never reproduce** (0/200). Only train and eval-easy
>   support row-level run-to-run comparison.

## The mechanism, as far as the code shows

`seed_episode_placement()` re-seeds **`random` and `np.random` only**:

```python
def seed_episode_placement(eval_seed, scene_id, episode_index):
    condition = placement_condition_seed(eval_seed, scene_id, episode_index)
    _random.seed(condition)
    np.random.seed(condition)
    return condition
```

**torch is not re-seeded there.** It is seeded once in the family setup
(`_torch.manual_seed(seed)`, `eval_grid.py:221`), whose own docstring says it is "called before the
env is constructed in every one". The placement RNG is numpy's -- "the half that decides the door"
-- and that half IS per-episode deterministic.

But ppg at `policy_mode=sample` draws its ACTIONS from torch (`PpoModel.act` -> `pd.sample()`), and
that stream is not re-seeded per episode. So for the three SAMPLING baselines -- `idaac`, `ppg`,
`ibac_sni` -- a row's value can depend on how much torch RNG was consumed before that cell.

**RETRACTED 2026-09-16, the sentence that used to end this paragraph.** It read: *"The nine mode
baselines take an argmax/mean and are unaffected."* That does not follow and the measurement
refutes it. Pairing all 88 endpoint rows across two completed runs of the SAME invocation
(peer session, bb191cd): MODE rows -- `pd.mean`, no sampling anywhere -- reproduce **282 of 800**
episodes, against **264 of 800** for sample. Near-identical. Whatever makes two identical runs
differ, action sampling is not it, and the nine mode baselines are **not** exempt.

The regime gradient is the informative part, and it points away from the policy entirely:

| regime | episodes reproduced (both modes) |
|---|---|
| train, eval-easy | 132-150 / 200 |
| eval-medium, eval-hard | **0 / 200** |

Placements are identical 40/40, so the divergence is downstream of placement. The code says why
that is possible. `eval_across_scenes.py:222-230`: `UniformRandomSampler` calls bare
`np.random.uniform` and draws from the GLOBAL numpy RNG, which `seed_episode_placement` re-seeds
every episode -- hence placements reproduce exactly. But the `seed` threaded through `robo_make`
reaches VGBWrapper's **`random_state`, "which drives texture/colour/lighting only -- a different
RNG object"**. That object is seeded once at construction and is **never re-seeded per episode**.
And the regimes that reproduce zero episodes are exactly the ones that randomise appearance:
`eval-medium` alone sets `except_robot=False`.

**What this does NOT license me to claim.** A once-seeded generator consumed identically would
still produce identical sequences, so `random_state` alone does not explain divergence between two
runs of the same invocation -- something must first perturb how many draws are taken. A plausible
candidate is GPU floating-point nondeterminism (cuDNN algorithm selection) producing a tiny action
difference that changes an episode's length and hence RNG consumption, with appearance
randomisation amplifying it; that is a hypothesis, not a measurement, and the honest state is that
**the mechanism is open**. What is settled is the negative: mode rows are affected too, at
essentially the same rate as sample rows.

The conclusion of this note is unchanged -- mean |diff| is 0.21 SE (mode) and 0.33 SE (sample), so
the reeval sits within evaluator noise. What changes is who is exposed: all twelve baselines, not
three.

## What is NOT yet established

- Whether the difference is RNG-consumption-by-breadth, or a genuine code change in the three
  commits that moved the revision (`84d3b85` no_grad, `31f8f80` row metadata, `0d4b0e1` episode ids).
- Whether the evaluator is deterministic given an IDENTICAL invocation. A repeat of the exact same
  narrow smoke is running to answer precisely this, and it is the cheapest discriminator:
  reproducing 25.794515705108644 exactly means deterministic-given-invocation, and the difference
  is then breadth or code; not reproducing it means something is nondeterministic.

## Why it matters beyond ppg

If a row's value depends on sweep breadth, then two things this project relies on need restating:

1. **Partial re-evaluation is not free.** Re-running a subset to fill gaps (e.g. idaac's 3 missing
   eval-hard mode rows) would produce rows not comparable with the 566 beside them.
2. **Curve and endpoint rows come from different invocations**, so even within one cell the curve's
   sampling baselines may not sit on the same RNG trajectory as the endpoint's.

Neither is established yet. Both are cheap to test and must be, before any sampling baseline's
numbers are reported.


---

## RESOLUTION — repeat the identical invocation, then put it in scale

A second run of the **byte-identical** invocation did not reproduce the first:

| run | value | sd |
|---|---|---|
| run 1, narrow sweep | 25.794515705108644 | 14.246 |
| run 2, narrow sweep, identical command | **26.052958893775940** | 14.390 |
| recorded 2026-09-09, full grid | 26.099544954299926 | 14.257 |

So the evaluator is **nondeterministic run to run**, despite every row recording
`deterministic_setting={'enabled': True, 'mode': 'torch.use_deterministic_algorithms'}`. That is a
real property and it is now documented rather than assumed away. It also means the test I designed
-- "reproduce the old number exactly" -- could never have passed, whatever the truth was.

**In scale, the effect is small:**

```
spread across the three runs : 0.3050
one standard error at n=20   : 3.1971      (sd 14.3 / sqrt 20)
spread as a fraction of 1 SE : 0.095
old vs mean(new)             : +0.176  =  0.055 SE
```

Run-to-run nondeterminism is about **a tenth of one standard error**, and old-vs-new is
**0.055 SE**. The values are statistically indistinguishable. **The estimand did not change.** The
earlier reading -- three commits touching `no_grad` execution, row metadata and episode ids, none
of them the measured quantity -- stands, and is now supported by measurement rather than by
reading diffs.

## What still follows from this

1. **A reported number cannot be reproduced bit-for-bit**, only within noise. Anything claiming
   exact reproduction of a sampling baseline's row is wrong. The three sampling baselines are
   `idaac`, `ppg`, `ibac_sni`; the nine mode baselines take an argmax/mean and were not tested here.
2. **Endpoint depth matters more than it looked.** At n=20 one SE is 3.2 on a mean of ~26, i.e.
   ~12%. The nondeterminism is negligible beside that, but the SE itself is not, and it is the
   reason `endpoint_eval_episodes=20` rather than 3.
3. **Partial re-evaluation is acceptable after all** -- not because rows reproduce exactly, but
   because they agree within a noise that is an order of magnitude below the reporting error. The
   breadth hypothesis (torch RNG not re-seeded per episode, `eval_grid.py:221` vs
   `seed_episode_placement`) remains TRUE as a description of the code, but is not needed to explain
   these numbers, and is not established as the cause.
4. **Unblocked**: the endpoint grid may run.
