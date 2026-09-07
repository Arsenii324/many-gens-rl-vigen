# Review 18 triage against the live tree

## Scope and reading rule

This is an independent triage of `notes/ai-review-18-external.md`, not a second full
source audit. Review 18 is treated as strong evidence of real project problems. It explicitly
says it did not have the live `runnable/**`, `families.json`, patch, or `ext/**` trees and did
not run training, tests, renderers, or infrastructure; I therefore use the live tree to refine
the exact status and action, not to discount its findings. I checked the decisive claims against
the live tree, `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`, `notes/review-17-triage.md`,
and local primary material in `ext/`.

The labels below mean:

- **CONFIRMED** — the concrete fact is supported by the current tree/local primary source.
- **PARTLY CONFIRMED** — the core observation is supported and actionable, while local evidence
  narrows its scope, target, or exact closure action.
- **ALREADY ADDRESSED** — the project has already made the relevant distinction or safeguard;
  Review 18 is useful as corroboration, not as a new closure requirement.
- **CONTRADICTED** — the local source/current tree directly disagrees with the review claim.
- **NEEDS MEASUREMENT** — the static fact is plausible or confirmed, but the recommendation
  requires a controlled run, runtime trace, or predeclared owner choice.

This note cross-references review 17 rather than repeating its full evidence tables. Review 17
remains the detailed live-tree triage for the IDAAC/PPG/CTRL/IBAC-SNI/action-semantics issues.

## Executive disposition

Review 18 supplies strong evidence for four material closure points:

1. Its distinction between benchmark fidelity, method fidelity, Door adaptation, and shared
   measurement protocol is scientifically correct, but the current project already records most
   of the distinctions in five-way classifications and lineage notes. The useful missing step is
   to make the target of each classification explicit in the source-resolution manifest.
2. Its downgrade of literal-original claims for RL-ViGen SVEA/CURL/SGQN, and its warning that
   the active RL-ViGen family is not interchangeable with each original paper implementation,
   are supported. They do not require replacing the current implementations.
3. Its recommendation to use the IDAAC DMC recipe for PPG or to make IDAAC-C primary regardless
   of observed Door competence identifies the right source-fidelity pressure, but needs a precise
   local rule. The DMC recipe is source-backed for IDAAC and a valuable secondary comparator for
   PPG; the best default is to retain C1/PPG-P as labelled current arms while preparing bounded
   C2/PPG-DMC-reference pilots or explicitly declaring the necessary adaptation before production.
4. The local source index contains a real provenance defect: the file called
   `ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf` identifies itself as InfoBot,
   arXiv:1901.10902, not IBAC-SNI. This is **CONFIRMED** and must be repaired before any source
   artifact or citation manifest is frozen.

Review 18 is sufficient to keep the named source-fidelity issues on the pre-production closure
path. Its notes-only scope means it cannot by itself establish numerical equivalence, runtime
correctness, or a completed production run.

## 1. Fidelity axes and benchmark framing

