# Is the system good for the next run? Better, and here is exactly what still is not

**2026-09-09**, after the first two production cells. Written as an audit rather than a summary: the
question is not "what did we fix" but **"what would still go wrong tomorrow"**.

## A — Fixed, with a test that fails without the fix

| # | problem | how it would have shown |
|---|---|---|
| 1 | `collect-host-run.sh` read `records.jsonl`, which **no completed run produces** | refused every good run; had the file been partial instead of absent it would have installed training rows, dropped 528 evaluation rows, and printed success |
| 2 | its final gate `grep` was the last command, so a missing summary line made it **exit 1 after a successful install** | indistinguishable from a refusal |
| 3 | unconditional `cp` into `results/records/` | a re-collection silently destroys a past run's only installed copy |
| 4 | it **refused a watch-stopped cell**, and `assemble_reaped_delivery.py` exists for exactly that cell | the two tools met at a wall; neither refusal wrong alone |
| 5 | eval allowance defaulted to the **training** budget, 69 % short — `ENDPOINT_EVAL_POLICY_MODES` sweeps the grid twice | the cell is stopped during evaluation and never reaches delivery. **This is what happened at 18:37.** |
| 6 | a prebuilt venv is family-specific and nothing said so (`"editable": []`) | an `rlvigen` cell fails at `ImportError` *after* the import check passed |
| 7 | `ppg_checkpoint_frame` reconstructed frames on the wrong cadence, off by one save | every ppg curve row mislabelled by up to 50k frames. **Confirmed prevented in production**: first row `frame=0`, reconstruction would have said 50000 |
| 8 | endpoint measured `snapshot.pt`, whose name carries no frame | **all 85 endpoint rows UNVERIFIABLE** — the headline measurement was the unlabelled one |
| 9–13 | five auditor defects: double-counting the bundle, a false cadence alarm on ppg's real quantisation, tail-scoping that **hid idaac's σ collapse**, pooling two families, flagging every smoke run | audits that read clean or cried wolf |
| 14 | the register double-counted the pooled row and averaged per-scene SDs | n reported as 400 for 200 episodes; SE understated 1.6x |

## B — Specified and deliberately NOT applied

| problem | why it waits | what unblocks it |
|---|---|---|
| `ppg`'s `nminibatch` clamp (32 → 1) | `runnable/ppg/` is a hashed `FAMILY_RUNTIME_MEMBER` and a cell is in flight; editing moves the evaluator revision and makes that cell uncollectable | ppg's evaluation finishing |
| no frame-0 checkpoint for most families, so **no random floor** | same hashed-tree constraint | schedule with the above |

Both are **real gaps in the next run**, not closed items. A `drqv2` cell launched tomorrow still has
no measured floor of its own.

## C — Open, unmitigated, and stated rather than quietly carried

| problem | status |
|---|---|
| the VRAM cap **never reaches any trainer** | confirmed in production (28,108 MiB against caps summing to 14,336). Ruled the wrong instrument; the free-memory floor + cooperative yield is what protects a co-tenant. Not fixed, deliberately |
| all nine `runnable/_launch/*.sh` replace `PYTHONPATH` | narrow: every one re-adds `runnable/_shim`, so the single casualty is the cap directory |
| **no second failure domain for results** | the host has one filesystem with ≥20 GB free. `NATIVE_ACCEPT_SAME_DEVICE=1` is an owner-level acceptance, not a fix |
| `production_run_register.py --check` covers the **generated** half only | statuses in `host-runs.jsonl` are asserted; nothing verifies a run directory still exists on the host |
| a run launched without `record_host_run.py` is **invisible** | procedural, not structural. The launcher runs on the host; the ledger is a file in this repo |
| **in-cell evaluation costs ~16 % of the training phase and produces nothing usable** | 26 blocks x 10 episodes ≈ 49 min/cell. At 10 episodes it ranked eval-easy *above* train where the 200-episode grid ranks it below. Its only value is liveness. **Newly quantified today, unaddressed** |

## D — The honest answer

**For the failure that actually cost us today — a cell stopped mid-evaluation losing its delivery —
the system is now good**: the allowance is derived from the real workload, the stop is detected, the
bundle is rebuildable, the collection path composes, and every row it produces is marked.

**For the failure that cost us more — `ppg` running a configuration it did not declare — it is
not.** The detection is new (`audit_training_diagnostics.py` reports trainer warnings above its
range checks) but the *cause* is unfixed by choice, and the same clamp will fire on the next ppg
cell unless the fix lands first.

**And the class I would bet on for tomorrow is C's last row**: things that are working as designed,
cost real time, and produce numbers nobody should use. Those do not announce themselves — I only
found this one because a question forced me to measure it.
