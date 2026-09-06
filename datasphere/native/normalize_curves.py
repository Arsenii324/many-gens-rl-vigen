"""One common record per measurement, derived from each family's own logs.

[Claude 2026-09-02 12:30 MSK] The families are not going to agree on a logger and should not be
made to: `train.csv` from RL-ViGen's logger and `train.log` from dmcontrol-generalization-benchmark
record different columns, and `actor_ent` and `actor_logprob` are different quantities that happen
to answer the same question. Forcing one schema *inside* the trainers would either drop columns or
invent them, and it would be a change to code that runs during training.

So the envelope is built **downstream, from the retained artifacts, after the run**. It is:

  * additive — every native file is retained unchanged and stays the source of truth;
  * training-unaffecting by construction, because it runs after the job;
  * lossless — the whole native row is carried in `native`, so nothing is thrown away;
  * honest about axes — one native evaluation row usually becomes TWO records, because RL-ViGen's
    eval row reports the eval regime averaged over ten scenes AND the train regime on scene 0, and
    a table that put those in one column would be comparing different measurements.

The fields every record carries:

    schema, cell, baseline, family, seed, phase, frame, regime, scene_set,
    episodes, episode_return_mean, episode_return_sd, success_rate, conventions, native,
    evaluator_scope, evaluator_scope_revision, evaluator_measurement_revision

`regime` and `scene_set` are the two axes that make cross-baseline comparison meaningful or
meaningless, so neither is ever left implicit: `scene_set` is "0-9" only where the measurement
really swept ten scenes, and "0" where it did not.

`conventions` (schema 2) carries the per-baseline choices that do not vary within a run and are
therefore the easy ones to forget: time-limit handling, render size, frame stack, and the shape of
whatever training-time evaluation the baseline has. Two rows from two baselines are not comparable
without them, and until now nothing in the data said so.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path


SCHEMA = 2
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# The per-baseline conventions that decide what a number MEANS, carried on every record.
#
# `regime` and `scene_set` vary per measurement and are already fields. These do not vary within a
# baseline -- which is exactly why they get forgotten, and why a reader comparing two rows from
# two baselines cannot see them. C1 is the case in point: nine baselines zero the value bootstrap
# on a task where every episode ends by time limit and three bootstrap through it, so their value
# targets are biased relative to each other, and no column in any native log says so.
#
# `eval_policy_mode` was added 2026-09-02 without a schema bump. It records the action rule used by
# the evaluator that produced the row, not merely whether the original repository shipped a
# suitable evaluator. Four paths sample (`idaac`, `ppg`, `ibac_sni`, `ctrl`) and eight take the
# distribution's mode. Two runs whose returns differ because one sampled and one did not are not
# comparable, and the row must say which happened.
#
# Duplicated from rlgen/protocol.py rather than imported: `rlgen` is not a payload member, so this
# file cannot import it on the container. tests/test_record_conventions.py asserts the two agree,
# which is the same anchor-and-check pattern scripts/audit_eval_cadence.py uses.
CONVENTIONS = {
    "drqv2":    {"time_limit_handling": "terminal",  "render_size": 84,  "frame_stack": 3,
                 "training_time_eval": "periodic-multiscene",
                 "eval_policy_mode": "mode"},
    "svea":     {"time_limit_handling": "terminal",  "render_size": 84,  "frame_stack": 3,
                 "training_time_eval": "periodic-multiscene",
                 "eval_policy_mode": "mode"},
    "sgqn":     {"time_limit_handling": "terminal",  "render_size": 84,  "frame_stack": 3,
                 "training_time_eval": "periodic-multiscene",
                 "eval_policy_mode": "mode"},
    "curl":     {"time_limit_handling": "terminal",  "render_size": 84,  "frame_stack": 3,
                 "training_time_eval": "periodic-multiscene",
                 "eval_policy_mode": "mode"},
    "drq":      {"time_limit_handling": "terminal",  "render_size": 84,  "frame_stack": 3,
                 "training_time_eval": "periodic-multiscene",
                 "eval_policy_mode": "mode"},
    "rad":      {"time_limit_handling": "bootstrap", "render_size": 100, "frame_stack": 3,
                 "training_time_eval": "periodic-two-regimes",
                 "eval_policy_mode": "mode"},
    "soda":     {"time_limit_handling": "bootstrap", "render_size": 100, "frame_stack": 3,
                 "training_time_eval": "periodic-two-regimes",
                 "eval_policy_mode": "mode"},
    "alda":     {"time_limit_handling": "bootstrap", "render_size": 64,  "frame_stack": 3,
                 "training_time_eval": "periodic-three-regimes",
                 "eval_policy_mode": "mode"},
    "idaac":    {"time_limit_handling": "terminal",  "render_size": 64,  "frame_stack": 1,
                 "training_time_eval": "periodic-single-regime",
                 "eval_policy_mode": "sample"},
    "ppg":      {"time_limit_handling": "terminal",  "render_size": 64,  "frame_stack": 1,
                 "training_time_eval": "none",
                 "eval_policy_mode": "sample"},
    "ibac_sni": {"time_limit_handling": "terminal",  "render_size": 64,  "frame_stack": 1,
                 "training_time_eval": "none",
                 "eval_policy_mode": "sample"},
    "ctrl":     {"time_limit_handling": "terminal",  "render_size": 64,  "frame_stack": 1,
                 "training_time_eval": "continuous",
                 "eval_policy_mode": "sample"},
}


def rows_of_csv(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def rows_of_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _recorded_on() -> dict:
    """Where the PROCESS WRITING this record is running. Not always where the number was measured.

    [C95] A container-trained checkpoint evaluated on this laptop reads 2.94-3.41 where the same
    file reads 41.66-50.73 in the container, and RL-ViGen's own eval loop fails locally exactly as
    ours does -- so the machine is part of the measurement and a record that does not name it
    cannot be audited later. Stamped into `native` rather than the top level so the schema stays 2
    and every existing reader keeps working.

    **The honest caveat, because the field would otherwise be read as more than it is**: this
    describes the writer, and the writer is the measurer only when the record is produced by an
    evaluation in the same process -- `eval_grid.py`, which is the case C95 is about. When
    `normalize_curves` is run locally over a result archive fetched from a job, the numbers were
    measured in the container and only the transcription happened here. `mujoco_gl` is the field
    that distinguishes them in practice: an evaluation this laptop performed carries `glfw`.
    """
    import os
    import platform as _platform

    return {
        "recorded_on": {
            "host": _platform.node(),
            "system": _platform.system(),
            "machine": _platform.machine(),
            "mujoco_gl": os.environ.get("MUJOCO_GL"),
        }
    }


def record(**fields) -> dict:
    base = {
        "schema": SCHEMA,
        "phase": "eval",
        "regime": None,
        "scene_set": None,
        "episodes": None,
        "episode_return_mean": None,
        "episode_return_sd": None,
        "success_rate": None,
        "checkpoint_sha256": None,
        "evaluator_revision": None,
        # Static evaluator_revision proves payload/source closure identity. These distinct fields
        # prove the resolved measurement scope; pooling must use evaluator_measurement_revision.
        "evaluator_scope": None,
        "evaluator_scope_revision": None,
        "evaluator_measurement_revision": None,
        "conventions": None,
        "native": {},
    }
    base.update(fields)
    run_provenance = base.pop("_run_provenance", None)
    # A record that cannot state its own conventions says so, rather than carrying a default that
    # would read as a measured fact.
    base["conventions"] = CONVENTIONS.get(base.get("baseline"))
    # Provenance first, caller's native blob second: a family that wants to say something about
    # `recorded_on` itself should win over the automatic stamp.
    automatic = _recorded_on()
    if run_provenance:
        automatic["run_provenance"] = run_provenance
    base["native"] = {**automatic, **(fields.get("native") or {})}
    return base


def declared_eval_episodes() -> int | None:
    """The N behind an evaluation mean, where it is knowable and OURS to know.

    [Claude 2026-09-03] Three of the first seven pre-production rows had a blank episode count, and
    the blanks did not share a cause -- which matters more than the blanks did:

    - `dmc_gb` takes `--eval_episodes {eval_episodes}` from families.json, so the runner's
      `NATIVE_EVAL_EPISODES` IS its N and stamping it is a fact, not an inference.
    - `alda` takes no eval flag at all. Its N is `alda_trainer.py:74`'s `n_eval_episodes: int = 10`
      -- the trainer's own default, which happens to equal ours. Recorded with that provenance,
      because a number that agrees by coincidence must not be read as a number we controlled.
    - `ctrl` has no N. It reports a trailing window, and stamping one would assert a fixed-policy
      evaluation that never happened -- the precise error `audit_comparability_seam.py`'s estimator
      axis exists to prevent. It stays blank, deliberately.

    A blank is therefore meaningful in this record set, and so is a filled value's `native`
    provenance. `scripts/audit_comparability_seam.py` says N "is precision, not quantity"; that is
    true only once N is known, and for two families it was not.
    """
    import os
    raw = os.environ.get("NATIVE_EVAL_EPISODES")
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def read_rlvigen(cell: Path, context: dict) -> list[dict]:
    """RL-ViGen's eval row is two measurements, and they are on different axes.

    `episode_reward`/`success_rate` are the eval regime averaged over the ten certified scenes
    (patch P14); `train_regime_reward`/`train_regime_success` are the train regime on scene 0 and
    are the retention denominator. Emitting them as one row would be the comparability error the
    whole project exists to avoid.
    """
    out = []
    eval_path = cell / "eval.csv"
    if eval_path.is_file():
        for row in rows_of_csv(eval_path):
            frame = number(row.get("frame"))
            out.append(record(**context, phase="eval", frame=frame,
                              regime=context.get("_eval_regime", "eval-easy"), scene_set="0-9",
                              episode_return_mean=number(row.get("episode_reward")),
                              success_rate=number(row.get("success_rate")), native=row))
            if "train_regime_reward" in row:
                out.append(record(**context, phase="eval", frame=frame,
                                  regime="train", scene_set="0",
                                  episode_return_mean=number(row.get("train_regime_reward")),
                                  success_rate=number(row.get("train_regime_success")), native=row))
    train_path = cell / "train.csv"
    if train_path.is_file():
        for row in rows_of_csv(train_path):
            out.append(record(**context, phase="train", frame=number(row.get("frame")),
                              regime="train", scene_set="0", episodes=1,
                              episode_return_mean=number(row.get("episode_reward")), native=row))
    return out


def read_dmc_gb(cell: Path, context: dict) -> list[dict]:
    """Both of dmc_gb's evaluation columns are ONE scene, which is the declared difference from
    RL-ViGen's ten-scene average and must not be pooled with it."""
    out = []
    eval_path = cell / "eval.log"
    if eval_path.is_file():
        for row in rows_of_jsonl(eval_path):
            frame = number(row.get("step"))
            out.append(record(**context, phase="eval", episodes=declared_eval_episodes(), frame=frame, regime="train", scene_set="0",
                              episode_return_mean=number(row.get("episode_reward")),
                              success_rate=number(row.get("success_rate")), native=row))
            if "episode_reward_test_env" in row:
                out.append(record(**context, phase="eval", episodes=declared_eval_episodes(), frame=frame,
                                  regime=context.get("_eval_regime", "eval-easy"), scene_set="0",
                                  episode_return_mean=number(row.get("episode_reward_test_env")),
                                  success_rate=number(row.get("success_rate_test_env")), native=row))
    train_path = cell / "train.log"
    if train_path.is_file():
        for row in rows_of_jsonl(train_path):
            out.append(record(**context, phase="train", frame=number(row.get("step")),
                              regime="train", scene_set="0", episodes=1,
                              episode_return_mean=number(row.get("episode_reward")), native=row))
    return out


