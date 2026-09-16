#!/usr/bin/env bash
# ctrl only, against the tree that pins nvidia-cudnn-cu12==9.5.1.17.
#
# ctrl is the last family short of 7/7. Its v212 cell died at the import gate on a jaxlib pin
# (since reverted); its earlier cells died in cuDNN because an unpinned nvidia-* stack resolved to
# a cuDNN with no Volta kernels. Both are fixed in this payload. Measured on this card:
# cudnn 9.26.0.51 FAILS, 9.5.1.17 and 9.1.0.70 run the conv correctly.
#
# DATASPHERE profile, exactly as v212: at v100 ctrl is num_envs=64 and takes ~31 GB of a 32 GB
# card, which trips its own 4000 MiB free-memory floor.
# Card 0 only. Card 1 is never touched: it is not ours to take.
set -uo pipefail
A=$HOME/rlvigen-runs/attest-v213
R=$HOME/rlvigen-work
RLV=$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz
mkdir -p "$A"
cd $HOME/rlvigen-work/repo

if [[ -f "$A/ctrl-result.tgz" ]]; then echo "=== SKIP ctrl (result present) ==="; exit 0; fi
while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do sleep 60; done
echo "=== $(date +%H:%M:%S) START ctrl (ctrl:1, 10000 frames, profile=datasphere) ==="
env CARD=0 CELLS="ctrl:1" FRAMES=10000 TASK=Door SEED=1 \
  CELL_TIMEOUT_SECONDS=3600 NATIVE_HOST_PROFILE=datasphere NATIVE_VRAM_CAP_MIB=8192 \
  CUDA_ROOT=/usr/local/cuda EVAL_EVERY_FRAMES=2147483647 EVAL_EPISODES=1 \
  SAVE_EVERY_FRAMES=10000 ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy \
  ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5 ENDPOINT_EVAL_DEVICE=cuda \
  bash datasphere/native/launch-card-cell.sh "$R/payload-v213-ctrl.tgz" \
    "$A/ctrl-result.tgz" "$RLV" > "$A/ctrl.log" 2>&1
echo "=== $(date +%H:%M:%S) ctrl rc=$? ==="
grep -oE "NATIVE_(CELL_COMPLETED|CELL_FAILED|CELL_YIELDED|RECORDS_EMITTED [0-9]+)[^=]*" "$A/ctrl.log" | tail -3
grep -oE "nvidia-cudnn-cu12==[0-9.]+|cudnn status: [0-9]+" "$A/ctrl.log" | sort -u | head -3
echo "=== V213 DONE ==="
