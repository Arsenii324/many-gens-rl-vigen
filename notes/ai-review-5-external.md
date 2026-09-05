I reviewed this version as a new release candidate rather than diffing mechanically against the prior review. It is materially better. Several earlier concerns are genuinely fixed in executable code.

My current verdict is still **NO-GO for the full production fleet**, but for a narrower set of reasons. I no longer see an obvious fundamental PPO/SNI correctness failure in the IBAC-SNI implementation. The remaining blockers are mostly evaluator validity, source/result provenance, a real CTRL RNG-isolation defect, unvalidated common evaluation, and several still-unfrozen scientific decisions.

I would permit targeted pilots/canaries now. I would not yet accept a 600k × 3-seed × 12-method run as the final experiment.

### What I verified fresh

I ran fresh checks against this artifact. Compilation of the included production/evaluator/IBAC code passes. `scripts/metrics.py` passes its self-tests. Focused production-gate, convention, and port-semantics tests mostly pass.

One current audit is genuinely red:

```text
scripts/audit_eval_cadence.py --check
STALE idaac: runnable/idaac/train.py:291 ...
11/12 audited anchors still hold.
```

That appears to be a stale audit anchor after the IDAAC RNG-isolation changes, not an RL bug. It nevertheless demonstrates that the release state is not currently self-consistent.

I could not fairly use a literal whole-repository pytest run as evidence because this review artifact deliberately excludes `ext/`, while this sandbox also lacks some runtime dependencies such as `gym`. I did not count failures caused solely by those review-environment exclusions.

### Improvements that are real

The previous raw-vs-clipped IBAC PPO concern is resolved. The rollout code samples the Gaussian action, passes that sample to the environment, stores that same raw sample, stores its log probability, and PPO later scores that raw stored action. The importance ratio is therefore internally consistent.

The continuous Gaussian machinery itself is sensible: `Independent(Normal(...), 1)` correctly sums log-probability and entropy across the seven action coordinates. SNI still uses the mean bottleneck representation for the noise-suspended rollout policy, while VIB training evaluates clean/noisy branches and retains the bottleneck KL penalty.

Several evaluation defects have also been repaired: the PPG/IBAC/CTRL sampled-action metadata is corrected; checkpoint SHA-256 is recorded; CUDA is now the common evaluator default; strict regime verification is used on production paths; per-condition evaluation seeding has been pushed through IDAAC/PPG/CTRL auto-reset wrappers; the IDAAC `level_seed` issue is fixed; the PPG continuous-action KL reduction is fixed; CTRL's evaluator configuration now comes from the family descriptor; environment closing and temporary-directory cleanup are much better; the old performance-selected “usable scene” headline path is disabled; and the ALDA memory-tier mistake now has scheduler-level protection.

Those are substantial improvements.

## Current release blockers

