#!/usr/bin/env python3
"""How far above its own untrained policy did each cell get?

    python scripts/learning_over_random.py <records.jsonl | run-dir | results/records>

## Why this exists

On 2026-09-09 I wrote that a baseline "did not learn Door" because its return curve ended where it
began. It had in fact reached **12-25x** a random policy, almost all of it in the first 51,200
frames, and then plateaued. The correct finding -- a plateau after fast early learning -- is nearly
the opposite reading and far more useful, and the only thing separating them is a **floor**.

That floor is free and nobody was collecting it. Every family's curve evaluation scores its
**frame-0 checkpoint**, which is the randomly initialised policy, under the same evaluator as every
other stamp. Measured that way on `ppg`: **train 2.24, eval-easy 1.98, eval-medium 1.54,
eval-hard 2.04** over 60 episodes per regime.

So this turns "did it learn" from a judgement into a division, per cell and per regime, for all
twelve baselines, automatically.

## What it refuses to do

**It reports no ratio for a cell with no frame-0 row.** A missing floor is reported as missing, never
substituted from another cell or another family: initialisation scale is architecture-specific, and
borrowing `ppg`'s 2.24 for `ctrl` would invent a number.

**It never ranks two baselines against each other.** A ratio over one's own initialisation is a
within-cell quantity. Comparing `idaac`'s 12x to `drqv2`'s 12x says nothing unless their floors and
policy modes match, which `scripts/comparison_blocks.py` exists to adjudicate. The output is one
line per cell, deliberately not a leaderboard.

**It is not a success criterion.** Beating random is the weakest possible bar -- a plateaued run
clears it easily, which is the whole point of the story above.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

FLOOR_FRAME = 0


def _rows(target: pathlib.Path) -> list[dict]:
    files = [target] if target.is_file() else sorted(target.rglob("*.jsonl"))
    out = []
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _weighted(rows: list[dict]) -> tuple[float, int]:
    n = sum(r.get("episodes") or 0 for r in rows)
    if not n:
        return float("nan"), 0
    total = sum((r.get("episode_return_mean") or 0.0) * (r.get("episodes") or 0) for r in rows)
    return total / n, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target")
    args = ap.parse_args()

    target = pathlib.Path(args.target)
    if not target.exists():
        print(f"no such path: {target}")
        return 2

    rows = [r for r in _rows(target) if r.get("frame") is not None]
    if not rows:
        print(f"No records with a frame under {target}. Nothing was compared, which is NOT the")
        print("same as nothing having been measured.")
        return 2

    #: (cell identity) -> regime -> frame -> rows
    grouped: dict[tuple, dict[str, dict[int, list[dict]]]] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    for r in rows:
        key = (r.get("baseline"), r.get("cell"), r.get("seed"))
        grouped[key][r.get("regime")][int(float(r["frame"]))].append(r)

    print(f"LEARNING OVER OWN INITIALISATION -- {target}\n")
    missing: list[str] = []
    for key in sorted(grouped, key=str):
        baseline, cell, seed = key
        print(f"  {baseline} / {cell} / seed {seed}")
        for regime in sorted(grouped[key]):
            frames = grouped[key][regime]
            if FLOOR_FRAME not in frames:
                missing.append(f"{baseline}/{cell}/{regime}")
                print(f"    {regime:<12} NO frame-0 row -- floor unknown, ratio NOT computed")
                continue
            floor, floor_n = _weighted(frames[FLOOR_FRAME])
            last_frame = max(frames)
            best_frame = max(frames, key=lambda f: _weighted(frames[f])[0])
            last, last_n = _weighted(frames[last_frame])
            best, _ = _weighted(frames[best_frame])
            ratio = (last / floor) if floor else float("inf")
            peak = (best / floor) if floor else float("inf")
            print(f"    {regime:<12} floor {floor:>7.2f} (n={floor_n})  "
                  f"last {last:>7.2f} @{last_frame} = {ratio:>5.1f}x  "
                  f"peak {best:>7.2f} @{best_frame} = {peak:>5.1f}x")
        print()

    if missing:
        print(f"  {len(missing)} cell/regime pair(s) have NO frame-0 row, so no floor:")
        for m in missing[:10]:
            print(f"    {m}")
        print("  A floor is NOT borrowed from another cell or family -- initialisation scale is")
        print("  architecture-specific, and substituting one would invent a number.\n")

    print("  A ratio over a cell's OWN initialisation is a within-cell quantity. Two baselines'")
    print("  ratios are not comparable unless their floors and policy modes match; that is what")
    print("  scripts/comparison_blocks.py adjudicates. This is not a leaderboard, and beating")
    print("  random is the weakest bar there is -- a plateaued run clears it easily.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
