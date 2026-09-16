#!/usr/bin/env bash
# Re-evaluate ANY banked checkpoint on the current evaluator closure. No training.
#
# [Claude 2026-09-15] Generalised from reeval-ppg.sh once the packing measurement came in: an eval
# cell uses ONE core (101% CPU), 841 MiB of VRAM and 2.1 GiB of RAM. The machine has 16 cores at
# load 7.4 and the card has ~16 GB free, so running these one at a time uses about a sixteenth of
# the node while the booking expires. They pack.
#
# [Claude 2026-09-16] NATIVE_PIP_CACHE_HOST, because bootstrap DOMINATES a short cell. Measured on
# idaac-s101-curve-100352: 257 pip lines against 25 evaluation lines, ~15-20 minutes of downloading
# before ~26 minutes of work. Across eleven stamps that is roughly three hours spent re-fetching
# the same wheels, and the nvidia ones are hundreds of MB each.
#
# The cache is mounted at /root/.cache/pip and must live under $HOME -- run_on_production_host.sh
# refuses anything else, which is the right refusal on a shared machine. It changes nothing about
# WHAT is installed: the requirements are still resolved and hashed per cell, so the executed
# environment is identical; only the download is skipped.
#
# [Claude 2026-09-16] NATIVE_NEED_MIB=1500, not the 4000 default, because 4000 is a TRAINING
# cell's requirement and this is an evaluation cell. Measured: an eval cell at num_envs=1 uses
# 841 MiB of VRAM, one core and 2.1 GiB of RAM. Demanding 4000 MiB made us refuse gaps that would
# comfortably hold two or three such cells -- on a booking this short that is the expensive kind of
# caution. 1500 leaves ~660 MiB of margin over the measured peak.
#
# It is lowered for EVAL only. A training cell keeps 4000: ibac_sni at procs=16 takes ~15 GiB and
# its headroom question is a different one.
#
# NATIVE_ALLOW_SHARED_CARD=1 is REQUIRED for a packed cell and is deliberate: --require-exclusive
# refuses any compute process on the card, and when we are packing, one of those processes is our
# own previous cell. The owner has confirmed the node is the group's for this booking. The disk and
# memory checks still run; only the exclusivity clause is relaxed.
set -uo pipefail
FAMILY="${FAMILY:?set FAMILY}"; BASELINE="${BASELINE:?set BASELINE}"; SEED="${SEED:?set SEED}"
FRAME="${FRAME:?set FRAME}"; SNAP="${SNAP:?set SNAP}"; MODE="${1:?usage: reeval-cell.sh endpoint|curve}"
TAG="${TAG:-$BASELINE-s$SEED-$MODE}"
A="$HOME/rlvigen-runs/reeval-v214"; R="$HOME/rlvigen-work"
mkdir -p "$A"; cd "$R/repo"
[[ -f "$SNAP" ]] || { echo "no snapshot at $SNAP"; exit 2; }

case "$MODE" in
  endpoint) REGIMES=train,eval-easy,eval-medium,eval-hard; SCENES=0,1,2,3,4,5,6,7,8,9; EPS=20; SCOPE=endpoint; MODES="${POLICY_MODES:-native,mode}" ;;
  curve)    REGIMES=train,eval-easy,eval-medium,eval-hard; SCENES=0,1,2,3,4,5,6,7,8,9; EPS=3;  SCOPE=curve;    MODES="${POLICY_MODES:-native}" ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac

echo "=== $(date +%H:%M:%S) reeval $TAG family=$FAMILY mode=$MODE ==="
env CARD="${CARD:-1}" NATIVE_YIELD_ON_PROCESSES=1 NATIVE_EXPECT_OURS="${EXPECT_OURS:-1}" \
  NATIVE_ALLOW_SHARED_CARD=1 \
  CELLS="$BASELINE:$SEED" FRAMES="$FRAME" TASK=Door SEED="$SEED" \
  CELL_TIMEOUT_SECONDS="${TIMEOUT_S:-3600}" NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB=8192 \
  NATIVE_PRODUCTION=1 NATIVE_EVAL_ALLOWANCE_SECONDS="${ALLOWANCE_S:-36000}" \
  NATIVE_ACCEPT_SAME_DEVICE=1 CUDA_ROOT=/usr/local/cuda \
  NATIVE_PIP_CACHE_HOST="${PIP_CACHE:-$HOME/.cache/rlvigen-pip}" \
  NATIVE_NEED_MIB="${NEED_MIB:-1500}" \
  EXTRA_MOUNT_1="$SNAP:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT" \
  OFFLINE_EVAL_FAMILY="$FAMILY" OFFLINE_EVAL_BASELINE="$BASELINE" OFFLINE_EVAL_SEED="$SEED" \
  OFFLINE_EVAL_FRAME="$FRAME" OFFLINE_EVAL_REGIMES="$REGIMES" OFFLINE_EVAL_SCENES="$SCENES" \
  OFFLINE_EVAL_EPISODES="$EPS" OFFLINE_EVAL_EPISODE_SEED=20260903 \
  OFFLINE_EVAL_DEVICE=cuda OFFLINE_EVAL_SCOPE="$SCOPE" OFFLINE_EVAL_POLICY_MODES="$MODES" \
  bash datasphere/native/launch-card-cell.sh "$R/payload-v214-$FAMILY.tgz" \
    "$A/$TAG-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz" \
    > "$A/$TAG.log" 2>&1
echo "=== $(date +%H:%M:%S) $TAG rc=$? ==="
grep -oE "NATIVE_(OFFLINE_EVAL_[A-Z_]+|CELL_[A-Z_]+)[^=]*|CELL EXIT=[0-9]+" "$A/$TAG.log" | tail -3
echo "=== REEVAL $TAG DONE ==="
