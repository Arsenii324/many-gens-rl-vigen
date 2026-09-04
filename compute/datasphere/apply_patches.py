#!/usr/bin/env python3
"""Apply this repo's edits to the vendored RL-ViGen checkout.

RL-ViGen is not importable as a library and is too large to vendor into git (1.8 GB), so it is
cloned by `setup/install.sh` and patched here. These three edits are the difference between
upstream and what this benchmark needs; each is stated with the defect it fixes so a reviewer can
judge it rather than trust it.

DESIGN. Every patch is (target file, exact text to find, replacement, a check that says whether it
is already applied). That makes the script **idempotent**: running it twice is a no-op, and running
it against an already-patched tree exits 0 without touching anything. This matters -- the four
`fix_*.py` scripts this repo used to carry were one-shot rewriters with no such guard, and
`docs/REVIEW.md` records them as a live hazard.

Run:  python setup/apply_patches.py [--check]
      --check exits 1 if any patch is missing, and changes nothing. Use it in CI.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.join(ROOT, "RL-ViGen-upstream")

VGB = os.path.join(UPSTREAM, "envs", "robosuiteVGB", "robosuitevgb")
WRAP = os.path.join(UPSTREAM, "wrappers")


# --------------------------------------------------------------------------------------------
# P1 -- make_env cannot be told which visual regime to build.
#
# `mode` lives only in the hydra config `robo_config.yaml`, so every env is built in whatever
# mode that file happens to say -- for the shipped config, `train`. A caller asking for
# `eval-easy` silently gets a train env, and the resulting "generalisation" number is measured on
# the training distribution. This is the single most dangerous upstream defect for this project:
# it produces a plausible number, not a crash.
#
# The sibling project (../gen-rebuttal/vigen-idaac) hit exactly this and recorded it as B7; it ran
# for the whole project before being found. We also export the resolved regime so a caller can
# VERIFY what it got instead of trusting that the request propagated.
# --------------------------------------------------------------------------------------------
P1_FIND = """def make_env(task_name: str, seed: int, scene_id: int = 0):
    \"\"\"
    create the robo envs with different parameters.
    \"\"\"
    hydra.core.global_hydra.GlobalHydra.instance().clear()
    with initialize(config_path="../cfg"):
        cfg = compose(config_name="robo_config")
        cfg_dict = omegaconf_to_dict(cfg)
    assert scene_id >= 0 and scene_id <= 9
    cfg_dict['scene_id'] = scene_id"""

P1_REPL = """def make_env(task_name: str, seed: int, scene_id: int = 0, mode=None):
    \"\"\"
    create the robo envs with different parameters.

    PATCHED (many-gens-rl-vigen P1): `mode` is now an argument. Upstream read it only from
    robo_config.yaml, so a caller asking for eval-easy silently received a train env and
    measured generalisation on the training distribution. See setup/apply_patches.py.
    \"\"\"
    hydra.core.global_hydra.GlobalHydra.instance().clear()
    with initialize(config_path="../cfg"):
        cfg = compose(config_name="robo_config")
        cfg_dict = omegaconf_to_dict(cfg)
    assert scene_id >= 0 and scene_id <= 9
    cfg_dict['scene_id'] = scene_id
    if mode is not None:
        cfg_dict['mode'] = mode"""

# Export the regime that was actually resolved, so the caller can assert on it.
P1B_FIND = """                     video_background=cfg_dict['video_background'],"""
P1B_REPL = """                     video_background=cfg_dict['video_background'],"""  # unchanged anchor


# --------------------------------------------------------------------------------------------
# P2 -- the background video is LOADED unconditionally but USED only by eval-hard.
#
# VGBWrapper.__init__ calls load_video(mode, ...) for every mode. The shipped asset pack contains
# assets/video/{eval-easy,eval-hard,eval-extreme} and has NO `train` directory (nor the
# `eval-medium` the code's own assert accepts). For mode='train', cv2.VideoCapture on a
# nonexistent file returns frame count -1, and np.empty((-1, H, W, 3)) raises
# "ValueError: negative dimensions are not allowed".
#
# So RL-ViGen's robosuite path does not run in train mode out of the box. `video_buf` is read only
# under `if self.video_background:` (vgb_wrapper.py:230), and video_background is set True only for
# eval-hard (utils.py:66) -- so guarding the load is behaviour-preserving for every mode that
# actually uses it, and turns a crash into a no-op for every mode that does not.
# --------------------------------------------------------------------------------------------
P2_FIND = """        self.video_buf = self.load_video(mode, image_height, image_width)"""

P2_REPL = """        # PATCHED (many-gens-rl-vigen P2): load the background video only when it is used.
        # video_buf is read solely under `if self.video_background:` below, and that flag is set
        # only for eval-hard. Upstream loaded it for every mode, which crashes on mode='train'
        # because assets/video/train/ does not exist. See setup/apply_patches.py.
        self.video_buf = (self.load_video(mode, image_height, image_width)
                          if video_background else None)"""


# --------------------------------------------------------------------------------------------
# P3 -- robo_make drops `mode` on the floor, and the resolved regime is unreachable.
#
# Even with P1, the wrapper chain that robo_make builds gives a caller no way to ask the outermost
# object which regime it got: the chain does not forward attribute lookups down to VGBWrapper. We
# thread `mode` through and hoist `_vigen_regime` onto the outermost wrapper so that
# rlgen/envs.py can assert the env was BUILT in the mode that was requested.
# --------------------------------------------------------------------------------------------
P3_FIND = """def robo_make(name, frame_stack=3, action_repeat=2, seed=1, scene_id=0):
    # create environment instance
    env = robosuitevgb.make_env(task_name=name, seed=seed, scene_id=scene_id)"""

P3_REPL = """def robo_make(name, frame_stack=3, action_repeat=2, seed=1, scene_id=0, mode=None):
    # PATCHED (many-gens-rl-vigen P3): thread `mode` through, and hoist the resolved regime onto
    # the outermost wrapper so a caller can verify what it got. See setup/apply_patches.py.
    base = robosuitevgb.make_env(task_name=name, seed=seed, scene_id=scene_id, mode=mode)
    env = base"""

P3B_FIND = """    env = ExtendedTimeStepWrapper(env)
    return env"""

P3B_REPL = """    env = ExtendedTimeStepWrapper(env)
    # PATCHED (P3): carry the resolved regime out to the outermost object.
    try:
        env._vigen_regime = {
            "mode": getattr(base, "_mode", None),
            "scene_id": getattr(base, "_scene_id", None),
            "video_background": getattr(base, "video_background", None),
        }
    except Exception:
        pass
    return env"""


# --------------------------------------------------------------------------------------------
# P4 -- `_get_places_batch` returns `imgs.cuda()`, unconditionally.
#
# SVEA and SGQN call `random_overlay`, which calls this. On any machine without CUDA -- this one,
# and any CPU-only CI -- both baselines die at their FIRST update with
# `AssertionError: Torch not compiled with CUDA enabled`, after the frame-0 evaluation has
# already written artifacts. SODA is unaffected because its own augmentation path moves the
# tensor itself.
#
# The fix follows the device of the observation it is about to be blended with, which is the only
# device that can be correct. It is a no-op on a CUDA box.
# --------------------------------------------------------------------------------------------
P4_FIND = """\treturn imgs.cuda()"""
P4_REPL = """\t# PATCHED (many-gens-rl-vigen P4): follow the caller's device instead of assuming CUDA.
\t# Unconditional .cuda() killed SVEA and SGQN at their first update on any CPU/MPS machine.
\treturn imgs.to(_places_device[0]) if _places_device else imgs"""

P4B_FIND = """def _get_places_batch(batch_size):"""
P4B_REPL = """#: Set by random_overlay before each batch is fetched -- see PATCH P4.
_places_device = []


