# Current state and responsibility — read this first, especially after context loss

**Last updated: 2026-09-19, 21:14 MSK, by Claude** (header, §1 tallies, §2's live-cell paragraph and §7b; the rest of §2–§7 was last reviewed 2026-09-18). This file says what is *true right now*. It is
**kept current, not appended to** — if you are adding a dated section to the bottom, you are using
the wrong file; put it in [`production-host/`](production-host/) as a numbered note and update this
one in place. [`START-HERE.md`](START-HERE.md) indexes what each surface is *for* and does not go
stale; this one does, so distrust it and re-run the commands in §1.

The previous version of this file was from **2026-09-06** and described the pre-production freeze
sequence — three evaluator-validation waves, a wave awaiting spend authorization, Codex coordination.
All of that is finished. It is preserved in git history rather than here, because a "current state"
file carrying ten days of superseded state is how a reader ends up acting on the wrong world.

---

## 1. Run these before trusting anything below

```bash
python scripts/production_gates.py | tail -3    # is the fleet launchable, recomputed from the tree
python scripts/campaign_status.py | tail -3     # coverage per baseline and seed
python scripts/export_fleet.py | tail -3        # rows, and how many are on the CURRENT closure
python scripts/operator_readiness.py | tail -3  # can an operator get from zero to results
python scripts/open_decisions.py | tail -3      # what awaits a person
```

As of the last run (2026-09-20 01:23 MSK, `campaign_status.py` and the strict ledger audit only):
campaign **36 cells: 31 MISSING, 3 DONE, 1 RUNNING, 1 PARTIAL**; audit exit 0. Gates were **37 pass /
0 fail / 9 owner** at 21:14 on 19 Sep. One cell of ours is running (§2). **The waiter that launched it is STILL RUNNING on the
host (pid 119610) and stays alive for the life of the cell** — it supervises the VRAM self-cap.
[Corrected 01:42 MSK 20 Sep: this said it had exited. It had not, and a pre-deploy check refusing
to overwrite `wait-and-train-v4.sh` is what showed it. Do not overwrite that file, or arm a second
waiter, until `idaac` s103 ends.]

**The narrative account, with every number's command beside it:**
[`CAMPAIGN-REPORT-2026-09-18.md`](CAMPAIGN-REPORT-2026-09-18.md).

## 2. Where the campaign actually is

**Three baselines have production-length rows. Three cells count as DONE and one as PARTIAL.**

| baseline | seed | state | rows collected | note |
|---|---|---|---|---|
| `ppg` | 1 | complete | 88 endpoint + 528 curve | seed 1 is outside the schedule's `{101,102,103}`, so the counter reads it as MISSING (below) |
| `idaac` | 101 | complete (DONE) | 569: 484 curve + 85 of 88 endpoint | stopped by the watch budget during the second endpoint pass on 2026-09-09 |
| `idaac` | 102 | complete (DONE) | 598: 484 curve + 88 endpoint | trained 7 h 15 min, grid about 13.5 h; finished 18:43 on 2026-09-17 |
| `ibac_sni` | 101 | complete (DONE) | 910: 528 curve + 88 endpoint + training-curve rows | trained 31.5 min at 16 processes, grid about 14 h; finished 11:16 on 2026-09-17 |
| `ibac_sni` | 102 | PARTIAL | 308 curve rows from seven salvaged stamps | attempt 1 stopped by the memory floor at 28,672 frames and kept nothing; attempt 2 stopped by it at 376,832 frames. The seed needs a rerun from zero (OPERATOR-GUIDE §6c) |

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
**Why those five and not the other
27:** [`production-host/35-what-the-campaign-costs-at-measured-rates.md`](production-host/35-what-the-campaign-costs-at-measured-rates.md)
puts the measured 15–21 hours per cell against 32 missing cells. The full campaign cannot finish on
this host; the sampled-estimand block can.

**The operator's cold start is no longer untested.** On the night of 17–18 Sep a fresh tree
(`git archive HEAD` — what a clone gives you) was reconstructed inside a container on the host and
taken all the way through: `bootstrap_sources.py`, `verify_sources.py`, then `build-payload`,
`verify-payload` and `verify-evaluator-binding` for **all seven families**, every exit code 0.
Evidence: [`results/evidence/linux-reconstruction-from-a-fresh-tree`](../results/evidence/linux-reconstruction-from-a-fresh-tree/CLAIM.md).
What remains untested there is a fresh clone taken to a *running cell*, and any host but this one.

**The first three-baseline same-axes reading exists**, in
[`production-host/34-first-three-baseline-reading-2026-09-17.md`](production-host/34-first-three-baseline-reading-2026-09-17.md).
It is a reading and not a result: one seed per baseline against a policy requiring three. Two things
in it are worth carrying — `eval-medium` scores below `eval-hard` in all three.

**The second claim that note made did not survive a second seed.** It read the train → eval-easy drop
as a ranking (`ibac_sni` −48%, `ppg` −21%, `idaac` −17%). At 15:30 `idaac` s102 gave the same baseline
**+18%** against s101's −17%: the gap changes *sign* between seeds, and a 35-point swing from the seed
alone is larger than the spread the ranking rested on. Do not quote a generalisation ranking from one
seed per baseline. `eval-medium` < `eval-hard` holds in both idaac seeds, so that finding stands.

**`ppg` still counts as MISSING, and that is not a mistake in the counter.**
`production-schedule-v100.json` names seeds `[101, 102, 103]`; ppg is banked at **seed 1**, so every
ppg column reads MISSING however good the rows are. The rows are valid — fixed in advance, not
outcome-selected, which is what `docs/EVAL-PROTOCOL.md` §4b requires. **Implemented default, awaiting
ratification: keep the run and record ppg's seed set as `{1, 102, 103}`** rather than spend eight
GPU-hours reproducing a number we have.

**Nine of twelve baselines have no production record at all**, and three of them are blocked on
things that are not compute:

- ~~`ibac_sni` has never completed a 600k cell~~ — **done 2026-09-16/17**, seed 101, 31.5 minutes of
  training at procs=16. The constraint that remains is memory that **stays** free: ~11.4 GiB
  (7,421 peak + the 4,000 floor). Counted from `results/host-runs.jsonl` at 21:05 on 2026-09-17:
  of ibac's **seven** failed attempts, **six** were the memory floor against a colleague's job and
  one (`card0-20260916-010515`) was an EGL worker dying 24 s in. Seed 102's first attempt launched
  two minutes after the co-tenant left and died eleven minutes in; its second waited out a
  15-minute absence and still died 32 minutes in, when the co-tenant returned. The ten-minute
  vacancy rule lowers this risk; it does not remove it.
- `ctrl` has never run at 600k and, at 32,435 MiB observed, cannot satisfy peak-plus-floor on a
  32,494 MiB card at all. It needs an empty card and an explicit decision about the floor.
- ~~`svea`, `sgqn` and `soda` are blocked on Places365~~ — **resolved 2026-09-18**: the full 26 GB
  corpus (1,803,462 files, 365 classes) is on the host, `verify_datasets` PASS, 200 sampled files
  sha256-identical to the laptop copy. `svea` s101's waiter was armed against it (`v6` wrapper,
  mounted read-only via `NATIVE_PLACES365_DIR_HOST`) for the rest of the day and **GAVE UP at 21:19
  without ever seeing a card window** — the card was occupied continuously, so the Places365 loader
  itself remains unexercised (§11.4 O6's own framing still holds: nothing has consumed the corpus
  at run time). **No gate ties a production run to the production dataset**, so a cell trained
  against the old 20-class fixture would still look correct if one ever ran against it by mistake —
  the corpus is a learning-affecting input, and that gap was never about availability alone.

