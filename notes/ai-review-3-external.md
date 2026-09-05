The additional documents change several conclusions, but the production decision remains **no-go**.

The main difference is that I can now separate three categories: defects caused by the incomplete ZIP, defects that the real-tree review has actually resolved, and defects that remain live in the working tree. The triage itself explicitly says it was read-only and did not fix the confirmed findings, so “confirmed” should not be read as “closed.” 

### Corrections to my previous review

I withdraw the earlier claims that the real project is missing its production source and that its normal test suite has 28 collection failures. According to the real-tree triage, those were artifacts of the ZIP: the working tree contains the missing `rlgen`, IBAC-SNI sources, production schedule, source locks, etc.; its full suite had one remaining deliberate internal-link failure rather than 28 collection errors. 

I would still not call that test state fully release-clean. A deliberately failing test should be made an explicit `xfail`/separate audit or fixed. A production culture where “red is expected” makes future real regressions easier to ignore. But it is no longer the severe failure I originally described.

The biggest IBAC conditional bug is also cleared. The real source trace says the sampled Gaussian action is stored raw, that same raw sample is what PPO later scores, and clipping does not flow back into the stored action. That makes the PPO importance ratio mathematically consistent. 

I would nevertheless change:

```python
env.step(action.cpu().numpy())
```

to something equivalent to:

```python
env.step(action.detach().cpu().numpy().copy())
```

because on CPU the NumPy array can alias tensor storage. The triage correctly identifies that as a latent mutation hazard. This is hardening, not a fundamental PPO defect.

`--append` also exists, so my statement that every restart necessarily destroys the prefix was too strong. What remains missing is true resume/skip-completed behavior. 

And RAD's evaluator has now been exercised successfully. ALDA is the remaining unexercised family. 

---

## What is still release-blocking

The most important remaining defects are now unusually well established because the project's second review independently reproduced them.

| Area                                     | Current status                                                                      |                      My severity |
| ---------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------: |
| Immutable source snapshot                | Still no single immutable commit meaning “code that generated the reported results” |                           **P0** |
| Result metadata                          | Known false `eval_policy_mode` values for PPG/IBAC/CTRL                             |                           **P0** |
| Checkpoint provenance                    | Common-grid records lack checkpoint/content hash and effective config               |                           **P0** |
| Evaluator reconciliation                 | Most families still not reconciled against their native evaluator                   |                           **P0** |
| Regime verification                      | Real jobs produced 16 abstentions; evaluator is fail-open                           |                           **P0** |
| Cross-method RNG pairing                 | Native probe consumes RNG while common grid does not                                |      **P0 for paired inference** |
| External RL-ViGen anchor                 | Still not established before fleet                                                  |                           **P0** |
| Statistical protocol                     | Now drafted, but not merged/frozen and needs corrections below                      |                           **P0** |
| Checkpoint-selection protocol            | Now drafted, but not frozen and needs corrections below                             |                           **P0** |
| ALDA resources/evaluator                 | Wrong tier OOMed; correct-tier preflight was still outstanding in these docs        |                           **P0** |
| Env/temp cleanup                         | Confirmed resource leaks                                                            |                               P1 |
| CPU evaluator default                    | Contradicts the project's own environment-validity finding                          |         P1/P0 depending launcher |
| Dependency/container provenance          | Still absent                                                                        |   P1/P0 for publication artifact |
| IBAC policy-scale diagnostics            | Finiteness check does not detect a finite-but-useless policy                        |                               P1 |
| Old performance-selected scene reporting | Confirmed biased                                                                    | **Must not enter final results** |

The confirmation for the evaluator/metadata/provenance defects is particularly strong: the real-tree triage explicitly verifies wrong policy-mode metadata, missing snapshot hashes, environment leaks, temp-directory leaks, the CPU default, stale audit instrumentation, stale protocol text, environment reproducibility gaps, performance-selected scenes, and the inadequate policy-scale gate. 

The immutable-snapshot problem becomes more serious, not less, given the new files. Both agent-coordination documents explicitly warn that current file claims are provisional because the tree is being edited concurrently.  

Before the first production result is accepted, I would want a single frozen object containing at minimum:

`git commit + nested repo commits + effective config + checkpoint SHA256 + evaluator commit + container/image digest + CUDA/PyTorch/JAX/MuJoCo/robosuite versions + command line + seeds`.

A filename like `seed1_600k.pt` is not provenance.

---

# The proposed inference protocol needs revision

The proposal identifies the right fundamental problem: 600 episode rows are absolutely not 600 independent replicates. One learned training seed generates results across all scenes, so training seed is the outer stochastic unit. The document explicitly recognizes this and proposes `n=3` at that level.

