This version is considerably closer, but I would still give it a **NO-GO for the final fleet**. The remaining blockers are no longer broad uncertainty about the RL implementation; they are a smaller number of concrete production-integrity failures that could generate expensive results with the wrong checkpoint, wrong protocol, or an unexecutable IBAC configuration.

Fresh checks on this exact artifact: compilation of the relevant source succeeds; all 12 evaluation-cadence anchors hold; the current production gate returns **23 PASS / 3 FAIL / 11 OWNER** and `NOT LAUNCHABLE`; targeted checkpoint, production-default, CTRL-pairing, diagnostic-fail-closed, payload/provenance, evaluator-device, endpoint/curve-scope and x-axis tests pass except for an external-source test whose required `ext/` tree is deliberately absent from the review artifact. I did not treat this sandbox's missing `gym` dependency as a project failure.

My current priority assessment is:

| Severity | Finding | Status |
|---|---|---|
| **P0** | IBAC V100 profile requests `procs=16` despite measured failure already at `procs=2` under the exact fork/live-EGL architecture still present | **Confirmed** |
| **P0** | New safe-checkpoint mechanism can leave an old fixed-name checkpoint behind and still let it be evaluated/labeled as the new endpoint | **New confirmed issue** |
| **P0** | A 600k run requires an explicit host profile but does **not** require `NATIVE_PRODUCTION=1`; production protocol can therefore silently remain unapplied | **New confirmed issue** |
| **P0** | Exact source remains unfrozen: artifact reports **177 uncommitted paths** | **Confirmed** |
| **P0** | Current evaluator revision has **0/7 evaluator-family validations** | **Confirmed by project gate** |
| **P0** | IBAC previous competence evidence predates the corrected `beta=1e-4` wiring | **Previous evidence no longer validates final config** |
| **P0/P1** | V100 executable configuration and the production schedule/comparability audits describe different experiments | **Confirmed** |
| **P0** | No 600k end-to-end canary through the actual final pipeline | **Open** |
| **P0 owner** | Statistical, seed, checkpoint and scope rules are not authoritative/frozen | **Open** |
| P1 | 13 claimed hyperparameters remain unlocated by the executable hyperparameter audit | **Partial certification only** |
| P1 | Checkpoint finiteness is tested after expensive trajectory/endpoint evaluation rather than before | **Operational waste/failure sequencing** |
| P1 | Production environment variables can override frozen production defaults without an explicit override authorization | **Protocol footgun** |
| P1 | PPG/IDAAC/CTRL retain substantial source-parallelism adaptations | **Scientific limitation** |

Several major earlier findings are now closed. The payload/evaluator dependency bug is repaired; the PPG witness collection bug is fixed; CTRL's common-evaluator double-reset bug is fixed; production endpoint diagnostics now fail closed; the duplicated weaker diagnostic implementation is gone; IBAC evaluation honors the requested device; the container is digest-pinned; CTRL raw-reward evaluation is corrected; the policy-mode metadata is truthful; and the IBAC beta is now actually passed on the command line.

Those fixes materially increase my confidence in the project.

## 1. The new checkpoint safety mechanism creates a stale-endpoint failure mode

This is the most important new issue I found.

`runnable/_shim/safe_checkpoint.py:85-151` deliberately makes a failed checkpoint write nonfatal:

```python
write_fn(tmp)
os.replace(tmp, path)
return True
...
return False
```

That design is sensible for an **intermediate** checkpoint: missing one curve point is preferable to killing a 40-hour training process.

But callers generally ignore the returned boolean.

For the five RL-ViGen methods, `RL-ViGen-upstream/train.py:352-381` writes the primary checkpoint to the fixed path:

```python
snapshot = self.work_dir / 'snapshot.pt'
...
safe_torch_save(payload, snapshot, ...)
```

without checking success.

At the endpoint, it does:

```python
self.save_snapshot()
print(f'NATIVE_FINAL_EVALUATION_COMPLETED frame={self.global_frame}')
```

again without knowing whether the endpoint checkpoint was actually written.

Suppose a valid 550k `snapshot.pt` already exists and the 600k save fails because of temporary disk pressure. `safe_write()` intentionally preserves the old destination and returns `False`.

