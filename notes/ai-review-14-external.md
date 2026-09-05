I would still classify the current version as **pre-production, not production-ready**, but the remaining work is more concentrated than in the previous artifacts.

Several previous hard defects are genuinely fixed. The most important new finding is different: **I think the newly introduced A27 “UTD correction” is based on the wrong denominator and should not be applied as a fidelity correction.** If implemented as proposed, it could itself handicap RAD/SODA/ALDA.

I also found that the previous IDAAC episode-boundary correctness defect has been repaired end-to-end. IBAC-SNI's intended 16-process production path remains the clearest hard implementation blocker.

A limitation: I did not finish a literal exhaustive audit of every source file before the tool window ended. I concentrated execution and source tracing on the production machinery and the baselines with the highest unresolved risk: PPG, IDAAC, IBAC-SNI, CTRL, the off-policy update schedules, evaluator/provenance, and final V100 resolution. I would still want one further source-differential pass over ALDA/RAD/SODA and the native five before calling the audit exhaustive.

# Current verdict

The repository's own gate currently reports roughly **25 PASS, 3 FAIL, 12 OWNER** and correctly refuses launch.

My scientific classification is:

| Area | Assessment |
|---|---|
| IDAAC terminal episode identity | **Fixed** |
| PPG vector-Normal auxiliary KL | **Fixed** |
| CTRL normalized evaluation return | **Fixed** |
| CTRL evaluator double reset | **Fixed** |
| A20 3-vs-5 executable mismatch | **Fixed in code**, stale protocol prose remains |
| V100 native-five replay | **Fine** at 620k for a ~600k experiment |
| PPG V100 cadence | Improved deliberately; still hybrid design point |
| A27 UTD correction | **I think the reasoning is wrong; do not implement as proposed** |
| IBAC β=1 | **Fixed** to 1e-4 |
| IBAC 16-process execution | **Hard blocker** |
| IBAC 16-worker physical RNG | **Hard blocker** |
| IBAC algorithm identity | Major unresolved hybrid-port issue |
| IDAAC algorithm design point | Major unresolved fairness issue |
| PPG algorithm design point | Major unresolved fairness issue |
| CTRL continuous action semantics | New important unresolved issue |
| Places365 split | Learning-affecting deviation remains |
| Time-limit handling | Important family-level confound remains |
| Current evaluator validation | **0/7 current-revision families** according to gate |
| Final V100 renderer/runtime | Unvalidated |
| External RL-ViGen positive control | Not yet established |
| Exact source tree | **Not frozen; manifest says 185 dirty paths** |
| Statistics/estimand | Substantially specified, but some gates/docs are stale |
| Fleet launch | **NO-GO** |

---

# 1. Most important new correction: I disagree with A27's UTD analysis

The project has recently reasoned roughly as follows:

> RAD/SODA/ALDA sources use action repeat 4. They do ~1 update per control step. Therefore they effectively do 0.25 updates per environment frame. Door uses action repeat 1, so doing one update per Door step quadruples UTD. Therefore production should reduce update frequency to 0.25.

I don't think that is the right fidelity calculation.

For RAD/SODA/ALDA-style off-policy loops, one control decision produces:

1. one action;
2. one environment transition;
3. one replay-buffer item;
4. approximately one learner update.

With action repeat 4, that **single replay transition represents four simulator substeps**. It does not create four new replay examples.

So in the ordinary replay-learning sense:

\[
\text{updates per newly collected replay transition}\approx1
\]

in the source.

Door at action repeat 1 currently also has:

\[
\text{updates per newly collected replay transition}\approx1.
\]

Thus the current implementation preserves the source's optimization-to-data ratio much better than an A27 correction to 0.25 would.

Changing to 0.25 would instead give:

\[
0.25\text{ learner updates per replay sample},
\]

which is a **4× reduction in optimization per collected data point relative to source**.

Action repeat changes how much *simulator time* one stored transition spans. It does not multiply the number of independently collected transition samples.

This distinction is important:

\[
\frac{\text{updates}}{\text{replay samples}}
\]

and

\[
\frac{\text{updates}}{\text{low-level physics substeps}}
\]

are different quantities.

Calling the latter “UTD” creates the confusion.

### It is especially problematic for the native RL-ViGen methods

The project's new A27 analysis also reasons from a generic action-repeat assumption for the native five. But RL-ViGen's Robosuite configuration itself uses action repeat 1 in its published setup. So Door action repeat 1 is not obviously a departure requiring compensation in the first place.

