#!/usr/bin/env bash
# Run one native probe/production cell directly on the production V100 host (cds2), via
# `docker run`, with no DataSphere API in the loop at all.
#
# [Claude 2026-09-07] Written because no such script existed. Every piece of tooling this project
# built for remote execution -- job.sh, contract.py, the cfg-*.yaml configs -- assumes DataSphere's
# own job-submission API (`datasphere project job execute`). The actual production host
# (notes/remote-infra.txt: `varaksin_as@cds2`, 16 cores, 113 GiB RAM, 2x V100-32GB, reached by
# plain SSH) is not managed by that API at all -- it is a bare Linux box with Docker, and nothing
# in this repo said how to run a cell there before this file.
#
# The good news, found by reading run_probe.sh itself rather than assuming a gap this size needed
# a new harness: run_probe.sh is ALREADY fully self-contained and platform-agnostic. It does its
# own `apt-get install`/`pip install` from a bare CUDA base image (see its own lines ~481-482,
# ~787-793) -- exactly what a DataSphere job's container does, with no DataSphere-specific step
# anywhere in it. So this script does not need to build a custom image or replicate any
# provisioning logic; it only needs to invoke the exact same command DataSphere already runs,
# through `docker run` instead of `datasphere project job execute`.
#
# NOT verified end to end on the actual host -- this agent has no SSH access to cds2. Every piece
# is derived directly from the already-proven DataSphere contract (source-lock.json's pinned
# image, run_probe.sh's own positional-argument and env-var interface, identical to what every
# cfg-*.yaml in this directory already sends it) rather than invented fresh. Verify the assumptions
# named below on the actual host before trusting a real result from this script.
#
# Usage (from a shell already on cds2, repo checked out or payload copied there):
#
#   CELLS=drqv2:2 FRAMES=100000 TASK=Door SEED=2 \
#   OFFLINE_EVAL_FAMILY=rlvigen OFFLINE_EVAL_BASELINE=drqv2 OFFLINE_EVAL_SEED=2 \
#   OFFLINE_EVAL_FRAME=100000 OFFLINE_EVAL_DEVICES=cuda \
#   OFFLINE_EVAL_REGIMES=train,eval-easy,eval-medium,eval-hard \
#   OFFLINE_EVAL_SCENES=0,1,2,3,4,5,6,7,8,9 OFFLINE_EVAL_EPISODES=10 \
#     bash datasphere/native/run_on_production_host.sh \
#       payload-v176-rlvigen.tgz result.tgz rlvigen-door2-90d8b8c4.tgz \
#       /tmp/native-out-v178-host s2-snapshot-100000.pt:/mnt/snap.pt:OFFLINE_EVAL_SNAPSHOT
#
# This is the exact R_A config (cfg-renderer-parity-t4-current-v178.yaml) with s/gt4.1/this host/
# -- pass the same env vars a cfg-*.yaml's `cmd:` block sets, plus any file the config declares
# under `inputs:` as an extra CODE:PATH:ENVVAR triple, and this script does the rest.
#
# Positional arguments:
#   $1  payload archive (the CODE input every cfg-*.yaml already builds via
#       `contract.py build-payload`) -- e.g. datasphere/native/payload-v176-rlvigen.tgz
#   $2  result archive OUTPUT path -- where result.tgz lands after the run, on the HOST
#       filesystem (outside the container), e.g. ./result-v178-host.tgz
#   $3  (optional) RL-ViGen asset archive -- e.g. rlvigen-door2-90d8b8c4.tgz. Omit for families
#       that do not need it (idaac, alda, ppg, ibac_sni, ctrl, dmc_gb all still take an RLVIGEN
#       input in every existing cfg-*.yaml, so in practice this is never actually omitted -- kept
#       optional only because run_probe.sh's own third argument already is).
#   $4  (optional) extra file mount, repeatable via EXTRA_MOUNT_* env vars below -- most configs
#       need this for a retained checkpoint (OFFLINE_EVAL_SNAPSHOT). See EXTRA_MOUNT_1 etc. below
#       instead of a fourth positional argument, since some configs need more than one.
#
# Every other input (CELLS, FRAMES, TASK, SEED, RECORDS_OUT, EVAL_EVERY_FRAMES, EVAL_EPISODES,
# OFFLINE_EVAL_*, ENDPOINT_EVAL*, NATIVE_HOST_PROFILE, ...) is an environment variable, forwarded
# into the container unchanged -- copy them verbatim from whichever cfg-*.yaml's `cmd:` block is
# the template, exactly as this file's own usage example above does for v178.
#
# LONG RUNS, PACKING, GPU PINNING -- the three things a production cell needs and a diagnostic
# probe does not:
#
#   Detach. `docker run` below is foreground and blocking. An SSH drop sends SIGHUP to this
#   script, and although dockerd keeps the container itself alive, this script dies before its
#   result-retrieval `cp` steps -- so run any multi-hour cell under nohup or tmux, wrapping the
#   WHOLE script, not just the docker command:
#     nohup bash datasphere/native/run_on_production_host.sh ... > run.log 2>&1 &
#   Partial output survives regardless, via the /tmp/native-out mount below; the wrapper is what
#   makes the final packaging step survive too.
#
#   Packing. Two cells on one host is ONE container, not two: run_probe.sh takes a comma-separated
#   CELLS list and runs the entries concurrently when NATIVE_CONCURRENT=1 (its own line ~303),
#   serially otherwise. `CELLS=drqv2:1,drqv2:2 NATIVE_CONCURRENT=1` is the packing experiment
#   MIGRATION-T4-TO-V100.md step 4 describes. Do not pack by launching this script twice -- the two
#   containers would each bootstrap separately, neither would see the other's memory use, and
#   nothing would arbitrate between them. One container, one CELLS list, one cgroup.
#   NOTE the co-scheduling constraint: run_probe.sh's own `check-co-schedulable` refuses families
#   that cannot share one Python environment (ctrl is JAX and strips torch; jax[cuda12]'s cudnn 9
#   and torch's pinned cudnn 8.9.2.26 have no common version). Pack within a family, not across.
#
#   Resource limits. This script sets no --memory and no --cpus, deliberately: the packing decision
#   in MIGRATION-T4-TO-V100.md step 4 is gated on MEASURED peak RAM/CPU headroom, and a cgroup cap
#   guessed before that measurement would convert an honest overcommit into an OOM-kill mid-run.
#   Add them once step 2's measurement exists, not before.
#
# GPU selection: notes/remote-infra.txt (2026-09-05) recorded GPU 0 occupied by another user
# (15.1 GB, 67% util), GPU 1 free. Re-check with `nvidia-smi` before every run -- that snapshot is
# a week-plus old by the time this runs and the occupant may have changed or left. Default below
# is `--gpus all`; export CUDA_VISIBLE_DEVICES=1 (or whichever index nvidia-smi shows free) to
# pin to one card instead, matching CTRL's own review-14-flagged caution about not assuming a
# packing plan without a real measurement. Pin at the DOCKER level, not with CUDA_VISIBLE_DEVICES:
# `DOCKER_GPUS='"device=1"'` gives the container exactly one card, so a library that ignores
# CUDA_VISIBLE_DEVICES cannot reach the occupied one. CUDA_VISIBLE_DEVICES is deliberately absent
# from the forwarded-variable list below for the same reason -- it would look like it pinned the
# run while the container still had both cards attached.
set -euo pipefail

