This version is closer to production, but I still recommend **NO-GO for the final fleet**. The core RL implementations are increasingly defensible; the remaining problems are concentrated in a few production-critical paths.

I used the supplied review/debugging/verification guidance where applicable. Fresh checks on this artifact include `compileall`, the production gates, comparability audit, pairing audit, executed-hyperparameter audit, V100 production-plan resolution, targeted production/checkpoint tests, and direct source traces through the current algorithm/evaluator paths. I did not run the complete real-environment suite because this review environment lacks some dependencies/assets intentionally excluded from the artifact; I do not infer whole-suite status from that limitation.

Fresh `production_gates.py` result:

> **25 PASS / 3 FAIL / 12 OWNER — NOT LAUNCHABLE**

`compileall` succeeds on the production/evaluator/algorithm tree.

## Current release assessment

| Severity | Finding | Assessment |
|---|---|---|
| **P0** | IBAC V100 `procs=16` is incompatible with its current MuJoCo multiprocessing implementation | Confirmed; project already measured failure at `procs=2` |
| **P0** | IBAC workers would inherit identical placement RNG streams even if the fork/EGL crash were fixed | Confirmed independently |
| **P0** | Corrected IBAC `beta=1e-4` means the previous competence pilots tested the wrong algorithm configuration | Needs new pilot |
| **P0** | Source is still not immutable: artifact says **185 uncommitted paths** | Final results cannot yet be bound to one source revision |
| **P0** | **0/7** evaluator families are validated on the current evaluator revision | Current common-grid numbers are not yet certified |
| **P0** | ALDA's common evaluator constructs its trainer incorrectly and allocates a completely unnecessary ~15 GiB replay state | New confirmed issue |
| **P0/P1** | ALDA production runs at UTD≈1.0 despite this project previously measuring catastrophic instability at 1.0 on Lift | Needs Door pilot before 600k |
| **P0** | No current-pipeline external RL-ViGen anchor, renderer-transfer proof, or literal 600k end-to-end canary | Still open |
| **P0 owner** | Statistical/checkpoint/seed/scope protocol not frozen | Must happen before outcomes exist |
| **P1** | Run manifest misstates the final marker for rounded-endpoint methods | New concrete provenance defect |
| **P1** | Production environment variables can still silently override frozen production defaults | Near-release footgun |
| **P1** | “claimed hyperparameters executed: PASS” includes **13 UNLOCATED** values | Gate overclaims |
| **P1** | “pairing proven physically: PASS” includes one group with **no physical evidence** | Gate overclaims |
| **P1** | CTRL representation learner receives raw Gaussian action although environment transition may use clipped action | Live port-semantic question |
| **P1** | IDAAC is using its Procgen-style PPO recipe despite an author-published continuous-control recipe that is substantially different | Needs explicit design-point decision |
| **P1** | Checkpoint finiteness is checked after potentially expensive curve + endpoint evaluation | Wastes many GPU-hours on a bad checkpoint |
| **P1** | One IDAAC real-environment test can still turn a genuine `RuntimeError` into a skip | Release-test weakness |
| Scientific | Three seeds cannot support a fine twelve-method ranking | Claims need strict bounding |

Several important previous problems are genuinely fixed: production-scale runs now require `NATIVE_PRODUCTION`; terminal fixed-name checkpoint saves fail closed; CTRL's double-reset pairing bug is fixed; PPG witness collection is fixed; endpoint diagnostics fail closed; payload/evaluator dependency closure is fixed; evaluator provenance is stronger; the V100 plan is now generated from the resolved V100 descriptor; and IBAC's requested evaluation device and `beta=1e-4` wiring are correct.

---

## 1. IBAC multiprocessing remains the immediate hard blocker

The V100 descriptor still resolves IBAC to:

```text
procs = 16
frames_per_proc = 128
```

But `runnable/ibac_sni/torch_rl/scripts/train.py` still forces multiprocessing `"fork"`, constructs live Robosuite/MuJoCo environments in the parent, and then `ParallelEnv` sends those already-created objects into child processes.

The project already empirically established that this architecture dies at **two processes** under EGL. Configuring it for sixteen is therefore not an untested optimization; it contradicts an observed failure.

There is a second independent correctness issue in `torch_rl/.../utils/penv.py`:

```python
def worker(conn, env):
    while True:
        ...
```

The worker never reseeds NumPy or Python randomness.

