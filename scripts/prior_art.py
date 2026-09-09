#!/usr/bin/env python3
"""Before you commit that note: what does the repo already say about the things in it?

    python scripts/prior_art.py notes/my-new-finding.md
    python scripts/prior_art.py notes/*.md --min-hits 3

## Why this exists

On 2026-09-09 I nearly published, as new, three things the codebase already documented — twice
better than I was about to:

* the `eval-hard` / `eval-medium` inversion, already stated in `rlgen/protocol.py:30-35`;
* "no durable second location exists on this host", already argued in
  `run_on_production_host.sh:405-437`, including the second-copy versus second-failure-domain
  distinction I thought I was drawing;
* a plan item I called unimplemented that `families.json` already covered.

`scripts/where_is_this_decided.py` would have found all three. The gap was never the tool — it was
that checking requires knowing *which* claim to check, and a claim I do not know is contested is
exactly the one I will not look up. **An agent writing from its own context cannot check breadth.**

So this inverts the ergonomics. Instead of remembering to search per claim, run one command on the
artifact you just wrote and let it tell you which of its terms already have a history.

## What it is NOT

**Not a gate.** It prints; nothing fails. A regex that flags absence-phrases was measured first and
rejected: 25 such lines exist across 15 notes and most are legitimate prose ("there is nothing to
check", "an unexercised guard is a claim nobody checked"). Enforcing that would tax honest writing
and teach me to phrase around it rather than to look.

**Not semantic.** It matches identifiers, so it finds a term that has been discussed, not an idea
that has been discussed. A finding phrased entirely in new words will pass clean and still be
old news. It narrows the blind spot; it does not close it.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Identifiers worth looking up: backticked symbols, dotted filenames, CONSTANT_CASE, snake_case
#: with an underscore. Bare English words are excluded deliberately -- "return" or "policy" would
#: match every file and drown the signal.
TERM = re.compile(r"""
    `([A-Za-z_][A-Za-z0-9_./-]{3,})`          # `something_like_this`
  | \b([A-Z][A-Z0-9_]{4,})\b                   # NATIVE_RESULT_MIRROR
  | \b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b        # eval_policy_mode
  | \b([a-z][a-z0-9-]*\.(?:py|sh|json|ya?ml))\b  # families.json
""", re.VERBOSE)

#: Words that match the shapes above but are too common to be evidence of anything.
NOISE = {"can_be", "is_not", "does_not", "such_as", "as_well", "in_the", "of_the", "to_the",
         "for_the", "and_the", "that_is", "it_is", "there_is", "note_that", "so_that"}


def _search():
    spec = importlib.util.spec_from_file_location(
        "_where_is_this_decided", ROOT / "scripts" / "where_is_this_decided.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


def terms_in(path: pathlib.Path) -> list[str]:
    text = path.read_text(errors="replace")
    found: dict[str, int] = {}
    for match in TERM.finditer(text):
        term = next(g for g in match.groups() if g)
        if term.lower() in NOISE or len(term) < 5:
            continue
        found[term] = found.get(term, 0) + 1
    return sorted(found, key=lambda t: (-found[t], t))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--min-hits", type=int, default=2,
                    help="only report a term with at least this many prior mentions elsewhere")
    ap.add_argument("--max-terms", type=int, default=40)
    args = ap.parse_args()

    search = _search()
    for raw in args.paths:
        path = pathlib.Path(raw)
        if not path.is_file():
            print(f"no such file: {path}")
            continue
        rel = path.resolve().relative_to(ROOT) if str(path.resolve()).startswith(str(ROOT)) else path
        terms = terms_in(path)[:args.max_terms]
        print(f"PRIOR ART FOR {rel}  ({len(terms)} distinctive term(s) examined)\n")

        reported = 0
        for term in terms:
            # [Claude 2026-09-09] NOT a blanket `except Exception: continue`. The first version had
            # one, and it swallowed an AttributeError on every single term -- the script printed a
            # header and nothing else, and looked like a clean "no prior art" result. That is the
            # failure this project refuses everywhere else: an instrument that could not run must
            # never read as one that ran. Only a genuinely missing term is tolerated here.
            hits = [h for h in search(term)
                    if (ROOT / h["path"]).resolve() != path.resolve()]
            if len(hits) < args.min_hits:
                continue
            reported += 1
            # [Claude 2026-09-09] CODE FIRST, and this ordering is the whole point. The first
            # version showed the newest hits overall, which for a heavily-discussed term is a wall
            # of my own notes: `eval-medium` returned 90 mentions led by notes I had just written,
            # and NOT `rlgen/protocol.py:30-35`, the code comment that actually explains why the
            # regimes are not rank-ordered. In all three misses this file exists for, the authority
            # was a comment or a refusal message in CODE and the notes were restatements of it.
            code = [h for h in hits if not str(h["path"]).startswith(("notes/", "docs/"))]
            prose = [h for h in hits if str(h["path"]).startswith(("notes/", "docs/"))]
            print(f"  {term}  — {len(hits)} prior mention(s) elsewhere "
                  f"({len(code)} in code, {len(prose)} in prose)")
            for label, group, n in (("code ", code, 2), ("prose", prose, 1)):
                for h in group[:n]:
                    marker = ("  [supersession marker]"
                              if str(h.get("marked", "")).lower() == "true" else "")
                    print(f"      {label}  {h.get('date','?')}  "
                          f"{h['path']}:{h.get('line','?')}{marker}")
        if not reported:
            print("  No term in this file has prior treatment elsewhere. That is WEAK evidence of")
            print("  novelty, not proof: this matches identifiers, so a finding phrased in new")
            print("  words reads clean and may still be old news.\n")
        else:
            print(f"\n  {reported} term(s) have a history. Read the newest hit and anything carrying")
            print("  a supersession marker BEFORE claiming this is new or that nothing covers it.")
            print("  Read the CODE hits first: a comment or a refusal message is usually the rule,")
            print("  and the prose hits are usually restatements of it.")
            print("  Where the repo already treats it, the valuable output is smaller: cite the")
            print("  existing treatment and add only the new data point.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