# [Claude 2026-09-08] These two checks cost nothing and must precede everything that does. The
# GPU refusal below is a pure environment test, and the image lookup after it starts a container --
# so ordering them the other way round means the most dangerous misconfiguration in this file is
# diagnosed only after a container has already been launched.
# `command -v docker` proves only that the CLI is INSTALLED. The daemon may be stopped, or this
# user may not be in the docker group -- and then the first real failure is a raw
# "failed to connect to the docker API at unix:///var/run/docker.sock" from the middle of the
# script, after the argument checks have already passed. `docker info` is the cheap question that
# distinguishes the three cases, and preflight_production_host.sh's own check 1 makes the same
# point: being in the docker group is not the same as docker running.
docker info >/dev/null 2>&1 || {
  if command -v docker >/dev/null 2>&1; then
    echo "refusing: the docker CLI is installed but the daemon is not reachable as this user." >&2
    echo "  Either dockerd is not running, or this account is not in the docker group." >&2
    echo "  Check with: docker info" >&2
  else
    echo "refusing: docker is not on PATH." >&2
  fi
  echo "  Every computation this script performs now runs inside a container -- reading" >&2
  echo "  source-lock.json and the disk model included -- because the production host permits" >&2
  echo "  nothing but small python-unrelated actions and docker itself to run outside one." >&2
  exit 2; }

# [Claude 2026-09-08] `--gpus "${DOCKER_GPUS:-all}"` defaulted to ALL CARDS. On a shared machine
# under a per-day GPU assignment schedule that is the single most dangerous line in this file: one
# forgotten environment variable and the container claims every GPU on the host, including the one
# assigned to somebody else today. The failure is silent from our side and looks like a CUDA OOM
# or a slowdown from theirs.
#
# There is now no default. Name the card, every time.
#
#   DOCKER_GPUS='"device=1"'                        the card assigned to us
#   DOCKER_GPUS='"device=GPU-<uuid>"'               the same card, immune to re-enumeration
#   DOCKER_GPUS=none                                CPU-only work (bootstrap, payload build)
#   DOCKER_GPUS=all                                 every card -- only if you actually own them
#
# The index form follows docker's PCI enumeration, which matches `nvidia-smi -L` order in the
# ordinary case but is not guaranteed to across a driver reload or a hardware change. The UUID form
# from `nvidia-smi -L` cannot be re-pointed by enumeration and is the safer spelling for a run that
# must never touch a neighbour's card.
#
# NOTE an image cannot reach a GPU on its own: access is granted here, by this flag, via the NVIDIA
# Container Toolkit. A CUDA base image with no --gpus sees no /dev/nvidia* at all. The danger has
# never been in which image is pulled; it is in this one string.
if [[ -z "${DOCKER_GPUS:-}" ]]; then
  echo "refusing: DOCKER_GPUS is unset, and this script no longer defaults to 'all'." >&2
  echo "  Defaulting to every card on a machine with a per-day GPU assignment is how a run" >&2
  echo "  takes a card belonging to someone else. Name the card explicitly:" >&2
  echo "    DOCKER_GPUS='\"device=1\"'              the card assigned to us" >&2
  echo "    DOCKER_GPUS='\"device=GPU-<uuid>\"'     the same card, immune to re-enumeration" >&2
  echo "                                            (uuid from: nvidia-smi -L)" >&2
  echo "    DOCKER_GPUS=none                        CPU-only work" >&2
  echo "    DOCKER_GPUS=all                         every card -- only if you own them all" >&2
  exit 3
fi

# [Claude 2026-09-08, second pass] `--gpus none` is NOT valid docker: it parses the value as a
# count and fails with `count must be an integer: strconv.Atoi: parsing "none"`. The way to give a
# container no GPU is to OMIT the flag, so `none` becomes an empty argument list rather than being
# passed through. Caught by testing an option this script itself advertises -- an unusable escape
# hatch in a refusal message is worse than none, because it gets followed under time pressure.
# NOT `[[ ... ]] && DOCKER_GPU_ARGS=()`: under `set -e` a false test makes that line return
# non-zero and abort the script for every caller who DID name a card, which is all of them.
if [[ "$DOCKER_GPUS" == "none" ]]; then
  DOCKER_GPU_ARGS=()
else
  DOCKER_GPU_ARGS=(--gpus "$DOCKER_GPUS")
fi

# [Claude 2026-09-08] This script used to run `python3` on the HOST three times: here, and twice
# more inside check_disk. The production host's rule is that nothing runs outside a container
# except small python-unrelated actions (mkdir, cp, df, stat), a clone, and docker itself. Reading
# JSON and computing a disk model are neither small nor python-unrelated, so both now happen in a
# container against a read-only mount of this repo.
#
# The chicken-and-egg is real and is resolved deliberately: the image we RUN is read from
# source-lock.json, so it cannot be the image we read it WITH. `NATIVE_HELPER_IMAGE` is therefore a
# literal in this file -- one fixed, tiny, general-purpose interpreter, used only for computation
# over a read-only mount and never for anything the experiment depends on. `python:3.11-slim` is
# 124 MB and already present on cds2, so this costs no pull there. It is deliberately NOT the
# pinned CUDA image: that one carries no python3 at all (run_probe.sh apt-installs it), so using it
# here would mean an apt-get per disk check.
HELPER_IMAGE="${NATIVE_HELPER_IMAGE:-python:3.11-slim}"

# Run python over this repository, read-only, inside a container. Nothing it can do reaches the
# host: the mount is `:ro`, the container is `--rm`, and no GPU is requested.
helper_python() {
  docker run --rm -v "$PWD:/repo:ro" -w /repo "$HELPER_IMAGE" python3 "$@"
}

IMAGE="$(helper_python -c "import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json').read_text())['container_image'])")"

