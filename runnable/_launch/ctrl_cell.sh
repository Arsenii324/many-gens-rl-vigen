#!/usr/bin/env bash
# [Claude 2026-09-02 09:40 MSK] One CTRL cell: train to the budget, keep the console curve, emit the
# marker its own trainer now prints.
#
# Two things about CTRL make a wrapper necessary rather than optional.
#
# 1. `train_ppo.py` ends with `app.run(main)` and `main` returns a tuple, so absl calls
#    `sys.exit(<tuple>)` and the process exits 1 on SUCCESS. That is documented in this project's
#    own smoke_all.sh. A non-zero exit therefore cannot be the failure signal here, so this script
#    uses the artifacts instead: the endpoint marker must be in the log AND a checkpoint must exist.
#    Any other non-zero exit still fails, because neither will be there.
# 2. CTRL logs its metrics through wandb, which does not run on DataSphere and is not worked around
#    there. What survives is the per-log-step `Eprew200 / Eprew0 / SR_ID / SR_OOD` line it prints --
#    which is also the only place its online out-of-distribution measurement appears. That line is
#    the curve, so it is tee'd into a file inside the run directory rather than left in the job log.
set -euo pipefail
TASK="${1:?task}"; NENV="${2:?num envs}"; RUN_DIR="${3:?run directory}"; shift 3

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$RUN_DIR"
CONSOLE="$RUN_DIR/train_console.log"

set +e
bash "$HERE/ctrl.sh" "$TASK" "$NENV" "$@" 2>&1 | tee "$CONSOLE"
training_status="${PIPESTATUS[0]}"
set -e

if ! grep -q "NATIVE_FINAL_EVALUATION_COMPLETED frame=" "$CONSOLE"; then
  echo "ctrl did not reach its endpoint (trainer status $training_status)" >&2
  exit 1
fi
# re-emit on stdout: run_measured's tee owns training.log, and the marker must appear there too
grep -h "NATIVE_FINAL_EVALUATION_COMPLETED frame=" "$CONSOLE" | tail -1
