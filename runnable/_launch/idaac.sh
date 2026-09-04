#!/usr/bin/env bash
# Run idaac's OWN train.py on RL-ViGen robosuite.
#
#   bash runnable/_launch/idaac.sh idaac Door 4      # algo, task, num_processes
#   bash runnable/_launch/idaac.sh ppo  Door 4       # the repo also ships plain PPO and DAAC
#
# Launch environment only; source changes are in `python scripts/deviations.py`.
#
# 64x64 is IDAAC's OWN resolution and is NOT optional here: ResNetBase and PolicyResNetBase both
# hardcode `nn.Linear(2048, hidden_size)`, and 2048 = 32 channels x 8 x 8, which is what three
# stride-2 pools give for a 64x64 input and nothing else. RL-ViGen patch P6 supplies it.
#
# SHIM REQUIRED, unlike ppg. train.py falls back to CPU on its own, but IDAACRolloutStorage
# hardcodes `self.device = 'cuda'` (storage.py:209) and `rollouts.to(device)` does not touch it,
# so `before_update` sends a tensor to CUDA no matter what train.py decided. That is the authors'
# code assuming its own deployment target; the shim answers it from outside instead of editing
# a line. A green run here proves the env integration, NOT the CUDA path -- that smoke is a T4.
#
# ext/baselines is OpenAI baselines (VecMonitor / VecNormalize / DummyVecEnv / logger), cloned
# because the repo imports it and pip cannot build it here. NOTE: the project root contains a
# directory also called `baselines/` -- this project's per-baseline run scripts -- which shadows
# the package whenever cwd is the project root. cd'ing into the clone below is what avoids it.
set -euo pipefail
ALGO="${1:-idaac}"; TASK="${2:-Door}"; NPROC="${3:-4}"; shift 3 2>/dev/null || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
export RLVIGEN_EVAL_MODE="${RLVIGEN_EVAL_MODE:-eval-easy}"
# _shim/no_tf holds a TensorFlow that raises on any use: baselines' running_mean_std.py has a
# module-level `import tensorflow` for a class idaac never constructs. Read that file.
export PYTHONPATH="$REPO/runnable/idaac:$REPO/ext/baselines:$REPO/runnable/_shim/no_tf:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
  export RLGEN_MPS_AS_CUDA="${RLGEN_MPS_AS_CUDA:-1}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# [Codex 2026-09-01 11:01 MSK: select a supplied remote interpreter instead of the developer-machine virtualenv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
cd "$REPO/runnable/idaac"   # train.py does `from test import evaluate` -- cwd must be the root
exec "$PY" train.py --env_name "robosuite:$TASK" --algo "$ALGO" \
  --num_processes "$NPROC" "$@"