def read_idaac(cell: Path, context: dict) -> list[dict]:
    """IDAAC's evaluator builds one env in the eval regime and collects ten episodes."""
    out = []
    for path in cell.glob("progress-*.csv"):
        for row in rows_of_csv(path):
            out.append(record(**context, phase="eval",
                              frame=number(row.get("train/total_num_steps")),
                              regime=context.get("_eval_regime", "eval-easy"), scene_set="0",
                              episodes=10,
                              episode_return_mean=number(row.get("test/mean_episode_reward")),
                              success_rate=number(row.get("test/success_rate")), native=row))
    return out


ALDA_LINE = re.compile(r"alda: (eval/[a-z_]+): ([-\d.]+)")
ALDA_STEP = re.compile(r"alda: (?:env_steps|step)[:= ]+(\d+)")
ALDA_REGIME = {"": "train", "_distracting": "eval-hard", "_color": "eval-easy"}


# alda passes no eval flag; this is `alda_trainer.py:74` `n_eval_episodes: int = 10`,
# its OWN default, which coincides with ours. See declared_eval_episodes().
ALDA_EVAL_EPISODES = 10


def read_alda(cell: Path, context: dict) -> list[dict]:
    """ALDA writes no csv and no tensorboard; its console log is its curve.

    It is also the only family that reports three regimes in one place, and they are its own
    regimes -- `distracting` and `color` are dmcontrol-generalization-benchmark's names, mapped
    here to the nearest RL-ViGen regime and labelled as a mapping rather than an identity.
    """
    log = cell / "training.log"
    if not log.is_file():
        return []
    text = ANSI.sub("", log.read_text(errors="replace"))
    out = []
    # The frame, from the checkpoint's own name, before the log is read at all.
    #
    # ALDA_STEP expects the logger prefix (`alda: env_steps ...`) and ALDA does not emit one at
    # the end of a run, so a completed 2,560-frame cell produced three correct records with
    # `frame: None` -- a row whose x-axis is unknown, which is exactly what eval_grid.py refuses
    # to emit. `save_checkpoint` names the file `sac_<env>_step_<frame>.pt` and `retain` fails the
    # cell without it, so the filename is both authoritative and guaranteed present. The log scan
    # below still runs and still wins where it finds something, because a mid-run curve has steps
    # the terminal filename does not.
    frame = None
    # `retain` copies the checkpoint to `snapshot.pt` and records where it came from, so the
    # original name -- `sac_<env>_step_<frame>.pt` -- survives only in retained.json. Reading the
    # cell directory for the glob finds nothing, which is how the first attempt at this still
    # produced `frame: None`.
    manifest = cell / "retained.json"
    if manifest.is_file():
        try:
            source = json.loads(manifest.read_text()).get("checkpoint_source", "")
        except (json.JSONDecodeError, OSError):
            source = ""
        stem = Path(source).stem.rsplit("_step_", 1)
        if len(stem) == 2 and stem[1].isdigit():
            frame = float(stem[1])
    pending: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        step = ALDA_STEP.search(line)
        if step:
            frame = float(step.group(1))
        match = ALDA_LINE.search(line)
        if not match:
            continue
        key, value = match.group(1), float(match.group(2))
        suffix = ""
        for candidate in ("_distracting", "_color"):
            if key.endswith(candidate):
                suffix = candidate
        metric = key[len("eval/"):]
        bucket = pending.setdefault(suffix, {})
        bucket[metric] = value
    for suffix, bucket in pending.items():
        returns = next((v for k, v in bucket.items() if k.startswith("episode_reward")), None)
        success = next((v for k, v in bucket.items() if k.startswith("success_rate")), None)
        out.append(record(**context, phase="eval", episodes=ALDA_EVAL_EPISODES, frame=frame,
                          regime=ALDA_REGIME.get(suffix, suffix.lstrip("_")), scene_set="0",
                          episode_return_mean=returns, success_rate=success,
                          native={"suffix": suffix or "(none)", **bucket},
                          regime_mapping_note="alda's own regime names, mapped to the nearest RL-ViGen regime"))
    return out