### ALDA's instability evidence is still useful

The earlier observation that ALDA was unstable at update ratio 1 while 0.25 was stable should not be discarded.

It establishes:

> On this target/runtime/configuration, reducing optimization frequency may improve ALDA stability.

It does **not** establish:

> 0.25 restores source fidelity.

Those are different arguments.

The scientifically clean next experiment is therefore a predeclared Door sensitivity:

\[
\text{ALDA UTD}\in\{1,\;0.5,\;0.25\}
\]

or at minimum 1 versus 0.25.

If 0.25 is required for a functional baseline, classify it as a **target-specific optimization adaptation**, not restoration of the original algorithm's UTD.

I would correct `FINDING-update-to-data-ratio.md` and `audit_comparability_seam.py` before this idea propagates into production.

For reporting, use two separate quantities:

- learner updates per newly collected replay transition;
- simulator/physics substeps per transition.

Do not collapse them.

This is probably the most important conceptual correction in this version because implementing the present A27 prescription could systematically weaken three baselines.

---

# 2. The previous IDAAC correctness blocker is genuinely repaired

I re-traced the actual terminal transition path rather than relying on the static tests.

The previous problem was:

```text id="pbsp1h"
terminal step from episode A
→ Baselines VecEnv auto-resets
→ returned observation is episode B
→ info still contains level_seed A
→ storage associates new B observation with A
```

That made IDAAC's same-instance temporal pairing incorrect.

The current version now handles the distinction explicitly.

The wrapper exposes a **next episode level ID** on terminal transitions.

The collector detects `done` and associates the auto-reset observation with that next ID.

The storage implementation now writes level/nstep into the corresponding next-observation slot before moving its pointer.

I reproduced the boundary logic against the current implementation, and episode membership remains aligned.

So I would remove the old:

> IDAAC implementation is invalid because episode IDs cross physical reset boundaries

blocker.

This was a real fix, not merely a new test asserting the same old behavior.

---

# 3. IDAAC still has a different, scientific problem: which IDAAC are you evaluating?

The current implementation is now internally coherent.

The remaining issue is baseline identity.

Current IDAAC is close to the authors' Procgen implementation parameters:

- \(\gamma=.999\);
- LR \(5\times10^{-4}\);
- entropy .01;
- rollout 256;
- PPO epoch 1;
- 8 minibatches;
- Procgen-oriented auxiliary scheduling.

Those are indeed the official repository defaults. 

But the IDAAC paper also evaluates continuous visual control with a substantially different design point, including things such as:

- three stacked frames;
- much longer 2048-step rollout;
- different optimization schedule;
- entropy 0;
- \(\gamma=.99\);
- LR around \(3\times10^{-4}\);
- substantially more PPO optimization;
- different continuous-control auxiliary choices.

Door is much closer in problem class to continuous visual control than to Procgen.

So the current baseline asks:

> What happens when the authors' Procgen IDAAC implementation is structurally ported to continuous Door?

It does not ask:

> What happens when the authors' published continuous-control IDAAC design is used on Door?

Neither question is inherently wrong.

The danger is getting a weak result from the first and presenting it simply as “IDAAC.”

Given the explicit concern about handicapped baselines, this remains one of the most important experiments to perform before full production:

**IDAAC-P:** current Procgen-derived port.

**IDAAC-C:** minimally Door-adapted version of the published continuous-control configuration.

Do this as a bounded preproduction comparison rather than after seeing final results.

The existing baseline should not be discarded; it is useful evidence about fidelity to the executable Procgen source.

---

# 4. The episode-ID concept itself is still an adaptation

Fixing the implementation doesn't remove the conceptual difference.

Procgen `level_seed` denotes a generated level.

The new Door ID denotes an episode.

Those aren't the same latent variable.

The current mapping is internally sensible: observations considered as belonging to the same IDAAC instance really do belong to the same physical rollout.

But the invariance objective now means something closer to:

> remove/identify information particular to one episode while learning temporal ordering within it

rather than the original persistent Procgen-level concept.

This doesn't require another engineering fix.

It needs to constrain claims about what a negative result means.

---

# 5. PPG's cadence has been deliberately improved

The previous V100 proposal used 16 PPG environments.

The current profile has deliberately gone back to 8.

That gives:

\[
8\times256=2048
\]

samples per PPG policy iteration.

With:

