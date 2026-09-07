I reviewed the supplied `C.zip` as the current production candidate, statically. I did not run tests, training, renderer jobs, remote jobs, or production commands. I did use read-only inspection and independent hash recomputation.

My conclusion is: **I would not start the production fleet from this exact tree yet.** There are a few genuine blockers, led by one newly found learning-path bug that the current production gate misses.

## Production blockers

1. **P0: “online evaluation disabled” is false at step 0 for RL-ViGen, RAD, SODA, and ALDA — eight baselines total.**

This is the most important finding.

`datasphere/native/family.py:342-346` correctly decides that periodic online evaluation should be disabled because it consumes the process-global NumPy stream used for Door placement.

But `datasphere/native/run_probe.sh:454-457` and `:733-739` implement “disabled” by passing:

```text
2147483647
```

as the evaluation cadence.

That does not disable evaluation at step 0.

RL-ViGen's `utils.Every` returns true when `step % every == 0` (`RL-ViGen-upstream/utils.py:76-87`), and its training loop calls it at global step 0 (`train.py:314-321`).

DMC-GB initializes `done=True`, `step=0`, then executes:

```text
if step % args.eval_freq == 0:
    evaluate(...)
```

before its first training reset (`runnable/dmc_gb/src/train.py:140-175`).

ALDA does exactly the analogous thing at step 0 (`runnable/alda/trainers/alda_trainer.py:608-625`).

So production currently performs an unwanted initial evaluation for `drqv2`, `svea`, `drq`, `sgqn`, `curl`, `rad`, `soda`, and `alda`.

This is scientifically material because the project disabled online evaluation specifically to prevent it from advancing Door's placement RNG. The unwanted evaluation advances that RNG before later training resets. DMC-GB does 20-episode online evaluation under the production configuration; ALDA evaluates its three environments at its native depth. Different families therefore receive different training-placement RNG perturbations while the manifest claims online evaluation was suppressed.

Worse, `scripts/production_gates.py:97-122` can pass this condition because it checks the descriptor (`eval_every=None`), not the executed sentinel semantics. So this is a real **gate false-negative**.

I would fix the mechanism, not the number. An explicit “skip online evaluation” branch is much safer than any numeric sentinel. Final endpoint evaluation can remain. Any files entering the hashed runtime/evaluator closure then need their corresponding final validation refreshed.

2. **P0: IDAAC's current evaluator attestation is stale against this archive.**

I independently recomputed the static evaluator-family closure hashes using the algorithm defined by the project. I did not execute project tests.

Six families matched their current validation ledger exactly:

```text
rlvigen   OK
dmc_gb    OK
alda      OK
ppg       OK
ibac_sni  OK
ctrl      OK
idaac     STALE
```

For IDAAC, the checked-in attestation's family-code revision is stale, and consequently its combined evaluator revision is stale.

Current combined revision I computed:

```text
1c6d9574a36f3c977272493433243faa34662f705da2e78c1b941037e266af40
```

Ledger combined revision:

```text
2fe1ee0956d34f06ce32d0aa4d73b2250a426990ad2a2b94c7274663dced6282
```

This is exactly the condition `scripts/production_gates.py` is intended to reject. Do the final seven-family evaluator-validation wave **after** the step-zero-evaluation fix and any other runtime-closure changes, rather than validating IDAAC now and invalidating it again.

3. **P0: production renderer/container parity remains an actual precondition, not paperwork.**

The project's own C95 gate is justified. Previous records apparently show approximately 131.5 versus 13.85 for the same checkpoint under a renderer/platform difference. That is far too large to treat renderer identity as infrastructure trivia.

Before production results become eligible, the actual V100 image/container, EGL path, evaluator closure and checkpoint-loading environment need the R_A/R_B parity check described by `scripts/production_gates.py:602-627` and `notes/CURRENT-STATE-AND-RESPONSIBILITY.md`.

For CTRL specifically, this also needs to prove that JAX is actually using the V100 backend. A successful Python process is insufficient if it falls back to CPU.

4. **P0 for CTRL: the production schedule restores 64 environments but still carries a memory number measured at 16.**

`families.json` correctly restores CTRL to 64 envs on V100.

But the production scheduling/resource model still carries roughly 13.4 GiB, which came from the 16-env measurement. The project's migration notes themselves acknowledge that ~54 GiB is merely a linear extrapolation and JAX/XLA memory does not have to scale linearly.

The 113-GiB host probably has sufficient capacity, but “probably” is not adequate for a 64-environment JAX job or for any packing decision around it.

The existing `cfg-ctrl-v100-memory-v130.yaml` is exactly the right bounded measurement shape. I would require the real 64-env V100 RSS/VRAM measurement before the CTRL production seed or before packing another cell beside it.

5. **The exact-final IBAC-SNI configuration has runnability evidence, but not adequate competence evidence.**

The current baseline is materially different from the old pilots: 16 processes, Impala visual trunk, `beta=1e-4`, entropy 0, continuous Gaussian Door head.

