# The upper-bound rule

> **If you do not know an upper bound on the resources you will occupy, do not run it.**
>
> **If anything else is occupying the GPU, CPU, RAM, disk or any other shared part — someone
> else's, or not certainly yours, or even certainly yours — and you are not sure the remainder will
> be enough for the whole of your concurrent run, do not run yours.**
>
> — the owner, 2026-09-08

This subsumes most of `04-resource-safety.md`. Where they differ, this wins.

## Read it as a bound, not an estimate

An upper bound is a number the run **cannot exceed**, with a reason. It is not a typical value, not
a previous run's average, and not a projection from a smaller configuration.

- "It used 13.57 GiB at `num_envs=16`, so 64 envs is about 54 GiB" is an **extrapolation**. Not a
  bound. That specific one is live in `families.json` (`ctrl.host_profiles.v100.production.
  host_memory_model`) and is marked as an extrapolation there.
- "It peaked at 3.33 GiB last time" is a **past observation**. It bounds nothing about a longer run,
  a different profile, or a phase that run never reached.
- A bound you cannot state in a number is not a bound.

## Peaks are combined, transient, and not where you are looking

CUDA OOM does not happen at the typical usage level. It happens when **your peak and theirs
coincide**, and peaks arrive in phases that are brief and easy to miss:

- model/dataset **loading** and first-touch allocation
- **epoch or phase switches** — PPG's auxiliary phase, an evaluation sweep opening its own envs
- **gradient / batch accumulation**, and any transient doubling during an optimizer step
- **autotuning and compilation.** Measured in this project: a `ctrl` cell requested a transient
  **8.27 GiB** inside XLA's convolution autotuner, mid-run, from a downstream path nobody was
  watching
- caching allocators that **grow and do not return** memory to the driver
- checkpoint save/load, which can hold a second copy of the weights

*(Not an exhaustive list — judgement is required beyond it.)*

**Consequence: a card that looks half free is not therefore half free for the next hour.** Another
process idling at 4 GiB may be about to take 20. Read what is running, and if you cannot bound
*its* peak either, you do not have enough information to start — which is a stop.

## Where this project stands today: it does NOT satisfy the rule for VRAM

`families.json` records a measured host-RSS peak per family, with a `memory_margin_gib`:

| family | host RSS peak (GiB) | VRAM upper bound |
|---|---:|---|
| rlvigen | 3.33 | **none** |
| dmc_gb | 2.64 | **none** |
| idaac | 3.17 | 2.23 GiB, **prose only**, not a structured field |
| alda | 14.73 | **none** |
| ppg | 4.20 | **none** |
| ibac_sni | 1.97 | **none** |
| ctrl | 13.57 (16 envs; 54.28 at 64 is extrapolated) | **none** |

**Six of seven families have no VRAM measurement at all**, and the seventh has one only in a prose
note. So under this rule, **no production cell may be started on a shared GPU yet** — we cannot
state what it will occupy.

This is a blocking gap, and it is exactly what the rule is for.

## Making the bound enforceable rather than hoped for

A measured bound is still only a description. Where the framework allows it, **cap the process** so
the bound is enforced:

- **JAX / `ctrl`** — `runnable/_launch/ctrl.sh:38` already sets
  `XLA_PYTHON_CLIENT_PREALLOCATE=false`, so it does not grab the whole card at startup. Add
  `XLA_PYTHON_CLIENT_MEM_FRACTION` to cap the fraction it may reach.
- **PyTorch / the other six** — `torch.cuda.set_per_process_memory_fraction`, and
  `PYTORCH_CUDA_ALLOC_CONF` to bound the caching allocator's growth.
- **Neither is currently set for any family.** That is the gap to close before the first shared-GPU
  run.

A cap turns "we think it stays under N" into "it cannot exceed N, and if it tries, **our** run dies
rather than someone else's". That asymmetry is the entire point.

## The procedure, per run

1. State the upper bound for VRAM, RAM, cores and disk — as numbers, with why each is a bound.
2. Read the current occupancy of each on the assigned card and host.
3. Check that **bound + everything already there** fits, at the combined peak, not the average.
4. If any bound is unknown, or any headroom is uncertain, or another load's peak cannot be bounded
   — **do not run.** Say which one was unknown.
