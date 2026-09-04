"""CTRL's training loop: PPO/actor-critic (`algo.py::update_ppo`/`loss_actor_and_critic`) plus
the SSL/cluster objective (`algo.py::update_cluster`/`loss_cluster`), transcribed from
`ext/ctrl_public/algo.py`. Findings this build rests on, all in `docs/REGISTER.md` (2026-08-14):

TWO SEPARATE OPTIMIZERS, encoder in both. The reference's `opt_idx=0`/`opt_idx=1` split
(`algo.py:373`/`:525`) each differentiate w.r.t. the FULL param tree, so the shared `encoder`
receives real, nonzero gradient from BOTH `loss_actor_and_critic` and `loss_cluster`, applied
sequentially each update with two independent Adam momentum states -- not "the encoder belongs
to one optimizer," which is what the pseudocode's stated grouping (already cited for DEPARTS(3))
suggests in isolation. `fc_v`/`dist_head` get exactly-zero gradient from `loss_cluster` (never
touched by `cluster()`); the cluster-specific heads get exactly-zero gradient from
`loss_actor_and_critic` (never touched by `ac()`) -- so those heads are each, in net effect,
updated by exactly one optimizer, but the encoder genuinely is not.

TARGET NETWORK: hard-copied at construction (`train_ppo.py:146,150` init both models from the
SAME key), then EMA'd via `state_update` -- Polyak `new_target = tau*online + (1-tau)*target`
with `tau=ctrl_cluster_momentum` (launch default 0.95, `train_ppo.py:60`), meaning the target
moves 95% of the way to online EVERY update, not 5% -- confirmed from the formula directly, the
opposite of the usual small-tau-means-slow-target intuition. `fc_v`/`dist_head`/`protos` are
hard-copied every update (`algo.py:103-110`), not EMA'd -- though `protos` is moot either way,
see below.

SCORING: the reference extracts `protos` via an identity-matrix trick that inadvertently
contaminates the weight matrix with a bias term (register entry, 2026-08-14) -- this module uses
a clean `protos_fn(v_clust)` forward call instead, and always reads it from the ONLINE model
(`self.policy.protos`, never `self.target.protos`) for both online and target embeddings' scores,
matching the reference exactly (`algo.py:187`, `params_embedding` not `params_target`) -- the
target's own `protos` submodule is a hard-copied, dead duplicate never separately consulted.

MYOW POSITIVE-PAIR SELECTION: the reference's own "neighbouring partitions" mechanism is
unrunnable as shipped (undefined `scores_w_target`, register entry 2026-08-14 -- and even if it
ran, `compute_distance`/`top_k`'s own negate-then-top-k idiom would select the FARTHEST
prototypes, not the nearest, a second independent problem with that path). This module carries
forward the same same-partition-sampling simplification `onpolicy_ext.py::CTRLLearner` already
used (DEPARTS(2), `docs/FAITHFULNESS.md` §ctrl) -- the only evidenced-runnable option, not a new
choice invented here.

L_CLUST: unlike the old `onpolicy_ext.py::CTRLLearner` (DEPARTS(1): dropped the Sinkhorn-Knopp
term entirely, kept only the MYOW predictive loss), this module builds the REAL `sinkhorn()`
assignment and `proto_loss` -- a defect the reference determines uniquely once the actual
mechanism is read in full (`porting-directive.md` §5: transcription, no permission needed), not
a new construction decision.

WINDOW SUBSAMPLING: the reference's `update_cluster` restricts each update to the first half of
the possible sliding windows (comment claims 1/8, code computes half -- register entry,
2026-08-14, flagged there as lower-confidence, not fully traced). This module uses ALL windows --
the unambiguous reading, not a guess at an uncertain quirk.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .model import CTRLPolicy, entropy, logp
from .storage import RolloutStorage


class NonFiniteLoss(RuntimeError):
    """Matches `idaac/algo.py`'s own convention: a NaN/Inf loss aborts the run."""


