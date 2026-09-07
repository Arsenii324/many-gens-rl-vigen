I do not think “fully accounted for” is yet demonstrated by the artifact you sent.

The important distinction is that the new ZIP is a response/changelog package, not the post-fix repository tree. It describes commits and fixes, but I cannot independently inspect the resulting source state or verify those commit SHAs from this upload. More importantly, the response documents themselves explicitly say that, at the time they were written, the PPG implementation changes and the IBAC-SNI architecture changes were still open work. So I can say that many of my previous findings were analyzed correctly and several were apparently implemented, but I cannot certify that the current live repository is fidelity-complete.

After re-reading substantially more of the primary sources, I also revise several parts of my own previous review. The biggest new finding is a concrete SODA fidelity error I missed. I also now regard your CTRL treatment as more defensible than my previous recommendation, and I retract most of my concern about IDAAC's episode-level discriminator identity.

My present ranking of issues is:

1. **SODA `aux_lr` is almost certainly wrong in the repository state I can inspect.**
2. **PPG remains unverified and was explicitly unfinished in the response artifact.**
3. **IBAC-SNI remains unverified and was explicitly unfinished; the missing mechanism is more precisely identifiable now.**
4. **SGQN has more RL-ViGen-publication-vs-release disagreement than previously identified, including representation dimension.**
5. **SVEA has its own RL-ViGen publication-vs-release feature-dimension conflict and is materially different from canonical SVEA beyond just “DrQ-v2 backbone.”**
6. **RAD is a good DMCGB implementation but should not be described as the original RAD implementation.**
7. **CTRL should remain an explicit paper/release conflict, rather than being forcibly changed to my earlier proposed configuration.**
8. **IDAAC's new target configuration is technically strong; its main remaining risk is operational validation of a radically changed compute geometry, not conceptual fidelity.**
9. **Your evaluation/action-diagnostic infrastructure is better than I gave it credit for.**
10. **The project's biggest remaining methodological weakness is provenance semantics: it still needs explicit names/fields for paper-vs-release-vs-RL-ViGen targets.**

## Revised top-level assessment

I would now score the baselines like this:

| Baseline | What you are actually reproducing | Mechanism fidelity | Published-config fidelity | Released-code fidelity | Main residual |
|---|---|---:|---:|---:|---|
| DrQ-v2 | RL-ViGen / canonical DrQ-v2 lineage | High | High-ish | High | Mostly protocol/provenance |
| DrQ | RL-ViGen DrQ variant | High | Medium | Medium-high | RL-ViGen hyperparameters ≠ original DrQ |
| CURL | RL-ViGen CURL variant | Medium to canonical CURL | Low/medium canonical | High to RL-ViGen release | Single-encoder + DrQ-v2 lineage is intentional but noncanonical |
| SVEA | RL-ViGen SVEA variant | Medium to canonical SVEA | Medium | High to RL-ViGen release | Backbone, strong augmentation, feature-dim conflict |
| SGQN | RL-ViGen SGQN variant | Medium to canonical SGQN | **Medium/low to RL-ViGen paper** | High to RL-ViGen release | q/.7/aux-LR/feature-dim conflicts |
| RAD | DMCGB-RAD | High mechanism | Medium canonical | High DMCGB | Standardized architecture ≠ original RAD architecture |
| SODA | Official DMCGB SODA | High mechanism | **Medium until aux-LR fixed** | **Medium until aux-LR fixed** | Official launch script uses 3e-4 |
| ALDA | Official ALDA adapted to Door | High | High given task adaptation | High | Basically sound |
| IDAAC | IDAAC DMC-continuous recipe adapted to Door | High if claimed changes landed | High | Medium | New workload unverified remotely |
| PPG | IDAAC-authors' DMC PPG comparator adapted to Door | Medium/unknown | Medium/unknown | N/A as canonical OpenAI continuous control | Implementation apparently still open |
| IBAC-SNI | CoinRun-lineage IBAC-SNI → Door hybrid | Medium/low until remaining port lands | Medium/low | Medium/low | 12-sample VIB/SNI, posterior scale, L2, UDA |
| CTRL | Official CTRL released code adapted to Door | High-ish release mechanics | Low/medium paper config | High-ish release | Genuine paper/code conflict + modernized JAX |

The word “High” here does not mean byte-identical. It means I would consider the implementation scientifically defensible under the named provenance.

---

# 1. New finding: SODA's auxiliary learning rate should be 3e-4

This is the clearest new actionable error.

Your vendored DMC Generalization Benchmark defines a generic parser default

```python
--aux_lr = 1e-3
```

and your Door launcher, in the project tree I have, launches SODA directly through `src/train.py` without overriding it.

I previously accepted the project's reasoning that “the official code uses 1e-3, while the paper says 3e-4.”

That reasoning is wrong.

The authors' actual official SODA experiment launcher is:

