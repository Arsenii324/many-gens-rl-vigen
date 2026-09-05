This version is materially stronger than the previous one. Several earlier failures are genuinely fixed in executable code. I would still classify it as **not ready for the final production fleet**, but the remaining blockers are now much more specific.

I ran targeted audits and tests rather than the slowest full environment suite. The fresh production gate reports **20 PASS, 2 FAIL, 11 OWNER**, with the project itself concluding `NOT LAUNCHABLE`. I agree with that verdict, but I also found two important problems that the current gates do not catch: a real CTRL evaluation-pairing bug and a likely-unrunnable IBAC `procs=16` production target.

## Overall assessment

The IBAC-SNI PPO mathematics now look defensible. Its raw-action likelihood bookkeeping is correct, the Gaussian event dimensions are correct, SNI/VIB branches are coherent, and the evaluator-device problem has been repaired. I would no longer redesign the continuous head before testing it.

The main risks have moved to four areas:

| Area | Current assessment |
|---|---|
| IBAC-SNI core RL math | **Reasonably sound as an authored continuous adaptation** |
| Final IBAC configuration | **Not yet validated; previous pilot used the wrong β and final process count is probably unrunnable** |
| Common evaluator | **Not validated; 0/12 current-revision burdens discharged, plus new CTRL bug** |
| Production/research protocol | **Still not frozen or source-clean** |

My strongest current blockers are:

| Severity | Finding |
|---|---|
| **P0** | IBAC's proposed V100 `procs=16` configuration directly contradicts a measured `procs=2` fork/EGL failure, while the code still uses the same unsafe fork architecture |
| **P0** | Previous IBAC pilots accidentally used `beta=1.0` rather than the intended `1e-4`; the previous learning evidence therefore does not test the configuration now proposed |
| **P0** | CTRL's common evaluator double-resets between measured episodes, so actual placement conditions are `0,2,4,...` while records claim `0,1,2,...` |
| **P0** | The exact source is still dirty: **116 uncommitted paths**, while `source-lock.json` names a different root commit |
| **P0** | **0/12** common-evaluator validation burdens survive under the current evaluator revision |
| **P0** | Production diagnostics remain fail-open, and the real-environment tests can convert arbitrary runtime failures into skips |
| **P0** | The final V100-host learning configuration is still not one frozen, executed configuration |
| **P0** | No production-length train → checkpoint → clean reload → full grid → records → statistics canary has completed |
| **P0** | Statistical/checkpoint/seed/scope choices remain owner decisions rather than frozen protocol |
| P1 | PPG at 16 envs changes its defining auxiliary-phase cadence by ~16× per environment frame relative to the published parallel setup |
| P1 | IDAAC and CTRL also retain substantial on-policy parallelism differences |
| P1 | Evaluation is paired in physical Door geometry at best, not necessarily in visual randomization |
| P1 | Several executable audits still overstate what they have actually proven |
| P1 | A number of current notes are already stale relative to current code |

Below is the detailed reasoning.

---

## What has actually been fixed

Several previous findings are closed.

The fleet-wide `rlgen/protocol.py` payload failure is fixed properly rather than patched at one callsite. The evaluator revision members are centralized, the payload includes them, and there is now a regression test enforcing the dependency closure.

The PPG witness-copy problem I found previously has been corrected: placement witnesses are collected after the rollout rather than copying an empty list beforehand. Diagnostics are also collected before the environment is torn down.

The duplicate weaker `completed_episode_diagnostics()` implementation in `eval_grid.py` is gone; production now uses the shared tested implementation.

CTRL's common evaluator now explicitly disables reward normalization, which restores evaluation returns to Door reward units rather than summing a moving-normalized reward.

Offline evaluation provenance is better. The run manifest now carries payload identity, RL-ViGen asset identity, pinned container identity, resolved packages/environment/EGL information, and offline records are enriched before being returned.

The container is now pinned by digest rather than a mutable tag.

