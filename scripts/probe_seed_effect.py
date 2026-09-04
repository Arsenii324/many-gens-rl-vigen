#!/usr/bin/env python3
"""What does the env `seed` argument actually control? -- C20 screen (b), env side.

Reading `robosuitevgb/utils.py` and `vgb_wrapper.py` says: `make_env(..., seed=s)` stores
`self.random_state = np.random.RandomState(s)`, and that stream is consumed ONLY by the colour,
camera, lighting and dynamics modders. In `mode='train'` all four `randomize_*` flags are False,
so `self.modders` is empty and `except_robot` is True -- nothing draws from the stream. If that
reading is right, the env seed changes nothing during training, and the run-to-run variation a
seed is supposed to control comes from the GLOBAL numpy/torch RNGs instead.

That is a claim about mechanism, so it is checked by running the mechanism.

## Design

Three axes, crossed, because a claim measured at one point on an axis is a claim about that
point:

    env_seed     0 vs 1      the argument under test
    global_seed  0 vs 1      np/random/torch, reset immediately before construction and reset
    mode         train vs eval-easy

**The positive control is the eval-easy arm.** In eval-easy the randomizers are on, so the env
seed MUST change the observation there. If it does not, this probe cannot detect an env-seed
effect at all and the train-mode result is uninterpretable rather than null -- which is reported
as UNINTERPRETABLE, not as "no effect". A null without a stated detectable effect is an
unfinished measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import sys

import numpy as np


def fingerprint(obs) -> str:
    a = np.asarray(obs, dtype=np.uint8) if not isinstance(obs, dict) else \
        np.concatenate([np.asarray(v).ravel() for v in obs.values()])
    return hashlib.sha1(np.ascontiguousarray(a)).hexdigest()[:16]


def one(robo_make, *, env_seed: int, global_seed: int, mode: str, task: str,
        scene_id: int = 0) -> dict:
    """Reset every global stream, then build and reset, so the only free variables are the axes."""
    import torch
    np.random.seed(global_seed)
    random.seed(global_seed)
    torch.manual_seed(global_seed)
    env = robo_make(name=task, frame_stack=3, action_repeat=1, seed=env_seed, mode=mode,
                    scene_id=scene_id)
    np.random.seed(global_seed)          # again: construction consumes draws
    random.seed(global_seed)
    ts = env.reset()
    obs = ts.observation if hasattr(ts, "observation") else ts
    a = np.asarray(obs)
    return {"env_seed": env_seed, "global_seed": global_seed, "mode": mode,
            "fp": fingerprint(obs), "mean": round(float(a.mean()), 6),
            "shape": list(a.shape)}


def summarise(rows: list[dict]) -> dict:
    """Per mode: does env_seed move the observation? does global_seed?"""
    out = {}
    for mode in sorted({r["mode"] for r in rows}):
        m = [r for r in rows if r["mode"] == mode]

        def moves(axis: str) -> bool:
            """True iff changing `axis` changes the fingerprint with the other axis held fixed."""
            other = "global_seed" if axis == "env_seed" else "env_seed"
            for v in sorted({r[other] for r in m}):
                held = sorted([r for r in m if r[other] == v], key=lambda r: r[axis])
                if len({r["fp"] for r in held}) > 1:
                    return True
            return False

        out[mode] = {"env_seed_moves_it": moves("env_seed"),
                     "global_seed_moves_it": moves("global_seed"),
                     "distinct_observations": len({r["fp"] for r in m}), "conditions": len(m)}
    ctrl = out.get("eval-easy", {}).get("env_seed_moves_it")
    if ctrl is None:
        verdict = "NO_CONTROL_RUN: eval-easy arm absent, nothing calibrates the null"
    elif not ctrl:
        verdict = ("UNINTERPRETABLE: the env seed does not move the observation even in "
                   "eval-easy, where the randomisers are on. This probe cannot detect an "
                   "env-seed effect, so the train-mode result is not a null.")
    elif out.get("train", {}).get("env_seed_moves_it"):
        verdict = "ENV_SEED_CONTROLS_TRAIN: the reading of vgb_wrapper.py was wrong."
    else:
        verdict = ("ENV_SEED_INERT_IN_TRAIN: confirmed against a control that fired -- the env "
                   "seed changes eval-easy observations and not train observations.")
    return {"per_mode": out, "verdict": verdict}


def scene_axis(robo_make, task: str, modes, scenes=(0, 7)) -> dict:
    """Does `scene_id` move the observation, per mode?

    Asked because C51 says training happens on one visual instance, and it matters *why*: if the
    scene axis were dead in train mode, giving IDAAC's labels a visual referent (C50 option 2)
    would need new machinery. If it is live and merely unused, the option costs one argument.
    """
    out = {}
    for mode in modes:
        fps = {sc: one(robo_make, env_seed=0, global_seed=0, mode=mode, task=task, scene_id=sc)
               for sc in scenes}
        out[mode] = {"moves": len({r["fp"] for r in fps.values()}) > 1,
                     "means": {sc: r["mean"] for sc, r in fps.items()}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="Door")
    ap.add_argument("--modes", default="train,eval-easy")
    ap.add_argument("--scenes", action="store_true",
                    help="also test whether scene_id moves the observation, per mode")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.eval_across_scenes import _setup
    _setup()
    from wrappers.robo_wrapper import robo_make

    rows = []
    for mode, es, gs in itertools.product(a.modes.split(","), (0, 1), (0, 1)):
        r = one(robo_make, env_seed=es, global_seed=gs, mode=mode, task=a.task)
        rows.append(r)
        print(f"  mode={r['mode']:<10} env_seed={es} global_seed={gs}  fp={r['fp']}  "
              f"mean={r['mean']}", flush=True)
    if a.scenes:
        sc = scene_axis(robo_make, a.task, a.modes.split(","))
        print("\n  scene axis:")
        for mode, r in sc.items():
            print(f"    {mode:<10} scene_id moves the observation: "
                  f"{'YES' if r['moves'] else 'NO'}   means={r['means']}")
    s = summarise(rows)
    print("\n" + json.dumps(s["per_mode"], indent=2))
    print("\nVERDICT:", s["verdict"])
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"rows": rows, **s}, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
