#!/usr/bin/env bash
# Train SGQN on RL-ViGen robosuite.
#
#   bash baselines/sgqn/train.sh                  # Door, seed 0, the config's full budget
#   bash baselines/sgqn/train.sh Lift 1           # task, seed
#   bash baselines/sgqn/train.sh Door 0 --smoke   # same code path, tiny budget
#
# This script names a CONFIG, not an algorithm. `configs/vigen.yaml:sgqn` is `base` plus only
# this method's own keys, so equal training conditions are the default and every deviation is one
# diffable line. Deviations from `base` for this baseline:
#   aux_beta: 0.9
#   aux_lr: 8e-05
#   sgqn_quantile: 0.9
#
# Environment: see baselines/sgqn/README.md. Evaluation is NOT configured here -- it is
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
exec "$PY" train.py --config sgqn --task "$TASK" --seed "$SEED" "$@"
