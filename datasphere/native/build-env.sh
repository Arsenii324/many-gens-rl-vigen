#!/usr/bin/env bash
# Build ONE reusable environment for a stack, once, into our own directory, from inside the pinned
# image. Every later cell mounts it read-only and skips `pip` entirely.
#
#     CELLS=idaac:1 PAYLOAD=~/rlvigen-work/payload-idaac-c19.tgz \
#       bash datasphere/native/build-env.sh
#
# [Claude 2026-09-08] Rationale, measurements and the rejected alternatives are in
# notes/production-host/19-environment-lifecycle-vs-run-lifecycle.md. The short version: `apt` is 71
# seconds and `pip` is over two hours, none of it survives the container, and there are exactly TWO
# distinct requirement sets across the twelve baselines -- so two venvs replace ~1710 MB of download
# per cell with ~1710 MB once.
#
# THE VENV IS BUILT AT THE PATH IT WILL BE MOUNTED AT (/opt/rlvigen-env). A venv's `bin/python`
# shebang and its `pyvenv.cfg` carry absolute paths, so a venv built somewhere else and mounted here
# is subtly broken in ways that surface late.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CELLS="${CELLS:?set CELLS, e.g. idaac:1 -- it selects which of the two requirement sets to build}"
PAYLOAD="${PAYLOAD:?set PAYLOAD: the editable installs are baked from the payload tree}"
ENV_ROOT="${NATIVE_ENV_ROOT:-$HOME/rlvigen-env}"
IMAGE="${NATIVE_IMAGE:?set NATIVE_IMAGE to the digest-pinned base image the cells run under}"
PIP_CACHE="${NATIVE_PIP_CACHE_HOST:-$HOME/.cache/pip-rlvigen}"

case "$ENV_ROOT" in "$HOME"/*) : ;; *) echo "refusing: NATIVE_ENV_ROOT must be under \$HOME" >&2; exit 2 ;; esac
[[ -f "$PAYLOAD" ]] || { echo "refusing: no payload at $PAYLOAD" >&2; exit 2; }

# The stack name is derived, not chosen: ctrl is the JAX stack, everything else is torch. If a
# third stack ever appears, `filtered-requirements` will hash differently and the directory name
# will say so -- the hash is the identity, the name is only for humans.
stack=torch
[[ "$CELLS" == *ctrl* ]] && stack=jax

echo "resolving the requirement set for $CELLS ..."
# Resolved in the HELPER image, not the CUDA one. `family.py` is pure Python and only reads the
# repo, while the CUDA image ships no python3 -- so resolving there apt-installs an interpreter
# inside a throwaway container on every build, for a step that takes milliseconds.
reqs="$(docker run --rm -v "$REPO:/repo:ro" -w /repo "${NATIVE_HELPER_IMAGE:-python:3.11-slim}" \
  python3 datasphere/native/family.py filtered-requirements --cells "$CELLS" \
    --requirements requirements-native.txt 2>/dev/null)"
[[ -n "$reqs" ]] || { echo "refusing: could not resolve the requirement set" >&2; exit 3; }
reqhash="$(printf '%s' "$reqs" | sort | shasum -a 256 2>/dev/null | cut -c1-8 || printf '%s' "$reqs" | sort | sha256sum | cut -c1-8)"

digest="$(printf '%s' "$IMAGE" | sed -n 's/.*sha256:\([0-9a-f]\{12\}\).*/\1/p')"
[[ -n "$digest" ]] || { echo "refusing: NATIVE_IMAGE is not digest-pinned; a venv keyed to a moving tag goes stale silently" >&2; exit 2; }

TARGET="$ENV_ROOT/${stack}-${reqhash}-${digest}"
if [[ -d "$TARGET" ]]; then
  echo "already built: $TARGET"
  echo "(delete it to rebuild: rm -rf that directory -- the build chowns it back to you)"
  exit 0
fi
mkdir -p "$TARGET" "$PIP_CACHE" || exit 2
echo "building:  $TARGET"
echo "stack:     $stack   requirements $reqhash   image $digest"

# The payload is extracted to /tmp/native-work because that is where a CELL extracts it, and the two
# editable installs bake an absolute path pointing there. Build path and run path must agree.
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/rlvigen-envbuild-XXXXXX")" || exit 2
cleanup() { docker run --rm -v "$STAGE:/s" "$IMAGE" rm -rf /s/. 2>/dev/null; rmdir "$STAGE" 2>/dev/null; }
trap cleanup EXIT
cp "$PAYLOAD" "$STAGE/code.tgz" || exit 2