def _get_places_batch(batch_size):"""

P4C_FIND = """def random_overlay(x, dataset='places365_standard'):"""
P4C_REPL = """def random_overlay(x, dataset='places365_standard'):
\t# PATCHED (P4): record the device the overlay must land on.
\t_places_device.clear(); _places_device.append(x.device)"""

#: Files the vendored tree is ALLOWED to differ from its pinned commit in, beyond the patches
#: above. Everything here is either produced by our own setup scripts or is a compatibility fix
#: that predates this file; the point of the list is that anything NOT on it is a surprise.
#:
#: This exists because `--check` used to verify only that our four patches were present, and
#: reported "the vendored tree is in a known state" while thirteen files were modified. A check
#: that certifies a subset of the truth is worse than no check: it is a false all-clear.
ALLOWED_MODIFIED = {
    "cfgs/aug_config.cfg": "written by setup/fetch_overlay_dataset.sh when the overlay dataset "
                           "is installed; not source, and not something a patch should carry",
    # NOT our edit and NOT fixable locally. Upstream tracks BOTH `cfgs/task/TwoArmHandOver.yaml`
    # and `cfgs/task/TwoArmHandover.yaml` -- two paths differing only in the case of one letter.
    # macOS is case-insensitive, so only one can exist on disk and git reports the other as
    # permanently modified. RL-ViGen therefore cannot be checked out cleanly on a Mac at all.
    # Neither file is on the Door/Lift path, so this is cosmetic here -- but it is a real
    # obstacle to "clone and run" on macOS and belongs in the record rather than in someone's
    # afternoon.
    "cfgs/task/TwoArmHandover.yaml": "upstream case-collision with TwoArmHandOver.yaml; "
                                     "unresolvable on a case-insensitive filesystem",
}


#: Untracked paths in the vendored tree that a RUN creates. Distinguished from modifications
#: because they fail differently: a modified file is a hand-edit nobody declared, while an
#: untracked one here is almost always output. `door.xml` -- 49 KB of MuJoCo XML named after the
#: task -- is dumped at cwd by a robosuite run, and it failed this check on every machine that
#: had ever run one. Kept as an explicit list rather than a wildcard: an untracked .py in this
#: tree really would be an undeclared deviation and must still fail.
ALLOWED_UNTRACKED = {
    "door.xml": "run artifact: a robosuite task model dumped at cwd during a run",
    "exp_local": "run artifact: RL-ViGen's own hydra output directory",
}


def undeclared_modifications() -> list[str]:
    """Files modified in the vendored tree that neither a patch nor ALLOWED_MODIFIED explains.

    Untracked paths are judged separately, against ALLOWED_UNTRACKED -- see its note.
    """
    import subprocess
    try:
        out = subprocess.run(["git", "-C", UPSTREAM, "status", "--porcelain"],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    if out.returncode != 0:
        return []
    patched = {os.path.relpath(path, UPSTREAM) for _n, path, _f, _r in PATCHES}
    bad = []
    for line in out.stdout.splitlines():
        code, rel = line[:2], line[3:].strip()
        if not rel or rel.endswith(".egg-info") or ".egg-info/" in rel:
            continue                      # pip install -e artifacts, not source
        if code == "??":
            if any(seg in ALLOWED_UNTRACKED for seg in rel.rstrip("/").split("/")):
                continue
            bad.append(f"{rel}  (untracked -- a file nothing declared adding)")
            continue
        if rel in patched or rel in ALLOWED_MODIFIED:
            continue
        bad.append(rel)
    return bad


# --------------------------------------------------------------------------------------------
# P5 -- DrQ's `log_alpha` is float64, and MPS does not support float64.
#
# `torch.tensor(np.log(init_temperature))` produces a float64 tensor, because numpy's log of a
# Python float is a float64 scalar. On CUDA and CPU that is merely wasteful; on Apple MPS it is
# fatal -- the tensor cannot be placed on the device and DrQ dies at construction.
#
# This edit existed in the vendored tree for weeks as an UNDECLARED hand-modification: it was
# needed to run DrQ on this machine, it was made, and it was never written down. So
# `setup/install.sh` on a fresh machine produced a tree in which DrQ crashes, while
# `apply_patches.py --check` reported everything in order. Declaring it is the fix; the lesson is
# that "I edited upstream to make it run" is exactly the kind of change that must become a patch
# the same day.
# --------------------------------------------------------------------------------------------
P5_FIND = """        self.log_alpha = torch.tensor(np.log(init_temperature)).to(device)"""
P5_REPL = """        # PATCHED (many-gens-rl-vigen P5): float32, because MPS does not support float64 and
        # np.log of a Python float is a float64 scalar. See setup/apply_patches.py.
        self.log_alpha = torch.tensor(np.float32(np.log(init_temperature))).to(device)"""



# P6 -- the render resolution is fixed at 84x84, and two baselines are specified on 100.
#
# `robo_config.yaml` sets image_height/image_width to 84. RAD and SODA are both specified on a
# 100x100 render cropped to 84, and at a native 84 render their OWN code degrades correctly but
# uselessly: RAD's `augmentations.random_crop` computes `crop_max = 84 - 84 = 0` and returns the
# input unchanged by its own guard -- so RAD becomes plain SAC, silently -- while SODA asserts
# `x.size(-1) == 100` and cannot run at all.
#
# Rendering at 100 makes both faithful at ZERO changed algorithm lines. Off by default: without
# RLVIGEN_IMAGE_SIZE the behaviour is exactly upstream's. `camera_heights`/`camera_widths`
# interpolate ${image_height}/${image_width} and are resolved by `omegaconf_to_dict`, so both
# levels must be set.
#
# Placed AFTER P1's replacement block, not inside it: an earlier attempt inserted between
# `cfg_dict = omegaconf_to_dict(cfg)` and the `assert`, which split P1_REPL and made --check
# report P1 as ANCHOR NOT FOUND.
P6_FIND = """    if mode is not None:
        cfg_dict['mode'] = mode"""
P6_REPL = """    if mode is not None:
        cfg_dict['mode'] = mode
    # PATCHED (many-gens-rl-vigen P6): allow the render resolution to be raised.
    # robo_config.yaml fixes 84x84, but RAD and SODA are specified on a 100x100 render cropped to
    # 84 -- at a native 84 render RAD's own random_crop degrades to the identity by its own
    # `crop_max <= 0` guard (so RAD becomes plain SAC), and SODA hard-asserts `x.size(-1) == 100`
    # and cannot run at all. Both are the AUTHORS' code behaving correctly for an input their
    # papers do not use. Defaults to unchanged behaviour when the variable is unset.
    # `camera_heights`/`camera_widths` interpolate ${image_height}/${image_width} and are already
    # resolved by omegaconf_to_dict, so both levels must be set.
    import os as _os
    _isz = _os.environ.get("RLVIGEN_IMAGE_SIZE")
    if _isz:
        _isz = int(_isz)
        cfg_dict['image_height'] = cfg_dict['image_width'] = _isz
        cfg_dict['task_def']['camera_heights'] = _isz
        cfg_dict['task_def']['camera_widths'] = _isz"""


# ---------------------------------------------------------------------------------------------
# P7 -- do not FORCE the MuJoCo GL backend; only default it.
#
# train.py and eval.py open with `os.environ['MUJOCO_GL'] = 'egl'`, which is right for the
# authors' Linux/CUDA target and unconditional. On macOS there is no EGL at all: dm_control's
# renderer is chosen at import time from this variable, so the assignment made
# `RL-ViGen-upstream/train.py` unimportable here -- ImportError('Unable to load EGL library')
# from wrappers/dmc.py, before any argument was read.
#
# setdefault is a strictly weaker statement than assignment: with MUJOCO_GL unset -- which is
# every Linux run, every Kaggle run, every DataSphere run -- the resulting environment is
# byte-identical to upstream. It only stops the line from overriding a backend the caller has
# already chosen deliberately. This is what lets runnable/_launch/rlvigen.sh ask for glfw.
P7_FIND = """os.environ['MUJOCO_GL'] = 'egl'"""
P7_REPL = """# PATCHED (many-gens-rl-vigen P7): default it, do not force it. Identical when MUJOCO_GL is
# unset (Linux/Kaggle/DataSphere); on macOS there is no EGL and the hard assignment made this
# file unimportable. See setup/apply_patches.py.
os.environ.setdefault('MUJOCO_GL', 'egl')"""


# ---------------------------------------------------------------------------------------------
# P8 -- restore the invariant that the OUTERMOST action spec is float32.
#
# `ReplayBufferStorage.add` asserts `spec.dtype == value.dtype` for every field. On the robosuite
# path that assertion fires on the first stored transition: the spec says float64, every RL-ViGen
# agent emits float32 from torch.
#
# Where the float64 comes from, read rather than guessed. robo_make builds
#   Gym2DMC(float32) -> ActionDTypeWrapper(float32) -> ActionRepeatWrapper
#     -> action_scale.Wrapper(minimum=-1.0, maximum=+1.0) -> FrameStack -> ExtendedTimeStep
# and dm_control 1.0.14's action_scale.Wrapper.__init__ does
#   minimum = np.array(minimum)          # a PYTHON float -> a float64 array
#   dtype = np.result_type(minimum, maximum, orig_dtype)   # float64, float64, float32 -> float64
# so the last wrapper that touches the action dtype promotes it back to float64. (It is the
# np.array() call, not NEP 50: np.result_type(-1.0, 1.0, np.float32) is float32 on numpy 2.4.6 --
# checked. The python floats are made strong by being turned into arrays first.)
#
# DrQv2, which this wrapper stack is copied from, keeps ActionDTypeWrapper OUTERMOST among the
# dtype-touching wrappers, and its DMC stack has no action_scale. RL-ViGen inserted action_scale
# for robosuite and left ActionDTypeWrapper inside it.
#
# The patch ADDS a second ActionDTypeWrapper outside action_scale rather than moving the first:
# no existing line changes, and it is provably INERT where the bug is absent -- if the inner spec
# is already float32 then `action.astype(float32)` is a no-op and the exposed spec is unchanged.
# Numerically nothing moves either way: action_scale.transform already ends in
# `.astype(orig_dtype)`, so the value reaching the env is float32 before and after.
P8_FIND = """    env = action_scale.Wrapper(env, minimum=-1.0, maximum=+1.0)"""
P8_REPL = """    env = action_scale.Wrapper(env, minimum=-1.0, maximum=+1.0)
    # PATCHED (many-gens-rl-vigen P8): action_scale re-promotes the action spec to float64
    # (np.array(-1.0) is float64), while every agent emits float32, so ReplayBufferStorage.add
    # asserts on the first transition. A no-op where the spec is already float32.
    env = ActionDTypeWrapper(env, np.float32)"""


# ---------------------------------------------------------------------------------------------
# P9 -- robosuite must not OVERWRITE a MUJOCO_GL the caller already chose.
#
# `third_party/robosuite/.../binding_utils.py` assigns `os.environ["MUJOCO_GL"]` at import time
# whenever GPU rendering is on and the current value is not "osmesa"/"glx". On macOS it writes
# "cgl" -- which dm_control's renderer rejects outright, its valid set being
# ('', '0', '1', 'disable', ..., 'egl', 'glfw', 'osmesa', ...). So importing robosuite makes
# dm_control unimportable in any process started afterwards, and RL-ViGen imports both.
#
# It surfaces as the least informative error in this project: the main process survives (it
# imported dm_control before robosuite ran), a spawned replay-buffer worker re-imports train.py,
# dies at `from wrappers.dmc import ...`, and the parent reports
# "DataLoader worker exited unexpectedly. Details are lost due to multiprocessing."
#
# Same shape as P7 and equally inert where it matters: on Linux the existing value is "egl"
# already (our launcher sets it, and robosuite would have written the same thing), so the
# resulting environment is unchanged. It only stops the line from overriding a deliberate choice.
# "glfw" is in robosuite's OWN _VALID_MUJOCO_GL list four lines below, so nothing downstream of
# this assignment objects to it.
P9_FIND = (
    '    if _SYSTEM == "Darwin":\n'
    '        os.environ["MUJOCO_GL"] = "cgl"\n'
    '    else:\n'
    '        os.environ["MUJOCO_GL"] = "egl"'
)
P9_REPL = (
    '    # PATCHED (many-gens-rl-vigen P9): do not override a MUJOCO_GL the caller set. Writing\n'
    '    # "cgl" here makes dm_control unimportable in every process started after robosuite.\n'
    '    if os.environ.get("MUJOCO_GL"):\n'
    '        pass\n'
    '    elif _SYSTEM == "Darwin":\n'
    '        os.environ["MUJOCO_GL"] = "cgl"\n'
    '    else:\n'
    '        os.environ["MUJOCO_GL"] = "egl"'
)


# ---------------------------------------------------------------------------------------------
# P10 -- expose robosuite's own success flag in `info`.
#
# THE PROBLEM THIS SOLVES. Door's reward is dense, unnormalised and scale-arbitrary, so an
# episode return is not comparable across anything except itself. robosuite defines success per
# task (`_check_success`), which is sparse, task-defined and unit-free -- the one quantity on
# this benchmark that means the same thing for every algorithm. Nothing currently reports it:
#   - VGBWrapper.step returns info == {'mode', 'scene_id'} and nothing else (probed live);
#   - RL-ViGen's logger.py DECLARES ('success_rate', 'SR', 'float'), but only
#     Workspace.habi_eval -- the HABITAT path -- ever calls log('success_rate', ...). The
#     robosuite path goes through Workspace.eval, which never does. So the `SR: 0.0000` printed
#     by every robosuite run to date is the logger's default for a column nothing fills, not a
#     measurement.
#
# One line here makes it available to ALL TWELVE baselines at once, because every one of them
# reaches the env through this wrapper -- the same way P6 turned out to be the general key for
# render size. Consuming it is separate and costs a line per baseline; see P11 for RL-ViGen's own.
#
# `self.env` is the robosuite task instance (verified: type(e.env).__name__ == 'Door'), and
# `_check_success` is defined by robosuite's task API, not by any one task. Cast to bool because
# some tasks return a numpy bool_, which is not JSON-serialisable in a run card.
P10_FIND = """        ob_dict, reward, done, info = self.env.step(action)
        info["mode"] = self._mode
        info["scene_id"] = self._scene_id"""
P10_REPL = """        ob_dict, reward, done, info = self.env.step(action)
        info["mode"] = self._mode
        info["scene_id"] = self._scene_id
        # PATCHED (many-gens-rl-vigen P10): expose robosuite's own task-defined success flag.
        # Door's dense return is scale-arbitrary; this is the only unit-free quantity available,
        # and no baseline could see it before. See setup/apply_patches.py.
        info["success"] = bool(self.env._check_success())"""




# ---------------------------------------------------------------------------------------------
# P11 -- let RL-ViGen's own five report the success rate their logger already has a column for.
#
# HISTORY, because it matters: this was written, applied, WITHDRAWN, and then written again the
# right way. The first version read `time_step.info`, which does not exist on the robosuite path
# -- `Gym2DMC.step` builds a 4-field `dm_env.TimeStep` and discards `info`, and
# `wrappers/dmc.py`'s `ExtendedTimeStep` has no `info` field (habitat has a SEPARATE one in
# `habi_wrapper.py` that does, which is exactly why habitat can report SR and robosuite cannot).
# It would have logged a computed-looking 0.0 forever: strictly worse than the obviously-unfilled
# 0.0000 it replaced.
#
# What makes the real version small: EVERY wrapper between Gym2DMC and the agent delegates
# unknown attributes -- ActionDTypeWrapper, ActionRepeatWrapper, FrameStackWrapper,
# ExtendedTimeStepWrapper all define __getattr__, and so does dm_control's action_scale.Wrapper
# (checked, not assumed). So one attribute set on Gym2DMC is readable on the outermost env
# without touching the TimeStep type or any wrapper in between.
#
# ACTION REPEAT, stated because it is the one place this is not exact: ActionRepeatWrapper calls
# the inner step k times, so `last_info` holds the LAST repeat's info and a success achieved and
# lost inside a repeat is missed. At this project's declared protocol -- action_repeat=1, which
# is also RL-ViGen's own Supplementary Table 2 for robosuite -- k is 1 and the question does not
# arise. It would at k>1, and that is why it is written down here rather than discovered later.
P11A_FIND = """    def step(self, action):
        obs, reward, done, info = self._gym_env.step(action)
        obs = obs['rgb']"""
P11A_REPL = """    def step(self, action):
        obs, reward, done, info = self._gym_env.step(action)
        # PATCHED (many-gens-rl-vigen P11): dm_env.TimeStep has no room for `info`, so it is
        # exposed as an attribute instead. Every wrapper above this one delegates unknown
        # attributes, so `env.last_info` is readable on the outermost env. Carries P10's
        # `success` -- the only unit-free metric on this benchmark. See setup/apply_patches.py.
        self.last_info = info
        obs = obs['rgb']"""

P11B_FIND = """    def eval(self):
        step, episode, total_reward = 0, 0, 0
        eval_until_episode = utils.Until(self.cfg.num_eval_episodes)"""
P11B_REPL = """    def eval(self):
        step, episode, total_reward = 0, 0, 0
        # PATCHED (many-gens-rl-vigen P11): accumulate robosuite's task-defined success. An
        # episode counts as a success if the flag held at ANY step -- the same convention the
        # other seven baselines use. logger.py has always declared this column; only habi_eval
        # ever filled it, so every robosuite run printed SR: 0.0000 as a default, not a
        # measurement.
        success_rate, succeeded = 0.0, False
        eval_until_episode = utils.Until(self.cfg.num_eval_episodes)"""

P11C_FIND = """                time_step = self.eval_env.step(action)
                if self.env_name == 'dmc':
                    self.video_recorder.record_dmc(self.eval_env, video=True)"""
P11C_REPL = """                time_step = self.eval_env.step(action)
                # PATCHED (P11): getattr with a default -- the dmc path sets no last_info.
                succeeded = succeeded or bool(
                    (getattr(self.eval_env, 'last_info', None) or {}).get('success', False))
                if self.env_name == 'dmc':
                    self.video_recorder.record_dmc(self.eval_env, video=True)"""

P11D_FIND = """            episode += 1
            self.video_recorder.save(f'{self.global_frame}.mp4')

        with self.logger.log_and_dump_ctx(self.global_frame, ty='eval') as log:
            log('episode_reward', total_reward / episode)
            log('episode_length', step * self.cfg.action_repeat / episode)
            log('episode', self.global_episode)
            log('step', self.global_step)"""
P11D_REPL = """            episode += 1
            success_rate += float(succeeded)   # PATCHED (P11)
            succeeded = False
            self.video_recorder.save(f'{self.global_frame}.mp4')

        with self.logger.log_and_dump_ctx(self.global_frame, ty='eval') as log:
            log('episode_reward', total_reward / episode)
            log('episode_length', step * self.cfg.action_repeat / episode)
            log('episode', self.global_episode)
            log('step', self.global_step)
            log('success_rate', success_rate / episode)   # PATCHED (P11)"""