The random-policy Door floor was remeasured under the newer evaluation setup at approximately **1.842**, rather than continuing to rely on the old 1.82 value.

The IBAC evaluator now moves its model to its requested evaluation device.

IDAAC's evaluator device and level-identity plumbing are improved.

PPG's continuous-action auxiliary KL reduction now sums over the action dimension before averaging.

These are meaningful improvements.

---

# IBAC-SNI: there was a much bigger hyperparameter error than entropy

The most important IBAC discovery in this version is the newly repaired `beta` wiring.

The launcher now explicitly executes:

```text
--use_bottleneck
--sni_type vib
--model_type impala
--entropy-coef 0.0
--beta 1e-4
```

But `torch_rl/scripts/train.py` defaults:

```python
--beta = 1.0
```

and PPO includes:

\[
L \supset \beta\,D_{\mathrm{KL}}(p(z|s)\|p(z)).
\]

Previous IBAC runs did not pass the intended beta. Therefore they actually trained with:

\[
\beta = 1.0
\]

while the project's fidelity record believed it was using the CoinRun-scale:

\[
\beta = 10^{-4}.
\]

That is a factor of:

\[
\boxed{10{,}000\times}
\]

on the information-bottleneck KL penalty.

This is not a small tuning difference. The KL term is one of IBAC's defining mechanisms.

The current source correctly recognizes this and repairs the launcher. But the consequence is important:

> The previous `entropy_coef=0` pilot cannot be used as evidence that the corrected IBAC configuration fails to learn Door.

It tested a radically over-regularized bottleneck.

The old comparison still gives useful causal information within that old configuration:

\[
c_H=0.01
\Rightarrow
\text{log-std/entropy runaway}
\]

versus

\[
c_H=0
\Rightarrow
\text{runaway disappears}.
\]

So keeping the entropy coefficient at zero remains reasonable.

But the observations about return/success from those runs need to be reset conceptually. The corrected \(10^{-4}\) beta configuration needs a fresh pilot.

This beta incident also shows why the current gate:

> `PASS claimed hyperparameters executed`

should be interpreted cautiously. Its own output admits that **13 claimed hyperparameters remain UNLOCATED** and therefore uncertified. It establishes “no contradiction among the values I could trace,” not “every scientifically important value reaches the process.”

---

# The proposed IBAC `procs=16` production configuration is presently a P0

This is more serious operationally.

Your own `families.json` documents why IBAC currently uses:

```text
procs = 1
```

It says that `procs=2` was actually tried on Linux EGL and failed with an `EOFError`, consistent with the existing macOS experience that MuJoCo GL contexts do not survive the fork architecture.

Yet the V100 host profile now overrides this to:

```text
procs = 16
```

because the original torch_rl configuration used 16 processes.

The problem is that the architecture that failed at 2 has not changed.

`torch_rl/scripts/train.py` still does:

```python
multiprocessing.set_start_method("fork")
```

It then constructs every Robosuite/MuJoCo environment in the parent:

```python
envs = []
for i in range(args.procs):
    env = utils.make_rlvigen_env(...)
    ...
    envs.append(env)
```

Only afterwards does `ParallelEnv` fork processes and pass those already-created environment objects into workers:

```python
p = Process(target=worker, args=(remote, env))
```

That is exactly the class of GL-context inheritance the current `constants_note` says was measured to fail at `procs=2`.

Moving this code from a T4 host to a V100 host does not make inherited EGL/MuJoCo contexts fork-safe.

So I would currently expect:

\[
\boxed{\texttt{procs=16} \text{ to fail before meaningful IBAC training}}
\]

unless the production environment behaves differently for an unexplained reason.

There are two defensible resolutions.

Keep `procs=1` and explicitly register it as an environment-constrained implementation adaptation. This preserves a known-working architecture but leaves a major update-geometry difference from upstream.

