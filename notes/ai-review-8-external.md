I would still **not authorize the final production run** from this version.

This version has repaired a meaningful fraction of the previous audit. The remaining problems are now concentrated enough that they can be stated more sharply. I found three kinds:

1. direct correctness bugs in the current evaluator/remote path;
2. baseline implementations whose current production configuration is not yet scientifically defensible as the named baseline;
3. provenance/protocol machinery that can certify materially different experiments as equivalent.

The most serious new result of this audit is **IBAC-SNI**. On inspection of the actual runnable source and the authors' configurations, its current state is substantially less faithful than the project documentation implies.

I did not complete literally every possible line-by-line comparison before the tool window ended, particularly the deepest remaining CTRL/ALDA mathematical-source comparison. What follows covers the important executable paths and the highest-risk baseline adaptations I was able to establish.

## Production verdict

| Component | Verdict |
|---|---|
| 600k production schedule | Now corrected |
| PPG continuous KL | Fixed |
| IDAAC episode identity | Fixed at implementation level |
| Strict scene/regime checking | Improved |
| Common placement seeding | Improved, **but broken for CTRL and likely PPG provenance path** |
| CTRL offline return | **Wrong units** |
| CTRL evaluation RNG isolation | **False** |
| PPG evaluator placement witnesses | **Broken** |
| Remote offline evaluation payload | **Currently broken** |
| IBAC-SNI implementation/config | **Not scientifically valid as presently configured** |
| PPG schedule fidelity | **Major unresolved adaptation** |
| IDAAC schedule/config fidelity | **Major unresolved adaptation** |
| RL-ViGen replay semantics | Still altered in currently executable DataSphere profile |
| Places365 augmentation distribution | Still altered |
| Time-limit semantics | Still inconsistent |
| Run/protocol provenance | **Insufficient** |
| Shared evaluator validation | Incomplete |
| Final statistical/estimand protocol | Not frozen |
| Overall | **NO-GO** |

# 1. CTRL's reported return is currently wrong

This is a direct measurement bug.

The common CTRL evaluator constructs:

`RLViGenVecEnvCustom(...)`

without disabling reward normalization.

That wrapper defaults to:

`normalize_rewards=True`

and wraps the environment in `VecNormalize`.

The evaluator then adds the **returned normalized reward** to the episode return.

That is not what the other evaluators report. In particular, the IDAAC path deliberately reaches into `VecMonitor` and reports raw episode return.

CTRL's own standalone evaluator also constructs its vector environment with reward normalization disabled and reports monitored raw return.

So under the present common evaluator:

> **CTRL return is not in Door reward units and cannot be compared numerically with the other eleven methods.**

This is an absolute production blocker.

The fix should not just set a flag and move on. Add a regression test in which reward normalization demonstrably transforms a synthetic reward and verify that the reported evaluation return remains the unnormalized value.

---

# 2. CTRL's supposedly paired episode conditions are not actually paired

There is a state-machine error in the evaluator.

The CTRL vector environment automatically resets an environment when its step returns terminal. Its internal reset increments the episode-condition counter.

But the common evaluator then explicitly calls `env.reset()` again at the beginning of the next measured episode.

The resulting sequence is approximately:

```text
measured episode 0 → condition 0
terminal auto-reset → condition 1 discarded
explicit reset
measured episode 1 → condition 2
terminal auto-reset → condition 3 discarded
explicit reset
measured episode 2 → condition 4
...
```

The result record, however, describes measured episodes as conditions:

```text
0, 1, 2, ...
```

So after episode zero:

- the physical conditions are not those recorded;
- CTRL is not paired with the other baselines;
- half the generated reset conditions are thrown away.

The production pairing gate currently misses this because it inspects the seeding expressions rather than exercising the environment state machine.

This is a good example of why the final pairing test must compare **realized physical initial states**, not merely seed arguments.

Fix either the auto-reset behavior or the evaluator's explicit reset scheme. Then run an integration test asserting equal physical placement hashes across families for episode indices 0…N.

---

# 3. CTRL online evaluation still changes subsequent training

The project now saves and restores NumPy state around CTRL evaluation.

That fixes only part of the problem.

CTRL stochastic actions use a JAX PRNG key. During training, that key is used for action sampling.

Online evaluation then calls the same action-selection function with the **same evolving key** and replaces it with the returned split key.

Only NumPy state is restored afterwards.