\[
N_\pi=32,
\]

the auxiliary phase occurs approximately every:

\[
2048\times32=65{,}536
\]

interactions.

That is notable because the authors' published continuous-control PPG configuration also uses roughly a 2048-step data batch and \(N_\pi=32\), producing the same approximate interaction cadence.

So the old objection that your final PPG runs its auxiliary phase wildly more frequently than the relevant continuous-control precedent is now substantially repaired.

The official original OpenAI source itself uses 64 environments, \(N_\pi=32\), LR/aux-LR \(5\times10^{-4}\), \(\gamma=.999\), one policy/value epoch, etc.  It feeds those settings directly into the PPG learner. 

---

# 6. But PPG is still a hybrid design point

Matching the auxiliary-phase cadence does not make the whole configuration equal to the published continuous-control PPG setup.

Current Door PPG remains approximately:

- one 64×64 frame;
- 8×256 data collection;
- \(\gamma=.999\);
- LR \(5\times10^{-4}\);
- entropy .01;
- 8 minibatches;
- Procgen-style observation/optimization choices.

The published continuous-control PPG design used materially different observation and optimization settings, including three-frame inputs, \(\gamma=.99\), entropy 0 and different optimizer/minibatch choices.

So current PPG is best described as:

> **continuous-action PPG based primarily on the original Procgen implementation, retimed so the PPG phase cadence corresponds to the authors' continuous-control sample cadence.**

That is a coherent authored variant.

It is still not an obvious canonical continuous-control PPG.

I would conduct the same kind of bounded configuration check as for IDAAC.

Particularly important variables are:

- one frame vs three;
- entropy .01 vs 0;
- \(\gamma=.999\) vs .99;
- optimization/minibatch schedule.

The continuous KL repair itself remains correct and is no longer an issue.

---

# 7. IBAC-SNI remains the clearest hard production blocker

The previous disastrous \(\beta=1\) problem has been fixed.

Current launch explicitly uses approximately:

\[
\beta=10^{-4}.
\]

That is in the range of the authors' principal visual/CoinRun IBAC-SNI configuration.

But the final V100 execution profile proposes **16 parallel environments**, and that path remains invalid.

## First problem: it has already failed operationally

The trainer forces multiprocessing start method:

```text id="ogfbrg"
fork
```

and multi-process MuJoCo/EGL testing has already produced `EOFError`/worker failure.

So the proposed final configuration is not presently runnable.

## Second problem: worker physical RNG is incorrect under fork

The parent globally seeds NumPy.

The RL-ViGen Door physical initialization uses global NumPy.

The wrapper's per-environment `seed()` does not actually assign a private RNG for that physical state.

Then `ParallelEnv` forks its workers.

Forked processes inherit the parent's NumPy RNG state.

Without an explicit per-worker reseed **inside the worker after fork**, workers can begin from identical/correlated Door-placement RNG streams.

Thus even if the EGL error disappeared, sixteen nominal environments would not yet constitute sixteen correctly seeded physical-environment streams.

This needs a proper worker lifecycle:

```text id="e9gz7d"
start process
→ derive deterministic worker seed from (run seed, worker ID)
→ seed physical NumPy RNG inside worker
→ construct/reset environment
```

If switching to `spawn`, create the environment inside the child too. Passing already-constructed MuJoCo environments into spawned processes is not a safe assumption.

Then verify behavior, not seed integers:

```text id="wpe6yn"
worker 0: first 10 realized Door poses
worker 1: first 10 realized Door poses
...
worker 15
```

Requirements:

- deterministic across repeats with same base seed;
- different between workers;
- changed appropriately with different training seed.

Until that passes, IBAC final production is blocked.

---

# 8. IBAC-SNI remains an algorithm hybrid after β is fixed

Current IBAC combines approximately:

- CoinRun-style IMPALA visual encoder;
- PyTorch/MiniGrid-side VIB implementation;
- a 64-dimensional single-sample bottleneck;
- \(\beta=10^{-4}\);
- authored continuous Gaussian head;
- entropy 0;
- target-specific parallelism.

The authors' main visual IBAC-SNI setup has other important properties, including multi-sample bottleneck behavior, different latent dimensionality, regularization and augmentation.

So using the CoinRun β and IMPALA trunk alone doesn't reproduce that method.

This should be resolved before interpreting a poor IBAC result.

