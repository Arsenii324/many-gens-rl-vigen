# Current state and responsibility — read this first, especially after context loss

**Last updated**: 2026-09-06, ~20:00 MSK, by Claude, right before a context compaction forced by
the owner's own "93%/1% context" warning — this update is intentionally dense and was written
under time pressure rather than after full verification of every claim. Re-derive before trusting.

## The standing mandate (verbatim, repeated across the whole session)

"Continue work autonomously; your ultimate goal is to finish the pre-production stage in full —
not 'solve the problems seen now' but taking full responsibility and working on the long horizon."
Also explicit and reinforced hard near the end of this session: **don't treat "flagged, not
fixed" as done.** If something is noted as a caveat, that note is a pointer to unfinished
investigation, not a resolution — go check it, or say plainly that checking it needs an actual
compute run (manual work) rather than more reading, and only then park it.

**The two-layer decision model**: every open question already has *some* behavior running today.
"It's the owner's decision" is never a reason to leave that behavior arbitrary — implement the
genuine best answer now, and only the *formal* resolved/PASS status waits on ratification.

## A live self-correction from the end of this session — read this before trusting any "flagged" caveat elsewhere in this file or DECISION-SHEET.md

I wrote, then had to retract under the owner's direct questioning: *"ctrl's new schema-2 payload
freezes Codex's in-progress, uncommitted edits (477 lines), self-consistent but not confirmed
finished or tested."* That was wrong in framing, caught only because the owner pushed on it
directly. What I'd actually seen was `git status` showing `runnable/ctrl` as modified relative to
its own nested repo's single "PRISTINE" commit — which is the PERMANENT, NORMAL state of all six
baseline clones (their nested git history never advances past the pristine snapshot; every patch
ever written to them shows as "uncommitted" forever). I treated that normal state as "in-progress,
uncertain" because I'd separately heard Codex was "actively editing ctrl," and didn't check
whether the actual diff content supported that. Partial re-check before compaction cut it off:
`vec_env.py`'s added `RLViGenVecEnvCustom`/`_SyncVecEnv` classes are dated `[Added 2026-09-05]` —
a day old, already cross-referenced by DECISION-SHEET A30 as an existing class, and
`refresh_clone_patches.py --check` already reports `ctrl` as "current" (patch matches clone) — all
of which points to this being finished, day-old work sitting in the normal uncommitted state, not
a live mid-edit. **I did not finish confirming this** (was about to run `pytest -k ctrl` when
compaction hit). Whoever picks this up: run the ctrl-specific tests fresh and check `algo.py`,
`buffer.py`, `models.py`, `train_ppo.py`'s diffs the same way (look for dated comments, cross-check
against what DECISION-SHEET/CORRECTIONS already reference) before repeating either claim — "it's
untested" or "it's fine" — as fact.

**The general lesson, stated because the owner named it explicitly**: a caveat I write and don't
act on is not neutral — it's either something I should have checked (cheap, just do it) or
something that genuinely needs a compute run (say so plainly and stop there), never a third
category of "noted and moved past."

## The cost question, unfinished — answer this first if picking this thread back up

The owner asked directly: **why does Codex's quoted 4,324.32 RUB / 21h figure for the 7-family
schema-2 revalidation wave look so expensive, and is it real?** I had the answer half-derived
before compaction: `scripts/audit_job_budgets.py`'s own per-config estimates for `v146`-`v152`
sum to **~13,030 seconds (~3.6 hours) of actual expected compute**, not 21 hours — the "21h" figure
is 7 configs' **uniform 3-hour safety-timeout ceiling**, summed as if run serially. Two real
overstatements stack: (1) timeout-ceiling instead of measured-per-family estimate, (2) serial
instead of parallel (this session ran all 7 earlier-generation configs simultaneously without
issue). If run in parallel like before, real wall-clock is ~44 minutes (the slowest single job,
`rlvigen`/`dmc_gb` at 2657s), and the real RUB cost should be proportional to ~3.6 total compute-
hours, not 21 — **likely a small fraction of the quoted figure**, though I did not finish
converting seconds-per-tier into an actual RUB number before compaction (would need the per-tier
hourly rate Codex used). This is worth surfacing to Codex/the owner explicitly: **worst-case
ceiling estimates for spend-authorization purposes are reasonable, but should be labeled as
ceilings, not presented as the expected cost** — conflating the two makes cheap things look
expensive and could cause either under- or over-investment in genuinely low-cost validation work.

## Honest answer to "are you super-sure we've reviewed everything?"

**No — and this project's own most recent, most careful review says so explicitly.** External
review 15 (`notes/ai-review-15-external.md`, triaged in `notes/review-15-triage.md`) states in its
own opening: *"I would therefore consider the RL-ViGen-native/RAD/ALDA source-level portion less
exhaustively inspected than PPG/IDAAC/IBAC/CTRL."* That's 5 of 12 baselines flagged by the most
recent reviewer as having received comparatively less scrutiny than the other 7 — not a blind
spot nobody named, a stated limitation of the review itself. Beyond that: five external AI
reviews across this project's history (6/7/8, 9/10, 11/12, Gemini, 15) plus this session's own
internal audit sweep is real, substantial coverage, but "unknown unknowns" are by construction
things no review has caught yet — no amount of past review makes that count zero going forward.

## Unknown-knowns hunt (silently-accepted defaults, done under time pressure — incomplete, worth continuing)

