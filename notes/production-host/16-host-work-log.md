# Work log — what was actually run on `cds2`, and what it cost

Every command below was run on 2026-09-08 and is reproducible. This exists so the next session
does not rediscover the shape of this by trial, and so anyone auditing what we did on a communal
machine can read it in one place rather than reconstructing it from a transcript.

**The rule this log records adherence to:** nothing runs outside a container except small
python-unrelated actions (`mkdir`, `df`, `du`, `stat`), a `git clone`, and docker itself.

## What exists on the host because of us

| thing | size | note |
|---|---|---|
| `~/rlvigen-work/` | ~1.5 GB | our directory, the only mount any container gets |
| `~/rlvigen-work/repo` | 156 MB + 860 MB reconstructed | clone plus `bootstrap_sources.py` output |
| `~/rlvigen-work/payload-host-test.tgz` | 249 KB | built and verified in a container |
| `~/rlvigen-work/runs/`, `mirror/` | ~0 | dry-run artefacts |
| docker image `ubuntu:24.04` | ~78 MB | **pulled by us**; `docker images ubuntu` was empty beforehand |
| docker image `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b…` | ~2 GB | the pinned production image |

`/` went **325 G → 321 G free**. Nothing else on the host was created, modified or deleted. No
apt, pip, conda or driver operation touched the host system — every `apt-get`/`pip install` ran
inside a `--rm` container whose writable layer was discarded on exit.

## The one host-side write

`mkdir -p ~/rlvigen-work`. That is the complete list. It could be avoided by letting `docker run -v`
create the directory, but it would then be root-owned.

## Recipes that worked

**Every container follows this shape.** No `--gpus` unless the step needs a GPU; only our own
directory mounted; `--rm`; `chown` back at the end because the container runs as root and would
otherwise leave root-owned files in our home.

```bash
docker run --rm --name rlvigen-<what> \
  -v "$HOME/rlvigen-work:/work" -w /work/repo \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  ubuntu:24.04 bash -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq git python3 ca-certificates >/dev/null 2>&1
    ...
    chown -R $HOST_UID:$HOST_GID /work'
```

**Nested git repositories need `safe.directory` — all nine of them.** After the `chown`, a root
process inside the container no longer owns the tree, so git refuses with
`detected dubious ownership`. `repo` alone is not enough: `RL-ViGen-upstream`, `ext/baselines` and
six `runnable/*` are each their own repository.

```bash
find /work/repo -maxdepth 3 -name .git -printf '%h\n' | while read -r d; do
  git config --global --add safe.directory "$d"
done
```

**Reconstructing the sources** (~860 MB, seven shallow pinned clones):

```bash
python3 setup/bootstrap_sources.py && python3 setup/verify_sources.py
```

`_publish` refuses to overwrite an existing destination, so this is safe to re-run but will not
repair a half-finished tree — remove the partial destination deliberately first.

**Passing a local file in without an out-of-container copy**: base64 into an environment variable
and decode inside. Used for diagnostic scripts and for the manifest during the repin.

```bash
B64=$(base64 < local.py | tr -d '\n')
docker run --rm ... -e CHK="$B64" <image> bash -c 'echo "$CHK" | base64 -d > /tmp/chk.py; python3 /tmp/chk.py'
```

**Reading host state** (all read-only, no directory traversal outside our own):
`df -hT`, `df -h /`, `free -g`, `nvidia-smi --query-gpu=... --format=csv,noheader`,
`docker ps --filter name=rlvigen-`, `docker images`, `docker system df`, `du -sh ~/rlvigen-work`.
**`du` is only ever pointed at our own directory** — walking anything else is the probing
`05-privacy-and-non-alarm.md` forbids. `df` reads mount metadata and is the right tool for
capacity.

## Mistakes made here, so they are not repeated

- **`cmd | tail` discards the command's exit status.** Committed three times in one session:
  `verify-payload --expect` printed a refusal and reported `exit=0` (real status **4**);
  `bootstrap_sources.py` errored under a `tail` and the ssh reported 0; `pip3 install | tail -1`
  hid an install failure that surfaced later as `ModuleNotFoundError: No module named 'numpy'`.
  Capture first, filter second, or use `set -o pipefail`.