```bash
CUDA_VISIBLE_DEVICES=0 python3 src/train.py \
    --algorithm soda \
    --aux_lr 3e-4 \
    --seed 0
```

The generic parser indeed defaults to `1e-3`; the algorithm-specific official launch script overrides it to `3e-4`. 

This is exactly why generic parser defaults should rank below algorithm-specific experiment scripts in your source-precedence policy.

DMCGB is unquestionably the right primary source for SODA: its authors explicitly call SODA and SVEA official implementations, whereas RAD/CURL/DrQ are standardized implementations based on the corresponding official repositories. 

So unless this has already been corrected after the response artifact was created, I would change:

```text
SODA aux_lr:
1e-3 → 3e-4
```

with high confidence.

The other SODA mechanics look good:

- SAC base.
- 100×100 replay image.
- independent 84×84 crops.
- Places365 overlay on the augmented branch.
- predictor/EMA-target representation.
- auxiliary update frequency 2.
- SODA batch 256.
- target coefficient `.005`.

And the code uses the Places365 **training** partition by default, not validation; I checked that path too.

So this is not a reason to distrust the whole SODA port. It is one highly material scalar inherited from the wrong level of the configuration hierarchy.

---

# 2. PPG: not proven fixed, and one provenance statement needs precision

The response artifact explicitly says its author did not implement:

- `1 × 2048` rollout geometry,
- 32 minibatches,
- PPG frame stacking,

and that the separate auxiliary-LR question was still open at that point.

Therefore I cannot call PPG resolved based on the material supplied.

The source situation is now very clear.

The continuous-control recipe is **not OpenAI PPG's own continuous-control recipe**. It comes from Raileanu & Fergus' IDAAC supplementary experiments, where they ported several Procgen algorithms—including PPG—to DeepMind Control.

Their DMC setup says:

- 3 stacked frames,
- LR \(3\times10^{-4}\),
- 32 minibatches,
- entropy 0,
- 10 PPO epochs as the common grid-selected PPO setup,
- \(\gamma=.99\),
- \(\lambda=.95\),
- 2048 steps,
- 1 process,
- value coefficient .5,
- linear LR decay over 1M environment steps.

For PPG specifically they then report:

- \(N_\pi=32\),
- \(E_\pi=1\),
- \(E_V=1\),
- \(E_{\rm aux}=6\),
- \(\beta_{\rm clone}=1\). 

The PPG-specific \(E_\pi=1\) obviously supersedes the common PPO 10-epoch setting for PPG's policy phase. So the correct translation is not “PPG PPO epochs = 10”; it is:

```text
rollout:
  processes = 1
  steps = 2048
  minibatches = 32

common continuous-control:
  lr = 3e-4
  gamma = .99
  gae_lambda = .95
  entropy = 0
  frame_stack = 3
  value_coef = .5
  lr_decay_horizon = 1M env steps

PPG-specific:
  E_pi = 1
  E_V = 1
  E_aux = 6
  N_pi = 32
  beta_clone = 1
```

Your former `8 × 256` design preserved total samples and auxiliary cadence, but not trajectory geometry. That remains a meaningful distinction.

There is still one source ambiguity I would not “solve” by guessing: OpenAI PPG has a separate auxiliary optimizer rate. The IDAAC supplement's statement of `3e-4 learning rate` does not, by itself, prove what they used for every PPG auxiliary optimizer parameter. If your current `aux_lr=5e-4` comes from OpenAI's canonical PPG code, I would preserve it until you locate a more specific source.

My preferred label would be:

**`PPG-IDAAC-DMC-reference-Door`**

not “original continuous-control PPG.”

That is both accurate and strong.

---

# 3. IBAC-SNI: the remaining work is more substantial than “a few hyperparameters”

Again, the latest response package explicitly says the 12-sample/256-d/posterior-scale/L2/UDA work had not been implemented by that agent when the response was written.

I independently inspected the actual authors' CoinRun source. The earlier review was directionally correct, but the important point is that these parameters form a coherent mechanism.

The official reproduction command is:

```text
--l2 0.0001
-uda 1
--beta 0.0001
--nr-samples 12
--sni
```

and the repository explicitly says the reported CoinRun results include weight decay and data augmentation. 

The implementation then does all of the following:

### 256-dimensional stochastic bottleneck

The network emits \(512\) parameters:

\[
(\mu,\rho)\in\mathbb R^{256}\times\mathbb R^{256}.
\]

### Shifted posterior scale

It constructs the posterior using the equivalent of

\[
\sigma=\operatorname{softplus}(\rho-5).
\]

This is materially different from an unshifted

\[
\operatorname{softplus}(\rho).
\]

It means the initial stochastic bottleneck is much tighter.

### Twelve posterior samples

It takes 12 latent samples per input for the reported IBAC-SNI CoinRun condition.

### Mixture policy, not a single sampled/averaged representation

This is the most important implementation fact I would preserve in the continuous-action port.

