#!/usr/bin/env bash
set -uo pipefail

JOB_START=$(date +%s)
CODE="${1:?code tarball}"
RESULT="${2:?result tarball}"
WKEY="${3:-}"

OUT=/tmp/out
mkdir -p "$OUT" /tmp/w
exec > >(tee -a "$OUT/job.log") 2>&1

step() { echo; echo "=== $1 (t+$(( $(date +%s) - JOB_START ))s) ==="; }

step "1. Hardware & System Inspection"
uname -a
free -h || true
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

step "2. System Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq python3 python3-pip python3-dev build-essential \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    openmpi-bin libopenmpi-dev >/dev/null 2>&1 || true

step "3. Unpack Self-Contained Code Payload"
tar -xzf "$CODE" -C /tmp/w

step "4. Python Dependencies"
PY="/usr/bin/python3"
"$PY" -m pip install --no-cache-dir --quiet torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -n 2 || true
"$PY" -m pip install --no-cache-dir --quiet -r /tmp/w/requirements.txt 2>&1 | tail -n 2 || true

step "5. Environment Verification"
"$PY" -c "import torch, sklearn, einops; print('PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'sklearn:', sklearn.__version__, 'einops:', einops.__version__)"

step "6. Launch Standalone ALDA (5,000 steps)"
export MUJOCO_GL="egl"
export RLVIGEN_ROOT="/tmp/w/RL-ViGen-upstream"
export PYTHONPATH="/tmp/w/runnable/alda"

cd /tmp/w/runnable/alda
"$PY" scripts/train.py \
    --experiment_spec_file specs/train_alda_robosuite_door.yaml \
    --results_dir results \
    --use_wandb False \
    --spec_overrides --spec.trainer.config.n_train_steps=5000 --spec.trainer.config.seed=1 \
    > "$OUT/alda_probe.log" 2>&1 || true

step "7. Verify & Package Artifacts"
tar -czf "$RESULT" -C "$OUT" .
echo "=== ALDA Standalone Probe Complete ==="
