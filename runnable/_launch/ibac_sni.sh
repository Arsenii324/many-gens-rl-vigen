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
# RESOLUTION / TRUNK. The paper's pixel branch pairs 64x64 with `impala_cnn`; the torch_rl branch
# was written for MiniGrid and its original trunk downsamples only once, so feeding it 64x64 would
# create an unintended 6.9M-parameter hybrid. The launcher therefore selects the source-backed
# Impala port below: 64x64 -> 8x8x32 = 2,048, matching the paper's pixel architecture. RL-ViGen
# patch P6 supplies the render size. `--model_type default` remains an explicit legacy ablation.
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
export PYTHONPATH="$BASE:$BASE/torch_rl:$REPO/runnable/_shim"
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
# [Claude 2026-09-04] --entropy-coef 0.0, and this one is MEASURED rather than reasoned.
#
# THE MEASUREMENT. Two runs, identical in code, seed, architecture, task and container, differing
# in this one flag:
#   coefficient 0.01 (bt1i1s0j8qhbal67gjnn): mean_log_std 0.0026 -> 1.4472 over 100k frames,
#     MONOTONICALLY, entropy 9.95 -> 20.03, success 0.00 throughout. At frame 24,960: 0.5381.
#   coefficient 0.0  (bt1338ue402pkpua43g0): mean_log_std FLAT at 0.033 through 25,088 frames,
#     entropy 10.16. Sixteen times smaller at the same frame.
# So the entropy bonus causes the inflation. The competing explanation -- that the policy gradient
# widens sigma because the returns carry no signal -- is refuted by the second run, where the
# returns carry no more signal and sigma does not move.
#
# WHY ZERO, AND WHAT THAT ARGUMENT IS **NOT**. [Rewritten 2026-09-04 after the first version was
# refuted by this project's own data.] I first argued that a Gaussian's entropy is unbounded, so
# ANY positive coefficient must inflate sigma without limit. That is false here, and three
# counterexamples sit in `results/logs/`: at the SAME nominal 0.01, `idaac` reaches mean_log_std
# **0.0206 at 100k**, `ctrl` **0.0034**, `ppg` **0.0008** (and ppg additionally clamps). Only
# `ibac_sni` runs away. So 0.01 is not inherently wrong for a continuous head, and the honest
# statement is narrower: something specific to THIS baseline lets the entropy term dominate, and
# the coefficient is the lever that removes it.
#
# The unbounded-entropy fact is still real and still explains the DIRECTION -- for a Gaussian,
# dH/d(log sigma) = 1 per dimension, so the bonus contributes a CONSTANT upward push at every
# gradient step, where a categorical's push vanishes as the distribution approaches uniform. What
# it does not explain on its own is magnitude, because in a policy that is learning the surrogate
# objective pushes back. The drift also accumulates per GRADIENT STEP rather than per frame, and
# ibac_sni takes far more of them per frame than its siblings (frames_per_proc 128, epochs 4,
# procs 1 -- roughly 3,100 steps over 100k, against idaac's ~780). Cause not yet isolated; the
# discriminating run is named in docs/CONSTRUCTION.md#c61.
#
# ZERO IS THE ORDINARY CONTINUOUS-CONTROL SETTING, not an exotic one: the 0.01 convention comes
# from discrete Atari-style work, and continuous PPO implementations commonly default the entropy
# bonus to 0.0. The alternative principled mechanisms are (a) clamping log_std to a range, which
# `ppg` does and SAC does by construction, and (b) SAC-style automatic temperature against a
# target entropy of -dim(A) -- which is what EIGHT of our twelve baselines already use, and which
# is a code change rather than a configuration one.
#
# THIS IS A DECLARED DEVIATION AND IT IS THE OWNER'S TO ACCEPT. Upstream's default is 0.01. The
# argument for departing is that 0.01 was never scoped to a continuous action space -- the
# torch_rl branch has no continuous task -- so there is no tie here to preserve, the same
# reasoning as `--model_type impala` above. The argument for keeping it is that a hyperparameter
# is part of the algorithm in a way checkpointing is not. Reverse with `--entropy-coef 0.01`,
# which the caller's "$@" can do because it comes last.
#
# A HINT, NOT A RESULT: at 0.0 the windowed return reached 17.78 and 11.04 against the C55 random
# floor of 1.82, where the 0.01 run sat at 2-4 throughout. One seed, a noisy windowed statistic,
# 25k frames, no success events -- suggestive that ibac_sni can learn once the bonus stops
# destroying the policy, and nothing more than suggestive until a real budget says so.
# [Claude 2026-09-05] --beta 1e-4, and this one is a REPAIR, not a new choice.
#
# `torch_rl/scripts/train.py:99` defaults `--beta` to 1.0 and `algos/ppo.py:118` adds
# `self.beta * kl` straight into the objective, so beta scales the bottleneck KL that IS the IBAC
# mechanism. Passing nothing meant we ran beta=1.0 while FAITHFULNESS.md:808 already recorded
# "`vib_beta: 1e-4` matches CoinRun [P]" and even wrote down that beta is per-benchmark --
# 1e-3 toy, 1e-6 Multiroom, 1e-4 CoinRun. The value was researched, sourced and then never wired
# to the process. Executed beta was 10,000x the CoinRun value and 1,000,000x the Multiroom one.
#
# 1e-4 is the CoinRun value, which is the branch this configuration already follows: the trunk is
# `--model_type impala`, ported from IBAC-SNI's own CoinRun branch (C3). The authors' own command
# is README.md:109 -- `--beta 0.0001 --nr-samples 12 --sni`.
#
# This is very likely relevant to the open ibac_sni competence question. A bottleneck penalty
# 10^4 too strong is a mechanism for a policy that neither diverges nor learns, which is the exact
# symptom the entropy_coef=0 pilots recorded. The pilot must be re-run at this beta before any
# competence conclusion is drawn -- do NOT read the earlier pilots as evidence about this config.
#
# Still NOT CoinRun-faithful after this: `--nr-samples 12` has no equivalent in torch_rl (single
# VIB sample), and the latent is this branch's 64-d rather than CoinRun's 256-d. See CLAIMS-LEDGER.
exec "$PY" scripts/train.py --algo ppo --env "robosuite:$TASK" --procs "$PROCS" \
  --use_bottleneck --sni_type vib --model_type impala --entropy-coef 0.0 --beta 1e-4 "$@"
