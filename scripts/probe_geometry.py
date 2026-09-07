#!/usr/bin/env python3
"""Measure the two structural differences between the twelve, instead of arguing about them.

    python scripts/probe_geometry.py                 # both probes
    python scripts/probe_geometry.py --actions-only  # no env needed, runs anywhere

`docs/AUDIT-2026-08-17.html` names two splits it could only describe:

  Finding 5  frame stacking splits the twelve 8/4, and a single frame on a manipulation task is
             "velocity-blind" -- an argument, with no number attached.
  Finding 6  four baselines bound their actions only by robosuite's `np.clip`, so mass outside
             the box is folded onto the boundary while the policy's likelihood treats it as
             interior -- again, no number.

This measures both.

## Probe 1: how much motion does a stacked observation actually carry

Builds the real RL-ViGen robosuite env, steps it, and reports `interframe_absdiff` for a
3-frame stack: the mean |pixel difference| between consecutive frames inside one observation.
That number IS the motion signal a stacked baseline receives and a single-frame one does not.
Reported at each render size in use, because field of view differs too.

## Probe 2: how much of the action distribution the environment clips

Needs no environment. For each of the three action-distribution families the audit identifies,
draw actions the way that family draws them at initialisation and measure the fraction of
COMPONENTS on the boundary. The unsquashed-Gaussian answer is also available in closed form,
which is why this probe can check itself: for log_std = 0 and a box of [-1, 1],

    P(|z| >= 1) = 2 * (1 - Phi(1)) = 0.3173

so ~32% of action components are clipped at step 0 for the four authored heads, against ~0 for
the tanh-squashed families. The probe asserts the empirical value against that closed form, so a
wrong sampler shows up as a mismatch rather than as a plausible number.

## What this cannot see

Probe 1 measures an *untrained* interaction: a random policy moves the arm differently from a
trained one, so the number is a floor on available motion, not the motion a converged policy
would see. Probe 2 measures initialisation only; saturation moves as `log_std` is learned, and
whether it moves up or down is exactly the thing worth watching during a real run.
"""
from __future__ import annotations

import argparse
import math
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import action_saturation_frac, interframe_absdiff  # noqa: E402


def probe_actions(n: int = 200_000, dim: int = 7, seed: int = 0) -> int:
    rng = np.random.default_rng(seed)
    print("\nPROBE 2 -- action mass the environment clips, at initialisation")
    print(f"  {n:,} samples, action dim {dim}, box [-1, 1], all heads at log_std = 0\n")
    print(f"  {'family':<34}{'baselines':<30}{'saturated':>10}")
    print("  " + "-" * 74)

    # Unsquashed Gaussian, bounded only by robosuite's controller clip. The four authored heads.
    g = rng.normal(0.0, 1.0, size=(n, dim))
    f_gauss = action_saturation_frac(g)
    print(f"  {'unsquashed Gaussian + env clip':<34}{'ppg idaac ibac_sni ctrl':<30}{f_gauss:>9.1%}")

    # SAC: tanh applied to the SAMPLE, so the density lives on (-1, 1) and never reaches it.
    f_sac = action_saturation_frac(np.tanh(rng.normal(0.0, 1.0, size=(n, dim))))
    print(f"  {'SAC squashed Gaussian':<34}{'rad soda alda':<30}{f_sac:>9.1%}")

    # DrQv2: tanh on the MEAN, then truncated noise clipped into the box. std=0.1 is the low end
    # of RL-ViGen's own linear schedule; at that scale saturation comes from the mean, not noise.
    mu = np.tanh(rng.normal(0.0, 1.0, size=(n, dim)))
    f_drq = action_saturation_frac(np.clip(mu + np.clip(rng.normal(0, 0.1, (n, dim)), -0.3, 0.3),
                                           -1, 1))
    print(f"  {'DrQv2 tanh-mean + trunc. noise':<34}{'drqv2 svea sgqn curl drq':<30}{f_drq:>9.1%}")

    closed_form = 2 * (1 - 0.5 * (1 + math.erf(1 / math.sqrt(2))))
    ok = abs(f_gauss - closed_form) < 0.005
    print(f"\n  closed form for the unsquashed case, P(|z|>=1) = 2(1-Phi(1)) = {closed_form:.4f}")
    print(f"  empirical {f_gauss:.4f} -> {'MATCHES' if ok else 'MISMATCH -- the sampler is wrong'}")
    print(f"\n  So at initialisation roughly one action component in three is decided by the\n"
          f"  environment's clip rather than by the policy, for ppg / idaac / ibac_sni / ctrl,\n"
          f"  and effectively none for the other eight.")
    return 0 if ok else 1


