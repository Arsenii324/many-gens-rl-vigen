# Running a cell on the production host

> **This is the operator's guide. Read §0 first; it is the arrival sequence.**
>
> §0-§8 are the mechanism and were written before the host was reachable. **§9 is the campaign
> layer** added 2026-09-16: who else is on the cards, the convenience wrappers above
> `launch-card-cell.sh`, the measured GPU-memory table, the stop mechanisms, monitoring, and the
> steps that turn a collected cell into a result.
>
> Two sections were corrected on 2026-09-16 because they had become false: "What this does NOT
> establish" still said the host had never been used, and the packing note still said the booking
> named one card. Both are marked in place.
>
> `python scripts/operator_readiness.py` checks that every operator need still routes somewhere in
> here, and that each live script's real interface is documented. Run it after changing a script.

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

## 0a. The model, and the words — read this before §0

Everything below §0 uses these words as technical terms. They are defined here because the rest of
the file assumes them, and because two of them (a *cell*, a *closure*) mean something narrower than
their ordinary sense.

### What the campaign is

Twelve **baselines** — twelve published RL methods — each trained on the **Door** task of RL-ViGen
for 600,000 frames, at **three seeds**, and each evaluated on the same grid so the numbers land on
one axis. That is 36 **cells**. The point is not any single score; it is that the twelve are
measured the same way, so a difference between them is attributable to the method.

### The objects, in the order they come into existence

| term | what it is |
|---|---|
| **baseline** | one of the twelve methods: `drqv2 svea drq sgqn curl rad soda alda idaac ppg ibac_sni ctrl` |
| **family** | a group of baselines sharing one payload and one evaluator. Seven of them: `rlvigen`(5), `dmc_gb`(2), then `alda`, `idaac`, `ppg`, `ibac_sni`, `ctrl` alone |
| **payload** | a source-only `.tgz` built by `contract.py build-payload`. No results, no weights, no `.git`. Third-party code is fetched inside the container at run time |
| **cell** | ONE (baseline, seed) unit of work — `idaac:102`. Not a container, not a run: one container may hold several cells |
| **run** / **run dir** | one launcher invocation, on the host as `cardN-YYYYMMDD-HHMMSS`, holding `native-out/` (artifacts) and `native-work/` (live run state). Both bind-mounted, so both survive the container |
| **stamp** | a checkpoint frame count. `save_every_frames=50000`, so a 600k cell writes twelve plus the endpoint. Actual values are 51,200 / 100,352 / … because stamps quantise to the rollout size |
| **regime** | `train`, `eval-easy`, `eval-medium`, `eval-hard`. **Distributions over visual conditions, not a difficulty ladder** — `eval-medium` alone randomises the robot's own appearance, and measured, it scores BELOW eval-hard |
| **scene set** | scenes 0–9 plus the pooled set = 11 |
| **policy mode** | `sample` or `mode`. `idaac`, `ppg`, `ibac_sni` report a SAMPLED return; the other nine a MODE return. **Different estimands** — rows differing here may not be ranked against each other |
| **grid** | the evaluation sweep. **curve** = 3 episodes per stamp; **endpoint** = 20 episodes at the final stamp, run TWICE (once per policy mode). One 600k cell = 3,476 episodes ≈ 17.4 h |
| **row** | one measurement: (cell, stamp, regime, scene set, policy mode) → mean return, sd, success rate |
| **record** | a JSONL line carrying a row plus its provenance: `evaluator_revision`, `checkpoint_sha256`, scope |
| **closure** / **evaluator revision** | a hash over the evaluator's code and config members. It answers "does the tree that produced this row still exist". Change a hashed file — comment bytes count — and every family's revision moves |

### The machinery that stops things, named once

| term | what it does |
|---|---|
| **floor** (`NATIVE_NEED_MIB`, default 4000) | minimum FREE card memory. Checked at preflight **and** for the life of the cell. Never waived by shared mode |
| **sentinel** (`/work/yield.sentinel`) | the file a watcher writes on a breach. A **training** cell polls it and stops; an **offline eval** cell never polls it |
| **self-cap** (`self-vram-cap.sh`) | bounds OUR container's own usage, which the floor does not. The floor protects the card; the cap protects the neighbour from us |
| **watch budget** | how long the watchers are armed. Must cover bootstrap + training + evaluation, or a watcher expires mid-run and exits 0 |

### The layers, and why a failure is usually in the one below the one you are looking at

```
laptop          scripts/*.py, contract.py, collection, audits, monitoring
  └─ ssh
host            docker + the shell scripts in ~/rlvigen-work. NOTHING else runs here
  └─ train-production-cell-v5.sh / curve-sweep-v3.sh / reeval-cell-cached.sh   (§9.2)
       └─ launch-card-cell.sh     preflight, watches, reaper, stand-down       (§3.0)
            └─ run_on_production_host.sh     mounts, env allow-list, docker run
                 └─ run_probe.sh   IN CONTAINER: apt+pip, train, retain, grids, delivery
```

### The lifecycle of a number, which is what "is this a result" means

```
payload ──> cell ──> checkpoints ──> grid ──> records_delivery.jsonl
                                                │
                    results/records/<tag>__records.jsonl   (collection, §9.6)
                                                │
                    populate_evaluator_ledger.py  ── refuses a stale closure
                                                │
                    campaign_status / export_fleet / production_gates
```

A number is a **result** only when four things hold, each checked by a tool that refuses: its
closure is live, its job's rows agree on that closure, no reported row pools two closures, and it
carries the `checkpoint_sha256` it was measured from. §10.1 has the table and the commands.

### Three facts that are not obvious and change what you do

1. **Evaluation is the expensive half**, and for a fast-training family it is nearly the whole
   cell. Measured on `idaac`: 4.95 h training, 4.60 h curve, 5.52 h endpoint. Measured on
   `ibac_sni` at procs=16: **44 minutes** training against the same 3,476-episode grid. See §5.
   Budget the whole cell, not the training (§0b, §3b).
2. **Exact reproduction is not available.** Two runs of the SAME invocation reproduce ~35% of
   episodes, in both policy modes. It is ~0.2–0.3 SE and the mechanism is open (§10.3).
3. **The host is shared and the two cards differ in kind.** Card 0's co-tenants are stable and
   large; card 1's is intermittent — median hold zero, but it returns within tens of minutes.
   Over two days, a training cell fits 13.7% of the time on card 0 and 87.8% on card 1 (§9.1).

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

**This table is one family, and the training row does not generalise.** [Claude 2026-09-17]
`ibac_sni` s101 trained the same 600,064 frames in **44 minutes**, not 4.95 hours — a 6.7x
difference, measured from its own log (launched 20:35, `F 600064` at 21:19).

| family | procs / envs | 600k training | source |
|---|---|---|---|
| `idaac` | 8 | **4.95 h** (33.7 frames/s) | `card0-20260909-035152` |
| `ibac_sni` | 16 | **0.73 h** (~228 frames/s) | `card1-20260916-203537` |

The difference is parallel environments, so it is a property of the family's configuration rather
than of the host. Do not budget a cell by scaling this table's training row; read the family's
`procs` and, if it has never run here, treat its training time as **unmeasured**.

What *does* generalise is the shape: the in-cell grid is a fixed 3,476 episodes whatever produced
the checkpoints, so for a fast-training family the grid is not "twice the training" — it is
**essentially the entire cell**. ibac's grid was still running 4.7 hours after a 44-minute training
run. Plan the booking around the grid.

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

## 0c. Which Python runs the laptop-side scripts

Everything under `scripts/` and `datasphere/native/*.py` runs **on the laptop**, not on the host —
the host rule is that nothing but `docker`, `git`, and the shell scripts in `~/rlvigen-work` runs
outside a container. So an operator needs one local interpreter, and it needs `numpy` at minimum;
`scripts/measure_vram_bounds.py`, `export_fleet.py` and `production_gates.py` all import it.

```bash
python3 -c "import numpy, json, pathlib; print('ok', numpy.__version__)"
```

Any Python 3.10+ with `numpy` will run the audit and reporting scripts. Plotting scripts also want
`matplotlib`.

**In the maintainer's workspace** the interpreter is
`/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python`, and the workspace note describing the
available environments is `docs/local-envs.md` **in the parent workspace, not in this repository** —
a clone from GitHub will not contain it, which is why the requirement is stated here rather than
linked. If `$BP` is set in your shell it already points at that interpreter.

## 1. Preconditions, checked on the host every time

