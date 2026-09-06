# Current state and responsibility — read this first, especially after context loss

Not a journal (that's `START-HERE.md`). This file is meant to be kept current and short: what's
true RIGHT NOW, what's mine to keep doing, where everything else lives. Update it when something
here goes stale rather than letting it drift — that's the whole point of it existing.

**Last updated**: 2026-09-06, ~13:50 MSK, by Claude, mid-session, at the owner's explicit request
("index of surfaces... single top-level index... after context compaction").

## The standing mandate (owner's own words, repeated verbatim across this session)

"Continue work autonomously from me; your ultimate goal is to finish the pre-production stage in
full; (when I tell finish, I don't mean e.g. 'solve the problems seen now', but truly finish in the
sense of taking full responsibility and working on the long horizon.)" Also explicit: don't stop
for intermediate check-ins unless something needs a real decision; wall-clock throughput (not
GPU-dollar cost) is the thing to optimize; GPU probes are fine, size them to their actual question
rather than a template.

**The two-layer decision model** (see `feedback_two_layer_decisions_rlvigen.md` in Claude's own
cross-session memory — durable guidance, not project-specific): every open question already has
*some* behavior running today. "It's the owner's decision" is never a reason to leave that behavior
arbitrary — implement the genuine best answer now (the "our best" layer), and only the *formal*
resolved/PASS status in the tracking surfaces waits on the owner's ratification. Don't mark
something formally resolved on your own authority; don't use pending ratification as an excuse not
to do the real analysis.

## Where everything lives (the surfaces — if it's not linked here, treat that as a bug to fix)

| Surface | What it is |
|---|---|
| `notes/CORRECTIONS.md` | Numbered bug-find-and-fix log. At **#88** as of this writing. Read the tail for the most recent work. |
| `notes/DECISION-SHEET.md` | A1-A32 ("our best" layer decisions). A32 is newest (statistical-inference framework, adopted 2026-09-06). |
| `notes/START-HERE.md` | Chronological session journal. Read its tail for narrative continuity; this file is for state, that one is for history. |
| `docs/CONSTRUCTION.md` | ~96 numbered findings (C1-ish numbering), the deepest technical ledger. |
| `docs/EVAL-PROTOCOL.md` | The living, operational evaluation protocol — sections merged in from proposals as they're adopted (most recent: §4c, A32). |
| `docs/FAITHFULNESS.md` | Per-baseline fidelity-to-original-repo ledger. |
| `docs/PART2-METRIC-INVENTORY.md` | What each of the 12 baselines actually emits, metric-by-metric. |
| `scripts/production_gates.py` | **The authoritative launch-readiness check.** Run it fresh; don't trust a cited tally. |
| `scripts/open_decisions.py` | Enumerates everything actually waiting on the owner (not on work). |
| `notes/ask-claude.md` / `notes/claude-answers.md` | The Codex mailbox — Codex's questions / Claude's answers, both directions. |
| `notes/FINDING-*.md` | Dedicated deep-dive writeups (C1's cancellation analysis, resolving power at n=3, on-policy update density, online-eval-per-family). |
| `notes/proposal-inference-and-checkpoint-selection.md` | Now merged into `EVAL-PROTOCOL.md` §4c (A32) — kept as the derivation record, not the live source. |
| `datasphere/native/` | The real submission pipeline (`job.sh`, `contract.py`, `family.py`, `evaluator_identity.py`, `families.json`, `cfg-*.yaml` configs). |
| `~/.local/state/ccm-intro/datasphere-v100-g1-1.json` | V100 budget ledger (not in the repo). |

## Right now, in flight (check before assuming any of this is stale)

- **Codex is stopped.** Its substantial uncommitted work was reviewed and checkpointed into git
  (commit `45d2f61`) once confirmed clean (0 test failures). A mailbox-watching background monitor
  is armed for if/when it returns — check `ps aux | grep 61433` or just re-arm one
  (`tail -f`-style md5-diff loop on `notes/ask-claude.md`) if it's gone.
- **V100 quota**: owner extended 2h → 4h (240 min cap) explicitly. **~87.5 minutes remain**
  (`bash datasphere/native/job.sh v100-budget status`) as of this writing. Spent so far: the
  renderer-parity probe (one failed submission that found a real bug, one that hit an undersized
  timeout and got killed mid-eval, now resubmitted correctly) and nothing else yet.
- **C95 renderer-parity probe**: job `bt1v3lo9ckk2iukvtjnu` is EXECUTING (resubmitted with a fixed
  6000s timeout, after the first two attempts failed for two different real, now-fixed reasons —
  see CORRECTIONS #88 and the timeout/admission-tier fixes in the commit right after it). Check its
  state with `GRPC_DNS_RESOLVER=native datasphere project job get --id bt1v3lo9ckk2iukvtjnu`. Once
  it succeeds, download results and compare against the T4 baseline
  (`cfg-offline-eval-s2-full-v50.yaml`'s own recorded numbers: train mean 89.47, eval-easy mean
  3.07 at 5 episodes/scene — this job runs the complete 10-episode grid, so compare like for like).
- **CTRL memory measurement and the ibac_sni competence pilot are specifically blocked on
  DataSphere, by design — but this is narrower than it first sounds, corrected after the owner
  pushed back on an overstatement.** Both need `NATIVE_HOST_PROFILE=v100` (CTRL's num_envs=64,
  ibac_sni's procs=16), which `job.sh` refuses on g1.1 ("g1.1 is diagnostic only") because that's
  specifically a RAM-capacity question (48-96 GiB vs the production host's 113 GiB) that a smaller
  box cannot validly answer either way it comes out. `cfg-ctrl-v100-memory-v130.yaml` exists but
  would be refused at submission (confirmed) — don't resubmit it as-is.

  **This does NOT mean DataSphere V100 work is broadly blocked or not worth doing.** Everything
  that isn't a RAM-capacity-at-v100-settings question DOES transfer to the real production host:
  the renderer-parity work below (rendering/driver stack, not RAM), the AppleDouble bug found and
  fixed this session (would have hit the production host identically), and the whole submission/
  contract/patch-application pipeline exercised end-to-end against a real Linux CUDA container.
  Only the specific "does this fit in RAM at v100 settings" class of question needs the actual
  separate host; everything else about running real jobs on a real GPU container is genuine prep.

## What's genuinely owner-only right now (from `production_gates.py`, re-run it for the live list)

As of this writing: 9 OWNER items — ibac_sni competence (the pilot above answers this), shared
evaluator validated (0/7, blocked on actually running each family's validation — the AppleDouble
fix removes the mechanical blocker, nobody has re-run the validations since), estimands frozen
(P-C76 + C1, both have stated recommendations, need ratification), seed policy frozen (n=3,
implemented, needs ratification), production canary (needs an actual full-length run), external
RL-ViGen anchor (C48, needs a real reproduction attempt), production renderer verified (the
renderer-parity probe above is exactly this), production scope frozen (Door vs +Lift, genuinely
undecided, no stated lean recorded anywhere — worth checking whether it deserves one), checkpoint
rule frozen (endpoint-headline, implemented, needs ratification).

## What was just closed out this session (context for why recent commits look the way they do)

Long stretch: closed all 4 metric-inventory-subagent findings; answered the C1 "does it cancel"
question rigorously (`FINDING-c1-does-the-asymmetry-cancel.md`); found and fixed two real
comparability-table gaps (C1-split warnings in both table generators) and one drift risk (STACK
dict); implemented A18 (floor-adjusted retention, decided but never coded); flagged and reconciled
A23 (delta superseded by the already-live success-rate gate); merged A32 (statistical-inference
framework) into `EVAL-PROTOCOL.md` from a side file it had sat in too long; found and fixed a real,
first-ever-exercised bug in Codex's evaluator-identity system (macOS AppleDouble sidecar files,
CORRECTIONS #88) via a cheap diagnostic job after exhausting local hypotheses; centralized a
duplicated g1.1-tier admission mapping into one function; fixed two undersized job timeouts (one
already killed a running job before the fix could apply — cost was small, lesson was real: check
`scripts/audit_job_budgets.py` and `scripts/production_gates.py` BEFORE submitting a new config
shape, not after).

## The one open self-critique worth remembering

The renderer-parity probe reused an existing "complete research grid" config (400 episodes) for a
narrower diagnostic question (does the platform reproduce the same number) that didn't need that
much data. Reuse-for-convenience over minimal-for-the-actual-question is the anti-pattern to keep
watching for on the next probe, not just this one.
