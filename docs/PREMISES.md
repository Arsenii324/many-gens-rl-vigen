# Premises: what a comparison on this benchmark actually requires

Companion to [`FAITHFULNESS.md`](FAITHFULNESS.md), which does the same job per algorithm.

`instruction.md` records *what was decided*. This document asks a different question: **starting
from "just run the algorithms and read the numbers", what is the smallest set of additional
premises that has to be true before a number means anything?** Each rung below is the minimal
increment over the one above, with the evidence that forces it.

The point is not to justify the design. It is to make the **degrees of freedom** visible — every
place where something was *set* rather than *derived*, so a reader can disagree with a specific
choice instead of with the whole edifice.

---

## 0. The headline number

> **Corrected 2026-08-24: this table measures the retired `rlgen/` port, not what runs.**
> `configs/vigen.yaml` is the port's launch config and **no clone run reads it** — the null became
> "the original repository, cloned, running its own `train.py`" on 2026-08-17, and each baseline now
> takes its knobs from its own upstream config. So the 44/129 split is a fact about a code path that
> no longer produces results, and the 75% figure below is not this project's current visibility.
> The *argument* the table supports — that most knobs are invisible from the launch config and live
> in constructor defaults — is unaffected and, if anything, understated by the clone, which has
> twelve launch configs instead of one. Recount before quoting a number here. Same failure as
> [C64](CONSTRUCTION.md#c64) and [C66](CONSTRUCTION.md#c66): a claim that outlived its referent
> because nothing ties it to a code path.

| | |
|---|---|
| Distinct declared knobs across all config sources | **173** |
| Knobs visible anywhere in `configs/vigen.yaml` (**retired port**) | **44** |
| **Invisible from the launch config** (**retired port**) | **129 (75%)** |

Four baselines — `drqv2`, `svea`, `sgqn`, `alda` — declare **zero** deviations from `base`. Their
method-specific settings are not "shared"; they are buried in constructor defaults (`SAC_DEFAULTS`,
`AldaConfig`'s 59 fields, RL-ViGen's own agent signatures). **P10's finding — SGQN's auxiliary
learning rate, 3,750x off the benchmark's own value — lived in exactly such a default**, and was
invisible for precisely that reason.

> **The 3,750× is the port's number and does not describe the clone** ([C64](CONSTRUCTION.md#c64)).
> It is `0.3 / 8e-5`, reached because the port bypassed hydra and hit `algos/sgqn.py`'s constructor
> default. The clone goes *through* hydra and reads `cfgs/sgqn_config.yaml:54` → `aux_lr: 1e-4`,
> which is **1.25×** off the paper's `8e-5`, not 3,750×. The example is still the right example —
> a value hiding in a constructor default was invisible and did bite — but the magnitude belongs to
> a code path that has been retired, and the live question is now the much smaller shipped-vs-paper
> gap, which is undecided.

Reproduce: `python -c` over `Protocol`, `TrainConfig`, `SAC_DEFAULTS`, `idaac.config.Config`,
`alda.config.AldaConfig`.

---

## 1. The ladder

### P0 — the null premise (false)

> *One command runs an algorithm on the environment, and the number it prints is the result.*

Every rung below is a way this is false. They are ordered so each is the smallest step from the
last, not by importance.

### P1 — the environment must be **told** which visual regime to build, and upstream will not be told

`make_env` reads `mode` only from a hydra config file. A caller asking for `eval-easy` silently
receives a `train` env and measures generalization on the training distribution — a plausible
number, not a crash. Requires patch **P1**; and because the wrapper chain does not forward
attribute lookups, patch **P3** to hoist the resolved regime out so the request can be *verified*
rather than trusted.

> **True premise**: a launch is at minimum `(algorithm, task, mode, scene_id, seed)`, and `mode`
> must be checked on the constructed object, not assumed from the argument.

### P2 — the environment does not run at all in one of the regimes it advertises

`VGBWrapper.__init__` loads a background video for every mode; the shipped asset pack has no
`train` directory, so `mode='train'` dies in `np.empty((-1, H, W, 3))`. Requires patch **P2**.
Patch **P4** is the same class of problem for the overlay path on any non-CUDA machine.

> **True premise**: "nothing done" is not available. **Five** patches stand between upstream and a
> tree that runs (P5 casts DrQ's `log_alpha` to float32; MPS does not support float64 and DrQ dies
> at construction without it), and `setup/apply_patches.py --check` must pass before any number is
> admissible.

### P3 — there is no single "the environment"

Ours, unpatched upstream, and the sibling project's port differ. The environment is itself a
parameter set: `image_size`, `frame_stack`, `action_repeat`, `horizon`, `robot`, `controller`,
`reward_shaping`, plus which upstream commit. `Protocol` names 31 such fields precisely so this
is arguable rather than implicit.

**Both provenance defects here are now fixed** (2026-08-10; they read as "known live defect" in
earlier revisions of this document). `Protocol.env_patches` named three patches while four were
applied and nothing ever wrote it, despite its comment — it is now correct and **pinned by a test**
to `apply_patches.py`. And `--check` verified only that our own patches were present while thirteen
files were modified; it now diffs the **whole** tree against the pinned commit, in both directions.
Chasing that second fix found four hand-edits that no script reproduced, one of them load-bearing
(`algos/drq.py`, now patch P5) — so a fresh `install.sh` really did produce a different tree, and
now does not. `ALLOWED_MODIFIED` is down to two entries, neither of them source.

> **True premise**: the environment is a decision with ~31 parameters and a patch set, and that
> patch set is now certifiable in both directions — nothing undeclared present, nothing declared
> absent. The hash moved twice as a result (`b5ba34d3…` → `07923ae8…` → `c0d7bc7c…`), which is the
> mechanism working: a changed environment must not silently pool with an older one.

### P4 — a number requires an evaluation protocol that training does not imply

Which scenes, how many episodes each, deterministic or stochastic policy, which statistic, whether
the training scene is included. None follows from "run the algorithm".

> **Status 2026-08-25: a protocol now exists in code, and it was never decided — it was built.**
> `scripts/eval_across_scenes.py` fixes most of the choices this premise says do not follow from
> training: **20 episodes × 10 scenes × 2 regimes**, deterministic CPU inference, return as the
> statistic ([C33](CONSTRUCTION.md#c33)), success latched across the episode
> ([C62](CONSTRUCTION.md#c62)), object placement and torch kernels pinned
> ([C69](CONSTRUCTION.md#c69), [C70](CONSTRUCTION.md#c70)). Those are answers to this premise, and
> they are good ones.
>
> **One of them is not settled and is the live decision.** The report pools over the scenes that
> clear the random floor *and* solve ≥25% of episodes, dropping the rest
> ([C55](CONSTRUCTION.md#c55)) — and prints, in its own output, *"pooled over the N usable scenes
> only — **NOT RL-ViGen's protocol**, which averages all ten. Dropping scenes changes the
> estimand."* RL-ViGen averages ten unconditionally; we average a **data-dependent subset**.
>
> Both are defensible. They are **different quantities**, and the choice decides whether our number
> is comparable to a published one ([C48](CONSTRUCTION.md#c48)) or deliberately incomparable. It
> also decides a subtler thing: whether a guard may drop a scene from a pooled mean at all, or
> whether an unusable scene should refuse the **whole cell** rather than be silently excluded from
> it.
>
> Recorded as the owner's decision in [C43](CONSTRUCTION.md#c43)/[C45](CONSTRUCTION.md#c45) and in
> [`STAGES.md`](STAGES.md)'s blocker table, where it is marked **upstream of**
> [C64](CONSTRUCTION.md#c64) and [C68](CONSTRUCTION.md#c68): those decide what a run should be,
> this decides what its number means.

**Correction, 2026-08-10.** This section previously claimed that because `train_scene_ids=(0,)` and
`eval_scene_ids=(0..9)` share the id 0, one tenth of every generalization number was
in-distribution. **That was wrong.** `scene_id` is nested inside `mode` — RL-ViGen resolves a scene
as `get_custom_reset_config(task, mode, scene_id)` — so `mode=train, scene 0` and
`mode=eval-easy, scene 0` are different configurations, and
`test_eval_modes_actually_look_different_from_train` asserts the modes differ in pixels. No
evaluation scene is the training condition. `Protocol.eval_includes_train_scenes=True` is true of
the *id lists* and misleading about what it implies; it should be renamed or set False.

The real asymmetry is that the two sides of the gap are sized differently: the train side is
1 scene × 10 episodes = **10**, the eval side is 10 scenes × 10 = **100**. RL-ViGen's own
`eval.py::robo_eval` runs 100 for both (at train level it simply does not switch scenes). So the
term we subtract is estimated from a tenth of the samples of the term we subtract it from.

**Two of our protocol choices are independently corroborated** by the prior project's own bug
register — `DISCREPANCY_MATRIX.md`, copied to `ext/` (gitignored, so a fresh clone will not have
it; it originated outside this repo). It is useful precisely because it was written from failures
rather than from theory:

- **B31, the denominator problem.** Training happens on `train`/scene 0 only, and in `train` mode
  scenes 1–9 are *still unseen*. Computing the gap's denominator as a 10-scene `train` average
  divides two near-zero numbers and produced a spurious "93.9% retention" where the honest figure
  was 0.9%. Our `train_scene_ids=(0,)` is the correct denominator, and our D6 rule (absolute
  difference, never a ratio) independently avoids the same trap.
- **Truncation bootstrapping.** `Door`/`Lift` never terminate early, so every episode ends by time
  limit. Treating truncation as termination zeroes the Q-target at step 500 on every episode and
  tells the critic the world ends there. Our `time_limit_handling: "truncate_with_bootstrap"` does
  this correctly.

  **Corrected 2026-08-15, Stage 3 (`porting-directive.md` §3).** This bullet previously compared
  our fix only against "the earlier single-file script" (the sibling project's draft). Reading
  RL-ViGen-upstream's own environment/replay seam directly (not the algorithm files, which we
  import unmodified) shows the SAME bug in the reference itself, not only in some other draft:
  `RL-ViGen-upstream/wrappers/robo_wrapper.py::Gym2DMC.step` (`:35-40`) sets `discount = 0.0`
  whenever the underlying `done` flag is true, unconditionally — no branch anywhere distinguishing
  true termination from a time-limit truncation. Since Door/Lift only ever end by time limit, this
  fires at EVERY episode's end. That `discount` flows straight into
  `RL-ViGen-upstream/replay_buffer.py::ReplayBuffer._sample`'s own n-step accumulation
  (`discount *= episode['discount'][idx+i] * self._discount`, `:159`), so upstream's own n-step
  return construction zeroes the bootstrap at every Door/Lift episode boundary. `wrappers/dmc.py`'s
  `ExtendedTimeStepWrapper` (`:46-54`) just accumulates whatever `discount` the underlying env
  reports — it is not itself the source of the zeroing, `Gym2DMC.step` is.

  This means `time_limit_handling: "truncate_with_bootstrap"` is not a repair of a defect specific
  to a sibling project's script — it is a deliberate, first-class DEVIATION from what
  RL-ViGen-upstream's own shipped code does, and from what any published numbers using that exact
  commit would have been produced under. The reasoning for making it (time-limit ≠ termination) is
  unchanged and still correct; what changes is the honest framing: this is `porting-directive.md`
  §4 territory (a documented adaptation with a stated reason), not merely "a bug we didn't
  reproduce." `rlgen/replay.py::FrameReplay.sample` already carries this reasoning in its own
  comment; this correction is to the CLAIM here about what it diverges from, not to any code.

**One choice it puts in doubt, and we have not handled it.** B33 records that retention *oscillates
violently across training* — one run moving `125% → 326% → 19% → 51% → 45% → 90% → 7%` across
checkpoints. Our `checkpoint_selection: "final"` therefore samples one point of a wildly
non-monotone curve. Reporting a single final-checkpoint gap per arm may be measuring checkpoint
noise rather than method quality. This is a live, unresolved protocol question and it belongs
next to the mean-vs-IQM one.

> **True premise**: the protocol is a separate object from the algorithm, it must be identical
> across arms to be comparable, and it is hashed so that two runs either pool or visibly do not.
> But identity across arms does not make any single arm's number stable across *checkpoints*, and
> nothing in our design currently addresses that.

### P5 — the budget's unit is ambiguous across every source paper

DrQ-v2 uses `action_repeat=2` uniformly and says it counts "environment steps, rather than agent
steps". DrQ v1 and CURL use per-task repeats of 2/4/8. We use **1**, deliberately (D4).

> **True premise**: our 500k frames are 500k policy decisions; a paper's 500k "steps" are 500k/`k`
> decisions. **No budget here is directly comparable to a published number without dividing by
> that paper's repeat.**

### P6 — "just use the published hyperparameters" is not available

Three independent reasons, each sufficient:

1. **None of these methods was published on this benchmark.** RAD, SVEA, SODA, SGQN, DrQ, DrQ-v2,
   CURL and ALDA are DMControl/DMControl-GB methods; PPG, IDAAC, IBAC-SNI and CTRL are Procgen
   methods. Robosuite 7-DoF manipulation is a third setting. Published values do not transfer;
   they have to be *mapped*, and mapping is a choice.
2. **Paper and official code disagree, for several of them.** CURL differs from its own repo on
   five hyperparameters (batch 512 vs 32/128, encoder tau 0.05 vs 0.005, alpha lr 1e-4 vs 1e-3,
   critic tau 0.01 vs 0.005, init temperature 0.1 vs 0.01). SODA's paper says aux lr 3e-4, its repo
   ships 1e-3. RAD's batch size disagrees three ways (paper 512, argparse 32, shipped script 128).
   So **"faithful" is ambiguous until you say faithful *to what*.**
3. **Some values do not exist for this action space.** PPG/IDAAC/IBAC-SNI are discrete-action
   methods; a 7-D Gaussian head has no published entropy coefficient, and Procgen's 0.01 is wrong
   for it because entropy sums over dimensions and is unbounded.

> **True premise**: every hyperparameter is either mapped from a source (and the mapping is a
> claim), or chosen by us (and must be marked as such).

### P7 — a shared base is not a neutral base

Our rule is: one `base` block, and each entry is `base` plus only its own deltas. That mechanism is
good — deviations are diffable and equality is the default. But **`base` is DrQ-v2's published
hyperparameter set**, and applying one arm's optimum to eleven others is the classic way to
handicap every arm but one:

| what | canonical for | applied to |
|---|---|---|
| `lr: 1e-4` | DrQ-v2 | all 12 — but DrQ and CURL publish **1e-3**, IDAAC 3e-4, CTRL 5e-4 |
| `nstep: 3` | DrQ-v2 | all off-policy — RAD/SVEA/SODA/SGQN/DrQ/ALDA are all **1-step TD** |
| `replay_capacity: 100000` | DrQ **v1** | all off-policy — DrQ-v2 uses **1e6** |
| `stddev_schedule: linear(1.0,0.1,100000)` | RL-ViGen **Door easy tier**, selected by `Door.yaml` | our budget is 600k |

The last one is subtle and worth spelling out: active Door composition selects the easy-tier
schedule, so exploration noise finishes annealing at about **16.7%** of the 600k budget and the
agent trains under low noise for the remainder. The medium-tier 500k string describes a historical
pre-fix run, not the production composition.

> **True premise**: R4 ("equal training conditions") is satisfiable in the letter and violated in
> fact. Equal *values* across arms is not equal *treatment* when the values are one arm's optimum.
> The honest options are (a) per-arm published values, (b) a tuned-per-arm budget, or (c) keep the
> shared base and **report it as a limitation of the comparison**. We currently do (c) implicitly;
> it should be explicit.

### P8 — the config does not show what the code reads

`base` presents one learning rate. Measured by constructing every baseline and reading its
optimizers:

| baselines | actual lr | mechanism |
|---|---|---|
| drqv2, svea, sgqn, curl, drq | 1e-4 | builder reads `hyper.get("lr", 1e-4)` |
| rad, soda, alda | **1e-3** | `lr` is not a key in `SAC_DEFAULTS`/`AldaConfig` → **silently dropped** |
| ctrl, idaac, ppg, ibac_sni | 1e-4 | `hasattr(Config,"lr")` → overrides IDAAC's 3e-4 |

The same mechanism silently discards `feature_dim`, `hidden_dim`, `critic_target_tau`,
`num_expl_steps`, `stddev_schedule`, `stddev_clip` for the PPO family, and `log_std_bounds` /
`hidden_depth` are passed to `drq` through a `defaults` dict rather than the config that also
lists them.

> **True premise**: a config key is only a decision if some code reads it. Ours are filtered by
> `if k in SAC_DEFAULTS` / `if hasattr(cfg, k)` — the same silent-no-op family as `RIGOR.md` §6.8.
> **Any claim about "the hyperparameters used" must be made by inspecting constructed objects, not
> by reading the yaml.**

### P9 — some parameters are infrastructure, not science

`trainer_onpolicy.py` runs `num_envs=1` because RL-ViGen's robosuite calls `GlobalHydra.clear()` on
every construction and needs its GL backend chosen before mujoco imports, so envs cannot be built
concurrently in one interpreter. Consequence, arithmetically:

`num_steps 256 x num_envs 1 = 256` samples per update; `num_mini_batch` is IDAAC's default **32**
and nothing overrides it; `storage.feed_forward_generator` computes `mb = 256 // 32 = ` **8
samples per minibatch**. IDAAC's own continuous-control column specifies a `1 x 2048` rollout with
32 minibatches, i.e. **64**.

> **True premise**: a machine constraint has silently become an algorithmic one. The PPO family is
> not running a small version of the published method; at 8-sample minibatches it is running a
> different one.

### P10 — some numbers are inherited defects, not decisions

SGQN's auxiliary optimizer runs at **`aux_lr = 0.3`**. Canonical SGQN uses **3e-4** — a factor of
**1000**, consistent with a decimal slip. The value is **upstream RL-ViGen's**, in a constructor
default our config never mentions (`sgqn` declares zero deviations). Nothing crashes; the
attribution head simply cannot learn.

> **True premise**: inheriting an implementation inherits its bugs, and a config that shows only
> *deviations* cannot show a defect that lives in the base it deviates from.

---

## 2. The premises that are actually true

Collected, as the answer to "what would have to hold":

1. A launch is `(algorithm, task, mode, scene, seed)` **plus** a verified patch set, **plus** a
   ~31-field protocol, **plus** ~9 trainer settings, **plus** 24–59 algorithm settings most of
   which are never named at the launch site.
2. The environment is a decision, not a given, and its provenance must be checkable. Ours
   currently is not — see P3's correction note above, and `docs/STATUS-AGAINST-THE-GOAL.md` §2a
   for how the two provenance defects were closed.
3. Evaluation is a separate object from training and must be identical across arms; ours is, and
   that is enforced structurally rather than by review.
4. Frame budgets are comparable within this project and **not** with any published number.
5. No hyperparameter here is "the published one" — each is mapped, chosen, or inherited, and which
   of the three is the fact worth recording.
6. Equal shared values across arms is a *defensible* protocol choice and a *real* bias; it must be
   reported as a limitation rather than presented as fairness.
7. What the code reads is an empirical question about constructed objects.
8. `num_envs=1` is a hardware fact that currently changes the PPO family's algorithm.
9. At least one number in the stack (SGQN `aux_lr`) is a defect inherited from upstream.

---

## 3. What this changes, in priority order

Highest first. Each is a decision for the owner, not something I should change unilaterally.

| # | Item | Why it ranks here |
|---|---|---|
| **1** | **SGQN `aux_lr` 0.3 → 3e-4** | 1000x off canonical; every SGQN number so far is uninterpretable. Cheapest possible fix, largest correctness gain. |
| **2** | ~~**PPO-family minibatch (8 samples)**~~ **APPLIED** | `num_steps` 256 → **2048**, giving 64 samples/minibatch. `num_envs > 1` turned out **not to be needed**: IDAAC's own continuous configuration is *"2048 steps, 1 process"*, so a single environment is the authors' setting rather than our limitation. A rollout now spans ~4 episodes instead of half of one, so GAE finally sees terminal structure. |
| **3** | **`Protocol.env_patches` + undeclared upstream edits** | The provenance chain is broken at two points and `--check` passes anyway. Cheap to fix, and it is what makes every other number auditable. |
| **4** | **`nstep: 3` on 1-step-TD methods** | Changes the estimator for 7 of 12 arms. Either set per-family or declare it as a deliberate protocol constant. |
| **5** | **`gamma` 0.999 (on-policy) vs `discount` 0.99 (off-policy)** | The two families currently optimise different objectives. The sibling annotated 0.99 as correct here and "NOT Procgen's 0.999". |
| **6** | **The shared-base bias** | Not a bug; a limitation that must appear in the write-up next to the table. |
| **7** | **`stddev_schedule` vs budget** | Only matters once real runs happen; harmless in smoke. |
| **8** | **Gap arms are sized 10 vs 100 episodes** | The term we subtract has a tenth of the samples of the term we subtract it from. RL-ViGen runs 100 for both. (The former entry here claimed a 1/10 in-distribution dilution; that premise was withdrawn — see P4.) |

---

## 4. Open questions that need research, not a decision

Stated rather than resolved, per the standing rule that an honest gap beats a plausible answer.

- **Q1 — Is any published hyperparameter set valid for robosuite manipulation at all?** RAD was
  never evaluated on manipulation. SVEA and SODA were, but on unreleased environments with a 2-D
  action space, not 7-DoF. Only SGQN released manipulation code (xArm7). So for most of the table
  the "canonical" values are DMControl locomotion values being asked to do a different job.
- **Q2 — What budget?** `total_frames: 500000` has no source in any file. It is `[OURS]`, and
  nothing says why.
- **Q3 — Is 8 clusters defensible for CTRL, where the paper uses 200?** **Partially answered,
  2026-08-13**: the "T=2 sampled timesteps, not a window" guess in this line was wrong — checked
  directly against `bmazoure/ctrl_public`'s own source (`algo.py::extract_windows_vectorized`,
  `train_ppo.py:54`'s `cluster_len` flag), the reference builds *sliding* (fully overlapping)
  windows of length 10 by default, not sampled timestep pairs, and has no episode-boundary guard
  either (this project's own `_embed_windows` builds disjoint, non-overlapping windows instead —
  the real gap is window construction density, not the mechanism guessed here). `ctrl_coef` — no
  such coefficient in the paper, encoder and policy are separate update targets — remains correct
  and unresolved as a decision. Full finding, plus the still-open `ctrl_window: 8` vs. reference
  `cluster_len: 10` numeric question: git tag `pre-lean-target-checkpoint-transition` (or `-main`),
  path `docs/PPO_FAMILY_ARCHITECTURE.md` as it existed there — removed from the working tree since
  (see `docs/COMPARABILITY_CONTRACT.md` §7 for why), citations still valid.
- **Q4 — Which SVEA?** Canonical SVEA's strong augmentation is random **convolution**; RL-ViGen's
  uses random **overlay** (SODA's). That is why our SVEA needs Places365 at all — canonical SVEA
  needs no external dataset. It also means `svea` and `soda` now share an augmentation source
  rather than contrasting two.
- **Q5 — Faithful to paper or to repo?** For CURL, SODA and RAD these differ materially. A single
  answer should be chosen and stated once, not per-algorithm by accident.

**Resolved by this audit** (was Q: "which ALDA"): the brief cites arXiv **2001.01046**, which is
*Adversarial-Learned Loss for Domain Adaptation* (AAAI 2020) — an **image-classification** paper
with no agents or environments. Our port implements arXiv **2410.07441**, *Associative Latent
DisentAnglement* (ICML 2025), which is a genuine visual-RL generalization method. Unrelated papers
sharing an acronym. **The port is right; the brief's citation is an error to raise with DZ.**
