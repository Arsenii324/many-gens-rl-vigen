# Where we actually are, measured against the original goal

2026-08-10. Written after the audit and the four deep-research passes, as a deliberate
top-down check rather than a summary of recent activity. `PREMISES.md` maps the decision surface
and `FAITHFULNESS.md` maps per-algorithm fidelity; **this document asks the different question of
how much of the actual task is done.**

---

## 0. The goal, restated

> Take twelve visual-RL generalization algorithms, train them under one protocol on one benchmark,
> and measure how much performance each retains when the visuals change.

Everything else — the twelve `train.sh` scripts, the shared evaluator, the plotting — is
infrastructure in service of one comparison. So progress has two independent axes, and they are at
very different places.

| axis | state |
|---|---|
| **Infrastructure** — can we run this, identically, for twelve methods? | **Essentially complete and verified** |
| **Science** — do we have a defensible comparison? | **Not started.** No result exists, and none should be quoted |

**The blunt version: we could have produced a full twelve-row table a week ago, and several of its
rows would have been meaningless.** SGQN's saliency head could not learn; the PPO family updated on
8-sample minibatches with no terminal in any rollout; DrQ ran a 3-step estimator where both its
sources say 1-step. None of those crash. All of them produce plausible numbers. The audit is what
stands between a table and a *true* table, and it is the reason there is no result yet.

---

## 1. Against the seven acceptance criteria

From `TASK.md` §3. "Structural" means the failure is impossible rather than merely absent.

| | criterion | state | evidence |
|---|---|---|---|
| **R1** | one `sh` script trains any baseline | **met** | 13 generated `train.sh`; all completed real-simulator runs under one protocol hash |
| **R2** | per-baseline directory + README naming deps | **met** | generated from the registry; a test regenerates and diffs, so a stale one fails the build |
| **R3** | evaluation identity | **met, structurally** | one `evaluate()` taking an opaque `policy`; AST test asserts exactly one eval stepping loop; a test mutates the label parameters and requires identical numbers |
| **R4** | equal training length, or a stated reason | **met in letter; was violated in fact; now largely repaired** | see §2 — this is the criterion the audit hit hardest |
| **R5** | one plotting routine over the logs | **met** | `plot.py`; a test asserts what it draws equals what was logged |
| **R6** | baseline coverage | **met numerically, contested scientifically** | 12/12 implemented, none an alias — but see §4 on whether four of them mean anything here |
| **R7** | clone-to-curve works | **reproducibility closed; the end-to-end clean-clone run still outstanding** | see §2a — a fresh `install.sh` now genuinely reproduces our tree, which it did **not** an hour ago |

**R4 deserves its own sentence.** It was satisfied mechanically — one shared `base`, one diffable
deviation list — while six of twelve baselines ran at a learning rate their own authors never used,
three of them because the key was silently dropped by their builder. That is the single most
instructive finding in the project: *a criterion can be enforced by a test and still be false.*

---

## 2. What the audit changed, and what it cost

Applied, each traceable to a primary source (`FAITHFULNESS.md` §0a):

| fix | from → to | source |
|---|---|---|
| SGQN `aux_lr` | 0.3 → **8e-5** | RL-ViGen Table 6; 8e-5 is its value across *all five* of its benchmarks |
| SGQN `sgqn_quantile` | 0.95 → **0.9** | canonical SGQN's own argparse default **and** RL-ViGen Table 6 — they agree |
| PPO `num_steps` | 256 → **2048** | IDAAC Appendix E, "2048 steps, 1 process" |
| PPO `gamma` | 0.999 → **0.99** | same; 0.999 is Procgen's, for ~1000-step episodes |
| `ctrl_coef` | 0.1 → **removed** | `pseudocode.tex:57` is a plain sum; the official repo has no such scalar |
| `ctrl_clusters` | 8 → **32** | SwAV equipartition collapses when clusters are large relative to batch |
| DrQ `nstep` | 3 → **1** | RL-ViGen's paper *and* its own `drq_config.yaml` |
| rad/soda `actor_lr`/`critic_lr` | implicit → **explicit 1e-3** | same value, now a declared choice rather than a dropped key |

Two of these needed a code change, not a config change: `sgqn_quantile` was not in the builder's
passthrough list (**a knob the config cannot reach is not a knob**), and `ctrl_coef` was wired into
the loss.

### 2a. Chasing "what does a clean clone actually get?" found the fix incomplete