class _RunningMeanStd:
    """`ext/ctrl_public/vec_env.py::RunningMeanStd`/`update_mean_var_count_from_moments`
    (`:298-327`), transcribed for the SINGLE-SAMPLE-PER-CALL case this project's trainer actually
    exercises (num_envs=1, one step per call) -- same reduction already verified for
    `ppg`/`ibac_sni`'s own `_RunningMeanStd` classes (a batch of size 1 collapses the reference's
    batched formula to plain incremental Welford), re-derived here against THIS file's own
    formula rather than assumed identical from the other two looking the same.
    """

    def __init__(self):
        self.mean, self.var, self.count = 0.0, 1.0, 1e-4

    def update(self, x: float) -> None:
        delta = x - self.mean
        tot = self.count + 1
        self.mean += delta / tot
        self.var = (self.var * self.count + delta * delta * self.count / tot) / tot
        self.count = tot


def _l2_normalize(x: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    return x * torch.rsqrt((x * x).sum(-1, keepdim=True) + eps)


def _sinkhorn(scores: torch.Tensor, temp: float, k: int) -> torch.Tensor:
    """`algo.py::sinkhorn`, formula-for-formula. `scores`: (n_samples, n_clusters).
    Returns the soft assignment `q_target`, same shape."""
    Q = (scores / temp).T  # (n_clusters, n_samples)
    Q = Q - Q.max()
    Q = torch.exp(Q)
    Q = Q / Q.sum()

    n_clusters, n_samples = Q.shape
    r = torch.full((n_clusters,), 1.0 / n_clusters, device=Q.device)
    c = torch.full((n_samples,), 1.0 / n_samples, device=Q.device)

    for _ in range(k):
        u = Q.sum(dim=1)
        u = r / u
        Q = Q * u.unsqueeze(1)
        Q = Q * (c / Q.sum(dim=0)).unsqueeze(0)
    Q = Q / Q.sum(dim=0, keepdim=True)
    return Q.T


def _cos_loss(p: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
    """`algo.py::cos_loss`: `z` is the stop-gradient target."""
    z = z.detach()
    p = _l2_normalize(p)
    z = _l2_normalize(z)
    return 2 - 2 * (p * z).sum(-1)


def _extract_windows(x: torch.Tensor, window: int) -> torch.Tensor:
    """`algo.py::extract_windows_vectorized`: sliding, stride-1, overlapping windows over dim 0.
    No episode-boundary guard, matching the reference exactly (`docs/FAITHFULNESS.md` §ctrl
    point 4, corrected 2026-08-14 -- the reference itself has this same property)."""
    T = x.shape[0]
    n = T - window + 1
    return torch.stack([x[i:i + window] for i in range(n)], dim=0)


class Learner:
    from .storage import RolloutStorage as storage_cls

    def __init__(self, cfg, obs_shape, act_dim: int, device):
        self.cfg, self.device = cfg, device
        self.window = int(cfg.ctrl_window)
        self.n_clusters = int(cfg.ctrl_clusters)

        self.policy = CTRLPolicy(obs_shape, act_dim, window=self.window,
                                  n_clusters=self.n_clusters, hidden=cfg.hidden_dim,
                                  init_log_std=cfg.init_log_std).to(device)
        # Same init as online: train_ppo.py:146,150 call model.init(key,...)/
        # model_target.init(key,...) with the IDENTICAL key, before any jax.random.split.
        self.target = CTRLPolicy(obs_shape, act_dim, window=self.window,
                                  n_clusters=self.n_clusters, hidden=cfg.hidden_dim,
                                  init_log_std=cfg.init_log_std).to(device)
        self.target.load_state_dict(self.policy.state_dict())
        for p in self.target.parameters():
            p.requires_grad_(False)

        ac_params = (list(self.policy.encoder.parameters())
                     + list(self.policy.fc_v.parameters())
                     + list(self.policy.dist_head.parameters()))
        cluster_params = (list(self.policy.encoder.parameters())
                           + list(self.policy._action_mlp.parameters())
                           + list(self.policy.concat.parameters())
                           + list(self.policy._v_clust_mlp.parameters())
                           + list(self.policy._w_clust_mlp.parameters())
                           + list(self.policy._v_pred_mlp.parameters())
                           + list(self.policy._w_pred_mlp.parameters())
                           + list(self.policy.protos.parameters()))
        self.policy_opt = torch.optim.Adam(ac_params, lr=cfg.lr, eps=1e-5)
        self.cluster_opt = torch.optim.Adam(cluster_params, lr=cfg.lr_ctrl, eps=1e-5)

        self._ret_rms = _RunningMeanStd()
        self._ret = 0.0

    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def value_of(self, obs_u8):
        return self.policy.value(obs_u8)

    def set_lr(self, frac_done: float) -> float:
        """`cfg.linear_lr_decay=False`, confirmed (`docs/REGISTER.md`: no schedule anywhere in
        the reference) -- constant LR, matching `ppg/algo.py`'s own no-op pattern."""
        return self.cfg.lr

    def normalize_reward(self, raw_reward: float, done: bool) -> float:
        """`ext/ctrl_public/vec_env.py::VecNormalize.step_wait` (`:272-281`), transcribed
        directly -- `train_ppo.py:91,99,106` construct every env with `normalize_rewards=True`
        (the reference's own default); `evaluate_ppo.py:38` explicitly sets
        `normalize_rewards=False` for evaluation, confirming the reference's own
        train/measurement split independently (the same pattern already found for
        `idaac`/`ibac_sni`, and CTRL's own `VecMonitor`-inside-`VecNormalize` wrapping order is a
        SECOND independent confirmation, `docs/REGISTER.md`, 2026-08-14).

        Formula, read verbatim from `step_wait`: `self.ret = self.ret*gamma + rews`; update
        `ret_rms` from the accumulated return; `rews = clip(rews/sqrt(var+eps), -cliprew,
        cliprew)`; `self.ret[news] = 0` -- byte-identical formula shape to
        `ibac_sni/algo.py::Learner.normalize_reward`'s own reference (DZ's `procgen_wrappers.py`
        carries the same `RunningMeanStd`/`VecNormalize` lineage as this file, both descending
        from the same OpenAI Baselines original), but independently re-read and cited against
        THIS reference's own file, not copied from that method, per `porting-directive.md` §1.
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

    @torch.no_grad()
    def _target_update(self, tau: float) -> None:
        """`algo.py::state_update`/`target_update`. `fc_v`/`dist_head`/`protos` are hard-copied
        (the reference's `fc_pi`/`fc_v`/`protos` exception), everything else Polyak-EMA'd at
        `tau` -- and at the launch default (`tau=0.95`) that means the target moves MOST of the
        way to online every update, not the reverse (see module docstring)."""
        hard_copy = {"fc_v", "dist_head", "protos"}
        for (n_o, p_o), (n_t, p_t) in zip(self.policy.named_parameters(),
                                          self.target.named_parameters()):
            top = n_o.split(".", 1)[0]
            if top in hard_copy:
                p_t.data.copy_(p_o.data)
            else:
                p_t.data.mul_(1.0 - tau).add_(p_o.data, alpha=tau)

    # ------------------------------------------------------------------ #
    def _ppo_phase(self, storage: RolloutStorage) -> dict:
        cfg = self.cfg
        adv = storage.advantages(normalize=True)
        mb_size = (storage.T * storage.N) // cfg.num_mini_batch
        acc = {"pi/pg_loss": 0.0, "v/loss": 0.0, "pi/entropy": 0.0, "health/nonfinite": 0.0}
        n_mb = 0
        for _ in range(cfg.epochs_policy):
            for obs, act, old_lp, old_v, ret, advb in storage.feed_forward_generator(adv, mb_size):
                v, dist = self.policy.ac(obs)
                lp = logp(dist, act)
                ratio = torch.exp(lp - old_lp)
                surr1 = ratio * advb
                surr2 = torch.clamp(ratio, 1.0 - cfg.clip_param, 1.0 + cfg.clip_param) * advb
                pg_loss = -torch.min(surr1, surr2).mean()

                v_clipped = old_v + (v - old_v).clamp(-cfg.clip_param, cfg.clip_param)
                v_loss = 0.5 * torch.max((v - ret).pow(2), (v_clipped - ret).pow(2)).mean()

                ent = entropy(dist).mean()
                loss = pg_loss + cfg.value_loss_coef * v_loss - cfg.entropy_coef * ent

                if not torch.isfinite(loss):
                    raise NonFiniteLoss(f"ctrl PPO loss non-finite: {float(loss)}")

                self.policy_opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [p for p in self.policy_opt.param_groups[0]["params"]], cfg.max_grad_norm)
                self.policy_opt.step()

                acc["pi/pg_loss"] += float(pg_loss.detach())
                acc["v/loss"] += float(v_loss.detach())
                acc["pi/entropy"] += float(ent.detach())
                n_mb += 1
        for k in ("pi/pg_loss", "v/loss", "pi/entropy"):
            acc[k] /= max(1, n_mb)
        return acc

    def _cluster_phase(self, storage: RolloutStorage) -> dict:
        cfg = self.cfg
        obs_seq = storage.obs[:-1, 0]      # (T, C, H, W) -- N=1, this project's only real value
        act_seq = storage.actions[:, 0]    # (T, act_dim)

        state_windows = _extract_windows(obs_seq, self.window)   # (n_windows, window, C, H, W)
        action_windows = _extract_windows(act_seq, self.window)  # (n_windows, window, act_dim)
        n_windows = state_windows.shape[0]
        if n_windows < cfg.n_minibatch_ctrl:
            return {"ctrl/proto_loss": 0.0, "ctrl/myow_loss": 0.0}

        mb_size = n_windows // cfg.n_minibatch_ctrl
        acc = {"ctrl/proto_loss": 0.0, "ctrl/myow_loss": 0.0}
        n_mb = 0
        for _ in range(cfg.lr_cluster_epochs):
            perm = torch.randperm(n_windows, device=self.device)
            for start in range(0, n_windows - mb_size + 1, mb_size):
                idx = perm[start:start + mb_size]
                sw, aw = state_windows[idx], action_windows[idx]

                v_clust, _w_clust, v_pred, w_pred = self.policy.cluster(sw, aw)
                with torch.no_grad():
                    v_clust_t, w_clust_t, _v_pred_t, w_pred_t = self.target.cluster(sw, aw)

                v_clust_n = _l2_normalize(v_clust)
                v_clust_t_n = _l2_normalize(v_clust_t)

                scores_v = self.policy.protos_fn(v_clust_n)          # (mb, n_clusters)
                scores_v_t = self.policy.protos_fn(v_clust_t_n)      # ONLINE protos, per algo.py
                log_p = F.log_softmax(scores_v / cfg.temp, dim=1)
                with torch.no_grad():
                    q_target = _sinkhorn(scores_v_t, temp=cfg.temp, k=cfg.sinkhorn_k)
                proto_loss = -(q_target * log_p).sum(dim=1).mean()

                # MYOW positive pairs: SAME-partition sampling (DEPARTS(2), carried forward --
                # see module docstring). Assign each sample to its argmax cluster under the
                # (stop-gradient) target score, then pair it with another sample from the same
                # assigned cluster.
                with torch.no_grad():
                    assign = torch.argmax(scores_v_t, dim=1)
                myow_terms = []
                for c in torch.unique(assign):
                    members = (assign == c).nonzero(as_tuple=True)[0]
                    if members.numel() < 2:
                        continue
                    perm_within = members[torch.randperm(members.numel(), device=self.device)]
                    myow_terms.append(_cos_loss(v_pred[members], w_pred_t[perm_within]))
                myow_loss = (torch.cat(myow_terms).mean() if myow_terms
                            else torch.zeros((), device=self.device))
                myow_loss = myow_loss * cfg.myow_reg

                loss = proto_loss + myow_loss
                if not torch.isfinite(loss):
                    raise NonFiniteLoss(f"ctrl cluster loss non-finite: {float(loss)}")

                self.cluster_opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [p for p in self.cluster_opt.param_groups[0]["params"]], cfg.max_grad_norm)
                self.cluster_opt.step()

                acc["ctrl/proto_loss"] += float(proto_loss.detach())
                acc["ctrl/myow_loss"] += float(myow_loss.detach())
                n_mb += 1
        if n_mb:
            for k in acc:
                acc[k] /= n_mb
        return acc

    def update(self, storage: RolloutStorage, update_idx: int) -> dict:
        row = {}
        row.update(self._ppo_phase(storage))
        row.update(self._cluster_phase(storage))
        self._target_update(self.cfg.ctrl_cluster_momentum)
        row["health/nonfinite"] = 0.0
        return row
