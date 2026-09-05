This version is substantially improved, but I still would not launch the production fleet. The important change is that the remaining problems are now concentrated: I no longer see a fundamental IBAC-SNI PPO-math defect, but I found several concrete release blockers in the actual current production path, including two that the project's own gates currently mark PASS.

I reviewed the exact uploaded artifact, ran fresh audits/tests, traced the remote-payload contract, re-read the IBAC/PPG/CTRL evaluation paths, inspected the production-host migration plan, and checked the statistical/provenance machinery.

Fresh verification on this artifact:

* `compileall`: passes.
* `audit_eval_cadence.py --check`: **12/12** anchors hold.
* `production_gates.py`: **18 PASS / 2 FAIL / 10 OWNER**, exit 1.
* `audit_comparability_seam.py`: all 6 named measurement-unit axes uniform, but only **1/10 condition axes** uniform across methods.
* Focused production/evaluator tests expose a real stale assertion: the test expects `RUNNER_CONTRACT = 10`, while production is now `12`.
* A second focused failure is only because `ext/baselines` is intentionally excluded from the review artifact; I do not count that as a real-tree defect.
* I could not fairly certify the entire repository pytest suite in this sandbox because the review artifact intentionally excludes some external sources and this environment lacks some project dependencies. I therefore do not infer whole-suite status from partial tests.

## Release verdict

| Severity | Current finding                                                                                                            | Verdict                                              |
| -------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **P0**   | Fleet-wide remote payload excludes a file required by the evaluator                                                        | **Confirmed broken**                                 |
| **P0**   | PPG placement-witness collection copies the list before evaluation                                                         | **Confirmed evaluator failure**                      |
| **P0**   | CTRL online evaluation still advances the training JAX RNG                                                                 | **Confirmed training perturbation; gate false-PASS** |
| **P0**   | Record-completeness/placement gates PASS records that do not satisfy the project's own spec                                | **Confirmed false-PASS**                             |
| **P0**   | Missing wrapper diagnostics are explicitly tolerated in production                                                         | **Irrecoverable data can be silently omitted**       |
| **P0**   | Exact production source is still dirty/unfrozen                                                                            | **79 uncommitted paths**                             |
| **P0**   | Final production hyperparameters are explicitly “NOT YET APPLIED”                                                          | **Experiment itself not frozen**                     |
| **P0**   | IBAC competence evidence is for a different process-count regime than intended final production                            | **Pilot must be repeated after final config**        |
| **P0**   | Shared evaluator has essentially not been revalidated after measurement-affecting revisions                                | **Current gate says only DrQ-v2 remains discharged** |
| **P0**   | Renderer-validation gate tells you to compare against a number another current doc explicitly invalidates for that purpose | **Protocol contradiction**                           |
| **P0**   | No production-length end-to-end canary                                                                                     | **Whole pipeline unproven**                          |
| P1       | Offline evaluation records still lack full run provenance                                                                  | Needs repair before data collection                  |
| P1       | `evaluator_revision` hashes the wrong boundary                                                                             | Partial evaluator identity                           |
| P1       | CTRL can falsely record Torch determinism as JAX determinism                                                               | Metadata bug                                         |
| P1       | PPG/IDAAC/CTRL parallelism remains far from source behavior on the final 16-core host                                      | Major declared adaptation                            |
| P1       | PPG auxiliary cadence is changed by up to an order of magnitude+                                                           | Major algorithm-dynamics adaptation                  |
| P1       | Physical placement is paired, but visual randomization is not necessarily paired across every family                       | Limits paired inference                              |
| P1       | Random floor 1.82 should be remeasured under final evaluator                                                               | Cheap protocol hardening                             |
| P1       | The project's claim that terminal-at-horizon methods are “systematically disadvantaged” is not established                 | Interpretation should be softened                    |

The first five are the ones I would fix before spending another expensive remote run.

---

## 1. The current remote evaluator is fleet-wide broken

This is the clearest release blocker.

`scripts/eval_provenance.py:23-30` defines the files required to compute the evaluator revision:

```python
members = (
    "scripts/eval_grid.py",
    "scripts/eval_across_scenes.py",
    "scripts/eval_provenance.py",
    "datasphere/native/normalize_curves.py",
    "setup/apply_patches.py",
    "rlgen/protocol.py",
)
```

