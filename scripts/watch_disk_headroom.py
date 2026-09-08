#!/usr/bin/env python3
"""Stop OUR cell if free disk falls toward a floor. Loud, positive, and on a mandatory timer.

    python scripts/watch_disk_headroom.py --path /home/me/runs --floor-gib 60 \
        --sentinel /work/yield.sentinel --max-seconds 14400

## Why this exists

`run_on_production_host.sh` checks disk ONCE, before the container starts, and that check is a
snapshot. A cell writes for hours: pip into the container layer, checkpoints in triplicate
(trainer, `retain()` copy, and the closing archive, all live at the same moment), Places365 when a
family needs it. The host this project runs on is a **shared** filesystem at 99% used -- 317 GB free
of 20 TB -- and the free space is not ours to spend. A preflight cannot see any of that.

The failure this prevents is not our job dying. It is **somebody else's** job dying, or a monitoring
threshold firing, because we filled a disk we share. That asymmetry is why this stops US rather
than merely warning: by the time an operator reads a warning, the space is already gone.

## How it stops us, and why that mechanism

It writes the same yield sentinel the GPU co-tenancy watcher uses, and `run_probe.sh` polls for it
and terminates its own training process group. No docker socket, no signals into another container,
no privileged access -- the cell keeps sole authority over the cell. Artifacts written so far are
durable on the bind mounts, so a stopped cell loses the remainder of its training and none of its
results.

## Reading it

Every check prints, whether or not anything is wrong: a watcher that only speaks on failure is
indistinguishable from a watcher that died. It exits loudly on its timer for the same reason.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys
import time

sys.stderr.reconfigure(line_buffering=True)
sys.stdout.reconfigure(line_buffering=True)

BANNER = "!" * 78
GIB = 1024 ** 3


def say(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def free_gib(path: str) -> float | None:
    try:
        return shutil.disk_usage(path).free / GIB
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path", required=True, help="any path on the filesystem to guard")
    ap.add_argument("--floor-gib", type=float, required=True,
                    help="stop the cell when free space falls below this. Choose it from what the "
                         "job still has to write, PLUS what the machine needs to keep working -- "
                         "not from what we would like to use.")
    ap.add_argument("--sentinel", required=True,
                    help="written to stop our own cell; run_probe.sh polls for it")
    ap.add_argument("--max-seconds", type=float, required=True,
                    help="mandatory. A watcher nobody remembers starting is its own hazard.")
    ap.add_argument("--must-cover-seconds", type=float, default=None,
                    help="refuse to arm unless --max-seconds is at least this long")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true", help="report the decision, stop nothing")
    args = ap.parse_args()

    if args.must_cover_seconds is not None and args.max_seconds < args.must_cover_seconds:
        say(BANNER)
        say(f"!! REFUSING TO ARM: --max-seconds {args.max_seconds:.0f} is shorter than the "
            f"{args.must_cover_seconds:.0f}s this watch must cover.")
        say(f"!! The watch would end {args.must_cover_seconds - args.max_seconds:.0f}s before the "
            f"work does. (exit 3: budget too short; exit 2 = cannot read the path.)")
        say(BANNER)
        return 3

    start_free = free_gib(args.path)
    if start_free is None:
        say(f"cannot stat {args.path}; refusing to arm a disk watch that cannot see its disk")
        return 2

    say(f"=== DISK WATCH armed on {args.path}: {start_free:.1f} GiB free, floor {args.floor_gib:.1f} "
        f"GiB, for {args.max_seconds:.0f}s ===")
    if start_free < args.floor_gib:
        say(BANNER)
        say(f"!! ALREADY BELOW THE FLOOR at arm time: {start_free:.1f} < {args.floor_gib:.1f} GiB.")
        say(f"!! Not starting work on a disk that is already short. Nothing was stopped because")
        say(f"!! nothing should be started.")
        say(BANNER)
        return 4

    started = time.time()
    low_water = start_free
    while time.time() - started < args.max_seconds:
        free = free_gib(args.path)
        left = args.max_seconds - (time.time() - started)
        if free is None:
            say(f"{BANNER}\n!! CANNOT READ {args.path}. Not knowing is not the same as fine.\n{BANNER}")
        else:
            low_water = min(low_water, free)
            used_by_us = start_free - free
            if free < args.floor_gib:
                say(BANNER)
                say(f"!! DISK FLOOR BREACHED on {args.path}: {free:.1f} GiB free, floor "
                    f"{args.floor_gib:.1f} GiB.")
                say(f"!! {used_by_us:.1f} GiB has been consumed since this watch armed.")
                say(f"!! This filesystem is SHARED. Stopping our own cell rather than letting it")
                say(f"!! keep writing -- somebody else's job failing is the outcome that matters.")
                if args.dry_run:
                    say("!! --dry-run: NOT writing the sentinel. Nothing has been stopped.")
                    say(BANNER)
                    return 1
                try:
                    pathlib.Path(args.sentinel).parent.mkdir(parents=True, exist_ok=True)
                    pathlib.Path(args.sentinel).write_text(
                        f"disk floor breached on {args.path}: {free:.1f} GiB free < "
                        f"{args.floor_gib:.1f} GiB floor at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    say(f"!! sentinel written: {args.sentinel}")
                    say(f"!! the cell polls for it and stops its own training process group.")
                except OSError as exc:
                    say(f"!! COULD NOT WRITE THE SENTINEL ({exc}). THE CELL WILL NOT STOP ITSELF.")
                    say(f"!! Stop it by hand, now.")
                say(BANNER)
                return 1
            moved = (f"{used_by_us:.1f} GiB consumed since arm" if used_by_us >= 0
                     else f"{-used_by_us:.1f} GiB freed since arm")
            say(f"    {args.path}: {free:.1f} GiB free (floor {args.floor_gib:.1f}, low water "
                f"{low_water:.1f}); {moved}; {left:.0f}s of watch left")
        time.sleep(args.interval)

    say(BANNER)
    say(f"!! DISK WATCH ON {args.path} IS ENDING after {args.max_seconds:.0f}s.")
    say(f"!! Low water mark was {low_water:.1f} GiB. FROM NOW ON NOBODY IS WATCHING THIS DISK.")
    say(BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
