# Both endpoint grids against the random floor — and the floor was already in the repo

**2026-09-10.** [`two-endpoint-grids-and-the-unit-of-variation.md`](two-endpoint-grids-and-the-unit-of-variation.md)
§2 said *"whether 33.69 is above random remains unanswerable"*. **That was wrong**, and correcting
it costs no run.

It was right about one thing and wrong about the other. `scripts/learning_over_random.py` does
report the floor as unknown, correctly — it wants a **frame-0 row of the same family**, an
evaluation of that family's own initialised network, and neither family has one. But that is not
the only floor this project has. `scripts/rlvigen_reference.py:87` carries a canonical **random-action**
floor for Door, C55, measured by `scripts/probe_floor.py --episodes 200`:

    mean 1.842   sd 2.839   95% CI [1.511, 2.271]   max 28.755

Two different negative controls answering two different questions — *"what does an untrained
network do?"* and *"what does acting at random do?"* — and only the first was missing.

## Why this floor survives the closure difference, which policy results do not

The endpoint rows were produced under an evaluator revision that has since moved. Normally that
forbids the comparison. Here it does not, for a reason that can be stated exactly rather than
waved at: `probe_floor.py:110` is

    a = rng.uniform(-1.0, 1.0, size=np.shape(env.action_space.sample()))

**The random policy never reads the observation.** So it is invariant to every axis whose change
moved the revision — frame stack, image size, crop policy, and the sampled-versus-mode action rule.
It is sensitive to the task, the horizon, the reward and the placement distribution, and none of
those has moved: Door, horizon 500, same reward, and `placement_condition_seed` omits the regime by
construction.

The same argument makes **one floor serve all four regimes**: a blind policy cannot tell them
apart. The regimes differ visually and only visually.

## The comparison

| cell | regime | mean | × floor | z vs floor sd | episodes ≤ floor 95% hi | episodes > floor max |
|---|---|---:|---:|---:|---:|---:|
| idaac-s101 | train | 33.69 | **18.3×** | 11.2 | 0.0 % | 50.5 % |
| | eval-easy | 31.58 | 17.1× | 10.5 | 1.0 % | 40.0 % |
| | eval-medium | 11.55 | 6.3× | 3.4 | 3.5 % | 4.0 % |
| | eval-hard | 18.47 | 10.0× | 5.9 | **11.0 %** | 21.0 % |
| ppg-s1 | train | 22.74 | **12.3×** | 7.4 | 0.0 % | 26.0 % |
| | eval-easy | 17.98 | 9.8× | 5.7 | 0.5 % | 13.5 % |
| | eval-medium | 11.34 | 6.2× | 3.3 | 3.0 % | 3.5 % |
| | eval-hard | 17.38 | 9.4× | 5.5 | 0.5 % | 14.0 % |

n = 200 episodes per regime, per cell. `z` is in units of the floor's own dispersion (2.839), not
the trained policy's.

**Both policies are well above chance in every regime** — 6.2× to 18.3×, and not one training
episode of either fell at or below the floor's 95% upper bound. With zero task successes anywhere,
that is a precise statement: *both learned to accumulate shaping reward — reaching and latching —
substantially better than random, and neither ever opened the door.*

## What the per-episode columns add that the means hide

A single random episode reached **28.755**, above idaac's whole eval-medium mean. Comparing means
alone would have missed that the distributions overlap.

**idaac's eval-hard is bimodal and its eval-medium is not.** eval-hard has both more near-floor
episodes (11.0 % vs 3.5 %) *and* more episodes beating the best random one (21.0 % vs 4.0 %). That
is why it carries a higher mean *and* twice the SD, and it is the mechanism behind the
`hard > medium` ordering being suggestive rather than established for idaac: the effect lives in a
tail, and a tail across ten scenes is what a scene-clustered SE of 3.77 is measuring.

**ppg's is a clean shift.** eval-hard sits at 0.5 % near-floor with 14.0 % above the random max —
it does better than eval-medium nearly everywhere rather than sometimes. That is the same fact as
`10/10 scenes` and `t = 6.74`, seen from the episode side.

So the two families reach a similar-looking ordering by different mechanisms, and only ppg's is a
location shift. **The ordering is real; only ppg's version of it is established.**

## A correction to the companion note's validity line

That note's "resets 200/200 reproducible in every regime" was **vacuous**, and is fixed there. The
audit had a single pass to look at, so no slot had a second observation to disagree with;
`audit_eval_validity.py` now prints `NOT COMPARED` for such input. On the **full bundle** the real
figures are train 200/200, eval-easy 200/200, `eval-hard` **145/166 (13 % vary)**, `eval-medium`
**75/200 (62 % vary)**.

Nothing on this page changes — the floor comparison is per-episode and does not rest on pairing.
But any *paired* claim about those two regimes remains unavailable, which is what
[`PRODUCTION-GRADE-PLAN.md`](PRODUCTION-GRADE-PLAN.md) has said all along.

## What is still genuinely missing

The frame-0 row — each family's own initialised network — remains unmeasured, and it is a different
question from this one. A randomly initialised *network* is not a uniform random *action* stream:
its action distribution is concentrated wherever initialisation puts it, which on a shaped task can
score either side of uniform. `learning_over_random.py` is right to refuse to substitute one for
the other, and right to refuse ppg's pilot figure across families.

Cheap, and worth doing once rather than per-run: have the runner stamp a checkpoint **before**
training and let the existing curve-eval loop pick it up, since that loop already maps checkpoint
files to frames. Then every future cell carries its own frame-0 row in its own closure, and this
note's argument about closure invariance stops being needed.
