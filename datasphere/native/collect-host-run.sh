#!/usr/bin/env bash
# Install a HOST run's records and populate the evaluator ledger, refusing rather than skipping.
#
#     bash datasphere/native/collect-host-run.sh idaac ~/rlvigen-runs/card0-20260909-025431
#
# [Claude 2026-09-09] `collect-wave.sh` is the DataSphere equivalent and cannot be used here: it
# calls `datasphere project job get` to check the job reached SUCCESS, and a host run has no job at
# all. What it does have is a run directory, and every fact that collector checks is present there
# in a different form -- so this is the same discipline against different evidence.
#
# The `job_id` the ledger keys on becomes the run directory's basename (`card0-<timestamp>`), which
# is unique per launch and carries the date, so a record can always be traced back to the directory
# it came from.
set -uo pipefail
cd "$(dirname "$0")/../.."
BP="${BP:-python3}"

FAMILY="${1:?usage: collect-host-run.sh <family> <run-dir>}"
RUN_DIR="${2:?usage: collect-host-run.sh <family> <run-dir>}"
JOB_ID="$(basename "${RUN_DIR%/}")"
SRC="$RUN_DIR/native-out/records.jsonl"
DEST="results/records/${JOB_ID}__records.jsonl"

echo "=== $FAMILY  $JOB_ID"

# 1. The run must have SUCCEEDED. A host run has no job status, so the runner's own markers are the
#    evidence: NATIVE_CELL_COMPLETED for every cell, and no NATIVE_CELL_FAILED anywhere.
LOG="$RUN_DIR/native-out/job.log"
if [[ ! -f "$LOG" ]]; then
  echo "   REFUSING: no job.log at $LOG. Nothing to judge the run by." >&2
  exit 2
fi
if grep -q "NATIVE_CELL_FAILED" "$LOG"; then
  echo "   REFUSING: the log carries NATIVE_CELL_FAILED:" >&2
  grep "NATIVE_CELL_FAILED" "$LOG" | sed 's/^/      /' >&2
  echo "   A failed cell's records describe a run that did not finish, and collecting them would" >&2
  echo "   put a partial result beside complete ones with nothing to tell them apart." >&2
  exit 1
fi
if ! grep -q "NATIVE_CELL_COMPLETED" "$LOG"; then
  echo "   REFUSING: no NATIVE_CELL_COMPLETED marker. The cell did not report completion." >&2
  exit 1
fi
echo "   completed: $(grep -c 'NATIVE_CELL_COMPLETED' "$LOG") cell(s)"

# 2. The renderer must have been real. A record produced by llvmpipe is not comparable with any
#    other record this project holds, and on 2026-09-08 that was one missing capability away.
EGL="$RUN_DIR/native-out/egl.json"
if [[ -f "$EGL" ]]; then
  if grep -qiE "llvmpipe|softpipe|swiftshader" "$EGL"; then
    echo "   REFUSING: this run rendered in SOFTWARE:" >&2
    sed 's/^/      /' "$EGL" >&2
    exit 1
  fi
  echo "   renderer: $($BP -c 'import json,sys;print(json.load(open(sys.argv[1])).get("renderer"))' "$EGL" 2>/dev/null)"
else
  echo "   NOTE: no egl.json; the renderer is unverified for this run." >&2
fi

# 3. Records must exist and be non-empty. SUCCESS with no records is itself a finding.
if [[ ! -s "$SRC" ]]; then
  echo "   REFUSING: $SRC is absent or empty. A completed cell that produced no records is a" >&2
  echo "   finding, not an empty result to file away." >&2
  exit 1
fi
mkdir -p results/records
cp "$SRC" "$DEST"
echo "   installed $(wc -l < "$SRC" | tr -d ' ') record rows -> $DEST"

# 4. The ledger REFUSES a stale evaluator revision, and that refusal is the most valuable thing it
#    does. Capture the status explicitly: piping it through `tail` would discard the exit code and
#    print "Do NOT write this entry" while exiting 0.
out="$("$BP" scripts/populate_evaluator_ledger.py "$FAMILY" "$JOB_ID" 2>&1)"
status=$?
printf '%s\n' "$out" | tail -3 | sed 's/^/   /'
if [[ $status -ne 0 ]] || printf '%s' "$out" | grep -q "Do NOT write this entry"; then
  echo "   REFUSED by the ledger: this record does not describe the current tree." >&2
  exit 1
fi

echo
"$BP" scripts/production_gates.py 2>&1 | grep -iE "shared evaluator validated" | cut -c1-200
