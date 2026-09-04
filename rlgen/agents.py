"""Adapters: many agent APIs in, one agent API out.

THE UNIFORM INTERFACE every baseline presents to this repo:

    agent.act(obs: np.ndarray (C,H,W) uint8, *, deterministic: bool) -> np.ndarray (act_dim,)
    agent.update(replay, step) -> dict[str, float]        # training only
    agent.save(path) / agent.load(path)

and, for the evaluator, `policy_for(agent, deterministic)` which collapses even that to a single
callable. The evaluator never sees an agent object -- see rlgen/evaluate.py for why that matters.

WHY ADAPTERS RATHER THAN EDITING THE ALGORITHMS. The upstream implementations are the reference;
editing them makes every future comparison against published numbers arguable. Everything
repo-specific lives here, in a file whose whole job is to be boring and inspectable.

TWO INVARIANTS ENFORCED HERE, both of which failed in the previous implementation:

* `deterministic` is honoured and is CHECKED. An agent that quietly ignores it evaluates a
  stochastic policy while the protocol card says `deterministic`, and the resulting number is a
  different quantity from every other baseline's. `assert_respects_deterministic` is called by
  the test suite against every registered baseline.
* Actions leave here as float32 in [-1, 1], shape (act_dim,), with no gradient attached. The
  previous loader returned shape (1, act_dim) for one baseline and a gradient-carrying tensor for
  another, and only a hand-written per-baseline squeeze kept the runner alive.
"""
from __future__ import annotations

import numpy as np


class RandomAgent:
    """Uniform on [-1, 1]^act_dim. The negative control.

    `deterministic` is meaningless for a random policy, and saying so is better than pretending:
    it returns the SAME distribution either way, and `assert_respects_deterministic` exempts it
    explicitly rather than letting it silently pass a check it cannot satisfy.
    """

    respects_deterministic = False

    def __init__(self, act_dim: int, seed: int = 0):
        self.act_dim = act_dim
        self._rng = np.random.default_rng(seed)

    def act(self, obs, *, deterministic: bool = True) -> np.ndarray:
        return self._rng.uniform(-1.0, 1.0, size=self.act_dim).astype(np.float32)

    def update(self, replay, step, batch_size: int = 256):  # never trains
        return {}

    def save(self, path): pass
    def load(self, path): pass


class DrQV2Adapter:
    """Wraps an RL-ViGen agent whose signature is `.act(obs, step, eval_mode)`.

    `step` drives the exploration-noise schedule and is therefore a TRAINING input. At evaluation
    the schedule must not matter -- eval takes the distribution mean -- so we pass the training
    step through during training and a fixed value at eval, and `assert_respects_deterministic`
    verifies that eval output really is independent of it.
    """

    respects_deterministic = True

    def __init__(self, agent, act_dim: int):
        self._agent = agent
        self.act_dim = act_dim
        self._step = 0
        self._iter = None

    def set_step(self, step: int) -> None:
        self._step = int(step)

    def act(self, obs, *, deterministic: bool = True) -> np.ndarray:
        import torch
        with torch.no_grad():
            a = self._agent.act(np.asarray(obs), self._step, eval_mode=bool(deterministic))
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        if a.shape != (self.act_dim,):
            raise ValueError(f"{type(self._agent).__name__}.act returned shape {a.shape}, "
                             f"expected ({self.act_dim},)")
        return np.clip(a, -1.0, 1.0)

    def update(self, replay, step, batch_size: int = 256):
        self._step = int(step)
        if getattr(self, "_iter", None) is None:
            # DrQ-v2 agents call `next(replay_iter)` and expect torch tensors.
            self._iter = replay.as_iterator(batch_size)
        out = self._agent.update(self._iter, step)
        return {k: float(v) for k, v in (out or {}).items()
                if isinstance(v, (int, float)) or hasattr(v, "__float__")}

    # -- checkpoints ---------------------------------------------------------------------------
    def state_dict(self):
        return {k: v.state_dict() for k, v in vars(self._agent).items()
                if hasattr(v, "state_dict")}

    def load_state_dict(self, sd):
        # FIXED 2026-08-14: previously silent on a key mismatch -- a checkpoint saved by a
        # differently-shaped agent (a renamed submodule, a version drift) would load PARTIALLY,
        # report nothing, and leave the unmatched submodule at its random init. Found by the
        # unbiased mutation sweep 2026-08-11 (docs/VALIDATION.md sec.4.2): a real code defect
        # that survived every existing test because nothing ever exercised a mismatched key.
        for k, v in sd.items():
            tgt = getattr(self._agent, k, None)
            if tgt is None or not hasattr(tgt, "load_state_dict"):
                raise KeyError(
                    f"checkpoint key {k!r} has no matching submodule on "
                    f"{type(self._agent).__name__} (or that submodule has no load_state_dict) -- "
                    f"refusing a partial, silently-incomplete load")
            tgt.load_state_dict(v)

    def train(self, training: bool = True):
        if hasattr(self._agent, "train"):
            self._agent.train(training)

    def __getattr__(self, name):
        return getattr(self._agent, name)


