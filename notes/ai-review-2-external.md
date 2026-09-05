No. I would not start the production sweep from the supplied project state.

There are some problems I would classify as hard implementation blockers, several unresolved algorithm-port validity problems, and a larger issue about what scientific claim the resulting twelve-way table could legitimately support.

One qualification: the uploaded archive intentionally omits most non-`.py`/`.md` files and many Python files inside the nested source clones. I therefore cannot independently reread every final baseline file byte-for-byte. I can directly audit the included evaluator/training code, the authored patch machinery, the surviving clone files, and the project's detailed recorded deltas. I do not count failures caused by omitted JSON/YAML/shell/source files as defects. “All problems” below means all material problems I could establish from that evidence, not a proof that no additional problems exist in the omitted clone files.

## Verdict

I would divide readiness as follows:

| Area                                    | Verdict                                                             |
| --------------------------------------- | ------------------------------------------------------------------- |
| Can all 12 execute?                     | Apparently yes                                                      |
| Can all 12 save useful checkpoints?     | Apparently yes                                                      |
| RL-ViGen five as an internal comparison | Relatively strong                                                   |
| Cross-family evaluation                 | Not production-ready                                                |
| Common evaluation pairing               | Currently wrong                                                     |
| IDAAC adaptation                        | Scientifically unresolved                                           |
| PPG continuous adaptation               | Scientifically unresolved                                           |
| IBAC-SNI                                | Known invalid default corrected provisionally, diagnosis incomplete |
| CTRL evaluator                          | Not sufficiently checkpoint-self-describing                         |
| Time-limit semantics                    | Major unresolved cross-family confound                              |
| Observation comparability               | Deliberately non-common                                             |
| Evaluation estimator                    | Deliberately non-common                                             |
| Statistical production plan             | Not frozen and currently problematic                                |
| Production protocol                     | Explicitly still “PROPOSED”                                         |
| Code/run provenance                     | Candidate/canonical state unresolved                                |
| Full 12-way “algorithm comparison”      | Not supported by the current design                                 |

The RL-ViGen-native subset is in much better shape than the twelve-way comparison.

---

# 1. Hard blocker: the supposedly paired evaluator does not actually pair Door placements across families

This is a new defect I found in the executable evaluator.

`scripts/eval_across_scenes.py:136–149` does:

```text
set_seed_everywhere(seed)
build env
env.reset()
env.step(zero_action)       # verification probe
...
for measured episode:
    env.reset()
```

The project has already established that Door placement and robot initialization consume the global NumPy RNG on reset.

Meanwhile `scripts/eval_grid.py:127–135` explicitly avoids doing this reset/step verification in the other evaluator families because it knows that it would consume the placement RNG.

Consequently:

**RL-ViGen family**

```
seed → verification placement draw → measured placement 1 → ...
```

**other families**

```
seed → measured placement 1 → ...
```

Yet `docs/EVAL-PROTOCOL.md:28` currently claims that one common evaluation seed gives checkpoints “identical door placements (a paired comparison).”

It does not.

This is not merely theoretical because C69 already measured substantial score/success changes from different placement draws.

Fix this before any production evaluation.

The robust solution is not simply “reseed once after the probe.” Give every measured episode an explicit condition seed immediately before its measured reset, after all construction/probes, preferably something such as `(eval_seed, scene, episode_index)`. Record the realized initial physical state/placement as evidence. Then all twelve genuinely see matching episode conditions.

Any existing common-grid results from the current evaluator are not truly placement-paired across the RL-ViGen/non-RL-ViGen boundary.

---

# 2. Hard blocker: regime/scene verification is fail-open for most evaluator families

`scripts/eval_grid.py:111–163` attempts to read back `_mode` and `scene_id`.

But when neither can be recovered it prints:

> UNVERIFIED ... This is not a pass.

and nevertheless continues evaluation.

That is not sufficient for production.

A production row must not exist if the evaluator cannot establish that it evaluated the requested `(regime, scene)`.

This is especially important here because an accidental fallback to `train` can generate the most deceptively convincing possible failure: retention near 1.

The native RL-ViGen path is somewhat stronger because it actively probes the scene, although its mode check also abstains if unreadable.

For production, this needs to be **fail-closed for all seven evaluator families**.

---

# 3. The shared evaluator is not validated across the twelve

The project's own protocol says this explicitly.

The offline evaluator is authored project code. It loads twelve heterogeneous artifact types and then attempts to reproduce each baseline's own observation/action/evaluation semantics.

That is a substantial new instrument.

DrQ-v2 has a reasonably convincing native-vs-common check. IDAAC has a later “CONSISTENT” result, but I would treat it as substantially weaker: the means are still materially different and the comparison lacks a proper reference dispersion, so the audit substitutes information from the project evaluator to avoid declaring disagreement.