Or redesign the parallel environment path so the child process starts clean and constructs its own Robosuite environment after spawn/forkserver, rather than inheriting a live MuJoCo object. Then prove `procs=16` with an actual multi-update pilot.

I strongly prefer the second if source-level parallelism is important to the paper's fidelity story. But it is a real implementation change, not a configuration toggle.

Until then, the migration note saying the IBAC parallelism gap is “closed” is not supported.

And critically, the next IBAC competence pilot must occur **after** this decision.

A sensible ordering is:

\[
\text{final process architecture}
\rightarrow
\beta=10^{-4}
\rightarrow
c_H=0
\rightarrow
100k\text{ pilot}
\rightarrow
600k.
\]

Not the reverse.

---

# IBAC's actual continuous PPO core still looks valid

Separate from those configuration errors, I remain reasonably comfortable with the probability mechanics.

The action distribution is effectively:

\[
q(a|z)=
\operatorname{Independent}
\left[
\mathcal N(\mu(z),\operatorname{diag}\sigma^2),
1
\right].
\]

That means both `log_prob` and entropy are joint over the seven-dimensional action vector rather than accidentally averaging coordinates.

The rollout path samples the raw Gaussian action and stores that raw action and its corresponding raw log probability. The environment may subsequently constrain it, but PPO computes:

\[
r_t(\theta)
=
\exp\left(
\log\pi_\theta(a_t^{\rm raw}|s_t)
-
\log\pi_{\rm old}(a_t^{\rm raw}|s_t)
\right),
\]

so the earlier possible clipped-action likelihood bug is absent.

For VIB/SNI, the clean/noise-suspended path uses the bottleneck mean while training incorporates the sampled bottleneck branch and the bottleneck KL. That remains conceptually consistent with the original SNI construction.

The global `log_std` remains state-independent, so:

\[
H[q(a|z)]
=
\sum_i\log\sigma_i+C
\]

does not depend on \(z\). Therefore `entropy_coef=0` removes primarily a global variance-expansion pressure rather than some rich \(z\)-conditional decoder entropy. Given the measured runaway, zero is a defensible continuous-action adaptation.

I would label this method explicitly as:

> **continuous-action PyTorch adaptation of IBAC-SNI**

rather than imply it is the continuous-control configuration supplied by the original authors.

Other remaining adaptations include the particular IMPALA/PyTorch trunk, one VIB sample versus the CoinRun configuration's larger sample count, different bottleneck dimensionality in some branches, and continuous Gaussian decoding.

Those do not make the experiment invalid. They constrain what “IBAC-SNI” means in the paper.

---

# New confirmed evaluator bug: CTRL is not actually episode-paired

This is the most important new evaluation bug I found.

The current CTRL vector environment now correctly has its own episode-conditioned placement counter:

```python
self._episode_indices = [0] * len(envs)
```

On every reset, it generates a condition from:

```python
SeedSequence([
    condition_seed,
    scene_id,
    self._episode_indices[index],
])
```

and increments the index.

That is good by itself.

But `_SyncVecEnv.step_wait()` automatically resets an environment as soon as it terminates:

```python
if d:
    o = self._reset_one(..., e)
```

Meanwhile `run_scene_ctrl()` also explicitly does this at the beginning of **every** measured episode:

```python
for episode_index in range(episodes):
    seed_episode_placement(seed, scene_id, episode_index)
    state = env.reset()
    ...
```

Therefore the sequence is:

```text
measured episode 0:
    explicit reset -> internal condition 0

terminal:
    automatic reset -> internal condition 1, discarded

measured episode 1:
    explicit reset -> internal condition 2

terminal:
    automatic reset -> internal condition 3, discarded

measured episode 2:
    explicit reset -> internal condition 4
```

The actual measured CTRL episodes therefore use:

\[
\boxed{0,2,4,6,\ldots}
\]

from its internal condition sequence.

But `_run_grid()` constructs recorded condition metadata assuming:

\[
0,1,2,3,\ldots
\]

So two things are wrong simultaneously:

1. the intended physical-placement pairing with other families is broken;
2. the stored condition-seed metadata does not describe the condition actually measured.

This is more serious than a harmless extra reset.

The current `production_gates.py` still says:

> `PASS evaluation pairing`

because its test is essentially structural: it sees per-episode condition-seeding code. It does not prove the observed episode sequence.

That PASS is false for CTRL.

The repair is straightforward: reset only once before the evaluation loop, and after a terminal step use the observation already returned by the vector environment's automatic reset as the next episode's initial state. Alternatively turn off auto-reset specifically for this evaluator.

Then add a behavioral regression over at least three episodes that checks:

\[
\text{recorded condition id}_i
=
\text{actual placement condition}_i
\]

and ideally compare actual realized placement hashes.

This is exactly why I keep recommending placement identity as data rather than trusting seed expressions.

---

# Pairing is physical, not necessarily visual

Even after fixing CTRL, I would narrow the project's language around paired evaluation.

The shared episode seed controls the global placement RNG used for the physical Door configuration.

But RL-ViGen's visual randomizers use their own `RandomState` attached to the environment/wrapper. Texture, camera, light and other visual modification streams are not necessarily reset from the same shared episode-condition seed.

There are also deliberate native differences. For example the DMC-GB branch uses its own environment construction seed convention including an offset.

So it is reasonable to claim:

> methods see matched physical Door geometry/placement where the pairing machinery is correct.

I would **not** claim:

> every method sees the identical randomized visual episode.

That is especially important because this study is explicitly about visual generalization.

You could standardize a separate per-episode visual randomization seed, but that would itself change some native evaluation conventions. The cleaner choice may be to keep native visual randomization and state the pairing boundary accurately.

This also limits how much precision you should claim from cross-method paired statistics. Physical difficulty can be blocked; exact pixel realization is not one common randomized treatment.

---

# The real-environment smoke tests can hide the bugs they are supposed to catch

This is a significant testing-quality issue.

`tests/test_family_env_smoke.py` contains patterns like:

```python
try:
    env = BUILDERS[family]()
except Exception as error:
    pytest.skip(...)
```

and, more seriously:

```python
try:
    STEPPERS[family](env, 505)
except Exception as error:
    pytest.skip(...)
```

That means all of these could produce a skip rather than a failure:

- an actual wrapper `RuntimeError`,
- a reset bug,
- a shape incompatibility,
- a broken action interface,
- a diagnostics exception,
- an environment-step regression.

Those are precisely what a “real environment smoke” is supposed to detect.

A missing optional dependency is a legitimate skip.

A runtime error after successfully importing and constructing the configured environment is generally not.

I would change these tests so they skip only for explicitly recognized environment unavailability conditions—e.g. missing module/platform/GL capability—and **fail** on behavior errors.

`test_family_regime_readback.py` has similar broad-skip patterns and deserves the same treatment.

This matters because otherwise you can add more “real environment” coverage while actually increasing the number of ways a regression turns yellow instead of red.

---

# Production diagnostics still fail open

The shared diagnostic collector is better and now validates required fields when it actually finds the wrapper's episode-diagnostics buffer.

But if the diagnostic buffer is not reachable through a given wrapper stack, the function still returns rows like:

```text
diagnostics_available = false
```

rather than rejecting the production cell.

That means a final production run can silently omit irrecoverable fields such as:

- realized initial placement;
- placement hash;
- episode length;
- termination reason;
- raw reward statistics;
- action clipping rate;
- raw-versus-executed action discrepancy.

Your own record-completeness rationale correctly notes that these cannot be reconstructed after the run.

For exploratory testing, `diagnostics_available=false` is useful.

For the final fleet I would make required diagnostics fail closed.

