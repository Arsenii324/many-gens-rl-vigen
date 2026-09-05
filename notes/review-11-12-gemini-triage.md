# Reviews 11, 12 and Gemini-2 — triage against the executable tree

**Snapshot:** 2026-09-05. This is a triage of hypotheses, not an authority for future tree state.
Claude and Codex are editing concurrently. Re-run `python scripts/production_gates.py` and inspect
the cited executable path before treating a status below as current.

Statuses used here:

- **LIVE DEFECT** — executable path can produce a wrong, mislabeled, or missing production result.
- **LIVE VALIDATION BLOCKER** — implementation may be sound, but required evidence is absent.
- **DESIGN-POINT DECISION** — no mechanical universal fix; choose and declare the best method
  definition before seeing final results. The operational default still gets the same research
  effort as a final decision, but remains owner-ratifiable.
- **DECLARED LIMITATION / SENSITIVITY** — not a hidden bug; interpretation or a bounded experiment
  is required.
- **RESOLVED / STALE / REJECTED** — do not re-open without new evidence.

The source reviews are `ai-review-11-external.md`, `ai-review-12-external.md`, and
`gemini-ai-review-2-take-critically.md`. Q18-Q20 in `ask-claude.md` coordinate overlapping work.

## Executive triage

| ID | Concern | Current classification | Required closure |
|---|---|---|---|
| T1 | IDAAC episode identity through auto-reset and storage | **LOCAL REPAIR VERIFIED; CUDA SMOKE PENDING** | Real wrapper→DummyVecEnv→storage test and local Door path pass; one bounded post-fix CUDA training smoke remains |
| T2 | IBAC `procs=16`, inherited EGL, worker RNG | **LIVE DEFECT, P0** | Choose final process architecture; construct envs and seed physical RNG correctly in workers; real multiprocess test |
| T3 | Failed terminal save can retain a stale fixed-name checkpoint | **RESOLVED BY CLAUDE** | Terminal saves retry for 30 minutes then fail the job; fixed-name sites are test-pinned |
| T4 | 600k can run without `NATIVE_PRODUCTION=1` | **RESOLVED BY CLAUDE** | Production-scale guard now requires both explicit host profile and `NATIVE_PRODUCTION` |
| T5 | Production overrides silently beat frozen defaults | **RESOLVED, verified 2026-09-05** | `run_probe.sh`'s `apply_production_settings` forces `strict=1` at FRAMES>=600000; a conflicting override aborts (`NATIVE_PRODUCTION_CONFLICT`, exit 3) rather than being silently kept. `test_production_host_guard_fires.py` green |
| T6 | Checkpoint finite/identity checks occur after expensive grids | **RESOLVED BY CODEX, verified 2026-09-05** | `run_probe.sh`: `check-finite` now runs immediately after `retain`, before the `CURVE_EVAL`/endpoint block -- read directly in the current file, not inferred |
| T7 | Pairing gate depends on caller CWD | **RESOLVED** | Child runs at `cwd=ROOT`; an outside-repository invocation is regression-tested |
| T8 | A20 says 3 curve episodes; executable profiles use 5 | **RESOLVED BY CLAUDE** | All seven executable profiles now resolve 3 curve episodes; owner-facing default remains ratifiable |
| T9 | V100 descriptor vs DataSphere schedule/audit | **RESOLVED LOCALLY; HOST MEASUREMENT PENDING** | Separate generated V100 artifact, profile-aware replay audit, and stale-artifact gate share `family.py` resolution; V100 throughput remains explicitly null |
| T10 | Current evaluator revision validation | **LIVE VALIDATION BLOCKER** | Reconcile all seven evaluator families after final evaluator freeze; competent checkpoints where equality could be vacuous |
| T11 | Exact source tree and nested lineages unfrozen | **LIVE VALIDATION BLOCKER** | Owner-approved commit/tag only after code, protocol, tests and manifests settle |
| T12 | IBAC competence evidence predates corrected beta/final geometry | **LIVE VALIDATION BLOCKER** | Final-geometry beta=`1e-4`, entropy=`0` competence pilot after T2 |
| T13 | Final renderer/runtime equivalence | **LIVE VALIDATION BLOCKER** | Current evaluator gives R_A here; same checkpoint/evaluator/container gives R_B on production host |
| T14 | Current-pipeline external RL-ViGen anchor | **LIVE VALIDATION BLOCKER; BASELINE CHOICE ALREADY RESEARCHED, differs from review 14** | Review 14 suggests SVEA/SGQN (a competent baseline). `notes/rlvigen-published-door-anchor.md`'s own cost analysis argues for `drqv2` instead: its published five-seed range (1-7 on Door eval-easy) is achievable at the SAME 6e5 budget the fleet runs anyway, so the anchor becomes free (checked against the production `drqv2` seeds) rather than a separate commissioned run against a high-performing baseline. Not a disagreement to resolve by picking a side -- state the T3 anchor as "drqv2 within the published 1-7 range" and check it against fleet output; add SVEA/SGQN only if drqv2 alone leaves the anchor unconvincing |
| T15 | Literal full-pipeline 600k canary | **LIVE VALIDATION BLOCKER** | Train→terminal identity→clean reload→curve+endpoint→records→analysis on exact final manifest |
| T16 | PPG rollout/auxiliary geometry | **CADENCE FIXED 2026-09-05 (A26); RECIPE-LEVEL PORTION STILL OPEN** | Auxiliary-phase cadence now matches the published continuous-control reference exactly (an undeclared V100 override had doubled it away; reverted, pinned by `test_ppg_auxiliary_cadence.py`). The broader hyperparameter-recipe comparison (lr, entropy coef, epochs) review 11 also asks for remains a genuine open design point, not touched |
| T17 | IDAAC rollout/update geometry | **DESIGN-POINT DECISION, after T1** | Compare Procgen-derived port with published continuous-control settings; do not tune around a broken identity mechanism |
| T18 | IBAC-SNI authored hybrid lineage | **DESIGN-POINT DECISION** | Name exact hybrid; bound with source-branch choices where feasible; avoid claiming literal reproduction |
| T19 | CTRL requested versus executed action in SSL | **TRACED AND CONFIRMED 2026-09-05 (A30); BROADER THAN NAMED** | Traced directly: `ctrl` samples an unbounded, unclamped Gaussian and computes its PPO log-probability on the pre-clip action while robosuite clips before execution. Not CTRL-specific -- `idaac` and `ibac_sni` share the identical shape. Sensitivity study (the required closure) still not run; not fixed, method-defining. See `DECISION-SHEET.md` A30 |
| T20 | Places365 train→validation substitution | **DECLARED LIMITATION / SENSITIVITY** | Prefer source train split if practical; otherwise representative train-vs-val sensitivity and disclosure |
| T21 | Artificial-horizon bootstrap split (3 vs 9) | **DECLARED LIMITATION / SENSITIVITY** | Preserve source semantics by default; test representative families and constrain causal claims |
| T22 | Scene ID also changes placement seed | **DECLARED ESTIMAND LIMITATION** | Primary within-scene regime contrast remains paired; scene heterogeneity is descriptive unless separately paired |
| T23 | PPG/IDAAC/IBAC/CTRL sampled evaluation vs deterministic families | **DECLARED ESTIMAND LIMITATION** | Report exact native policy-evaluation convention; do not claim identical functional across all methods |
| T24 | Protocol hash is not complete training identity | **LIVE PROVENANCE REQUIREMENT** | Keep comparison-protocol ID distinct from full resolved training-lineage/runtime ID |
| T25 | Unlocated claimed hyperparameters | **RESOLVED BY CODEX, verified 2026-09-05** | Fresh `audit_executed_hyperparameters.py` run: zero live MISMATCH/UNLOCATED rows; the 12 retired-port/canonical-reference claims are now explicitly excluded rather than silently miscounted |
| T26 | Endpoint rounding/actual frame counts | **RESOLVED PRINCIPLE; verify execution** | Record actual count and enforce each family's declared rounding rule; do not force exact 600,000 |
| T27 | Minimum budgets/cadence duplicated across host profiles | **RESOLVED BY CLAUDE, verified 2026-09-05** | `check_budget` now derives idaac/ibac_sni's floor from the RESOLVED profile's `num_processes x num_steps` / `procs x frames_per_proc` instead of a static per-family number; proven non-vacuous (`test_budget_floor_is_profile_aware.py`) against the exact zero-rollout-canary scenario T27 named |
| T28 | Headline/statistics/checkpoint/seed/task scope | **OWNER DECISIONS WITH OPERATIONAL DEFAULTS** | Freeze before outcomes: n=3 outer training seeds, endpoint headline, fixed scene grid, Door scope unless Lift is fully re-derived |
| T29 | Replay 620k vs 1M at 600k | **RESOLVED IN FAVOUR OF 620k DEFAULT** | 620k is non-evicting with headroom and permits packing; retain 1M only if budget grows |
| T30 | Native five, RAD and ALDA need algorithm redesign | **REJECTED** | No new comparable algorithm defect found; remaining work is shared evaluator/runtime/provenance validation |

