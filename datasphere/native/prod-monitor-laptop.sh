#!/usr/bin/env bash
# Run with bash explicitly. The first version ran under zsh, which does NOT word-split an unquoted
# $holders, so three known group names were reported as one unknown one.
H=varaksin_as@100.98.2.11
# [Claude 2026-09-17] The disk thresholds were 60 and 35, and both sat BELOW the floor the running
# cell enforces on itself. A cell prints its own floor in its launch banner --
# `disk: 118 GiB free, floor 98 GiB` -- and stands itself down when free space reaches it. Warning
# at 60 therefore fires long after the cell has already died, so the operator learns about the disk
# from the run disappearing rather than from the monitor. Warn ABOVE the floor.
#
# Override both when the cell's banner says a different floor; these defaults assume 98.
DISK_WARN=${DISK_WARN:-105}; DISK_CRIT=${DISK_CRIT:-99}
CURVE_TOTAL=${CURVE_TOTAL:-5}; HEARTBEAT=6; STALE_LOG_S=2400
KNOWN="sg_sam2 rl4vla_cudagl rlvigen_kalugin_df"
STATE="${STATE_FILE:-/tmp/prod-monitor-seen}"      # survives a re-arm, so a group is announced once
touch "$STATE"
last=""; fails=0; since=99
while true; do
  out=$(ssh -o BatchMode=yes -o ConnectTimeout=25 "$H" '
f0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 0)
f1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 1)
e0=$(docker ps --format "{{.Names}}" | grep -cE "^cell-c0-[0-9]+$")
t1=$(docker ps --format "{{.Names}}" | grep -cE "^cell-c1-[0-9]+$")
cur=$(ls ~/rlvigen-runs/reeval-v214/idaac-s102-curve-*.tgz 2>/dev/null | wc -l)
d=$(df -Pk ~ | awk "NR==2{printf \"%d\", \$4/1048576}")
sw=0; for p in $(pgrep -f curve-sweep-v3.sh 2>/dev/null); do
  a=$(tr "\0" "\n" < /proc/$p/cmdline 2>/dev/null | sed -n 2p); case "$a" in *curve-sweep-v3.sh) sw=$((sw+1));; esac; done
wt=0; for p in $(pgrep -f wait-and-train-v3.sh 2>/dev/null); do
  a=$(tr "\0" "\n" < /proc/$p/cmdline 2>/dev/null | sed -n 2p); case "$a" in *wait-and-train-v3.sh) wt=$((wt+1));; esac; done
