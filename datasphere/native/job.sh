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
# `submit` below is the only supported production-scale DataSphere submission route. This cannot
# prevent a user from invoking the raw CLI independently; it makes the guarded path the one this
# project treats as admissible and binds its host identity before the CLI can upload anything.
set -euo pipefail

PROJECT="${DATASPHERE_PROJECT:-bt12q57tmrs03pnt8drc}"
EVIDENCE="${NATIVE_EVIDENCE_LOG:-/tmp/ccm-intro-datasphere-recovery-2026-08-31.2KXKs5/datasphere-job-actions.log}"
SUBMISSION_LEDGER="${SUBMISSION_LEDGER:-results/submissions.jsonl}"
# [Claude 2026-09-06] Raised 120 -> 240 minutes: owner explicitly extended the V100 allowance
# ("if you're not sure in e.g. the time limits, extend 2h to 4h") once this session's probes
# needed more than the original 2h across the renderer-parity re-run, the CTRL memory
# measurement, and the ibac_sni competence pilot. The existing state file's own recorded
# cap_minutes was bumped to match in the same edit -- load_state() refuses to use a state file
# whose stamped cap disagrees with the script's current one, by design.
# [Claude 2026-09-06, later] Raised 240 -> 420: owner unconditionally added ~3h (180 min) as a
# pre-emptive top-up ("in case you did exhaust the V100 GPU timing that was set"), not tied to a
# specific probe. Same state-file-must-match-script rule applies; bumped together.
V100_BUDGET_CAP_MINUTES=420
V100_BUDGET_STATE="${NATIVE_V100_BUDGET_STATE:-${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ccm-intro/datasphere-v100-g1-1.json}"
export GRPC_DNS_RESOLVER=native

usage() { sed -n '2,12p' "$0"; exit 2; }

expected_container_image() {
  python3 -c 'import json; from pathlib import Path; print(json.loads(Path("datasphere/native/source-lock.json").read_text())["container_image"])'
}

verify_container_image() {
  local cfg="$1" expected declared
  expected="$(expected_container_image)"
  declared="$(awk '/^[[:space:]]*image:[[:space:]]*/ {sub(/^[[:space:]]*image:[[:space:]]*/, ""); sub(/[[:space:]]+#.*$/, ""); print; exit}' "$cfg")"
  declared="${declared#\"}"; declared="${declared%\"}"
  declared="${declared#\'}"; declared="${declared%\'}"
  [[ -n "$declared" ]] || { echo "NO CONTAINER IMAGE DECLARED: $cfg" >&2; return 1; }
  [[ "$declared" == "$expected" ]] || {
    echo "MUTABLE OR MISMATCHED CONTAINER IMAGE: $declared" >&2
    echo "expected the source-locked digest: $expected" >&2
    return 1
  }
  echo "container image pinned: $declared"
}

