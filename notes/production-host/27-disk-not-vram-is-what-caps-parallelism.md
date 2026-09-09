# Disk headroom, not VRAM, is what caps parallelism on this host

Measured 2026-09-09 ~14:47 MSK, while `idaac` and `ppg` were both running on card 0.

## The numbers

```
/dev/sda2   20T   19T used   278G avail   99%   /
/dev/sda3   975M                376M     59%   /boot
```

**One filesystem.** `/`, `/tmp`, `~/rlvigen-runs` and every bind mount are the same `/dev/sda2`.
There is no second place on this machine to put anything.

Two disk watches were armed:

| watch | floor | headroom at 14:47 |
|---|---|---|
| `cell-c0-disk-405898` (idaac) | 255 GiB | 23 GiB |
| `cell-c0-disk-876257` (ppg) | 268 GiB | **10 GiB** |

The floors are `avail_at_launch − allowance`, so they are doing exactly what they were built to do.
The consequence is the part worth writing down: **any new disk consumer of more than ~10 GiB stops
our own production runs**, because it drives `avail` below the ppg watch's floor and the watch
writes the yield sentinel. The instrument cannot tell our own second job from a neighbour's.

## What that rules out, concretely

`drqv2` is the next run in the queue. `family.py disk-requirement --cells drqv2 --frames 600000`:

```
replay_gib  17.74     checkpoints  0.71 written + 0.71 retained     archive  0.71
total_gib   19.88     margin  8.0      required_gib  27.88
```

`launch-card-cell.sh` derives the allowance as the requirement doubled, so a `drqv2` cell wants
about **56 GiB**, and to launch without threatening the ppg watch it needs `avail ≥ 268 + 56 = 324
GiB`. There is 278. **`drqv2` cannot be co-scheduled with the current pair, and the constraint is
disk, not the card.**

Card 0 has 4.4 GiB free of 32.5 GiB with both cells resident, so VRAM would refuse it too — but VRAM
frees the moment a cell ends, and disk does not. Disk is the one that shapes the schedule.

## So the answer to "can pairing 2+ GPU runs in parallel help?"

On *this* host, at *this* disk occupancy: **for replay-buffer families, no.** The pairing question was
posed as a VRAM and throughput question and the earlier work answered it on those terms — `idaac`-class
cells pack, `ppg` is a whole-card job. That answer stands and is incomplete. A second cell also needs
its whole disk allowance to fit *under the floor of every watch already armed*, and with 278 GiB free
on a shared 20T at 99%, two replay-backed families do not fit at all.

The on-policy families are the exception that makes the rule visible: `idaac` and `ppg` pack on disk
precisely because neither writes a replay buffer. Their cells are ~2 GiB each after eleven hours.

## The prebuilt environment serves every family, so this costs nothing extra

`family.py filtered-requirements --cells <baseline>` is **byte-identical across `drqv2`, `idaac` and
`ppg`** (sha256 `72053d1e78d0`).

**RETRACTED, same day.** I wrote that one venv therefore serves all of them, that
`~/rlvigen-env/torch-02805cc0-94c1577b2cd9` was "already in use by both running cells", and that
`drqv2` should point `NATIVE_VENV_HOST` at it. **All three are wrong, and acting on them would have
broken the run.**

- **Neither running cell uses it.** Both set `NATIVE_PIP_CACHE=1` and no `NATIVE_VENV`; the idaac log
  carries `Successfully installed robosuite-1.4.0` and `robosuitevgb-1.0.0`, which only the pip path
  produces. I inferred the env was in use from its existence and did not check.
- **Identical requirements do not make an identical environment.** That env's `ENVIRONMENT.json`
  reads `"cells": "idaac:1"`, `"editable": []`, with `robosuite` and `robosuitevgb` **ABSENT**.
  `build-env.sh` bakes the two editable installs only `[[ -d RL-ViGen-upstream ]]`, payloads never
  carry that tree — the runner git-clones it — so the build printed its NOTE and baked nothing. The
  requirements hash in the directory name is identical for all twelve families and says nothing
  about this.
- **The failure would not have been loud.** `run_probe.sh` skips the editable installs when
  `NATIVE_VENV` is set, and its import check ran with `third_party/robosuite` prepended, which no
  launcher keeps. It would have passed, and the trainer would have hit `ImportError` inside a GPU
  call.

`run_probe.sh` now imports both modules with `PYTHONPATH=""` and refuses with
`NATIVE_EDITABLE_NOT_INSTALLED` when they resolve only from the clone.

**So `drqv2` takes the same path as the two running cells: `NATIVE_PIP_CACHE=1`, no
`NATIVE_VENV_HOST`.** With a warm cache that is minutes, not the two-hour cold bootstrap — but it
is a `pip` install, so it is not free of disk either, and the allowance must cover it.

*(Measured properly on the second attempt. The first comparison ran `filtered-requirements --family`,
which is not the flag; every family hashed to `e3b0c442`, which is sha256 of the empty string. A
check that agrees with nothing agrees with everything.)*

## A plan item that is already closed in code, and I nearly re-discovered it

`notes/RUNNING-ON-PRODUCTION-HOST.md` and the standing plan both ask for a **durable second location
for results**. There is nowhere on this host to put one: `/dev/sda2` is the only filesystem with
space and `/dev/sda3` is a 975 MB `/boot`.

