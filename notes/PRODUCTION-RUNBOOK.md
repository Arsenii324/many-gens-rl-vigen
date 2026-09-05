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
- vector-level action clip rate — the fraction of actions with *any* coordinate clipped, ~93% at
  σ=1 for the five RL-ViGen natives. `scripts/eval_provenance.py::action_diagnostics()` computes
  the equivalent generically (`action_clip_rate_coordinate/vector`) but is **never called anywhere**
  -- a built, unused instrument, not a missing one. Wiring it in would not fix A30 (the PPO
  objective still uses the pre-clip action regardless of what gets measured); it would only make
  the drift visible for `ctrl`/`idaac`/`ibac_sni`, which currently have no empirical (only
  analytical, via boundary_fraction) signal for it.
- PPO approximate KL and clip fraction — for the four on-policy families
- value explained variance, gradient norm
- **train-regime** return trend — the only signal that says "learning is happening"

**Progress**: frames/sec against the measured baseline. A cell running materially slower than its
envelope is usually contention or thrash, and on a shared box **GPU 0 has another tenant**.

**Provenance, once per cell**: that the row carries checkpoint SHA-256, container digest, and the
host-profile actually used (see `MIGRATION-T4-TO-V100.md` — a run inheriting probe values is the
silent failure).

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
3. Per completed cell: records row count, checkpoint hash present, stamps retained as expected.
4. Anchor check as soon as `sgqn`/`svea` endpoints exist — do they land near the published **391.4**
   and **268.8**? That is the discriminating positive control; `drqv2`'s 3.6 is at the floor and
   tells you almost nothing.

## Not yet built, and worth having before day one

- a single command that reports campaign state across cells (currently per-job);
- an alert on `log_std` drift rather than post-hoc inspection;
- the fleet-level exporter and schema note (`production-readiness-by-class.md` lists it as PARTIAL).
