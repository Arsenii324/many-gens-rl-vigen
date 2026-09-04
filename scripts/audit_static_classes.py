#!/usr/bin/env python3
"""Three defect classes that were findable by reading and were not found. [C77](../docs/CONSTRUCTION.md#c77), [C79](#), [C80](#)

    python scripts/audit_static_classes.py
    python scripts/audit_static_classes.py --strict    # exit 1 if any class reports a hit

## Why this exists

On 2026-08-27/28 the owner asked a question this repository had no answer to: *"if it's you finding
things that influence experiment results, why were these not found at implementation?"* Sorting
that day's findings by whether **running** was necessary to find them gives an uncomfortable split.

**Needed a run** — [C70](../docs/CONSTRUCTION.md#c70) (torch kernel selection moves an episode
across Door's `hinge_qpos > 0.3` threshold), [C84](../docs/CONSTRUCTION.md#c84) (a policy scale of
exactly 0 under bounds that should make it unreachable). No amount of reading finds those.

**Did not need a run, and cost real compute anyway:**

| class | instance | what it cost |
|---|---|---|
| **loop boundary** | [C77](../docs/CONSTRUCTION.md#c77): the save sits inside `if time_step.last():` at the TOP of a `while step < until` loop, so a run launched at exactly N never saves at N | a 3.5-hour run, and a default that would have produced **zero** checkpoints for every future cell |
| **written, never read** | [C79](../docs/CONSTRUCTION.md#c79): `use_tb=True` added `actor_loss`/`critic_loss` to `train.csv`; for six days nothing read them, while divergence was checked only post-hoc on checkpoints | 64 minutes of a run that was NaN from minute six |
| **never executed** | [C80](../docs/CONSTRUCTION.md#c80): `mutants/run.py` had never once passed its own sanity gate, so no mutant had ever been measured | the suite's sensitivity was unmeasured while three documents cited the framework |

`scripts/audit_dead_knobs.py` already covers a fourth class — a knob **passed and never read**
([C71](../docs/CONSTRUCTION.md#c71)). These three had no checker between them, which is the gap
this file closes.

## What it does NOT claim

It finds **candidates**, not defects, and it is deliberately noisy in the safe direction. A loop
whose exit and whose side effect are in the same body is usually fine; a column nobody reads is
usually just a column. **The output is a list to look at, not a list to fix** — the value is that
the question gets asked at all, on every run, rather than after a wasted afternoon.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

SKIP = ("__pycache__", "/ext/", "/.git/", "site-packages", "/third_party/",
        "dm_control", "/coinrun/", "gym-minigrid", "/baselines/")

#: Where the twelve baselines' live code is. `rlgen/` is the retired port and is excluded: its
#: loops cannot cost a run any more, and including it would bury the live hits.
LIVE = ["RL-ViGen-upstream/train.py", "RL-ViGen-upstream/algos", "runnable", "scripts"]


def _files():
    for rel in LIVE:
        p = ROOT / rel
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*.py"):
                if not any(x in str(f) for x in SKIP):
                    yield f


def loop_boundary_hits() -> list[str]:
    """A `while <cond>:` whose body has a side effect gated on a condition that can coincide with exit.

    The C77 shape exactly: the loop tests `step < N` at the top, and the body's save is gated on
    `step % k == 0`. When `N % k == 0` the two conditions meet on the same iteration, the while-test
    runs first, and the side effect for step N never happens. Flagged wherever a modulo-gated call
    appears inside a while whose condition bounds the same variable.
    """
    out = []
    for f in _files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.While):
                continue
            cond = ast.unparse(node.test)
            body = ast.unparse(node)
            if "%" not in body:
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.If):
                    continue
                t = ast.unparse(sub.test)
                if "%" not in t:
                    continue
                # a save/write/dump gated on a modulo, inside a bounded while
                if re.search(r"\b(save|dump|write|snapshot|checkpoint|log)\w*\s*\(",
                             ast.unparse(sub)):
                    out.append(f"{f.relative_to(ROOT)}:{sub.lineno}  `if {t[:44]}` inside "
                               f"`while {cond[:34]}` — does the boundary iteration run?")
    return out


def written_never_read(cols: dict[str, list[str]]) -> list[str]:
    """A quantity written to a log that nothing in the tree reads back.

    C79's shape: the column existed for six days and every divergence check went to the checkpoint
    instead. Names are taken from the writers and searched for in every live file; a name that
    appears only where it is written is a candidate.
    """
    out = []
    hay = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in _files())
    for name, where in cols.items():
        readers = [m for m in re.finditer(rf"['\"]{re.escape(name)}['\"]", hay)]
        if len(readers) <= len(where):
            out.append(f"{name!r} written at {', '.join(where)} and read nowhere in the live tree")
    return out


def never_executed() -> list[str]:
    """An instrument with no test and no caller — nothing establishes it has ever run."""
    out = []
    tests = "\n".join((ROOT / "tests").rglob("*.py") and
                      [f.read_text(encoding="utf-8", errors="replace")
                       for f in (ROOT / "tests").rglob("*.py")])
    callers = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                        for f in _files() if f.parent.name != "scripts")
    shell = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                      for f in (ROOT / "scripts").rglob("*.sh"))
    for f in sorted((ROOT / "scripts").glob("*.py")):
        stem = f.stem
        if stem.startswith("_"):
            continue
        if stem in tests or stem in callers or stem in shell:
            continue
        out.append(f"scripts/{f.name} — no test names it and nothing calls it; "
                   "nothing establishes it has ever run (C80's class)")
    return out


#: Columns the natives' trainer writes, from `train.py`'s own `log(...)` calls. Listed rather than
#: parsed: the writer builds them through a context manager and a parser would be guessing.
LOGGED = {
    "actor_loss": ["RL-ViGen-upstream/algos/*.py"],
    "critic_loss": ["RL-ViGen-upstream/algos/*.py"],
    "critic_q1": ["RL-ViGen-upstream/algos/*.py"],
    "critic_target_q": ["RL-ViGen-upstream/algos/*.py"],
    "batch_reward": ["RL-ViGen-upstream/algos/*.py"],
    "actor_logprob": ["RL-ViGen-upstream/algos/*.py"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    print("STATIC DEFECT CLASSES — three that were findable by reading and were not found\n")
    print("  Candidates, not defects. The value is that the question is asked on every run")
    print("  rather than after a wasted afternoon. See C77, C79, C80.\n")

    total = 0
    for title, hits, note in (
        ("loop boundary (C77)", loop_boundary_hits(),
         "a modulo-gated side effect inside a bounded while: does the boundary iteration run?"),
        ("written, never read (C79)", written_never_read(LOGGED),
         "a logged quantity nothing reads back — an instrument you already paid for"),
        ("never executed (C80)", never_executed(),
         "an instrument with no test and no caller"),
    ):
        print(f"  {title}  — {note}")
        if not hits:
            print("    (none)\n")
            continue
        total += len(hits)
        for h in hits:
            print(f"    {h}")
        print()

    print(f"  {total} candidate(s). A hit is a question, not a verdict.")
    return 1 if (a.strict and total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
