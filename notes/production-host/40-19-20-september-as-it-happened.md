# 40 — 19–20 September as it happened: the chronology moved out of the state document

Filed 2026-09-20 23:28 MSK by Claude. `CURRENT-STATE-AND-RESPONSIBILITY.md` is meant to be rewritten in place;
over 19–20 Sep I appended to its §2 four times instead, so it read as layers of "earlier the same
day". Those paragraphs are moved here VERBATIM, newest first, as the log of what happened. Nothing
in them is current state any more; the state document's §2 now says only what is true.

Two facts from the night of 20 Sep that were in no file until now:

- **Card 0's holders on 20 Sep, from the occupancy log:** our `drqv2` cell alone until 16:56; a
  labmate's bare-host job (`no-container`, ~26–31 GiB) from 16:56; ours stopped at 17:46; the card
  EMPTY 18:29–18:32 — three minutes, a restart between that person's jobs — then held again until
  22:33, and empty from 22:33. So a short vacancy on this card is as likely a restart as a departure,
  which is what the sustained-vacancy rule is for, and I had called the card "only just free" from a
  COUNT of holder-free minutes before reading the timestamps.
- **The owner, 20 Sep ~23:00:** no runs overnight; card 0 stays unused unless they say otherwise;
  `drqv2`'s deferred evaluation is the natural first use of a free card when they do.

---

**NOTHING OF OURS IS RUNNING (as of 2026-09-20 17:49 MSK, read from the host) except the read-only
occupancy logger. No waiter is armed. The owner asked for NO further runs for now** (wrap up; defer
what can be done separately in a few days).
- **`idaac` s103 COMPLETED** at 17:45 (`card1-20260920-011652`, `CELL EXIT=0`, 598 records) — it ran
  its last hours beside `rlvigen_kalugin_df`'s 21.5 GiB on card 1 without incident. Collection is
  the next step; its outputs are being copied to `fetched/`.
- **`drqv2` s101 TRAINED to 600k, EVALUATION DEFERRED** (`card0-20260920-094616`). First native
  cell: ~32 FPS on the V100 (DataSphere T4: 26.05), 5.2 h of training, **38.5 GiB RAM at full
  replay, measured** (computed: ~40). I stopped it at 17:46 during its curve evaluation (7 of 13
  stamps begun) because a labmate's bare-host job took 26 GiB of card 0, leaving 5.4 GiB free, and
  our floor-yield watcher for that cell was no longer running. 12 checkpoints (50k–600k) plus
  `snapshot.pt` are retained in `native-out` and being copied to the laptop; the evaluation can be
  run any day from them with `host-scripts/reeval-cell*.sh`. The yield watcher had exited because
  it had FIRED: it wrote the sentinel at 16:57 and our evaluating cell ignored it — a real defect,
  `production-host/38`. All 12 checkpoints and `snapshot.pt` are now also on the laptop
  (`fetched/card0-20260920-094616`, 1.6 GB, three hashes checked against the host).
  **Its training curve, read from its own `train.csv`:** mean training-episode reward 52 over the
  first 50k frames, 266 by 100k, **457 by 150k, then 455–476 all the way to 600k** (ceiling ≈ 488;
  random floor 1.84; `idaac` reaches ~35), at a steady 31 FPS, 5.37 h. So this native solves the
  TRAINING scene within a quarter of the budget, as the 100k exploratory runs and RL-ViGen's own
  published shape said it would. What it retains under the visual shifts is what the deferred
  evaluation will show — training-episode reward says nothing about that.
- Deployed to the host at 17:49, with the previous copies kept as `*.before-20260920-swap`: the
  fixed `wait-and-train-v4.sh` (contiguous vacancy samples) and both wrappers (refuse a slow
  baseline without `TIMEOUT_S`); hashes equal the laptop's; the refusal was exercised on the host.

**Earlier the same day — two cells were running (as of 2026-09-20 09:53 MSK, read from the host).** (1) **`drqv2` s101 — the first
native production cell** — run `card0-20260920-094616`, container `cell-c0-605720`, **card 0**,
launched 09:46 by hand through `train-production-cell-v6.sh` after a passing dry run, with
`TIMEOUT_S=86400` explicit and a 77 GiB disk floor; recorded; watched by its own `watch-cell.sh
trip`. Card 0 is usable because both cards are booked for our group for ~3–4 days (owner, 20 Sep;
§7b rulings) — with consideration for the colleague the booking is under. (2) `idaac` s103 on
card 1, below — it finished training overnight and is in its evaluation grid. No third cell: host
RAM is unbounded by any guard and a native cell's RAM (computed ~40 GiB) is being measured by (1).

