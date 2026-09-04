"""CUDA smoke for the Part 1 originals: do they run UNMODIFIED on a real GPU?

Every local run in this project is CPU or Apple MPS, and `runnable/_shim/sitecustomize.py`
exists precisely so the CUDA-native repos need no edits to run there. That shim downcasts float64
(MPS has none) and reports `is_cuda` for MPS tensors, so **a green local run does not prove the
CUDA path**. This kernel is the thing that does.

It also proves something the local runs cannot: the kernel clones each upstream from its PUBLIC
url at the SHA in PINS.json and applies `patches/<name>.patch`, so a green run here shows the
exported patches actually reproduce the local clones from public sources — not merely that they
exist. Nothing but ~100 KB of patches and this script comes from the private workspace.

Staged deliberately. Every stage reports and continues rather than aborting, because a Kaggle
round trip costs ~15 minutes and one push should answer as many questions as possible.
"""
import json
import os
import subprocess
import sys
import textwrap

# Clones go to /kaggle/temp, NOT /kaggle/working. Everything under /kaggle/working becomes the
# kernel's OUTPUT: the first run put a 1.8 GB RL-ViGen tree there, and `kaggle kernels output`
# then tried to download all of it just to fetch a log, hit the rate limiter, and blocked reading
# the result for half an hour.
WORK = "/kaggle/temp"
os.makedirs(WORK, exist_ok=True)


def find_src():
    """Locate the mounted dataset by its CONTENT, not by a guessed path.

    The first push assumed /kaggle/input/<slug>; the actual mount was
    /kaggle/input/datasets/<owner>/<slug>/<version>/. Searching for the file that must be there
    costs nothing and cannot be wrong in a way that only shows up remotely.
    """
    for root, _dirs, files in os.walk("/kaggle/input", followlinks=True):
        if "PINS.json" in files:
            return root
    return None


SRC = find_src()


def sh(cmd, cwd=None, check=False, quiet=False):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if not quiet:
        out = (r.stdout or "")[-3000:]
        err = (r.stderr or "")[-3000:]
        if out.strip():
            print(out)
        if err.strip():
            print("STDERR:", err)
    if check and r.returncode != 0:
        raise RuntimeError(f"failed ({r.returncode}): {cmd}")
    return r


def banner(t):
    print("\n" + "=" * 78 + f"\n== {t}\n" + "=" * 78, flush=True)


# ---------------------------------------------------------------------------------------------
banner("STAGE 0  base image")
print("python:", sys.version.replace("\n", " "))
sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader")
try:
    import torch
    print("torch:", torch.__version__, "| cuda build:", torch.version.cuda,
          "| is_available:", torch.cuda.is_available(),
          "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO GPU")
except Exception as e:
    print("torch import failed:", e)
import numpy
print("numpy:", numpy.__version__)
print("input dir:", SRC, sorted(os.listdir(SRC)) if SRC else "PINS.json NOT FOUND under /kaggle/input")

# ---------------------------------------------------------------------------------------------
banner("STAGE 1  dependencies")
# Pinned where the pin is load-bearing. gym is held at 0.25.2 because every one of these repos
# predates gymnasium and uses the 4-tuple step API; robosuite comes from RL-ViGen's own
# third_party tree below, not from PyPI, because that is the copy the benchmark was built on.
# numpy is NOT pinned. The first push pinned numpy<2 and got 1.26.4, which conflicts with the
# base image's tifffile/opencv/shap AND diverges from the local runs, which are on numpy 2.4.6.
# gym 0.25.2 warns loudly under numpy 2 and works, locally and here; a pin that makes the remote
# environment differ from the local one defeats the purpose of the remote check.
# Installed in SEPARATE pip calls, on purpose. A single call aborts entirely when any one
# package fails to build, and that is not hypothetical: pinning `mujoco==2.3.7` (the version this
# workspace runs locally) has no cp312 wheel, so it tried to build from source, failed, and took
# hydra down with it -- surfacing two stages later as `ModuleNotFoundError: No module named
# 'hydra'`, which says nothing about the real cause.
BASE_DEPS = ["dm_control==1.0.14", "'gym==0.25.2'", "termcolor", "imageio", "imageio-ffmpeg",
             "opencv-python-headless", "xmltodict", "tqdm", "einops", "kornia",
             "hydra-core", "omegaconf", "scipy",
             # cfgs/config.yaml declares `override hydra/launcher: submitit_local`, so hydra
             # refuses to compose without this plugin. It was missing on runs 3-6, which is one
             # concrete cause of the SVEA stage never producing output, and it costs nothing to
             # eliminate before blaming the renderer.
             "hydra-submitit-launcher",
             # tensorboard. RL-ViGen's logger.py:13 does `from torch.utils.tensorboard import
             # SummaryWriter` at MODULE SCOPE -- unconditionally, even with use_tb=False -- and
             # on this image that import SEGFAULTS the interpreter (run 9's faulthandler dump:
             # train.py:27 -> logger.py:13 -> torch/utils/tensorboard/writer.py:19). That, and
             # not the renderer or the GPU or the DataLoader, is why every SVEA stage died.
             # dmc_gb's logger imports no tensorboard, which is exactly why RAD always worked.
             "tensorboard", "protobuf"]