Full audit with every number read first-hand:
[`production-host/33-what-we-actually-have-2026-09-16.md`](production-host/33-what-we-actually-have-2026-09-16.md).

## 3. The standing mandate (unchanged, and still the operating rule)

"Continue work autonomously; your ultimate goal is to finish the pre-production stage in full — not
'solve the problems seen now' but taking full responsibility and working on the long horizon."

**Don't treat "flagged, not fixed" as done.** A caveat is a pointer to unfinished investigation, not
a resolution. Go check it, or say plainly that checking it needs a compute run rather than more
reading, and only then park it.

**The two-layer decision model.** Every open question already has *some* behaviour running today.
"It's the owner's decision" is never a reason to leave that behaviour arbitrary — implement the
genuine best answer now; only the *formal* resolved/PASS status waits on ratification. The ppg seed
set in §2 is a live example of this being applied.

## 4. Constraints that no gate encodes — these are the owner's, not conveniences

1. **No global or host-wide changes.** Nothing installs outside a container. On the host: `docker`,
   `git clone`, `mkdir`, read-only inspection, and the scripts in `~/rlvigen-work`. Not arbitrary
   Python.
2. **Never CUDA OOM — ours or anyone else's, including spikes.**
3. **Never delete a container, image or directory without proof you created it** and that it did not
   exist before.
