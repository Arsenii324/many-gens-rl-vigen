#!/usr/bin/env bash
# Evaluate every retained checkpoint of a run, several cells at a time.
#
# [Claude 2026-09-15] A real curve needs ONE CELL PER STAMP: run_offline_eval takes a single
# --snapshot, so a "curve mode" that passes the terminal checkpoint only re-scores the endpoint at
# a shallower depth. 13 stamps for ppg, 12 for idaac.
#
# They pack, and that is measured rather than hoped: one eval cell uses 101% CPU (one core),
# 841 MiB of VRAM and 2.1 GiB of RAM, on a 16-core node at load ~8 with ~16 GB free on the card.
# Running them one at a time would spend the booking at a sixteenth of the machine.
#
# CONCURRENCY is the whole safety story here, so it is a hard gate rather than a hope: the loop
# counts OUR OWN cell containers and refuses to start another until the count drops. It also
# re-checks free VRAM and free disk before each launch, because the node is shared and a colleague
# may grow at any time. The owner's standing rule is absolute -- never CUDA OOM, including spikes,
# including other people's jobs -- and our per-process cap does NOT bind (PYTHONPATH is overwritten
# by every family launcher), so headroom is the only real protection we have.
set -uo pipefail
FAMILY="${FAMILY:?}"; BASELINE="${BASELINE:?}"; SEED="${SEED:?}"; CKPT_DIR="${CKPT_DIR:?}"
CARD="${CARD:-1}"          # [Claude 2026-09-15] the card is a parameter: card 1 filled up when a
                           # colleague grew to 21 GB, while card 0 still had 6.4 GB free. A sweep
                           # pinned to one card idles while the other card is usable.
MAXCELLS="${MAXCELLS:-6}"; MIN_FREE_MIB="${MIN_FREE_MIB:-6000}"; MIN_FREE_GIB="${MIN_FREE_GIB:-100}"
LOG="$HOME/rlvigen-runs/curve-sweep-$BASELINE-c$CARD.log"
say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }

mapfile -t STAMPS < <(ls "$CKPT_DIR" 2>/dev/null | grep -E '\.(pt|jd|msgpack)$' | sort)
say "sweep start: ${#STAMPS[@]} stamps for $BASELINE from $CKPT_DIR (max $MAXCELLS cells)"

frame_of() {   # ppg names by save index; everyone else carries the frame in the filename
  local f="$1"
  if [[ "$FAMILY" == "ppg" ]]; then
    local idx; idx="$(echo "$f" | grep -oE '[0-9]+' | tail -1 | sed 's/^0*//')"; idx="${idx:-0}"
    grep 'Saving to .*IC=' "$PPG_TRAIN_LOG" 2>/dev/null | grep -oE 'IC=[0-9]+' | cut -d= -f2 | sed -n "$((idx+1))p"
  else
    echo "$f" | grep -oE '[0-9]+' | tail -1
  fi
}

for f in "${STAMPS[@]}"; do
  frame="$(frame_of "$f")"
  if [[ -z "$frame" ]]; then say "SKIP $f -- frame unmappable, refusing to label a measurement with a guess"; continue; fi
  tag="$BASELINE-s$SEED-curve-$frame"
  [[ -f "$HOME/rlvigen-runs/reeval-v214/$tag-result.tgz" ]] && { say "SKIP $tag (result present)"; continue; }

  while :; do
    ours=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cE "^cell-c${CARD}-[0-9]+$")
    freemib=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
    freegib=$(df -Pk "$HOME" | awk 'NR==2{printf "%d", $4/1048576}')
    if (( ours < MAXCELLS )) && (( ${freemib:-0} > MIN_FREE_MIB )) && (( ${freegib:-0} > MIN_FREE_GIB )); then break; fi
    say "waiting: cells=$ours/$MAXCELLS vram_free=${freemib}MiB disk_free=${freegib}GiB"
    sleep 120
  done

  # [Claude 2026-09-16] STAGE THE STAMP UNDER A COLON-FREE NAME. idaac writes
  # `agent-robosuite:Door-idaac-s101_200704.pt`, and EXTRA_MOUNT_1 is parsed as
  # host:container:ENVVAR -- so the colon inside the FILENAME truncated the path at
  # "agent-robosuite" and every idaac stamp died with
  # "EXTRA_MOUNT_1 names a missing file". ppg was unaffected only because its stamps are
  # model000.jd. Copy, do not symlink: the mount resolves on the host side and a link would
  # point back at the colon.
  STAGE="$HOME/rlvigen-runs/stamp-staging"; mkdir -p "$STAGE"
  staged="$STAGE/${BASELINE}-s${SEED}-${frame}$([[ "$f" == *.jd ]] && echo .jd || echo .pt)"
  if [[ ! -f "$staged" ]]; then
    cp "$CKPT_DIR/$f" "$staged" || { say "SKIP $tag -- could not stage $f"; continue; }
  fi
  say "launching $tag (frame=$frame, file=$f, staged as $(basename "$staged"))"
  FAMILY="$FAMILY" BASELINE="$BASELINE" SEED="$SEED" FRAME="$frame" TAG="$tag" \
    SNAP="$staged" EXPECT_OURS="$MAXCELLS" TIMEOUT_S=3600 ALLOWANCE_S=14400 CARD="$CARD" \
    nohup setsid bash "$HOME/rlvigen-work/reeval-cell.sh" curve >> "$LOG" 2>&1 &
  sleep 90    # let the launcher take its slot before the next occupancy count
done
say "sweep dispatched all stamps"
