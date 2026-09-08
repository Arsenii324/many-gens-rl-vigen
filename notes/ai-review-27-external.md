My current verdict is: **do not fan out the full production fleet yet**. The algorithm implementations are much closer to ready than they were in earlier reviews; most remaining blockers are now cross-layer production/provenance/evaluator issues, plus one major methodological exception: IBAC-SNI.

I would not reopen the core implementations of DrQ-v2, DrQ, CURL-RLViGen, RAD-DMCGB, SODA-DMCGB, ALDA, or the current IDAAC profile unless a concrete canary fails. The remaining work should be narrower and more disciplined.

## Launch blockers

| Priority | Issue | Consequence |
|---|---|---|
| **P0** | Final production renderer/container has not been cross-host certified | All visual training can occur on a different pixel distribution |
| **P0** | `source-lock.json` describes the old Places365-validation experiment | Returned immutable provenance can falsely describe a correct train-split run |
| **P0** | `run_manifest` hard-codes the RL-ViGen launcher for every family | Non-RLViGen results can contain false immutable execution provenance |
| **P0** | Places365 production disk preflight ignores the actual train dataset | SVEA/SGQN/SODA can pass preflight and fail during extraction/training |
| **P0/P1** | Current evaluator attestation is stale after CTRL eval-mode + frame-stack changes | Existing retained evidence does not certify the evaluator actually going to production |
| **P1** | Owner's new evaluation-policy ruling is not reflected in comparison blocking | Valid native comparisons are still excluded, especially CTRL |
| **P1** | PPG evaluation provenance is intrinsically unresolved upstream | Sampling is reasonable but cannot be claimed as verified original evaluation behavior |
| **P1** | IBAC-SNI is still a substantial authored hybrid | Cannot honestly be presented as a high-fidelity reproduction of the main IBAC-SNI condition |
| **P1** | Exact-final IBAC competence not demonstrated | Highest-risk adapted learner could consume three long seeds without evidence it functions |
| **P1** | CTRL raw-vs-executed action issue remains open | CTRL representation objective may condition on actions different from those producing transitions |
| **P1** | Concurrent GPU packing still fails open if device map is absent | Multiple jobs may silently converge on GPU 0 |
| **P1** | Runtime environment is not actually immutable despite pinned base-image digest | apt/pip resolution can change between nominally identical production jobs |
| **P1** | No final train→reload→full-grid→records→statistics canary | Individual pieces are tested, but the actual production lifecycle is not certified |
| **P1** | Seed/checkpoint/scope/estimand owner gates are not all frozen | Analysis choices remain movable after results become visible |

That is my actual stop list. Below is why.

---

## 1. Renderer equivalence remains the strongest fleet-wide scientific blocker

I would resolve this before any expensive training.

The project itself correctly retains an OWNER gate for production renderer verification. That is not bureaucracy. The policy learns from rendered images, so a renderer difference changes the **training environment itself**.

Your source tree can be perfect and your final offline evaluator can be perfectly standardized, but neither repairs 600k interactions learned under pixels that differ from the validated host.

The certification should use the **final** production closure:

- final container/image digest;
- exact benchmark/assets;
- `MUJOCO_GL=egl`;
- current evaluator;
- same checkpoint;
- same evaluation conditions;
- trusted host versus V100 production host.

I would add fixed-seed raw rendered-frame comparison. Returns are downstream and noisy; direct pixel witnesses answer the renderer question more cleanly.

Do this after finalizing the production image, not before, otherwise you certify an environment you subsequently replace.

---

# 2. `source-lock.json` currently records a false experimental history

This should be fixed before creating expensive immutable results.

Current production policy has correctly moved SVEA, SGQN and SODA back to Places365 **train**.

But `datasphere/native/source-lock.json` still contains the older accepted-adaptation statements describing Places365 **validation**, including the old 36,500-image validation asset pin.

That file is not harmless archival prose.

`datasphere/native/contract.py` copies its `accepted_adaptations` into the payload/run provenance.

So the following is currently possible:

1. production correctly trains SODA using Places365 train;
2. job succeeds;
3. immutable result provenance says the experiment used the validation adaptation.

That destroys an important benefit of the provenance machinery.

I would consider the source lock part of the experimental input and regenerate it from current truth.

