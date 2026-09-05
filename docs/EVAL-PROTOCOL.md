Written 2026-09-03.

# The evaluation protocol — and a proposed decision for P-C76 / R3

**Status: PROPOSED. Nothing here is settled.** Every item below is a decision I have made *as if*
it were mine, so that it can be argued with concretely. The register keeps them OPEN until the
owner records otherwise; a default is not a decision.

---

## THE PROPOSAL IN ONE PAGE — written 2026-09-04 at the owner's request

Everything below this section is the reasoning. This is the shape to approve or amend. **Bold**
marks the four points the owner has already decided; the rest are defaults awaiting a yes.

**What is measured.** Each baseline's *saved policy*, driven through **its own action path** by our
offline harness (`scripts/eval_grid.py`), in the container on CUDA. The platform is not a
preference — a container-trained policy read 12-14x low when evaluated locally
([C95](CONSTRUCTION.md#c95)).

| | |
|---|---|
| **Metrics reported** | **Full matrix:** `R_train`, `R_OOD`, `Δ = R_OOD − R_train`, success rate, retention and floor-adjusted retention, per regime and scene. Success and absolute returns lead; retention is secondary and only interpreted for competent policies. |
| **Checkpoints** | **Endpoint is the headline; trajectory is descriptive; no selected-best column.** All seven families write stamped intermediate checkpoints on a common **50k** grid, so any future trajectory analysis remains constructible without selecting on the reported holdout. |
| Regimes | `train`, `eval-easy`, `eval-medium`, `eval-hard`. `train` is the retention denominator and is scene 0, verified to be what the training env actually is (`robo_config.yaml` defaults `mode: train`, `scene_id: 0`). |
| Scenes | Ten certified, per regime, **pending P-C76** — the one UNITS split and the only thing keeping R3 NOT MET. Our harness can sweep ten for all twelve at **zero clone deviations**, which is why option (1) is cheaper than the branch point assumes. |
| Episodes | **3 per scene at each 50k trajectory stamp; 20 per scene at the endpoint.** Per-scene and per-episode rows are retained, never only the pooled mean. |
| Eval seed | One fixed constant, expanded into a per-(scene, episode) condition seed and shared across every baseline and training seed. The seed is applied immediately before each measured reset, so checkpoints are compared on identical door-placement conditions despite family-specific construction (a paired comparison; [C69](CONSTRUCTION.md#c69)). |
| **Training seeds** | **Fixed 3 for every reported row.** A one-seed pilot may establish that a method runs or sits at floor, but never licenses a ranking or substitutes for a missing production seed. |
| Budget | **6e5 Door frames.** 5e5 likely suffices internally (`drqv2` reached success 1.00 at 75k), but 6e5 is RL-ViGen's published Door budget, gives PPG nine auxiliary phases rather than a token one, and makes seed 1 of `drqv2` the [C48](CONSTRUCTION.md#c48) external anchor at no extra training cost. |
| **Compute** | **1-2 V100, not the grant.** The grant arithmetic in `plan_production.py` is therefore a bound on *that* route, not on this one; what carries over is the per-cell hours and the archive sizes. |
| Storage | Retain every production checkpoint on the production host; export episode records separately. C95 still requires evaluation in the matched renderer/image, not on this laptop. |

### Current operational defaults — 2026-09-05, awaiting owner settlement

These are the defaults the project implements and validates now; `OWNER` means formal settlement is
still open, not that an arbitrary alternative may be substituted. They supersede earlier adaptive
seed and 100k-cadence passages below, which remain only as dated reasoning.

- **Fixed 3 for every reported row.** No outcome-dependent allocation; report an absent/failed cell
  rather than redistributing its seeds.
- **50k stamp grid**, three episodes per intermediate scene and twenty at the endpoint; retain all
  checkpoints on the production host and every episode record.
- **Endpoint is the headline; trajectory is descriptive; no selected-best column.**
- Report the full metric matrix above. The provisional headline contrast is appearance generalisation
  with scene held fixed (P-C76 estimand B); all other estimands remain reported, not hidden.

**The limitation to state in the write-up, not bury.** RL-ViGen **equalises** the observation
across its own five — `robo_config.yaml` drives `camera_heights`/`camera_widths` from one value and
all five read 84 — which is the standard benchmark move, since resolution is a property of the
environment rather than of the algorithm. **We do not equalise across the twelve**: the seven
imported baselines keep their own native sizes (Procgen's 64, dmc_gb's 100→84 crop) because each
architecture derives its width from its input, so equalising would mean authoring an encoder change
in seven clones — which the clone-era null forbids. **So this table compares algorithms at their
own design points, not at a common observation.** That is right for a porting exercise and is *not*
the same claim as a benchmark result. **The size of the confound is unmeasured and is not cheap to
measure**: every one of the twelve hardcodes its input size — `drqv2`'s encoder fixes
`repr_dim = 32 * 35 * 35`, which is what 84 yields and 64 does not — so even running one baseline at
a second resolution needs an encoder edit. Equalising across the twelve would need seven.

**What is deliberately excluded**, so it is a decision rather than a gap: the **camera axis**
(`cam-easy`/`cam-hard`) — viewpoint rather than appearance generalisation, unreachable from our
harness without a patch, and 1.5x the grid. See §2.

**What is not yet earned.** All twelve baselines have an **undischarged shared-evaluator burden**
under the current evaluator identity (`scripts/audit_shared_evaluator.py`). Earlier paired results
for `drqv2` and `idaac` remain useful historical measurements, but [C96](CONSTRUCTION.md#c96)
showed that their global provenance field did not certify the action-path code that produced them.
The live gate correctly begins again at zero of seven families until each family is rerun with a
reviewed runtime-import manifest. That is a statement about the instrument, not about the
baselines, and it is the honest caveat on every pre-production number.

---

## 0. The fact that determines the whole design

`scripts/audit_eval_cadence.py`, run today:

| | evals per run | regimes | cadence unit |
|---|---|---|---|
| `drqv2 svea sgqn curl drq` | 5 | 2 | frames |
| `rad soda` | 4 | 2 | steps |
| `alda` | 6 | 3 | steps |
| `idaac` | 2 | 1 | **updates** |
| `ctrl` | 0 | 2 | **continuous, not episodic** |
| `ibac_sni`, `ppg` | **0** | 0 | none |

Its own conclusion: *"three of twelve run no periodic training-time evaluation at all … so 'metrics
on the same axes' is **not reachable from training logs by construction**. It is reachable offline,
from checkpoints, which is why the evaluator is a separate harness."*

**So the choice between "save checkpoints" and "save eval results" is not a trade-off.** Training
logs cannot deliver same-axes metrics for a quarter of the set at any cadence, in any format, no
matter how much logging is added. Adding tensorboard to `ppg`/`ibac_sni`/`ctrl` would produce more
numbers on *more* different axes, not fewer.

**Decision: checkpoints are the primary artefact. Evaluation is offline, from them.**

Three further reasons, all from this project's own history:

1. **The evaluation procedure is not settled yet** — this document is the attempt to settle it.
   Committing to eval outputs now would freeze the very thing under discussion.
2. **[C95](CONSTRUCTION.md#c95) is the proof case.** An entire evaluation methodology was
   invalidated after the fact (wrong renderer). Because checkpoints existed, everything was
   re-measured for ~60 RUB. Had we kept only eval results, the runs would have been lost.
3. **Re-evaluation is cheap and re-training is not**: a four-regime ten-scene grid over 400
   episodes cost ~168 RUB; a production cell costs hours of GPU.

---

## 1. Proposed decision for P-C76 / R3 — and why it is cheaper than the branch point assumes

`RESEARCH-FRAME.md` frames option (1) as *"give the seven evaluators a scene sweep — costs a
deviation in each clone and re-opens the faithfulness ledger for seven baselines"*. **That cost is
an artefact of assuming evaluation happens inside the clones.**

Under §0 it does not. Evaluation runs in **our** offline harness (`scripts/eval_grid.py` +
`OFFLINE_EVAL`), which loads a checkpoint and drives the baseline's *own* action path. The scene
set is then a parameter of our harness, not of anyone's `train.py`.

**Proposal: a common evaluation grid for all twelve — same scenes, same seeds, same episode count,
same regimes — implemented entirely in our evaluator, with zero clone deviations.**

What this costs is real but different: `eval_grid.py` now has seven family-specific paths. That is
**our** code, so it adds nothing to `deviations.py` and re-opens no faithfulness ledger. `ctrl`'s
JAX path is the largest one, because its checkpoint is a flax msgpack and its policy is JAX.

**What it does not equalise, on purpose.** The *estimator* stays each baseline's own: our harness
calls their `act`, so `idaac`/`ibac_sni`/`ppg`/`ctrl` keep sampling and the other eight keep taking a mode
(`COMPARABILITY_CONTRACT` §5c). Equalising that would replace their policies with ours. It is
declared, not removed.

**The burden of proof is OURS, per baseline, and it is mostly undischarged.** A shared evaluator
distinct from each method's own evaluator is a new instrument, and for every baseline we must show
it measures what that baseline's own evaluator measures. `scripts/audit_shared_evaluator.py` tracks
this and, **as corrected on 2026-09-05, reports ZERO discharged under the current evaluator
revision** -- see production_gates. The two results below stand as history, not as standing
discharges: both were measured before per-episode placement seeding, deterministic kernels and
strict regime verification, and before this session's ctrl reward-units and ppg collection-order
fixes. The former reading was **2 of 12**: `drqv2` PASS (131.57 against 135.71) and
`idaac` CONSISTENT; ten remain UNRECONCILED.

Two rules it encodes, both learned here rather than assumed:

- **Ours-lower is SUSPECT, not neutral.** If our number is below the baseline's own, "their
  evaluator is generous" and "our harness handicaps their policy" predict the same observation.
  C95 was exactly that shape, at 12–14x, with nothing crashing. `idaac`'s 1.663 against 3.01 sits
  in that direction.
- **A comparison at the floor is not evidence.** Two numbers straddling 1.842 agree about nothing —
  both describe a policy doing nothing, which any harness reproduces.

**The harness running is not the discharge, and neither is the ratio.** Six families exist and
all six produce plausible magnitudes; that is a statement about the code. Agreement to 3% on
one checkpoint is corroboration, not proof — it shows two instruments produced similar numbers,
not that they measure the same thing, and it lets an undeclared difference hide behind "close
enough". **The actual obligation is structural and lives in [`EVALUATOR-DELTA.md`](EVALUATOR-DELTA.md)**:
every way our harness differs from each baseline's own evaluator, declared and classified. It
already names three material deltas that were nowhere written down — our determinism setting
(ours alone, not upstream), an RNG offset introduced by the rlvigen verification probe, and a
different episode-accounting scheme for `idaac` and `ibac_sni`.

**What would show this wrong**: if driving a baseline's `act` from outside its own trainer changes
its behaviour — the C95 failure mode one level in. Guard: our harness's number must reproduce the
baseline's own evaluator on the same checkpoint.

**Held for the natives; INCONCLUSIVE for the first non-native tried, and the reason is instructive.**
For `drqv2` it holds — 131.57 against a logged 135.71. For `idaac` (`bt1dbmtc04sg5nhc18r6`), on its
own 9,216-frame checkpoint: **our harness 1.663, its own evaluator 3.01** on eval-easy. That is
~1.8x, not C95's 12–14x, so it is *not* evidence of the failure mode — but it is not evidence of
agreement either, because **both numbers straddle the 1.842 random floor** and `idaac` samples. At
ten episodes of a stochastic policy at chance, this comparison has no power.

**So the guard cannot be completed with any checkpoint pre-production currently has**: every
non-native sits at or near the floor at 10k. It needs a *competent* policy, which needs a longer run
than pre-production has done. **This is the competence gate of §3 arriving from the other side** —
the same floor that makes a retention ratio undefined makes a fidelity check uninformative. Until a
competent non-native checkpoint exists, §1's proposal rests on the natives' evidence plus a
mechanism argument, and that limitation is part of the proposal rather than a footnote to it.

---

## 2. The grid

Per baseline, per seed, per retained checkpoint:

- **regimes**: `train`, `eval-easy`, `eval-medium`, `eval-hard` — all four. `train` is the
  retention denominator and is *not* a randomised distribution ([C51](CONSTRUCTION.md#c51)).

  > **The camera axis is EXCLUDED, and as of 2026-09-04 that is a decision rather than an
  > oversight.** `robosuitevgb/utils.py` branches on **six** regimes, not four: `cam-easy` and
  > `cam-hard` set `randomize_camera=True` and override position, rotation and fov. A register row
  > from 2026-08-18 recorded that this project measures none of it and nothing followed.
  >
  > **DEFAULT SET, awaiting approval: leave it out of this deliverable.** Three reasons, in order
  > of weight. (1) It is a **different kind of generalisation** — viewpoint, not appearance — and
  > the contract's retention question is posed over the appearance regimes; mixing a viewpoint
  > result into that column would answer a question nobody asked. (2) It is **not reachable from
  > our harness as written**: the branch loads its settings via
  > `open('../../../../envs/robosuiteVGB/cfg/setting/robo_setting.yaml')`, a cwd-relative path four
  > levels up that resolves only from upstream's own launch directory, so an offline evaluator
  > running anywhere else raises `FileNotFoundError` before the env is built. (3) It would make the
  > grid **1.5x larger** (six regimes against four) at a budget already over the grant.
  >
  > **What it would cost if wanted**: one patch making that path absolute — PLATFORM-class, since
  > it changes where a file is found and not what is measured — plus 50% more evaluation. Recorded
  > so the exclusion can be reversed by decision rather than rediscovered as a gap.
- **scenes**: all ten certified, per regime. Per-scene rows retained, never only the aggregate —
  today's grid showed 392.9 on scene 0 against 0.7 on scene 3, which an aggregate erases.
- **episodes**: 10 per (regime, scene) cell. 4 × 10 × 10 = 400 episodes per checkpoint ≈ 1h ≈ 168 RUB.
- **seeds**: the *evaluation* seed is **fixed and shared** across every baseline and every training
  seed; the *training* seed is the §3b #4 decision. These are different axes and the record names
  both.

  **Found by the blind-spot pass, 2026-09-03, and it was silent.** `OFFLINE_EVAL` passed the same
  variable to `--seed` and `--episode-seed`. Via [C69](CONSTRUCTION.md#c69) the evaluation seed
  seeds the *global numpy RNG*, which is what places the door on every reset — so a three-seed
  production set would have evaluated each seed's checkpoint on a **different set of door
  placements**, and the across-seed spread would have mixed the training-seed effect with an
  evaluation-seed effect having nothing to do with the algorithm. `OFFLINE_EVAL_EPISODE_SEED` is now
  separate and defaults to a constant, so "same scene set, same seed set" holds **by construction
  rather than by remembering to pass a flag**.
- **platform**: the machine that trained the policy. Non-negotiable, [C95](CONSTRUCTION.md#c95).

**Emit per-episode returns, not summaries.** `eval_grid.py` already carries `native.returns` per
cell. This is what makes the owner's "all metrics, select later" possible: median, IQM, bootstrap
CI, success-conditioned return and any competence gate are all post-processing over per-episode
data. **A summary statistic chosen at write time cannot be un-chosen.**

---

## 3. The competence gate (§3b #15)

*A method that never learns has gap ≈ 0, which reads as perfect generalization.* Today: six of
twelve sat at or below the then-current 1.82 random floor ([C55](CONSTRUCTION.md#c55)) with
success 0.00. (That observation stands as recorded; the floor has since been re-measured
under the current paired evaluator at **1.842**, which does not change the reading.)

**Proposal**: a baseline receives a retention *ratio* only if its train-regime denominator clears
the floor by a stated margin **and** its train-regime success is non-zero. Below that it is
reported as **"did not reach competence"** — not as a number, and never as a ratio. The floor and
the margin travel with every table.

This is a reporting rule, not a filter: the run and its returns are still published.

---

## 4. Checkpoint cadence (§3b #3)

The owner's reading — *progress is algorithm-dependent, so maybe each is separate* — is the right
one, and there is a hard constraint underneath it:
[C60](CONSTRUCTION.md#c60) — the RL-ViGen five can only stamp at **multiples of 50k plus the
endpoint**. `RLVIGEN_PRESERVE_SNAPSHOTS` filters that grid; it cannot add to it.

**Proposal**: retain the 50k grid plus the endpoint for every family that can, and evaluate the
**endpoint** as the headline while publishing the curve. This makes "checkpoint selection" a
post-processing choice over a retained curve rather than a decision baked into what was kept —
consistent with §2's principle.

> ### Measured 2026-09-04 — "every family that can" turns out to be ONE, and the curve is not currently producible
>
> The sentence above was written from C60, which is about the RL-ViGen five. Read across all
> twelve — from `families.json` and confirmed against four returned archives rather than the
> descriptor alone — the per-family save cadence is:
>
> **Corrected 2026-09-04, second pass.** The first version of this table asked the wrong question —
> *does the family have a `save_every`* — and got four families wrong. The question that decides
> whether a curve exists is **whether each stamp gets its own filename or overwrites one path**:
>
> | family | stamps | mechanism |
> |---|---|---|
> | `rlvigen` | **distinct** | saves at hardcoded 50k boundaries and overwrites; patch **P18** preserves copies, `RLVIGEN_PRESERVE_SNAPSHOTS` filters which |
> | `dmc_gb` | **distinct** | `model/{frames}.pt`, one file per stamp. `--save_freq` is passed by `families.json`'s `options`, not the launcher, and has always been live — now 50000, was 100000 |
> | `alda` | **distinct** | `save_checkpoint` writes `sac_{env}_step_{env_steps}.pt` (`alda_trainer.py:688`), so its `save_every: 50000` yields a real curve |
> | `ibac_sni` | **distinct** | *was* one path (`--save-interval 1` saved every update into a fixed, overwritten `model.pt`); `--save_interval_frames` now writes `model_<frames>.pt` beside it |
> | `idaac` | **distinct** | *was* guarded by `if j == num_updates - 1` (terminal by upstream design); `--save_interval_frames` now stamps on frame-boundary crossings |
> | `ppg` | **distinct** | upstream already implemented `save_mode="all"` and its own `train.py` hardcoded `"last"`; exposing `--save_mode`/`--ic_per_save` was enough. Names by **save index** (`model000.jd` …), not by frame |
> | `ctrl` | **distinct** | `checkpoint_interval` was *declared at `train_ppo.py:98` and never read*; wiring it writes `checkpoint_<frames>.msgpack` |
>
> **Updated 2026-09-04, third pass — all twelve can now produce a checkpoint curve, and it is
> validated on hardware.** The four "one path" rows above were closed by one minimal intervention
> each, every one changing what is *retained* and never what is learned. Confirmed by running them:
> `bt1h3l1rl7v7n4bve0au` returned **5** stamps for `ibac_sni`, **4** for `idaac` and **6** for
> `ppg`; `bt1791fdh5uctgr1ckhk` returned `ctrl`'s. **So the intersection across all twelve is no
> longer the endpoint alone** — the cross-baseline offline curve is now buildable, which is what
> makes "endpoint" and "best over the trajectory" both reconstructible from retained data, as the
> owner asked. The endpoint remains the *reported* number (§4's conclusion); what changed is that
> it is now a choice rather than the only option.
>
> **Superseded by the third-pass result above.** The earlier text correctly identified endpoint-only
> retention as the conservative interim default, but it predates the four retention-only fixes and
> their hardware validation. It is retained in the dated register as an audit trail, not as the
> current state of the production tree. The live default remains endpoint headline plus retained
> intermediate curve; checkpoint selection is still not allowed to use the reported held-out metric.

**Operational default, awaiting settlement**: endpoint headline, trajectory descriptive, no
selected-best column. Selecting the best checkpoint *by the metric being reported* is a
garden-of-forking-paths hazard; a future selected-best analysis needs a separately reserved
criterion and equal candidate opportunity, neither of which the current protocol claims.

---

## 4b. Seeds, and what a given seed count licenses (§3b #4)

**Operational default 2026-09-05, awaiting approval: Fixed 3 for every reported row.** The former
adaptive proposal is withdrawn: one seed everywhere followed by outcome-dependent concentration
lets early noise decide which methods receive replication. A floor-level method is still a reported
row, not a reason to remove its predeclared seeds.

**What each seed count licenses, stated so a later table cannot quietly exceed it:**

| seeds | admissible claims |
|---|---|
| **1** | *existence* — "this baseline reaches success 1.00 in the training regime at 100k"; and *floor* — "this baseline is indistinguishable from random in eval-easy". Both are about one run and neither orders two baselines. |
| **2** | the above, plus "the effect reproduced", which is a statement about reproducibility, not about size. |
| **3+** | a ranking claim, and only between baselines that each have 3+, at the resolution [C18](CONSTRUCTION.md#c18) allows — **CORRECTED 2026-09-05 (A28): ~53% at the operational n=3, ~35% at five.** The ~31%-at-five figure this row previously carried used the normal approximation, which understates the requirement at small n; the t-corrected multiplier agrees with it only at n≈50. **Corrected once more, review 14 section 24**: calling these figures "floors" overclaimed what a single same-seed pair supports -- the adjustment direction (genuine seed variance adds to backend-only noise) is structurally sound, but the CV itself is a one-pair point estimate with real sampling uncertainty of its own. Treat ~53%/~35% as illustrative under the current thin evidence, not as guaranteed bounds. Full derivation: `notes/FINDING-resolving-power-at-n3.md`. |

**The two results in hand are both single-seed and both stay inside row 1**: `drqv2`'s 0.30%
retention is an existence-plus-floor claim, and `ibac_sni`'s entropy collapse is an existence claim
about one run. Neither orders anything, and the write-ups say so.

One-seed runs remain legitimate plumbing or diagnostic pilots, but are not production rows and do
not change the fixed seed allocation for any reported baseline.

---

## 5. On-policy vs off-policy on frames seen

The owner's instruction: report it, let the audience see. Agreed, and the record already supports
it — `frames` is the executed count, and today's pass showed 9216 / 10000 / 10112 / 10240 for a
requested 10,000, because each family floors to its own rollout quantum. The table prints what ran.

No harmonisation. A phasic or on-policy method spending its budget differently is part of what is
being compared.

**A related but distinct axis, added 2026-09-05 (A29):** this section is about the
executed FRAME COUNT rounding to each family's rollout quantum. A separate question -- how many
gradient updates each family takes PER frame of that budget -- is not harmonised either, and is
now a declared comparability-seam axis (`updates per env frame`,
`scripts/audit_comparability_seam.py`) rather than an implicit assumption: idaac and ppg run their
regular-phase updates 4x-32x denser than their Procgen source because a single V100 cannot match
Procgen's parallelism (`notes/FINDING-on-policy-update-density.md`). Same "report it, don't
harmonise" stance as this section takes for frame-count rounding; stated separately because it is a
different quantity.

---

## 6. Storage, and the local-space constraint

At 6e5 with the 50k grid: ~12 stamps × 12 baselines × N seeds. A `drqv2` snapshot is ~104 MB, so
one seed is ~15 GB and three seeds ~45 GB. **This lives on the production machine, not here.**

*(Local free space was ~12 GB when this was written and is **73.1 GB** as of 2026-09-04 — the
owner cleared space. The rule is unchanged, because §6a's reason for it is C95 rather than
capacity, but the number is corrected so nothing else is argued from the old one.)*

**Proposal**: checkpoints stay remote; only *records* (JSONL, kilobytes) come back by default. A
checkpoint is fetched locally only for a specific investigation, and deleted after.

### 6a. The intermediate curve is evaluated in the container — and it is not free

*(2026-09-04. The numbers above were re-measured from real `retained.json` files rather than
estimated: `drqv2` 104.1 MB, `alda` 103.9, `ctrl` 39.8, `ibac_sni` 27.6, `idaac` and `ppg` 5.0.)*

**[C95](CONSTRUCTION.md#c95) removes the choice about *where* the intermediate grid is evaluated**:
a container-trained checkpoint read on this laptop gives a different number, because the renderer
differs. Weights that cannot be validly evaluated where they land are worth nothing there, so the
grid is evaluated in the container or not at all.

> **Correction, 2026-09-04, hours after this section was written.** It originally argued from a
> second fact — that 13 checkpoints per cell × 12 baselines × 3 seeds is **35.5 GB** against
> "roughly 30 GB free", and so *does not fit*. The owner then cleared space and the real figure is
> **73.1 GB**: it fits. That leg is withdrawn. The conclusion is unchanged because it never rested
> on it, but the arithmetic is still worth keeping in view — 35.5 GB is about half the free disk,
> spent on data with no valid local use. `plan_production.checkpoint_storage_gb` computes it, from
> checkpoint sizes measured on real jobs rather than estimated.

So the weights are evaluated where they were produced and only records travel:
`run_probe.sh::run_curve_eval` walks the retained stamps after `retain`, runs `eval_grid.py` on
each, and `CURVE_EVAL_DISCARD_WEIGHTS=1` deletes each intermediate once evaluated — never the
terminal `snapshot.pt`. It is **opt-in**, so no ordinary probe starts paying for it.

**What it costs, which is the part that needs a decision.** Derived from the same measured
throughputs the cost model uses, at 6e5 × 3 seeds:

| stamp grid | episodes | stamps | job-hours | RUB | vs the ~525 h of training |
|---|---|---|---|---|---|
| 50k | 20 | 13 | 260.6 | 43,891 | +51% |
| 50k | 10 | 13 | 130.3 | 21,946 | +25% |
| 50k | 5 | 13 | 65.1 | 10,973 | +13% |
| 100k | 5 | 7 | 35.1 | 5,909 | +7% — historical lower-cost option |
| 200k | 5 | 4 | 20.0 | 3,376 | +4% |

**The table above is historical and its episode counts are superseded — CORRECTED 2026-09-05,
external review 14 section 14, which found exactly this kind of contradiction survives a
"superseded" label when the very next sentence reads as current.** A20 decided **three** episodes
per intermediate cell, not five; `families.json`'s `curve_eval_episodes: 3` is what every family
actually runs (`test_production_defaults.py` pins this). The table's cost arithmetic used 5/10/20
because it was written before A20; it is kept for the cost *shape* (more episodes costs
proportionally more), not for its episode counts. **Current operational default: 50k stamp grid,
three episodes per intermediate cell, twenty at the endpoint.** Production retains the weights, so
any stamp can later be re-evaluated more deeply than three episodes if a specific cell warrants it.

**The mechanism now exists rather than being a rule to remember.** `run_probe.sh` emits
`records.jsonl` as an optional **separate job output** (`RECORDS_OUT`), so a caller can declare
`- records.jsonl: RECORDS` and fetch ~100 KB instead of the archive. `result.tgz` is unchanged and
still contains the records, so every existing configuration means what it meant. Today's session
is the cautionary case: one five-cell archive was 791 MB and the endurance pack 207 MB, and I
extracted selectively to avoid unpacking four checkpoints I did not need.

---

## 7. What remains open after this document

- **§3b #1 headline metric** — resolved *in shape* by §2 (emit everything, select later), but the
  headline column still has to be named for the deliverable.
- **§3b #4 seeds** and **§3b #5 budget** — untouched here; #5 in particular deserves the owner's
  "can numbers decide it" question taken seriously rather than defaulted to 6e5 because RL-ViGen
  says so.
- **Evaluator construction coverage — 7 families, 12 of 12 rows, exercised as of 2026-09-04.**
  `rlvigen` (five baselines), `dmc_gb` (two), `idaac`, `ppg`, and — added 2026-09-03/04 —
  `ibac_sni`, `alda`, and `ctrl`. All seven drive the baseline's **own** action path.  This is
  construction coverage, not a standing equivalence discharge: [C96](CONSTRUCTION.md#c96) found
  that the earlier global revision could not tie those executions to the current action path, so
  the seven families must be revalidated under their family-specific source/config identities.

  Two things the new ones settle, both by reading each repo's own evaluator rather than improvising:

  - `ibac_sni` — its `Agent` loads from a **directory**, appending `model.pt` itself, so the
    harness stages the checkpoint under that name and lets *their* loader load it. Reaching past it
    to `torch.load` would mean the acting object is one we built.
  - `alda` — its modules do not exist until `initialize_env_dmc` then `build` have run, so the
    checkpoint cannot be loaded standalone; `_alda_trainer` runs that sequence through alda's own
    factory. Its action call is `select_action(preprocess_obs(obs['rgb'][None]))` and its step is a
    5-tuple with info fifth — copied from its `evaluate()`, because the extraction, the batch axis
    and the preprocessing are all part of *how alda acts*.

  **`ctrl` was the hardest and is done.** JAX end to end. Its checkpoint is
  `flax.serialization.to_bytes(train_state)`, and `from_bytes` **fills a target rather than
  constructing one**, so the TrainState has to be rebuilt first — the model with ctrl's own dims and
  flags, `model.init` on the same fake batch shapes, and the same optax chain, because the optimiser
  state is part of what was serialised. A wrong flag there produces a differently-shaped model
  rather than an error, which is why `CTRL_DEFAULTS` names each one against `train_ppo.py`.

  Establishing it also produced the estimator correction: `select_action(..., sample=False)` takes
  `pi.mode()`, but `train_ppo.py:244`/`:253` pass `sample=True`, so **ctrl samples** and the
  estimator axis is 4/8 rather than 3/9. That is the argument for building a family *before*
  reporting a baseline's numbers rather than after.

  **`alda` also widens its own grid.** It ships three regimes — `train`, `eval-easy` (`color_env`),
  `eval-hard` (`distract_env`) — and no `eval-medium`. Its `_build` chain takes the mode as an
  argument, so our harness constructs any RL-ViGen regime through *its* wrappers. That is the
  harness widening the grid, not a change to alda.

  **Validation status, stated because it is not the same as "works".** All seven family paths run
  and produce plausible magnitudes. Only two baselines are checked against their own evaluator's
  number so far; the remaining ten rest on construction rather than measurement. That is a burden
  on confidence in the instrument, not evidence that those baselines are poor.

- **Whether our harness driving a foreign `act` is faithful** — §1's guard is stated, not run, for
  ten of the twelve baselines; `drqv2` and `idaac` are the two discharged comparisons.
