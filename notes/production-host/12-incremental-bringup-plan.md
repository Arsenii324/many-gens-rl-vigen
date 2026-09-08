# Incremental bring-up on `cds2` — the plan

**Status: PLAN ONLY. Nothing here has been executed.**

Each rung adds **exactly one** new risk, is bounded, is reviewed by a person before the next, and
is individually reversible. No rung runs until the one below it has been read and accepted.

## Design rules for every rung

1. **Fresh occupancy read immediately before.** Never a remembered one — card 1 went from 16301 MiB
   at 88% to 0 MiB in five minutes, and the tenant that did it is still resident.
2. **A stated upper bound before, a measured actual after.** If the bound cannot be stated, the rung
   does not run.
3. **One rung at a time. Never two concurrently**, and never concurrently with someone else's peak
   if it can be avoided.
4. **Cleanup verified, not assumed**: container gone, temp dirs gone, and the **disk delta measured**
   with `df` before and after.
5. **Abort criteria written down before starting**, so stopping is a decision already made rather
   than a judgement under pressure.
6. Nothing installed on the host. Everything inside the container.

## The two constraints that shape all of it

**Card 1 is shared with an intermittent tenant.** `rl4vla_cudagl_gpu1` has been up three weeks and
its load is episodic — measured at **16301 MiB** once. So **plan against ~16 GiB usable, not 32**,
and assume that 16 GiB can reappear mid-run.

**The root filesystem is at 99%, 325 GB free** — and this bites harder than it first looks:

> A container's writable layer, its `apt-get` packages and its pip wheels are stored under
> `/var/lib/docker` **on the host's root filesystem**. "Inside a container" is not "off the shared
> disk". `run_probe.sh` runs `apt-get install` (~11 packages) and `pip install -r requirements`
> including torch, which is several GB per image build.

So disk is consumed at rungs 3 and 5 even though neither trains anything.

---

## STATUS as of 2026-09-08 ~16:00 MSK — rungs 0–3 executed, and rung 3 earned its keep

| rung | state | what actually happened |
|---|---|---|
| 0 read-only | **done** | one filesystem, 325→321 GB free at 99%; card 1 holds 17268 MiB at 0% util; 125 GB RAM, 111 available |
| 1 wrapper dry run | **in progress** | needed a payload on the host first; being built in a container |
| 2 pinned image present? | **done — it was ABSENT** | raised as the plan requires, then pulled by digest with the cost stated (~2 GB, 323→321 GB). `sha256:94c1577b…` confirmed, Ubuntu 22.04.3, no `python3` (correct for a runtime image) |
| 3 container, no GPU, nothing installed | **done, and it found a blocker** | see below |
| 4 GPU visible, no compute | **not started** | |
| 5 first CUDA allocation | **blocked** | card 1's 17268 MiB is not ours to clear, and no production-geometry VRAM peak has been measured |
| 6–7 real cells | **blocked** | on rung 5 and on the owner items |

**Rung 3 was supposed to be a formality and was not.** Running the documented provisioning path in
a container found that `setup/bootstrap_sources.py` refuses its own correct output: the pinned
`expected_tree_hash` for RL-ViGen had been computed on macOS from a tree missing all 546 files
under `third_party/robosuite/robosuite/models/`. No local instrument could ever have caught it —
`verify_sources.py` correctly abstains on a case-insensitive filesystem, so the pin sat unverified
until a machine existed that could check it. Repinned against the Linux reconstruction,
cross-validated against the archive production actually runs, and `verify_sources.py` on the host
now prints `source reconstruction verified` with **no** `NOT VERIFIED HERE` line for the first time.

Three further defects were found and fixed by walking these rungs rather than reasoning about them:
the staging directory was on a filesystem nothing checked; `check-memory` was reachable only via one
literal profile string; and **`--gpus` defaulted to `all`**, which on a per-day-assigned machine
would have taken a neighbour's card on any run that forgot one environment variable.

That is the argument for the ladder. The remaining rungs get run, not reasoned about.

## Rung 0 — read-only. No writes, no container, no GPU.

```bash
ssh -o BatchMode=yes varaksin_as@100.98.2.11 '
  nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader
  df -h "$HOME" | tail -1
  free -g | sed -n 2p
  uptime'
```

Confirms: assignment still valid for today in **UTC+3**, card 1's current occupancy, disk headroom.
**Abort if** free disk has fallen below ~100 GB, or card 1 shows a load whose peak we cannot bound.

## Rung 1 — the wrapper's dry run. Writes ~250 KB to a temp dir, removed by its own `trap`.

```bash
NATIVE_HOST_DRY_RUN=1 FRAMES=10000 CELLS=<one baseline>:1 CELL_TIMEOUT_SECONDS=3600 \
DOCKER_GPUS='"device=1"' \
bash datasphere/native/run_on_production_host.sh <payload> <result-in-our-own-dir>
```