The first repair made `--check` diff the whole vendored tree instead of only confirming our four
patches. That closed *undeclared-but-present* drift. It did **not** close the other direction, and
five files were declared allowed-to-differ while **only one** was reproduced by any script:

| file | was | now |
|---|---|---|
| `algos/drq.py` — `np.float32` cast on `log_alpha` | orphan hand-edit | **patch P5** |
| `cfgs/task/TwoArmHandOver.yaml` | orphan hand-edit | reverted |
| `envs/DMCVGB/dmcvgb/wrappers.py` | orphan hand-edit | reverted |
| `envs/DMCVGB/dmc2gym/dmc2gym/wrappers.py` | orphan hand-edit | reverted |
| `cfgs/aug_config.cfg` | written by our fetch script | unchanged, still declared |

**The `drq.py` orphan was load-bearing.** `np.log` of a Python float is float64, MPS does not
support float64, so on a fresh Mac install DrQ dies at construction. That edit sat in the tree for
weeks because someone needed it to run and never wrote it down — the precise failure the patch
mechanism exists to prevent, inside the tree the patch mechanism guards.

Verified before/after: the three reverted files are off our path (`robo_wrapper` imports
`wrappers/dmc.py`, a *different* and unmodified file). P5 applies to a pristine `drq.py`, and
`Protocol.env_patches` was pinned by a test that promptly failed with
*"names ['P1'..'P4'] but apply_patches.py applies ['P1'..'P5']"*. Hash moved again
(`07923ae8…` → `c0d7bc7c…`).

**Also found, and not ours to fix:** RL-ViGen tracks two paths differing only in one letter's case,
`TwoArmHandOver.yaml` and `TwoArmHandover.yaml`. macOS is case-insensitive, so only one can exist
and git reports the other permanently modified. **RL-ViGen cannot be checked out cleanly on a Mac
at all.** Cosmetic for Door/Lift, real for "clone and run", now declared with that reason.

---

## 3. Degrees of freedom still open

The honest inventory. **Sourced** means a primary source specifies it and we follow. **[OURS]**
means we chose it. The second group is the real answer to "what don't you have covered".

### 3a. Now sourced and closed

`action_repeat=1` · `discount=0.99` · n-step per family · SGQN's three knobs · PPO rollout and
minibatch · entropy coefficient 0.0 · learning rate per family · replay 1e5 (= SECANT's robosuite
value) · frame stack 3 · hidden dim 1024 · 100 eval episodes over 10 scenes · deterministic policy
· final checkpoint · raw undiscounted return.

### 3b. Open, ranked by how much they can distort the comparison

