#!/usr/bin/env bash
# Evaluate, from the host's occupancy log, whether each card is GENUINELY available for a training
# cell as of a moment in time. Read-only; it never launches anything.
#
# Rule, measured on 2026-09-17: the co-tenant's absences from card 1 over 30 h were
# 2,1,1,36,1,1,171,1,5,1,1,4 minutes -- ten of twelve were restarts between its jobs. A training cell
# launched into a 4-minute gap was stopped by the memory floor. So a card is AVAILABLE only when, for
# the last HOLD consecutive samples, it had NO foreign holder AND at least NEED MiB free.
#   NEED = 11421 = ibac_sni's measured 7,421 peak + the 4,000 MiB floor (the largest cell we run
#          except ctrl, which needs an empty card regardless).
# A foreign holder present at ANY size disqualifies the card: kalugin ran at ~12 GiB for hours with
# 20 GiB free and could regrow to ~22 GiB, which would put a new cell under the floor.
#
#   AS_OF="2026-09-17T11:00" bash capacity-check.sh     # replay a past moment
#   bash capacity-check.sh                              # now
H="${HOST:-varaksin_as@100.98.2.11}"
NEED="${NEED:-11421}"; HOLD="${HOLD:-10}"; TOTAL="${TOTAL:-32768}"; AS_OF="${AS_OF:-}"
ssh -o BatchMode=yes -o ConnectTimeout=20 "$H" "AS_OF='$AS_OF' NEED=$NEED HOLD=$HOLD TOTAL=$TOTAL bash -s" <<'REMOTE' 2>/dev/null
LOG=~/rlvigen-runs/gpu-occupancy.log
for c in 0 1; do
  if [ -n "$AS_OF" ]; then
    lines=$(grep "card=$c " "$LOG" | awk -v t="$AS_OF" 'substr($1,1,16) <= t' | tail -"$HOLD")
  else
    lines=$(grep "card=$c " "$LOG" | tail -"$HOLD")
  fi
  n=$(printf '%s\n' "$lines" | grep -c "card=$c ")
  # a sample is CLEAR when no foreign holder is present and used memory leaves NEED free
  clear=$(printf '%s\n' "$lines" | awk -v need="$NEED" -v total="$TOTAL" '
    /card=/ { m=$0; sub(/.*mem=/,"",m); sub(/ .*/,"",m);
              h=$0; sub(/.*holders=/,"",h); gsub(/cell-c[0-9]+-[0-9]+/,"",h); gsub(/[,-]/,"",h);
              if (h=="" && (total-m) >= need) c++ }
    END { print c+0 }')
  last=$(printf '%s\n' "$lines" | tail -1 | cut -c1-16)
  holders=$(printf '%s\n' "$lines" | tail -1 | grep -oE 'holders=[^ ]*' | cut -d= -f2)
  if [ "$n" -ge "$HOLD" ] && [ "$clear" -ge "$HOLD" ]; then v="AVAILABLE"; else v="not-available"; fi
  echo "card $c as of $last: $v  ($clear/$n clear samples; last holders: ${holders:-none})"
done
REMOTE
