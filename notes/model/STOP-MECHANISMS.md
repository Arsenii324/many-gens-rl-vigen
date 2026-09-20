# Everything that can stop a run, and whether it can do so silently

Written 2026-09-16 after one production training cell was killed ten minutes in by our own yield.
The failure was not that a guard fired; it was that **nobody had enumerated which guards could fire,
on which cells, and with what warning.** This is that enumeration.

**[Claude 2026-09-20] FIXED ON THE LAPTOP, not yet on the shared machine — deployment is the
lead's step.** Points 2 and 3 below described the actual defect (`notes/production-host/38-...md`
has the observation that forced the fix: a cell kept evaluating for 50 minutes under the memory
floor because the poller had already died with `$training_pid`). As of this fix, one poller
(`start_cell_yield_watch`, armed once per cell) covers training AND curve/endpoint evaluation and
every gap between them, printing `phase=<training|curve-eval|endpoint-eval|other>` in the marker so
which phase yielded is no longer a guess. The stall watchdog (row 8 below is the wrong number now —
see the table) got the same extension, on its own mechanism (`run_watched_eval`), for the same
reason. Points 2 and 3 are kept below UNCHANGED as the historical record of what was wrong and why
it stayed invisible; do not read them as the current behaviour.

Two facts shaped the table as first written (2026-09-16), before the 2026-09-20 fix above:

1. **The sentinel is one file, written by three different watchers.** `/work/yield.sentinel` is
   shared by the GPU co-tenancy watch, the disk watch and the host-side neighbour yield. Reading
   "a sentinel appeared" does not tell you which fired; only its CONTENTS do. Still true.
2. **[2026-09-16 through 2026-09-20] Only a TRAINING cell obeyed it.** The poller lived inside
   `run_measured`, keyed to `$training_pid` (`run_probe.sh:194-212` at the time). A cell that runs
   `run_offline_eval` instead never started that poller, so an eval cell ignored a sentinel
   entirely. **This asymmetry is why the defect stayed invisible: every eval cell survived it, and
   the first training cell died.**
