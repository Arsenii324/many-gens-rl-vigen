#!/usr/bin/env python3
"""Is a record's `frame` corroborated by the checkpoint it was computed from?

    python scripts/audit_record_frame_provenance.py <run-dir-or-records.jsonl> [--strict]

## The hole this closes

The evaluator-revision machinery proves **code identity** -- that the tree which produced a row still
exists. Nothing proves **label correctness**: that a row's `frame` is the frame of the checkpoint it
measured. Labels are set by shell plumbing, and shell plumbing is where every defect of 2026-09-09
lived. One of them, `ppg_checkpoint_frame`'s reconstruction fallback, would have attached correct
measurements to frames off by one save and on the wrong cadence -- and **nothing downstream could
have detected it**, because `frame=200000` for a checkpoint at 200704 is not implausible, not
malformed, and not checkable after the fact.

## Why a check is possible at all

Two independent producers write the frame:

  * the **trainer** names the checkpoint file, and six families stamp the frame into that name
    (`agent-robosuite:Door-idaac-s101_100352.pt`);
  * **`eval_grid.py`** writes `frame` into the record, from a value the runner passed it.

They share no code path. If they agree, the label is corroborated by construction. If they disagree,
one of them is wrong and the record is not usable.

`checkpoint_sha256` is what ties a record to a file, so the comparison needs no filename bookkeeping:
hash the checkpoints, match, then read the frame out of the matched name.

## What it deliberately will not do

`ppg` names by **save index** (`model004.jd`), so its frames come from `IC=` lines in its training
log and there is no second producer. Those rows are reported **UNVERIFIABLE**, never OK. A record
whose corroboration is impossible and a record that was corroborated must not print the same, which
is the whole reason the earlier fallback survived three days.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

FRAME_IN_NAME = re.compile(r"_(\d+)\.(?:pt|pth|jd|tar)$")


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _checkpoints(root: pathlib.Path) -> dict[str, pathlib.Path]:
    out: dict[str, pathlib.Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in (".pt", ".pth", ".jd", ".tar"):
            try:
                out[_sha256(path)] = path
            except OSError:
                continue
    return out


def _records(target: pathlib.Path) -> list[dict]:
    files = [target] if target.is_file() else sorted(target.rglob("*.jsonl"))
    rows = []
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="a run directory, or a records .jsonl")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any MISMATCH (UNVERIFIABLE alone never fails)")
    args = ap.parse_args()

    target = pathlib.Path(args.target)
    if not target.exists():
        print(f"no such path: {target}")
        return 2

    root = target if target.is_dir() else target.parent
    rows = _records(target)
    if not rows:
        print("no records found. Nothing was checked, which is NOT the same as nothing being wrong.")
        return 2

    by_hash = _checkpoints(root)
    corroborated = mismatched = unverifiable = 0
    problems: list[str] = []

    for r in rows:
        sha = r.get("checkpoint_sha256")
        frame = r.get("frame")
        baseline = r.get("baseline", "?")
        if not sha or frame is None:
            unverifiable += 1
            continue
        path = by_hash.get(sha)
        if path is None:
            unverifiable += 1
            continue
        m = FRAME_IN_NAME.search(path.name)
        if not m:
            # ppg and anything else naming by save index: no second producer exists.
            unverifiable += 1
            continue
        named = int(m.group(1))
        if named == int(float(frame)):
            corroborated += 1
        else:
            mismatched += 1
            problems.append(f"    {baseline} {r.get('regime','?'):<11} record frame={frame} "
                            f"but the checkpoint it measured is named {named} ({path.name})")

    total = len(rows)
    print(f"RECORD FRAME PROVENANCE -- {total} record(s) under {target}\n")
    print(f"  corroborated  {corroborated:>5}   the trainer's filename and the record agree")
    print(f"  MISMATCHED    {mismatched:>5}   two independent producers disagree")
    print(f"  unverifiable  {unverifiable:>5}   no second producer exists for these rows")
    if problems:
        print("\n  Disagreements:")
        for p in problems[:20]:
            print(p)
    if unverifiable:
        print("\n  UNVERIFIABLE IS NOT OK. It means the label rests on one producer -- typically ppg,")
        print("  which names checkpoints by save index, so its frames come from IC= log lines with")
        print("  nothing to check them against. Read those rows as uncorroborated, not as clean.")
    if mismatched:
        print("\n  A mismatch means a real measurement is attached to the wrong frame. The record is")
        print("  well-formed and plausible, which is exactly why nothing else would catch it.")
    return 1 if (mismatched and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
