#!/usr/bin/env python3
"""Recompute the mechanical facts a handoff must not state falsely.

    python scripts/state.py

## READ THIS FIRST: what this script is now about

**It reports on `rlgen/algos/`, which is the SUPERSEDED port, not the current deliverable.**
Since 2026-08-17 the project's null is the original repository cloned and running its own
`train.py` (`docs/RUNNABLE-ORIGINALS.md`), and the ledger for that is
`python scripts/deviations.py`. Nothing below measures the twelve runnable baselines.

That is not a reason to delete this file. `rlgen/` still exists, its provenance facts are still
true, and the reason the approach changed is legible only if the thing it replaced stays
measurable. But anyone reading this output as "the state of the project" is reading the wrong
report, which is exactly the staleness this script was written to prevent -- so it says so here
and in its own first line of output.

## What this is for

On 2026-08-16 a handoff block and an inventory table both recorded a baseline's base term as a
"clean, remote-verified" tree. The remote *was* verified. The working tree was dirty and its
`agents/ppo.py` raised `SyntaxError`. Both claims were written the same day they were found wrong
(`git log -S`), so nothing went stale — the sweep that produced them checked `git remote -v` and
never opened the tree. This script exists so that specific half of a handoff is **recomputed
rather than remembered**.

## What this is NOT for, stated because the boundary is the whole point

**This cannot carry the unknown unknowns, and most of what has actually mattered was one.** A
generator only checks what its author already knew to check, so this script is a floor, never a
status report. It cannot tell you:

  - that a third party's re-derivation was about to be used as a reference while the authors' own
    code sat unread in the same repo;
  - that a value chosen for cross-baseline uniformity silently disabled half of one algorithm's
    mechanism;
  - that a cited reference is not on this disk at all;
  - what was decided, why, or which claim to distrust first.

Those came from reading, and from someone asking a question this script does not contain. The
prose handoff in `docs/STEP-ZERO.md` carries them and is not replaceable by tooling. If this
script ever seems sufficient, that is the failure mode it was built to make visible, not evidence
that it is.

## The limit that bit hardest

**This searches only the references listed in `BASELINES` below, so a 0% means "does not descend
from what I listed" — never "does not descend from anything."** `idaac` read 0% here for exactly
that reason and was queued for a base-first rebuild on the strength of it; `scripts/authorship.py`,
which searches every reference on disk, shows it descending 83-100% from a sibling project's port.
A curated list is a hypothesis about where code came from, and it fails silently when the
hypothesis is wrong. Use `authorship.py` when the question is "where did this come from"; use this
when the question is "does it still match what we believe".

## Reading the descent column

Textual descent is a **flag, not a verdict**. `ctrl` reads 0% because its reference is JAX/Flax
and the crossing is declared; `rad.py` reads 0% because it is a thin wrapper whose substance lives
in `sac.py` (93%). A low number says where to look. Whether it means anything is a judgement about
frameworks, wrappers and layout that belongs to a person.
"""
from __future__ import annotations

import ast
import difflib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (baseline, module path relative to ROOT, reference dirs to search, note)
BASELINES = [
    ("ibac_sni", "rlgen/algos/ibac_sni",
     ["rlgen/algos/ibac_sni/_upstream_1678e4a"], "base vendored in-tree"),
    ("ppg", "rlgen/algos/ppg", ["ext/phasic-policy-gradient"], ""),
    # BOTH hops. Listing only ext/idaac made this row read 0%, which was taken as "descends
    # from nothing" and used to queue a base-first rebuild. It actually descends 83-100% from a
    # SIBLING PROJECT's port -- the alda situation. A curated reference list reports "not the
    # thing I listed", never "nothing"; see scripts/authorship.py, which searches everything.
    ("idaac", "rlgen/algos/idaac",
     ["ext/idaac", "../gen-rebuttal/vigen-idaac/vigen_idaac"], "two-hop; ref has no cont. head"),
    ("ctrl", "rlgen/algos/ctrl", ["ext/ctrl_public"], "JAX/Flax crossing declared"),
    ("alda", "rlgen/algos/alda",
     ["ext/ALDA_Official", "../gen-rebuttal/vigen-idaac/vigen_alda"], "two-hop"),
    ("rad", "rlgen/algos/rad.py", ["ext/rad"], "thin wrapper over sac.py"),
    ("soda", "rlgen/algos/soda.py",
     ["ext/dmcontrol-generalization-benchmark"], ""),
    ("sac(shared)", "rlgen/algos/sac.py",
     ["ext/dmcontrol-generalization-benchmark"], "under rad + soda"),
]


def sh(cmd: str, cwd: pathlib.Path) -> str:
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True).stdout


def code_lines(p: pathlib.Path) -> list[str]:
    """Code only: no blank lines, no comments, module docstring stripped."""
    try:
        src = p.read_text(errors="replace")
    except OSError:
        return []
    src = re.sub(r'^\s*"""(?:.|\n)*?"""\n', "", src, count=1)
    return [l.rstrip() for l in src.splitlines()
            if l.strip() and not l.strip().startswith("#")]


