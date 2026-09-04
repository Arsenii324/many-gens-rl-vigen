#!/usr/bin/env bash
# Produce one table cell that is trustworthy end to end.
#
#   bash scripts/run_cell.sh drqv2 Door 7
#   bash scripts/run_cell.sh svea  Door 1
#
# The recipe is not obvious and each part was learned from a defect:
#
#   55k frames, not 40k -- train.py:309 saves a snapshot only at multiples of 50k steps, so
#     three healthy 40k runs produced no checkpoint at all (STAGES.md inventory).
#   not more than ~100k -- both runs that reached 120k diverged to NaN (C57), and 50k-100k is
#     the only interval that has ever yielded a finite checkpoint.
#   save_snapshot=True explicitly -- a 200k run reached 439.19 and saved nothing without it.
#   the frame watcher attached -- the replay buffer keeps only a run's ENDING
#     (replay_buffer.py:94), so provenance has to be captured live or not at all (C54, C58).
#
# Afterwards, check_checkpoint_finite.py must pass before any number is computed from the
# result: a diverged run writes a checkpoint of 7.4M NaNs and looks entirely ordinary.
set -euo pipefail

# The budget a baseline must actually be LAUNCHED with to obtain a checkpoint at `want`. See C77
# and the long comment at the save-cadence block below. Defined as a function with a query mode
# (`--effective-frames <baseline> <want>`) so `tests/test_run_cell_budget.py` drives this exact
# code rather than a copy of it -- a test that re-implements the rule cannot catch the rule being
# wrong, which is precisely how the claim this replaces survived.
effective_frames () {
  case "$1" in
    drqv2|svea|drq|sgqn|curl)
      if [ $(( $2 % 50000 )) -eq 0 ]; then echo $(( $2 + 5000 )); else echo "$2"; fi ;;
    *) echo "$2" ;;
  esac
}

if [ "${1:-}" = "--effective-frames" ]; then
  effective_frames "${2:?baseline}" "${3:?frames}"
  exit 0
fi

BASELINE="${1:-drqv2}"; TASK="${2:-Door}"; SEED="${3:-1}"; FRAMES="${4:-50000}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
# The cell directory does not carry the budget, because when this was written every cell ran at
# one. C73 made the budget an axis: a 100k re-run of a seed that already has a 50k cell would
# write its provenance frames into that cell's directory and leave two budgets indistinguishable
# inside one record. CELL_DIR overrides the name; the default is unchanged, so existing cells and
# the tests that read them are untouched.
OUT="$REPO/results/${CELL_DIR:-cell-${BASELINE}-${TASK}-seed${SEED}}"
mkdir -p "$OUT/frames"
PY="${PYTHON:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}"

# The match string is per family. `num_train_frames=` is a hydra override and appears only in
# RL-ViGen run paths; a clone never has it, so the watcher matched nothing, captured nothing and
# said nothing -- a clone cell came out with no provenance while the run reported success.
case "$BASELINE" in
  drqv2|svea|drq|sgqn|curl) MATCH="num_train_frames=${FRAMES}"; WITNESS=yes ;;
  alda)                     MATCH="alda";  WITNESS=yes ;;   # ReplayBuffer.save writes observations
  *)                        MATCH="";      WITNESS=no  ;;   # C58: no observation record exists
esac

if [ "$WITNESS" = yes ]; then
  "$PY" "$HERE/watch_training_frames.py" --out "$OUT/frames" --seconds 40000 --interval 0.15 \
        --match "$MATCH" > "$OUT/watcher.log" 2>&1 &
  W=$!
else
  echo "NOTE: $BASELINE keeps no observation record (C58), so this cell's training distribution"
  echo "      CANNOT be verified. The cell is still usable; it just carries unverified provenance."
  W=""
fi
# Live divergence watch (C79). A NaN-diverged run is not a network, and since `use_tb=True` was
# turned on its `train.csv` carries `actor_loss`/`critic_loss`, which go literally `nan` on the
# first bad update. The run that made this necessary was NaN at frame 7 000, 5.9 minutes in, and
# was allowed to continue for another 64. Attaching this by default is the whole fix: an
# instrument nobody remembers to start is not an instrument.
#
# It REPORTS, it does not kill -- see the script's own docstring for why -- so this costs the run
# nothing and the operator reads `$OUT/divergence.log`.
#
# Only the five natives are watchable: they write `exp_local/<date>/<time>_<overrides>/train.csv`
# with `num_train_frames=` in the directory name, which is what `--match` keys on. The other seven
# write elsewhere and in their own formats. Attaching it to them anyway would produce a watcher
# that matched nothing and stayed silent for the whole run -- and silence from a watcher reads
# exactly like a clean run. Saying so out loud is the honest version.
DW=""
case "$BASELINE" in
  drqv2|svea|drq|sgqn|curl)
    "$PY" "$HERE/watch_divergence.py" --match "num_train_frames=${FRAMES}" --interval 60 \
          --seconds 40000 > "$OUT/divergence.log" 2>&1 &
    DW=$!
    if [ "$BASELINE" = drq ]; then
      echo "NOTE: drq runs with use_tb=False, so its train.csv has no loss columns and the"
      echo "      divergence watch is BLIND to it (C79). It will say so rather than report"
      echo "      healthy. Gate on check_checkpoint_finite.py before using its checkpoint."
    fi ;;
  *)
    echo "NOTE: $BASELINE is not watched for divergence -- watch_divergence.py reads RL-ViGen's"
    echo "      exp_local train.csv, which only the five natives write (C79). Run"
    echo "      check_checkpoint_finite.py on its checkpoint before computing anything from it." ;;