def read_ppg(cell: Path, context: dict) -> list[dict]:
    out = []
    last_frame = None
    progress = cell / "progress.csv"
    if progress.is_file():
        for row in rows_of_csv(progress):
            # [Claude 2026-09-04] `Misc/InteractCount` FIRST, because it is the column this repo
            # actually writes. The two names below appear in other PPG-lineage forks and neither
            # exists in `phasic_policy_gradient/log_save_helper.py`'s output, so until today EVERY
            # ppg training record carried `frame: null` -- a curve with no x-axis, which does not
            # look like a defect in a record set, it looks like a field nobody filled. Found by
            # reading a returned progress.csv rather than by any test.
            #
            # AXIS CAVEAT, not resolved here: this counts environment interactions and advances in
            # a 2048 quantum (2048, 4096, ... -- which is also why a requested 2560 executes 4096).
            # Whether one InteractCount equals one `frame` as the RL-ViGen five count them, given
            # action_repeat, is a comparability question this project answers per axis and NOT by
            # assuming two similarly-named counters are one quantity.
            frame = number(row.get("Misc/InteractCount") or row.get("misc/total_timesteps")
                           or row.get("total_timesteps"))
            out.append(record(**context, phase="train", frame=frame, regime="train",
                              scene_set="0",
                              episode_return_mean=number(row.get("EpRewMean") or row.get("eprewmean")),
                              native=row))
            if frame is not None:
                last_frame = frame
    log = cell / "training.log"
    if log.is_file():
        text = ANSI.sub("", log.read_text(errors="replace"))
        match = re.search(r"episode_reward mean/median\s*:\s*([-\d.]+)", text)
        success = re.search(r"success_rate\s*:\s*([-\d.]+)", text)
        episodes = re.search(r"episodes=(\d+)", text)
        if match:
            # [Claude 2026-09-04] The eval frame is INFERRED, and the inference is stated: ppg has
            # no training-time evaluator, so `runnable/_launch/ppg_eval.py` runs once after training
            # finishes and the policy it measures is the endpoint. So the last training row's
            # InteractCount is this record's frame. Left as `null` before today, which put ppg's
            # only eval number on no x-axis at all -- unplottable, and indistinguishable from a
            # field nobody filled.
            out.append(record(**context, phase="eval", frame=last_frame,
                              regime=context.get("_eval_regime", "eval-easy"), scene_set="0",
                              episodes=int(episodes.group(1)) if episodes else None,
                              episode_return_mean=float(match.group(1)),
                              success_rate=float(success.group(1)) if success else None,
                              native={"source": "runnable/_launch/ppg_eval.py stdout"},
                              action_note="ppg's evaluator SAMPLES from the policy; this repository has no deterministic-action path"))
    return out