It also appears to retain an older “root” repository identity alongside the current artifact commit. Even if both fields have distinct intended meanings, that distinction needs to be machine-obvious. A future reader should not encounter two plausible “source commit” values and have to infer which one actually produced the model.

### Stronger design

Do not manually duplicate current experimental adaptations into a static lock if the executable descriptors already know them.

Prefer provenance generated from:

```text
resolved family descriptor
+ upstream source reconstruction record
+ actual argv
+ actual asset
+ actual environment
```

rather than another manually maintained narrative list.

---

# 3. The per-result launcher identity is currently false for 7/12 families

`datasphere/native/run_probe.sh` currently emits something equivalent to:

```json
"command": "runnable/_launch/rlvigen.sh"
```

for every family.

That is wrong for:

- RAD;
- SODA;
- ALDA;
- IDAAC;
- PPG;
- IBAC-SNI;
- CTRL.

The effective configuration elsewhere may correctly contain their real argv, so this probably does **not** launch the wrong algorithm.

But it means the immutable manifest can make a false statement about how the result was generated.

I would fix this before production, because post-hoc editing of provenance is exactly what the provenance system is supposed to eliminate.

At minimum record:

```text
outer production entry point
family launcher
resolved argv
working tree/source digest
```

as separate fields.

---

# 4. Places365 train is now scientifically correct, but the production disk model does not include it

This is a real operational blocker for SVEA/SGQN/SODA.

`family.py::disk_requirement_gib()` accounts for things such as:

- replay;
- checkpoints;
- retained copies;
- result copies.

It does not account for the actual Places365 train asset.

Yet production currently does approximately:

1. copy the large Places365 archive into a host temporary directory;
2. extract the ~1.8M-image train dataset into the work filesystem;
3. construct the `ImageFolder` index;
4. retain normal training/checkpoint/replay state alongside it.

So a host can pass the project's formal disk preflight and still lack enough space for the workload the preflight supposedly certified.

There are actually two filesystem questions:

- enough space wherever the archive is copied;
- enough space on the work filesystem for the expanded tree plus normal RL state.

The previous validation/small-fixture tests do not certify this. Your current attestation fixture is much smaller than the real train corpus.

I would either:

- explicitly budget the compressed + expanded train corpus in `disk_requirement_gib()`, or
- avoid the redundant archive copy by read-only mounting a provisioned asset.

Then perform one real-asset provisioning canary before the three Places-dependent families fan out.

This is no longer a question about whether train vs validation is correct. **Train is the correct fidelity choice.** The remaining problem is that the resource/gate layer has not caught up.

---

# 5. The production environment is reproducible only at the base-image level

This deserves more attention than it currently receives.

The source lock pins a CUDA base-image digest. Good.

But each job subsequently mutates that image through things such as:

```text
apt-get update
apt-get install ...
pip install --upgrade pip
pip install ...
```

The Python package list is subsequently captured, which is useful.

But this is not the same as pinning the final environment.

Two jobs started months apart from the same base-image digest can receive different:

- Ubuntu packages;
- transitive apt dependencies;
- pip versions;
- transitive Python wheels;
- platform-specific binary distributions.

Your `gate_environment_manifest()` appears substantially weaker than its name suggests: finding that the source lock mentions a container/dependencies does not prove the **executed environment** is frozen.

### My preference before final production

Bake the now-working environment into a final image and pin:

```text
final-image digest
```

Then production jobs should not perform apt/pip mutation.

That immediately improves:

- reproducibility;
- renderer certification;
- startup time;
- dependency equality between families;
- postmortem tractability.

If you decide not to do that, at least capture:

```text
dpkg-query -W
apt source/snapshot information
pip version
pip freeze
Python version
CUDA/runtime libraries
MuJoCo version
GL/EGL libraries
```

and pin pip itself.

But the baked final image is considerably stronger.

---

# 6. Existing evaluator attestations are no longer evidence for the final evaluator configuration

The retained evaluator-validation ledger is stale in exactly the important places.

It still contains evidence corresponding to approximately:

- CTRL: stochastic evaluation, frame stack 1;
- IBAC-SNI: frame stack 1.

Current production is:

- CTRL: deterministic native evaluation;
- CTRL: frame stack 3;
- IBAC-SNI: frame stack 3.