for _d in BASE_DEPS:
    r = sh(f"pip install -q {_d} 2>&1 | tail -2", quiet=True)
    print(f"  {'ok  ' if r.returncode == 0 else 'FAIL'} {_d}"
          + ("" if r.returncode == 0 else f"  {(r.stdout or r.stderr)[-200:]}"))

# MUJOCO, and this is the one that matters. RL-ViGen's vendored robosuite 1.4.0 calls
# `self.sim.data.qM`, which newer mujoco renamed to `M` -- run 3 died on exactly that, before a
# single env step, with "AttributeError: 'MjData' object has no attribute 'qM'". The local
# machine has 2.3.7 and so never saw it.
#
# Rather than guess a version and spend another round trip, try candidates newest-first and
# REPORT what each one actually has. The answer is then a fact in the log, not a belief.
# Run 5 settled this: mujoco<3.3 -> 3.2.7, which HAS MjData.qM, so robosuite 1.4.0 works.
# It does NOT have MjModel.tex_rgb (removed in mujoco 3.0), so RL-ViGen's texture modder --
# i.e. every eval-* regime -- cannot run here. mujoco 2.x has both but its last wheel is cp311
# and Kaggle is cp312, so on THIS platform the train regime is the most that is reachable.
# See docs/RUNNABLE-ORIGINALS.md. The list is kept so the probe re-derives it rather than
# trusting this comment.
MUJOCO_CANDIDATES = ["mujoco<3.3", "mujoco==3.1.6", "mujoco==2.3.7"]
chosen = None
for cand in MUJOCO_CANDIDATES:
    r = sh(f"pip install -q '{cand}' 2>&1 | tail -2", quiet=True)
    if r.returncode != 0:
        print(f"  FAIL install {cand}: {(r.stdout or r.stderr)[-160:]}")
        continue
    probe = sh("python -c \"import mujoco;print(mujoco.__version__, hasattr(mujoco.MjData,'qM'))\"",
               quiet=True)
    out = (probe.stdout or "").strip()
    print(f"  installed {cand:16} -> version/has_qM = {out or probe.stderr[-120:]}")
    if out.endswith("True"):
        chosen = f"{cand} ({out})"
        break
print("mujoco chosen:", chosen or "NONE HAS qM -- robosuite 1.4.0 cannot work with any of these")

# numpy version churn during pip can leave an already-imported numpy inconsistent with the one
# now on disk -- it surfaces as "numpy.dtype size changed, may indicate binary incompatibility"
# at the first C-extension import. Re-exec once so every import below sees one consistent set.
# (docs/compute-procgen.md 2.1 -- this cost a Kaggle round trip the first time.)
if os.environ.get("RLGEN_REEXEC") != "1":
    os.environ["RLGEN_REEXEC"] = "1"
    print("re-exec after dependency install", flush=True)
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy
print("numpy after re-exec:", numpy.__version__)

# ---------------------------------------------------------------------------------------------
banner("STAGE 2  clone the upstreams at their pinned SHAs")
PINS = json.load(open(os.path.join(SRC, "PINS.json")))


def clone(name, url, sha, dest):
    """Fetch one commit by SHA. GitHub serves arbitrary SHAs, so this avoids a full history."""
    if os.path.isdir(dest):
        return True
    os.makedirs(dest, exist_ok=True)
    ok = sh(f"git init -q {dest} && cd {dest} && git remote add origin {url} && "
            f"git fetch -q --depth 1 origin {sha} && git checkout -q FETCH_HEAD",
            quiet=True).returncode == 0
    if not ok:  # some servers refuse SHA fetches; fall back to full history
        sh(f"rm -rf {dest}", quiet=True)
        ok = sh(f"git clone -q {url} {dest} && cd {dest} && git checkout -q {sha}",
                quiet=True).returncode == 0
    print(f"  {name:10} {'OK ' if ok else 'FAILED'} {sha}  {url}")
    if ok:
        got = sh(f"git -C {dest} log -1 --format=%h", quiet=True).stdout.strip()
        print(f"  {'':10} HEAD is {got}  {'(matches)' if sha.startswith(got[:7]) or got.startswith(sha[:7]) else '<-- MISMATCH'}")
    return ok


