I would still make the current decision **NO-GO for the final production fleet**, although it is substantially closer.

I inspected the current executable tree, ran the production gates, ran targeted code/tests where useful, and traced several state-machine paths rather than relying on the repository's static audits. The project's current production gate itself reports **23 PASS, 3 FAIL, 11 OWNER** and `NOT LAUNCHABLE`.

More importantly, I found one new **hard IDAAC correctness defect**, one unresolved **hard IBAC V100 execution/RNG defect**, and one concrete mismatch between a supposedly settled production decision and the executable production configuration.

I did not exhaustively execute all full RL training/evaluation combinations—the complete test surface is slow and parts of this review environment lack legacy dependencies such as `gym`. The targeted tests I ran did not expose unrelated failures before timing out. The findings below come from direct executable-path inspection and several targeted executions, including reproducing the IDAAC storage problem.

# Bottom line

The remaining hierarchy is roughly:

| Severity | Problems |
|---|---|
| **Hard blocker** | IDAAC episode identity is still misaligned in the actual VecEnv→storage pipeline |
| **Hard blocker** | IBAC 16-process V100 configuration currently cannot run and has invalid physical RNG initialization |
| **Hard blocker** | Exact production source tree is not frozen |
| **Hard blocker** | Current common evaluator revision has 0/7 evaluator-family validations |
| **Production-spec bug** | A20 says 3 curve episodes; executable family configs run 5 |
| **Major fidelity risk** | PPG update/auxiliary schedule is a target-specific retimed variant |
| **Major fidelity risk** | IDAAC is far from the authors' published continuous-control design point |
| **Major fidelity risk** | IBAC-SNI remains a hybrid of different author branches |
| **Major port-semantic risk** | CTRL representation learning consumes requested Gaussian actions, not necessarily actions actually executed after clipping |
| **Major unresolved condition** | Final V100 profile is not yet the exact frozen/canaried experiment |
| **Major unresolved condition** | Places365 validation split changes augmentation distribution |
| **Comparability issue** | Artificial-horizon treatment differs across families |
| **Protocol issue** | High-level protocol hash does not identify many result-changing baseline settings |
| **Preproduction requirement** | Production renderer/runtime not yet validated |
| **Preproduction requirement** | No current-pipeline external RL-ViGen anchor |
| **Unfrozen science** | Headline estimand, stats, checkpoint rule, scope remain open |

Several previous blockers are genuinely gone. I would no longer block production on the old PPG KL problem, CTRL normalized rewards, CTRL double-reset bug, remote omission of `rlgen/protocol.py`, or final replay capacity for the native five.

---

# 1. New hard blocker: IDAAC's episode-scoped `level_seed` repair does not survive the actual rollout pipeline

This is the most important new finding.

The current `_LevelSeed` wrapper correctly creates a new level ID at every environment reset:

`runnable/idaac/ppo_daac_idaac/envs.py:104–116`

That was intended to fix the previous problem where multiple independent Door episodes were treated as the same IDAAC “level.”

But the wrapper's `step()` attaches:

```python
info["level_seed"] = self._level_seed
```

to the transition that just occurred.

Then the Baselines `DummyVecEnv` behavior matters.

When an environment terminates, `DummyVecEnv.step_wait()`:

1. obtains `(obs, reward, done, info)` from the terminal transition;
2. sees `done=True`;
3. calls `env.reset()`;
4. replaces `obs` with the **new episode's initial observation**;
5. returns that new observation together with the **old terminal transition's info**.

That is the standard Baselines implementation. 

Your IDAAC trainer then does:

```python
obs, reward, done, infos = envs.step(action)

levels = torch.LongTensor(
    [info["level_seed"] for info in infos]
)

rollouts.insert(..., obs, ..., levels, nsteps)
```

So at an episode boundary:

> `obs` belongs to new episode B, while `level_seed` still identifies old episode A.

It gets worse inside the original IDAAC storage code.

`IDAACRolloutStorage.insert()` writes:

