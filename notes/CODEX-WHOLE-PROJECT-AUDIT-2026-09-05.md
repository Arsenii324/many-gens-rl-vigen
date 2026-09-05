# Whole-project pre-production audit — Codex, 2026-09-05

This is a live audit record, not a launch approval. It incorporates reviews 13 and 14, the
current executable gates, and the fixes made while auditing. Prose in older handovers is
historical; the tree, the current gate output, saved checkpoint arguments, and fresh remote
evidence outrank it.

## Current verdict

Fresh `python scripts/production_gates.py` output after the 18:xx MSK repairs:

```text
27 pass, 2 fail, 11 waiting on the owner
NOT LAUNCHABLE
```

The two failures are the expected source-freeze gate (roughly 189 uncommitted paths, with work
from two concurrent agents interleaved) and incomplete physical-pairing evidence in one historical
record group. The owner rows are not cosmetic. They include:

- IBAC-SNI `procs=16`: structurally repaired with a spawn/factory path, but not yet proven in a
  real Linux/EGL T4 job;
- the corrected IBAC competence configuration: the prior short evidence was not at the final
  beta/architecture settings;
- shared evaluator validation on the *current* evaluator revision (the gate currently says 0/7);
- the statistical/estimand, seed, checkpoint-selection, and Door/+Lift scope protocol;
- a production-length train → checkpoint → clean reload → full offline-grid canary;
- a current-pipeline RL-ViGen anchor and the V100 renderer/platform transfer probe.

These are the remaining release conditions. The report below distinguishes an engineering task,
an empirical task, and a formal owner decision; an operational default is researched and used while
the decision is open, but is not called owner-settled.

### Fresh corrections after the original pass

- The claimed-hyperparameter gate is now scoped to *live production values*. Twelve parsed
  prose pairs are explicitly classified as retired-port or canonical-reference material, rather
  than silently omitted; PPG's live callable defaults for its auxiliary epochs and clone weight
  are resolved. The audit now finds no live value that disagrees with or cannot be located in its
  executed path. Its gate previously counted the audit's own `UNLOCATED` legend as a failure;
  a regression test now distinguishes a legend from a table row.
- The IBAC recovery patch snapshot was regenerated after the driver change and reproduces the
  clone again. The cadence audit anchor was refreshed only after verifying the guarded log block
  stayed semantically unchanged.
- The first real Linux/EGL `procs=16` smoke exposed a spawn-only defect: each child imported
  `train.py` as `__mp_main__` and executed the whole top-level training setup, resolving the
  inner `torch_rl.utils` instead of the compatibility `utils` module. The driver is now
  main-guarded and explicitly puts its compatibility layer first. A fresh, marker-verified
  payload was submitted as `bt1ra06pih7t0tup3fkd`; it is an executing smoke, not evidence of
  successful 16-process operation until its records/logs are inspected.

## Method and evidence hierarchy

The null is each original repository's own training entry point and model, run on the Door target;
the harness is responsible for orchestration, retention, and measurement, not for silently making
the twelve implementations identical. The authoritative order is:

1. saved checkpoint arguments and effective command/config artifacts;
2. executable source and the current payload/runner contract;
3. the original README and repository defaults;
4. paper/protocol prose and older handover notes.

Every difference between a requested setting and an effective setting is a finding. A local test
can prove a shell or Python invariant but cannot prove CUDA, EGL, Linux multiprocessing, or V100
throughput. A historical result computed with an older evaluator revision is not reused as current
validation.

## Experimental boundary and estimands

- Scope currently means **Door**, four named regimes (`train`, `eval-easy`, `eval-medium`,
  `eval-hard`), ten certified scenes, and a 500-step episode horizon. Lift is not a free extension:
  its floor, scene set, anchor, renderer behavior, and likely competence threshold must be
  re-derived before adding it.
- The common training budget is operationally 600,000 environment transitions, with the family
  quantum respected (IDAAC floors to a rollout and PPG can ceil to a segment). The executed frame
  count is recorded, not rounded in reporting.
- Endpoint evaluation is the authoritative headline candidate: 4 regimes × 10 scenes × 20
  episodes, evaluated from the final checkpoint inside the container where it was trained.
- Intermediate checkpoints are retained at a 50,000-transition grid and evaluated at 3 episodes
  per scene for trajectory plots. The curve is descriptive; it is not a best-checkpoint selection
  rule. Endpoint and `best over trajectory` can both be computed later if a separately frozen
  selection protocol is adopted.
- Per-episode placement pairing uses a protocol-derived seed, with a realized-placement witness in
  records. Strict regime read-back is now present at all seven evaluator families and fails closed
  when the requested intervention cannot be observed.
