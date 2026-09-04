"""The on-policy training loop, for the PPO-family baselines.

WHY A SECOND TRAINER. `rlgen/trainer.py` is off-policy: a replay buffer, and one gradient step
every few frames. PPO-family methods (IDAAC, PPG, IBAC-SNI) collect a fixed-length rollout, compute
GAE over it, take several epochs of minibatch updates, and throw it away. Those are different
loops, and pretending otherwise is how an on-policy method ends up quietly trained off-policy.

WHAT IS SHARED, AND WHY THAT IS THE WHOLE POINT. Everything the supervisor's brief requires to be
identical:

    the evaluator          rlgen.evaluate.evaluate      -- the same function, the same protocol
    the logger             rlgen.logging_.RunLogger     -- the same tags, the same episodes.csv
    the protocol           rlgen.protocol.Protocol      -- the same hash, so numbers are comparable
    the eval cadence       protocol.eval_every_frames   -- the same x-axis
    the budget             protocol.total_frames        -- frames, with action_repeat folded in

Only the *experience collection* differs, which is exactly the thing the brief allows to differ
("если это не противоречит каким то особенностям обучения алгоритма"). A run from this trainer and
a run from the off-policy one carry the same protocol hash and can sit in the same table.

FRAMES ARE STILL FRAMES. `num_steps * num_envs * action_repeat` frames per update. The budget is
counted the same way as everywhere else, so "500k frames" means the same thing for PPG as for
DrQ-v2 -- even though the two do very different amounts of learning with them. That difference is
real and belongs in the write-up, not in the accounting (docs/TASK.md section 6).

ONE ENVIRONMENT. RL-ViGen's robosuite calls `GlobalHydra.clear()` on every construction and needs
its GL backend chosen before mujoco is imported, so environments cannot be built concurrently in
one interpreter (rlgen/envs.py). This loop therefore runs `num_envs=1` and pays for it in
wall-clock rather than in correctness. Multiplying it out means one subprocess per environment;
the seam is ready for that and it is not done here.
"""
from __future__ import annotations

import os
import time

import numpy as np

from . import tags
from .agents import policy_for
from .envs import make_env, spec_from_protocol
from .evaluate import checkpoint_fingerprint
from .logging_ import RunLogger
from .protocol import Protocol
from .trainer import TrainConfig, _do_eval, _save