Training then still emits the 600k completion marker.

`datasphere/native/family.py:350-363` subsequently retains the checkpoint by checking only:

```python
checkpoint.is_file()
checkpoint.stat().st_size > 0
```

It does not verify its internal `_global_step`.

Then `run_endpoint_eval()` passes the expected frame explicitly:

```text
--snapshot snapshot.pt
--frame 600000
```

at `run_probe.sh:536-569`.

So there is a credible path:

\[
\text{550k policy bytes}
\rightarrow
\text{retained snapshot}
\rightarrow
\text{recorded/evaluated as 600k}.
\]

The SHA-256 correctly identifies the bytes, but it does not tell downstream analysis that those bytes are from the wrong training step.

IBAC has the same structural issue. `torch_rl/utils/save.py:24-34` writes fixed `model.pt`, ignores the result, and the training loop later logs:

```text
Model successfully saved
```

unconditionally. An old model and a newer status/log can therefore disagree.

This needs a distinction between checkpoint classes. Periodic saves may fail nonfatally. The **terminal checkpoint of record must not**. A failed terminal save should invalidate the cell before retention/evaluation. For formats containing an internal frame counter, assert:

\[
f_{\rm checkpoint}=f_{\rm expected}.
\]

For overwrite-style methods, I would also prefer retaining an endpoint-stamped file rather than trusting the generic fixed filename.

This is release-blocking because it can produce a completely plausible, finite, hashed, successfully evaluated result with the wrong policy.

## 2. A 600k run can accidentally run without the production protocol

`datasphere/native/run_probe.sh:383-399` applies the production descriptor only if:

```bash
[[ -n "${NATIVE_PRODUCTION:-}" ]] || return 0
```

That setting controls important behavior including endpoint evaluation, trajectory evaluation, online-eval disabling/isolation, checkpoint cadence and RL-ViGen's production replay override.

At production scale, however, the hard guard at lines 415–427 checks only that the host profile was explicitly selected:

```bash
if [[ "${FRAMES:-10000}" -ge 600000 &&
      "${NATIVE_HOST_PROFILE_EXPLICIT:-0}" != "1" ]]; then
    exit 3
fi
```

It does **not** require:

```text
NATIVE_PRODUCTION=1
```

I found no executable launcher/config inside this artifact that makes that flag unavoidable.

Therefore this is accepted by the runner in principle:

```text
FRAMES=600000
NATIVE_HOST_PROFILE=v100
NATIVE_PRODUCTION unset
```

and it can train a full 600k cell while silently not applying the intended production measurement protocol.

The code even handles that case gracefully later: if `ENDPOINT_EVAL` is absent it prints:

```text
NATIVE_NO_ENDPOINT_GRID
```

and continues rather than failing.

That is too dangerous for a final experiment.

At production scale I would require, mechanically:

\[
\texttt{FRAMES}\ge600000
\Rightarrow
\texttt{NATIVE\_PRODUCTION}=1.
\]

Better still, production-scale frames could imply production mode automatically, with an explicit separate flag needed to run a non-production 600k diagnostic.

There is a related issue: `apply_production_settings()` deliberately lets already-set environment variables win over the descriptor:

```text
NATIVE_PRODUCTION_KEPT ... job config overrides the default
```

That is useful during development, but means one forgotten smoke-test variable can silently modify the final endpoint episode count, save cadence, replay cap, etc.

For the final fleet, I would fail on conflicting overrides unless something explicit like `ALLOW_PRODUCTION_OVERRIDE=1` is provided and recorded.

## 3. IBAC `procs=16` is still not a runnable production configuration

The project's own gate correctly marks this FAIL.

`families.json:615-625` says:

```text
base procs = 1
V100 procs = 16
```

but the same file immediately records measured evidence that `procs=2` dies at parallel-environment initialization under Linux EGL.

The production implementation has not changed the architecture responsible for that failure.

`torch_rl/scripts/train.py:109-145` still:

1. forces multiprocessing `"fork"`;
2. creates every Robosuite/MuJoCo environment in the parent;
3. then gives those live objects to `ParallelEnv`.

