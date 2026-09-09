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

**VRAM.** Card 1 held **17268 MiB at 0% utilisation** in the morning; by 17:02 a different job was
resident at **14501 MiB and computing at 88% mean over a 30-minute window**. Neither is ours to
clear, and the second is the one that matters: the binding constraints turned out to be SMs and
POWER (260–282 W against a 300 W limit), not memory. Original note follows — allocated, not computing, and not
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


## Observing the cards: what runs, and the one deliberate exception

`scripts/watch_gpu_headroom.py` has two modes and they are kept apart on purpose.

**`--preflight --device N`** is a **verdict** — a non-zero exit, so a launch can be gated on it
rather than on a person reading a number. It refuses on two separate grounds: free memory below
what the run needs (a correctness limit) and high utilisation with another process present (a
**courtesy** limit, overridable with `--max-util 100` once the owner has said that slowing a
co-tenant is acceptable). It takes one card, because a verdict about two cards answers no question
anyone asked.

**`--watch --device 0,1|all`** is a **description**, and must not fail merely because a neighbour
is busy. It is **bounded and self-terminating**, never a daemon: a long-lived watcher on a communal
host is a process someone else has to wonder about and one we would forget.

**What it refuses to collect.** `nvidia-smi --query-compute-apps` will hand over other users' PIDs
and their per-process memory. Alerting on that is profiling a colleague's work, which
`05-privacy-and-non-alarm.md` forbids. It reads the card's aggregate memory and utilisation plus
the **count** of compute processes — enough to answer "is the card busy, is there room" without
answering "who, and what". Our own usage is attributable from our own archives, which is
`measure_vram_bounds.py`'s job.

**The exception, recorded so nobody finds it later and assumes the worst.** A container can only
read a device attached to it, so watching both cards means **`--gpus all` on the observer**. That
is the flag this project otherwise refuses outright. It is acceptable for this one container
because the process demonstrably cannot consume a GPU — it shells out to `nvidia-smi` and sleeps,
creating no CUDA context and running no kernel. The container is named `rlvigen-cardwatch-both` so
an auditor can see what it is. **Anything that could allocate still names exactly one card**, and
`run_on_production_host.sh` still refuses an unnamed one.

**Device numbering.** With `--gpus '"device=1"'` the pinned HOST card 1 appears as **index 0**
inside the container, and `nvidia-smi -L | grep -c '^GPU '` returns 1 — that count is the check
that the pin worked. With `--gpus all` the indices match the host's.


## `host-run.sh` and the helper container — the two tools no document mentioned

Both were written on 2026-09-08 and neither appeared in any `.md` until now, which is how a tool
that exists to prevent a class of mistake gets bypassed by the person about to make it.

**`datasphere/native/host-run.sh`** runs a script inside a container with no quoting hazards. The
body is base64-encoded into an environment variable and decoded inside, so the host shell, ssh and
`bash -c` never interpret it — a script full of backticks, `$(...)`, quotes and semicolons runs
exactly as written. It also enforces, in one place: `--rm` always, the mount must be under `$HOME`,
no GPU unless named (`-g none` omits `--gpus` entirely, since `--gpus none` is invalid docker), a
`chown` back to the caller, and **the exit status is the container's, never a pipe's**.

```bash
bash datasphere/native/host-run.sh -n <name> [-g '"device=1"'] [-m DIR] [-r] [-d] <script>
echo 'du -sh /work' | bash datasphere/native/host-run.sh -      # or from stdin
```

The "Recipes that worked" section above documents hand-rolling `ssh host "docker run ... bash -c
'...'"` with three levels of nesting. That is what this replaces, and the mistakes it lists are the
ones it prevents.

**`NATIVE_HELPER_IMAGE`** (default `python:3.11-slim`) is how `run_on_production_host.sh` and
`preflight_production_host.sh` do every JSON read and every computation, because the production
host permits nothing but small python-unrelated actions and docker itself outside a container. Two
consequences worth knowing before a first run on a new machine: that image must be pullable (it was
already present on cds2, so it cost nothing there), and **anything the helper needs must be passed
as a flag, not inherited** — it receives no environment. That is not hypothetical: `check_disk`
lost `NATIVE_HOST_PROFILE` exactly this way and sized a v100 run against the base profile, 28 GiB
demanded against 48 needed, until `--profile` was passed explicitly.

## A clone edit invalidates every existing checkout, not just the repo

Editing a `runnable/<family>` tree changes two things a host cannot infer: the family's
`expected_tree_hash` in `setup/source-reconstruction.json`, and its evaluator revision.

