#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
# Needs the production host to still hold the three card1 run directories of 2026-09-16/17.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=only-a-training-cell-obeys-the-sentinel

C $S sentinel-grid-ibac --host-path '~/rlvigen-runs/card1-20260916-203537/native-work/yield.sentinel' \
  --note "ibac_sni s101, PAST training and in its endpoint grid: its watcher wrote a sentinel and the cell ignored it" \
  --fact grid_ibac_free_mib=2365 --anchor 'free_mib=2365'

C $S sentinel-grid-idaac --host-path '~/rlvigen-runs/card1-20260916-213222/native-work/yield.sentinel' \
  --note "idaac s102, PAST training and in its curve grid: its watcher wrote a sentinel and the cell ignored it" \
  --fact grid_idaac_free_mib=321 --anchor 'free_mib=321'

C $S sentinel-training-cell --host-path '~/rlvigen-runs/card1-20260917-075047/native-work/yield.sentinel' \
  --note "ibac_sni s102, the only cell still TRAINING: same event, and this is the one that died" \
  --fact training_cell_free_mib=75 --anchor 'free_mib=75'

C $S training-cell-stopped --host-path '~/rlvigen-runs/prod-v214/ibac_sni-s102-prod.log' \
  --grep 'NATIVE_CELL_(YIELDED|FAILED)' --only-matching --max 4 \
  --note "the training cell's own log: it announced the yield and stopped" \
  --fact training_cell_marker=NATIVE_CELL_YIELDED --anchor 'NATIVE_CELL_YIELDED'

C $S grids-still-running --command "ssh -o BatchMode=yes varaksin_as@100.98.2.11 'docker ps --format \"{{.Names}} {{.Status}}\" | grep -E \"^cell-c1-(1437491|1567571) \"'" \
  --note "taken after the event: both grid cells are still up, having ignored their sentinels" \
  --fact grid_cells_still_up=2 --anchor 'cell-c1-1437491'
