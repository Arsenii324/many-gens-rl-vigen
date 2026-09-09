#!/usr/bin/env bash
# Install a HOST run's records and populate the evaluator ledger, refusing rather than skipping.
#
#     bash datasphere/native/collect-host-run.sh idaac ./fetched/card0-20260909-035152
#
# [Claude 2026-09-09] `collect-wave.sh` is the DataSphere equivalent and cannot be used here: it
# calls `datasphere project job get` to check the job reached SUCCESS, and a host run has no job at
# all. What it does have is a run directory, and every fact that collector checks is present there
# in a different form -- so this is the same discipline against different evidence.
#
# The `job_id` the ledger keys on becomes the run directory's basename (`card0-<timestamp>`), which
# is unique per launch and carries the date, so a record can always be traced back to the directory
# it came from.
#
# ## RUN_DIR IS A LOCAL COPY, not a path on the production host
#
# This script writes into `results/records/` and runs repo Python. Neither may happen on the host:
# the standing rule there is docker operations and trivial shell only. Fetch first, collect here:
#
#     rsync -a --exclude 'native-work' \
#       varaksin_as@100.98.2.11:'~/rlvigen-runs/card0-20260909-035152' ./fetched/
#
# `native-work` is excluded because it holds the checkpoints -- gigabytes, and not what the ledger
# needs. `scripts/audit_record_frame_provenance.py` DOES need them, so fetch that subtree separately
# when auditing frame labels rather than dragging it through every collection.
#
# ## The source file, which the first version of this script got wrong
#
# [Claude 2026-09-09] It read `native-out/records.jsonl`. **No completed host run has that file.**
# `normalize_curves.py` writes per-cell rows to `records.jsonl`; the delivered bundle -- those rows
# PLUS every offline evaluation row from `cells/<cell>/offline_eval_*.jsonl` -- is assembled by
# `collect_record_delivery` into `records_delivery.jsonl`.
#
# Measured on completed runs, 2026-09-09. On `card0-20260909-005543`, `records_delivery.jsonl` holds
# **6 rows (2 eval + 4 offline-eval)** and matches that run's `NATIVE_RECORDS_EMITTED 6 rows` exactly,
# while `records.jsonl` holds **2 rows and no offline-eval rows at all**. On three other completed
# runs `records.jsonl` does not exist. Either way it is never the bundle.
#
# Byte sizes mislead here and are worth not trusting: the bundle was 1.39 MB against records.jsonl's
# 12.9 KB, which looks like a 100x row difference and is not one. Delivery rows carry
# `_run_provenance` -- manifest, payload and asset digests, resolved packages -- at roughly 231 KB
# per row. Count rows, never bytes.
#
# The failure was fail-closed by luck rather than by design: an absent file trips the `-s` test and
# refuses, so nothing would have been silently lost. Had `records.jsonl` merely been *incomplete*
# instead of absent, this collector would have installed training rows, dropped 528 evaluation rows,
# and printed success. `run_probe.sh` carries a comment about that exact failure one directory level
# down; it recurred here because a collector's source is a claim about the runner, and claims about
# other components go stale.
#
# So the two checks below do not just read the right file -- they check the choice of file against
# evidence this script does not control. That is the only version of the fix that survives the
# runner changing again.
set -uo pipefail
cd "$(dirname "$0")/../.."
BP="${BP:-python3}"
RECORDS_DIR="${RECORDS_DIR:-results/records}"

