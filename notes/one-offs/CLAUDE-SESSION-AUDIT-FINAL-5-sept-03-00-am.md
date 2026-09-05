# Comprehensive Adversarial Audit: Claude Code Session Final State
**Session ID:** `d037da9e-fd2d-49f1-a9c8-ac05885402ab`  
**Target Window:** 2026-09-04 21:48:00Z to 23:48:03Z (final ~2 hours before cutoff)  
**Resets / Cutoff:** Terminated abruptly at `23:48:03Z` by Anthropic session limit (`resets 6:30am MSK`).

---

## Executive Summary: Live Blockers & Critical Residue

1. **DataSphere Revalidation Job `bt11qe3gunam3cnjml0u` FAILED (`ERROR` code 5):**
   - Claude submitted this job at `23:44:37Z` to re-run the `idaac` evaluator discharge on the post-fix evaluator (`scripts/eval_grid.py`).
   - Claude saw it as `EXECUTING` at `23:45:38Z`, then hit the session limit at `23:48:03Z`.
   - The job finished at `23:53:32Z` with status **`ERROR`** (no output files/records).
   - **Critical discrepancy:** `scripts/production_gates.py` still reports:  
     `OWNER shared evaluator validated: 2 of 12 burdens discharged (drqv2 PASS, idaac CONSISTENT)`  
     In reality, the `idaac` discharge remains **unvalidated and unrecovered** after the 4 breaking evaluator changes. Only `drqv2` survives.

2. **Active Broken Tests in `tests/test_eval_loop_measurement.py` (5 RED Failures):**
   - Codex introduced fail-closed checking for episode diagnostics (`placement`) via `completed_episode_diagnostics`.
   - Claude proved that this wrapper walk cannot reach `VGBWrapper` across subprocess/vector boundaries, and previously abstained 16 times in `bt1sgcg49j6d6jk84vuj` on `idaac`, `ppg`, `ibac_sni`.
   - Codex's fail-closed raising converts what was a missing diagnostic into an unhandled `RuntimeError: completed 4 episodes but only 0 environment diagnostics were exposed`.
   - Claude logged notes `A21` and `A21b` in `notes/claude-answers.md`, but **refused to edit the file or fix the test**.
   - **Live state:** All 5 tests are **actively failing right now** in `pytest tests/test_eval_loop_measurement.py`. In production, this will crash evaluations for at least 3 of 12 baselines.

3. **Door-Floor Discrepancy Patched but UNCOMMITTED:**
   - `rlvigen_reference.py:32` cited `1.82` (from C55, $n=200$ episodes), while line 65 had `1.633` (from C17, $n=25$ episodes).
   - Claude resolved that both measure the same random policy under different sample sizes, and patched line 65 to `1.818` ($n=200$).
   - This edit was applied locally at `23:48:01Z` (2 seconds before session termination) and remains **uncommitted** in the working tree.

4. **Working Tree Dirty (73 Uncommitted Files):**
   - Claude refused to commit changes, claiming tree commits belong exclusively to the owner.
   - As a result, the `source tree frozen` gate remains **FAIL**, blocking production readiness.

5. **DataSphere vs. V100 Host Conflict (Decision A14) Unresolved:**
   - DataSphere constraints forced 4 algorithms into artificial learning-dynamics reductions (`ppg` 32× batch reduction; `idaac` 16× fewer procs; `ibac_sni` 16× fewer procs; replay buffer 300k cap).
   - The production host has 16 cores and 113 GB RAM, capable of upstream parameters.
   - Claude parked V100 targets in an inert dictionary comment in `families.json` (`_production_host_targets`), but the runtime profile mechanism is **completely unbuilt**.

---

## Detailed Audit of Discoveries & Actions (Chronological & Topic)

### 1. The Door Comparability Anchor & Random Floor (Resolved & Sharpened)
- **The Instrument Bug:** `scripts/rlvigen_reference.py` previously looked for a nonexistent vendored path and printed "absent" on every call, leaving RL-ViGen's published Door numbers unread for the project's entire history. Claude patched it to read `rlvigen-door2-90d8b8c4.tgz`.
- **The Anchor Discovery:**
  - RL-ViGen's published Door numbers are **raw returns**, not success rates.
  - Published DrQ-v2 on Door is **3.6**, and CURL is **6.6**.
  - The project's random policy floor on Door has **mean 1.82, max 6.93** ($n=200$).
  - **Fatal finding:** Both published DrQ-v2 and CURL sit **entirely within the random-policy noise floor**. They do not demonstrate task competence above chance.
  - Only **SGQN (391.4)** and **SVEA (268.8)** achieve true competence and can serve as valid comparative anchors.
- **The C17 vs. C55 Discrepancy:**
  - C17 measured $1.633$ ($n=25$ random episodes).
  - C55 re-derived $1.818$ ($n=200$ random episodes).
  - Both measure the same quantity. Line 65 was patched to `1.818`.

### 2. Evaluator Discharges & `RESULTS-VALIDITY.md`
- **The Invalidation Finding:** All retained records in `results/records/` were written 04 Sep 16:55. On 05 Sep 01:25, `scripts/eval_grid.py` was altered in 4 substantive ways:
  1. Per-episode condition seeding (altering door placement sequences).
  2. `torch.use_deterministic_algorithms(True)` (enforcing deterministic kernels; Door is threshold-sensitive per C70).
  3. Strict regime verification (preventing unverified regime recording).
  4. CUDA execution for `run_scene_idaac` (replacing CPU).
