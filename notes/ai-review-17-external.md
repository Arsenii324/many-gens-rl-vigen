I reviewed the uploaded project artifact and paper/source collection statically. I did not launch training or run the live test suite. I treated adaptations to Door as legitimate where the original benchmark does not provide a direct continuous-control implementation; the question I used was whether the adaptation preserves the defining algorithmic mechanism and the best available published/source configuration.

The project artifact I reviewed is the 14.2 MB `many-gens-rl-vigen-review-artifact.zip`.  The paper/source collection is the 83.4 MB `papers-sorted.zip`. 

My main conclusion is:

> The project architecture is now substantially better than its older internal audit documents make it look. Using original repositories/training loops plus thin RL-ViGen environment adapters is the right strategy. RAD, SODA, ALDA and DrQ-v2 are already in reasonably strong shape. The major fidelity problems are now concentrated in **IDAAC, PPG, CTRL, IBAC-SNI, and the identity of the RL-ViGen variants of CURL/SVEA/SGQN**. Of those, **IDAAC and CTRL have the clearest source-backed hyperparameter corrections**, while **SGQN has a concrete mismatch against RL-ViGen's own published Door table**.

I would not launch the final fleet with the current values for IDAAC, CTRL, or SGQN if the stated goal is “highest fidelity to the originals.”

## Overall assessment

| Baseline | Current implementation lineage | Fidelity assessment | Most important issue |
|---|---|---|---|
| DrQ-v2 | RL-ViGen implementation, DrQ-v2 lineage | **High** | Mostly protocol/documentation distinctions |
| RAD | DMC Generalization Benchmark | **High** | 100→84 crop changes FoV vs native-84 families |
| SODA | Official DMCGB implementation | **High** | Paper-vs-code hyperparameter ambiguity |
| ALDA | Adapted official ALDA | **High** | Door is necessarily a new environment transfer |
| DrQ | RL-ViGen implementation | **High to RL-ViGen; medium to canonical DrQ** | shift vs original crop/config lineage |
| SVEA | RL-ViGen implementation | **High to RL-ViGen; medium to canonical SVEA** | DrQ-v2-based benchmark variant vs original SAC/DMCGB SVEA |
| CURL | RL-ViGen implementation | **High to RL-ViGen; low/medium to canonical CURL** | intentionally removes CURL's original online/target encoder structure |
| SGQN | RL-ViGen implementation | **Medium currently** | current Door hyperparameters disagree with RL-ViGen supplement |
| PPG | OpenAI PPG adapted to Door | **Medium** | equal sample count is being mistaken for published rollout geometry |
| IDAAC | original IDAAC repo adapted to Door | **Low/medium currently** | published DMC configuration is available and differs substantially |
| CTRL | original CTRL repo adapted to Door | **Medium structurally, low config fidelity** | parser defaults differ substantially from paper appendix |
| IBAC-SNI | authors' PyTorch branch + CoinRun Impala components | **Medium** | hybrid omits several defining CoinRun VIB/SNI details |

The important qualification is that “RL-ViGen fidelity” and “original-algorithm fidelity” are genuinely different objectives. DMCGB itself explicitly says its implementations use standardized architecture/hyperparameters where applicable, and that SVEA and SODA are official implementations.  Your experiment should expose lineage in the names rather than collapse these distinctions.

I would name results something like `drqv2-rlvigen`, `drq-rlvigen`, `curl-rlvigen`, `svea-rlvigen`, `sgqn-rlvigen`, `rad-dmcgb`, `soda-dmcgb`, `alda-official-door`, etc. That protects you from an avoidable reviewer objection: some of these are faithful reproductions of the RL-ViGen baselines but demonstrably are not the canonical versions of the algorithms whose acronyms they carry.

---

# 1. IDAAC — I would change this before production

This is the largest cleanly correctable issue I found.

The project currently uses the IDAAC authors' code, which is good. The problem is that the configuration essentially follows its Procgen defaults plus a continuous-action/Door adapter, while the IDAAC publication has an explicit continuous-control DMC experimental recipe. Because you are adapting to a continuous visual-control environment, that DMC appendix is a materially better source of precedent than the Procgen parser defaults.

