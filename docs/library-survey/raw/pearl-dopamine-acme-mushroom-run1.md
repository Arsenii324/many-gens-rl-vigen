<!-- VERBATIM subagent output. Do not edit. First of two passes over the same four libraries;
     the second is in pearl-dopamine-acme-mushroom-run2.md. They are kept separate, not merged.
     Landed 2026-08-17. Brief: see _brief-given-to-jobs.md. -->

# Library sweep: Meta Pearl, Dopamine, Acme, Mushroom-RL

Coverage target: DrQ, DrQ-v2, SAC-from-pixels, CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC/DAAC, IBAC-SNI, CTRL, ALDA.

All repos cloned shallow (`--depth 1`) into `/Users/a2mogus/.claude/jobs/d037da9e/tmp/libsweep/{pearl,dopamine,acme,mushroom-rl}/`.

---

## Meta Pearl

**Repo:** `facebookresearch/Pearl` → `.../libsweep/pearl`

**Coverage of the twelve: none.** `grep -rli` for all twelve names across the package → zero hits. `pearl/policy_learners/sequential_decision_making/` contains only: `bootstrapped_dqn.py`, `ddpg.py`, `deep_q_learning.py`, `deep_sarsa.py`, `deep_td_learning.py`, `double_dqn.py`, `implicit_q_learning.py`, `ppo.py`, `quantile_regression_deep_q_learning.py`, `quantile_regression_deep_td_learning.py`, `reinforce.py`, `soft_actor_critic.py`, `soft_actor_critic_continuous.py`, `tabular_q_learning.py`, `td3.py`. Pearl is a production/applied-RL library (bandits, offline RL, safety) — the null matches its scope.

**Pixel support (context):** generic CNN scaffolding exists — `CNNValueNetwork`/`CNNActorNetwork` (`pearl/neural_networks/common/{value_networks,actor_networks}.py`) plus Atari wrappers (`pearl/user_envs/wrappers/`), but none of the twelve baselines are built on it.

**Fidelity claims:** no reproducibility statement or literature-benchmark table found. `benchmark.py`/`benchmark_config.py` is Pearl's own internal sanity-check harness on classic-control/MuJoCo state envs, not a reproduction of published numbers. UNVERIFIED: contents of the linked arXiv paper (not fetched).

**Modular vs single-file:** explicitly modular, and argues for it —
> "Pearl was built with a modular design so that industry practitioners or academic researchers can select any subset and flexibly combine features below to construct a Pearl agent customized for their specific use cases." (README.md, "Design and Features")

README's comparison table even claims modularity as a differentiator vs. Dopamine (`Agent Modularity: Pearl ✅, Dopamine ❌`).

**Continuous action head:** `ContinuousSoftActorCritic` → `GaussianActorNetwork` (`pearl/neural_networks/sequential_decision_making/actor_networks.py:489`). **State-dependent** log_std (`self.fc_std = nn.Linear(hidden_dims[-1], output_dim)`), bounded via smooth tanh-rescale (naive `torch.clamp` explicitly commented out in favor of it):
```python
log_std = torch.tanh(log_std)
log_std = self._log_std_min + 0.5 * (self._log_std_max - self._log_std_min) * (log_std + 1)
```
`log_std_min=-5, log_std_max=2`. **Squash = tanh**, with standard SAC log-prob correction (`epsilon=1e-6`); a post-tanh clamp line is present but commented out — no prose bias warning, just implemented correction.

**Evaluation protocol:** `num_runs=4`, seeded via `set_seed(run_idx)`. `online_learning` exposes an `exploit: bool` deterministic-mode flag, but `benchmark.py` itself never references `exploit` — UNVERIFIED whether the standard benchmark driver runs a separate deterministic eval pass. No CI reporting; `rliable` → zero hits repo-wide.

**robosuite:** zero hits repo-wide. Env lists in `benchmark_config.py` are classic-control + state-based MuJoCo (`HalfCheetah/Ant/Hopper/Walker2d-v4`) only.

---

## Dopamine

