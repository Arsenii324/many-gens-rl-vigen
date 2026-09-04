#!/usr/bin/env bash
# Run ctrl_public's OWN train_ppo.py on RL-ViGen robosuite.
#
#   bash runnable/_launch/ctrl.sh Door 8            # task, num_envs
#   bash runnable/_launch/ctrl.sh Door 8 --algo=ppo # the repo also ships ppo / daac / daac_ctrl
#
# JAX, NOT TORCH -- the only baseline here that is. Nothing in runnable/_shim applies: there is
# no `.cuda()` to intercept, jax picks its backend itself, and on this machine that is CPU
# (jax-metal is not installed and would not be trusted for a fidelity run anyway). Everything
# below is launch environment.
#
# 64x64 is not adjustable for this repo: train_ppo.py builds the model with
# `jnp.zeros((1, cluster_len, 64, 64, 3))` as its init example, and Impala's flatten is fixed by
# it. That is CTRL's own Procgen resolution. RL-ViGen patch P6 supplies it.
#
# VERSIONS. requirements.txt pins jax==0.2.17 / flax==0.3.4 / optax==0.0.9 (2021); no wheels for
# those exist for python 3.11 on arm64. This runs on jax 0.4.35 / flax 0.10.2 / optax 0.2.3 --
# chosen because tensorflow_probability 0.25's JAX substrate, which models.py imports for its
# action distribution, breaks on jax >= 0.5 (`jax.interpreters.xla.pytype_aval_mappings` was
# removed). That version gap is a real difference from the authors' environment and is recorded
# here rather than assumed away.
#
# --wandb_mode=disabled by default: the repo calls wandb.init() unconditionally and this
# workspace is private-by-default.
set -euo pipefail
TASK="${1:-Door}"; NENV="${2:-8}"; shift 2 2>/dev/null || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
# [Claude 2026-09-03] `_shim` joins the path because train_ppo.py:7 does a bare `import
# wandb`, and this project runs offline with a stub rather than a credential. The import
# gate already carried _shim and passed; the CELL launcher did not, so ctrl reached its own
# first import and died there -- job bt16l824d0p1k8thbnqe, after nine attempts had finally
# got it that far. Appended, so ctrl's own modules still win any name they define.
export PYTHONPATH="$REPO/runnable/ctrl:$REPO/runnable/_shim"
export XLA_PYTHON_CLIENT_PREALLOCATE="${XLA_PYTHON_CLIENT_PREALLOCATE:-false}"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# [Claude 2026-09-02 00:36 MSK: select the supplied remote interpreter, never a local developer venv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
cd "$REPO/runnable/ctrl"
# `robosuite:` prefix is what the guarded branch in train_ppo.py dispatches on.
exec "$PY" train_ppo.py --env_name="robosuite:$TASK" --num_envs="$NENV" \
  --wandb_mode=disabled "$@"
