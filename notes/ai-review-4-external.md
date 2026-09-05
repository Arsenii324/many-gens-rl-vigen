I re-audited the newer artifact from the executable production path outward rather than assuming the previous findings persisted. Several earlier defects have been repaired. The current state is still **not ready for the final production sweep**, but the reasons are now narrower and more substantive: some production specifications disagree with the code, and several baseline adaptations materially alter learning dynamics in ways that could support a “handicapped baseline” criticism.

My production decision would be: **do not launch the final 12-method reviewer-facing sweep yet. Targeted pilots and sensitivity runs are appropriate.**

The most important finding is that the remaining risks are no longer mainly ordinary coding errors. They are concentrated in **batch/update semantics, target-specific adaptations, replay/augmentation distributions, and what the 12-way comparison actually estimates**.

## What has actually been fixed

I checked these rather than relying on the project documents.

The previous PPG KL problem is fixed. `runnable/ppg/phasic_policy_gradient/ppg.py` now detects vector-valued continuous-action KL and sums across action dimensions before averaging. That preserves the scalar role the original categorical PPG cloning KL had much better than the previous `.mean()` over seven dimensions. The original PPG code indeed uses a scalar-per-sample KL mean. ([GitHub][1])

The previous IDAAC worker-constant `level_seed` defect is also fixed. `_LevelSeed` is now episode-scoped rather than assigning every episode in one worker the same pseudo-level. That removes the clearly invalid cross-episode temporal-order comparisons I identified previously.

The common evaluator now reseeds Door placement per measured episode after setup/probes, and regime/scene verification is strict rather than fail-open. CTRL checkpoint reconstruction is now bound to the checkpoint configuration rather than a duplicate evaluator-default dictionary. The IDAAC evaluator no longer silently hardcodes CPU. Selected-scene shortcuts have been eliminated. Online evaluation has generally been disabled or isolated. IBAC-SNI has also been moved onto the Impala architecture from its own source family instead of the inappropriate MiniGrid-style hybrid.

Those are real corrections.

They expose the next layer more clearly.

# A. Hard production blockers

## 1. The production schedule does not describe the intended experiment

The most immediate blocker is mundane but serious.

`datasphere/native/production-schedule.json` still schedules **500,000 frames** for all twelve long runs.

The current evaluation protocol and production reasoning use **600,000 Door frames**. `plan_production.py` itself says to regenerate the schedule with `--frames 600000`.

The same stale schedule still recommends 25k online evaluation intervals even though the actual family configurations have moved away from online evaluation to prevent evaluation RNG from altering training.

So there is currently no single frozen answer to:

> What exactly is the production experiment?

Do not launch until the schedule is regenerated from one authoritative production manifest and the old settings are removed rather than merely superseded in prose.

This is exactly the sort of defect that produces perfectly valid runs of the wrong experiment.

---

## 2. The source tree is dirty, while the “source frozen” gate falsely passes

The review artifact identifies itself as:

> `Tree Dirty: True (52 uncommitted paths)`

yet `production_gates.py::gate_source_tree_frozen()` reports the source tree as clean in this artifact.

The reason is itself a gate bug: it runs `git status --short`, ignores the subprocess return code, and interprets empty stdout as a clean repository. In the review artifact `.git` is absent, so Git fails and produces no stdout; the gate converts failure-to-check into PASS.

This is a genuine false-green production check.

Before production:

* establish one committed production tree;
* tag/hash it;
* make failure to establish Git state fail closed;
* bind the run manifest to that exact tree/patch state.

The current gate output of 12 PASS / 2 FAIL / 8 OWNER already says “not launchable,” but one of the apparent PASSes is itself invalid.

---

## 3. CTRL's claimed online-evaluation RNG isolation is incomplete

This is a new concrete code defect.

`runnable/ctrl/train_ppo.py` saves and restores NumPy RNG state around ID/OOD evaluation. That protects Door/reset randomness.

