#!/usr/bin/env python3
"""Why is this record bundle so large? Answers per field, not per file.

    python scripts/explain_delivery_size.py <records.jsonl>
    python scripts/explain_delivery_size.py <records.jsonl> --rows 5000

## Why this exists

`collect-host-run.sh` refuses a bundle over 1 MB/row and needs to hand the reader something better
than "it is big". On `card0-20260909-115331` the bundle was **1,365,573,627 bytes for 964 rows** and
the answer was a single field: `collect_record_delivery` stamps the run manifest onto EVERY row, and
that manifest inlined the resource sampler's entire per-second series -- 2,173,638 bytes of it,
carried 616 times.

That shape recurs. Anything large placed in a run-level structure is multiplied by the row count,
and the multiplication is invisible from any single row. So this reports the **largest fields by
total bytes across rows**, which is the quantity that actually made the file, rather than the
largest field of one row.

## What it also checks, because size was not the worst part

`gpu_compute_processes` comes from `nvidia-smi --query-compute-apps=pid,...`. On a SHARED host that
lists **other users' PIDs and their GPU memory**. A bundle carrying it would replicate them into
every published record, so this reports their presence separately from the byte count -- it is a
disclosure question, not a storage one, and a bundle small enough to pass the size guard can still
carry them.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys


def walk(obj, prefix, sizes, depth=0, max_depth=3):
    if depth > max_depth or not isinstance(obj, dict):
        return
    for key, value in obj.items():
        path = f"{prefix}{key}"
        sizes[path] += len(json.dumps(value, default=str))
        walk(value, path + ".", sizes, depth + 1, max_depth)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path")
    parser.add_argument("--rows", type=int, default=2000,
                        help="stop after this many rows (default 2000); the shape shows up fast")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    path = pathlib.Path(args.path)
    if not path.is_file():
        print(f"no such file: {path}", file=sys.stderr)
        return 2

    sizes: dict[str, int] = collections.defaultdict(int)
    total_bytes = row_count = scanned = 0
    largest = (0, 0)
    pid_rows = 0
    with path.open(errors="replace") as handle:
        for index, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            row_count += 1
            total_bytes += len(line)
            if len(line) > largest[0]:
                largest = (len(line), index)
            if scanned >= args.rows:
                continue
            scanned += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            walk(record, "", sizes)
            if "gpu_compute_processes" in line:
                pid_rows += 1

    if not row_count:
        print("no rows")
        return 1

    print(f"{path.name}: {row_count} rows, {total_bytes:,} bytes, "
          f"{total_bytes // row_count:,} bytes/row mean")
    print(f"  largest single row: {largest[0]:,} bytes at line {largest[1]}")
    print(f"  fields measured over the first {scanned} row(s)\n")
    print(f"  {'total bytes':>15}  {'per row':>10}  field")
    for field, size in sorted(sizes.items(), key=lambda kv: -kv[1])[:args.top]:
        # A parent and its child both appear; that is deliberate, it shows where the weight enters.
        print(f"  {size:>15,}  {size // max(1, scanned):>10,}  {field}")

    if pid_rows:
        print(f"\n  WARNING: {pid_rows} of the {scanned} scanned rows contain "
              f"`gpu_compute_processes`.")
        print("  On a shared host that is other users' PIDs and GPU memory, from nvidia-smi.")
        print("  This is a disclosure question rather than a size one: it stays true of a bundle")
        print("  small enough to pass collect-host-run.sh's byte guard.")
        print("  run_probe.sh stores a summary since 2026-09-10; a bundle from an older runner")
        print("  still carries the series.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
