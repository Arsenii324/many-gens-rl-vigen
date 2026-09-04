"""Part 1 CUDA smoke on DataSphere — the version where the EVAL REGIMES also work.

Same question as `compute/rlvigen-cuda-smoke/` on Kaggle: do the originals run on real CUDA, and
do the exported patches rebuild the clones from public sources? The difference is the image.
Kaggle is python 3.12, and RL-ViGen's texture modder needs mujoco 2.x (`MjModel.tex_rgb`, removed
in 3.0) whose last wheel is cp311 — so on Kaggle only the `train` regime is reachable, which is
useless for a generalisation benchmark. DataSphere pins 3.11, so `eval-easy` runs here.

Reads `PINS.json` and `patches/` from this directory (kept in sync by the sync line in the
README), clones each upstream at its pinned SHA from its PUBLIC url, applies our patch, and runs.
"""
import json, os, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
WORK = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "rlgen"
WORK.mkdir(parents=True, exist_ok=True)
OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.append(line)


def sh(cmd, cwd=None, quiet=False):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if not quiet:
        for stream in (r.stdout, r.stderr):
            if stream and stream.strip():
                say(stream[-2500:])
    return r


# Everything executable lives in main(). The datasphere CLI does not merely grep for the
# `if __name__` guard -- utils.py:296 then IMPORTS this file with importlib to analyse its
# dependencies, so with the job body at module level that import would clone the upstreams
# and start training ON THE LAPTOP every time a job is submitted. The guard is load-bearing,
# and `def clone` must precede `def main` or it silently swallows the job body -- which it
# did on the first attempt, parsing cleanly while main() shrank to 16 lines.

def clone(name, url, sha, dest):
    if dest.exists():
        return True
    ok = sh(f"git init -q {dest} && cd {dest} && git remote add origin {url} && "
            f"git fetch -q --depth 1 origin {sha} && git checkout -q FETCH_HEAD",
            quiet=True).returncode == 0
    if not ok:
        sh(f"rm -rf {dest}", quiet=True)
        ok = sh(f"git clone -q {url} {dest} && cd {dest} && git checkout -q {sha}",
                quiet=True).returncode == 0
    got = sh(f"git -C {dest} log -1 --format=%h", quiet=True).stdout.strip()
    say(f"  {name:10} {'OK ' if ok else 'FAILED'} asked {sha}, got {got}")
    return ok


def main():
    say("== base image");  say("python", sys.version.split()[0])
    sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader")
    try:
        import torch
        say("torch", torch.__version__, "| cuda", torch.version.cuda,
            "| available", torch.cuda.is_available(),
            "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO GPU")
    except Exception as e:
        say("torch import failed:", e)
    import mujoco
    say("mujoco", mujoco.__version__,
        "| MjData.qM", hasattr(mujoco.MjData, "qM"),
        "| MjModel.tex_rgb", hasattr(mujoco.MjModel, "tex_rgb"),
        "  <- BOTH must be True, or the eval regimes cannot run")

    PINS = json.load(open(HERE / "PINS.json"))

    say("\n== clone at the pinned SHAs")
    RLV = WORK / "RL-ViGen-upstream"
    clone("RL-ViGen", PINS["rl_vigen"]["url"], PINS["rl_vigen"]["sha"], RLV)
    DMCGB = WORK / "dmc_gb"
    clone("dmc_gb", PINS["dmc_gb"]["url"], PINS["dmc_gb"]["sha"], DMCGB)

    say("\n== apply the patch sets")
    (WORK / "setup").mkdir(exist_ok=True)      # apply_patches.py derives ../RL-ViGen-upstream
    sh(f"cp {HERE}/apply_patches.py {WORK}/setup/apply_patches.py", quiet=True)
    for args in ([], ["--check"]):
        r = subprocess.run([sys.executable, f"{WORK}/setup/apply_patches.py", *args],
                           capture_output=True, text=True, cwd=WORK)
        say(r.stdout[-2500:]); say("exit:", r.returncode)
    r = sh(f"git -C {DMCGB} apply {HERE}/patches/dmc_gb.patch && echo PATCH_APPLIED")
    say("dmc_gb patch:", "applied" if "PATCH_APPLIED" in (r.stdout or "") else "FAILED")

    say("\n== robosuite from RL-ViGen's own third_party")
    sh(f"pip install -q -e {RLV}/third_party/robosuite 2>&1 | tail -2")

    BASE = dict(os.environ, RLVIGEN_ROOT=str(RLV), MUJOCO_GL="egl",
                PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="python")

    say("\n== RAD, eval_mode=eval-easy  (the regime Kaggle cannot reach)")
    env = dict(BASE, RLVIGEN_IMAGE_SIZE="100",
               PYTHONPATH=f"{DMCGB}/src:{DMCGB}/src/env/dmc2gym:{RLV}:{RLV}/envs/robosuiteVGB")
    r = subprocess.run([sys.executable, "src/train.py", "--domain_name", "robosuite",
                        "--task_name", "Door", "--algorithm", "rad", "--action_repeat", "1",
                        "--episode_length", "500", "--eval_mode", "eval-easy", "--seed", "0",
                        "--train_steps", "1200", "--init_steps", "200", "--eval_freq", "1000",
                        "--eval_episodes", "1"],
                       cwd=DMCGB, env=env, capture_output=True, text=True, timeout=5400)
    say(r.stdout[-4000:]); say("STDERR:", r.stderr[-2000:]); say("RAD exit:", r.returncode)

    say("\n== SVEA, RL-ViGen's own train.py, eval env in eval-easy via P12")
    env = dict(BASE, RLVIGEN_EVAL_MODE="eval-easy",
               PYTHONPATH=f"{RLV}:{RLV}/algos:{RLV}/envs/robosuiteVGB")
    try:
        r = subprocess.run([sys.executable, "-X", "faulthandler", "train.py", "--config-name",
                            "svea_config", "env=robosuite", "task@_global_=Door", "action_repeat=1",
                            "use_wandb=False", "use_tb=False", "save_video=False",
                            "replay_buffer_num_workers=0", "num_train_frames=1200",
                            "num_seed_frames=600", "eval_every_frames=1000",
                            "num_eval_episodes=1"],
                           cwd=RLV, env=env, capture_output=True, text=True, timeout=5400)
        say(r.stdout[-4000:]); say("STDERR:", r.stderr[-2500:]); say("SVEA exit:", r.returncode)
    except Exception as e:
        say("SVEA did not complete:", type(e).__name__, e)

    pathlib.Path("result.txt").write_text("\n".join(OUT))
    say("\n== DONE")



if __name__ == '__main__':
    main()