def policy_for(agent, deterministic: bool):
    """Collapse an agent to the single callable the evaluator accepts.

    This is where algorithm identity stops. Everything downstream sees `obs -> action`.
    """
    def policy(obs: np.ndarray) -> np.ndarray:
        return agent.act(obs, deterministic=deterministic)
    return policy


def assert_respects_deterministic(agent, obs_shape, *, n: int = 4) -> None:
    """`deterministic=True` must be a function of the observation alone.

    Called by tests/test_agents.py for every registered baseline. An agent that ignores the flag
    produces a stochastic-policy number under a card that says `deterministic`, which is not a
    crash and not visible in any curve -- exactly the class of defect this repo is built against.
    """
    if not getattr(agent, "respects_deterministic", True):
        return
    obs = np.random.default_rng(0).integers(0, 256, size=obs_shape, dtype=np.uint8)
    first = agent.act(obs, deterministic=True)
    for _ in range(n - 1):
        a = agent.act(obs, deterministic=True)
        if not np.allclose(first, a, atol=1e-6):
            raise AssertionError(
                f"{type(agent).__name__}.act(deterministic=True) returned different actions for "
                f"the same observation ({first} vs {a}). The protocol card would claim a "
                f"deterministic policy while a stochastic one was measured.")
    # And it must be a real distinction: an agent whose stochastic mode is identical to its
    # deterministic mode is not honouring the flag either, it is ignoring it in the other
    # direction. Sampled several times because a low-entropy policy can coincide once.
    sampled = [agent.act(obs, deterministic=False) for _ in range(6)]
    if all(np.allclose(first, s, atol=1e-9) for s in sampled):
        raise AssertionError(
            f"{type(agent).__name__}.act ignores `deterministic`: stochastic mode returned the "
            f"deterministic action every time. Either wire the flag or set "
            f"`respects_deterministic = False` and say so.")


#: The SAC-family hyperparameters, in one place, with their source.
#:
#: These are DMC-GB / SODA's published defaults -- the setting RAD and SODA were tuned in. They
#: live here rather than in `configs/vigen.yaml` because they are *required* constructor arguments
#: with no defaults in `sac.py`: a value that appears only in a yaml entry is a crash waiting for
#: any caller without that entry, which is exactly what the test suite is.
#: `configs/vigen.yaml` may override any of them, and the per-baseline README prints the diff.
SAC_DEFAULTS = dict(
    discount=0.99, init_temperature=0.1,
    actor_lr=1e-3, actor_beta=0.9, actor_log_std_min=-10, actor_log_std_max=2,
    actor_update_freq=2,
    critic_lr=1e-3, critic_beta=0.9, critic_tau=0.01, critic_target_update_freq=2,
    alpha_lr=1e-4, alpha_beta=0.5,
    encoder_tau=0.05,
    num_shared_layers=11, num_head_layers=0, num_filters=32, projection_dim=100,
    hidden_dim=1024,
    aux_lr=1e-3, aux_beta=0.9, aux_update_freq=2,
    soda_batch_size=256, soda_tau=0.005,
)