esac

# Intermediate-snapshot preservation (C68/C77), attached PER RUN for the reason C84 records.
#
# The five natives save to one path and overwrite it, so a 105k run's 50k weights are destroyed
# when the 100k save lands. `preserve_intermediate_snapshot.py` copies them out, which is what
# turns each cell into a within-run 50k/100k comparison (C81).
#
# It used to be started by hand as one long-lived process with `--seconds 80000`. That window
# expired between batches, nothing announced it, and `drq`'s 3.1-hour cell came out with **no
# paired 50k point at all** -- unrecoverable without re-running it. **A watcher with a timeout is
# a watcher that stops watching.** Scoping it to the run, and to the run's own budget, removes the
# failure mode rather than lengthening the timeout: it starts when the run starts, dies with the
# trap below, and cannot silently outlive or under-live its subject.
PW=""
case "$BASELINE" in
  drqv2|svea|drq|sgqn|curl)
    if [ $(( FRAMES / 50000 )) -ge 2 ]; then
      "$PY" "$HERE/preserve_intermediate_snapshot.py" --match "num_train_frames=${FRAMES}" \
            --seconds 40000 > "$OUT/preserve.log" 2>&1 &
      PW=$!
    fi ;;
esac

trap '[ -n "$W" ] && kill $W 2>/dev/null; [ -n "$DW" ] && kill $DW 2>/dev/null; [ -n "$PW" ] && kill $PW 2>/dev/null; true' EXIT

# Per-baseline save cadence. C60: every default is at or above 100k steps, while 50k-100k is the
# only interval that has yielded a finite checkpoint (C57) -- so a run at our budgets saves
# nothing unless told otherwise, and the flag is different for every family. Passing these costs
# no deviation: each launcher forwards "$@" to the trainer.
SAVE_AT=$(( FRAMES / 2 ))

# C68: for the five RL-ViGen natives the save cadence is NOT settable. `train.py:309` saves at
# `global_step % int(5e4) == 0` and there is no end-of-run save (the one at :268 is inside
# `habi_eval`, the habitat path). So a native run at 55 000 frames saves at 50 000 and then trains
# 5 000 frames that are discarded -- which is what the four existing cells did, and why every one
# of them reports `trained_step=50000` from a `num_train_frames=55000` launch.
#
# THE PARAGRAPH THAT USED TO BE HERE WAS WRONG, and it cost a 3.5-hour run. It read: "The default
# is therefore 50000, not 55000: same checkpoint, ~9% less compute." It is not the same checkpoint.
# It is NO checkpoint. See C77.
#
# The save at :309 sits inside `if time_step.last():` at the TOP of the loop body, and the loop is
# `while train_until_step(self.global_step)` with `Until.__call__` returning `step < until`
# (utils.py:73). At the end of the episode that lands on step N, the while-test is evaluated FIRST,
# `N < N` is false, and the loop exits before the episode-end block -- so the save for step N never
# runs. A run launched at exactly N therefore saves at every multiple of 50k strictly below N, and
# never at N itself.
#
# Confirmed three ways, not inferred: `num_train_frames=100000` seed 7 ended at frame 99500 with
# `snapshot.pt` holding step=50000; the archived 120000-frame run DOES hold a step-100000
# snapshot; and every 55000-frame cell holds step=50000.
#
# So the budget must exceed the checkpoint you want by at least one episode (500 frames). This
# bumps it rather than warning, because a warning about a checkpoint that will not exist is read
# after the compute is already spent. SAVE_AT above is still meaningful for `rad`/`soda`
# (`--save_freq`) and `alda` (`checkpoint_n_steps`), whose cadences the trainer does accept.
if [ "$(effective_frames "$BASELINE" "$FRAMES")" != "$FRAMES" ]; then
  echo "!! ${FRAMES} is an exact multiple of 50000, and this baseline never saves at the step"
  echo "!! its loop stops on -- it would train ${FRAMES} frames and write NO checkpoint at"
  echo "!! ${FRAMES}. See C77. Raising the budget to $(effective_frames "$BASELINE" "$FRAMES")"
  echo "!! so the ${FRAMES} save is actually reached; the checkpoint reads trained_step=${FRAMES}."
  FRAMES="$(effective_frames "$BASELINE" "$FRAMES")"