Requested explicitly per `docs/anthropic-prompting.md`'s framework (Known/Unknown Knowns/Unknowns).
Candidates found in the time available, **none of these have DECISION-SHEET entries yet** — that
itself is the finding:

1. **The asymmetric-scrutiny fact above (5 of 12 baselines less inspected) is not itself recorded
   as an accepted risk anywhere.** It's stated once, in passing, inside review 15's own text. No
   one has explicitly said "we accept this asymmetry" or "we should equalize scrutiny before
   production" — it's just sitting there unaddressed.
2. **All 12 baselines continuing to production despite 3 of them (PPG/IDAAC/IBAC-SNI) carrying
   "major fidelity issue"-level open questions (A35-A37) is itself an unstated default.** Nobody
   has asked "should a baseline this compromised be dropped rather than reported misleadingly,"
   only "should we run a pilot to characterize it better."
3. **The sequencing risk of this session's own work**: enormous infrastructure investment
   (evaluator-identity schema, record-delivery fix, validation ledger) happened *before* the
   IDAAC/PPG/IBAC fidelity pilots (A35-A37) that could, if run, meaningfully change which baseline
   variant is even worth validating. If those pilots reveal IDAAC-C/PPG-C should replace the
   current design point, some of the validation work already spent (and about to be spent on the
   v146-v152 wave) targets the *wrong* configuration. Nobody has explicitly decided the ordering
   "infrastructure first, fidelity pilots second" versus the reverse — it just happened that way
   because infrastructure bugs kept surfacing reactively. Worth a deliberate ordering decision,
   not more accretion.
4. **Whether the owner has actually reviewed the growing pile of "our best" DECISION-SHEET answers
   (now at A37) is itself unknown to me.** I've been diligently producing them; I have no signal
   whether they're being read/checked, versus quietly becoming the de facto production spec by
   sheer accumulation. Worth an explicit "have you looked at A1-A37, do any of them look wrong to
   you" check before treating the pile as reviewed-by-default.
5. **CTRL's real V100 memory footprint at 64 envs has no trustworthy number at all** — not just
   "unmeasured": the fallback "~54 GiB" figure people might reach for is *itself* flagged
   (`notes/claude-answers.md:1975`) as an untrustworthy linear extrapolation from the 16-env
   measurement, not a real estimate. Two candidate numbers exist (13.4 stale, ~54 untrustworthy
   extrapolation) and neither is the truth. This is the single most concrete "silently might get
   used as if known" risk found — if anyone schedules production packing math off either number,
   it should be flagged as provisional, not authoritative.

## Where everything actually stands mechanically (re-verify, don't trust this list)

- `production_gates.py`: was **31 pass / 0 fail / 9 owner** as of the last full run this session.
  Re-run fresh.
- `open_decisions.py` now has a real, tested split between `ANALYSIS INCOMPLETE` (the "our best"
  layer never done) and the rest (done, awaiting ratification/spend). As of last check, nothing
  remains in the `ANALYSIS INCOMPLETE` bucket — A35/A36/A37 (IDAAC/PPG/IBAC-SNI fidelity specs)
  were completed and their status tags corrected in the same session (see #4 above on whether
  anyone's actually reviewed them).
- Evaluator-identity schema is **2**, profile-invariant (CORRECTIONS #94/#95 area). All 5 families
  validated earlier this session are schema-1 legacy. A fresh 7-family schema-2 wave
  (`payload-v146`-`v152`, `cfg-*-revalidate-v146..152.yaml`) is built and locally verified
  (`verify-payload` + `verify-evaluator-binding`, both clean) but **NOT submitted** — needs owner
  spend authorization, and the cost question above should be resolved with real numbers first.
- C95 renderer-parity: T4 side (`cfg-renderer-parity-t4-current-v144.yaml`) was resubmitted after
  the Q37 record-delivery fix but **this payload (v133/v145-era) now predates schema 2** — it is
  NOT a valid current-identity measurement either; needs rebuilding against the schema-2 payload
  before its result means anything. V100 side is not resubmittable regardless — ~51.6 of the
  needed 100 reservation-minutes remain of the 240-minute cap.
- Codex is down for ~3 hours as of this writing (per the owner). Its last handoff (mailbox Q45)
  was fully executed and committed. Do not touch `run_probe.sh`, `normalize_curves.py`,
  `contract.py`, `refresh_clone_patches.py`, or `runnable/ctrl` without checking the mailbox tail
  first when it returns.
- Git tree was clean (all committed) as of the last check before this compaction, modulo whatever
  the ctrl-test investigation above turns up.

## What to do first on resume

1. Re-run `production_gates.py` and `open_decisions.py` fresh — do not trust the tallies above.
2. Finish the ctrl self-correction: run ctrl-specific tests, read the remaining 3 diffs
   (`algo.py`, `buffer.py`, `models.py`, `train_ppo.py`) the same way `vec_env.py` was checked.
3. Finish the cost-question answer: get the actual per-tier RUB/hour rate and convert the real
   ~3.6-hour compute estimate into a real number to hand back to the owner, rather than leaving
   "smaller than quoted" unquantified.
4. Decide (or ask) about the sequencing risk in unknown-knowns item #3 — should the v146-v152
   wave wait until after A35-A37's pilots are run, given they could change what's worth validating?
5. Read this whole file critically before extending it — it was written in the last minute before
   a forced compaction and may itself contain the exact "flagged, not verified" pattern it warns
   against.