Your V100 descriptor currently resolves approximately to:

| Parameter | Current V100 |
|---|---:|
| processes | 16 |
| rollout steps/process | 256 |
| batch/iteration | 4096 |
| minibatches | 8 |
| PPO epochs | 1 |
| LR | 5e-4 |
| γ | .999 |
| entropy coefficient | .01 |
| value epochs | 9 |
| value frequency | 1 |
| advantage-loss coefficient | .25 |
| invariance/order coefficient | .001 |
| observations | effectively 1 RGB frame |

The published continuous-control recipe gives:

| Parameter | Published DMC IDAAC |
|---|---:|
| processes | **1** |
| rollout steps | **2048** |
| minibatches | **32** |
| PPO epochs | **10** |
| LR | **3e-4** |
| γ | **.99** |
| GAE λ | .95 |
| entropy | **0** |
| value-loss coefficient | .5 |
| value epochs \(E_V\) | **9** |
| value frequency \(N_\pi\) | **32** |
| advantage coefficient \(\alpha_a\) | **.1** |
| invariance coefficient \(\alpha_i\) | **.1** |
| frames | **3 stacked** |
| LR schedule | **linear decay over 1M environment steps** |

That is not a cosmetic difference. `order_loss_coef=.001 → .1` is 100×; `value_freq=1 → 32` changes the defining decoupled value-update schedule; one versus ten PPO epochs changes data reuse enormously; and a 16×256 rollout does not have the same GAE/trajectory geometry as one 2048-step rollout.

So my recommended production IDAAC profile is the published continuous-control one:

```text
num_processes = 1
num_steps = 2048
num_mini_batch = 32
ppo_epoch = 10
lr = 3e-4
gamma = 0.99
gae_lambda = 0.95
entropy_coef = 0
value_loss_coef = 0.5
value_epoch = 9
value_freq = 32
adv_loss_coef = 0.1
order_loss_coef = 0.1
frame_stack = 3
linear_lr_decay_horizon = 1_000_000
```

For a 600k Door run, I would retain the literal 1M LR-decay horizon rather than silently rescale it to 600k. Scaling it to your budget is defensible, but it becomes a Door adaptation.

There is a deeper IDAAC issue too: the meaning of `level_seed`/“environment instance.” In Procgen, it has a real level identity. IDAAC's invariance objective attempts to remove environment-instance information. Giving every Door episode a fresh “instance” identity is mathematically usable but conceptually different: it can encourage invariance to episode-specific placement/trajectory information that may actually be task-relevant. If training only uses one RL-ViGen training visual scene, there may simply be no clean analogue of the original nuisance-instance variable.

I would therefore document your episode-level identity as an explicit adaptation rather than present it as equivalent to IDAAC's original instance-invariance supervision. If you have a real persistent visual-domain/background/randomization identity available, that is the preferable label.

This is not criticism of adapting Procgen work; IDAAC is the opposite case: the publication itself gives you a continuous-control precedent, so you should exploit it.

---

# 2. PPG — the project's current “2048 = 2048” reasoning is insufficient

Your project deserves credit for noticing the published continuous-control PPG precedent in the IDAAC work. But the current resolution is only partly correct.

Current production uses:

```text
8 environments × 256 steps = 2048 samples/update
n_pi = 32
```

and correctly observes that this produces a 65,536-interaction auxiliary-phase cadence:

\[
8 \times 256\times32=65,536.
\]

The continuous-control PPG recipe gives:

```text
1 environment × 2048 steps = 2048 samples/update
n_pi = 32
```

and thus also 65,536 interactions between auxiliary phases.

That equality is useful, but it does not make the algorithms equivalent. GAE is constructed over trajectories. `8×256` means eight short 256-step fragments; `1×2048` means one 2048-step temporal trajectory. Minibatching also differs: your eight minibatches produce batches of 256; 32 published minibatches produce batches of 64.

I would switch PPG to:

