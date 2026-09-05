I reviewed the new artifact as an executable experimental system rather than assuming that fixes documented in the repository were correct. I also ran targeted tests and production gates where that could cheaply falsify claims; I did not run long RL training.

My conclusion remains **NO-GO for the final production sweep**, but this version is materially better. Several previous blockers are repaired. The remaining blockers are now concentrated in a few evaluator bugs, the exact fidelity of PPG/IDAAC/IBAC-SNI, final-host configuration, and experiment lineage.

One limitation: I was able to inspect and test the major paths, but not literally finish a line-by-line semantic audit of every one of ~1,600 Python files before the tool window closed. In particular, ALDA and the entire five-member RL-ViGen family received less source-differential scrutiny than PPG/IDAAC/CTRL/IBAC-SNI. I therefore distinguish things I established directly from questions that still deserve verification.

## Executive assessment

| Area | Current assessment |
|---|---|
| Previous PPG KL bug | Fixed |
| Previous IDAAC worker-ID bug | Fixed |
| Previous CTRL normalized-return bug | Fixed |
| Previous remote omission of `rlgen/protocol.py` | Fixed |
| 600k schedule | Corrected in nominal schedule |
| V100 replay | Improved to 620k; effectively non-evicting |
| CTRL common evaluator | **Still wrong: double reset breaks pairing** |
| CTRL online-eval isolation | **Only NumPy isolated; JAX training RNG still perturbed** |
| Cross-scene pairing | **Doesn't support “only scene changes” interpretation** |
| Physical-placement provenance | Improved, but still fail-open |
| IBAC-SNI | **Still not a clean author implementation; new 16-process RNG blocker** |
| PPG | **Major schedule/design-point ambiguity** |
| IDAAC | **Major Procgen-vs-published-continuous-control ambiguity** |
| Places augmentation | Still changed to validation distribution |
| Time-limit semantics | Still inconsistent |
| Exact final V100 experiment | **Not yet instantiated/canaried as final production configuration** |
| Shared evaluator validation | **0/12 current-revision validations according to gate** |
| Source freeze | FAIL |
| Statistical/estimand protocol | Still OWNER/unfrozen |
| Final production | **Do not launch yet** |

# 1. Hard blocker: CTRL's common evaluator still double-resets

This is the clearest remaining direct evaluation bug.

`run_scene_ctrl()` explicitly resets before every measured episode. But CTRL's vector environment already auto-resets a completed environment inside `step_wait()`.

Its condition-seeding system increments an internal episode index on every reset.

The actual sequence becomes approximately:

```text
explicit reset → condition 0 → measured episode 0
terminal auto-reset → condition 1, discarded
explicit reset → condition 2 → measured episode 1
terminal auto-reset → condition 3, discarded
explicit reset → condition 4 → measured episode 2
...
```

Meanwhile the result metadata describes measured episodes as conditions 0, 1, 2, ...

Consequences:

- CTRL is paired correctly only on episode zero;
- later CTRL episodes do not use the conditions assigned to their recorded episode indices;
- half of the condition sequence is consumed by discarded auto-resets;
- placement provenance for CTRL is factually wrong.

The current pairing gate passes because it verifies the seed machinery syntactically. It does not exercise this state machine.

This must be fixed before interpreting any common-grid CTRL result.

The appropriate regression test is not another source inspection. Execute 5–10 short terminal episodes and require the realized physical initial-placement hashes to equal the expected sequence and to match another evaluator family under the same condition IDs.

---

# 2. CTRL reward reporting has been fixed

This is worth separating from #1.

Previously the common evaluator instantiated CTRL's vector environment with reward normalization enabled and summed normalized rewards, making its return incomparable with the other methods.

The current `run_scene_ctrl()` explicitly uses:

```python
normalize_rewards=False
```

so that particular measurement defect is gone.

Any old CTRL common-evaluator results from before this change should still be considered obsolete.

---

