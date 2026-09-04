# RAW — broad sweep across 14 RL libraries

**Provenance.** Subagent report, received 2026-08-17. Run blind: it did not read
`docs/AUDIT-2026-08-17.html` or anything else in this `docs/` tree. Brief given to it is in
`_brief-given-to-jobs.md` / `../CONTEXT.md`.

**Preserved verbatim and unmerged**, per an explicit instruction to record the original
information before any synthesis. The only alterations are un-escaping HTML entities that the
message transport introduced (`&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&`); no wording, number,
locator, or claim has been changed, and nothing has been cut.

**Not independently re-verified by me** beyond the spot checks noted in the synthesis. The
report's own `UNVERIFIED` markers and its closing "what I did not get to" section are its own
admissions and should be read as such. This agent spawned parallel children for some libraries;
its "Verification status" paragraph states which sections it executed itself and which it
inherited and re-checked. A second, independently-produced report covering four of the same
libraries is preserved separately in `pearl-dopamine-acme-mushroom-*.md` — where the two
disagree, both readings are kept rather than reconciled.

---

All four sweeps are complete and I have spot-verified the load-bearing quotes against the clones directly. Here is the report.

---

# Library implementation sweep — 12 visual-RL baselines vs. the established RL libraries

**Method.** Shallow-cloned every library into `/Users/a2mogus/.claude/jobs/d037da9e/tmp/libsweep/{skrl,sb3,sb3-contrib,zoo,sbx,cleanrl,tianshou,jaxrl,jaxrl2,jaxrl_m,purejaxrl,brax,AgileRL,garage,acme,dopamine,Pearl,mushroom-rl}` and grepped/read source directly, supplemented with WebFetch/WebSearch for papers, docs and issues. File paths below are repo-relative to those clone roots. Quotes marked verbatim were read from the cloned file or fetched page.

**Verification status.** I personally executed the SKRL, SB3-family, CleanRL, SBX and robosuite work. The Tianshou/jaxrl, Pearl/Dopamine/Acme/Mushroom, and garage/PureJaxRL/Brax/AgileRL sections came from parallel sweeps; I independently re-verified their highest-value quotes and coverage claims against the same clones (jaxrl README fidelity disclaimer, jaxrl_m single-file philosophy, Tianshou 5-seed/IQM line, PureJaxRL "not a modular library", garage `TanhNormal` docstring, Acme's absent `agents/jax/drq*` + `DrQTorso` locator, Dopamine's `DrQ`/`DrQ_eps` + rliable link, Pearl's tanh log-prob correction, Mushroom's `SquashedGaussianTorchPolicy`). All held.

---

## Headline findings

1. **Coverage of your twelve across the entire field surveyed is essentially zero.** Fourteen libraries; the only hits are (a) jaxrl/jaxrl2's DrQ, explicitly reduced-fidelity and explicitly disclaimed by its own author; (b) Dopamine's `DrQ`/`DrQ(ε)`, which is the *discrete Atari-100k* variant, not your continuous one; (c) Acme's DrQ-v2 as an *example-script recipe*, not a packaged agent; (d) CleanRL's `ppg_procgen.py`, which is a genuine PPG. **CURL, RAD, SVEA, SGQN, SODA, IDAAC/DAAC, IBAC-SNI, CTRL, ALDA appear in none of the fourteen.**
2. **SKRL — the premise that it is the obvious robosuite choice is false as of 2026.** SKRL **removed** robosuite support in v2.0.0 (2026-04-08). And even in v1.4.3, the wrapper flattened all observations into a 1-D vector, making pixel-based robosuite impossible without rewriting it.
3. **SB3's stated fidelity position is narrower than its reputation.** Its validation target is SB2 and the gSDE paper's PyBullet table — not the original algorithm papers. The RL Zoo's own benchmark table carries the disclaimer *"this is not a quantitative benchmark as it corresponds to only one run."*
4. **On your stance, the field splits cleanly and CleanRL's JMLR paper argues your exact case** — "painless performance attribution" is your "a JOIN can silently change whose numbers you are reporting," argued from the maintainer's side. SB3 partially agrees in its own developer guide: *"The library is not meant to be modular."*
5. **On the log-prob-under-clipping bias, SB3 and SKRL do opposite things** — SB3 stores the unclipped action; SKRL stores the clipped one and takes its density under the unclipped Normal, in its own shipped manipulation examples, undocumented.

---

## 1. SKRL (Toni-SM/skrl) — highest priority

Version in clone: **2.1.0** (`skrl/version.txt`), CHANGELOG dated 2026-05-10.

### Coverage of the twelve: **none of them.**

Full torch agent roster (`skrl/agents/torch/`): `a2c, amp, cem, ddpg, ddqn, dqn, ppo, q_learning, rpo, sac, sarsa, td3, trpo`. Multi-agents (`skrl/multi_agents/torch/`): `ippo, mappo`. JAX roster is a subset; there is also a NVIDIA Warp backend.

A case-insensitive grep for `drqv2|drq-v2|drq_v2|curl|svea|sgqn|soda|idaac|ibac|alda|phasic` across `*.py|*.md|*.rst|*.yaml|*.txt` returns **zero matches**.

**SKRL is not a pixel-RL library at all.** No data augmentation of any kind exists — grep for `random_shift|random_crop|augment` across `skrl/` returns nothing. No frame-stacking. `conv2d` exists only as a layer type string in the model instantiators (`skrl/utils/model_instantiators/torch/common.py:199-220`, emitting `nn.LazyConv2d`/`nn.Conv2d`), and **no shipped example uses `Conv2d`** (`grep -rln Conv2d examples/` → empty).

### robosuite: **support existed, and was deliberately removed.**

`CHANGELOG.md:61`, under `## [2.0.0] - 2026-04-08`, `### Removed`:

> - Remove support for Bi-DexHands and robosuite environments

Same block also removes Isaac Gym, Omniverse Isaac Gym, Brax and DeepMind envs. Current `skrl/envs/wrappers/torch/` contains only `gym_envs, gymnasium_envs, isaaclab_envs, mani_skill_envs, pettingzoo_envs, playground_envs`. Robosuite was added back in `## [0.9.0] - 2023-01-13` ("Wrapper for robosuite environments", "Farama Shimmy and robosuite examples").

I retrieved the removed wrapper (`https://raw.githubusercontent.com/Toni-SM/skrl/1.4.3/skrl/envs/wrappers/torch/robosuite_envs.py`, 146 lines). Three findings that matter to you:

- **`_observation_to_tensor` flattens everything**: for an `OrderedDict` spec it does `torch.cat([...for k in sorted(spec.keys())], dim=-1).reshape(self.num_envs, -1)`. Image observations get concatenated into a 1-D vector. **Pixel-based robosuite was never possible through this wrapper.**
- **`truncated = False` is hardcoded** in `step()`, and `info = {}` discards all robosuite info. robosuite's `horizon` termination would be reported as `terminated`, corrupting time-limit bootstrapping.
- The wrapper is single-env only (`self.num_envs` reshape, no vectorization).

### Fidelity claims: **none made.**

SKRL's JMLR paper (Serrano-Muñoz et al., JMLR 24(254), 2023, `http://jmlr.org/papers/v24/23-0112.html`) abstract: *"skrl is an open-source modular library for reinforcement learning written in Python and designed with a focus on readability, simplicity, and transparency of algorithm implementations."* No reproduction claim, no benchmark numbers, no mention of robosuite.

A repo-wide grep for `reproduc|deviat|differs from|unlike the original|original paper` across `*.rst|*.md|*.py` finds **no deviation statements at all** — only bug-report boilerplate in `CONTRIBUTING.md` and `set_seed` mentions.

**Published numbers** exist, but not against papers. `docs/source/intro/examples.rst:32` and `:511` link GitHub Discussion **#32** ("Benchmark results"). That discussion benchmarks PPO/AMP/DDPG/TD3/SAC on Isaac Gym, Omniverse Isaac Gym, Isaac Orbit and PyBullet, with mean±std tables, and **compares against the `rl_games` library, not against original papers' numbers**. The author states: *"These benchmarks are a work in progress that will be updated (editing or adding new results) over time."*

