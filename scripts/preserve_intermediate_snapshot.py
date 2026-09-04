#!/usr/bin/env python3
"""Keep the 50k snapshot that a 100k run is about to overwrite. [C68](../docs/CONSTRUCTION.md#c68)

    python scripts/preserve_intermediate_snapshot.py --match num_train_frames=100000 --seed 7

## Why this exists

The five RL-ViGen natives save at `global_step % int(5e4) == 0` (`train.py:309`) to one path,
`snapshot.pt`, and there is no end-of-run save. A 100 000-frame run therefore writes its 50k
weights and then **overwrites them** with its 100k weights, leaving no trace that the earlier
point ever existed. The cadence is not settable -- C68 -- so the only way to keep both is to copy
the file out from beside the run.

That matters here for one specific reason. [C73](../docs/CONSTRUCTION.md#c73) established that 50k
sits below the learning threshold and 100k above it, but on **n = 1**: only the archived
(and C54-contaminated) run has checkpoints at both budgets, and its own entry lists as an honest
limit that nothing says whether the threshold sits in the same place for `svea` or `drq`. If each
100k run keeps its own 50k point, that n = 1 becomes n = 4, *within run* -- same seed, same
trajectory, same contamination status, only the budget differing. Pairing against the older 50k
cells would not be the same comparison: those were separate launches, some with different `use_tb`
settings, and after C70 we know the runtime does not reproduce a trajectory bit-for-bit anyway.

## What it does not do

It does not touch the training process, its arguments, or its outputs -- it copies a file the
trainer has finished writing. It also **refuses to preserve a snapshot from a NaN-diverged run**
(delegating that judgement to `watch_divergence.inspect`, never reimplementing it) and says so, but
it does not delete the file the trainer wrote: removing evidence is not this script's job. That is the same standing as `watch_training_frames.py`: an
observation instrument beside the run, not a deviation inside it. It never deletes anything and it
refuses to overwrite an existing preserved copy, because a second 50k save (there is none at these
budgets, but the code should not assume its own reading of the cadence) must not silently replace
the first.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "RL-ViGen-upstream" / "exp_local"


def _divergence():
    """`watch_divergence`, loaded by path because `scripts/` is not a package.

    Composed rather than reimplemented: this file must not grow its own opinion about what a
    diverged run looks like, or the two instruments will drift and one of them will be wrong
    without anything noticing.
    """
    spec = importlib.util.spec_from_file_location(
        "_wd", pathlib.Path(__file__).with_name("watch_divergence.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


WD = _divergence()


def stable(p: pathlib.Path, checks: int = 3, gap: float = 5.0) -> bool:
    """True once the file's size stops changing -- torch.save is not atomic."""
    last = -1
    for _ in range(checks):
        try:
            cur = p.stat().st_size
        except FileNotFoundError:
            return False
        if cur != last:
            last = cur
            time.sleep(gap)
        else:
            return True
    return p.stat().st_size == last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--match", required=True,
                    help="substring the run directory name must contain, e.g. num_train_frames=100000")
    ap.add_argument("--seed", default=None, help="also require seed=<N> in the directory name")
    ap.add_argument("--name", default="snapshot_50k_frames.pt", help="name for the preserved copy")
    ap.add_argument("--seconds", type=float, default=40000.0)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--stable-gap", type=float, default=5.0,
                    help="seconds between size checks; lowered by the test so a real end-to-end "
                         "run of this script finishes inside a test, rather than the test "
                         "re-implementing the logic it is supposed to be checking")
    a = ap.parse_args()

    root = pathlib.Path(a.root)
    started = time.time()
    # Only directories created after this instrument started are eligible: an older run's
    # snapshot.pt is already final, and copying it would fabricate a "preserved" point that this
    # run never produced.
    seen_before = {p.parent for p in root.rglob("snapshot.pt")} if root.exists() else set()
    done: set[pathlib.Path] = set()

    print(f"watching {root} for '{a.match}'"
          f"{' seed=' + a.seed if a.seed else ''}; {len(seen_before)} pre-existing run dirs ignored",
          flush=True)

    while time.time() - started < a.seconds:
        for snap in sorted(root.rglob("snapshot.pt")):
            d = snap.parent
            if d in seen_before or d in done:
                continue
            if a.match not in d.name:
                continue
            if a.seed is not None and f"seed={a.seed}" not in d.name:
                continue
            dest = d / a.name
            if dest.exists():
                done.add(d)
                continue
            if not stable(snap, gap=a.stable_gap):
                continue

            # A snapshot from a NaN-diverged run is not a network (C57), and preserving one files
            # 100 MB of NaNs under a name that reads like a measurement. That happened on
            # 2026-08-26: a `drqv2` seed-7 run was NaN from frame 7 000 and its 50k snapshot was
            # preserved anyway, because this instrument only knew about file sizes. The check is
            # delegated to `watch_divergence`, never reimplemented here.
            code, why = WD.inspect(d)
            if code == WD.DEAD:
                done.add(d)
                print(f"REFUSED  {dest.name} for {d.name[:60]}: {why}. A checkpoint from a "
                      "diverged run is not a network (C57), so it is not preserved as one. The "
                      "file the trainer wrote is left untouched -- deleting evidence is not this "
                      "script's job.", flush=True)
                continue
            blind = " [divergence UNCHECKABLE: no loss columns in train.csv -- run "
            blind += "check_checkpoint_finite.py before trusting this]" if code == WD.BLIND else ""
            shutil.copy2(snap, dest)
            done.add(d)
            print(f"PRESERVED {dest}  ({dest.stat().st_size/1e6:.0f} MB) at "
                  f"{time.strftime('%H:%M:%S')}"
                  + (blind if code == WD.BLIND else ""), flush=True)
        time.sleep(a.interval)

    print(f"done; preserved {len(done)} snapshot(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
