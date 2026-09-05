#!/usr/bin/env python3
"""Extract a family's peak resident set from a finished job and record it in the descriptor.

Five of seven families have no `fixed_peak_gib`, so `check_memory` could say nothing about them --
and said "memory ok" anyway until 2026-09-05, which is how ctrl reached a tier that killed it. The
number is already in every job we run: the runner wraps each cell in `/usr/bin/time -v`, which
prints `Maximum resident set size (kbytes)`.

Usage:
    python scripts/record_measured_peak.py <job-dir> [--family ctrl] [--write]

Reads the extracted result tree (the one holding `cells/<cell>/training.log`). Without `--write` it
only reports, because a peak from a run that FAILED is a lower bound, not a peak, and the difference
decides whether the recorded number is usable.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "datasphere" / "native" / "families.json"
GIB = 1024 * 1024


def peaks(job_dir: pathlib.Path) -> dict[str, tuple[float, bool]]:
    """cell -> (peak GiB, completed cleanly). A killed cell reports a LOWER BOUND."""
    found: dict[str, tuple[float, bool]] = {}
    for log in sorted(job_dir.rglob("training.log")):
        text = log.read_text(errors="replace")
        match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", text)
        if not match:
            continue
        status = re.search(r"Exit status: (\d+)", text)
        clean = bool(status) and status.group(1) == "0"
        found[log.parent.name] = (int(match.group(1)) / GIB, clean)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", type=pathlib.Path)
    parser.add_argument("--family")
    parser.add_argument("--margin", type=float, default=2.0,
                        help="headroom over the observed peak; the descriptor stores it separately "
                             "so the measurement and the judgement stay distinguishable")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    found = peaks(args.job_dir)
    if not found:
        print(f"no `/usr/bin/time -v` block under {args.job_dir}; nothing to record")
        return 1
    for cell, (gib, clean) in sorted(found.items()):
        kind = "peak" if clean else "LOWER BOUND (cell did not exit 0)"
        print(f"  {cell:20} {gib:6.2f} GiB   {kind}")
    if not args.write:
        print("\n  reporting only; pass --write with --family to record it")
        return 0
    if not args.family:
        print("\n  --write needs --family")
        return 1

    gib, clean = max(found.values(), key=lambda item: item[0])
    raw = json.loads(DESCRIPTOR.read_text())
    production = raw.setdefault(args.family, {}).setdefault("production", {})
    production["fixed_peak_gib"] = round(gib, 2)
    production["memory_margin_gib"] = args.margin
    production["memory_note"] = (
        f"Measured from {args.job_dir.name}: peak RSS {gib:.2f} GiB, cell exit "
        f"{'0 (clean peak)' if clean else 'non-zero (LOWER BOUND -- the process died reaching for more)'}."
    )
    DESCRIPTOR.write_text(json.dumps(raw, indent=2) + "\n")
    print(f"\n  recorded {args.family}: fixed_peak_gib={gib:.2f} margin={args.margin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