else
  case "$BASELINE" in
    drqv2|svea|drq|sgqn|curl)
      echo "note: ${FRAMES} frames -> the checkpoint will read"
      echo "      trained_step=$(( FRAMES / 50000 * 50000 )); the last $(( FRAMES % 50000 )) frames are"
      echo "      trained and discarded. That tail is what makes the save reachable at all (C77)." ;;
  esac
fi

echo "=== $BASELINE/$TASK seed $SEED, ${FRAMES} frames, start $(date +%H:%M:%S) ==="
case "$BASELINE" in
  drq)
    # drq alone cannot run with TensorBoard on. algos/drq.py:328 logs
    # `dist.entropy()` under `if self.use_tb:`, and its `dist` is a SquashedNormal --
    # a torch TransformedDistribution, which does not implement entropy(). Turning tb on
    # (2026-08-20, for TASK.md R7 and C57 detection) therefore activated a latent upstream bug
    # and broke exactly one baseline. tb affects no number, so running drq without it costs the
    # artifact and nothing else; the asymmetry is disclosed rather than hidden.
    echo "NOTE: drq runs with use_tb=False -- algos/drq.py:328 calls entropy() on a"
    echo "      SquashedNormal, which torch does not implement. It produces no tensorboard log."
    bash "$REPO/runnable/_launch/rlvigen.sh" "$BASELINE" "$TASK" \
         num_train_frames="$FRAMES" seed="$SEED" save_snapshot=True use_tb=False ;;
  curl)
    # curl cannot run under the MPS shim at all -- it dies with "scatter: index -1", which the
    # register already documented and `smoke_all.sh` already worked around with device=cpu. I
    # rediscovered it by crashing two 55k runs first, having not grepped the register for the
    # error string. CPU is ~60x slower for conv work here, so a 55k curl cell is not feasible on
    # this machine: refuse it rather than burn a day producing nothing.
    echo "curl cannot run on MPS (scatter: index -1; see CONSTRUCTION.md and smoke_all.sh:15),"
    echo "and CPU is ~60x slower, so a ${FRAMES}-frame cell is not feasible here. Needs CUDA."
    exit 3 ;;
  drqv2|svea|sgqn)
    bash "$REPO/runnable/_launch/rlvigen.sh" "$BASELINE" "$TASK" \
         num_train_frames="$FRAMES" seed="$SEED" save_snapshot=True ;;
  rad|soda)
    bash "$REPO/runnable/_launch/dmc_gb.sh" "$BASELINE" "$TASK" "$SEED" \
         --save_freq "$SAVE_AT" --train_steps "$FRAMES" ;;
  alda)
    # NOT --save_freq: that flag lives in the vendored dmcontrol_generalization_benchmark copy,
    # which alda's entry point does not use. alda runs scripts/train.py against a spec, and its
    # real key is trainers/alda_trainer.py:73 `checkpoint_n_steps: int = 50_000`, saved at :614.
    # Overridden through the spec path, the syntax alda.sh's own usage line documents.
    bash "$REPO/runnable/_launch/alda.sh" \
         --spec.trainer.config.n_train_steps="$FRAMES" \
         --spec.trainer.config.checkpoint_n_steps="$SAVE_AT" ;;
  idaac)
    # Saves only at j == num_updates - 1, so the budget IS the cadence. No flag exists.
    bash "$REPO/runnable/_launch/idaac.sh" --seed "$SEED" ;;
  ibac_sni)
    bash "$REPO/runnable/_launch/ibac_sni.sh" ;;
  ppg)
    echo "ppg saves only when LogSaveHelper's ic_per_save > 0, which is not a CLI flag and is"
    echo "never set. No checkpoint is produced. See C60 option 2." ; exit 3 ;;
  ctrl)
    echo "ctrl cannot checkpoint: train_ppo.py:12 comments out the flax checkpoints import"
    echo "upstream. Its own evaluate_ppo.py restores what its trainer cannot write. See C60." ; exit 3 ;;
  *)
    echo "unknown baseline: $BASELINE" ; exit 2 ;;
esac 2>&1 \
  | grep -vE "UserWarning|warnings.warn|RuntimeWarning|cbd1|Hydra|hydra.cc|version_base|with initialize"
echo "=== done $(date +%H:%M:%S) ==="
sleep 3
N=$(ls "$OUT/frames" 2>/dev/null | wc -l | tr -d ' ')
echo "frames captured: $N"
if [ "$WITNESS" = yes ] && [ "$N" -eq 0 ]; then
  echo "PROVENANCE NOT CAPTURED. This baseline can be witnessed but nothing was recorded, so the"
  echo "cell's training distribution is UNVERIFIED. Do not report it as checked. Exit 4."
  exit 4
fi
