#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ppg-banked-seed-is-off-schedule
SCHED=datasphere/native/production-schedule-v100.json

C $S schedule-now --local-path $SCHED --lines 21:25 \
  --note 'the production schedule names seeds 101, 102, 103' \
  --fact schedule_seeds='101,102,103' --anchor $'22:    101,\n23:    102,\n24:    103'
C $S schedule-ppg-row --local-path $SCHED --lines 385:393 \
  --note 'and names the same three for ppg specifically' \
  --fact ppg_row_seeds='101,102,103' --anchor $'390:        101,\n391:        102,\n392:        103'
C $S schedule-at-launch --command "git show 672202d:$SCHED" --lines 21:25 \
  --note 'the schedule already said 101-103 at commit 672202d (2026-09-09 11:52 MSK), before the ppg run launched' \
  --fact schedule_seeds_at_launch='101,102,103' --anchor $'22:    101,\n23:    102,\n24:    103'
C $S launch-commit-time --command 'git log -1 --format="%h %ci" 672202d' \
  --note 'when that schedule revision was committed' \
  --fact schedule_commit_time='2026-09-09 11:52:24 +0300' --anchor '672202d 2026-09-09 11:52:24 +0300'
C $S run-seed --host-path '~/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1/effective_config.json' \
  --grep '"(SEED|seed|CELLS)": ' \
  --note 'the banked ppg run was launched as seed 1 (run dir card0-20260909-115331, i.e. 11:53 MSK)' \
  --fact run_seed=1 --anchor '"SEED": "1"' \
  --fact run_cells=ppg:1 --anchor '"CELLS": "ppg:1"'
C $S committed-seeds --command "\"$PY\" -c \"
import json
for f in ('results/records/reeval-v214-ppg-endpoint__records.jsonl', 'results/records/reeval-v214-ppg-curve__records.jsonl', 'results/records/reeval-v214-idaac-endpoint__records.jsonl'):
    rows = [json.loads(l) for l in open(f)]
    print(f, 'seeds', sorted({r['seed'] for r in rows}), 'cells', sorted({r['cell'] for r in rows}))
\"" --note 'the seeds the admissible records carry' \
  --fact ppg_records_seed=1 --anchor "reeval-v214-ppg-endpoint__records.jsonl seeds [1] cells ['ppg-s1']" \
  --fact idaac_records_seed=101 --anchor "reeval-v214-idaac-endpoint__records.jsonl seeds [101] cells ['idaac-s101']"
C $S why-named --local-path docs/CONSTRUCTION.md --lines 954:956 \
  --note 'why the schedule names seeds at all: the trees default to different ones' \
  --fact defaults_disagree='1, 0, None' --anchor 'the default seeds still disagree across trees (1, 0, `None`)'
