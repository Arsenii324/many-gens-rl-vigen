#!/usr/bin/env bash
# Train DrQ on RL-ViGen robosuite.
#
#   bash baselines/drq/train.sh                  # Door, seed 0, the config's full budget
#   bash baselines/drq/train.sh Lift 1           # task, seed
#   bash baselines/drq/train.sh Door 0 --smoke   # same code path, tiny budget
#
# This script names a CONFIG, not an algorithm. `configs/vigen.yaml:drq` is `base` plus only
# this method's own keys, so equal training conditions are the default and every deviation is one
# diffable line. Deviations from `base` for this baseline:
#   hidden_depth: 2
#   init_temperature: 0.1
#   log_std_bounds: [-5, 2]
#   nstep: 1
#
# Environment: see baselines/drq/README.md. Evaluation is NOT configured here -- it is
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
exec "$PY" train.py --config drq --task "$TASK" --seed "$SEED" "$@"