verify_payload_input() {
  local cfg="$1" declared_cells="$2" code_input rlvigen_input resolved_cells payload_families runner_contract
  # A CODE input is the archive passed as ${CODE} to run_probe.sh. Check its contract here, while
  # the archive is still local: run_probe.sh has the same check, but only after the container has
  # started. Configurations that do not use ${CODE} remain generic job.sh submissions; a config
  # that does use it but does not declare a CODE input is rejected because run_probe.sh cannot
  # handle that shape.
  code_input="$(awk '/^inputs:/{f=1;next} /^[a-z]/{f=0} f && /^  - / && /:[[:space:]]*CODE[[:space:]]*$/{sub(/^  - /,""); sub(/[[:space:]]*:[[:space:]]*CODE[[:space:]]*$/,""); print; exit}' "$cfg")"
  if [[ -z "$code_input" ]]; then
    if grep -q '\${CODE}' "$cfg"; then
      echo "refusing to submit: config invokes \${CODE} but declares no CODE payload input" >&2
      return 1
    fi
    return 0
  fi

  # Match run_probe.sh's fallback order exactly. In particular, offline-only configs without
  # CELLS use OFFLINE_EVAL_FAMILY as their effective family; omitting that check would let a
  # wrong-family archive through and defer the rejection to the remote runner.
  resolved_cells="$declared_cells"
  if [[ -z "$resolved_cells" ]]; then
    for key in BASELINES BASELINE OFFLINE_EVAL_FAMILY; do
      resolved_cells="$(grep -oE "\\b${key}=[^[:space:]]+" "$cfg" | head -1 | cut -d= -f2- || true)"
      [[ -n "$resolved_cells" ]] && break
    done
  fi
  if [[ -z "$resolved_cells" ]]; then
    resolved_cells="drqv2"
  fi
  payload_families="$(python3 datasphere/native/family.py families-of-cells --cells "$resolved_cells")" || return 1
  payload_families="${payload_families//$'\n'/,}"
  payload_families="${payload_families%,}"
  runner_contract="$(python3 -c 'import runpy; print(runpy.run_path("datasphere/native/contract.py")["RUNNER_CONTRACT"])')" || return 1
  # [Claude 2026-09-08] Check the CONSUMING home too, not just the maintained one.
  #
  # The verify below compares the payload against contract.py's RUNNER_CONTRACT. The container
  # compares it against run_probe.sh's own `--require-runner-contract` literal. Those are two
  # homes for one number, and job bt1tceje08tpvq8cchhj proved the gap: contract.py had been bumped
  # to 14, the payload was stamped 14, this submit check passed -- and the cell then paid a full
  # apt-get bootstrap before the runner refused it for still requiring 13.
  #
  # The check that was supposed to save eight minutes cost them, because it was reading the number
  # nobody consumes. Reading both here makes the divergence impossible to submit.
  local runner_literal
  runner_literal="$(grep -oE -- '--require-runner-contract[[:space:]]+[0-9]+' datasphere/native/run_probe.sh | grep -oE '[0-9]+$' | sort -u)"
  if [[ -n "$runner_literal" && "$runner_literal" != "$runner_contract" ]]; then
    echo "refusing to submit: contract.py stamps runner contract $runner_contract but" >&2
    echo "  run_probe.sh requires [$runner_literal]. The payload would be built for one and" >&2
    echo "  refused by the other, after the bootstrap has already been paid for." >&2
    return 1
  fi
  python3 datasphere/native/contract.py verify-payload \
    --archive "$code_input" \
    --require-runner-contract "$runner_contract" \
    --require-families "$payload_families" \
    --require-evaluator-identity \
    --expect 'scripts/eval_grid.py:evaluator_revision=EVALUATOR_REVISION'
  rlvigen_input="$(awk '/^inputs:/{f=1;next} /^[a-z]/{f=0} f && /^  - / && /:[[:space:]]*RLVIGEN[[:space:]]*$/{sub(/^  - /," "); sub(/[[:space:]]*:[[:space:]]*RLVIGEN[[:space:]]*$/," "); print; exit}' "$cfg" | sed 's/^ *//;s/ *$//')"
  if [[ -z "$rlvigen_input" ]]; then
    echo "refusing validation submission: config declares CODE but no RLVIGEN archive input" >&2
    return 1
  fi
  python3 datasphere/native/contract.py verify-evaluator-binding \
    --archive "$code_input" \
    --source . \
    --families "$payload_families" \
    --rlvigen-archive "$rlvigen_input"
}