CODE="${1:?usage: $0 PAYLOAD.tgz RESULT.tgz [RLVIGEN.tgz] [PLACES365.tgz]}"
RESULT="${2:?usage: $0 PAYLOAD.tgz RESULT.tgz [RLVIGEN.tgz] [PLACES365.tgz]}"
RLVIGEN_ARCHIVE_HOST="${3:-}"
# [Claude 2026-09-07, external review 25 thread] run_probe.sh's THIRD positional is the Places365
# asset, not the RL-ViGen archive -- RL-ViGen arrives through the RLVIGEN_ARCHIVE environment
# variable (every cfg-*.yaml sets `RLVIGEN_ARCHIVE=${RLVIGEN}` and passes Places365 positionally).
# This script had the two swapped and set RLVIGEN_ARCHIVE not at all, so on the production host
# svea/sgqn/soda would hand the RL-ViGen tarball to `contract.py check-asset` and fail its count
# and hash, while RL-ViGen itself fell back to a network clone instead of the pinned archive.
# Invisible for every other baseline, because `cells_need_places365` is false for them and the
# third argument is then never read.
PLACES365_ARCHIVE_HOST="${4:-}"

[[ -f "$CODE" ]] || { echo "no such payload archive: $CODE" >&2; exit 2; }
[[ -z "$RLVIGEN_ARCHIVE_HOST" || -f "$RLVIGEN_ARCHIVE_HOST" ]] || {
  echo "no such RL-ViGen archive: $RLVIGEN_ARCHIVE_HOST" >&2; exit 2; }
[[ -z "$PLACES365_ARCHIVE_HOST" || -f "$PLACES365_ARCHIVE_HOST" ]] || {
  echo "no such Places365 archive: $PLACES365_ARCHIVE_HOST" >&2; exit 2; }

