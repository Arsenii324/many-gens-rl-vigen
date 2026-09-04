# The question, who asks it, and why the design looks like this

**Written 2026-08-24. Dated snapshot, not a living document.**

## The question

*Of twelve visual-RL methods, which retain their performance when the visual conditions change from
those they trained under — and by how much?*

The setting is **RL-ViGen**, a benchmark for visual generalization in RL. The tasks used here are
robosuite manipulation: **Door** (open a door with a Panda arm) and **Lift**. The methods span
off-policy pixel-RL (DrQ-v2, DrQ, CURL, SVEA, SGQN, RAD, SODA), on-policy PPO derivatives (PPG,
IDAAC, IBAC-SNI, CTRL), and one sibling port (ALDA).

**Who is asking:** the MIPT Centre for Cognitive Modelling, generalization-in-RL group. This is
unpublished lab work, supervised, and the deliverable is a defensible comparison table plus an
account of what it does and does not support.

## The design, choice by choice

### 1. Hermetic clones, not a shared framework

Each baseline is a **separate clone of the original authors' code**, with its own file, own
utilities, and **no shared base classes, runners, or adapters.** The governing rule, from
`../../../../docs/porting-directive.md` §1:

> Duplication is cheaper than a wrong abstraction.

and the project's own formulation: **duplication is free; any join carries burden of proof.**

**Why.** A shared abstraction across twelve RL algorithms silently changes their numbers. The
project surveyed fifteen RL libraries partly to check this intuition against the field; TorchRL's
own issue tracker documents roughly twenty cases of a shared component changing an algorithm's
results (`../../library-survey/CONTEXT.md`). The cost of duplication is maintenance. The cost of a
wrong abstraction is a wrong result that looks right, which is unrecoverable.

**What it costs, honestly.** Twelve near-copies of similar code, no single place to fix a bug, and
no mechanism that notices when two clones drift apart in a way that matters. The project accepts
this deliberately.

### 2. The null is the original repository, cloned, running its own `train.py`

Not our re-implementation. Not a port. The *actual upstream repo*, invoked through *its own* entry
point and *its own* hydra configs.

**Why.** A port introduces an author — us — between the method and the number, and then every
disagreement with a published result has two candidate explanations. Running upstream's own code
removes one of them.

A previous architecture *did* port everything into a unified `rlgen/` package. It was **superseded
on 2026-08-17** in favour of clones. That switch is the single largest direction change in the
project, and it has a long tail: documents written about the port still describe "our"
configuration in terms that no longer reach a run. **C64** is a live instance — `FAITHFULNESS.md`'s
SGQN row states our `aux_lr` is 0.3, but the clone reads upstream's `cfgs/sgqn_config.yaml:54` and
runs **1e-4**. Both halves of that document are internally true; the join is false.

### 3. Retention as the endpoint

The reported quantity is **retention**: performance in a held-out visual regime divided by
performance in the training regime, per method.

**Why this and not raw held-out score.** Because of the identification problem below. Raw held-out
score confounds "generalizes well" with "is a better algorithm on this task". A ratio makes **each
method its own control**: a method is compared against itself, so the seven configuration choices
that differ between methods largely divide out.

**What it costs.** A ratio inherits the noise of both arms and is unstable when the denominator is
small — which on this task it usually is. Guarding that denominator has produced three separate
refusals in the tooling, each added after a real failure:

| refusal | fires when | added because |
|---|---|---|
| `AT-CHANCE` | denominator does not clear the measured random floor (1.82) | a 2.02 denominator looked precise (sd 0.8) and was chance |
| `UNSOLVED-DENOM` / `WEAK-DENOM` | denominator solves the task < 25% of the time | a policy at 1/20 on every scene produced a 0.947 "retention" |
| **contamination alarm** | the ratio's entire CI sits above 1.0 | **C65**, added 2026-08-24 — see below |

### 4. The identification problem — the design's central weakness, stated in full

**Method identity is perfectly collinear (r = 1) with seven configuration choices.** Each baseline
differs from the others not only in its algorithm but in its learning rate, its replay capacity, its
augmentation, its n-step, its network sizes, its rollout length, and its backbone lineage — because
each is faithful to *its own* origin, which is the point of the hermetic design.

**Therefore no observed difference between two baselines is attributable to the algorithm.** This is
not a caveat; it is a property of the design, recorded in `../../RESEARCH-FRAME.md`, and it is why
retention rather than raw score is the endpoint. A reviewer is entitled to ask why the study is
being run at all given this, and that question is asked back in [09](09-open-questions.md).

The honest answer the project gives itself: the comparison is a **benchmark-style** claim ("under
each method's own recommended configuration, here is how much each retains"), not a **scientific**
claim ("this algorithmic mechanism causes better generalization"). Whether the first is worth
producing is a legitimate thing to challenge.

### 5. The regimes

`train` (fixed textures and lighting) versus `eval-easy` (randomised). The benchmark also defines
`eval-hard` and a camera axis (`cam-easy`/`cam-hard`) — **neither has ever been measured here.**

**A live problem with this axis, C54.** The only archived checkpoints the project has were
*provably not trained on the distribution their config declares*. Per-pixel comparison of the run's
own stored training frame against freshly rendered frames puts `eval-easy`/scene 0 nearest (7.6) and
the declared `train`/scene 0 nearly furthest (39.9) of twenty combinations. No mechanism has been
found. Two register entries depend on those checkpoints.

**C65 is the cheap screen that came out of it** and generalizes it: a retention ratio above 1 means
the policy does *better* away from its declared training condition, which a correctly-trained policy
does not do. All eight grids split cleanly by that sign — four freshly-trained cells below 1
(0.03–0.88), three archived checkpoints above (1.89–2.79), and the random-policy control at
**1.02**, which is the anchor that makes it readable: a policy with nothing to lose sits at 1.

## What would falsify the design itself

Stated so it can be checked rather than defended:

- If evaluation noise at fixed seed turns out to exceed the retention differences between methods,
  the endpoint cannot support a ranking. **This is currently live** — see
  [03](03-what-was-measured.md) §2, where the same checkpoint evaluated twice disagrees by 47% on
  success count.
- If the retention ratio proves as sensitive to scene selection as the 0.003-vs-0.030 gap suggests,
  the endpoint needs a fixed estimand chosen in advance rather than one determined by which scenes
  passed a guard.
- If our evaluation protocol turns out not to match RL-ViGen's, every external comparison is void
  and the internal ones are unaffected. Nothing currently checks this.
