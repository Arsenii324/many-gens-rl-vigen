#!/usr/bin/env bash
# Retry the three families the first chain could not attest.
#   ctrl  -- yielded to itself at v100 (num_envs=64 takes ~31 GB of 32); retried at datasphere (16)
#   svea  -- refused: launch-card-cell.sh could not pass the Places365 archive (now fixed)
#   soda  -- same
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v210
R=$HOME/rlvigen-work
RLV=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz
P365=$HOME/rlvigen-assets/places365-train-attest.tgz
cd $HOME/rlvigen-work/repo

wait_card() { while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done; }

run_one() {
  local tag="$1" fam="$2" cells="$3" frames="$4" vram="$5" tmo="$6" profile="$7" places="$8"
  wait_card
  echo "=== $(date +%H:%M:%S) START $tag (profile=$profile) ==="
  env CARD=0 CELLS="$cells" FRAMES="$frames" TASK=Door SEED=1 \
    CELL_TIMEOUT_SECONDS="$tmo" NATIVE_HOST_PROFILE="$profile" NATIVE_VRAM_CAP_MIB="$vram" \
    CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 \
    SAVE_EVERY_FRAMES="$frames" ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy \
    ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
    NATIVE_PLACES365_SPLIT=train PLACES365_EXPECTED_COUNT=1000 RLVIGEN_PLACES_WORKERS=0 \
    bash datasphere/native/launch-card-cell.sh "$R/payload-v211-$fam.tgz" \
      "$A/$tag-result.tgz" "$RLV" $places > "$A/$tag.log" 2>&1
  echo "=== $(date +%H:%M:%S) $tag rc=$? ==="
  grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|CELL_YIELDED|RECORDS_EMITTED [0-9]+|PLACES365_[A-Z]+)[^=]*" "$A/$tag.log" | tail -3
}

run_one ctrl-retry    ctrl    "ctrl:1" 10000 8192 3600 datasphere ""
run_one svea-retry    rlvigen "svea:1" 10000 8192 6600 v100       "$P365"
run_one soda-retry    dmc_gb  "soda:1" 10000 8192 7800 v100       "$P365"
echo "=== $(date +%H:%M:%S) RETRY CHAIN DONE ==="
