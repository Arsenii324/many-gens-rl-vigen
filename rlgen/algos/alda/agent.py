"""SAC + ALDA. The learner, and the only file where gradients are decided.

THE COMPUTATIONAL GRAPH, stated once so it can be checked rather than inferred. `->` is a
forward edge; `-x-` is a forward edge that a `.detach()` cuts, so no gradient crosses it.

    obs (B, 3k, H, W) uint8/255
      | fold framestack into batch: (B*k, 3, H, W)
      v
    shared_trunk  ---->  z_cont (B*k, n_z)
      |                    |
      |                    +-x-> latent_model.associate(z_cont.DETACHED) -> z_q
      |                    |                                                 |
      |                    |                          RL PATH:               v
      |                    |                       (B, k, n_z) -> shared_history -> projection
      |                    |                                                 |         |
      |                    |                                                 v         v
      |                    |                                              critic     actor
      |                    |
      |                    +----> z_hat = z_cont + (z_q - z_cont).detach()   [straight-through]
      |                                     |
      v                                     v
    RECONSTRUCTION PATH:                 decoder -> logits -> BCE(obs_newest_frame)
                                            and commitment: ||z_cont - z_q.detach()||^2

Three consequences, each of which is a thing a reimplementation gets wrong:

  * NO actor or critic gradient EVER reaches `shared_trunk`. The cut is `associate(x.detach())`
    in [AC]. This is not incidental: it IS the method. Letting the critic through produces
    "ALDA (CG)", which [A] Appendix A.10 measures as worse on every environment, and which the
    authors name in the ICML rebuttal as the routing they deliberately chose.
  * The encoder is trained ONLY by reconstruction + commitment, i.e. by an objective that has
    no idea what the task is.
  * The commitment loss pulls the ENCODER toward the codebook, not the codebook toward the
    encoder. [A]'s ICML equation and [AC] agree; the ICLR version of the same equation has the
    StopGradient on the other side, which would be L_quantize -- the loss ALDA explicitly
    omits. See ALDA.md F:A2.

OPTIMISER PARTITION. [AC] hands overlapping parameter sets to several optimisers and relies on
gradients happening to be None to keep them from double-stepping. That is true there, but it is
true by accident, and an edit anywhere in the graph would silently turn it false. Here the
partition is disjoint by construction and `assert_disjoint_optimizers` proves it at build time.
The mapping is exactly equivalent to [AC]'s effective behaviour:

    ae      AdamW(wd=0.1)  shared_trunk, decoder          <- reconstruction + commitment
    latent  Adam           codebook                       <- inert unless cfg.train_codebook
    critic  Adam           critic, shared_history, critic projection [+ trunk iff CG]
    actor   Adam           actor, actor projection
    alpha   Adam           log_alpha

The `[+ trunk iff CG]` is load-bearing and was missing at first. A gradient that reaches a
parameter is not applied to it -- some optimiser has to OWN it. With `critic_grad_to_encoder`
set but the trunk absent from the critic optimiser, the critic's gradient arrived at the encoder
(measured magnitude ~6e3) and was then discarded by `ae_optimizer.zero_grad()` at the top of
`update_alda`, so the SAC+AE arm was quietly not SAC+AE. `check_construction` could not see it:
it verifies the GRAPH, and the graph was correct. Ownership is now checked too.
"""
from __future__ import annotations

import copy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from . import nets
from .config import AldaConfig
from .nets import (Actor, Critic, HistoryEncoder, OuterEncoder, RLProjection,
                   build_encoder_decoder, build_latent_model, count_parameters, weight_init)


def soft_update(net: nn.Module, target: nn.Module, tau: float) -> None:
    with torch.no_grad():
        for p, tp in zip(net.parameters(), target.parameters()):
            tp.data.copy_(tau * p.data + (1.0 - tau) * tp.data)


def assert_disjoint_optimizers(named: dict, allowed_overlap: set[int] | None = None) -> None:
    """No parameter may be owned by two optimisers, unless the overlap is DECLARED.

    Double ownership is normally the failure this guards: two Adam states over one tensor apply
    two updates per step with independent moment estimates, which does not error, does not show
    in any loss, and changes the effective learning rate by a factor that drifts during training.

    The one legitimate exception is upstream's own design for the critic-gradient arms. [AC]
    builds `critic_optimizer` over `critic.parameters() + critic_encoder.parameters()`, and
    `critic_encoder` CONTAINS the shared trunk -- so the trunk sits in both the critic optimiser
    and the autoencoder optimiser on purpose. Each calls `zero_grad` before its own backward, so
    each applies only its own objective's gradient, in sequence; that is two sequential updates,
    not a doubled one. For plain ALDA the trunk receives no critic gradient at all, so the
    overlap is inert -- which is why it is easy to miss that it is load-bearing for ALDA (CG)
    and SAC+AE.
    """
    allowed_overlap = allowed_overlap or set()
    seen: dict[int, str] = {}
    for name, opt in named.items():
        for g in opt.param_groups:
            for p in g["params"]:
                if id(p) in seen and id(p) not in allowed_overlap:
                    raise AssertionError(
                        f"parameter of shape {tuple(p.shape)} is in both {seen[id(p)]!r} and "
                        f"{name!r}; it would be stepped twice per update")
                seen[id(p)] = name