and fails closed if any is absent:

```python
if not path.is_file():
    raise RuntimeError(
        f"cannot stamp evaluator revision: missing {relative}"
    )
```

But `datasphere/native/contract.py:19-45` does not include:

```text
rlgen/protocol.py
```

in `BASE_ALLOWED`.

I programmatically tested every payload family:

```text
rlvigen   False
dmc_gb    False
idaac     False
alda      False
ppg       False
ibac_sni  False
ctrl      False
```

None is permitted to ship that file.

Your own newest forensic note records the observed consequence from remote job `bt1muhrpsvpdn8kio2tm`:

```text
RuntimeError: cannot stamp evaluator revision: missing rlgen/protocol.py
NATIVE_OFFLINE_EVAL_FAILED device=cuda rc=1
```

This is not an IDAAC issue. It is structurally applicable to every remote payload that enters `eval_grid.py`.

So the present source is not capable of completing the intended production offline-evaluation stage.

The immediate fix is simple, but I would fix the class of bug, not just this instance: define the evaluator-revision member set once and test that every one of those members is contained in every payload family. Otherwise the next addition to `evaluator_revision()` can reproduce exactly this outage.

---

## 2. I found another concrete PPG evaluator break

This one is not in the project's current top-level gate output.

PPG creates a mutable witness list in `runnable/ppg/phasic_policy_gradient/envs.py:26`:

```python
placement_witnesses = []
```

Every episode reset appends to it at lines 54–73, and the same live object is exposed at line 96:

```python
venv._placement_witnesses = placement_witnesses
```

But `scripts/eval_grid.py:527-535` does:

```python
venv = get_venv(...)
...
LAST_PLACEMENT_WITNESSES.extend(
    getattr(venv, "_placement_witnesses", [])
)
while roller.episode_count < episodes:
    roller.multi_step(32)
```

`extend()` copies the list's current elements. It does not retain a reference to future additions.

Therefore the resets that happen during `roller.multi_step()` continue appending to `venv._placement_witnesses`, but **not** to `LAST_PLACEMENT_WITNESSES`.

Later `_run_grid()` enforces:

```python
if len(witnesses) != len(returns):
    raise RuntimeError(...)
```

at `eval_grid.py:902-904`.

With one environment and twenty requested episodes, the witness list copied before the loop cannot contain the twenty witnesses generated during the loop. In ordinary execution this should terminate the PPG common-grid cell.

Move the witness collection after the rollout, or retain the actual list reference instead of copying it.

There is a second PPG ordering issue in the same function: the venv is closed at `eval_grid.py:538-543`, and only **after** closure does the code call:

```python
completed_episode_diagnostics(venv, ...)
```

at lines 547–548.

Even after fixing the witness bug, diagnostics should be extracted before destroying the wrapper/process structure.

---

## 3. CTRL's training RNG is still contaminated by reporting

The current production gate says:

```text
PASS train/eval RNG isolation
```

I disagree with that PASS.

`runnable/ctrl/train_ppo.py:258-259` gets the training JAX PRNG key:

```python
train_state, state, batch, key = get_transition(..., key)
```

Then the online ID evaluator consumes and replaces it:

```python
action_id, _, _, key = select_action(
    ...,
    key,
    sample=True,
)
```

at lines 267–273.

The OOD evaluator consumes the already-advanced key and replaces it again at 276–282.

The isolation mechanism saves only NumPy:

```python
_eval_numpy_state = np.random.get_state()
```

and restores only NumPy:

```python
np.random.set_state(_eval_numpy_state)
```

The JAX key is **not restored**.

Consequently:

$$
K_{t+1}^{\rm training}
$$

depends on how much evaluation was performed between training updates.

That means reporting changes the subsequent stochastic training trajectory.

This is not a harmless reproducibility detail. In a stochastic-policy on-policy algorithm, evaluation has become part of the algorithm.

The current gate misses it because `production_gates.py:81-101` declares CTRL isolated essentially if it can find the string:

```python
np.random.get_state()
```

in the source.

That is a textbook false-PASS gate.

Use an independent evaluation key:

