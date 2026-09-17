#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
# Needs the production host to still hold ~/rlvigen-runs/card1-20260916-203537.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ibac-endpoint-weights-equal-frame-600064
R='~/rlvigen-runs/card1-20260916-203537'

C $S retained-hashes --host-hashes "$R/native-out/cells/ibac_sni-s101" --name-glob 'snapshot.pt' \
  --note "the retained terminal ibac_sni snapshot of the 600k cell card1-20260916-203537" \
  --fact snapshot_bytes=4620135 --anchor '4620135' \
  --fact snapshot_sha256=d0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef \
  --anchor 'd0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef'

C $S trainer-model-pt --host-hashes "$R/native-work/runs/ibac_sni-s101/cell" --name-glob 'model.pt' \
  --note "the trainer's own model.pt; the retained snapshot.pt is a copy of it, not a separate write" \
  --fact model_pt_sha256=d0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef \
  --anchor 'd0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef'

C $S intermediate-hashes --host-hashes "$R/native-out/cells/ibac_sni-s101/checkpoints" \
  --name-glob 'model_*.pt' \
  --note "all twelve retained frame-named intermediates; every one is 4,619,623 bytes" \
  --fact intermediate_bytes=4619623 --anchor '4619623' \
  --fact frame_600064_sha256=3c07f06ef8d95acbcab4d0d67615ec166ca168f3c3e033fb3c19e8256c90e073 \
  --anchor '3c07f06ef8d95acbcab4d0d67615ec166ca168f3c3e033fb3c19e8256c90e073'

C $S weight-equality --command "$PY results/evidence/$S/compare_weights.py" \
  --note "loads both checkpoints and compares every parameter tensor; the file hashes differ, the weights do not" \
  --fact tensors_compared=37 --anchor 'tensors compared: 37' \
  --fact max_abs_parameter_difference=0.0 \
  --anchor 'max |snapshot - model_600064| over every parameter: 0.0'

C $S endpoint-row-names-the-snapshot --host-path "$R/native-out/cells/ibac_sni-s101/offline_eval_endpoint.jsonl" \
  --grep '"checkpoint_sha256": "[a-f0-9]+"' --only-matching --max 1 \
  --note "the endpoint row's own hash, taken from the live grid; it names the frame-less snapshot.pt and no frame-named file" \
  --fact endpoint_row_checkpoint_sha256=d0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef \
  --anchor 'd0298c76da7fe34695fb12aaae1479e9a69e99ee5126edf4f5b14788623965ef'
