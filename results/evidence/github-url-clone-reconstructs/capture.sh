#!/usr/bin/env bash
# Recipe for this bundle.
#
# The evidence is one container's output, and the container is what proves the claim, so the run
# itself is step 1 and is kept OFF by default: it clones the real GitHub URL over the host's
# network, uses about 1.7 GB of shared disk, and takes a few minutes. `container-run.log` beside
# this script is the output of the run of 2026-09-18; step 2 re-cuts the excerpt from it.
#
# This is deliberately NOT the same test as `linux-reconstruction-from-a-fresh-tree`, which ships
# the committed tree as a `git archive HEAD` tarball. That proves the TREE reconstructs; it never
# exercises `git clone` itself -- auth, network reachability from an arbitrary host, `.gitattributes`,
# line endings, any of it. This bundle clones the literal published URL.
#
#   bash capture.sh            # re-cut the excerpt from the stored log
#   RERUN=1 bash capture.sh    # do the whole thing again on the host, then re-cut
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=github-url-clone-reconstructs
B=results/evidence/$S
HOST=${HOST:-varaksin_as@100.98.2.11}
URL=${URL:-https://github.com/Arsenii324/many-gens-rl-vigen.git}

if [ "${RERUN:-0}" = "1" ]; then
  ssh -o BatchMode=yes "$HOST" 'mkdir -p ~/github-clone-test'
  ssh -o BatchMode=yes "$HOST" 'bash -s' > "$B/container-run.log" <<REMOTE
set -u
W="\$HOME/github-clone-test"
echo "=== free before: \$(df -Pk "\$HOME" | awk 'NR==2{printf "%d GiB", \$4/1048576}') ==="
timeout 3600 docker run --rm --memory 4g -v "\$W:/work" -w /work python:3.11-slim bash -c '
set -e
apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq git >/dev/null 2>&1; git --version
echo "=== cloning the REAL github url (not a shipped archive) ==="
time git clone --quiet $URL /work/repo
cd /work/repo
echo "=== HEAD: \$(git log --oneline -1) on branch \$(git branch --show-current) ==="
echo "=== tree: \$(git ls-files 2>/dev/null | wc -l) tracked files, runnable present pre-bootstrap? \$(ls -d runnable 2>/dev/null || echo no) ==="
echo "=== bootstrap_sources.py ==="; time python3 setup/bootstrap_sources.py; echo "bootstrap rc=\$?"
echo "=== du after ==="; du -sh runnable RL-ViGen-upstream ext 2>/dev/null
echo "=== verify_sources.py ==="; python3 setup/verify_sources.py; echo "verify rc=\$?"
'
echo "=== docker rc=\$? ==="
echo "=== free after: \$(df -Pk "\$HOME" | awk 'NR==2{printf "%d GiB", \$4/1048576}') | github-clone-test size: \$(du -sh "\$W" 2>/dev/null | cut -f1) ==="
REMOTE
  # our own scratch, by exact name -- files are root-owned so removal goes through a container
  ssh -o BatchMode=yes "$HOST" "docker run --rm -v ~/github-clone-test:/target python:3.11-slim rm -rf /target/repo && rmdir ~/github-clone-test"
fi

C $S container-run --command "cat $B/container-run.log" \
  --grep 'git version|cloning the REAL|real|HEAD:|tree:|bootstrap_sources|bootstrap rc|runnable|RL-ViGen-upstream|verify_sources|verify rc|docker rc|free' --max 25 \
  --note "python:3.11-slim on the production host, cloning the LITERAL published GitHub URL (not a shipped tree) and reconstructing inside the container." \
  --fact clone_head=c507b5e --anchor 'HEAD: c507b5e' \
  --fact bootstrap_rc=0 --anchor 'bootstrap rc=0' \
  --fact verify_rc=0 --anchor 'verify rc=0' \
  --fact tracked_files=1566 --anchor 'tree: 1566 tracked files'
