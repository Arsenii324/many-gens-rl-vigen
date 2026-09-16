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
# I then produced a THIRD wrong number and must record it here, because this file was written on
# the strength of it. I reported 22,675 MiB "measured". It was the sum of every compute process on
# a SHARED card: 21,300 MiB of it belonged to a colleague (two processes at 10,650). The instrument
# summed all compute processes while claiming in its own docstring to filter to our process tree.
#
# So all three figures were wrong: ~15 GiB (never measured), 2,199 MiB (3-process cell, and it
# UNDER-counts because EGL render contexts are not compute apps -- that cell's card delta is
# 6,804 MiB), and 22,675 MiB (a colleague's memory). The honest state is that ibac_sni at procs=16
# is UNMEASURED, with a lower bound of ~6.6 GiB from the card delta at the moment the floor stood
# it down 42.4 s in, while its process count was still climbing 2 -> 20.
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
