# Research Integrity, Faithfulness & Negative Constraints

**Maintained by Gemini** (`projects/many-gens-rl-vigen/datasphere_gemini/RESEARCH_INTEGRITY_AND_RULES.md`)  
**Standard**: Research-grade fidelity that withstands hostile peer review. Zero tolerance for synthetic-as-real conflation, ungrounded estimates, or disguised failures, sidestepping real tasks with cheap proxies, or cutting corners. Even if the examples below are concrete, extrapolate their rigor to other parts of your work by analogy and by spirit.

---

## 1. Absolute Prohibitions (Things NOT to Do)

1. **NEVER call a run "successful" without auditing internal process logs**:
   - A shell script or container exit code of `0` is necessary but **not sufficient**.
   - If an internal process crashed with a traceback (e.g. `ModuleNotFoundError`, `KeyError`, `AssertionError`), the run is a **FAILURE** or **PARTIAL FAILURE**, and must be explicitly recorded as such.
2. **NEVER present synthetic benchmarks or proxies as authentic algorithm data**:
   - Mock scripts (e.g. `profile_worker.py` with dummy ConvNets) test OS/hardware capacity only.
   - They must **never** be cited as algorithm performance, throughput, or memory usage of actual RL baselines.
3. **NEVER extrapolate from post-crash or idle states**:
   - If memory is flat because worker processes died, do not describe it as "steady-state buffer write behavior". Meticulously trace the lifecycle of every worker process.
4. **NEVER present ungrounded estimates as empirical data**:
   - If an algorithm has not completed a verified run on target hardware, state clearly: **"No real empirical data measured yet."**
   - Any theoretical projections or literature curves must be explicitly labeled `[THEORETICAL MODEL]` or `[UNVERIFIED ESTIMATE]`.
5. **NEVER discard or silently alter existing code or untracked assets**:
   - Do not delete pre-existing logs in `results/`, overwrite historical checkpoints, or use blunt git operations (`git clean -fd`, `git reset --hard`) that could erase untracked work.
6. **NEVER hide changes or omit in-place attribution**:
   - Every modification made by Gemini must have explicit inline `# [Gemini YYYY-MM-DD]` comments and be documented in [`CHANGES_LOG.md`](CHANGES_LOG.md). Even if it's a temporary or a small modification. If it has multiple surfaces where it has text or multiple files or multiple gemini modifications are present, comment each out; more commenting-out is better than less.

---

## 2. Mandatory Verification Protocol (Things TO Do)

1. **Order of Truth**:
   - Raw downloaded logs (`.log`, `.tsv`, `.json`) > Output stdout > Configuration manifests > Prose summaries.
2. **Full Provenance on Every Claim**:
   - Every number reported must link to a specific DataSphere Job ID, a concrete log line, or a mathematical derivation from known hardware constraints.
3. **Maintain Append-Only Ledgers**:
   - [`RUN_LEDGER.md`](RUN_LEDGER.md): Distinct tag, exact command, hardware node, duration, and honest outcome for every single remote compute submission.
   - [`CHANGES_LOG.md`](CHANGES_LOG.md): Exact timestamped diff log for every file created or modified in this workspace.
