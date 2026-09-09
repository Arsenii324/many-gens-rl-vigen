# Running a cell on the production host

Operator runbook for `varaksin_as@cds2` (`notes/remote-infra.txt`: 16 cores, 113 GiB RAM,
2x Tesla V100-SXM2-32GB, plain SSH). The host is not behind DataSphere's job API, so `job.sh`,
`contract.py`'s submit path and every `cfg-*.yaml` are inapplicable here — those talk to
`datasphere project job execute`. What runs a cell on this host is
`datasphere/native/run_on_production_host.sh`, which invokes the same `run_probe.sh` inside the
same digest-pinned container image a DataSphere job uses.

Rationale, defect history and the decisions still awaiting the owner:
[`PRODUCTION-HOST-RATIFICATION.md`](PRODUCTION-HOST-RATIFICATION.md). Sequencing — what to run in
what order — is summarized in the arrival sequence below and derived in
[`MIGRATION-T4-TO-V100.md`](MIGRATION-T4-TO-V100.md) steps 1-8 and
[`PRODUCTION-RUNBOOK.md`](PRODUCTION-RUNBOOK.md). The companion carries the reasoning; this file
carries the executable mechanism and the host-arrival sequence.

## 0. When the production host becomes available — do this in order

This is the entry sequence for the first real host session. It is deliberately short: details of
each command are in the numbered sections below, and scientific rationale remains in the companion
surface. **Do not release the fleet until steps 1-6 pass.** Use the operational defaults already
recorded in `DECISION-SHEET.md`; an owner-ratification item is not a reason to improvise a new value
on the host, and a later change requires a new payload and a new run.

1. **Freeze and identify the inputs.** Run `production_gates.py`; require a clean tree, current
   source lock, and a freshly built payload. Verify both payload identity and evaluator binding.
   Never reuse a payload made before the last source commit. Transfer the payload, the RL-ViGen
   asset, and any explicitly mounted checkpoint; record their hashes.
2. **Prove the host boundary.** SSH to `cds2`, read `nvidia-smi` for the occupancy of **the card
   assigned to us** (8 September: `V100-1` — a free card that is not ours is still not ours),
   verify `docker run --gpus '"device=1"' <pinned-image> nvidia-smi -L` shows exactly ONE GPU,
   and check free disk against the 60-GB floor. Read occupancy with the aggregate query
   `nvidia-smi --query-gpu=...`, which does not enumerate other users' processes. Stop on any
   mismatch. A DataSphere `g1.1`
   diagnostic is not evidence that this production host is configured correctly.
3. **Prove renderer parity before training.** Use the source-locked image and `MUJOCO_GL=egl`.
   Evaluate one known checkpoint with the current evaluator on the already validated side to get
   \(R_A\), then the identical checkpoint/evaluator/container on `cds2` to get \(R_B\). Compare raw
   rendered-observation witnesses as well as returns. A container, renderer, GPU attachment, or
   evaluator mismatch stops the fleet; do not explain it away as algorithm variance.
4. **Measure the V100 resource shape.** Run the prepared CTRL 64-environment memory smoke and
   retain its `resources.json`; the current 54.28-GiB CTRL value is only an extrapolation. Measure
   enough throughput/resource data to set timeouts and decide whether any same-family packing is
   safe. Until this exists, run one cell per container and do not add `--memory`/`--cpus` caps.

   **4a. [CORRECTED 2026-09-08 — the CUDA pairing did NOT cost those cells; my own watchdog did.]**
   The two `ctrl` failures below were `NATIVE_CELL_STALLED`, and the stall was a false positive:
   Python block-buffers stdout when it is not a tty, the cell's stdout is a fifo, and the watchdog
   was reading the log's size. `runnable/ctrl/train_ppo.py` has five `print()` calls and one
   `flush=True`. `PYTHONUNBUFFERED=1` is now exported for every cell; without it the watchdog would
   have killed the 45-hour production `ctrl` cell at thirty minutes.

   The evidence that settles it: the 10k `ctrl` cell that SUCCEEDED (`bt1d8jicbkdu1jv87ogp`)
   printed the same `cuStreamGetGreenCtx` warning, the same 8.27 GiB allocator message and the same
   buffer-comparator diffs, then ran to 1851 lines. None of those is a failure mode.

   **Still worth doing, on its own merits rather than as a fix for the above: pin ctrl's CUDA
   driver and runtime together when the image is baked.** `ctrl` is the one family whose JAX stack pulls the CUDA **12.9**
   wheels; every torch family pins **12.1** (measured across 30 archives by
   `scripts/audit_environment_drift.py`, which found no other within-family drift at all). On the
   pre-production tier that landed runtime 12.9.0 on driver 12.2.0, and job
   `bt1hvkmei18hasgj5bbv` deadlocked inside cudnn convolution autotuning:

       conv_algorithm_picker.cc:770  Results mismatch between different convolution algorithms.
         This is likely a bug/unexpected loss of precision in cudnn.
       Device: NVIDIA L4   Driver: 12.2.0   Runtime: 12.9.0   cudnn: 9.25.1

   It produced no output for 30 minutes and was killed by the stall watchdog. The 10k attest cell
   succeeded on the same stack, so this is reached only at length — a 600k `ctrl` cell would meet
   it. `XLA_FLAGS=--xla_gpu_autotune_level=0` is the diagnostic workaround, **not** the fix; the
   fix is a driver the installed CUDA runtime supports, decided when the image is baked. Verify
   with `nvidia-smi` (driver) against `python -c "import jax; print(jax.devices())"` and the
   `nvidia-*` versions in `resolved_packages.json` before the first `ctrl` cell.