Thus:

\[
K_{\text{training after eval}}
\ne
K_{\text{training without eval}}.
\]

Consequently evaluation changes subsequent training actions even when the target environment's NumPy state is perfectly restored.

The current production gate nevertheless certifies CTRL evaluation isolation because it tests only for the NumPy save/restore mechanism.

This is another false-green gate.

The correct repair is simple: give evaluation its own independent JAX PRNG stream, or disable online evaluation completely.

The correct test is stronger:

> start two identical short CTRL runs; insert evaluation into only one; verify that the subsequent training actions, resets and parameter updates remain identical.

---

# 4. The PPG common evaluator's placement-witness collection is broken

PPG's target wrapper correctly accumulates placement witnesses when episodes reset.

But `run_scene_ppg()` copies:

```python
LAST_PLACEMENT_WITNESSES.extend(
    getattr(venv, "_placement_witnesses", [])
)
```

**before** it rolls the requested evaluation episodes.

`extend()` copies the elements present at that moment. It does not retain a reference to the live list.

Subsequent resets append into the environment's list, not into `LAST_PLACEMENT_WITNESSES`.

The rollout then executes afterwards.

Therefore the recorded witness collection cannot reliably contain the requested measured episodes.

There is another wrinkle: PPG's Roller advances in chunks, so it may generate/reset beyond the exact requested terminal episode. The final implementation should associate witness \(i\) explicitly with completed episode \(i\), rather than copy whatever happens to be in the wrapper list.

The placement-witness integration contract should be exercised with `episodes > 1`; a one-episode smoke test can conceal this class of bug.

---

# 5. “Placement witness” is still weaker than the project claims

The evaluator has machinery for extracting actual realized placement state, which is good.

But the wrappers allow physical-placement diagnostics to be unavailable, in which case evaluation can continue with an observation-derived witness.

An observation hash is not a physical placement witness.

The same robot/door placement under two different visual regimes can yield different image hashes. Conversely, an image hash provides no direct decomposition of which underlying physical variables differ.

For production paired evaluation I would require, not merely optionally collect:

- door pose/state;
- robot initialization variables relevant to the task;
- scene;
- episode condition seed;
- stable hash of those physical quantities.

Then assert cross-family equality for every intended paired condition.

If the wrapper architecture hides those variables, propagate them through the wrappers.

---

# 6. The current remote evaluator payload is actually broken

This isn't hypothetical.

The evaluator revision hash now includes:

`rlgen/protocol.py`

but the DataSphere payload allowlist does not include that file.

A real IDAAC remote revalidation job subsequently failed because the evaluator could not find `rlgen/protocol.py`.

So the present remote production/evaluation bundle cannot execute its own provenance scheme.

Add the file to the contract, version/bump the payload contract, rebuild from scratch and rerun the revalidation.

This is another case where a file-list/unit contract passed while the complete deployed artifact did not.

---

# 7. IBAC-SNI is presently the largest baseline-validity problem

My previous audit focused too much on its entropy coefficient.

The deeper inspection shows a much larger problem.

The present launcher selects approximately:

```text
--use_bottleneck
--sni_type vib
--model_type impala
--entropy-coef 0.0
```

but does **not** pass `--beta`.

The runnable PyTorch IBAC-SNI branch has:

\[
\beta = 1.0
\]

as its default.

Its PPO loss adds:

\[
\beta D_{KL}
\]

directly to the objective.

The authors' demonstrated settings are dramatically different.

Their reproducible GridWorld VIB-SNI command uses approximately:

\[
\beta=10^{-6}.
\]

Their principal CoinRun IBAC-SNI configuration uses approximately:

\[
\beta=10^{-4},
\]

along with twelve bottleneck samples, weight decay and data augmentation. These are documented in the authors' repository. 

So the current production port uses a VIB coefficient:

- **10,000× the CoinRun value**;
- **1,000,000× the GridWorld value**.

That alone is enough for me to reject the current IBAC-SNI result.

And it is not the only discrepancy.

## The current IBAC-SNI is a hybrid of two author implementations

It combines:

- the CoinRun-style IMPALA visual trunk;
- the PyTorch/MiniGrid branch's bottleneck implementation;
- that branch's 64-dimensional latent bottleneck;
- a single VIB sample;
- the newly authored continuous Gaussian action head;
- an authored `entropy_coef=0` adaptation;
- drastically reduced process count.