## What the three less-obvious concern groups mean

### PPG and IDAAC geometry; IBAC hybrid lineage

These are questions about **which scientific method the row represents**, not checkpoint plumbing.

**PPG.** The defining auxiliary phase runs after `n_pi` policy phases. At the current V100 default,
`16 envs × 256 steps × n_pi 32 = 131,072` interactions per auxiliary phase, so roughly four phases
occur by 600k. A source-global Procgen launch (`4 MPI × 64 envs × 256 × 32`) reaches one only after
about 2.10M interactions. A published continuous-control PPG recipe instead uses long single-process
rollouts and gives another cadence. Keeping literal `n_pi=32` while changing global batch geometry
does not preserve the same learning schedule. The current row is therefore a **retimed
continuous-action PPG port** unless a bounded design-point comparison supports a better choice.

**IDAAC.** The current Door port similarly inherits Procgen-style settings while using 16 sequential
`DummyVecEnv` environments, 256-step rollouts, one frame, and target-specific PPO geometry. The
authors also published a continuous-control setup with materially different rollout length,
frame-stack, epochs, minibatches, entropy, learning rate and discount. The correct order is: repair
T1, then compare or justify design points. Hyperparameter adjustment cannot validate a mechanism
whose episode equivalence classes are currently wrong.

**IBAC-SNI.** The executable combines the authors' CoinRun IMPALA CNN and beta scale, their
MiniGrid/PyTorch VIB-SNI machinery, and a newly authored continuous Gaussian policy plus Door-specific
parallelism and entropy choice. No single author release contains that exact combination. It may be
the best available port, but must be called a hybrid and should not support the unqualified claim
“the original IBAC-SNI fails on Door.” T2 and T12 are mechanical/evidentiary blockers; T18 is the
remaining method-definition decision.