Door placement depends on global NumPy state. With `fork`, the child processes inherit the parent's RNG state. Even if you somehow make the inherited MuJoCo contexts work, multiple rollout workers can start with identical placement RNG streams.

That defeats much of the intended diversity of the 16-environment PPO batch.

I see three credible configurations:

\[
16 \times 128 = 2048
\]

with environments constructed inside independently seeded workers; or retain `procs=1` and explicitly accept the adaptation; or a potentially useful middle design, **`procs=1`, `frames_per_proc=2048`**, which preserves the original 2048-sample PPO batch/update cadence without multiprocessing. The latter changes temporal/data diversity but preserves optimization batch size much better than the current 1×128 fallback.

Whichever you choose must be the configuration used for the next competence pilot.

---

# 2. IBAC's previous competence evidence is obsolete

The beta issue is now fixed properly:

\[
\beta=10^{-4}
\]

actually reaches the process.

Before this fix, the parser default of:

\[
\beta=1
\]

was silently used.

That's a **10,000× stronger information-bottleneck KL penalty** than the project believed it was testing.

Consequently, previous conclusions separate into two groups.

The entropy experiment remains informative because it was internally controlled:

\[
c_H=0.01 \Rightarrow \text{policy-scale runaway}
\]

versus

\[
c_H=0 \Rightarrow \text{runaway arrested}.
\]

I still support keeping `entropy_coef=0` for this continuous adaptation.

But:

\[
\text{old beta=1 run failed to solve Door}
\]

tells us very little about whether:

\[
\beta=10^{-4},\;c_H=0
\]

solves Door.

So the next IBAC run is not “one more precautionary pilot.” It is effectively the **first competence test of the final algorithm**.

I would run it only after the multiprocessing decision is resolved.

---

# 3. I found a new ALDA evaluator defect

This is concrete and should be fixed before ALDA evaluator validation.

`scripts/eval_grid.py::_alda_trainer()` currently does:

```python
trainer = create_instance_from_spec(...)
trainer.initialize_env_dmc(spec)
trainer.build(spec)
```

But `runnable/alda/trainers/alda_trainer.py::build()` itself does:

```python
self.initialize_env_dmc(spec)

self.buffer = utils.ReplayBuffer(
    ...
    capacity=self.buffer_capacity,
)
```

So offline evaluation initializes ALDA's environment stack **twice**.

The first train/color/distractor environment set is overwritten without being closed. This is exactly the kind of unnecessary EGL/MuJoCo context creation that has already caused reliability trouble elsewhere in the project.

More importantly, `build()` also creates ALDA's training replay buffer.

The evaluator comment says:

> “construction is cheap ... allocation happens in training, which is never reached here.”

That statement is false.

`ReplayBuffer.__init__()` immediately executes:

```python
if prefill:
    self._obses = prefill_memory(
        self._obses, capacity, obs_shape
    )
```

with:

\[
\text{capacity}=1,000,000.
\]

At 3×64×64 uint8 alone, the image payload is about:

\[
1,000,000 \times 3\times64\times64
\approx 11.44\ {\rm GiB},
\]

before Python-object overhead and the action/reward arrays. That matches the project's measured ~15.3 GiB ALDA training footprint.

So **every ALDA offline evaluator startup allocates the enormous training replay buffer even though evaluation never uses it**.

For intermediate checkpoints this expense is repeated process-by-process.

Fix `_alda_trainer()` to follow the native training construction exactly—call `build()` once—and give evaluation a non-training replay configuration (`prefill=False`, capacity 1, or a dedicated model-only build path) before validating the evaluator.

This is one of the highest-value fixes in the present version.

---

# 4. ALDA UTD is now a genuine preproduction risk

The latest comparability audit correctly added the previously missing axis:

> `updates per env frame`

Current Door execution is roughly:

- RL-ViGen five: 0.5 learner updates/environment transition;
- RAD/SODA: 1.0;
- ALDA: 1.0;
- on-policy methods: not meaningfully represented by the same scalar.

ALDA's training loop makes this explicit:

```python
if step >= self.init_steps:
    num_updates = self.init_steps if step == self.init_steps else 1
    for _ in range(num_updates):
        self.update(...)
```

After warmup, that's one update per Door transition.

The worrying part is not merely cross-method comparability. This project already has experimental evidence from its earlier ALDA work that UTD=1.0 diverged on Lift across three runs/two seeds by roughly 141k, while UTD=0.25 remained stable through 220k.

