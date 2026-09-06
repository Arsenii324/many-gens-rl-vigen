# Production runbook — what to watch, what aborts, what must not be done

**This category had no surface.** A 9–28 day campaign has failure modes this project has already
met, and the decisions about them must be made *before* the run, because several of them are
survivorship traps that look like ordinary operational judgement in the moment.

Everything here is grounded in a failure that actually happened, not a hypothetical.

---

## Failure signatures we have already seen, with what they look like

| signature | what it was | what to do |
|---|---|---|
| `NATIVE_CELL_SIGNALLED Command terminated by signal 9` | **SIGKILL = OOM.** `alda` on a tier whose ceiling it exceeded by 0.23 GiB. Not a dependency error — a missing module raises `ModuleNotFoundError` and exits through Python | check memory against the envelope before rerunning; do **not** retry unchanged |
| Job reports **SUCCESS** while validating nothing | The cadence knob the runner never read: cfgs set `SAVE_EVERY`, `run_probe.sh` read `SAVE_EVERY_FRAMES`, so every cell "saved once at the end" and looked fine | check the marker the job was *supposed* to emit, not its exit status |
| `Spec override key not found` | ALDA rejects overrides for keys absent from its spec file; cost two jobs | pinned by `tests/test_alda_spec_overrides_resolve.py` |
| Finite but useless policy | `ibac_sni` at σ ≈ 4.3 — **perfectly finite**, entropy climbing 9.95 → 20.03, success 0.00 throughout | the finiteness gate cannot catch this; watch `log_std`, not NaN |
| Records come home empty | `RECORDS_OUT` copied only the training normalizer's output; eval-only jobs have no training cells | check row counts, not just that the file exists |
| `NATIVE_CURVE_EVAL_NO_STAMPS` or `NATIVE_CURVE_EVAL_PARTIAL` | requested intermediate evaluation had no usable stamps or one or more stamp evaluations failed | production cells fail after retaining evidence; exploratory probes emit `NATIVE_CURVE_EVAL_TOLERATED` and remain explicitly partial |
| `NATIVE_RECORDS_NORMALIZATION_FAILED` | `normalize_curves.py` failed after the run manifest was written | the production archive is still written, but its manifest clears final-evaluation completion and records the postprocess failure; do not treat the job as successful |
| `NATIVE_RECORD_DELIVERY_FAILED` or `record_delivery != complete` | the final JSONL bundle was absent, empty, malformed, or execution had already failed | keep the archive for diagnosis, but do not summarize it as a production/evaluation result; `summarize_result.py --diagnostic` is inspection-only |
| `record_content_mismatch` or `NATIVE_RECORDS_COLLECTION_FAILED` | the delivered sequence is truncated, reordered, duplicated, changed, or a collector write failed | retain the archive, inspect canonical/raw hashes and the source files, and rerun only under the predeclared failure policy |
| `NATIVE_RECORDS_OUT_SOURCE_ALIAS` | `RECORDS_OUT` resolves to a declared native source before collection | no source is truncated; retain the archive, correct the destination, and rerun under the predeclared failure policy |
| `delivery_stamp_failed` | final source comparison succeeded, but the records-only completion stamp could not be atomically written or revalidated | retain the archive; the lightweight bundle is not final and the manifest is failed |

## What to watch, per cell

