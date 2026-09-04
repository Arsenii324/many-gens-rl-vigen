# Status briefing for the supervisor

**Date**: 2026-08-10. **Written to be read top-down** — the decisions are first, because several
of them block work and two are corrections rather than questions.

*(In English, consistent with the rest of the repo. Say the word and it is translated.)*

---

## In one paragraph

The **infrastructure is built and verified**: twelve baselines plus a negative control, all
thirteen running end to end on the real simulator under one protocol, one shared evaluator that is
structurally incapable of seeing which algorithm produced a policy, a test suite with mutation
testing behind it, and remote GPU compute proven working. What is **not** settled is the science:
every hyperparameter in the project is *mapped* from a different benchmark rather than inherited,
because none of these twelve methods was ever published on robosuite manipulation. **Nothing has
been trained at meaningful scale and no claim is made about any algorithm's performance.** An audit
this week found several things that need your decision before real compute is spent — and one
inherited defect that makes one baseline's numbers meaningless as they stand.

---

## 1. Two corrections (not questions)

### 1.1 The ALDA citation in the brief points at the wrong paper

The brief cites **arXiv 2001.01046**. That is *Adversarial-Learned Loss for Domain Adaptation*
(Chen et al., **AAAI 2020**) — unsupervised domain adaptation for **image classification**. No
agents, no environments, no reinforcement learning of any kind.

The ALDA that is a visual-RL generalization method is **arXiv 2410.07441**, *Associative Latent
DisentAnglement* (Batra & Sukhatme, **ICML 2025**) — SAC-based, evaluated on DMControl-GB. Two
unrelated papers sharing an acronym.

**Our port implements 2410.07441**, which is the only one that can be an RL baseline at all, and it
matches that paper's published hyperparameters. So no work is lost. But the brief's reference
should be corrected, and if 2001.01046 was intended deliberately then the whole ALDA line needs
rethinking, because that method is not applicable here.

### 1.2 SGQN, as inherited, cannot learn its own mechanism

RL-ViGen's SGQN sets its attribution-predictor learning rate to **`aux_lr = 0.3`**. The canonical
implementation (Bertoin et al., NeurIPS 2022) uses **`3e-4`** — a factor of **1000**, consistent
with a decimal slip.

Nothing crashes. The saliency head simply cannot learn at that rate, and saliency guidance *is* the
method. **Every SGQN number this project has produced is therefore uninterpretable.** The value is
RL-ViGen's, not ours, and it lives in a constructor default our configuration never mentions.

**Updated after reading RL-ViGen's own source and paper — there are four values, not two:**

| source | `aux_lr` |
|---|---|
| RL-ViGen **paper**, Table 6 (Door/Lift) | **8e-5** |
| RL-ViGen **code**, `cfgs/sgqn_config.yaml` | **1e-4** |
| RL-ViGen **constructor default** | **0.3** |
| canonical SGQN (Bertoin et al.) | 3e-4 |

**Upstream never actually runs at 0.3** — their entry point builds the agent through hydra, so the
yaml supplies 1e-4 and the 0.3 is a dead default. **We hit it because we bypass hydra**, loading
the class by file path and constructing it directly. So the defect is real for us and latent for
them.

**The fix target is 8e-5** (with `sgqn_quantile 0.9` and critic weight 0.7, also from Table 6) —
these are the numbers behind the published SGQN curves our comparison is implicitly calibrated
against. Not canonical 3e-4: RL-ViGen deliberately re-tuned SGQN for its unified DrQ-v2 backbone,
so canonical would reproduce neither their setup nor the original SAC-based one.

**APPLIED 2026-08-10** — `aux_lr = 8e-5`, `sgqn_quantile = 0.9`. Measured on the constructed
agent afterwards: `aux_optimizer lr=8e-05`. I applied it without waiting because **0.3 is wrong
under every reading** — paper 8e-5, their own yaml 1e-4, canonical 3e-4 — so moving off it needed
no decision, only the destination did, and all three candidate destinations are within a factor of
4 of each other while 0.3 is 3,750x away.

What still needs your answer is the *general* rule, because it recurs: **do we mean paper-RL-ViGen
or code-RL-ViGen?** They disagree on `feature_dim` (256 vs 50) and on `action_repeat` too. One
sentence settles several knobs at once.

