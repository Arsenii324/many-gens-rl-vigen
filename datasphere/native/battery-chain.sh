#!/usr/bin/env bash
# The production battery: 12 baselines x 3 seeds x 600k frames, CARD 0 ONLY, one cell at a time.
#
# Every cell goes through launch-card-cell.sh, so the exclusivity, yield and disk watches are armed
# and sized from the cell's own timeout. Card 1 is never touched: it is not ours.
#
# NATIVE_VRAM_CAP_MIB is set for the log record and is NOT protection -- notes/production-host/26:
# all nine family launchers overwrite PYTHONPATH, so the cap module never reaches a trainer. The
# protection is the yield watch's free-memory floor.
#
# ppg is a WHOLE-CARD job (26,653 MiB of 32,494 at its auxiliary phase). Nothing is packed here
# anyway -- one cell at a time -- but do not change that for ppg.
#
# RESUMABLE: a cell whose result archive already exists is skipped, so this can be re-run after an
# interruption without repeating finished work.
set -uo pipefail
A=$HOME/rlvigen-runs/battery-v1
R=$HOME/rlvigen-work
mkdir -p "$A"
cd $HOME/rlvigen-work/repo

FRAMES=600000
SEEDS="101 102 103"

# [Claude 2026-09-10] The asset archives are POSITIONAL all the way down --
# run_on_production_host.sh reads them as $3 and $4 -- so they are passed as arguments, not exported.
# Exporting RLVIGEN_ARCHIVE_HOST/PLACES365_ARCHIVE_HOST looks like it works and does nothing: that is
# what made the svea attestation refuse with NATIVE_PLACES365_MISSING.
# v212 = the frozen tree the attestation wave validates: jaxlib pinned, episode ids carrying scope
# and policy mode, the ibac_sni docstring corrected. A battery must run the payloads its attestation
# certified, or its records are on a closure nothing validated.
PAYLOAD_PREFIX="${PAYLOAD_PREFIX:-payload-v212}"
RLVIGEN_ARCHIVE="${RLVIGEN_ARCHIVE:-$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz}"
[[ -f "$RLVIGEN_ARCHIVE" ]] || { echo "no RL-ViGen archive at $RLVIGEN_ARCHIVE" >&2; exit 2; }
# Places365 is passed ONLY for the three baselines that enter its block. PLACES365_ARCHIVE must
# point at the FULL train corpus for production; the 1000-image attestation fixture certifies the
# code path, not the dataset.
PLACES365_ARCHIVE="${PLACES365_ARCHIVE:-}"

# family:baseline:vram_mib:cell_timeout_seconds -- timeouts from production-schedule-v100 training
# hours x 1.5, floored at 4h; the eval allowance is derived by launch-card-cell.sh on top of this.
CELLS="
idaac:idaac:4096:26000
ppg:ppg:30000:42000
ibac_sni:ibac_sni:4096:34000
ctrl:ctrl:16384:60000
alda:alda:8192:103000
rlvigen:drqv2:4096:35000
rlvigen:drq:4096:72000
rlvigen:curl:4096:69000
dmc_gb:rad:4096:147000
rlvigen:svea:6144:90000
rlvigen:sgqn:12288:139000
dmc_gb:soda:8192:277000
"

# ORDER MATTERS. The last three -- svea, sgqn, soda -- are the only baselines that enter the
# Places365 block, and the 26 GB train corpus is NOT on the host (only the 1000-image attestation
# fixture is). Everything above them is runnable today: 27 of the 36 cells. Ordering them last means
# the corpus acquisition blocks the tail of the campaign rather than its start.
[[ -n "${PLACES365_ARCHIVE_HOST:-}" ]] || echo "NOTE: PLACES365_ARCHIVE_HOST unset -- svea/sgqn/soda will refuse; the other nine run."

for entry in $CELLS; do
  fam="${entry%%:*}"; rest="${entry#*:}"
  base="${rest%%:*}"; rest="${rest#*:}"
  vram="${rest%%:*}"; timeout_s="${rest##*:}"
  for seed in $SEEDS; do
    tag="$base-s$seed"
    if [[ -f "$A/$tag-result.tgz" ]]; then
      echo "=== $(date +%H:%M:%S) SKIP $tag (result already present) ==="
      continue
    fi
    # Wait for card 0 to be free of OUR cells.
    while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done
    PLACES_ARG=""
    case "$base" in
      svea|sgqn|soda)
        if [[ -z "$PLACES365_ARCHIVE" || ! -f "$PLACES365_ARCHIVE" ]]; then
          echo "=== $(date +%H:%M:%S) SKIP $tag -- needs Places365 and PLACES365_ARCHIVE is unset ==="
          continue
        fi
        PLACES_ARG="$PLACES365_ARCHIVE" ;;
    esac
    echo "=== $(date +%H:%M:%S) START $tag  frames=$FRAMES timeout=${timeout_s}s ==="
    env CARD=0 CELLS="$base:$seed" FRAMES="$FRAMES" TASK=Door SEED="$seed" \
      NATIVE_PRODUCTION=1 CELL_TIMEOUT_SECONDS="$timeout_s" NATIVE_HOST_PROFILE=v100 \
      NATIVE_VRAM_CAP_MIB="$vram" CUDA_ROOT=/usr/local/cuda \
      CURVE_EVAL=1 ENDPOINT_EVAL=1 \
      bash datasphere/native/launch-card-cell.sh "$R/${PAYLOAD_PREFIX}-$fam.tgz" \
        "$A/$tag-result.tgz" "$RLVIGEN_ARCHIVE" $PLACES_ARG > "$A/$tag.log" 2>&1
    echo "=== $(date +%H:%M:%S) DONE $tag rc=$? ==="
    grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|RECORDS_EMITTED [0-9]+|ENDPOINT_SUPPLEMENTARY_INCOMPLETE)[^=]*" "$A/$tag.log" | tail -3
  done
done
echo "=== $(date +%H:%M:%S) BATTERY CHAIN DONE ==="
