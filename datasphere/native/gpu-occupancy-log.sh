#!/usr/bin/env bash
# Append one line per card per minute to a log THAT OUTLIVES THE SSH SESSION.
#
# [Claude 2026-09-14] Three monitors died this session without reporting anything, because each
# was a loop held open by a persistent ssh connection: kill the local task and the remote loop dies
# with it, leaving no verdict, no history, and no evidence it had ever run. A watcher whose death
# is indistinguishable from silence is not a watcher.
#
# This runs DETACHED on the host and writes its own file. Two consequences that the ssh version
# could not offer:
#   - the log is readable at any time, so occupancy becomes HISTORY rather than an edge trigger --
#     "was card 0 ever free in the last six hours" is answerable after the fact;
#   - a GAP in the timestamps is positive evidence the logger died, which is exactly what was
#     missing when the ssh monitors were killed.
#
# Bash, docker and nvidia-smi only. No python, no pip, no apt, nothing host-wide: the standing rule
# for this host is docker operations and trivial shell. It reads; it never stops anything.
set -uo pipefail
LOG="${1:-$HOME/rlvigen-runs/gpu-occupancy.log}"
INTERVAL="${GPU_LOG_INTERVAL:-60}"
HOURS="${GPU_LOG_HOURS:-24}"

# One logger at a time, via flock rather than pgrep.
#
# [Claude 2026-09-14] The first version used `pgrep -f gpu-occupancy-log.sh` and refused to start
# EVERY time: the ssh command that launches it has the script name in its own command line, so the
# guard matched the launching shell and exited 3 before writing a byte. The log file was never
# created, and a `pgrep | wc -l` of 1 looked like "the logger is running" when it was counting that
# same shell. A guard that matches itself is the same defect as a check that cannot fail.
#
# flock holds a real kernel lock on a real file: it cannot match a command line, and it releases
# automatically when the holder dies, so a killed logger leaves no stale lock to clear by hand.
LOCK="${GPU_LOG_LOCK:-$HOME/.gpu-occupancy-log.lock}"
exec 9>"$LOCK" || { echo "cannot open lock $LOCK" >&2; exit 3; }
if ! flock -n 9; then
  echo "another logger holds $LOCK; not starting a second" >&2
  exit 3
fi

holder_of() {                      # container name owning a pid, or "-" when not ours to name
  local pid="$1" cg nm
  cg="$(grep -oE 'docker[-/][0-9a-f]{12}' "/proc/$pid/cgroup" 2>/dev/null | head -1 | grep -oE '[0-9a-f]{12}')"
  [[ -z "$cg" ]] && { printf '%s' "no-container"; return; }
  nm="$(docker ps --format '{{.ID}} {{.Names}}' 2>/dev/null | awk -v c="$cg" '$1==substr(c,1,12){print $2}')"
  printf '%s' "${nm:-id:$cg}"
}

printf '# gpu-occupancy-log started %s interval=%ss hours=%s\n' "$(date -Is)" "$INTERVAL" "$HOURS" >> "$LOG"
end=$(( SECONDS + HOURS * 3600 ))
while (( SECONDS < end )); do
  now="$(date -Is)"
  for c in 0 1; do
    mem="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$c" 2>/dev/null)"
    util="$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -i "$c" 2>/dev/null)"
    pids="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$c" 2>/dev/null)"
    n="$(printf '%s' "$pids" | grep -c . )"
    holders=""
    for p in $pids; do holders="${holders:+$holders,}$(holder_of "$p")"; done
    printf '%s card=%s mem=%s util=%s procs=%s holders=%s\n' \
      "$now" "$c" "${mem:-?}" "${util:-?}" "$n" "${holders:--}" >> "$LOG"
  done
  sleep "$INTERVAL"
done
printf '# gpu-occupancy-log exited cleanly %s\n' "$(date -Is)" >> "$LOG"
