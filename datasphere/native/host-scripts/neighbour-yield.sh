#!/usr/bin/env bash
# Yield card 0 to a REAL neighbour -- including a small one the 4000 MiB floor cannot see --
# without ever killing our own run on a misread.
#
# Ownership is by PID, not by count: `docker top` on OUR OWN containers lists exactly our
# processes, and --yield-on-processes is unusable here because our interpreter count is not
# knowable in advance (eval, checkpoint saving and dataloader workers all spawn more, at times
# this watcher cannot predict).
#
# THE ASYMMETRY THAT SHAPES THIS SCRIPT. Failing to yield costs a neighbour some time. Yielding by
# mistake costs us a whole cell. So every ambiguity resets the counter instead of advancing it:
#   - a docker command that fails or returns nothing while our containers exist -> UNKNOWN, reset;
#   - our own containers gone -> stand down, never yield;
#   - a PID seen on the card but not yet in docker top (it started between the two snapshots)
#     -> next pass includes it, foreign set empties, reset.
# Only a foreign PID present on SIX CONSECUTIVE passes (3 minutes) writes the sentinel. A genuine
# neighbour is still yielded to promptly; a transient or a race never is.
#
# Acting = writing the same sentinel yield_gpu_to_neighbour.py writes: the CELL stops itself and
# checkpoints already on the bind mount survive. No `ps`, no other user's containers inspected.
set -uo pipefail
WORK="${1:?usage: neighbour-yield.sh <native-work dir>}"
SENTINEL="$WORK/yield.sentinel"
STRIKES_NEEDED=6
strikes=0

our_pids () {                       # every container we own, whatever its role
  local names
  names="$(docker ps --format '{{.Names}}' 2>/dev/null \
           | grep -E '^(cell-c0-|rlvigen-)' || true)"
  [[ -z "$names" ]] && return 1
  local any=0
  while read -r c; do
    [[ -z "$c" ]] && continue
    local pids
    pids="$(docker top "$c" -eo pid 2>/dev/null | tail -n +2 || true)"
    [[ -n "$pids" ]] && { printf '%s\n' $pids; any=1; }
  done <<< "$names"
  [[ $any -eq 1 ]]
}

while :; do
  if ! mapfile -t ours < <(our_pids); then ours=(); fi
  if [[ ${#ours[@]} -eq 0 ]]; then
    if [[ -z "$(docker ps -q --filter 'name=cell-c0-' 2>/dev/null)" ]]; then
      echo "$(date +%H:%M:%S) no cell of ours on card 0; standing down"; exit 0
    fi
    echo "$(date +%H:%M:%S) UNKNOWN: our containers exist but docker top gave no pids; strikes reset"
    strikes=0; sleep 30; continue
  fi

  oncard="$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader -i 0 2>/dev/null)" \
    || { echo "$(date +%H:%M:%S) UNKNOWN: nvidia-smi failed; strikes reset"; strikes=0; sleep 30; continue; }

  foreign=()
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    pid="$(awk -F, '{gsub(/ /,"",$1); print $1}' <<< "$line")"
    [[ -z "$pid" ]] && continue
    hit=0
    for mine in "${ours[@]}"; do [[ "$pid" == "$mine" ]] && { hit=1; break; }; done
    [[ $hit -eq 0 ]] && foreign+=("$line")
  done <<< "$oncard"

  if [[ ${#foreign[@]} -gt 0 ]]; then
    strikes=$((strikes+1))
    echo "$(date +%H:%M:%S) FOREIGN on card 0 (strike $strikes/$STRIKES_NEEDED), ours=${#ours[@]} pids:"
    printf '    %s\n' "${foreign[@]}"
    if [[ $strikes -ge $STRIKES_NEEDED ]]; then
      echo "$(date +%H:%M:%S) YIELDING: card 0 held by another party for $((STRIKES_NEEDED*30))s."
      printf 'yielded at %s: foreign on card 0: %s\n' "$(date +%s)" "${foreign[*]}" > "$SENTINEL"
      exit 0
    fi
  else
    [[ $strikes -gt 0 ]] && echo "$(date +%H:%M:%S) card 0 ours alone again; strikes reset"
    strikes=0
  fi
  sleep 30
done
