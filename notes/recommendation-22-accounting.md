# External recommendation 22 — the production path against its resilience requirements

Recommendation 22 is not a defect report. It is a **specification**: sixteen requirements a
production run must meet, plus a state machine, written as "what I would insist on before releasing
this fleet". So the useful response is not triage but an audit — check each requirement against the
live tree, and say plainly which are met, which are met by accident, and which were not met at all.

Its own framing, worth keeping because it is the right bar: *a hardware/process/storage failure may
waste compute, but must not silently change the experiment, corrupt an accepted result, or make it
impossible to reconstruct what actually ran.*

| # | requirement | status | evidence |
|---|---|---|---|
| 1 | Every cell immutable once started | **MET** | `effective_config.json` per cell, `source-lock.json`, payload/manifest/requirements hashes and evaluator revisions in every record |
| 2 | Retries preserve the training seed | **MET as policy** | A24, and `EVAL-PROTOCOL.md`. Declared, not mechanically enforced — nothing can enforce it, since the retry is a human action |
| 3 | Resume only where state-complete | **MET, and newly explicit** | The per-family resume table in `RUNNING-ON-PRODUCTION-HOST.md` §6 is generated from each save site's source. No family persists its replay: `_save_snapshot` is hardcoded `False` upstream. Off-policy cells restart from zero |
| 4 | Checkpoint writes never destroy the last good one | **MET** | `safe_checkpoint.safe_write` writes a temporary then `os.replace`, atomic on POSIX. A partial file cannot masquerade as a checkpoint |
| 5 | A checkpoint is not accepted merely because it exists | **MET** | `check_checkpoint_finite.py` at retention, `checkpoint_sha256` in every record, `checkpoint_bytes` in `retained.json`. Deserialisation failure fails the record |
| 6 | Training and evaluation failures separated | **MET** | `OFFLINE_EVAL_SNAPSHOT` re-evaluates an existing checkpoint without retraining; `verify_final_evaluation` refuses to call a cell complete on a zero exit alone |
| 7 | No learning-metric auto-restarts | **MET** | Nothing in the runner restarts on a metric. Aborts are reserved for non-finite state, process death and resource exhaustion |
| 8 | Numerical health observed, not over-controlled | **MET** | `check-finite` at retention, action-clipping diagnostics, `log_std` where relevant. Nothing changes a hyperparameter mid-run |
| 9 | Fail closed on wrong hardware/runtime identity | **WAS NOT MET — fixed 2026-09-07** | The accelerator was DETECTED and only recorded. `require_accelerator` now refuses at production scale, checking ctrl through `jax.devices()` since its requirements filter torch out entirely. `NATIVE_ALLOW_CPU=1` is the announced opt-out |
| 10 | Resource exhaustion anticipated per cell | **MET, same day** | `check_memory` now charges the replay it used to exclude, has a `v100` tier, is profile-aware, and refuses to pack against an extrapolated figure. `family.py disk-requirement` derives disk per cell |
| 11 | Disk exhaustion a controlled failure, not late corruption | **PARTLY MET — improved 2026-09-07** | `safe_checkpoint` waits, announces `SAFE_CHECKPOINT_WAITING`, then skips, so a squeeze is loud and operator-fixable. Disk was recorded ONCE in the manifest and never again; `measure_resources.py` now samples `free_disk_gib` per sample. **Deliberately not an auto-stop** — a monitor that kills a 27-hour cell on an inferred threshold is a new way to lose a run |
| 12 | Retain failure evidence | **MET** | A failed cell still archives `training.log`, `effective_config.json`, `resources.json` and the native curves; `NATIVE_CELL_FAILED` names the cell. Job ids serve as attempt ids |
| 13 | Exactly one authority for eligibility | **MET in structure** | `production_gates.py` is that authority, and `audit_*` scripts report rather than admit. Worth restating in the runbook rather than relying on convention |
| 14 | Support machinery must not perturb the training RNG | **WAS NOT MET — fixed 2026-09-07** | `CORRECTIONS.md #99`: "disabled" online evaluation was a `2147483647` cadence, and `step % cadence == 0` holds at step 0, so eight baselines ran an unrequested initial evaluation against the placement stream. Recommendation 22 flagged this from review 21 and was right to insist |
| 15 | A rerun never silently incorporates a fixed tree | **EVIDENCE EXISTED, CHECK DID NOT — fixed 2026-09-07** | Every record has carried `payload_sha256`, `requirements_native_sha256`, `container_image` and the evaluator revisions. Nothing compared them across the seeds of one row. `scripts/audit_row_closure.py` does now, separating production rows from exploratory ones so a development corpus does not read as a finding |
| 16 | Interruption degrades to "retry this cell" | **MET** | Cells are isolated by construction: own output directory, run directory, log, records. The wrapper's mounts now make a killed container's checkpoints survive |

## The soft requirements

Periodic heartbeat and resource sampling: **met**, and now durable — `resources.json` is flushed
every 30 s instead of only at process exit, so a killed cell leaves its record. A maximum wall-time
with graceful termination: **not implemented**; `run_on_production_host.sh` imposes no timeout, and
adding one is a decision about how long a stuck cell may burn rather than an engineering gap. A
second durable copy of final results: **not implemented**. A machine-readable attempt ledger:
**partly** — job ids and records exist, nothing joins retries to their original cell.

## The state machine

`PLANNED → RUNNING → TRAINED → EVALUATED → ELIGIBLE`, with `FAILED-TRAIN`, `FAILED-EVAL`, `INVALID`.
The tree implements every transition's *substance* — `NATIVE_CELL_FAILED`,
`NATIVE_FINAL_EVALUATION_COMPLETED`, the gates' admissibility rules — but not the vocabulary. That
is a naming gap, not a behavioural one, and worth adopting in the runbook so two agents and an
operator use one set of words.

## What this audit changed

Three of sixteen were not met, and all three were of the same kind: **the evidence existed and
nothing acted on it.** The accelerator was recorded but never enforced; disk was recorded once and
never watched; closure identity was stamped on every record and never compared across a row. That
is the recurring shape of this project's real defects, and it is worth stating as the lesson rather
than as three fixes.