```bash
ssh varaksin_as@cds2
cd <the repo, or wherever the payload and this script are>
bash datasphere/native/preflight_production_host.sh --cells drqv2:1 --frames 600000
```

**One command, TEN checks, exit 0 only if all pass.** (Check 9, added 2026-09-08, refuses when
`DOCKER_GPUS` is unset; check 10 is the named card's headroom/utilisation verdict, delegated to
`watch_gpu_headroom.py --preflight`. This line said "nine" until 2026-09-16, when running it
produced ten.)

**Verified by running it, 2026-09-16**, which had not been done from this side before. It passes
nine and correctly FAILS the tenth on a card with ~2.6 GiB free, printing the command to get the
numbers and distinguishing the two halves of that verdict: *"the utilisation half is a COURTESY
limit -- override with --max-util 100 only if the owner has said that slowing a co-tenant is
acceptable. The memory half is not."* It also prints both cards' occupancy, which makes it the
cheapest honest way to see what the machine is doing before you decide anything.

> A trap worth naming because it caught me while running this: `bash preflight... | tail -30` and
> then reading `$?` gives you **tail's** status, not the preflight's — the script reported
> "1 FAILED" while my wrapper printed `exit=0`. Capture first, filter second. It was a hand-run checklist until
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

> **Where it must live, and in what form.**
>
> ```
> ~/rlvigen-assets/places365/train/<365 class directories>/*.jpg     <- the production value (A22)
> ~/rlvigen-assets/places365/val/<36,500 images>                     <- present and complete today
> ```
>
> **Checked on the host 2026-09-16:** `val/` is there in full — 36,500 images, 548 MB. `train/`
> holds only **20 class directories and 1,000 files (16 MB)**, which is the attestation FIXTURE this
> section warns about at its end, not the corpus.
>
> Fetching train was attempted and abandoned rather than skipped: `rlvigen-runs/places365-fetch.log`
> shows `places365standard_easyformat.tar` (~24 GB) downloading at ~55 kB/s with a five-day ETA.
>
> **So `svea`, `sgqn` and `soda` are not stuck — they need a decision, not a card.** `run_probe.sh`
> refuses the val split unless `NATIVE_PLACES365_ACCEPT_VAL=1` is set explicitly, so running against
> val is a *recorded* deviation from A22 rather than a silent one. Either fetch train on a better
> link, or run against val with that flag and say so in the record.
>
> Note the guide's own path below (`/data/places365`) does not exist on this host and `/data` is not
> writable. Use `~/rlvigen-assets/`.

On the host, once — with the path corrected to somewhere writable:

```bash
bash setup/fetch_overlay_dataset.sh ~/rlvigen-assets/places365-train train    # ~24 GB
PLACES365_ROOT=~/rlvigen-assets/places365-train python3 setup/verify_datasets.py --split train
```

Require `dataset usable: PASS` with `class directories: 365` **before the first svea/sgqn/soda
cell**, and do it ONCE for the host rather than per cell — a million-image integrity scan on every
cell is the kind of check people switch off. `setup/verify_datasets.py` hardcodes
`EXPECTED_CLASSES = 365`, so it is the check that distinguishes the corpus from the fixture; run it
and read the class count rather than assuming the directory that exists is the right one.

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

### 3.0a Record the launch, locally, immediately — one command, and it is not optional

The register in [`../results/PRODUCTION-RUNS.md`](../results/PRODUCTION-RUNS.md) is generated from
`results/records/`, so **a cell that ran and was never collected does not appear in it at all**. On
2026-09-09 the two most important runs this project had produced existed only on the host and in one
session's memory; if that session had ended, nothing in the repository would have said they happened.

So, from the laptop, as soon as the run directory exists on the host:

```bash
rsync -a --exclude 'native-work' varaksin_as@100.98.2.11:'~/rlvigen-runs/<run-id>' ./fetched/
python scripts/record_host_run.py ./fetched/<run-id> --status "launched"
python scripts/production_run_register.py        # regenerate the register
```

It reads the cell's own `effective_config.json` — nothing is typed — and **refuses to overwrite an
existing entry** for the same run id. Update a status later with `--update-status`; every entry
carries `status_as_of`, and the register prints the age beside it.

**This is a procedure, not a guarantee.** Skipping it makes the run invisible to the register. There
is no structural backstop: the launcher runs on the host and the ledger is a file in this repo.

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

> **[Claude 2026-09-16] The "lighter alternative" below DOES NOT WORK on this image, and the code
> already knows it.** `run_probe.sh` says so in full: *"A cache is therefore NOT ACHIEVABLE on this
> image, whatever flags are passed. Debian patches pip's caching out, so `pip cache dir` reports
> 'cache is disabled' with no PIP_NO_CACHE_DIR and no pip.conf in sight."* The feature announced
> success twice while doing nothing — first with `--no-cache-dir` merely omitted, then with
> `--cache-dir` passed explicitly, which pip **accepts and does not honour**.
>
> Verified again today on a live cell: the mount is present
> (`~/.cache/rlvigen-pip -> /root/.cache/pip`), the directory holds **0 files**, and the cell had
> 243 pip download lines. So every cell pays the full download, and any script promising otherwise
> is promising something the image cannot give.
>
> **The prebuilt environment is the real remedy** and one already exists on the host:
> `~/rlvigen-env/torch-02805cc0-94c1577b2cd9`, 5.8 GB, built for `cells: idaac:1`. Read its
> `ENVIRONMENT.json` before reusing it — this one reports `"editable": []`, which per the box above
> means it cannot run an `rlvigen` cell; `run_probe.sh` refuses with `NATIVE_EDITABLE_NOT_INSTALLED`
> rather than running the wrong thing, so trying it costs a refusal, not a bad result.

Lighter alternative if you do not want a prebuilt environment, **kept for the record and not
usable here**: `NATIVE_PIP_CACHE_HOST=$HOME/.cache/pip-rlvigen` was meant to persist the wheels
between cells so only the first pays the download.

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
> **[Claude 2026-09-16] The assignment has changed and this block is now doubly stale: the booking
> covers BOTH cards.** That does not make `--gpus all` safe, and the reason is different from the
> one above. Both cards carry other groups' containers in practice (§9.1) — the booking says the
> cards are ours, the occupancy says we share them — so naming a card explicitly remains correct,
> and `launch-card-cell.sh` still requires it. What changed is only that card 0 is no longer
> off-limits by assignment.
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

## 9. The 2026-09 campaign layer — co-tenants, wrappers, and what is measured

Everything above describes the mechanism. This section describes running it on **this** host, in
**this** booking, and it exists because §0-§8 were written before the host was ever reachable and
before anyone else was observed on the cards.

### 9.1 You are sharing the cards, whatever the booking says

The booking covers both cards. The occupancy does not agree, and the occupancy is what your cell
meets. Observed containers, by name:

| container | typical hold | behaviour |
|---|---|---|
| `rlvigen_kalugin_df` | **two processes, ~10,650 MiB each = ~21.3 GiB** | releases the whole block and reclaims it minutes later |
| `rl4vla_cudagl` | ~14,700 MiB | long-lived |
| `sg_sam2` | ~3,800 MiB | long-lived |

**A card that just became free is not a free card.** On 2026-09-16 a 600k cell was launched into a
five-minute vacancy on card 1 and the co-tenant returned within minutes. Watch a card for a
sustained period before committing a multi-hour job to it. Card 0 went 12,354 -> 6,190 MiB free in
ten minutes on the same day.

### Decide whether to launch at all, before deciding what

Measured across seven training attempts and eleven eval cells on 2026-09-16:

> **On this host, under the current co-tenant, EVALUATION work is viable and TRAINING work is not.**

An eval cell is 841 MiB and coexists with a 21.7 GiB co-tenant. A training cell is 2.6 GiB or more
and does not survive the spikes, because the floor stands it down the instant free memory drops
under 4,000 MiB. That is the floor working — our cell dies, the colleague's does not — but plan
around it rather than relearning it:

- idaac s102 was killed at 41% when free fell **6,422 → 224 MiB in twenty seconds**.
- ibac_sni s101 was killed **eight minutes after launch**, mid-ramp, when free fell 8,575 → 2,595.
- In the same afternoon, eleven eval cells completed on card 0 and produced an entire 11-stamp
  curve while co-tenants held 26 GiB of that card.