For the discrete CoinRun policy, it builds a mixture across the per-latent-sample action distributions. The value used during noisy training is averaged across latent samples.

So a high-fidelity continuous adaptation should not merely:

1. draw 12 latent samples,
2. average them,
3. run one Gaussian policy.

The closest continuous analogue is a uniform mixture of 12 Gaussian action policies:

\[
\pi(a|s)
=\frac1{12}\sum_{j=1}^{12}\pi_j(a\mid z_j),
\]

with the PPO likelihood corresponding to that mixture density.

That is more work, but it is the semantically faithful translation of the source.

### SNI train/run distinction

The authors separate the noisy training policy from the more stable run policy, with the selective-noise mechanism determining where noise applies.

Preserving “noise for representation regularization but stable execution pathway” is part of SNI, not merely an implementation convenience.

### `-uda 1` is now exactly known

I traced the CoinRun C++ implementation.

It is not random shift, overlay, color jitter or standard DrQ augmentation. It draws a random number of randomly sized, randomly located **solid-color rectangular blotches** over the rendered observation.

So if you want CoinRun-lineage fidelity on Door, the correct adaptation is approximately:

> after rendering, add 0–5 randomly positioned rectangular occluders, with randomized dimensions and randomized RGB colors, following the authors' original dimensional formulas.

Do not replace `-uda 1` with random crop and call it equivalent.

### L2 is part of the reported condition

The authors use \(10^{-4}\) weight decay for the reported CoinRun runs.

So my preferred IBAC target is now:

```text
Impala pixel trunk
VIB latent = 256
sigma = softplus(rho - 5)
nr_samples = 12
beta = 1e-4
SNI train/run semantics
continuous mixture-policy analogue
L2 weight decay = 1e-4
CoinRun-style rectangle UDA
```

Your entropy=0 modification remains defensible as a documented continuous-Gaussian adaptation if `.01` genuinely causes variance blow-up on Door. I would not restore `.01` merely for literalism.

Until the rest above is in the actual production tree, however, I would characterize the current implementation as an **IBAC-SNI-inspired Door port**, not yet a high-fidelity CoinRun IBAC-SNI port.

---

# 4. IDAAC: I substantially upgrade my assessment

The response's claimed IDAAC changes are technically the right ones.

They match the publication's actual DMC recipe rather than the generic Procgen settings. The DMC experiment is not a speculative analogy: IDAAC was actually evaluated on continuous-control tasks with distractors. 

Assuming the commits landed as described, your production target now has:

- 1 process,
- 2048-step rollout,
- 32 minibatches,
- 10 policy epochs,
- LR `3e-4`,
- gamma `.99`,
- lambda `.95`,
- entropy 0,
- three frames,
- linear LR decay over literal 1M env steps,
- value epochs 9,
- value update frequency 32,
- advantage coefficient `.1`,
- invariance coefficient `.1`.

That is much stronger than the previous port.

### I retract my prior criticism of episode-level `level_seed`

I previously worried that giving every Door episode a distinct “instance ID” might misinterpret IDAAC's adversarial objective.

After re-reading the paper, that objection was mostly wrong.

The paper describes the discriminator as taking **two observations from the same trajectory/episode** and trying to determine which one came first. The encoder is adversarially trained to prevent that ordering inference. The purpose is to remove information correlated with remaining episode length.

Thus, if your `level_seed` is simply serving as a grouping key so the rollout code samples two observations from the same episode, an episode-scoped unique ID is actually a principled translation.

This is very different from saying that the ID itself is an input or target representing some persistent visual world identity.

I would keep the current episode grouping semantics, assuming the code indeed ensures that positive pairs are within one trajectory.

### Remaining IDAAC issue is operational

The response correctly identifies its own most important blind spot: the new configuration drastically changes the workload.

Compared with your prior profile you now have:

- a 2048-step rollout,
- 10 policy epochs,
- 32 minibatches,
- 9-channel input,
- value updates with frequency 32,
- one environment rather than a throughput-oriented vectorized collection.

Old:

- FPS estimates,
- memory estimates,
- `cells_per_job`,
- wall-clock assumptions,

are not trustworthy evidence for the new workload.

I am not recommending you change the algorithm to fit the old throughput profile. I am saying the infrastructure budgets must be recertified around the algorithm, not vice versa.

The response also correctly notes that old 3-channel checkpoints will be shape-incompatible with the new 9-channel model. I would add an explicit checkpoint metadata check and fail with a useful message rather than allowing a first-convolution PyTorch mismatch to be the user interface.

---

# 5. CTRL: the agent was right to push back on my previous recommendation

My previous response said, essentially, “paper table wins; switch CTRL.”

That was too categorical.

I independently checked both sides.

The publication's appendix gives approximately:

```text
num_envs = 32
nsteps = 256
RL epochs = 1
representation epochs = 1
RL lr = 5e-4
representation lr = 5e-4

num_clusters = 200
cluster_len T = 2
nearest-cluster k = 3
temperature beta = .3
```

