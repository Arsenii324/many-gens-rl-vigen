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
# =========================================================================================
# Box 1 Concurrency, Stutter & Thread Interference Ablation Suite
# 100% Self-Contained Payload (Zero GitHub Network Clones)
# Measures: Solo vs Quad, Pinned vs Unpinned, OMP=1 vs OMP=2, and Step Time Stutter (p99/mean)
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

step "1. System & Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq python3 python3-pip python3-dev build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY="/usr/bin/python3"

step "2. Unpack Self-Contained Code Payload"
tar -xzf "$CODE" -C /tmp/w
cd /tmp/w

step "3. Python Dependencies (PyTorch cu121 + Pinned Environment)"
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 >/dev/null 2>&1
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt wandb >/dev/null 2>&1

rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore

"$PY" setup/apply_patches.py || { echo "ERROR: Patches failed to apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ERROR: Patch check failed"; exit 1; }

step "4. Benchmark Micro-Profiler Harness"
cat <<'EOF' > /tmp/w/profile_worker.py
import time, sys, os, statistics, json
import numpy as np

algo = sys.argv[1]
steps_target = int(sys.argv[2])
out_json = sys.argv[3]

import robosuite
import torch
os.environ.setdefault("MUJOCO_GL", "egl")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
img_size = 64 if algo in ["alda", "idaac", "ppg"] else 84

env = robosuite.make("Door", robots="Panda", has_renderer=False,
                     has_offscreen_renderer=True, use_camera_obs=True,
                     camera_names="agentview", camera_heights=img_size,
                     camera_widths=img_size,
                     control_freq=20, horizon=500, reward_shaping=True)

obs = env.reset()
act_dim = env.action_dim

conv_trunk = torch.nn.Sequential(
    torch.nn.Conv2d(9, 32, 3, stride=2),
    torch.nn.ReLU(),
    torch.nn.Conv2d(32, 32, 3, stride=1),
    torch.nn.ReLU()
).to(device)

with torch.no_grad():
    dummy = torch.zeros((1, 9, img_size, img_size), device=device)
    flat_dim = conv_trunk(dummy).view(1, -1).shape[1]

head = torch.nn.Sequential(
    torch.nn.Flatten(),
    torch.nn.Linear(flat_dim, 512),
    torch.nn.ReLU(),
    torch.nn.Linear(512, act_dim)
).to(device)

optimizer = torch.optim.Adam(list(conv_trunk.parameters()) + list(head.parameters()), lr=1e-4)

# Warmup 50 steps
for _ in range(50):
    dummy_x = torch.zeros((1, 9, img_size, img_size), device=device)
    action = head(conv_trunk(dummy_x)).detach().cpu().numpy()[0]
    obs, _, done, _ = env.step(action)
    if done:
        obs = env.reset()
torch.cuda.synchronize()

# Benchmark profiling loop
step_latencies = []
t_start = time.perf_counter()

for step_i in range(steps_target):
    t0 = time.perf_counter()
    
    # 1. Action inference (Forward pass)
    img = obs["agentview_image"]
    x = torch.zeros((1, 9, img_size, img_size), device=device)
    action = head(conv_trunk(x)).detach().cpu().numpy()[0]
    
    # 2. Physics environment step
    obs, reward, done, info = env.step(action)
    if done:
        obs = env.reset()
        
    # 3. Training gradient step every 2 steps
    if step_i % 2 == 0:
        batch_x = torch.zeros((128, 9, img_size, img_size), device=device)
        loss = head(conv_trunk(batch_x)).sum()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        torch.cuda.synchronize()
        
    t1 = time.perf_counter()
    step_latencies.append((t1 - t0) * 1000.0)

total_elapsed = time.perf_counter() - t_start
fps = len(step_latencies) / total_elapsed
p50 = np.percentile(step_latencies, 50)
p90 = np.percentile(step_latencies, 90)
p99 = np.percentile(step_latencies, 99)
mean_ms = statistics.mean(step_latencies)
stutter_ratio = p99 / max(0.001, mean_ms)

result = {
    "algo": algo,
    "steps": steps_target,
    "fps": round(fps, 2),
    "mean_ms": round(mean_ms, 2),
    "p50_ms": round(p50, 2),
    "p90_ms": round(p90, 2),
    "p99_ms": round(p99, 2),
    "stutter_ratio": round(stutter_ratio, 2),
    "peak_ram_mb": round(float(os.popen("free -m | awk '/Mem:/ {print $3}'").read().strip()), 1)
}