So the old attestation did its job for an old experiment. It simply does not certify the current one.

I would rerun the evaluator-attestation wave after the final source/config/environment closure is frozen.

This is not asking you to rerun unit tests. The useful evidence is different:

> checkpoint → fresh process/import → exact final evaluator → actual records → physical pairing/provenance verification.

Given the cost relative to the eventual training fleet, I would certify all 12 final evaluator paths rather than only the seven that happen to have changed most visibly.

---

# 7. The new owner ruling on policy mode has not propagated to the comparison logic

This should be resolved before results exist.

The owner's current ruling, as you described it, is:

> stochastic versus deterministic action selection is not itself a units-breaking axis if each baseline is evaluated according to its original/native evaluation convention.

We established from original source:

- **IDAAC:** stochastic upstream evaluation.
- **IBAC-SNI:** stochastic upstream evaluation by default.
- **CTRL:** deterministic upstream evaluation.
- **PPG:** no dedicated upstream evaluation runner exists; sampling is supplied by its ordinary `act()` implementation, but original evaluation-time behavior cannot be verified.

Current CTRL evaluator has now been corrected to deterministic. Good.

But `scripts/comparison_blocks.py` still puts:

```text
policy mode
```

in `BLOCKING_AXES`.

That retains the **old policy**, not the owner's new one.

As a result, CTRL can be source-correctly evaluated and still be excluded from primary on-policy comparisons merely because it is deterministic while the others sample.

That is now internally inconsistent.

### What I would do

Remove policy mode as a generic blocking axis for a family whose native mode has been upstream-verified.

Then treat PPG separately.

There are two defensible PPG resolutions:

1. Owner accepts:
   > no upstream evaluator exists; sample is the closest released-code convention because the only supplied PPG action-selection function samples.

   Then PPG joins the same native-policy-mode equivalence class.

2. Owner decides lack of direct eval evidence prevents that conclusion.

   Then only PPG gets a provenance qualification—not all deterministic/stochastic cross-family pairs.

Do not continue using a global `policy mode` blocker after the owner explicitly ruled that the difference is acceptable when source-native.

---

# 8. PPG itself is now substantially improved

Several prior PPG objections are obsolete.

The current version has, as I understand the production resolver:

```text
1 environment
× 2048 rollout steps
32 minibatches
3 stacked frames
gamma = .99
policy LR = 3e-4
entropy = 0
N_pi = 32
```

That fixes the previous `8×256` trajectory-geometry issue.

This is now a good adaptation of the IDAAC authors' published DMC PPG comparator, using the OpenAI PPG implementation lineage.

### Remaining PPG issue 1: source naming

The current provenance still tends to compress two different things:

- **implementation source:** OpenAI released PPG;
- **continuous-control experimental profile:** IDAAC authors' DMC comparator.

Those should be separate provenance fields.

“PPG authors' released code” alone does not explain where the DMC-specific rollout/frame/LR choices came from.

### Remaining PPG issue 2: auxiliary LR

Current `aux_lr=5e-4` is actually a reasonable choice.

OpenAI's released PPG uses that auxiliary LR. The continuous-control comparator specifies the general learning rate as \(3\times10^{-4}\), but I have not found source evidence demonstrating that its **separate PPG auxiliary optimizer** was also changed to \(3\times10^{-4}\).

So I now prefer the current interpretation:

```text
policy LR = 3e-4     # DMC comparator
aux LR = 5e-4        # released PPG auxiliary default
```

over pretending `aux_lr=3e-4` is source-established.

Just document the ambiguity.

### Remaining PPG issue 3: evaluation

As above: sampling is reasonable, but not directly upstream-eval-verified.

The official PPG release exposes the training implementation but no dedicated evaluation runner that resolves this question. 

That is a provenance uncertainty, not a reason to invent deterministic evaluation.

---

# 9. IBAC-SNI remains the algorithm I would be most reluctant to call “done”

The project has improved it.

Current production apparently now has:

- authors' Impala pixel trunk;
- latent width 256;
- \(\beta=10^{-4}\);
- source-lineage LR;
- three Door frames;
- continuous Gaussian policy;
- entropy coefficient zero as a deliberate stability adaptation.

Those are meaningful corrections.