# apply_patches.py derives its target as `<parent of its own dir>/RL-ViGen-upstream`, so the
# clone path and the script path are chosen to satisfy that rather than editing the script.
RLV = f"{WORK}/RL-ViGen-upstream"
clone("RL-ViGen", PINS["rl_vigen"]["url"], PINS["rl_vigen"]["sha"], RLV)
DMCGB = f"{WORK}/dmc_gb"
clone("dmc_gb", PINS["dmc_gb"]["url"], PINS["dmc_gb"]["sha"], DMCGB)

# ---------------------------------------------------------------------------------------------
banner("STAGE 3  apply the patch sets")
# RL-ViGen patches P1-P9, by the project's own script, with its own --check as the verdict.
os.makedirs(f"{WORK}/setup", exist_ok=True)
sh(f"cp {SRC}/apply_patches.py {WORK}/setup/apply_patches.py", quiet=True)
r = subprocess.run([sys.executable, f"{WORK}/setup/apply_patches.py"],
                   capture_output=True, text=True, cwd=WORK)
print(r.stdout[-4000:], r.stderr[-2000:])
r = subprocess.run([sys.executable, f"{WORK}/setup/apply_patches.py", "--check"],
                   capture_output=True, text=True, cwd=WORK)
print("apply_patches --check exit:", r.returncode)
print(r.stdout[-1500:])

# The clone patches. `git apply` fails loudly on any context mismatch, which is the point: it
# proves the patch belongs to exactly this commit.
r = sh(f"git -C {DMCGB} apply --stat {SRC}/patches/dmc_gb.patch && "
       f"git -C {DMCGB} apply {SRC}/patches/dmc_gb.patch && echo PATCH_APPLIED")
print("dmc_gb patch:", "applied" if "PATCH_APPLIED" in (r.stdout or "") else "FAILED")

# ---------------------------------------------------------------------------------------------
banner("STAGE 4  robosuite from RL-ViGen's own third_party tree")
sh(f"pip install -q -e {RLV}/third_party/robosuite 2>&1 | tail -3")
sh(f"python -c \"import robosuite; print('robosuite', robosuite.__version__)\"")

# ---------------------------------------------------------------------------------------------
banner("STAGE 5  RL-ViGen's own SVEA on its own train.py, on the GPU, with NO shim")
# RUNS FIRST, deliberately. On runs 5 and 6 this stage timed out with no output while RAD, in
# the same kernel and the same env, trained fine -- and RAD's teardown raises
# `EGLError(err = EGL_NOT_INITIALIZED)` from `eglDestroyContext`. So one hypothesis is that the
# first process leaves the EGL display unusable for the second. Putting SVEA first tests that
# directly: if it now runs and RAD (below) fails instead, the order is the cause, not the agent.
# Different dependency stack from the RAD stage (hydra + the dm_env wrapper chain + a replay
# DataLoader) and a different failure surface, so it is worth the same round trip. It also
# exercises patches P7/P8/P9, none of which stage 5 touches.
env6 = os.environ.copy()
env6.update({
    # Installing tensorboard did NOT fix the segfault (run 10): it still dies at the identical
    # line, torch/utils/tensorboard/writer.py:19. That import pulls in protobuf-generated
    # modules, and run 9's extension list shows `google._upb._message` -- protobuf's C
    # implementation. A hard crash rather than an exception is the signature of a mismatch
    # between that C extension and the generated pb2 modules. This env var makes protobuf use
    # its pure-Python backend, which is the documented escape hatch and costs only speed in a
    # code path RL-ViGen does not even use here (use_tb=False).
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    "MUJOCO_GL": "egl",
    # $RLV/algos is on the path because algos/sgqn.py does a bare `import drqv2`; harmless here.
    "PYTHONPATH": f"{RLV}:{RLV}/algos:{RLV}/envs/robosuiteVGB",
})
# -X faulthandler: run 8 turned the three timeouts into `SVEA exit: -11` (SIGSEGV) once the
# DataLoader workers were removed -- a crash, not a hang, and with EMPTY stdout, so it dies
# before the first print. faulthandler makes the interpreter dump a Python traceback on the
# fatal signal, which turns "segfaults somewhere" into a file and a line.
cmd6 = [sys.executable, "-X", "faulthandler", "train.py", "--config-name", "svea_config",
        "env=robosuite",
        "task@_global_=Door", "action_repeat=1", "use_wandb=False", "use_tb=False",
        # num_seed_frames MUST exceed one episode (500 here) or the replay loader raises
        # "IndexError: Cannot choose from an empty sequence" -- there is nothing to sample from
        # before the first episode closes. 400 was below it.
        # replay_buffer_num_workers=0. RL-ViGen defaults to 4 torch DataLoader workers, and this
        # stage has now timed out with NO OUTPUT on three consecutive runs -- second (v5, v6) and
        # first on a fresh EGL display (v7), with the hydra plugin installed and a seed budget
        # above one episode. RAD trains in the same kernel either side of it, so the renderer,
        # the GPU, the patches and the order are all excluded. Forked DataLoader workers are the
        # remaining structural difference between the two paths, and the same setting was already
        # needed locally for an unrelated reason.
        "save_video=False", "replay_buffer_num_workers=0",
        "num_train_frames=1200", "num_seed_frames=600",
        "eval_every_frames=100000", "num_eval_episodes=1"]
