#!/usr/bin/env bash
# Run dmcontrol-generalization-benchmark's OWN train.py on RL-ViGen robosuite.
#
#   bash runnable/_launch/dmc_gb.sh rad  Door 0
#   bash runnable/_launch/dmc_gb.sh soda Door 0
#
# Everything here is launch environment, not source change: PYTHONPATH, MUJOCO_GL, and the
# RLVIGEN_ROOT the one patched branch in src/env/wrappers.py reads. Recorded because a run that
# needs undocumented environment is not reproducible, even at zero changed lines.
#
# RLGEN_MPS_AS_CUDA=1 loads runnable/_shim/sitecustomize.py, which lets this CUDA-native repo run
# on Apple MPS while changing ZERO of its lines. A green run here does NOT prove the CUDA path:
# the shim downcasts float64 (MPS has none) and reports is_cuda for MPS tensors. The
# authoritative smoke is on a real T4.
set -euo pipefail
ALGO="${1:-rad}"; TASK="${2:-Door}"; SEED="${3:-0}"; shift 3 2>/dev/null || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$REPO/runnable/dmc_gb/src"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
# RAD and SODA are specified on a 100x100 render cropped to 84 (RL-ViGen P5 makes the render size
# settable). At a native 84 render RAD's random_crop no-ops by its own guard -- RAD becomes plain
# SAC -- and SODA asserts and dies. Rendering at 100 is what makes both FAITHFUL, at zero changed
# algorithm lines. NOTE for comparability (Part 2): these two then see an 84 crop of a 100 render,
# a different field of view from baselines that render 84 natively.
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-100}"
export PYTHONPATH="$SRC:$SRC/env/dmc2gym:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
  export RLGEN_MPS_AS_CUDA="${RLGEN_MPS_AS_CUDA:-1}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# Default to the project venv, not whatever `python` resolves to on PATH -- anaconda's python
# is first on PATH here and lacks robosuite, which surfaces as a confusing ModuleNotFoundError.
# [Claude 2026-09-02 00:36 MSK: select the supplied remote interpreter, never a local developer venv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
# cwd is the REPO ROOT, not src/: utils.load_config() opens the relative path
# 'setup/config.cfg', which the repo ships at its root. Running from src/ makes SODA's
# Places365 overlay lookup fail with FileNotFoundError. Launcher fix, zero source change.
# setup/config.cfg holds the RELATIVE path "data" so the exported patch stays machine-
# independent -- an absolute /Users/... path in a version-controlled patch is not portable, and
# the Kaggle CUDA smoke is what surfaced it. The dataset is supplied here, as launch environment.
ln -sfn "$REPO/data" "$REPO/runnable/dmc_gb/data"
cd "$REPO/runnable/dmc_gb"
# DEAD KNOB (C71 #1): `--action_repeat 1` below is passed and NEVER READ on this path.
# `src/env/wrappers.py`'s `domain_name == 'robosuite'` branch returns at `FrameStack(...)`, before
# the `dmc2gym.make(..., frame_skip=action_repeat)` that is the file's only consumer of it. Left in
# place because removing it would imply the value is 4 (this tree's `arguments.py:12` default) --
# it is 1, but by absence of a mechanism rather than by this flag. `rad` and `soda` run through
# here. See docs/CONSTRUCTION.md#c71 and docs/INTEGRATION-DELTA.md's action-repeat audit.
#
# The upstream SODA launcher explicitly supplies aux_lr=3e-4; arguments.py's 1e-3 is only the
# generic parser default. Keep that effective source value when this production launcher bypasses
# runnable/dmc_gb/scripts/soda.sh. Extra user arguments remain last, so a deliberate diagnostic
# override still wins.
ALGO_ARGS=()
if [[ "$ALGO" == "soda" ]]; then
  ALGO_ARGS+=(--aux_lr 3e-4)
fi
exec "$PY" src/train.py --domain_name robosuite --task_name "$TASK" --algorithm "$ALGO" \
  --action_repeat 1 --episode_length 500 --eval_mode eval-easy --seed "$SEED" \
  "${ALGO_ARGS[@]}" "$@"
