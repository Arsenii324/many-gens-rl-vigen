#!/usr/bin/env python3
"""Enumerate the decisions this project has reached, and catch the ones it forgot to log.

## Why this is a script and why it adds no document

The home and the format both already exist, and adding a third of either would repeat the failure
`CONSTRUCTION.md` was created to fix — its header records these items once being "spread across
four documents in three formats with no shared status".

- **Home**: `docs/SYSTEM.md`'s routing table — *"A decision, when reached →
  INTEGRATION-DELTA.md"*. That file is Log-layer: append-only, never rewritten.
- **Format**: `docs/porting-directive.md` §4 — per branch point, *the structural property the
  mechanism depends on, the options considered, the choice, and the result that would show the
  choice was wrong.* The fourth field is the one that keeps a decision from fossilising into an
  assumption, and it is already required.

What was missing is **enforcement and retrieval**, and the register says so in as many words:
`REGISTER.md` category 42, *"Decision held only in working state, lost"*, recorded as
*"INTEGRATION-DELTA.md appends, but nothing enforces it."* This is that enforcement. It lives in
the Measurement layer — recomputed, never remembered.

## The two failures it catches

1. **A decision reached and not logged.** An item leaves `CONSTRUCTION.md`'s judgement queue
   because a choice was made; the choice survives as a sentence in a resolved entry, and a year
   later nobody can enumerate what was chosen or what the alternatives were. The decision has been
   forgotten *as a decision* — it now reads as the way things are, which is the state in which
   nobody reopens it.
2. **A decision logged without its falsifier.** §4 requires the overturning result. A block
   missing it is a record of what happened, not a decision anyone can later re-examine.

## Commands

    python scripts/decisions.py            # the table
    python scripts/decisions.py --brief    # prose, for a reader who was not present
    python scripts/decisions.py --check    # exit 1 on a malformed or missing decision
"""
from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "CONSTRUCTION.md"
# Decisions have more than one right home, and forcing them into one would misfile them.
# INTEGRATION-DELTA.md is keyed by authored element -- "who wrote this, and how do we know it is
# right" -- so a change to the CODE belongs there. A decision about what the claim may say is not
# an authored element; it belongs with the claim, in RESEARCH-FRAME.md, which is Standard-layer
# and amended in place. The §4 block format is the same in both, which is what makes them
# enumerable together.
HOMES = [ROOT / "docs" / "INTEGRATION-DELTA.md", ROOT / "docs" / "RESEARCH-FRAME.md"]

# A §4 block is a two-column table whose first row is the `§4 field` header, preceded by a bolded
# title line naming what the decision is about.
# The title may wrap -- a bolded name followed by a register citation on the next line is the
# natural way to write one, and a parser that forbids it would be making the record serve the
# instrument. Up to three lines of anything non-table are allowed between title and header.
BLOCK = re.compile(r"\*\*(?P<title>[^*\n]+?)\*\*(?:[^\n]*\n){0,3}?\s*"
                   r"\| §4 field \|[^\n]*\n\|[-| ]+\|\n(?P<rows>(?:\|[^\n]*\n)+)", re.M)
ROW = re.compile(r"^\|\s*\*\*(?P<field>[^*]+)\*\*\s*\|\s*(?P<value>.*?)\s*\|\s*$", re.M)

WANT = {"structural": "what the reference's mechanism depends on",
        "target": "what this target offers instead",
        "options": "the alternatives considered",
        "choice": "what was chosen, by whom",
        "wrong": "what would show the choice was wrong"}


def classify(field: str) -> str | None:
    f = field.lower()
    if "structural property" in f:
        return "structural"
    if "target actually offers" in f or "target offers" in f:
        return "target"
    if f.startswith("options"):
        return "options"
    if f.startswith("choice"):
        return "choice"
    if "wrong" in f:
        return "wrong"
    return None


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse() -> list[dict]:
    out = []
    for home in HOMES:
      text = home.read_text()
      for m in BLOCK.finditer(text):
        fields = {}
        for r in ROW.finditer(m.group("rows")):
            k = classify(r.group("field"))
            if k:
                fields[k] = squash(r.group("value"))
        d = {"title": squash(m.group("title")), "home": home.name, **fields}
        d["missing"] = [k for k in WANT if k not in fields]
        ch = fields.get("choice", "")
        d["settled"] = bool(ch) and not any(m in ch.lower() for m in UNDECIDED_MARKERS)
        # Only entries named in the TITLE count as settled by this decision. A block that cites
        # C47 while explaining its reasoning has not decided C47, and counting it would let a
        # measurement disappear from the "unlogged" list for being mentioned.
        head = m.group(0)[:m.group(0).index("| §4 field |")]
        d["entries"] = sorted(set(re.findall(r"\bC\d+\b", head)))
        out.append(d)
      # (loop body ends)
    return out