# Mirror run_probe.sh's own production refusals HERE, on the host, before a container bootstrap is
# paid for. run_probe.sh raises both of these itself (its lines ~391 and ~404); catching them at
# this boundary is the same discipline contract.py's payload check already applies -- refuse before
# the expensive step, not after it.
if [[ "${FRAMES:-10000}" -ge 600000 ]]; then
  [[ -n "${NATIVE_PRODUCTION:-}" ]] || {
    echo "refusing: FRAMES=$FRAMES is production scale and NATIVE_PRODUCTION is unset." >&2
    echo "  run_probe.sh would exit 3 inside the container after the full bootstrap was paid." >&2
    echo "  Set NATIVE_PRODUCTION=1 (and NATIVE_HOST_PROFILE) for any production-scale cell." >&2
    exit 3; }
  [[ -n "${NATIVE_HOST_PROFILE:-}" ]] || {
    echo "refusing: FRAMES=$FRAMES is production scale and NATIVE_HOST_PROFILE is unset." >&2
    echo "  run_probe.sh requires it explicitly at this scale (its own line ~391)." >&2
    exit 3; }
  # [Claude 2026-09-07, external recommendation 22] A production cell with no per-cell ceiling can
  # burn the whole job's wall clock on one stuck family, and because the result archive is written
  # LAST, a job cut off at the job level loses the evidence of every cell that already finished.
  # run_probe.sh honours CELL_TIMEOUT_SECONDS and simply does not cap when it is unset.
  #
  # The right VALUE needs the host throughput measurement and cannot be guessed from here -- so
  # this refuses rather than inventing one. That converts a silent omission into a decision made
  # at submit time, which is the part that was missing; the number still comes from measurement.
  #   ceiling ~= (frames / measured frames-per-second) x a factor for eval and checkpointing
  [[ -n "${CELL_TIMEOUT_SECONDS:-}" ]] || {
    echo "refusing: FRAMES=$FRAMES is production scale and CELL_TIMEOUT_SECONDS is unset." >&2
    echo "  Without a per-cell ceiling one stuck cell burns the job and the result archive --" >&2
    echo "  written last -- is lost for every cell that already completed." >&2
    echo "  Derive it from the host throughput measurement (runbook step 2), not from a guess:" >&2
    echo "    CELL_TIMEOUT_SECONDS ~= (FRAMES / measured_fps) * headroom_for_eval_and_saves" >&2
    exit 3; }
  # [Claude 2026-09-08] A SECOND DEVICE for the results, verified to be a second device.
  #
  # Both /tmp/native-out and /tmp/native-work are already bind-mounted to host paths, so
  # checkpoints are durable as they are written -- that half of the durability gap closed on
  # 2026-09-07. What remains is the host disk itself: a 45-hour soda cell whose volume fails loses
  # every seed on it, and the campaign is ~893 GPU-hours.
  #
  # Requiring a path and trusting the operator to pick a different volume would be worse than
  # useless -- it manufactures assurance without evidence, which is the exact failure mode this
  # project keeps finding. So the device id is compared, and a mirror on the same filesystem is
  # REFUSED rather than accepted with a warning. `stat -f -c %i` is Linux (GNU coreutils); the
  # production host is Linux by construction (docs/RUNNING-ON-PRODUCTION-HOST.md), and if the
  # field cannot be read the check says so instead of passing.
  [[ -n "${NATIVE_RESULT_MIRROR:-}" ]] || {
    echo "refusing: FRAMES=$FRAMES is production scale and NATIVE_RESULT_MIRROR is unset." >&2
    echo "  Results live on one host volume. Name a directory on a DIFFERENT device and the" >&2
    echo "  result archive is copied there when the run completes." >&2
    echo "    NATIVE_RESULT_MIRROR=/mnt/other-volume/rlvigen-results" >&2
    exit 3; }
  mkdir -p "$NATIVE_RESULT_MIRROR" || {
    echo "refusing: NATIVE_RESULT_MIRROR=$NATIVE_RESULT_MIRROR cannot be created." >&2
    exit 3; }
  # [Claude 2026-09-08] VALIDATE the output, do not just check the exit status. `stat -f -c %i` is
  # GNU coreutils, where -f means "the filesystem, not the file". On a `stat` where -f means a
  # format string instead, the command SUCCEEDS and prints something else entirely -- so the
  # `== "unreadable"` guard below never fires and a garbage value reaches the same-device
  # comparison. Found by running this script's new dry run on macOS, where it produced
  # `(fsid -c<newline>unreadable)` in the middle of a refusal message.
  #
  # The production host is Linux and would not hit that. The point is that a guard whose failure
  # path depends on a command failing CLEANLY is not a guard -- it silently degrades wherever the
  # command fails some other way, and this one gates whether the campaign's only off-device copy
  # actually lives on another device.
  _dev_of() {
    local out
    out="$(stat -f -c %i "$1" 2>/dev/null)" || { echo "unreadable"; return; }
    # [Claude 2026-09-08, second pass] The first version of this validation demanded ^[0-9]+$ and
    # was WRONG on the only platform that matters. GNU stat prints the filesystem ID of `-f %i` in
    # HEX -- cds2 returns `c4aaf1bac0c3eb66` -- so every real production run failed the check,
    # reported "unreadable", and demanded NATIVE_ACCEPT_UNVERIFIED_DEVICE=1. The same-device branch
    # could then never fire at all, which is the branch that carries the durability finding.
    #
    # Found by running the wrapper's dry run on the host rather than reasoning about it. The
    # original defect (macOS `stat -f` taking a format string, printing garbage that passed) is
    # still caught: its output contains `(`, spaces and the letters r/n/u/s, none of which are hex.
    [[ "$out" =~ ^[0-9a-fA-F]+$ ]] || { echo "unreadable"; return; }
    printf '%s' "$out"
  }
  _result_dev="$(_dev_of "$(dirname "$RESULT")")"
  _mirror_dev="$(_dev_of "$NATIVE_RESULT_MIRROR")"
  if [[ "$_result_dev" == "unreadable" || "$_mirror_dev" == "unreadable" ]]; then
    echo "refusing: cannot read the filesystem id of the result path or the mirror," >&2
    echo "  so 'a different device' cannot be verified and must not be assumed." >&2
    echo "  Set NATIVE_ACCEPT_UNVERIFIED_DEVICE=1 to proceed and record the deviation." >&2
    # [Claude 2026-09-08] The escape exists for the same reason NATIVE_ACCEPT_SAME_DEVICE does:
    # "verified same device" and "could not verify" are both deviations, and both belong to the
    # operator rather than to this script. It is NOT a default -- an unverified mirror silently
    # accepted is the failure this whole block exists to prevent, and the marker below is what
    # makes a run that took it identifiable afterwards.
    [[ "${NATIVE_ACCEPT_UNVERIFIED_DEVICE:-0}" == "1" ]] || exit 3
    echo "=== NATIVE_RESULT_MIRROR_DEVICE_UNVERIFIED (accepted explicitly) ===" >&2
  elif [[ "$_result_dev" == "$_mirror_dev" ]]; then
    # [Claude 2026-09-08] Same fsid has TWO causes and they need different answers. The operator
    # pointing the mirror at the same volume when others exist is a mistake, and telling them to
    # "point it at another volume" fixes it. A host that HAS only one volume is not making a
    # mistake, and that advice is unfollowable -- cds2 is exactly this: `df -hT` shows a single
    # /dev/sda2 carrying /, /home, /var/lib/docker and /tmp alike.
    #
    # This matters because the deviation marker is what identifies such a run afterwards, and a
    # marker that fires on every single run of the campaign carries no information. Diagnosing the
    # two cases apart keeps "the operator accepted a worse layout than this host offered" separate
    # from "this host offers nothing better", which is an owner-level fact about the campaign, not
    # an operator slip.
    # [Claude 2026-09-08, second pass] Counting FILESYSTEMS was wrong: cds2 reports two, and the
    # second is /dev/sda3, a 975 MB /boot partition with 376 MB free. Telling an operator "a better
    # mirror location EXISTS" and pointing them at /boot is worse than saying nothing.
    #
    # What matters is not how many filesystems exist but whether any of them could actually HOLD a
    # result. The floor below is deliberately crude and named in the message rather than hidden:
    # anything with less than 20 GB free cannot take a production cell's output, so it is not a
    # candidate whatever its mount point says.
    _mirror_floor_gb=20
    _mirror_candidates="$(df -P --local -x tmpfs -x devtmpfs -x squashfs -x overlay -x fuse.gvfsd-fuse \
        2>/dev/null | awk -v need="$_mirror_floor_gb" 'NR>1 && ($4/1048576) >= need {print $1}' \
        | sort -u | wc -l | tr -d ' ')"
    _real_filesystems="$_mirror_candidates"
    echo "refusing: NATIVE_RESULT_MIRROR is on the SAME filesystem as the result path" >&2
    echo "  (fsid $_result_dev). A copy beside the original does not survive the failure it" >&2
    echo "  exists for." >&2
    if [[ "${_real_filesystems:-0}" -le 1 ]]; then
      echo "  THIS HOST HAS NO SECOND FILESYSTEM THAT COULD HOLD A RESULT (none besides this one" >&2
      echo "  has ${_mirror_floor_gb} GB free), so there is no second volume to point at and" >&2
      echo "  no durable second location exists here. The mirror still buys a second COPY -- it" >&2
      echo "  survives our own tar failing, a bad path, an overwrite -- but it does NOT buy a" >&2
      echo "  second failure domain: one full or failed disk loses both." >&2
      echo "  Attach external storage or a network mount, or set NATIVE_ACCEPT_SAME_DEVICE=1 to" >&2
      echo "  run knowing that. This is an owner-level property of the campaign, not a slip." >&2
      [[ "${NATIVE_ACCEPT_SAME_DEVICE:-0}" == "1" ]] || exit 3
      echo "=== NATIVE_RESULT_MIRROR_SINGLE_DEVICE_HOST filesystems=${_real_filesystems} fsid=$_result_dev (accepted explicitly) ===" >&2
    else
      echo "  This host has ${_real_filesystems} filesystems with at least ${_mirror_floor_gb} GB free," >&2
      echo "  so a better mirror location EXISTS. They are:" >&2
      df -Ph --local -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null \
        | awk -v need="$_mirror_floor_gb" 'NR>1 && ($4+0>0) {print "    " $0}' >&2
      echo "  Point it at another volume, or set NATIVE_ACCEPT_SAME_DEVICE=1 to record the" >&2
      echo "  deviation deliberately." >&2
      [[ "${NATIVE_ACCEPT_SAME_DEVICE:-0}" == "1" ]] || exit 3
      echo "=== NATIVE_RESULT_MIRROR_SAME_DEVICE fsid=$_result_dev of ${_real_filesystems} available (accepted explicitly) ===" >&2
    fi
  fi
fi

