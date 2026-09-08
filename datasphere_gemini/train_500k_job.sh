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
# Authored by Gemini: DataSphere 500k benchmark training and evaluation runner for gt4i.1
# Fully isolated, handles buffer preservation, thread constraints, EGL/CUDA gates, and W&B logging.
set -uo pipefail

JOB_START=$(date +%s)
CODE="${1:?code tarball}"
RESULT="${2:?result tarball}"
WKEY="${3:-}"

AGENT="${AGENT:-svea}"
TASK="${TASK:-Door}"
SEED="${SEED:-1}"
FRAMES="${FRAMES:-505000}"       # 505k frames so C77 boundary triggers the 500k snapshot save
EVAL_EVERY="${EVAL_EVERY:-50000}"
UPSTREAM_COMMIT="90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec"
UPSTREAM_URL="https://github.com/gemcollector/RL-ViGen.git"

OUT=/tmp/out
mkdir -p "$OUT"
exec > >(tee -a "$OUT/job.log") 2>&1

step() { echo; echo "=== $1 (t+$(( $(date +%s) - JOB_START ))s) ==="; }

step "1. Hardware and CGroup Inspection"
uname -a
nproc
free -h
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || echo "No GPU detected via nvidia-smi"

step "2. System Dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq python3 python3-pip python3-dev python3-venv build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1

PY=$(command -v python3)
echo "Python: $("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])') at $PY"

step "3. Unpack Code Payload"
mkdir -p /tmp/w && tar --no-same-owner -xzf "$CODE" -C /tmp/w
cd /tmp/w

step "4. Clone RL-ViGen Upstream at Pinned Commit"
tc=$(date +%s)
git clone -q "$UPSTREAM_URL" RL-ViGen-upstream
git -C RL-ViGen-upstream checkout -q "$UPSTREAM_COMMIT"
echo "Cloned at commit: $(git -C RL-ViGen-upstream rev-parse HEAD) in $(( $(date +%s) - tc ))s"

step "5. Python Dependencies (PyTorch cu121 + Pinned Environment)"
tp=$(date +%s)
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 >/dev/null 2>&1

# Strip torch/torchvision from requirements.txt to prevent downgrade
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt wandb >/dev/null 2>&1

# Install Robosuite editable from vendored fork
rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1
echo "Installed Python packages in $(( $(date +%s) - tp ))s"

# Threading constraints to prevent CPU starvation on 8 vCPUs
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore
export PYTHONPATH=/tmp/w:/tmp/w/RL-ViGen-upstream:/tmp/w/RL-ViGen-upstream/envs/robosuiteVGB

step "6. Apply RL-ViGen Patches P1-P12"
"$PY" setup/apply_patches.py || { echo "ERROR: Patches failed to apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ERROR: Patch check failed"; exit 1; }
echo "Patches verified cleanly."

step "7. GL Gate (Hardware EGL Verification)"
set +e
GLOUT=$("$PY" - <<'GL' 2>&1
import os, sys
os.environ.setdefault("MUJOCO_GL", "egl")
import robosuite
env = robosuite.make("Door", robots="Panda", has_renderer=False,
                     has_offscreen_renderer=True, use_camera_obs=True,
                     camera_names="agentview", camera_heights=84, camera_widths=84,
                     control_freq=20, horizon=500, reward_shaping=True)
obs = env.reset()
img = obs["agentview_image"]
from OpenGL import GL
rend = GL.glGetString(GL.GL_RENDERER).decode()
print("GL_VENDOR   :", GL.glGetString(GL.GL_VENDOR).decode())
print("GL_RENDERER :", rend)
print("Frame shape :", img.shape, img.dtype, "Mean px:", round(float(img.mean()), 2))
sw = any(k in rend.lower() for k in ("llvmpipe", "softpipe", "swrast"))
print("Software fallback:", sw)
env.close()
sys.exit(2 if sw else 0)
GL
)
GLRC=$?
echo "$GLOUT"
if [ $GLRC -eq 2 ]; then
  echo "ABORTING: Software OpenGL renderer detected (~10x slower)."; exit 1
