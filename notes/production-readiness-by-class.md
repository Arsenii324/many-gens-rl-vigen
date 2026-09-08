# "Are all things of this class ready?" — item by item

Written 2026-09-05, answering the owner's list directly. The list was given as a reference for a
*class*, so I have added the members they did not name but which belong to it.

**Short answer: no. Four are ready, five are partial, two are not, and one is audited but
unresolved.** Detail below, each with what would make it ready.

---

## READY

**Step and frame counts.** R4 is MET and computed, not asserted: at a 600,000-frame request the
seven runner families execute **599,040–600,064** — a spread of 0.17%, which is each family's own
rollout quantum and cannot be removed without editing a clone. Endpoint markers are verified per
family (`NATIVE_FINAL_EVALUATION_COMPLETED frame=N`), so a cell that lands elsewhere fails rather
than being silently accepted.

**Both train and eval results are produced and retained.** Training curves are kept per family at
their native cadence (`results/logs/`), evaluation records separately (`results/records/`). Six jobs
and 1,001 records are already retained this way.

**Downloadable whole, and post-processable.** `records.jsonl` is a *separate job output* from
`result.tgz`, so records can be fetched without the archive; both paths are exercised routinely.
Records are JSONL with a `schema` field.

**Rich rather than summarised, in structure.** Rows are per-episode, not per-cell means — the
property that makes any later aggregation possible. Per-scene and per-episode success flags are
carried, not just pooled rates.

## PARTIAL

**Eval frequency.** A 50k stamp grid is agreed and the descriptors carry `save_every`; the resolved
production environment now explicitly emits `CURVE_EVAL=1` and the endpoint/curve axes. The cadence
is wired, but no cell has demonstrated the full production shape end to end.
→ *Ready when one production-profile cell demonstrates it end to end.*

**Strength of intermediate eval.** The current default is **3 episodes × 4 regimes × 10 scenes per
stamp** (20 at the endpoint), after A20's cost decision; it is descriptive rather than inferential.
**It has never run at that full shape** — the preflight used 2 regimes × 1 scene × 3 episodes. The
cost is modelled, not measured at production depth.
→ *Ready when one cell runs the real shape and the timing is measured rather than assumed.*

**Checkpoint regularity.** All twelve now write stamped intermediates, and four families have
historical hardware evidence (`idaac` 4 stamps, `ppg` 6, `ibac_sni` 5, `ctrl` 1). That evidence is
not a current-revision discharge; the later ALDA/CTRL/RL-ViGen validation attempts failed before
they could establish the current fleet path, while `rlvigen` and `dmc_gb` still rely on mechanisms
not re-verified after the latest evaluator changes.
→ *Ready when one current-profile cell per distinct checkpoint path completes and its artifacts are
retained.*

**Post-hoc metrics from checkpoints.** Earlier jobs exercised six of seven evaluator families on
real checkpoints, but the current family-specific identity invalidates those as current assurance;
the live gate is **0/7**. The **full loop at production scale** — train → stamp → retrieve →
*fresh-process* reload → grid → records — has never run.
→ *Ready when the canary demonstrates it, plus the universal round-trip gate (compare distribution
parameters, not sampled actions).*

**Whole-fleet export. DONE 2026-09-08, and done before the data exists, as this entry asked.**
`scripts/export_fleet.py` emits one flat table across every `results/records/*.jsonl`, and
`--schema` prints the column contract from the same tuple the writer iterates, so the note cannot
drift from what is written. Verified over the current 2,119-record corpus: 12 baselines, and every
row accounted for.

Two decisions it makes, both pinned by `tests/test_fleet_export.py`, because an exporter written
after the data would have resolved them in whichever direction made that table come out:

- a row from a **superseded** closure is exported and marked (`closure_current`), never dropped.
  Dropping would make the export disagree with `results/records/` for a reason no reader can see;
  keeping silently would pool trees that no longer exist. `--current-only` is the caller's explicit
  choice.
- `policy_mode` rides on every row, because `idaac`, `ppg` and `ibac_sni` report a SAMPLED return
  and the other nine a mode return -- different estimands. A bare `return` column would invite the
  cross-block ranking `scripts/comparison_blocks.py` refuses.

It deliberately computes no ratios or retention: those carry caveats
(`docs/RESEARCH-FRAME.md`'s second-order interaction, C18's near-zero denominator), and a column of
numbers with its caveats stripped is how a caveat gets lost.

