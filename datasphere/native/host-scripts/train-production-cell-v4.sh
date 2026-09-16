#!/usr/bin/env bash
# One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve.
#
# [Claude 2026-09-15] The booking ends 2026-09-16 23:59 MSK. A full production cell is train plus
# curve plus endpoint: for ibac_sni that is ~6.3 h + ~5.7 h + ~11.7 h = most of the window for one
# baseline, with no slack for anything going wrong.
#
# [Claude 2026-09-16] CURVE_EVAL=0 was REMOVED. run_probe refuses it at production scale --
# "NATIVE_PRODUCTION_CONFLICT CURVE_EVAL=0 expected=1 ... production settings are frozen at scale"
# -- and the refusal is right: trimming the protocol produces a cell that is not a production cell
# whatever its frame count says. The full protocol is ~23.7 h (6.3 train + 5.7 curve + 11.7
# endpoint) and the booking's SOFT end is ~17 Sep 09:00, giving 32.2 h. It fits with slack.
#
# And a run cut short is not a loss of everything. Intermediate checkpoints are written every
# save_every frames and each one is EVALUABLE afterwards by exactly the sweep used for ppg and
# idaac, so a cell that reaches 400k yields a gradeable 400k measurement. What is NOT available is
# RESUMING: families.json:160 records that keys_to_save omits the replay buffer, so an off-policy
# run restarted from a snapshot is a different experiment. ibac_sni is on-policy, but the run is
# sized to finish rather than to be resumed.
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
  ENDPOINT_EVAL=1 \
  bash datasphere/native/launch-card-cell.sh "$R/payload-v214-$FAMILY.tgz" \
    "$A/$TAG-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz" \
    > "$A/$TAG.log" 2>&1
echo "=== $(date +%H:%M:%S) $TAG rc=$? ==="
grep -oE "NATIVE_(CELL_[A-Z_]+|RECORDS_EMITTED [0-9]+|ENDPOINT[A-Z_]*)[^=]*|CELL EXIT=[0-9]+" "$A/$TAG.log" | tail -4
echo "=== PROD $TAG DONE ==="
