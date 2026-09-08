#!/usr/bin/env python3
"""Stop OUR cell when someone else needs the card. We yield; they never fail.

    python3 scripts/yield_gpu_to_neighbour.py --device 0 --container rlvigen-result-<stamp>
    python3 scripts/yield_gpu_to_neighbour.py --device 0 --container <name> --dry-run

## The asymmetry this exists for

A CUDA allocator's reservation is a floor: it never shrinks, and it grows when a high-water mark is
exceeded. On a shared card the process that asks the driver SECOND is the one that fails. So if we
are resident and a neighbour's job starts or grows, **their** allocation raises the OutOfMemoryError
and ours never notices. We would cause a failure we could not see.

`NATIVE_VRAM_CAP_MIB` bounds what we can take. This is the other half: it bounds how long we keep
it once somebody else wants the card. The rule the production-host notes state is that we must
never cause another process to fail; the only way to honour that against a co-tenant who arrives
after us is to leave.

## What it watches, and what it refuses to watch

The COUNT of compute processes on the card, and the card's free memory. Not who they are, not their
PIDs, not their memory — `notes/production-host/05-privacy-and-non-alarm.md` forbids profiling a
colleague's work, and a count answers "has someone else arrived" without answering "who and what".

Our own container is identified by NAME, which we chose. Everything else on the card is "someone
else" by definition, and that is the only distinction this needs.

## What "stop" means

`docker stop`, which sends SIGTERM and then SIGKILL after a grace period. Not `docker kill`. The
grace matters: `/tmp/native-out` and `/tmp/native-work` are bind-mounted, so every checkpoint
written so far is already on host storage and survives. A stopped cell loses the remainder of its
training, not its artifacts.

**It never touches anything but our own named container.** It cannot stop, kill, or signal another
user's process — the only verb it has is `docker stop <our-name>`.
"""
from __future__ import annotations

# [Claude 2026-09-08] Line-buffer our own stdout. Python BLOCK-buffers stdout when it is not a tty,
# which is always here -- these run detached in a container. Observed live: the yield watch ran for
# 52 seconds with completely EMPTY `docker logs`, indistinguishable from a container that crashed
# at startup. This project has already paid for this lesson once: run_probe.sh exports
# PYTHONUNBUFFERED=1 because a stall watchdog reading a buffer's flush cadence instead of a
# process's liveness killed two healthy ctrl cells.
#
# The alarm paths already pass flush=True, so a breach would have been visible. The routine
# confirmations were not -- and a monitor whose healthy output is invisible cannot be distinguished
# from a dead one, which is the whole property these scripts exist to provide.
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)
_sys.stderr.reconfigure(line_buffering=True)

import argparse
import pathlib
import subprocess
import sys
import time