## NOT READY

**Eval runs do not yet record everything needed to understand the result.**
`scripts/production_gates.py` reports the rows are missing:

- **realized placement parameters** — a hash proves pairing but cannot answer "did performance
  depend on where the door was";
- **policy scale** (`log_std` mean/min/max) — σ ≈ 4.3 was perfectly finite and useless, and the
  finiteness gate cannot detect that failure, which we have already hit once;
- **vector-level action clip rate** — ~93% of 7-D actions clip at σ=1, which is what the environment
  experiences; only the per-coordinate 0.317 proxy is currently available.

Also unrecorded: **whether determinism was actually enabled for that row** (the `try/except` can fall
back silently), and a decision on per-step reward traces (~10^9 values fleet-wide — the one item
here that genuinely costs something).
→ *This is the only class whose omission cannot be repaired after the fleet finishes.*

**[Claude 2026-09-08] MOSTLY CLOSED — verified against a real record row, not against the gate.**
`scripts/production_gates.py` now reports `record completeness` and `placement provenance` as PASS,
and job `bt1ik7krfpjeftl65s3b`'s rows carry all four:

| item | field on the row |
|---|---|
| realized placement parameters | `native.placement_witnesses`, `native.placement_condition_seeds`, `native.eval_episode_ids` |
| vector-level action clip rate | `native.policy_action_diagnostics.action_clip_rate_vector` (alongside `_coordinate`) |
| determinism actually enabled | `evaluator_scope.deterministic_setting.enabled` + `.backend` + `.mode` |
| policy scale | `policy_scale` — present per episode, **`null` for drqv2** |

`null` there is correct rather than missing: DrQ-v2's TruncatedNormal takes a **scheduled** stddev
computed from the step, so there is no stored `log_std` for `eval_provenance.policy_scale` to find.

**What is NOT closed** is whether it resolves for the four families that DO carry a learned
`log_std` — `idaac`, `ppg`, `ibac_sni`, `ctrl`. The only test covering it
(`tests/test_eval_provenance.py:43`) hands the walker a synthetic object, which tests our idea of
the layout rather than the layout. A silent `None` for `ibac_sni` would mean the σ≈4.3 saturation
detector never fires for the exact family whose failure motivated it. The walker itself is sound —
it returns `log_std_mean 1.4586` from a real `nn.Parameter` at σ≈4.3 — so what is untested is the
attribute path into each family's own agent, and that is checkable in a container with no GPU.

Per-step reward traces remain undecided; `reward_min/mean/max` per episode are recorded.

**Reporting/analysis rules are not frozen.** The corrected statistics live in `notes/`, not in
`EVAL-PROTOCOL.md`: outer unit = training seed (n=3, **not** 600 episode rows), scenes as a fixed
grid, a numeric competence threshold, a missing-run policy, and the checkpoint-selection rule.
→ *Ready when merged and frozen — decisions A3–A8 on the sheet.*

## AUDITED BUT UNRESOLVED — the hyperparameters

This is better covered than I expected and worse in substance. `FAITHFULNESS.md` carries a
per-baseline divergence table with risk ratings, so the class **is** audited. What it records:

| baseline | divergence | risk |
|---|---|---|
| **`ppg`** | **rollout 256 vs upstream 65,536**, lr 1e-4 vs 5e-4, **continuous head has no reference** | **high** |
| **`curl`** | lr 1e-4 vs 1e-3; DrQ-v2-based rather than SAC; paper and code disagree five ways | **high** |
| `drq` | lr 1e-4 vs 1e-3 (n-step fixed 2026-08-10) | low-medium |
| `soda` | official and active production launchers use aux lr 3e-4; generic parser default remains 1e-3 | low |

`ppg`'s rollout being **1/32 of its reference** is the one I would put in front of a reader: it
changes the optimisation regime, not a detail, and it compounds with the auxiliary phase first
firing at 65,536 frames. Neither high-risk item is *resolved*; both are recorded with a stated risk.
→ *These are declarations, not defects — but they belong in the write-up's limitations, not a
footnote, and the two `high` ratings deserve an explicit owner decision.*

## The caveat that applies to this whole page

`audit_comparability_seam.py` reports every axis as derived or recorded — but its own output says
this is relative to a **hand-maintained list**: *"Add the next one to NOT_COVERED as…"*. So
"everything is covered" means "everything anyone has named". The three external reviews each found
axes nobody had named. That is the honest bound on any completeness claim here, including this one.

