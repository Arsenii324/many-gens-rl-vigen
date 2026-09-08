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

**Torch needs no equivalent for PREALLOCATION** — it allocates on demand and caches, so there is
nothing like JAX's 75% grab to disable. It does need a **cap**, and as of 2026-09-08 it has one:
`datasphere/native/vram_cap.py`, described in full further down this file. An earlier draft of this
paragraph said the cap "does not exist here", which was true when written and false by the time the
file was finished.

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


## What the cap does NOT cover — the residual, and why it matters more here than usually

`torch.cuda.set_per_process_memory_fraction` bounds **PyTorch's caching allocator** and nothing
else. Three things sit outside it:

1. **The CUDA context** — roughly 300 MiB on a V100, created before any tensor exists, invisible to
   `memory_allocated()`.
2. **EGL/OpenGL rendering buffers.** `MUJOCO_GL=egl` renders every observation **on the GPU**
   through the graphics pipeline rather than through CUDA, so `set_per_process_memory_fraction`
   can neither see nor bound it. For this project that is the significant one: every family renders
   84×84 observations continuously for the whole run.
3. Allocations bypassing torch — cuBLAS/cuDNN handle workspaces, and anything calling `cudaMalloc`
   directly.

**So `NATIVE_VRAM_CAP_MIB=2048` does not mean 2048 MiB on the card.** Expect cap + context +
rendering.

### Measured on cds2, 2026-09-08 — the cap binds

`scripts/verify_vram_cap.py` in the container, card 1, cap 512 MiB:

```
card before this process touched CUDA        14563 MiB   (all the neighbour's)
card after the CUDA context                  14871 MiB   -> CONTEXT COSTS 308 MiB
after allocating 256 MiB under the cap       15127 MiB   -> 564 MiB taken in total
request 1024 MiB, past the cap:  OutOfMemoryError raised IN THIS PROCESS
  "GPU 0 has a total capacity of 31.73 GiB of which 16.96 GiB is free"
max_memory_allocated 256   max_memory_reserved 256   over-reserve 0 MiB
```

**The decisive line is that 16.96 GiB was free and torch refused anyway.** The driver had the
memory; our own accounting stopped the request before `cudaMalloc` was called. We cannot take what
we did not declare, whatever the model later asks for — which is the property that protects a
co-tenant, and the reason a cap beats a headroom ratio.

So the footprint is `cap + ~308 MiB`. At `NATIVE_VRAM_CAP_MIB=2048` expect **~2.36 GiB plus the
EGL rendering share**, against ~17 GiB free.

**Two caveats on the 0 MiB over-reserve, because it is the weakest number here.** It was measured
with a single clean allocation, which cannot fragment — it shows the allocator does not round up
gratuitously, and says nothing about fragmentation under real training, where reserved routinely
exceeds allocated. And this ran on **torch 2.5.1+cu121**, not the pinned **2.3.1+cu121**: the
capping API is unchanged between them, but the arithmetic should be re-read from the real cell
rather than carried over from here. The first and third are measured by `scripts/verify_vram_cap.py`; the rendering share
only appears once an environment is stepping, which is step 5.

**And the cap binds on RESERVED, not allocated.** PyTorch rounds requests into blocks and caches
them, so `memory_reserved()` exceeds `memory_allocated()` — under fragmentation, substantially.
Fragmentation therefore eats the cap, and `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` is
the lever if the measured gap is large.

## Could we co-run because the profiles complement?

The strongest argument for running alongside the neighbour, and it is testable rather than
rhetorical. Their job is **compute-bound**: `sm` 83–100% against memory bandwidth 13–15%. If
`idaac` is environment-stepping-bound rather than GPU-compute-bound, we would use CPU (1.35 cores
against a load of 1.42 on 16) and memory (1,204 MiB against ~17,900 free) where they have headroom,
and touch SMs lightly.

Circumstantial support: `idaac` trains at **34.82 fps**, which is slow for a V100 and smells
environment-bound rather than GPU-bound.

**It cannot be claimed yet, for one specific reason: MuJoCo renders on the GPU via EGL.** Our
"CPU-bound" environment stepping is partly graphics work on the same SMs and the same power budget
that the neighbour is already saturating. The complementarity is plausible and unestablished.

**One number settles it** — our process's attributable `sm%` during a short `idaac` run, which is
exactly what step 5 produces. If it comes back low, co-running becomes defensible on evidence
instead of hope. Until then the preflight's utilisation refusal stands.

---

# The executable recipe: `idaac` on card 0 with a yield watch

Written 2026-09-08. **Not yet run.** Every value below is either measured or derived from something
measured; nothing here is a placeholder.

## The sentinel path, which is the part that silently does not work

`NATIVE_YIELD_SENTINEL` names **one file seen through three different mounts**. Get this wrong and
the observer writes a file nobody reads, the cell never yields, and nothing announces the failure:

| seen by | path |
|---|---|
| the host | `$WORK/yield.sentinel` |
| the observer container (`-v $WORK:/work`) | `/work/yield.sentinel` |
| the training container (`-v $WORK:/tmp/native-work`) | `/tmp/native-work/yield.sentinel` |

