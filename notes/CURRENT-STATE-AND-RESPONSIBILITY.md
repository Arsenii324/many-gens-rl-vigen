# Current state and responsibility — read this first, especially after context loss

**Last updated: 2026-09-16, ~15:30 MSK, by Claude.** This file says what is *true right now*. It is
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

As of the last run: gates **36 pass / 0 fail / 10 owner**; fleet **4157 rows, 1216 on the current
closure**; campaign **36 cells: 35 MISSING, 1 DONE**.

## 2. Where the campaign actually is

**Two baselines are banked at production length and admissible on the current closure**, which is
new since 2026-09-14 — the fleet held 28 current rows then and holds 732 now.

| baseline | seed | endpoint | curve | note |
|---|---|---|---|---|
| `ppg` | 1 | 88 rows | 528 rows, 12 stamps | complete |
| `idaac` | 101 | 88 rows | 484 rows, 11 stamps | complete — the only cell the campaign counts |
| `idaac` | 102 | — | — | **training now**, card 1, since 14:32 MSK |

**The campaign counts 1 of 36 and that is not a mistake in the counter.**
`production-schedule-v100.json` names seeds `[101, 102, 103]`; ppg is banked at **seed 1**, so every
ppg column reads MISSING however good the rows are. The rows are valid — fixed in advance, not
outcome-selected, which is what `docs/EVAL-PROTOCOL.md` §4b requires. **Implemented default, awaiting
ratification: keep the run and record ppg's seed set as `{1, 102, 103}`** rather than spend eight
GPU-hours reproducing a number we have.

**Nine of twelve baselines have no production record at all**, and three of them are blocked on
things that are not compute:

- `ibac_sni` has never completed a 600k cell — five attempts, four stopped by the memory floor on a
  card a colleague was holding. It needs ~11 GiB that *stays* free.
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
instrument whose docstring claimed a filter it did not have. Only a lower bound survives: **~6.6 GiB**.

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
