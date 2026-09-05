# Codex parallel pre-production plan — DRAFT FOR REVIEW

> **Status:** proposed work while Claude continues in the same tree. Nothing in this document
> authorizes a production run, source-freeze commit, merge or push. The plan is dependency-ordered;
> “done” means executable evidence, not prose or a green static token search.

## Outcome

Reach one stable production candidate in which the remaining mechanical defects are repaired, the
V100 experiment is generated from one resolved descriptor, all seven evaluator families are
reconciled on the final evaluator revision, and the exact container/renderer/canary path is proven
before the fleet. Preserve researched operational defaults while keeping genuine owner decisions
visible until ratified.

## Current ownership boundary

Claude answered Q18-Q21 and explicitly assigned these areas to Codex:

1. IDAAC full VecEnv→trainer→storage episode identity.
2. IBAC-SNI multiprocessing/environment construction/worker RNG.
3. V100-resolved production schedule and comparability artifacts.
4. CWD-independent physical-pairing production gate.

Claude has already completed terminal-checkpoint fail-closed handling, the production-mode guard,
and the curve-evaluation 3-vs-5 correction. Those are verification inputs, not work to duplicate.
Claude also reports current evaluator *execution* for all twelve baselines; this is not the same as
native/common evaluator reconciliation, and the live gate correctly remains 0/7.

## Rules while both agents are active

- Modify only the four assigned areas and their new/focused tests.
- Re-read every target immediately before patching and inspect concurrent diffs afterward.
- Do not run the full suite until the code/config hash stops moving.
- Do not build or submit evaluator-validation jobs until `families.json` and evaluator-revision
  members are frozen; otherwise all results become stale by construction.
- DataSphere remains T4-only (`gt4.1`/`gt4i.1`), at most four concurrent jobs. Never use DataSphere
  V100. Final V100 checks run on the actual production host.
- Do not commit, merge, push, delete generated history, or clean either working tree.
- Refresh clone patch snapshots only after clone edits settle, then verify against `ext/`.

## Dependency graph

```text
CWD gate ───────────────────────────────────────────────┐
IDAAC state-machine repair ─────────────────────────────┤
IBAC process/RNG repair ──> final IBAC pilot ───────────┤
V100 resolved planner ──────────────────────────────────┤
                                                       v
                                    freeze evaluator/config revision
                                                       |
                              seven-family native/common reconciliation
                                                       |
              renderer R_A→R_B + positive anchor + short V100 throughput
                                                       |
                                  exact 600k end-to-end canary
                                                       |
                               full suite + source freeze candidate
```

## Work package 1 — make the pairing gate independent of caller CWD

**Priority:** first; small, isolated, no scientific choice.

**Files:**

- Modify `scripts/production_gates.py`, only `gate_pairing_proven_physically()`.
- Add focused coverage to `tests/test_production_gates.py` or a new
  `tests/test_production_gate_cwd.py` if isolation is clearer.

**Plan:**

- [ ] Write a regression test that invokes the absolute `production_gates.py` from a temporary
  working directory and from the repository root against the same records.
- [ ] Assert the physical-pairing gate status/detail are identical in both invocations.
- [ ] Verify the test fails because the child `audit_pairing_evidence.py` resolves its default glob
  relative to the caller.
- [ ] Add `cwd=ROOT` to that child `subprocess.run` call.
- [ ] Run the new test and the existing production-gate tests.
- [ ] Run the gate from the repository and `/tmp`; compare the complete pairing row, not only exit
  status.

**Closure evidence:** one regression test plus two real invocations with identical output.

## Work package 2 — repair IDAAC episode identity through the real state machine

**Priority:** highest algorithm-correctness item.

### Defect to preserve in the failing test

At an episode boundary, Baselines `DummyVecEnv` returns the newly reset episode's observation with
the terminal transition's old `info`. `_LevelSeed.step()` currently puts only the old episode ID in
that `info`. The trainer reads it as the level for the returned observation. Then
`IDAACRolloutStorage.insert()` advances `self.step` before writing `levels[self.step + 1]` and
`nsteps[self.step + 1]`, introducing another index shift. Wrapper-only tests cannot catch either
join error.

**Files:**

