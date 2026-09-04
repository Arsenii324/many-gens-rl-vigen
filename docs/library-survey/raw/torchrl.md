# RAW — TorchRL (pytorch/rl), depth sweep

**Provenance.** Subagent report, received 2026-08-17. Run blind (no access to
`docs/AUDIT-2026-08-17.html` or this `docs/` tree). Basis stated in the report itself: shallow
clone of `pytorch/rl` at commit `82a259373f1b` (2026-08-16, post-0.13.3 main) plus
`pytorch/tensordict` main, GitHub issues/PRs via authenticated `gh`, and arXiv:2306.00577.

**Preserved verbatim and unmerged**, per an explicit instruction to record the original
information before any synthesis. Only alteration: transport HTML entities un-escaped
(`&gt;` → `>`, `&amp;` → `&`). Nothing cut, no claim or locator changed.

**Why this one matters most of the set.** It is the only report that went looking for *evidence
about the consequences of sharing* rather than for feature coverage, and it found roughly twenty
cited instances in which a shared component silently changed an algorithm's numbers in the
field's flagship modular library — including a shared value estimator that treated every
truncation as a termination for every GAE/TD(λ) consumer (issue #1662), and a shared trainer
whose PPO gamma/lambda were wrong while the duplicated script's were right (PR #3679). That is
the empirical case for this project's stance, made from the other side.

**Not independently re-verified by me.** Its own "Things I could not verify" section is its own
admission. Two claims are flagged there as UNVERIFIED (a public W&B URL; whether TorchRL is
tracked by Open RL Benchmark) and should not be repeated as fact.

---

# TorchRL — library sweep

**Basis for every claim below:** shallow clone of `pytorch/rl` at commit `82a259373f1b` (2026-08-16, post-0.13.3 main) and `pytorch/tensordict` main, both under `/tmp/torchrl_sweep/`; GitHub issues/PRs via authenticated `gh`; arXiv:2306.00577 via two independent HTML renderings. Paths below are repo-relative to `/tmp/torchrl_sweep/rl/` unless absolute.

---

## 1. Coverage of the twelve

**Zero of the twelve exist in TorchRL.** This is a confident, exhaustive absence, not a failed search.

Method: case-insensitive grep across all `*.py`/`*.md`/`*.rst`/`*.yaml` for each name, plus the complete inventory of loss modules and SOTA scripts.

| Baseline | In TorchRL? | Evidence |
|---|---|---|
| DrQ | **No** | 0 hits. Requested as issue [#32](https://github.com/pytorch/rl/issues/32) — see below |
| DrQ-v2 | **No** | 0 hits; discussed in #32, never written |
| SAC-from-pixels | **No** | `sota-implementations/sac/utils.py:89` passes `from_pixels=cfg.logger.video` — pixels are rendered *for video logging only*, never as the training observation |
| CURL | **No** | The 3 `curl` hits are the HTTP tool in `torchrl/envs/llm/transforms/tools.py` |
| RAD | **No** | All hits are substrings of `grad`/`gradient` |
| SVEA / SGQN / SODA | **No** | 0 hits each, any case |
| PPG | **No** | 0 hits for `PPG` or `phasic` |
| IDAAC / DAAC | **No** | 0 hits |
| IBAC-SNI | **No** | 0 hits; `SNI` matches only `snippet` |
| CTRL | **No** | `ctrl_` hits are `ctrl_c` etc. |
| ALDA | **No** | Hits are the substring in `IFEvalDataset` (`torchrl/envs/llm/datasets/ifeval.py`) |

**Complete loss-module inventory** (`grep '^class .*Loss' torchrl/objectives/*.py torchrl/objectives/multiagent/*.py`): A2C, ACT, BC, ClipPPO, CQL, CrossQ, DDPG, DiffusionBC, DiscreteCQL, DiscreteIQL, DiscreteSAC, DistributionalDQN, DQN, Dreamer{Actor,Model,Value}, DreamerV3{Actor,Model,Value}, DT, GAIL, IPPO, IQL, KLPENPPO, MAPPO, OnlineDT, PPO, QMixer, REDQ, Reinforce, RND, SAC, TD3, TD3BC, TQC, WorldModel. **28 SOTA scripts** under `sota-implementations/`. No visual-generalization algorithm in either list.

**The load-bearing citation — issue [#32](https://github.com/pytorch/rl/issues/32), "[Feature Request] Image Augmentation Is All You Need benchmark"** (that is the DrQ paper's title). Opened **2022-03-07**, labels `enhancement`/`new algo`, **still OPEN** as of 2026-02-22. Three volunteers over four years (`yemaedahrav` 2023-11, `PaulBeuran` 2024-10, `alektebel` 2026-02); a commenter proposed doing DrQ-v2 instead and linked `facebookresearch/drqv2`; nothing shipped. Maintainer `vmoens` identified the blocker: *"the main technical difficulty is to do transforms in a consistent manner (eg, have an action mapping operator that follows the image/state transform etc)."*

His statement of what a SOTA script is *for* is worth having, because it is the opposite of your null:

> "the primary goal is that if anyone wants to build on top of this work a new research paper or an application … it should be doable. The secondary goals are: provide the set of primitives that are needed for this … provide a script that reproduces some of the paper's result **to showcase how those primitives should be used**. This hierarchy of values is important … **we don't want to write a new benchmark for the sake of the script, we want the benchmark to show how to use what that paper proposes using torchrl.**"

**Corroborating structural absence:** TorchRL has **no random image augmentation at all**. Verified inventory of image transforms:
- `torchrl/envs/transforms/_observation.py:166` `Resize`
- `torchrl/envs/transforms/_observation.py:274` `Crop(w, h, top=0, left=0)` — *deterministic* offsets
- `torchrl/envs/transforms/_observation.py:341` `CenterCrop`
- `torchrl/envs/transforms/_misc.py:277` `RandomCropTensorDict` — **not** an image transform; it is a *temporal* sub-trajectory sampler ("Gathers a sub-sequence of a defined length along the last dimension"), and its docstring says "it cannot be used as an environment transform"

No random-shift, no random-offset crop, no random conv, no color jitter, no pad-and-crop. The mechanism shared by DrQ, DrQ-v2, RAD, SVEA and SGQN does not exist in the library.

---

## 2. The fidelity question

Separate the three things, because they diverge sharply here.

### 2.1 What they publish numbers for — the paper, and only the paper

The published reproduced results are **Table 1 and Table 2 of arXiv:2306.00577**, not the repo, not the docs site, not W&B.

**Table 1 caption, verbatim:** *"Experimental training of multiple on-policy and off-policy algorithms. We run each training 5 times with different seeds and report the mean final reward and std."*

| Algorithm | HalfCheetah (1M) | Pong | Breakout |
|---|---|---|---|
| A2C | 836 ± 964 | 20.57 ± 0.65 | 375.65 ± 47.34 |
| PPO | 2770 ± 821 | 20.52 ± 0.58 | 335.71 ± 46.72 |
| IMPALA | — | 20.54 ± 0.18 | 525.57 ± 105.47 |
| DDPG | 10433 ± 357 | — | — |
| TD3 | 10285 ± 837 | — | — |
| SAC | 11077 ± 323 | — | — |

Table 2 (offline, HalfCheetah): DT 4916 ± 30, oDT 4968 ± 58, IQL 4864 ± 147.

### 2.2 How fidelity is established — against **paper numbers**, never against the authors' code

The methodology sentence, verbatim:

> "In each case, we closely follow the original implementations (including network architectures, hyperparameters and number of training steps) and **obtain results that match those of their original papers**."

That is the whole of it. There is no code-level diff against any reference implementation, and — verified — **no golden numbers from any original author's implementation exist anywhere in the repository**. A repo-wide grep for `stable.?baselines|cleanrl|spinning ?up|original implementation|reference implementation` across the ~25,275-line `test/objectives/` suite returns **no test comparisons**; the only hits are an SB3 `VecEnv` *wrapper* in `torchrl/envs/libs/gym.py`, a link list in `knowledge_base/RESOURCES.md`, one prose line in `knowledge_base/DEBUGGING_RL.md:67`, and a code comment in `torchrl/objectives/dreamer.py:357`.

**A hard contradiction I verified independently, and which I think is the single most useful fidelity finding for you.** The paper claims 5 seeds for A2C, PPO and IMPALA. The shipped scripts for those algorithms **have no seed knob at all**:

```
grep -c seed sota-implementations/ppo/config_mujoco.yaml      → 0
grep -c seed sota-implementations/ppo/config_atari.yaml       → 0
grep -c seed sota-implementations/a2c/config_mujoco.yaml      → 0
grep -c seed sota-implementations/a2c/config_atari.yaml       → 0
grep -c seed sota-implementations/impala/config_single_node.yaml → 0
grep -c seed sota-implementations/dqn/config_atari.yaml       → 0
```

`ppo_mujoco.py`, `ppo_atari.py`, `impala_single_node.py`, `dqn_atari.py` contain **zero** `manual_seed`/`set_seed` calls. `a2c_mujoco.py:113` and `a2c_atari.py:117` seed only the *test* env (`test_env.set_seed(0)`); training is unseeded. By contrast the off-policy family is properly seeded — `sac.py:66`, `td3.py:65`, `ddpg.py:68`, `crossq.py:65` all call `torch.manual_seed(cfg.env.seed)` with `seed: 42` in their configs, and `sac/utils.py:85,114,144,180` seeds envs and collectors. **So the released code for three of the six algorithms in Table 1 cannot produce the seeded runs the paper describes.**

### 2.3 Where the reproduced curves live — nowhere public

- **`sota-implementations/README.md`: the entire Results section is commented out.** The HalfCheetah SAC/REDQ charts, the `media/halfcheetah_chart.png` and `cheetah_chart.png` references, and the reproduce-a-single-run commands are all wrapped in `[//]: # (…)` markdown comments. They are in the file and deliberately not rendered.
- **`sota-check/`** is a pre-release Slurm sweep. `sota-check/README.md`: *"This script is to be executed before every release to assess the performance of the various algorithms … The name of the project will include the specific commit of torchrl used (e.g. `torchrl-examples-check-<commit>`)."* Each script (e.g. `sota-check/run_sac.sh`) writes `${group_name}_${SLURM_JOB_ID}=success|error` to `report.log` — **exit status only, no reward**. `submitit-release-check.sh --n_runs` defaults to **1**.
- **UNVERIFIED:** I could not find any publicly viewable `torchrl-example-check-*` W&B project. Searches for `"torchrl-example-check"`, `wandb.ai` + torchrl returned only BenchMARL's (separate project's) public W&B. The projects are almost certainly internal. I have no URL to give you.
- **UNVERIFIED:** whether TorchRL is one of the libraries tracked by Open RL Benchmark (arXiv:2402.03046). The abstract says only "a wide range of RL libraries" without naming them; I could not extract the library list from the paper.
- No results/benchmark page exists under `docs/source/reference/`. The README's Benchmarks badge points to `https://pytorch.github.io/rl/dev/bench/`, which is the **pytest-benchmark speed** dashboard (see §3.3).

### 2.4 Do they document deviations the way CleanRL does? — Essentially no

CleanRL's `docs/rl-algorithms/*.md` per-algorithm "implementation details that matter" has **no TorchRL equivalent**. Verified README inventory of `sota-implementations/`:

- **Have a README (13):** a2c, bandits, dqn, dreamer, dreamer_v3, expert-iteration, grpo, impala, multiagent, multiagent_trainer, ppo, redq, vla_grpo
- **No README (25):** **sac, td3, ddpg, cql, iql, crossq, tqc**, discrete_sac, gail, rnd, pilco, td3_bc, diffusion_bc, decision_transformer, offline_to_online, ppo-async, and all nine `*_trainer` variants

**The complete set of explicit deviation statements I found, quoted verbatim:**

1. `sota-implementations/ppo/README.md`, opening paragraph:
   > "We follow the original paper *Proximal Policy Optimization Algorithms* by Schulman et al. (2017) to implement the PPO algorithm **but introduce the improvement of computing the Generalised Advantage Estimator (GAE) at every epoch.**"

2. The paper's matching footnote: *"Our implementations compute the Generalized Advantage Estimator (GAE) at every epoch."*

3. Top-level `README.md:507-509` — the global disclaimer:
   > "The implementations are meant to be **readable starting points, not black-box benchmarks**. They show how TorchRL components fit together and can be copied into research code when a full trainer abstraction is not the right fit."

That is all. Everything else is described as faithful. **Three concrete deviations I found that are NOT documented anywhere:**

- **PPO-MuJoCo uses a tanh-squashed Gaussian.** `sota-implementations/ppo/utils_mujoco.py:293` `distribution_class = TanhNormal`, with `low`/`high` from the action spec and `tanh_loc: False`. Schulman's PPO, SB3 and CleanRL all use an **unsquashed** Normal with environment-side clipping. This changes the policy class, the entropy, and the importance ratio. The config's `exp_name` is literally `Mujoco_Schulman17` (`config_mujoco.yaml:21`).
- **Non-standard orthogonal init gains.** `utils_mujoco.py:308-311` applies `orthogonal_(w, 1.0)` to **every** policy Linear; `utils_mujoco.py:346-349` applies `orthogonal_(w, 0.01)` to **every** value Linear (same in `a2c/utils_mujoco.py:78,116`). The reference recipe is gain √2 on hidden layers, 0.01 on the *policy output only*, 1.0 on the *value output*. Applying 0.01 to every critic layer makes the critic near-degenerate at init. And `ppo/utils_atari.py` applies **no** orthogonal init at all.
- **PPO and A2C disagree with each other on the std floor**: `ppo/utils_mujoco.py:317-319` passes `scale_lb=1e-8`; `a2c/utils_mujoco.py:100-102` uses the default `1e-4`.

The nearest thing to a deviation document is `docs/source/reference/dreamer_v3.rst:32-72`, a **Nomenclature** table mapping Dreamer-paper terms to TorchRL keys ("Belief"/`h_t` → `"belief"` key, "Slow critic"/"EMA critic", etc.). Useful as a model for vocabulary alignment, but it documents *naming*, not *divergence*.

---

## 3. The join question

### 3.1 The actual shared surface

TorchRL states the philosophy explicitly in `README.md:34-36`:

> "Environments, policies, replay buffers, objectives, and collectors should be **independent modules that can be swapped without rewriting the rest of the stack**."

Concretely, here is everything `sota-implementations/sac/{sac.py,utils.py}` (619 lines total) imports — this *is* the shared surface for one algorithm:

```
tensordict: TensorDict, TensorDictModule, InteractionType, CudaGraphModule,
            NormalParamExtractor
torchrl.collectors:  Collector, AsyncCollector
torchrl.data:        TensorDictReplayBuffer, LazyMemmapStorage/LazyTensorStorage,
                     PrioritizedSampler
torchrl.envs:        GymEnv, TransformedEnv, ParallelEnv, InitTracker, RewardSum,
                     StepCounter, DoubleToFloat, ExplorationType, set_exploration_type
torchrl.modules:     MLP, ProbabilisticActor, ValueOperator, TanhNormal
torchrl.objectives:  SACLoss, SoftUpdate, group_optimizers
torchrl.record:      VideoRecorder, get_logger, generate_exp_name
torchrl._utils:      timeit, compile_with_warmup, get_available_device
```

PPO-MuJoCo is the same set with `ClipPPOLoss`, `GAE`, `SamplerWithoutReplacement`, `AddStateIndependentNormalScale`.

Directory-level: `torchrl/objectives/` (34 losses + `objectives/value/advantages.py`), `torchrl/collectors/` (Collector, AsyncCollector, MultiSync/MultiAsync, `distributed/`, `weight_update.py`), `torchrl/data/replay_buffers/` (storages, samplers, writers, checkpointers, `her.py`, `scheduler.py`), `torchrl/modules/` (distributions, models, tensordict_module, exploration), `torchrl/envs/transforms/` (21 modules), `torchrl/trainers/` (Trainer + 22 hook classes), `torchrl/record/loggers/` (7 backends), and `torchrl/data/tensor_specs.py`.

**A convergence worth noting: at the *recipe* level, TorchRL practises your stance.** `sota-implementations/ppo/README.md`:

> "**Please note that each example is independent of each other for the sake of simplicity.**"

Measured: `sac/utils.py` (380 lines), `td3/utils.py` (318), `ddpg/utils.py` (324), `crossq/utils.py` (319), `discrete_sac/utils.py` (323), `cql/utils.py` (470), `iql/utils.py` (436), `tqc/utils.py` (237) each independently define the *same nine* function names — `apply_env_transforms`, `dump_video`, `env_maker`, `get_activation`, `log_metrics`, `make_collector`, `make_environment`, `make_loss_module`, `make_replay_buffer`. SAC and TD3 differ in only ~261 lines. **The library is maximally shared; the scripts on top of it are deliberately duplicated.** That is your architecture, one level up.

### 3.2 Has sharing silently changed an algorithm's behaviour? — **Yes, repeatedly and structurally**

This is the richest part of the sweep. Roughly 20 verified instances, spanning every shared subsystem. The strongest, ordered by how directly they bear on your stance:

**(a) The one that states your thesis in TorchRL's own words — issue [#4063](https://github.com/pytorch/rl/issues/4063)** (2026-08-06, closed 2026-08-07). A user migrating a hand-written PPO loop to the shared `PPOTrainer` discovered that `ValueEstimatorHook` registers at the `"pre_epoch"` stage, and `Trainer.optim_steps()` fires `pre_epoch` *inside* the epoch loop — so with `num_epochs=N`, GAE is recomputed N times against a critic that has already moved. Verbatim:

> "It is a meaningful algorithmic choice that is currently **selected implicitly by the hook placement** and is not obvious from the `add_gae` argument."
> "…**migrating to PPOTrainer can otherwise silently change the training semantics**."
> "Because GAE is recomputed using the updated critic before every epoch, the actor is effectively chasing a moving target."

vmoens closed it in 15 hours, documentation-only, confirming the variant is intentional: *"[preferred] Compute it once at the beginning of every optimization epoch. Advantages are refreshed using the updated critic. **This is the current trainer behavior.**"* — Note this is the *same* deviation the paper footnotes for its Table 1 PPO number, now propagated into the shared trainer via hook ordering rather than via an argument.

**(b) `terminated` read from the `done` key inside the shared value estimators — issue [#1662](https://github.com/pytorch/rl/issues/1662), PR [#1661](https://github.com/pytorch/rl/pull/1661)** (merged 2023-10-30). In `torchrl/objectives/value/advantages.py`:

```diff
-terminated = tensordict.get(("next", self.tensor_keys.done), default=done)
+terminated = tensordict.get(("next", self.tensor_keys.terminated), default=done)
...
-    terminated=done,
+    terminated=terminated,
```

**Every algorithm using GAE or TD(λ) bootstrapped as if time-limit truncations were terminations.** Reporter: *"3 mistakes that are most likely copy-pasting mistakes made during the large update to handle 'terminated' on top of 'done'."* Nothing crashed. This compounds with **issue [#1837](https://github.com/pytorch/rl/issues/1837)**, where the shared `StepCounter` transform *blanks* native truncation — reproduced in the issue: Acrobot-v1 gives `truncated: tensor([499, 999, 1499, 1999])` without it and `truncated: tensor([])` with `StepCounter(max_steps=2000)` appended. Two individually-defensible components; the composition destroys bootstrapping silently.

**(c) Your #1192, and its siblings.** Confirmed from `gh pr diff 1192`: PR **"[BugFix] Fix SAC alpha optim"** (merged 2023-05-26) flipped `TanhNormal.tanh_loc` from `True` to `False` *and* changed `SafeTanhTransform._inverse` eps from `finfo.eps` to `finfo.resolution`, in a PR whose title names SAC — while leaving the docstring reading "Default is :obj:`True`", producing issue [#1202](https://github.com/pytorch/rl/issues/1202). The same class of default-flip-in-a-shared-component recurs:
- **[#2049](https://github.com/pytorch/rl/issues/2049)**: *"The default value of `normalize_advantage` in `ClipPPOLoss` and `KLPENPPOLoss` is set to `True` even though the documentation states that it should be `False`. **The base class `PPOLoss` uses the correct default value.**"*
- **[#1181](https://github.com/pytorch/rl/issues/1181)** "DDPG worse performance than stable baselines" → PR [#1183](https://github.com/pytorch/rl/pull/1183) flipped `DDPGLoss.delay_value` `False`→`True`. vmoens: *"DDPG should default to have a target net and we should not be able to create SoftUpdate without one, so this one's defo on me :)"* — **DDPG shipped with no target network by default**, and `SoftUpdate` silently copied source onto itself. PR [#1184](https://github.com/pytorch/rl/pull/1184) added the `"The target and source data are identical for all params"` guard and made `SoftUpdate`/`HardUpdate` args keyword-only (previously `SoftUpdate(loss, 0.995)` bound positionally to `eps`, so passing a Polyak `tau` gave a 200×-wrong rate). Fixing it touched three unrelated algorithms' examples.
- **PR [#3679](https://github.com/pytorch/rl/pull/3679)** (merged 2026-04-28) on `torchrl/trainers/algorithms/ppo.py`: `gamma: 0.9→0.99`, `lmbda: 0.99→0.95`. Body verbatim: *"causing the agent to heavily discount future rewards and **perform significantly worse than expected on standard benchmarks**. Every major PPO reference implementation (Stable Baselines3, CleanRL, the existing `sota-implementations/ppo/`) uses gamma=0.99 … The GAE lambda was **inverted** from the standard value."* — the shared trainer was wrong while the duplicated script was right.

**(d) Composition producing silently wrong gradients for ~20 algorithms — RFC [#3866](https://github.com/pytorch/rl/issues/3866), PRs [#3888](https://github.com/pytorch/rl/pull/3888), [#4057](https://github.com/pytorch/rl/pull/4057).** Verbatim: *"Most other loss modules still call `_reduce(loss, reduction=self.reduction)` directly, which **silently averages padded positions into the gradient**."* Composing `SliceSampler(pad_output=True)` with any `LossModule` was wrong; the fix migrated CQL, DiscreteCQL, CrossQ, DDPG, DT, OnlineDT, DQN, DistributionalDQN, GAIL, IQL, DiscreteIQL, GRPO, PPO, ClipPPO, KLPENPPO, REDQ, SAC, DiscreteSAC, TD3, TD3BC. PR #4057's process note: *"before the fix … this branch **failed 72 existing tests** … That crash is the reason a mask-discovery change needs the objectives suite run against a baseline, not just new unit tests."*

**(e) One shared distribution, nine algorithms — issue [#2199](https://github.com/pytorch/rl/issues/2199) (open 26 months), PR [#4080](https://github.com/pytorch/rl/pull/4080)** (merged 2026-08-13): *"Fixes incorrect `TanhNormal` scores and gradients when finite-precision tanh saturation prevents `atanh(action)` from recovering the sampled preimage."* Blast radius quoted from the PR: *"used by `SafeProbabilisticModule` and by internally generated sample-and-score paths in **SAC, CQL, CrossQ, REDQ, A2C, PPO, Decision Transformer, GRPO, and V-trace**."* The user-visible symptom was "multi-agent SAC diverges after 1M steps."

**(f) A live bug I found in the current tree, and it lands on an evaluation metric.** `torchrl/trainers/trainers.py:2557-2559`, `LogValidationReward` docstring:

> "exploration_type (ExplorationType, optional): exploration mode to use for the policy. **By default, no exploration is used and the value used is `ExplorationType.DETERMINISTIC`.** Set to `ExplorationType.RANDOM` to enable exploration"

`torchrl/trainers/trainers.py:2583`, the actual signature:

```python
exploration_type: ExplorationType = ExplorationType.RANDOM,
```

and `trainers.py:2616` uses it: `with set_exploration_type(self.exploration_type):`. Now look at both call sites — `torchrl/trainers/helpers/trainers.py:260-266` and `sota-implementations/redq/utils.py:334-340` construct `recorder_obj` **without** passing `exploration_type` (intending deterministic eval → logs to `r_evaluation`), then construct a second `recorder_obj_explore` that **explicitly** passes `ExplorationType.RANDOM` (→ `r_evaluation_exploration`). Because the default is RANDOM, **both run stochastic evaluation**, and REDQ's headline `r_evaluation` is a stochastic-policy number. Same shape as #1202, three years later, in a metric.

**(g) Two more live, unfixed, verified against the working tree:**
- `torchrl/modules/distributions/continuous.py:74-76` documents `TruncatedNormal.tanh_loc` as *"if `False`, the above formula is used"* while `:118-119` applies it when **True**. `TanhNormal` (:367) and `TanhDelta` say "if `True`". Inverted docstring, same file, today — the residue of #1192.
- The Hydra config system's default continuous head, `torchrl/trainers/algorithms/configs/modules.py:307-345` (`TanhNormalModelConfig`) and its builder `_make_tanh_normal_model` at `:500-552`, **never reads the environment's action spec** — no `low`/`high` is threaded to `TanhNormal`, and `TanhNormalModelConfig` has no `distribution_kwargs` field. Any env whose bounds are not `[-1, 1]` silently gets a policy clipped to `[-1, 1]`. The shipped `sac_trainer` config happens to use HalfCheetah-v4 (bounds `[-1,1]`), so it is latent rather than active.

**(h) Replay-buffer specifics relevant to your PPO-family baselines.** `torchrl/data/replay_buffers/samplers.py:598-604`, `SamplerWithoutReplacement` — the sampler PPO-MuJoCo uses (`ppo_mujoco.py:158` constructs it bare):

> "When the sampler reaches the end of the list of available indices, a new sample order will be generated and the resulting indices will be completed with this new draw, **which can lead to duplicated indices, unless the `drop_last` argument is set to `True`.**"
> `def __init__(self, drop_last: bool = False, shuffle: bool = True):`

The reference PPO behaviour is to drop the incomplete minibatch. TorchRL's default refills it from a fresh permutation, so some transitions get two gradient updates per epoch. The shipped config (2048/64 = 32) divides evenly so it is latent; any override of `frames_per_batch` or `mini_batch_size` activates it. **Nobody has filed this** — it was found by reading the sampler, not from an issue.

PER has its own cluster: issues [#2205](https://github.com/pytorch/rl/issues/2205), [#2210](https://github.com/pytorch/rl/issues/2210), [#2211](https://github.com/pytorch/rl/issues/2211), [#2212](https://github.com/pytorch/rl/issues/2212) (June 2024) — `_max_priority` initialised to 1 while Bellman errors are near 0, so it may never update and new samples get IS weight ≈ 0; `update_priority()` applying `pow(priority + eps, alpha)` a second time; `PrioritizedSliceSampler` sampling **across trajectory boundaries** *"unlike `SliceSampler` which handles this correctly"*.

**(i) The maintainers' own articulation of the failure mode — issue [#2477](https://github.com/pytorch/rl/issues/2477)** (Gymnasium 1.0 autoreset), verbatim:

> "The recent release of Gymnasium 1.0 introduces an auto-reset feature that **silently but irrevocably changes the behavior of the step method** … it **breaks the modularity and data integrity assumptions in TorchRL**."
> "This will **silently cause the last observation of trajectory `t` to be considered as the first of trajectory `t+1`**."
> "resets are infrequent but in some frameworks (eg, Robohive) they can occur as often as every 50 steps, which could lead to a **2% amount of corrupted data in the buffer**."

They chose to refuse support rather than absorb the semantics.

**Well-searched negatives** (worth recording): no filed bug for GAE `time_dim` inference being wrong; none for `vec_generalized_advantage_estimate` disagreeing with the loop version (they are tested against each other exhaustively); none for PER α/β defaults; none for collector "stale weights" (closest is #995, #3000 — both loud); none for `init_random_frames` off-by-one; none for `ExplorationType` semantics changing; **zero issues** about OU / additive-Gaussian defaults; none for `VecNorm` train/eval statistics sharing; none for `CatFrames` mis-resetting at episode boundaries. The structural observation: **TorchRL users file crashes, not "my numbers are wrong."** In the whole corpus only two reports are of the latter kind — [#1181](https://github.com/pytorch/rl/issues/1181) (DDPG vs SB3) and [#1221](https://github.com/pytorch/rl/issues/1221) (PPO on Pong) — and **both required the reporter to hold an external reference implementation to notice anything at all.** On #1221 vmoens' first response is: *"A couple of weeks back we had good perf so I guess it must be a decent change we made."*

### 3.3 Is there a mechanism that would catch it? — Essentially no

Four independent layers, each failing for a different reason:

**Benchmarks are wall-clock only.** `.github/workflows/benchmarks.yml` runs `pytest --benchmark-only --benchmark-json output.json` and feeds `benchmark-action/github-action-benchmark@v1` with `tool: 'pytest'`, `fail-on-alert: true`, **`alert-threshold: '200%'`** (lines 196-201, 212-217) — a 2× *slowdown* alarm. `benchmarks_pr.yml:384` compares baseline vs contender with `--reporting-threshold 5`, again a percentage speed delta. **`benchmarks/test_objectives_benchmarks.py` is 1389 lines with zero `assert` statements** — every test ends in `benchmark(loss, td)`; the loss value is never inspected. A build where every loss returned `torch.zeros(())` would pass, faster.

**Loss tests are structural and self-consistent, never referential.** The old `test/test_cost.py` is now `test/objectives/` — 20 files, 25,275 lines. The densest numerical file, `test_values.py`, has 113 asserts of which 68 are `assert_close` — and **all 68 are TorchRL-vs-TorchRL**: chunked vs unchunked (`test_values.py:85-126`), vectorized vs loop (`test_gae` at `:1507-1537` asserts `vec_generalized_advantage_estimate == generalized_advantage_estimate`), shifted vs unshifted, split vs concatenated. These are identity tests, which stay green precisely when both paths share a misinterpretation — exactly what happened with #1662's `terminated=done`, which lived in the shared `forward` so both backends agreed perfectly while both bootstrapped through truncations. The rest of the suite asserts key sets, `isfinite()`, gradient presence/absence, functional==stateful, and input non-mutation (`_objectives_common.py:39-52`, `_check_td_steady`). The one exception is three days old: PR [#4079](https://github.com/pytorch/rl/pull/4079) added `test/objectives/test_tqc.py::test_tqc_numerical_contract` with hand-computable constant-quantile critics — one algorithm out of ~25, and still not a comparison to the TQC authors' code.

**No reward threshold is asserted anywhere in CI.** `.github/unittest/linux_sota/scripts/test_sota.py` is a pure smoke test: 36 commands run with `collector.total_frames=40`, `frames_per_batch=20`, `logger.backend=`, sharded 2 ways; `test_commands` calls `run_command`, which raises only on non-zero exit. A repo-wide grep for reward thresholds finds only env-reward-range checks in `test/libs/test_mujoco.py:754`, a toy mock in `test/envs/test_special.py`, GRPO's in-training data filter, and DT's `target_return` conditioning input.

**The single exception — and it proves the rule.** `sota-implementations/dreamer_v3/benchmark.py` runs seeds `[0,1,2]`, aggregates median/IQR, and raises:

```python
if final_median < args.minimum_final_return:
    raise RuntimeError(f"Final median DMC Walker return {final_median:.1f} is below {args.minimum_final_return:.1f}.")
```

with `benchmark: {seeds: [0,1,2], minimum_final_median_return: 700.0}` in `config_dmc_walker.yaml:38-40`. **It is not wired into CI** — grep for `benchmark.py` in `.github/` returns nothing relevant, and `sota-implementations/dreamer_v3/README.md` says so: *"Full learning-curve runs are intended for scheduled or manual validation; **pull-request CI uses short smoke overrides**."* One algorithm, one env, one threshold, run by hand.

**The doc/default-mismatch class specifically is structurally uncatchable.** `scripts/check-docstring-args` (wired at `.pre-commit-config.yaml:70-72`) verifies each argument *has* a docstring entry; it parses names via regex and never reads the AST default. `tanh_loc: bool = False` documented as "Default is `True`" is a clean pass. And there is no behavioural backstop: `grep -rn "tanh_loc" test/` returns **exactly one line** (`test/test_distributions.py:601`), where it is passed explicitly as `False`. **No test exercises `tanh_loc=True`; no test would fail if the default flipped either way.** Meanwhile `AGENTS.md` §12 mandates a two-minor-release runway for default changes — none of the flips above went through it, because they all shipped as `[BugFix]`, which the policy does not gate. `AGENTS.md` §10 states outright: *"Pure correctness fixes don't need one [a benchmark]."*

**Bottom line for your stance:** TorchRL's CI can prove a loss module is fast, differentiable, shape-correct, non-mutating, key-consistent and self-consistent across its own implementations — and cannot prove its value is right. Your "any join carries a burden of proof" is not a conservative position relative to this library; it is the position this library's own issue tracker keeps arriving at after the fact.

---

## 4. Continuous heads

### 4.1 The construction

`ProbabilisticActor(module=TensorDictModule(net, out_keys=["loc","scale"]), in_keys=["loc","scale"], spec=…, distribution_class=…, distribution_kwargs=…)`, defined at `torchrl/modules/tensordict_module/actors.py:146` as a subclass of `SafeProbabilisticTensorDictSequential`.

Two parameter heads exist, and **the choice is per-algorithm, not a single library default**:

| | class | location | `scale_mapping` | floor | init |
|---|---|---|---|---|---|
| **State-dependent** | `NormalParamExtractor` | `tensordict/nn/distributions/continuous.py:41-87` | `"biased_softplus_1.0"` | `scale_lb=1e-4` | inherits `nn.Linear` default |
| **State-independent** | `AddStateIndependentNormalScale` | `tensordict/nn/distributions/continuous.py:90-190` | `"exp"` | `scale_lb=1e-4` | `init_value=0.0`, `make_param=True` |

`NormalParamExtractor.forward`: `loc, scale = tensor.chunk(2, -1); scale = self.scale_mapping(scale).clamp_min(self.scale_lb)`.
`AddStateIndependentNormalScale.forward`: `scale = self.state_independent_scale.expand_as(loc); scale = mappings(self.scale_mapping)(scale).clamp_min(self.scale_lb)`.

**`AddStateIndependentNormalScale` is your four authored heads, in the field's own library.** A trainable `nn.Parameter` of shape `(action_dim,)`, **initialised to 0.0**, exponentiated → std = 1.0 at init. That is exactly "state-independent log_std initialised to 0". It is what TorchRL uses for **every** on-policy MuJoCo actor: `ppo/utils_mujoco.py:317`, `a2c/utils_mujoco.py:100`, `rnd/utils_mujoco.py:128`, `gail/ppo_utils.py:79`, `ppo-async/utils_mujoco.py:142`, plus `examples/collectors/isaaclab_rnn_ppo_memory_utils.py:381` and `examples/satellite/_utils.py:724`. **Use it as your prior-art citation** — your design decision is the library's standard for the on-policy family, not a local invention.

The off-policy family uses the state-dependent head: `sac/utils.py:251-253` builds `NormalParamExtractor(scale_mapping=f"biased_softplus_{cfg.network.default_policy_scale}", scale_lb=cfg.network.scale_lb)` with `default_policy_scale: 1.0`, **`scale_lb: 0.1`** (`sac/config.yaml:41-42`). Note that std floor: original SAC clamps `log_std ∈ [-20, 2]`, i.e. std ≳ 2e-9. TorchRL's SAC cannot produce a std below **0.1**. Undocumented deviation.

Full mapping menu (`tensordict/nn/utils.py:86-93`): `"softplus"`, `"exp"`, `"relu"`, `"biased_softplus"`, `"none"`, `"expln"` (the SDE mapping from Rückstieß et al.), plus the parameterised `"biased_softplus_{bias}"` / `"biased_softplus_{bias}_{min_val}"` — `biased_softplus(bias, min_val=0.01)` computes `softplus(x + inv_softplus(bias - min_val)) + min_val` so that `f(0) = bias`.

**The library's *configured* default** (`torchrl/trainers/algorithms/configs/modules.py:307-345`, `TanhNormalModelConfig` → `_make_tanh_normal_model` at `:500-552`): MLP → `NormalParamExtractor(scale_mapping="biased_softplus_1.0", scale_lb=1e-4)` → `TanhNormal`, `default_interaction_type="RANDOM"`. **State-dependent, softplus, tanh-squashed** — and, as noted in §3.2(g), it drops the action bounds.

### 4.2 The distributions

`TanhNormal` — `torchrl/modules/distributions/continuous.py:337`:
```python
def __init__(self, loc, scale, upscale=5.0, low=-1.0, high=1.0,
             event_dims=None, tanh_loc=False, safe_tanh=True)
```
- `event_dims` defaults to `min(1, loc.ndim)`; `arg_constraints` requires `scale > 1e-6`.
- `tanh_loc=True` applies `loc = tanh(loc/upscale)*upscale` then `loc += (high-low)/2 + low` (`:556-560`). **Default is `False`** — no mean squashing. All SOTA scripts pass `tanh_loc: False` explicitly (`sac/utils.py:248`, `ppo/utils_mujoco.py:295`, `a2c/utils_mujoco.py:62`).
- Non-`[-1,1]` bounds are handled by composing `SafeTanhTransform` with `_PatchedAffineTransform(loc=(high+low)/2, scale=(high-low)/2)` (`:465-473`).
- **`mode` raises `RuntimeError`** (`:598-602`): *"The distribution TanhNormal has not analytical mode. Use ExplorationMode.DETERMINISTIC to get a deterministic sample from it."* **`mean` raises `NotImplementedError`** (`:643-649`). `deterministic_sample` (`:605-610`) returns `tanh(loc)` pushed through the transforms — i.e. the standard SAC/DrQ-v2 eval action. There is also a `get_mode()` that estimates the mode by **200 Adam steps** (`:612-641`).

`TruncatedNormal` — `continuous.py:171`, `__init__(loc, scale, upscale=5.0, low=-1.0, high=1.0, tanh_loc=False)`. **This one is worth comparing carefully against your five DrQ-v2-family baselines.** TorchRL's is a *genuine* truncated normal (Burkardt-normalised, backed by `truncated_normal.py`): `log_prob` (`:288-307`) clamps values into `[a,b]` and masks anything outside to `-inf`. DrQ-v2's `TruncatedNormal` subclasses `pyd.Normal` and only clips the *sample*, leaving the density unnormalised. Also `deterministic_sample = self.mean` (the truncated mean), not `loc`. These are different distributions with the same name — if you ever borrow from TorchRL here, that is the trap.

`IndependentNormal` — `continuous.py:47`, the unsquashed option: `__init__(loc, scale, upscale=5.0, tanh_loc=False, event_dim=1)`, `mode = base_dist.mean`, `deterministic_sample = mean`. **No SOTA script uses it.**

Note `TruncatedNormal`'s error message reads `"TanhNormal high values must be strictly greater than low values"` (`:220`) — a copy-paste artefact.

### 4.3 The action-bound problem

TorchRL's answer is **squash, not clip**, with three independent guards:

1. **The distribution's support is the box.** `TanhNormal` composes tanh + affine, so samples are in `[low, high]` by construction. `distribution_kwargs` in the SOTA scripts pass `action_spec.space.low/high` (`sac/utils.py:246-247`, `ppo/utils_mujoco.py:294-295`).
2. **`safe` projection, off by default.** `ProbabilisticActor(safe=False)` — `torchrl/modules/tensordict_module/probabilistic.py:217`, and `common.py:205` for deterministic modules. When enabled it calls `TensorSpec.project`, which for `Bounded` is `torch.clamp(val, low, high)` (`torchrl/data/tensor_specs.py:2599-2603`). Off by default because the squash makes it redundant.
3. **`TanhModule`** (`torchrl/modules/tensordict_module/actors.py:2066`) for deterministic policies, with an optional `clamp: bool = False` that pulls outputs to "a minimum resolution" inside the bounds.

`ClipTransform` (`torchrl/envs/transforms/_clip.py:37`) exists but is documented for observations/rewards, not for closing an action-distribution mismatch.

**Do they warn about the clip-vs-squash log-prob mismatch? Yes — but in the knowledge base, not the API docs.** `knowledge_base/DEBUGGING_RL.md`, §"Action Space" → "Are your actions normalized/standardized?", verbatim:

> "It is common to [clip](https://github.com/DLR-RM/stable-baselines3/blob/…/policies.py#L354) the action outputs of a policy to a reasonable range. **Note, this clipped action should not (as opposed to the raw action) be used for training because the clip operation is not part of the computation graph and gradients will be incorrect. This should be thought of as part of the environment and so a policy will learn that actions in the bounded region lead to higher reward.** One can also use a squashing function such as tanh. This can be part of the computation graph and to do this efficiently, **one should correct the log probs** such as is done [here](https://github.com/Unity-Technologies/ml-agents/blob/develop/…/distributions.py#L110). Remember to remap actions to the original action space on the environment side if normalized."

That is the field's canonical statement of your exact problem, and it *endorses* your choice: with env-side `np.clip`, the clip is part of the environment, the policy scores the raw unclipped action, and the log-prob is self-consistent. The failure mode the doc warns against is scoring the *clipped* action — which is what you avoid.

The same file also carries a warning directly relevant to your visual-generalization setting:

> "**Be very careful with any data augmentation.** Data augmentation cannot be applied to RL in the same ways as CV since an agent needs to act based on the observation. As an example, flipping an image may correspondingly 'flip' the appropriate action."

**On the squash side, they are candid that there is no clean answer.** Issue [#2199](https://github.com/pytorch/rl/issues/2199), where maintainers compare their tanh log-prob handling against RLlib's and SB3's line by line. vmoens:

> "I played a lot with Tanh transform back in the days and the TLDR is that **anything you do (clamp or no clamp) will degrade performance for someone.** What about giving the option to use the 'safe' tanh (with clamping) or not?"

matteobettini: *"The `logp` seems to be the core of these instabilities. I also experienced that in the past. Clamping tricks are helpful but we have to be careful how we do this."*

The eventual fix is `TanhNormal.rsample_and_log_prob` (`continuous.py:478-515`), whose docstring is the cleanest statement of the hazard I found anywhere:

> "Calling `rsample()` and `log_prob()` separately reconstructs the pre-tanh value from the rounded action. **Once tanh saturates, that inverse can return a different Normal value and produce the wrong score and gradients.** This method scores the exact Normal value used to create the action."

Wiring check: `SACLoss` (`sac.py:56`), `CQLLoss`, `REDQLoss`, `CrossQLoss`, `DTLoss` all route through `rsample_and_log_prob`. **PPO and A2C do not** for the ratio — `PPOLoss._log_weight` (`ppo.py:753-797`) computes `log_prob = dist.log_prob(stored_action)`, which for `TanhNormal` requires the `atanh` inverse and hits saturation. They call `rsample_and_log_prob` only for the MC entropy estimate (`a2c.py:419`). Given that TorchRL's PPO-MuJoCo uses `TanhNormal` (unlike Schulman/SB3/CleanRL), this is a live path.

### 4.4 Exploration semantics — a shared-surface subtlety worth knowing

`InteractionType` (`tensordict/nn/probabilistic.py:74-78`): `MODE`, `MEDIAN`, `MEAN`, `RANDOM`, `DETERMINISTIC`. `DETERMINISTIC` queries `deterministic_sample`, falling back to `mean` (`:66-70`); the registry (`:100-121`) maps most torch distributions to `MEAN`, enumerable ones to `MODE`.

`ProbabilisticActor`'s own default is `InteractionType.DETERMINISTIC` (`probabilistic.py:218`), but `DEFAULT_EXPLORATION_TYPE = ExplorationType.RANDOM` (`torchrl/collectors/_constants.py:48`) and collectors install it via `set_interaction_type`. **The same policy object samples stochastically inside a collector and deterministically outside it** — exploration is a property of the ambient context, not the module. Issue [#2175](https://github.com/pytorch/rl/issues/2175) is the resulting user report: *"This issue becomes particularly problematic when implementing training code without using a data collector, leading to problems in training and learning performance."*

---

## 5. Metrics and logging vocabulary

### 5.1 Loggers

`torchrl/record/loggers/`: `CSVLogger`, `WandbLogger`, `TensorboardLogger`, `MLFlowLogger`, `TrackioLogger`, plus `RayLogger`/`ProcessLogger` service wrappers. Base API (`common.py`): `log_scalar`, `log_video`, `log_hparams`, `log_histogram`, `log_metrics(metrics, step, keys_sep="/")`. `log_metrics` batches CUDA→CPU transfers into one sync and flattens nested TensorDict keys with `/`.

### 5.2 Loss-module output keys — this is the field vocabulary you asked for

**`ClipPPOLoss.out_keys`** (`torchrl/objectives/ppo.py:1344-1355`) — richer than the scripts actually log:
```
loss_objective, clip_fraction, entropy, loss_entropy, loss_critic,
value_clip_fraction, ESS, kl_approx, max_ratio, mean_ratio
```
plus `explained_variance`, set at `ppo.py:1435` and gated by `log_explained_variance: bool = True` (`:471`). `composite_entropy` for multi-head actions. Base `PPOLoss.out_keys` (`:630-640`) is the leaner `loss_objective` + `entropy`/`loss_entropy` + `loss_critic` + `value_clip_fraction`.

Definitions worth noting: `ESS` is set as `ess/batch` (`:1437`); the docstring at `:143-145` explains *"the inverse of the sum of the squared importance weights … Any value below 1 indicates that the samples are not equally weighted."* `kl_approx = (prev_log_prob - log_prob).mean()` (`:793`, `:1414`) — the **k1** estimator only; TorchRL does not compute Schulman's k3 `(r-1) - log r` that CleanRL reports as `approx_kl`.

**Off-policy keys:**
- `SACLoss` (`sac.py:676-700`): `loss_actor`, `loss_qvalue`, `loss_alpha`, `alpha`, `entropy` (= `-log_prob.mean()`), plus `loss_value` for v1. Writes `td_error` to `tensor_keys.priority` (`:668`).
- `DDPGLoss` (`ddpg.py:95`, `:180-184`, `:381-384`): `loss_actor`, `loss_value`, `td_error`, `pred_value`, `target_value`, `pred_value_max`, `target_value_max`.
- `TD3Loss` (`td3.py:134`, `:405`, `:491-495`): `loss_actor`, `loss_qvalue`, `pred_value`, `state_action_value_actor`, `next_state_value`, `target_value`, `td_error`.
- `CQLLoss`: adds `loss_cql`. `DQNLoss`: `loss` + `td_error`.
- `A2CLoss` (`a2c.py:551-560`): `loss_objective`, `entropy`, `loss_entropy`, `loss_critic`, `value_clip_fraction`.
- Priority key default is `"td_error"` everywhere (`ddpg.py:168`, `td3.py:199`, `dqn.py:157`).

**Standard TensorDict keys:** `advantage`, `value_target`, `state_value`, `action`, `reward`, `done`, `terminated`, `td_error`, and the log-prob key — which is **`"sample_log_prob"` when `composite_lp_aggregate()` is True, `"action_log_prob"` when False** (`ppo.py:445-449`). CI pins the flag off (`test_sota.py:13`: `assert not composite_lp_aggregate()`).

### 5.3 What the SOTA scripts actually log

**SAC** (`sac.py:197-229`): `train/reward`, `train/episode_length`, `train/q_loss`, `train/actor_loss`, `train/alpha_loss`, `train/alpha`, `train/entropy`, `eval/reward`, `time/*` via `timeit.todict(prefix="time")` → `time/collect`, `time/rb - extend`, `time/rb - sample`, `time/train`, `time/update`, `time/eval`, and `time/speed`.

**PPO** (`ppo_mujoco.py:296-378`): `train/reward`, `train/episode_length`, `train/{loss_objective,loss_critic,loss_entropy,…}` (whatever survives in `losses_mean`), `train/lr`, `train/clip_epsilon`, `eval/reward`, `time/collecting`, `time/training`, `time/adv`, `time/rb - extend`, `time/update`, `time/eval`, `time/speed`.

**TD3** (`td3.py:217-243`): `train/reward`, `train/episode_length`, `train/q_loss`, `train/a_loss`, `eval/reward`, `time/speed`.
**DQN-Atari** (`dqn_atari.py:207-259`): `train/episode_reward`, `train/episode_length`, `train/q_values`, `train/q_loss`, **`train/epsilon`**, `eval/reward`, `time/*`.
**IMPALA** (`impala_single_node.py:152-244`): `train/reward`, `train/episode_length`, `train/{losses}`, `train/lr`, `train/sampling_time`, `train/training_time`, `eval/reward`, `eval/time`.

**Trainer-API hooks** add: `r_training` (via `LogScalar(("next","reward"), "r_training")`, `trainers.py:2187`), `r_evaluation` and `total_r_evaluation` (`LogValidationReward`, `:2606-2640`), `grad_norm` (`:77`, `:312`), `optim_steps`, and **`UTDRHook`** (`:3024-3072`) → `utd_ratio`, `write_count`, `update_count`, with `utd_ratio = batch_size * update_count / write_count`.

**Against your specific list:**

| Metric | In TorchRL? |
|---|---|
| replay ratio | Yes, two names: `utd_ratio` (`UTDRHook`, trainer-only) and the config knob `optim.utd_ratio` (SAC/TD3/DDPG/CQL/IQL/TQC = 1.0). DreamerV3 calls it `train_ratio: 1024` |
| TD error | Yes — `td_error`, the universal priority key |
| target-network divergence | **No.** Grep for `target.*diverg`, `param_distance`, `target_norm` returns nothing. Not measured anywhere |
| alpha / entropy temperature | Yes — `alpha`, `loss_alpha`, `entropy`; `SACLoss` defaults `alpha_init=1.0`, `target_entropy="auto"` (= `-prod(action_shape)`), with `min_alpha`/`max_alpha`/`fixed_alpha` |
| explained variance | Yes — `explained_variance`, on by default in `PPOLoss` |
| clip fraction | Yes — `clip_fraction` and separately `value_clip_fraction` |
| approx KL | Partly — `kl_approx` (k1 only, no k3) |
| entropy | Yes — `entropy`, `loss_entropy`, `composite_entropy` |
| ESS | Yes — `ESS`, plus `max_ratio` / `mean_ratio` |
| grad norm | Trainer API only (`grad_norm`); the SOTA scripts do not log it |

**Caveat: the SOTA scripts log a small subset of what the losses emit.** PPO-MuJoCo logs `losses_mean` items, so whether `ESS`/`kl_approx`/`clip_fraction`/`explained_variance` reach W&B depends on `out_keys` filtering. Neither `train/` nor `eval/` carries an explicit clip-fraction or KL line.

### 5.4 Evaluation protocol — and it is not uniform

**Eval is deterministic** everywhere: `with set_exploration_type(ExplorationType.DETERMINISTIC)` in `sac.py:214`, `td3.py:231`, `ddpg.py:205`, `crossq.py:234`, `ppo_mujoco.py:353`, `a2c_mujoco.py:245`, `a2c_atari.py:264`, `cql_offline.py:176`, `discrete_cql_online.py:192`, `online_dt.py:150`. For `TanhNormal` this resolves to `tanh(loc)`.

**But the two families disagree on everything else.**

| | off-policy (SAC/TD3/DDPG/CrossQ) | on-policy (PPO/A2C) |
|---|---|---|
| frequency | `eval_iter: 25000` frames | `test_interval` |
| episodes | **1** — a single `eval_env.rollout(max_episode_steps, break_when_any_done=True)` (`sac.py:217-224`) | `num_test_episodes` = 3–5, looped in `eval_model` (`ppo/utils_mujoco.py:433-447`) |
| metric | `eval_rollout["next","reward"].sum(-2).mean()` — one episode return | mean over N episode returns |
| seed | `cfg.env.seed: 42` | **none** |

And the eval frequencies are degenerate for the on-policy family: `ppo/config_mujoco.yaml` has `test_interval: 1_000_000` with `total_frames: 1_000_000`; `config_atari.yaml` `test_interval: 40_000_000` with `total_frames: 40_000_000`; `impala/config_single_node.yaml` `test_interval: 200_000_000` with `total_frames: 200_000_000`. **Deterministic evaluation runs exactly once, at the end, on 3–5 episodes.** Everything plotted during training is `train/reward` — episode returns completed under the *stochastic* collection policy. (DQN-Atari is the exception: `test_interval: 1_000_000` on 40M.)

**Seed counts, concretely:** `seed: 42` in sac/td3/ddpg/crossq/tqc/gail/diffusion_bc/td3_bc/discrete_sac configs; `seed: 0` in dreamer/redq; **no seed field** in ppo/a2c/impala/dqn. Multi-seed exists in exactly one place: `dreamer_v3/config_dmc_walker.yaml:38-39` `seeds: [0,1,2]` driving `benchmark.py`. `sota-check/submitit-release-check.sh --n_runs` defaults to 1.

One design note you may want: `ProbabilisticActor` accepts a `generator` argument specifically so *"the agent's RNG stream must be isolated from the environment's — see Patterson et al., 'Empirical Design in Reinforcement Learning' (arXiv:2304.01315)"* (`actors.py:228-233`). No SOTA script uses it.

---

## 6. Robosuite / visual generalization

**Robosuite is reachable, transitively, through LIBERO — and it supports pixels.** `torchrl/envs/libs/libero.py:204` defines `LiberoWrapper` (+ `LiberoEnv`), described at `:213` as *"tasks (robosuite/MuJoCo based) widely used to evaluate and fine-tune"* policies. Signature (`:358-360`): `camera: str = "agentview"`, `wrist_camera: str | None = None` (e.g. `"robot0_eye_in_hand"`), `from_pixels: bool = False`, plus `camera_heights`/`camera_widths` and `render_gpu_device_id` *"to pin robosuite rendering"* (`:236`). With `from_pixels=True` it exposes the camera frame as a root `pixels` entry in HWC uint8, *"the torchrl pixels-rendering convention"* (`:286-291`). The CI installs `robosuite==1.4.0` (`.github/unittest/linux_libs/scripts_libero/install.sh:88`, with a note at `:77` that *"robosuite 1.4.0 calls the pre-3.10 mj_fullM signature"*).

**There is no direct robosuite wrapper** — no `torchrl/envs/libs/robosuite.py`. Full wrapper list (`torchrl/envs/libs/`): brax, dm_control, envpool, genesis, gym, habitat, isaac_lab, isaacgym, jumanji, **libero**, meltingpot, mjlab, mujoco_playground, openml, openspiel, pettingzoo, **procgen**, robohive, safety_gymnasium, smacv2, unity_mlagents, vmas.

**Manipulation from pixels: no.** The one manipulation path in a SOTA script is MuJoCo Playground's Franka Panda `PandaPickCube` through `sota-implementations/ppo/ppo_mujoco.py` (`env.backend=mujoco_playground`). Its README is explicit on both counts:
> "This run is intended as a **functional training/checkpointing check** for a richer manipulation environment **rather than a solved-policy benchmark**."
> "**Pixel video rendering is unavailable for this backend because the MuJoCo Playground wrapper does not support `from_pixels=True`.**"

and `ppo/utils_mujoco.py:78-81` raises on `from_pixels=True` for that backend.

**Pixel-based continuous control: none.** Confirmed for `sac/utils.py:89` (`from_pixels=cfg.logger.video` — video only), and identically in `ddpg/utils.py`, `cql/utils.py`, `iql/utils.py`, `discrete_sac/utils.py`. Pixel *training* exists only in `dreamer/`, `dreamer_v3/`, and the discrete Atari scripts (`ppo/utils_atari.py`, `a2c/utils_atari.py`, `dqn/dqn_atari.py`, `impala/utils.py`). **There is no DrQ-style pixel SAC/DDPG anywhere.**

**Procgen — a genuinely useful partial.** `torchrl/envs/libs/procgen.py` provides `ProcgenWrapper` (`:49`) and `ProcgenEnv` (`:247`) exposing exactly the generalization knobs: `distribution_mode` (`:262`), `start_level` (`:265`, default 0), `num_levels` (`:266`). So the *environment-side* train/test level split your four Procgen baselines rely on is supported — while none of PPG, IDAAC, IBAC-SNI or CTRL is implemented, and no SOTA script uses the wrapper.

**Domain randomization / generalization evaluation: nothing.** Grep for `domain_random`, `randomiz`, `generaliz`, `distractor` across `torchrl/`, `docs/source/`, `sota-implementations/` returns only false positives (`generalized_advantage_estimate`, "RANDOMIZED ENSEMBLED DOUBLE Q-LEARNING" in REDQ's docstring). No train/test env-split protocol, no visual-perturbation harness, no held-out-scene evaluation. Combined with §1's absence of random image augmentation, **RL-ViGen's entire problem statement is outside TorchRL's scope today.**

---

## Things I could not verify

- **A public W&B URL for the reproduced curves.** `sota-check/` logs to `torchrl-example-check-<short-sha>`; searches for that string and for `wandb.ai` + torchrl surfaced only BenchMARL's separate public project. I believe these projects are internal to Meta but I have no confirmation either way.
- **Whether TorchRL is tracked by Open RL Benchmark** (arXiv:2402.03046). The abstract says "a wide range of RL libraries" without naming them, and I could not extract the library list from the paper body.
- **Whether the `expln` mapping or `IndependentNormal` are used by any downstream project** — they exist in the library and are used by no SOTA script.
- I did **not** deep-read `sota-implementations/` READMEs for a2c, dqn, impala, dreamer, redq, bandits, grpo, multiagent, expert-iteration, vla_grpo. I read ppo's and dreamer_v3's in full; the deviation inventory in §2.4 could therefore be incomplete on the low side.

---

## Three things I'd suggest taking

1. **`AddStateIndependentNormalScale`** (`tensordict/nn/distributions/continuous.py:90-190`) is your four authored heads, verbatim, in PyTorch's own RL library: trainable per-dimension parameter, `init_value=0.0`, `scale_mapping="exp"`, `scale_lb=1e-4`, used by every on-policy MuJoCo actor TorchRL ships. Cite it and the file:line list in §4.1 — your decision is the field's standard for that family, not an improvisation.
2. **`knowledge_base/DEBUGGING_RL.md`, §"Action Space"** is the clean prior-art statement that env-side clipping is the *correct* framing ("This should be thought of as part of the environment") and that the error is scoring the clipped action. It endorses what you did. Pair it with issue #2199's *"anything you do (clamp or no clamp) will degrade performance for someone"* if you need to defend not squashing.
3. **The metric vocabulary in §5.2** is worth adopting name-for-name — `ESS`, `clip_fraction`, `value_clip_fraction`, `kl_approx`, `explained_variance`, `max_ratio`/`mean_ratio` on-policy; `td_error`, `alpha`, `entropy`, `pred_value`/`target_value`/`pred_value_max`, `utd_ratio` off-policy. Two gaps you could fill cheaply and be ahead of the library: **target-network divergence is measured nowhere in TorchRL**, and its `kl_approx` is the k1 estimator only.

And one thing to note rather than take: **TorchRL's own SOTA scripts duplicate rather than join** — *"each example is independent of each other for the sake of simplicity"* — with nine identically-named helpers reimplemented across eight off-policy `utils.py` files. The library is the most-shared thing in the ecosystem; the recipes on top of it are not. Your architecture is the same choice, made one level lower.