validate_submission_host_binding() {
  local cfg="$1" tier="$2" binding
  # Parse only the YAML command that DataSphere will receive. Do not source the config and do not
  # infer a profile from a description/comment: the runner sees these command assignments.
  if ! binding="$(python3 - "$cfg" "$tier" <<'PY'
import re
import shlex
import sys
from pathlib import Path

config, tier = Path(sys.argv[1]), sys.argv[2]
lines = config.read_text().splitlines()
command_lines = []
in_command = False
for line in lines:
    if line.startswith("cmd:"):
        in_command = True
        tail = line[len("cmd:"):].strip()
        if tail and tail[0] not in ">|":
            command_lines.append(tail)
        continue
    if in_command and line and not line[0].isspace():
        break
    if in_command and line.strip():
        command_lines.append(line.strip())

tokens = []
try:
    for line in command_lines:
        tokens.extend(shlex.split(line, comments=True, posix=True))
except ValueError as error:
    print(f"refusing to submit: cannot parse the forwarded cmd: {error}", file=sys.stderr)
    raise SystemExit(1)

def assignment_prefix(start):
    values = {}
    index = start
    while index < len(tokens):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", tokens[index])
        if not match:
            break
        values.setdefault(match.group(1), []).append(match.group(2))
        index += 1
    return values


# Live configs use either shell assignments before the command or `env` assignments after the
# timeout wrapper. Do not treat an assignment-looking argument to the eventual command as a real
# binding: submission safety depends on the value actually entering the runner environment.
if "env" in tokens:
    assignments = assignment_prefix(tokens.index("env") + 1)
else:
    assignments = assignment_prefix(0)

profiles = assignments.get("NATIVE_HOST_PROFILE", [])
if len(set(profiles)) > 1:
    print("refusing to submit: conflicting NATIVE_HOST_PROFILE assignments in forwarded cmd",
          file=sys.stderr)
    raise SystemExit(1)

frames = []
for raw in assignments.get("FRAMES", []):
    if raw.isdigit():
        frames.append(int(raw))
production = any(value >= 600_000 for value in frames)
production = production or any(value != "" for value in assignments.get("NATIVE_PRODUCTION", []))

datasphere_tiers = {
    "gt4.1", "gt4i.1", "g1.1", "g1.2", "g1.4",
    "g2.1", "g2.2", "g2.4", "g2.8",
    "c1.4", "c1.8", "c1.32", "c1.80",
}
admitted = "datasphere" if tier in datasphere_tiers else "unknown"
if production and admitted == "unknown":
    print(f"refusing to submit production-scale config: cannot admit cloud tier {tier!r}",
          file=sys.stderr)
    raise SystemExit(1)

if production and len(profiles) != 1:
    print("refusing to submit production-scale config: exactly one explicit "
          "NATIVE_HOST_PROFILE assignment is required in forwarded cmd", file=sys.stderr)
    raise SystemExit(1)

selected = profiles[0] if profiles else "unbound"
if profiles and selected not in {"datasphere", "v100"}:
    print(f"refusing to submit: unsupported NATIVE_HOST_PROFILE={selected!r}", file=sys.stderr)
    raise SystemExit(1)
if profiles and admitted == "unknown":
    print(f"refusing to submit: selected host profile cannot be admitted for cloud tier {tier!r}",
          file=sys.stderr)
    raise SystemExit(1)
if profiles and selected != admitted:
    if selected == "v100" and admitted == "datasphere":
        print("refusing to submit: NATIVE_HOST_PROFILE=v100 names the separate production host, "
              f"but cloud tier {tier} is DataSphere; g1.1 is diagnostic only", file=sys.stderr)
    else:
        print("refusing to submit: selected host profile "
              f"{selected!r} does not match admitted profile {admitted!r} for cloud tier {tier}",
              file=sys.stderr)
    raise SystemExit(1)

binding_state = "explicit" if profiles else "unbound"
print("\t".join((admitted, selected, binding_state, "1" if production else "0")))
PY
)"; then
    return 1
  fi
  IFS=$'\t' read -r SUBMISSION_ADMITTED_PROFILE SUBMISSION_SELECTED_PROFILE \
    SUBMISSION_PROFILE_BINDING SUBMISSION_PRODUCTION_SCALE <<< "$binding"
  echo "submission host profile: admitted=$SUBMISSION_ADMITTED_PROFILE " \
       "selected=$SUBMISSION_SELECTED_PROFILE binding=$SUBMISSION_PROFILE_BINDING " \
       "production_scale=$SUBMISSION_PRODUCTION_SCALE"
}