**A `git pull` does not fix the host.** `runnable/*` is gitignored — the trees are *reconstructed*,
not tracked — so pulling brings the new manifest while leaving the old tree in place, and
`verify_sources.py` then fails with `source closure hash mismatch`. Observed exactly that on
2026-09-08 after the Places365 worker fix: the host tree hashed to `1cc5640c…` against a manifest
expecting `faee77f4…`.

The fix, per family, and it is safe by construction — the target is a reconstructed tree,
gitignored, rebuildable from the pinned commit plus the patch, by the same tool that made it:

```bash
rm -rf runnable/dmc_gb
python3 setup/bootstrap_sources.py --family dmc_gb    # --family exists; without it, _publish
python3 setup/verify_sources.py                       # refuses every already-present destination
```

`_publish` refuses to overwrite an existing destination, so the removal is required rather than
optional, and running bootstrap without `--family` on a populated tree errors on the first one.

**Passing a script to the host without quoting hell.** `host-run.sh` base64-encodes the body, which
solves the container side. The remaining hazard is getting the file *to* the host: a heredoc nested
inside `ssh '...'` breaks the moment the script contains a single quote — it happened here, on a
`python3 -c "...json.load(open('...'))..."` line, and `set -e` aborted before the `rm` ran. Send the
file over stdin instead, which interprets nothing:

```bash
ssh HOST "cat > /tmp/script.sh" < local_script.sh
ssh HOST 'bash ~/rlvigen-work/host-run.sh -n name /tmp/script.sh'
```


## 2026-09-08 evening — launching a cell on a shared card, and what went wrong

**Launch, in one command, detached.** Everything below is what `launch-card-cell.sh` now does, and
the reason it exists is that doing it by hand got the arithmetic wrong.

```bash
CARD=0 CELLS=idaac:101 FRAMES=10000 CELL_TIMEOUT_SECONDS=3600 \
  nohup bash datasphere/native/launch-card-cell.sh payload.tgz result.tgz > run.log 2>&1 &
```

**Methods that worked and are worth repeating:**

- **`docker exec` into our own container is the honest progress signal**, not `docker logs`. `pip`
  detects a non-tty and prints only *completed* progress bars, so the log's last bar belongs to the
  previous wheel and looks frozen for an hour. Use instead:
  `docker exec C sh -c "cat /proc/net/dev"` twice, 30 s apart — that showed 126 kB/s and settled
  whether pip was alive. `docker ps -s` layer growth works as a cross-check.
- **Redirect long host commands to a file on the host and read it back.** `ssh HOST 'cmd | tail'`
  under an outer `timeout` returns nothing at all: `tail` buffers and the kill discards it. Use
  `nohup cmd > /tmp/x.log 2>&1 &` then read `/tmp/x.log`.
- **The bind mounts are what make a failure diagnosable.** The cell container is `--rm`; it was
  gone before I looked at it. Everything I learned came from `$W/native-out/job.log` and
  `resolved_packages.json` on the host.

**Traps hit, so the next session does not:**

- `ssh ... | grep -v WARNING` makes `$?` the grep's. An `scp` that printed `rc=1` had in fact
  succeeded. Capture first, filter second.
- A watcher container started with `docker run -d` **survives an SSH drop**; the foreground wrapper
  does not. So an SSH timeout leaves watchers running and the cell unsupervised — the opposite of
  what you would guess.
- Files a container writes to a bind mount are **root-owned**, and the host user cannot delete them.
  `build-env.sh` now `chown`s its output back to the invoking UID for this reason; found when the
  smoke test could not clean up after itself.


## 2026-09-09 — a neighbour took card 0 mid-plan, and what that exercised

The preflight refused, in production, on a real co-tenant rather than a test:

```
card 0: 16155 MiB used, 16340 MiB free, 100% util, 1 compute process(es)
REFUSING: the card is at 100% with another process on it.
ABORTING: preflight refused the card.
```

The launcher stood everything down (`no watcher leaked`) and nothing of ours touched the card. That
is the first time the co-tenancy guard has fired against somebody else's actual job.

**Then the card freed, and I relaunched on a single reading.** That was hasty, and the preflight's
own text says why: *"A single reading is a snapshot, not a bound."* A job that ran once can run
again. What makes relaunching defensible is not the reading; it is that the yield daemon is armed
with `baseline: 0 compute process(es)` and *"will yield if a process appears beyond ours"*, so a
returning neighbour stops our cell automatically — during bootstrap the exclusivity watch also
alarms, because a process on the card while our `cell-active` marker is absent is by construction
not ours. **Verify that the daemon is armed before relying on it**; do not rely on the free reading.

