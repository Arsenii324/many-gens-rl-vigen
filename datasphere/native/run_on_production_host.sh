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
# GPU selection: notes/remote-infra.txt (2026-09-05) recorded GPU 0 occupied by another user
# (15.1 GB, 67% util), GPU 1 free. Re-check with `nvidia-smi` before every run -- that snapshot is
# a week-plus old by the time this runs and the occupant may have changed or left. Default below
# is `--gpus all`; export CUDA_VISIBLE_DEVICES=1 (or whichever index nvidia-smi shows free) to
# pin to one card instead, matching CTRL's own review-14-flagged caution about not assuming a
# packing plan without a real measurement.
set -euo pipefail

IMAGE="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json').read_text())['container_image'])")"

CODE="${1:?usage: $0 PAYLOAD.tgz RESULT.tgz [RLVIGEN.tgz]}"
RESULT="${2:?usage: $0 PAYLOAD.tgz RESULT.tgz [RLVIGEN.tgz]}"
RLVIGEN_ARCHIVE_HOST="${3:-}"

[[ -f "$CODE" ]] || { echo "no such payload archive: $CODE" >&2; exit 2; }
[[ -z "$RLVIGEN_ARCHIVE_HOST" || -f "$RLVIGEN_ARCHIVE_HOST" ]] || {
  echo "no such RL-ViGen archive: $RLVIGEN_ARCHIVE_HOST" >&2; exit 2; }

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
mkdir -p "$WORKDIR/out"
cp "$CODE" "$WORKDIR/code.tgz"
CONTAINER_ARGS=(/work/code.tgz /work/out/result.tgz)
if [[ -n "$RLVIGEN_ARCHIVE_HOST" ]]; then
  cp "$RLVIGEN_ARCHIVE_HOST" "$WORKDIR/rlvigen.tgz"
  CONTAINER_ARGS+=(/work/rlvigen.tgz)
fi

# Extra file mounts (checkpoints, etc.) declared as HOST_PATH:CONTAINER_PATH:ENV_VAR_NAME triples
# in EXTRA_MOUNT_1, EXTRA_MOUNT_2, ... -- mirrors a cfg-*.yaml's `inputs:` list entries beyond the
# three standard ones above (e.g. `datasphere/native/s2-snapshot-100000.pt: SNAP` becomes
# `EXTRA_MOUNT_1=datasphere/native/s2-snapshot-100000.pt:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT`).
DOCKER_ENV_ARGS=()
DOCKER_MOUNT_ARGS=(-v "$WORKDIR:/work")
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
for name in CELLS FRAMES TASK SEED RECORDS_OUT EVAL_EVERY_FRAMES EVAL_EPISODES SAVE_EVERY_FRAMES \
    ENDPOINT_EVAL ENDPOINT_EVAL_REGIMES ENDPOINT_EVAL_SCENES ENDPOINT_EVAL_EPISODES \
    ENDPOINT_EVAL_DEVICE OFFLINE_EVAL_FAMILY OFFLINE_EVAL_BASELINE OFFLINE_EVAL_SEED \
    OFFLINE_EVAL_FRAME OFFLINE_EVAL_DEVICES OFFLINE_EVAL_REGIMES OFFLINE_EVAL_SCENES \
    OFFLINE_EVAL_EPISODES NATIVE_HOST_PROFILE NATIVE_DISABLE_ONLINE_EVAL CUDA_ROOT; do
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
docker run --rm --gpus "${DOCKER_GPUS:-all}" \
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
