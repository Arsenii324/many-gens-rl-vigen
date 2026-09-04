#!/usr/bin/env python3
"""Are the runs in `logs/` actually comparable, and does each say where it came from?

    python tools/verify_run_provenance.py            # checks ./logs
    python tools/verify_run_provenance.py <dir>

Four properties, each of which has been violated in this repo at least once:

1. **One protocol hash across all runs.** Anything else and the numbers cannot sit in one table.
   This is the property the hash exists to make checkable rather than assumed.

2. **One `code_commit` per run file.** `episodes.csv` used to be opened in append mode, and run
   directories are keyed by (task, baseline, mode-seed), so re-running a baseline concatenated a
   second run into the first with nothing marking the boundary. Observed: one baseline holding two
   runs at different commits, another holding six runs' worth of rows at frame 0 against three at
   later eval points -- so a per-point mean averaged a different number of runs at different x.

3. **No `-dirty` provenance.** `git_commit()` derives that flag from `git status --porcelain`,
   which lists UNTRACKED files, so a stray scratch file anywhere in the tree silently degrades the
   provenance of every run made while it existed. For a `-dirty` run the exact tree state is not
   recoverable from the record.

4. **Uniform episode counts per eval point**, per mode. An asymmetry here is the visible symptom
   of (2), and it is what makes a mean quietly wrong rather than loudly missing.

Exit code is non-zero if any property fails, so this can gate a results table.
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import os
import sys


def main() -> int:
    # argparse rather than sys.argv[1], so `--help` is help and not a directory named "--help".
    # It was the latter, which is a small thing that makes a tool feel broken on first contact.
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="logs",
                    help="directory to search for episodes.csv (default: logs)")
    root = ap.parse_args().root
    paths = sorted(glob.glob(os.path.join(root, "**", "episodes.csv"), recursive=True))
    if not paths:
        print(f"FATAL: no episodes.csv under {root!r}. A verifier that checks nothing must not "
              f"report success.", file=sys.stderr)
        return 2

    hashes: set[str] = set()
    commits: set[str] = set()
    problems: list[str] = []

    # Column labels deliberately avoid the `prefix/name` shape: `tests/test_eval_identity.py::
    # test_no_tag_literals_outside_tags_module` scans for it, and "eval/pt" as a header string was
    # flagged as a stray logging key. The guard is right to be that blunt -- rename the label.
    print(f"{'run':38s} {'rows':>5s} {'pts':>4s} {'eval_ep':>9s} {'train_ep':>9s}  commit")
    print("-" * 92)
    for p in paths:
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        name = os.path.relpath(os.path.dirname(p), root)
        if not rows:
            problems.append(f"{name}: no rows")
            continue
        cm = {r["code_commit"] for r in rows}
        hashes |= {r["protocol_hash"] for r in rows}
        commits |= cm
        per = collections.Counter((r["frames"], r["mode"]) for r in rows)
        ev = {v for k, v in per.items() if k[1] != "train"}
        tr = {v for k, v in per.items() if k[1] == "train"}
        pts = len({k[0] for k in per})
        print(f"{name:38s} {len(rows):5d} {pts:4d} {str(sorted(ev)):>9s} {str(sorted(tr)):>9s}  "
              f"{','.join(sorted(cm))}")
        if len(cm) != 1:
            problems.append(f"{name}: {len(cm)} code_commits in one file {sorted(cm)} -- this is "
                            f"two or more runs concatenated")
        if any("dirty" in c for c in cm):
            problems.append(f"{name}: provenance is -dirty, so the tree state is unrecoverable")
        if len(ev) > 1 or len(tr) > 1:
            problems.append(f"{name}: uneven episode counts across eval points "
                            f"(eval={sorted(ev)}, train={sorted(tr)})")

    print(f"\nprotocol hashes : {sorted(hashes)}")
    print(f"code commits    : {sorted(commits)}")
    if len(hashes) > 1:
        problems.append(f"{len(hashes)} distinct protocol hashes -- these runs are NOT comparable "
                        f"and must not share a table")
    if len(commits) > 1:
        print(f"\nNOTE: {len(commits)} distinct commits across runs. `code_commit` is excluded "
              f"from the protocol hash, so this does not break comparability -- but confirm the "
              f"differences are not in code:\n"
              f"    git diff --name-only {sorted(commits)[0]}..{sorted(commits)[-1]} "
              f"| grep -E '^(rlgen/|train\\.py|configs/|baselines/)'")

    if problems:
        print("\nPROBLEMS:")
        for x in problems:
            print(f"  - {x}")
        return 1
    print("\nOK: one protocol hash, one commit per run, no -dirty provenance, uniform counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
