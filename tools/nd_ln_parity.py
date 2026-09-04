#!/usr/bin/env python3
"""Report every run's numbers the way Nd_ln.py (DZ's own reference script) would compute them,
ALONGSIDE this repo's own protocol — never instead of it.

    python tools/nd_ln_parity.py            # everything under ./logs
    python tools/nd_ln_parity.py <dir>

WHY THIS EXISTS. DZ's brief asks for our eval-like pipeline to be based on `Nd_ln.py`. Read
directly (`ext/alda/Nd_ln.py` in the sibling gen-rebuttal project, and the same file's own
`DISCREPANCY_MATRIX.md`), that script's protocol differs from ours on several axes at once:
scene 0 only (not 10 scenes), 10 episodes (not 100), no truncation bootstrapping at the horizon
(`DISCREPANCY_MATRIX.md` T1 — Robosuite episodes never terminate early, so this alone biases SAC's
critic), and an update-to-data ratio 4x too high once `action_repeat` changes from 4 to 1 (T6,
matching the ALDA `utd` fix applied to this repo 2026-08-13). Adopting Nd_ln.py's SHAPE wholesale
would mean adopting its measured defects along with it.

The resolution the sibling project settled on (its STATE.md D6: "Report both aggregations... DONE")
is what this tool implements: read the SAME `episodes.csv` this repo already writes — nothing
about training or the 10-scene evaluation protocol changes — and additionally compute the number
Nd_ln.py's own narrower slice of that same data would report. Two views of one measurement, not
two measurements or two protocols. If they diverge sharply, THAT divergence is itself information
(scene-to-scene variance, mostly — DISCREPANCY_MATRIX.md E1 measured single-scene relative
standard error at ~64% of the 10-scene mean on this exact benchmark).

WHAT COUNTS AS "Nd_ln-PARITY", precisely, sourced from DISCREPANCY_MATRIX.md's ledger (E1-E4):
  * scene_id == 0 only              (E1: Nd_ln.py never varies scene_id)
  * mean, not IQM or any trim       (E3: Nd_ln.py uses plain np.mean; this repo's own headline
                                          metric is mean too, per docs/PREMISES.md -- so this is
                                          the one axis that already agrees)
  * train denominator is scene 0    (E4: NOT the 10-scene train aggregate -- averaging over scenes
                                          the agent never trained on inflates retention; measured
                                          93.9% vs a true 0.9% on the sibling project's own runs)

A retention ratio is refused, not silently printed, whenever the train-scene-0 mean is smaller in
magnitude than --min-train-denominator (default 1.0): a ratio against a near-zero denominator is
exactly the failure `plot.py` already declines to draw for the SAME reason, stated there in the
same words ("a ratio whose denominator is a near-zero training score produces numbers like '131%
retention'").
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import statistics as st
import sys
from collections import defaultdict


def load_episodes(root: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(root, "**", "episodes.csv"), recursive=True)):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_path"] = path
                rows.append(row)
    return rows


def group_by_run(rows: list[dict]) -> dict[tuple, list[dict]]:
    """(task, baseline, seed, frames) -> its episode rows. `frames` is the checkpoint's training
    frame count (EpisodeRecord's own distinction between that and episode length), so this groups
    by evaluation POINT, not by run directory -- a run has one group per checkpoint evaluated."""
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["task"], r["baseline"], r["seed"], r["frames"])
        out[key].append(r)
    return out


def nd_ln_parity_row(episodes: list[dict], *, min_train_denominator: float) -> dict:
    """One (task, baseline, seed, frames) group -> the Nd_ln-shaped numbers, plus this repo's own
    full-protocol numbers for the SAME group, side by side."""
    by_mode = defaultdict(list)
    for r in episodes:
        by_mode[r["mode"]].append(r)

    def full_mean(mode: str) -> float | None:
        vals = [float(r["return_raw"]) for r in by_mode.get(mode, [])]
        return st.fmean(vals) if vals else None

    def scene0_mean(mode: str) -> tuple[float | None, int]:
        vals = [float(r["return_raw"]) for r in by_mode.get(mode, []) if r["scene_id"] == "0"]
        return (st.fmean(vals) if vals else None), len(vals)

    train_full = full_mean("train")
    eval_full = full_mean("eval-easy")
    train_s0, n_train_s0 = scene0_mean("train")
    eval_s0, n_eval_s0 = scene0_mean("eval-easy")

    retention_full = (eval_full / train_full) if (train_full and eval_full is not None
                                                   and abs(train_full) >= min_train_denominator
                                                   ) else None
    retention_nd_ln = (eval_s0 / train_s0) if (train_s0 and eval_s0 is not None
                                               and abs(train_s0) >= min_train_denominator
                                               ) else None

    return {
        "train_full_mean": train_full, "eval_full_mean": eval_full,
        "retention_full_protocol": retention_full,
        "train_scene0_mean": train_s0, "n_train_scene0_episodes": n_train_s0,
        "eval_scene0_mean": eval_s0, "n_eval_scene0_episodes": n_eval_s0,
        "retention_nd_ln_parity": retention_nd_ln,
    }


def fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) else ("--" if x is None else str(x))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="logs",
                    help="directory to search for episodes.csv (default: logs)")
    ap.add_argument("--min-train-denominator", type=float, default=1.0,
                    help="refuse to print a retention ratio when |train mean| is below this "
                         "(default 1.0) -- see the module docstring for why")
    args = ap.parse_args()

    rows = load_episodes(args.root)
    if not rows:
        print(f"FATAL: no episodes.csv under {args.root!r}. As of 2026-08-13 this project has "
              f"produced zero training runs (docs/dz-report-ru.md sec.1), so an empty result here "
              f"is expected, not a tool bug -- run this once real evaluation data exists.",
              file=sys.stderr)
        return 2

    groups = group_by_run(rows)
    print(f"{'task':6s} {'baseline':10s} {'seed':4s} {'frames':>9s} | "
          f"{'train(full)':>11s} {'eval(full)':>10s} {'ret(full)':>9s} | "
          f"{'train(s0)':>9s} {'n':>3s} {'eval(s0)':>8s} {'n':>3s} {'ret(Nd_ln)':>10s}")
    print("-" * 118)
    for (task, baseline, seed, frames) in sorted(groups, key=lambda k: (k[0], k[1], k[2], int(k[3]))):
        r = nd_ln_parity_row(groups[(task, baseline, seed, frames)],
                             min_train_denominator=args.min_train_denominator)
        print(f"{task:6s} {baseline:10s} {seed:4s} {frames:>9s} | "
              f"{fmt(r['train_full_mean']):>11s} {fmt(r['eval_full_mean']):>10s} "
              f"{fmt(r['retention_full_protocol']):>9s} | "
              f"{fmt(r['train_scene0_mean']):>9s} {r['n_train_scene0_episodes']:>3d} "
              f"{fmt(r['eval_scene0_mean']):>8s} {r['n_eval_scene0_episodes']:>3d} "
              f"{fmt(r['retention_nd_ln_parity']):>10s}")

    print("\n'full' = this repo's protocol: 10 scenes, all episodes, arithmetic mean.")
    print("'Nd_ln' = DZ's reference script's slice of the SAME data: scene 0 only, mean.")
    print("A ratio prints as '--' when |train mean| is below --min-train-denominator "
          f"({args.min_train_denominator}) -- see the module docstring for why a ratio is refused "
          "rather than printed against a near-zero denominator.")
    print("Both come from the same episodes.csv rows. Neither is a second evaluation run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
