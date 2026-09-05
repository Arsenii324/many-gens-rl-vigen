"""CTRL's evaluated return must be in Door reward units, like the other eleven baselines.

`RLViGenVecEnvCustom` -- added by runnable/_patches/ctrl.patch:686, and NOT the `ProcgenVecEnvCustom`
that sits at vec_env.py:17 -- defaults `normalize_rewards=True` and then wraps the stack in
`VecNormalize(ret=True)` OUTSIDE `VecMonitor`, dividing each reward by a running return std and
clipping at +/-10.  (REGISTER.md:198's "all twelve report raw returns" is about the monitor-recorded
training return, a different quantity from the `step()` reward this evaluator sums.)  The common evaluator had inherited that training-time default, so ctrl's episode
return was accumulated in units of its own moving statistics and was not comparable with any other
baseline's.  CTRL's own evaluator uses False (evaluate_ppo.py:38, byte-identical upstream) while its
trainer uses True (train_ppo.py:91,99,106), so this is the source's own convention, not a tuning
choice.

The first test is behavioural on CTRL's real VecNormalize -- the point being that the flag is
load-bearing, so the second test is not merely asserting a cosmetic keyword.
"""
import ast
import importlib.util
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CTRL = ROOT / "runnable" / "ctrl"


def _vec_env_module():
    if str(CTRL) not in sys.path:
        sys.path.insert(0, str(CTRL))
    spec = importlib.util.spec_from_file_location("_ctrl_vec_env", CTRL / "vec_env.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:                                    # pragma: no cover
        pytest.skip(f"ctrl vec_env is not importable here: {type(error).__name__}: {error}")
    return module


class _ConstantRewardVenv:
    """Emits a fixed Door-unit reward so any transformation is visible."""
    num_envs = 1

    def __init__(self, reward=5.0):
        from gym.spaces import Box
        self.reward = reward
        self.observation_space = Box(low=0, high=255, shape=(4,), dtype=np.uint8)
        self.action_space = Box(low=-1.0, high=1.0, shape=(7,), dtype=np.float32)

    def reset(self):
        return np.zeros((1, 4), dtype=np.uint8)

    def step_wait(self):
        return (np.zeros((1, 4), dtype=np.uint8),
                np.array([self.reward], dtype=np.float64),
                np.array([False]), [{}])


def test_vecnormalize_really_transforms_the_reward():
    """If this ever stops transforming, the flag below stops meaning anything."""
    module = _vec_env_module()
    wrapped = module.VecNormalize(venv=_ConstantRewardVenv(5.0), ob=False)
    wrapped.reset()
    seen = [float(wrapped.step_wait()[1][0]) for _ in range(5)]
    assert all(abs(value - 5.0) > 1e-6 for value in seen), (
        f"VecNormalize returned the raw reward unchanged ({seen}); this test can no longer "
        "demonstrate that normalize_rewards is load-bearing"
    )


def test_the_common_evaluator_builds_ctrl_without_reward_normalization():
    tree = ast.parse((ROOT / "scripts" / "eval_grid.py").read_text())
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "RLViGenVecEnvCustom"]
    assert calls, "the ctrl evaluator no longer constructs RLViGenVecEnvCustom"
    for call in calls:
        flags = {kw.arg: kw.value for kw in call.keywords}
        assert "normalize_rewards" in flags, (
            "RLViGenVecEnvCustom defaults normalize_rewards=True, so omitting it reports ctrl's "
            "return in normalized units and breaks comparability with the other eleven baselines"
        )
        value = flags["normalize_rewards"]
        assert isinstance(value, ast.Constant) and value.value is False, (
            "ctrl must be evaluated with normalize_rewards=False, matching evaluate_ppo.py:38"
        )
