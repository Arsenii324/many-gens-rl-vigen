# Review 17 triage against the live tree

**Status:** independent triage, 2026-09-06. This note treats
`notes/ai-review-17-external.md` as strong evidence of real project risks. It verifies each
finding against the live tree to refine its exact status and to choose the best operational
action; it is not a reason to discount a finding merely because the external reviewer could
not inspect every local file. No code, configuration, result, or remote job was changed for this
triage.

## Reading rule

The review was read in full. Its findings are presumed substantive and were checked against the live runnable source,
launchers, `datasphere/native/families.json`, the RL-ViGen checkout, the primary-source
reconciliation in `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`, and the relevant primary
materials under `ext/`. Local source and effective descriptors establish what this tree would
run; papers establish what the authors specified. A paper mismatch is therefore a closure item:
the best action is either to repair the setting before production, run a bounded labelled pilot,
or declare the necessary Door adaptation. It is not silently waived.

Disposition labels used below are exactly the requested set:

* **CONFIRMED** — the factual finding or source mismatch is established locally.
* **PARTLY CONFIRMED** — the core observation is true, and local evidence narrows the exact
  scope, provenance, or action; the finding remains actionable at that narrower scope.
* **ALREADY ADDRESSED** — the review asks for something the live tree already implements or
  records; remaining work may be validation or reporting.
* **CONTRADICTED** — the live source or primary material directly contradicts the review's
  assertion.
* **NEEDS EMPIRICAL TEST** — static evidence identifies a decision or risk, but cannot choose
  the production setting or establish numerical equivalence.

Where a recommendation is a genuine owner/reporting choice, that is stated in the closure
column rather than silently treating the recommendation as settled.

## Executive disposition

The review identifies real high-value closure work. Local verification narrows which items are
code repairs, which are bounded pilots, and which are declared adaptations; it does not lower
their priority merely because a proposed remedy needs a different source target.

1. **Confirmed source conflicts:** the current IDAAC Door profile is neither the published
   Procgen profile nor the authors' DMC continuous-control profile; current CTRL differs from
   the CTRL paper appendix on `T`, nearest-cluster `k`, temperature, representation learning
   rate, PPO epoch count, and environment count; current RL-ViGen SGQN differs from the
   published RL-ViGen Door table; IBAC-SNI remains a deliberate hybrid.
2. **The PPG warning is valid and remains an open production design point.** `8×256`
   and `1×2048` have different trajectory geometry even when a product or auxiliary cadence
   matches. The checked PPG primary source specifies Procgen, 256-step rollouts and no frame
   stack; the `1×2048`, 32-minibatch, three-stack profile comes from IDAAC's DMC supplement.
3. **The RL-ViGen names should expose lineage.** CURL/SVEA/SGQN/DrQ/DrQ-v2 are currently
   benchmark-family members, not all canonical implementations of the acronym-named papers.
4. **Several operational safeguards in the review are already present:** common offline
   checkpoint evaluation, effective argv/environment snapshots, training-row provenance,
   action-boundary diagnostics, and 100→84 RAD/SODA preprocessing.
5. **Operational default:** do not present the current tree as twelve source-exact methods.
   Before production, repair the provenance/index defects, freeze lineage-qualified identities,
   and close IDAAC/PPG/CTRL/IBAC-SNI design points through the labelled pilot or explicit
   necessary-adaptation route recorded in the tables below. Existing closed evaluator and
   reporting safeguards remain usable.

## Baseline and recommendation triage

