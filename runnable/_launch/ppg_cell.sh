#!/usr/bin/env bash
# [Claude 2026-09-02 08:25 MSK] Train PPG, then evaluate what it saved, then say so exactly.
#
# PPG is the one baseline of the twelve whose repository ships NO evaluation entry point at all --
# `ppg_eval.py` in this directory exists for that reason and explains itself at length. So "one
# cell = train to a budget, measure the trained policy on a held-out regime, emit the endpoint
# marker" cannot be a single call to the clone's own train.py. This composes the two.
#
# It lives in runnable/_launch/ on purpose, next to ppg_eval.py: it changes ZERO lines in the
# clone, so `scripts/deviations.py` stays an honest account of what was done to the original.
#
# The endpoint is passed in rather than recomputed here. PPG tests its budget BEFORE taking a
# segment, so a request of N interactions completes ceil(N / (num_envs * 256)) * num_envs * 256 of
# them; that arithmetic is declared once, in families.json, and checked by the same code that
# verifies the marker. Duplicating it here is exactly how the two would drift apart.
#
#   bash runnable/_launch/ppg_cell.sh Door 8 10240 10 --interacts_total 10000 --seed 1 --log_dir DIR
set -euo pipefail
TASK="${1:?task}"; NENV="${2:?num envs}"; ENDPOINT="${3:?executed interaction count}"
EPISODES="${4:?evaluation episodes}"; shift 4

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

LOG_DIR=""
SEED="0"
previous=""
for argument in "$@"; do
  case "$previous" in
    --log_dir) LOG_DIR="$argument" ;;
    --seed) SEED="$argument" ;;
  esac
  previous="$argument"
done
: "${LOG_DIR:?ppg_cell needs --log_dir so the saved model can be found}"

bash "$HERE/ppg.sh" "$TASK" "$NENV" "$@"

MODEL="$LOG_DIR/model.jd"
if [[ ! -s "$MODEL" ]]; then
  echo "ppg saved no model at $MODEL" >&2
  exit 1
fi

PY="${PYTHON_BIN:-${PYTHON:-python3}}"
export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
export PYTHONPATH="$REPO/runnable/ppg"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi
"$PY" "$HERE/ppg_eval.py" --model "$MODEL" --task "$TASK" --mode "${RLVIGEN_EVAL_MODE:-eval-easy}" \
  --num_envs 1 --episodes "$EPISODES" --seed "$SEED"

echo "NATIVE_FINAL_EVALUATION_COMPLETED frame=$ENDPOINT"