4. **Do not inspect other users' processes or directories.** `ps aux` is itself a hazard here.
5. **"No room" is answered by waiting for room, never by lowering a floor.** One stated exception,
   owner 2026-09-19, for `ctrl` only, whose peak cannot fit beside the floor on any card here — §7b
   item 6. It is an exception for a family that cannot otherwise run, not a precedent.
6. **A blocked action is a stop, not a puzzle.** It may encode context nobody wrote down.

Two more that the owner stated as standing, added 2026-09-19:

7. **`ppg`'s rollout quantum is not to be changed.** *"the ppg rollout quantum is different and
   shouldn't be changed unless I explicitly say later."* (18 Sep). It is why `ppg` checkpoints land
   near 51,200-frame spacing instead of 50,000 (`production-host/37`); that is accepted, not a bug
   to fix.
8. **Autonomy has an upper edge.** Careful, proven deletions and ordinary runs need no sign-off
    (*"I'm not against deletion/rm as a thing if it's very careful … I expect you're not blocked on
    'decisions' that are actually non-decisions"*), but *"the heavy-results decisions … like big
    deletes, big runs that could have real super-unintended consequence"* stay the owner's (19 Sep).

### Dated remarks — context for judgement, NOT constraints

The owner, 2026-09-19: *"I've given ones and then given the others. Maybe I changed my opinion over
time. Each was for its respective stage."* Each line below answered one situation on one day. None
of them decides anything today on its own: weigh it, prefer the owner's most recent word, and ask
if it would be the deciding reason. They are kept because they explain why things were done the way
they were ([`inventory-2026-09-19/owner-statement-sweep.md`](inventory-2026-09-19/owner-statement-sweep.md)
is the executor report they came from — a report, not a to-do list).

What each one was a reply to is NOT recorded here; the date is, and the transcript has the rest.

- 17 Sep: *"Yeah, don't be stopping health cells."* — `OPERATOR-GUIDE.md` §10.1 is the check that
  tells a quiet cell from a dead one.
- 16 Sep: *"Cuda oom wouldn't be good regardless of ours or theirs so 'no-yield' isn't a right
  policy I think"*. What runs today: the process yield may be off on a card shared by choice; the
  memory-floor yield and the disk watch stay armed (`notes/model/HARNESS-MODEL.md` §5).
- 18 Sep, about which host directories a disk survey may look at: *"'not just home' I meant only
  the varaksin_as user folder of course!"*
- 16 Sep: *"If any card is free for one of our runs, please try take."* and *"Due to limited
  compute, really use the most out of it."* — and on 19 Sep the owner named *"trying to run it in a
  way that'd over-contend the machine for OOM"* as not acceptable. `production-host/33` records why
  a sustained vacancy, not "the card looks free", became the launch trigger.

Governing detail: [`production-host/README.md`](production-host/README.md) and the 33 numbered notes
it indexes. Read the directory, not just its index.

## 5. What is measured, and the one number that still is not

Six of seven families have a measured VRAM peak (`datasphere/native/measured-vram-bounds.json`).
**`ibac_sni` at `procs=16` does not**, and three different figures for it were quoted as fact in a
single day — an estimate from a code comment, a 3-process measurement that under-counts because EGL
contexts are not compute apps, and a figure that was 94% a colleague's memory read through an
instrument whose docstring claimed a filter it did not have. That lower bound held, and it is now measured: **7,421 MiB** total at procs=16 — 2,199 compute plus 5,222 EGL — which needs 11,421 with the floor and so cannot share card 1 with its 21.3 GiB co-tenant.

**The rule that failure produced, and it is the most transferable thing in this file: before a number
decides anything, find where it was produced. A number in a comment is not a measurement.**

## 6. Self-corrections from this session — read before citing anything of mine

Two claims of mine were published and are now retracted **in place**, not edited away:

- **"The memory floor is enforced only at preflight."** False. `watch_gpu_headroom.py`'s `watch()`
  is only a recorder, but it is not the enforcer — `yield_gpu_to_neighbour.py` polls the floor for
  the life of the cell. I read one function, found it did not enforce, and concluded nothing did.
- **"The nine mode baselines are unaffected by evaluator nondeterminism."** False. Mode rows
  reproduce 282/800 episodes against sample's 264/800, so all twelve baselines are exposed. The
  mechanism is **open**.

Both live in [`model/STOP-MECHANISMS.md`](model/STOP-MECHANISMS.md) and
[`endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md`](endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md).

## 7. The host, operationally

Both cards are booked for us and **both carry other groups' containers in practice**.
`rlvigen_kalugin_df` holds ~21.3 GiB across two processes and cycles off and back on within tens of
minutes. Therefore:

**Size a launch against the co-tenant's RETURN, not against current free.** Worked example from
today: card 1 at 28,858 MiB free with our 2,635 MiB cell resident — adding a 7,146 MiB ppg cell
leaves 21,712, the colleague reclaims 21,298, free drops to 414, under the 4,000 floor, and **both**
our cells yield. Declining to launch kept the running cell alive. The second cell's real cost is the
first cell.

## 7b. Waiting on the owner — nine decisions, no default chosen

Each of these has real work behind it already; none has been decided for you. Items 1-3 are the
original three; 4-9 were added 2026-09-18 to consolidate everything else raised that session,
previously scattered across `ACCOUNTABILITY.md`'s dated entries and `OPERATOR-GUIDE.md`'s O-items
— gathered here so nothing needs to be hunted down separately.

**One list, since 2026-09-20.** Each item below now also exists as an A-item in
[`DECISION-SHEET.md`](DECISION-SHEET.md), which `python scripts/open_decisions.py` enumerates (69
sheet items). The A-item is the enumerable record — question, working value, the owner's words,
status, what would reopen it; the text below is kept in full as the reasoning behind it. How these
are handled, by the owner's instruction of that day: the lead sets and tunes the working values
and returns with finals for ratification.

| §7b item | A-item | state on 2026-09-20 |
|---|---|---|
| 1 budget vs scope | A59 | 600k kept as the working headline (RL-ViGen Table 6); `ibac_sni` 6M probe approved, deferred |
| — queue order | A60 | natives first, accepted by the owner |
| 2 card-0 vacancy rule | A61 | future-operator guidance only |
| 3 `ppg` seed 1 | A62 | handle last |
| 4 upstream-source archive risk | — | CLOSED, risk accepted by the owner |
| 5 `ctrl` in-loop evaluation cost | A63 | re-read in code 2026-09-20 (3× env work, logging only); first cell runs as upstream |
| 6 `ctrl` prerequisites and floor | A64 | floor to be lowered for `ctrl` only; value pending a measurement |
| 7 stopped-cell continuation | A65 | DROPPED by the owner: rerun from zero |
| 8 prebuilt env (O9) | — | CLOSED; the hash seam is `ACCOUNTABILITY.md` G9 |
| 9 licence and CI | A66, A67 | no licence for now, a not-redistributed notice; CI unruled |
| — evaluation cost | A68 | parallelise by regime; nothing in the grid dropped |
| — training timeout | A69 | schedule-derived backstop, owner-approved; being implemented |
| — data richness | A70 | endpoint-as-headline is conditional on it; audited |
| — estimand passes | A71 | keep both; which leads is not decided |
| — Lift | A72 | not now |

1. **Budget vs scope, given the competence-gate finding**
   ([`production-host/36`](production-host/36-no-completed-cell-passes-the-competence-gate.md)).
   Every completed cell sits far above the random floor on shaped return and opens the door in at
   most 1/200 episodes — success stays flat at ~0.000 across the whole training curve while shaped
   return climbs 15.15 → 79.36. Under EVAL-PROTOCOL §3 no retention ratio may be printed for any of
   them. Three live options: extend the frame budget for a subset (does more training reach
   competence, or is 600k just not enough for this task/family combination?), narrow scope to
   report the plateau itself as the finding, or something else. This is a research-direction call,
   not a mechanical one.
   **Read `DECISION-SHEET.md` A46 (2026-09-08) first — it already tabulates what 600,000 frames is
   to each of the twelve, and the paragraph below, written 2026-09-19 without having found it, is
   narrower and in one respect misleading.** A46's horizons: `rad`/`soda`/`alda`/`sgqn` 500k (600k
   is 120%); the RL-ViGen four 1.1M from `cfgs/task/easy.yaml` (55%) — **which is wrong as a source horizon, found
   2026-09-20: the RL-ViGen paper's own Table 6 (p.17) sets Robosuite Door at `int(6e5)` training
   frames, so for the five natives 600k is exactly the published budget** (A46 now carries the
   correction);
   `idaac`/`ppg` **1M, from IDAAC's DMC appendix** — continuous control from pixels, a closer
   analogue to Door than the 25M-step Procgen table cited below (60%, and their learning rate,
   annealed over a literal 1M steps, stops at 40% of its initial value); `ctrl` 8M (7.5%);
   `ibac_sni` 160M on CoinRun (0.375%). Both sourcings are true of different experiments by the
   same authors; A46's is the one to reason from. A46's status is "operational, not ratified".
   **Not idle speculation — checked against the primary sources, 2026-09-19.** `action_repeat=1`
   is universal and paper-verified across all 12 baselines (`docs/FAITHFULNESS.md:208`), so 600k
   frames means the same 600,000 real environment steps for every baseline; no hidden multiplier
   asymmetry. But the four on-policy families' *native* training length, read directly from their
   own papers, is far larger: `idaac`/`ibac_sni`/`ppg` are compared in IDAAC's own Table 1 at
   **25,000,000** Procgen steps (`ext/idaac/raileanu21a.pdf`, p.6); `ctrl`'s own paper reports its
   primary results at **8,000,000** steps (`ext/ctrl_rl/2106.02193v2.pdf`, p.9, Table 1 caption).
   600k is **2.4%–7.5% of what these four are shown, in their own papers, to need** on a task
   that's also easier to represent (Procgen's fixed discrete 15-action space vs. Door's continuous
   control). This does not prove more frames would reach competence here — Door and Procgen are
   different tasks — but it is a concrete, sourced reason to suspect under-training rather than a
   broken port, and it argues for extending the budget for *just the on-policy subfamily* as the
   best-motivated of the three options, rather than a blind guess between them. `EVAL-PROTOCOL.md`
   §5 already rules that harmonising the two subfamilies' budgets is explicitly not the goal
   ("report it, let the audience see" — owner-ratified) — this finding is about whether *600k
   itself* is enough for either subfamily, a different and still-open question.