But its defining CoinRun result still uses a package of behavior absent from the Door port:

```text
12 posterior samples
shifted posterior scale
L2 = 1e-4
CoinRun UDA
SNI
beta = 1e-4
```

The authors' released main-result command explicitly contains:

```text
--l2 0.0001
-uda 1
--beta 0.0001
--nr-samples 12
--sni
``` 


The current PyTorch bottleneck still appears to use effectively:

```python
std = softplus(raw)
z = dist.rsample()
```

for one posterior sample.

The CoinRun implementation's 12-sample construction is not equivalent to just making the latent width correct. Those samples participate in the stochastic policy machinery.

Likewise:

- the original posterior scale uses the shifted construction roughly `softplus(rho - 5)`;
- L2 is absent;
- the original CoinRun UDA is not DrQ random shift—it consists of randomized colored rectangular occlusions.

### My production recommendation

If you do not want to make another substantial algorithm change immediately, **freeze the method as an explicitly hybrid baseline**:

```text
IBAC-SNI-hybrid-Door
```

and do not claim that it is a high-fidelity reproduction of the paper's main CoinRun condition.

If the stated objective remains “most fidelity to originals,” this is the one algorithm where I think further porting still has strong scientific justification.

The biggest next piece would be the 12-sample SNI/VIB policy semantics, not another superficial hyperparameter tweak.

---

# 10. Exact-current IBAC competence is still worth requiring

Even if you deliberately keep the hybrid.

This baseline has changed along several dimensions since the earlier instability tests:

- β;
- encoder;
- latent width;
- process count;
- frame stack;
- potentially resource profile.

The old observation that entropy `.01` drove Gaussian scale instability was useful and justifies entropy zero.

But it does not certify the **current complete variant**.

I would require one predeclared competence pilot before three long seeds.

Not:

> must achieve return X or we tune it.

Rather:

- finite losses;
- nonexploding `log_std`;
- action clipping not pathological;
- policy/value actually update;
- return moves nontrivially from initialization/random floor;
- no representation collapse.

That protects against spending the entire budget on an implementation that is technically alive but algorithmically dead.

---

# 11. CTRL's raw-action versus executed-action question remains genuinely open

This is not a generic PPO concern alone because CTRL consumes action information inside its representation objective.

For an adapted Gaussian policy, one can have:

\[
a_{\text{raw}}\sim\pi
\]

but the environment executes:

\[
a_{\text{exec}}
=
\operatorname{clip}(a_{\text{raw}},-1,1).
\]

If CTRL's clustering/sequence representation records \(a_{\rm raw}\), while the next state came from \(a_{\rm exec}\), then the representation learner is trained on a state-transition tuple containing an action that did not actually cause the transition.

If clipping is extremely rare, this is irrelevant.

If clipping is common, it is a real semantic mismatch.

The current project has diagnostic support but, from the material I reviewed, not the final comparison/measurement needed to close this question.

I would measure during actual short training:

```text
coordinate clipping fraction
transition clipping fraction
mean |a_raw - a_exec|
max raw action
policy log_std
```

for CTRL and preferably PPG/IDAAC/IBAC too.

Do not automatically change to a tanh-squashed policy; that would introduce another adaptation.

First determine whether a problem exists.

---

# 12. GPU packing should fail closed, not merely support explicit device lists

The old problem where the production wrapper dropped `NATIVE_CELL_DEVICES` is fixed.

But the underlying runner still apparently allows:

```text
NATIVE_CONCURRENT=1
```

without requiring a device map.

In that case multiple CUDA processes can see the same GPUs and independently choose cuda:0.

That is dangerous because it produces a plausible-looking launch until both jobs collide on one GPU.

For production-scale multi-cell jobs I would enforce:

```text
if concurrent CUDA cells > 1:
    NATIVE_CELL_DEVICES must exist
    length(device list) == number of cells
    devices must be unique
```

Otherwise abort.

This is preferable to a permissive fallback.

---

# 13. Result mirroring currently provides less durability than its language suggests

The wrapper sensibly requires a second filesystem/mirror location for production.

But the final mirror appears to happen **after** completion.

That has two implications.

First, if the final mirror copy fails, the wrapper currently seems able to warn rather than fail the whole production contract. If the second copy is required, that should produce an incomplete/nonzero result state.

