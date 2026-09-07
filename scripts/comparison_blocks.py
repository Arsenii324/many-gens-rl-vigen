#!/usr/bin/env python3
"""Which pairwise comparisons are PRIMARY, derived from the axes rather than asserted.

## Why this is derived and not a list

A25 names the primary comparison set as prose: two mechanism groups, 6 + 15 pairs. Three axes then
split those groups internally, and each was handled by declaring it:

  - **evaluation policy mode** (UNITS): 9 take the mode, 3 sample. `notes/SAME-AXES-VERDICT.md`.
  - **frame-stack depth**: 10 stack three frames, `ctrl` and `ibac_sni` stack one. A40.
  - **time-limit handling** (C1, rated the largest comparability defect found): 3 bootstrap
    through truncation, 9 zero the value target at it.

Declaring is the right response to ONE such split. It stops being sufficient when the splits
straddle the majority of the comparisons the paper leads with -- and they do: 4 of the on-policy
group's 6 pairs cross the frame-stack split, and 8 of the off-policy group's 15 cross the
time-limit split. A reader looking at `svea` beside `rad` cannot tell augmentation from truncation
handling, and no caption makes that attributable.

So the blocks are COMPUTED here from the same tables the audits read. A pair is primary only if its
two baselines agree on every axis below. That makes the reported set a consequence of the data
rather than a judgement anyone has to re-derive, and it changes automatically if an axis does.

## What this does NOT claim

Blocking is not a repair. The cross-block comparisons remain interesting and remain reportable --
as descriptive, with the confounding axis named. What is refused is RANKING across a block
boundary, which is the operation that would silently attribute an axis difference to the method.
"""
from __future__ import annotations

import argparse
import itertools
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import OBSERVATION_GEOMETRY, TIME_LIMIT_HANDLING  # noqa: E402

sys.path.insert(0, str(ROOT / "datasphere" / "native"))
from evaluator_identity import (  # noqa: E402
    FAMILY_ALLOWED_BASELINES, family_eval_policy_mode,
)

#: A25's mechanism groups. The GROUPS are a scientific judgement -- what question a comparison
#: answers -- and stay prose. Which pairs inside them are comparable is arithmetic, and is here.
GROUPS = {
    "on-policy PPO, differing in what regularizes it": ["idaac", "ibac_sni", "ppg", "ctrl"],
    "off-policy, differing in augmentation": ["drqv2", "svea", "sgqn", "drq", "rad", "soda"],
    "latent-dynamics": ["alda", "curl"],
}


def _policy_mode(baseline: str) -> str:
    for family, baselines in FAMILY_ALLOWED_BASELINES.items():
        if baseline in baselines:
            return family_eval_policy_mode(family)
    return "?"


def axes_of(baseline: str) -> dict[str, object]:
    image_size, frame_stack = OBSERVATION_GEOMETRY[baseline]
    return {
        "policy mode": _policy_mode(baseline),
        "frame stack": frame_stack,
        "time limit": TIME_LIMIT_HANDLING[baseline],
        "render size": image_size,
    }


#: Axes on which a difference confounds the comparison with something that is not the method.
#: `render size` is deliberately NOT here: it is declared, and unlike the other three it does not
#: change what the agent can infer (crop policy already equalises what the network sees at 84).
BLOCKING_AXES = ("policy mode", "frame stack", "time limit")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any group has no primary pair left")
    args = parser.parse_args()

    print("COMPARISON BLOCKS -- a pair is PRIMARY only if it agrees on every blocking axis\n")
    print(f"  blocking axes: {', '.join(BLOCKING_AXES)}\n")

    empty = []
    for title, members in GROUPS.items():
        present = [b for b in members if b in OBSERVATION_GEOMETRY]
        pairs = list(itertools.combinations(present, 2))
        primary, descriptive = [], []
        for left, right in pairs:
            differing = [axis for axis in BLOCKING_AXES
                         if axes_of(left)[axis] != axes_of(right)[axis]]
            (descriptive if differing else primary).append(((left, right), differing))
        print(f"  {title}")
        print(f"    {len(pairs)} pairs: {len(primary)} primary, {len(descriptive)} descriptive")
        for (left, right), _ in primary:
            print(f"      PRIMARY      {left} vs {right}")
        for (left, right), differing in descriptive:
            print(f"      descriptive  {left} vs {right}   (differs on: {', '.join(differing)})")
        if not primary:
            empty.append(title)
        print()

    blocks: dict[tuple, list[str]] = {}
    for baseline in OBSERVATION_GEOMETRY:
        key = tuple(axes_of(baseline)[axis] for axis in BLOCKING_AXES)
        blocks.setdefault(key, []).append(baseline)
    print("  Blocks across the whole fleet (rank within, never across):")
    for key, members in sorted(blocks.items(), key=lambda item: -len(item[1])):
        described = ", ".join(f"{axis}={value}" for axis, value in zip(BLOCKING_AXES, key))
        print(f"    {described}")
        print(f"      {', '.join(sorted(members))}")

    if empty:
        print()
        print(f"  WARNING: {len(empty)} group(s) have NO primary pair left: {'; '.join(empty)}.")
        print("  A group whose every comparison is confounded cannot carry a headline claim.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