```text
num_envs = 1
nstep = 2048
nminibatch = 32
lr = 3e-4
gamma = 0.99
entropy_coef = 0
frame_stack = 3

n_epoch_pi = 1
n_epoch_vf = 1
n_aux = 6
n_pi = 32
beta_clone = 1
```

The last five are the PPG-specific continuous-control values and your implementation is already close there.

There is one uncertainty: the continuous-control source states a learning rate of \(3\times10^{-4}\), but OpenAI PPG has distinct primary and auxiliary optimizer rates. I would confidently change the policy-side LR to `3e-4`; I would verify the exact continuous-control implementation before declaring that its separate `aux_lr` must also be `3e-4`.

Your Gaussian continuous-action adaptation is reasonable. The modification that sums the KL over action dimensions before reducing the batch is also the right semantic analogue of categorical policy KL. There was no original continuous Door PPG, so I would not penalize that adaptation.

I would, however, stop describing `8×256` as matching the continuous-control rollout. It matches the **sample count and auxiliary cadence**, not the rollout geometry.

---

# 3. CTRL — use the publication configuration, not the parser defaults

This was the clearest paper/source disagreement I found because your local arXiv source contains the experiment table directly.

Your production profile currently inherits roughly:

```text
V100 num_envs = 64
n_steps = 256
ppo epochs = 3
CTRL epochs = 1
lr = 5e-4
lr_ctrl = 1e-4
cluster_len = 10
temperature = 0.1
nearest clusters = 1
num_clusters = 200
```

The paper's LaTeX appendix gives:

```text
num_envs = 32
n_steps = 256
samples/epoch = 8192
PPO/RL epochs = 1
representation epochs = 1
lr_rl = 5e-4
lr_repr = 5e-4
gamma = .999
GAE lambda = .95
entropy = .01
clip = .2
frame_stack = 1

num_clusters = 200
cluster_len = 2
nearest_clusters = 3
cluster_temperature = .3
```

I would use those values.

Three differences directly affect CTRL rather than generic PPO:

\[
T: 10\rightarrow2,\qquad
k:1\rightarrow3,\qquad
\tau:0.1\rightarrow0.3.
\]

And `lr_ctrl=1e-4 → 5e-4` is a 5× difference in the representation learner.

One implementation trap: the paper's \(k=3\) is the number of neighboring clusters. In your clone, that corresponds to something like `myow_k`. It is not the separate Sinkhorn/subiteration `k`. Do not turn both knobs to 3.

Your project made two sensible interventions here. It restored two apparently intended-but-commented source lines required for the released CTRL path to execute, and it adapted the old JAX/Flax/Optax code to current APIs. Those are reasonable repairs. But you are running JAX 0.4.35 / Flax 0.10.2 / Optax 0.2.3 rather than the authors' approximately JAX 0.2.17 / Flax 0.3.4 / Optax 0.0.9 environment. That remains a provenance divergence even if the numerical operation graph is preserved.

The official repository should remain the primary implementation source, but the paper experiment table should win over generic parser defaults when the goal is reproduction of the reported CTRL experiment.

---

# 4. IBAC-SNI — much improved, but still a hybrid

The current project has already corrected two very serious earlier problems.

Selecting the authors' CoinRun/Impala-style trunk instead of feeding 64×64 images through the MiniGrid network is correct. Setting \(\beta=10^{-4}\) is also source-backed. The original authors' CoinRun reproduction command explicitly uses `--beta 0.0001 --nr-samples 12 --sni`.

The remaining discrepancies are important:

| Mechanism | CoinRun/paper lineage | Current Door implementation |
|---|---:|---:|
| VIB latent | **256** | 64 |
| VIB samples | **12** | 1 |
| posterior scale | shifted softplus (`rho - 5` lineage) | unshifted PyTorch bottleneck |
| IB β | **1e-4** | **1e-4 — fixed** |
| L2 | **1e-4** | absent |
| authors' UDA flag | **enabled** | absent |
| pixel encoder | Impala | **Impala — fixed** |
| entropy | source configs ≠ your zero | **0, deliberate Door adaptation** |

The most important structural difference is probably not the latent dimension. It is the 12-sample VIB/SNI construction. A single stochastic posterior sample is not the same training objective/estimator as the CoinRun implementation's multi-sample policy mixture.