### Places split and artificial horizon

**Places365.** SVEA, SGQN and SODA draw augmentation images from a fixed validation subset because
the source training split is about 24 GB and was not selected. This is not train/test label leakage—the
images are nuisance augmentations—but it changes the augmentation distribution for exactly three
methods. Equalizing those three does not prove comparisons against the other nine are unaffected.
Use the source train split if operationally reasonable; otherwise run a representative sensitivity
and disclose the substitution.

**Horizon.** RAD, SODA and ALDA bootstrap value estimates through the 500-step artificial limit;
the other nine treat it as terminal. This changes targets even with identical environment frames.
Blindly rewriting all twelve would reduce source fidelity, so the current best default is preserve,
record, and run a bounded representative sensitivity. It limits causal interpretation of a global
rank table but does not invalidate within-method regime contrasts.

### CTRL raw versus clipped action

The adapted CTRL policy samples an unsquashed Gaussian action. Robosuite executes a clipped
`[-1,1]` version. PPO must retain the **raw sampled action** to compute the likelihood ratio for the
sample actually drawn. CTRL's transition/cluster representation, however, is supposed to condition
on the action that generated the observed transition, which is arguably the **executed clipped
action**. Replacing the action globally would break PPO. The safe investigation is to preserve both
fields, trace which one reaches `update_cluster`, measure clipping incidence, and compare the SSL
objective under raw vs executed input. This is a focused port-semantic sensitivity, not permission
for a speculative global clamp.

## Review 11/12 findings that are useful but not new defects

