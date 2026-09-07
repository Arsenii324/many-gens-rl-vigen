I would not release the full production fleet from the `C.zip` state without further action.

The project is now substantially better than in the first two reviews. IDAAC in particular is much stronger, SODA's auxiliary-LR problem is fixed, the PPG continuous KL reduction is fixed, endpoint arithmetic is mostly sound, provenance is much better, evaluation instrumentation is unusually careful, and many old audit findings are now stale rather than live.

But I still have several findings I would classify as pre-production stops. The most important are not stylistic; they can change the learned policies or invalidate the interpretation of the run.

## Final launch verdict

I would use this gate:

| Priority | Finding | My decision |
|---|---|---|
| P0 | Production V100 renderer/container not cross-host certified | **STOP fleet** |
| P0 | Places365 train split is rewritten to validation for SVEA/SGQN/SODA | **Change for maximal fidelity, or explicitly redefine variants** |
| P0 | IBAC-SNI is still a substantial hybrid, not the main published IBAC-SNI condition | **Do not call it high-fidelity IBAC-SNI** |
| P1 | PPG rollout geometry is still 8×256, not the selected continuous-control reference's 1×2048 | **Change if DMC-reference fidelity is the target** |
| P1 | PPG `aux_lr=3e-4` remains weakly sourced | **Resolve or declare** |
| P1 | CTRL V100 RAM planner reports 13.4 GiB although production restores 64 envs and the project itself estimates ~54 GiB | **Fix scheduler/resource model before launch** |
| P1 | No exact-current IBAC-SNI V100 competence evidence | **Pilot before committing three 600k seeds** |
| P1 | Physical pairing has not been demonstrated from a current provenanced cross-regime record | **Run the cheap proof before fleet** |
| P1 | Shared evaluator has not been re-certified on this exact packaged source closure | **Certify before fleet** |
| P1 | No complete production train→checkpoint→fresh reload→offline grid→records→statistics canary | **Stage first seed as canary** |
| P2 | Time-limit semantics differ 3-bootstrap / 9-terminal | Keep for source fidelity, but **predeclare as comparability seam** |
| P2 | RL-ViGen paper/release conflicts for SGQN and SVEA | Current release target defensible, but labels must say so |
| P2 | Observation geometry/stack differs materially across families | Keep source-faithful primary; disclose |
| P2 | Gaussian continuous-action adaptations may train on unclipped actions while environment executes clipped actions | Measure training-time clipping before long runs |
| P2 | `n=3` seeds and best-in-group inference | Freeze analysis before outcomes |

If those P0/P1 items are handled, I would be comfortable letting most of the system go.

---

# 1. P0: certify the production renderer before training anything expensive

This is the single strongest operational stop.

Your own `production_gates.py` currently returns:

> `OWNER production renderer verified`

and gives the correct proposed experiment: take the same checkpoint, same current evaluator, same pinned software/container and evaluate it on the already validated host and the new V100 host, changing only the platform.

I agree completely with this gate.

This is especially important here because these are vision-based methods. Renderer differences are not merely evaluation noise. If EGL/MuJoCo/OpenGL produces different pixels on the V100 host, the entire 600k training distribution changes. Re-evaluating later on a standardized machine cannot repair the learned representation.

Do this before the fleet:

1. Freeze the actual production Docker image and digest.
2. `MUJOCO_GL=egl` on both sides.
3. Use the current evaluator—not an older evaluator result—as host A.
4. Evaluate the same checkpoint on host B.
5. Compare raw rendered-observation witnesses as well as return.
6. Ideally compare first-reset RGB arrays/hashes for several fixed conditions before even involving the policy.

If pixels disagree, investigate before training.

The current source lock pins `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:...`. If the V100 production image changes, the new digest must replace/be added to the frozen production provenance.

This is a fleet-wide issue.

---

# 2. P0: I would reverse Places365 validation → training for the fidelity run

This is now one of my strongest recommendations.

The current production provisioning deliberately modifies both augmentation loaders:

```python
use_val=False
```

to:

```python
use_val=True
```

in:

- RL-ViGen's loader used by SVEA/SGQN;
- DMCGB's loader used by SODA.

`datasphere/native/configure_places365_val.py` then requires only:

```text
places365_standard/val/images
```

and `run_probe.sh` provisions that validation asset.

The released loaders default to the Places365 **training** partition.