The authors' released executable code defaults approximately to:

```text
num_envs = 64
nsteps = 256
PPO epochs = 3
representation epochs = 1
RL lr = 5e-4
CTRL lr = 1e-4

num_clusters = 200
cluster_len = 10
myow_k = 1
temperature = .1
```

The repository is unquestionably the authors' official CTRL release. 

So this is a genuine source conflict.

Your response's C97-style resolution—record the conflict and keep one declared released-code profile—is scientifically respectable.

What is not scientifically respectable would be calling one set simply “CTRL defaults” without the qualifier.

I recommend two named configurations:

```text
CTRL-release
CTRL-paper
```

with exactly one predeclared primary.

If your research question is “how does the released implementation adapt to RL-ViGen Door?”, `CTRL-release` is a good primary.

If your claim is “reproduce the numerical experiment described by Mazoure et al.,” the paper profile is more appropriate.

Do not choose between the two by Door performance.

### One more verified provenance detail

The response listed the original dependency versions as an unverified claim. I checked them: the released project specifies approximately:

- JAX 0.2.17,
- Flax 0.3.4,
- Optax 0.0.9.

Your project uses much newer equivalents.

I do not think you need to resurrect the ancient stack if your compatibility port preserves the computations. But this is enough API distance that I would specifically test:

- Sinkhorn normalization,
- cluster assignment,
- MYOW neighbor construction,
- stop-gradient boundaries,
- PRNG key consumption,
- optimizer update semantics.

A simple “imports and trains” test is weaker evidence than numeric comparison of those kernels against the old stack.

---

# 6. SGQN: there are at least four RL-ViGen paper↔release conflicts

The project's discussion has focused on three:

- quantile,
- critic consistency coefficient,
- auxiliary LR.

There is another: **feature dimension**.

RL-ViGen's supplementary common-parameter table says, in effect:

> DrQ(v2), CURL: feature dimension 50; otherwise: 256.

That implies SVEA and SGQN should be 256 in the published configuration.

The released `sgqn_config.yaml` uses 50.

So for RL-ViGen Door I now count at least:

| SGQN parameter | RL-ViGen publication | released config/code |
|---|---:|---:|
| feature dimension | **256 implied by common table** | **50** |
| quantile | **.90** | **.93** |
| consistency critic weight | **.70** | **.90** |
| auxiliary LR | **8e-5** | **1e-4** |

Action repeat was another shipped/default mismatch, but your launcher already correctly forces Robosuite to 1.

The SGQN publication itself describes SGQN as a generic value-learning extension consisting of a saliency consistency regularizer plus a self-supervised saliency objective, and the reported benchmark implementation is SAC-based. 

RL-ViGen's SGQN changes the RL backbone to its DrQ-v2 lineage.

So you have two independent axes of divergence:

1. canonical SGQN → RL-ViGen SGQN,
2. RL-ViGen published SGQN → RL-ViGen released SGQN.

I would make that explicit rather than resolving everything with the word “SGQN.”

For example:

```text
SGQN-canonical
SGQN-RLViGen-paper
SGQN-RLViGen-release
```

You do not necessarily have to run all three. But your one production result must tell the reader which one it is.

### What should be primary?

For a benchmark called “RL-ViGen Door” where you are reproducing the paper's published baseline numbers, I would normally prefer the **task-specific publication table** over a generic released config unless the authors document that the table is stale.

So my source-fidelity preference remains:

```text
feature_dim = 256
quantile = .90
consistency weight = .70
aux_lr = 8e-5
```

for `SGQN-RLViGen-paper`.

But keeping the shipped code is not “wrong”; it is `SGQN-RLViGen-release`.

The mistake is collapsing the distinction.

---

# 7. SVEA: more different from canonical SVEA than my previous answer conveyed

This is another place where the current project is benchmark-faithful but not method-canonical.

The official SVEA implementation is in DMCGB, which explicitly identifies SVEA as one of its official implementations. 

Canonical DMCGB SVEA is:

- SAC,
- entropy/temperature term,
- its SVEA clean/augmented critic objective,
- strong augmentation from the SVEA/DMCGB augmentation family.

RL-ViGen SVEA is:

- DrQ-v2/DDPG-style actor-critic,
- scheduled truncated-normal exploration,
- random-shift preprocessing,
- Places/random-overlay-style strong augmentation.

So the change is not just “same SVEA but DrQ-v2 underneath.” The strong augmentation source changes too.

The defining SVEA principle—stabilize critic learning by mixing clean and strongly augmented observations—is retained, so I would not call the method unrecognizable.

But I would rate it only **medium canonical-method fidelity**.

It remains a good **RL-ViGen SVEA reproduction**.

And the same feature-dimensional RL-ViGen publication/release conflict appears here:

```text
RL-ViGen publication: SVEA feature_dim apparently 256
RL-ViGen released svea_config.yaml: 50
```