The posterior scale initialization also deserves attention. If the CoinRun branch really computes the equivalent of

\[
\sigma=\operatorname{softplus}(\rho-5),
\]

while the current PyTorch path uses

\[
\sigma=\operatorname{softplus}(\rho),
\]

that is a major numerical difference in how noisy the information bottleneck starts.

My preferred implementation target would therefore be: retain your authors' Impala port, then port the **CoinRun VIB/SNI head itself**, including 256-dimensional latent, `rho-5` scale semantics and 12-sample behavior, into the PyTorch continuous-action path.

I would also restore L2 \(10^{-4}\). I would inspect what `-uda 1` concretely invokes in the CoinRun branch before mapping it onto Door; do not assume it means DrQ-style random shift.

Your entropy `0` decision is more nuanced. You have experimental evidence that `.01` specifically drives the adapted IBAC Gaussian's log standard deviation upward while the same nominal entropy coefficient does not produce the same failure in PPG/IDAAC/CTRL. So `0` is a defensible continuous-action stabilization adaptation. I would keep it as the primary Door profile if that behavior is reproducible—but mark it plainly as an adaptation rather than a fidelity repair.

The official repository itself distinguishes the CoinRun/TF pixel branch and the PyTorch MiniGrid branch, so there is no single authors' PyTorch continuous-pixel implementation that you could simply run unchanged. This baseline necessarily requires more judgment than IDAAC/CTRL.

---

# 5. SGQN — fix the RL-ViGen values

This is the biggest issue among the five algorithms sourced directly from RL-ViGen.

There are actually three relevant SGQNs:

| Variant | Base | Quantile | consistency weight | auxiliary LR |
|---|---|---:|---:|---:|
| Original SGQN lineage | SAC/DMCGB | around .90 | .9 | authors' original settings |
| RL-ViGen Door publication | DrQ-v2-based | **.90** | **.7** | **8e-5** |
| Current project/upstream config | DrQ-v2-based | **.93** | **.9 hardcoded** | **1e-4** |

RL-ViGen's Door supplementary table is therefore not reproduced by the current released config you are inheriting.

I would change the Door RL-ViGen SGQN production profile to:

```text
quantile = 0.90
critic_consistency_weight = 0.70
aux_lr = 8e-5
```

and expose the currently hard-coded consistency coefficient as configuration rather than leaving `.9` buried inside `sgqn.py`.

This matters more than it looks because the auxiliary optimizer contains/shared-updates the encoder. Changing `aux_lr` therefore changes representation learning directly rather than merely training an isolated prediction head.

The original SGQN objective itself is being represented—the paper adds a saliency-consistency loss and an auxiliary objective supervising saliency-guided representations.  But RL-ViGen's SGQN is a DrQ-v2 adaptation, whereas canonical SGQN was developed in the DMCGB/SAC lineage. If you want “reproduce RL-ViGen Door,” make the three corrections above. If you want “canonical SGQN transported to Door,” use the official SGQN implementation as the base instead.

I would not mix those results under one `SGQN` label.

---

# 6. CURL — correct as RL-ViGen CURL, not canonical CURL

This is the best example of why lineage naming matters.

RL-ViGen deliberately changes CURL. Its supplementary material states that its implementation uses a single encoder instead of CURL's original online/target encoder design. Your implementation follows that decision.

So:

**As a reproduction of RL-ViGen's CURL baseline:** structurally appropriate.

**As a reproduction of original CURL:** substantially different.

Original CURL is a SAC-era visual-control implementation with a target-encoder contrastive construction. RL-ViGen's implementation inherits its newer DrQ-v2-ish training architecture, random-shift preprocessing, and single encoder.

I would keep it if your stated experiment is “RL-ViGen Door baselines,” but call it `CURL-RLViGen` in the experiment manifest.

If you need an original-algorithm sensitivity check, run a second `CURL-original` based on the official repository or DMCGB standardized implementation. DMCGB explicitly includes CURL based on its official implementation and uses the common framework for standardized comparisons. 

---