The project's A22 decision correctly recognizes this as a learning-affecting deviation, but I disagree with its justification:

> all three affected baselines use the SAME split, so the cross-baseline comparison is unaffected

That conclusion does not follow.

SODA, SVEA and SGQN do not consume overlays identically:

- SVEA introduces strong augmentation inside its stabilized critic objective.
- SODA uses overlays in an auxiliary representation-learning objective.
- SGQN combines augmentation/saliency objectives and can make additional augmentation draws.

Changing augmentation distribution \(P_{\rm Places}\) can therefore have different effects on the three algorithms. “Same image pool” does not imply an invariant ordering.

For the study you described—where fidelity is more important than convenience—I would use the released **train split**.

If storage/download constraints make that unacceptable, keeping validation is scientifically possible, but then your provenance should cease saying simply:

```text
SVEA — RL-ViGen released code
SGQN — RL-ViGen released code
SODA — DMCGB released code
```

because the executed training distribution differs.

Use something like:

```text
SVEA-RLViGen-PlacesVal
SGQN-RLViGen-PlacesVal
SODA-DMCGB-PlacesVal
```

and list A22 as a learning intervention.

I would prefer fixing it now.

---

# 3. P0: IBAC-SNI is still not a high-fidelity reproduction of the main result

The project's description of it as:

> authored hybrid of the authors' PyTorch and CoinRun implementations

is accurate.

Keep that wording.

Do not upgrade it to “high-fidelity IBAC-SNI” in the paper/results.

Current production gets several things right:

- authors' Impala pixel trunk rather than inappropriate MiniGrid architecture;
- \(\beta=10^{-4}\);
- PPO/SNI/VIB machinery derived from authors' implementation;
- 16 processes restored on the V100 profile after spawn/EGL repairs;
- entropy coefficient 0 is deliberately motivated by instability of the continuous Gaussian adaptation.

But the authors' main CoinRun IBAC-SNI condition contains a coherent package that is still absent:

```text
latent dimension = 256
VIB posterior samples = 12
sigma ≈ softplus(rho - 5)
weight decay = 1e-4
UDA enabled
SNI
beta = 1e-4
```

The released reproduction command explicitly includes:

```text
--l2 0.0001
-uda 1
--beta 0.0001
--nr-samples 12
--sni
```

The source shows that the 12 samples are not merely averaged into one representation: they participate in the stochastic policy construction. A continuous analogue therefore deserves more consideration than “sample one Gaussian latent.”

The CoinRun UDA is also not DrQ random shift. It is random solid-colored rectangular occlusion/blotching.

Current Door IBAC still approximately has:

```text
latent = 64
VIB samples = 1
posterior std = softplus(raw)
no 12-component continuous mixture analogue
no 1e-4 L2
no CoinRun rectangular UDA
```

Those differences are not forced by converting a discrete Procgen action space into a continuous Door action space.

My two acceptable choices are therefore:

**A. Fidelity arm:** port the CoinRun VIB/SNI mechanism more literally before production.

**B. Current arm:** run it unchanged, but call it something like `IBAC-SNI-hybrid-Door` and do not use language implying exact reproduction of the primary CoinRun condition.

Given the effort already invested in the project, I would prefer A if practical.

---

# 4. P1: PPG still has the rollout-geometry problem

Current V100 PPG is:

```text
8 environments
× 256 serial steps
= 2048 observations/update
```

with:

```text
n_pi = 32
```

so auxiliary phases occur every:

\[
8\times256\times32=65{,}536
\]

environment interactions.

That is a good correction from the former 16-env V100 setting because it matches the auxiliary cadence of the selected continuous-control reference.

But it does **not** reproduce its temporal geometry.

The IDAAC authors' continuous-control PPG comparator uses:

```text
1 environment
× 2048 serial steps
= 2048 observations/update
```

with 32 minibatches.

Those are not interchangeable for GAE/PPO.

For Door specifically, horizon is 500. Thus a 2048-step serial rollout traverses roughly four complete horizon-bounded episodes, while each 256-step vector fragment is shorter than an episode.

That changes:

- number/location of terminal boundaries inside rollout storage;
- GAE bootstrap structure;
- advantage temporal context;
- minibatch trajectory composition.

I therefore recommend, if your declared source target is the IDAAC DMC PPG comparator:

```text
num_envs = 1
nstep = 2048
nminibatch = 32
frame_stack = 3
gamma = .99
lr = 3e-4
entropy = 0
N_pi = 32
E_pi = 1
E_V = 1
E_aux = 6
beta_clone = 1
```

Current `8×256` preserves **sample count and auxiliary frequency**, not rollout equivalence.

There is also a provenance contradiction in `families.json`:

```text
source_target:
    PPG authors' released code

source_variant:
    ... using the IDAAC-authors' DMC comparator profile
```

Those are different targets.

Choose one.

For this Door experiment I think the IDAAC continuous-control comparator is the better reference, precisely because it is the available published continuous-control PPG adaptation.

---

# 5. P1: PPG auxiliary LR is still unresolved

The OpenAI released PPG code has approximately:

```text
lr = 5e-4
aux_lr = 5e-4
```

The IDAAC continuous-control comparator says learning rate \(3\times10^{-4}\), but that statement does not obviously disambiguate PPG's separate auxiliary optimizer.

Current project runs:

```text
lr = 3e-4
aux_lr = 3e-4
```

I am comfortable with `lr=3e-4`.

I cannot give the same level of confidence to `aux_lr=3e-4`.

If there is no stronger source in your archive specifying the auxiliary optimizer's value for the continuous-control PPG comparator, I would not describe `3e-4` as source-established.

The scientifically clean options are:

- find the IDAAC authors' exact continuous-control implementation/config;
- or retain OpenAI's `aux_lr=5e-4` while using the DMC policy LR `3e-4`;
- or keep `3e-4` but mark it as an adaptation/interpretation.

Do not pick based on the Door pilot result.

The continuous-action KL correction itself looks good: KL across seven independent action coordinates is summed before averaging, consistent with PPO's action log-probability reduction.

---

# 6. P1: CTRL's V100 memory model is currently false

This is a concrete engineering bug.

The project correctly restores:

```text
CTRL num_envs = 64
```

on the V100 host.

The descriptor itself says the measured 16-env peak was about:

```text
13.57 GiB
```

and estimates 64 envs at approximately:

```text
54 GiB
```

which is plausible and should fit on a 113-GiB host when run alone.

But `plan_production.py` currently emits:

```text
ctrl:
    num_envs = 64
    cell_ram_gib_model = 13.4
    basis = "on-policy rollout only, budget-independent"
```

because `cell_ram_gib()` has no CTRL process/vector-size model and falls back to:

```python
ENVELOPE["ctrl"]["rss_gib"]
```

which was measured at the 16-env configuration.

So the scheduler's RAM model underestimates production CTRL by about 4× according to the project's own estimate.

This does not prove CTRL will OOM. Quite the opposite: ~54 GiB probably fits on your 113-GiB host.

But it means:

> `PASS scheduler RAM invariant`

does not establish what it sounds like it establishes for V100 CTRL.

Fix the planner before production.

I would prefer an actual short 64-env V100 measurement over linear extrapolation, then record the measured peak.

---

# 7. CTRL algorithm choice itself is now defensible

I do **not** recommend changing CTRL to the paper configuration at this point.

The conflict is real.

Paper:

```text
32 envs
256 steps
1 PPO epoch
1 representation epoch
representation LR = 5e-4
cluster_len = 2
nearest-cluster k = 3
temperature = .3
```

Official released code:

```text
64 envs
256 steps
3 PPO epochs
representation LR = 1e-4
cluster_len = 10
myow_k = 1
temperature = .1
```

Current V100 production restores the released 64-env profile and explicitly declares the authors' released code as its source target.

That is internally consistent.

Keep it.

Just call the result:

```text
CTRL-release-Door
```

rather than implying it reproduces the paper appendix's exact reported configuration.

The modern JAX/Flax/Optax port remains a provenance divergence from roughly JAX 0.2.17 / Flax 0.3.4 / Optax 0.0.9, but I do not think that alone justifies resurrecting the old software stack. Numeric tests of Sinkhorn/MYOW/optimizer/stop-gradient behavior are the appropriate defense.

---

# 8. IDAAC is now one of the stronger on-policy baselines

I would let IDAAC run, subject to the fleet-wide renderer/evaluator gates.

Current C2 resolves to:

```text
num_processes = 1
num_steps = 2048
num_mini_batch = 32
ppo_epoch = 10
lr = 3e-4
gamma = .99
GAE lambda = .95
entropy = 0
value coefficient = .5
value_epoch = 9
value_freq = 32
adv_loss_coef = .1
order_loss_coef = .1
frame_stack = 3
linear LR decay over literal 1M interactions
```

