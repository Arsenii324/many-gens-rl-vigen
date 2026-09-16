#!/usr/bin/env bash
# svea and soda, third attempt. Attempt 2 got the Places365 archive through (the launcher fix works)
# and then died on `PLACES365_EXPECTED_SHA256: parameter null or not set` -- run_probe.sh reads it
# under set -u and the v205 configs set it alongside PLACES365_EXPECTED_COUNT. I passed only COUNT.
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v210
R=$HOME/rlvigen-work
RLV=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz
P365=$HOME/rlvigen-assets/places365-train-attest.tgz
cd $HOME/rlvigen-work/repo
run_one() {
  local tag="$1" fam="$2" cells="$3" tmo="$4"
  while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done
  echo "=== $(date +%H:%M:%S) START $tag ==="
  env CARD=0 CELLS="$cells" FRAMES=10000 TASK=Door SEED=1 \
    CELL_TIMEOUT_SECONDS="$tmo" NATIVE_HOST_PROFILE=v100 NATIVE_VRAM_CAP_MIB=8192 \
    CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 \
    SAVE_EVERY_FRAMES=10000 ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy \
    ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
    NATIVE_PLACES365_SPLIT=train PLACES365_EXPECTED_COUNT=1000 \
    PLACES365_EXPECTED_SHA256=c08327c5baf66746d2caf2f6f126c297fa421280d90a7d17eb903e7939dfed2e RLVIGEN_PLACES_WORKERS=0 \
    bash datasphere/native/launch-card-cell.sh "$R/payload-v211-$fam.tgz" \
      "$A/$tag-result.tgz" "$RLV" "$P365" > "$A/$tag.log" 2>&1
  echo "=== $(date +%H:%M:%S) $tag rc=$? ==="
  grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|RECORDS_EMITTED [0-9]+|PLACES365_[A-Z]+)[^=]*" "$A/$tag.log" | tail -3
}
run_one svea-r3 rlvigen "svea:1" 6600
run_one soda-r3 dmc_gb  "soda:1" 7800
echo "=== $(date +%H:%M:%S) R3 DONE ==="
