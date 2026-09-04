"""IBAC-SNI's learner — the base's `agents/ppo.py::PPO.optimize` with the reference's SNI loss.

**Base term**: `joonleesky/train-procgen-pytorch` @ `1678e4a`, `agents/ppo.py`, vendored at
`_upstream_1678e4a/agents_ppo.py`. `update()` below is that file's `optimize()` — same epoch
loop, same minibatch generator, same gradient-accumulation schedule, same clipped value loss,
same `clip_grad_norm_`-then-step ordering — with the policy/entropy terms replaced by the
reference's SNI forms and three terms added.

**Semantic authority**: `ext/IBAC-SNI` (`microsoft/IBAC-SNI` @ `6b3a58b`), the authors' own
release. NOT DZ's `agents/ppo_ibac.py`, which is a re-derivation
(`_upstream_1678e4a/PROVENANCE.md`). Every line of the loss below maps to `coinrun/coinrun/ppo2.py`
and is cited inline.

## The reference's loss, verbatim (`ppo2.py:153`)

    loss = pg_loss - entropy * ent_coef + vf_loss * vf_coef
           + l2_loss * Config.L2_WEIGHT + beta * info_loss

and, under `Config.SNI` (`ppo2.py:96-107`):

    pg_loss  = mean(max(pg_losses_train, pg_losses2_train))     # from pd_train (noisy)
    pg_loss += mean(max(pg_losses_run,   pg_losses2_run))       # from pd_run   (deterministic)
    pg_loss /= 2.
    entropy  = mean(pd_train._components_distribution.entropy())
    entropy += mean(pd_run.entropy())
    entropy /= 2.

Four properties of that, each of which the discarded module got wrong or omitted:

1. **The mix is over LOSSES.** Two complete, independently-clipped PPO surrogates are reduced to
   scalars and *then* averaged — not a mix of distributions, log-probs, or ratios.
2. **The value function is not mixed at all.** `vf_loss` is built from `train_model.vf_train`
   alone (`ppo2.py:76-81`), and under SNI `vf_train` is overwritten to the *deterministic*
   `fc(h_vf, 'v', 1)` (`policies.py:161`), with the authors' comment: *"Use deterministic value
   function for both as VIB for regression seems like a bad idea."* The old module computed
   `sni_lambda*value_det + (1-sni_lambda)*value_stoch` and this project's `registry.py` note
   advertised it as a feature.
3. **One denominator, two numerators.** `OLDNEGLOGPAC` is the rollout-time `pd_run` log-prob
   (`ppo2.py:231-235`) and is shared by `ratio_train` and `ratio_run` (`ppo2.py:84,99`). The
   old-deterministic vs. new-stochastic asymmetry in `ratio_train` is the reference's own
   behaviour, not a defect to fix.
4. **The mixing weight is hardcoded 1/2** (`ppo2.py:104,107`). `Config.SNI` is a boolean;
   `config.py` has no lambda flag at all — the "lambda = 0.5" in the paper's figures is this `/2`.
   There is therefore **no `sni_lambda` knob** in this module, deliberately: exposing one would
   invent a degree of freedom the reference does not have.

`info_loss` is computed once from the encoding distribution and is independent of the train/run
split (`policies.py:61-67`), so it enters the loss once, in bits (`policy.py::info_loss_bits`).

## What is inert, and why that is stated rather than hidden

`cfg.entropy_coef` is 0.0, uniformly across all four of this project's on-policy baselines, for
the continuous-adaptation reason given in `config.py`. The entropy term therefore contributes
nothing, and **SNI's entropy-mixing half is inert** — only the policy-gradient mixing is live.
Real scope limitation, recorded in `docs/FAITHFULNESS.md` rather than left for a reader to
discover from the arithmetic.
"""
from __future__ import annotations

import numpy as np
import torch

from .model import ImpalaModel
from .policy import IBACPolicy


class NonFiniteLoss(RuntimeError):
    """A NaN/Inf loss aborts rather than poisons weights. Project-wide convention, not the
    reference's — the reference has no such guard. Uniform across all baselines."""


