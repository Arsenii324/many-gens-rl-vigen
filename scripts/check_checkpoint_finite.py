#!/usr/bin/env python3
"""Is this checkpoint a network, or 7.4M NaNs? [C57](../docs/CONSTRUCTION.md#c57).

A `drqv2` run diverged to NaN around frame 35,000, then trained for 70,000 more frames, logged
seven evaluations, and wrote a snapshot. Every artifact this project keeps -- eval.csv,
train.csv, the snapshot itself -- was indistinguishable from a run that merely trained badly.
The weights were the only place the difference was visible, and nothing looked at them.

The tell in the logs, once you know to read it, is **standard deviation 0.00 across episodes**:
`nan` actions clip to the same constant, so a dead run scores identically every episode where a
bad policy would still vary. Two independent seeds landed on 0.69 to the digit.

Run this on any snapshot before believing a number computed from it:

    python scripts/check_checkpoint_finite.py path/to/snapshot.pt
    python scripts/check_checkpoint_finite.py --all      # every snapshot under exp_local

Exit code is 1 if any checkpoint is non-finite, so it can gate a pipeline.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


# A checkpoint is a pickle of an agent OBJECT for most of these baselines, so unpickling it needs
# that baseline's own modules importable -- and **those namespaces collide**. dmc_gb ships
# `utils` and `algorithms`; so does RL-ViGen. Putting both on one `sys.path` makes RL-ViGen
# snapshots fail with `cannot import name 'random_overlay' from 'utils'`, which is the hermetic
# problem this project is built around, appearing inside a diagnostic script.
#
# So each checkpoint is opened in its OWN subprocess with only its own baseline's paths. That is
# slower and it is the only correct shape: no ordering of a shared path serves all twelve.
PATHS_FOR = {
    "RL-ViGen-upstream": ("", "algos", "envs/robosuiteVGB"),
    "runnable/dmc_gb": ("src",),
    "runnable/alda": ("", "dmcontrol_generalization_benchmark/src"),
    "runnable/idaac": ("",),
    "runnable/ppg": ("",),
    "runnable/ibac_sni": ("",),
}

_PROBE = r"""
import json, sys, pathlib, torch
root, rel = sys.argv[1], sys.argv[2].split(":")
for r in rel:
    q = str(pathlib.Path(root) / r) if r else root
    sys.path.insert(0, q)
sys.path.insert(0, %r)
try:
    payload = torch.load(open(sys.argv[3], "rb"), map_location="cpu", weights_only=False)
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {str(e)[:70]}"})); raise SystemExit(0)
agent = payload.get("agent") if isinstance(payload, dict) else payload
step = payload.get("_global_step", -1) if isinstance(payload, dict) else -1
mods = {}
for name, mod in vars(agent).items():
    if not isinstance(mod, torch.nn.Module):
        continue
    bad = tot = 0
    for _, v in mod.state_dict().items():
        f = v.float()
        bad += int(torch.isnan(f).sum() + torch.isinf(f).sum()); tot += f.numel()
    if tot:
        mods[name] = [bad, tot]
print(json.dumps({"step": step, "modules": mods,
                  "bad": sum(b for b, _ in mods.values()),
                  "total": sum(t for _, t in mods.values())}))
