#!/usr/bin/env python3
"""Do the evaluation regimes actually differ from training? Measured, with a control.

    python scripts/probe_regimes.py                 # all four regimes, Door
    python scripts/probe_regimes.py --task Lift --episodes 3

This is `docs/CONSTRUCTION.md` C19. It exists because the entire project rests on a claim nobody
had measured: that `eval-easy` / `eval-medium` / `eval-hard` present a *different visual
distribution* from `train`. If they do not, then "generalisation" is measuring noise and every
training run after that is wasted compute.

## What the regimes are supposed to do

Read from `RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/utils.py:67-90`:

    train         nothing randomised
    eval-easy     colour + lighting randomised
    eval-medium   + moving light, and the robot itself is included
    eval-hard     + moving light + video background

`tests/test_real_env.py::test_eval_modes_actually_look_different_from_train` already proves the
env *constructs* differently. That is a different claim from "the observation distribution
moved", and only the second one makes a generalisation number mean anything.

## The design, which is the whole point

A between-regime distance on its own is uninterpretable. Two samples drawn from the *same*
regime with different seeds already differ — initial states differ, and in the eval regimes the
per-episode randomisation differs too. So:

  * **within-regime**  distance(regime, seed A) vs (regime, seed B)   <- the control
  * **between-regime** distance(train, seed A)  vs (regime, seed A)

The verdict is a RATIO, not a distance: between / within. A ratio near 1 means the regimes are
not separated no matter what the config sets. This is the positive-control discipline in
`docs/rl-experiment-runbook.md` applied to an environment rather than an algorithm.

## What this cannot see

It measures the *marginal intensity distribution*, not semantics. Two scenes could differ
structurally while sharing a histogram, and this would under-report. It is therefore a ONE-SIDED
instrument: a large ratio is evidence of separation, a small one is not proof of its absence.
Stated because the asymmetry decides how the number may be used.

It also measures what a RANDOM policy sees. A trained policy visits a different part of the
state space, so this is the separation available at initialisation, not the separation a
converged agent experiences.
"""
from __future__ import annotations

import argparse
import itertools
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import histogram_tv_distance  # noqa: E402

REGIMES = ("train", "eval-easy", "eval-medium", "eval-hard")


def _setup_env_path() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    rlv = root / "RL-ViGen-upstream"
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for p in (str(rlv), str(rlv / "envs" / "robosuiteVGB")):
        if p not in sys.path:
            sys.path.insert(0, p)


def collect(task: str, mode: str, seed: int, episodes: int, frames_per_ep: int,
            stride: int) -> np.ndarray | None:
    """Frames from a random policy: (N, C, H, W) uint8, or None if the env cannot be built."""
    import robosuitevgb.utils as ru
    try:
        env = ru.make_env(task_name=task, seed=seed, scene_id=0, mode=mode)
    except Exception as e:                       # say so, never substitute a guess
        print(f"    could not build {mode!r}: {type(e).__name__}: {str(e)[:70]}")
        return None

    rng = np.random.default_rng(seed)
    out = []
    for ep in range(episodes):
        obs = env.reset()                        # randomisation, where there is any, happens here
        out.append(np.asarray(obs["rgb"], dtype=np.uint8))
        for step in range(frames_per_ep * stride):
            act = env.action_space.sample()
            act = np.asarray(act, dtype=np.float64) * 0 + rng.uniform(-1, 1, size=np.shape(act))
            obs, _, done, _ = env.step(act)
            if step % stride == 0:
                out.append(np.asarray(obs["rgb"], dtype=np.uint8))
            if done:
                break
    return np.stack(out) if out else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="Door")
    ap.add_argument("--episodes", type=int, default=3, help="episodes per sample")
    ap.add_argument("--frames", type=int, default=6, help="frames kept per episode")
    ap.add_argument("--stride", type=int, default=8, help="env steps between kept frames")
    ap.add_argument("--size", default="84", help="render resolution")
    ap.add_argument("--ratio-threshold", type=float, default=2.0,
                    help="between/within below this is reported as NOT SEPARATED")
    a = ap.parse_args()

    _setup_env_path()
    os.environ["RLVIGEN_IMAGE_SIZE"] = str(a.size)

    print(f"\nPROBE -- regime separation, task {a.task}, render {a.size}, random policy")
    print(f"  {a.episodes} episodes x {a.frames} frames per sample, two seeds per regime\n")

    # Two independent samples per regime. Seed A is used for the between-regime comparison,
    # seed B only to establish what "different for reasons that are not the regime" looks like.
    samples: dict[tuple[str, str], np.ndarray] = {}
    for mode in REGIMES:
        for tag, seed in (("A", 0), ("B", 1)):
            print(f"  collecting {mode:12} seed {tag} ...", flush=True)
            s = collect(a.task, mode, seed, a.episodes, a.frames, a.stride)
            if s is not None:
                samples[(mode, tag)] = s

    if ("train", "A") not in samples:
        print("\n  train could not be built, so there is no reference to compare against.")
        print("  A SKIP is not a pass: nothing about regime separation was measured.")
        return 1

    print(f"\n  {'regime':<13}{'within':>9}{'vs train':>10}{'ratio':>8}   verdict")
    print("  " + "-" * 66)
    within: dict[str, float] = {}
    for mode in REGIMES:
        if (mode, "A") not in samples or (mode, "B") not in samples:
            continue
        within[mode] = histogram_tv_distance(samples[(mode, "A")], samples[(mode, "B")])

    base = within.get("train", float("nan"))
    bad = 0
    for mode in REGIMES:
        if (mode, "A") not in samples:
            continue
        w = within.get(mode, float("nan"))
        if mode == "train":
            print(f"  {mode:<13}{w:>9.4f}{'--':>10}{'--':>8}   the control")
            continue
        b = histogram_tv_distance(samples[("train", "A")], samples[(mode, "A")])
        # Compare against the LARGER of the two within-regime numbers: the honest denominator is
        # the most variation attributable to something other than the regime change.
        denom = max(w, base, 1e-9)
        ratio = b / denom
        ok = ratio >= a.ratio_threshold
        bad += 0 if ok else 1
        print(f"  {mode:<13}{w:>9.4f}{b:>10.4f}{ratio:>8.1f}x   "
              f"{'separated' if ok else 'NOT SEPARATED at this threshold'}")

    print(f"\n  within-regime distance is the control: two samples of the SAME regime, different")
    print(f"  seeds. A between/within ratio near 1 means the regime change moved the observation")
    print(f"  distribution no more than re-seeding does, whatever the config sets.")
    if bad:
        print(f"\n  {bad} regime(s) below {a.ratio_threshold}x. Before spending training compute,")
        print("  establish why -- a generalisation gap cannot be measured across regimes that")
        print("  are not distinguishable at the input.")
    else:
        print("\n  All regimes separated. This licenses the generalisation measurement at the")
        print("  INPUT level only; it says nothing about whether a policy's behaviour differs.")
    print("\n  One-sided instrument: a large ratio is evidence of separation; a small one is not")
    print("  proof of its absence, because two scenes can differ structurally and share a")
    print("  histogram. And this is what a RANDOM policy sees, not a trained one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