But CTRL's stochastic evaluation actions use the **same JAX PRNG key** used by training:

```python
action, key = select_action(..., key, sample=True)
```

`select_action()` splits that key.

Therefore inserting online evaluation changes the JAX key from which subsequent **training actions** are sampled.

The production metadata claims online evaluation is RNG-isolated, and the production gate currently checks only for NumPy state preservation, so it falsely certifies this case.

Either disable CTRL online evaluation entirely for production or create a separate evaluation JAX key. Then test the actual invariant:

> same training seed, with vs without evaluation inserted → identical subsequent training action/state sequence.

Until then, CTRL's training trajectory depends on its evaluation cadence.

---

## 4. IDAAC's actual production hyperparameters contradict the project's fidelity analysis

This is one of the most important issues in the current tree.

The actual production descriptor launches IDAAC with approximately:

* 4 processes;
* 256 steps;
* 8 minibatches;
* \(\gamma=0.999\);
* LR \(5\times10^{-4}\);
* one PPO epoch.

The original Procgen repository defaults are 64 processes, 256 steps, \(\gamma=0.999\), LR \(5\times10^{-4}\), etc.

But your own current `FAITHFULNESS.md` also identifies a **published continuous-control IDAAC configuration** using approximately:

* rollout 2048;
* \(\gamma=0.99\);
* LR \(3\times10^{-4}\);
* ten PPO epochs;
* associated DAAC/IDAAC auxiliary scheduling changes.

The same document then claims the current implementation matches several of those continuous-control values.

It does not.

The actual production launcher is essentially using the Procgen hyperparameter family after translating the action/environment, while simultaneously reducing parallelism from 64 processes to 4.

That is scientifically consequential because IDAAC was not only a Procgen method; its paper contains continuous-control experiments. The official repo itself is Procgen-oriented and describes its defaults as good Procgen settings. ([GitHub][2])

For a reviewer-facing continuous-control comparison, the existence of an author-published continuous-control configuration means there is a serious alternative reference point.

I would not choose one by intuition. Run a controlled IDAAC configuration comparison before production:

**A:** current repo-faithful Procgen-derived port;
**B:** continuous-control-paper-derived configuration.

Then decide the production policy using a predeclared criterion.

The present configuration is defensible only if explicitly described as such; the current documentation instead makes a factually incorrect fidelity claim.

---

## 5. PPG's defining learning schedule has been rescaled by roughly 32×

This is probably the largest PPG validity issue left.

The original OpenAI PPG setup uses 64 environments per MPI process and its documented invocation uses four MPI processes. With rollout length 256, one synchronized policy update corresponds to approximately:

$$
4\times64\times256 = 65{,}536
$$

environment interactions globally.

The production port uses:

$$
1\times8\times256 = 2{,}048.
$$

That is a **32× reduction in global rollout batch per update**.

`n_pi=32` has not been rescaled.

Therefore PPG's defining auxiliary phase now occurs after approximately:

$$
32\times 2{,}048 = 65{,}536
$$

target interactions, instead of the approximately:

$$
32\times65{,}536 \approx 2.1\text{M}
$$

global interactions implied by the source configuration.

This means the statement that “600k is sufficient because PPG gets about nine auxiliary phases” is not evidence of source fidelity. It is largely a consequence of having made the auxiliary phase about **32× more frequent in sample-count terms**.

It also changes:

* minibatch size;
* gradient noise;
* policy update frequency per collected frame;
* optimizer-step/sample relationship.

PPG is specifically about the temporal separation of policy and auxiliary phases, so changing that schedule is not peripheral.

The original implementation and paper confirm the phased structure and source defaults. ([GitHub][1]) More generally, PPO is not automatically batch-size invariant when batch size changes without compensating optimizer/update changes. ([arXiv][3])

I would require one of three things:

1. restore substantially closer rollout-scale semantics;
2. derive a principled rescaling of `n_pi`, minibatching and/or optimizer schedule;
3. explicitly treat the current version as a retimed PPG variant and perform a sensitivity experiment.

