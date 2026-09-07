I reviewed this as a source-fidelity study rather than as a question of whether the code runs. I did not launch training, tests, remote jobs, or production commands. I inspected the three aggregate documents, inventoried the supplied paper archive, inspected selected TeX/source material where it resolved a real ambiguity, and independently checked public upstream repositories/publication material for several of the highest-risk cases. The important limitation is exactly the one you noted: I do not have your live `runnable/**`, `families.json`, patches, or `ext/**` trees, so I cannot independently certify that the aggregate documents describe the present effective tree. Your reconciliation itself correctly says implementation is authoritative for what runs, paper for what the authors specify, and RL-ViGen for the Door protocol rather than unrelated algorithm hyperparameters. 

My overall assessment is that the project is substantially more rigorous than a normal “ported 12 baselines” study. The main remaining scientific problems are not generic implementation sloppiness. They are provenance-definition problems: in several places the project still conflates “faithful to RL-ViGen's implementation,” “faithful to the original method,” and “a defensible Door adaptation.” Those are three different targets. The current five-category classification system is good, but the object being classified needs one more dimension: fidelity *to what*. 

## The most important correction: use two fidelity axes

For every baseline I would freeze two separate identities:

**Benchmark fidelity:** does this reproduce the baseline as RL-ViGen defines/runs it on Door?

**Method fidelity:** does this preserve the original paper/code's algorithm, optimizer/backbone, hyperparameters and preprocessing as far as Door permits?

Then separately record **necessary Door adaptations** and **project-wide measurement choices**.

This matters much more than wording. For example, a baseline can be an excellent reproduction of *RL-ViGen-SVEA* while simultaneously being a material variant of original SVEA. Calling that simply “SVEA — exact source match” obscures a genuine fact about the experiment.

The RL-ViGen supplement gives a clear benchmark recipe: 84×84, stack 3, \(\gamma=.99\), action repeat 1 on Robosuite, DrQ \(n=1\) and otherwise \(n=3\), and a replay capacity of \(10^7\). Door is 600k frames at lr \(10^{-4}\); its SGQN values are quantile .9, critic weight .7, auxiliary lr \(8\times10^{-5}\).  Those are benchmark-source values, even when they differ from an algorithm's original DMC publication.

### Baseline-by-baseline disposition I would use

