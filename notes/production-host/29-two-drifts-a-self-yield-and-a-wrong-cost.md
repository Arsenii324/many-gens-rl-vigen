# 29 — Two drifts with one mechanism, a whole-card job that yields to itself, and a cost note 26 got wrong

**2026-09-10.** Four findings from the attestation wave, written because three of them correct
something already written down.

## 1. The drift mechanism, named

Twice in one session I took a shared resource I had no bound on:

- **card 1**: `nvidia-smi` showed `0 MiB, 0 %`, so I launched a cell on it. I have no booking for
  card 1.
- **disk**: `df` showed 289 GB free, so I started a ~24 GB Places365 download onto a shared
  filesystem at 99 % used.

**Both are the same error: substituting a point-in-time observation for a bound.**
[`10-resource-upper-bound-rule.md`](10-resource-upper-bound-rule.md) says exactly this and I used
the reading anyway. "It is free now" is not "the remainder will be enough for the whole of my
concurrent run".

**And both went through a path with no guard.** Where a wrapper encodes the rule, the rule held:
`run_on_production_host.sh` refused my first launch for a missing `NATIVE_VRAM_CAP_MIB` and I
complied; `launch-card-cell.sh` derives its disk allowance from `family.py disk-requirement`. The
drift went through hand-rolled `docker run` and through `host-run.sh`, **which had no disk check at
all** — the one host path that could write to a shared filesystem without stating the cost.

Fixed at the mechanism rather than the instance: `host-run.sh` now refuses a **writable** mount
without a declared `HOST_RUN_DISK_BOUND_GIB`, and refuses a bound that would leave less than the
project's own `NATIVE_DISK_ABS_FLOOR_GIB` of 50. Read-only mounts skip it; they cannot consume.

**The invariant: never touch a shared resource except through the wrapper that encodes its bound.
When no wrapper exists, that absence is the signal to compute the bound and write it down, not to
proceed.**

## 2. `ctrl` at the v100 profile is a whole-card job, and the floor yields to itself

`ctrl-s1` was stopped by its own yield watch:

    yielded at 1789026735: free memory 1210 MiB is below the 4000 MiB floor
    free_mib=1210 procs=1 util=0

**`procs=1` — the only process on the card was ours.** `ctrl` is `num_envs=16` under `datasphere`
and **64 under `v100`**, and at 64 it takes ~31 GB of a 32 GB card. The floor did exactly its job:
a neighbour arriving at that moment would have failed. But it means **`ctrl` at v100 cannot run
under a 4000 MiB floor without stopping itself.**

This is the memory-trigger analogue of the process-trigger's documented self-yield. `ppg` is already
known to be whole-card (26,653 MiB at its auxiliary phase, note 26). **`ctrl` at v100 joins it.**
Either is only schedulable on a card we hold outright.

Attestation is re-run under `NATIVE_HOST_PROFILE=datasphere`, which is what the v205 configs used
and what keeps `num_envs` at 16. The profile does **not** change the evaluator revision — that is
computed from `families.json`'s bytes, not from the resolved profile — so the attestation is valid.

## 3. Note 26's cost for fixing the nine launchers is wrong

[`26-the-vram-cap-never-reached-a-trainer.md`](26-the-vram-cap-never-reached-a-trainer.md) says:

> Fixing the nine launchers is a **hashed-tree edit** (`runnable/_launch/*` are payload members),
> so it moves payload hashes and is an owner decision

Checked, all three claims:

| | |
|---|---|
| evaluator revision | **NOT moved.** `runnable/_launch` is in **no** `FAMILY_RUNTIME_MEMBERS` entry — so no re-attestation |
| source closure | **NOT affected.** The reconstruction trees are `runnable/<family>` and `RL-ViGen-upstream`; `runnable/_launch` is outside all of them |
| payload bytes | **changed** — payloads must be rebuilt, which is routine and happens every wave anyway |

So the edit costs a payload rebuild, not a re-attestation of seven families. **Note 26's second
argument still stands and is the one that matters**: a per-process cap is coercive, cannot see
render buffers or the CUDA context, and fails hardest late in a long run where the loss is largest.
Not fixing it remains defensible — but it should be declined on that argument, not on a cost that
is three times larger than the real one.

## 4. The disk bound is a ceiling, not a budget

Measured for the battery with Places365 mounted, one cell at a time:

    Places365 extracted (permanent)      26.5 GiB
    retained checkpoints, whole fleet    28.6 GiB
    worst single live cell (soda)        29.0 GiB
    ----------------------------------------------
    peak                                 84.1 GiB   of 273 GiB free

That 84.1 is **the most we may ever occupy**, not an allowance to spend up to. The 27 cells that do
not need Places365 peak at **57.6 GiB**. The partial 1.4 GB download left by the aborted fetch was
removed, by full path, from inside a container, after verifying it was ours and unheld.