$$
K_{\rm train}, K_{\rm eval}
$$

with no assignment from `K_eval` back into `K_train`, or snapshot the training key before evaluation and restore it afterwards.

Then test behaviorally:

```text
next_training_key(with_eval)
==
next_training_key(without_eval)
```

The test should not inspect source strings.

---

## 4. The record-completeness gate currently certifies data you are not recording

This is particularly important because, unlike analysis decisions, omitted production data cannot be reconstructed later.

Your current specification says **every production episode row** should contain, among other fields:

```text
baseline
family
training_seed
regime
scene_id
episode_index
eval_episode_id

checkpoint_frame
checkpoint_sha256
source_commit
container_digest
evaluator_revision
effective_config

episode_return
success
time_to_success
episode_length
termination_reason

initial_placement
placement_hash
applied mode/scene

policy scale
action clipping diagnostics
```

See `notes/record-completeness-spec.md:33-63`.

But `eval_grid.py:912-932` does not emit one episode row.

It emits one **scene aggregate**:

```python
record(
    regime=regime,
    scene_set=str(scene),
    episodes=len(returns),
    episode_return_mean=...,
    success_rate=...,
    native={
        "returns": [...],
        "episode_success": [...],
        "placement_condition_seeds": [...],
        "placement_witnesses": witnesses,
        "episode_diagnostics": diagnostics,
    },
)
```

That nested structure preserves some episode-level arrays, so it is not intrinsically unusable. But it is not what the specification or gate claims.

In particular, I find no actual `eval_episode_id` emitted.

The current placement gate passes because:

```python
has_id = re.search(r"eval_episode_id|episode_index", source)
```

and `episode_index` happens to appear as a loop variable.

That is not evidence that an episode identifier reaches the record.

Similarly, `gate_record_completeness()` merely scans the source text for strings such as:

```text
episode_length
initial_placement
log_std
action_clip
```

and then says:

```text
PASS episode rows carry outcome, condition and policy diagnostics
```

This is again source-presence checking rather than schema validation.

### More seriously: missing diagnostics are intentionally allowed

Both diagnostic helpers contain:

```python
if found is None:
    return [
        {
            "diagnostics_available": False,
            "policy_scale": policy,
        }
        for _ in range(episodes)
    ]
```

So a production wrapper stack may hide:

* realized placement parameters,
* placement hash,
* raw reward statistics,
* clipping diagnostics,
* termination reason,

and production still records the cell.

That directly violates the rationale of your own record specification:

> “A row not recorded is unrecoverable without repeating the run.”

For exploratory runs, `diagnostics_available=false` is fine.

For the final fleet, this should be **fail-closed**.

---

## 5. There are two diagnostic implementations, and production uses the weaker one

This is a subtle testing seam.

`scripts/eval_provenance.py:96-149` contains the stronger implementation. When diagnostics are reachable, it verifies all required fields:

```python
required = {
    "episode_length",
    "termination_reason",
    "reward_sum",
    "reward_mean",
    "reward_min",
    "reward_max",
    "initial_placement",
    "applied_mode",
    "applied_scene_id",
    "action_clip_rate_coordinate",
    "action_clip_rate_vector",
    "action_raw_executed_l1",
}
```

and raises on omissions.

But `scripts/eval_grid.py:67-112` defines its **own duplicate** `completed_episode_diagnostics()`, and that version does not perform the required-field validation.

The tests exercise the stricter helper.

Production uses the local weaker helper.

That means you can have:

```text
test passes
production accepts malformed diagnostics
```

without either side technically contradicting itself.

Delete the duplicate and make `eval_grid` import the tested helper.

This is exactly the sort of drift a shared helper exists to prevent.

---

## 6. The evaluator revision is simultaneously too broad and too narrow

The new evaluator hash is a good idea, but its present boundary is wrong.

It hashes `rlgen/protocol.py`, even though the native evaluation path does not import that protocol for its runtime configuration. That unnecessary dependency is the direct cause of the current remote outage.

Yet it does **not** hash several inputs that actually change measurements, including important configuration/descriptors such as:

* `datasphere/native/families.json`,
* the relevant production runner configuration,
* the actual environment source/patch result,
* potentially family-specific evaluation configuration.

