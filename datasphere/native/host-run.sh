#!/usr/bin/env bash
# Run a script inside a container on the production host, with no quoting hazards.
#
#     bash datasphere/native/host-run.sh [options] <script-file>
#     echo 'du -sh /work' | bash datasphere/native/host-run.sh -      # read the script from stdin
#
# Options (all have safe defaults; every one is printed before anything runs):
#   -i IMAGE     container image            (default ubuntu:24.04)
#   -m PATH      host path to mount at /work (default $HOME/rlvigen-work)
#   -r           mount it READ-ONLY
#   -g SPEC      GPU spec: none | "device=1" | "device=GPU-<uuid>" | all   (default none)
#   -n NAME      container name suffix     (default a timestamp)
#   -k           keep root ownership; by default /work is chown'd back on exit
#   -d           dry run: print the exact argv and stop
#
# WHY THIS EXISTS
#
# Every container invocation in this session was written as `ssh host "docker run ... bash -c '
# ...'"`, which nests three levels of quoting: the ssh argument, the `bash -c` string, and whatever
# the script itself quotes. That cost real mistakes -- a `$?` that read the wrong process, and a
# commit message where backticks inside a double-quoted `-m` executed `docker run --rm` and ate a
# sentence. Neither was a thinking error; both were quoting errors, and quoting errors are a class
# you remove with a mechanism rather than with care.
#
# So the script body never appears on a command line. It is base64-encoded, passed in an
# environment variable, and decoded inside the container. Nothing in it is interpreted by the
# host shell, by ssh, or by `bash -c`. A script containing backticks, `$(...)`, single quotes,
# double quotes and newlines runs exactly as written.
#
# It also enforces two rules this host needs, in the one place every run passes through:
# GPUs are never claimed by default (see 07-this-repo-s-own-hazards.md), and the mount is a single
# explicit path under our own directory rather than anything global.
set -euo pipefail

IMAGE="ubuntu:24.04"
MOUNT="${HOME}/rlvigen-work"
READONLY=""
GPUS="none"
NAME_SUFFIX="$(date +%Y%m%d-%H%M%S)"
CHOWN_BACK=1
DRY=0

while getopts ":i:m:rg:n:kd" opt; do
  case "$opt" in
    i) IMAGE="$OPTARG" ;;
    m) MOUNT="$OPTARG" ;;
    r) READONLY=":ro" ;;
    g) GPUS="$OPTARG" ;;
    n) NAME_SUFFIX="$OPTARG" ;;
    k) CHOWN_BACK=0 ;;
    d) DRY=1 ;;
    \?) echo "unknown option -$OPTARG" >&2; exit 2 ;;
    :)  echo "option -$OPTARG needs a value" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

# [Claude 2026-09-10] A WRITABLE MOUNT NEEDS A DECLARED UPPER BOUND. Added after this script was
# used to start a ~24 GB download onto the shared disk having checked only `df` -- which is a
# point-in-time observation, not a bound, and is exactly what
# `notes/production-host/10-resource-upper-bound-rule.md` forbids:
#
#   "If you do not know an upper bound on the resources you will occupy, do not run it."
#
# Every other host path already enforces this. `run_on_production_host.sh` runs check_disk and
# refuses; `launch-card-cell.sh` derives an allowance from `family.py disk-requirement` and arms a
# disk watch. This script had NO disk check at all, so it was the one way to write to a shared
# filesystem without stating what the write would cost -- and that is the path the drift took.
#
# The bound is DECLARED, not derived, because this runner has no cell to derive from: a caller who
# cannot state a number does not have a bound. The floor reuses the project's own absolute floor
# rather than inventing a threshold. READ-ONLY mounts (-r) skip the check: they cannot consume.
if [[ -z "$READONLY" ]]; then
  _abs_floor="${NATIVE_DISK_ABS_FLOOR_GIB:-50}"
  # `df -PBG` is a GNU extension: on macOS it exits 64 and, under `set -euo pipefail`, aborted this
  # script with NO message -- a refusal indistinguishable from a crash, which is the failure mode
  # this repo has paid for repeatedly. POSIX `-Pk` works on both, and `|| true` keeps a df failure
  # from aborting before the refusal can be printed.
  _free="$( { df -Pk "$MOUNT" 2>/dev/null || true; } | awk 'NR==2 {printf "%d", $4/1048576}')"
  if [[ -z "${HOST_RUN_DISK_BOUND_GIB:-}" ]]; then
    echo "refusing: $MOUNT is mounted WRITABLE and HOST_RUN_DISK_BOUND_GIB is unset." >&2
    echo "  State an upper bound in GiB on what this script may write. Not a typical value and not" >&2
    echo "  a previous run's size: a number the run cannot exceed, with a reason." >&2
    echo "  Free on $MOUNT right now: ${_free:-unknown} GiB. Absolute floor: ${_abs_floor} GiB." >&2
    echo "  Mount read-only with -r if the script only reads." >&2
    exit 2
  fi
  if [[ -n "$_free" ]] && (( _free - HOST_RUN_DISK_BOUND_GIB < _abs_floor )); then
    echo "refusing: bound ${HOST_RUN_DISK_BOUND_GIB} GiB against ${_free} GiB free would leave" >&2
    echo "  $(( _free - HOST_RUN_DISK_BOUND_GIB )) GiB, below the ${_abs_floor} GiB absolute floor." >&2
    echo "  This filesystem is SHARED. Filling it breaks every writer on the machine at once." >&2
    exit 2
  fi
  echo "disk bound: ${HOST_RUN_DISK_BOUND_GIB} GiB declared, ${_free:-?} GiB free, floor ${_abs_floor} GiB" >&2
