# External review 15 — triage against the executable tree

**Snapshot:** 2026-09-06. Source: `notes/ai-review-15-external-processed.md` (built at commit
`6727a1f1241b4e57ba27d4ca9f53c1bad62b46d3`, mid-session — several items below were already
resolved or promoted by the time this triage was written, later the same day). Re-run
`python scripts/production_gates.py` / `python scripts/open_decisions.py` before treating a status
below as current; this is a disposition of hypotheses, not a live feed.

Statuses used here, matching `review-11-12-gemini-triage.md`'s vocabulary:

- **RESOLVED** — the reviewer's own concern no longer applies; confirmed, not asserted.
- **PROMOTED** — the concern had no concrete "our best" answer before; now has one, recorded as a
  `notes/DECISION-SHEET.md` entry marked `ANALYSIS INCOMPLETE` until compute is spent on it.
- **ALREADY TRACKED** — the concern already has a DECISION-SHEET/CORRECTIONS entry with a stated
  reading; review 15 corroborates rather than discovers.
- **FIXED** — a concrete, checkable bug; fixed and tested this session.
  **COMPUTE-BOUND** — no further analysis closes this; it needs an actual run, and the reviewer's
  own "not yet established" framing already says so.
- **INFORMATIONAL** — a correct observation that constrains interpretation but names no action.