```python
self.obs[self.step + 1].copy_(obs)
...
self.step = (self.step + 1) % self.num_steps
self.levels[self.step + 1].copy_(levels)
self.nsteps[self.step + 1].copy_(nsteps)
```

The level/nstep write therefore has an additional index relationship that isn't equivalent to simply annotating the just-written observation.

I executed the current storage code with a forced synthetic episode transition. It produced:

```text
idx   obs   level   nstep
0       0      10      0
1       1      20      3
2       2      10      1
3     100      10      2
4     101      10      0
5     102      20      1
6     103      20      2
```

where observations 100+ represented the new episode.

So the supposed invariant:

> observations carrying the same IDAAC level ID never cross physical Door episodes

is **still false in the real collection pipeline**.

Your existing static/semantic tests do not exercise:

`_LevelSeed`
→ `DummyVecEnv terminal auto-reset`
→ `train.py`
→ `IDAACRolloutStorage.insert`
→ `before_update()` pairing.

They test already-aligned synthetic level labels.

This is a hard algorithm-validity blocker because the defining IDAAC order/invariance mechanism can still compare observations under an incorrect notion of “same instance.”

### Required fix

Write an integration test with a deliberately tiny horizon. Track an authoritative episode identity through the entire actual VecEnv and storage stack and assert, for every stored observation:

```text
stored obs
stored level
stored nsteps
true physical episode ID
```

Then require every pair created by `before_update()` with the same level to belong to the same true episode.

The implementation probably needs to propagate the **next episode's ID** with the auto-reset observation rather than relying on the old transition's `info`.

This issue should be resolved before choosing IDAAC hyperparameters, because currently the defining auxiliary mechanism itself is not operating on the intended equivalence classes.

---

# 2. IBAC-SNI's intended 16-process V100 configuration is currently unusable

The production gate catches the first half of this.

`runnable/ibac_sni/torch_rl/scripts/train.py` forces:

```python
multiprocessing.set_start_method("fork")
```

The project has already empirically observed the multi-process MuJoCo/EGL configuration die with an `EOFError`.

The V100 host profile nevertheless specifies:

```text
ibac_sni procs = 16
```

So the intended final configuration currently cannot run.

But there is a second problem even if the EGL crash is repaired.

The IBAC trainer seeds global NumPy once in the parent:

```python
numpy.random.seed(seed)
```

It constructs multiple live environments and calls:

```python
env.seed(args.seed + 10000 * i)
```

But the RL-ViGen adaptation's `_HWCFloat.seed()` is intentionally a no-op:

```python
def seed(self, seed=None):
    return []
```

The actual Door physical placement uses global NumPy.

`ParallelEnv` then forks worker processes from the already-seeded parent. Its `worker()` performs **no worker-specific NumPy reseeding**.

Thus the forked workers inherit the same global NumPy RNG state governing Door placement.

This can make the 16 ostensibly independent parallel environments start from correlated or identical physical-placement RNG streams.

The one-process pilots cannot reveal this.

### A switch to `spawn` alone isn't sufficient

The decision documentation suggests spawn might solve both EGL and RNG.

It may solve the fork/EGL problem.

It does not by itself establish the desired scientific RNG semantics.

With spawn, each process might simply get unrelated OS-initialized randomness rather than a deterministic stream derived from:

```text
training_seed × worker_index
```

And because live MuJoCo environments are currently passed into `Process`, they may not be cleanly picklable under spawn anyway.

The proper design is:

```text
worker starts
→ create environment inside worker
→ seed all physical RNGs explicitly using SeedSequence(base_seed, worker_id)
→ first reset
```

Then execute a real 16-process integration test and record the first several realized Door placements from every worker.

IBAC final production cannot precede that.

---

# 3. IBAC β is fixed, but the baseline remains an authored hybrid

The catastrophic previous default:

\[
\beta=1
\]

has been repaired. The current launcher explicitly uses approximately:

\[
\beta=10^{-4}.
\]

That's much more defensible.

However, current IBAC-SNI still combines:

- CoinRun-style IMPALA visual architecture;
- the authors' PyTorch/MiniGrid-side VIB machinery;
- 64-dimensional, single-sample bottleneck;
- CoinRun-like \(\beta=10^{-4}\);
- newly authored continuous Normal policy;
- target-specific `entropy_coef=0`;
- target-specific parallelism.

It therefore doesn't closely reproduce either one complete author configuration.

The project now acknowledges this as an authored hybrid, which is the correct description.

For publication, however, this remains a baseline-fidelity vulnerability. If IBAC scores poorly, “IBAC-SNI performs poorly” is stronger than the evidence licenses.

There should be one declared primary lineage.

Because this is a visual task and the current architecture already chooses IMPALA, the authors' main visual/CoinRun lineage is probably the more coherent reference. That would require considering its bottleneck sampling/dimensionality and other relevant regularization choices rather than importing only its β.

Also, repeat the small entropy sensitivity experiment **after** the final β/architecture/process configuration exists. The earlier `0.01` vs `0` evidence was collected under materially different settings.

---

# 4. Production says 3 curve episodes; executable production actually uses 5

This is a direct production-spec bug.

`notes/DECISION-SHEET.md` now says:

> A20 DECIDED — 3 episodes per stamp.

`run_probe.sh` defaults to:

```bash
${CURVE_EVAL_EPISODES:-3}
```

But every evaluator family's live `production` block in `datasphere/native/families.json` still contains:

```json
"curve_eval_episodes": 5
```

`family.py::production_env()` exports the family value.

So production doesn't use the shell fallback.

It runs **five episodes**, despite the supposedly frozen decision being three.

This changes the experiment and cost. It raises intermediate-grid evaluation workload by \(5/3\), about 67%; using the project's own estimates, it moves the trajectory-evaluation cost from roughly 176 GPU-hours back toward the older ~291 GPU-hour regime.

The current `schedule matches protocol` production gate still passes because it checks the 600k budget and online-evaluation settings but not the fully resolved curve configuration.

Fix the seven production blocks or revise A20.

Then strengthen the gate to compare the **resolved production environment** with the frozen protocol, rather than checking selected JSON fields.

---

# 5. The final V100 replay setting is now fine

This was a major issue in earlier versions and should now be removed from the blocker list.

The intended V100 profile gives the native RL-ViGen replay methods approximately:

\[
620{,}000
\]

capacity for a nominal 600k interaction experiment.

Accounting for reset/bootstrap overhead, the project's upper-bound reasoning leaves sufficient headroom.

So unlike the earlier 300k DataSphere profile, the final V100 run should not evict early experience.

For this experiment:

> 620k and 1M replay capacities are effectively behaviorally equivalent because neither becomes full.

I would not spend more effort restoring the nominal 1M merely for source-number fidelity.

What matters is ensuring the **actual final run really resolves to 620k**, rather than accidentally using the lower base profile.

---

# 6. The actual final V100 experiment still does not exist as one frozen executable object

This remains an important production-engineering/scientific issue.

The repository has:

- base DataSphere-safe family configurations that have seen more testing;
- a V100 host profile that overlays 16-process/16-env settings and larger replay;
- a production schedule that is still primarily expressed in the older scheduling model.

The V100 overlay changes algorithmic behavior for on-policy methods.

Therefore it is not merely deployment metadata.

Before production, generate an exact frozen manifest containing the final resolved settings for every baseline after applying the V100 host profile.

The canary must execute **that manifest**, not the base family configuration plus a manually remembered host override.

---

# 7. V100 changes the actual algorithm schedule for PPG

The current V100 PPG configuration is approximately:

\[
16\text{ envs}\times256\text{ rollout}
=
4096
\]

interactions per PPO policy iteration.

With:

\[
N_\pi=32,
\]

the auxiliary phase occurs every:

\[
4096\times32
=
131{,}072
\]

interactions.

The original OpenAI Procgen setup used approximately 64 envs per MPI rank and documented multi-rank execution. Under four ranks:

\[
4\times64\times256=65{,}536
\]

interactions per global policy iteration.

The auxiliary phase then occurs after approximately:

\[
2.1\text{M interactions}.
\]

So current Door PPG invokes its defining auxiliary phase roughly **16× more frequently per collected interaction** than that source-global configuration.

At 600k:

- that source schedule wouldn't yet run one PPG auxiliary phase;
- current Door PPG runs about four.

This is not a throughput detail.

## There is also a better comparison than literal Procgen PPG

IDAAC's published continuous-control appendix also evaluates PPG and gives a continuous-control recipe.

It uses 3-frame stacking, 2048-step rollouts, one process, 10 PPO epochs, entropy coefficient 0, LR \(3\times10^{-4}\), 32 minibatches, \(\gamma=.99\), linear LR decay, and PPG's \(N_\pi=32\), among other settings. 

That design implies an auxiliary phase about every 65.5k interactions.

So the current PPG is neither:

- literal original Procgen PPG;
- nor that published continuous-control PPG design point.

Its phase cadence is closer to the latter, while many other settings remain Procgen-derived.

The project now honestly calls current PPG a **retimed continuous-action port**. That's scientifically much better than pretending it is literal PPG reproduction.

But it remains one of the clearest possible “handicapped baseline?” attack surfaces.

### Before production

I would run a bounded pilot comparing:

**current port**  
vs  
**the published continuous-control PPG recipe adapted minimally to Door**.

Make the reference choice before seeing full production results.

---

# 8. IDAAC has an even stronger published continuous-control alternative

The same appendix is directly relevant to IDAAC.

The published continuous-control setup uses approximately:

- 3 stacked frames;
- 2048-step rollouts;
- one process;
- 10 PPO epochs;
- 32 minibatches;
- entropy coefficient 0;
- LR \(3\times10^{-4}\);
- \(\gamma=.99\);
- linear LR decay;
- its continuous-control IDAAC auxiliary coefficients/schedule. 

The intended Door V100 setup instead remains approximately:

- 1 × 64×64 frame;
- 16 × 256 rollouts;
- 1 PPO epoch;
- 8 minibatches;
- entropy .01;
- LR \(5\times10^{-4}\);
- \(\gamma=.999\);
- Procgen-derived auxiliary schedule.

These are substantially different learning systems.

The V100 process increase makes it less distorted than the former 4-process DataSphere profile, but still gives:

\[
16\times256=4096
\]

samples per rollout versus source Procgen's roughly:

\[
64\times256=16{,}384.
\]

So Procgen-style update events remain roughly four times more frequent per environment interaction.

Once the concrete episode-ID bug in §1 is fixed, I would consider the **choice of IDAAC reference configuration** the next highest scientific issue for that baseline.

---

# 9. The IDAAC `level_seed` concept itself remains a target reinterpretation

Even after fixing the concrete storage bug, “episode identity” is not the same construct as Procgen `level_seed`.

Procgen's identity describes a procedural level that can recur conceptually across observations.

The Door adaptation describes one physical episode.

That is a reasonable way to make the temporal-order machinery coherent, but it changes what IDAAC's invariance mechanism means.

This shouldn't block production by itself once correctly implemented.

It should constrain interpretation.

A poor IDAAC score would not cleanly establish that the original IDAAC generalization mechanism fails on Door; it could also mean Door lacks the latent-level structure that the original discriminator exploits.

---

# 10. New CTRL port-semantic concern: its representation learner sees pre-clipping actions, not executed actions

The direct CTRL evaluator defects from previous reviews are fixed.

I found a deeper port issue instead.

CTRL's original cluster/representation machinery embeds actions as part of its transition representation. The authors' public implementation explicitly passes `action` into the clustering model. 

In the original discrete environment:

> policy action = executed action.

In the continuous Door port:

1. Gaussian policy samples raw \(a\);
2. CTRL stores raw \(a\) in its training batch;
3. RL-ViGen clips the action to [-1,1];
4. environment transition is generated by \(\mathrm{clip}(a)\);
5. CTRL's cluster representation later conditions on **raw \(a\)**.