2. **The vacancy rule on card 0.** Twelve hours of the strict "no foreign holder at all" rule
   produced nothing, while card 0 has sat at ~9.6 GiB free beside a stable long-lived co-tenant —
   enough for `idaac`'s 6.6 GiB peak. Relax the rule for a small cell beside a *stable* co-tenant
   (not one that cycles), or keep it strict everywhere? Relaxing it without the co-tenant's own
   behaviour being predictable is exactly the OOM risk §5.1 exists to prevent, so this needs a
   human judgement call about that specific co-tenant, not a blanket policy change.
   **Owner's clarification, 2026-09-19: this is future-operator guidance only.** Nothing this
   session has changed, or will change, the *current* automated waiter's behaviour to push a
   launch onto a card while `rl4vla_cudagl` or any other current co-tenant is running — relaxing
   this rule is not something to operationalise now, only something to write down for whoever
   configures the next waiter with a specific, known co-tenant in front of them.
3. **`ppg` seed 1 is off-schedule.** It is a complete, real cell, but the schedule names seeds
   {101, 102, 103} and `campaign_status.py` reads seed 1 as MISSING. Keep the run and record the
   seed set as {1, 102, 103} for `ppg` specifically, or rerun it at 101 to match the other eleven
   baselines? Either is defensible; neither has been chosen. **Owner's ruling, 2026-09-19:
   lowest priority — handle last, after everything else.** A light operator note is enough for now
   (whoever reads `campaign_status.py`'s output should know seed 1 is a real, complete cell reading
   as MISSING, and why) rather than resolving the choice itself. It's a minor reproducibility
   footnote, not a blocker.
