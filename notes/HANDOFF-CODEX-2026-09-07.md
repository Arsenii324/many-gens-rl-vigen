# Claude → Codex handoff — 2026-09-07

Read `notes/START-HERE.md` first, then this file. This file exists specifically to survive
context compaction: `notes/claude-answers.md` A71 has the factual changelog (commits, file lists),
this file has the *why* — intent, priorities, what I chose not to do and why, and constraints that
don't show up in a diff. Verify tree state before acting; this is a genuinely concurrent-writer
tree.

## The one thing to read before touching anything: Q56

Your Q56 (`notes/ask-claude.md:940`) reserves PPG/IDAAC launch, wrapper, geometry, evaluator, and
source-lock files for your persistent worker. **I have not touched any of those files since Q56
landed, and I am not going to until your report lands.** I found Q56 via the mailbox-change
monitor mid-session, read it immediately, and stopped short of any further work in that area —
this handoff itself was written instead.

**Flagging a possible duplication, not assuming it either way**: Q56 says you're implementing
"explicit three-frame support through launcher/environment/evaluator/identity" for *both* IDAAC
and PPG. IDAAC's three-frame path (IDAAC-C2: `frame_stack=3`, the full DMC PPO recipe, linear LR
decay) is **already fully implemented and is the current production default** — commits `93ae962`,
`15b4e73`, `819db7c`, `b2b7ad5`, reported at A65/A67. If your worker is re-deriving IDAAC from
scratch, that may be redundant; if it's specifically PPG's still-missing three-frame wrapper/CNN
path (which A65/A67 both explicitly left undone), that's the real remaining gap and exactly right.
I don't know which from Q56's wording alone — worth checking before your report lands, not after.
When your report does land, I'll do the acceptance review you asked for (diff vs. authors' DMC
supplement, wrapper/reset ordering, channel geometry at train and offline eval, checkpoint/
evaluator identity, C1 isolation, PPG-as-comparator-not-primary-source prose) — not before.

## What I actually spent this session on, and why

The owner asked, explicitly and in detail, for an external-reviewer-facing document set
(`notes/review-17-18-response/`), with a specific instruction that mattered more than it might
look: don't just name blind spots, *close them* where closing is cheap, because "concealing things
you're not sure in... could plant bugs." I treated that as the operative instruction for the whole
session, not just the initial document-writing pass. Concretely: every time
`04-blind-spots-and-unverified-claims.md` named something as "taken on trust, not checked," I
treated that as a todo, not a disclaimer, and worked down the list for as long as I had budget.
That's the reasoning behind an otherwise-odd-looking session shape (write a report, then spend most
of the remaining time doing primary-source code reads that report named as gaps).

**What got closed this way, roughly in order, each with a direct code/primary-source read, not an
inference from either external review's prose**:
1. CTRL's paper hyperparameter table (`ext/.../appendix.tex`) — exact match, one real nuance found
   (one shared LR, not two).
2. The action-clipping instrumentation both reviews wanted — already exists
   (`ActionDiagnosticsAccumulator`), wired into all six evaluators.
3. IBAC-SNI's architecture-gap numbers, both sides — all verified; found `-uda` is genuinely dead
   code (defined once, read nowhere).
4. ALDA's five headline hyperparameters — byte-identical across all four official DMC specs,
   stronger evidence than either review states.
5. RAD's 100→84 crop mechanism — traced fully (empty `RAD` class, crop lives in the shared replay
   buffer's `sample()`, calls `random_crop` not `random_shift`); found and fixed a wrong
   function-name in `CLAIMS-LEDGER.md`'s `rad` row as a result.
6. DrQ-v2's replay-capacity arithmetic — independently recomputed (601,200 transitions at 600k
   frames/1,200 resets; 620k V100 / 300k DataSphere both confirmed against
   `families.json:28-30,101`), not just re-cited.
7. CTRL's authors' JAX/Flax/Optax versions — exact match against `ext/ctrl_public/requirements.txt`.
8. `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`'s two overbroad `EXACT SOURCE MATCH` verdicts
   (CURL, SVEA) that two of my own earlier review-response entries had already flagged as open
   and explicitly deferred as "your document, not mine to fix" — I fixed them directly this time.
   **Why the reversal**: those entries were written before the owner's explicit "if Codex is down,
   take the whole thing yourself" instruction; by the time I re-found them, that instruction was
   already in force and Codex had been unreachable 40+ minutes, so deferring a third time seemed
   like the wrong call. If you disagree with either correction, they're dated and reversible —
   see that file's CURL and SVEA sections.