# 3. CTRL online evaluation still modifies subsequent training through the JAX PRNG

The new code saves/restores global NumPy state around evaluation. That protects the Door physical-placement stream.

It does not protect CTRL's policy-action randomness.

Training maintains a JAX PRNG key. Evaluation calls the stochastic action selector with that same key and stores the newly split key. After evaluation, NumPy is restored but the JAX key is not.

Therefore:

\[
K_{\text{after evaluation}}
\neq
K_{\text{without evaluation}}.
\]

Subsequent training actions differ because evaluation occurred.

The production gate now effectively narrows its claim to physical NumPy isolation, which is more honest than the previous version, but this still matters scientifically.

There are two defensible choices.

If preserving CTRL's original training/reporting behavior is paramount, retain it and explicitly say online evaluation is part of the training RNG trajectory.

If the goal is making reporting observational rather than interventionist, give evaluation an independent JAX key.

What should not happen is calling it generic “training/evaluation RNG isolation.”

A direct A/B trajectory test would settle the engineering property.

---

# 4. The new common-random-numbers scheme does not isolate scene identity

This is a different issue from CTRL.

The physical placement condition seed is derived from something equivalent to:

\[
f(\text{eval seed},\text{scene id},\text{episode index}).
\]

This does pair different **algorithms within a given scene**.

But scene 0 episode \(i\) and scene 1 episode \(i\) deliberately receive different physical-placement seeds.

Some project comments/documents still describe the scene experiment as if only scene identity changes while the Door placement sequence is held fixed.

That's no longer true.

For example:

```text
algorithm A, scene 3, episode 7
algorithm B, scene 3, episode 7
```

can be paired.

But:

```text
scene 0, episode 7
scene 3, episode 7
```

are not matched physical initializations.

This matters if you want to estimate a **scene intervention** or scene-retention effect.

You need to choose between two valid designs:

- If the desired estimand is “change scene while holding physical initialization constant,” physical placement should be keyed by `(eval_seed, episode_index)` independently of scene.
- If scenes should constitute independently randomized strata, keep the current implementation but stop interpreting scene differences as “only scene changed.”

This decision should follow the unresolved scene-generalization estimand rather than precede it.

---

# 5. Physical-placement provenance is improved but still permits missing physical evidence

The new wrappers expose useful actual environment diagnostics such as initial Door pose/state, reward components, success and clipping statistics.

That's much better.

But the evaluator still permits a completed episode to have:

```text
diagnostics_available = false
```

and continue.

Separately, observation hashes can be used as witnesses.

An image hash is not evidence that physical placement is the same.

Under different visual regimes the exact same physical state should generally produce different images.

If paired physical conditions matter to the paper, make their evidence mandatory:

```text
condition ID
door pose
robot initialization variables
scene
physical-state hash
```

No row should count as a paired-condition result unless those physical diagnostics exist.

---

# 6. Hard final-profile blocker: IBAC-SNI's 16 workers appear to inherit the same physical-reset NumPy stream

This issue didn't matter in the one-process DataSphere pilot. It matters in the intended 16-process V100 production profile.

The IBAC trainer globally seeds Python/NumPy/Torch and then constructs multiple environments.

The RL-ViGen adapter has an environment `.seed()` that is intentionally effectively a no-op for the process-global NumPy stream.

The underlying Door placement sampler uses global:

```python
np.random.uniform(...)
```

rather than the per-wrapper visual `RandomState`.

`ParallelEnv` then forks worker processes.

On normal Linux `fork`, those children inherit the parent's NumPy RNG state.

Therefore multiple workers can begin with identical physical-placement RNG state even though their nominal environment seed arguments differ.

The visual randomization streams are distinct. The **physical Door placement stream is the concern**.

At 16 processes this can collapse a substantial amount of the supposed parallel physical diversity.

This is a production blocker for the V100 IBAC profile until tested/fixed.