4. **The upstream-source archive risk** (`ACCOUNTABILITY.md` C9/T1). 5 of the 7 pinned third-party
   algorithm repos are on individual researchers' personal GitHub accounts, not orgs; all 7 are
   currently reachable, checked directly. No local mirror exists. `.gitignore`'s own comment states
   why: ~200 MB each, reproducible from the pinned commit + a tracked patch — a deliberate
   space-vs-durability call, already made once. Worth revisiting given the durability side is a
   permanent, silent risk (if any one disappears, the exact algorithm code becomes unrecoverable
   from this repo's own history)? Or accept the risk as already decided and move on?
   **Owner's answer, 2026-09-19: a local copy as backup is enough for the submit.** State of that
   backup, checked 2026-09-19, not more: `ext/` holds file copies (no `.git`, so the commit is NOT
   verifiable) of `dmcontrol-generalization-benchmark`, `ALDA_Official`, `idaac`, `IBAC-SNI`,
   `ctrl_public`, `phasic-policy-gradient`; `ext/rl_vigen` holds 2 files and is not a copy of
   RL-ViGen. The pinned-commit clones live only in the gitignored reconstruction trees on this
   laptop. **Diffed 2026-09-19:** the six `runnable/<family>` checkouts each have a HEAD tree equal
   to the pinned `tree` in `setup/source-reconstruction.json` (spot-checked for `idaac`:
   `1b00786c…`), and each `ext/` copy differs from its checkout only in the files this project's
   patch modifies. So six of seven have a verified local copy. **RL-ViGen itself does not**:
   `ext/rl_vigen` is two PDFs and `RL-ViGen-upstream/` has no `.git`, so its commit cannot be
   checked locally — and it is the family the most cells depend on.
   **Owner, 2026-09-19 (later the same evening): risk accepted, item closed.** *"I don't expect any
   of these get deleted and I have the local copy; if it's a reproduction I can't take the others'
   works directly in, maybe."* So: no mirror, no vendoring of upstream code into this repository.
   The RL-ViGen gap above stays a stated fact, not open work.
5. **`ctrl`'s in-loop eval cost — recommendation: leave the algorithm code untouched; fix the
   schedule instead, 2026-09-19.** Analysed the "reduce it" option specifically for hidden risk
   before recommending against it: `succ_id = [False] * FLAGS.num_envs` and the `for i, info in
   enumerate(infos_id)` loop both assume `env_test_ID`'s vectorised width equals `FLAGS.num_envs`
   exactly. Shrinking just the test envs (the natural way to cut the ×3) breaks that pairing —
   either an index error or a silent truncation of tracked success/return stats, in code that is
   upstream's own scaffolding, not ours, so its edge cases haven't been stress-tested by this
   project. That is exactly the "specifically crafted implementation, don't touch without being
   asked" class. **The lower-risk fix lives entirely on our side instead**: the ×3 cost is already
   folded into whatever a real `ctrl` run's "training time" measures, so once a real cell runs, its
   watch budget and `production-schedule.json`'s throughput entry should be *re-derived from that
   measurement* rather than the current cross-algorithm hardware conversion (item 6 below) — that
   closes the actual risk (a foreseeable reap) without touching a single line of `ctrl`'s own code.
   **Re-read by me in the code, 2026-09-20 17:53 MSK, after the owner said this had never been faced
   head-on** (`runnable/ctrl/train_ppo.py:301-346, 384-412`): every training step takes one
   transition in each of the 64 training envs AND steps 64 in-distribution and 64 out-of-distribution
   test envs — **three times the environment work**. On Procgen, where CTRL was written, an env step
   is nearly free; on Door each one is a MuJoCo step plus an EGL render, so upstream's progress
   reporting becomes ~2/3 of the env cost. The test envs' outputs reach ONLY `wandb.log`
   (`ep_return_200`, `ep_return_all`, the success buffers); nothing feeds a training update. One real
   coupling: the JAX key is threaded through the test-env action sampling, so removing or thinning
   them changes the training random stream, not the algorithm (NumPy placement is already isolated by
   `NATIVE_ISOLATE_ONLINE_EVAL`). No switch exists for `ctrl` (`FINDING-online-eval-per-family.md`).
   So the owner's dilemma resolves like this: dropping the in-loop test envs loses nothing
   scientific — the offline grid measures the same quantities, better — while keeping them pays a
   3× factor that is an artefact of Procgen's cheap envs. **Working value (mine, per the owner's
   instruction to set these and return for ratification): run the FIRST `ctrl` cell exactly as
   upstream, to get a faithful row and a measured cost; prepare — do not yet use — an opt-in switch
   that steps the test envs every N-th training step, declared as a reporting-cadence change with a
   different random stream; bring the measured cost and that switch back to the owner.** No `ctrl`
   run is planned while the owner's "no further runs" holds.