**On attributing the neighbour.** `docker ps` names are visible to everyone on the daemon, and
`rl4vla_cudagl_gpu1` is explicitly named for GPU 1 while an unsuffixed `rl4vla_cudagl` also exists.
That is inference from a public listing, not identification. Mapping a GPU process to a container
needs PID inspection of another user's work, which is not ours to do, so the neighbour stays
unattributed. Worth knowing: `gpu-stats-main-gpu-stats-1` runs on this box, so somebody is
recording GPU usage independently of us.

**Latent bug found while waiting:** `NATIVE_PIP_CACHE` printed "wheels persist across cells" through
two complete installs while the host cache stayed at 4.0K. pip in this image reports *"cache
commands can not function since cache is disabled"*, so merely omitting `--no-cache-dir` does
nothing; `--cache-dir` must be passed explicitly. A feature that reports success while doing
nothing — the exact defect class this workspace exists to refuse, shipped by me the same day.


## 2026-09-09 — the production launch recipe that actually works

Getting one production cell onto card 0 took six attempts, and every failure was a guard doing its
job. Recorded in order, because the next person will hit them in the same order.

```bash
cd ~/rlvigen-work/repo && git pull --ff-only origin main

# 1. Payload from the CURRENT tree. A repo fix is not a payload fix: run_probe.sh executes from
#    inside the payload, so an edit committed five minutes ago is absent until you rebuild.
docker run --rm -v "$PWD:/repo" -v ~/rlvigen-work:/out -w /repo python:3.11-slim \
  python3 datasphere/native/contract.py build-payload --source . --output /out/payload.tgz --families idaac
docker run --rm -v "$PWD:/repo:ro" -v ~/rlvigen-work:/out:ro -w /repo python:3.11-slim \
  python3 datasphere/native/contract.py verify-payload --archive /out/payload.tgz \
    --require-runner-contract 19 --require-families idaac --require-evaluator-identity

# 2. Launch. `env` explicitly rather than relying on an exported shell variable -- a sourced
#    NATIVE_ACCEPT_SAME_DEVICE did not reach the wrapper once and cost a run.
nohup env NATIVE_ACCEPT_SAME_DEVICE=1 NATIVE_ACCEPT_UNVERIFIED_DEVICE=1 \
  CARD=0 CELLS=idaac:101 FRAMES=600000 NATIVE_PRODUCTION=1 \
  CELL_TIMEOUT_SECONDS=43200 NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB=4096 \
  NATIVE_RESULT_MIRROR=$HOME/rlvigen-mirror SAVE_EVERY_FRAMES=50000 EVAL_EVERY_FRAMES=50000 \
  ENDPOINT_EVAL=1 \
  bash datasphere/native/launch-card-cell.sh ~/rlvigen-work/payload.tgz ~/rlvigen-runs/result.tgz \
  > /tmp/run.log 2>&1 &
```

### The four guards that will stop you, in the order they fire

| guard | what it says | what it means |
|---|---|---|
| result mirror | `NATIVE_RESULT_MIRROR is on the SAME filesystem` | this host has one filesystem; pass `NATIVE_ACCEPT_SAME_DEVICE=1` **via `env`**, and know the mirror buys a second copy, not a second failure domain |
| production freeze | `NATIVE_PRODUCTION_CONFLICT ENDPOINT_EVAL_REGIMES=train,eval-easy expected=train,eval-easy,eval-medium,eval-hard` | do NOT carry a smoke config's eval overrides into production. Delete `ENDPOINT_EVAL_REGIMES`, `ENDPOINT_EVAL_SCENES`, `ENDPOINT_EVAL_EPISODES` and let the production defaults apply |
| VRAM cap | `NATIVE_VRAM_CAP_NOT_IN_FORCE` | the cap could not be loaded. Refuses in ~8 minutes rather than after 12 hours |
| memory floor | `free memory NNNN MiB is below the 4000 MiB floor` | something — possibly us — is filling the card. Two packed cells at 600k did exactly this |

### Sizing the cap, which is the part that is easy to get wrong

`NATIVE_VRAM_CAP_MIB` is enforced **per process**, and a cell runs about **three** processes
(measured: 2019 + 308 + 308 MiB for a solo `idaac`; two packed cells produced six). So the run
budget is `cap x 3`, not `cap`. A 10240 cap on a packed pair permitted 61 GiB on a 32 GiB card and
took 92% of it before the floor stopped us. **4096 for a solo cell** leaves the card mostly free.

### What a healthy production cell looks like

```
NATIVE_VRAM_CAP_IN_FORCE 4096 MiB, sitecustomize resolves
NATIVE_PRODUCTION_SET CURVE_EVAL_SCENES=0,1,2,3,4,5,6,7,8,9
NATIVE_PRODUCTION_SET ENDPOINT_EVAL_EPISODES=20
card 0: 2639 MiB, 7%, 3 compute processes
/work: 286.5 GiB free (floor 255.0); 8.2 GiB consumed since arm
```
