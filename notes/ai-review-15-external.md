This is the strongest version so far. The project has moved from “many known correctness hazards” to “a small number of release-integrity questions.” My current verdict is:

**Near production, but still NO-GO for the final fleet.**

The important point is that I no longer see a major unresolved bug in the IBAC-SNI PPO/SNI implementation itself. The remaining highest-risk issue I found is now in **evaluator identity/revalidation**, followed by empirical competence/canary requirements and ALDA stability.

I ran the current gates under the intended V100 profile, compiled the relevant source, exercised targeted audits, inspected the current evaluator-validation machinery, resolved production descriptors, IBAC multiprocessing implementation/evidence, source provenance, ALDA path, statistical protocol, and the current revalidation configs.

Fresh V100 gate result is:

> **28 PASS / 2 FAIL / 10 OWNER — NOT LAUNCHABLE**

The two literal FAILs need interpretation. `source tree frozen` fails only because `.git` is deliberately excluded from this review ZIP; the artifact itself says it was built from clean `main@6727a1f...` with zero uncommitted paths. The release-suite failure is partly caused by links to parent-workspace documentation deliberately excluded from the artifact, although I did find four genuinely stale internal source citations that should be repaired.

The substantive blockers are elsewhere.

## What is genuinely fixed now

A large number of previous P0s are closed.

IBAC's 16-process execution is no longer hypothetical. The multiprocessing path has been redesigned so workers can receive environment factories, child workers use `spawn`, environments are constructed in the child instead of inheriting live MuJoCo/EGL contexts, and each worker gets an independent seed. The retained validation record shows a real `procs=16`, 4,096-frame functional run completed successfully with approximately 19.25 GiB aggregate process high-water under the available 27 GiB envelope.

That closes my previous objection that `procs=16` was inherently unrunnable.

The ALDA evaluator is also repaired. It no longer initializes the environment twice, and evaluation builds ALDA with essentially no training replay allocation:

```python
trainer.build(spec, replay_capacity=1, prefill=False)
```

rather than allocating the million-transition training buffer.

Production-mode enforcement is now strong. A 600k-scale run requires both an explicit host profile and production mode. Conflicting production overrides are also treated much more strictly.

Terminal checkpoint handling is substantially safer. Mandatory final saves fail closed, checkpoint finiteness is checked before expensive endpoint evaluation, and the previous “old fixed-name checkpoint silently evaluated as the new endpoint” path is closed.

The CTRL double-reset condition-pairing bug is fixed. Current pairing evidence reports zero known-unpaired and zero eligible comparisons without physical evidence.

The V100 schedule is now generated from the actual V100 family descriptor instead of inheriting DataSphere assumptions. CTRL is back to 64 environments, RL-ViGen replay is 620k, IBAC is 16×128, PPG deliberately remains 8×256, and throughput is correctly labeled **unmeasured on V100** rather than guessed.

The hyperparameter audit is also much stronger. It now has:

> **0 UNLOCATED live launcher/descriptor/argparse claims**

which is a meaningful improvement after the IBAC-beta incident.

And the statistical inference framework is finally merged into the live evaluation protocol rather than remaining a side proposal.

Those are significant changes.

---

# The largest new blocker: evaluator revalidation is targeting the wrong identity

This is the most important problem I found in this version.

The evaluator-identity implementation explicitly documents a code/config split:

> configuration changes should change `config_revision` and combined revision but **leave `code_revision` alone**.

That is conceptually correct.

But the implementation does this inside the common digest helper:

```python
def _digest_of(members, root):
    ...
    digest.update(
        b"NATIVE_HOST_PROFILE\0"
        + _selected_host_profile(root).encode("utf-8")
    )
```

Every code revision calls `_digest_of()`.

Consequently, the exact same evaluator code produces a different **code revision** solely because the selected host profile changes.

I verified this directly.

For example:

```text
                 datasphere code rev   v100 code rev
rlvigen          420726e24ca72197      4b9f1ce20bfa60ac
ibac_sni         e2870f92fbbe2db5      5d40fff2cd4be0ef
ctrl             b82a18865402327d      65fad37c723a77fc
```

No source changed between those calculations.

That contradicts the reason the code/config split was introduced.

It would be less serious if this were only semantic naming. It is not.

All seven new evaluator revalidation configs:

```text
cfg-rlvigen-revalidate-v136
cfg-dmc_gb-revalidate-v137
cfg-idaac-revalidate-v138
cfg-alda-revalidate-v139
cfg-ppg-revalidate-v140
cfg-ibac_sni-revalidate-v141
cfg-ctrl-revalidate-v142
```

omit:

```text
NATIVE_HOST_PROFILE=v100
```