The correct solution is to establish a distinct deterministic physical RNG stream **inside each worker after fork**, not merely before creating `Process` objects.

Then execute a real multiprocessing integration test and inspect the realized Door initial placements across all 16 workers.

Do not rely on the distinct constructor seed integers as proof; they currently do not necessarily govern the RNG that actually chooses Door position.

---

# 7. IBAC-SNI's catastrophic β=1 setting is fixed — but the resulting baseline is still a hybrid

The new launcher now uses approximately:

\[
\beta=10^{-4}.
\]

That fixes the previous worst IBAC-SNI defect, where the default \(\beta=1\) was four to six orders of magnitude above demonstrated author settings.

However, the current implementation still does not correspond closely to one single author configuration.

It combines:

- CoinRun-style IMPALA visual trunk;
- PyTorch/GridWorld branch bottleneck machinery;
- a 64-dimensional, single-sample VIB;
- authored continuous Gaussian policy;
- target-specific entropy coefficient 0;
- \(\beta=10^{-4}\).

The authors' main CoinRun configuration uses materially different bottleneck semantics, including different latent size/multi-sampling and additional regularization/augmentation choices, while their PyTorch/GridWorld VIB configuration uses a much smaller beta.

So this remains an authored hybrid.

For a final reviewer-facing IBAC-SNI baseline, I would choose one lineage explicitly.

Either preserve the authors' PyTorch VIB-SNI mechanism and adapt the visual/action interfaces, or port the actual CoinRun visual IBAC-SNI mechanism more comprehensively.

Given that Door is a pixel task and you've already selected IMPALA, the CoinRun lineage is probably the cleaner reference—but that implies more than taking its \(\beta\).

Also: earlier “entropy 0 fixes IBAC” experiments were performed under the previous wrong β. They cannot establish that entropy 0 is still necessary at corrected β.

Repeat the small 0 versus 0.01 entropy intervention after fixing β and the multiprocessing RNG issue.

---

# 8. PPG's mathematical continuous-action KL is now correct

The earlier continuous adaptation retained the source's scalar `.mean()` KL on a vector Normal, weakening the cloning constraint by approximately seven dimensions.

The current code now sums vector KL over action dimensions before averaging.

That is the right semantic correction.

I would no longer list PPG's auxiliary KL implementation as a blocker.

---

# 9. PPG's more important problem is now schedule identity

The source PPG structure uses roughly:

- 64 envs per MPI rank;
- documented four-rank invocation;
- rollout length 256;
- `n_pi=32`.

The global interaction count per policy iteration is therefore roughly:

\[
4\times64\times256=65{,}536.
\]

Auxiliary phase every 32 such iterations:

\[
\approx2.1\text{ million interactions}.
\]

The final proposed V100 setup is one process × 16 envs × 256:

\[
4096
\]

interactions per policy iteration.

With the same `n_pi=32`, auxiliary phases occur approximately every:

\[
131{,}072
\]

interactions.

That's about **16× more frequent in environment-interaction units** than the documented source setup.

At 600k:

- source-global schedule would not yet perform a PPG auxiliary phase;
- present target PPG performs roughly four.

This changes PPG's defining mechanism.

But there is an important second reference point that changes how I would resolve it.

The IDAAC authors' published continuous-control experiments also evaluate PPG. Their DMC setup uses a **single process with 2048-step rollouts** and retains PPG's \(N_\pi=32\), which implies an auxiliary phase every approximately 65.5k interactions. They also use three stacked frames, PPO epochs 10, entropy coefficient 0, LR \(3\times10^{-4}\), \(\gamma=.99\), etc. 

Thus the current PPG is neither:

- the literal Procgen/source training schedule; nor
- the published continuous-control PPG design point.

Its auxiliary frequency is actually much closer to the continuous-control precedent, but many other important hyperparameters are still Procgen-like.

Because Door is continuous control, I regard that published DMC PPG configuration as highly relevant to reviewer fairness.