I would not put its current row into a paper as straightforward “PPG” without resolving this.

---

## 6. The RL-ViGen five now have a 300k replay buffer in a 600k experiment

This is another major learning-affecting production adaptation.

The production descriptor limits replay capacity to **300,000** because the intended source-sized buffer is too expensive in memory.

The original RL-ViGen-family configuration is around **1,000,000**.

At a 600k training budget:

* a 1M buffer retains effectively the entire run;
* a 300k buffer deletes the first half of experience.

That changes the sampling distribution seen by DrQ-v2, DrQ, SVEA, SGQN and CURL.

It is not merely a resource optimization.

More concerning, `audit_comparability_seam.py` still reasons that the nominal 1M capacity exceeds the 600k budget and therefore effectively gives whole-run replay. That audit is now false for the production configuration.

For reviewer-resistant results I would strongly prefer solving this at the systems level—more RAM, compression, storage changes that preserve sampling semantics—rather than altering the algorithm.

If 300k is unavoidable, perform a replay-cap sensitivity experiment on representative methods and declare it a target/platform adaptation.

This affects five baselines simultaneously, so it is high priority.

---

## 7. Places365 is using a different data distribution from the source

`configure_places365_val.py` rewrites the loaders from `use_val=False` to `use_val=True`.

This is not merely replacing a filesystem path.

It switches augmentation data from the intended Places training partition to the validation subset.

For SVEA/SODA/SGQN-style visual augmentation, the external image distribution is part of the learning mechanism. Reducing/changing its diversity can directly affect the methods whose central purpose is visual robustness.

RL-ViGen's public setup expects Places data for those augmentation methods. The project should either use the source-intended split or classify this as a learning-affecting adaptation and test its effect.

I would not ship a visual-generalization paper where the visual-generalization baselines receive a substantially altered augmentation corpus purely because the smaller corpus is operationally convenient.

---

## 8. ALDA's common evaluation path still has not been exercised end-to-end

The ALDA evaluator implementation looks plausible on inspection.

That is not enough.

The current owner-decision notes still identify `run_scene_alda` as the one common evaluator family that has not actually been exercised.

Since the production result depends on the authored common evaluator rather than merely native ALDA training code, the first actual execution of that path should not be in the expensive final sweep.

Run:

checkpoint → clean process → ALDA loader → one actual scene → full condition grid → result record

before production.

This is a straightforward hard gate.

---

## 9. The shared evaluator remains empirically reconciled for only a minority of families

The current evaluator audit has roughly:

* DrQ-v2: convincing agreement;
* IDAAC: broadly consistent, but much weaker evidence;
* remaining families: no strong native/common reconciliation.

The IDAAC numbers themselves are not especially close; the audit's “consistent” interpretation relies on weak variance information.

This is still too little validation for an instrument that will produce all twelve headline rows.

For each evaluator family I would require at least one competent checkpoint and either:

* common evaluator vs native evaluator under matched conditions; or
* if no useful native evaluator exists, fixed-observation action/distribution equivalence plus a short matched rollout.

Do not validate evaluators using chance-level policies. Agreement at the floor contains very little information.

---

## 10. IBAC-SNI's currently proposed configuration has escaped one pathology but has not established competence

The architecture correction is meaningful: using the Impala architecture from the appropriate source branch removes a serious previous mismatch.

Likewise, the `entropy_coef=0.01` continuous port had clear pathological behavior: exploding log standard deviation / entropy and no successes. Moving to `entropy_coef=0` prevents that runaway.

But the current zero-entropy configuration has only short evidence and has not demonstrated successful Door learning.

So the evidence currently says:

> `0.01` is bad for this continuous port; `0` avoids that specific pathology.

It does **not** yet say:

> `0` is a sound continuous IBAC-SNI adaptation.

Before a final production run, run a sufficiently long pilot to cross the expected learning onset and show that the corrected architecture/configuration has a plausible learning trajectory.