Those regression tests currently protect the **retired `rlgen` ALDA port**, not `runnable/alda`, which is what production actually launches.

That does not prove Door will diverge at UTD 1.

But I would absolutely not spend on a 600k ALDA seed before running something like:

\[
\text{Door, UTD}=1.0
\quad\text{vs}\quad
0.25
\]

far enough to examine:

- critic loss;
- Q magnitude relative to reward scale;
- policy entropy/temperature;
- reconstruction/quantization loss;
- return.

This is a cheap discriminating experiment relative to a failed 600k run.

---

# 5. The run manifest has a new endpoint-marker provenance bug

The runner correctly computes each family's actual endpoint before accepting the training job.

For V100 at a requested 600k:

\[
\begin{aligned}
\text{IDAAC} &= 598{,}016,\\
\text{PPG} &= 600{,}064,\\
\text{IBAC-SNI} &= 600{,}064,\\
\text{others} &= 600{,}000.
\end{aligned}
\]

The per-cell verification correctly uses these family-specific values.

But after all cells finish, `run_probe.sh` does:

```bash
export FINAL_EVALUATION_MARKER=
"NATIVE_FINAL_EVALUATION_COMPLETED frame=$frames"
```

where `$frames` is still the **requested** budget.

The manifest then searches each training log for that requested-frame marker.

For IDAAC, PPG and IBAC, it therefore looks for a marker that a correct run should never emit.

Result: a successfully verified IDAAC run can have:

```json
"completed": true,
"snapshot_retained": true,
"final_evaluation_marker": null
```

while the manifest's top-level `final_evaluation_marker` contains the wrong 600000 value.

This doesn't appear to corrupt the actual policy result, because the earlier verifier uses the correct expected endpoint. But it makes the provenance artifact contradict successful execution.

The manifest should record the per-cell `expected_endpoint`, not one job-level requested-frame marker.

Add a regression test specifically using IDAAC or PPG. The existing test only checks that the marker field/string exists, which cannot catch this bug.

---

# 6. Production-mode enforcement is fixed; production overrides are not

A previous serious footgun is now correctly closed.

At ≥600k, `run_probe.sh` requires both an explicit host profile and `NATIVE_PRODUCTION`. Good.

But `apply_production_settings()` still does:

```bash
if [[ -z "${!prod_key:-}" ]]; then
    export "$prod_key=$prod_value"
else
    echo "NATIVE_PRODUCTION_KEPT ... job config overrides the default"
fi
```

So a stale environment variable from a smoke/debug run can silently override the supposedly frozen production descriptor.

The run remains valid-looking and production-labeled.

Near release, I would invert this rule.

If:

\[
\texttt{NATIVE\_PRODUCTION}=1
\]

and an ambient value disagrees with the resolved descriptor, abort unless an explicit mechanism such as:

```text
ALLOW_PRODUCTION_OVERRIDE=1
```

is present. Record every authorized difference.

Development convenience is no longer worth ambiguity at 600k.

---

# 7. Checkpoint safety is much better, but validation order is inefficient

The former stale-checkpoint hazard is substantially fixed: terminal fixed-name saves are now mandatory/fail-closed. Targeted checkpoint tests passed.

That is a substantial improvement.

But `run_probe.sh` still runs:

\[
\text{retain}
\rightarrow
\text{curve eval}
\rightarrow
\text{800-episode endpoint eval}
\rightarrow
\text{check-finite}.
\]

If a retained policy is NaN/corrupt, you can pay for every evaluation before discovering it.

Move:

```text
checkpoint existence
checkpoint identity / endpoint
finite-value check
```

immediately after retention.

Only a validated checkpoint should enter the expensive evaluator.

---

# 8. The release dashboard still turns “not established” into PASS

Two examples remain.

The hyperparameter gate currently says:

> **PASS — claimed hyperparameters executed**

while its own detailed output says:

> **13 could not be located and are NOT certified.**

Some are method-defining:

```text
ALDA num_steps
CTRL cluster/window/coefficient parameters
IBAC sni_lambda
PPG aux_epochs
PPG beta_clone
SGQN aux_update_freq
```

Given that the IBAC beta defect was *exactly* a case where documentation claimed one value while an unnoticed default executed another, this distinction matters.

The correct gate state is approximately:

> **PARTIAL / OWNER — no known contradiction among located parameters; 13 claims unverified.**

Likewise, the physical-pairing gate says PASS while the fresh audit actually reports:

```text
5 comparisons:
0 known unpaired
1 with NO PHYSICAL EVIDENCE
```

“Not demonstrated to be wrong” is not the same as “proven physically.”

This matters less once you regenerate final endpoint records with required diagnostics, but the release dashboard should preserve the distinction.

---

# 9. Current-revision evaluator validity is still 0/7

This remains an absolute preproduction requirement for me.

The current gate correctly reports:

> **0/7 evaluator families validated on evaluator revision `05d3d1c...`**

Every old reconciliation belongs to a superseded measurement path.

This is not bureaucratic. The project has repeatedly found real common-evaluator defects:

- incorrect reward units;
- double resets;
- missing regime readback;
- misplaced PPG witness collection;
- device mismatch;
- diagnostic loss;
- and now ALDA's construction discrepancy.

Fix the ALDA issue and any remaining evaluator bug first. Then freeze the evaluator revision.

Then reconcile one competent policy per evaluator family:

```text
rlvigen
dmc_gb
alda
idaac
ppg
ibac_sni
ctrl
```

against the corresponding native measurement path.

I would not start three production seeds of any family before its evaluator family is discharged.

---

# 10. PPG is better justified in this version than I previously gave it credit for

Current V100 PPG is back to:

\[
8\ {\rm envs}\times256=2048
\]

samples per policy iteration.

With:

\[
N_\pi=32,
\]

an auxiliary phase occurs every:

\[
2048\times32=65{,}536
\]

interactions.

This does have a relevant continuous-control precedent: the IDAAC authors' DMC experiments used **2048 steps, one process**, and for PPG found \(N_\pi=32,E_\pi=1,E_V=1,E_{aux}=6,\beta_{clone}=1\). 

So I withdraw the simplistic earlier objection that PPG's 8-env configuration is inherently the wrong cadence.

It still isn't a literal reproduction—the temporal/data-diversity geometry of one 2048-step process and eight 256-step environments differs—but matching the aggregate 2048-step policy-phase size is a defensible continuous-control design point.

The original Procgen PPG setup, by contrast, used four workers ×64 environments, 256-step rollouts, \(N_\pi=32\), \(E_{aux}=6\), and \(\beta_{clone}=1\). 

Current PPG should therefore be described as using the **continuous-control-scale rollout design point**, not the Procgen parallel design.

---

# 11. IDAAC's design point deserves more scrutiny than PPG's now

Current IDAAC still inherits its Procgen-oriented defaults:

\[
\gamma=.999,\quad
\text{entropy}=.01,\quad
lr=5\times10^{-4},
\]

one PPO epoch, eight minibatches, 256 steps ×16 environments, and one image frame.

But IDAAC's authors actually published a continuous-control configuration. Their DMC appendix reports:

\[
\gamma=.99,\quad
\lambda=.95,\quad
2048\text{ steps},\quad
1\text{ process},
\]

with three stacked frames, 10 PPO epochs, entropy coefficient 0, learning rate \(3\times10^{-4}\), and 32 minibatches; those values were selected for their continuous-control experiments. 

Door is not DMC, so this does **not** prove you should simply copy those settings.

But for an authored continuous-action Door port, the continuous-control recipe is at least as relevant a fidelity anchor as the categorical Procgen one.

I would record the present IDAAC row explicitly as:

> IDAAC mechanism + Procgen-style optimization recipe + continuous Gaussian Door adaptation

unless you run a small design-point comparison.

This does not need a huge sweep. One representative pilot comparing the current configuration against the authors' continuous-control PPO geometry would substantially strengthen the row's interpretation.

---

# 12. CTRL still has a subtle raw-vs-executed action question

CTRL's PPO probability accounting is fine: it needs the raw sampled Gaussian action for its log probability and PPO ratio.

But its representation/cluster update also consumes the stored action.

Robosuite may clip that raw action before physical execution.

That creates two action variables:

\[
a_{\rm policy}
\]

and

\[
a_{\rm executed}
=
\operatorname{clip}(a_{\rm policy}).
\]

For PPO:

\[
a_{\rm policy}
\]

is the correct one.

For CTRL's transition representation, the semantic question is different: the representation is attempting to model a transition that was generated by \(a_{\rm executed}\), not necessarily \(a_{\rm policy}\).

Original discrete CTRL doesn't have this distinction.

I would not globally replace stored actions—doing so would break PPO probability semantics.

Instead separate them:

```text
policy_action   → PPO/log probability
executed_action → candidate CTRL representation input
```

