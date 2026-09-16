#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ibac-sni-vram-22-gib-was-the-colleague
RUN='~/rlvigen-runs/card1-20260916-141636/native-out'
B=results/evidence/$S/raw
WORK=${EVIDENCE_WORK:-$(mktemp -d)}

# --- the samples the cell's own sampler wrote, whole ---
C $S resources --host-path "$RUN/cells/ibac_sni-s101/resources.json" --max 0 \
  --note 'nvidia-smi samples from the ibac_sni-s101 cell (procs=16) on card 1, written by measure_resources.py'
C $S stop --host-path "$RUN/job.log" --grep '^yielded at|^free_mib=|NATIVE_CELL_(YIELDED|FAILED)' \
  --note 'the cell was stood down by the memory floor' \
  --fact s101_reason=memory-floor --anchor 'free memory 3063 MiB is below the 4000 MiB floor'

# --- what the repo script reports for it ---
# pinned to bb191cd: the revision that produced the 22,675 MiB figure (the script is being fixed after it)
C $S script-report --command "mkdir -p $WORK/data/ibac_sni-s101 && sed '1,/^#---/d' $B/resources.txt > $WORK/data/ibac_sni-s101/resources.json && git show bb191cd:scripts/measure_vram_bounds.py > $WORK/measure_vram_bounds_bb191cd.py && cd $WORK && \"$PY\" measure_vram_bounds_bb191cd.py data" \
  --note 'scripts/measure_vram_bounds.py as of bb191cd, over exactly the captured file' \
  --fact reported_ours_mib=22675 --anchor 'ibac_sni-s101        ibac_sni      None   22675 Mi   29432 Mi' \
  --fact reported_ours_gib=22.14 --anchor 'ibac_sni   22.14 GiB'
C $S script-sum --command 'git show bb191cd:scripts/measure_vram_bounds.py' --grep 'ours_peak = |procs = |for sample in samples' \
  --note 'the script sums EVERY compute process in a sample; nothing filters to our process tree' \
  --fact sums_all_processes=true --anchor 'sum(int(p.get("used_memory_mib") or 0) for p in procs)'
C $S script-claim --command 'git show bb191cd:scripts/measure_vram_bounds.py' --grep "belonging to this cell's process tree|silently inflate" \
  --note 'what the script says it does'

# --- what the samples actually contain ---
C $S decompose --command "\"$PY\" -c \"
import json
body = open('$B/resources.txt').read().split('#' + '-' * 99 + '\n', 1)[1]
r = json.loads(body)
s = r['samples']
ms = [x['monotonic_seconds'] for x in s]
print('samples', len(s), 'span_s', round(ms[-1] - ms[0], 1), 'cadence_s', round((ms[-1] - ms[0]) / (len(s) - 1), 2))
print('card uuid', sorted({g['gpu_uuid'] for x in s for g in x['gpu_devices']}))
tree = {p['pid'] for x in s for p in x['processes']}
print('tree pids (container namespace) min', min(tree), 'max', max(tree), 'count', len(tree))
last = s[-1]
for p in sorted(last['gpu_compute_processes'], key=lambda p: -p['used_memory_mib']):
    print('compute pid', p['pid'], 'MiB', p['used_memory_mib'], 'in tree', p['pid'] in tree)
first = s[0]
print('card used first', first['gpu_devices'][0]['used_memory_mib'], 'last', last['gpu_devices'][0]['used_memory_mib'])
print('process_count first', first['process_count'], 'last', last['process_count'])
big = sum(p['used_memory_mib'] for p in last['gpu_compute_processes'] if p['used_memory_mib'] > 5000)
small = sum(p['used_memory_mib'] for p in last['gpu_compute_processes'] if p['used_memory_mib'] <= 5000)
print('compute sum', big + small, '= two 10650 pids', big, '+ three small pids', small)
f_small = sum(p['used_memory_mib'] for p in first['gpu_compute_processes'] if p['used_memory_mib'] <= 5000)
print('first sample: card', first['gpu_devices'][0]['used_memory_mib'], '- our small pids', f_small, '=', first['gpu_devices'][0]['used_memory_mib'] - f_small, 'MiB held by everything else')
print('last sample: card', last['gpu_devices'][0]['used_memory_mib'], '- that =', last['gpu_devices'][0]['used_memory_mib'] - (first['gpu_devices'][0]['used_memory_mib'] - f_small), 'MiB ours if the rest stayed constant')
\"" --note 'the samples decomposed: which pids, how long, how the card grew' \
  --fact sampler_span_s=42.4 --anchor 'samples 38 span_s 42.4' \
  --fact card=GPU-6325104e --anchor "card uuid ['GPU-6325104e-9447-4ce3-1272-7b436a1b61af']" \
  --fact colleague_sized_pids=21300 --anchor '= two 10650 pids 21300 + three small pids 1375' \
  --fact no_compute_pid_in_tree=true --anchor 'compute pid 586690 MiB 759 in tree False' \
  --fact card_growth='23452 -> 29432' --anchor 'card used first 23452 last 29432' \
  --fact still_starting='process_count 2 -> 20' --anchor 'process_count first 2 last 20' \
  --fact rest_of_card_at_start_mib=22836 --anchor '= 22836 MiB held by everything else' \
  --fact ours_at_kill_if_rest_constant_mib=6596 --anchor '= 6596 MiB ours if the rest stayed constant'
C $S card-map --command 'ssh -o BatchMode=yes varaksin_as@100.98.2.11 nvidia-smi -L' \
  --note 'host card index to UUID (read-only query)' \
  --fact card1_uuid=GPU-6325104e --anchor 'GPU 1: Tesla V100-SXM2-32GB (UUID: GPU-6325104e-9447-4ce3-1272-7b436a1b61af)'
C $S occupancy --host-path '~/rlvigen-runs/gpu-occupancy.log' --grep '^2026-09-16T14:(2[4-9]).*card=1' \
  --note 'card 1 by the on-host 60 s logger, around the cell: the colleague alone at 22,836 MiB with 2 processes' \
  --fact colleague_alone_mib=22836 --anchor 'card=1 mem=22836 util=39 procs=2 holders=rlvigen_kalugin_df,rlvigen_kalugin_df'
C $S yield-time --command "\"$PY\" -c \"
import datetime as d
print('s101 yield', d.datetime.fromtimestamp(1789558045, d.timezone(d.timedelta(hours=3))).isoformat())
\"" --note 'the yield epoch in Moscow time: between two 60 s occupancy samples' \
  --fact s101_yield_time=2026-09-16T14:27:25+03:00 --anchor 's101 yield 2026-09-16T14:27:25+03:00'
C $S unmeasured-waiter-figure --host-path '~/rlvigen-runs/ibac-waiter.log' --grep 'measured ~15 GiB' --max 1 \
  --note 'an earlier figure, "measured ~15 GiB", that no measurement backs either' \
  --fact waiter_claimed_gib=15 --anchor 'ibac_sni procs=16 measured ~15 GiB'