If it remains at floor, the interpretation must distinguish “algorithm fails” from “continuous adaptation is still not functioning.”

---

# B. A major family-wide problem: resource changes have changed the algorithms

This deserves separate treatment because three of the imported on-policy methods have been made operationally smaller in a way that changes learning dynamics.

## IDAAC

Source-style:

$$
64\times256=16{,}384
$$

samples per rollout.

Current:

$$
4\times256=1{,}024.
$$

That's a 16× reduction.

## PPG

As above, approximately 32× smaller global rollout under the documented multi-rank source setup.

## IBAC-SNI

Source default is approximately 16 processes × 128 frames = 2048 samples.

Current production uses one process × 128 = 128 samples.

That's another 16× reduction.

For IBAC-SNI, batch size remains 256, so a 128-sample rollout changes the minibatch/update structure as well.

## CTRL

Source default uses 64 environments.

Production uses 16.

That's a 4× change.

These decisions arose from real resource constraints: EGL/multiprocessing problems, clustering divisibility, memory and CPU limits.

But the scientific category is still:

> **learning-dynamics adaptation.**

“Number of environments” is not simply a throughput knob for synchronous PPO-like algorithms. It determines the on-policy batch distribution and update cadence.

This is the biggest class of potential reviewer criticism in the newer version.

A production protocol needs to state how parallelism changes are treated. Ideally, preserve the effective rollout/update schedule even if physical execution uses fewer simultaneous processes—for example by accumulating equivalent rollout volume before updating where algorithmically possible.

---

# C. IDAAC's `level_seed` is no longer broken, but its construct validity remains unsettled

The previous implementation was wrong because the “level” was permanently tied to worker identity.

The new episode-scoped identity fixes that internal inconsistency.

But there remains a deeper question.

IDAAC's original mechanism exploits Procgen's persistent **level identity**: multiple observations can be associated with the same generated level while varying in time/state.

Door does not naturally expose that construct.

An episode ID is not equivalent to a Procgen level ID. It says “these observations belong to one rollout instance,” which is at least internally coherent, but it changes what the invariance discriminator means.

With only four parallel environments, the diversity structure of that discriminator also differs substantially from the original.

Therefore I would now classify IDAAC as:

* no longer obviously incorrectly implemented;
* still a **nontrivial target reinterpretation** of the level-invariance mechanism.

That's acceptable research if explicitly stated. It weakens any claim that poor performance directly measures “IDAAC's generalization ability.”

---

# D. The 12 methods still optimize different effective MDPs at the time limit

The project still has roughly:

* three methods that bootstrap through the 500-step time limit;
* nine methods that treat it as terminal.

Door does not terminate upon success; the main termination is the externally imposed episode horizon.

So the methods disagree about whether that final transition is:

**a true terminal state**, or
**an artificial truncation of a continuing process**.

This directly changes value targets.

The standard treatment is not ambiguous in principle: artificial time limits on continuing tasks should be bootstrapped through; alternatively, if finite horizon is intrinsic to the task, remaining time belongs in the state. ([arXiv][4])

Preserving each source's handling can be defended under “native-design-point port.”

It is not a controlled algorithm comparison.

Because this occurs on every episode, I consider it too large to leave as a buried implementation detail.

At minimum run a sensitivity experiment on representative on-policy and off-policy methods. Better is to define target-environment truncation semantics once.

---

# E. The full twelve-way result is still not an isolated algorithm comparison

This is not something you necessarily have to “fix.” It needs to determine the claim.

The methods currently receive materially different inputs:

| Family                        | Typical temporal input |  Resolution |
| ----------------------------- | ---------------------: | ----------: |
| RL-ViGen five                 |               3 frames |          84 |
| RAD / SODA                    |               3 frames | 100→84 crop |
| ALDA                          |               3 frames |          64 |
| PPG / IDAAC / CTRL / IBAC-SNI |                1 frame |          64 |

Three-frame methods receive motion/history information that one-frame methods do not.