That is directionally correct and much better than episode-level uncertainty. Few-run uncertainty is a major RL-evaluation issue; Agarwal et al. likewise emphasize interval estimates rather than trusting point estimates from a handful of runs. ([arXiv][1])

But I would change several details before merging it.

### 1. `(seed, scene)` is not an independent statistical unit

The proposal says:

> one number per `(baseline, seed, regime, scene)` ... “the smallest unit that is not internally correlated by design.”

That wording is wrong.

For one seed:

$$
\theta_{m,r}
$$

is one learned policy. Its scores on scene 0, scene 1, ..., scene 9 all share that same random trained policy. Therefore those ten scene observations remain correlated.

Use `(seed, scene)` as an **analysis cell**, not as an independent replicate.

For a fixed ten-scene benchmark, I would compute:

$$
Y_{m,r,g,s}
=
\frac1E\sum_e R_{m,r,g,s,e},
$$

then

$$
\bar Y_{m,r,g}
=
\frac1{10}\sum_s Y_{m,r,g,s},
$$

and regard the three

$$
\bar Y_{m,1,g},
\bar Y_{m,2,g},
\bar Y_{m,3,g}
$$

as your three outer replicates.

Scene-level results should absolutely still be shown because visual generalization heterogeneity is scientifically interesting. But do not pretend those ten scene cells turn three trained agents into thirty independent agents.

### 2. Decide whether scenes are fixed or random before specifying the bootstrap

The proposal currently says to bootstrap seeds **and scenes**.

That silently assumes the ten chosen scenes are draws from a larger population of possible RL-ViGen appearances.

Maybe that is your intended estimand. But it might instead be:

> average performance on these ten prescribed benchmark scenes.

Those are different scientific questions.

If the ten scenes are a **fixed benchmark grid**, keep them fixed and resample entire training-seed vectors. In other words, when seed 2 is resampled, bring all ten scene results for seed 2 together. Cluster/bootstrap methods preserve all observations belonging to the resampled outer cluster rather than independently pretending nested observations are fresh replicates. ([DOI][2])

If the target really is a **population of possible visual scenes**, then a hierarchical scene/seed procedure can be justified, but say explicitly what population the ten scenes represent.

Do not let the implementation of `bootstrap()` define the scientific estimand.

### 3. With three training seeds, a nominal “95% CI” needs a warning label

The proposal appropriately rejects p-value theater with \(n=3\).

I agree.

But a bootstrap cannot manufacture independent trained agents either. With three outer clusters, uncertainty about training variation remains severe.

I would show, for every headline value:

* all three seed-level aggregate points,
* their mean,
* their SD/range,
* and, if desired, a clearly labelled seed-cluster/bootstrap interval.

I would not let the CI visually obscure the fact that there are three learned policies.

This is consistent with the motivation behind modern RL evaluation work: better interval procedures help with few-run studies, but they do not make three runs equivalent to thirty. ([arXiv][1])

### 4. The proposed cross-method “pairing” is not yet established

The proposal's precision argument depends on:

> every baseline sees the identical sequence of placements.

But the later real-tree triage explicitly says the current evaluators do **not** preserve that premise: one evaluator performs `reset()+step()` verification and consumes the global NumPy stream while the other deliberately avoids doing so. The triage says this undercuts the paired-comparison claim. 

So no paired analysis should be performed yet.

The proposed fix from the other session is good: validate scene/mode from the first `info` object produced by a step that evaluation was going to take anyway, instead of injecting an additional probe step. That removes the extra RNG consumption and can work through subprocess wrappers. 

For IBAC specifically, attribute traversal is insufficient because mode/scene enter through `RLVIGEN_MODE` and `RLVIGEN_SCENE_ID`; the docs recommend verifying both the requested environment variables and the environment's observed output. 

I would go one step further: **record the actual door-placement parameters or a deterministic placement hash for every episode.**

Then the claim

> A seed-1 scene-4 episode 7 and B seed-1 scene-4 episode 7 saw the same physical placement

is empirically auditable rather than inferred from RNG theory.

### 5. Be careful about what is actually paired

Even once evaluation placements match, “training seed 1” for IBAC and “training seed 1” for DrQ-v2 is not automatically a meaningful paired training replicate.

The algorithms consume RNG differently, use different libraries, have different architectures, and often different rollout structures. Matching the integer `1` does not guarantee common-random-number correlation through training.

You clearly have pairing in:

* regime,
* scene,
* episode placement.

You only have **training-seed pairing** if the experiment deliberately establishes it as a common-random-number block and can defend that interpretation.

Otherwise I would aggregate each method's scenes within each training seed and compare distributions of three independently trained policies, while using common evaluation placements mainly to reduce measurement noise.

### 6. “Not distinguishable from random floor” is underspecified and clashes with the no-p-value rule

The competence section says that a method whose train score is not “distinguishable” from the 1.82 floor gets no retention value.