- The current scientific question is primarily within-method retention across visual regimes with
  scene held fixed. Raw return, success, train/OOD return difference, raw ratio, and floor-adjusted
  quantities should all be retained and reported; a shaped-reward raw ratio is not invariant to a
  nonzero Door floor.
- Three training seeds (`101,102,103`) are the current researched default. They support broad
  screening and large effects, not fine-grained ranking. Missing-run and comparison-set rules still
  need to be frozen before outcomes are inspected.

## The twelve baselines

| baseline(s) | production path and native design point | important adaptations/risks | status before fleet |
|---|---|---|---|
| `drqv2` | RL-ViGen native launcher; 84×84, stack 3, Door action repeat 1; replay-backed source path | replay cap 300k on the DataSphere profile is an operational memory accommodation and changes eviction semantics; V100 profile is distinct | implementation evidence exists; current evaluator revision still needs validation |
| `svea` | RL-ViGen native launcher; 84×84, stack 3, action repeat 1 | same RL-ViGen cap/eviction issue; Places365/augmentation assets and worker memory make this the heavy native family | implementation evidence exists; current evaluator revision still needs validation |
| `drq` | RL-ViGen native launcher; 84×84, stack 3, action repeat 1 | largest native model and high process-tree memory; run alone on the local machine during rehearsal | implementation evidence exists; current evaluator revision still needs validation |
| `sgqn` | RL-ViGen native launcher; 84×84, stack 3, action repeat 1 | native replay/update cadence remains a source design point, not equalized to other families | implementation evidence exists; current evaluator revision still needs validation |
| `curl` | RL-ViGen native launcher; 84×84, stack 3, action repeat 1 | contrastive objective and source replay semantics retained; no cross-family retuning | implementation evidence exists; current evaluator revision still needs validation |
| `rad` | `runnable/dmc_gb`; 84/100 native render path with its own center crop to 84, stack 3; Door effective repeat 1 | source `action_repeat` flag is not effective on this robosuite path; uncapped replay is deliberate because capping requires a source change and buys little | evaluator has been exercised historically; current revision must be rerun |
| `soda` | `runnable/dmc_gb`; same 100→84 crop design, stack 3 | augmentation is update-only, not an eval leak; uncapped replay is deliberate; memory/throughput is the long-cell risk | evaluator has been exercised historically; current revision must be rerun |
| `alda` | `runnable/alda`; 64×64, stack 3; source SAC/QLAE lineage | production clone has no `utd` flag and does one update per new Door replay transition; old `.25` evidence is from a retired port on Lift and is not a source-fidelity proof; evaluator memory bug fixed but remote validation pending | stability sensitivity and current evaluator validation required |
| `idaac` | `runnable/idaac`; 64×64, stack 3; vector PPO, 4×256 rollout | Procgen-derived executable recipe is a different design point from the authors' continuous-control recipe; episode identity repair is real but Door episode identity is an adaptation of Procgen level identity | implementation/evaluator evidence exists, but current revision and design-point disclosure remain |
| `ppg` | `runnable/ppg`; 64×64, stack 1; 8 envs × 256, source PPG machinery | continuous-action adaptation and 8-env cadence are deliberate; auxiliary KL/action-dimension scaling fixed; no native train-time eval | checkpoint/evaluator path exists; current revision validation and design-point declaration remain |
| `ibac_sni` | `runnable/ibac_sni`; 64×64 Impala residual encoder, VIB/SNI additions, continuous Gaussian head | this is an authored hybrid port, not a literal categorical Procgen reproduction; `beta=1e-4` reaches the process and entropy 0 is an empirical stability workaround; the intended upstream `procs=16` needs real spawn/EGL proof | hard release blocker until `procs=16` smoke and final-setting competence pilot |
| `ctrl` | official-JAX-derived `runnable/ctrl`; 64×64, stack 1; host profile 16 envs on DataSphere and 64 on separate 113-GiB V100 host | continuous Gaussian action semantics (raw versus executed/clipped action in representation learner) remain a focused port question; online diagnostics are structurally thin; CUDA_ROOT is required in the job | evaluator exercised, but current revision and V100 JAX path need validation |

The geometry is intentional but not common-observation: native families preserve the fixed input
size and crop/augmentation design point of the source path. RAD/SODA's 100-render-to-84 crop and
ALDA/PPG/IDAAC/IBAC/CTRL 64×64 paths are not interchangeable; no augmentation from one repository
is imported into another merely to make the table look uniform. This is a declared condition
limitation, not an unnoticed size mismatch.

## Cross-cutting training mechanics

### Frames, actions, and update/data accounting

All twelve x-axes count environment transitions, even though vector families multiply their vector
step by process count and PPG has a 2048 interaction quantum. Door uses action repeat 1, consistent
with the RL-ViGen robosuite protocol. RAD/SODA/ALDA source configurations use action repeat 4, so
one source transition represents four simulator substeps.

