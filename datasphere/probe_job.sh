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
# Job 2 of the DataSphere bring-up: can this box run OUR benchmark correctly, and how fast?
#
# Still no training. This answers the questions whose wrong answers are expensive, in the order
# that makes each one cheap to diagnose, and it MEASURES the things that decide how to size a real
# run. Every gate below is one that has already produced a silent wrong result in this workspace
# or the sibling project:
#
#   1 clone + install     -- reproduce setup/install.sh's path, timed (decides whether to cache)
#   2 patches applied     -- an unpatched tree EVALUATES ON THE TRAINING DISTRIBUTION and returns
#                            a plausible number. This is the single most dangerous defect here.
#   3 import doctor       -- report every missing module at once; an env worker's ImportError
#                            otherwise surfaces as an opaque "failed to start"
#   4 GL gate             -- build a robosuite env FIRST (that establishes the EGL context), then
#                            read GL_RENDERER. A software fallback is ~10x slower and its results
#                            get discarded; a CRASHED probe is a different verdict and must not be
#                            reported as "software"
#   5 CUDA gate           -- NOT implied by the GL gate. The sibling rendered on an NVIDIA L4 while
#                            torch.cuda.is_available() was False and trained ~60x slower on CPU
#                            with every other check green
#   6 protocol hash       -- the box must compute the SAME hash as this laptop, or its numbers
#                            cannot sit in the same table as the local ones
#   7 mode verification   -- every eval regime constructs AND reports the regime it was asked for
#   8 throughput          -- env steps/s with a render/physics split, so the real run is sized on
#                            a measurement rather than on hope
#   9 end-to-end eval     -- rlgen.evaluate against the real simulator, the actual deliverable path
#
# Results are packed and verified before exit, with the same discipline as pullback_job.sh: `tar`
# exiting 0 does not mean the archive holds what was promised.
set -uo pipefail
CODE=${1:?code tarball}
RESULT=${2:?result tarball}
UPSTREAM_COMMIT=${UPSTREAM_COMMIT:-90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec}
UPSTREAM_URL=${UPSTREAM_URL:-https://github.com/gemcollector/RL-ViGen.git}
EXPECT_HASH=${EXPECT_HASH:-}
t0=$(date +%s)
fsize() { wc -c < "$1" | tr -d ' '; }
step() { echo; echo "=== $1  (t+$(( $(date +%s) - t0 ))s) ==="; }

OUT=/tmp/out; mkdir -p "$OUT"
exec > >(tee -a "$OUT/probe.log") 2>&1     # everything also lands in the returned archive

step "box"
uname -a; nproc; free -g | awk 'NR==2{print "RAM "$2"G total, "$7"G avail"}'
df -h /tmp | tail -1
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || echo "no nvidia-smi"

step "system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1
# libglvnd0 + libgl1 matter as much as libegl1: with EGL alone PyOpenGL gets a context and no way
# to draw through it ('NoneType' object has no attribute 'glGetError').
apt-get install -y -qq python3 python3-pip python3-dev python3-venv build-essential git curl \
    libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 patchelf \
    libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null 2>&1
PY=$(command -v python3)
echo "python: $("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])') at $PY"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,9) else 1)' \
  || { echo "ABORTING: need Python >= 3.9"; exit 1; }

step "unpack our code"
mkdir -p /tmp/w && tar --no-same-owner -xzf "$CODE" -C /tmp/w
cd /tmp/w
ls -d rlgen tests setup configs >/dev/null || { echo "ABORTING: payload is not our repo"; exit 1; }

step "clone RL-ViGen upstream at the pinned commit"
tc=$(date +%s)
git clone -q "$UPSTREAM_URL" RL-ViGen-upstream || { echo "ABORTING: clone failed"; exit 1; }
git -C RL-ViGen-upstream checkout -q "$UPSTREAM_COMMIT" || { echo "ABORTING: pinned commit missing"; exit 1; }
echo "clone+checkout seconds: $(( $(date +%s) - tc ))"
echo "upstream size: $(du -sh RL-ViGen-upstream | cut -f1)"
echo "upstream HEAD: $(git -C RL-ViGen-upstream rev-parse HEAD)"