docker run --rm \
  -v "$TARGET:/opt/rlvigen-env" \
  -v "$STAGE:/stage" \
  -v "$PIP_CACHE:/root/.cache/pip" \
  -v "$REPO:/repo:ro" \
  -e DEBIAN_FRONTEND=noninteractive -e TZ=Etc/UTC \
  -e RLVIGEN_BUILD_IMAGE="$IMAGE" \
  -e RLVIGEN_BUILD_CELLS="$CELLS" \
  -e RLVIGEN_BUILD_REQHASH="$reqhash" \
  -e RLVIGEN_BUILD_UID="$(id -u)" -e RLVIGEN_BUILD_GID="$(id -g)" \
  "$IMAGE" bash -c '
set -euo pipefail
apt-get -qq update
apt-get -qq install -y python3 python3-pip python3-venv git libglvnd0 libgl1 libegl1 \
  libglew-dev libosmesa6 libglib2.0-0 libsm6 libxext6 libxrender1 >/dev/null
mkdir -p /tmp/native-work
tar --no-same-owner -xzf /stage/code.tgz -C /tmp/native-work
cd /tmp/native-work

python3 -m venv /opt/rlvigen-env
. /opt/rlvigen-env/bin/activate
python3 -m pip install --upgrade pip

python3 datasphere/native/family.py filtered-requirements --cells "'"$CELLS"'" \
  --requirements requirements-native.txt > /tmp/reqs.txt
python3 -m pip install -r /tmp/reqs.txt

# The two editable installs, baked. They write an absolute path into site-packages; that path is
# /tmp/native-work/... which is a BIND MOUNT at run time, so each cell supplies its own tree behind
# the same string. The venv holds the pointer, the payload holds the code.
if [[ -d RL-ViGen-upstream ]]; then
  python3 -m pip install --no-deps -e RL-ViGen-upstream/third_party/robosuite
  python3 -m pip install --no-deps -e RL-ViGen-upstream/envs/robosuiteVGB
else
  echo "NOTE: no RL-ViGen-upstream in this payload; the editable installs are NOT baked." >&2
  echo "      A cell using this venv must supply them itself." >&2
fi

python3 - <<PY
import json, os, subprocess, sys, datetime
pkgs = {}
out = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"],
                     capture_output=True, text=True).stdout
for row in json.loads(out or "[]"):
    pkgs[row["name"]] = row["version"]
json.dump({
    "built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base_image": os.environ.get("RLVIGEN_BUILD_IMAGE", ""),
    "cells": os.environ.get("RLVIGEN_BUILD_CELLS", ""),
    "requirements_sha256_8": os.environ.get("RLVIGEN_BUILD_REQHASH", ""),
    "python": sys.version,
    "venv_path": "/opt/rlvigen-env",
    "resolved_packages": pkgs,
    "editable": sorted(p for p in pkgs if p.lower() in ("robosuite", "robosuitevgb")),
}, open("/opt/rlvigen-env/ENVIRONMENT.json", "w"), indent=1, sort_keys=True)
print("wrote ENVIRONMENT.json with", len(pkgs), "packages")
PY

# [Claude 2026-09-08] Hand the tree back to the invoking user. The container runs as root -- the
# images declare no USER and apt-get needs it -- so everything created here lands root-owned on a
# bind mount, and the operator cannot `rm -rf` their own environment to rebuild it. Found by smoke
# test: the cleanup failed with Permission denied on every file, which also falsified the
# "delete it to rebuild" message above. Without the chown the directory can be removed only by
# launching another container, which is a trap to leave in an operator path.
chown -R "${RLVIGEN_BUILD_UID}:${RLVIGEN_BUILD_GID}" /opt/rlvigen-env
'
status=$?

if [[ $status -ne 0 ]]; then
  echo "BUILD FAILED (exit $status). Removing the half-built directory: a partial venv that reads" >&2
  echo "as a complete one is exactly the failure this design exists to prevent." >&2
  docker run --rm -v "$ENV_ROOT:/envs" "$IMAGE" rm -rf "/envs/$(basename "$TARGET")"
  exit "$status"
fi
echo "built: $TARGET"
echo "mount it read-only at /opt/rlvigen-env and set NATIVE_VENV=/opt/rlvigen-env"