The CoinRun configuration instead uses a 256-dimensional VIB representation and twelve bottleneck samples, plus the aforementioned regularization/augmentation choices.

Even the VIB scale parameterization differs between the branches.

So selecting `model_type=impala` does **not** make this “the paper's CoinRun IBAC-SNI configuration.” It selects one architectural component of it.

The present method is better described as:

> an authored hybrid continuous-action IBAC-SNI adaptation combining parts of the authors' PyTorch and CoinRun implementations.

That could still be a reasonable experiment. But it is nowhere near sufficient for reviewer-resistant “IBAC-SNI baseline” status yet.

### What I would do

Choose one explicit reference definition before doing more IBAC runs.

Either:

**A. PyTorch/GridWorld lineage**

Preserve that implementation's VIB/SNI semantics and use its demonstrated \(\beta \approx 10^{-6}\), while documenting the visual/continuous adaptations.

Or:

**B. CoinRun headline lineage**

Port the actual CoinRun IBAC-SNI semantics: IMPALA, \(\beta\approx10^{-4}\), appropriate bottleneck dimensionality, multi-sample mechanism, regularization/data augmentation where applicable, and then make only the target-required continuous-action adaptation.

Given that the present port deliberately selected the CoinRun IMPALA architecture, B is arguably the more internally coherent reference.

But **before doing anything else, remove \(\beta=1\).**

The previous “entropy 0.01 causes log-std explosion; entropy 0 avoids it” experiments were conducted in a system simultaneously carrying this enormous VIB coefficient. They do establish something about the entropy term, but they do not validate the resulting baseline.

---

# 8. PPG's schedule is still radically retimed

The continuous KL correction is now good.

The remaining problem is more fundamental.

The original PPG configuration has:

- 64 environments per MPI rank;
- documented launch with four MPI processes;
- rollout 256;
- `n_pi=32`.

That gives approximately:

\[
4\cdot64\cdot256=65,536
\]

global interactions per PPO iteration.

An auxiliary phase every 32 PPO iterations therefore corresponds to roughly:

\[
32\cdot65,536
=
2,097,152
\]

interactions.

The current production configuration is:

\[
1\cdot8\cdot256=2,048
\]

interactions per PPO iteration.

Thus the first auxiliary phase comes at:

\[
32\cdot2,048=65,536
\]

interactions.

That is a **32× phase-frequency shift in environment-interaction units**.

At the common 600k budget:

- source-scale PPG has not reached its first auxiliary phase;
- current PPG has performed roughly nine.

That is not a minor batch-size difference.

The defining idea of PPG is precisely the policy/auxiliary-phase schedule.

So the project needs to choose what “600k PPG” is supposed to mean.

There are several legitimate choices, but they answer different questions:

**Preserve source iteration semantics:** keep `n_pi=32`; current smaller batches make PPG much more auxiliary-heavy per environment interaction.

**Preserve source interaction semantics:** rescale `n_pi` upward so auxiliary phases occur with approximately the original sample frequency.

**Preserve source physical parallelism:** restore ~256 global envs, likely impractical.

**Treat 600k as target-specific tuning:** choose the phase schedule for Door under a declared tuning procedure.

What is not legitimate is treating `num_envs` as merely a machine-resource knob and then presenting unchanged `n_pi=32` as fidelity.

The intended V100 profile apparently raises PPG from 8 to 16 environments. That reduces the discrepancy but doesn't solve it: one rank × 16 environments still makes auxiliary phases roughly 16× more frequent in interaction-count terms than the documented four-rank source configuration.

Official PPG documentation confirms the multi-process invocation. 

---

# 9. IDAAC has the same retiming problem, although less spectacularly

Original repo-style IDAAC uses roughly:

\[
64\times256=16,384
\]

transitions per outer rollout/update.

Current DataSphere production uses:

\[
4\times256=1,024.
\]

So outer training phases occur **16× more frequently per environment interaction**.

The proposed V100 profile raises this to 16 processes, but that's still a 4× schedule shift.

This matters because IDAAC's value/auxiliary structure is scheduled in update units, not in a magically sample-invariant continuous time.

There is an additional scientific complication.

The official repository is Procgen-focused and describes its defaults as Procgen settings. 

But the IDAAC paper also contains continuous-control experiments. The supplement describes continuous-control experiments using three stacked frames and a different hyperparameter search regime rather than simply carrying the Procgen configuration over unchanged. 