step "python dependencies"
tp=$(date +%s)
"$PY" -m pip -q install --upgrade pip >/dev/null 2>&1
# torch FIRST and pinned to a cu12x wheel. An unpinned torch pulled a CUDA-13 default wheel whose
# runtime the T4 driver (12.2) cannot load, and torch.cuda.is_available() then returns False while
# every install step reports success -- a GPU job that succeeds at everything except being a GPU job.
"$PY" -m pip -q install torch torchvision --index-url https://download.pytorch.org/whl/cu121 \
  >/dev/null 2>&1 || { echo "ABORTING: torch install failed"; exit 1; }
# Then our pins, minus torch/torchvision which are already placed above.
grep -vE '^\s*(torch|torchvision)\b' requirements.txt > /tmp/req-notorch.txt
"$PY" -m pip -q install -r /tmp/req-notorch.txt >/dev/null 2>&1 \
  || { echo "ABORTING: requirements install failed"; "$PY" -m pip install -r /tmp/req-notorch.txt 2>&1 | tail -20; exit 1; }
# robosuite EDITABLE from the fork -- a wheel build drops models/assets and every texture lookup
# fails at eval time. --no-deps so it cannot move our pins.
rm -rf RL-ViGen-upstream/third_party/robosuite/build RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/third_party/robosuite >/dev/null 2>&1 \
  || { echo "ABORTING: robosuite editable install failed"; exit 1; }
"$PY" -m pip -q install --no-deps -e ./RL-ViGen-upstream/envs/robosuiteVGB/ >/dev/null 2>&1 || true
echo "install seconds: $(( $(date +%s) - tp ))"

export PYTHONPATH=/tmp/w
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MKL_SERVICE_FORCE_INTEL=1 PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

step "patches -- the unpatched tree evaluates on the training distribution"
"$PY" setup/apply_patches.py   || { echo "ABORTING: patches did not apply"; exit 1; }
"$PY" setup/apply_patches.py --check || { echo "ABORTING: --check disagrees with apply"; exit 1; }
"$PY" setup/install_assets.py --check || echo "WARNING: asset check reported a problem"

step "import doctor"
"$PY" - <<'DOC'
import importlib, sys
missing = []
for m in ('torch','numpy','robosuite','mujoco','cv2','gym','dm_control','dm_env','hydra',
          'omegaconf','termcolor','yaml','pandas','h5py','matplotlib','captum',
          'rlgen.protocol','rlgen.envs','rlgen.evaluate','rlgen.registry'):
    try:
        importlib.import_module(m)
    except Exception as e:
        missing.append(f'{m}: {type(e).__name__}: {e}')
print('IMPORT DOCTOR:', 'ALL OK' if not missing else f'{len(missing)} FAILED')
for x in missing:
    print('  MISSING', x)
sys.exit(1 if missing else 0)
DOC
[ $? -ne 0 ] && { echo "ABORTING: dependencies incomplete -- see IMPORT DOCTOR"; exit 1; }

step "GL gate"
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
print("frame       :", img.shape, img.dtype, "mean px", round(float(img.mean()), 2))
sw = any(k in rend.lower() for k in ("llvmpipe", "softpipe", "swrast"))
print("software_fallback:", sw)
env.close()
sys.exit(2 if sw else 0)
GL
)
GLRC=$?
echo "$GLOUT"
if [ $GLRC -eq 2 ]; then
  echo "ABORTING: software renderer -- ~10x slower and the result would be discarded"; exit 1
elif [ $GLRC -ne 0 ]; then
  echo "ABORTING: GL probe CRASHED (exit $GLRC) -- this is NOT a software-rendering verdict"; exit 1
fi
echo "GPU rendering confirmed"

step "CUDA gate -- separate device path from rendering, gate both"
"$PY" - <<'CU' || { echo "ABORTING: torch cannot see the GPU -- would silently train on CPU"; exit 1; }
import sys, time, torch
ok = torch.cuda.is_available()
print(f"torch {torch.__version__} cuda_available={ok}"
      + (f" device={torch.cuda.get_device_name(0)}" if ok else ""))
if ok:
    a = torch.randn(2048, 2048, device="cuda"); torch.cuda.synchronize()
    t = time.time(); [torch.mm(a, a) for _ in range(20)]; torch.cuda.synchronize()
    print(f"matmul throughput: {20*2*2048**3/(time.time()-t)/1e9:.0f} GFLOP/s")
sys.exit(0 if ok else 1)
CU

