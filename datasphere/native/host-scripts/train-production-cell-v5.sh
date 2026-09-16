#!/usr/bin/env bash
# One PRODUCTION training cell to 600k, with the endpoint grid and WITHOUT the in-cell curve.
#
# [Claude 2026-09-16] v5 differs from v4 in exactly one respect, and the reason is specific.
#
# v4 hardcoded NATIVE_YIELD_ON_PROCESSES=1 inside its `env` line, so it could not be overridden
# from the environment. On card 1 that is correct: launch-card-cell.sh:269 REFUSES a non-zero card
# without it, because a card that is not ours is not ours to take. On card 0 it is actively wrong
# when the card is shared. launch-card-cell.sh:289 arms process yield on card 0 "by request", and
# watch_card_exclusivity then compares the card's compute-process count against --expect-ours. Two
# foreign processes are resident on card 0 right now (18,487 MiB between them), so an 8-process
# cell would be measured against a card showing ten, and the yield would fire -- at preflight, or
# hours in, silently, after the training it was protecting had already been paid for.
#
# So CARD and the yield are both parameters here, and the DEFAULT is card 0 with process yield OFF,
# paired with NATIVE_ALLOW_SHARED_CARD=1. That combination says what is actually true: this card is
# ours by booking, co-tenants are present, we do not surrender to them, and we do not pretend the
# card is exclusive either. The 4000 MiB free-memory floor is NOT waived by any of it.
#
# [Claude 2026-09-16] RETRACTED, and the retraction is the useful part. This header used to read:
# "the floor is a PREFLIGHT check ... between launch and finish, nothing on the host enforces
# headroom." That is wrong, and it is wrong in a way worth naming, because TWO different mechanisms
# are called "yield" here and I collapsed them into one:
#
#   STEP 2, yield_gpu_to_neighbour.py (launch-card-cell.sh:294) -- armed UNCONDITIONALLY, in a
#     container, for the life of the cell. It re-checks --floor-mib 4000 every 20 seconds and
#     writes /work/yield.sentinel when free memory drops below it. This one enforces the floor.
#   STEP 2b, the host-side PID neighbour yield (launch-card-cell.sh:318) -- NOT armed when
#     NATIVE_ALLOW_SHARED_CARD=1, deliberately, because it stops on a co-tenant's PRESENCE and
#     presence is what shared mode agrees to.
#
# Only 2b is skipped in shared mode. The floor stays armed in both modes, which is what
# launch-card-cell.sh:320 says in so many words: "The memory floor and disk watch remain armed."
#
# What misled me was reading watch_gpu_headroom.watch(), which really does only RECORD samples, and
# concluding from that recorder that nothing enforced. The enforcer is a different file. It was
# demonstrated an hour after I wrote the retracted claim, by a cell standing itself down with
# "yielded at ...: free memory 3063 MiB is below the 4000 MiB floor".
#
# The operational consequence is the opposite of what the old text implied: a co-tenant arriving
# mid-run does NOT go unnoticed, and a cell CAN stop itself hours in. Size the run accordingly.
#
# Sizing, from our own archives rather than an estimate: scripts/measure_vram_bounds.py over the
# returned card0-* cells puts ibac_sni at 2,199 MiB across 3 compute processes. Production runs 8,
# so a linear scale is ~5.9 GiB -- and measured-vram-bounds.json's own rule forbids treating a
# scaled peak as a bound. It is a planning figure. Card 0 had 12,354 MiB free at launch.
#
# Seed 101, not 1. production-schedule-v100.json names seeds [101,102,103]; idaac is banked at 101
# and ppg at 1. Using 101 here keeps ppg as the single off-schedule seed instead of making it two.
set -uo pipefail
A="$HOME/rlvigen-runs/prod-v214"; R="$HOME/rlvigen-work"
mkdir -p "$A"; cd "$R/repo"
FAMILY="${FAMILY:-ibac_sni}"; BASELINE="${BASELINE:-ibac_sni}"; SEED="${SEED:-101}"
FRAMES="${FRAMES:-600000}"; TAG="$BASELINE-s$SEED-prod"
[[ -f "$A/$TAG-result.tgz" ]] && { echo "SKIP $TAG (result present)"; exit 0; }

echo "=== $(date +%H:%M:%S) START $TAG frames=$FRAMES card=${CARD:-0} yield_procs=${YIELD_PROCS:-0} ==="
env CARD="${CARD:-0}" NATIVE_YIELD_ON_PROCESSES="${YIELD_PROCS:-0}" NATIVE_EXPECT_OURS="${EXPECT_OURS:-8}" \
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
