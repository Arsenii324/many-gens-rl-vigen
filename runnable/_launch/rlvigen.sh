#!/usr/bin/env bash
# Run RL-ViGen's OWN train.py with one of ITS OWN agents on robosuite.
#
#   bash runnable/_launch/rlvigen.sh svea  Door
#   bash runnable/_launch/rlvigen.sh drq   Door
#   agents: svea | drq | sgqn | curl | drqv2   (algos/*.py in the upstream tree)
#
# RL-ViGen selects the agent by picking a WHOLE config file, not by an `agent=` override: each
# cfgs/<name>_config.yaml carries its own `agent._target_` plus that agent's hyperparameters.
# `config` (no prefix) is the drqv2 one, and train.py's own @hydra.main defaults to svea_config.
#
# THERE IS NO CLONE UNDER runnable/ FOR THESE FIVE, and that is the point. RL-ViGen ships them
# together with the benchmark, so "the original repository running its own train.py" IS
# RL-ViGen-upstream itself. Cloning it per agent would fabricate five copies of one tree and make
# the change count look like work that was never done. Their deviation is the RL-ViGen patch set
# (P1-P6, `python setup/apply_patches.py --check`), which every other baseline goes through too.
#
# 84x84 is RL-ViGen's own default -- robo_config.yaml sets it -- so RLVIGEN_IMAGE_SIZE is left
# unset here on purpose, and P6 is inert. rad/soda render 100 and alda/ppg/idaac/ibac_sni render
# 64 because those are THEIR papers' resolutions. Part 2 has to decide whether that is comparable.
set -euo pipefail
AGENT="${1:-svea}"; TASK="${2:-Door}"; shift 2 2>/dev/null || true
CFG="${AGENT}_config"; [[ "$AGENT" == "drqv2" ]] && CFG="config"   # drqv2 owns cfgs/config.yaml
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RLV="$REPO/RL-ViGen-upstream"

# $RLV/algos is on the path because algos/sgqn.py does a bare `import drqv2` and algos/curl.py
# a bare `import drq` -- module paths that only resolve if algos/ is itself a top-level entry.
# With just $RLV, hydra reports the useless "Error locating target 'algos.sgqn.SGQNAgent'" and
# swallows the ModuleNotFoundError underneath. Zero source lines; drqv2/svea/drq do not need it.
# RLVIGEN_EVAL_MODE is what patch P12 reads. WITHOUT it, RL-ViGen's own train.py builds
# eval_env with arguments identical to train_env, so it inherits robo_config's `mode: train`
# and "evaluation" measures the training distribution -- these five reported no generalisation
# gap at all. eval-easy matches what every other baseline here evaluates on.
export RLVIGEN_EVAL_MODE="${RLVIGEN_EVAL_MODE:-eval-easy}"
export PYTHONPATH="$RLV:$RLV/algos:$RLV/envs/robosuiteVGB:$REPO/runnable/_shim"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export MUJOCO_GL="${MUJOCO_GL:-glfw}"
  export PYGLFW_LIBRARY="${PYGLFW_LIBRARY:-/opt/homebrew/lib/libglfw.dylib}"
  # cfgs/config.yaml hardcodes `device: cuda` and the agents call .to(cuda) unconditionally.
  export RLGEN_MPS_AS_CUDA="${RLGEN_MPS_AS_CUDA:-1}"
  # macOS only. robosuite's binding_utils.py:41 OVERWRITES MUJOCO_GL with 'cgl' at import when
  # MUJOCO_GPU_RENDERING is on -- and dm_control's renderer rejects 'cgl' outright. The main
  # process survives because dm_control is already imported by then; a forked replay-buffer
  # DataLoader worker re-validates and dies, surfacing as the useless
  # "DataLoader worker exited unexpectedly, details are lost due to multiprocessing".
  # Zero workers means no fork, no re-validation. Data loading concurrency only -- it changes
  # no algorithm and no number. Left at RL-ViGen's own 4 on Linux.
  EXTRA_OVERRIDES=(replay_buffer_num_workers=0)
else
  export MUJOCO_GL="${MUJOCO_GL:-egl}"
  EXTRA_OVERRIDES=()
fi

# [Codex 2026-09-01 10:00 MSK: select the supplied remote interpreter, never a local developer venv]
PY="${PYTHON_BIN:-${PYTHON:-python3}}"
cd "$RLV"
# `task@_global_=` not `task=`: cfgs/*.yaml declare the task group as `task@_global_`, and
# current hydra rejects the bare form the repo's own scripts/train.sh uses.
# action_repeat=1 is NOT a preference, it is this project's declared protocol
# (rlgen/protocol.py DEFAULT_ACTION_REPEAT) and it is what RL-ViGen's OWN paper specifies:
# Supplementary Table 2, "Action repeat -- Robosuite: 1, otherwise: 2". Their cfgs/config.yaml
# sets 2 and no robosuite task file overrides it, and robo_wrapper really does apply it
# (ActionRepeatWrapper), so a stock run is off their own table by 2x on every budget -- and,
# more to the point here, on a different x-axis from the other seven baselines, none of which
# repeat actions at all. See docs/FAITHFULNESS.md. Override on the command line to study it.
# use_tb=True since 2026-08-20, and it is not a preference. TASK.md's R7 -- the acceptance test
# for this repo as a deliverable -- is "clone -> install -> sh script -> TENSORBOARD LOG ->
# shared plotter -> eval curve", and with tb off that sequence cannot be run at all. It is also
# the only outlet for the one signal that would have caught C57: drqv2.py computes
# `metrics['critic_loss']` every update and logger.py writes it nowhere else, so all eight runs
# before this date discarded ~100,000 finite-ness checks each and a NaN divergence went unnoticed
# for 70,000 frames. Verified to work: a 6,000-frame run logs train/critic_loss, train/actor_loss
# and the three critic-Q series at 373 points. Changes no number and no algorithm -- it only adds
# an artifact -- and `"$@"` comes last, so `use_tb=False` still overrides it.
exec "$PY" train.py --config-name "$CFG" env=robosuite "task@_global_=$TASK" \
  action_repeat=1 use_wandb=False use_tb=True save_video=False "${EXTRA_OVERRIDES[@]}" "$@"
