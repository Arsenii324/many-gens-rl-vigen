#!/usr/bin/env python3
"""Which instruments in this repo are themselves checked, and which are taken on trust?

`docs/SYSTEM.md` carries the standard: *every checker should have a test that deliberately breaks
what it claims to check; a green instrument is evidence only if something is known to make it
red.* That is a mechanical claim about this repository, so it should be **run**, not written down
— the same document records three figures that were stale within hours of being typed, the
instrument/test counts among them.

    python scripts/audit_instruments.py            # table, worst-covered first
    python scripts/audit_instruments.py --json     # machine-readable
    python scripts/audit_instruments.py --strict   # exit 1 if any instrument has no test at all

## What "red-green" means here, and why the number is a floor

Coverage is detected two ways, both cheap and both imperfect:

- **referenced**: a test file mentions the instrument's module name. A test that imports a script
  and never asserts anything would count, so this over-reports.
- **red-green**: the covering test text contains a marker of deliberate breakage — `mutant`,
  `pytest.raises`, `deliberately`, `must fail`, and so on. A test that verifies a failure mode
  without using any of those words is missed, so this **under**-reports.

So read the red-green share as a floor, not a measurement, and read a `NO` as "look at this one",
not as proof. The honest use is triage: it found seven uncovered instruments on 2026-08-18, two of
which were load-bearing for published claims.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

RED_MARKS = ("mutant", "mutat", "red-green", "red_green", "must fail", "deliberately",
             "pytest.raises", "planted", "broken", "would have missed", "uninterpretable")


def audit(root: pathlib.Path = ROOT) -> list[dict]:
    tests = {p: p.read_text(errors="replace") for p in sorted((root / "tests").glob("*.py"))}
    rows = []
    for d in ("scripts", "tools"):
        for s in sorted((root / d).glob("*.py")):
            if s.stem.startswith("_"):
                continue
            refs = [p.name for p, t in tests.items() if re.search(rf"\b{re.escape(s.stem)}\b", t)]
            covering = "\n".join(tests[p] for p in tests if p.name in refs).lower()
            rows.append({"instrument": s.stem, "tests": refs,
                         "red_green": any(m in covering for m in RED_MARKS)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any instrument has no test referencing it")
    a = ap.parse_args()
    rows = audit()
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        tested = [r for r in rows if r["tests"]]
        red = [r for r in rows if r["red_green"]]
        print(f"  instruments: {len(rows)}")
        print(f"    referenced by at least one test : {len(tested)} "
              f"({100*len(tested)//max(1,len(rows))}%)")
        print(f"    with a test asserting a FAILURE : {len(red)} "
              f"({100*len(red)//max(1,len(rows))}%)  <- a floor, see the docstring\n")
        print(f"    {'instrument':<32}{'tests':>6}  red-green?")
        print("    " + "-" * 60)
        for r in sorted(rows, key=lambda r: (r["red_green"], len(r["tests"]), r["instrument"])):
            print(f"    {r['instrument']:<32}{len(r['tests']):>6}  "
                  f"{'yes' if r['red_green'] else 'NO ':<4} {','.join(r['tests'])[:24]}")
    if a.strict and any(not r["tests"] for r in rows):
        print("\n  strict: an instrument has no test referencing it")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
