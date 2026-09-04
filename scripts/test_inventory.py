#!/usr/bin/env python3
"""What is the test suite actually verifying? Classified by what each file imports.

    python scripts/test_inventory.py
    python scripts/test_inventory.py --by-file

This is `docs/CONSTRUCTION.md` C30, option 2: make the green figure readable before deciding
whether to rebuild anything. "N tests green" is the sentence most likely to be trusted about this
project, and it does not distinguish *what* is green.

## The classification, and why these boundaries

The `rlgen/` package was the project's original design -- one shared trainer, evaluator and
logger for all twelve -- and it was **superseded** by twelve hermetic clones each running its
authors' own `train.py`. It was not deleted, and most of the suite still exercises it. But not
all of `rlgen/` is port-era: `protocol.py` defines the comparability contract the *clone* era
uses (`env_patches` pins P1-P13 against the vendored tree the clones run, `OBSERVATION_GEOMETRY`
describes the twelve). So splitting on "imports rlgen" is too crude, and this splits on *which*
module:

    CONTRACT   imports only rlgen.protocol / rlgen.tags -- live, used by the clone era
    PORT       imports rlgen.{agents,envs,trainer,trainer_onpolicy,replay,registry,
               evaluate,logging_,algos} -- the superseded implementation
    CLONE      references runnable/ -- the twelve that actually produce numbers
    STANDALONE neither: metrics definitions, doc staleness, register structure, packaging

A file counted as CLONE takes precedence over PORT, because what matters is whether it constrains
something that produces a reported number.

## What this cannot tell you

Whether a port-era test is *worthless*. It is not: the port-era suite bought the audit findings
that justified moving to clones, and several of those tests (real environments, eval regimes)
constrain shared machinery the clones also use. This measures coverage attribution, not value.

It also classifies by import, not by behaviour. A test that imports nothing but shells out to a
clone's entry point would be misfiled; `--by-file` exists so that can be checked by eye.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

CONTRACT_MODS = {"protocol", "tags"}
PORT_MODS = {"agents", "envs", "trainer", "trainer_onpolicy", "replay", "registry",
             "evaluate", "logging_", "algos"}


def classify(path: pathlib.Path) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    n = len(re.findall(r"^\s*def test_", text, re.M))
    # NESTED paths matter: the parity suites import `from rlgen.algos.ppg.algo import Learner`,
    # and a pattern anchored on a single segment before " import" silently matches none of them
    # -- which filed ~80 port-era tests as STANDALONE on the first run of this script.
    mods = set(re.findall(r"from rlgen\.(\w+)[\w.]* import|import rlgen\.(\w+)", text))
    flat = {a or b for a, b in mods}
    # UPPER BOUND, not a count of clone-facing tests. Any MENTION of a `runnable/` path counts,
    # including one inside a string literal that is test data rather than a target -- e.g.
    # `tests/test_greenmark.py` listing `runnable/_shim/...` to assert it classifies as code, and
    # `tests/test_test_inventory.py` embedding `runnable/idaac` in a synthetic fixture. Those two
    # alone added 15 to CLONE on 2026-08-18 without constraining a clone at all.
    #
    # Left as a documented upper bound rather than tightened: every sharper rule tried here
    # (require a filesystem call, require an import from a clone) also matched those files, and a
    # detector that is wrong in a way nobody can predict is worse than one that is wrong in a way
    # written down. Read CLONE as "at most this many".
    touches_clone = bool(re.search(r"runnable[/.]", text))
    if touches_clone:
        return "CLONE", n
    if flat & PORT_MODS:
        return "PORT", n
    if flat & CONTRACT_MODS:
        return "CONTRACT", n
    return "STANDALONE", n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--by-file", action="store_true", help="print every file's verdict")
    a = ap.parse_args()

    files = sorted(TESTS.glob("test_*.py"))
    if not files:
        print(f"no test files under {TESTS} -- this checker would report success while "
              "checking nothing")
        return 1

    counts: collections.Counter = collections.Counter()
    per_file = []
    for f in files:
        kind, n = classify(f)
        counts[kind] += n
        per_file.append((kind, n, f.name))

    if a.by_file:
        print(f"  {'kind':<11}{'tests':>6}  file")
        print("  " + "-" * 58)
        for kind, n, name in sorted(per_file, key=lambda r: (r[0], -r[1])):
            print(f"  {kind:<11}{n:>6}  {name}")
        print()

    total = sum(counts.values())
    print(f"  {'target':<12}{'test fns':>9}{'share':>8}   what it constrains")
    print("  " + "-" * 74)
    NOTE = {
        "CLONE": "the twelve that produce numbers -- UPPER BOUND, see classify()",
        "CONTRACT": "rlgen/protocol.py -- live, used by the clone era",
        "PORT": "the SUPERSEDED rlgen implementation",
        "STANDALONE": "metrics, docs, register, packaging",
    }
    for kind in ("CLONE", "CONTRACT", "PORT", "STANDALONE"):
        n = counts[kind]
        print(f"  {kind:<12}{n:>9}{n / total:>7.0%}   {NOTE[kind]}")
    print("  " + "-" * 74)
    print(f"  {'TOTAL':<12}{total:>9}")

    print(f"\n  Counts are test FUNCTION DEFINITIONS, not what pytest collects after")
    print("  parametrisation -- the collected number is larger and differently distributed.")
    print("\n  Port-era tests are not worthless: they bought the audit findings that justified")
    print("  moving to clones, and some constrain machinery the clones share. This measures")
    print("  where coverage POINTS, not what it is worth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
