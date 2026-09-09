#!/usr/bin/env bash
# Launch one cell on one GPU card, with the exclusivity and yield watches sized to actually cover it.
#
#     CARD=0 CELLS=idaac:101 FRAMES=10000 CELL_TIMEOUT_SECONDS=3600 \
#       bash datasphere/native/launch-card-cell.sh ~/payload.tgz ~/runs/result.tgz
#
# Run it DETACHED. `run_on_production_host.sh` is foreground and blocking, so an SSH drop sends
# SIGHUP and kills this script before its stand-down steps -- dockerd keeps the cell container
# alive, but nothing stops the watchers and nothing reports the result:
#
#     nohup bash datasphere/native/launch-card-cell.sh ... > run.log 2>&1 &
#
# [Claude 2026-09-08] This file exists because the launch it replaces was typed by hand, and the
# number that mattered was guessed. Both card watches were armed for 4500s against an assumed ~10
# minute bootstrap. The real bootstrap was still downloading 51 minutes in, against a 4500s (75
# minute) watch -- the production host pulls the torch CUDA
# stack at 162-835 kB/s, and `nvidia_cublas_cu12` alone took 14m15s -- so the watches would have stood
# down at 21:29 and the cell would have reached the GPU at ~22:25. The entire GPU phase, the only
# part where exclusivity and yielding mean anything, would have run unwatched, and both instruments
# would have exited 0 on the way out.
#
# Nothing here is cleverer than that arithmetic; it just does it in code, from one declared cell
# timeout and one bootstrap allowance, and passes the result to `--must-cover-seconds` so the
# watchers refuse rather than arm short. The card index is derived once, too: it was previously
# typed three times (--gpus, and --device on each watcher) with nothing checking they agreed.
set -uo pipefail

PAYLOAD="${1:?usage: launch-card-cell.sh <payload.tgz> <result.tgz>}"
RESULT="${2:?usage: launch-card-cell.sh <payload.tgz> <result.tgz>}"
CARD="${CARD:?set CARD to the GPU index this cell may use}"
CELLS="${CELLS:?set CELLS, e.g. idaac:101}"
CELL_TIMEOUT_SECONDS="${CELL_TIMEOUT_SECONDS:?set CELL_TIMEOUT_SECONDS; the watch budget is derived from it}"

# How long the bootstrap may take before the cell touches the GPU. Measured 2026-09-08 on the
# production host WITHOUT a wheel cache: ~2h, essentially all of it downloading the torch CUDA
# stack. With NATIVE_PIP_CACHE_HOST set and warm this collapses to minutes -- but the allowance is
# what the watch is SIZED against, so it stays pessimistic on purpose. Over-covering costs an idle
# poll every 20s; under-covering costs the watch.
# [Claude 2026-09-08] The default is 9000s because that is what an unprepared cell costs: `pip`
# ran past two hours on 2026-09-08. With NATIVE_VENV_HOST pointing at a prebuilt environment there
# is no pip at all -- only `apt`, measured at 71 seconds -- so the allowance collapses and the whole
# watch budget with it. Derived from which path is in use rather than left to be remembered, because
# an allowance sized for the slow path silently over-covers and one sized for the fast path silently
# under-covers, and the second is the dangerous direction.
if [[ -n "${NATIVE_VENV_HOST:-}" ]]; then
  BOOTSTRAP_ALLOWANCE="${NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS:-600}"
else
  BOOTSTRAP_ALLOWANCE="${NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS:-9000}"
fi
# How many compute processes OUR cell legitimately puts on the card. One, for every family:
# checked 2026-09-08 across `runnable/` for SubprocVecEnv, AsyncVectorEnv, torch.multiprocessing
# and mp.set_start_method -- the only hit is `runnable/alda/scripts/train.py:116`, commented out.
# idaac reaches the card through DummyVecEnv/ProcgenEnv, both in-process. It is a variable rather
# than a literal because the exclusivity watch reads a FALSE BREACH as a real one, so a family that
# later grows a worker pool must be able to say so instead of being argued with.
# One process per CELL, so a packed run expects as many as it packs. Derived from the CELLS list
# rather than typed, because the first packed run yielded to itself: two cells put two processes on
# the card, the watchers expected one, and both healthy cells were stopped as if a co-tenant had
# arrived. Serial runs (NATIVE_CONCURRENT unset) execute one cell at a time, so they expect one.
if [[ "${NATIVE_CONCURRENT:-}" == "1" ]]; then
  _cell_count="$(printf '%s' "$CELLS" | awk -F, '{print NF}')"
