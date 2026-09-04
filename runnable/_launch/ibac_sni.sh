#!/usr/bin/env bash
# Run IBAC-SNI's OWN scripts/train.py on RL-ViGen robosuite.
#
#   bash runnable/_launch/ibac_sni.sh Door 2                      # IBAC-SNI (bottleneck + SNI)
#   bash runnable/_launch/ibac_sni.sh Door 2 --sni_type ''        # plain IBAC, no SNI
#
# WHICH HALF OF THIS REPO. IBAC-SNI ships two implementations: `coinrun/` (TensorFlow 1, the
# paper's CoinRun experiments) and `torch_rl/` (PyTorch, on gym-minigrid). This launcher drives
# `torch_rl/`, the authors' own PyTorch code -- the TF branch is not runnable here and would put
# a framework crossing between us and the reference for no gain.
#
# RESOLUTION. torch_rl was written for MiniGrid's tiny grids, and ACModel derives
# image_embedding_size from the input dims, so any size loads -- but the flatten grows as H*W.
# 64x64 is chosen because it is the resolution of the paper's OWN CoinRun experiments, and it
# gives ((64-1)//2-2)^2 * 64 = 53824 -> Linear(53824, 64). At 84 that would be 2.4x larger for
# no reason the paper supports. RL-ViGen patch P6 supplies the render size.
#
# NO SHIM: base.py picks `cuda if torch.cuda.is_available() else cpu` and train.py guards
# `acmodel.cuda()` the same way, so this repo falls back to CPU by itself. Green here proves the
# env integration, NOT the CUDA path -- that smoke is a T4.
set -euo pipefail
TASK="${1:-Door}"; PROCS="${2:-2}"; shift 2 2>/dev/null || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BASE="$REPO/runnable/ibac_sni/torch_rl"

export RLVIGEN_ROOT="$REPO/RL-ViGen-upstream"
export RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-64}"
export RLVIGEN_MODE="${RLVIGEN_MODE:-train}"   # train | eval-easy | eval-medium | eval-hard
# Two entries: $BASE holds `utils`, `model`, `bottleneck`; $BASE/torch_rl holds the `torch_rl`
# package (the repo ships it as a separate installable with its own setup.py).
export PYTHONPATH="$BASE:$BASE/torch_rl"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# [Claude 2026-09-02 00:36 MSK: select the supplied remote interpreter, never a local developer venv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
cd "$BASE"
# --use_bottleneck --sni_type vib IS the paper's method (IBAC-SNI); the repo's own defaults are
# both off, which is plain PPO. Pass `--sni_type ''` for IBAC without SNI.
#
# [Claude 2026-09-04] --model_type impala, for the same reason and by the same precedent as the
# line above: the repository's default is not what its authors ran on this kind of input, and the
# launcher's job is to select the paper's configuration.
#
# IBAC-SNI ships TWO implementations. `coinrun/` (TensorFlow) is the PIXEL one and pairs 64x64
# frames with `impala_cnn`. `torch_rl/` (PyTorch, what we run) is the MiniGrid one, whose trunk
# downsamples ONCE because MiniGrid is 7x7. This project took 64x64 from the pixel branch and left
# the architecture behind, producing a configuration **nobody has ever run**: neither MiniGrid's
# (7x7 + MiniGrid trunk) nor the paper's pixel one (64x64 + impala). At 64x64 the MiniGrid trunk
# flattens to 53,824 and the model is 6,900,671 parameters against the paper's 360,399 -- see
# docs/CONSTRUCTION.md#c3.
#
# `model_type impala` is that architecture, ported into `torch_rl/model.py` from IBAC-SNI's OWN
# coinrun branch, and it completes the pairing rather than inventing one. Verified locally: 64x64
# gives an 8x8x32 = 2,048 embedding, the paper's own figure.
#
# **This supersedes measurements taken on the hybrid**, including the C61 entropy-collapse run
# (boundary_fraction 0.580 at 100k) -- that finding stands for the configuration it was measured
# on, and must be re-measured here. Pass `--model_type default` to get the old hybrid back.
exec "$PY" scripts/train.py --algo ppo --env "robosuite:$TASK" --procs "$PROCS" \
  --use_bottleneck --sni_type vib --model_type impala "$@"