FAMILY="${1:?usage: collect-host-run.sh <family> <run-dir>}"
RUN_DIR="${2:?usage: collect-host-run.sh <family> <run-dir>}"
JOB_ID="$(basename "${RUN_DIR%/}")"
SRC="$RUN_DIR/native-out/records_delivery.jsonl"
DEST="$RECORDS_DIR/${JOB_ID}__records.jsonl"

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
WATCH_STOP=0
if ! grep -q "NATIVE_CELL_COMPLETED" "$LOG"; then
  # [Claude 2026-09-09] `NATIVE_CELL_COMPLETED` is printed at the end of the WHOLE cell, after
  # evaluation. A cell stopped by its own watch budget mid-evaluation never prints it -- so this
  # refusal, which is right, made `scripts/assemble_reaped_delivery.py` unusable: that tool exists
  # to rebuild exactly such a cell's bundle, and its output could not then be collected. Two tools
  # for one case, meeting at a wall, and neither refusal wrong on its own.
  #
  # So there is an explicit path, never a silent one. It requires evidence that the stop was OURS
  # and that the bundle was rebuilt rather than found.
  if [[ "${NATIVE_ACCEPT_WATCH_STOP:-0}" == "1" ]]; then
    grep -q "NATIVE_CELL_BEGIN" "$LOG" || {
      echo "   REFUSING: no NATIVE_CELL_COMPLETED and no NATIVE_CELL_BEGIN either. This log does" >&2
      echo "   not show a cell that started, so there is nothing a watch stop would explain." >&2
      exit 1; }
    WATCH_STOP=1
    echo "   === NATIVE_COLLECTED_AFTER_WATCH_STOP: no NATIVE_CELL_COMPLETED, accepted explicitly"
    echo "       The cell began and was stopped before finishing. Its rows are collected; the run"
    echo "       is NOT complete and must not be read as one that finished."
  else
    echo "   REFUSING: no NATIVE_CELL_COMPLETED marker. The cell did not report completion." >&2
    if compgen -G "$RUN_DIR/native-out/cells/*/offline_eval_*.jsonl" >/dev/null 2>&1; then
      echo "   Per-cell evaluation rows DO exist. If this cell was stopped by its own watch budget," >&2
      echo "   rebuild the bundle and collect it deliberately:" >&2
      echo "     python scripts/assemble_reaped_delivery.py $RUN_DIR --out $RUN_DIR/native-out/records_delivery.jsonl" >&2
      echo "     NATIVE_ACCEPT_WATCH_STOP=1 bash datasphere/native/collect-host-run.sh $FAMILY $RUN_DIR" >&2
      echo "   Every row will carry _assembled_after_reaping and the records will be marked." >&2
    fi
    exit 1
  fi
else
  echo "   completed: $(grep -c 'NATIVE_CELL_COMPLETED' "$LOG") cell(s)"
fi

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

# 2c. A SUPPLEMENTARY policy-mode pass may be missing without the cell having failed.
#
# Since 2026-09-10 a non-native endpoint pass that fails no longer fails the cell: `native` is the
# estimand the family reports and `mode` is an extra for the A25 cross-group pairs, so losing the
# second must not discard the first (ppg-s1 on card0-20260909-115331 lost a complete 44-row native
# grid that way). The consequence for collection is that a run can now be legitimately collectable
# AND missing a comparison, and nothing else in this script would say so.
if grep -q "NATIVE_ENDPOINT_SUPPLEMENTARY_INCOMPLETE" "$LOG"; then
  echo "   SUPPLEMENTARY PASS MISSING -- collectable, but not the whole grid:"
  grep -h "NATIVE_ENDPOINT_SUPPLEMENTARY_FAILED" "$LOG" | sed 's/^/     /'
  echo "     The native endpoint grid is present and is the reported estimand. Any table that"
  echo "     needs the mode/sample comparison for this cell must treat it as absent, not as zero."
fi