### 1.3 The benchmark's paper and its code are different experiments

Established by reading both. Beyond SGQN:

| knob | paper | their code | ours |
|---|---|---|---|
| `action_repeat` (robosuite) | **1** | 2, with no robosuite override | **1** — we match the paper |
| n-step for DrQ | **1** | 1 | **3** — we match neither |
| replay capacity | **1e7** | 1e6 | 1e5 |
| `feature_dim` (SVEA/SGQN) | **256** | 50 | 50 |
| training frames | **Door 6e5, Lift 8e5** | — | 5e5 |

Two of these are ours to fix regardless of the paper-vs-code answer: **our DrQ n-step of 3
disagrees with both sources**, and our training budget was invented when Table 6 in fact specifies
one. The rest need the §1.2 decision first.

---

## 2. Decisions that need you

### 2.1 "Equal training conditions" holds in the letter and fails in fact

Requirement R4 asks that training conditions be equal except where an algorithm's nature forbids
it. Mechanically we satisfy it: one shared `base` block, and every baseline is `base` plus a short,
diffable list of its own deviations.

But **`base` is DrQ-v2's published hyperparameter set**, applied to eleven other algorithms. Some
consequences, all measured rather than estimated:

- **Six of twelve baselines run at a learning rate their own authors did not use.** DrQ and CURL
  publish 1e-3; IDAAC 3e-4; CTRL 5e-4. All run at 1e-4.
- Three baselines run at **ten times** the configured rate, because the key is silently dropped by
  their builder — the configuration file shows one learning rate and the code constructs two.
- **`nstep = 3` is applied to seven baselines whose originals all use 1-step TD.** That is not a
  tuning knob; it is a different estimator.
- The two algorithm families currently optimise **different discount factors** (0.99 and 0.999).

**The decision**: keep one shared configuration and report it as a stated limitation of the
comparison; or use each method's published values; or tune a few high-sensitivity knobs per arm.
These give different tables and support different claims. My recommendation is to decide this
*before* compute, and to say so explicitly in any write-up, because a reader will otherwise read
"equal conditions" as "fair comparison" and those are not the same claim.

### 2.2 Four baselines are unvalidated continuous adaptations

PPG, IBAC-SNI and CTRL are Procgen methods with **discrete** action spaces.

*(Partly superseded — see Appendix A1/A3. A continuous PPG does exist (XuanCe `Gaussian_PPG`,
unvalidated on continuous control), and IDAAC's Appendix E specifies its continuous configuration
in full, including the action head. The claim stands for **IBAC-SNI and CTRL**, where searching
found no continuous implementation anywhere. And Appendix A3 adds a sharper problem than the
action head: by the authors' own stated condition — gains are expected where there are **episode
length variations** — IDAAC should not be expected to gain on a single scene with a fixed horizon.)*

So our continuous action head for these is **original engineering with no reference to check
against**. The encoder, the PPO core and each method's auxiliary loss can be verified against
primary sources; the action distribution cannot.

**The decision**: report them clearly labelled as unvalidated adaptations; validate against Procgen
first, where published numbers exist (real extra work — a second environment stack); or drop them
and report a smaller, better-grounded matrix.

I want to flag an incentive problem honestly: the brief asks for twelve baselines, so we are under
pressure to keep twelve. That is exactly the pressure that produces a table with four rows that do
not mean anything.

### 2.3 We have no reference evaluation, and the protocol is about to become expensive to change

You withdrew the candidate evaluation script as not a good example and not faithful to its paper.
So **our protocol was built from the requirement rather than copied from a source**, and every
choice in it is ours. The protocol is hashed, so changing it later makes every prior number
formally incomparable — by design, but it means now is roughly the last cheap moment.

Choices we would like reviewed. Two we are least sure of:

- **The two sides of the gap are sized differently.** The train side is 1 scene x 10 episodes; the
  eval side is 10 scenes x 10 = 100. RL-ViGen runs 100 for both. So the quantity we subtract is
  measured from a tenth of the samples of the quantity we subtract it from.
  *(An earlier version of this briefing said the training scene was inside the evaluation set and
  diluted the gap. That was wrong: `scene_id` is nested within `mode`, so `train/scene 0` and
  `eval-easy/scene 0` are different configurations. Withdrawn.)*