# [Claude 2026-09-03] `ibac_sni`'s evaluator prints ONE line and it is not a CSV row, so until
# today this reader emitted 79 train records and zero eval records -- the cell trained, evaluated
# and reported `SR 0.0000`, and none of it reached the record set. The pre-production table caught
# it (`scripts/preprod_table.py`), which is what that table exists for: an R7 break in the
# RECORDING path looks exactly like a baseline that scored nothing.
#
#   F 5000.0 | FPS 59 | D 84 | R:muσmM 1.74 1.47 0.71 5.73 | F:muσmM 500.0 0.0 500.0 500.0 | SR 0.0000
#
# It is distinguishable from a training line because those begin `U <update> | F ...`. Episode
# count is the total frame figure over the per-episode mean, since the evaluator reports no count.
IBAC_EVAL_LINE = re.compile(
    r"^F\s+([\d.]+)\s*\|\s*FPS\s+\d+\s*\|\s*D\s+\d+\s*\|\s*"
    r"R:\S+\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\|\s*"
    r"F:\S+\s+([\d.]+)\s+\S+\s+\S+\s+\S+\s*\|\s*SR\s+([\d.]+)",
    re.M)


def read_ibac_sni(cell: Path, context: dict) -> list[dict]:
    out = []
    path = cell / "log.csv"
    if path.is_file():
        for row in rows_of_csv(path):
            out.append(record(**context, phase="train", frame=number(row.get("frames")),
                              regime="train", scene_set="0",
                              episode_return_mean=number(row.get("rreturn_mean") or row.get("return_mean")),
                              native=row))
    log = cell / "training.log"
    if log.is_file():
        for match in IBAC_EVAL_LINE.finditer(log.read_text(errors="replace")):
            total_frames, mean, sd, low, high, ep_len, sr = (float(g) for g in match.groups())
            episodes = int(round(total_frames / ep_len)) if ep_len else None
            out.append(record(**context, phase="eval",
                              regime=os.environ.get("RLVIGEN_EVAL_MODE") or "eval-easy",
                              scene_set="0", episodes=episodes,
                              episode_return_mean=mean, episode_return_sd=sd,
                              success_rate=sr,
                              native={"return_min": low, "return_max": high,
                                      "episode_length_mean": ep_len,
                                      "source": "training.log evaluator line"}))
    return out