Ten baselines do not have convincing empirical common-evaluator validation.

This matters particularly for PPG, IBAC-SNI, ALDA and CTRL because their common evaluators are newly authored and their original evaluation mechanisms do not cleanly provide the desired RL-ViGen grid.

Before production I would require, per family, one of:

* common evaluator vs native evaluator on the same competent checkpoint; or
* where no native target evaluator exists, action-level equivalence on fixed observations plus a matched short rollout under controlled RNG.

A chance-level checkpoint is inadequate for this test: almost any two broken evaluators can agree that a useless policy is useless.

---

# 4. Training-time evaluation changes the training trajectory through the environment RNG

The project discovered this itself under C69 but has not eliminated the mechanism.

`RL-ViGen-upstream/train.py:47` seeds NumPy globally once.

The training environment and evaluation environments then consume the same global NumPy stream. Periodic evaluation performs resets. Those resets consume the same RNG that determines subsequent training resets.

The project experimentally demonstrated that inserting an evaluation reset changes the physical state of the next training reset.

P14 makes this worse by evaluating many scenes.

Therefore:

> Same algorithm + same training seed + different evaluation schedule ≠ same training experiment.

This is scientifically awkward because the twelve families have radically different native evaluation schedules: some periodically evaluate, CTRL interacts continuously with eval envs, and PPG/IBAC-SNI historically perform none.

Production training should isolate evaluation RNG from training.

The cleanest solution is probably to remove all unnecessary online evaluation from production and do comparison evaluation offline from checkpoints.

If online evaluation is retained, save and restore Python/NumPy/Torch RNG states around it and verify experimentally that inserting evaluation leaves subsequent training initial states unchanged.

At present the evaluation instrumentation can causally alter the data the learner sees.

---

# 5. The twelve-way comparison does not control the information supplied to the policies

The project knows this and calls it a porting-design-point comparison.

That qualification is essential.

Current families differ approximately as follows:

| Family                  | Frame stack | Resolution |
| ----------------------- | ----------: | ---------: |
| RL-ViGen five           |           3 |         84 |
| RAD/SODA                |           3 |     100→84 |
| ALDA                    |           3 |         64 |
| PPG/IDAAC/CTRL/IBAC-SNI |           1 |         64 |

The frame-stack difference is more serious than the resolution difference.

A three-frame policy gets motion/history information a single-frame policy does not. In robotic manipulation from pixels, this changes the effective partial observability problem.

Thus “method identity” is perfectly confounded with observation information across families.

This does not make the runs worthless. It changes the claim.

The resulting twelve-way table can reasonably mean:

> performance of these adapted implementations at their selected/native design points on RL-ViGen Door.

It cannot cleanly mean:

> controlled comparison of the twelve algorithms.

The project's own `RESEARCH-FRAME.md:64–82` essentially reaches the same conclusion.

Within the RL-ViGen five this particular objection is much smaller because their protocol is largely common.

---

# 6. Major validity problem: time-limit treatment differs across methods

This is probably the largest unresolved algorithmic-comparability problem.

Current project records:

* RAD/SODA/ALDA bootstrap through the artificial horizon.
* RL-ViGen five, PPG, IDAAC, CTRL, IBAC-SNI treat horizon `done` as terminal.

Door apparently does not terminate when successful. Runs terminate at the 500-step limit.

So this distinction affects effectively every training episode.

For example, included `runnable/idaac/train.py:213–216` does:

```python
masks = [[0.0] if done_ else [1.0] for done_ in done]
```

which means no bootstrap at the 500-step boundary.

This was appropriate for Procgen's true episode terminations. It is not automatically appropriate after transplanting the method onto an externally imposed manipulation time limit.

Pardo et al. distinguish exactly these cases: if a time limit is merely an artificial truncation of a continuing task, bootstrap through it; if the finite horizon itself defines the task, remaining time needs to be observable to preserve the Markov formulation. ([arXiv][1])

The current project occupies neither consistent position across methods.

This is a legitimate fidelity dilemma, but leaving three methods on one MDP interpretation and nine on another makes the cross-family ranking materially confounded.

I would not bury this as “native hyperparameter differences.”

Before production you need either:

1. harmonized target-environment truncation semantics; or
2. a planned sensitivity experiment demonstrating that this split does not drive conclusions; or
3. a substantially weaker cross-family claim.

---

# 7. PPG has a concrete continuous-action scaling defect in its defining auxiliary loss

This is a major port issue and I would fix it before presenting the baseline as PPG.

The original OpenAI PPG code performs:

```python
td.kl_divergence(oldpd, pd).mean()
```

for the auxiliary policy-cloning loss. That is verified directly in the authors' repository.

For the original `Categorical`, KL has effectively one scalar per sample.

Your continuous adaptation uses a 7-dimensional `Normal`.

That makes the KL tensor gain an action dimension.

The unchanged `.mean()` consequently averages over the seven action dimensions, while the PPO log-probability objective sums over action dimensions.

Your own `RUNNABLE-ORIGINALS.md:158–162` correctly notes the result:

> effective `beta_clone` is ~7× smaller.

I disagree with leaving this untouched on the grounds that “it is the authors' line.”

The mathematical object changed rank because of your adaptation.

Literal source-line preservation is therefore **less faithful to the original mechanism**.

A semantically faithful continuous adaptation should sum the per-dimension KL first and then average over samples/time, or otherwise recalibrate the clone coefficient explicitly.

Until that is decided, the PPG row is a specific continuous PPG variant whose signature auxiliary constraint has been weakened by approximately the action dimension.

Also note that PPG's first auxiliary phase occurs around 65,536 frames. Every existing 10k PPG probe is literally PPO with the PPG machinery not yet exercised. A 600k run does exercise it, so this is a warning about validation rather than a 600k blocker.

---

# 8. IDAAC's `level_seed` adaptation does not implement the mechanism it purports to represent

This is more serious than “IDAAC gets little benefit on Door.”

The official IDAAC storage mechanism groups observations by `level_seed`, picks another observation with the same level, and uses `nsteps` to construct the temporal-order target.

Official training obtains `level_seed` from each Procgen environment's `info`.

Your RL-ViGen adapter instead assigns `_LevelSeed(..., args.seed + i)`: effectively an environment-slot label.

The project has already experimentally established that these labels are not visually decodable; classification accuracy is exactly chance while a `scene_id` positive control is perfectly decodable.

That is already enough to say the IDAAC “instance identity” assumption is not preserved.

But there is an additional problem.

Because the label is tied to **worker slot rather than episode/instance**, `before_update()` can pair two observations from different Door episodes as supposedly belonging to “the same level.”

`nsteps` resets at episode termination (`runnable/idaac/train.py:217–218`).

Therefore a random pair crossing an episode boundary can have a temporal-order label derived from two independently reset physical instances. “Which came first in this instance?” has no meaningful answer for that pair.

A 256-step IDAAC rollout is shorter than the 500-step episode horizon, but rollouts are not synchronized to episode starts, so rollouts can straddle an episode boundary.

I regard this as a genuine semantic error in the adaptation, not merely an inconvenient property of the benchmark.

At minimum, `level_seed` should identify a coherent episode/instance for the duration over which the order relation is supposed to be meaningful. Whether an episode identifier is the right adaptation needs explicit reasoning, but a permanent worker identifier is not.

I would block IDAAC production until this is resolved.

---

# 9. IBAC-SNI's original continuous port was known-bad; `entropy_coef=0` is only a provisional repair

The project has strong evidence here.

Under the current Impala architecture, at `entropy_coef=0.01`:

* `mean_log_std`: 0.0026 → **1.4472**
* entropy: 9.95 → **20.03**
* success: 0 throughout
* σ ≈ 4.3 in an action space restricted to [-1,1].

A controlled run with only `entropy_coef` changed to 0 kept `mean_log_std` near 0.033 through ~25k.

So there is good evidence that the inherited categorical entropy bonus causes the pathological policy-scale growth in this port.

The latest `CONSTRUCTION.md` therefore supersedes the earlier 0.01 default and proposes `--entropy-coef 0.0`.

That is much better than running 0.01.

But it creates a different question:

> Is zero a principled IBAC-SNI continuous adaptation, or just the first value shown not to explode?

The project itself admits that the underlying reason IBAC-SNI reacts dramatically while IDAAC/PPG/CTRL do not has not been fully isolated.

I would allow further experimental work at `0.0`.

I would **not** yet call the resulting final row an original-implementation-faithful IBAC-SNI baseline without explicitly reporting that this is a target-specific entropy adaptation selected from a diagnostic intervention.

Also, the handoff documents are stale here: `RECOVERY-HANDOFF.md` still describes 0.01 as the pending default in places, while later C61 says 0.0. Production config must have one canonical source.

---

# 10. The Gaussian clipping problem is larger than the project's diagnostic makes it look

The project reports `boundary_fraction≈0.317` at initial σ=1.

That is the probability that an individual scalar Gaussian action coordinate lies outside [-1,1].

For a 7-dimensional independent standard Gaussian, the probability that **at least one coordinate** lies outside the legal action interval is approximately:

$$
1 - 0.6827^7 \approx 93\%.
$$

So near initialization, roughly nine out of ten action vectors from the unsquashed on-policy families are expected to have at least one coordinate clipped by the environment.

This isn't necessarily an implementation bug: unsquashed Normal + environment clipping is a known PPO construction.

But after porting categorical Procgen algorithms to 7-D continuous robotic control it is an important adaptation property, especially because the PPO likelihood is calculated for the pre-clipped action while the environment executes the clipped one.

For IBAC-SNI as σ grows, this becomes pathological rather than merely conventional.

I would add both:

* mean per-coordinate clipping probability;
* probability any action dimension clips;

to production health diagnostics.

---

# 11. CTRL checkpoints do not bind their reconstruction configuration

`runnable/ctrl/train_ppo.py` serializes a Flax `TrainState`.

`scripts/eval_grid.py:536–574` then recreates a target structure using this hardcoded dictionary:

```python
CTRL_DEFAULTS = {
  num_clusters=200,
  n_att_heads=2,
  embedding_type="concat",
  cluster_len=10,
  lr=5e-4,
  lr_ctrl=1e-4,
  max_grad_norm=0.5
}
```

and deserializes into it.

That's dangerous.

Flax `from_bytes` needs the target structure. The checkpoint is therefore not self-describing enough to establish which model/config it represents.

Today this may exactly match the production defaults.

But any future launcher override can make the evaluator reconstruct a different target while the checkpoint filename alone provides no proof.

Production checkpoints should contain—or be immutably associated with—the exact model/config manifest needed to reconstruct them.

Do not let the evaluator contain a second copy of production hyperparameters.

---

# 12. IDAAC's evaluator silently ignores the evaluator device

`scripts/eval_grid.py` accepts:

```text
--device
```

but `run_scene_idaac()` hardcodes:

```python
device = torch.device("cpu")
```

The generic loader later tries to set modules to the CLI device, but the IDAAC evaluation environment itself is explicitly constructed with CPU.

This may not materially change return once rendering is correctly containerized. But the CLI/API contract is false, and the project currently describes evaluation as being in-container on CUDA.

Either define IDAAC evaluation as CPU intentionally and validate it, or honor `--device`.

Silent parameter ineffectiveness is unacceptable in the production evaluator.

---

# 13. Evaluation policy estimators differ across methods

The project deliberately preserves native evaluation behavior.

Some algorithms use deterministic/mode actions.

PPG, IDAAC, IBAC-SNI and CTRL sample.

For example, the official PPG repository does not provide the deterministic continuous evaluation path you would ideally want; the project's adaptation consequently evaluates its stochastic policy. The original PPG repository is a Procgen implementation and explicitly supports its original PPG/PPO procedures rather than this continuous target. ([GitHub][2])

This isn't necessarily wrong.

But it means the common table does **not** use a common behavioral estimand.

A policy's stochastic expected return and the return of its mean/mode policy are different quantities.

I would produce two evaluation views where feasible:

1. **native-estimator result** — faithfulness-oriented;
2. **standardized deterministic continuous-policy result** — comparison-oriented.

If an algorithm cannot naturally define #2, say so.

What I would not do is put sampled and deterministic results into one column and call the column simply “return” without the estimator being visible.

---

# 14. Places365 is deliberately changed to the validation distribution

This is a significant fidelity issue for SVEA/SGQN/SODA.

`datasphere/native/configure_places365_val.py` modifies both source-family loaders from:

```python
use_val=False
```

to:

```python
use_val=True
```

and explicitly disables fallback.

RL-ViGen's public instructions say these algorithms use Places for augmentation and instruct users to download/configure the Places dataset. ([GitHub][3])

Your production system is therefore not merely pointing the original loader at a new filesystem location. It changes which Places partition supplies augmentation.

That changes the learning distribution.

For overlay-based generalization methods, the diversity of the background augmentation is part of the method.

I would not call this PLATFORM-class.

Before production, either supply the source-intended Places distribution or establish and disclose the validation-only substitution as a learning-affecting adaptation. Ideally run a sensitivity check.

This affects the methods using `random_overlay`, especially SVEA/SGQN/SODA.

---

# 15. The Places worker-count adaptation is not proven behavior-preserving

P19 changes Places DataLoader worker count because SGQN was crashing with eight JPEG workers on a four-CPU container.

The comment asserts:

> changes how images are fetched, never which images or in what order.

That conclusion is stronger than what worker-count equality generally licenses.

`shuffle=True` may preserve sampler index ordering, but stochastic transforms executed in worker processes can depend on worker-local RNG state and scheduling.

Because the actual nested loader/transforms are omitted from this slim archive, I cannot establish whether this matters in your exact implementation.

