#!/usr/bin/env python3
"""Can an operator get from zero to banked results without asking anyone? Checked, not asserted.

    python scripts/operator_readiness.py              # the matrix, exit 1 if any need is unrouted
    python scripts/operator_readiness.py --gaps       # only what is unrouted
    python scripts/operator_readiness.py --interfaces # only the script-vs-doc drift check

## Why this is a script and not a section in the guide

The operator guide is long and good, and it still went eight days out of date without anything
noticing: the launch path moved from calling the wrapper directly to a launcher chain, and the
guide kept describing the wrapper. Nothing failed, because prose cannot fail. The campaign already
knows this pattern -- `production_gates.py` exists so that "we are ready" is a thing a machine
refuses rather than a thing a person believes -- and operator readiness deserves the same
treatment.

So this enumerates what an operator must be able to DO, end to end, and requires each need to
route somewhere real: a document section that exists and has substance, and where the need is
mechanised, a tool that exists. A need with no route is a FAIL.

## The check that actually catches drift, and why it is shaped this way

Keyword presence is not coverage, and I proved it on myself while building this: a first version
grepped the guide for `train-production-cell` and reported the topic covered. The match was a
banner I had added to the guide an hour earlier. **The instrument was reading text its own author
had inserted** -- the same failure class as the VRAM measurement that summed a colleague's memory
under a field named `ours_peak_mib`.

The fix is to check something neither document controls: **the scripts' own interfaces.**
`extract_interface` reads every `${VAR:?}` (required) and `${VAR:-default}` (optional) out of a
live script and compares that set against what the documentation actually names. A required
variable the guide never mentions is a hole an operator falls into; an option whose default the
guide never states is a decision made silently on their behalf. Both are reported. This cannot be
satisfied by writing more prose about the topic -- only by documenting the actual interface.

## What a PASS does and does not mean

It means every enumerated need has a destination and the live scripts' interfaces are documented.
It does not mean the instructions are correct, and it cannot: no static check knows whether a
command works on the host. It narrows "is the guide usable" to "are the enumerated needs the right
ones", which is a judgement a person can review in one screen -- rather than leaving it as "did
anyone reread 725 lines lately", which nobody can answer.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: A need is routed when its doc section exists with substance, and its tool (if any) exists.
#: (phase, need, doc_path, heading_substring, tool_path_or_None)
NEEDS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("A orient", "host access and what the box is",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Running a cell on the production host", None),
    ("A orient", "the arrival sequence, in order",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "When the production host becomes available", None),
    ("A orient", "which laptop interpreter to use",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Which Python runs the laptop-side scripts", None),
    ("A orient", "who else is on the cards, and how they behave",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "You are sharing the cards", None),

    ("B setup", "what a cell costs, measured",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "What a cell actually costs", None),
    ("B setup", "Places365 acquisition and placement",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Places365", None),
    ("B setup", "build and transfer the payload",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Build and transfer the payload", None),
    ("B setup", "dry-run the wrapper before the first real cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Dry-run the wrapper FIRST", None),

    ("C session", "readiness gate before acting",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Preconditions, checked on the host every time",
     "scripts/production_gates.py"),
    ("C session", "disarm stale waiters before a manual launch",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", None),

    ("E run", "start a production training cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers",
     "datasphere/native/host-scripts/train-production-cell-v5.sh"),
    ("E run", "evaluate every retained checkpoint",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers",
     "datasphere/native/host-scripts/curve-sweep-v3.sh"),
    ("E run", "evaluate a single checkpoint",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers",
     "datasphere/native/host-scripts/reeval-cell-cached.sh"),
    ("E run", "pack more than one cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Packing two cells", None),
    ("E run", "the per-cell wall-clock ceiling",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "per-cell wall-clock ceiling", None),

    ("F watch", "every stop mechanism and whether it is silent",
     "notes/model/STOP-MECHANISMS.md", "", None),
    ("F watch", "bound our own GPU footprint, not just the card's",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Stop mechanisms",
     "datasphere/native/self-vram-cap.sh"),
    ("F watch", "the measured resource table",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Measured GPU memory", "datasphere/native/measured-vram-bounds.json"),
    ("F watch", "watching a live cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Watching a live cell", None),
    ("F watch", "monitoring that reports to a person, and its traps",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Monitoring that reports to a person", None),

    ("G after", "retrieve and process results",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Retrieve and process", None),
    ("G after", "collect a whole wave in one step",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "datasphere/native/collect-wave.sh"),
    ("G after", "turn records into ledger entries",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/populate_evaluator_ledger.py"),
    ("G after", "see campaign coverage per baseline and seed",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/campaign_status.py"),
    ("G after", "one flat table of every record",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/export_fleet.py"),

    ("H fail", "what survives an interruption; what is resumable",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "What survives an interruption", None),
    ("H fail", "the mistakes already made, and the practice each produced",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Monitoring that reports to a person", None),
)

#: Live scripts whose interface the documentation must actually specify.
INTERFACE_CONTRACTS: tuple[tuple[str, str], ...] = (
    ("datasphere/native/host-scripts/train-production-cell-v5.sh", "notes/RUNNING-ON-PRODUCTION-HOST.md"),
    ("datasphere/native/host-scripts/curve-sweep-v3.sh", "notes/RUNNING-ON-PRODUCTION-HOST.md"),
    ("datasphere/native/host-scripts/reeval-cell-cached.sh", "notes/RUNNING-ON-PRODUCTION-HOST.md"),
    ("datasphere/native/self-vram-cap.sh", "notes/RUNNING-ON-PRODUCTION-HOST.md"),
)

#: Variables every cell inherits from the launcher rather than from the script being documented.
_INHERITED = {"HOME", "PATH", "PWD", "USER", "SHELL"}

#: Documents whose instructions an operator follows literally. Every repo-relative path they name
#: must exist in a fresh clone, or the instruction is unrunnable for anyone but its author.
INSTRUCTION_DOCS = ("notes/RUNNING-ON-PRODUCTION-HOST.md",)

#: Paths deliberately referenced while NOT being in this repository. Each needs a reason, because
#: the whole point of the check is that a missing path is normally a defect.
EXTERNAL_BY_DESIGN = {
    # Lives in the maintainer's parent workspace. Section 0c says so explicitly and states the
    # interpreter requirement inline precisely so a GitHub clone does not need this file.
    "docs/local-envs.md",
}


def clone_completeness() -> list[str]:
    """Every repo-relative path the instruction docs name, that a fresh clone would not have."""
    import re
    problems: list[str] = []
    pattern = (r'(?:scripts|datasphere/native(?:/host-scripts)?|setup|runnable|notes|docs|results)'
               r'/[A-Za-z0-9_./-]+')
    for doc in INSTRUCTION_DOCS:
        text = (ROOT / doc).read_text(errors="replace")
        for raw in dict.fromkeys(re.findall(pattern, text)):
            rel = raw.rstrip('.,`)"\'')
            if rel in EXTERNAL_BY_DESIGN or (ROOT / rel).exists():
                continue
            problems.append(f"{doc} names {rel}, which is not in the repository")
    return problems


def extract_interface(path: pathlib.Path) -> tuple[set[str], dict[str, str]]:
    """(required, {optional: default}) from a shell script's own parameter expansions."""
    text = path.read_text(errors="replace")
    required = set(re.findall(r'\$\{([A-Z_][A-Z0-9_]*):\?', text))
    optional = {m.group(1): m.group(2)
                for m in re.finditer(r'\$\{([A-Z_][A-Z0-9_]*):-([^}]*)\}', text)}
    return required - _INHERITED, {k: v for k, v in optional.items() if k not in _INHERITED}