I would compare the current port against that continuous-control design point **before** seeing final PPG results.

---

# 10. IDAAC has the same, even stronger, reference-design problem

The implementation-level worker-constant `level_seed` bug is fixed. Episode-scoped identities now prevent nonsensical temporal comparisons across unrelated episodes.

But current IDAAC remains essentially a port of the authors' Procgen implementation.

The authors also published IDAAC on continuous-control DMC.

Their DMC protocol uses, among other things:

- 3 stacked frames;
- 2048-step rollout;
- 1 process;
- 10 PPO epochs;
- 32 minibatches;
- entropy 0;
- LR \(3\times10^{-4}\);
- \(\gamma=.99\);
- linear LR decay;
- and substantially different IDAAC auxiliary coefficients/schedules. 

The current intended V100 Door setup instead has approximately:

- 1 frame at 64×64;
- 16 processes × 256;
- 1 PPO epoch;
- 8 minibatches;
- entropy .01;
- LR \(5\times10^{-4}\);
- \(\gamma=.999\);
- Procgen-family auxiliary settings.

This is not a small difference.

Given that you're evaluating a continuous robotic-control task, a reviewer could reasonably ask why IDAAC and PPG were given their Procgen optimization/observation design rather than the authors' own continuous-control design.

This is now one of my highest-priority **baseline-handicap** concerns.

I would not resolve it merely by choosing whichever version scores better.

Before production, predeclare and compare:

**Procgen-source port** versus **published continuous-control design point adapted to Door**.

Then either report both or choose the primary by an explicitly stated fidelity principle.

---

# 11. IDAAC's episode identity remains a target reinterpretation even after the bug fix

Procgen's `level_seed` names a procedurally generated level.

Your Door episode identifier names a single rollout instance.

Those are not semantically equivalent.

The new implementation at least gives IDAAC a coherent relation:

> observations within this rollout belong to one shared physical episode.

But its original invariance construction was exploiting repeated level identity.

So the Door version remains a target-specific reinterpretation of IDAAC's distinctive mechanism.

That is acceptable as a port, but it means a poor IDAAC result has multiple explanations:

- IDAAC mechanism isn't useful on Door;
- your continuous optimization setup is poor;
- the target benchmark lacks a natural analogue of the latent level variable IDAAC assumes.

That distinction should survive into interpretation.

---

# 12. CTRL's rollout/update schedule is still changed 4×

Official CTRL defaults use approximately 64 environments × 256 steps.

Final proposed Door uses 16 × 256.

Thus rollout batch drops from about:

\[
16{,}384
\]

to:

\[
4096.
\]

PPO/CTRL updates occur ~4× more frequently per environment interaction and minibatches become substantially smaller.

This is less extreme than old PPG/IDAAC settings, but it is still a learning-dynamics adaptation rather than a pure compute optimization.

CTRL has no analogous published continuous-control configuration that cleanly resolves the issue, so an authored mapping is unavoidable.

At minimum preserve/update-scale semantics consciously.

---

# 13. The final V100 profile is much better, but it isn't yet the tested experiment

This version introduces an intended final V100 host profile:

- ~16 CPU cores;
- ~113 GiB RAM;
- V100 32 GB;
- replay 620k for RL-ViGen methods;
- PPG 16 envs;
- IDAAC 16 processes;
- IBAC 16 processes.

The replay change is especially good.

With roughly 620k capacity and a 600k Door budget, the native RL-ViGen off-policy methods can effectively retain their full run rather than evicting the first half at 300k.

But the current `production-schedule.json` remains essentially a DataSphere schedule with the old resource-oriented settings and no strong final host-profile identity.

The gates check that it says 600k and disables online eval. They do **not** establish that the schedule represents the intended V100 experiment.

So there are two systems:

1. the DataSphere profile that has been exercised more;
2. the final V100 profile that is scientifically better but materially changes replay and on-policy learning schedules.

The final profile needs to become the actual frozen executable schedule and then receive the canaries.