The present Door version instead uses:

- one 64×64 frame;
- Procgen-like gamma/LR/epochs;
- reduced process count.

That isn't necessarily wrong. It means the project has chosen:

> a port of the author's Procgen implementation to continuous Door

rather than:

> the author's continuous-control IDAAC design point applied to Door.

Given the stated concern about handicapped baselines, I would compare those two plausible references before freezing IDAAC.

---

# 10. IDAAC's episode-ID repair solves an implementation error, not the conceptual transfer problem

The previous worker-constant `level_seed` was clearly wrong.

The new episode-scoped identity is internally coherent: temporal-order pairs no longer cross unrelated episodes under one permanent worker label.

But Procgen's `level_seed` represents a persistent procedural-level identity.

“Current Door episode” is not the same construct.

So the IDAAC invariance mechanism now learns something like:

> distinguish information invariant to time within this particular rollout instance

rather than its original notion of level-specific nuisance information.

That's a target-specific reinterpretation.

It may be the best available mapping. But if IDAAC performs badly, the conclusion cannot automatically be:

> IDAAC doesn't generalize to Door.

A competing interpretation is:

> the benchmark does not expose a natural analogue of the latent level identity used by IDAAC's defining invariance mechanism.

That distinction belongs in the eventual scientific interpretation.

---

# 11. Current production replay still changes all five native RL-ViGen methods

The executable DataSphere profile uses replay capacity around:

\[
300,000
\]

for the five RL-ViGen off-policy methods.

The intended original/source-scale capacity is at least 1M in the relevant implementation family.

At a 600k run:

- 1M retains all experience;
- 300k discards roughly the first half by the end.

So the sampled training distribution changes after 300k.

This affects five methods:

DrQ-v2, DrQ, SVEA, SGQN and CURL.

The intended V100 profile apparently restores 1M because the host has much more RAM.

That's the correct direction.

The problem is that the V100 profile currently exists as a proposed configuration, not as the actual executable production profile.

Do not launch the DataSphere-safe 300k version as final data.

And don't manually edit this when moving to V100. Make host profile an explicit resolved production manifest that gets hashed into the run lineage.

---

# 12. Places365 still uses the wrong partition

The project still rewrites the visual augmentation loaders from the intended Places training distribution to the validation split.

That affects the methods whose robustness mechanism explicitly uses external visual augmentation.

This is not a filesystem adaptation.

It changes the augmentation distribution.

RL-ViGen's setup expects the standard Places dataset for these visual methods. 

If the V100 environment has sufficient disk/resources, restore the intended source distribution.

I see little scientific justification for deliberately using the smaller validation subset in the final experiment if the only reason is operational convenience.

---

# 13. The protocol hash does not hash the experiment

This is a structural production issue.

`Protocol.hash()` claims to identify the protocol sufficiently for comparability.

But it omits many settings that currently move the result:

- replay capacity;
- environment/process count;
- rollout/update batch;
- PPO epochs/minibatching;
- PPG auxiliary schedule;
- IBAC \(\beta\);
- IBAC entropy;
- architecture selection;
- learning rate;
- Places partition;
- reward normalization;
- several other intrinsic algorithm settings.

Consequently these materially different runs can currently carry the same protocol/comparability hash:

```text
PPG 8 envs
PPG 16 envs
```

and:

```text
DrQ 300k replay
DrQ 1M replay
```

and potentially:

```text
IBAC beta = 1
IBAC beta = 1e-4.
```

That is precisely what the provenance mechanism should prevent.

I would not solve this by requiring all twelve algorithms to have identical hyperparameters. They shouldn't.

Use two identities:

**comparison-protocol hash**

Common scientific conditions: task, budget, action repeat, horizon, evaluation cells, seed policy, metric definitions, etc.

**resolved training-lineage hash**

Exact baseline-specific executable configuration: argv, environment count, rollout, optimizer, gamma, architecture, replay, entropy/beta, assets/data split, code/payload hash, runtime/container, etc.

A paper cell needs both.

---

# 14. Evaluated checkpoints currently have weak linkage back to their exact training configuration

The common evaluator records useful things such as:

- checkpoint SHA;
- evaluator revision;
- baseline/family;
- seed/frame;
- condition information.

That's good.

But a checkpoint hash tells you **which bytes were evaluated**, not what experiment created those bytes.