# Disk. A production cell needs far more than its checkpoints: the RL-ViGen five keep their replay
# as episode files on disk under the run directory, capped at families.json's replay_capacity of
# 300000 transitions x 63,504 B = about 19 GB per cell, plus 1.7-3.2 GiB of retained checkpoints
# (families.json preserve_snapshots=100000 keeps six of a 600k run's twelve saves plus the
# endpoint) plus the result archive. Roughly 25 GB per off-policy cell, so about 50 GB for the
# two-cell packing MIGRATION-T4-TO-V100.md step 4 plans. The on-policy families (idaac, ppg, ctrl,
# ibac_sni) hold no replay at all and need a small fraction of that.
#
# The floor below is deliberately one number rather than a per-family figure: families.json does
# not carry a disk column today, and inventing one here would put a second, unreviewed source of
# truth next to it. notes/PRODUCTION-HOST-RATIFICATION.md records deriving it per family as the
# better version and why it is not done yet.
# [Claude 2026-09-07] Was a single 60 GB constant, which is about right for one off-policy cell
# and roughly thirty times too strict for an on-policy one -- idaac holds no replay and retains
# 0.06 GiB of checkpoints, so its real need is ~5 GB. A floor that is wrong for half the fleet gets
# overridden as a matter of routine, and a routinely-overridden guard is not a guard. Derived per
# cell now, from the same replay model check_memory uses plus plan_production's MEASURED checkpoint
# bytes: 43 GiB for one drqv2 cell, 81 for two packed, 5 for idaac, 24 for rad.
check_disk() {
  local target="$1" free_gb required
  free_gb="$(df -Pk "$target" 2>/dev/null | awk 'NR==2 {printf "%d", $4 / 1048576}')" || free_gb=""
  # [Claude 2026-09-08] Both of these used to `return 0` -- the whole disk check silently skipped,
  # with no output, whenever `df` failed or printed nothing. On a communal host that inverts the
  # rule this check exists to enforce: not knowing how much space we have is the reason NOT to
  # run, never a reason to proceed unchecked. Refuse at production scale; below it, say plainly
  # that nothing was verified rather than reading as a check that passed.
  if [[ -z "$free_gb" ]]; then
    if [[ "${FRAMES:-10000}" -ge 600000 ]]; then
      echo "REFUSING: could not read free space at $target (df failed or returned nothing)." >&2
      echo "  A production cell writes tens of GiB to this path on a shared host. Running without" >&2
      echo "  knowing the headroom is the case the upper-bound rule forbids outright." >&2
      echo "  Set NATIVE_DISK_FLOOR_GB only if you have measured the headroom another way." >&2
      exit 4
    fi
    echo "WARNING: could not read free space at $target; NOTHING was verified about disk headroom." >&2
    return 0
  fi
  if [[ -n "${NATIVE_DISK_FLOOR_GB:-}" ]]; then
    required="$NATIVE_DISK_FLOOR_GB"
  else
    # One containerised call, not a host pipeline of two. `--ceil-total` exists for exactly this.
    required="$(helper_python datasphere/native/family.py disk-requirement \
        --cells "${CELLS:-drqv2:1}" --frames "${FRAMES:-10000}" --ceil-total 2>/dev/null)" \
        || required=""
    # [Claude 2026-09-08] The fallback is a generic constant that is right for roughly none of the
    # fleet -- 60 GB is ~10x idaac's real need and ~10 GiB short of soda's. It stays as a floor for
    # probe-scale work, but at production scale a failed requirement computation means the number
    # being enforced is not this job's, so say so instead of enforcing a stranger's number.
    if [[ -z "$required" ]]; then
      if [[ "${FRAMES:-10000}" -ge 600000 ]]; then
        echo "REFUSING: family.py disk-requirement failed for --cells ${CELLS:-drqv2:1}" >&2
        echo "  --frames ${FRAMES:-10000}, so this job's real disk need is unknown. The 60 GB" >&2
        echo "  fallback is not this job's number: soda needs 70.73 GiB and idaac needs 6.52." >&2
        echo "  Fix the tool, or set NATIVE_DISK_FLOOR_GB to a number you have justified." >&2
        exit 4
      fi
      required=60
      echo "WARNING: disk-requirement failed; falling back to a generic ${required} GB floor that" >&2
      echo "  is not derived from these cells." >&2
    fi
  fi
  echo "free disk at $target: ${free_gb} GB (this job needs ~${required} GB)" >&2
  if [[ "$free_gb" -lt "$required" ]]; then
    echo "refusing: ${free_gb} GB free at $target, below the ${required} GB this job needs." >&2
    echo "  Breakdown (run it in a container, not on the host):" >&2
    echo "    docker run --rm -v \"\$PWD:/repo:ro\" -w /repo $HELPER_IMAGE \\" >&2
    echo "      python3 datasphere/native/family.py disk-requirement --cells ${CELLS:-drqv2:1} --frames ${FRAMES:-10000}" >&2
    echo "  Replay episode files dominate for off-policy cells; on-policy cells need a fraction." >&2
    echo "  Free space, or set NATIVE_DISK_FLOOR_GB to override with a number you have justified." >&2
    exit 4
  fi
}

# [Claude 2026-09-08] WORKDIR was `mktemp -d` -- $TMPDIR, in practice /tmp -- and the Places365
# archive is COPIED into it a few lines below: 45 GiB for an svea/sgqn/soda cell, the largest
# single write this script makes. Two things were wrong with that on a shared host.
#
#   1. `check_disk` is called on $NATIVE_WORK_HOST_DIR and on nothing else, so the filesystem
#      receiving that write was never checked at all. The requirement number already INCLUDES
#      places365_gib; it was simply being asked of the wrong mount.
#   2. /tmp is tmpfs on many Linux hosts. A 45 GiB write to tmpfs is a 45 GiB RAM allocation. It
#      does not fill a disk and it does not fail cleanly -- it evicts other users' processes,
#      which is precisely the outcome notes/production-host/ forbids outright.
#
# So the payload staging directory now defaults beside $RESULT, on the filesystem the disk check
# validates; NATIVE_WORKDIR_PARENT overrides it for an operator with a better disk; and a
# memory-backed filesystem is refused loudly here rather than discovered later as somebody else's
# OOM kill. The EXIT trap still removes it, so this is a transient peak and not accumulation --
# `docker run --rm` (below) likewise frees the container layer holding the pip install.
WORKDIR_PARENT="${NATIVE_WORKDIR_PARENT:-$(dirname "$RESULT")}"
mkdir -p "$WORKDIR_PARENT"
WORKDIR="$(mktemp -d "$WORKDIR_PARENT/native-payload-XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT
# `df -T` is GNU-only; on a host without it this reads empty and the case falls through rather
# than refusing a run for a filesystem type it could not determine.
WORKDIR_FSTYPE="$(df -PT "$WORKDIR" 2>/dev/null | awk 'NR==2 {print $2}')"
case "$WORKDIR_FSTYPE" in
  tmpfs|ramfs)
    echo "refusing: $WORKDIR is on $WORKDIR_FSTYPE, which is RAM, not disk." >&2
    echo "  The payload and the Places365 archive (~21 GiB compressed) are copied here. On a" >&2
    echo "  memory-backed filesystem that is host RAM, and exhausting it evicts other users'" >&2
    echo "  processes. Set NATIVE_WORKDIR_PARENT to a directory on real storage." >&2
    exit 4 ;;
  "")
    # No default arm at all, originally: an unsupported `df -T` fell through in total silence,
    # which reads identically to a check that ran and passed. Say which it was.
    echo "note: could not determine the filesystem type of $WORKDIR (\`df -T\` unsupported here)." >&2
    echo "  The tmpfs refusal did NOT run. On Linux this should not happen; verify by hand that" >&2
    echo "  $WORKDIR_PARENT is on real storage before a production cell." >&2 ;;
  *)
    echo "staging payload on $WORKDIR_FSTYPE at $WORKDIR" >&2 ;;