The existing 16-process evidence demonstrates multiprocessing/render/memory viability. It does not demonstrate that this exact repaired algorithm learns Door.

Your own `production_gates.py` recognizes this distinction.

Given how noncanonical IBAC-SNI necessarily is—CoinRun visual lineage, torch bottleneck/training lineage, authored continuous head, one VIB sample rather than the CoinRun 12, latent64 rather than 256—I would not spend three full 600k seeds without one bounded exact-final competence run. Otherwise a finite floor result can easily be mistaken for evidence against IBAC-SNI rather than evidence against this particular hybrid port.

## High-priority issues I would settle before the first production outcome is seen

6. **Places365 is still deliberately changed from the upstream training partition to the validation partition.**

`datasphere/native/configure_places365_val.py` rewrites the source `use_val=False` behavior to `use_val=True`.

That affects SVEA, SGQN and SODA.

This is a learning-distribution change to the augmentation mechanism itself. Sharing the same deviation between the three does not establish that rankings are unaffected.

Given your stated priority of source fidelity, I recommend using the upstream **training** split for production. If there is a compelling operational reason not to, freeze `val` now as an explicitly accepted learning-affecting adaptation. I would not leave this in the “same for everyone so probably harmless” category.

7. **PPG's present “DMC comparator profile” is still internally incomplete.**

The PPG production port has now improved substantially: stack3, γ=.99, lr=3e-4, 32 minibatches, entropy0, etc.

But the IDAAC supplement's shared continuous-control recipe also specifies linear LR decay over one million environment steps. IDAAC now implements that literally and correctly. PPG does not.

There is a legitimate provenance conflict: original OpenAI PPG itself uses constant LR, whereas the third-party IDAAC-authors' PPG DMC comparator belongs to the linearly-decayed DMC experiment.

So I do **not** prescribe blindly adding decay. I prescribe freezing the identity:

Either PPG is “OpenAI PPG adapted to Door, borrowing selected continuous-control values,” in which case constant LR is defensible; or it is “the IDAAC-authors' DMC PPG comparator ported to Door,” in which case linear decay is a missing setting.

Current wording sits between those two.

Also, 8 envs ×256 steps is not identical to the published 1×2048 continuous-control rollout. It preserves 2048 samples/update and the 65,536-interaction auxiliary cadence, but not GAE truncation/trajectory geometry. Report exactly that.

8. **ALDA UTD=1 remains a real stability risk.**

The active ALDA path runs UTD=1.0, which is the correct source-primary choice. I agree with not silently replacing it with .25.

But the project's previous Lift/retired-port observations of catastrophic UTD=1 instability are strong enough to justify the already-designed Door 1.0-vs-.25 bounded stability check before buying three long ALDA runs.

The interpretation should remain:

source primary = 1.0;
if Door requires .25, .25 is a target-specific stabilization adaptation, not a restored source value.

9. **The production result provenance strings for the RL-ViGen variants are weaker than the scientific understanding now in the project.**

This matters because `normalize_curves.py` stamps these strings into records.

In particular, the current labels understate how modified RL-ViGen SVEA, SGQN and CURL are relative to their original publications.

SVEA is not merely “SVEA source mechanism, RL-ViGen Door configuration”; RL-ViGen puts the SVEA-style regularization on its DrQ-v2-style backbone.

SGQN is an RL-ViGen released-code SGQN profile on that backbone, with known differences from the publication's Door table.

CURL is likewise RL-ViGen's one-encoder/DrQ-v2-backed variant, not merely original CURL with different preprocessing.

Do not rename the baseline IDs now. Do strengthen their immutable provenance descriptions before results are emitted.

10. **Remove “best-in-group winner versus best-in-group winner” from primary comparisons.**

A25's grouping by scientific mechanism is an improvement over grouping by repository.

But selecting the empirically best method from each group and then comparing those winners creates winner's-curse/post-selection bias. Predeclaring that you will select the winner does not remove the bias.

This is particularly problematic at \(n=3\), when your own resolving-power analysis correctly says close rankings are poorly resolved.

Freeze fixed cross-group contrasts now, based on scientific rationale, or label winner-v-winner comparisons explicitly as post-selected/descriptive. Do this before seeing production outcomes.

11. **`effective_config.json` does not capture every learning/evaluation-affecting environment variable.**

The capture list in `run_probe.sh` includes many important variables, but omits at least `NATIVE_ISOLATE_ONLINE_EVAL`, the endpoint/curve regime/scene/episode settings, and some snapshot/evaluator-related controls.

`NATIVE_ISOLATE_ONLINE_EVAL` is particularly important because changing it changes training RNG semantics for the continuous on-policy ports.

I would make the effective-config artifact exhaustive for all production-affecting environment variables rather than relying on some of them being recoverable indirectly from other manifests.

12. **The memory preflight is weaker than the actual replay-memory model.**