**The first of the two, as written at launch (2026-09-20 01:23 MSK, read from the host): `idaac` s103**, run `card1-20260920-011652`,
container `cell-c1-119658`, card 1, launched 01:16 by `wait-and-train-v4.sh` after 12 genuine
post-restart clear samples; recorded in `results/host-runs.jsonl`; watched by `watch-cell.sh trip`
(disk floor 65 GiB). Both cards had sat empty for three hours after the reboot. It is the second
launch: the first, two minutes earlier, was stopped by me during its apt bootstrap because the
derived disk floor was 307 GiB of 325 free — the reboot had cleared other tenants' data, so their
ordinary return would have tripped it; relaunched with `NATIVE_DISK_ALLOWANCE_GIB=260`. The
occupancy logger was restarted at 01:02 for 40 h.

**What happened before that (19 Sep 22:07 MSK, read from the host): nothing of ours was running.** The host crashed
at ~21:25 MSK and booted again at 22:05 — `last -x` shows no `shutdown` record, so it was not an
orderly reboot; every tenant's containers were lost and both cards read 0 MiB. **It was not us:** our
cell's last resource sample (21:25) shows ~8.6 GiB of RAM in total (trainer 3.05 GiB, four loader
workers ~1.4 GiB each) on a 125 GiB host, 2,797 MiB of VRAM, GPU util 0; card 0 carried the other
groups' 27 GiB at 90% util. Cause unknown. The occupancy logger died with the host and is NOT
running — the vacancy rule cannot be applied until it is restarted.
**`svea` s101 attempt 2 is recorded failed, and must not be relaunched as it was:** it reached
frame 9,000 in 35 minutes — **~2.4 FPS with GPU util 0** — against the ~14 FPS its 12-hour training
budget requires, so the reaper would have stopped it near 100–180k frames. Suspected, not proven:
the Places365 overlay loader running with `RLVIGEN_PLACES_WORKERS=0`, the silent default at
`run_probe.sh:2206`, reading JPEGs synchronously from the shared mount. `production-schedule.json`
calls `svea`'s throughput "measured" — on DataSphere, not on this host with this corpus mount.
What the paragraph below says about that launch is history.

**Established 2026-09-20 01:05 MSK, from the code history and the schedule file:**
`run_probe.sh` has defaulted `RLVIGEN_PLACES_WORKERS` to 0 since 2026-09-08 (`a2c38bc`) because
more than zero overlay-loader workers corrupted the heap intermittently on DataSphere
(`malloc_consolidate(): unaligned fastbin chunk detected`; the comment block above
`run_probe.sh:2206` has the job ids). `production-schedule.json`'s throughput for the three
Places365 baselines — `svea` 9.99, `sgqn` 6.5, `soda` 3.25 frames/s, marked "measured" — was in the
file by 2026-09-04, i.e. measured under the 8-worker loader that was then banned, and never
re-measured. The only figure at 0 workers is this cell's: **~2.4 frames/s**, one 35-minute sample
on a shared host with a cold file cache, which is ~69 h of training per seed against the schedule's
16.7 h. Separately, **the launch used the wrapper's default `TIMEOUT_S` of 43,200 s (12 h)**, below
even the schedule's own 16.7 h for `svea` (and 25.6 h `sgqn`, 27.1 h `rad`, 51.3 h `soda`): the
training timeout must be set per baseline from the schedule, and nothing enforces that.

**[history, 19 Sep 20:42–21:25] `svea` s101, the first cell of the RL-ViGen five and the first Places365 cell.**
Run `card1-20260919-204235`, container `cell-c1-1272142`, card 1, launched 20:42 MSK on 19 Sep with
the owner present, recorded in `results/host-runs.jsonl`, watched by `watch-cell.sh trip` (disk
floor 55 GiB). It is the second attempt. The first (`card1-20260919-203001`) died before training:
`run_probe.sh` ran `check-asset` on a *mounted* Places365 corpus and tripped on
`PLACES365_EXPECTED_COUNT: parameter null or not set` — a path no cell had ever exercised. Fixed in
`6458c05`, shipped as `payload-v216-rlvigen.tgz`; the live log shows
`NATIVE_PLACES365_ASSET_CHECK_SKIPPED` and the loader reading the full train split. It also exposed
`record_host_run.py` writing `seed: None` for a hydra-style cell (fixed, `415687c`).
**Why this cell matters more than its one-in-36 share:** `docs/RESEARCH-FRAME.md` identifies the
across-method contrast only *inside* the RL-ViGen five, and until now that subgroup had no
production cell at all — every completed cell is on-policy, and every one fails the competence gate
(`production-host/36`). This run also yields the first RAM and wall-time measurement of a native
cell on this host, which is what decides whether two can ever share it.
**No second cell beside it, by the numbers:** one `rlvigen` cell (4,549 MiB peak) survives the
co-tenant returning at its observed 21,298 MiB with 6,647 MiB free; two leave 2,098, under the
4,000 floor, and both yield. No waiter is armed: the `idaac` s103 waiter described here until
2026-09-19 ended on the evening of 18 Sep (`HANDOFF.md`). The on-policy queue that paragraph named
(`idaac` s103, `ibac_sni` s102 from zero and s103, `ppg`'s two seeds) is still unrun; whether it or
the native five should get the next free card is an open ordering question for the owner.
