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
`ppg`** (sha256 `72053d1e78d0`). One venv serves all of them, and `~/rlvigen-env/torch-02805cc0-94c1577b2cd9`
is already built and already in use by both running cells. `drqv2` points `NATIVE_VENV_HOST` at the
same directory: no `pip`, no two-hour bootstrap, and **no additional disk**.

*(Measured properly on the second attempt. The first comparison ran `filtered-requirements --family`,
which is not the flag; every family hashed to `e3b0c442`, which is sha256 of the empty string. A
check that agrees with nothing agrees with everything.)*

## A plan item this closes in the negative

`notes/RUNNING-ON-PRODUCTION-HOST.md` and the standing plan both ask for a **durable second location
for results**, so that a 45-hour cell does not lose everything if the host disk fails. **There is
nowhere on this host to put one.** `/dev/sda2` is the only filesystem with space; `/dev/sda3` is a
975 MB `/boot`. The second location has to be off-host, which makes it a transfer policy rather than
a mount, and that is a different piece of work from the one the plan describes.

## The sequencing this implies

1. `ppg` reaches 600k at roughly **15:39 MSK** (450,560 at 14:47, ~173k frames/hour), then runs its
   own curve and endpoint evaluation outside the cell timeout.
2. `idaac`'s endpoint grid finishes at roughly **16:04 MSK** (22 of 44 rows at 14:47, ~210 s/row),
   well inside its 18:37 reaper.
3. **Collect both**, which frees nothing on disk but retires both watches and their floors.
4. Only then launch `drqv2`, with an allowance sized against the `avail` that actually exists at
   that moment rather than against today's.
