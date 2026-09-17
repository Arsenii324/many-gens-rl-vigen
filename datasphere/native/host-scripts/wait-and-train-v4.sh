#!/usr/bin/env bash
# Wait for a GENUINE vacancy on a card, then launch ONE production cell. Runs ON THE HOST, detached.
#
# Why v4 exists. `wait-and-train-v3.sh` counts polls with `free >= NEED` and nothing else, so beside
# a co-tenant holding 12 GiB a 32 GiB card still looks free and it would launch — which is the case
# OPERATOR-GUIDE §5.1 exists to prevent (the co-tenant's own peak on this card is 32,346 MiB, taken
# by one process, so "free now" says nothing about free in ten minutes). v4 applies the rule that was
# actually validated: for HOLD consecutive samples of `gpu-occupancy.log`, the card must have **no
# foreign holder at all** and at least NEED MiB free.
#
# It exists because a real window opened at 21:39 on 2026-09-17, the watcher reported it correctly,
# and nobody was at the keyboard to launch into it. A reporter that no one reads during the window
# is the same as no reporter.
#
#   CARD=1 FAMILY=idaac BASELINE=idaac SEED=103 VRAM_MIB=5000 nohup setsid bash wait-and-train-v4.sh &
#   DRYRUN=1 ... bash wait-and-train-v4.sh        # decide, print, never launch
#   AS_OF=2026-09-17T11:00 DECIDE_ONLY=1 ...      # replay one past moment and exit (validation)
#
# What it REFUSES to do, each for a reason this campaign paid for:
#   * launch while the occupancy log is stale — a blind waiter cannot see a co-tenant (LOGGER);
#   * launch when any cell container of ours is up, or another launcher is running (double-launch);
#   * launch when the result archive for this tag already exists (it would be skipped anyway);
#   * launch with less than MIN_DISK_GIB free — a new cell's bootstrap eats into live cells' floors;
#   * hold the lock silently: everything it decides goes to its log with a timestamp.
#
# It never stops, kills or deletes anything. The only thing it starts is train-production-cell-v5.sh,
# and after that the self-cap watcher for the container that appears.
set -uo pipefail
CARD="${CARD:-1}"
FAMILY="${FAMILY:?set FAMILY}"; BASELINE="${BASELINE:?set BASELINE}"; SEED="${SEED:?set SEED}"
NEED="${NEED:-11421}"        # ibac_sni's 7,421 peak + the 4,000 MiB floor: the largest cell we run
HOLD="${HOLD:-10}"           # ten one-minute samples; ten of twelve past absences were restarts
POLL="${POLL:-60}"
MAXWAIT="${MAXWAIT:-43200}"
MIN_DISK_GIB="${MIN_DISK_GIB:-60}"
VRAM_MIB="${VRAM_MIB:-5000}"
EXPECT_OURS="${EXPECT_OURS:-20}"
LOG_MAX_AGE="${LOG_MAX_AGE:-180}"
OCC="${OCC:-$HOME/rlvigen-runs/gpu-occupancy.log}"
A="$HOME/rlvigen-runs/prod-v214"; TAG="$BASELINE-s$SEED-prod"
LOG="${WAITER_LOG:-$A/$TAG-waiter-v4.log}"
mkdir -p "$A"
say(){ echo "$(date -Is) $*" >> "$LOG"; }

# How many of the last HOLD samples for this card were CLEAR: no foreign holder, and NEED free.
# Identical rule to host-scripts/capacity-check.sh, which was validated against two known moments.
clear_streak(){
  local as_of="${1:-}"
  local lines
  if [ -n "$as_of" ]; then
    lines=$(grep "card=$CARD " "$OCC" | awk -v t="$as_of" 'substr($1,1,16) <= t' | tail -"$HOLD")
  else
    lines=$(grep "card=$CARD " "$OCC" | tail -"$HOLD")
  fi
  printf '%s\n' "$lines" | awk -v need="$NEED" -v total="${TOTAL:-32768}" '
    /card=/ { m=$0; sub(/.*mem=/,"",m); sub(/ .*/,"",m);
              h=$0; sub(/.*holders=/,"",h); gsub(/cell-c[0-9]+-[0-9]+/,"",h); gsub(/[,-]/,"",h);
              if (h=="" && (total-m) >= need) c++ }
    END { print c+0 }'
}

if [ "${DECIDE_ONLY:-0}" = "1" ]; then
  n="$(clear_streak "${AS_OF:-}")"
  echo "card $CARD at ${AS_OF:-now}: $n/$HOLD clear samples -> $([ "$n" -ge "$HOLD" ] && echo LAUNCHABLE || echo wait)"
  exit 0
fi