---

# CORRECTION, same day — I wrote the above on thin evidence

The owner asked whether I was ready to write this. I was not. Before writing it I had checked the
mailbox, grepped for whether a hyperparameter audit existed, and **read six lines of a table**;
everything else came from session memory. What further research changed:

## 1. Five high-severity divergences, not two

The full `FAITHFULNESS.md` table lists, at **high** or **critical**:

| baseline | divergence | note |
|---|---|---|
| `svea` | **uses SODA's overlay, not SVEA's random convolution**; DrQ-v2-based not SAC | **verified current** |
| `ctrl` | **structural**: `L_clust` absent; positives from the same partition, not a neighbouring one | **first half appears superseded** |
| `idaac` | rollout 256 vs 2048 continuous; 8-sample minibatches | |
| `ppg` | rollout 256 vs 65,536; continuous head has no reference | |
| `curl` | lr 1e-4 vs 1e-3; DrQ-v2-based not SAC; paper/code disagree 5 ways | |

`drqv2` (stddev schedule from the wrong tier) and `sgqn` (`aux_lr` 0.3 vs 3e-4 — **1000× on the
shared encoder**) were high/critical and are marked FIXED 2026-08-10.

## 2. `svea` verified: the divergence is real and current

`RL-ViGen-upstream/algos/svea.py:12` imports `random_overlay`; `:298` applies it as the strong
augmentation. So our `svea` is SVEA's *loss form* with **SODA's augmentation** — in a baseline
RL-ViGen publishes at **268.8** on Door, i.e. one of the four that generalise well there. The row is
"RL-ViGen's SVEA", not SVEA.

## 3. `ctrl` — the table appears stale, and my own R6 audit was right for the wrong reason

`loss_cluster` is defined (`algo.py:173`) and its gradient **is** applied (`:558`), so "L_clust
absent" looks superseded — by a repair this project made: as released, two lines were commented out
while their result was still used, so `loss_cluster` raised `NameError` and **ctrl_public @ 7a118c8
could not run its own algorithm at all**. Restoring the authors' own lines was the fix. The second
half of the claim — positives drawn from the same partition rather than a neighbouring one — I did
**not** verify and it may well stand.

## 4. The weakness this exposes in `audit_implementations.py`

My R6 audit passes a baseline when *marker symbols are present in the source*. That is too weak in
exactly the way this research shows:

- **`svea` PASSES my audit** (`aug_obs`, `aug_loss` both present) while applying the wrong
  augmentation. Presence of the consistency-loss form says nothing about which augmentation feeds it.
- **`ctrl` would have PASSED** even in the released state where `loss_cluster` raised `NameError` on
  first call, because the symbol is present either way.

A mechanism check must ask whether the term reaches the **gradient**, and whether its **inputs are
the right ones** — not whether a name appears. R6's verdict of 12/12 at 6e5 should be read with that
limitation attached until the audit is strengthened.

## 5. And the currency caveat I should have led with

`FAITHFULNESS.md`'s summary is tagged **`[MIXED]`** by its own header, and its banner records that
two earlier banners were wrong. Some rows are dated ("FIXED 2026-08-10"); the `ctrl` row is not, and
appears to predate a repair. **So I cited a partly-stale document as current.** Reconciling that
table against the clones is itself an open task, and it is a prerequisite for any claim about this
class being "ready".

---

# UPDATE 2026-09-05 (later) — reviews 6, 7 and 8 change several answers on this page

Evidence and verification for each: [`review-6-7-8-triage.md`](review-6-7-8-triage.md).

## Moved from "ready" to "was never ready, now fixed"

These were not on any risk list because nothing had looked:

| item | what it actually was | now |
|---|---|---|
| **remote offline evaluation, all 7 families** | `eval_provenance` required `rlgen/protocol.py`; `contract.py` never shipped it. **No remote evaluation could complete** — two jobs died on it | fixed + `tests/test_payload_contract_covers_provenance.py` |
| **`ppg` evaluator** | witnesses copied before the rollout, diagnostics read after teardown. **Every ppg cell would have terminated** | fixed + a structural test across all seven `run_scene*` |
| **`ctrl` evaluated return** | summed the outermost `VecNormalize` reward — **not in Door units, not comparable with the other eleven** | fixed to CTRL's own `normalize_rewards=False` evaluation convention |
| **`ibac_sni` VIB coefficient** | launcher passed no `--beta`, so **1.0 applied against the 1e-4 the fidelity table claimed** | fixed to 1e-4; **all prior competence evidence is void** |

