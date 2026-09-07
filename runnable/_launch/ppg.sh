#!/usr/bin/env bash
# Run phasic-policy-gradient's OWN train.py CLI on RL-ViGen robosuite.
#
#   bash runnable/_launch/ppg.sh Door 2          # task, num_envs
#
# Everything here is launch environment, not source change.
#
# NO SHIM, and that is not an oversight. PPG picks its device through `tu.have_cuda()`, which
# tests `torch.has_cuda` -- False on a macOS wheel because it is not COMPILED with CUDA, which
# `runnable/_shim/sitecustomize.py` deliberately does not fake. So PPG resolves to
# device_type='cpu' and backend='gloo' by its own logic and runs unmodified. Slower than MPS;
# correct without touching anything. The authoritative smoke is still CUDA (Kaggle / DataSphere),
# where this same command runs with device_type='cuda' and nccl.
#
# 64x64 is PPG's encoder resolution. The selected Door main profile uses the IDAAC-authors'
# DMC continuous-control comparator, including an explicit 3-frame stack passed by families.json;
# `--frame_stack 1` remains an explicit historical C1 override. RL-ViGen patch P6 makes the render
# size settable, so the ImpalaCNN receives the geometry selected by the profile.
set -euo pipefail
TASK="${1:-Door}"; NENV="${2:-2}"; shift 2 2>/dev/null || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
# log_save_helper.py does a bare os.environ["RCALL_LOGDIR"] -- OpenAI's internal launcher set it
# and the public repo never does. Supplying it is launch environment, not a source change.
export RCALL_LOGDIR="${RCALL_LOGDIR:-/tmp/ppg}"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
export PYTHONPATH="$REPO/runnable/ppg:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# [Codex 2026-09-01 11:01 MSK: select a supplied remote interpreter instead of the developer-machine virtualenv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
cd "$REPO/runnable/ppg"
# `robosuite:` prefix is what the one guarded branch in envs.py:get_venv dispatches on. Every
# other flag below is the repo's own CLI, unchanged.
exec "$PY" -m phasic_policy_gradient.train \
  --env_name "robosuite:$TASK" --num_envs "$NENV" "$@"
