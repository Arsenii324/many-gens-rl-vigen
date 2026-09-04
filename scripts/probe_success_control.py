#!/usr/bin/env python3
"""Can the success signal fire AT ALL in our configuration, without being forced?

    python scripts/probe_success_control.py

This is the positive control for `docs/CONSTRUCTION.md` C17, and it exists because the floor
probe could not answer the question it was run to answer.

## Why a floor was not enough

`scripts/probe_floor.py` ran 25 random episodes on Door and Lift. Both scored 0/25 and, more
importantly, the flag was **never observed firing**. That is the expected result and it is
uninterpretable on its own: "the task is hard" and "the success signal is dead in this
configuration" produce an identical log of zeros. A negative control with no positive control
cannot separate them — the single most common way correct code yields an unsupported conclusion.

## What this does that `tests/test_success_metric.py` does not

That test proves the flag *propagates*, by monkeypatching `_check_success` to return `True`. That
is the right test for the plumbing above the task, and it deliberately says nothing about the
task function itself. It would pass identically if `Door._check_success()` could never return
True in our env — wrong table height, wrong hinge address, a scene where the door cannot open.

So this drives the **simulator** into a success state and leaves `_check_success` alone:

    Door   sim.data.qpos[hinge_qpos_addr] = 0.5     (its own threshold is > 0.3)
    Lift   cube free-joint z raised above table     (its own threshold is table + 0.04)

Then it steps normally and asks three separate questions, because they fail in different places:

    1. does `_check_success()` itself return True?      -- the task function is alive
    2. does the flag reach the caller's `info`?         -- P10/P11 plumbing carries it
    3. was it False before the intervention?            -- we are not reading a stuck True

A stuck `True` would make every success rate meaningless in the opposite direction, so (3) is not
a formality.

## What this cannot tell you

That success is *reachable by a policy*. It establishes the signal is live and the threshold
attainable in principle. Whether an agent can get there at an affordable budget is the ceiling
question, and it needs a trained or scripted policy.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

import numpy as np


def _setup_env_path() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    rlv = root / "RL-ViGen-upstream"
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for p in (str(rlv), str(rlv / "envs" / "robosuiteVGB")):
        if p not in sys.path:
            sys.path.insert(0, p)


def find_task(env):
    """Walk out to the robosuite task -- the object that owns `_check_success` and `sim`."""
    chain, e = [], env
    for _ in range(20):
        chain.append(type(e).__name__)
        if hasattr(e, "_check_success") and hasattr(e, "sim"):
            return e, chain
        nxt = getattr(e, "env", None) or getattr(e, "_env", None)
        if nxt is None or nxt is e:
            break
        e = nxt
    return None, chain


def drive_to_success(task, name) -> str:
    """Put the simulator in a state the task's OWN criterion calls success. Returns a note."""
    if name == "Door":
        addr = task.hinge_qpos_addr
        task.sim.data.qpos[addr] = 0.5           # its threshold is > 0.3
        task.sim.forward()
        return f"qpos[hinge]=0.5 (threshold >0.3), read back {task.sim.data.qpos[addr]:.3f}"
    if name == "Lift":
        table_z = task.model.mujoco_arena.table_offset[2]
        target = table_z + 0.25                  # its threshold is table + 0.04
        # the cube is a free body: its joint qpos is [x,y,z,qw,qx,qy,qz]
        jname = task.cube.joints[0]
        q = np.array(task.sim.data.get_joint_qpos(jname)).copy()
        q[2] = target
        task.sim.data.set_joint_qpos(jname, q)
        task.sim.forward()
        got = task.sim.data.body_xpos[task.cube_body_id][2]
        return f"cube z -> {target:.3f} (threshold {table_z + 0.04:.3f}), read back {got:.3f}"
    return "no intervention defined"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="Door,Lift")
    ap.add_argument("--size", default="84")
    a = ap.parse_args()
    _setup_env_path()
    os.environ["RLVIGEN_IMAGE_SIZE"] = str(a.size)
    import robosuitevgb.utils as ru

    print("\nPROBE -- positive control on the success signal (no monkeypatching)\n")
    bad = 0
    for name in [t.strip() for t in a.task.split(",")]:
        print(f"  {name}")
        try:
            env = ru.make_env(task_name=name, seed=0, scene_id=0, mode="train")
        except Exception as e:
            print(f"    could not build: {type(e).__name__}: {str(e)[:70]}"); bad += 1; continue
        env.reset()
        zero = np.zeros(np.shape(env.action_space.sample()))
        _, _, _, info0 = env.step(zero)
        before = bool((info0 or {}).get("success", False))

        task, chain = find_task(env)
        if task is None:
            print(f"    could not reach the robosuite task. chain: {' -> '.join(chain)}")
            bad += 1
            continue
        print(f"    chain: {' -> '.join(chain)}")
        print(f"    {drive_to_success(task, name)}")
        direct = bool(task._check_success())
        _, _, _, info1 = env.step(zero)
        after = bool((info1 or {}).get("success", False))

        ok = (not before) and direct and after
        bad += 0 if ok else 1
        print(f"    before intervention   info['success'] = {before}   "
              f"{'(good -- not stuck True)' if not before else '(BAD: stuck True)'}")
        print(f"    _check_success()      = {direct}   "
              f"{'(the task function is alive)' if direct else '(BAD: task cannot register success)'}")
        print(f"    after intervention    info['success'] = {after}   "
              f"{'(reaches the caller)' if after else '(BAD: does not propagate)'}")
        print(f"    => {'LIVE' if ok else 'NOT ESTABLISHED'}\n")

    if bad:
        print("  At least one task's success signal is NOT established as live. Until it is, a\n"
              "  reported 0.000 cannot be distinguished from a dead signal, and no floor or\n"
              "  training result on that task should be read as evidence of anything.")
    else:
        print("  Both signals are live and the thresholds are attainable in the simulator, so a\n"
              "  0.000 from a trained policy means 'did not reach the threshold' rather than\n"
              "  'the instrument is broken'.\n"
              "  This is NOT a ceiling: reachable-in-principle is not reachable-by-a-policy.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
