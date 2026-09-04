#!/usr/bin/env bash
# Authored by Gemini: Build code.tgz payload for DataSphere 500k runs.
# Ships: setup/, runnable/_launch/, runnable/_shim/, runnable/alda, runnable/idaac, runnable/ppg, ext/baselines, scripts/, rlgen/, requirements.txt, RL-ViGen-upstream (robosuite core)
# 100% self-contained (zero remote git cloning required).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$HERE/code.tgz"

cd "$ROOT"
echo "Packaging code from $ROOT into $OUT..."
tar czf "$OUT" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='results' \
  --exclude='artifacts' \
  --exclude='logs' \
  --exclude='.venv' \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='RL-ViGen-upstream/exp_local' \
  --exclude='RL-ViGen-upstream/results' \
  --exclude='RL-ViGen-upstream/.git' \
  --exclude='RL-ViGen-upstream/envs/carla' \
  --exclude='RL-ViGen-upstream/envs/locodmc' \
  --exclude='dmcontrol_generalization_benchmark/src/env/data' \
  setup runnable/_launch runnable/_shim runnable/alda runnable/idaac runnable/ppg ext/baselines scripts rlgen requirements.txt RL-ViGen-upstream

echo "Built $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"

# Verify required files are in the payload
for must in setup/apply_patches.py runnable/_launch/rlvigen.sh runnable/_launch/alda.sh runnable/_launch/idaac.sh runnable/_launch/ppg.sh rlgen/protocol.py requirements.txt RL-ViGen-upstream/train.py; do
  tar tzf "$OUT" | grep -qx "$must" || { echo "ERROR: $must missing from $OUT"; exit 1; }
done
echo "Payload verified successfully."
