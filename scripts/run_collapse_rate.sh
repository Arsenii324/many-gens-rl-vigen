#!/bin/bash
# C57 option 1: how often does drqv2/Door collapse?
#
# Seed 1 is already known -- it solved the task at 20k frames and was a constant sub-random
# policy by 40k. One run is an anecdote; this turns it into a rate. 40k frames is chosen
# because that is where seed 1 had already both solved AND lost the task, so it is the shortest
# budget that can observe the whole event.
#
# Two chains of two, rather than four at once: each run is ~1 core plus MPS, and four
# concurrent MPS contexts is untested here. Sequential within a chain keeps that honest.
set -u
cd "$(dirname "$0")/.."
CHAIN="$1"; shift
for SEED in "$@"; do
  echo "=== seed $SEED start $(date +%H:%M:%S) ==="
  bash runnable/_launch/rlvigen.sh drqv2 Door \
    num_train_frames=40000 seed="$SEED" save_snapshot=True 2>&1 \
    | grep -vE "UserWarning|warnings.warn|RuntimeWarning|cbd1|Hydra|hydra.cc|version_base|with initialize"
  echo "--- seed $SEED done $(date +%H:%M:%S) ==="
done
echo "CHAIN $CHAIN COMPLETE $(date +%H:%M:%S)"
