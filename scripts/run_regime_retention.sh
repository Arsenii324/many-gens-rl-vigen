#!/bin/bash
# Regime retention for drqv2/Door from existing checkpoints.
#
# The printed report of eval_across_scenes.py is SCENE retention (held-out scene vs scene 0,
# one regime). This driver produces the other axis: the same scenes evaluated under `train`
# and under `eval-easy`, so the denominator C43 says was never available becomes available.
# The two are different quantities and are not combined here -- only recorded side by side.
#
# CPU, not MPS: C20 measured drqv2 as non-reproducing on the MPS backend and reproducing on
# CPU. Running this on MPS would inject that nondeterminism into the exact comparison being
# measured.
set -u
cd "$(dirname "$0")/.."
PY=/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python
RUN="RL-ViGen-upstream/exp_local/2026.08.18/120404_action_repeat=1,env=robosuite,num_train_frames=120000,replay_buffer_num_workers=0,save_snapshot=True,save_video=False,task@_global_=Door,use_tb=False,use_wandb=False"
OUT=results/regime-retention

# The floor runs FIRST, and deliberately so. Retention divides by the train-regime score, and a
# smoke test put the uniform-random policy at 1.52 on Door/train against the 50k checkpoint's
# 2.02 -- indistinguishable. Without this reference the 50k row would have produced a confident
# retention ratio out of two chance-level numbers. Measured per regime, because there is no
# reason to assume chance performance is the same under both.
for MODE in train eval-easy; do
  TAG="random-floor__${MODE}"
  if [ -f "$OUT/$TAG.json" ]; then echo "SKIP $TAG (exists)"; continue; fi
  echo "=== $TAG  $(date +%H:%M:%S) ==="
  $PY scripts/eval_across_scenes.py --random-policy --mode "$MODE" \
    --scenes 0,1,2,3,4,5,6,7,8,9 --episodes 20 --seed 0 \
    --json "$OUT/$TAG.json" 2>&1 | grep -vE "UserWarning|warnings.warn|RuntimeWarning|ret = |Hydra|version_base|hydra.cc|with initialize"
  echo "--- exit ${PIPESTATUS[0]} for $TAG"
done

for CK in snapshot_50k_frames snapshot_100k_frames snapshot; do
  for MODE in train eval-easy; do
    TAG="${CK}__${MODE}"
    if [ -f "$OUT/$TAG.json" ]; then echo "SKIP $TAG (exists)"; continue; fi
    echo "=== $TAG  $(date +%H:%M:%S) ==="
    $PY scripts/eval_across_scenes.py \
      --snapshot "$RUN/$CK.pt" --mode "$MODE" \
      --scenes 0,1,2,3,4,5,6,7,8,9 --episodes 20 --seed 0 --control-seed 1 \
      --device cpu --json "$OUT/$TAG.json" 2>&1 | grep -vE "UserWarning|warnings.warn|RuntimeWarning|ret = "
    echo "--- exit ${PIPESTATUS[0]} for $TAG"
  done
done
echo "ALL DONE $(date +%H:%M:%S)"
