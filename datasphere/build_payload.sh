#!/usr/bin/env bash
# Build code.tgz: this repo's SOURCE only. RL-ViGen upstream is NOT shipped -- the box clones it.
#
# WHY NOT SHIP UPSTREAM. It is 1.8 GB, and more importantly `requirements.txt` records that the
# PyPI robosuite of the same version number differs from RL-ViGen's vendored fork in 761 files,
# with `Custom01..Custom40` texture names resolved through XML only the fork carries. So the
# sibling project's trick -- pip install robosuite and overlay a handful of files -- is not
# available to us: our verified install path (setup/install.sh) installs the fork editable. The
# box therefore reproduces that path rather than approximating it, and it clones on cloud
# bandwidth instead of our uplink.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:?path to the many-gens-rl-vigen repo}"
OUT="$REPO/code.tgz"

cd "$SRC"
# Everything the box needs to run rlgen + its tests, and nothing that is regenerable or huge.
tar czf "$OUT" \
  --exclude='.git' \
  --exclude='RL-ViGen-upstream' \
  --exclude='.venv' \
  --exclude='logs' \
  --exclude='artifacts' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  rlgen tests setup configs baselines mutants plot.py requirements.txt \
  README.md instruction.md docs

echo "built $OUT: $(wc -c < "$OUT" | tr -d ' ') bytes"
tar tzf "$OUT" | wc -l | xargs echo "members:"
# Fail if the payload is implausibly small -- a mistyped path in the tar line above would
# otherwise produce a tarball that uploads fine and fails on the box ten minutes later.
SZ=$(wc -c < "$OUT" | tr -d ' ')
[ "$SZ" -gt 100000 ] || { echo "!! payload is only $SZ bytes -- something did not get packed"; exit 1; }
for must in rlgen/envs.py setup/apply_patches.py rlgen/protocol.py requirements.txt; do
  tar tzf "$OUT" | grep -qx "$must" || { echo "!! $must missing from payload"; exit 1; }
done
echo "payload verified to contain the files the job depends on"