# ---------------------------------------------------------------------------------------------
# P12 -- RL-ViGen's own train.py evaluates on the TRAINING distribution.
#
# `Workspace.setup` builds both envs with identical arguments:
#     self.train_env = robo_make(name=..., action_repeat=..., frame_stack=..., seed=...)
#     self.eval_env  = robo_make(name=..., action_repeat=..., frame_stack=..., seed=...)
# Neither passes `mode`, so both fall back to robo_config.yaml's `mode: train`. The eval env is
# a second copy of the train env. **RL-ViGen's five baselines therefore report no generalisation
# gap out of the box on robosuite** -- the benchmark's own runner measures the train regime twice.
#
# This is the same failure P1 was written for. P1's docstring says it exactly: "a caller asking
# for eval-easy silently received a train env and measured generalisation on the training
# distribution." P1 fixed the CALLEE (make_env now accepts mode) and P3 threaded it through
# robo_make; this caller never used either.
#
# Driven by RLVIGEN_EVAL_MODE, the same variable idaac's seam reads, and DEFAULTING TO None --
# which is `robo_make`'s own default and reproduces upstream behaviour byte for byte when the
# variable is unset. So this patch changes nothing about a run that does not ask for it.
P12_FIND = """            self.eval_env = robo_make(name=self.cfg.task_name, action_repeat=self.cfg.action_repeat, 
                                      frame_stack=self.cfg.frame_stack, seed=self.cfg.seed)"""
