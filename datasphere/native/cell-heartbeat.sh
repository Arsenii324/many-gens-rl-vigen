#!/usr/bin/env bash
# Watch one running cell and SAY something the moment anything looks wrong. Never stops anything.
#
# [Claude 2026-09-15] The rule this implements, in the owner's words: relaxing a monitor is easier
# than finding a silent error. So it errs loud. It writes to its own file on the host, detached, so
# that -- unlike the three ssh-held monitors killed earlier today -- its DEATH is visible as a gap
# in its own timestamps rather than as silence.
#
# It reports, it does not act. No kill, no yield, no container touched. The only automatic
# stand-down in this system remains the cell's own yield sentinel, which the cell honours itself.
set -uo pipefail
LOG_IN="${1:?usage: cell-heartbeat.sh <cell log> [name]}"
NAME="${2:-cell}"
OUT="$HOME/rlvigen-runs/heartbeat-$NAME.log"
STALL="${HEARTBEAT_STALL_SECONDS:-1800}"
INTERVAL="${HEARTBEAT_INTERVAL:-120}"
WARN_AT="${HEARTBEAT_WARN_FRACTION:-0}"     # epoch seconds; 0 disables the budget warning

say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$OUT"; }
say "heartbeat started for $NAME watching $LOG_IN (stall=${STALL}s)"
last_size=0; last_change=$(date +%s); warned_budget=0

while :; do
  now=$(date +%s)
  size=$(stat -c%s "$LOG_IN" 2>/dev/null || echo 0)
  running="$(docker ps -q --filter "name=cell-c1-" --filter "name=cell-c0-" 2>/dev/null | wc -l)"
  eps=$(grep -c "episode_return_mean" "$LOG_IN" 2>/dev/null || echo 0)

  if [[ "$size" -ne "$last_size" ]]; then last_size=$size; last_change=$now; fi
  quiet=$(( now - last_change ))

  # Terminal states first: say what happened, then stop watching.
  if grep -qE "NATIVE_OFFLINE_EVAL_COMPLETED" "$LOG_IN" 2>/dev/null; then
    say "DONE: NATIVE_OFFLINE_EVAL_COMPLETED seen. rows-with-means=$eps"; exit 0; fi
  if grep -qE "NATIVE_OFFLINE_EVAL_FAILED|NATIVE_CELL_FAILED|ABORTING" "$LOG_IN" 2>/dev/null; then
    say "PROBLEM: failure marker in the log -- $(grep -oE 'NATIVE_[A-Z_]+FAILED[^=]*|ABORTING.*' "$LOG_IN" | tail -1)"; exit 2; fi
  if grep -qE "CELL EXIT=[1-9]" "$LOG_IN" 2>/dev/null; then
    say "PROBLEM: $(grep -oE 'CELL EXIT=[0-9]+' "$LOG_IN" | tail -1)"; exit 2; fi
  if [[ -f "$(dirname "$LOG_IN")/../native-work/yield.sentinel" ]]; then
    say "YIELDED: a sentinel was written, so the cell stood down for a neighbour. Not an error."; exit 0; fi
  if [[ "${running:-0}" -eq 0 ]]; then
    say "PROBLEM: no cell container is running and no completion marker was written"; exit 2; fi

  # Non-terminal warnings: loud, repeated, but the run continues.
  if [[ "$quiet" -gt "$STALL" ]]; then
    say "WARNING: the log has not grown for ${quiet}s (stall threshold ${STALL}s). rows=$eps"
  fi
  if (( WARN_AT > 0 )) && (( now > WARN_AT )) && (( warned_budget == 0 )); then
    say "WARNING: past the notify-before-the-watch-fires mark. The watch budget will end this cell"
    say "         without further notice. Nothing has been stopped by this monitor."
    warned_budget=1
  fi
  sleep "$INTERVAL"
done
