"""The protocol object: every setting that can move a number, in one hashable place.

THE RULE THIS FILE ENFORCES. A run is admissible only if it can state the protocol that produced
it, and two numbers may be compared only if their protocol hashes agree. Everything else in this
repo is arranged so that no protocol-determining value can live anywhere but here.

WHY IT IS THIS LONG. The previous implementation had a five-field Protocol
(`name, checkpoint_selection, time_limit_handling, distractor_dynamics, train_levels`) while
`action_repeat`, `frame_stack`, image size, episode count, eval scenes and the code commit were
hardcoded in the env wrapper and in argparse. The emitted card therefore omitted every field that
actually set the numbers, and asserted `checkpoint_selection: final` for runs that had no
checkpoint at all. It also carried `train_levels: 200`, a Procgen concept, into every RL-ViGen
card. See docs/REVIEW.md F13.

The test
`tests/test_contract.py::test_no_protocol_value_is_hardcoded_outside_this_module` keeps it honest.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any

SCHEMA_VERSION = 1

#: RL-ViGen robosuite visual regimes. `train` randomises nothing; the eval modes differ in WHICH
#: effects are switched on, not in the magnitude of any single effect -- the magnitudes are shared
#: constants upstream. So `easy < medium < hard` is a statement about the number of active
#: nuisance factors, and it does NOT imply the returns are rank-ordered. In the sibling project
#: only 3 of 12 checkpoints came out ordered easy >= medium >= hard.
MODES = ("train", "eval-easy", "eval-medium", "eval-hard")

TASKS = ("Door", "Lift")

#: Observation and episode geometry, defined ONCE. `rlgen/envs.py` imports these rather than
#: repeating them: a second copy of `84` is a second place the protocol can silently change, and
#: `tests/test_contract.py::test_no_protocol_value_is_hardcoded_outside_this_module` fails the
#: build if one appears. These are RL-ViGen's own values -- but from three different files, so
#: each line names its own source rather than inheriting one blanket claim.
DEFAULT_IMAGE_SIZE = 84        # robo_config.yaml image_height / image_width
DEFAULT_FRAME_STACK = 3        # robo_config.yaml + the paper's supplementary. TRUE FOR 8 OF THE
                               # 12 BASELINES ONLY -- see OBSERVATION_GEOMETRY below, which is
                               # the field that must be consulted per baseline.

#: Per-baseline observation geometry, because it is NOT shared and pretending otherwise makes the
#: protocol hash certify a value four runs do not have.
#:
#: `frame_stack` splits the twelve 8/4, and the split is exactly the four whose originals are
#: PROCGEN -- which serves one RGB frame, and whose encoders were built for one. Stacking them
#: would be a deviation in each clone; not stacking them is faithful. But a single frame on a
#: manipulation task is VELOCITY-BLIND: the gripper's motion is unobservable. An 8-vs-4 comparison
#: on Door is therefore across two different POMDPs, not two algorithms, and no rescaling of the
#: y-axis repairs that. See docs/PART2-METRIC-INVENTORY.md Finding 5.
#:
#: `image_size` splits them three ways, and that one is deliberate: each baseline renders at its
#: own paper's resolution so its encoder and augmentations run unmodified (RL-ViGen patch P6).
#: RAD at 84 is exactly SAC by its own `crop_max <= 0` guard; IDAAC hardcodes `Linear(2048, .)`
#: which is 32x8x8 and only 64; CTRL's model.init example is literally (1, L, 64, 64, 3).
#:
#: `tests/test_observation_geometry.py` checks these against what the launchers and the exported
#: clone patches actually do, so this table cannot drift from the runs it describes.
# Dependencies whose version can change a result rather than merely a warning. `mujoco` heads
# the list because it gates whether a regime RUNS AT ALL: RL-ViGen's texture modder reads
# `MjModel.tex_rgb`, removed in 3.0, so on a 3.x platform the eval-* regimes -- the entire
# manipulated variable -- are unreachable and only `train` is. A Kaggle run and a DataSphere run
# can therefore differ in what is executable and, until 2026-08-19, carried identical protocol
# hashes. See C29.
#
# This is READ, not hashed. Whether to hash it is the open half of C29 and is a judgement about
# where to draw the boundary -- hashing everything churns on patch bumps that change nothing.
# Recording it costs nothing and is required under every option, including the ones that hash.
VERSIONED_DEPENDENCIES = ("torch", "numpy", "mujoco", "robosuite", "gym", "gymnasium",
                          "dm-control", "jax")


def runtime_versions() -> dict:
    """Installed versions of the dependencies that can change a result. Metadata only.

    Deliberately does not import the packages: this is called to stamp a card, and importing
    torch or mujoco to find out their version would make writing a card cost seconds and, worse,
    could fail on a machine where a dependency is installed but not loadable.
    """
    from importlib import metadata
    out = {}
    for name in VERSIONED_DEPENDENCIES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "absent"
    return out


OBSERVATION_GEOMETRY = {
    # baseline:      (render size, frame stack)
    "drqv2":         (84, 3),
    "svea":          (84, 3),
    "sgqn":          (84, 3),
    "curl":          (84, 3),
    "drq":           (84, 3),
    "rad":           (100, 3),   # cropped to 84 by RAD's own random_crop
    "soda":          (100, 3),   # asserts x.size(-1) == 100
    "alda":          (64, 3),
    "ppg":           (64, 1),
    "idaac":         (64, 1),
    "ibac_sni":      (64, 1),
    "ctrl":          (64, 1),
}

# Time-limit handling, per baseline. Door and Lift have NO early termination, so every episode
# ends by time limit and this choice applies on every episode of every run. Three baselines
# bootstrap through it (correct for a truncation); nine zero the bootstrap, treating the limit as
# a terminal state -- which is right for Procgen, where episodes genuinely terminate, and wrong
# here because the environment changed underneath them. See C1.
#
# This exists because `time_limit_handling` below was a single string reading
# "truncate_with_bootstrap" for all twelve, INSIDE the hash. It was true of three. The hash
# therefore certified a convention nine baselines do not have, and two runs differing in it
# hashed identically -- the exact failure the hash exists to prevent. C1's own note named this
# split as "the consistent one"; this is it.
TIME_LIMIT_HANDLING = {
    # baseline:     convention        where the code does it
    "rad":          "bootstrap",      # runnable/dmc_gb/src/train.py:149
    "soda":         "bootstrap",      # same file, shared SAC
    "alda":         "bootstrap",      # runnable/alda/trainers/alda_trainer.py:655
    "drqv2":        "terminal",       # RL-ViGen-upstream/wrappers/robo_wrapper.py:42
    "svea":         "terminal",       # same wrapper
    "sgqn":         "terminal",       # same wrapper
    "curl":         "terminal",       # same wrapper
    "drq":          "terminal",       # same wrapper
    "ctrl":         "terminal",       # runnable/ctrl/buffer.py:16,18
    "idaac":        "terminal",       # runnable/idaac/ppo_daac_idaac/storage.py:58-62
    "ppg":          "terminal",       # runnable/ppg/phasic_policy_gradient/ppo.py:38
    "ibac_sni":     "terminal",       # Procgen-native, same reasoning
}
# DEAD KNOB (C71 #4): declared here and NEVER CONSULTED BY THE RUNNERS. `Protocol` hashes this
# value into the comparability record, but `runnable/_launch/*.sh` and the clones' own entry points
# never read it, so a launcher passing a different repeat would not conflict with it -- it would
# simply not be noticed. The check that does bite is
# `tests/test_x_axis_invariant.py::test_every_archived_grid_was_measured_at_action_repeat_1`,
# which reads the grids rather than this constant.
DEFAULT_ACTION_REPEAT = 1      # Supplementary Table 2: "Action repeat -- Robosuite: 1,
                               # otherwise: 2". NOT a robo_config.yaml key -- do not go looking
                               # for it there and "correct" this to 2. Their own code
                               # contradicts their paper here: cfgs/config.yaml sets 2, neither
                               # Door.yaml nor Lift.yaml overrides it, and robo_make really does
                               # apply it (wrappers/robo_wrapper.py:124 ActionRepeatWrapper), so
                               # a stock RL-ViGen robosuite run is off its own table by 2x on
                               # every budget. We follow the paper. See docs/FAITHFULNESS.md.
DEFAULT_HORIZON = 500          # robo_config.yaml task_def.horizon


@functools.lru_cache(maxsize=4)
def git_commit(short: bool = True) -> str:
    """The commit that produced a run. Absent provenance is recorded as such, never as blank.

    Cached: this is a `default_factory`, so it runs on every `Protocol()` construction, and it
    spawns two subprocesses. The test suite builds hundreds of protocols. The value cannot change
    within a process in any way that matters -- a run's provenance is fixed at start.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--short" if short else "HEAD",
                              "HEAD"], capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return "unknown"
        sha = out.stdout.strip().split("\n")[0]
        dirty = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10)
        return sha + ("-dirty" if dirty.stdout.strip() else "")
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class Protocol:
    """Every value that can change a reported number. Frozen: a run cannot mutate its own protocol.

    Fields are grouped exactly as the emitted card is, so the card and this class cannot drift.
    """

    # -- identity -----------------------------------------------------------------------------
    name: str = "canonical"
    schema_version: int = SCHEMA_VERSION

    # -- environment --------------------------------------------------------------------------
    benchmark: str = "rl_vigen_robosuite"
    task: str = "Door"
    #: RL-ViGen upstream commit. The field that ends most disputes.
    env_commit: str = "90d8b8c"
    #: Which patches the vendored upstream carries. Recorded so a run says which tree produced it,
    #: and INSIDE the hash, so a run on an unpatched tree cannot pool with one on a patched tree.
    #:
    #: This was stale: it named three patches when four are applied, and its old comment claimed
    #: `apply_patches.py` set it -- nothing ever wrote it. So the hash certified a patch set that
    #: was not the one that ran. `tests/test_contract.py::test_env_patches_matches_the_patch_script`
    #: now pins it to setup/apply_patches.py, which is the only thing that knows the real answer.
    env_patches: tuple = ("P1-make_env-mode", "P2-guard-video-load", "P3-robo_make-mode",
                          "P4-overlay-device", "P5-drq-log-alpha-float32",
                          # P6 added 2026-08-17. Off unless RLVIGEN_IMAGE_SIZE is set, but it is
                          # declared unconditionally because the PATCH is present in the tree
                          # whether or not a given run activates it, and the hash certifies the
                          # tree. It lets each baseline render at its own paper's resolution --
                          # RAD/SODA 100 (cropped to 84), ALDA 64 -- which is what makes their
                          # own augmentations and encoders work unmodified.
                          "P6-render-size-settable",
                          # P7 added 2026-08-17. train.py/eval.py forced MUJOCO_GL='egl' at
                          # import; setdefault makes it a default instead. On every Linux target
                          # -- Kaggle, DataSphere -- MUJOCO_GL is unset and the environment is
                          # byte-identical to upstream, so this changes no run that matters. It
                          # is declared anyway because the patch is in the tree the hash certifies.
                          "P7-mujoco-gl-not-forced",
                          # P8 added 2026-08-17. dm_control's action_scale re-promotes the
                          # action spec to float64 while every agent emits float32, so
                          # ReplayBufferStorage.add asserted on the FIRST stored transition --
                          # i.e. RL-ViGen's own five could not train on robosuite at all with
                          # dm-control 1.0.14. Inert where the spec is already float32.
                          "P8-action-spec-float32",
                          # P9 added 2026-08-17. robosuite's binding_utils overwrote MUJOCO_GL
                          # at import ("cgl" on macOS), which dm_control rejects, so any process
                          # importing robosuite first could not import dm_control at all. On
                          # Linux the value it would have written is the one already set.
                          "P9-robosuite-keeps-mujoco-gl",
                          # P10 added 2026-08-17. Puts robosuite's own task-defined
                          # _check_success() into info. Door's dense return is scale-arbitrary;
                          # this is the only unit-free quantity on the benchmark, and NOTHING
                          # reported it before -- the SR column in RL-ViGen's logger is filled
                          # only on the habitat path. The seven non-RL-ViGen baselines receive
                          # it immediately; RL-ViGen's own five are blocked by their dm_env
                          # conversion dropping info (see P11, withdrawn).
                          "P10-success-in-info",
                          # P11 added 2026-08-17. Carries P10's info past RL-ViGen's own dm_env
                          # conversion (which drops it) as an attribute, and fills the
                          # success_rate column logger.py has always declared but only the
                          # HABITAT path ever wrote to. Exact at action_repeat=1, which is the
                          # declared protocol; at k>1 a success lost inside a repeat is missed.
                          "P11-eval-reports-success-rate",
                          # P12 added 2026-08-17. RL-ViGen's own train.py built eval_env with
                          # arguments IDENTICAL to train_env, so it inherited robo_config's
                          # `mode: train` -- its five baselines evaluated on the training
                          # distribution and reported no generalisation gap at all. Driven by
                          # RLVIGEN_EVAL_MODE, unset = upstream behaviour unchanged.
                          "P12-eval-env-gets-a-regime",
                          # P13 added 2026-08-17. logger.py imported SummaryWriter at module
                          # scope for a feature that is off by default and off in every run
                          # here; on Kaggle that import segfaults (protobuf C extension) or
                          # hangs (pure-python protobuf). Moved into the one `if use_tb:`
                          # branch that uses it. Identical where TensorBoard is actually on.
                          "P13-tensorboard-imported-lazily",
                          # P14 added 2026-08-19, and it is the first patch to change WHICH
                          # DISTRIBUTION is evaluated rather than what is recorded about it.
                          # C45: the protocol certifies ten evaluation scenes (`eval_scene_ids`,
                          # inside this hash) and `train.py` evaluated scene 0 forever, so the
                          # hash agreed with itself while certifying coverage nothing enforced.
                          # C43: retention needs a train-regime denominator, which nothing built,
                          # so the generalisation gap was not computable from a training run.
                          # Both are one edit to one loop, which is why they are one patch.
                          # Its presence here is what makes pre-P14 and post-P14 numbers
                          # machine-distinguishable instead of silently poolable -- C47's
                          # retention was measured before it and must not be superseded quietly.
                          "P14-eval-sweeps-scenes-and-train-regime",
                          # P15, P17, P18 added to this tuple 2026-09-02, LATE. They were applied
                          # to the tree earlier and this declaration was not updated with them, so
                          # `Protocol.hash()` certified a P1-P14 tree while a P1-P18 tree ran --
                          # the exact failure the field exists to prevent, and the one its own
                          # comment above describes. Caught by
                          # `test_env_patches_matches_the_patch_script`, which is why that test is
                          # written against apply_patches.py rather than against a list.
                          #
                          # P15 (ENABLES). Evaluates and snapshots at the exact finite endpoint,
                          # so a run's last measurement is at the budget it declares rather than
                          # at the last cadence boundary before it. It adds a measurement.
                          "P15-terminal-eval-and-snapshot",
                          # P17 (PLATFORM). `drq`'s actor logged `dist.entropy()` on a
                          # SquashedNormal -- a TransformedDistribution with no closed-form
                          # entropy -- which raises NotImplementedError. Guarded by `use_tb`,
                          # which the launcher has forced since 2026-08-20, so `drq` could not
                          # train at all. Removing the line changes nothing measured; it is the
                          # difference between a run and a crash.
                          "P17-drq-actor-entropy-crash",
                          # P18 (ENABLES). Keeps the intermediate snapshots the loop already
                          # writes and then overwrites, on a cadence. It changes what is RETAINED,
                          # not what is learned -- training is byte-identical -- but a budget
                          # curve that exists is a measurement that did not exist before.
                          "P18-preserve-intermediate-snapshots",
                          # P19 (PLATFORM). The places365 loader hardcodes 8 JPEG-decoding workers
                          # with pin_memory on a 4-CPU container, which corrupts the heap under
                          # sgqn's doubled draw rate. Worker count changes SCHEDULING, never which
                          # images are drawn nor in what order, so a number produced with it is
                          # still upstream's -- but it IS a difference from the pinned tree and the
                          # hash must carry it. Added the same day it was written, unlike P15/P17/P18.
                          "P19-places-loader-workers")
    robot: str = "Panda"
    controller: str = "OSC_POSE"

    # -- observation --------------------------------------------------------------------------
    #: `None` means "take it from OBSERVATION_GEOMETRY for this baseline". Closed 2026-08-19,
    #: the same defect as `time_limit_handling` and the same fix: these are hashed, they defaulted
    #: to (84, 3) for every baseline, and the map beside them already recorded that `rad`/`soda`
    #: render at 100 and that four baselines stack ONE frame. So `Protocol(name="ppg")` certified
    #: an observation ppg never sees. An explicit value is still honoured and never overwritten.
    image_size: int | None = None
    frame_stack: int | None = None
    channels: str = "rgb"
    #: robosuite steps once per env.step. RL-ViGen's cfgs/config.yaml defaults to 2 and no task
    #: config overrides it, which is how a factor-of-two frame-accounting error gets into a table.
    #: 1 is correct here and is stated rather than inherited.
    action_repeat: int = DEFAULT_ACTION_REPEAT

    # -- episode ------------------------------------------------------------------------------
    #: robo_config.yaml task_def.horizon. Door/Lift have no early termination, so EVERY episode
    #: end is a time limit. Truncation is derived from this number rather than from the env's
    #: `discount` field, because ExtendedTimeStepWrapper turns the terminal 0.0 back into 1.0.
    horizon: int = DEFAULT_HORIZON
    #: **WAS TRUE OF THREE BASELINES OUT OF TWELVE, as a single blanket value. Closed
    #: 2026-08-19: the field is now filled per baseline from TIME_LIMIT_HANDLING above, so
    #: it does describe the run it belongs to.** The warning is kept rather than deleted
    #: because the history is the point: this field asserted the opposite of what nine
    #: baselines do, from inside the hash, for weeks.**
    #:
    #: It states what `rlgen/replay.py` did, and what a correct treatment of a time limit IS: on
    #: Door and Lift nothing terminates early, so EVERY episode ends by truncation, and zeroing
    #: the bootstrap there biases every value estimate downward. The clone approach deliberately
    #: gave that up -- each baseline runs its authors' code, and most of those authors zero it.
    #: Surveyed by reading each clone rather than assuming (an independent audit asserted "every
    #: current clone zeroes the bootstrap", which is false):
    #:
    #:   rad, soda      BOOTSTRAP   dmc_gb/src/train.py:149 --
    #:                              `done_bool = 0 if episode_step + 1 == env._max_episode_steps`
    #:   alda           BOOTSTRAP   trainers/alda_trainer.py:655, the identical idiom against
    #:                              `self.env.env._max_episode_steps`
    #:   drqv2 svea sgqn curl drq   zero -- RL-ViGen wrappers/robo_wrapper.py:42 `discount = 0.0`
    #:   ctrl           zero -- buffer.py:16,18 `(1 - done[t])` in the GAE recursion
    #:   idaac          zero -- ppo_daac_idaac/storage.py:58-62, GAE masked by `masks[step+1]`
    #:   ppg            zero -- phasic_policy_gradient/ppo.py:38 `notlast = 1.0 - first[:, t+1]`
    #:
    #: The split is 3 / 9, and it is not arbitrary: the three that get it right are exactly the
    #: SAC-family clones descended from Yarats' dmcontrol code, which carried the fix. The nine
    #: that do not are the RL-ViGen five and the four Procgen-native on-policy algorithms, for
    #: which every episode in Procgen genuinely IS a termination -- so their authors were right
    #: for Procgen and are wrong here, purely because the environment changed underneath them.
    #: That is a deviation nobody introduced and nobody can see from a diff.
    #:
    #: So this is the same shape as DEFAULT_FRAME_STACK above -- a single field standing in for a
    #: split -- and it is the more consequential of the two, because it means three baselines'
    #: value TARGETS mean something different from the other nine's, underneath every number
    #: either produces. That is a comparability fact and it belongs in the report, not only here.
    #:
    #: Left at this value rather than corrected to `truncate_as_terminal`, because the value is
    #: inside `hash()` (see `block("episode", ...)`) and changing it invalidates every recorded
    #: protocol hash -- a decision with consequences for existing results, not a docs fix. The
    #: honest options are (a) re-value it and re-stamp, (b) split it per-baseline the way
    #: OBSERVATION_GEOMETRY splits frame stacking. (b) is the consistent one.
    #: **CLOSED 2026-08-19 by (b).** The default is now the sentinel below, which asserts nothing
    #: about any baseline; `__post_init__` fills it from TIME_LIMIT_HANDLING when `name` is one of
    #: the twelve, so `Protocol(name="drq")` and `Protocol(name="rad")` no longer hash alike. The
    #: re-stamp this costs was bundled with P14's, which moved every hash the same day.
    time_limit_handling: str = "per-baseline"

    # -- training -----------------------------------------------------------------------------
    #: Budget in ENVIRONMENT FRAMES with action_repeat folded in. Never "steps": that word means
    #: agent steps in some codebases and simulator steps in others.
    total_frames: int = 500_000
    train_mode: str = "train"
    #: Training uses a single scene. Stated because it is invisible in the code otherwise and it
    #: determines what "generalisation" means for every number in the table.
    train_scene_ids: tuple = (0,)

    # -- evaluation ---------------------------------------------------------------------------
    eval_mode: str = "eval-easy"
    eval_scene_ids: tuple = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    episodes_per_scene: int = 10
    eval_every_frames: int = 50_000
    policy_mode: str = "deterministic"
    #: Held out from training: training uses scene 0 only, evaluation uses all ten. Recorded
    #: explicitly because the reference repo evaluates on the full distribution INCLUDING the
    #: training levels, and the two answers are not comparable.
    eval_includes_train_scenes: bool = True
    checkpoint_selection: str = "final"

    # -- scoring ------------------------------------------------------------------------------
    #: Undiscounted raw episodic return. Never the normalised return: the reference repo wraps its
    #: eval env in VecNormalize and reports a normalised number under a name that reads like a raw
    #: one, which makes its curves incomparable with published tables.
    metric: str = "episode_return_raw_undiscounted"
    reward_shaping: bool = True
    #: MEAN, not IQM. On RL-ViGen eval-easy the per-scene return distribution is bimodal, and IQM
    #: trims the successful tail: across the sibling project's evaluations the mean exceeded the
    #: IQM in 82% of cases, median ratio 1.418. That is a bias, not noise.
    aggregation: str = "mean"
    uncertainty: str = "bootstrap_ci_95"

    # -- provenance ---------------------------------------------------------------------------
    seed: int = 0
    code_commit: str = field(default_factory=git_commit)
    #: "checkpoint:<sha256[:12]>" or "random_init". A results artifact that cannot say where its
    #: weights came from is not admissible -- the previous implementation silently evaluated
    #: untrained networks and labelled the output `checkpoint_selection: final`.
    weights_source: str = "unset"

    # -----------------------------------------------------------------------------------------
    def __post_init__(self):
        # A named baseline carries ITS convention, not a project-wide claim. Left as the sentinel
        # for `canonical` and for any name not among the twelve, because asserting one there is
        # what made this field false in the first place.
        if self.time_limit_handling == "per-baseline" and self.name in TIME_LIMIT_HANDLING:
            object.__setattr__(self, "time_limit_handling", TIME_LIMIT_HANDLING[self.name])
        geo = OBSERVATION_GEOMETRY.get(self.name)
        if self.image_size is None:
            object.__setattr__(self, "image_size", geo[0] if geo else DEFAULT_IMAGE_SIZE)
        if self.frame_stack is None:
            object.__setattr__(self, "frame_stack", geo[1] if geo else DEFAULT_FRAME_STACK)
        if self.task not in TASKS:
            raise ValueError(f"task {self.task!r} not in {TASKS}")
        for f, v in (("train_mode", self.train_mode), ("eval_mode", self.eval_mode)):
            if v not in MODES:
                raise ValueError(f"{f} {v!r} not in {MODES}")
        if self.policy_mode not in ("deterministic", "stochastic"):
            raise ValueError(f"policy_mode {self.policy_mode!r} must be deterministic|stochastic")
        if self.aggregation not in ("mean", "iqm", "median"):
            raise ValueError(f"aggregation {self.aggregation!r} not supported")
        if self.episodes_per_scene < 1 or not self.eval_scene_ids:
            raise ValueError("evaluation must run at least one episode on at least one scene")
        if self.horizon % self.action_repeat:
            raise ValueError(
                f"horizon {self.horizon} is not a multiple of action_repeat {self.action_repeat}; "
                "truncation is derived from the horizon, so a non-integer episode length would "
                "make the derived flag wrong on the last step")

    # -- derived ------------------------------------------------------------------------------
    @property
    def n_eval_episodes(self) -> int:
        return len(self.eval_scene_ids) * self.episodes_per_scene

    @property
    def steps_per_episode(self) -> int:
        return self.horizon // self.action_repeat

    @property
    def obs_shape(self) -> tuple:
        return (3 * self.frame_stack, self.image_size, self.image_size)

    # -- identity -----------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}

    #: Fields excluded from the comparability hash. `name` is a label; `seed` must differ between
    #: runs that are averaged together; `weights_source` and `code_commit` are provenance, not
    #: protocol. Everything else must match for two numbers to belong in one table.
    HASH_EXCLUDE = ("name", "seed", "weights_source", "code_commit")

    def hash(self) -> str:
        d = {k: v for k, v in self.to_dict().items() if k not in self.HASH_EXCLUDE}
        blob = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def comparable_to(self, other: "Protocol") -> bool:
        return self.hash() == other.hash()

    def differences(self, other: "Protocol") -> dict[str, tuple]:
        """Exactly which fields make two runs incomparable. Better than a boolean in a review."""
        a, b = self.to_dict(), other.to_dict()
        return {k: (a[k], b[k]) for k in a
                if k not in self.HASH_EXCLUDE and a[k] != b[k]}

    def replace(self, **kw) -> "Protocol":
        return dataclasses.replace(self, **kw)

    # -- the card -----------------------------------------------------------------------------
    def card(self) -> str:
        d = self.to_dict()
        def block(title, keys):
            out = [f"  {title}:"]
            for k in keys:
                out.append(f"    {k}: {json.dumps(d[k])}")
            return "\n".join(out)
        return "\n".join([
            "# Protocol card",
            "",
            "```yaml",
            "protocol_card:",
            f"  hash: {self.hash()}      # NECESSARY, not sufficient -- see runtime below",
            "  # The hash covers the protocol. It does NOT cover the dependency versions the run",
            "  # executed against, and those can decide whether a regime runs at all (mujoco 3.x",
            "  # lacks MjModel.tex_rgb, so the eval-* regimes are unreachable there). Two cards",
            "  # with the same hash and different `runtime` are NOT interchangeable. C29.",
            "  runtime:",
            "\n".join(f"    {k}: {v}" for k, v in runtime_versions().items()),
            f"  name: {json.dumps(d['name'])}",
            f"  schema_version: {d['schema_version']}",
            block("environment", ["benchmark", "task", "env_commit", "env_patches", "robot",
                                  "controller"]),
            block("observation", ["image_size", "frame_stack", "channels", "action_repeat"]),
            block("episode", ["horizon", "time_limit_handling"]),
            block("training", ["total_frames", "train_mode", "train_scene_ids", "seed"]),
            block("evaluation", ["eval_mode", "eval_scene_ids", "episodes_per_scene",
                                 "eval_every_frames", "policy_mode",
                                 "eval_includes_train_scenes", "checkpoint_selection"]),
            block("scoring", ["metric", "reward_shaping", "aggregation", "uncertainty"]),
            block("provenance", ["code_commit", "weights_source"]),
            f"  derived:",
            f"    n_eval_episodes: {self.n_eval_episodes}",
            f"    steps_per_episode: {self.steps_per_episode}",
            f"    obs_shape: {list(self.obs_shape)}",
            "```",
            "",
        ])

    def write_card(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.card())

    def write_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"hash": self.hash(), **self.to_dict()}, f, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "Protocol":
        fields = {f.name for f in dataclasses.fields(cls)}
        kw = {k: v for k, v in d.items() if k in fields}
        for k in ("env_patches", "train_scene_ids", "eval_scene_ids"):
            if k in kw and isinstance(kw[k], list):
                kw[k] = tuple(kw[k])
        return cls(**kw)
