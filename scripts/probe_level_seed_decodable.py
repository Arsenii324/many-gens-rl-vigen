#!/usr/bin/env python3
"""Can `level_seed` be decoded from an observation? The direct test of [C50](../docs/CONSTRUCTION.md#c50).

IDAAC's instance-invariance loss and its order classifier both assume `level_seed` names something
recoverable from pixels. C50 argues it does not, on this target, in train mode. That argument is
currently supported *indirectly* — by C49 showing the env seed is inert, and by C51 showing one
fixed scene. The direct question was never asked: train a classifier to predict which env an
observation came from, and see whether it beats chance.

**Positive control is the whole design, and the first one chosen was wrong.** It used `eval-easy`
as the control, on the strength of C49 measuring the env seed as live there. That control
*failed* (0.113 against a 0.125 chance) and the probe correctly refused to conclude. The reason
is a flaw in the arm, not in the target: `eval-easy` re-randomises textures **every reset**, so an
env has no single appearance and 25 resets average over exactly the variation the env seed drives.
C49 compared first observations with the global stream pinned; this compares distributions.

The control that works tests the **classifier** rather than the seed: `scene_id`. C51 measured
train-mode scenes as visually distinct (scene 0 renders ~104 mean, scene 7 ~82), so a classifier
that cannot separate scenes is blind, full stop. With that arm passing, a near-chance `level_seed`
row is a null with a stated detectable effect.

**C56-aware by construction.** Two robosuite envs in one process do not render independently, and
only the most recently built one is trustworthy. So envs are built, sampled, and dropped strictly
one at a time -- never two alive while either is read.

Classifier is nearest-centroid on downsampled frames with a held-out split: no dependency beyond
numpy, and its failures are legible. A stronger model could only *raise* accuracy, so a
near-chance result from this one is the conservative direction for C50's claim.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]


def collect(mode: str, n_envs: int, per_env: int, base_seed: int,
            vary: str = "seed") -> tuple[np.ndarray, np.ndarray]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import eval_across_scenes as E
    E._setup()
    from wrappers.robo_wrapper import robo_make
    X, y = [], []
    for i in range(n_envs):
        # idaac/ppo_daac_idaac/envs.py:101 -- `seed=args.seed + i`, one env per parallel worker.
        # vary="seed" reproduces idaac's construction; vary="scene" is the classifier control.
        env = robo_make(name="Door", action_repeat=1, frame_stack=3,
                        seed=base_seed + (i if vary == "seed" else 0),
                        scene_id=(i if vary == "scene" else 0), mode=mode)
        for _ in range(per_env):
            obs = np.asarray(env.reset().observation)[-3:].astype(np.float32)
            X.append(obs[:, ::4, ::4].ravel() / 255.0)      # 3x21x21, enough for texture identity
            y.append(i)
        del env                                             # never two alive; see C56
        print(f"    env {i} ({vary}) sampled", flush=True)
    return np.array(X), np.array(y)


def nearest_centroid(Xtr, ytr, Xte, yte, k) -> float:
    cents = np.stack([Xtr[ytr == c].mean(axis=0) for c in range(k)])
    pred = np.argmin(((Xte[:, None, :] - cents[None]) ** 2).sum(axis=2), axis=1)
    return float((pred == yte).mean())


def run(mode: str, n_envs: int, per_env: int, base_seed: int, rng, vary="seed",
        label=None) -> dict:
    print(f"  collecting {label or mode} ...", flush=True)
    X, y = collect(mode, n_envs, per_env, base_seed, vary)
    idx = rng.permutation(len(y))
    X, y = X[idx], y[idx]
    cut = int(0.6 * len(y))
    acc = nearest_centroid(X[:cut], y[:cut], X[cut:], y[cut:], n_envs)
    n = len(y) - cut
    chance = 1.0 / n_envs
    # Wilson interval: at accuracies near chance with small n, the normal approximation is
    # exactly where this project has been burned before (RIGOR.md on width-zero at p=0).
    z = 1.96
    d = 1 + z * z / n
    c = (acc + z * z / (2 * n)) / d
    h = z * np.sqrt(acc * (1 - acc) / n + z * z / (4 * n * n)) / d
    return {"mode": label or mode, "acc": acc, "lo": max(0.0, c - h), "hi": min(1.0, c + h),
            "chance": chance, "n_test": n}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=8)
    ap.add_argument("--per-env", type=int, default=25)
    ap.add_argument("--base-seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(0)

    print("CAN `level_seed` BE DECODED FROM AN OBSERVATION?")
    print(f"  {a.envs} envs, seeds {a.base_seed}..{a.base_seed + a.envs - 1}, "
          f"{a.per_env} resets each, Door scene 0\n")

    out = [
        run("train", a.envs, a.per_env, a.base_seed, rng, vary="scene",
            label="scene_id (control)"),
        run("eval-easy", a.envs, a.per_env, a.base_seed, rng, label="level_seed/eval-easy"),
        run("train", a.envs, a.per_env, a.base_seed, rng, label="level_seed/train"),
    ]

    print(f"\n  {'regime':<12} {'accuracy':>9} {'95% CI':>18} {'chance':>8}  verdict")
    print(f"  {'-'*62}")
    ctrl = None
    for r in out:
        beats = r["lo"] > r["chance"]
        v = "DECODABLE" if beats else "AT CHANCE"
        if r["mode"].startswith("scene_id"):
            ctrl = beats
        print(f"  {r['mode']:<22} {r['acc']:9.3f} [{r['lo']:6.3f},{r['hi']:6.3f}] "
              f"{r['chance']:8.3f}  {v}")
    print()
    if not ctrl:
        print("  POSITIVE CONTROL FAILED. Scenes are visually distinct (C51) -- a classifier")
        print("  that cannot separate THEM is blind, so every row below it is UNINTERPRETABLE")
        print("  rather than null. Nothing is concluded.")
        return 1
    tr = [r for r in out if r["mode"] == "level_seed/train"][0]
    print(f"  Control fired, so the train row is a null with a stated detectable effect: this")
    print(f"  design resolves decodability down to {tr['hi']:.3f} against a {tr['chance']:.3f} chance.")
    print("  Scope: Door, scene 0, first observation after reset, nearest-centroid on 3x21x21.")
    print("  A stronger classifier could only raise accuracy, so a near-chance result here is")
    print("  the conservative direction for C50's claim -- not proof that no model could decode it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