so they select the default:

```text
datasphere
```

Yet the final fleet is explicitly a V100-profile experiment.

And `gate_shared_evaluator_validated()` requires the ledger's:

```text
family_code_revision
family_config_revision
evaluator_revision
```

to equal the current revisions exactly.

Therefore, as currently defined:

\[
\boxed{
\text{successful DataSphere revalidation}
\not\Rightarrow
\text{V100 evaluator validated}
}
\]

The seven jobs currently staged for revalidation cannot discharge the V100 production evaluator gate if the gate is evaluated with `NATIVE_HOST_PROFILE=v100`.

This is a genuine preproduction-plan bug.

There are two ways to fix it.

The cleaner design is:

\[
\text{code revision}
=
H(\text{measurement-affecting source bytes})
\]

with **no host-profile term**.

Then:

\[
\text{config revision}
=
H(\text{evaluator-affecting resolved configuration}),
\]

and the resolved measurement scope separately carries device, scenes, regimes, action rule, episode count, etc.

Right now the family config revision hashes the entire family descriptor plus host profile, which means training-only changes such as replay capacity or training process count can invalidate an offline evaluator even when they cannot affect evaluation of a fixed checkpoint.

Alternatively, if you intentionally want evaluator validity to be host-profile-specific, every validation job must explicitly set `NATIVE_HOST_PROFILE=v100`, and the launch gate itself must be unambiguously run for V100.

What I would not do is keep the current hybrid, where the comments say “code identity is independent of configuration” while host configuration secretly changes the code identity.

This is **P0 before evaluator revalidation**. Fix it before spending the seven validation jobs, otherwise you may have to repeat them.

---

# The common evaluator is still 0/7 validated

The current ledger contains historical evidence for all seven evaluator families, but every modern identity field is still null:

```text
family_code_revision: null
family_config_revision: null
runtime_imports_checked: false
validation_kind: null
evaluator_revision: null
...
```

So current status is correctly:

\[
\boxed{0/7}
\]

on the new evaluator-closure scheme.

That is acceptable as a preproduction state. It is not acceptable at launch.

And because real bugs have repeatedly been found in this layer—reward units, CTRL resets, PPG witnesses, ALDA construction, device placement, regime verification—I strongly agree with retaining this gate.

But fix the host-profile identity problem first, then revalidate. Otherwise the seven new jobs are certifying an identity that production does not use.

---

# IBAC-SNI is now implementation-ready; competence is the remaining question

My assessment of IBAC itself is substantially positive now.

The current port has:

- correct joint Gaussian action likelihood via `Independent(Normal(...), 1)`;
- raw policy action stored and scored consistently for PPO;
- correct SNI noise-suspended mean-latent rollout path;
- VIB KL included;
- requested evaluation device honored;
- correct `beta=1e-4` reaching execution;
- entropy coefficient deliberately set to zero;
- process geometry back to the intended 16×128 shape;
- spawn-based child environment construction;
- independent worker seeding;
- a real 16-process/EGL functional smoke.

I no longer see an algorithmic reason to redesign the head before the next pilot.

The old competence evidence is still obsolete, however, because earlier pilots ran before the beta correction. They effectively used:

\[
\beta=1
\]

rather than:

\[
\beta=10^{-4},
\]

a factor of 10,000 on IB regularization.

The entropy experiment still tells you that:

\[
c_H=.01
\]

causes policy-scale runaway and:

\[
c_H=0
\]

removes it.

But the old zero-success result does not establish that the corrected final IBAC fails to learn.

The next 100k pilot should therefore be treated as the **first real competence test of the final configuration**:

\[
\boxed{
16\times128,\;
\beta=10^{-4},\;
c_H=0,\;
\text{current IMPALA model},
\text{ current Door wrapper}
}
\]

I would require meaningful learning—not merely finite weights and stable log-std—before paying for three 600k seeds.

This remains a P0 empirical gate, but it is no longer a code-validity concern.

---

# ALDA UTD remains a serious pre-fleet risk

This is probably the second most important algorithm-side item after the IBAC pilot.

The live production ALDA implementation still runs approximately:

\[
\mathrm{UTD}\approx1
\]

after its warmup: one learner update per new environment transition.

Your own historical ALDA work recorded that, on Lift, UTD=1.0 diverged in three runs/two seeds with critic loss exceeding approximately \(10^8\) by ~141k frames, while UTD=0.25 remained stable through 220k.

That is not proof that the current Door clone will fail:

- different task;
- different live implementation;
- previous experiments involved a retired port;
- the older rationale involving action repeat was partly wrong.

So I would not automatically change the production value.