The worker implementation at `torch_rl/.../utils/penv.py:18-35` still does:

```python
p = Process(target=worker, args=(remote, env))
p.start()
```

with the already-created environment.

There is also no child-worker RNG reseeding in `worker()`.

So the V100 profile currently says “16” for an execution architecture that the project has empirically demonstrated cannot run “2.”

A V100 does not inherently make inherited EGL contexts fork-safe.

This needs to be resolved before the next IBAC competence pilot. Either retain `procs=1` and explicitly declare the reduced rollout geometry as an adaptation, or redesign the multiprocessing path so each worker starts without an inherited MuJoCo context, constructs its own environment inside the child, and receives independent deterministic seeds.

Only after that should you test:

\[
\beta=10^{-4},\qquad
c_H=0,\qquad
\text{final process architecture}.
\]

## 4. The beta correction means the old IBAC competence evidence is obsolete

The current version correctly passes:

```text
--beta 1e-4
```

and the fresh executed-hyperparameter audit confirms:

```text
ibac_sni vib_beta  claimed=1e-4 executed=1e-4 AGREES
```

That is an important repair.

Previously, the launcher silently inherited the training parser's default:

\[
\beta=1.0.
\]

Thus earlier IBAC runs used an information-bottleneck KL penalty **10,000 times** larger than the intended \(10^{-4}\).

So the old observations should now be separated into two categories.

The entropy ablation remains useful:

\[
c_H=0.01
\Rightarrow
\text{scale runaway},
\]

while

\[
c_H=0
\Rightarrow
\text{runaway removed}.
\]

That is a matched comparison inside the old setup.

But claims about Door competence are not transferable. A policy trained under \(\beta=1\) does not tell you whether the corrected \(\beta=10^{-4}\) system learns Door.

I therefore agree with the current gate that IBAC competence remains unresolved.

The good news is that, after re-reading the current source again, I still do **not** see a reason to redesign the Gaussian PPO head before that pilot. The raw action is scored consistently, `Independent(Normal(...),1)` gives the correct joint likelihood over action dimensions, and the SNI/VIB path remains internally coherent.

## 5. The executable V100 experiment and the green planning/audit tools disagree

This is now important because you are approaching actual scheduling.

The current V100 production descriptor resolves the five RL-ViGen methods to:

```text
replay_capacity = 620000
```

at `families.json:25-31`.

The rationale is sensible: at a 600k Door budget it should be non-evicting while fitting two cells more plausibly on a 113-GiB host.

But `scripts/audit_comparability_seam.py:645-675` still explicitly reads:

```python
descriptors["rlvigen"]["production"]
```

rather than the selected host-profile-resolved configuration.

Its prose consequently still describes:

```text
300k DataSphere recency ring
```

and even says the V100 target is “1e6, deliberately unapplied.”

That is stale relative to executable V100 configuration.

Similarly, `datasphere/native/production-schedule.json` is still a DataSphere schedule:

- `gt4.1` / `gt4i.1`,
- DataSphere throughput,
- DataSphere RAM/VRAM limits,
- 300k RL-ViGen replay.

Yet the production gate reports:

```text
PASS schedule matches protocol
PASS replay audit is honest
```

because those gates do not verify that the schedule/audit corresponds to the **selected final host profile**.

Near production, that is not sufficient.

I would make `host_profile` an explicit required input to the schedule generator and comparability audit, then have the gate compare the generated schedule against the same resolved descriptor used by the launcher.

The invariant should look more like:

\[
\operatorname{schedule}(\text{v100})
=
\operatorname{resolved\ executable\ config}(\text{v100})
\]

for process counts, replay capacity, endpoint rounding, resources, checkpoint cadence and evaluation workload.

Right now a green schedule gate can describe a different deployment.

## 6. Final source provenance is still not acceptable

The artifact manifest reports:

```text
source_commit =
12f63229073d65ed46d364882ae0a975580277cc

tree_dirty = true
177 uncommitted paths
```

So the commit does not identify the bytes under review.

Separately, `source-lock.json` carries another root commit identity. That may have a historical explanation, but it is not a clean answer to:

> Which exact source generated the production result?

The project now has strong payload hashing, environment metadata and a pinned container digest. Those are good.

Before the canary I would still insist on one immutable clean source revision, regenerated source lock, regenerated evaluator hash, regenerated payload hash and fresh tests from exactly that revision.

This becomes particularly important now because fixes are landing fast enough that some notes become obsolete during the same day.

## 7. The current evaluator validations are all stale by the project's own standard

The fresh gate reports:

```text
0/7 evaluator families validated on CURRENT revision
```

with all previous family validations belonging to a superseded evaluator revision.

I would not waive this now.

You have repeatedly found real semantic evaluator bugs—CTRL reward normalization, CTRL reset sequencing, PPG witness ordering, diagnostic access, regime verification. The history shows that “it runs and returns a plausible number” is not sufficient.

After the last evaluator-affecting fix, freeze the evaluator revision once and re-run one native-vs-common reconciliation for each distinct family:

- RL-ViGen;
- DMC-GB;
- IDAAC;
- ALDA;
- PPG;
- IBAC-SNI;
- CTRL.

The checkpoint safety correction itself need not change evaluation mathematics, but I would resolve it first because it determines which bytes are presented to the evaluator.

## 8. Checkpoint validation occurs too late in the cell

`run_probe.sh:253-285` currently does:

```text
verify final marker
retain checkpoint
curve evaluation
endpoint evaluation
check checkpoint finite
```

So a corrupt/NaN checkpoint can consume the complete trajectory evaluation and an 800-episode endpoint grid before the runner finally checks finiteness.

This does not cause a bad row to be accepted if the final check works—the cell eventually fails—but it can waste many GPU-hours.

The order should be closer to:

\[
\text{retain}
\rightarrow
\text{identity/frame check}
\rightarrow
\text{finite check}
\rightarrow
\text{curve}
\rightarrow
\text{endpoint}.
\]

The new terminal-checkpoint identity test belongs at the same early gate.

## 9. The hyperparameter audit is useful, but not a production certification yet

Fresh output now finds no known contradiction, which is an improvement.

But it also says **13 claimed values are UNLOCATED**, including method-defining parameters for CTRL, ALDA, PPG, SGQN and IBAC/SNI.

Examples include:

```text
CTRL clusters/window/coefficient
ALDA num_steps
IBAC sni_lambda
PPG aux_epochs / auxiliary clone beta
SGQN aux_update_freq
```

“UNLOCATED” explicitly means the auditor cannot establish whether the claim reaches execution.

Given that the IBAC beta error had exactly the form:

> documentation says X; launcher never passes X; clone default silently wins,

I would not call this gate globally PASS in the human-facing release dashboard.

Its actual result is closer to:

> No contradiction found among certified values; 13 values remain uncertified.

For final release, I would manually close the method-defining subset rather than trying to make an automatic parser understand every configuration framework.

## 10. PPG remains a major declared adaptation

The final V100 profile uses 16 PPG environments rather than the source's much larger global Procgen parallelism.

With 256 rollout steps:

\[
16\times256=4096
\]

transitions per policy phase.

With `n_pi=32`, an auxiliary phase arrives after approximately:

\[
32\times4096
=
131{,}072
\]

environment frames.

Under the source-scale \(4\times64\) environment arrangement:

\[
4\times64\times256
=
65{,}536
\]

frames per policy phase, giving:

\[
32\times65{,}536
=
2{,}097{,}152
\]

frames before an auxiliary phase.

So at a 600k budget the V100 adaptation runs several auxiliary phases while the source-scale cadence would not reach its first.

That does not mean the row is invalid. It means the study cannot simultaneously preserve source global-frame cadence, preserve `n_pi=32`, and enforce a common 600k budget.

That decision belongs in the frozen method protocol, not buried as a machine-resource detail.

IDAAC and CTRL have related, smaller rollout-geometry adaptations.

## 11. The statistical plan is now mostly defensible

The revised inference proposal is no longer a major methodological concern for me.

The important choices are correct:

\[
n=3
\]

trained policies is the outer replication level, not 600 episode rows.

The ten scenes can be treated as a fixed benchmark grid.

