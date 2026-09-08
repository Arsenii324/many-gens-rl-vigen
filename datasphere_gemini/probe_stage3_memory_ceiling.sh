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

# Enforcement, not just the banner above: a comment protects a reader, this protects the host.
# `require_container.sh` refuses if no container is detected, because a job body run on a host
# apt-gets and pip-installs into that host's python.
_rc="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)/require_container.sh"
[[ -f "$_rc" ]] || _rc="$(cd "$(dirname "${BASH_SOURCE[0]}")/../native" 2>/dev/null && pwd)/require_container.sh"
[[ -f "$_rc" ]] || _rc="datasphere/native/require_container.sh"
if [[ -f "$_rc" ]]; then . "$_rc"; else
  echo "WARNING: require_container.sh not found beside this script; the uncontained guard did NOT run." >&2
fi
# ==============================================================================
# STAGE 3: BOX 1 25,000-STEP TIME-SERIES MEMORY CEILING & STABILITY PROBE
# ==============================================================================
set -uo pipefail

JOB_START=$(date +%s)
CODE="${1:?code tarball}"
RESULT="${2:?result tarball}"
WKEY="${3:-}"

OUT=/tmp/out
mkdir -p "$OUT" /tmp/w /tmp/ppg
exec > >(tee -a "$OUT/job.log") 2>&1

step() { echo; echo "=== $1 (t+$(( $(date +%s) - JOB_START ))s) ==="; }

step "1. System & Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq python3 python3-pip python3-dev build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    openmpi-bin libopenmpi-dev \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY="/usr/bin/python3"

step "2. Unpack Self-Contained Code Payload"
tar -xzf "$CODE" -C /tmp/w
cd /tmp/w

step "3. Python Dependencies (PyTorch cu121 + Pinned Environment)"
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 >/dev/null 2>&1
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt >/dev/null 2>&1

rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2

"$PY" setup/apply_patches.py || { echo "ERROR: Patches failed to apply"; exit 1; }

step "4. Launch Continuous Memory & VRAM Sampler Daemon"
SAMPLER_LOG="$OUT/memory_timeseries.tsv"
echo -e "timestamp\telapsed_sec\ttotal_rss_mb\tfree_ram_mb\tvram_used_mb\tp0_rss_mb\tp1_rss_mb\tp2_rss_mb\tp3_rss_mb" > "$SAMPLER_LOG"

cat << 'MEOF' > /tmp/mem_daemon.py
import time, os, subprocess, sys

out_file = sys.argv[1]
pids = [int(p) for p in sys.argv[2:] if p.isdigit()]
t0 = time.time()

def get_pid_rss(pid):
    try:
        with open(f"/proc/{pid}/statm", "r") as f:
            pages = int(f.read().split()[1])
            return round(pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
    except:
        return 0.0

def get_vram():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True)
        return float(out.strip().split()[0])
    except:
        return 0.0

def get_total_rss():
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem_total = 0
        mem_free = 0
        mem_avail = 0
        for l in lines:
            if l.startswith("MemTotal:"):
                mem_total = int(l.split()[1]) // 1024
            elif l.startswith("MemFree:"):
                mem_free = int(l.split()[1]) // 1024
            elif l.startswith("MemAvailable:"):
                mem_avail = int(l.split()[1]) // 1024
        used = mem_total - mem_avail
        return used, mem_avail
    except:
        return 0.0, 0.0

with open(out_file, "a") as f:
    while True:
        now = time.time()
        elapsed = round(now - t0, 1)
        used_mb, free_mb = get_total_rss()
        vram_mb = get_vram()
        p_rss = [get_pid_rss(p) for p in pids]
        while len(p_rss) < 4:
            p_rss.append(0.0)
            
        f.write(f"{now:.1f}\t{elapsed}\t{used_mb}\t{free_mb}\t{vram_mb}\t{p_rss[0]}\t{p_rss[1]}\t{p_rss[2]}\t{p_rss[3]}\n")
        f.flush()
        time.sleep(2.0)
MEOF

step "5. Launch 4-Worker 25,000-Step Concurrent Pack"
ROOT_DIR="/tmp/w"