print("$", " ".join(cmd6), flush=True)
try:
    # 900 s, not 3600: on run 5 this stage consumed its full hour without emitting a line, for a
    # budget that takes minutes locally. A shorter cap turns "it hung" into a log with an FPS in
    # it, or at worst fails fast instead of eating the session.
    # Output goes to FILES, not PIPEs. On the three previous runs this stage timed out and
    # subprocess.run's captured output was discarded with the exception, so "it hung" carried no
    # information about WHERE. Partial output on disk survives the timeout.
    _o, _e = f"{WORK}/svea.out", f"{WORK}/svea.err"
    with open(_o, "w") as fo, open(_e, "w") as fe:
        r6 = subprocess.run(cmd6, cwd=RLV, env=env6, stdout=fo, stderr=fe, text=True,
                            timeout=900)
    print(open(_o).read()[-5000:])
    # HEAD of stderr, not the tail. robosuite's EGL contexts raise EGL_NOT_INITIALIZED from
    # __del__ at interpreter shutdown -- dozens of "Exception ignored in" blocks that are pure
    # teardown noise and that a tail slice shows instead of the real exception. Run 12 lost
    # SVEA's actual error that way. Both ends are printed now, and the EGL blocks are dropped.
    _err = open(_e).read()
    _sig = [l for l in _err.splitlines()
            if not any(t in l for t in ("EGL", "egl", "glCheckError", "__del__", "free()",
                                        "Exception ignored", "_opaque", "result = 0",
                                        "cArguments", "baseOperation", "err ="))]
    print("STDERR (EGL teardown filtered, first 60 lines):")
    print("\n".join(_sig[:60]))
    print("SVEA exit:", r6.returncode)
except Exception as e:
    print("SVEA stage did not complete:", type(e).__name__, e)
    for _f, _label in ((f"{WORK}/svea.out", "PARTIAL STDOUT"), (f"{WORK}/svea.err", "PARTIAL STDERR")):
        try:
            _t = open(_f).read()
            print(f"--- {_label} ({len(_t)} bytes) ---\n{_t[-4000:]}")
        except OSError as _oe:
            print(f"--- {_label}: unreadable ({_oe}) ---")

# ---------------------------------------------------------------------------------------------
banner("STAGE 6  RAD on RL-ViGen robosuite, on the GPU, with NO shim")
env = os.environ.copy()
env.update({
    "RLVIGEN_ROOT": RLV,
    # RAD and SODA are specified on a 100x100 render cropped to 84. At a native 84 render RAD's
    # own random_crop no-ops by its own `crop_max <= 0` guard and RAD degrades to plain SAC.
    "RLVIGEN_IMAGE_SIZE": "100",
    "MUJOCO_GL": "egl",
    "PYTHONPATH": f"{DMCGB}/src:{DMCGB}/src/env/dmc2gym:{RLV}:{RLV}/envs/robosuiteVGB",
})
# NOTE the absence of runnable/_shim from PYTHONPATH. That is the entire point of this stage.
cmd = [sys.executable, "src/train.py", "--domain_name", "robosuite", "--task_name", "Door",
       "--algorithm", "rad", "--action_repeat", "1", "--episode_length", "500",
       # --eval_mode train, NOT eval-easy: `_initialize_modders` only builds a TextureModder
       # when randomize_color is set, which train mode does not. eval-easy therefore cannot run
       # on mujoco 3.x at all (run 5 died there), while train can -- and training on CUDA is
       # what this stage exists to demonstrate.
       "--eval_mode", "train", "--seed", "0",
       "--train_steps", "1200", "--init_steps", "200", "--eval_freq", "1000",
       "--eval_episodes", "1"]   # --save_video is store_true; omitted, not set to "false"
print("$", " ".join(cmd), flush=True)
r = subprocess.run(cmd, cwd=DMCGB, env=env, capture_output=True, text=True, timeout=3600)
print(r.stdout[-6000:])
print("STDERR:", r.stderr[-4000:])
print("RAD exit:", r.returncode)

banner("DONE")
