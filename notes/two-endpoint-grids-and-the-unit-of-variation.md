# Two complete endpoint grids, two defects, and the wrong standard error

**2026-09-10**, from `card0-20260909-035152` (idaac-s101) and `card0-20260909-115331` (ppg-s1).
Both cells ended marked `NATIVE_CELL_FAILED`. **Both nevertheless carry a complete, valid
production result**, and establishing that cost no run at all.

Prior art this builds on rather than repeats: [`first-complete-endpoint-grid-idaac.md`](first-complete-endpoint-grid-idaac.md)
already reports idaac's table, already explains `eval-hard > eval-medium` from upstream's shared
magnitudes, and already refuses the borrowed floor. What is new here is ppg as a second family, and
a correction to the standard error in that note.

---

## 1. What is reportable, and why "failed" was the wrong summary

`family_eval_policy_mode` makes **sampled** the native estimand for both families
(`SAME-AXES-VERDICT.md`). The sampled endpoint pass is the reported number; the `mode` pass is a
supplement.

| cell | sampled endpoint | mode pass | what actually failed |
|---|---|---|---|
| idaac-s101 | **44/44 rows** | 41/44 | watch-budget stop took 3 eval-hard rows |
| ppg-s1 | **44/44 rows** | 0/44 | the `no_grad` defect in §3 |

44 = 4 regimes × 11 scene sets (ten scenes plus the pooled aggregate). **Both primary grids are
complete.** The cell-level `FAILED` marker is correct about the cell and wrong about the result,
and nothing in the runner said so.

**Validity** (`scripts/audit_eval_validity.py`, both files, exit 0):

- row summaries match their own raw episodes — PASS
- **800 episode ids each, 0 duplicated, 0 mismatched** — PASS
- placement seed identical across regimes and frames — PASS, so the regimes are **paired**
- reset observation reproducible **200/200 in every regime** for both cells

## 2. The numbers

Endpoint, sampled, pooled row only. Door's horizon is 500 and success sets 1.0 while shaping pays
at most 0.25 reaching + 0.25 latch, so a return **above 250 proves success** and anything below it
without success is shaping alone.

| cell | frame | regime | n | mean | SD | success |
|---|---:|---|---:|---:|---:|---:|
| idaac-s101 | 598016 | train | 200 | 33.69 | 26.25 | **0.000** |
| | | eval-easy | 200 | 31.58 | 27.93 | 0.000 |
| | | eval-medium | 200 | 11.55 | 8.86 | 0.000 |
| | | eval-hard | 200 | 18.47 | 17.64 | 0.000 |
| ppg-s1 | 600064 | train | 200 | 22.74 | 14.64 | **0.000** |
| | | eval-easy | 200 | 17.98 | 12.23 | 0.000 |
| | | eval-medium | 200 | 11.34 | 8.13 | 0.000 |
| | | eval-hard | 200 | 17.38 | 12.51 | 0.000 |

The frames differ because IDAAC floors a requested budget and PPG ceils it; both are the endpoint.

**Zero successes in 1,600 episodes.** Every number above is shaping reward. That is a fact about
what these policies do, not a scale artefact, and it is the first thing any reader of the table
needs. **Corrected 2026-09-10:** an earlier version of this paragraph said whether 33.69 is above random
was unanswerable. It is answerable. `learning_over_random.py` does report the floor as unknown, and
correctly — it wants a **frame-0 row of the same family** and neither family has one — but the
project also holds a canonical **random-action** floor for Door (C55, `rlvigen_reference.py:87`:
mean 1.842, sd 2.839, max 28.755). Both policies are **6.2×–18.3× that floor** in every regime, and
no training episode of either fell at or below its 95% upper bound. The two controls answer
different questions and only the frame-0 one is missing. See
[`both-endpoint-grids-against-the-random-floor.md`](both-endpoint-grids-against-the-random-floor.md).

## 3. The two defects

**ppg's mode evaluation ran without `no_grad`.** `PpoModel.act` carries `@tu.no_grad`
(`runnable/ppg/phasic_policy_gradient/ppg.py:26`); the harness's mode override replaced `act` with a
direct `forward` call and took the behaviour while leaving the decorator, so `th2np`'s
`tharr.cpu().numpy()` raised `Can't call numpy() on Tensor that requires grad`. Sampled worked and
mode did not, from the same checkpoint in the same process — that asymmetry is the whole diagnosis.
Swept the other two families that implement a mode: idaac's `act` is undecorated and
`eval_grid.py:553` supplies the context itself; ibac_sni's `Agent.get_actions` holds its own. ppg
was the only family whose harness stood in for the vendored method, and the only one broken.

**The run manifest inlined the sampler's whole series.** `records_delivery.jsonl` came to
**1,365,573,627 bytes for 964 rows** because `_run_provenance` — stamped on every row — carried
2,173,638 bytes of per-second `resource_samples`. `collect-host-run.sh` had sized that field at
"roughly 231 KB per row" against a short cell; the size is a function of run duration and nothing
said so. Worse than the bytes: `gpu_compute_processes` comes from `nvidia-smi
--query-compute-apps=pid,...`, which on a **shared** host lists other users' PIDs — nine of them in
that run — and those would have been copied into every published record. Fixed by calling
`summarize_resources`, which this project already had and which emits no PID: 410 bytes, 5,302x
smaller, and the projected bundle drops to ~3 MB.