**The two cards are not interchangeable.** Card 0's co-tenants (`sg_sam2`, `rl4vla_cudagl`) are
long-lived and stable; card 1's (`rlvigen_kalugin_df`) cycles off and back within tens of minutes.
Put work you care about on card 0.

**The launch criterion, and it is not "is there room now".** A window is only worth a multi-hour
cell if it would survive the co-tenant's *return*:

```
free  >=  (the family's measured peak)  +  4000 floor  +  (the co-tenant's usual hold, ~21,300 MiB)
```

For idaac that is 27,938 MiB, not 6,638. Anything less is a cell you will pay for and lose, and —
as §9.1's worked example shows — it can take a healthy cell down with it.

Read occupancy with the aggregate queries only — never `ps aux`, never another user's directories:

```bash
nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader -i 1
```

### 9.2 The convenience wrappers above `launch-card-cell.sh`

§3.0's launcher is still the mechanism. These sit on top of it, live in
[`../datasphere/native/host-scripts/`](../datasphere/native/host-scripts/) and are deployed to
`~/rlvigen-work/`. Their interfaces are checked against this section by
`python scripts/operator_readiness.py --interfaces`, so a script that gains an option and does not
gain a line here **fails a check** rather than drifting.

**`train-production-cell-v5.sh`** — one 600k cell, train + endpoint grid. No required variables;
every parameter has a default:

| var | default | note |
|---|---|---|
| `FAMILY` / `BASELINE` | `ibac_sni` | set both |
| `SEED` | `101` | the schedule's seeds are `[101,102,103]` |
| `FRAMES` | `600000` | |
| `CARD` | `0` | any other card needs `YIELD_PROCS=1` (below) |
| `YIELD_PROCS` | `0` | `NATIVE_YIELD_ON_PROCESSES` |
| `EXPECT_OURS` | `8` | processes this cell legitimately puts on the card |
| `TIMEOUT_S` | `43200` | `CELL_TIMEOUT_SECONDS`, 12 h |
| `VRAM_MIB` | `4096` | `NATIVE_VRAM_CAP_MIB`; **does not bind** — every family launcher overwrites `PYTHONPATH` |

**The `CARD`/`YIELD_PROCS` interaction is not obvious and has cost a cell.** `launch-card-cell.sh`
refuses any non-zero card unless `NATIVE_YIELD_ON_PROCESSES=1`, and says why in the refusal:
*"Any other card must process-yield, because it is not ours to take."* But v5 also sets `NATIVE_ALLOW_SHARED_CARD=1`, and on a non-zero card that
combination sets `YIELD_PROCS=()`: the gate is satisfied and the process yield is then deliberately
**not applied**. The launcher's own comment records why — the count trigger once killed a
production training cell ten minutes in, because it saw two colleagues on a card we had chosen to
share. The memory floor and the disk watch are never waived.

**`curve-sweep-v3.sh`** — evaluates every retained checkpoint, several cells at a time.
Requires `FAMILY`, `BASELINE`, `SEED`, `CKPT_DIR`. Options: `CARD` (1), `MAXCELLS` (6),
`MIN_FREE_MIB` (6000), `MIN_FREE_GIB` (100). It **skips stamps whose result tgz already exists**, so
restarting after a crash is safe and prints `SKIP <tag> (result present)`. Sitting at
`waiting: cells=N/N vram_free=...` is correct behaviour, not a stall.

**`reeval-cell-cached.sh <endpoint|curve>`** — one eval cell against one checkpoint.
Requires `FAMILY`, `BASELINE`, `SEED`, `FRAME`, `SNAP`. Options: `CARD` (1), `TAG`
(`$BASELINE-s$SEED-$MODE`), `TIMEOUT_S` (3600), `ALLOWANCE_S` (36000), `NEED_MIB` (**1500**, not the
4000 training floor — an eval cell is measured at 841 MiB), `EXPECT_OURS` (1),
`PIP_CACHE` (`$HOME/.cache/rlvigen-pip`), `POLICY_MODES` (`native`).

> `POLICY_MODES` defaults to `native` here, while the **endpoint** protocol is `native,mode` and
> sweeps the grid twice (§0b). If you are reproducing an endpoint grid rather than a curve, set it
> explicitly.

**`self-vram-cap.sh <container> <card> <cap_mib> [log]`** — option `INTERVAL` (20 s). Stops **our**
container, by exact name, when **our** usage crosses the cap. See §9.4.

### 9.3 Measured GPU memory, and one number that was wrong three times

From `datasphere/native/measured-vram-bounds.json` via `scripts/measure_vram_bounds.py`.

| family | peak | | family | peak |
|---|---|---|---|---|
| `ctrl` | 32,435 MiB — **exceeds a 32,494 MiB card once the 4,000 floor is added**, so it needs an empty card *and* an explicit decision about the floor | | `dmc_gb` | 2,529 MiB |
| `ppg` | 7,146 MiB | | `alda` | 2,397 MiB |
| `rlvigen` | 4,549 MiB | | one eval cell | 841 MiB, 1 core, 2.1 GiB RAM |
| `idaac` | 2,638 MiB | | `ibac_sni` | **UNMEASURED** |

**`ibac_sni` is the cautionary case.** Three figures for its `procs=16` VRAM circulated on
2026-09-16 and all three were wrong:

- *~15 GiB* — never measured. An estimate in a comment in `reeval-cell.sh`, quoted back as a
  measurement by two agents deciding whether a card had room.
- *2,199 MiB* — real, but a 3-process cell, and it **under-counts**: the same cell's card delta is
  6,804 MiB and the ~4.6 GiB gap is EGL render contexts, which are not compute apps and so never
  appear in a per-process sum. At `procs=16`, one context per worker, that term dominates.
- *22,675 MiB* — reported as measured; **21,300 MiB of it was a colleague's two processes.**
  `measure_vram_bounds.py` summed every compute process on the card while its docstring claimed it
  filtered to our process tree.

The instrument is fixed — the field is now `all_procs_peak_mib`, rows carry `shared_card` and
`steady_state`, and the aggregation refuses a shared or still-ramping row. The number is still
unknown: the only figure the data supports is a **lower bound of ~6.6 GiB** (card delta when the
floor stood the cell down 42.4 s in, process count still climbing 2 -> 20).

**So: before using a number to decide anything, find where it was produced. If it came from a
comment, it is not a measurement.**

### 9.4 Stop mechanisms — the operational summary

Full treatment, including two retracted claims, in
[`model/STOP-MECHANISMS.md`](model/STOP-MECHANISMS.md).

- **The memory floor is enforced for the whole run**, not just at preflight.
  `yield_gpu_to_neighbour.py` (STEP 2) polls free memory against `NATIVE_NEED_MIB` and writes
  `/work/yield.sentinel` on a breach. `NATIVE_ALLOW_SHARED_CARD=1` waives exclusivity and the
  utilisation ceiling; it never waives the floor. `scripts/watch_gpu_headroom.py`'s `watch()` is
  only a **recorder** — reading that function alone will mislead you, and it did: a claim that the
  floor was preflight-only was published in STOP-MECHANISMS and retracted a day later.
- **Only a TRAINING cell obeys the sentinel.** An offline eval cell never polls it, so a sweep
  survives a breach that stands a training cell down. Do not read "the eval cells are still going"
  as "the floor is not working".
- **The floor protects the CARD, not us.** It fires when free memory is already low, which on a
  shared card can mean our own growth pushed a co-tenant to the edge. `self-vram-cap.sh` is the
  other half: it bounds our own footprint. Size the cap as
  `card_total - (our other cells) - 4000`, then leave the co-tenant room to return. On a 32,494 MiB
  card with a 2,635 MiB cell of ours resident, the floor trips at 25,859; with `rlvigen_kalugin_df`
  taking 21.3 GiB when present, 8,000-10,000 MiB is the considerate cap.

### 9.5 Monitoring that reports to a person

A monitor writing to a file on the host is not monitoring. Run the poll from the laptop. Three
traps, each of which has produced a false reading here:

- **`pgrep -f <script>` matches your own ssh shell**, whose command line contains the script name.
  `pkill -f ibac-waiter.sh` killed the operator's own session; `pgrep -fc` self-counts, which is
  what launched three duplicate sweeps. Resolve `argv[1]` from `/proc/<pid>/cmdline` and check it
  ends with the script name.
- **Never grep a run directory for a marker.** `native-work/` contains `run_probe.sh`, which
  contains the literal string `NATIVE_CELL_FAILED`. Grepping the run dir reports a failure for
  every healthy run. Grep the **log file**.