Some SAC defaults also diverge from Haarnoja without comment (`skrl/agents/torch/sac/sac_cfg.py`): `batch_size: int = 64` (paper: 256), `learning_rate: float = 1e-3` (paper: 3e-4), `polyak: float = 0.005`, `gradient_steps: int = 1`. PPO defaults (`ppo_cfg.py`): `rollouts=16`, `learning_epochs=8`, `mini_batches=2`, `ratio_clip=0.2`, `grad_norm_clip=0.5`, and notably **`value_loss_scale: float = 2.5`** (Schulman's default is 0.5) and **`entropy_loss_scale: float = 0.0`**.

### Modular vs single-file: **argues explicitly for modularity.**

`README.md`: *"`skrl` is an open-source modular library for Reinforcement Learning ... designed with a focus on modularity, readability, simplicity, and transparency of algorithm implementation."* `docs/source/index.rst:53` lists *"Modularity and reusability"* as the first feature. This is the direct antithesis of your stance, and it is asserted rather than defended — no argument is offered for why sharing is safe.

### Continuous action heads

**`GaussianMixin`** (`skrl/models/torch/gaussian.py:19-24`) defaults:

```
clip_actions: bool = False
clip_mean_actions: bool = False
clip_log_std: bool = True
min_log_std: float = -20
max_log_std: float = 2
reduction: Literal["mean","sum","prod","none"] = "sum"
```

**log_std is state-independent by default.** The `gaussian_model` instantiator (`skrl/utils/model_instantiators/torch/gaussian.py:117-118`) emits:

```python
self.log_std_parameter = nn.Parameter(
    torch.full(size=(action_dim,), fill_value=initial_log_std, dtype=torch.float32),
    requires_grad=not fixed_log_std)
```

with `initial_log_std: float = 0` (→ σ=1.0 at init) and `fixed_log_std: bool = False` (`gaussian.py:30-31`).

**Squash: neither, by default.** There is **no tanh log-prob correction anywhere in SKRL** — grep for `1 - .*tanh|atanh|squash` across `skrl/` returns nothing. The shipped SAC example (`examples/gymnasium/torch_gymnasium_pendulum_sac.py:59-72`) puts `nn.Tanh()` on the *mean* and scales it (`return 2.0 * x, {"log_std": self.log_std_parameter}`), i.e. **SKRL's SAC is a tanh-mean unsquashed Gaussian** — the DrQ-v2 family, not Haarnoja's squashed Gaussian, and without DrQ-v2's truncation. This is an undocumented, substantive deviation from the SAC paper whose pseudocode `docs/source/api/agents/sac.rst` otherwise reproduces faithfully.

**The clipping bias — SKRL has it, and does not warn.** `skrl/models/torch/gaussian.py:96-105`:

```python
actions = self._g_distribution.rsample()
# clip actions
if self._g_clip_actions:
    actions = torch.clamp(actions, min=self._g_min_actions, max=self._g_max_actions)
# log of the probability density function
log_prob = self._g_distribution.log_prob(inputs.get("taken_actions", actions))
```

The action is clipped first, then its density is taken **under the unclipped Normal**. `PPO.record_transition` stores that same clipped action (`skrl/agents/torch/ppo/ppo.py:297,301`), and `_update` re-evaluates it via `taken_actions` (`:391`). The PPO ratio stays self-consistent, but the density is wrong for boundary-saturated actions (the true clipped law has atoms at the bounds), so the policy gradient is biased exactly where actions saturate.

Default `clip_actions=False` avoids this — but **SKRL's own manipulation-adjacent examples turn it on**: `examples/mani_skill/torch_mani_skill_push_cube_ppo.py:117`, `examples/mani_skill/jax_mani_skill_push_cube_ppo.py:118`, `examples/playground/{warp,jax}_playground_cartpole_balance_ppo.py:114` all pass `clip_actions=True`. No docstring or doc page mentions the bias.

### Evaluation protocol

`skrl/trainers/torch/base.py`: eval is **timestep-budgeted, not episode-budgeted** — `timesteps: int = 100000` (`:42`), no episode count anywhere. `stochastic_evaluation: bool = False` (`:60-61`, *"Whether to use actions rather than (deterministic) mean actions during evaluation"*), and `eval()` at `:305` does `actions = actions if self.cfg.stochastic_evaluation else outputs.get("mean_actions", actions)` — so **deterministic (mean) eval by default**.

Seeding: `skrl.utils.set_seed(seed=None, deterministic=False)` seeds `random`, `numpy`, `torch` and the skrl PRNG keys; in distributed runs the seed is incremented by rank. Examples default to `--seed None`.

**No CIs, no seed sweeps, no `rliable`** — grep for `rliable` returns only unrelated `time_limit_bootstrap` test parameters.

---

## 2. Stable-Baselines3 + sb3-contrib + RL Baselines3 Zoo

### Coverage of the twelve: **none of them, in any of the three.**

- SB3 (`stable_baselines3/`): `a2c, common, ddpg, dqn, her, ppo, sac, td3`. Grep for `drqv2|drq-v2|drq|curl|svea|sgqn|soda|idaac|ibac|alda|phasic|ppg` across `*.py|*.rst|*.md` → **zero matches**. Grep for `robosuite` → **zero matches**.
- sb3-contrib (`sb3_contrib/`): `ars, crossq, ppo_mask, ppo_recurrent, qrdqn, tqc, trpo`. Same greps → zero.
- RL Zoo `ALGOS` dict (`rl_zoo3/utils.py:27-41`): `a2c, ddpg, dqn, ppo, sac, td3, ars, crossq, qrdqn, tqc, trpo, ppo_lstm`. Zero robosuite mentions.

**No data augmentation in SB3 either** — grep for `random_shift|random_crop|augment|RandomShift` across `stable_baselines3/` → nothing. Pixel support is `NatureCNN` (`common/torch_layers.py:47`, the 2015 DQN CNN) plus `VecFrameStack` (`common/vec_env/vec_frame_stack.py:11`).

**Naming trap worth flagging:** the SB3-team's JAX repo **SBX** (`araffin/sbx`) ships **DroQ** = *Dropout Q-Functions for Doubly Efficient RL* (`README.md:15`, `## Note about DroQ` at `:116`, described as *"a special configuration of SAC"*). This is **not** DrQ. SBX's algorithm set is `crossq, ddpg, dqn, ppo, sac, td3, tqc` — none of the twelve.

### Fidelity claims — the strong stated position, and its actual scope

**The headline claim** (SB3 JMLR paper abstract, Raffin et al., JMLR 22(268), 2021, `https://jmlr.org/papers/volume22/20-1364/20-1364.pdf`), verbatim:

> "Stable-Baselines3 provides open-source implementations of deep reinforcement learning (RL) algorithms in Python. **The implementations have been benchmarked against reference codebases, and automated unit tests cover 95% of the code.**"

**But the reference codebase is SB2, not the papers.** `README.md:22-23` points to issues **#48** and **#49** for the performance validation. Issue #48's stated methodology: SB2 (TF) vs SB3 (PyTorch) on **PyBullet** HalfCheetah/Ant/Hopper/Walker2D, on-policy 6 seeds × 2M steps, off-policy 3-6 seeds × 1M steps, with the success criterion taken from the gSDE paper:

> "See https://paperswithcode.com/paper/generalized-state-dependent-exploration-for for the score that should be reached in 1M (off-policy) or 2M steps (on-policy)."

So the validation target is **SB2 parity plus one paper's PyBullet table** — not Haarnoja's or Schulman's published numbers. That is a meaningful narrowing of "benchmarked against reference codebases."

**SB3's "Reproducibility" doc section is about bitwise determinism, not fidelity** (`docs/guide/algos.md:63-72`): *"Completely reproducible results are not guaranteed across PyTorch releases or different platforms..."* — credited to the PyTorch docs. Do not mistake it for a reproduction claim.

### Published numbers: yes, with protocol, in the module docs

`docs/modules/ppo.md:106-152` — PyBullet, 2M steps, **6 seeds**, gSDE-paper hyperparameters, a mean±std table (e.g. `HalfCheetah | PPO Gaussian 1976 +/- 479 | PPO gSDE 2826 +/- 45`), followed by a literal **"How to replicate the results?"** section giving the exact commands:

```
python train.py --algo ppo --env $ENV_ID --eval-episodes 10 --eval-freq 10000
python scripts/all_plots.py -a ppo -e HalfCheetah Ant Hopper Walker2D -f logs/ -o logs/ppo_results
```

sb3-contrib mirrors this for every algorithm (`docs/modules/{tqc,crossq,ars,trpo,qrdqn,ppo_mask,ppo_recurrent}.md` each have `## Results` + `### How to replicate the results?` + an "Original Implementation" link).

### Documented deviations — this is where SB3 is genuinely strong

SB3 states deviations explicitly, in `:::{note}` blocks, with locators. Verbatim examples:

- `docs/guide/migration.md:42`: *"PPO is now closer to the original implementation (no clipping of the value function by default), cf PPO section below"*
- `docs/guide/migration.md`, breaking changes: *"The features extractor (CNN extractor) is shared between policy and q-networks for DDPG/SAC/TD3 and only the policy loss used to update it (much faster)"* — **note this is now stale**: `share_features_extractor: bool = False` is the current SAC default (`stable_baselines3/sac/policies.py:231`), changed in **Release 1.6.0 (2022-07-11)** (`docs/misc/changelog.md:997-998`): *"`share_features_extractor` is now set to False by default and the `net_arch=[256, 256]` (instead of `net_arch=[]` that was before)"*. The historical default is directly contrary to SAC-AE/DrQ/DrQ-v2, which update the encoder from the **critic** loss and stop-gradient the actor through it.
- `docs/modules/sac.md:43`: *"When automatically adjusting the temperature ... we optimize the logarithm of the entropy coefficient instead of the entropy coefficient itself. This is consistent with the original implementation and has proven to be more stable"*
- `docs/modules/sac.md`: *"The default policies for SAC differ a bit from others MlpPolicy: it uses ReLU instead of tanh activation, to match the original paper"*
- `docs/guide/migration.md:137-138`: *"SAC implementation matches the latest version of the original implementation: it uses two Q function networks and two target Q function networks instead of two Q function networks and one Value function network..."*
- sb3-contrib `docs/modules/crossq.md:29-31`: *"Compared to the original implementation, the default network architecture for the q-value function is `[1024, 1024]` instead of `[2048, 2048]` as it provides a good compromise between speed and performance."*
- sb3-contrib `docs/modules/crossq.md:34-36`: *"There is currently no `CnnPolicy` for using CrossQ with images."*
- sb3-contrib `docs/modules/tqc.md`, an **environment-level** deviation of the kind you care about: *"We are using the open source PyBullet environments and not the MuJoCo simulator (as done in the original paper). You can find a complete benchmark on PyBullet envs in the gSDE paper if you want to compare TQC results to those of A2C/PPO/SAC/TD3."*

### The RL Zoo's self-disclaimer — the single most citable line in this orbit

`benchmark.md` header and `README.md:114`, verbatim:

> *"NOTE: this is not a quantitative benchmark as it corresponds to only one run (cf [issue #38](https://github.com/araffin/rl-baselines-zoo/issues/38)). This benchmark is meant to check algorithm (maximal) performance, find potential bugs and also allow users to have access to pretrained agents."*

Protocol for that table: *"computed by running `python -m rl_zoo3.benchmark`: it runs the trained agent (trained on `n_timesteps`) for `eval_timesteps` and then reports the mean episode reward during this evaluation. **It uses the deterministic policy except for Atari games.**"* Columns are `mean_reward, std_reward, n_timesteps, eval_timesteps, eval_episodes` — eval is **timestep-budgeted** (~150k) with a variable resulting episode count (e.g. `a2c/AntBulletEnv-v0`: 150000 eval_timesteps → 150 episodes; `a2c/Acrobot-v1`: 149979 → 1778 episodes).

### Modular vs single-file — SB3 partly agrees with you

`docs/guide/developer.md`, verbatim:

> **"The library is not meant to be modular, although inheritance is used to reduce code duplication."**

It points to two design discussions: `hill-a/stable-baselines#576` and `#733`. (I fetched #576; it is about TF eager mode, `VecEnv` unification and parameter-naming standardization — **it contains no explicit modularity-vs-duplication or fidelity argument**. So the developer-guide sentence is the position statement; the linked issues do not substantiate it further. Marking the "argued for its position" answer as: *stated, not argued.*)

**sb3-contrib's founding rationale is a direct admission that joins are costly**, `README.md`, verbatim:

> "However sometimes these utilities were too niche to be considered for stable-baselines or **proved to be too difficult to integrate well into the existing code without creating a mess. sb3-contrib aims to fix this by not requiring the neatest code integration with existing code** and not setting limits on what is too niche: almost everything remotely useful goes!"

That is the field conceding your point in practice — they built a second repository rather than pay the integration cost.

### Continuous action heads

| | PPO / A2C | SAC / TD3 (and contrib TQC) |
|---|---|---|
| class | `DiagGaussianDistribution` (`common/distributions.py:127`) | `SquashedDiagGaussianDistribution` (`:209`) |
| log_std | **state-independent**: `nn.Parameter(th.ones(action_dim) * log_std_init)` (`:152`) | **state-dependent**: `self.log_std = nn.Linear(last_layer_dim, action_dim)` (`sac/policies.py:103`) |
| init | `log_std_init: float = 0.0` (`common/policies.py:457`) → σ=1.0 | `log_std_init: float = -3` (`sac/policies.py:59`) — used only for gSDE |
| bounds | none | `th.clamp(log_std, LOG_STD_MIN, LOG_STD_MAX)`, `LOG_STD_MIN=-20`, `LOG_STD_MAX=2` (`sac/policies.py:21-22`, `:164`) |
| squash | **no** — env-side clip | **tanh**, with correction |
| gSDE | `StateDependentNoiseDistribution` (`:429`), `log_std_init: float = -2.0` (`:522`) | same |

Squash correction (`common/distributions.py:241`), verbatim with its comment:

```python
# Squash correction (from original SAC implementation)
# this comes from the fact that tanh is bijective and differentiable
log_prob -= th.sum(th.log(1 - actions**2 + self.epsilon), dim=1)
```

`epsilon: float = 1e-6` (`:217`). `TanhBijector.inverse` clamps to `±(1-eps)` before `atanh` (`:663`). `SquashedDiagGaussianDistribution.entropy()` returns `None` — *"No analytical form, entropy needs to be estimated using -log_prob.mean()"* (`:245-247`).

**SB3 handles the clipping bias correctly and does not document it as such.** `common/on_policy_algorithm.py:206-218`:

```python
clipped_actions = actions
if isinstance(self.action_space, spaces.Box):
    if self.policy.squash_output:
        clipped_actions = self.policy.unscale_action(clipped_actions)
    else:
        # Otherwise, clip the actions to avoid out of bound error
        # as we are sampling from an unbounded Gaussian distribution
        clipped_actions = np.clip(actions, self.action_space.low, self.action_space.high)
new_obs, rewards, dones, infos = env.step(clipped_actions)
```

and then `rollout_buffer.add(self._last_obs, actions, ...)` at `:246-248` — **the unclipped action goes in the buffer**, so `log_prob` is always the density of a point the unclipped Gaussian actually generated. This is the opposite of SKRL. Also note `scale_action`/`unscale_action` (`common/policies.py:387-412`) handle non-symmetric Boxes for squashed policies, so `[-1,1]`-bounded robosuite action specs map cleanly.

**No documentation of the bias itself.** The closest prose is `docs/guide/rl_tips.md:165` — *"normalize your action space and make it symmetric if it is continuous (see potential problem below) A good practice is to rescale your actions so that they lie in [-1, 1]"* — and the "Why should I normalize the action space?" section, which is about scale mismatch with a σ=1 Gaussian, not about the density of clipped actions. **So: implemented correctly, never explained.**

### Evaluation protocol

`common/evaluation.py:12-22`: `evaluate_policy(model, env, n_eval_episodes: int = 10, deterministic: bool = True, ...)`. `EvalCallback` (`common/callbacks.py:375-379`): `n_eval_episodes: int = 5`, `deterministic: bool = True`. Vectorized eval statically divides episodes across envs *"to remove bias. See https://github.com/DLR-RM/stable-baselines3/issues/402"*. Zoo CLI default: `--eval-episodes 5`, `--seed -1` (random) (`rl_zoo3/train.py:55,62`).

**`rliable` — only in the Zoo, and only in the plotting tool.** `setup.py:28`: `plots_requires = ["seaborn", "rliable~=1.2.0", "scipy~=1.10", "pandas>=2.2"]`. `rl_zoo3/plots/plot_from_file.py:209-240` computes `aggregate_median, aggregate_iqm, aggregate_mean, aggregate_optimality_gap` via `rly.get_interval_estimates(..., reps=2000, confidence_interval_size=args.ci_size)` with `--ci-size` default `0.95`, plus performance profiles. Docs: `docs/guide/plot.md:28-61`. **This is offline analysis of logs you produce; the published `benchmark.md` table does not use it.** This is the only rliable integration in the entire SB3 family.

---

## 3. Tianshou (thu-ml/tianshou)

### Coverage of the twelve: **none of them.**

Roster (`tianshou/algorithm/modelfree/`, `imitation/`, `modelbased/`): DQN, Double/Dueling/Branching DQN, C51, Rainbow, QRDQN, IQN, FQF, PG, NPG, A2C, TRPO, PPO, DDPG, TD3, SAC, REDQ, DiscreteSAC, BCQ, CQL, TD3+BC, GAIL, ICM, PSRL. Word-boundary greps for all twelve → zero. **No augmentation or contrastive utilities anywhere** (`random.?crop|random.?shift|data.?augmentation|contrastive` → nothing).

**"SAC-from-pixels" is not covered.** Continuous SAC (`tianshou/algorithm/modelfree/sac.py`) is state-vector only; the only pixel SAC is `DiscreteSAC` on Atari (`examples/atari/atari_sac.py`). There is no continuous+pixel combination usable on robosuite.

**robosuite: zero mentions** in code, docs, or issues (`gh api search/issues?q=repo:thu-ml/tianshou+robosuite` → 0 results).

### Fidelity claims

`examples/mujoco/README.md`, verbatim:

> "By comparison to both classic literature and open source implementations (e.g., SpinningUp), Tianshou's implementations of DDPG, TD3, and SAC are roughly at-parity with or better than the best reported results for these algorithms, so you can definitely use Tianshou's benchmark for research purposes."

**Explicit deviation statement**, same file (line ~91), verbatim:

> "In offpolicy algorithms (DDPG, TD3, SAC), the shared hyperparameters are almost the same, and unless otherwise stated, hyperparameters are consistent with those used for benchmark in SpinningUp's implementations (e.g. we use batchsize 256 in DDPG/TD3/SAC while SpinningUp use 100. Minor difference also lies with `start-timesteps`, data loop method `collection_step_num_env_steps`, method to deal with/bootstrap truncated steps because of timelimit and unfinished/collecting episodes (contribute to performance improvement), etc.)."

Published numbers: pretrained agents + tfevent logs at a Tsinghua Cloud link in the README; results embedded in `docs/04_benchmarks/benchmarks.rst`. **Comparison target is SpinningUp, not the original papers.**

### Modular vs single-file: argues for modularity

`README.md`: *"Modular low-level interfaces for algorithm developers (RL researchers) that are both flexible, hackable and type-safe."* `docs/01_user_guide/02_core_abstractions.md`: *"Tianshou's architecture is built around a number of key abstractions that work together to provide a modular and flexible reinforcement learning framework... This modular design allows each component to focus on its specific responsibility while maintaining clean interfaces."* The v2 rewrite explicitly separated `Algorithm` from `Policy`, on top of shared `Collector`/`Buffer`/`Trainer`.

### Continuous action heads

`tianshou/utils/net/continuous.py`, `ContinuousActorProbabilistic`:
- `conditioned_sigma: bool = False` default → **state-independent** log_std as `sigma_param = nn.Parameter(torch.zeros(output_dim, 1))` (init 0 → σ=1.0). The MuJoCo SAC example (`examples/mujoco/mujoco_sac.py`) overrides to `conditioned_sigma=True, unbounded=True`.
- `SIGMA_MIN = -20`, `SIGMA_MAX = 2` when conditioned.
- With `unbounded=False` (class default), `mu = max_action * torch.tanh(mu)` — tanh on the **mean**. SAC instead builds the actor `unbounded=True` and tanh-squashes the **sample**, with `correct_log_prob_gaussian_tanh()` whose docstring cites *"equation 21 in the original SAC paper"*: `log_prob_correction = torch.log(1 - tanh_squashed_action.pow(2) + eps).sum(-1, keepdim=True)`. Correct and unconditional; no warning needed.

### Evaluation protocol — the best in this survey

- **First-party `rliable` integration**: `tianshou/evaluation/rliable_evaluation.py`, module docstring: *"The rliable-evaluation module provides a high-level interface to evaluate the results of an experiment with multiple runs on different seeds using the rliable library. The API is experimental and subject to change!"* Provides `EvaluationSequenceEntry.iqm` and `.iqm_confidence_interval`.
- `docs/04_benchmarks/benchmarks.rst:12`, verbatim: *"Each experiment is conducted under 5 random seeds, we report the interquartile mean (IQM) and 95% confidence intervals over these seeds."*
- `tianshou/trainer.py`: `test_step_num_episodes: int = 1` class default; `examples/mujoco/mujoco_sac.py` sets it to `num_test_envs` (default 10).
- `SACPolicy.__init__`: `deterministic_eval: bool = True` — `dist.mode` outside training, `dist.rsample()` during.

**Tianshou is the only library surveyed that ships rliable as part of the library itself and states a seed count in its benchmark docs.**

---

## 4. jaxrl / jaxrl2 / jaxrl_m (Kostrikov, Ghosh)

### Coverage

| repo | DrQ | DrQ-v2 | others of the twelve |
|---|---|---|---|
| jaxrl | **yes**, `jaxrl/agents/drq/{drq_learner,networks,augmentations}.py` | no | none |
| jaxrl2 | **yes**, `jaxrl2/agents/drq/{drq_learner,augmentations}.py` | no | none |
| jaxrl_m | no | no | none |

jaxrl also has SAC, SAC-v1, DDPG, REDQ, AWAC, BC. jaxrl2 adds IQL, Pixel-IQL, Pixel-BC. jaxrl_m ships SAC, IQL, continuous BC, discrete BC/CQL.

**The DrQ is explicitly reduced-fidelity.** `jaxrl/README.md:9`, verbatim: *"[Image Augmentation Is All You Need](https://arxiv.org/abs/2004.13649)**(only [K=1, M=1])**"*. Verified in code: `_update_jit` in `drq_learner.py` calls `batched_random_crop` exactly once on `observations` and once on `next_observations` — no averaging over K augmented targets or M augmented Q-estimates.

### The fidelity statement that matters most to you

`jaxrl/README.md:14`, verbatim (I read this line directly):

> "The goal of this repository is to provide simple and clean implementations to build research on top of. **Please do not use this repository for baseline results and use the original implementations instead ([SAC](https://github.com/rail-berkeley/softlearning/), [AWAC](https://github.com/vitchyr/rlkit/tree/master/examples/awac), [DrQ](https://github.com/denisyarats/drq)).**"

**This is the strongest field endorsement of your null hypothesis I found.** The author of DrQ-v2's lineage tells you, in the README of his own reimplementation, to go clone `denisyarats/drq` instead. Two result images exist (`learning_curves/images/results.png`, `results_drq.png`) with no seed count or CI.

**A documentation defect worth knowing about.** jaxrl2's `DrQLearner.__init__` docstring reads: *"An implementation of the version of Soft-Actor-Critic described in https://arxiv.org/abs/1812.05905"* — the plain **SAC** paper, byte-identical to `jaxrl2/agents/sac/sac_learner.py:91`. jaxrl2's DrQ agent's own docstring never cites the DrQ paper; the only signal is the file path and the `batched_random_crop` import. jaxrl2's README has no algorithm list and no fidelity prose at all.

**Confirmed not DrQ-v2:** `DrQLearner` retains SAC's stochastic policy and entropy temperature (`Temperature`, `init_temperature: float = 1.0`, `backup_entropy: bool = True`, `target_entropy = -action_dim / 2`). DrQ-v2 uses a deterministic policy with scheduled exploration noise and n-step returns — none present.

### Continuous action heads

| | jaxrl `NormalTanhPolicy` | jaxrl2 `NormalTanhPolicy` | jaxrl_m `Policy` |
|---|---|---|---|
| file | `jaxrl/networks/policies.py` | `jaxrl2/networks/normal_tanh_policy.py` | `jaxrl_m/networks.py` |
| log_std | `state_dependent_std: bool = True` (toggleable) | **always** state-dependent (toggle removed) | `state_dependent_std: bool = True` |
| bounds | `LOG_STD_MIN = -10.0`, `LOG_STD_MAX = 2.0` | `log_std_min = -20`, `log_std_max = 2` | `log_std_min = -20`, `log_std_max = 2`; SAC example overrides to `-10.0` |
| squash | `tanh_squash_distribution: bool = True`, TFP `TransformedDistribution` + `tfb.Tanh()` | `distrax.Block(distrax.Tanh(), 1)` | `tanh_squash_distribution: bool = **False**` in the class, but SAC example passes `True` |

All three use bijector frameworks that apply the log-det-Jacobian automatically — **probabilistically correct, no warning given or needed**. Note the **unremarked `-10` vs `-20` `log_std_min` inconsistency between jaxrl and jaxrl2**, same author, same lineage. jaxrl's non-default `tanh_squash_distribution=False` path tanh's only the *mean* and leaves the base distribution untransformed — materially different, and a trap.

`jaxrl_m/examples/mujoco/sac.py` additionally does `actions = jnp.clip(actions, -1, 1)` **after** the tanh sample — a redundant defensive clip on already-bounded output.

DrQ encoder detail (`jaxrl/agents/drq/networks.py`): `Encoder(features=(32,32,32,32), strides=(2,1,1,1))`, `x/255.0`, actor conv frozen via `jax.lax.stop_gradient(x)` with the comment *"We do not update conv layers with policy gradients"* — i.e. the correct SAC-AE/DrQ convention, and the opposite of SB3's historical shared-extractor default. jaxrl2 uses `PixelMultiplexer(..., stop_gradient=True)` for the actor with `D4PGEncoder` (default) or `ResNetV2Encoder((2,2,2,2))`. Augmentation is `batched_random_crop(key, imgs, padding=4)`.

### Modular vs single-file — jaxrl_m argues your case

`jaxrl_m/README.md:7-11`, verbatim (verified):

> "The primary goal of the codebase is to make ease of coding up a new algorithm: towards this goal, the primary philosophy is that
>
> **algorithms should be single-file implementations**
>
> This means that (almost) all components of the algorithm (from update rule to network choices to hyperparameter choices) are all contained in one file... This makes it easy to read and understand the algorithm, and also makes it easy to modify the algorithm to test out new ideas."

Also: *"This project serves as a 'central backbone' for an RL codebase, designed to accelerate prototyping and diagnosis of **new** algorithms (although it auxiliarily does contain reference implementations of SAC, CQL, IQL, BC)."* — i.e. explicitly not a fidelity target. jaxrl and jaxrl2 are file-per-component with **no stated position**.

### Evaluation protocol

- jaxrl: `evaluate(agent, env, num_episodes)` → `agent.sample_actions(obs, temperature=0.0)`, i.e. deterministic via temperature-zeroing. Defaults `seed = 42`, `eval_episodes = 10`, `eval_interval = 5000`; eval env seeded `seed + 42`.
- jaxrl2: `agent.eval_actions()` → `dist.mode()` — explicit deterministic. Same numeric defaults (`seed=42`, `eval_episodes=10`, `eval_interval=5000`).
- jaxrl_m: **reproducibility gap** — `run_mujoco_sac.py` does `flags.DEFINE_integer('seed', np.random.choice(1000000), 'Random seed.')`, drawing a random seed at import time unless `--seed` is passed. `eval_episodes = 10`.
- **None of the three use `rliable`**; none report CIs; none ship a multi-seed sweep script.

**robosuite: zero mentions in all three**, code, docs, and issues.

---

## 5. CleanRL + PureJaxRL — the single-file camp, and the only real PPG hit

### CleanRL (vwxyzjn/cleanrl)

**Coverage: `cleanrl/ppg_procgen.py` — a genuine PPG implementation, one of your twelve.** Also `sac_continuous_action.py`, `sac_atari.py`. Greps for `drqv2|drq|svea|sgqn|soda|idaac|daac|ibac|alda` → **zero**. `robosuite` → zero.

**It confirms your premise about the Procgen four being discrete-only.** `cleanrl/ppg_procgen.py:262`:

```python
assert isinstance(envs.single_action_space, gym.spaces.Discrete), "only discrete action space is supported"
```

with `Categorical(logits=...)` throughout (`:197, :208, :211, :454`). An independent single-file reimplementation of PPG, and it too has no continuous head.

**CleanRL's PPG docs are a model of the discipline you're practising** (`docs/rl-algorithms/ppg.md`):

- `:15`: *"The original code has multiple code level details that are not mentioned in the paper. We found these changes to be important for reproducing the results claimed by the paper."*
- `:76-90`: five numbered implementation details, each with a **permalinked line in `openai/phasic-policy-gradient` at a pinned commit** — full rollout sampling in the aux phase (`ppg.py#L173`), batch-level advantage normalization (`ppo.py#L70`), normalized network init (`impala_cnn.py#L64`), Adam eps `1e-8` vs `1e-5`, and a `gamma` mismatch in `openai/train-procgen` that they call *"technically incorrect"*.
- `:101-106`, deviations from the original: *"The original PPG code supports LSTM whereas the CleanRL code does not. The original PPG code uses separate optimizers for policy and auxiliary phase, but we do not implement this as we found it to not make too much difference. The original PPG code utilizes multiple GPUs but our implementation does not."*
- **Published numbers**, 25M steps, **3 seeds** (`benchmark/ppg.sh`: `--num-seeds 3`), comparing `ppg_procgen.py` / `ppo_procgen.py` / **their own rerun of `openai/phasic-policy-gradient`**: Starpilot `34.82 ± 13.77` / `32.47 ± 11.21` / `42.01 ± 9.59`; Bossfight `10.78 ± 1.90` / `9.63 ± 2.35` / `10.71 ± 2.05`; Bigfish `24.23 ± 10.73` / `16.80 ± 9.49` / `15.94 ± 10.80`.
- **And the reason they reran the original rather than cite the paper** (`:126`, `:144`), verbatim and directly on point for you:

  > "Note that we have run the procgen experiments using the `easy` distribution for reducing the computational cost. However, the original paper's results were condcuted with the `hard` distribution mode. For convenience, in the learning curves below, we compared the performance of the original code base (`openai/phasic-policy-gradient` the purple curve) in the `easy` distribution."
  >
  > "We also note that (Cobbe et al., 2020) used `procgen==0.9.2` and (Cobbe et al., 2021) used `procgen==0.10.4`, which also could cause performance difference. **It is for this reason, we ran our own `openai/phasic-policy-gradient` experiments on the `easy` distribution for comparison**, but this does mean it's challenging to compare our results against those in the original PPG paper."

  This is your null hypothesis, adopted by CleanRL, with the procgen-version-sensitivity caveat spelled out. (You are on `procgen 0.10.7+37b521d`.)

**Continuous head** (`cleanrl/ppo_continuous_action.py:129-141`) — **exactly your `ppg/idaac/ibac_sni/ctrl` family**:

```python
self.actor_logstd = nn.Parameter(torch.zeros(1, np.prod(envs.single_action_space.shape)))
...
probs = Normal(action_mean, action_std)
return action, probs.log_prob(action).sum(1), probs.entropy().sum(1), self.critic(x)
```

State-independent log_std, init 0.0 (σ=1.0), unsquashed Normal, and clipping done **env-side** by `gym.wrappers.ClipAction` at `:96` — so the buffered action and its log_prob are both pre-clip. No bias. This is direct prior art for the head you authored.

**Single-file argument** — `README.md:19-21`, verbatim: *"Every detail about an algorithm variant is put into a single standalone file. For example, our `ppo_atari.py` only has 340 lines of code but contains all implementation details on how PPO works with Atari games, **so it is a great reference implementation to read for folks who do not wish to read an entire modular library**."*

**The JMLR paper's argument** (Huang et al., JMLR 23(274), 2022, `https://www.jmlr.org/papers/volume23/21-1342/21-1342.pdf`) — abstract: *"CleanRL is a non-modular library... Such a paradigm significantly reduces the complexity and the lines of code (LOC) in each implemented variant, which makes them quicker and easier to understand. This paradigm gives the researchers the most fine-grained control over all aspects of the algorithm in a single file, allowing them to prototype novel features quickly. Despite having succinct implementations, CleanRL's codebase is thoroughly documented and benchmarked to ensure performance is on par with reputable sources."*

Introduction: *"Many of them have adopted good modular designs and fostered vibrant development communities. Nevertheless, understanding all the implementation details of an algorithm remains difficult because these details are spread to different modules. However, understanding these implementation details is essential because they could significantly affect performance (Engstrom et al., 2020)."* and *"running the PPO model in Atari games using Stable Baselines 3 (SB3) with a debugger involves jumping back and forth between 20 python files that comprise 4000+ LOC (Raffin et al., 2021)."*

**Section 2, "Painless performance attribution" — the passage closest to your stance:**

> "If a new version of our algorithm has obtained a higher performance, we know the exact single file which is responsible for the performance improvement. To attribute the performance improvement, we can simply do a filediff between the current and past versions, and every line of code change is made explicit to us. In comparison, two different versions of modular RL libraries usually involve dozens of file changes, which are more difficult to compare."

That is "any JOIN carries a burden of proof because it can silently change whose numbers you are reporting," argued from the maintainer's side rather than the auditor's. **CleanRL is your strongest citation for the design decision.**

### PureJaxRL (luchris429/purejaxrl)

**Coverage: none.** Files: `dqn.py, ppo.py, ppo_continuous_action.py, ppo_minigrid.py, ppo_rnn.py, dpo_continuous_action.py, experimental/s5/ppo_s5.py`. `dpo_continuous_action.py` is **Discovered Policy Optimisation** (NeurIPS'22), **not PPG** — a naming trap. No PPG/phasic in source. robosuite: zero.

**Code philosophy** (`README.md:35-37`, verified verbatim): *"PureJaxRL is inspired by [CleanRL](https://github.com/vwxyzjn/cleanrl), providing high-quality single-file implementations with research-friendly features. **Like CleanRL, this is not a modular library and is not meant to be imported.** The repository focuses on simplicity and clarity in its implementations..."*

**Fidelity:** the blog post (`https://chrislu.page/blog/meta-disco/`) claims *"We achieve nearly identical results given the same hyperparameters and number of frames"* against CleanRL's PyTorch baseline, alongside the 1000× speed claim. `UNVERIFIED` at the plot level — relayed from a WebFetch summary, not independently replotted.

**Continuous head** (`purejaxrl/ppo_continuous_action.py:41`): `actor_logtstd = self.param("log_std", nn.initializers.zeros, (self.action_dim,))` → `distrax.MultivariateNormalDiag(actor_mean, jnp.exp(actor_logtstd))`. **State-independent**, init 0 (σ=1.0), **no tanh**. Clipping is env-side via `ClipAction` (`purejaxrl/wrappers.py:174-183`) — but note `jnp.clip(action, self.low, self.high)` with the correct action-space-bounds version **commented out at `:182`** and a `# TODO`. `log_prob` is on the pre-clip action, so no bias, but the bounds are effectively hardcoded. No eval harness; metrics logged inline from `returned_episode_returns`; no `rliable`.

---

## 6. Brax (google/brax)

**Coverage: none.** `brax/training/agents/` = `apg, ars, bc, es, ppo, sac`. robosuite: zero. `rliable`: zero.

**Continuous head** (`brax/training/distribution.py`, `brax/training/agents/ppo/networks.py`): default `distribution_type='tanh_normal'` → `NormalTanhDistribution(event_size, min_std=0.001, var_scale=1)`. `param_size = 2 * event_size` — **both loc and scale are state-dependent** from one forward pass. `scale = (jax.nn.softplus(raw_scale) + min_std) * var_scale` (softplus, not exp).

**Brax has the most explicit engineering comment on the squash/log-prob problem** of any library here, verbatim:

> "We apply tanh to gaussian actions to bound them. Normally we would use TransformedDistribution to automatically apply tanh to the distribution. We can't do it here because of tanh saturation which would make log_prob computations impossible. Instead, most of the code operate on pre-tanh actions and we take the postprocessor jacobian into account in log_prob computations."

`log_prob()` subtracts `self._postprocessor.forward_log_det_jacobian(actions)` — correct. An alternative `distribution_type='normal'` (no squash, identity postprocessor) exists but is not the default.

**Eval:** PPO and SAC `train.py` both default `num_eval_envs: int = 128`, **`deterministic_eval: bool = False`** (stochastic eval by default — one episode per env), single `seed: int = 0`.

**Context worth flagging:** `README.md` top warning: *"Only `brax/training` is actively being maintained as of 0.13.0. Instead of `brax/envs`, users should use MuJoCo Playground... We may repurpose `brax` purely as an RL library in the future."* Brax's own envs are being deprecated — consistent with SKRL 2.0.0 dropping Brax in favor of MuJoCo Playground. Fidelity: the Brax paper (arXiv:2106.13281) reports remaining differences vs MuJoCo attributed to contact-physics and actuation-model differences — `UNVERIFIED` at exact-wording level (WebSearch snippet only, WebFetch on the abstract page did not surface the sentence).

---

## 7. Acme (google-deepmind/acme)

**Coverage: SAC only as a first-class agent. DrQ-v2 exists only as an example recipe.** I verified this myself:

- `acme/agents/jax/` = `ail, ars, bc, bve, cql, crr, d4pg, dqn, impala, lfd, mbop, mpo, multiagent, ppo, pwil, r2d2, rnd, sac, sqil, td3, value_dice, wpo`. **No `drq`, `drqv2`, or `curl` directory** (confirmed by `ls`).
- `find . -iname '*drq*'` returns exactly one file: **`examples/tf/control_suite/lp_dmpo_pixels_drqv2.py`**. The CNN is `class DrQTorso` at **`acme/tf/networks/vision.py:185`** — *"DrQ Torso inspired by the second DrQ paper [Yarats et al., 2021]"*. So Acme's DrQ-v2 is **TF DMPO + DrQ visual torso + `acme/datasets/image_augmentation.py`, assembled in an example script** — not a packaged agent, not JAX, and not in `docs/user/agents.md` (whose continuous-control list is D4PG, TD3, SAC, MPO, PPO, DMPO, MO-MPO).
- CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC, IBAC, CTRL, ALDA: **zero hits**. `robosuite`: **zero**. `rliable`: **zero**.
- `UNVERIFIED`: whether an older release ever had `agents/jax/drqv2/`. `gh api search/commits -f q='drqv2 repo:google-deepmind/acme'` returned `total_count: 0` (inconclusive — shallow clone, and that endpoint is unreliable for commit-message search).

**Fidelity:** Acme paper arXiv:2006.00979. Abstract-level text obtained: *"These implementations serve both as a validation of our design decisions as well as an important contribution to reproducibility in RL research."* **`UNVERIFIED`: the benchmark tables/numbers inside the paper body** — WebFetch returned only abstract-level text; a direct PDF read is needed before repeating "Acme published a benchmark paper with numbers."

**Modularity:** `README.md`, verbatim: *"Acme is a library of reinforcement learning (RL) building blocks that strives to expose simple, efficient, and readable agents. These agents first and foremost serve both as reference implementations as well as providing strong baselines for algorithm performance... the building blocks of Acme are designed in such a way that the agents can be run at multiple scales (e.g. single-stream vs. distributed agents)."* Fully shared actor/learner/builder/Reverb infrastructure — the most joined design in this survey alongside AgileRL.

**Continuous head:** SAC uses `networks_lib.NormalTanhDistribution` (`acme/agents/jax/sac/networks.py:105`, defined `acme/jax/networks/distributional.py:237-265`). Two separate `hk.Linear` heads → **state-dependent** scale via `scale = jax.nn.softplus(scale) + self._min_scale`, `min_scale: float = 1e-3`. Not a log_std at all. `MultivariateNormalDiagHead` (`:268+`) with `init_scale=0.3, min_scale=1e-6, w_init=VarianceScaling(1e-4)` is used by other agents.

**Acme's `TanhTransformedDistribution` (`distributional.py:179-218`) is the most sophisticated treatment of the clipping/saturation problem found anywhere in this survey** — `threshold=.999`, and rather than just clipping it computes closed-form tail masses:

```python
def log_prob(self, event):
    event = jnp.clip(event, -self._threshold, self._threshold)
    return jnp.where(event <= -self._threshold, self._log_prob_left,
        jnp.where(event >= self._threshold, self._log_prob_right, super().log_prob(event)))
```

with a comment describing `_log_prob_left`/`_log_prob_right` as *"the log of the average probability distribution outside the clipping range"*, built from `log_cdf`/`log_survival_function`. **If you want a citation for "we thought about the density of clipped/saturated actions," this is it** — but note it lives in code comments, not documentation.

**Eval:** `examples/baselines/rl_continuous/run_sac.py`: `seed=0`, `eval_every=50_000` steps, `evaluation_episodes=10`. Deterministic switch verified: `acme/jax/experiments/run_experiment.py:156` builds `make_policy(..., evaluation=True)`; `acme/agents/jax/sac/networks.py:142-143` gives `sample=lambda params, key: params.sample(seed=key)` (train) vs `sample_eval=lambda params, key: params.mode()` (eval).

---

## 8. Dopamine (google/dopamine)

**Coverage: SAC, plus a `DrQ` that is not your DrQ.**

- **SAC**: `dopamine/jax/agents/sac/sac_agent.py`, `configs/sac.gin`. **Pixel variant exists**: `dopamine/labs/sac_from_pixels/` (`continuous_networks.py`, `deepmind_control_lib.py`, `sac_pixels.gin`) — cites Yarats et al. 2019 (SAC+AE), DrQ's predecessor.
- **`DrQ` / `DrQ(ε)`**: `dopamine/labs/atari_100k/configs/{DrQ,DrQ_eps}.gin`, `train.py:40` (`AGENTS = ['DER','DrQ','OTRainbow','DrQ_eps','SPR']`), augmentation at `atari_100k_rainbow_agent.py:107` (`def drq_image_augmentation(key, obs, img_pad=4)`). Built on `JaxFullRainbowAgent` — **discrete Atari-100k, not the continuous SAC-based DrQ you run**. Flag as a false-positive risk if anyone counts library coverage by name.
- **DrQ-v2, CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC, IBAC-SNI, CTRL, ALDA: zero hits.** Native roster is DQN/C51/Rainbow/IQN/SAC/PPO. `robosuite`: zero.

**Design philosophy — the argued position** (`README.md:11-24`, verbatim):

> "Dopamine is a research framework for fast prototyping of reinforcement learning algorithms. It aims to fill the need for a **small, easily grokked codebase** in which users can freely experiment with wild ideas (speculative research).
>
> Our design principles are:
> * *Easy experimentation*: Make it easy for new users to run benchmark experiments.
> * *Flexible development*: Make it easy for new users to try out research ideas.
> * *Compact and reliable*: Provide implementations for a few, battle-tested algorithms.
> * *Reproducible*: Facilitate reproducibility in results. In particular, our setup follows the recommendations given by Machado et al. (2018)."

Structure is one small forkable file per agent (`dopamine/jax/agents/<algo>/<algo>_agent.py`), closer to your duplication-friendly null than to Acme's shared infrastructure. Machado et al. 2018 is "Revisiting the ALE," the source of the sticky-actions eval convention.

**Published numbers, with a self-declared deviation** — `baselines/atari/` and `baselines/mujoco/` (raw JSON + `plots.html`). `baselines/mujoco/README.md`, verbatim:

> "We currently only support SAC for mujoco. Also, **the baseline data is reported using the training regime, not evaluation. For SAC, that means we are using sampled actions, not the mean action.**"

i.e. their published SAC curves are stochastic training returns, not deterministic eval — exactly the kind of protocol disclosure worth imitating.

**Continuous head** (`dopamine/jax/continuous_networks.py:127-185`, `ActorNetwork`): single `nn.Dense(action_dim*2)` → state-dependent loc+scale, **no min/max clamp on scale**, `scale_diag = jnp.exp(scale_diag)`, `tfd.MultivariateNormalDiag`, tanh squash via TFP `TransformedDistribution` (automatic Jacobian). The only clip is inside `_Tanh._inverse` for `arctanh` stability, commented *"We perform clipping in the _inverse function, as is done in TF-Agents"* — a provenance note, not a bias warning.

**Eval:** `sac.gin`: `evaluation_steps=10_000` agent steps per iteration (**step-budgeted**), `num_iterations=3_200`, `max_steps_per_episode=1_000`, and `SACAgent.seed=None  # Seed with the current time` — **no fixed default seed**. Atari-100k lab: `MaxEpisodeEvalRunner`, `num_eval_episodes=100`, `max_noops=30`.

**The rliable connection is real and explicit.** `dopamine/labs/atari_100k/README.md:13-15`, verbatim: *"For evaluation, we report scores averaged over 100 episodes after training. For more details about evaluation protocols, refer to the [rliable library](https://github.com/google-research/rliable)"*, citing Agarwal, Schwarzer, Castro, Courville & Bellemare 2021, "Deep RL at the Edge of the Statistical Precipice." Castro and Bellemare are Dopamine authors — direct team lineage. rliable is referenced as an external tool, not vendored.

---

## 9. Meta Pearl (facebookresearch/Pearl)

**Coverage: none.** `pearl/policy_learners/sequential_decision_making/` = `bootstrapped_dqn, ddpg, deep_q_learning, deep_sarsa, deep_td_learning, double_dqn, implicit_q_learning, ppo, quantile_regression_deep_q_learning, quantile_regression_deep_td_learning, reinforce, soft_actor_critic, soft_actor_critic_continuous, tabular_q_learning, td3`. Grep for all twelve → zero. `robosuite` → zero. `rliable` → zero. Pearl is a production/applied library (contextual bandits, offline RL, safety modules); the absence matches its scope. Generic CNN scaffolding exists (`CNNValueNetwork`/`CNNActorNetwork` in `pearl/neural_networks/common/`, Atari wrappers in `pearl/user_envs/wrappers/`) but none of the twelve are built on it.

**Modularity, argued** — `README.md`, "Design and Features", verbatim: *"Pearl was built with a modular design so that industry practitioners or academic researchers can select any subset and flexibly combine features below to construct a Pearl agent customized for their specific use cases."* Its comparison table even claims `Agent Modularity: Pearl ✅, Dopamine ❌`.

**Continuous head** — `GaussianActorNetwork` (`pearl/neural_networks/sequential_decision_making/actor_networks.py:489+`). **State-dependent** log_std (`self.fc_std = nn.Linear(...)`), `_log_std_min = -5`, `_log_std_max = 2`, and a smooth tanh-rescale instead of clamping — with the naive clamp **commented out at `:542`** and a candid comment: *"alternate to standard clamping; not sure if it makes a difference but still"*:

```python
log_std = torch.tanh(log_std)
log_std = self._log_std_min + 0.5 * (self._log_std_max - self._log_std_min) * (log_std + 1)
```

Tanh squash with the correction **including the action-scaling factor** (`:578-581`), which most implementations omit:

```python
log_prob = normal.log_prob(sample)
log_prob -= torch.log(self._action_bound * (1 - normalized_action.pow(2)) + epsilon)
```

A post-tanh clamp line is present but commented out (`:575`).

**Fidelity:** no reproducibility statement or literature-benchmark table found. `benchmark.py`/`benchmark_config.py` is an internal sanity harness on classic-control + state-based MuJoCo (`HalfCheetah/Ant/Hopper/Walker2d-v4`), `num_runs=4`, `set_seed(run_idx)`. `UNVERIFIED`: whether the standard benchmark driver uses the `exploit: bool` deterministic flag — `online_learning` exposes it but `benchmark.py` never references it. `UNVERIFIED`: contents of the linked arXiv paper (not fetched).

---

## 10. Mushroom-RL (MushroomRL/mushroom-rl)

**Coverage: none.** `mushroom_rl/algorithms/actor_critic/deep_actor_critic/` = `a2c, ddpg, ppo, ppo_bptt, ppo_rudin, sac, td3, trpo`; DQN family under `algorithms/value/dqn/`. Greps for the twelve produce only **false positives** on `data.ctrl` (MuJoCo actuator arrays, `mushroom_rl/environments/mujoco.py:129`, `mujoco_envs/ball_in_a_cup.py:91`) — worth knowing if you grep for "CTRL" mechanically. `robosuite` → zero. `rliable` → zero.

**Minimal pixel support:** exactly one CNN in the repo, `mushroom_rl/approximators/parametric/networks/atari_network.py` (`AtariNetwork`/`AtariFeatureNetwork`, 3-conv, `state.float()/255.`, Xavier-uniform), wired only to the DQN family — **not to SAC or any actor-critic**. So no SAC-from-pixels.

**Continuous head:** `SAC` (`.../sac.py:27`) takes `log_std_min=-20, log_std_max=2` and separate `actor_mu_params`/`actor_sigma_params` approximators → **state-dependent** log_std. Policy is `SquashedGaussianTorchPolicy` (**`mushroom_rl/policy/torch_policy.py:265`**), whose class docstring reads: *"Torch policy implementing a Gaussian policy squashed by a tanh and remapped to a bounded action range, as used by the Soft Actor-Critic algorithm. The squashing and the corresponding change-of-variables are handled by the..."* — `TransformedDistribution(TanhTransform(cache_size=1) + AffineTransform)`, `self._eps = 1e-6` (`:294`). `draw_with_log_prob` uses `rsample_and_log_prob` to avoid inverting the tanh near the boundaries. Correct, and deliberately so.

**Modularity, stated not argued** — `README.rst:28-33`, verbatim: *"MushroomRL is a Python Reinforcement Learning (RL) library whose modularity allows to easily use well-known Python libraries for tensor computation (e.g. PyTorch, Tensorflow) and RL benchmarks (e.g. Gymnasium, PyBullet, Deepmind Control Suite)..."* No "why modular" section found.

**Fidelity:** JMLR paper D'Eramo, Tateo, Bonarini, Restelli, Peters, "MushroomRL: Simplifying Reinforcement Learning Research," JMLR 22(131):1-5, 2021 (arXiv:2001.01102), reportedly accompanied by a separate benchmarking suite. **`UNVERIFIED` at exact-quote level** (search summary only; no in-repo benchmark-numbers doc found under `docs/source/*.rst`). **`UNVERIFIED`: evaluation protocol** — no canonical eval script/doc located within budget.

---

## 11. garage (rlworkgroup/garage)

**Coverage: none.** README algorithm table: CEM, CMA-ES, REINFORCE, DDPG, DQN, DDQN, ERWR, NPO, PPO, REPS, TD3, TNPG, TRPO, MAML, RL2, PEARL, SAC, MTSAC, MTPPO, MTTRPO, Task Embedding, BC. Grep for the twelve across `src/` → zero. `robosuite` → zero. `rliable` → zero. Has vanilla `SAC` (`src/garage/torch/algos/sac.py`) but no CNN stochastic policy paired with it, so no SAC-from-pixels.

**garage's stance is the most interesting middle position in this survey** — fully modular, but explicitly treating that as a risk requiring a standing counter-measure. `README.md`, "## Testing", verbatim:

> "The most important feature of garage is its comprehensive automated unit test and benchmarking suite... **Acceptance Testing:** Any commit which might change the performance of an algorithm is subjected to comprehensive benchmarks on the relevant algorithms before it is merged. **Benchmarks and Monitoring:** We benchmark the full suite of algorithms against their relevant benchmarks and widely-used implementations regularly, to detect regressions and improvements we may have missed."

and from Credits: *"The garage project is grateful for the contributions of the original rllab authors, and hopes to continue advancing the state of reproducibility in RL research in the same spirit."*

**This is a burden of proof on every JOIN, discharged by mandatory CI benchmarking rather than by repo separation.** It is the field's clearest alternative answer to your design question. Note however that the benchmark harness (`benchmarks/src/garage_benchmarks/benchmark_algos.py`) compares garage's own PyTorch vs TF implementations against each other on `MuJoCo1M_ENV_SET`, and no plots/numbers are checked into the repo (`docs/user/benchmarking.md` documents how to run them; output goes to `./data/local/benchmarks/`). **Documents a reproducibility policy; does not publish numbers in-repo.**

**Continuous heads** (`src/garage/torch/{policies,modules}/`):
- `GaussianMLPPolicy` → `GaussianMLPModule`: **state-independent** `torch.nn.Parameter(log_std)`, `init_std=1.0`, `min_std=1e-6`, `max_std=None`, `std_parameterization='exp'`, no squash. Used by PPO/TRPO/VPG.
- `GaussianMLPIndependentStdModule`: mean and log_std from **two fully separate MLPs** (state-dependent).
- `TanhGaussianMLPPolicy` → `GaussianMLPTwoHeadedModule` + `TanhNormal`: shared trunk, two heads (state-dependent), `init_std=1.0`, `min_std=np.exp(-20.)`, `max_std=np.exp(2.)`. Used by SAC/MTSAC.

**garage carries the only explicit prose warning about log-prob accuracy under squashing** I found, `src/garage/torch/distributions/tanh_normal.py:37-43`, verbatim (verified):

> "Note: when pre_tanh_value is None, an estimate is made of what the value is. **This leads to a worse estimation of the log_prob.** If the value being used is collected from functions like `sample` and `rsample`, one can instead use functions like `sample_return_pre_tanh_value` or `rsample_return_pre_tanh_value`"

**Eval:** `src/garage/torch/algos/sac.py` ~`:121`: `use_deterministic_evaluation=True` by default; `_evaluate_policy` → `obtain_evaluation_episodes(..., num_eps=self._num_evaluation_episodes, deterministic=self._use_deterministic_evaluation)`.

---

## 12. AgileRL (AgileRL/AgileRL)

**Coverage: none**, and notably **no SAC at all**. `agilerl/algorithms/`: `bc_lm, cispo, cqn, ddpg, dpo, dqn_rainbow, dqn, grpo, gspo, ilql, ippo, maddpg, matd3, neural_ts_bandit, neural_ucb_bandit, ppo_llm, ppo, reinforce_llm, sft, td3`. **`dpo.py` here is Direct Preference Optimization (LLM/RLHF)** — a naming collision with PureJaxRL's Discovered Policy Optimisation. `robosuite` → zero. `rliable` → zero.

**Most joined design in the survey**, and never defended: a shared `EvolvableModule`/`EvolvableNetwork`/`EvolvableDistribution` stack (`agilerl/modules/`, `agilerl/networks/`) plus shared `components/{replay_buffer,rollout_buffer}.py` underlies all 20 algorithms, from PPO to MADDPG. Justified purely on engineering/HPO grounds (population-based evolvable networks), never on fidelity grounds. **A useful example of the pattern you're pushing back against, precisely because it never has to defend the choice.**

**Fidelity:** README benchmarks are about LLM multi-turn training (CISPO vs ART/TRL on GEM Sudoku-Hard) and evolutionary-HPO efficiency (AgileRL vs Optuna) — **no published numbers vs original papers for the continuous-control algorithms**, no reproducibility statement.

**Continuous head:** `EvolvableDistribution` (`agilerl/networks/distributions.py`): for `spaces.Box`, `log_std = torch.nn.Parameter(torch.ones(1, action_dim) * action_std_init)`, `action_std_init: float = 0.0` → **state-independent**, σ=1.0 — same pattern as garage's `GaussianMLPModule`, PureJaxRL, CleanRL, and your Procgen four. `squash_output: bool = False` by default; when False, `np.clip(action_np, action_space.low, action_space.high)` (`agilerl/algorithms/ppo.py` ~`:676`).

**A finding flagged as needing your own confirmation:** `distributions.py` ~`:236` comments that `log_prob` *"Handles squashing correction internally for Box space"*, but tracing `TorchDistribution.log_prob()` → `log_prob_from_space()` → `_log_prob_box()` (`agilerl/utils/torch_utils.py:515-526`) → `log_prob_continuous(mu, log_std, action)` (`:231-250`) yields a plain diagonal-Gaussian log-density with **no tanh Jacobian term and no `squash_output` parameter in the chain**. Corroborating hint: `ppo.py` carries `# Use -log_prob as entropy when squashing output in continuous action spaces`, a workaround implying `entropy_continuous()` is invalid under squashing. **This is a code-trace finding from one read-through, not confirmed by running the code** — verify with a runtime check before repeating it as fact.

**Eval:** `EvolvableAlgorithm.test()` abstract (`agilerl/algorithms/core/base.py:571`); PPO's implementation (`ppo.py:1093`) defaults to `loop: int = 3` test episodes, returns the mean, and uses **stochastic** sampling (`get_action()` always `sample=True`; no deterministic path found for PPO).

---

## Cross-cutting summary tables

### A. Coverage of the twelve

| Library | Any of the twelve? | Detail |
|---|---|---|
| SKRL | **none** | Not a pixel-RL library at all; no augmentation, no CNN examples |
| SB3 / contrib / Zoo / SBX | **none** | SBX's **DroQ** ≠ DrQ |
| Tianshou | **none** | No augmentation utilities; pixel SAC is discrete-only |
| jaxrl | **DrQ** (K=1,M=1) | `jaxrl/agents/drq/`; author says don't use for baselines |
| jaxrl2 | **DrQ** (K=1,M=1) | `jaxrl2/agents/drq/`; docstring mislabels it as SAC |
| jaxrl_m | none | Has augmentation building blocks, no pixel RL agent |
| **CleanRL** | **PPG** | `cleanrl/ppg_procgen.py`, discrete-only, benchmarked vs original |
| PureJaxRL | none | `dpo_continuous_action.py` is DPO, **not** PPG |
| Brax | none | |
| Acme | DrQ-v2 as an **example recipe** | `examples/tf/control_suite/lp_dmpo_pixels_drqv2.py` + `DrQTorso` |
| Dopamine | **DrQ/DrQ(ε)**, *discrete Atari-100k* | plus `labs/sac_from_pixels/` (SAC+AE lineage) |
| Meta Pearl | none | |
| Mushroom-RL | none | `data.ctrl` is a grep false positive |
| garage | none | |
| AgileRL | none | no SAC either |

**CURL, RAD, SVEA, SGQN, SODA, IDAAC/DAAC, IBAC-SNI, CTRL, ALDA: zero implementations across all fourteen libraries.** For nine of your twelve, no library in the field is even a candidate substitute for the original repo.

### B. Continuous action heads

| Library | on-policy log_std | off-policy log_std | squash | clipping bias handled? |
|---|---|---|---|---|
| SKRL | state-indep, `nn.Parameter`, init 0 | same mixin | **none** (tanh on mean in examples) | **No** — clipped action's density under unclipped Normal; examples enable it |
| SB3 | state-indep, init `0.0` | state-dep `nn.Linear`, `[-20,2]` | tanh w/ `log(1-a²+1e-6)` | **Yes** — unclipped action stored in buffer |
| Tianshou | state-indep `nn.Parameter(zeros)` (opt. conditioned) | state-dep, `[-20,2]` | tanh w/ eq.-21 correction | Yes |
| jaxrl / jaxrl2 / jaxrl_m | — | state-dep, `[-10,2]` / `[-20,2]` | tanh via TFP/distrax bijector | Yes (bijector) |
| CleanRL | state-indep `nn.Parameter(zeros)` | state-dep | none (PPO) / tanh (SAC) | Yes — env-side `ClipAction` |
| PureJaxRL | state-indep, `nn.initializers.zeros` | — | **none**, env-side clip | Yes (pre-clip log_prob); bounds hardcoded |
| Brax | state-dep (softplus, `min_std=1e-3`) | same | tanh w/ explicit Jacobian | Yes, with an explicit design comment |
| Acme | `init_scale=0.3, min_scale=1e-6` | state-dep softplus | tanh, **closed-form tail correction at `threshold=.999`** | Yes, most sophisticated |
| Dopamine | — | state-dep, **no clamp** | tanh via TFP bijector | Yes |
| Pearl | — | state-dep, tanh-rescaled to `[-5,2]` | tanh w/ correction incl. action-bound factor | Yes |
| Mushroom-RL | — | state-dep, `[-20,2]` | tanh via `TransformedDistribution` | Yes |
| garage | state-indep `nn.Parameter`, `init_std=1.0` | state-dep two-headed, `[e⁻²⁰,e²]` | `TanhNormal` | Yes, **with the only prose warning** |
| AgileRL | state-indep, init `0.0` | — | optional, default off | **Possibly not** — flagged, needs runtime check |

Two observations. First: **state-independent `nn.Parameter` log_std initialized to zero is the universal on-policy convention** (SB3, Tianshou, CleanRL, PureJaxRL, garage, AgileRL, SKRL) — your `ppg/idaac/ibac_sni/ctrl` head has unanimous field precedent. Second: **SKRL is the only library that gets the clipping bias wrong**, and it does so in its own shipped manipulation examples.

### C. Evaluation protocol

| Library | budget | policy | seeds stated | CIs | rliable |
|---|---|---|---|---|---|
| SKRL | 100k **timesteps** | deterministic (mean) | none | no | no |
| SB3 | 10 episodes (`evaluate_policy`), 5 (`EvalCallback`) | `deterministic=True` | 6 (on-pol) / 3-6 (off-pol) in docs | ±std | **Zoo plotting only**, IQM/median/mean/opt-gap, 2000 reps, 95% |
| Tianshou | 10 episodes (MuJoCo examples) | `deterministic_eval=True` | **5, stated in docs** | **95% CI** | **first-party module** |
| jaxrl/jaxrl2 | 10 episodes | deterministic | seed=42 | no | no |
| jaxrl_m | 10 episodes | deterministic (temp=0) | **random by default** | no | no |
| CleanRL | inline training returns | stochastic | **3** (`benchmark/ppg.sh`) | ±std | no |
| Brax | 128 eval envs × 1 ep | **stochastic** (`deterministic_eval=False`) | seed=0 | no | no |
| Acme | 10 episodes, every 50k | deterministic (`params.mode()`) | seed=0 | no | no |
| Dopamine | 10k **agent steps** (MuJoCo); 100 episodes (Atari-100k) | **stochastic** in published MuJoCo baselines | **`seed=None`** | no | **cited, external** |
| Pearl | — | `exploit` flag exists, unused in benchmark | `num_runs=4` | no | no |
| garage | `num_evaluation_episodes` | `use_deterministic_evaluation=True` | — | no | no |
| AgileRL | 3 episodes | **stochastic** | — | no | no |
| Mushroom-RL | `UNVERIFIED` | `UNVERIFIED` | — | no | no |

**Only Tianshou states a seed count and CI method in its own benchmark documentation.** rliable appears in exactly three places field-wide: Tianshou's library, the RL Zoo's plotting tool, and Dopamine's Atari-100k README as an external pointer.

### D. Where the field stands on your "duplication is free, joins carry a burden of proof"

| Position | Who | Grounds |
|---|---|---|
| **Agrees, argued** | **CleanRL** (JMLR 2022), **PureJaxRL**, **jaxrl_m** | "Painless performance attribution": a filediff of one file vs dozens across modules; implementation details spread across modules become invisible and they materially affect performance (citing Engstrom et al. 2020) |
| **Agrees, in practice** | **sb3-contrib** | Created a second repo because integration "proved to be too difficult... without creating a mess" |
| **Agrees, partially stated** | **SB3** | *"The library is not meant to be modular, although inheritance is used to reduce code duplication"* — stated in `docs/guide/developer.md`, not argued |
| **Agrees, in spirit** | **Dopamine** | "small, easily grokked codebase", "a few, battle-tested algorithms", one forkable file per agent |
| **Agrees, tacitly** | **jaxrl** | Tells you to use the original repos for baseline results |
| **Middle: modular + mandatory proof** | **garage** | Modular, but any commit that "might change the performance of an algorithm" must pass benchmarks before merge — a continuous, automated burden of proof |
| **Disagrees, argued** | **SKRL**, **Tianshou**, **Meta Pearl** | Modularity/reusability asserted as a headline design virtue; Pearl even markets it as a differentiator vs Dopamine |
| **Disagrees, unargued** | **Acme**, **Brax**, **Mushroom-RL**, **AgileRL** | Conventional shared-infrastructure library design; never has to defend the choice |

### E. robosuite

**No library in this survey currently ships robosuite support.** SKRL had it and removed it in 2.0.0; nobody else ever mentioned it in code, docs, or issues.

What is technically possible, verified against the actual wrapper source:

- **robosuite 1.4.0** (`.../solve-vla-rl-dz/.venv/.../robosuite/wrappers/gym_wrapper.py`, `__version__ = "1.4.0"`) — `GymWrapper` imports from legacy **`gym`**, `reset()` returns obs only, `step()` returns the **4-tuple**, and `_flatten_obs` does `np.concatenate([np.array(obs_dict[key]).flatten() ...])`. **Image observations are flattened into a 1-D vector.** No library can do pixel RL through this without replacing the wrapper.
- **robosuite master (1.5+)** (fetched `raw.githubusercontent.com/ARISE-Initiative/robosuite/master/.../gym_wrapper.py`) — prefers **gymnasium** (falls back to `gym>=0.26.0`), signature is `GymWrapper(env, keys=None, flatten_obs=True)`, and with `flatten_obs=False` you get `spaces.Dict({key: get_box_space(obs[key]) ...})`, `reset(seed=None, options=None)` → `(obs, info)`, `step()` → the gymnasium 5-tuple. **This makes SB3's `MultiInputPolicy` (Dict obs + `NatureCNN`) a technically viable path to pixel-based robosuite.**
- **But `step()` returns `truncated` hardcoded to `False`** (`return obs, reward, terminated, False, info`). robosuite's `horizon` termination surfaces as `terminated`. Any library that bootstraps on truncation — SB3, SKRL, Tianshou all do — will silently mis-handle time limits unless you add a `TimeLimit` wrapper. The removed SKRL 1.4.3 wrapper had the identical `truncated = False` defect.

---

## What I did not get to, and what remains UNVERIFIED

- **Acme's benchmark numbers.** The paper (arXiv:2006.00979) abstract was fetched but not the body. Do not repeat "Acme published a benchmark paper with numbers" without a direct PDF read.
- **Whether an older Acme release had a JAX `drqv2` agent directory.** `gh api search/commits` returned `total_count: 0`, which is inconclusive on a shallow clone.
- **Mushroom-RL's evaluation protocol** — no canonical eval script/doc located; and its JMLR paper's benchmark claims are from a search summary, not the primary PDF.
- **Meta Pearl's benchmark determinism** — `online_learning` exposes `exploit: bool` but `benchmark.py` never references it.
- **Brax's exact MuJoCo-comparison wording** in arXiv:2106.13281 — substance corroborated by a search snippet, exact sentence not extracted.
- **PureJaxRL's "nearly identical results"** — relayed from a WebFetch summary of the blog post, not independently replotted.
- **AgileRL's `log_prob` squash discrepancy** — a code-trace finding needing a runtime check, not a confirmed bug.
- **garage's TensorFlow-side policies** (`src/garage/tf/`) were not examined at the same depth as the PyTorch side.
- **Not attempted anywhere:** actually running any library against a robosuite env. All robosuite findings above are source-reading plus grep-for-mentions.
- **Libraries not covered at all:** `rl_games` (Isaac Lab's default, and SKRL's benchmark comparator — likely worth a follow-up given its Isaac/manipulation focus), TorchRL, Ray RLlib, Spinning Up, TF-Agents, `imitation`, `d3rlpy`, `sample-factory`.
