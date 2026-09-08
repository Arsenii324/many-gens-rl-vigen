# The first real cell: `idaac`, and how it cannot disturb the neighbour

Written 2026-09-08 against measured numbers. This is the plan from "nothing has run" to "one
algorithm has trained on cds2", ordered so that the first step that could affect another user is
also the step we have the most evidence for.

## Which baseline, and why it is not a close call

| baseline | RAM GiB | basis | VRAM MiB | disk GB | Places365 |
|---|---:|---|---:|---:|---|
| **`idaac`** | **5.17** | measured | **1204** | **9** | no |
| `ppg` | 6.20 | measured | 1588 | 9 | no |
| `ibac_sni` | 3.97 | measured | 1102 | 9 | no |
| `alda` | 15.73 | measured | — | 12 | no |
| `rad` | 21.40 | measured | 1476 | 29 | no |
| `drqv2` | 40.82 | measured | 1650 | 28 | no |
| `sgqn` | 40.82 | measured | 7142 | 29 | yes |
| `ctrl` | 56.28 | **EXTRAPOLATED** | — | 9 | no |

`ibac_sni` is nominally the lightest and is **still the wrong first choice**: at the v100 profile it
runs `procs=16` on a 16-core shared machine, so it is a whole-host CPU job. `ctrl` is the other
trap — its RAM figure is `13.57 × 4`, an extrapolation, and it is the JAX family (see below).

**`idaac`: 5.17 GiB RAM, 1204 MiB VRAM, 9 GB disk, no Places365, every figure measured.**

## The hazard that actually threatened the neighbour, and it was not a big baseline

**JAX preallocates 75% of the card by default.** Nothing in this repository said otherwise. On a
32,768 MiB V100 that is ~24,576 MiB reserved on the first CUDA call, needed or not. Card 1 holds
17,268 MiB of someone else's work, leaving 15,500 — so a `ctrl` cell could not even have succeeded,
and the failure mode is either dying immediately or taking everything left and starving them.

Fixed 2026-09-08 in `run_probe.sh`, for **every** cell rather than only the JAX ones, because a
guard that must be remembered per family will be missed:

```
XLA_PYTHON_CLIENT_PREALLOCATE=false     allocate on demand, like torch
XLA_PYTHON_CLIENT_MEM_FRACTION=0.25     bound it at 8 GiB of a 32 GiB card
XLA_PYTHON_CLIENT_ALLOCATOR=platform
```

The runner prints `NATIVE_GPU_MEMORY_DISCIPLINE ...` so a returned log proves it applied.

**Torch needs no equivalent and has none.** Torch allocates on demand and caches; it does not
preallocate. A hard per-process cap (`torch.cuda.set_per_process_memory_fraction`) would bound
transients too, and does not exist here — worth adding before a *large* torch cell, not before
`idaac` at 1204 MiB.

## The ladder

Each step states what it may consume before it runs, and what aborts it. **No step begins while
the previous one is unread.**

**Step 1 — re-read the card, immediately before anything.** Not the figure from earlier today.
```
nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader
free -g | sed -n 2p
df -h /
```
**Abort if** free VRAM on card 1 is below **4,000 MiB** (3× our measured 1204 with room for a
transient), or free RAM is below **16 GB** (3× our 5.17), or `/` is below **40 GB**.

**And a utilisation criterion, which the first version of this plan was missing.** Memory
thresholds alone are not enough:

| card 1 | 2026-09-08 ~11:20 MSK | 2026-09-08 16:52 MSK |
|---|---|---|
| memory used | 17,268 MiB | 14,501 MiB |
| utilisation | 0% | **100%** |

Their allocation **moved by 2.8 GB** between two readings, and the job went from parked to
computing. Two things follow. An allocation that varies can vary *upward*, so free memory read once
is not free memory during our run. And at 100% utilisation the card's compute is fully committed:
our cell would not fail them, but it would timeshare SMs with a running job and slow it.

**So: do not start step 5 while card 1 is at high utilisation from another process.** Wait for it
to fall, or ask the owner whether slowing that workload is acceptable. This is a courtesy
constraint rather than a correctness one, and it is exactly the case
`10-resource-upper-bound-rule.md` describes — not knowing what the co-tenant will need next is a
reason not to run, not a reason to run carefully.

**Card 0 is idle and is NOT an alternative.** Read 0 MiB used, 32,495 MiB free, 0% on the same
date. The assignment for 8 Sept is V100-**1**. An idle card is not an available card: the schedule
is the authority, not the occupancy, and today's idle card is somebody's assignment tomorrow.

**Step 2 — the wrapper's dry run at the real budget.** Costs nothing, proves every guard.
```
NATIVE_HOST_DRY_RUN=1 NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 \
CELL_TIMEOUT_SECONDS=... NATIVE_RESULT_MIRROR=... NATIVE_ACCEPT_SAME_DEVICE=1 \
DOCKER_GPUS='"device=1"' CELLS=idaac:101 FRAMES=... \
bash datasphere/native/run_on_production_host.sh <payload> <result>
```
**Abort if** it prints anything but `every guard passed`, or if `gpus:` is not exactly `"device=1"`.

**Step 3 — GPU visible, no compute.** The first step that touches the card at all.
```
docker run --rm --gpus '"device=1"' <pinned image> nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader
```
Proves the toolkit works and that we see **one** card, not two. Consumes no VRAM.
**Abort if** two GPUs are listed — the device pin failed and everything after it is unsafe.

**Step 4 — a bounded CUDA allocation, deliberately tiny.** Allocate ~256 MiB, read it back, free
it, exit. Proves the driver/runtime pairing works under our image and that we can allocate at all,
at a size that could not disturb anyone.

**Step 5 — `idaac` at a SHORT budget.** 10k frames, not 600k: minutes of exposure instead of hours,
with the full chain exercised. **Watch `nvidia-smi` throughout** and record our own peak from
`resources.json` — this is the first production-geometry VRAM measurement this project will have.
**Abort if** our attributed VRAM exceeds 4,000 MiB, or the neighbour's process disappears.

**Step 6 — read the artifacts before running anything longer.** Records, curve, endpoint grid,
`retained.json`, and `measure_vram_bounds.py` over the returned archive. Only then consider a
600k cell.

## What still cannot be promised, stated plainly

Their process holds 17,268 MiB **allocated**. Allocated memory is reserved, so we cannot take it —
but if their workload *grows* while ours is resident, our presence is what makes their growth fail.
Nothing in our control prevents that. The honest mitigations are the ones above: take little, cap
what we take, and keep the run short enough that the window is small.

**The disk arithmetic is settled** and is not a risk at this size: `idaac` needs 9 GB against
321 GB free, and the Places365 mount removes the only large term for the baselines that use it.
**The RAM arithmetic is settled** for sequential cells and now refuses concurrent ones that would
not fit. **The VRAM arithmetic is the one that has never been measured at production geometry**,
which is why step 5 exists and why it runs at 10k frames.
