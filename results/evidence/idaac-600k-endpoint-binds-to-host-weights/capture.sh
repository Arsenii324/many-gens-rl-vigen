#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=idaac-600k-endpoint-binds-to-host-weights
RUNS='~/rlvigen-runs'
CELL="$RUNS/card0-20260909-035152/native-out/cells/idaac-s101"
B=results/evidence/$S/raw

# --- which host snapshot is which: every retained idaac snapshot, hashed in place ---
C $S snapshot-card0-20260909-005543 --host-hashes "$RUNS/card0-20260909-005543/native-out/cells/idaac-s101" --name-glob 'snapshot.pt' \
  --note 'the retained terminal idaac snapshot of card0-20260909-005543'
C $S snapshot-card0-20260909-013936 --host-hashes "$RUNS/card0-20260909-013936/native-out/cells/idaac-s101" --name-glob 'snapshot.pt' \
  --note 'the retained terminal idaac snapshot of card0-20260909-013936'
C $S snapshot-card0-20260909-035152 --host-hashes "$RUNS/card0-20260909-035152/native-out/cells/idaac-s101" --name-glob 'snapshot.pt' \
  --note 'the retained terminal idaac snapshot of card0-20260909-035152'
C $S snapshot-card0-20260910-120437 --host-hashes "$RUNS/card0-20260910-120437/native-out/cells/idaac-s1" --name-glob 'snapshot.pt' \
  --note 'the retained terminal idaac snapshot of card0-20260910-120437'

# --- the run whose snapshot the rows name: what it was asked for, and that it finished ---
C $S run-record --host-path "$CELL/effective_config.json" --grep '"frames_requested"|"host_profile"|"cell"' \
  --note 'the 600k production cell' \
  --fact frames_requested=600000 --anchor '"frames_requested": "600000"'
C $S run-end --host-path "$CELL/training.log" --grep 'NATIVE_FINAL_EVALUATION_COMPLETED|Command being timed|Exit status' \
  --note 'the trainer reached its floored endpoint and exited 0' \
  --fact final_frame=598016 --anchor 'NATIVE_FINAL_EVALUATION_COMPLETED frame=598016' \
  --fact exit_status=0 --anchor 'Exit status: 0' \
  --fact rollout=2048 --anchor '--num_steps 2048'
C $S retained-record --host-path "$CELL/retained.json" --grep '"checkpoint_(bytes|source)"' \
  --note 'the terminal snapshot was copied from the trainer save' \
  --fact terminal_source=models/agent-robosuite:Door-idaac-s101.pt --anchor 'models/agent-robosuite:Door-idaac-s101.pt"'
C $S intermediate-weights --host-hashes "$CELL/checkpoints" --name-glob 'agent-*.pt' \
  --note 'the 11 frame-stamped intermediate checkpoints the curve sweep reads' \
  --fact intermediate_count=11 --anchor 'header:# matched-lines: 11 '
C $S endpoint-rule --local-path datasphere/native/families.json --lines 412:418 \
  --note 'idaac descriptor (the family block starts at line 283): the endpoint floors requested frames to whole rollouts' \
  --fact endpoint_rule=floor_to_quantum --anchor '"rule": "floor_to_quantum"'

# --- the join, and the arithmetic ---
C $S join --command "\"$PY\" -c \"
import json
def listing(name):
    body = open('$B/' + name + '.txt').read().split('#' + '-' * 99 + '\n', 1)[1]
    return {line.split()[2]: line.split(maxsplit=3)[3] for line in body.splitlines()}
snaps = {}
for run in ('card0-20260909-005543', 'card0-20260909-013936', 'card0-20260909-035152', 'card0-20260910-120437'):
    for sha, name in listing('snapshot-' + run).items():
        snaps[sha] = run
rows = [json.loads(l) for l in open('results/records/reeval-v214-idaac-endpoint__records.jsonl')]
by = {}
for r in rows:
    by.setdefault((r['frame'], r['checkpoint_sha256']), []).append(r['conventions']['eval_policy_mode'])
print('rows', len(rows))
for (frame, sha), modes in sorted(by.items()):
    print('frame', frame, 'sha', sha[:16], '->', snaps.get(sha, 'NOT-ON-HOST'), 'rows', len(modes),
          'sample', modes.count('sample'), 'mode', modes.count('mode'))
print('floor(600000 / 2048) * 2048 =', 600000 // 2048 * 2048)
\"" --note 'the committed endpoint rows, joined to the four candidate snapshots' \
  --fact endpoint_rows=88 --anchor 'rows 88' \
  --fact endpoint_snapshot_run=card0-20260909-035152 --anchor '-> card0-20260909-035152 rows 88 sample 44 mode 44' \
  --fact floored_endpoint=598016 --anchor 'floor(600000 / 2048) * 2048 = 598016'
C $S join-failures --command "sed '1,/^#---/d' $B/join.txt" --grep 'NOT-ON-HOST' --allow-empty \
  --note 'absence: every endpoint row names a snapshot that is on the host' \
  --fact unmatched_rows=0 --anchor 'header:# matched-lines: 0 '

# --- the in-run mode endpoint was 3 eval-hard rows short; the committed re-evaluation is not ---
C $S in-run-mode-regimes --host-path "$CELL/offline_eval_endpoint_mode.jsonl" \
  --grep '"regime": "[a-z-]+"' --only-matching --max 0 \
  --note 'the training cell own mode-policy endpoint file: one regime field per row' \
  --fact in_run_mode_rows=41 --anchor 'header:# matched-lines: 41 '
C $S coverage --command "\"$PY\" -c \"
import collections, json, re
body = open('$B/in-run-mode-regimes.txt').read().split('#' + '-' * 99 + '\n', 1)[1]
print('in-run mode rows by regime', sorted(collections.Counter(re.findall(r'regime.: .([a-z-]+)', body)).items()))
c = collections.Counter()
for l in open('results/records/reeval-v214-idaac-endpoint__records.jsonl'):
    r = json.loads(l)
    c[(r['conventions']['eval_policy_mode'], r['regime'])] += 1
print('committed re-evaluation rows by mode and regime', sorted(c.items()))
\"" --note 'the gap the tracker still lists, and the committed rows that close it' \
  --fact in_run_eval_hard_mode_rows=8 --anchor "('eval-hard', 8)" \
  --fact committed_eval_hard_mode_rows=11 --anchor "(('mode', 'eval-hard'), 11)"