class AldaAgent:
    def __init__(self, cfg: AldaConfig, obs_shape, act_dim: int, device: torch.device):
        self.cfg, self.device, self.act_dim = cfg, device, act_dim
        c, h, w = obs_shape
        assert c == 3 * cfg.frame_stack and h == w == cfg.image_size, (obs_shape, cfg.image_size)
        self.k = cfg.frame_stack

        # Upstream constrains these two, so say so here rather than let it fail as a KeyError
        # deep inside HistoryEncoder or as a silent channel mismatch.
        assert cfg.frame_stack == 3, (
            f"[AC] models/sac.py HistoryEncoder hardcodes Conv1d(in_channels=3); frame_stack="
            f"{cfg.frame_stack} would need a change to vendored code")
        from models.sac import LATENT_MAPPING
        assert cfg.num_latents in LATENT_MAPPING, (
            f"[AC] LATENT_MAPPING covers {sorted(LATENT_MAPPING)}; num_latents="
            f"{cfg.num_latents} is not one of them")

        # WEIGHT_INIT ORDER IS UPSTREAM'S. `weight_init` draws from the RNG, and upstream applies
        # it to actor_encoder and then critic_encoder -- both of which contain the SAME shared
        # trunk and history encoder, so those are initialised twice, the second overwriting the
        # first. Applying it once per module instead would consume the RNG differently and
        # produce a different network from the same seed.
        #
        # CONSTRUCTION order is NOT identical, and an earlier version of this comment wrongly
        # claimed it was (R10-F7). `build_encoder_decoder` returns the trunk and the decoder
        # together, so our decoder is built BEFORE `HistoryEncoder`; upstream builds the decoder
        # last (`_reference/alda_trainer.py:202-220`: trunk, history, RLProjection x2, decoder).
        #
        # It matters for exactly one submodule. `weight_init` (models/sac.py:59-73, vendored
        # unmodified) reinitialises `nn.Linear`, `nn.Conv2d` and `nn.ConvTranspose2d` -- **not
        # `nn.Conv1d`** -- so HistoryEncoder's two Conv1d layers keep whatever PyTorch's default
        # constructor drew, which depends on the RNG position when they were built. Everything
        # weight_init touches is unaffected, and the differential test still shows 0.000e+00
        # across 125 tensors because it drives both sides from one already-built agent.
        #
        # CONSEQUENCE, STATED: for those two Conv1d layers our "seed 0" is not upstream's seed 0.
        # Both are valid draws from the same distribution, so no result here is invalidated -- but
        # this is a difference in initialisation, not the exact reproduction the old comment
        # claimed. NOT reordered: the eight completed runs were trained under this order, and
        # changing it now would make any future run incomparable to them for no gain.
        trunk, decoder, self.plan = build_encoder_decoder(cfg.image_size, cfg.num_latents)
        trunk, decoder = trunk.to(device), decoder.to(device)
        history = HistoryEncoder(cfg.num_latents, cfg.embedding_size).to(device)
        self.shared_trunk, self.shared_history_encoder, self.decoder = trunk, history, decoder

        self.actor_encoder = OuterEncoder(
            trunk, history, RLProjection(cfg.embedding_size, cfg.embedding_size).to(device))
        self.critic_encoder = OuterEncoder(
            trunk, history, RLProjection(cfg.embedding_size, cfg.embedding_size).to(device))
        self.actor_encoder.apply(weight_init)     # touches trunk + history + actor projection
        self.critic_encoder.apply(weight_init)    # touches trunk + history AGAIN + critic proj
        self.decoder.apply(weight_init)

        self.latent_model = build_latent_model(
            cfg.latent_model, cfg.num_latents, cfg.values_per_latent, cfg.beta,
            cfg.train_codebook).to(device)

        # upstream's signature takes an action SHAPE tuple and indexes [0]
        self.actor = Actor(cfg.embedding_size, (act_dim,), cfg.hidden_dim,
                           cfg.actor_log_std_min, cfg.actor_log_std_max).to(device)
        self.critic = Critic(cfg.embedding_size, (act_dim,), cfg.hidden_dim).to(device)

        # Targets. deepcopy gives encoder_target its OWN trunk and history (it is not a view of
        # the shared ones), which is what makes a target network a target network.
        self.critic_target = copy.deepcopy(self.critic)
        self.encoder_target = copy.deepcopy(self.critic_encoder)
        self.latent_target = copy.deepcopy(self.latent_model)
        for p in list(self.critic_target.parameters()) + list(self.encoder_target.parameters()) \
                + list(self.latent_target.parameters()):
            p.requires_grad_(False)     # targets move only by soft_update, never by a gradient

        self.log_alpha = torch.tensor(np.log(cfg.init_temperature), dtype=torch.float32,
                                      device=device, requires_grad=True)
        self.target_entropy = -float(act_dim)          # [AC] -np.prod(action_shape)

        latent_params = [p for p in self.latent_model.parameters() if p.requires_grad]
        self.ae_optimizer = torch.optim.AdamW(
            list(trunk.parameters()) + list(self.decoder.parameters()),
            lr=cfg.encoder_lr, weight_decay=cfg.ae_weight_decay)
        self.latent_optimizer = (torch.optim.Adam(latent_params, lr=cfg.encoder_lr)
                                 if latent_params else None)
        # THE TRUNK GOES IN THE CRITIC OPTIMISER IFF the critic is supposed to train it.
        # Without this the CG arms are silently NOT what they claim: the critic's gradient
        # reaches the encoder in the graph (measured magnitude ~6e3) and is then thrown away by
        # `ae_optimizer.zero_grad()` at the top of update_alda, before anything steps it. The
        # pre-flight routing check could not catch that -- it verifies the GRAPH, and the graph
        # was right; what was missing was an optimiser that owns the parameter. [AC] gets this
        # for free because its critic optimiser is built over `critic_encoder.parameters()`,
        # which contains the trunk.
        _critic_params = (list(self.critic.parameters()) + list(history.parameters())
                          + list(self.critic_encoder.projection.parameters()))
        _overlap = set()
        if cfg.critic_grad_to_encoder:
            _critic_params += list(trunk.parameters())
            _overlap = {id(p) for p in trunk.parameters()}
        self.critic_optimizer = torch.optim.Adam(
            _critic_params, lr=cfg.critic_lr, betas=(cfg.critic_beta, 0.999))
        self.actor_optimizer = torch.optim.Adam(
            list(self.actor.parameters()) + list(self.actor_encoder.projection.parameters()),
            lr=cfg.actor_lr, betas=(cfg.actor_beta, 0.999))
        self.log_alpha_optimizer = torch.optim.Adam(
            [self.log_alpha], lr=cfg.alpha_lr, betas=(cfg.alpha_beta, 0.999))

        opts = {"ae": self.ae_optimizer, "critic": self.critic_optimizer,
                "actor": self.actor_optimizer, "alpha": self.log_alpha_optimizer}
        if self.latent_optimizer is not None:
            opts["latent"] = self.latent_optimizer
        assert_disjoint_optimizers(opts, allowed_overlap=_overlap)
        self._optimizers = opts

        self.n_updates = 0
        self.train(True)

    # ------------------------------------------------------------------ basics
    @property
    def alpha(self) -> torch.Tensor:
        return self.log_alpha.exp()

    def train(self, training: bool = True) -> None:
        for m in (self.shared_trunk, self.shared_history_encoder, self.decoder, self.latent_model,
                  self.actor, self.critic, self.actor_encoder.projection,
                  self.critic_encoder.projection):
            m.train(training)

    def eval(self) -> None:
        self.train(False)

    def parameter_counts(self) -> dict:
        return {"params/trunk": count_parameters(self.shared_trunk),
                "params/history": count_parameters(self.shared_history_encoder),
                "params/decoder": count_parameters(self.decoder),
                "params/actor": count_parameters(self.actor),
                "params/critic": count_parameters(self.critic),
                "params/latent": count_parameters(self.latent_model)}

    def preprocess(self, obs) -> torch.Tensor:
        """uint8 (B, 3k, H, W) -> float32 in [0, 1]. The BCE target lives in this range."""
        t = torch.as_tensor(obs, device=self.device)
        assert t.dtype == torch.uint8, f"obs must arrive as uint8, got {t.dtype} (FINDINGS R6)"
        return t.float().div_(255.0)

    # ------------------------------------------------------------ forward paths
    def _fold(self, obs: torch.Tensor) -> torch.Tensor:
        """(B, 3k, H, W) -> (B*k, 3, H, W), frame-major.

        Equivalent to [AC]'s `einops.rearrange(obs, 'b (f c) h w -> (b f) c h w', c=3)`: the
        channel axis is ordered frame-major, channel-minor, which is exactly what a reshape
        does. `test_fold_matches_einops` pins the equivalence rather than asserting it here.
        """
        b, ck, h, w = obs.shape
        assert ck == 3 * self.k, (ck, self.k)
        return obs.reshape(b * self.k, 3, h, w)

    def _pre_projection(self, obs: torch.Tensor, encoder: OuterEncoder,
                        latent_model: nn.Module, detach: bool = False) -> torch.Tensor:
        """Everything up to (not including) the per-head projection."""
        b = obs.shape[0]
        pre_z = encoder.shared_trunk(self._fold(obs))
        outs = latent_model(pre_z)
        # `z_quantized` is derived from a DETACHED encoder output, so the RL loss stops here --
        # that is ALDA. `z_hat` is the straight-through estimator, which passes the gradient
        # back to the encoder with identity -- that is ALDA (CG) / SAC+AE. One line, one flag,
        # and `predictions.check_construction` asserts the graph agrees with the flag.
        # The two are equal in exact arithmetic but not bitwise: `x + (z_q - x)` costs ~1e-8 of
        # float32 rounding, so switching the flag perturbs the forward value at that scale and
        # changes the gradient completely. Only the second is the point.
        z = outs["z_hat" if self.cfg.critic_grad_to_encoder else "z_quantized"]
        z = z.reshape(b, self.k, -1)
        z = encoder.shared_history_encoder(z)
        return z.detach() if detach else z

    def compute_embeddings(self, obs: torch.Tensor, encoder: OuterEncoder,
                           latent_model: nn.Module, detach: bool = False) -> torch.Tensor:
        return encoder.projection(
            self._pre_projection(obs, encoder, latent_model, detach))

    @torch.no_grad()
    def act(self, obs, deterministic: bool = True) -> np.ndarray:
        """(N, 3k, H, W) uint8 -> (N, act_dim) float32 in [-1, 1] (tanh-squashed)."""
        was_training = self.actor.training
        self.eval()
        try:
            e = self.compute_embeddings(self.preprocess(obs), self.actor_encoder,
                                        self.latent_model)
            mu, pi, _, _ = self.actor(e, compute_pi=not deterministic, compute_log_pi=False)
            a = mu if deterministic else pi
        finally:
            self.train(was_training)
        return a.detach().cpu().numpy().astype(np.float32)

    @torch.no_grad()
    def encode_latents(self, obs, newest_only: bool = True) -> dict:
        """z_cont and z_d for one batch of stacks. For the diagnostics and probes.

        `newest_only` defaults True so this measures the SAME population as
        `_latent_health` during training, which reads `obs[:, -3:]` because that is what
        `update_alda` encodes. It did not, at first: this folded all k frames while training
        measured one, so `latent_frac_outside_unit` in an eval JSON and `latent/frac_outside_unit`
        in a training log were subtly different quantities -- and comparing exactly those two
        across regimes is the entire point of logging them. The frames in a stack are
        consecutive and similar, so the numbers were close, which is what would have made it
        hard to notice rather than harmless.
        """
        x = self.preprocess(obs)
        x = x[:, -3:] if newest_only else self._fold(x)
        z_cont = self.shared_trunk(x)
        outs = self.latent_model(z_cont)
        return {"z_cont": z_cont.cpu().numpy(), "z_d": outs["z_quantized"].cpu().numpy()}

    # ----------------------------------------------------------------- updates
    def update_critic(self, obs, action, reward, next_obs, not_done, log: dict) -> None:
        assert reward.shape == (obs.shape[0], 1) and not_done.shape == (obs.shape[0], 1), (
            f"reward {tuple(reward.shape)} / not_done {tuple(not_done.shape)} must be (B, 1); "
            f"a (B,) tensor would broadcast against the (B, 1) Q and silently make the MSE a "
            f"B x B outer product")
        with torch.no_grad():
            next_a = self.compute_embeddings(next_obs, self.actor_encoder, self.latent_model)
            next_c = self.compute_embeddings(next_obs, self.encoder_target, self.latent_target)
            _, pi, log_pi, _ = self.actor(next_a)
            tq1, tq2 = self.critic_target(next_c, pi)
            # entropy-regularised target; alpha is detached (it has its own loss)
            target_v = torch.min(tq1, tq2) - self.alpha.detach() * log_pi
            target_q = reward + not_done * self.cfg.discount * target_v

        e = self.compute_embeddings(obs, self.critic_encoder, self.latent_model)
        q1, q2 = self.critic(e, action)
        loss = F.mse_loss(q1, target_q) + F.mse_loss(q2, target_q)

        self.critic_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        # Measured HERE, before update_alda's ae_optimizer.zero_grad() wipes it. `grad_norms()`
        # runs at the end of update() and therefore reports the RECONSTRUCTION gradient on the
        # trunk -- so in a CG arm there was no way to see from the logs whether the critic was
        # training the encoder at all. It is (the ownership test proves it); this makes it
        # visible. Zero for plain ALDA by construction, which is itself the check.
        with torch.no_grad():
            gt = [p.grad.detach().pow(2).sum() for p in self.shared_trunk.parameters()
                  if p.grad is not None]
            log["grad/trunk_from_critic"] = (float(torch.stack(gt).sum().sqrt()) if gt else 0.0)
            # grad/critic must be read HERE, before update_actor_and_alpha runs. The actor loss
            # is -min(Q1,Q2) evaluated through `self.critic`, so `actor_loss.backward()` deposits
            # an ADDITIONAL gradient on the critic's weights -- and `actor_optimizer.zero_grad()`
            # cannot clear it, because the critic is not in the actor optimizer's param groups.
            # grad_norms() runs after the actor step, so it was reading (applied + never-applied)
            # and reporting it as "the gradients that were actually applied". Measured: 9.845
            # applied vs 7.905 as logged -- not even an over-estimate, a DIFFERENT vector sum.
            gc = [p.grad.detach().pow(2).sum() for p in self.critic.parameters()
                  if p.grad is not None]
            log["grad/critic"] = (float(torch.stack(gc).sum().sqrt()) if gc else 0.0)
        self.critic_optimizer.step()

        log["critic/loss"] = float(loss.detach())
        log["critic/q1"] = float(q1.detach().mean())
        log["critic/q2"] = float(q2.detach().mean())
        log["critic/target_q"] = float(target_q.mean())
        log["critic/q_gap"] = float((q1 - q2).detach().abs().mean())
        # DIAGNOSTIC SUITE. Each of these exists to make a specific failure legible rather than
        # inferable, and each is cheap (detached scalars on an already-computed tensor).
        with torch.no_grad():
            td = (q1 - target_q).abs()
            log["critic/td_error"] = float(td.mean())          # TD error, the thing being minimised
            log["critic/td_error_max"] = float(td.max())       # a single exploding sample shows here first
            log["critic/target_q_std"] = float(target_q.std())
            # reward scale: robosuite rescales by reward_scale, so |Q| <= r_max/(1-gamma). A Q far
            # above this ceiling is divergence, not optimism, and the ceiling needs r_max to state.
            log["batch/reward_mean"] = float(reward.mean())
            log["batch/reward_max"] = float(reward.max())
            log["batch/not_done_frac"] = float(not_done.mean())   # must be 1.0 on Door/Lift (truncation only)
            # RUNNING max, not the batch max. Using reward.max() per batch was wrong three ways
            # and I caught it only by adversarially testing my own detector: an all-negative
            # batch gives a NEGATIVE ceiling, so the ratio flips sign and a diverging Q reads as
            # a large negative number -- the detector inverts precisely when it should fire; an
            # all-zero batch makes the ratio ~5e10, a false alarm whenever a batch happens to
            # contain no reward; and being batch-dependent, the same Q reads differently run to
            # run. A running maximum is monotone, stable, and is what the bound actually needs.
            self._r_max_seen = max(getattr(self, "_r_max_seen", 0.0), float(reward.max()))
            if self._r_max_seen > 1e-6:
                q_ceiling = self._r_max_seen / (1.0 - self.cfg.discount)
                log["critic/q_over_ceiling"] = float(q1.mean()) / q_ceiling
            else:
                # no positive reward seen yet -- the bound is undefined, so say nothing rather
                # than emit a number that looks like a reading
                log["critic/q_over_ceiling"] = float("nan")
            log["batch/r_max_seen"] = self._r_max_seen
            # NaN/Inf guard: a silent NaN propagates for thousands of updates before the return moves
            log["health/nonfinite"] = float(
                (~torch.isfinite(q1)).sum() + (~torch.isfinite(target_q)).sum())

    def update_actor_and_alpha(self, obs, log: dict) -> None:
        # `detach=True` cuts after the history encoder, so the actor loss trains the actor MLP
        # and the actor's own projection, and nothing upstream. [AC].
        #
        # ONE encode, two projections. [AC] calls compute_embeddings twice here, but
        # `actor_encoder` and `critic_encoder` SHARE the trunk, the latent model and the history
        # encoder -- they differ only in `projection`. So the second call recomputes an identical
        # tensor: 384 image encodes per actor update, thrown away. Everything before the
        # projection is deterministic (no dropout, GroupNorm and LayerNorm carry no running
        # state), so this is bit-identical, and `test_fused_actor_embeddings_match_two_passes`
        # asserts exactly that against the naive path. Worth ~20% of total training time.
        z = self._pre_projection(obs, self.actor_encoder, self.latent_model, detach=True)
        a_emb = self.actor_encoder.projection(z)
        c_emb = self.critic_encoder.projection(z)
        mu, pi, log_pi, log_std = self.actor(a_emb)   # mu kept: action-saturation diagnostic
        q1, q2 = self.critic(c_emb, pi)
        actor_loss = (self.alpha.detach() * log_pi - torch.min(q1, q2)).mean()

        self.actor_optimizer.zero_grad(set_to_none=True)
        actor_loss.backward()
        self.actor_optimizer.step()
        # The backward above also deposited gradients on `critic` and on the critic projection,
        # because Q(pi) is differentiated through them. They are never applied: the next
        # update_critic calls critic_optimizer.zero_grad() before its own backward. [AC] relies
        # on the same ordering; stated here so a reordering cannot silently apply them.

        # SAC temperature: drive the policy's entropy to -act_dim
        self.log_alpha_optimizer.zero_grad(set_to_none=True)
        alpha_loss = (self.alpha * (-log_pi - self.target_entropy).detach()).mean()
        alpha_loss.backward()
        self.log_alpha_optimizer.step()

        # Differential entropy of the pre-squash Gaussian. Not the entropy of the tanh-squashed
        # policy (which is what -log_pi estimates); both are logged because they answer
        # different questions -- log_std collapse vs. actual policy stochasticity.
        gauss_entropy = 0.5 * log_std.shape[1] * (1.0 + np.log(2 * np.pi)) + log_std.sum(dim=-1)
        log["actor/loss"] = float(actor_loss.detach())
        log["actor/alpha"] = float(self.alpha.detach())
        log["actor/alpha_loss"] = float(alpha_loss.detach())
        log["actor/entropy_gauss"] = float(gauss_entropy.detach().mean())
        log["actor/neg_log_pi"] = float((-log_pi).detach().mean())
        log["actor/log_std"] = float(log_std.detach().mean())
        with torch.no_grad():
            # ACTION SATURATION. Every reported eval uses the MEAN action, and on Lift the
            # deterministic policy scored ~60x worse than sampled actions (FINDINGS D23) -- a gap
            # that was visible only in the eval, never in training. If tanh(mu) is pinned at the
            # bounds, the "mean action" is a bang-bang controller and the deterministic score
            # describes something the agent never actually did while training. This makes that
            # diagnosable DURING the run instead of after it.
            mu_t = mu.detach()                      # already tanh-squashed by the actor
            log["actor/mu_saturated_frac"] = float((mu_t.abs() > 0.99).float().mean())
            log["actor/mu_abs_mean"] = float(mu_t.abs().mean())
            log["actor/pi_saturated_frac"] = float((pi.detach().abs() > 0.99).float().mean())
            # policy std collapse -- the leading indicator of the entropy collapse in ALDA.md 26
            log["actor/std_min"] = float(log_std.detach().exp().min())

    def update_alda(self, obs, log: dict, detailed: bool = False) -> None:
        """Reconstruction + commitment. The ONLY thing that trains the encoder."""
        # [AC] `obs[:, -3:]`: the NEWEST frame only, not all k folded into the batch. [A]'s prose
        # says all k; the released code says one, and the released code is what was measured.
        x = obs[:, -3:]
        pre_z = self.shared_trunk(x)
        outs = self.latent_model(pre_z)
        logits = self.decoder(outs["z_hat"])
        assert logits.shape == x.shape, (
            f"decoder produced {tuple(logits.shape)} for input {tuple(x.shape)}; the mirrored "
            f"output_padding plan is wrong for image_size={self.cfg.image_size}")

        # ASSEMBLED EXACTLY AS [AC] DOES: the weighted terms are summed as a PER-SAMPLE VECTOR
        # and meaned once at the end, not meaned individually and then added. The two are
        # mathematically identical and numerically are not, and the difference is not academic:
        # a conv bias immediately followed by GroupNorm has a mathematically ZERO gradient
        # (normalising removes any constant the bias adds), so its computed gradient is pure
        # floating-point residue -- and Adam's first step is lr * g / (|g| + eps) ~ lr * sign(g),
        # which promotes that residue to a full-size step. Combining the terms in a different
        # order flipped those signs and moved 45 tensors by ~1e-3 on update 0.
        # `test_our_update_matches_alda_official_step_for_step` measures this to be exactly 0.
        commitment = (outs["z_continuous"] - outs["z_quantized"].detach()).pow(2).mean(1)
        recon = F.binary_cross_entropy_with_logits(logits, target=x)
        quantization = torch.zeros(1, device=self.device)      # [AC] torch.Tensor([0.0])
        if self.cfg.use_quant_loss:
            quantization = (outs["z_continuous"].detach() - outs["z_quantized"]).pow(2).mean(1)
        total = (self.cfg.commitment_coef * commitment
                 + self.cfg.quantization_coef * quantization
                 + self.cfg.recon_coef * recon)
        total = total.mean()

        self.ae_optimizer.zero_grad(set_to_none=True)
        if self.latent_optimizer is not None:
            self.latent_optimizer.zero_grad(set_to_none=True)
        total.backward()
        self.ae_optimizer.step()
        if self.latent_optimizer is not None:
            self.latent_optimizer.step()

        log["alda/total_loss"] = float(total.detach())
        log["alda/recon_bce"] = float(recon.detach())
        log["alda/commitment"] = float(commitment.detach().mean())
        log["alda/quantization"] = float(quantization.detach().mean())
        with torch.no_grad():
            mse = F.mse_loss(torch.sigmoid(logits), x)
            # PSNR against a [0, 1] dynamic range; 10*log10(1/mse)
            log["alda/psnr"] = float(10.0 * torch.log10(1.0 / mse.clamp_min(1e-12)))
            log["alda/recon_mse"] = float(mse)
            if detailed:
                log.update(self._latent_health(pre_z.detach(), outs))

    @torch.no_grad()
    def _latent_health(self, z_cont: torch.Tensor, outs: dict) -> dict:
        """The detectors that decide whether the associative memory is alive.

        `z_cont` outside [-1, 1] is not an error -- it is the OOD signal the association step
        exists to fold back onto the codebook -- but if it is outside on TRAINING data then the
        commitment loss is losing and every input snaps to an endpoint, which collapses the
        representation to 2 values per latent. `frac_outside` is the number to watch.
        """
        out: dict = {}
        out["latent/z_abs_mean"] = float(z_cont.abs().mean())
        out["latent/z_std"] = float(z_cont.std())
        out["latent/frac_outside_unit"] = float((z_cont.abs() > 1.0).float().mean())
        lm = self.latent_model
        v = nets.codebook_tensor(lm)                      # (n_z, |V|), or None
        if v is None:
            return out                                    # continuous arm: no codebook
        d = torch.abs(z_cont.unsqueeze(-1) - v[None])
        idx = torch.argmin(d, dim=-1)                     # (B, n_z) nearest code
        n_vals = v.shape[1]
        # usage entropy per latent, averaged: log(|V|) means every code is used equally, 0 means
        # the latent has collapsed onto a single code and carries no information at all
        ent, dead = [], 0
        for j in range(v.shape[0]):
            cnt = torch.bincount(idx[:, j], minlength=n_vals).float()
            p = cnt / cnt.sum().clamp_min(1)
            ent.append(float(-(p * (p + 1e-12).log()).sum()))
            dead += int((cnt == 0).sum())
        out["latent/usage_entropy"] = float(np.mean(ent))
        out["latent/usage_entropy_max"] = float(np.log(n_vals))
        out["latent/dead_codes_frac"] = dead / float(v.numel())
        if hasattr(lm, "beta"):
            # softmax sharpness: 1.0 means the retrieval is a hard argmin (beta is doing its job)
            out["latent/softmax_max_weight"] = float(
                nets.assignment_weights(lm, z_cont).max(-1).values.mean())
        out["latent/codebook_absmax"] = float(v.abs().max())
        return out

    def soft_update_targets(self) -> None:
        soft_update(self.critic.Q1, self.critic_target.Q1, self.cfg.critic_tau)
        soft_update(self.critic.Q2, self.critic_target.Q2, self.cfg.critic_tau)
        soft_update(self.critic_encoder, self.encoder_target, self.cfg.encoder_tau)
        soft_update(self.latent_model, self.latent_target, self.cfg.encoder_tau)

    def update(self, buffer, log: dict, detailed: bool = False) -> dict:
        return self.update_from_batch(*buffer.sample(self.cfg.batch_size), log=log,
                                      detailed=detailed)

    def update_from_batch(self, obs, action, reward, next_obs, not_done, log: dict,
                          detailed: bool = False) -> dict:
        """One update on an explicit batch.

        Split out from `update` so the differential test can feed the SAME batch to this and to
        ALDA_Official's own `update`, run both, and compare every parameter afterwards. That is
        the only way to state "this is their algorithm" as a measurement rather than a claim.
        The update ORDER below -- critic, then autoencoder, then (every 2nd) actor+alpha, then
        (every 2nd) target -- is upstream's, and the order matters: the actor's backward leaves
        gradients on the critic that only the next critic zero_grad clears.
        """
        obs = self.preprocess(obs)
        next_obs = self.preprocess(next_obs)
        action = torch.as_tensor(action, device=self.device)
        reward = torch.as_tensor(reward, device=self.device).unsqueeze(-1)
        not_done = torch.as_tensor(not_done, device=self.device).unsqueeze(-1)

        self.update_critic(obs, action, reward, next_obs, not_done, log)
        self.update_alda(obs, log, detailed=detailed)
        if self.n_updates % self.cfg.actor_update_freq == 0:
            self.update_actor_and_alpha(obs, log)
        if self.n_updates % self.cfg.critic_target_update_freq == 0:
            self.soft_update_targets()
        self.n_updates += 1

        if detailed:
            log.update(self.grad_norms())
        return log

    @torch.no_grad()
    def grad_norms(self) -> dict:
        """Per-module gradient norm as it stood after that module's own backward.

        Measured AFTER the step, so these are the gradients that were actually applied --
        with the documented exception of grad/critic, which is written by update_critic. The
        IDAAC port learned the hard way that a norm read at the wrong point in the sequence
        reports a different module's gradient (FINDINGS R24 discussion).
        """
        def n(m):
            g = [p.grad.detach().pow(2).sum() for p in m.parameters() if p.grad is not None]
            return float(torch.stack(g).sum().sqrt()) if g else 0.0
        # grad/critic is NOT reported here. `actor_loss = alpha*log_pi - min(Q1,Q2)` is
        # differentiated through `self.critic`, so the actor's backward deposits an extra
        # gradient on critic weights that `actor_optimizer.zero_grad()` cannot clear (the critic
        # is not in its param groups). By the time this function runs, `self.critic`'s .grad is
        # the applied gradient PLUS that never-applied deposit. update_critic writes grad/critic
        # at the one point where it means what this docstring claims.
        return {"grad/trunk": n(self.shared_trunk), "grad/decoder": n(self.decoder),
                "grad/history": n(self.shared_history_encoder), "grad/actor": n(self.actor),
                "grad/latent": n(self.latent_model)}

    # ------------------------------------------------------------ (de)serialise
    def state_dict(self) -> dict:
        return {
            "shared_trunk": self.shared_trunk.state_dict(),
            "shared_history_encoder": self.shared_history_encoder.state_dict(),
            "actor_projection": self.actor_encoder.projection.state_dict(),
            "critic_projection": self.critic_encoder.projection.state_dict(),
            "decoder": self.decoder.state_dict(),
            "latent_model": self.latent_model.state_dict(),
            "actor": self.actor.state_dict(), "critic": self.critic.state_dict(),
            "critic_target": self.critic_target.state_dict(),
            "encoder_target": self.encoder_target.state_dict(),
            "latent_target": self.latent_target.state_dict(),
            "log_alpha": self.log_alpha.detach().cpu(),
            "n_updates": self.n_updates,
        }

    def load_state_dict(self, sd: dict) -> None:
        self.shared_trunk.load_state_dict(sd["shared_trunk"])
        self.shared_history_encoder.load_state_dict(sd["shared_history_encoder"])
        self.actor_encoder.projection.load_state_dict(sd["actor_projection"])
        self.critic_encoder.projection.load_state_dict(sd["critic_projection"])
        self.decoder.load_state_dict(sd["decoder"])
        self.latent_model.load_state_dict(sd["latent_model"])
        self.actor.load_state_dict(sd["actor"])
        self.critic.load_state_dict(sd["critic"])
        self.critic_target.load_state_dict(sd["critic_target"])
        self.encoder_target.load_state_dict(sd["encoder_target"])
        self.latent_target.load_state_dict(sd["latent_target"])
        with torch.no_grad():
            self.log_alpha.copy_(sd["log_alpha"].to(self.device))
        self.n_updates = int(sd.get("n_updates", 0))

    def optimizer_state_dict(self) -> dict:
        return {k: o.state_dict() for k, o in self._optimizers.items()}

    def load_optimizer_state_dict(self, sd: dict) -> None:
        for k, o in self._optimizers.items():
            if k in sd:
                o.load_state_dict(sd[k])
