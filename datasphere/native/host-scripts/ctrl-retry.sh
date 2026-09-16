#!/usr/bin/env bash
# Retry ctrl's attestation under the DATASPHERE profile.
#
# Under v100 ctrl is num_envs=64 and takes ~31 GB of the 32 GB card, so the yield watch's 4000 MiB
# free-memory floor fired on OUR OWN allocation: "free memory 1210 MiB is below the 4000 MiB floor,
# procs=1". That is the floor working -- a neighbour arriving then would have failed -- and it means
# ctrl at v100 is a whole-card job like ppg.
#
# v205 attested ctrl with NATIVE_HOST_PROFILE=datasphere explicitly. The profile does not change the
# evaluator revision (that is computed from families.json's bytes, not from the resolved profile),
# so attestation under datasphere is valid and does not take the whole card.
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v210
cd $HOME/rlvigen-work/repo
while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done
echo "=== $(date +%H:%M:%S) ctrl retry, datasphere profile ==="
env CARD=0 CELLS=ctrl:1 FRAMES=10000 TASK=Door SEED=1 \
  CELL_TIMEOUT_SECONDS=3600 NATIVE_HOST_PROFILE=datasphere NATIVE_VRAM_CAP_MIB=8192 \
  CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 SAVE_EVERY_FRAMES=10000 \
  ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy ENDPOINT_EVAL_SCENES=0 \
  ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
  RLVIGEN_ARCHIVE_HOST=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz \
  bash datasphere/native/launch-card-cell.sh ~/rlvigen-work/payload-v211-ctrl.tgz \
    $A/ctrl-retry-result.tgz > $A/ctrl-retry.log 2>&1
echo "=== $(date +%H:%M:%S) ctrl retry rc=$? ==="
grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|CELL_YIELDED|RECORDS_EMITTED [0-9]+)[^=]*" $A/ctrl-retry.log | tail -3
