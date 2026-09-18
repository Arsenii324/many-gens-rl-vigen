#!/usr/bin/env bash
# Keep watching prod when NOTHING of ours is running, so a genuine opening is noticed without a prompt.
# Written after all cell-bound watchers had exited with their cells and nothing watched prod for ~2 h.
#
# It NEVER launches. It reports:
#   CAPACITY  a card is AVAILABLE under capacity-check.sh's validated rule (no foreign holder and
#             >= NEED MiB free for HOLD consecutive samples). Validated on 2026-09-17: fires at 11:00
#             (a real 15-min absence), does NOT fire at 07:52 (the 4-min gap that killed a cell).
#   OPENING   a card has been clear for 3-9 samples: a window may be forming. Heads-up only.
#   NEW-GROUP a group not seen before is on either card.
#   LOGGER    the occupancy log went stale -- then this watcher is blind and says so.
# MODE=trip exits on CAPACITY / NEW-GROUP / LOGGER (run as a background shell, no timeout).
# MODE=beat also prints a heartbeat and OPENING notices, and keeps going (run as a Monitor).
H="${HOST:-varaksin_as@100.98.2.11}"
MODE="${1:-trip}"; NEED="${NEED:-11421}"; TOTAL=32768
# Minutes between "HOST ..." heartbeat lines in beat mode. Purely a liveness ping -- CAPACITY,
# OPENING, NEW-GROUP and LOGGER all fire immediately on their own trigger, unaffected by this.
# Default 15 keeps existing behaviour for any other caller; a Monitor re-arming every 30 min can
# raise it without losing any real detection.
HEARTBEAT_MIN="${HEARTBEAT_MIN:-15}"
KNOWN="sg_sam2 rl4vla_cudagl rlvigen_kalugin_df"
STATE="$HOME/.prod-monitor-seen"; touch "$STATE"
fails=0; since=99; lastopen=""
while true; do
  out=$(ssh -o BatchMode=yes -o ConnectTimeout=20 "$H" "NEED=$NEED TOTAL=$TOTAL bash -s" <<'REMOTE' 2>/dev/null
LOG=~/rlvigen-runs/gpu-occupancy.log
age=$(( $(date +%s) - $(stat -c %Y "$LOG" 2>/dev/null || echo 0) ))
res=""
for c in 0 1; do
  run=$(grep "card=$c " "$LOG" | tail -30 | awk -v need="$NEED" -v total="$TOTAL" '
    { m=$0; sub(/.*mem=/,"",m); sub(/ .*/,"",m);
      h=$0; sub(/.*holders=/,"",h); gsub(/cell-c[0-9]+-[0-9]+/,"",h); gsub(/[,-]/,"",h);
      ok[NR] = (h=="" && (total-m) >= need) }
    END { r=0; for (i=NR; i>=1; i--) { if (ok[i]) r++; else break }; print r }')
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i $c 2>/dev/null)
  res="$res$c:$run:${free:-0};"
done
h=$(tail -2 "$LOG" 2>/dev/null | grep -oE "holders=[^ ]*" | cut -d= -f2 | tr "," "\n" | grep -vE "^cell-c|^-$|^$" | sort -u | tr "\n" ",")
echo "$age|$res|$h"
REMOTE
) || true
  if [ -z "$out" ]; then fails=$((fails+1)); [ $fails -ge 3 ] && { echo "CAPACITY-WATCH host unreachable 3x at $(date +%H:%M)"; [ "$MODE" = trip ] && exit 0; fails=0; }; sleep 60; continue; fi
  fails=0
  IFS='|' read -r age res holders <<< "$out"
  [ "${age:-0}" -gt 900 ] && { echo "LOGGER $(date +%H:%M): occupancy log ${age}s stale -- this watcher is BLIND until it is restarted"; [ "$MODE" = trip ] && exit 0; }
  IFS=',' read -r -a hs <<< "$holders"
  for x in "${hs[@]}"; do
    [ -z "$x" ] && continue
    case " $KNOWN " in *" $x "*) continue;; esac
    grep -qx "$x" "$STATE" && continue
    echo "NEW-GROUP $(date +%H:%M): '$x' is on the cards"; echo "$x" >> "$STATE"
    [ "$MODE" = trip ] && exit 0
  done
  IFS=';' read -r -a cards <<< "$res"
  line=""
  for e in "${cards[@]}"; do
    [ -z "$e" ] && continue
    IFS=':' read -r c run free <<< "$e"
    line="$line card$c clear=${run}min free=${free}MiB |"
    if [ "${run:-0}" -ge 10 ]; then
      echo "CAPACITY $(date +%H:%M): card $c has had no foreign holder and >= ${NEED} MiB free for ${run} consecutive minutes (free now ${free} MiB). Genuinely available under the validated rule -- a training cell may be launched. Nothing has been launched."
      [ "$MODE" = trip ] && exit 0
    elif [ "${run:-0}" -ge 3 ] && [ "$MODE" = beat ] && [ "$lastopen" != "$c:$run" ]; then
      echo "OPENING $(date +%H:%M): card $c clear for ${run} min (needs 10). Not yet -- ten of twelve past absences were restarts."
      lastopen="$c:$run"
    fi
  done
  if [ "$MODE" = beat ]; then
    since=$((since+1)); [ $since -ge "$HEARTBEAT_MIN" ] && { echo "HOST $(date +%H:%M)$line logger ${age}s | groups: ${holders//,/ }"; since=0; }
  fi
  sleep 60
done
