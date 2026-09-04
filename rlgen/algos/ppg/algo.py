"""PPG's learner — the PPO phase and the auxiliary phase, from the base's own two files.

**Base**: `_upstream_7295473/ppo.py::compute_losses` (the PPO phase) and `ppg.py` (`aux_train`,
`PhasicValueModel.compute_aux_loss`, and `learn`'s `n_pi` schedule). `diff`-checkable against
that directory; every deviation is cited inline.

## What the reference's PPO loss actually is, and how it differs from the usual one

    losses["pi"] = negent + pg + pi_kl
    losses["vf"] = vfcoef * ((vpred - vtarg) ** 2).mean()          # ppo.py:compute_losses

Two things a reader carrying PPO habits will get wrong:

1. **There is no value clipping.** Plain MSE, and not halved either — `vfcoef` is the only factor.
   `ibac_sni`'s base *does* clip its value loss, so this is exactly the kind of detail that does
   not survive being assumed from a neighbouring baseline.
2. **There is a KL penalty term in the policy loss**: `pi_kl = kl_penalty * 0.5 * logratio²`,
   present alongside the clipped surrogate rather than instead of it.

Entropy is `sum_nonbatch(pd.entropy()).mean()` — summed over action dims, then averaged over the
batch.

## The auxiliary phase

Every `n_pi` policy iterations, the stashed segments are replayed for `n_aux_epochs`
(`ppg.py::learn`, `aux_train`). Its loss (`ppg.py:110-115`):

    vf_aux  = 0.5 * ((vpredaux  - vtarg) ** 2).mean()    # aux head, on the POLICY encoder
    vf_true = 0.5 * ((vpredtrue - vtarg) ** 2).mean()    # true value head, on the VALUE encoder

plus a policy-distillation KL weighted by `beta_clone`, which is what stops the auxiliary
objective from dragging the policy: the value knowledge is pushed into `pi_enc` while the action
distribution is held near its pre-aux self. **This is the method.** Without dual encoders and this
phase, PPG is PPO with extra steps.

## Carried forward from the discarded construction — a decision, not a default

`_RunningMeanStd` and `normalize_reward` below are kept verbatim. Under
`docs/STEP-ZERO.md` gate 1 the null is reset-to-base, so preserving anything is a decision that
has to be argued: this transcription was made from `reward_normalizer.py` directly and **verified
2026-08-14 by running the reference's own code side by side with it across an episode boundary,
matching to floating point** (`docs/REGISTER.md`). Re-deriving it would discard a real
verification to regain nothing. Recorded as a back-merge in `docs/INTEGRATION-DELTA.md`.
"""
from __future__ import annotations

import numpy as np
import torch

from .model import PPGPolicy, entropy, logp


class NonFiniteLoss(RuntimeError):
    """A NaN/Inf loss aborts rather than poisons weights. Project-wide, not the reference's."""


class _RunningMeanStd:
    """`reward_normalizer.py::RunningMeanStd`/`update_mean_var_count_from_moments`, transcribed
    for the SINGLE-SAMPLE-PER-CALL case this project's trainer actually exercises (num_envs=1,
    one step per call). The reference's own formula is batched (`x.mean(dim=0)`/`x.var(dim=0)`
    over an arbitrary batch); for a batch of size 1, `batch_mean = x`, `batch_var = 0` (variance
    of one point is exactly zero), `batch_count = 1` -- substituting those into
    `update_mean_var_count_from_moments` collapses it to plain incremental Welford, algebraically
    identical to `idaac/algo.py::_RunningReturnStd.update` (verified by direct substitution, not
    assumed from the two looking similar): `delta=x-mean`, `new_mean=mean+delta/tot`,
    `new_var=(var*count+delta^2*count/tot)/tot`. A DIFFERENT concrete implementation from
    idaac's own (this project's own duplication discipline, `porting-directive.md` §1), whose
    formula happens to specialize to the same one PPG's reference batched formula reduces to.
    """

    def __init__(self):
        self.mean, self.var, self.count = 0.0, 1.0, 1e-4

    def update(self, x: float) -> None:
        delta = x - self.mean
        tot = self.count + 1
        self.mean += delta / tot
        self.var = (self.var * self.count + delta * delta * self.count / tot) / tot
        self.count = tot