Thus its action-conditioned SSL objective can be told that the transition was produced by an action the environment never actually executed.

For PPO itself, retaining the raw action for the original log-probability ratio is correct.

So simply replacing the stored action globally with the clipped action would create another error.

The likely clean implementation is to preserve both:

```text id="40zi2u"
policy_action       # raw Normal sample; PPO/logprob
executed_action     # clipped action; transition/CTRL representation
```

Then use the executed action for the action-conditioned representation objective.

This could be material.

At initial standard-Normal scale, an individual action coordinate exceeds [-1,1] about 31.7% of the time, implying approximately:

\[
1-(0.683)^7\approx93\%
\]

of 7-dimensional action vectors have at least one clipped coordinate.

The current episode diagnostics can tell you how severe this is empirically.

I would treat this as a **major unresolved CTRL port-semantics question**, not automatically declare one mathematical answer. A short sensitivity run using raw vs executed actions in the cluster objective can answer whether it matters.

---

# 11. CTRL's online evaluation changes its JAX action RNG, but this is now better characterized

The project correctly isolates the global NumPy stream governing physical Door placement.

Online CTRL evaluation still consumes the same JAX PRNG key subsequently used for training-policy sampling.

Thus evaluation changes the future training action trajectory.

This is real.

However, it also appears to preserve CTRL's source-style reporting behavior rather than being an accidental target-specific bug.

Therefore I would no longer classify it as a hard production blocker.

Instead, state the precise contract:

> CTRL's online evaluation is physically RNG-isolated with respect to Door reset randomness, but stochastic evaluation consumes the same policy PRNG stream as training.

If you want evaluation to be observational, separate the keys.

If source fidelity is preferred, preserve it and record the evaluation cadence as part of the training lineage.

---

# 12. The current scene pairing design is defensible—but some descriptions overclaim it

Current physical condition seeds depend on:

\[
(\text{eval seed},\text{scene id},\text{episode index})
\]

and not the regime.

This gives an excellent paired comparison for:

> train appearance vs OOD appearance **within the same scene**.

That is probably the most useful primary generalization contrast.

But it intentionally does **not** hold physical placement fixed across scene IDs.

So:

```text id="4k5smv"
scene 0, episode i
scene 4, episode i
```

have different random physical placements.

If the intended scene axis is descriptive heterogeneity, that is fine and gives you broader physical coverage.

If you claim a causal scene effect where “only scene changed,” it is false.

The current decision sheet appears to be moving toward the former interpretation. I think that's reasonable.

Clean up remaining evaluator comments/documentation saying that each scene gets the same placement sequence.

---

# 13. The physical diagnostic machinery is now much stronger

Earlier I objected that an observation hash could substitute for physical placement evidence.

The current production path has moved substantially beyond that.

It records actual episode-level environment diagnostics and can fail closed in production for missing required fields.

That is enough in principle.

The remaining requirement is empirical: the current-revision evaluator-family validation should prove all seven families actually emit these diagnostics correctly.

---

# 14. Current evaluator validation is 0/7 families

This is a major production gate and I agree with the gate's conservative state.

The common evaluator has changed in material ways across these recent revisions:

- physical condition seeds;
- strict mode/scene verification;
- raw reward correction;
- CTRL reset semantics;
- placement diagnostics;
- deterministic-kernel configuration;
- checkpoint/protocol metadata.

Old evaluator-validation results should not automatically validate the current revision.

Before final production:

| Family | Required current check |
|---|---|
| RL-ViGen native | native/common competent checkpoint |
| DMC-GB | native/common or matched action/rollout |
| IDAAC | fixed-policy outputs + matched rollout; after ID bug fix |
| PPG | same |
| ALDA | common path canary/parity |
| IBAC | after final multiprocessing/config resolution |
| CTRL | post-fix current common vs native/standalone behavior |