Your existing project documents apparently already recognize this issue. It should move from an obscure claims ledger into the executed-result provenance.

---

# 8. CURL: current code is a deliberate RL-ViGen variant, not canonical CURL

No major change from my previous conclusion.

Canonical CURL's contrastive mechanism uses an online representation against a separately updated target representation and was developed in the SAC visual-control lineage.

RL-ViGen explicitly says it uses a single encoder instead.

Your implementation follows RL-ViGen's stated intentional modification.

Therefore:

- **RL-ViGen benchmark fidelity:** high.
- **Canonical CURL fidelity:** materially lower.

This is not a bug if the experiment is “RL-ViGen baseline reproduction.”

It is a naming/provenance problem.

A result named merely `CURL` lets a reader infer the original CURL method when you are actually measuring `CURL-RLViGen`.

That distinction is scientifically meaningful because the target encoder is part of CURL's representation-learning machinery.

---

# 9. RAD: good implementation, but DMCGB-RAD is not original RAD

I audited this more carefully because the latest agent explicitly admitted it had taken my RAD claims on trust.

Your production path is indeed DMCGB's standardized RAD, and it really does use the intended 100→84 image transform for augmentation. Keeping 100→84 rather than forcing all methods to native 84 is reasonable.

DMCGB says explicitly:

- SVEA/SODA are official implementations,
- RAD/CURL/DrQ/etc. are based on their official implementations,
- architecture/hyperparameters are standardized where applicable. 

The original RAD repo has a materially different architecture/configuration lineage. Its published launch example uses:

- 100 pre-transform → 84,
- frame stack 3,
- SAC,
- batch 128,
- critic LR 1e-3,
- actor LR 1e-3,

and its pixel encoder lineage is the original CURL/RAD architecture rather than DMCGB's standardized deep shared CNN/projection architecture. 

So I revise the earlier “RAD high” to:

- **High algorithm-mechanism fidelity.**
- **High DMCGB-release fidelity.**
- **Medium exact original-RAD implementation fidelity.**

Call it `RAD-DMCGB`.

If you ultimately want one extra canonical sensitivity arm, RAD-original is more justified than many of the other optional duplicates because the architectural change is meaningful.

But it is not necessary to invalidate the DMCGB baseline.

---

# 10. SODA after the LR fix should be one of the strongest baselines

Once `aux_lr=3e-4` is fixed, I would again put SODA near the top of your fidelity ranking.

DMCGB is the authors' official codebase and the repository specifically supplies the Places dataset setup and SODA implementation. 

This is stronger provenance than a third-party reimplementation.

I would not create unnecessary “SODA-paper” and “SODA-code” branches after discovering the official script: for this particular parameter the apparent disagreement largely disappears, because both the experiment script and the published configuration point to `3e-4`.

The parser's `1e-3` is just a generic default.

That is a useful lesson for the entire project.

---

# 11. ALDA remains strong

No new major concern.

The official ALDA repository explicitly says its `specs/` directory contains the default YAML configurations used for the paper's main results. It also says the SAC implementation is based on SVEA. 

Your source-backed values:

- batch 128,
- 12 latents,
- 12 values/latent,
- beta 100,
- frame stack 3,
- 64×64,

remain appropriate.

The response's proposed budget handling is particularly good:

- preserve a 500k checkpoint corresponding to the source experiment horizon,
- also train/evaluate a common 600k endpoint for benchmark comparability.

That is preferable to choosing one horizon and pretending the other objective does not exist.

I would keep UTD=1 as the primary faithful profile. Any lower-UTD runs should be labeled resource/throughput ablations.

---

# 12. DrQ-v2 remains one of the cleanest baselines

The official DrQ-v2 method makes the key changes one expects:

- SAC → DDPG-style base learner,
- n-step returns,
- scheduled exploration noise,
- updated hyperparameters/implementation. 

RL-ViGen is itself strongly based on this training stack, so adapting its DrQ-v2 to Door is relatively direct.

Your action-repeat override to 1 for Robosuite is important and correct relative to the RL-ViGen protocol.

### Replay capacity

The response's argument is sound only when host-qualified.

On the V100 profile:

```text
capacity = 620,000
maximum transitions generated/retained ≈ 601,200
```

so there is no replay eviction before the 600k endpoint. With respect specifically to the **eviction behavior**, that is equivalent to using 1M or 10M capacity for this horizon.

But the DataSphere/base profile remains around 300k and therefore is a recency ring.

So documentation should say:

> On the V100 600k profile, replay capacity is behaviorally non-evicting over the experiment horizon.

not:

> DrQ-v2 uses behaviorally equivalent replay capacity.

The latter sounds global and is false.

---

# 13. DrQ is reasonably faithful in mechanism, but RL-ViGen's recipe is not original DrQ's recipe

I would soften one statement from my previous answer: original DrQ's augmentation and RL-ViGen's random-shift augmentation should not be treated as fundamentally different algorithms.