class Learner:
    """Presents this project's on-policy learner contract over PPG's own algorithm.

    The contract (`storage_cls`, `policy.act`, `value_of`, `normalize_reward`, `set_lr`,
    `update`) is the `porting-directive.md` §2 harness layer, legitimately shared because a defect
    in it lands uniformly on every baseline. Nothing algorithmic is shared.
    """

    from .storage import RolloutStorage as storage_cls

    def __init__(self, cfg, obs_shape, act_dim: int, device):
        self.cfg, self.device = cfg, device
        self.policy = PPGPolicy(obs_shape, act_dim, hidden=cfg.hidden_dim,
                                init_log_std=cfg.init_log_std).to(device)
        self.policy_opt = torch.optim.Adam(self.policy.parameters(), lr=cfg.lr, eps=1e-5)
        # `ppg.py:239` builds a SEPARATE Adam for the aux phase, at its own `aux_lr`.
        self.aux_opt = torch.optim.Adam(self.policy.parameters(), lr=cfg.aux_lr, eps=1e-5)
        self.n_pi = int(cfg.n_policy_phases)
        self.n_aux_epochs = int(cfg.aux_epochs)
        self.beta_clone = float(cfg.aux_beta_clone)
        self.kl_penalty = float(getattr(cfg, "kl_penalty", 0.0))
        self._stash: list[dict] = []
        self._ret_rms = _RunningMeanStd()
        self._ret = 0.0

    @torch.no_grad()
    def value_of(self, obs_u8):
        return self.policy.value(obs_u8).unsqueeze(-1)

    def normalize_reward(self, raw_reward: float, done: bool) -> float:
        """`reward_normalizer.py::RewardNormalizer.__call__`/`backward_discounted_sum`,
        transcribed for one env, one step per call (this project's trainer loop shape).

        The reference computes `ret[t] = reward[t] + (1 - first[t]) * gamma * prevret`, where
        `first[t]` marks the FIRST step of a new episode. This project's signature carries `done`
        (did THIS transition END one) instead — equivalent by direct substitution when state is
        threaded consistently: resetting `_ret` AFTER a `done` step gives the same sequence as
        skipping `prevret` BEFORE the next episode's first step. Unrolled across an episode
        boundary to confirm, and verified 2026-08-14 by running the reference's own code side by
        side with this (`docs/REGISTER.md`).

        **Restored verbatim 2026-08-16 after I broke it.** This module's docstring said the
        verified normalizer was "kept verbatim"; in fact only `_RunningMeanStd` was kept and this
        method was rewritten from the description — dropping the `if done: self._ret = 0.0` reset
        entirely, so the discounted return accumulated across episode boundaries forever. Caught
        by `tests/test_reward_normalizer.py`'s closed-form check, which exists precisely because
        this is the kind of state bug that produces plausible numbers. The lesson is narrow and
        exact: "carry it forward" means *copy the code*, and a docstring claiming a component was
        preserved is a claim like any other.
        """
        if not self.cfg.normalize_reward:
            return raw_reward
        self._ret = self._ret * self.cfg.gamma + raw_reward
        self._ret_rms.update(self._ret)
        reward = raw_reward / (self._ret_rms.var + 1e-8) ** 0.5
        reward = max(-self.cfg.reward_clip, min(self.cfg.reward_clip, reward))
        if done:
            self._ret = 0.0
        return reward

    def set_lr(self, frac_done: float) -> float:
        lr = self.cfg.lr * max(0.0, 1.0 - frac_done) if self.cfg.linear_lr_decay else self.cfg.lr
        for g in self.policy_opt.param_groups:
            g["lr"] = lr
        return lr

    # ---- PPO phase: `ppo.py::compute_losses` ------------------------------------------------
    def _ppo_losses(self, obs, act, old_lp, ret, adv):
        pd, vpred, _vaux = self.policy(obs)
        newlogp = logp(pd, act).squeeze(-1)
        logratio = newlogp - old_lp
        ratio = torch.exp(logratio)
        pg = torch.max(-adv * ratio,
                       -adv * torch.clamp(ratio, 1.0 - self.cfg.clip_param,
                                          1.0 + self.cfg.clip_param)).mean()
        ent = entropy(pd).mean()
        pi_kl = self.kl_penalty * 0.5 * (logratio ** 2).mean()
        pi_loss = -ent * self.cfg.entropy_coef + pg + pi_kl
        # No value clipping and no 0.5 factor -- `ppo.py::compute_losses` verbatim.
        vf_loss = self.cfg.value_loss_coef * ((vpred - ret) ** 2).mean()
        return pi_loss, vf_loss, pg, ent

    def update(self, storage, update_idx: int) -> dict:
        cfg = self.cfg
        adv = storage.advantages(normalize=bool(getattr(cfg, "normalize_adv", True)))
        mbs = max(1, (storage.T * storage.N) // cfg.num_mini_batch)
        pg_l, v_l, ent_l = [], [], []
        self.policy.train()
        for _e in range(cfg.epochs_policy):
            for obs, act, old_lp, _old_v, ret, adv_b in storage.feed_forward_generator(adv, mbs):
                pi_loss, vf_loss, pg, ent = self._ppo_losses(
                    obs, act, old_lp.squeeze(-1), ret.squeeze(-1), adv_b.squeeze(-1))
                loss = pi_loss + vf_loss
                if not torch.isfinite(loss):
                    raise NonFiniteLoss(f"non-finite PPO loss at update {update_idx}")
                self.policy_opt.zero_grad()
                loss.backward()
                # NO gradient clipping -- the reference has none (grepped the whole package for
                # `clip_grad`/`grad_norm`/`max_grad`: zero matches). CORRECTION, same day: an
                # earlier version of this comment said the discarded construction clipped and
                # that this rebuild fixed it. It did not clip -- `git show` on the old algo.py
                # shows two explicit "NO clip_grad_norm_ call here" comments citing the same
                # reference fact. The old module got this right; nothing was fixed here. Every
                # OTHER on-policy baseline does clip, so the project is deliberately non-uniform
                # at this point: the null is the base implementation, and equalisation is a
                # downstream tuning question (`docs/STEP-ZERO.md` gate 1).
                self.policy_opt.step()
                pg_l.append(pg.item()); v_l.append(vf_loss.item()); ent_l.append(ent.item())

        # Stash this iteration's segment for the auxiliary phase (`ppg.py::learn`, store_segs).
        self._stash.append({"obs": storage.obs[:-1].reshape(-1, *storage.obs.shape[2:]).clone(),
                            "vtarg": storage.returns[:-1].reshape(-1).clone()})
        out = {"ppg/pg_loss": float(np.mean(pg_l)), "ppg/vf_loss": float(np.mean(v_l)),
               "ppg/entropy": float(np.mean(ent_l))}
        if self.n_pi > 0 and len(self._stash) >= self.n_pi:
            out.update(self._aux_phase(update_idx))
            self._stash.clear()
        return out

    # ---- Auxiliary phase: `ppg.py::aux_train` + `compute_aux_loss` --------------------------
    def _aux_phase(self, update_idx: int) -> dict:
        obs = torch.cat([s["obs"] for s in self._stash])
        vtarg = torch.cat([s["vtarg"] for s in self._stash])
        with torch.no_grad():                      # `compute_presleep_outputs` (`ppg.py:264`)
            old_pd, _v, _a = self.policy(obs)
            old_mean, old_scale = old_pd.mean.clone(), old_pd.scale.clone()
        aux_l, clone_l = [], []
        # `aux_num_mini_batch` (a COUNT) rather than the reference's `aux_mbsize` (a SIZE):
        # `train.py:23` sets `aux_mbsize=4` against a Procgen-scale segment buffer, which at this
        # project's scale would be a pathological minibatch. Already sourced and argued in
        # `config.py` as `[OURS]`; the learner reads the existing field rather than introducing a
        # second name for the same knob.
        mbs = max(1, obs.shape[0] // max(1, int(self.cfg.aux_num_mini_batch)))
        for _e in range(self.n_aux_epochs):
            perm = torch.randperm(obs.shape[0], device=obs.device)
            for i in range(0, obs.shape[0] - mbs + 1, mbs):
                idx = perm[i:i + mbs]
                pd, vpredtrue, vpredaux = self.policy(obs[idx])
                vf_aux = 0.5 * ((vpredaux - vtarg[idx]) ** 2).mean()
                vf_true = 0.5 * ((vpredtrue - vtarg[idx]) ** 2).mean()
                ref = torch.distributions.Normal(old_mean[idx], old_scale[idx])
                clone = torch.distributions.kl_divergence(ref, pd).sum(-1).mean()
                loss = vf_aux + vf_true + self.beta_clone * clone
                if not torch.isfinite(loss):
                    raise NonFiniteLoss(f"non-finite aux loss at update {update_idx}")
                self.aux_opt.zero_grad()
                loss.backward()          # unclipped, as above
                self.aux_opt.step()
                aux_l.append(vf_aux.item()); clone_l.append(clone.item())
        return {"ppg/aux_vf_aux": float(np.mean(aux_l)),
                "ppg/aux_pol_distance": float(np.mean(clone_l))}
