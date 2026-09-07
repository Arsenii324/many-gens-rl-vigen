#!/usr/bin/env bash
# One install for every baseline in this repo.
#
#   bash setup/install.sh              # into ./.venv
#   VENV=/path/to/venv bash setup/install.sh
#
# Ends by VERIFYING, not by claiming: it builds a real environment in every mode and fails if any
# of them does not report the mode it was asked for.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
VENV="${VENV:-$REPO/.venv}"

say() { printf '\n=== %s ===\n' "$1"; }

# [Claude 2026-09-07, external review 24] Source acquisition lives in ONE place. This script used
# to clone RL-ViGen itself, pinning the commit in a second location and knowing nothing about the
# other six families or the OpenAI Baselines auxiliary tree -- so a new user had two different
# answers to "how do I get the source?". setup/bootstrap_sources.py is the authority now; this
# script builds the ENVIRONMENT and verifies it.
say "1/6  pinned sources"
if [[ ! -d RL-ViGen-upstream ]]; then
  echo "RL-ViGen-upstream is absent. Reconstruct the pinned sources first:"
  echo "    python3 setup/bootstrap_sources.py"
  echo "    python3 setup/verify_sources.py"
  echo "(RL-ViGen needs a case-sensitive filesystem; see docs/RUN-THIS-PROJECT.md.)"
  exit 2
fi
python3 setup/verify_sources.py --family rlvigen || {
  echo "the reconstructed RL-ViGen tree does not match its manifest; refusing to build on it" >&2
  exit 2
}

say "2/6  virtualenv"
if [[ ! -x "$VENV/bin/python" ]]; then python3 -m venv "$VENV"; fi
PY="$VENV/bin/python"
"$PY" -m pip install -q --upgrade pip

say "3/6  pinned dependencies"
"$PY" -m pip install -q -r requirements.txt

say "4/6  robosuite (RL-ViGen's vendored fork, EDITABLE)"
# Editable is not a preference. A wheel build of this tree drops models/assets/ because setup.py
# declares no package_data, and every texture lookup then fails at eval time.
# A leftover build/ from an earlier attempt makes setuptools fail with
# "[Errno 66] Directory not empty", so clear it first.
rm -rf ./RL-ViGen-upstream/third_party/robosuite/build \
       ./RL-ViGen-upstream/third_party/robosuite/*.egg-info
"$PY" -m pip install -q --no-deps -e ./RL-ViGen-upstream/third_party/robosuite

say "5/6  patch upstream (idempotent; bootstrap_sources.py already applied these)"
"$PY" setup/apply_patches.py

say "6/6  VERIFY"
"$PY" setup/apply_patches.py --check
"$PY" setup/install_assets.py --check
"$PY" - <<'PYEOF'
import os, sys, platform
os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
sys.path.insert(0, os.getcwd())
from rlgen.envs import EnvSpec, make_env
import numpy as np
bad = 0
for task in ("Door", "Lift"):
    for mode in ("train", "eval-easy", "eval-hard"):
        try:
            e = make_env(EnvSpec(task=task, mode=mode, scene_id=0, seed=0))
            o = e.reset()
            e.step(np.zeros(e.act_dim, dtype=np.float32))
            print(f"  OK   {task:5s} {mode:10s} obs{o.shape} {o.dtype} act({e.act_dim},)")
            e.close()
        except Exception as ex:
            bad += 1
            print(f"  FAIL {task:5s} {mode:10s} {type(ex).__name__}: {ex}")
print()
if bad:
    print(f"{bad} environment(s) failed to build. Do not trust any number from this install.")
    sys.exit(1)
print("all six task x mode environments build and step, and each reports the mode requested.")
PYEOF

say "done"
echo "Activate with:  source $VENV/bin/activate"
echo "Then:           bash baselines/drqv2/train.sh Door 0 --smoke"