## 4. The correction: the scene is the unit of variation, not the episode

`first-complete-endpoint-grid-idaac.md` reports idaac's regime SEs as **0.42 and 0.76**, computed
across pooled episodes. For a *between-regime* comparison that is the wrong denominator. Episodes
within a scene share a scene; the ten scenes are what vary. Pairing by scene and taking the SE
across the ten paired differences:

| cell | hard − medium | SE | t | scenes where hard > medium |
|---|---:|---:|---:|---:|
| idaac-s101 | +6.92 | 3.77 | **1.83** | 7/10 |
| ppg-s1 | +6.04 | 0.90 | **6.74** | **10/10** |

At the episode level both look like roughly 5σ. Clustered properly, **idaac alone does not
establish the effect and ppg does.** The pooled row remains the right *descriptive* statistic — it
is what `eval_grid.py:1259` builds and it carries the between-scene variance a mean-of-SDs
discards — but it is not a basis for an SE on a comparison across regimes.

So the finding in the earlier note strengthens and its statistics weaken, at the same time. Its
"1 of 1 checkpoints not rank-ordered" becomes **2 of 2**, and the second one is unambiguous.

## 5. What this says about the design

The recovery question — can these results be completed without retraining? — has a clean answer,
and the reason it does is worth naming.

`sha256(snapshot.pt)` on the host equals the `checkpoint_sha256` carried in that cell's own eval
rows, exactly, for both cells:

    idaac-s101  c68368c1de6e27ded42a542377cd066a55e48e994a7cdee8937646f2fd5f3a5b   x85 rows
    ppg-s1      a328e63e6ffa96f8cde493dfef15e70589d9811bad0cb387a194f9cc4ab0d220   x44 rows

**The checkpoint is the contract between training and evaluation, and the hash proves it holds.**
Any later evaluation of those bytes is commensurable with these rows by construction, which is what
makes `retention-and-eval-depth.md`'s "retain every checkpoint" pay off in practice rather than in
principle.

What the runner does not yet do is treat evaluation as a **separately retryable stage**. ppg spent
3.6 hours training and 572 curve rows, and a nine-second defect in a supplementary pass marked the
whole cell failed. The mechanism for the fix already exists — `OFFLINE_EVAL_SNAPSHOT` selects
`execution_kind = eval_only_validation` — so this is wiring, not invention. That is the same loop
`retention-and-eval-depth.md` §4 names as the one thing never demonstrated at production scale.

**The one measurement that would change what the §2 table means is a frame-0 row per family.** It
costs no training — it is an evaluation of an untrained checkpoint — and without it "33.69" has no
denominator. It is the highest-value remaining eval item, ahead of recovering the mode passes.

## 6. Caveat on the mode passes

The `eval_grid.py` fix moves every family's evaluator revision, so mode rows produced now would sit
on a different closure from the 44 sampled rows already collected. **They must not be pooled.** If
the mode pass is re-run, re-run *both* passes for that cell so the mode-versus-sample comparison
lives inside one closure. The sampled grids stand on the closure they were produced under.

---

## 7. Why the earlier note's table said 400 episodes — a mislabel, not a miscount

Chasing that discrepancy found the defect underneath it, and it is the most consequential thing on
this page.

`normalize_curves.py:186` builds the row's `conventions` block from `CONVENTIONS.get(baseline)`, a
**static per-baseline dict**. So `conventions.eval_policy_mode` always reports the family's *native*
action rule and can never reflect `--policy-mode mode`. The comment at `normalize_curves.py:57-61`
states the requirement exactly right — *"It records the action rule used by the evaluator that
produced the row, not merely whether the original repository shipped a suitable evaluator … the row
must say which happened"* — and the code does the opposite.

Measured on the installed idaac delivery, endpoint rows only:

| `evaluator_scope.eval_policy_mode` | `conventions.eval_policy_mode` | rows |
|---|---|---:|
| `mode` | **`sample`** | 41 |
| `sample` | `sample` | 44 |

**All 85 rows claim `sample`.** Two pooled rows exist per regime, identically labelled, with
different means — eval-medium 11.55 and 14.32, train 33.69 and 34.00. A reader keying on
`conventions` sees 400 episodes per regime where there are 200 of each of two estimands. That is
where the earlier note's 400 came from.

`scripts/audit_row_closure.py:44` reads `conventions.eval_policy_mode` — so the audit whose purpose
is to stop exactly this pooling reads the one field that cannot distinguish the passes.

**Nothing needs re-running.** `evaluator_scope.eval_policy_mode` is correct on every row (41 `mode`,
44 `sample`, matching the counts exactly), so the delivered records are relabellable in place and
the two estimands separate cleanly. The fix is to derive the row's convention from the resolved
scope — `eval_grid.py:1451` already computes the right value — rather than from the static table,
and to make `audit_row_closure.py` refuse a row whose two fields disagree.

Both files are `CODE_MEMBER`s, so this belongs in the same single evaluator-revision bump as the
`no_grad` fix in §3 rather than in a bump of its own.