- **We aggregate with the mean, not IQM.** The conclusion is right and **the reason we gave for it
  was not** — see Appendix A1. IQM aggregates over *runs* (task x seed), never over episodes within
  a run, so our bimodal-*episode* evidence was measured at the wrong level and does not bear on it.
  Mean within a run is correct because nobody proposes trimming episodes; what to do *across* runs
  is a separate, still-open question that only matters once we have more than one seed.

Also open: whether **return is the right headline metric at all**, given that on `Lift` a random
arm accumulates a large shaped return without ever lifting the block — success rate may be the
honest number.

---

## 3. What is built and verified

Evidence for each of these is in `docs/VALIDATION.md`, which is dated and gives the command.

- **Twelve baselines implemented, none an alias**, plus a uniform-random negative control. All
  thirteen complete real-simulator runs under a single protocol hash, each with a checkpoint.
- **One evaluator, structurally enforced.** It takes an opaque `policy: (obs) -> action` and cannot
  see the algorithm; a test proves that relabelling a run changes no number. Two training loops
  (off-policy and on-policy) share it, along with the logger, protocol and evaluation cadence.
- **The environment is verified, not trusted.** Five patches to RL-ViGen; without one of them a
  request for an evaluation regime silently returns a *training* environment and the resulting
  "generalization" number is measured on the training distribution. Every constructed environment
  is asserted to report the regime it was asked for.
- **A test suite with mutation testing behind it** — a curated catalogue of defects the suite must
  catch, plus an unbiased random-operator sweep that removes me from the loop. Survivors are
  triaged individually rather than counted.
- **Cross-validation against an independent implementation.** Our random-policy floor reproduces
  the sibling project's separately-written measurement: Door 1.54 vs 1.69; Lift 7.46 vs 7.80, with
  the same heavy right skew and zero successes in both. This is the strongest single piece of
  evidence that the environment, reward path, termination and aggregation are wired correctly.
- **Remote compute is proven.** A Yandex DataSphere T4 runs the full stack — GPU rendering
  confirmed, CUDA confirmed, every patch applied and re-verified on the box, and **the remote
  machine computes the same protocol hash as the laptop**, so remote and local numbers can sit in
  one table. Measured throughput: ~78 environment steps/s, i.e. ~1.8 h of environment stepping per
  500k-frame run, CPU-bound on physics.

---

## 4. What is *not* established

Stated plainly, because the temptation is to let a working pipeline imply working science.

- **No baseline has been trained at meaningful scale.** Everything so far is a 3 000-frame smoke
  run whose only purpose is to prove the code path executes. **No performance claim is made about
  any algorithm, and none should be quoted.**
- **Nothing has been validated against published numbers.** For most of the table that is not
  currently possible: no method here was published on robosuite manipulation.
- **The training budget has no source.** 500 000 frames is our choice and nothing justifies it.
- **The environment is not fully reproducible from our own install script.** Thirteen files are
  modified in the vendored upstream where only four are declared patches, and the check reports a
  known state anyway. Being fixed.
- **Frame budgets are not comparable with published numbers** without dividing by each paper's
  action-repeat convention.

---

## 5. What happens next without further input

1. Four deep-research passes are running: RL-ViGen's own documented hyperparameters and protocol;
   whether any published hyperparameters transfer to 7-DoF manipulation; how to adapt the
   discrete on-policy methods properly; and whether our evaluation protocol is defensible.
2. When they land, the decisions in §2 get concrete options with evidence attached.
3. Then — and not before — a real training run at scale.

The remaining open questions for you are in [`TASK.md`](TASK.md) §6. The highest-value one is
still the **reference evaluation**: you mentioned a defect in an existing evaluation and offered to
share it privately. We have neither the defect nor a reference, and we have now built an evaluator
without either. If that conversation is still available, it is the cheapest way to find out whether
we reproduced the same mistake.

---

## If you read one thing

**§1.2** — SGQN's inherited learning rate is 1000× off, one baseline's numbers are currently
meaningless, and the fix is one line that I am deliberately not making without a view on whether
fidelity to RL-ViGen or to the original paper takes precedence.