| Baseline | My source-fidelity judgment | What I would freeze / change |
|---|---|---|
| **DrQ-v2** | **Strongest case.** The method mechanism is very close to original DrQ-v2; Door necessarily changes action repeat/environment/evaluation. Your reconciliation gets this basically right.  | Keep the RL-ViGen implementation as primary. Distinguish three replay values in provenance: original DrQ-v2 ≈1M, RL-ViGen =10M, project production value if 620k. A 620k buffer that never evicts during a 600k run can be called **behaviorally no-eviction-equivalent for this horizon**, not an “exact source match.” |
| **DrQ** | **Benchmark-faithful, original-hyperparameter variant.** Core SAC/DrQ path appears well preserved, but native84, batch256/lr1e-4 etc. are RL-ViGen choices rather than original DrQ DMC settings.  | Current strategy is defensible. Call it “DrQ under the RL-ViGen Door recipe,” not “original DrQ hyperparameters.” |
| **SVEA** | **Important downgrade needed.** The SVEA loss idea may be preserved, but RL-ViGen's active SVEA actor/critic is DrQ-v2-like: scheduled Gaussian exploration and actor loss \(-Q\), with no SAC entropy/temperature term in the implementation I inspected.  Original SVEA is SAC-based. Your current reconciliation calling the core mechanism an `EXACT SOURCE MATCH` is too generous.  | Keep it if reproducing RL-ViGen, but identify it explicitly as **RL-ViGen-SVEA**: SVEA augmentation/critic regularization on RL-ViGen's DrQ-v2-style backbone. Do not imply optimizer/backbone fidelity to the original SVEA paper. |
| **SGQN** | **Same basic issue as SVEA.** RL-ViGen's `SGQNAgent` explicitly inherits `DrQV2Agent`; it is therefore a valid SGQN-style method instantiation, but not the original paper's SAC realization.  | Keep **RL-ViGen-SGQN** for benchmark fidelity. Make Door's q=.9, critic=.7, aux-lr=8e-5 a hard effective-config check; don't trust generic YAML values.  |
| **CURL** | **Most explicit RL-ViGen variant.** RL-ViGen states in the paper that it replaces CURL's two Polyak-coupled encoders with a single encoder; its code also has `CURLAgent(DrQV2Agent)`.   So “exact mechanism match” in the reconciliation is too strong.  | Keep as **RL-ViGen-CURL** if benchmark replication is primary. If you ever run original-CURL-as-ported, make it a distinct variant; don't silently swap it into the same row. |
| **RAD** | **Good method resemblance, weaker provenance than stated.** You are using Hansen's DMC Generalization Benchmark standardized RAD implementation, not Misha Laskin et al.'s original RAD repository. That is a strong independent reproduction, but not “official RAD source.” The reconciliation already records sizable optimizer/batch differences.  | Rename provenance internally to **DMCGB-RAD**. Keep the 100→84 crop: that is a real method/preprocessing requirement, not cosmetic harmonization. For maximal original fidelity, source method-level values from original RAD unless DMCGB's differences are intentionally part of your comparison. |
| **SODA** | **One of the strongest added baselines.** DMCGB is the authors' source lineage for SODA; mechanism, 100→84 dependence, and auxiliary machinery are appropriately preserved.  | Keep. Main deviations should be Door/action-repeat, 600k versus source horizon, evaluation protocol, and Places365 split. |
| **ALDA** | **Strong algorithmic fidelity, necessary task adaptation.** The latent structure, β=100, 12×12 representation, stack3 and main optimization choices look source-backed.  | Keep source UTD≈1 as the fidelity primary. Do not turn the old retired-port 0.25 stability fix into “the faithful ALDA value”; your own A27 correctly recognizes that the evidence is a task-specific stability prior, not source fidelity.  Resolve the apparent 500k-vs-600k ambiguity before freeze. An elegant solution is to train through 600k but predeclare/report the retained 500k checkpoint as a source-horizon slice as well as the common 600k endpoint. |
| **IDAAC** | **Current Procgen-shaped port should not be the primary fidelity target.** IDAAC has unusually strong applicable evidence: the authors themselves give a DMC continuous-control recipe. It uses stack3, 1 process, 2048 steps, 32 minibatches, 10 PPO epochs, entropy0, lr3e-4, \(\gamma=.99,\lambda=.95\), linear LR decay, and IDAAC-specific \(E_V=9,N_\pi=32,\alpha_d=.1,\alpha_i=.1\).  Your latest Decision Sheet eventually reconstructs this correctly.  | **IDAAC-C should be the source-fidelity primary regardless of whether it scores better on Door.** Implement linear LR decay if feasible; it is a real stated source setting. The current one-stack/4×256 configuration is useful as `IDAAC-ProcgenPort`/C1, not as the baseline that replaces C when C performs poorly. |
| **PPG** | **No unique original continuous-control PPG exists.** This needs more careful wording than the current Decision Sheet. The continuous-control recipe you are using comes from the *IDAAC authors' DMC experiment*, where PPG was a comparator—not from the original PPG authors. That supplement indeed uses stack3, 1×2048, 32 minibatches, entropy0, lr3e-4, \(\gamma=.99\), linear decay, plus \(N_\pi=32,E_\pi=1,E_V=1,E_{aux}=6,\beta_{clone}=1\).  | I would call this **PPG-DMC-reference Door port**, not “original continuous-control PPG.” If you adopt that reference, use its actual geometry: **1×2048 and stack3**, not 8×256/stack1. 8×256 preserves 2048 samples/update and the interaction count per phasic cycle, but it does *not* preserve rollout geometry or GAE truncation. If instead maximal original-PPG provenance is paramount, preserve original PPG-specific constants and identify continuous-policy choices as authored adaptations. |
| **IBAC-SNI** | **Irreducibly composite unless you implement substantially more.** Your latest assessment is right: CoinRun visual IMPALA + PyTorch/GridWorld bottleneck/trainer + authored Gaussian Door head is not a single original source branch.  | Commit explicitly to a **visual/CoinRun-lineage Door port**. If fidelity budget permits, closing `nr-samples=12` and latent256 is more valuable than tweaking peripheral knobs. Continuous action remains a necessary adaptation. Also fix the source-index arXiv identifier: the canonical IBAC-SNI preprint is **1910.12911**, not `1901.10902`.  |
| **CTRL** | **Do not “fix” cluster_len 10→2 yet. There is a real paper/code conflict.** Your paper table says PPO epoch1, 32 envs, k=3, T=2; the released official code defaults to epoch3, 64 envs, k=1, `cluster_len=10`.  The upstream code I independently inspected confirms those released defaults.  | Upgrade this from “current value conflicts with source” to **PAPER↔OFFICIAL-CODE CONFLICT**. Determine which provenance you intend to reproduce. Until that is established, current T=10 is no less source-backed than T=2. Continuous Box/Gaussian handling remains a separate necessary adaptation. |