- The comparison is a benchmark of released/adapted implementations under declared design points,
  not a causal intervention on algorithm name alone. Resolution, frame stack, action distribution,
  update geometry and time-limit semantics are collinear with method.
- Primary reporting should keep success and raw return visible. Within-scene regime difference is
  cleaner than raw return ratio. Floor-adjusted retention is secondary and competence-gated.
- Endpoint should be the predeclared headline. Intermediate checkpoints describe trajectories; the
  final OOD grid must not select a best checkpoint unless a separate validation criterion is frozen.
- Three training seeds are the outer replicates. Scenes and episodes are not substitutes for trained
  policies. Show points/uncertainty and avoid fine rank claims that n=3 cannot support.
- CTRL online evaluation consumes the JAX action key used by subsequent training, but production
  currently disables online evaluation. Preserve source behaviour or isolate it deliberately; do
  not describe NumPy placement isolation as isolation of every RNG.
- Places and time-limit sensitivities, plus PPG/IDAAC design-point pilots, should be bounded and
  predeclared. They are not reasons to mutate all families toward one architecture.

## Claims already resolved or stale

- The final V100 RL-ViGen replay default of 620k is sound for a 600k Door budget and does not evict.
- PPG's continuous-action auxiliary KL now sums across action dimensions before averaging.
- IBAC evaluator device handling, beta wiring, CTRL raw-reward evaluation and CTRL double-reset have
  been repaired, but those fixes do not substitute for current-revision validation.
- Archived DrQ-v2 `480.6` predates measurement-affecting evaluator changes and is not the renderer
  control or a current anchor.
- The canonical current Door random floor is 1.842 from 200 paired episodes. 1.818 is historical.
- Exact equality is not a valid evaluator-reconciliation criterion on this stack; observed repeated
  CUDA evaluation varies. A tolerance must be designed from adequate repeats and estimands, not
  copied from one percentage.

## Gemini-specific triage

### Confirmed and new

`production_gates.py` launches `audit_pairing_evidence.py` without `cwd=ROOT`; the child audit's
default glob is relative. Reproduced on 2026-09-05: launching the gate from the repository reports
the pairing row PASS, while invoking the same absolute script from `/tmp` reports OWNER/no records.
This is T7.

### Useful corroboration

Gemini correctly repeats T2, the dirty-tree problem, the major comparability splits, the need for a
competent SVEA/SGQN anchor, and the distinction between within-scene regime pairing and unpaired
across-scene descriptions.

### Rejected or overclaimed

- “Pairing is verified across all evaluator families” overstates the records; available paired
  comparisons pass, but current evaluator validation remains 0/7 under the project's revision gate.
- `1.818` is not the current floor.
- Archived `480.6` is not current-pipeline evidence.
- A measured 0.77% spread from a tiny IDAAC repeated-evaluation sample is not a universal
  significance threshold and not a renderer-equivalence acceptance criterion.
- The V100 calendar extrapolates T4 throughput; it is a planning envelope, not measured production
  throughput.
- The review labels A1-A22 “resolved” without owner ratification. Operational defaults may be fully
  researched and executable while the decision surface remains open to the owner.
- Recommending IDAAC as the first 600k canary while T1 is live is internally contradictory.
- “Keep IBAC procs=1” is one defensible fallback, not a demonstrated optimum. It changes rollout
  geometry and cannot silently replace the intended multiprocess design.

## Recommended dependency order

1. Repair T1, T3, T4, T6 and T7 with execution-level regression tests.
2. Resolve T2's final IBAC worker construction/seeding architecture; then run T12.
3. Reconcile T8/T9/T27 so one resolved V100 manifest feeds scheduling, auditing and launch.
4. Investigate T19; perform bounded T16/T17/T20/T21 sensitivities where they can change defaults.
5. Close method-defining T25 values and freeze T28's protocol choices before viewing production
   outcomes.
6. Freeze evaluator/source/runtime once; then T10, T13 and T14.
7. Run T15 on that exact object. Only then launch the fleet.

No issue in this file is closed merely because it was documented. A **LIVE DEFECT** closes through
code plus a test exercising the real state transition; a **VALIDATION BLOCKER** closes through the
specified evidence; a **DESIGN-POINT DECISION** closes only after its default is researched,
implemented, and still surfaced for owner ratification.
