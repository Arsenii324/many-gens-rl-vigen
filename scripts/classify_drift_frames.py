#!/usr/bin/env python3
"""Classify each training episode's reset frame by which render condition it matches.

Answers the question [C54](../docs/CONSTRUCTION.md#c54) leaves open: a run's training
observations are supposed to come from one fixed condition, and the only long run this project
has ended in a different one from the one its config named. Whether that happens gradually,
at a point, or not at all is not decidable from an archived run -- drqv2's loader unlinks each
episode once consumed, so nothing survives from the middle. Frames must be copied out live.

Classification is per-pixel against freshly rendered reset frames for all twenty regime x scene
combinations. Channel means are NOT enough: on the one case checked by hand they put the true
condition (2.63) and a wrong one (3.48) within 0.9 of each other, while per-pixel separated the
same pair 7.60 vs 18.61. The weak statistic is the one a reader will reach for, so the strong
one is the only one computed here.

The per-episode initial object placement is randomised, so a single frame's distance carries
real noise. A verdict is therefore reported per episode, but a SWITCH is only reported when the
nearest condition changes and stays changed -- one episode's disagreement is placement noise,
not a transition.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMES = ROOT / "results" / "drift-frames"
CACHE = ROOT / "results" / "drift-references.npz"
MODES = ("train", "eval-easy")
SCENES = range(10)
RUN_LENGTH = 3          # episodes a new verdict must persist before it counts as a switch

# Beyond this L1 the "nearest" condition is not a match, it is just the least-bad of twenty. A
# genuine match lands at 4-12 (measured across four cells); a drq run produced five frames whose
# nearest reference was 57-68 away and was reported as `eval-easy|2`, which reads as live
# provenance drift and is nothing of the kind -- those frames simply resemble no rendered
# condition, most likely because of arm occlusion. Nearest-neighbour with no reject option will
# always name something.
UNMATCHED_ABOVE = 25.0


def build_references(path: pathlib.Path, draws: int = 3) -> dict:
    """Render every condition. Cached, because it costs ~2 minutes and never changes."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import eval_across_scenes as E
    E._setup()
    from wrappers.robo_wrapper import robo_make
    refs = {}
    for mode in MODES:
        for sc in SCENES:
            env = robo_make(name="Door", action_repeat=1, frame_stack=3, seed=1,
                            scene_id=sc, mode=mode)
            # Several draws, kept separately: a condition is a distribution, not a point, and
            # eval-easy re-randomises per episode. Matching uses the closest draw.
            refs[f"{mode}|{sc}"] = np.stack(
                [np.asarray(env.reset().observation)[-3:].astype(np.uint8)
                 for _ in range(draws)])
            print(f"  rendered {mode:<10} scene {sc}", flush=True)
    np.savez_compressed(path, **refs)
    return {k: v for k, v in refs.items()}


def load_references() -> dict:
    if CACHE.exists():
        z = np.load(CACHE)
        return {k: z[k] for k in z.files}
    print(f"rendering references -> {CACHE}")
    return build_references(CACHE)


def classify(frame: np.ndarray, refs: dict) -> list[tuple[float, str]]:
    """Rank conditions by distance to their CLOSEST draw, nearest first.

    Closest-draw rather than mean-draw: eval-easy re-randomises every reset, so its draws are a
    spread and a frame belongs to the condition if it is near ANY of them. Averaging the draws
    first would compare against a blur that no episode ever looked like.
    """
    f = frame.astype(np.float32)
    ranked = []
    for key, draws in refs.items():
        stack = draws if draws.ndim == 4 else draws[None]
        ranked.append((min(float(np.abs(f - d.astype(np.float32)).mean()) for d in stack), key))
    ranked.sort()
    return ranked


def main() -> int:
    if not FRAMES.exists() or not any(FRAMES.glob("*.npy")):
        print(f"no frames in {FRAMES}. Run a training job with the watcher attached.")
        return 1
    refs = load_references()
    fns = sorted(FRAMES.glob("*.npy"), key=lambda p: int(p.stem[2:]))
    print(f"\n{len(fns)} episode(s) captured\n")
    print(f"  {'episode':>8}  {'nearest condition':<20} {'L1':>7}  {'runner-up':<20} {'L1':>7}")
    print(f"  {'-'*70}")
    verdicts = []
    for p in fns:
        ranked = classify(np.load(p), refs)
        (d0, k0), (d1, k1) = ranked[0], ranked[1]
        if d0 > UNMATCHED_ABOVE:
            k0 = f"UNMATCHED(>{UNMATCHED_ABOVE:.0f})"
        verdicts.append(k0)
        ep = int(p.stem[2:])
        if len(fns) <= 40 or ep % max(1, len(fns) // 40) == 0:
            print(f"  {ep:>8}  {k0:<20} {d0:7.2f}  {k1:<20} {d1:7.2f}")

    first = verdicts[0]
    n_un = sum(1 for v in verdicts if v.startswith("UNMATCHED"))
    if n_un:
        print(f"\n  {n_un} episode(s) match NO reference within L1 {UNMATCHED_ABOVE:.0f} and are")
        print("  reported as UNMATCHED rather than assigned to the least-bad condition.")
    print(f"\n  first episode matches: {first}")
    switch = None
    for i in range(len(verdicts) - RUN_LENGTH + 1):
        w = verdicts[i:i + RUN_LENGTH]
        if w[0] != first and len(set(w)) == 1:
            switch = (i, w[0])
            break
    if switch is None:
        print(f"  NO SUSTAINED SWITCH across {len(verdicts)} episodes "
              f"(a verdict must hold {RUN_LENGTH} episodes to count).")
        odd = sum(v != first for v in verdicts)
        print(f"  {odd} episode(s) disagreed transiently -- placement noise, not a transition.")
    else:
        i, k = switch
        print(f"  SWITCH at episode {int(fns[i].stem[2:])}: {first} -> {k}, sustained.")
    tally = {}
    for v in verdicts:
        tally[v] = tally.get(v, 0) + 1
    print("\n  tally: " + ", ".join(f"{k} x{n}" for k, n in
                                    sorted(tally.items(), key=lambda t: -t[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
