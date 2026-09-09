#!/usr/bin/env bash
# Pull a finished wave's records, install them, populate the evaluator ledger, report the gate.
#
#     bash datasphere/native/collect-wave.sh rlvigen:bt1... ibac_sni:bt2... [more...]
#     bash datasphere/native/collect-wave.sh --from-submissions v205
#
# [Claude 2026-09-08] Written before the v205 wave lands, because the step AFTER a wave is where
# this session actually lost time. Each family needed: `job.sh diagnose` into a scratch directory,
# then `cp <scratch>/records.jsonl results/records/<job>__records.jsonl` by hand -- the path is not
# obvious and `populate_evaluator_ledger.py` fails with a bare FileNotFoundError when it is wrong --
# then `populate_evaluator_ledger.py <family> <job>`. Three families, six manual steps, one of them
# a hand-typed path. Seven families is twenty-one.
#
# It REFUSES rather than skips on a job that did not succeed. A collector that quietly passed over
# a failed cell would leave the ledger reporting 6/7 with no indication which one is missing and
# why, and this project's rule is that an instrument which could not run must never read as one
# that ran.
set -uo pipefail
cd "$(dirname "$0")/../.."
export GRPC_DNS_RESOLVER=native
BP="${BP:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}"
SCRATCH="${SCRATCH:-${CLAUDE_JOB_DIR:-/tmp}/wave-collect}"

pairs=("$@")
if [[ "${1:-}" == "--from-submissions" ]]; then
  tag="${2:?usage: --from-submissions <tag, e.g. v205>}"
  mapfile -t pairs < <("$BP" - "$tag" <<'PY'
import json, pathlib, re, sys
tag = sys.argv[1]
seen = {}
for line in pathlib.Path("results/submissions.jsonl").read_text().splitlines():
    if not line.strip():
        continue
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    cfg = str(row.get("config") or row.get("cfg") or "")
    if tag not in cfg:
        continue
    m = re.search(r"cfg-([a-z_]+)-", pathlib.Path(cfg).name)
    job = row.get("job_id") or row.get("id")
    if m and job:
        seen[m.group(1)] = job          # later submission of a family wins
for fam, job in seen.items():
    print(f"{fam}:{job}")
PY
)
  printf 'resolved %d family:job pair(s) from results/submissions.jsonl for %s\n' "${#pairs[@]}" "$tag"
fi

[[ ${#pairs[@]} -gt 0 ]] || { echo "nothing to collect"; exit 2; }

failed=()
for pair in "${pairs[@]}"; do
  family="${pair%%:*}"; job="${pair##*:}"
  echo "=== $family  $job"
  state="$(datasphere project job get --id "$job" 2>/dev/null | tail -1 | awk '{print $(NF-3)}')"
  if [[ "$state" != "SUCCESS" ]]; then
    echo "   REFUSING: state is ${state:-unknown}, not SUCCESS. Not collected."
    failed+=("$family:$job:$state")
    continue
  fi
  dir="$SCRATCH/$job"; mkdir -p "$dir"
  bash datasphere/native/job.sh diagnose "$job" "$dir" >/dev/null 2>&1
  src="$dir/records.jsonl"
  if [[ ! -s "$src" ]]; then
    echo "   REFUSING: $src is absent or empty -- SUCCESS with no records is itself a finding."
    failed+=("$family:$job:no-records")
    continue
  fi
  cp "$src" "results/records/${job}__records.jsonl"
  echo "   installed $(wc -l < "$src" | tr -d ' ') record rows"
  # The populate step REFUSES a record whose evaluator revision is not the live one, and that
  # refusal is the most valuable thing it does. Piping it through `tail` discards its exit status,
  # so it is captured explicitly -- otherwise this collector prints "Do NOT write this entry" and
  # then exits 0, which is the quietly-passed-over failure its own header forbids.
  out="$("$BP" scripts/populate_evaluator_ledger.py "$family" "$job" 2>&1)"
  status=$?
  printf '%s\n' "$out" | tail -2 | sed 's/^/   /'
  if [[ $status -ne 0 ]] || printf '%s' "$out" | grep -q "Do NOT write this entry"; then
    echo "   REFUSED by the ledger: this record does not describe the current tree."
    failed+=("$family:$job:stale-revision")
  fi
done

echo
"$BP" scripts/production_gates.py 2>&1 | grep -iE "shared evaluator validated" | cut -c1-200
echo
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "NOT COLLECTED (${#failed[@]}):"
  printf '   %s\n' "${failed[@]}"
  echo "The ledger is short by that many families. It is not 7/7 and must not be reported as such."
  exit 1
fi
# [Claude 2026-09-09] Same class as the refusal-status capture above, one step milder and found in
# collect-host-run.sh first: a summary piped through `tail` exits 0 whatever the summary did, so a
# crashed campaign_status.py prints three lines of traceback and reads as a clean finish. The
# collection itself already succeeded by this point, so the status is reported rather than returned.
summary="$("$BP" scripts/campaign_status.py 2>&1)"
summary_status=$?
printf '%s\n' "$summary" | tail -3
if [[ $summary_status -ne 0 ]]; then
  echo "   NOTE: campaign_status.py exited $summary_status. The collection SUCCEEDED; the summary" >&2
  echo "   above is the failing command's output, not a campaign state." >&2
fi