# The lock is v4's OWN file, deliberately. [Claude 2026-09-18] `wait-and-train-v3.sh` takes
# `~/rlvigen-runs/.wait-and-train.lock` and holds it for the life of the cell it starts -- and the
# reaper subshell inside launch-card-cell.sh (`sleep $WATCH_SECONDS`) INHERITS that open descriptor,
# so the lock stays held for the whole watch budget even after the cell has completed. Found live:
# `ibac_sni` s101 finished at 11:16 on 17 Sep, and at 01:07 on 18 Sep the lock was still held by
# `sleep 115668` started 20:35 on 16 Sep -- 32 hours, of which the cell used 15. A waiter sharing
# that file would refuse every window in between, which is the opposite of what a waiter is for.
#
# Single-launcher safety does not come from the file anyway: it comes from the two checks below,
# which look at what is actually RUNNING rather than at what once opened a descriptor.
exec 9>"$HOME/rlvigen-runs/.wait-and-train-v4.lock"
flock -n 9 || { say "REFUSING: another v4 waiter holds the lock. One launcher at a time."; exit 3; }
for p in $(pgrep -f "train-production-cell-v5.sh|wait-and-train-v3.sh" 2>/dev/null); do
  say "REFUSING: a launcher is already running (pid $p)."; exit 3
done
if [ -f "$A/$TAG-result.tgz" ]; then say "REFUSING: $A/$TAG-result.tgz exists; nothing to launch."; exit 0; fi

say "waiting for card $CARD: no foreign holder and >= ${NEED} MiB free for ${HOLD} samples; max ${MAXWAIT}s"
started=$(date +%s); last=""
while :; do
  now=$(date +%s)
  if [ $((now-started)) -ge "$MAXWAIT" ]; then say "GAVE UP after ${MAXWAIT}s without a window"; exit 4; fi

  age=$(( now - $(stat -c %Y "$OCC" 2>/dev/null || echo 0) ))
  if [ "$age" -gt "$LOG_MAX_AGE" ]; then
    say "BLIND: $OCC is ${age}s stale, so a co-tenant would be invisible. Not launching. Restart gpu-occupancy-log.sh."
    sleep "$POLL"; continue
  fi

  if docker ps --format '{{.Names}}' | grep -qE "^cell-c[0-9]+-[0-9]+$"; then
    say "HOLDING: a cell container of ours is already running."
    sleep "$POLL"; continue
  fi

  n="$(clear_streak)"
  [ "$n:$age" != "$last" ] && { say "streak ${n}/${HOLD} (log ${age}s old)"; last="$n:$age"; }
  if [ "$n" -lt "$HOLD" ]; then sleep "$POLL"; continue; fi

  # final checks at the instant of launch, not from a sample a minute old
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
  case "$free" in ''|*[!0-9]*) say "nvidia-smi gave no number; waiting"; sleep "$POLL"; continue;; esac
  if [ "$free" -lt "$NEED" ]; then say "window evaporated at the last check: ${free} MiB free"; sleep "$POLL"; continue; fi
  disk=$(df -Pk "$HOME" | awk 'NR==2{printf "%d", $4/1048576}')
  if [ "$disk" -lt "$MIN_DISK_GIB" ]; then say "REFUSING: ${disk} GiB free, below MIN_DISK_GIB=${MIN_DISK_GIB}"; sleep "$POLL"; continue; fi

  say "WINDOW HELD: ${n}/${HOLD} clear samples, ${free} MiB free, ${disk} GiB disk. Launching $TAG on card $CARD."
  if [ "${DRYRUN:-0}" = "1" ]; then say "DRYRUN=1 -- stopping here, nothing launched."; exit 0; fi

  [ -f "$A/$TAG-prod.log" ] && cp -p "$A/$TAG-prod.log" "$A/$TAG-prod-previous-$(date +%Y%m%d-%H%M).log"
  env CARD="$CARD" YIELD_PROCS=1 FAMILY="$FAMILY" BASELINE="$BASELINE" SEED="$SEED" \
      EXPECT_OURS="$EXPECT_OURS" VRAM_MIB="$VRAM_MIB" \
      bash "$HOME/rlvigen-work/train-production-cell-v5.sh" >> "$LOG" 2>&1 &
  launcher=$!
  say "launcher pid $launcher; waiting for the cell container to arm the self-cap"
  for _ in $(seq 1 60); do
    c=$(docker ps --format '{{.Names}}' | grep -E "^cell-c${CARD}-[0-9]+\$" | head -1)
    [ -n "$c" ] && break
    sleep 5
  done
  if [ -n "${c:-}" ]; then
    nohup setsid bash "$HOME/rlvigen-work/self-vram-cap.sh" "$c" "$CARD" "$VRAM_MIB" \
      "$HOME/rlvigen-runs/self-vram-cap-$BASELINE-s$SEED.log" >/dev/null 2>&1 &
    say "self-cap armed on $c at ${VRAM_MIB} MiB"
  else
    say "NO CELL CONTAINER appeared within 300s -- check $A/$TAG-prod.log; no self-cap armed"
  fi
  wait "$launcher"
  say "launcher exited rc=$? -- this waiter is done"
  exit 0
done
