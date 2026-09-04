#!/usr/bin/env bash
set -euo pipefail

run_measured() {
  local output_dir="$1"
  shift
  local temporary
  temporary="$(mktemp -d)"
  local pipe="$temporary/training.pipe"
  mkfifo "$pipe"
  if command -v setsid >/dev/null; then
    setsid "$@" > "$pipe" 2>&1 &
  else
    "$@" > "$pipe" 2>&1 &
  fi
  local training_pid="$!"
  python3 datasphere/native/measure_resources.py --pid "$training_pid" --output "$output_dir/resources.json" &
  local sampler_pid="$!"
  tee "$output_dir/training.log" < "$pipe" &
  local tee_pid="$!"
  set +e
  wait "$training_pid"
  local training_status="$?"
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
  # [Claude 2026-09-02 10:40 MSK: a checkpoint full of NaNs is indistinguishable from a bad run in
  # every other artifact this project keeps -- docs/CONSTRUCTION.md#c57 records exactly that, for
  # 70,000 frames. Cheap here; expensive after seven hours.]
  python3 "$FAMILY_TOOL" check-finite --family "$family" --root "$work_root" \
    --checkpoint "$cell_out/snapshot.pt" || return 1
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
  if [[ "${NATIVE_CONCURRENT:-}" == "1" ]]; then
    local pids=() specs=()
    for spec in "${cell_list[@]}"; do
      echo "=== NATIVE_CELL_BEGIN $(cell_id "$spec") ==="
      run_one_cell "$spec" "$task" "$frames" "$eval_every" "$eval_episodes" "$out_root" "$work_root" &
      pids+=("$!")
      specs+=("$spec")
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

apply_production_settings() {
  [[ -n "${NATIVE_PRODUCTION:-}" ]] || return 0
  local prod_key prod_value
  while IFS='=' read -r prod_key prod_value; do
    [[ -z "$prod_key" || "$prod_key" == \#* ]] && continue
    if [[ "$prod_key" == "NATIVE_PRODUCTION_UNAPPLIED" ]]; then
      echo "=== NATIVE_PRODUCTION_UNAPPLIED $prod_value ===" >&2
      continue
    fi
    if [[ -z "${!prod_key:-}" ]]; then
      export "$prod_key=$prod_value"
      echo "=== NATIVE_PRODUCTION_SET $prod_key=$prod_value ==="
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
  apply_production_settings "$cells_arg"
  python3 "$FAMILY_TOOL" check-budget --cells "$cells_arg" --frames "${FRAMES:-10000}"
  run_cell_list "$cells_arg" "${TASK:-Door}" "${FRAMES:-10000}" \
    "${EVAL_EVERY_FRAMES:-${FRAMES:-10000}}" "${EVAL_EPISODES:-2}" "$out_arg" "$work_arg"
  exit "$?"
fi

code="${1:?payload archive}"
result="${2:?result archive}"
asset_archive="${3:-}"
out="/tmp/native-out"
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
  local device
  for device in $(echo "${OFFLINE_EVAL_DEVICES:-cuda}" | tr ',' ' '); do
    echo "=== NATIVE_OFFLINE_EVAL_BEGIN device=$device checkpoint=$(basename "$snapshot") ==="
    set +e
    python3 scripts/eval_grid.py \
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
      --out "$output_dir/offline_eval_$device.jsonl" 2>&1 | tee -a "$output_dir/training.log"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ "$rc" -eq 0 ]]; then
      echo "=== NATIVE_OFFLINE_EVAL_COMPLETED device=$device ==="
    else
      echo "=== NATIVE_OFFLINE_EVAL_FAILED device=$device rc=$rc ===" >&2
      status=1
    fi
  done
  return "$status"
}

cells="${CELLS:-${BASELINES:-${BASELINE:-drqv2}}}"
frames="${FRAMES:-10000}"
task="${TASK:-Door}"
# [Claude 2026-09-02 18:30 MSK: NATIVE_PRODUCTION applies the settings families.json records for
# this family -- the cap, the cadences, the preserve cadence -- instead of asking the job config to
# repeat them. Explicit environment still wins, so a job can deviate deliberately; what it can no
# longer do is deviate by omission. A declared setting with no lever prints
# NATIVE_PRODUCTION_UNAPPLIED rather than being silently dropped.]
apply_production_settings "$cells"
eval_every="${EVAL_EVERY_FRAMES:-$frames}"
eval_episodes="${EVAL_EPISODES:-2}"
# [Claude 2026-09-02 11:35 MSK: the checkpoint cadence, separate from the evaluation cadence. It
# defaults to the whole budget -- save once, at the end -- and a production job sets it to keep the
# budget curve a long run writes anyway.]
save_every="${SAVE_EVERY_FRAMES:-$frames}"
seed="${SEED:-1}"
export DEFAULT_SEED="$seed"
export NATIVE_CELLS="$cells"
export NATIVE_EVAL_EVERY_FRAMES="$eval_every"
export NATIVE_EVAL_EPISODES="$eval_episodes"
export NATIVE_SAVE_EVERY_FRAMES="$save_every"
# [Claude 2026-09-02 06:45 MSK: the runner and the payload are separate job inputs and can drift.
# Refuse a payload built for an older runner here, immediately after extraction, rather than
# after a full bootstrap.]
python3 datasphere/native/contract.py verify-payload --archive "$code" --require-runner-contract 10
# [Claude 2026-09-02 19:05 MSK: as early as the payload allows -- after the contract check, which
# is what makes family.py trustworthy, and before the family dependency installs and the clone.
# A budget below a family's floor trains nothing and fails at retain(), which is otherwise
# discovered only after the whole bootstrap and a full evaluation have been billed.]
python3 "$FAMILY_TOOL" check-budget --cells "$cells" --frames "$frames"
# [Claude 2026-09-02 10:35 MSK: refuse a job whose families cannot share one python environment,
# before the bootstrap rather than after it.]
python3 "$FAMILY_TOOL" check-co-schedulable --cells "$cells"
python3 -m pip install --upgrade pip
# [Claude 2026-09-02 10:50 MSK: a family that cannot share a job may also need a base requirement
# left out. CTRL is a JAX baseline and never imports torch, and jax[cuda12]'s cudnn 9 and torch's
# pinned cudnn 8.9.2.26 have no common version -- so a CTRL job installs the base requirements with
# torch filtered out, and every other job installs them unchanged.]
python3 "$FAMILY_TOOL" filtered-requirements --cells "$cells" --requirements requirements-native.txt > /tmp/requirements-for-this-job.txt
python3 -m pip install -r /tmp/requirements-for-this-job.txt
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
# the runner applies P1-P18 itself immediately below, and the vendored working copy has them
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
python3 -m pip install --no-deps -e RL-ViGen-upstream/third_party/robosuite
python3 -m pip install --no-deps -e RL-ViGen-upstream/envs/robosuiteVGB
python3 -m pip check
# [Codex 2026-09-01 10:51 MSK: preserve resolved versions so remote results remain reproducible despite transitive package resolution]
python3 - <<'PY' > "$out/resolved_packages.json"
import importlib.metadata
import json

print(json.dumps({dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions() if dist.metadata.get("Name")}, sort_keys=True))
PY
python3 setup/apply_patches.py
python3 setup/apply_patches.py --check
# [Codex 2026-09-01 15:20 MSK: verify the source-hashed exceptional import closure before any wrapper import or timed calibration]
python3 datasphere/native/contract.py verify-robosuite-closure --source RL-ViGen-upstream --requirements requirements-native.txt --closure datasphere/native/robosuite-import-closure.json
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl WANDB_MODE=offline WANDB_DISABLED=true
export PYTHONPATH="$work/RL-ViGen-upstream:$work/RL-ViGen-upstream/algos:$work/RL-ViGen-upstream/envs/robosuiteVGB:$work/runnable/_shim"
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
  if [[ -z "$asset_archive" ]]; then
    echo "=== NATIVE_PLACES365_MISSING these cells need the Places365 val set and no asset archive was passed ===" >&2
    echo "    cells: $cells" >&2
    echo "    add a 4th positional argument and a places365-val.tgz job input, plus" >&2
    echo "    PLACES365_EXPECTED_COUNT and PLACES365_EXPECTED_SHA256 in the environment." >&2
    exit 1
  fi
  asset_dir="$work/places365-val"
  mkdir -p "$asset_dir"
  tar --no-same-owner -xzf "$asset_archive" -C "$asset_dir"
  asset_images="$asset_dir/val/images"
  python3 datasphere/native/contract.py check-asset --asset "$asset_images" --expected-count "${PLACES365_EXPECTED_COUNT:?}" --expected-sha256 "${PLACES365_EXPECTED_SHA256:?}"
  dataset_root="$work/places365-root"
  mkdir -p "$dataset_root/places365_standard"
  ln -s "$asset_dir/val" "$dataset_root/places365_standard/val"
  python3 datasphere/native/configure_places365_val.py --repo RL-ViGen-upstream --dataset-root "$dataset_root"
  python3 datasphere/native/configure_places365_val.py --repo RL-ViGen-upstream --dataset-root "$dataset_root" --check
  # [Claude 2026-09-02 04:20 MSK: soda loads the overlay through dmc_gb's own copy of the same
  # loader, so it needs the same val pinning or the two families would overlay from different
  # image distributions. `data` is where dmc_gb's launcher symlinks its dataset root from.]
  ln -sfn "$dataset_root" "$work/data"
  if [[ -d "$work/runnable/dmc_gb" ]]; then
    python3 datasphere/native/configure_places365_val.py --repo runnable/dmc_gb --dataset-root "$dataset_root" --flavor dmc_gb
    python3 datasphere/native/configure_places365_val.py --repo runnable/dmc_gb --dataset-root "$dataset_root" --flavor dmc_gb --check
  fi
  python3 - "$dataset_root/places365_standard/val" <<'PY'
import pathlib
import sys
import utils

utils._load_places(batch_size=1, image_size=84, num_workers=0)
actual = pathlib.Path(utils.places_dataloader.dataset.root).resolve()
expected = pathlib.Path(sys.argv[1]).resolve()
if actual != expected:
    raise RuntimeError(f'Places365 loader selected {actual}, expected {expected}')
PY
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

cell_status=0
if [[ "${PREFLIGHT_ONLY:-0}" == "1" ]]; then
  : > "$out/training.log"
  export FINAL_EVALUATION_MARKER=""
  export FAILED_CELLS=""
elif [[ -n "${OFFLINE_EVAL_SNAPSHOT:-}" ]]; then
  run_offline_eval "$out" || cell_status=1
  export FINAL_EVALUATION_MARKER="NATIVE_OFFLINE_EVAL_COMPLETED"
  export FAILED_CELLS=""
else
  run_cell_list "$cells" "$task" "$frames" "$eval_every" "$eval_episodes" "$out" "$work" || cell_status=1
  export FINAL_EVALUATION_MARKER="NATIVE_FINAL_EVALUATION_COMPLETED frame=$frames"
fi
# [Claude 2026-09-02 00:50 MSK: one manifest entry per baseline. A single job now carries several
# calibrations, so a single top-level `baseline`/`snapshot_retained` pair could no longer say which
# run it described.]
python3 - <<'PY' > "$out/run_manifest.json"
import json
import os
from pathlib import Path

OUT = Path("/tmp/native-out")
preflight_only = os.environ.get("PREFLIGHT_ONLY", "0") == "1"
requested = [spec.strip() for spec in os.environ.get("NATIVE_CELLS", "").split(",") if spec.strip()]
failed = [name for name in os.environ.get("FAILED_CELLS", "").split() if name.strip()]
default_seed = os.environ.get("SEED", "1")


def identify(spec):
    baseline, _, seed = spec.partition(":")
    return baseline, (seed or default_seed)


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def rows(path):
    return max(0, len(path.read_text().splitlines()) - 1) if path.exists() else 0


cells = {}
for spec in requested:
    baseline, seed = identify(spec)
    identifier = f"{baseline}-s{seed}"
    directory = OUT / "cells" / identifier
    log = directory / "training.log"
    snapshot = directory / "snapshot.pt"
    marker = os.environ.get("FINAL_EVALUATION_MARKER") or ""
    cells[identifier] = {
        "baseline": baseline,
        "seed": seed,
        "completed": identifier not in failed and directory.exists(),
        "final_evaluation_marker": marker if (log.exists() and marker and marker in log.read_text(errors="replace")) else None,
        "snapshot_retained": snapshot.exists() and snapshot.stat().st_size > 0,
        "snapshot_bytes": snapshot.stat().st_size if snapshot.exists() else 0,
        "train_curve_rows": rows(directory / "train.csv"),
        "eval_curve_rows": rows(directory / "eval.csv"),
        "resource_samples": read_json(directory / "resources.json"),
    }

json.dump({
    "command": "runnable/_launch/rlvigen.sh",
    "cells_requested": requested,
    "cells_failed": failed,
    "cells": cells,
    "concurrent": os.environ.get("NATIVE_CONCURRENT") == "1",
    "baseline": identify(requested[0])[0] if len(requested) == 1 else None,
    "frames": os.environ.get("FRAMES", "10000"),
    "eval_every_frames": os.environ.get("NATIVE_EVAL_EVERY_FRAMES"),
    "eval_episodes": os.environ.get("NATIVE_EVAL_EPISODES"),
    "extra_overrides": os.environ.get("NATIVE_EXTRA_OVERRIDES") or None,
    "eval_scenes": os.environ.get("RLVIGEN_EVAL_SCENES") or "0,1,2,3,4,5,6,7,8,9",
    "cell_timeout_seconds": os.environ.get("CELL_TIMEOUT_SECONDS") or None,
    "seed": default_seed,
    "preflight_only": preflight_only,
    "final_evaluation_marker": os.environ.get("FINAL_EVALUATION_MARKER") or None,
    "snapshot_retained": bool(cells) and all(entry["snapshot_retained"] for entry in cells.values()),
    "payload_sha256": os.environ["PAYLOAD_SHA256"],
    "asset_sha256": os.environ["ASSET_SHA256"],
    "resolved_packages": read_json(OUT / "resolved_packages.json"),
    "environment": read_json(OUT / "environment.json"),
    "egl": read_json(OUT / "egl.json"),
    "resource_high_water_source": "GNU time -v in each cells/<baseline>-s<seed>/training.log",
}, (OUT / "run_manifest.json").open("w"), sort_keys=True)
PY
# [Claude 2026-09-02 12:45 MSK: one common record per measurement, derived from each family's own
# logs after they are written. Additive and lossless -- every native file is retained unchanged and
# stays the source of truth -- and training-unaffecting by construction, because it runs here. It
# makes `regime` and `scene_set` explicit on every row, which is what stops a cross-baseline table
# from putting a ten-scene average and a single-scene number in the same column.]
python3 datasphere/native/normalize_curves.py --directory "$out" --output "$out/records.jsonl" || \
  echo "records.jsonl could not be derived; the native curves are unaffected" >&2

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
# Additive: result.tgz is unchanged and still contains records.jsonl. RECORDS_OUT is optional, so
# every existing configuration means exactly what it meant.
#
# [Claude 2026-09-04] OFFLINE-EVAL JOBS WRITE THEIR RECORDS SOMEWHERE ELSE, and the first version
# of this block did not know that. `normalize_curves.py` reads training CELLS and writes
# records.jsonl; an eval-only job has no cells, so records.jsonl is legitimately empty while the
# eval rows sit in offline_eval_<device>.jsonl (written at the --out of the eval invocation above).
# Result: bt1ip5f8c6mqqm7fd2bn returned an EMPTY records.jsonl and announced NATIVE_RECORDS_EMPTY
# while its four eval records rode home inside result.tgz -- the expensive artefact this block
# exists to let the caller skip. The failure was silent and the job otherwise succeeded.
#
# Both sources are concatenated because both are records in the same schema; an eval-only job
# contributes only the second, a training job only the first, and a job that does both gets both.
if [[ -n "${RECORDS_OUT:-}" ]]; then
  : > "$RECORDS_OUT"
  # An `if` rather than `[[ -s "$src" ]] && cat ...`: under `set -e` a false test as the LAST
  # command of a loop body is the exit status of the body, and that is how two jobs died silently
  # earlier in this project. An unmatched glob simply fails `-s` and is skipped.
  for src in "$out/records.jsonl" "$out"/offline_eval_*.jsonl; do
    if [[ -s "$src" ]]; then
      cat "$src" >> "$RECORDS_OUT"
    fi
  done
  if [[ -s "$RECORDS_OUT" ]]; then
    echo "=== NATIVE_RECORDS_EMITTED $(wc -l < "$RECORDS_OUT") rows -> $(basename "$RECORDS_OUT") ==="
  else
    echo "=== NATIVE_RECORDS_EMPTY no records were derived; the archive still holds the native curves ===" >&2
  fi
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
echo "native probe completed successfully"
