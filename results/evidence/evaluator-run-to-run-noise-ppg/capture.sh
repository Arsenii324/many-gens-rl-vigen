#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=evaluator-run-to-run-noise-ppg
R='~/rlvigen-runs/reeval-v214'
OLD=results/superseded-runs/card0-20260909-115331__records.jsonl
# the fields that decide the question; each row is ~27 KB, so only these are kept
FIELDS='"(phase|regime|scene_set|episode_return_mean|episode_return_sd|checkpoint_sha256|evaluator_revision|episode_seed|regimes|scenes|eval_policy_mode|eval_scope|episodes|returns|placement_condition_seeds|deterministic_setting)": *(\[[^]]*\]|\{[^}]*\}|"[^"]*"|[-0-9.e]+)'

# --- the two narrow re-runs (host archives) and the original full-grid row (repo) ---
C $S run1-row --host-path "$R/ppg-smoke-run1.tgz" --tar-member ./offline_eval_cuda.jsonl \
  --grep "$FIELDS" --only-matching --max 0 \
  --note 'run 1 of the narrow re-evaluation (train, scene 0, 20 sampled episodes), 2026-09-15 15:40 MSK' \
  --fact run1_mean=25.794515705108644 --anchor '"episode_return_mean": 25.794515705108644' \
  --fact run1_sd=14.245690545714764 --anchor '"episode_return_sd": 14.245690545714764' \
  --fact checkpoint=a328e63e6ffa96f8 --anchor '"checkpoint_sha256": "a328e63e6ffa96f8' \
  --fact new_evaluator_revision=248751f7caca --anchor '"evaluator_revision": "248751f7caca' \
  --fact narrow_scope_regimes='["train"]' --anchor '"regimes": ["train"]'
C $S run2-row --host-path "$R/ppg-smoke-result.tgz" --tar-member ./offline_eval_cuda.jsonl \
  --grep "$FIELDS" --only-matching --max 0 \
  --note 'run 2: the same invocation repeated, 2026-09-15 15:56 MSK' \
  --fact run2_mean=26.05295889377594 --anchor '"episode_return_mean": 26.05295889377594' \
  --fact run2_sd=14.39036276163836 --anchor '"episode_return_sd": 14.39036276163836' \
  --fact run2_checkpoint=a328e63e6ffa96f8 --anchor '"checkpoint_sha256": "a328e63e6ffa96f8' \
  --fact run2_evaluator_revision=248751f7caca --anchor '"evaluator_revision": "248751f7caca'
C $S old-row --command "grep -m1 '\"episode_return_mean\": 26.099544954299926' $OLD" \
  --grep "$FIELDS" --only-matching --max 0 \
  --note 'the row recorded 2026-09-09 by the full grid (four regimes x ten scenes), same checkpoint' \
  --fact old_mean=26.099544954299926 --anchor '"episode_return_mean": 26.099544954299926' \
  --fact old_evaluator_revision=184329928b51 --anchor '"evaluator_revision": "184329928b51' \
  --fact old_checkpoint=a328e63e6ffa96f8 --anchor '"checkpoint_sha256": "a328e63e6ffa96f8' \
  --fact full_scope_regimes='4 regimes' --anchor '"regimes": ["train", "eval-easy", "eval-medium", "eval-hard"]'

# --- the two invocations were the same: their run manifests differ only in disk free and output hashes ---
C $S run1-manifest --host-path "$R/ppg-smoke-run1.tgz" --tar-member ./run_manifest.json --max 0 \
  --note 'run 1 run_manifest.json, whole'
C $S run2-manifest --host-path "$R/ppg-smoke-result.tgz" --tar-member ./run_manifest.json --max 0 \
  --note 'run 2 run_manifest.json, whole'
B=results/evidence/$S/raw
C $S manifest-diff --command "bash -c 'diff <(sed \"1,/^#---/d\" $B/run1-manifest.txt) <(sed \"1,/^#---/d\" $B/run2-manifest.txt); true'" \
  --note 'every line on which the two run manifests differ: disk free/used and the result hashes, nothing about the invocation' \
  --fact manifest_diff_lines=36 --anchor 'header:# matched-lines: 36 ' \
  --fact diff_touches_free=true --anchor '<         "free": 159380615168,'