Other systematic family differences include:

* \(\gamma\approx0.99\) vs \(0.999\);
* reward normalization vs raw reward;
* squashed/truncated vs unsquashed Gaussian action distributions;
* different time-limit bootstrapping;
* different update batch sizes;
* native deterministic vs stochastic evaluation.

No amount of additional seeds removes these confounds.

Therefore the defensible twelve-way estimand is something like:

> performance of twelve adapted method systems under their selected implementation design points at a common 600k Door interaction budget.

It is **not**:

> causal ranking of the twelve algorithmic ideas under otherwise identical conditions.

The five native RL-ViGen methods form a much cleaner internal comparison and can support stronger language.

I would make that distinction visible in the result structure rather than relegating it to limitations.

---

# F. Initial action clipping is extreme in the continuous on-policy ports

PPG/IDAAC/CTRL/IBAC-SNI use unsquashed Gaussian policies and rely on environment/controller clipping to [-1,1].

At initialization with roughly \(\sigma=1\):

$$
P(|a_i|>1)\approx31.7\%
$$

for one coordinate.

With seven independent action dimensions:

$$
P(\text{at least one coordinate clips})
=
1-0.6827^7
\approx93.1\%.
$$

So initially about **93% of action vectors** are expected to have at least one coordinate changed before execution.

The PPO-style log probability is calculated for the pre-clipped action, whereas the environment acts on the clipped one.

Some continuous PPO implementations do use this arrangement, so I would not call it automatically erroneous.

But in these categorical-to-continuous ports it is a major behavioral feature, and IBAC-SNI has already shown that policy-scale behavior can become catastrophic.

Production diagnostics should record at least:

* fraction of coordinates clipped;
* fraction of action vectors with any clipping;
* mean/max log standard deviation.

If one of these baselines performs poorly, a squashed-Gaussian or lower-initial-variance sensitivity run would be scientifically informative before attributing failure to the method.

---

# G. Evaluation still mixes different policy estimands

The newer version correctly records the evaluation policy mode. That is an improvement.

But the final table would still combine:

* deterministic/mean policies for some methods;
* sampled stochastic policies for PPG, IDAAC, CTRL, IBAC-SNI.

Expected return under a stochastic policy and return of the policy mean are not the same estimand.

For publication I would ideally report two views where meaningful:

1. **native estimator**, preserving each implementation's normal evaluation behavior;
2. **standardized deterministic continuous-action estimator**, using mean actions where mathematically defined.

If you retain one mixed table, the estimator needs to be visible as part of baseline identity.

---

# H. DMC-GB evaluation preserves native +42 visual seeding, so the visual conditions are not fully paired across families

For RAD/SODA, `eval_grid.py` deliberately uses the DMC-GB convention:

```text
train: seed
eval:  seed + 42
```

for visual-randomization RNG.

Door placement is separately controlled with the common condition seed.

So the newer evaluator now pairs the **Door physical placement**, but it does not necessarily pair the complete visual intervention across RL-ViGen/DMC-GB/other families.

This is reasonable if preserving native DMC-GB evaluation is the goal.

It means “common random numbers across methods” should not be claimed for the entire rendered condition.

A clean approach is to separate:

* native evaluator parity test using +42;
* final common comparison using a common visual-condition seed and recorded visual condition where possible.

---

# I. The retention metric still needs to be redesigned before becoming a headline

The protocol still contemplates:

$$
\text{retention}
=
R_{\mathrm{eval}} / R_{\mathrm{train}}.
$$

Door has dense shaped reward and a nonzero random-policy floor.

A ratio of returns is not invariant to an additive reward offset. If the reward function were shifted by a constant without changing any behavior, the retention ratio would change.

That makes it a weak headline generalization measure.

The unresolved denominator issue compounds this:

* denominator = train appearance, scene 0;
* numerator potentially averages randomized appearance across scenes 0–9.

That conflates visual generalization and scene/geometry generalization.