### IDAAC

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| The current V100 profile is approximately 16 processes × 256 steps, 8 minibatches, PPO epoch 1, `lr=5e-4`, `gamma=.999`, entropy `.01`, value epochs 9/frequency 1, and one RGB frame. | **CONFIRMED** | `datasphere/native/families.json:247-275` sets base `4` processes and the V100 override `16`; `:282-299` passes 256/8; `runnable/idaac/ppo_daac_idaac/arguments.py:17-80,134-145` supplies the other defaults; `runnable/_launch/idaac.sh:9-17,28-30` selects 64×64 and the Door adapter. | Keep this as the exact current effective profile in the run manifest. Do not describe it as the DMC recipe. |
| The authors' DMC continuous-control profile is 1 process, 2048 steps, 32 minibatches, 10 PPO epochs, `lr=3e-4`, `gamma=.99`, entropy 0, value frequency 32, IDAAC coefficients `.1/.1`, three-frame input, and linear decay over 1M steps. | **CONFIRMED** | `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:193-195` records the checked `ext/idaac/raileanu21a-supp.pdf`, §E evidence; the current source does not apply those values. | Treat this as a real source-backed alternative, not a default silently substituted into C1. |
| “Change IDAAC before production” to the DMC profile. | **NEEDS EMPIRICAL TEST** | The source conflict is proven, but the paper's DMC environment and the Door adapter are not the same task. The current tree explicitly calls C1 a one-stack/4×256 Door port and records C2 as unresolved: `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:194,319,334-335`. | Run or otherwise approve a labelled C2 arm: DMC-like 3-stack/update geometry versus the current C1 Door port. Preserve C1; do not promote a short pilot to a source-fidelity conclusion. |
| The current instance/`level_seed` identity is conceptually unlike Procgen's nuisance level identity. | **CONFIRMED** | The live IDAAC descriptor says training-time evaluation uses literal scene 0 and calls the split vacuous (`families.json:363-365`); the primary reconciliation identifies the Procgen-level versus Door-scene mismatch (`:195`). | Define and report the Door identity variable explicitly. A fresh episode/scene label must not be presented as equivalent to Procgen's persistent level identity without a source/task rationale. |
| The DMC precedent should be used because continuous control is available in the IDAAC supplement. | **PARTLY CONFIRMED** | It is strong evidence for IDAAC, but it does not settle whether the shared Door budget, frame geometry, or instance label should change. | Use it as the C2 source-backed design point and record any departure as a Door adaptation. |

