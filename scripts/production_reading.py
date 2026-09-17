#!/usr/bin/env python3
"""The headline reading, aggregated the way the protocol says and no other way.

    python scripts/production_reading.py                 # every baseline that has a DONE cell
    python scripts/production_reading.py --markdown      # same, for a write-up
    python scripts/production_reading.py --strict        # exit 1 unless every printed baseline has n=3

## Why this exists

`scripts/results_table.py` refuses to render without `--legacy-exploratory` and says: *"Its interval
resamples episodes from one trained policy; the production outer unit is the training seed. Use the
production reporting path for headline numbers."* There was no such path. Every production number
read so far -- including the three-baseline reading in `notes/production-host/34`, whose ranking was
retracted the next day -- was aggregated by hand.

## What it computes, and where that is decided

`docs/EVAL-PROTOCOL.md` §4c (A32), verbatim in its own notation:

    Y[m,r,g,s]  = mean over episodes e of R[m,r,g,s,e]        # an analysis CELL, not a replicate
    Ȳ[m,r,g]    = mean over the ten scenes s of Y[m,r,g,s]     # one number per trained policy
    replicates  = { Ȳ[m,1,g], Ȳ[m,2,g], Ȳ[m,3,g] }             # n = 3, and that is the whole n

So: a record row IS Y (it already carries `episode_return_mean` over its 20 episodes); the ten
single-scene rows are averaged to one number per trained policy; and the seeds -- never the scenes,
never the episodes -- are the replicates. The protocol's reporting convention follows: **every seed
point is printed individually**, with their mean and range, because "an interval must never visually
obscure that there are exactly three learned policies behind it".

Three things it refuses to do, each because the alternative manufactures a result:

* **It never pools across `policy_mode`.** Sampled and mode returns are different estimands
  (`docs/COMPARABILITY_CONTRACT.md`); they get separate blocks and are never averaged together.
* **It never treats a scene as a replicate.** Ten scenes do not turn three trained agents into
  thirty observations, and the ten-scene pooled row that the evaluator also writes
  (`scene_set = "0,1,...,9"`) is dropped rather than double-counted.
* **It never prints an n=1 or n=2 mean without saying so.** Those rows are labelled PROVISIONAL,
  and `--strict` exits 1 on them. Today's own two-seed `idaac` reading is why: the train → eval-easy
  gap changed SIGN between seeds 101 and 102 (`production-host/34`).

## Which cells count

Not a second opinion: `campaign_status.state_of` decides, and only its **DONE** cells are read --
a record at the scheduled endpoint, on the current evaluator closure. A cell that is RUNNING,
PARTIAL or SUPERSEDED contributes nothing, and the footer says how many were skipped for which
reason, so a silently thin table is impossible.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import campaign_status as cs  # noqa: E402

REGIMES = ("train", "eval-easy", "eval-medium", "eval-hard")


def _is_pooled(row: dict) -> bool:
    """The evaluator writes ten single-scene rows AND one pooled row; only the ten are cells."""
    return "," in str(row.get("scene_set", ""))


def per_seed_means(rows: list[dict]) -> dict[tuple[str, str], float]:
    """Ȳ[m,r,g] for one cell: mean over the ten scene cells, per (regime, policy mode)."""
    buckets: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        if row.get("eval_scope") != "endpoint" or _is_pooled(row):
            continue
        mode = (row.get("conventions") or {}).get("eval_policy_mode")
        regime, value = row.get("regime"), row.get("episode_return_mean")
        if mode is None or regime is None or value is None:
            continue
        buckets.setdefault((regime, mode), []).append(float(value))
    return {key: statistics.fmean(values) for key, values in buckets.items()}


def collect(schedule_path: pathlib.Path) -> tuple[dict, dict]:
    """Returns {(baseline, mode, regime): [(seed, Ȳ), ...]} and a tally of skipped cells."""
    schedule = json.loads(schedule_path.read_text())
    live, attested = cs._live_revisions(), cs._attested()
    records = cs._records_index()
    submitted, ended, running = cs._submitted(), cs._host_ended(), cs._host_running()

    points: dict[tuple[str, str, str], list[tuple[int, float]]] = {}
    skipped: dict[str, int] = {}
    default_seeds = schedule.get("seeds", [])
    for entry in schedule.get("rows", []):
        baseline, family = entry["baseline"], entry["family"]
        endpoint = entry.get("executed_endpoint", schedule.get("frames"))
        for seed in entry.get("seeds", default_seeds):
            state, _ = cs.state_of(baseline, family, seed, endpoint, records, submitted,
                                   attested, live, ended, running)
            if state != "DONE":
                skipped[state] = skipped.get(state, 0) + 1
                continue
            rows = [r for r in records.get((baseline, seed), [])
                    if r.get("frame") in (endpoint, str(endpoint))
                    and r.get("evaluator_revision") == live.get(family)]
            for (regime, mode), value in per_seed_means(rows).items():
                points.setdefault((baseline, mode, regime), []).append((seed, value))
    return points, skipped


def render(points: dict, skipped: dict, markdown: bool) -> tuple[list[str], bool]:
    out, provisional = [], False
    blocks: dict[tuple[str, str], dict] = {}
    for (baseline, mode, regime), seeds in points.items():
        blocks.setdefault((baseline, mode), {})[regime] = sorted(seeds)

    head = "| baseline | estimand | regime | seed points (seed: Ȳ) | mean | range | n |"
    out.append(head if markdown else
               "  baseline   estimand  regime        seed points                     mean    range    n")
    if markdown:
        out.append("|---|---|---|---|---|---|---|")
    for (baseline, mode), regimes in sorted(blocks.items()):
        for regime in REGIMES:
            seeds = regimes.get(regime)
            if not seeds:
                continue
            values = [v for _, v in seeds]
            mean = statistics.fmean(values)
            spread = f"{min(values):.2f}-{max(values):.2f}" if len(values) > 1 else "-"
            pts = " ".join(f"{s}:{v:.2f}" for s, v in seeds)
            n = len(values)
            if n < 3:
                provisional = True
            flag = "" if n >= 3 else "  PROVISIONAL"
            if markdown:
                out.append(f"| `{baseline}` | {mode} | {regime} | {pts} | {mean:.2f} | {spread} | "
                           f"{n}{' **provisional**' if n < 3 else ''} |")
            else:
                out.append(f"  {baseline:<10} {mode:<9} {regime:<13} {pts:<30} {mean:7.2f}  "
                           f"{spread:<11} {n}{flag}")
    out.append("")
    out.append("Ȳ is the mean over the ten certified scenes for one trained policy; the seeds are the")
    out.append("replicates (EVAL-PROTOCOL §4c). Sampled and mode rows are different estimands and are")
    out.append("never pooled. Scenes and episodes are not replicates.")
    if skipped:
        out.append("")
        out.append("  cells not read: " + ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())))
    return out, provisional


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", default=str(cs.DEFAULT_SCHEDULE))
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any printed baseline has fewer than three seeds")
    args = ap.parse_args(argv)

    points, skipped = collect(pathlib.Path(args.schedule))
    if not points:
        print("No DONE cell on the current closure. Nothing to read.")
        print("  cells: " + ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())))
        return 0

    print("PRODUCTION READING -- endpoint returns, aggregated per EVAL-PROTOCOL §4c\n")
    lines, provisional = render(points, skipped, args.markdown)
    print("\n".join(lines))
    if provisional:
        print("\n  PROVISIONAL rows have fewer than three trained policies behind them. The seed")
        print("  spread is the finding at that point, not the mean: on 2026-09-17 idaac's")
        print("  train -> eval-easy gap changed sign between two seeds.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
