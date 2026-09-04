#!/usr/bin/env bash
# Measure TRAINING throughput for a real baseline on a T4. Not a training run -- a measurement.
#
# WHY THIS JOB EXISTS. docs/CONSTRUCTION.md C34 measured local training at ~3 FPS, which puts one
# run at RL-ViGen's own 1.1M-frame budget at ~102 hours and the full design at ~12,000 hours. The
# whole sweep therefore rests on one unmeasured number: what a T4 actually does. Two facts already
# in this workspace say it cannot be assumed:
#
#   * ccm-intro/docs/compute-yandex-datasphere.md measured a visual-RL workload at 378 steps/s on
#     a T4 against 212 on an M2 Pro -- only 1.78x -- and concluded "benchmark before budgeting".
#   * datasphere/README.md measured 77.9 ENV steps/s here, SLOWER than this laptop's ~100, because
#     stepping is CPU-bound (physics ~88%, render ~12%) and gt4.1 has 4 vCPU.
#
# So the GPU can only accelerate the gradient half, and env stepping is a hard floor of ~3.9 h per
# 1.1M-frame run regardless of GPU. This job measures where the combined rate actually lands.
#
# It runs SVEA through `runnable/_launch/rlvigen.sh` -- the SAME entry point as locally, not a
# re-derivation -- so the number is comparable to the local one by construction.
set -uo pipefail
JOB_START=$(date +%s)
CODE="${1:?code tarball}"; RESULT="${2:?result tarball}"
FRAMES="${FRAMES:-8000}"          # seed frames are 4000; this leaves 4000 of real training
UPSTREAM_URL="https://github.com/gemcollector/RL-ViGen.git"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-90d8b8c}"

step(){ echo; echo "== $* (t+$(( $(date +%s) - JOB_START ))s)"; }
mkdir -p /tmp/out

step "system deps"
apt-get -qq update >/dev/null 2>&1
apt-get -qq install -y git libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY=$(command -v python3)
echo "python: $("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"

step "unpack our code"
mkdir -p /tmp/w && tar --no-same-owner -xzf "$CODE" -C /tmp/w
cd /tmp/w
ls -d setup runnable/_launch >/dev/null || { echo "ABORTING: payload is not the clone-era set"; exit 1; }

step "clone RL-ViGen at the pinned commit"
git clone -q "$UPSTREAM_URL" RL-ViGen-upstream || { echo "ABORTING: clone failed"; exit 1; }
git -C RL-ViGen-upstream checkout -q "$UPSTREAM_COMMIT" || { echo "ABORTING: pinned commit missing"; exit 1; }

step "python dependencies"
tp=$(date +%s)
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
# torch pinned to a cu12x wheel: an unpinned torch pulled a CUDA-13 wheel the T4 driver cannot
# load, and cuda.is_available() then returns False while every install step reports success.
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 \
  >/dev/null 2>&1 || { echo "ABORTING: torch install failed"; exit 1; }
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt >/dev/null 2>&1 \
  || { echo "ABORTING: requirements install failed"; exit 1; }
rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1 \
  || { echo "ABORTING: robosuite editable install failed"; exit 1; }
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1 || true
echo "install seconds: $(( $(date +%s) - tp ))"

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore

step "patches -- an unpatched tree evaluates on the TRAINING distribution and returns a plausible number"
"$PY" setup/apply_patches.py       || { echo "ABORTING: patches did not apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ABORTING: --check disagrees with apply"; exit 1; }

step "CUDA gate -- NOT implied by anything else"
"$PY" - <<'CU' || { echo "ABORTING: no usable CUDA; an FPS measured on CPU answers a different question"; exit 1; }
import sys, torch
ok = torch.cuda.is_available()
print("torch", torch.__version__, "cuda_available", ok,
      "device", torch.cuda.get_device_name(0) if ok else "-")
sys.exit(0 if ok else 1)
CU

step "GL gate -- build a robosuite env FIRST, that is what establishes the EGL context"
cd /tmp/w
PYTHONPATH="/tmp/w/RL-ViGen-upstream:/tmp/w/RL-ViGen-upstream/envs/robosuiteVGB" \
RLVIGEN_ROOT=/tmp/w/RL-ViGen-upstream "$PY" - <<'GL' || echo "WARNING: GL gate did not complete"
import robosuitevgb.utils as ru
env = ru.make_env(task_name="Door", seed=0, scene_id=0, mode="train"); env.reset()
from OpenGL import GL
print("GL_RENDERER:", GL.glGetString(GL.GL_RENDERER))
GL

step "the measurement: SVEA on Door through its OWN launcher, $FRAMES frames"
tt=$(date +%s)
PYTHON="$PY" timeout 5400 bash runnable/_launch/rlvigen.sh svea Door \
    num_train_frames="$FRAMES" eval_every_frames=1000000 num_eval_episodes=1 seed=1 \
    2>&1 | tee /tmp/out/train.log | grep -E "^\| (train|eval)" || true
echo "train wall seconds: $(( $(date +%s) - tt ))"

step "extract FPS"
"$PY" - <<'FPS' | tee /tmp/out/fps.txt
import re, json, statistics as st
rows = []
for line in open("/tmp/out/train.log", errors="replace"):
    line = re.sub(r"\x1b\[[0-9;]*m", "", line)
    m = re.search(r"^\| train .*\bF: (\d+).*\bFPS: ([\d.]+)", line)
    if m:
        rows.append((int(m.group(1)), float(m.group(2))))
if not rows:
    print("NO TRAIN LINES -- the run produced no throughput to report"); raise SystemExit(1)
fps = [f for _, f in rows]
out = {"n_points": len(fps), "fps_median": st.median(fps), "fps_mean": st.mean(fps),
       "fps_min": min(fps), "fps_max": max(fps), "last_frame": rows[-1][0],
       "points": rows}
print(json.dumps(out, indent=2))
open("/tmp/out/fps.json", "w").write(json.dumps(out, indent=2))
FPS

step "pack"
cp /tmp/out/train.log /tmp/out/ 2>/dev/null || true
tar czf "$RESULT" -C /tmp/out . || { echo "ABORTING: pack failed"; exit 1; }
# `tar` exiting 0 does not mean the archive holds what was promised -- the same guard the
# pullback job earned the hard way.
tar tzf "$RESULT" | grep -q "fps.json" || { echo "ABORTING: result lacks fps.json"; exit 1; }
echo "packed $(wc -c < "$RESULT") bytes; total $(( $(date +%s) - JOB_START ))s"