CTRL_LINE = re.compile(
    r"\[(\d+)\]\s*Eprew200:\s*([-\d.nan]+)\s*Eprew0:\s*([-\d.nan]+)\s*"
    r"SR_ID:\s*([-\d.nan]+)\s*SR_OOD:\s*([-\d.nan]+)")


def read_ctrl(cell: Path, context: dict) -> list[dict]:
    """CTRL measures a held-out regime ONLINE, on a parallel env set, during training.

    That is a different protocol from every other baseline's offline checkpoint grid, and it is
    the only held-out number CTRL can currently produce -- its shipped evaluator is procgen-only
    and discrete-action. Labelled `online` so it is never silently pooled with the others.
    """
    out = []
    for name in ("train_console.log", "training.log"):
        path = cell / name
        if not path.is_file():
            continue
        text = ANSI.sub("", path.read_text(errors="replace"))
        for frame, in_dist, out_dist, sr_id, sr_ood in CTRL_LINE.findall(text):
            out.append(record(**context, phase="eval", frame=float(frame), regime="train",
                              scene_set="0", episode_return_mean=number(in_dist),
                              success_rate=number(sr_id),
                              native={"Eprew200": in_dist, "SR_ID": sr_id},
                              measurement="online, during training"))
            out.append(record(**context, phase="eval", frame=float(frame),
                              regime=context.get("_eval_regime", "eval-easy"), scene_set="0",
                              episode_return_mean=number(out_dist), success_rate=number(sr_ood),
                              native={"Eprew0": out_dist, "SR_OOD": sr_ood},
                              measurement="online, during training"))
        break
    return out