and run a short sensitivity comparison, together with the actual production vector-level clipping rate.

This is a port question rather than a proven failure.

---

# 13. The three-seed design is suitable for coarse claims, not ranking twelve methods

The project's updated seed-power analysis is now substantially more candid.

With three training seeds, its estimate says differences on the order of roughly **50% of return scale** are what the design can resolve comfortably under its current variance proxy. And that variance proxy comes from same-seed backend variation, so genuine training-seed variation may be larger.

This is not an argument that three seeds are worthless.

It means the experiment is suitable for:

> does method X generalize at all, and what is the rough magnitude of its OOD degradation?

It is poor for:

> method A is slightly better than method B.

Twelve methods give 66 pairwise comparisons. With \(n=3\), a ranked table without prominent uncertainty would invite interpretation the design cannot support.

I agree with the current proposed analysis:

\[
R_{\rm train},
\quad
R_{\rm OOD},
\quad
\Delta_{\rm OOD}=R_{\rm OOD}-R_{\rm train},
\]

all individual seed points, success rate, and intervals/effect sizes; retention secondary.

Endpoint should be the headline checkpoint.

Those rules still need to become the authoritative protocol before results exist.

---

# 14. One narrow test weakness remains

The real-environment smoke tests have improved substantially: generic runtime errors no longer broadly become skips.

One exception remains in `tests/test_family_regime_readback.py`.

The IDAAC environment construction path does:

```python
except RuntimeError as error:
    if "regime" in str(error):
        raise AssertionError(...)
    pytest.skip(...)
```

Any genuine IDAAC runtime defect that happens to raise `RuntimeError` without the word `"regime"` therefore becomes a skipped test.

Near production, a successfully imported environment that crashes while being constructed should normally fail.

Skip only explicit missing-renderer/platform/dependency conditions.

---

# 15. Source identity remains unresolved

The review artifact says:

```text
base commit:
12f63229073d65ed46d364882ae0a975580277cc

tree_dirty:
true

uncommitted_paths:
185
```

Therefore that commit does not identify the code I just audited.

A payload SHA is useful, and the runtime/container provenance is much stronger now. But before the canary and definitely before the fleet, I still want:

\[
\boxed{
\text{one clean source commit}
+
\text{source lock}
+
\text{payload hash}
+
\text{container digest}
+
\text{evaluator revision}
}
\]

all generated from the exact same state.

The current source-freeze gate correctly fails closed.

---

## What I would require before pressing production

1. Fix IBAC multiprocessing, including **both** EGL-safe environment construction and worker RNG independence. Choose the final rollout geometry.
2. Fix `_alda_trainer()`: eliminate duplicate environment initialization and do not allocate a million-transition replay buffer merely to evaluate a checkpoint.
3. Run the corrected IBAC pilot at `beta=1e-4`, entropy 0 and the exact final rollout geometry. Run the cheap ALDA UTD stability pilot.
4. Fix the rounded-endpoint manifest marker bug and move checkpoint identity/finiteness checks before offline evaluation.
5. Make production descriptor conflicts fail closed unless an explicit override is authorized.
6. Downgrade/fix the hyperparameter and pairing gates so `UNLOCATED` / “no physical evidence” cannot render as PASS; close the method-defining unlocated knobs manually.
7. Freeze the evaluator revision and revalidate all seven evaluator families.
8. Decide the remaining method-design questions, especially IDAAC's Procgen-vs-continuous-control recipe and CTRL's raw-vs-executed action representation semantics.
9. Commit the tree and regenerate all source/runtime/provenance identities.
10. Freeze the statistical, seed, endpoint, missing-run and scope rules; explicitly constrain three-seed claims.
11. Establish the current-pipeline RL-ViGen positive anchor and renderer-transfer measurement.
12. Run one **literal final 600k canary** from clean source through terminal save → process exit → fresh checkpoint load → trajectory evaluation → 800-episode endpoint grid → records/provenance → frozen analysis.

If those pass, I would be substantially more comfortable approving the fleet.

The largest change in my assessment is that I am now **more confident in the actual RL cores than in earlier reviews**. IBAC's Gaussian PPO/SNI machinery does not look like the main risk. PPG's current 2048-sample policy-phase geometry also has a defensible continuous-control reference. The immediate problems are much more concrete: **IBAC's currently impossible multiprocessing configuration, ALDA's evaluator/replay construction and stability risk, missing current-revision evaluator validation, and final source/protocol freeze**.
