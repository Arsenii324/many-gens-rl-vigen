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

from rlgen.protocol import (  # noqa: E402
    OBSERVATION_GEOMETRY, REWARD_NORMALIZATION, TIME_LIMIT_HANDLING,
)

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


#: What the NETWORK receives, which is not always what the renderer produces. `rad` and `soda`
#: render at 100 and crop to 84 -- that crop is RAD's actual augmentation mechanism, so forcing a
#: native 84 would make it a no-op by RAD's own `crop_max <= 0` guard. Everyone else's network
#: input equals their render size.
NETWORK_INPUT_SIZE = {"rad": 84, "soda": 84}


def axes_of(baseline: str) -> dict[str, object]:
    image_size, frame_stack = OBSERVATION_GEOMETRY[baseline]
    return {
        "policy mode": _policy_mode(baseline),
        "frame stack": frame_stack,
        "time limit": TIME_LIMIT_HANDLING[baseline],
        "render size": image_size,
        "reward scale": REWARD_NORMALIZATION[baseline],
        "network input": NETWORK_INPUT_SIZE.get(baseline, image_size),
    }


#: Axes on which a difference confounds the comparison with something that is not the method.
#:
#: Two axes are deliberately NOT here, each for its own stated reason:
#:
#:   `render size`   declared -- and superseded as an axis by `network input` below, which is the
#:                   quantity that actually matters. The old justification ("crop policy equalises
#:                   what the network sees at 84") was true of `rad`/`soda` and false of the
#:                   64-render group, where nothing equalises anything. Resolved 2026-09-08 by
#:                   blocking on the network input instead: `rad`/`soda` render 100 and crop to 84,
#:                   so they are 84 like the RL-ViGen five; the 64 group is genuinely 64.
#:
#:                   Adding it changed NOTHING -- both primary sets are identical before and after,
#:                   because each mechanism group happens to be internally uniform in input size.
#:                   That is exactly why it is worth adding: the reported set was correct by
#:                   coincidence, and is now correct by construction. A baseline that moves
#:                   resolution is caught instead of quietly confounding a pair.
#:   `reward scale`  declared. `rlgen/protocol.py::REWARD_NORMALIZATION` carries the argument:
#:                   equalising is less faithful in BOTH directions, the transplanted convention's
#:                   condition is not violated on Door (a running normaliser is scale-adaptive,
#:                   unlike a frame stack, which assumes velocity is visible), and every family's
#:                   evaluator reports the RAW return, so it is a training-objective difference
#:                   rather than a units one.
#:
#: A reader checking the arithmetic should note that `reward scale` and `time limit` both split
#: 3/9 over DISJOINT sets of three, so "the three that differ" is ambiguous without naming which.
#: BLOCKING DEPENDS ON THE QUANTITY, which this file used to ignore.
#:
#: [Claude 2026-09-08, external review 27 sec.7] Review 27 says to drop `policy mode` as a blocking
#: axis, because the owner ruled that a source-native evaluation convention is acceptable, so CTRL
#: being deterministic should not exclude it from primary on-policy comparisons.
#:
#: The premise is right and the conclusion does not follow AS STATED. Policy mode is a UNITS axis:
#: E[return | a = argmax pi] and E[return | a ~ pi] are different ESTIMANDS, not one quantity under
#: two conditions. "Acceptable to report each family's own estimand" is not "those estimands are
#: commensurable" -- a correctly measured mean and a correctly measured median are both correct and
#: still not rankable against each other. `notes/SAME-AXES-VERDICT.md` records exactly that
#: distinction, and its operative plan is "rank within a block, never across".
#:
#: But the review does expose a real error, and it is in this file. There are TWO reported
#: quantities and one blocking set was applied to both:
#:
#:   RAW RETURN   nothing cancels. Every axis below genuinely blocks.
#:   RETENTION    the study's actual endpoint. `docs/RESEARCH-FRAME.md` establishes that retention
#:                divides each method by its own train-regime performance, so a per-method confound
#:                appears in numerator and denominator alike and cancels TO FIRST ORDER -- it names
#:                frame stack, lr and discount as exactly such confounds. Policy mode is one too:
#:                a baseline's train-regime and eval-regime returns are both measured under its own
#:                native mode.
#:
#: So blocking retention comparisons on policy mode was wrong for a reason that cancels in
#: retention, and blocking raw-return comparisons on it remains right. Both sets are reported.
#:
#: The first-order cancellation is NOT a licence. RESEARCH-FRAME's second-order caveat stands in
#: full -- a confound can interact with the regime shift -- and so does C18's near-zero-denominator
#: problem. Retention pairs are "usable with a stated caveat", which is what that page already
#: says; they are not promoted to unqualified primaries here.
RETURN_BLOCKING_AXES = ("policy mode", "frame stack", "time limit", "network input")