esac
check_disk "$WORKDIR"
mkdir -p "$WORKDIR/out"
cp "$CODE" "$WORKDIR/code.tgz"
CONTAINER_ARGS=(/work/code.tgz /work/out/result.tgz)
if [[ -n "$RLVIGEN_ARCHIVE_HOST" ]]; then
  cp "$RLVIGEN_ARCHIVE_HOST" "$WORKDIR/rlvigen.tgz"
fi
if [[ -n "$PLACES365_ARCHIVE_HOST" ]]; then
  cp "$PLACES365_ARCHIVE_HOST" "$WORKDIR/places365.tgz"
  CONTAINER_ARGS+=(/work/places365.tgz)
fi

# Extra file mounts (checkpoints, etc.) declared as HOST_PATH:CONTAINER_PATH:ENV_VAR_NAME triples
# in EXTRA_MOUNT_1, EXTRA_MOUNT_2, ... -- mirrors a cfg-*.yaml's `inputs:` list entries beyond the
# three standard ones above (e.g. `datasphere/native/s2-snapshot-100000.pt: SNAP` becomes
# `EXTRA_MOUNT_1=datasphere/native/s2-snapshot-100000.pt:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT`).
DOCKER_ENV_ARGS=()
# RL-ViGen travels by environment, not position -- see the note at the argument list.
[[ -n "$RLVIGEN_ARCHIVE_HOST" ]] && DOCKER_ENV_ARGS+=(-e "RLVIGEN_ARCHIVE=/work/rlvigen.tgz")
# [Claude 2026-09-07] run_probe.sh keeps its whole working state -- every SAVE_EVERY_FRAMES
# checkpoint, training.log, the per-cell run dirs -- in `out=/tmp/native-out` and `work=
# /tmp/native-work`, both container-local, and copies NOTHING to the mounted result path until its
# single final `tar -czf "$result" -C "$out" .` (its own line 1546). A container killed at any
# point before that line therefore loses the entire run: hours of training, all intermediate
# checkpoints, unrecoverable, because none of it was ever on host storage. Mounting /tmp/native-out
# on the host makes every checkpoint durable as it is written, and makes the run inspectable while
# it runs (`scripts/watch_divergence.py --run <dir>` needs a readable training.log, which is
# otherwise sealed inside the container). This needs no run_probe.sh change -- it writes to the
# same path either way. NATIVE_OUT_HOST_DIR overrides the location.
# Deliberately NOT under $WORKDIR: the EXIT trap removes that, and it fires on a crash too --
# which would delete exactly the partial run this mount exists to save. Default lands next to
# the result archive, where the operator is already looking.
STAMP="$(date +%Y%m%d-%H%M%S)"
NATIVE_OUT_HOST_DIR="${NATIVE_OUT_HOST_DIR:-$(dirname "$RESULT")/native-out-$STAMP}"
# [Claude 2026-09-07] Mounting /tmp/native-out alone was NOT enough, and the first version of this
# script claimed durability it did not have. Every family writes its checkpoints under the cell's
# RUN directory, `$work_root/runs/<cell>` = /tmp/native-work -- families.json's `artifact_root` is
# `{run_dir}` for five of seven and a subdirectory of it for the other two -- and they reach
# /tmp/native-out only when `family.py retain` copies them, which happens AFTER training completes.
# So a container killed at hour 20 of a 27-hour drqv2 cell lost every checkpoint; only training.log
# was durable, because run_measured writes that straight into the cell output.
#
# This is also where the replay episode files live (~19 GB for an off-policy cell), so mounting it
# moves that traffic from Docker's own overlay directory onto a path the operator chose. Same disk
# in the ordinary case, but now visible, and the free-space check below applies to it.
NATIVE_WORK_HOST_DIR="${NATIVE_WORK_HOST_DIR:-$(dirname "$RESULT")/native-work-$STAMP}"
mkdir -p "$NATIVE_OUT_HOST_DIR" "$NATIVE_WORK_HOST_DIR"

# [Claude 2026-09-08] These two directories are stamped per run and deliberately NOT removed --
# that is the whole point of them (a killed container's partial run must survive). The consequence
# is that they ACCUMULATE: 36 cells leave 36 pairs, and an off-policy cell's native-work holds
# ~18 GiB of replay episode files. `check_disk` below does catch the result -- it reads real free
# space, so a disk filled by our own leftovers makes the NEXT run refuse rather than overflow --
# but a refusal at run 20 means runs 1-19 already consumed a shared disk, and on this host that
# is other people's headroom. So: report what is already there, by size, every time. Never delete
# it here. Nothing in this script has proof that a given leftover directory is finished with, and
# the one under $NATIVE_WORK_HOST_DIR may belong to a run still executing.
leftovers="$(find "$(dirname "$RESULT")" -maxdepth 1 -type d \
    \( -name 'native-out-*' -o -name 'native-work-*' \) 2>/dev/null | wc -l | tr -d ' ')"
if [[ "${leftovers:-0}" -gt 2 ]]; then
  echo "note: $(( leftovers - 2 )) directory(ies) from previous runs remain under $(dirname "$RESULT"):" >&2
  du -sh "$(dirname "$RESULT")"/native-out-* "$(dirname "$RESULT")"/native-work-* 2>/dev/null \
      | sort -h | tail -8 | sed 's/^/    /' >&2
  echo "  These are kept on purpose (a killed run's partial output lives there) and are NOT" >&2
  echo "  removed automatically. Collect and delete the finished ones yourself before the disk" >&2
  echo "  reaches a level that affects other users of this host." >&2
fi