## Three places where I would change the current project's reasoning, not merely its labels

First, the **IDAAC/PPG variant-selection rule should not use Door performance to decide what the baseline is**. Your current proposals say, roughly, “if the source-informed C variant reaches competence at least as well as P, use C; if C fails, retain P as primary.” That is written explicitly for IDAAC and PPG.  

Predeclaring that rule prevents hidden cherry-picking, but it does not solve the deeper fidelity problem: the benchmark result is still choosing the algorithm definition. If the declared purpose is source fidelity, source evidence should determine the primary before observing Door performance. A faithful source-informed port that fails Door has produced a scientifically valid negative result. The more successful adaptation can still be reported as an alternate. Otherwise a reader cannot distinguish “IDAAC generalized poorly” from “we replaced IDAAC with whichever of two adaptations learned Door.”

IDAAC is straightforward because its own authors supply the applicable continuous-control recipe. PPG is different: the DMC recipe is a published third-party adaptation by Raileanu and Fergus, not an OpenAI PPG source. I would correct any project text calling that “the authors' own continuous-control design.” It isn't. 

Second, **A25's mechanism taxonomy is currently factually wrong**. It groups `drqv2`, `svea`, `sgqn`, `drq`, `rad`, and `soda` as “off-policy SAC” and says they all share a SAC backbone.  DrQ-v2 is specifically DDPG-style; RL-ViGen's SGQN inherits DrQ-v2, and its SVEA implementation is likewise DrQ-v2-style in its policy/Q optimization. CURL also inherits DrQ-v2 in RL-ViGen.   

I would replace the one-dimensional “mechanism group” with two orthogonal fields: **RL backbone/optimizer** and **generalization mechanism**. That immediately makes the study more legible. For example, `RL-ViGen-SGQN` = DrQ-v2-style backbone + saliency/attribution regularization; DrQ = SAC + random-shift DrQ; SODA = SAC + soft augmentation representation objective; IDAAC = PPO-family + decoupling/adversarial invariance.

I would also remove “best-in-group versus best-in-other-group” from anything described as a primary statistical comparison. Choosing the “best” from noisy \(n=3\) observations and then comparing winners is post-selection, even if you predeclared that you would select winners. Keep it as descriptive summary or predeclare fixed algorithm-to-algorithm contrasts. Your own seed analysis is already appropriately cautious: with three seeds, only very large differences can support meaningful ranking statements. 

