#!/usr/bin/env python3
"""Do the notes still cite what they claim? Checks every `path:line` a note asserts.

    python scripts/verify_note_citations.py                    # all notes
    python scripts/verify_note_citations.py notes/foo.md       # one
    python scripts/verify_note_citations.py --strict            # exit 1 on drift

## The problem this exists for

This project's value is in its conditionals, and a conditional is only as good as the code it points
at. A note that says

    `minibatch_optimize` splits the LEADING axis (`minibatch_optimize.py:53`)

is true until someone edits that file, and then it is a confident false statement with a citation --
which is worse than no citation, because the citation is what makes a reader stop checking.

Nothing detected that. `where_is_this_decided.py` finds WHERE a topic is discussed;
`refresh_clone_patches.py` keeps vendored trees reproducible; `test_docs_not_stale.py` checks a
handful of hardcoded claims. None of them asks the general question: **does every line this note
points at still exist, and does it still say what the note says it says?**

## What it checks, and what it deliberately does not

For each `path:line` reference in a note:

1. **The file exists.** A note citing a deleted file is stale by construction.
2. **The line exists.** A citation past the end of a file is stale.
3. **If the note quotes an identifier in backticks within two lines of the citation, that
   identifier still appears within +/- `--window` lines of the cited line.** Code moves; a citation
   that has drifted twenty lines is usually fine and a citation whose subject has vanished is not.

It does **not** check that the note's *reasoning* is right. That is not automatable and pretending
otherwise would be the same overclaim this file exists to catch. It checks that the evidence a
reader would follow still leads where the note says.

## Why line-anchored rather than content-anchored

A content-only check ("does this string appear anywhere in the repo") passes when the code moved to
a different file with different meaning -- which is precisely how the `ppg` nminibatch confusion
survived: `nminibatch` appears in the retired `rlgen/algos/ppg/_upstream_7295473/` port AND in the
live `runnable/ppg/`, and a search that did not distinguish them would have confirmed either story.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: `path/to/file.ext:123`, optionally inside backticks. Requires a real-looking extension so prose
#: like "12:30" or "A25:3" does not match.
CITATION = re.compile(
    r"`?((?:[A-Za-z0-9_./-]+/)*[A-Za-z0-9_.-]+\.(?:py|sh|json|yaml|yml|md|txt))"
    r":(\d+)(?:-\d+)?`?"
)
IDENTIFIER = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{2,})`")


def check_note(note: pathlib.Path, window: int) -> list[str]:
    problems: list[str] = []
    lines = note.read_text(errors="replace").splitlines()
    for index, line in enumerate(lines):
        for match in CITATION.finditer(line):
            rel, number = match.group(1), int(match.group(2))
            target = ROOT / rel
            if not target.is_file():
                # A BARE BASENAME is the common case in prose (`ppo.py:130`). Resolve it, and treat
                # an ambiguous one as a finding rather than picking a winner: `nminibatch` lives in
                # BOTH the live `runnable/ppg/` and the retired `rlgen/algos/ppg/_upstream_*` port,
                # and a citation that cannot say which is exactly how a stale story survives.
                if "/" not in rel:
                    matches = [m for m in ROOT.rglob(rel)
                               if ".git" not in m.parts and "__pycache__" not in m.parts]
                    if len(matches) == 1:
                        target = matches[0]
                    elif len(matches) > 1:
                        shown = ", ".join(str(m.relative_to(ROOT)) for m in matches[:3])
                        problems.append(
                            f"{note.name}:{index + 1}  cites bare {rel}:{number}, AMBIGUOUS across "
                            f"{len(matches)} files ({shown}) -- qualify the path")
                        continue
                    else:
                        problems.append(
                            f"{note.name}:{index + 1}  cites {rel}:{number} -- FILE MISSING")
                        continue
                else:
                    problems.append(f"{note.name}:{index + 1}  cites {rel}:{number} -- FILE MISSING")
                    continue
            try:
                body = target.read_text(errors="replace").splitlines()
            except Exception as error:                       # noqa: BLE001
                problems.append(f"{note.name}:{index + 1}  {rel}: unreadable ({error})")
                continue
            if number > len(body):
                problems.append(
                    f"{note.name}:{index + 1}  cites {rel}:{number} but the file has "
                    f"{len(body)} lines -- PAST END")
                continue
            context = " ".join(lines[max(0, index - 1):index + 2])
            wanted = [name for name in IDENTIFIER.findall(context)
                      if not name.endswith((".py", ".sh", ".json", ".md", ".yaml", ".txt"))]
            if not wanted:
                continue
            lo, hi = max(0, number - 1 - window), min(len(body), number + window)
            near = "\n".join(body[lo:hi])
            missing = [name for name in wanted if name.split(".")[-1] not in near]
            # Report only when EVERY named identifier is absent: a note usually names several and
            # some belong to the prose rather than to the cited line.
            if missing and len(missing) == len(wanted):
                problems.append(
                    f"{note.name}:{index + 1}  cites {rel}:{number} but none of "
                    f"{missing[:3]} appears within +/-{window} lines")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--window", type=int, default=25)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    notes = ([pathlib.Path(p) for p in args.paths] if args.paths
             else sorted((ROOT / "notes").rglob("*.md")))
    total = 0
    checked = 0
    for note in notes:
        if not note.is_file():
            print(f"no such note: {note}", file=sys.stderr)
            continue
        checked += 1
        problems = check_note(note, args.window)
        total += len(problems)
        for problem in problems:
            print(f"  {problem}")

    print(f"\n{checked} note(s) checked, {total} stale citation(s).")
    if not total:
        print("  Every path:line a note points at still exists and still names what the note names.")
        print("  This does NOT check that the reasoning is right -- only that the evidence a reader")
        print("  would follow still leads where the note says it does.")
    return 1 if (total and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