Do not use a chance-level policy as the only evaluator validation. Two wrong evaluators can easily agree that a useless policy is useless.

---

# 15. Places365 remains a real algorithmic adaptation

The production system still switches source loaders from the intended Places training distribution to a fixed validation subset of about 36.5k images.

The decision sheet now consciously accepts that choice and says the affected methods all receive the same split.

That does not make it neutral.

SVEA/SODA/SGQN are specifically augmentation/generalization methods.

Changing their augmentation distribution changes their learning mechanism while the nine other methods are unaffected.

Therefore:

> “all three affected methods use the same split, so cross-baseline comparison is unaffected”

is too strong.

Their **comparison with each other** is less affected.

Their relative performance against other algorithm families can absolutely move.

If production storage permits the source-intended distribution, use it.

If not, preserve the fixed val split but run a source-train-vs-val sensitivity on one or more representative augmentation methods and disclose it.

---

# 16. Time-limit handling remains one of the largest cross-family semantic differences

The 500-step Door boundary is treated differently:

- some methods bootstrap through it;
- most methods treat it as terminal.

Because Door generally doesn't terminate immediately upon successful manipulation, the artificial horizon is a common episode endpoint.

That changes value targets systematically.

The standard distinction is between true termination and artificial truncation; artificial truncations of continuing tasks should generally preserve bootstrap information, whereas a truly finite-horizon formulation requires time-to-go to be represented appropriately. 

I still wouldn't mechanically rewrite twelve original algorithms to one convention without evidence.

But before final production, one representative sensitivity experiment per major family would be useful.

If negligible, the source-preserving split becomes much easier to defend.

If large, it is a major part of what the twelve-way table measures.

---

# 17. Production provenance is improved, but the high-level protocol hash is still not an experiment identity

The full run-manifest machinery now records substantially more:

- payload/source data;
- host;
- resolved config;
- environment;
- packages;
- assets;
- container.

Good.

But the higher-level `Protocol.hash()` still doesn't encode many baseline-specific settings capable of moving performance, such as:

- replay capacity;
- process count;
- rollout/update geometry;
- PPG auxiliary schedule;
- PPO epochs/minibatching;
- IBAC β/entropy;
- architecture choice;
- Places split.

That is fine only if the protocol hash is explicitly:

> ID of the shared comparison conditions,

rather than:

> ID of the complete experiment.

I would formalize two immutable IDs:

```text id="5q97ql"
comparison_protocol_id
resolved_training_lineage_id
```

The second should hash the entire resolved baseline-specific executable configuration and runtime lineage.

No aggregation code should ever decide two trained artifacts are interchangeable merely because the first ID matches.

---

# 18. The exact root source remains unfrozen

The production gate correctly fails this.

The artifact still represents a dirty working tree with many uncommitted paths. The root source-lock identity also corresponds to an earlier state rather than uniquely identifying the exact current orchestration/evaluator code.

Before canaries become production evidence:

```text id="6e1r7a"
commit exact root
freeze nested source pins
freeze applied patches
freeze production descriptors
freeze evaluator
freeze statistical code
tag release
```

Then build payloads from that commit.

At this point the root code contains enough scientific semantics that pinning only nested baseline repositories is insufficient.

---

# 19. The final renderer/platform still needs the explicit production-host equivalence check

This remains OWNER and should stay a blocker.

The project already discovered that the same DrQ-v2 weights could produce dramatically different results under different rendering/runtime conditions.

Therefore do the clean comparison:

```text id="glwa1i"
known checkpoint
+ current evaluator
+ current local/preproduction host
= R_A

same checkpoint
+ same evaluator
+ same immutable container
+ final V100 host
= R_B
```

Then compare.

That isolates host/rendering effects much better than comparing a current result against an old score produced by an old evaluator.

Only after that should the final V100 host be treated as benchmark-equivalent.

---

# 20. An external RL-ViGen anchor remains valuable

The project now has a sensible public Door reference extraction.

The useful positive-control methods aren't near-floor DrQ-v2; they are methods with substantial published Door performance such as SVEA/SGQN.