# 7. SVEA — same distinction

Current RL-ViGen SVEA preserves the essential SVEA idea—critic stabilization through a clean/strongly-augmented loss—but its learner is in RL-ViGen's DrQ-v2 lineage.

Canonical SVEA's official ConvNet implementation lives in the DMC Generalization Benchmark, whose authors explicitly identify it as an official SVEA implementation. 

Thus:

`SVEA-RLViGen`: good benchmark reproduction target.

`SVEA-original`: use DMCGB.

I would not rewrite your current implementation if the target is RL-ViGen results. I would change the documentation/name.

---

# 8. DrQ

Again, the current implementation is substantially better viewed as **RL-ViGen DrQ** than a pristine reproduction of Kostrikov et al.

Original DrQ is SAC-based and uses the original augmentation/preprocessing scheme. RL-ViGen's variant operates inside its own standardized visual-control architecture/configuration.

For the RL-ViGen benchmark objective, I would keep the released implementation. For a paper that says “we reproduce original DrQ,” I would not use that wording without qualification.

I did not find a similarly severe RL-ViGen-published Door hyperparameter contradiction for DrQ like the one in SGQN.

---

# 9. DrQ-v2

This is the strongest of the RL-ViGen-native group because RL-ViGen itself is built substantially around DrQ-v2's training architecture.

The project has correctly overridden Robosuite action repeat to 1. That is particularly important: the released config has a generic `action_repeat=2`, whereas RL-ViGen's own supplementary protocol says Robosuite uses 1.

Your V100 replay size of roughly 620k looks superficially much smaller than various 1M/10M source/document values, but for a 600k Door run it is effectively non-evicting. With only about 600k transitions ever inserted, capacity above the run length has no behavior to preserve. This is a case where matching the literal integer would consume memory without improving fidelity.

I would keep the current effective non-evicting replay policy and document:

```text
replay capacity >= maximum transitions generated
=> no replay eviction
=> equivalent sampling support over this budget
```

That is stronger reasoning than “the paper used 10M, therefore allocate 10M.”

---

# 10. RAD

Your current production path is considerably more faithful than some stale project notes imply.

It runs through DMCGB's RAD implementation. DMCGB explicitly says its RAD baseline is based on the official implementation and puts RAD into a standardized SAC framework. 

More importantly, production really does render 100×100 and crop to 84×84. Some older internal descriptions talk about random shift/n-step behavior inherited from an earlier port; those are no longer descriptions of the production clone path.

I regard the current approach as strong.

There is nevertheless a comparability issue:

\[
100\times100\ \text{camera render}\rightarrow84\times84\ \text{crop}
\]

is not visually identical to

\[
84\times84\ \text{camera render}.
\]

The resulting observations have different effective FoV/projection sampling. But setting RAD to native 84 would make the random crop degenerate/no-op and destroy method fidelity.

So I would keep 100→84 for the source-faithful result. Do not “fix” it for visual equality.

Instead report an observation-geometry table, and if desired add a separate standardized-sensor ablation.

---

# 11. SODA

This is perhaps your cleanest “original implementation adapted to Door” case.

DMCGB is not merely some reproduction: its repository explicitly states that it contains the official SODA implementation, and it provides Places365 as the augmentation source. 

Your current path preserves the important structure:

```text
100 render → 84 crop
SAC base
SODA auxiliary objective
strong Places365 overlay
EMA/target representation
```

There appears to be some paper-versus-released-code ambiguity around auxiliary LR—the source lineage uses values not necessarily identical to every paper table. I would resolve that by making the provenance explicit:

```text
SODA-code profile = exact official DMCGB defaults
SODA-paper profile = paper table values, where different
```

and make `SODA-code` primary unless you have compelling evidence that the code's default is not what generated the paper results.

Official executable code supplied by the authors is unusually strong evidence here.

---

# 12. ALDA

I am favorable toward this implementation.

The ALDA repository says explicitly that `specs/` contains the default YAML configurations used for the main paper results and that its SAC implementation derives from SVEA. 

Your Door profile preserves the recurring source configuration:

```text
batch_size = 128
num_latents = 12
values_per_latent = 12
beta = 100
frame_stack = 3
64×64 architecture/input
```

and preserves the source update structure rather than trying to artificially compensate UTD for Door action-repeat differences.

That is the right philosophy.

ALDA never had a Door experiment, so there is no unique source-backed answer to certain task-specific settings. I would call this “official-implementation-preserving Door adaptation,” which is about as strong as one can reasonably do.

---

# Three project-wide issues matter more than another round of tiny hyperparameter tuning

## Observation geometry

Right now different baselines deliberately get different source-backed observation constructions:

| Family | Input construction |
|---|---|
| RL-ViGen five | native 84×84, 3-frame stack |
| RAD/SODA | 100×100 render → 84 crop |
| ALDA | 64×64, 3-stack |
| PPG | currently 64×64, 1 frame |
| IDAAC | currently 64×64, effectively 1 frame |
| IBAC-SNI | 64×64 |
| CTRL | 64×64, 1 frame |

There is no universally “fair” correction. Enforcing 84×84 everywhere makes RAD cease to implement RAD's crop properly and breaks/changes architecture assumptions elsewhere.

I would therefore make source-faithful geometry the primary protocol and expose it explicitly. Then, if reviewers care about identical sensory bandwidth, provide a **second standardized-observation ablation**. Do not compromise both goals into one configuration.

For IDAAC and continuous-control PPG specifically, however, 3-frame stacking is publication-backed and I would change those.

## Online evaluation and RNG

Your discovery that RL-ViGen's environment seeding uses process-global NumPy/Python RNG is significant. Online evaluation can therefore alter future training placements simply by consuming random numbers.

Disabling online evaluation or snapshot/restoring the relevant RNG state around evaluation is sound experimental hygiene. I favor what the current project is doing here.

This is technically a deviation from any historical run in which evaluation consumed the shared RNG stream. But that historical behavior is not an algorithmic feature. For a multi-baseline benchmark it is undesirable confounding.

I would describe the protocol as:

> Evaluation is RNG-isolated from environment training so evaluation frequency cannot modify the subsequent training trajectory.

Primary performance should come from your common offline checkpoint evaluator anyway. That removes another large class of family-specific evaluation differences.

## Continuous action adaptation

PPG, IBAC-SNI and CTRL did not give you an authoritative Door continuous-action head. You have sensibly used Gaussian policies.

One thing I would instrument in every such baseline is:

```text
raw sampled action
executed/clipped action
fraction of action components clipped
fraction of transitions with >=1 clipped component
mean distance raw→executed
```

This matters because the environment may execute

\[
a_{\rm env}=\mathrm{clip}(a_{\rm sample},-1,1)
\]

while PPO's likelihood is computed for the unbounded \(a_{\rm sample}\).

CTRL adds another complication: if its representation objective consumes the raw action while the dynamics consumed the clipped action, it is learning on an action-transition pair that did not actually occur.

I would not silently replace everything with tanh-squashed Gaussians; that invents a different algorithm. First measure the issue. If clipping is common, explicitly choose and document the continuous-control convention.

---

# What I would change before final production

In descending order of confidence/importance:

1. **IDAAC:** move to the publication's DMC profile: 1×2048 rollout, 32 minibatches, 10 PPO epochs, LR 3e-4, γ .99, entropy 0, value frequency 32, \(\alpha_a=\alpha_i=.1\), three frames and linear LR decay. Reconsider what your “instance” label means on Door.

2. **SGQN:** if reproducing RL-ViGen Door, set quantile `.90`, consistency loss coefficient `.7`, auxiliary LR `8e-5`; make the hard-coded coefficient configurable.

3. **CTRL:** switch production from repository parser defaults to paper-experiment settings: 32×256 rollout, 1 PPO epoch, representation LR 5e-4, cluster length 2, nearest-cluster `k=3`, temperature .3.

4. **PPG:** switch 8×256 → 1×2048 and 8 → 32 minibatches; use the continuous-control recipe's γ=.99, LR 3e-4, entropy 0 and 3-frame observation. Preserve `N_pi=32`, policy/value epochs 1, aux epochs 6, clone β=1.

