# Deep Workspace & Pre-Production State Audit

**Audit Date:** 2026-09-05 03:41 MSK  
**Scope:** `/Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen` and `/Users/a2mogus/build-projs/ccm-intro/projects/flow`  
**Operational Constraint Enforced:** Zero modifications to repo contents (strictly read-only). Fast, targeted verification without executing slow full test suites.

---

## 1. Executive Summary & Critical Finding

While both primary agents (Claude Code and Codex) are inactive, a deep inspection of recent remote executions, working tree state, and inter-agent correspondence revealed **one critical remote blocker** that escaped both agents, alongside **several structural synchronization points**:

1. **Undetected Remote Revalidation Blocker (`bt1muhrpsvpdn8kio2tm`):**
   - In Codex turn 63, Codex built payload v99 and submitted DataSphere job `bt1muhrpsvpdn8kio2tm` (`cfg-idaac-revalidate-v99.yaml`).
   - Codex exited turn 64 while the job was still `EXECUTING`.
   - **Diagnosis:** The job failed with exit code 5 at `2026-09-05T00:27:22Z` with:
     ```text
     RuntimeError: cannot stamp evaluator revision: missing rlgen/protocol.py
     === NATIVE_OFFLINE_EVAL_FAILED device=cuda rc=1 ===
     ```
   - **Root Cause:** In turn 60, Codex added `rlgen/protocol.py` to `evaluator_revision()` in `scripts/eval_provenance.py`, but omitted `"rlgen/protocol.py"` from `BASE_ALLOWED` in `datasphere/native/contract.py`. The build script silently excluded it from `payload-v99.tgz`.
2. **Fleet-Wide Regime Verification (Turn 64):**
   - Codex's final actions correctly addressed PPG and IBAC-SNI wrapper hiding issues without stepping environments. Unit tests pass (89/89).
3. **Production Gate Readiness:**
   - `scripts/production_gates.py` recomputed: **19 PASS, 1 FAIL (`source tree frozen`), 10 OWNER BLOCKS**.
   - No fleet runs can launch until the 10 human owner decisions in `notes/DECISION-SHEET.md` are unfrozen.

---

## 2. Remote Job Pipeline & DataSphere Forensics

### 2.1 Failure Trace of `bt1muhrpsvpdn8kio2tm`
- **Job ID:** `bt1muhrpsvpdn8kio2tm`
- **Config:** `datasphere/native/cfg-idaac-revalidate-v99.yaml`
- **Status:** `ERROR` (Exit code 5, wall time ~11m)
- **Log Extract from Remote Execution:**
  ```text
  === bt1muhrpsvpdn8kio2tm (2860 lines) ===
  budget ok: 100000 frames
  === NATIVE_RLVIGEN_FROM_INPUT commit=90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec sha256=3f7c4dd4143df9f9fd9dc7711dd8c2aaa4cf5c9218c47ae7251aad06c36d0b24 ===
  === NATIVE_IMPORT_GATE idaac ===
  === NATIVE_IMPORT_GATE_PASSED idaac ===
  --- last non-boilerplate lines:
      EVALUATOR_REVISION = evaluator_revision(ROOT)
    File "/tmp/native-work/scripts/eval_provenance.py", line 35, in evaluator_revision
      raise RuntimeError(f"cannot stamp evaluator revision: missing {relative}")
  RuntimeError: cannot stamp evaluator revision: missing rlgen/protocol.py
  === NATIVE_OFFLINE_EVAL_FAILED device=cuda rc=1 ===
  0 records from /tmp/native-out
  === NATIVE_RECORDS_EMPTY no records were derived; the archive still holds the native curves ===
  ```

### 2.2 Forensic Mechanism & The Contract Seam
In `scripts/eval_provenance.py`:
```python
def evaluator_revision(root: Path) -> str:
    members = (
        "scripts/eval_grid.py",
        "scripts/eval_across_scenes.py",
        "scripts/eval_provenance.py",
        "datasphere/native/normalize_curves.py",
        "setup/apply_patches.py",
        "rlgen/protocol.py",   # <--- REQUIRED HERE
    )
```
In `datasphere/native/contract.py`:
```python
BASE_ALLOWED = (
    "datasphere/native/contract.py",
    "datasphere/native/configure_places365_val.py",
    "datasphere/native/families.json",
    "datasphere/native/family.py",
    "datasphere/native/measure_resources.py",
    "datasphere/native/normalize_curves.py",
    "datasphere/native/robosuite-import-closure.json",
    "datasphere/native/rlvigen-source.json",
    "datasphere/native/run_probe.sh",
    "datasphere/native/source-lock.json",
    "requirements-native.txt",
    "runnable/_shim",
    "runnable/_shim/alda_models/models",
    "scripts/check_checkpoint_finite.py",
    "scripts/eval_across_scenes.py",
    "scripts/eval_grid.py",
    "scripts/eval_provenance.py",
    "scripts/metrics.py",
    "scripts/preserve_intermediate_snapshot.py",
    "scripts/watch_divergence.py",
    "setup/apply_patches.py",
    # MISSING: "rlgen/protocol.py"
)
```
**Consequence:** When building `payload-v99.tgz`, `contract.py` strictly excludes any file not in `BASE_ALLOWED` or declared in `family_members`. Thus `rlgen/protocol.py` is absent from the extracted root on the remote VM, causing the runtime crash when `eval_grid.py` imports `evaluator_revision`.

**Fix Required for Resuming Agent:**
1. Add `"rlgen/protocol.py"` to `BASE_ALLOWED` in `datasphere/native/contract.py`.
2. Rebuild payload as `payload-v100.tgz` (or re-stamp contract if needed).
3. Update job config to target `payload-v100.tgz` and resubmit.

