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

As of the last run (2026-09-19 ~21:14 MSK): gates **37 pass / 0 fail / 9 owner**; campaign **36 cells:
31 MISSING, 3 DONE, 1 RUNNING, 1 PARTIAL**; all five commands exit 0. One cell of ours is running
(§2). No waiter is armed on the host.

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

**Running now: `svea` s101, the first cell of the RL-ViGen five and the first Places365 cell.**
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

Added 2026-09-19 from a sweep of the owner's own messages of 16–19 Sep against these docs
([`inventory-2026-09-19/owner-statement-sweep.md`](inventory-2026-09-19/owner-statement-sweep.md)).
Each was said in chat, acted on at the time, and written down nowhere as a rule. Quoted, not
paraphrased:

7. **`ppg`'s rollout quantum is not to be changed.** *"the ppg rollout quantum is different and
   shouldn't be changed unless I explicitly say later."* (18 Sep). It is why `ppg` checkpoints land
   near 51,200-frame spacing instead of 50,000 (`production-host/37`); that is accepted, not a bug
   to fix.
8. **Do not stop a healthy cell.** *"Yeah, don't be stopping health cells."* (17 Sep). A quiet log
   or a loaded host is not a reason; `OPERATOR-GUIDE.md` §10.1 is the check to run first.
9. **Some yield stays armed.** *"Cuda oom wouldn't be good regardless of ours or theirs so
   'no-yield' isn't a right policy I think"* (16 Sep). A cell may run with the *process* yield off
   on a card shared by choice; the memory-floor yield and the disk watch are never turned off.
10. **On the host, our scope is the `varaksin_as` home directory and nothing else.** *"'not just
    home' I meant only the varaksin_as user folder of course!"* (18 Sep).
11. **Use the compute there is, inside items 2 and 5.** *"If any card is free for one of our runs,
    please try take."* and *"Due to limited compute, really use the most out of it."* (16 Sep),
    bounded three days later by *"trying to run it in a way that'd over-contend the machine for
    OOM"* being named as not acceptable (19 Sep). Read together: take every window the upper-bound
    rule permits, and none it does not. `production-host/33` records why "the card looks free" was
    the wrong trigger and a sustained vacancy is the right one.
12. **Autonomy has an upper edge.** Careful, proven deletions and ordinary runs need no sign-off
    (*"I'm not against deletion/rm as a thing if it's very careful … I expect you're not blocked on
    'decisions' that are actually non-decisions"*), but *"the heavy-results decisions … like big
    deletes, big runs that could have real super-unintended consequence"* stay the owner's (19 Sep).

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

1. **Budget vs scope, given the competence-gate finding**
   ([`production-host/36`](production-host/36-no-completed-cell-passes-the-competence-gate.md)).
   Every completed cell sits far above the random floor on shaped return and opens the door in at
   most 1/200 episodes — success stays flat at ~0.000 across the whole training curve while shaped
   return climbs 15.15 → 79.36. Under EVAL-PROTOCOL §3 no retention ratio may be printed for any of
   them. Three live options: extend the frame budget for a subset (does more training reach
   competence, or is 600k just not enough for this task/family combination?), narrow scope to
   report the plateau itself as the finding, or something else. This is a research-direction call,
   not a mechanical one.
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
   torch/cu121 lines its `excluded_base_requirements` drops). Not re-run inside the
   `python:3.11-slim` container the script uses. History: `OPERATOR-GUIDE.md` §11.4 O9.
9. **The repository is public on GitHub with no `LICENSE` file and no CI.** Checked directly via
   the GitHub API (`private: false`, `visibility: public`). Neither is a technical gap; both are
   policy calls — add a license (and which one), add CI, or leave both as they are?

**Owner's standing ruling on external/blocked items, 2026-09-19:** prepare for them as far as
review and verification reach, give the operator a full package, and past that point they are the
operator's problem, not open work here. Item 7's question about replay buffers was answered
verbally (no family restores one; `OPERATOR-GUIDE.md` §6c has the per-family table).

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
