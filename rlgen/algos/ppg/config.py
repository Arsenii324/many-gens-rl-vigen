"""PPG's own hyperparameters. Hermetic: does not import `idaac.config.Config`, per
`porting-directive.md` §2.

Source tags:
  [P]     Cobbe et al. 2020, arXiv:2009.04416, or its released code's own defaults
          (`ext/phasic-policy-gradient/phasic_policy_gradient/{ppo,ppg,train}.py`, read in full
          2026-08-14 -- every [P] tag below cites a real line, not the paper alone).
  [RLV]   `configs/vigen.yaml`'s `ppg:` block -- already correctly sourced there
          (`n_policy_phases`/`aux_epochs`/`aux_beta_clone`, tagged `[P][C]`); this module's own
          attribute names match that block exactly rather than renaming it.
  [CA]    Continuous-adaptation reasoning shared with `idaac`/`ibac_sni` -- see their own
          config/model docstrings for the underlying argument, not re-derived here.
  [OURS]  Not in any source; chosen here, with the reason stated.

Values NOT set here because `Learner` never reads them from `cfg`: `gae_lambda`
(`[RLV]`, threaded through `trainer_onpolicy.py`'s own arguments, matching every other
on-policy `Learner`). `gamma` IS set here (below), unlike that note previously claimed --
`normalize_reward` needs it internally for the discounted-return accumulator, the same reason
`idaac/config.py` carries its own `gamma` despite the trainer's GAE loop also receiving it
independently through `hyper`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    lr: float = 5.0e-4                  # [P] train.py's own default -- NOT this project's
                                         # previously-inherited 1e-4 (idaac.config.Config's value,
                                         # unrelated to PPG)
    epochs_policy: int = 3              # [P][C] `ppo_hps` n_epoch_pi in train.py's own PPO
                                        # phase; the reference drives it through
                                        # `minibatch_optimize(nepoch=...)` (minibatch_optimize.py:46)
    normalize_adv: bool = True          # [OURS] normalised once per update rather than per
                                        # minibatch, uniformly with every other on-policy
                                        # baseline here, so the choice lands as a systematic
                                        # offset rather than selectively (STEP-ZERO gate 3)
    kl_penalty: float = 0.0             # [P][C] `ppo.py::compute_losses` carries a
                                        # `kl_penalty * 0.5 * logratio**2` term ALONGSIDE the
                                        # clipped surrogate. 0.0 is the reference's own default;
                                        # set here explicitly so the term's existence is visible
                                        # rather than silently absent
    # NOTE: there is deliberately NO max_grad_norm. The reference does not clip gradients at all
    # (grepped the whole package: zero matches for clip_grad/grad_norm/max_grad), and the null is
    # the base implementation. See algo.py's update() for the full note.

    aux_lr: float = 5.0e-4              # [P] train.py's own default, same as lr
    linear_lr_decay: bool = False       # [P] no LR schedule found anywhere in the reference
                                         # (grepped adjust_lr/lr_decay/scheduler across all three
                                         # reference files, zero matches) -- this attribute exists
                                         # for documentation; Learner.set_lr is a hard no-op
    clip_param: float = 0.2             # [P] ppo.py::learn's own default
    value_loss_coef: float = 0.5        # [P] vfcoef default. UNCLIPPED formula in algo.py --
                                         # ppo.py:107 has no clip-around-rollout-prediction at all
    entropy_coef: float = 0.0           # [CA] [P]'s own reference default is 0.01
                                         # (ppo.py::learn's entcoef, confirmed NOT overridden by
                                         # train.py's ppo_hps dict, so 0.01 is what literally runs
                                         # in the reference) -- 0.0 kept as this project's own
                                         # already-deliberate correction for a 7-D Gaussian's
                                         # summed (unbounded) entropy vs. a 1-D Categorical's,
                                         # same reasoning idaac/config.py already states
    num_mini_batch: int = 32            # [OURS] [P]'s own nminibatch default is 8, but that's
                                         # sized for num_envs=64 * nstep=256; this project's
                                         # rollout (num_steps=2048, one env) already uses 32
                                         # minibatches for idaac/ibac_sni at this scale -- kept
                                         # consistent rather than re-deriving an unverified count
                                         # for PPG specifically

    hidden_dim: int = 256               # [CA] IMPALA-ResNet output width
    init_log_std: float = -1.0          # [CA] shrinks the initial action distribution for
                                         # robosuite's [-1,1] box

    n_policy_phases: int = 32           # [RLV] = [P][C] N_pi, train.py:27 `n_pi=32`. Name matches
                                         # configs/vigen.yaml's existing key, not renamed
    aux_epochs: int = 6                 # [RLV] = [P][C] E_aux, ppg.py:224 `n_aux_epochs=6`
    aux_beta_clone: float = 1.0         # [RLV] = [P][C] beta_clone, train.py:28 `beta_clone=1.0`
    vf_true_weight: float = 1.0         # [P] train.py:29 -- NOT previously in configs/vigen.yaml
                                         # or this project's docs at all; found this session
    aux_num_mini_batch: int = 32        # [OURS] [P]'s own aux_mbsize=4 (train.py:23) is a raw
                                         # minibatch SIZE at Procgen scale, not a count, and not
                                         # directly portable to this project's rollout size --
                                         # kept consistent with num_mini_batch above rather than
                                         # re-deriving an unverified ratio, same reasoning as
                                         # ibac_sni/config.py's grad_accum_steps note

    # ---- reward normalization (docs/REGISTER.md, 2026-08-14) -----------------
    normalize_reward: bool = True       # [P] reward_normalizer.py's RewardNormalizer is
                                         # unconditionally constructed and called in the
                                         # reference's own training loop -- no flag to disable it
                                         # there, so True is the faithful default, matching
                                         # idaac/config.py's own convention for expressing that
    gamma: float = 0.99                 # [RLV] configs/vigen.yaml's ppg: block -- coincides
                                         # with, but is not derived from, reward_normalizer.py's
                                         # OWN internal default (RewardNormalizer.__init__'s
                                         # gamma=0.99, reward_normalizer.py:66). NOT [P]'s
                                         # Procgen-native GAE/value-path gamma (0.999, ppo.py) --
                                         # this project already runs GAE at 0.99 for every
                                         # on-policy baseline (docs/FAITHFULNESS.md §ppg's
                                         # "internally inconsistent discount factors" finding is
                                         # about the REFERENCE's own two different defaults, not a
                                         # live inconsistency here: this project uses one gamma,
                                         # 0.99, for both GAE and the reward normalizer, matching
                                         # neither of the reference's two Procgen-native values
                                         # exactly but reconciling the split the reference itself
                                         # never resolved)
    reward_clip: float = 10.0           # [P] RewardNormalizer's own cliprew default
                                         # (reward_normalizer.py:66) -- coincides with, but is not
                                         # derived from, idaac/config.py's [IK]-sourced 10.0

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
