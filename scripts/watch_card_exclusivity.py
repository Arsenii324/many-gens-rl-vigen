#!/usr/bin/env python3
"""Confirm out loud that a card is ours alone — and scream the moment it is not.

    python3 scripts/watch_card_exclusivity.py --device 0 --expect-ours 1 --max-seconds 3600

## Why this is not the yielder

`yield_gpu_to_neighbour.py` acts: a co-tenant appears, our cell stops. This one only SPEAKS, and it
speaks to the operator rather than to the cell. The two answer different questions — *"should we
get out of the way"* versus *"is the card we were told is free actually free"* — and merging them
would mean an alarm that can only fire by killing something.

## Three properties, each because the obvious version gets them wrong

**It confirms, it does not merely stay quiet.** A monitor that prints nothing while healthy is
indistinguishable from a monitor that died, and after an hour of silence a person reads both as
"fine". So it prints a positive line on every check: *card N is ours alone*. Silence from this
process means it is gone, never that all is well.

**It screams, and keeps screaming.** A single line about a foreign process scrolls away. A breach
prints a banner, repeats on every subsequent check, and exits non-zero so a wrapper can act on it.

**It dies on a timer, loudly.** `--max-seconds` is required. A monitor on a shared machine that
outlives the work it watched is a process someone else has to wonder about — and one that exits
quietly leaves the operator believing they are still covered. The exit banner is as loud as the
alarm, for exactly that reason.

## What it will not look at

The COUNT of compute processes and the card's memory. Never PIDs, never per-process memory, never
command lines: `notes/production-host/05-privacy-and-non-alarm.md` forbids profiling a colleague's
work, and a count answers "is somebody else here" without answering "who, and what".

"Ours" is therefore a NUMBER you assert — `--expect-ours` — not an identity this tool discovers.
Pass the number of cells you are running. Anything above it is somebody else.
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
import subprocess
import sys
import time

BANNER = "!" * 78


def card(device: int) -> dict | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={device}", "--query-gpu=memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
        used, free, util = [int(x.strip()) for x in out.stdout.strip().splitlines()[0].split(",")]
        procs = subprocess.run(
            ["nvidia-smi", f"--id={device}", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30)
        return {"used": used, "free": free, "util": util,
                "procs": len([l for l in procs.stdout.splitlines() if l.strip()])}
    except Exception:
        return None


def say(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", type=int, required=True)
    ap.add_argument("--expect-ours", type=int, required=True,
                    help="how many compute processes are OURS; anything above is a stranger")
    ap.add_argument("--max-seconds", type=float, required=True,
                    help="hard lifetime -- required, so this can never become furniture")
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--quiet-ok", action="store_true",
                    help="print the healthy confirmation only when it CHANGES (default: every check)")
    args = ap.parse_args()

    started = time.time()
    breaches = 0
    checks = 0
    last_ok = None
    say(f"=== CARD {args.device} EXCLUSIVITY WATCH armed: expecting at most {args.expect_ours} "
        f"process(es) of ours, for {args.max_seconds:.0f}s ===")

    while time.time() - started < args.max_seconds:
        now = card(args.device)
        checks += 1
        left = args.max_seconds - (time.time() - started)
        if now is None:
            say(f"{BANNER}\n!! CANNOT READ CARD {args.device}. Not knowing is not the same as fine.\n{BANNER}")
            breaches += 1
        elif now["procs"] > args.expect_ours:
            breaches += 1
            say(BANNER)
            say(f"!! CARD {args.device} IS NOT OURS ALONE: {now['procs']} compute processes, "
                f"expected at most {args.expect_ours}.")
            say(f"!! {now['used']} MiB used, {now['free']} MiB free, {now['util']}% utilisation.")
            say(f"!! Somebody else is on this card. Stop our work or move it.")
            say(BANNER)
        else:
            line = (f"    card {args.device} is ours alone: {now['procs']}/{args.expect_ours} "
                    f"process(es), {now['used']} MiB used, {now['util']}% util, "
                    f"{left:.0f}s of watch left")
            if not args.quiet_ok or line != last_ok:
                say(line)
                last_ok = line
        time.sleep(args.interval)

    # A quiet exit would leave the operator believing they are still covered.
    say(BANNER)
    say(f"!! CARD {args.device} EXCLUSIVITY WATCH IS ENDING after {args.max_seconds:.0f}s "
        f"({checks} checks).")
    say(f"!! FROM NOW ON NOBODY IS WATCHING THIS CARD. Breaches seen: {breaches}.")
    say(BANNER)
    return 1 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