**`run_on_production_host.sh:405-437` already knows this, and says it better than I first wrote it.**
It counts filesystems with at least 20 GB free — *"what matters is not how many filesystems exist but
whether any of them could actually HOLD a result"* — and when there is only one it refuses with:

> THIS HOST HAS NO SECOND FILESYSTEM THAT COULD HOLD A RESULT … The mirror still buys a second COPY
> — it survives our own tar failing, a bad path, an overwrite — but it does NOT buy a second failure
> domain: one full or failed disk loses both. … set `NATIVE_ACCEPT_SAME_DEVICE=1` to run knowing
> that. **This is an owner-level property of the campaign, not a slip.**

That distinction — second copy versus second failure domain — is the whole content of the plan item,
and it was already drawn. My first version of this section presented it as a finding.

**The pattern is worth more than the fact.** This is the second time today a note of mine claimed
novelty the codebase already had. An agent writing from its own context cannot check breadth, so
"this is not handled anywhere" is a claim it is structurally unable to make. Run
`scripts/where_is_this_decided.py` before asserting an absence.

## The drqv2 launch, with every value it actually needs

`launch-card-cell.sh` derives only `DOCKER_GPUS` (from `CARD`) and `NATIVE_RESULT_MIRROR` (from the
run directory). Everything else is the caller's, and `run_on_production_host.sh` refuses production
scale without it:

```bash
CARD=0 CELLS=drqv2:101 FRAMES=600000 CELL_TIMEOUT_SECONDS=43200 NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB=10240 NATIVE_ACCEPT_SAME_DEVICE=1 NATIVE_PIP_CACHE=1 NATIVE_PIP_CACHE_HOST="$HOME/rlvigen-work/pip-cache" NATIVE_DISK_ALLOWANCE_GIB=56   nohup bash datasphere/native/launch-card-cell.sh \
    ~/rlvigen-work/payload-v208-rlvigen.tgz ~/rlvigen-runs/drqv2-result.tgz > run.log 2>&1 &
```

**Pre-flighted 2026-09-09, so the numbers are seen before launch rather than after a stop:**

| | value |
|---|---|
| disk required (`family.py disk-requirement --cells drqv2 --frames 600000`) | **28 GiB** |
| eval workload derived | 3,476 episodes → **62,568 s (17.4 h)** allowance |
| `MUST_COVER` = train 43,200 + eval 62,568 + bootstrap 9,000 | 114,768 s |
| **`WATCH_SECONDS`** (+900 s slack) | **≈ 115,700 s (32 h)** |

**A 32-hour watch is long for a shared, booked card, and that is deliberate rather than careless.**
The reaper is a *last* resort against a hung cell; what protects a co-tenant is the **yield watch**,
which stands down cooperatively within seconds of another process appearing — it did exactly that
four times between 01:32 and 03:25 today. Over-covering the reaper costs an idle poll; under-covering
it costs the delivery step, which is what happened to `idaac` at 18:37.

Against the measured `idaac` cell (5 h training + 10 h evaluation ≈ 15 h) the derived budget is a
~1.3x margin on a slower off-policy family. If `drqv2` trains at 20 frames/s rather than `idaac`'s
33.7, 600k frames is ~8.3 h and the 12 h `CELL_TIMEOUT_SECONDS` still holds.

**The payload is already on the host**, staged 2026-09-09: `~/rlvigen-work/payload-v208-rlvigen.tgz`,
277,571 bytes, sha256 `b0fed801ef6cd694…`, matching the local copy byte for byte. It verifies against
`--require-runner-contract 19 --require-families rlvigen --require-evaluator-identity`, which every
`payload-v205-*.tgz` in the repo fails (they report contract 14).

- **No `NATIVE_VENV_HOST`.** Retracted above: the only prebuilt env has `"editable": []` and cannot
  run an `rlvigen` cell. The pip-cache path is what both current cells use.
- **`NATIVE_ACCEPT_SAME_DEVICE=1` is an owner-level acceptance**, not a workaround — the refusal
  above says so in those words, and the campaign has been running under it.
- **`NATIVE_VRAM_CAP_MIB` is required whenever a GPU is requested** (`run_on_production_host.sh:165`)
  and, per note 26, bounds evaluation rather than the trainer. Set it, and do not read it as
  protection for a co-tenant; the free-memory floor is what does that.
- **The payload must be rebuilt.** Every `payload-v205-*.tgz` in the repo reports *"built for runner
  contract 14 but this runner needs 19"*. `payload-v208-rlvigen.tgz` is built and verifies against
  contract 19 with `--require-evaluator-identity`.

## The sequencing this implies

1. `ppg` reaches 600k at roughly **15:39 MSK** (450,560 at 14:47, ~173k frames/hour), then runs its
   own curve and endpoint evaluation outside the cell timeout.
2. `idaac`'s endpoint grid finishes at roughly **16:04 MSK** (22 of 44 rows at 14:47, ~210 s/row),
   well inside its 18:37 reaper.
3. **Collect both**, which frees nothing on disk but retires both watches and their floors.
4. Only then launch `drqv2`, with an allowance sized against the `avail` that actually exists at
   that moment rather than against today's.
