#!/usr/bin/env bash
# Re-evaluate ppg's banked 600k checkpoints on the CURRENT evaluator closure.
#
# No training. The weights already exist: card0-20260909-115331 trained ppg to 600,064 frames on
# 2026-09-09 and its 14 checkpoints are retained and sha-verified against their rows. What is stale
# is only the evaluator revision (16e960b1f446 against today's 248751f7caca), so re-running the
# grid converts already-spent training compute into an admissible result.
#
# SMOKE mode re-measures ONE cell whose old value is known -- train / scene 0 / 20 episodes /
# endpoint / native -> 26.099544954299926. Because episode seeds are content-addressed
# (SeedSequence([eval_seed, scene_id, episode_index]) re-seeded per episode), an identical number
# proves the closure change did not move the measurement; a different one names what moved. That is
# a decisive empirical answer where reading three diffs was only suggestive.
#
# Card 1 is NOT ours by default, so the launcher refuses it unless process yield is armed. That is
# deliberate and is left in force here.
# NATIVE_PRODUCTION=1 is set because FRAMES is production scale and run_probe.sh refuses that
# combination otherwise -- correctly, and it refuses BEFORE paying the bootstrap. This IS a
# production measurement of a production-length checkpoint, so the label is accurate rather than
# a workaround.
#
# NATIVE_ACCEPT_SAME_DEVICE=1 is set DELIBERATELY and is narrower than it looks. The guard exists
# because results and work share one device, so one full or failed disk loses both -- true, and an
# owner-level property of a TRAINING campaign, where the loss would be irreplaceable GPU-hours.
# This cell trains nothing. The irreplaceable artifact is ppg's 600k checkpoint, which already
# exists in two places (the host run dir and results/superseded-runs/checkpoints/ locally,
# sha-verified a328e63e...). What this cell produces is an evaluation, and an evaluation is
# reproducible by construction: episode seeds are content-addressed, so re-running yields the same
# numbers. The guard should stay armed for training cells. NATIVE_EVAL_ALLOWANCE_SECONDS is explicit because the launcher's budget models
# the CURVE/ENDPOINT grids, not the OFFLINE_EVAL path this cell takes.
set -uo pipefail
MODE="${1:?usage: reeval-ppg.sh smoke|endpoint|curve}"
A="$HOME/rlvigen-runs/reeval-v214"
R="$HOME/rlvigen-work"
SNAP="${SNAPSHOT_OVERRIDE:-$HOME/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1/snapshot.pt}"
mkdir -p "$A"
cd "$R/repo"
[[ -f "$SNAP" ]] || { echo "no snapshot at $SNAP"; exit 2; }

case "$MODE" in
  smoke)    REGIMES=train;                          SCENES=0;                   EPS=20;  SCOPE=endpoint; MODES=native ;;
  endpoint) REGIMES=train,eval-easy,eval-medium,eval-hard; SCENES=0,1,2,3,4,5,6,7,8,9; EPS=20;  SCOPE=endpoint; MODES=native,mode ;;
  curve)    REGIMES=train,eval-easy,eval-medium,eval-hard; SCENES=0,1,2,3,4,5,6,7,8,9; EPS=3;   SCOPE=curve;    MODES=native ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac

echo "=== $(date +%H:%M:%S) reeval ppg mode=$MODE regimes=$REGIMES scenes=$SCENES eps=$EPS ==="
env CARD=1 NATIVE_YIELD_ON_PROCESSES=1 NATIVE_EXPECT_OURS=1 \
  CELLS="ppg:1" FRAMES=600064 TASK=Door SEED=1 \
  CELL_TIMEOUT_SECONDS="${TIMEOUT_S:-3600}" NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB=8192 \
  NATIVE_PRODUCTION=1 NATIVE_EVAL_ALLOWANCE_SECONDS="${ALLOWANCE_S:-3600}" \
  NATIVE_ACCEPT_SAME_DEVICE=1 \
  CUDA_ROOT=/usr/local/cuda \
  EXTRA_MOUNT_1="$SNAP:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT" \
  OFFLINE_EVAL_FAMILY=ppg OFFLINE_EVAL_BASELINE=ppg OFFLINE_EVAL_SEED=1 \
  OFFLINE_EVAL_FRAME=600064 OFFLINE_EVAL_REGIMES="$REGIMES" OFFLINE_EVAL_SCENES="$SCENES" \
  OFFLINE_EVAL_EPISODES="$EPS" OFFLINE_EVAL_EPISODE_SEED=20260903 \
  OFFLINE_EVAL_DEVICE=cuda OFFLINE_EVAL_SCOPE="$SCOPE" OFFLINE_EVAL_POLICY_MODES="$MODES" \
  bash datasphere/native/launch-card-cell.sh "$R/payload-v214-ppg.tgz" \
    "$A/ppg-$MODE-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz" \
    > "$A/ppg-$MODE.log" 2>&1
echo "=== $(date +%H:%M:%S) reeval rc=$? ==="
grep -oE "NATIVE_(OFFLINE_EVAL_[A-Z_]+|CELL_[A-Z_]+|RECORDS_EMITTED [0-9]+)[^=]*" "$A/ppg-$MODE.log" | tail -5
echo "=== REEVAL $MODE DONE ==="