def probe_observation(task: str = "Door", steps: int = 60) -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    rlv = root / "RL-ViGen-upstream"
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for p in (str(rlv), str(rlv / "envs" / "robosuiteVGB")):
        if p not in sys.path:
            sys.path.insert(0, p)

    print("\nPROBE 1 -- motion carried by a stacked observation")
    print(f"  task {task}, {steps} random-policy steps per size, 3-frame stack\n")
    print(f"  {'render':>8}  {'used by':<34}{'interframe_absdiff':>20}")
    print("  " + "-" * 64)

    USERS = {64: "alda ppg idaac ibac_sni ctrl", 84: "drqv2 svea sgqn curl drq",
             100: "rad soda (cropped to 84)"}
    rows = []
    for size in (64, 84, 100):
        os.environ["RLVIGEN_IMAGE_SIZE"] = str(size)
        try:
            import importlib
            import robosuitevgb.utils as ru
            importlib.reload(ru)
            env = ru.make_env(task_name=task, seed=0, scene_id=0, mode="train")
        except Exception as e:                       # env unavailable -> say so, do not guess
            print(f"  {size:>8}  env could not be built: {type(e).__name__}: {str(e)[:60]}")
            continue
        obs = env.reset()
        frames = [np.asarray(obs["rgb"], dtype=np.uint8)]
        for _ in range(steps):
            obs, _, done, _ = env.step(env.action_space.sample())
            frames.append(np.asarray(obs["rgb"], dtype=np.uint8))
            if done:
                obs = env.reset()
        # Stack every consecutive triple the way FrameStack would, and average.
        vals = [interframe_absdiff(np.concatenate(frames[i:i + 3], axis=0), 3)
                for i in range(len(frames) - 3)]
        v = float(np.mean(vals))
        rows.append((size, v))
        print(f"  {size:>8}  {USERS[size]:<34}{v:>20.5f}")

    if rows:
        print(f"\n  A 3-frame stack at these sizes carries {min(v for _, v in rows):.4f}-"
              f"{max(v for _, v in rows):.4f} mean absolute pixel change per step.")
        print("  ppg / idaac receive the selected C2 three-frame stack; ibac_sni / ctrl retain\n"
              "  one frame. Historical C1 for ppg / idaac is explicit only: frame_stack=1.")
    return 0


def probe_network_size() -> int:
    """PROBE 3 -- how much NETWORK an input-resolution choice buys, without anyone typing a size.

    `docs/AUDIT-2026-08-17.html` §4 argues that our format choices propagate into layer widths,
    because several of these architectures DEFINE their widths as a function of the input shape.
    `ibac_sni` is the clean case, because its resolution is the one that is ours rather than a
    reference's, and because the dependence is a single line:

        model.py:83   image_embedding_size = ((n-1)//2-2) * ((m-1)//2-2) * 64

    Its conv trunk is four small layers and does not depend on n at all. Everything downstream
    does. So this constructs the real ACModel at three resolutions and counts parameters. Run in
    a subprocess with the clone's own sys.path, like probe_heads.py, for the same reason.
    """
    print("\nPROBE 3 -- network size as a function of input resolution (ibac_sni)")
    print("  its conv trunk is fixed; everything after it is a function of n\n")
    code = """
import gym, numpy as np
from model import ACModel
box = gym.spaces.Box(-1, 1, (7,), np.float32)
for n in (7, 64, 84):
    m = ACModel({"image": (n, n, 3)}, box)
    print("ROW", n, m.image_embedding_size,
          sum(p.numel() for p in m.image_conv.parameters()),
          sum(p.numel() for p in m.parameters()))
"""
    root = pathlib.Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": ":".join([
        str(root / "runnable" / "ibac_sni" / "torch_rl"),
        str(root / "runnable" / "ibac_sni" / "torch_rl" / "torch_rl")])}
    import subprocess
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                       timeout=600)
    rows = [l.split()[1:] for l in r.stdout.splitlines() if l.startswith("ROW")]
    if not rows:
        why = (r.stderr.strip().splitlines() or ["no output"])[-1][:70]
        print(f"  SKIP -- could not construct ACModel: {why}")
        print("  A SKIP is not a pass: nothing about network size was measured.")
        return 0

    print(f"  {'input':>9}{'embedding':>12}{'conv params':>14}{'TOTAL params':>15}   note")
    print("  " + "-" * 74)
    NOTE = {7: "MiniGrid native -- what the architecture was written for",
            64: "OURS -- the one resolution not taken from a reference",
            84: "the RL-ViGen five's resolution, for comparison"}
    base = None
    for n, emb, conv, tot in ((int(a), int(b), int(c), int(d)) for a, b, c, d in rows):
        base = tot if base is None else base
        print(f"  {f'{n}x{n}':>9}{emb:>12,}{conv:>14,}{tot:>15,}   {NOTE.get(n, '')}")
    tots = {int(a): int(d) for a, _, _, d in rows}
    if 7 in tots and 64 in tots:
        print(f"\n  The conv trunk is IDENTICAL at every resolution ({int(rows[0][2]):,} params).")
        print(f"  Choosing 64x64 over MiniGrid's 7x7 multiplies the model by "
              f"{tots[64] / tots[7]:.0f}x -- {tots[64]:,} parameters against {tots[7]:,} --")
        print("  and every one of those parameters is in a fully-connected head fed by a\n"
              "  flattened conv output the architecture expected to be 64-dimensional.")
        print("  Nobody typed a layer size. The resolution was the layer size.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actions-only", action="store_true",
                    help="skip the env probe (needs no robosuite install)")
    ap.add_argument("--task", default="Door")
    ap.add_argument("--steps", type=int, default=60)
    a = ap.parse_args()
    rc = probe_actions()
    rc |= probe_network_size()          # needs no env, so it runs even with --actions-only
    if not a.actions_only:
        rc |= probe_observation(a.task, a.steps)
    return rc


if __name__ == "__main__":
    sys.exit(main())