| # | degree of freedom | current | the alternative, and why it matters |
|---|---|---|---|
| 1 | **headline metric** | raw return | success rate. A random arm scores ~7.5 on `Lift` with **zero** successes, because the reward pays `1−tanh(10d)` every step and nothing terminates. This can invert a ranking. |
| 2 | **`feature_dim` for SVEA/SGQN** | 50 | RL-ViGen's paper says **256**, its code says 50. A 5× representational bottleneck on exactly the two augmentation arms expected to lead. |
| 3 | **checkpoint selection** | final | the prior project measured retention oscillating `125→326→19→51→45→90→7 %` across checkpoints of one run. We may be reporting checkpoint noise. |
| 4 | **seeds** | 1 | 3–5. Nothing supports a ranking claim at n=1, and this is the axis that actually costs compute. |
| 5 | **training budget** | 5e5 | Table 6 specifies **Door 6e5, Lift 8e5**. Ours was invented; theirs is sourced. **NUMBERS NOW BEAR ON THIS, 2026-09-03** — the owner asked whether they could. `drqv2-s2`'s own budget curve (`bt12o3nc3fg8g0ffhaso`, eval.csv): train-regime **0.84 → 30.67 → 283.66 → 453.91 → 456.06** at 0/25k/50k/75k/100k, with `train_regime_success` reaching **1.00 at 75k**. That is **saturation by 75k**: the last 25k buys +0.5%. So for this baseline 6e5 buys nothing over 1e5 *on the training distribution*. **But the eval column does not trend at all** — 0.80, 13.87, 3.27, 45.44, 5.61 — so there is no evidence generalisation emerges with more frames, and none that it does not: at `num_eval_episodes=20` over ten scenes that is **2 episodes per scene**, too noisy to read. **The decision this supports**: set the budget per baseline from a saturation curve rather than from one global number, and get the curve from the 50k stamp grid plus offline evaluation ([`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md) §4) — cheap, because re-evaluating a retained checkpoint costs ~168 RUB against hours of GPU for a longer run. **One seed, one baseline; not yet a finding about the twelve.** |
| 6 | **CTRL pair selection** | same cluster | the paper samples from *neighbouring* clusters — the substantive half of the method. |
| 7 | **CTRL optimizer** | shared with policy | the paper runs two optimizers over **disjoint** parameter sets; policy params are not in the SSL update at all. |
| 8 | **exploration schedule** | `linear(1.0,0.1,500000)` | rescaled `linear(...,80000)` preserves DrQ-v2's 16 %-of-training anneal. As-is, DDPG-family arms never train under low noise. |
| 9 | **`init_log_std`** | ~~−1.0 (σ₀ = 0.368)~~ **0.0 (σ₀ = 1.0) — corrected 2026-09-03; this row was stale** | **Already at the alternative.** Every constructed continuous head initialises log-std to zero: `ibac_sni/torch_rl/model.py:143` `torch.zeros`, `ctrl/models.py:129,254` `nn.initializers.zeros`, `idaac/distributions.py:89` `AddBias(torch.zeros(...))`; `ppg/train.py:104`'s own comment records that log_std = 0 gives entropy 9.9326, and a live `ibac_sni` cell logged 9.944 at its first update. So the project believed it carried a deviation it does not carry. `INTEGRATION-DELTA.md`'s M4 made the same claim and is refuted on the same evidence. **Nothing to decide here; the row was the defect.** | Kostrikov's convention, which IDAAC states it builds on, is **σ₀ = 1.0**. Defensible for clipped actions, but `[OURS]` and undeclared until today. |
| 10 | **train-side eval episodes** | 10 | RL-ViGen runs **100** for both sides. The term we subtract has a tenth of the samples. |
| 11 | **SVEA augmentation** | `random_overlay` (RL-ViGen's) | canonical is `random_conv`. Ours makes `svea` and `soda` share an augmentation instead of contrasting two. |
| 12 | **IBAC-SNI deterministic pass** | not audited | must fix the **VIB latent**, not the action distribution — fixing the latter changes which algorithm we run. |
| 13 | **batch size** | 256 | SECANT and PVM-Robotics both use 512 on Panda. |
| 14 | **PPG `N_π`** | 32 | at 500k frames that is ~7 auxiliary phases in a whole run; 8–16 makes the mechanism observable. |
| 15 | **gap definition** | absolute difference | needs a floor + competence gate: **a method that never learns has gap ≈ 0, which reads as perfect generalization.** |
| 16 | **run-level statistic** | mean | our IQM defence was a level error (IQM aggregates runs, not episodes). Conclusion survives, argument does not. |

---

## 4. The concern that outranks all the knobs

**Four of the twelve may not be measuring what their names say**, and no hyperparameter fixes that:

- **IDAAC.** *(Corrected 2026-08-10 after reading the paper directly — my first description of
  this was mechanically wrong and the correction makes the point sharper, not weaker.)*
  The discriminator does **not** classify level identity. It takes two observations **from the same
  trajectory** and predicts which came first (Fig. 2: labels `{0 if i<j, 1 if i>j}`, adversarial
  target 0.5); the encoder is pushed to make that prediction impossible. So the mechanism is
  "strip temporal-position information", and it **still operates** on a single scene — it is not
  inert.

  What is absent is the *reason to expect it to help*. The paper's chain is explicit (§4.3):
  "**Since different levels have different lengths**, capturing such information ... translates
  into capturing information specific to that level." And §6 states the condition directly: "the
  settings where we can expect most gains are those with partial observability, a set of goal
  states, and **episode length variations**."

  We have one scene and a fixed 500-step horizon with no early termination — **no episode length
  variation at all**. By the authors' own stated condition, IDAAC should not be expected to gain
  here. The paper never ablates the invariance loss against the number of training levels, so the
  single-scene boundary case is untested rather than contradicted.
- **CTRL.** No continuous reference implementation exists. Two structural divergences remain open
  (items 6 and 7 above).
- **IBAC-SNI.** No continuous reference implementation exists anywhere searched.
- **PPG.** A continuous implementation exists (XuanCe) but is itself unvalidated on continuous
  control, and may carry a tanh log-det-Jacobian defect.

And the honest meta-point: **the brief asks for twelve baselines, which is exactly the pressure that
produces a table with four rows that do not mean anything.** The options are to report them
explicitly labelled as unvalidated continuous adaptations, or to cut them. Quietly including them
is the one option that is not available.

---

## 5. What I would cross-check next, and with what

Ordered by how much doubt each removes per unit of effort.

| # | cross-check | what it would settle | cost |
|---|---|---|---|
| ~~1~~ | ~~Run a policy through our `evaluate()` and RL-ViGen's `robo_eval`~~ | **DONE, at n=100/side.** Same seeded policy through both, RL-ViGen's side calling `robo_make` directly and bypassing every line of `rlgen`: ours **1.4764**, theirs **1.3706**, difference +0.1058, SE 0.1769, so `abs(z) = 0.60` — agree within sampling error. **Minimum detectable effect ≈24% of the mean**, so the claim is "no systematic distortion larger than about a quarter of the mean", not "they agree". An earlier n=30 pass gave +0.4464 and a 44% bound; quadrupling the sample cut both, which is what sampling noise does. `VALIDATION.md` §0.05 | done |
| 2 | **Sanity gate: reproduce RL-ViGen's ordering** — augmentation arms ~240–305 vs DrQ-v2/DrQ/CURL ~48–59 on Robo-EASY | Whether the whole stack lands in the right regime. If SGQN does not lead the augmentation group, the aux-lr fix did not take. | one real run per arm |
| 3 | **Diff `third_party/robosuite` against SECANT's fork** (now in `ext/`) rather than PyPI | What "the environment" actually is. Our "761 files differ" over-attributes SECANT's changes to RL-ViGen. | ~1 h |
| 4 | **DeGuV (arXiv 2509.04970) per-task Door/Lift numbers** | The only published *per-task* figures on this backend — RL-ViGen aggregates over three tasks. An independent sanity target. | reading |
| 5 | **RL-ViGen issue #6** ("About parallel training") | Whether `num_envs=1` is truly forced. Less urgent now: IDAAC's own continuous config is 1 process, so it is legitimate rather than merely tolerated. | blocked for the DR agent; may work over `gh` |
| 6 | **Unit tests on the Gaussian machinery** | Analytic KL vs Monte-Carlo; entropy closed form; `log_prob` summing over 7 dims. Catches the class of defect suspected in XuanCe. No training run needed. | ~1 h, highest ROI of the code-level checks |

**What kind of source would help most**, generically: not more papers. The gap now is *numerical
agreement with an independent implementation on the same input* — which is why item 1 outranks
everything. We have three independent structural corroborations (RL-ViGen's code, SECANT, the
sibling project's random-policy floor) and **zero** numerical ones beyond the random-policy floor.

---

## 6. General concerns, stated plainly

1. **Nothing has been trained at meaningful scale.** Every number in this repo is from a
   3 000-frame smoke run whose only purpose is to prove a code path executes.
2. **The comparison may still be uninterpretable along algorithm-family lines** even after the lr
   fix, because the shared base remains DrQ-v2-calibrated and the arms differ in how much they
   depend on it. This is a stated limitation, not a solved problem.
3. ~~`setup/install.sh` does not reproduce the tree~~ — **fixed, in two stages, the second only
   because the first was checked.** See §2a.
4. ~~`Protocol.env_patches` is stale~~ — **fixed.** It named three patches while four were applied,
   and nothing ever wrote it despite its comment. Corrected, and pinned to `apply_patches.py` by a
   test so it cannot drift again. **The protocol hash changed as a result** (`b5ba34d3…` →
   `07923ae8…`), which is the invalidation property working: the declared patch set genuinely
   changed, so prior runs must not silently pool with new ones.
5. **The protocol hash covers evaluation, not training.** Changing `nstep` altered training without
   changing the hash. That is defensible but easy to misread as "same training conditions".
6. **Two acronym collisions in one project** (ALDA → an AAAI image-classification paper; CTRL → an
   LLM-critic paper). Both were caught. The base rate of this is higher than it looks and every
   citation deserves a check against its actual content.
7. **The audit found its own errors as fast as the code's.** Five of my published claims were
   withdrawn or corrected in a single day. The register of what is *provisional* is now part of the
   deliverable (`SHARED-CONTEXT.md` §3) precisely because that rate is not going to be zero.

---

## 7. If I could do one thing next

Item 5.1 — put one checkpoint through both evaluators and compare. It is half an hour, it needs no
decision from anyone, and it converts "our evaluator is structurally identical to the reference"
into "our evaluator agrees with the reference to within sampling error", which is the difference
between a design argument and evidence.