The final platform should reproduce at least one qualitatively competent RL-ViGen Door result before twelve-way production.

This doesn't require reproducing an exact paper mean.

It needs to establish:

> our final simulator/render/training/evaluation stack inhabits the expected performance regime.

Given the renderer history, this is high-value.

---

# 21. The native five no longer look like the main production risk

With V100 replay effectively non-evicting, the native RL-ViGen group is now relatively close.

I would prioritize:

1. exact V100 manifest;
2. renderer equivalence;
3. current evaluator validation;
4. one external anchor;
5. source freeze.

I did not find a comparably serious new DrQ/DrQ-v2/CURL/SVEA/SGQN implementation defect in this pass.

SVEA/SGQN retain the Places issue.

---

# 22. RAD and ALDA also look comparatively close

RAD's continuous-action/environment port is structurally straightforward compared with the Procgen-derived on-policy baselines.

ALDA is itself in the continuous-control/SAC family, so the target adaptation is much smaller semantically.

Their remaining blockers are predominantly:

- current common-evaluator validation;
- final runtime/canary;
- frozen source/protocol.

SODA additionally inherits the Places augmentation-distribution concern.

I wouldn't spend substantial new algorithm-port effort on RAD/ALDA unless a canary produces contradictory evidence.

---

# 23. Interaction count is not exactly 600,000 for every family

Because synchronous algorithms work in complete rollout blocks:

PPG V100:

\[
147\times4096=602{,}112.
\]

IDAAC V100 approximately:

\[
146\times4096=598{,}016.
\]

IBAC with 16×128:

\[
293\times2048=600{,}064
\]

depending on the final loop rule.

The DMC-GB trainer can similarly execute one extra transition under its inclusive loop.

These differences are below roughly 0.4%.

I would not change algorithms to force exact equality.

Just record the actual environment-interaction count and stop labeling all endpoints as literally identical 600,000 samples.

---

# 24. The V100 host override creates stale minimum-budget and cadence metadata

Several family descriptors retain lower-resource quantum assumptions.

Examples:

- PPG `min_frames` reflects 8×256 rather than V100 16×256;
- IDAAC likewise reflects the old process count;
- IBAC reflects the one-process configuration.

This won't change the 600k result.

It means the same guards can approve a V100 probe shorter than one complete V100 update.

Some explanatory cadence text is also now stale because increasing process count changes interactions per update/logging period.

Recompute all derived quantities from the resolved host profile.

Do not store resource-dependent derived values independently.

---

# 25. The statistics are moving in the right direction but still need freezing

Fixed training seeds are much preferable to the older outcome-adaptive allocation.

Keep:

- training seed as the outer independent unit;
- scenes as a fixed evaluation grid rather than pretending ten scenes are sampled population units;
- individual run points;
- success and return;
- no significance-theater p-values with n=3.

Three training seeds can establish gross differences.

They remain weak for fine ordinal claims.

If the paper depends on “A beats B,” five or more independent training seeds are much safer where affordable. If three is the practical limit, show the points and uncertainty and avoid overinterpreting exact rank.

---

# 26. The floor-adjusted retention proposal has a stale constant

A18 still refers to random-return floor approximately:

\[
1.818.
\]

The current canonical implementation has superseded that with approximately:

\[
1.842
\]

from the newer paired measurement.

The executable gate uses the latter.

If floor-adjusted retention is implemented, import a single canonical floor constant from the reference module.

Do not copy its numerical value into decision documents/aggregation implementations.

This is minor technically but exactly the sort of quantity that otherwise diverges between a methods section and the generated table.

---

# 27. Floor-adjusted retention is much better than raw return ratio, but success should remain prominent

Raw:

\[
R_\mathrm{OOD}/R_\mathrm{train}
\]

depends on the arbitrary reward origin.

Floor adjustment:

\[
\frac{R_\mathrm{OOD}-R_\mathrm{floor}}
     {R_\mathrm{train}-R_\mathrm{floor}}
\]

