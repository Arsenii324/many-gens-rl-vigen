# Assets and environment on a persistent host — three defects inherited from DataSphere

The wrapper was written against DataSphere, where every job got a fresh VM and nothing could
persist. On `cds2` nothing is fresh, and three of its behaviours become waste rather than necessity.

## 1. The big assets are COPIED per run, not mounted

`run_on_production_host.sh:257,260`:

```bash
cp "$RLVIGEN_ARCHIVE_HOST"   "$WORKDIR/rlvigen.tgz"      # 227 MB
cp "$PLACES365_ARCHIVE_HOST" "$WORKDIR/places365.tgz"    # ~24 GB at production
```

`WORKDIR` is a `mktemp -d`, deleted by the `EXIT` trap. So each cell copies the assets in and throws
them away.

At production Places365 is the **~24 GB train split**, not the 468 MB attest fixture. Across 36
cells that is **~864 GB of pure copy churn** on a filesystem with 325 GB free — and each copy needs
24 GB free *at that moment*, on top of the run's own footprint.

**The read-only mount mechanism already exists in the same file.** `EXTRA_MOUNT_N` does exactly
this at line 313:

```bash
DOCKER_MOUNT_ARGS+=(-v "$host_path:$container_path:ro")
```

The two large assets simply do not use it. **Fix: mount them `:ro` instead of copying.** The
download happens once into our own directory; every cell then mounts it. Read-only also means no
cell can corrupt the shared asset.

`rlvigen.tgz` at 227 MB is cheap enough that copying is survivable — but there is no reason for it
either, and mounting both is the same change.

## 2. The Python environment is rebuilt inside every container

Two `apt-get install` passes and a full `pip install` including torch, per cell, into a container
layer under `/var/lib/docker` on the shared `/`. See `13-how-the-operator-path-works.md`.

### A baked image is the textbook fix and is NOT the easiest one here

Our install is genuinely awkward: per-family requirement sets, and `ctrl`'s JAX stack conflicting
with torch's pinned cuDNN so it must exclude `torch`/`torchvision` entirely. One image cannot hold
both stacks cleanly, so "bake it" really means "bake several", plus a Dockerfile, plus a build that
writes layers to the same full disk.

### The better fit: build the environment ONCE into our own directory, from inside a container

- Run a container **once**, mounting a directory in our home, and `pip install` the environment
  into a **venv on that mounted path** rather than into the container layer.
- Every subsequent cell mounts that venv (`:ro` if practical) and runs against it.

This gets what the baked image was for, without the build:

| | |
|---|---|
| host untouched | every install happens inside a container, writing only to our own directory |
| built once | no per-cell apt/pip, no repeated multi-GB downloads |
| disk | one env on disk instead of a fresh container layer per cell |
| the gate | `gate_environment_manifest`'s "executed environment is not frozen" is answered — it is frozen because it is not rebuilt |
| per-family conflicts | solved by one venv per family, which is the natural shape anyway |

**Not implemented. Proposed only**, and it changes how every cell runs, so it belongs to the owner.

## 3. Checkpoints exist in three copies at once

`notes/RUNNING-ON-PRODUCTION-HOST.md:386`, verified:

1. the trainer writes them under `{run_dir}`;
2. `family.py retain` **copies** them into the cell output — `shutil.copy2`, not a move;
3. the closing `tar -czf` writes a third, compressed copy into `result.tgz` **while both others are
   still on disk**.

~1.32 GiB per RL-ViGen cell each, so roughly 4 GiB of the ~44 GiB a cell needs is the same
checkpoints three times over. On a host where space is the binding constraint, step 2 could be a
move rather than a copy — but only after checking what else reads the originals.

## On "does it abort on every warning?"

No, and the distinction matters. `set -euo pipefail` is set in both the wrapper and `run_probe.sh`,
so it aborts on a **non-zero exit**, not on a warning. Warnings pass through — which is correct, and
also why this project has needed explicit checks for the failures that *warn* rather than exit: the
non-fatal `safe_write`, the finite-but-saturated policy, the stall that produced no output at all.
