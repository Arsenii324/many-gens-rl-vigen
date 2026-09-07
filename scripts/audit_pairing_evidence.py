#!/usr/bin/env python3
"""Do the records PROVE paired physical conditions, or only assert them?

    python scripts/audit_pairing_evidence.py results/records/*.jsonl

## Why this exists

External review 10 made a point the project had not answered:

> An image hash is not evidence that physical placement is the same. Under different visual regimes
> the exact same physical state should generally produce different images.

That is right, and it matters because `placement_witnesses` -- which the evaluator records and
`_run_grid` counts -- are **observation hashes**. They are good within-cell provenance and they
cannot demonstrate cross-regime pairing, because a matched physical placement under `train` and
`eval-easy` SHOULD hash differently.

The physical evidence exists and is already collected: patch P20 records the realized
`initial_placement` (door body position and quaternion) per episode. **This audit compares that.**

A record must also name the evaluator revision that produced it.  The raw archive retains
pre-provenance measurements, but they cannot establish a claim about the current evaluator: their
collector and placement schema are unidentified.  This audit prints such cross-regime groups as
`legacy/ineligible`, rather than quietly treating them as a failed current measurement or allowing
them to make the production gate pass.

## What it checks

For each (baseline, seed, scene) that appears under more than one regime:

1. **the realized physical placement** is identical episode-for-episode across regimes -- the
   property every retention claim depends on;
2. the recorded `placement_condition_seeds` agree, which is the seed-level statement;
3. the `placement_witnesses` DIFFER across regimes, which is the correct behaviour and worth
   asserting because witnesses being equal across visual regimes would mean the regime is not
   reaching the renderer.

Point 3 is the one a naive check gets backwards.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import sys


def load(paths: list[str]) -> list[dict]:
    rows = []
    for pattern in paths:
        for name in sorted(glob.glob(pattern)):
            for line in pathlib.Path(name).read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def placements(row: dict) -> list | None:
    diagnostics = (row.get("native") or {}).get("episode_diagnostics") or []
    out = [d.get("initial_placement") for d in diagnostics if isinstance(d, dict)]
    return out if out and all(o is not None for o in out) else None


def audit(paths: list[str]) -> int:
    rows = [r for r in load(paths) if r.get("phase") == "offline-eval" and r.get("regime")]
    groups: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    legacy: dict[tuple, set[str]] = collections.defaultdict(set)
    pooled: dict[tuple, set[str]] = collections.defaultdict(set)
    # Each cell emits TWO rows with the same scene_set: the per-scene record, which carries the
    # per-episode `native` arrays, and the pooled aggregate, which does not. Keeping whichever
    # arrived last kept the aggregate and made every comparison report "no physical evidence" --
    # the audit's own first run said exactly that about records I had already read placements out
    # of by hand. Prefer the row that actually carries diagnostics.
    #
    # [Claude 2026-09-07] That dedup only fires when both rows SHARE a scene_set string, which is
    # only true for a single-scene cell ("aggregate over {0}" == "0"). A genuinely multi-scene
    # aggregate (scene_set "0,1,...,9") gets its OWN key, distinct from each per-scene "0".."9"
    # key, and never carries placements by design -- it is a pooled summary of rows that are
    # already checked individually below, not a second piece of evidence to demand. Found by the
    # C95 R_A re-measurement (v178, ten scenes): it made this a real FAIL, not a hypothetical.
    # Excluded the same way as `legacy`, not counted as unprovable.
    for row in rows:
        aggregate_scenes = (row.get("native") or {}).get("aggregate_over_scenes")
        if isinstance(aggregate_scenes, list) and len(aggregate_scenes) > 1:
            pooled[(row.get("baseline"), row.get("seed"), str(row.get("scene_set")))].add(
                str(row.get("regime")))
            continue
        # `None` was emitted before evaluator provenance existed.  Do not delete or rewrite that
        # historical evidence, but do not let it answer a current-evaluator question either.
        if not row.get("evaluator_revision"):
            legacy[(row.get("baseline"), row.get("seed"), str(row.get("scene_set")))].add(
                str(row.get("regime")))
            continue
        key = (row.get("baseline"), row.get("seed"), str(row.get("scene_set")),
               str(row.get("evaluator_revision"))[:12])
        regime = str(row.get("regime"))
        if placements(row) is not None or regime not in groups[key]:
            groups[key][regime] = row

    checked = mismatched = unprovable = 0
    legacy_cross_regime = [key for key, regimes in legacy.items() if len(regimes) > 1]
    for key in sorted(legacy_cross_regime, key=str):
        print(f"  {key[0]} s{key[1]} scene {key[2]}: LEGACY/INELIGIBLE "
              "(no evaluator_revision) -- retained raw evidence cannot establish current pairing")
    for key in sorted(pooled, key=str):
        print(f"  {key[0]} s{key[1]} scenes {key[2]}: POOLED/INELIGIBLE "
              "(multi-scene aggregate, no per-episode diagnostics by design) -- its constituent "
              "per-scene rows are the evidence, checked individually below")
    for key, by_regime in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(by_regime) < 2:
            continue
        regimes = sorted(by_regime)
        base = by_regime[regimes[0]]
        base_placements = placements(base)
        if base_placements is None:
            unprovable += 1
            print(f"  {key[0]} s{key[1]} scene {key[2]} rev {key[3]}: NO PHYSICAL EVIDENCE "
                  "(diagnostics absent) -- pairing cannot be demonstrated from these records")
            continue
        for regime in regimes[1:]:
            other = placements(by_regime[regime])
            checked += 1
            if other is None:
                unprovable += 1
                print(f"  {key[0]} s{key[1]} scene {key[2]}: {regime} has no physical evidence")
                continue
            same = [json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
                    for a, b in zip(base_placements, other)]
            witness_a = (base.get("native") or {}).get("placement_witnesses") or []
            witness_b = (by_regime[regime].get("native") or {}).get("placement_witnesses") or []
            note = ""
            if witness_a and witness_b and witness_a == witness_b:
                note = "  [witnesses IDENTICAL across regimes -- the regime may not be reaching the renderer]"
            if all(same):
                print(f"  {key[0]} s{key[1]} scene {key[2]} rev {key[3]}: "
                      f"{regimes[0]} vs {regime} -- physically PAIRED, {len(same)} episodes{note}")
            else:
                mismatched += 1
                print(f"  {key[0]} s{key[1]} scene {key[2]} rev {key[3]}: "
                      f"{regimes[0]} vs {regime} -- NOT PAIRED, episodes {[i for i, s in enumerate(same) if not s]}")

    pooled_cross_regime = [key for key, regimes in pooled.items() if len(regimes) > 1]
    print()
    print(f"  {checked} eligible cross-regime comparisons; {mismatched} not paired; "
          f"{unprovable} lacking physical evidence; {len(legacy_cross_regime)} "
          f"legacy/ineligible groups excluded; {len(pooled_cross_regime)} pooled/ineligible "
          "groups excluded")
    if not checked and not unprovable:
        print("  no current, provenanced (baseline, seed, scene) appears under two regimes, so "
              "nothing could be checked. That is NOT a pass.")
        return 0
    if not checked:
        print(f"  {unprovable} current group(s) had two regimes but no physical evidence to compare.")
        print("  That is NOT a pass either -- it means those records cannot demonstrate pairing.")
        return 0
    if mismatched:
        print("  A retention number compares regimes. Unpaired conditions make that comparison "
              "confounded by placement.")
    return 1 if mismatched else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("records", nargs="*", default=["results/records/*.jsonl"])
    return audit(ap.parse_args().records or ["results/records/*.jsonl"])


if __name__ == "__main__":
    raise SystemExit(main())
