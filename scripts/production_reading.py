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
from regime_retention_report import MIN_DENOM_SUCCESS  # noqa: E402

REGIMES = ("train", "eval-easy", "eval-medium", "eval-hard")


def _door_random_floor() -> float:
    """The floor every return reads against (C55). Imported, never restated."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_rlvigen_reference", ROOT / "scripts" / "rlvigen_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return float(module.DOOR_RANDOM_FLOOR)


def _is_pooled(row: dict) -> bool:
    """The evaluator writes ten single-scene rows AND one pooled row; only the ten are cells."""
    return "," in str(row.get("scene_set", ""))


def _by_scene(rows: list[dict], field: str) -> dict[tuple[str, str], dict[str, list[float]]]:
    """Endpoint values grouped (regime, mode) -> scene -> values.

    Grouping by SCENE first is not cosmetic. The same checkpoint can be measured twice -- the
    in-cell grid writes one set of rows and an offline re-evaluation sweep can write another for
    the same frame, regime and scene (`idaac` s101 has both). Appending them to one list would
    weight those scenes twice in Ȳ. Averaging within a scene first makes a repeat measurement what
    it actually is: a better estimate of that one scene cell, not an extra scene.
    """
    out: dict[tuple[str, str], dict[str, list[float]]] = {}
    for row in rows:
        if row.get("eval_scope") != "endpoint" or _is_pooled(row):
            continue
        mode = (row.get("conventions") or {}).get("eval_policy_mode")
        regime, value, scene = row.get("regime"), row.get(field), str(row.get("scene_set"))
        if mode is None or regime is None or value is None:
            continue
        out.setdefault((regime, mode), {}).setdefault(scene, []).append(float(value))
    return out


def per_seed_means(rows: list[dict]) -> dict[tuple[str, str], float]:
    """Ȳ[m,r,g] for one cell: mean over the ten scene cells, per (regime, policy mode)."""
    return {key: statistics.fmean(statistics.fmean(v) for v in scenes.values())
            for key, scenes in _by_scene(rows, "episode_return_mean").items()}


def per_seed_success(rows: list[dict]) -> dict[tuple[str, str], float]:
    """Train-regime success, the other half of the competence gate (EVAL-PROTOCOL §3)."""
    return {key: statistics.fmean(statistics.fmean(v) for v in scenes.values())
            for key, scenes in _by_scene(rows, "success_rate").items()}


def competence(train_mean: float, train_success: float, floor: float) -> tuple[bool, str]:
    """May this cell be given a retention RATIO at all?

    `docs/EVAL-PROTOCOL.md` §3: only if the train-regime denominator clears the floor by a stated
    margin AND train-regime success is non-zero. The margin used here is the project's existing
    one, `MIN_DENOM_SUCCESS` from `regime_retention_report.py` (0.25), imported rather than
    restated -- it was raised from "any success at all" after an adversarial re-check found a
    policy scoring 1/20 on every scene passing the gate and producing a retention of 0.947 that
    was really a shaped-reward plateau.
    """
    if train_mean <= floor:
        return False, f"train Ȳ {train_mean:.2f} at or below the {floor:.3f} random floor"
    if train_success < MIN_DENOM_SUCCESS:
        return False, (f"train success {train_success:.3f} below {MIN_DENOM_SUCCESS:.2f}: the "
                       f"denominator is shaped reward, not task success")
    return True, ""


def collect(schedule_path: pathlib.Path) -> tuple[dict, dict, dict]:
    """Returns the seed points, a tally of skipped cells, and the competence gate per cell."""
    schedule = json.loads(schedule_path.read_text())
    live, attested = cs._live_revisions(), cs._attested()
    records = cs._records_index()
    submitted, ended, running = cs._submitted(), cs._host_ended(), cs._host_running()

    points: dict[tuple[str, str, str], list[tuple[int, float]]] = {}
    skipped: dict[str, int] = {}
    gate: dict[tuple[str, str, int], tuple[bool, str, float, float]] = {}
    floor = _door_random_floor()
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
            means, successes = per_seed_means(rows), per_seed_success(rows)
            for (regime, mode), value in means.items():
                points.setdefault((baseline, mode, regime), []).append((seed, value))
            for mode in {m for _, m in means}:
                train = means.get(("train", mode))
                if train is None:
                    continue
                competent, why = competence(train, successes.get(("train", mode), 0.0), floor)
                gate[(baseline, mode, seed)] = (competent, why, train,
                                                successes.get(("train", mode), 0.0))
    return points, skipped, gate


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


def render_retention(points: dict, gate: dict) -> list[str]:
    """Retention per seed = Ȳ[regime] / Ȳ[train], and a refusal where the gate says so."""
    out = ["", "RETENTION (eval regime / train regime), per trained policy", ""]
    per_cell: dict[tuple[str, str], dict[int, dict[str, float]]] = {}
    for (baseline, mode, regime), seeds in points.items():
        for seed, value in seeds:
            per_cell.setdefault((baseline, mode), {}).setdefault(seed, {})[regime] = value

    refused = 0
    for (baseline, mode), seeds in sorted(per_cell.items()):
        for seed in sorted(seeds):
            competent, why, train_mean, train_success = gate.get(
                (baseline, mode, seed), (False, "no train regime measured", float("nan"), float("nan")))
            head = f"  {baseline:<10} {mode:<7} seed {seed:<4}"
            if not competent:
                refused += 1
                out.append(f"{head} DID NOT REACH COMPETENCE -- no ratio. {why}")
                out.append(f"  {'':<10} {'':<7}          (train Ȳ {train_mean:.2f}, "
                           f"train success {train_success:.3f})")
                continue
            parts = []
            for regime in REGIMES[1:]:
                value = seeds[seed].get(regime)
                if value is not None and train_mean:
                    parts.append(f"{regime} {value / train_mean:.3f}")
            out.append(f"{head} " + "  ".join(parts))
    out.append("")
    if refused:
        out.append(f"  {refused} cell(s) received no ratio. That is the reporting rule in")
        out.append("  EVAL-PROTOCOL §3, not a missing measurement: a method that never solves the")
        out.append("  task has nothing to retain, and its gap would read as perfect generalisation.")
        out.append("  The returns above are still real and still published.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", default=str(cs.DEFAULT_SCHEDULE))
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--retention", action="store_true",
                    help="also show eval/train ratios, with the competence gate applied")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any printed baseline has fewer than three seeds")
    args = ap.parse_args(argv)

    points, skipped, gate = collect(pathlib.Path(args.schedule))
    if not points:
        print("No DONE cell on the current closure. Nothing to read.")
        print("  cells: " + ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())))
        return 0

    print("PRODUCTION READING -- endpoint returns, aggregated per EVAL-PROTOCOL §4c\n")
    lines, provisional = render(points, skipped, args.markdown)
    print("\n".join(lines))
    if args.retention:
        print("\n".join(render_retention(points, gate)))
    if provisional:
        print("\n  PROVISIONAL rows have fewer than three trained policies behind them. The seed")
        print("  spread is the finding at that point, not the mean: on 2026-09-17 idaac's")
        print("  train -> eval-easy gap changed sign between two seeds.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