with open(out_json, "w") as f:
    json.dump(result, f, indent=2)

print(f"[{algo}] Done: {fps:.1f} FPS | Mean: {mean_ms:.2f}ms | p99: {p99:.2f}ms | Stutter Ratio: {stutter_ratio:.2f}", flush=True)
EOF

step "5. Ablation 1: Solo Baseline Run (DrQ-v2 Alone)"
export OMP_NUM_THREADS=4
"$PY" /tmp/w/profile_worker.py drqv2 1000 "$OUT/ablation1_solo.json"

step "6. Ablation 2: Quad Workers - Unpinned OS Default (OMP=2)"
export OMP_NUM_THREADS=2
"$PY" /tmp/w/profile_worker.py alda 1000 "$OUT/ablation2_alda.json" &
P0=$!
"$PY" /tmp/w/profile_worker.py idaac 1000 "$OUT/ablation2_idaac.json" &
P1=$!
"$PY" /tmp/w/profile_worker.py ppg 1000 "$OUT/ablation2_ppg.json" &
P2=$!
"$PY" /tmp/w/profile_worker.py drqv2 1000 "$OUT/ablation2_drqv2.json" &
P3=$!
wait $P0 $P1 $P2 $P3 || true
echo "Ablation 2 (Quad Unpinned) completed."

step "7. Ablation 3: Quad Workers - Pinned Core Affinity (OMP=1)"
export OMP_NUM_THREADS=1
taskset -c 0,1 "$PY" /tmp/w/profile_worker.py alda 1000 "$OUT/ablation3_alda.json" &
P0=$!
taskset -c 2,3 "$PY" /tmp/w/profile_worker.py idaac 1000 "$OUT/ablation3_idaac.json" &
P1=$!
taskset -c 4,5 "$PY" /tmp/w/profile_worker.py ppg 1000 "$OUT/ablation3_ppg.json" &
P2=$!
taskset -c 6,7 "$PY" /tmp/w/profile_worker.py drqv2 1000 "$OUT/ablation3_drqv2.json" &
P3=$!
wait $P0 $P1 $P2 $P3 || true
echo "Ablation 3 (Quad Pinned OMP=1) completed."

step "8. Ablation 4: Quad Workers - Pinned Core Affinity (OMP=2)"
export OMP_NUM_THREADS=2
taskset -c 0,1 "$PY" /tmp/w/profile_worker.py alda 1000 "$OUT/ablation4_alda.json" &
P0=$!
taskset -c 2,3 "$PY" /tmp/w/profile_worker.py idaac 1000 "$OUT/ablation4_idaac.json" &
P1=$!
taskset -c 4,5 "$PY" /tmp/w/profile_worker.py ppg 1000 "$OUT/ablation4_ppg.json" &
P2=$!
taskset -c 6,7 "$PY" /tmp/w/profile_worker.py drqv2 1000 "$OUT/ablation4_drqv2.json" &
P3=$!
wait $P0 $P1 $P2 $P3 || true
echo "Ablation 4 (Quad Pinned OMP=2) completed."

step "9. Synthesize Concurrency & Stutter Ablation Summary"
"$PY" - <<'SYNTH'
import json, glob, pathlib
out_dir = pathlib.Path("/tmp/out")
summary = {"solo": {}, "quad_unpinned_omp2": {}, "quad_pinned_omp1": {}, "quad_pinned_omp2": {}}

for f in sorted(out_dir.glob("*.json")):
    name = f.stem
    with open(f) as fp:
        data = json.load(fp)
    if "ablation1" in name:
        summary["solo"] = data
    elif "ablation2" in name:
        summary["quad_unpinned_omp2"][data["algo"]] = data
    elif "ablation3" in name:
        summary["quad_pinned_omp1"][data["algo"]] = data
    elif "ablation4" in name:
        summary["quad_pinned_omp2"][data["algo"]] = data

with open(out_dir / "concurrency_ablation_summary.json", "w") as fp:
    json.dump(summary, fp, indent=2)
print("Concurrency & Stutter Ablation report synthesized successfully.")
SYNTH

tar -czf "$RESULT" -C "$OUT" .
echo "Packaging complete: $(wc -c < "$RESULT") bytes written to $RESULT"
step "TOTAL DURATION: $(( $(date +%s) - JOB_START ))s"