At present the full-episode diagnostic smoke exercises PPG, CTRL and IDAAC. IBAC is construct/regime-tested but not in the full 505-step `STEPPERS` set, and not every evaluator family has equivalent end-to-end diagnostic coverage.

So the gate:

> `PASS record completeness`

is stronger than the behavioral evidence supports.

It is another gate I would downgrade from “PASS” to “static structure present” until every family completes a real episode and produces the required final schema.

---

# Source provenance remains a hard blocker

This artifact says:

```text
Commit: 12f63229073d65ed46d364882ae0a975580277cc
Tree Dirty: True
116 uncommitted paths
```

So that commit does **not** identify the source I just reviewed.

Separately:

`datasphere/native/source-lock.json`

still identifies its root repository with:

```text
f041f5e170368d298e9b5b60127faa10ba5364e5
```

which is not the artifact's stated base commit either.

The production gate now behaves correctly when `.git` is absent: it fails closed rather than treating an empty `git status` as clean. That is an improvement.

But the underlying source state is still not production-grade.

A payload SHA is strong evidence for exact bytes if the corresponding payload archive is permanently retained. I would still require the final production source to be committed and the source lock regenerated from that exact state.

For a research artifact, you want to be able to answer:

> What code generated this number?

with one immutable object, not:

> commit X plus 116 local modifications, represented somewhere by payload hash Y, while source-lock says Z.

---

# The final host profile is still not the experiment until it is explicitly selected

The current descriptor defaults to the DataSphere profile.

The V100 configuration is activated by:

```text
NATIVE_HOST_PROFILE=v100
```

and changes several scientifically meaningful settings.

For example:

```text
RL-ViGen replay: 620,000
IDAAC processes: 16
PPG envs: 16
IBAC processes: 16
```

Those settings are not just performance tuning.

For on-policy methods, environment/process count changes the rollout batch and the relationship between environment frames and optimizer phases.

I would make the final production launcher explicitly require:

```text
NATIVE_HOST_PROFILE=v100
```

rather than defaulting quietly to DataSphere values if an operator forgets the environment variable.

A production-run command should ideally refuse to start if the expected profile is not explicitly named.

And the V100 profile needs to be fixed before final pilots, because the pilot should test exactly what the fleet runs.

---

# PPG is still a large algorithm-dynamics adaptation

This deserves emphasis because it is easy to describe merely as “fewer parallel environments.”

The source configuration corresponds globally to approximately:

\[
4\ {\rm MPI\ ranks}
\times
64\ {\rm envs/rank}
\times
256\ {\rm steps}
=
65{,}536
\]

environment transitions per policy iteration.

The proposed V100 configuration has:

\[
1\times16\times256
=
4{,}096.
\]

So each policy iteration sees a global batch **16× smaller**.

But PPG's:

\[
n_{\pi}=32
\]

still counts policy iterations before the auxiliary phase.

Thus the auxiliary phase occurs after approximately:

Original-scale setup:

\[
32\times65{,}536
=
2{,}097{,}152
\]

environment frames.

V100 adaptation:

\[
32\times4{,}096
=
131{,}072.
\]

That is **16× earlier in environment-frame time**.

At your fixed 600k-frame budget, this becomes qualitatively important:

- original global-frame cadence would not even complete the first 2.1M-frame PPG auxiliary interval;
- the V100 adaptation will execute roughly four auxiliary phases.

So reducing environment parallelism has changed how much of PPG's defining phasic mechanism occurs during the benchmark.

This is not automatically invalid. There is simply no fully faithful answer under a 600k fixed horizon:

- preserve `n_pi=32` → much more frequent auxiliary updates per frame;
- rescale \(n_\pi\) to about \(512\) → preserve source frame cadence, but then the 600k run may perform no PPG auxiliary phase;
- extend PPG's budget → abandon equal-frame-budget comparison.

That is a scientific design decision, not a code bug.

It should be predeclared and prominently described.

