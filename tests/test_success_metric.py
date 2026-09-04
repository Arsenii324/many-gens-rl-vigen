"""`SR: 0.0000` must be a measurement, not a placeholder.

This project has already been burned by that exact ambiguity. RL-ViGen's `logger.py` declares a
`('success_rate', 'SR', 'float')` column and only its **habitat** eval path ever fills it, so
every robosuite run printed `SR: 0.0000` — which reads as "measured zero" and was in fact "no
one wrote to this column". A metric that is always zero and a metric that is broken look
identical from the log.

So the check here is a red/green one: force `Door._check_success()` to return True at the
bottom of the stack and require the flag to arrive at the top. A test that only asserted
`success is False` on an untrained agent would pass just as happily against a hard-coded False.

Two paths are under test, because they are genuinely different plumbing:

  - **P10 + dmc_gb's chain** (`_RGBOnly` → `FrameStack`), which is what `rad` and `soda` run on,
    and which is a plain gym 4-tuple all the way out.
  - **P10 + P11 + RL-ViGen's own chain**, which converts to `dm_env` at `Gym2DMC` and therefore
    has NO room for `info` in its `TimeStep`. P11 exposes it as an attribute instead and relies
    on every wrapper above delegating unknown attributes. That delegation is the thing to check:
    if any wrapper in that chain ever stops delegating, `success` silently becomes False again
    and `SR` goes back to being a placeholder that reads as a measurement.

Marked slow: it builds a real robosuite environment (~20 s) and needs `runnable/dmc_gb/`, which
is ~200 MB and not in git.

**Why a probe that produces no RESULT line is a FAILURE and not a skip.** Until 2026-08-17 both
tests read `if line is None: pytest.skip(...)`, so *any* fault inside the probe — including one
caused by the very patches under test — was reported as a skip and read as a pass. An
independent audit flagged it, and it is the same defect `docs/REGISTER.md:104` already recorded
and removed by name elsewhere: "a blanket `except Exception: pytest.skip(...)` turned a real
import failure into a silent pass... Removed the guard entirely: if the base cannot be loaded,
the file has no meaning and must say so loudly." This file is the *only* thing establishing that
`SR` is a live measurement rather than a placeholder, so a silent pass here is worse here than
almost anywhere else in the suite. Both tests now fail with the probe's stderr attached.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DMCGB = ROOT / "runnable" / "dmc_gb"
RLV = ROOT / "RL-ViGen-upstream"


def no_result_is_a_failure(which: str, r) -> str:
    """The message for a probe that ran but produced no RESULT line.

    Deliberately not a skip. The probe subprocess printing nothing means the env could not be
    built, or a wrapper in the chain raised, or a patch under test broke it — and those are
    indistinguishable from here, which is exactly why the honest report is "this did not work"
    rather than "not applicable". The file-level `skipif` above still handles the one case that
    genuinely is not applicable: the clone being absent from the checkout.
    """
    return (f"the {which} probe produced no RESULT line, so nothing about the success metric "
            f"was checked. exit={r.returncode}\n"
            f"--- stderr (last 1500 chars) ---\n{r.stderr[-1500:]}\n"
            f"--- stdout (last 500 chars) ---\n{r.stdout[-500:]}")

pytestmark = pytest.mark.slow


PROBE = textwrap.dedent("""
    from env.wrappers import make_env
    env = make_env(domain_name='robosuite', task_name='Door', seed=0, episode_length=500,
                   action_repeat=1, frame_stack=3, mode='train')
    env.reset()
    _, _, _, info = env.step(env.action_space.sample())
    baseline = info.get('success')

    e = env
    while type(e).__name__ != 'VGBWrapper':
        e = e.env
    # P10 calls `self.env._check_success()` on the robosuite task, NOT on the wrapper -- patching
    # the wrapper instead silently does nothing and the test would pass for the wrong reason.
    inner = type(e.env).__name__
    e.env._check_success = lambda: True
    _, _, _, info2 = env.step(env.action_space.sample())
    print('RESULT', repr(baseline), repr(info2.get('success')), inner)