Review 14 corrected the prior A27 interpretation. A source action-repeat-4 transition is one
replay item, not four replay items. Therefore source replay learning is approximately one learner
update per newly collected replay transition, and production RAD/SODA/ALDA at one update per Door
transition are not a claimed 4× replay ratio. The native RL-ViGen five take about 0.5 updates per
new transition because `update_every_steps=2`. The physics-substep rate and learner-updates per
replay-transition are separate reported axes.

ALDA remains a live stability question: the old Lift/retired-port result showed 1.0 unstable and
0.25 stable, but it does not prove `.25` is faithful for the production Door clone. The operational
default is the current one-update/new-transition path pending a predeclared Door 1.0-versus-0.25
sensitivity. If `.25` is required, label it target-specific adaptation.

### Normalisation, clipping, entropy, and RNG

- Reported returns remain raw; learner-side reward normalisation is family-local and documented.
- Success is computed through the common evaluator's explicit convention, not inferred from a
  return threshold.
- Entropy coefficient 0 for IBAC is empirical damage control, not a theorem about Gaussian entropy;
  the original 0.01 experiment showed runaway policy scale while other continuous families remain
  stable through their own mechanisms. The corrected beta and final architecture make old IBAC
  competence evidence obsolete.
- `torch.use_deterministic_algorithms(True)` is an ours-level reproducibility aid and must remain
  disclosed as such. Door placement uses global NumPy state; training/evaluation streams are kept
  separate where the source path permits it, and the offline evaluator has fixed episode seeds.
- CTRL's key/RNG behavior follows the official JAX port where splitting it would itself be a
  deviation; its raw-versus-clipped action input to the representation learner remains a focused
  sensitivity item, not a speculative patch.

### Replay, warmup, and memory

RL-ViGen's 300k cap is required on the allowed DataSphere envelope; RAD/SODA remain uncapped by
choice because their 600k preallocation fits their selected tier and a cap would change source
behavior. ALDA's fixed replay working set is large but host-resolved. Warmup floors and family
quanta are enforced before a paid job starts. Local rehearsal must count the whole process tree,
not just the trainer PID; the M2 Pro has no CUDA and only limited safe rendering concurrency.

## Evaluation and records

The shared evaluator has seven family-specific loaders/execution paths. All now return aligned
returns, successes, and flags, and records preserve family, baseline, seed, frame, scope, regime,
scene, episode, policy mode, diagnostics, and placement witnesses. `run_scene_dmc_gb` uses the same
eval mode context as the native evaluator. ALDA offline construction now initializes once and uses
a one-slot non-prefilled replay, avoiding the training-only ~15 GiB allocation.

The evaluator must be validated against the current **family runtime closure** after the last
changes. The prior common hash was not a valid substitute: it included the patch generator
(therefore moved for training-only checkpoint work) but omitted such live paths as CTRL's
`vec_env.py`. The repaired stamp hashes shared evaluator code plus the selected family's reachable
source roots, separately hashes that family's descriptor, and retains the repository-local modules
actually loaded through pickle/factory paths in every row. A reviewer must inspect that dynamic
manifest before the ledger can count a validation. Older 2/12 or 7/7 statements are historical and
cannot certify the new closure. Container-side evaluation is mandatory for container-trained
checkpoints because the local GLFW/MPS renderer does not reproduce the container EGL measurement
(C95).

The authoritative report can contain endpoint and trajectory rows together. Endpoint is the safe
headline default because it is fixed in advance and does not select a lucky checkpoint. A
best-over-trajectory metric is buildable from retained data, but requires equal candidate
opportunity, a validation split, and a predeclared per-seed/per-method selection rule.

## Lifecycle and remote operations

The payload is allowlisted and runner-version checked; `--families` must be explicit, the container
digest is pinned, and `CUDA_ROOT=/usr/local/cuda` is required for the CTRL JAX path. DataSphere
probes use only `gt4.1`/`gt4i.1`; the separate production machine is the V100 host, not DataSphere
V100. Results are private by default.

The runner records the resolved argv and family environment beside each cell. Production scale
refuses an unnamed host profile or missing `NATIVE_PRODUCTION`, and production settings are
announced when applied. Explicit environment overrides remain a release footgun unless the final
submission wrapper is clean and the effective-config artifacts are inspected; do not treat a
`NATIVE_PRODUCTION_KEPT` line as equivalent to a frozen default.

Terminal checkpoint writes use bounded retries and fail loudly after the terminal window. Curve
stamps have a shorter retry window. Finiteness is now checked immediately after terminal retention,
before any paid curve or endpoint evaluation. End-of-job collection includes both training records
and offline-evaluation JSONL files.

## What is fixed, what still needs work

### High-confidence closures already in the tree

