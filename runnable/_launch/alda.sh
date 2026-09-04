#!/usr/bin/env bash
# Run ALDA_Official's OWN scripts/train.py on RL-ViGen robosuite.
#
#   bash runnable/_launch/alda.sh
#   bash runnable/_launch/alda.sh --spec.trainer.config.n_train_steps=2000
#
# Overrides use the repo's OWN `--spec.<dotted.path>=<value>` syntax (common/utils.py
# parse_spec_overrides), which is checked there and rejects anything without the prefix.
#
# The spec file IS this repo's configuration mechanism -- it ships one per task -- so
# `specs/train_alda_robosuite_door.yaml` is a NEW FILE, not a modification. `domain_name:
# robosuite` in it selects the one guarded branch added to alda_trainer.initialize_env_dmc.
#
# 64x64 is ALDA's own resolution: its encoder is built for it and dies on an 84 render with a
# 3x6400-vs-4096x256 shape mismatch. RL-ViGen patch P6 supplies it. Frame stack 3, from the spec.
#
# SHIM REQUIRED. ALDA calls .to('cuda') and torch.device('cuda') unconditionally.
# A green run here proves the env integration, NOT the CUDA path -- that smoke is a T4.
#
# Eval video is off for robosuite: VideoRecorder.record calls
# env.render(mode=, height=, width=, camera_id=) and RL-ViGen's VGBWrapper.render accepts none of
# those. VideoRecorder(None) disables itself by the repo's own logic. Logging, not algorithm.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BASE="$REPO/runnable/alda"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
# dmc2gym is vendored INSIDE alda's own copy of dmcontrol_generalization_benchmark, which its
# trainer imports; it is a path entry, not a dependency to install.
# [Codex 2026-09-01 21:41 MSK: include the separately vendored ALDA models package required by trainers.alda_trainer imports]
# [Claude 2026-09-02 09:00 MSK: expose ONLY `models` from third_party/alda, not the whole directory.
# `third_party/alda/trainers/` is a regular package (it has __init__.py) and `runnable/alda/trainers/`
# is a namespace package (it has none). Python resolves a regular package ahead of a namespace one
# REGARDLESS of PYTHONPATH order, so putting third_party/alda on the path shadowed ALDA's own
# trainers and `import trainers.alda_trainer` failed outright. Caught by the family import gate, not
# by the previous test, which asserted the path CONTAINED the directory rather than that the import
# worked. A directory holding one symlink is launch environment; it changes no source line.]
ALDA_MODELS_PATH="${ALDA_MODELS_PATH:-$REPO/runnable/_shim/alda_models}"
mkdir -p "$ALDA_MODELS_PATH"
ln -sfn "$REPO/third_party/alda/models" "$ALDA_MODELS_PATH/models"
export PYTHONPATH="$BASE:$BASE/dmcontrol_generalization_benchmark/src/env/dmc2gym:$ALDA_MODELS_PATH:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
  export RLGEN_MPS_AS_CUDA="${RLGEN_MPS_AS_CUDA:-1}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# [Codex 2026-09-01 11:01 MSK: select a supplied remote interpreter instead of the developer-machine virtualenv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
# ALDA refuses to reuse a results directory (FileExistsError on results/<name>/seed_<n>). That
# is its own guard against silently overwriting a run and it is left in place; set ALDA_RESULTS
# to point elsewhere instead of deleting anything.
RES="${ALDA_RESULTS:-results}"
cd "$BASE"
# --spec_overrides is argparse.REMAINDER, so it must come last and swallows everything after it.
if [[ $# -gt 0 ]]; then
  exec "$PY" scripts/train.py --experiment_spec_file specs/train_alda_robosuite_door.yaml \
    --results_dir "$RES" --use_wandb False --spec_overrides "$@"
fi
exec "$PY" scripts/train.py --experiment_spec_file specs/train_alda_robosuite_door.yaml \
  --results_dir "$RES" --use_wandb False