""")


@pytest.mark.skipif(not (DMCGB / "src" / "env" / "wrappers.py").exists(),
                    reason="runnable/dmc_gb clone absent (not tracked in git)")
def test_success_flag_travels_from_the_task_to_the_caller():
    env = {
        **os.environ,
        "RLVIGEN_ROOT": str(RLV),
        "RLVIGEN_IMAGE_SIZE": "100",
        "PYTHONPATH": os.pathsep.join([
            str(DMCGB / "src"), str(DMCGB / "src" / "env" / "dmc2gym"),
            str(RLV), str(RLV / "envs" / "robosuiteVGB")]),
    }
    env.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        env.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")

    r = subprocess.run([sys.executable, "-c", PROBE], cwd=DMCGB, env=env,
                       capture_output=True, text=True, timeout=900)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line is not None, no_result_is_a_failure("dmc_gb's chain", r)

    _, baseline, forced, inner = line.split(maxsplit=3)
    assert inner.strip() == "Door", (
        f"VGBWrapper wraps {inner!r}, not the robosuite task -- P10 calls _check_success on "
        "whatever this is, so the metric's source is not what this test thinks it is")
    assert baseline == "False", (
        f"an unforced step reported success={baseline}; either the task really succeeded on a "
        "random action (it does not) or the flag is hard-coded")
    assert forced == "True", (
        "forcing Door._check_success() to True did NOT reach the caller. info['success'] is "
        "therefore always False, and any success_rate computed from it is a placeholder that "
        "reads as a measured zero. Check RL-ViGen patch P10 and the wrapper chain.")


@pytest.mark.skipif(not (RLV / "wrappers" / "robo_wrapper.py").exists(),
                    reason="RL-ViGen-upstream absent")
def test_success_survives_rlvigens_own_dm_env_conversion():
    """P11: `last_info` must be readable on the OUTERMOST env, not just on Gym2DMC.

    `dm_env.TimeStep` is a 4-field NamedTuple with nowhere to put `info`, so P11 hangs it off
    the wrapper and depends on `__getattr__` delegation through ActionDTypeWrapper,
    ActionRepeatWrapper, dm_control's action_scale.Wrapper, FrameStackWrapper and
    ExtendedTimeStepWrapper. Five wrappers, any one of which could stop delegating.
    """
    probe = textwrap.dedent("""
        import numpy as np
        from wrappers.robo_wrapper import robo_make
        env = robo_make(name='Door', frame_stack=3, action_repeat=1, seed=0, scene_id=0,
                        mode='train')
        env.reset()
        zero = np.zeros(env.action_spec().shape, dtype=np.float32)
        env.step(zero)
        baseline = (getattr(env, 'last_info', None) or {}).get('success')
        e = env
        while type(e).__name__ != 'Gym2DMC':
            e = e._env
        e._gym_env.env._check_success = lambda: True
        env.step(zero)
        forced = (getattr(env, 'last_info', None) or {}).get('success')
        print('RESULT', repr(baseline), repr(forced))
    """)
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([
            str(RLV), str(RLV / "algos"), str(RLV / "envs" / "robosuiteVGB")]),
    }
    env.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        env.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    r = subprocess.run([sys.executable, "-c", probe], cwd=RLV, env=env,
                       capture_output=True, text=True, timeout=900)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line is not None, no_result_is_a_failure("RL-ViGen's own chain", r)
    _, baseline, forced = line.split()
    assert baseline == "False", f"unforced step reported success={baseline}"
    assert forced == "True", (
        "forcing Door._check_success() did not reach the outermost env. Some wrapper in "
        "RL-ViGen's dm_env chain stopped delegating attributes, so P11's last_info no longer "
        "arrives and the eval success_rate is a hard zero that reads as a measurement.")


# -- the positive control: can the signal fire at all, without being forced? -------------------

@pytest.mark.slow
@pytest.mark.parametrize("task", ["Door", "Lift"])
def test_the_success_criterion_can_actually_be_met(task):
    """Drive the SIMULATOR into a success state and check the flag arrives, unforced.

    The two tests above prove the flag PROPAGATES, by monkeypatching `_check_success` to return
    True. That is the right test for the plumbing and it says nothing about the task function:
    both would pass identically if `Door._check_success()` could never return True here -- wrong
    hinge address, wrong table height, a scene where the door cannot open.

    That mattered, because `scripts/probe_floor.py` found the flag had NEVER been observed firing
    in 25 random episodes on either task. "The task is hard" and "the signal is dead" produce the
    same log of zeros, and only a positive control separates them.

    So this leaves `_check_success` alone and moves the world instead -- Door's hinge past its own
    0.3 threshold, Lift's cube above its own table+0.04 -- then asserts three things that fail in
    different places: it was False before (not stuck True), the task function returns True, and
    the flag reaches the caller.

    Not a ceiling: attainable-in-the-simulator is not attainable-by-a-policy.
    """
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from scripts.probe_success_control import _setup_env_path, drive_to_success, find_task
    _setup_env_path()
    os.environ["RLVIGEN_IMAGE_SIZE"] = "84"
    import robosuitevgb.utils as ru

    env = ru.make_env(task_name=task, seed=0, scene_id=0, mode="train")
    env.reset()
    zero = np.zeros(np.shape(env.action_space.sample()))
    _, _, _, info0 = env.step(zero)
    assert not bool((info0 or {}).get("success", False)), (
        f"{task} reports success on a zero action before any intervention -- a stuck True would "
        "make every success rate meaningless in the opposite direction")

    inner, chain = find_task(env)
    assert inner is not None, f"could not reach the robosuite task; chain: {' -> '.join(chain)}"
    note = drive_to_success(inner, task)
    assert inner._check_success(), (
        f"{task}._check_success() is False after {note}. The task's own criterion cannot be met "
        "in this configuration, so a reported success rate of 0.000 would be uninterpretable.")
    _, _, _, info1 = env.step(zero)
    assert bool((info1 or {}).get("success", False)), (
        f"{task}._check_success() is True but the flag does not reach the caller after {note} -- "
        "P10/P11 carry it, so this is a plumbing regression rather than a task one")