def train_onpolicy(protocol: Protocol, baseline: str, cfg: TrainConfig, hyper: dict, logdir: str,
                   *, verbose: bool = True) -> str:
    import torch

    from . import registry
    spec = registry.get(baseline)
    if not spec.trainable:
        raise SystemExit(f"baseline {baseline!r} has status {spec.status!r} and cannot be trained.")

    problems = registry.check_data_requirements(baseline)
    if problems:
        raise SystemExit(f"baseline {baseline!r} cannot TRAIN here -- missing data:\n"
                         + "\n".join(f"  - {p}" for p in problems))

    # SEED THE GLOBAL RNGS -- same fix and same reason as rlgen/trainer.py (2026-08-14): nothing
    # here ever called torch.manual_seed, so `protocol.seed` did not control weight
    # initialisation despite being threaded through as `hyper["seed"]`. See that file's comment
    # for the measurement that found it.
    import random
    torch.manual_seed(protocol.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(protocol.seed)
    np.random.seed(protocol.seed)
    random.seed(protocol.seed)

    device = torch.device(cfg.resolve_device())
    env_spec = spec_from_protocol(protocol, mode=protocol.train_mode,
                                  scene_id=protocol.train_scene_ids[0], seed=protocol.seed,
                                  backend=cfg.backend)
    env = make_env(env_spec)
    act_dim = env.act_dim
    agent = spec.build(protocol, protocol.obs_shape, act_dim, str(device),
                       {**hyper, "seed": protocol.seed})

    # FIXED 2026-08-14 (docs/REGISTER.md). Used to hardcode `from .algos.idaac.storage import
    # RolloutStorage` unconditionally, for every on-policy baseline -- silently routing ppg/
    # ibac_sni through IDAAC's own buffer regardless of which Learner they'd actually built,
    # contrary to `porting-directive.md` §1 ("buffers are never shared") and defeating the point
    # of those modules having their own `storage.py` at all. Each hermetic Learner now declares
    # its own `storage_cls`; read it off the already-constructed agent instead.
    RolloutStorage = agent.learner.storage_cls
    num_steps = int(hyper.get("num_steps", 256))
    storage = RolloutStorage(num_steps, 1, protocol.obs_shape, act_dim, device)

    logger = RunLogger(logdir, protocol, baseline=baseline)
    if verbose:
        print(f"[train] {baseline} (on-policy) on {protocol.task} | device={device} | "
              f"{protocol.total_frames:,} frames | rollout {num_steps} | protocol {protocol.hash()}")

    learner = agent.learner
    gamma = float(hyper.get("gamma", 0.999))
    gae_lambda = float(hyper.get("gae_lambda", 0.95))

    obs = env.reset()
    storage.init_obs(obs[None])
    frames, n_updates, update_idx = 0, 0, 0
    ep_ret, ep_returns = 0.0, []
    t0 = time.time()
    ckpt = os.path.join(logger.logdir, "checkpoint.pt")

    _do_eval(protocol, agent, logger, 0, cfg, baseline, spec, verbose)
    logger.log_train(frames=0, n_updates=0)
    evaluated_at = {0}
    next_eval, next_save = protocol.eval_every_frames, cfg.save_every_frames

    while frames < protocol.total_frames:
        # ---- collect one rollout ----------------------------------------------------------
        # The budget is a HARD stop, not a lower bound. Collection breaks the moment `frames`
        # reaches it, so an on-policy run ends at exactly `total_frames` like every off-policy
        # one -- previously it ran to the end of the rollout that crossed the budget and finished
        # at 3072 where the others finished at 3000, putting the final points of two curves at
        # different x in the same panel (instruction.md section 8b).
        # A rollout cut short is NOT used for an update: a shorter final batch would be a real,
        # if small, algorithmic change, and the run is over anyway.
        rollout_complete = True
        for _t in range(num_steps):
            if frames >= protocol.total_frames:
                rollout_complete = False
                break
            ob = torch.as_tensor(obs[None], device=device)
            with torch.no_grad():
                action, logprob = learner.policy.act(ob, deterministic=False)
                value = learner.value_of(ob)
            a = np.clip(action.squeeze(0).cpu().numpy().astype(np.float32), -1.0, 1.0)
            nxt, reward, terminated, truncated, _info = env.step(a)
            ep_ret += reward
            frames += protocol.action_repeat

            done = bool(terminated or truncated)
            # Door/Lift never terminate early, so every end is a time limit and the value of the
            # final observation must be bootstrapped through. storage.insert folds
            # gamma * truncated * boot_value into the stored reward.
            boot = torch.zeros((1, 1), device=device)
            if truncated:
                with torch.no_grad():
                    boot = learner.value_of(torch.as_tensor(nxt[None], device=device))
            # FIXED 2026-08-14 (docs/REGISTER.md, "reward-normalizer placement decision"). Used
            # to pass raw `reward` to BOTH storage args -- `porting-directive.md` §2: the
            # reference's own reward normalizer is part of the algorithm and stays, but only for
            # what training consumes. `storage.rewards_raw` stays genuinely untouched (what the
            # harness/measurement sees, already accumulated into `ep_ret` above, unaffected);
            # `storage.rewards` (what GAE/`compute_returns` reads) now goes through each hermetic
            # Learner's own `normalize_reward` -- a real transcription on `idaac`, an explicit
            # guarded no-op on `ctrl` (still shared-core, task #21), tracked placeholder no-ops on
            # `ppg`/`ibac_sni` (tasks #22/#23) until their own reference mechanisms are wired.
            reward_for_training = learner.normalize_reward(reward, done)
            storage.insert(
                torch.as_tensor(nxt[None], device=device), action, logprob, value,
                torch.tensor([float(reward_for_training)], device=device),
                torch.tensor([float(reward)], device=device),
                torch.tensor([float(done)], device=device),
                torch.tensor([float(truncated)], device=device),
                boot, gamma)
            obs = nxt
            if done:
                ep_returns.append(ep_ret)
                ep_ret = 0.0
                obs = env.reset()

        # ---- one update over the rollout ---------------------------------------------------
        if not rollout_complete:
            break
        with torch.no_grad():
            next_value = learner.value_of(torch.as_tensor(obs[None], device=device))
        storage.compute_returns(next_value, gamma, gae_lambda)
        learner.set_lr(min(1.0, frames / max(1, protocol.total_frames)))
        learner.update(storage, update_idx)
        storage.after_update()
        update_idx += 1
        n_updates += 1

        # ---- evaluate, on the SHARED cadence with the SHARED evaluator ----------------------
        if frames >= next_eval:
            _do_eval(protocol, agent, logger, frames, cfg, baseline, spec, verbose)
            logger.log_train(frames=frames, n_updates=n_updates,
                             return_mean=float(np.mean(ep_returns[-10:])) if ep_returns else None)
            evaluated_at.add(frames)
            while next_eval <= frames:
                next_eval += protocol.eval_every_frames
        if frames >= next_save:
            _save(agent, ckpt, protocol, frames, n_updates)
            next_save += cfg.save_every_frames

    _save(agent, ckpt, protocol, frames, n_updates)
    if frames not in evaluated_at:
        _do_eval(protocol, agent, logger, frames, cfg, baseline, spec, verbose,
                 weights=checkpoint_fingerprint(ckpt))
        logger.log_train(frames=frames, n_updates=n_updates,
                         return_mean=float(np.mean(ep_returns[-10:])) if ep_returns else None)
    logger.close()
    env.close()
    if verbose:
        print(f"[train] done: {frames:,} frames, {n_updates:,} updates, "
              f"{time.time() - t0:.0f}s -> {logger.logdir}")
    return logger.logdir