step "protocol hash -- must equal the one computed on the laptop"
"$PY" - <<PH
import json, sys
from rlgen.protocol import Protocol
p = Protocol(task="Door")
h = p.hash()
print("protocol hash:", h)
expect = "${EXPECT_HASH}"
if expect:
    if h != expect:
        print(f"ABORTING: hash {h} != expected {expect} -- remote numbers could not be pooled "
              f"with local ones. Something in the protocol resolves differently on this box.")
        sys.exit(1)
    print("hash matches the laptop")
else:
    print("no EXPECT_HASH supplied; recording only")
json.dump({"protocol_hash": h, "card": p.card()}, open("/tmp/out/protocol.json", "w"),
          indent=2, default=str)
PH
[ $? -ne 0 ] && { echo "ABORTING: protocol hash mismatch"; exit 1; }

step "every regime constructs AND reports what it was asked for"
"$PY" - <<'MODES' || { echo "ABORTING: a regime did not verify"; exit 1; }
import sys
from rlgen.envs import EnvSpec, make_env
bad = []
for task in ("Door", "Lift"):
    for mode in ("train", "eval-easy", "eval-hard"):
        try:
            e = make_env(EnvSpec(task=task, mode=mode, scene_id=0, seed=0))
            o = e.reset()
            print(f"  {task:5s} {mode:11s} obs={o.shape} {o.dtype} act={e.act_dim}")
            e.close()
        except Exception as ex:
            bad.append(f"{task}/{mode}: {type(ex).__name__}: {ex}")
for b in bad:
    print("  FAILED", b)
sys.exit(1 if bad else 0)
MODES

step "throughput -- sizes every future run, so measure it rather than assume"
"$PY" - <<'TP'
import json, time, numpy as np
from rlgen.envs import EnvSpec, make_env
res = {}
for mode in ("train", "eval-hard"):
    e = make_env(EnvSpec(task="Door", mode=mode, scene_id=0, seed=0))
    e.reset()
    a = np.zeros(e.act_dim, dtype=np.float32)
    for _ in range(10):                     # warm up; the first steps are not representative
        e.step(a)
    N = 200
    t = time.time()
    for _ in range(N):
        e.step(a)
    dt = time.time() - t
    res[mode] = {"steps_per_s": N/dt, "ms_per_step": 1000*dt/N}
    print(f"  {mode:10s} {N/dt:7.1f} steps/s   {1000*dt/N:6.2f} ms/step")
    e.close()
json.dump(res, open("/tmp/out/throughput.json", "w"), indent=2)
TP

step "end-to-end evaluation through rlgen.evaluate -- the actual deliverable path"
"$PY" - <<'EV'
import json
import numpy as np
from rlgen.protocol import Protocol
from rlgen.evaluate import evaluate
p = Protocol(task="Door", horizon=20, episodes_per_scene=1, eval_scene_ids=(0, 1))
rng = np.random.default_rng(0)
def policy(obs):
    return rng.uniform(-1, 1, size=7).astype(np.float32)
res = evaluate(p, policy, mode="eval-easy")
print(f"  episodes     : {len(res.records)}")
print(f"  protocol hash: {res.protocol_hash}")
print(f"  mode         : {res.mode}")
print(f"  returns      : {[round(float(x), 3) for x in res.returns]}")
print(f"  scalars      : { {k: round(float(v), 4) for k, v in res.scalars.items()} }")
json.dump({"protocol_hash": res.protocol_hash, "mode": res.mode,
           "returns": [float(x) for x in res.returns],
           "per_scene": {str(k): [float(x) for x in v] for k, v in res.per_scene().items()},
           "scalars": {k: float(v) for k, v in res.scalars.items()}},
          open("/tmp/out/eval_rows.json", "w"), indent=2)
EV
[ $? -ne 0 ] && { echo "WARNING: end-to-end evaluate failed -- see traceback above"; }

step "pack"
cp /tmp/req-notorch.txt "$OUT/" 2>/dev/null || true
"$PY" -m pip freeze > "$OUT/pip-freeze.txt" 2>/dev/null || true
if ! tar czf "$RESULT" -C "$OUT" .; then
  echo "!! PACKING FAILED -- the job would report SUCCESS with no artifacts"; exit 1
fi
# `tar` exiting 0 says the command ran, not that the archive holds what was promised.
for must in ./probe.log ./protocol.json; do
  tar tzf "$RESULT" | grep -qx "$must" || { echo "!! $must missing from archive"; tar tzf "$RESULT"; exit 1; }
done
echo "packed $(fsize "$RESULT") bytes, archive verified"
echo "=== total seconds: $(( $(date +%s) - t0 )) ==="
