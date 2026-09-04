#!/usr/bin/env bash
# One place for the three things every DataSphere interaction here repeats.
#
#   bash datasphere/native/job.sh submit   datasphere/native/cfg-foo.yaml
#   bash datasphere/native/job.sh status
#   bash datasphere/native/job.sh diagnose bt1abc...
#
# Written 2026-09-03 after a wasted job: a `sed` meant to repoint a config at a new payload
# targeted `v37 -> v38` while the file still said `v36`, the submit went out against a payload
# predating the fix it was meant to test, and the failure looked identical to the one being fixed.
# `submit` therefore RESOLVES AND CHECKS every declared input before spending anything.
#
# GRPC_DNS_RESOLVER=native is not optional on this machine: gRPC's own c-ares resolver cannot
# reach a nameserver here while the system resolver can, so every CLI call fails without it.
# See docs/compute-yandex-datasphere.md section 2.
set -euo pipefail

PROJECT="${DATASPHERE_PROJECT:-bt12q57tmrs03pnt8drc}"
EVIDENCE="${NATIVE_EVIDENCE_LOG:-/tmp/ccm-intro-datasphere-recovery-2026-08-31.2KXKs5/datasphere-job-actions.log}"
export GRPC_DNS_RESOLVER=native

usage() { sed -n '2,12p' "$0"; exit 2; }

case "${1:-}" in
submit)
  cfg="${2:?config path}"
  [[ -f "$cfg" ]] || { echo "no such config: $cfg" >&2; exit 1; }
  # every `- path: NAME` under inputs must exist, resolved relative to the repo root
  missing=0
  while read -r path; do
    [[ -z "$path" ]] && continue
    if [[ ! -e "$path" ]]; then echo "MISSING INPUT: $path" >&2; missing=1
    else printf '  input ok  %-52s %s bytes\n' "$path" "$(wc -c < "$path" | tr -d ' ')"; fi
  done < <(awk '/^inputs:/{f=1;next} /^[a-z]/{f=0} f && /^  - /{sub(/^  - /,""); sub(/:.*$/,""); print}' "$cfg")
  [[ "$missing" -eq 0 ]] || { echo "refusing to submit: an input named in $cfg is not on disk" >&2; exit 1; }
  name="$(awk '/^name:/{print $2; exit}' "$cfg")"
  # `mktemp -u`, not `mktemp`: the CLI refuses to write its result over a file that already
  # exists, and mktemp creates one. The first version of this helper used mktemp, so the submit
  # succeeded, the job was created, and this script printed nothing and logged nothing -- the
  # exact silence it exists to prevent.
  out="$(mktemp -u)"
  log="$out.log"
  if ! datasphere project job execute -p "$PROJECT" -c "$cfg" --async -o "$out" >"$log" 2>&1; then
    echo "submit failed; last lines:" >&2; tail -5 "$log" >&2; exit 1
  fi
  # The id is `bt1` plus 17 characters -- twenty in total, e.g. bt199gop4olvienk7uu6. The first
  # version of this matched `bt1[a-z0-9]{19}`, which is twenty-two, so it matched nothing, the
  # `|| true` below turned that into an empty string, and the helper exited reporting an unreadable
  # id -- while the job had been created and was running. Silence with the work already done, which
  # is exactly the failure mode this helper exists to remove.
  # `|| true` on both: `set -euo pipefail` is on, and a grep that matches nothing exits 1, which
  # aborts the command substitution and with it the whole script -- silently, AFTER the job has
  # already been created. That is how the first two submits through this helper printed nothing
  # and logged nothing while succeeding.
  id="$(grep -oE 'bt1[a-z0-9]{17}' "$out" 2>/dev/null | head -1 || true)"
  [[ -n "$id" ]] || id="$(grep -oE 'bt1[a-z0-9]{17}' "$log" | head -1 || true)"
  [[ -n "$id" ]] || { echo "submitted but could not read a job id from $out or $log" >&2; exit 1; }
  echo "SUBMITTED $id  $name"
  printf '%s  SUBMIT   %s  %s (%s)\n' "$(date '+%Y-%m-%d %H:%M MSK')" "$id" "$name" "$cfg" >> "$EVIDENCE" 2>/dev/null || true
  ;;
status)
  shift || true
  ids="${*:-}"
  datasphere project job list -p "$PROJECT" 2>/dev/null \
    | { [[ -n "$ids" ]] && grep -E "$(echo "$ids" | tr ' ' '|')" || cat; } \
    | sed 's/  */ /g' \
    | awk '{id=$1; st="?"; for(f=1;f<=NF;f++) if($f ~ /^(SUCCESS|ERROR|CANCELLED|EXECUTING|PREPARING|CREATING)$/) st=$f;
            if (id ~ /^bt1/) printf "%-22s %s\n", id, st}' \
    | head -20
  ;;
diagnose)
  id="${2:?job id}"
  dir="${3:-/tmp/probe-results/$id}"
  mkdir -p "$dir"
  ( cd "$dir" && datasphere project job download-files --id "$id" --with-logs >/dev/null 2>&1 ) || true
  log="$dir/stdout.log"
  [[ -f "$log" ]] || { echo "no stdout.log downloaded for $id" >&2; exit 1; }
  echo "=== $id  ($(wc -l < "$log" | tr -d ' ') lines) ==="
  # the markers this runner emits, in the order they should appear
  grep -hE 'NATIVE_RLVIGEN_(FROM_INPUT|NO_INPUT|CLONE_FAILED)|budget ok|NATIVE_EXCLUDED_PACKAGE_PRESENT|NATIVE_FAMILY_(APT|PIP)_FAILED|NATIVE_IMPORT_GATE(_FAILED|_PASSED|_SKIPPED)?|NATIVE_PRODUCTION_(SET|KEPT|UNAPPLIED)|NATIVE_CELL_(BEGIN|COMPLETED|FAILED)|non_finite|NATIVE_FINAL_EVALUATION' "$log" | head -25
  echo "--- last non-boilerplate lines:"
  grep -vE 'Warning|warn|Deprecat|already applied|Requirement already|^\s*$' "$log" | tail -8 | cut -c1-170
  if [[ -f "$dir/result.tgz" ]]; then
    echo "--- result.tgz $(wc -c < "$dir/result.tgz" | tr -d ' ') bytes, cells:"
    tar -tzf "$dir/result.tgz" 2>/dev/null | grep -E '^\./cells/[^/]+/[^/]+$' | sed 's|^\./cells/||' | head -12
  fi
  ;;
*) usage ;;
esac