# 2d. A delivery whose rows are mostly provenance is a defect, not a large run.
#
# `collect_record_delivery` stamps the run manifest onto EVERY row, so anything large in that
# manifest is multiplied by the row count. On card0-20260909-115331 the manifest inlined the
# resource sampler's whole per-second series and the bundle reached 1,365,573,627 bytes for 964
# rows -- about 1.4 MB per row, of which roughly 8 KB was the record. run_probe.sh now stores a
# summary instead, but a bundle produced by an older runner still carries it, and the next thing
# to bloat a manifest would do this again silently.
#
# Bytes-per-row rather than total bytes: a genuinely large run has many rows, and a threshold on
# total size would refuse it while passing a small run with a bloated manifest -- exactly backwards.
_rows="$(wc -l < "$SRC" | tr -d ' ')"
if [[ "${_rows:-0}" -gt 0 ]]; then
  _bytes="$(wc -c < "$SRC" | tr -d ' ')"
  _per_row=$(( _bytes / _rows ))
  if [[ "$_per_row" -gt 65536 ]]; then
    echo "   OVERSIZED ROWS: $_per_row bytes/row over $_rows rows ($_bytes bytes total)." >&2
    echo "   A record row is normally a few KB. This is the run manifest being stamped onto every" >&2
    echo "   row with something large inside it -- historically resource_samples, which grows with" >&2
    echo "   run duration and, on a shared host, names other users' GPU PIDs." >&2
    if [[ "$_per_row" -gt 1048576 && "${NATIVE_ACCEPT_FAT_DELIVERY:-0}" != "1" ]]; then
      echo "   REFUSING at over 1 MB/row. Find what the manifest carries before installing it:" >&2
      echo "     python3 scripts/explain_delivery_size.py $SRC" >&2
      echo "   Set NATIVE_ACCEPT_FAT_DELIVERY=1 to install it anyway, deliberately." >&2
      exit 1
    fi
  fi
fi

# 3. The bundle must exist and be non-empty. SUCCESS with no records is itself a finding.
if [[ ! -s "$SRC" ]]; then
  echo "   REFUSING: $SRC is absent or empty. A completed cell that produced no records is a" >&2
  echo "   finding, not an empty result to file away." >&2
  if compgen -G "$RUN_DIR/native-out/cells/*/offline_eval_*.jsonl" >/dev/null 2>&1; then
    echo "   BUT the per-cell evaluation rows EXIST. collect_record_delivery runs after evaluation," >&2
    echo "   so a cell reaped mid-evaluation has written every row and assembled none -- the" >&2
    echo "   measurements are unassembled, not lost. Recover them explicitly:" >&2
    echo "     python scripts/assemble_reaped_delivery.py $RUN_DIR --out <bundle>.jsonl" >&2
    echo "   Every row it writes is marked _assembled_after_reaping and must never be filed as" >&2
    echo "   though the runner produced it." >&2
  fi
  if [[ -s "$RUN_DIR/native-out/records.jsonl" ]]; then
    echo "   records.jsonl IS present. That file is normalize_curves.py's per-cell rows, not the" >&2
    echo "   delivered bundle -- measured on card0-20260909-005543 it held 2 rows and ZERO" >&2
    echo "   offline-eval rows, against the bundle's 6. Collecting it would install" >&2
    echo "   a fraction of the run and report success. Find out why collect_record_delivery did not" >&2
    echo "   run; do not point this script at records.jsonl." >&2
  fi
  exit 1
fi

# 3b. A watch-stopped collection must be an ASSEMBLED bundle, not a found one. Without this the
#     flag would let any incomplete cell through on the operator's say-so; with it, the flag only
#     opens the path that `assemble_reaped_delivery.py` marks every row on.
if [[ "$WATCH_STOP" == "1" ]]; then
  total_rows="$(wc -l < "$SRC" | tr -d ' ')"
  marked="$(grep -c '_assembled_after_reaping' "$SRC" || true)"
  if [[ "$marked" -eq 0 || "$marked" -ne "$total_rows" ]]; then
    echo "   REFUSING: NATIVE_ACCEPT_WATCH_STOP=1 but only $marked of $total_rows rows carry" >&2
    echo "   _assembled_after_reaping. This flag exists to collect a bundle rebuilt by" >&2
    echo "   scripts/assemble_reaped_delivery.py, not to wave through an arbitrary incomplete run." >&2
    exit 1
  fi
  echo "   all $total_rows row(s) marked _assembled_after_reaping"
