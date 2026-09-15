#!/usr/bin/env bash
# One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve.
#
# [Claude 2026-09-15] The booking ends 2026-09-16 23:59 MSK. A full production cell is train plus
# curve plus endpoint: for ibac_sni that is ~6.3 h + ~5.7 h + ~11.7 h = most of the window for one
# baseline, with no slack for anything going wrong.
#
# CURVE_EVAL=0 is therefore deliberate and is NOT a quality cut. The curve is the descriptive half
# (endpoint-as-headline is the standing default), the checkpoints are retained either way, and this
# session has now demonstrated that a curve can be rebuilt afterwards from retained stamps at
# 3 episodes per cell -- so the only thing skipped is work that can be redone later from artifacts
# we keep. The endpoint, which carries the reported number, is NOT skipped.
#
# Chosen baseline: ibac_sni. ppg and idaac are already banked at 600k and are both on-policy PPO
# variants, so a third on-policy baseline turns two isolated numbers into THREE primary pairs
# (idaac-ibac_sni, idaac-ppg, ibac_sni-ppg) under comparison_blocks' blocking axes. That is the
# largest scientific gain available per GPU-hour in this window.
#
# procs=16 is the v100 profile and is the UPSTREAM count -- "Use the upstream IBAC-SNI process
# count after the Door-specific spawn/factory repair". Running it at the DataSphere profile would
# be the deviation, not the economy.
set -uo pipefail
A="$HOME/rlvigen-runs/prod-v214"; R="$HOME/rlvigen-work"
mkdir -p "$A"; cd "$R/repo"
FAMILY="${FAMILY:-ibac_sni}"; BASELINE="${BASELINE:-ibac_sni}"; SEED="${SEED:-1}"
FRAMES="${FRAMES:-600000}"; TAG="$BASELINE-s$SEED-prod"
[[ -f "$A/$TAG-result.tgz" ]] && { echo "SKIP $TAG (result present)"; exit 0; }

echo "=== $(date +%H:%M:%S) START $TAG frames=$FRAMES (train + endpoint, no in-cell curve) ==="
env CARD="${CARD:-1}" NATIVE_YIELD_ON_PROCESSES=1 NATIVE_EXPECT_OURS="${EXPECT_OURS:-8}" \
  NATIVE_ALLOW_SHARED_CARD=1 \
  CELLS="$BASELINE:$SEED" FRAMES="$FRAMES" TASK=Door SEED="$SEED" \
  CELL_TIMEOUT_SECONDS="${TIMEOUT_S:-43200}" NATIVE_HOST_PROFILE=v100 \
  NATIVE_VRAM_CAP_MIB="${VRAM_MIB:-4096}" NATIVE_PRODUCTION=1 NATIVE_ACCEPT_SAME_DEVICE=1 \
  CUDA_ROOT=/usr/local/cuda \
  CURVE_EVAL=0 ENDPOINT_EVAL=1 \
  bash datasphere/native/launch-card-cell.sh "$R/payload-v214-$FAMILY.tgz" \
    "$A/$TAG-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz" \
    > "$A/$TAG.log" 2>&1
echo "=== $(date +%H:%M:%S) $TAG rc=$? ==="
grep -oE "NATIVE_(CELL_[A-Z_]+|RECORDS_EMITTED [0-9]+|ENDPOINT[A-Z_]*)[^=]*|CELL EXIT=[0-9]+" "$A/$TAG.log" | tail -4
echo "=== PROD $TAG DONE ==="