Original DrQ performs replication padding plus random cropping; modern implementations often represent effectively the same transform as “random shift.”

The larger differences are configuration/learner provenance:

- canonical DrQ is SAC,
- original code used significantly different optimization settings—e.g. actor/critic learning rates around `1e-3` and larger reproduction batch choices,
- RL-ViGen uses its own standardized Door recipe with different LR/batch defaults.

Therefore:

**Mechanism fidelity:** high.

**Exact original published experiment configuration:** medium.

**RL-ViGen Door fidelity:** high.

Again, `DrQ-RLViGen` is a more scientifically honest display name.

---

# 14. Your action-clipping diagnostics already address much of my previous recommendation

I previously suggested explicitly measuring raw sampled actions versus environment-executed clipped actions in the Gaussian adaptations.

I subsequently inspected the evaluator instrumentation more closely.

You already record approximately:

- coordinate clipping rate,
- vector/transition clipping rate,
- raw-versus-executed L1 difference,
- raw min/max,
- action-bound source.

And the PPG, IDAAC, IBAC and CTRL evaluator paths generally sample from their stochastic policies rather than evaluating only a deterministic mean.

That is better than I gave the project credit for.

Two qualifications remain.

First, these are primarily **evaluation-time** policy samples, not necessarily the exact action distribution seen over live training. If policy stochasticity or scheduling differs during training, evaluator clipping rate is a proxy rather than the actual training statistic.

Second, the instrumentation explicitly does not claim to observe downstream Robosuite controller-internal clipping. That limitation is correctly scoped.

I would not force a tanh-squashed Gaussian merely because the environment bounds its action space. Measure first; preserve the adaptation convention unless clipping is actually substantial.

---

# 15. C98's evaluator fix is good, but I would make certification independent rather than declarative

The response says it fixed incorrect evaluator metadata by sourcing geometry from `OBSERVATION_GEOMETRY` rather than stale CLI defaults.

That is an improvement.

But it still risks becoming self-certification:

```text
protocol declares "9 channels"
evaluator metadata copies protocol declaration
→ metadata says "9 channels"
```

even if some environment wrapper unexpectedly emits 3.

A stronger scheme has three independently obtained quantities:

```text
declared:
  frame_stack = 3
  image_size = 64

observed runtime:
  observation.shape == (9, 64, 64)
  dtype == uint8/expected

checkpoint/model:
  first conv expects 9 input channels
```

and startup fails unless they are mutually compatible.

For every baseline I would record:

- raw render resolution,
- pre-augmentation tensor resolution,
- model-input resolution,
- frame count,
- channels,
- dtype/range,
- action shape,
- raw policy action domain,
- executed action bounds,
- action repeat,
- episode horizon,
- n-step return horizon,
- replay/rollout geometry.

That is much stronger than a manually maintained “observation geometry” dictionary alone.

---

# 16. A formal source-precedence policy is now necessary

This review uncovered the same failure mode in several algorithms:

- CTRL: paper table versus released parser defaults.
- SGQN: RL-ViGen publication tables versus released config.
- SVEA: RL-ViGen publication feature dimension versus released config.
- SODA: generic parser default versus **algorithm-specific official launch script**.
- RAD: official algorithm code versus DMCGB standardized adaptation.
- PPG: original OpenAI method versus later IDAAC-authors' DMC adaptation.

I would adopt this hierarchy.

1. First declare **what object is being reproduced**:
   - canonical publication,
   - authors' released experiment,
   - RL-ViGen published baseline,
   - RL-ViGen released baseline.

2. For benchmark/environment semantics, use RL-ViGen Door protocol.

3. For defining method mechanics, use the canonical paper plus authors' implementation.

4. For a published experiment, a **task-specific paper table** outranks a generic parser default.

5. For an authors'-release experiment, an **algorithm-specific official launch script** outranks a generic parser default.

6. If a task-specific paper table conflicts with an authors' actual launch script/released config, declare two profiles rather than silently resolving it:
   - `paper`
   - `release`

7. Never choose which profile is “canonical” based on observed Door performance.

8. “Already running” is an operational argument about whether to disrupt a campaign, not a fidelity argument.

9. Claims of behavioral equivalence must specify the dimension:
   - “equivalent with respect to replay eviction through 600k”
   is valid;
   - “equivalent replay configuration”
   is too broad.

This policy would have caught SODA immediately.

---

# 17. I strongly recommend two fidelity axes, not one score

Your current problem cannot be represented correctly by a single `faithful = yes/no`.

For example:

- CURL has high RL-ViGen fidelity but lower canonical CURL fidelity.
- SVEA has high RL-ViGen-release fidelity but lower original SVEA fidelity.
- SGQN can have high RL-ViGen-release fidelity while disagreeing with the RL-ViGen paper.
- CTRL can faithfully reproduce released source defaults while disagreeing with its paper's stated experiment.
- RAD can faithfully reproduce DMCGB-RAD while not reproducing original RAD architecture.