fi

# 4. THE SOURCE CHOICE IS CHECKED AGAINST THE LOG. If the runner evaluated anything, the bundle must
#    carry offline-eval rows. This is what makes reading the wrong file loud instead of quiet, and it
#    is anchored on markers this script does not write.
if grep -qE "NATIVE_(CURVE_EVAL_COMPLETED|ENDPOINT_EVAL_BEGIN)" "$LOG"; then
  offline="$(grep -cE '"phase"[[:space:]]*:[[:space:]]*"offline-eval"' "$SRC")"
  if [[ "$offline" -eq 0 ]]; then
    echo "   REFUSING: the log says this run evaluated checkpoints, but $(basename "$SRC") carries" >&2
    echo "   ZERO offline-eval rows. Either the delivery step missed them or this script is reading" >&2
    echo "   the wrong file. Both mean the evaluation -- the expensive half of the cell -- would be" >&2
    echo "   filed as if it had never happened." >&2
    exit 1
  fi
  echo "   offline-eval rows: $offline"
fi

# 5. THE RUNNER STATES HOW MANY ROWS IT WROTE. A disagreement means the file changed between the
#    runner emitting it and this script reading it -- a truncated fetch is the likely cause, and a
#    truncated fetch installs a silently short result.
emitted="$(grep -oE 'NATIVE_RECORDS_EMITTED [0-9]+ rows' "$LOG" | tail -1 | awk '{print $2}')"
have="$(wc -l < "$SRC" | tr -d ' ')"
if [[ -n "$emitted" && "$emitted" != "$have" ]]; then
  echo "   REFUSING: the runner emitted $emitted rows; this copy has $have. The file is not the one" >&2
  echo "   the runner wrote -- most likely an interrupted fetch. Re-fetch rather than collect." >&2
  exit 1
fi

mkdir -p "$RECORDS_DIR"

# 5b. NEVER OVERWRITE A PAST RUN'S RECORDS.
#
# [Claude 2026-09-09] `cp` was unconditional. The job id is the run directory's basename
# (`card0-<YYYYmmdd-HHMMSS>`), which is unique per launch at second resolution, so a collision needs
# either a re-collection of the same run or a re-used directory name -- and BOTH are plausible: a
# re-collection is exactly what an operator does after fixing a fetch, and this script is designed
# to be re-runnable. Overwriting is silent, and the thing overwritten is a completed production
# cell's only installed copy.
#
# Identical content is not a collision -- re-collecting the same run must stay idempotent. Different
# content is refused, with both paths named, because deciding which is right is not this script's
# call.
if [[ -e "$DEST" ]]; then
  if cmp -s "$SRC" "$DEST"; then
    echo "   already installed and byte-identical; nothing to do"
  else
    echo "   REFUSING: $DEST already exists and DIFFERS from what this run produced." >&2
    echo "     existing: $(wc -l < "$DEST" | tr -d ' ') rows, $(stat -c %s "$DEST" 2>/dev/null || stat -f %z "$DEST") bytes" >&2
    echo "     incoming: $have rows, $(stat -c %s "$SRC" 2>/dev/null || stat -f %z "$SRC") bytes" >&2
    echo "   A job id is the run directory basename and is unique per launch, so this means either" >&2
    echo "   a re-collection whose source changed, or two runs sharing a directory name. Installing" >&2
    echo "   over it would destroy a completed production cell's only installed copy. Move the" >&2
    echo "   existing file aside deliberately, or collect under a different RECORDS_DIR." >&2
    exit 1
  fi
else
  cp "$SRC" "$DEST"
fi
echo "   records at $DEST: $have row(s)${emitted:+, runner emitted $emitted}"

