# Current state and responsibility — read this first, especially after context loss

**Last updated: 2026-09-17, ~21:05 MSK, by Claude.** This file says what is *true right now*. It is
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

As of the last run (2026-09-17 21:03): gates **36 pass / 1 fail / 9 owner**, and the one FAIL is
`source tree frozen` counting three uncommitted documentation edits that were committed minutes
later; campaign **36 cells: 32 MISSING, 3 DONE, 1 PARTIAL**; fleet export **6,193 rows, 2,932 on
the current closure**. Nothing of ours was running on either card at that time.

## 2. Where the campaign actually is

**Three baselines have production-length rows. Three cells count as DONE and one as PARTIAL.**

| baseline | seed | state | rows collected | note |
|---|---|---|---|---|
| `ppg` | 1 | complete | 88 endpoint + 528 curve | seed 1 is outside the schedule's `{101,102,103}`, so the counter reads it as MISSING (below) |
| `idaac` | 101 | complete (DONE) | 569: 484 curve + 85 of 88 endpoint | stopped by the watch budget during the second endpoint pass on 2026-09-09 |
| `idaac` | 102 | complete (DONE) | 598: 484 curve + 88 endpoint | trained 7 h 15 min, grid about 13.5 h; finished 18:43 on 2026-09-17 |
| `ibac_sni` | 101 | complete (DONE) | 910: 528 curve + 88 endpoint + training-curve rows | trained 31.5 min at 16 processes, grid about 14 h; finished 11:16 on 2026-09-17 |
| `ibac_sni` | 102 | PARTIAL | 308 curve rows from seven salvaged stamps | attempt 1 stopped by the memory floor at 28,672 frames and kept nothing; attempt 2 stopped by it at 376,832 frames. The seed needs a rerun from zero (OPERATOR-GUIDE §6c) |

Next in the queue when a card is genuinely vacant (the co-tenant absent for ten consecutive
minutes): `idaac` s103, which makes `idaac` the first baseline at three seeds; then `ibac_sni` s102
from zero; then `ppg` s101.

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
- **`svea`, `sgqn` and `soda` are blocked on Places365**, found 2026-09-16 and not previously
  recorded. The host holds only the 20-class/1,000-image attestation fixture; the corpus is ~24 GB
  and has never been fetched. **No gate ties a production run to the production dataset**, so a
  cell trained against the fixture would look correct — the corpus is a learning-affecting input.

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
5. **"No room" is answered by waiting for room, never by lowering a floor.**
6. **A blocked action is a stop, not a puzzle.** It may encode context nobody wrote down.

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