5. **Run the exact IBAC-SNI competence pilot.** Use the intended production settings (`procs=16`,
   Impala trunk, `beta=1e-4`, entropy `0`) and predeclared internal health/learning criteria.
   Process startup and finite loss are necessary but not sufficient. Do not tune it by comparing
   its return with another baseline after seeing results.

   **5a. READ `action_clip_rate_coordinate`, NOT `boundary_fraction`. NEW 2026-09-08.** Run
   `python scripts/read_stack_pilot.py --cell <dir>` rather than reading the log by eye. The
   102400-frame pre-production pilot (`bt1leljqi6n7osmcdb77`) passed every check that existed at
   the time and should not have: `mean_log_std` gave `sigma 1.073`, so the ANALYTIC clip rate was
   0.351 and looked healthy, while the evaluator's own measurement was **0.857 of coordinates and
   1.0000 of vectors** — every action it emitted had a coordinate outside the space, with
   `action_raw_min` at −10.43. `gaussian_boundary_fraction` assumes a zero mean and cannot see a
   mean that has run off-centre, which is what was happening.

   Context so this is not over-read: the eight squashed or clamped heads clip exactly **0.000**,
   and the four unsquashed sit at 0.24–0.44 at 10k, so substantial clipping is a property of the
   group. `ibac_sni` is the highest of the four and doubled between 10k and 102k. **The control at
   matching length does not exist yet** — no `idaac` or `ppg` run at 102400 frames — so this is a
   flag, not a verdict. If the production pilot reproduces it, A43's predeclared disambiguation
   applies: revert `lr` first, re-pilot, and revert the 2026-09-08 policy-head init alongside it,
   since that init is a fifth variable in the stack and the 10k evidence moved the clip rate the
   wrong way by 0.024.
6. **Run one staged production canary.** Prefer one DrQ-v2 seed at the full budget. Detach the
   whole wrapper with `nohup`/`tmux`; use one container; keep the host output mount. Require the
   complete chain: training, intermediate/terminal checkpoints, fresh-process reload, full
   offline grid, normalized records, and the planned statistics. Inspect disk, memory, logs,
   checkpoint hashes, and the live evaluator revision before proceeding.
7. **Recompute and release.** Update the V100 schedule with measured throughput/RAM, rerun gates,
   check the DrQ-v2 external anchor, and archive the canary manifest. Only then schedule the
   remaining fixed three-seed Door fleet. Pack cells only where the measured headroom and the
   co-scheduling rule permit it; otherwise keep one cell per container.

**Hard stop conditions:** missing or stale payload binding; unpinned/mismatched image; failed GPU
container check; insufficient disk; renderer witness mismatch; CTRL memory beyond the host margin;
IBAC failure of the predeclared competence criteria; missing checkpoint/reload/grid/records output;
or a changed source/config after the canary payload was built. Preserve the partial host output and
rerun a failed off-policy seed from zero rather than resuming it against an empty replay buffer.

## 0b. What a cell actually costs — measured end to end, 2026-09-09

The first complete production cell, `card0-20260909-035152` (`idaac-s101`, 600k frames, sharing card
0 with a `ppg` cell for its last four hours). Every figure is from the job log.

| phase | wall time | detail |
|---|---|---|
| training | **4.95 h** | 600,064 frames at 33.7 frames/s |
| curve evaluation | **4.60 h** | 11 stamps x 44 rows x 3 episodes = 1,452 episodes |
| endpoint grid | **5.52 h** | 44 rows x 20 episodes x **2 policy-mode passes** |
| **total** | **≈15 h** | evaluation is **twice** the training that precedes it |

**Budget the whole thing, not the training.** `CELL_TIMEOUT_SECONDS` wraps training only. The
allowance that covers evaluation used to default to the training budget and was **69 % short**;
`launch-card-cell.sh` now derives it from episodes actually scheduled — including
`ENDPOINT_EVAL_POLICY_MODES`, which defaults to `native,mode` and sweeps the endpoint grid **twice**
— and prints the workload before the cell starts. Read that line; a wrong number there is visible in
seconds, and the failure it prevents is not a truncated evaluation but a **lost delivery**, since
`collect_record_delivery` runs after evaluation and a reaped cell never reaches it.

**Disk, not VRAM, caps how much runs at once.** One filesystem, 278 GiB free on a 20 TB at 99 %. Two
armed disk watches left **10 GiB** of headroom, so a `drqv2` cell (27.88 GiB required, ~56 GiB
allowance) could not be co-scheduled at all. The on-policy pair packs only because neither writes a
replay buffer: ~2 GiB each after eleven hours. See
[`production-host/27-disk-not-vram-is-what-caps-parallelism.md`](production-host/27-disk-not-vram-is-what-caps-parallelism.md)
and [`production-host/28-eval-is-sixty-percent-of-a-cell.md`](production-host/28-eval-is-sixty-percent-of-a-cell.md).

**Collect with the collector, and read what it prints.**
`datasphere/native/collect-host-run.sh <family> <local-copy-of-run-dir>` now runs
`audit_record_frame_provenance.py` (refusing on a mismatch) and `audit_training_diagnostics.py`
(reporting) on every result. The second exists because both cells of 2026-09-09 produced nulls whose
cause was invisible in every artifact the pipeline checked.

## 1. Preconditions, checked on the host every time

```bash
ssh varaksin_as@cds2
cd <the repo, or wherever the payload and this script are>
bash datasphere/native/preflight_production_host.sh --cells drqv2:1 --frames 600000
```