- Modify `runnable/idaac/ppo_daac_idaac/envs.py`.
- Modify `runnable/idaac/train.py`.
- Modify `runnable/idaac/ppo_daac_idaac/storage.py`.
- Add `tests/test_idaac_episode_identity_pipeline.py`.
- Refresh `runnable/_patches/idaac.patch` only after the fix passes.
- Update the corresponding construction/register item after executable proof.

### Test design

- [ ] Move or expose the episode-ID wrapper/helper at module scope so the test drives the actual
  implementation rather than copying it.
- [ ] Build a tiny RGB Gym environment whose observation encodes `(physical_episode, timestep)` and
  whose horizon is two steps.
- [ ] Wrap it in the actual `_LevelSeed` equivalent, Baselines `DummyVecEnv`, and the same tensor
  conversion path used by training.
- [ ] Execute a rollout crossing at least two auto-resets.
- [ ] Feed every returned observation, chosen level ID and nstep through the real
  `IDAACRolloutStorage.insert()`.
- [ ] Assert each `obs[k]`, `levels[k]` and `nsteps[k]` describe the same physical episode/time.
- [ ] Seed `before_update()`, inspect selected partner observations, and assert every equal-level
  pair remains inside one physical episode.
- [ ] Verify this integration test fails on the current code while the old wrapper-only test still
  passes; that demonstrates the missing seam.

### Minimal semantic repair

- [ ] On a terminal transition, make the wrapper expose both the completed episode ID and the next
  episode ID that `DummyVecEnv` will assign during its automatic reset. The next ID must be derived
  from the wrapper's authoritative episode counter, not guessed from rollout position.
- [ ] In the trainer, select the level ID corresponding to the **returned observation**: current
  level for nonterminal steps, next level for auto-reset steps.
- [ ] Initialize `rollouts.levels[0]` from the actual initial episode identities rather than waiting
  for the first transition to back-fill it.
- [ ] In storage, write `levels` and `nsteps` to the same destination index as the observation before
  advancing the circular pointer.
- [ ] Preserve raw transition `info["level_seed"]` for compatibility; use an explicit next-observation
  field rather than silently changing what the old key means.

### Verification

- [ ] Run the new integration test, existing port-semantic tests, storage tests and IDAAC focused
  evaluator tests.
- [ ] Add a mutation check: reverting either the auto-reset selection or the storage write order
  must fail the new test.
- [ ] Run a zero/short local fake-environment trainer path to ensure initialization works at rollout
  index 0 and across `after_update()` carry-over.
- [ ] Refresh `idaac.patch`; run `scripts/refresh_clone_patches.py --check` and
  `scripts/deviations.py` against the real `ext/` source.
- [ ] Do not use old IDAAC competence/evaluator comparisons to validate the repaired training
  mechanism. Any training evidence predating this fix is marked pre-fix.

**Closure evidence:** real-stack integration invariant, mutation sensitivity, patch reproduction,
and one bounded post-fix CUDA training smoke after the revision freezes.

## Work package 3 — resolve IBAC-SNI process construction and physical RNG

**Priority:** second P0; design before implementation.

### Required semantics

- No live MuJoCo/EGL object crosses a process boundary.
- Every worker constructs its environment inside that worker before first reset.
- Every worker receives a deterministic stream derived from `(training_seed, worker_index)`.
- Python, NumPy and Torch RNGs are seeded inside the worker before environment construction.
- Repeated launches reproduce each worker's placement sequence; distinct workers do not share one.
- `procs=1` remains functional and provides a conservative fallback, but is not silently called
  equivalent to the intended 16-process design.

**Files likely involved:**

- `runnable/ibac_sni/torch_rl/torch_rl/torch_rl/utils/penv.py`
- `runnable/ibac_sni/torch_rl/scripts/train.py`
- possibly a small module-level, picklable environment factory under
  `runnable/ibac_sni/torch_rl/torch_rl/torch_rl/utils/`
- `runnable/_launch/ibac_sni.sh` and `datasphere/native/families.json` only after the process design
  is demonstrated
- new `tests/test_ibac_parallel_env.py`
- refreshed `runnable/_patches/ibac_sni.patch`

### Design and local tests

- [ ] Write a picklability test for the proposed factory/spec; closures and already-created env
  objects are forbidden inputs to workers.
- [ ] Refactor the training entry point under a real `main()`/`if __name__ == "__main__"` boundary
  before adopting `spawn` or `forkserver`; otherwise child import can execute training recursively.