- **Progress strings differ by family, and so does how OFTEN they appear.** `ibac_sni` and `ppg`
  log `F {:06}`; `idaac` logs a key/value table with `train/total_num_steps`. A monitor matching
  only `F [0-9]+` reads zero forever against an idaac cell.
- **Run monitor loops under `bash` explicitly.** The laptop shell is zsh, which does not word-split
  an unquoted `$var`: a loop `for h in $holders` saw three known group names as ONE unknown name
  and raised a false "new group on the machine" alarm. Put the loop in a file and run
  `bash file.sh`, and split lists with `IFS=, read -r -a` rather than relying on the shell.
- **"Has a sentinel fired?" must be asked of ONE run directory, never a glob.** A yielded cell
  leaves `native-work/yield.sentinel` behind in its own run directory, and those directories are
  never cleaned up. Asking `ls ~/rlvigen-runs/card1-2026091*/native-work/yield.sentinel` on
  2026-09-17 returned **fourteen** sentinel files, every one of them from a cell that died days or
  hours earlier, while both live cells were untouched. The list looks exactly like a fleet-wide
  stand-down and is pure history. Name the run directory of the cell you are asking about:

  ```bash
  ls ~/rlvigen-runs/card1-20260916-203537/native-work/yield.sentinel 2>/dev/null || echo "not fired"
  ```

  The same caution applies to counting `cell-c1-*` containers and to anything else globbed over
  `~/rlvigen-runs/`: that directory is an archive of every attempt, not a picture of what is running.
- **The host occupancy logger has a 24-hour life by default** (`GPU_LOG_HOURS`). If you need its
  record to cover tomorrow morning, restart it with a longer window — stop it, wait one interval
  (its orphaned `sleep` child holds the flock), start the new one, and confirm a fresh
  `# gpu-occupancy-log started` line. It is the only record that answers "was a card free while
  nobody was watching", which is how the co-tenant model in §9.1 was finally measured.
- **A stall detector must be longer than the logging interval it watches.** idaac writes a block
  every ~24,600 steps, which is about **11 minutes** of wall clock. A 9-minute stall threshold
  fired on a cell sitting at 99.5% CPU with its GPU processes resident. Use the **log file's
  mtime** for liveness — it is fine-grained and family-independent — and treat the step counter as
  progress, not as a heartbeat. Before acting on any stall alarm, check
  `docker stats --no-stream <container>`: a busy container is not stalled whatever the log says. Match both, and alarm on `NATIVE_CELL_FAILED`,
  `NATIVE_CELL_YIELDED`, `Traceback`, `Killed` and `OOM` as well — a filter that matches only
  success signals stays silent through a crash.

- **Test your stop detector against a log of a cell that actually stopped.** The marker is
  `=== NATIVE_CELL_YIELDED stopping this cell; reason follows from the sentinel ===`, so the usual
  `grep -oE "=== NATIVE_CELL_(COMPLETED|FAILED|YIELDED) " | awk '{print $2}'` yields the WHOLE token
  `NATIVE_CELL_YIELDED`. A `case "$mk" in FAILED|YIELDED)` therefore never matches, and the monitor
  silently loses the one event it exists to report. Five monitors of mine carried that bare form on
  2026-09-17; when `ibac_sni` s102 was stood down by the memory floor at 08:01 not one of them said
  so, and the stop went unnoticed for eighteen minutes until a frame counter failed to move. Use
  `*FAILED|*YIELDED`, and prove it on a real stopped cell:

  ```bash
  mk=$(grep -aoE "=== NATIVE_CELL_(COMPLETED|FAILED|YIELDED) " "$LOG" | tail -1 | awk '{print $2}')
  echo "[$mk]"     # expect [NATIVE_CELL_YIELDED], not [YIELDED]
  ```

  The general form of the mistake: a monitor's alarm branches are the part that never runs during
  normal operation, so they are the part that is never exercised. A green heartbeat says nothing
  about them.
- **Retire a handled failure from the monitor, or it masks the runs that still matter.** Once the
  stop detection was fixed, the dead cell became the dominant state at every heartbeat and the two
  LIVE grids dropped out of the line entirely. A monitor should report what needs attention now, not
  the last thing that went wrong: when a failure has been recorded in `results/host-runs.jsonl` and
  nothing further can be done about it, drop its alarm branch and keep at most a counter for context.
  The same applies to the alert TEXT — a generic "checkpoints from 51200 onward are retained" read
  as reassurance on a cell that stopped at frame 28,672 and had none.
- **A stop marker does not name its cause.** `NATIVE_CELL_YIELDED` is written by the poller, which
  deliberately does not say why — the reason is in the cell's `yield.sentinel`, and it is not always
  a co-tenant. Read the sentinel: `cat <run-dir>/native-work/yield.sentinel`.
- **Do not pass a timeout to a watch you want to keep.** A long-lived poll loop launched as a
  background shell is not reaped on its own — one ran past ten minutes with no timeout argument and
  kept going. What killed the first one was a `timeout` of 600000 ms that *I* passed, and the
  symptom read as an environment limit rather than as my own argument, which sent me looking in the
  wrong place. Arm an overnight watch with no timeout, and confirm it by checking the process is
  still there some minutes later rather than by assuming either way.
- **A watch you edit while it runs is a watch with no defined contents.** Write the change to a new
  file (`prod-monitor-v4.sh`), restore the running file byte-for-byte, then stop the old watch and
  start the new one. Editing in place produced a syntax error reported at a stale byte offset, on a
  file that passes `bash -n`.
- **Set a disk threshold above the floor the running cell enforces on itself**, not at a round
  number. The cell prints its own floor in its launch banner (`disk: 118 GiB free, floor 98 GiB`).
  A monitor warning at 60 GiB fires long after that cell has already stood itself down, so the
  operator learns about the disk from the run dying. Warn above the floor, not below it.

Also useful, from §7b: `docker logs -f <container>`, `docker stats <container>`,
`scripts/watch_divergence.py`, and `scripts/watch_policy_health.py --log <training.log>` for
saturation/collapse (it warns and never kills, deliberately).

### 9.5b Two cells on one card: measured, not assumed

`wait-and-train-v3.sh` takes a `flock` and holds it for the whole life of the cell it launches, so
it enforces **one launcher at a time**. Its stated reason is a real incident: two 600k cells once
landed on this 16-core host, "neither errored, and the only symptom was halved throughput".

That rule is about CPU, so it can be checked rather than obeyed blindly. Measured on 2026-09-16,
with `ibac_sni` s101 in its in-cell grid and `idaac` s102 training from zero on the same card:

| | ibac eval throughput | host load | per-cell CPU |
|---|---|---|---|
| solo (21:22–21:32) | 1.872 log-lines/min | ~2.5 | — |
| packed (21:35–21:45) | 1.680 log-lines/min | ~3.5 | 98.9% and 100.3% |

**r = packed/solo = 0.90.** The runbook's threshold is `r < 0.5` means packing loses; 0.90 does not
come close. `docker stats --no-stream` is the decisive instrument here: each container sits at
about **one core**, not sixteen, so two cells are nowhere near saturating the host. A later load
average of 42.67 on 16 cores was *other people's* jobs — our two cells accounted for ~2 of it.

So the one-launcher lock is a duplicate-prevention rule, not a capacity limit. The bounds on a second
cell are **VRAM** (see the capacity model in §9.3), **disk** — a bootstrap costs up to ~7 GiB
transiently, against a floor of 98 GiB that the cells enforce on themselves — and **whether the
vacancy you are launching into is real**, which is the one that has actually killed cells.

