I continued from the interrupted point rather than restarting. This revision is substantially closer to a defensible production state. Several previous hard blockers are genuinely gone.

My current decision is still **NO-GO for the complete final 12×seed production fleet**, but it is no longer a broad “the system is untrustworthy” judgment. The remaining risk is concentrated in a few imported baselines—especially IBAC-SNI, and scientifically PPG/IDAAC—plus final-platform/evaluator validation and one provenance inconsistency.

I did not complete an exhaustive line-by-line differential audit of every source file before the tool window closed. I concentrated on the exact production configurations, current gates, evaluation state machines, provenance, and the baselines carrying the largest remaining semantic adaptation. I would therefore consider the RL-ViGen-native/RAD/ALDA source-level portion less exhaustively inspected than PPG/IDAAC/IBAC/CTRL.

# Current status

| Area | Assessment |
| --- | --- |
| Root project at artifact creation | **Clean committed tree** |
| Nominal production budget | 600k, explicit V100 schedule |
| Native-five replay | **Resolved**: 620k is effectively non-evicting |
| PPG continuous KL | **Resolved** |
| PPG phase cadence | **Improved materially** |
| IDAAC episode identity/storage | **Resolved end-to-end** |
| CTRL normalized-return evaluator bug | **Resolved** |
| CTRL double-reset evaluator bug | **Resolved** |
| IBAC β=1 | **Resolved** to $$ 10^{-4} $$ |
| IBAC fork RNG issue | Structurally improved with spawn + child construction/seeding |
| IBAC 16-env path | Functional smoke passed, but competence/final behavior unresolved |
| Places distribution | **Still a scientific deviation** |
| PPG baseline choice | **Major fairness/design-point issue** |
| IDAAC baseline choice | **Major fairness/design-point issue; stronger than PPG** |
| IBAC algorithm identity | **Major fidelity issue** |
| CTRL continuous-action representation semantics | **Major unresolved port question** |
| Common evaluator current-revision validation | **Still effectively 0/7 families** |
| V100 renderer equivalence | Not yet established |
| External RL-ViGen positive control | Not yet established |
| Source-lock root lineage | **Wrong/stale commit identifier** |
| CTRL V100 resource model | **Stale after return to 64 envs** |
| Final statistical structure | Mostly sensible; some ratification/canonicalization remains |
| Production | **Not yet** |

The repository's own production gate currently reports approximately **28 PASS, 2 FAIL, 10 OWNER** and refuses launch. One FAIL is an artifact issue rather than a real project failure: `.git` is intentionally omitted from the review ZIP. `artifact-manifest.json` says the source was clean when built at commit:

`6727a1f1241b4e57ba27d4ca9f53c1bad62b46d3`

with zero uncommitted paths.

Likewise, the release-suite documentation-link failures are largely because the review artifact omits sibling coordination documents. I would not hold RL production over those.

The issues below are the ones I would actually act on.

---

# 1. Concrete provenance defect: `source-lock.json` identifies the wrong root commit

The clean-commit problem has been solved, but the project now has an easier-to-fix inconsistency.

The review artifact says the root project is:

`6727a1f1241b4e57ba27d4ca9f53c1bad62b46d3`

while `datasphere/native/source-lock.json` still says:

`f041f5e170368d298e9b5b60127faa10ba5364e5`.

That old root identifier propagates into the payload/provenance machinery.

This does **not** mean the actual payload bytes are unidentified: you also hash the payload itself, which is considerably stronger evidence about what actually ran.

But it means a reviewer-facing/source-lineage record can say:

> root commit f041f5e...

when the project that actually generated the production payload is 6727a1f....

Fix this before producing final artifacts.

The freeze gate should eventually verify:

$$
\text{source-lock root}
=
\text{production HEAD}
=
\text{artifact source commit}.
$$

This is no longer a conceptual issue—just a concrete provenance bug.

---

# 2. PPG is much better configured now, but it remains a hybrid design point

The previous V100 proposal used 16 PPG environments. The current revision deliberately returns to **8**.

That is a meaningful improvement.

Current PPG collects:

$$
8\times256=2048
$$

interactions per policy iteration.

With:

$$
N_\pi=32,
$$

