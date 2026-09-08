# This repository's own hazards on a shared host

Found by reading the code, not by running it. **This list is a floor.** Anything not here is
unexamined, which is not the same as safe.

## 1. `--gpus` used to default to `all` — FIXED 2026-09-08, and the history is the point

The script read:

```
docker run --rm --name "$CONTAINER_NAME" --gpus "${DOCKER_GPUS:-all}" \
```

Unset `DOCKER_GPUS` meant **`all`** — both V100s attached to our container, on a machine under a
per-day GPU assignment. One forgotten environment variable and a run took a card belonging to
someone else: silent from our side, a CUDA OOM or an unexplained slowdown from theirs. It was the
single most dangerous line in the repository.

**There is now no default.** The name must be given, and the refusal fires before anything starts
a container, because a pure environment test costing nothing must not be diagnosed after a
container has already launched:

```
DOCKER_GPUS='"device=1"'              # the assigned card; docker needs the inner quotes
DOCKER_GPUS='"device=GPU-<uuid>"'     # same card, immune to re-enumeration (nvidia-smi -L)
DOCKER_GPUS=none                      # CPU-only work
DOCKER_GPUS=all                       # every card -- only if you own them all
```

**The index form is not the safest spelling.** `device=1` follows docker's PCI enumeration, which
matches `nvidia-smi -L` in the ordinary case but is not guaranteed to across a driver reload or a
hardware change. On a machine where taking a neighbour's card is forbidden, prefer the UUID.

`DOCKER_GPUS=none` omits the flag entirely rather than passing `--gpus none`, which is invalid
docker — it parses the value as a count and fails with `count must be an integer`. That was found
by testing an option this script's own refusal message advertises; an unusable escape hatch in a
refusal is worse than none, because it gets followed under time pressure.

**An image cannot reach a GPU by itself.** Access is granted here, by this flag, through the NVIDIA
Container Toolkit; a CUDA base image run without `--gpus` sees no `/dev/nvidia*` at all. The danger
was never in which image was pulled — it was in this one string.

The script's own comment says `CUDA_VISIBLE_DEVICES` is deliberately absent from its forwarded
variables, and the reason is exactly right: it would *look* like it pinned the run while the
container still had both cards attached. Pin at the Docker level or not at all.

## 2. `ibac_sni` at `procs=16` requests every core on a 16-core shared machine

`families.json` `ibac_sni.host_profiles.v100.constants.procs = 16`, and `notes/remote-infra.txt`
records `nproc` **16**. That configuration is *correct* as fidelity — it restores `torch_rl`'s own
released rollout shape — and it is a whole-host job.

**Do not run it beside anything else, and cap it deliberately**: `--cpus` on the container plus
`OMP_NUM_THREADS` / `MKL_NUM_THREADS`, both of which the wrapper forwards. Treat it as exclusive
use, and confirm the machine is quiet before starting.

## 3. `ctrl` at `num_envs=64` has an UNMEASURED memory figure

`ctrl.host_profiles.v100.production.host_memory_model` gives **54.28 GiB**, and that number is
`13.57 × 4` — a linear extrapolation from a measured 16-environment peak, not a measurement. The
host has 113 GiB available and shares it.

`family.py` already refuses to pack cells against an estimate. **Measure it first, alone, watching
`free` and `nvidia-smi`**, before it runs beside anything. If the extrapolation is wrong upward,
this is the cell that OOMs the machine.

## 4. Mount paths follow `RESULT`, so a careless result path mounts a careless directory

`run_on_production_host.sh:285,297`:

```
NATIVE_OUT_HOST_DIR="${NATIVE_OUT_HOST_DIR:-$(dirname "$RESULT")/native-out-$STAMP}"
NATIVE_WORK_HOST_DIR="${NATIVE_WORK_HOST_DIR:-$(dirname "$RESULT")/native-work-$STAMP}"
```

Both are derived from `dirname "$RESULT"` and bind-mounted read-write into the container. Pass a
result path in a shared or global location and that location becomes a writable container mount.

**Give `RESULT` an absolute path inside our own directory**, and read the dry run's `mounts:`
section (`NATIVE_HOST_DRY_RUN=1`) before the real run. It prints every mount.

## 5. Places365 is ~21 GiB compressed, ~45 GiB modelled -- and the figure is an estimate

`setup/fetch_overlay_dataset.sh` fetches the **train** split — the production value, because the
overlay distribution is the mechanism for `svea`/`sgqn`/`soda`. Know the destination and confirm
the free space first. It is also a long download on a shared link.

## 6. A cell's footprint grows, and one phase allocates in a burst

Replay dominates for the eight off-policy baselines (~35.5 GiB for one 600k cell), and checkpoints
are counted three times over. Separately, a `ctrl` cell was observed requesting a transient
**8.27 GiB** VRAM allocation inside XLA's convolution autotuner, mid-run, from a code path nobody
was watching. Start-of-run headroom does not bound peak.

## 7. Use the dry run. It is free and it is the whole point

```
NATIVE_HOST_DRY_RUN=1 <all the real env> bash datasphere/native/run_on_production_host.sh ...
```

Runs every guard, the disk-headroom arithmetic, payload staging, mount assembly and environment
forwarding — then prints the exact `docker run` it would execute and exits 0 **without executing
it**. Seconds, no GPU, no container.

Until 2026-09-08 this script had never been executed anywhere; its tests all read the source rather
than run it. On its first dry run it immediately surfaced a required variable
(`NATIVE_RESULT_MIRROR`) and a real guard defect (a filesystem-id probe that succeeded with garbage
instead of failing). **Run the dry run first, every time, and read its `mounts:` and `env:` blocks
before letting it go.**