The current note saying the PPG auxiliary phase first fires at 65,536 frames is also profile-specific/stale: that corresponds to the earlier 8-env DataSphere adaptation. At V100/16 envs, the first phase is about 131,072 frames.

---

# IDAAC and CTRL have related, smaller parallelism adaptations

IDAAC moves to 16 processes on V100, while its source setup used 64.

That means a rollout goes from roughly:

\[
64\times256=16{,}384
\]

samples to:

\[
16\times256=4{,}096.
\]

Again, this changes minibatch/update geometry even if every scalar hyperparameter is unchanged.

IDAAC also uses an authored adaptation of its level identity. Procgen's procedural `level_seed` has been mapped to Door episode/placement identity. That gives the adversarial invariance machinery a meaningful changing nuisance variable, but it is no longer exactly the original semantic object.

CTRL similarly runs fewer parallel environments than source.

One correction to my earlier review is important here: CTRL's online evaluation consuming the same JAX PRNG stream as later training is not something I would now call an implementation bug. The current project checked the source and found that behavior upstream as well. Preserving it is a fidelity decision.

It means CTRL's training trajectory intrinsically includes the random draws made by its continuous online evaluator. That is unusual, but changing it would be an adaptation. The project correctly narrowed its RNG-isolation gate to placement RNG rather than falsely claiming all training randomness is evaluation-independent.

The **common offline evaluator double-reset issue**, however, is a genuine project bug and should still be fixed.

---

# The action-repeat warnings are not hidden budget failures

I investigated the static dead-knob audit rather than accepting it literally.

It flags `action_repeat` as unused on some Robosuite branches.

In those branches the environment simply does not install a repeat wrapper, so effective repeat is:

\[
1,
\]

which is the value being passed anyway.

So this is currently dead configuration surface, not a hidden 2×/4× frame-count error.

Likewise, the 100×100 behavior for RAD/SODA is independently activated through `RLVIGEN_IMAGE_SIZE=100` before those methods apply their native crop/translation path. The image-size distinction is real.

I would clean up the dead knobs because dead arguments invite future false confidence, but I would not block the run on them.

---

# Cross-method results remain design-point comparisons, not controlled algorithm effects

The comparability audit confirms that your fundamental units are mostly aligned, but the conditions are not.

Methods differ jointly in:

- input resolution;
- one versus three frames;
- convolutional architecture;
- optimizer/update geometry;
- parallel environment count;
- gamma;
- reward normalization during training;
- replay versus on-policy storage;
- time-limit target semantics;
- policy distribution;
- sampled versus deterministic evaluation;
- augmentation;
- rendering/cropping strategy.

Several are not incidental implementation details.

One frame versus three frames, for example, changes effective observability of velocity from RGB.

Three methods bootstrap at the 500-step limit while nine use terminal targets. That means their learning targets differ near horizon. I agree with the newer decision-sheet wording that the project should report the difference without asserting, absent an ablation, that the terminal methods are necessarily “systematically disadvantaged.” A 500-step finite-horizon episodic task can coherently use terminal targets.

The scientifically defensible headline remains something like:

> visual generalization of twelve released/adapted implementations on RL-ViGen Door under their declared design points.

Not:

> a controlled causal ranking of twelve RL mechanisms.

Your within-method quantity:

\[
\Delta_{\rm OOD}
=
R_{\rm OOD}-R_{\rm train}
\]

is a much cleaner generalization result than trying to causally interpret every cross-method rank.

---

# Evaluation policy modes remain different estimands

IDAAC, PPG, IBAC-SNI and CTRL sample actions during evaluation because that reproduces their native reporting path.

Other families use deterministic policy actions.

The metadata now accurately reports this, which is an improvement.

But the return from:

\[
a_t\sim\pi(\cdot|s_t)
\]

and the return from:

\[
a_t=\operatorname{mode}\pi(\cdot|s_t)
\]

are distinct estimands.

So cross-method numbers remain “what each implementation reports under its native convention,” not an identical deterministic-policy evaluation.