---

## 3. Fleet-Wide Regime Verification Audit (Turn 64 Verification)

In Turn 64, the user asked whether the vector-wrapper fix applied to IDAAC was required for other baselines.

### 3.1 Audit of RL-ViGen Baseline Construction Stacks
| Baseline Family | Outer Environment Structure | Mode/Scene Visibility | Fix Applied by Codex |
|---|---|---|---|
| **DrQ-v2** | Direct Gym `VGBWrapper` | Directly exposed | None needed |
| **RAD** | Direct Gym `VGBWrapper` | Directly exposed | None needed |
| **CTRL** | Direct Gym `VGBWrapper` | Directly exposed | None needed |
| **ALDA** | `runnable/_shim/alda_models/models` wrapping `VGBWrapper` | Exposed | None needed |
| **IDAAC** | Wrapped in `gym3.ConcatEnv` | Obscured by ConcatEnv | **Fixed in Turn 63 (L8018):** Hoisted `_vigen_regime` onto `ConcatEnv` |
| **PPG** | Wrapped in `gym3.ConcatEnv` | Obscured by ConcatEnv | **Fixed in Turn 64 (L8140):** Captured `_mode`/`_scene_id` at construction, hoisted onto `venv._vigen_regime` |
| **IBAC-SNI** | Wrapped in `_HWCFloat` | Obscured by wrapper | **Fixed in Turn 64 (L8140):** Captured `_mode`/`_scene_id` before `_HWCFloat`, hoisted onto wrapper |

### 3.2 RNG Integrity Check
Crucially, Codex captured `_mode` and `_scene_id` from the base environment **before wrapper instantiation** without invoking `.reset()` or `.step()`. This guarantees that C69 global NumPy placement RNG states are not consumed prior to measured evaluation episodes.

---

## 4. Production Gates & Requirements Status

### 4.1 Production Gate Recomputation (`scripts/production_gates.py`)
- **Total Gates:** 30
- **Passed:** 19
- **Failed (Technical):** 1 (`gate_source_tree_frozen`)
  - 79 uncommitted paths exist in the recovery workspace.
  - Two agents (Claude Code and Codex) interleaved edits without committing.
- **Waiting on Owner (Policy/Protocol):** 10

### 4.2 The 10 Owner Decisions Blocking Production Fleet Launch
1. **`ibac_sni competence`:** `entropy_coef: 0.0` stops runaway entropy inflation, but needs an empirical learning pilot before running 600k frames. `datasphere/native/cfg-c61-entropy-v80.yaml` is prepared but not launched.
2. **`shared evaluator validated`:** DrQ-v2 is validated; IDAAC is suspended pending CUDA revalidation (blocked by the payload issue detailed above).
3. **`estimands frozen`:** Time-limit split handling: 3 bootstrap vs 9 terminal. Reward offset floor handling in Door.
4. **`seed policy frozen`:** Allocation rule (fixed minimum n=3 seeds across all reported rows vs adaptive concentrating).
5. **`production canary`:** End-to-end training -> checkpointing -> clean reload -> offline evaluation curve -> normalized records pipeline has never been executed at full production horizon.
6. **`external RL-ViGen anchor`:** Issue C48: No published RL-ViGen number has yet been independently reproduced in-tree.
7. **`statistical protocol frozen`:** Outer unit of analysis must be training seed (n=3), not episode count (n=600).
8. **`checkpoint rule frozen`:** Headline metric rule: endpoint vs best-over-trajectory vs trajectory mean.
9. **`production renderer verified`:** Production Docker container (Linux / V100 / `MUJOCO_GL=egl`) must reproduce DrQ-v2 100k training regime return (~480.6) before launching the full fleet.
10. **`production scope frozen`:** Confirmed single task (Door) vs multi-task (+Lift).

---

## 5. Working Tree & Inter-Agent Alignment

### 5.1 Concurrent Agent Seams
- **Mailbox Protocol:** `notes/ask-claude.md` and `notes/claude-answers.md` were used as single-writer communication channels.
- **Identified Drift:**
  - In `notes/CORRECTIONS.md`, Claude documented that a stale 8× rollout gap figure was mistakenly copied into `families.json` by the concurrent session before being retracted.
  - In `scripts/production_gates.py`, Codex removed Claude's stale assertion that IDAAC was discharged.
- **Repo Health:** All newly modified unit tests (114 tests across `test_eval_regime_verification.py`, `test_eval_provenance.py`, `test_production_gates.py`, `test_record_conventions.py`, `test_production_schedule_not_stale.py`, `test_job_knobs_are_read.py`, `test_ibac_evaluator_device.py`) pass cleanly in <9 seconds.

---

## 6. Action Plan for Next Active Agent Turn

When an agent resumes active development:
1. **Immediate Remote Fix (5 minutes):**
   - Edit `datasphere/native/contract.py` to append `"rlgen/protocol.py"` into `BASE_ALLOWED`.
   - Run `$BP datasphere/native/contract.py build-payload --source . --output datasphere/native/payload-v100.tgz --families idaac`.
   - Update `datasphere/native/cfg-idaac-revalidate-v99.yaml` (or create `v100`) to point to `payload-v100.tgz`.
   - Submit: `bash datasphere/native/job.sh submit datasphere/native/cfg-idaac-revalidate-v100.yaml`.
2. **Submit IBAC Entropy Pilot:**
   - Submit `datasphere/native/cfg-c61-entropy-v80.yaml` to verify IBAC learning curve with `entropy_coef: 0.0`.
3. **Commit Clean Checkpoint:**
   - Once revalidation jobs are verified in-flight, bundle the verified contract, wrapper, and gate fixes into a clean git commit to satisfy `gate_source_tree_frozen`.