| Severity  | Finding                                                                  | Why it matters                                                                                                                                                                                                                                                |
| --------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0**    | The exact source being reviewed is not immutably identified              | `README-ARTIFACT.md` / manifest says source commit `12f6322...` but also `tree_dirty: true` with **52 uncommitted paths**. That commit therefore does not identify the code contained in this artifact.                                                       |
| **P0**    | `source tree frozen` gate can false-PASS                                 | `gate_source_tree_frozen()` reads `git status` stdout but does not check its return code. In this review artifact `.git` is excluded, `git status` fails, stdout is empty, and the gate declares PASS.                                                        |
| **P0**    | The release-suite gate is not actually a release-suite gate              | `gate_release_suite_green()` runs a single docs-integrity pytest target, not the project's complete release tests/audits. It can say PASS while another production audit is currently failing.                                                                |
| **P0**    | CTRL's claimed train/eval RNG isolation is incomplete                    | CTRL saves/restores NumPy state, but online evaluation consumes the same **JAX PRNG key** subsequently used for training and returns the advanced key into the training loop. Reporting therefore changes later training randomness.                          |
| **P0**    | IBAC common evaluation ignores the requested CUDA policy device          | IBAC saves the model on CPU; `Agent` reloads it on CPU and creates a `self.device`, but never moves the model to that device. `eval_grid --device cuda` therefore silently evaluates the IBAC policy on CPU.                                                  |
| **P0**    | Common-evaluator equivalence is still largely unproven                   | The project's own gate still has only **2/12** evaluator burdens discharged. A common harness producing numbers is not sufficient evidence that those numbers equal the intended native measurements.                                                         |
| **P0**    | IBAC final configuration has not demonstrated Door competence            | `entropy=0` convincingly fixes the early scale runaway, but the evidence currently establishes stability, not successful Door learning under the exact final configuration.                                                                                   |
| **P0**    | Realized placement provenance is still absent                            | Condition seeds are now much better, but results do not record an actual realized Door placement/state hash. Given the previous RNG-stream problems, claimed pairing remains inferred rather than directly auditable.                                         |
| **P0/P1** | Offline grid rows are incompletely bound to runtime provenance           | They now carry checkpoint SHA-256, but direct `eval_grid` rows do not receive the full `run_manifest` provenance that normalized training records receive. The cheap records bundle can therefore omit container/package/full environment identity.           |
| **P0**    | Statistical protocol is still not frozen into the authoritative protocol | The revised proposal is much stronger, but `EVAL-PROTOCOL.md` remains proposed and owner choices such as the competence margin \(\delta\), primary contrasts, missing-run handling, and other estimand decisions remain unresolved.                           |
| **P0**    | Endpoint/checkpoint policy is not yet authoritative                      | Endpoint-as-headline is the right solution, but it needs to become the actual frozen protocol rather than remaining a proposal.                                                                                                                               |
| **P0**    | External RL-ViGen anchor remains open                                    | Before interpreting a twelve-method benchmark, the project still needs evidence that its benchmark/evaluation stack reproduces a known RL-ViGen reference point under matched conditions.                                                                     |
| **P0**    | Full-scale production canary remains open                                | There is still no completed 600k-class train → saved checkpoint → clean reload → full grid → records → final analysis rehearsal for the slowest/riskiest path.                                                                                                |
| **P1**    | Production gates are too syntactic in several places                     | Multiple gates establish “PASS” by finding strings/source patterns rather than proving behavior. The source-freeze and CTRL RNG cases show this is already producing false confidence.                                                                        |
| **P1**    | Environment lock is not fully immutable                                  | The container is represented by a mutable image tag rather than an image digest; the requirements hash is useful but not the same as an immutable resolved transitive environment.                                                                            |
| **P1**    | `source-lock.json` identity appears stale relative to this candidate     | Its recorded root identity does not correspond cleanly to this artifact's current source commit/dirty state.                                                                                                                                                  |
| **P1**    | Production schedule contains stale secondary rows                        | Its headline throughput table has been updated, but older per-cell rows still contain outdated tiers, unmeasured throughput entries, and older budgets. It says the executable source is elsewhere, but duplicated stale operational data is still hazardous. |
| **P1**    | Legacy reporting code does not implement the new inference plan          | `scripts/results_table.py` still contains historical one-seed/episode-bootstrap/retention-style reporting. It should not be capable of silently becoming the final publication path.                                                                          |

The first three gate problems are worth emphasizing. The project has moved in a good direction by having an executable preflight, but the preflight itself currently cannot be treated as an authority. It has at least two demonstrated false-PASS mechanisms: source cleanliness and CTRL RNG isolation.

## CTRL has a real training-validity problem

This is the strongest new algorithm-execution defect I found.

The relevant structure in `runnable/ctrl/train_ppo.py` is effectively:

```python
numpy_state = np.random.get_state()

# evaluation
..., key = select_action(..., key, sample=True)
...
..., key = select_action(..., key, sample=True)

np.random.set_state(numpy_state)

# future training uses `key`
update_ppo(..., key)
```

Restoring NumPy does not restore JAX's functional RNG state. The evaluation phase advances `key`, and that advanced key is retained.

So, unless production completely disables this online evaluation path, two runs with identical training seed/config but different reporting cadence can follow different training trajectories.

That violates the project's intended “evaluation should not perturb training” condition.

The fix is conceptually straightforward: maintain a separate evaluation PRNG key/stream that never becomes the training key, or disable the online evaluator in production. Then add a regression test that compares the next training JAX key with and without evaluation. A test that merely searches for `np.random.get_state()` is not sufficient.

## IBAC-SNI: my current algorithm assessment

The core port now looks much more defensible than it did during the first review.