6. **`ctrl` at 600k needs a genuinely empty card** (its 32,435 MiB observed peak leaves no room for
   the 4,000 MiB floor on a 32,494 MiB card), **plus** an explicit decision to lower or waive the
   floor for this one family, **plus** a real RAM measurement, **plus a fourth prerequisite found
   2026-09-18**: `production-schedule.json` prices `ctrl` at 11.17h/seed with
   `throughput_source: "converted from gt4i.1 x1.14"` — a generic hardware-tier scaling of a
   *different* algorithm's measured throughput, not a measurement of `ctrl` at all (`ctrl` has never
   run at 600k). It cannot reflect `ctrl`'s own cost structure, which includes stepping two fully
   vectorized test environments at training's own scale every single step (item 5 above) — a real,
   unaccounted overhead the borrowed number has no way of capturing. **Concretely: the watch budget
   sized from this number may be wrong, and a first real `ctrl` launch risks the reaper stopping it
   mid-run for a foreseeable, avoidable reason** unless the budget is re-derived, or at minimum
   padded generously, before that launch. None of the four exist yet.
   **Owner's answer, 2026-09-19: no such card exists, so the floor has to be lowered for `ctrl`.**
   Direction decided; the value is not. Pick it from a real `ctrl` peak measurement, and keep the
   never-CUDA-OOM rule above it: a lowered floor only makes sense on a card with no co-tenant.