Given that Door is a pixel generalization task, I still think the cleanest reference is the authors' **main visual/CoinRun IBAC-SNI**, not a hybrid of CoinRun architecture and MiniGrid bottleneck semantics.

If implementing the entire original stack is infeasible, at least port the defining bottleneck/SNI semantics:

- appropriate latent dimension;
- multi-sample behavior;
- relevant L2;
- augmentation;
- SNI;
- then continuous action adaptation.

And rerun the entropy intervention **after** the final β/bottleneck/process configuration. The old entropy evidence was generated under a materially different method.

---

# 9. New CTRL question: its representation objective sees the requested action, not necessarily the executed one

This is a subtler continuous-port issue.

CTRL's representation/clustering machinery conditions on action.

In the original discrete setting:

\[
a_\text{policy}=a_\text{executed}.
\]

In current Door:

1. Gaussian samples raw \(a\);
2. PPO needs raw \(a\) and its raw-policy log probability;
3. environment receives \(a\);
4. environment/controller clips or scales it to its legal range;
5. transition comes from \(a_{\rm executed}\);
6. CTRL representation learner is later given raw \(a\).

Thus the representation objective may be learning:

\[
(s_t,a_\text{raw},r_t,s_{t+1})
\]

when the actual transition came from:

\[
(s_t,a_\text{executed},r_t,s_{t+1}).
\]

For PPO, replacing raw action with clipped action would be wrong because the likelihood ratio needs the actual policy sample.

For CTRL's transition/representation objective, executed action may be the semantically correct one.

That suggests retaining both:

```text id="zyx8by"
policy_action
executed_action
```

and using them for their respective purposes.

I would not make this change solely from reasoning.

Run a short controlled sensitivity:

- CTRL cluster uses raw action;
- CTRL cluster uses executed action;

while PPO remains identical.

This matters because initial Gaussian saturation can be substantial.

---

# 10. CTRL's final 16-environment configuration remains a resource-driven algorithm adaptation

Original CTRL defaults are approximately 64 environments.

Current V100 profile uses 16.

That changes rollout batch from roughly:

\[
64\times256=16{,}384
\]

to:

\[
16\times256=4096.
\]

Thus update/cluster phases occur about four times more frequently per collected interaction and minibatches are substantially smaller.

The final host has enough nominal RAM that 64 might possibly fit, but JAX memory behavior cannot safely be extrapolated linearly.

This deserves one actual V100 measurement.

If 64 fits, I would prefer it for source fidelity.

If it doesn't, keep 16 and classify it as a learning-schedule adaptation.

---

# 11. CTRL's old common-evaluator defects remain fixed

I specifically rechecked the relevant direction.

The current common evaluator:

- no longer sums normalized training rewards;
- no longer explicitly resets after an auto-reset, avoiding the old 0,2,4 placement sequence;
- reconstructs the model from bound configuration rather than a detached set of evaluator defaults.

So those should stay off the blocker list.

Online evaluation still advances CTRL's JAX policy PRNG while NumPy physical state is restored, but the repository now characterizes that much more accurately as source-style behavior rather than claiming complete RNG noninterference.

I would not block final production on that alone if the exact online cadence is part of the resolved training lineage.

---

# 12. The final V100 native-five replay setting is scientifically fine

Earlier versions were going to use a 300k replay buffer for 600k training.

That would have changed the learning distribution substantially.

Current final V100 profile uses approximately:

\[
620k.
\]

The estimated maximum retained transitions for a nominal 600k run fit below that.

Thus replay never actually fills/evicts.

In that regime:

> 620k and the nominal source 1M capacity are behaviorally equivalent with respect to replay eviction.

I would remove this from the scientific blocker list.

Make sure the final resolved production manifest, not merely the host-profile documentation, actually contains the 620k value.

---

# 13. The V100 `min_frames` guards are stale for some on-policy methods

The project improved final-host configuration but retained some derived quantities from the lower-resource profile.

Example: IDAAC's base minimum meaningful probe budget corresponds to approximately:

\[
4\times256=1024.
\]

But V100 uses 16 processes.

One complete V100 rollout is:

\[
16\times256=4096.
\]

A 1024-frame V100 probe can therefore satisfy the nominal minimum-frame check while:

```python id="ktbjhi"
num_updates =
1024 // 256 // 16
= 0
```

and perform no meaningful learning.

A similar issue exists around IBAC's process-dependent minimum budget.

This won't affect a 600k production run.

It can invalidate the **canaries used to approve that production run**.