This is substantially closer to the published DMC design than the old 16×256 configuration.

The requested 600k budget correctly resolves to 598,016 because updates happen in 2048-interaction quanta.

### Episode identity bug: appears resolved

An old project decision correctly identified a serious issue involving:

```text
EpisodeLevelSeed
→ DummyVecEnv auto-reset
→ rollout storage
```

where terminal/autoreset metadata could associate an observation with the wrong episode identity, corrupting IDAAC's within-trajectory adversarial ordering objective.

The current tree contains a real integration test through the wrapper, Baselines `DummyVecEnv`, and rollout storage, and the collector now distinguishes terminal versus next-episode `level_seed`.

I regard this old blocker as fixed.

### Remaining IDAAC concern

The new workload geometry is radically different from previous throughput experiments, so old speed/memory estimates should not be treated as certification.

The 2048-step rollout storage itself is fixed-size, so I am not especially concerned about progressive RAM growth. I am concerned about wall time and exact V100 behavior.

A first production seed can provide that evidence.

---

# 9. SGQN: current variant is legitimate only as RL-ViGen-release SGQN

You have made a coherent provenance choice: use the released RL-ViGen configuration.

Keep that if intentional.

But do not describe it as reproducing RL-ViGen's published parameter table.

There are at least these paper↔release differences:

| Parameter | RL-ViGen publication | released configuration |
|---|---:|---:|
| feature dimension | apparently 256 | 50 |
| SGQN quantile | .90 | .93 |
| critic consistency coefficient | .70 | .90 |
| auxiliary LR | 8e-5 | 1e-4 |

And then there is the additional Places365 train→validation modification in your production pipeline.

Thus the executed version is currently best described as:

```text
RL-ViGen released SGQN
+ Places365-validation adaptation
```

not simply `SGQN`.

If you reverse Places365 to train, `SGQN-RLViGen-release` is a good label.

---

# 10. SVEA: same provenance issue

RL-ViGen SVEA is not canonical SVEA.

Canonical SVEA's official implementation is in the DMC Generalization Benchmark/SAC lineage.

RL-ViGen instead gives it a DrQ-v2-style learner and its own strong augmentation implementation. It preserves the central SVEA idea—critic training stabilized across clean/strongly augmented observations—but this is a meaningful adaptation.

The released RL-ViGen SVEA additionally uses feature dimension 50, whereas RL-ViGen's publication-wide table appears to imply 256 for SVEA.

Again, your choice of released code is defensible.

Use:

```text
SVEA-RLViGen-release
```

and, preferably, restore the released Places training split.

---

# 11. CURL: acceptable as RL-ViGen CURL

No launch stop beyond Places if CURL itself does not use that asset.

RL-ViGen deliberately changes canonical CURL's encoder construction, using a single encoder rather than CURL's original online/target contrastive representation arrangement.

Current project follows RL-ViGen.

Therefore:

- high RL-ViGen-release fidelity;
- materially less exact canonical-CURL fidelity.

Name it accordingly.

I would run it.

---

# 12. DrQ and DrQ-v2

I would run both.

DrQ-v2 is among your cleanest baselines because RL-ViGen's training stack is directly descended from DrQ-v2.

The Robosuite `action_repeat=1` correction is important.

On the V100 profile the RL-ViGen five have replay capacity:

```text
620,000
```

and the project calculates at most approximately:

```text
601,200
```

retained transitions through the 600k Door run, including reset-related entries.

Therefore the V100 run is non-evicting.

That is a valid behavioral-equivalence argument with respect to replay eviction.

It should remain phrased specifically as:

> V100 600k replay is non-evicting over the experiment horizon.

The base/DataSphere 300k profile is not equivalent.

DrQ should be described as the RL-ViGen DrQ variant rather than an exact reproduction of the original DrQ experimental stack.

No production stop there.

---

# 13. RAD is good as RAD-DMCGB

I would run it.

DMCGB's RAD is a standardized implementation based on original RAD, rather than the exact original RAD architecture.

That is precisely why the current provenance name should be:

```text
RAD-DMCGB
```

The 100×100 render → 84×84 random crop should remain. Do not force native 84 merely to make sensor geometry look superficially identical across baselines; that would disable an important part of RAD.

---

# 14. SODA is fixed except for Places365