Do not manually overlay V100 settings at launch time.

---

# 14. There is a small but real interaction-budget mismatch between families

“600k” isn't exactly 600,000 interactions for every trainer.

Examples include approximately:

- DMC-GB style loops: 600,001 transitions due to inclusive loop;
- PPG 16×256 quantization: approximately 602,112;
- IDAAC floor quantization: approximately 598,016;
- IBAC 16×128: approximately 600,064.

These are less than ~0.4% in most cases, so I would not redesign algorithms around them.

But don't put an exact `600000` x-axis value on each row when the executed count differs.

Record and report the actual interaction count.

---

# 15. The Places365 distribution is still changed

The project intentionally rewrites visual augmentation loaders from the source's training-style Places data to the **validation partition**, pinned at about 36,500 images.

This affects visual-generalization methods for which external image augmentation is part of the learner, particularly relevant SVEA/SODA/SGQN-style mechanisms.

That is learning-affecting, not a storage-path adaptation.

For the final larger V100 environment, I would restore the intended training distribution if operationally possible.

If not, this should be an explicit baseline adaptation with a sensitivity check.

For a project whose central object is generalization, changing the distribution used to train augmentation-based generalization methods is particularly easy for a reviewer to question.

---

# 16. Time-limit semantics remain inconsistent across method families

The current protocol explicitly preserves a split:

- some SAC-style methods bootstrap through the artificial 500-step truncation;
- most imported methods treat it as terminal.

Door doesn't normally terminate when success occurs, so this horizon boundary appears in essentially every episode.

The methods therefore learn different value targets at the same target-environment boundary.

The standard distinction is that artificial truncation of a continuing task should bootstrap, while a genuinely finite-horizon task requires the remaining time to be represented if the state is to remain Markov. 

Preserving native source behavior is one possible fidelity policy.

It still confounds the twelve-way comparison.

At this stage I would not settle it by doctrine. Run a small sensitivity experiment on representative methods.

If the effect is negligible, document that.

If large, either harmonize target truncation semantics or make the system-level comparison framing explicit.

---

# 17. The protocol hash still does not identify the experiment strongly enough

The documentation describes protocol hashing in terms strong enough to imply materially result-changing settings are represented.

They are not all represented.

Examples omitted from the protocol identity include settings such as:

- replay capacity;
- on-policy process/environment counts;
- rollout/update schedule;
- optimizer epochs/minibatches;
- IBAC β;
- PPG phase schedule;
- architecture choices;
- augmentation partition;
- several learning rates and intrinsic coefficients.

Thus these pairs can potentially share the same high-level comparability hash:

```text
DrQ 300k replay
DrQ 620k replay
```

or:

```text
PPG 8 envs
PPG 16 envs
```

or materially different IBAC configurations.

The concept needs splitting.

Use a **comparison-protocol ID** for shared scientific conditions.

Separately use a **resolved training-lineage ID** covering the exact per-baseline executable configuration.

The latter should hash the resolved argv/config, source/payload, host profile, assets and runtime.

---

# 18. Lightweight record provenance does not yet consistently contain the complete effective configuration

The run-manifest machinery is significantly improved: it captures payload hashes, asset information, environment/container state, resolved packages and effective configuration.

But that information doesn't flow uniformly into all lightweight result records.

The training-record normalization path stores a smaller `run_provenance` object and omits some of the effective configuration that the manifest contains.

Offline evaluator enrichment uses a different placement/schema for provenance.

That means downstream aggregation can encounter two result records that look similarly normalized but have different levels/locations of lineage information.

Fix this before the paper data exist.

Every final evaluation row should lead canonically to:

```text
checkpoint hash
training run ID
exact effective training config
source/payload hash
asset identity
host/runtime identity
comparison-protocol ID
evaluator revision
evaluation condition
```

The fact that the full manifest exists somewhere is weaker than making the join obligatory.

---