Second, and more important: final copying does not protect a 40-hour job from primary-volume loss at hour 35.

If the intent is merely:

> leave two copies after successful completion,

current behavior is mostly fine after making copy failure fatal.

If the intent is:

> survive storage loss during production,

periodically mirror retained checkpoints or place working checkpoints on durable storage.

Do not describe final post-run copying as protection from mid-run primary-volume failure.

---

# 14. Current Places attestations are not the same thing as proving the real train corpus path

This deserves its own note.

The project has exercised train semantics using a small train fixture—roughly 1,000 images in the current attestation material.

That proves:

- split selection;
- loader rooting;
- probably archive/layout handling.

It does **not** prove operational behavior of the real source train corpus with ~1.8M images.

The full corpus can change:

- `ImageFolder` startup/indexing memory;
- startup time;
- filesystem inode pressure;
- page-cache behavior;
- extraction duration;
- disk requirement.

The V100 host has plenty of RAM, so I do not expect a conceptual ML failure here. But the first real SVEA/SODA/SGQN run should not also be the first time the complete production asset is expanded and consumed.

One asset canary is enough.

---

# 15. Time-limit semantics remain a deliberate comparability seam

This is not something I recommend “fixing” now, but it must be frozen.

Current families split approximately:

**bootstrap through timeout**

- RAD;
- SODA;
- ALDA.

**treat Door horizon as terminal**

- other nine.

Because Door essentially runs to its horizon, this affects a meaningful fraction of return targets.

There are two defensible philosophies:

- source-faithful timeout semantics;
- one common finite-horizon MDP semantics.

The project has chosen source fidelity.

I think that is defensible.

But then bootstrap-vs-terminal cross-family comparisons are not identical training objectives and should remain qualified/descriptive where your comparison policy says so.

Do not change this after seeing results.

---

# 16. There is currently no primary ALDA-vs-CURL “latent group” comparison

This falls out of the project's own comparison rules.

ALDA and CURL differ on at least:

- network/input size;
- timeout semantics.

Current blocking therefore gives the two-member latent group **zero primary pairs**.

That means if the conceptual study intends to make a strong claim like:

> among latent/representation approaches ALDA beats CURL

the existing “same-axes primary comparison” framework cannot support that as a primary inferential contrast.

Either:

1. accept that this mechanism group has no same-axes primary pair and report the two descriptively;
2. create a prespecified standardized secondary comparison;
3. or stop describing it as a primary comparison group.

Do not silently loosen the axes only after seeing which one wins.

Similarly, current off-policy primary comparisons partition around observation/timeout choices rather than producing all-pairs inference.

That is fine if intentional.

---

# 17. Reward normalization differences affect optimization but not reporting units

Current roughly:

**normalized training rewards**

- IDAAC;
- PPG;
- CTRL.

**raw training rewards**

- the others.

The evaluator reports raw environment return for all.

I agree with treating this as a source-native algorithm/training difference rather than a reporting-units failure.

But it belongs in the methods table because reward scaling interacts strongly with:

- value loss;
- optimizer magnitude;
- entropy scale;
- auxiliary-loss relative weights.

It should not accidentally disappear from the final reproducibility description just because all plotted returns use common units.

---

# 18. Three frames for all twelve is still my recommended Door policy

I rechecked this in the original sources already, and nothing in the current artifact changes the conclusion.

For the DMC/visual-control lineage, three frames is native.

For PPG and IDAAC, the authors' published DMC continuous-control comparator uses three stacked frames.

For IBAC-SNI and CTRL, their original one-frame Procgen configurations are special:

- IBAC-SNI explicitly says no frame stack is necessary because velocity is painted into the image.
- CTRL similarly enables Procgen velocity painting.

Door does not paint velocity into a single image.

Therefore three Door frames gives those algorithms a closer dynamical information set than one unaugmented Door RGB frame would.

I would retain stack=3 for all twelve.

But clean up stale comments that still say “10/12 use 3 and 2/12 use 1.” Current executable truth is 12/12.

Because these comments live next to protocol/comparison logic, stale statements here are more dangerous than random historical prose.

---

# 19. Keep spatial render/input size source-faithful rather than forcing one common resolution

Current spatial geometry is sensible:

- RL-ViGen five: 84×84;
- RAD/SODA: 100 render → 84 crop;
- ALDA/PPG/IDAAC/IBAC/CTRL: 64×64.

I would not standardize that before production.

For RAD/SODA especially, 100→84 is part of their image augmentation pipeline, not an arbitrary sensor choice.

The experimental claim should therefore be:

> source-/implementation-faithful benchmark adaptations under a common Door task,

not:

> all algorithms see exactly the same neural input tensor and differ only by learning objective.

Those are different studies.

A common-resolution sensitivity experiment could come later.

---

# 20. Common 600k budget is scientifically clean, but very far from some source horizons

This is another place where interpretation matters.

Approximate relationships:

| Family lineage | Source horizon | Door common horizon |
|---|---:|---:|
| RAD/SODA/ALDA / canonical SGQN-ish | ~500k | 120% |
| RL-ViGen easy-setting families | ~1.1M | ~55% |
| IDAAC/PPG DMC | 1M | 60% |
| CTRL | 8M | 7.5% |
| IBAC-SNI CoinRun | 160M | **0.375%** |

A fixed 600k budget is perfectly valid if the research question is:

> what do these methods accomplish under equal Door interaction budget?

It is **not** equivalent to:

> faithfully reproduce each paper at its convergence/training horizon.

This particularly matters for IBAC-SNI and CTRL. A weak 600k result may reflect genuine sample efficiency rather than an implementation bug.

So competence pilots should detect broken learning—not guarantee source-level ultimate performance.

For IDAAC, remember its fixed 1M LR schedule means a 600k common-budget endpoint intentionally occurs part-way through that source schedule; do not silently renormalize decay to end at zero exactly at 600k unless you want a different experiment.

---

# 21. Freeze owner decisions before first outcome is inspected

The production gate still appears to have owner-level unresolved/freeze requirements around:

- fixed 3-seed allocation;
- endpoint checkpoint rule;
- Door-only production scope;
- estimand/time-limit choices;
- possibly comparison policy.

These should not remain “obvious operational intent.” Turn them into frozen declarations before production results become visible.

My preferences:

```text
seeds:
    exactly 3 prespecified seeds per baseline

headline:
    fixed common endpoint

checkpoint selection:
    no best-checkpoint selection

curves:
    descriptive

scope:
    Door only for this experiment

scene set:
    fixed before outcomes

outer inferential unit:
    seed, not episode
```

Three seeds is small. Report each seed. Avoid episode-level pseudoreplication.

Do not:

1. choose the best member of an algorithm group from these same three seeds;
2. then conduct a naive inferential test only on the winners.

That introduces selection bias.

---

# 22. A complete lifecycle canary remains worth doing even with excellent unit tests

I agree with you that there is no value in my rerunning your local test suite.

The canary I care about is different.

The project still needs one actual production lifecycle:

```text
production trainer
→ retained endpoint checkpoint
→ completely fresh evaluation process
→ all required regimes/scenes
→ normalized records
→ physical-pairing proof
→ statistics/report consumer
→ durable result archive
```

I would make the first DrQ-v2 seed the staged production canary.

Reasons:

- high confidence algorithm;
- representative RL-ViGen code path;
- large replay/checkpoint behavior;
- no Places dependency;
- relatively little methodological ambiguity.

Do not release the remaining fleet until that exact seed reaches the end of the pipeline and you inspect the artifact contract.

This is not pretesting the scientific result. It is validating the production system.

---

# 23. V100 throughput is still mostly a planning unknown

That is operational rather than scientific, but it matters if jobs have hard timeouts.

Several final configurations differ materially from older measurements:

- IDAAC now 1×2048 with more policy reuse;
- CTRL restored to 64 envs;
- all on-policy families now stack three frames;
- IBAC encoder/latent configuration changed;
- Places families will use full train asset.

Old T4/DataSphere throughput is not a reliable basis for tight V100 deadlines.

If production timeout is generous enough that this cannot kill a valid run, this does not block science.

If jobs have scheduled hard deadlines, get short final-config V100 throughput measurements first.

---

# 24. CTRL's 64-env RAM planning bug is fixed

Do not carry forward my old criticism.

Current planner now budgets approximately 54 GiB rather than incorrectly reusing the old ~13.6-GiB 16-env measurement.