**Repo:** `google/dopamine` → `.../libsweep/dopamine`

**Coverage of the twelve:** only SAC, plus a discrete-Atari "DrQ" that is a different beast from RL-ViGen's DrQ.
- **SAC** — `dopamine/jax/agents/sac/sac_agent.py`, config `dopamine/jax/agents/sac/configs/sac.gin`. Pixel variant: `dopamine/labs/sac_from_pixels/` (`continuous_networks.py`, `deepmind_control_lib.py`, `sac_pixels.gin`) — cites Yarats et al. 2019 (SAC+AE, DrQ's predecessor), not DrQ itself.
- **"DrQ"** — `dopamine/labs/atari_100k/configs/{DrQ,DrQ_eps}.gin`, built on `JaxFullRainbowAgent`/`JaxDQNAgent` — this is the **discrete**-action Atari-100k Efficient-DQN variant (Kostrikov/Yarats/Fergus 2020), not the continuous SAC-based DrQ used for robosuite. Flag this as a false-positive risk if naively counted.
- **DrQ-v2, CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC/DAAC, IBAC-SNI, CTRL, ALDA** — explicit absence, zero grep hits. Dopamine's native roster is DQN/C51/Rainbow/IQN/SAC/PPO only; none of the four Procgen-native algorithms (PPG, IDAAC, IBAC-SNI, CTRL) appear anywhere, consistent with Dopamine never touching Procgen.

**Fidelity claims (verbatim, README.md):**
> "Dopamine is a research framework for fast prototyping of reinforcement learning algorithms. It aims to fill the need for a small, easily grokked codebase in which users can freely experiment with wild ideas (speculative research)."
>
> "Our design principles are: *Easy experimentation*... *Flexible development*... *Compact and reliable*: Provide implementations for a few, battle-tested algorithms. *Reproducible*: Facilitate reproducibility in results. In particular, our setup follows the recommendations given by Machado et al. (2018)."

(Machado et al. 2018 = "Revisiting the ALE: Evaluation Protocols and Open Problems," the paper behind sticky-actions/no-life-loss Atari eval conventions.)

Published numbers: yes — `baselines/atari/` and `baselines/mujoco/` (raw JSON + `plots.html`). Self-documented deviation, verbatim (`baselines/mujoco/README.md`):
> "We currently only support SAC for mujoco. Also, the baseline data is reported using the training regime, not evaluation. For SAC, that means we are using sampled actions, not the mean action."
— i.e. their own published SAC curves are stochastic training returns, not deterministic eval.

**Modular vs single-file (verbatim, same README block):** "Compact and reliable: Provide implementations for a few, battle-tested algorithms." Structure is one small, forkable file per agent (`dopamine/jax/agents/<algo>/<algo>_agent.py>`) — closer to the group's own duplication-friendly null hypothesis than to a fully modular actor/learner split.

**Continuous action head** — `ActorNetwork`, `dopamine/jax/continuous_networks.py:127-185`: single `nn.Dense(action_dim*2)` (state-dependent, jointly produces loc+scale, **no min/max clamp** on scale), `scale_diag = jnp.exp(scale_diag)`, distribution `tfd.MultivariateNormalDiag`. **Squash = tanh** via TFP `TransformedDistribution` bijector chain with automatic Jacobian correction (no naive-clipping bias). Only clip present is inside `_Tanh._inverse` purely for `arctanh` numerical stability near ±1, with comment "We perform clipping in the _inverse function, as is done in TF-Agents" (provenance note, not a bias warning).

**Evaluation protocol:** MuJoCo/SAC (`sac.gin`): `evaluation_steps=10_000` agent steps/iteration (step-budgeted not episode-count), `num_iterations=3_200`, `max_steps_per_episode=1_000`, `SACAgent.seed=None # Seed with the current time` (no fixed default). Published curves use stochastic sampled actions (see deviation quote above). Atari-100k lab: `MaxEpisodeEvalRunner`, `num_eval_episodes=100`, `max_noops=30`.

**rliable connection — confirmed, explicit.** `dopamine/labs/atari_100k/README.md`: "For evaluation, we report scores averaged over 100 episodes after training. For more details about evaluation protocols, refer to the [rliable library](https://github.com/google-research/rliable)," citing Agarwal/Schwarzer/Castro/Courville/Bellemare 2021 ("Deep RL at the Edge of the Statistical Precipice"). Castro and Bellemare are both original Dopamine authors — direct team lineage, not incidental. rliable is referenced as an external tool, not vendored.

**robosuite:** zero hits anywhere in the repo. Continuous-control surface is `gym` MuJoCo + `dm_control` only.

---

## Acme

**Repo:** `google-deepmind/acme` → `.../libsweep/acme`

**Coverage of the twelve.** Only SAC as a first-class agent; DrQ-v2 exists only as a *recipe*, not an agent module.
- **`acme/agents/jax/` full listing:** `ail, ars, bc, bve, cql, crr, d4pg, dqn, impala, lfd, mbop, mpo, multiagent, ppo, pwil, r2d2, rnd, sac, sqil, td3, value_dice, wpo`. **No `drq`/`drqv2`/`curl` directory exists in the current clone.**
- **DrQ-v2**: not a standalone agent. Exists as a CNN torso class `DrQTorso` in `acme/tf/networks/vision.py:185` — "DrQ Torso inspired by the second DrQ paper [Yarats et al., 2021]" — combined with the existing **TF** DMPO agent (`acme.agents.tf.dmpo`) plus `acme.datasets.image_augmentation` in the example script `examples/tf/control_suite/lp_dmpo_pixels_drqv2.py`. So Acme's "DrQ-v2" is DMPO + DrQ-style visual torso + image augmentation, assembled at the example level, not a dedicated learner/agent directory. This matches the "historically had a DrQ/DrQ-v2 agent" framing loosely but the current master has no first-class JAX (or TF) DrQ-v2 agent module.
- **SAC** — `acme/agents/jax/sac/` (`builder.py`, `config.py`, `learning.py`, `networks.py`, README). State-based by default (`examples/baselines/rl_continuous/run_sac.py`); no JAX-side CNN/vision torso found (`acme/jax/networks/` has `atari.py`, `embedding.py`, `multiplexers.py`, `resnet.py`, `continuous.py`, `base.py` — Atari CNN exists but isn't wired to SAC in this repo). "SAC-from-pixels" is not demonstrated for JAX SAC; only the TF DMPO+DrQTorso combo touches pixel continuous control.
- **CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC/DAAC, IBAC-SNI, CTRL, ALDA, robosuite** — `grep -riEl 'drq|curl|svea|sgqn|soda|idaac|ibac|alda|robosuite|\bppg\b|\bctrl\b' --include='*.py' --include='*.md' .` → only the 3 DrQ-related files above matched; every other term returned **zero** hits, including `robosuite` on its own (`grep -ril robosuite .` → exit 1, no matches) and `rliable` (`grep -ril rliable .` → exit 1, no matches).
- Cross-check against canonical docs table `docs/user/agents.md` (last reviewed 2022-09-23): continuous-control agents listed are D4PG, TD3, SAC, MPO, PPO, DMPO, MO-MPO — no DrQ/DrQ-v2/CURL/RAD entry anywhere in the doc either, confirming these were never promoted to first-class documented agents.
- UNVERIFIED: whether an older Acme release (pre-shallow-clone HEAD) ever had a dedicated `agents/jax/drqv2/` directory that was later removed — `gh api search/commits -f q='drqv2 repo:google-deepmind/acme'` returned `"total_count":0` (inconclusive; GitHub commit-message search via this endpoint may not be reliable/complete). Did not dig further into full git history (shallow clone) or PyPI historical release tarballs.

**Fidelity claims.** Acme paper: arXiv:2006.00979, "Acme: A Research Framework for Distributed Reinforcement Learning" (linked from README.md as `[technical report][Paper]`). WebFetch of the arXiv abstract page confirmed only abstract-level text (full PDF not accessible via WebFetch): "These implementations serve both as a validation of our design decisions as well as an important contribution to reproducibility in RL research" and "simple, modular components that can be used at various scales." **UNVERIFIED**: actual benchmark tables/numbers/environments inside the paper body (DeepMind Control Suite / Atari specifics, whether DrQ/SAC numbers are published) — could not access full text via available tools; this needs a direct PDF read to confirm the "published a benchmark paper with numbers" claim at the figure/table level.

**Modular vs single-file (verbatim, README.md):**
> "Acme is a library of reinforcement learning (RL) building blocks that strives to expose simple, efficient, and readable agents. These agents first and foremost serve both as reference implementations as well as providing strong baselines for algorithm performance. However, the baseline agents exposed by Acme should also provide enough flexibility and simplicity that they can be used as a starting block for novel research... the building blocks of Acme are designed in such a way that the agents can be run at multiple scales (e.g. single-stream vs. distributed agents)."

This is Acme's actor/learner/builder/Reverb-replay modular architecture — a fully shared-infrastructure design, the opposite pole from the group's "duplication is free, joins carry burden of proof" stance.

**Continuous action heads — exact classes/defaults.**
- SAC uses `networks_lib.NormalTanhDistribution(num_dimensions)` (`acme/agents/jax/sac/networks.py:105`), defined in `acme/jax/networks/distributional.py:237-265`. Two separate `hk.Linear` heads (`_loc_layer`, `_scale_layer`) → **state-dependent** scale: `scale = jax.nn.softplus(scale) + self._min_scale` with `min_scale: float = 1e-3` default (not log_std — a direct softplus-parameterized scale, no free/global parameter). Distribution: `tfd.Normal(loc, scale)` wrapped in `TanhTransformedDistribution` (squash = **tanh**).
- `TanhTransformedDistribution` (`acme/jax/networks/distributional.py:179-218`) — explicit, documented log-prob-under-clipping handling, quoted verbatim:
```python
class TanhTransformedDistribution(tfd.TransformedDistribution):
  """Distribution followed by tanh."""
  def __init__(self, distribution, threshold=.999, validate_args=False):
    """
    Args:
      threshold: Clipping value of the action when computing the logprob.
    """
    ...
    # Computes the log of the average probability distribution outside the
    # clipping range, i.e. on the interval [-inf, -atanh(threshold)] for
    # log_prob_left and [atanh(threshold), inf] for log_prob_right.
    ...
  def log_prob(self, event):
    # Without this clip there would be NaNs in the inner tf.where and that
    # causes issues for some reasons.
    event = jnp.clip(event, -self._threshold, self._threshold)
    return jnp.where(event <= -self._threshold, self._log_prob_left,
        jnp.where(event >= self._threshold, self._log_prob_right, super().log_prob(event)))
```
  This is a real, code-level answer to "log-prob-under-clipping bias": Acme clips the *event* at `threshold=.999` for numerical stability but corrects the log-density in the tails using closed-form `log_cdf`/`log_survival_function` terms so gradients stay defined everywhere — an explicit engineering treatment of exactly the failure mode the assignment flagged, though phrased as inline code comments, not a docs warning.
- Also present: `MultivariateNormalDiagHead` (`distributional.py:268+`), used e.g. by continuous PPO/D4PG-style agents — `init_scale: float = 0.3`, `min_scale: float = 1e-6`, `w_init=VarianceScaling(1e-4)` — separate from the SAC tanh-squashed head; **not verified which of Acme's twelve-relevant agents (only SAC applies) use this vs. NormalTanhDistribution** — SAC confirmed uses `NormalTanhDistribution`.

**Evaluation protocol.** From `examples/baselines/rl_continuous/run_sac.py`: `flags.DEFINE_integer('seed', 0, ...)`, `eval_every=50_000` (steps), `evaluation_episodes=10`. Deterministic vs stochastic eval is a real, code-verified switch: `acme/jax/experiments/run_experiment.py:156` builds `eval_policy = config.make_policy(..., evaluation=True)`; SAC's `builder.make_policy` (`acme/agents/jax/sac/builder.py:156-162`) forwards this into `sac_networks.apply_policy_and_sample(networks, eval_mode=evaluation)`, which for SAC networks selects between (`acme/agents/jax/sac/networks.py:78-88, 142-143`):
```python
sample=lambda params, key: params.sample(seed=key),       # training: stochastic
sample_eval=lambda params, key: params.mode()              # eval: deterministic
```
No confidence-interval / rliable usage found anywhere in-repo (`grep -ril rliable .` → zero hits).

**robosuite:** zero hits anywhere in the repo (code, docs, examples, README). Continuous-control examples target `dm_control`/control-suite (`examples/tf/control_suite/`) and generic `rl_continuous` baselines (`examples/baselines/rl_continuous/`), not robosuite.

**Not covered / out of scope for this pass:** full-text read of arXiv:2006.00979 PDF (benchmark tables specifically); Acme's TF-legacy agent tree beyond the DrQ-v2 example; git history search for a possibly-removed JAX drqv2 agent (inconclusive `gh api` search, not pursued further).

---

## Mushroom-RL

**Repo:** `MushroomRL/mushroom-rl` → `.../libsweep/mushroom-rl` (dev branch HEAD)

**Coverage of the twelve: none.** Grep for all twelve names → only false positives (`data.ctrl` MuJoCo actuator-array indexing in `mushroom_rl/environments/mujoco.py:129` and `mushroom_rl/environments/mujoco_envs/ball_in_a_cup.py:91`, not the CTRL algorithm). Algorithm dirs (`mushroom_rl/algorithms/actor_critic/deep_actor_critic/`: `a2c.py, ddpg.py, ppo.py, ppo_bptt.py, ppo_rudin.py, sac.py, td3.py, trpo.py`; `mushroom_rl/algorithms/value/dqn/`: `dqn.py, double_dqn.py, dueling_dqn.py, categorical_dqn.py, noisy_dqn.py, quantile_dqn.py, rainbow.py, maxmin_dqn.py, averaged_dqn.py`) are generic state-based deep RL — no vision-RL baselines. Has plain state-vector SAC (`.../sac.py`), not "SAC-from-pixels" — no CNN wired to it.

**Pixel/vision support minimal:** one CNN in the whole repo, `mushroom_rl/approximators/parametric/networks/atari_network.py` (`AtariNetwork`/`AtariFeatureNetwork`, 3-conv Atari-style encoder, `state.float()/255.` normalization, Xavier-uniform init), wired only to the DQN family for Atari — not to SAC or any actor-critic.

**Fidelity claims:** JMLR paper D'Eramo, Tateo, Bonarini, Restelli, Peters, "MushroomRL: Simplifying Reinforcement Learning Research," JMLR 22(131):1-5, 2021 (arXiv:2001.01102). Per search-summary (not independently opened/verified against primary PDF — **UNVERIFIED** at exact-quote level): paper is "accompanied by a benchmarking suite collecting experimental results of state-of-the-art deep RL algorithms" with a DQN-on-Atari reproducibility demo. No in-repo benchmark-numbers doc found (checked `docs/source/*.rst`).

**Modular vs single-file:** modular, stated as a feature rather than argued for against alternatives. Verbatim, `README.rst`:
> "MushroomRL is a Python Reinforcement Learning (RL) library whose modularity allows to easily use well-known Python libraries for tensor computation (e.g. PyTorch, Tensorflow) and RL benchmarks (e.g. Gymnasium, PyBullet, Deepmind Control Suite). It allows to perform RL experiments in a simple way providing classical RL algorithms... and deep RL algorithms (e.g. DQN, DDPG, SAC, TD3, TRPO, PPO)."

Grepped for `modular|philosophy|design|why mushroom|goal` — no dedicated "why modular" argument section found beyond this.

**Continuous action head (SAC, exact):** class `SAC`, `mushroom_rl/algorithms/actor_critic/deep_actor_critic/sac.py`. Mean/log-std from **two separate approximators** (`actor_mu_params`, `actor_sigma_params`) → **state-dependent** log_std. Constructor defaults: `log_std_min=-20, log_std_max=2`. Policy class `SquashedGaussianTorchPolicy` (`mushroom_rl/policy/torch_policy.py:265`) clamps `log_sigma` to `[log_std_min, log_std_max]`, builds `SquashedGaussian` (`mushroom_rl/utils/torch_utils/torch_distributions.py:20`) — **tanh squash** via `TransformedDistribution(TanhTransform(cache_size=1) + AffineTransform)`. Docstring, verbatim as reported: "The proper change-of-variables is handled by the underlying transforms, so `log_prob` is a correct density in the action space"; `rsample_and_log_prob` computes log-prob directly during sampling "without inverting the tanh, to avoid the precision loss caused by the inverse near the boundaries" (`eps=1e-6` used near ±1 boundaries in `log_prob(value)` for arbitrary given actions). An explicit, correctness-motivated treatment of the tanh-squash log-prob issue — not a bias warning, a "we get this right" design comment.

**Evaluation protocol:** UNVERIFIED at file-path level — no canonical eval-protocol doc/script standard found in the time budget (would need a deeper pass over `examples/`). Confirmed: `rliable` does not appear anywhere in the repo (zero grep hits).

**robosuite:** zero hits anywhere in the repo. No native wrapper. `mushroom_rl/environments/` has `gymnasium_env.py` (generic Gymnasium wrapper), `mujoco.py`/`mujoco_envs/` (native MuJoCo, non-robosuite manipulation like `ball_in_a_cup.py`), `pybullet.py`, `dm_control_env.py`, `isaacsim_env.py`, `atari.py`. Since robosuite ships its own Gymnasium wrapper upstream, a robosuite task is plausibly drivable through `gymnasium_env.py` as a generic external env — but this is neither documented nor tested in Mushroom-RL. Treat as: theoretically possible via generic gym wrapper, not supported, not mentioned.

**Not covered / didn't get to:** primary-source verification of the JMLR paper's benchmark numbers (only have a search-engine summary); canonical eval-loop convention in `examples/`; whether `mushroom_rl[all]` extras include anything robotics-adjacent beyond PyBullet/MuJoCo/Isaac Sim.

---

## Cross-cutting notes

- **None of the four libraries implement any of the twelve RL-ViGen baselines as first-class, ready-to-run agents.** The closest hits are: Acme's DrQ-v2 *recipe* (TF DMPO + `DrQTorso` CNN + image augmentation, assembled at example-script level, not a packaged agent) and Dopamine's discrete Atari-100k "DrQ" (different action space, different DrQ variant than RL-ViGen's).
- **robosuite: zero mentions in any of the four repos**, verified by direct `grep -ril robosuite` over each full clone.
- **rliable:** confirmed direct lineage from Dopamine/Google Brain (Castro & Bellemare are both Dopamine and rliable-paper authors; Dopamine's own `atari_100k` lab README cites rliable for eval protocol). Zero rliable references found in Pearl, Acme, or Mushroom-RL.
- **Design-philosophy spectrum**, most duplication-friendly → most joined: Dopamine ("compact and reliable... a few, battle-tested algorithms," small per-agent files) ≈ Pearl (modular but agent-selectable/composable) < Mushroom-RL (general modular framework, less argued) < Acme (fully modular actor/learner/builder/Reverb-replay shared infrastructure, explicitly built to "run at multiple scales").
- All three continuous-action SAC-family heads found (Pearl, Dopamine, Mushroom-RL) plus Acme's SAC use **state-dependent** scale/log_std and **tanh squashing**, not clipping — and Acme's `TanhTransformedDistribution` and Mushroom-RL's `SquashedGaussian` both contain explicit, code-level engineering against the log-prob-under-clipping bias (closed-form tail correction in Acme; direct-log-prob-without-inversion in Mushroom-RL). Pearl's `GaussianActorNetwork` implements the standard SAC tanh log-prob correction without special-casing the tails.
