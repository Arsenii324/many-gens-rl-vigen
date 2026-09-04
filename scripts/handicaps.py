#!/usr/bin/env python3
"""Handicaps, inverted: which ones apply to each baseline? — closes SYSTEM.md's "no home" gap.

    python scripts/handicaps.py            # per-baseline view
    python scripts/handicaps.py --by-entry # per-handicap view (what the register already gives)

## The gap this closes, in SYSTEM.md's own words

`docs/SYSTEM.md` names four kinds of divergence and says the third — **handicap: recorded, not
removed** — has *no home*, structurally rather than by oversight:

> A handicap leaves no trace in code, so it cannot be found by the two mechanisms this project
> relies on: it produces no `git diff` hunk for `deviations.py` to count, and no authored line for
> `INTEGRATION-DELTA`'s own rule to admit — a non-change *is* correctly attributed to the authors.
> [...] They are findable by **date** through the register and invisible by **algorithm**, which is
> the axis a reader of `idaac`'s FAITHFULNESS section is on.

So the missing thing was never a document. It was an **index**: the facts were all recorded, and
none of them could be reached from the question a reader actually asks, which is *"I am about to
quote `idaac`'s number — what is stacked against it?"*

## Why a generated view rather than a new document

A `HANDICAPS.md` would be a second place to update, and this project has been bitten repeatedly by
a claim that outlived its referent (C64, C66, C5's own attribution). The register stays the single
source of truth; each handicap entry carries one `**Handicap — affects:**` line, and this script
inverts them. Nothing to keep in sync, and a handicap that loses its marker disappears from the
view rather than silently going stale — which `tests/test_handicaps_index.py` is there to catch.

## What this deliberately does not do

It does not decide what counts as a handicap. That judgement lives in the register, in the entry,
next to its evidence. This only inverts the axis.
"""
from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "CONSTRUCTION.md"

ENTRY = re.compile(r"^### (C\d+) — (.+?) \{#c\d+\}$", re.M)
MARK = re.compile(r"^\*\*Handicap — affects:\*\* (.+)$", re.M)
WHY = re.compile(r"^\*(.+?)\*$", re.M)

#: The twelve, so a marker naming something else is caught rather than silently creating a
#: thirteenth baseline in the output.
BASELINES = ["drqv2", "drq", "svea", "sgqn", "curl", "rad", "soda", "alda",
             "idaac", "ppg", "ctrl", "ibac_sni"]


def parse() -> list[dict]:
    text = REGISTER.read_text(encoding="utf-8")
    entries = list(ENTRY.finditer(text))
    out = []
    for i, m in enumerate(entries):
        end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
        body = text[m.start():end]
        mk = MARK.search(body)
        if not mk:
            continue
        why = WHY.search(body[mk.end():mk.end() + 400])
        out.append({"id": m.group(1), "title": m.group(2),
                    "affects": mk.group(1).split(),
                    "why": why.group(1) if why else ""})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--by-entry", action="store_true")
    a = ap.parse_args(argv)

    hs = parse()
    if not hs:
        print("no handicap entries found -- the `**Handicap — affects:**` markers are gone, or "
              "the register moved. This is a failure, not an empty result.")
        return 1

    unknown = sorted({b for h in hs for b in h["affects"]} - set(BASELINES))
    if a.by_entry:
        for h in hs:
            print(f"{h['id']}  {h['title']}")
            print(f"    affects ({len(h['affects'])}): {' '.join(h['affects'])}")
            if h["why"]:
                print(f"    {h['why']}")
        return 0

    print("HANDICAPS BY BASELINE -- what is stacked against this number before you quote it")
    print("  A handicap is a NON-change with a consequence: nothing in `git diff` records it,")
    print("  and it is correctly attributed to the original authors. See SYSTEM.md.\n")
    for b in BASELINES:
        mine = [h for h in hs if b in h["affects"]]
        print(f"  {b:<10} {len(mine)} handicap(s)")
        for h in mine:
            print(f"      {h['id']}  {h['title']}")
    print(f"\n  {len(hs)} handicap entries, covering "
          f"{len({b for h in hs for b in h['affects']})} of {len(BASELINES)} baselines.")
    if unknown:
        print(f"  !! marker names something that is not one of the twelve: {unknown}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