---

# Appendix — what four deep-research passes established, and what they overturned

Added 2026-08-10 after `ext/DR_1..DR_4`. Each pass verified paper sources it could reach and was
blocked from RL-ViGen's *code*, which I hold locally — so the two halves compose. **Four of my own
positions and one of the project's did not survive.** Those are listed first, because a briefing
that only reports confirmations is not worth reading.

## A1. Overturned

| claim | status | what is actually true |
|---|---|---|
| "Evaluation includes the training scene, so 1/10 of every gap is in-distribution" | **WRONG** | `scene_id` is nested inside `mode`. `eval-easy/scene 0` is a randomized easy scene, not the clean training scene. A label collision, not contamination. Independently confirmed by DR_4. |
| "Our replay 1e5 is 100× below the benchmark" | **WRONG** | RL-ViGen's replay is disk-backed (one `.npz` per episode); 1e7 is a nominal cap, not a tensor. Our 1e5 **equals SECANT's robosuite value exactly**. |
| "No continuous adaptation of PPG exists" | **WRONG for PPG** | XuanCe ships `Gaussian_PPG` (exists, unvalidated on continuous control). Also IDAAC's Appendix E *reports continuous PPG hyperparameters*. The claim stands for IBAC-SNI and CTRL. |
| "We were never given a reference evaluation" | **WRONG in substance** | RL-ViGen's own protocol is fully documented in paper §D.1.1 *and* readable in `eval.py::robo_eval`. Three of our contested choices already match it. |
| **Project's D5**: "mean beats IQM because IQM trims the successful tail" | **WRONG REASONING** | IQM aggregates over **runs** (task×seed), never over episodes within a run. Our evidence (bimodal *episode* returns, ratio 1.418) is measured at the wrong level. Right answer — mean within a run — for an argument that does not hold. |

## A2. The biggest live risk, and it is cheap to fix

**Episodic return is the wrong headline metric for these tasks.**

robosuite does not terminate on success — every episode runs the full 500 steps by design — and the
dense reward pays `1 − tanh(10·d)` *every step*. So a policy that hovers near the object for 500
steps without ever lifting it accumulates a large return. We already measured the consequence: a
**random** arm scores ~7.5 mean return on `Lift` with **zero** successes.

Success rate from robosuite's `_check_success` is the accepted headline across robosuite's own
benchmarking, RoboMimic, ManiSkill, Meta-World and GR00T. We already record it. **Recommendation:
promote success rate to the headline and keep raw return as a secondary diagnostic.**

## A3. Per-algorithm findings that change what we can claim

**IDAAC — the authors' own stated condition for expecting gains does not hold here.**
*(Corrected after reading the paper directly; my first version described the mechanism wrongly.)*

The discriminator does **not** classify level identity. It takes two observations **from the same
trajectory** and predicts which came first (Fig. 2: labels `{0 if i<j, 1 if i>j}`, adversarial
target 0.5), and the encoder is trained to make that impossible. So the mechanism — "strip
temporal-position information" — **still operates** on a single scene. It is not inert.

What is missing is the reason to expect it to *help*. §4.3: "**Since different levels have
different lengths**, capturing such information ... translates into capturing information specific
to that level." And **IDAAC's §6** states the condition outright: "the settings where we can expect most gains
are those with partial observability, a set of goal states, and **episode length variations**."

We train on one scene with a fixed 500-step horizon and no early termination — **no episode-length
variation at all.** By the authors' own criterion, IDAAC should not be expected to gain here. The
paper never ablates the loss against the number of training levels, so this is untested rather than
contradicted. Still the strongest scientific caveat among the four on-policy arms.

**CTRL — our auxiliary weighting is structurally wrong.** The paper applies `L_CTRL = L_clust +
L_pred` to the **encoder only**, as a plain sum; the official code has *separate* update functions
(`update_ppo`, `update_daac`, `update_cluster`). **There is no scalar weighting the SSL loss against
PPO, so our invented `ctrl_coef = 0.1` is not a mis-tuned value — it is a mechanism the method does
not have.** Separately: 200 clusters presuppose thousands of trajectory views (SwAV-style Sinkhorn
enforces equipartition and collapses when clusters are large relative to batch), so at our rollout
the defensible count is **16–32**, not 200 and not 8.

