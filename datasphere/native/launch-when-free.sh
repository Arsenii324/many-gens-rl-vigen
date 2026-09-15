#!/usr/bin/env bash
# Retry a cell launch until a card is genuinely free, then stop retrying.
#
# [Claude 2026-09-15] The booking ends 2026-09-16 23:59 MSK and both cards are shared with three
# colleagues, so a free card may appear at any hour and waiting for a human to notice wastes the
# window. This retries; it does not force.
#
# THE PREFLIGHT IS THE GUARD, and that is the whole safety argument. `launch-card-cell.sh` runs
# `watch_gpu_headroom.py --preflight --require-exclusive` before anything else and refuses when ANY
# compute process is on the card -- at preflight our cell does not exist, so every process there is
# someone else's. A retry loop therefore cannot take an occupied card no matter how often it tries;
# an attempt against a busy card costs one refused container and nothing else. Measured live:
# a colleague's `rlvigen_kalugin_df` took card 1 at 15:57 and the 15:58 attempt refused.
#
# It never kills, never yields anything of anyone else's, and stops after the first success.
set -uo pipefail
MODE="${1:?usage: launch-when-free.sh <mode> [card]}"
CARD_WANT="${2:-1}"
INTERVAL="${LAUNCH_RETRY_INTERVAL:-300}"
DEADLINE="${LAUNCH_DEADLINE_EPOCH:-0}"       # 0 = no deadline
LOG="$HOME/rlvigen-runs/launch-when-free.log"

say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
say "started: mode=$MODE card=$CARD_WANT interval=${INTERVAL}s"

while :; do
  if (( DEADLINE > 0 )) && (( $(date +%s) > DEADLINE )); then
    say "DEADLINE reached without ever finding a free card; giving up"
    exit 1
  fi
  procs="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$CARD_WANT" 2>/dev/null | grep -c .)"
  if [[ "${procs:-1}" -eq 0 ]]; then
    say "card $CARD_WANT reads free (0 compute apps); attempting launch"
    TIMEOUT_S="${TIMEOUT_S:-3600}" ALLOWANCE_S="${ALLOWANCE_S:-36000}" \
      bash "$HOME/rlvigen-work/reeval-ppg.sh" "$MODE" >> "$LOG" 2>&1
    rc=$?
    if [[ $rc -eq 0 ]] && grep -q "NATIVE_OFFLINE_EVAL_COMPLETED" \
         "$HOME/rlvigen-runs/reeval-v214/ppg-$MODE.log" 2>/dev/null; then
      say "LAUNCH SUCCEEDED and evaluation completed (mode=$MODE)"
      exit 0
    fi
    if grep -q "preflight refused" "$HOME/rlvigen-runs/reeval-v214/ppg-$MODE.log" 2>/dev/null; then
      say "preflight refused -- someone took the card between the check and the launch; retrying"
    else
      say "attempt ended rc=$rc without a completion marker; see ppg-$MODE.log. Retrying."
    fi
  fi
  sleep "$INTERVAL"
done
