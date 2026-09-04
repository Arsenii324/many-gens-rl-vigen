#!/usr/bin/env python3
"""RL-ViGen's own published robosuite numbers, read from the file already in the tree.

    python scripts/rlvigen_reference.py

`RL-ViGen-upstream/results/evaluation_score.xlsx` ships with the benchmark and contains the
authors' evaluation scores: sheet `Robosuite`, 5 seeds, three regimes, seven methods, door and
lift. This reads it rather than transcribing it, because a number retyped into a document is a
number that can drift from its source -- a failure this project has already caught three times.

It is the ceiling reference for `docs/CONSTRUCTION.md` C31 and the evidence for C32.

**These are RETURNS, not success rates**, and that is itself the finding recorded as C33: the
benchmark's own endpoint is not the one this project reports.

**Two numbers from different systems are not the same quantity until shown to be.** These were
produced under RL-ViGen's configuration; ours are not verified to match it on budget,
action_repeat, robot, scene or episode length. Use this to bound what is reachable and as a
reproduction target -- not to subtract from our numbers.
"""
from __future__ import annotations

import pathlib
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
XLSX = ROOT / "RL-ViGen-upstream" / "results" / "evaluation_score.xlsx"
# measured by scripts/probe_floor.py, 25 random episodes, OUR configuration
OUR_RANDOM = {"door": (1.633, 6.933), "lift": (6.562, 34.647)}


def read(sheet: str = "Robosuite") -> dict:
    import openpyxl
    ws = openpyxl.load_workbook(XLSX, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    out: dict[str, list] = {}
    for i, r in enumerate(rows):
        head = str(r[0]).strip().lower() if r and r[0] is not None else ""
        if head not in ("door", "lift"):
            continue
        label = ""
        for j in range(i - 1, -1, -1):
            c = rows[j][0]
            if c and str(c).strip().lower() not in ("door", "lift", "twoarm", "none"):
                label = str(c).strip()
                break
        vals = [c for c in r[1:6] if isinstance(c, (int, float))]
        if vals:
            out.setdefault(head, []).append((label, vals))
    return out


def main() -> int:
    if not XLSX.exists():
        print(f"absent: {XLSX}")
        return 1
    data = read()
    for task in ("door", "lift"):
        rmean, rmax = OUR_RANDOM[task]
        print(f"\n=== {task.upper()} -- RL-ViGen published, mean over 5 seeds ===")
        print(f"  our random-policy floor, OUR config: mean {rmean:.2f}, max {rmax:.2f}")
        print(f"\n  {'method / regime':<22}{'mean':>9}{'sd':>8}{'min':>6}{'max':>6}")
        print("  " + "-" * 53)
        for label, vals in data[task]:
            sd = st.stdev(vals) if len(vals) > 1 else 0.0
            print(f"  {label:<22}{st.mean(vals):>9.1f}{sd:>8.1f}{min(vals):>6g}{max(vals):>6g}")
    print("\n  These are RETURNS. The benchmark does not publish success rates for robosuite,")
    print("  which is C33. And they come from RL-ViGen's configuration, not ours -- a bound on")
    print("  what is reachable and a reproduction target, not a baseline to subtract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