The previous concrete bug is now corrected.

Current production passes:

```text
--aux_lr 3e-4
```

which agrees with the official DMCGB SODA launch script rather than inheriting the generic parser's `1e-3`.

Good.

With the Places365 train split restored, I would consider SODA one of your highest-fidelity baselines.

---

# 15. ALDA is strong

I would run ALDA.

The implementation preserves the important released configuration:

```text
64×64
frame_stack = 3
batch = 128
12 latents
12 values / latent
beta = 100
```

and uses the official implementation lineage.

The common-budget extension to 600k is not source-identical to a 500k reported setup, but preserving the 500k checkpoint alongside the 600k common endpoint is a good solution.

Use:

- 600k for your common-budget twelve-baseline comparison;
- 500k as the source-horizon sensitivity/comparison point.

Do not performance-select between them.

---

# 16. P1: certify physical pairing with an actual current record

The code now appears designed correctly:

\[
\text{condition seed}
=f(\text{eval seed}, \text{scene}, \text{episode index})
\]

without regime in that tuple, so the same physical condition should occur across visual regimes.

Records also carry realized placement witnesses.

This is good engineering.

But `production_gates.py` currently says:

> no current, provenanced cross-regime record has a physical pairing comparison

That is cheap evidence to generate and valuable.

Do it before fleet.

This is exactly the type of property that should be proven from output rather than inferred from source.

---

# 17. P1: re-certify the shared evaluator on this exact closure

The gate currently cannot establish evaluator identity for all families because external source material is omitted from `C.zip`.

That is an artifact-packaging limitation, not evidence of an evaluator bug.

But the production repository needs the corresponding gate green.

Given the history of this project—wrong regime selection, missing IBAC evaluation parsing, stale metadata, evaluator revisions—I would not weaken this requirement.

The evaluator is part of the experiment.

Freeze its source hash alongside the trainer.

---

# 18. P1: do one complete canary before fan-out

The production gate correctly says there has never been:

```text
train
→ checkpoint
→ clean process
→ checkpoint reload
→ full 4×10 offline evaluation grid
→ normalized records
→ statistics/report
```

at production length.

I would not interpret this as “spend an extra 600k job.”

Make the first production seed a staged canary.

My preferred order:

1. renderer/platform equivalence;
2. physical-pairing/evaluator proof;
3. one DrQ-v2 production seed through the complete lifecycle;
4. inspect artifacts and resource accounting;
5. release remaining DrQ-v2 seeds and the fleet.

Why DrQ-v2 first?

- strong implementation confidence;
- exercises the large replay-memory regime;
- large checkpoint;
- checkpoint/reload path representative of the five RL-ViGen algorithms;
- no Places365 dependency;
- much less ambiguity than IBAC/PPG.

Do not start all 36 expensive cells simultaneously merely because short smoke tests were green.

---

# 19. P1: IBAC competence still needs an exact-current pilot

Your gate says this correctly.

Historical evidence that:

```text
entropy_coef=.01
```

caused continuous Gaussian variance blow-up and:

```text
entropy_coef=0
```

removed it is useful.

But the current production configuration now combines:

- `procs=16`;
- Impala trunk;
- β \(10^{-4}\);
- current hybrid bottleneck;
- current V100 host.

There is no exact-current competence evidence in `C.zip`.

A functional smoke establishes that processes spawn and memory fits. It does not establish that the baseline learns.

Given that IBAC is also the least canonical method adaptation, I would require a predeclared competence pilot before burning three complete seeds.

Importantly: do not tune it after comparing its final return to the other algorithms. The pilot criteria must be internal—finite losses, policy-scale behavior, clipping, nondegenerate value/return movement—not “must beat algorithm X.”

---

# 20. Measure action clipping during training for all authored Gaussian adapters

This is still important.

PPG, IDAAC, IBAC-SNI and CTRL use continuous Gaussian policies adapted from categorical/discrete-origin code.

The policy can sample:

\[
a_{\rm raw}\notin[-1,1]^7
\]

while the environment ultimately executes something equivalent to:

\[
a_{\rm env}=\mathrm{clip}(a_{\rm raw},-1,1).
\]

PPO then computes its likelihood/ratio using \(a_{\rm raw}\), not the many-to-one clipped action actually responsible for the transition.

CTRL can also embed/use an action in its representation objective which differs from the executed transition action.