| § | topic | status | note |
|---|---|---|---|
| 1 | `source-lock.json`'s root commit names the legacy tree | **FIXED** | CORRECTIONS.md #95. Confirmed via `git cat-file`: the old value wasn't just stale, it didn't exist in this repository at all. Fixed to current HEAD; added a test checking the recorded root is a real ancestor of HEAD (not literal-equality, which no committed value can satisfy) |
| 2 | PPG's remaining continuous-control recipe gap (lr, gamma, entropy, minibatches) | **PROMOTED** | DECISION-SHEET A36. T16's cadence half was already fixed (A26); the rest had never had a concrete spec. Independently corroborated by C61 (a sibling port's measured categorical-to-Gaussian entropy-coefficient failure) |
| 3 | IDAAC's episode-identity bug | **RESOLVED** | Reviewer's own re-trace confirms the full chain fix, not just the wrapper |
| 4 | IDAAC's continuous-control design point, `order_loss_coef` 100x below precedent | **PROMOTED** | DECISION-SHEET A35 — the review's own top priority. Full current-vs-proposed parameter table, pilot sizing, and a decision rule stated before either arm runs |
| 5 | IDAAC's episode ID is a conceptual (not implementation) adaptation | **INFORMATIONAL** | Correctly constrains how a weak IDAAC result should be interpreted later; names no action now |
| 6 | IBAC's β and fork-RNG fixes | **RESOLVED** | `--beta 1e-4` (A17) and the spawn-based multiprocessing redesign are both already in the tree; reviewer's own re-check confirms |
| 7 | IBAC-SNI's hybrid lineage (CoinRun trunk + PyTorch/GridWorld bottleneck) | **PROMOTED** | DECISION-SHEET A37 — commits to the CoinRun/visual lineage as the reference, with reasoning, rather than re-stating "choose a coherent lineage" as if that were itself an answer |
| 8 | IBAC competence under the final configuration | **COMPUTE-BOUND** | Already `production_gates.py` OWNER ("ibac_sni competence"); separately blocked on the actual production host per A1's revision (a smaller-process pilot measures a different rollout geometry, not the production one) |
| 9 | CTRL's evaluator bugs (normalized-return, double-reset) | **RESOLVED** | Both already fixed and tested this project; reviewer's own re-check confirms |
| 10 | CTRL's raw-vs-executed (pre-clip) action for representation learning | **ALREADY TRACKED** | DECISION-SHEET A30 — traced in more depth than three prior reviews combined (11/12/14), and found to be a 3-family issue, not CTRL-specific. Already has a stated "declare, don't compensate without evidence" reading and an explicit re-open trigger (`clip_fraction`/`approx_kl_k3`) |
| 11 | CTRL's V100 memory model (13.4 GiB) is stale after the return to 64 envs | **COMPUTE-BOUND, flagged not fixed** | Confirmed the number is genuinely unchanged (`production-schedule-v100.json`'s `cell_ram_gib_model: 13.4`, `cell_ram_model_basis: "on-policy rollout only, budget-independent"`) since before the 16->64 env restoration. No generator script computes this value from source — it is a recorded measurement, not a derived one — so there is nothing to "recompute" without an actual run. This is exactly the "CTRL 64-env resource evidence" Codex named as one of the remaining compute-bound closures (mailbox Q45). Do not trust this number for capacity planning until a real 64-env V100/gt4i.1 canary measures it |
| 12 | The off-policy A27 "0.25 UTD" correction | **RESOLVED** | Reviewer's own words: "the current correction is sound... I would not alter RAD/SODA on the old A27 reasoning" |
| 13 | Native-five replay capacity (620k vs 300k) | **RESOLVED** | Reviewer's own words: "I would not block DrQ-v2/DrQ/CURL/SVEA/SGQN over this anymore" |
| 14 | Places365 train-vs-validation split | **ALREADY TRACKED** | A documented, deliberate deviation (disk-space constrained on DataSphere), not a blind spot. Reviewer's actual new point — now that production isn't disk-constrained (V100 host), reconsider — is a live one; no DECISION-SHEET entry yet reopens it against the changed constraint. Worth a follow-up entry if the owner wants to revisit before production, not urgent enough to promote unilaterally here |
| 15 | SVEA/CURL implementation-identity naming precision | **INFORMATIONAL** | Presentation/provenance, not a reason not to train; no DECISION-SHEET action needed |
| 16 | Time-limit/horizon-truncation semantics split across families | **ALREADY TRACKED** | C1 / DECISION-SHEET A5's revision already lands on exactly the reviewer's own recommendation: report the difference, drop the directional claim, don't force one convention |
| 17 | The twelve-way comparison isn't an algorithm-only ablation | **ALREADY TRACKED** | Matches this project's own stated estimand framing (`RESEARCH-FRAME.md`, P-C76) throughout `docs/CONSTRUCTION.md`/`FAITHFULNESS.md` |
| 18 | Common evaluator validation, current revision | **IN PROGRESS, restarted** | Was 5/7 under schema 1; CORRECTIONS #94 found schema 1 itself was profile-coupled (unrelated to this review), so all entries are now schema-2 legacy. `evaluator_identity.py` schema 2 is fixed and committed; a fresh seven-family revalidation wave is prepared locally (Q44/Q45) but not submitted — needs owner spend authorization |
| 19 | Condition-seeding pairs appearance, not scene, across regimes | **INFORMATIONAL** | Correct characterization of an already-deliberate design; no action named |
| 20 | Physical episode diagnostics are now strong | **RESOLVED** | Reviewer's own words: "that's now a strong design... not another rewrite" |
| 21 | Final V100 renderer equivalence (C95) | **COMPUTE-BOUND, in progress** | The whole point of the C95 renderer-parity work this session. Currently blocked on a real record-delivery bug (mailbox Q37, now fixed) and V100 budget (51.6 of the needed 100 minutes remain) |
| 22 | An RL-ViGen positive-control run on the final platform | **ALREADY TRACKED** | DECISION-SHEET's A9 revision already answers the ordering concern for the *external* anchor without a dedicated cell (a free acceptance test against production drqv2 seeds); the *platform* positive-control the reviewer asks for here is the same C95 work, not a second requirement |
| 23 | Normalized-record schema: can a paper row mechanically recover its training manifest | **NOT YET CHECKED** | A real, cheap, unchecked verification — "given one final normalized row and nothing else, can the aggregation code recover exactly one training manifest." Not promoted to a DECISION-SHEET entry because it doesn't need a design choice, it needs someone to actually trace one row through the pipeline once. Worth doing as a quick follow-up, not urgent enough to block this triage |
| 24 | High-level protocol hash is not the complete experiment identity | **RESOLVED** | Reviewer's own words: "that addresses part of my previous criticism... that's fine if aggregation keeps the two concepts separate," which the current code already does |
| 25 | Exact interaction budgets differ slightly from 600,000 | **INFORMATIONAL** | Reviewer's own recommendation ("do not deform the loops... simply record the actual count") is already this project's practice |
| 26 | Statistical protocol (seeds, checkpoint primacy, no pseudo-replication) | **ALREADY TRACKED** | DECISION-SHEET A28/A32 |
| 27 | Success rate should outrank return ratios | **ALREADY TRACKED** | DECISION-SHEET A18 (floor-adjusted retention, implemented) and the project's own stated metric-priority ordering |
| 28 | Don't select checkpoints against the final OOD grid | **ALREADY TRACKED** | `production_gates.py`'s "checkpoint rule frozen" gate (endpoint-as-headline, no peeking) |
| 29 | Native RL-ViGen subgroup status | **INFORMATIONAL** | Summary judgment; no new action beyond §14/§18/§21 above |
| 30 | RAD/ALDA status | **INFORMATIONAL** | Summary judgment; no new action beyond §18/§21 |
| 31 | Overall risk classification (IDAAC/IBAC/CTRL highest) | **INFORMATIONAL** | Matches this triage's own weighting — A35/A37/A30 are exactly those three, and they are the three `ANALYSIS INCOMPLETE`-or-`OPEN` items this triage treats as highest priority |

## What this triage adds beyond the review itself

Two things: (1) three genuine "our best" specs that didn't exist before (A35 IDAAC, A36 PPG, A37
IBAC lineage) — the review named the gaps, it didn't and couldn't produce the parameter tables,
since that requires reading this project's own source, not just the published papers; (2) one real
bug fix (#95, source-lock root) and one honest non-fix (§11, CTRL's memory model correctly
identified as unmeasured rather than silently patched with a guessed number).

## What remains genuinely compute-bound after this triage

Matches Codex's own closing list in mailbox Q45: all seven evaluator family validations under
schema 2, IBAC-SNI competence at `procs=16` (needs the actual production host), C95 renderer
R_A/R_B, CTRL's 64-env resource canary (§11), and eventually a 600k end-to-end production canary.
None of these are analysis gaps anymore — they are spending decisions.
