#!/usr/bin/env bash
# Run with bash explicitly. The first version ran under zsh, which does NOT word-split an unquoted
# $holders, so three known group names were reported as one unknown one.
H=varaksin_as@100.98.2.11
DISK_WARN=60; DISK_CRIT=35; CURVE_TOTAL=5; HEARTBEAT=6; STALE_LOG_S=2400
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
fr=$(grep -aoE "F [0-9]+" "$L" 2>/dev/null | tail -1 | tr -d "F ")
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
      disk-crit)     echo "DISK-CRIT $(date +%H:%M) ${d} GiB free";;
      disk-low)      echo "DISK-LOW $(date +%H:%M) ${d} GiB free";;
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