elif [ $GLRC -ne 0 ]; then
  echo "ABORTING: GL probe crashed with code $GLRC."; exit 1
fi
echo "Hardware GPU rendering verified."

step "8. CUDA Gate"
"$PY" - <<'CU' || { echo "ABORTING: CUDA is not available to PyTorch"; exit 1; }
import sys, time, torch
ok = torch.cuda.is_available()
print(f"PyTorch {torch.__version__} | CUDA available: {ok}")
if not ok:
    sys.exit(1)
print(f"Device name: {torch.cuda.get_device_name(0)}")
a = torch.randn(2048, 2048, device="cuda")
torch.cuda.synchronize()
t = time.time()
for _ in range(30):
    torch.mm(a, a)
torch.cuda.synchronize()
dt = time.time() - t
print(f"Matmul throughput: {30*2*2048**3/dt/1e9:.1f} GFLOP/s")
sys.exit(0)
CU

step "9. Weights & Biases Setup"
if [ -n "$WKEY" ] && [ -s "$WKEY" ]; then
  WANDB_API_KEY=$(cat "$WKEY")
  export WANDB_API_KEY
  export WANDB_PROJECT=many-gens-rl-vigen
  export WANDB_RUN_GROUP=datasphere-500k-gemini
  echo "W&B: API Key configured. Project=$WANDB_PROJECT, Group=$WANDB_RUN_GROUP"
  USE_WANDB="True"
else
  echo "W&B: No key provided or empty. Running offline."
  USE_WANDB="False"
fi

step "10. Background Snapshot Preservation Monitor"
# Background watcher to ensure intermediate checkpoints (50k, 100k, 200k, 300k, 400k, 500k) are not overwritten
"$PY" - <<'MON' &
import time, os, shutil, pathlib, glob

root = pathlib.Path("/tmp/w/RL-ViGen-upstream/exp_local")
out_dir = pathlib.Path("/tmp/out/checkpoints")
out_dir.mkdir(parents=True, exist_ok=True)

seen = set()
print("Snapshot monitor started...", flush=True)

for _ in range(1200): # Watch for up to ~10 hours
    for snap in root.rglob("snapshot.pt"):
        try:
            sz = snap.stat().st_size
            if sz < 1000000: # Wait until written
                continue
            mtime = snap.stat().st_mtime
            key = (str(snap), mtime)
            if key not in seen:
                # Attempt to extract step
                import torch
                payload = torch.load(snap, map_location="cpu", weights_only=False)
                step = payload.get("_global_step", payload.get("step", int(time.time())))
                dest = out_dir / f"snapshot_{step}_frames.pt"
                shutil.copy2(snap, dest)
                print(f"[PRESERVE] Copied snapshot at step {step} -> {dest.name} ({sz/1e6:.1f} MB)", flush=True)
                seen.add(key)
        except Exception as e:
            pass
    time.sleep(15)
MON
MON_PID=$!

step "11. Launch 500k Training Run ($AGENT on $TASK, Seed $SEED)"
t_train=$(date +%s)
PYTHON="$PY" bash runnable/_launch/rlvigen.sh "$AGENT" "$TASK" \
    num_train_frames="$FRAMES" eval_every_frames="$EVAL_EVERY" num_eval_episodes=10 seed="$SEED" \
    use_wandb="$USE_WANDB" use_tb=True save_snapshot=True save_video=False \
    2>&1 | tee "$OUT/train_console.log"

echo "Training completed in $(( $(date +%s) - t_train ))s"

# Terminate snapshot monitor cleanly
kill -9 $MON_PID 2>/dev/null || true

step "12. Evaluation Sweep Across 10 Scenes (Train and Eval-Easy)"
# Run comprehensive evaluation across 10 scenes on train and eval-easy distributions
"$PY" - <<'EVAL' || echo "WARNING: Eval script encountered non-critical exception"
import sys, os, glob, json, pathlib
import torch
import numpy as np
from rlgen.protocol import Protocol
from rlgen.evaluate import evaluate