validate_submission_record_delivery() {
  local cfg="$1"
  python3 - "$cfg" <<'PY'
import re
import shlex
import sys
from pathlib import Path

config = Path(sys.argv[1])
lines = config.read_text().splitlines()
command_lines = []
in_command = False
for line in lines:
    if line.startswith("cmd:"):
        in_command = True
        tail = line[len("cmd:"):].strip()
        if tail and tail[0] not in ">|":
            command_lines.append(tail)
        continue
    if in_command and line and not line[0].isspace():
        break
    if in_command and line.strip():
        command_lines.append(line.strip())

try:
    tokens = []
    for line in command_lines:
        tokens.extend(shlex.split(line, comments=True, posix=True))
except ValueError as error:
    print(f"refusing to submit: cannot parse the forwarded cmd: {error}", file=sys.stderr)
    raise SystemExit(1)

assignments = {}
for token in tokens:
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", token)
    if match:
        assignments.setdefault(match.group(1), []).append(match.group(2))

def one_assignment(name):
    values = assignments.get(name, [])
    if len(values) > 1 and len(set(values)) != 1:
        print(f"refusing to submit: ambiguous {name} assignments in forwarded cmd", file=sys.stderr)
        raise SystemExit(1)
    return values[0] if values else None

offline = one_assignment("OFFLINE_EVAL_SNAPSHOT")
production_values = assignments.get("NATIVE_PRODUCTION", [])
if len(production_values) > 1 and len(set(production_values)) != 1:
    print("refusing to submit: ambiguous NATIVE_PRODUCTION assignments in forwarded cmd",
          file=sys.stderr)
    raise SystemExit(1)
production = any(value == "1" for value in production_values)
frames = [int(value) for value in assignments.get("FRAMES", []) if value.isdigit()]
production = production or any(value >= 600_000 for value in frames)

if not offline and not production:
    raise SystemExit(0)

records_values = assignments.get("RECORDS_OUT", [])
if len(records_values) > 1:
    print("refusing to submit: ambiguous RECORDS_OUT assignments in forwarded cmd", file=sys.stderr)
    raise SystemExit(1)
if len(records_values) != 1 or not records_values[0]:
    print("refusing to submit: eval-only/production command must contain exactly one nonempty "
          "RECORDS_OUT binding", file=sys.stderr)
    raise SystemExit(1)
records_value = records_values[0]
if records_value not in {"${RECORDS}", "records.jsonl"}:
    print("refusing to submit: RECORDS_OUT must use the supported ${RECORDS} or records.jsonl "
          "binding", file=sys.stderr)
    raise SystemExit(1)

outputs = []
in_outputs = False
for line in lines:
    if line == "outputs:":
        in_outputs = True
        continue
    if in_outputs and line and not line[0].isspace():
        break
    if in_outputs:
        match = re.match(r"^\s*-\s*([^:#\s]+)\s*:\s*([^#\s]+)", line)
        if match:
            outputs.append((match.group(1), match.group(2)))

if records_value == "${RECORDS}":
    valid = [path for path, name in outputs if name == "RECORDS"]
else:
    valid = [path for path, _ in outputs if path == records_value]
if len(valid) != 1:
    print("refusing to submit: RECORDS_OUT has no unique corresponding `outputs` declaration",
          file=sys.stderr)
    raise SystemExit(1)
PY
}

