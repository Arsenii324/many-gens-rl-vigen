#!/usr/bin/env bash
# [Claude 2026-09-02 09:20 MSK] Train IBAC-SNI, then measure the saved policy in a held-out regime
# with the repository's OWN scripts/evaluate.py, then emit the exact endpoint marker.
#
# Unlike PPG, this repository ships its own evaluator, so nothing here reimplements a measurement:
# it composes two of the clone's own entry points and adds the marker the native runner requires.
# Zero lines change in the clone.
#
# `--save-interval 1` is not a preference. train.py saves only inside
# `if args.save_interval > 0 and update % args.save_interval == 0`, and its default is 0, so a run
# without it finishes with no checkpoint at all and there is nothing for the evaluator to load.
#
#   bash runnable/_launch/ibac_sni_cell.sh Door 2 10240 10 cell --frames 10000 --seed 1 ...
set -euo pipefail
TASK="${1:?task}"; PROCS="${2:?procs}"; ENDPOINT="${3:?executed frame count}"
EPISODES="${4:?evaluation episodes}"; MODEL="${5:?model name}"; shift 5

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BASE="$REPO/runnable/ibac_sni/torch_rl"

SEED="0"
previous=""
for argument in "$@"; do
  case "$previous" in
    --seed) SEED="$argument" ;;
  esac
  previous="$argument"
done

bash "$HERE/ibac_sni.sh" "$TASK" "$PROCS" "$@"

MODEL_DIR="${TORCH_RL_STORAGE:-$BASE/storage}/$MODEL"
if [[ ! -s "$MODEL_DIR/model.pt" ]]; then
  echo "ibac_sni saved no model at $MODEL_DIR/model.pt" >&2
  exit 1
fi

PY="${PYTHON_BIN:-${PYTHON:-python3}}"
export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
export PYTHONPATH="$BASE:$BASE/torch_rl:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi
# RLVIGEN_MODE is what the clone's own env branch reads; eval-easy matches every other baseline.
cd "$BASE"
RLVIGEN_MODE="${RLVIGEN_EVAL_MODE:-eval-easy}" "$PY" scripts/evaluate.py \
  --env "robosuite:$TASK" --model "$MODEL" --episodes "$EPISODES" --seed "$SEED" --procs 1

echo "NATIVE_FINAL_EVALUATION_COMPLETED frame=$ENDPOINT"