Twenty episodes per scene partially addresses Monte-Carlo noise, but stochastic policies add another source of evaluation variance that deterministic methods do not have.

That should appear in the methods/limitations section, not be treated as a hidden nuisance.

---

# Statistical plan is now mostly right but still not frozen

The corrected inference proposal is substantially improved.

I agree with:

\[
n=3
\]

training seeds as the outer replicate, not hundreds of episodes.

I agree with treating the ten chosen benchmark scenes as a fixed scene grid unless you explicitly define a super-population of scenes.

I agree that raw outcomes should lead:

\[
R_{\rm train},
\quad
R_{\rm OOD},
\quad
R_{\rm OOD}-R_{\rm train},
\]

plus Door success.

Retention ratios should be secondary and competence-gated because the shaped-reward floor makes near-zero/floor denominators pathological.

Endpoint-as-headline is also the cleanest checkpoint rule.

The remaining issue is governance: these rules still live primarily in the proposal/decision layer rather than being the frozen authoritative evaluation protocol.

`open_decisions.py` currently reports **22 decisions waiting on a person**, including P-C76, the seed policy, checkpoint rule, entropy/fidelity issues, the external anchor and other study-definition choices.

Some historical register entries are stale, so 22 is not “22 unresolved code bugs.” But the experiment still has genuine owner choices that must be resolved before outcomes exist.

The most important to freeze are:

- fixed minimum training-seed count for every headline row;
- missing/crashed-run policy;
- exact primary endpoint and contrast;
- numeric competence threshold/margin;
- endpoint checkpoint rule;
- Door-only versus Door+Lift scope;
- treatment of PPG's phasic cadence adaptation;
- exact final process counts.

---

# The external anchor and renderer check still need to happen before the fleet

The production gate correctly keeps both as OWNER blockers.

The old DrQ-v2 100k value around 480.6 cannot be used directly as the renderer-transfer reference because it was generated before several measurement-affecting evaluator changes.

The clean comparison is:

\[
R_A
=
\text{same checkpoint on current evaluator/current validated platform}
\]

then:

\[
R_B
=
\text{same checkpoint, same evaluator, same container on production V100 platform}.
\]

Only then is platform/renderer the main changed variable.

Likewise the published RL-ViGen anchor should be established before twelve expensive methods are run through the same pipeline. Otherwise a benchmark-wide measurement defect is discovered only after the expensive data have already been produced.

The more discriminating published positive-control methods are preferable to a floor-level anchor where possible.

---

# Shared evaluator validation is currently zero, not one or two

The current production gate is appropriately conservative:

> **ZERO of twelve evaluator burdens are discharged under the current evaluator revision.**

That is the correct status.

Multiple family-agnostic measurement changes invalidated the older reconciliation results:

- per-episode placement conditioning;
- strict regime verification;
- deterministic-kernel changes;
- CTRL raw-reward fix;
- PPG collection-order fix;
- required diagnostics;
- evaluator revision boundary changes.

And now the CTRL double-reset bug means I would fix that first and let the evaluator revision change once more.

Then freeze it.

Then validate every distinct evaluator family against its own native measurement path using a competent checkpoint.

A common evaluator “running successfully” proves integration, not semantic equivalence.

---

# The evaluation budget is large enough that this matters operationally

The current endpoint grid is:

\[
4\ {\rm regimes}
\times
10\ {\rm scenes}
\times
20\ {\rm episodes}
=
800
\]

episodes per final checkpoint.

Intermediate curve evaluation currently uses five episodes over the same broad grid, repeated over the saved trajectory.

At roughly 12 seconds per episode on recent measurements, evaluation itself is many GPU-hours per cell and hundreds of GPU-hours over the fleet.

Current calendar estimates are on the order of a thousand total GPU-hours when training plus endpoint and trajectory evaluation are combined, before accounting for production-V100 throughput differences.

