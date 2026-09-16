#!/usr/bin/env bash
# Launch ibac_sni on WHICHEVER card gets genuine room. Never contend for a card a colleague holds.
set -uo pipefail
NEED=${NEED:-18000}; LOG="$HOME/rlvigen-runs/ibac-waiter.log"
say(){ printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
say "waiting for >= ${NEED} MiB free on either card (ibac_sni procs=16 measured ~15 GiB)"
while :; do
  if grep -q "NATIVE_CELL_COMPLETED" "$HOME/rlvigen-runs/prod-v214/ibac_sni-s1-prod.log" 2>/dev/null; then say "already COMPLETED"; exit 0; fi
  for c in 1 0; do
    f=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i $c 2>/dev/null)
    if (( ${f:-0} >= NEED )); then
      say "card $c has ${f} MiB free -- launching ibac_sni there"
      rm -f "$HOME/rlvigen-runs/prod-v214/ibac_sni-s1-prod-result.tgz"
      CARD=$c TIMEOUT_S=43200 bash "$HOME/rlvigen-work/train-production-cell-v4.sh" >> "$LOG" 2>&1
      if grep -q "NATIVE_CELL_COMPLETED" "$HOME/rlvigen-runs/prod-v214/ibac_sni-s1-prod.log" 2>/dev/null; then
        say "ibac_sni COMPLETED on card $c"; exit 0; fi
      say "attempt on card $c ended without completion; see the log. Waiting for room again."
      sleep 900
    fi
  done
  sleep 300
done
