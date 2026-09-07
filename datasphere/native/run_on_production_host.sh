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

IMAGE="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json').read_text())['container_image'])")"

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
  free_gb="$(df -Pk "$target" 2>/dev/null | awk 'NR==2 {printf "%d", $4 / 1048576}')" || return 0
  [[ -n "$free_gb" ]] || return 0
  if [[ -n "${NATIVE_DISK_FLOOR_GB:-}" ]]; then
    required="$NATIVE_DISK_FLOOR_GB"
  else
    required="$(python3 datasphere/native/family.py disk-requirement \
        --cells "${CELLS:-drqv2:1}" --frames "${FRAMES:-10000}" 2>/dev/null \
        | python3 -c 'import json,sys; print(int(json.load(sys.stdin)["required_gib"] + 0.999))' \
        2>/dev/null)" || required=""
    [[ -n "$required" ]] || required=60
  fi
  echo "free disk at $target: ${free_gb} GB (this job needs ~${required} GB)" >&2
  if [[ "$free_gb" -lt "$required" ]]; then
    echo "refusing: ${free_gb} GB free at $target, below the ${required} GB this job needs." >&2
    echo "  Breakdown: python3 datasphere/native/family.py disk-requirement --cells ${CELLS:-drqv2:1} --frames ${FRAMES:-10000}" >&2
    echo "  Replay episode files dominate for off-policy cells; on-policy cells need a fraction." >&2
    echo "  Free space, or set NATIVE_DISK_FLOOR_GB to override with a number you have justified." >&2
    exit 4
  fi
}

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
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
check_disk "$NATIVE_WORK_HOST_DIR"
DOCKER_MOUNT_ARGS=(-v "$WORKDIR:/work"
                   -v "$NATIVE_OUT_HOST_DIR:/tmp/native-out"
                   -v "$NATIVE_WORK_HOST_DIR:/tmp/native-work")
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
    NATIVE_HOST_PROFILE_EXPLICIT RLVIGEN_IMAGE_SIZE OMP_NUM_THREADS MKL_NUM_THREADS; do
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

docker run --rm --name "$CONTAINER_NAME" --gpus "${DOCKER_GPUS:-all}" \
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
echo "cell output (training.log, retained artifacts): $NATIVE_OUT_HOST_DIR" >&2
echo "live run directory (checkpoints AS WRITTEN, replay): $NATIVE_WORK_HOST_DIR" >&2
