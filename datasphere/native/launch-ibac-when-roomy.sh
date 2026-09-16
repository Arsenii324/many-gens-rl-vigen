#!/usr/bin/env bash
# Launch the ibac_sni 600k production cell when a card genuinely has room for it -- not before.
#
# [Claude 2026-09-16] It failed twice tonight and the second failure is the instructive one: a
# worker died (EOFError on its pipe) during PPOAlgo construction, with EGL_NOT_INITIALIZED in the
# teardown. ibac_sni at the v100 profile is procs=16, so it builds SIXTEEN MuJoCo/EGL contexts, and
# card 0 had ~5 GB free with two colleagues and three of our own cells on it. The v212 attestation
# ran the same procs=16 successfully -- on a card that was free.
#
# So the requirement is HEADROOM, not a smaller process count. Lowering procs would be the fidelity
# deviation ("Use the upstream IBAC-SNI process count"), not an economy, and the whole reason to run
# this baseline is that it completes the on-policy block honestly.
#
# NEED_MIB is therefore set well above the launcher's own 4000 MiB floor: that floor asks whether
# ONE process can start, and this cell needs sixteen renderers plus the trainer.
set -uo pipefail
NEED_MIB="${NEED_MIB:-14000}"; CARD="${CARD:-0}"; INTERVAL="${INTERVAL:-300}"
LOG="$HOME/rlvigen-runs/ibac-when-roomy.log"
say() { printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
say "waiting for >= ${NEED_MIB} MiB free on card ${CARD} (16 EGL contexts + trainer)"
while :; do
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$CARD" 2>/dev/null)
  ours=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cE "^cell-c${CARD}-[0-9]+$")
  if (( ${free:-0} >= NEED_MIB )); then
    say "card ${CARD} has ${free} MiB free and ${ours} cell(s) of ours -- launching ibac_sni"
    CARD="$CARD" TIMEOUT_S=43200 bash "$HOME/rlvigen-work/train-production-cell-v2.sh" >> "$LOG" 2>&1
    if grep -q "NATIVE_CELL_COMPLETED" "$HOME/rlvigen-runs/prod-v214/ibac_sni-s1-prod.log" 2>/dev/null; then
      say "ibac_sni COMPLETED"; exit 0
    fi
    say "attempt ended without a completion marker; will retry when there is room again"
    sleep 600
  else
    say "waiting: card ${CARD} free=${free} MiB (need ${NEED_MIB}), ours=${ours}"
  fi
  sleep "$INTERVAL"
done
