For this run, I would define resilience narrowly: **a hardware/process/storage failure may waste compute, but must not silently change the experiment, corrupt an accepted result, or make it impossible to reconstruct what actually ran.**

I would make the following the production requirements.

1. **Every cell is immutable once it starts.** A cell is identified by baseline, training seed, frozen source revision, resolved effective config, container/runtime identity, and evaluator revision. A retry uses the same scientific configuration. No “small fix and continue this seed” after seeing partial behavior; changed code/config means a new attempt lineage.

2. **Retries preserve the original training seed.** Do not substitute a new seed because one crashed. Your current missing-run policy already has the right principle: rerun the identical seed, never choose replacements after seeing results, and report a genuinely missing seed as missing rather than manufacturing \(n=3\). 

3. **Resume only where resume is genuinely state-complete.** This is the main resilience rule I would insist on. A checkpoint is resumable only if it restores everything that materially determines subsequent learning: model parameters, optimizer state, schedules/counters, RNG state, and—where applicable—replay state or an equivalent complete reconstruction.

   For the RL-ViGen-style off-policy jobs in this tree, ordinary model checkpoints do not give you a faithful replay-buffer resume. Therefore a failed production cell should ordinarily **restart the same seed from frame 0**, not resume from a 300k/400k policy checkpoint with an empty replay buffer. A longer rerun is much preferable to quietly changing the latter half of the experiment.

4. **Checkpoint writes must never destroy the last good checkpoint.** Write to a temporary/new path, finish serialization, flush/close, and only then publish/rename it. Keep at least the previous completed checkpoint when writing the next one. Your existing 50k retention strategy is already well suited to this; I would not add elaborate transactional machinery beyond preventing partial files from masquerading as valid checkpoints.

5. **A checkpoint is not accepted merely because the file exists.** At minimum, record size/hash and enough metadata to know its intended frame, seed, baseline and source revision. On reload for evaluation, mismatch or deserialization failure should fail the record rather than fall back to another checkpoint.

6. **Training and evaluation failures are separated.** If training reaches its declared endpoint and the offline evaluation later fails, keep the completed training checkpoint and retry evaluation against that exact checkpoint. Do not retrain just because evaluation delivery/rendering failed. Conversely, do not call a cell complete merely because training exited zero if the required endpoint record was never successfully produced.

7. **No learning-metric auto-restarts.** Do not automatically kill/restart because reward is low, success is zero, a curve looks strange, or one baseline is much worse than expected. Those can be legitimate results. Automatic aborts should be reserved for clearly invalid execution: NaN/Inf in required state, process death, CUDA/OOM, corrupt checkpoint, disk exhaustion, renderer failure, impossible environment state, or violated production invariants.

8. **Numerical health should be observed, not over-controlled.** Log the already-important diagnostics—loss finiteness, policy log-std where relevant, raw→executed action clipping, replay/update counters, frame count. If something becomes non-finite, fail loudly. If something is merely extreme but finite, retain the evidence and let the predefined policy decide; do not invent an emergency hyperparameter change inside the run.

9. **Fail closed on wrong hardware/runtime identity.** Production should refuse to start if the expected GPU/backend, renderer mode, source/evaluator closure, container/environment identity, or required assets are absent. In particular, CTRL should not quietly run on JAX CPU fallback, and an EGL/rendering mismatch should never become a valid result just because the Python process completed.

10. **Resource exhaustion should be anticipated at the cell level.** Before launch, establish enough RAM/VRAM/disk for the resolved configuration with margin. Do not rely on packing estimates for an unmeasured shape such as CTRL-64. Once measured, packing is fine; I would not require dedicated hardware per baseline if coexistence has been demonstrated.

11. **Disk exhaustion must be a controlled failure, not late corruption.** At launch, verify sufficient workspace for the expected replay/checkpoints/logs plus margin. During a multi-day cell, monitor free space. If the safety reserve is crossed, stop cleanly before a checkpoint/write failure rather than continuing until arbitrary files fail.

12. **Retain failure evidence.** A failed attempt should keep its stdout/stderr, resolved config, attempt ID, last valid checkpoint(s), resource record and failure reason. Do not overwrite it with the successful retry. The final result can point to the successful attempt while the audit trail explains why an earlier attempt was ineligible.

13. **Exactly one authority decides whether an attempt is eligible.** Avoid different scripts independently deciding that a run “counts.” A production record should become eligible only when the frozen criteria agree: correct source/runtime identity, required training endpoint, valid checkpoint, correct evaluator identity, valid endpoint evaluation, and complete provenance. Your external-review design already correctly requires final effective manifests, frozen source, evaluator validation, checkpoints and delivery/metric validity before final claims. 

14. **RNG perturbation by support machinery is forbidden unless explicitly part of the method.** Logging, checkpointing, health monitoring and offline evaluation must not consume the training RNG stream. Native online evaluation is allowed only where it is intentionally part of the source method and its RNG semantics are understood. This is why I consider the step-zero “disabled evaluation” issue from my previous review worth fixing rather than merely documenting.

15. **A rerun never silently incorporates a newly fixed tree.** If you fix production code after seed 101 fails, either the fix is demonstrably execution-only and leaves the hashed scientific closure unchanged, or seeds already produced under the old closure become a different revision and must not be mixed without explicit treatment. The review blueprint already makes source/revision identity a prerequisite to final readiness rather than an afterthought. 

16. **External interruption should degrade to “retry this cell,” not “repair the experiment.”** Machine reboot, scheduler kill, transient filesystem/network problem, GPU loss, or evaluation-delivery failure should all have simple deterministic responses. The best resilience design for 36 expensive but independent cells is not a sophisticated distributed recovery system; it is strong cell isolation plus reliable rerunability.

A few softer requirements are worth having but I would not delay production to overengineer them: periodic heartbeat/resource sampling; a clear maximum wall-time with graceful termination before the scheduler's hard kill; copying final checkpoints/results to a second durable location; and a machine-readable attempt ledger mapping retries to their original cell.

The most useful operational state machine is probably just:

**PLANNED → RUNNING → TRAINED → EVALUATED → ELIGIBLE**

with side states **FAILED-TRAIN**, **FAILED-EVAL**, and **INVALID**.

`FAILED-TRAIN` normally means restart the same seed from zero unless that particular family has a verified full-state resume. `FAILED-EVAL` means reuse the exact completed checkpoint. `INVALID` means the run completed computationally but violated provenance/runtime/protocol invariants and therefore cannot enter the scientific table.

I would specifically avoid three kinds of “resilience” because they damage the experiment: adaptive hyperparameter recovery after instability, automatically replacing failed seeds, and opportunistically resuming off-policy policies without their replay state. Those make the fleet more likely to finish, but less likely to mean what you intended.

If the items above hold, I would consider the run operationally resilient enough for production without building a large fault-tolerance framework.