- [ ] Pass a serializable environment specification containing env name, worker index, base seed,
  observation mode and wrapper choices.
- [ ] In each child, derive a seed with `numpy.random.SeedSequence([base_seed, worker_index])`, seed
  Python/NumPy/Torch, then construct the environment.
- [ ] Decide explicitly whether worker 0 remains local. If it does, run the identical factory/seed
  path in the parent; do not leave worker 0 with different RNG semantics.
- [ ] Make worker startup report a small handshake: worker index, derived seed and successfully
  constructed observation/action-space signatures. Parent startup fails if any handshake is absent.
- [ ] Make worker exceptions propagate with traceback/context instead of surfacing only as pipe
  `EOFError`.
- [ ] Ensure all workers close envs and pipes on normal exit and parent failure.

Use a tiny fake environment to test 1, 2 and 16 workers locally without MuJoCo. Assert deterministic
per-worker sequences, cross-worker distinction, reset-after-done behavior, exception propagation and
cleanup. These tests validate orchestration, not EGL.

### Remote validation sequence

- [ ] On allowed DataSphere T4i, run only a bounded `procs=2` startup/training smoke to establish
  that child-side construction removes the measured fork/EGL crash. Do not use DataSphere V100.
- [ ] Inspect placement witnesses from several resets per worker; repeated job with the same seed
  must reproduce them and worker streams must differ.
- [ ] On the actual production V100 host, run `procs=16` startup plus a bounded training smoke,
  measuring CPU saturation, RSS, VRAM, transitions/s and shutdown behavior.
- [ ] Only after `procs=16` works, run the beta=`1e-4`, entropy=`0` competence pilot at the exact final
  model/input/process geometry.
- [ ] If the proper multiprocess path cannot be made reliable, set `procs=1` as an explicit fallback
  adaptation and recompute rollout/update cadence and cost. Do not retain a knowingly impossible 16.

**Closure evidence:** fake-env process tests, T4i EGL smoke, V100 16-worker placement/RNG witness,
and final-geometry competence pilot.

## Work package 4 — generate V100 planning and audits from one resolved descriptor

**Priority:** before any evaluator hash freeze or production scheduling.

### Problem

`plan_production.py`, `production-schedule.json`, and `audit_comparability_seam.py` still primarily
describe the DataSphere profile. The executable V100 profile resolves different replay and
parallelism. Current gates check selected fields but can pass while planning and launch describe
different experiments.

**Files:**

- Modify `datasphere/native/family.py` only if needed to expose an explicit, side-effect-free
  `profile` argument for descriptor resolution.
- Modify `datasphere/native/plan_production.py`.
- Regenerate or split `datasphere/native/production-schedule.json` into clearly profile-labelled
  artifacts.
- Modify `scripts/audit_comparability_seam.py`.
- Strengthen `scripts/production_gates.py` schedule/replay checks.
- Extend `tests/test_production_schedule_not_stale.py`,
  `tests/test_production_defaults.py`, and comparability/gate tests.

### Design

- [ ] Make host profile an explicit required planner input; do not rely on ambient environment in
  generated artifacts.
- [ ] Reuse `family.py`'s descriptor merge logic. Do not implement a second JSON overlay algorithm.
- [ ] Stamp each artifact with `host_profile`, resolved descriptor hash, frame budget, seed set,
  process/update geometry, replay capacity, checkpoint cadence and evaluation workload.
- [ ] Keep DataSphere and V100 outputs separate or make one multi-profile document with unambiguous
  sections. Never label T4-derived throughput as measured V100 throughput.
- [ ] Model V100 hardware using the actual host facts: 16 CPU cores, 113 GiB available RAM,
  V100-32GiB devices, and currently one free GPU. Availability is runtime state, not an immutable
  hardware constant.
- [ ] Resolve replay from the V100 descriptor: 620k for the native five at a 600k budget. Compute
  eviction from capacity versus maximum retained transitions rather than from prose.
- [ ] Resolve on-policy quanta from selected process/env counts. Derive minimum useful budget,
  endpoint rounding and auxiliary cadence rather than copying base-profile values.
- [ ] Include endpoint and trajectory evaluation episodes/constructions in time estimates.
- [ ] Mark all V100 throughput `UNMEASURED` until a real V100 cell supplies it; T4 projections remain
  separately labelled upper-bound planning evidence.

### Tests