C $S invocation-keys-not-in-diff --command "sed '1,/^#---/d' $B/manifest-diff.txt" \
  --grep 'payload_sha256|requirements_native_sha256|container_image|command|cells_requested|eval_|frames|host_profile|torch' \
  --allow-empty \
  --note 'absence: none of the invocation-defining manifest keys is among the changed lines' \
  --fact invocation_keys_changed=0 --anchor 'header:# matched-lines: 0 '
C $S run1-invocation --command "sed '1,/^#---/d' $B/run1-manifest.txt" \
  --grep '"(payload_sha256|requirements_native_sha256|container_image|command|eval_episodes|host_profile|frames)"' \
  --note 'the invocation-defining keys, as run 1 recorded them (run 2 differs from these nowhere; see manifest-diff)' \
  --fact payload_sha256=404a766c848e --anchor '"payload_sha256": "404a766c848e'

# --- analysis of the captured rows, executed ---
C $S derived --command "\"$PY\" -c \"
import json, math, re, statistics as st
def rows(name):
    body = open('$B/' + name + '.txt').read().split('#' + '-' * 99 + '\n', 1)[1]
    out = {}
    for line in body.splitlines():
        m = re.match(r'\d+:\\\"(\w+)\\\": *(.*)', line)
        if m and m.group(1) not in out:
            out[m.group(1)] = json.loads(m.group(2))
    return out
r1, r2, old = rows('run1-row'), rows('run2-row'), rows('old-row')
for name, r in (('run1', r1), ('run2', r2), ('old', old)):
    x = r['returns']
    print(name, 'n', len(x), 'mean-of-returns', round(st.mean(x), 12), 'recorded', r['episode_return_mean'], 'sd', round(st.stdev(x), 6))
print('placement seeds identical run1/run2/old:', r1['placement_condition_seeds'] == r2['placement_condition_seeds'] == old['placement_condition_seeds'])
print('episodes whose return differs run1 vs run2:', sum(a != b for a, b in zip(r1['returns'], r2['returns'])), 'of', len(r1['returns']))
means = [r1['episode_return_mean'], r2['episode_return_mean'], old['episode_return_mean']]
se = st.mean([r1['episode_return_sd'], r2['episode_return_sd'], old['episode_return_sd']]) / math.sqrt(20)
spread = max(means) - min(means)
print('spread of three means', round(spread, 4))
print('one SE at n=20', round(se, 4))
print('spread in SE', round(spread / se, 3))
print('old minus mean(new) in SE', round((old['episode_return_mean'] - (means[0] + means[1]) / 2) / se, 3))
\"" --note 'recomputed from the captured per-episode returns, not from the recorded means' \
  --fact placement_seeds_identical=True --anchor 'placement seeds identical run1/run2/old: True' \
  --fact episodes_differing_run1_run2=16/20 --anchor 'episodes whose return differs run1 vs run2: 16 of 20' \
  --fact spread=0.305 --anchor 'spread of three means 0.305' \
  --fact se_n20=3.197 --anchor 'one SE at n=20 3.19' \
  --fact spread_in_se=0.095 --anchor 'spread in SE 0.095' \
  --fact old_vs_new_in_se=0.055 --anchor 'old minus mean(new) in SE 0.055'

# --- the mechanism in code: placements re-seeded per episode, torch seeded once, ppg samples from torch ---
C $S seeding-code --local-path scripts/eval_grid.py --lines 213:242 \
  --note 'eval_grid.py: family setup seeds random/numpy/torch once; per-episode reseeding touches random and numpy only' \
  --fact torch_seeded_once=true --anchor '_torch.manual_seed(seed)' \
  --fact per_episode_reseeds_numpy=true --anchor 'np.random.seed(condition)'
C $S ppg-samples-from-torch --local-path runnable/ppg/phasic_policy_gradient/ppg.py --lines 27:36 \
  --note 'ppg act() samples its action from the torch distribution' \
  --fact ppg_act_samples=true --anchor 'ac = pd.sample()'
C $S determinism-flag-recorded --host-path "$R/ppg-smoke-run1.tgz" --tar-member ./offline_eval_cuda.jsonl \
  --grep '"deterministic_setting": *\{[^}]*\}' --only-matching --max 1 \
  --note 'every row records torch.use_deterministic_algorithms as enabled, and the runs still differ' \
  --fact deterministic_flag_enabled=true --anchor '"enabled": true'