# [Claude 2026-09-04] The metrics a baseline logs to W&B and NOWHERE else.
#
# `ctrl/train_ppo.py:277-293` builds a `metric_dict` -- its PPO and CTRL-specific losses -- and
# passes it to `wandb.log`. It never prints it. Its stdout carries exactly four numbers
# (`Eprew200`, `Eprew0`, `SR_ID`, `SR_OOD`), so no amount of log parsing recovers the rest, and
# `read_ctrl` accordingly emitted two native keys for a baseline that computes dozens.
#
# **`ctrl` is the only family this reaches today, and that was checked rather than assumed.** An
# earlier version of this note said `alda` was the same shape. Three things must line up and alda
# fails the first: it must call `wandb.log` (`runnable/_launch/alda.sh` passes `--use_wandb False`,
# so it writes no sink), `families.json` must retain `wandb_offline.jsonl` (ctrl lists it, alda does
# not), and the family's `artifact_root` must be where the shim writes, namely `run_dir` (ctrl's is
# `{run_dir}`; alda's is `{run_dir}/alda_robosuite_door/seed_{seed}`, a different directory).
#
# Nothing needed to change in either clone. `runnable/_shim/wandb.py` already writes every
# `wandb.log` call to `$run_dir/wandb_offline.jsonl` (that is what made it an offline sink rather
# than a fail-closed stub), so these numbers have been landing on disk in every cell and simply
# had no reader. This is the reader. Zero new deviation in a vendored tree, which is why it is
# preferred over teaching the two trainers to print.
#
# **Nothing here is mapped to a shared column.** Not `episode_return_mean`, not `success_rate`,
# even where a key looks like an obvious match: ctrl's `ep_return_200` IS `Eprew200`, a trailing
# window over ~200 episodes of successive policies, which COMPARABILITY_CONTRACT §5d already
# records as a different estimand from every other baseline's saved-policy evaluation. Promoting
# it to `episode_return_mean` would put that difference back underground one field at a time.
# Keys are kept verbatim, prefix and all, for the same reason: renaming is what makes two
# quantities look like one.
#
# Calls sharing a step are MERGED into one record. ctrl issues three `wandb.log` calls per
# iteration at the same step (the metric dict, then two return summaries); emitting three records
# would triple the row count and split one instant across rows that a reader would have to rejoin.
def read_wandb_sink(cell: Path, context: dict) -> list[dict]:
    """Every `wandb.log` call the shim captured, one record per step, keys verbatim."""
    path = cell / "wandb_offline.jsonl"
    if not path.is_file():
        return []
    by_step: dict = {}
    order: list = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue        # a partial final line from a killed process is not a reason to lose the rest
        if event.get("_event") != "log":
            continue
        data = event.get("data")
        if not isinstance(data, dict) or not data:
            continue
        # [Claude 2026-09-04] The step is not always the `step=` kwarg. `ctrl/train_ppo.py` issues
        # THREE wandb.log calls per iteration and passes `step=` on only the first; the other two
        # carry the same count as a DATA field named `<env_name>/step`. Reading only the kwarg
        # therefore produced three records per iteration -- the losses on one, `ep_return_200` and
        # `ep_return_all` on two unstepped others -- which is precisely the scattering this
        # function's merge exists to prevent, and it did it while the docstring said otherwise.
        # Verified against a real archive (bt1fer7809i7bpob7g2f): 6 records became 2.
        step = event.get("step")
        if step is None:
            for field, value in data.items():
                if field == "step" or field.endswith("/step"):
                    step = value
                    break
        key = step if step is not None else f"_unstepped{len(order)}"
        if key not in by_step:
            by_step[key] = {}
            order.append(key)
        by_step[key].update(data)
    out = []
    for key in order:
        step = key if not isinstance(key, str) else None
        out.append(record(**context, phase="native-metrics", frame=number(step),
                          regime=None, scene_set=None,
                          native={"wandb_step": step, **by_step[key]},
                          measurement="the baseline's OWN metric dict, captured from its wandb.log "
                                      "calls by runnable/_shim/wandb.py. Keys are verbatim and "
                                      "UNRECONCILED: a key here shares no axis with any other "
                                      "baseline's key of the same name unless shown to."))
    return out


