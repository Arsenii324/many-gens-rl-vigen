"""CTRL's own hyperparameters. Hermetic: does not import `idaac.config.Config`, per
`porting-directive.md` §2.

Source tags:
  [C]     `ext/ctrl_public/{algo,train_ppo,models,buffer}.py`, all read in full 2026-08-14
          (`docs/REGISTER.md`) -- every `[C]` tag below cites a real flag default or a real line,
          not the paper alone.
  [RLV]   `configs/vigen.yaml`'s `ctrl:` block -- already correctly sourced there
          (`num_steps`, `gamma`, `gae_lambda`, `ctrl_window`, `ctrl_clusters`); this module's own
          attribute names match that block exactly rather than renaming it.
  [CA]    Continuous-adaptation reasoning shared with `idaac`/`ibac_sni`/`ppg` -- see their own
          config/model docstrings for the underlying argument, not re-derived here.
  [OURS]  Not in any source; chosen here, with the reason stated.

`normalize_reward`/`reward_clip` (below): task #21, `docs/REGISTER.md`, 2026-08-14 -- CTRL's own
reference does normalize reward (`ext/ctrl_public/vec_env.py::VecNormalize`) and the mechanism is
now transcribed in `ctrl/algo.py::Learner.normalize_reward`. `onpolicy_ext.py::CTRLLearner`'s own
guarded no-op is untouched -- that class is unreachable from the registry (task #19), kept only
because a test still imports it directly (task #24 tracks its eventual deletion).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    lr: float = 5.0e-4                  # [C] train_ppo.py:42, the PPO/actor-critic optimizer
    lr_ctrl: float = 1.0e-4             # [C] train_ppo.py:49, the SSL/cluster optimizer -- a
                                         # SEPARATE learning rate for a SEPARATE optimizer
                                         # (opt_idx=1), not a scaled fraction of `lr`
    linear_lr_decay: bool = False       # [C] no LR schedule found anywhere in the reference
                                         # (grepped schedule/decay/anneal across algo.py,
                                         # train_ppo.py, models.py, buffer.py -- zero matches).
                                         # A fourth real, previously-unflagged CTRL divergence
                                         # from what this project's shared core currently applies
                                         # via inheritance (idaac.algo.Learner.set_lr's linear
                                         # decay) -- same shape of gap already found and fixed
                                         # for PPG
    max_grad_norm: float = 0.5          # [C] train_ppo.py:38, applied via
                                         # optax.clip_by_global_norm to every one of the three
                                         # optimizers identically
    gamma: float = 0.99                 # [RLV] configs/vigen.yaml ctrl: block -- NOT
                                         # train_ppo.py's own Procgen default (0.999); same
                                         # DMC-vs-Procgen distinction idaac/config.py already
                                         # documents for its own gamma
    gae_lambda: float = 0.95            # [C][RLV] agree
    clip_param: float = 0.2             # [C] train_ppo.py:44 clip_eps
    value_loss_coef: float = 0.5        # [C] train_ppo.py:47 critic_coeff. Clipped formula
                                         # confirmed identical to idaac's
                                         # (loss_critic/loss_actor_and_critic, algo.py:255-259)
    entropy_coef: float = 0.0           # [CA] reference's own default is 0.01
                                         # (train_ppo.py:46) -- kept at this project's own
                                         # already-deliberate 0.0 for a 7-D Gaussian's summed
                                         # (unbounded) entropy vs. Procgen's 1-D Categorical,
                                         # same reasoning idaac/ppg's own configs state
    num_mini_batch: int = 32            # [OURS] [C]'s own n_minibatch default is 8
                                         # (train_ppo.py:41), sized for num_envs=64; kept
                                         # consistent with idaac/ppg/ibac_sni at this project's
                                         # rollout scale rather than re-deriving an unverified
                                         # count, same reasoning ppg/config.py already states
    epochs_policy: int = 3              # [C] train_ppo.py:43 epoch_ppo

    hidden_dim: int = 256               # [CA] IMPALA-ResNet output width, matches `dims=(256,
                                         # 256)` (train_ppo.py:122, models.py's own default)
    init_log_std: float = -1.0          # [CA] shrinks the initial action distribution for
                                         # robosuite's [-1,1] box

    # ---- CTRL's own self-supervised objective --------------------------------
    ctrl_window: int = 8                # [RLV] = [C] cluster_len, configs/vigen.yaml's own key,
                                         # not renamed. [C]'s own default is 10
                                         # (train_ppo.py:54)
    ctrl_clusters: int = 32             # [RLV] = [C] num_clusters, configs/vigen.yaml's own key.
                                         # [C]'s own default is 200 (train_ppo.py:55) --
                                         # configs/vigen.yaml already justifies 32: Sinkhorn
                                         # equipartition collapses when clusters are large
                                         # relative to batch, and 200 presupposes thousands of
                                         # views this project's single-environment rollout
                                         # doesn't produce
    ctrl_cluster_momentum: float = 0.95 # [C] train_ppo.py:60 ema_ctrl -- the EMA `tau` for the
                                         # target network's cluster-assignment machinery.
                                         # Matches `onpolicy_ext.py::CTRLLearner`'s existing
                                         # attribute name (`cluster_momentum`), not renamed
    lr_cluster_epochs: int = 1          # [C] train_ppo.py:56 epoch_ctrl
    n_minibatch_ctrl: int = 8           # [C] train_ppo.py:57
    temp: float = 0.1                   # [C] train_ppo.py:52, Sinkhorn-Knopp temperature
    sinkhorn_k: int = 1                 # [C] train_ppo.py:53 k, Sinkhorn sub-iterations
    myow_k: int = 1                     # [C] train_ppo.py:58, MYOW k-NN neighbor count
    myow_reg: float = 1.0               # [C] train_ppo.py:59, MYOW loss weight relative to the
                                         # proto (Sinkhorn) loss

    # ---- reward normalization (docs/REGISTER.md, 2026-08-14) -----------------
    normalize_reward: bool = True       # [C] train_ppo.py:91,99,106 construct every env with
                                         # normalize_rewards=True -- the reference's own default;
                                         # evaluate_ppo.py:38 explicitly sets normalize_rewards=
                                         # False for evaluation, confirming the reference's own
                                         # train/measurement split independently
    reward_clip: float = 10.0           # [C] VecNormalize's own cliprew default
                                         # (vec_env.py:254)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