# 19. The source is still not frozen, and the source-lock root is stale relative to the artifact

The current artifact reports over a hundred uncommitted paths.

The source-freeze gate correctly fails.

There is also a mismatch between the artifact's base commit and the root identifier stored in the source lock.

Before production, create one exact immutable tree that is the thing being reviewed and run.

Avoid a situation where:

- nested baseline commits are precisely pinned;
- patches are precisely enumerated;
- but the root orchestration/evaluator/protocol tree remains an uncommitted workspace.

The root code now carries enough scientific semantics that its identity is just as important as the baseline clones.

---

# 20. Placement proof should be tested from outputs, not code structure

This applies beyond CTRL.

Current gates have become sophisticated about looking for:

- condition seeding;
- diagnostic fields;
- strict regime checks;
- provenance keys.

But several of the failures across these versions arise because all the appropriate statements were present while the state-machine behavior differed.

The production condition-pairing gate should eventually be one integration test:

For every evaluator family, run e.g. 3 short episodes under one common condition schedule and emit:

```text
family
episode condition ID
realized door pose
realized robot initial state
scene
physical state hash
```

Then assert equality where the protocol claims pairing.

That's a better oracle than eleven family-specific source recognizers.

---

# 21. Shared evaluator validation is currently effectively reset to zero

The production gate itself now says there are **0/12 validated baselines under the current evaluator revision**.

That is appropriate.

The evaluator changed in scientifically relevant ways:

- condition seeding;
- strict checks;
- provenance;
- deterministic-kernel policy;
- CTRL reward fix;
- placement diagnostics;
- PPG collection behavior;
- family/profile hashing.

Old native/common comparisons do not fully validate the current instrument.

Before production I would require at least one competent current checkpoint for each distinct evaluator family.

Where a native evaluator exists, compare.

Where one doesn't, compare fixed-observation policy outputs and a matched short rollout.

Chance-level agreement isn't useful.

---

# 22. Deterministic-kernel enforcement is another evaluator adaptation worth validating

The common evaluator now asks PyTorch for deterministic algorithms.

That's reasonable for reproducibility.

But it may differ from the exact computation performed by the native evaluator.

I don't expect this to be a major performance changer, but because the common evaluator is publication infrastructure, freeze that choice and include it in the native/common validation.

Do not silently toggle it later because one GPU dislikes an operation.

---

# 23. The entire twelve-way comparison remains a systems comparison, not a clean algorithm ablation

Even after resolving all implementation defects, the families receive different effective experimental substrates.

Among other things:

- 1 vs 3 frames;
- 64 vs 84 vs cropped 100→84 pixels;
- \(\gamma=.99\) vs .999;
- reward normalization differences;
- artificial-horizon handling differences;
- replay vs synchronous rollouts;
- deterministic vs stochastic evaluation;
- different continuous distributions;
- different auxiliary training data.

That's acceptable if the intended object is:

> adapted methods as systems at their selected design points.

It isn't a causal experiment where “algorithm identity” is the only treatment.

The native five RL-ViGen methods remain a cleaner subgroup.

A particularly important qualification is that **PPG and IDAAC's own published continuous-control configuration uses three stacked frames**, which makes giving them a single frame less defensible as “native fidelity” than it first appeared.

---

# 24. The unsquashed Gaussian ports still deserve explicit action-saturation diagnostics

For a roughly standard Normal initialized independently across seven action dimensions:

\[
P(|a_i|>1)\approx31.7\%.
\]

Therefore:

\[
P(\text{any of 7 coordinates outside }[-1,1])
\approx93\%.
\]

So the environment can clip at least one action coordinate for roughly nine out of ten initial action vectors.

This is not automatically a PPO bug; unsquashed Gaussians plus action clipping have precedent.

But after categorical→continuous adaptation it is a major behavioral fact.

The newer diagnostics already move in the correct direction.

Keep both:

- per-coordinate clipping rate;
- whole-vector-any-clipping rate;
- log-std trajectory.