For example, CTRL's evaluator explicitly reads values from `families.json`, but changing that file need not change `EVALUATOR_REVISION`.

So it is possible in principle to have:

$$
\text{same evaluator revision}
$$

with a materially different evaluator configuration.

The stronger provenance identity is something like:

$$
(\text{checkpoint hash},
 \text{payload hash},
 \text{RL-ViGen asset hash},
 \text{effective config},
 \text{container digest},
 \text{evaluator code revision})
$$

rather than trying to make one hand-maintained evaluator hash carry all of those concepts.

---

## 7. Offline evaluation records still lose provenance in the cheap-return path

Training-derived records are substantially better.

`normalize_curves.py:574-619` attaches a `_run_provenance` object containing:

```text
manifest_sha256
payload_sha256
asset_sha256
container_image
requirements_native_sha256
resolved_packages
environment
egl
```

But `eval_grid.py` directly builds its record context from approximately:

```python
{
    "cell": ...,
    "baseline": ...,
    "family": ...,
    "seed": ...,
    "checkpoint_sha256": ...,
}
```

No run manifest is supplied.

Then `run_probe.sh:989-1004` creates `RECORDS_OUT` by directly concatenating:

```text
records.jsonl
offline_eval_*.jsonl
cells/*/offline_eval_*.jsonl
```

It does not enrich those offline rows with `run_manifest.json`.

So the lightweight records bundle—the exact mechanism designed to let you bring records home without downloading checkpoints—can contain an offline evaluation row with:

* checkpoint hash,
* evaluator revision,
* writer host,

but without the complete immutable runtime provenance attached to normalized training records.

The full archive can still contain `run_manifest.json`, so this is not complete data loss if every archive is retained forever. But it defeats the design goal that the returned record itself be independently auditable.

---

## 8. The source identity is still not frozen

The artifact states:

```text
Commit: 12f63229073d65ed46d364882ae0a975580277cc
Tree Dirty: True (79 uncommitted paths)
```

So that commit does not identify this source.

Separately, `source-lock.json` identifies:

```text
nested_repository_commits.root =
f041f5e170368d298e9b5b60127faa10ba5364e5
```

which is a different root identity.

That might have a historical explanation, but as a provenance artifact it is currently ambiguous.

The source-freeze gate is improved since the previous version: in an artifact without `.git`, it now **fails closed** rather than declaring an empty `git status` clean.

That is good.

But the real fact remains: the version whose behavior you are about to fund does not yet have one immutable source identity.

A payload SHA mitigates this operationally, but for a research result I still want one canonical commit corresponding to the production source.

---

## 9. Current tests and gates are still lagging the source

A small but concrete example:

```text
contract.py:
RUNNER_CONTRACT = 12
```

while:

```python
tests/test_production_defaults.py:
assert "RUNNER_CONTRACT = 10" in contract
```

That test fails freshly in this artifact.

It is not an RL bug. It shows that this exact candidate has not completed its source→tests→release synchronization cycle.

Likewise the current gate result is:

```text
18 pass
2 fail
10 owner
NOT LAUNCHABLE
```

The two technical failures are:

```text
source tree frozen
release suite green
```

I agree with the no-launch result.

I also would not use `audit_implementations.py`'s `7/12 genuine` output literally on this review artifact. The five RL-ViGen methods are reported `UNRESOLVED` because the audit expects an external absolute-path asset which this review artifact deliberately excluded—even though the corresponding source tree is included elsewhere in the artifact. That is an audit portability defect, not proof those five algorithms are absent.

---

# IBAC-SNI specifically

My view of IBAC is now considerably better than it was in the first review.

The continuous PPO core is internally coherent.

The head uses:

```python
Independent(
    Normal(mean, exp(log_std)),
    1
)
```

so `log_prob()` and `entropy()` are joint action quantities rather than accidental per-coordinate quantities.

Rollout actions are sampled raw and the raw action is what is stored and later scored. I see no clipped-action likelihood-ratio corruption.

SNI rollouts use the noise-suspended bottleneck mean. During VIB training both clean and noisy policies contribute PPO loss, consistent with the intended selective-noise construction.

The evaluator now correctly moves the loaded model to its requested device:

```python
self.acmodel.to(self.device)
```