> **Correction, 2026-09-17.** This paragraph used to say "launch a second cell by calling
> `train-production-cell-v5.sh` directly, which is what the waiter does anyway". That is the advice
> that lost `ibac_sni` s102, and "what the waiter does anyway" was false in the part that matters.
> The waiter does not just call v5: it first requires card capacity to hold for **`HOLD=10` polls at
> `POLL=60` s — ten sustained minutes**. Calling v5 directly throws that check away.
>
> **That ten minutes is the right number, and it is measured, not chosen.** Thirty hours of the
> occupancy log show the co-tenant `rlvigen_kalugin_df` leaving card 1 twelve times. The absences
> lasted **2, 1, 1, 36, 1, 1, 171, 1, 5, 1, 1 and 4 minutes**. Ten of the twelve are ≤5 minutes:
> those are not vacancies, they are the co-tenant **restarting between jobs**, and its next job
> reclaims ~22 GiB within minutes. Only two were real windows — 36 and 171 minutes, the second being
> the window `ibac_sni` s101 trained in. A ten-minute hold rejects every restart in that record and
> admits both real windows.
>
> s102 was launched at 07:50 into the 07:48 absence, which lasted four minutes. The co-tenant came
> back while s102's EGL contexts were still ramping, free memory hit 75 MiB, and the floor stood it
> down at frame 28,672 — before its first 50k checkpoint, so nothing was kept. The same trap
> presented itself again at 10:28 (card 1 used fell to 2,994 MiB); waiting one minute showed a new
> `rlvigen_kalugin_df` process already ramping 466 → 1,358 MiB.
>
> **So: to add a cell to a shared card, require the vacancy to persist for ten minutes first.** Use
> the waiter when its lock is free. When the lock is held by a running cell's waiter — as it is for
> the life of that cell — reproduce its check by hand: sample the card once a minute and launch only
> after ten consecutive samples have the capacity you need. Checking the occupancy log's `holders=`
> for the co-tenant's name over those ten minutes is the same test with a better label.

**What packing does not change:** on card 1 with `NATIVE_ALLOW_SHARED_CARD=1`, process yield is not
armed (`launch-card-cell.sh:276`), so a second cell of ours does not trip the other's count trigger.
The 4,000 MiB memory floor stays armed for both, independently, for the life of each cell.

### 9.5c Every running cell has its own disk floor, and a new launch eats into all of them

**The disk floor is not one number.** `launch-card-cell.sh:439-453` sets it per cell, once, at that
cell's launch: `floor = free space at launch − allowance`, where the allowance is twice
`family.py disk-requirement` (absolute minimum 50 GiB). Each cell prints its own in its banner. On
2026-09-17 three cells were live with three different floors:

| cell | free at its launch | allowance | its floor |
|---|---|---|---|
| `ibac_sni` s101 | 118 GiB | 20 | **98** |
| `idaac` s102 | 117 GiB | 18 | **99** |
| `ibac_sni` s102, attempt 2 | 109 GiB | 20 | 89 |

**Nothing checks a new launch against the floors of cells already running.** A new cell sizes its
own allowance from the free space it sees and never looks at anyone else's floor. But its
bootstrap installs torch into a fresh container layer, which costs **~7-10 GiB transiently** — and
that transient lands on every running cell's margin at once.

It came within one sampling interval of stopping a cell. `ibac_sni` s102 attempt 2 launched at
11:00 with 108 GiB free, against `idaac` s102's floor of 99. At 11:06:18, mid-`pip install`, free
space read **98 GiB — below idaac's floor.** idaac survived only because `watch_disk_headroom.py`
samples every 60 s (`--interval 60`) and the dip had recovered to 101 by 11:06:33; its sentinel was
untouched. The earlier launch at 07:50 had done the same thing less severely (108 → 101).

I had reasoned before both launches that disk was "comfortably above the 98 floor". That compared
the wrong cell's floor against a transient I had measured once and then underestimated.

**Before launching onto a host with cells already running:**

```bash
# every live cell's floor, from its own banner
grep -h "^disk: " ~/rlvigen-runs/prod-v214/*-prod.log | tail -5
df -Pk ~ | awk 'NR==2{printf "%d GiB free\n", $4/1048576}'
```

Take the **highest** floor among cells still running, add ~10 GiB for the new cell's bootstrap
transient, and launch only if current free space exceeds that sum. On 2026-09-17 that was
99 + 10 = 109 against 108 free — so neither launch should have been made on disk grounds alone.

A monitor's disk threshold has the same shape: it must be above the highest live floor, not above a
remembered constant. The committed `prod-monitor-laptop.sh` defaults assume 98 and say so.

### 9.6 After a run — the steps that turn a cell into a result

A collected archive is not yet a result. In order:

**A re-evaluation SWEEP is collected differently from a run**, and this was undocumented until
2026-09-16 — ppg's 528 curve rows were merged by hand. A sweep leaves one archive per stamp, each
with its own `records_delivery.jsonl`; `collect-host-run.sh` takes a run directory and does not
apply. Use:

```bash
rsync -a 'HOST:~/rlvigen-runs/reeval-v214/idaac-s101-curve-*-result.tgz' ./fetched/
python scripts/collect_reeval_sweep.py ./fetched --tag reeval-v214-idaac-curve          # dry run
python scripts/collect_reeval_sweep.py ./fetched --tag reeval-v214-idaac-curve --write
python scripts/populate_evaluator_ledger.py idaac reeval-v214-idaac-curve
```

It prints every stamp it found, so a missing one is a gap in a printed list rather than an absence
nobody counted, and it REFUSES rather than warns on: a row whose evaluator revision is not live,
rows spanning two revisions, a duplicated stamp, and overwriting an existing collection. Validated
against ppg's hand-assembled curve — same 528 rows, identical keys, zero differing values.

```bash
# 1. record the run exists -- see 3.0a, and do it at LAUNCH, not after
python scripts/record_host_run.py ./fetched/<run-id> --status running
python scripts/production_run_register.py

# 2. collect, with the audits that refuse rather than warn
bash datasphere/native/collect-host-run.sh <family> ./fetched/<run-id>
bash datasphere/native/collect-wave.sh --from-submissions <tag>   # a whole wave

# 3. records -> ledger. A record that is not in the ledger is not a result.
python scripts/populate_evaluator_ledger.py <family> <job>

# 4. read the campaign, not the run
python scripts/campaign_status.py
python scripts/export_fleet.py --csv fleet.csv     # flat table + documented schema
python scripts/production_gates.py | tail -3
```

> **There are TWO attempt systems, and until 2026-09-16 only one of them was gated.**
> `results/submissions.jsonl` records DataSphere jobs and `audit_attempt_ledger.py --strict` refuses
> when an earlier attempt's outcome cannot be read — that is what enforces "a rerun never silently
> replaces a failed seed". Host cells are not DataSphere jobs: they are recorded in
> `results/host-runs.jsonl` by `record_host_run.py`, and **nothing refused anything about them.** So
> the guarantee held for the jobs we had stopped running and not for the ones we had started. It
> became concrete when five ibac_sni cells failed on the host in one day; a sixth could have been
> launched with nothing on disk saying what became of its predecessors. `audit_attempt_ledger.py`
> now checks both, with the same rule: for a (baseline, seed) attempted more than once, every
> attempt but the newest must carry a terminal status. **So record the launch (§3.0a) and update its
> status when it ends** — that is not bookkeeping etiquette, it is what the gate reads.

`populate_evaluator_ledger.py` **refuses a record whose evaluator revision is not the live one**,
and that refusal is the most valuable thing it does. Never pipe it through `tail` and read `$?` —
the pipe returns the filter's status, and this exact mistake made the collector print
"Do NOT write this entry" and exit 0.

### 9.7 Before you finish a session

```bash
python scripts/operator_readiness.py     # does every operator need still route somewhere?
python scripts/production_gates.py | tail -3
git status --porcelain                   # stage BY PATH; a second agent shares this tree
python -m pytest tests/ -q               # slow; at real checkpoints, not every iteration
```

`source tree frozen` is a gate and it **fails on uncommitted paths**, deliberately: a commit is what
makes "the code whose results we report" well defined. Never `git add -A` here.

## 10. Is this a result yet? — admissibility, comparability, and the tools

A finished cell is not a result, and the distinction is mechanical rather than a matter of
judgement. This section is the operator's half; the scientific reasoning lives in
[`../docs/EVAL-PROTOCOL.md`](../docs/EVAL-PROTOCOL.md) and
[`SAME-AXES-VERDICT.md`](SAME-AXES-VERDICT.md) and is not restated here.

### 10.1 When a number becomes a result

Four things must hold. Each is checked by a tool that **refuses**, so none of them is your opinion.

| # | condition | what refuses if it fails |
|---|---|---|
| 1 | the row's `evaluator_revision` equals the family's LIVE revision | `populate_evaluator_ledger.py` — this assertion "is the whole value of this script" |
| 2 | every row within one job agrees on `evaluator_revision` | the same script: *"rows disagree on evaluator_revision within one job"* |
| 3 | no reported row pools seeds from two closures | `audit_row_closure.py --strict`, and the `no row pools two closures` gate |
| 4 | the row carries the `checkpoint_sha256` it was measured from | `audit_record_frame_provenance.py`, run by `collect-host-run.sh` |

