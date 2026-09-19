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
#   * count a streak across a logger outage — samples more than MAX_SAMPLE_GAP apart are a
#     different window, however clear each one looks on its own (found 2026-09-20);
#   * hold the lock silently: everything it decides goes to its log with a timestamp.
#
# It never stops, kills or deletes anything. The only thing it starts is train-production-cell-v5.sh,
# and after that the self-cap watcher for the container that appears.
#
# WHAT IT DOES NOT DO, and somebody has to: it does not record the attempt. `record_host_run.py` and
# the attempt ledger live on the laptop, and `audit_attempt_ledger.py --strict` fails later on a run
# with no terminal status. So when this waiter launches, fetch the cell's effective_config.json and
# record it (OPERATOR-GUIDE §5.2), and arm `watch-cell.sh` -- this script watches the CARD, not the
# cell it started.
set -uo pipefail
CARD="${CARD:-1}"
FAMILY="${FAMILY:?set FAMILY}"; BASELINE="${BASELINE:?set BASELINE}"; SEED="${SEED:?set SEED}"
NEED="${NEED:-11421}"        # ibac_sni's 7,421 peak + the 4,000 MiB floor: the largest cell we run
HOLD="${HOLD:-10}"           # ten one-minute samples; ten of twelve past absences were restarts
POLL="${POLL:-60}"
# How far apart two counted samples may be before they no longer count as one streak. Default is
# three LOGGER intervals (gpu-occupancy-log.sh writes every 60 s) -- generous enough for an occasional
# missed write, not for a real outage. Deliberately NOT derived from POLL: POLL is how often this
# waiter looks, not how often the log is written, and POLL=10 would make every sample a "gap".
# See clear_streak() for why this exists.
MAX_SAMPLE_GAP="${MAX_SAMPLE_GAP:-180}"
MAXWAIT="${MAXWAIT:-43200}"
MIN_DISK_GIB="${MIN_DISK_GIB:-60}"
VRAM_MIB="${VRAM_MIB:-5000}"
EXPECT_OURS="${EXPECT_OURS:-20}"
LOG_MAX_AGE="${LOG_MAX_AGE:-180}"
OCC="${OCC:-$HOME/rlvigen-runs/gpu-occupancy.log}"
A="$HOME/rlvigen-runs/prod-v214"; TAG="$BASELINE-s$SEED-prod"
LOG="${WAITER_LOG:-$A/$TAG-waiter-v4.log}"
# WHICH wrapper it launches. Default v5, because that is the script every completed cell on this
# host went through and idaac s103 should not be the run that tries something new. A Places365
# baseline needs v6, which adds PAYLOAD and PLACES365_DIR and nothing else; pass WRAPPER for that.
WRAPPER="${WRAPPER:-train-production-cell-v5.sh}"
# Host RAM, which NOTHING else checks. launch-card-cell.sh gates VRAM and disk; the co-tenant's
# RAM is invisible to both. An RL-ViGen cell is ~40 GiB resident (36.7 GiB of replay at the v100
# cap plus a 3.3 GiB peak) on a 125 GiB host that already had 43 GiB in use on 2026-09-18, so a
# cell of that family started at the wrong moment can push the kernel OOM killer into choosing a
# victim -- possibly the co-tenant's. That is the one outcome the standing rule forbids outright.
# Default 0 (off), so the families that have already run keep exactly the behaviour they ran with;
# pass MIN_RAM_GIB for a family whose resident set is large.
MIN_RAM_GIB="${MIN_RAM_GIB:-0}"
# Re-arming after a launch that died in its first minutes. OFF by default, and the default is the
# behaviour every armed waiter so far has run with: launch once, then exit.
#
# Why it is wanted at all: on 2026-09-17 a cell died 24 s in with `EGL_NOT_INITIALIZED`, the card
# stayed clear for the rest of the night, and nothing used it -- the waiter had already exited. The
# window is the scarcest thing in this campaign (free once in thirteen hours), so throwing one away
# over a 24-second failure is the most expensive mistake available.
#
# Why it is off by default, and bounded when on: a retry is an unattended relaunch. It is confined
# to failures inside FAST_FAILURE_SECONDS, because a cell that ran for hours and then failed has a
# partial run on disk, and relaunching over it from zero without a human looking is not a decision
# a waiter should make. MAX_RETRIES bounds a crash loop: three identical EGL deaths in a row are a
# broken configuration, not a bad moment.
RETRY_FAST_FAILURES="${RETRY_FAST_FAILURES:-0}"
FAST_FAILURE_SECONDS="${FAST_FAILURE_SECONDS:-600}"
MAX_RETRIES="${MAX_RETRIES:-2}"
CELL_WAIT_TRIES="${CELL_WAIT_TRIES:-60}"   # x5s = 300s for the container to appear
mkdir -p "$A"
say(){ echo "$(date -Is) $*" >> "$LOG"; }