Third, I would reverse the current default on the **Places365 validation split** if “most faithful to originals” is the objective. Your project deliberately patches the DMCGB loader from its train split to the validation split for SVEA/SGQN/SODA, and correctly recognizes this as learning-affecting rather than infrastructural.  Using the same validation set for all three does not establish that rankings are unaffected; it only makes the deviation common. If storage/network access permits, original `use_val=False` is the fidelity choice. If you retain validation for operational reasons, it should remain a prominent variant flag, not a minor reproducibility convenience.

## PPG deserves one additional correction

Your A26 observation is useful but slightly overclaimed. Eight environments × 256 steps × \(N_\pi=32\) gives the same 65,536 interactions per auxiliary phase as one environment × 2048 steps × 32, so it correctly preserves one **global interaction cadence**. 

It does not reproduce the continuous-control rollout geometry.

With 8×256, GAE/rollout cuts occur every 256 environment steps in eight simultaneous trajectories. With 1×2048, the collection process is one long stream of 2048 steps, containing several Door episodes because Door's horizon is 500. That changes bootstrap boundaries at rollout truncation, temporal correlation, the distribution of per-update episode phases, and potentially normalization statistics. Calling 8×256 “exactly the continuous-control design point” therefore goes too far. “Matches samples/update and auxiliary interaction cadence” is accurate.

The same point is why environment count should never be treated as a mere throughput knob for synchronous on-policy algorithms. Your project has already reached that conclusion independently. 

## The continuous-action clipping seam is real, and your current treatment is correct

I agree with the project's decision not to casually replace the Gaussian policies of IDAAC/IBAC-SNI/CTRL with tanh-squashed distributions. Your trace found that these authored continuous heads can sample unbounded actions, store the raw sample for the PPO likelihood, while Robosuite clips before applying the action. That means the update can be conditioned on an action that was not literally executed when clipping occurs.

This is a scientifically important adaptation seam, but changing it unilaterally would be another algorithm. The right current response is exactly what your project converged to: measure per-coordinate/action clip fraction, monitor log-std, retain raw/applied action semantics in provenance, and only promote it to a defect if clipping is substantial. The initial analysis also correctly generalized the issue beyond CTRL to IDAAC and IBAC-SNI rather than treating it as a one-off port bug. 

## Replay capacity: change the language, not necessarily the value

RL-ViGen's common table says replay size \(10^7\), not approximately 1M.  The original DrQ-v2 paper/code uses a different capacity, so there are actually three provenance values here: algorithm source, RL-ViGen benchmark, project production.

Your later 620k reasoning is sensible: if the production run contains no more than roughly 600k transitions, 620k means no sampled transition is ever evicted. At that horizon, a 620k and 10M buffer can have the same *contents* at every learning update modulo storage implementation. The Decision Sheet recognizes that 620k versus 1M is behaviorally identical for eviction at 600k. 

I would simply stop calling 620k “fully faithful.” Call it:

**capacity-reduced, behaviorally equivalent with respect to replay eviction for the predeclared 600k Door horizon.**

That is a stronger claim because it says exactly what has and has not been established.

## ALDA and common budgets

There is a live-document ambiguity I cannot resolve without your actual effective tree. The reconciliation says ALDA's current source/spec is 500k and matches the paper's 500k.  Elsewhere the Decision Sheet discusses all `rad/soda/alda` at a common 600k budget. 

I would resolve this before source freeze even if it is only documentation drift. For a twelve-method Door comparison, I prefer a common 600k resource horizon over giving ALDA a unique shorter primary horizon. Because you retain 50k checkpoints, you can get both quantities without another training run: predeclare ALDA's **500k source-horizon result** and **600k common-budget result**. The same technique is useful for any other method whose canonical source budget has a checkpoint inside the 600k trajectory. Neither should be selected after seeing which is better.

