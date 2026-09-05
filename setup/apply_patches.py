#!/usr/bin/env python3
"""Apply this repo's edits to the vendored RL-ViGen checkout.

RL-ViGen is not importable as a library and is too large to vendor into git (1.8 GB), so it is
cloned by `setup/install.sh` and patched here. These declared edits are the difference between
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
import re
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


def undeclared_modifications() -> list[str] | None:
    """Files modified in the vendored tree that neither a patch nor ALLOWED_MODIFIED explains.

    Untracked paths are judged separately, against ALLOWED_UNTRACKED -- see its note.
    """
    import subprocess

    # [Claude 2026-09-04] **This check must confirm which repository it is talking to, and until
    # today it did not.** `git -C <dir> status` walks UP to the nearest enclosing repository. In
    # this recovery workspace `RL-ViGen-upstream` is unpacked from the rlvigen tarball input and
    # has no `.git` of its own, so:
    #   * before the workspace was put under version control, the command FAILED, this function
    #     returned [] on the error path, and the check silently passed on every run since
    #     2026-08-31 -- inert, and indistinguishable from clean;
    #   * the moment a repository existed at the project root, the command SUCCEEDED against the
    #     wrong tree and reported the project's own edited docs as "undeclared modifications in
    #     the vendored tree".
    # One assumption -- "UPSTREAM is its own repository" -- produced a silent false negative for
    # weeks and then a loud false positive. It is now checked, and an abstention is ANNOUNCED
    # rather than returned as an empty list, because a guard that cannot run and a guard that
    # found nothing must not look the same. That confusion is this project's signature join
    # defect; see STEP-ZERO section 8.
    try:
        top = subprocess.run(["git", "-C", UPSTREAM, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        top = None
    resolved = (top.stdout.strip() if top and top.returncode == 0 else "")
    if os.path.realpath(resolved or os.devnull) != os.path.realpath(UPSTREAM):
        print(f"  ?? undeclared-modification check ABSTAINED: {UPSTREAM} is not the root of its "
              f"own git repository (git resolves it to {resolved or 'no repository'}), so a "
              "porcelain listing there describes a different tree. This is not a pass.",
              file=sys.stderr)
        return None
    try:
        out = subprocess.run(["git", "-C", UPSTREAM, "status", "--porcelain"],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if out.returncode != 0:
        return None
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
        info["success"] = bool(self.env._check_success())
        # PATCHED (many-gens-rl-vigen P20): retain the raw reward at the env boundary so vector
        # normalisers can still emit truthful per-episode reward summaries.
        info["_native_raw_reward"] = float(reward)
        # PATCHED (many-gens-rl-vigen P20): retain bounded, per-episode diagnostics.  The action
        # reaching the robosuite controller is clipped to its declared input range; recording both
        # sides makes the amount of clipping observable without changing the policy path.
        raw_action = np.asarray(action, dtype=float)
        action_low, action_high = self.env.action_spec
        executed_action = np.clip(raw_action, action_low, action_high)
        delta = np.abs(raw_action - executed_action)
        self._episode_rewards.append(float(reward))
        self._episode_steps += 1
        self._episode_clip_coordinates += int(np.count_nonzero(delta > 1e-12))
        self._episode_clip_vectors += int(np.any(delta > 1e-12))
        self._episode_raw_executed_l1 += float(delta.sum())
        self._episode_raw_min = min(self._episode_raw_min, float(raw_action.min()))
        self._episode_raw_max = max(self._episode_raw_max, float(raw_action.max()))
        if info["success"] and self._episode_first_success is None:
            self._episode_first_success = self._episode_steps
        if done:
            rewards = np.asarray(self._episode_rewards, dtype=float)
            self.episode_diagnostics.append({
                "episode_length": self._episode_steps,
                "termination_reason": "time_limit" if self.step_count >= self._max_episode_steps else "terminal",
                "time_to_success": self._episode_first_success,
                "reward_sum": float(rewards.sum()),
                "reward_mean": float(rewards.mean()),
                "reward_min": float(rewards.min()),
                "reward_max": float(rewards.max()),
                "initial_placement": self.last_initial_placement,
                "applied_mode": self._mode,
                "applied_scene_id": self._scene_id,
                "action_clip_rate_coordinate": float(self._episode_clip_coordinates /
                                                       max(1, self._episode_steps * raw_action.size)),
                "action_clip_rate_vector": float(self._episode_clip_vectors /
                                                  max(1, self._episode_steps)),
                "action_raw_executed_l1": self._episode_raw_executed_l1,
                "action_raw_min": self._episode_raw_min,
                "action_raw_max": self._episode_raw_max,
            })"""


