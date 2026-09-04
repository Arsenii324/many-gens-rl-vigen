#!/usr/bin/env python3
"""The evaluator's MEASUREMENT loop, not the arithmetic on top of it.

`tests/test_eval_across_scenes.py` has eight tests and every one of them checks aggregation — how
retention is computed once rows exist. **None checks that a recorded episode return equals the sum
of the rewards the environment actually emitted**, and that loop is the single point every number
in this project flows through: the table, the retention report, C81, C83, C86–C89.

Found on 2026-08-29 while auditing what is assured by which mechanism. The gap is exactly the shape
this project keeps finding — the layer everything rests on being the layer nobody tested — so it is
closed here with a stub environment whose rewards are known in advance.

Three properties, each with a way to be wrong that would not raise:

1. **return == sum of emitted rewards.** An off-by-one on the final step, or dropping the reward
   on the terminal transition, changes every number by a fixed fraction and looks entirely normal.
2. **success is ANY-step, not last-step.** [PART2-METRIC-INVENTORY](../docs/PART2-METRIC-INVENTORY.md)
   records this as a *chosen* convention: on Door the alternative differs whenever the policy opens
   the door and lets it swing back. A last-step reading would silently under-count.
3. **the agent is asked in eval mode.** Without it the measurement is of a noisier policy than the
   run produced — `eval_across_scenes.py` says so in its own comment, and nothing checked it.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _TS:
    def __init__(self, reward, last): self.reward, self._last = reward, last
    def last(self): return self._last
    @property
    def observation(self): return np.zeros((9, 84, 84), dtype=np.uint8)


class _Spec:
    shape, minimum, maximum = (7,), -1.0, 1.0


class _StubEnv:
    """Emits a known reward sequence and flags success on a chosen step.

    It must also report `scene_id` and `_mode` back, because `run_scene` REFUSES to measure an env
    that does not confirm the scene and regime it was asked for. That refusal is the reason a
    silent fallback to `robo_config.yaml`'s `mode: train` cannot produce a grid, and honouring it
    here is part of what this test is checking: a stub that could not satisfy it would mean the
    guard is not actually on the measurement path.
    """
    def __init__(self, rewards, success_step=None, scene_id=0, mode="train"):
        self.rewards, self.success_step = rewards, success_step
        self.scene_id, self._mode = scene_id, mode
        self.i = 0
        self.last_info = {"scene_id": scene_id}

    def action_spec(self): return _Spec()

    def reset(self):
        self.i = 0
        self.last_info = {"scene_id": self.scene_id}
        return _TS(None, False)

    def step(self, action):
        r = self.rewards[self.i]
        self.last_info = {"scene_id": self.scene_id,
                          "success": self.i == self.success_step}
        self.i += 1
        return _TS(r, self.i >= len(self.rewards))


@pytest.fixture(autouse=True)
def _restore_sys_modules():
    """Undo the module injection below. **This fixture is the whole reason the suite was red.**

    `_load` puts fake `wrappers`, `wrappers.robo_wrapper` and `utils` modules into `sys.modules` so
    `run_scene`'s function-level imports resolve to a stub. The first version never removed them,
    so **every later test that built a real environment got the stub instead** — all 25 of
    `tests/test_real_env.py` failed with `ContractError: the env did not report a regime`, while
    passing when run alone. `e` sorts before `r`, so the pollution always reached them.

    It looked like contention with a live training run and was not: a test polluting global state
    for its successors. Recorded here rather than silently fixed, because the failure mode —
    *green in isolation, red in company* — is the one a per-file re-run confirms as "fine".
    """
    import sys
    keys = ("wrappers", "wrappers.robo_wrapper", "utils", "eas_loop")
    saved = {k: sys.modules.get(k) for k in keys}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _load(stub_env, recorder=None):
    """Import eval_across_scenes with its env factory and utils replaced."""
    wr = types.ModuleType("wrappers.robo_wrapper")
    wr.robo_make = lambda **kw: stub_env
    wrappers = types.ModuleType("wrappers")
    wrappers.robo_wrapper = wr

    class _EvalMode:
        def __init__(self, *a): pass
        def __enter__(self):
            if recorder is not None: recorder.append("eval_mode")
        def __exit__(self, *a): return False

    ut = types.ModuleType("utils")
    ut.eval_mode = _EvalMode
    ut.set_seed_everywhere = lambda s: None
    for k, v in {"wrappers": wrappers, "wrappers.robo_wrapper": wr, "utils": ut}.items():
        sys.modules[k] = v
    spec = importlib.util.spec_from_file_location(
        "eas_loop", ROOT / "scripts" / "eval_across_scenes.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_recorded_return_is_the_sum_of_emitted_rewards():
    # Every reward is DISTINCT and NON-ZERO, and the last one especially. The first version of
    # this list ended in 0.0, and a mutant that dropped the reward on the terminal transition
    # therefore SURVIVED — the test could not see a defect it was written to catch. Distinct
    # values also mean a permutation or a double-count changes the sum, not just the order.
    rewards = [0.25, 0.5, 0.125, 1.0, 0.375]
    m = _load(_StubEnv(rewards))
    rets, succ, flags = m.run_scene(None, "Door", 0, "train", episodes=3, seed=0,
                             action_repeat=1, frame_stack=3, step=0)
    assert len(rets) == 3, f"asked for 3 episodes, got {len(rets)}"
    for r in rets:
        assert r == pytest.approx(sum(rewards)), (
            f"episode return {r} != sum of emitted rewards {sum(rewards)} — the loop is dropping "
            "or double-counting a transition, which shifts EVERY number in the project by a "
            "fixed fraction and looks entirely normal")


def test_per_episode_success_flags_align_with_returns():
    """The new field is only usable if its index means the same episode as `returns`'s.

    Success-conditioned return -- the reason the flags exist -- is computed by masking one array
    with the other, so a length mismatch or an off-by-one does not raise: it silently pairs
    episode i's reward with episode j's outcome and produces a plausible number. Two invariants
    catch that: same length, and the flags must SUM to the count the harness already reported,
    which is computed on a separate path (`successes += int(succeeded)`).

    `success_step=1` makes every episode succeed, so an all-zero flag list -- the shape a wrong
    variable name produces -- fails rather than passing by coincidence with an all-zero truth.
    """
    m = _load(_StubEnv([0.1] * 5, success_step=1))
    rets, succ, flags = m.run_scene(None, "Door", 0, "train", episodes=4, seed=0,
                                    action_repeat=1, frame_stack=3, step=0)
    assert len(flags) == len(rets), (
        f"{len(flags)} flags for {len(rets)} episodes -- masking one by the other would pair "
        "an episode's return with a different episode's outcome and still return a number")
    assert sum(flags) == succ, (
        f"flags sum to {sum(flags)} but the harness reports {succ} successes; the two are "
        "computed on separate paths and disagreeing means one of them is wrong")
    assert all(f == 1 for f in flags), "every episode succeeds in this stub; got " + repr(flags)


def test_success_is_any_step_not_the_last_step():
    """Door's own case: the door opens mid-episode and swings back before the end."""
    rewards = [0.1] * 5
    m = _load(_StubEnv(rewards, success_step=1))          # succeeds early, not at the end
    _, succ, _ = m.run_scene(None, "Door", 0, "train", episodes=4, seed=0,
                          action_repeat=1, frame_stack=3, step=0)
    assert succ == 4, (
        f"{succ}/4 episodes counted as successes. Success flagged on a middle step must count — "
        "a last-step reading silently under-counts exactly the case the convention was chosen for")


def test_no_success_is_reported_when_the_flag_never_fires():
    m = _load(_StubEnv([0.1] * 5, success_step=None))
    _, succ, _ = m.run_scene(None, "Door", 0, "train", episodes=4, seed=0,
                          action_repeat=1, frame_stack=3, step=0)
    assert succ == 0, "successes were counted with the flag never set — the count is not reading it"


def test_a_policy_is_asked_in_eval_mode():
    """Without it the measurement is of a noisier policy than the run produced."""
    seen = []

    class _Agent:
        def act(self, obs, step, eval_mode):
            seen.append(eval_mode)
            return np.zeros(7, dtype=np.float32)

    m = _load(_StubEnv([0.1] * 3), recorder=seen)
    m.run_scene(_Agent(), "Door", 0, "train", episodes=2, seed=0,
                action_repeat=1, frame_stack=3, step=0)
    assert seen, "the agent was never asked for an action"
    assert all(x is True for x in seen if isinstance(x, bool)), (
        "the agent was asked with eval_mode=False somewhere — this measures exploration noise")
    assert "eval_mode" in seen, "utils.eval_mode was never entered around the forward pass"
