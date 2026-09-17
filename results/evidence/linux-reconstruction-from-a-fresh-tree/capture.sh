#!/usr/bin/env bash
# Recipe for this bundle.
#
# The evidence is one container's output, and the container is what proves the claim, so the run
# itself is step 1 and is kept OFF by default: it clones several upstreams over the host's network,
# uses about 1.7 GB of shared disk, and takes ten minutes. `container-run.log` beside this script is
# the output of the run of 2026-09-17, and step 2 re-cuts the excerpt from it.
#
#   bash capture.sh            # re-cut the excerpt from the stored log
#   RERUN=1 bash capture.sh    # do the whole thing again on the host, then re-cut
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=linux-reconstruction-from-a-fresh-tree
B=results/evidence/$S
HOST=${HOST:-varaksin_as@100.98.2.11}

if [ "${RERUN:-0}" = "1" ]; then
  # ship the COMMITTED tree -- what a fresh clone holds -- and reconstruct inside a container
  git archive --format=tar HEAD | gzip -c > /tmp/tree-HEAD.tgz
  ssh -o BatchMode=yes "$HOST" 'mkdir -p ~/bootstrap-test'
  scp -o BatchMode=yes -q /tmp/tree-HEAD.tgz "$HOST":bootstrap-test/tree.tgz
  ssh -o BatchMode=yes "$HOST" 'bash -s' > "$B/container-run.log" <<'REMOTE'
set -u
W="$HOME/bootstrap-test"; rm -rf "$W/repo"; mkdir -p "$W/repo"
echo "=== free before: $(df -Pk "$HOME" | awk 'NR==2{printf "%d GiB", $4/1048576}') ==="
timeout 3000 docker run --rm --memory 4g -v "$W:/work" -w /work python:3.11-slim bash -c '
set -e
apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq git >/dev/null 2>&1; git --version
tar xzf /work/tree.tgz -C /work/repo; cd /work/repo
echo "=== tree: $(git ls-files 2>/dev/null | wc -l) files (no .git expected), runnable present? $(ls -d runnable 2>/dev/null || echo no) ==="
echo "=== bootstrap_sources.py ==="; time python3 setup/bootstrap_sources.py; echo "bootstrap rc=$?"
echo "=== du after ==="; du -sh runnable RL-ViGen-upstream ext 2>/dev/null
echo "=== verify_sources.py ==="; python3 setup/verify_sources.py; echo "verify rc=$?"
'
echo "=== docker rc=$? ==="
echo "=== free after: $(df -Pk "$HOME" | awk 'NR==2{printf "%d GiB", $4/1048576}') | bootstrap-test size: $(du -sh "$W" 2>/dev/null | cut -f1) ==="
REMOTE
  ssh -o BatchMode=yes "$HOST" 'rm -rf ~/bootstrap-test'   # our own scratch, by exact name
fi

C $S container-run --command "cat $B/container-run.log" \
  --grep 'git version|tree:|bootstrap_sources|bootstrap rc|real|runnable|RL-ViGen-upstream|verify_sources|verify rc|docker rc|free' --max 25 \
  --note "python:3.11-slim on the production host, against the repository's committed tree shipped as a 37 MB archive. Closes the half of OPERATOR-GUIDE 11.4 O8 a macOS laptop cannot test: bootstrap_sources.py refuses on a case-insensitive filesystem." \
  --fact bootstrap_rc=0 --anchor 'bootstrap rc=0' \
  --fact verify_rc=0 --anchor 'verify rc=0' \
  --fact wall_clock=9m40.266s --anchor 'real	9m40.266s' \
  --fact runnable_size=408M --anchor '408M	runnable'

# The second excerpt: the same fresh tree taken all the way to verified payloads. Its own run is
# `linux-clone-to-payload`, kept beside this script as clone-to-payload.log for the same reason.
C $S clone-to-payload --command "cat $B/clone-to-payload.log" \
  --grep 'reconstruct|bootstrap rc|verify_sources rc|RUNNER_CONTRACT|payload |docker rc' --max 20 \
  --note "fresh tree -> reconstruct -> build-payload + verify-payload + verify-evaluator-binding for all seven families, in one container on the host" \
  --fact families_all_zero=7 --anchor 'payload ctrl      build=0 verify=0 binding=0' \
  --fact runner_contract=19 --anchor 'RUNNER_CONTRACT = 19'
