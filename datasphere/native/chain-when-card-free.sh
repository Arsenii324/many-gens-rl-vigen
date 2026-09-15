#!/usr/bin/env bash
# Run queued cells back to back, waiting only for OUR OWN previous cell to finish.
#
# [Claude 2026-09-15] The booking ends 2026-09-16 23:59 MSK. A card that sits idle between two of
# our own jobs is the cheapest waste available, and the gap is exactly as long as it takes a human
# to notice. This closes that gap and nothing else.
#
# It waits for our container to be GONE, not for a card to be empty: the node is the group's, a
# colleague may legitimately share it, and forcing exclusivity between our own queued jobs would
# stall the queue for no benefit. The pre-launch occupancy and disk checks inside
# launch-card-cell.sh still run for every job in the queue -- this schedules, it does not bypass.
set -uo pipefail
QUEUE=("$@")
[[ ${#QUEUE[@]} -gt 0 ]] || { echo "usage: chain-when-card-free.sh <mode> [mode...]"; exit 2; }
LOG="$HOME/rlvigen-runs/chain.log"
say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
say "chain started with: ${QUEUE[*]}"

for mode in "${QUEUE[@]}"; do
  waited=0
  while [[ -n "$(docker ps -q --filter 'name=cell-c1-' 2>/dev/null)" ]]; do
    sleep 60; waited=$((waited+60))
    if (( waited > 43200 )); then say "gave up waiting 12h for our own cell to finish"; exit 1; fi
  done
  say "previous cell finished; launching mode=$mode"
  TIMEOUT_S="${TIMEOUT_S:-3600}" ALLOWANCE_S="${ALLOWANCE_S:-36000}" \
    bash "$HOME/rlvigen-work/reeval-ppg.sh" "$mode" >> "$LOG" 2>&1
  rc=$?
  if grep -q "NATIVE_OFFLINE_EVAL_COMPLETED" "$HOME/rlvigen-runs/reeval-v214/ppg-$mode.log" 2>/dev/null; then
    say "mode=$mode COMPLETED"
  else
    say "mode=$mode ended rc=$rc WITHOUT a completion marker -- see ppg-$mode.log. Continuing to next."
  fi
done
say "chain finished"
