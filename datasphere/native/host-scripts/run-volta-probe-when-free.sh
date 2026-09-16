#!/usr/bin/env bash
# Wait for card 0 to be free of OUR cells, then run the JAX/Volta probe once.
# Read-only mount: the probe writes nothing, so host-run.sh's disk-bound guard does not apply.
set -uo pipefail
cd $HOME/rlvigen-work/repo
waited=0
while [[ -n "$(docker ps -q --filter 'name=cell-c0-')" ]]; do
  sleep 60; waited=$((waited+60))
  [[ $waited -gt 10800 ]] && { echo "gave up waiting for card 0 after 3h"; exit 1; }
done
echo "=== $(date +%H:%M:%S) card 0 free; running the JAX/Volta probe ==="
bash datasphere/native/host-run.sh -r -g "device=0" -n volta-probe ~/rlvigen-work/jax-volta-probe.sh
echo "=== $(date +%H:%M:%S) probe rc=$? ==="
