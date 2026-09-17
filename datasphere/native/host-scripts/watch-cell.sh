#!/usr/bin/env bash
# Watch ONE production cell from the laptop: stop detection, result, disk against the cell's own
# floor, stall, occupancy logger, and any new group on the cards.
#
# PROVENANCE -- this is not a proposal. It is the watcher that actually ran on 2026-09-17, committed
# with only its hardcoded run paths turned into required parameters; the logic is unchanged.
#   - It watched idaac s102 from 12:03 onward in both modes (trip as a background shell, beat as a
#     Monitor) for hours without a false alarm, through a co-tenant's job churning on the same card.
#   - Its stop test `*FAILED|*YIELDED` is the form proven on a real stopped cell: five earlier
#     monitors used the bare `FAILED|YIELDED`, which never matches because the marker is
#     `=== NATIVE_CELL_YIELDED stopping this cell; ... ===` and awk '{print $2}' yields the whole
#     token. A cell died unreported for 18 minutes before that was found.
#   - The committed form was then run against a cell that really did stop, and fired.
#
#     RUN=card1-20260917-110044 LOG=ibac_sni-s102-prod.log CELL=ibac_sni-s102 FLOOR=89 \
#       bash watch-cell.sh trip
#
# Parameters (all required -- a wrong default here watches the wrong run silently):
#   RUN    run directory name under ~/rlvigen-runs/  (card<N>-<YYYYmmdd-HHMMSS>)
#   LOG    launcher log name under ~/rlvigen-runs/prod-v214/
#   CELL   cell directory name under native-out/cells/  (e.g. idaac-s102)
#   FLOOR  this cell's own disk floor in GiB, from its launch banner line `disk: ... floor N GiB`.
#          It is per cell, fixed at that cell's launch; when several cells run, pass the HIGHEST.
#
# Modes:  trip  exit on the first actionable event (run as a background shell, no timeout)
#         beat  also print a heartbeat every sixth poll and keep going (run as a Monitor)
#
# What it does NOT know: curve and endpoint row TOTALS differ by family and by stamp count, so the
# heartbeat prints counts, not percentages. Read OPERATOR-GUIDE.md section 10 for what each stop means.
H="${HOST:-varaksin_as@100.98.2.11}"
RUN="${RUN:?set RUN to the run directory name}"; LOG="${LOG:?set LOG to the launcher log name}"
CELL="${CELL:?set CELL to the cell directory name}"; FLOOR="${FLOOR:?set FLOOR to the cell disk floor in GiB}"
KNOWN="sg_sam2 rl4vla_cudagl rlvigen_kalugin_df"
MODE="${1:-trip}"; STATE="$HOME/.prod-monitor-seen"; touch "$STATE"
fails=0; last=""; since=99
while true; do
  out=$(ssh -o BatchMode=yes -o ConnectTimeout=25 "$H" '
I=~/rlvigen-runs/prod-v214/'"$LOG"'
D=~/rlvigen-runs/'"$RUN"'/native-out/cells/'"$CELL"'
mk=$(grep -aoE "=== NATIVE_CELL_(COMPLETED|FAILED|YIELDED) " "$I" 2>/dev/null | tail -1 | awk "{print \$2}")
res=$(ls ~/rlvigen-runs/prod-v214/'"${LOG%.log}"'-result.tgz 2>/dev/null | wc -l)
cv=$(wc -l < "$D/offline_eval_curve.jsonl" 2>/dev/null)
ep=$(wc -l < "$D/offline_eval_endpoint.jsonl" 2>/dev/null)
em=$(wc -l < "$D/offline_eval_endpoint_mode.jsonl" 2>/dev/null)
age=$(( $(date +%s) - $(stat -c %Y "$I" 2>/dev/null || date +%s) ))
t=$(docker ps --format "{{.Names}}" | grep -cE "^cell-c1-[0-9]+$")
d=$(df -Pk ~ | awk "NR==2{printf \"%d\", \$4/1048576}")
f1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 1)
lg=$(( $(date +%s) - $(stat -c %Y ~/rlvigen-runs/gpu-occupancy.log 2>/dev/null || echo 0) ))
h=$(tail -2 ~/rlvigen-runs/gpu-occupancy.log 2>/dev/null | grep -oE "holders=[^ ]*" | cut -d= -f2 | tr "," "\n" | grep -vE "^cell-c|^-$|^$" | sort -u | tr "\n" ",")
echo "${mk:-none}|$res|${cv:-0}|${ep:-0}|${em:-0}|$age|$t|$d|$f1|$lg|$h"' 2>/dev/null) || true
  if [ -z "$out" ]; then
    fails=$((fails+1))
    if [ "$fails" -ge 3 ]; then echo "TRIP host unreachable on 3 consecutive polls at $(date +%H:%M)"; [ "$MODE" = trip ] && exit 0; fails=0; fi
    sleep 120; continue
  fi
  fails=0
  IFS='|' read -r mk res cv ep em age t d f1 lg h <<< "$out"
  IFS=',' read -r -a hs <<< "$h"
  for x in "${hs[@]}"; do
    [ -z "$x" ] && continue
    case " $KNOWN " in *" $x "*) continue;; esac
    grep -qx "$x" "$STATE" && continue
    echo "NEW-GROUP $(date +%H:%M) a group not seen before is on the cards: '$x'"; echo "$x" >> "$STATE"
    [ "$MODE" = trip ] && exit 0
  done
  case "$mk" in *FAILED|*YIELDED) echo "CELL-STOPPED $(date +%H:%M) marker=$mk with $cv curve row(s) and $ep+$em endpoint row(s) written. Every row already written is durable; whether any CHECKPOINT survived depends on whether training passed its first cadence stamp. Read ${RUN}/native-work/yield.sentinel for the reason."; [ "$MODE" = trip ] && exit 0;; esac
  [ "$res" -gt 0 ] 2>/dev/null && { echo "CELL-DONE $(date +%H:%M) result present -- collect it. Do NOT populate the evaluator ledger from it: a production file is never attestation evidence."; [ "$MODE" = trip ] && exit 0; }
  [ "$t" = "0" ] && { echo "NO-CELLS $(date +%H:%M) no card-1 cell containers at all (marker=$mk)"; [ "$MODE" = trip ] && exit 0; }
  [ "$d" -le "$FLOOR" ] 2>/dev/null && { echo "DISK $(date +%H:%M) $d GiB -- at or below this cell's own floor of ${FLOOR} GiB -- the cell stands itself down there"; [ "$MODE" = trip ] && exit 0; }
  [ "$age" -gt 2400 ] 2>/dev/null && { echo "CELL-STALLED $(date +%H:%M) log untouched ${age}s at $cv curve row(s) -- check docker stats before acting"; [ "$MODE" = trip ] && exit 0; }
  [ "$lg" -gt 900 ] 2>/dev/null && { echo "LOGGER-STALE $(date +%H:%M) occupancy log ${lg}s old"; [ "$MODE" = trip ] && exit 0; }
  if [ "$MODE" = beat ]; then
    since=$((since+1))
    if [ "$since" -ge 6 ]; then
      echo "HOST $(date +%H:%M) ${CELL} curve rows ${cv} endpoint ${ep}+${em} (${age}s) | card1 free ${f1} | disk ${d}GiB | groups: ${h//,/ }"
      since=0
    fi
  fi
  sleep 120
done
