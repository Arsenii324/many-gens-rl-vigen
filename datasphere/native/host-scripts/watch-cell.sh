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
#
# [Claude 2026-09-20, item 5 of the stop-mechanisms fix] PROJECTION: FRAMES (target, default the
# production 600000) and CEILING_S (this cell's own CELL_TIMEOUT_SECONDS; optional -- leave unset
# and the projection still prints, just without an overrun comparison) let the heartbeat say
# whether training is actually on pace. 2026-09-19: a cell ran at 2.4 FPS against a required ~14
# and nothing said so anywhere in this chain (eval-cost-and-timeout-trace.md Part 2, 2d: "No
# projection mechanism found"). `project_training_finish` below is the whole mechanism; it is a
# pure function over a fetched header+last-row of train.csv, target frames and a ceiling, kept
# separate from the ssh plumbing so it can be lifted and tested with canned input, per the
# tests/test_places365_checks_the_split_it_consumes.py extraction pattern.
H="${HOST:-varaksin_as@100.98.2.11}"
RUN="${RUN:?set RUN to the run directory name}"; LOG="${LOG:?set LOG to the launcher log name}"
CELL="${CELL:?set CELL to the cell directory name}"; FLOOR="${FLOOR:?set FLOOR to the cell disk floor in GiB}"
FRAMES="${FRAMES:-600000}"; CEILING_S="${CEILING_S:-}"
KNOWN="sg_sam2 rl4vla_cudagl rlvigen_kalugin_df"
MODE="${1:-trip}"; STATE="$HOME/.prod-monitor-seen"; touch "$STATE"

# --- BEGIN project_training_finish ---
# Args: $1 = "<header>@@TCROW@@<last-data-row>" from train.csv (CSV, comma-separated, header names
#            the columns) -- empty means the family offers nothing parseable (six of the twelve
#            baselines here do not write this file: idaac writes progress-*.csv, dmc_gb families
#            write train.log as JSONL, ppg writes model saves plus its own log lines, ctrl and alda
#            write only their console log -- normalize_curves.py's seven read_* functions are the
#            map of what exists per family; this function does not try to cover them and says so
#            when it cannot).
#       $2 = target FRAMES for this cell.
#       $3 = ceiling in seconds, or empty if unknown.
#       $4 = MODE ("trip" or "beat"); an OVERRUN line is only emitted for "trip".
# Prints one PROJECTION line always, and one OVERRUN line iff mode=trip and the projected finish
# exceeds the ceiling by more than 10%. Touches no file and no network.
project_training_finish() {
  local raw="$1" target_frames="$2" ceiling_s="$3" mode="${4:-}"
  if [ -z "$raw" ]; then
    echo "PROJECTION no parseable training-progress file for this family (train.csv absent) -- cannot project"
    return 0
  fi
  local header="${raw%%@@TCROW@@*}" lastrow="${raw#*@@TCROW@@}"
  local frame_col="" time_col="" i=0 name old_ifs="$IFS"
  IFS=','
  for name in $header; do
    i=$((i + 1))
    [ "$name" = "frame" ] && frame_col=$i
    [ "$name" = "total_time" ] && time_col=$i
  done
  IFS="$old_ifs"
  if [ -z "$frame_col" ] || [ -z "$time_col" ]; then
    echo "PROJECTION train.csv has no frame/total_time column -- cannot project"
    return 0
  fi
  local frame total_time
  frame=$(echo "$lastrow" | cut -d, -f"$frame_col")
  total_time=$(echo "$lastrow" | cut -d, -f"$time_col")
  case "$frame" in ''|*[!0-9.]*) frame="";; esac
  case "$total_time" in ''|*[!0-9.]*) total_time="";; esac
  if [ -z "$frame" ] || [ -z "$total_time" ] || [ "$frame" = "0" ] || [ "$total_time" = "0" ]; then
    echo "PROJECTION train.csv has no usable frame/total_time row yet -- cannot project"
    return 0
  fi
  local fps finish_h ceiling_h
  # LC_ALL=C: an awk under a comma-decimal locale (e.g. ru_RU) prints "8,3" for %.1f, which nothing
  # downstream (this function's own arithmetic, or a test asserting on the text) can parse as a
  # number -- pin the C locale for every arithmetic call in this function.
  fps=$(LC_ALL=C awk -v f="$frame" -v t="$total_time" 'BEGIN{ if (t>0) printf "%.2f", f/t; else print "0" }')
  finish_h=$(LC_ALL=C awk -v f="$frame" -v t="$total_time" -v target="$target_frames" \
    'BEGIN{ printf "%.1f", (target / f) * t / 3600 }')
  if [ -n "$ceiling_s" ]; then
    ceiling_h=$(LC_ALL=C awk -v c="$ceiling_s" 'BEGIN{printf "%.1f", c / 3600}')
  else
    ceiling_h="unknown"
  fi
  echo "PROJECTION projected training finish in ${finish_h} h at ${fps} FPS; ceiling ${ceiling_h} h"
  if [ "$mode" = trip ] && [ -n "$ceiling_s" ]; then
    local over
    over=$(LC_ALL=C awk -v fh="$finish_h" -v c="$ceiling_s" \
      'BEGIN{ finish_s = fh * 3600; print (finish_s > c * 1.1) ? 1 : 0 }')
    if [ "$over" = "1" ]; then
      echo "OVERRUN projected finish (${finish_h} h) exceeds the ceiling (${ceiling_h} h) by more than 10% -- stop and look before it eats the whole booking"
    fi
  fi
}
# --- END project_training_finish ---

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
tc=""
if [ -f "$D/train.csv" ]; then tc="$(head -1 "$D/train.csv")@@TCROW@@$(tail -1 "$D/train.csv")"; fi
echo "${mk:-none}|$res|${cv:-0}|${ep:-0}|${em:-0}|$age|$t|$d|$f1|$lg|$h|$tc"' 2>/dev/null) || true
  if [ -z "$out" ]; then
    fails=$((fails+1))
    if [ "$fails" -ge 3 ]; then echo "TRIP host unreachable on 3 consecutive polls at $(date +%H:%M)"; [ "$MODE" = trip ] && exit 0; fails=0; fi
    sleep 120; continue
  fi
  fails=0
  IFS='|' read -r mk res cv ep em age t d f1 lg h tc <<< "$out"
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
  # [Claude 2026-09-20, item 5] Visible in minutes, from the laptop: project training's own pace
  # against the ceiling every poll (2 minutes), not only in the six-poll heartbeat. Trip mode gets
  # ONE actionable line and exits on it, matching every other check above; beat mode folds the
  # same projection into its periodic heartbeat instead.
  proj="$(project_training_finish "$tc" "$FRAMES" "$CEILING_S" "$MODE")"
  overrun="$(printf '%s\n' "$proj" | grep '^OVERRUN' || true)"
  if [ -n "$overrun" ]; then
    echo "$overrun $(date +%H:%M)"
    [ "$MODE" = trip ] && exit 0
  fi
  if [ "$MODE" = beat ]; then
    since=$((since+1))
    if [ "$since" -ge 6 ]; then
      echo "HOST $(date +%H:%M) ${CELL} curve rows ${cv} endpoint ${ep}+${em} (${age}s) | card1 free ${f1} | disk ${d}GiB | groups: ${h//,/ }"
      printf '%s\n' "$proj" | grep '^PROJECTION' | sed "s/^PROJECTION/PROJECTION $(date +%H:%M)/"
      since=0
    fi
  fi
  sleep 120
done
