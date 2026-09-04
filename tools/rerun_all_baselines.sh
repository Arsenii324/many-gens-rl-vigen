#!/usr/bin/env bash
# Re-run every runnable baseline into a clean logs/ tree, at ONE commit.
#
#   bash tools/rerun_all_baselines.sh                 # smoke budget
#   PYTHON=/path/to/venv/bin/python bash tools/rerun_all_baselines.sh
#   ARGS="" bash tools/rerun_all_baselines.sh         # full budget instead of --smoke
#
# TWO THINGS THAT COST A RUN EACH, both learned on 2026-08-10:
#
# 1. `PYTHON` must point at an interpreter that has robosuite. `baselines/<x>/train.sh` does
#    `PY="${PYTHON:-python}"`, so without it you get whatever `python` is on PATH and every
#    baseline dies instantly with `ModuleNotFoundError: No module named 'robosuite'` -- deep in a
#    stack trace that never mentions the interpreter. This script fails loudly up front instead.
#
# 2. DO NOT COMMIT, and do not leave stray files in the repo, while this runs. `code_commit` is
#    captured PER RUN from `git rev-parse` plus `git status --porcelain`, so a commit mid-batch
#    fragments provenance across several SHAs, and a single UNTRACKED file anywhere in the tree
#    stamps every overlapping run `-dirty`. Two stray copies of a doc were enough to invalidate
#    three runs' provenance and force them to be redone.
#
# Verify afterwards with tools/verify_run_provenance.py.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="${PYTHON:-python}"
ARGS="${ARGS---smoke}"
TASK="${TASK:-Door}"
SEED="${SEED:-0}"

if ! "$PY" -c "import robosuite" >/dev/null 2>&1; then
  echo "ABORTING: '$PY' cannot import robosuite."
  echo "  Set PYTHON to an interpreter that can, e.g."
  echo "  PYTHON=/path/to/.venv/bin/python bash tools/rerun_all_baselines.sh"
  exit 1
fi

DIRT="$(git -C "$REPO" status --porcelain)"
if [ -n "$DIRT" ]; then
  echo "WARNING: the tree is not clean, so every run below will be stamped '-dirty':"
  echo "$DIRT" | sed 's/^/    /'
  echo "  Commit, stash or remove these first if you want exact provenance."
  echo
fi

COMMIT=$(git -C "$REPO" rev-parse --short HEAD)
echo "=== re-running all baselines at $COMMIT (task=$TASK seed=$SEED args='$ARGS') ==="

FAIL=""
for b in $("$PY" -c "from rlgen import registry; print(' '.join(sorted(registry.runnable())))"); do
  t0=$(date +%s)
  if PYTHON="$PY" bash "baselines/$b/train.sh" "$TASK" "$SEED" $ARGS > "/tmp/rerun-$b.log" 2>&1; then
    echo "  OK      $b  ($(( $(date +%s) - t0 ))s)"
  else
    echo "  FAILED  $b  ($(( $(date +%s) - t0 ))s)  -- see /tmp/rerun-$b.log"
    FAIL="$FAIL $b"
  fi
done

echo "=== done at $COMMIT ==="
if [ -n "$FAIL" ]; then
  echo "FAILURES:$FAIL"
  exit 1
fi
echo "all baselines completed; now run: python tools/verify_run_provenance.py"
