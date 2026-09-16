#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ppg-600k-rows-bind-to-host-weights
CELL='~/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1'
B=results/evidence/$S/raw

# --- the weights on the host: size, mtime and sha256 of every retained file ---
C $S intermediate-weights --host-hashes "$CELL/checkpoints" --name-glob 'model*.jd' \
  --note 'the 13 IC-stamped checkpoints the training run saved, hashed in place' \
  --fact intermediate_count=13 --anchor 'header:# matched-lines: 13 '
C $S terminal-weights --host-hashes "$CELL" --name-glob 'snapshot.pt' \
  --note 'the retained terminal checkpoint (retained.json: copied from model_terminal.jd)' \
  --fact terminal_count=1 --anchor 'header:# matched-lines: 1 '
C $S retained-record --host-path "$CELL/retained.json" --max 0 \
  --note 'what the runner says it retained, and from where' \
  --fact terminal_source=model_terminal.jd --anchor '"checkpoint_source": "/tmp/native-work/runs/ppg-s1/model_terminal.jd"' \
  --fact terminal_bytes=5033857 --anchor '"checkpoint_bytes": 5033857'
C $S save-stamps --host-path "$CELL/training.log" --grep 'Saving to .*IC=' --max 20 \
  --note 'which checkpoint file holds which interaction count' \
  --fact model012_ic=600064 --anchor 'model012.jd IC=600064'

# --- the committed records, joined to those hashes ---
C $S join --command "\"$PY\" -c \"
import json, re
def listing(name):
    body = open('$B/' + name + '.txt').read().split('#' + '-' * 99 + '\n', 1)[1]
    out = {}
    for line in body.splitlines():
        size, mtime, sha, path = line.split(maxsplit=3)
        out[sha] = (path.lstrip('./'), int(size))
    return out
weights = {**listing('intermediate-weights'), **listing('terminal-weights')}
stamps = {}
for line in open('$B/save-stamps.txt').read().split('#' + '-' * 99 + '\n', 1)[1].splitlines():
    m = re.search(r'(model\d+\.jd) IC=(\d+)', line)
    stamps[m.group(1)] = int(m.group(2))
for f in ('results/records/reeval-v214-ppg-curve__records.jsonl', 'results/records/reeval-v214-ppg-endpoint__records.jsonl'):
    by_frame = {}
    n = 0
    for line in open(f):
        r = json.loads(line)
        n += 1
        by_frame.setdefault(r['frame'], set()).add(r['checkpoint_sha256'])
    print(f, 'rows', n, 'frames', len(by_frame))
    for frame, shas in sorted(by_frame.items()):
        for sha in sorted(shas):
            name, size = weights.get(sha, ('NOT-ON-HOST', 0))
            ic = stamps.get(name, 'terminal' if name == 'snapshot.pt' else '?')
            print('  frame', frame, 'sha', sha[:16], '->', name, 'IC', ic, 'match' if ic in (frame, 'terminal') else 'MISMATCH')
    print('  distinct checkpoints per frame:', sorted({len(v) for v in by_frame.values()}))
\"" --note 'every committed row names a checkpoint hash; each hash is looked up among the host files' \
  --fact curve_rows=528 --anchor 'reeval-v214-ppg-curve__records.jsonl rows 528 frames 12' \
  --fact endpoint_rows=88 --anchor 'reeval-v214-ppg-endpoint__records.jsonl rows 88 frames 1' \
  --fact curve_600064_is_model012=true --anchor '-> model012.jd IC 600064 match' \
  --fact curve_51200_is_model001=true --anchor '-> model001.jd IC 51200 match' \
  --fact endpoint_is_terminal=true --anchor '-> snapshot.pt IC terminal match'
C $S join-failures --command "sed '1,/^#---/d' $B/join.txt" --grep 'NOT-ON-HOST|MISMATCH' --allow-empty \
  --note 'absence: no row names a hash missing from the host, and no hash sits at the wrong stamp' \
  --fact unmatched_rows=0 --anchor 'header:# matched-lines: 0 '

# --- the curve's last stamp and the endpoint evaluate different FILES; are they the same weights? ---
# read-only copies from the host into a scratch directory; the probe prints each file's sha256, which
# must equal the host listing above
WORK=${EVIDENCE_WORK:-$(mktemp -d)}
H=varaksin_as@100.98.2.11:rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1
scp -q -o BatchMode=yes "$H/checkpoints/model011.jd" "$H/checkpoints/model012.jd" "$H/snapshot.pt" "$WORK/"
C $S weights-equivalence --command "\"$PY\" scripts/probe_torch_checkpoint_equivalence.py $WORK/model012.jd $WORK/snapshot.pt" \
  --note 'model012.jd (curve stamp 600,064) against snapshot.pt (endpoint): different bytes, different pickle protocol' \
  --fact model012_sha=753736df8bb4983d --anchor 'A sha256 753736df8bb4983d' \
  --fact snapshot_sha=a328e63e6ffa96f8 --anchor 'B sha256 a328e63e6ffa96f8' \
  --fact storages_identical=71/71 --anchor 'storages A 71 B 71  same keys True  byte-identical 71' \
  --fact curve_end_and_endpoint_same_weights=true --anchor 'VERDICT same tensors, same structure'
C $S weights-equivalence-negative-control --command "\"$PY\" scripts/probe_torch_checkpoint_equivalence.py $WORK/model011.jd $WORK/model012.jd" \
  --note 'control: two consecutive checkpoints must come out DIFFERENT, or the probe proves nothing' \
  --fact control_storages_identical=0/71 --anchor 'byte-identical 0' \
  --fact control_verdict=DIFFERENT --anchor 'VERDICT DIFFERENT'
