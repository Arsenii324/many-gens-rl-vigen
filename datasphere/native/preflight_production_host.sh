#!/usr/bin/env bash
# Check every assumption notes/RUNNING-ON-PRODUCTION-HOST.md makes about the production host,
# BEFORE the first real cell, and print a verdict per check.
#
# [Claude 2026-09-07] Written because §1 of that runbook was a list of commands a human was
# expected to run and interpret. Every one of them is mechanical, and the cost of getting one wrong
# is a cell that fails hours in -- or worse, one that succeeds while measuring something else. The
# renderer check in particular is not a formality: C95 records a 131.5-versus-13.85 difference on
# the same checkpoint under a renderer change, which is larger than any effect this project is
# trying to measure.
#
#   bash datasphere/native/preflight_production_host.sh                 # every check
#   bash datasphere/native/preflight_production_host.sh --cells drqv2:1 --frames 600000
#
# Exit 0 only if every check passes. Nothing here writes, submits, or trains.
set -uo pipefail

CELLS="${CELLS:-drqv2:1}"
FRAMES="${FRAMES:-600000}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cells) CELLS="$2"; shift 2 ;;
    --frames) FRAMES="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

PASS=0; FAIL=0
ok()   { printf '  PASS  %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '  FAIL  %s\n' "$1"; FAIL=$((FAIL + 1)); }
note() { printf '        %s\n' "$1"; }

echo "production-host preflight: cells=$CELLS frames=$FRAMES"

# 1. Docker reachable AS THIS USER. Being in the docker group is not the same as docker running,
#    and `sudo docker` working is not the same as the wrapper working.
if docker info >/dev/null 2>&1; then
  ok "docker daemon reachable without sudo"
else
  bad "docker info failed: the daemon is down, or this user is not in the docker group"
  note "every command in the runbook assumes docker works as the SSH user"
fi

# 2. The pinned image, by digest. A different image is a different experiment (C95).
# [Claude 2026-09-08] Every python3 in this script used to run ON THE HOST. That is the discipline
# `run_on_production_host.sh` was changed to obey the same day -- nothing but small
# python-unrelated actions and docker itself runs outside a container -- and a preflight that
# violates the rule it is checking compliance with is worse than no preflight.
HELPER_IMAGE="${NATIVE_HELPER_IMAGE:-python:3.11-slim}"
helper_python() {
  docker run --rm -v "$PWD:/repo:ro" -w /repo "$HELPER_IMAGE" python3 "$@" 2>/dev/null
}
IMAGE="$(helper_python -c "import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json').read_text())['container_image'])")"
if [[ -n "$IMAGE" ]]; then
  ok "source-lock pins an image: ${IMAGE:0:60}..."
else
  bad "could not read container_image from datasphere/native/source-lock.json"
fi

# 3. GPU passthrough. nvidia-smi on the host does NOT prove `docker run --gpus` works -- that needs
#    nvidia-container-toolkit and a daemon configured for it.
if [[ -n "$IMAGE" ]] && docker run --rm --gpus all "$IMAGE" nvidia-smi >/dev/null 2>&1; then
  ok "docker run --gpus all reaches the GPUs from inside the pinned image"
else
  bad "GPU passthrough failed inside the container"
  note "host nvidia-smi working does not imply this; check nvidia-container-toolkit"
fi

# 4. How many GPUs, and are they free. Packing needs two; a busy card changes the schedule.
if command -v nvidia-smi >/dev/null 2>&1; then
  COUNT="$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ')"
  ok "nvidia-smi reports ${COUNT} GPU(s)"
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null \
    | while IFS= read -r line; do note "GPU $line"; done
  note "NATIVE_CELL_DEVICES indexes these; packing two cells needs two free cards"
else
  bad "nvidia-smi not found on the host"
fi

# 5. Outbound network. run_probe.sh installs apt and pip packages inside the container every run.
if [[ -n "$IMAGE" ]] && docker run --rm "$IMAGE" bash -c \
     'apt-get -qq update >/dev/null 2>&1 && echo reachable' 2>/dev/null | grep -q reachable; then
  ok "the container can reach apt repositories"
else
  bad "no outbound network from inside the container"
  note "run_probe.sh bootstraps its whole environment per run; this is fatal, not slow"
fi

# 6. Disk, against the DERIVED requirement for these cells rather than a constant.
# --profile explicitly: the helper container receives no environment, so family.py's fallback to
# os.environ["NATIVE_HOST_PROFILE"] reads nothing there and would silently size against the base
# profile. Same defect as run_on_production_host.sh's check_disk, same fix.
REQUIRED="$(helper_python datasphere/native/family.py disk-requirement \
  --cells "$CELLS" --frames "$FRAMES" --profile "${NATIVE_HOST_PROFILE:-v100}" --ceil-total)"
FREE="$(df -Pk . 2>/dev/null | awk 'NR==2 {printf "%d", $4 / 1048576}')"
if [[ -n "$REQUIRED" && -n "$FREE" ]]; then
  if [[ "$FREE" -ge "$REQUIRED" ]]; then
    ok "disk: ${FREE} GB free here, ${REQUIRED} GB needed for ${CELLS} at ${FRAMES} frames"
  else
    bad "disk: ${FREE} GB free, ${REQUIRED} GB needed for ${CELLS} at ${FRAMES} frames"
    note "docker run --rm -v \"\$PWD:/repo:ro\" -w /repo $HELPER_IMAGE \\"
    note "  python3 datasphere/native/family.py disk-requirement --cells $CELLS --frames $FRAMES"
  fi
else
  bad "could not compute the disk requirement"
fi

# 7. RAM, against the same model check_memory enforces at run time.
if docker run --rm -v "$PWD:/repo:ro" -w /repo -e NATIVE_HOST_PROFILE=v100 -e FRAMES="$FRAMES" \
     "$HELPER_IMAGE" python3 datasphere/native/family.py check-memory \
     --cells "$CELLS" --tier v100 --frames "$FRAMES" >/dev/null 2>&1; then
  ok "memory model admits ${CELLS} on the v100 tier at ${FRAMES} frames"
else
  bad "memory model refuses ${CELLS} on the v100 tier"
  docker run --rm -v "$PWD:/repo:ro" -w /repo -e NATIVE_HOST_PROFILE=v100 "$HELPER_IMAGE" \
    python3 datasphere/native/family.py check-memory \
    --cells "$CELLS" --tier v100 --frames "$FRAMES" 2>&1 | sed 's/^/        /'
fi

# 8. Host RAM actually present, since the model's ceiling is a claim about this machine.
if [[ -r /proc/meminfo ]]; then
  TOTAL_GIB="$(awk '/MemTotal/ {printf "%d", $2 / 1048576}' /proc/meminfo)"
  if [[ "$TOTAL_GIB" -ge 100 ]]; then
    ok "host reports ${TOTAL_GIB} GiB of RAM"
  else
    bad "host reports ${TOTAL_GIB} GiB of RAM; family.py's v100 tier assumes 100 GiB usable of 113"
  fi
else
  note "/proc/meminfo unreadable (not Linux?); the v100 tier's 100 GiB assumption is UNVERIFIED"
fi

# 9. The GPU we are ASSIGNED, and whether starting now would disturb whoever is on it.
#
# [Claude 2026-09-08] Checks 3 and 4 ask whether passthrough works and how many cards exist. Neither
# asks the two questions that actually decide whether a cell may start on a shared, per-day-assigned
# machine: has the operator NAMED a card, and does that card have room right now.
#
# DOCKER_GPUS is mandatory in run_on_production_host.sh since this date -- it no longer defaults to
# `all` -- so a preflight that passes without it green-lights a run that will refuse.
if [[ -z "${DOCKER_GPUS:-}" ]]; then
  bad "DOCKER_GPUS is unset; run_on_production_host.sh will refuse (exit 3)"
  note "name the assigned card: DOCKER_GPUS='\"device=1\"' or '\"device=GPU-<uuid>\"'"
  note "the UUID form survives re-enumeration; nvidia-smi -L lists them"
else
  ok "DOCKER_GPUS=${DOCKER_GPUS}"
  # Index INSIDE a pinned container is 0, but this check runs on the host, where it is the real
  # index. Extract it from the spec; a UUID form cannot be indexed and is reported rather than
  # checked, since matching a UUID to an index would mean listing every card.
  gpu_index="$(printf '%s' "$DOCKER_GPUS" | sed -n 's/.*device=\([0-9][0-9]*\).*/\1/p')"
  if [[ -n "$gpu_index" ]]; then
    if docker run --rm -v "$PWD:/repo:ro" -w /repo "$HELPER_IMAGE" \
         python3 scripts/watch_gpu_headroom.py --preflight --device "$gpu_index" \
         --need-mib "${PREFLIGHT_NEED_MIB:-4000}" >/dev/null 2>&1; then
      ok "card ${gpu_index} has room and is not busy with someone else's work"
    else
      bad "card ${gpu_index} failed the headroom/utilisation verdict"
      note "run it directly for the numbers:"
      note "  python3 scripts/watch_gpu_headroom.py --preflight --device ${gpu_index} --need-mib 4000"
      note "the utilisation half is a COURTESY limit -- override with --max-util 100 only if the"
      note "owner has said that slowing a co-tenant is acceptable. The memory half is not."
    fi
  else
    note "DOCKER_GPUS is a UUID form; headroom not checked here -- check it by hand"
  fi
fi

echo
# Printed on BOTH paths deliberately. An operator reading a failure list is exactly the person who
# might otherwise fix the four failures, see green, and take it for a parity result.
echo "NOT COVERED by this script, on any outcome: renderer parity (C95). That is the R_A/R_B"
echo "comparison in MIGRATION-T4-TO-V100.md step 2, against a real checkpoint, and it is its own"
echo "gate -- a green preflight says the host can RUN a cell, not that its pixels match."
echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "preflight: ${PASS} checks passed, 0 failed."
  exit 0
fi
echo "preflight: ${PASS} passed, ${FAIL} FAILED. Do not start a production cell."
exit 1
