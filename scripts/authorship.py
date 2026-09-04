#!/usr/bin/env python3
"""Every first-party file, measured against every reference on disk. No sampling, no vibes.

    python scripts/authorship.py            # full table
    python scripts/authorship.py --summary  # totals only

## Why

Documents in this repo make claims about what is ported and what is authored. Those claims were
written file by file, by the person writing the file, and several have been falsified today by one
command. This walks **every** `.py` under `rlgen/`, `tools/` and `scripts/` and asks the same
question of each: how much of it descends, textually, from any reference available on this disk?

The answer is a number per file. It is not a quality judgement and it is not a verdict — see the
limits below — but it cannot be argued with, and it covers the files nobody chose to write about.

## Limits, stated because the number invites over-reading

- **Descent is provenance, not correctness.** `ctrl` reads 0% legitimately (its reference is
  JAX/Flax); `alda` reads ~100% against a *sibling project's port* and 0% against the authors'
  repo. A high number can mean "copied from the wrong thing" and a low one can mean "reimplemented
  faithfully in a different shape". Always read the matched source, printed alongside.
- **It cannot see semantics.** Two files can share no lines and compute the same function.
- **The denominator differs from `scripts/state.py`'s, and they are not interchangeable.**
  Here `pct = kept / len(OUR file)` — "how much of what we wrote descends". `state.py` uses
  `kept / len(REFERENCE file)` — "how much of the reference we reproduced". Same file reads 87%
  here and 99% there, and both are right. Quoting one for the other was a live error until
  2026-08-16. Ask which question you want before reading either number.
- **A percentage says nothing about the RESIDUAL, and the residual is usually the point.**
  `sac.py`'s missing 7% is a docstring, import-path rewrites and `.cuda()` -> `.to(self.device)`
  — entirely benign. Another file's missing 7% could be a dropped loss term. The number narrows
  where to look; only reading the diff says what it means.
- **It cannot see what SHOULD have been ported.** A file that authored something already present
  in an unread reference scores as authored, correctly, and looks the same as one that had no
  reference at all. Distinguishing those requires reading.
"""
from __future__ import annotations

import difflib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIRST_PARTY = ["rlgen/**/*.py", "tools/*.py", "scripts/*.py"]
REF_ROOTS = ["ext", "RL-ViGen-upstream", "../gen-rebuttal/vigen-idaac"]


def code(p: pathlib.Path) -> list[str]:
    try:
        s = p.read_text(errors="replace")
    except OSError:
        return []
    s = re.sub(r'^\s*"""(?:.|\n)*?"""\n', "", s, count=1)
    return [l.rstrip() for l in s.splitlines() if l.strip() and not l.strip().startswith("#")]


def main() -> int:
    refs: list[pathlib.Path] = []
    for r in REF_ROOTS:
        rp = (ROOT / r).resolve()
        if rp.exists():
            refs += [f for f in rp.rglob("*.py") if ".git" not in f.parts]
    # vendored bases live inside rlgen/ but ARE references
    refs += [f for f in ROOT.rglob("_upstream_*/*.py")]

    ours: list[pathlib.Path] = []
    for g in FIRST_PARTY:
        ours += [f for f in ROOT.glob(g)
                 if "_upstream_" not in str(f) and "__pycache__" not in str(f)]
    ours = sorted(set(ours))

    rows, tot_lines, tot_kept = [], 0, 0
    for o in ours:
        ol = code(o)
        if not ol:
            continue
        best, src = 0.0, None
        for r in refs:
            rl = code(r)
            if not rl:
                continue
            sm = difflib.SequenceMatcher(None, rl, ol, autojunk=False)
            if sm.quick_ratio() < 0.20:
                continue
            kept = sum(b.size for b in sm.get_matching_blocks())
            pct = 100 * kept / len(ol)          # share of OUR file that descends
            if pct > best:
                best, src = pct, r
        rows.append((str(o.relative_to(ROOT)), len(ol), best, src))
        tot_lines += len(ol)
        tot_kept += len(ol) * best / 100

    if "--summary" not in sys.argv:
        print(f'{"file":<44}{"lines":>6}{"descent":>9}  matched reference')
        print("-" * 104)
        for name, n, pct, src in sorted(rows, key=lambda r: -r[1]):
            s = str(src.relative_to(ROOT)) if src and ROOT in src.parents else (
                str(src) if src else "-")
            print(f'{name:<44}{n:>6}{pct:>8.0f}%  {s[-52:] if src else "(no reference matched)"}')
        print()
    print(f"first-party code lines: {tot_lines}")
    print(f"  descending from some reference : {tot_kept:>7.0f}  ({100*tot_kept/max(1,tot_lines):.0f}%)")
    print(f"  authored here                  : {tot_lines-tot_kept:>7.0f}  "
          f"({100*(tot_lines-tot_kept)/max(1,tot_lines):.0f}%)")
    print("\nDescent is provenance, not correctness — read this file's docstring before concluding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