class _RunningMeanStd:
    """`_upstream_1678e4a/`'s sibling `common/env/procgen_wrappers.py:274-303` — the
    `RunningMeanStd` that `VecNormalize` uses. Single-sample incremental Welford.

    Provenance note, corrected 2026-08-16: this was previously cited to DZ's copy of that file.
    It is byte-identical to pristine `1678e4a` (`procgen_wrappers.py` is not among the four files
    DZ's delta touches), so the transcription is from the **base**, not from a third party's port.
    The transcription itself is unchanged and was verified 2026-08-14 by running the reference's
    own code side by side with it across an episode boundary — exact to floating point
    (`docs/REGISTER.md`). Carried over rather than rewritten: it is already anchored to the right
    artefact and already has a real verification behind it.
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
    """Presents this project's on-policy learner contract over IBAC-SNI's own algorithm.

    The contract — `storage_cls`, `policy.act`, `value_of`, `normalize_reward`, `set_lr`,
    `update` — is the `porting-directive.md` §2 harness layer, shared by every on-policy
    baseline. It is legitimately shared because a defect in it lands *uniformly* on all of them
    and shows up as a systematic offset (`docs/STEP-ZERO.md` gate 3). Nothing algorithmic is
    shared: this class neither inherits from nor calls into any other baseline's learner.
    """

    from .storage import RolloutStorage as storage_cls

    def __init__(self, cfg, obs_shape, act_dim: int, device):
        self.cfg, self.device = cfg, device
        if not cfg.sni:
            # Refused rather than silently run. The reference's non-SNI branch does not merely
            # skip the mix — it aliases `pd_run` to `pd_train` (`policies.py:186-189`), so the
            # rollout policy becomes the noisy one and both ratios collapse to a single ordinary
            # PPO ratio. Skipping the mix while keeping a deterministic rollout would be a third
            # thing matching no branch of the reference. Declared exclusion (`__init__.py`);
            # an unrun code path that looks supported is worse than one that says it is not.
            raise NotImplementedError(
                "ibac_sni: sni=False is not implemented. The reference's plain branch aliases "
                "pd_run to pd_train (policies.py:186-189), which this module does not do.")

        # `train.py:98-101` builds the embedder then hands it to the policy — the base's own
        # wiring, kept. `in_channels=obs_shape[0]` is 9 here (3 stacked RGB frames) where the
        # reference had 3; the parameter already existed, so this is zero edits.
        embedder = ImpalaModel(in_channels=obs_shape[0], image_size=cfg.image_size)
        self.policy = IBACPolicy(
            embedder,
            recurrent=False,
            action_size=act_dim,
            ib_dim=cfg.ib_dim,
            nr_samples=cfg.nr_samples,
            scale_offset=cfg.scale_offset,
            init_scale=cfg.policy_head_init_scale,
        ).to(device)
        with torch.no_grad():
            self.policy.logstd.fill_(float(cfg.init_log_std))

        # `ppo2.py:158` `AdamOptimizer(learning_rate=LR, epsilon=1e-5)`; the base's own
        # `agents/ppo.py:__init__` likewise uses `optim.Adam(..., eps=1e-5)`.
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=cfg.lr, eps=1e-5)

        # `ppo2.py:116` `weight_params = [v for v in params if '/b' not in v.name]` — biases are
        # excluded from the L2 term; `logstd` (scope 'model/pi/logstd') is NOT excluded by that
        # test, so it is included here too.
        self._l2_params = [p for n, p in self.policy.named_parameters()
                           if not n.endswith(".bias")]

        self._ret_rms = _RunningMeanStd()
        self._ret = 0.0

    @torch.no_grad()
    def value_of(self, obs_u8):
        """The deterministic value head — `policies.py:161`, the only value tensor under SNI.

        This is also what fills `old_value_batch` in the rollout, so the value clip compares
        like with like, as it does in the reference (`ppo2.py:77`).
        """
        _pd_train, _pd_run, value, _info = self.policy(obs_u8)
        return value.unsqueeze(-1)

    def normalize_reward(self, raw_reward: float, done: bool) -> float:
        """`common/env/procgen_wrappers.py::VecNormalize.step_wait` (`:324-334`).

        `self.ret = self.ret*gamma + rews`; update `ret_rms` from the accumulated return;
        `rews = clip(rews/sqrt(var+eps), -cliprew, cliprew)`; `self.ret[news] = 0`. Verified
        2026-08-14 against the reference actually running (`docs/REGISTER.md`); unchanged here.
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
        """`misc_util.py:33-37` `adjust_lr`: `lr = init_lr * (1 - timesteps/max_timesteps)`,
        called once per update by `agents/ppo.py::train`."""
        lr = self.cfg.lr * max(0.0, 1.0 - frac_done) if self.cfg.linear_lr_decay else self.cfg.lr
        for g in self.optimizer.param_groups:
            g["lr"] = lr
        return lr

    def update(self, storage, update_idx: int) -> dict:
        """`agents/ppo.py::PPO.optimize` (`_upstream_1678e4a/agents_ppo.py:63-113`), with the
        policy/entropy terms replaced by `ppo2.py:83-107` and the L2/info terms from `:153`."""
        cfg = self.cfg
        # The base normalizes advantages ONCE, globally, in `compute_estimates`
        # (`common/storage.py:68-69`) — not per minibatch. `storage.advantages` does the same.
        adv = storage.advantages(normalize=cfg.normalize_adv)

        # `agents_ppo.py:65-69`, verbatim in structure.
        batch = storage.T * storage.N
        mini_batch_size = max(1, batch // cfg.num_mini_batch)
        grad_accumulation_steps = max(1, cfg.grad_accum_steps)
        grad_accumulation_cnt = 1

        pi_l, v_l, ent_l, info_l, l2_l = [], [], [], [], []
        self.policy.train()
        self.optimizer.zero_grad()
        for _epoch in range(cfg.epochs_policy):
            for obs_b, act_b, old_lp_b, old_v_b, ret_b, adv_b in storage.feed_forward_generator(
                    adv, mini_batch_size, drop_last=True):
                adv_f = adv_b.squeeze(-1)
                old_lp = old_lp_b.squeeze(-1)
                old_v = old_v_b.squeeze(-1)
                ret = ret_b.squeeze(-1)

                pd_train, pd_run, value, info_loss = self.policy(obs_b)

                # --- policy gradient, noisy pass: `ppo2.py:83-87` ---------------------------
                ratio_train = torch.exp(pd_train.log_prob(act_b) - old_lp)
                pg_losses_train = -adv_f * ratio_train
                pg_losses2_train = -adv_f * torch.clamp(
                    ratio_train, 1.0 - cfg.clip_param, 1.0 + cfg.clip_param)
                pg_loss = torch.max(pg_losses_train, pg_losses2_train).mean()

                # `ppo2.py:91-92`: under the VIB the train entropy is the MEAN OF THE COMPONENT
                # entropies, not the entropy of the mixture (which has no closed form).
                entropy = pd_train.component_distribution.entropy().mean()

                # --- SNI: second surrogate from the deterministic pass, then /2 -------------
                if cfg.sni:                                    # `ppo2.py:96-107`
                    ratio_run = torch.exp(pd_run.log_prob(act_b) - old_lp)
                    pg_losses_run = -adv_f * ratio_run
                    pg_losses2_run = -adv_f * torch.clamp(
                        ratio_run, 1.0 - cfg.clip_param, 1.0 + cfg.clip_param)
                    pg_loss = pg_loss + torch.max(pg_losses_run, pg_losses2_run).mean()
                    pg_loss = pg_loss / 2.0
                    entropy = entropy + pd_run.entropy().mean()
                    entropy = entropy / 2.0

                # --- value loss, deterministic head only: `ppo2.py:76-81` -------------------
                vpredclipped = old_v + torch.clamp(
                    value - old_v, -cfg.clip_param, cfg.clip_param)
                vf_losses1 = (value - ret).pow(2)
                vf_losses2 = (vpredclipped - ret).pow(2)
                vf_loss = 0.5 * torch.max(vf_losses1, vf_losses2).mean()

                # --- L2 on non-bias params: `ppo2.py:116,128` (`tf.nn.l2_loss` is sum(w^2)/2) -
                l2_loss = 0.5 * sum(p.pow(2).sum() for p in self._l2_params)

                # --- `ppo2.py:153` ----------------------------------------------------------
                loss = (pg_loss
                        - entropy * cfg.entropy_coef
                        + vf_loss * cfg.value_loss_coef
                        + l2_loss * cfg.l2_weight
                        + cfg.vib_beta * info_loss)

                if not torch.isfinite(loss):
                    raise NonFiniteLoss(
                        f"non-finite loss at update {update_idx}: pg={pg_loss.item()} "
                        f"vf={vf_loss.item()} info={info_loss.item()}")
                loss.backward()

                # `agents_ppo.py:101-106`: clip, step, zero — only on accumulation boundaries.
                if grad_accumulation_cnt % grad_accumulation_steps == 0:
                    torch.nn.utils.clip_grad_norm_(self.policy.parameters(), cfg.max_grad_norm)
                    self.optimizer.step()
                    self.optimizer.zero_grad()
                grad_accumulation_cnt += 1

                pi_l.append(pg_loss.item())
                v_l.append(vf_loss.item())
                ent_l.append(entropy.item())
                info_l.append(info_loss.item())
                l2_l.append(l2_loss.item())

        return {"Loss/pi": float(np.mean(pi_l)),
                "Loss/v": float(np.mean(v_l)),
                "Loss/entropy": float(np.mean(ent_l)),
                "Loss/info_bits": float(np.mean(info_l)),
                "Loss/l2": float(np.mean(l2_l))}
