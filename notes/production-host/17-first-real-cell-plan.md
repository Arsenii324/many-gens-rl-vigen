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

**Step 0 — the automated pre-launch verdict.** `scripts/watch_gpu_headroom.py --preflight` is the
machine-checkable form of step 1, and it exits non-zero so a launch can be gated on it rather than
on someone reading a number:

```
python3 scripts/watch_gpu_headroom.py --preflight --device 0 --need-mib 4000
```

*Executed 2026-09-08: refused with exit 1 — "the card is at 100% with another process on it".*
The utilisation half is a courtesy constraint and is overridable with `--max-util 100` once the
owner has said that slowing a co-tenant is acceptable; the memory half is not.

**Step 1 — re-read the card by hand, and read what the preflight refused to.** Not the figure from
earlier today.
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

**Device numbering, because it will confuse someone.** `--gpus '"device=1"'` pins the HOST's card
1, and inside the container it appears as **index 0** — `nvidia-smi` there reports
`0, Tesla V100-SXM2-32GB, ...` and `nvidia-smi -L | grep -c '^GPU '` returns **1**. That count is
the check that matters: if it is 2, the pin failed and nothing after it is safe. Anything reading
the card from inside a cell must therefore say `--device 0`, not `--device 1`.

*Executed 2026-09-08 in the pinned image: count 1, the card unchanged at 14,501/17,994 MiB — our
container consumed nothing.*

**Step 4 — a bounded CUDA allocation, deliberately tiny.** Allocate ~256 MiB, read it back, free
it, exit. Proves the driver/runtime pairing works under our image and that we can allocate at all,
at a size that could not disturb anyone.

**Cap ourselves before step 5, and understand why a headroom ratio is not enough.** A caching
allocator's reservation is a **floor** on future usage, not a ceiling: it does not shrink, and it
grows whenever a high-water mark is exceeded — at an eval pass with a different batch, a validation
stage, a concurrent evaluator beside training. None of those has occurred in any window we have
observed.

On a shared card that failure is one-sided. **Whoever asks the driver second is the one that
fails.** If we take the free memory and their allocator then wants more, *their* process raises the
OOM and ours never notices — we would cause a failure we could not see. A headroom ratio is
computed from what they hold now and cannot protect against that.

So the first cell runs with `NATIVE_VRAM_CAP_MIB` set — `idaac` measured at 1204 MiB, so **2048**
is roughly 1.7× with room for a transient and still 8× below what is free:

```
NATIVE_VRAM_CAP_MIB=2048
```

`torch.cuda.set_per_process_memory_fraction` then makes an allocation beyond that raise
`OutOfMemoryError` **in our process**. That is the right way round: our cell fails loudly, theirs
continues. A cell that dies against its own cap has a wrong bound, which is a finding rather than
an accident. The runner prints `NATIVE_VRAM_CAP_APPLIED`, so a returned log proves it bound.

Its limits, stated: it caps PyTorch's allocator only — cuDNN workspaces, NCCL buffers and any
library going straight to the driver are outside it. JAX is bounded separately by
`XLA_PYTHON_CLIENT_MEM_FRACTION`.

**Step 5 — `idaac` at a SHORT budget.** 10k frames, not 600k: minutes of exposure instead of hours,
with the full chain exercised. **Watch `nvidia-smi` throughout** and record our own peak from
`resources.json` — this is the first production-geometry VRAM measurement this project will have.
**Abort if** our attributed VRAM exceeds 4,000 MiB, or the neighbour's process disappears.

**Step 5a — capture torch's own peak, because `nvidia-smi` cannot.** `measure_resources.py` samples
`nvidia-smi`, which reports the allocator's RESERVED pool. That is the correct number for "what we
deny the neighbour", and it is the wrong number for "what the model actually needed". Step 5 is
this project's first production-geometry VRAM measurement, so it should record both:
`torch.cuda.max_memory_allocated()` and `max_memory_reserved()` at the end of the cell. Nothing
reads them today.

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


---

# The four contention channels, measured 2026-09-08 — and which one actually binds

Memory was the channel we watched all day and it is the one that does **not** bind.

| channel | reading | binds? |
|---|---|---|
| GPU memory | 17,994 MiB free, flat across 120 samples / 30 min | **no** — `idaac` needs 1,204 |
| host CPU | 16 cores, load average 1.42 (~9%), 32 users | **no** — `idaac` needs 1.35 cores |
| GPU memory bandwidth | `mem` 13–15% while `sm` 83–100% | **no** — ~85% headroom |
| **GPU SMs** | 83–100%, mean 88% over 30 min | **YES** |
| **GPU power** | 260–274 W against a 300 W limit | **YES** — ~26 W headroom |

The neighbour's job is **compute-bound**, not bandwidth-bound. Two consequences we could not have
seen from memory figures: our kernels contend for SMs that are already saturated, and they push a
card drawing 274 W into its 300 W cap, **clocking both jobs down**. Neither fails anything. Both
make someone else's work slower, and the second one does it to *our* work too.

## What is certain, what is not, and what is not ours to know

**Measured and stable:** free memory, CPU load, bandwidth headroom, power draw, SM utilisation.
Card 0 is parked — 135 MHz against a 1,530 MHz maximum, 41.8 W, 0 compute processes. That is
idle by four independent indicators, not one.

**Uncertain, and it is our uncertainty to reduce:** `idaac`'s 1,204 MiB was measured on `gt4.1`,
a **T4**. cuDNN selects different algorithms per architecture, so a V100 may want a larger
workspace. The 2,048 MiB cap is a reasonable first bound, not a derived one — and if it is too
tight the cell dies against its own cap, loudly, which is cheap and is a finding.

**Not ours to know, and no instrument here will fix it:** whether card 0 is booked by someone who
simply is not using it yet; whether the card-1 job will grow its reservation at a phase boundary
it has not reached; whether anyone is benchmarking. The schedule lives in a spreadsheet, and
30 minutes of flat memory is evidence about 30 minutes.

## The decision this forces, which is the owner's

Running `idaac` now would not fail anybody. It **would** measurably slow a job that is currently
using the card properly, through SM contention and the power cap. That is a courtesy question, not
a safety one, and it has three honest answers:

1. **Wait** for card 1 to fall idle. Costs time, costs nothing else, and the preflight already
   refuses until then.
2. **Run anyway**, with `--max-util 100` set deliberately and the cap at 2,048 MiB. Defensible —
   the card is assigned to us today — but it slows a colleague.
3. **Run the cell on DataSphere instead.** `idaac` at 600k is ~4.79 h of training plus the grid,
   roughly **1,300–1,700 RUB**, and contends with nobody. Every baseline fits `gt4i.1` at the full
   600k budget on the base profile; what does not fit a DataSphere tier is the **v100 profile's**
   larger settings, which is a different axis from length.

**Recommendation: (1) while the card is busy, (3) if the canary is wanted sooner than the card
frees.** Do not take (2) without saying so out loud — it is the only one that spends someone
else's throughput.

## Before the first cell, calibrate the instrument on the idle card

Card 0 is a known-zero baseline, which is the cheapest possible validation of a monitor: run the
enriched watcher against it and confirm it reports 0 sm / 0 bandwidth / ~41 W / 135 MHz / 0
processes. An instrument that cannot report a card that is definitely idle cannot be trusted about
a card that is definitely busy. Do that before relying on it to watch our own cell.