**Re-evaluation rows need `--checkpoints`, or they are all UNVERIFIABLE and it looks like a pass.**
A re-evaluation cell is handed a *staged copy* of a checkpoint some earlier run's trainer wrote, so
the checkpoint never lives beside the records. Pointed at a records file alone the audit has nothing
to hash: `reeval-v214-ppg-endpoint` reported **88 rows, 88 unverifiable, exit 0**. That is not a
false alarm — the rows really were unchecked — but it reads identically to a clean pass unless you
read the counts, and re-evaluation is now how this project produces admissible results.

```bash
python scripts/audit_record_frame_provenance.py results/records/<tag>__records.jsonl     --checkpoints <the ORIGINAL run directory, not just its checkpoints/ subdir> --strict
```

Measured 2026-09-16 on the two banked baselines:

| bundle | without `--checkpoints` | with it |
|---|---|---|
| `reeval-v214-idaac-curve` | 484 unverifiable | **484 corroborated**, 0 mismatched |
| `reeval-v214-ppg-curve` | 528 unverifiable | **528 tied**, 0 mismatched |
| `reeval-v214-ppg-endpoint` | 88 unverifiable | 88 unverifiable — see below |

The two verdicts differ for a real reason. idaac's trainer names each file `..._151552.pt`, so the
filename and the record agree through no shared code path — the strongest verdict available. ppg
names by save INDEX (`model012.jd`), so the frame can only be tied through the original training
log, which is why `--checkpoints` must point at the run directory rather than its `checkpoints/`
subdirectory.

**ppg's ENDPOINT rows stay unverifiable by this instrument, and that is honest rather than fixable
here.** The endpoint measures the terminal `snapshot.pt`, which carries no frame in its name and
has no save line. The repo does hold that policy at
`results/superseded-runs/checkpoints/ppg-s1-600064-a328e63e.pt` and its sha matches the rows — but
that is a name *we* chose, and teaching the audit to parse it would make the check agree with our
own convention instead of with the trainer's. Those rows are instead covered independently: a peer
session compared all 71 tensor storages between the endpoint's `snapshot.pt` and the curve's
`model012.jd` at 600,064 and found them byte-identical, with `model011` as a negative control that
came out DIFFERENT.

**"Superseded" means re-hashed, not refuted.** A row whose closure has moved is not wrong; it
describes a tree that no longer exists. Because every intermediate checkpoint is retained, the fix
is to re-run the grid, which costs **no training** — that is exactly how ppg's and idaac's 600k runs
became admissible on 2026-09-16, turning 28 current rows into 732
([`production-host/33`](production-host/33-what-we-actually-have-2026-09-16.md) §0).

Read the state with `python scripts/export_fleet.py`, whose `closure_current` column exists to make
this visible; it exports superseded rows **marked** rather than dropped, so the table can never
disagree with `results/records/` for a reason the reader cannot see.

### 10.2 The grid, the cadence and the seeds — what an operator must not improvise

All three are decided and frozen; the operator's job is to not deviate, because a deviation makes a
cell that is not a production cell whatever its frame count says. `run_probe.sh` refuses the obvious
deviations itself (`NATIVE_PRODUCTION_CONFLICT CURVE_EVAL=0 expected=1`).

- **The grid**: 4 regimes x 11 scene sets, curve at 3 episodes per stamp, endpoint at 20 episodes
  x 2 policy modes. 3,476 episodes per 600k cell. [`EVAL-PROTOCOL.md`](../docs/EVAL-PROTOCOL.md) §2;
  the "three, not five" decision is A20, 2026-09-05.
- **The cadence**: `save_every_frames=50000`, and on the v100 profile every family retains all 13
  stamps. Actual deltas are 49,152 / 51,200 because stamps quantise to the rollout size — the
  declared round number is not what lands. [`EVAL-PROTOCOL.md`](../docs/EVAL-PROTOCOL.md) §4.
- **The seeds**: fixed n=3 per reported row, **allocated in advance, never chosen by outcome**.
  [`EVAL-PROTOCOL.md`](../docs/EVAL-PROTOCOL.md) §4b, and §4c for what n=3 licenses statistically.
  `production-schedule-v100.json` names `[101, 102, 103]`.

> **A live discrepancy, so nobody rediscovers it as a surprise.** `ppg`'s banked 600k run is at
> **seed 1**, outside that set, so `campaign_status.py` reports it MISSING on all three columns and
> the campaign reads **1 DONE of 36** despite two complete baselines existing. The rows are valid;
> the join is what fails. See [`production-host/33`](production-host/33-what-we-actually-have-2026-09-16.md) §1.

### 10.3 Which comparisons are licensed

`python scripts/comparison_blocks.py` computes this; do not eyeball it. Raw return blocks on four
axes, and two methods differing on **any** of them may not be ranked against each other:

```
RETURN_BLOCKING_AXES = ("policy mode", "frame stack", "time limit", "network input")
```

`policy mode` is the one that bites daily: `idaac`, `ppg` and `ibac_sni` report a **sampled** return,
the other nine a **mode** return. Different estimands, not one quantity measured twice —
`export_fleet.py` carries `policy_mode` on every row for exactly this reason.

Retention (an eval/train ratio) blocks on **nothing**, deliberately: those four are per-method
properties appearing in both regimes, so they cancel in the ratio.

Two further limits that are easy to miss:

- **The regimes are distributions, not a difficulty ladder.** `eval-medium` alone randomises the
  robot's own appearance. Measured for ppg, eval-medium scores *below* eval-hard, and 60% of its
  slots vary across passes against 0% for train and eval-easy — so **eval-medium and eval-hard are
  not paired**, and a paired claim about them is unavailable.
- **Exact reproduction is not available and any claim of it is false.** Two runs of the *same*
  invocation reproduce only ~35% of episodes, in mode and sample alike; the mechanism is open. Plan
  comparisons that tolerate this — it is ~0.2-0.3 SE, well inside the noise, but it is not zero.

### 10.4 Every tool in this repository, and what it is for

158 entry points. An operator asking "is there already something for this?" should look here
before writing anything. Regenerate with `python scripts/script_inventory.py --write`; check it is
current with `--check` (the release suite does).

<!-- BEGIN script-inventory (generated by scripts/script_inventory.py) -->

**`scripts/*.py`** — 99 file(s)