What does “distinguishable” mean?

* CI lower bound \(>1.82\)?
* mean \(>1.82\)?
* success rate \(>x\)?
* return \(>1.82+\delta\)?
* all three seeds?
* at least two?
* method-level mean?

This must be a deterministic preregistered rule.

I actually prefer a **practical competence threshold** over a significance threshold here, especially with three seeds. For example, whatever task-specific criterion you choose, define it numerically before the fleet starts.

And always report the raw training and OOD scores even when retention is suppressed.

### 7. Do not make retention the primary generalization statistic

The proposal correctly recognizes the denominator problem. A ratio can explode near the random floor.

I would make the primary quantities:

$$
R_{\text{train}},
\qquad
R_{\text{OOD}},
\qquad
\Delta = R_{\text{OOD}}-R_{\text{train}},
$$

plus success rate if success is a meaningful Door metric.

Then retention

$$
\rho = \frac{R_{\text{OOD}}}{R_{\text{train}}}
$$

is secondary and shown only for competent methods.

That makes a failed agent visibly a failed agent rather than converting its denominator pathology into an odd generalization percentage.

If you use log retention,

$$
\log R_{\text{OOD}}-\log R_{\text{train}},
$$

you also need a rule for zero/non-positive returns. “Use log scale” alone is incomplete.

### 8. Freeze the primary outcome

The proposal uses “score” generically.

Before production, explicitly say whether the primary endpoint is:

* shaped episode return,
* task success probability,
* or another metric.

If both return and success are headline outcomes, say so in advance.

Door is particularly vulnerable to a method getting better shaped reward without actually opening the door; your IBAC pilot is already showing why this distinction matters.

### 9. Predefine pairwise comparisons

Twelve algorithms create

$$
\binom{12}{2}=66
$$

possible pairwise comparisons.

Even without p-values, it is easy to look through 66 noisy effect estimates and narrate the attractive ones.

Either specify the small set of primary comparisons before training, or publish the complete pairwise matrix and avoid selectively highlighting only winners.

### 10. Predefine missing-run policy

With three seeds, losing one seed is catastrophic statistically.

State in advance:

* whether a crashed seed is rerun with the identical seed,
* whether replacement seeds are forbidden,
* what happens when one method lacks one scene,
* whether incomplete methods remain in the headline table.

Do not decide this after seeing which seed performed badly.

---

# Checkpoint-selection proposal: good core, but four additions

The basic rule is correct:

> endpoint is the headline.

That is the safest option and should remain the default. The document correctly identifies that choosing the best of ~13 checkpoints using the same eval regime later reported turns test evaluation into validation.

I would tighten it further.

First, “select using train-regime score” is only clean if the data used to select are not subsequently presented as an unbiased estimate of that selected checkpoint's train score.

Suppose checkpoint \(k^\*\) is:

$$
k^\*=\arg\max_k R_{\text{train,val}}(k).
$$

Then reporting that same maximum as `train score = R_train,val(k*)` has winner's-curse optimism.

A rigorous best-checkpoint procedure is:

$$
\text{validation episodes}
\rightarrow
k^\*
\rightarrow
\text{fresh reporting episodes at }k^\*.
$$

The validation set may be a reserved subset of training-regime placements; it does not necessarily require sacrificing an OOD test regime.

Second, candidate checkpoint opportunities must be the same. “Same rule” is not enough if one method has 13 eligible checkpoints and another has 25. More candidates means more opportunity to win by noise. Freeze the target frame stamps and define how a method maps an update boundary onto each stamp.

Third, define whether checkpoint selection is **per seed** or **per method**. Those are different procedures.

Per-seed:

$$
k^\*_{m,r}
$$

simulates early stopping each actual training run.

Method-level:

$$
k^\*_m
$$

uses the three seeds jointly to choose one training horizon for the algorithm.

Endpoint avoids this entire ambiguity.

Fourth, define tie breaking and missing checkpoints.

The easiest scientifically defensible protocol remains:

> **Headline = exact endpoint. Full trajectory = descriptive supplementary result. No “best checkpoint” headline at all.**

That is what I would choose.

---

# IBAC-SNI: revised assessment

The new evidence improves my confidence in the implementation considerably.

The PPO likelihood ratio is apparently correct, as discussed above.

The global `log_std` observation also changes how I view `entropy_coef=0`. The triage adopts the point that state-independent standard deviation means:

$$
H[q(a|z)]
=
\sum_j \log \sigma_j + C,
$$

so the “conditional” entropy does not actually vary with the IB latent \(z\). Therefore removing this entropy term removes less of IBAC's representation-specific mechanism than the name “IBAC entropy” initially suggests. 

I therefore no longer consider “diagnose exactly whether VIB/SNI or PPO update count caused the 0.01 runaway” a prerequisite for the production run.