I would put fields like these into every run manifest:

```text
algorithm: sgqn

variant:
  display_name: SGQN-RLViGen-release
  canonical_algorithm: SGQN
  implementation_lineage: RL-ViGen

source_target:
  method: canonical-paper
  benchmark: rlvigen-release

fidelity:
  mechanism: medium
  canonical_publication_config: low
  authors_release: n/a
  rlvigen_publication: medium
  rlvigen_release: high

adaptations:
  - Door environment
  - DrQ-v2 learner lineage
  - action_repeat=1
```

The exact schema is less important than refusing to compress independent questions into one label.

---

# 18. Baseline naming should change in result metadata even if internal job keys do not

I understand why renaming every internal shell target now might be undesirable.

You do not have to.

Keep:

```text
svea
curl
sgqn
rad
```

as internal keys if changing them risks breaking infra.

But emit display/provenance names:

```text
DrQ-v2-RLViGen
DrQ-RLViGen
CURL-RLViGen
SVEA-RLViGen-release
SGQN-RLViGen-release       # or -paper
RAD-DMCGB
SODA-DMCGB-official
ALDA-official-Door
IDAAC-DMC-reference-Door
PPG-IDAAC-DMC-reference-Door
IBAC-SNI-CoinRun-reference-Door
CTRL-release-Door
```

This is not cosmetic. It communicates exactly what result is being measured.

---

# 19. Provenance should become cryptographic, not prose-only

The newest response package lists commit SHAs, but because it does not include the resulting Git tree I cannot verify any of them.

Your final research artifact should make that problem impossible.

For each baseline, record:

```text
upstream_url
upstream_commit_sha
upstream_release/tag, if any

source_archive_sha256
pristine_tree_sha256

integration_patch_sha256
final_tree_sha256

dependency_lock_sha256
container image digest

asset hashes
  Places365
  benchmark assets
  evaluation scenes

resolved argv
resolved config

benchmark adapter commit
evaluator commit
```

For vendored historical repos, this is especially valuable because years later GitHub branches can move, disappear or become archived.

The actual source archive is evidence. A prose statement like “cloned from official repo” is not.

---

# 20. Keep “current truth” separate from historical audit archaeology

The response package itself demonstrates a real problem: high-quality old audit reasoning stays in documents after the implementation changes.

That makes it increasingly difficult to tell whether a warning describes:

- the current implementation,
- a retired local port,
- a proposed profile,
- a previous agent's misunderstanding,
- a publication/release conflict intentionally left unresolved.

I still strongly recommend:

```text
docs/
  CURRENT_EXECUTED_CONFIGURATION.md
  CURRENT_FIDELITY_DELTAS.md
  SOURCE_PRECEDENCE.md
  PROVENANCE.md

  historical/
      ...
```

Ideally `CURRENT_EXECUTED_CONFIGURATION` is generated from the same resolver that launches the experiments.

Historical decisions can remain exhaustive. They just should not be the primary state representation.

---

# 21. The new IDAAC compute profile means stale infrastructure numbers should be visibly invalidated

The response artifact itself was unusually good about admitting this.

The new IDAAC changes the computational shape so much that old estimates should not merely have a “possibly stale” note. They should be invalidated in machine-readable state:

```text
throughput_certification: stale
memory_certification: stale
remote_cuda_smoke: not_yet_recorded
```

until your own live test establishes new values.

Since you explicitly said you run the infrastructure yourself, I am not suggesting that I launch anything.

The key point is scientific/operational separation:

> do not change the source-faithful IDAAC recipe because an old V100 scheduling estimate was based on a different algorithm geometry.

Instead update the scheduler after measurement.

---

# 22. The statistical “best in group” issue still deserves attention

The latest response says the post-selection issue was not addressed.

If you run several algorithms in a conceptual group, choose whichever happens to have the best mean across three seeds, and then statistically compare only the winning algorithms, the winner's estimate is upward-selected.

This is not fixed merely by declaring groups in advance.

For headline inference I would prefer one of:

- algorithm-by-algorithm predeclared contrasts,
- hierarchical modeling across algorithms/seeds/scenes,
- multiplicity-aware contrasts,
- or reporting all algorithms and treating “best-in-group” as descriptive.

If you want winner probabilities, bootstrap or posterior probability-of-best is more informative than a winner-only p-value.

This is separate from implementation fidelity but matters once the engineering is good enough for statistical interpretation to become the limiting factor.

---

# My actual launch gate now

If I were reviewing this artifact for a paper and deciding what must be fixed before I accepted “high-fidelity reproduction,” I would divide it like this.

### Must resolve or explicitly profile before calling the setup fidelity-complete