is considerably more interpretable.

But for Door, success remains the cleaner behavioral outcome.

I would make the result hierarchy something like:

**primary:** success rate under each condition;

**secondary:** raw shaped return;

**generalization effect:** within-scene paired success drop and/or floor-adjusted dense-return retention;

**scene heterogeneity:** descriptive per-scene distribution.

That also fits the current condition-seeding design.

---

# 28. Do not choose the reported checkpoint from the final OOD grid

Keep 600k-ish endpoint as the predeclared primary checkpoint.

Intermediate checkpoints can describe learning/generalization trajectories.

If you inspect all OOD grid scores and pick the best intermediate checkpoint, the test set became a validation set.

If best-checkpoint results are desired, define a distinct validation criterion beforehand.

---

# My current baseline assessment

| Baseline | Status |
|---|---|
| **DrQ-v2** | Near production after final renderer/current-evaluator/source freeze |
| **DrQ** | Same |
| **CURL** | Same; name as RL-ViGen implementation/design point precisely |
| **SVEA** | Near, except Places distribution issue |
| **SGQN** | Near, except Places distribution and final anchor opportunity |
| **RAD** | Near; current evaluator/runtime canary |
| **SODA** | Places distribution + canary |
| **ALDA** | Near; current evaluator/runtime canary |
| **PPG** | **Not final-ready:** reference/design-point decision needed |
| **IDAAC** | **Hard blocked:** actual episode-ID/storage pipeline remains wrong; design-point question after that |
| **CTRL** | Direct evaluator bugs repaired; **major raw-vs-executed action semantic question** + schedule adaptation |
| **IBAC-SNI** | **Hard blocked:** 16-process production path fails and has invalid worker RNG design; hybrid-method issue remains |

# What I would do now

The ordering is important because some work shouldn't wait on general production decisions.

1. **Fix IDAAC's actual episode-ID alignment through the VecEnv/storage state machine.**
2. **Fix IBAC multiprocessing and seed physical RNG explicitly in each worker.**
3. **Resolve the production `curve_eval_episodes` 3-vs-5 mismatch.**
4. **Generate one actual resolved V100 production manifest for every baseline.**
5. **Investigate CTRL raw requested action vs executed clipped action in the representation objective.**
6. **Run the PPG current-vs-published-continuous-control design pilot.**
7. **Run the analogous IDAAC design-point pilot only after its storage correctness fix.**
8. **Resolve/validate final IBAC lineage and repeat β/entropy competence pilot.**
9. **Restore Places train split or run a sensitivity establishing the val substitution's effect.**
10. **Validate all seven evaluator families on the current revision.**
11. **Run the final-host renderer equivalence check.**
12. **Run at least one strong RL-ViGen positive-control anchor.**
13. **Freeze estimand, seeds, endpoint rule and statistics.**
14. **Commit/tag the complete exact tree.**
15. **Run exact-V100-profile canaries.**
16. **Then launch the fleet.**

## Production decision

I would **not launch all twelve yet**.

I also would **not delay the near-ready families because PPG/IDAAC/IBAC require more scientific decisions**, provided runs are explicitly classified as canary/preproduction rather than final evidence.

The project is now asymmetric:

- the native RL-ViGen/RAD/ALDA side is mainly waiting on final-platform/evaluator/provenance validation;
- PPG needs a defensible design-point choice;
- IDAAC contains a concrete current mechanism bug plus a design-point problem;
- IBAC's proposed final execution configuration does not yet work correctly;
- CTRL is operationally much healthier, but its continuous action-conditioned representation semantics deserve one focused check.

The **most important finding in this review is the IDAAC state-machine defect**. The wrapper-level episode-ID correction looked correct in isolation, and the repository's semantic tests supported it, but Baselines auto-reset plus the original rollout-storage indexing makes the actual stored `(observation, level, nsteps)` relation wrong around episode boundaries. That is exactly the kind of defect worth finding before the expensive runs, because more seeds would only produce more precise measurements of the wrong IDAAC mechanism.