## Statistical/evaluation design: mostly strong

Several decisions here are exactly what I would want in a serious baseline paper. Treating training seed as the only outer replicate and scenes as a fixed evaluation grid avoids the extremely common mistake of turning hundreds of evaluation episodes into pseudo-independent training replicates. Showing the three seed-level values rather than decorating \(n=3\) with p-values is appropriate. Shared evaluation placements can denoise within-policy regime comparisons, but do not turn equal seed integers across algorithms into paired training replicates. 

Endpoint-as-primary, retained trajectories as descriptive evidence, and no “best checkpoint” column are also good choices. So is the crash/missingness policy: rerun the same failed seed, do not choose replacements after observing results, and never silently convert an \(n=2\) method into an \(n=3\) row. 

The time-limit treatment is now appropriately modest. The original claim that terminal-at-horizon methods were systematically disadvantaged was not established; the revised statement—that three methods bootstrap while nine terminate, therefore learning targets differ near the horizon—is the right one unless you actually run a controlled ablation. 

Your rich raw-record policy is particularly valuable. Keeping episode returns, success, diagnostics, placement seeds and episode IDs means future aggregation choices do not require rerunning GPUs.  I would retain success, raw return, train/OOD delta, ordinary ratio and floor-adjusted ratio exactly as you now intend, with any “headline” explicitly presentation-level rather than a data-retention decision.

At \(n=3\), however, I would avoid publishing a strict 1–12 rank ordering except as descriptive. Your own resolving-power analysis already supports this: claims should be “large separation / approximate generalization magnitude,” not “method A is statistically better than method B” for ordinary-sized differences. 

## Source precedence I would formally freeze

This is the one policy I think should become explicit before you settle any more method-specific forks:

1. For **task/environment/evaluation**, RL-ViGen Door is authoritative.
2. For **method-defining algorithmic machinery**, the method's original publication plus official implementation are authoritative.
3. For **task-specific values**, a source's explicit task/domain table beats a generic parser/YAML default. RL-ViGen Door's SGQN q=.9/.7/8e-5 is a good example.
4. For a Procgen-original method with no original continuous-control implementation, preserve original **method-specific** constants first; use the strongest published continuous-control port for generic PPO/action-domain choices only with explicit secondary provenance.
5. If paper and official implementation disagree, record a **paper↔code conflict**; do not silently declare either one “the source.” CTRL is currently the clearest example.
6. Benchmark performance must evaluate a frozen variant, not choose which variant earns the unqualified method name.
7. “Behaviorally equivalent” must always state the axis of equivalence—e.g. replay eviction—not stand in for nominal source equality.

That policy resolves most of the current ambiguity without requiring a single new training run.

## Review of the three project documents themselves

`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` has the right intellectual structure. Its distinction among exact match, contextual variant, necessary adaptation, conflict and unspecified is useful, and its statement that the benchmark should control the Door protocol rather than unrelated method hyperparameters is exactly right.  The main correction is that several `EXACT SOURCE MATCH` judgments are currently too broad because they judge the retained auxiliary mechanism while ignoring a changed RL backbone—especially RL-ViGen SVEA and CURL.

`DECISION-SHEET.md` contains very good scientific self-correction. The IDAAC frame-stack episode is illustrative: an initially plausible theoretical argument was rechecked against the actual supplement and reversed when the authors' DMC experiment directly contradicted it.  The weakness is structural: it is chronological, so obsolete conclusions and their corrections coexist hundreds of lines apart. It is excellent research history and a dangerous effective-config authority. A reviewer should never have to infer “latest wins” from 1,600 lines.

`EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md` is very strong. In particular, separating “SOURCE-FIDELITY REVIEW NOW” from “FINAL PRODUCTION-READINESS REVIEW LATER” prevents source inspection from being laundered into claims about runtime/renderer/checkpoint integrity.  Its insistence that absence cannot be indistinguishable from deletion, and that dirty paths/provenance survive into the review artifact, is also correct. 