The current lineage needs a stronger binding:

```text
evaluation record
→ checkpoint hash
→ immutable training run ID
→ resolved training manifest
→ exact payload/source hashes
→ runtime profile
→ external assets
```

This becomes particularly urgent now because the project has:

- DataSphere-safe profiles;
- intended V100 profiles;
- unresolved source dirtiness;
- augmentation corpus adaptations.

Without the full join, the final table can contain a perfectly identified checkpoint whose generating training protocol is ambiguous.

---

# 15. The current source lock does not identify the actual current source tree

The artifact reports:

- base commit `12f6322...`;
- 79 uncommitted paths.

The source lock contains a different historical root identifier.

So neither one by itself identifies the runnable project I just audited.

The frozen-source production gate catches the dirty state, which is appropriate.

However, `apply_patches.py --check` contains another misleading behavior: when Git/reference information is unavailable it says undeclared-modification checking is abstained, but still ultimately emits language equivalent to:

> vendored tree matches pinned commit plus exactly declared differences.

That conclusion is not licensed after abstention.

Make it fail or say only:

> declared patches appear present; absence of undeclared changes was not checked.

For final production, commit the exact reviewed tree, tag it and build payloads only from that state.

---

# 16. The V100 “production profile” is not yet a production configuration

The project recognizes that DataSphere limits forced substantial changes and records intended larger-host settings:

- IBAC processes: 1 → 16;
- IDAAC: 4 → 16;
- PPG: 8 → 16;
- replay: 300k → 1M.

This is useful planning.

But at the moment the executable family descriptors remain the DataSphere-safe versions.

So there are effectively two experiments:

**the tested one**, with scientifically problematic resource reductions;

and

**the intended final one**, which has not gone through the same integrated validation.

That second configuration has to become code before final canaries.

Do not regard “we intend to use 16 processes on V100” as satisfying a gate.

The exact host profile needs to be generated, stamped and exercised.

---

# 17. The artificial-time-limit discrepancy remains scientifically material

Three families bootstrap through the 500-step Door limit; most others treat it as terminal.

Door apparently does not naturally terminate on success, making the 500-step limit the dominant termination mechanism.

Thus the methods are learning different target semantics at every episode boundary.

For an artificial truncation of a continuing task, standard RL treatment is to bootstrap through the truncation. If the horizon is intrinsic to the task, then time-to-go becomes part of the state needed for a Markov finite-horizon formulation. 

Preserving native handling remains a defensible *fidelity* decision.

But it is a nontrivial *comparability* confound.

I would run a representative sensitivity experiment rather than trying to resolve this philosophically from source provenance alone.

If the effect is negligible, you have evidence.

If it changes results materially, the final paper should either harmonize target semantics or explicitly treat the systems as different design points.

---

# 18. The common table still mixes deterministic and stochastic policies

The evaluator records this more clearly now, but the issue remains.

RL-ViGen/DMC-style methods generally use deterministic evaluation actions.

PPG, IDAAC and IBAC-SNI use sampled actions.

CTRL currently samples as well.

CTRL is especially ambiguous because its online reporting path samples but its standalone evaluation implementation uses greedy evaluation.

So there is no obvious single “native” answer.

This is not necessarily something to harmonize away.

But a table column called “return” is mixing:

\[
J(\pi)
\]

for stochastic policies with something closer to:

\[
J(\text{mode/mean}(\pi))
\]

for others.

I would report the policy estimator explicitly.

For continuous methods, I would strongly consider a secondary standardized mean-action evaluation alongside the fidelity/native evaluation.

---

# 19. Unsquashed continuous Gaussian behavior remains an important adaptation property

The imported on-policy methods initialize unsquashed Gaussian policies at approximately \(\sigma=1\), with environment-side action clipping.

For one coordinate:

\[
P(|a_i|>1)\approx0.317.
\]

Across seven independent coordinates:

\[
1-(1-0.317)^7
\approx0.93.
\]

So initially roughly **93% of action vectors** have at least one coordinate outside the legal action range before clipping.

Meanwhile PPO computes likelihood for the pre-clipped action.

This is a historically common continuous-PPO construction, so I am not calling it an implementation error.

But it is a large behavioral feature of the categorical→continuous ports.

The current diagnostics should record:

- fraction of individual coordinates clipped;
- fraction of entire vectors clipped anywhere;
- log-std trajectory;
- action norm/saturation.

