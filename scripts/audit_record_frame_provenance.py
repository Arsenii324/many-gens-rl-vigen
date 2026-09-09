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

## Three grades, because two of them would be a lie

The strength of the evidence differs by family, and collapsing that difference is the failure this
file exists to prevent.

**CORROBORATED** -- two producers that share no code path agree. The **trainer** names the checkpoint
file and stamps the frame into that name (`agent-robosuite:Door-idaac-s101_100352.pt`); **`eval_grid.py`**
writes `frame` into the record from a value the runner passed it. Agreement here is real
corroboration: for the record to be wrong, two unrelated pieces of code must be wrong the same way.

**TIED** -- `ppg` names by save index (`model008.jd`), so no frame is in the filename. Its training
log carries `Saving to /tmp/native-work/runs/ppg-s1/model008.jd IC=401408`, which names the file and
the frame together, and that is what `ppg_checkpoint_frame` reads. So the record's frame is
**derived from** that line rather than independent of it, and calling the agreement "corroboration"
would manufacture confidence out of a single producer.

What it does establish is narrower and is exactly the defect that was live: **the frame in the record
belongs to the specific file the record measured**, tied through `checkpoint_sha256`. The
reconstruction fallback would have failed this -- it computed a frame from an assumed cadence while
the file came from a save index, with nothing connecting the two. A trainer that writes a wrong `IC=`
is still not caught, and TIED says so.

**UNVERIFIABLE** -- no checkpoint matched the row's hash, or the row carries no hash, or the file is
named by index and no log line mentions it. Nothing was checked. It must never print like a pass.

## The cadence check, which is independent

`IC=` values are emitted by the trainer on a fixed save cadence. Uneven deltas mean a save was missed
or the cadence changed mid-run, and either one breaks any reasoning that maps save index to frame.
This is checked from the log alone and does not depend on the records, so it catches a class the
per-row grades cannot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