else
  _cell_count=1
fi
EXPECT_OURS="${NATIVE_EXPECT_OURS:-$_cell_count}"
SLACK="${NATIVE_WATCH_SLACK_SECONDS:-900}"
MUST_COVER=$(( CELL_TIMEOUT_SECONDS + BOOTSTRAP_ALLOWANCE ))
WATCH_SECONDS=$(( MUST_COVER + SLACK ))

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="${NATIVE_RUN_DIR:-$HOME/rlvigen-runs/card${CARD}-$(date +%Y%m%d-%H%M%S)}"
IMAGE="${NATIVE_HELPER_IMAGE:-python:3.11-slim}"
CELL_NAME="cell-c${CARD}-$$"
EXCL="cell-c${CARD}-exclusivity-$$"
DISK="cell-c${CARD}-disk-$$"
YIELD="cell-c${CARD}-yield-$$"

mkdir -p "$W/native-work" "$W/native-out" "$W/mirror" || exit 2
echo "run dir:        $W"
echo "card:           $CARD"
echo "cells:          $CELLS  (expecting $EXPECT_OURS process(es) of ours)"
echo "cell timeout:   ${CELL_TIMEOUT_SECONDS}s"
echo "bootstrap:      ${BOOTSTRAP_ALLOWANCE}s allowed (${NATIVE_VENV_HOST:+prebuilt env: $NATIVE_VENV_HOST})${NATIVE_VENV_HOST:-, no prebuilt env: this cell will run pip}"
echo "watch budget:   ${WATCH_SECONDS}s (must cover ${MUST_COVER}s, ${SLACK}s slack)"

reaper_pid=""

stand_down() {
  echo "=== STEP 4: stand down"
  [[ -n "$reaper_pid" ]] && kill "$reaper_pid" 2>/dev/null
  docker stop "$EXCL" "$YIELD" "$DISK" >/dev/null 2>&1
  # `--rm` removal is asynchronous after `docker stop` returns, so an immediate check races it and
  # reports a leak that is not one -- observed 2026-09-09. Settle first, then report.
  local leaked=""
  local _i
  for _i in 1 2 3 4 5 6 7 8 9 10; do
    leaked="$(docker ps --filter "name=cell-c${CARD}-" --format '{{.Names}}')"
    [[ -z "$leaked" ]] && break
    sleep 1
  done
  [[ -z "$leaked" ]] && echo "  no watcher leaked" || echo "  LEAKED: $leaked"
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | sed 's/^/  /'
}
trap stand_down EXIT

echo "=== STEP 0: preflight on card $CARD"
docker run --rm -v "$REPO:/repo:ro" -w /repo --gpus "\"device=${CARD}\"" "$IMAGE" \
  python3 scripts/watch_gpu_headroom.py --preflight --device "$CARD" \
    --need-mib "${NATIVE_NEED_MIB:-4000}"
pf=$?
echo "preflight exit=$pf"
[[ $pf -ne 0 ]] && { echo "ABORTING: preflight refused the card."; exit 3; }

# Both watchers observe with `--gpus all` deliberately: nvidia-smi inside a container reports only
# the cards it was given, so an observer restricted to our own card could not see a neighbour on
# another one. It reads counts, never PIDs, and never touches /var/run/docker.sock.
echo "=== STEP 1: exclusivity watch (expects 0 of ours until the cell announces itself)"
docker run -d --rm --name "$EXCL" \
  -v "$REPO:/repo:ro" -v "$W/native-work:/work" -w /repo --gpus all "$IMAGE" \
  python3 scripts/watch_card_exclusivity.py --device "$CARD" --expect-ours "$EXPECT_OURS" \
    --active-file /work/cell-active --stop-when-inactive \
    --max-seconds "$WATCH_SECONDS" --must-cover-seconds "$MUST_COVER" --interval 20 >/dev/null \
  || { echo "ABORTING: the exclusivity watch refused to arm."; exit 4; }