Do not interpret a floor-performing PPG/IDAAC/CTRL/IBAC run without inspecting them.

---

# 25. Evaluation mixes stochastic and deterministic behavioral estimands

The metadata now makes this more explicit.

Some baselines use mean/mode/deterministic actions.

PPG/IDAAC/IBAC/CTRL sample.

Those aren't identical policy estimands.

I would keep the fidelity-oriented/native behavior but add, where mathematically meaningful, a secondary standardized mean-action evaluation.

This can answer two different questions without pretending one is the other:

- How does the implementation normally act at evaluation?
- How good is its deterministic central policy under a common convention?

---

# 26. The final statistical protocol is still not frozen

The gates correctly leave several items OWNER:

- headline estimand;
- checkpoint rule;
- training seed policy;
- statistical protocol;
- scope.

Resolve these before final results arrive, not after.

In particular:

**Don't use OOD scenes to choose the best checkpoint** if those same scenes are the reported test result.

Use the predeclared 600k-ish endpoint as primary, or create an independent validation criterion.

**Don't treat evaluation episodes as independent training replicates.**

Three training seeds can establish coarse differences but are weak for fine rankings. Five or more would be preferable for main ranking claims if compute permits. Small-run deep-RL rankings are known to be unstable, motivating interval/probability-based reporting rather than overinterpreting point estimates.

---

# 27. Raw-return “retention” should not be the primary generalization statistic

A quantity such as

\[
R_{\mathrm{OOD}}/R_{\mathrm{train}}
\]

changes if an arbitrary constant is added to the reward function.

Door has shaped reward and a nonzero random-policy floor.

So raw return ratio lacks a clean behavioral interpretation.

Success rate should probably be the primary outcome where possible.

Useful views include:

- train success;
- OOD success;
- absolute success drop;
- raw return;
- perhaps floor-adjusted dense-return retention.

And separate:

- visual/appearance generalization;
- scene generalization;
- joint scene+appearance shift.

That decomposition also clarifies how to resolve the cross-scene condition-seeding issue.

---

# 28. ALDA currently looks comparatively coherent

I did not find an analogous major baseline-handicap defect in the inspected ALDA path.

ALDA is already a continuous-control/SAC-family method, and its Door adaptation preserves much more of the natural source semantics than the categorical Procgen imports.

The visible target configuration is reasonably aligned with the official ALDA family defaults.

That does **not** make its current results production-valid yet, because the common evaluator has to be validated under the current revision and the final runtime still needs a production canary.

But ALDA is not currently where I would spend algorithm-port debugging effort.

---

# 29. RAD/SODA likewise have relatively straightforward continuous-action adaptation

Their main remaining concerns are elsewhere:

- SODA's Places distribution;
- exact common evaluator validation;
- one-extra-transition accounting from the inclusive loop;
- runtime freeze.

The DMC-style trainer can execute approximately `train_steps + 1` transitions while labeling the terminal point `train_steps`.

That's tiny relative to 600k, but the actual sample count should be recorded accurately.

---

# 30. The native RL-ViGen five are approaching actual production eligibility

Assuming the final V100 profile really uses ~620k replay, the most important previous resource distortion for these methods disappears.

Their comparison is also the cleanest structurally:

- same target family;
- similar observations;
- same task/horizon;
- common action family;
- largely shared training substrate.

I would make DrQ-v2 the first final-platform anchor.

Before the fleet:

1. run a known competent checkpoint through the **current** evaluator;
2. reproduce it under the exact final V100 container/render stack;
3. verify its observation fingerprint and result;
4. run one short final-profile training canary;
5. then use it as the benchmark/runtime anchor.

This is especially worthwhile because the earlier apparent checkpoint failure turned out to be a rendering/runtime effect.

---

# 31. The final runtime needs to be treated as part of the experiment

The repository has improved here by pinning an actual CUDA container digest rather than only a mutable tag.