exp_dirs = glob.glob("/tmp/w/RL-ViGen-upstream/exp_local/*/*")
if exp_dirs:
    latest_dir = max(exp_dirs, key=os.path.getmtime)
    snap_path = os.path.join(latest_dir, "snapshot.pt")
    if os.path.exists(snap_path):
        print(f"Loading final policy from {snap_path} for 10-scene evaluation...")
        payload = torch.load(snap_path, map_location="cuda" if torch.cuda.is_available() else "cpu", weights_only=False)
        agent = payload["agent"]
        
        protocol = Protocol(task=os.environ.get("TASK", "Door"), episodes_per_scene=10)
        
        for mode in ("train", "eval-easy"):
            print(f"Evaluating on regime: {mode} (10 scenes x 10 episodes)...")
            def policy_fn(obs):
                with torch.no_grad():
                    # Format observation tensor [C, H, W] -> [1, C, H, W]
                    t_obs = torch.as_tensor(obs, device="cuda" if torch.cuda.is_available() else "cpu").unsqueeze(0)
                    act = agent.act(t_obs, step=500000, eval_mode=True)
                    if isinstance(act, torch.Tensor):
                        act = act.cpu().numpy()
                    return np.squeeze(act, axis=0)
            
            res = evaluate(protocol, policy_fn, mode=mode)
            res_dict = {
                "mode": mode,
                "returns": [float(x) for x in res.returns],
                "scalars": {k: float(v) for k, v in res.scalars.items()},
                "per_scene": {str(k): [float(x) for x in v] for k, v in res.per_scene().items()}
            }
            out_file = f"/tmp/out/eval_500k_{mode}.json"
            with open(out_file, "w") as f:
                json.dump(res_dict, f, indent=2)
            print(f"Regime {mode} evaluation saved to {out_file} (Mean return: {res.scalars.get('mean_return', 0):.2f})")
EVAL

step "13. Collect Artifacts and Logs"
# Copy all train logs, eval CSVs, hydra configs, TensorBoard logs, and preserved checkpoints
mkdir -p "$OUT/hydra" "$OUT/tb" "$OUT/csv"
find /tmp/w/RL-ViGen-upstream/exp_local -name "*.csv" -exec cp {} "$OUT/csv/" \; 2>/dev/null || true
find /tmp/w/RL-ViGen-upstream/exp_local -name "*.yaml" -exec cp {} "$OUT/hydra/" \; 2>/dev/null || true
find /tmp/w/RL-ViGen-upstream/exp_local -name "events.out.tfevents.*" -exec cp {} "$OUT/tb/" \; 2>/dev/null || true
find /tmp/w/RL-ViGen-upstream/exp_local -name "snapshot.pt" -exec cp {} "$OUT/checkpoints/final_snapshot.pt" \; 2>/dev/null || true

# Extract throughput summary
"$PY" - <<'FPS'
import re, json, glob, statistics as st
fps_list = []
log_files = glob.glob("/tmp/out/train_console.log") + glob.glob("/tmp/out/csv/train.log")
for lf in log_files:
    for line in open(lf, errors="replace"):
        m = re.search(r"^\| train .*\bF: (\d+).*\bFPS: ([\d.]+)", line)
        if m:
            fps_list.append(float(m.group(2)))
if fps_list:
    summary = {
        "n_samples": len(fps_list),
        "fps_median": round(st.median(fps_list), 2),
        "fps_mean": round(st.mean(fps_list), 2),
        "fps_min": round(min(fps_list), 2),
        "fps_max": round(max(fps_list), 2)
    }
    with open("/tmp/out/throughput_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Throughput Summary:", json.dumps(summary, indent=2))
FPS

step "14. Package Results into Archive"
cd "$OUT"
tar czf "$RESULT" .
echo "Packaging complete: $(wc -c < "$RESULT" | tr -d ' ') bytes written to $RESULT"
echo "=== TOTAL JOB DURATION: $(( $(date +%s) - JOB_START ))s ==="