So I would classify this as **unproven**, not as a known bug.

Before production, empirically compare the augmentation stream under the selected production worker setting against the source/default configuration using fixed seeds and recorded image hashes/statistics.

---

# 16. The common 600k budget answers a sample-efficiency question, not a reproduction-at-convergence question

This distinction needs to be explicit.

CTRL's included `train_ppo.py` defaults to **25,000,000** training frames.

IDAAC/PPG are also Procgen algorithms designed for substantially larger training regimes.

600k does exercise all twelve mechanisms—the project correctly found that PPG doesn't even reach its first auxiliary phase below ~65.5k—but it is still a very different training horizon from some sources.

A fixed 600k interaction budget is perfectly legitimate if the claim is:

> performance after 600k target-environment interactions.

It is not enough to support:

> method X fails on Door.

A reviewer could reasonably argue that some baselines have very different learning schedules and were evaluated much earlier relative to their native training horizon.

Do not repair this by extending only methods that look bad after seeing results. Either predeclare a convergence/extension criterion or frame the experiment purely as fixed-budget sample efficiency.

---

# 17. Adaptive training-seed allocation can introduce post-selection bias

The proposed protocol says:

> one seed everywhere to find who is competent, then concentrate seeds on comparisons that are live.

That is fine for **exploration**.

It is problematic for a final comparative study if first-seed outcome determines who receives enough seeds to become publishable.

A method that gets an unlucky first seed can be categorized as “floor” and receive no further trials, while another receives three or five seeds.

That is outcome-dependent sampling.

For final results I would require either:

* the same minimum number of independent training seeds for all rows that appear in the main comparison; or
* an explicitly predeclared sequential design/stopping rule.

Deep-RL point estimates from only a few runs are known to be unstable, which is why interval estimates and careful treatment of run-level uncertainty are recommended. ([arXiv][4])

Twenty evaluation episodes × ten scenes does not repair a one-seed training experiment.

The training seed is the relevant independent replication unit for algorithm performance.

---

# 18. Three training seeds is still thin for ranking claims

The protocol currently says “3+” can license ranking, acknowledging poor resolution.

I'd be more conservative.

Three seeds can show gross differences. It generally cannot support fine ranking among high-variance deep-RL methods.

If compute is constrained, uncertainty intervals and effect/probability-of-improvement reporting become more important, not less. ([arXiv][4])

I would prefer five where a ranking is publication-relevant, perhaps more for highly unstable rows.

---

# 19. The proposed “retention = eval/train return” is a problematic headline quantity

Return ratio is not invariant to reward offsets.

Suppose every episode reward gets a harmless constant shaping offset \(c\). Then:

$$
\frac{R_{\text{eval}}}{R_{\text{train}}}
$$

changes even though the policy behavior and generalization gap may be unchanged.

Door has dense shaped reward with a non-zero random floor.

That makes raw return-ratio retention especially awkward.

The competence gate prevents the worst pathology—two chance policies giving “perfect retention”—but doesn't fix the metric's dependence on the arbitrary reward origin.

For Door I would make **success rate** the cleanest headline behavioral quantity and report dense return alongside it.

For a retention-style dense metric, a floor-adjusted version such as

$$
\frac{R_\text{eval}-R_\text{floor}}
     {R_\text{train}-R_\text{floor}}
$$

has better interpretation when the denominator is safely above floor, although it can be unstable near the floor.

Absolute train→eval success-rate drop is also very interpretable.

---

# 20. The retention denominator/scene estimand is not settled

This is the project's P-C76/R3 issue, and it is more important than a bookkeeping decision.

There are at least three different questions:

**A. Appearance robustness on trained geometry**

train scene 0, train appearance
vs
scene 0, randomized appearance.

**B. Appearance robustness conditional on geometry**

For each scene \(s\):

train-appearance scene \(s\)
vs
randomized-appearance scene \(s\),

then aggregate the within-scene effect.

**C. Joint appearance + scene generalization**

training distribution scene 0
vs
randomized appearance across scenes 0–9.

Those are different estimands.

If the denominator is only training scene 0 and numerator pools ten scenes, a “retention” score conflates visual shift with geometry/scene shift.

Fortunately the grid is collecting enough raw per-scene data to report these separately.

Do that.

Don't force them into one ratio before deciding what scientific construct it represents.

---

# 21. The same evaluation seed still does not guarantee the same stochastic experiment without per-episode seeding

Even after fixing the explicit RL-ViGen probe bug, one seed at the beginning of each scene is weaker than the protocol assumes.

Different wrappers can consume NumPy/Python/Torch randomness during:

* environment construction;
* reset;
* preprocessing;
* stochastic policy evaluation;
* diagnostics.

Therefore a single initial seed does not prove that episode \(k\) in baseline A corresponds to episode \(k\) in baseline B.

The robust common-random-numbers design is:

```text
condition_seed = f(global_eval_seed, regime, scene, episode_index)
seed environment stochasticity immediately before measured reset
record realized initial state
use a separate policy-action RNG
```

This also separates environmental randomness from stochastic-policy randomness.

---

# 22. The final renderer must be treated as part of the experimental condition

C95 is important and apparently resolved correctly: the prior huge saved-policy discrepancy was actually a renderer/environment discrepancy, not stale weights.

So I would **not** list checkpoint corruption as currently unresolved.

But C95 demonstrates that:

> same policy weights + different renderer = radically different result.

Therefore production needs to pin more than “EGL.”

Pin the exact container image/digest, MuJoCo/robosuite/RL-ViGen versions and relevant rendering stack.

At evaluator startup, run an observation fingerprint on a known state/configuration.

If the model is that sensitive to rendering, “V100 + EGL” alone is too loose a definition of the evaluation environment.

---

# 23. Universal checkpoint behavioral round-trip should still be a production gate

Although C95 exonerated serialization in the dramatic DrQ-v2 case, the history justifies a stronger generic test.

For every family:

1. capture fixed observations;
2. obtain the live acting policy's distribution parameters/action;
3. save;
4. start a fresh process;
5. reload;
6. evaluate the same observations;
7. compare.

For stochastic policies compare distribution parameters, not merely independent sampled actions.

CTRL especially needs this because reconstruction currently depends on hardcoded evaluator defaults.

IDAAC/PPG whole-model pickle formats also deserve explicit round-trip gates.

---

# 24. IDAAC's visible trainer does not itself seed NumPy

`runnable/idaac/train.py:80–81` does:

```python
torch.manual_seed(args.seed)
torch.cuda.manual_seed_all(args.seed)
```

but not `np.random.seed(args.seed)`.

The omitted `make_rlvigen_venv` implementation may seed NumPy elsewhere, so I cannot label IDAAC definitively unseeded from this archive.

But given that the project has established that the target environment uses global NumPy for physically important randomness, **RNG closure must be demonstrated, not inferred**.

Treat this as a required verification item.

---

# 25. CTRL's online evaluation is particularly entangled with training

`runnable/ctrl/train_ppo.py:257–277` takes a training transition and then immediately acts in ID and OOD test environments using the same ongoing training process and JAX key.

The JAX action-key progression itself is intentional.

The larger concern is the target environment's external/global NumPy randomness. Test-env resets in the same Python process may perturb the training environment's future reset stream exactly as C69 demonstrated for RL-ViGen.

CTRL therefore needs the same training/eval RNG-isolation audit.

---

# 26. Source implementation identity needs careful labels in the final paper

Several RL-ViGen-native methods are not necessarily canonical implementations of the named papers.

The project itself records inherited differences such as RL-ViGen's adaptations of SVEA/CURL/etc.

That is acceptable if the experimental object is:

> RL-ViGen's implementation of CURL

or

> RL-ViGen CURL baseline.

It becomes dangerous if the paper says simply “CURL” and invites readers to assume the canonical algorithm.

Likewise CTRL required restoring source code that was commented while still referenced, because the published repository otherwise could not run its own clustering path.

That is a defensible repair, but it needs to be part of the baseline identity.

---

# 27. PPG's continuous policy is necessarily an authored algorithm adaptation

The original OpenAI repository is explicitly a PPG implementation for its original setting and has very little code history; it does not provide your seven-dimensional continuous robotic action implementation. ([GitHub][2])

Your choices—state-independent log standard deviation, Normal registration, continuous PPO handling—are reasonable.

But they are not “the PPG original implementation running on another environment.”

They are **a continuous-action port of original PPG**.

That wording should be consistent throughout presentation.

And because the continuous adaptation changes the dimensionality of the KL object, item #7 is especially important.

---

# 28. IDAAC is even more benchmark-dependent than the current presentation suggests

The official repository explicitly describes itself as IDAAC/DAAC/PPO on **Procgen** and says its default hyperparameters are the best overall Procgen values. ([GitHub][5])

IDAAC's distinctive mechanism depends on level identity.

The target task does not naturally provide Procgen-style level identity.

Thus this is not merely “categorical → continuous.”

It is a structural transfer in which one of the algorithm's explanatory variables disappears.

The result is still scientifically interesting, but the interesting result may be:

> IDAAC's original invariance construction is not naturally instantiated by this target benchmark.

That is different from:

> IDAAC is a poor visual-generalization algorithm on Door.