- [ ] Mutate a fixture's V100 replay/process/checkpoint values and prove planner, audit and gate all
  change together.
- [ ] Assert a V100 artifact cannot contain DataSphere tiers or silently inherit 300k replay.
- [ ] Assert DataSphere output remains unchanged and still respects allowed tiers.
- [ ] Assert schedule hash/profile equals the launcher's resolved profile/hash.
- [ ] Assert A20's executable curve depth is 3 and endpoint depth is 20 in the resolved V100 plan.
- [ ] Assert actual endpoint frame rules for IDAAC/PPG/IBAC derive from resolved quanta.

**Closure evidence:** one resolver, profile-stamped generated outputs, mutation-sensitive gates, and
no measured-V100 claim before measurement.

## Work package 5 — investigate CTRL raw versus executed actions without premature patching

**Priority:** after P0 local fixes, before source freeze; initially read-only/candidate-only.

- [ ] Trace one training batch from Gaussian sampling through environment clipping, rollout storage,
  PPO likelihood calculation, window extraction and `update_cluster`.
- [ ] Document exact tensors and shapes. PPO must keep the raw sampled action; the representation
  objective may need the action actually producing the transition.
- [ ] Use existing P20 raw-to-executed diagnostics to quantify evaluation clipping, but do not infer
  training incidence from evaluation alone.
- [ ] Add candidate-only training diagnostics for coordinate-level and vector-level clipping over a
  short run; do not change the default objective yet.
- [ ] If clipping is nontrivial, run a bounded matched sensitivity in which rollout storage preserves
  both fields and only CTRL's cluster input switches raw↔executed. PPO/log-prob remains raw in both.
- [ ] Select the default from source semantics plus sensitivity, then record the deviation class.

This is not on the critical path to fixing T1/T2, but it is on the scientific freeze path for CTRL.

## Work package 6 — settle design-point defaults with bounded evidence

These are research decisions, not generic code cleanup. Work can proceed as read-only source/paper
analysis while Claude edits.

### PPG

- [ ] Reconstruct three exact schedules: author Procgen global setup, authors' published continuous-
  control setup, and current Door V100 setup.
- [ ] Compare interactions per policy update, auxiliary phase, optimizer pass and minibatch sample.
- [ ] Identify which quantities can remain faithful under the common 600k budget and which cannot.
- [ ] Predeclare a bounded current-vs-continuous-control pilot only if it can change the default.
- [ ] Keep current operational label “retimed continuous-action PPG port” unless evidence supports a
  stronger claim.

### IDAAC

- [ ] Perform the analogous geometry comparison only after Work package 2 fixes the mechanism.
- [ ] Keep episode identity described as a Door reinterpretation of Procgen level identity.
- [ ] Do not claim the method is inert merely because an auxiliary classifier measured one target at
  chance; distinguish absent label referent from zero training effect.

### IBAC-SNI

- [ ] Map each architecture, beta, bottleneck, SNI and policy-head choice to the exact author branch
  or our port.
- [ ] Keep the exact executable named as a hybrid unless one complete author configuration can be
  run on Door without a different, worse mismatch.

### Places and horizon

- [ ] Treat Places validation split and 3-bootstrap/9-terminal horizon behavior as declared
  cross-method conditions.
- [ ] Check production-host storage for the source Places train split before accepting val solely for
  old local storage constraints.
- [ ] Run sensitivities only if they can change the production default or materially bound claims;
  do not spend fleet-scale compute to make a limitation paragraph cosmetically smaller.

Deliverable: a concise design-point decision memo feeding the owner decision surface, with one best
operational default per item and alternatives retained—not a menu of unresearched possibilities.

## Work package 7 — freeze evaluator revision once and reconcile all seven families

**Start only after Work packages 1-4 and any accepted CTRL/evaluator-affecting change settle.**

- [ ] Compute the final evaluator revision and list every member contributing to it.
- [ ] Build fresh payloads from that exact tree; verify contract markers before submission.
- [ ] For each family, distinguish three levels of evidence:
  1. loader/execution smoke;
  2. complete diagnostics/regime/scene/placement checks;
  3. native-versus-common measurement reconciliation.
- [ ] Do not upgrade Claude's twelve successful execution smokes into level 3.
- [ ] Reconcile RL-ViGen, DMC-GB, IDAAC, ALDA, PPG, IBAC-SNI and CTRL separately because checkpoint
  formats, action conventions and wrappers differ.
