#!/usr/bin/env python3
"""Does the SCENE axis carry signal? The measurement C45 needs to be worth acting on.

    python scripts/probe_scenes.py                       # Door, eval-easy, scenes 0-9
    python scripts/probe_scenes.py --task Lift --scenes 0,1,2

This is `docs/CONSTRUCTION.md` C45. That entry establishes, from source, that RL-ViGen's own
`eval.py` sweeps ten scenes while the `train.py` we run pins `scene_id=0` — so their published
numbers average ten scenes and ours measure one. What it does NOT establish is **how much that
matters**. If scenes were near-identical, C45 would be a bookkeeping defect. If they are as
separated as the difficulty regimes are, then a single-scene number is a different quantity and
no comparison survives.

## Design, copied deliberately from `probe_regimes.py`

Same yardstick, so the two answers can be read against each other:

  * **within-scene**   distance(scene s, seed A) vs (scene s, seed B)   <- the control
  * **between-scene**  distance(scene 0, seed A) vs (scene k, seed A)

The verdict is the RATIO. At `eval-easy` the within-scene control is not zero and must not be:
colour and lighting are re-randomised every reset, so two samples of the *same* scene already
differ. That randomisation is exactly the variation our single-scene evaluation already averages
over, which makes it the right floor to measure the scene effect against.

## The positive control, which is the point of running this at all

A between-scene ratio near 1 is only interpretable if this instrument can register an effect it
is *known* to be able to see. So the mode axis is measured in the same run: `train` vs
`eval-easy` at fixed scene 0. `probe_regimes.py` puts that at **6-7x** the within-regime control
on Door, so it is a calibrated reference rather than a hope. Reported side by side:

    scene axis   ratio X   <- the unknown
    mode  axis   ratio Y   <- known separated, same instrument, same run

If the mode axis fails to separate here, the run says nothing about scenes either, and it says so
rather than reporting the scene number anyway.

## What this cannot tell you

Inherited wholesale from `probe_regimes.py`, and the limits are not smaller here:

- It measures the **marginal intensity distribution**, not semantics. Two scenes could differ
  structurally while sharing a histogram. **One-sided**: a large ratio is evidence of separation;
  a small one is not proof of its absence.
- It measures what a **random policy** sees at initialisation, not what a converged agent visits.
  A trained policy that has learned to ignore texture would experience less separation than this
  reports; one that has overfit to scene 0's texture would experience more.
- It is a statement about the observation stream, **not about return**. It cannot say how many
  points of return the scene axis is worth. That needs a trained checkpoint evaluated across
  scenes, which is the natural follow-up and is deliberately not attempted here.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import statistics as st
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import histogram_tv_distance          # noqa: E402
from scripts.probe_regimes import _setup_env_path          # noqa: E402


def collect(task: str, mode: str, scene_id: int, seed: int, episodes: int,
            frames_per_ep: int, stride: int) -> np.ndarray | None:
    """Frames from a random policy at a fixed (mode, scene). None if the env cannot be built."""
    import robosuitevgb.utils as ru
    try:
        env = ru.make_env(task_name=task, seed=seed, scene_id=scene_id, mode=mode)
    except Exception as e:                       # say so, never substitute a guess
        print(f"    could not build scene {scene_id} {mode!r}: "
              f"{type(e).__name__}: {str(e)[:70]}")
        return None
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(episodes):
        obs = env.reset()                        # per-episode randomisation happens here
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


def summarise(within: dict, between: dict, control: float | None,
              threshold: float = 2.0) -> dict:
    """Turn distances into a verdict, with the positive control able to veto it.

    Separated from `main` so it can be tested without building robosuite, and because the one
    property worth guarding is a logical one rather than a numerical one: **when the positive
    control fails, a flat scene result must NOT be reportable as "no scene effect".** Those two
    states produce the same table and mean opposite things -- one is a finding, the other is a
    broken instrument -- and collapsing them is the failure `docs/research-evidence` calls the
    single highest-value thing to check. So `interpretable` is False whenever the control is
    missing or below threshold, whatever the scene numbers look like.
    """
    floor = st.median(within.values()) if within else None
    if floor is None:
        return {"floor": None, "interpretable": False, "verdict": "NO CONTROL",
                "ratios": {}, "median_ratio": None, "control_ratio": None}
    ratios = {s: (d / floor if floor > 0 else float("inf")) for s, d in between.items()}
    control_ratio = (control / floor if floor > 0 else float("inf")) if control is not None else None
    control_ok = control_ratio is not None and control_ratio >= threshold
    med = st.median(ratios.values()) if ratios else None
    if not control_ok:
        verdict = "UNINTERPRETABLE"          # never "not separated"
    elif med is None:
        verdict = "NO SCENES COMPARED"
    else:
        verdict = "SEPARATED" if med >= threshold else "NOT SEPARATED"
    return {"floor": floor, "ratios": ratios, "median_ratio": med,
            "control_ratio": control_ratio, "control_ok": control_ok,
            "interpretable": bool(control_ok), "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="Door")
    ap.add_argument("--mode", default="eval-easy", help="regime held fixed while scene varies")
    ap.add_argument("--scenes", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--control-scenes", default="0,1,2,3",
                    help="scenes sampled twice, to establish the within-scene floor")
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--frames", type=int, default=5)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--size", default="84")
    ap.add_argument("--ratio-threshold", type=float, default=2.0)
    a = ap.parse_args()

    _setup_env_path()
    os.environ["RLVIGEN_IMAGE_SIZE"] = str(a.size)
    scenes = [int(s) for s in a.scenes.split(",")]
    controls = [int(s) for s in a.control_scenes.split(",")]

    print(f"\nPROBE -- scene separation, task {a.task}, regime {a.mode!r}, render {a.size}")
    print(f"  scenes {scenes}, within-scene control on {controls}")
    print(f"  {a.episodes} episodes x {a.frames} frames per sample, random policy\n")

    t0 = time.time()
    A: dict[int, np.ndarray] = {}
    B: dict[int, np.ndarray] = {}
    for s in scenes:
        print(f"  collecting scene {s} seed A ...", flush=True)
        v = collect(a.task, a.mode, s, 0, a.episodes, a.frames, a.stride)
        if v is not None:
            A[s] = v
        if s in controls:
            print(f"  collecting scene {s} seed B ...", flush=True)
            v = collect(a.task, a.mode, s, 1, a.episodes, a.frames, a.stride)
            if v is not None:
                B[s] = v

    # Positive control: an axis this instrument is known to resolve. It must be a DIFFERENT
    # regime from the one under test -- with `--mode train` the old hardcoded "vs train" control
    # compared train against train, measured TV 0.0245, and correctly reported FAILED. The guard
    # worked; the control was simply degenerate by construction. Found by running it.
    ctrl_mode = "eval-easy" if a.mode == "train" else "train"
    print(f"  collecting scene 0 {ctrl_mode!r} seed A  (positive control) ...", flush=True)
    train0 = collect(a.task, ctrl_mode, 0, 0, a.episodes, a.frames, a.stride)

    if 0 not in A:
        print("\n  scene 0 could not be built; there is no reference to compare against.")
        print("  A SKIP is not a pass: nothing about scene separation was measured.")
        return 1

    within = {s: histogram_tv_distance(A[s], B[s]) for s in sorted(B) if s in A}
    if not within:
        print("\n  no within-scene control could be formed. Between-scene distances alone are")
        print("  uninterpretable, so no verdict is reported.")
        return 1
    floor = st.median(within.values())

    print(f"\n  within-scene control (same scene, two seeds) -- the noise floor")
    for s, w in sorted(within.items()):
        print(f"    scene {s}: {w:.4f}")
    print(f"    median: {floor:.4f}   n={len(within)}")

    print(f"\n  {'scene':<8}{'TV vs scene 0':>16}{'ratio':>9}   verdict")
    print("  " + "-" * 52)
    ratios = []
    for s in sorted(A):
        if s == 0:
            continue
        d = histogram_tv_distance(A[0], A[s])
        r = d / floor if floor > 0 else float("inf")
        ratios.append(r)
        print(f"  {s:<8}{d:>16.4f}{r:>9.2f}   "
              f"{'separated' if r >= a.ratio_threshold else 'NOT separated'}")

    if train0 is not None:
        dm = histogram_tv_distance(A[0], train0)
        rm = dm / floor if floor > 0 else float("inf")
        print(f"\n  POSITIVE CONTROL -- mode axis at fixed scene 0 "
              f"({a.mode} vs {ctrl_mode})")
        print(f"    TV {dm:.4f}   ratio {rm:.2f}   "
              f"{'instrument resolves a known effect' if rm >= a.ratio_threshold else 'FAILED'}")
        if rm < a.ratio_threshold:
            print("    The mode axis is separated at 6-7x by scripts/probe_regimes.py. If it does")
            print("    not separate here, this run cannot speak to the scene axis either, and the")
            print("    scene numbers above should be treated as an instrument failure.")
    else:
        print("\n  POSITIVE CONTROL COULD NOT BE BUILT. Without it a flat scene result is")
        print("  uninterpretable -- it cannot be distinguished from an instrument that sees")
        print("  nothing. Do not read the table above as evidence of no scene effect.")

    if ratios:
        med = st.median(ratios)
        print(f"\n  scene axis: median ratio {med:.2f} over {len(ratios)} scenes "
              f"(min {min(ratios):.2f}, max {max(ratios):.2f})")
        # Deliberately NOT "6-7x, per C19". That ratio has a different denominator -- C19's
        # floor is a within-REGIME control at its own sample size, this one is within-SCENE at
        # this run's. Printing the two ratios side by side would invite subtracting them. The
        # comparable quantities are the raw TV distances measured in THIS run against THIS floor.
        if train0 is not None and ratios:
            med_d = st.median([histogram_tv_distance(A[0], A[s]) for s in sorted(A) if s != 0])
            print(f"\n  scene axis vs mode axis, same run and same floor (the comparable form):")
            print(f"    median between-scene TV {med_d:.4f}   vs   mode-axis TV {dm:.4f}"
                  f"   = {100 * med_d / dm:.0f}% as far")
        print(f"\n  Reading this: the ratio is between-scene distance over the SAME-scene floor.")
        print(f"  Near 1 means scene identity is not visible above per-reset randomisation, and")
        print(f"  C45 is then a bookkeeping defect. Well above 1 means a single-scene evaluation")
        print(f"  samples one point on an axis the benchmark averages over, and our numbers are")
        print(f"  not a smaller version of theirs -- they are a different quantity.")
    print(f"\n  elapsed {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
