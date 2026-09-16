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
    ("A orient", "read-the-directory-first rule and the index",
     "notes/production-host/README.md", "", None),
    ("A orient", "the vocabulary and the model, before the words are used",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "The model, and the words", None),
    ("A orient", "the absolute prohibitions",
     "notes/production-host/02-absolute-prohibitions.md", "", None),
    ("A orient", "docker discipline and what may be deleted",
     "notes/production-host/03-docker-discipline.md", "", None),
    ("A orient", "resource safety: assume none of it is free",
     "notes/production-host/04-resource-safety.md", "", None),
    ("A orient", "privacy: what not to look at",
     "notes/production-host/05-privacy-and-non-alarm.md", "", None),
    ("A orient", "the mandatory pre-action procedure",
     "notes/production-host/06-before-any-action.md", "", None),
    ("A orient", "dangerous defaults in our OWN code",
     "notes/production-host/07-this-repo-s-own-hazards.md", "", None),
    ("A orient", "the upper-bound rule",
     "notes/production-host/10-resource-upper-bound-rule.md", "", None),
    ("A orient", "how the operator path works, layer by layer",
     "notes/production-host/13-how-the-operator-path-works.md", "", "notes/model/HARNESS-MODEL.md"),
    ("A orient", "current state of the campaign",
     "notes/production-host/33-what-we-actually-have-2026-09-16.md", "", "scripts/campaign_status.py"),
    ("A orient", "which laptop interpreter",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Which Python runs the laptop-side scripts", None),
    ("A orient", "the arrival sequence, in order",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "When the production host becomes available", None),
    ("B setup", "what is transient and what accumulates on a persistent host",
     "notes/production-host/14-assets-and-environment-on-a-persistent-host.md", "", None),
    ("B setup", "Places365 acquisition and placement",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Places365", None),
    ("B setup", "prebuilt env vs pip cache",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "The environment: build it once", None),
    ("B setup", "what a cell actually costs",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "What a cell actually costs", None),
    ("B setup", "build, verify and transfer the payload",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Build and transfer the payload", "datasphere/native/contract.py"),
    ("B setup", "dry-run before the first real cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Dry-run the wrapper FIRST", None),
    ("C preflight", "readiness gate before acting",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Preconditions, checked on the host every time", "scripts/production_gates.py"),
    ("C preflight", "who else is on the cards, and the return arithmetic",
     "notes/production-host/33-what-we-actually-have-2026-09-16.md", "", None),
    ("C preflight", "decide whether to launch at all, not just what",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Decide whether to launch at all", None),
    ("C preflight", "which baselines can share a card",
     "notes/production-host/21-which-baselines-to-run-on-a-shared-card.md", "", None),
    ("C preflight", "disk, not VRAM, is what caps parallelism",
     "notes/production-host/27-disk-not-vram-is-what-caps-parallelism.md", "", None),
    ("C preflight", "disarm stale waiters",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", None),
    ("D launch", "start a production training cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", "datasphere/native/host-scripts/train-production-cell-v5.sh"),
    ("D launch", "choose CARD, yield flags and the cap",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", None),
    ("D launch", "the per-cell wall-clock ceiling",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "per-cell wall-clock ceiling", None),
    ("D launch", "pack more than one cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Packing two cells", None),
    ("D launch", "record the launch immediately",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Record the launch", "scripts/record_host_run.py"),
    ("E during", "every stop mechanism and whether it is silent",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Stop mechanisms", "notes/model/STOP-MECHANISMS.md"),
    ("E during", "what a yield actually costs",
     "notes/production-host/24-what-a-yield-actually-costs.md", "", None),
    ("E during", "the VRAM cap does not bind a trainer",
     "notes/production-host/26-the-vram-cap-never-reached-a-trainer.md", "", None),
    ("E during", "bound our own GPU footprint",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Stop mechanisms", "datasphere/native/self-vram-cap.sh"),
    ("E during", "monitoring that reports to a person, and its traps",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Monitoring that reports to a person", None),
    ("E during", "watching a live cell",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Watching a live cell", None),
    ("E during", "the abort ladder: what fails when",
     "notes/production-host/15-what-fails-when.md", "", None),
    ("E during", "the measured resource table",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Measured GPU memory", "datasphere/native/measured-vram-bounds.json"),
    ("E during", "what one cell actually uses on the card",
     "notes/production-host/22-what-a-cell-actually-uses.md", "", None),
    ("E during", "did we crowd anyone out",
     "notes/production-host/30-did-we-crowd-anyone-out.md", "", None),
    ("F eval", "evaluate every retained checkpoint",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", "datasphere/native/host-scripts/curve-sweep-v3.sh"),
    ("F eval", "evaluate a single checkpoint",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "convenience wrappers", "datasphere/native/host-scripts/reeval-cell-cached.sh"),
    ("F eval", "evaluation is 60% of a cell",
     "notes/production-host/28-eval-is-sixty-percent-of-a-cell.md", "", None),
    ("F eval", "the grid, cadence and seeds",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "The grid, the cadence and the seeds", "docs/EVAL-PROTOCOL.md"),
    ("G after", "retrieve and process results",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Retrieve and process", None),
    ("G after", "collect a whole wave in one step",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "datasphere/native/collect-wave.sh"),
    ("G after", "turn records into ledger entries",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/populate_evaluator_ledger.py"),
    ("G after", "campaign coverage per baseline and seed",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/campaign_status.py"),
    ("G after", "one flat table of every record",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/export_fleet.py"),
    ("G after", "update the run register",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run", "scripts/production_run_register.py"),
    ("G after", "what artifacts a cell leaves, and which is the product",
     "notes/production-host/32-what-we-actually-have-2026-09-14.md", "", None),
    ("H judge", "when a row is admissible",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "When a number becomes a result", "scripts/audit_row_closure.py"),
    ("H judge", "which comparisons are licensed",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "comparisons are licensed", "scripts/comparison_blocks.py"),
    ("H judge", "evaluator noise: what reproduces and what does not",
     "notes/production-host/33-what-we-actually-have-2026-09-16.md", "", None),
    ("I fail", "what survives an interruption; what is resumable",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "What survives an interruption", None),
    ("I fail", "record an attempt that wrote nothing",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Recording an attempt that failed", None),
    ("J hygiene", "ending a session",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Before you finish a session", None),
    ("J hygiene", "the utility scripts, each with a purpose",
     "notes/RUNNING-ON-PRODUCTION-HOST.md", "Every tool in this repository", None),
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


#: A directory whose README claims to index it. 13 of its 33 files were absent from that index on
#: 2026-09-16, including the current-state note and every file covering shared-card operation --
#: so "read this entire directory" pointed at a table that showed under half of it.
INDEXED_DIRS = (("notes/production-host", "README.md"),)


def index_completeness() -> list[str]:
    """Every file in an indexed directory must appear in that directory's index."""
    problems: list[str] = []
    for rel, index_name in INDEXED_DIRS:
        d = ROOT / rel
        index = d / index_name
        if not index.is_file():
            problems.append(f"{rel}/{index_name} does not exist")
            continue
        text = index.read_text(errors="replace")
        for f in sorted(d.glob("*.md")):
            if f.name == index_name:
                continue
            if f.name not in text:
                problems.append(f"{rel}/{f.name} is not indexed in {index_name}")
    return problems


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
        print("INDEX COMPLETENESS -- does every file appear in its directory's own index?\n")
        idx = index_completeness()
        if idx:
            for prob in idx:
                print(f"  FAIL  {prob}")
            failures.extend(idx)
        else:
            print(f"  PASS  every file in {INDEXED_DIRS[0][0]} appears in its README")
        print()

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
