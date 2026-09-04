"""The shared training loop.

One loop for every baseline whose status is `implemented`. It owns the things the brief requires
to be identical -- when evaluation happens, how many frames a run gets, what is written where --
and delegates to the agent only the two things that are genuinely per-algorithm: choosing an
action, and consuming a batch.

WHAT IS DELIBERATELY *NOT* HERE. Any normalisation of the reported return, any per-algorithm
evaluation, any per-algorithm logging key. Those are the axes on which the group's reference repo
diverged, and they live in rlgen/evaluate.py and rlgen/tags.py where there is exactly one of each.

FRAMES, NOT STEPS. The budget is counted in environment frames with `action_repeat` folded in.
"Steps" means agent steps in some codebases and simulator steps in others, and the resulting
factor-of-N confusion has already cost this group real time.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np

from . import tags
from .agents import policy_for
from .envs import EnvSpec, make_env, spec_from_protocol
from .evaluate import evaluate, checkpoint_fingerprint
from .logging_ import RunLogger
from .protocol import Protocol
from .replay import FrameReplay


@dataclass
class TrainConfig:
    batch_size: int = 256
    replay_capacity: int = 100_000
    #: Frames of random-policy data before the first gradient step. Named in frames for the same
    #: reason the budget is.
    num_seed_frames: int = 4_000
    update_every_frames: int = 2
    nstep: int = 3
    discount: float = 0.99
    device: str = "auto"
    save_every_frames: int = 50_000
    backend: str = "robosuite"

    def resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            # MPS is real on this hardware and roughly 60x CPU for conv-heavy work. Selecting it
            # explicitly matters: a silent fall back to CPU turns a 3-hour run into a 7-day one,
            # and the sibling project's IDAAC trainer had exactly that missing branch.
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"


def train(protocol: Protocol, baseline: str, cfg: TrainConfig, hyper: dict, logdir: str,
          *, verbose: bool = True) -> str:
    from . import registry
    spec = registry.get(baseline)
    if not spec.trainable:
        raise SystemExit(
            f"baseline {baseline!r} has status {spec.status!r} and cannot be trained.\n"
            f"  {spec.notes}\n"
            f"Runnable baselines: {', '.join(registry.runnable())}")

    # PREFLIGHT. Check external data before an env is built or a single artifact is written.
    # SVEA's overlay augmentation needs Places365 and only asks for it at the FIRST GRADIENT STEP
    # -- by which point the frame-0 evaluation has already emitted a protocol card, an
    # episodes.csv and a tensorboard file. A run that cannot finish must not leave behind a
    # directory that looks like one that can.
    # NOT exempted for the synthetic backend. A data requirement is a property of the ALGORITHM,
    # not of the environment: SODA's auxiliary loss calls random_overlay on every update whatever
    # the env is. Exempting synthetic let a SODA smoke run get halfway and die inside the aux
    # update, which is the late failure this preflight exists to prevent.
    problems = registry.check_data_requirements(baseline)
    if problems:
        raise SystemExit(
            f"baseline {baseline!r} cannot TRAIN here -- missing data:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\n\nEvaluating an existing checkpoint does not need it (the augmentation is in "
              "update(), not act()). See baselines/" + baseline + "/README.md.")

    # SEED THE GLOBAL RNGS. FOUND 2026-08-14 by a differential test: `protocol.seed` was passed
    # to `spec.build` as a `hyper["seed"]` value, but NOTHING in this file, `registry.py`, or any
    # agent's `__init__` ever called `torch.manual_seed`. Measured directly: two agents built with
    # the identical declared seed, in the same process, produced different actions from identical
    # observations -- weight initialisation was governed by ambient global RNG state, not by the
    # seed anyone declared. `rlgen/algos/soda_utils.py::set_seed_everywhere` does exactly this and
    # has existed, unused, with zero callers, the whole time -- vendored from SODA's own script,
    # where it presumably ran, and never wired into this repo's shared trainer.
    # This does NOT change the "different seeds differ" property (still true, verified) -- it adds
    # the "same seed reproduces" property, which every earlier claim implicitly assumed.
    import random
    import numpy as np
    import torch
    torch.manual_seed(protocol.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(protocol.seed)
    np.random.seed(protocol.seed)
    random.seed(protocol.seed)

    device = cfg.resolve_device()
    env_spec = spec_from_protocol(protocol, mode=protocol.train_mode,
                                  scene_id=protocol.train_scene_ids[0], seed=protocol.seed,
                                  backend=cfg.backend)
    env = make_env(env_spec)
    act_dim = env.act_dim
    agent = spec.build(protocol, protocol.obs_shape, act_dim, device, {**hyper, "seed": protocol.seed})

    replay = FrameReplay(capacity=cfg.replay_capacity, frame_shape=(3, protocol.image_size,
                                                                    protocol.image_size),
                         act_dim=act_dim, frame_stack=protocol.frame_stack,
                         discount=cfg.discount, nstep=cfg.nstep, seed=protocol.seed)

    logger = RunLogger(logdir, protocol, baseline=baseline)
    if verbose:
        print(f"[train] {baseline} on {protocol.task} | device={device} | "
              f"{protocol.total_frames:,} frames | protocol {protocol.hash()}")
        print(f"[train] logdir {logger.logdir}")

    frames, n_updates = 0, 0
    obs = env.reset()
    replay.start_episode()
    ep_ret, ep_returns = 0.0, []
    t0 = time.time()
    next_save = cfg.save_every_frames
    ckpt_path = os.path.join(logger.logdir, "checkpoint.pt")

    # Evaluate BEFORE the first frame. This point is the untrained-network reference for this
    # exact architecture and protocol, it costs one eval, and without it the first real point has
    # nothing to be a change from. It is recorded at frames=0, not frames=1.
    _do_eval(protocol, agent, logger, 0, cfg, baseline, spec, verbose)
    logger.log_train(frames=0, n_updates=0)
    evaluated_at = {0}
    next_eval = protocol.eval_every_frames

    while frames < protocol.total_frames:
        # ---- act -------------------------------------------------------------------------
        if frames < cfg.num_seed_frames:
            action = np.random.uniform(-1, 1, size=act_dim).astype(np.float32)
        else:
            if hasattr(agent, "set_step"):
                agent.set_step(frames)
            action = agent.act(obs, deterministic=False)

        nxt, reward, terminated, truncated, _ = env.step(action)
        # The buffer stores the newest single frame; the stack is rebuilt on read.
        replay.add(nxt[-3:], action, reward, terminated or truncated)
        ep_ret += reward
        frames += protocol.action_repeat
        obs = nxt

        if terminated or truncated:
            ep_returns.append(ep_ret)
            ep_ret = 0.0
            obs = env.reset()
            replay.start_episode()

        # ---- learn -----------------------------------------------------------------------
        if frames >= cfg.num_seed_frames and frames % cfg.update_every_frames == 0:
            try:
                # The BUFFER is passed, not an iterator: the DrQ-v2 family wants
                # `next(replay_iter)` and the SAC family wants an object with `.sample()`.
                # Each adapter builds its own view, so the trainer stays algorithm-agnostic.
                agent.update(replay, frames, batch_size=cfg.batch_size)
                n_updates += 1
            except RuntimeError as e:
                if "no sampleable transition" not in str(e):
                    raise

        # ---- evaluate --------------------------------------------------------------------
        if frames >= next_eval:
            _do_eval(protocol, agent, logger, frames, cfg, baseline, spec, verbose)
            logger.log_train(frames=frames, n_updates=n_updates,
                             return_mean=float(np.mean(ep_returns[-10:])) if ep_returns else None)
            evaluated_at.add(frames)
            while next_eval <= frames:
                next_eval += protocol.eval_every_frames

        if frames >= next_save:
            _save(agent, ckpt_path, protocol, frames, n_updates)
            next_save += cfg.save_every_frames

    # Final evaluation, at exactly total_frames -- but only if the loop did not already evaluate
    # at this frame count. Evaluating twice at one x writes two sets of episodes under the same
    # `frames`, which silently doubles the episode count of the final point and makes its
    # confidence interval narrower than the protocol says it is.
    _save(agent, ckpt_path, protocol, frames, n_updates)
    if frames not in evaluated_at:
        _do_eval(protocol, agent, logger, frames, cfg, baseline, spec, verbose,
                 weights=checkpoint_fingerprint(ckpt_path))
        logger.log_train(frames=frames, n_updates=n_updates,
                         return_mean=float(np.mean(ep_returns[-10:])) if ep_returns else None)
    logger.close()
    env.close()
    if verbose:
        print(f"[train] done: {frames:,} frames, {n_updates:,} updates, "
              f"{time.time() - t0:.0f}s -> {logger.logdir}")
    return logger.logdir


def _do_eval(protocol, agent, logger, frames, cfg, baseline, spec, verbose, weights=None):
    """Both curves, from the SAME evaluator, differing only in the protocol's mode and scenes."""
    if hasattr(agent, "train"):
        agent.train(False)
    p = protocol.replace(weights_source=weights or f"in_memory@{frames}")
    det = protocol.policy_mode == "deterministic"
    pol = policy_for(agent, det)

    tr = evaluate(p, pol, mode=protocol.train_mode, scene_ids=protocol.train_scene_ids,
                  frames=frames, checkpoint=str(frames), baseline=baseline,
                  backbone=spec.backbone, backend=cfg.backend,
                  progress=(lambda s: print(s)) if verbose else None)
    ev = evaluate(p, pol, mode=protocol.eval_mode, scene_ids=protocol.eval_scene_ids,
                  frames=frames, checkpoint=str(frames), baseline=baseline,
                  backbone=spec.backbone, backend=cfg.backend,
                  progress=(lambda s: print(s)) if verbose else None)
    # One log call per curve, then the gap is derived centrally by the logger.
    logger.log_episodes(tr.records)
    logger.log_scalars(tr.scalars, frames)
    logger.log_eval(ev, frames)
    if verbose:
        print(f"[eval ] {frames:>8,} frames | train {tr.scalars.get(tags.TRAIN_EVAL_RETURN_MEAN, float('nan')):8.3f} "
              f"| {protocol.eval_mode} {ev.scalars.get(tags.EVAL_RETURN_MEAN, float('nan')):8.3f}")
    if hasattr(agent, "train"):
        agent.train(True)


def _save(agent, path, protocol, frames, n_updates):
    import torch
    sd = agent.state_dict() if hasattr(agent, "state_dict") else {}
    torch.save({"agent": sd, "protocol": protocol.to_dict(), "frames": frames,
                "n_updates": n_updates, "schema": 1}, path)