You already collect enough data to avoid this.

I would report separately:

**appearance robustness:** scene 0 train appearance → scene 0 held-out appearance;

**conditional appearance robustness:** within each scene, train-style → held-out visual condition;

**scene generalization:** scene 0 → other scenes under a fixed appearance regime;

**joint shift:** scene + appearance shift.

For Door, success rate and absolute success-rate loss are cleaner primary behavioral statistics. Dense return can remain secondary.

If a retention ratio is retained, floor-adjusting it is more meaningful:

$$
\frac{R_{\rm eval}-R_{\rm floor}}
     {R_{\rm train}-R_{\rm floor}},
$$

with the usual caution near a weak denominator.

---

# J. Three training seeds are enough for coarse effects, not confident fine rankings

The newer production schedule appears to use fixed seeds 1/2/3, which is substantially better than the previously contemplated outcome-adaptive seed allocation.

Keep the fixed allocation.

But twenty evaluation episodes across multiple scenes do not create additional independent algorithm runs. The outer experimental unit for learned-policy variation is the **training seed**.

Deep-RL comparisons with few runs can have unstable point estimates, which is why robust interval/probability-of-improvement style reporting has been advocated. ([arXiv][5])

Three seeds can distinguish “learns consistently” from “at floor” or very large effects.

They are weak for claims like:

> method A ranks second and B ranks third.

For important main-table comparisons, five independent training seeds would be substantially preferable if compute permits.

If only three are affordable, use uncertainty-conscious language and avoid ordinal overinterpretation.

---

# K. Do not select the best checkpoint on the reported OOD grid

The project can now retain intermediate checkpoints for all twelve, which is useful.

But the checkpoint selection rule is still not fully frozen.

The safest primary result is the **predeclared endpoint** at 600k.

If you inspect the ten held-out scenes and choose whichever intermediate checkpoint has the highest mean OOD score, those evaluation scenes become a validation set rather than a test set.

Then the reported number is optimistically selected.

Use checkpoint curves descriptively, or define a separate validation criterion that is independent of the final reported OOD grid.

---

# L. There is still no strong external RL-ViGen reproduction anchor

The current DrQ-v2 common-vs-native evaluator agreement says:

> our evaluator behaves similarly to the native evaluator.

It does not say:

> our full benchmark/runtime/training pipeline reproduces the expected RL-ViGen behavior.

Given the previous renderer discrepancy—which changed performance drastically with identical weights—an external anchor is particularly worthwhile.

Before spending the whole fleet, reproduce at least one well-understood RL-ViGen Door reference result under matched enough conditions to establish that the simulator/render/runtime pipeline is in the expected regime.

This need not become the paper's central result. It is a benchmark sanity anchor.

---

# M. The exact renderer/runtime needs stronger freezing than a CUDA image tag

The old apparent checkpoint failure turned out to be an environment/rendering mismatch rather than stale weights.

That is useful evidence: renderer identity is load-bearing.

The source lock currently includes a container tag such as:

`nvidia/cuda:12.2.2-runtime-ubuntu22.04`

A mutable tag is weaker than an image digest.

Production artifacts should bind at least:

* immutable container digest;
* Python package lock/resolved versions;
* MuJoCo;
* robosuite;
* RL-ViGen revision;
* relevant rendering backend;
* ideally GPU/driver metadata;
* a known observation fingerprint from a fixed environment state.

Otherwise “same code and checkpoint” does not guarantee the same observation distribution.

---

# N. Checkpoint round-trip should remain universal despite the renderer explanation

The previous dramatic DrQ-v2 discrepancy was not checkpoint corruption.

That doesn't remove the value of the test.

For every baseline before production:

$$
\text{live policy}
\rightarrow
\text{save}
\rightarrow
\text{fresh process}
\rightarrow
\text{load}
$$

should reproduce fixed-observation policy outputs.

For stochastic policies compare distribution parameters, not separately sampled actions.

This is especially worthwhile for:

