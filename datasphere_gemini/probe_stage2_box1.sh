#!/usr/bin/env bash
#
# ============================================================================
#  CONTAINER JOB BODY -- DO NOT RUN THIS ON A HOST.
#
#  This script is the `cmd:`/`${JOB}` body of a remote job. It runs INSIDE a
#  fresh container, where `apt-get install` and `pip install` mutate that
#  container's own throwaway filesystem and nothing else.
#
#  Run on a host it would attempt to install system packages and pip into the
#  host's python. On a shared machine that is other people's environment.
#
#  The host-side entry point is `datasphere/native/run_on_production_host.sh`,
#  which starts the container; the DataSphere one is
#  `datasphere/native/job.sh submit <config>.yaml`.
# ============================================================================
# =========================================================================================
# Stage 2: Box 1 Standalone Component Probes (drqv2, alda, idaac, ppg) on gt4i.1
# 100% Self-Contained Payload (Zero GitHub Network Clones)
# Authored by Gemini (2026-08-31)
# =========================================================================================
set -uo pipefail

JOB_START=$(date +%s)
CODE="${1:?code tarball}"
RESULT="${2:?result tarball}"
WKEY="${3:-}"

OUT=/tmp/out
mkdir -p "$OUT" /tmp/w /tmp/ppg
exec > >(tee -a "$OUT/job.log") 2>&1

step() { echo; echo "=== $1 (t+$(( $(date +%s) - JOB_START ))s) ==="; }

step "1. Hardware & System Inspection"
uname -a
free -h || true
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

step "2. System Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq python3 python3-pip python3-dev build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    openmpi-bin libopenmpi-dev \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY="/usr/bin/python3"
echo "Python: $("$PY" -V 2>&1 | cut -d' ' -f2) at $PY"

step "3. Unpack Self-Contained Code Payload"
tar -xzf "$CODE" -C /tmp/w
cd /tmp/w

step "4. Python Dependencies (PyTorch cu121 + Pinned Environment)"
tp=$(date +%s)
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 >/dev/null 2>&1
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt >/dev/null 2>&1

rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1
echo "Installed Python packages in $(( $(date +%s) - tp ))s"

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2

step "5. Apply RL-ViGen Patches P1-P14"
"$PY" setup/apply_patches.py || { echo "ERROR: Patches failed to apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ERROR: Patch check failed"; exit 1; }
echo "Patches verified cleanly."

step "6. GL & CUDA Hardware Gates"
"$PY" - <<'GL'
import os
os.environ.setdefault("MUJOCO_GL", "egl")
import robosuite
from OpenGL import GL
env = robosuite.make("Door", robots="Panda", has_renderer=False,
                     has_offscreen_renderer=True, use_camera_obs=True,
                     camera_names="agentview", camera_heights=84, camera_widths=84,
                     control_freq=20, horizon=500, reward_shaping=True)
obs = env.reset()
print("GL_VENDOR   :", GL.glGetString(GL.GL_VENDOR).decode())
print("GL_RENDERER :", GL.glGetString(GL.GL_RENDERER).decode())
print("Frame shape :", obs["agentview_image"].shape)
GL

step "7. W&B Setup"
if [ -n "$WKEY" ] && [ -f "$WKEY" ]; then
    export WANDB_API_KEY=$(cat "$WKEY" | tr -d ' \n\r')
    "$PY" -c "import wandb; wandb.login(key='$WANDB_API_KEY')" || true
fi
export WANDB_PROJECT="many-gens-rl-vigen"

step "8. Probe 2A: DrQ-v2 Standalone Probe (5,000 steps)"
t0=$(date +%s)
PYTHON="$PY" bash runnable/_launch/rlvigen.sh drqv2 Door \
    num_train_frames=5000 eval_every_frames=2500 num_eval_episodes=2 seed=1 \
    use_wandb=False use_tb=True save_snapshot=True save_video=False \
    2>&1 | tee "$OUT/drqv2_probe.log"
echo "DrQ-v2 probe completed in $(( $(date +%s) - t0 ))s"

step "9. Probe 2B: IDAAC Standalone Probe (5,000 steps)"
t1=$(date +%s)
PYTHON="$PY" bash runnable/_launch/idaac.sh idaac Door 1 \
    --num_env_steps 5000 --seed 1 \
    2>&1 | tee "$OUT/idaac_probe.log"
echo "IDAAC probe completed in $(( $(date +%s) - t1 ))s"

step "10. Probe 2C: PPG Standalone Probe (5,000 steps)"
t2=$(date +%s)
PYTHON="$PY" bash runnable/_launch/ppg.sh Door 1 \
    --interacts_total 5000 \
    2>&1 | tee "$OUT/ppg_probe.log"
echo "PPG probe completed in $(( $(date +%s) - t2 ))s"

step "11. Probe 2D: ALDA Standalone Probe (5,000 steps, Full Buffer)"
t3=$(date +%s)
PYTHON="$PY" bash runnable/_launch/alda.sh \
    --spec.trainer.config.n_train_steps=5000 --spec.trainer.config.seed=1 \
    2>&1 | tee "$OUT/alda_probe.log"
echo "ALDA probe completed in $(( $(date +%s) - t3 ))s"

step "12. Package Artifacts & Telemetry Logs"
tar -czf "$RESULT" -C "$OUT" .
echo "Packaging complete: $(wc -c < "$RESULT") bytes written to $RESULT"
step "TOTAL STAGE 2 DURATION: $(( $(date +%s) - JOB_START ))s"