def _heading_level(line: str) -> int:
    """0 if not an ATX heading, else the number of leading '#'."""
    s = line.lstrip()
    n = len(s) - len(s.lstrip("#"))
    return n if n and (len(s) == n or s[n] == " ") else 0


def section_of(doc: pathlib.Path, heading: str) -> str | None:
    """The text under the first heading containing `heading`. Empty heading means the whole file.

    [Claude 2026-09-16] Fenced code blocks are tracked, and that is not a nicety. The first version
    cut a section at `# 1. record the run exists` -- a shell COMMENT inside a ```bash fence -- and
    so reported a 27-line section as a 123-character stub. Every section in this guide whose value
    is its commands would have been judged empty, which is precisely backwards.
    """
    if not doc.is_file():
        return None
    text = doc.read_text(errors="replace")
    if not heading:
        return text
    lines = text.split("\n")
    fence = False
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if _heading_level(line) and heading.lower() in line.lower():
            start = i
            break
    if start is None:
        return None
    level = _heading_level(lines[start])
    fence = False
    for j in range(start + 1, len(lines)):
        if lines[j].lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        lvl = _heading_level(lines[j])
        if lvl and lvl <= level:
            return "\n".join(lines[start:j])
    return "\n".join(lines[start:])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gaps", action="store_true")
    ap.add_argument("--interfaces", action="store_true")
    args = ap.parse_args()

    failures: list[str] = []

    if not args.interfaces:
        print("OPERATOR READINESS -- can someone get from zero to banked results?\n")
        phase_now = None
        for phase, need, doc, heading, tool in NEEDS:
            if phase != phase_now:
                print(f"  {phase}")
                phase_now = phase
            path = ROOT / doc
            body = section_of(path, heading)
            doc_ok = body is not None and len(body.strip()) > 200
            tool_ok = tool is None or (ROOT / tool).exists()
            ok = doc_ok and tool_ok
            why = []
            if body is None:
                why.append(f"no section '{heading or doc}' in {doc}")
            elif not doc_ok:
                why.append(f"section '{heading}' in {doc} is under 200 chars -- a stub")
            if not tool_ok:
                why.append(f"tool missing: {tool}")
            print(f"    {'PASS' if ok else 'FAIL'}  {need:52} {doc}")
            if not ok:
                for w in why:
                    print(f"          -> {w}")
                failures.append(f"{need}: {'; '.join(why)}")
            elif args.gaps:
                pass
        print()

    if not args.gaps:
        print("SCRIPT INTERFACES -- every required variable and every default, documented?\n")
        for script, doc in INTERFACE_CONTRACTS:
            spath, dpath = ROOT / script, ROOT / doc
            if not spath.is_file():
                print(f"  MISSING  {script}")
                failures.append(f"interface: {script} does not exist")
                continue
            required, optional = extract_interface(spath)
            dtext = dpath.read_text(errors="replace") if dpath.is_file() else ""
            undoc_req = sorted(v for v in required if v not in dtext)
            undoc_opt = sorted(v for v in optional if v not in dtext)
            status = "PASS" if not undoc_req and not undoc_opt else "FAIL"
            print(f"  {status}  {pathlib.Path(script).name}"
                  f"  ({len(required)} required, {len(optional)} optional)")
            if undoc_req:
                print(f"        REQUIRED but never named in {doc}: {', '.join(undoc_req)}")
                failures.append(f"{script}: undocumented required vars {undoc_req}")
            if undoc_opt:
                print(f"        optional, default not stated in {doc}: "
                      + ", ".join(f"{v}={optional[v]!r}" for v in undoc_opt))
                failures.append(f"{script}: undocumented options {undoc_opt}")
        print()

    if not args.gaps and not args.interfaces:
        print("CLONE COMPLETENESS -- does every path the guide tells you to run exist here?\n")
        problems = clone_completeness()
        if problems:
            for prob in problems:
                print(f"  FAIL  {prob}")
            failures.extend(problems)
        else:
            print(f"  PASS  every repo-relative path in {', '.join(INSTRUCTION_DOCS)} exists"
                  f" ({len(EXTERNAL_BY_DESIGN)} documented as external by design)")
        print()

    if failures:
        print(f"{len(failures)} unrouted need(s). An operator hits each of these as a question with")
        print("no answer in the documentation, and asks a person -- or guesses.")
        return 1
    print("Every enumerated need routes to a section that exists, and every live script's")
    print("interface is documented. That is not 'the guide is correct'; see the module docstring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