That is precisely why I would not accept “we can correct the evaluation later.” The evaluation is itself expensive.

The full production canary therefore remains necessary.

I would use a representative long-running method and exercise the literal final sequence:

```text
final clean source
→ V100 profile
→ 600k training
→ intermediate checkpoint retention
→ process exits
→ fresh process
→ checkpoint reload
→ full endpoint grid
→ trajectory grid
→ records bundle
→ frozen statistics code
```

The gate correctly says that has never happened at production length.

---

# Operational resume remains unsafe for off-policy methods

The RL-ViGen off-policy resume path still does not persist the replay buffer as part of an exact training continuation.

Restoring model/optimizer/global frame but starting with a fresh replay buffer changes the algorithm's state.

For final long production runs, I would either ensure sufficient non-preemptible wall-clock capacity or define interruption as a failed seed and restart it from frame zero with the same seed.

Do not silently call model-only recovery an exact resume.

The missing-run/retry policy should be frozen before this happens in production.

---

# Some current documentation/audit claims are already stale

This continues to be a project-management risk because multiple agents are editing quickly.

Examples in the present artifact include:

- `review-6-7-8-triage.md` says the CTRL double-reset mechanism was not reproduced because there was no episode counter; current `_SyncVecEnv` now has exactly that counter and the double-reset issue is real.
- the V100 migration text says IBAC `procs=16` closes the source gap despite the still-documented measured EGL failure at `procs=2`;
- some migration text discusses a 1M V100 replay target while executable configuration now uses 620k;
- old PPG notes quote a 65,536-frame first auxiliary phase, while the intended 16-env V100 profile makes it about 131,072;
- old renderer instructions still surface the historical DrQ-v2 reference even though newer validity notes correctly say it cannot isolate renderer effects.

This is why I would trust executable descriptors plus fresh behavioral tests above prose, and regenerate a concise production manifest after the source is frozen.

---

## What I would do next

I would not spend another fleet-scale dollar before this sequence:

1. Fix CTRL's auto-reset/explicit-reset interaction and add a multi-episode behavioral pairing test using actual realized placement hashes, not merely seed expressions. Tighten the real-environment tests so genuine runtime exceptions fail rather than skip.

2. Resolve IBAC's parallel environment architecture. Either formally retain `procs=1`, or make child-created MuJoCo environments work at 16 processes and prove it. Then run a new beta-correct `beta=1e-4`, `entropy=0` competence pilot at that **exact final process configuration**.

3. Make required episode diagnostics and provenance fail closed for final production. Exercise one full episode through every distinct evaluator wrapper family and verify the emitted record, not merely source strings.

4. Explicitly freeze/select the V100 host profile and all algorithm-dynamics choices—especially PPG `n_pi` versus reduced parallelism. Recompute throughput and the production calendar after that configuration is real.

5. Commit the exact tree, reconcile `source-lock.json`, regenerate the payload, and run all audits/tests from that immutable version. The current artifact's 116 uncommitted paths are not an acceptable final provenance state.

6. Fix the remaining evaluator bugs, freeze one evaluator revision, revalidate all distinct family evaluators, then perform the current-evaluator anchor and renderer transfer.

7. Freeze the statistical, seed, checkpoint, retry/missing-run and task-scope protocol before seeing production results.

8. Run one full 600k end-to-end canary. Only if that produces the expected checkpoints, evaluation records, diagnostics, provenance and final statistics without manual repair would I launch the twelve-method fleet.

My current answer to “is the RL implementation ready?” is therefore nuanced:

**The continuous IBAC-SNI algorithm itself is now close enough that I would test it rather than redesign it. The experiment as a production system is not ready yet.**

The three issues I would put at the very top of the board are the **IBAC `procs=16`/fork-EGL contradiction**, the **beta correction invalidating all previous IBAC competence evidence**, and the **CTRL double-reset corrupting the common episode-pairing scheme**. Fix those before interpreting another expensive run.