# ---------------------------------------------------------------------------------------------
# P20 -- expose the realized object pose after reset.
#
# The global NumPy stream is what samples Door's placement, but a seed is not data: a future
# analysis needs the pose that was actually applied, especially because the vendored Door reset
# samples twice.  The wrapper is the common boundary for all seven evaluator families, and the
# value below is read only after the final sim.forward().  It does not alter the trajectory.
P20_FIND = """        self.env.sim.forward()
        return self._reformat_obs(self.env._get_observations(force_update=True))"""
P20_REPL = """        self.env.sim.forward()
        # PATCHED (many-gens-rl-vigen P20): retain the realized post-reset object pose.  A hash
        # alone proves pairing but cannot support a later performance-versus-placement analysis.
        placement = {}
        root_body = getattr(getattr(self.env, "door", None), "root_body", None)
        if root_body is not None:
            body_id = self.env.sim.model.body_name2id(root_body)
            placement["door_root_body"] = root_body
            placement["body_pos"] = np.asarray(self.env.sim.model.body_pos[body_id], dtype=float).tolist()
            placement["body_quat"] = np.asarray(self.env.sim.model.body_quat[body_id], dtype=float).tolist()
        else:
            # Keep the patch useful for other robosuite tasks without guessing a task-specific
            # object name.  Door is the production scope and takes the branch above.
            for label, body_id in getattr(self.env, "object_body_ids", {}).items():
                placement[str(label)] = {
                    "body_pos": np.asarray(self.env.sim.model.body_pos[body_id], dtype=float).tolist(),
                    "body_quat": np.asarray(self.env.sim.model.body_quat[body_id], dtype=float).tolist(),
                }
        self.last_initial_placement = placement
        # Keep bounded summaries at the common environment boundary.  Vector wrappers may
        # auto-reset immediately after a terminal step, so the completed list intentionally
        # survives reset and is read by the evaluator after the cell finishes.
        if not hasattr(self, "episode_diagnostics"):
            self.episode_diagnostics = []
        self._episode_rewards = []
        self._episode_steps = 0
        self._episode_first_success = None
        self._episode_clip_coordinates = 0
        self._episode_clip_vectors = 0
        self._episode_raw_executed_l1 = 0.0
        self._episode_raw_min = float("inf")
        self._episode_raw_max = float("-inf")
        return self._reformat_obs(self.env._get_observations(force_update=True))"""




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

P11B_FIND = """    def _eval_single(self):
        step, episode, total_reward = 0, 0, 0
        eval_until_episode = utils.Until(self.cfg.num_eval_episodes)"""
