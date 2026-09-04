#!/usr/bin/env python3
"""Do WE and RL-ViGen's own evaluation loop return the same number for the same policy?

    python tools/crosscheck_against_rlvigen_eval.py [--episodes-per-scene 3] [--task Door]

WHY THIS EXISTS. Everything establishing that our evaluator is correct is a *structural* argument:
one stepping loop, an opaque policy, a hashed protocol, tests that mutate labels and require
identical numbers. All true, and none of it is evidence that the number agrees with an independent
implementation on the same input.

RL-ViGen's `eval.py::robo_eval` is the closest thing to a reference that exists for this benchmark.
This script runs the SAME policy through both:

  * OURS   -- rlgen.evaluate.evaluate(), the full stack: Protocol, spec_from_protocol, RoboEnv,
              run_episode, summarize.
  * THEIRS -- a faithful transcription of robo_eval's loop calling `robo_make` DIRECTLY, bypassing
              every line of rlgen. 10 episodes per scene, scene switched every 10 episodes across
              ids 0..9, deterministic policy, pooled mean over all episodes.

A random policy is used deliberately. It needs no checkpoint, it is exactly reproducible from a
seed, and it exercises the entire path that a trained policy would -- env construction in a given
mode and scene, the reward path, time-limit termination, and aggregation. If the two disagree, the
disagreement is in the harness, which is the thing under test.

WHAT AGREEMENT WOULD AND WOULD NOT SHOW. Agreement to within sampling error shows our harness does
not systematically distort the quantity. It does NOT show the protocol is the right one to have
chosen -- that is docs/PREMISES.md P4 and is a separate argument.
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
UPSTREAM = os.path.join(ROOT, "RL-ViGen-upstream")


def _make_policy(seed: int, act_dim: int):
    """A deterministic-per-episode random policy: identical for both evaluators."""
    rng = np.random.default_rng(seed)
    return lambda obs: rng.uniform(-1.0, 1.0, size=act_dim).astype(np.float32)


def theirs(task: str, mode: str, scenes, episodes_per_scene: int, seed: int,
           action_repeat: int, frame_stack: int) -> list[float]:
    """RL-ViGen's robo_eval loop, transcribed, calling robo_make directly.

    Their loop rebuilds the env when it switches scene (`self.eval_env = robo_make(...)`) and steps
    `while not time_step.last()`, accumulating `time_step.reward`. Both are reproduced here.
    """
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    for p in (UPSTREAM, os.path.join(UPSTREAM, "envs", "robosuiteVGB")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from wrappers.robo_wrapper import robo_make

    returns: list[float] = []
    for scene in scenes:
        env = robo_make(name=task, frame_stack=frame_stack, action_repeat=action_repeat,
                        seed=seed, scene_id=scene, mode=mode)
        try:
            # action_spec is a METHOD on RL-ViGen's wrapper, not a property (robo_wrapper.py:58).
            act_dim = int(env.action_spec().shape[0])
            policy = _make_policy(seed, act_dim)
            for _ep in range(episodes_per_scene):
                ts = env.reset()
                total = 0.0
                while not ts.last():
                    ts = env.step(policy(ts.observation))
                    total += float(ts.reward)
                returns.append(total)
        finally:
            try:
                env.close()
            except Exception:
                pass
    return returns


def ours(task: str, mode: str, scenes, episodes_per_scene: int, seed: int) -> list[float]:
    from rlgen.evaluate import evaluate
    from rlgen.protocol import Protocol
    p = Protocol(task=task, seed=seed, eval_scene_ids=tuple(scenes),
                 episodes_per_scene=episodes_per_scene)
    policy = _make_policy(seed, 7)
    res = evaluate(p, policy, mode=mode, scene_ids=scenes,
                   episodes_per_scene=episodes_per_scene)
    return [float(x) for x in res.returns]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="Door")
    ap.add_argument("--mode", default="eval-easy")
    ap.add_argument("--episodes-per-scene", type=int, default=3)
    ap.add_argument("--scenes", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    scenes = [int(x) for x in args.scenes.split(",")]

    from rlgen.protocol import DEFAULT_ACTION_REPEAT, DEFAULT_FRAME_STACK

    print(f"task={args.task} mode={args.mode} scenes={scenes} "
          f"episodes/scene={args.episodes_per_scene} seed={args.seed}\n")

    print("running OURS   (rlgen.evaluate) ...", flush=True)
    a = ours(args.task, args.mode, scenes, args.episodes_per_scene, args.seed)
    print("running THEIRS (robo_make direct, robo_eval loop) ...", flush=True)
    b = theirs(args.task, args.mode, scenes, args.episodes_per_scene, args.seed,
               DEFAULT_ACTION_REPEAT, DEFAULT_FRAME_STACK)

    if not a or not b:
        print("FATAL: one side produced no episodes; a comparison of nothing is not a result.",
              file=sys.stderr)
        return 2

    ma, mb = st.mean(a), st.mean(b)
    sa = st.stdev(a) if len(a) > 1 else 0.0
    sb = st.stdev(b) if len(b) > 1 else 0.0
    # Standard error of the difference of two independent means.
    se = ((sa ** 2) / len(a) + (sb ** 2) / len(b)) ** 0.5
    z = abs(ma - mb) / se if se > 0 else float("inf")

    print(f"\n{'':8s} {'n':>4s} {'mean':>10s} {'sd':>10s} {'median':>10s}")
    print("-" * 46)
    print(f"{'OURS':8s} {len(a):4d} {ma:10.4f} {sa:10.4f} {st.median(a):10.4f}")
    print(f"{'THEIRS':8s} {len(b):4d} {mb:10.4f} {sb:10.4f} {st.median(b):10.4f}")
    print(f"\ndifference of means : {ma - mb:+.4f}")
    print(f"SE of difference    : {se:.4f}")
    print(f"|z|                 : {z:.2f}")

    if z < 2.0:
        print("\nAGREE: the two evaluators are within sampling error of each other on the same "
              "policy.\nThis does NOT show the protocol is the right one -- only that our harness "
              "does not distort it.")
        return 0
    print("\nDISAGREE: |z| >= 2. The harnesses differ by more than sampling error. Investigate "
          "before\ntrusting any number from either -- likely suspects are episode length, the "
          "reward path,\ntime-limit handling, or which scene each side actually built.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
