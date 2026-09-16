#!/usr/bin/env bash
# Launch ONE production cell when a card's capacity for us clears a threshold and STAYS clear.
#
# [Claude 2026-09-16] Written after the occupancy log refuted my own conclusion. Two days of
# 60-second samples say card 1's co-tenant is INTERMITTENT -- median hold 0 MiB, capacity for us
# 28,494 MiB median, a training cell fits 87.8% of samples and the longest unbroken window is
# 18.2 hours. I had concluded "training is not viable on this host" from a few hours in which that
# co-tenant happened to be active. Card 0 is the opposite: median co-tenant 26,243 MiB, capacity
# 2,251 MiB, training fits 13.7%. So card 0 is for EVAL and card 1 is for TRAINING, which is the
# reverse of what stability alone suggested.
#
# Why a waiter rather than launching by hand: the windows are long but their starts are not
# predictable, and a 600k cell launched into a momentary vacancy dies -- twice today, once at 41%
# and once eight minutes in.
#
# THE DUPLICATE HAZARD IS THE REASON THIS IS WRITTEN CAREFULLY. An armed-and-forgotten
# `ibac-waiter.sh` fired fifteen seconds before a deliberate launch earlier today and put two 600k
# cells on one 16-core host; neither errored, and the only symptom was halved throughput. So:
#   - refuses to start if another waiter or a production launcher is already running,
#   - refuses if a result for this exact tag already exists,
#   - launches AT MOST ONCE and exits, rather than looping,
#   - resolves PIDs from /proc/<pid>/cmdline argv[1], never `pgrep -f`, which matches its own shell.
set -uo pipefail
CARD="${CARD:-1}"; NEED="${NEED:-15000}"; HOLD="${HOLD:-10}"; POLL="${POLL:-60}"
FAMILY="${FAMILY:?}"; BASELINE="${BASELINE:?}"; SEED="${SEED:?}"; CAP="${CAP:-12000}"
MAXWAIT="${MAXWAIT:-43200}"
TAG="$BASELINE-s$SEED-prod"; A="$HOME/rlvigen-runs/prod-v214"; LOG="$A/$TAG-waiter.log"
mkdir -p "$A"
say(){ echo "$(date -Is) $*" >> "$LOG"; }

real_pids(){ for p in $(pgrep -f "$1" 2>/dev/null); do
  a=$(tr "\0" "\n" < "/proc/$p/cmdline" 2>/dev/null | sed -n 2p)
  case "$a" in *"$1") echo "$p";; esac
done; }

# [Claude 2026-09-16] v2. v1 REFUSED ITSELF. It excluded only $$ from the match, but the script
# appears twice in the process table -- itself and the `setsid bash` wrapper that started it -- so
# one of its own processes always survived the filter and looked like a competing waiter. Exclude
# this whole process group: $$, $PPID, and anything whose process-group id is ours.
# [Claude 2026-09-16] v3. v1 and v2 both REFUSED THEMSELVES. Every scheme that identifies "another
# instance" by scanning the process table for its own script name has to then exclude itself, and
# both attempts got that wrong -- the script appears more than once (itself, and the `setsid bash`
# that started it), and excluding $$ or the process group missed a case each time.
#
# flock is the tool for this. It is atomic, it cannot match itself, and the lock dies with the
# process holding it, so a killed waiter leaves nothing to clean up. The process-table scan remains
# only for the OTHER script -- train-production-cell-v5.sh -- where there is no self to exclude.
exec 9>"$HOME/rlvigen-runs/.wait-and-train.lock"
flock -n 9 || { say "REFUSING: another waiter holds the lock. One launcher at a time."; exit 3; }

for p in $(real_pids train-production-cell-v5.sh); do
  say "REFUSING: train-production-cell-v5.sh already running (pid $p). One launcher at a time."
  exit 3
done
[ -f "$A/$TAG-result.tgz" ] && { say "REFUSING: $A/$TAG-result.tgz exists; nothing to launch."; exit 0; }

say "waiting for card $CARD capacity >= ${NEED} MiB sustained ${HOLD} polls (${POLL}s each), max ${MAXWAIT}s"
started=$(date +%s); streak=0
while :; do
  now=$(date +%s); [ $((now-started)) -ge "$MAXWAIT" ] && { say "GAVE UP after ${MAXWAIT}s without a window"; exit 4; }
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
  case "$free" in ''|*[!0-9]*) sleep "$POLL"; continue;; esac
  if [ "$free" -ge "$NEED" ]; then streak=$((streak+1)); else
    [ "$streak" -gt 0 ] && say "window broke at ${free} MiB after ${streak} poll(s)"
    streak=0
  fi
  [ $((streak % 5)) -eq 0 ] && [ "$streak" -gt 0 ] && say "streak ${streak}/${HOLD} at ${free} MiB free"
  if [ "$streak" -ge "$HOLD" ]; then
    say "WINDOW HELD: ${free} MiB free for ${HOLD} polls. Launching $TAG on card $CARD."
    env CARD="$CARD" YIELD_PROCS=1 FAMILY="$FAMILY" BASELINE="$BASELINE" SEED="$SEED" \
        EXPECT_OURS="${EXPECT_OURS:-20}" \
        bash "$HOME/rlvigen-work/train-production-cell-v5.sh" >> "$LOG" 2>&1 &
    launcher=$!
    say "launcher pid $launcher; arming the self-cap once the container appears"
    for _ in $(seq 1 40); do
      c=$(docker ps --format '{{.Names}}' | grep -E "^cell-c${CARD}-[0-9]+\$" | head -1)
      [ -n "$c" ] && break
      sleep 3
    done
    if [ -n "${c:-}" ]; then
      nohup setsid bash "$HOME/rlvigen-work/self-vram-cap.sh" "$c" "$CARD" "$CAP" \
        "$HOME/rlvigen-runs/self-vram-cap-$TAG.log" >/dev/null 2>&1 &
      say "self-vram-cap armed on $c at ${CAP} MiB"
    else
      say "WARNING: no container appeared; cap NOT armed"
    fi
    wait "$launcher"
    say "launcher exited rc=$?; waiter is done, it launches at most once"
    exit 0
  fi
  sleep "$POLL"
done