It is a worthwhile mechanistic ablation, but not a production blocker if you freeze `entropy_coef=0` and clearly call the result a **continuous-action adaptation**.

What remains a production blocker for IBAC is **competence under the final configuration**.

The evidence described so far establishes:

$$
0.01 \Rightarrow \text{scale runaway},
$$

and

$$
0.0 \Rightarrow \text{scale remains controlled early}.
$$

It does not yet establish:

$$
0.0 \Rightarrow \text{learns Door}.
$$

Those are different claims.

Before paying for a 600k × 3 production IBAC run, I still want a pilot of the exact final source/config to cross the project's predeclared competence threshold, or at minimum show a compelling monotonic learning signal at a substantially longer horizon than ~25k.

And I would add these logs to IBAC production:

$$
\text{mean/min/max log\_std},
$$

actual **vector-level raw-action clipping frequency**,

$$
\|a_{\rm raw}-a_{\rm executed}\|,
$$

PPO approximate KL,

clip fraction,

policy loss,

value loss / explained variance,

VIB KL,

clean-vs-noisy policy losses,

gradient norm,

and actual success rate.

The current finiteness gate cannot detect exactly the failure you already experienced: a policy with \(\sigma\approx4.3\) is finite but behaviorally useless. The real-tree audit independently confirms that problem. 

I also would not dismiss the ~93% initial vector saturation just because similar PPO implementations sometimes initialize \(\sigma=1\). The triage correctly softens it from “algorithm bug” to “measurement gap.”  What matters now is measuring what percentage of the actual 7-D Door actions are transformed/clipped during learning.

---

# ALDA is a real operational blocker

The new documents reveal an issue my original review could not know.

The ALDA preflight was SIGKILLed with memory still climbing. The project's own planner says its fixed working set is 15.3 GiB while `gt4.1` offers only 14.5 GiB usable. So that cell physically does not fit the assigned tier. 

The Claude-side record reaches the same diagnosis and says it belongs on `gt4i.1` with 27 GiB usable. 

A controlled same-payload test on the bigger tier was in flight when that document was written. 

Until that passes:

**ALDA is not production-ready, and therefore the twelve-method fleet is not production-ready.**

I would also encode a scheduler invariant:

$$
\text{requested RAM}
\ge
\text{measured fixed peak}
+
\text{explicit safety margin},
$$

rather than relying on a human to notice that the cost model and production schedule disagree.

---

# One additional issue I would add to the project's register

The inference proposal assumes paired placements but the result schema apparently does not record enough information to prove pairing.

I would add a production requirement:

> Every episode result carries an `eval_episode_id` plus the actual initial Door placement state/hash.

That gives you three benefits simultaneously:

1. pairing is provable;
2. accidental RNG-stream divergence is detectable;
3. later reanalysis can pair episode differences without trying to reconstruct RNG state.

Given that RNG-stream asymmetry has already occurred once, I would consider this cheap insurance rather than optional metadata.

---

## Updated production gate

I would approve the fleet only after these are all true:

1. Freeze one immutable source commit and container/dependency digest.
2. Make the complete release test gate green rather than “green except a deliberate failure.”
3. Fix the known false result metadata and stamp checkpoint/config/source provenance into every row.
4. Make regime/scene verification **fail closed**, without extra RNG-consuming steps, and record actual placement identity.
5. Reconcile every evaluator family against a known competent checkpoint; ALDA must complete its correct-tier preflight.
6. Establish the external RL-ViGen anchor.
7. Merge/freeze the statistical protocol with the corrections above: outer unit = training seed, explicit fixed-vs-random scene estimand, fixed primary metric, precise competence rule, missing-run policy, and no episode-IID inference.
8. Freeze endpoint as the headline checkpoint rule; preferably do not publish a selected-best headline.
9. Run the exact final IBAC-SNI `entropy=0` pilot far enough to establish competence and verify policy-scale/clipping diagnostics.
10. Disable the old performance-selected `usable scenes` reporting path for final tables.

The important change from my first audit is that I am now substantially less worried about **IBAC's PPO implementation itself**. The raw-action likelihood seam appears correct, and `entropy=0` has a stronger conceptual justification than I initially gave it.

The reason I still would not press “production” is now primarily **experimental validity and provenance**, not a hidden PPO algebra bug. The project is close enough that these are fixable release conditions rather than a need to redesign the research project.

[1]: https://arxiv.org/abs/2108.13264?utm_source=chatgpt.com "Deep Reinforcement Learning at the Edge of the Statistical Precipice"
[2]: https://doi.org/10.1016/j.jeconom.2022.04.001?utm_source=chatgpt.com "Cluster-robust inference: A guide to empirical practice - ScienceDirect"

