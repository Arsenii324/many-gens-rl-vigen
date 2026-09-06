# Current state and responsibility — read this first, especially after context loss

Not a journal (that's `START-HERE.md`). This file is meant to be kept current and short: what's
true RIGHT NOW, what's mine to keep doing, where everything else lives. Update it when something
here goes stale rather than letting it drift — that's the whole point of it existing.

**Last updated**: 2026-09-06, ~15:20 MSK, by Claude, mid-session (fully rewritten from the
2026-09-06 ~13:50 version, which was stale within two hours — see "how fast this goes stale" below).

## The standing mandate (owner's own words, repeated verbatim across this session)

"Continue work autonomously from me; your ultimate goal is to finish the pre-production stage in
full; (when I tell finish, I don't mean e.g. 'solve the problems seen now', but truly finish in the
sense of taking full responsibility and working on the long horizon.)" Also explicit: don't stop
for intermediate check-ins unless something needs a real decision; wall-clock throughput (not
GPU-dollar cost) is the thing to optimize; GPU probes are fine, size them to their actual question
rather than a template; current multi-agent setup (this session + Codex via the mailbox) is the
right scale — don't escalate to heavier orchestration (Workflow tool, agent sweeps) unprompted.

**The two-layer decision model** (see `feedback_two_layer_decisions_rlvigen.md` in Claude's own
cross-session memory): every open question already has *some* behavior running today. "It's the
owner's decision" is never a reason to leave that behavior arbitrary — implement the genuine best
answer now (the "our best" layer), and only the *formal* resolved/PASS status waits on
ratification. Applied concretely this session: every new OWNER gate got a reasoned recommendation
recorded (A33, A34), not just a bare "needs a decision."

## Codex is active, not stopped — this changed since the last version of this file

Codex resumed (quota reset) partway through this session and has been reviewing work live via the
mailbox (`notes/ask-claude.md` / `notes/claude-answers.md`), catching real issues fast: a
pre-fix-vs-post-fix evaluator confound in the C95 probe design (Q33), a V100
reservation-vs-timeout invariant gap (Q34, now fixed and committed as `c3e5b73`), and a
record-delivery ordering bug that makes an eval-only job pay for a full evaluation before failing
to deliver its result (Q37, live, not yet fixed). **Check the mailbox tail before assuming anything
below is current** — this file has already gone stale once in under two hours this session.

Live coordination convention that's worked well: state exactly what files/paths you're each
touching, verify the other's claims independently before acting on them (both directions — Codex
verified my ledger work found a real gap; I verified Codex's C95/budget findings before acting),
and hand off cleanly rather than duplicate effort. `runnable/ctrl/`, `datasphere/native/run_probe.sh`,
`normalize_curves.py`, `summarize_result.py`, `contract.py`, and the clone-patch tooling
(`refresh_clone_patches.py`) are Codex's live territory as of this writing — don't edit them
without checking the mailbox first.

## Where everything lives (the surfaces — if it's not linked here, treat that as a bug to fix)

| Surface | What it is |
|---|---|
| `notes/CORRECTIONS.md` | Numbered bug-find-and-fix log. At **#93** as of this writing. |
| `notes/DECISION-SHEET.md` | A1-A34 ("our best" layer decisions). A33 (Door-vs-+Lift scope) and A34 (`ppg`'s training-only exclusion gap) are newest. |
| `notes/START-HERE.md` | Chronological session journal. |
| `docs/CONSTRUCTION.md` | ~96 numbered findings, the deepest technical ledger. |
| `docs/EVAL-PROTOCOL.md` | The living, operational evaluation protocol. |
| `scripts/production_gates.py` | **The authoritative launch-readiness check.** Run it fresh; don't trust a cited tally. |
| `scripts/open_decisions.py` | Enumerates everything actually waiting on the owner. |
| `notes/ask-claude.md` / `notes/claude-answers.md` | The Codex mailbox, both directions. **Check this first, always — it's the most current surface in the project.** |
| `datasphere/native/validated_evaluator_families.json` | The evaluator-family validation ledger (see below — 4/7 current as of this writing). |
| `datasphere/native/` | The submission pipeline (`job.sh`, `contract.py`, `family.py`, `evaluator_identity.py`, `families.json`, `cfg-*.yaml`). |
| `~/.local/state/ccm-intro/datasphere-v100-g1-1.json` | V100 budget ledger (not in the repo; `bash datasphere/native/job.sh v100-budget status`). |

## Right now, in flight (check before assuming any of this is stale)

- **`gate_shared_evaluator_validated`: 4/7** (`rlvigen`, `dmc_gb`, `idaac`, `ibac_sni`), up from 0/7
  this session. Each entry independently adversarially reviewed by a fresh agent, not self-graded.
  - `ppg`: ledger entry exists but `runtime_imports_checked` is honestly `false` — the review found
    `train.py` is loaded during evaluation (via `phasic_policy_gradient/__init__.py`) despite being
    excluded from the hashed closure. Currently harmless, structurally real. See CORRECTIONS #93 /
    DECISION-SHEET A34. Needs a fresh validation run once (ideally) the exclusion gap is closed.
  - `alda`: needed a real fix first (CORRECTIONS #91 — a residual Tensor crashed `json.dumps` in
    this project's own train_metrics.jsonl persistence patch, first hit for real by this campaign).
    Fixed, re-running as job `bt18gmov8nbfkkd117s6`.
  - `ctrl`: excluded on purpose — its runtime files are being actively edited live by Codex, so no
    job's baked-in revision can match "current" right now. Needs a fresh run once those edits land.
- **V100 budget**: **51.6 minutes remain** of the 240-minute cap (reconciled as of this writing;
  re-check, it moves). Spent this session: two renderer-parity failures that found real bugs
  (AppleDouble sidecars, #88; an undersized timeout), one that succeeded on evaluation but failed
  record delivery (below).
- **C95 renderer-parity is blocked on a real, live bug, not just waiting on compute.** Codex found
  (Q37): `run_probe.sh` only collects/enriches `offline_eval_*.jsonl` when `RECORDS_OUT` is set,
  but always calls `finalize_record_delivery`, which requires a delivered file for
  `execution_kind=eval_only_validation` — so an eval-only config without `RECORDS_OUT` is
  *guaranteed* to run the full (paid) evaluation and only then fail. Both C95 configs
  (`cfg-renderer-parity-v100-v128.yaml`, `cfg-renderer-parity-t4-current-v144.yaml`) had this
  omission. The V100 job (`bt1v3lo9ckk2iukvtjnu`) ran the full grid successfully (pooled train
  108.58, eval-easy 2.97 — real data, recovered from `result.tgz`'s `offline_eval_cuda.jsonl`, but
  not a certified delivery) then ERRORed on delivery. The T4 companion (`bt1bcgonkd4clpqml76p`)
  was correctly cancelled by Codex before repeating the same paid failure. **Waiting on Codex's
  systemic fix** (fail before the expensive step, not after) before resubmitting either side.
  Do not resubmit a renderer-parity config without `RECORDS_OUT` set until that fix lands.
- **CTRL memory measurement and the ibac_sni competence pilot remain genuinely blocked on
  DataSphere by design** (RAM-capacity-at-v100-settings specifically, not V100 work broadly — this
  was corrected once already this session after an overstatement; see CORRECTIONS/START-HERE for
  the full reasoning if it needs re-deriving). Confirmed again this session
  (DECISION-SHEET.md's A1 revision): a smaller-process-count pilot would measure a different
  rollout geometry, not the production configuration, so it doesn't substitute.

## What's genuinely owner-only right now (from `production_gates.py`, re-run it for the live list)

8 OWNER items + 1 FAIL as of this writing (FAIL is "source tree frozen," entirely Codex's active
uncommitted work, not mine to touch): ibac_sni competence, shared evaluator validated (4/7, above),
estimands frozen, seed policy frozen, production canary, external RL-ViGen anchor (has a stated
free-acceptance-test criterion now, A9/A49-era fix — awaiting only ratification and the fleet's own
drqv2 seeds), production renderer verified (blocked on the Q37 bug above), production scope frozen
(Door vs +Lift — now has a stated lean, A33: Door alone, Lift as a follow-on), checkpoint rule
frozen. Every one of these except the record-delivery bug already carries a recorded "our best"
reading; none is a bare unexplored question.

## What was just closed out this session (most recent stretch — see CORRECTIONS.md for the full log)

Centralized the g1.1→gt4i.1 admission-tier mapping (#84-class duplication); found and fixed a
second "two homes for one number" bug (`MIN_DENOM_SUCCESS`, #89); recorded a reasoned lean on two
previously-bare OWNER gates (A33 production scope, and rewrote `gate_external_anchor`'s stale
message to match its own already-decided default, #90); ran a full evaluator-family
re-validation campaign (7 fresh jobs, found and fixed a real ALDA bug along the way, #91); got
independent adversarial review of the resulting ledger before treating it as final, which caught
a real gap in `ppg`'s attestation (#93, A34) rather than rubber-stamping 5/7; fixed three
test-suite regressions from earlier-this-session commits that only a full-suite run surfaced
(#92); coordinated with a resumed, live Codex across seven mailbox exchanges (Q32-Q37), verifying
every claim independently in both directions before acting on it.

## How fast this file goes stale — read this as a warning, not just a caveat

The previous version of this file (written ~90 minutes before this rewrite) said "Codex is
stopped" and described a 0/7 evaluator-validation state with no live coordination happening. Both
were wrong within the hour. This file is a snapshot, not a live feed — the mailbox tail and a fresh
`production_gates.py` run are the only things that are actually current. Re-derive, don't cite.