- [ ] Use competent checkpoints where a floor policy would make two wrong evaluators agree.
- [ ] Predeclare tolerance from repeated-evaluation evidence at the episode/aggregate level. Do not
  reuse Gemini's 0.77% as a universal threshold.
- [ ] Store job IDs, hashes, raw episode arrays, diagnostics and verdict in
  `validated_evaluator_families.json`; require exact revision match in the gate.
- [ ] Limit DataSphere concurrency to four and use only gt4.1/gt4i.1.

**Closure evidence:** 7/7 on one revision, each with explicit native/common basis. Functional-only
success remains separately reported.

## Work package 8 — final-platform pre-production sequence

This uses the actual V100 production host, not DataSphere V100.

1. **Renderer control:** evaluate one known checkpoint on the current validated environment for
   R_A, then the same bytes/evaluator/container on the production host for R_B. Compare using the
   predeclared repeatability model; archived DrQ-v2 480.6 is not the control.
2. **Positive anchor:** train/evaluate a competent RL-ViGen positive control—prefer SVEA or SGQN—on
   the current pipeline before the fleet.
3. **Throughput calibration:** one bounded 50k training cell on V100, ideally a canary candidate,
   records training FPS, evaluation seconds/episode, CPU/RAM/VRAM and checkpoint I/O. Replace only
   the matching planner inputs; do not extrapolate one method silently to twelve.
4. **Packing check:** test one-cell first. Two-cell packing is allowed only after measured peak RAM,
   CPU and throughput establish no interference.
5. **Literal canary:** DrQ-v2 first, not IDAAC while historical IDAAC evidence is pre-fix. Execute
   600k training, all 50k checkpoints, clean process exit, terminal identity/finite gate, clean
   reload, full trajectory and endpoint grids, record normalization and final analysis.

A canary result becomes production evidence only if its source/evaluator/container/protocol exactly
match the frozen fleet. Otherwise it is pre-production evidence and must be rerun.

## Work package 9 — final verification and interruption-safe handoff

- [ ] Run focused tests after each work package.
- [ ] After all code/config changes and remote validations settle, run the full suite once.
- [ ] Run `production_gates.py` from two working directories.
- [ ] Run patch reproduction, payload provenance, clean-clone/bootstrap and production-plan
  mutation tests.
- [ ] Generate one current handoff listing completed evidence, exact open owner decisions and exact
  commands/artifacts for the V100 operator.
- [ ] Execute the collision-free local publication rehearsal from
  `draft-git-publication-rehearsal-and-freeze-plan-under-review.md`.
- [ ] Do not make the real freeze commit until the owner reviews the exact candidate tree ID and
  staged inventory.

## Owner decisions, kept separate from implementation work

Operational defaults should be researched and executable, but these remain owner-ratifiable:

1. Door-only production versus adding Lift with its own floor/scenes/horizon/anchor derivation.
2. Fixed training seeds and missing-run/retry policy; recommended default is three outer training
   seeds for every reported method, never outcome-adaptive allocation.
3. Headline hierarchy; recommended default is endpoint success plus raw return and within-scene OOD
   difference, with competence-gated floor-adjusted retention secondary.
4. Endpoint headline and descriptive intermediate trajectory; current operational depth is 20
   endpoint and 3 episodes per regime/scene/stamp every 50k.
5. Scene-placement estimand; recommended default keeps independent placements by scene for coverage
   and labels scene heterogeneity descriptive.
6. PPG/IDAAC/IBAC/CTRL design-point defaults after the bounded work above.
7. Places train versus validation split if production storage makes source fidelity feasible.
8. Preservation of source-specific horizon handling versus any harmonized sensitivity result.
9. Exact private GitHub destination and legacy-history publication policy.
10. Final source-freeze commit/tag and production-fleet launch.

## What I would start after approval

1. Work package 1 (CWD gate): smallest complete repair and verifies our ownership boundary.
2. Work package 2 (IDAAC): highest-confidence hard algorithm defect.
3. Work package 4 (V100 planner): local, independently testable, and must precede hash freeze.
4. Work package 3 (IBAC): larger refactor; design/fake tests first, then bounded T4i and actual-V100
   checks.
5. In parallel, read-only Work packages 5-6.

I would not submit additional evaluator jobs, run the full suite, commit, or start the 600k canary
until those first four packages settle.