- **Order diagnostics so the dependency-free part runs first.** A missing `numpy` cost a whole
  container round-trip that a source-level `grep` answered on its own.
- **`ubuntu:24.04` was an avoidable pull.** `python:3.11-slim` (124 MB) and `alpine` were already
  on the host and would have done the clone and bootstrap. Check `docker images` before pulling.
- **`pip install --break-system-packages`** is used inside containers. It is safe *only* because
  the container is `--rm` and the host's python is never touched. Never let that flag near a host.

## Before any GPU step — the contention arithmetic, stated rather than assumed

This is the part that has **not** been executed, and the reason is resource contention, not
missing code.

**RAM.** Host has 125 GB total, ~111 available. Per-cell worker-resident replay at the **v100**
profile is `replay_capacity` 620000 × 63,504 B = **36.7 GiB** for one rlvigen cell, plus its
~3.3 GiB fixed peak. `ctrl` at v100 is modelled at **54.28 GiB — and that figure is
`13.57 × 4`, an extrapolation from 16 environments to 64, not a measurement.** `check_memory`
gates against `usable = {"v100": 100.0}`, i.e. it assumes 13 GiB is enough for the OS, the page
cache and **every other user on a ~20-user machine**. That reserve is a judgement, not a
measurement. Two cells packed, or one `ctrl` cell whose real peak exceeds its extrapolation, is
how we would evict someone else's process.

**VRAM.** Card 1 held **17268 MiB at 0% utilisation** all day — allocated, not computing, and not
ours to clear. 15500 MiB remain. No production-geometry VRAM peak has ever been measured; the
figures we have (`sgqn` 7142 MiB the largest) come from smaller budgets on different hardware and
must not be scaled. CUDA peaks are transient and land at loading, epoch switches and batch
accumulation — not at the steady-state level a glance at `nvidia-smi` shows.

**Disk.** `/` is one filesystem at 99% with 321 GB free, shared. It carries `/home`,
`/var/lib/docker` and `/tmp` alike. There is no second filesystem with 20 GB free, so there is no
durable second location on this host at all.

**The conclusion this arithmetic forces:** do not start a GPU cell while card 1 is occupied by
another process, and do not pack two cells without a measured peak for each at production
geometry. An upper bound we cannot state is a reason not to run
(`10-resource-upper-bound-rule.md`), and every quantity above is either extrapolated, unmeasured,
or someone else's.

## Measured: what the environment build actually costs on disk

Run 2026-09-08 in the **pinned production image** on cds2, installing `requirements-native.txt`.
No GPU flag. `--rm`, so everything below was freed on exit — `/` went 321 G → 318 G during the
install and back to 321 G after.

```
site-packages                 5.8 GB
  nvidia (CUDA runtime)       2.8 GB
  torch                       1.6 GB
  triton                      420 MB
  llvmlite                    129 MB
  scipy 97M, cv2 79M + opencv_python.libs 90M, imageio_ffmpeg 71M, sympy 57M, dm_control 57M
/root/.cache/pip              3.0 GB
apt (python3, python3-pip, git)  ~0.3 GB
```

**This replaced a guess with a number and the guess was wrong.** `disk_requirement_gib`'s
`margin` was a flat **5.0 GiB** covering the payload, the pip wheels, the apt packages *and*
RL-ViGen's extracted tree. Measured steady cost is **~7.3 GB** (5.8 site-packages + 1.1 RL-ViGen
archive-plus-tree + ~0.3 apt), and the peak was **~10.3 GB** with pip's cache. The margin is now
**8.0 GiB**, and `run_probe.sh` passes `--no-cache-dir`, which removes 3.0 GB from every cell's
peak — the cache buys nothing in a layer `docker run --rm` discards.

Why this mattered: `/var/lib/docker` has **no separate mount** on cds2, so the container's writable
layer competes for the same `/dev/sda2` that `check_disk` reads. And `check_disk` runs on the host
*before* `docker run`, so it has to anticipate a layer that does not exist yet. Under-counting it
is the one direction that ends with a full shared root filesystem.

**What this measurement does NOT cover:** one requirement set in one image. `ctrl` pulls its own
JAX/CUDA stack, excluded from the torch base, and was not measured here. Per-family extras remain
unmeasured, and `check_disk`'s refusal is what stands between that and the disk.