# 6. THE TWO AUDITS THAT CAN ONLY RUN HERE. Both read artifacts that never enter the repository --
#    checkpoints to hash, and the training CSV or log -- so `production_gates.py` classifies them
#    DESCRIPTIVE and this is where they actually execute, once per collected result.
#
#    [Claude 2026-09-09] Wired in after the first two production cells each produced a null whose
#    CAUSE was invisible in every artifact the pipeline checked. Reading their logs by hand found
#    idaac updating far outside the trust region (clip_fraction 0.82, KL 1.0-1.5 nats) and ppg's
#    policy diagnostics pinned at zero. Ten baselines remain; finding that by hand once is luck.
#
#    The frame audit REFUSES on a mismatch -- a real measurement attached to the wrong frame is a
#    corrupt record and must not be filed. The diagnostics audit REPORTS: a flag is a question about
#    the run, not a defect in the record, and a deliberate deviation may be expected.
if [[ -f scripts/audit_record_frame_provenance.py ]]; then
  echo "   -- frame provenance"
  frames_out="$("$BP" scripts/audit_record_frame_provenance.py "$RUN_DIR" --strict 2>&1)"
  frames_status=$?
  printf '%s\n' "$frames_out" | sed 's/^/      /'
  if [[ $frames_status -ne 0 ]]; then
    echo "   REFUSING: a record's frame does not belong to the checkpoint it measured. The rows are" >&2
    echo "   well-formed and plausible, which is why nothing downstream would catch it." >&2
    rm -f "$DEST"
    exit 1
  fi
fi
if [[ -f scripts/audit_training_diagnostics.py ]]; then
  echo "   -- training diagnostics"
  "$BP" scripts/audit_training_diagnostics.py "$RUN_DIR" 2>&1 | sed 's/^/      /'
fi

# [Claude 2026-09-09] Eval validity: are these numbers reportable at all? Checks each row's summary
# against its own raw episodes, episode-id uniqueness, and that placement is paired across regimes --
# then REPORTS reset reproducibility per regime rather than failing on it, because eval-medium and
# eval-hard resample their perturbation by design and that is a limit on what may be claimed, not a
# fault. Not --strict here: a defect it finds is about the evaluator, not about whether these rows
# should be filed, and refusing the collection would lose the very evidence that shows the defect.
if [[ -f scripts/audit_eval_validity.py ]]; then
  echo "   -- eval validity"
  "$BP" scripts/audit_eval_validity.py "$DEST" 2>&1 | sed 's/^/      /'
fi

# 7. The ledger REFUSES a stale evaluator revision, and that refusal is the most valuable thing it
#    does. Capture the status explicitly: piping it through `tail` would discard the exit code and
#    print "Do NOT write this entry" while exiting 0.
out="$("$BP" scripts/populate_evaluator_ledger.py "$FAMILY" "$JOB_ID" 2>&1)"
status=$?
printf '%s\n' "$out" | tail -3 | sed 's/^/   /'
if [[ $status -ne 0 ]] || printf '%s' "$out" | grep -q "Do NOT write this entry"; then
  echo "   REFUSED by the ledger: this record does not describe the current tree." >&2
  exit 1
fi

# 8. The gate line is a SUMMARY, and a summary must not decide this script's exit status. As the
#    last command, a `grep` that matches nothing made the collector exit 1 after installing the
#    bundle and passing the ledger -- indistinguishable, to a caller, from a refusal. The collection
#    either happened or it did not, and by this line it has.
echo
gate="$("$BP" scripts/production_gates.py 2>&1 | grep -iE "shared evaluator validated" | cut -c1-200)"
if [[ -n "$gate" ]]; then
  printf '%s\n' "$gate"
else
  echo "   NOTE: production_gates.py printed no 'shared evaluator validated' line. The collection" >&2
  echo "   SUCCEEDED -- this is about the summary, not the result. Check the gate separately." >&2
fi
exit 0