That estimate is still extrapolated rather than measured on the exact V100 64-env run, but it is at least dimensionally consistent and should fit comfortably on the stated host when run alone.

I would get a direct measurement before aggressively packing another memory-heavy workload beside it.

---

# 25. SODA auxiliary LR is fixed

Also resolved.

Production now uses:

```text
aux_lr = 3e-4
```

matching the algorithm-specific official DMCGB SODA launch rather than the generic parser's `1e-3`.

I regard SODA as one of the stronger baseline implementations once the Places/environment/provenance common issues are closed.

---

# 26. IDAAC is also now fundamentally sound

Current C2 follows the published DMC continuous-control recipe closely:

- 1 process;
- 2048-step rollout;
- 32 minibatches;
- 10 PPO epochs;
- LR \(3\times10^{-4}\);
- \(\gamma=.99\);
- λ .95;
- entropy zero;
- value epochs 9;
- value frequency 32;
- .1 advantage coefficient;
- .1 invariance/order coefficient;
- 3 frames;
- literal 1M LR schedule.

The old episode/autoreset identity issue appears statically repaired and has an integration test in the project.

I would not change the algorithm further absent evidence.

Its remaining risks are the common renderer/evaluator/production closure and obtaining realistic resource behavior for the new workload.

---

# 27. The RL-ViGen baseline labels should remain explicit

Your current provenance direction is much better.

Keep distinctions such as:

- `DrQ-v2-RLViGen`;
- `DrQ-RLViGen`;
- `CURL-RLViGen`;
- `SVEA-RLViGen-release`;
- `SGQN-RLViGen-release`;
- `RAD-DMCGB`;
- `SODA-DMCGB-official`;
- `ALDA-official-Door`;
- `IDAAC-DMC-reference-Door`;
- `PPG-IDAAC-DMC-reference-Door`;
- `IBAC-SNI-hybrid-Door`;
- `CTRL-release-Door`.

Because:

- RL-ViGen CURL is deliberately not canonical CURL;
- RL-ViGen SVEA has a different learner/augmentation lineage from canonical SVEA;
- RL-ViGen SGQN release differs from both canonical SGQN and parts of RL-ViGen's own published parameter table;
- DMCGB RAD is standardized RAD, not the byte-identical original RAD architecture;
- CTRL paper and released defaults genuinely disagree.

These are not implementation failures once named correctly.

---

## What I would fix before production, in exact order

1. **Build/freeze the actual final runtime image**, preferably eliminating runtime apt/pip mutation.
2. **Fix `source-lock.json`** so it describes current Places-train/current adaptations/current source truth.
3. **Fix per-run manifest launcher identity.**
4. **Add Places train to disk/resource preflight** and test provisioning with the real corpus.
5. **Make concurrent GPU assignment fail closed.**
6. **Certify renderer equivalence on the final image/V100.**
7. **Resolve the policy-mode governance mismatch:** remove native policy mode as a generic blocking axis per the owner's ruling; explicitly decide how PPG's unverifiable upstream evaluation convention is treated.
8. **Regenerate evaluator attestations for the final 12-family closure**, including physical-pairing evidence.
9. **Decide IBAC-SNI's scientific status:** either port the remaining major CoinRun machinery or freeze it explicitly as the hybrid.
10. **Run exact-final IBAC competence diagnostics.**
11. **Measure CTRL/raw-action clipping semantics**, and general Gaussian clipping diagnostics while doing the on-policy pilots.
12. **Freeze seeds/checkpoint/scope/statistical rules.**
13. **Stage the first DrQ-v2 production seed through the entire downstream pipeline.**
14. Only then **fan out the fleet**.

I would not spend another pre-production cycle tinkering with the core DrQ-v2/DrQ/RAD/SODA/ALDA/IDAAC learning implementations. The expected value is now much higher in closing the production/provenance/evaluator contracts and deciding IBAC's fidelity boundary.

The most important qualitative change from earlier reviews is that the project is no longer primarily threatened by obvious baseline hyperparameter mistakes. It is now threatened by **the possibility that the thing you actually run, the thing you later say you ran, and the thing the evaluator attestation certifies are subtly different objects**. Fix that last layer before the expensive run.
