#!/usr/bin/env bash
# Run the remaining attestation cells on CARD 0, one at a time, each through launch-card-cell.sh
# so the exclusivity, yield and disk watches are armed for every one of them.
# Card 1 is deliberately never touched: it is not ours to take.
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v210
R=$HOME/rlvigen-work
cd $HOME/rlvigen-work/repo

run_one() {
  local fam="$1" cells="$2" frames="$3" vram="$4" timeout_s="$5" places="$6"
  echo "=== $(date +%H:%M:%S) starting $fam ($cells, $frames frames) ==="
  # Wait for card 0 to be free of OUR cells before starting the next one.
  local waited=0
  while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do
    sleep 30; waited=$((waited+30))
    if [[ $waited -gt 21600 ]]; then echo "  giving up waiting for card 0 after 6h"; return 1; fi
  done
  local extra=()
  [[ -n "$places" ]] && extra=(PLACES365_ARCHIVE_HOST="$places" NATIVE_PLACES365_SPLIT=train
                               PLACES365_EXPECTED_COUNT=1000 RLVIGEN_PLACES_WORKERS=0)
  env CARD=0 CELLS="$cells" FRAMES="$frames" TASK=Door SEED=1 \
    CELL_TIMEOUT_SECONDS="$timeout_s" NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB="$vram" \
    CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 \
    SAVE_EVERY_FRAMES="$frames" ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy \
    ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
    RLVIGEN_ARCHIVE_HOST=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz \
    NATIVE_OUT_HOST_DIR=$A/$fam-out NATIVE_WORK_HOST_DIR=$A/$fam-work \
    ${extra[@]+"${extra[@]}"} \
    bash datasphere/native/launch-card-cell.sh "$R/payload-v211-$fam.tgz" \
      "$A/$fam-result.tgz" > "$A/$fam.log" 2>&1
  echo "=== $(date +%H:%M:%S) $fam finished rc=$? ==="
  grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|RECORDS_EMITTED [0-9]+)[^=]*" "$A/$fam.log" | tail -3
}

PLACES=$HOME/rlvigen-assets/places365-train-attest.tgz
run_one ibac_sni "ibac_sni:1" 10112 4096 3600 ""
run_one ctrl     "ctrl:1"     10000 8192 3600 ""
run_one rlvigen  "svea:1"     10000 8192 6600 "$PLACES"
run_one dmc_gb   "soda:1"     10000 8192 7800 "$PLACES"
echo "=== $(date +%H:%M:%S) CHAIN DONE ==="