| Review 18 claim/recommendation | Status | Live evidence and triage | Closure action |
|---|---|---|---|
| Freeze separate “benchmark fidelity” and “method fidelity” identities, plus Door adaptations and project measurement choices. | **PARTLY CONFIRMED** | The underlying distinction is real. `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:1-42,65-83` already separates RL-ViGen task authority, original sources, adaptations, and five controlled classifications; `EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:193-207,256-282` already requires source/current evidence and target-specific rows. What is not yet explicit is a first-class `fidelity_target`/`variant_identity` field on every resolution. | Add these fields to the planned source-resolution manifest when that artifact is implemented. Do not rewrite the current classifications as if the distinction were previously absent. |
| RL-ViGen Door should be authoritative for task/environment/evaluation, while original method sources govern method machinery. | **ALREADY ADDRESSED** | This is the operating rule in the primary reconciliation (`:8-42,65-83`) and its closure requirements (`:324-355`). The common offline grid is explicitly project-owned in `docs/EVAL-PROTOCOL.md:133-147`. | Preserve the rule in the final artifact; no algorithm change follows from Review 18. |
| A method can be benchmark-faithful while being materially different from the original paper/code. | **CONFIRMED** | `families.json:65-70` selects RL-ViGen implementations for five baselines; the primary reconciliation explicitly labels their RL-ViGen source path rather than silently treating it as each paper’s canonical code (`:101,115-118,125-141,147-163`). | Use lineage-qualified result names and keep original-source values beside effective Door values. |
| RL-ViGen’s shared Door recipe is 84×84, stack 3, γ=.99, action repeat 1, and 600k frames, with Door-specific SGQN values. | **CONFIRMED** | The live reconciliation records the Door task and geometry at `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:65-83,101-107`; production planning uses 600k at `datasphere/native/plan_production.py:367-386`; SGQN’s source discrepancy is independently triaged in `review-17-triage.md` under “SGQN and RL-ViGen variant identity.” | Keep this as benchmark evidence, not as a claim about every original algorithm source. Retain effective composed values in the run manifest. |
| Review 18’s statement that RL-ViGen’s common replay table says 10M should be used to describe the current benchmark. | **CONTRADICTED** | The local RL-ViGen configs all set `replay_buffer_size: 1000000`, e.g. `RL-ViGen-upstream/cfgs/config.yaml:19-23` and `svea_config.yaml:18-22`; current DataSphere production sets `replay_capacity: 300000` in `datasphere/native/families.json:100-105`. No `10000000` replay setting appears in the active RL-ViGen tree. | Do not import the 10M number into the current manifest without a separate primary citation. Report original/configured 1M and production 300k as distinct values; see replay row below. |

## 2. Baseline-by-baseline triage

The following rows are deliberately short. Detailed live evidence and closure ordering are in
`notes/review-17-triage.md`; these rows record what Review 18 adds and the precise action after
local verification.

