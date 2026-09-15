# Everything that can stop a run, and whether it can do so silently

Written 2026-09-16 after one production training cell was killed ten minutes in by our own yield.
The failure was not that a guard fired; it was that **nobody had enumerated which guards could fire,
on which cells, and with what warning.** This is that enumeration.

Two facts shape the whole table:

1. **The sentinel is one file, written by three different watchers.** `/work/yield.sentinel` is
   shared by the GPU co-tenancy watch, the disk watch and the host-side neighbour yield. Reading
   "a sentinel appeared" does not tell you which fired; only its CONTENTS do.
2. **Only a TRAINING cell obeys it.** The poller lives inside `run_measured`, keyed to
   `$training_pid` (`run_probe.sh:194-212`). A cell that runs `run_offline_eval` instead never
   starts that poller, so an eval cell ignores a sentinel entirely. **This asymmetry is why the
   defect stayed invisible: every eval cell survived it, and the first training cell died.**

---

## The table

| # | mechanism | fires on | writes | who obeys | silent? | state now |
|---|---|---|---|---|---|---|
| 1 | `yield_gpu_to_neighbour.py` memory floor | free VRAM < `--floor-mib` (4000) | sentinel | training only | **yes** | **DISARMED** (both cards ours) |
| 2 | same, `--yield-on-processes` | compute procs > `--expect-ours` | sentinel | training only | **yes** | **DISARMED**; it killed ibac_sni-s1 |
| 3 | `watch_disk_headroom.py` | free disk < `--floor-gib` (101-105) | **same sentinel** | training only | **yes** | **ARMED** -- the live risk |
| 4 | `neighbour-yield.sh` (host) | a GPU pid not in our containers | sentinel + optional `docker stop` | anything | **yes** | **DISARMED** |
| 5 | `CELL_TIMEOUT_SECONDS` | wall clock on TRAINING only | SIGTERM to the trainer | training | no, it is the budget | 43200 s for ibac_sni |
| 6 | watch `--max-seconds` | wall clock | nothing -- the watch exits | nobody | no | 115668 s, covers the cell |
| 7 | the reaper (`launch-card-cell.sh:353+`) | cell silent past `_stall_window`, grace to `NATIVE_REAP_MAX_GRACE_SECONDS` (10800) | `docker stop` | the cell | partly | ARMED, progress-aware |
| 8 | `watch_policy_health.py` | divergence in the log | nothing | nobody | no | ARMED; *"It warns and never kills"* |
| 9 | `watch_card_exclusivity.py` | a co-tenant | nothing | nobody | no | ARMED; prints a positive line every check |

## Why #3 is the one to watch

Disk is the only silent killer still armed, and it is armed for a reason: filling a **shared**
filesystem breaks every writer on the machine, which is the one harm worse than losing our own run.
So it stays.

Its margin is thin and moves for reasons outside our control. Right now: **117 GiB free against
floors of 101-105 GiB**. Our own cells write little -- a curve cell is ~400 MB -- and the fall from
262 GiB yesterday morning is other users' docker (325 GB of images machine-wide).

**If it fires:** the training cell stops with `NATIVE_CELL_YIELDED`, the sentinel says
`free_gib=...`, and every checkpoint written so far survives on the bind mounts. The run is
resumable only in the sense that its stamps are still EVALUABLE -- `families.json:160` bars true
resumption for the off-policy five because `keys_to_save` omits the replay buffer.

**What I would do:** not clear the sentinel and restart blindly. First read it to learn which
watcher fired, because the same file means three different things. If disk, the honest options are
to wait, or to stop packing so fewer cells write -- not to raise the floor, which converts a
guarded stop into an unguarded one.

## Why disk cannot simply be reclaimed

13.4 GB sits in 18 of our own run dirs with **0 records and 0 checkpoints**. It cannot be deleted
as `varaksin_as`: the files were written by root inside containers and `rm` returns
`Permission denied`. Removing them would need a root container doing `rm -rf` on a shared
filesystem, which is a worse risk than the 13 GB is worth. Recorded so the next person does not
rediscover the permission wall.

## The rule this produced

**A guard that can stop a run must be enumerated before the run starts, not after it dies.** The
ibac_sni failure was avoidable by reading three lines of the launcher. Specifically:
`NATIVE_ALLOW_SHARED_CARD=1` and `NATIVE_YIELD_ON_PROCESSES=1` are contradictory -- the first says
co-tenants are expected, the second says stop when one appears -- and the launcher now refuses to
arm the second in shared mode, on either card.