Derive minimum frames, cadence and expected stamps from the fully resolved host profile rather than storing them as independent constants.

---

# 14. A20 is executable now, but the evaluation protocol document is still internally stale

The previous artifact had executable production set to five intermediate-grid episodes despite A20 deciding three.

Current live family configuration is now three.

Good.

But portions of `EVAL-PROTOCOL.md` still describe five episodes as the operational default.

So the experiment itself is closer to correct, while the purported specification contains contradictory historical states.

Fix the prose and, more importantly, make the gate compare the **fully resolved production environment** against the frozen protocol.

Checking selected JSON fields is how the previous 3-vs-5 mismatch survived.

---

# 15. Places365 remains a learning-affecting deviation

The project still substitutes approximately 36.5k Places validation images for the source-intended Places training distribution.

This affects SVEA, SGQN and SODA—the algorithms for which external visual diversity is specifically part of the robustness mechanism.

That is not a neutral platform substitution merely because the same three methods receive the same alternative data.

It can change their relative performance against methods that do not use Places at all.

Now that final production moves to a much larger V100 host, I would revisit whether this operational compromise is still necessary.

If storage permits, restore the source-intended distribution.

If not, run train-split versus validation-split sensitivity on at least one affected method and explicitly classify the val split as a learning adaptation.

---

# 16. Time-limit semantics remain inconsistent across families

Some methods bootstrap through Door's 500-step artificial truncation.

Most imported methods treat that boundary as terminal.

Because Door generally runs to the time limit rather than ending on task success, this affects essentially every episode's final value target.

This remains one of the largest cross-family MDP-definition differences.

I would not automatically rewrite all original algorithms.

I would run a bounded sensitivity on representative methods.

If the effect is small, preserving native behavior becomes easy to defend.

If large, then this split is one of the substantive treatments represented by the twelve-system comparison rather than incidental implementation detail.

---

# 17. The full twelve-way experiment remains a system/design-point comparison

This continues to matter for presentation.

Across families there are systematic differences in:

- one versus three frames;
- 64 vs 84 vs 100→84 resolution;
- \(\gamma\);
- reward normalization;
- time-limit bootstrapping;
- replay vs rollout learning;
- action distributions;
- update schedules;
- stochastic versus deterministic evaluation;
- auxiliary data.

So even when everything is implemented faithfully:

> the twelve-way table compares twelve adapted algorithm systems.

It does not isolate a single algorithmic mechanism under otherwise identical conditions.

The native five provide a substantially cleaner within-family comparison.

Notably, the PPG/IDAAC one-frame choice becomes more contestable because their authors' continuous-control setup used three-frame inputs.

---

# 18. Shared evaluator validation remains a hard preproduction requirement

The current production gate reports **zero of seven evaluator families validated under the current evaluator revision**.

I agree with resetting old validation after the evaluator has materially changed.

You need current-revision reconciliation for:

- RL-ViGen;
- DMC-GB;
- PPG;
- IDAAC;
- ALDA;
- IBAC-SNI;
- CTRL.

Use competent checkpoints.

Agreement on a floor-performing policy says very little.

Where a native evaluator doesn't support the exact target grid, validate:

1. fixed-observation policy outputs/distribution parameters;
2. short matched rollout under controlled physical/random conditions;
3. raw return/success extraction;
4. realized placement diagnostics.

This should happen after the remaining IDAAC/IBAC/CTRL semantic decisions, otherwise you validate an implementation that is about to change.

---

# 19. The production renderer remains unvalidated

This stays a serious blocker because the project has direct evidence that rendering/runtime can move results dramatically with identical weights.

The appropriate experiment remains:

\[
R_A =
\text{known checkpoint + current evaluator + current trusted platform}
\]

versus:

\[
R_B =
\text{same checkpoint + same evaluator + same container + final V100 platform}.
\]

The host should be the only intended change.

Do this using a competent checkpoint.

Don't compare a new V100 measurement against an old result produced by a different evaluator revision.

---

# 20. Run one external RL-ViGen positive control before the fleet

The project still needs evidence that the **whole** final simulator/render/train/eval chain lives in a plausible RL-ViGen performance regime.

Evaluator parity alone answers:

> does our common evaluator behave like our native evaluator?

It doesn't answer:

> is the entire benchmark stack behaving like RL-ViGen?

Use a reasonably competent published Door method such as SVEA/SGQN rather than a weak near-floor checkpoint.

