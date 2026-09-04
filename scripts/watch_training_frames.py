#!/usr/bin/env python3
"""Copy each training episode's reset frame out of the replay buffer before it is deleted.

`replay_buffer.py:94` hardcodes `self._save_snapshot = False`, so `_store_episode` unlinks every
episode file the moment the loader has consumed it -- `cfg.save_snapshot=True` does not change
this. What survives in a run's `buffer/` is therefore whichever episodes had not yet been
fetched when the run stopped, i.e. its last few. **A run cannot testify about its own middle**,
which is exactly the interval [C54](../docs/CONSTRUCTION.md#c54) needs to see.

Attach this alongside a run and it keeps 3x84x84 uint8 per episode -- 21KB against ~860KB for
the full episode, so a 240-episode run costs ~5MB instead of 200MB. That ratio is the reason
this exists rather than a patch making the buffer keep everything: no upstream deviation, no
protocol hash change, and the SSD is not filled by a diagnostic.

    python scripts/watch_training_frames.py --out results/drift-frames --seconds 16000

It is deliberately dumb about which run it watches: any buffer under `exp_local` matching
`--match`. Two concurrent runs writing the same episode numbers would collide, so `--match`
should name one of them.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Where runs land. RL-ViGen's five write here; the clones write under runnable/<baseline>/.
# Hardcoding only the first meant a watcher attached to a clone cell searched a tree the clone
# never writes to, captured nothing, and said nothing -- see C62.
EXP = ROOT / "RL-ViGen-upstream" / "exp_local"


def sweep(out: pathlib.Path, match: str, seen: set, search_all: bool = True) -> int:
    """One pass. Returns how many new episodes were captured."""
    n = 0
    # Computed here, not at import, so a test monkeypatching EXP still controls the search.
    roots = (EXP, ROOT / "runnable") if search_all else (EXP,)
    for buf in [b for r in roots for b in r.rglob("buffer") if b.is_dir()]:
        if match and match not in str(buf):
            continue
        for f in sorted(buf.glob("*.npz")):
            if f.name in seen:
                continue
            try:
                obs = np.load(f)["observation"]
            except Exception:
                # Half-written, or unlinked between glob and load. Both are normal: leave it
                # out of `seen` so the next sweep retries rather than losing the episode.
                continue
            try:
                ep = int(f.name.split("_")[1])
            except (IndexError, ValueError):
                continue
            np.save(out / f"ep{ep:05d}.npy", obs[0, -3:].astype(np.uint8))
            seen.add(f.name)
            n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "drift-frames"))
    ap.add_argument("--seconds", type=float, default=3600.0)
    ap.add_argument("--interval", type=float, default=4.0,
                    help="sweep period. Must be well under the time it takes the loader to "
                         "consume an episode, or episodes are lost between sweeps.")
    ap.add_argument("--match", default="num_train_frames=",
                    help="substring identifying the run directory to watch")
    a = ap.parse_args(argv)

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    seen: set = set()
    deadline = time.time() + a.seconds
    total = 0
    while time.time() < deadline:
        total += sweep(out, a.match, seen)
        time.sleep(a.interval)
    print(f"captured {total} episode(s) into {out}")
    if total == 0:
        # Silence is the defect this guard exists for. A watcher that matched nothing and exited
        # 0 let a clone cell be produced with NO provenance while the run reported success.
        print("  CAPTURED NOTHING. Either the run wrote no episode files where this looked, or")
        print(f"  --match {a.match!r} matches no run directory. Any cell built from this run has")
        print("  UNVERIFIED provenance -- do not treat it as checked. See C58 for which")
        print("  baselines can be witnessed at all.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
