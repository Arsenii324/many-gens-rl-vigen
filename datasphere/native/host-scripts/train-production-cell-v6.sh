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
#
# [Claude 2026-09-20] REFUSES before launching anything if TIMEOUT_S is unset and BASELINE is not
# one of the three with a measured sub-12h V100 time (idaac, ppg, ibac_sni) -- the 12h default cut
# svea near 430k/600k frames on 2026-09-19 with no warning. See _scheduled_train_seconds() below.
set -uo pipefail
A="$HOME/rlvigen-runs/prod-v214"; R="$HOME/rlvigen-work"
mkdir -p "$A"; cd "$R/repo"
FAMILY="${FAMILY:-ibac_sni}"; BASELINE="${BASELINE:-ibac_sni}"; SEED="${SEED:-101}"
FRAMES="${FRAMES:-600000}"; TAG="$BASELINE-s$SEED-prod"
PAYLOAD="${PAYLOAD:-$R/payload-v214-$FAMILY.tgz}"
[[ -f "$A/$TAG-result.tgz" ]] && { echo "SKIP $TAG (result present)"; exit 0; }
[[ -f "$PAYLOAD" ]] || { echo "REFUSING: no payload at $PAYLOAD"; exit 2; }

# Training-timeout floor (2026-09-20). TIMEOUT_S below defaults CELL_TIMEOUT_SECONDS to 43200 (12h),
# and seven of the twelve baselines are scheduled to train longer than that on the DataSphere T4
# tier (production-schedule.json's solo_hours_per_seed_gt4_1) -- V100 throughput is UNMEASURED for
# all of them, so a T4-tier hour is the best number available, not a promise. svea launched
# 2026-09-19 with the 12h default and would have been cut near 430k/600k frames with no warning.
# Only idaac, ppg and ibac_sni have a MEASURED sub-12h V100 training time (OPERATOR-GUIDE.md
# §4c.1); every other baseline -- known to this table or not -- must pass TIMEOUT_S explicitly.
#
# Kept in sync with production-schedule.json by tests/test_train_production_cell_timeout.py, which
# fails if this table drifts from the JSON -- the host shell has no python and cannot read it.
_scheduled_train_seconds() {
  case "$1" in
    drqv2)    echo 23040 ;;   # 6.40 h
    svea)     echo 60048 ;;   # 16.68 h
    drq)      echo 48060 ;;   # 13.35 h
    sgqn)     echo 92304 ;;   # 25.64 h
    curl)     echo 45756 ;;   # 12.71 h
    rad)      echo 97704 ;;   # 27.14 h
    soda)     echo 184608 ;;  # 51.28 h
    alda)     echo 68580 ;;   # 19.05 h
    idaac)    echo 17244 ;;   # 4.79 h
    ppg)      echo 28152 ;;   # 7.82 h
    ibac_sni) echo 22536 ;;   # 6.26 h
    ctrl)     echo 40212 ;;   # 11.17 h
    *)        return 1 ;;
  esac
}
if [[ -z "${TIMEOUT_S:-}" ]]; then
  case "$BASELINE" in
    idaac|ppg|ibac_sni) : ;;   # measured sub-12h on THIS host; the 43200s default is safe as-is
    *)
      if _sched=$(_scheduled_train_seconds "$BASELINE"); then
        echo "REFUSING: $BASELINE has no measured sub-12h V100 training time and TIMEOUT_S is unset." >&2
        echo "  The 12h default (CELL_TIMEOUT_SECONDS=43200) would cut it before it finishes:" >&2
        echo "  scheduled training is $(( _sched / 3600 ))h $(( (_sched % 3600) / 60 ))m on the" >&2
        echo "  DataSphere T4 tier (production-schedule.json); V100 is unmeasured for it. Pass" >&2
        echo "  TIMEOUT_S explicitly (seconds) once you know how long this baseline actually needs." >&2
      else
        echo "REFUSING: $BASELINE is not in the scheduled-training-time table and TIMEOUT_S is" >&2
        echo "  unset -- the 12h default is unverified for it. Pass TIMEOUT_S explicitly." >&2
      fi
      exit 2
      ;;
  esac
elif _sched=$(_scheduled_train_seconds "$BASELINE") && [[ "$TIMEOUT_S" -lt "$_sched" ]]; then
  echo "WARNING: TIMEOUT_S=$TIMEOUT_S is below $BASELINE's scheduled training time" >&2
  echo "  ($(( _sched / 3600 ))h $(( (_sched % 3600) / 60 ))m = ${_sched}s on the DataSphere T4" >&2
  echo "  tier; V100 is unmeasured for it). Continuing on the operator's word." >&2
fi

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