| Baseline | Review 18’s concrete finding/recommendation | Status | Current evidence and closure |
|---|---|---|---|
| **drqv2** | The core DrQ-v2 mechanism is the strongest case; distinguish original replay, RL-ViGen replay, and project production replay. Call 620k “non-evicting for this horizon,” not source-exact. | **PARTLY CONFIRMED** | The actor/critic/augmentation match is already recorded in `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:112-123`. The review’s 620k statement applies only to the V100 override (`datasphere/native/families.json:25-32`); ordinary production is 300k (`:100-105`). No additional numerical neutrality has been shown. | Keep the review-17 wording: host-profile-qualified behavioral equivalence only. Never generalize the V100 capacity argument to the ordinary 300k profile. |
| **drq** | Call it DrQ under the RL-ViGen Door recipe, not original DrQ hyperparameters. | **ALREADY ADDRESSED** | The primary reconciliation already marks the original-DMC versus RL-ViGen batch/lr/replay mismatch as `SOURCE CONFLICT` if called original and `SOURCE VARIANT WITH CONTEXT` if called RL-ViGen Door (`:134-141`). | Apply the lineage-qualified name in reporting; no source or training change is implied. |
| **svea** | The active RL-ViGen SVEA is DrQ-v2-style, without a SAC entropy/temperature term, so “exact original SVEA” is too broad; call it RL-ViGen-SVEA. | **PARTLY CONFIRMED** | The runtime code confirms the observation: `RL-ViGen-upstream/algos/svea.py:165-194,218-320` uses the DrQ-v2-style Gaussian actor, Q losses, and actor loss `-Q.mean()`; it has no SAC temperature term. The current primary note’s “EXACT SOURCE MATCH” is explicitly scoped to the SVEA update mechanism and separately marks architecture/optimization as variants (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:125-132`). | Do not relabel the active code as canonical SAC-SVEA. Tighten the report-level identity to `RL-ViGen-SVEA` if naming can be changed. A full reclassification is documentation work, not evidence for a code replacement. |
| **sgqn** | The active SGQN inherits the RL-ViGen DrQ-v2-style backbone rather than the original paper’s SAC realization; use RL-ViGen-SGQN and verify Door q/.7/aux-lr values. | **ALREADY ADDRESSED** | `RL-ViGen-upstream/algos/sgqn.py:119-145,157-172` shows inheritance/actor/Q structure and the hard-coded `.9`; the Door-value conflict and lineage label are already confirmed in `review-17-triage.md` and `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:143-149`. | Retain the existing effective-argv/source-composition closure. Do not infer a new SGQN implementation from Review 18. |
| **curl** | RL-ViGen CURL is explicitly a one-encoder DrQ-v2-derived variant, not original CURL’s two-encoder implementation; call it CURL-RLViGen. | **CONFIRMED** | `RL-ViGen-upstream/algos/curl.py:54-78` subclasses `DrQV2Agent` and constructs one encoder plus the CURL head. The primary reconciliation currently scopes `EXACT SOURCE MATCH` only to the mechanism (`:154-163`), and review 17 already recorded the lineage issue. | Use `CURL-RLViGen` in the report/manifest. A canonical two-encoder arm would be a separate experiment, not a silent substitution. |
| **rad** | The active implementation is the DMC Generalization Benchmark RAD lineage, not necessarily the original RAD repository; call it DMCGB-RAD. | **PARTLY CONFIRMED** | The source index includes both original `ext/rad/**` material and active `runnable/dmc_gb` source (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:51,165-177`); the descriptor maps RAD to `dmc_gb` (`datasphere/native/families.json:142-243`). “Not official RAD source” is therefore right as provenance caution, but the current mechanism is still source-backed. | Record both `method_source=RAD` and `runtime_lineage=DMCGB`; do not rename a source directory or alter the method without a separate request. |
| **soda** | SODA is source-shaped and the 100→84 path is important, but auxiliary-LR provenance and final runtime correctness need care. | **PARTLY CONFIRMED** | The source mechanism and size dependency are documented in `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:169-177`; live crop code is `runnable/dmc_gb/src/algorithms/modules.py:67-80`. Static source evidence does not establish numerical fidelity or select a paper/code LR profile. | Keep 100→84 as the primary default. Snapshot effective argv and, if the LR remains material, run a targeted source/profile check; do not call “strong” a completed empirical validation. |
| **alda** | ALDA’s core values look source-backed, but 500k versus common 600k must be resolved; source UTD≈1 should not be replaced by the retired `.25` stability setting. | **PARTLY CONFIRMED** | Active spec/trainer evidence is `runnable/alda/specs/train_alda_robosuite_door.yaml:9-47` and `runnable/alda/trainers/alda_trainer.py:49-80`; the descriptor advertises 500k source-style values (`datasphere/native/families.json:374-480`) while production templates accept the global `{frames}` field (`:382-386`) and planning defaults to 600k (`datasphere/native/plan_production.py:367-373`). | Resolve the effective production budget in the final composed manifest. If both are wanted, predeclare 500k source-horizon and 600k common-budget outputs; never select after observing performance. No additional ALDA code change follows from Review 18 alone. |
| **idaac** | The DMC continuous-control recipe is the applicable source-informed target; IDAAC-C should be the primary even if it is less successful, rather than choosing by Door performance. | **PARTLY CONFIRMED** | The DMC recipe is confirmed at `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:193-196,238-258`; current C1 is confirmed as 64×64, one stack, 4×256, PPO1 at `:103` and is already triaged in review 17. The “regardless of performance” rule is a policy recommendation, not a fact supplied by the paper; the current Decision Sheet proposes a predeclared competence-based choice among labelled arms (`notes/DECISION-SHEET.md:1497-1529`). | Keep C1 and C2 distinct. Before production, predeclare either a source-fidelity-primary rule or a fixed two-arm report; do not let Review 18 retroactively decide after results. A C2 pilot remains **NEEDS MEASUREMENT**, not an automatic replacement. |
| **ppg** | There is no established original continuous-control PPG design; the 1×2048/32/stack3 recipe is from the IDAAC authors’ DMC comparator, not original PPG. | **CONFIRMED** | Local PPG source/reconciliation says Procgen PPG specifies 256-step/8-minibatch/no-stack with phasic `nπ=32`, while current Door uses 8×256 and a project Gaussian head (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:208-212`; `runnable/ppg/phasic_policy_gradient/train.py:27-45`; `datasphere/native/families.json:481-505`). Review 17 already made the same distinction. | Name any DMC-inspired arm `PPG-DMC-reference` or equivalent. Do not call it published PPG or silently replace the current port. A 1×2048/stack3 comparison is **NEEDS MEASUREMENT**. |
| **ibac_sni** | The current method is an irreducible hybrid; restore CoinRun head details only as a separately tested fidelity arm; entropy 0 and one process are adaptations, not source defaults. | **CONFIRMED** | `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:214-223,280-321` and review 17 establish Impala, latent/sample, UDA/L2, entropy, and process distinctions. The current source paper index is additionally wrong; see §5. | Preserve the explicit hybrid label. Correct the source index before artifact generation. Any CoinRun-head change requires a separate architecture/config identity and measurement; no silent “fix” is licensed. |
| **ctrl** | Paper Table 2 and released official code disagree; do not change `cluster_len=10` to paper T=2 without choosing which source target is being reproduced. | **CONFIRMED** | Local paper TeX gives T=2, k=3, 32 envs, temp .3, 1 epoch at `ext/ctrl_rl/arXiv-2106.02193v2/appendix.tex:104-128`; official parser defaults differ at `ext/ctrl_public/train_ppo.py:33-58`; current DataSphere profile is 16 envs while V100 is 64 in `datasphere/native/families.json:754-821`. | Record a paper↔code conflict. Trace the continuous Door action/window path and predeclare a paper-target or released-code-target arm; changing knobs remains **NEEDS MEASUREMENT**. Do not generalize “current 64” beyond V100. |

## 3. Specific cross-cutting recommendations

| Review 18 claim/recommendation | Status | Evidence and closure |
|---|---|---|
| The current one-dimensional mechanism groups incorrectly call DrQ-v2, SVEA, SGQN, DrQ, RAD, and SODA all “off-policy SAC.” | **CONFIRMED** | `notes/DECISION-SHEET.md:953-978` currently contains that grouping, while local code shows DrQ-v2’s DDPG-style path (`RL-ViGen-upstream/algos/drqv2.py:124-204`), and SVEA’s DrQ-v2-style actor/Q path (`RL-ViGen-upstream/algos/svea.py:165-320`). | Replace the reporting taxonomy with orthogonal `rl_backbone/optimizer` and `generalization_mechanism` fields. This is a real documentation/analysis defect, not a reason to alter algorithms. |
| Remove “best-in-group versus best-in-other-group” from primary statistical comparisons because it is post-selection. | **ALREADY ADDRESSED** | The operational protocol already makes endpoint primary, trajectory descriptive, and forbids a selected-best column (`docs/EVAL-PROTOCOL.md:21-30`; `notes/DECISION-SHEET.md:1-7,1324-1331`). The mechanism-group row still describes planned comparisons, so the review’s warning is useful for final analysis wording but does not identify a missing endpoint rule. | Keep all fixed baselines in the primary matrix. If group winners are shown, label them descriptive/post-selection and never use them as the primary inferential contrast. |
| Reverse Places365 from validation to the original train split for maximal source fidelity. | **PARTLY CONFIRMED** | The live patch changes `use_val=False` to `use_val=True` (`datasphere/native/configure_places365_val.py:33-35`); the Decision Sheet explicitly identifies this as learning-affecting and chooses validation as the operational default (`notes/DECISION-SHEET.md:818-842`). The source-fidelity objection is valid; “reverse” is not an unconditional conclusion because the project has deliberately chosen a common fixed split. | Keep validation for the current declared default unless published-source parity is the target. If reversed, rerun SVEA/SGQN/SODA and treat it as a new variant; do not claim the split is immaterial without a sensitivity measurement. |
| Report replay as “capacity-reduced but behaviorally non-evicting for the predeclared 600k horizon,” not fully faithful. | **PARTLY CONFIRMED** | The behavior claim is valid only for a capacity at least as large as the executed frame horizon. Current normal production RL-ViGen is 300k (`datasphere/native/families.json:100-105`), while 620k is a V100 override (`:25-32`); the primary reconciliation explicitly says 300k neutrality is not empirically shown (`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md:120-123`). | Retain host-qualified wording and effective capacity in each row. A 620k non-eviction claim must not be attached to the ordinary DataSphere profile. |
| ALDA can expose both a 500k source-horizon and 600k common-budget result from retained checkpoints. | **NEEDS MEASUREMENT** | The current source-style spec uses 500k while production templating can pass 600k; this is a valid construction in principle, but no final retained 500k/600k production checkpoint evidence exists in the current tree. | Predeclare both outputs if the budget is chosen; ensure the 500k checkpoint is actually retained and evaluated under the same estimator before reporting. |
| Continuous Gaussian clipping/raw-action treatment across IDAAC, PPG, IBAC-SNI, and CTRL is a real scientific seam; do not replace it casually with tanh. | **ALREADY ADDRESSED** | The primary reconciliation marks continuous heads as necessary adaptations (`:78-79,233`), and review 17 already records raw/applied action diagnostics and the no-speculative-patch rule. | Keep raw and executed actions plus clip rates in records. A distribution change is a new method variant and requires a source/effect trace. |
| Endpoint-as-primary, full intermediate records, fixed scenes, three seed-level values, no p-values, no pseudo-replication, and no strict rank ordering at n=3 are sound. | **ALREADY ADDRESSED** | `docs/EVAL-PROTOCOL.md:21-30,133-147,223-246`; `notes/DECISION-SHEET.md:1308-1331`; and retained-record policy already implement these principles. | Preserve them in final reporting. Review 18 adds no new measurement requirement here. |
| The revised time-limit statement should say bootstrapping differs across methods, not that nine methods are systematically disadvantaged. | **ALREADY ADDRESSED** | The project explicitly revised the earlier overclaim in `notes/DECISION-SHEET.md:406-413`; the primary reconciliation repeats the cautious formulation. | Do not resurrect the withdrawn causal claim. A controlled truncation ablation remains optional, not a production blocker. |
| The source-precedence policy should be formalized: Door task from RL-ViGen; method machinery from original source; task-specific source values over generic defaults; paper/code disagreements remain conflicts; behavioral equivalence names its axis. | **PARTLY CONFIRMED** | The principles are consistent with the primary reconciliation and blueprint, but they are not currently a single authoritative policy object. The blueprint already has the needed response schema (`notes/EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:234-283`). | Encode the policy in the review/source-resolution manifest and final report template. Do not use it to erase existing paper↔code conflicts. |

## 4. Provenance and artifact claims

| Review 18 claim/recommendation | Status | Evidence and closure |
|---|---|---|
| Extend `planned-source-resolution.json` with `variant_identity`, fidelity target, paper/code/benchmark/target/effective values, conflict, adaptation, behavioral-equivalence scope, and upstream revision. | **CONFIRMED** | These fields directly fill a real granularity gap in the existing blueprint. The current blueprint requires source/current citations and effective values (`EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:193-207,239-283`) but does not name all of the proposed dimensions. | Add them when implementing the artifact package. This is a package/schema task, not a justification for changing current runs. |
| Add paper source archives/TeX as first-class review evidence. | **ALREADY ADDRESSED** | The blueprint includes relevant `ext` papers and official source closures (`EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:127-183`), and the local CTRL TeX is already the decisive source used here. | Preserve TeX/source where present; record absent material explicitly. |
| The IBAC-SNI paper index is wrong: `paper_1901.10902.pdf` is not IBAC-SNI. | **CONFIRMED** | `pdftotext` of `ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf`, page 1, says “INFOBOT: Transfer and Exploration via the Information Bottleneck” and `arXiv:1901.10902v5`. The local file is not an IBAC-SNI primary paper despite its directory/name. | Obtain/copy the correct IBAC-SNI primary material into the source closure, update the index and hashes, and mark the old file as unrelated/misindexed. Rebuild any external artifact afterward. Until then, IBAC-SNI’s primary-paper citation is **not clean**. |
| The external corpus contains unrelated/wrong SGQN, CTRL, and IDAAC material that should be excluded but manifest-recorded. | **NEEDS MEASUREMENT** | The exclusion principle is correct and already required by `EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:90-105,285-283`; Review 18 did not provide live relative paths that can be checked here, and this triage did not treat names inside an archive as proof of irrelevance. | During artifact construction, classify each candidate by exact path/content and record every exclusion. Do not delete or silently omit any file in the current tree. |
| Review 18’s positive assessment of the artifact blueprint means the package is ready. | **CONTRADICTED** | The blueprint itself lists unresolved builder defects and missing source-closure/effective-config behavior (`EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md:329-397`); the builder task is separate from this triage. | Treat the blueprint as design input, not as a completed artifact or production-readiness certificate. |

## 5. What Review 18 cannot generalize

These limits are admitted by Review 18 itself and matter for how its conclusions may be used:

1. It did not inspect the live `runnable/**`, `families.json`, patches, or `ext/**` tree. Therefore
   its claims about current effective argv, active branches, host profiles, checkpoint delivery,
   source closures, and line-level implementation state cannot substitute for the local evidence
   cited above.
2. It ran no training, smoke tests, evaluator, renderer, full suite, or remote job. “Strongest,”
   “good method resemblance,” “source-shaped,” and “will show true performance” are static
   judgments, not competence, numerical fidelity, or evaluator-validity findings.
3. It did not establish that an IDAAC/PPG/CTRL variant learns Door, that a source-informed arm is
   behaviorally equivalent, or that a changed Places split/replay capacity changes rankings.
4. It did not resolve the PPG continuous-control source gap. The 1×2048/stack3 prescription is
   traceable to the IDAAC DMC comparator, not to the PPG paper’s original Procgen source.
5. It did not resolve CTRL paper-versus-official-code precedence, nor did it trace the current
   continuous action path end to end. Those remain source-target and empirical questions.
6. It did not establish that CoinRun’s IBAC-SNI `nr-samples=12`, latent width, L2, or UDA map
   meaningfully to the current PyTorch continuous Door head. Those are adaptation experiments,
   not automatic porting instructions.
7. It did not independently validate the review’s claim that the supplied corpus contains each
   named unrelated document. The exclusion rule is right; exact exclusions require a manifest
   pass over the actual files.
8. It did not inspect every PDF/source archive line-by-line, especially PPG, CURL, and SODA, and
   reports intermittent OpenReview access. Its source claims in those areas should remain
   secondary until matched to the local primary closure.

Consequently, Review 18 should drive provenance repair, lineage naming, and the bounded design
work listed below. Its admitted notes-only scope limits it as a runtime certification, not as
evidence that the underlying source-fidelity risks are optional.

## 6. Dependency-ordered closure actions

1. **Repair IBAC-SNI source provenance first.** Replace or relabel the misindexed InfoBot PDF,
   add the correct primary material, and update source hashes before external packaging.
2. **Make target identity explicit in the source-resolution schema:** benchmark vs method vs
   adaptation, lineage/variant name, paper/code/benchmark/effective values, and equivalence axis.
3. **Correct the comparison taxonomy** so backbone/optimizer is separate from generalization
   mechanism; retain the fixed endpoint matrix and no selected-best primary column.
4. **Resolve documentation-level effective values:** SGQN composed Door overrides, ALDA 500k vs
   600k, host-qualified replay capacity, Places split, and lineage-qualified names.
5. **Keep IDAAC-C, PPG-DMC-reference, IBAC CoinRun-lineage, and CTRL paper/code profiles as
   labelled alternatives until the project’s predeclared rule and bounded measurements settle
   them. Do not let an external reviewer’s preferred source target silently replace the current
   arm.
6. **Only after those choices, build the external artifact** with exact inclusion/exclusion
   manifests, source revisions, effective configurations, and the review-17/review-18 triage
   cross-references.

Review 18 therefore identifies one immediate provenance blocker (the IBAC-SNI paper entry), several
documentation/schema improvements, and several genuine measurement/design questions. It does not
show that the existing training/evaluation code is numerically invalid, nor that any proposed
variant should be promoted without a predeclared target and evidence.