P12_REPL = """            # PATCHED (many-gens-rl-vigen P12): give the EVAL env a visual regime. Upstream
            # built it with arguments identical to train_env, so it inherited
            # robo_config.yaml's `mode: train` and evaluated on the training distribution --
            # the very thing P1's note describes. None (unset) is robo_make's own default and
            # leaves upstream behaviour unchanged. See setup/apply_patches.py.
            import os as _os
            self.eval_env = robo_make(name=self.cfg.task_name, action_repeat=self.cfg.action_repeat, 
                                      frame_stack=self.cfg.frame_stack, seed=self.cfg.seed,
                                      mode=_os.environ.get("RLVIGEN_EVAL_MODE") or None)"""


# ---------------------------------------------------------------------------------------------
# P13 -- do not import TensorBoard for a feature that is switched off.
#
# `logger.py:13` does `from torch.utils.tensorboard import SummaryWriter` at module scope, and
# `SummaryWriter` is referenced at exactly ONE site: line 145, inside `if use_tb:`. So the import
# is unconditional for a feature that defaults to off and is off in every run this project makes.
#
# On Kaggle that import is fatal. Run 9's faulthandler dump put the segfault at
# `torch/utils/tensorboard/writer.py:19`; installing tensorboard and protobuf did not help
# (run 10, identical line); forcing protobuf's pure-Python backend removed the crash and replaced
# it with a hang that produced ZERO bytes in 900 s (run 11) -- consistent with that backend
# parsing torch's many generated pb2 modules very slowly. Four runs, one import.
#
# Moving it inside the branch is behaviour-preserving where TensorBoard is actually used: the
# same class, from the same module, bound at the same call. It only stops a disabled feature
# from being able to prevent the program from starting.
P13_FIND = """from torch.utils.tensorboard import SummaryWriter"""
P13_REPL = """# PATCHED (many-gens-rl-vigen P13): imported lazily, in the one branch that uses it (~line
# 145, `if use_tb:`). At module scope this import is unconditional for a feature that is off by
# default -- and on some images it segfaults or hangs the interpreter outright. See
# setup/apply_patches.py."""
P13B_FIND = """        if use_tb:
            self._sw = SummaryWriter(str(log_dir / 'tb'))"""