But this is exactly the kind of prior evidence that justifies a cheap controlled pilot.

Before one 600k ALDA seed:

\[
\mathrm{UTD}=1.0
\quad\text{vs}\quad
0.25
\]

on Door, with critic loss, Q scale, actor/temperature behavior, ALDA reconstruction/disentanglement losses, return and success recorded.

I would classify that as **pilot-required**, not “optional future analysis.”

The current production gate does not elevate A27 enough for my taste.

---

# Source cleanliness is finally fixed, but source-lock provenance is still inconsistent

The artifact itself is much better:

```text
commit:
6727a1f1241b4e57ba27d4ca9f53c1bad62b46d3

tree_dirty:
false

uncommitted_paths:
0
```

That closes one of my longest-running objections.

The gate reports source freeze FAIL only because `.git` is intentionally excluded from the review ZIP. Given the artifact manifest, I would treat this as **not a real project-source blocker**, provided the actual repository still verifies clean immediately before payload construction.

However `datasphere/native/source-lock.json` still says:

```json
"nested_repository_commits": {
  "root": "f041f5e170368d298e9b5b60127faa10ba5364e5",
  ...
}
```

That is not the current clean project commit.

Project notes identify `f041f5e...` with an older/canonical architecture-transition history, while the current recovery repository has a different history.

This makes the field named `root` misleading.

The payload is fortunately strongly content-addressed by its SHA-256, so exact executable bytes are not lost. But the source-level provenance currently says two different things:

\[
\text{artifact current source}=6727a1f...
\]

versus

\[
\text{source-lock root}=f041f5e...
\]

Before final production, either update `root` to mean the actual current project commit or rename the fields explicitly, for example:

```text
current_project_commit
canonical_history_commit
nested_clone_commits
```

I would also put the current project commit explicitly into `payload_manifest.json` and `run_manifest.json`; at present the runtime manifest carries the payload SHA but not a human-readable current source commit.

This is no longer a reason to distrust the bytes, but it remains a **publication/provenance defect**.

---

# V100 production planning is now substantially sounder

The resolved V100 comparability audit now correctly sees:

- RL-ViGen replay 620k, non-evicting at a 600k run;
- CTRL 64×256, matching its upstream rollout geometry;
- IBAC 16×128, matching its upstream PPO update density;
- PPG 8×256;
- IDAAC 16×256;
- exact per-family x-axis accounting;
- effective action repeat 1 throughout.

Most importantly, the planning system no longer pretends DataSphere throughput is V100 throughput.

The V100 schedule explicitly reports throughput as:

> `UNMEASURED_ON_V100`

and the production calendar is therefore blocked rather than fabricating a precise completion date.

That is correct.

The comparability audit currently finds:

\[
6/6
\]

named **unit** axes uniform, but only:

\[
1/12
\]

named **condition** axes uniform.

That succinctly describes the scientific design.

The twelve methods still differ in frame stack, resolution, crop policy, time-limit semantics, replay/on-policy behavior, action distribution, observation representation and update density.

So this remains a benchmark of:

> released/adapted implementations at declared design points

rather than a controlled causal experiment in “algorithm identity.”

That limitation is now well documented and no longer looks hidden.

---

# PPG's current 8×256 setting is defensible

I would no longer flag this as a production defect.

At:

\[
8\times256=2048
\]

transitions per regular policy phase, and:

\[
N_\pi=32,
\]

PPG reaches an auxiliary phase every:

\[
65{,}536
\]

environment interactions.

That gives it a defensible continuous-control-scale optimization geometry.

It is not the gigantic original Procgen distributed setup, but for this continuous-control adaptation it is reasonable and preferable to changing environment count merely because more CPU is available.

The important thing is to describe it as an authored continuous-control design point rather than an exact Procgen execution reproduction.

---

# IDAAC remains the least cleanly anchored on-policy design point

This is not a correctness bug, but I would make it explicit in the report.

The current V100 IDAAC path uses:

\[
16\times256=4096
\]

samples per rollout and its Procgen-style optimization recipe.

The original authors also published a substantially different continuous-control recipe. Door does not force you to copy that recipe, but this means the current row is not an unambiguous “author-recommended continuous IDAAC” configuration.

The method should be described as an IDAAC-mechanism continuous Door adaptation with the declared current PPO design point.

Given how close the project is to launch, I would **not** introduce a broad IDAAC hyperparameter redesign now unless there is actual evidence that the current configuration cannot learn Door. The cure could become worse than the fidelity concern.

---

# The statistical protocol is now one of the stronger parts of the project

The main inference mistakes from early versions are fixed.

The protocol now correctly treats:

\[
n=3
\]