- IBAC's actual Impala residual encoder is present and selected by the launcher; the 64×64 geometry
  is no longer confused with the default Nature-style model.
- IBAC Door environment construction now uses picklable factories, explicit `spawn`, and independent
  per-worker seeds; upstream `procs=16` is preserved as the intended profile rather than silently
  replaced by `1`.
- IDAAC terminal episode identity, PPG auxiliary-KL scaling, CTRL evaluator reset/return handling,
  strict regime read-back, placement witnesses, endpoint diagnostics, current checkpoint cadence,
  and the ALDA evaluator replay/memory construction have dedicated checks.
- Intermediate checkpoint retention is wired for all seven families. PPG frame axes are recovered
  from interaction counts rather than a nonexistent total-timestep field.
- Endpoint and intermediate evaluation can both be generated from container-local checkpoints;
  records, not invalid local weights, are the portable artifact.
- The current A27 finding and decision sheet now separate replay-transition ratio from simulator
  substep ratio.

### Required engineering/empirical work before a fleet

1. Build a fresh payload from the current tree and run an exact `ibac_sni`, `procs=16`, Linux/EGL
   smoke on a high-memory allowed T4 tier. The first exact gt4.1 attempt
   (`bt1kgfmbbjhnslfjekg1`) is informative rather than a competence result: all sixteen repaired
   spawn workers constructed, then the 16 GiB cgroup killed the parent at 49 s. Its measured
   parent-plus-workers lower bound is 17.91 GiB, so submission now refuses that shape on gt4.1
   before billing; `bt1djai23kme336auat4` is the same 16-worker functional smoke on 32 GiB gt4i.1.
   A clean high-memory-T4 result validates the code path, not the final V100 hardware profile.
   Then run the corrected IBAC competence pilot long enough to test learning at the intended
   beta/encoder/entropy settings. Do not call `procs=1` the final method.
2. Run the ALDA Door 1.0-versus-0.25 sensitivity at matched transitions and predeclared health
   metrics; validate the corrected ALDA evaluator remotely.
3. Re-run the seven-family shared-evaluator validation on the current family closures, inspect the
   captured runtime-import manifests, and include the curve path and all families that were
   previously only statically inspected.
4. Reconcile the remaining review-13 lifecycle items: strict production override handling and the
   IDAAC test's skip-versus-failure behavior. The endpoint-marker provenance defect is fixed: the
   manifest now reads the actual per-cell marker, including rounded IDAAC/PPG endpoints. Pairing and
   hyperparameter gate overclaims are fixed by fail-closed statuses, but the underlying stale/
   incomplete evidence still needs resolution.
5. On the separate V100 host, pin the Docker digest/renderer and perform the three-step transfer
   probe: current evaluator on the existing platform (R_A), same checkpoint/evaluator/container on
   V100 (R_B), then attribute only R_A→R_B to platform.
6. Run one literal production-length canary through training, terminal save, clean reload, full
   offline grid, record collection, and statistics before starting the fleet.
7. Freeze the source tree and create the provenance-bearing revision only after concurrent edits
   are reconciled. No pre-production merge is scientifically required if this tree itself becomes
   the frozen production revision; a merge/commit is operationally required before results can be
   bound to an immutable source identity.

### Owner decision surface, with researched operational defaults

These are not being silently treated as settled by Codex:

- **Scope:** Door only (recommended now); add Lift only after re-deriving its protocol and anchor.
- **Headline:** endpoint full-grid raw return/success plus all auxiliary metrics (recommended);
  retain trajectory and floor-adjusted views without selecting the best after seeing them.
- **Seeds/statistics:** fixed n=3 seeds with bounded claims (recommended); no adaptive concentration
  after seeing results unless a stopping rule is frozen first.
- **A27:** current one-update/new-replay-transition ALDA default pending the Door sensitivity;
  `.25` only as an explicitly target-specific stability adaptation if the probe supports it.
- **IDAAC and PPG:** retain the executable source-derived design points as the primary fidelity
  rows, and disclose the continuous-control geometry/recipe limitation; any alternate continuous
  control design point is a predeclared sensitivity, not a silent replacement.
- **CTRL raw versus executed action:** preserve the official port and run the focused trace/
  sensitivity before changing the learner input.
- **Reporting:** publish the full metric × method matrix; freeze the comparison set, missing-run,
  competence, and inference rules rather than pretending one permanent headline resolves selection.

## Closure order

The safe order is: current-tree mechanical fixes and focused tests → IBAC 16-process T4 smoke and
competence pilot → ALDA sensitivity/evaluator validation → current-revision seven-family evaluator
validation → renderer/V100 transfer probe → literal canary → freeze source and protocol → fleet.
Until those gates have fresh evidence, the project is a strong pre-production implementation with
a well-specified measurement design, not a production result.