P11B_REPL = """    def _eval_single(self):
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

# ---------------------------------------------------------------- P14 (C45 + C43)
# ONE patch, because it is one change to one loop. C45 and C43 were separate register entries and
# are not separate edits: the protocol certifies ten evaluation scenes and `train.py` evaluated
# scene 0 forever, and retention needs a train-regime denominator that nothing built. Both are
# answered by making `eval()` choose WHICH distribution it evaluates.
#
# ENABLES-class. It changes what is measured, not merely what is recorded about it, so every
# number produced with it active is ours and `Protocol.env_patches` carries it into the hash --
# numbers from before and after cannot be silently pooled.
#
# Upstream's own `eval.py:178-184` already sweeps scenes (`scene_id=count`, ten episodes each);
# `train.py` never did. This makes the training loop's evaluation match the offline evaluator and
# the protocol, rather than inventing a third convention.
#
# The original loop is PRESERVED byte-for-byte as `_eval_single` and still runs for `dmc` and
# `habitat`, which have no scene axis. Only the robosuite path, which builds `_make_eval_env`,
# takes the new route.
P14A_FIND = """                                      mode=_os.environ.get("RLVIGEN_EVAL_MODE") or None)"""
P14A_REPL = """                                      mode=_os.environ.get("RLVIGEN_EVAL_MODE") or None)
            # PATCHED (many-gens-rl-vigen P14): keep the recipe, so eval() can rebuild the env
            # per scene and per regime instead of being stuck with the one built here.
            self._eval_mode = _os.environ.get("RLVIGEN_EVAL_MODE") or None
            self._make_eval_env = lambda _mode, _scene: robo_make(
                name=self.cfg.task_name, action_repeat=self.cfg.action_repeat,
                frame_stack=self.cfg.frame_stack, seed=self.cfg.seed,
                mode=_mode, scene_id=_scene)"""

P14B_FIND = """    def eval(self):
        step, episode, total_reward = 0, 0, 0"""
P14B_REPL = """    def eval(self):
        \"\"\"PATCHED (many-gens-rl-vigen P14). Sweep the certified scenes; measure both regimes.

        `dmc` and `habitat` have no scene axis and keep the original loop, unchanged, below.
        \"\"\"
        if not hasattr(self, '_make_eval_env'):
            return self._eval_single()
        scenes = [int(x) for x in (os.environ.get('RLVIGEN_EVAL_SCENES')
                                   or '0,1,2,3,4,5,6,7,8,9').split(',') if x.strip()]
        per = max(1, self.cfg.num_eval_episodes // max(1, len(scenes)))
        # The reported number: the eval regime, averaged over the ten certified scenes.
        rep = self._eval_regime(self._eval_mode, scenes, per)
        # The denominator for retention: the TRAINING distribution, which is scene 0 in the train
        # regime. It is deliberately not swept -- sweeping it would measure something the agent
        # was never trained on and make the ratio uninterpretable.
        den = self._eval_regime('train', scenes[:1], per)
        with self.logger.log_and_dump_ctx(self.global_frame, ty='eval') as log:
            log('episode_reward', rep['reward'])
            log('episode_length', rep['length'])
            log('episode', self.global_episode)
            log('step', self.global_step)
            log('success_rate', rep['success'])
            log('train_regime_reward', den['reward'])
            log('train_regime_success', den['success'])

    def _eval_regime(self, mode, scene_ids, episodes_per_scene):
        \"\"\"[OURS P14] One visual regime, averaged over `scene_ids` x `episodes_per_scene`.\"\"\"
        step, episode, total_reward, success_rate = 0, 0, 0.0, 0.0
        for scene_id in scene_ids:
            env = self._make_eval_env(mode, scene_id)
            for _ in range(episodes_per_scene):
                time_step = env.reset()
                self.video_recorder.init(env, enabled=(episode == 0))
                succeeded = False
                while not time_step.last():
                    with torch.no_grad(), utils.eval_mode(self.agent):
                        action = self.agent.act(time_step.observation,
                                                self.global_step,
                                                eval_mode=True)
                    time_step = env.step(action)
                    succeeded = succeeded or bool(
                        (getattr(env, 'last_info', None) or {}).get('success', False))
                    self.video_recorder.record(env)
                    total_reward += time_step.reward
                    step += 1
                episode += 1
                success_rate += float(succeeded)
                self.video_recorder.save(f'{self.global_frame}.mp4')
        n = max(1, episode)
        return {'reward': total_reward / n,
                'length': step * self.cfg.action_repeat / n,
                'success': success_rate / n}

    def _eval_single(self):
        step, episode, total_reward = 0, 0, 0"""

# [Codex 2026-09-01 16:24 MSK: P15 adds endpoint-only evaluation and retention after a finite train loop whose periodic check occurs before stepping]
P15_FIND = """            self._global_step += 1

    def save_snapshot(self):"""
P15_REPL = """            self._global_step += 1

        # [Codex 2026-09-01 16:24 MSK: evaluate and retain the exact finite-run endpoint without adding another training step]
        if self.global_frame == self.cfg.num_train_frames:
            if self.cfg.env == 'habitat':
                self.habi_eval()
            else:
                self.eval()
                if self.cfg.save_snapshot:
                    self.save_snapshot()
            print(f'NATIVE_FINAL_EVALUATION_COMPLETED frame={self.global_frame}')

    def save_snapshot(self):"""


# [Claude 2026-09-02 01:30 MSK: P17 removes a crash that only fires when tensorboard logging is on]
# ---------------------------------------------------------------- P17
# `algos/drq.py`'s actor update ends with
#     metrics['actor_ent'] = dist.entropy().sum(dim=-1).mean().item()
# and on THIS agent that line always raises. DrQ's actor returns a `SquashedNormal`, which is a
# `torch.distributions.TransformedDistribution`; the base class's `entropy()` raises
# NotImplementedError, and no closed form exists for a tanh-squashed Gaussian.
#
# It is guarded by `if self.use_tb:`, so it is a crash you only meet once logging is on. This
# project's launcher forces `use_tb=True` (since 2026-08-20, because docs/TASK.md R7 makes the
# tensorboard log part of the deliverable), so the FIRST actor update of every drq run dies --
# at frame `num_seed_frames`, long before any endpoint. The 2026-08-17 smoke that recorded drq
# as TRAINED ran before that flag existed, which is exactly why nothing caught it.
# Reproduced 2026-09-02 on a real 2,000-frame Door run: NotImplementedError at drq.py:328.
#
# No substitute metric is invented. `actor_logprob`, which upstream already logs on the line
# above, carries the same signal for this agent: `log_prob` is summed over action dimensions and
# includes the tanh Jacobian term, so `-actor_logprob` IS the Monte-Carlo entropy of the squashed
# policy. That is a genuinely DIFFERENT quantity from the analytic Gaussian `actor_ent` that
# drqv2/svea/sgqn/curl log, and it keeps a different name for that reason rather than being
# unified into one column that would mean two things.
#
# PLATFORM: drq's learning is byte-identical with and without this patch. Only the crash goes.
P17_FIND = """        if self.use_tb:
            metrics['actor_loss'] = actor_loss.item()
            metrics['actor_logprob'] = log_prob.mean().item()
            metrics['actor_ent'] = dist.entropy().sum(dim=-1).mean().item()"""
P17_REPL = """        if self.use_tb:
            metrics['actor_loss'] = actor_loss.item()
            # PATCHED (many-gens-rl-vigen P17): upstream's third line here was
            #     metrics['actor_ent'] = dist.entropy().sum(dim=-1).mean().item()
            # and it raises NotImplementedError on every call: this agent's actor returns a
            # SquashedNormal (a TransformedDistribution), which has no closed-form entropy.
            # -actor_logprob below is this agent's entropy signal, and is deliberately not
            # renamed to actor_ent -- it is the Monte-Carlo entropy of a squashed policy, not
            # the analytic Gaussian entropy drqv2/svea/sgqn/curl report under that name.
            metrics['actor_logprob'] = log_prob.mean().item()"""


# [Claude 2026-09-02 11:30 MSK: P18 keeps the intermediate checkpoints a long run already writes]
# ---------------------------------------------------------------- P18
# Upstream saves a snapshot at every episode boundary where `global_step % 50_000 == 0`, and every
# one of those writes to the SAME `snapshot.pt`. A 500k run therefore performs ten checkpoint saves
# and keeps one. That is a real loss: the ten it discards are a budget curve -- the same policy at
# 50k, 100k, ... 500k -- and evaluating them offline costs no training at all. Recovering it later
# means retraining.
#
# Off by default, because it is disk: twelve DrQ-v2 snapshots are 3.4 GiB and twelve DrQ ones are
# 6.5 GiB against 20.2 GiB free in the container, and packed cells multiply that. The runner sets
# it per job, and sets it to a CADENCE rather than a flag so the curve's resolution and its cost
# are the same dial.
#
# This is not a background watcher copying a file when its mtime changes: that races with the write
# it is watching. It is one more `torch.save` inside the function that already saved, so a
# step-stamped file is complete when it exists.
#
# ENABLES-class: it changes what is retained, not what is learned. The training is byte-identical.
#
# MAINTENANCE NOTE, earned the expensive way: P18_REPL below is matched BYTE-FOR-BYTE against
# `save_snapshot()`. That function is now also where `runnable/_shim/safe_checkpoint` gets wired in
# (2026-09-05), and every edit to safe-checkpoint behavior inside `save_snapshot()` broke this exact
# anchor -- five times in one session. DETECTION never failed once: `tests/test_contract.py::
# test_upstream_patches_are_applied` runs this file's own `--check` and caught every one via the
# ordinary suite, no manual step needed. What was wasteful was the ROUND TRIP -- edit, run the
# suite, get told it broke, fix the anchor, re-run -- five times, for a fix that is one paragraph
# and could have landed in the same edit that caused it. The byte-exact match itself is correct and
# should stay (P18's job is proving the vendored tree matches its pinned commit plus exactly the
# declared differences, which needs exact bytes). The fix is procedural: editing `save_snapshot()`
# for ANY reason means updating P18_REPL in THE SAME edit, before running anything.
P18_FIND = """    def save_snapshot(self):
        snapshot = self.work_dir / 'snapshot.pt'
        keys_to_save = ['agent', 'timer', '_global_step', '_global_episode']
        payload = {k: self.__dict__[k] for k in keys_to_save}
        with snapshot.open('wb') as f:
            torch.save(payload, f)"""
P18_REPL = """    def save_snapshot(self):
        snapshot = self.work_dir / 'snapshot.pt'
        keys_to_save = ['agent', 'timer', '_global_step', '_global_episode']
        payload = {k: self.__dict__[k] for k in keys_to_save}
        try:
            from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS
        except ImportError:
            TERMINAL_MAX_WAIT_SECONDS = 1800
            def safe_torch_save(obj, path, torch_kwargs=None, **_kwargs):
                import torch as _torch
                _torch.save(obj, path, **(torch_kwargs or {}))
                return True
        terminal = self.global_frame == self.cfg.num_train_frames
        wait_kwargs = {"max_wait_seconds": TERMINAL_MAX_WAIT_SECONDS} if terminal else {}
        ok = safe_torch_save(payload, snapshot, label="rlvigen.snapshot", **wait_kwargs)
        # Codex, mailbox Q18(b): save_snapshot is called from three places -- two periodic
        # (episode-boundary logging, the 50k cadence below) and one true terminal (the caller's own
        # `global_frame == num_train_frames` check). All three write the SAME fixed `snapshot.pt`.
        # Fail CLOSED only for the terminal call: a periodic skip costs one point on a curve; a
        # terminal skip leaves the fixed name the offline evaluator always reads either missing or
        # stale, while the run still exits 0.
        if terminal and not ok:
            raise RuntimeError(
                "rlvigen's terminal snapshot.pt write failed -- the run cannot produce a usable "
                "terminal checkpoint. Exiting rather than reporting success over a missing or "
                "stale one.")
        # PATCHED (many-gens-rl-vigen P18): keep the intermediate checkpoints this loop already
        # writes and then overwrites. Upstream saves whenever `global_step % 50_000 == 0` -- a
        # cadence that is hardcoded, not configurable -- and every save overwrites the same file,
        # so a 600k run performs twelve saves and keeps one. The eleven it discards are a budget
        # curve that costs no training to evaluate and a full retrain to recover.
        #
        # The variable is a CADENCE, not a flag, because keeping all twelve is 3.4 GiB for drqv2
        # and 6.5 GiB for drq, per cell, against 20.2 GiB free in the container. Unset keeps none;
        # an integer keeps the saves at multiples of it; any other truthy value keeps all of them.
        # The endpoint is always stamped when anything is: a budget curve missing its last point
        # is not a budget curve.
        preserve = os.environ.get('RLVIGEN_PRESERVE_SNAPSHOTS', '').strip()
        if preserve:
            cadence = int(preserve) if preserve.isdigit() and int(preserve) > 0 else 0
            if not cadence or terminal or self.global_frame % cadence == 0:
                stamped = self.work_dir / f'snapshot_{self.global_frame}.pt'
                safe_torch_save(payload, stamped, label="rlvigen.stamped_snapshot")"""



# [Claude 2026-09-03 MSK: P19 stops the places365 loader corrupting the heap on a 4-CPU container]
# ---------------------------------------------------------------- P19
# `sgqn` is the only baseline of twelve that could not complete a pre-production cell. It reached
# F: 5000 of 10,000 twice and died both times with a DataLoader worker `Aborted` -- at 3.77 GB RSS
# on a 32 GB tier, so not OOM. With `replay_buffer_num_workers=0` the fault became legible and was
# somewhere else entirely:
#
#   malloc_consolidate(): unaligned fastbin chunk detected
#   sgqn.py:242 update -> update_aux -> random_overlay -> utils.py:208 _get_places_batch
#
# That is glibc heap corruption, and the DataLoader aborting is the PLACES365 one, not the replay
# buffer -- a different loader that the replay override never touched. `_load_places` hardcodes
# `num_workers=8` with `pin_memory=True`, and the container reports `logical_cpu_count: 4`. Eight
# JPEG-decoding workers on four CPUs, drawn from on every update.
#
# **Why only `sgqn`, when `svea` and `soda` also use places365 and both passed**: `sgqn.update`
# calls `random_overlay` an EXTRA time inside `update_aux`, so it pulls places batches roughly
# twice as often and is the one that loses the race.
#
# The default becomes an environment read rather than a fixed number, so the fix is a dial the
# runner sets per job and not a new hardcoded constant replacing an old one. Unset preserves
# upstream's 8 exactly, so no other baseline's behaviour moves.
#
# PLATFORM-class: it changes how images are fetched, never which images or in what order --
# `shuffle=True` draws from the same generator whatever the worker count, and the seeding is
# unchanged. A run at 0 workers and a run at 8 differ in scheduling, not in data.
P19_FIND = """				batch_size=batch_size, shuffle=True,
				num_workers=num_workers, pin_memory=True)"""
P19_REPL = """				batch_size=batch_size, shuffle=True,
				# PATCHED (many-gens-rl-vigen P19): upstream passes the signature's default of 8. On a
				# 4-CPU container that corrupts the heap under sgqn's doubled draw rate --
				# `malloc_consolidate(): unaligned fastbin chunk detected`, twice, at 3.77 GB of 32 GB.
				# The dial is read HERE and not in the signature, because
				# `datasphere/native/configure_places365_val.py` rewrites the signature line to select
				# the val partition and fails on any form it does not recognise -- which is exactly how
				# the first version of this patch was rejected. Unset keeps upstream's value.
				num_workers=int(__import__("os").environ.get("RLVIGEN_PLACES_WORKERS", num_workers)),
				pin_memory=True)"""


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
    ("P20 realized placement in reset", os.path.join(VGB, "vgb_wrapper.py"), P20_FIND, P20_REPL),
    # =========================================================================================
    # PATCH ORDERING REQUIREMENTS (Audited & Fixed by Gemini, 2026-08-31):
    #
    # 1. P12 MUST PRECEDES P14a:
    #    P12 creates the `mode=_os.environ.get("RLVIGEN_EVAL_MODE") or None)` line in `train.py`.
    #    P14a uses that exact line as its search anchor to attach `self._make_eval_env`.
    #    On a fresh clone from GitHub, running P14a before P12 fails with ANCHOR NOT FOUND.
    #
    # 2. P14b MUST PRECEDES P11b:
    #    P14b renames `eval` to `_eval_single`, and P11b patches that renamed method by name.
    #
    # STATED ORDER OF EXECUTION FOR train.py: P7a -> P12 -> P14a -> P14b -> P11b -> P11c -> P11d
    # =========================================================================================
    ("P12 eval env gets a regime", os.path.join(UPSTREAM, "train.py"), P12_FIND, P12_REPL),
    ("P14a eval env recipe kept", os.path.join(UPSTREAM, "train.py"),
     P14A_FIND, P14A_REPL),
    ("P14b eval sweeps scenes + train regime", os.path.join(UPSTREAM, "train.py"),
     P14B_FIND, P14B_REPL),
    ("P11a Gym2DMC keeps last_info", os.path.join(WRAP, "robo_wrapper.py"), P11A_FIND, P11A_REPL),
    ("P11b eval tracks success", os.path.join(UPSTREAM, "train.py"), P11B_FIND, P11B_REPL),
    ("P11c eval reads last_info", os.path.join(UPSTREAM, "train.py"), P11C_FIND, P11C_REPL),
    ("P11d eval logs success_rate", os.path.join(UPSTREAM, "train.py"), P11D_FIND, P11D_REPL),
    ("P13a logger drops tb import", os.path.join(UPSTREAM, "logger.py"), P13_FIND, P13_REPL),
    ("P13b logger imports tb lazily", os.path.join(UPSTREAM, "logger.py"), P13B_FIND, P13B_REPL),
    ("P15 terminal eval + snapshot", os.path.join(UPSTREAM, "train.py"), P15_FIND, P15_REPL),
    ("P17 drq actor entropy crash", os.path.join(UPSTREAM, "algos", "drq.py"), P17_FIND, P17_REPL),
    ("P18 keep intermediate snapshots", os.path.join(UPSTREAM, "train.py"), P18_FIND, P18_REPL),
    ("P19 places loader worker dial", os.path.join(UPSTREAM, "utils.py"), P19_FIND, P19_REPL),
]

# --- what kind of change each patch is -------------------------------------------------------
#
# The registry says WHAT changed and `Protocol.env_patches` hashes the set, so any number can be
# traced to the patches present when it was produced. What neither says is what kind of change it
# was -- and that is the distinction that decides whether a number is attributable to RL-ViGen or
# to us. Three classes:
#
#   PLATFORM  needed for this machine or stack to run at all. Device, dtype, GL, imports. Changes
#             nothing about what is measured; a number produced with these is still theirs.
#   RESTORES  makes upstream's own declared intent reachable where its code did not deliver it.
#             `mode` existed in their config and never reached the env; `train` crashed on a
#             missing asset directory. The number moves TOWARD what they intended.
#   ENABLES   adds or changes what is measured. The number is ours, and no longer comparable to
#             one produced without the patch.
#
# The line between a fidelity run and a constructed one is the ENABLES set, and it was crossed
# before P14 was ever proposed: success rate is not emitted by upstream at all (P10, P11) and the
# render resolution is fixed at 84 in their config (P6), so RAD and SODA cannot run at their
# papers' 100 without us. What P14 would add is different in kind again -- the first patch that
# changes WHICH DISTRIBUTION is evaluated rather than what is recorded about it.
PATCH_CLASS = {
    "P1":  "RESTORES",   # a caller asking for eval-easy silently received a train env
    "P2":  "RESTORES",   # upstream loaded the background video for every mode; train has no assets
    "P3":  "RESTORES",   # threads mode through robo_make, and exports the resolved regime
    "P4":  "PLATFORM",   # Places365 batch device
    "P5":  "PLATFORM",   # MPS has no float64
    "P6":  "ENABLES",    # render size settable: RAD/SODA are specified at 100, their config fixes 84
    "P7":  "PLATFORM",   # do not force a GL backend
    "P8":  "PLATFORM",   # action spec stays float32
    "P9":  "PLATFORM",   # robosuite keeps MUJOCO_GL
    "P10": "ENABLES",    # success flag into info -- upstream emits no success on this path
    "P11": "ENABLES",    # success accumulated and logged: the unit-free endpoint is ours
    "P12": "RESTORES",   # eval env gets a regime; theirs built two copies of the train env
    "P13": "PLATFORM",
    "P14": "ENABLES",   # changes WHICH distribution is evaluated: ten scenes, and
                        # a train-regime denominator that did not exist before   # tensorboard import made lazy
    # [Codex 2026-09-01 16:24 MSK: classify P15 as candidate measurement and retention behavior rather than pure upstream fidelity]
    "P15": "ENABLES",
    # [Claude 2026-09-02 01:30 MSK: P17 deletes an always-raising logging line; drq's learning is
    # byte-identical with and without it, so a number produced under it is still upstream's]
    "P17": "PLATFORM",
    # [Claude 2026-09-02 11:30 MSK: P18 retains checkpoints the loop already wrote; training is
    # byte-identical with and without it, but what a run leaves behind is not]
    "P18": "ENABLES",
    # [Claude 2026-09-03 MSK: P19 makes the places365 loader's worker count an env dial. PLATFORM
    # and not ENABLES, deliberately: worker count changes SCHEDULING, never which images are drawn
    # nor in what order -- `shuffle=True` draws from the same generator at any worker count and the
    # seeding is untouched. So a number produced with it is still upstream's, which is the whole
    # test for this class. Unset preserves upstream's 8 exactly.
    #
    # Declared here and not only in PATCHES because `highest_patch_id()` reads THIS dict: a patch
    # missing from it is invisible to the id checker, which is how P19 shipped while four documents
    # still said the registry topped out at P18.]
    "P19": "PLATFORM",
    "P20": "PLATFORM",   # records post-reset pose; it does not alter the environment trajectory
}


def patch_family(name):
    """`P11c eval reads last_info` -> `P11`."""
    return re.match(r"(P\d+)", name).group(1)


def classify_patches():
    """{class: [family, ...]} over the registry, so a caller never has to keep the list."""
    out = {}
    for name, *_ in PATCHES:
        fam = patch_family(name)
        out.setdefault(PATCH_CLASS.get(fam, "UNCLASSIFIED"), set()).add(fam)
    return {k: sorted(v, key=lambda f: int(f[1:])) for k, v in out.items()}


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
    by_class = classify_patches()
    print("\nby kind of change  (PLATFORM: theirs still · RESTORES: toward their intent · "
          "ENABLES: ours)")
    for cls in ("PLATFORM", "RESTORES", "ENABLES", "UNCLASSIFIED"):
        fams = by_class.get(cls)
        if fams:
            print(f"  {cls:<14}{', '.join(fams)}")
    ours = by_class.get("ENABLES", [])
    if ours:
        print(f"\nA number produced with {', '.join(ours)} active is not a pure-fidelity number:")
        print("  those patches change what is measured, not how it is reached.")

    # A patch set being present does not mean the tree is unmodified elsewhere.
    # The asymmetry that made the first version of this check incomplete: it detected files
    # modified that nothing explains, but NOT declared differences that are absent. A fresh
    # `install.sh` produced a tree missing four hand-edits and passed. Both directions matter.
    undeclared = undeclared_modifications()
    if undeclared is None:
        print("SOURCE_ORIGIN_UNKNOWN -- cannot certify the vendored tree's source origin: the "
              "nested repository check abstained. Static post-patch evaluator identity remains "
              "a separate proof; this is not a source-origin certificate.", file=sys.stderr)
        if os.environ.get("NATIVE_REQUIRE_SOURCE_ORIGIN") == "1":
            print("FAILED -- source-origin certification was explicitly required.", file=sys.stderr)
            return 3 if args.check else 1
        undeclared = []
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