check_disk "$NATIVE_WORK_HOST_DIR"
# [Claude 2026-09-08] A pre-extracted Places365 corpus, mounted READ-ONLY and shared by every job.
#
# NATIVE_PLACES365_DIR_HOST points at a directory on the host that already holds the expanded tree.
# It is mounted at a fixed container path and named to run_probe.sh, which then skips the copy and
# the extraction entirely. One 24 GiB corpus on disk forever, instead of ~21 GiB copied plus
# ~24 GiB expanded per job -- and `:ro` means no cell can damage an asset every other cell reads.
#
# Refused rather than ignored if the path is wrong: a silently-skipped mount would fall back to the
# archive path and reintroduce the copy without saying so.
PLACES365_RO_ARGS=()
# The two names are one letter apart and mean different sides of the mount, so the confusable case
# is refused rather than left to produce a container path that does not exist. _HOST is the host
# directory you mount; NATIVE_PLACES365_DIR is what the container sees, and the wrapper sets it.
if [[ -n "${NATIVE_PLACES365_DIR:-}" && -z "${NATIVE_PLACES365_DIR_HOST:-}" ]]; then
  echo "refusing: NATIVE_PLACES365_DIR is set but NATIVE_PLACES365_DIR_HOST is not." >&2
  echo "  NATIVE_PLACES365_DIR names a path INSIDE the container and is set by this script when" >&2
  echo "  it mounts one. Setting it by hand without a mount forwards a host path into a container" >&2
  echo "  where it does not exist." >&2
  echo "  Use: NATIVE_PLACES365_DIR_HOST=/path/to/extracted/places365" >&2
  exit 2
fi
if [[ -n "${NATIVE_PLACES365_DIR_HOST:-}" ]]; then
  [[ -d "$NATIVE_PLACES365_DIR_HOST" ]] || {
    echo "refusing: NATIVE_PLACES365_DIR_HOST=$NATIVE_PLACES365_DIR_HOST is not a directory." >&2
    exit 2; }
  PLACES365_RO_ARGS=(-v "${NATIVE_PLACES365_DIR_HOST}:/opt/places365:ro")
  DOCKER_ENV_ARGS+=(-e "NATIVE_PLACES365_DIR=/opt/places365")
  echo "places365: ${NATIVE_PLACES365_DIR_HOST} -> /opt/places365 (read-only, shared, not copied)" >&2
fi

DOCKER_MOUNT_ARGS=(-v "$WORKDIR:/work"
                   -v "$NATIVE_OUT_HOST_DIR:/tmp/native-out"
                   -v "$NATIVE_WORK_HOST_DIR:/tmp/native-work"
                   "${PLACES365_RO_ARGS[@]}")
i=1
while true; do
  var="EXTRA_MOUNT_$i"
  spec="${!var:-}"
  [[ -z "$spec" ]] && break
  host_path="${spec%%:*}"
  rest="${spec#*:}"
  container_path="${rest%%:*}"
  env_name="${rest#*:}"
  [[ -f "$host_path" ]] || { echo "EXTRA_MOUNT_$i names a missing file: $host_path" >&2; exit 2; }
  DOCKER_MOUNT_ARGS+=(-v "$host_path:$container_path:ro")
  DOCKER_ENV_ARGS+=(-e "$env_name=$container_path")
  i=$((i + 1))
done

# Forward every env var a cfg-*.yaml's `cmd:` block would set. Allow-list, not blanket `-e` of
# the whole environment, so a stray unrelated shell variable never silently reaches the container.
# [Claude 2026-09-07] The first version of this list was built from what a *diagnostic* cfg-*.yaml
# sets, and that silently made the script unable to run the thing it exists for. run_probe.sh
# refuses outright at FRAMES >= 600000 when NATIVE_PRODUCTION is unset (its own line ~404,
# `exit 3`) -- so every production-scale cell, the 600k canary included, would have died after
# paying the full container bootstrap, with the refusal blamed on the config rather than on this
# forwarding list. NATIVE_CONCURRENT was missing for the same reason and silently disabled cell
# packing (run_probe.sh:303 gates the parallel branch on it), which is exactly the capability
# MIGRATION-T4-TO-V100.md step 4 plans to use on this host.
for name in CELLS FRAMES TASK SEED RECORDS_OUT EVAL_EVERY_FRAMES EVAL_EPISODES SAVE_EVERY_FRAMES \
    SAVE_EVERY ENDPOINT_EVAL ENDPOINT_EVAL_REGIMES ENDPOINT_EVAL_SCENES ENDPOINT_EVAL_EPISODES \
    ENDPOINT_EVAL_DEVICE OFFLINE_EVAL_FAMILY OFFLINE_EVAL_BASELINE OFFLINE_EVAL_SEED \
    OFFLINE_EVAL_FRAME OFFLINE_EVAL_DEVICES OFFLINE_EVAL_REGIMES OFFLINE_EVAL_SCENES \
    OFFLINE_EVAL_EPISODES NATIVE_HOST_PROFILE NATIVE_DISABLE_ONLINE_EVAL CUDA_ROOT \
    NATIVE_PRODUCTION NATIVE_PRODUCTION_STRICT NATIVE_CONCURRENT NATIVE_LAUNCHER \
    NATIVE_EXTRA_OVERRIDES NATIVE_NO_TIME_WRAPPER NATIVE_FAMILY \
    NATIVE_PLACES365_SPLIT NATIVE_PLACES365_ACCEPT_VAL PLACES365_EXPECTED_COUNT \
    PLACES365_EXPECTED_SHA256 ENDPOINT_EVAL_POLICY_MODES OFFLINE_EVAL_POLICY_MODES \
    OFFLINE_EVAL_DEVICE OFFLINE_EVAL_EPISODE_SEED OFFLINE_EVAL_SCOPE OFFLINE_EVAL_SNAPSHOT \
    CURVE_EVAL CURVE_EVAL_REGIMES CURVE_EVAL_SCENES CURVE_EVAL_EPISODES CURVE_EVAL_DEVICE \
    CURVE_EVAL_STRICT CURVE_EVAL_DISCARD_WEIGHTS CELL_TIMEOUT_SECONDS CELL_PYTHON \
    NATIVE_CELL_DEVICES NATIVE_ALLOW_CPU NATIVE_ONLINE_EVAL_DISABLED_SPELLING \
    NATIVE_HOST_PROFILE_EXPLICIT RLVIGEN_IMAGE_SIZE RLVIGEN_PLACES_WORKERS \
    CELL_STALL_SECONDS NATIVE_NO_POLICY_HEALTH_WATCH XLA_FLAGS NATIVE_MEMORY_TIER \
    NATIVE_PLACES365_DIR XLA_PYTHON_CLIENT_PREALLOCATE XLA_PYTHON_CLIENT_MEM_FRACTION \
    NATIVE_VRAM_CAP_MIB \
    XLA_PYTHON_CLIENT_ALLOCATOR \
    OMP_NUM_THREADS MKL_NUM_THREADS; do
  value="${!name:-}"
  [[ -n "$value" ]] && DOCKER_ENV_ARGS+=(-e "$name=$value")