### PPG

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| `8×256` is not equivalent to `1×2048` merely because the interaction count, or `8×256×32`, matches. | **CONFIRMED** | The current descriptor is `num_envs=8`, `nstep=256`, `nminibatch=8` (`families.json:484-505`); the PPG implementation collects per-environment rollout data and computes GAE over the rollout (`runnable/ppg/phasic_policy_gradient/train.py:26-44`, `ppo.py` rollout/optimization path). Eight 256-step fragments are not one 2048-step trajectory. | Report rollout shape, minibatch size, and auxiliary cadence separately. Remove any wording that calls sample-count equality rollout equivalence. |
| Switch PPG to 1 environment × 2048 steps and 32 minibatches. | **PARTLY CONFIRMED** | That is the checked IDAAC DMC profile, not a PPG paper setting. The PPG paper/source reconciliation says Procgen uses 256-step rollouts, 8 minibatches, no frame stack, and `n_pi=32`: `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:208-212`; current project code uses `8×256` to retain the PPG rollout length (`families.json:496-505`). | Do not call this “published PPG.” If desired, make it a separately named continuous-control transfer arm and test it against the current PPG-shaped Door profile. |
| Use `gamma=.99`, `lr=3e-4`, entropy 0, and three-frame observations for PPG. | **PARTLY CONFIRMED** | These values are present in the IDAAC DMC precedent, not in the checked PPG primary recipe. Current PPG defaults remain `gamma=.999`, `lr=5e-4`, `aux_lr=5e-4`, `nminibatch=8`, `entcoef=.01`: `runnable/ppg/phasic_policy_gradient/train.py:27-44,156-163`; the launcher selects 64×64 (`runnable/_launch/ppg.sh:15-28`). | Treat the action head and entropy value as Door design points. A three-stack/1×2048 arm requires its own acceptance rationale and competence/equivalence probe; do not overwrite the current source-adapted profile by analogy. |
| The proposed continuous-control entropy/LR details need source verification, especially separate auxiliary LR. | **NEEDS EMPIRICAL TEST** | The review itself admits it did not identify an exact continuous-control PPG implementation; the live PPG has separate `lr` and `aux_lr` arguments (`train.py:31-32,85-104`). | Search/obtain a primary PPG continuous-control implementation or label both rates as Door choices. Compare health and performance only after retaining the two rates in the effective manifest. |
| Preserve PPG-specific `n_pi=32`, policy/value epochs 1/1, auxiliary epochs 6, and clone coefficient 1. | **ALREADY ADDRESSED** | `runnable/ppg/phasic_policy_gradient/train.py:27-45,79-109` passes these values into the source PPG learner; `families.json:513-524` adds retention flags without changing them. | Keep; verify in the executed config. |
| The continuous Gaussian adaptation is reasonable. | **PARTLY CONFIRMED** | The current Gaussian head is explicitly project-authored (`runnable/ppg/phasic_policy_gradient/distr_builder.py:1-54`), while the PPG source action head is Procgen categorical (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:210`). | Report it as a necessary Door adaptation, not a source match; keep raw/executed action and entropy diagnostics. |

### CTRL

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| The paper appendix specifies 32 environments, 256 rollout steps, one RL/representation epoch, 8192 samples/epoch, learning rate `5e-4`, clusters 200, nearest-cluster `k=3`, clustering `T=2`, and temperature `.3`. | **CONFIRMED** | The local primary LaTeX appendix gives these values at `ext/ctrl_rl/arXiv-2106.02193v2/appendix.tex:104-128` (the table is labelled “Experiments' parameters”). | Preserve this as paper evidence, but distinguish paper's discrete Procgen setup from the Door port. |
| Current CTRL differs materially: `cluster_len=10`, nearest `myow_k=1`, Sinkhorn `k=1`, temperature `.1`, `lr_ctrl=1e-4`, and environment count 16 on DataSphere or 64 in the V100 profile. | **CONFIRMED** | `datasphere/native/families.json:754-821` sets 16/10/8/200/5e-4/1e-4; its V100 host profile sets `num_envs=64`; `runnable/ctrl/train_ppo.py:33-58` and `runnable/ctrl/algo.py:151-204,208-245` show the live knobs and their use. | Correctly state which host profile is intended. Do not repeat “current 64” as a universal claim: it is V100-only. |
| Change production to paper values, especially `T=2`, nearest `k=3`, temperature `.3`, and representation LR `5e-4`. | **NEEDS EMPIRICAL TEST** | The mismatch is real, but paper Table 2 is for discrete Procgen and the current Door code adds a continuous Gaussian/action path (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:231-233`; `runnable/ctrl/models.py:110-179`). | First trace and record the Door raw-action/transition path. Then run a short, explicitly labelled sensitivity arm (`10` vs `2`, `myow_k=1` vs `3`, `.1` vs `.3`, `1e-4` vs `5e-4`) or obtain an owner-selected paper-faithful adaptation. Do not change both method and resource profile without attribution. |
| The paper's `k=3` means nearest clusters, not the separate Sinkhorn iteration count. | **CONFIRMED** | The paper appendix defines `k` as nearest neighbours (`appendix.tex:122-125`); the live implementation has separate `k` and `myow_k` arguments (`train_ppo.py:52-58`, calls at `:241-245`). | Any patch/config change must set `myow_k=3` only unless a separate Sinkhorn decision is intended. Add a source-to-argv mapping check before changing it. |
| JAX/Flax/Optax versions differ from the authors' environment. | **CONFIRMED** | The production descriptor pins JAX 0.4.35, Flax 0.10.2 and Optax 0.2.3 (`families.json:851-860`); the project notes record the older author-era stack and the CUDA-root workaround. | Record exact resolved packages and environment in the run manifest, and use a smoke/identity check after any dependency change. This is provenance evidence, not proof of a numerical defect. |
| The official repository should remain the implementation source. | **ALREADY ADDRESSED** | The active port is under `runnable/ctrl`, with its source closure and patch provenance recorded in `families.json` and `source-lock.json`; the primary reconciliation treats the official `ext/ctrl_public` source as the comparison basis. | Keep the source closure and patch hash; do not replace it with a new hand-written CTRL implementation. |

