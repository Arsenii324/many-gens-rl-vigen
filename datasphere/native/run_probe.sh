#!/usr/bin/env bash
set -euo pipefail

# A V100 run must select its profile explicitly.  Keeping the DataSphere default here preserves
# every existing probe config, while the manifest below makes the effective host observable.
# Whether the CALLER named a host must be captured BEFORE the default is applied, or the
# production guard below can never fire: after this line the variable is always set, so testing it
# for emptiness tests nothing. (Written after doing exactly that.)
if [[ -n "${NATIVE_HOST_PROFILE:-}" ]]; then
  NATIVE_HOST_PROFILE_EXPLICIT=1
else
  NATIVE_HOST_PROFILE_EXPLICIT=0
fi
export NATIVE_HOST_PROFILE_EXPLICIT
export NATIVE_HOST_PROFILE="${NATIVE_HOST_PROFILE:-datasphere}"

# [Claude 2026-09-08] THE SENTINEL IS NEVER A DISABLE, WHEREVER IT COMES FROM.
#
# The 2026-09-07 fix for external review 21 P0 resolves a per-family spelling of "never evaluate"
# -- but only on the branch where EVAL_EVERY_FRAMES is UNSET. Twenty attest and cover cfgs set
# 2147483647 explicitly, which takes the else branch straight back to the value the fix exists to
# remove, and `0 % 2147483647 == 0` is True, so a full evaluation ran at step 0 under a manifest
# saying online evaluation was off. Job bt1utl06n6mqffrt2jdn's own log carries the proof:
# `| eval | F: 0 | S: 0 | E: 0 | L: 500 | R: 7.6385`.
#
# Those episodes draw from the process-global NumPy stream Door's placement uses, so training
# placements were perturbed -- by a different amount per family, since the loops differ.
#
# Normalising HERE rather than editing twenty cfgs is deliberate: it fixes every cfg that already
# exists and every one anyone writes later, including the production ones, which do not exist yet.
# The value is mapped to the family's own spelling, and the substitution is announced rather than
# silent, so a run that relied on the sentinel is identifiable in its own log.
normalize_eval_sentinel() {
  local cells="$1"
  [[ "${EVAL_EVERY_FRAMES:-}" == "2147483647" ]] || return 0
  local spelling="${NATIVE_ONLINE_EVAL_DISABLED_SPELLING:-}"
  if [[ -z "$spelling" ]]; then
    spelling="$(python3 "$FAMILY_TOOL" production-env --cells "$cells" 2>/dev/null \
      | sed -n 's/^NATIVE_ONLINE_EVAL_DISABLED_SPELLING=//p' | head -1)"
  fi
  if [[ -z "$spelling" ]]; then
    # No spelling means the family has no `{eval_every}` option at all -- true of idaac, ppg,
    # ibac_sni and ctrl, whose loops never receive this value, so the sentinel cannot reach a
    # `step % cadence` test through it. Leave it alone and say nothing: refusing here would break
    # four families' cfgs to fix a defect they never had.
    return 0
  fi
  echo "=== NATIVE_EVAL_SENTINEL_NORMALIZED 2147483647 -> ${spelling} ===" >&2
  EVAL_EVERY_FRAMES=""
  export NATIVE_ONLINE_EVAL_DISABLED_SPELLING="$spelling"
  # ALSO set the disable flag, and this is the half the first version missed.
  #
  # Clearing EVAL_EVERY_FRAMES is not enough on its own, because the guarded branch below is
  # `NATIVE_DISABLE_ONLINE_EVAL == 1 AND -z EVAL_EVERY_FRAMES` -- and that flag is only ever
  # exported by `apply_production_settings`, which returns immediately unless NATIVE_PRODUCTION is
  # set. No diagnostic cfg sets it. So for every attest and cover cell the disable path was
  # unreachable, and clearing the variable alone dropped through to
  # `eval_every="${EVAL_EVERY_FRAMES:-$frames}"` -- i.e. the whole budget as a cadence.
  #
  # Measured, in job bt1kj79a5o9gs61qkl96, which is where this was found: with the sentinel deleted
  # from the cfg the cell reported `eval_every_frames=10000` and evaluated at F: 0 AND F: 10000.
  # Deleting the line made it strictly worse than leaving it. Passing the sentinel is a request to
  # disable; honouring it means saying so to the branch that acts on it.
  export NATIVE_DISABLE_ONLINE_EVAL=1
}

run_measured() {
  local output_dir="$1"
  shift
  local temporary
  temporary="$(mktemp -d)"
  local pipe="$temporary/training.pipe"
  local sampler_ready="$temporary/sampler.ready"
  mkfifo "$pipe"
  # Keep a small supervisor alive while the sampler takes its first process-tree sample. Without
  # this handshake, a short but successful command can exit between starting the sampler and its
  # first poll, leaving an empty resources.json and making the runner's evidence depend on timing.
  # [Claude 2026-09-08] PYTHONUNBUFFERED=1, and the stall watchdog below is UNSOUND without it.
  #
  # Python block-buffers stdout when it is not a tty, and the cell's stdout is this function's
  # fifo. So a cell can be working perfectly and emit nothing for a long time simply because its
  # 8 KB buffer has not filled -- which is indistinguishable, to a watchdog reading the log's size,
  # from a hang.
  #
  # That is not hypothetical. It killed two healthy `ctrl` cells: `bt1hvkmei18hasgj5bbv` and
  # `bt17gfr8pq5astv4g3n3`, both NATIVE_CELL_STALLED after 1800s of silence, both diagnosed at the
  # time as a CUDA driver/runtime problem because their last line was a `cuStreamGetGreenCtx`
  # warning. The 10k `ctrl` cell that SUCCEEDED (`bt1d8jicbkdu1jv87ogp`) printed that same warning,
  # the same 8.27 GiB allocator message and the same buffer-comparator diffs, then ran to 1851
  # lines -- so none of those was the failure. `runnable/ctrl/train_ppo.py` has five `print()`
  # calls and exactly one passes `flush=True`.
  #
  # A watchdog that measures a stdout buffer's flush cadence instead of a process's liveness would
  # have killed the 45-hour production `ctrl` cell at thirty minutes.
  local supervisor_script='ready="$1"; shift; while [[ ! -e "$ready" ]]; do sleep 0.01; done; export PYTHONUNBUFFERED=1; "$@"'
  if command -v setsid >/dev/null; then
    setsid bash -c "$supervisor_script" run_probe_supervisor "$sampler_ready" "$@" > "$pipe" 2>&1 &
  else
    bash -c "$supervisor_script" run_probe_supervisor "$sampler_ready" "$@" > "$pipe" 2>&1 &
  fi
  local training_pid="$!"
  python3 datasphere/native/measure_resources.py --pid "$training_pid" --output "$output_dir/resources.json" \
    --ready-file "$sampler_ready" &
  local sampler_pid="$!"
  tee "$output_dir/training.log" < "$pipe" &
  local tee_pid="$!"

  # [Claude 2026-09-08] STALL WATCHDOG. `CELL_TIMEOUT_SECONDS` bounds how long a cell may RUN; it
  # cannot bound how long a DEAD cell takes to notice. Job bt12f5us5h120laajpme is the case that
  # forced this: a Places365 DataLoader worker took SIGABRT at ~8500 frames, the exception
  # propagated and printed, and the process then sat there until the 7800s cell timeout fired 105
  # minutes later. Roughly 1200 of 7800 seconds were work.
  #
  # A timeout must be sized for the longest legitimate RUN -- 45 hours at production scale -- so it
  # is a useless bound on a hang. A stall detector is sized for the longest legitimate SILENCE,
  # which is short and, importantly, does not grow with the run.
  #
  # Longest measured silent phase is the Places365 first load at 561.8s. Everything else is
  # noisier: training logs every 500 frames (111s at sgqn's measured 4.51 fps), and the endpoint
  # eval grid is 96s end to end (NATIVE_ENDPOINT_EVAL_SECONDS, job bt1utl06n6mqffrt2jdn). The
  # 1800s default is 3.2x the longest silence anyone has measured. It would have killed the svea
  # cell above at ~30 minutes instead of ~105.
  #
  # Kill the process GROUP, not the pid: the thing that hangs is often a child (a DataLoader
  # worker, a vectorised env worker), and killing the parent alone can leave it. `setsid` above
  # puts the cell in its own session, so the group is exactly the cell and nothing else.
  local stall_pid=""
  local stall_seconds="${CELL_STALL_SECONDS:-1800}"
  if [[ "$stall_seconds" != "0" ]]; then
    (
      log="$output_dir/training.log"
      last_size=-1
      quiet=0
      pgid="$(ps -o pgid= -p "$training_pid" 2>/dev/null | tr -d ' ')"
      while kill -0 "$training_pid" 2>/dev/null; do
        sleep 30
        size="$(wc -c < "$log" 2>/dev/null || echo 0)"
        if [[ "$size" == "$last_size" ]]; then
          quiet=$((quiet + 30))
        else
          quiet=0
          last_size="$size"
        fi
        if [[ "$quiet" -ge "$stall_seconds" ]]; then
          echo "=== NATIVE_CELL_STALLED no output for ${quiet}s (limit ${stall_seconds}s) ===" >&2
          if [[ -n "$pgid" ]]; then
            kill -TERM "-$pgid" 2>/dev/null
            sleep 20
            kill -KILL "-$pgid" 2>/dev/null
          else
            kill -TERM "$training_pid" 2>/dev/null
            sleep 20
            kill -KILL "$training_pid" 2>/dev/null
          fi
          exit 0
        fi
      done
    ) &
    stall_pid="$!"
  fi

  # [Claude 2026-09-08] POLICY-HEALTH WATCH, alongside the stall watchdog and deliberately NOT
  # merged into it: one kills, this one only speaks. PRODUCTION-RUNBOOK lists "an alert on
  # `log_std` drift rather than post-hoc inspection" as not built and worth having before day one,
  # because the failure it catches survives every other check -- ibac_sni at sigma ~ 4.3, entropy
  # climbing 9.95 -> 20.03, success 0.00, and finite the whole way. At 45 hours for the longest
  # cell, post-hoc means the run is over before anyone knows.
  #
  # It never aborts. DECISIONS-IF-PRODUCTION-GOES-WRONG's rule holds here too: a faithfully
  # implemented method that simply performs badly is a result, not a defect, and a watchdog that
  # killed on saturation would delete exactly those results -- for whichever baseline struggled
  # most, which is the worst selection rule available.
  # NO `-f` GUARD, deliberately. The first version of this block had one, and it would have made
  # the watcher a silent no-op on the container: `watch_policy_health.py` was not in
  # `contract.py::PAYLOAD_MEMBERS`, so the file is absent there, the guard is false, and nothing is
  # said -- while PRODUCTION-RUNBOOK tells the operator it runs on every cell. That is precisely
  # the "an instrument that cannot run must never read as one that ran" failure this watcher was
  # built to catch, rebuilt inside it. The member is declared and RUNNER_CONTRACT is bumped to 14,
  # so a payload without it is refused at the contract boundary rather than here.
  # [Claude 2026-09-08] YIELD WATCH. The other half of scripts/yield_gpu_to_neighbour.py, which
  # observes the card from a separate container and writes a sentinel when a co-tenant appears.
  #
  # Why a sentinel and not a signal. Stopping this container from outside would need
  # /var/run/docker.sock mounted into the observer -- root-equivalent access to the host, a far
  # worse hazard on a shared machine than the one being solved. So the observer writes a file and
  # THIS process decides to stop. The cell keeps sole authority over the cell.
  #
  # It kills the training process group, exactly as the stall watchdog does, and for the same
  # reason: checkpoints are already durable on the /tmp/native-out and /tmp/native-work bind
  # mounts, so a yielded cell loses the remainder of its training and none of its artifacts.
  #
  # NATIVE_YIELD_SENTINEL is unset by default, so this costs nothing on a machine we own.
  local yield_pid=""
  if [[ -n "${NATIVE_YIELD_SENTINEL:-}" ]]; then
    rm -f "$NATIVE_YIELD_SENTINEL"
    (
      while kill -0 "$training_pid" 2>/dev/null; do
        if [[ -e "$NATIVE_YIELD_SENTINEL" ]]; then
          # [Claude 2026-09-09] Do not name the cause here. The sentinel carries the real reason,
          # and it is not always a co-tenant: a 600k packed run stopped itself because OUR OWN six
          # processes had taken 29910 MiB of 32494 and free memory fell under the floor. The log
          # then said "a co-tenant needs the card" while no co-tenant existed, which sent the first
          # reader looking for a neighbour who was never there.
          echo "=== NATIVE_CELL_YIELDED stopping this cell; reason follows from the sentinel ===" >&2
          cat "$NATIVE_YIELD_SENTINEL" >&2 2>/dev/null || true
          echo "    Artifacts written so far are durable on the bind mounts." >&2
          kill -TERM -- "-$training_pid" 2>/dev/null || kill -TERM "$training_pid" 2>/dev/null
          sleep 30
          kill -KILL -- "-$training_pid" 2>/dev/null || kill -KILL "$training_pid" 2>/dev/null
          exit 0
        fi
        sleep 15
      done
    ) &
    yield_pid="$!"
    # [Claude 2026-09-08] Announce that a cell is now on the card, into the same shared directory
    # the sentinel uses. Closes a real blind spot: the observers count compute processes against a
    # baseline, and during the ~10 minute apt/pip bootstrap OUR count is zero -- so the FIRST
    # process to appear was credited to us, and a stranger arriving in that window was silently
    # absorbed as our own. With this marker they expect ZERO processes until the cell says
    # otherwise, and any process before it is unambiguously somebody else.
    : > "$(dirname "$NATIVE_YIELD_SENTINEL")/cell-active"
    echo "=== NATIVE_YIELD_WATCH_ARMED sentinel=$NATIVE_YIELD_SENTINEL ===" >&2
    echo "=== NATIVE_CELL_ACTIVE_MARKER $(dirname "$NATIVE_YIELD_SENTINEL")/cell-active ===" >&2
  fi

  local health_pid=""
  if [[ -z "${NATIVE_NO_POLICY_HEALTH_WATCH:-}" ]]; then
    python3 scripts/watch_policy_health.py --log "$output_dir/training.log" --interval 60 \
      2>>"$output_dir/training.log" &
    health_pid="$!"
  fi

  set +e
  wait "$training_pid"
  local training_status="$?"
  if [[ -n "$stall_pid" ]]; then kill "$stall_pid" 2>/dev/null; wait "$stall_pid" 2>/dev/null; fi
  if [[ -n "$health_pid" ]]; then kill "$health_pid" 2>/dev/null; wait "$health_pid" 2>/dev/null; fi
  if [[ -n "$yield_pid" ]]; then kill "$yield_pid" 2>/dev/null; wait "$yield_pid" 2>/dev/null; fi
  # [Claude 2026-09-08] Retract the marker. Creating it closed the bootstrap blind spot; never
  # removing it opened a symmetric one at the other end. After the cell exits, our count returns to
  # zero but the observers go on expecting one process of ours -- so a neighbour who takes the card
  # we have just VACATED reads as a breach. That is a false alarm raised at exactly the moment the
  # card is legitimately theirs, and an instrument that cries wolf once it has stopped mattering is
  # one an operator learns to ignore. Marker present means a cell is on the card, and now that is
  # true in both directions.
  if [[ -n "${NATIVE_YIELD_SENTINEL:-}" ]]; then
    rm -f "$(dirname "$NATIVE_YIELD_SENTINEL")/cell-active"
    echo "=== NATIVE_CELL_ACTIVE_MARKER_CLEARED ===" >&2
  fi
  wait "$tee_pid"
  local tee_status="$?"
  wait "$sampler_pid"
  local sampler_status="$?"
  set -e
  # [Claude 2026-09-02 00:45 MSK: return the status explicitly. `set -e` is disabled inside a
  # function called in a condition context, so a bare `[[ ... ]]` would let a failed trainer
  # report success to the per-baseline loop below.]
  # [Claude 2026-09-03: GNU `time -v` prints BOTH "Command terminated by signal 9" and, a few
  # lines later, "Exit status: 0". The second line is meaningless once the first appears, and
  # reading it turns an OOM kill into an apparent success -- which is exactly what happened to
  # alda three times (jobs bt15evs9066in8etvlt4, bt1m66qf9d9ch66i5ki5, bt1j5k32stle6gakhbk6): the
  # cell was killed at 11.5 GB on a 16 GB gt4.1, the runner saw "Exit status: 0", and the failure
  # surfaced later as an unexplained missing checkpoint with no error anywhere.]
  local measured_log="$output_dir/training.log"
  # [Claude 2026-09-08] Check the stall FIRST. A watchdog kill arrives as a signal, so without this
  # it would be reported as NATIVE_CELL_SIGNALLED and read like an OOM -- which is the diagnosis
  # that cost alda three jobs. A cell that stopped talking and a cell that was killed for using too
  # much memory need different fixes and must not share a marker.
  if grep -q "NATIVE_CELL_STALLED" "$measured_log" 2>/dev/null; then
    echo "=== NATIVE_CELL_FAILED_STALLED $(grep -m1 'NATIVE_CELL_STALLED' "$measured_log") ===" >&2
    return 1
  fi
  if grep -q "Command terminated by signal" "$measured_log" 2>/dev/null; then
    local signal_line
    signal_line="$(grep -m1 "Command terminated by signal" "$measured_log" || true)"
    echo "=== NATIVE_CELL_SIGNALLED $signal_line ===" >&2
    echo '    time -v also prints an Exit status line after this; it does not mean anything here.' >&2
    return 1
  fi
  if [[ "$training_status" -ne 0 ]]; then return "$training_status"; fi
  if [[ "$tee_status" -ne 0 ]]; then return "$tee_status"; fi
  if [[ "$sampler_status" -ne 0 ]]; then return "$sampler_status"; fi
  return 0
}

verify_result_archive() {
  python3 - "$1" <<'PY'
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    names = {member.name.lstrip("./") for member in archive.getmembers()}
if "run_manifest.json" not in names:
    raise SystemExit("result archive is missing run_manifest.json")
PY
}

verify_final_evaluation() {
  local frames="$1"
  local training_log="$2"
  local marker="NATIVE_FINAL_EVALUATION_COMPLETED frame=$frames"
  # [Codex 2026-09-01 16:24 MSK: fail closed unless the measured trainer completed its exact endpoint evaluation]
  if ! grep -Fqx "$marker" "$training_log"; then
    echo "final evaluation marker missing: $marker" >&2
    return 1
  fi
}

# [Claude 2026-09-02 01:50 MSK: a CELL is one (baseline, seed) run. Naming it that, rather than
# "baseline", is what lets the same runner serve three different jobs: a serial multi-baseline
# calibration, a concurrency-packing experiment (the same baseline at several seeds at once), and
# a production pack. Each cell owns a deterministic hydra run directory, so its snapshot and its
# curve are unambiguously its own -- `find -name snapshot.pt -print -quit` would have returned
# whichever cell wrote first.]
cell_baseline() { printf '%s' "${1%%:*}"; }
cell_seed() { local spec="$1"; if [[ "$spec" == *:* ]]; then printf '%s' "${spec#*:}"; else printf '%s' "${DEFAULT_SEED:-1}"; fi; }
cell_id() { printf '%s-s%s' "$(cell_baseline "$1")" "$(cell_seed "$1")"; }

# [Claude 2026-09-02 03:20 MSK: the overlay asset is not SVEA-only, and the answer is per baseline
# rather than per family: algos/sgqn.py:194 calls utils.random_overlay on every update and drq does
# not; dmc_gb's soda calls augmentations.random_overlay and rad does not. families.json holds the
# list; a job whose cells include any of them must carry the declared private input or it would
# either fail at its first update or take the historical fallback this project rejects.]
FAMILY_TOOL="${FAMILY_TOOL:-datasphere/native/family.py}"
cells_need_places365() { python3 "$FAMILY_TOOL" needs-places365 --cells "$1"; }