echo "=== STEP 2: yield watch"
docker run -d --rm --name "$YIELD" \
  -v "$REPO:/repo:ro" -v "$W/native-work:/work" -w /repo --gpus all "$IMAGE" \
  python3 scripts/yield_gpu_to_neighbour.py --device "$CARD" --sentinel /work/yield.sentinel \
    --expect-ours "$EXPECT_OURS" \
    --active-file /work/cell-active --stop-when-inactive \
    --max-seconds "$WATCH_SECONDS" --must-cover-seconds "$MUST_COVER" \
    --interval 20 --floor-mib "${NATIVE_FLOOR_MIB:-4000}" >/dev/null \
  || { echo "ABORTING: the yield watch refused to arm."; exit 4; }

sleep 10
for c in "$EXCL" "$YIELD"; do
  if [[ -z "$(docker ps -q --filter "name=$c")" ]]; then
    echo "ABORTING: $c is not running ten seconds after launch. It refused:"
    docker logs "$c" 2>&1 | tail -6
    exit 4
  fi
done
echo "  both armed and alive"

# [Claude 2026-09-08] A HARD BOUND ON THE CONTAINER, not just on the cell inside it.
# CELL_TIMEOUT_SECONDS bounds how long a cell may RUN; it starts when training starts, and nothing
# bounded the bootstrap before it. A cell whose `pip` hangs -- entirely plausible on a link that
# delivers 162-835 kB/s and has to move ~2.5 GB -- would sit in that container indefinitely. The
# only thing that would have stopped it on 2026-09-08 was an outer `timeout` on the SSH connection,
# and that kills the client while dockerd keeps the container alive: the worst of both, an orphan
# nobody is watching on a machine we share.
#
# So the container gets the same budget the watches do. If it is still up when that expires, it has
# already exceeded everything anyone declared for it, and it stops.
(
  sleep "$WATCH_SECONDS"
  if [[ -n "$(docker ps -q --filter "name=^${CELL_NAME}$")" ]]; then
    echo "!! REAPING $CELL_NAME: still running after ${WATCH_SECONDS}s, which is the whole declared" >&2
    echo "!! budget (cell timeout + bootstrap allowance + slack). Artifacts on the bind mounts are" >&2
    echo "!! durable; the container is not." >&2
    docker stop "$CELL_NAME" >/dev/null 2>&1
  fi
) &
reaper_pid="$!"

# [Claude 2026-09-09] DISK WATCH. `run_on_production_host.sh` checks free space ONCE, before the
# container starts, and a cell then writes for hours: pip into the container layer, checkpoints in
# triplicate, Places365 for the families that need it. This filesystem is SHARED and sits at 99%
# used (317 GB free of 20 TB), and that free space is not ours to spend.
#
# The floor is DERIVED, not typed, from two independent concerns, whichever binds first:
#   * our own overconsumption -- free-at-arm minus an allowance of 4x what a cell is estimated to
#     need, so a runaway is caught well before it matters;
#   * the machine itself -- an absolute floor below which nobody should be writing regardless of
#     whose fault it is.
# It stops OUR cell by writing the same sentinel the GPU co-tenancy watch uses. Somebody else's job
# failing because we filled a shared disk is the outcome this exists to prevent, and by the time a
# human reads a warning the space is already gone.
_free_gib="$(df -PBG "$W" 2>/dev/null | awk 'NR==2 {gsub(/G/,"",$4); print $4}')"
# [Claude 2026-09-09] DERIVE the allowance from what this cell actually needs, do not type it.
# `family.py disk-requirement` gives 9 GiB for idaac/ppg at 600k and **48** for drqv2, while this
# defaulted to 40 -- so a drqv2 cell writing what it legitimately needs would breach a floor sized
# for a smaller job and yield partway through a multi-hour run. The allowance is a statement about
# how much this cell may consume, so it has to be at least what the cell needs. Same principle as
# the watch budget: a number that must match the run should be computed from the run.
_need_gib="$(docker run --rm -v "$REPO:/repo:ro" -w /repo "$IMAGE" \
  python3 datasphere/native/family.py disk-requirement --cells "$CELLS" \
    --frames "${FRAMES:-600000}" --profile "${NATIVE_HOST_PROFILE:-datasphere}" --ceil-total \
  2>/dev/null | tr -dc '0-9')"