`family.py::check_memory()` primarily uses fixed measured peak plus margin. It does not fully model the large replay allocation/growth of RL-ViGen or DMC-GB.

Your planned tiers happen to account for this elsewhere, so this is unlikely to break the intended V100 production path. But a production-shaped manually submitted DataSphere configuration can be certified by this check despite being too large for the tier.

Use the planner's replay calculation in submission-time memory validation as well. One memory truth, not two.

13. **`OPEN-QUESTIONS.md` contains at least two stale questions that should be closed before freeze.**

Q1 and Q4 are now statically answerable from this tree.

Door composes the `easy` task configuration, whose active schedule is the 100k DrQ-v2 exploration schedule. Production is not deriving the 500k value from the retired port.

Likewise active RL-ViGen production configuration uses `num_seed_frames=4000`; the 600-frame occurrences belong to smoke/short-job overrides.

Leaving these as unresolved questions creates a risk that someone “fixes” already-correct production values immediately before launch.

14. **Multi-environment PPG/CTRL Door placement is one shared process-global NumPy stream, not one independent physical-placement RNG per environment.**

PPG and CTRL instantiate multiple Robosuite environments inside one process. The wrapper has per-environment random state for visual randomization, but the underlying Door placement sampler consumes process-global NumPy.

So `seed+i` should not be interpreted as independent physical-placement RNG streams. The vector environments consume successive draws from one common stream.

I do not see evidence that they get identical placements, so this is not a blocker. Evaluation uses one environment and your paired endpoint placement protocol remains intact. But this is part of the continuous-control vectorization adaptation and should not be described as independent per-env placement seeding.

15. **Production failure semantics need an explicit “restart from frame zero” rule for off-policy runs lacking full-state replay restoration.**

RL-ViGen checkpoints do not preserve the replay buffer. Resuming a 400k checkpoint with an empty replay buffer is not the same experiment.

Your missing-seed policy already says to rerun the same seed. Make the operational consequence explicit: for families without complete optimizer/RNG/replay state restoration, a crashed production cell restarts that same seed from zero rather than “resuming” an evaluation checkpoint.

That matters over multi-day runs.

## Things I investigated that I would not block

I initially flagged CTRL's continuous online evaluation because it advances the JAX PRNG key even while NumPy is restored. On deeper inspection, the gate explicitly recognizes this exact fact (`production_gates.py:111-116`) and treats the JAX-key advancement as behavior inherited from upstream CTRL, while isolating only the Door-placement NumPy stream. I therefore **do not classify that as a current defect**. The comments could be more precise, but the choice is conscious rather than hidden.

Likewise I would not “repair” the continuous PPO ports by tanh-squashing them immediately. IDAAC, IBAC-SNI and CTRL have the known raw-policy-action versus controller-clipped-action seam. The project now has action clipping/raw→executed diagnostics. Preserve the frozen port and monitor the seam rather than silently introducing a different likelihood model.

I would retain CTRL `cluster_len=10`. The publication says T=2 while the released implementation defaults to 10; that is a genuine paper↔official-code conflict, and using released code is a coherent provenance decision.

I would retain RL-ViGen replay capacity 620k. It is not nominally the upstream 10M capacity, but at this fixed 600k horizon it is safely non-evicting. “Non-evicting at the declared horizon” is the exact defensible statement.

The current IDAAC C2 is much stronger than the earlier project state. The one-million-step LR decay is implemented correctly on environment steps; it is not mistakenly rescaled to 600k. Its 1×2048/32-minibatch/10-epoch/stack3 recipe is genuinely source-informed.

The PPG frame-stack correction, SODA 100→84 path and auxiliary lr repair, ALDA 600k trajectory with retained 500k checkpoint, IBAC 16-process spawn path, 50k checkpoint retention, raw per-episode endpoint records, training-seed-as-replicate statistics, missing-seed policy, endpoint-primary checkpoint rule, and current success/return reporting design all look directionally sound from static inspection.

## Launch disposition

If this were my production gate, I would make items **1–4 unconditional blockers**. I would also close **IBAC exact-final competence** before committing its three main cells. I would settle Places365 and the PPG provenance/LR choice before source freeze, because both affect what algorithm is actually being claimed.

After those source/runtime changes, I would do **one final evaluator-closure validation wave**, not piecemeal validations; establish production V100 renderer/container parity; measure CTRL64 memory; then freeze the source commit, production schedule, effective-config schema, statistical comparison set, and container digest.

Only then would I regard the 36-cell 12×3 production fleet as scientifically frozen.

One limitation: although I inspected the actual archive broadly and traced the highest-risk production paths, I did not exhaustively prove every line of every vendored dependency equivalent to its source, and the archive deliberately excludes the actual `results/**` payloads. Therefore I could independently inspect the checked-in validation ledger and recompute its static hashes, but I could not independently re-evaluate the empirical measurements those result files substantiate. I also deliberately did not execute the project's test suite or any training/infrastructure code, per your instruction.