Raw outcomes should lead:

\[
R_{\rm train},
\quad
R_{\rm OOD},
\quad
R_{\rm OOD}-R_{\rm train},
\]

plus Door success.

Retention should be secondary and competence-gated.

Endpoint-as-headline avoids checkpoint-selection bias.

And shared physical placement should be interpreted as evaluation-noise control, not as pairing of “seed 1” training trajectories across different algorithms.

What remains is to promote that proposal into the authoritative protocol and freeze the numerical choices before results arrive.

The current decision tracker still reports **22 owner decisions**, although some are historical/stale register items rather than twenty-two genuinely undecided design choices. The important live ones are the seed minimum/retry policy, competence threshold, primary headline metric/contrast, checkpoint rule, task scope, PPG cadence treatment and final parallelism settings.

One small inconsistency to clean up: some proposal/decision text still uses the older random floor around 1.82, while the current project gate says the floor has been remeasured as approximately **1.842** over 200 paired episodes.

## 12. Cross-method interpretation remains intentionally limited

The comparability audit's broad result is still informative even though its V100 replay section is stale:

- common units are mostly harmonized;
- experimental conditions are not.

The methods differ in frame stack, resolution, crop policy, time-limit treatment, replay/on-policy mechanics, policy distribution, evaluation action convention, optimizer geometry and training architecture.

Therefore I still recommend framing the experiment as:

> visual-generalization performance of twelve released/adapted implementations on RL-ViGen Door under their declared design points.

The project should not use a rank ordering as if it were a causal intervention on algorithm identity alone.

The one-frame versus three-frame split is particularly substantial because it changes effective observability from RGB, not merely encoder capacity.

Likewise four methods sample evaluation actions while others use deterministic actions. Their reported returns are native-method estimands rather than precisely identical policy-evaluation functionals.

None of this blocks the benchmark if stated accurately.

## Production sign-off sequence

I would use this exact order now:

1. **Fix terminal checkpoint semantics first.** A terminal save failure must fail the cell; assert checkpoint frame identity before any offline evaluation. Make overwrite-style checkpoints impossible to mislabel.

2. **Require production mode mechanically at production scale.** `FRAMES>=600000` should not be able to execute without the full frozen production descriptor. Reject accidental conflicting overrides.

3. **Resolve IBAC multiprocessing.** Do not run the beta-correct competence pilot until the exact final process architecture is known and demonstrated to run. If `procs=16` is retained, worker-side environment construction and RNG seeding need actual validation.

4. **Freeze the V100 descriptor and regenerate every dependent artifact**—schedule, replay/comparability audit, resource model and commands—from that same host profile. Measure V100 throughput rather than projecting from DataSphere.

5. **Commit the exact tree and regenerate all provenance.** Zero unexplained dirty paths, one source identity, one evaluator revision, one payload, one digest-pinned runtime.

6. **Re-run the corrected IBAC pilot** with `beta=1e-4`, `entropy_coef=0`, final process geometry and exact final observation/model settings. Require actual competence, not merely stable `log_std`.

7. **Revalidate all seven evaluator families on the final evaluator revision**, including complete endpoint diagnostics and actual placement witnesses.

8. **Freeze the statistical/checkpoint/seed/scope protocol and close the important unlocated hyperparameters.**

9. **Perform the current-evaluator external anchor and renderer-transfer test** before the fleet.

10. **Run one literal 600k canary end to end**: train, mandatory endpoint save, process exit, fresh reload, full curve + endpoint evaluation, records/provenance collection and frozen final analysis. Only after that passes would I authorize the twelve-method fleet.

My assessment of the underlying RL is now more favorable than my assessment of the production wrapper. **IBAC-SNI's continuous PPO/SNI core is not the reason I would hold the launch.** The current hard blockers are the impossible `procs=16` execution target, terminal-checkpoint integrity, production-mode enforcement, stale V100 planning artifacts, and absence of current-revision evaluator/canary evidence.

Those are tractable. But two of them—the stale-checkpoint path and optional production mode—are exactly the type that can produce an expensive dataset that looks valid afterward. I would fix those before any production-scale run.