its defining auxiliary phase occurs approximately every:

$$
2048\times32=65,536
$$

interactions.

That is almost exactly the phase cadence implied by the authors' published continuous-control PPG setting: a 2048-step rollout and $$
N_\pi=32
$$.

So my previous criticism that production PPG had its defining phase retimed by 16–32× relative to every meaningful precedent no longer applies.

Official OpenAI PPG itself uses 64 environments, $$
\gamma=.999
$$, LR and auxiliary LR $$
5\times10^{-4}
$$, 8 minibatches, one policy/value epoch, six auxiliary epochs and $$
N_\pi=32
$$.  Those values flow directly into the original learner.

However, matching **one cadence** isn't the same as matching the authors' continuous-control configuration.

The relevant published continuous-control setup uses approximately:

- 3 stacked frames;
- 2048-step rollout;
- one environment/process;
- LR $$
3\times10^{-4}
$$;
- $$
\gamma=.99
$$;
- entropy coefficient 0;
- 32 minibatches;
- linear LR decay;
- with PPG-specific $$
N_\pi=32,E_\pi=1,E_V=1,E_{\rm aux}=6,\beta_{\rm clone}=1
$$. [Proceedings of Machine Learning Research](https://proceedings.mlr.press/v139/raileanu21a/raileanu21a-supp.pdf)

Current Door PPG instead uses approximately:

- one 64×64 frame;
- 8 environments × 256 steps;
- LR $$
5\times10^{-4}
$$;
- $$
\gamma=.999
$$;
- entropy .01;
- 8 minibatches.

There is also a less obvious distinction:

$$
8\times256
$$

and

$$
1\times2048
$$

have the same number of samples but are not equivalent trajectory structures. The former repeatedly bootstraps 256-step fragments from eight environments; the latter carries a much longer temporal sequence before rollout truncation.

So I would now characterize the implementation as:

> a Procgen-source-derived continuous PPG port, with the PPG auxiliary-phase frequency deliberately matched to the authors' continuous-control sample cadence.

That is coherent and considerably better than the previous version.

But because an author-published continuous-control PPG configuration exists, I would still run one bounded pilot comparing the current version against a minimally Door-adapted form of that configuration **before final full-scale production**.

The most interesting variables are probably frame stack, $$
\gamma
$$, entropy and optimization/minibatching—not `n_pi`, which you have already aligned well.

---

# 3. IDAAC's old implementation bug is genuinely fixed

The previous version had a difficult real bug involving:

`EpisodeLevelSeed`

→ Baselines auto-reset

→ terminal `info`

→ new episode observation

→ rollout storage.

The result was that a new episode observation could inherit the previous episode's level identity.

The current version has fixed the whole chain rather than merely fixing the wrapper.

It now:

- exposes the next episode identity across terminal auto-reset;
- chooses the next identity for the reset observation;
- aligns storage level/nstep indexing with the observation slot.

I traced and exercised this boundary again.

I would remove the previous “IDAAC mechanism is currently incorrect because episode classes cross reset boundaries” blocker.

---

# 4. IDAAC nevertheless remains one of the strongest possible “handicapped baseline” objections

The remaining IDAAC problem is scientific rather than implementation-level.

Current Door IDAAC is still overwhelmingly based on the authors' **Procgen** configuration:

$$
\gamma=.999
$$

LR:

$$
5\times10^{-4}
$$

entropy:

$$
.01
$$

plus:

- 256-step rollout;
- 1 PPO epoch;
- 8 minibatches;
- one 64×64 frame;
- value epoch 9;
- value frequency 1;
- advantage loss coefficient .25;
- order/invariance loss coefficient .001.

Those really are close to the public Procgen defaults. The authors' repository confirms LR $$
5\times10^{-4}
$$, $$
\gamma=.999
$$, entropy .01, 64 processes, 256 steps, one PPO epoch and eight minibatches.

But the same IDAAC paper contains a published **continuous visual-control** configuration.

That configuration is approximately:

- three stacked frames;
- 2048 steps;
- one process;
- LR $$
3\times10^{-4}
$$;
- $$
\gamma=.99
$$;
- entropy 0;
- 32 minibatches;
- substantially more PPO optimization;
- linear LR decay;
- and IDAAC-specific continuous-control coefficients, including $$
N_\pi=32
$$, $$
\alpha_a=.1
$$, $$
\alpha_i=.1
$$. [Proceedings of Machine Learning Research](https://proceedings.mlr.press/v139/raileanu21a/raileanu21a-supp.pdf)

Two current differences are especially consequential.

Current `value_freq=1`, versus the continuous-control design's approximately $$
N_\pi=32
$$-style value/auxiliary cadence.

More importantly, current:

$$
\text{order\_loss\_coef}=0.001
$$

versus the published continuous-control invariance coefficient:

$$
\alpha_i=0.1.
$$

That is a **100× difference in the weight of IDAAC's defining invariance objective**.

This is no longer something I would treat as an implementation-detail footnote.

Door is continuous visual control. A skeptical reviewer has a straightforward argument:

> The authors already provided a continuous-control IDAAC recipe; why was the baseline instead given its Procgen hyperparameters, one frame rather than the published continuous-control three-frame observation, and a 100× weaker invariance coefficient?

There may be a good answer—but that answer should exist **before** observing the final comparison.

My strongest recommendation for IDAAC is therefore a two-design preproduction test:

**IDAAC-P:** current faithful-to-public-Procgen-code port.

**IDAAC-C:** minimally Door-adapted published continuous-control design.

If their conclusions agree, excellent.

If IDAAC-C learns substantially better, the final paper should not quietly report only IDAAC-P.

If only one can be afforded for all seeds, decide the primary using a stated fidelity principle before seeing the production outcome.

---

# 5. IDAAC's episode ID remains a conceptual adaptation even though its code is now correct

Procgen `level_seed` denotes a generated level.

Door episode identity denotes one particular physical rollout.

Those aren't identical constructs.

The current adaptation at least gives the invariant/order machinery internally valid groups. That is a large improvement.

But if IDAAC remains weak, several explanations remain possible:

- IDAAC is not effective on this generalization problem;
- the Procgen-derived optimizer/design point is poor for continuous Door;
- Door lacks a natural analogue of the persistent latent “level” variable IDAAC was designed to suppress.

That should constrain interpretation later.

---

# 6. IBAC's previous two catastrophic implementation problems are substantially repaired

Two old problems should be retired.

First, production now passes approximately:

$$
\beta=10^{-4}
$$

rather than falling through to the PyTorch branch's disastrous $$
\beta=1
$$.

Second, the final multiprocessing path has been redesigned around `spawn`, child-side environment construction and deterministic worker-specific seeding rather than forking sixteen already-initialized MuJoCo environments from one globally seeded parent.

The repository also has a successful >4-process functional smoke for the new EGL/spawn path.

So I would no longer claim:

> IBAC's proposed 16-process configuration is known not to execute.

Nor would I retain the old:

> all workers necessarily inherit identical NumPy physical-placement state

as the present implementation diagnosis.

Those were valid findings against earlier versions.

---

# 7. IBAC still is not yet reviewer-safe

The largest remaining IBAC issue is what algorithm the row represents.

Current IBAC combines approximately:

- CoinRun-style IMPALA visual trunk;
- PyTorch/GridWorld-side bottleneck implementation;
- 64-dimensional bottleneck;
- single bottleneck sample;
- $$
\beta=10^{-4}
$$;
- authored continuous Gaussian head;
- entropy coefficient 0;
- 16-env target execution.

The authors' main visual/CoinRun IBAC-SNI uses materially different VIB/SNI mechanics, including different bottleneck dimensionality and multi-sample behavior, plus associated regularization/augmentation choices.

So the current variant takes a meaningful parameter ($$
\beta
$$) and visual backbone from the CoinRun line without actually becoming the CoinRun implementation.

That is still a hybrid.

It may be a perfectly reasonable newly constructed continuous IBAC-SNI variant.

But if it performs at the floor, reviewers can reasonably say:

> This doesn't establish that the original visual IBAC-SNI mechanism is weak; it establishes that this particular hybrid continuous port is weak.

I would choose a coherent reference lineage.

Given that Door is visual, the CoinRun/visual implementation is probably the easier primary baseline to defend.

At minimum, the defining bottleneck choices—latent dimension, number of samples, SNI behavior, relevant regularization and augmentation—deserve explicit comparison with that source.

---

# 8. IBAC competence still needs to be demonstrated under the final configuration

The gate correctly leaves this OWNER.

Historical ~100k IBAC evidence showing near-floor return, zero success and extreme action clipping should **not** be interpreted as evidence against the current final-beta/final-multiprocessing implementation. The project now correctly labels that run as non-final evidence.

The old run remains useful for one reason: it proves the action diagnostics can detect a pathological policy.

Final IBAC should get a targeted preproduction run long enough to answer:

> Does the actual intended β/architecture/process configuration acquire Door competence at all?

If the answer remains no, I would not immediately launch three 600k seeds.

First inspect:

- action saturation;
- log-std;
- VIB magnitude relative to PPO losses;
- invariance/SNI losses;
- whether the bottleneck actually learns nondegenerate features.

Also repeat the entropy 0 versus .01 intervention **under the final configuration**. The old entropy diagnosis was generated in a materially different IBAC system.

---

# 9. CTRL's old evaluator defects are fixed

I rechecked the relevant direction before the interruption.

The current common evaluator now:

- uses raw, unnormalized Door reward;
- avoids the earlier explicit-reset-after-auto-reset problem;
- reconstructs from checkpoint-bound model configuration.

Those prior hard blockers should stay deleted.

---

# 10. CTRL has a more subtle continuous-port problem: raw policy action versus executed action

This remains unresolved and I consider it scientifically material.

CTRL's representation/clustering objective explicitly conditions on action in the original implementation. That action is passed into the clustering representation/loss.

In its original discrete environment:

$$
a_{\rm sampled}=a_{\rm executed}.
$$

In the current continuous Door version:

1. Gaussian policy produces raw $$
a
$$;
2. PPO must retain raw $$
a
$$ because the policy ratio/log probability corresponds to that sample;
3. the environment/controller applies its allowed action bounds;
4. physical transition is caused by the bounded action;
5. CTRL's representation objective consumes the raw stored action.

Consequently the representation learner can be asked to explain transition:

$$
s_t\to s_{t+1}
$$

conditioned on an action that wasn't exactly the action applied at the declared action boundary.

For PPO itself, replacing the stored raw action with its clipped value would be incorrect.

So the sensible port representation is probably to keep both:

$$
a_{\rm policy}
$$

and

$$
a_{\rm executed/bounded},
$$

using the former for policy likelihood and the latter for CTRL's transition-conditioned representation learning.

I would **not implement this solely from theoretical reasoning**, though.

The project now measures raw-versus-bounded action diagnostics. Use them first.

If clipping is rare once learning begins, this is probably negligible.

If vector clipping is pervasive, run a short raw-action-versus-bounded-action CTRL representation sensitivity.

This is exactly the sort of adaptation where an apparently small categorical→continuous substitution can alter the defining auxiliary mechanism.

---

# 11. CTRL is restored to 64 environments, which is good scientifically—but the production memory model hasn't caught up

Earlier V100 configurations reduced CTRL from the author's approximately 64 environments to 16.

That changed rollout/update geometry by about 4×.

The current V100 schedule restores 64.

I consider that a substantial fidelity improvement.

But `production-schedule-v100.json` still estimates roughly **13.4 GiB** for the CTRL cell—approximately the observed 16-env footprint.

Earlier internal scaling estimates were around 54 GiB at 64 environments.

This doesn't necessarily make the schedule impossible: the V100 host has approximately 113 GiB system RAM and CTRL runs alone.

The more significant unknown may be the V100's 32 GiB VRAM.

Therefore the exact 64-env V100 canary should measure:

- host RSS peak;
- GPU peak allocation;
- actual rollout/update completion;
- throughput.

The current scheduler resource model should not be trusted for CTRL until then.

---

# 12. The off-policy A27 “action repeat means 0.25 UTD” error has been corrected

This is important because the proposed correction in an earlier version would likely have introduced a new baseline handicap.

The current project now correctly distinguishes:

$$
\frac{\text{learner updates}}
     {\text{new replay transitions}}
$$

from:

$$
\frac{\text{learner updates}}
     {\text{low-level simulator substeps}}.
$$

RAD/SODA/ALDA collect one replay transition per control decision. Source action repeat 4 means that transition spans four low-level simulator steps; it doesn't mean four new replay samples appeared.

Thus retaining approximately one learner update per newly collected replay transition is substantially more source-like than blindly reducing updates to 0.25.

The current correction is sound.

If ALDA empirically needs 0.25 updates per transition for Door stability, that's still useful evidence—but it should be identified as a **target-specific optimization adaptation**, not a restoration of source UTD.

I would not alter RAD/SODA on the old A27 reasoning.

---

# 13. Native-five replay is no longer a problem

Earlier production proposals used a 300k replay buffer for 600k training.

That would have evicted approximately half the early data by the endpoint.

The current V100 profile uses approximately:

$$
620,000
$$

capacity and the project's conservative retained-transition estimate is around:

$$
601,200.
$$

So replay does not fill.

In this experiment:

> 620k behaves like the nominal 1M source capacity with respect to replay eviction.

I would not block DrQ-v2/DrQ/CURL/SVEA/SGQN over this anymore.

---

# 14. Places365 is now one of the largest remaining fairness issues for SVEA/SGQN/SODA

The project still changes the source loader from the intended Places training distribution to a fixed validation subset of roughly 36.5k images.

That change is intentional, deterministic and well recorded.

It is nevertheless a **learning intervention**.

These methods use external visual augmentation specifically as part of their generalization mechanism.

Changing the augmentation corpus changes the mechanism's effective training distribution.

And saying:

> SVEA, SGQN and SODA all get the same alternative split

doesn't remove the cross-family issue.

They are precisely the methods affected; DrQ/PPG/IDAAC/etc. are not.

Now that final production is no longer restricted to the small DataSphere disk environment, I would ask again whether this compromise is necessary.

If the full intended Places train data can be provided on the V100 host, use it.

If not, conduct a bounded train-split-vs-val-split sensitivity on one or preferably two affected methods.

This is especially important because the paper's subject is generalization.

---

# 15. Be precise about SVEA and CURL identities

Another possible reviewer confusion is baseline naming.

The canonical DMC generalization implementation of SVEA uses its own augmentation scheme; for example, the public SVEA implementation's critic path uses `random_conv`.

RL-ViGen's baseline implementation is not necessarily byte-for-byte or architecturally identical to what a reader would assume from the original method name.

Likewise RL-ViGen's CURL baseline inherits benchmark-specific implementation choices.

This is fine if these rows intentionally mean:

> RL-ViGen implementation of SVEA

and:

> RL-ViGen implementation of CURL.

It is riskier to label them unqualified “SVEA” and “CURL” in a context where reviewers might assume canonical implementations.

This is presentation/provenance rather than a reason not to train them.

---

# 16. Artificial-horizon semantics remain unresolved across families

Current project explicitly records a split:

**bootstraps at the 500-step time limit:** RAD, SODA, ALDA;

**treats it as terminal:** native five, PPG, IDAAC, CTRL, IBAC-SNI.

Because Door usually runs until the imposed horizon rather than ending immediately on task success, this affects most episode endings.

The different algorithms therefore learn different terminal value semantics.

This is a genuine cross-family confound.

I still would not automatically “fix” all twelve to one convention solely for uniformity. That could reduce source/design fidelity.

At this late stage, the most informative thing is a targeted sensitivity on representative methods.

If the difference barely matters, you have empirical permission to preserve native conventions.

If it matters strongly, the final twelve-way table needs to be described explicitly as a comparison of algorithm systems with differing horizon semantics—or the target environment's truncation convention needs harmonization.

---

# 17. The full twelve-way result still isn't an algorithm-only comparison

This remains fundamental and isn't an engineering defect.

Families differ in:

- one versus three frames;
- 64/84/100→84 inputs;
- gamma;
- reward normalization;
- time-limit handling;
- replay versus rollout learning;
- optimizer/update schedules;
- policy distributions;
- stochastic versus deterministic evaluation;
- auxiliary data.

The correct estimand is approximately:

> performance of twelve adapted method systems at explicitly chosen design points under a shared Door training-budget/evaluation framework.

It isn't:

> causal comparison of twelve algorithmic ideas while everything else is identical.

The five RL-ViGen-native methods support a substantially stronger controlled-comparison interpretation.

For PPG and IDAAC specifically, the one-frame observation is now a more significant fairness concern because their authors' published continuous-control setup used **three stacked frames**. [Proceedings of Machine Learning Research](https://proceedings.mlr.press/v139/raileanu21a/raileanu21a-supp.pdf)

---

# 18. Common evaluator validation is now probably the largest fleet-wide preproduction requirement

The gate effectively treats **0/7 evaluator families** as validated under the current evaluator revision.

I agree with being conservative here.

The evaluator has changed materially enough across these revisions that old validations shouldn't automatically bless it:

- physical condition control;
- strict regime/scene checks;
- raw reward corrections;
- CTRL reset changes;
- placement diagnostics;
- provenance;
- deterministic computation settings.

Before generating final endpoint results, validate each evaluator family with a competent checkpoint.

You do not necessarily need a completely independent native target-grid evaluator for every method.

The useful validation hierarchy is:

1. fixed observation → same policy/distribution outputs;
2. checkpoint clean-reload equivalence;
3. matched physical reset condition;
4. matched short rollout;
5. raw return/success extraction;
6. native/common evaluator comparison where one exists.

Floor policies are weak validators.

Two broken evaluators can easily agree that a useless policy scores near zero.

There is already measured small same-checkpoint/evaluator nondeterminism in the underlying simulator/render path, so require **agreement within an evidence-based tolerance**, not bit-identical rollout returns.

---

# 19. The current condition-seeding design is good for appearance generalization, not a pure scene intervention

Physical condition seed now depends on something equivalent to:

$$
(\text{evaluation seed},\text{scene},\text{episode index})
$$

but not on visual regime.

This means within a given scene:

```
train appearance, episode i
eval-easy appearance, episode i
eval-medium appearance, episode i
eval-hard appearance, episode i
```

can share the same physical Door initialization.

That's a very useful paired visual-generalization design.

But:

```
scene 0, episode i
scene 7, episode i
```

do **not** share the same physical initialization.

So the scene axis shouldn't be interpreted as:

> the same physical initial state with only scene changed.

Treat scene variation as a fixed heterogeneous evaluation grid instead.

That's perfectly reasonable.

It also argues for making **within-scene appearance effect** one of the strongest generalization quantities.

---

# 20. Physical episode diagnostics are now much stronger

Previous versions could sometimes substitute image hashes for physical-placement evidence.

The current evaluator records much more useful environment-level episode diagnostics and production can be made to fail closed if those are missing.

That's now a strong design.

The remaining task isn't another rewrite—it is current-revision empirical validation that every evaluator family actually produces the expected diagnostics and condition alignment.

---

# 21. Final renderer equivalence is still a hard practical gate

This remains OWNER and I would not waive it.

The project already discovered that one very large “checkpoint failure” was actually:

> same weights, different rendering/runtime → radically different performance.

That means platform equivalence is empirically known to be load-bearing.

Before the V100 fleet:

$$
\text{same competent checkpoint}
+
\text{same current evaluator}
+
\text{same container}
$$

should be evaluated on:

1. the currently trusted reference platform;
2. the production V100 platform.

Host/runtime should be the intended change.

Compare observations and returns.

The container digest is now pinned, which is a meaningful improvement.

---

# 22. Run an RL-ViGen positive control on the final platform

Evaluator parity establishes:

> our common evaluator agrees with another evaluator.

It does not establish:

> our simulator/render/training environment is operating in the expected benchmark regime.

Given the previous renderer incident, run at least one competent RL-ViGen-positive-control method on Door.

SVEA or SGQN is more useful here than an accidentally weak DrQ-v2 checkpoint.

The goal isn't exact table-number reproduction under mismatched hardware/settings.

It's detecting a gross benchmark-wide error before spending the full fleet.

---

# 23. Production lineage is much better, but the normalized-record schema deserves one final check

The full `run_manifest.json` now embeds `effective_configs` for the actual cells, plus:

- payload hash;
- asset hash;
- immutable container image;
- resolved packages;
- environment;
- EGL details;
- host profile.

That is good.

One thing I noticed while tracing the normalization path is that `normalize_curves.py` constructs a smaller `run_provenance` object containing manifest/payload/container/runtime fields but not obviously the complete `effective_configs` payload at that immediate normalization layer.

Other downstream enrichment appears designed to carry the full manifest into final records.

Before production, I would run one end-to-end provenance assertion:

> Given one final normalized paper row and nothing else, can the aggregation code mechanically recover exactly one training manifest and therefore exactly one effective baseline configuration?

If yes, no further architecture change is needed.

If not, add a stable `training_run_id`/manifest hash join.

The important object is:

$$
\text{paper row}
\rightarrow
\text{checkpoint}
\rightarrow
\text{training manifest}
\rightarrow
\text{effective config}
\rightarrow
\text{source/payload/runtime/assets}.
$$

---

# 24. The high-level protocol hash is now better described than in earlier revisions

The current code explicitly says the protocol hash is **necessary, not sufficient** and distinguishes runtime identity.

That addresses part of my previous criticism.

I would still avoid treating the high-level protocol hash as the complete experiment identity because baseline-specific choices such as:

- PPG rollout geometry;
- IDAAC coefficients;
- IBAC β/bottleneck;
- replay capacity;
- Places split;

belong naturally in the baseline-specific training lineage.

That's fine if aggregation keeps the two concepts separate.

You don't need to cram every algorithm parameter into one universal comparison hash.

---

# 25. Exact interaction budgets differ slightly, and that's fine

Final synchronous schedules land around:

PPG:

$$
\sim600,064
$$

IDAAC:

$$
\sim598,016
$$

IBAC-SNI:

$$
\sim600,064
$$

rather than exactly 600,000.

These errors are small.

I would not deform the original update loops to force exact equality.

Simply record the actual interaction count and plot/report that rather than pretending the endpoints are mathematically identical 600,000-step points.

---

# 26. Statistical protocol is now mostly sensible

The current direction is substantially improved:

- fixed training seeds 101/102/103;
- training seed is the independent replication unit;
- endpoint checkpoint is primary;
- intermediate checkpoints are descriptive;
- no episode-level pseudo-replication;
- scenes are a fixed evaluation grid rather than pretending they are independent sampled tasks.

That is a defensible small-compute deep-RL protocol.

Three seeds are still weak for fine rankings.

A claimed ~53% “effect resolution” should be interpreted as an illustrative calculation under the assumed variance, not as a guaranteed empirical lower bound on detectability.

For gross differences—competent versus floor, for example—three can be adequate.

For:

> A reliably beats B by 10–20%

three is poor evidence.

If the eventual scientific conclusions depend on exact ordinal ranking among closely performing methods, increase the important comparisons to five or more training seeds.

---

# 27. Success rate should remain more prominent than return ratios

The project is moving toward floor-adjusted return retention rather than raw:

$$
R_{\rm OOD}/R_{\rm train}.
$$

That's better because a raw ratio changes under an arbitrary additive reward shift.

A floor-adjusted quantity:

$$
\frac{R_{\rm OOD}-R_{\rm floor}}
     {R_{\rm train}-R_{\rm floor}}
$$

has a more useful interpretation.

But Door success rate is still cleaner behaviorally.

I would give result priority approximately:

**success rate → absolute success drop → raw shaped return → floor-adjusted return retention.**

And use the paired within-scene appearance contrast when making the strongest generalization claims.

Make sure the random-policy floor has a single canonical computational source; the project history already contains slightly different old floor values.

---

# 28. Don't choose checkpoints using the final OOD grid

The current endpoint-first rule is good.

Keep it.

Intermediate checkpoints can be shown as trajectories.

If you later select whichever intermediate checkpoint performs best on the same OOD scenes used for reporting, those scenes cease to be test conditions and become validation conditions.

A “best checkpoint” result therefore needs an independent predeclared selector.

---

# 29. The native RL-ViGen subgroup is now close to actual production

With the replay issue resolved, I don't see a major unresolved common algorithmic blocker for:

- DrQ-v2;
- DrQ;
- CURL;
- SVEA;
- SGQN.

SVEA and SGQN retain the Places issue.

CURL/SVEA need careful implementation naming.

Otherwise their remaining requirements are mainly:

- final V100 runtime validation;
- current evaluator validation;
- external positive control;
- provenance cleanup.

This is a substantially different state from several versions ago.

---

# 30. RAD and ALDA also look relatively close

I would not currently subject RAD or ALDA to broad new port refactoring.

For RAD, the earlier proposal to lower UTD because the source used action repeat 4 should remain rejected.

ALDA's previous observed stability improvement at lower update rate remains a potential target-specific adaptation worth studying, not source-fidelity evidence.

Their main remaining common requirements are evaluator/final-platform validation.

SODA additionally has the Places augmentation issue.

---

# 31. The remaining production risk is asymmetric

I would roughly classify the methods now as:

| Baseline | Present status |
| --- | --- |
| DrQ-v2 | Near production |
| DrQ | Near production |
| CURL | Near production; naming/lineage caveat |
| SVEA | Near, subject to Places decision |
| SGQN | Near, subject to Places decision |
| RAD | Near production |
| SODA | Near, subject to Places |
| ALDA | Near production |
| PPG | Implementation works; **design-point comparison required** |
| IDAAC | Implementation correctness fixed; **strong design-point/fairness issue remains** |
| CTRL | Major old bugs fixed; **raw-vs-bounded representation-action question + V100 64-env resource canary** |
| IBAC-SNI | Multiprocessing improved; **competence and coherent algorithm identity remain unresolved** |

# What I would actually do before launching

At this point I would avoid another broad engineering cycle. The remaining work should be narrow:

1. **Fix the root source-lock commit mismatch.**
2. **Run the exact 64-env CTRL V100 resource canary and update its memory/VRAM model.**
3. **Run final-config IBAC competence + β/entropy/bottleneck diagnostics.**
4. **Decide a coherent IBAC source lineage—or label the current hybrid explicitly enough that its result isn't presented as literal original IBAC-SNI.**
5. **Run the bounded PPG current-vs-published-continuous-control configuration comparison.**
6. **Run the analogous IDAAC Procgen-port-vs-published-continuous-control comparison. IDAAC is the higher-priority one because its current invariance coefficient is 100× below the continuous precedent and its observation stack differs.**
7. **Resolve the Places train-vs-validation split.**
8. **Run the targeted CTRL raw-action-vs-bounded-action representation diagnostic if actual clipping is substantial.**
9. **Validate all seven evaluator families under the current evaluator revision.**
10. **Run final V100 renderer equivalence and one competent RL-ViGen positive control.**
11. **Run at least a representative time-limit-handling sensitivity if the cross-family comparison will receive strong algorithm-ranking language.**
12. **Verify the final normalized result→training-manifest→effective-config provenance join.**
13. **Freeze remaining estimand/scope decisions and exact V100 manifests.**
14. **Then launch final seeds.**

## My production recommendation

I would **not launch the whole twelve-method production study today**.

I would be comfortable launching final-platform **canaries and possibly final runs for the near-ready subgroup** if they are kept explicitly separate from the final frozen evidence set until the evaluator/runtime validation has passed.

The three areas I would spend the most scientific attention on before a reviewer-facing fleet are now:

**IDAAC:** the code is no longer obviously wrong, which makes its configuration choice the central issue. Its published continuous-control precedent differs dramatically from the present Procgen-derived Door baseline, including a 100× invariance-loss coefficient difference.

**IBAC-SNI:** the gross β and fork defects are repaired, but the current algorithm is still a hybrid of author implementations and has not demonstrated competence under its final configuration.

**CTRL:** the common evaluator has been repaired and upstream-scale parallelism restored; the remaining question is whether its action-conditioned representation should use the raw Gaussian policy sample or the bounded action that actually generated the physical transition.

The most important fleet-wide requirements are no longer generic code correctness. They are **current-revision evaluator validation and final-V100 renderer/runtime validation**.

Once those targeted issues are resolved, I would no longer see a general engineering reason to postpone production. The remaining limitations—different observation stacks, time-limit conventions, gamma, reward normalization, optimizer structures—would mostly define what the experiment *is*: a comparison of twelve explicitly adapted method systems rather than a perfectly controlled twelve-way algorithm ablation.