#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ibac-sni-16sep-three-stops
RUNS='~/rlvigen-runs'
A1="$RUNS/card0-20260916-005601/native-out"
A2="$RUNS/card0-20260916-010515/native-out"
A3="$RUNS/card1-20260916-115450/native-out"
OCC="$RUNS/gpu-occupancy.log"
STOPS='NATIVE_CELL_BEGIN|NATIVE_YIELD_WATCH_ARMED|NATIVE_YIELDING_TO_NEIGHBOUR|NATIVE_CELL_YIELDED|^yielded at|^free_mib=|NATIVE_CELL_FAILED'

# --- attempt 1, card 0, 00:56 MSK ---
C $S a1-stop --host-path "$A1/job.log" --grep "$STOPS" \
  --note 'attempt 1: the sentinel text, which names the watcher branch that fired' \
  --fact a1_reason=memory-floor --anchor 'yielded at 1789509788: free memory 3705 MiB is below the 4000 MiB floor' \
  --fact a1_procs_on_card=6 --anchor 'free_mib=3705 procs=6'
C $S a1-progress --host-path "$A1/cells/ibac_sni-s1/training.log" --grep '^U [0-9]+ \| F [0-9]+' --allow-empty \
  --note 'absence: attempt 1 was stopped before its first PPO update was logged' \
  --fact a1_updates_logged=0 --anchor 'header:# matched-lines: 0 '
C $S a1-occupancy --host-path "$OCC" --grep '^2026-09-16T01:0[0-3].*card=0' \
  --note 'card 0 around the stop: two colleague containers, one other cell of ours, and ibac_sni (cell-c0-3252469)' \
  --fact a1_colleagues='rl4vla_cudagl,sg_sam2' --anchor 'holders=rl4vla_cudagl,sg_sam2,cell-c0-3157898,cell-c0-3252469' \
  --fact a1_card_used_mib=28445 --anchor 'card=0 mem=28445'

# --- attempt 2, card 0, 01:05 MSK ---
C $S a2-death --host-path "$A2/cells/ibac_sni-s1/training.log" \
  --grep 'EGL_NOT_INITIALIZED|^EOFError|in reset|Exit status|Elapsed \(wall' \
  --note 'attempt 2: an env worker pipe closed during the first reset, with EGL_NOT_INITIALIZED, 24 s in' \
  --fact a2_error=EOFError --anchor 'EOFError' \
  --fact a2_egl=EGL_NOT_INITIALIZED --anchor 'err = EGL_NOT_INITIALIZED' \
  --fact a2_wall_clock=0:24.18 --anchor 'Elapsed (wall clock) time (h:mm:ss or m:ss): 0:24.18'
C $S a2-stop --host-path "$A2/job.log" --grep "$STOPS|Exit status" \
  --note 'attempt 2: no sentinel; the trainer itself exited 1' \
  --fact a2_no_sentinel=true --anchor 'Exit status: 1'
C $S a2-occupancy --host-path "$OCC" --grep '^2026-09-16T01:0[5-9].*card=0' \
  --note 'card 0 while attempt 2 started and died'

# --- attempt 3, card 1, 11:54 MSK ---
C $S a3-stop --host-path "$A3/job.log" --grep "$STOPS" \
  --note 'attempt 3: the memory floor again, with 125 MiB left' \
  --fact a3_reason=memory-floor --anchor 'yielded at 1789549938: free memory 125 MiB is below the 4000 MiB floor'
C $S a3-progress --host-path "$A3/cells/ibac_sni-s1/training.log" --grep '^U [0-9]+ \| F [0-9]+' \
  --note 'attempt 3: training updates logged before the stop' \
  --fact a3_last_frame=100352 --anchor 'U 49 | F 100352'
C $S a3-occupancy --host-path "$OCC" --grep '^2026-09-16T12:(09|1[0-4]).*card=1' \
  --note 'card 1 around the stop: ours alone, then a colleague arrives, then the colleague alone' \
  --fact a3_ours_alone_mib=7712 --anchor 'card=1 mem=7712 util=57 procs=3 holders=cell-c1-207974,cell-c1-207974,cell-c1-207974' \
  --fact a3_colleague_arrives=rlvigen_kalugin_df --anchor 'card=1 mem=25713 util=48 procs=4 holders=cell-c1-207974,cell-c1-207974,cell-c1-207974,rlvigen_kalugin_df' \
  --fact a3_after_we_left_mib=32344 --anchor 'card=1 mem=32344 util=0 procs=1 holders=rlvigen_kalugin_df'

# --- what the sentinel text means: the watcher's branch ---
C $S watcher-branch --local-path scripts/yield_gpu_to_neighbour.py --lines 238:252 \
  --note 'the floor message is written only when the process-count branch did NOT fire' \
  --fact floor_text_implies_not_process_branch=true --anchor 'if neighbour'

# --- what the project said caused attempt 1 ---
C $S stated-cause --command 'git log -1 --format=%B bb05db6' --grep 'cause was our own process-count yield|ten minutes' \
  --note 'the commit that enumerated the stop mechanisms attributed attempt 1 to the process-count yield' \
  --fact stated_cause=process-count --anchor 'The cause was our own process-count yield'
C $S stated-row --command 'git show d43952a:notes/model/STOP-MECHANISMS.md' --grep '^\| 2 \|' \
  --note 'STOP-MECHANISMS.md row 2 as it stood at d43952a, before this bundle corrected it' \
  --fact row2_claim='it killed ibac_sni-s1' --anchor 'it killed ibac_sni-s1'

# --- times, and the waiter that launched the next attempt ---
C $S times --command "\"$PY\" -c \"
import datetime as d
z = d.timezone(d.timedelta(hours=3))
for label, t in (('attempt 1 yield', 1789509788), ('attempt 3 yield', 1789549938)):
    print(label, t, d.datetime.fromtimestamp(t, z).isoformat())
\"" --note 'sentinel epochs in Moscow time' \
  --fact a1_yield_time=2026-09-16T01:03:08+03:00 --anchor '1789509788 2026-09-16T01:03:08+03:00' \
  --fact a3_yield_time=2026-09-16T12:12:18+03:00 --anchor '1789549938 2026-09-16T12:12:18+03:00'
C $S next-attempt --host-path "$RUNS/ibac-waiter.log" --max 0 \
  --note 'the waiter that replaced blind retries: it launches only when a card has 18 GB free' \
  --fact waiter_threshold_mib=18000 --anchor 'waiting for >= 18000 MiB free on either card'