Exact numerical reproduction is not necessary if conditions differ. The objective is detecting a gross shared benchmark/runtime problem before producing 36 expensive training runs.

---

# 21. Provenance is substantially improved, but `Protocol.hash()` should be interpreted more narrowly

The full run-manifest system now records much more useful information:

- payload hashes;
- effective argv;
- runner environment;
- host profile;
- package resolution;
- assets;
- container identity;
- resolved effective configuration.

That can support strong lineage.

But `Protocol.hash()` itself still omits baseline-specific settings such as:

- replay capacity;
- process count;
- rollout/update geometry;
- PPG schedule;
- optimizer schedule;
- IBAC β/entropy;
- augmentation corpus;
- architecture variants.

Yet its documentation speaks in terms close to “every setting capable of moving a number.”

That is too strong.

I would explicitly split identities:

**comparison protocol ID**

```text id="8cbgrn"
Door
600k budget
seed policy
evaluation grid
scene/regime semantics
metrics
episode horizon
etc.
```

and **resolved training lineage ID**

```text id="4x581x"
exact source tree
exact patch set
exact argv
host profile
process count
optimizer
replay
augmentation corpus
all algorithm hyperparameters
runtime/container/assets
```

Two numbers can share the first and still originate from intentionally different algorithm configurations.

---

# 22. Root source freezing remains a real final blocker

The artifact manifest itself says the source workspace was dirty with roughly **185 uncommitted paths** when the review artifact was produced.

That is not merely because this zip omits `.git`.

The originating workspace was not frozen.

Wait until the remaining fixes/configuration decisions are complete, then:

- commit exact root tree;
- pin nested baselines;
- pin patch set;
- freeze production family descriptor;
- freeze evaluator;
- freeze aggregation/statistical code;
- tag it;
- build production payloads only from that identity.

There is no value freezing earlier while hard implementation decisions remain.

---

# 23. Several OWNER gates are stale rather than truly undecided

The raw gate count somewhat exaggerates how much science remains unresolved.

For example, the current protocol already specifies:

- fixed three training seeds for every reported row;
- production schedule uses 101/102/103;
- endpoint as headline;
- intermediate trajectory as descriptive;
- no “pick best OOD checkpoint and report it” rule.

Yet corresponding gates still report OWNER because their detection logic/prompt text reflects older versions.

These should be updated.

However, some OWNER items remain genuinely unresolved:

- full statistical protocol;
- competence threshold details;
- Door-only versus Door+Lift scope;
- renderer equivalence;
- exact final V100 canary;
- current evaluator validations.

---

# 24. The current “53% effect resolution at n=3” should not be described as a known lower bound

The arithmetic underlying the project's ~53% detectable relative difference is reasonable given the assumed coefficient of variation.

The evidentiary basis for that CV is weaker.

It appears to come substantially from a same-seed/backend repeat observation, not a large sample of independent training-seed variability.

So saying that approximately 53% is a guaranteed “lower bound” because true seed variance cannot be smaller is too strong.

True cross-seed variability could be greater or—in some conditions—even smaller than that particular repeated-run estimate.

Treat 53% as an **illustrative power/resolution calculation under the assumed variance**, not as a known property of the benchmark.

The main qualitative conclusion remains correct:

> n=3 resolves only coarse effects reliably.

If exact ranking is scientifically central, ≥5 independent training seeds is safer.

---

# 25. Checkpoint/curve stamps should use actual interaction counts

The synchronous methods cannot always stop exactly at requested 50k/600k values.

For example, final endpoints can be approximately:

- PPG ~600,064;
- IDAAC ~598,016;
- IBAC ~600,064;
- DMC-style loops possibly ~600,001.

These discrepancies are tiny and not worth distorting algorithms to eliminate.

But result records and plots should use the **actual executed interaction count**, not simply relabel a crossing checkpoint “50k” or “600k.”

This is especially important for intermediate trajectories if different rollout quantization shifts the checkpoint by a few thousand interactions.

---

# 26. Evaluation policy mode remains a mixed estimand

The common evaluator explicitly records this now, which is good.

PPG/IDAAC/CTRL/IBAC typically use sampled stochastic actions.

Most of the other methods use deterministic/mean/mode behavior.

So one “return” column contains different policy estimators.

Keep native/fidelity evaluation as primary if that's the chosen philosophy.

I would still add, where mathematically available, a secondary standardized mean-action evaluation.

