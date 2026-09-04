#!/usr/bin/env bash
# Train SODA on RL-ViGen robosuite.
#
#   bash baselines/soda/train.sh                  # Door, seed 0, the config's full budget
#   bash baselines/soda/train.sh Lift 1           # task, seed
#   bash baselines/soda/train.sh Door 0 --smoke   # same code path, tiny budget
#
# This script names a CONFIG, not an algorithm. `configs/vigen.yaml:soda` is `base` plus only
# this method's own keys, so equal training conditions are the default and every deviation is one
# diffable line. Deviations from `base` for this baseline:
#   actor_lr: 0.001
#   aux_update_freq: 2
#   critic_lr: 0.001
#   soda_batch_size: 256
#   soda_tau: 0.005
#
# Environment: see baselines/soda/README.md. Evaluation is NOT configured here -- it is
# identical for every baseline by construction (rlgen/evaluate.py).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$REPO"

TASK="${1:-Door}"
SEED="${2:-0}"
shift 2 2>/dev/null || true

# macOS renders through GLFW; dm_control's validator rejects "cgl". Linux GPU boxes want "egl".
if [[ "$(uname -s)" == "Darwin" ]]; then export MUJOCO_GL="${MUJOCO_GL:-glfw}"
else export MUJOCO_GL="${MUJOCO_GL:-egl}"; fi
export PYTHONPATH="$REPO:${PYTHONPATH:-}"

PY="${PYTHON:-python}"
exec "$PY" train.py --config soda --task "$TASK" --seed "$SEED" "$@"