Your offline evaluator already records useful clipping diagnostics. That is good.

For production I would also record them during a short training pilot, because evaluation distribution is not necessarily training distribution.

At minimum:

```text
coordinate clip fraction
transition/vector clip fraction
mean |a_raw - a_executed|
max |a_raw|
log_std mean/min/max
```

for PPG/IDAAC/IBAC/CTRL.

Do not immediately switch to tanh Gaussians. That would be another algorithm adaptation.

First establish whether this is negligible.

Predeclare what would count as “material” before inspecting the results.

---

# 21. The 3-bootstrap / 9-terminal time-limit split must be treated as a scientific design choice

This is probably your largest remaining cross-method comparability seam.

Three methods bootstrap through Door's 500-step time limit; nine treat it as terminal.

That means, even on nominally identical environment trajectories, they solve slightly different Bellman/return targets around horizon boundaries.

There are two legitimate objectives:

**Source fidelity:** preserve each implementation's original timeout semantics.

**Strict common-MDP comparison:** force all methods to treat timeout identically.

You cannot perfectly have both.

I agree with the project's existing recommendation:

> preserve source behavior, declare and quantify the seam rather than silently equalizing it.

But this must be frozen **before** production, because changing it later creates a new experiment.

I would add it prominently to every methodology table.

---

# 22. Observation geometry is also a real experimental factor

Your primary configurations roughly span:

```text
RL-ViGen five: 84×84 × 3 frames
RAD/SODA:      100 render → 84 crop, 3-stack lineage
ALDA:          64×64 × 3
IDAAC:         64×64 × 3
PPG:           64×64 × 3
IBAC-SNI:      64×64 × 1
CTRL:          64×64 × 1
```

That means “baseline” includes differences in sensory bandwidth/history.

For fidelity, I would keep these primary configurations.

Do not compromise them into one arbitrary geometry just to make a table look cleaner.

But the paper/report must say explicitly that this is an **implementation-faithful benchmark**, not a controlled architecture ablation where only the regularizer changes.

A standardized 84×84/3-frame sensitivity study could be useful later but is not a pre-production requirement.

---

# 23. V100 throughput is entirely unmeasured

The V100 planner currently correctly says:

```text
calendar_status =
BLOCKED_ON_MEASURED_V100_THROUGHPUT
```

Every baseline has:

```text
v100_completed_frames_per_second = null
```

This is honest.

It need not block the scientific run if your job scheduler has sufficiently generous timeouts and you do not care about calendar estimates.

But do not use T4-based projections for production timeout decisions without large margin.

SODA and SGQN are especially slow in the previous measurements, CTRL's parallelism has changed 4×, and IDAAC's training geometry has changed radically.

---

# 24. Your current source-tree gate failure is an artifact limitation—but rerun it in the real checkout

`production_gates.py` returns:

```text
FAIL source tree frozen
```

because `C.zip` deliberately does not contain `.git`.

That is not evidence the actual tree is dirty.

The artifact's own provenance says approximately:

```text
git commit:
e334a688d9d702b9352955846c881666d7b52152

tree_dirty: false
source tree digest:
e2d1ba40b8f628903d72a47345edc57661e79cb725cf46a932eb0c1a61995207
```

So I do not call this a project bug.

But immediately before actual launch, run the production gate from the actual Git checkout and archive:

```text
git HEAD
git status --porcelain
source-tree SHA256
payload SHA256
resolved families/config SHA256
container digest
```

A result should refer to those immutable identifiers.

---

# 25. The documentation-link release failure is not a learning blocker

The current artifact fails the fast docs-link test because many links point outside the packaged repository, e.g. shared parent-project documents such as:

```text
../../docs/porting-directive.md
../../../docs/local-envs.md
...
```

Those parent documents are absent from `C.zip`.

This appears to be packaging/monorepo-context fallout, not baseline code failure.

I would not block expensive RL solely for it.

I would still require the real repository's fast gate/full suite to be green before tagging the code corresponding to the results.

---

# 26. Statistical decisions must be frozen now

The project currently intends fixed:

```text
3 seeds per baseline
```

which is much better than outcome-dependent seed allocation.

Keep it fixed.

Three seeds is still a small number for strong frequentist claims, especially with environment stochasticity and twelve algorithms.

My recommendation:

