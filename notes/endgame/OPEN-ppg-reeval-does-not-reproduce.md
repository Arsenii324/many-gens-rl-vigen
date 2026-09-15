# OPEN — re-evaluating ppg's 600k checkpoint does not reproduce its recorded value

**Status: OPEN. Nothing else should run until this is understood.** That rule is from this
session's own plan, written before the result was known.

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
`ibac_sni` -- a row's value can depend on how much torch RNG was consumed before that cell, i.e. on
the breadth and order of the sweep. The nine mode baselines take an argmax/mean and are unaffected.

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