- **The Consequence:** No retained record matches the current evaluator.
- **The Failed Revalidation:** Claude attempted three submissions to recompute `idaac` ($n=20$, train + eval-easy):
  - `bt1etnf38oph256v5gi1`: Failed (`FRAMES=0` rejected by family floor).
  - `bt1hc5oegrfr62f56t3o`: Failed (missing `ppo_daac_idaac` module in payload v80).
  - `bt11qe3gunam3cnjml0u`: Built payload v95, pinned CUDA digest, submitted. **Failed on remote with ERROR code 5.**
  - **Verdict:** The claim that the shared evaluator is validated on 2 of 12 baselines is currently untrue. `idaac`'s discharge must be considered unvalidated.

### 3. `FAITHFULNESS.md` Divergence Table Reconciliation
Claude audited `docs/FAITHFULNESS.md` against real run logs and upstream source code, discovering three major false/mischaracterised rows:
- **`ppg`:** Table claimed "rollout 256 vs 65,536" (implying 256×). Upstream uses 4 MPI workers $\times$ 64 envs $\times$ 256 steps = 65,536 samples/update. The port uses 1 worker $\times$ 8 envs $\times$ 256 steps = 2,048 samples/update. The per-env rollout length (256) matches upstream exactly; the divergence is a **32× smaller effective batch / 32× more frequent updates**, which alters auxiliary phase frequency (`n_pi=32` triggers every 65k frames instead of 2.1M).
- **`idaac`:** Table claimed "rollout 256 vs 2048". Upstream uses 64 processes $\times$ 256 steps = 16,384 samples/update. The port uses 4 processes $\times$ 256 steps = 1,024 samples/update. Per-env rollout is identical; divergence is **16× fewer parallel processes**.
- **`reward_shaping`:** Table tagged `reward_shaping = True` as `[OURS]`. Claude proved that RL-ViGen's own `cfgs/robo_config.yaml` has `reward_shaping: true`. It is native to the benchmark, meaning return scales are aligned.
- **`sgqn`:** Marked as "FIXED" after removing `aux_lr: 0.3`, but the new value is `1e-4` (RL-ViGen global default) rather than canonical `3e-4` (3× divergence on the shared encoder).
- **`curl`:** Confirmed `1e-4` vs canonical `1e-3` (10× divergence).
- **Defect:** Claude documented this in `notes/faithfulness-reconciliation.md` but **never updated `docs/FAITHFULNESS.md`**.

### 4. External Reviews 4 & 5 Triage
- **Confirmed & Fixed:**
  - `gate_source_tree_frozen`: Was checking stdout without return code, returning false-green on missing `.git`. Fixed to fail closed.
  - `gate_release_suite_green`: Was inspecting only one doc test file for `xfail`. Fixed to run fast audits and state that it is not the full suite.
  - Container mutable tag: Pinned to `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000`.
  - IBAC evaluator device bug: Fixed.
- **Refuted:**
  - Review 5 claimed train vs. offline-eval rows have asymmetric field sets. Claude proved retained rows have identical field sets.
- **Recorded but Unverified / Unchecked:**
  - Review 4's IDAAC continuous-precedent contradiction.
  - Review 4's Section M environment lock items beyond digest.
  - Offline grid rows receiving full `run_manifest` provenance.

### 5. Surface Consolidation & Indexing
- Reconciled `scripts/open_decisions.py` to parse and display all 14 items from `notes/DECISION-SHEET.md`.
- Created `notes/README.md` and `notes/START-HERE.md` indexing the six surfaces:
  - `DECISION-SHEET.md` (A1–A14)
  - `RESULTS-VALIDITY.md` (record timestamps vs evaluator changes)
  - `CLAIMS-LEDGER.md` (row-by-row entitlement)
  - `CORRECTIONS.md` (retractions and corrections)
  - `OPEN-QUESTIONS.md` (research questions distinct from decisions)
  - `ACCEPTANCE-R7.md` (acceptance criteria)

---

## Action Items Required for Next Agent / Session

1. **Diagnose and Recover DataSphere Job `bt11qe3gunam3cnjml0u`:**
   Inspect `/var/folders/pj/kc0mj8fx5ks38zy3t9nbjfdh0000gn/T/datasphere/job_2026-09-05T02:54:51.483518` to find why it exited with code 5. Fix configuration and re-run to settle the `idaac` discharge.
2. **Fix Failing Diagnostics Traversal in `tests/test_eval_loop_measurement.py`:**
   Implement Claude's recommendation in `A21b`: read `placement` directly from the environment `info` dictionary (`eval_grid.py:221, :306, :429`) instead of relying on recursive wrapper object traversal that breaks on vectorized/subprocess envs.
3. **Commit the Recovery Tree:**
   Once test gates are green, stage and commit the 73 dirty files to clear the `source tree frozen` gate.
4. **Implement Host Profiles (`datasphere` vs `v100`):**
   Replace `_production_host_targets` comment in `families.json` with an operational profile selector so V100 execution does not inherit 32×-rescaled parameters.
5. **Update Canonical `docs/FAITHFULNESS.md`:**
   Apply the corrections from `notes/faithfulness-reconciliation.md` to the canonical document.