trained policies as the outer replication level rather than treating hundreds of episodes as independent RL runs.

It treats the scenes as a fixed benchmark grid.

It leads with raw quantities:

\[
R_{\rm train},
\qquad
R_{\rm OOD},
\qquad
\Delta_{\rm OOD}=R_{\rm OOD}-R_{\rm train},
\]

plus success.

Retention is secondary and competence-gated.

Endpoint-as-headline avoids checkpoint-selection bias.

This is methodologically much better.

The main remaining constraint is statistical power, not statistical correctness. With three seeds, this experiment can support large/coarse conclusions:

> method X consistently learns and loses approximately this much OOD performance.

It should not support:

> method X ranks slightly above method Y.

The project's own resolving-power analysis now acknowledges roughly that scale.

Formal owner ratification of the seed/checkpoint/estimand choices is still open, but I do not see a substantive reason to change the implemented defaults.

---

# Renderer parity, external anchor and canary remain real launch gates

These are not paperwork.

According to the artifact's current-state record, the V100 renderer-parity job was still executing when the artifact was built. Therefore production-renderer equivalence is not yet established in the material I have.

The correct comparison is already understood:

\[
R_A
=
\text{checkpoint on current evaluator/reference platform}
\]

versus

\[
R_B
=
\text{same checkpoint/evaluator/container on production V100}.
\]

Do not compare directly against the historical 480.6 result generated under an older evaluator revision.

Likewise, the external RL-ViGen anchor remains open. I still agree it should be established before the whole fleet, because an experiment-wide benchmark mistake discovered afterward cannot be repaired by retaining checkpoints alone if the measurements themselves were wrong.

And there is still no literal production-length canary through the entire final sequence:

\[
600k\ training
\rightarrow
mandatory\ endpoint\ save
\rightarrow
process\ exit
\rightarrow
fresh\ reload
\rightarrow
curve\ evaluation
\rightarrow
full\ endpoint\ grid
\rightarrow
records/provenance
\rightarrow
frozen\ statistics.
\]

Given the number of bugs this project has already found only by crossing component boundaries, I would not waive that canary.

---

# Test/release-state qualifications

I could compile the relevant source successfully.

I could not fairly claim a fresh full pytest pass from this review container. Some tests require `gym` and external reference clones/assets deliberately excluded from the review artifact. A broad run therefore hits environment/artifact exclusions.

I did find one genuine maintenance issue independent of those exclusions: four source citations still point to obsolete IBAC `general.py:66/74` lines after that logic moved into the newer runtime module. Those occur in the construction/research/audit evidence chain. Fix them before calling the documentation audit fully green.

The current release dashboard's two FAILs are therefore not, by themselves, why I recommend no-go. The substantive reasons are the evaluator-validation identity problem and the empirical launch gates above.

---

## My production sequence from here

1. **Fix evaluator identity before running the seven revalidation jobs.** Make code revision truly code-only, decide exactly which evaluation configuration belongs in config identity, and make the validation gate explicitly target the final V100 measurement identity.

2. **Run all seven evaluator revalidations** under the corrected identity and require complete diagnostics, physical placement evidence, runtime-import attestation and matching scope revisions.

3. **Run the final IBAC competence pilot** using the actual 16×128 spawn configuration, `beta=1e-4`, entropy 0 and current model. Run the short ALDA UTD 1.0-vs-0.25 Door probe.

4. **Finish renderer parity and the external RL-ViGen anchor.** Do not launch the fleet if either exposes a benchmark-level measurement discrepancy.

5. **Clean the remaining provenance ambiguity:** reconcile `source-lock`'s root identity with clean `6727a1f...`, and stamp the current source commit directly in payload/run manifests.

6. **Freeze/ratify the already-implemented owner choices** for n=3, endpoint headline, estimands and Door-only versus Door+Lift scope. I would keep the current inference/checkpoint defaults.

7. **Measure actual V100 throughput/resource behavior** rather than filling the schedule using T4 ratios.

8. **Run one complete 600k canary.** Require zero manual recovery between training, checkpoint retention, fresh-process evaluation, records and final statistics.

9. Freeze that clean commit/evaluator/container/config and then launch the fleet.

If the evaluator-identity issue is repaired and those empirical gates pass, I would be close to signing off.

The main conclusion has shifted considerably across these reviews: **I no longer regard IBAC-SNI's continuous PPO implementation as the weak link.** The current core looks technically coherent, its multi-process path is now actually exercised, and its critical beta wiring is fixed. The highest remaining risk is that the project could perform evaluator revalidation against the wrong host-profile identity and believe it has certified the final V100 measurement path when, mechanically, it has not. Fix that first.