# How many of the last HOLD samples for this card were CLEAR: no foreign holder, and NEED free.
# Identical rule to host-scripts/capacity-check.sh, which was validated against two known moments.
#
# [Claude 2026-09-20] A STREAK is samples close together in TIME, not just individually clear.
# Found live: the host crashed at 21:25 on 2026-09-19, the logger restarted at 01:02 on 2026-09-20,
# and three minutes later a DRYRUN replay printed "streak 10/10" built from seven pre-crash lines
# (21:16-21:22) plus three fresh ones -- the "ten CONSECUTIVE one-minute samples" rule had silently
# become a "any ten samples, however far apart" rule. The only staleness guard, LOG_MAX_AGE, looks
# only at the age of the LAST line, which a fresh restart always satisfies; it says nothing about
# what came before that line. Fixed here by walking the tail forward and keeping only the trailing
# run whose consecutive gaps are all <= MAX_SAMPLE_GAP -- everything before the first wider gap
# belongs to a different window and does not count, exactly as if it had never been logged.
#
# [Claude 2026-09-20, same day] A sample `date -d` cannot parse is NOT a free pass. The first cut
# of this fix let an unparsable timestamp fall through with epoch="", which simply skipped the gap
# comparison -- so a logger whose format ever changed (or a host whose `date` behaves differently)
# would silently go back to counting individually-clear samples with no regard for time at all, the
# exact defect above. A timestamp that cannot be placed in time cannot prove its sample belongs to
# the current window, so it is treated the same as a hard gap: nothing at or before it counts.
clear_streak(){
  local as_of="${1:-}"
  local lines
  if [ -n "$as_of" ]; then
    lines=$(grep "card=$CARD " "$OCC" | awk -v t="$as_of" 'substr($1,1,16) <= t' | tail -"$HOLD")
  else
    lines=$(grep "card=$CARD " "$OCC" | tail -"$HOLD")
  fi
  local -a arr=()
  while IFS= read -r line; do [ -n "$line" ] && arr+=("$line"); done <<< "$lines"
  local start=0 i epoch prev_epoch="" reset_msg=""
  for (( i=0; i<${#arr[@]}; i++ )); do
    epoch=$(date -d "${arr[i]%% *}" +%s 2>/dev/null)
    if [ -z "$epoch" ]; then
      start=$(( i + 1 ))
      reset_msg="cannot parse the timestamp of sample $i ('${arr[i]%% *}'); samples up to it do not count"
    elif [ -n "$prev_epoch" ] && [ $(( epoch - prev_epoch )) -gt "$MAX_SAMPLE_GAP" ]; then
      start=$i
      reset_msg="a gap > ${MAX_SAMPLE_GAP}s separates sample $start from sample $((start - 1)) of ${#arr[@]}; only the trailing $(( ${#arr[@]} - start )) sample(s) count"
    fi
    prev_epoch="$epoch"
  done
  if [ "$start" -gt 0 ]; then
    say "streak reset: $reset_msg"
  fi
  local trimmed="" j
  for (( j=start; j<${#arr[@]}; j++ )); do trimmed="$trimmed${arr[j]}"$'\n'; done
  printf '%s' "$trimmed" | awk -v need="$NEED" -v total="${TOTAL:-32768}" '
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
#
# [Claude 2026-09-18, an hour later] The same trap bit THIS script: after `kill`ing the waiter, its
# own `sleep` child still held fd 9 and the replacement refused for a minute. Every long-lived child
# below therefore gets `9>&-`, which closes the descriptor for it. That includes the launcher, so
# v4's lock is released when v4 exits rather than when the cell's watch budget ends.
# WAITER_LOCK exists so the guards below can be TESTED while a real waiter is armed: with one
# hardcoded path, every test run refused at the lock and reached none of the branches it meant to
# exercise -- a test that cannot fail for the right reason, which is this project's recurring defect.
exec 9>"${WAITER_LOCK:-$HOME/rlvigen-runs/.wait-and-train-v4.lock}"
flock -n 9 || { say "REFUSING: another v4 waiter holds the lock. One launcher at a time."; exit 3; }
for p in $(pgrep -f "train-production-cell-v[56].sh|wait-and-train-v3.sh" 2>/dev/null); do
  say "REFUSING: a launcher is already running (pid $p)."; exit 3
done
if [ -f "$A/$TAG-result.tgz" ]; then say "REFUSING: $A/$TAG-result.tgz exists; nothing to launch."; exit 0; fi

# Validate what the launch will need NOW, not in ten hours. Before this, a mistyped WRAPPER or a
# missing payload waited out the whole window and then failed at the instant of launch -- which
# costs the scarcest thing here, since the card was free once in thirteen hours.
[ -f "$HOME/rlvigen-work/$WRAPPER" ] || { say "REFUSING: no wrapper at ~/rlvigen-work/$WRAPPER"; exit 2; }
if [ -n "${PAYLOAD:-}" ] && [ ! -f "$PAYLOAD" ]; then say "REFUSING: PAYLOAD=$PAYLOAD does not exist"; exit 2; fi
if [ -n "${PLACES365_DIR:-}" ] && [ ! -d "$PLACES365_DIR" ]; then say "REFUSING: PLACES365_DIR=$PLACES365_DIR is not a directory"; exit 2; fi
say "will launch $TAG via $WRAPPER${PAYLOAD:+ with $(basename "$PAYLOAD")}${PLACES365_DIR:+ + places365}${MIN_RAM_GIB:+, RAM floor ${MIN_RAM_GIB} GiB}"

say "waiting for card $CARD: no foreign holder and >= ${NEED} MiB free for ${HOLD} samples; max ${MAXWAIT}s"
started=$(date +%s); last=""; polls=0; retries=0
# A heartbeat, because this runs unattended for hours: without one the log only moves when the
# state changes, and "quiet because nothing changed" reads exactly like "dead". Every HEARTBEAT
# polls it says what it sees, whatever that is.
HEARTBEAT="${HEARTBEAT:-15}"
while :; do
  now=$(date +%s); polls=$((polls+1))
  if [ $((now-started)) -ge "$MAXWAIT" ]; then say "GAVE UP after ${MAXWAIT}s without a window"; exit 4; fi

  age=$(( now - $(stat -c %Y "$OCC" 2>/dev/null || echo 0) ))
  if [ "$age" -gt "$LOG_MAX_AGE" ]; then
    say "BLIND: $OCC is ${age}s stale, so a co-tenant would be invisible. Not launching. Restart gpu-occupancy-log.sh."
    sleep "$POLL" 9>&-; continue
  fi

  if docker ps --format '{{.Names}}' | grep -qE "^cell-c[0-9]+-[0-9]+$"; then
    say "HOLDING: a cell container of ours is already running."
    sleep "$POLL" 9>&-; continue
  fi

  n="$(clear_streak)"
  if [ "$n" != "${last%%:*}" ] || [ $((polls % HEARTBEAT)) -eq 0 ]; then
    say "streak ${n}/${HOLD} (log ${age}s old, poll ${polls}, $(( (now-started)/60 )) min waited)"
    last="$n:$age"
  fi
  if [ "$n" -lt "$HOLD" ]; then sleep "$POLL" 9>&-; continue; fi

  # final checks at the instant of launch, not from a sample a minute old
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
  case "$free" in ''|*[!0-9]*) say "nvidia-smi gave no number; waiting"; sleep "$POLL" 9>&-; continue;; esac
  if [ "$free" -lt "$NEED" ]; then say "window evaporated at the last check: ${free} MiB free"; sleep "$POLL" 9>&-; continue; fi
  disk=$(df -Pk "$HOME" | awk 'NR==2{printf "%d", $4/1048576}')
  if [ "$disk" -lt "$MIN_DISK_GIB" ]; then say "REFUSING: ${disk} GiB free, below MIN_DISK_GIB=${MIN_DISK_GIB}"; sleep "$POLL" 9>&-; continue; fi
  if [ "$MIN_RAM_GIB" -gt 0 ]; then
    ram=$(free -g | awk 'NR==2{print $7}')
    if [ "${ram:-0}" -lt "$MIN_RAM_GIB" ]; then
      say "REFUSING: ${ram} GiB RAM available, below MIN_RAM_GIB=${MIN_RAM_GIB}. Starting a large cell"
      say "  here risks the kernel OOM killer choosing a co-tenant's process. Waiting instead."
      sleep "$POLL" 9>&-; continue
    fi
  fi

  say "WINDOW HELD: ${n}/${HOLD} clear samples, ${free} MiB free, ${disk} GiB disk, ${ram:-n/a} GiB RAM. Launching $TAG on card $CARD via $WRAPPER."
  if [ "${DRYRUN:-0}" = "1" ]; then say "DRYRUN=1 -- stopping here, nothing launched."; exit 0; fi

  [ -f "$A/$TAG-prod.log" ] && cp -p "$A/$TAG-prod.log" "$A/$TAG-prod-previous-$(date +%Y%m%d-%H%M).log"
  launch_at=$(date +%s)
  env CARD="$CARD" YIELD_PROCS=1 FAMILY="$FAMILY" BASELINE="$BASELINE" SEED="$SEED" \
      EXPECT_OURS="$EXPECT_OURS" VRAM_MIB="$VRAM_MIB" \
      bash "$HOME/rlvigen-work/$WRAPPER" >> "$LOG" 2>&1 9>&- &
  launcher=$!
  say "launcher pid $launcher; waiting for the cell container to arm the self-cap"
  # Reset per attempt. With the retry branch below, a stale `c` from a previous attempt would arm a
  # second self-cap watcher on a container that is already gone.
  c=""
  for _ in $(seq 1 "$CELL_WAIT_TRIES"); do
    c=$(docker ps --format '{{.Names}}' | grep -E "^cell-c${CARD}-[0-9]+\$" | head -1)
    [ -n "$c" ] && break
    sleep 5 9>&-
  done
  if [ -n "${c:-}" ]; then
    nohup setsid bash "$HOME/rlvigen-work/self-vram-cap.sh" "$c" "$CARD" "$VRAM_MIB" \
      "$HOME/rlvigen-runs/self-vram-cap-$BASELINE-s$SEED.log" >/dev/null 2>&1 9>&- &
    say "self-cap armed on $c at ${VRAM_MIB} MiB"
  else
    say "NO CELL CONTAINER appeared within $((CELL_WAIT_TRIES*5))s -- check $A/$TAG-prod.log; no self-cap armed"
  fi
  wait "$launcher"; rc=$?
  ran=$(( $(date +%s) - launch_at ))
  say "launcher exited rc=$rc after ${ran}s"
  if [ "$RETRY_FAST_FAILURES" = "1" ] && [ "$rc" -ne 0 ] \
     && [ "$ran" -lt "$FAST_FAILURE_SECONDS" ] && [ "$retries" -lt "$MAX_RETRIES" ]; then
    retries=$((retries+1))
    say "fast failure (ran ${ran}s < ${FAST_FAILURE_SECONDS}s). RETRY_FAST_FAILURES=1: retry ${retries}/${MAX_RETRIES}."
    say "  The card may still be clear; the streak rule below decides, exactly as it did the first time."
    sleep "$POLL" 9>&-
    continue
  fi
  if [ "$RETRY_FAST_FAILURES" = "1" ] && [ "$rc" -ne 0 ] && [ "$ran" -ge "$FAST_FAILURE_SECONDS" ]; then
    say "  not a fast failure: it ran ${ran}s, so a partial run exists. A human decides what happens to it."
  fi
  say "this waiter is done"
  exit 0
done