# Worker 0: ALDA (Full unconstrained buffer, 25k steps) - [Gemini 2026-08-31]
(
    cd "$ROOT_DIR/runnable/alda"
    export PYTHONPATH="$ROOT_DIR/runnable/alda"
    taskset -c 0,1 "$PY" scripts/train.py \
        --experiment_spec_file specs/train_alda_robosuite_door.yaml \
        --results_dir results --use_wandb False \
        --spec_overrides --spec.trainer.config.n_train_steps=25000 --spec.trainer.config.seed=1 \
        > "$OUT/alda_25k.log" 2>&1
) &
P0=$!

# Worker 1: IDAAC (25k env steps) - [Gemini 2026-08-31]
(
    cd "$ROOT_DIR/runnable/idaac"
    export RLVIGEN_ROOT="$ROOT_DIR/RL-ViGen-upstream"
    export RLVIGEN_IMAGE_SIZE=64
    export RLVIGEN_EVAL_MODE=eval-easy
    export PYTHONPATH="$ROOT_DIR/runnable/idaac:$ROOT_DIR/ext/baselines:$ROOT_DIR/runnable/_shim/no_tf:$ROOT_DIR/runnable/_shim"
    taskset -c 2,3 "$PY" train.py \
        --env_name "robosuite:Door" --algo idaac --num_processes 1 --num_env_steps 25000 \
        > "$OUT/idaac_25k.log" 2>&1
) &
P1=$!

# Worker 2: PPG (25k interaction steps) - [Gemini 2026-08-31]
(
    cd "$ROOT_DIR/runnable/ppg"
    export RLVIGEN_ROOT="$ROOT_DIR/RL-ViGen-upstream"
    export RCALL_LOGDIR=/tmp/ppg
    export RLVIGEN_IMAGE_SIZE=64
    export PYTHONPATH="$ROOT_DIR/runnable/ppg"
    taskset -c 4,5 "$PY" -m phasic_policy_gradient.train \
        --env_name "robosuite:Door" --num_envs 1 --interacts_total 25000 \
        > "$OUT/ppg_25k.log" 2>&1
) &
P2=$!

# Worker 3: DrQ-v2 (25k train frames) - [Gemini 2026-08-31]
(
    cd "$ROOT_DIR/RL-ViGen-upstream"
    export PYTHONPATH="$ROOT_DIR/RL-ViGen-upstream"
    taskset -c 6,7 "$PY" train.py \
        env=robosuite task@_global_=Door num_train_frames=25000 eval_every_frames=25000 use_wandb=false \
        > "$OUT/drqv2_25k.log" 2>&1
) &
P3=$!

echo "Launched Worker PIDs: ALDA ($P0), IDAAC ($P1), PPG ($P2), DrQ-v2 ($P3)"

# Launch background monitor
"$PY" /tmp/mem_daemon.py "$SAMPLER_LOG" $P0 $P1 $P2 $P3 &
MONITOR_PID=$!

echo "Waiting for all 4 workers to finish 25,000 steps..."
wait $P0 $P1 $P2 $P3 || true
kill $MONITOR_PID || true

step "6. Synthesize Memory Curve Summary"
"$PY" - << 'SYNTH'
import json, glob, pathlib

try:
    with open("/tmp/out/memory_timeseries.tsv") as f:
        lines = [l.strip().split("\t") for l in f if l.strip()]
    header = lines[0]
    data = lines[1:]
    
    total_rss_vals = [float(r[2]) for r in data if len(r) > 2]
    vram_vals = [float(r[4]) for r in data if len(r) > 4]
    
    summary = {
        "samples_count": len(data),
        "peak_total_rss_mb": max(total_rss_vals) if total_rss_vals else 0,
        "initial_total_rss_mb": total_rss_vals[0] if total_rss_vals else 0,
        "growth_mb": (max(total_rss_vals) - total_rss_vals[0]) if total_rss_vals else 0,
        "peak_vram_mb": max(vram_vals) if vram_vals else 0
    }
    with open("/tmp/out/stage3_memory_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Stage 3 Memory Summary synthesized successfully:\n", json.dumps(summary, indent=2))
except Exception as e:
    print("Error synthesizing memory summary:", e)
SYNTH

cd "$OUT"
tar -czf "$RESULT" ./*
echo "Stage 3 25,000-Step Memory Probe completed successfully."