**One command, nine checks, exit 0 only if all pass.** (Check 9, added 2026-09-08, refuses when `DOCKER_GPUS` is unset and verifies the named card has headroom.) It was a hand-run checklist until
2026-09-07, which is the wrong shape for something whose failure modes are a cell dying six hours
in — or worse, succeeding while measuring something else. It checks: the Docker daemon is reachable
*as this user* (being in the group is not the same as the daemon running); `source-lock.json` pins
an image; `docker run --gpus '"device=1"' <pinned image> nvidia-smi` actually reaches the GPU (host
`nvidia-smi` working does **not** prove this — it needs `nvidia-container-toolkit`); how many GPUs
there are and whether they are busy; that the container has outbound network, since `run_probe.sh`
bootstraps its whole environment per run; free disk against the **derived** requirement for those
exact cells; the memory model on the `v100` tier; and that the host really has the RAM that tier
assumes.

It deliberately does **not** check renderer parity. That is C95's R_A/R_B comparison against a real
checkpoint (`MIGRATION-T4-TO-V100.md` step 2) and it is a separate gate — the preflight says so on
success rather than letting a green be mistaken for one.

## 2. Build and transfer the payload

Build it locally, exactly as for any DataSphere job — do not invent a transfer path (this repo has
no configured git remote):

```bash
python datasphere/native/contract.py build-payload --source . \
    --output payload-vNNN-<family>.tgz --families <family>
python datasphere/native/contract.py verify-payload --archive payload-vNNN-<family>.tgz \
    --require-evaluator-identity
python datasphere/native/contract.py verify-evaluator-binding --archive payload-vNNN-<family>.tgz
scp payload-vNNN-<family>.tgz rlvigen-door2-90d8b8c4.tgz varaksin_as@cds2:~/
```

The payload is source only — the allowlist in `contract.py` (`BASE_ALLOWED` plus the family's
`payload_members`) rejects any path containing `results`, `logs`, `models`, `data`, `wandb`,
`.git`, `.venv`, `__pycache__`, and the names `wandb_key.txt`, `.netrc`, `id_rsa`, `id_ed25519`.
Everything third-party — apt packages, the pip environment, RL-ViGen upstream — is fetched inside
the container at run time by `run_probe.sh`, so **the host needs outbound network access**.

## 2b. Places365 — required by `svea`, `sgqn` and `soda`, by nothing else

These three overlay Places365 images as their augmentation, so the dataset is a
**learning-affecting input**, not a fixture. A22 decided the upstream **train** split.

On the host, once:

```bash
bash setup/fetch_overlay_dataset.sh /data/places365 train    # ~24 GB
PLACES365_ROOT=/data/places365 python3 setup/verify_datasets.py --split train
```

Require `dataset usable: PASS` with `class directories: 365` **before the first svea/sgqn/soda
cell**, and do it ONCE for the host rather than per cell — a million-image integrity scan on every
cell is the kind of check people switch off.

Then pass the archive as the FOURTH positional argument and name the split:

```bash
NATIVE_PLACES365_SPLIT=train PLACES365_EXPECTED_COUNT=<n> PLACES365_EXPECTED_SHA256=<sha> \
  DOCKER_GPUS='"device=1"' \
  bash datasphere/native/run_on_production_host.sh     payload.tgz result.tgz rlvigen-door2-90d8b8c4.tgz places365.tgz
```

Three things that were wrong here until 2026-09-07, so verify rather than assume if you are on an
older checkout: the wrapper passed the RL-ViGen archive in the Places365 argument slot and never
set `RLVIGEN_ARCHIVE`; `NATIVE_PLACES365_SPLIT` was not in the forwarding list, so `train` could
not be selected on the host at all; and the runner asserted the loader root equalled a hardcoded
`.../val` after configuring it for `$places_split`, so the decided production split failed its own
check.

**`places365-train-attest.tgz` is not this asset.** It is a 1000-image/20-class loader-path
attestation fixture used by the v196 wave to prove the train branch executes. It certifies the
code path, not the dataset.

## 2c. Dry-run the wrapper FIRST, before the first real cell

```bash
NATIVE_HOST_DRY_RUN=1 \
DOCKER_GPUS='"device=1"' \
FRAMES=600000 NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 \
CELL_TIMEOUT_SECONDS=170000 CELLS=drqv2:101 \
NATIVE_RESULT_MIRROR=/mnt/other-volume/rlvigen-results \
bash datasphere/native/run_on_production_host.sh payload.tgz result.tgz rlvigen.tgz places365.tgz
```

It runs every guard, every path check, the disk-headroom arithmetic, the payload staging, the mount
assembly and the environment forwarding — then prints the exact `docker run` it would execute and
exits 0 without executing it. Seconds, no GPU, no container.

**Do this before anything else on the host.** Until 2026-09-08 this script had never been executed
anywhere: its twenty-nine tests all read the source rather than run it, and with `set -euo pipefail`
and `${VAR:?}` a missing variable or a swapped positional surfaces as an abort partway through — on
the host, on the day, with the campaign waiting.

The dry run earns its keep immediately: run here for the first time it surfaced `NATIVE_RESULT_MIRROR`
as a required variable at production scale in about a second, which is the kind of thing otherwise
learned by failing.

Expect to set one of these on a host where the filesystem id cannot be read or the mirror shares a
device — both are refusals by design, and both are deviations the operator accepts explicitly rather
than the script assuming:

- `NATIVE_ACCEPT_UNVERIFIED_DEVICE=1` — the fsid could not be read, so "different device" is
  unverified. Marker: `NATIVE_RESULT_MIRROR_DEVICE_UNVERIFIED`.
- `NATIVE_ACCEPT_SAME_DEVICE=1` — verified same device. Marker:
  `NATIVE_RESULT_MIRROR_SAME_DEVICE`.