If a method remains near floor while clipping 90%+ of its actions, that fact needs to precede algorithmic interpretation.

---

# 20. The full twelve-way comparison still needs appropriately weak causal language

This remains true despite implementation improvements.

The families differ systematically in:

- one vs three frames;
- 64 vs 84 vs 100→84 image geometry;
- gamma;
- reward normalization;
- rollout/update schedule;
- replay distribution;
- time-limit treatment;
- action parameterization;
- stochastic vs deterministic evaluation;
- auxiliary data.

Therefore the full table measures:

> **performance of twelve adapted algorithm systems at their selected design points under a common target interaction/evaluation framework.**

It does not isolate:

> **the causal effect of twelve generalization mechanisms with all other conditions equal.**

That isn't fatal.

In fact, trying to force identical architecture/hyperparameters can handicap methods more severely.

But the distinction should shape the paper.

The five native RL-ViGen baselines form a considerably cleaner internal comparison once full replay is restored.

---

# 21. IDAAC's continuous-control precedent makes the one-frame choice more contestable than before

This deserves emphasis.

The current IDAAC port uses a single 64×64 frame because that follows the Procgen source family.

But IDAAC's own continuous-control experiments used three stacked frames according to the supplementary material. 

So a reviewer could reasonably say:

> Why did a continuous-control IDAAC baseline receive the Procgen visual-input convention instead of the authors' continuous-control convention?

There may be a defensible answer.

But this is exactly the sort of choice I would resolve experimentally before final production rather than answer retrospectively after seeing a weak IDAAC score.

---

# 22. Training-seed policy is better, but three runs remain weak for fine rankings

The production schedule now uses fixed seeds rather than an outcome-adaptive “give more runs to methods that look promising” scheme.

That's an important improvement.

Three independent training runs are still thin for fine ordinal comparisons in deep RL.

Evaluation episodes estimate a given trained policy. They do not replace independent training replicates.

RLiable's general warning remains applicable: small-run RL point estimates can be unstable, and interval/probability-style analysis is preferable to overinterpreting simple rankings. 

For obviously separated results, three may suffice to establish a coarse effect.

For claims such as “A consistently outperforms B,” I would prefer five or more where feasible.

---

# 23. The proposed raw-return retention ratio remains a poor primary metric

A ratio

\[
R_\text{OOD}/R_\text{train}
\]

changes if a constant is added to the reward function.

Door has shaped reward and a meaningful nonzero floor.

So the ratio doesn't have a clean behavioral interpretation.

Success rate is considerably easier to interpret.

I'd use:

- success rate as primary;
- raw return as secondary;
- absolute train→OOD success drop;
- perhaps floor-adjusted dense-return retention as an auxiliary diagnostic.

Also keep appearance shift and scene shift separate. Pooling ten scenes in the numerator against training scene 0 in the denominator conflates different generalization dimensions.

---

# 24. Do not select the best checkpoint on the final OOD grid

The project can retain intermediate checkpoints across the methods now.

Good.

Use 600k endpoint as the primary predeclared result unless there is an independently defined validation criterion.

If the ten reported evaluation scenes are inspected across checkpoints and the best checkpoint is selected, those scenes have become model-selection data.

Then the resulting OOD score is optimistic.

Curves can still be reported descriptively.

---

# 25. The final runtime environment remains part of the scientific object

The earlier large DrQ-v2 discrepancy was eventually attributed to rendering/runtime rather than checkpoint corruption.

That is strong evidence that observation generation is sensitive enough that “same checkpoint and code” does not define the experiment.

The final run manifest should therefore bind:

- container digest, not merely tag;
- package resolution;
- MuJoCo/robosuite version;
- RL-ViGen revision;
- rendering backend;
- relevant GPU/driver metadata;
- external assets such as Places;
- a deterministic observation fingerprint under a known condition.

Robosuite's current release history/configuration can be externally pinned as well. 

---

# 26. A genuine external RL-ViGen anchor is still worth doing

Evaluator agreement with your own native implementation establishes evaluator consistency.

It does not establish that the overall simulator/training/runtime is reproducing the intended benchmark regime.

Given how large the renderer effect was, one well-understood external/native Door reproduction is high-value.

I would do it before the fleet.

Not because every baseline must reproduce a paper number exactly, but because otherwise a common environment-level deviation can contaminate all twelve while remaining internally consistent.

---

