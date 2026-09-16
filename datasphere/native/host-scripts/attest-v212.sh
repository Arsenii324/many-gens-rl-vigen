#!/usr/bin/env bash
# ATTESTATION WAVE v212 -- all seven evaluator families against the frozen tree.
#
# Runs AFTER the bump (jaxlib pin, episode ids carrying scope+policy_mode, the ibac_sni docstring),
# so this is the "accumulate fixes, validate once" wave Q47 prescribes rather than the second of two.
#
# Card 0 only, one cell at a time, every cell through launch-card-cell.sh so the exclusivity, yield
# and disk watches are armed and sized. ctrl runs at the DATASPHERE profile: at v100 it is
# num_envs=64 and takes ~31 GB of a 32 GB card, which trips its own 4000 MiB free-memory floor.
# Both asset archives are passed POSITIONALLY -- exporting them does nothing.
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v212
R=$HOME/rlvigen-work
RLV=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz
P365=$HOME/rlvigen-assets/places365-train-attest.tgz
mkdir -p "$A"
cd $HOME/rlvigen-work/repo

run_one() {
  local fam="$1" cells="$2" frames="$3" tmo="$4" profile="$5" places="$6"
  if [[ -f "$A/$fam-result.tgz" ]]; then echo "=== SKIP $fam (result present) ==="; return 0; fi
  while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done
  echo "=== $(date +%H:%M:%S) START $fam ($cells, $frames frames, profile=$profile) ==="
  env CARD=0 CELLS="$cells" FRAMES="$frames" TASK=Door SEED=1 \
    CELL_TIMEOUT_SECONDS="$tmo" NATIVE_HOST_PROFILE="$profile" NATIVE_VRAM_CAP_MIB=8192 \
    CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 \
    SAVE_EVERY_FRAMES="$frames" ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy \
    ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
    NATIVE_PLACES365_SPLIT=train PLACES365_EXPECTED_COUNT=1000 \
    PLACES365_EXPECTED_SHA256=c08327c5baf66746d2caf2f6f126c297fa421280d90a7d17eb903e7939dfed2e RLVIGEN_PLACES_WORKERS=0 \
    bash datasphere/native/launch-card-cell.sh "$R/payload-v212-$fam.tgz" \
      "$A/$fam-result.tgz" "$RLV" $places > "$A/$fam.log" 2>&1
  echo "=== $(date +%H:%M:%S) $fam rc=$? ==="
  grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|CELL_YIELDED|RECORDS_EMITTED [0-9]+)[^=]*" "$A/$fam.log" | tail -2
}

run_one idaac    "idaac:1"    8192  3600 v100       ""
run_one ppg      "ppg:1"     10240  3600 v100       ""
run_one alda     "alda:1"    10000  3600 v100       ""
run_one ibac_sni "ibac_sni:1" 10112 3600 v100       ""
run_one ctrl     "ctrl:1"    10000  3600 datasphere ""
run_one rlvigen  "svea:1"    10000  6600 v100       "$P365"
run_one dmc_gb   "soda:1"    10000  7800 v100       "$P365"
echo "=== $(date +%H:%M:%S) V212 WAVE DONE ==="