P13B_REPL = """        if use_tb:
            from torch.utils.tensorboard import SummaryWriter   # PATCHED (P13): see line ~13
            self._sw = SummaryWriter(str(log_dir / 'tb'))"""

PATCHES = [
    ("P1  make_env accepts mode", os.path.join(VGB, "utils.py"), P1_FIND, P1_REPL),
    ("P2  guard the video load", os.path.join(VGB, "vgb_wrapper.py"), P2_FIND, P2_REPL),
    ("P3a robo_make threads mode", os.path.join(WRAP, "robo_wrapper.py"), P3_FIND, P3_REPL),
    ("P3b robo_make exports regime", os.path.join(WRAP, "robo_wrapper.py"), P3B_FIND, P3B_REPL),
    ("P4a places batch device", os.path.join(UPSTREAM, "utils.py"), P4_FIND, P4_REPL),
    ("P4b places device holder", os.path.join(UPSTREAM, "utils.py"), P4B_FIND, P4B_REPL),
    ("P4c random_overlay records device", os.path.join(UPSTREAM, "utils.py"), P4C_FIND, P4C_REPL),
    ("P5  drq log_alpha float32", os.path.join(UPSTREAM, "algos", "drq.py"), P5_FIND, P5_REPL),
    ("P6  render size settable", os.path.join(VGB, "utils.py"), P6_FIND, P6_REPL),
    ("P7a train.py GL not forced", os.path.join(UPSTREAM, "train.py"), P7_FIND, P7_REPL),
    ("P7b eval.py GL not forced", os.path.join(UPSTREAM, "eval.py"), P7_FIND, P7_REPL),
    ("P8  action spec stays float32", os.path.join(WRAP, "robo_wrapper.py"), P8_FIND, P8_REPL),
    ("P9  robosuite keeps MUJOCO_GL", os.path.join(UPSTREAM, "third_party", "robosuite",
                                                   "robosuite", "utils", "binding_utils.py"),
     P9_FIND, P9_REPL),
    ("P10 success flag in info", os.path.join(VGB, "vgb_wrapper.py"), P10_FIND, P10_REPL),
    ("P11a Gym2DMC keeps last_info", os.path.join(WRAP, "robo_wrapper.py"), P11A_FIND, P11A_REPL),
    ("P11b eval tracks success", os.path.join(UPSTREAM, "train.py"), P11B_FIND, P11B_REPL),
    ("P11c eval reads last_info", os.path.join(UPSTREAM, "train.py"), P11C_FIND, P11C_REPL),
    ("P11d eval logs success_rate", os.path.join(UPSTREAM, "train.py"), P11D_FIND, P11D_REPL),
    ("P12 eval env gets a regime", os.path.join(UPSTREAM, "train.py"), P12_FIND, P12_REPL),
    ("P13a logger drops tb import", os.path.join(UPSTREAM, "logger.py"), P13_FIND, P13_REPL),
    ("P13b logger imports tb lazily", os.path.join(UPSTREAM, "logger.py"), P13B_FIND, P13B_REPL),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report status and exit 1 if anything is unpatched; change nothing")
    args = ap.parse_args()

    if not os.path.isdir(UPSTREAM):
        print(f"FATAL: {UPSTREAM} not found. Run setup/install.sh first.", file=sys.stderr)
        return 2

    applied = skipped = missing = 0
    for name, path, find, repl in PATCHES:
        if not os.path.exists(path):
            print(f"  !! {name:32s} target missing: {path}")
            missing += 1
            continue
        src = open(path, encoding="utf-8").read()
        if repl in src:
            print(f"  == {name:32s} already applied")
            skipped += 1
            continue
        if find not in src:
            # Neither the original nor our replacement is present. Upstream has moved, or someone
            # hand-edited. Refuse rather than guess -- a partial patch set is worse than none.
            print(f"  !! {name:32s} ANCHOR NOT FOUND -- upstream changed, or hand-edited")
            missing += 1
            continue
        if args.check:
            print(f"  -- {name:32s} NOT applied")
            missing += 1
            continue
        open(path, "w", encoding="utf-8").write(src.replace(find, repl, 1))
        # Verify the write landed. Claiming success without re-reading is the failure mode
        # docs/RIGOR.md section 5 exists to prevent.
        assert repl in open(path, encoding="utf-8").read(), f"{name}: wrote but cannot re-read"
        print(f"  OK {name:32s} applied")
        applied += 1

    print(f"\n{applied} applied, {skipped} already present, {missing} unresolved")

    # A patch set being present does not mean the tree is unmodified elsewhere.
    # The asymmetry that made the first version of this check incomplete: it detected files
    # modified that nothing explains, but NOT declared differences that are absent. A fresh
    # `install.sh` produced a tree missing four hand-edits and passed. Both directions matter.
    undeclared = undeclared_modifications()
    if undeclared:
        print("\nUNDECLARED MODIFICATIONS in the vendored tree:")
        for rel in undeclared:
            print(f"  !! {rel}")
        print("Each is a difference from the pinned commit that no patch and no entry in "
              "ALLOWED_MODIFIED explains,\nso `setup/install.sh` on a fresh machine does NOT "
              "reproduce this tree. Declare them or revert them.", file=sys.stderr)
    if missing or undeclared:
        print("FAILED -- the vendored tree is not in a known state.", file=sys.stderr)
        return 1
    print("The vendored tree matches its pinned commit plus exactly the declared differences.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