READERS = {
    "rlvigen": read_rlvigen,
    "dmc_gb": read_dmc_gb,
    "idaac": read_idaac,
    "alda": read_alda,
    "ppg": read_ppg,
    "ibac_sni": read_ibac_sni,
    "ctrl": read_ctrl,
}


def normalize(result_root: Path, eval_regime: str = "eval-easy") -> list[dict]:
    manifest_path = result_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    run_provenance = {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if manifest_path.is_file() else None,
        "finalization_schema": manifest.get("finalization_schema"),
        "execution_kind": manifest.get("execution_kind"),
        "payload_sha256": manifest.get("payload_sha256"),
        "asset_sha256": manifest.get("asset_sha256"),
        "container_image": manifest.get("container_image"),
        "requirements_native_sha256": manifest.get("requirements_native_sha256"),
        "resolved_packages": manifest.get("resolved_packages"),
        "environment": manifest.get("environment"),
        "egl": manifest.get("egl"),
    }
    records: list[dict] = []
    cells_root = result_root / "cells"
    for cell in sorted(cells_root.glob("*")) if cells_root.is_dir() else []:
        if not cell.is_dir():
            continue
        entry = (manifest.get("cells") or {}).get(cell.name, {})
        baseline = entry.get("baseline") or cell.name.rsplit("-s", 1)[0]
        seed = entry.get("seed") or cell.name.rsplit("-s", 1)[-1]
        retained = cell / "retained.json"
        if retained.is_file():
            family = json.loads(retained.read_text())["family"]
        else:
            # [Claude 2026-09-02 12:40 MSK: archives produced before retain.json existed still
            # normalize -- the descriptor knows which family owns a baseline.]
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import family as family_module

            try:
                family = family_module.family_of(baseline)
            except Exception:
                continue
        if family not in READERS:
            continue
        context = {"cell": cell.name, "baseline": baseline, "family": family, "seed": seed,
                   "_eval_regime": eval_regime, "_run_provenance": run_provenance}
        # The family reader first, then the W&B sink, which is family-INDEPENDENT: it reads what
        # the shim captured regardless of who logged it, and returns nothing when the file is
        # absent. Two families use it today (`alda`, `ctrl`); any clone that starts logging is
        # picked up without a code change here.
        for row in list(READERS[family](cell, context)) + read_wandb_sink(cell, context):
            row.pop("_eval_regime", None)
            records.append(row)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True,
                        help="an extracted result archive")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--eval-regime", default="eval-easy")
    args = parser.parse_args(argv)

    records = normalize(args.directory.resolve(), args.eval_regime)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    if args.output:
        args.output.write_text(text)
    else:
        sys.stdout.write(text)
    print(f"{len(records)} records from {args.directory}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