I do not see evidence that the PPO ratio is invalid. The clean/noisy SNI structure is coherent. The action log-probabilities are reduced correctly. The bottleneck KL remains in the objective. `entropy_coef=0` is also a reasonable continuous-action adaptation given your controlled evidence.

In fact, because this Gaussian implementation uses a **global state-independent `log_std`**, its conditional action entropy is

$$
H[q(a|z)]
=
\sum_i \log\sigma_i + C,
$$

which does not depend on \(z\).

That means the entropy bonus in this particular continuous port is mostly a global variance-pressure term rather than an information-bottleneck-specific conditional exploration mechanism. Turning it off removes less of the distinctive IBAC machinery than would be the case for the original categorical decoder.

Your controlled result is useful:

$$
c_H=0.01
\quad\Rightarrow\quad
\text{large log-std growth / entropy growth / no success},
$$

whereas

$$
c_H=0
\quad\Rightarrow\quad
\text{early policy scale stays controlled}.
$$

I would therefore freeze `entropy_coef=0` rather than spend production resources trying to preserve 0.01 for historical aesthetics.

The remaining IBAC blocker is empirical:

$$
\text{stable scale} \neq \text{competent Door policy}.
$$

The exact intended final configuration needs a longer one-seed pilot, preferably to the already proposed ~100k checkpoint, and needs to cross a predeclared competence criterion before three 600k runs are justified.

### IBAC evaluator device bug

There is a subtle current implementation mismatch.

Training deliberately moves `acmodel` to CPU before saving, so the earlier possible “CPU observation into CUDA model” failure does **not** occur.

However `utils/agent.py` reloads that CPU model and never performs the equivalent of:

```python
self.acmodel.to(self.device)
```

Its preprocessing likewise stays on CPU.

Therefore the common evaluator's `--device cuda` does not actually govern IBAC. The policy runs on CPU.

That may or may not produce large score differences, but the project has already learned the hard way that evaluation environment/backend details can change Door measurements. A production evaluator should never silently ignore its device contract.

Either make IBAC honor the requested evaluation device or explicitly define “IBAC native evaluation uses CPU” and empirically reconcile CPU and CUDA results. I strongly prefer the first.

### Policy saturation still needs actual measurement

The initial diagonal Gaussian uses \(\sigma=1\) in seven dimensions. Even at mean zero, roughly 31.7% of individual coordinates lie outside \([-1,1]\), and approximately 93% of complete seven-dimensional samples have at least one out-of-range component.

That is not automatically an RL correctness bug; clipped Gaussian PPO policies are common.

But your present analytic `gaussian_boundary_fraction()` is only a zero-mean per-coordinate scale proxy. It ignores the actor's learned mean, and the mean head itself is not bounded to \([-1,1]\).

The useful production statistic is the actual one:

$$
\Pr(a_\text{raw} \neq a_\text{executed})
$$

and ideally

$$
\|a_\text{raw}-a_\text{executed}\|.
$$

Log it per vector, per dimension, and over training. A finite checkpoint with huge but finite variance is exactly the failure mode your current finite-value gate cannot detect.

### One smaller fidelity issue

The new PyTorch IMPALA trunk reproduces the broad architecture, but its convolution layers use normal PyTorch `nn.Conv2d` default initialization while the imported `initialize_parameters()` routine only specially initializes `Linear` layers.

That is not the same initialization behavior as the TensorFlow CoinRun implementation.

I would not block production solely on this. It does mean the result should remain described as an **authored continuous-action/PyTorch adaptation of IBAC-SNI**, not as bit-level reproduction of the original implementation. If exact fidelity matters, add an initialization-distribution/parity test or explicitly register this as an accepted adaptation.

## Evaluation/statistical validity

The revised statistical thinking is substantially better than the earlier version.

Training seed should indeed be the outer replicate. Ten scenes from one trained policy do not create ten independently trained policies. Treating the benchmark scenes as a fixed grid and showing all three training-seed aggregates is much more defensible than episode-level bootstrapping.

The primary outputs should stay close to:

$$
R_{\rm train},\qquad
R_{\rm OOD},\qquad
\Delta = R_{\rm OOD}-R_{\rm train},
$$

plus Door success rate.

Retention should remain secondary and suppressed for incompetent policies.

The remaining unresolved piece is the competence threshold. A rule such as

$$
R_{\rm train} > R_{\rm floor}+\delta
$$