Both print a marker into the log, so a run that took either is identifiable afterwards.

## 3. Run one cell

### 3.0 On a shared card, use the launcher — added 2026-09-08

```bash
CARD=0 CELLS=idaac:101 FRAMES=10000 CELL_TIMEOUT_SECONDS=3600 \
NATIVE_VENV_HOST=$HOME/rlvigen-env/torch-<reqhash>-<digest> \
  nohup bash datasphere/native/launch-card-cell.sh payload.tgz result.tgz > run.log 2>&1 &
```

`datasphere/native/launch-card-cell.sh` does the card preflight, arms the exclusivity alarm and the
yield daemon, bounds the container with a reaper, and stands everything down. It exists because the
same sequence done by hand got the arithmetic wrong: both watches were armed for 4500 s against a
bootstrap still running at 51 minutes, so the GPU phase would have been unwatched and both watchers
would have exited 0 reporting a clean run. The launcher derives the budget from
`CELL_TIMEOUT_SECONDS + bootstrap allowance + slack`, derives the card index once instead of three
times, and passes `--must-cover-seconds` so a short watch **refuses to arm** (exit 3) instead of
arming short. Full account: `production-host/18-the-watch-that-would-have-expired-first.md`.

**Run it under `nohup`.** `run_on_production_host.sh` is foreground and blocking; SIGHUP from an SSH
drop kills it while dockerd keeps the container running, so the cell continues with nobody
retrieving its result. Verified on 2026-09-08 — an outer `timeout 5400 ssh` fired mid-bootstrap, the
script died at STEP 3, and the container ran on for hours.

### 3.0b The environment: build it once, mount it read-only

> **[Claude 2026-09-09] A PREBUILT ENVIRONMENT IS FAMILY-SPECIFIC, and its directory name does not
> say so.** `build-env.sh` bakes the `robosuite` / `robosuitevgb` editable installs only when the
> payload it was built from carries `RL-ViGen-upstream/` — and **payloads never do**, because
> `run_probe.sh` git-clones that tree at run time. The host's only prebuilt environment reads
> `"cells": "idaac:1"`, `"editable": []`, with both packages **absent**, while its directory name
> carries only the requirements hash, which is **identical for all twelve baselines**.
>
> Using it for an `rlvigen` cell would have failed *after* the import check passed, because that
> check ran with `third_party/robosuite` prepended and no `runnable/_launch/*.sh` keeps that entry.
> `run_probe.sh` now refuses with `NATIVE_EDITABLE_NOT_INSTALLED`.
>
> **Check `ENVIRONMENT.json` before reusing one**: `"editable": []` means it cannot run `rlvigen`.
> Both production cells of 2026-09-09 used `NATIVE_PIP_CACHE=1` instead, which is minutes with a
> warm cache rather than the two hours below.


Every cell otherwise rebuilds its environment inside a container that is then thrown away.
Measured here: `apt` **71 s**; `pip` **over two hours** for 1710 MB of wheels at 162–835 kB/s, the
largest ones slowest. At 10k frames the training itself is minutes, so a short cell is ~95 %
bootstrap and none of it survives.

```bash
CELLS=idaac:1 PAYLOAD=~/rlvigen-work/payload.tgz \
NATIVE_IMAGE=<the digest-pinned image from source-lock.json> \
  bash datasphere/native/build-env.sh          # once per requirement set
```