Continue that discipline through:

- MuJoCo;
- robosuite;
- RL-ViGen;
- Python packages;
- rendering backend;
- driver/GPU metadata where material;
- external Places asset;
- observation fingerprint.

The old renderer discrepancy is direct evidence that this isn't generic reproducibility bureaucracy. It can change the result dramatically with identical weights.

---

# What I would do before final production

At this point I would **not** start another broad code-quality campaign. The marginal issues are specific.

In order:

1. **Fix CTRL's double-reset evaluator state machine.**
2. **Decide/fix CTRL's online JAX evaluation-key interaction.**
3. **Fix IBAC 16-process physical RNG seeding after fork.**
4. **Decide a coherent IBAC author lineage and revalidate β/entropy under it.**
5. **Instantiate the actual V100 schedule/config—not a conceptual host override.**
6. **Keep 620k+ replay for the native five.**
7. **Restore the source-intended Places distribution.**
8. **Run PPG current vs authors' published continuous-control design-point pilot.**
9. **Run IDAAC current Procgen-port vs authors' published continuous-control design-point pilot.**
10. **Resolve the cross-scene physical-condition design according to the actual scene estimand.**
11. **Make physical placement diagnostics mandatory when claiming paired conditions.**
12. **Validate all distinct common-evaluator families under the current evaluator revision.**
13. **Create exact resolved training-lineage hashes/manifests.**
14. **Unify lightweight training/offline result provenance.**
15. **Commit and freeze the exact root tree.**
16. **Run time-limit sensitivity on representative methods.**
17. **Freeze endpoint, metric and statistical policies.**
18. **Run final-profile canaries.**
19. **Then launch the expensive seeds.**

## Baseline-by-baseline production status

| Baseline | Status |
|---|---|
| DrQ-v2 | **Nearly ready** after final V100/runtime/evaluator anchor |
| DrQ | Nearly ready with same final-profile validation |
| CURL | Nearly ready; be precise about RL-ViGen implementation identity |
| SVEA | **Blocked by Places distribution/final validation** |
| SGQN | Places/data-stream validation + final canary |
| RAD | Comparatively clean; current evaluator/final runtime canary needed |
| SODA | **Places issue** + final canary |
| ALDA | Comparatively clean; current evaluator validation needed |
| PPG | **Not ready: design-point/schedule decision remains** |
| IDAAC | **Not ready: continuous-control design point + level construct remain** |
| CTRL | **Hard blocked by current evaluator double reset** |
| IBAC-SNI | **Hard blocked by final multiprocessing RNG + unresolved coherent source lineage** |

## What changed most in this version

Some earlier high-risk problems are genuinely gone:

- PPG's continuous KL reduction is repaired.
- IDAAC's worker-constant level identity is repaired.
- CTRL raw-return normalization is repaired.
- remote evaluator provenance payload coverage is repaired.
- intended native replay can now be preserved on the larger host.
- source/runtime/provenance instrumentation is appreciably stronger.

The main concern has moved.

It is now less:

> “Does the code basically work?”

and more:

> **“Does each final row correspond to a defensible version of the named algorithm, evaluated under the exact condition the record claims?”**

PPG and IDAAC are the clearest examples because the authors themselves supplied continuous-control precedents substantially different from your current Procgen-derived ports. IBAC-SNI is still more fundamental: its current implementation chooses pieces from different author branches, and the intended 16-worker target execution introduces a physical-RNG problem that the one-worker pilots cannot reveal. CTRL has a much simpler situation: there is a concrete evaluator state-machine bug that should just be fixed.

I would therefore withhold the final fleet, but I would **not** describe the whole project as generally unready anymore. The native RL-ViGen/RAD/ALDA side is approaching production-shaped validation. The remaining scientific risk is disproportionately concentrated in the imported on-policy baselines and in ensuring that the shared evaluator/provenance system reports what actually happened rather than what its seed/config metadata intended to happen.