run_one_cell() {
  local spec="$1" task="$2" frames="$3" eval_every="$4" eval_episodes="$5"
  local out_root="$6" work_root="$7"
  local baseline seed identifier family
  # [Claude 2026-09-02 11:40 MSK: the checkpoint cadence is a job-level variable that the
  # --run-cells entry point does not set, so resolve it here against this cell's own budget.]
  local cell_save_every="${save_every:-$frames}"
  baseline="$(cell_baseline "$spec")"
  seed="$(cell_seed "$spec")"
  identifier="$(cell_id "$spec")"
  # [Claude 2026-09-02 03:20 MSK: the family decides both the argv shape and the artifact set.
  # NATIVE_FAMILY exists so a test can drive this path with a stub launcher and an invented
  # baseline name that no descriptor claims.]
  family="${NATIVE_FAMILY:-$(python3 "$FAMILY_TOOL" family-of --baseline "$baseline")}"
  if [[ -z "$family" ]]; then
    echo "no family declares baseline: $baseline" >&2
    return 1
  fi
  for blocked in ${BLOCKED_FAMILIES:-}; do
    if [[ "$blocked" == "$family" ]]; then
      echo "family $family failed its import gate; not attempting $identifier" >&2
      return 1
    fi
  done
  local cell_out="$out_root/cells/$identifier"
  local run_dir="$work_root/runs/$identifier"
  mkdir -p "$cell_out" "$run_dir"
  # [Claude 2026-09-03] RESUME_SNAPSHOT places a checkpoint where RL-ViGen's train.py will find it
  # (train.py:380 auto-resumes from `snapshot.pt` in the run directory). It exists for one
  # experiment: the checkpoint-reproduction defect. A stamped checkpoint evaluates far below what
  # its own run logged, and every offline explanation has been excluded -- so the remaining
  # question is what the TRAINING LOOP reports when handed the same file. Returns at the level the
  # run had mean the policy is intact and the offline path differs; returns at the level the
  # offline grid sees mean the file does not carry the policy. It cannot be answered locally: the
  # snapshot's storages are CUDA and this laptop's torch has none.
  if [[ -n "${RESUME_SNAPSHOT:-}" && -f "${RESUME_SNAPSHOT}" ]]; then
    cp "$RESUME_SNAPSHOT" "$run_dir/snapshot.pt"
    echo "=== NATIVE_RESUME_FROM $(basename "$RESUME_SNAPSHOT") -> $run_dir/snapshot.pt ==="
  fi
  # [Claude 2026-09-03] The offline W&B shim writes here. `ctrl` calls wandb.init/log
  # unconditionally (train_ppo.py:111) and has no flag to turn it off; putting the sink in the run
  # directory turns those calls into a returned artifact instead of a lost one.
  export RLGEN_WANDB_JSONL="$run_dir/wandb_offline.jsonl"
  local argv=()
  local item
  while IFS= read -r item; do
    argv+=("$item")
  done < <(python3 "$FAMILY_TOOL" command --family "$family" --baseline "$baseline" --task "$task" \
    --frames "$frames" --eval-every "$eval_every" --eval-episodes "$eval_episodes" \
    --save-every "$cell_save_every" --seed "$seed" --run-dir "$run_dir")
  if [[ "${#argv[@]}" -eq 0 ]]; then
    echo "family command resolution failed for $identifier" >&2
    return 1
  fi
  if [[ -n "${NATIVE_LAUNCHER:-}" ]]; then
    argv[0]="$NATIVE_LAUNCHER"
  fi

  local time_wrapper=()
  if [[ -z "${NATIVE_NO_TIME_WRAPPER:-}" ]]; then
    time_wrapper=(/usr/bin/time -v)
  fi
  # [Claude 2026-09-02 02:20 MSK: cap each cell, not only the job. With several cells per job a
  # single job-level `timeout` means one slow or hung cell destroys the evidence of every cell
  # that already finished, because the result archive is written last. Inside `time -v`, so the
  # resource high-water marks are still reported for a cell that is cut off.]
  local cell_timeout=()
  if [[ -n "${CELL_TIMEOUT_SECONDS:-}" ]]; then
    cell_timeout=(timeout --foreground "${CELL_TIMEOUT_SECONDS}s")
  fi
  # [Claude 2026-09-02 01:05 MSK: NATIVE_EXTRA_OVERRIDES is a deliberate escape hatch for local
  # end-to-end rehearsal (shortening num_seed_frames so a two-thousand-frame run still writes a
  # curve). It is recorded verbatim in the manifest, so any run that used it is identifiable and
  # never silently pooled with one that did not.]
  local extra_overrides=()
  if [[ -n "${NATIVE_EXTRA_OVERRIDES:-}" ]]; then
    local previous_ifs_overrides="$IFS"
    IFS=' '
    extra_overrides=(${NATIVE_EXTRA_OVERRIDES})
    IFS="$previous_ifs_overrides"
  fi
  # [Claude 2026-09-02 08:45 MSK: a family may need environment a flag cannot carry; it is declared
  # in families.json and applied here rather than exported globally, so one cell cannot leak its
  # results directory into the next.]
  local cell_environment=()
  while IFS= read -r item; do
    cell_environment+=("$item")
  done < <(python3 "$FAMILY_TOOL" environment --family "$family" --baseline "$baseline" --task "$task" \
    --frames "$frames" --eval-every "$eval_every" --eval-episodes "$eval_episodes" \
    --save-every "$cell_save_every" --seed "$seed" --run-dir "$run_dir")
  # [Added 2026-09-05, Codex Q8.] THE EFFECTIVE CONFIGURATION, WRITTEN ONCE, BESIDE THE CELL.
  #
  # `notes/record-completeness-spec.md` asks for "the resolved values actually used, not the
  # template". A `host_profile` label in the manifest is necessary and not sufficient: reconstructing
  # what a cell ran by re-reading `families.json` later gives the WRONG answer the moment a
  # descriptor is edited, and descriptors were edited three times in this session alone.
  #
  # So the rendered argv is captured here, at the only moment it is known, and never derived again.
  #
  # [Claude 2026-09-07, Codex Q63.] The captured argv is the EXECUTED one, overrides included.
  # It used to be the pre-override argv, with NATIVE_EXTRA_OVERRIDES recorded separately -- so for
  # the PPG geometry probe the field named "effective config" said `--num_envs 8 --nstep 256` while
  # the process ran `--num_envs 8 --nstep 256 --num_envs 1 --nstep 2048`. The run was valid
  # (argparse takes the last value) and the artifact was not self-sufficient: reconstructing what
  # ran required knowing that appended duplicates win, which is a property of argparse rather than
  # of anything this file records. An artifact whose whole purpose is "what actually ran" must not
  # need a second document to be read correctly.
  #
  # Both are kept: `argv` is now the merged command line, and `extra_overrides` stays a separate
  # field so the PROVENANCE of a deviation -- that it came from the job config rather than from the
  # descriptor -- is still legible without diffing two argv lists.
  mkdir -p "$cell_out"
  printf '%s\0' "${argv[@]}" ${extra_overrides[@]+"${extra_overrides[@]}"} | env \
      _EC_CELL="$identifier" _EC_FAMILY="$family" _EC_BASELINE="$baseline" _EC_SEED="$seed" \
      _EC_TASK="$task" _EC_FRAMES="$frames" _EC_SAVE_EVERY="$cell_save_every" \
      _EC_EVAL_EVERY="$eval_every" _EC_EVAL_EPISODES="$eval_episodes" \
      _EC_CELL_ENVIRONMENT="$(printf '%s\n' ${cell_environment[@]+"${cell_environment[@]}"})" \
      python3 -c '
import json, os, sys
argv = [a for a in sys.stdin.buffer.read().decode("utf-8", "replace").split("\0") if a]
# [Claude 2026-09-07, external review 21 #11] This was a hand-maintained allow-list and it had
# fallen behind what the runner actually reads: NATIVE_ISOLATE_ONLINE_EVAL was missing, and it
# changes training RNG semantics for the continuous on-policy ports; so were every
# ENDPOINT_EVAL_*/CURVE_EVAL_*/OFFLINE_EVAL_* axis, the snapshot controls, and the new
# NATIVE_ONLINE_EVAL_DISABLED_SPELLING. An "effective config" that omits a learning- or
# evaluation-affecting variable is not effective, and the omission is invisible in the artifact.
# Captured by PREFIX now, so a variable added to the runner is captured the day it is added rather
# than the day someone remembers this list. Prefixes, not os.environ wholesale: the container also
# holds credentials and unrelated host variables that must not be stamped into a record.
prefixes = ("NATIVE_", "ENDPOINT_EVAL", "CURVE_EVAL", "OFFLINE_EVAL", "RLGEN_", "RLVIGEN_",
            "EVAL_", "SAVE_EVERY", "CELLS", "FRAMES", "TASK", "SEED", "CUDA_", "CUBLAS_",
            "MUJOCO_GL", "XLA_", "JAX_", "PYTHON", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
# Never stamped, whatever prefix they match: paths that leak the host layout, and anything that
# could carry a secret.
redact = ("NATIVE_EXTRA_OVERRIDES_FILE",)
keep = sorted(k for k in os.environ
              if k.startswith(prefixes) and k not in redact
              and not k.startswith("_EC_")
              and "TOKEN" not in k and "KEY" not in k and "SECRET" not in k
              and "PASSWORD" not in k and "CREDENTIAL" not in k)
json.dump({
    "cell": os.environ.get("_EC_CELL"),
    "family": os.environ.get("_EC_FAMILY"),
    "baseline": os.environ.get("_EC_BASELINE"),
    "seed": os.environ.get("_EC_SEED"),
    "task": os.environ.get("_EC_TASK"),
    "frames_requested": os.environ.get("_EC_FRAMES"),
    "save_every": os.environ.get("_EC_SAVE_EVERY"),
    "eval_every": os.environ.get("_EC_EVAL_EVERY"),
    "eval_episodes": os.environ.get("_EC_EVAL_EPISODES"),
    # Same default as the record path and as family.host_profile(), which is the authority. These
    # disagreed: this site stamped null where the record stamped "datasphere", so the two artifacts
    # describing a SINGLE run host contradicted each other in the default case -- which is every run
    # made so far. A reader could not tell a real profile change from an artifact of two defaults.
    "host_profile": os.environ.get("NATIVE_HOST_PROFILE", "datasphere"),
    # The merged, executed command line (Codex Q63). `extra_overrides` below says which tail of
    # it came from NATIVE_EXTRA_OVERRIDES rather than from the descriptor.
    "argv": argv,
    "extra_overrides": [a for a in os.environ.get("NATIVE_EXTRA_OVERRIDES", "").split() if a],
    "runner_environment": {k: os.environ[k] for k in keep if k in os.environ},
    # The family-specific environment `family.py environment` resolved for THIS cell -- e.g. ALDA
    # runs with ALDA_RESULTS pointing at its own directory. Written after that resolution, not
    # before: an "effective" config that omits the environment the process actually ran under is
    # not effective, and this artifact was first placed where it could not see it (Codex Q10).
    "cell_environment": [line for line in
                         os.environ.get("_EC_CELL_ENVIRONMENT", "").split("\n") if line],
}, sys.stdout, indent=2, sort_keys=True)
' > "$cell_out/effective_config.json" || {
    echo "=== NATIVE_EFFECTIVE_CONFIG_FAILED $identifier ===" >&2
    return 1
  }
  echo "=== NATIVE_EFFECTIVE_CONFIG $identifier argv=${#argv[@]} env=${#cell_environment[@]} profile=${NATIVE_HOST_PROFILE:-unset} ==="
  run_measured "$cell_out" ${time_wrapper[@]+"${time_wrapper[@]}"} ${cell_timeout[@]+"${cell_timeout[@]}"} \
    env ${cell_environment[@]+"${cell_environment[@]}"} \
    bash "${argv[@]}" ${extra_overrides[@]+"${extra_overrides[@]}"} || return 1
  # [Claude 2026-09-02 06:05 MSK: the endpoint a family reaches is not always the endpoint asked
  # for. IDAAC floors a budget to a whole rollout, PPG overshoots to the next segment. The rule is
  # computed exactly from the family's own quantum, so a run that lands anywhere else is a failure
  # rather than a rounding, and the number the marker carries is the executed one.]
  local expected_endpoint
  expected_endpoint="$(python3 "$FAMILY_TOOL" expected-endpoint --family "$family" --frames "$frames")" || return 1
  verify_final_evaluation "$expected_endpoint" "$cell_out/training.log" || return 1
  python3 "$FAMILY_TOOL" retain --family "$family" --baseline "$baseline" --task "$task" \
    --frames "$frames" --save-every "$cell_save_every" --seed "$seed" --run-dir "$run_dir" \
    --output "$cell_out" || return 1
  # [Codex 2026-09-05.] Check the retained terminal checkpoint before paying for any intermediate
  # or endpoint grid. A non-finite checkpoint is already a failed cell; evaluating it first only
  # burns GPU time and can create misleading partial records.
  "${CELL_PYTHON:-python3}" "$FAMILY_TOOL" check-finite --family "$family" --root "$work_root" \
    --checkpoint "$cell_out/snapshot.pt" || return 1
  if [[ "${CURVE_EVAL:-0}" == "1" ]]; then
    # A PRODUCTION trajectory must be complete or the cell fails: a curve with holes cannot be
    # distinguished later from one that was never asked for, and the checkpoints have already been
    # retained above, so failing here costs the evaluation and keeps the expensive artifact.
    # CURVE_EVAL_STRICT defaults to whether this is a production cell (production_env sets
    # ENDPOINT_EVAL=1), so a cheap exploratory probe keeps its non-fatal behaviour and production
    # cannot mistake a partial curve for a complete one.
    run_curve_eval_with_policy "$cell_out" "$family" "$baseline" "$seed" "$cell_save_every" || return 1
  fi
  if [[ "${ENDPOINT_EVAL:-0}" == "1" ]]; then
    run_endpoint_eval "$cell_out" "$family" "$baseline" "$seed" "$expected_endpoint" || return 1
  else
    # Loud, not silent: a training cell that produced no endpoint grid has produced no reportable
    # number, and that must be visible in the log rather than discovered during analysis.
    echo "=== NATIVE_NO_ENDPOINT_GRID $baseline (set ENDPOINT_EVAL=1 to evaluate the final checkpoint) ===" >&2
  fi
  return 0
}

# [Claude 2026-09-02 01:50 MSK: run every requested cell even after one fails, then fail the job.
# Aborting on the first failure would throw away the evidence the later cells would have produced
# at no extra bootstrap cost; hiding it would make the job falsely green. NATIVE_CONCURRENT=1
# starts every cell at once instead -- that is the packing experiment, and later the production
# shape, and it is deliberately all-or-nothing rather than a scheduler: one job is one pack.]
run_cell_list() {
  local cells="$1" task="$2" frames="$3" eval_every="$4" eval_episodes="$5"
  local out_root="$6" work_root="$7"
  local failed=""
  local spec
  local previous_ifs="$IFS"
  IFS=','
  local cell_list=($cells)
  IFS="$previous_ifs"
  # [Claude 2026-09-07] Per-cell GPU assignment. Packed cells had NO device differentiation: every
  # cell inherited the same visible devices and every framework here defaults to cuda:0, so two
  # cells packed on the two-GPU production host would both land on GPU 0 -- one card saturated at
  # double the memory, the other idle, and the packing buying nothing it was run for. Invisible on
  # DataSphere, whose tiers have one GPU, which is why it survived this long.
  #
  # NATIVE_CELL_DEVICES is a comma-separated list of device indices to round-robin across; unset
  # leaves the environment exactly as before, so no existing job changes behaviour.
  local devices=()
  if [[ -n "${NATIVE_CELL_DEVICES:-}" ]]; then
    local previous_ifs_devices="$IFS"
    IFS=','
    devices=(${NATIVE_CELL_DEVICES})
    IFS="$previous_ifs_devices"
  fi
  # [Claude 2026-09-08, A55 -- external review 27 sec.12] FAIL CLOSED on a multi-GPU host.
  #
  # With NATIVE_CONCURRENT=1 and no NATIVE_CELL_DEVICES, every cell launches unpinned, so each
  # CUDA process sees all GPUs and independently chooses cuda:0. The launch looks correct and the
  # collision only shows up as one device at double memory and the rest idle -- the packing buying
  # nothing it was run for.
  #
  # The refusal is scoped to where the danger is real. DataSphere tiers have ONE GPU, and packing
  # co_schedulable families onto it is the intended behaviour with nothing to assign; refusing
  # there would break the existing probe path for no gain. On a host with more than one GPU an
  # absent device map is a silent bug, so it stops.
  if [[ "${NATIVE_CONCURRENT:-}" == "1" && "${#cell_list[@]}" -gt 1 && "${#devices[@]}" -eq 0 ]]; then
    local visible_gpus
    visible_gpus="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || echo 0)"
    if [[ "$visible_gpus" -gt 1 ]]; then
      echo "REFUSING: NATIVE_CONCURRENT=1 with ${#cell_list[@]} cells and no NATIVE_CELL_DEVICES" >&2
      echo "  on a host with $visible_gpus GPUs. Every cell would see all of them and pick cuda:0," >&2
      echo "  so they would collide on one device while the others idle -- a launch that looks" >&2
      echo "  correct and wastes the packing it was run for." >&2
      echo "  Set NATIVE_CELL_DEVICES=0,1,... with one index per concurrent cell." >&2
      exit 3
    fi
  fi
  # Duplicate indices in an explicit list are always a mistake: the operator asked for packing and
  # named the same device twice.
  if [[ "${#devices[@]}" -gt 1 ]]; then
    local unique_devices
    unique_devices="$(printf '%s\n' "${devices[@]}" | sort -u | wc -l | tr -d ' ')"
    if [[ "$unique_devices" -ne "${#devices[@]}" ]]; then
      echo "REFUSING: NATIVE_CELL_DEVICES=${NATIVE_CELL_DEVICES} repeats a device index." >&2
      echo "  Round-robin over a list with duplicates puts two cells on one GPU silently." >&2
      exit 3
    fi
  fi
  local cell_index=0
  if [[ "${NATIVE_CONCURRENT:-}" == "1" ]]; then
    local pids=() specs=()
    for spec in "${cell_list[@]}"; do
      echo "=== NATIVE_CELL_BEGIN $(cell_id "$spec") ==="
      if [[ "${#devices[@]}" -gt 0 ]]; then
        local device="${devices[$(( cell_index % ${#devices[@]} ))]}"
        echo "=== NATIVE_CELL_DEVICE $(cell_id "$spec") CUDA_VISIBLE_DEVICES=$device ==="
        CUDA_VISIBLE_DEVICES="$device"           run_one_cell "$spec" "$task" "$frames" "$eval_every" "$eval_episodes" "$out_root" "$work_root" &
      else
        run_one_cell "$spec" "$task" "$frames" "$eval_every" "$eval_episodes" "$out_root" "$work_root" &
      fi
      pids+=("$!")
      specs+=("$spec")
      cell_index=$((cell_index + 1))
    done
    local index=0
    while [[ "$index" -lt "${#pids[@]}" ]]; do
      if wait "${pids[$index]}"; then
        echo "=== NATIVE_CELL_COMPLETED $(cell_id "${specs[$index]}") ==="
      else
        echo "=== NATIVE_CELL_FAILED $(cell_id "${specs[$index]}") ===" >&2
        failed="$failed $(cell_id "${specs[$index]}")"
      fi
      index=$((index + 1))
    done
  else
    for spec in "${cell_list[@]}"; do
      echo "=== NATIVE_CELL_BEGIN $(cell_id "$spec") ==="
      if run_one_cell "$spec" "$task" "$frames" "$eval_every" "$eval_episodes" "$out_root" "$work_root"; then
        echo "=== NATIVE_CELL_COMPLETED $(cell_id "$spec") ==="
      else
        echo "=== NATIVE_CELL_FAILED $(cell_id "$spec") ===" >&2
        failed="$failed $(cell_id "$spec")"
      fi
    done
  fi
  FAILED_CELLS="${failed# }"
  export FAILED_CELLS
  if [[ -n "$FAILED_CELLS" ]]; then
    echo "failed cells:$failed" >&2
    return 1
  fi
  return 0
}