in 2/3 seeds is fine in principle, but \(\delta\) has to be chosen **before** seeing the production outcomes.

Likewise, the missing-seed policy and the primary method comparisons need to be frozen beforehand.

Endpoint-as-headline is the cleanest checkpoint rule. I would not add a “best checkpoint” headline at all. Show the trajectory descriptively.

### Pairing is improved, but not proven yet

The new condition-seeding scheme is an important improvement. However, given the history of wrappers consuming global RNG differently, I would still require every evaluated episode to record a compact hash of the realized initial physical state/door placement.

Then pairing becomes an observable property of the resulting dataset rather than an assumption about equivalent RNG consumption.

This also lets the analysis assert something strong before computing a paired difference:

```text
placement_hash(A, scene=4, episode=7)
==
placement_hash(B, scene=4, episode=7)
```

If that fails, that pair is invalid.

## Cross-method interpretation remains limited

This is not something code changes can completely “fix.”

The twelve rows still differ jointly in several dimensions: observation resolution, one-frame versus three-frame input, architecture, gamma, time-limit treatment, reward normalization, action-distribution/evaluation convention, rollout/process count, replay-buffer design, data augmentation, and native training horizon.

Some of those differences are central to the released implementations.

Consequently, a scientifically safe headline is still:

> performance and visual generalization of twelve released/adapted implementations on RL-ViGen Door under their declared design points.

It is not:

> a controlled causal test showing algorithm A's defining mechanism is superior to algorithm B's.

In particular, one frame versus three frames is an observability difference, not just parameter count. Time-limit bootstrap versus terminal treatment changes value targets. And 600k frames represents very different fractions of the original training horizon for different methods.

That does not invalidate the benchmark. It constrains the claim.

Other declared adaptations should also remain prominent: the 300k replay cap, reduced on-policy process counts imposed by the EGL/fork environment, the Places365 validation split for augmentation-based methods, and the authored continuous heads for categorical-origin methods.

## Operational concerns

The ALDA memory failure is much better handled now: the scheduler knows the measured fixed footprint and prevents placement on an undersized tier. I consider the original ALDA OOM diagnosis substantially addressed at the planning layer.

Off-policy resume remains a different matter. If replay contents and all required stochastic state are not persisted, restoring only model/optimizer/global step is not continuation of the same experiment. Production jobs for those methods should either run non-preemptibly or be restarted from the original seed from frame zero after interruption.

The project also still needs the long canary. The shortest route to confidence is not another 10k all-method smoke test; it is one deliberately expensive 600k-class cell on the slow/risky path, followed by clean process restart, checkpoint reload, full evaluation grid, records collection, and the exact proposed final analysis.

## My approval conditions

I would change the status to production-ready after all of the following are true:

1. Create a clean immutable commit for the exact payload, and bind each run/result to that commit plus payload hash and immutable container digest.
2. Harden `production_gates.py`: check subprocess return codes, make the release gate execute the real release suite/audits, and test negative cases rather than source-string presence.
3. Fix CTRL's JAX RNG contamination or disable its online evaluator during production training.
4. Make IBAC's common evaluator honor the declared policy device and reconcile it against the native evaluator.
5. Discharge the remaining common-evaluator validation burden rather than treating “runs without exception” as equivalence.
6. Record realized Door placement identity/hash per evaluation episode.
7. Propagate the run-manifest/environment identity into offline evaluation records or bind them cryptographically to one manifest.
8. Merge and freeze the statistical/checkpoint protocol, including the competence \(\delta\), missing-run policy, primary metrics, and primary contrasts.
9. Run the exact-final-config IBAC `entropy=0` competence pilot.
10. Establish the external RL-ViGen anchor and complete one full-scale end-to-end canary.
11. Replace/disable legacy episode-bootstrap reporting for the final results pipeline and implement the frozen three-seed analysis explicitly.
12. Regenerate all audits/tests from that exact frozen tree and require zero unexplained failures.

After those, I would be substantially more comfortable signing off.

The important overall conclusion in this version is that **IBAC-SNI's continuous PPO core is no longer what worries me most**. The method is an adaptation rather than an original-paper continuous implementation, but its basic probability accounting and SNI/VIB structure look defensible. The highest risks now sit around the experiment: exact source identity, evaluator equivalence, RNG neutrality, measurement provenance, and the still-unfrozen final inference protocol.

