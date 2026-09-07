# Review 19's own "launch gate" — status against the current tree

> **Superseding update, 2026-09-07:** the v185 functional endpoint wave is complete for all
> seven evaluator families and is accepted by `production_gates.py` (7/7 current closures;
> retained artifacts are in `results/validation/`). This closes evaluator-path validation, not
> production-length competence or host migration. The resource/throughput recertification below
> remains open where it requires the production V100 host.

Written after reading `notes/ai-review-19-external.md` in full (1140 lines), cross-checked
against `00-review-19-triage.md` (Codex's independent triage) and the tree as of commit `c10719b`.
Review 19's final section, "My actual launch gate now," gives an explicit numbered checklist of
what "fidelity-complete" requires. This file states, item by item, whether the current tree
satisfies each one — not a re-triage of the whole review, which `00-review-19-triage.md` already
does well.

## "Must resolve or explicitly profile before calling the setup fidelity-complete"

1. **SODA `--aux_lr 3e-4` in production.** SATISFIED. `runnable/_launch/dmc_gb.sh` now passes it
   explicitly for `soda`, matching the official `runnable/dmc_gb/scripts/soda.sh`.
   `tests/test_soda_source_contract.py::test_production_launcher_preserves_official_soda_auxiliary_lr`
   pins it. Commit `b1a4c5a`.
2. **PPG's 1×2048/32-minibatch/3-frame continuous-reference adaptation actually in the tree, not
   just described.** SATISFIED. `families.json`'s `ppg` constants carry `frame_stack=3, gamma=.99,
   lr=3e-4, aux_lr=3e-4, nminibatch=32, entcoef=0`; threaded through `ppg_cell.sh` → `train.py` →
   `get_venv`'s `FrameStack` wrapper, and symmetrically into `ppg_eval.py`'s offline evaluator.
   `tests/test_ppg_c2_contract.py` builds a real 9-channel checkpoint and evaluates it through the
   actual CLI, not a mock. Commit `b1a4c5a`. (Note: `num_envs`/`nstep` remain `8`/`256`, a
   resource/domain adaptation from the source's `1`/`2048` per-process rollout — this is the
   already-declared A26 axis, not a gap review 19's own text treats as needing a fix.)
3. **IBAC-SNI's 256-d shifted-scale 12-sample CoinRun VIB/SNI, L2, and UDA semantics landed, or the
   baseline explicitly called a partial hybrid.** SATISFIED VIA THE SECOND OPTION, not the first —
   review 19 itself offers this as an acceptable fallback ("or explicitly call the current baseline
   a partial hybrid"). None of the mixture-policy/256-d/L2/rectangle-UDA work has been implemented
   this session; `notes/CLAIMS-LEDGER.md`'s `ibac_sni` row and `docs/CONSTRUCTION.md`'s A37 both
   already state plainly that this is "an authored hybrid of the authors' PyTorch and CoinRun
   implementations," not a claim of CoinRun fidelity. Genuinely still open as an implementation
   task (DECISION-SHEET A37, `production_gates.py`'s `ibac_sni competence` OWNER row) — not a
   documentation gap.
4. **SGQN: explicitly choose `RLViGen-paper` or `RLViGen-release`, including feature dimension in
   the conflict.** SATISFIED. `CLAIMS-LEDGER.md`'s `sgqn` row now states all four conflicts
   (feature_dim 50 vs 256, aux_lr 1e-4 vs 8e-5, quantile .93 vs .90, consistency .9 vs .7) and
   declares the released-code profile as "the one predeclared configuration — not a silent
   retune" (matches C64, already ratified). Review 19's own stated preference (the paper profile,
   for a "reproduce RL-ViGen's Door baselines" framing) is a live disagreement worth recording
   here rather than silently resolving: this project's chosen default is released-code, not
   paper-table. Both are defensible; the tree does not blur which one it runs.
5. **SVEA: record RL-ViGen-release vs canonical-SVEA provenance, and the feature-dimension
   conflict.** SATISFIED. `CLAIMS-LEDGER.md`'s `svea` row now states the feature_dim 256-vs-50
   conflict. `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` §5.2 (fixed this session, before review
   19 was read in full) narrows the Core-method row's "EXACT SOURCE MATCH" to the joint-loss
   mechanism only, and adds a dedicated Augmentation row stating the `random_overlay`-not-
   `random_conv` swap. Independently corroborates review 19's own §7 finding that "the change is
   not just 'same SVEA but DrQ-v2 underneath' — the strong augmentation source changes too."
6. **CTRL: keep the paper/release conflict explicit; do not revert to "paper table wins."**
   SATISFIED, unchanged. C97 remains open with the released-code profile as the operational
   default, exactly as review 19 now itself recommends (its own correction, §5: "I was too
   categorical").
7. **Source-target/provenance labels on result manifests.** SATISFIED. All 12 baselines carry a
   `{source_target, source_variant}` pair in `families.json`, read through `family.provenance_for`
   (fail-loud on a missing/malformed label), threaded through `normalize_curves.py`,
   `eval_grid.py`'s shared record factory, and `results_table.py`'s row/display functions.
   `docs/EVAL-PROTOCOL.md` states explicitly these are disclosure metadata, not a faithfulness
   verdict. `tests/test_provenance_labels.py` pins the whole chain end to end. Commit `b1a4c5a`.

**All seven "must resolve" items are now satisfied** — five by landed implementation, two
(IBAC-SNI, and the SGQN/paper-vs-release choice) by the honest-labeling fallback review 19 itself
names as acceptable. This does not mean the project is "fidelity-complete" in review 19's own
stronger sense (see below) — it means the specific gate this section poses is cleared.

## "Strongly recommended, but do not invalidate the algorithms"

8. **Runtime-observed, independent geometry certification** (declared vs. observed-at-construction
   vs. checkpoint-expected, failing startup on any mismatch) — NOT DONE. Correctly named as open in
   `00-review-19-triage.md` ("production hardening item, not evidence current rows are
   reinterpreted"). `rlgen/protocol.py::OBSERVATION_GEOMETRY` remains the single declared source of
   truth; nothing cross-checks it against an actual constructed tensor's `.shape` at every
   production call site as one automated gate. Worth doing, not done.
9. **SHA256 provenance chain** (per-baseline upstream URL/commit/pristine-tree/patch/final-tree
   hashes) — PARTIALLY DONE, differently shaped than review 19 asked for. `scripts/
   build_external_review_artifact.py` (committed `722bc3f`) computes a project-tree-level
   `source_tree_digest`, per-included-file SHA256, `builder_sha256`, and git commit/branch/dirty
   state — real cryptographic provenance, but at the whole-tree level, not the per-baseline
   upstream-commit ledger review 19 describes (`docs/RUNNABLE-ORIGINALS.md` and
   `docs/ORIGINAL_LOCATIONS.md` carry the per-baseline upstream commit SHAs already, in prose, not
   as a machine-checked hash chain). Not the same artifact; overlapping intent.
10. **Current-state docs generated from the resolved configuration, not hand-maintained prose** —
    NOT DONE. `docs/CONSTRUCTION.md`/`CLAIMS-LEDGER.md`/`DECISION-SHEET.md` remain hand-written,
    append-only registers. This is a real, named, unaddressed structural recommendation (review
    19 §20's `CURRENT_EXECUTED_CONFIGURATION.md` proposal) — the project's actual mitigation is
    the append-a-dated-correction convention plus tests like
    `tests/test_docs_not_stale.py`/`test_provenance_labels.py` that catch specific drifts, not a
    generated single source of truth.
11. **Re-certify IDAAC's new resource use on real infrastructure** — FUNCTIONAL PATH CLOSED;
    RESOURCE RECERTIFICATION OPEN. The v185 evaluator wave validates evaluator behavior/identity
    for all 7 families against the frozen tree, but is a short (8,192–10,240 frame) functional
    run, not the throughput/memory recertification review 19 names. A 40,960-frame g1.1 C2
    rehearsal exists (`bt1596tjbdu1rv5senim`), but the production V100 host measurement remains
    open; see `MIGRATION-T4-TO-V100.md` step 1.
12. **Host/horizon-qualified replay-equivalence wording** — SATISFIED, already fixed. `CLAIMS-
    LEDGER.md`'s `drqv2` row and `docs/DECISION-SHEET.md` A14 both scope the "non-evicting"
    claim to the V100 600k profile specifically, not a global claim.
13. **Best-in-group statistical comparisons stay descriptive or selection-aware** — OPEN, correctly
    an OWNER item (`production_gates.py`'s "statistical protocol frozen" gate, DECISION-SHEET A25).
    No code change; a reporting-policy ratification, already stated as a default.

## "Optional sensitivity arms, not prerequisites" (14-17)

Not built (canonical RAD/SVEA/CURL/SGQN arms beside the RL-ViGen variants) — review 19 itself
says these are valuable for a methodological paper but not required to run the RL-ViGen Door
benchmark. Consistent with this project's one-predeclared-main-run-per-algorithm scope (Q55); not
a gap against the current campaign's stated goals.

## What this file does not do

It does not re-litigate review 19's meta-recommendations (§16 source-precedence policy, §17 two
fidelity axes, §18 display-name renaming) — those are named, undone, and already tracked in
`04-blind-spots-and-unverified-claims.md`'s "things both reviews asked for that I didn't do"
section; nothing here changes that status. It does not re-verify SODA/IBAC-SNI/CTRL primary-source
claims independently of what `00-review-19-triage.md` and this session's own commits already
verified — see those for the evidence trail.
