# External reviews 20 and 21 — item-by-item accounting

Written 2026-09-07. Every row was checked against the live tree before being called stale, fixed or
open — not against the review's description of the tree. Three of the reviews' findings did not
hold here, and saying which is as much the point as fixing the ones that did.

`C.zip`, the artefact both reviewers read, is a snapshot. Where a finding is marked **stale**, it
was true of that snapshot and is not true of this tree; the commit that closed it is named.

## Review 21

| # | Finding | Status | Evidence |
|---|---|---|---|
| 1 | **P0** "online evaluation disabled" evaluates at step 0 for eight baselines | **FIXED** | Real and verified: `Every(2147483647,1)(0) is True`. `run_probe.sh` spelled "disabled" as a huge cadence and every affected loop gates on `step % cadence == 0`. rlvigen now disables through upstream's own None-cadence path, dmc_gb and alda through an explicit guard. New gate `online eval disable executed` reads the mechanism, not the descriptor. CORRECTIONS #99 |
| 2 | **P0** idaac's evaluator attestation stale | **STALE — did not hold** | Recomputed all seven revisions from the live tree before touching anything: every one matched the ledger. The review's `C.zip` predates commit `0ef59ab`. Its *advice* — do one wave after the source changes, not per-family — is followed |
| 3 | **P0** renderer/container parity is a precondition | **OPEN, host-bound** | Agreed and already this project's own C95 gate. Its CTRL-specific addition (prove JAX uses the V100 backend, not a CPU fallback) is now in the runbook's §1 checks |
| 4 | **P0** CTRL restores 64 envs but carries a 16-env memory number | **PARTLY STALE, tooling FIXED** | The v100 schedule already carried 54.28 GiB, not 13.4. But `check_memory` resolved the BASE descriptor, had no `v100` tier at all, and was never called by the runner — so the host had no memory preflight of any kind. All three fixed; packing on an extrapolated figure is now refused outright |
| 5 | IBAC-SNI has runnability but not competence evidence | **OPEN, host-bound** | This project's own `ibac_sni competence` OWNER gate says the same thing |
| 6 | Places365 val-vs-train split | **REASONING CORRECTED, decision stands** | The review is right that "same split for all three" does not imply invariant ordering — svea, soda and sgqn consume overlays through different objectives. That inference is withdrawn from A22 and CLAIMS-LEDGER. The decision stands on cost (105 GB vs the 477 MB asset) and on the fact that adopting it only where feasible would make the augmentation distribution platform-dependent |
| 7 | PPG sits between two identities; freeze it | **FIXED, and the review was more right than it knew** | Reading `raileanu21a-supp.pdf` §E directly: this port already ran §E's shared grid in every value that distinguishes the identities, each deviating from PPG's own release. Linear LR decay implemented and set to 1e6 env steps. A36 then adopted §E's 1x2048 rollout after the matched same-tier probe; all hosts now inherit that geometry. |
| 8 | ALDA UTD=1 stability check before three long runs | **ANSWERED, arm cancelled** | ALDA-P (`utd=1.0`) already SUCCEEDED at 150k, which is the arm the production decision turns on. The 0.25 arm was resubmitted, then cancelled as answering nothing we act on — under fidelity-first we run 1.0 regardless, and divergence after 150k is addressed by the production seed's own `check-finite`, not by the C arm. A27 |
| 9 | RL-ViGen provenance strings understate the modification | **FIXED** | Verified against the classes first: `svea.py:165` is DDPG-shaped with `random_overlay`; `sgqn.py:119` and `curl.py:54` inherit `DrQV2Agent`. `provenance_for` now says so, and it feeds every emitted record |
| 10 | Winner-versus-winner is post-selection inference | **FIXED** | A25 replaces it with three fixed cross-group pairs named on scientific grounds before any outcome exists, plus a group-level aggregate. Winner-vs-winner demoted to the supplementary matrix, labelled post-selected |
| 11 | `effective_config.json` is not exhaustive | **FIXED** | It was a hand-maintained allow-list missing `NATIVE_ISOLATE_ONLINE_EVAL` and every endpoint/curve/offline axis. Captured by prefix now, with an explicit secret filter |
| 12 | Memory preflight weaker than the replay model | **FIXED, and worse than reported** | `fixed_peak_gib` for rlvigen is 3.33 GiB and EXCLUDES the replay; the v100 profile restores a 620k buffer worth 35.5 GiB. `check_memory` would have certified a drqv2 cell at 5.33 GiB while the schedule said 38.78. It now imports the planner's model — one memory truth |
| 13 | Two stale questions in `OPEN-QUESTIONS.md` | **STALE — already closed** | Q1 and Q4 were both answered 2026-09-07 by fresh Hydra composition, before the review arrived |
| 14 | `seed+i` is not independent per-env placement RNG | **STALE — already documented** | `docs/CONSTRUCTION.md:3347-3352` states exactly this, names all three files (idaac, ctrl, ppg), and backs it with a crossed measurement |
| 15 | Make "restart from zero" explicit for off-policy | **FIXED** | The per-family resume table in `RUNNING-ON-PRODUCTION-HOST.md` §6 is generated from the source of each save site; A24's rerun-the-seed policy is named as the operational consequence |

## Review 20

Its P0/P1 rows overlap review 21 substantially. The distinct ones:

| Finding | Status |
|---|---|
| PPG `aux_lr=3e-4` weakly sourced | **RESOLVED by §E** — the searched rate is 3e-4 and §E says the best values were used "for all the methods". PPG's own release is 5e-4, so this is a comparator value, consistent with the identity now frozen |
| IBAC-SNI must not be called high-fidelity | **ALREADY SATISFIED** — `CLAIMS-LEDGER` calls it "a continuous-action adaptation" and "an authored hybrid of the authors' PyTorch and CoinRun implementations" |
| Physical pairing not demonstrated from a current record | **STALE** — the `pairing proven physically` gate reads 55 eligible cross-regime comparisons, 0 unpaired, 0 lacking physical evidence |
| Gaussian ports may train on unclipped actions | **DECLARED** — the `induced action distribution` axis in `audit_comparability_seam.py` carries it; review 21 independently agreed not to "repair" it |
| n=3 and best-in-group inference | **FIXED** — see review 21 #10 |
| Time-limit 3-bootstrap / 9-terminal | **DECLARED** — C1, and `notes/FINDING-c1-does-the-asymmetry-cancel.md` establishes the bias cannot enter the reported arithmetic while neither Δ nor retention is protected by construction |

## What both reviews converge on, and what remains

Both call the same four things blockers, and all four are host-bound rather than unresolved:
renderer/container parity, CTRL's 64-env memory, IBAC-SNI competence at the exact final geometry,
and one complete production canary. Codex's arrival sequence in `RUNNING-ON-PRODUCTION-HOST.md` §0
orders them; `MIGRATION-T4-TO-V100.md` derives them.

**The earlier two-attestation warning is historical.** After A36, the v185 single final wave
completed and the ledger accepts all seven current evaluator closures; its retained artifacts are
under `results/validation/`. The remaining blockers below are host-bound, not evaluator-path
validation.

**Found by this pass, named by neither review**: packed cells had no GPU assignment and would both
have landed on `cuda:0`; the live run directory was not mounted, so a killed container lost every
checkpoint; the disk floor was one constant that was thirty times too strict for the on-policy
families; and `idaac`'s linear LR decay is our addition from the paper, absent from
`ext/idaac/train.py`, which needed the governing principle written down.