if [[ -n "$_need_gib" && "$_need_gib" -gt 0 ]]; then
  # Twice the requirement, not 1.5x: the live idaac cell consumed 8.2 GiB against a computed
  # need of 9, so the measured margin between "what family.py predicts" and "what the container
  # layer plus staging actually costs" is thin, and a floor that fires on a healthy cell is worse
  # than one that fires slightly late.
  _derived=$(( _need_gib * 2 ))
  DISK_ALLOWANCE_GIB="${NATIVE_DISK_ALLOWANCE_GIB:-$_derived}"
  echo "disk need:      ${_need_gib} GiB for $CELLS at ${FRAMES:-600000} frames -> allowance ${DISK_ALLOWANCE_GIB} GiB"
else
  DISK_ALLOWANCE_GIB="${NATIVE_DISK_ALLOWANCE_GIB:-40}"
  echo "disk need:      could not be computed; falling back to a ${DISK_ALLOWANCE_GIB} GiB allowance" >&2
fi
DISK_ABS_FLOOR_GIB="${NATIVE_DISK_ABS_FLOOR_GIB:-50}"
if [[ -n "$_free_gib" ]]; then
  DISK_FLOOR_GIB=$(( _free_gib - DISK_ALLOWANCE_GIB ))
  # if/fi, not `[[ ]] && assign`: a false test makes that line return non-zero, which
  # aborts the script under `set -e`. This file does not set -e today; the next edit might.
  if [[ "$DISK_FLOOR_GIB" -lt "$DISK_ABS_FLOOR_GIB" ]]; then
    DISK_FLOOR_GIB="$DISK_ABS_FLOOR_GIB"
  fi
else
  DISK_FLOOR_GIB="$DISK_ABS_FLOOR_GIB"
fi
echo "disk:           ${_free_gib:-?} GiB free, floor ${DISK_FLOOR_GIB} GiB (allowance ${DISK_ALLOWANCE_GIB})"
docker run -d --rm --name "$DISK" \
  -v "$REPO:/repo:ro" -v "$W/native-work:/work" -w /repo "$IMAGE" \
  python3 scripts/watch_disk_headroom.py --path /work --floor-gib "$DISK_FLOOR_GIB" \
    --sentinel /work/yield.sentinel --max-seconds "$WATCH_SECONDS" \
    --must-cover-seconds "$MUST_COVER" --interval 60 >/dev/null \
  || { echo "ABORTING: the disk watch refused to arm."; exit 4; }
sleep 5
if [[ -z "$(docker ps -q --filter "name=^${DISK}$")" ]]; then
  echo "ABORTING: the disk watch is not running. It refused:"
  docker logs "$DISK" 2>&1 | tail -6
  exit 4
fi
echo "  disk watch armed"

echo "=== STEP 3: the cell"
cd "$REPO" || exit 2
CELL_TIMEOUT_SECONDS="$CELL_TIMEOUT_SECONDS" \
NATIVE_CONTAINER_NAME="$CELL_NAME" \
NATIVE_VENV_HOST="${NATIVE_VENV_HOST:-}" \
CELLS="$CELLS" \
DOCKER_GPUS="\"device=${CARD}\"" \
NATIVE_YIELD_SENTINEL=/tmp/native-work/yield.sentinel \
NATIVE_WORK_HOST_DIR="$W/native-work" NATIVE_OUT_HOST_DIR="$W/native-out" \
NATIVE_RESULT_MIRROR="$W/mirror" \
  bash datasphere/native/run_on_production_host.sh "$PAYLOAD" "$RESULT"
cell=$?
echo "=== CELL EXIT=$cell"
exit "$cell"