def card(device: int) -> dict | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={device}", "--query-gpu=memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
        free, util = [int(x.strip()) for x in out.stdout.strip().splitlines()[0].split(",")]
        procs = subprocess.run(
            ["nvidia-smi", f"--id={device}", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30)
        return {"free_mib": free, "util": util,
                "procs": len([l for l in procs.stdout.splitlines() if l.strip()])}
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", type=int, required=True, help="card index as the HOST sees it")
    ap.add_argument("--sentinel", required=True,
                    help="path to write when yielding; run_probe.sh polls for it and exits")
    ap.add_argument("--active-file",
                    help="path the CELL touches when it starts using the card. Until it exists we "
                         "expect ZERO processes of ours, so a stranger arriving during the "
                         "bootstrap window cannot be absorbed as ours")
    ap.add_argument("--interval", type=float, default=30.0)
    # [Claude 2026-09-08] REQUIRED, and it is the fix for a leak I would otherwise have shipped.
    # The loop's only exits were "yielded" and "cannot read the card", so with no co-tenant ever
    # arriving -- the ordinary case -- a detached observer container ran FOREVER on a shared
    # machine, outliving the cell it was guarding by however long nobody noticed. A watchdog that
    # outlives its subject is just a process someone else has to wonder about.
    #
    # Set it a little beyond the cell's own CELL_TIMEOUT_SECONDS: long enough that it cannot expire
    # while the cell is still running, short enough that it cannot become furniture.
    ap.add_argument("--max-seconds", type=float, required=True,
                    help="hard lifetime; set just beyond the cell's CELL_TIMEOUT_SECONDS")
    ap.add_argument("--must-cover-seconds", type=float, default=None,
                    help="refuse to arm unless --max-seconds is at least this long. Pass the cell "
                         "timeout PLUS the bootstrap allowance: a watch that expires before the "
                         "work it covers is worse than none, because the operator believes they "
                         "are covered. Measured 2026-09-08: apt/pip bootstrap alone ran ~2h on the "
                         "production host, against a 4500s watch -- the GPU phase would have been "
                         "entirely unwatched.")
    ap.add_argument("--yield-after-checks", type=int, default=3,
                    help="how many CONSECUTIVE checks must see a co-tenant before yielding. "
                         "Memory starvation always yields immediately; process count is debounced, "
                         "because a transient process on a shared box is normal and killing a "
                         "12-hour run for it is not. Default 3 (~60s at the 20s interval).")
    ap.add_argument("--expect-ours", type=int, default=1,
                    help="how many compute processes OUR cell legitimately puts on the card. ONE "
                         "per cell, so a PACKED run of N cells must pass N. Getting this wrong in "
                         "the low direction makes the daemon yield to itself.")
    ap.add_argument("--stop-when-inactive", action="store_true",
                    help="stand down once --active-file has appeared and then been removed. Never "
                         "fires if the marker never appeared.")
    ap.add_argument("--floor-mib", type=int, default=2000,
                    help="yield if free memory falls below this, whoever caused it")
    ap.add_argument("--dry-run", action="store_true", help="report the decision, stop nothing")
    args = ap.parse_args()
    if args.must_cover_seconds is not None and args.max_seconds < args.must_cover_seconds:
        bar = "!" * 78
        print(bar)
        print(f"!! REFUSING TO ARM: --max-seconds {args.max_seconds:.0f} is shorter than the "
              f"{args.must_cover_seconds:.0f}s this watch must cover.")
        print(f"!! The watch would end "
              f"{args.must_cover_seconds - args.max_seconds:.0f}s before the work does, and "
              f"nothing would be yielding this card for that window.")
        print("!! Raise --max-seconds, or lower what you claim it must cover. "
              "Do not run uncovered. (exit 3: budget too short, distinct from "
              "exit 2 = cannot read the card)")
        print(bar, flush=True)
        return 3

    baseline = card(args.device)
    if baseline is None:
        print("cannot read the card; refusing to arm a watchdog that cannot see what it guards")
        return 2
    # Our own cell counts as one process once it starts. Anything BEYOND our own is a neighbour.
    print(f"  armed on card {args.device}; sentinel {args.sentinel}")
    print(f"  baseline: {baseline['procs']} compute process(es), {baseline['free_mib']} MiB free")
    if baseline["procs"]:
        print(f"  NOTE: {baseline['procs']} process(es) already on this card. They are the baseline;")
        print(f"        a yield fires only on arrivals BEYOND them, or on the memory floor.")
    print(f"  expecting up to {args.expect_ours} process(es) of our own")
    print(f"  a co-tenant must persist {args.yield_after_checks} consecutive checks to trigger "
          f"a yield; memory starvation triggers immediately")
    print(f"  will yield if a process appears beyond ours, or free memory drops below "
          f"{args.floor_mib} MiB")
    ours_seen = False
    saw_active = False
    consecutive = 0
    baseline_procs = baseline["procs"]
    started = time.time()
    sentinel_dir = pathlib.Path(args.sentinel).parent

    while True:
        if time.time() - started > args.max_seconds:
            print(f"  reached --max-seconds ({args.max_seconds:.0f}s) without yielding. Exiting "
                  f"rather than becoming a process nobody remembers starting.")
            return 0
        # The run directory is bind-mounted from the host. If it is gone, the run it belonged to is
        # gone, and guarding it is pointless.
        if not sentinel_dir.is_dir():
            print(f"  {sentinel_dir} no longer exists; the run it guarded is over. Exiting.")
            return 0
        # [Claude 2026-09-08] Stand down when the cell retracts its marker. Symmetric with the
        # exclusivity watcher: once our work is off the card there is nothing left to yield, and a
        # yield daemon that outlives its cell would sit there ready to write a stop-sentinel for a
        # run that has already ended. Only fires if the marker was ever seen -- a cell that died in
        # bootstrap must leave the daemon running, because that is when a neighbour is most likely
        # to arrive and find the card apparently free.
        if args.stop_when_inactive and args.active_file:
            active_now = pathlib.Path(args.active_file).exists()
            saw_active = saw_active or active_now
            if saw_active and not active_now:
                print("  the cell retracted its marker; our work is off this card. Standing down.")
                return 0
        now = card(args.device)
        if now is None:
            time.sleep(args.interval)
            continue
        # [Claude 2026-09-08] Count against a BASELINE captured before our cell starts, not against
        # the constant 1. The first version read `procs > (1 if ours_seen else 0)`, which assumes
        # the card is empty when we arm -- so a co-tenant who was ALREADY resident got counted as
        # our own process, and a second arrival would have been needed before it noticed. On a card
        # where somebody is already working, which is the case this exists for, it would never have
        # fired at the right moment.
        #
        # baseline = processes present at arm time. Ours adds `--expect-ours`, one per cell.
        # Anything above that is somebody new.
        #
        # [Claude 2026-09-09] This used to add the constant 1, with a comment asserting "ours adds
        # at most one". True for a single cell and FALSE for a packed one: the first packed run
        # (idaac+ppg, NATIVE_CONCURRENT=1) put two processes on the card, the second read as a
        # co-tenant, and the daemon yielded to itself and killed both healthy cells --
        # "compute processes went 0(+ours) -> 2". The mechanism worked perfectly against the wrong
        # expectation, which is the more dangerous kind of bug: nothing failed, the run just
        # stopped and reported a co-tenant that did not exist.
        # Our cell only counts as present once it SAYS it is on the card. Before that the
        # bootstrap is still running and any process is a stranger's.
        cell_active = (pathlib.Path(args.active_file).exists() if args.active_file else True)
        ours_seen = cell_active and (ours_seen or now["procs"] > baseline_procs)
        expected = baseline_procs + (args.expect_ours if ours_seen else 0)
        # [Claude 2026-09-09] Debounce the PROCESS trigger; never debounce the MEMORY one.
        #
        # A 600k production cell was killed ~90 seconds in by `procs -> 6` while only 3.65 GiB of
        # 32 was in use and utilisation was 21%. Our two cells declare one process each, so four of
        # those were somebody else's -- and on a box with a dozen containers, brief GPU touches by
        # other people are normal traffic, not a claim on the card. Yielding a twelve-hour run to
        # one poll of one such blip makes long runs impossible while preventing no harm at all.
        #
        # What we actually owe a co-tenant is memory: the process that asks the driver SECOND is
        # the one that fails. `free_mib < floor` is that condition measured directly, and it still
        # fires on the first reading. Presence is debounced; starvation is not.
        starved = now["free_mib"] < args.floor_mib
        crowded = now["procs"] > expected
        consecutive = consecutive + 1 if crowded else 0
        neighbour = crowded and consecutive >= args.yield_after_checks
        if crowded and not neighbour:
            print(f"  {now['procs']} process(es) on the card, expected {expected} "
                  f"({consecutive}/{args.yield_after_checks} checks) -- waiting before yielding",
                  flush=True)
        if neighbour or starved:
            why = (f"compute processes went {baseline_procs}(+ours) -> {now['procs']}"
                   if neighbour
                   else f"free memory {now['free_mib']} MiB is below the {args.floor_mib} MiB floor")
            print(f"=== NATIVE_YIELDING_TO_NEIGHBOUR {why} ===", file=sys.stderr, flush=True)
            print(f"    writing the sentinel; the CELL stops itself. Checkpoints already written "
                  f"survive on the bind mounts.", file=sys.stderr)
            if args.dry_run:
                print("    --dry-run: no sentinel written.", file=sys.stderr)
                return 0
            try:
                pathlib.Path(args.sentinel).write_text(
                    f"yielded at {time.time():.0f}: {why}\n"
                    f"free_mib={now['free_mib']} procs={now['procs']} util={now['util']}\n")
            except OSError as error:
                print(f"    COULD NOT write the sentinel: {error}. The cell will NOT stop.",
                      file=sys.stderr)
                return 2
            print(f"=== NATIVE_YIELD_SENTINEL_WRITTEN {args.sentinel} ===", file=sys.stderr, flush=True)
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