v100_budget_command() {
  V100_BUDGET_CAP_MINUTES="$V100_BUDGET_CAP_MINUTES" python3 - "$@" <<'PY'
import datetime as dt
import json
import os
import re
import secrets
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

CAP = int(os.environ["V100_BUDGET_CAP_MINUTES"])


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def load_state(path, missing_ok=True):
    if not path.exists():
        if missing_ok:
            return {"schema": 1, "cap_minutes": CAP, "reservations": []}
        fail(f"V100 budget state does not exist: {path}")
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"refusing to use unreadable V100 budget state {path}: {error}")
    if (not isinstance(state, dict) or state.get("schema") != 1
            or state.get("cap_minutes") != CAP
            or not isinstance(state.get("reservations"), list)):
        fail(f"refusing to use invalid V100 budget state {path}")
    for item in state["reservations"]:
        if (not isinstance(item, dict) or not isinstance(item.get("reserved_minutes"), int)
                or item["reserved_minutes"] <= 0 or item["reserved_minutes"] > CAP):
            fail(f"refusing to use malformed V100 reservation in {path}")
        actual = item.get("actual_minutes")
        if actual is not None and (not isinstance(actual, (int, float)) or actual < 0):
            fail(f"refusing to use malformed actual V100 usage in {path}")
    return state


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def lock_state(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = Path(str(path) + ".lock")
    try:
        lock.mkdir()
    except FileExistsError:
        fail(f"refusing V100 budget update: lock already exists at {lock}")
    try:
        yield
    finally:
        lock.rmdir()


def accounted(item):
    actual = item.get("actual_minutes")
    return max(float(item["reserved_minutes"]), float(actual or 0))


def summary(state):
    reserved = sum(float(item["reserved_minutes"]) for item in state["reservations"])
    actual = sum(float(item["actual_minutes"]) for item in state["reservations"]
                 if item.get("actual_minutes") is not None)
    accounted_total = sum(accounted(item) for item in state["reservations"])
    return {"cap_minutes": CAP, "reserved_minutes": reserved,
            "actual_minutes_known": actual, "accounted_minutes": accounted_total,
            "remaining_minutes": CAP - accounted_total,
            "reservations": state["reservations"]}


def parse_minutes(raw):
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        fail("NATIVE_V100_RESERVATION_MINUTES must be a positive integer number of minutes")
    minutes = int(raw)
    if minutes > CAP:
        fail(f"V100 reservation {minutes} minutes exceeds the {CAP}-minute allowance")
    return minutes


def reserve(path, config, raw_minutes):
    minutes = parse_minutes(raw_minutes)
    with lock_state(path):
        state = load_state(path)
        used = sum(accounted(item) for item in state["reservations"])
        if used + minutes > CAP:
            fail(f"V100 reservation of {minutes} minutes would exceed the {CAP}-minute "
                 f"allowance (already accounted: {used:g} minutes)")
        reservation_id = "v100-" + secrets.token_hex(8)
        state["reservations"].append({
            "reservation_id": reservation_id, "tier": "g1.1",
            "config": str(Path(config).resolve()), "reserved_minutes": minutes,
            "actual_minutes": None, "job_id": None, "status": "reserved",
            "reserved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        write_state(path, state)
    print(reservation_id)


def finalize(path, reservation_id, job_id):
    with lock_state(path):
        state = load_state(path, missing_ok=False)
        matches = [item for item in state["reservations"]
                   if item.get("reservation_id") == reservation_id]
        if len(matches) != 1 or matches[0].get("status") != "reserved":
            fail(f"cannot finalize unknown or already-finalized V100 reservation {reservation_id}")
        item = matches[0]
        item["job_id"] = job_id
        item["status"] = "submitted"
        item["submitted_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_state(path, state)


def metadata_items(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("jobs", "items"):
            if isinstance(raw.get(key), list):
                return raw[key]
        return [raw]
    fail("DataSphere metadata must be a JSON object or a list of objects")


def field(item, *names):
    for name in names:
        if item.get(name) is not None:
            return item[name]
    return None


def timestamp(value):
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def reconcile(path, metadata_path):
    try:
        raw = json.loads(Path(metadata_path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"refusing unreadable DataSphere metadata {metadata_path}: {error}")
    with lock_state(path):
        state = load_state(path, missing_ok=False)
        by_job = {item.get("job_id"): item for item in state["reservations"]
                  if item.get("job_id")}
        updated = 0
        for metadata in metadata_items(raw):
            if not isinstance(metadata, dict):
                continue
            item = by_job.get(field(metadata, "job_id", "jobId", "id"))
            if item is None:
                continue
            started = timestamp(field(metadata, "created_at", "createdAt", "created"))
            finished = timestamp(field(metadata, "finished_at", "finishedAt", "finished"))
            if started is None or finished is None:
                continue
            elapsed = (finished - started).total_seconds() / 60.0
            if elapsed < 0:
                fail(f"refusing DataSphere metadata with negative elapsed time for {item['job_id']}")
            item["actual_minutes"] = round(elapsed, 3)
            item["actual_source"] = str(Path(metadata_path).resolve())
            item["reconciled_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            updated += 1
        if updated:
            write_state(path, state)
    print(json.dumps({"updated": updated, **summary(state)}, indent=2, sort_keys=True))


command = sys.argv[1] if len(sys.argv) > 1 else ""
if command == "reserve" and len(sys.argv) == 5:
    reserve(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
elif command == "finalize" and len(sys.argv) == 5:
    finalize(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
elif command == "status" and len(sys.argv) == 3:
    print(json.dumps(summary(load_state(Path(sys.argv[2]))), indent=2, sort_keys=True))
elif command == "reconcile" and len(sys.argv) == 4:
    reconcile(Path(sys.argv[2]), sys.argv[3])
else:
    fail("usage: reserve STATE CONFIG MINUTES | finalize STATE RESERVATION_ID JOB_ID | "
         "status STATE | reconcile STATE METADATA_JSON")
PY
}

timeout_budget_minutes() {
  local cfg="$1"
  python3 - "$cfg" <<'PY'
import re
import shlex
import sys
from pathlib import Path

config = Path(sys.argv[1])
lines = config.read_text().splitlines()
command_lines = []
in_command = False
for line in lines:
    if line.startswith("cmd:"):
        in_command = True
        tail = line[len("cmd:"):].strip()
        if tail and tail[0] not in ">|":
            command_lines.append(tail)
        continue
    if in_command and line and not line[0].isspace():
        break
    if in_command and line.strip():
        command_lines.append(line.strip())

try:
    tokens = []
    for line in command_lines:
        tokens.extend(shlex.split(line, comments=True, posix=True))
except ValueError as error:
    print(f"cannot parse forwarded cmd: {error}", file=sys.stderr)
    raise SystemExit(1)

matches = []
for index, token in enumerate(tokens):
    if token != "timeout":
        continue
    if (index + 2 >= len(tokens) or tokens[index + 1] != "--foreground"
            or not re.fullmatch(r"[1-9][0-9]*s", tokens[index + 2])):
        print("timeout must use exactly `timeout --foreground <positive-integer>s`", file=sys.stderr)
        raise SystemExit(1)
    matches.append(int(tokens[index + 2][:-1]))

if len(matches) != 1:
    print("command must contain exactly one parseable `timeout --foreground <positive-integer>s`",
          file=sys.stderr)
    raise SystemExit(1)

seconds = matches[0]
print(f"{seconds}\t{(seconds + 59) // 60}")
PY
}

case "${1:-}" in
submit)
  cfg="${2:?config path}"
  [[ -f "$cfg" ]] || { echo "no such config: $cfg" >&2; exit 1; }
  verify_container_image "$cfg"
  cells="$(grep -oE '\bCELLS=[^[:space:]]+' "$cfg" | head -1 | cut -d= -f2- || true)"
  tier="$(awk '/^cloud-instance-type:/{print $2; exit}' "$cfg")"
  # [Claude 2026-09-06] Was an inline g1.1->gt4i.1 mapping duplicated here and in
  # scripts/audit_submission_configs.py's own simulation of this path -- the audit's copy was
  # missing and flagged two configs that had already submitted and run for real. One home now:
  # datasphere/native/family.py::admission_tier_for.
  admission_tier="$(python3 datasphere/native/family.py admission-tier --tier "$tier")"
  validate_submission_host_binding "$cfg" "$tier"
  validate_submission_record_delivery "$cfg"
  # Memory admission must see the argv the YAML will actually execute.  In particular, IBAC's
  # `--procs=16` creates sixteen independent EGL/MuJoCo worker processes; checking only the
  # descriptor's probe-safe procs=1 admitted a shape that the 16 GiB tier OOM-killed in 49 s
  # (bt1kgfmbbjhnslfjekg1).  Parse the inert config text here -- do not source it -- and pass only
  # this one command override to family.py.
  cfg_extra_overrides="$(grep -oE '\bNATIVE_EXTRA_OVERRIDES=[^[:space:]]+' "$cfg" | head -1 | cut -d= -f2- || true)"
  if [[ -n "$cells" && -n "$tier" ]]; then
    python3 datasphere/native/family.py check-tier --cells "$cells" --tier "$admission_tier"
    # Tier feasibility must be checked on the submission path. The planner also checks RAM, but
    # a hand-written cfg can bypass the planner and send ALDA to gt4.1, where its measured fixed
    # working set is too close to the usable limit.
    # [Claude 2026-09-07] Pass the config's OWN budget. check_memory now charges the replay
    # allocation that families.json's fixed_peak_gib excludes, and that charge is budget-dependent:
    # without this a 10k probe is sized against a 600k buffer and refused on a tier it fits on.
    cfg_frames="$(grep -oE '\bFRAMES=[0-9]+' "$cfg" | head -1 | cut -d= -f2- || true)"
    NATIVE_EXTRA_OVERRIDES="$cfg_extra_overrides" \
      python3 datasphere/native/family.py check-memory --cells "$cells" --tier "$admission_tier" \
        ${cfg_frames:+--frames "$cfg_frames"}
  fi
  # every `- path: NAME` under inputs must exist, resolved relative to the repo root
  missing=0
  while read -r path; do
    [[ -z "$path" ]] && continue
    if [[ ! -e "$path" ]]; then echo "MISSING INPUT: $path" >&2; missing=1
    else printf '  input ok  %-52s %s bytes\n' "$path" "$(wc -c < "$path" | tr -d ' ')"; fi
  done < <(awk '/^inputs:/{f=1;next} /^[a-z]/{f=0} f && /^  - /{sub(/^  - /,""); sub(/:.*$/,""); print}' "$cfg")
  [[ "$missing" -eq 0 ]] || { echo "refusing to submit: an input named in $cfg is not on disk" >&2; exit 1; }
  verify_payload_input "$cfg" "$cells" || {
    echo "refusing to submit: CODE payload compatibility check failed" >&2
    exit 1
  }
  reservation_id=""
  if [[ "$tier" == "g1.1" ]]; then
    reservation_minutes="$(grep -oE '\bNATIVE_V100_RESERVATION_MINUTES=[^[:space:]]+' "$cfg" \
      | head -1 | cut -d= -f2- || true)"
    if [[ -z "$reservation_minutes" ]]; then
      echo "refusing to submit g1.1: config must explicitly set NATIVE_V100_RESERVATION_MINUTES" >&2
      exit 1
    fi
    if [[ ! "$reservation_minutes" =~ ^[1-9][0-9]*$ ]]; then
      echo "NATIVE_V100_RESERVATION_MINUTES must be a positive integer number of minutes" >&2
      exit 1
    fi
    timeout_budget="$(timeout_budget_minutes "$cfg")" || {
      echo "refusing to submit g1.1: timeout bound is absent, ambiguous, or unparseable" >&2
      exit 1
    }
    IFS=$'\t' read -r timeout_seconds required_minutes <<< "$timeout_budget"
    if (( reservation_minutes < required_minutes )); then
      echo "refusing to submit g1.1: reservation ${reservation_minutes} minutes is below " \
           "the command timeout bound of ${required_minutes} minutes (${timeout_seconds}s)" >&2
      exit 1
    fi
    reservation_id="$(v100_budget_command reserve "$V100_BUDGET_STATE" "$cfg" "$reservation_minutes")" || {
      echo "refusing to submit g1.1: V100 allowance reservation failed" >&2
      exit 1
    }
    echo "reserved g1.1 V100 allowance: ${reservation_minutes} minutes ($reservation_id)"
  fi
  name="$(awk '/^name:/{print $2; exit}' "$cfg")"
  # `mktemp -u`, not `mktemp`: the CLI refuses to write its result over a file that already
  # exists, and mktemp creates one. The first version of this helper used mktemp, so the submit
  # succeeded, the job was created, and this script printed nothing and logged nothing -- the
  # exact silence it exists to prevent.
  out="$(mktemp -u)"
  log="$out.log"
  if ! datasphere project job execute -p "$PROJECT" -c "$cfg" --async -o "$out" >"$log" 2>&1; then
    if [[ -n "$reservation_id" ]]; then
      echo "g1.1 reservation $reservation_id retained: submission outcome is ambiguous" >&2
    fi
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
  if [[ -n "$reservation_id" ]]; then
    v100_budget_command finalize "$V100_BUDGET_STATE" "$reservation_id" "$id" || {
      echo "submitted $id but could not finalize g1.1 reservation $reservation_id; allowance remains held" >&2
      exit 1
    }
  fi
  echo "SUBMITTED $id  $name"
  printf '%s  SUBMIT   %s  %s profile=%s tier=%s binding=%s (%s)\n' \
    "$(date '+%Y-%m-%d %H:%M MSK')" "$id" "$name" \
    "$SUBMISSION_ADMITTED_PROFILE" "$tier" "$SUBMISSION_PROFILE_BINDING" "$cfg" \
    >> "$EVIDENCE" 2>/dev/null || true
  # [Claude 2026-09-07, external review 20 #24 / recommendation 22] A record pins the exact BYTES
  # that ran -- payload_sha256, manifest_sha256, container_image -- and nothing maps those bytes
  # back to a commit anyone can check out. This writes that mapping at the one moment both are
  # known, so a result is traceable to a tree without trusting anybody's memory of which commit
  # was current. Machine-readable on purpose: it is also the first column of the attempt ledger
  # the recommendation asks for (job id -> cfg -> commit -> inputs).
  #
  # Never fatal: a submission that succeeded must not be reported as failed because a log write
  # did not.
  python3 - "$id" "$name" "$cfg" "$tier" >> "$SUBMISSION_LEDGER" 2>/dev/null <<'LEDGER' || true
import hashlib, json, pathlib, re, subprocess, sys, datetime

job_id, name, cfg, tier = sys.argv[1:5]
root = pathlib.Path(__file__).resolve().parent if False else pathlib.Path(".").resolve()

def git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:
        return ""

def sha256(path):
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None

inputs = {}
try:
    text = pathlib.Path(cfg).read_text()
    block = text.split("inputs:", 1)[1].split("\noutputs:", 1)[0]
    for line in block.splitlines():
        match = re.match(r"\s*-\s*([^:]+):", line)
        if match:
            relative = match.group(1).strip()
            inputs[relative] = sha256(relative)
except Exception:
    pass

print(json.dumps({
    "submitted_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "job_id": job_id,
    "name": name,
    "config": cfg,
    "tier": tier,
    "source_commit": git("rev-parse", "HEAD"),
    # A dirty tree at submit time means the commit does NOT describe what was uploaded.
    #
    # [Claude 2026-09-08] The ledger EXCLUDES ITSELF. `results/submissions.jsonl` is untracked and
    # is written by this very block, so from the first submission onward `git status --porcelain`
    # was never empty and every row said `source_dirty: true` -- including the six submitted from
    # a verified-clean tree that `production_gates.py::gate_source_tree_frozen` had just passed.
    # A flag that reports the same value whatever the world does carries no information, and this
    # one would have made a genuinely dirty submission indistinguishable from a clean one.
    # Parse the PATH, not a fixed offset. `git()` above strips the whole output, which removes
    # porcelain's leading status space on the first line only -- so ` M results/submissions.jsonl`
    # arrived here as `M results/submissions.jsonl` and `line[3:]` yielded `esults/...`, missing the
    # one file this exclusion exists for. The first submission of a batch read false and every
    # later one read true, which looked like the flag working and was an off-by-one.
    "source_dirty": bool([
        line for line in git("status", "--porcelain").splitlines()
        if line.split(maxsplit=1)[-1].strip()
        not in {"results/submissions.jsonl", "results/attempt-outcomes.json"}
    ]),
    "inputs_sha256": inputs,
}, sort_keys=True))
LEDGER
  ;;
verify-image)
  cfg="${2:?config path}"
  [[ -f "$cfg" ]] || { echo "no such config: $cfg" >&2; exit 1; }
  verify_container_image "$cfg"
  ;;
v100-budget)
  case "${2:-status}" in
  status)
    [[ "$#" -eq 2 ]] || { echo "usage: $0 v100-budget status" >&2; exit 2; }
    v100_budget_command status "$V100_BUDGET_STATE"
    ;;
  reconcile)
    metadata="${3:?usage: $0 v100-budget reconcile METADATA_JSON}"
    [[ -f "$metadata" ]] || { echo "no such metadata file: $metadata" >&2; exit 1; }
    v100_budget_command reconcile "$V100_BUDGET_STATE" "$metadata"
    ;;
  *)
    echo "usage: $0 v100-budget {status|reconcile METADATA_JSON}" >&2
    exit 2
    ;;
  esac
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
