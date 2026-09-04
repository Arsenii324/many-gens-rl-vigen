# Brief D — the evaluation protocol, which we built without a reference

**Upload with**: `SHARED-CONTEXT.md`, `PREMISES.md`, `FAITHFULNESS.md`.

**Suggested approach**: this is the most methodological of the four briefs and probably benefits
least from a scoping pass — the relevant literature (RL evaluation methodology, generalization
benchmarks, rliable) is known and findable. Go deep, but ground every recommendation in what is
actually affordable at ~78 environment steps/s (see §5).

---

## Why this brief exists

The supervisor's brief requires that evaluation be **identical across all baselines**, and we
enforce that structurally: one `evaluate()` function, which takes an opaque
`policy: Callable[[obs], action]` and cannot see which algorithm produced it, with the protocol
frozen in a hashed dataclass so two runs either pool or visibly do not.

**But we were never given a reference evaluation to copy.** A candidate existed and was explicitly
withdrawn by the supervisor as not being a good example, and as not faithful to the paper it came
from. So our protocol was **built from the requirement rather than copied from a source**, and
every choice in it is ours. That is stated plainly in our docs, and it is the largest unexamined
assumption in the project.

## The decision this feeds

**Whether to change the protocol before spending real compute.** Protocol changes are cheap now and
expensive later — every number produced under the old protocol becomes incomparable, by design,
because the protocol is hashed. So this is the right moment and roughly the last one.

---

## 1. Our protocol, stated for critique

| choice | value | our reasoning |
|---|---|---|
| training regime | `train`, **scene 0 only** | defines what "generalization" means here |
| evaluation regime | `eval-easy` (also `eval-hard` available) | the held-out visual distribution |
| evaluation scenes | **0–9, including the training scene** | see §2 — the weakest point |
| episodes per scene | 10 → 100 episodes per evaluation | |
| policy | **deterministic** | stochastic evaluation confounds exploration noise with competence |
| metric | raw undiscounted episodic return, **never normalized** | a reference repo reported a `VecNormalize`d number under a name that reads raw |
| aggregation | **mean**, not IQM | *(reasoning WITHDRAWN — see §3. The conclusion stands; the bimodal-episode argument was a level error.)* |
| uncertainty | bootstrap 95% CI | |
| gap | **absolute difference** train − eval, never a ratio | a ratio against a near-zero denominator produced a published "131.3% retention" off a denominator of 0.11 |
| checkpoint | final, never best-by-eval | |
| success | recorded alongside return where the env exposes it | |

Please **argue against** these where the literature does. We would rather be corrected now.

## 2. ~~The training scene is in the evaluation set~~ — WITHDRAWN 2026-08-10, the premise was wrong

**This section previously asked how much a 1/10 in-distribution contamination costs. There is no
such contamination, and the question should not be answered as posed.**

`scene_id` is nested *within* `mode`: RL-ViGen resolves a scene as
`get_custom_reset_config(task, mode, scene_id)`. We train on `mode=train, scene 0` and evaluate on
`mode=eval-easy, scenes 0..9`. Those share an integer, not a configuration — and our own
`test_eval_modes_actually_look_different_from_train` asserts the two modes differ in pixels. So
**no evaluation scene is the training condition**, and `Protocol.eval_includes_train_scenes=True`
is literally true about the id lists while being misleading about what it implies.

The real asymmetry, which is a genuine question, is §2a below.

## 2a. The two sides of the gap are measured with different precision

Our gap is `train − eval`, and the two are not sized alike:

| | scenes | episodes/scene | total episodes |
|---|---|---|---|
| train side | 1 (`train_scene_ids=(0,)`) | 10 | **10** |
| eval side | 10 | 10 | **100** |

RL-ViGen's own `eval.py::robo_eval` runs **100 episodes for both** — at the train level it simply
does not switch scenes (`if self.level == 'train': pass`), so it is 100 episodes on one scene.

