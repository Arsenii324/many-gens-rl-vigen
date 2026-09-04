#!/usr/bin/env python3
"""Maintain `docs/CONSTRUCTION.md` safely: recount statuses, check structure, locate an entry.

    python scripts/register.py --check          # structure + counts, exit 1 on drift
    python scripts/register.py --recount        # rewrite the summary line from the table
    python scripts/register.py --show C37       # print one entry
    python scripts/register.py --bounds C37     # the safe line range for an edit

## Why this exists — a tooling fix for a mistake I kept making

The register is edited often, and I damaged it repeatedly by editing it from shell:

1. **Unquoted heredocs, three times.** `python3 - <<PY` lets the shell expand the body, so every
   `` `backtick` `` in markdown ran as a command substitution and was replaced by its (empty)
   output. Entries came out as "the 10  functions". Quoting the delimiter (`<<'PY'`) fixes it, but
   the deeper fix is not to write prose through a shell at all.
2. **Slices anchored on the wrong boundary, twice.** Replacing an entry by slicing from its
   heading to the *next* `### C` heading silently ate the `## Resolved` section heading when the
   entry was the last one in its section, because the next `### C` lived in the following section.

Both are the same shape: an edit that *looked* like it worked. Neither was caught by review; the
register's own structure test caught one and the other was found by eye.

So: **prose goes through the Edit tool** (which fails loudly on a mismatch and does not interpret
backticks), and the one thing that genuinely needed computation — recounting statuses after adding
an entry — lives here instead of in an ad-hoc heredoc.

`--bounds` exists for the second failure: it reports the range an entry actually occupies and
refuses to cross a `## ` section boundary.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "CONSTRUCTION.md"
STATUSES = ("OPEN", "READY", "BLOCKED", "MONITORED", "RESOLVED")
ROW = re.compile(r"^\|\s*\[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|\s*\*{0,2}([A-Z-]+)\*{0,2}\s*\|", re.M)
COUNT_LINE = re.compile(
    r"\*\*(\d+) OPEN · (\d+) READY · (\d+) BLOCKED · (\d+) MONITORED · (\d+) RESOLVED · "
    r"(\d+) total\.\*\*")


def rows(text: str) -> list[tuple[str, str]]:
    return ROW.findall(text)


def sections(text: str) -> dict[str, tuple[int, int]]:
    """{id: (start, end)} character offsets, never crossing a `## ` section heading."""
    out = {}
    for m in re.finditer(r"^### (C\d+) — ", text, re.M):
        cid, start = m.group(1), m.start()
        nxt = re.search(r"^(### C\d+ — |## )", text[start + 4:], re.M)
        end = start + 4 + nxt.start() if nxt else len(text)
        out[cid] = (start, end)
    return out


def recount(text: str) -> tuple[str, str]:
    c = collections.Counter(s for _, s in rows(text))
    line = (f"**{c['OPEN']} OPEN · {c['READY']} READY · {c['BLOCKED']} BLOCKED · "
            f"{c['MONITORED']} MONITORED · {c['RESOLVED']} RESOLVED · {len(rows(text))} total.**")
    return COUNT_LINE.sub(lambda _: line, text), line


def check(text: str) -> list[str]:
    problems = []
    r = rows(text)
    if not r:
        return ["no summary rows parsed -- the table format changed, or this checker is blind"]
    ids = [i for i, _ in r]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        problems.append(f"duplicate ids: {dupes}")
    bad = sorted({(i, s) for i, s in r if s not in STATUSES})
    if bad:
        problems.append(f"statuses outside {list(STATUSES)}: {bad}")
    detail = set(sections(text))
    if set(ids) != detail:
        problems.append(f"summary-only: {sorted(set(ids) - detail)}; "
                        f"section-only: {sorted(detail - set(ids))}")
    m = COUNT_LINE.search(text)
    if not m:
        problems.append("summary count line missing or reworded")
    else:
        c = collections.Counter(s for _, s in r)
        claimed = dict(zip(STATUSES, (int(g) for g in m.group(1, 2, 3, 4, 5))))
        for k, v in claimed.items():
            if c[k] != v:
                problems.append(f"count line says {v} {k}, table has {c[k]}")
        if int(m.group(6)) != len(r):
            problems.append(f"count line total {m.group(6)} != {len(r)} rows")
    # The mangling signature from the unquoted-heredoc mistake: a `code span` that ran as a command
    # substitution is replaced by its empty output, leaving two spaces mid-sentence.
    #
    # Fenced-block STATE must be tracked, not just the fence line: aligned code inside a block
    # ("model.py:83   image_embedding_size = ...") is legitimately double-spaced and produced a
    # false positive on the first version. Tables and indented lines are skipped for the same
    # reason. This is a heuristic and is allowed to miss; it must not cry wolf, because a checker
    # that reports routine formatting as damage stops being read.
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith(("|", " ", "\t", ">")):
            continue
        if re.search(r"[\w,;)\.]  +[\w(*]", line):
            problems.append(f"line {n}: double space mid-sentence -- possible eaten code span: "
                            f"{line.strip()[:70]!r}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--recount", action="store_true")
    ap.add_argument("--show", metavar="ID")
    ap.add_argument("--bounds", metavar="ID")
    a = ap.parse_args()
    if not DOC.exists():
        print(f"missing: {DOC}")
        return 1
    text = DOC.read_text(encoding="utf-8")

    if a.show or a.bounds:
        cid = (a.show or a.bounds).upper()
        secs = sections(text)
        if cid not in secs:
            print(f"{cid} not found. Known: {', '.join(sorted(secs))}")
            return 1
        s, e = secs[cid]
        if a.show:
            print(text[s:e].rstrip())
        else:
            ls = text[:s].count("\n") + 1
            le = text[:e].count("\n")
            print(f"{cid}: lines {ls}-{le} ({e - s} chars). Safe to replace this range; it stops "
                  "at the next '### C' or '## ' heading, whichever comes first.")
        return 0

    if a.recount:
        new, line = recount(text)
        if new != text:
            DOC.write_text(new, encoding="utf-8")
            print(f"recounted: {line}")
        else:
            print(f"already correct: {line}")
        return 0

    problems = check(text)
    print(f"{len(rows(text))} entries")
    for p in problems:
        print(f"  PROBLEM  {p}")
    if not problems:
        print("  structure and counts agree")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
