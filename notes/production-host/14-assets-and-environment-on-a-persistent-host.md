# Assets and environment on a persistent host — what is transient, what accumulates

The wrapper was written against DataSphere, where every job got a fresh VM and nothing could
persist. On `cds2` nothing is fresh. This page separates the parts of that inheritance that are
merely wasteful from the one that was a genuine hazard, because the first version of this page
conflated them and overstated the danger.

**The correction, stated first.** Almost everything this script writes is *transient*:
`docker run --rm` (line 394 — verified) frees the container's writable layer at exit, so the
`pip install` disappears with the container; and the `EXIT` trap on `WORKDIR` removes the staged
asset copies, on a crash as well as on success. Neither accumulates. The earlier framing of
"~864 GB against 325 GB free" was **write volume over the campaign, not space held at once** — a
cost in time and I/O, not a disk that fills up. Only §0 below was a real correctness problem, and
it is now fixed.

## 0. The staging directory was on a filesystem nobody checked — FIXED 2026-09-08

`WORKDIR` was `mktemp -d`, i.e. `$TMPDIR`, in practice `/tmp`. The Places365 archive is copied
into it. `check_disk` was called on `$NATIVE_WORK_HOST_DIR` **and on nothing else**, so the mount
receiving the single largest write this script makes was never checked at all.

The sharp end of that: **`/tmp` is `tmpfs` on many Linux hosts, and `tmpfs` is RAM.** A ~21 GiB
archive copy into `tmpfs` is a ~21 GiB host memory allocation. It does not fill a disk and it does
not fail cleanly — it evicts other users' processes, which is the one outcome the rules on this
host forbid outright.

Fixed in `run_on_production_host.sh`: the staging directory now defaults beside `$RESULT`, on the
filesystem `check_disk` validates; `NATIVE_WORKDIR_PARENT` overrides it; `check_disk` is now
called on it; and a `tmpfs`/`ramfs` staging directory is refused with exit 4 rather than
discovered later as somebody else's OOM kill. Verified by `NATIVE_HOST_DRY_RUN=1`.

## 1. The big assets are COPIED per run, not mounted — waste, not hazard

`run_on_production_host.sh` (post-fix line numbers shift; the two `cp` calls are unchanged):

```bash
cp "$RLVIGEN_ARCHIVE_HOST"   "$WORKDIR/rlvigen.tgz"      # 227 MB
cp "$PLACES365_ARCHIVE_HOST" "$WORKDIR/places365.tgz"    # ~21 GiB compressed at production
```

`family.py:417` charges `PLACES365_TRAIN_GIB = 45.0` per cell — ~21 GiB compressed archive plus the
expanded ~1.8M-image tree, roughly the same again. **That is a labelled estimate from DMC-GB's
published asset size, not a measurement**, and the first host provisioning should replace it.

Each copy is deleted by the `EXIT` trap, so the *space* cost is one copy at a time, and the disk
check now covers it. What remains is real but ordinary: ~21 GiB read + written per overlay cell,
nine such cells, for a file that never changes.

**The read-only mount mechanism already exists in the same file** (`EXTRA_MOUNT_N`):

```bash
DOCKER_MOUNT_ARGS+=(-v "$host_path:$container_path:ro")
```

The two large assets simply do not use it. **Fix: mount them `:ro` instead of copying.** The
download happens once into our own directory; every cell then mounts it. Read-only also means no
cell can corrupt the shared asset. `rlvigen.tgz` at 227 MB is cheap enough that copying is
survivable, but mounting both is the same change.

## 1b. What DOES accumulate, and it is deliberate

`native-out-<stamp>` and `native-work-<stamp>` are created per run beside the result and are
**never removed** — that is their purpose, since a killed container's partial run must survive the
`EXIT` trap. An off-policy cell's `native-work` holds ~18 GiB of replay episode files. Thirty-six
cells leave thirty-six pairs.

`check_disk` does bound the consequence: it reads real free space, so leftovers make the *next*
run refuse rather than overflow. But a refusal at run 20 means runs 1–19 already consumed a shared
disk. The script now **reports** existing leftovers with `du -sh` before every run and says they
are the operator's to collect. It does not delete them — nothing here has proof that a given
directory is finished with, and one of them may belong to a run still executing.

## 2. The Python environment is rebuilt inside every container

Two `apt-get install` passes and a full `pip install` including torch, per cell, into the
container's writable layer. See `13-how-the-operator-path-works.md`.

**This one is self-cleaning and the earlier page was wrong to imply otherwise.** `docker run --rm`
frees that layer when the container exits, so nothing is left under `/var/lib/docker` afterwards.
The cost is a **transient** peak (a few GB while the container lives), ~600 s of wall clock per
cell, and a repeated multi-GB download — pip's HTTP cache lives in the same discarded layer, so
torch is fetched again every single cell. That is bandwidth and time on a shared network, which is
worth removing, but it is not a disk that fills up.


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

`family.py` charges all three (`checkpoints_written` + `checkpoints_retained_copy` + `archive`),
so the triple copy is already in the requirement rather than a hidden overrun. Step 2 could be a
move rather than a copy — but only after checking what else reads the originals.

### Where a cell's disk actually goes — computed, not quoted

Per cell, at the production frame budget. **Run it in a container, not on the host** — nothing but
small python-unrelated actions and docker itself may run outside one, and the wrapper itself was
changed on 2026-09-08 to obey that:

```
docker run --rm -v "$PWD:/repo:ro" -w /repo python:3.11-slim \
  python3 datasphere/native/family.py disk-requirement --cells <cell> --frames 600000
```


| cell | replay | checkpoints ×3 | Places365 | total | +5 GiB margin |
|---|---:|---:|---:|---:|---:|
| soda | 16.76 | 3.96 | 45.00 | 65.73 | 70.73 |
| svea / sgqn | 17.74 | 2.13 | 45.00 | 64.88 | 69.88 |
| rad | 16.76 | 3.96 | 0 | 20.73 | 25.73 |
| drqv2 / curl / drq | 17.74 | 2.13 | 0 | 19.88 | 24.88 |
| alda | 0 | 3.96 | 0 | 3.96 | 8.96 |
| idaac / ppg / ibac_sni / ctrl | 0 | 1.52 | 0 | 1.52 | 6.52 |

Two things this table settles. **Replay dominates every off-policy cell** — ~17 GiB of retained
transitions at 63,504 B each (one 84×84×9 `uint8` observation), which is why "checkpoints are only
4 GiB" and "a cell needs ~44 GiB" were never in tension. And **Places365 is the single largest
term wherever it appears**, larger than everything else in the cell combined, which is what makes
mounting it once instead of copying it nine times the change worth making.

Sequential execution with one cell at a time peaks at **70.73 GiB**. Nothing about the campaign
needs 325 GB at once — but nothing enforces sequential execution either, and two overlay cells
packed together would need ~141 GiB before either has trained a step.

## On "does it abort on every warning?"

No, and the distinction matters. `set -euo pipefail` is set in both the wrapper and `run_probe.sh`,
so it aborts on a **non-zero exit**, not on a warning. Warnings pass through — which is correct, and
also why this project has needed explicit checks for the failures that *warn* rather than exit: the
non-fatal `safe_write`, the finite-but-saturated policy, the stall that produced no output at all.