if [[ "${1:-}" == "--test-command" ]]; then
  command="${2:?test command}"
  shift 2
  [[ "${1:-}" == "--output" ]]
  out="${2:?output directory}"
  mkdir -p "$out"
  bash -c "$command" 2>&1 | tee "$out/training.log"
  exit "${PIPESTATUS[0]}"
fi

if [[ "${1:-}" == "--measure-command" ]]; then
  command="${2:?test command}"
  shift 2
  [[ "${1:-}" == "--output" ]]
  out="${2:?output directory}"
  mkdir -p "$out"
  run_measured "$out" bash -c "$command"
  exit 0
fi

if [[ "${1:-}" == "--verify-result-archive" ]]; then
  archive="${2:?result archive}"
  verify_result_archive "$archive"
  exit 0
fi

if [[ "${1:-}" == "--verify-final-eval" ]]; then
  frames="${2:?requested frames}"
  shift 2
  [[ "${1:-}" == "--output" ]]
  out="${2:?output directory}"
  verify_final_evaluation "$frames" "$out/training.log"
  exit 0
fi

# [Claude 2026-09-02 00:45 MSK: expose the retention and multi-baseline paths so their failure
# branches are exercised by the local suite rather than only by a paid remote job]
if [[ "${1:-}" == "--cells-need-places365" ]]; then
  cells_need_places365 "${2:?cell list}"
  exit "$?"
fi

require_accelerator() {
  # [Claude 2026-09-07, external recommendation 22 item 9.] Fail closed on wrong runtime identity.
  #
  # The environment record below already DETECTS the accelerator -- torch.cuda for six families,
  # jax.devices() for ctrl -- but only to write it into a manifest. Detecting is not refusing. A
  # ctrl cell that falls back to JAX CPU runs perhaps fifty times slower and produces a
  # valid-looking result with an honest manifest saying it had no GPU, which is exactly the
  # "succeeds quietly" failure require_production_configuration exists to prevent for host
  # profiles. Recommendation 22 names this case specifically.
  #
  # Production scale only. A probe may legitimately run on CPU -- several diagnostic configs in
  # this directory do, deliberately -- and refusing there would break them for no benefit.
  local cells="$1"
  [[ "${FRAMES:-10000}" -ge 600000 ]] || return 0
  [[ "${NATIVE_ALLOW_CPU:-0}" == "1" ]] && {
    echo "=== NATIVE_ACCELERATOR_CHECK_SKIPPED NATIVE_ALLOW_CPU=1 ===" >&2
    return 0
  }
  local family
  family="$(python3 "$FAMILY_TOOL" family-of --baseline "${cells%%:*}" 2>/dev/null)" || family=""
  python3 - "$family" <<'ACCEL' || exit 3
import sys

family = sys.argv[1]
if family == "ctrl":
    try:
        import jax
    except Exception as error:                                   # noqa: BLE001
        print(f"REFUSING: ctrl needs JAX and it did not import: {error}", file=sys.stderr)
        raise SystemExit(1)
    devices = [d for d in jax.devices() if d.platform in ("gpu", "cuda", "rocm")]
    if not devices:
        print("REFUSING: ctrl resolved NO JAX GPU device -- this is the CPU fallback.",
              file=sys.stderr)
        print(f"  jax.devices() = {jax.devices()}", file=sys.stderr)
        print("  A CPU cell finishes, reports honestly that it had no GPU, and costs the",
              file=sys.stderr)
        print("  campaign a slot. Set NATIVE_ALLOW_CPU=1 only for a deliberate CPU probe.",
              file=sys.stderr)
        raise SystemExit(1)
    print(f"=== NATIVE_ACCELERATOR ctrl jax {devices[0]} ===")
else:
    try:
        import torch
    except Exception as error:                                   # noqa: BLE001
        print(f"REFUSING: {family or 'this family'} needs torch and it did not import: {error}",
              file=sys.stderr)
        raise SystemExit(1)
    if not torch.cuda.is_available():
        print(f"REFUSING: {family or 'this family'} resolved no CUDA device at production scale.",
              file=sys.stderr)
        print("  Set NATIVE_ALLOW_CPU=1 only for a deliberate CPU probe.", file=sys.stderr)
        raise SystemExit(1)
    print(f"=== NATIVE_ACCELERATOR {family} torch {torch.cuda.get_device_name(0)} ===")
ACCEL
}

require_production_configuration() {
  # A production-length run must NAME its host. `host_profile()` defaults to "datasphere" so that
  # every existing probe config keeps working -- but that same default is the silent failure the
  # whole migration document exists to prevent: DataSphere-shaped values (num_envs, procs, the
  # 300k replay cap) executing on a 16-core/113-GiB V100, producing valid-looking numbers of a
  # rescaled experiment, stamped with a profile that is honest and wrong. Too small on the big
  # machine SUCCEEDS QUIETLY; only too large fails loudly. So refuse the default at production
  # scale, where the cost of being wrong is the whole campaign.
  if [[ "${FRAMES:-10000}" -ge 600000 && "${NATIVE_HOST_PROFILE_EXPLICIT:-0}" != "1" ]]; then
    echo "REFUSING: FRAMES=${FRAMES} is production scale and NATIVE_HOST_PROFILE is unset." >&2
    echo "  Set it explicitly (v100 | datasphere). Inheriting the probe default here would run" >&2
    echo "  hardware-adapted values on hardware they were not chosen for, and succeed." >&2
    exit 3
  fi
  # Codex, mailbox Q18(c): a SEPARATE, pre-existing flag from the one above, and nothing enforced
  # it at production scale. `apply_production_settings` -- which applies families.json's cadence,
  # replay cap and preserve-snapshots settings -- returns immediately if NATIVE_PRODUCTION is unset.
  # Without this guard, a job with NATIVE_HOST_PROFILE correctly set but NATIVE_PRODUCTION forgotten
  # would train a full 600k+ run at PROBE-scale cadence/replay settings and complete looking
  # successful -- the same "too small on the big machine succeeds quietly" failure as above, for a
  # different knob.
  if [[ "${FRAMES:-10000}" -ge 600000 && -z "${NATIVE_PRODUCTION:-}" ]]; then
    echo "REFUSING: FRAMES=${FRAMES} is production scale and NATIVE_PRODUCTION is unset." >&2
    echo "  Without it, apply_production_settings silently applies NOTHING -- the run would train" >&2
    echo "  at probe-scale cadence and replay settings and complete looking successful." >&2
    exit 3
  fi
}