So the quantity we subtract is estimated from a tenth of the samples of the quantity we subtract it
from. **Is that the right allocation of a fixed evaluation budget?** Arguments both ways: the train
side has no scene variance to average over, so it may need fewer episodes; but it is also the
denominator-ish term whose noise propagates directly into every gap. What does the literature say
about allocating episodes between the two arms of a difference?

- What is standard in the visual-RL generalization literature — Procgen, DMControl-GB, RL-ViGen
  itself? Do they evaluate on held-out levels only, or on the full distribution including training
  levels?
- Is there a defensible reason to include it (e.g. reporting train and test from one sweep), or is
  this simply a bug in our design?
*(Two further questions stood here and are removed: both assumed the 1/10 contamination that §2
withdrew. Do not answer them.)*

## 3. ~~Statistics: are we right about mean vs IQM?~~ — ANSWERED, and we were wrong about why

**Do not spend effort here.** Our stated justification was that IQM trims the successful tail of a
bimodal return distribution, evidenced by mean > IQM in 82% of a sibling project's evaluations,
ratio 1.418. That is a **level confusion**: IQM aggregates over *runs* (task x seed), never over
episodes within a run, so episode-level bimodality does not bear on it and nobody proposes trimming
episodes. Mean within a run is simply correct; what to use *across* runs is separate and only
matters once there is more than one seed.

**What is still worth answering:**

- **Should success rate be the headline metric instead of return?** On `Lift` the shaped reward
  pays `1 - tanh(10d)` at every one of 500 steps and nothing terminates on success, so a **random**
  arm scores ~7.5 mean return with **zero** successes. If a policy can score highly without ever
  completing the task, return may be measuring the wrong thing. **This is the question we most want
  challenged.**
- How many seeds does a credible multi-baseline table need, and what should we report if we cannot
  afford them? We can afford few, and this is the axis that actually costs compute.

## 4. The generalization gap as a quantity

- **Absolute difference vs ratio vs normalized retention** — what does the literature use, and what
  are the failure modes of each? Our absolute-difference rule came from a specific disaster
  (a ratio against a 0.11 denominator), but an absolute gap has its own problem: it is not
  comparable across methods with very different training performance.
- Is there an accepted normalization that is robust when training performance is near the floor?
- **A method that fails to learn has a gap of zero**, which reads as perfect generalization. How is
  this handled in the literature? We think a measured random-policy floor plus a competence gate is
  necessary before any gap is meaningful — is that the accepted approach, and what is the gate?
- Should the gap be reported at a **fixed frame budget**, at **matched training performance**, or as
  a curve? Matched-performance comparison is more informative and much more expensive.

## 5. What is affordable

Ground the recommendations in this, or they are not usable.

- ~78 environment steps/s on a T4; 500 steps per episode → **~6.4 s per evaluation episode**.
- 100 episodes per evaluation point ≈ **11 minutes**, on top of training.
- A 500k-frame training run is ~1.8 h of pure environment stepping.
- Twelve baselines × 2 tasks × N seeds, on one or two T4s.

So: **what is the cheapest evaluation protocol that supports the claims we want to make?** If 100
episodes per point is wasteful and 30 would do, that is directly useful. If we need more seeds and
fewer episodes per seed, that is a trade we can make. If the honest answer is that a credible
twelve-baseline comparison is not affordable at this budget, we need to know that now — the right
response would be to cut the matrix rather than to report an underpowered one.

---

## Output we want

1. **A critique of §1**, choice by choice, with sources.
2. **A verdict on including the training scene** in the evaluation set.
3. **A recommendation on mean vs IQM vs success rate** for a bimodal, shaped-reward manipulation
   task, and on whether return is the right headline at all.
4. **A recommended gap definition**, including how to handle methods that never learn.
5. **A minimum viable design**: seeds × episodes × eval points that supports a defensible
   multi-baseline claim within the compute above — and an explicit statement if that is not
   achievable, together with what to cut.