#: Phrasings that mean "this branch point is recorded but NOT resolved". The predicate used to
#: test for the single literal "not yet made", and on 2026-08-26 a block whose Choice row read
#: **NOT MADE -- the owner's** was counted as DECIDED. That is the worst possible direction for
#: this instrument to fail in: the ledger exists to keep open decisions visible, and a hardcoded
#: sentinel silently converts one into a closed one whenever a writer picks different words.
#:
#: Kept as a list rather than a regex so that adding a phrasing is obvious, and matched on the
#: lowercased Choice cell. A block that means "undecided" and says so in none of these ways will
#: still be miscounted -- which is why `tests/test_decision_ledger.py` asserts the ones actually
#: used in the two homes are all recognised, rather than trusting this list to be complete.
UNDECIDED_MARKERS = (
    "not yet made", "not made", "undecided", "not decided", "open", "deferred",
    "the owner's", "owner's to make", "pending",
)


def statuses() -> dict[str, str]:
    """Register id -> status, from the summary table."""
    return {c: st for c, st in re.findall(
        r"^\|\s*\[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|\s*\*{0,2}([A-Z-]+)",
        REGISTER.read_text(), re.M)}


def shifted_under(d: dict, st: dict[str, str]) -> list[str]:
    """Entries this decision REASONS ABOUT that have since been settled.

    The problem this exists for: decisions accumulate, and a pending one is written against a
    landscape that later decisions change. C50's option 2 was written as "collides with C45";
    once C45 was decided, that option meant something different, and nothing would have said so.
    A decision whose premises moved is not wrong -- it is unreviewed, which is worse, because it
    still reads as current.
    """
    cited = set(re.findall(r"\bC\d+\b", " ".join(
        str(d.get(k, "")) for k in ("structural", "target", "options", "choice", "wrong"))))
    return sorted(c for c in cited - set(d["entries"]) if st.get(c) == "RESOLVED")


def unlogged() -> list[str]:
    """Register entries that left the judgement queue with no §4 block naming them.

    A measurement legitimately has none. A CHOICE recorded only as prose in a resolved entry is
    the failure this script exists to catch, so the list is a lead, not a verdict.
    """
    text = REGISTER.read_text()
    listed = {c for d in parse() for c in d["entries"]}
    rows = re.findall(r"^\|\s*\[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|\s*\*{0,2}([A-Z]+)"
                      r"\*{0,2}\s*\|\s*([^|]*)\|", text, re.M)
    return [c for c, status, action in rows
            if status == "RESOLVED" and "decision" not in action.lower() and c not in listed]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    ds = parse()

    if a.check:
        bad = [d for d in ds if d["missing"]]
        for d in bad:
            names = ", ".join(WANT[k] for k in d["missing"])
            print(f"  INCOMPLETE  {d['title'][:48]} — missing: {names}")
        print(f"\n  {len(ds)} logged decision(s), {len(bad)} incomplete")
        if not ds:
            print("  none logged: either none has been reached, or the log is not being kept")
        return 1 if bad else 0

    if a.brief:
        for d in ds:
            state = "DECIDED" if d["settled"] else "PENDING"
            print(f"\n[{state}] {d['title']}")
            if d["entries"]:
                print(f"  register: {', '.join(d['entries'])}")
            for k in ("structural", "target", "options", "choice", "wrong"):
                if k in d:
                    print(f"  {WANT[k]}:\n    {d[k]}")
        print(f"\n{len(ds)} decision(s) logged in docs/INTEGRATION-DELTA.md. "
              "Recomputed; nothing here is stored.")
        return 0

    print(f"  {'state':<10}{'register':<14}what")
    print("  " + "-" * 72)
    for d in ds:
        print(f"  {'DECIDED' if d['settled'] else 'PENDING':<10}"
              f"{','.join(d['entries'])[:12]:<14}{d['title'][:46]}")
    st = statuses()
    for d in ds:
        if not d["settled"]:
            moved = shifted_under(d, st)
            if moved:
                print(f"\n  PENDING {','.join(d['entries'])} reasons about "
                      f"{', '.join(moved)}, all now RESOLVED — re-read before deciding.")
                print("  (over-reports: it cannot tell which were already settled when the "
                      "decision was written. A re-read is cheap; a moved premise nobody noticed "
                      "is not.)")
    miss = unlogged()
    if miss:
        print(f"\n  RESOLVED with no §4 block: {', '.join(miss)}")
        print("  (a measurement needs none; a CHOICE recorded this way cannot be enumerated)")
    print(f"\n  {len(ds)} logged, {sum(d['settled'] for d in ds)} settled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
