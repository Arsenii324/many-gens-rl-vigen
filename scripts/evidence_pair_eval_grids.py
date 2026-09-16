#!/usr/bin/env python3
"""Pair two captured evaluation grids row by row, and say how far apart repeat measurements are.

    python scripts/evidence_pair_eval_grids.py GRID1.txt GRID2.txt

Both inputs are evidence excerpts taken by `scripts/capture_host_evidence.py --only-matching`. Each
body line is `<row>:"<field>": <json value>`, where `<row>` is the source line number, so one
evaluation row. A row is keyed by (regime, scene_set, eval_policy_mode).

The script reports three things, separately for the `sample` and `mode` policy rows:

* **Placements.** How many paired rows used identical placement seeds.
* **Identity.** How many paired rows reproduced every episode return exactly, and how many
  individual episodes reproduced.
* **Scale.** |mean difference| in units of that row's standard error, sd / sqrt(episodes),
  averaged over the two grids.
* **Where.** Identical episodes per regime, and by episode index. Divergence that grows with the
  index would point at state leaking from one episode into the next.

The split by policy mode is the point. A `sample` row draws its actions from the policy
distribution, so a torch RNG that is not re-seeded per episode is enough to explain a difference.
A `mode` row takes the distribution's mode, which consumes no torch randomness at all. If `mode`
rows also differ, the nondeterminism is somewhere else: CUDA kernels, rendering or physics.
"""
from __future__ import annotations

import json
import math
import re
import statistics as st
import sys

SEPARATOR = "#" + "-" * 99 + "\n"
LINE = re.compile(r'^(\d+):"(\w+)": *(.*)$')


def rows(path: str) -> dict[tuple, dict]:
    body = open(path).read().split(SEPARATOR, 1)[1]
    by_row: dict[int, dict] = {}
    for line in body.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        fields = by_row.setdefault(int(m.group(1)), {})
        # a field can occur twice in a row (e.g. eval_policy_mode in conventions and in scope);
        # the first occurrence is the row's own
        fields.setdefault(m.group(2), json.loads(m.group(3)))
    out = {}
    for fields in by_row.values():
        key = (fields["regime"], str(fields["scene_set"]), fields["eval_policy_mode"])
        if key in out:
            raise SystemExit(f"{path}: duplicate row key {key}")
        out[key] = fields
    return out


def main(a: str, b: str) -> int:
    g1, g2 = rows(a), rows(b)
    print(f"rows grid1 {len(g1)} grid2 {len(g2)} paired {len(set(g1) & set(g2))} "
          f"unpaired {sorted(set(g1) ^ set(g2))}")
    for mode in sorted({k[2] for k in g1}):
        keys = sorted(k for k in set(g1) & set(g2) if k[2] == mode)
        # pooled scene-set rows are aggregates and carry no per-episode lists
        per_ep = [k for k in keys if "returns" in g1[k] and "returns" in g2[k]]
        same_seeds = sum(g1[k]["placement_condition_seeds"] == g2[k]["placement_condition_seeds"] for k in per_ep)
        same_rows = sum(g1[k]["returns"] == g2[k]["returns"] for k in per_ep)
        episodes = sum(len(g1[k]["returns"]) for k in per_ep)
        same_episodes = sum(x == y for k in per_ep for x, y in zip(g1[k]["returns"], g2[k]["returns"]))
        z = []
        for k in keys:
            n = g1[k]["episodes"]
            se = (g1[k]["episode_return_sd"] + g2[k]["episode_return_sd"]) / 2 / math.sqrt(n)
            d = abs(g1[k]["episode_return_mean"] - g2[k]["episode_return_mean"])
            z.append(d / se if se > 0 else (0.0 if d == 0 else math.inf))
        print(f"mode={mode} pairs {len(keys)} (per-scene {len(per_ep)})  identical placement seeds "
              f"{same_seeds}/{len(per_ep)}  identical rows {same_rows}/{len(per_ep)}  "
              f"identical episodes {same_episodes}/{episodes}")
        print(f"mode={mode} |mean diff| in SE: mean {st.mean(z):.3f}  median {st.median(z):.3f}  "
              f"max {max(z):.3f}  rows above 1 SE {sum(v > 1 for v in z)}/{len(z)}")
        for regime in sorted({k[0] for k in per_ep}):
            ks = [k for k in per_ep if k[0] == regime]
            same = sum(x == y for k in ks for x, y in zip(g1[k]["returns"], g2[k]["returns"]))
            total = sum(len(g1[k]["returns"]) for k in ks)
            print(f"  mode={mode} regime={regime} identical episodes {same}/{total}")
        # does divergence accumulate along a row? (it would if state leaked from episode to episode)
        by_pos = [sum(g1[k]["returns"][i] == g2[k]["returns"][i] for k in per_ep) for i in range(20)]
        print(f"  mode={mode} identical by episode index 0..19: {by_pos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