I would extend its `planned-source-resolution.json` rather than invent another document. It already asks for exact argv, environment, packages, rollout/update accounting, transforms and source path/line for every value.  Add these fields: `variant_identity`, `fidelity_target = benchmark|method|adaptation`, `paper_value`, `official_code_value`, `benchmark_value`, `target_value`, `effective_value`, `paper_code_conflict`, `necessary_domain_adaptation`, `behavioral_equivalence_scope`, and the exact upstream commit/revision.

I would also add arXiv source archives/TeX as first-class entries under `reference/`, not merely PDFs. That matches your preference and, as CTRL demonstrates, TeX tables can settle ambiguities more reliably than OCR/PDF extraction.

## One artifact-level source hygiene correction

The current primary-source index names the IBAC-SNI local paper as `paper_1901.10902.pdf`.  The actual IBAC-SNI paper is arXiv **1910.12911**.  Even if the local PDF bytes are the correct paper and only the filename is wrong, fix this before generating provenance manifests; a wrong identifier is exactly the sort of innocuous-looking defect that propagates into citations and source hashes.

The ZIP also contains material that is clearly not part of these twelve—for example the explicitly marked “WRONG-SGQN” paper, the unrelated 2025 “CTRL-Critic-Training-RL” paper, and unrelated material inside the IDAAC directory. Your blueprint's exclusion-manifest philosophy is appropriate here: exclude those from the primary-source closure but record that they were present, rather than letting folder location imply relevance.

## What I would consider blocking before a scientific source freeze

I would not block on more generic smoke tests. I would block on the following scientific definitions being settled in the source manifest: the RL-ViGen-vs-original identity of SVEA/SGQN/CURL; Door-specific SGQN's effective .9/.7/8e-5 values; IDAAC-C as the source-continuous target and whether linear decay is implemented; PPG's exact provenance target and the 1×2048/stack3 versus 8×256/stack1 distinction; IBAC-SNI's declared lineage and remaining 12-sample/latent-width gaps; CTRL's publication-versus-code target; Places365 train versus validation; and ALDA's 500k/600k effective budget.

I would **not** block source freeze merely because some faithful method learns poorly. That is an experimental result, not a fidelity defect.

The safest eventual paper-level framing is something close to:

**Five benchmark-native RL-ViGen Door baselines reproduced according to RL-ViGen's released implementations and Door recipe, plus seven source-informed, explicitly adapted Door ports. Original-method, benchmark, and adaptation provenance are reported separately for every baseline.**

That claim is both stronger and more defensible than saying “twelve faithful reproductions,” because for PPG, IBAC-SNI, CTRL, and even RL-ViGen's own CURL/SVEA/SGQN variants, literal original-method reproduction is not what the experiment actually is.

### What I did and did not inspect

I read the three supplied `.md` documents extensively, including their late revisions rather than stopping at their opening summaries. I inventoried `papers-sorted.zip` and used the embedded source/TeX where it was especially valuable—for CTRL, in particular. I independently inspected public RL-ViGen source for CURL/SVEA/SGQN and the released CTRL code, and checked publication material for RL-ViGen, IDAAC/PPG's DMC comparator setup, and IBAC-SNI.

I did **not** have your live project source/config tree, so I could not independently recompute final effective argv or verify that the line references in the reconciliation still match the tree. I did **not** exhaustively read every PDF and every source tarball in the ZIP line-by-line; PPG, CURL and SODA in particular do not appear to have complete canonical primary-source packages in the supplied ZIP, so those portions rely more heavily on the aggregate audit and public upstream material. I also did not use every OpenReview attachment: OpenReview's attachment/interface access was intermittently blocked during the earlier source-gathering pass, although several corresponding PDFs were available directly in your supplied archive or through publication sites. No training, test suite, renderer, or live infrastructure was launched.
