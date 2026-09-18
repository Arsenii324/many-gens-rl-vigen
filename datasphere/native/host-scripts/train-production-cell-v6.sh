#!/usr/bin/env bash
# One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve.
#
# v6 = v5 with exactly two knobs added, and nothing else changed. v5's body is reproduced verbatim
# apart from those two substitutions, because it is the script that ran every completed cell on this
# host and its defaults are the ones that worked.
#
#   PAYLOAD        path to the payload tgz. Default: the v5 path, $R/payload-v214-$FAMILY.tgz.
#                  v5 hardcoded that name, so a family whose payload was built later could not be
#                  launched without editing the script -- and naming a new build "v214" to fit the
#                  pattern would mislabel it.
#   PLACES365_DIR  host directory holding an EXTRACTED Places365 corpus. When set, it is passed as
#                  NATIVE_PLACES365_DIR_HOST, which mounts it read-only at /opt/places365 and makes
#                  run_probe.sh skip the copy and the extraction entirely. Required by svea, sgqn
#                  and soda; ignored by the other nine.
#
# Production with Places365 also needs NATIVE_PLACES365_SPLIT=train: run_probe.sh REFUSES a
# production-scale cell on the `val` split unless NATIVE_PLACES365_ACCEPT_VAL=1 states the
# deviation (A22). This script sets `train` by default for exactly that reason, and passing
# PLACES365_SPLIT=val is then a deliberate, recorded choice rather than a silence.
#
# The layout it expects, either of which run_probe.sh accepts:
#     $PLACES365_DIR/places365_standard/train/<365 class dirs>/     <- the easyformat shape
#     $PLACES365_DIR/train/<365 class dirs>/
#
# Everything about the yield, the floor, the timeout and the VRAM cap is v5's, including that
# NATIVE_VRAM_CAP_MIB does not bind a trainer (see OPERATOR-GUIDE §6b and production-host/26).
#
# To DRY-RUN the Places365 wiring, do not call this script with NATIVE_HOST_DRY_RUN: going through
# launch-card-cell.sh would arm three watch containers and a reaper for a cell that never starts.
# Call the wrapper directly instead, which runs every guard and prints the mounts without executing:
#
#   NATIVE_HOST_DRY_RUN=1 NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 FRAMES=600000 \
#     CELLS=svea:101 TASK=Door SEED=101 CELL_TIMEOUT_SECONDS=43200 NATIVE_VRAM_CAP_MIB=4096 \
#     NATIVE_ACCEPT_SAME_DEVICE=1 DOCKER_GPUS='"device=1"' NATIVE_RESULT_MIRROR=/tmp/mirror-dryrun \
#     NATIVE_PLACES365_DIR_HOST=$HOME/rlvigen-assets/places365-train NATIVE_PLACES365_SPLIT=train \
#     bash datasphere/native/run_on_production_host.sh $PAYLOAD /tmp/dryrun-result.tgz \
#       $HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz
set -uo pipefail
A="$HOME/rlvigen-runs/prod-v214"; R="$HOME/rlvigen-work"
mkdir -p "$A"; cd "$R/repo"
FAMILY="${FAMILY:-ibac_sni}"; BASELINE="${BASELINE:-ibac_sni}"; SEED="${SEED:-101}"
FRAMES="${FRAMES:-600000}"; TAG="$BASELINE-s$SEED-prod"
PAYLOAD="${PAYLOAD:-$R/payload-v214-$FAMILY.tgz}"
[[ -f "$A/$TAG-result.tgz" ]] && { echo "SKIP $TAG (result present)"; exit 0; }
[[ -f "$PAYLOAD" ]] || { echo "REFUSING: no payload at $PAYLOAD"; exit 2; }

places_env=()
if [[ -n "${PLACES365_DIR:-}" ]]; then
  [[ -d "$PLACES365_DIR" ]] || { echo "REFUSING: PLACES365_DIR=$PLACES365_DIR is not a directory"; exit 2; }
  places_env=(NATIVE_PLACES365_DIR_HOST="$PLACES365_DIR"
              NATIVE_PLACES365_SPLIT="${PLACES365_SPLIT:-train}")
  echo "=== places365: $PLACES365_DIR (split ${PLACES365_SPLIT:-train}) ==="
fi

echo "=== $(date +%H:%M:%S) START $TAG frames=$FRAMES card=${CARD:-0} yield_procs=${YIELD_PROCS:-0} ==="
echo "=== payload: $PAYLOAD ==="
env CARD="${CARD:-0}" NATIVE_YIELD_ON_PROCESSES="${YIELD_PROCS:-0}" NATIVE_EXPECT_OURS="${EXPECT_OURS:-8}" \
  NATIVE_ALLOW_SHARED_CARD=1 \
  CELLS="$BASELINE:$SEED" FRAMES="$FRAMES" TASK=Door SEED="$SEED" \
  CELL_TIMEOUT_SECONDS="${TIMEOUT_S:-43200}" NATIVE_HOST_PROFILE=v100 \
  NATIVE_VRAM_CAP_MIB="${VRAM_MIB:-4096}" NATIVE_PRODUCTION=1 NATIVE_ACCEPT_SAME_DEVICE=1 \
  CUDA_ROOT=/usr/local/cuda \
  ENDPOINT_EVAL=1 \
  ${places_env[@]+"${places_env[@]}"} \
  bash datasphere/native/launch-card-cell.sh "$PAYLOAD" \
    "$A/$TAG-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz" \
    > "$A/$TAG.log" 2>&1
echo "=== $(date +%H:%M:%S) $TAG rc=$? ==="
grep -oE "NATIVE_(CELL_[A-Z_]+|RECORDS_EMITTED [0-9]+|ENDPOINT[A-Z_]*)[^=]*|CELL EXIT=[0-9]+|places365:.*" "$A/$TAG.log" | tail -5
echo "=== PROD $TAG DONE ==="