and preprocessing uses the same device.

So my former CPU-policy issue is fixed.

`entropy_coef=0` remains defensible here. Because `log_std` is global rather than \(z\)-dependent,

$$
H[q(a|z)]
=
C+\sum_i\log\sigma_i
$$

does not actually vary with \(z\). In this authored continuous version, that term is primarily global scale pressure, not a rich conditional-entropy regularizer.

The controlled evidence that `0.01` drives scale upward while `0.0` arrests it therefore supports using zero.

### The new IBAC problem is configuration validity

The current descriptor still says:

```text
procs = 1
frames_per_proc = 128
```

while `_production_host_targets` explicitly says final production should use:

```text
procs = 16
```

to match the original source process count.

That is not just a throughput change for PPO.

It changes:

* rollout batch size,
* minibatch count,
* optimizer-update ordering,
* gradient-noise properties,
* number of updates per collected frame.

The current ~25k `entropy=0` pilot was evidence about the low-process configuration.

It is **not** evidence that the exact `procs=16` final configuration learns Door.

Your own A1 says “pilot at the exact final config.” Therefore A14 has to be applied **before** A1 is considered satisfied.

For IBAC I would do:

$$
\text{final procs}=16
\rightarrow
100k\ \text{pilot}
\rightarrow
\text{policy-scale + success + train-return check}
\rightarrow
600k
$$

not pilot at `procs=1`, change the optimization dynamics, then call the production run validated.

### One smaller IBAC fidelity note

The new PyTorch IMPALA trunk reproduces the original broad architecture, but convolutional initialization comes from PyTorch defaults; `initialize_parameters()` specially initializes only `Linear` modules.

That does not invalidate it. It reinforces the correct description:

> continuous-action PyTorch adaptation of IBAC-SNI

rather than an exact implementation reproduction.

---

# PPG is still a serious fidelity problem even after fixing its evaluator

The production-host migration improves PPG from 8 to 16 environments.

But upstream is documented as:

$$
4\ {\rm MPI}\times 64\ {\rm envs}
=
256\ {\rm environments}.
$$

With 256 steps per rollout:

$$
256\times256
=
65{,}536
$$

environment transitions per global policy phase.

The current 8-env version collects:

$$
8\times256=2{,}048,
$$

a **32×** reduction.

The proposed 16-env production version collects:

$$
16\times256=4{,}096,
$$

still a **16×** reduction.

More importantly, `n_pi=32` has not been rescaled.

So upstream's auxiliary phase occurs at roughly:

$$
32\times65{,}536
\approx2.10{\rm M}
$$

global environment frames.

At 16 environments yours occurs around:

$$
32\times4{,}096
=
131{,}072.
$$

That's a 16× earlier auxiliary cadence per environment frame.

At a 600k budget:

* upstream-scale cadence would not even reach its first global auxiliary phase;
* the 16-env adaptation reaches roughly four;
* the current 8-env adaptation reaches roughly nine.

This is not a minor engineering difference. It changes how much PPG is “PPG” over the 600k horizon.

There is no perfect fix if the benchmark insists on one 600k budget for all methods. You need to declare the choice:

* preserve `n_pi=32` and accept much more frequent auxiliary updates;
* rescale `n_pi` to preserve global-frame cadence, in which case the mechanism may barely/not run at 600k;
* or give PPG a different horizon, abandoning same-frame-budget comparison.

Any is publishable if explicit. None is a canonical PPG reproduction under the current setup.

The same phenomenon exists, less dramatically, for IDAAC and CTRL because environment count determines synchronous rollout/update geometry.

---

# The production-host migration is not yet a configuration

`families.json` itself says:

> “PRODUCTION-HOST TARGETS, NOT YET APPLIED.”

The current production source still carries DataSphere-safe values:

```text
IBAC:   1 process      → target 16
IDAAC:  4 processes    → target 16, source 64
PPG:    8 envs         → target 16, source 256
RL-ViGen replay: 300k  → target 1M
CTRL:   16 envs        → source 64
```

Your measured host has:

```text
16 CPU cores
113 GiB available RAM
2 × V100 32 GiB
```

so some of the DataSphere adaptations can indeed be removed.