* custom CTRL serialization;
* pickled whole-model PPG/IDAAC paths;
* anything with normalizers or preprocessing state.

---

# O. Several current project documents describe the retired implementation rather than the production one

This has become scientifically dangerous because some of the stale claims are precisely about fidelity.

For example, sections of `FAITHFULNESS.md` still reason about the retired shared `rlgen/trainer_onpolicy.py`/`configs/vigen.yaml` implementation and make claims such as current IDAAC rollout/LR/gamma matching a continuous precedent.

The production descriptor actually invokes the hermetic `runnable/idaac` source tree and disagrees with those claims.

Similar PPG sections describe old shared-port values rather than the current original-source-based PPG path.

`RUNNABLE-ORIGINALS.md` also contains stale descriptions of IDAAC instance identity from before the episode-ID fix.

This isn't just documentation untidiness. A reviewer packet generated from those files could make false statements about the code that produced the results.

Before freezing production:

> generate the fidelity/config table from the actual `families.json` + launch command + source defaults rather than maintaining those numbers independently in prose.

---

# P. The provenance registry itself is slightly behind the actual patch set

The source-lock records accepted patches P1–P18 while `apply_patches.py` includes P19, and current production behavior depends on that later worker-count adaptation.

Likewise some descriptions of which methods consume Places365 are stale.

Again, this is not an RL failure by itself. But if the goal is reusable reviewer-facing evidence, the provenance machinery cannot lag the actual patches.

Freeze exact applied patch identities per baseline.

---

# Per-baseline assessment

| Baseline     | My present assessment                                                                                                                                                   |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DrQ-v2**   | Closest to production-ready. Replay-cap change still material; use as external/runtime anchor.                                                                          |
| **DrQ**      | Similar. Main concern is 300k replay cap and general runtime provenance.                                                                                                |
| **CURL**     | Similar operationally; be precise that this is the RL-ViGen implementation/design point rather than implicitly canonical CURL. Replay cap applies.                      |
| **SVEA**     | Replay cap **plus Places validation-split change**, both learning-affecting. Not final-ready.                                                                           |
| **SGQN**     | Same replay issue; Places/worker-stream behavior needs verification where used.                                                                                         |
| **RAD**      | Generally cleaner; common evaluator validation and DMC visual-seed semantics remain.                                                                                    |
| **SODA**     | Places validation split is material; very long runtime makes production-shaped canary especially important.                                                             |
| **ALDA**     | Common evaluator path still unexercised; cannot approve final run until exercised.                                                                                      |
| **PPG**      | KL repair is correct, but 32× rollout/phase rescheduling is a major fidelity issue. Not final-ready.                                                                    |
| **IDAAC**    | Episode identity bug repaired, but production hyperparameters conflict with continuous-control precedent and docs; level construct is target-authored. Not final-ready. |
| **CTRL**     | Concrete JAX evaluation-key contamination; 4× rollout reduction; modern JAX/Flax port and continuous head are substantial adaptations. Not final-ready.                 |
| **IBAC-SNI** | Architecture corrected, but 16× process/rollout reduction and entropy adaptation remain; current corrected version has not established competence. Not final-ready.     |

The likely cleanest scientific result today is the RL-ViGen-native subgroup **after resolving the 300k replay cap**.

The imported Procgen/generalization methods require more care before their relative performance should be interpreted.

# What I would do next, in order

I would avoid another broad refactoring cycle. The remaining work can be relatively targeted.

1. **Freeze the production experiment.** Pick 600k or 500k; based on the present protocol it appears intended to be 600k. Regenerate schedule and remove stale online-evaluation recommendations.

2. **Commit/freeze the tree and repair the frozen-source gate.** Any inability to inspect Git state must fail.

3. **Fix CTRL's JAX key isolation** and add an actual with/without-eval trajectory-equivalence test.

4. **Resolve replay capacity for the RL-ViGen five.** Prefer preserving full-run replay rather than accepting 300k.

