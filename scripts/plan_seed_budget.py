#!/usr/bin/env python3
"""How large a difference can N seeds actually resolve? -- `docs/CONSTRUCTION.md` C18.

C18 observes that the current reporting is one seed and ten episodes, and that `bootstrap_ci`
resamples *episodes within a run*, which says nothing about the seed-to-seed term. This script
estimates that term from the only paired evidence this project has -- C41's two runs of the same
configuration and the same seed, evaluated at matched frame counts -- and converts it into the
number the plan actually needs: **the smallest difference a given seed budget can detect**.

## Why this is an estimate and not a result

One pair of runs. Nine checkpoints from that pair, which are successive points on the same two
trajectories and therefore **not independent samples**. The estimator also assumes the two runs
are exchangeable draws from one distribution -- which is exactly C41's reading ("two noisy samples
of one learning curve") but is an assumption, not a measurement.

So every number here is indicative and should be read as C41 asks its own to be read: *at least
this much*. A second pair of runs would improve it more than any refinement of the arithmetic.

**The conservatism has a direction, which is the useful part.** C41's two runs share a
configuration AND a seed, so their disagreement is backend nondeterminism with no seed
contribution at all. Real seed-to-seed variation adds a different initialisation and a different
exploration path on top of that and cannot be smaller. Every CV here is therefore a floor, every
"seeds required" is a floor, and the error makes a given budget look **better** than it is.

## The estimator

For paired runs A, B of the same configuration, `E|A - B| = sigma_diff * sqrt(2/pi)` under
normality, and `sigma_diff = sigma * sqrt(2)` for two independent runs of variance `sigma^2`.
Working in relative terms gives a coefficient of variation for a single run's return. The
two-sample detectable difference at 5% significance and 80% power is then
`d = z * CV * sqrt(2/n)` with `z = 2.802`.

**Returns, not success rate.** At these budgets C41 found success rate flipping both ways between
paired runs (1.0 vs 0.4 at 80k), so it carries no signal to plan against. C33 made return the
reported endpoint, which is also the quantity this can be estimated for.
"""
from __future__ import annotations

import argparse
import math
import statistics as st

Z_80_POWER = 2.802

# C41, `docs/REGISTER.md` 2026-08-18: (frame, run A return, run B return). Same config, same seed,
# same machine, runs a day apart. Frames 0 and 10k agreed exactly and are omitted -- they are
# pre-divergence and would bias the spread downward.
C41_PAIRS = [
    (20_000, 5.809078, 5.677693), (30_000, 57.443439, 50.096433),
    (40_000, 70.4576, 104.6356), (50_000, 89.5000, 118.6335),
    (60_000, 121.0673, 179.5595), (70_000, 242.7015, 253.0373),
    (80_000, 292.5496, 232.7729), (90_000, 365.3291, 447.6736),
    (100_000, 469.4089, 436.2104),
]


def cv_from_pairs(pairs) -> float:
    """Coefficient of variation of a single run's return, from paired disagreements."""
    rels = [abs(a - b) / ((a + b) / 2) for _, a, b in pairs]
    return st.mean(rels) / math.sqrt(2 / math.pi) / math.sqrt(2)


def detectable(cv: float, n: int, z: float = Z_80_POWER) -> float:
    """Smallest relative difference two arms of `n` seeds each can separate."""
    return z * cv * math.sqrt(2 / n)


def seeds_for(cv: float, d: float, z: float = Z_80_POWER) -> int:
    return math.ceil(2 * (z * cv / d) ** 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-frame", type=int, default=0,
                    help="use only checkpoints at or after this frame (late ones are quieter)")
    a = ap.parse_args()
    pairs = [p for p in C41_PAIRS if p[0] >= a.from_frame]
    if len(pairs) < 2:
        print("need at least two checkpoints"); return 1
    cv = cv_from_pairs(pairs)
    print(f"  {len(pairs)} paired checkpoints from {pairs[0][0]:,} frames")
    print(f"  CV of one run's return at a matched checkpoint: {100*cv:.1f}%\n")
    print("  seed budget -> smallest RELATIVE difference in return it can resolve")
    for n in (1, 3, 5, 10, 20, 50):
        print(f"    n = {n:>3} seeds/arm  ->  {100*detectable(cv, n):>5.1f}%")
    print("\n  inverse: seeds needed for a target difference")
    for d in (0.05, 0.10, 0.20, 0.50):
        print(f"    {int(100*d):>3}%  ->  {seeds_for(cv, d):>5} seeds/arm")
    print("\n  One pair of runs, non-independent checkpoints: read as 'at least this much'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