### IBAC-SNI

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| Selecting the Impala trunk and passing `beta=1e-4` corrected two major earlier errors. | **ALREADY ADDRESSED** | `runnable/_launch/ibac_sni.sh:46-60,113-134` selects `--model_type impala` and `--beta 1e-4`; `runnable/ibac_sni/torch_rl/model.py:147-181` is the three-pool Impala port. | Revalidate this exact configuration; do not reuse competence numbers from the old MiniGrid-shaped trunk or beta=1 run. |
| The CoinRun source command uses `--l2 0.0001 -uda 1 --beta 0.0001 --nr-samples 12 --sni`. | **CONFIRMED** | `ext/IBAC-SNI/README.md:104-120` gives the command and explains weight decay/data augmentation; `coinrun/coinrun/policies.py:55-75` shows 256 latent, `rho-5`, and repeated stochastic samples. | Treat these as CoinRun branch evidence, not as an automatic Door command translation. |
| Current Door IBAC-SNI is still a hybrid: latent 64 instead of 256, one sample instead of 12, unshifted softplus instead of `rho-5`, no source-backed L2/weight decay, and no mapped UDA. | **CONFIRMED** | Current bottleneck is `runnable/ibac_sni/torch_rl/bottleneck.py:20-45` (latent from model construction, unshifted `softplus`); current `model.py:205-209` constructs a 64-dimensional bottleneck and `:277-281` adds the Box Gaussian; launcher has no `nr-samples`, `l2`, or `uda` equivalent. The source-side values are at `ext/IBAC-SNI/coinrun/coinrun/policies.py:55-83` and `config.py:54,131-134`. | Retain the hybrid label. Any CoinRun-head port must be a new fidelity arm with separate checkpoint identity and tests for sample expansion, posterior scale, L2, and augmentation. |
| Port the CoinRun VIB/SNI head, restore L2, and investigate UDA. | **NEEDS EMPIRICAL TEST** | The missing mechanisms are source-confirmed, but no primary source defines their continuous 7-D Door semantics. The current primary reconciliation explicitly classifies latent/sample/action choices as adaptations (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:219-223`). | First establish a minimal functional equivalence test on the current torch path; then decide whether 12 samples and 256 latent are scientifically meaningful under the continuous head. Do not map `-uda 1` to DrQ random shift without tracing the CoinRun implementation. |
| Entropy 0 is a defensible Door profile after the `.01` divergence. | **PARTLY CONFIRMED** | The live launcher documents paired probes: `.01` drove `mean_log_std` upward while 0.0 did not (`ibac_sni.sh:65-112`); the primary reconciliation calls 0 a measured Door deviation, not a source default (`:222`). This is not a 600k competence or full-factorial result. | Keep 0 as the operational default pending owner ratification, but label it as an adaptation and remeasure with the exact Impala/beta configuration at the competence budget. |
| The official repository has no single authors' PyTorch continuous-pixel implementation to run unchanged. | **CONFIRMED** | The launcher itself distinguishes the TensorFlow CoinRun pixel branch and PyTorch MiniGrid branch (`ibac_sni.sh:7-16`); the current Box head is authored in `model.py:188-203`. | Report lineage as “IBAC-SNI-derived Door port, Impala/VIB/SNI hybrid,” not “authors' exact continuous pixel implementation.” |
| One process is safe but not source-faithful to the original 16-process default. | **PARTLY CONFIRMED** | Original torch parser defaults to 16 processes and 128 frames/process (`ext/IBAC-SNI/torch_rl/scripts/train.py:35-49`); current descriptor base is one process ×128 and records the 16-worker gt4.1 OOM evidence (`families.json:619-749`). That proves a DataSphere capacity failure, not that one process is methodically correct. | Do not record one process as a superseding source default. The production manifest must state host, process count, and memory rationale; a V100 or other bounded resource test can determine whether source-like parallelism is runnable. |

### SGQN and RL-ViGen variant identity

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| RL-ViGen Door SGQN should use quantile `.90`, critic consistency weight `.7`, and auxiliary LR `8e-5`. | **CONFIRMED** | `pdftotext` of `ext/baseline_resources/benchmarks/rlvigen_neurips_supplementary.pdf`, Table 6, lists Door values `.9`, `.7`, `8e-5` (the same source is indexed in the primary reconciliation). | This is a legitimate source-fidelity correction candidate, but change only in a separate configuration/version and revalidate the evaluator binding. |
| The current config uses `.93` and `1e-4`, and the consistency weight is hard-coded `.9`. | **CONFIRMED** | `RL-ViGen-upstream/cfgs/sgqn_config.yaml:49-56` has `aux_lr: 1e-4`, `sgqn_quantile: .93`; `RL-ViGen-upstream/algos/sgqn.py:120-127,142-145,168-173` passes the first two and hard-codes the critic consistency coefficient. | Expose the hard-coded coefficient, create a composed effective-argv/config snapshot, and run a focused source/config test before any production resubmission. |
| Canonical SGQN and RL-ViGen SGQN should not be mixed under one name. | **CONFIRMED** | RL-ViGen's supplementary source describes its SGQN saliency/augmentation variant, while the active family is the RL-ViGen DrQ-v2 branch (`families.json:65-70`; `RL-ViGen-upstream/algos/sgqn.py:119-124`). | Use an explicit result label such as `sgqn-rlvigen`; preserve canonical SGQN only as a separate arm if it is ever implemented. |
| CURL should be called `CURL-RLViGen`, because RL-ViGen uses one encoder rather than CURL's original target/online pair. | **CONFIRMED** | RL-ViGen supplementary, §A, states the single-encoder alteration; `RL-ViGen-upstream/algos/curl.py:54-78` subclasses `DrQV2Agent` and constructs one encoder plus CURL head. | Change report/manifest naming at the reporting layer, not the algorithm source, unless a separate canonical CURL arm is requested. |
| SVEA should similarly be source-tagged as RL-ViGen, and the current RL-ViGen DrQ-v2 lineage should be retained for that objective. | **CONFIRMED** | Current `RL-ViGen-upstream/algos/svea.py:165-194` is the RL-ViGen learner with its own encoder/actor/critic and random-shift augmentation; the primary reconciliation distinguishes it from DMCGB's official SVEA path (`:134-137`). | Keep the implementation for an RL-ViGen reproduction; use `svea-rlvigen` in the result namespace. |
| DrQ is better described as RL-ViGen DrQ than as pristine canonical DrQ. | **PARTLY CONFIRMED** | The active family is the RL-ViGen checkout (`families.json:22-70`), while the original DrQ source is a separate `ext/drq` closure; the primary reconciliation records the SAC/DMC versus RL-ViGen distinction (`:143-145`). The review did not exhaustively establish every scalar. | Source-tag the lineage. Do not claim all canonical DrQ hyperparameters are reproduced without a separate source audit. |

### DrQ-v2, RAD, SODA, and ALDA

| Review 17 claim/recommendation | Status | Live/primary evidence | Closure action |
|---|---|---|---|
| DrQ-v2's action-repeat-1 Door override is important and already correct. | **ALREADY ADDRESSED** | `runnable/_launch/rlvigen.sh:61-78` passes `action_repeat=1`; the primary reconciliation records the RL-ViGen Robosuite convention (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:94-107`). | Keep and retain the effective override in each manifest. |
| V100 replay capacity around 620k is effectively non-evicting for a 600k Door run. | **PARTLY CONFIRMED** | The V100 override is explicit at `datasphere/native/families.json:25-32`, with the reset/headroom calculation. However the ordinary DataSphere production profile is `300000` at `:100-105`; 620k is not the universal current production value. | Report host profile with the capacity. Do not generalize the V100 argument to the 300k DataSphere profile, which is intentionally recency-limited. |
| RAD/SODA are in strong source shape and must render 100 then crop to 84. | **PARTLY CONFIRMED** | The live launcher enforces 100 (`runnable/_launch/dmc_gb.sh:21-27`); `wrappers.py:26-36` uses the Robosuite branch, and `modules.py:67-80,130-141` implements the 84 crop. The primary reconciliation records that native 84 makes RAD's crop degenerate and SODA assert (`:169-177`). “Strong” remains a static fidelity judgment, not live numerical validation. | Keep 100→84 for the source-faithful arms and report the FoV difference. Do not replace it with native 84 in the primary run. |
| RAD/SODA's 100→84 sensor is not visually identical to native 84. | **CONFIRMED** | The launcher comments state the different field of view (`dmc_gb.sh:22-26`), and the crop code takes an 8-pixel border from a 100 render (`modules.py:67-80`). | Retain the observation-geometry table; add a standardized-sensor arm only if the owner wants a separate comparability analysis. |
| SODA should use an explicit code-profile versus paper-profile distinction because auxiliary-LR provenance is ambiguous. | **NEEDS EMPIRICAL TEST** | The primary reconciliation records the paper/code ambiguity; the live DMCGB path is the active source closure. No static source fact alone selects which profile generated the external paper result. | Snapshot the exact effective SODA argv/config and label it `SODA-code` unless primary evidence for a paper profile is found. Do not silently tune the LR. |
| ALDA preserves the important source values: batch 128, 12 latents × 12 values, beta 100, stack 3, 64×64. | **CONFIRMED** | `runnable/alda/specs/train_alda_robosuite_door.yaml:9-14,38-47` and `runnable/alda/trainers/alda_trainer.py:49-80` show those values; the ALDA source/spec provenance is recorded in `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:179-187`. | Keep the algorithmic values; report Door horizon/action-repeat and the source adaptation separately. |
| ALDA is therefore ready/high-fidelity. | **PARTLY CONFIRMED** | Static algorithmic settings are close, but Door is not an ALDA source task and no full CUDA production competence result is implied by the source match. The current spec also documents that Door action repeat is a dead knob (`:42-46`). | Require the normal functional/endpoint validation and retain the explicit Door adaptation label. |

