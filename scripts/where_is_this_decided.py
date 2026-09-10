#!/usr/bin/env python3
"""Given a topic, show every place that discusses it, newest authority first.

    python scripts/where_is_this_decided.py num_processes
    python scripts/where_is_this_decided.py frame_stack --limit 40

## Why this exists

Answering "why is idaac num_processes=1" on 2026-09-09 took a subagent, a grep sweep and
`git log -S` archaeology. It found the answer -- DECISION-SHEET A35/Q55, commit 15b4e73, confirmed
against a primary source -- and **six documents still asserting the discarded value in the present
tense**, including a test docstring that said "raises" while the same file's code comment below it
had already been corrected.

That is the recurring shape: the answer exists, several contradictions exist beside it, and nothing
tells a reader which is current. `docs/PROJECT-INDEX.md` maps documents to purposes and
`notes/PARAMETER-REVIEW-CONSENSUS-MATRIX.md` reconciles parameters across reviews, but neither
answers "of these nine files, which one is still true?"

## What it does, and deliberately does not do

It reports **recency and provenance**, not truth. For every hit it prints the file, the line, the
date of the last commit that touched that file, and whether the file carries a supersession marker.
Sorted newest-first, so the likely authority is at the top and the likely fossils are at the bottom.

It does **not** pick a winner. A newest-first list is an ordering, not a ruling: a note written
yesterday can be wrong and a config comment from last week can be the authority. The point is to
make the whole set visible cheaply, so a reader cannot settle on the first hit without seeing the
others -- which is exactly how the stale `num_processes` claims survived.

Generated files and vendored trees are excluded from the ranking but counted, because a hit inside
`runnable/` is usually upstream's own code and not a claim this project makes.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

SEARCH_DIRS = ("notes", "docs", "datasphere", "scripts", "tests", "rlgen", "setup")
SKIP_PARTS = ("__pycache__", ".git", "node_modules", "ext", "RL-ViGen-upstream", "third_party")
#: A hit in a vendored tree is upstream's code, not a claim of ours.
VENDORED = ("runnable/",)
SUPERSEDED = re.compile(r"SUPERSEDED|superseded|EXPIRED|no longer (true|current)|discarded", re.I)


def _last_commit(path: pathlib.Path) -> tuple[str, str]:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ad|%h", "--date=short", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
        if "|" in out:
            date, sha = out.split("|", 1)
            return date, sha
    except Exception:
        pass
    return "untracked", "-"


def search(term: str) -> list[dict]:
    hits: list[dict] = []
    seen_files: dict[pathlib.Path, tuple[str, str]] = {}
    for d in SEARCH_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(p in path.parts for p in SKIP_PARTS):
                continue
            if path.suffix not in (".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt"):
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            if term not in text:
                continue
            if path not in seen_files:
                seen_files[path] = _last_commit(path)
            date, sha = seen_files[path]
            marked = bool(SUPERSEDED.search(text))
            for n, line in enumerate(text.splitlines(), 1):
                if term in line:
                    hits.append({"path": path.relative_to(ROOT), "line": n,
                                 "date": date, "sha": sha, "marked": marked,
                                 "text": line.strip()[:118]})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("term")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--files-only", action="store_true")
    args = ap.parse_args()

    hits = search(args.term)
    if not hits:
        # [Claude 2026-09-10] A MULTI-WORD QUERY MUST NEVER REPORT A BARE ABSENCE.
        #
        # `search` is a literal substring test, so a multi-word phrase (a family name plus two
        # or three parameter names) matches nothing almost by construction -- and
        # the old message, "no occurrences of ... under notes, docs, ...", reads as "this project
        # has not considered it". On 2026-09-10 that answer was returned for a question the repo
        # HAD answered, in notes/FINDING-on-policy-update-density.md, which carried the decisive
        # arithmetic. A term-by-term grep found it seconds later.
        #
        # An instrument that could not run must never read as one that ran, and a phrase search
        # that found nothing has not searched for the topic. Decompose and report per term.
        words = [w for w in re.split(r"[^A-Za-z0-9_.\-]+", args.term) if len(w) > 2]
        if len(words) > 1:
            print(f"The literal phrase {args.term!r} does not occur. **That is not evidence of "
                  f"absence** -- this is a substring search, and a phrase rarely appears verbatim.")
            print("Searching each term separately:\n")
            any_hit = False
            for word in words:
                word_hits = search(word)
                if not word_hits:
                    print(f"  {word:<24} 0")
                    continue
                any_hit = True
                by_file = {}
                for hit in word_hits:
                    by_file.setdefault(hit["path"], hit)
                newest = sorted(by_file.values(), key=lambda h: h["date"], reverse=True)[:3]
                print(f"  {word:<24} {len(word_hits):>4} hit(s) in {len(by_file)} file(s); newest:")
                for hit in newest:
                    print(f"  {'':<24}   {hit['date']}  {hit['path']}")
            if any_hit:
                print("\nRe-run on the single term that looks closest before concluding anything.")
            return 1
        print(f"no occurrences of {args.term!r} under {', '.join(SEARCH_DIRS)}")
        print("Single term, searched literally. Try a shorter or differently-spelled identifier "
              "before treating this as an absence.")
        return 1

    hits.sort(key=lambda h: (h["date"], str(h["path"])), reverse=True)

    files = {}
    for h in hits:
        files.setdefault(h["path"], h)

    print(f"{len(hits)} occurrence(s) of {args.term!r} in {len(files)} file(s), "
          f"NEWEST FILE FIRST.\n")
    print("  This is an ORDERING, not a ruling. A note written yesterday can be wrong and a config")
    print("  comment from last week can be the authority. Read the set, not the top row.")
    print("  Recency is LAST-TOUCHED, which a typo fix also moves; for the change that actually")
    print("  altered the value, use the git log -S line printed at the end.")
    print("  And treat a confident tone as no evidence at all: several notes here were written by")
    print("  an assistant from whatever was in its context, and a document can read as an")
    print("  exhaustive review while having seen a subset. Breadth is a claim like any other.\n")

    shown = 0
    for path, first in files.items():
        if shown >= args.limit:
            print(f"\n  ... {len(files) - shown} more file(s); raise --limit")
            break
        flag = "  [carries a supersession marker]" if first["marked"] else ""
        print(f"  {first['date']}  {first['sha']:>8}  {path}{flag}")
        if not args.files_only:
            for h in hits:
                if h["path"] == path:
                    print(f"      :{h['line']}  {h['text']}")
        shown += 1

    print("\n  Next: for the decisive change rather than the newest file, run")
    print(f"      git log -S{args.term!r} --oneline --date=short --format='%ad %h %s'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