L=~/rlvigen-runs/prod-v214/ibac_sni-s101-prod.log
# Family-dependent, and getting this wrong is silent. ibac_sni and ppg log `F {:06}`; idaac logs a
# key/value table whose value is in SCIENTIFIC NOTATION (`| train/total_num_steps | 3.71e+05 |`), so
# an integer regex against it captures the leading "3" and reports a 62%-trained cell as 0%. For an
# idaac cell read its `Update 180, step 370688:` line instead, which is a plain integer.
fr=$(grep -aoE "F [0-9]+" "$L" 2>/dev/null | tail -1 | tr -d "F ")
[ -z "$fr" ] && fr=$(grep -aoE "^Update [0-9]+, step [0-9]+:" "$L" 2>/dev/null | tail -1 | grep -oE "[0-9]+:$" | tr -d ":")
mk=$(grep -aoE "=== NATIVE_CELL_(COMPLETED|FAILED|YIELDED) " "$L" 2>/dev/null | tail -1 | awk "{print \$2}")
age=$(( $(date +%s) - $(stat -c %Y "$L" 2>/dev/null || date +%s) ))
res=$(ls ~/rlvigen-runs/prod-v214/ibac_sni-s101-prod-result.tgz 2>/dev/null | wc -l)
holders=$(tail -2 ~/rlvigen-runs/gpu-occupancy.log 2>/dev/null | grep -oE "holders=[^ ]*" | cut -d= -f2 | tr "," "\n" | grep -vE "^cell-c|^$" | sort -u | tr "\n" ",")
lg=$(( $(date +%s) - $(stat -c %Y ~/rlvigen-runs/gpu-occupancy.log 2>/dev/null || echo 0) ))
echo "$f0|$f1|$e0|$t1|$cur|$d|$sw|$wt|${fr:-0}|${mk:-none}|$age|$res|$lg|${holders}"' 2>/dev/null) || true

  if [ -z "$out" ]; then
    fails=$((fails+1))
    if [ "$fails" -ge 2 ] && [ "$last" != "UNREACH" ]; then echo "ALERT $(date +%H:%M) host unreachable on 2 consecutive polls"; last="UNREACH"; fi
    sleep 180; continue
  fi
  fails=0
  IFS='|' read -r f0 f1 e0 t1 cur d sw wt fr mk age res lg holders <<< "$out"
  case "$f0$f1$e0$t1$cur$d$sw$wt$age$res$lg" in *[!0-9]*|"") sleep 180; continue;; esac

  # Split on commas explicitly; do not rely on the shell's word splitting at all.
  IFS=',' read -r -a hs <<< "$holders"
  for h in "${hs[@]}"; do
    [ -z "$h" ] && continue
    case " $KNOWN " in *" $h "*) continue;; esac
    grep -qx "$h" "$STATE" && continue
    echo "NEW-GROUP $(date +%H:%M) a group not seen before is on the cards: '$h' (card0 ${f0} / card1 ${f1} MiB free)"
    echo "$h" >> "$STATE"
  done

  state="ok"
  [ "$cur" -ge "$CURVE_TOTAL" ] && state="curve-done"
  [ "$sw" -eq 0 ] && [ "$e0" -eq 0 ] && [ "$cur" -lt "$CURVE_TOTAL" ] && state="curve-stalled"
  [ "$lg" -gt 900 ] && state="logger-stale"
  [ "$d" -lt "$DISK_WARN" ] && state="disk-low"
  [ "$wt" -eq 0 ] && [ "$t1" -eq 0 ] && [ "$res" -eq 0 ] && state="waiter-gone"
  [ "$t1" -gt 0 ] && state="ibac-running"
  [ "$t1" -gt 0 ] && [ "$age" -gt "$STALE_LOG_S" ] && state="ibac-stalled"
  [ "$res" -gt 0 ] && state="ibac-done"
  [ "$d" -lt "$DISK_CRIT" ] && state="disk-crit"

  since=$((since+1))
  if [ "$state" != "$last" ] || [ "$since" -ge "$HEARTBEAT" ]; then
    groups="${holders//,/ }"
    case "$state" in
      disk-crit)     echo "DISK-CRIT $(date +%H:%M) ${d} GiB free -- at or below the floor the cell enforces on itself; it will stand down";;
      disk-low)      echo "DISK-LOW $(date +%H:%M) ${d} GiB free, against a cell floor of ~98 GiB";;
      logger-stale)  echo "LOGGER-STALE $(date +%H:%M) gpu-occupancy.log not written for ${lg}s -- the morning watch depends on it";;
      curve-stalled) echo "CURVE-STALLED $(date +%H:%M) s102: no sweep and no eval cells, ${cur}/${CURVE_TOTAL}";;
      curve-done)    echo "CURVE-DONE $(date +%H:%M) idaac s102 partial curve ${cur}/${CURVE_TOTAL} -- collect it";;
      waiter-gone)   echo "WAITER-GONE $(date +%H:%M) no ibac waiter, no ibac cell, no result -- it gave up or died; last ibac marker ${mk}";;
      ibac-running)  echo "IBAC-RUNNING $(date +%H:%M) ibac_sni s101 on card 1 at frame ${fr}, log ${age}s old";;
      ibac-stalled)  echo "IBAC-STALLED $(date +%H:%M) ibac log untouched ${age}s at frame ${fr} -- check docker stats";;
      ibac-done)     echo "IBAC-DONE $(date +%H:%M) ibac_sni-s101-prod-result.tgz present -- THIRD baseline; collect it";;
      *)             echo "HOST $(date +%H:%M) s102 curve ${cur}/${CURVE_TOTAL} (${e0} eval) | waiter ${wt} | card0 ${f0} card1 ${f1} MiB free | groups: ${groups:-none} | logger ${lg}s | disk ${d}GiB";;
    esac
    last="$state"; since=0
  fi
  sleep 180
done
