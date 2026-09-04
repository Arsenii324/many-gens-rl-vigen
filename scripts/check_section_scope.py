#!/usr/bin/env python3
"""Every `##` heading in a two-era document must say which era it describes. [C82](../docs/CONSTRUCTION.md#c82)

    python scripts/check_section_scope.py            # report
    python scripts/check_section_scope.py --strict   # exit 1 on any untagged or unknown-tag heading

## Why this exists

On 2026-08-27 three separate wrong claims were written about `FAITHFULNESS.md`, each corrected by
the owner. All three came from the same move: **navigating by headings and concluding from a proxy
for reading.** `grep '^## '` produced a map — "Summary", "The PPO family", "What would raise
fidelity most" — and not one of those headings says whether the section describes the retired
`rlgen/` port or what runs today. The worst consequence was the third: the file's §5 *is* its
current-state section, re-triaged in the clone era, and the heading gave no way to know that, so a
banner was written over the whole document saying it did not know the clone tree existed.

**The fix is not "read more carefully".** That advice has now failed three times in one day. The
fix is to make the heading carry the fact, so that the cheap operation — the heading scan every
agent and every hurried human actually performs — returns something true.

## The convention

A `##` heading in a scoped document ends with a tag:

    ## 4. The PPO family — `idaac`, `ppg`, `ibac_sni`, `ctrl`  ·  [PORT-ERA]
    ## 5. What would raise fidelity most, per unit of work  ·  [CURRENT-STATE]

`[CURRENT-STATE]` is the load-bearing one: it marks the section a reader should start from, because
**scoped appending edits put the newest answer at the END of a document, not the top**, and nothing
else in the file advertises that. A scoped document may have at most one.

## What it does not do

It does not judge whether a tag is *correct* — no checker can. It enforces that a tag is *present*
and *from the vocabulary*, which is the part that rots silently. A wrong tag is visible to the next
reader; a missing one is what let three wrong claims through.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Documents that span more than one era, or otherwise mislead a heading-level scan. Listed rather
#: than detected: whether a document has this problem is a judgement about its history, and a
#: heuristic that guessed would either nag every file or miss the ones that matter.
SCOPED = {
    "docs/FAITHFULNESS.md":
        "spans the rlgen/ port era and the clone era, and the split runs THROUGH sections "
        "(the port mediated only the seven non-native baselines)",
    "docs/COMPARABILITY_CONTRACT.md":
        "sections 1-10 audit the retired rlgen/ port; its head already says so in prose (C30)",
    "docs/PART2-METRIC-INVENTORY.md":
        "clone-era throughout, but its section 5 order-of-work carries resolved items (C76)",
}

VOCABULARY = {
    "LIVE": "describes what runs today; verifiable against the current tree",
    "PORT-ERA": "describes the retired `rlgen/` port, superseded 2026-08-17",
    "HISTORY": "was true when written and is deliberately kept; not current, not a backlog",
    "CURRENT-STATE": "the document's own latest triage — READ THIS FIRST. At most one per document",
    "DURABLE": "about papers, released code or other people's results; era-independent",
    "MIXED": "contains both eras; individual items carry their own marks inside",
}

#: Any tag may carry a `-U` suffix: **unverified** — the tag is the tagger's belief about the
#: section, not the result of checking every claim in it. Added at the owner's suggestion on the
#: day the tags were introduced, because the tagger had read one of the three scoped documents in
#: full and inferred the other two from a register entry. A tag applied without reading is a guess,
#: and a guess that looks like a finding is the failure this whole convention exists to stop.
UNVERIFIED_SUFFIX = "-U"

#: THE RULE THAT MATTERS MORE THAN THE TAGS. A tag scopes a section's *"ours"* claims — what the
#: implementation did. It **never** licenses discarding a claim unread. `PORT-ERA` sections carry
#: durable research about papers and released code that is unaffected by which of our trees ran;
#: `FAITHFULNESS.md` §4 is the case in point, and was re-tagged MIXED for exactly this reason after
#: a flat PORT-ERA would have invited a reader to throw away IDAAC's Appendix E column, PPG's
#: 65 536-sample update, and the first author's own caution about DAAC on DMC.
NEVER_DISCARD = (
    "A scope tag tells you which system a section's OWN claims describe. It does not tell you the "
    "section is wrong, and it never authorises discarding a claim without checking it. PORT-ERA "
    "sections routinely carry durable research about papers and released code."
)

TAG = re.compile(r"·\s*\[([A-Z-]+)\]\s*$")
HEADING = re.compile(r"^## +(.*?)\s*$")


def scan(path: pathlib.Path) -> list[tuple[int, str, str | None]]:
    """-> [(lineno, heading text, tag or None)] for every `##` heading."""
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = HEADING.match(line)
        if not m:
            continue
        t = TAG.search(m.group(1))
        out.append((i, m.group(1), t.group(1) if t else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    problems, total = [], 0
    print("SECTION SCOPE TAGS")
    print("  A heading scan is the cheapest operation a reader performs, and in a two-era document")
    print("  it is the one most able to mislead. These documents make it say which era.\n")
    for rel, why in SCOPED.items():
        p = ROOT / rel
        if not p.exists():
            problems.append(f"{rel}: listed as scoped but does not exist")
            continue
        heads = scan(p)
        total += len(heads)
        current = [h for h in heads if h[2] and h[2].removesuffix(UNVERIFIED_SUFFIX) == "CURRENT-STATE"]
        print(f"  {rel}  ({len(heads)} sections)")
        print(f"    why scoped: {why}")
        for lineno, text, tag in heads:
            shown = TAG.sub("", text).strip()
            if tag is None:
                problems.append(f"{rel}:{lineno} untagged — {shown[:60]}")
                print(f"      {'UNTAGGED':<14} {shown[:62]}")
            elif tag.removesuffix(UNVERIFIED_SUFFIX) not in VOCABULARY:
                problems.append(f"{rel}:{lineno} unknown tag [{tag}] — {shown[:50]}")
                print(f"      {'?' + tag:<14} {shown[:62]}")
            else:
                print(f"      {tag:<14} {shown[:62]}")
        unver = sum(1 for _, _, t in heads if t and t.endswith(UNVERIFIED_SUFFIX))
        if unver:
            print(f"      ({unver} tag(s) marked -U: believed, not verified by reading)")
        if len(current) > 1:
            problems.append(f"{rel}: {len(current)} CURRENT-STATE sections; at most one is meaningful")
        if not current:
            print("      (no CURRENT-STATE section — fine only if the document genuinely has none)")
        print()

    print(f"  {total} sections across {len(SCOPED)} scoped documents; {len(problems)} problem(s)")
    for pr in problems:
        print(f"    {pr}")
    if not problems:
        print("\n  A tag says which era a section describes. It does NOT certify the section is")
        print("  right — no checker can. It certifies the heading scan is not silently misleading,")
        print("  which is the failure this exists for (C82).")
    print(f"\n  {NEVER_DISCARD}")
    print("  A `-U` suffix means the tag is believed, not verified by reading that section.")
    return 1 if (a.strict and problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())