"""


def _paths_for(path: pathlib.Path):
    sp = str(path)
    for key, rels in PATHS_FOR.items():
        if key in sp:
            return str(ROOT / key), rels
    # Fallback: the checkpoint's own directory. A pickled agent class often lives beside the
    # file, and it costs nothing when it does not.
    return str(path.parent), ("",)


def inspect(path: pathlib.Path) -> dict:
    import json
    import subprocess
    base, rels = _paths_for(path)
    shim = str(ROOT / "runnable" / "_shim")
    env = dict(os.environ)
    env.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    env.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    out = subprocess.run([sys.executable, "-c", _PROBE % shim, base, ":".join(rels), str(path)],
                         capture_output=True, text=True, timeout=300, env=env)
    line = next((l for l in out.stdout.splitlines() if l.startswith("{")), None)
    if line is None:
        raise RuntimeError((out.stderr.strip().splitlines() or ["no output"])[-1][:80])
    d = json.loads(line)
    if "error" in d:
        raise RuntimeError(d["error"])
    d["modules"] = {k: tuple(v) for k, v in d["modules"].items()}
    return d


def scan_buffers() -> int:
    """NaN in the stored ACTIONS. The agent's output, recorded as it was taken.

    Confirmed against a run whose weights were separately verified NaN: 3500 of 3507 action
    values in its last stored episode were `nan`, against 0 of 3507 for a healthy run at the same
    budget. Cheaper and earlier than the weights, and available when no snapshot exists.
    """
    import numpy as np
    bufs = sorted((ROOT / "RL-ViGen-upstream" / "exp_local").glob("*/*/buffer"))
    seen = worst = 0
    for d in bufs:
        fs = sorted(d.glob("*.npz"))
        if not fs:
            continue
        try:
            a = np.load(fs[-1])["action"].astype(np.float32)
        except Exception as e:
            print(f"  UNREADABLE  {d.parent.name[:40]}: {type(e).__name__}")
            worst = 1
            continue
        seen += 1
        bad = int(np.isnan(a).sum() + np.isinf(a).sum())
        tag = "DEAD" if bad > a.size // 2 else ("PARTIAL" if bad else "finite")
        if bad:
            worst = 1
        print(f"  {tag:<8} {bad:>6}/{a.size:<6} non-finite actions  ep {fs[-1].name.split('_')[1]:>4}"
              f"  {d.parent.name[:44]}")
    if not seen:
        print("  no stored episodes found. A SKIP is not a pass: nothing was checked.")
        return 1
    if worst:
        print("\n  An agent was emitting NaN actions. The run continued; see C57.")
    return worst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--all", action="store_true",
                    help="every snapshot*.pt under RL-ViGen-upstream/exp_local")
    ap.add_argument("--buffers", action="store_true",
                    help="scan stored replay episodes for NaN ACTIONS instead. Works on runs too "
                         "short to checkpoint -- train.py:309 only saves every 50k steps, so a "
                         "40k run has no snapshot at all, and the buffer is the only witness.")
    a = ap.parse_args()

    if a.buffers:
        return scan_buffers()
    if a.all:
        paths = sorted((ROOT / "RL-ViGen-upstream" / "exp_local").rglob("snapshot*.pt"))
    elif a.path:
        paths = [pathlib.Path(a.path)]
    else:
        print("give a snapshot path or --all")
        return 2
    if not paths:
        print("no snapshots found. A SKIP is not a pass: nothing was checked.")
        return 1

    worst = unreadable = 0
    for p in paths:
        try:
            r = inspect(p)
        except Exception as e:
            # UNREADABLE is NOT the same verdict as DEAD, and the summary below must not merge
            # them: one says the weights are NaN, the other says this checker could not look.
            # Printing "not a network" for a file it failed to open is the same overclaim this
            # instrument exists to prevent.
            print(f"  UNREADABLE  {p.name}: {type(e).__name__}: {str(e)[:60]}")
            unreadable += 1
            worst = 1
            continue
        frac = r["bad"] / r["total"] if r["total"] else 0.0
        tag = "DEAD" if frac > 0.5 else ("PARTIAL" if r["bad"] else "finite")
        if r["bad"]:
            worst = 1
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        print(f"  {tag:<8} step {r['step']:>7}  {r['bad']:>9}/{r['total']:<9} non-finite  "
              f"{str(rel)[-58:]}")
        if r["bad"]:
            for m, (b, t) in r["modules"].items():
                if b:
                    print(f"           {m:<16} {b}/{t}")
    readable_bad = worst and (unreadable < len(paths))
    if unreadable:
        print(f"\n  {unreadable} checkpoint(s) could not be OPENED -- unpickling needs that "
              f"baseline's own modules on the path.")
        print("  That is a gap in this checker, not a verdict about those weights. Nothing is")
        print("  claimed about them either way.")
    if readable_bad:
        print("\n  Where a checkpoint WAS readable and reported DEAD: it is not a network, and")
        print("  any number computed from it is not a measurement of a policy. See C57.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