7. **Stopped-cell continuation.** No family has a wired resume path; every stop today means rerun
   from zero. May a continued run ever stand in for a seed (restarting with an empty replay buffer
   for the off-policy families, or resetting Adam's state for `ibac_sni`)? If yes, the per-family
   code change is scoped in `OPERATOR-GUIDE.md` §6c; if no, that's the status quo, stated rather than
   assumed.
8. ~~**`build-env.sh`'s prebuilt environment (O9).**~~ **CLOSED 2026-09-19, no decision needed.**
   The "delete and rebuild from a payload that carries the upstream tree" fix that stood here was
   wrong: no payload ever carries `RL-ViGen-upstream/` (`run_probe.sh:1788-1789`). Real fix,
   commit `d25905b`: `build-env.sh` clones the pinned commit and applies the patches itself.
   Verified on the host: `ENVIRONMENT.json` lists `"editable": ["robosuite","robosuitevgb"]`.
   Verified 2026-09-19 on the laptop with `build-env.sh`'s own recipe: eleven baselines — the
   RL-ViGen five, `rad`, `soda`, `alda`, `ppg`, `ibac_sni` **and `idaac`** — resolve to the same 42
   requirement lines, hash `10d2004a`; `ctrl` alone differs (`2466d111`, 37 lines, the five
   torch/cu121 lines its `excluded_base_requirements` drops). **The literal hash is only valid on
   the machine that computed it**, found the same evening: the recipe pipes through `sort`, and
   the same 42 lines hash to `10d2004a` under an en_US locale and `e26959bf` under `LC_ALL=C`; the
   env directory built on the host on 19 Sep is keyed `02805cc0`, which is neither. `build-env.sh`
   hashes on the host shell from the host checkout's `family.py`; `run_probe.sh:1552-1558` re-hashes
   inside the container from the payload's and exits 3 on `NATIVE_VENV_REQUIREMENTS_MISMATCH`. So
   "eleven baselines share one requirement set" is verified; "a cell will accept the prebuilt env"
   is NOT. It has not bitten because `train-production-cell-v5/v6.sh` do not pass
   `NATIVE_VENV_HOST` — tonight's `svea` cell ran the full apt+pip bootstrap. Check on the host
   when it is reachable: what a container computes vs the manifest's `requirements_sha256_8`. History: `OPERATOR-GUIDE.md` §11.4 O9.
9. **The repository is public on GitHub with no `LICENSE` file and no CI.** Checked directly via
   the GitHub API (`private: false`, `visibility: public`). Neither is a technical gap; both are
   policy calls — add a license (and which one), add CI, or leave both as they are?

**Owner's standing ruling on external/blocked items, 2026-09-19:** prepare for them as far as
review and verification reach, give the operator a full package, and past that point they are the
operator's problem, not open work here. Item 7's question about replay buffers was answered
verbally (no family restores one; `OPERATOR-GUIDE.md` §6c has the per-family table).

### Owner's rulings of 2026-09-20 09:41 MSK — on the proposals for queue order, budget and the open decisions

Dated, and each an answer to the proposal put to them that night (`ACCOUNTABILITY.md` F6). Quoted
where the wording matters.

- **How open decisions are to be handled from here (this governs the rest):** *"preserve the 'open
  decisions' framing, but actually define the technical working values yourself, so tune if they're
  bad, analyze if they're good and return with the finals for ratification."* Formal ratification
  is not to pull the owner back into re-deriving why each value was set. One list is fine: §7b may
  link into what `open_decisions.py` gathers.
- **Queue order:** RL-ViGen natives first — accepted. Their point is reproduction: RL-ViGen already
  ran them, so either we reproduce their numbers (and learn if we are off) or, where they published
  none, we gather them. The Places365 loader-worker experiment (G12) is approved.
- **Budget:** keep the proposal — 600k as the headline budget, plus the `ibac_sni` 6M probe (*"if
  ibac_sni is so fast, 6M doesn't seem a problem"*). Wider principle stated: *"we have slow
  algorithms and fast; if it coincides so that faster ones need more frames, naturally it's not a
  problem to run the faster ones and budget's not a thing to withhold from consideration."* The
  owner also said they are *"still not sure in the concrete values … like, 600k"* — so 600k is a
  working value with its source recorded (RL-ViGen Table 6), not a ratified one.
- **n = 3:** ok, and partial results are to be analysed as they arrive, before the final set.
- **Endpoint-as-headline:** acceptable ONLY IF the retained data allow rich recomputation: *"the
  metrics (at least the all-checkpoint runs; better, this including dense train metrics) should
  allow to richly recalculate different statistics … if the job produces, after coagulation and
  summing, just 2-3 metrics but we'd secretly need a fourth, this seems chasing running the same
  thing again and again."* → a data-richness audit of what a cell retains is owed (taskset H2).
- **Production canary, renderer substitution:** ok. **Resume:** dropped — rerun from zero.
- **Evaluation cost** (raised about `ctrl`'s in-training eval and about the grid taking ~2× the
  training time): *"I don't want either to drop it from a scientifically valid value … or to have it
  2x since it's a random number of eval steps set; I don't see us approaching this problem in whole
  face to face."* → owed: a head-on treatment of evaluation cost (taskset H1), not another note.
- **Training timeout:** the owner doubts the mechanism itself — a pre-set timer that stops a job,
  with no notice and no progress/stall distinction. → owed: H3.
- **Not ruled, questions back to me:** what the "external anchor" actually pins (RL-ViGen-supplied
  vs algorithm-supplied parameters); whether Lift is possible; what the "estimands" question is;
  whether each run already records its apt/pip versions; why MIT for a lab repository.
- **The host, for the next 3–4 days:** *both cards are booked for our group, under Kalugin's name.*
  The supervisor has said the owner may use them, with consideration: if Kalugin's work would take
  the cards, give way; never OOM anyone. So card 0 is usable now, which the recorded 8 Sep
  assignment ("card 1 only") did not allow. §4's constraints are unchanged.

## 8. What to do first on resume

1. Re-run the five commands in §1. Do not trust the tallies above.
2. Read [`production-host/33`](production-host/33-what-we-actually-have-2026-09-16.md) — it is the
   first-hand audit this summary compresses.
3. Read [`HANDOFF.md`](HANDOFF.md) for the intent and unproven suspicions that this file
   deliberately does not carry.
4. Check what is running before launching anything: `docker ps` on the host, and disarm any waiter
   script still armed (`ibac-waiter.sh` and friends) — one of them double-launched a 600k cell.
5. Finish idaac's curve if it is not at 11/11, then collect it: the sweep skips completed stamps, so
   restarting it is safe and cheap.
