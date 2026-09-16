# The idaac 600k endpoint rows name the snapshot of the 600k production run, and they are complete

This bundle is the evidence behind the second admissible full-length result (commit `5e169b9`).
That result is `results/records/reeval-v214-idaac-endpoint__records.jsonl`.

## Status

**Resolved.**
- All 88 rows name one checkpoint.
- Of the four idaac snapshots retained on the host, that checkpoint is the one from the 600k
  production run `card0-20260909-035152`, and that run finished.
- The committed rows cover every regime in both policy modes. The in-run mode endpoint did not:
  it was three eval-hard rows short.

## Chain

1. **Which snapshot.** The host retains four idaac terminal snapshots, hashed in place:
   `raw/snapshot-card0-20260909-005543.txt`, `raw/snapshot-card0-20260909-013936.txt`,
   `raw/snapshot-card0-20260909-035152.txt` and `raw/snapshot-card0-20260910-120437.txt`.
   - The join (`raw/join.txt`) matches all fact:endpoint_rows rows to fact:endpoint_snapshot_run,
     with 44 rows per policy mode.
   - No row is unmatched (fact:unmatched_rows).
2. **That run is the 600k production cell, and it finished.**
   - It requested fact:frames_requested frames (`raw/run-record.txt`), with rollouts of
     fact:rollout steps.
   - The descriptor floors the request to whole rollouts (fact:endpoint_rule,
     `raw/endpoint-rule.txt`): fact:floored_endpoint.
   - The trainer reported fact:final_frame and exited with status fact:exit_status
     (`raw/run-end.txt`).
   - The terminal snapshot was copied from fact:terminal_source (`raw/retained-record.txt`).
   - The run also retained fact:intermediate_count frame-stamped checkpoints
     (`raw/intermediate-weights.txt`). The curve sweep reads those. Their rows are not committed
     yet, so this bundle does not join them.
3. **Coverage.**
   - The training cell's own mode-policy endpoint file has fact:in_run_mode_rows rows
     (`raw/in-run-mode-regimes.txt`), with only fact:in_run_eval_hard_mode_rows in eval-hard.
   - The committed re-evaluation has fact:committed_eval_hard_mode_rows in eval-hard, and 11 per
     regime in both modes (`raw/coverage.txt`).
   - So the tracker item "idaac's 3 missing eval-hard mode rows" was closed by the full
     re-evaluation, not by a partial one.

## What this does not show

- **That the snapshot's tensors equal the trainer's final `agent-...pt` save.** The runner's
  record says it was copied from there. That is quoted, not compared.
- **The idaac curve rows.** They are still sweeping at capture time. Once they are committed, add a
  join against `raw/intermediate-weights.txt`, keyed on the `_<frame>.pt` suffix.
- **idaac's fidelity.** The recipe decisions are recorded in `datasphere/native/families.json`
  and the fidelity docs.
- **Why the in-run file was three rows short.** It is recorded as observed, not traced.

## Falsifier

- A committed idaac endpoint row whose `checkpoint_sha256` is not the `card0-20260909-035152`
  snapshot. `tests/test_evidence_backed_register_rows.py` checks this offline.
- A regime or mode with fewer than 11 committed rows.

## Sources

The four host run directories under `~/rlvigen-runs/` are finished scratch, and their listings
carry the hashes. Re-take everything with `bash capture.sh`.
