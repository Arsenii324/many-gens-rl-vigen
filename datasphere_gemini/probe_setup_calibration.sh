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
# Phase 1 Calibration Probe on DataSphere gt4i.1 (Tesla T4i / NVIDIA L4)
# Authored by Gemini (2026-08-31)
# =========================================================================================
set -uo pipefail

JOB_START=$(date +%s)
CODE="${1:?code tarball}"
RESULT="${2:?result tarball}"
WKEY="${3:-}"

OUT=/tmp/out
mkdir -p "$OUT" /tmp/w
exec > >(tee -a "$OUT/job.log") 2>&1

step() { echo; echo "=== $1 (t+$(( $(date +%s) - JOB_START ))s) ==="; }

step "1. Hardware and CGroup Inspection"
uname -a
nproc || true
free -h || true
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

step "2. System Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq python3 python3-pip python3-dev build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY="/usr/bin/python3"
echo "Python: $("$PY" -V 2>&1 | cut -d' ' -f2) at $PY"

step "3. Unpack Code Payload"
tar -xzf "$CODE" -C /tmp/w
cd /tmp/w

step "4. Clone RL-ViGen Upstream at Pinned Commit"
tc=$(date +%s)
git clone -q https://github.com/gemcollector/RL-ViGen.git RL-ViGen-upstream
(cd RL-ViGen-upstream && git checkout -q 90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec)
echo "Cloned at commit: $(cd RL-ViGen-upstream && git rev-parse HEAD) in $(( $(date +%s) - tc ))s"

step "5. Python Dependencies (PyTorch cu121 + Pinned Environment)"
tp=$(date +%s)
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 >/dev/null 2>&1
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt wandb >/dev/null 2>&1

rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1
echo "Installed Python packages in $(( $(date +%s) - tp ))s"

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore
export PYTHONPATH=/tmp/w:/tmp/w/RL-ViGen-upstream:/tmp/w/RL-ViGen-upstream/envs/robosuiteVGB

step "6. Apply RL-ViGen Patches P1-P14"
"$PY" setup/apply_patches.py || { echo "ERROR: Patches failed to apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ERROR: Patch check failed"; exit 1; }
echo "Patches verified cleanly."

step "7. GL & CUDA Hardware Gates"
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

"$PY" - <<'CUDA'
import torch
print("CUDA Available:", torch.cuda.is_available(), "Device:", torch.cuda.get_device_name(0))
CUDA

step "8. W&B Setup"
if [ -n "$WKEY" ] && [ -f "$WKEY" ]; then
    export WANDB_API_KEY=$(cat "$WKEY" | tr -d ' \n\r')
    "$PY" -c "import wandb; wandb.login(key='$WANDB_API_KEY')" || true
fi
export WANDB_PROJECT="many-gens-rl-vigen"

step "9. Run Single SVEA 5k Baseline (Measure Single Worker Max FPS)"
t_probe=$(date +%s)
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
PYTHON="$PY" bash runnable/_launch/rlvigen.sh svea Door \
    num_train_frames=5000 eval_every_frames=2500 num_eval_episodes=2 seed=1 \
    use_wandb=True use_tb=True save_snapshot=True save_video=False \
    2>&1 | tee "$OUT/svea_probe.log"
echo "SVEA 5k probe completed in $(( $(date +%s) - t_probe ))s"

step "10. Run 4-Worker Concurrency & Thread Calibration Probe (2k steps per worker)"
t_quad=$(date +%s)
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2

taskset -c 0,1 "$PY" RL-ViGen-upstream/train.py --config-name config env=robosuite "task@_global_=Door" action_repeat=1 num_train_frames=2000 eval_every_frames=5000 num_eval_episodes=1 seed=1 use_wandb=False use_tb=False save_snapshot=False save_video=False > "$OUT/worker_0.log" 2>&1 &
PID0=$!

taskset -c 2,3 "$PY" RL-ViGen-upstream/train.py --config-name svea_config env=robosuite "task@_global_=Door" action_repeat=1 num_train_frames=2000 eval_every_frames=5000 num_eval_episodes=1 seed=2 use_wandb=False use_tb=False save_snapshot=False save_video=False > "$OUT/worker_1.log" 2>&1 &
PID1=$!

taskset -c 4,5 "$PY" RL-ViGen-upstream/train.py --config-name drq_config env=robosuite "task@_global_=Door" action_repeat=1 num_train_frames=2000 eval_every_frames=5000 num_eval_episodes=1 seed=3 use_wandb=False use_tb=False save_snapshot=False save_video=False > "$OUT/worker_2.log" 2>&1 &
PID2=$!

taskset -c 6,7 "$PY" RL-ViGen-upstream/train.py --config-name curl_config env=robosuite "task@_global_=Door" action_repeat=1 num_train_frames=2000 eval_every_frames=5000 num_eval_episodes=1 seed=4 use_wandb=False use_tb=False save_snapshot=False save_video=False > "$OUT/worker_3.log" 2>&1 &
PID3=$!

echo "Quad workers spawned: PIDs $PID0 $PID1 $PID2 $PID3"

# Monitor loop for 4 workers
for _ in $(seq 1 60); do
    if ! kill -0 $PID0 2>/dev/null && ! kill -0 $PID1 2>/dev/null && ! kill -0 $PID2 2>/dev/null && ! kill -0 $PID3 2>/dev/null; then
        echo "All 4 workers completed!"
        break
    fi
    mem_used=$(free -m | awk '/Mem:/ {print $3}')
    echo "Active Quad Workers: RSS RAM used = ${mem_used} MB"
    sleep 5
done

wait $PID0 $PID1 $PID2 $PID3 || true
echo "Quad calibration completed in $(( $(date +%s) - t_quad ))s"

step "11. Package Artifacts and Calibration Results"
tar -czf "$RESULT" -C "$OUT" .
echo "Packaging complete: $(wc -c < "$RESULT") bytes written to $RESULT"
step "TOTAL DURATION: $(( $(date +%s) - JOB_START ))s"