- headline = fixed 600k endpoint;
- all three seeds included;
- no performance-selected checkpoint;
- no performance-selected scene subset;
- report individual seeds;
- report mean plus uncertainty;
- emphasize effect magnitude;
- treat trajectory curves descriptively;
- use the fixed ten scenes rather than scene selection.

If you later choose “best algorithm in each conceptual group” based on those same three seeds and then perform inferential tests only on the winners, that is post-selection inference.

Either test prespecified algorithm contrasts or label winner comparisons descriptive.

---

# 27. The retention metric is now in much better condition

Executable code now has one canonical Door random floor:

```text
1.842
```

from the remeasured paired 200-episode run.

The old 1.818/1.82 values survive in historical documentation, but current consumers import the canonical value rather than maintaining independent live literals.

That is not a production blocker.

The floor-adjusted retention quantity is preferable to raw:

\[
R_{\rm eval}/R_{\rm train}
\]

because Door's shaped reward has a nonzero offset.

Keep the denominator competence guard as well: retention becomes meaningless when the training-regime policy has not actually learned the task.

---

# 28. A more accurate final baseline table

This is how I would describe the twelve **after** the changes I recommend.

| Internal key | Scientific display name | Production judgment |
|---|---|---|
| drqv2 | `DrQ-v2-RLViGen` | **GO after fleet gates** |
| drq | `DrQ-RLViGen` | **GO after fleet gates** |
| curl | `CURL-RLViGen` | **GO after fleet gates** |
| svea | `SVEA-RLViGen-release` | **GO after Places train fix** |
| sgqn | `SGQN-RLViGen-release` | **GO after Places train fix** |
| rad | `RAD-DMCGB` | **GO after fleet gates** |
| soda | `SODA-DMCGB-official` | **GO after Places train fix; aux LR now correct** |
| alda | `ALDA-official-Door` | **GO after fleet gates** |
| idaac | `IDAAC-DMC-reference-Door` | **GO after fleet gates / first-seed resource observation** |
| ppg | `PPG-IDAAC-DMC-reference-Door` | **Change rollout geometry first if fidelity is priority** |
| ibac_sni | `IBAC-SNI-hybrid-Door` | **Do not call canonical; pilot required** |
| ctrl | `CTRL-release-Door` | **GO after V100 RAM model/measurement** |

That table would substantially reduce ambiguity in the final paper.

---

# What I would actually do before pressing “production”

In order:

1. **Switch Places365 to the released training split** for SVEA, SGQN and SODA, given your stated fidelity objective.
2. **Decide PPG provenance.** If using the DMC comparator as source target, change `8×256 → 1×2048`; resolve/declare auxiliary LR.
3. **Decide IBAC-SNI scope.** Either port the remaining CoinRun mechanism or freeze the name as a hybrid.
4. **Fix CTRL's V100 RAM model** and preferably measure a short 64-env V100 run.
5. **Pin the exact V100 image digest.**
6. **Run renderer equivalence** with a fixed checkpoint/current evaluator before any training fleet.
7. **Produce one current physical-pairing record** and make `pairing proven physically` green.
8. **Re-certify the shared evaluator** on the exact final source/config closure.
9. **Run short exact-final Gaussian-policy diagnostics** for PPG/IDAAC/IBAC/CTRL, with training-time clipping/log-std recorded.
10. **Run the first DrQ-v2 600k seed as a staged production canary** all the way through fresh reload, complete evaluation grid, record normalization and statistics.
11. If that closes cleanly, **release the fleet**, with IBAC handled separately until its competence criterion is satisfied.
12. Freeze the analysis policy: fixed 3 seeds, endpoint headline, no selected-best checkpoint/scene, fixed Door scope.

I would not spend another iteration changing DrQ-v2, DrQ, CURL, RAD, ALDA, or the IDAAC algorithmic profile unless a concrete test fails. They are past the point where speculative tweaking is more likely to reduce fidelity than improve it.

The remaining substantive algorithm questions are **PPG and IBAC-SNI**. The remaining common-experiment risks are **renderer equivalence, Places365, evaluator/pairing certification, and the CTRL V100 memory model**.

I did not launch training or your live infrastructure. I did run only static/project-local audit commands against `C.zip`; dependency-sensitive tests could not all run in this environment, and the packaged artifact intentionally omits `.git` and some external source closures. I therefore cannot certify the actual production checkout's Git cleanliness, external-clone patch reproduction, GPU behavior, or full test-suite state from this ZIP. Those are explicitly part of the launch gate above.