Runs every guard, the disk arithmetic, payload staging, mount assembly and env forwarding, prints
the exact `docker run`, and **exits without executing it**.

**Review before rung 2**: read the printed `mounts:` block line by line — every host path must be
inside our own directory — and the `env:` block, and confirm `--gpus "device=1"`.
**Abort if** any mount resolves outside our directory, or the GPU flag is not exactly card 1.

## Rung 2 — is the pinned image already present? (No pull.)

```bash
docker image inspect nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b2cd9... >/dev/null \
  && echo present || echo ABSENT
```

Scoped to one image by digest — not `docker images`, which lists everyone's.

**If ABSENT this is a decision, not a step.** Pulling writes ~2–3 GB to a root filesystem at 99%.
Stop and raise it.

## Rung 3 — container starts, **no GPU**, nothing installed.

```bash
docker run --rm --name rlvigen-smoke-<stamp> <pinned-image> python3 --version
```

Proves: we can run a container, the image works, it exits cleanly, and the name convention makes it
identifiable as ours. **No `--gpus`.** No `apt-get`, no `pip`.

Upper bound: a few MB of container layer, seconds of runtime, zero VRAM.
**Verify after**: `docker ps --filter name=rlvigen-smoke` is empty, and `df` shows no meaningful
delta.

## Rung 4 — GPU **visible**, still no compute.

```bash
docker run --rm --gpus '"device=1"' --name rlvigen-gpucheck-<stamp> <pinned-image> nvidia-smi -L
```

Proves the pin works. The decisive check: **`nvidia-smi -L` inside must list exactly one GPU.** If
it lists two, the pin failed and everything downstream would have had access to card 0 — stop
immediately.

Upper bound: no VRAM allocated (a listing, not a context).
**Abort if** two GPUs are visible, or the command touches card 0 in any way.

## Rung 5 — the first CUDA allocation, deliberately tiny and capped.

A single small tensor, printed device, immediate exit — with the cap set so **our** process dies
first if anything grows:

- PyTorch: `PYTORCH_CUDA_ALLOC_CONF` and `torch.cuda.set_per_process_memory_fraction`
- JAX/`ctrl`: `XLA_PYTHON_CLIENT_PREALLOCATE=false` (already set) **plus**
  `XLA_PYTHON_CLIENT_MEM_FRACTION`

**Neither cap is currently set for any family — that is a code change owed before this rung.**
Without it we have no enforcement, only hope, and the whole point of a cap is that a runaway kills
our run rather than the tenant's.

Upper bound: state it explicitly, e.g. ≤1 GiB, enforced by the fraction.
This rung installs Python packages, so it is also **the first meaningful disk write** — measure it.

## Rung 6 — the shortest real cell, on the smallest family.

**`dmc_gb` (`rad`) or `alda`.** Chosen deliberately: both measured at **~1.4 GiB**, both at their
**production parallelism** (single env), so their observed peak is representative rather than
extrapolated. Not `ibac_sni` despite its 0.88 GiB — that was `procs=1` against production's 16.

Sized to `min_frames` plus a margin, **not** the inherited uniform 10000: `dmc_gb`'s `min_frames` is
**1001**. Attestation-shaped work needs a training row, a checkpoint and an endpoint eval. Roughly
350s of training rather than 3448s. *(Copying the uniform 10000 is exactly the inefficiency that
cost about an hour on the pre-production wave.)*

**Verify after**: records emitted, checkpoint written, `retained.json` sane, container gone, disk
delta measured, and the whole thing reconciled against the same cell run on DataSphere.

## Rung 7 — one full-length cell.

Only after 6 is clean, and only if **all** of these hold:

- disk headroom covers the cell's full footprint (~56 GB, ~80 GB if Places365 is needed) with margin
- the **GPU assignment window** covers the cell's projected wall clock in UTC+3 — a cell that will
  outlive its window must not start, because off-policy cells cannot resume from a mid-run
  checkpoint (`ai-recommendation-22`: replay is not persisted; a cut-off cell restarts from frame 0)
- card 1's tenant is accounted for: our bound **plus** its ~16 GiB peak fits in 32 GiB

`ctrl` and `ibac_sni` are **not** candidates for rung 7. Both would run at a parallelism their
measurements never covered, and `ctrl` was already at 20.78 GiB with a quarter of production's
environments.

---

## What must be settled with the owner before rung 5

1. **Where campaign data may live.** 325 GB on a shared root does not hold a 36-cell campaign, and
   at 99% our writes could be what fills it — which breaks every writer on the machine at once.
2. **How many consecutive days are assigned**, since no 600k cell fits one day and none can resume.
3. **Whether the VRAM caps may be added** — a small code change to the launchers, owed before any
   allocation on a shared card.