1. **SODA:** confirm production passes `--aux_lr 3e-4`. The official algorithm script is unambiguous. 
2. **PPG:** verify the actual current tree contains the intended 1×2048 / 32-minibatch / 3-frame continuous-reference adaptation. The response artifact says it did not at the time it was written. 
3. **IBAC-SNI:** verify the actual current tree contains 256-d shifted-scale 12-sample CoinRun VIB/SNI, L2 and exact-ish UDA semantics—or explicitly call the current baseline a partial hybrid. 
4. **SGQN:** explicitly choose `RLViGen-paper` or `RLViGen-release`; include feature dimension in that conflict.
5. **SVEA:** explicitly record RL-ViGen-release versus canonical-SVEA provenance and the feature-dimension publication conflict.
6. **CTRL:** keep the paper/release conflict explicit. Do not revert to my prior “paper table unquestionably wins” position.
7. Add source-target/provenance labels to result manifests.

### Strongly recommended, but they do not invalidate the algorithms

8. Runtime-observed observation/model compatibility certification.
9. SHA256 provenance chain.
10. Current-state docs generated from resolved configurations.
11. Re-certify new IDAAC resource use on your actual infrastructure.
12. Make replay-equivalence claims host/horizon-specific.
13. Keep best-in-group statistical comparisons descriptive or selection-aware.

### Optional sensitivity arms, not prerequisites

14. Canonical original RAD beside `RAD-DMCGB`.
15. Canonical SVEA beside `SVEA-RLViGen`.
16. Canonical CURL beside `CURL-RLViGen`.
17. Canonical SGQN beside `SGQN-RLViGen`.

Those would be valuable for a methodological paper, but I would not require them merely to run the RL-ViGen Door benchmark.

---

## What the latest AI-agent response got right

Quite a lot.

Its strongest points are:

- It moved IDAAC toward the actual continuous-control source rather than Procgen defaults.
- It correctly implemented/recognized three-frame IDAAC observations.
- It recognized that CTRL is a genuine source conflict instead of blindly applying my recommendation.
- It correctly kept the literal 1M IDAAC LR-decay horizon rather than silently normalizing it to 600k.
- It preserved ALDA's 500k source checkpoint while supporting the common 600k endpoint.
- It admitted operational blind spots instead of claiming its local CPU verification established CUDA/remote behavior.
- It admitted it had not independently checked RAD/SODA/IBAC primary sources.
- It explicitly stated that PPG and IBAC implementation work remained open at that moment.
- It found stale-document propagation caused by the IDAAC geometry change and corrected some of it.

That is a serious audit response.

Where I disagree is mainly in the implication that this amounts to “fully accounted.” Its own documents explicitly say otherwise.

---

## What I correct from my own previous review

For clarity, these are corrections to my earlier answer, not new criticisms of your project.

**CTRL:** I was too categorical. The paper configuration and official code genuinely disagree. Keeping a named release-code profile is legitimate.

**IDAAC episode identity:** I withdraw most of my objection. IDAAC explicitly trains an adversary to tell temporal order for two observations from the same trajectory/episode. Episode-level grouping is a defensible translation.

**SODA:** I missed the most important configuration hierarchy. The generic parser says `1e-3`, but the official SODA launch script explicitly says `3e-4`; the latter is the stronger source.

**RAD:** I previously called DMCGB RAD essentially “original.” More precise: it is a standardized implementation based on original RAD, not the original RAD architecture.

**SVEA:** RL-ViGen changes more than the learner backbone; its strong augmentation lineage changes as well.

**SGQN:** the RL-ViGen paper/release conflict also includes feature dimension.

**PPG:** the DMC continuous-control settings are from the IDAAC authors' comparator experiment, not an OpenAI PPG continuous-control implementation.

Those corrections make the overall review more internally consistent.

---

## Sources and accessibility

For this pass I used all three bodies of material available to me:

- the earlier full project artifact,
- the earlier sorted primary-paper/source archive,
- the new review/response ZIP.

The new ZIP contains review/changelog documents rather than the resulting post-fix repository, so I could not inspect the commits it names or independently establish that later PPG/IBAC work has since landed.

I did **not** launch training, run live infrastructure jobs, or execute your project test suite.

I directly read local primary source/implementation material for IDAAC, CTRL and IBAC-SNI, including the actual CoinRun policy and augmentation source. I independently checked public official repositories for DMCGB/SODA/RAD/DrQ-v2/ALDA/IDAAC and publication material for SGQN. DMCGB explicitly distinguishes official SVEA/SODA from standardized baselines based on the other official implementations, which is an important provenance distinction for this project. 

OpenReview access limitations from the first research pass are no longer material to most conclusions above because your local paper/source collection contained the relevant publication material. Some publication-vs-release claims for RL-ViGen are based on the supplementary source you supplied rather than a newly fetched publication-site attachment.

My present judgment is therefore: **the project is substantially stronger than at the first review, and the agent's IDAAC/CTRL reasoning is mostly good, but “fully accounted” is not established. SODA is a newly identified concrete correction; PPG and IBAC remain uncertified from the supplied state; and the remaining RL-ViGen publication/release disagreements need to become explicit provenance rather than implicit policy choices.**