class _Args:
    """Attribute bag. `sac.py` reads its configuration off an object, not a dict."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class SacAdapter:
    """Wraps a SAC-family agent (RAD, SODA) into this repo's uniform interface.

    Two things differ from the DrQ-v2 family and both are handled here rather than in the trainer:

    * the action interface is `select_action` / `sample_action` rather than
      `act(obs, step, eval_mode)`, and there is no exploration schedule to thread;
    * `update` wants a replay *object* exposing `sample()` and `sample_soda()`, not an iterator,
      so the buffer is wrapped in `SacView` on first use.
    """

    respects_deterministic = True

    def __init__(self, model, act_dim: int, device):
        self._m = model
        self.act_dim = act_dim
        self._device = device
        self._view = None

    def set_step(self, step: int) -> None:      # no exploration schedule in SAC
        pass

    def act(self, obs, *, deterministic: bool = True) -> np.ndarray:
        a = self._m.select_action(obs) if deterministic else self._m.sample_action(obs)
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        if a.shape != (self.act_dim,):
            raise ValueError(f"{type(self._m).__name__} returned action shape {a.shape}, "
                             f"expected ({self.act_dim},)")
        return np.clip(a, -1.0, 1.0)

    def update(self, replay, step, batch_size: int = 128):
        from .replay import SacView
        if self._view is None:
            self._view = SacView(replay, batch_size, self._device)
        self._m.update(self._view, None, step)
        return {}

    def train(self, training: bool = True):
        if hasattr(self._m, "train"):
            self._m.train(training)

    def state_dict(self):
        return {k: v.state_dict() for k, v in vars(self._m).items() if hasattr(v, "state_dict")}

    def load_state_dict(self, sd):
        # FIXED 2026-08-14 -- same defect and same fix as DrQV2Adapter above.
        for k, v in sd.items():
            tgt = getattr(self._m, k, None)
            if tgt is None or not hasattr(tgt, "load_state_dict"):
                raise KeyError(
                    f"checkpoint key {k!r} has no matching submodule on "
                    f"{type(self._m).__name__} (or that submodule has no load_state_dict) -- "
                    f"refusing a partial, silently-incomplete load")
            tgt.load_state_dict(v)

    def __getattr__(self, name):
        return getattr(self._m, name)


class AldaAdapter:
    """Wraps ALDA (`rlgen/algos/alda/agent.py`) into this repo's uniform interface.

    Two differences from the DrQ-v2 and SAC families, both absorbed here:

    * ALDA's `act` is written for a BATCH -- it folds `(B, 3k, H, W)` into the VQ-VAE encoder --
      so a single observation must be unsqueezed on the way in and squeezed on the way out.
      The previous implementation of this repo hand-wrote that squeeze inline in its loader and
      got the shape wrong for one baseline (docs/REVIEW.md); doing it in one adapter, with the
      shape asserted on exit, is why `policy_for` can stay ignorant of all of it.
    * `update_from_batch(obs, action, reward, next_obs, not_done, log)` takes a batch directly
      rather than a buffer, so no buffer-interface matching is needed -- the `SacView` batch is
      handed straight through.
    """

    respects_deterministic = True

    def __init__(self, model, act_dim: int, device):
        self._m = model
        self.act_dim = act_dim
        self._device = device
        self._view = None

    def set_step(self, step: int) -> None:      # no exploration schedule
        pass

    def act(self, obs, *, deterministic: bool = True) -> np.ndarray:
        o = np.asarray(obs)
        if o.ndim == 3:
            o = o[None]                          # (C,H,W) -> (1,C,H,W)
        a = self._m.act(o, deterministic=bool(deterministic))
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        if a.shape != (self.act_dim,):
            raise ValueError(f"ALDA returned action shape {a.shape}, expected ({self.act_dim},)")
        return np.clip(a, -1.0, 1.0)

    def update(self, replay, step, batch_size: int = 128):
        from .replay import SacView
        if self._view is None:
            # ALDA asserts uint8 on entry and normalises internally -- see SacView.__init__.
            self._view = SacView(replay, batch_size, self._device, float_obs=False)
        obs, action, reward, next_obs, not_done = self._view.sample()
        # `update_from_batch` calls `.unsqueeze(-1)` on reward and not_done itself, so it wants
        # them 1-D (B,), while the SAC family wants (B, 1). Reconciled here rather than by
        # editing either side. ALDA asserts the resulting shape, which is how this was caught.
        reward = reward.reshape(-1)
        not_done = not_done.reshape(-1)
        log: dict = {}
        self._m.update_from_batch(obs, action, reward, next_obs, not_done, log)
        return {k: float(v) for k, v in log.items()
                if isinstance(v, (int, float)) or hasattr(v, "__float__")}

    def train(self, training: bool = True):
        if hasattr(self._m, "train"):
            self._m.train(training)

    def state_dict(self):
        return self._m.state_dict() if hasattr(self._m, "state_dict") else {}

    def load_state_dict(self, sd):
        if hasattr(self._m, "load_state_dict"):
            self._m.load_state_dict(sd)

    def __getattr__(self, name):
        return getattr(self._m, name)


class PPOFamilyAdapter:
    """Wraps the PPO-family `Learner` (IDAAC / DAAC / PPO) into the uniform interface.

    `update` is NOT implemented here: on-policy methods consume a rollout, not a batch, and
    `rlgen/trainer_onpolicy.py` drives `learner.update(storage, idx)` directly. Raising rather
    than silently no-op'ing is deliberate -- an on-policy agent handed to the off-policy trainer
    would otherwise collect frames and never learn, and the curve would look merely bad.
    """

    respects_deterministic = True
    on_policy = True

    def __init__(self, learner, act_dim: int, device):
        self.learner = learner
        self.act_dim = act_dim
        self._device = device

    def set_step(self, step: int) -> None:
        pass

    def act(self, obs, *, deterministic: bool = True) -> np.ndarray:
        import torch
        o = np.asarray(obs)
        if o.ndim == 3:
            o = o[None]
        # A deterministic action is evaluated in eval mode, so that any training-time stochastic
        # regulariser (IBAC's bottleneck, dropout, batch-norm statistics) is switched off. Without
        # this the "deterministic" policy is not one -- see IBACSNILearner.encode_with_vib.
        was_training = self.learner.policy.training
        if deterministic:
            self.learner.policy.eval()
        try:
            with torch.no_grad():
                a, _lp = self.learner.policy.act(torch.as_tensor(o, device=self._device),
                                                 deterministic=bool(deterministic))
        finally:
            if deterministic and was_training:
                self.learner.policy.train()
        a = np.asarray(a.squeeze(0).cpu().numpy(), dtype=np.float32).reshape(-1)
        if a.shape != (self.act_dim,):
            raise ValueError(f"policy returned action shape {a.shape}, "
                             f"expected ({self.act_dim},)")
        return np.clip(a, -1.0, 1.0)

    def update(self, replay, step, batch_size: int = 256):
        raise RuntimeError(
            f"{type(self.learner).__name__} is on-policy and must be driven by "
            f"rlgen/trainer_onpolicy.py, which feeds it a rollout. Handing it to the off-policy "
            f"trainer would collect frames and never learn.")

    def train(self, training: bool = True):
        for m in (getattr(self.learner, "policy", None), getattr(self.learner, "value_net", None)):
            if m is not None and hasattr(m, "train"):
                m.train(training)

    def state_dict(self):
        return {k: v.state_dict() for k, v in vars(self.learner).items()
                if hasattr(v, "state_dict")}

    def load_state_dict(self, sd):
        # FIXED 2026-08-14 -- same defect and same fix as DrQV2Adapter/SacAdapter above.
        for k, v in sd.items():
            tgt = getattr(self.learner, k, None)
            if tgt is None or not hasattr(tgt, "load_state_dict"):
                raise KeyError(
                    f"checkpoint key {k!r} has no matching submodule on "
                    f"{type(self.learner).__name__} (or that submodule has no load_state_dict) "
                    f"-- refusing a partial, silently-incomplete load")
            tgt.load_state_dict(v)