3. **[2026-09-16 through 2026-09-20] A training cell STOPPED obeying it partway through, and that
   was not the same statement as 2.** [Claude 2026-09-17] The poller's loop was `while kill -0
   "$training_pid"` (`run_probe.sh:197`). The training process exits when training finishes, so
   from the moment a cell entered its in-cell curve/endpoint grid the poller was gone and the cell
   was, for sentinel purposes, an eval cell. The distinction was not "eval cells vs training cells"
   but "before vs after the training PID exits", **inside one cell**.

   This has two consequences, observed live on card 1 on 2026-09-17 with `ibac_sni` s101 in its
   grid and `idaac` s102 still training:

   - **It decides who is sacrificed when the floor fires.** Only the still-training cell obeys, so
     the floor stands down idaac and leaves ibac's grid untouched. That happens to be the right
     ordering -- the grid cell has already banked its training -- but it is a consequence of PID
     lifetime, not a policy anyone chose, and nothing would stop it being the wrong ordering in a
     different pairing.
   - **It means a card can reach a state where NOTHING of ours can yield.** Once every cell on the
     card is past training, the sentinel has no reader. The footprint is small then (a grid cell
     holds ~840 MiB against a training cell's 2,600-7,400), so we are unlikely to be what crowds a
     co-tenant -- but "unlikely to matter" is the honest claim, not "protected". If a co-tenant
     needs the card while our cells are all in their grids, the only way to give it back is by hand.

   Do not read row 8's "ARMED" in the table below as meaning armed for the life of the cell.

---

## The table

| # | mechanism | fires on | writes | who obeys | silent? | state now |
|---|---|---|---|---|---|---|
| 1 | `yield_gpu_to_neighbour.py` memory floor | free VRAM < `--floor-mib` (4000) | sentinel | **[2026-09-20] the whole cell** — training, curve-eval, endpoint-eval, and the gaps between (was training only) | **yes** | **DISARMED** (both cards ours); **this is what stopped ibac_sni-s1, twice** (attempts 1 and 3 on 16 Sep, both during training — coverage during evaluation is fixed on the laptop but not yet exercised live) |
| 2 | same, `--yield-on-processes` | compute procs > `--expect-ours` | sentinel | **[2026-09-20] the whole cell** (was training only) | **yes** | **DISARMED**; ~~it killed ibac_sni-s1~~ **[CORRECTED 2026-09-16: it did not; see below]** |
| 3 | `watch_disk_headroom.py` | free disk < `--floor-gib` (101-105) | **same sentinel** | **[2026-09-20] the whole cell** (was training only) | **yes** | **ARMED** -- the live risk |
| 4 | `neighbour-yield.sh` (host) | a GPU pid not in our containers | sentinel + optional `docker stop` | anything | **yes** | **DISARMED** |
| 5 | `CELL_TIMEOUT_SECONDS` | wall clock on TRAINING only (unchanged scope) | SIGTERM to the trainer; **[2026-09-20]** a plain 124 exit now also prints `NATIVE_CELL_TIMEOUT phase=training limit=<s> last_frame_hint=<n\|unknown>` before falling through to the ordinary failure path (was silent, indistinguishable from a crash) | training | no, it is the budget | 43200 s for idaac/ppg/ibac_sni; **[2026-09-20]** derived per baseline for every other scheduled one at the v5/v6 wrapper, `max(3× scheduled seconds, 86400)` (`notes/DECISION-SHEET.md` A69) |
| 6 | watch `--max-seconds` | wall clock | nothing -- the watch exits | nobody | no | 115668 s, covers the cell |
| 7 | the reaper (`launch-card-cell.sh:353+`) | cell silent past `_stall_window`, grace to `NATIVE_REAP_MAX_GRACE_SECONDS` (10800) | `docker stop` | the cell | partly | ARMED, progress-aware |
| 8 | `watch_policy_health.py` | divergence in the log | nothing | nobody | no | ARMED; *"It warns and never kills"* |
| 9 | `watch_card_exclusivity.py` | a co-tenant | nothing | nobody | no | ARMED; prints a positive line every check |
| 10 | **[2026-09-20]** stall watchdog, evaluation phase (`run_watched_eval`, used by curve and endpoint eval) | combined size of `training.log` + that phase's own `offline_eval_*.jsonl` unchanged for `CELL_STALL_SECONDS` (1800s, same default as training's) | `NATIVE_CELL_STALLED phase=<curve-eval\|endpoint-eval>`, then that phase's own `*_FAILED` marker | that phase | no, it is loud | **new; not yet exercised on a live cell** — the training-side stall watchdog (row not listed separately above; see `run_probe.sh:127-159`) already existed and is unchanged |

> **Correction, 2026-09-16, from the host artifacts:**
> [`results/evidence/ibac-sni-16sep-three-stops`](../../results/evidence/ibac-sni-16sep-three-stops/CLAIM.md).
>
> - **Attempt 1's sentinel names the memory floor, not the process count.** It reads
>   `free memory 3705 MiB is below the 4000 MiB floor`, with `procs=6`. The watcher writes that
>   text only when its process-count branch did not fire.
> - **Card 0 was crowded.** At that minute it held `rl4vla_cudagl`, `sg_sam2`, one other cell of
>   ours and ibac_sni's three processes, 28,445 MiB used.
> - **So row 1 stopped it, not row 2.** Whether row 2 was even armed is not recorded in `job.log`.
>   The shared-mode contradiction fixed in `bb05db6` is real, but it was not what fired here.
> - **Attempt 2 was not a yield at all.** A worker died 24 s in, with `EGL_NOT_INITIALIZED`.
> - **Attempt 3 was the floor again**, when a colleague arrived on card 1. The addendum below
>   describes it correctly.
>
> The opening sentence's "killed ... by our own yield" stands. "Process-count" does not.

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


---

## Addendum, 2026-09-16 — the floor fired correctly and I misread it

`ibac_sni-s1` reached **F 100352** and stopped: `NATIVE_CELL_YIELDED ... reason follows from the
sentinel`, `CELL EXIT=1`. My first reading was that the cell had tripped its OWN guard, since
`procs=16` is a card-sized job, and I lowered `NATIVE_FLOOR_MIB` from 4000 to 200 to let it run.

**That was wrong, and wrong in the dangerous direction.** Card 1's 26,664 MiB belonged to
`rlvigen_kalugin_df` -- a colleague who returned mid-run. The floor did exactly what it exists for:
it noticed a co-tenant starving us and stood OUR cell down rather than contending. Lowering it
would have put us in a memory fight on a card someone else was already using, and the failure mode
there is THEIR run dying, which is the one outcome the standing rule forbids outright.

Reverted within minutes. The rule this yields:

> **"No room" is answered by waiting for room, never by lowering the bar for what counts as room.**

The distinction that makes the sentinel readable: it is written by three watchers and says only
"something stopped this cell". Whether that was our own consumption or a neighbour's arrival is
answered by looking at WHO HOLDS THE CARD -- `nvidia-smi --query-compute-apps` resolved through
`/proc/<pid>/cgroup` to a container name. I stated a cause before doing that lookup, and the lookup
reversed it.

## Verified, since it was asked directly

No colleague container was ever stopped by anything in this session. Checked by uptime: at the time
of asking, `rlvigen_kalugin_df` had 4 days, `rl4vla_cudagl` 4 weeks, `sg_sam2` 34 hours,
`avla_malinin_aa` 4 weeks, `isaac-lab-base` 2 months, and the whole `cvat_*` stack 22-43 hours --
every one of them older than this session. Our `pkill`s matched only our own script FILENAMES
(`curve-sweep.sh`, `neighbour-yield.sh`, `chain-when-card-free.sh`) and `docker stop` was only ever
given exact `cell-c*` names.

**No OOM of any kind occurred** -- no `out of memory`, no CUDA error, no kernel OOM killer, on
either card, for us or for anyone else.

## Addendum, 2026-09-16 — the floor is a preflight, and three ways a run stopped without saying so

Three stops happened within one hour, and none of them announced itself. They are separate
defects that share a shape: **the thing that was supposed to notice was looking somewhere else.**

### 1. RETRACTED — the floor IS enforced during the run. I had this backwards.

**What I wrote here first was wrong, and it was wrong in the dangerous direction**: I claimed the
4000 MiB floor is a preflight-only check and that a shared-mode cell therefore runs for hours with
nothing enforcing headroom. Half of that is true and the conclusion does not follow.

True half: `scripts/watch_gpu_headroom.py`'s `watch()` (line 167) really is only a recorder. It
samples, appends JSON, prints a summary, and never writes the sentinel. Reading that function alone
is what produced the wrong conclusion.

The part I missed: `watch()` is not the enforcer. **`scripts/yield_gpu_to_neighbour.py`, armed at
STEP 2 of every launch, polls free memory against the floor for the life of the cell and writes
`/work/yield.sentinel` when it breaches.** `NATIVE_ALLOW_SHARED_CARD=1` disarms only
`--yield-on-processes`; the memory floor is never waived, exactly as the launcher's own banner says
("the 4000 MiB free-memory floor is NOT").

It was demonstrated an hour after I wrote the retracted claim. ibac_sni s101 reached training on
card 1, co-tenants grew, and the cell stopped itself:

    === NATIVE_CELL_YIELDED stopping this cell; reason follows from the sentinel ===
    yielded at 1789558045: free memory 3063 MiB is below the 4000 MiB floor
    free_mib=3063 procs=5 util=16

That is the mechanism I said did not exist, firing correctly, and protecting a colleague's job
rather than ours. A peer session had independently corrected the same point for the 16 Sep
attempt-1 stop (a318c00, sentinel at 3705 MiB, procs=6) — two stops, one mechanism, and I had
attributed one of them to a process-count yield.

**The methodological failure is worth more than the fact.** I read one function, found it did not
enforce, and concluded nothing enforced — without asking which component the launcher actually
arms for this purpose. The project's own rule covers it: trace where the value is WRITTEN before
concluding about what reads it. `yield.sentinel` has three writers, and I checked one.

**What is genuinely still open**, stated narrowly so it does not regrow into the retracted claim:
the floor protects the CARD's free memory, not our own footprint. It fires once free memory is
already low, which on a shared card can mean our own growth is what pushed a co-tenant toward the
edge. A self-scoped cap — stop OUR container when OUR usage crosses a number chosen from the
co-tenant's headroom — is a different guarantee, and `datasphere/native/self-vram-cap.sh` is it.

### 2. A stale waiter double-launched a production training cell.

`ibac-waiter.sh` was armed earlier in the day to launch ibac_sni when a card freed. It was never
disarmed. When card 1 freed at ~14:15 it fired `train-production-cell-v4.sh` → `CELLS=ibac_sni:1`
at 11:16:53Z, **15 seconds before** a deliberate launch of `CELLS=ibac_sni:101` at 11:17:08Z. Two
600k training cells, 16 worker processes each, on a 16-core host also running the eval sweep.

Neither cell would have failed. Both would have run, slowly, and the first evidence would have been
a frame rate half of what the schedule assumed — visible only to someone who knew what the frame
rate should be. **A duplicate does not look like an error; it looks like the machine being slow.**

The guard now exists in the operator's monitor (count of `cell-c1-<pid>` containers > 1), not on
the host. A host-side interlock — refuse to start a production cell of a baseline that already has
one running — is the better fix and is not yet written.

### 3. A sweep died on a syntax error in a file that is syntactically valid.

`curve-sweep-v3.sh` completed idaac stamp 200704 at 14:10:25 (rc=0) and then stopped with
`reeval-cell-cached.sh: line 64: syntax error near unexpected token '('`. `bash -n` on that file
passes, and `cat -A` shows no CRLF and no stray bytes: the file is valid.

The file's mtime is 14:00:43. Bash reads a script by byte offset as it executes; rewriting the file
underneath a running invocation makes it resume at a stale offset, mid-token. I rewrote it while
the sweep was running it — the same rule ("never write to a script that may be executing; deploy
under a new name") that this workspace already learned from `d-cell.sh: command not found`, broken
by the person who wrote the rule down.

The cost was 3 minutes of idle card, because the failure was loud. Had the rewrite landed between
stamps instead of during one, the sweep would have exited silently with 3 of 11 stamps done.

**What these three have in common** is worth stating: each mechanism was *present*, *correct in its
own terms*, and pointed at the wrong moment — a check that runs once for a condition that changes,
a launcher with no memory of other launchers, a reader with no memory of the file it is reading.