5. **Restore the intended Places training distribution** unless there is a strong reason not to.

6. **Run the PPG schedule sensitivity before full PPG production.** This is more important than another generic PPG unit test.

7. **Run IDAAC source-default vs continuous-control-derived configuration pilot.** Stop claiming the current configuration matches the latter until it does.

8. **Run a meaningful IBAC-SNI pilot** on the corrected architecture/entropy setting.

9. **Exercise ALDA's common evaluator and validate all evaluator families.**

10. **Make a decision on artificial-horizon bootstrapping.** At least conduct representative sensitivity if preserving native divergence.

11. **Freeze the estimands:** success/return, appearance vs scene shift, endpoint checkpoint, native vs standardized policy estimator.

12. **Freeze fixed training-seed replication.** Prefer ≥5 for main claims if affordable; do not outcome-adapt seed count after observing first runs.

13. **Run one production-shaped canary per materially different runtime/resource family**, especially replay-growing RL-ViGen/SODA, PPG's late auxiliary cycles, IBAC-SNI and CTRL.

14. **Only then launch the fleet.**

## What I would *not* block production over

I would not require all twelve algorithms to have identical:

* observation resolution;
* architectures;
* reward normalization;
* gamma;
* policy distributions;
* optimization schedules.

Trying to harmonize all of those can destroy the very algorithms being compared.

But retaining those differences changes the claim from “controlled algorithm ablation” to “comparison of adapted method systems.”

That is a valid experiment if represented accurately.

I also would not make the extraction's full `pytest` failure a production blocker by itself. Several failures here result from the review artifact not containing the complete external repository context or from this environment lacking legacy `gym`/DMC dependencies. The important problem is the **substantive false-green gates**, especially source freezing and CTRL RNG isolation.

# Bottom line

The new version resolves a meaningful portion of the previous audit. I would no longer identify the old PPG KL bug, IDAAC cross-episode worker identity, evaluator placement probe, fail-open regime check, CTRL reconstruction defaults, or IDAAC CPU evaluation as outstanding blockers.

The remaining highest-risk problems are more important scientifically:

1. **PPG has been retimed by roughly 32× through rollout-size reduction.**
2. **IDAAC production is using a Procgen-derived optimization regime despite a relevant continuous-control precedent, while the documentation currently says otherwise.**
3. **The RL-ViGen five discard half the 600k experience through the new 300k replay cap.**
4. **Visual-augmentation methods use the Places validation subset instead of the source training distribution.**
5. **CTRL online evaluation still changes the training JAX PRNG trajectory despite being declared isolated.**
6. **IBAC-SNI's corrected continuous version has not yet demonstrated competence.**
7. **Artificial time-limit semantics remain inconsistent across families.**
8. **The shared evaluator is not sufficiently validated across the whole set, and ALDA's path remains unexercised.**
9. **The production schedule, source freeze and some fidelity documents disagree with the code that would actually run.**
10. **The final estimand/statistical protocol is not yet frozen.**

If those are resolved, I would be much more comfortable authorizing the expensive production run.

The important shift from the previous version is that I would now spend almost no effort on adding generic scaffolding or more broad tests. The marginal work should be **a small number of discriminating experiments and exact production-contract repairs**: PPG batch/schedule, IDAAC configuration, replay cap, Places split, IBAC competence, time-limit sensitivity, evaluator parity, and CTRL RNG isolation. Those are the places most capable of changing either the eventual numbers or what the numbers legitimately mean.

[1]: https://github.com/openai/phasic-policy-gradient "https://github.com/openai/phasic-policy-gradient"
[2]: https://github.com/rraileanu/idaac "https://github.com/rraileanu/idaac"
[3]: https://arxiv.org/abs/2110.00641 "https://arxiv.org/abs/2110.00641"
[4]: https://arxiv.org/abs/1712.00378 "https://arxiv.org/abs/1712.00378"
[5]: https://arxiv.org/abs/2108.13264 "https://arxiv.org/abs/2108.13264"

