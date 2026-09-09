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


## Packed, measured 2026-09-09 — and the cap that was not capping

Two cells (`idaac:101,ppg:1`) under `NATIVE_CONCURRENT=1` on card 0:

| | solo (idaac) | packed (idaac + ppg) |
|---|---|---|
| GPU utilisation | 5.9% mean | **25.4% mean, 69% max** |
| GPU memory | 831 MiB | **9296 MiB** |
| CPU | 1.24 cores | 2.07 cores |
| RAM | 2.3 GiB | 4.8 GiB |

Packing behaves as the solo figures predicted for CPU and RAM, and better than predicted for GPU
utilisation. The watchers attributed both processes correctly (`2/2 process(es)`) once
`--expect-ours` was derived from the cell list.

**But the memory figure exposed a mechanism that had never worked.** Per-process:

```
243728, 2019 MiB     <- idaac
243736, 8207 MiB     <- ppg
```

against a declared `NATIVE_VRAM_CAP_MIB=2048`. `run_probe.sh` installed the cap as a
`sitecustomize` on `PYTHONPATH` and then **overwrote `PYTHONPATH` five lines later** without
preserving it. The cap has therefore never applied on any run.

It survived because a solo `idaac` cell sits at ~2019 MiB — just under the declared cap, because
that is simply what idaac uses. The cap appeared to work on the one family whose natural footprint
resembles it, and every run printed `NATIVE_VRAM_CAP_REQUESTED 2048 MiB`. **A coincidence that
looks like enforcement is worse than no enforcement**, because it is quoted as a safety property:
this one was, by me, in this repo, earlier the same day.

Consequence for packing arithmetic: the GPU-memory column in the table above was computed from an
*uncapped* `idaac` at 831 MiB and an uncapped `ppg` at 8207 MiB. `ppg` is roughly **10x** `idaac`
on VRAM, so a packed set must be sized from per-family measurements, not from one family's figure
multiplied by N.


## How many processes a cell puts on the card, measured 2026-09-09

**Two packed cells produce SIX compute processes.** Confirmed while we were the only user on the
box: `nvidia-smi --query-compute-apps` reported 6 with card 0 at 3689 MiB and 18% utilisation, and
the same run logged `NATIVE_VRAM_CAP_APPLIED` **24 times** — 24 interpreter starts.

`families.json` declares `num_processes: 1` for `idaac` and `num_envs: 1` for `ppg`. Both are true
and neither predicts this: the extra processes come from what robosuite, EGL and each trainer fork
underneath, not from anything the configuration names.

**This killed two production launches before it was understood.** The yield daemon counted
processes against `--expect-ours`, derived from the cell list as 2, saw 6, and stopped both healthy
cells at ~90 seconds — twice — while 28794 MiB of 32494 was free and utilisation was 21%. The
assumption was corrected three times before the signal itself was questioned:

| version | assumption | how it failed |
|---|---|---|
| first | ours is one process per RUN | packed run yielded to its own second cell |
| second | ours is one process per CELL | packed run yielded to its own forked workers |
| third | not countable in advance | process trigger made opt-in; memory floor is the trigger |

The lesson is not the number. It is that **a signal which needs a correct constant to be safe, and
whose correct constant is a property of somebody else's fork behaviour, is the wrong signal.**
Memory is the right one: it measures the harm directly (the process that asks the driver second is
the one that OOMs), needs no constant, and cannot be wrong about who owns what.

`watch_card_exclusivity.py` still counts processes and still reports co-tenancy loudly. Seeing a
neighbour arrive is useful; stopping a twelve-hour run over an uncountable proxy is not.


## Packing does NOT survive production scale — measured 2026-09-09, and it reverses this note

The recommendation at the top of this file was "pack 3-4 cells", derived from a **10k-frame** cell
using 831 MiB and 6% of the card. At **600k with production settings** the same packed pair
(`idaac:101,ppg:1`) reached:

```
card 0: 29910 MiB of 32494, 100% utilisation, 6 compute processes
yielded: free memory 2585 MiB is below the 4000 MiB floor
```

Two cells took **92% of a shared card**. The disk watch and the memory floor both behaved
correctly — the floor stopped us, cleanly, with no leak and the card back to 0 MiB — but what they
stopped was *us starving the card ourselves*, not a co-tenant.

**Why the 10k measurement did not predict this.** Utilisation and CPU scaled roughly as expected;
memory did not. At 10k the pair held 9296 MiB; at 600k, 29910. The growth is in what production
settings allocate (`SAVE_EVERY_FRAMES`, `EVAL_EVERY_FRAMES`, endpoint evaluation and each
trainer's own buffers), none of which is exercised at smoke scale.

**And the cap could not prevent it.** `NATIVE_VRAM_CAP_MIB` is enforced **per process**, and the
pair runs six. A 10240 MiB cap therefore permits 61 GiB on a 32 GiB card: it bounded every
individual process correctly and bounded the aggregate not at all. A per-process cap is not a
per-run budget, and treating it as one is how 92% of a shared card gets taken while every
individual limit reads as respected.

### Revised recommendation

- **Do not pack at production scale on a shared card.** One cell at a time.
- **Size the cap as `budget / expected_processes`**, and remember that the process count is not
  knowable from the cell list — it was 6 for two cells and no configuration file says so.
- The 10k packing measurement stands only for 10k. Any packing claim must be re-measured at the
  scale it is claimed for; this note asserted otherwise for several hours and was wrong.


## Correction, 2026-09-09 — the packing verdict was wrong, and it was my error of interpretation

The section above concluded that packing "does not survive production scale" because a packed pair
reached 29910 MiB of 32494. That reading was wrong in a way worth spelling out, because the wrong
number came from a fact recorded earlier in this same project and then not applied.

**`nvidia-smi memory.used` is the allocator's RESERVED pool, not live usage.** PyTorch's caching
allocator reserves and does not return; `NATIVE_VRAM_CAP_MIB` bounds exactly that reservation, per
process. The packed pair ran **six** processes under a **10240 MiB** cap, so it was entitled to
reserve up to ~61 GiB and reserved 29910 of it. Almost none of that was memory anyone needed.

The solo run proves the gap directly: `idaac` under a 4096 cap sat at **2644 MiB reserved** for five
hours, against a measured live requirement of **1204 MiB**. Reserved is roughly twice live, and it
tracks the cap, not the workload.

**There is no leak anywhere.** 37 consecutive samples of the solo 600k run read *exactly* 2644 MiB
across five hours of training. `idaac` saves checkpoints, writes logs, and holds a constant
footprint, which is what a normal on-policy trainer should do.

**`ppg`'s large footprint is its algorithm, not a defect.** `ppg.py:241` sets `n_pi=32` and
`store_segs = n_pi != 0 and n_aux_epochs != 0`, so PPG retains 32 rollout segments to fit its
auxiliary value head — the phasic phase that gives the method its name. At `nstep=2048`,
`frame_stack=3`, 64x64x3 float32 that is **288 MiB per segment and ~9.0 GiB of observations**,
bounded and expected.

### So what is the real packing constraint?

**Sizing, not feasibility.** The rule is `cap x expected_processes <= the share of the card we are
willing to hold`, and a cell runs about three processes. For two packed cells on a 32 GiB card,
leaving a third free for a neighbour: `cap = 20000 / 6 ~= 3400 MiB`. That binds `idaac` (live 1204)
comfortably and would bind `ppg` (live ~9 GiB) far too hard — so **`ppg` cannot be packed against a
small cap, and `idaac`-class families can**.

The withdrawal in the section above stands only for `ppg`-like families and for the specific
10240 cap that was used. It does not stand as a general claim, and note 21's queue should not be
read as if packing were ruled out.