# Per-baseline status after this audit

| Baseline | Status |
|---|---|
| **DrQ-v2** | Close after final runtime freeze and 1M replay restoration. Best candidate for benchmark anchor. |
| **DrQ** | Similar; 300k current replay must not become final production by accident. |
| **CURL** | Similar; preserve precise identity as RL-ViGen's CURL implementation/design point. |
| **SVEA** | Full replay + correct Places distribution required. |
| **SGQN** | Same; worker/data-stream adaptation should be checked after fixing Places split. |
| **RAD** | Comparatively clean. Need current evaluator revalidation/runtime freeze. |
| **SODA** | Correct Places distribution plus production-shaped canary important because of runtime cost. |
| **ALDA** | No large new algorithm bug found in the inspected path, but current evaluator revision still needs a full canary/parity run. |
| **PPG** | Continuous KL now repaired. Major unresolved 16–32× schedule retiming remains. Not final-ready. |
| **IDAAC** | Old episode-ID bug repaired. Process/update retiming and Procgen-vs-DMC reference choice remain major. Not final-ready. |
| **CTRL** | **Currently invalid evaluator:** normalized return + double reset; training evaluation also perturbs JAX RNG. Not final-ready. |
| **IBAC-SNI** | **Largest algorithm blocker:** β=1 plus hybrid implementation has no close relation to demonstrated author settings. Do not run final production in this state. |

# What I would fix before spending more large-scale compute

In strict priority order:

1. **IBAC-SNI β/reference implementation.** Do this before another long IBAC run.
2. **CTRL raw evaluation reward.**
3. **CTRL double-reset/placement alignment.**
4. **CTRL separate evaluation JAX PRNG stream.**
5. **PPG placement-witness collection.**
6. **Remote payload inclusion of `rlgen/protocol.py`.**
7. **Build the actual V100 production profile as executable configuration.**
8. **Restore 1M replay on that profile.**
9. **Restore the intended Places training split.**
10. **Resolve/test PPG's phase schedule rather than treating env count as throughput-only.**
11. **Run IDAAC configuration/schedule sensitivity, including the authors' continuous-control precedent.**
12. **Strengthen physical-placement provenance and cross-family integration tests.**
13. **Validate every common evaluator on the current evaluator revision.**
14. **Replace the incomplete Protocol hash with resolved training-lineage hashing.**
15. **Commit and freeze the exact tree and runtime.**
16. **Resolve the time-limit sensitivity.**
17. **Freeze endpoint/metrics/statistical protocol.**
18. **Run production-shaped canaries of every materially different family.**
19. **Then launch final seeds.**

The order matters. There is little value in spending 600k frames establishing IBAC-SNI competence while its bottleneck coefficient is between four and six orders of magnitude away from the authors' demonstrated values, or validating CTRL statistics while its evaluator is summing normalized rewards.

## The largest change in my assessment

The project is now better enough that the critical risks are more visible.

I am **less worried than before about generic implementation sloppiness**. Several real problems were repaired correctly.

I am **more worried about baseline-fidelity decisions being mistaken for resource configuration**.

PPG, IDAAC and IBAC-SNI demonstrate the issue particularly clearly. For synchronous on-policy algorithms, changing environment count while leaving “every N updates do X” unchanged does not merely make the program slower or faster. It changes how often algorithmic mechanisms operate per unit of experience.

IBAC-SNI goes beyond that: the current implementation has effectively assembled a new variant from different branches of the authors' code while retaining a default bottleneck coefficient utterly unlike either authors' demonstrated configuration.

Those are precisely the issues a technically careful reviewer could use to argue that poor imported-baseline performance is not evidence about the original method.

Conversely, I do **not** think the answer is “harmonize everything.” Making PPG, IDAAC, CTRL and the RL-ViGen SAC family use identical frames, gamma, optimizers and action distributions would create another set of handicapped baselines.

The defensible strategy is narrower:

> preserve or deliberately map each method's defining learning semantics; hold the actual target experiment/evaluation construct common; explicitly classify unavoidable target adaptations; and bind the exact resolved variant to every reported result.

This version is closer to being able to do that. It is not there yet, chiefly because of **IBAC-SNI, PPG/IDAAC schedule semantics, three concrete CTRL bugs, current replay/Places resource adaptations, and incomplete experiment lineage**.

Those are the areas I would work on now rather than adding more generic test/documentation machinery.