def recon(refdir: pathlib.Path) -> str:
    """The check that was missing: open the tree, do not just identify it."""
    if not refdir.exists():
        return "ABSENT"
    if not (refdir / ".git").exists():
        bad = sum(1 for f in refdir.rglob("*.py") if not parses(f))
        return f"no-git, {bad} parse-fail" if bad else "no-git, parses"
    st = sh("git status --porcelain", refdir).splitlines()
    dirty = [l for l in st if not l.startswith("??") and not l.endswith(".DS_Store")]
    commit = sh("git log -1 --format=%h", refdir).strip()
    bad = [f for f in refdir.rglob("*.py") if ".git" not in f.parts and not parses(f)]
    flags = []
    if dirty:
        flags.append(f"DIRTY({len(dirty)})")
    if bad:
        flags.append(f"PARSE-FAIL({len(bad)})")
    return f"@{commit} " + (" ".join(flags) if flags else "clean")


def parses(f: pathlib.Path) -> bool:
    try:
        ast.parse(f.read_text(errors="replace"))
        return True
    except SyntaxError:
        return False
    except OSError:
        return True


def descent(module: pathlib.Path, refdirs: list[pathlib.Path]) -> str:
    ours = [module] if module.suffix == ".py" else sorted(module.glob("*.py"))
    reffiles: list[pathlib.Path] = []
    for rd in refdirs:
        if rd.exists():
            reffiles += [f for f in rd.rglob("*.py") if ".git" not in f.parts]
    pcts, winners = [], set()
    for o in ours:
        if o.name == "__init__.py":
            continue
        ol = code_lines(o)
        if not ol:
            continue
        best, best_src = 0.0, None
        for r in reffiles:
            rl = code_lines(r)
            if not rl:
                continue
            sm = difflib.SequenceMatcher(None, rl, ol, autojunk=False)
            if sm.quick_ratio() < 0.15:
                continue
            kept = sum(b.size for b in sm.get_matching_blocks())
            pct = 100 * kept / len(rl)
            if pct > best:
                best, best_src = pct, r
        pcts.append(best)
        if best_src is not None and best > 25:
            winners.add(_which_ref(best_src, refdirs))
    if not pcts:
        return "-"
    s = "/".join(f"{p:.0f}" for p in sorted(pcts, reverse=True)) + "%"
    # WHICH reference matched is as load-bearing as how much. `alda` scores ~100% against
    # a SIBLING PROJECT'S port and 0% against the authors' own repo; printing only the
    # number makes a two-hop construction look like a clean transcription. This is the
    # single most misleading thing this script could have done, so it names the source.
    if winners:
        s += " <" + ",".join(sorted(winners)) + ">"
    return s


def _which_ref(matched: pathlib.Path, refdirs: list[pathlib.Path]) -> str:
    for rd in refdirs:
        try:
            matched.relative_to(rd)
            return rd.name
        except ValueError:
            continue
    return "?"


def main() -> int:
    print("SCOPE: rlgen/algos/ -- the SUPERSEDED port. The current deliverable is the cloned")
    print("       originals; run `python scripts/deviations.py` for that. See this file's")
    print("       docstring and docs/RUNNABLE-ORIGINALS.md.\n")
    print(f"repo: {ROOT}")
    head = sh("git log -1 --format='%h %s'", ROOT).strip()
    print(f"branch: {sh('git branch --show-current', ROOT).strip()}  head: {head[:60]}")
    # Compare main by CONTENT, not by commit count. This branch has historically been
    # synced to main by cherry-pick, which gives the same content different SHAs -- so
    # `rev-list --count` reports a large divergence that is pure bookkeeping. Reporting
    # that as "DIVERGED" would raise a false alarm on every run, and a monitor that cries
    # wolf is worse than no monitor.
    ahead = sh("git rev-list --count main..HEAD", ROOT).strip() or "?"
    differing = [f for f in sh("git diff main HEAD --name-only", ROOT).splitlines() if f]
    if not differing:
        verdict = "content identical"
    else:
        verdict = f"CONTENT DIFFERS in {len(differing)} file(s): " + ", ".join(differing[:3])
        if len(differing) > 3:
            verdict += f", +{len(differing) - 3} more"
    print(f"vs main: {ahead} commits ahead (SHAs differ by cherry-pick) -- {verdict}")
    print()
    print(f'{"baseline":<13}{"base term (tree opened)":<26}{"descent":<34}note')
    print("-" * 88)
    for name, mod, refs, note in BASELINES:
        m = ROOT / mod
        rds = [(ROOT / r).resolve() for r in refs]
        states = " ".join(recon(rd) for rd in rds)
        d = descent(m, rds) if m.exists() else "MODULE ABSENT"
        flag = ""
        first = d.split("/")[0].rstrip("%")
        if first.replace(".", "").isdigit() and float(first) < 25 and not note:
            flag = "  <-- 0% and unexplained: look"
        print(f"{name:<13}{states[:25]:<26}{d:<34}{note}{flag}")
    print()
    print("descent = best textual match of each module file against any reference file, "
          "high-to-low.")
    print("A flag, not a verdict -- read this file's docstring before concluding anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
