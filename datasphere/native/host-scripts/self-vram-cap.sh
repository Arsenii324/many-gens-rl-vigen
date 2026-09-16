#!/usr/bin/env bash
# Stop OUR OWN cell if its GPU memory would endanger a co-tenant. Never touches anyone else's.
#
# [Claude 2026-09-16] This fills the gap recorded in notes/model/STOP-MECHANISMS.md addendum 1:
# the 4000 MiB floor is a PREFLIGHT check, watch_gpu_headroom's watch() only records samples, and
# shared mode does not arm neighbour-yield -- so a cell can run for hours with nothing enforcing
# headroom. That is tolerable when we are sized well below the card. It is not tolerable here.
#
# The situation that produced it, and the measurement that settled it. ibac_sni runs procs=16 with
# MuJoCo/EGL rendering per worker. Its VRAM at that configuration had NEVER been measured: the
# "~15 GiB" figure in reeval-cell.sh was a comment cited back as fact by two agents, and the only
# real number was 2,199 MiB over 3 processes, which measured-vram-bounds.json's own rule forbids
# scaling. Both were wrong, in opposite directions.
#
# The true figure, measured 2026-09-16 from the card1-20260916-141636 archive:
# **22,675 MiB (22.14 GiB)** for our own processes. So ibac_sni needs ~22.1 GiB plus the 4000 MiB
# floor -- about 26.2 GiB free on a 32.5 GiB card. It cannot share a card with a co-tenant larger
# than ~6 GiB, which is why four attempts failed and why the fourth one's floor breach was correct.
#
# The floor already protects the CARD (yield_gpu_to_neighbour.py polls it for the life of the cell;
# see STOP-MECHANISMS addendum 1, including the retraction of my claim that it did not). What the
# floor does NOT do is bound OUR OWN footprint: it fires once free memory is already low, which on
# a shared card can mean our growth is what pushed a co-tenant toward the edge. This bounds us.
#
# So this watches OUR container's own summed compute-process memory and stops OUR container if it
# crosses CAP_MIB. It does not read, signal, or stop anything belonging to anyone else, and it does
# not yield our card to a neighbour who grows -- the booking is ours; the asymmetry is deliberate.
#
# It is LOUD. Every sample goes to the log, the trip is announced with the number that caused it,
# and the marker string is greppable, because a stop mechanism nobody can see fire is the defect
# this file exists to answer, not a feature.
set -uo pipefail
CELL="${1:?usage: self-vram-cap.sh <container> <card> <cap_mib> [log]}"
CARD="${2:?}"; CAP="${3:?}"; LOG="${4:-$HOME/rlvigen-runs/self-vram-cap-$CELL.log}"
INTERVAL="${INTERVAL:-20}"
say(){ echo "$(date -Is) $*" >> "$LOG"; }

say "START watching $CELL on card $CARD, cap ${CAP} MiB, interval ${INTERVAL}s"
peak=0
while true; do
  docker ps --format '{{.Names}}' | grep -qx "$CELL" || { say "STOP: $CELL is no longer running (peak ${peak} MiB). Exiting."; exit 0; }
  pids=$(docker top "$CELL" 2>/dev/null | awk 'NR>1{print $2}')
  [ -z "$pids" ] && { sleep "$INTERVAL"; continue; }
  ours=0
  while IFS=, read -r pid mem; do
    pid=$(echo "$pid" | tr -d ' '); mem=$(echo "$mem" | tr -d ' ')
    case "$mem" in ''|*[!0-9]*) continue;; esac
    for p in $pids; do [ "$p" = "$pid" ] && ours=$((ours+mem)); done
  done <<< "$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)"
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
  [ "$ours" -gt "$peak" ] && peak=$ours
  say "sample ours=${ours}MiB peak=${peak}MiB card_free=${free}MiB"
  if [ "$ours" -gt "$CAP" ]; then
    say "TRIPPED: our cell reached ${ours} MiB, above the ${CAP} MiB cap. Stopping OUR container"
    say "TRIPPED: only $CELL is stopped. No other container is touched."
    docker stop -t 30 "$CELL" >> "$LOG" 2>&1
    say "NATIVE_SELF_VRAM_CAP_TRIPPED ours=${ours} cap=${CAP} peak=${peak}"
    exit 3
  fi
  sleep "$INTERVAL"
done
