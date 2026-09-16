#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=evaluator-noise-full-grid-replicate-ppg
RUNS='~/rlvigen-runs'
R1="$RUNS/card1-20260915-160000/native-out/records_delivery.jsonl"
R2="$RUNS/card1-20260916-035335/native-out/records_delivery.jsonl"
B=results/evidence/$S/raw
FIELDS='"(regime|scene_set|eval_policy_mode|episodes|episode_return_mean|episode_return_sd|checkpoint_sha256|evaluator_revision|returns|placement_condition_seeds)": *(\[[^]]*\]|"[^"]*"|[-0-9.e]+)'

# --- two complete endpoint grids of one checkpoint, same revision, same invocation ---
C $S grid1-rows --host-path "$R1" --grep "$FIELDS" --only-matching --max 0 \
  --note 'endpoint grid 1: 2026-09-15 16:00-19:47 MSK, the rows that were committed' \
  --fact grid1_revision=248751f7caca --anchor '"evaluator_revision": "248751f7caca'
C $S grid2-rows --host-path "$R2" --grep "$FIELDS" --only-matching --max 0 \
  --note 'endpoint grid 2: 2026-09-16 03:53-09:04 MSK, a retry of the same invocation, never committed' \
  --fact grid2_revision=248751f7caca --anchor '"evaluator_revision": "248751f7caca'
C $S committed-is-grid1 --command 'shasum -a 256 results/records/reeval-v214-ppg-endpoint__records.jsonl' \
  --note 'the committed file; its hash equals the grid 1 source hash in grid1-rows.txt' \
  --fact committed_sha=dbfff3625bb7a00f --anchor 'dbfff3625bb7a00f'
# run_manifest.json in native-out is root-only (mode 600); the result archives hold readable copies
C $S grid1-invocation --host-path "$RUNS/card1-20260915-160000/mirror/ppg-endpoint-result.tgz" --tar-member ./run_manifest.json \
  --grep '"(payload_sha256|requirements_native_sha256|container_image|frames|host_profile)"' \
  --note 'grid 1 invocation keys, from the archive mirrored with that run'
C $S grid2-invocation --host-path "$RUNS/reeval-v214/ppg-endpoint-result.tgz" --tar-member ./run_manifest.json \
  --grep '"(payload_sha256|requirements_native_sha256|container_image|frames|host_profile)"' \
  --note 'grid 2 invocation keys, from the archive the retry wrote (it replaced grid 1 at this path)'
C $S invocation-diff --command "bash -c 'diff <(sed \"1,/^#---/d\" $B/grid1-invocation.txt | cut -d: -f2-) <(sed \"1,/^#---/d\" $B/grid2-invocation.txt | cut -d: -f2-); true'" \
  --allow-empty \
  --note 'absence: the invocation keys are identical in both grids' \
  --fact invocation_key_differences=0 --anchor 'header:# matched-lines: 0 '

# --- the paired comparison, from the captured per-episode returns ---
C $S paired --command "\"$PY\" scripts/evidence_pair_eval_grids.py $B/grid1-rows.txt $B/grid2-rows.txt" \
  --note 'every (regime, scene set, policy mode) row paired across the two grids' \
  --fact rows_paired=88 --anchor 'rows grid1 88 grid2 88 paired 88 unpaired []' \
  --fact mode_placements_identical=40/40 --anchor 'mode=mode pairs 44 (per-scene 40)  identical placement seeds 40/40' \
  --fact mode_rows_identical=2/40 --anchor 'identical rows 2/40' \
  --fact mode_episodes_identical=282/800 --anchor 'identical episodes 282/800' \
  --fact sample_episodes_identical=264/800 --anchor 'identical episodes 264/800' \
  --fact mode_z_mean=0.212 --anchor 'mode=mode |mean diff| in SE: mean 0.212' \
  --fact sample_z_mean=0.328 --anchor 'mode=sample |mean diff| in SE: mean 0.328' \
  --fact mode_eval_hard_identical=0/200 --anchor 'mode=mode regime=eval-hard identical episodes 0/200' \
  --fact mode_eval_medium_identical=0/200 --anchor 'mode=mode regime=eval-medium identical episodes 0/200' \
  --fact mode_train_identical=132/200 --anchor 'mode=mode regime=train identical episodes 132/200' \
  --fact mode_easy_identical=150/200 --anchor 'mode=mode regime=eval-easy identical episodes 150/200' \
  --fact sample_train_identical=123/200 --anchor 'mode=sample regime=train identical episodes 123/200'

# --- is `mode` really free of torch sampling? ---
C $S mode-act-fn --local-path scripts/eval_grid.py --grep 'def ppg_mode_act_fn|pd\.mean|return .*mean|act_fn' --max 12 \
  --note 'the ppg mode rule takes the Normal mean; it draws no sample' \
  --fact mode_is_mean=true --anchor 'whose mode is its mean'