fi

SCRIPT="${1:?usage: host-run.sh [options] <script-file>|-   (see the header)}"
if [[ "$SCRIPT" == "-" ]]; then
  BODY="$(cat)"
else
  [[ -f "$SCRIPT" ]] || { echo "no such script: $SCRIPT" >&2; exit 2; }
  BODY="$(cat "$SCRIPT")"
fi
[[ -n "$BODY" ]] || { echo "refusing: the script is empty" >&2; exit 2; }

[[ -d "$MOUNT" ]] || { echo "refusing: mount path does not exist: $MOUNT" >&2; exit 2; }
case "$MOUNT" in
  "$HOME"/*) : ;;
  *) echo "refusing: $MOUNT is outside \$HOME." >&2
     echo "  This host's rules put our work in our own directory, never a global path." >&2
     echo "  Pass -m explicitly with a path under $HOME if you meant something else there." >&2
     exit 3 ;;
esac

# The GPU rule, in the one place every run passes through. `--gpus none` is not valid docker -- it
# parses the value as a count -- so `none` means OMIT the flag, which is how a container gets no
# GPU at all.
GPU_ARGS=()
if [[ "$GPUS" != "none" ]]; then
  GPU_ARGS=(--gpus "$GPUS")
fi

# [Claude 2026-09-08] Order matters and the first version got it wrong: this ran AFTER the argv
# array was built, so HOSTRUN_CHOWN=1 was already baked in and a read-only run emitted a page of
# `chown: Read-only file system`. Decide it before anything reads the value.
if [[ "$READONLY" == ":ro" && "$CHOWN_BACK" == "1" ]]; then
  CHOWN_BACK=0
  echo "note:      mount is read-only, so the chown-back is skipped" >&2
fi

CONTAINER="rlvigen-${NAME_SUFFIX}"
B64="$(printf '%s' "$BODY" | base64 | tr -d '\n')"

# The inner command is FIXED text. It contains no interpolation of the script, the mount or any
# other caller-supplied string -- those travel as environment variables, which docker passes
# without shell interpretation.
INNER='set -euo pipefail
printf "%s" "$HOSTRUN_B64" | base64 -d > /tmp/hostrun.sh
bash /tmp/hostrun.sh
status=$?
if [ "${HOSTRUN_CHOWN:-0}" = "1" ]; then chown -R "$HOSTRUN_UID:$HOSTRUN_GID" /work || true; fi
exit $status'

ARGV=(docker run --rm --name "$CONTAINER"
      "${GPU_ARGS[@]}"
      -v "${MOUNT}:/work${READONLY}" -w /work
      -e "HOSTRUN_B64=$B64"
      -e "HOSTRUN_UID=$(id -u)" -e "HOSTRUN_GID=$(id -g)"
      -e "HOSTRUN_CHOWN=$CHOWN_BACK"
      "$IMAGE" bash -c "$INNER")

echo "image:     $IMAGE" >&2
echo "mount:     ${MOUNT}:/work${READONLY:-  (read-write)}" >&2
echo "gpus:      ${GPUS}$([[ "$GPUS" == "none" ]] && echo '  (--gpus omitted; no /dev/nvidia*)')" >&2
echo "container: $CONTAINER" >&2
echo "script:    $(printf '%s' "$BODY" | wc -l | tr -d ' ') line(s), passed as base64, never on a command line" >&2
if [[ "$DRY" == "1" ]]; then
  echo "=== DRY RUN, not executing ===" >&2
  printf '  %q\n' "${ARGV[@]}" >&2
  exit 0
fi

# No pipe. The exit status of `docker run` is the exit status of this script, which is the whole
# point -- a `| tail` here would report the filter's status and has already hidden three real
# failures in this project.
"${ARGV[@]}"