FRAME_IN_NAME = re.compile(r"_(\d+)\.(?:pt|pth|jd|tar)$")
#: The trainer's own save line. `ppg` is the family that needs it; the pattern is not ppg-specific,
#: so any family that names by index and logs the pair is covered without a new branch.
SAVE_LINE = re.compile(r"Saving to\s+(\S+)\s+IC=(\d+)")


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _checkpoints(root: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    """hash -> EVERY file with that content, frame-named ones first.

    [Claude 2026-09-09] This returned one path per hash and overwrote the rest, which lost the whole
    endpoint grid. Measured on card0-20260909-013936: every row carrying a `checkpoint_sha256`
    matched `snapshot.pt` -- the terminal snapshot, whose name carries no frame -- so all 24 read
    UNVERIFIABLE. The curve names its checkpoints (`..._501760.pt`) and the endpoint does not; the
    headline measurement was the one with no verifiable label, for EVERY family, not just ppg.

    A trainer that writes `snapshot.pt` normally writes the same bytes to a frame-named file. When
    it does, the two are ALIASES and the frame-named one corroborates the record exactly as it would
    have if the endpoint had measured it directly -- same bytes, same weights, an independent
    producer having stamped the frame into a name. So all aliases are kept and the frame-named ones
    are preferred.
    """
    out: dict[str, list[pathlib.Path]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in (".pt", ".pth", ".jd", ".tar"):
            try:
                out.setdefault(_sha256(path), []).append(path)
            except OSError:
                continue
    for paths in out.values():
        paths.sort(key=lambda p: (FRAME_IN_NAME.search(p.name) is None, p.name))
    return out


def _save_lines(root: pathlib.Path) -> tuple[dict[str, int], list[tuple[str, int]]]:
    """basename -> frame, plus the ordered sequence for the cadence check."""
    by_name: dict[str, int] = {}
    ordered: list[tuple[str, int]] = []
    for log in sorted(root.rglob("*.log")):
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        for match in SAVE_LINE.finditer(text):
            name = pathlib.PurePosixPath(match.group(1)).name
            frame = int(match.group(2))
            # A later line for the same basename wins: a resumed run rewrites the same index.
            by_name[name] = frame
            ordered.append((name, frame))
    return by_name, ordered


def _records(target: pathlib.Path) -> list[dict]:
    """Every record under `target`, counting each row ONCE.

    [Claude 2026-09-09] `records_delivery.jsonl` is by construction the concatenation of
    `records.jsonl` and every `cells/*/offline_eval_*.jsonl`. Globbing all of them counted each row
    twice: a 553-row bundle audited as **1,106 records**, with corroborated and unverifiable both
    doubled. The per-row verdicts were right and every total was wrong, which is the worse failure —
    a reader checks the totals.

    So when the bundle and its own sources are both present, the bundle is skipped: the sources are
    the primary artifact and the bundle adds no row they do not have.
    """
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.jsonl"))
        sources = [f for f in files if f.name != "records_delivery.jsonl"]
        if sources and len(sources) < len(files):
            files = sources
    rows = []
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def cadence_report(ordered: list[tuple[str, int]]) -> list[str]:
    """A MISSED save, reported from the log alone. Jitter is not a finding.

    [Claude 2026-09-09] The first version flagged any delta differing from the modal one, and the
    live ppg cell's real cadence is **alternating 51200 / 49152**:

        0, 51200, 100352, 151552, 200704, 251904, 301056, 350208, 401408, 450560, 501760,
        550912, 600064

    That is `ic_per_save=50000` quantised onto a 2048-frame rollout -- the save fires on the first
    iteration past each 50,000 multiple, so the gap is 25 or 24 rollouts. Every correct ppg run
    produces it, and a check that fires on every correct run is one people learn to ignore.

    What the check is FOR is a save that did not happen, which breaks any index-to-frame mapping.
    So it compares against the median delta by RATIO: at least 1.5x is a gap where a save is
    missing, at most 0.5x is a duplicate or a restart. Quantisation jitter is neither.
    """
    frames = sorted({f for _, f in ordered})
    if len(frames) < 4:
        return []
    deltas = [b - a for a, b in zip(frames, frames[1:])]
    typical = median_int(deltas)
    if typical <= 0:
        return []
    odd = [(frames[i], frames[i + 1], d) for i, d in enumerate(deltas)
           if d >= 1.5 * typical or d <= 0.5 * typical]
    if not odd:
        return []
    out = [f"    the typical save interval is {typical} frames, and {len(odd)} gap(s) are at least",
           "    50% away from it -- large enough to be a missing or duplicated save, not jitter:"]
    for a, b, d in odd[:8]:
        out.append(f"      {a} -> {b} is {d}  ({d / typical:.2f}x typical)")
    return out


def median_int(values: list[int]) -> int:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="a run directory, or a records .jsonl")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any MISMATCH. TIED and UNVERIFIABLE never fail on their own")
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
    saves, ordered = _save_lines(root)
    corroborated = tied = mismatched = unverifiable = aliased = 0
    problems: list[str] = []

    for r in rows:
        sha = r.get("checkpoint_sha256")
        frame = r.get("frame")
        baseline = r.get("baseline", "?")
        if not sha or frame is None:
            unverifiable += 1
            continue
        paths = by_hash.get(sha)
        if not paths:
            unverifiable += 1
            continue
        path = paths[0]
        alias = (f" (as {path.name}, identical bytes to {paths[1].name})"
                 if len(paths) > 1 and FRAME_IN_NAME.search(path.name) else "")
        m = FRAME_IN_NAME.search(path.name)
        if m:
            named = int(m.group(1))
            if named == int(float(frame)):
                corroborated += 1
                if alias:
                    aliased += 1
            else:
                mismatched += 1
                problems.append(f"    {baseline} {r.get('regime','?'):<11} record frame={frame} "
                                f"but the checkpoint it measured is named {named} ({path.name})")
            continue
        logged = saves.get(path.name)
        if logged is None:
            unverifiable += 1
            continue
        if logged == int(float(frame)):
            tied += 1
        else:
            mismatched += 1
            problems.append(f"    {baseline} {r.get('regime','?'):<11} record frame={frame} but the "
                            f"training log saves {path.name} at IC={logged}")

    total = len(rows)
    print(f"RECORD FRAME PROVENANCE -- {total} record(s) under {target}\n")
    print(f"  corroborated  {corroborated:>5}   trainer filename and record agree, no shared code path")
    if aliased:
        print(f"    of which     {aliased:>5}   matched through a byte-identical frame-named alias "
              f"of an\n                      unnamed file such as snapshot.pt")
    print(f"  tied          {tied:>5}   frame belongs to the measured file, via the training log")
    print(f"  MISMATCHED    {mismatched:>5}   the frame does not belong to the file it labels")
    print(f"  unverifiable  {unverifiable:>5}   nothing was checked for these rows")

    if problems:
        print("\n  Disagreements:")
        for p in problems[:20]:
            print(p)

    if tied:
        print("\n  TIED IS WEAKER THAN CORROBORATED and the difference is not cosmetic. The record's")
        print("  frame is DERIVED from the same log line the check reads, so a trainer writing a")
        print("  wrong IC= passes. What it does establish is that the frame belongs to the specific")
        print("  file measured -- which is precisely what ppg_checkpoint_frame's reconstruction")
        print("  fallback broke, and what nothing downstream could have detected.")

    if unverifiable:
        print("\n  UNVERIFIABLE IS NOT OK. No checkpoint matched the hash, or the row carries none, or")
        print("  the file is named by index and no log line mentions it. Read these as unchecked.")

    if mismatched:
        print("\n  A mismatch means a real measurement is attached to the wrong frame. The record is")
        print("  well-formed and plausible, which is exactly why nothing else would catch it.")

    cadence = cadence_report(ordered)
    if cadence:
        print("\n  SAVE CADENCE IS UNEVEN -- checked from the log alone, so this holds even where every")
        print("  row above is unverifiable. Any reasoning that maps save index to frame is unsound:")
        for line in cadence:
            print(line)
    elif ordered:
        print(f"\n  Save cadence even across {len({f for _, f in ordered})} logged saves.")

    return 1 if (mismatched and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