**What I deliberately did NOT do, and why that's a judgment call, not a blocker**: your
`scripts/build_external_review_artifact.py` (522 lines) and its supporting notes/tests are sitting
uncommitted. I ran their tests against the current tree (they pass), but I did not read the script
closely enough to put my own name on committing it — a 522-line pipeline felt like a different
category of "take ownership" than a bounded, independently-verified doc fix. If you want me to
actually review and commit it rather than wait for you, say so; I'm not blocked on anything
technical here, only on not wanting to claim authorship of work I haven't read.

## Unresolved branches — what's still open and why, not just that it's open

- **SODA has had zero independent code reads this entire session.** Only confirmed it shares
  RAD's crop-size branch in `arguments.py`. Its own paper-vs-code aux-lr ambiguity and train-mode
  guard are exactly as taken-on-trust as before I started. This is a real, named gap in
  `04-blind-spots-and-unverified-claims.md`, not an oversight I'm unaware of — I prioritized RAD
  (which was named alongside it) because RAD's trace also touched a live `CLAIMS-LEDGER.md` bug;
  SODA didn't have an equivalent lead pulling me toward it. That allocation could be wrong.
- **IDAAC-C2 has never been exercised by an actual remote job.** Everything I verified was local
  (construction, forward pass, a five-step rollout, on CPU/MPS-as-CUDA-shim). Throughput
  (`MEASURED_TRAIN_FPS["idaac"]=30` is the *old* recipe's number), the `fixed_peak_gib: 3.17`
  memory ceiling, `cells_per_job: 2`, and the `gt4i.1` tier choice are all unexamined against the
  new compute pattern (10 PPO epochs vs 1, 32 minibatches vs 8, one 2048-step rollout vs many
  smaller ones). This is Phase 2 of the standing plan, genuinely not reached — not because it's
  hard, but because I ran out of turns before submitting the bounded probe job Phase 2 calls for.
  If you get there first: don't trust the old FPS number for the new config's timeout.
- **A checkpoint from the old idaac-P recipe will fail opaquely under new default code** — a raw
  `load_state_dict` shape-mismatch, not a message saying "this predates the C2 transition." Not
  fixed; low stakes, real discoverability cost.
- **C98's fix (evaluator_scope sourced from `OBSERVATION_GEOMETRY`) has the identical "never run
  for real" gap** as IDAAC-C2, for all twelve baselines — correct locally, untested against an
  actual evaluator job, per the governing one-final-wave rule (Q47), not an oversight.
- Nothing has been renamed anywhere a result/manifest would show it (`CURL-RLViGen`,
  `SVEA-RLViGen`, etc.) despite both reviews asking and my own fixes this session making the case
  for it *stronger*, not weaker. I treated renaming as more invasive than a doc correction — it
  touches `families.json`/job configs/result labels — and deliberately left it for an explicit ask
  rather than doing it opportunistically alongside the verdict fixes.
- No formal source-precedence-policy document, no two-axis `CLAIMS-LEDGER.md` restructuring, A25's
  post-selection-ranking caution never checked, no consolidated startup-time contract artifact, no
  SHA256 provenance-chain audit — all named plainly as not-done in
  `04-blind-spots-and-unverified-claims.md`'s own "things both reviews asked for that I didn't do"
  section, not silently dropped.

## Constraints worth restating, since they're easy to lose in a diff

- **Governing rule (Q47) still holds**: evaluator-family validation runs once, against the final
  frozen tree, not reactively after each fix. Still not reached — `production_gates.py`'s "source
  tree frozen" gate is the one real FAIL, and it's supposed to be red right now.
- **`ext/` is read-only.** Never wrote to it this session; several primary-source reads came from
  there (CTRL's `requirements.txt` and `appendix.tex`, ALDA's specs, IBAC-SNI's `policies.py`).
- **Register/ledger convention**: append a dated correction, never rewrite the historical body.
  Used consistently this session (`CLAIMS-LEDGER.md`'s `rad` row, `PRIMARY-SOURCE-FIDELITY-
  RECONCILIATION.md`'s CURL/SVEA rows) — if you touch either again, keep the pattern.
- **Two-layer decision model**: implement the genuinely-best technical default now; only the
  formal OWNER ratification in `production_gates.py` waits on the actual owner. This is why I felt
  free to fix the PRIMARY-SOURCE verdicts myself rather than leave them flagged a third time.

## Mechanical state at handoff

`production_gates.py`: 30 pass / 1 fail (source tree frozen — expected, your artifact-builder work
is mid-flight) / 9 owner, unchanged from before this session started. Full `pytest tests/ -q`
confirmed green (exit 0) as of commit `7c96ae6`; everything since has been markdown-only and
scope-tested clean (`test_docs_integrity.py`, `test_docs_not_stale.py`,
`test_ibac_source_provenance.py`, `test_external_review_artifact.py`). Commits this session, in
order: `7c96ae6`, `72c9393`, `41a6d21`, `64a8e3d` (the A71 hand-off), this file next.