So `NATIVE_YIELD_SENTINEL=/tmp/native-work/yield.sentinel` — the **training** container's view,
because that is the process which reads it. And `$NATIVE_WORK_HOST_DIR` must be set **explicitly**:
the wrapper otherwise generates a stamped directory the observer cannot predict.

## Device numbering

Card 0 on the host is index 0 in every view here — `--gpus '"device=0"'` renumbers the pinned card
to 0 inside a container, and 0 is already 0 on the host. That coincidence does not hold for card 1
(host 1, container 0), so do not carry this recipe over unchanged.

## The sequence

```bash
export WORK=$HOME/rlvigen-runs/idaac-c0-$(date +%Y%m%d-%H%M)
mkdir -p "$WORK" "$WORK/out" "$WORK/mirror"

# 0. Verdict, not a glance. Non-zero exit means do not proceed.
docker run --rm -v "$PWD:/repo:ro" -w /repo --gpus '"device=0"' python:3.11-slim \
  python3 scripts/watch_gpu_headroom.py --preflight --device 0 --need-mib 4000

# 1. A payload built from THIS tree. Every archive on disk predates RUNNER_CONTRACT 16.
bash datasphere/native/host-run.sh -m "$PWD" <<'S'
python3 datasphere/native/contract.py build-payload \
  --source . --output /work/payload-idaac.tgz --families idaac
python3 datasphere/native/contract.py verify-payload --archive /work/payload-idaac.tgz \
  --require-runner-contract 16 --require-families idaac --require-evaluator-identity
S

# 2. The observer, in its own container, watching card 0 and writing the sentinel.
#    It allocates nothing: nvidia-smi and sleep.
docker run -d --rm --name rlvigen-yield-watch --gpus '"device=0"' \
  -v "$WORK:/work" -v "$PWD:/repo:ro" -w /repo python:3.11-slim \
  python3 scripts/yield_gpu_to_neighbour.py \
    --device 0 --sentinel /work/yield.sentinel --floor-mib 4000 --interval 30

# 3. The cell. DRY RUN FIRST -- every guard, no container, no GPU.
NATIVE_HOST_DRY_RUN=1 \
NATIVE_HOST_PROFILE=v100 NATIVE_PRODUCTION= \
CELLS=idaac:101 FRAMES=10000 TASK=Door SEED=101 \
DOCKER_GPUS='"device=0"' \
NATIVE_VRAM_CAP_MIB=2048 \
NATIVE_YIELD_SENTINEL=/tmp/native-work/yield.sentinel \
NATIVE_WORK_HOST_DIR="$WORK/native-work" NATIVE_OUT_HOST_DIR="$WORK/native-out" \
NATIVE_RESULT_MIRROR="$WORK/mirror" NATIVE_ACCEPT_SAME_DEVICE=1 \
ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy ENDPOINT_EVAL_SCENES=0 \
ENDPOINT_EVAL_EPISODES=5 \
  bash datasphere/native/run_on_production_host.sh \
    "$WORK/payload-idaac.tgz" "$WORK/result.tgz"

# 4. The same command with NATIVE_HOST_DRY_RUN removed.
```

## Why each value

- **`idaac`** — 5.17 GiB RAM, 1204 MiB VRAM, 9 GB disk, no Places365, every figure **measured**,
  and **profile-invariant**: the v100 profile changes nothing for it, because it is on-policy and
  holds no replay. `ibac_sni` is lighter on paper and runs `procs=16` on a 16-core shared box;
  `ctrl` is the JAX family and its RAM figure is an extrapolation.
- **`FRAMES=10000`** — minutes, not hours. This proves the host PATH. It proves nothing scientific:
  `drqv2` at 100k solves its trained scene 63% of the time and eval-easy **0.0%**, so a 10k `idaac`
  cell will learn nothing and is not meant to.
- **`NATIVE_VRAM_CAP_MIB=2048`** — 1.7× the measured 1204 MiB. Verified to bind: a 1024 MiB request
  past a 512 MiB cap raised `OutOfMemoryError` with **16.96 GiB still free on the card**. Add ~308
  MiB of CUDA context outside the cap, plus EGL rendering buffers it cannot bound at all.
- **`--floor-mib 4000`** — yield if free memory drops below roughly 3× what we need, whoever caused
  it.
- **`NATIVE_PRODUCTION=` empty and no `CELL_TIMEOUT_SECONDS`** — both are only demanded at
  `FRAMES >= 600000`. At 10k the production refusals do not apply.
- **`NATIVE_ACCEPT_SAME_DEVICE=1`** — cds2 has one filesystem, so a mirror on a different device
  does not exist here. This is an owner-level property of the campaign, not an operator setting.

## Abort criteria during the run

Stop if our attributed VRAM exceeds 4000 MiB, if the card's power stays within 20 W of its 300 W
limit with our kernels contributing, or if the neighbour's process disappears (we may have caused
it). The yield watch handles the arrival of a co-tenant automatically; these are the ones a person
still has to watch for.