That separates:

> how the authors' implementation normally evaluates

from:

> how the central deterministic policy performs under one shared convention.

---

# 27. Action saturation diagnostics are still important for the imported continuous Gaussians

With independent \(\sigma\approx1\) initialization:

\[
P(|a_i|>1)\approx31.7\%.
\]

Across seven dimensions:

\[
P(\exists i:|a_i|>1)\approx93\%.
\]

So early in training, a very large majority of action vectors can be modified by the environment/controller.

The current diagnostics are much better positioned to measure this than earlier versions.

Keep:

- per-coordinate clip fraction;
- any-coordinate clip fraction;
- log-standard-deviation trajectory;
- action norms.

This is especially useful for interpreting IBAC/PPG/IDAAC/CTRL differences.

---

# What is actually near-ready?

I would separate the twelve.

| Baseline | Current assessment |
|---|---|
| **DrQ-v2** | Near-ready after evaluator/runtime/source freeze |
| **DrQ** | Same |
| **CURL** | Same; identify as RL-ViGen's implementation accurately |
| **SVEA** | Near, except Places augmentation distribution |
| **SGQN** | Near, except Places distribution; good positive-control candidate |
| **RAD** | Near; **do not apply A27 0.25 “fidelity correction” without evidence** |
| **SODA** | Places issue; same A27 warning |
| **ALDA** | Near algorithmically; target stability sensitivity useful; same A27 warning |
| **PPG** | No hard code defect found; **design-point fairness pilot still warranted** |
| **IDAAC** | Previous hard storage/episode bug **fixed**; design-point/construct issue remains |
| **CTRL** | Old evaluator bugs fixed; raw-vs-executed action representation question + 16-vs-64 env issue |
| **IBAC-SNI** | **Still hard-blocked** by final multiprocessing/EGL/RNG path; hybrid-method issue remains |

# What I would do next, strictly ordered

I would not do another general scaffolding cycle.

1. **Do not implement A27 as a blanket UTD correction.** Rewrite the analysis around updates per collected replay transition versus simulator substeps.
2. **Fix IBAC multiprocessing completely**, including deterministic worker-specific physical RNG.
3. **Choose/implement a coherent final IBAC-SNI lineage.**
4. **Investigate CTRL raw-policy-action versus executed-action use in its representation objective.**
5. **Measure whether CTRL 64 envs fits V100; use it if practical.**
6. **Run the bounded PPG current-vs-published-continuous-control design pilot.**
7. **Run the analogous IDAAC design-point pilot now that its actual mechanism is fixed.**
8. **Restore Places training distribution if practical; otherwise perform sensitivity.**
9. **Generate one exact fully resolved V100 production manifest and derive all dependent values—min frames, update geometry, checkpoint cadence—from it.**
10. **Validate all seven evaluator families on the final evaluator revision.**
11. **Run final-host renderer equivalence.**
12. **Run one competent RL-ViGen external positive control.**
13. **Run representative artificial-horizon sensitivity.**
14. **Fix stale protocol/gate descriptions, including 3-vs-5 and already-set seed/checkpoint rules.**
15. **Freeze statistics/estimand/scope.**
16. **Commit/tag the exact final root tree.**
17. **Run exact production-profile canaries.**
18. **Then launch.**

# Production recommendation

I would not authorize the 12×3 final production fleet yet.

But the reason is no longer broad lack of confidence in the codebase.

The remaining blockers are fairly localized:

**IBAC cannot yet execute its proposed final configuration correctly.**

**PPG and IDAAC need a defensible decision between Procgen-derived ports and the authors' continuous-control design points.**

**CTRL has one important continuous-port semantic question and a potentially avoidable 4× batch-schedule deviation.**

**The new A27 update-ratio reasoning should be corrected before it causes new changes to otherwise relatively clean RAD/SODA/ALDA implementations.**

**The final evaluator/runtime/manifest/source still need the actual production-level validation and freeze.**

The most significant conclusion from this pass is therefore the A27 one: **action repeat is not a multiplier of replay data.** The current one-update-per-new-transition RAD/SODA/ALDA behavior is much closer to the source learner/data relationship than a proposed 0.25 update rate would be. If 0.25 proves better on Door, use it because target evidence justifies it—not because it allegedly restores the source UTD.

And conversely, the most important previous blocker that should now be deleted is the IDAAC terminal episode-ID/storage bug: the new end-to-end logic fixes that actual defect.
