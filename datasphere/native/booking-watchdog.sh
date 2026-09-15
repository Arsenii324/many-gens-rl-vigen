#!/usr/bin/env bash
# Say something when the shared node changes in a way that should change what we do.
#
# [Claude 2026-09-15] The booking is the group's until 2026-09-16 23:59 MSK and the expiry is SOFT:
# it may slip a few hours, or end early if the next booker arrives. So the thing to watch is not a
# clock but WHO IS ON THE CARDS. This records every distinct container that holds a GPU and flags a
# name it has never seen before -- that is the signal that somebody outside the group has entered
# and that our packing should stop being aggressive.
#
# It also watches the two failure modes that would silently end a run:
#   - free disk approaching a cell's own disk-watch floor. A breach writes a yield sentinel, and a
#     TRAINING cell polls that sentinel and stops. Our footprint is small; the filesystem is shared,
#     so this can happen entirely because of someone else.
#   - our own cell count dropping without a completion marker.
#
# It reports. It never stops anything and never touches another user's container.
set -uo pipefail
OUT="$HOME/rlvigen-runs/booking-watchdog.log"
KNOWN="$HOME/rlvigen-runs/.known-gpu-holders"
DISK_WARN_GIB="${DISK_WARN_GIB:-125}"
INTERVAL="${WATCHDOG_INTERVAL:-300}"
touch "$KNOWN"
say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$OUT"; }
say "watchdog started (disk warn <${DISK_WARN_GIB}GiB, interval ${INTERVAL}s)"
last_ours=-1

while :; do
  holders=""
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    cg=$(grep -oE 'docker[-/][0-9a-f]{12}' "/proc/$p/cgroup" 2>/dev/null | head -1 | grep -oE '[0-9a-f]{12}')
    [[ -z "$cg" ]] && continue
    nm=$(docker ps --format '{{.ID}} {{.Names}}' 2>/dev/null | awk -v c="$cg" '$1==substr(c,1,12){print $2}')
    [[ -n "$nm" ]] && holders="$holders$nm"$'\n'
  done
  while read -r nm; do
    [[ -z "$nm" ]] && continue
    case "$nm" in cell-c0-*|cell-c1-*) continue ;; esac      # ours, named by our own launcher
    if ! grep -qxF "$nm" "$KNOWN"; then
      echo "$nm" >> "$KNOWN"
      say "NEW GPU HOLDER: '$nm' -- not seen before. If this is outside the group, stop packing and"
      say "                reduce to one cell; the booking may have passed to someone else."
    fi
  done <<< "$holders"

  free_gib=$(df -Pk "$HOME" | awk 'NR==2{printf "%d", $4/1048576}')
  (( free_gib < DISK_WARN_GIB )) && say "DISK WARNING: ${free_gib} GiB free. A cell's disk watch fires near its own floor and a TRAINING cell stops on the sentinel."

  ours=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cE '^cell-c[01]-[0-9]+$')
  if (( last_ours >= 0 )) && (( ours < last_ours )); then
    say "our cell count fell ${last_ours} -> ${ours} (expected when one completes; check for a completion marker if not)"
  fi
  last_ours=$ours
  sleep "$INTERVAL"
done
