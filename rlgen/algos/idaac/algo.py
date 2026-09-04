"""PPO / DAAC / IDAAC objectives.

Sign convention, worked out from the paper so it stays checkable:

  eq. 1  J_DAAC(theta)  = J_pi + alpha_s*S_pi - alpha_a*L_A            (MAXIMISE)
  eq. 4  J_IDAAC(theta) = J_DAAC - alpha_i*L_E                         (MAXIMISE)
  =>     loss(theta)    = -J_pi - alpha_s*S_pi + alpha_a*L_A + alpha_i*L_E   (MINIMISE)

L_E (eq. 3) is already minimised at D = 0.5, so the "+alpha_i * L_E" sign is right: we push
the discriminator towards chance.

PAPER ERRATUM (FINDINGS B5). Eq. 2, the discriminator loss, is printed with both cross-entropy
terms on the SAME ordered pair, which is eq. 3 up to a factor of 2 and cannot train a
classifier. The text says the discriminator "is trained using a cross-entropy loss that aims to
predict which observation was first", so we implement the classifier. Flag it if a reviewer asks.

VALUE TARGET. The paper defines L_V against the Monte-Carlo return; the code it is built on
([IK storage.py]) puts the GAE(lambda) return into `returns` and regresses onto that. With
lambda=0.95 these are different objects. We follow the CODE, because that is what produced the
published numbers.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from . import metrics as M
from .model import OrderDiscriminator, PolicyNet, ValueNet, encoder_confusion_loss


class NonFiniteLoss(RuntimeError):
    """RUNBOOK O5: a NaN/Inf loss aborts the run rather than poisoning the weights."""


class _RunningReturnStd:
    """Welford on the discounted return, matching [IK] VecNormalize's `ret_rms`.

    Transcribed from this baseline's own prior lineage, not invented here: identical to
    `../../../../projects/gen-rebuttal/vigen-idaac/vigen_idaac/envs.py::RunningReturnStd`
    (`docs/REGISTER.md`, reward-normalizer placement decision, 2026-08-14). That file's config
    dataclass (`normalize_reward`, `reward_clip`) was already copied into `idaac/config.py`; this
    is the mechanism those fields describe, finally wired to something that reads them.
    """

    def __init__(self):
        self.mean, self.var, self.count = 0.0, 1.0, 1e-4

    def update(self, x: float) -> None:
        d = x - self.mean
        tot = self.count + 1
        self.mean += d / tot
        # batch variance term (`bv`) is 0 for a single sample; the combining formula collapses to
        # this incremental form, matching the vectorised reference at num_envs=1.
        self.var = (self.var * self.count + d * d * self.count / tot) / tot
        self.count = tot


class Learner:
    #: FOUND 2026-08-14 (docs/REGISTER.md): `trainer_onpolicy.py` used to hardcode
    #: `from .algos.idaac.storage import RolloutStorage` at module scope, for EVERY on-policy
    #: baseline regardless of which Learner actually ran -- silently forcing every hermetic
    #: module (`ibac_sni`, `ppg`) through this class's own storage instead of their own, contrary
    #: to `porting-directive.md` §1 ("buffers are never shared") which building those separate
    #: storage classes was supposed to satisfy. `trainer_onpolicy.py` now reads `storage_cls` off
    #: the constructed learner instead of importing one class unconditionally. Declared here so
    #: it isn't a second silent hardcode.
    from .storage import RolloutStorage as storage_cls

    def __init__(self, cfg, obs_shape, act_dim: int, device):
        self.cfg, self.device = cfg, device
        head = "value" if cfg.algo == "ppo" else "adv"
        self.policy = PolicyNet(obs_shape, act_dim, cfg.hidden_dim,
                                cfg.init_log_std, cfg.mean_head_gain, head=head).to(device)
        self.policy_opt = torch.optim.Adam(self.policy.parameters(), lr=cfg.lr, eps=1e-5)

        self.value_net = self.value_opt = None
        if cfg.algo != "ppo":
            self.value_net = ValueNet(obs_shape, cfg.hidden_dim).to(device)
            self.value_opt = torch.optim.Adam(self.value_net.parameters(), lr=cfg.lr, eps=1e-5)

        self.disc = self.disc_opt = None
        if cfg.algo == "idaac":
            self.disc = OrderDiscriminator(cfg.hidden_dim, cfg.disc_hidden).to(device)
            self.disc_opt = torch.optim.Adam(self.disc.parameters(), lr=cfg.lr, eps=1e-5)

        # `porting-directive.md` §1: stateful, single-worker (`num_envs=1` here), never lifted
        # out or shared across baselines even though other on-policy modules do their own version
        # of the same Welford-on-discounted-return shape.
        self._ret_rms = _RunningReturnStd()
        self._disc_ret = 0.0

    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def value_of(self, obs_u8):
        return self.policy.value(obs_u8) if self.cfg.algo == "ppo" else self.value_net(obs_u8)

    def normalize_reward(self, raw_reward: float, done: bool) -> float:
        """`porting-directive.md` §2: part of the algorithm, applies only to what training
        consumes -- `trainer_onpolicy.py` calls this to build `storage.rewards`, never
        `storage.rewards_raw`, which stays the untouched value for the harness. No-op when
        `cfg.normalize_reward` is `False`; default `True` (`[T3]`).

        Order matches the reference exactly: accumulate the discounted return with THIS step's
        raw reward, update the running variance from that, normalize THIS step's raw reward by
        the JUST-updated std, then reset the accumulator if the episode ended -- the reset happens
        after the normalized value is computed, not before.
        """
        if not self.cfg.normalize_reward:
            return raw_reward
        self._disc_ret = self._disc_ret * self.cfg.gamma + raw_reward
        self._ret_rms.update(self._disc_ret)
        reward = raw_reward / (self._ret_rms.var + 1e-8) ** 0.5
        reward = max(-self.cfg.reward_clip, min(self.cfg.reward_clip, reward))
        if done:
            self._disc_ret = 0.0
        return reward

    def set_lr(self, frac_done: float) -> float:
        lr = self.cfg.lr * max(0.0, 1.0 - frac_done) if self.cfg.linear_lr_decay else self.cfg.lr
        for opt in (self.policy_opt, self.value_opt, self.disc_opt):
            if opt is not None:
                for g in opt.param_groups:
                    g["lr"] = lr
        return lr

    def _modules(self) -> dict:
        return {"policy_enc": self.policy.encoder, "dist_head": self.policy.dist_head,
                "aux_head": self.policy.aux, "value": self.value_net, "disc": self.disc}

    # ------------------------------------------------------------------ #
    def _is_diag_update(self, update_idx: int) -> bool:
        if self.cfg.diag_every <= 0:
            return False
        return (update_idx < self.cfg.diag_dense_updates
                or update_idx % self.cfg.diag_every == 0)

    def update(self, storage, update_idx: int) -> dict:
        cfg = self.cfg
        diag = self._is_diag_update(update_idx)
        adv = storage.advantages(normalize=True)
        acc = {k: 0.0 for k in ("pi/pg_loss", "pi/entropy", "adv/loss", "disc/enc_loss",
                                "disc/loss", "disc/acc", "pi/approx_kl", "pi/clipfrac",
                                "pi/ratio_max", "v/loss", "adv_head/corr",
                                "disc/pair_purity")}
        n_pol = 0
        nonfinite = 0
        # Last minibatch of each phase wins -- stated because it is not an average, and the
        # previous comment claimed "once per update" from inside the minibatch loop.
        grads: dict = {}

        epochs_ran, stopped_early = 0, False
        for _ in range(cfg.epochs_policy):
            epoch_kl, epoch_n = 0.0, 0
            for obs, act, old_lp, old_v, ret, adv_t in \
                    storage.feed_forward_generator(adv, cfg.num_mini_batch):
                lp, ent, feat = self.policy.evaluate(obs, act)
                logratio = lp - old_lp
                ratio = logratio.exp()
                s1 = ratio * adv_t
                s2 = torch.clamp(ratio, 1 - cfg.clip_param, 1 + cfg.clip_param) * adv_t
                pg = -torch.min(s1, s2).mean()
                loss = pg - cfg.entropy_coef * ent.mean()

                if cfg.algo == "ppo":
                    v = self.policy.value_from_feat(feat)
                    vl = self._value_loss(v, old_v, ret)
                    loss = loss + cfg.value_loss_coef * vl
                    acc["v/loss"] += float(vl.detach())
                else:
                    a_pred = self.policy.advantage(feat, act)
                    a_loss = F.mse_loss(a_pred, adv_t)
                    loss = loss + cfg.adv_loss_coef * a_loss
                    acc["adv/loss"] += float(a_loss.detach())
                    acc["adv_head/corr"] += M.advantage_head_tracking(a_pred, adv_t)["adv_head/corr"]

                fi = fj = lbl = None
                if cfg.algo == "idaac":
                    oi, oj, lbl, purity = storage.sample_order_pairs(cfg.disc_batch_size)
                    acc["disc/pair_purity"] += purity
                    fi, fj = self.policy.encode(oi), self.policy.encode(oj)
                    e_loss = encoder_confusion_loss(self.disc(fi, fj))
                    loss = loss + cfg.inv_loss_coef * e_loss
                    acc["disc/enc_loss"] += float(e_loss.detach())

                nonfinite += M.nonfinite_count(loss)
                if nonfinite:
                    raise NonFiniteLoss(f"non-finite policy loss at update {update_idx}")

                # theta step. This backward also deposits gradients on psi (the discriminator
                # appears inside e_loss); they are discarded by disc_opt.zero_grad() below,
                # and policy_opt owns only theta.
                self.policy_opt.zero_grad(set_to_none=True)
                loss.backward()
                if diag:
                    # Only the modules THIS backward owns. The old call took all five here, which
                    # mislabelled two of them: `grad_norm/value` read whatever the previous
                    # update's value phase had left on the value net (value_opt.zero_grad runs
                    # further down), i.e. a stale gradient, or 0.0 at update 0; and
                    # `grad_norm/disc` read d(policy/confusion loss)/d(psi) -- gradients that are
                    # about to be thrown away by disc_opt.zero_grad -- rather than the
                    # discriminator's own BCE gradient. Each module is now measured immediately
                    # after its own backward and before its own clip, which is the only point
                    # where the number means what its name says.
                    grads.update(M.grad_norms({k: v for k, v in self._modules().items()
                                               if k in ("policy_enc", "dist_head", "aux_head")}))
                nn.utils.clip_grad_norm_(self.policy.parameters(), cfg.max_grad_norm)
                self.policy_opt.step()

                if cfg.algo == "idaac":
                    # psi step on DETACHED features: IDAAC 4.3 -- "only the discriminator's
                    # parameters are updated ... the encoder's parameters remain fixed".
                    z = self.disc(fi.detach(), fj.detach())
                    d_loss = F.binary_cross_entropy_with_logits(z, lbl)
                    self.disc_opt.zero_grad(set_to_none=True)
                    d_loss.backward()
                    if diag:
                        grads.update(M.grad_norms({"disc": self.disc}))
                    nn.utils.clip_grad_norm_(self.disc.parameters(), cfg.max_grad_norm)
                    self.disc_opt.step()
                    acc["disc/loss"] += float(d_loss.detach())
                    acc["disc/acc"] += M.adversary_health(z, lbl, float(0.0))["disc/acc"]

                h = M.ppo_health(ratio, logratio, cfg.clip_param)
                acc["pi/approx_kl"] += h["pi/approx_kl"]
                acc["pi/clipfrac"] += h["pi/clipfrac"]
                acc["pi/ratio_max"] = max(acc["pi/ratio_max"], h["pi/ratio_max"])
                acc["pi/pg_loss"] += float(pg.detach())
                acc["pi/entropy"] += float(ent.mean().detach())
                epoch_kl += h["pi/approx_kl"]
                epoch_n += 1
                n_pol += 1

            epochs_ran += 1
            # R16: leave the epoch loop once this epoch's mean KL says the policy has left the
            # trust region. Checked per EPOCH rather than per minibatch so an epoch is never
            # half-applied across the rollout, which would weight early minibatches more.
            if cfg.kl_early_stop and epoch_n and (epoch_kl / epoch_n) > cfg.target_kl:
                stopped_early = True
                break

        acc["pi/epochs_ran"] = float(epochs_ran)
        acc["pi/kl_early_stopped"] = float(stopped_early)

        # ---- value network, on its own schedule (N_pi) --------------------- #
        n_val = 0
        if cfg.algo != "ppo" and update_idx % cfg.value_update_every == 0:
            for _ in range(cfg.epochs_value):
                for obs, _a, _lp, old_v, ret, _adv in \
                        storage.feed_forward_generator(adv, cfg.num_mini_batch):
                    vl = self._value_loss(self.value_net(obs), old_v, ret)
                    if M.nonfinite_count(vl):
                        raise NonFiniteLoss(f"non-finite value loss at update {update_idx}")
                    self.value_opt.zero_grad(set_to_none=True)
                    # FINDINGS R24. Scaling the loss before clip_grad_norm_ means the norm is
                    # capped AFTER scaling, so with value_loss_coef=0.5 the value net's effective
                    # cap is max_grad_norm/0.5 = 1.0 -- twice the configured value and twice
                    # upstream's. Correct: backward on the unscaled loss, scale the gradients,
                    # then clip.
                    #
                    # Behind a flag because it changes LEARNING DYNAMICS, and a seed set must be
                    # internally consistent: seed 0 ran with the deviation, so box 1's seeds keep
                    # `False` to stay comparable with it, while a fresh box runs `True` as its own
                    # consistent set. Comparability is a property of a SET, not of a commit.
                    if cfg.fix_value_grad_scale:
                        vl.backward()
                        for _p in self.value_net.parameters():
                            if _p.grad is not None:
                                _p.grad.mul_(cfg.value_loss_coef)
                    else:
                        (cfg.value_loss_coef * vl).backward()
                    if diag:
                        grads.update(M.grad_norms({"value": self.value_net}))
                    nn.utils.clip_grad_norm_(self.value_net.parameters(), cfg.max_grad_norm)
                    self.value_opt.step()
                    acc["v/loss"] += float(vl.detach())
                    n_val += 1

        # Only IDAAC produces discriminator metrics. Emitting them as zeros for ppo/daac
        # would make the `disc/pair_purity < 1.0` alarm fire on a perfectly healthy run --
        # a false alarm is as damaging as a missed one, because it trains you to ignore them.
        if cfg.algo != "idaac":
            for k in ("disc/enc_loss", "disc/loss", "disc/acc", "disc/pair_purity"):
                acc.pop(k, None)
        if cfg.algo == "ppo":
            acc.pop("adv/loss", None)
            acc.pop("adv_head/corr", None)
        # These are per-update facts, not per-minibatch sums: dividing them by n_pol would
        # silently scale them (epochs_ran 4 over 128 minibatches would log as 0.03).
        NOT_AVERAGED = ("pi/ratio_max", "pi/epochs_ran", "pi/kl_early_stopped")
        row = {k: (v / n_pol if n_pol else 0.0) for k, v in acc.items()
               if k not in NOT_AVERAGED}
        for k in NOT_AVERAGED:
            if k in acc:
                row[k] = acc[k]
        # NaN, not 0.0, when the value net did not train this update: a real 0.0 loss and "did
        # not run" are different facts, and averaging them into a curve understates the loss.
        row["v/loss"] = (acc["v/loss"] / n_val) if n_val else float("nan")
        row.update(grads)
        # `nonfinite` can only ever be 0 here: any non-zero value raises NonFiniteLoss on the
        # spot (see the raise above), so the row never carries a positive count and both the
        # `health/nonfinite > 0` abort and analyze.py's O5 were unreachable. Report what is
        # actually true -- the run reached this line, therefore every loss was finite -- and let
        # the RAISE be the detector, which is louder than an alarm anyway.
        row["health/nonfinite"] = float(nonfinite)
        row["health/losses_all_finite"] = 1.0
        row["v/value_updated"] = float(n_val > 0)
        row["adv/std_prenorm"] = storage.adv_std_prenorm
        row["pi/log_std_mean"] = float(self.policy.dist_head.log_std.mean())
        row["pi/log_std_min"] = float(self.policy.dist_head.log_std.min())
        row["pi/log_std_max"] = float(self.policy.dist_head.log_std.max())
        row["v/explained_variance"] = M.explained_variance(storage.returns[:-1], storage.values[:-1])
        row["diag/corr_V_t"] = storage.value_time_correlation()
        row["diag/corr_A_t"] = (self._advantage_time_corr(storage) if diag else float("nan"))
        row["diag/is_diag_update"] = float(diag)
        return row

    @torch.no_grad()
    def _advantage_time_corr(self, storage) -> float:
        """One extra forward pass per update. IDAAC's own diagnostic needs both halves."""
        if self.cfg.algo == "ppo":
            return float("nan")            # no advantage head in the shared-net baseline
        B = storage.T * storage.N
        obs = storage.obs[:-1].reshape(B, *storage.obs.shape[2:])
        act = storage.actions.reshape(B, -1)
        preds = []
        for i in range(0, B, 512):         # chunked: B can be 100k+ observations
            feat = self.policy.encode(obs[i:i + 512])
            preds.append(self.policy.advantage(feat, act[i:i + 512]))
        return storage.advantage_time_correlation(torch.cat(preds))

    def _value_loss(self, v, old_v, ret):
        if not self.cfg.clip_value_loss:
            return 0.5 * (ret - v).pow(2).mean()
        # [IK ppo.py] clips the value prediction around the rollout-time prediction with the
        # SAME epsilon as the policy clip.
        v_clip = old_v + (v - old_v).clamp(-self.cfg.clip_param, self.cfg.clip_param)
        return 0.5 * torch.max((v - ret).pow(2), (v_clip - ret).pow(2)).mean()

    # `state_dict`/`load_state_dict` are NOT defined here. The actual checkpoint path is
    # `PPOFamilyAdapter.state_dict`/`load_state_dict` (rlgen/agents.py), which reflects over
    # `vars(self.learner)` generically -- it is what `PPGLearner`, `IBACSNILearner`, and
    # `CTRLLearner` need too, since those add their own extra submodules (`vib`, `ctrl_predictor`)
    # that a hand-curated method here would not know about. REMOVED 2026-08-14: a hand-curated
    # pair used to live here, hardcoded to exactly {policy, policy_opt, value_net, value_opt,
    # disc, disc_opt} -- confirmed to have ZERO callers anywhere in the codebase (the adapter never
    # calls `self.learner.state_dict()` as a whole) and, had it been called, it would have silently
    # omitted `vib`/`ctrl_predictor` for the three subclasses below. Found on a deep review pass
    # specifically because it read as load-bearing but was not -- see
    # docs/FINAL-VERIFICATION-CHECKLIST.md §11.
