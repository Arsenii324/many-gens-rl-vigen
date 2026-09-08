#!/usr/bin/env python3
"""Card headroom: one pre-launch verdict, or a bounded sampling run. Never a daemon.

    python3 scripts/watch_gpu_headroom.py --preflight --device 1 --need-mib 4000
    python3 scripts/watch_gpu_headroom.py --watch --device 0,1 --seconds 1800 --interval 15 \
        --out headroom.jsonl
    python3 scripts/watch_gpu_headroom.py --watch --device all --seconds 1800

## What it deliberately does NOT do

It never attributes usage to another user. `nvidia-smi --query-compute-apps` will hand you other
people's PIDs and their memory, and building an alert around that is profiling a colleague's work
on a shared machine -- which `notes/production-host/05-privacy-and-non-alarm.md` forbids and which
no amount of good intent makes appropriate.

So it reads two things only: the CARD's aggregate memory and utilisation, and the COUNT of compute
processes on it. A count answers "is the card busy" without answering "who and what". Our own usage
is attributable because our own PIDs are ours; that is what `measure_vram_bounds.py` does from a
returned archive, and it is the right instrument for that question.

## What `memory.used` means, and what a FLAT reading does not prove

`nvidia-smi` reports what the CUDA caching allocator has **RESERVED from the driver**, not live
tensor usage. PyTorch and JAX take blocks and recycle them internally, so allocate/free inside a
training step is invisible here. The number moves only when a framework asks the driver for *more*
-- when its high-water mark grows.

Measured on cds2's card 1, 2026-09-08: 71 samples over 17.6 min, `used_mib` **constant at 14501**
while utilisation took 19 distinct values from 0 to 100. The instrument was live; the memory
genuinely did not move.

**A flat reading is not evidence that the job has no phases.** It says the co-tenant's high-water
mark was set before our window and has not been exceeded during it. A phase that allocates more --
a larger eval batch, a different stage, a checkpoint save -- simply has not occurred yet, and
seventeen minutes says little about a job that may run for hours. Treat the minimum free figure as
"what is available right now", never as "what will remain available".

**For the safety question this is nevertheless the RIGHT number.** A neighbour cannot use memory
our allocator has reserved, whether or not our tensors fill it -- so reserved is exactly what one
process denies another. `max_memory_allocated()` answers a different and narrower question (how big
is the model's true peak) and would understate what we take from the card.

## Why bounded rather than a daemon

A long-lived watcher on a communal host is a process someone else has to wonder about, and one we
would eventually forget. `--watch` samples for a stated number of seconds and exits. If you want
coverage of a longer window, run it again and say so -- an explicit second measurement is better
than a process nobody remembers starting.

## Watching a card we are not assigned

`--device` takes a list, and `all` means every card the container can see. Observing a card we may
not USE is not a contradiction: the schedule governs running work, and a status query allocates no
memory, creates no CUDA context and runs no kernel. Knowing whether the other card is genuinely
idle over time is exactly what tells us whether a neighbour might move onto ours.

It does cost one thing, and it should be stated rather than buried: a container can only read a
device that was attached to it, so watching both cards means `--gpus all` on the OBSERVER
container. That is the flag this project otherwise refuses, and the reason it is acceptable here
and nowhere else is that this process cannot consume a GPU -- it shells out to `nvidia-smi` and
sleeps. Anything that could allocate must still name one card.

## Why the preflight is separate from the watch

The pre-launch question is a VERDICT -- may we start -- and must be a non-zero exit, so a launch
script can be gated on it without parsing text. The watch question is a DESCRIPTION -- what does
this card look like over time -- and must not fail merely because a neighbour is busy. Conflating
them produces a check that either blocks a measurement or fails to block a launch.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

# [Claude 2026-09-08] Memory was never the binding constraint on this host, and watching only it
# hid the two that are. Measured on cds2 card 1 while a neighbour trained: sm 83-100% but memory
# BANDWIDTH only 13-15% (compute-bound, not bandwidth-bound), and power 260-274 W against a 300 W
# limit -- about 26 W of headroom. Our kernels would push the card into its power cap and clock
# BOTH jobs down, which is a way of harming a co-tenant that no memory figure can show.
#
# `clocks.sm` is the cheapest idle/busy discriminator there is: card 0 read 135 MHz against a
# 1530 MHz maximum, which is parked, not merely between kernels.
FIELDS = ("index", "memory.total", "memory.used", "memory.free", "utilization.gpu",
          "utilization.memory", "power.draw", "power.limit", "temperature.gpu",
          "clocks.sm", "clocks.max.sm")


def read(device: int) -> dict | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={device}",
             "--query-gpu=" + ",".join(FIELDS), "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
    if len(parts) != len(FIELDS):
        return None
    try:
        row = {"index": int(parts[0]), "total_mib": int(parts[1]), "used_mib": int(parts[2]),
               "free_mib": int(parts[3]), "utilization_pct": int(parts[4]),
               "membw_pct": int(parts[5]), "power_w": float(parts[6]),
               "power_limit_w": float(parts[7]), "temp_c": int(parts[8]),
               "clock_sm_mhz": int(parts[9]), "clock_sm_max_mhz": int(parts[10])}
    except ValueError:
        return None
    # COUNT only. Deliberately not the pids, not the per-process memory, not the command lines.
    procs = subprocess.run(
        ["nvidia-smi", f"--id={device}", "--query-compute-apps=pid", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=30)
    row["compute_processes"] = len([l for l in procs.stdout.splitlines() if l.strip()])
    row["t"] = time.time()
    return row


def preflight(device: int, need_mib: int, max_util: int) -> int:
    row = read(device)
    if row is None:
        print("REFUSING: could not read the card. Not knowing is a reason not to run.")
        return 2
    print(f"  card {row['index']}: {row['used_mib']} MiB used, {row['free_mib']} MiB free, "
          f"{row['utilization_pct']}% util, {row['compute_processes']} compute process(es)")
    verdict = 0
    if row["free_mib"] < need_mib:
        print(f"REFUSING: {row['free_mib']} MiB free is below the {need_mib} MiB this run needs.")
        verdict = 1
    if row["utilization_pct"] > max_util and row["compute_processes"] > 0:
        print(f"REFUSING: the card is at {row['utilization_pct']}% with another process on it. "
              f"Starting here would timeshare SMs with a running job.")
        print("  This is a courtesy constraint, not a correctness one -- override deliberately "
              "with --max-util 100 if the owner has said it is acceptable.")
        verdict = 1
    if verdict == 0:
        print("  OK to start on this card, on THIS reading. A single reading is a snapshot, not a "
              "bound: an allocation that moved 2.8 GB in one day can move again.")
    return verdict


def visible_devices() -> list[int]:
    out = subprocess.run(["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
                         capture_output=True, text=True, timeout=30)
    return [int(l) for l in out.stdout.split() if l.strip().isdigit()]


def watch(devices: list[int], seconds: float, interval: float, out: str | None) -> int:
    rows, started, handle = [], time.time(), (open(out, "w") if out else None)
    try:
        while time.time() - started < seconds:
            for device in devices:
                row = read(device)
                if row is not None:
                    rows.append(row)
                    if handle:
                        handle.write(json.dumps(row) + "\n")
                        handle.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  interrupted; reporting what was sampled", file=sys.stderr)
    finally:
        if handle:
            handle.close()
    if not rows:
        print("no samples. Nothing was observed -- which is NOT the same as nothing happening.")
        return 1
    for device in devices:
        subset = [r for r in rows if r["index"] == device]
        if subset:
            report(subset)
    return 0


def report(rows: list[dict]) -> None:
    used = [r["used_mib"] for r in rows]
    free = [r["free_mib"] for r in rows]
    util = [r["utilization_pct"] for r in rows]
    procs = [r["compute_processes"] for r in rows]
    span = (rows[-1]["t"] - rows[0]["t"]) / 60.0
    print(f"  {len(rows)} samples over {span:.1f} min on card {rows[0]['index']} "
          f"({rows[0]['total_mib']} MiB total)")
    print(f"    used   MiB   min {min(used):6}  max {max(used):6}  mean {sum(used)//len(used):6}  "
          f"swing {max(used)-min(used):6}")
    print(f"    free   MiB   min {min(free):6}  max {max(free):6}  mean {sum(free)//len(free):6}")
    print(f"    util    %    min {min(util):6}  max {max(util):6}  mean {sum(util)//len(util):6}")
    print(f"    compute procs min {min(procs)}  max {max(procs)}")
    if "power_w" in rows[0]:
        pw = [r["power_w"] for r in rows]; lim = rows[0]["power_limit_w"]
        bw = [r["membw_pct"] for r in rows]
        clk = [r["clock_sm_mhz"] for r in rows]; clkmax = rows[0]["clock_sm_max_mhz"]
        print(f"    power   W    min {min(pw):6.0f}  max {max(pw):6.0f}  limit {lim:.0f}  "
              f"HEADROOM at peak {lim-max(pw):5.0f} W")
        print(f"    mem bandwidth %  min {min(bw):4}  max {max(bw):4}   (vs sm util above)")
        print(f"    sm clock MHz min {min(clk):6}  max {max(clk):6}  of {clkmax}")
        if lim - max(pw) < 40:
            print("    POWER-LIMITED: adding work here pushes the card into its cap and clocks")
            print("    BOTH jobs down. This is contention no memory figure can show.")
        if max(bw) < 30 and max(util) > 70:
            print("    Compute-bound, not bandwidth-bound: SMs are the contended resource.")
    print()
    print(f"  The number that matters for planning is the MINIMUM free: {min(free)} MiB. Not the "
          f"mean --")
    print("  a co-tenant's peak is what would collide with ours, and a mean hides it.")
    print(f"  Observed swing over this window: {max(used)-min(used)} MiB.")
    if max(used) == 0 and max(util) == 0:
        print("  IDLE for every sample. That is not the same as unbooked -- the schedule lives in a")
        print("  spreadsheet this instrument cannot read, and an idle card is still somebody's.")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", required=True,
                    help="one index, a comma list (0,1), or 'all'")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--need-mib", type=int, default=4000)
    ap.add_argument("--max-util", type=int, default=50)
    ap.add_argument("--seconds", type=float, default=1800)
    ap.add_argument("--interval", type=float, default=15)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.preflight == args.watch:
        print("choose exactly one of --preflight (a verdict) or --watch (a description)")
        return 2
    if args.preflight:
        if args.device == "all" or "," in args.device:
            print("--preflight is a verdict about ONE card: the one we would run on. Name it.")
            return 2
        return preflight(int(args.device), args.need_mib, args.max_util)
    devices = visible_devices() if args.device == "all" else [
        int(d) for d in args.device.split(",") if d.strip()]
    if not devices:
        print("no visible devices to watch")
        return 1
    print(f"  watching device(s) {devices} for {args.seconds:.0f}s at {args.interval:.0f}s "
          f"intervals -- reads only, no allocation")
    return watch(devices, args.seconds, args.interval, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