## Shared protocol, action semantics, and evaluation

| Review 17 recommendation/finding | Status | Live evidence | Closure action |
|---|---|---|---|
| The observation geometries should remain source-faithful rather than be forced to one size. | **CONFIRMED** | The current split is documented in `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:76-77,238-258`: RL-ViGen native 84/3, RAD/SODA 100→84, ALDA 64/3, PPG 64/1, IDAAC 64/1, IBAC 64, CTRL 64/1. Their encoders are resolution-coupled. | Report the geometry as a protocol axis. Do not “equalize” by silently breaking RAD/SODA or changing resolution-dependent trunks. |
| IDAAC and continuous PPG should both be changed to three-frame stacks. | **PARTLY CONFIRMED** | IDAAC's DMC supplement explicitly supports three frames; the checked PPG primary source describes Procgen 64×64 without a frame stack (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:194,209-211`). | Make IDAAC C2 a real arm. For PPG, obtain PPG-specific continuous evidence or call three-stack a Door adaptation; do not call it publication-backed PPG. |
| RNG isolation around online evaluation is sound, and common offline checkpoint evaluation should be authoritative. | **ALREADY ADDRESSED** | `families.json:106-129,341-365,587-615,804-925` records disabled/diagnostic family-native evaluation and the common offline grid; `docs/EVAL-PROTOCOL.md:133-147` makes the offline evaluator authoritative. The live evaluator/provenance path records applied mode/scene and placement witnesses in `scripts/eval_provenance.py:180-204`. | Preserve this as the reporting rule. Any native train-time curve remains diagnostic, not the headline metric. |
| Instrument raw action, executed/clipped action, clipping rates, and raw-to-executed distance. | **PARTLY CONFIRMED** | `scripts/eval_provenance.py:256-296,299-354` implements policy-output versus declared action-boundary diagnostics and explicitly records controller clipping as unobserved; `scripts/eval_grid.py:1054-1068` preserves that distinction. | The policy-boundary requirement is already met. Do not claim controller-internal torque clipping is measured; add it only if a wrapper exposes it. |
| Do not silently replace the continuous Gaussian with tanh squashing. | **ALREADY ADDRESSED** | The primary reconciliation classifies PPG/IDAAC/IBAC-SNI/CTRL Gaussian heads as necessary Door adaptations and the action diagnostics preserve raw values (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:78-83,210,220,232-233`; `eval_provenance.py:271-275`). | Keep current semantics unless a separately named, source-backed action-density arm is adopted. |

## Provenance and reporting

| Review 17 claim/recommendation | Status | Live evidence | Closure action |
|---|---|---|---|
| A final executed-config manifest is needed; descriptor prose is not enough. | **ALREADY ADDRESSED** | `datasphere/native/run_probe.sh:196-245` captures the rendered argv, host profile, runner environment, and cell environment; `:1293-1300` carries effective configs into `run_manifest.json`; `tests/test_effective_config_artifact.py:26-145` tests the ordering, JSON, and manifest collection. | Ensure every final job retains these files in the archive and lightweight records. This is a production-evidence requirement, not a reason to rewrite source code. |
| Effective host/argv configuration must remain distinct from evaluator identity. | **ALREADY ADDRESSED** | `datasphere/native/normalize_curves.py:583-600` puts `host_profile` and `effective_configs` on training provenance while evaluator identity uses its canonical scope; the schema-2 repair is reflected in `datasphere/native/evaluator_identity.py:131-147`. | Preserve this split during payload revalidation; do not reintroduce host profile into evaluator code/config identity. |
| Action and observation semantics should be emitted as contracts. | **PARTLY CONFIRMED** | Action-boundary and effective-config fields exist, but the evaluator explicitly says controller clipping is not observed (`eval_provenance.py:299-307,333-338`). Resolution/frame/action-repeat/stack are carried in canonical scope fields (`evaluator_identity.py:141-148,226-245`). | Treat the existing fields as the contract baseline and keep the unobserved controller boundary explicit. |
| The uploaded review artifact's missing nested clone `.git` history prevents cryptographic proof of upstream ancestry. | **CONFIRMED** | This is a limitation of the artifact reviewed, and the review states it plainly. The project has source-lock commit records (`datasphere/native/source-lock.json:58-66`) and the replacement builder records root git metadata, but neither can reconstruct omitted nested history from a copied directory alone. | Build the final artifact only after freeze; include upstream URL/commit, pristine-tree hash, patch hash, final-tree hash, and the source-lock. Do not claim the current uploaded artifact proves nested ancestry. |
| Use lineage-qualified names such as `curl-rlvigen`, `svea-rlvigen`, and `sgqn-rlvigen`. | **CONFIRMED** | Current family data groups these under one RL-ViGen family (`families.json:65-70`), while the primary source and active code show benchmark-specific variants. | Apply at the report/manifest namespace. This is a reporting correction, not a training-code change. |
| Retain a canonical/original-algorithm sensitivity arm for CURL/SVEA where needed. | **NEEDS EMPIRICAL TEST** | The distinction is proven, but a second canonical implementation is outside the current RL-ViGen null and would be a new experiment. | Do not add it to the primary fleet without owner approval; if needed, run as a separate labelled comparison, never merge columns. |

## Per-baseline current status matrix

| Baseline | Review-17 disposition | What is actually established | Remaining closure |
|---|---|---|---|
| `drqv2` | **PARTLY CONFIRMED** | RL-ViGen lineage, action-repeat 1, and profile-specific replay reasoning are documented. | Retain profile-specific capacity and obtain final validation; no need to change the algorithm from this review. |
| `svea` | **CONFIRMED** for lineage naming; **PARTLY CONFIRMED** for “high fidelity” | RL-ViGen SVEA is not DMCGB canonical SVEA, but current implementation preserves the intended benchmark lineage. | Name/report correctly and validate the final frozen payload. |
| `drq` | **PARTLY CONFIRMED** | Current target is RL-ViGen DrQ, not canonical SAC/DMC DrQ. | Source-tag; do not claim canonical equivalence. |
| `sgqn` | **CONFIRMED** mismatch | RL-ViGen Door table values differ from current YAML/hard-coded weight. | Decide and implement a versioned correction, then revalidate. |
| `curl` | **CONFIRMED** lineage distinction | Current code is one-encoder RL-ViGen CURL, not original target/online CURL. | Rename/report; canonical arm only if separately commissioned. |
| `rad` | **PARTLY CONFIRMED** | DMCGB source path and 100→84 are correct; “ready/high” is static, not a live result. | Preserve geometry and complete functional/production validation. |
| `soda` | **PARTLY CONFIRMED** | Official DMCGB path and 100→84 are correct; aux-LR provenance remains unresolved. | Snapshot effective code profile and resolve/report paper-vs-code choice. |
| `alda` | **PARTLY CONFIRMED** | Principal source values are present; Door is a necessary adaptation, and no full production competence is implied. | Validate the exact Door spec and retain adaptation labels. |
| `idaac` | **CONFIRMED** source conflict; **NEEDS EMPIRICAL TEST** for replacement | Current C1 is 4×256/8, one RGB frame; DMC §E is 1×2048/32/10, three stack, etc. | Run/ratify C2; do not relabel C1 as DMC-faithful. |
| `ppg` | **PARTLY CONFIRMED** | Rollout-geometry warning is correct; proposed DMC-like profile is not PPG-primary evidence. | Resolve with a PPG-specific source or separate Door arm. |
| `ibac_sni` | **CONFIRMED** hybrid | Impala/beta repair is live, but latent/sample/scale/L2/UDA/continuous-head gaps remain. | Keep hybrid name; decide whether a CoinRun-head port is worth a separate arm; remeasure entropy/beta/profile. |
| `ctrl` | **CONFIRMED** source mismatch; **NEEDS EMPIRICAL TEST** for switch | Paper table values are verified, current DataSphere/V100 profiles and Door action path differ. | Trace action semantics and run a narrowly controlled config sensitivity before adopting paper values. |

## Review-17 blind spots and uncertainty

The review explicitly says it did not run training, smoke tests, live evaluation, or the full test
suite. It therefore cannot establish competence, endpoint numerical behavior, convergence, or
whether any proposed profile is better on Door. It also says:

* nested clone `.git` histories were absent from the reviewed artifact, so upstream ancestry was
  not independently cryptographically verified;
* some OpenReview pages and supplementary ZIPs were not parseable in its browsing environment;
* it did not exhaustively source-audit every scalar in all twelve baselines, especially SODA's
  paper-versus-code auxiliary LR and lower-level augmentation defaults.

The live-tree primary reconciliation reduces, but does not erase, those limits. In particular,
the following are still not settled by static evidence:

1. whether IDAAC C2 or C1 is the intended Door design point;
2. whether the IDAAC DMC rollout recipe should be transferred to PPG, and whether PPG should
   use three stacked frames;
3. whether CTRL's discrete-Procgen appendix values should be transferred to the continuous Door
   adaptation, especially `cluster_len`, nearest-cluster `myow_k`, temperature, and `lr_ctrl`;
4. whether CoinRun's 12-sample/256-latent VIB estimator is the right continuous-action IBAC-SNI
   adaptation, and what `-uda 1` should mean on Door;
5. whether source-like IBAC-SNI process parallelism is affordable on the authorized production
   host; and
6. whether the remaining source/code ambiguities in SODA and lower-level augmentation defaults
   affect the headline result materially.

## Dependency-ordered closure actions

1. Freeze and capture current effective argv/environment manifests before changing any profile.
2. Resolve the IDAAC C1/C2 design point, with a labelled three-stack DMC-style arm if the source
   fidelity objective is retained.
3. Treat PPG's proposed geometry as a separate hypothesis, not a source correction; decide it
   only after primary PPG evidence or a controlled Door diagnostic.
4. Trace CTRL's continuous action path and map paper `k` to `myow_k`; then decide whether a
   paper-profile sensitivity is warranted.
5. Decide whether to correct SGQN to the RL-ViGen Door table. If yes, expose the `.7` coefficient
   and rebuild/revalidate the evaluator binding.
6. For IBAC-SNI, retain the Impala/`beta=1e-4` default, but keep the latent/sample/scale/L2/UDA
   gaps visible and run only the bounded diagnostics needed to choose a Door design point.
7. Preserve RAD/SODA 100→84 and lineage-qualified names; resolve SODA's code-vs-paper LR in the
   effective manifest.
8. Build the final review artifact only after the source/profile decisions and validation wave;
   include the source-lock and effective manifests, while preserving the exclusion manifest and
   avoiding any claim that omitted nested `.git` history was copied.

No item above is evidence that a production result already exists. The strongest current state is
“source-audited with explicit unresolved design points,” not “all twelve source-exact.”