But until those values are actually moved into a separate final production descriptor and all pilots/cost estimates are rerun against it, you do not yet have **the experiment that will be run**.

Also, the host snapshot shows GPU 0 occupied by another 15 GiB process. The calendar estimate that assumes two available V100s should not be treated as an operational guarantee until exclusive GPU allocation is known.

---

# Common-evaluator validation remains weak

The current production gate correctly changed its language:

> DrQ-v2 remains discharged; IDAAC's former result is suspended.

So effectively only one shared-evaluator burden is presently trusted.

That matters because the shared evaluator is doing a lot of custom integration:

* reconstruction of CTRL TrainState,
* custom ALDA construction,
* PPG Roller integration,
* staged IBAC model directory,
* IDAAC VecMonitor/raw-reward semantics,
* DMC-GB environment recreation,
* RL-ViGen native policy evaluation.

The fact that all of these “run” is not equivalence.

Before fleet evaluation I would require, per distinct evaluator family, one competent checkpoint where:

$$
\text{native evaluator estimate}
$$

and

$$
\text{common evaluator estimate}
$$

agree within a predeclared Monte-Carlo tolerance under the **current evaluator revision**.

The payload bug currently prevents that revalidation anyway.

---

# Your old renderer anchor cannot be used as presently written

This is an internal contradiction in the current source.

`notes/RESULTS-VALIDITY.md:34-39` explicitly says the old DrQ-v2 100k value around 480.6 predates:

* per-episode condition seeding,
* deterministic-kernel evaluation,
* strict regime verification,

and therefore:

> re-measure the probe baseline on the current evaluator before migrating.

I agree.

But `gate_production_renderer_verified()` still recommends:

> reproduce DrQ-v2 100k train-regime **480.6** on the production host.

That does **not** isolate renderer effects.

A mismatch could be caused by evaluator revision rather than the renderer.

Correct experiment:

1. current evaluator + current source + current known platform → measurement \(R_A\);
2. same checkpoint/evaluator/container on production platform → measurement \(R_B\);
3. compare \(R_A\) to \(R_B\).

Only then is platform/renderer the principal changed factor.

The same argument means the 1.82 random-policy floor should be rerun cheaply under the final evaluator if you're going to use it as a hard numerical competence threshold.

---

# The CTRL determinism metadata has another subtle bug

The new record spec asks for:

```text
deterministic_algorithms: true | false
```

The evaluator does:

```python
try:
    import torch
    torch.use_deterministic_algorithms(True)
    DETERMINISTIC_ALGORITHMS = True
except ...:
    pass
```

and comments that JAX-only CTRL has no Torch dependency.

But `requirements-native.txt` globally installs Torch.

So a CTRL evaluation can successfully import Torch and record:

```text
deterministic_algorithms = true
```

even though CTRL's policy and computations are in JAX and `torch.use_deterministic_algorithms()` governs none of them.

That boolean should be backend-specific, e.g.:

```text
determinism_backend = "torch"
torch_deterministic_algorithms = true
```

versus:

```text
determinism_backend = "jax"
jax_prng_seeded = true
```

Do not stamp a Torch setting as a property of a JAX measurement.

---

# I would weaken one claim in the project's scientific framing

The project repeatedly describes the nine methods that zero-bootstrap at Door's horizon as “systematically disadvantaged” and describes bootstrapping as the correct treatment.

The **difference** is unquestionably real and should be reported.

The **directional judgment** is not established.

If the 500-step horizon defines the benchmark's finite episodic task, then zeroing the value target at the endpoint is a perfectly coherent finite-horizon objective.

If the 500 steps are meant as an artificial truncation of a continuing MDP, bootstrapping is the natural convention.

Those are different task semantics.

Because evaluation itself is a fixed 500-step episodic score, I would not state categorically that terminal handling is “wrong” or that it disadvantages those methods without a controlled ablation demonstrating the direction.

Say instead:

> methods retain their native time-limit semantics; three bootstrap and nine terminate, so their learning targets differ near the horizon.

That is fully defensible.

---

# Cross-method comparisons are still implementation-at-design-point comparisons

The latest comparability audit is unusually clear:

```text
UNITS:      6/6 named axes uniform
CONDITIONS: 1/10 named axes uniform
```