## The class question this page exists to answer, restated

The owner's list was: eval frequency, what is reported, whether the report is rich and downloadable
and post-processable, train **and** eval results, intermediate evals that are not over-aggregated,
regular checkpoints that can be retrieved and re-evaluated, post-hoc metrics from checkpoints, no
skipped metrics, step/frame counts, and whether the parameters are right.

**On the reporting half, the answer is now stronger than it was this morning:**

- every offline record carries index-aligned per-episode arrays — returns, success flags, placement
  condition seeds, placement witnesses, full per-episode diagnostics — so post-hoc aggregation does
  not depend on us having chosen the right aggregate in advance;
- each of those episodes is now **named** (`eval_episode_ids`), not merely positioned;
- offline rows now carry the same `_run_provenance` training rows always had, so a record is
  auditable without fetching the archive it came from;
- the evaluator revision now includes the per-family evaluation configuration, so two materially
  different evaluator setups can no longer share one identity.

**On the parameters half, the answer got worse before it got better.** The `beta` defect is the
clearest possible instance of the question being the right one to ask: a parameter that was
researched, sourced, written into the fidelity table — and never reached the process. It went
unnoticed through five prior reviews, an audit that reports "12/12 genuine", and a fidelity ledger
that cites its value. **`audit_implementations.py` checks that mechanisms are present; nothing in
this tree checks that a claimed hyperparameter is the one the process runs.** That gap is now the
most likely place for another finding of this size, and it is not closed — `tests/test_ibac_beta_is_wired.py`
closes it for exactly one parameter of one baseline.

## Still NOT ready, unchanged

The owner gates, the uncommitted tree, the production-host configuration (`A14`, still "NOT YET
APPLIED"), the shared-evaluator revalidation under one frozen revision, the exact-final IBAC
competence pilot, and the 600k canary. Reviews 7 and 8 both put the configuration freeze *before*
the pilots, and both are right: an IBAC pilot at `procs=1` measures a different algorithm from the
`procs=16` production target. The repaired `procs=16` path now completes a short functional smoke
on DataSphere `gt4i.1` and fits its 27 GiB RAM, but that does not prove competence or the production
V100 host, so the exact-final pilot remains a production-host job rather than something to buy on
the smaller `gt4.1` tier.

## Two more items from the owner's list, checked today

**Checkpoint regularity and re-evaluability — READY.** Cadence is a uniform **50,000 frames** across
all seven families, and every family's descriptor carries the reason its number is what it is.
The two overwrite hazards are both closed: patch **P18** keeps the RL-ViGen five's intermediate
saves (upstream writes twelve and keeps one), and `ibac_sni` writes `model_<frames>.pt` beside the
fixed `model.pt` it overwrites (`torch_rl/scripts/train.py:320`). The descriptor note claiming
ibac_sni still "needs preserved COPIES" was stale and is corrected in place.

**Intermediate evaluation — POSSIBLE, NOT SCHEDULED.** This is the gap. `run_curve_eval` is opt-in
behind `CURVE_EVAL=1` and `production-schedule.json` never sets it, so a production cell as
scheduled today yields **one** evaluation at the endpoint and eleven unevaluated checkpoints. The
weights are retained, so nothing is permanently lost — but "we have a training curve" would not be
a true statement about the records, and retention alone does not satisfy the requirement.
New decision **A20** carries the fork and a costed default (curve at reduced depth: two regimes,
three scenes, ten episodes — about 1x the endpoint's cost rather than the 12x a full grid per stamp
would take).

**Frame counts — READY.** `production-schedule.json` now carries **600000**; reviews 4 and 5 found
it describing a 100k/500k experiment and that is fixed.

## Correction 2026-09-05, RETRACTED — the replay cap IS real

A claim was briefly published here that the cap evicts only 0.40%, computed from `action_repeat: 2`
in `cfgs/config.yaml`. **`runnable/_launch/rlvigen.sh:78` overrides it to `action_repeat=1`**, so
600,000 frames is 600,000 agent steps and the 300,000 cap discards about half the experience, as
originally recorded. See `CORRECTIONS.md` #35/#36.