The former is much better supported.

---

# 29. Reward normalization is another cross-family confound

The learner sees different reward pipelines.

Several on-policy Procgen-derived families normalize rewards. Others learn directly from raw Door reward.

Evaluation reports raw return.

Again, this is not necessarily a port defect: preserving a method's own normalization can be part of faithfully running it.

But it is another reason the twelve-way result is a comparison of **configured algorithm systems**, not isolated algorithmic mechanisms.

More seeds cannot remove this confound.

---

# 30. Gamma is materially different across families

The Procgen PPG/IDAAC/CTRL set uses approximately \(\gamma=0.999\), versus \(\gamma=0.99\) for most others.

At a 500-step horizon those correspond to dramatically different effective planning horizons.

Combined with the time-limit-treatment split, this is especially consequential.

Again: acceptable for native-design-point evaluation; incompatible with strong causal statements about algorithm identity.

---

# 31. The production protocol itself is not frozen

This is not merely documentation cosmetic.

`docs/EVAL-PROTOCOL.md:5` says:

> Status: PROPOSED. Nothing here is settled.

Open items include:

* scene definition/P-C76;
* headline metric;
* training-seed allocation;
* budget;
* treatment of IBAC-SNI adaptation;
* code-tree reconciliation.

You should not generate expensive final data while the estimand can still move.

That guarantees either reruns or post-hoc protocol selection.

---

# 32. The project's current authoritative code tree is ambiguous

`RECOVERY-HANDOFF.md:27–39` says the reconstructed candidate and older versioned tree still differ substantially:

* 30 files differ;
* 18 exist in only one;
* the post-August-31 infrastructure exists only in the candidate;
* manual reconciliation has not occurred.

This does not necessarily mean you must merge candidate into the old tree.

It means you must decide **which exact tree is production source**, audit it, commit it, and freeze its hash.

Production should never begin from “candidate plus intended future reconciliation.”

Once runs start, source ambiguity becomes experimental-provenance ambiguity.

---

# 33. There is current specification drift inside the evaluation documentation

`docs/EVAL-PROTOCOL.md` contains later text correctly saying all twelve can now retain checkpoint curves, followed shortly afterwards by an older block claiming the cross-family intersection is endpoint-only and PPG/IDAAC cannot provide the curve.

`scripts/eval_grid.py`'s module docstring likewise still says it supports only a subset of the families even though the implementation now covers seven evaluator families/all twelve baselines.

This is not an RL-math defect.

It is a production-risk defect because launch and interpretation decisions are currently being made from a spec containing mutually inconsistent historical states.

Before production, produce one small immutable protocol manifest instead of asking the run operator to interpret historical Markdown.

---

# 34. The proposed online training curves for RL-ViGen are too noisy to interpret per scene

P14 divides the configured evaluation-episode count across ten scenes.

At the commonly used 20 episodes, that's only two episodes per scene.

Those points should not be treated as meaningful per-scene learning curves.

Use them as diagnostics only.

The production-quality endpoint/intermediate checkpoint grid with 10–20 episodes **per scene** is a much stronger instrument.

---

# 35. Non-finite detection is post-hoc rather than obviously universal live abort

The project now has a checkpoint finiteness gate and correctly treats non-finite cells as failures rather than retrying until one survives.

That's good.

But earlier runs continued for long periods after numerical failure.

From the supplied slim archive I cannot establish that every current production family has a live loss/parameter non-finiteness abort during training.

Before nine-hour cells, require either:

* periodic live finiteness checks, or
* sufficiently dense checkpoint health checks so divergence is caught quickly.

Do not silently retry a failed seed. That would create survivorship bias.

---

# 36. ALDA/RAD/SODA/SGQN/etc. remain less independently audited than the detailed documents may make them appear

The omitted nested Python sources prevent me from independently verifying their final post-patch implementations in this uploaded copy.

So, specifically, I would still want before production:

* RAD: target env path, 100→84 preprocessing, SAC update/time-limit behavior, checkpoint/evaluator round trip.
* SODA: same plus Places365 distribution and augmentation path.
* SVEA: Places365 path and intended RL-ViGen SVEA identity.
* SGQN: Places worker fix, auxiliary update, Places stream and evaluator.
* CURL: exact RL-ViGen CURL mechanism versus canonical CURL naming.
* DrQ/DrQ-v2: snapshot/environment/evaluator parity is comparatively well supported.
* ALDA: target adaptation, action/reward wrappers, and common-evaluator validation.

I am deliberately not inventing baseline-specific defects where the actual final source is absent.

---

# 37. The RL-ViGen five are a materially cleaner comparison than the twelve-way table

This is important because it suggests a useful decomposition rather than simply saying “everything is invalid.”

