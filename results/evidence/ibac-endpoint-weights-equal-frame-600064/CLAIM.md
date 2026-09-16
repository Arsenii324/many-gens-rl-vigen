# ibac_sni's endpoint measures frame 600,064's policy, and the file hash cannot show it

`ibac_sni` s101 is the first ibac cell to complete a 600k training run (card `card1-20260916-203537`,
2026-09-16, 44 minutes of wall clock). Its curve rows read twelve frame-named intermediates and will
grade CORROBORATED. Its **endpoint** rows read the terminal `snapshot.pt`, and that file is not
byte-identical to any frame-named checkpoint, so the byte-alias route in
`scripts/audit_record_frame_provenance.py` does not rescue them.

## Status

**Resolved as a fact, deliberately NOT promoted to a grade.**

- The endpoint checkpoint holds exactly the weights of frame 600,064: fact:tensors_compared of
  fact:tensors_compared parameter tensors are bitwise equal,
  `max |a-b| = fact:max_abs_parameter_difference`.
- The auditor still grades these rows UNVERIFIABLE, and that is correct. It indexes by the sha256 of
  the FILE, and a measurement taken once by hand must not become a grade that no check re-runs.

## Chain

1. **The two files differ in bytes.** `raw/retained-hashes.txt` gives the retained
   `snapshot.pt` at fact:snapshot_bytes bytes; `raw/intermediate-hashes.txt` gives all twelve
   intermediates, every one of them **exactly fact:intermediate_bytes bytes**. A constant 512-byte gap across twelve files is
   structural, not a different training state.
2. **`snapshot.pt` is the trainer's own `model.pt`.** `raw/trainer-model-pt.txt` hashes
   `native-work/runs/ibac_sni-s101/cell/model.pt` at fact:model_pt_sha256; the retained `snapshot.pt`
   in `raw/retained-hashes.txt` carries the same fact:snapshot_sha256. The harness retains a copy under a generic name, per
   `families.json` (`"checkpoint": "model.pt"`, `"intermediate_checkpoints": "model_[0-9]*.pt"`).
3. **The 512 bytes are device tags, and the cause is in the trainer.**
   `runnable/ibac_sni/torch_rl/scripts/train.py:324-326` calls `acmodel.cpu()` and then writes both
   `model.pt` and the stamped copy; line 352 restores `acmodel.cuda()`; the guaranteed terminal
   write at line 371 runs after the loop with the model back on the device. `save_model`
   (`utils/save.py:24-43`) pickles the whole `ACModel` and never moves it. So the terminal file
   carries CUDA device tags and every in-loop file carries CPU tags.
4. **The weights are identical.** `raw/weight-equality.txt` is the output of
   `compare_weights.py`, which fetches both files from the host and compares every parameter:
   `max |snapshot - model_600064| over every parameter: fact:max_abs_parameter_difference`, over
   fact:tensors_compared tensors with identical keys. The 600,064 intermediate is
   fact:frame_600064_sha256.

## What this does not show

It establishes that ibac's endpoint number is a measurement of the 600,064-frame policy, so the
endpoint and the last curve point describe the same weights.

It does not establish that any automated check will say so. The honest fix is a weight-level hash --
load the checkpoint, hash the `state_dict` in key order -- which would tie these two files
automatically and would subsume the existing byte-alias route. That is not implemented: it needs
torch and the family's model class importable at audit time, which the auditor does not currently
require, and that cost should be decided rather than slipped in. Until then the endpoint rows read
UNVERIFIABLE with this bundle as the reason.

## Falsifier

Re-run `compare_weights.py`. If any parameter tensor differs -- that is, if
`max |snapshot - model_600064|` is anything but fact:max_abs_parameter_difference, or the two
state_dicts stop sharing keys -- then the endpoint is measuring a policy that is not frame 600,064's,
and the claim is dead. The same follows if the retained `snapshot.pt` ever stops matching the
trainer's `model.pt` (fact:model_pt_sha256), since the chain runs through that copy.

A weaker falsifier that does not need the host: if any of the twelve intermediates is ever found at
a size other than fact:intermediate_bytes, the "constant 512-byte gap is structural" reasoning in
step 1 no longer holds and the device-tag explanation must be re-derived rather than assumed.

## Re-deriving

    python results/evidence/ibac-endpoint-weights-equal-frame-600064/compare_weights.py

Needs the host to still hold `~/rlvigen-runs/card1-20260916-203537`.