done
# RECORDS_OUT inside a cfg-*.yaml names a DataSphere output binding, not a real path -- here it
# must be a real in-container path under /work/out so the host can retrieve it afterward.
DOCKER_ENV_ARGS+=(-e "RECORDS_OUT=/work/out/records.jsonl")

echo "image: $IMAGE" >&2
echo "verify this matches datasphere/native/source-lock.json before trusting the result as a" >&2
echo "platform-only comparison (C95) -- a mismatched image confounds container with host." >&2

INNER_ARGS="${CONTAINER_ARGS[*]}"
# Named deterministically so an operator can reach the running cell:
#   docker exec -it <name> bash            -- a shell beside the training process
#   docker logs -f <name>                  -- the stream this script's stdout also carries
#   docker stats <name>                    -- live memory against the model in families.json
# Without a name Docker assigns a random one, and finding it during an incident means parsing
# `docker ps` against an image every cell shares.
CONTAINER_NAME="${NATIVE_CONTAINER_NAME:-rlvigen-$(basename "${RESULT%.tgz}")-$STAMP}"
echo "container: $CONTAINER_NAME  (docker exec -it $CONTAINER_NAME bash)" >&2

# [Claude 2026-09-08] NATIVE_HOST_DRY_RUN=1 stops here, after every guard, every path check and the
# whole `docker run` argument vector have been built, and before anything is executed.
#
# Why this exists: until now the operator's FIRST execution of this script on the production host
# would have been its first execution ANYWHERE. Its 29 tests all read the source rather than run
# it, and `set -euo pipefail` with `${VAR:?}` means a missing variable, a swapped positional or a
# typo in the forwarded-variable list surfaces as an abort partway through -- on the host, on the
# day, with the campaign waiting. That is precisely the "bad code delays production at the last
# moment" case.
#
# The dry run exercises: positional handling and the archive existence checks, the production-scale
# refusals (NATIVE_PRODUCTION, NATIVE_HOST_PROFILE, CELL_TIMEOUT_SECONDS), the disk headroom
# arithmetic, mount assembly, and the environment forwarding -- everything except Docker and the
# GPU. It prints the exact command it WOULD run, so the operator can read it before it runs.
if [[ -n "${NATIVE_HOST_DRY_RUN:-}" ]]; then
  echo
  echo "=== NATIVE_HOST_DRY_RUN: every guard passed; NOT executing ==="
  echo "image:  $IMAGE"
  echo "gpus:   ${DOCKER_GPUS}$([[ "$DOCKER_GPUS" == "none" ]] && echo '  (--gpus omitted entirely; the container sees no /dev/nvidia*)')"
  echo "mounts: ${#DOCKER_MOUNT_ARGS[@]} argument(s)"
  printf '        %s\n' "${DOCKER_MOUNT_ARGS[@]}"
  echo "env:    ${#DOCKER_ENV_ARGS[@]} argument(s)"
  printf '        %s\n' "${DOCKER_ENV_ARGS[@]}"
  echo
  echo "would run: docker run --rm --name $CONTAINER_NAME ${DOCKER_GPU_ARGS[*]} \\"
  echo "             <mounts> <env> -e MUJOCO_GL=egl -w /work $IMAGE bash -c '<bootstrap+probe>'"
  exit 0
fi

docker run --rm --name "$CONTAINER_NAME" "${DOCKER_GPU_ARGS[@]}" \
  "${DOCKER_MOUNT_ARGS[@]}" "${DOCKER_ENV_ARGS[@]}" \
  -e DEBIAN_FRONTEND=noninteractive -e TZ=Etc/UTC \
  -e MUJOCO_GL=egl \
  -w /work \
  "$IMAGE" \
  bash -c "
    set -euo pipefail
    apt-get -qq update
    apt-get -qq install -y python3 python3-pip git
    mkdir -p code && tar xzf code.tgz -C code
    cd code
    bash datasphere/native/run_probe.sh $INNER_ARGS
  "

cp "$WORKDIR/out/result.tgz" "$RESULT"
if [[ -f "$WORKDIR/out/records.jsonl" ]]; then
  cp "$WORKDIR/out/records.jsonl" "$(dirname "$RESULT")/records.jsonl"
fi
echo "result: $RESULT" >&2
# [Claude 2026-09-08] The second copy the production-scale guard above required. Done AFTER the
# result exists and reported by its own line, so an operator can see whether it happened rather
# than assume it: a mirror that silently did not run is worse than no mirror, because it is
# believed. Failure here does not destroy the primary result, so it warns and continues -- the
# run is finished and its output is on disk either way.
if [[ -n "${NATIVE_RESULT_MIRROR:-}" ]]; then
  if cp "$RESULT" "$NATIVE_RESULT_MIRROR/" 2>/dev/null; then
    if [[ -f "$(dirname "$RESULT")/records.jsonl" ]]; then
      cp "$(dirname "$RESULT")/records.jsonl" "$NATIVE_RESULT_MIRROR/" 2>/dev/null || true
    fi
    echo "mirrored: $NATIVE_RESULT_MIRROR/$(basename "$RESULT")" >&2
  else
    # [Claude 2026-09-08, A55 -- external review 27 sec.13] FATAL, not a warning.
    #
    # This was a warning that let the wrapper exit 0. But production scale REFUSES to start without
    # NATIVE_RESULT_MIRROR, so the second copy is a stated requirement of the run -- and a
    # requirement whose failure is a log line nobody greps is not a requirement. The operator would
    # believe two copies existed.
    #
    # The training output is not lost: $RESULT, $NATIVE_OUT_HOST_DIR and $NATIVE_WORK_HOST_DIR are
    # all on the primary volume and intact. What has failed is the durability contract, so the run
    # reports incomplete and the operator decides.
    echo "FAILED: NATIVE_RESULT_MIRROR copy to $NATIVE_RESULT_MIRROR did not succeed." >&2
    echo "  The primary result at $RESULT is intact and so is $NATIVE_OUT_HOST_DIR." >&2
    echo "  There is NO second copy, which production scale requires. Copy it manually and" >&2
    echo "  re-check, or re-run with a reachable NATIVE_RESULT_MIRROR." >&2
    exit 4
  fi
fi
echo "cell output (training.log, retained artifacts): $NATIVE_OUT_HOST_DIR" >&2
echo "live run directory (checkpoints AS WRITTEN, replay): $NATIVE_WORK_HOST_DIR" >&2