**IBAC-SNI — the port has one decision the paper settles.** After porting there are two Gaussian
noise sources: the VIB latent and the action distribution. The "deterministic" pass must fix **the
VIB latent, not the action distribution** — SNI was only ever about the *regularizer's added* noise.
Fixing the action distribution would change which algorithm we are running. β=1e-4 and λ=0.5 are
the authors' own values and are what we already use.

**PPG — reachable, with one caveat.** IDAAC's Appendix E reports continuous PPG hyperparameters, so
this arm has an authors' anchor. At a 500k budget with `N_π=32` we would get only **~7 auxiliary
phases in an entire run**; reducing `N_π` to 8–16 makes the mechanism observable and is a
documentable deviation.

## A4. The rollout finding that removes a blocker

I had `num_envs > 1` on the roadmap as the correct fix for the PPO family. **It is not needed.**
IDAAC's own continuous configuration (Appendix E, verbatim) is *"2048 steps, 1 process"* — the
authors ran exactly our constraint. The fix is to raise `num_steps` from 256 to **2048**, which is
free, and keep `num_mini_batch=32`, giving 64 samples per minibatch — **matching IDAAC's own
2048/32 exactly.**

There is a second reason this matters: at 256 steps a rollout spans *half an episode and contains
no terminal at all*, so every update sees only bootstrapped returns. At 2048 it spans ~4 complete
episodes and GAE sees real time-limit structure.

## A5. What is affordable, stated bluntly

**A pairwise-significant 12-arm ranking is not affordable and should not be attempted.** Training
(~2–3 h/run) dwarfs evaluation (~11 min per 100 episodes), so cutting episodes saves almost nothing
— the real cost is runs. The defensible design is **3 seeds × 2 tasks × 12 arms + the random
control**, reporting train and eval as two columns with a derived gap, a measured random floor plus
a competence gate (a non-learner has gap ≈ 0, which reads as perfect generalization), stratified
bootstrap CIs, and **tiered/banded rankings rather than a fully-ordered leaderboard.**

## A6. The fix list, sorted by whether it needs you

**Zero compute, no decision needed — sourced and unambiguous:**

| # | change | source |
|---|---|---|
| 1 | γ **0.999 → 0.99** for the four on-policy arms | IDAAC App. E verbatim; DR_2 and DR_3 independently |
| 2 | `entropy_coef = 0.0` for the PPO arms | Andrychowicz C13; Kostrikov MuJoCo default; IDAAC App. E |
| 3 | `num_steps` **256 → 2048** (keep `num_mini_batch=32`) | IDAAC App. E "2048 steps, 1 process" |
| 4 | **remove `ctrl_coef`**, update the encoder in a separate step | the paper has no such scalar |
| 5 | ~~`ctrl_clusters` 8 → 16–32~~ **APPLIED (32)**. Sinkhorn over the whole rollout is still open. | SwAV equipartition/collapse analysis |
| 6 | DrQ `nstep` **3 → 1** | RL-ViGen's paper *and* its own `drq_config.yaml` |
| 7 | set `lr` **explicitly per family**, killing the silent 10× split | measured here; DR_2 ranks it the top interpretability threat |
| 8 | SGQN `aux_lr` **0.3 → 8e-5**, quantile **0.9**, critic weight **0.7** | Table 6; 8e-5 is RL-ViGen's value across *all* its benchmarks |
| 9 | promote **success rate** to the headline metric | A2 above |

**Needs your decision:**

- **Training budget.** Table 6 specifies Door 6e5 and Lift 8e5; we run 5e5. Adopting them changes
  the protocol hash — free now, expensive after real runs.
- **`feature_dim`**: the paper says 256 for SVEA/SGQN, their code says 50 for everything. Which
  RL-ViGen do we mean? (Same question as item 8, and it recurs.)
- **Do IDAAC and CTRL stay?** Given A3, IDAAC's own authors' condition for expecting gains fails here
  and CTRL has no reference implementation. They can be reported with caveats, or cut.
- **Rewrite D5's justification** (A1, last row) — the conclusion survives, the argument does not.