The methods differ in:

* training-time scene coverage,
* time-limit handling,
* 64 / 84 / 100 pixel rendering,
* crop policy,
* replay semantics,
* one-frame versus three-frame observability,
* induced action distribution,
* observation format/scaling,
* native evaluation capabilities.

This does not invalidate the study.

It determines the claim.

A valid headline is:

> visual-generalization behavior of these twelve released/adapted implementations on RL-ViGen Door under their declared design points.

A much weaker claim would be:

> algorithm A's mechanism is inherently better than algorithm B's.

Your primary within-method contrast—

$$
R_{\rm OOD}-R_{\rm train}
$$

with the learned policy held fixed—is much cleaner than causal cross-method ranking.

The one-frame/four-method group is especially worth emphasizing: on pure RGB Door, one frame hides velocity, whereas three frames expose motion information. Those methods are operating under different effective observability.

---

# Statistical plan: now mostly sound, but not yet authoritative

The revised proposal fixed the main problems from my previous review.

It now correctly says:

$$
n=3
$$

training policies, not 600 episode replicates.

It treats the ten scenes as a fixed benchmark grid.

It correctly rejects cross-method training-seed pairing.

It demotes retention and promotes:

$$
R_{\rm train},\quad
R_{\rm OOD},\quad
\Delta=R_{\rm OOD}-R_{\rm train},
$$

plus success rate.

And endpoint-as-headline is the clean checkpoint rule.

I agree with those choices.

But they still live in `notes/proposal-inference-and-checkpoint-selection.md`, while the production gate correctly reports the statistical protocol and checkpoint rule as OWNER decisions.

There are still values to freeze before seeing production results:

* competence margin \(\delta\),
* missing/crashed-seed policy,
* primary contrasts versus full pairwise matrix,
* Door-only versus Door+Lift,
* exact production-process counts,
* exact handling of incomplete evaluator cells.

The data-collection bug is more urgent than these because protocol choices can often be made before analysis; missing episode diagnostics cannot be recreated.

---

## Priority order before any production spend

1. **Fix the payload contract** and add a dependency-closure test so every evaluator-revision member is guaranteed inside every payload.
2. **Fix PPG's witness/diagnostic timing**, then execute an actual 20-episode PPG grid cell and assert 20 witnesses + 20 complete diagnostics.
3. **Fix CTRL's JAX training/eval RNG separation** and replace the current source-string gate with a behavioral invariant test.
4. **Make record completeness real:** one explicit episode structure/ID, complete realized placement and diagnostics, no `diagnostics_available=false` in production; remove the duplicate weaker diagnostic helper.
5. **Attach full run provenance to offline rows**, not only the archive beside them; fix evaluator identity so it hashes actual measurement dependencies.
6. **Freeze and commit the exact source**, reconcile `source-lock`, regenerate all tests/audits, and make the release surface completely green.
7. **Apply the final V100-host configuration first.** Recompute resource/throughput planning. Explicitly document the PPG/IDAAC/CTRL residual parallelism adaptations.
8. **Then run the IBAC 100k pilot at the actual final `procs=16` configuration.** Require stable policy scale and genuine training competence, not just absence of divergence.
9. **Remeasure the random floor and renderer baseline under the current evaluator**, then do the production-host renderer transfer check.
10. **Revalidate every distinct common-evaluator family under the current evaluator revision.**
11. **Freeze the analysis/checkpoint/scope/missing-run protocol.**
12. **Run one complete 600k canary through training → checkpoint retention → clean reload → full grid → lightweight records → final analysis. Only then launch the fleet.**

The largest change in my assessment is this: **I am now reasonably comfortable with the IBAC-SNI continuous PPO core itself.** I would not redesign its head again before the pilot. The project is being held back by the measurement and production-control layer, plus substantial cross-method fidelity adaptations—not by an obvious hidden error in the IBAC likelihood or SNI objective.

The largest newly discovered code issue in this version is the PPG witness-copy bug; the largest fleet-wide issue is the payload/evaluator contract mismatch; and the largest scientific issue remaining is that the exact production learning dynamics have not yet been frozen, especially for PPG/IDAAC/CTRL and the planned IBAC `1 → 16` process change.

