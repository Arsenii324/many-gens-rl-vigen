#!/usr/bin/env bash
# Build code-clone.tgz for the CLONE-ERA jobs: enough to run a baseline through its OWN launcher.
#
# Different payload from build_payload.sh, which packs the port-era set (rlgen tests configs
# baselines mutants) because that is what its job needs. This one ships what the twelve actually
# run through: setup/ to clone and patch RL-ViGen, runnable/_launch/ for the entry points, and
# runnable/_shim/ because rlvigen.sh puts it on PYTHONPATH (it is inert off macOS, and shipping it
# keeps the remote command byte-identical to the local one rather than a re-derivation).
#
# RL-ViGen upstream is NOT shipped -- 1.8 GB, and the box clones it at the pinned commit on cloud
# bandwidth. Same reasoning as build_payload.sh, which explains why the PyPI robosuite cannot
# substitute for the vendored fork.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/.." && pwd)"
OUT="$HERE/code-clone.tgz"

cd "$SRC"
tar czf "$OUT" \
  --exclude='__pycache__' --exclude='*.pyc' \
  setup runnable/_launch runnable/_shim scripts rlgen requirements.txt

echo "built $OUT: $(wc -c < "$OUT" | tr -d ' ') bytes"
# A mistyped path above would upload fine and fail on the box twenty minutes later, so the
# members the job depends on are asserted here rather than discovered remotely.
for must in setup/apply_patches.py runnable/_launch/rlvigen.sh rlgen/protocol.py requirements.txt; do
  tar tzf "$OUT" | grep -qx "$must" || { echo "!! $must missing from payload"; exit 1; }
done
echo "payload verified to contain the files the job depends on"