Within the five RL-ViGen-native algorithms, the project reports:

* common 84×84 observations;
* three-frame stack;
* same task/runtime;
* same reward;
* same training/evaluation structure;
* same action family;
* same horizon;
* same regime/scene evaluation;
* mostly common hyperparameters except method-specific elements such as DrQ's n-step.

That subset is much closer to an identifiable benchmark comparison.

Across all twelve, method identity also selects observation memory, input resolution, discount, truncation convention, reward normalization, action distribution and several other things.

So I would present the analysis hierarchically:

**Tier 1:** controlled-ish comparison within the RL-ViGen native family.

**Tier 2:** cross-family port-at-design-point comparison.

Do not give Tier 2 stronger causal language than Tier 1.

---

# What I would require before authorizing production

The minimum gate is substantially smaller than rebuilding the project again. I would require these in order:

1. **Fix the evaluation pairing defect.** Per-episode environment condition seeds after all probes; record initial-condition witnesses.

2. **Make regime/scene verification fail closed** for every evaluator family.

3. **Isolate evaluation RNG from training RNG** and prove that inserting an evaluation does not change the next training reset.

4. **Resolve IDAAC `level_seed`.** A worker slot cannot be the same-instance identity if episodes reset to independent physical instances. Test the corrected mechanism.

5. **Resolve PPG auxiliary KL scaling.** I strongly favor sum-over-action-dim before sample mean, because that preserves the mathematical role of the original scalar categorical KL.

6. **Freeze IBAC-SNI's target adaptation.** If `entropy_coef=0` is used, declare it explicitly as a target adaptation and run enough of the diagnostic/control to know the resulting algorithm is actually learning rather than merely no longer exploding.

7. **Bind CTRL checkpoint to its reconstruction config.**

8. **Fix IDAAC evaluator device semantics.**

9. **Validate the common evaluator family-by-family**, at least behaviorally, before trusting production endpoint numbers.

10. **Decide the time-limit semantics.** This deserves an actual experiment or harmonization, not a footnote.

11. **Freeze the scientific estimands.** In particular separate appearance generalization from scene generalization and determine the retention definition.

12. **Freeze seed policy before seeing production outcomes.** One exploratory seed may screen engineering viability; final comparative rows need predeclared replication.

13. **Freeze one exact source tree/commit and environment/container manifest.**

14. **Replace the mutable Markdown production spec with one machine-readable frozen production manifest.**

15. **Run one complete production-shaped canary for every evaluator/runtime family**, including train → checkpoint → clean reload → full offline grid → records → final statistics.

Only after those pass would I launch 12 × seeds × 600k.

---

## If you ran production tonight anyway

I would regard the resulting data as useful **preproduction/exploratory evidence**, not as the final reviewer-facing benchmark.

The most serious reasons are not documentation or polish:

1. the common evaluation pairing is currently false;
2. some evaluator cells are allowed to remain unverified;
3. the common evaluator itself is insufficiently validated;
4. evaluation can alter subsequent training experience through shared RNG;
5. IDAAC's distinctive same-instance mechanism has an invalid instance identifier on this target;
6. PPG's continuous auxiliary KL is mis-scaled relative to its original mathematical role;
7. the time-limit MDP semantics differ across families;
8. the twelve methods do not receive equivalent observations or use equivalent evaluation estimators;
9. IBAC-SNI's continuous target setting has only just been changed following a demonstrated failure;
10. the final statistical/scene/metric protocol is not frozen.

Those are enough independently to withhold production approval.

The project is much closer to being able to run twelve things reliably than it is to being able to say that the twelve resulting numbers constitute one scientifically homogeneous comparison. The remaining work should therefore be concentrated on **experimental semantics and a handful of concrete evaluator/port defects**, not on adding broad new infrastructure.

[1]: https://arxiv.org/abs/1712.00378?utm_source=chatgpt.com "Time Limits in Reinforcement Learning"
[2]: https://github.com/openai/phasic-policy-gradient?utm_source=chatgpt.com "GitHub - openai/phasic-policy-gradient: Code for the paper \"Phasic Policy Gradient\" · GitHub"
[3]: https://github.com/gemcollector/RL-ViGen?utm_source=chatgpt.com "GitHub - gemcollector/RL-ViGen: This is the repo of \"RL-ViGen: A Reinforcement Learning Benchmark for Visual Generalization\" · GitHub"
[4]: https://arxiv.org/abs/2108.13264?utm_source=chatgpt.com "Deep Reinforcement Learning at the Edge of the Statistical Precipice"
[5]: https://github.com/rraileanu/idaac "GitHub - rraileanu/idaac · GitHub"