**Live NaN divergence — automatable, not manual.** [Added 2026-09-05, found while auditing run
stages: the tool exists and was not referenced here.] `scripts/watch_divergence.py --run <dir>`
tails a live `exp_local` run and catches a C57-class divergence (NaN at frame 35k, 70k more frames
trained before anyone noticed) in minutes instead of at the terminal finite-check, which only fires
after the FULL budget is spent. Run it alongside each rlvigen-family cell for the duration of the
fleet, or accept that a diverged cell burns its entire training budget before the terminal check
(now gated before paid evaluation, per this session) catches it. The other five/seven families'
divergence classes are not NaN-shaped (see `ibac_sni`'s σ pathology below) and this tool does not
cover them.

**Health, checked at every checkpoint stamp** — a finite checkpoint is not a healthy one:

- `log_std`/`logstd` mean/min/max, and **`boundary_fraction`** — flat log_std is healthy;
  monotone growth is the `ibac_sni` pathology (`REGISTER.md` 2026-09-04: crossed 0.50 by ~50k
  frames, vs idaac's 0.024 at the same budget). **Already logged for all three continuous-Gaussian
  ports** (`ctrl` at `train_ppo.py:359`, `idaac` at `train.py:374,381`, `ibac_sni` the same way) --
  CORRECTED 2026-09-05: an earlier version of this row wrongly said this monitoring was missing.
  Watch it for all three; ibac_sni's own case is already an open owner decision, independent of A30.
- vector-level action clip rate — the fraction of actions with *any* coordinate clipped. The offline
  evaluator now records `native.policy_action_diagnostics` on every per-scene row for all seven
  adapter families. It calls `scripts/eval_provenance.py::action_diagnostics()` on the exact value
  supplied at the adapter-to-environment boundary; PPG is observed at `venv.act` after its
  intentional tensor-to-NumPy conversion, so the policy action is not copied through a new device
  path. The existing per-episode P20 fields remain the independent VGB-wrapper measurement at the
  declared action-space boundary. These diagnostics do not alter actions or PPO likelihoods.

  The scope is deliberately explicit: `policy_action_diagnostics` compares the adapter output with
  the declared VGB/Gym action bounds (`action_clip_rate_coordinate`, `action_clip_rate_vector`,
  `action_raw_executed_l1`, raw min/max). `action_raw_executed_l1` is the **aggregate L1 total**
  over every action vector observed in that scene-level diagnostic, not a mean or a per-action
  value. It does **not** observe controller-internal conversion or
  torque clipping; records say `controller_clipping_observed: false`. If a wrapper exposes no
  numeric action bounds or no action is observed, the record carries `available: false` and a reason
  instead of silently treating the normalized [-1, 1] fallback as empirical. Wiring this in still
  does not fix A30: PPO objectives intentionally use the sampled pre-clip action, while the
  diagnostic makes the resulting boundary drift visible.
- PPO approximate KL and clip fraction — for the four on-policy families
- value explained variance, gradient norm
- **train-regime** return trend — the only signal that says "learning is happening"

**Progress**: frames/sec against the measured baseline. A cell running materially slower than its
envelope is usually contention or thrash, and on a shared box **GPU 0 has another tenant**.

**Provenance, once per cell**: that the row carries checkpoint SHA-256, container digest, and the
host-profile actually used (see `MIGRATION-T4-TO-V100.md` — a run inheriting probe values is the
silent failure).

**Submission boundary**: `bash datasphere/native/job.sh submit <config>` is the only supported
production-scale DataSphere submission route. It parses the forwarded `cmd`, requires exactly one
explicit `NATIVE_HOST_PROFILE` for `FRAMES >= 600000` or `NATIVE_PRODUCTION=1`, and admits
`datasphere` for DataSphere tiers. `NATIVE_HOST_PROFILE=v100` is the separate owner-host identity,
not a label for `g1.1`; placing it in a DataSphere config is rejected before the CLI can upload.
Historical sub-production probes remain admissible without the explicit binding. The guard cannot
prevent a user from invoking the raw DataSphere CLI directly, so such a submission is outside the
reproduction protocol and has no claim to the guarded production path.

## Abort criteria — predeclare, because deciding in the moment is the bias

**Abort the cell** on: SIGKILL; non-finite loss or parameters; `log_std` growth beyond a stated
bound; wall-clock beyond ~2× the envelope estimate.

**Abort the campaign and re-plan** if the longest cell (`soda`, ~45 h projected) cannot complete —
that is the envelope test, which is why it should run first.

**Do not silently retry a failed seed.** Re-running until one survives is survivorship bias and it
will not be visible in the results. If a seed is rerun, the record must say so and why.

**Decide now, not later** (these are on the decision sheet):

- is a crashed seed rerun under the *identical* seed, or is the cell lost?
- are replacement seeds forbidden? (recommended: yes)
- what happens if one method is missing one scene?
- does an incomplete method stay in the headline table?

With n=3, losing one seed is statistically severe — which is exactly why the rule must predate the
loss.

## What must not be done during the run

- **Do not adjust hyperparameters after seeing results.** Any change makes the completed cells a
  different experiment; the register must record it as a new configuration, not a fix.
- **Do not extend only the methods that look bad.** Either predeclare a convergence/extension
  criterion or frame the result purely as fixed-budget performance.
- **Do not change the evaluation grid mid-campaign.** Scenes, regimes and episode counts are part of
  the estimand.
- **Do not read a near-floor eval score as a broken port.** RL-ViGen's *own published* DrQ-v2, CURL
  and DrQ sit at 3.6, 6.6 and 14.0 on Door against a 1.82 floor. A floor result is the expected
  published outcome for those methods.

## Daily loop

1. `python scripts/production_gates.py` — anything newly FAIL?
2. Per running cell: `log_std`, clip rate, train-regime trend, frames/sec vs envelope.
3. Per completed cell: records row count, checkpoint hash present, stamps retained as expected; inspect
   `run_manifest.json` for `execution_kind`, `finalization_schema: 1`, and `record_delivery: complete`
   before accepting lightweight records. Production and eval-only jobs must have a nonempty
   `RECORDS_OUT`; a missing destination is a failed delivery, not an optional convenience. Also
   verify every delivered row has `_delivery_provenance.record_delivery == "complete"` and that
   its source count/hash agree across rows; this is the records-only check when `result.tgz` is not
   fetched.
4. Anchor check as soon as `sgqn`/`svea` endpoints exist — do they land near the published **391.4**
   and **268.8**? That is the discriminating positive control; `drqv2`'s 3.6 is at the floor and
   tells you almost nothing.

## Not yet built, and worth having before day one

- a single command that reports campaign state across cells (currently per-job);
- an alert on `log_std` drift rather than post-hoc inspection;
- the fleet-level exporter and schema note (`production-readiness-by-class.md` lists it as PARTIAL).