apply_production_settings() {
  [[ -n "${NATIVE_PRODUCTION:-}" ]] || return 0
  local prod_key prod_value current
  # A probe may intentionally override a resolved setting, but a production-scale job must not
  # silently become a different experiment because its YAML happened to export SAVE/EVAL knobs.
  # Strict mode is automatic at the 600k boundary; the explicit variable remains useful for a
  # smaller rehearsal that wants to exercise the same refusal path.
  local strict="${NATIVE_PRODUCTION_STRICT:-0}"
  if [[ "${FRAMES:-10000}" -ge 600000 ]]; then
    strict=1
  fi
  while IFS='=' read -r prod_key prod_value; do
    [[ -z "$prod_key" || "$prod_key" == \#* ]] && continue
    if [[ "$prod_key" == "NATIVE_PRODUCTION_UNAPPLIED" ]]; then
      echo "=== NATIVE_PRODUCTION_UNAPPLIED $prod_value ===" >&2
      continue
    fi
    current="${!prod_key:-}"
    if [[ -z "$current" ]]; then
      export "$prod_key=$prod_value"
      echo "=== NATIVE_PRODUCTION_SET $prod_key=$prod_value ==="
    elif [[ "$strict" == "1" && "$current" != "$prod_value" ]]; then
      echo "=== NATIVE_PRODUCTION_CONFLICT $prod_key=$current expected=$prod_value ===" >&2
      echo "    production settings are frozen at scale; remove the job-config override or set" >&2
      echo "    NATIVE_PRODUCTION_STRICT=0 only for a deliberately non-production rehearsal" >&2
      return 3
    else
      echo "=== NATIVE_PRODUCTION_KEPT $prod_key=${!prod_key} (job config overrides the default) ==="
    fi
  done < <(python3 "$FAMILY_TOOL" production-env --cells "$1")
}

if [[ "${1:-}" == "--run-cells" ]]; then
  shift
  [[ "${1:-}" == "--cells" ]]
  cells_arg="${2:?cell list}"
  shift 2
  [[ "${1:-}" == "--work" ]]
  work_arg="${2:?work directory}"
  shift 2
  [[ "${1:-}" == "--output" ]]
  out_arg="${2:?output directory}"
  mkdir -p "$work_arg" "$out_arg"
  export DEFAULT_SEED="${SEED:-1}"
  echo "=== NATIVE_HOST_PROFILE $(python3 "$FAMILY_TOOL" host-profile) ==="
  apply_production_settings "$cells_arg"
  require_production_configuration
  require_accelerator "$cells_arg"
  python3 "$FAMILY_TOOL" check-budget --cells "$cells_arg" --frames "${FRAMES:-10000}"
  normalize_eval_sentinel "$cells_arg"
  if [[ "${NATIVE_DISABLE_ONLINE_EVAL:-0}" == "1" && -z "${EVAL_EVERY_FRAMES:-}" ]]; then
    # Same fix as the production path below: a numeric sentinel evaluates at step 0 because
    # `step % cadence == 0` holds there for every cadence (external review 21, P0).
    #
    # The spelling is PER FAMILY and must be resolved, not defaulted. `null` is right for rlvigen
    # (Hydra parses it to None and utils.Every returns False) and WRONG for dmc_gb and alda, whose
    # cadence reaches argparse with `type=int` -- `--eval_freq null` would fail to parse before a
    # single frame ran. Those two disable through their guarded call sites instead, so the numeric
    # value is inert for them. Falling back to the sentinel rather than to `null` keeps the failure
    # mode "an extra step-0 evaluation in a diagnostic probe" instead of "the cell will not start".
    run_eval_every="${NATIVE_ONLINE_EVAL_DISABLED_SPELLING:-}"
    if [[ -z "$run_eval_every" ]]; then
      run_eval_every="$(python3 "$FAMILY_TOOL" production-env --cells "$cells_arg" 2>/dev/null \
        | sed -n 's/^NATIVE_ONLINE_EVAL_DISABLED_SPELLING=//p' | head -1)"
    fi
    [[ -n "$run_eval_every" ]] || run_eval_every=2147483647
  else
    run_eval_every="${EVAL_EVERY_FRAMES:-${FRAMES:-10000}}"
  fi
  run_cell_list "$cells_arg" "${TASK:-Door}" "${FRAMES:-10000}" \
    "$run_eval_every" "${EVAL_EPISODES:-2}" "$out_arg" "$work_arg"
  exit "$?"
fi

code="${1:?payload archive}"
result="${2:?result archive}"
require_production_configuration
asset_archive="${3:-}"
out="/tmp/native-out"
# [Claude 2026-09-08] THE UNCONTAINED GUARD, and this is the script that most needs it.
#
# run_probe.sh apt-gets eleven system packages and pip-installs torch and the whole CUDA stack. It
# is meant to run inside a fresh container started by run_on_production_host.sh, where that is
# free. Run directly on a host -- by someone reading the repo and trying the obvious thing, or by
# an agent that reasoned "this is containerised" without checking where it was about to execute --
# it installs into the HOST's python. On a machine shared with about twenty people, into theirs.
#
# A banner is a comment and protects a reader. This refuses.
_rc="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)/require_container.sh"
[[ -f "$_rc" ]] || _rc="datasphere/native/require_container.sh"
if [[ -f "$_rc" ]]; then
  . "$_rc"
else
  echo "WARNING: require_container.sh is absent, so the uncontained guard did NOT run." >&2
  echo "  It is a declared payload member (RUNNER_CONTRACT 16); a payload without it is stale." >&2
fi

work="/tmp/native-work"
mkdir -p "$out" "$work"
exec > >(tee -a "$out/job.log") 2>&1

payload_sha256="$(sha256sum "$code" | awk '{print $1}')"
asset_sha256=""
if [[ -n "$asset_archive" ]]; then
  asset_sha256="$(sha256sum "$asset_archive" | awk '{print $1}')"
fi
export PAYLOAD_SHA256="$payload_sha256" ASSET_SHA256="$asset_sha256"

export DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC
apt-get -qq update
apt-get -qq install -y python3 python3-pip git libglvnd0 libgl1 libegl1 libglew-dev libosmesa6 libglib2.0-0 libsm6 libxext6 libxrender1 time
# [Claude 2026-09-09] REGISTER THE NVIDIA EGL VENDOR, and refresh the loader cache.
#
# Two separate omissions by libnvidia-container 1.13.2 have to be repaired here, and neither
# announces itself:
#
#   1. No `10_nvidia.json`. libglvnd picks an EGL vendor by reading `egl_vendor.d/*.json`. The
#      toolkit normally mounts the driver copy; this one does not, so the directory holds only
#      `50_mesa.json` and EGL silently resolves to Mesa `llvmpipe` -- CPU rasterisation, which is
#      what killed the 2026-09-08 cell after a two-and-a-half hour bootstrap.
#   2. The loader cache predates the `libnvidia-gpucomp` bind mount the wrapper adds, so `ldconfig`
#      has to run before anything dlopens the NVIDIA vendor.
#
# `__EGL_VENDOR_LIBRARY_FILENAMES` is libglvnd's documented override: it loads exactly the listed
# files and enumerates nothing else. Preferred over deleting `50_mesa.json`, because deleting Mesa
# would make a broken NVIDIA path fail as "no vendor at all" instead of failing loudly as itself.
if [[ -e /dev/nvidiactl || -n "${NVIDIA_DRIVER_CAPABILITIES:-}" ]]; then
  mkdir -p /etc/glvnd/egl_vendor.d
  printf '%s\n' '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' \
    > /etc/glvnd/egl_vendor.d/10_nvidia.json
  export __EGL_VENDOR_LIBRARY_FILENAMES=/etc/glvnd/egl_vendor.d/10_nvidia.json
  ldconfig 2>/dev/null || true
  echo "=== NATIVE_EGL_VENDOR_REGISTERED /etc/glvnd/egl_vendor.d/10_nvidia.json ===" >&2
  if ldd /usr/lib/x86_64-linux-gnu/libnvidia-eglcore.so.* 2>/dev/null | grep -q "not found"; then
    echo "=== NATIVE_EGL_DEPENDENCY_MISSING ===" >&2
    ldd /usr/lib/x86_64-linux-gnu/libnvidia-eglcore.so.* 2>/dev/null | grep "not found" | sed 's/^/    /' >&2
    echo "    The NVIDIA EGL vendor cannot load. Rendering would fall back to software, and the" >&2
    echo "    renderer check below will refuse. If this names libnvidia-gpucomp, the host container" >&2
    echo "    toolkit is older than 1.13.5 and run_on_production_host.sh should have injected it." >&2
  fi
fi
python3 -V
tar --no-same-owner -xzf "$code" -C "$work"
cd "$work"
# [Claude 2026-09-02 01:50 MSK: CELLS is the general form -- "drqv2:1,drqv2:2" is a packing
# experiment, "drq,sgqn,curl" is a serial multi-baseline calibration at the job's SEED. BASELINES
# and BASELINE stay accepted so every already-submitted configuration still means what it meant.]
# [Claude 2026-09-03] Run the offline grid ON THE CONTAINER, against a checkpoint supplied as a
# job input, instead of training anything.
#
# Why this exists: local offline evaluation of a container-trained checkpoint under-measures by
# 12-14x. Same 60k snapshot, eval-easy, scene 0, twenty episodes -- RL-ViGen's own `_eval_regime`
# returns 41.66 in the container and 3.41 on the laptop, and my `eval_grid.py` returns 2.94 there,
# so the loop is exonerated and the machine is not. Every R7/C43 generalisation number this project
# has computed locally therefore has to be recomputed where the policy was trained.
#
# [Claude 2026-09-03] OFFLINE_EVAL_SEED and OFFLINE_EVAL_EPISODE_SEED are DIFFERENT AXES and were
# briefly the same variable, which is a defect worth naming because it is silent. `--seed` names the
# seed of the RUN being evaluated; `--episode-seed` seeds the EVALUATION -- and via [C69] the global
# numpy RNG it seeds is what places the door on every reset. Passing one value to both ties the
# evaluation's door placements to the training seed, so a three-seed production set would evaluate
# each seed's checkpoint on a DIFFERENT set of placements and the across-seed spread would mix the
# training-seed effect with an evaluation-seed effect that has nothing to do with the algorithm.
#
# The evaluation seed therefore defaults to a FIXED constant, shared by every baseline and every
# training seed, so that "same scene set, same seed set" holds across the twelve by construction
# rather than by remembering to pass a flag.
#
# Two candidate causes remain conflated -- CUDA versus CPU, and EGL versus GLFW rendering.
# [Claude 2026-09-04: evaluate the intermediate checkpoint grid WHERE IT WAS PRODUCED, and let only
# the records travel.
#
# C95 decides this on its own: a container-trained checkpoint CANNOT be validly evaluated on the
# laptop the archives come home to, because the renderer differs (EGL there, glfw here). So the
# intermediate grid is evaluated where it was produced or it is not evaluated at all, and what
# travels is records rather than weights.
#
# [CORRECTED 2026-09-04, same day: this block first argued from storage as well -- 35.5 GB of
# checkpoints against "roughly 30 GB free". The owner then cleared space and the real figure is
# **73.1 GB**, so the weights WOULD fit and that leg of the argument is withdrawn. The design does
# not change, because it never rested on the storage: weights that cannot be validly evaluated
# where they land are worth nothing however much room there is for them. Recorded rather than
# quietly deleted, because a conclusion propped up by a premise that turned out false should be
# re-derived in the open -- and the size still matters as a secondary fact, since 35.5 GB is half
# the free disk for data with no local use. `plan_production.checkpoint_storage_gb` computes it.]
#
# Off by default (CURVE_EVAL unset): a probe that only wants training must not start paying for a
# ten-scene grid per stamp. `CURVE_EVAL_DISCARD_WEIGHTS=1` additionally removes each intermediate
# after it has been evaluated, leaving the terminal `snapshot.pt` untouched -- that one is the
# checkpoint of record and is never deleted here.]
ppg_checkpoint_frame() {
  local cell_out="$1" stamp="$2" save_every="$3" actual
  # PPG's model<N>.jd is indexed by save order. LogSaveHelper logs the exact interaction count
  # beside every save, so prefer that authoritative value over reconstructing a requested cadence.
  actual="$(grep 'Saving to .*IC=' "$cell_out/training.log" 2>/dev/null \
    | grep -oE 'IC=[0-9]+' | cut -d= -f2 | sed -n "$((10#$stamp + 1))p" || true)"
  if [[ -n "$actual" ]]; then
    printf '%s\n' "$actual"
  else
    # [Claude 2026-09-09] REFUSE rather than reconstruct. This used to fall back to
    # `(stamp + 1) * save_every`, which is wrong in two independent ways, measured against a live
    # ppg cell on 2026-09-09:
    #
    #   actual IC=   0, 51200, 100352, 151552, 200704   (ppg saves on its rollout quantum, 25x2048)
    #   fallback     50000, 100000, 150000, 200000, 250000
    #
    # The cadence is wrong (51200, not the requested 50000) AND it is off by one save, because
    # `model000.jd` is written at IC=0. So every curve row would carry a frame wrong by up to 50k,
    # shifted systematically, and nothing would say so -- a checkpoint evaluated at one frame and
    # recorded at another is exactly the mislabelling `eval_grid.py --frame` exists to prevent.
    #
    # An unmapped checkpoint is skipped and named. A skipped checkpoint is visible in the record
    # count; a mislabelled one is not visible at all.
    echo "=== NATIVE_PPG_FRAME_UNMAPPABLE stamp=$stamp: no 'Saving to ... IC=' line for it in" \
         "$cell_out/training.log, so its frame is unknown. Skipping rather than reconstructing a" \
         "cadence that is measurably off by one save and by the rounding to the rollout quantum. ===" >&2
    printf '%s\n' ""
  fi
}

# [Added 2026-09-05, Codex Q7.] THE TERMINAL GRID A TRAINING JOB OWES.
#
# `run_curve_eval` visits `cells/*/checkpoints` and evaluates intermediate stamps at a deliberately
# SHALLOW depth. Nothing evaluated the cell's FINAL checkpoint, so a training job produced curve
# rows and no reportable endpoint -- the headline number had to come from a separate offline job,
# paying a second bootstrap and shipping a checkpoint out of the container that C95 says must be
# evaluated where it trained.
#
# Scope is separate from the curve's on purpose: the endpoint is the reported quantity (4 regimes x
# 10 scenes x 20 episodes by default) and an intermediate stamp is descriptive. Sharing one
# CURVE_EVAL_* scope would have forced a choice between a full grid at every stamp and a shallow
# endpoint, which is exactly the reconciliation Q7 asked for.
#
# Opt-in like CURVE_EVAL, because a probe that only wants training must not silently start paying
# for an 800-episode grid. When a training job finishes WITHOUT one, that is announced rather than
# passed over in silence -- an absent endpoint must not look like a completed one.
run_endpoint_eval() {
  local cell_out="$1" family="$2" baseline="$3" seed="$4" frame="$5"
  local snapshot="$cell_out/snapshot.pt"
  if [[ ! -s "$snapshot" ]]; then
    echo "=== NATIVE_ENDPOINT_EVAL_NO_CHECKPOINT $baseline ===" >&2
    return 1
  fi
  # [Claude 2026-09-07, DECISION-SHEET A25 addendum] The endpoint grid runs once per requested
  # POLICY MODE, the same shape `run_offline_eval` already uses for OFFLINE_EVAL_DEVICES.
  #
  # Why more than one pass can be worth its cost: the evaluation policy mode is the fleet's only
  # UNITS-class comparability split. Eight baselines report E[return | a = argmax pi] and four
  # report E[return | a ~ pi], because eval_grid.py deliberately reproduces each family's own
  # reporting path. Those are different estimands, and two of A25's three fixed cross-group pairs
  # straddle the split -- so a cross-group number built from native passes alone confounds the
  # mechanism with the action rule.
  #
  # `native` alone is the default and is what every existing record was produced under. Only the
  # sampling families are given a second `mode` pass by family.py -- three since ctrl was
  # corrected to `mode` (idaac, ppg, ibac_sni); asking the nine deterministic ones for one would
  # re-run an identical grid at full price.
  local endpoint_modes="${ENDPOINT_EVAL_POLICY_MODES:-native}"
  local rc=0 policy_mode out_suffix
  # [Claude 2026-09-07] dmc_gb's own render is 84x84; rad/soda need the raw 100x100 render to
  # crop from -- runnable/_launch/dmc_gb.sh exports this before TRAINING, but this function calls
  # eval_grid.py directly, in run_probe.sh's own shell, which never inherited it. Unset, the env
  # (robosuitevgb/utils.py) renders natively at 84, RAD's own random_crop degrades to the identity
  # by its `crop_max <= 0` guard, and soda hard-asserts `x.size(-1) == 100` and cannot run at all.
  # `verify_runtime_observation_geometry` is what caught this (v194, rad-s1: "expected ... 100x100,
  # observed (9, 84, 84)") -- it was failing correctly, on a real mismatch, not a false positive.
  local image_size_env=()
  [[ "$family" == "dmc_gb" ]] && image_size_env=(RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-100}")
  local previous_ifs_modes="$IFS"
  IFS=','
  local mode_list=($endpoint_modes)
  IFS="$previous_ifs_modes"
  for policy_mode in "${mode_list[@]}"; do
    # The native pass keeps the historical filename so nothing downstream has to learn a new one;
    # only an extra mode gets a suffix.
    out_suffix=""
    [[ "$policy_mode" == "native" ]] || out_suffix="_$policy_mode"
  local started
  started="$(date +%s)"
  echo "=== NATIVE_ENDPOINT_EVAL_BEGIN $baseline frame=$frame policy_mode=$policy_mode epoch=$started ==="
  set +e
  env ${image_size_env[@]+"${image_size_env[@]}"} python3 scripts/eval_grid.py \
    --family "$family" \
    --baseline "$baseline" \
    --task "${TASK:-Door}" \
    --seed "$seed" \
    --snapshot "$snapshot" \
    --frame "$frame" \
    --regimes "${ENDPOINT_EVAL_REGIMES:-train,eval-easy,eval-medium,eval-hard}" \
    --scenes "${ENDPOINT_EVAL_SCENES:-0,1,2,3,4,5,6,7,8,9}" \
    --episodes "${ENDPOINT_EVAL_EPISODES:-20}" \
    --episode-seed "${OFFLINE_EVAL_EPISODE_SEED:-20260903}" \
    --device "${ENDPOINT_EVAL_DEVICE:-cuda}" \
    --policy-mode "$policy_mode" \
    --eval-scope endpoint \
    --append \
    --out "$cell_out/offline_eval_endpoint${out_suffix}.jsonl" 2>&1 | tee -a "$cell_out/training.log"
  rc=${PIPESTATUS[0]}
    set -e
    echo "=== NATIVE_ENDPOINT_EVAL_SECONDS $(( $(date +%s) - started )) policy_mode=$policy_mode ==="
    if [[ "$rc" -ne 0 ]]; then
      echo "=== NATIVE_ENDPOINT_EVAL_FAILED $baseline policy_mode=$policy_mode rc=$rc ===" >&2
      return 1
    fi
    echo "=== NATIVE_ENDPOINT_EVAL_COMPLETED $baseline frame=$frame policy_mode=$policy_mode ==="
  done
  return 0
}

run_curve_eval() {
  local cell_out="$1" family="$2" baseline="$3" seed="$4" save_every="$5"
  local dir="$cell_out/checkpoints"
  [[ -d "$dir" ]] || { echo "=== NATIVE_CURVE_EVAL_NO_STAMPS $baseline ===" >&2; return 1; }
  # See run_endpoint_eval's identical comment: dmc_gb needs RLVIGEN_IMAGE_SIZE=100 for rad/soda's
  # crop to be real rather than an identity, and this call site never inherits the training
  # launcher's export either.
  local image_size_env=()
  [[ "$family" == "dmc_gb" ]] && image_size_env=(RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-100}")
  local failed=0
  local count=0 item base stamp frame
  for item in "$dir"/*; do
    [[ -s "$item" ]] || continue
    base="$(basename "$item")"
    # the stamp is the last integer in the filename. For six families that integer IS the frame;
    # ppg names by SAVE INDEX (model<N>.jd), so use its save log's exact interaction count.
    stamp="$(echo "$base" | grep -oE '[0-9]+' | tail -1 || true)"
    [[ -n "$stamp" ]] || { echo "=== NATIVE_CURVE_EVAL_UNSTAMPED $base ===" >&2; continue; }
    if [[ "$family" == "ppg" ]]; then
      frame="$(ppg_checkpoint_frame "$cell_out" "$stamp" "$save_every")"
      # ppg_checkpoint_frame returns empty when it cannot map a save index to an interaction count.
      # Evaluating anyway would attach a real measurement to a wrong frame, which is worse than not
      # measuring it: the row would be indistinguishable from a correct one.
      if [[ -z "$frame" ]]; then
        echo "=== NATIVE_CURVE_EVAL_SKIPPED $baseline file=$base (frame unmappable) ===" >&2
        continue
      fi
    else
      frame="$stamp"
    fi
    echo "=== NATIVE_CURVE_EVAL_BEGIN $baseline frame=$frame file=$base ==="
    set +e
    env ${image_size_env[@]+"${image_size_env[@]}"} python3 scripts/eval_grid.py \
      --snapshot "$item" \
      --family "$family" \
      --baseline "$baseline" \
      --seed "$seed" \
      --frame "$frame" \
      --regimes "${CURVE_EVAL_REGIMES:-train,eval-easy}" \
      --scenes "${CURVE_EVAL_SCENES:-0}" \
      --episodes "${CURVE_EVAL_EPISODES:-3}" \
      --episode-seed "${OFFLINE_EVAL_EPISODE_SEED:-20260903}" \
      --device "${CURVE_EVAL_DEVICE:-cuda}" \
      --eval-scope curve \
      --append \
      --out "$cell_out/offline_eval_curve.jsonl" 2>&1 | tee -a "$cell_out/training.log"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ "$rc" -ne 0 ]]; then
      echo "=== NATIVE_CURVE_EVAL_FAILED $baseline frame=$frame rc=$rc ===" >&2
      failed=$(( failed + 1 ))
    else
      count=$((count + 1))
      if [[ "${CURVE_EVAL_DISCARD_WEIGHTS:-0}" == "1" ]]; then
        rm -f "$item"
      fi
    fi
  done
  # [Corrected 2026-09-05, Codex Q10.] This used to log each failure and then return success, so a
  # trajectory could be silently PARTIAL while the cell and the job both went green -- an absent
  # stamp is indistinguishable from one that was never scheduled. The count is reported either way
  # and the caller decides how fatal it is.
  if [[ "$failed" -gt 0 ]]; then
    echo "=== NATIVE_CURVE_EVAL_PARTIAL $baseline stamps=$count failed=$failed ===" >&2
    return 1
  fi
  if [[ "$count" -eq 0 ]]; then
    echo "=== NATIVE_CURVE_EVAL_NO_STAMPS $baseline ===" >&2
    return 1
  fi
  echo "=== NATIVE_CURVE_EVAL_COMPLETED $baseline stamps=$count ==="
}

run_curve_eval_with_policy() {
  if run_curve_eval "$@"; then
    return 0
  fi
  if [[ "${CURVE_EVAL_STRICT:-${ENDPOINT_EVAL:-0}}" == "1" ]]; then
    echo "=== NATIVE_CURVE_EVAL_FATAL ${3:-unknown} (production trajectory is incomplete) ===" >&2
    return 1
  fi
  echo "=== NATIVE_CURVE_EVAL_TOLERATED ${3:-unknown} (exploratory probe; trajectory is partial) ===" >&2
  return 0
}

# OFFLINE_EVAL_DEVICES runs the same grid once per device inside ONE job, both under EGL: if both
# land near 41 the renderer is the cause, and if the CPU pass lands near 3 the device is.
run_offline_eval() {
  local output_dir="$1"
  : > "$output_dir/training.log"
  local snapshot="${OFFLINE_EVAL_SNAPSHOT:-}"
  if [[ ! -f "$snapshot" ]]; then
    echo "=== NATIVE_OFFLINE_EVAL_NO_SNAPSHOT ${snapshot:-<unset>} ===" >&2
    return 1
  fi
  local status=0
  local device policy_mode
  # See run_endpoint_eval's identical comment: dmc_gb (rad/soda) needs RLVIGEN_IMAGE_SIZE=100 here
  # too, for the same reason -- this is a bare eval_grid.py invocation, not the training launcher.
  local image_size_env=()
  [[ "${OFFLINE_EVAL_FAMILY:-rlvigen}" == "dmc_gb" ]] && \
    image_size_env=(RLVIGEN_IMAGE_SIZE="${RLVIGEN_IMAGE_SIZE:-100}")
  # [Claude 2026-09-07] The endpoint path gained ENDPOINT_EVAL_POLICY_MODES and this one did not,
  # which is its own inconsistency: `run_offline_eval` is the mechanism recommendation 22 item 6
  # relies on -- re-evaluate an existing checkpoint without retraining -- so it is exactly where a
  # forced-mode pass would be requested after the fact. Same shape as OFFLINE_EVAL_DEVICES: a
  # comma-separated list, one grid per entry, default unchanged.
  for policy_mode in $(echo "${OFFLINE_EVAL_POLICY_MODES:-native}" | tr ',' ' '); do
  for device in $(echo "${OFFLINE_EVAL_DEVICES:-${OFFLINE_EVAL_DEVICE:-cuda}}" | tr ',' ' '); do
    # [Added 2026-09-05.] Wall-clock markers around the eval phase. Throughput under the current
  # evaluator is an open question (notes/EVALUATOR-THROUGHPUT.md) and it could not be answered from
  # job duration, because that is dominated by a ~10-minute bootstrap that installs torch. Two
  # echoed epochs make s/episode a subtraction instead of an inference -- and inferring it from
  # total wall time is precisely how a "4x regression" got claimed and then withdrawn.
  local _eval_started
  _eval_started="$(date +%s)"
  echo "=== NATIVE_OFFLINE_EVAL_BEGIN device=$device checkpoint=$(basename "$snapshot") epoch=$_eval_started ==="
    set +e
    env ${image_size_env[@]+"${image_size_env[@]}"} python3 scripts/eval_grid.py \
      --snapshot "$snapshot" \
      --family "${OFFLINE_EVAL_FAMILY:-rlvigen}" \
      --baseline "${OFFLINE_EVAL_BASELINE:-drqv2}" \
      --seed "${OFFLINE_EVAL_SEED:-1}" \
      --frame "${OFFLINE_EVAL_FRAME:-0}" \
      --regimes "${OFFLINE_EVAL_REGIMES:-train,eval-easy}" \
      --scenes "${OFFLINE_EVAL_SCENES:-0}" \
      --episodes "${OFFLINE_EVAL_EPISODES:-20}" \
      --episode-seed "${OFFLINE_EVAL_EPISODE_SEED:-20260903}" \
      --device "$device" \
      --policy-mode "$policy_mode" \
      --eval-scope "${OFFLINE_EVAL_SCOPE:-endpoint}" \
      --out "$output_dir/offline_eval_$device$([[ "$policy_mode" == "native" ]] || printf '_%s' "$policy_mode").jsonl" 2>&1 | tee -a "$output_dir/training.log"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ "$rc" -eq 0 ]]; then
      echo "=== NATIVE_OFFLINE_EVAL_SECONDS $(( $(date +%s) - _eval_started )) ==="
      echo "=== NATIVE_OFFLINE_EVAL_COMPLETED device=$device ==="
    else
      echo "=== NATIVE_OFFLINE_EVAL_FAILED device=$device rc=$rc ===" >&2
      status=1
    fi
  done
  done
  return "$status"
}

# Offline-only jobs have no CELLS/BASelines argument, but their evaluator family still needs its
# per-family dependency install. Falling back to drqv2 here made ALDA's offline evaluator reach
# `from colorlog import ...` without ever installing colorlog; the training path was unaffected
# because normal jobs always set CELLS explicitly.
cells="${CELLS:-${BASELINES:-${BASELINE:-${OFFLINE_EVAL_FAMILY:-drqv2}}}}"
frames="${FRAMES:-10000}"
task="${TASK:-Door}"
# [Claude 2026-09-02 18:30 MSK: NATIVE_PRODUCTION applies the settings families.json records for
# this family -- the cap, the cadences, the preserve cadence -- instead of asking the job config to
# repeat them. Explicit environment still wins, so a job can deviate deliberately; what it can no
# longer do is deviate by omission. A declared setting with no lever prints
# NATIVE_PRODUCTION_UNAPPLIED rather than being silently dropped.]
apply_production_settings "$cells"
normalize_eval_sentinel "$cells"
if [[ "${NATIVE_DISABLE_ONLINE_EVAL:-0}" == "1" && -z "${EVAL_EVERY_FRAMES:-}" ]]; then
  # [Claude 2026-09-07, external review 21 P0] A very large positive cadence DOES NOT suppress
  # periodic evaluation: every one of these loops gates on `step % cadence == 0` and 0 % anything
  # is 0, so step 0 evaluated anyway -- for drqv2, svea, drq, sgqn, curl, rad, soda and alda --
  # while the manifest recorded online evaluation as disabled. That evaluation consumes the
  # process-global NumPy stream Door's placement draws from, so the eight baselines received
  # DIFFERENT training-placement perturbations, which is exactly what disabling it was meant to
  # prevent. The spelling is now the family's own: `null` where the loop has an upstream disable
  # path, and an explicit source guard where the cadence must stay an integer.
  # No default here, deliberately. A silent fallback to the sentinel would hand rlvigen the exact
  # value CORRECTIONS #99 exists to remove, and the run would look correct while evaluating at step
  # 0 again. Production refuses instead: family.py sets this whenever it sets
  # NATIVE_DISABLE_ONLINE_EVAL, so its absence means the two came apart and that is worth stopping
  # for. The diagnostic path falls back, because there the cost of guessing is one extra evaluation.
  if [[ -z "${NATIVE_ONLINE_EVAL_DISABLED_SPELLING:-}" ]]; then
    echo "REFUSING: NATIVE_DISABLE_ONLINE_EVAL=1 but NATIVE_ONLINE_EVAL_DISABLED_SPELLING is unset." >&2
    echo "  family.py sets both together; their disagreement means the descriptor lookup failed." >&2
    echo "  Guessing here reintroduces the step-0 evaluation of CORRECTIONS #99 silently." >&2
    exit 3
  fi
  eval_every="$NATIVE_ONLINE_EVAL_DISABLED_SPELLING"
else
  eval_every="${EVAL_EVERY_FRAMES:-$frames}"
fi
eval_episodes="${EVAL_EPISODES:-2}"
# [Claude 2026-09-02 11:35 MSK: the checkpoint cadence, separate from the evaluation cadence. It
# defaults to the whole budget -- save once, at the end -- and a production job sets it to keep the
# budget curve a long run writes anyway.]
# [Claude 2026-09-04: this read only SAVE_EVERY_FRAMES while `family.py` emitted, and all three
# checkpoint-cadence cfgs set, SAVE_EVERY. The name did not match, the runner fell back to the whole
# budget, and job bt1791fdh5uctgr1ckhk therefore launched --checkpoint_interval=10000 against a
# 10000-frame budget: one save, at the end, nothing for retention to keep -- and it reported
# SUCCESS. A probe whose only purpose is a cadence, that validates no cadence and passes, is worse
# than one that fails. Both names are accepted; the alias is announced so the drift stays visible.]
if [[ -n "${SAVE_EVERY:-}" && -n "${SAVE_EVERY_FRAMES:-}" && "$SAVE_EVERY" != "$SAVE_EVERY_FRAMES" ]]; then
  echo "NATIVE_KNOB_CONFLICT SAVE_EVERY=$SAVE_EVERY vs SAVE_EVERY_FRAMES=$SAVE_EVERY_FRAMES" >&2
  exit 3
fi
if [[ -z "${SAVE_EVERY_FRAMES:-}" && -n "${SAVE_EVERY:-}" ]]; then
  echo "NATIVE_KNOB_ALIAS SAVE_EVERY -> SAVE_EVERY_FRAMES ($SAVE_EVERY)" >&2
fi
save_every="${SAVE_EVERY_FRAMES:-${SAVE_EVERY:-$frames}}"
seed="${SEED:-1}"
export DEFAULT_SEED="$seed"
export NATIVE_CELLS="$cells"
export NATIVE_EVAL_EVERY_FRAMES="$eval_every"
export NATIVE_EVAL_EPISODES="$eval_episodes"
export NATIVE_SAVE_EVERY_FRAMES="$save_every"
# [Claude 2026-09-02 06:45 MSK: the runner and the payload are separate job inputs and can drift.
# Refuse a payload built for an older runner here, immediately after extraction, rather than
# after a full bootstrap.]
# An offline-only job gets its selected family from OFFLINE_EVAL_FAMILY rather than CELLS.  The
# payload allowlist is family-scoped, so archive integrity alone is not enough: a rlvigen-only
# archive is valid but cannot unpickle or evaluate an IDAAC checkpoint.  Resolve the actual family
# set before any pip/apt work and require that the archive declares all of it.
payload_families="$(python3 "$FAMILY_TOOL" families-of-cells --cells "$cells")"
payload_families="${payload_families//$'\n'/,}"
payload_families="${payload_families%,}"
# [Claude 2026-09-08] 13 -> 14 with contract.py::RUNNER_CONTRACT. These are TWO HOMES FOR ONE
# NUMBER and they must move together: bumping contract.py alone made every payload built
# afterwards unrunnable against this runner, and job bt1tceje08tpvq8cchhj died on exactly
# that -- "payload was built for runner contract 14 but this runner needs 13". The check
# worked; the number was maintained in one place and read in another. Same shape as
# SAVE_EVERY vs SAVE_EVERY_FRAMES and the curve_eval_episodes duplicate.
python3 datasphere/native/contract.py verify-payload --archive "$code" --require-runner-contract 19 \
  --require-families "$payload_families" \
  --require-evaluator-identity \
  --expect 'scripts/eval_grid.py:evaluator_revision=EVALUATOR_REVISION'
# [Claude 2026-09-02 19:05 MSK: as early as the payload allows -- after the contract check, which
# is what makes family.py trustworthy, and before the family dependency installs and the clone.
# A budget below a family's floor trains nothing and fails at retain(), which is otherwise
# discovered only after the whole bootstrap and a full evaluation have been billed.]
python3 "$FAMILY_TOOL" check-budget --cells "$cells" --frames "$frames"
# [Claude 2026-09-02 10:35 MSK: refuse a job whose families cannot share one python environment,
# before the bootstrap rather than after it.]
python3 "$FAMILY_TOOL" check-co-schedulable --cells "$cells"
# [Claude 2026-09-07, external review 21 #4] The production host had NO memory preflight. check_memory
# existed but only knew DataSphere tiers, was never called by this runner, and read the base
# descriptor -- so a ctrl cell would have been sized by its 16-environment peak while the v100
# profile restores 64 environments. DataSphere jobs are still checked before submission by
# scripts/audit_submission_configs.py; this is the equivalent for the host that has no submit step.
# [Claude 2026-09-08] Was `if [[ "${NATIVE_HOST_PROFILE:-}" == "v100" ]]`, which made the only
# memory preflight this runner has conditional on one literal string. The hole that leaves is
# exact: `NATIVE_HOST_PROFILE=datasphere FRAMES=600000` on the production host satisfies
# require_production_configuration -- the profile IS named explicitly, which is all that refusal
# checks -- and then skips check-memory, because the name is not "v100". A production cell then
# runs with no memory preflight of any kind, in precisely the configuration the refusal above
# calls "honest and wrong". family.py records what that costs: ctrl was certified for gt4.1 that
# way and SIGKILLed at 11.07 GiB RSS (bt1lhobnsq5lq4766np6) -- hours into the cell, because
# nothing had computed the peak for the geometry actually running.
#
# check-memory takes a TIER (its usable-RAM table) and reads the PROFILE from the environment for
# the descriptor. Two vocabularies, which is why one string could not drive both. So map profile
# to tier here, and at production scale REFUSE when no tier can be derived rather than silently
# skipping. The tier is not otherwise knowable from inside a container: it lives in the cfg yaml's
# `cloud-instance-type`, which only scripts/audit_submission_configs.py reads, at submit time.
case "${NATIVE_HOST_PROFILE:-datasphere}" in
  v100) memory_tier="v100" ;;
  *)    memory_tier="${NATIVE_MEMORY_TIER:-}" ;;
esac
if [[ -n "$memory_tier" ]]; then
  python3 "$FAMILY_TOOL" check-memory --cells "$cells" --tier "$memory_tier"
elif [[ "${FRAMES:-10000}" -ge 600000 ]]; then
  echo "REFUSING: FRAMES=${FRAMES} is production scale, NATIVE_HOST_PROFILE=${NATIVE_HOST_PROFILE:-datasphere}," >&2
  echo "  and no memory tier follows from it -- so check-memory would not run at all, and this cell" >&2
  echo "  would train with no memory preflight. That is how a ctrl cell got sized for the wrong" >&2
  echo "  geometry and was SIGKILLed hours in (family.py: bt1lhobnsq5lq4766np6, 11.07 GiB RSS)." >&2
  echo "  Set NATIVE_HOST_PROFILE=v100 on the production host, or NATIVE_MEMORY_TIER to the tier" >&2
  echo "  this job actually runs on (gt4.1 | gt4i.1 | v100)." >&2
  exit 3
else
  echo "note: NATIVE_HOST_PROFILE=${NATIVE_HOST_PROFILE:-datasphere} yields no memory tier, so" >&2
  echo "  check-memory did NOT run. Tolerated below production scale: DataSphere jobs are checked" >&2
  echo "  at submit time by scripts/audit_submission_configs.py, which this runner has no" >&2
  echo "  equivalent of. Set NATIVE_MEMORY_TIER to check here as well." >&2
fi
# [Claude 2026-09-08] PREBUILT ENVIRONMENT. When NATIVE_VENV names a venv mounted read-only, this
# cell uses it and does no `pip install` at all. Rationale and measurements:
# notes/production-host/19-environment-lifecycle-vs-run-lifecycle.md -- `apt` is 71s and `pip` is
# over two hours, so the environment and the run are different lifecycles and rebuilding the former
# per cell is the whole cost.
#
# EVERY MISMATCH IS FATAL. There is deliberately no fallback to `pip`: a fallback would restore the
# two-hour bootstrap silently, and the only symptom would be the bandwidth bill. Same rule as
# RUNNER_CONTRACT -- the value lives in two places, and drift stops the job rather than being
# absorbed by it.
NATIVE_VENV_DISCIPLINE="off: this cell builds its own environment with pip"
if [[ -n "${NATIVE_VENV:-}" ]]; then
  manifest="$NATIVE_VENV/ENVIRONMENT.json"
  if [[ ! -f "$manifest" ]]; then
    echo "=== NATIVE_VENV_UNUSABLE no ENVIRONMENT.json at $manifest ===" >&2
    echo "    NATIVE_VENV names a directory that is not a built environment. Refusing rather than" >&2
    echo "    falling back to pip, which would hide a broken mount behind two hours of download." >&2
    exit 3
  fi
  if [[ ! -x "$NATIVE_VENV/bin/python3" ]]; then
    echo "=== NATIVE_VENV_UNUSABLE no interpreter at $NATIVE_VENV/bin/python3 ===" >&2
    exit 3
  fi
  # The venv is keyed to a base image. Only the HOST knows which image it launched, so it tells us,
  # and we compare against what the build recorded. A venv built under a different image is wrong in
  # ways that do not announce themselves.
  venv_image="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("base_image",""))' "$manifest" 2>/dev/null)"
  if [[ -z "${NATIVE_IMAGE_DIGEST:-}" ]]; then
    echo "=== NATIVE_VENV_UNVERIFIABLE NATIVE_IMAGE_DIGEST was not forwarded ===" >&2
    echo "    The venv records the image it was built under; without the image this container is" >&2
    echo "    running, that record cannot be checked. Unverifiable is not the same as fine." >&2
    exit 3
  fi
  if [[ "$venv_image" != *"$NATIVE_IMAGE_DIGEST"* ]]; then
    echo "=== NATIVE_VENV_IMAGE_MISMATCH ===" >&2
    echo "    venv was built under: $venv_image" >&2
    echo "    this container runs:  $NATIVE_IMAGE_DIGEST" >&2
    echo "    Binary wheels are built against the image glibc and CUDA. Refusing." >&2
    exit 3
  fi
  # And the requirement set itself, recomputed here rather than trusted from the directory name.
  want_hash="$(python3 "$FAMILY_TOOL" filtered-requirements --cells "$cells" \
      --requirements requirements-native.txt 2>/dev/null | sort | sha256sum | cut -c1-8)"
  venv_hash="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("requirements_sha256_8",""))' "$manifest" 2>/dev/null)"
  if [[ "$want_hash" != "$venv_hash" ]]; then
    echo "=== NATIVE_VENV_REQUIREMENTS_MISMATCH ===" >&2
    echo "    this cell needs requirement set $want_hash; the venv holds $venv_hash." >&2
    echo "    $cells cannot run in this environment. Build the matching one with build-env.sh." >&2
    exit 3
  fi
  export VIRTUAL_ENV="$NATIVE_VENV"
  export PATH="$NATIVE_VENV/bin:$PATH"
  NATIVE_VENV_DISCIPLINE="on: prebuilt $venv_hash under image $NATIVE_IMAGE_DIGEST, pip is not run"
  echo "=== NATIVE_VENV_DISCIPLINE $NATIVE_VENV_DISCIPLINE ===" >&2
  python3 -c "import sys; print('    interpreter:', sys.executable)" >&2
fi
echo "NATIVE_VENV_DISCIPLINE $NATIVE_VENV_DISCIPLINE"

if [[ -z "${NATIVE_VENV:-}" ]]; then
python3 -m pip install --upgrade pip
# [Claude 2026-09-02 10:50 MSK: a family that cannot share a job may also need a base requirement
# left out. CTRL is a JAX baseline and never imports torch, and jax[cuda12]'s cudnn 9 and torch's
# pinned cudnn 8.9.2.26 have no common version -- so a CTRL job installs the base requirements with
# torch filtered out, and every other job installs them unchanged.]
python3 "$FAMILY_TOOL" filtered-requirements --cells "$cells" --requirements requirements-native.txt > /tmp/requirements-for-this-job.txt
# [Claude 2026-09-08] --no-cache-dir, measured rather than assumed. Installing this requirement
# set in the pinned image on cds2 leaves 5.8 GB in site-packages (nvidia 2.8G, torch 1.6G, triton
# 420M) AND 3.0 GB in /root/.cache/pip -- both in the container's writable layer, both on the same
# /dev/sda2 that check_disk measures, and the cache buys nothing here because the layer is
# discarded by `docker run --rm` the moment the cell ends. Dropping it removes 3.0 GB from the
# peak of every cell on a filesystem that is 99% full and shared.
# [Claude 2026-09-08] The flag is now conditional. Without a cache mount the reasoning above holds
# exactly and --no-cache-dir stays. With NATIVE_PIP_CACHE=1 the host has bind-mounted a persistent
# /root/.cache/pip, so the 3.0 GB does NOT land in the container layer -- it lands on the host, once,
# and every later cell resolves the torch CUDA stack from disk instead of re-pulling ~2.5 GB at the
# 162-835 kB/s this host actually gets. The two branches are printed, because a run that silently chose
# the slow one would be indistinguishable from a slow network.
PIP_CACHE_FLAGS=(--no-cache-dir)
NATIVE_PIP_CACHE_DISCIPLINE="off: --no-cache-dir, wheels re-downloaded every cell"
if [[ "${NATIVE_PIP_CACHE:-0}" == "1" ]]; then
  if mkdir -p /root/.cache/pip 2>/dev/null && [[ -w /root/.cache/pip ]]; then
    # [Claude 2026-09-09] `--cache-dir` EXPLICITLY, not merely the absence of `--no-cache-dir`.
    # pip in this image reports "pip cache commands can not function since cache is disabled", so
    # dropping the flag achieved nothing: two full installs ran with the mount in place and left the
    # host cache at 4.0K, while this very variable printed "wheels persist across cells". A feature
    # that reports success while doing nothing is the defect class this project exists to refuse,
    # and I shipped one. `pip cache dir --cache-dir /root/.cache/pip` returns the path, so an
    # explicit --cache-dir overrides whatever disabled it.
    PIP_CACHE_FLAGS=(--cache-dir /root/.cache/pip)
    NATIVE_PIP_CACHE_DISCIPLINE="on: --cache-dir /root/.cache/pip (host bind mount), wheels persist across cells"
  else
    NATIVE_PIP_CACHE_DISCIPLINE="REQUESTED but /root/.cache/pip is not writable; falling back to --no-cache-dir"
  fi
fi
echo "NATIVE_PIP_CACHE_DISCIPLINE $NATIVE_PIP_CACHE_DISCIPLINE"
python3 -m pip install ${PIP_CACHE_FLAGS[@]+"${PIP_CACHE_FLAGS[@]}"} -r /tmp/requirements-for-this-job.txt
# [Claude 2026-09-09] VERIFY the cache rather than claiming it, for the same reason the VRAM cap is
# verified: this feature has now announced success twice while doing nothing. First `--no-cache-dir`
# was merely omitted, which this image ignores; then `--cache-dir` was passed explicitly, which it
# ACCEPTS and does not honour. Measured on the production image: a real install with an explicit
# --cache-dir leaves the directory with **0 entries**. Debian patches pip's caching out, so
# `pip cache dir` reports "cache is disabled" with no PIP_NO_CACHE_DIR and no pip.conf in sight.
#
# A cache is therefore NOT ACHIEVABLE on this image, whatever flags are passed. The prebuilt
# environment (NATIVE_VENV) is the real remedy and removes pip from the cell entirely.
if [[ "${NATIVE_PIP_CACHE:-0}" == "1" ]]; then
  _cached="$(find /root/.cache/pip -type f 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${_cached:-0}" -gt 0 ]]; then
    echo "=== NATIVE_PIP_CACHE_EFFECTIVE ${_cached} file(s) cached; later cells will reuse them ===" >&2
  else
    echo "=== NATIVE_PIP_CACHE_INEFFECTIVE requested, mounted, and wrote nothing ===" >&2
    echo "    This image ships a pip whose cache is disabled and which ignores --cache-dir, so the" >&2
    echo "    wheels were re-downloaded and will be again next cell. Not fatal, and not fixable" >&2
    echo "    with flags. Use NATIVE_VENV (datasphere/native/build-env.sh) to remove pip instead." >&2
  fi
fi
fi   # end: skip the whole pip bootstrap when NATIVE_VENV supplied one
# [Claude 2026-09-02 20:05 MSK: EXCLUDING A PACKAGE BY NAME DOES NOT EXCLUDE ITS DEPENDANTS.
# ctrl declared excluded_base_requirements ["torch","torchvision"], and pip installed torch anyway
# -- as a dependency of captum and kornia, which stayed in the list. With our pin removed it took
# the newest, torch 2.14.0, and with it CUDA 13 runtime wheels onto a CUDA 12.2 driver. Job
# bt1amu1210ol8ofufa16 warned "The NVIDIA driver on your system is too old (found version 12020)"
# and then died with no traceback at all, 3,029 lines in.
#
# So the exclusion is now verified rather than trusted: if a family declares a package excluded and
# that package is importable afterwards, something pulled it in transitively and the job stops here
# -- before the bootstrap finishes, and with the reason named -- instead of crashing later inside a
# GPU call with nothing to read.]
for excluded_module in $(python3 "$FAMILY_TOOL" excluded-modules --cells "$cells" 2>/dev/null); do
  if python3 -c "import $excluded_module" 2>/dev/null; then
    echo "=== NATIVE_EXCLUDED_PACKAGE_PRESENT $excluded_module ===" >&2
    echo "    $cells declares it excluded, and it imported anyway -- a listed requirement depends" >&2
    echo "    on it. Add that dependant to excluded_base_requirements; excluding the package by" >&2
    echo "    name does not exclude whatever pulls it in." >&2
    python3 -c "import $excluded_module as _m; print('    installed at:', _m.__file__)" >&2 || true
    exit 1
  fi
done
# [Claude 2026-09-02 08:35 MSK: per-family dependencies, installed only for the families this job
# actually runs. PPG needs an MPI runtime and gym3; nothing else does, and putting them in the
# shared requirements would slow every bootstrap and make every job's resolved-package manifest
# claim a dependency that job never used.]
# [Claude 2026-09-02 09:55 MSK: a family whose dependency install fails is blocked, not fatal. CTRL
# brings a whole JAX-on-CUDA stack that nothing else needs; if it fails to resolve, that must not
# take ALDA, PPG and IBAC-SNI down with it in the same job.]
DEPENDENCY_BLOCKED=""
for dependency_family in $(python3 "$FAMILY_TOOL" families-of-cells --cells "$cells"); do
  family_apt="$(python3 "$FAMILY_TOOL" apt-packages --family "$dependency_family")"
  if [[ -n "$family_apt" ]]; then
    echo "=== NATIVE_FAMILY_APT $dependency_family: $family_apt ==="
    if ! apt-get -qq install -y $family_apt; then
      echo "=== NATIVE_FAMILY_APT_FAILED $dependency_family ===" >&2
      DEPENDENCY_BLOCKED="$DEPENDENCY_BLOCKED $dependency_family"
      continue
    fi
  fi
  family_pip="$(python3 "$FAMILY_TOOL" pip-requirements --family "$dependency_family")"
  if [[ -n "$family_pip" ]]; then
    echo "=== NATIVE_FAMILY_PIP $dependency_family: $family_pip ==="
    if ! python3 -m pip install $family_pip; then
      echo "=== NATIVE_FAMILY_PIP_FAILED $dependency_family ===" >&2
      DEPENDENCY_BLOCKED="$DEPENDENCY_BLOCKED $dependency_family"
    fi
  fi
done
export DEPENDENCY_BLOCKED="${DEPENDENCY_BLOCKED# }"
# [Claude 2026-09-02 18:05 MSK: this clone is the first network act of every billed job, and it is
# where alda and ctrl died -- the only two baselines still without a successful CUDA run. The pin
# is right and stays; what was missing is that a single transient here throws away a whole
# bootstrap, and for a production cell that bootstrap sits in front of 9 to 78 hours of training.
# Three attempts with backoff, and a failure that names itself so the next reader does not go
# looking in the family's own code the way the first two failures made us.
# This does NOT fix rate limiting, which is per-IP and shared by two concurrent jobs on the same
# egress; the real remedy is shipping the tree as a hash-checked input, scoped as task 18.]
RLVIGEN_COMMIT=90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec
clone_rlvigen() {
  local attempt delay=10
  # A retry has to clear a half-finished clone, and `rm -rf` earns its own guard rather than
  # relying on the caller having cd'd somewhere sensible: this only ever runs inside the job's
  # own extraction directory, and refuses if it is anywhere else. The --run-cells entry point
  # returns long before this line, so a local rehearsal cannot reach it either.
  if [[ "$PWD" != "$work" || -z "$work" || "$work" == "/" ]]; then
    echo "=== NATIVE_RLVIGEN_CLONE_REFUSED: cwd $PWD is not the job work dir ${work:-<unset>} ===" >&2
    return 1
  fi
  for attempt in 1 2 3; do
    rm -rf "$work/RL-ViGen-upstream"
    if git clone -q https://github.com/gemcollector/RL-ViGen.git RL-ViGen-upstream \
       && git -C RL-ViGen-upstream checkout -q "$RLVIGEN_COMMIT"; then
      echo "=== NATIVE_RLVIGEN_CLONED attempt=$attempt commit=$RLVIGEN_COMMIT ==="
      return 0
    fi
    echo "=== NATIVE_RLVIGEN_CLONE_RETRY attempt=$attempt sleep=${delay}s ===" >&2
    sleep "$delay"
    delay=$((delay * 3))
  done
  echo "=== NATIVE_RLVIGEN_CLONE_FAILED after 3 attempts: the job never reached any baseline's own code ===" >&2
  return 1
}
# [Claude 2026-09-02 19:00 MSK: prefer a shipped tree over the network. Jobs
# bt1nlcstc5kg3qtqro52 and bt1uk6ehfsfo6m49dsdn both died at the clone with `could not read
# Username for 'https://github.com'` after all three retries, while the same repository answered
# `git ls-remote` from the laptop at that moment and returned exactly this commit. The container's
# egress changed; upstream did not. apt and pip still work, which fits a policy that allows the
# platform's mirrors and not the general internet.
#
# RLVIGEN_ARCHIVE is a job input carrying a PRISTINE tree at $RLVIGEN_COMMIT -- pristine because
# the runner applies P1-P21 itself immediately below, and the vendored working copy has them
# applied already (15 modified files under `git status`). Shipping the working copy would patch a
# patched tree.
#
# The hash is checked, not trusted: an input silently swapped or truncated would otherwise show up
# as a patch anchor failing, several minutes later, with no hint of why.]
provide_rlvigen() {
  if [[ -n "${RLVIGEN_ARCHIVE:-}" && -f "${RLVIGEN_ARCHIVE}" ]]; then
    local expected actual
    expected="$(python3 -c "import json,sys; print(json.load(open('datasphere/native/rlvigen-source.json'))['sha256'])")"
    actual="$(sha256sum "$RLVIGEN_ARCHIVE" | awk '{print $1}')"
    if [[ "$expected" != "$actual" ]]; then
      echo "=== NATIVE_RLVIGEN_ARCHIVE_HASH_MISMATCH expected=$expected actual=$actual ===" >&2
      return 1
    fi
    tar --no-same-owner -xzf "$RLVIGEN_ARCHIVE" -C "$work"
    if [[ ! -d "$work/RL-ViGen-upstream" ]]; then
      echo "=== NATIVE_RLVIGEN_ARCHIVE_SHAPE: no RL-ViGen-upstream/ at the archive root ===" >&2
      return 1
    fi
    echo "=== NATIVE_RLVIGEN_FROM_INPUT commit=$RLVIGEN_COMMIT sha256=$actual ==="
    return 0
  fi
  echo "=== NATIVE_RLVIGEN_NO_INPUT: falling back to the network clone ===" >&2
  clone_rlvigen
}
provide_rlvigen
# [Claude 2026-09-08] Baked into the prebuilt environment when there is one. These write an
# ABSOLUTE path into site-packages, and that path -- /tmp/native-work/RL-ViGen-upstream/... -- is a
# bind mount whose container-side name is identical on every run, so the pointer baked at build time
# resolves to each cell's own tree. Against a read-only venv these would fail outright; run against
# a writable one they would be redundant. Either way the check below is what proves it worked.
if [[ -z "${NATIVE_VENV:-}" ]]; then
  python3 -m pip install --no-deps -e RL-ViGen-upstream/third_party/robosuite
  python3 -m pip install --no-deps -e RL-ViGen-upstream/envs/robosuiteVGB
fi
# Proven, not assumed, and in BOTH paths: a baked pointer aimed at a directory this cell did not
# populate is an ImportError inside a GPU call, which is the worst place to learn about a mount.
# [Claude 2026-09-09] The module names are `robosuite` and `robosuitevgb` -- LOWERCASE. The
# directory is `envs/robosuiteVGB` and pip reports `Successfully installed robosuitevgb-1.0.0`, and
# the first version of this check used the directory spelling. It therefore failed on a cell whose
# install had just succeeded, and killed a healthy run: a check that refuses a correct state is
# worse than no check, because it is trusted. The names here match what the codebase imports.
#
# Checked under the same PYTHONPATH the cell will run with, so this verifies the real condition
# rather than a stricter one that happens to hold for the pip path only.
for _mod in robosuite robosuitevgb; do
  if ! PYTHONPATH="$work/RL-ViGen-upstream:$work/RL-ViGen-upstream/envs/robosuiteVGB:$work/RL-ViGen-upstream/third_party/robosuite:${PYTHONPATH:-}" \
       python3 -c "import $_mod" 2>/dev/null; then
    echo "=== NATIVE_EDITABLE_IMPORT_FAILED $_mod ===" >&2
    echo "    NATIVE_VENV=${NATIVE_VENV:-<unset>}; the tree is expected at" >&2
    echo "    /tmp/native-work/RL-ViGen-upstream. If a prebuilt env is mounted, its baked pointer" >&2
    echo "    aims there and this cell did not populate it." >&2
    exit 3
  fi
done
python3 -m pip check
# [Codex 2026-09-01 10:51 MSK: preserve resolved versions so remote results remain reproducible despite transitive package resolution]
python3 - <<'PY' > "$out/resolved_packages.json"
import importlib.metadata
import json

print(json.dumps({dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions() if dist.metadata.get("Name")}, sort_keys=True))
PY
python3 setup/apply_patches.py
python3 setup/apply_patches.py --check
# The payload's runner contract and allowlist are not the evaluator identity. After the separately
# supplied pristine RL-ViGen tree has been patched, compare the exact family closure bytes before
# any Robosuite or family import. If the archive input is absent, the existing clone-at-commit path
# remains in force; the closure comparison still applies, but this gate does not claim an archive
# origin certificate.
if [[ -n "${RLVIGEN_ARCHIVE:-}" && -f "${RLVIGEN_ARCHIVE}" ]]; then
  python3 datasphere/native/contract.py verify-evaluator-binding \
    --archive "$code" --source "$work" --families "$payload_families" \
    --rlvigen-archive "$RLVIGEN_ARCHIVE"
else
  python3 datasphere/native/contract.py verify-evaluator-binding \
    --archive "$code" --source "$work" --families "$payload_families"
fi
# [Codex 2026-09-01 15:20 MSK: verify the source-hashed exceptional import closure before any wrapper import or timed calibration]
python3 datasphere/native/contract.py verify-robosuite-closure --source RL-ViGen-upstream --requirements requirements-native.txt --closure datasphere/native/robosuite-import-closure.json
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl WANDB_MODE=offline WANDB_DISABLED=true

# [Claude 2026-09-08] JAX PREALLOCATES 75% OF THE CARD BY DEFAULT. Nothing here had ever said
# otherwise, and on a shared GPU that is the single most antisocial thing this runner could do:
# `ctrl` is a JAX baseline, and on a 32,768 MiB V100 its first CUDA call would reserve ~24,576 MiB
# whether it needs it or not. Card 1 on cds2 has 17,268 MiB already held by another user's process,
# leaving 15,500 -- so that reservation cannot even succeed, and the failure mode is either our
# cell dying at once or, worse, taking everything left and starving the neighbour.
#
# `false` makes JAX allocate on demand like torch does. `MEM_FRACTION` then bounds what it may
# reach even so, as a fraction of TOTAL card memory: 0.25 of 32 GiB is 8 GiB, comfortably above
# any measured figure here (the largest in plan_production.ENVELOPE is sgqn at 7,142 MiB, and that
# is a torch family) and far below what would disturb a co-tenant.
#
# Set for every cell, not just the JAX ones: these variables are inert for torch families, and a
# guard that has to be remembered per family is a guard that will be missed.
# [Claude 2026-09-08, external audit finding A3] BOUND THE BLAS THREAD POOL.
#
# The audit found an asymmetry: `run_cell_list` FAILS CLOSED when packed cells would collide on one
# GPU (exit 3, added after external review 27 sec.12), and has nothing analogous for CPU threads.
# `run_on_production_host.sh` sets no `--cpus` deliberately, and OMP/MKL are forwarded only if the
# operator sets them -- so PyTorch and NumPy default their thread pools to the FULL host core
# count. On cds2 that is 16 threads per cell, and `NATIVE_CONCURRENT=1` multiplies it by the number
# of cells, on a box shared with about twenty people.
#
# The number is chosen from measurement, not caution. `measure_vram_bounds.py` over the seedvar
# archives puts drqv2 at 1.68-1.69 CPU cores and families.json puts idaac at 1.35, both reproducible
# across seeds -- so a pool of 4 is more than twice the observed need and cannot slow us, while
# cutting the thread count fourfold. Thread pool size is not CPU utilisation: 16 threads doing 1.7
# cores of work still contend for cache and scheduler.
#
# Overridable, and NOT applied when the caller has already decided.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-$OMP_NUM_THREADS}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-$OMP_NUM_THREADS}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-$OMP_NUM_THREADS}"
echo "=== NATIVE_THREAD_DISCIPLINE omp=$OMP_NUM_THREADS mkl=$MKL_NUM_THREADS openblas=$OPENBLAS_NUM_THREADS (measured need: idaac 1.35, drqv2 1.68 cores) ===" >&2

export XLA_PYTHON_CLIENT_PREALLOCATE="${XLA_PYTHON_CLIENT_PREALLOCATE:-false}"
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.25}"
export XLA_PYTHON_CLIENT_ALLOCATOR="${XLA_PYTHON_CLIENT_ALLOCATOR:-platform}"
echo "=== NATIVE_GPU_MEMORY_DISCIPLINE preallocate=$XLA_PYTHON_CLIENT_PREALLOCATE mem_fraction=$XLA_PYTHON_CLIENT_MEM_FRACTION allocator=$XLA_PYTHON_CLIENT_ALLOCATOR ===" >&2

# [Claude 2026-09-08] The torch half of the same discipline. XLA's fraction is an environment
# variable; torch has no equivalent, so the cap has to be applied IN-PROCESS -- and installing it
# as `sitecustomize` means it runs at interpreter start, before any framework import, without
# editing seven launchers that would each be a place to forget it.
#
# Why a cap and not a headroom check. A caching allocator's reservation is a FLOOR on future usage:
# it never shrinks, and it grows whenever a high-water mark is exceeded. On a shared card the
# process that asks the driver SECOND is the one that fails -- so if we take the free memory and a
# neighbour's allocator then wants more, THEIR process raises the OOM and ours never notices. A
# headroom ratio is computed from what they hold now and cannot protect against that; a cap bounds
# what we can ever take, whatever we later want.
#
# Unset by default: a cap that is wrong is its own failure, so it is named per run rather than
# guessed here. `notes/production-host/17-first-real-cell-plan.md` sets one for the first cell.
if [[ -n "${NATIVE_VRAM_CAP_MIB:-}" ]]; then
  vram_cap_dir="$work/.vram-cap"
  mkdir -p "$vram_cap_dir"
  cp datasphere/native/vram_cap.py "$vram_cap_dir/sitecustomize.py"
  export PYTHONPATH="$vram_cap_dir${PYTHONPATH:+:$PYTHONPATH}"
  echo "=== NATIVE_VRAM_CAP_REQUESTED ${NATIVE_VRAM_CAP_MIB} MiB via sitecustomize at $vram_cap_dir ===" >&2
fi
# [Claude 2026-09-09] `${PYTHONPATH:+:$PYTHONPATH}` -- KEEP what is already there. Without it this
# line silently discarded the VRAM cap installed ~5 lines above, and the cap has therefore never
# taken effect on any run. Caught by the first PACKED cell: two processes on card 0 at 2019 MiB and
# 8207 MiB against a declared 2048 MiB cap. The 2019 was not enforcement -- it is what idaac happens
# to use -- which is exactly why this survived: the cap appeared to work on the one family whose
# natural footprint sits near the cap, and every log line said NATIVE_VRAM_CAP_REQUESTED.
#
# A safety mechanism that has never once functioned, while reporting that it had. Nothing overwrites
# PYTHONPATH after this point; anything added later must append the same way.
# [Claude 2026-09-09] The inherited PYTHONPATH goes FIRST, not last. Appending it was not enough:
# `runnable/_shim` ships its own `sitecustomize.py` (the Mac MPS shim) and Python imports the FIRST
# one it finds, so the shim won and the VRAM cap still never loaded -- caught by the cap
# verification below refusing a production cell after eight minutes rather than after twelve hours.
# vram_cap.py chains to whichever sitecustomize it displaces, so putting the cap first costs the
# shim nothing.
# [Claude 2026-09-09] `third_party/robosuite` added. `envs/robosuiteVGB` was already here, which is
# why `import robosuitevgb` worked from the path alone, but `robosuite` itself lived only in the
# editable install -- so a cell running against a READ-ONLY prebuilt environment (NATIVE_VENV) had
# no way to import it: the venv cannot be written to, and build-env.sh cannot bake the pointer
# because the payload carries no RL-ViGen tree (it is cloned at run time). With both package roots
# on PYTHONPATH the editable installs become an optimisation rather than a requirement, and the
# prebuilt-environment path -- which removes pip from the cell entirely -- becomes usable.
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$work/RL-ViGen-upstream:$work/RL-ViGen-upstream/algos:$work/RL-ViGen-upstream/envs/robosuiteVGB:$work/RL-ViGen-upstream/third_party/robosuite:$work/runnable/_shim"

# [Claude 2026-09-09] VERIFY the cap rather than announcing it. `NATIVE_VRAM_CAP_REQUESTED` was
# printed on every run for a day while the cap was silently discarded by the PYTHONPATH assignment
# above, and the only reason anyone noticed is that a packed cell put an 8207 MiB process next to a
# 2048 MiB declaration. "Requested" and "in force" are different claims and the log said the wrong
# one, so this checks that the module the cap lives in is actually importable by the interpreter the
# trainer will use -- after every PYTHONPATH assignment, which is where it went wrong.
if [[ -n "${NATIVE_VRAM_CAP_MIB:-}" ]]; then
  if python3 -c "import sitecustomize, os, sys; sys.exit(0 if 'vram' in (getattr(sitecustomize,'__file__','') or '') or hasattr(sitecustomize,'_rlvigen_vram_cap') else 1)" 2>/dev/null; then
    echo "=== NATIVE_VRAM_CAP_IN_FORCE ${NATIVE_VRAM_CAP_MIB} MiB, sitecustomize resolves ===" >&2
  else
    echo "=== NATIVE_VRAM_CAP_NOT_IN_FORCE ===" >&2
    echo "    NATIVE_VRAM_CAP_MIB=${NATIVE_VRAM_CAP_MIB} was requested, but the cap module is NOT" >&2
    echo "    importable, so nothing bounds this process on a shared card. PYTHONPATH=$PYTHONPATH" >&2
    echo "    Refusing: an unenforced cap is worse than a declared absence, because it is quoted." >&2
    exit 3
  fi
fi
# [Codex 2026-09-01 10:31 MSK: fail before timed calibration when native training imports are incomplete]
# [Claude 2026-09-02 13:20 MSK: this gate imports RL-ViGen's OWN train.py, which imports
# torchvision. A family that runs without torch -- CTRL, which is JAX and reaches the robosuite
# environment through robosuitevgb rather than through RL-ViGen's trainer -- would fail here on a
# module it was never going to use. Job bt1m4tjcmldq0qmb2ts9 died exactly there. Such a job is
# covered by its own family gate instead.]
if python3 "$FAMILY_TOOL" excludes-base-requirements --cells "$cells"; then
  echo "=== NATIVE_IMPORT_GATE_SKIPPED rlvigen-entrypoint (this job runs without part of the base environment) ==="
else
python3 - <<'PY'
import importlib

importlib.import_module("train")
# [Codex 2026-09-01 15:04 MSK: import the selected RobosuiteVGB wrapper before timing so undeclared wrapper imports fail as a dependency gate, not an apparent calibration]
importlib.import_module("wrappers.robo_wrapper")
PY
fi
python3 - <<'PY' > "$out/environment.json"
import json
import platform
import subprocess

# [Claude 2026-09-03: torch is not present in every job. `ctrl` excludes it -- it is a JAX
# baseline, and keeping torch meant pip resolving CUDA 13 wheels onto a CUDA 12.2 driver. This
# block used to `import torch` unconditionally and so failed the one family that had successfully
# got rid of it (job bt1q2rjpgrms72lltsf0, ModuleNotFoundError at the environment probe, after
# everything else had passed).
#
# The gate's PURPOSE is kept: a GPU job that silently lands on CPU is the failure worth catching,
# and it is still caught -- by whichever framework this job actually has, and by nvidia-smi when
# it has neither.]
payload = {"platform": platform.platform()}
accelerator = None
try:
    import torch
    payload["torch"] = torch.__version__
    accelerator = bool(torch.cuda.is_available())
    if accelerator:
        payload["gpu"] = torch.cuda.get_device_name(0)
except Exception:
    payload["torch"] = None
if accelerator is None:
    try:
        import jax
        payload["jax"] = jax.__version__
        gpus = [d for d in jax.devices() if d.platform in ("gpu", "cuda", "rocm")]
        accelerator = bool(gpus)
        if gpus:
            payload["gpu"] = str(gpus[0])
    except Exception:
        payload["jax"] = None
payload["cuda"] = bool(accelerator)
payload["nvidia_smi"] = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True, capture_output=True).stdout.strip()
# [Claude 2026-09-02 00:50 MSK: a long run writes a replay episode per 500 frames into the work
# directory. The container disk budget is the difference between a finished 500k run and one that
# dies at hour five, and nothing has ever recorded it.]
import shutil
payload["disk_bytes"] = {name: dict(zip(("total", "used", "free"), shutil.disk_usage(name))) for name in ("/tmp", "/")}
print(json.dumps(payload, sort_keys=True))
# Neither framework saw a device: fall back to the driver itself before failing, so a job
# whose framework is merely mis-detected is distinguishable from one with no GPU at all.
if not payload["cuda"] and payload["nvidia_smi"]:
    payload["cuda_via_nvidia_smi_only"] = True
raise SystemExit(0 if (payload["cuda"] or payload["nvidia_smi"]) else 1)
PY
python3 - <<'PY' > "$out/egl.json"
import json

import mujoco
from OpenGL import GL

context = mujoco.GLContext(64, 64)
try:
    context.make_current()
    renderer = (GL.glGetString(GL.GL_RENDERER) or b"").decode(errors="replace")
    vendor = (GL.glGetString(GL.GL_VENDOR) or b"").decode(errors="replace")
    if not renderer or any(token in renderer.lower() for token in ("llvmpipe", "softpipe", "software", "swiftshader")):
        raise RuntimeError(f"software EGL renderer: {renderer or 'unreported'}")
    print(json.dumps({"renderer": renderer, "vendor": vendor}, sort_keys=True))
finally:
    context.free()
PY
if cells_need_places365 "$cells"; then
  # [Claude 2026-09-03] This was a bare `[[ -n "$asset_archive" ]]`, which under `set -e` ends the
  # job with NO message at all: the log simply stops mid-import and the status is ERROR. It cost
  # two jobs of the pre-production pass (bt1bciubjre32859p455, bt1hgetjvsf2s56opbv6) whose configs
  # forgot the asset input -- both logs ended at byte-identical length with no error, which is the
  # worst possible diagnostic. A guard that refuses must say what it wants.
  # [Claude 2026-09-08] A pre-extracted corpus, bind-mounted READ-ONLY, instead of copying and
  # expanding the archive per job.
  #
  # The archive path below copies ~21 GiB into the staging directory and expands ~24 GiB more into
  # this job's work root -- every job, for a corpus of 1.8M JPEGs that never changes. Two jobs
  # running at once do it twice. On a filesystem that is 99% full and shared with about twenty
  # people, that is the largest avoidable thing this runner does.
  #
  # `NATIVE_PLACES365_DIR` names a directory that ALREADY holds the extracted tree. The wrapper
  # mounts it `:ro`, so a cell cannot corrupt an asset every other cell depends on, and the
  # existing symlink step below points into it exactly as it would point into a fresh extraction.
  # Nothing downstream can tell the difference: `check-asset` and the loader verdict both run
  # against whatever `asset_dir` names.
  #
  # It is CHECKED, not trusted. A directory that does not exist, or that holds neither layout this
  # code understands, refuses here rather than failing later inside the loader.
  if [[ -n "${NATIVE_PLACES365_DIR:-}" ]]; then
    asset_dir="$NATIVE_PLACES365_DIR"
    if [[ ! -d "$asset_dir" ]]; then
      echo "=== NATIVE_PLACES365_DIR_MISSING $asset_dir is not a directory ===" >&2
      exit 1
    fi
    if [[ ! -d "$asset_dir/places365_standard" && ! -d "$asset_dir/val" ]]; then
      echo "=== NATIVE_PLACES365_DIR_SHAPE $asset_dir has neither places365_standard/ nor val/ ===" >&2
      echo "    A pre-extracted corpus must have the same shape the archive expands to." >&2
      ls -1 "$asset_dir" 2>/dev/null | head -5 | sed 's/^/      /' >&2
      exit 1
    fi
    echo "=== NATIVE_PLACES365_PREEXTRACTED $asset_dir (no copy, no extraction this job) ===" >&2
  elif [[ -z "$asset_archive" ]]; then
    echo "=== NATIVE_PLACES365_MISSING these cells need the Places365 val set and no asset archive was passed ===" >&2
    echo "    cells: $cells" >&2
    echo "    add a 4th positional argument and a places365-val.tgz job input, plus" >&2
    echo "    PLACES365_EXPECTED_COUNT and PLACES365_EXPECTED_SHA256 in the environment," >&2
    echo "    or set NATIVE_PLACES365_DIR to a pre-extracted corpus mounted read-only." >&2
    exit 1
  else
    asset_dir="$work/places365-val"
    mkdir -p "$asset_dir"
    # -xf, not -xzf: the canonical production asset is `places365standard_easyformat.tar`, which is
    # NOT gzipped, while the val probe fixture is a .tgz. Both tar implementations auto-detect
    # compression from the stream, so one flag reads either. -xzf refused the production archive.
    tar --no-same-owner -xf "$asset_archive" -C "$asset_dir"
  fi
  dataset_root="$work/places365-root"
  mkdir -p "$dataset_root/places365_standard"
  # [Claude 2026-09-07, DECISION-SHEET A22 DECIDED.] The overlay split is now NAMED rather than
  # implied by running this script at all. `train` is the production value: the overlay
  # distribution IS the mechanism for svea/sgqn/soda, so drawing it from the validation partition
  # is a learning-affecting deviation, and both arguments for keeping it collapsed -- the "same
  # split so ordering is unaffected" inference does not follow, and the cost was priced at 105 GB
  # when DMC-GB's own README points at places365standard_easyformat.tar, ~21 GB.
  #
  # Probes keep `val`, which is why the default is not simply flipped: a functional probe should not
  # need a 21 GB asset. Production is refused on `val` unless the deviation is stated explicitly,
  # so the fleet cannot inherit it by silence the way it did until today.
  places_split="${NATIVE_PLACES365_SPLIT:-val}"
  if [[ "${FRAMES:-10000}" -ge 600000 && "$places_split" != "train" ]]; then
    if [[ "${NATIVE_PLACES365_ACCEPT_VAL:-0}" != "1" ]]; then
      echo "REFUSING: production scale with Places365 split '$places_split'." >&2
      echo "  A22 decided the upstream TRAIN split for production; the overlay distribution is the" >&2
      echo "  mechanism for svea/sgqn/soda, so this changes what they learn." >&2
      echo "  Provision places365standard_easyformat.tar (~21 GB) and set" >&2
      echo "  NATIVE_PLACES365_SPLIT=train, or set NATIVE_PLACES365_ACCEPT_VAL=1 to run the" >&2
      echo "  declared deviation deliberately." >&2
      exit 3
    fi
    echo "=== NATIVE_PLACES365_DECLARED_DEVIATION split=$places_split (A22 accepted explicitly) ===" >&2
  fi
  # [Claude 2026-09-08] `check-asset` validated "$asset_dir/val/images" UNCONDITIONALLY, even
  # under NATIVE_PLACES365_SPLIT=train. That is the SAME defect external review 24 found in the
  # loader-selection assertion below -- caught there, missed here, one call earlier. Two
  # consequences, neither visible below production scale:
  #
  #   - the integrity check certified 36,500 VAL images while the canary
  #     (bt1f8b5gb39jgadqngke) trained on the fixture's 1,000 TRAIN ones. The split that is the
  #     learning mechanism for svea/sgqn/soda was the one split never checked.
  #   - the canonical `places365standard_easyformat.tar` carries no flat `val/images` at all, so
  #     the first real production cell would have died at this guard AFTER the 21 GB upload.
  #
  # Resolve the split that is actually CONSUMED, in whichever layout the archive carries: the
  # easyformat archive nests `places365_standard/<split>/<class>/`, the probe fixtures ship a flat
  # `<split>/`. Refuse loudly rather than link a path that does not exist.
  places_link_source=""
  if [[ -d "$asset_dir/places365_standard/$places_split" ]]; then
    places_link_source="$asset_dir/places365_standard/$places_split"
  elif [[ -d "$asset_dir/$places_split" ]]; then
    places_link_source="$asset_dir/$places_split"
  else
    echo "REFUSING: NATIVE_PLACES365_SPLIT=$places_split but the archive has no such split." >&2
    echo "  looked for: $asset_dir/places365_standard/$places_split and $asset_dir/$places_split" >&2
    exit 3
  fi
  # DMC-GB's val fixture nests images one level down as `val/images` with no class directories;
  # the easyformat archive uses `<split>/<class>/`. `asset_digest` hashes paths RELATIVE to the
  # directory it is given, so checking `val/images` rather than `val` is what keeps every
  # previously declared val sha256 valid. The count and hash must describe the CONSUMED split.
  if [[ -d "$places_link_source/images" ]]; then
    asset_images="$places_link_source/images"
  else
    asset_images="$places_link_source"
  fi
  python3 datasphere/native/contract.py check-asset --asset "$asset_images" --expected-count "${PLACES365_EXPECTED_COUNT:?}" --expected-sha256 "${PLACES365_EXPECTED_SHA256:?}"
  ln -sfn "$places_link_source" "$dataset_root/places365_standard/$places_split"
  # Leave val linked too when the archive carries it, so nothing that assumed the previous on-disk
  # shape changes behaviour as a side effect of this fix.
  if [[ "$places_split" != "val" && -d "$asset_dir/val" ]]; then
    ln -sfn "$asset_dir/val" "$dataset_root/places365_standard/val"
  fi
  # [Claude 2026-09-08, second pass] Both loaders honour this now. `dmc_gb`'s copy in
  # `src/augmentations.py` hardcoded `num_workers=16` with no override -- DOUBLE the count that
  # produced glibc heap corruption in the RL-ViGen copy and prompted P19 -- and the dmc_gb patch
  # was extended to read the same variable. The log line below reports the real value for both
  # rather than asserting a constant for one of them.
  #
  # [Claude 2026-09-08] P19 introduced `RLVIGEN_PLACES_WORKERS` as a dial and nothing ever read it
  # here, forwarded it, or recorded it. Its value is not cosmetic: `RandomResizedCrop` and
  # `RandomHorizontalFlip` run INSIDE the DataLoader workers, whose RNG is seeded from
  # `base_seed + worker_id`, so the worker count changes the actual pixels overlaid.
  #
  # Measured locally on the fixture at num_workers 0 vs 2, same seed: identical file list,
  # identical order, identical sampled indices -- and a first-batch max absolute pixel difference
  # of 0.9686 (mean 0.2052). So review 2 sec.15 was right to call P19's claim unproven, and the
  # claim is true as far as it goes: the IMAGES and their ORDER really are unchanged. What it
  # omits is that the crop and flip applied to them are not.
  #
  # This does not change the distribution -- a different random crop of the same image, drawn in
  # the same order from the same pool, is the same draw process -- so it is not a fidelity or a
  # comparability defect. It does mean a seed is only bit-reproducible at a FIXED worker count.
  # Pin it and stamp it, so a rerun that differs is visible rather than silent.
  # The DEFAULT is 0, not upstream's 8, and that is a correctness choice rather than a performance
  # one. P19's own comment in `RL-ViGen-upstream/utils.py` blames 8 for
  # `malloc_consolidate(): unaligned fastbin chunk detected` -- and every places cfg that ever ran
  # to completion (`cfg-svea-functional-v118`, `cfg-soda-functional-v121`,
  # `cfg-preprod-sgqn-v56/v58`) sets 0 explicitly.
  #
  # [Claude 2026-09-08] The first version of THIS block defaulted to 8 anyway. It quoted the
  # reproducibility half of P19's comment and ignored the sentence above it, so
  # `cfg-rlvigen-attest-v197.yaml`, which sets no dial, ran svea with 8 workers for the first time
  # and died exactly as P19 predicted: heap corruption in a forked loader worker at ~8500 frames,
  # `RuntimeError: DataLoader worker (pid 23921) is killed by signal: Aborted.` raised inside
  # `random_overlay` (job bt12f5us5h120laajpme).
  #
  # That job also FALSIFIES P19's stated condition. P19 says "on a 4-CPU container"; this ran on
  # `gt4i.1`, which `resources.json` records as 8 logical CPUs, and 8 workers corrupted the heap
  # there too. So the safe value is not "workers <= cores".
  #
  # And the failure is NOT deterministic, which is the part that matters for choosing a default:
  # `bt1utl06n6mqffrt2jdn` (cfg-sgqn-cover-v197) ran the SAME overlay path, the same 10000 frames,
  # the same absent dial and therefore the same 8 workers, on the same tier in the same hour -- and
  # exited SUCCESS in 2381s. `malloc_consolidate(): unaligned fastbin chunk detected` is glibc
  # noticing an already-corrupted heap, so which allocation trips it is a matter of timing. One
  # clean run at 8 is not evidence that 8 is safe; it is evidence that the corruption is
  # intermittent, which is worse, because it means a 600k-frame production cell samples the failure
  # many more times than a 10k smoke does.
  #
  # 0 is the only value with a clean-exit HISTORY rather than a clean-exit INSTANCE
  # (`cfg-svea-functional-v118`, `cfg-soda-functional-v121`, `cfg-preprod-sgqn-v56/v58`), and it
  # removes the forked worker entirely rather than making it less likely to lose the race. A dial
  # whose default is the value its own rationale indicts is worse than no dial, because the cfgs
  # that need it most are the ones that do not set it.
  places_workers="${RLVIGEN_PLACES_WORKERS:-0}"
  export RLVIGEN_PLACES_WORKERS="$places_workers"
  echo "=== NATIVE_PLACES365_LOADER split=$places_split rlvigen_workers=$places_workers dmc_gb_workers=$places_workers ===" >&2
  python3 datasphere/native/configure_places365_val.py --repo RL-ViGen-upstream --dataset-root "$dataset_root" --split "$places_split"
  python3 datasphere/native/configure_places365_val.py --repo RL-ViGen-upstream --dataset-root "$dataset_root" --split "$places_split" --check
  # [Claude 2026-09-02 04:20 MSK: soda loads the overlay through dmc_gb's own copy of the same
  # loader, so it needs the same val pinning or the two families would overlay from different
  # image distributions. `data` is where dmc_gb's launcher symlinks its dataset root from.]
  ln -sfn "$dataset_root" "$work/data"
  if [[ -d "$work/runnable/dmc_gb" ]]; then
    python3 datasphere/native/configure_places365_val.py --repo runnable/dmc_gb --dataset-root "$dataset_root" --flavor dmc_gb --split "$places_split"
    python3 datasphere/native/configure_places365_val.py --repo runnable/dmc_gb --dataset-root "$dataset_root" --flavor dmc_gb --split "$places_split" --check
  fi
  # [Claude 2026-09-07, external review 24] This asserted `.../val` unconditionally, while the
  # loader immediately above was configured for $places_split. Under the DECIDED production value
  # `train` the loader correctly resolves to the train root and this check then failed it --
  # "loader selected .../train, expected .../val". The check is right to exist; it was asserting
  # the wrong partition.
  # [Claude 2026-09-08, A57] The VERDICT is a printed marker, not the interpreter's exit code.
  #
  # Job bt1jmirrveqa3p8lnru5 died here after everything it checks had already passed: the split
  # resolved, check-asset passed, `NATIVE_PLACES365_LOADER split=train` was stamped and
  # `Loaded dataset from /tmp/native-work/places365-root` printed. Then:
  #
  #   terminate called without an active exception
  #   Aborted (core dumped)
  #
  # That is a C++ std::terminate at interpreter teardown -- a thread from torch/MuJoCo/EGL not
  # joined at exit -- and it happens AFTER the comparison this block exists to make. The identical
  # block succeeded in the previous wave (bt1tjqjmpcnicb6ih739), so it is a race, not a regression.
  #
  # Killing a completed 100-minute cell over a teardown race is the wrong trade, and simply
  # ignoring the exit code would also ignore a real mismatch. So the check reports itself: the
  # RuntimeError below prevents the marker, and the shell requires the marker. A genuine
  # wrong-split failure still stops the job; a crash during exit no longer does.
  places_verdict="$work/places365-loader-verdict.txt"
  python3 - "$dataset_root/places365_standard/$places_split" > "$places_verdict" 2>&1 <<'PY' || true
import pathlib
import sys
import utils

utils._load_places(batch_size=1, image_size=84, num_workers=0)
actual = pathlib.Path(utils.places_dataloader.dataset.root).resolve()
expected = pathlib.Path(sys.argv[1]).resolve()
if actual != expected:
    raise RuntimeError(f'Places365 loader selected {actual}, expected {expected}')
print("NATIVE_PLACES365_LOADER_VERIFIED", actual, flush=True)
PY
  if ! grep -q "NATIVE_PLACES365_LOADER_VERIFIED" "$places_verdict"; then
    echo "REFUSING: the Places365 loader did not verify against $places_split." >&2
    sed -n '1,40p' "$places_verdict" >&2
    exit 3
  fi
  grep -h "NATIVE_PLACES365_LOADER_VERIFIED" "$places_verdict" >&2
fi
# [Claude 2026-09-02 00:50 MSK: BASELINES runs several RL-ViGen agents in one job. They share one
# bootstrap, one dependency closure and one machine, so a three-baseline job costs one bootstrap
# instead of three. BASELINE stays accepted so every previously submitted configuration still
# means exactly what it meant.]
# [Claude 2026-09-02 04:20 MSK: import every family's real entry point before any timed cell. This
# is the gate that already caught termcolor, numba, matplotlib and h5py on the RL-ViGen path, each
# time for the price of a bootstrap instead of a calibration.]
# [Claude 2026-09-02 08:05 MSK: a gate failure disqualifies that family's cells and nothing else.
# Killing the job would mean one family's undeclared import destroys another family's calibration
# in the same job, which is exactly the coupling the per-cell design exists to avoid. The job still
# fails at the end.]
BLOCKED_FAMILIES="${DEPENDENCY_BLOCKED:-}"
if [[ "${PREFLIGHT_ONLY:-0}" != "1" ]]; then
  for gate_family in $(python3 "$FAMILY_TOOL" families-of-cells --cells "$cells"); do
    echo "=== NATIVE_IMPORT_GATE $gate_family ==="
    if [[ " $BLOCKED_FAMILIES " == *" $gate_family "* ]]; then
      echo "=== NATIVE_IMPORT_GATE_SKIPPED $gate_family (its dependencies did not install) ===" >&2
    elif python3 "$FAMILY_TOOL" import-gate --family "$gate_family" --root "$work" --cells "$cells"; then
      echo "=== NATIVE_IMPORT_GATE_PASSED $gate_family ==="
    else
      echo "=== NATIVE_IMPORT_GATE_FAILED $gate_family ===" >&2
      BLOCKED_FAMILIES="$BLOCKED_FAMILIES $gate_family"
    fi
  done
fi
export BLOCKED_FAMILIES="${BLOCKED_FAMILIES# }"

# The exact "else\n  run_cell_list" / "\nfi\n# [Claude" text below is matched literally by
# tests/test_datasphere_native_contract.py::test_runner_sets_completion_only_on_success_and_
# records_failure_marker, which slices this block out of the file by string search rather than
# parsing bash. Reshaping the else-branch's first line or the blank-line/comment layout around
# the closing `fi` will break that slice without touching its behavior -- update the test's split
# markers in the SAME edit if this block's literal text must change.
cell_status=0
export FAILURE_MARKER=""
if [[ "${PREFLIGHT_ONLY:-0}" == "1" ]]; then
  : > "$out/training.log"
  export FINAL_EVALUATION_MARKER=""
  export FAILED_CELLS=""
elif [[ -n "${OFFLINE_EVAL_SNAPSHOT:-}" ]]; then
  # [Corrected 2026-09-05: a completion marker used to export unconditionally even when
  # run_offline_eval failed, so the manifest could claim NATIVE_OFFLINE_EVAL_COMPLETED for a run
  # that returned nonzero. The marker now reflects cell_status, not the shell's own exit path.]
  if run_offline_eval "$out"; then
    export FINAL_EVALUATION_MARKER="NATIVE_OFFLINE_EVAL_COMPLETED"
  else
    cell_status=1
    export FINAL_EVALUATION_MARKER=""
    export FAILURE_MARKER="NATIVE_OFFLINE_EVAL_FAILED"
  fi
  export FAILED_CELLS=""
else
  # [Claude 2026-09-07, external recommendation 22 item 9.] Here rather than beside the other
  # preflights: this one needs torch/jax importable, and the family's dependencies are installed
  # only at line ~960. Every earlier refusal (host profile, budget, co-schedulability, memory) is
  # answerable from the descriptor alone and therefore runs before the bootstrap is paid for; this
  # one cannot be, so it runs at the last moment before training instead.
  require_accelerator "$cells"
  run_cell_list_ok=1
  # [Corrected 2026-09-05, external review: the analogous training-path bug -- a failed
  # run_cell_list (nonzero via `|| cell_status=1`) still exported the COMPLETED marker
  # unconditionally right after. run_cell_list already exports the real FAILED_CELLS before
  # returning nonzero; this branch must not overwrite it and must not claim completion on failure.]
  if run_cell_list "$cells" "$task" "$frames" "$eval_every" "$eval_episodes" "$out" "$work"; then
    export FINAL_EVALUATION_MARKER="NATIVE_FINAL_EVALUATION_COMPLETED"
  else
    cell_status=1
    export FINAL_EVALUATION_MARKER=""
    export FAILURE_MARKER="NATIVE_FINAL_EVALUATION_FAILED cells=$FAILED_CELLS"
  fi
fi
# Record provenance before the normalizer runs.  The normalized rows inherit this manifest, so the
# execution kind cannot be inferred later from whether a file happened to be nonempty.
if [[ "${PREFLIGHT_ONLY:-0}" == "1" ]]; then
  EXECUTION_KIND="preflight"
elif [[ -n "${OFFLINE_EVAL_SNAPSHOT:-}" ]]; then
  EXECUTION_KIND="eval_only_validation"
elif [[ "${NATIVE_PRODUCTION:-0}" == "1" ]]; then
  EXECUTION_KIND="training_production"
else
  EXECUTION_KIND="exploratory"
fi
export EXECUTION_KIND
# [Claude 2026-09-02 00:50 MSK: one manifest entry per baseline. A single job now carries several
# calibrations, so a single top-level `baseline`/`snapshot_retained` pair could no longer say which
# run it described.]
python3 - <<'PY' > "$out/run_manifest.json"
import hashlib
import json
import os
import re
from pathlib import Path

OUT = Path("/tmp/native-out")
preflight_only = os.environ.get("PREFLIGHT_ONLY", "0") == "1"
offline_eval = bool(os.environ.get("OFFLINE_EVAL_SNAPSHOT"))
production = os.environ.get("NATIVE_PRODUCTION", "0") == "1"
execution_kind = (
    "preflight" if preflight_only else
    "eval_only_validation" if offline_eval else
    "training_production" if production else
    "exploratory"
)
requested = [spec.strip() for spec in os.environ.get("NATIVE_CELLS", "").split(",") if spec.strip()]
failed = [name for name in os.environ.get("FAILED_CELLS", "").split() if name.strip()]
default_seed = os.environ.get("SEED", "1")


def identify(spec):
    # Exact shape asserted by tests/test_datasphere_native_contract.py's manifest tests (they
    # build NATIVE_CELLS from already-formed identifiers, not real colon specs) -- if this
    # function's branching changes, run that file before trusting the manifest again.
    if ":" in spec:
        baseline, _, seed = spec.partition(":")
        return baseline, (seed or default_seed)
    # No colon: `spec` is already a formed "baseline-sSEED" identifier rather than a real
    # `--cells baseline:seed` entry. Real `NATIVE_CELLS` is always colon-form (line ~747); this
    # branch exists so a caller building NATIVE_CELLS directly from identifiers (a test fixture,
    # or a future caller that already knows the identifier) resolves to the SAME identifier
    # instead of silently getting a second "-s{default_seed}" appended onto it.
    match = re.match(r"^(.+)-s([^-]+)$", spec)
    if match:
        return match.group(1), match.group(2)
    return spec, default_seed


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def rows(path):
    return max(0, len(path.read_text().splitlines()) - 1) if path.exists() else 0


def final_marker(path):
    """Return the endpoint marker actually emitted by this cell's own evaluator.

    IDAAC floors and PPG ceils a requested budget, and a job may contain several cells. The
    top-level requested-frame marker cannot describe either case. `run_one_cell` has already
    verified the family's exact endpoint; the manifest records the observed per-cell marker so
    it remains truthful without re-deriving the endpoint from a later-edited descriptor.
    """
    if not path.exists():
        return None
    hits = re.findall(r"NATIVE_FINAL_EVALUATION_COMPLETED frame=([0-9]+)",
                      path.read_text(errors="replace"))
    return f"NATIVE_FINAL_EVALUATION_COMPLETED frame={hits[-1]}" if hits else None


def cell_failure_marker(path):
    """The line explaining why a FAILED cell failed, from its own log.

    [Added 2026-09-05, external review pointing at run_probe.sh:1070-1071.] A cell can fail
    AFTER emitting a real completion marker -- training finishes and saves, then endpoint
    evaluation dies -- so a cell's own log can contain BOTH a success line and a failure line.
    Only called for cells already known to be in `failed`; this never overrides `completed`.
    """
    if not path.exists():
        return None
    hits = re.findall(r"NATIVE_\w*_FAILED[^\n]*", path.read_text(errors="replace"))
    return hits[-1] if hits else None


frames_requested = int(os.environ.get("FRAMES", "10000"))
cells = {}
for spec in requested:
    baseline, seed = identify(spec)
    identifier = f"{baseline}-s{seed}"
    directory = OUT / "cells" / identifier
    log = directory / "training.log"
    snapshot = directory / "snapshot.pt"
    cell_failed = identifier in failed
    marker = final_marker(log)
    cells[identifier] = {
        "baseline": baseline,
        "seed": seed,
        "completed": not cell_failed and directory.exists(),
        "frames_requested": frames_requested,
        "observed_endpoint": (int(re.search(r"frame=([0-9]+)", marker).group(1))
                              if marker else None),
        "final_evaluation_marker": final_marker(log),
        "terminal_status": "completed",
        "failure_marker": None,
        "snapshot_retained": snapshot.exists() and snapshot.stat().st_size > 0,
        "snapshot_bytes": snapshot.stat().st_size if snapshot.exists() else 0,
        "train_curve_rows": rows(directory / "train.csv"),
        "eval_curve_rows": rows(directory / "eval.csv"),
        "resource_samples": read_json(directory / "resources.json"),
    }
    # A cell can emit a real completion marker and still be in `failed` -- training saved, then
    # endpoint evaluation died. `failed` is the authoritative signal; the log's own success text
    # must not override it, or a failed cell reads as a completed one from its own marker alone.
    if cell_failed:
        cells[identifier]["observed_endpoint"] = None
        cells[identifier]["final_evaluation_marker"] = None
        cells[identifier]["terminal_status"] = "failed"
        cells[identifier]["failure_marker"] = cell_failure_marker(log)

# [Claude 2026-09-08, A54 -- external review 27 sec.3] `command` was the LITERAL
# "runnable/_launch/rlvigen.sh" for every family, so the immutable manifest of a rad, soda, alda,
# idaac, ppg, ibac_sni or ctrl result asserted it was produced by the RL-ViGen launcher. Seven of
# twelve families carried a false statement about how they were generated -- in the one artifact
# whose purpose is to make post-hoc provenance editing unnecessary.
#
# The effective configuration per cell already carries the real resolved argv, so nothing ran
# wrong; what was wrong is what the manifest SAID. Recorded now as review 27 asks: the outer entry
# point and the per-cell family launcher as separate fields, each true of what it names.
# Fail-soft: this block writes the manifest AFTER the cells have run, so an exception here would
# destroy a completed job's evidence over a provenance nicety. An unreadable descriptor yields
# "unknown", which is honest, rather than a traceback.
try:
    _FAMILIES = json.loads(Path("datasphere/native/families.json").read_text())
    _LAUNCHER_OF_BASELINE = {
        baseline: entry.get("launcher")
        for name, entry in _FAMILIES.items()
        if isinstance(entry, dict)
        for baseline in entry.get("baselines", [])
    }
except Exception:
    _LAUNCHER_OF_BASELINE = {}
_cell_launchers = {}
for _spec in requested:
    _baseline = identify(_spec)[0]
    _cell_launchers[identify(_spec)[0] + "-s" + identify(_spec)[1]] = _LAUNCHER_OF_BASELINE.get(
        _baseline, "unknown")

json.dump({
    # The outer entry point, which is true for every family. The family launcher is per cell.
    "command": "datasphere/native/run_probe.sh",
    "cell_launchers": _cell_launchers,
    "cells_requested": requested,
    "cells_failed": failed,
    "cells": cells,
    "concurrent": os.environ.get("NATIVE_CONCURRENT") == "1",
    "baseline": identify(requested[0])[0] if len(requested) == 1 else None,
    "frames": os.environ.get("FRAMES", "10000"),
    "frames_requested": frames_requested,
    "failure_marker": os.environ.get("FAILURE_MARKER") or None,
    "eval_every_frames": os.environ.get("NATIVE_EVAL_EVERY_FRAMES"),
    "eval_episodes": os.environ.get("NATIVE_EVAL_EPISODES"),
    "extra_overrides": os.environ.get("NATIVE_EXTRA_OVERRIDES") or None,
    "host_profile": os.environ.get("NATIVE_HOST_PROFILE", "datasphere"),
    "eval_scenes": os.environ.get("RLVIGEN_EVAL_SCENES") or "0,1,2,3,4,5,6,7,8,9",
    "cell_timeout_seconds": os.environ.get("CELL_TIMEOUT_SECONDS") or None,
    "seed": default_seed,
    "preflight_only": preflight_only,
    "finalization_schema": 1,
    "execution_kind": execution_kind,
    "record_delivery": "pending",
    "record_artifacts": {"inputs": [], "output": None},
    "record_delivery_error": None,
    "final_evaluation_marker": os.environ.get("FINAL_EVALUATION_MARKER") or None,
    "snapshot_retained": bool(cells) and all(entry["snapshot_retained"] for entry in cells.values()),
    "payload_sha256": os.environ["PAYLOAD_SHA256"],
    "asset_sha256": os.environ["ASSET_SHA256"],
    # Immutable environment identity: package versions alone do not identify the CUDA userspace
    # that loads MuJoCo and JAX. Keep the image and direct native-input digest beside each result.
    "container_image": os.environ.get("NATIVE_CONTAINER_IMAGE", "nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000"),
    "requirements_native_sha256": hashlib.sha256(Path("requirements-native.txt").read_bytes()).hexdigest()
        if Path("requirements-native.txt").is_file() else None,
    "resolved_packages": read_json(OUT / "resolved_packages.json"),
    "environment": read_json(OUT / "environment.json"),
    "egl": read_json(OUT / "egl.json"),
    "resource_high_water_source": "GNU time -v in each cells/<baseline>-s<seed>/training.log",
    # [Added 2026-09-05.] Each cell's EFFECTIVE configuration, carried in the manifest so it also
    # reaches the lightweight RECORDS_OUT bundle -- offline rows inherit the manifest, and a caller
    # who skips result.tgz would otherwise get rows with no record of what produced them. The files
    # themselves remain in the archive; this is the copy that travels with the numbers.
    "effective_configs": {path.parent.name: read_json(path)
                          for path in sorted((OUT / "cells").glob("*/effective_config.json"))}
        if (OUT / "cells").is_dir() else {},
}, (OUT / "run_manifest.json").open("w"), sort_keys=True)
PY
# [Claude 2026-09-02 12:45 MSK: one common record per measurement, derived from each family's own
# logs after they are written. Additive and lossless -- every native file is retained unchanged and
# stays the source of truth -- and training-unaffecting by construction, because it runs here. It
# makes `regime` and `scene_set` explicit on every row, which is what stops a cross-baseline table
# from putting a ten-scene average and a single-scene number in the same column.]
normalize_records() {
  local target="$1" normalizer_status=0 marker required_delivery=0
  python3 datasphere/native/normalize_curves.py --directory "$target" \
    --output "$target/records.jsonl" || normalizer_status="$?"
  if [[ "$normalizer_status" -eq 0 ]]; then
    return 0
  fi
  marker="NATIVE_RECORDS_NORMALIZATION_FAILED rc=$normalizer_status"
  echo "=== $marker ===" >&2
  # The archive is still the evidence boundary.  A production failure is recorded now, before
  # RECORDS_OUT enrichment and tar, and the final nonzero exit happens only after that archive is
  # written below.  An earlier cell failure owns the failure marker and must not be replaced.
  if [[ "${EXECUTION_KIND:-}" == "training_production" ||
        "${EXECUTION_KIND:-}" == "eval_only_validation" ||
        "${ENDPOINT_EVAL:-0}" == "1" ]]; then
    required_delivery=1
  fi
  if [[ "$cell_status" -eq 0 && "$required_delivery" -eq 1 ]]; then
    python3 - "$target/run_manifest.json" "$marker" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
marker = sys.argv[2]
manifest = json.loads(path.read_text())
manifest["final_evaluation_marker"] = None
manifest["failure_marker"] = marker
manifest["records_normalization_status"] = "failed"
manifest["records_normalization_failure_marker"] = marker
path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
PY
    export FINAL_EVALUATION_MARKER=""
    export FAILURE_MARKER="$marker"
    cell_status=1
  else
    echo "=== NATIVE_RECORDS_NORMALIZATION_TOLERATED (exploratory or earlier cell failure) ===" >&2
  fi
  return 0
}

finalize_record_delivery() {
  local target="$1" delivery_path="${2:-}" execution_status="${3:-1}" collection_status="${4:-0}"
  local delivery_channel="${5:-external}"
  local -a command=(python3 datasphere/native/contract.py finalize-records
                    --manifest "$target/run_manifest.json"
                    --execution-status "$execution_status"
                    --collection-status "$collection_status"
                    --delivery-channel "$delivery_channel")
  if [[ -n "$delivery_path" ]]; then
    command+=(--records-out "$delivery_path")
  fi
  "${command[@]}"
}

normalize_records "$out"

# [Claude 2026-09-03] The records are also emitted as a SEPARATE output when the caller asks for
# one, so the cheap artefact can be fetched without the expensive one.
#
# Why it matters at production scale: a five-cell 10k job returned a **791 MB** result.tgz, almost
# all of it checkpoints, and the records inside it are ~100 KB. At 6e5 x 12 baselines x N seeds the
# archives are the only thing standing between a decision and an afternoon of downloading, and this
# laptop has ~12 GB free. `docs/EVAL-PROTOCOL.md` §6 makes the rule -- checkpoints stay remote,
# records come back -- and this is the mechanism that lets the rule be followed rather than
# remembered.
#
# Additive: result.tgz is unchanged and still contains the native sources. RECORDS_OUT remains
# optional for direct/legacy invocations, but those invocations now get an explicitly archive-only
# delivery artifact rather than a post-evaluation missing-output failure.
#
# [Claude 2026-09-04] OFFLINE-EVAL JOBS WRITE THEIR RECORDS SOMEWHERE ELSE, and the first version
# of this block did not know that. `normalize_curves.py` reads training CELLS and writes
# records.jsonl; an eval-only job has no cells, so records.jsonl is legitimately empty while the
# eval rows sit in offline_eval_<device>.jsonl (written at the --out of the eval invocation above).
# Result: bt1ip5f8c6mqqm7fd2bn returned an EMPTY records.jsonl and announced NATIVE_RECORDS_EMPTY
# while its four eval records rode home inside result.tgz -- the expensive artefact this block
# exists to let the caller skip. The failure was silent and the job otherwise succeeded.
#
collect_record_delivery() {
  local root="$1" external="${2:-}" internal="$1/records_delivery.jsonl"
  record_collection_status=0

  # Check before truncating: either destination is never a native source. resolve(strict=False)
  # catches relative paths and symlink aliases even when the destination has not been created yet;
  # samefile additionally catches an existing hard link to a source.
  if [[ -n "$external" ]] && python3 - "$root" "$external" "$internal" <<'ALIAS_GUARD'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2]).resolve(strict=False)
internal = Path(sys.argv[3]).resolve(strict=False)
sources = [root / "records.jsonl"]
sources.extend(sorted(root.glob("offline_eval_*.jsonl")))
sources.extend(sorted(root.glob("cells/*/offline_eval_*.jsonl")))
sources.append(internal)

for source in sources:
    resolved_source = source.resolve(strict=False)
    if destination == resolved_source:
        print(f"source alias: {sys.argv[2]} -> {source}", file=sys.stderr)
        raise SystemExit(1)
    try:
        if destination.exists() and source.exists() and os.path.samefile(destination, source):
            print(f"source alias: {sys.argv[2]} is the same file as {source}", file=sys.stderr)
            raise SystemExit(1)
    except OSError:
        # The lexical/resolved comparison above remains authoritative when a
        # filesystem identity query is unavailable.
        pass
ALIAS_GUARD
  then
    :
  else
    if [[ -n "$external" ]]; then
      echo "=== NATIVE_RECORDS_OUT_SOURCE_ALIAS path=$external ===" >&2
      record_collection_status=1
    fi
  fi

  if [[ "$record_collection_status" -eq 0 ]]; then
    if ! : > "$internal"; then
      echo "=== NATIVE_RECORDS_INTERNAL_UNWRITABLE path=$internal ===" >&2
      record_collection_status=1
    else
      # An `if` rather than `[[ -s "$src" ]] && cat ...`: under `set -e` a false test as the LAST
      # command of a loop body is the exit status of the body, and that is how two jobs died silently
      # earlier in this project. An unmatched glob simply fails `-s` and is skipped.
      # [Claude 2026-09-04: the per-CELL glob was missing, and the curve evaluation writes there.
      # `run_curve_eval` emits one record per intermediate checkpoint into
      # `$out/cells/<cell>/offline_eval_curve.jsonl`; a collector that looks only in `$out` would have
      # left the entire offline curve -- the whole point of retaining intermediate checkpoints -- to
      # ride home inside result.tgz and be reported as NATIVE_RECORDS_EMPTY. That is the same failure
      # this block was written to fix, one directory level down.]
      # [Claude 2026-09-05, external review 7 section 7] OFFLINE ROWS USED TO COME HOME WITHOUT RUN
      # PROVENANCE. normalize_curves.py attaches `_run_provenance` (manifest/payload/asset digests,
      # container image, resolved packages, EGL state) to every TRAINING row it writes into
      # records.jsonl. The offline_eval_*.jsonl rows were concatenated raw, so the lightweight records
      # bundle -- the exact mechanism that exists so a caller can skip downloading result.tgz --
      # carried evaluation rows that were not independently auditable. The facts were only in the
      # archive we were trying to avoid fetching.
      #
      # Enriched here rather than in eval_grid.py because the manifest is a property of the JOB, and
      # eval_grid does not know it is running inside one; it is also written after eval_grid returns.
      for src in "$root/records.jsonl" "$root"/offline_eval_*.jsonl "$root"/cells/*/offline_eval_*.jsonl; do
        if [[ -s "$src" ]]; then
          case "$src" in
            *offline_eval_*)
              if ! python3 - "$src" "$root/run_manifest.json" >> "$internal" <<'ENRICH'
import json, sys
rows, manifest_path = sys.argv[1], sys.argv[2]
try:
    with open(manifest_path) as handle:
        manifest = json.load(handle)
except (OSError, ValueError) as error:
    # Loud, never silent, and never fatal: the rows themselves are the expensive thing and they
    # are already measured. An unprovenanced row is a finding, not a reason to discard a run.
    print(f"=== NATIVE_RECORDS_NO_MANIFEST {type(error).__name__}: offline rows ship unenriched ===",
          file=sys.stderr)
    manifest = None
with open(rows) as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        if manifest is None:
            print(line)
            continue
        try:
            row = json.loads(line)
        except ValueError:
            print(line)
            continue
        row.setdefault("_run_provenance", manifest)
        print(json.dumps(row, sort_keys=True))
ENRICH
              then
                echo "=== NATIVE_RECORDS_COLLECTION_FAILED source=$src ===" >&2
                record_collection_status=1
              fi
              ;;
            *)
              if ! cat "$src" >> "$internal"; then
                echo "=== NATIVE_RECORDS_COLLECTION_FAILED source=$src ===" >&2
                record_collection_status=1
              fi
              ;;
          esac
        fi
      done
    fi
  fi

  if [[ -n "$external" && "$record_collection_status" -eq 0 ]]; then
    if [[ -d "$external" ]] || ! : > "$external" || ! cat "$internal" >> "$external"; then
      echo "=== NATIVE_RECORDS_OUT_UNWRITABLE path=$external ===" >&2
      record_collection_status=1
    fi
  fi
  if [[ -s "$internal" ]]; then
    echo "=== NATIVE_RECORDS_EMITTED $(wc -l < "$internal") rows -> $(basename "$internal") ==="
  else
    echo "=== NATIVE_RECORDS_EMPTY no records were derived; the archive still holds the native curves ===" >&2
  fi
}

record_collection_status=0
record_delivery_path="$out/records_delivery.jsonl"
record_delivery_channel="archive_internal"
if [[ "${EXECUTION_KIND:-}" == "preflight" ]]; then
  record_delivery_path=""
  record_delivery_channel="external"
else
  if [[ -n "${RECORDS_OUT:-}" ]]; then
    record_delivery_path="$RECORDS_OUT"
    record_delivery_channel="external"
  fi
  collect_record_delivery "$out" "${RECORDS_OUT:-}"
fi

# Finalization is part of the evidence boundary.  A required delivery failure updates the
# manifest, but this status is propagated only after the archive below has been written.
finalization_status=0
if finalize_record_delivery "$out" "$record_delivery_path" "$cell_status" "$record_collection_status" \
  "$record_delivery_channel"; then
  :
else
  finalization_status=$?
  cell_status=1
fi

tar -czf "$result" -C "$out" .
if ! verify_result_archive "$result"; then
  exit 1
fi
# [Claude 2026-09-02 00:50 MSK: archive first, then fail. The evidence for the baselines that did
# run is exactly what the next decision needs, and DataSphere returns an output written before a
# non-zero exit.]
if [[ "$cell_status" -ne 0 ]]; then
  echo "native probe failed for cells: ${FAILED_CELLS:-unknown}" >&2
  exit 1
fi
if [[ "$finalization_status" -ne 0 ]]; then
  echo "native record delivery failed" >&2
  exit "$finalization_status"
fi
echo "native probe completed successfully"
