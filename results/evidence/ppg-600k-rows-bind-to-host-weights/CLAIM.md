# Every committed ppg 600k row names weights that exist on the host, at the right stamp

The claim: the curve's last point and the endpoint evaluate the same weights, from two different
files.

`notes/endgame/PPG-600K-COMPLETE.md` says the 14 checkpoints "were sha-verified against their own
rows before any of this ran". This bundle is that verification, kept, and extended by one question
the note did not ask.

## Status

**Resolved.**
- All 616 committed rows bind to a retained host file whose checkpoint was saved at the row's
  frame. None is unmatched.
- Curve stamp 600,064 and the endpoint read different files that hold identical tensors.

## Chain

1. **The weights on the host.**
   - The training run retained fact:intermediate_count IC-stamped checkpoints
     (`raw/intermediate-weights.txt`, with size, mtime and SHA-256 taken in place) and
     fact:terminal_count terminal checkpoint (`raw/terminal-weights.txt`).
   - The runner's record says the terminal checkpoint was copied from fact:terminal_source, at
     fact:terminal_bytes bytes (`raw/retained-record.txt`).
   - The training log maps each file to its interaction count, e.g. fact:model012_ic for
     `model012.jd` (`raw/save-stamps.txt`).
2. **The join** (`raw/join.txt`).
   - The committed curve file has fact:curve_rows rows over 12 frames, and the endpoint file has
     fact:endpoint_rows rows over 1.
   - Each frame carries exactly one checkpoint hash, and every hash is one of the host files at its
     own stamp. For example, frame 51,200 is `model001.jd` (fact:curve_51200_is_model001), frame
     600,064 is `model012.jd` (fact:curve_600064_is_model012), and the endpoint is the terminal
     `snapshot.pt` (fact:endpoint_is_terminal).
   - No row is unmatched (fact:unmatched_rows, `raw/join-failures.txt`).
3. **Curve end and endpoint are the same model** (`raw/weights-equivalence.txt`).
   - `model012.jd` (fact:model012_sha) and `snapshot.pt` (fact:snapshot_sha) differ in bytes,
     because they were pickled with different protocols.
   - All tensor storages are byte-identical (fact:storages_identical), and the unpickled object
     graph is identical (fact:curve_end_and_endpoint_same_weights).
   - The probe compares without importing the model classes.
   - Negative control: consecutive checkpoints `model011.jd` and `model012.jd` share
     fact:control_storages_identical storages and come out fact:control_verdict
     (`raw/weights-equivalence-negative-control.txt`). So the probe can tell weights apart.

## What this does not show

- **That the evaluation of those weights was right.** That is the evaluator's attestation and
  `audit_eval_validity.py`, not this bundle.
- **That the curve's last point and the endpoint should agree numerically.** They are different
  episode counts (3 against 20) of a nondeterministic evaluator. See
  [`../evaluator-run-to-run-noise-ppg/CLAIM.md`](../evaluator-run-to-run-noise-ppg/CLAIM.md).
  This bundle only shows they measure the same model.
- **Anything about `model000.jd`.** It is the IC=0 initialisation, and no row evaluates it.
- **The training's fidelity.** See the two ppg fidelity bundles.

## Falsifier

- A committed ppg row whose `checkpoint_sha256` is not in the host listing.
- A row whose hash belongs to a file saved at a different interaction count.
- `tests/test_evidence_backed_register_rows.py` recomputes the join from the committed records and
  the captured listing, and fails in either case.

## Sources

The host run directory `~/rlvigen-runs/card0-20260909-115331/` may be reclaimed. The listings
carry each file's hash, and the probe prints the hashes of the copies it read, which match. The
scp copies used by the probe are scratch and are not committed. Re-take everything with
`EVIDENCE_WORK=<dir> bash capture.sh`.