5. **IBAC-SNI:** after your already-good β/Impala fixes, port the remaining CoinRun VIB mechanism: 12 samples, 256 latent and shifted-softplus posterior scale; restore source-backed L2. Determine exactly what authors' `-uda 1` does before mapping the augmentation.

6. **Rename/source-tag the RL-ViGen variants.** Particularly CURL/SVEA/SGQN. It costs nothing and makes the scientific claim much stronger.

7. **Freeze one executed-config manifest.** Several project documents contain correct historical analyses that have subsequently become stale because the clone-era implementation superseded the old port. Generate a machine-readable manifest from actual final argv plus resolved Hydra/argparse/absl values and make every report consume that rather than manually restating defaults.

8. **Record action semantics and observation semantics as contracts.** Shape, dtype, frame stack, image render resolution, post-augmentation resolution, raw/executed action ranges and clipping rate should be emitted at startup.

9. **Preserve your offline common evaluator as the primary comparison.** Family-native online evaluation should be diagnostic, not the source of the headline generalization comparison.

10. **Strengthen source provenance.** The uploaded artifact intentionally does not contain the nested clones' `.git` histories, so I cannot independently prove that each “pristine” directory corresponds to the stated upstream commit. For final archival reproducibility record upstream URL, commit SHA, pristine-tree/tar SHA256, patch SHA256 and final-tree SHA256.

# One documentation correction I would make immediately

The project has accumulated a lot of high-quality audit work, but that has become a liability in one particular way: historical findings survive after the implementation they describe has been superseded.

For example, production RAD/SODA now use their DMCGB source paths and proper 100→84 cropping, yet some older analyses still discuss properties of the former local ports. Likewise, PPG's “2048 matches continuous control” statement is presented more strongly than warranted.

I would separate documentation into:

```text
CURRENT_EXECUTED_CONFIGURATION.md
CURRENT_FIDELITY_DELTAS.md
historical/
```

and mechanically generate the first document.

That would substantially improve the artifact.

# Sources I did and did not use

I used the uploaded project statically, including the current launchers, V100 family descriptor, current clone source/configuration, audit/reconciliation documents, patches and evaluation/protocol material. I used the uploaded paper collection where it contained useful source-level artifacts; most importantly, CTRL's arXiv LaTeX appendix was more useful than its PDF because it gives the hyperparameter table unambiguously. I also used the local IDAAC supplementary material and the IBAC/RAD source/code lineage available in the collection.

I independently checked authoritative web material where useful. In particular, the DMC Generalization Benchmark repository confirms that SVEA and SODA are official implementations and that its RAD/CURL/DrQ baselines derive from their official implementations.  ALDA's official repository confirms its `specs/` files are the paper-result configurations and its SVEA ancestry. 

I did **not** run your training, smoke tests or live evaluation infrastructure. That was deliberate given your instruction and because a static fidelity audit does not require spending/altering live experiment state.

I also could not independently verify the nested original repositories' git ancestry from this artifact because their `.git` directories were omitted. That does not prevent source comparison, but it prevents me from cryptographically asserting “this directory is exactly upstream commit X.”

Some OpenReview pages were challenge-blocked when I researched the source bundle earlier. NeurIPS ZIP supplements also resolved but were not directly parseable in that browsing environment. For this implementation review those limitations were mostly superseded by your local source/paper collection, original repositories and extracted supplementary material.

I have **not exhaustively source-audited every scalar setting in all twelve baselines**. In particular, I would still want to settle the exact SODA paper-vs-official-code auxiliary LR provenance and a few lower-level augmentation defaults before claiming a line-by-line reproduction certificate. Those are secondary to the much larger IDAAC/PPG/CTRL/IBAC/SGQN issues above.

The overall research design is strong enough that I would preserve it rather than rewrite it. The biggest gain now comes from making the five high-impact corrections above and being precise about which object you are reproducing: **canonical algorithm, authors' released implementation, or RL-ViGen's benchmark adaptation**. Those are three different experimental targets, and your codebase is now good enough to distinguish them explicitly rather than blur them.