There are exactly **two** requirement sets across the twelve baselines: eleven share the torch one,
`ctrl` has the JAX one (its cuDNN 9 and torch's pinned 8.9.2.26 have no common version). So two
environments cover the fleet. Pass the built directory as `NATIVE_VENV_HOST`; it is mounted
**read-only**, which is the mechanism rather than caution — an environment a cell cannot write is
frozen by construction, which is what `gate_environment_manifest` asks for. `apt` still runs at run
time, so that is the pip half only, and the gate note says so.

Every mismatch — missing `ENVIRONMENT.json`, missing interpreter, unforwarded image digest, wrong
digest, wrong requirement hash — **refuses** with exit 3 and never falls back to `pip`. A fallback
would restore the two-hour bootstrap silently and execute an environment nobody verified. Design:
`production-host/19-environment-lifecycle-vs-run-lifecycle.md`.

Lighter alternative if you do not want a prebuilt environment:
`NATIVE_PIP_CACHE_HOST=$HOME/.cache/pip-rlvigen` persists the wheels between cells, so only the
first pays the download.

### 3.0c Rendering: the container needs `graphics`, and `--gpus` does not give it
**The container needs the `graphics` driver capability, and `--gpus` does not give it.** The wrapper now sets `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics` (override with
`NATIVE_DRIVER_CAPABILITIES`). Without it a GPU container has CUDA but no `libEGL_nvidia`, EGL
falls back to Mesa's `llvmpipe` CPU rasteriser, and every rendered observation is software-produced
— wrong pixels and far too slow. The first cell on the production host died on exactly this, after
a two-hour bootstrap, with `RuntimeError: software EGL renderer: llvmpipe`. DataSphere set the
capability for us, so it stayed invisible until the platform changed.

### 3.1 The wrapper directly

Copy the environment block verbatim from whichever `cfg-*.yaml` is the template for this cell; the
script forwards an allow-list of exactly those variables and nothing else.

```bash
CELLS=drqv2:1 FRAMES=600000 TASK=Door SEED=1 \
NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 \
SAVE_EVERY_FRAMES=50000 EVAL_EVERY_FRAMES=50000 EVAL_EPISODES=10 ENDPOINT_EVAL=1 \
DOCKER_GPUS='"device=1"' \
NATIVE_OUT_HOST_DIR=/data/runs/drqv2-s1 \
CELL_TIMEOUT_SECONDS=NNNNN \
NATIVE_RESULT_MIRROR=/mnt/other-volume/rlvigen-results \
  bash datasphere/native/run_on_production_host.sh \
    payload-vNNN-rlvigen.tgz result-drqv2-s1.tgz rlvigen-door2-90d8b8c4.tgz
```

**`NATIVE_RESULT_MIRROR` is mandatory at 600k, and it is checked rather than trusted.** Results
otherwise live on exactly one host volume; a soda cell alone is ~45 hours and the campaign is
~893 GPU-hours.

**What it does and does not protect against** (external review 27 §13 is right to insist on the
distinction). The mirror copy happens **after** the run completes, so it protects the finished
result against later loss of the primary volume. It does **not** protect a 45-hour cell against
losing that volume at hour 35. Mid-run durability comes from a different mechanism and is already
in place: `/tmp/native-out` and `/tmp/native-work` are both bind-mounted to host directories, so
checkpoints are durable on the primary volume **as they are written** rather than only when the
result is packed. Surviving loss of the primary volume mid-run would need periodic mirroring of
retained checkpoints, which is not implemented and is not claimed. The script compares the filesystem id of the mirror against the result path's
(`stat -f -c %i`) and **refuses if they match** — a copy beside the original does not survive the
failure it exists for. It also refuses if either id cannot be read, rather than assuming.

If the host genuinely has one volume, `NATIVE_ACCEPT_SAME_DEVICE=1` records the deviation
explicitly and the run proceeds; the marker `NATIVE_RESULT_MIRROR_SAME_DEVICE` then appears in the
log. Prefer a real second device, including a network mount.

After the run, look for the `mirrored:` line. If the copy fails the wrapper now **exits 4** rather
than warning: production scale refuses to start without a mirror, so a requirement whose failure is
a log line nobody greps is not a requirement. The training output is not lost — `$RESULT`,
`NATIVE_OUT_HOST_DIR` and `NATIVE_WORK_HOST_DIR` are all intact on the primary volume — but the
durability contract has failed, so the run reports incomplete and the operator decides.

`NATIVE_PRODUCTION=1` and `NATIVE_HOST_PROFILE` are **mandatory at 600k** — `run_probe.sh` refuses
without them, because `apply_production_settings` would otherwise apply nothing and train a full
run at probe-scale cadence and replay settings while looking successful. The script raises both
refusals itself, before the container bootstrap is paid for.

Extra file inputs (a checkpoint for an offline grid, a resume snapshot) are
`EXTRA_MOUNT_N=HOST_PATH:CONTAINER_PATH:ENV_VAR_NAME`, e.g.
`EXTRA_MOUNT_1=s2-snapshot-100000.pt:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT`.

**GPU pinning belongs at the Docker level.** `DOCKER_GPUS='"device=1"'` attaches exactly one card.
`CUDA_VISIBLE_DEVICES` is deliberately not forwarded: it would look like it pinned the run while
the container still had both cards attached, and a library that ignores it could still reach the
occupied GPU.

**Long runs must be detached.** `docker run` here is foreground; `dockerd` keeps the container
alive across an SSH drop but this script dies with its session before retrieving results. Wrap the
whole script, not the docker command:

```bash
nohup bash datasphere/native/run_on_production_host.sh ... > run.log 2>&1 &
```

## 3b. The per-cell wall-clock ceiling — required at production scale

`run_on_production_host.sh` REFUSES a run at `FRAMES >= 600000` unless `CELL_TIMEOUT_SECONDS` is
set. That is deliberate and it is not a value this repository can supply: it depends on the host's
measured throughput.

Why it is required rather than optional: `run_probe.sh` caps a cell only when the variable is set,
and the result archive is written **last**. So one stuck cell with no ceiling burns the job's whole
wall clock and takes down the evidence of every cell that already finished — the failure mode the
per-cell cap exists to prevent.

Derive it after step 2's throughput measurement:

```
CELL_TIMEOUT_SECONDS ~= (FRAMES / measured_frames_per_second) * headroom
```

where `headroom` covers the endpoint grid, checkpoint writes and the packaging step, not just
training. Round up: the cost of a ceiling that is too generous is a late failure; the cost of one
that is too tight is a killed cell that was working.

## 4. Packing two cells

Packing is **one container with two cells**, not two invocations:

```bash
CELLS=drqv2:1,drqv2:2 NATIVE_CONCURRENT=1 ... bash datasphere/native/run_on_production_host.sh ...
```

`run_probe.sh` runs a comma-separated `CELLS` list concurrently when `NATIVE_CONCURRENT=1` and
serially otherwise. Two separate invocations would each pay their own bootstrap, neither would see
the other's memory use, and nothing would arbitrate between them.

**Pin the cells to different GPUs, or packing buys nothing.** `NATIVE_CELL_DEVICES=0,1` makes
`run_probe.sh` round-robin `CUDA_VISIBLE_DEVICES` across the packed cells and announce each
assignment as `NATIVE_CELL_DEVICE <cell> CUDA_VISIBLE_DEVICES=<n>`. Without it every cell inherits
the same visible devices and every framework here defaults to `cuda:0`, so two packed cells land on
one card at double the memory while the other sits idle. This was invisible on DataSphere, whose
tiers have a single GPU.

Note the interaction with `DOCKER_GPUS`: that flag decides which cards the CONTAINER can see, and
`NATIVE_CELL_DEVICES` indexes within that set. Packing across both cards would need `--gpus all`
plus `NATIVE_CELL_DEVICES=0,1`; pinning the container to one card and then asking for two devices
would fail.

> **[SUPERSEDED 2026-09-08 — DO NOT PACK ACROSS BOTH CARDS.]** `cds2` is under a strict GPU
> assignment schedule and the assignment names **one card**: 8 September is `V100-1`. Card 0 is not
> ours whether or not it is idle. Two-card packing is therefore not available, and `--gpus all`
> would silently take both.
>
> **[Claude 2026-09-08] This is no longer a default.** `DOCKER_GPUS` is now mandatory — the script
> refuses with no card named, before it starts any container. `all` remains available but has to be
> typed, which is the point.
>
> **Always set `DOCKER_GPUS='"device=1"'` explicitly**, and confirm with `nvidia-smi -L` *inside*
> the container that exactly one GPU is visible. `CUDA_VISIBLE_DEVICES` is not a substitute: a
> library that ignores it still sees every attached card.
>
> See [`production-host/08-gpu-assignment-and-time.md`](production-host/08-gpu-assignment-and-time.md)
> and [`production-host/`](production-host/) in full.

Three constraints:

- **Co-scheduling.** `run_probe.sh`'s `check-co-schedulable` refuses families that cannot share one
  Python environment. `ctrl` is JAX and strips torch — `jax[cuda12]`'s cudnn 9 and torch's pinned
  cudnn 8.9.2.26 have no common version. Pack within a family, not across.
- **Headroom first.** `MIGRATION-T4-TO-V100.md` step 4 gates packing on measured peak RAM/CPU from
  step 2. The script sets no `--memory` or `--cpus`: a cap guessed before that measurement would
  convert an honest overcommit into an OOM-kill mid-run.
- **Disk doubles too, and that is now checked.** Two packed `drqv2` cells need 84 GiB against one
  cell's 44 — the replay episode files are per cell. `family.py disk-requirement --cells a:1,a:2`
  prints it and the runner refuses below it.

**No config conflation.** `family.py production_env` refuses a cell list spanning families outright
("production settings are per family and these cells span ..."), so a packed job is always one
family, whose constants are identical across its cells; only the seed differs. Each cell gets its
own output directory (`cells/<baseline>-s<seed>`), its own run directory, its own `training.log`,
`effective_config.json`, `resources.json` and records. The one genuinely shared write is
`door.xml`, which `vgb_wrapper.py:368` dumps at the process CWD on every reset — harmless, because
nothing ever reads it back (the wrapper passes the XML string in memory) and CORRECTIONS #97
removed it from the hashed evaluator closure for exactly this reason. The shared `job.log`
interleaves lines from concurrent cells; the per-cell `training.log` files do not.

## 5. Disk

**Derived per cell, not a constant.** `python3 datasphere/native/family.py disk-requirement --cells
<cells> --frames <frames>` prints the breakdown; the runner refuses a job whose target filesystem
has less (`NATIVE_DISK_FLOOR_GB` overrides with a number you have justified).

| cells at 600k, **v100 profile** | copied | mounted `:ro` |
|---|---|---|
| `drqv2:1` (any RL-ViGen five) | **48 GiB** | 48 GiB |
| `drqv2:1,drqv2:2` packed | **87 GiB** | 87 GiB |
| `rad:1` | **29 GiB** | 29 GiB |
| `soda:1` (Places365) | **74 GiB** | 29 GiB |
| `svea:1`/`sgqn:1` (Places365) | **93 GiB** | 48 GiB |
| `alda:1` | **12 GiB** | 12 GiB |
| `idaac:1`, `ppg:1` | **9 GiB** | 9 GiB |
| `ctrl:1` | **10 GiB** | 10 GiB |
| `ibac_sni:1` | **10 GiB** | 10 GiB |

**[Claude 2026-09-08] Recomputed.** The previous table predated two changes and was wrong in the
dangerous direction. The margin went 5.0 → 8.0 GiB (measured: site-packages alone is 5.8 GB), so
every row moved. And `rad` and `soda` were listed together at 26 GiB although **only `soda` opens
Places365** — `family.py::PLACES365_BASELINES` is `svea, sgqn, soda` — so that single row
understated `soda` by 45 GiB.

The right-hand column is what the same cell needs with a pre-extracted corpus bind-mounted via
`NATIVE_PLACES365_DIR_HOST`, which is the difference between 74 and 29 GiB for `soda`.

**Pass `--profile v100`.** Without it `family.py` sizes against the base profile, whose
`replay_capacity` is 300000 rather than 620000 — 28 GiB instead of 48 for `drqv2:1`.

Three terms, each from a measurement this project holds rather than an estimate:

1. **Replay episode files** dominate for the eight off-policy baselines — 35.5 GiB for an
   RL-ViGen cell at the v100 620k cap, 16.8 for `rad`/`soda`, zero for the four on-policy families.
   Written under the live run directory, never retained, gone when the run ends.
2. **Checkpoints, counted THREE times.** The trainer writes them under `{run_dir}`; `family.py
   retain` **copies** (`shutil.copy2`, not move) the retained set into the cell output; the closing
   `tar -czf` writes a third, compressed copy into `result.tgz` while both others are still on
   disk. 1.32 GiB per RL-ViGen cell each, so ~4 GiB of the 44.
3. **8 GiB of margin** (measured 2026-09-08, was a 5 GiB judgement under by ~2x) for the payload, the pip wheels, the apt packages and the extracted
   RL-ViGen tree.

**Disk pressure mid-run is loud and survivable, by design.** `runnable/_shim/safe_checkpoint.py`
checks free space before every write, prints `SAFE_CHECKPOINT_WAITING label=... free=... needed=...`
on each poll while it waits (up to `SAFE_CHECKPOINT_MAX_WAIT_SECONDS`, default 1800), and only then
prints `SAFE_CHECKPOINT_SKIPPED` and continues without that stamp. **That wait is the window in
which you can free space and lose nothing** — the run keeps training throughout. Writes are atomic
(`os.replace`), so a full disk cannot leave a truncated checkpoint. The terminal checkpoint fails
closed instead of skipping, because a cell without one is not a usable cell.

## 6. What survives an interruption — and what a checkpoint actually is

**No baseline saves its replay buffer.** For RL-ViGen this is upstream's own behaviour, not a
project choice: `_save_snapshot` is hardcoded `False` (`replay_buffer.py:94`), and `save_snapshot`
persists `['agent', 'timer', '_global_step', '_global_episode']` only
(`RL-ViGen-upstream/train.py:354`). So what a resume gives you differs by family:

<!-- BEGIN checkpoint-semantics (generated by scripts/audit_checkpoint_semantics.py) -->
| family | baselines | checkpoint contains | replay buffer | resume from a stamp |
|---|---|---|---|---|
| `rlvigen` | drqv2, svea, drq, sgqn, curl | agent (networks + optimizers), timer, _global_step, _global_episode | on disk during the run, never in the checkpoint and never retained | **NOT a full restart -- empty buffer** |
| `dmc_gb` | rad, soda | networks + optimizers | in memory only, never written | **NOT a full restart -- empty buffer** |
| `alda` | alda | networks + optimizers (sac_*_step_*.pt) | in memory at production default; optional save_buffer writes it | **NOT a full restart -- empty buffer** |
| `idaac` | idaac | [actor_critic, envs.ob_rms] | none -- on-policy | **policy + observation statistics; no optimizer/RNG state** |
| `ppg` | ppg | model<N>.jd via LogSaveHelper | none -- on-policy | **policy only; no optimizer/rollout state** |
| `ctrl` | ctrl | flax to_bytes(train_state), optax optimizer state included | none -- on-policy | **model + optimizer state; no environment/RNG state** |
| `ibac_sni` | ibac_sni | model.pt | none -- on-policy | **policy only; no optimizer/rollout state** |

| family | saves every | retains every | curve points at 600k | retained checkpoint bytes |
|---|---|---|---|---|
| `rlvigen` | 50000 | 50000 | 13 | 1.32 GiB |
| `dmc_gb` | 50000 | all stamps | 13 | 1.32 GiB |
| `alda` | 50000 | all stamps | 13 | 1.32 GiB |
| `idaac` | 50000 | all stamps | 13 | 0.06 GiB |
| `ppg` | 50000 | all stamps | 13 | 0.06 GiB |
| `ctrl` | 50000 | all stamps | 13 | 0.51 GiB |
| `ibac_sni` | 50000 | all stamps | 13 | 0.35 GiB |
<!-- END checkpoint-semantics -->

Regenerate with `python scripts/audit_checkpoint_semantics.py`; `--check` verifies this
block against `families.json` and against the source of each save site, so a clone edit
that started persisting a buffer would fail rather than silently invalidate the table.
`tests/test_checkpoint_semantics.py` runs that check.

Consequence for the nine off-policy cells: an interrupted run resumed from its last stamp is **a
different experiment** from an uninterrupted one, because the agent restarts against an empty
buffer. Rerun the seed from zero instead — which is also what `EVAL-PROTOCOL.md`'s missing-run
policy already says (rerun a crashed seed under the identical seed; no post-hoc replacement seeds).
Resume exists for on-policy families and for deliberate continuation experiments, not as crash
recovery for off-policy training.

Partial output *is* durable: the script bind-mounts the container's `/tmp/native-out` onto
`NATIVE_OUT_HOST_DIR`, so every checkpoint, `training.log` and per-cell run directory lands on host
storage as it is written. Without it, `run_probe.sh` copies nothing out until its closing
`tar -czf "$result" -C "$out" .`, and a container killed before that line loses everything. The
mount also makes `python scripts/watch_divergence.py --run <dir>` usable against a live run.

The replay episode files are **not** on that mount — they live in the container-local work
directory and are gone when the container is. That is deliberate: they are ~19 GB per cell and
nothing downstream reads them.

## 7. Checkpoint cadence and the reward curve

Saves happen every `SAVE_EVERY_FRAMES` — 50000 for all seven families — so a 600k cell writes
twelve stamps plus the endpoint. `family.py retain` then applies `preserve_snapshots`, and the
in-container curve evaluation runs against what retention kept.

**On the v100 profile every family keeps all thirteen** — twelve stamps plus the endpoint, at 50k
spacing, uniform across the fleet. `production_gates.py`'s `checkpoint cadence matches fleet` gate
pins exactly that.

Read the cadence from the **resolved v100 descriptor**, never from the base one. `rlvigen`'s base
`preserve_snapshots` is 100000 — a DataSphere container-disk decision (20.2 GiB free in that
container) — and its v100 profile overrides it to 50000 because the 113 GiB host has no such limit.
A table built from the base descriptor reports a seven-point `rlvigen` curve that production does
not produce. The generated block in §6 resolves the profile for this reason.

The cost of that uniformity is real and is the campaign's largest evaluation term: at 3 episodes ×
4 regimes × 10 scenes per stamp, `python datasphere/native/plan_production.py` computes the
trajectory grid at up to **325 GPU-h** against 601 GPU-h of training — see
`PRODUCTION-CALENDAR.md`, and note that six of twelve baselines' per-episode rates are still the
pessimistic unmeasured default rather than measurements.

The checkpoints are full training state (optimizers included, 104.1 MB for `rlvigen`) because that
is upstream's own save format; curve evaluation reads only the policy from them. Keeping the
format is a fidelity choice, and the disk cost it implies is already handled by the preserve
cadence and by `CURVE_EVAL_DISCARD_WEIGHTS=1`, which deletes each intermediate once evaluated and
leaves the terminal `snapshot.pt` untouched.

## 7b. Watching a live cell, and what runs where

**Everything below is possible only because the live run directory is mounted** (§6). Before that
the training process was sealed inside the container.

| you want | run this, on the HOST |
|---|---|
| a shell beside the training process | `docker exec -it <container> bash` — the container is named, and the name is printed at startup (`NATIVE_CONTAINER_NAME` overrides) |
| the run's own stdout | `docker logs -f <container>`, or `tail -f` the `nohup` log |
| live memory against `families.json`'s model | `docker stats <container>` |
| **divergence watch** | `python scripts/watch_divergence.py --run $NATIVE_WORK_HOST_DIR/runs/<cell>` — it reads `train.csv`, which the RL-ViGen five write in their run directory. C57's NaN run is what this exists for; it needs no container access |
| checkpoints as they appear | `ls -la $NATIVE_WORK_HOST_DIR/runs/<cell>/` |
| what the cell has retained so far | `$NATIVE_OUT_HOST_DIR/cells/<cell>/` — `training.log` from the first second, everything else after `retain` |

**`plan_production.py` is not part of a run.** It is the planner: it reads `families.json`, resolves
the host profile, and writes `production-schedule-v100.json`. Run it **before** the campaign, and
again whenever a measurement changes a descriptor — the `v100 schedule matches descriptor` gate
fails if the file and the descriptors disagree. It never touches a running job and never evaluates a
checkpoint.

**Nothing evaluates during training.** Online (training-time) evaluation is disabled for every
family that has it, and as of CORRECTIONS #99 that disable is real rather than a large cadence.
Evaluation happens after training within the same cell, in this order: `retain` → `check-finite` →
curve grid over the retained stamps → endpoint grid. So the GPU time an evaluation costs is
sequential with training, never concurrent with it, and the curve grid's cost is the one in
`PRODUCTION-CALENDAR.md` — for the fast families it can exceed their training time, which is why
the six unmeasured per-episode rates matter.

## 8. Retrieve and process

`result.tgz` lands at `$2`; `records.jsonl` beside it; the live run directory stays at
`NATIVE_OUT_HOST_DIR`. The archive shape is identical to a DataSphere job's by construction, so
process it the way `job.sh diagnose` does internally. Weights stay on the host: C95 forbids
evaluating a container-trained checkpoint on the laptop, since the renderer differs (EGL there,
glfw here). Records travel; weights do not.

## What this does NOT establish

- **Never executed on `cds2`.** No SSH access from the session that wrote it. Every command is
  derived from `run_probe.sh`'s own exercised contract and ordinary `docker run` semantics.
- **Outbound network access, Docker, and NVIDIA Container Toolkit on the host are assumed** — §1's
  checks are how you find out, and they have not been run.
- **Free disk on the host is unknown**, so §5's floor has never been checked against reality.
- **Concurrent use of the host is the owner's to arbitrate.** This script reserves nothing.

## Recording an attempt that failed before it wrote anything

`scripts/audit_attempt_ledger.py --strict` is a gating audit (`production_gates.py`). It refuses
exactly one situation: a config submitted more than once where an **earlier** attempt's outcome
cannot be read off disk. That is the shape of "a rerun silently replaced a failed seed", and it is
the thing that must not be discovered after the results are written.

Everything it reports is derived from artifacts — the records filename carries the job id, and
`evaluator_revision`, `record_delivery` and `execution_kind` carry the rest. Nothing is maintained
by hand, because a ledger the runner must remember to update will be wrong in the direction of
looking complete.

The one exception is a job that **failed before writing records**: it leaves no artifact saying so,
so nothing can derive its state, and without an escape the gate would stay red with no way to clear
it. Record it explicitly:

```json
// results/attempt-outcomes.json
{"bt1abc...": {"state": "FAILED-TRAIN", "reason": "OOM at 40k, log line 812"}}
```

`state` must be one of `FAILED-TRAIN`, `FAILED-EVAL`, `CANCELLED`, `SUPERSEDED-BEFORE-RUN`, and a
`reason` is required. **`ELIGIBLE` is deliberately not accepted** — a reported number must come from
records, never from an assertion. Every recorded entry is printed in full on every run, so using
the escape is visible rather than quiet.

The attempt that is *currently running* is never flagged; only a predecessor's unknown outcome
blocks. Otherwise the gate would be red for the whole duration of every wave.

## Tier concurrency is a measured limit, not an assumption

The DataSphere `gt4i.1` tier refuses the **eighth** concurrent job. Measured on 2026-09-08: the
twelve-cell v197 wave put nine cells on that tier, seven started, and the eighth and ninth went to
ERROR in 4 and 2 seconds — before any container existed, so there is no stdout to diagnose and
`job.sh diagnose` reports "no stdout.log downloaded".

Two consequences for anyone submitting a batch:

- **A returned job id is not a started job.** `job.sh submit` reports an id for a job that is
  created and then refused. Check status a minute after a batch; an ERROR with a sub-10-second
  runtime and no log is this, not a code fault.
- **Do not plan a fan-out wider than the tier accepts.** `plan_production.py` does not model tier
  concurrency. Stage submissions, or expect to lose the tail silently.

This is the pre-production tier. The production V100 host is a different machine with its own
limits, and its concurrency is governed by `NATIVE_CELL_DEVICES` and the GPU count instead — see
the packing refusal above, which fails closed for the same reason.

