#!/usr/bin/env python3
"""Are these numbers reportable? Checks the evaluation's own identity fields, per record file.

    python scripts/audit_eval_validity.py results/records/<job>__records.jsonl [--strict]

## Why

A return is only as good as the conditions it was measured under. `eval_grid.py` records those
conditions per episode -- `placement_condition_seeds`, `placement_witnesses` (a hash of the reset
observation), `eval_episode_ids`, `returns`, `episode_success` -- and nothing read them until
2026-09-09, when reading them changed a published conclusion.

## What it checks

1. **Self-consistency.** `episode_return_mean`, `episode_return_sd`, `episodes` and `success_rate`
   must equal what the row's own raw `returns` and `episode_success` say. A summary that disagrees
   with its own data is the cheapest possible lie and nothing was checking for it.
2. **Episode-id uniqueness and agreement.** Ids must be unique within a file and must encode the
   row's own baseline, seed, frame, regime, scene and index -- a row whose ids name a different
   scene is mislabelled.
3. **Placement pairing.** `placement_condition_seed(seed, scene, index)` deliberately omits the
   REGIME, so every regime sees identical initial conditions and train-vs-eval is a paired
   comparison. If seeds differ across regimes for one (scene, index), that pairing is broken and the
   generalisation gap confounds placement with perturbation.
4. **Reset reproducibility, per regime.** The reset observation cannot be influenced by the policy,
   so for a given (regime, scene, index) it must be identical at every frame and in every pass.
   **It is not, for `eval-medium` and `eval-hard`** -- see below. This check reports the rate rather
   than failing, because the variation is a property of the benchmark rather than of this project.

## The finding this was written for

Measured on `card0-20260909-035152`, per-regime rate of (regime, scene, index) slots whose reset
observation differs across frames or passes:

| regime | rate | randomisation (`robosuitevgb/utils.py:67-90`) |
|---|---:|---|
| `train` | **0 %** | none |
| `eval-easy` | **0 %** | colour + lighting, `except_robot=True` |
| `eval-hard` | 10 % | + `moving_light`, `video_background` |
| `eval-medium` | **62 %** | + `moving_light`, **`except_robot=False`** |

At the endpoint's two policy-mode passes, **122 of 200 `eval-medium` slots and 15 of 160
`eval-hard` slots saw different reset observations, against 0 of 200 for `train` and `eval-easy`.**

**This is probably not a defect.** RL-ViGen's regimes are *distributions* over visual conditions and
sampling them is the point. But it has a hard consequence for what may be reported:

* `train` and `eval-easy` are **paired**: the same initial conditions and the same pixels, so a
  difference between them is attributable to the regime alone.
* `eval-medium` and `eval-hard` are **not paired across passes or frames**. Their numbers carry
  perturbation variance on top of episode variance, so a difference involving them is noisier than
  its episode count implies, and a *paired* comparison (same checkpoint, two policy modes) is not
  available for them at all.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import re
import statistics
import sys

#: `<baseline>-s<seed>-f<frame>[-<scope>-<policy_mode>]-<regime>-sc<scene>-e<index>`.
#: The scope and policy-mode fields were added 2026-09-10 because without them the endpoint `mode`
#: pass reproduced every id the `sample` pass had used -- 760 collisions on one cell. They are
#: OPTIONAL here so records written before that date still parse: an id that lacks them is old, not
#: malformed, and refusing to read it would make this audit unusable on the existing corpus.
ID = re.compile(r"^(?P<baseline>.+?)-s(?P<seed>\d+)-f(?P<frame>\d+)"
                r"(?:-(?P<scope>curve|endpoint)-(?P<mode>native|sample|mode))?"
                r"-(?P<regime>train|eval-easy|eval-medium|eval-hard)"
                r"-sc(?P<scene>\d+)-e(?P<idx>\d+)$")


def _rows(path: pathlib.Path) -> list[dict]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on a self-consistency, id or pairing failure "
                         "(reset reproducibility is reported, never failed)")
    args = ap.parse_args()

    target = pathlib.Path(args.target)
    if not target.exists():
        print(f"no such path: {target}")
        return 2
    files = [target] if target.is_file() else sorted(target.rglob("*.jsonl"))
    rows = [r for f in files for r in _rows(f)]
    detailed = [r for r in rows if (r.get("native") or {}).get("returns")
                and not (r.get("native") or {}).get("aggregate_over_scenes")]
    if not detailed:
        print(f"No rows with per-episode detail under {target}.")
        print("Nothing was checked, which is NOT the same as nothing being wrong: rows predating")
        print("`native.returns` cannot be validated this way at all.")
        return 2

    print(f"EVAL VALIDITY -- {len(detailed)} detailed row(s) of {len(rows)} under {target}\n")
    fail = 0

    # 1. self-consistency
    bad = []
    for r in detailed:
        n = r["native"]
        ret = n["returns"]
        if len(ret) != (r.get("episodes") or 0):
            bad.append((r, f"episodes={r.get('episodes')} but {len(ret)} returns"))
            continue
        if abs(statistics.mean(ret) - (r.get("episode_return_mean") or 0)) > 1e-6:
            bad.append((r, "episode_return_mean disagrees with its own returns"))
        if len(ret) > 1 and r.get("episode_return_sd") is not None:
            if abs(statistics.stdev(ret) - r["episode_return_sd"]) > 1e-6:
                bad.append((r, "episode_return_sd disagrees with its own returns"))
        succ = n.get("episode_success")
        if succ is not None and r.get("success_rate") is not None:
            if abs(sum(succ) / len(succ) - r["success_rate"]) > 1e-9:
                bad.append((r, "success_rate disagrees with episode_success"))
    print(f"  1. row summaries match their own raw episodes: "
          f"{'PASS' if not bad else f'FAIL ({len(bad)})'}")
    for r, why in bad[:5]:
        print(f"       {r.get('regime')}/{r.get('scene_set')}@{r.get('frame')}: {why}")
    fail += len(bad)

    # 2. episode ids
    ids = collections.Counter()
    mismatched = []
    for r in detailed:
        for i, eid in enumerate(r["native"].get("eval_episode_ids") or []):
            ids[eid] += 1
            m = ID.match(eid)
            if not m:
                mismatched.append((eid, "unparseable"))
            elif (m["regime"] != r["regime"] or m["scene"] != str(r["scene_set"])
                  or int(m["frame"]) != int(r["frame"]) or int(m["idx"]) != i):
                mismatched.append((eid, f"disagrees with row {r['regime']}/{r['scene_set']}"))
    dupes = [k for k, v in ids.items() if v > 1]
    print(f"  2. episode ids unique and agreeing with their row: "
          f"{'PASS' if not dupes and not mismatched else 'FAIL'}"
          f"  [{len(ids)} ids, {len(dupes)} duplicated, {len(mismatched)} mismatched]")
    for eid, why in mismatched[:3]:
        print(f"       {eid}: {why}")
    fail += len(dupes) + len(mismatched)

    # 3. placement pairing across regimes
    seeds = collections.defaultdict(set)
    for r in detailed:
        for i, s in enumerate(r["native"].get("placement_condition_seeds") or []):
            seeds[(str(r["scene_set"]), i)].add(s)
    unpaired = [k for k, v in seeds.items() if len(v) > 1]
    print(f"  3. placement seed identical across regimes and frames: "
          f"{'PASS' if not unpaired else f'FAIL ({len(unpaired)} of {len(seeds)})'}")
    fail += len(unpaired)

    # 4. reset reproducibility -- REPORTED, not failed
    # A SET alone cannot tell "seen once" from "seen ten times identically" -- and those are the
    # difference between "not measured" and "perfectly reproducible". Count observations too.
    wit = collections.defaultdict(set)
    seen = collections.Counter()
    for r in detailed:
        for i, w in enumerate(r["native"].get("placement_witnesses") or []):
            slot = (r["regime"], str(r["scene_set"]), i)
            wit[slot].add(w)
            seen[slot] += 1
    # [Claude 2026-09-10] COUNT THE COMPARISONS, and refuse to report a rate without them.
    #
    # A slot is only evidence of reproducibility if the same (regime, scene, index) was OBSERVED
    # MORE THAN ONCE -- at another frame, or in another pass. `wit` is a set per slot, so a file
    # holding a single pass at a single frame gives every slot exactly one witness, `len(v) > 1` is
    # never true, and this printed "200/200 reproducible (0% vary)" having compared nothing.
    #
    # That is not hypothetical: run on one endpoint file it reported 0% vary for all four regimes
    # across 800 slots, none of which had a second observation, and the number was repeated into
    # two notes as though it were a measurement. The full bundle for the same cell has 146
    # comparable slots and says eval-medium 62% and eval-hard 10%.
    #
    # An instrument that could not run must never read as one that ran, so the compared count is
    # now printed beside every rate and a regime with none says so instead of showing 0%.
    # varying, total slots, COMPARABLE slots (observed more than once -- the only ones that
    # carry evidence either way).
    per = collections.defaultdict(lambda: [0, 0, 0])
    for slot, v in wit.items():
        reg = slot[0]
        per[reg][1] += 1
        if seen[slot] > 1:
            per[reg][2] += 1
            if len(v) > 1:
                per[reg][0] += 1
    print("\n  4. reset observation reproducible across frames and passes, per regime:")
    uncomparable = []
    for reg in sorted(per):
        b, t, comparable = per[reg]
        if comparable == 0:
            uncomparable.append(reg)
            print(f"       {reg:<12} NOT COMPARED -- all {t} slot(s) observed exactly once")
            continue
        note = ""
        if b:
            note = ("  <- NOT paired: comparisons involving this regime carry perturbation "
                    "variance beyond their episode count")
        print(f"       {reg:<12} {comparable - b:>4}/{comparable} reproducible "
              f"({b / comparable:>5.0%} vary), of {t} slot(s){note}")
    if uncomparable:
        print(f"\n     {len(uncomparable)} regime(s) had NO repeated observation of any slot, so"
              f" nothing")
        print("     about their reproducibility was measured here. This happens when the input is a"
              " single")
        print("     pass at a single frame -- run the audit on the full bundle (curve + every"
              " endpoint")
        print("     pass) to get a rate. A single-pass file cannot disagree with itself.")
    print("\n     Reported, never failed: RL-ViGen's regimes are distributions over visual")
    print("     conditions and sampling them is the point. What it forbids is a PAIRED claim")
    print("     about a regime that varies -- see the module docstring.")

    return 1 if (args.strict and fail) else 0


if __name__ == "__main__":
    raise SystemExit(main())
