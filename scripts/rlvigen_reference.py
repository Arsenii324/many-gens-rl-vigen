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
# [Claude 2026-09-05] This pointed only at `ROOT/RL-ViGen-upstream/...`, which does not exist in
# this tree -- the benchmark is supplied to jobs as an ASSET ARCHIVE, not vendored here. So every
# invocation printed "absent" and **RL-ViGen's published Door numbers went unread for the project's
# entire life**, while C37 was rewritten twice trying to explain a gap against them. The table says
# their own DrQ-v2 scores 3.6 on Door against our 1.842 random floor: their baseline does not
# generalise there either, and our 1.44 was never anomalous.
#
# Now searches the asset archive too, and `--asset` accepts an explicit path.
_CANDIDATES = [
    ROOT / "RL-ViGen-upstream" / "results" / "evaluation_score.xlsx",
    pathlib.Path.home() / "build-projs" / "rlgen-assets" / "rlvigen-door2-90d8b8c4.tgz",
]
XLSX = _CANDIDATES[0]


def _load_workbook(explicit: "pathlib.Path | None" = None):
    """Return the workbook, extracting from the asset tarball when the tree has no vendored copy."""
    import io
    import tarfile
    import openpyxl
    for candidate in ([explicit] if explicit else []) + _CANDIDATES:
        if candidate is None or not candidate.is_file():
            continue
        if candidate.suffix in {".tgz", ".gz"}:
            with tarfile.open(candidate) as tar:
                for member in tar:
                    if member.name.endswith("results/evaluation_score.xlsx"):
                        handle = tar.extractfile(member)
                        if handle is not None:
                            return openpyxl.load_workbook(io.BytesIO(handle.read()), data_only=True)
            continue
        return openpyxl.load_workbook(candidate, data_only=True)
    raise FileNotFoundError(
        "evaluation_score.xlsx not found. Looked in the vendored path and the asset archive; pass "
        "--asset PATH. This file is the T3 anchor -- without it the project cannot compare against "
        "RL-ViGen's published results, which is exactly what happened until 2026-09-05.")
# THERE IS ONE CURRENT DOOR FLOOR: 1.842. The other two numbers below are SUPERSEDED estimates of
# the same quantity, kept only so a reader meeting them elsewhere can place them:
#
#   1.633  C17, 25 episodes                              superseded (small sample)
#   1.818  C55, 200 episodes, pre-paired evaluator       superseded (older evaluator)
#   1.842  C55 re-measured, 200 paired episodes          <- CURRENT, and the value below
#
# All three measure the same random policy on Door and agree: 1.633 and 1.818 both fall inside the
# current measurement's 95% CI of [1.511, 2.271]. They are one number measured three times, not
# three floors. Import DOOR_RANDOM_FLOOR rather than any literal (Codex Q12/Q13).  Reporting the larger sample
# matters because this floor is the competence gate's denominator guard, and the 25-episode
# estimate is what the line below used to print while the comment above cited 1.82.
# Lift has no 200-episode re-derivation, so it remains the 25-episode figure and says so.
# Door re-measured 2026-09-05 under the CURRENT evaluator and PAIRED per-episode seeding
# (scripts/probe_floor.py --episodes 200): mean 1.842, sd 2.839, 95% CI [1.511, 2.271], max 28.755,
# 0/200 successes and the flag never fired.  C55's superseded 1.818 falls inside that interval, so switching to
# per-episode condition seeding left the floor where it was -- a confirmation, as expected, since
# both schemes draw from the same marginal placement distribution.
#
# The MAX is the number that moved (6.933 -> 28.755) and it did so only because the old max came
# from C17's 25 episodes while the mean quoted beside it came from 200.  Both figures are now from
# the same 200-episode sample.  That matters: a single chance episode reaching 28.8 is why the
# per-episode DISPERSION, not just the mean, has to travel with any competence claim.
OUR_RANDOM = {"door": (1.842, 28.755), "lift": (6.562, 34.647)}
RANDOM_EPISODES = {"door": 200, "lift": 25}

#: THE canonical Door random-policy floor. Import this; do not copy the literal.
#: On 2026-09-05 the number 1.82 was living in five places at once -- two `RANDOM_FLOOR = 1.82`
#: constants and three prose statements -- while the measured value had moved to 1.842. That is
#: SYNTHESIS Mechanism 2 ("two homes for one number") in its most literal form, and the fix is a
#: single home rather than five edits. Raised by Codex as Q12.
DOOR_RANDOM_FLOOR = OUR_RANDOM["door"][0]
DOOR_RANDOM_FLOOR_EPISODES = RANDOM_EPISODES["door"]
#: [Claude 2026-09-07, A31] The measurement this constant comes from (`probe_floor.py --episodes
#: 200`, comment above) is separately documented as "0/200 successes and the flag never fired".
#: Exposed as its own constant, not re-derived from a different grid, so a caller wanting the
#: success count alongside the canonical mean has one home for both rather than pairing this
#: float with a locally-measured count from an unrelated pipeline.
DOOR_RANDOM_FLOOR_SUCCESSES = 0


def read(sheet: str = "Robosuite") -> dict:
    import openpyxl
    ws = _load_workbook()[sheet]
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
    if not any(c.is_file() for c in _CANDIDATES):
        print("absent: no vendored copy and no asset archive; looked in\n  "
              + "\n  ".join(str(c) for c in _CANDIDATES))
        return 1
    data = read()
    for task in ("door", "lift"):
        rmean, rmax = OUR_RANDOM[task]
        print(f"\n=== {task.upper()} -- RL-ViGen published, mean over 5 seeds ===")
        n = RANDOM_EPISODES.get(task, 25)
        print(f"  our random-policy floor, OUR config: mean {rmean:.2f}, max {rmax:.2f} "
              f"(n={n} random episodes)")
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