#: Everything in RETURN_BLOCKING_AXES is a per-method property that appears in both regimes, so all
#: of it cancels to first order in a ratio. The set is empty by derivation, not by preference.
RETENTION_BLOCKING_AXES = ()

#: Kept as the name the rest of the tooling imports; it is the RAW RETURN set, which is the
#: stricter of the two and the right default for anything that does not say which quantity it means.
BLOCKING_AXES = RETURN_BLOCKING_AXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any group has no primary pair left")
    args = parser.parse_args()

    print("COMPARISON BLOCKS -- a pair is PRIMARY only if it agrees on every blocking axis\n")
    print(f"  RAW RETURN blocks on: {', '.join(RETURN_BLOCKING_AXES)}")
    print("  RETENTION  blocks on: nothing -- every axis above is a per-method property that")
    print("             appears in both regimes of the ratio and cancels to first order")
    print("             (docs/RESEARCH-FRAME.md). Usable WITH ITS STATED CAVEAT, not unqualified:")
    print("             a confound can still interact with the regime shift, and C18's")
    print("             near-zero-denominator problem is untouched by any of this.\n")
    print("  The set below is the RAW RETURN one. Retention is the study's endpoint and is less")
    print("  restricted; reporting one set for both was the error external review 27 sec.7 found,")
    print("  though its own prescription -- drop policy mode outright -- would have applied the")
    print("  retention answer to raw return, where the two estimands do not cancel.\n")

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
        print(f"    {len(pairs)} pairs: {len(primary)} primary, {len(descriptive)} descriptive"
              " (RAW RETURN)")
        for (left, right), _ in primary:
            print(f"      PRIMARY      {left} vs {right}")
        for (left, right), differing in descriptive:
            print(f"      descriptive  {left} vs {right}   (differs on: {', '.join(differing)})")
        # RETENTION blocks on nothing, so every pair in the group is usable there WITH the stated
        # caveat. Printed per group rather than only in the header, because the difference decides
        # whether a group can carry a claim at all -- see the warning below.
        if not primary and pairs:
            print(f"    on RETENTION, the study's endpoint, all {len(pairs)} pair(s) are usable "
                  "with RESEARCH-FRAME's second-order caveat")
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
        print(f"  WARNING: {len(empty)} group(s) have no RAW-RETURN primary pair: "
              f"{'; '.join(empty)}.")
        # [Claude 2026-09-08] This used to read "cannot carry a headline claim", full stop, and
        # that was wrong in a way that mattered. The set computed above is the RAW RETURN one;
        # `RETENTION_BLOCKING_AXES` is empty by derivation, and retention is the study's actual
        # endpoint (`docs/RESEARCH-FRAME.md`). So a group with no raw-return primary is not a
        # group with nothing to say -- `alda` vs `curl` is the live case, and it is the only pair
        # in the latent-dynamics group.
        #
        # An instrument that gates a scientific claim must name the quantity it is gating, or the
        # honest answer "usable on retention, not on raw return" gets rounded to "unusable".
        print("  That blocks a RAW-RETURN headline for those groups. It does NOT block retention,")
        print("  which is this study's endpoint and blocks on nothing -- every axis above is a")
        print("  per-method property appearing in both regimes of the ratio, so it cancels to")
        print("  first order. Those pairs are reportable on retention WITH RESEARCH-FRAME's")
        print("  second-order caveat and C18's near-zero-denominator caveat, and are NOT")
        print("  promoted to unqualified primaries by this.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
