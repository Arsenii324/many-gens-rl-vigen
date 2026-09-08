# 22 — What a cell actually uses, measured on the card

**2026-09-09, during the first `idaac` cell to reach the GPU on `cds2`.** Measured rather than
estimated, because every packing decision below follows from it and the estimates in
`DECISION-SHEET.md` were made on different hardware.

## The measurement

30 samples at 2 s intervals of card 0 while `idaac:101` trained at `procs=1`, plus one
`docker stats` reading and host load:

| quantity | value |
|---|---|
| GPU utilisation | **mean 5.9%, max 8%** |
| GPU memory | **831 MiB** mean (of 32510) |
| GPU power | 55 W (card idles at ~40 W) |
| container CPU | **124%** — 1.24 cores of 16 |
| container RAM | **2.3 GiB** of 126 |
| host load average | 1.18 of 16 cores |

## What this says, and what it contradicts

**A cell uses about 6% of one V100 and 1.24 CPU cores.** The machine is ~94% idle while a cell
runs. The card is barely above its idle power draw.

Three consequences, in order of how much they change:

1. **Train is not VRAM-bound and not GPU-compute-bound. It is CPU-bound, weakly.** The open
   question was whether train is VRAM-bound while eval is compute-bound, which would make
   train/eval overlap attractive. For `idaac` that premise is false: nothing about this cell is
   near a GPU limit, so overlapping train with eval would be solving a problem that does not exist.
   The gain from overlap is bounded by 6% utilisation; the gain from **packing whole cells** is not.

2. **Thread tuning is not where the speed is.** `OMP_NUM_THREADS=4` is set and the process uses
   1.24 cores, so it is not saturating the threads it already has. Pinning or raising the thread
   count optimises something that is not the bottleneck. The bottleneck is serial environment
   stepping in robosuite, which is a per-process property.

3. **Packing is the whole opportunity.** Per-cell headroom, taking each limit alone:

   | limit | cells that fit |
   |---|---|
   | CPU (16 cores / 1.24) | ~12 |
   | GPU utilisation (100% / 6%) | ~16 |
   | GPU memory (32510 MiB / 831) | ~39 |
   | host RAM (113 GiB / 2.3) | ~49 |

   **CPU binds first, at roughly 12.** That is the arithmetic, not the recommendation.

## The recommendation is much lower than the arithmetic, and deliberately

This host is **shared**. Five containers belonging to other people were running during this
measurement; they were idle then and will not always be. Sizing our packing to the arithmetic
maximum would mean taking the entire machine and would make somebody else's job slow at a time of
our choosing, which is exactly the failure the whole co-tenancy apparatus exists to avoid.

**Pack 3-4 cells.** That is a 3-4x throughput gain for roughly 5 of 16 cores and ~25% of one card,
and it leaves the machine visibly free. If the measured per-cell figures hold at 600k frames, revisit
the number — but revisit it upward only with evidence about who else is using the box, not from the
table above.

## How to pack, and how NOT to

`run_probe.sh` takes a comma-separated `CELLS` list and runs the entries concurrently when
`NATIVE_CONCURRENT=1`. **That is one container with several cells, not several containers.**
`run_on_production_host.sh`'s own header states why: two containers would each bootstrap
separately, neither would see the other's memory use, and nothing would arbitrate between them.

`family.py check-memory` already sums the peaks under `NATIVE_CONCURRENT`, so the memory preflight
covers a packed cell. Whether it also covers the *disk* triple-copy for several cells at once is
**not** established here and should be checked before packing at 600k.

## What this does not measure

`idaac` only, at `procs=1`, at 10k frames, during early training. `ppg` is a different family and
the RL-ViGen-native baselines carry replay buffers that change the RAM picture entirely at 600k.
Every number above is one family's, and the per-limit table must be recomputed per family before it
is used to size anything.