| script | what it is for |
|---|---|
| `_discover_grid_checkpoints.py` | Which checkpoints do the existing grids name? — helper for `rederive_grids.sh` (C69). |
| `assemble_reaped_delivery.py` | Rebuild a delivery bundle for a cell that was reaped before it could assemble its own. |
| `audit_attempt_ledger.py` | Every submitted attempt and what became of it, DERIVED from artifacts. |
| `audit_checkpoint_semantics.py` | What a checkpoint contains per family, and what it therefore does NOT let you do. |
| `audit_comparability_seam.py` | Do the twelve clones' reported numbers land on one axis? — the clone-era seam audit. |
| `audit_dead_knobs.py` | Which configuration parameters does an early-returning branch silently drop? — C71. |
| `audit_environment_drift.py` | Did two jobs of the same family actually get different packages? |
| `audit_eval_axis.py` | Per baseline: how many evaluation scenes, and how many visual regimes? — C45 / C43. |
| `audit_eval_cadence.py` | Per baseline: does training-time evaluation exist, how often, and over what? — C43 / C45 / R3. |
| `audit_eval_state.py` | What an OFFLINE evaluator needs from each baseline beyond the weights — R3 / R7 / C43. |
| `audit_eval_validity.py` | Are these numbers reportable? Checks the evaluation's own identity fields, per record file. |
| `audit_executed_hyperparameters.py` | Does the value the fidelity table CLAIMS actually reach the process? |
| `audit_implementations.py` | R6: is each of the twelve a GENUINE implementation, or the name of one? |
| `audit_instruments.py` | Which instruments in this repo are themselves checked, and which are taken on trust? |
| `audit_job_budgets.py` | Can each job config's timeout actually fit the evaluation it asks for? |
| `audit_observation_geometry.py` | Declared, executed, observed — the observation geometry of all twelve, in one table. |
| `audit_pairing_evidence.py` | Do the records PROVE paired physical conditions, or only assert them? |
| `audit_payload_freshness.py` | Which built payloads no longer match the tree, and in which members? |
| `audit_record_frame_provenance.py` | Is a record's `frame` corroborated by the checkpoint it was computed from? |
| `audit_row_closure.py` | Do the seeds pooled into one reported row come from ONE scientific closure? |
| `audit_seed_control.py` | Does a seed actually control each baseline's run? -- `docs/CONSTRUCTION.md` C20, screen (a). |
| `audit_shared_evaluator.py` | Has the shared evaluator earned the right to report each baseline's number? |
| `audit_static_classes.py` | Three defect classes that were findable by reading and were not found. [C77](../docs/CONSTRUCTION.md#c77), [C79](#), [C80](#) |
| `audit_submission_configs.py` | Would this job config die on the tier it asks for, or name a cell that does not exist? |
| `audit_training_diagnostics.py` | Did the optimiser behave, or did the run only *look* like it ran? |
| `authorship.py` | Every first-party file, measured against every reference on disk. No sampling, no vibes. |
| `build_external_review_artifact.py` | Build a non-destructive, directory-first external review artifact. |
| `campaign_feasibility.py` | For each of the twelve baselines: what does a production cell need, and can this host give it? |
| `campaign_status.py` | Campaign state across all 36 cells in one view, derived from artifacts. |
| `capture_host_evidence.py` | Capture a verbatim excerpt as evidence, with enough provenance to re-derive it. |
| `check_checkpoint_finite.py` | Is this checkpoint a network, or 7.4M NaNs? [C57](../docs/CONSTRUCTION.md#c57). |
| `check_citations.py` | Check that `file.py:123`-style citations resolve, and point where they claim to. |
| `check_section_scope.py` | Every `##` heading in a two-era document must say which era it describes. [C82](../docs/CONSTRUCTION.md#c82) |
| `classify_drift_frames.py` | Classify each training episode's reset frame by which render condition it matches. |
| `collect_attestation_wave.py` | Collect whichever v212 attestation cells have finished, and populate the ledger for each. |
| `collect_metrics.py` | Read the twelve baselines' logs and put their metrics on one set of axes. |
| `collect_reeval_sweep.py` | Merge a re-evaluation sweep's result archives into one records file, refusing on disagreement. |
| `comparison_blocks.py` | Which pairwise comparisons are PRIMARY, derived from the axes rather than asserted. |
| `decisions.py` | Enumerate the decisions this project has reached, and catch the ones it forgot to log. |
| `deviations.py` | Every line this project changed in an original repo, counted and shown. |
| `eval_across_scenes.py` | What is the scene axis worth IN RETURN? The follow-up C46 names and could not answer. |
| `eval_grid.py` | The offline evaluation grid: regimes x scenes, from one checkpoint — R3 / R7 / C43. |
| `eval_provenance.py` | Small, dependency-light provenance helpers used by the offline evaluators. |
| `evidence_pair_eval_grids.py` | Pair two captured evaluation grids row by row, and say how far apart repeat measurements are. |
| `explain_delivery_size.py` | Why is this record bundle so large? Answers per field, not per file. |
| `export_fleet.py` | One flat table of every record in the fleet, with a documented schema. |
| `generate_fidelity_table.py` | Emit the per-baseline hyperparameter table FROM SOURCE, so prose cannot drift away from it. |
| `greenmark.py` | Record which tree the suite was last green on, and whether that is still this tree. |
| `handicaps.py` | Handicaps, inverted: which ones apply to each baseline? — closes SYSTEM.md's "no home" gap. |
| `learning_over_random.py` | How far above its own untrained policy did each cell get? |
| `measure_vram_bounds.py` | Extract a per-family VRAM peak from returned job archives, so the upper-bound rule can be met. |
| `metrics.py` | The metric definitions this project reports, in one place, with their conditions of validity. |
| `open_decisions.py` | Everything waiting on the owner, from every source that holds one. One command, one list. |
| `operator_readiness.py` | Can an operator get from zero to banked results without asking anyone? Checked, not asserted. |
| `plan_seed_budget.py` | How large a difference can N seeds actually resolve? -- `docs/CONSTRUCTION.md` C18. |
| `plot_curves.py` | One plotting routine over TensorBoard event files. [TASK.md](../docs/TASK.md) R5, item 3. |
| `populate_evaluator_ledger.py` | Write one family's entry in the evaluator-validation ledger, from its job's own records. |
| `preprod_table.py` | Assemble the twelve-baseline pre-production table from returned job archives. |
| `preserve_intermediate_snapshot.py` | Keep the 50k snapshot that a 100k run is about to overwrite. [C68](../docs/CONSTRUCTION.md#c68) |
| `prior_art.py` | Before you commit that note: what does the repo already say about the things in it? |
| `probe_determinism.py` | Do two same-seed runs of a clone agree? -- `docs/CONSTRUCTION.md` C20, screen (b). |
| `probe_floor.py` | What does a random policy score? The floor, without which a trained 0.000 means nothing. |
| `probe_geometry.py` | Measure the two structural differences between the twelve, instead of arguing about them. |
| `probe_heads.py` | Construct each authored continuous head and check its initialisation, instead of reading logs. |
| `probe_level_seed_decodable.py` | Can `level_seed` be decoded from an observation? The direct test of [C50](../docs/CONSTRUCTION.md#c50). |
| `probe_ppg_aux_minibatches.py` | Count PPG's auxiliary-phase minibatches by executing the vendored code, not a re-derivation. |
| `probe_regimes.py` | Do the evaluation regimes actually differ from training? Measured, with a control. |
| `probe_scenes.py` | Does the SCENE axis carry signal? The measurement C45 needs to be worth acting on. |
| `probe_seed_effect.py` | What does the env `seed` argument actually control? -- C20 screen (b), env side. |
| `probe_shim_divergence.py` | How much does the MPS path change the numbers? A golden trace, not an argument. |
| `probe_success_control.py` | Can the success signal fire AT ALL in our configuration, without being forced? |
| `probe_torch_checkpoint_equivalence.py` | Do two `torch.save` files hold the same tensors in the same structure, whatever their bytes? |
| `production_gates.py` | Is the fleet launchable? Recomputed from the tree, not remembered from a document. |
| `production_run_register.py` | One catalogue of every run whose records this repository holds — regenerated, never hand-kept. |
| `read_stack_pilot.py` | Apply the frame-stack pilots' PREDECLARED criterion to a returned cell. |
| `recheck_evidence.py` | Re-hash the sources behind every evidence bundle and say which still match. |
| `record_host_run.py` | Record that a host cell exists, from its own config, before anyone needs its results. |
| `record_measured_peak.py` | Extract a family's peak resident set from a finished job and record it in the descriptor. |
| `refresh_clone_patches.py` | Keep `runnable/_patches/*.patch` reproducing the clones they claim to reproduce. |
| `regime_retention_report.py` | Regime retention from paired `eval_across_scenes.py --json` dumps. |
| `register.py` | Maintain `docs/CONSTRUCTION.md` safely: recount statuses, check structure, locate an entry. |
| `requirements.py` | R1-R7 from the brief, checked against the repo as it is now. |
| `results_table.py` | The presentation-ready results table, built only from what the cells actually support. |
| `rlvigen_reference.py` | RL-ViGen's own published robosuite numbers, read from the file already in the tree. |
| `script_inventory.py` | What every script in this repo is for, generated from the scripts themselves. |
| `state.py` | Recompute the mechanical facts a handoff must not state falsely. |
| `test_inventory.py` | What is the test suite actually verifying? Classified by what each file imports. |
| `verify_cells.py` | Do the tabulated numbers come from the runs they claim? Provenance invariants, per cell. |
| `verify_note_citations.py` | Do the notes still cite what they claim? Checks every `path:line` a note asserts. |
| `verify_resolved_register.py` | Is every `resolved` row in the register actually resolved? Checks, does not trust. |
| `verify_vram_cap.py` | Does `datasphere/native/vram_cap.py` actually bind, and what sits OUTSIDE it? |
| `watch_card_exclusivity.py` | Confirm out loud that a card is ours alone — and scream the moment it is not. |
| `watch_disk_headroom.py` | Stop OUR cell if free disk falls toward a floor. Loud, positive, and on a mandatory timer. |
| `watch_divergence.py` | Catch a NaN-diverged run from its LIVE log, in minutes. [C57](../docs/CONSTRUCTION.md#c57), C79. |
| `watch_gpu_headroom.py` | Card headroom: one pre-launch verdict, or a bounded sampling run. Never a daemon. |
| `watch_policy_health.py` | Watch a running cell's policy for saturation or collapse, and say so while it can still matter. |
| `watch_training_frames.py` | Copy each training episode's reset frame out of the replay buffer before it is deleted. |
| `where_is_this_decided.py` | Given a topic, show every place that discusses it, newest authority first. |
| `yield_gpu_to_neighbour.py` | Stop OUR cell when someone else needs the card. We yield; they never fail. |

**`datasphere/native/*.py`** — 9 file(s)

| script | what it is for |
|---|---|
| `configure_places365_val.py` | Configure a pinned Places365 overlay loader (RL-ViGen or dmc_gb flavor) for one split. |
| `contract.py` | Build and verify the fail-closed native DataSphere payload. |
| `evaluator_identity.py` | Dependency-free evaluator identity primitives shared by build and remote preflight. |
| `family.py` | Resolve one family descriptor into a command line and a retained artifact set. |
| `measure_resources.py` | Sample the native calibration process tree without adding a monitoring dependency. |
| `normalize_curves.py` | One common record per measurement, derived from each family's own logs. |
| `plan_production.py` | Derive the production schedule from measured throughput and the replay memory law. |
| `summarize_result.py` | Turn one returned result archive into the per-cell numbers a scheduling decision needs. |
| `vram_cap.py` | Bound this process's GPU reservation, so a co-tenant's growth cannot be starved by ours. |

**`datasphere/native/*.sh`** — 25 file(s)

| script | what it is for |
|---|---|
| `battery-chain.sh` | The production battery: 12 baselines x 3 seeds x 600k frames, CARD 0 ONLY, one cell at a time. |
| `booking-watchdog.sh` | Say something when the shared node changes in a way that should change what we do. |
| `build-env.sh` | Build ONE reusable environment for a stack, once, into our own directory, from inside the pinned |
| `cell-heartbeat.sh` | Watch one running cell and SAY something the moment anything looks wrong. Never stops anything. |
| `chain-when-card-free.sh` | Run queued cells back to back, waiting only for OUR OWN previous cell to finish. |
| `collect-host-run.sh` | Install a HOST run's records and populate the evaluator ledger, refusing rather than skipping. |
| `collect-wave.sh` | Pull a finished wave's records, install them, populate the evaluator ledger, report the gate. |
| `curve-sweep.sh` | Evaluate every retained checkpoint of a run, several cells at a time. |
| `fire-wave-v205.sh` | [Claude 2026-09-08] Fire the single re-attestation wave after the closure batch. |
| `gpu-occupancy-log.sh` | Append one line per card per minute to a log THAT OUTLIVES THE SSH SESSION. |
| `host-run.sh` | Run a script inside a container on the production host, with no quoting hazards. |
| `job.sh` | One place for the three things every DataSphere interaction here repeats. |
| `launch-card-cell.sh` | Launch one cell on one GPU card, with the exclusivity and yield watches sized to actually cover it. |
| `launch-ibac-when-roomy.sh` | Launch the ibac_sni 600k production cell when a card genuinely has room for it -- not before. |
| `launch-when-free.sh` | Retry a cell launch until a card is genuinely free, then stop retrying. |
| `neighbour-yield.sh` | Yield card 0 to a REAL neighbour -- including a small one the 4000 MiB floor cannot see -- |
| `preflight_production_host.sh` | Check every assumption notes/RUNNING-ON-PRODUCTION-HOST.md makes about the production host, |
| `prod-monitor-laptop.sh` | Run with bash explicitly. The first version ran under zsh, which does NOT word-split an unquoted |
| `reeval-cell.sh` | Re-evaluate ANY banked checkpoint on the current evaluator closure. No training. |
| `reeval-ppg.sh` | Re-evaluate ppg's banked 600k checkpoints on the CURRENT evaluator closure. |
| `require_container.sh` | Refuse to run outside a container. Source this at the top of any script whose body installs |
| `run_on_production_host.sh` | Run one native probe/production cell directly on the production V100 host (cds2), via |
| `run_probe.sh` | (no summary) |
| `self-vram-cap.sh` | Stop OUR OWN cell if its GPU memory would endanger a co-tenant. Never touches anyone else's. |
| `train-production-cell.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |

**`datasphere/native/host-scripts/*.sh`** — 29 file(s)

| script | what it is for |
|---|---|
| `attest-chain.sh` | Run the remaining attestation cells on CARD 0, one at a time, each through launch-card-cell.sh |
| `attest-retry.sh` | Retry the three families the first chain could not attest. |
| `attest-retry2.sh` | svea and soda, third attempt. Attempt 2 got the Places365 archive through (the launcher fix works) |
| `attest-v212.sh` | ATTESTATION WAVE v212 -- all seven evaluator families against the frozen tree. |
| `attest-v213-ctrl.sh` | ctrl only, against the tree that pins nvidia-cudnn-cu12==9.5.1.17. |
| `ctrl-retry.sh` | Retry ctrl's attestation under the DATASPHERE profile. |
| `curve-sweep-v2.sh` | Evaluate every retained checkpoint of a run, several cells at a time. |
| `curve-sweep-v3.sh` | Evaluate every retained checkpoint of a run, several cells at a time. |
| `curve-sweep.sh` | Evaluate every retained checkpoint of a run, several cells at a time. |
| `extract-places-once.sh` | (no summary) |
| `fetch-places.sh` | (no summary) |
| `host-run.sh` | Run a script inside a container on the production host, with no quoting hazards. |
| `ibac-waiter.sh` | Launch ibac_sni on WHICHEVER card gets genuine room. Never contend for a card a colleague holds. |
| `jax-cudnn-diag.sh` | WHY the conv fails, and whether it can be made to work without changing the declared jax spec. |
| `jax-cudnn-pin.sh` | Is ctrl's conv failure the CARD (sm_70) or the DEPENDENCY RESOLUTION DATE? |
| `jax-volta-probe-v2.sh` | Does THIS jax build run a convolution on THIS card? |
| `jax-volta-probe.sh` | (no summary) |
| `neighbour-yield.sh` | Yield card 0 to a REAL neighbour -- including a small one the 4000 MiB floor cannot see -- |
| `reeval-cell-cached.sh` | Re-evaluate ANY banked checkpoint on the current evaluator closure. No training. |
| `reeval-cell.sh` | Re-evaluate ANY banked checkpoint on the current evaluator closure. No training. |
| `run-volta-probe-when-free.sh` | Wait for card 0 to be free of OUR cells, then run the JAX/Volta probe once. |
| `self-vram-cap.sh` | Stop OUR OWN cell if its GPU memory would endanger a co-tenant. Never touches anyone else's. |
| `train-production-cell-v2.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |
| `train-production-cell-v3.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |
| `train-production-cell-v4.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |
| `train-production-cell-v5.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |
| `train-production-cell.sh` | One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve. |
| `verify-places-folder.sh` | (no summary) |
| `wait-and-train-v3.sh` | Launch ONE production cell when a card's capacity for us clears a threshold and STAYS clear. |

*162 entry points. Generated; do not edit by hand.*

<!-- END script-inventory -->

## What this does NOT establish

**[Claude 2026-09-16] Rewritten. Every bullet that used to be here was true when written and is
false now**, which is the worst state for a section whose whole job is to mark the boundary of what
is known. It read "Never executed on `cds2`. No SSH access from the session that wrote it", and
that has not been the case since 2026-09-08: the host has since run attestation waves, two complete
600k production cells, and dozens of evaluation cells. A reader trusting the old text would have
discounted instructions that are now the most heavily exercised part of this file.

Established since, by execution rather than derivation:

- **The host runs this pipeline.** Docker, the NVIDIA Container Toolkit and outbound network all
  work; §1's `preflight_production_host.sh` has been run many times and passes.
- **§5's disk floor has been checked against reality** repeatedly, and disk has been the binding
  constraint more than once. Free space is ~100 GiB at the time of writing, ~57 GiB of it ours.
- **Two 600k cells completed end to end** (`ppg` seed 1, `idaac` seed 101), each with a full
  endpoint grid, and `ppg` with a full curve as well.

Genuinely still not established:

- **`ctrl` has never run at 600k**, and at 32,435 MiB observed it needs a card to itself.
- **`ibac_sni` has never completed a 600k cell.** Five attempts; the furthest reached F 100352
  before the memory floor stood it down. Its VRAM at `procs=16` remains unmeasured (§9.3).
- **Nine of twelve baselines have never produced a production record**, so most of the fleet's
  runtime behaviour at length is still inference from short cells.
- **Concurrent use of the host is the owner's to arbitrate.** This script reserves nothing, and §9.1
  describes what the co-tenants actually do.

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

