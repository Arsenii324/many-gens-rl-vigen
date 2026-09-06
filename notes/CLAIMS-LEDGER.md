# What each row is entitled to claim

Derived from a concern rather than from a file: **the write-up's limitations section will be
assembled from memory unless it is assembled now**, and by then the people who know why a row is
qualified may not be in the room. Every entry here is verified in this tree and cited.

Two rules apply to the whole table:

- **Tier 1 / Tier 2.** The five RL-ViGen-native methods share observation, frame stack, horizon,
  reward and evaluation structure — a genuinely controlled comparison. The twelve-way table does
  not, and must not borrow Tier 1's causal language.
- **A near-floor eval score is not a defect.** RL-ViGen's *own published* DrQ-v2, CURL and DrQ score
  **3.6, 6.6, 14.0** on Door against a **1.82** random floor. Reproducing a published failure is a
  result.

---

## Per baseline

| baseline | must be called | the qualification that must travel with the row |
|---|---|---|
| `drqv2` | DrQ-v2 (RL-ViGen) | Replay capped at 300k in a 600k run unless the host target is applied |
| `drq` | DrQ (RL-ViGen) | lr 1e-4 vs canonical 1e-3; replay cap |
| `curl` | **RL-ViGen's CURL** | DrQ-v2-based, *not* SAC; lr 1e-4 vs 1e-3; **paper and code disagree five ways**; replay cap |
| `svea` | **RL-ViGen's SVEA** | **Uses SODA's `random_overlay`, not SVEA's random convolution** (`svea.py:12,298`). The loss form is SVEA's; the augmentation is not. **Places validation split** (A22); replay cap |
| `sgqn` | **SGQN (RL-ViGen released-code profile)** | Released code differs from its own Door/Lift Table 6: attribution `aux_lr` **1e-4** vs `8e-5`, quantile **.93** vs `.90`, and an ungated critic-consistency literal **.9** vs `.7`. The released profile is the one predeclared configuration—not a silent retune. Replay cap; Places split. | Executed values are RL-ViGen's own: `aux_lr` **1e-4**, `sgqn_quantile` **.93**, `aux_beta` **.99**, consistency **.9 hard-coded**. The old "FIXED to 8.0e-5 / .9" statement describes the retired `rlgen/` path, which production does not run.
| `rad` | RAD (dmc_gb) | `random_shift`, not the paper's crop/translate; n-step 3 vs 1; needs the 100-px render (P6) or it silently *is* SAC |
| `soda` | SODA (dmc_gb) | aux lr follows code not paper; **Places validation split**; longest cell (~45 h) |
| `alda` | ALDA | Recorded faithful; benchmark extrapolated DMControl-GB → robosuite |
| `ppg` | **a continuous-action port of PPG, retimed** | **32× smaller global rollout** (1×8×256 vs 4 MPI×64×256); `n_pi` unrescaled so the auxiliary phase fires ~32× more often in sample terms; **the continuous head has no reference** |
| `idaac` | **IDAAC (DMC continuous-control profile)** [Updated 2026-09-06, A35/A65/Q55: production now runs the authors' own published DMC continuous-control recipe (`num_processes=1`, `num_steps=2048`, `ppo_epoch=10`, `frame_stack=3`, linear LR decay, etc.), not the reduced Procgen-parser adaptation this row previously described — **not** a smaller rollout any more, `num_processes=1` now matches the paper exactly. **Not yet validated by a full-length training run**, see DECISION-SHEET A35's PILOT RESULT/IMPLEMENTED notes.] | `level_seed` is episode-scoped — internally coherent but **an episode is not a Procgen level**, so the invariance construct is target-authored (unchanged by the C2 transition, a separate adaptation) |
| `ibac_sni` | **a continuous-action adaptation of IBAC-SNI** | Impala trunk ported from its own CoinRun branch; **`entropy_coef=0` is an empirical workaround whose cause is not isolated**; 16× smaller rollout; competence on Door not yet established | **Every ibac_sni run before 2026-09-05 used `beta=1.0`** — the launcher passed no `--beta`, so the branch default applied while FAITHFULNESS recorded 1e-4; the VIB penalty was 10^4x CoinRun's. Corrected, but **no competence evidence yet exists for the corrected configuration**. Also still not CoinRun: single VIB sample against `--nr-samples 12`, and a 64-d latent against 256-d, so the honest name is **an authored hybrid of the authors' PyTorch and CoinRun implementations**
| `ctrl` | CTRL (repaired) | Two lines restored that were commented out upstream — **without them `ctrl_public @ 7a118c8` cannot run its own algorithm**; 4× smaller rollout; MYOW draws from the *nearest* neighbouring cluster repeatedly (upstream's own quirk); **C97 records a declared paper-vs-code conflict, with the released-code profile as the operational default and no paper profile scheduled in the one-run campaign** | Online eval advances the JAX PRNG that the next `update_ppo`/`update_cluster` consumes, so the training trajectory is a function of the eval code path; **this is upstream's own structure** (`ctrl_public/train_ppo.py:193,202`) and is deliberately unpatched, so the isolation guard covers the placement stream only **Its evaluated return was in normalized units until 2026-09-05** (the common evaluator inherited `normalize_rewards=True` and summed the outermost VecNormalize reward); any ctrl evaluation number predating that fix is void, not merely incomparable

## Claims the table cannot support, whatever the numbers say

- **"Algorithm A generalizes better than B."** Method identity is perfectly confounded with frame
  stack (3 vs 1), resolution (84 / 100→84 / 64), γ (0.99 vs 0.999), time-limit treatment (3
  bootstrap / 9 terminal), reward normalization, action distribution and rollout size. More seeds
  cannot remove collinearity.
- **"These are the published algorithms."** Five are RL-ViGen's implementations; four are
  continuous-action ports of discrete methods, two of which have no reference implementation for the
  continuous head.
- **"n = 600 episodes."** The outer replicate is the training seed: **n = 3**.
- **Any cross-run numeric comparison straddling 05 Sep 01:25** — see
  [`RESULTS-VALIDITY.md`](RESULTS-VALIDITY.md).

## What it *can* support

- **Within-method, across-regime retention** — the identified clean contrast, and the project's
  actual question. [C81](../docs/CONSTRUCTION.md#c81): the random-policy floor is byte-identical
  across train and eval-easy over 200/200 episodes, so the regimes differ *only* at the observation.
- **Tier 1 comparison among the RL-ViGen five**, with the replay cap and Places split declared.
- **"These twelve adapted implementations, at their own design points, on Door at a common 600k
  budget"** — the honest twelve-way estimand.

## Correction 2026-09-05, RETRACTED THE SAME DAY — the replay cap IS a real deviation

A correction was published here claiming the cap evicts only 0.40%, derived from
`cfgs/config.yaml`'s `action_repeat: 2`. **That was wrong and is withdrawn.**
`runnable/_launch/rlvigen.sh:78` passes **`action_repeat=1`** — line 61 calls it "this project's
declared protocol" — so a 600,000-frame budget is 600,000 agent steps, ~600,000 transitions are
stored against a 300,000 cap, and the cap **does** discard roughly half the experience.

The qualification on all five RL-ViGen rows therefore **stands as originally written**. See
[`CORRECTIONS.md`](CORRECTIONS.md) #35 and #36 for the error and its retraction.

## Added 2026-09-05 — what a PER-SCENE number may claim

`placement_condition_seed` includes `scene_id`, so **scene 0 episode 3 and scene 1 episode 3 run
different physical placements.** A per-scene comparison therefore carries scene variation *and*
placement variation together.

- **A per-scene row may say**: "under scene *s*, with placements drawn for that scene, the policy
  scored X." That is a description of a cell.
- **A per-scene row may NOT say**: "scene *s* is harder than scene *t*", or attribute a difference
  between scenes to the scene. Those are unpaired comparisons and the placement draw is a live
  alternative explanation.
- **Unaffected**: the across-regime contrast at a fixed scene. The seed excludes the regime, so
  train and eval-* share placements exactly — verified in `bt1baht74a35e6uq582c`'s recorded
  `placement_condition_seeds`. **The headline retention contrast is properly paired.**

See `DECISION-SHEET` A21 for the fork (keep independent placements for coverage, drop `scene_id` for
paired scene contrasts, or add a small paired block for both).

## Upgraded 2026-09-05 — cross-regime pairing is now PHYSICALLY proven, not derived

The retention contrast assumes episode *i* under `train` and under `eval-*` runs the same physical
Door placement. That was argued from the seed formula and then from recorded condition seeds. It is
now shown from the **realized physics**.

`scripts/audit_pairing_evidence.py` compares P20's `initial_placement` — the actual door
`body_pos` and `body_quat` after reset — episode-for-episode across regimes:

    5 cross-regime comparisons, 0 not paired
    ibac_sni, idaac (two revisions), ppg, rad -- all physically PAIRED across train and eval-easy

**Why this needed a separate artifact.** `placement_witnesses` are **observation hashes**, and
external review 10 is right that an image hash cannot demonstrate physical pairing: the same
physical placement under two visual regimes *should* hash differently. Counting witnesses proves
nothing about pairing, and the audit now flags identical witnesses across regimes as a red flag —
that would mean the regime is not reaching the renderer.

**So a retention row may now say** that the compared regimes ran the same physical conditions, and
cite the audit. It still may **not** say that across *scenes* (A21).


## A22 — the Places365 split, stated once for all three baselines that use it

`svea`, `sgqn` and `soda` all draw overlay images from the Places365 **validation** split, because
`datasphere/native/configure_places365_val.py:34-35` rewrites upstream's `use_val=False` to `True`.

For those three the augmentation distribution *is* the mechanism, so this is a learning-affecting
deviation, not a platform one. All three use the SAME split, so the cross-baseline comparison this
project actually reports is unaffected; what it forecloses is any claim of parity with **published**
SODA/SVEA/SGQN numbers, which this ledger already forbids on other grounds.

Recorded here because the qualification existed on two of the three rows and not on `svea`'s, and
because it had no decision row anywhere until A22 — the failure mode being that a per-row
qualification is read as a detail of that row rather than as a shared property of a group.

## A35/A36 pilot arms, 2026-09-06 — the running "C" arms are NOT the source-faithful continuous-control recipe

`idaac-pilot-c` (`bt1djeamji7gilgnndft`) and `ppg-pilot-c` (`bt19878rgm9qnqrhopoj`) are running at
**one-frame observations**, the same as `idaac-p`/`ppg-p`. This is a known, deliberate gap, not an
oversight discovered after the fact — recorded here so a future write-up cannot mistake either for
the authors' actual continuous-control design point.

**The frame-stack concern itself is not new.** Review 2 named the 8/4 observability split; reviews
8 and 10–15 separately cite the IDAAC authors' own DMC continuous-control setup (3 stacked frames,
for both IDAAC and their PPG baseline) as the reference. This session's own primary-source check
(`ext/idaac/raileanu21a-supp.pdf` §E) confirms it directly rather than through a review summary.

**What travels with any result from these two jobs, if quoted before a C2 arm exists:**
- `idaac-pilot-c` tests `order_loss_coef 0.001→0.1` (the headline finding) and the other DECISION-
  SHEET A35 recipe changes (`num_processes`, `num_steps`, `num_mini_batch`, `gamma`, `entropy_coef`,
  `lr`, `value_freq`, `adv_loss_coef`) at frame_stack=1 and `ppo_epoch=3` — **not** the primary
  source's `ppo_epoch=10`, which A35 resolved only after this arm was already running.
- `ppg-pilot-c` tests `gamma`/`lr`/`nminibatch`/`entcoef` at frame_stack=1 — its 3-frame wrapper/CNN
  path is not yet implemented or verified at all (A36).
- Neither is "IDAAC/PPG's published continuous-control configuration." Call them what A35/A36 call
  them: a bounded, partial recipe pilot (informally, the "C1" arm), with a full-recipe **"C2"** arm
  (frame_stack=3, `ppo_epoch=10` for IDAAC) still to be built, in the final frozen wave, not before
  (Q47's own rule: no reactive resubmission of an already-running job).

**All four jobs landed SUCCESS 2026-09-06; results read directly from `records.jsonl`, endpoint
scope, 245760 frames, n=1 seed, 5 episodes/regime.** Numbers, not a verdict — see caveats below.

| job | regime | return (mean±sd) | success_rate |
|---|---|---:|---:|
| idaac-p (`bt1opt8j8ehdhpdsfnv0`) | train | 10.39 ± 10.22 | 0.0 |
| idaac-p | eval-easy | 13.26 ± 11.97 | 0.0 |
| idaac-c1 (`bt1djeamji7gilgnndft`) | train | 59.57 ± 31.73 | 0.0 |
| idaac-c1 | eval-easy | 87.71 ± 35.39 | 0.0 |
| ppg-p (`bt1439jqhahgfbm2l9kb`) | train | 33.63 ± 42.06 | 0.2 |
| ppg-p | eval-easy | 16.21 ± 5.96 | 0.0 |
| ppg-c (`bt19878rgm9qnqrhopoj`) | train | 47.03 ± 21.93 | 0.0 |
| ppg-c | eval-easy | 30.26 ± 22.99 | 0.0 |

**Reading against each pilot's own pre-registered decision rule (A35/A36: "if the C arm reaches
competence at least as well as P, make it primary; if it fails outright, P stays primary and C's
result is reported, not discarded")**: `MIN_DENOM_SUCCESS = 0.25`
(`scripts/regime_retention_report.py`). **Neither arm of either pilot clears it** — idaac-p and
idaac-c1 both sit at 0.0 in both regimes; ppg-p's 0.2 (train) is closer but still under the bar,
and ppg-c is 0.0 everywhere. Read plainly, this is not "C failed and P held" — **neither recipe
demonstrated Door competence at this budget**, which the decision rule did not anticipate as an
outcome for both arms at once.

**Do not read the raw-return gap as a fidelity verdict.** idaac-c1's returns are 6-9x idaac-p's
despite identical (zero) success rates — a real, directional signal that the C1 hyperparameters
(mainly `order_loss_coef 0.1`, `value_freq 32`, `gamma .99`, `lr 3e-4`) move the reward-shaped
return substantially, but Door's binary success criterion is a stricter, different quantity
(`docs/CONSTRUCTION.md` — the dense reward has a non-zero floor, see A18's own note on why
retention/return are not interchangeable). ppg's raw-return gap (47.0 vs 33.6 train) runs the same
direction as idaac's despite ppg-p having the only nonzero success rate in the whole table — a
reminder that "higher shaped return" and "reaches the success gate" can disagree even within one
comparison, not just across families.

**What this pilot round actually settles, and what it does not**:
- Settled: none of these four cells reaches production-grade competence at 245760 frames (well
  under a third of the eventual 600k budget) — consistent with a short pilot simply being too
  short to observe competence, independent of which recipe is better, not evidence either
  algorithm is broken.
- Not settled: whether idaac's or ppg's `C` recipe out-competes `P` at production length/seed
  count. n=1, a budget under half of production length, and a competence readout of exactly 0 or
  1 successes out of 5 episodes is the small-n regime A23 already named as too thin to trust
  (a single flipped episode moves ppg-p from "clears the bar" to "at the bar" and back).
- Not settled, and explicitly deferred per Q47: the C1 vs C2 question for idaac (frame_stack=1 vs
  3, ppo_epoch 3 vs 10) — this round says nothing about C2, which has not been built.
- **My reading, offered not decided**: this result does not by itself justify extending either
  pilot's budget or building C2 early — it's consistent with "too short to tell," which is exactly
  what a longer, later, single frozen-tree measurement is for. Record and move on rather than
  chase an inconclusive n=1 pilot with more pilots.
